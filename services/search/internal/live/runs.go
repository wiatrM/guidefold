package live

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// maxTargetRepos mirrors live.plan's own limit (API-CONTRACT §8, max_repos
// 50): the worker enforces it against the repositories it actually resolves,
// this is only the same number carried in the job's limits.
const maxTargetRepos = 50

// costView is the `LiveRun.cost` DTO (API-CONTRACT §5.5a). Decoding into this
// struct rather than passing the jsonb column through means an empty '{}'
// (every run before its first worker write) renders as real zeros and
// usd_estimated:false, which is what the schema requires, not an empty
// object.
type costView struct {
	TokensIn     int64   `json:"tokens_in"`
	TokensOut    int64   `json:"tokens_out"`
	USD          float64 `json:"usd"`
	USDEstimated bool    `json:"usd_estimated"`
}

// countsView is the `LiveRun.counts` DTO, always computed live from
// gfm.live_run_targets rather than cached on the run row: it is the one
// number a client actually watches while a run is in flight.
type countsView struct {
	Targets int `json:"targets"`
	Done    int `json:"done"`
	Failed  int `json:"failed"`
	Skipped int `json:"skipped"`
}

// runView is the `LiveRun` DTO.
type runView struct {
	RunID      string     `json:"run_id"`
	State      string     `json:"state"`
	Prompt     string     `json:"prompt"`
	Provider   string     `json:"provider"`
	Model      string     `json:"model"`
	CreatedBy  *string    `json:"created_by"`
	CreatedAt  time.Time  `json:"created_at"`
	StartedAt  *time.Time `json:"started_at"`
	FinishedAt *time.Time `json:"finished_at"`
	Counts     countsView `json:"counts"`
	Cost       costView   `json:"cost"`
	Error      *string    `json:"error"`
}

// targetView is the `LiveRunTarget` DTO.
type targetView struct {
	RepoID     string     `json:"repo_id"`
	State      string     `json:"state"`
	JobID      *string    `json:"job_id"`
	Findings   int        `json:"findings"`
	Error      *string    `json:"error"`
	StartedAt  *time.Time `json:"started_at"`
	FinishedAt *time.Time `json:"finished_at"`
}

// runSelect reads one run alongside its counts, computed live from
// gfm.live_run_targets by the same join and the same three FILTER clauses
// every route that shows a run uses — create's first response, the list, the
// single-run read and cancel's answer can never disagree about what a run's
// counts mean. A caller appends its own WHERE, then runGroupBy, then any
// ORDER BY/LIMIT.
const runSelect = `SELECT r.run_id::text,r.state,r.prompt,r.provider,r.model,r.created_by::text,
 r.created_at,r.started_at,r.finished_at,r.cost::text,r.error,
 count(t.repo_id) AS targets,
 count(t.repo_id) FILTER (WHERE t.state='done') AS done,
 count(t.repo_id) FILTER (WHERE t.state='failed') AS failed,
 count(t.repo_id) FILTER (WHERE t.state='skipped') AS skipped
 FROM gfm.live_runs r
 LEFT JOIN gfm.live_run_targets t ON t.org_id=r.org_id AND t.run_id=r.run_id`

const runGroupBy = `GROUP BY r.run_id,r.state,r.prompt,r.provider,r.model,r.created_by,
 r.created_at,r.started_at,r.finished_at,r.cost,r.error`

func scanRun(row pgx.Row) (runView, error) {
	var v runView
	var createdBy, costRaw, runError *string
	var targets, done, failed, skipped int64
	e := row.Scan(&v.RunID, &v.State, &v.Prompt, &v.Provider, &v.Model, &createdBy,
		&v.CreatedAt, &v.StartedAt, &v.FinishedAt, &costRaw, &runError,
		&targets, &done, &failed, &skipped)
	if e != nil {
		return v, e
	}
	v.CreatedBy, v.Error = createdBy, runError
	v.Counts = countsView{Targets: int(targets), Done: int(done), Failed: int(failed), Skipped: int(skipped)}
	v.Cost = decodeCost(costRaw)
	return v, nil
}

// decodeCost turns the run's cost jsonb into the DTO's required, non-null
// shape. A worker that has not written anything yet (or a column holding
// '{}') decodes to real zeros and usd_estimated:false, which is what an
// unstarted run's cost actually is — not "unknown".
func decodeCost(raw *string) costView {
	var c costView
	if raw == nil || *raw == "" {
		return c
	}
	_ = json.Unmarshal([]byte(*raw), &c)
	return c
}

