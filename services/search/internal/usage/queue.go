package usage

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/usage/domain"
)

// queueItem is the `QueueItem` DTO (API-CONTRACT §5.5).
type queueItem struct {
	ItemID   string         `json:"item_id"`
	SkillID  string         `json:"skill_id"`
	Revision *string        `json:"revision"`
	Reason   string         `json:"reason"`
	Since    *string        `json:"since"`
	Evidence map[string]any `json:"evidence"`
	Decision *decisionDTO   `json:"decision"`
	// Source separates an item a worker wrote from one this report derived, so
	// the reader knows which of the two they are looking at.
	Source string `json:"source"`
}

type decisionDTO struct {
	Action string  `json:"action"`
	Reason *string `json:"reason"`
	At     *string `json:"at"`
}

// The two reasons the report derives from telemetry. The other three
// (`source_changed`, `source_removed`, `missing_dependency`) are written by the
// import worker: they are facts about the repository, not about usage.
var computedReasons = map[string]bool{"negative_feedback": true, "zero_loads": true}

// decisionActions is the closed set from API-CONTRACT §4.6. "no_change" is a
// decision with a reason, not the absence of one.
var decisionActions = map[string]bool{"reviewed": true, "fixed_in_git": true, "no_change": true}

// computedID is the stable identifier of a derived item: `reason:skill_id:revision`.
// It has to be stable across requests, because an owner deciding an item must
// close the same item the list showed them, and nothing persisted it.
func computedID(reason, skillID, revision string) string {
	return reason + ":" + skillID + ":" + revision
}

// splitComputedID reverses computedID. A skill URN contains colons, so the
// reason is read from the front and the revision from the back — the remainder
// is the URN, whatever colons it holds.
func splitComputedID(id string) (reason, skillID, revision string, ok bool) {
	head, rest, found := strings.Cut(id, ":")
	if !found || !computedReasons[head] {
		return "", "", "", false
	}
	cut := strings.LastIndex(rest, ":")
	if cut < 0 {
		return "", "", "", false
	}
	return head, rest[:cut], rest[cut+1:], true
}

// derivedUUID turns a computed identifier into the uuid the table needs, the
// same way every time. Deciding the same derived item twice therefore updates
// one row instead of appending a second one.
func derivedUUID(id string) string {
	sum := sha256.Sum256([]byte("guidefold.usage.queue:" + id))
	b := sum[:16]
	b[6] = (b[6] & 0x0f) | 0x50 // version 5: a name-based identifier
	b[8] = (b[8] & 0x3f) | 0x80
	s := hex.EncodeToString(b)
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}

// queueRow is one gfm.owner_queue row as read.
type queueRow struct {
	itemID   string
	skillID  string
	revision string
	reason   string
	since    time.Time
	evidence []byte
	state    string
	decision *string
	reasonTx *string
	decided  *time.Time
}

// queue merges what the import worker wrote with what this report derived.
//
// A derived item is suppressed as soon as a row exists for the same
// (skill, reason, revision): either the worker already raised it, or an owner
// already decided it. That is what makes the derived items decidable at all —
// the decision is a row, so the observation stops being asked about.
func (s *Service) queue(ctx context.Context, orgID, repoID string, report domain.Report,
	meta map[string]domain.SkillMeta) ([]queueItem, error) {
	rows, e := s.pool.Query(ctx, `SELECT item_id::text,skill_id,revision_id,reason,since,
 evidence,state,decision,decision_reason,decided_at
 FROM gfm.owner_queue
 WHERE org_id=$1::uuid AND repo_id=$2
   AND (state='open' OR reason IN ('negative_feedback','zero_loads'))
 ORDER BY since DESC,item_id`, orgID, repoID)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	items := []queueItem{}
	settled := map[string]bool{}
	for rows.Next() {
		var r queueRow
		var revision *string
		if e := rows.Scan(&r.itemID, &r.skillID, &revision, &r.reason, &r.since, &r.evidence,
			&r.state, &r.decision, &r.reasonTx, &r.decided); e != nil {
			return nil, mgmt.Internal(e)
		}
		r.revision = text(revision)
		settled[computedID(r.reason, r.skillID, r.revision)] = true
		if r.state != "open" {
			continue
		}
		items = append(items, persistedItem(r))
	}
	if e := rows.Err(); e != nil {
		return nil, mgmt.Internal(e)
	}
	for _, computed := range report.Computed {
		id := computedID(computed.Reason, computed.SkillID, computed.Revision)
		if settled[id] {
			continue
		}
		if m, ok := meta[computed.SkillID]; ok && m.RepoID != repoID {
			continue
		}
		since := computed.Since.UTC().Format(time.RFC3339)
		items = append(items, queueItem{ItemID: id, SkillID: computed.SkillID,
			Revision: optional(computed.Revision), Reason: computed.Reason,
			Since: &since, Evidence: computed.Evidence, Source: "computed"})
	}
	return items, nil
}

