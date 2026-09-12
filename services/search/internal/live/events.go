package live

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// eventView is the `LiveRunEvent` DTO.
type eventView struct {
	Seq     int64           `json:"seq"`
	At      time.Time       `json:"at"`
	RepoID  *string         `json:"repo_id"`
	Type    string          `json:"type"`
	Payload json.RawMessage `json:"payload"`
}

// Append writes the next event of a run under the run row's own lock, so two
// concurrent writers — the worker fanning live.repo out across repositories —
// agree on the next seq instead of colliding on the primary key.
// gfm.live_run_events has no row of its own to lock before the first insert,
// which is why the lock is taken on gfm.live_runs instead.
//
// text is the one Polish sentence this event carries in payload.text
// (§5.5a): the console prints it exactly as returned rather than translating
// a type code into words on its own side, so a second person reading the
// same run through the API sees exactly what the first one saw live. text is
// a required, positional argument rather than a field a caller can leave out
// of fields, so an empty one is an error, not a blank line in someone's
// console. fields is merged alongside it into payload and may be nil.
//
// It enforces the 20,000-event cap of §5.5a: once the log already holds
// maxEventsPerRun rows, every event type except repo.finished and
// run.finished — the two that end something — is dropped rather than
// appended, and a caller must read a returned (0, nil) as "dropped", never as
// failure. The first repo.finished or run.finished past the cap is preceded
// by exactly one error event naming live_run_log_truncated. That guard is a
// query, not an in-process flag: the worker can restart mid-run, and only
// the log itself can say whether the notice was already written.
func Append(ctx context.Context, tx jobs.Tx, orgID, runID, repoID, eventType, text string, fields map[string]any) (int64, error) {
	if strings.TrimSpace(text) == "" {
		return 0, fmt.Errorf("live: Append %s event with empty payload.text", eventType)
	}
	var locked int
	if e := tx.QueryRow(ctx, `SELECT 1 FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid FOR UPDATE`, orgID, runID).Scan(&locked); e != nil {
		return 0, e
	}
	// The next seq is always one past the highest already assigned, never a
	// row count: Append never leaves a gap, so the two agree in the normal
	// path, but reading it this way is what lets the cap be reached (and
	// tested) by seeding one row at seq=maxEventsPerRun rather than by
	// inserting the cap's worth of rows one at a time.
	var high int64
	if e := tx.QueryRow(ctx, `SELECT COALESCE(max(seq),0) FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID).Scan(&high); e != nil {
		return 0, e
	}
	if high >= maxEventsPerRun {
		if eventType != EventRepoFinished && eventType != EventRunFinished {
			return 0, nil
		}
		var already bool
		if e := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND type=$3 AND payload->>'reason'=$4)`,
			orgID, runID, EventError, ErrorLogTruncated).Scan(&already); e != nil {
			return 0, e
		}
		if !already {
			seq, e := insertEvent(ctx, tx, orgID, runID, high+1, "", EventError, map[string]any{
				"reason": ErrorLogTruncated,
				"text":   "Dziennik zdarzeń osiągnął limit 20 000 wpisów; od teraz zapisywane są już tylko zakończenia repozytoriów i przebiegu.",
			})
			if e != nil {
				return 0, e
			}
			high = seq
		}
	}
	payload := map[string]any{"text": text}
	for k, v := range fields {
		payload[k] = v
	}
	return insertEvent(ctx, tx, orgID, runID, high+1, repoID, eventType, payload)
}

func insertEvent(ctx context.Context, tx jobs.Tx, orgID, runID string, seq int64,
	repoID, eventType string, payload any) (int64, error) {
	body, e := json.Marshal(payload)
	if e != nil {
		return 0, e
	}
	if len(body) == 0 || string(body) == "null" {
		body = []byte("{}")
	}
	if _, e := tx.Exec(ctx, `INSERT INTO gfm.live_run_events(org_id,run_id,seq,repo_id,type,payload)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6::jsonb)`,
		orgID, runID, seq, nullable(repoID), eventType, string(body)); e != nil {
		return 0, e
	}
	return seq, nil
}

// handleEvents answers one page of the log. It is the contract's only live
// channel and deliberately not a streaming one (ADR-0046 §4): the page is
// read first and the run's state and the log's current high-water mark only
// after, so a run that finishes mid-request cannot make `done` true while
// events this very response did not return are still waiting — reading the
// high-water mark first would race exactly that.
func (s *Service) handleEvents(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	runID := c.Param("run_id")
	if !looksLikeUUID(runID) {
		return mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	after := int64(0)
	if v := c.Query("after"); v != "" {
		n, err := strconv.ParseInt(v, 10, 64)
		if err != nil || n < 0 {
			return mgmt.Invalid("invalid_integer", "after must be a non-negative integer.")
		}
		after = n
	}
	limit := defaultEventLimit
	if v := c.Query("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > maxEventLimit {
			return mgmt.Invalid("invalid_integer", "limit must be between 1 and 500.")
		}
		limit = n
	}

	rows, err := s.pool.Query(c.Ctx(), `SELECT seq,at,repo_id,type,payload::text
 FROM gfm.live_run_events WHERE org_id=$1::uuid AND run_id=$2::uuid AND seq>$3
 ORDER BY seq LIMIT $4`, org.ID, runID, after, limit)
	if err != nil {
		return mgmt.Internal(err)
	}
	items := []eventView{}
	nextAfter := after
	for rows.Next() {
		var v eventView
		var repoID *string
		var payload string
		if e := rows.Scan(&v.Seq, &v.At, &repoID, &v.Type, &payload); e != nil {
			rows.Close()
			return mgmt.Internal(e)
		}
		v.RepoID = repoID
		v.Payload = json.RawMessage(payload)
		items = append(items, v)
		nextAfter = v.Seq
	}
	if e := rows.Err(); e != nil {
		rows.Close()
		return mgmt.Internal(e)
	}
	rows.Close()

	var state string
	var maxSeq *int64
	e = s.pool.QueryRow(c.Ctx(), `SELECT r.state,
 (SELECT max(seq) FROM gfm.live_run_events WHERE org_id=r.org_id AND run_id=r.run_id)
 FROM gfm.live_runs r WHERE r.org_id=$1::uuid AND r.run_id=$2::uuid`, org.ID, runID).
		Scan(&state, &maxSeq)
	if isNoRows(e) {
		return mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	var high int64
	if maxSeq != nil {
		high = *maxSeq
	}
	// done only when the run will never append again AND this page reached
	// the log's current end — never on an empty page, which for a running
	// agent is normal quiet, not completion.
	done := isTerminal(state) && nextAfter >= high
	return c.JSON(http.StatusOK, map[string]any{"items": items, "next_after": nextAfter, "done": done})
}