// loadRunByID reads one run of one organisation, or live_run_not_found. It is
// the single place that translates "no such row" into the contract's error,
// so create, get and cancel answer it identically.
func (s *Service) loadRunByID(ctx context.Context, orgID, runID string) (runView, error) {
	if !looksLikeUUID(runID) {
		return runView{}, mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	row := s.pool.QueryRow(ctx, runSelect+`
 WHERE r.org_id=$1::uuid AND r.run_id=$2::uuid `+runGroupBy, orgID, runID)
	v, e := scanRun(row)
	if isNoRows(e) {
		return runView{}, mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	if e != nil {
		return runView{}, mgmt.Internal(e)
	}
	return v, nil
}

func (s *Service) loadTargets(ctx context.Context, orgID, runID string) ([]targetView, error) {
	rows, e := s.pool.Query(ctx, `SELECT repo_id,state,job_id::text,findings,error,started_at,finished_at
 FROM gfm.live_run_targets WHERE org_id=$1::uuid AND run_id=$2::uuid ORDER BY repo_id`, orgID, runID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	items := []targetView{}
	for rows.Next() {
		var v targetView
		var jobID, errText *string
		if e := rows.Scan(&v.RepoID, &v.State, &jobID, &v.Findings, &errText,
			&v.StartedAt, &v.FinishedAt); e != nil {
			return nil, e
		}
		v.JobID, v.Error = jobID, errText
		items = append(items, v)
	}
	return items, rows.Err()
}

type createRunRequest struct {
	Prompt   string   `json:"prompt"`
	Provider string   `json:"provider"`
	Model    string   `json:"model"`
	Repos    []string `json:"repos"`
}

// handleCreate starts one run. Validation, the credential check, the
// one-active-run check, the run row, its opening event and the live.plan job
// all happen in one transaction, so a run is never visible without the event
// and the job that make it progress (API-CONTRACT §8: enqueue joins the
// caller's transaction).
func (s *Service) handleCreate(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req createRunRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	prompt, provider, model, e := validateRun(req.Prompt, req.Provider, req.Model)
	if e != nil {
		return e
	}

	tx, e := c.Tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()

	var hasCredential bool
	if e := tx.QueryRow(c.Ctx(), `SELECT EXISTS(SELECT 1 FROM gfm.org_credentials
 WHERE org_id=$1::uuid AND provider=$2)`, org.ID, provider).Scan(&hasCredential); e != nil {
		return mgmt.Internal(e)
	}
	if !hasCredential {
		return mgmt.Fail(http.StatusConflict, "model_credential_missing",
			"This organisation has no key for that provider; add one before starting a run.")
	}

	if active, e := activeRunID(c.Ctx(), tx, org.ID); e != nil {
		return e
	} else if active != "" {
		return alreadyActive(active)
	}

	runID := jobs.NewID()
	_, insertErr := tx.Exec(c.Ctx(), `INSERT INTO gfm.live_runs
 (org_id,run_id,state,prompt,provider,model,created_by)
 VALUES($1::uuid,$2::uuid,'queued',$3,$4,$5,$6::uuid)`,
		org.ID, runID, prompt, provider, model, nullable(c.Principal.UserID))
	if isUniqueViolation(insertErr) {
		// The friendly pre-check above can race a concurrent start; the
		// partial index is the actual guarantee (ADR-0046 §6), and losing the
		// race still has to name the run that won it.
		_ = tx.Rollback(c.Ctx())
		active, e := activeRunID(c.Ctx(), s.pool, org.ID)
		if e != nil {
			return e
		}
		return alreadyActive(active)
	}
	if insertErr != nil {
		return mgmt.Internal(insertErr)
	}

	if _, e := Append(c.Ctx(), tx, org.ID, runID, "", EventRunStarted,
		map[string]any{"provider": provider, "model": model}); e != nil {
		return mgmt.Internal(e)
	}

	payload, e := json.Marshal(map[string]any{"schema_version": PayloadVersion,
		"org_id": org.ID, "run_id": runID, "repos": req.Repos})
	if e != nil {
		return mgmt.Internal(e)
	}
	limits, e := json.Marshal(map[string]int{"max_repos": maxTargetRepos})
	if e != nil {
		return mgmt.Internal(e)
	}
	plan := jobs.Job{OrgID: org.ID, Kind: KindPlan, Payload: payload, InputDigest: runID,
		Limits: limits, IdempotencyKey: KindPlan + ":" + runID}
	if _, e := s.queue.Enqueue(c.Ctx(), tx, plan); e != nil {
		return mgmt.Internal(e)
	}

	if e := c.Audit(c.Ctx(), tx, org.ID, "live.start", "live_run:"+runID, provider+":"+model); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}

	run, e := s.loadRunByID(c.Ctx(), org.ID, runID)
	if e != nil {
		return e
	}
	return c.JSON(http.StatusAccepted, run)
}

func (s *Service) handleList(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	limit := 50
	if v := c.Query("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > 100 {
			return mgmt.Invalid("invalid_request", "limit must be between 1 and 100.")
		}
		limit = n
	}
	after, before := time.Time{}, ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 2)
		if err != nil {
			return err
		}
		ts, perr := time.Parse(time.RFC3339Nano, parts[0])
		if perr != nil {
			return mgmt.Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
		}
		after, before = ts, parts[1]
	}
	rows, err := s.pool.Query(c.Ctx(), runSelect+`
 WHERE r.org_id=$1::uuid
   AND ($2::timestamptz IS NULL OR (r.created_at,r.run_id::text) < ($2::timestamptz,$3))
 `+runGroupBy+`
 ORDER BY r.created_at DESC,r.run_id DESC LIMIT $4`,
		org.ID, nullableTime(after), before, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []runView{}
	for rows.Next() {
		v, e := scanRun(rows)
		if e != nil {
			return mgmt.Internal(e)
		}
		items = append(items, v)
	}
	if e := rows.Err(); e != nil {
		return mgmt.Internal(e)
	}
	next := ""
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		next = mgmt.EncodeCursor(last.CreatedAt.UTC().Format(time.RFC3339Nano), last.RunID)
	}
	return c.JSON(http.StatusOK, map[string]any{"items": items, "next_cursor": nullable(next)})
}

func (s *Service) handleGet(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	runID := c.Param("run_id")
	run, e := s.loadRunByID(c.Ctx(), org.ID, runID)
	if e != nil {
		return e
	}
	targets, e := s.loadTargets(c.Ctx(), org.ID, runID)
	if e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{"run": run, "targets": targets})
}

func nullableTime(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return t
}