func persistedItem(r queueRow) queueItem {
	since := r.since.UTC().Format(time.RFC3339)
	item := queueItem{ItemID: r.itemID, SkillID: r.skillID, Revision: optional(r.revision),
		Reason: r.reason, Since: &since, Source: "worker"}
	if len(r.evidence) > 0 {
		var evidence map[string]any
		if json.Unmarshal(r.evidence, &evidence) == nil {
			item.Evidence = evidence
		}
	}
	if r.decision != nil {
		at := ""
		if r.decided != nil {
			at = r.decided.UTC().Format(time.RFC3339)
		}
		item.Decision = &decisionDTO{Action: *r.decision, Reason: r.reasonTx, At: optional(at)}
	}
	return item
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

type decisionRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
	Action         string `json:"action"`
	Reason         string `json:"reason"`
}

// handleDecision closes one review item.
//
// The decision is the point of the queue: U9 asks that closing a review records
// who decided, on which revision, and why. It changes nothing about the skill —
// "the source changed" is an observation and "the skill is wrong" is a
// judgment, and only a person makes the second one.
func (s *Service) handleDecision(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req decisionRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if !decisionActions[req.Action] {
		return mgmt.Invalid("invalid_request",
			"action must be one of reviewed, fixed_in_git, no_change.")
	}
	reason := strings.TrimSpace(req.Reason)
	if len(reason) < 3 || len(reason) > 500 {
		return mgmt.Invalid("invalid_request", "reason must be 3 to 500 characters.")
	}
	itemID := c.Param("item_id")
	if itemID == "" || len(itemID) > 400 {
		return mgmt.Invalid("invalid_request", "item_id is missing or too long.")
	}
	actor := ""
	if c.Principal != nil {
		actor = c.Principal.UserID
	}
	tx, err := c.Tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())

	var item queueItem
	if reasonName, skillID, revision, ok := splitComputedID(itemID); ok {
		item, e = s.decideComputed(c, tx, org.ID, repo.ID, itemID, reasonName, skillID, revision,
			req.Action, reason, actor)
	} else {
		item, e = s.decidePersisted(c, tx, org.ID, repo.ID, itemID, req.Action, reason, actor)
	}
	if e != nil {
		return e
	}
	revision := ""
	if item.Revision != nil {
		revision = *item.Revision
	}
	if err := c.Audit(c.Ctx(), tx, org.ID, "usage.queue."+req.Action,
		"queue_item:"+item.ItemID, revision); err != nil {
		return mgmt.Internal(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "item": item})
}

// decidePersisted closes an item a worker raised. Only an open item can be
// decided: re-deciding a closed one would overwrite the record of who decided
// it first.
func (s *Service) decidePersisted(c *mgmt.Context, tx pgx.Tx, orgID, repoID, itemID,
	action, reason, actor string) (queueItem, error) {
	var r queueRow
	var revision *string
	e := tx.QueryRow(c.Ctx(), `UPDATE gfm.owner_queue
 SET state='resolved',decision=$4,decision_reason=$5,decided_by=$6::uuid,decided_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND item_id=$3::uuid AND state='open'
 RETURNING item_id::text,skill_id,revision_id,reason,since,evidence,state,
  decision,decision_reason,decided_at`,
		orgID, repoID, itemID, action, reason, nullable(actor)).
		Scan(&r.itemID, &r.skillID, &revision, &r.reason, &r.since, &r.evidence, &r.state,
			&r.decision, &r.reasonTx, &r.decided)
	if isNoRows(e) {
		return queueItem{}, mgmt.NotFound("not_found", "No open review item with that id.")
	}
	if e != nil {
		// An item_id that is neither a uuid nor a derived id is a bad request,
		// not a server fault.
		if strings.Contains(e.Error(), "invalid input syntax for type uuid") {
			return queueItem{}, mgmt.Invalid("invalid_request", "item_id is not a review item id.")
		}
		return queueItem{}, mgmt.Internal(e)
	}
	r.revision = text(revision)
	if e := settleDriftStatus(c, tx, orgID, repoID, r.skillID, r.reason); e != nil {
		return queueItem{}, e
	}
	return persistedItem(r), nil
}

// settleDriftStatus closes the *skill's* half of a drift item, in the same
// transaction as the decision.
//
// The drift pass marks a skill whose source changed `needs_review` and asks the
// owner a question; publication deliberately no longer answers it (build.go,
// markPublished). The answer is this decision, whichever of the three it is:
// `reviewed`, `fixed_in_git` and `no_change` all mean a person looked. A
// `source_removed` item is different — the file is still gone, so the skill
// stays `archived` and only an import that brings it back changes that. Every
// other reason is an observation about usage and never touches the status.
//
// This is the "API (decyzja)" writer that §7 names for `gfm.skills`; it is the
// owner's decision, not the telemetry ingest path, that writes here.
func settleDriftStatus(c *mgmt.Context, tx pgx.Tx, orgID, repoID, skillID, reason string) error {
	if reason != "source_changed" {
		return nil
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.skills
 SET publication_status='published',updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=$3 AND publication_status='needs_review'`,
		orgID, repoID, skillID); e != nil {
		return mgmt.Internal(e)
	}
	return nil
}

// decideComputed records a decision on an item this report derived. The row it
// writes is what makes the derivation stop being asked about, so the same
// observation does not come back the next time the window is recomputed.
func (s *Service) decideComputed(c *mgmt.Context, tx pgx.Tx, orgID, repoID, itemID,
	reasonName, skillID, revision, action, reason, actor string) (queueItem, error) {
	var known string
	e := tx.QueryRow(c.Ctx(), `SELECT repo_id FROM gfm.skills
 WHERE org_id=$1::uuid AND skill_id=$2`, orgID, skillID).Scan(&known)
	if isNoRows(e) || (e == nil && known != repoID) {
		return queueItem{}, mgmt.NotFound("not_found", "No review item with that id.")
	}
	if e != nil {
		return queueItem{}, mgmt.Internal(e)
	}
	// Close the worker's twin first, if one exists, so the same observation is
	// not left open under a different identifier.
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.owner_queue
 SET state='resolved',decision=$5,decision_reason=$6,decided_by=$7::uuid,decided_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=$3 AND reason=$4
   AND revision_id IS NOT DISTINCT FROM $8 AND state='open'`,
		orgID, repoID, skillID, reasonName, action, reason, nullable(actor),
		nullable(revision)); e != nil {
		return queueItem{}, mgmt.Internal(e)
	}
	evidence, _ := json.Marshal(map[string]any{"computed_item_id": itemID})
	var decidedAt time.Time
	if e := tx.QueryRow(c.Ctx(), `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence,state,
  decision,decision_reason,decided_by,decided_at)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7::jsonb,'resolved',$8,$9,$10::uuid,now())
 ON CONFLICT (org_id,item_id) DO UPDATE SET
  state='resolved',decision=EXCLUDED.decision,decision_reason=EXCLUDED.decision_reason,
  decided_by=EXCLUDED.decided_by,decided_at=now()
 RETURNING decided_at`,
		orgID, derivedUUID(itemID), repoID, skillID, nullable(revision), reasonName,
		string(evidence), action, reason, nullable(actor)).Scan(&decidedAt); e != nil {
		return queueItem{}, mgmt.Internal(e)
	}
	at := decidedAt.UTC().Format(time.RFC3339)
	reasonCopy := reason
	return queueItem{ItemID: itemID, SkillID: skillID, Revision: optional(revision),
		Reason: reasonName, Source: "computed",
		Evidence: map[string]any{"computed_item_id": itemID},
		Decision: &decisionDTO{Action: action, Reason: &reasonCopy, At: &at}}, nil
}
