package agentrun

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// liveRepoPayloadVersion labels every live.repo payload this package
// writes. It is a version of this package's own payload shape, not of
// live.PayloadVersion (that one names live.plan's payload) — the two job
// kinds are versioned independently because either one's shape can change
// without the other's.
const liveRepoPayloadVersion = "live.repo-1"

// livePlanPayload mirrors exactly what internal/live's handleCreate writes
// (runs.go): {schema_version, org_id, run_id}. There is no repos field
// (API-CONTRACT §4.9, 1.6.0): a run always covers every repository of the
// organisation, so there is nothing else for the API to tell live.plan.
type livePlanPayload struct {
	SchemaVersion string `json:"schema_version"`
	OrgID         string `json:"org_id"`
	RunID         string `json:"run_id"`
}

// liveRepoPayload is what live.plan enqueues per target, matching
// API-CONTRACT §8's live.repo input column: run_id, repo_id,
// installation_id. full_name travels alongside it because ghapp's read
// operations need it and re-deriving it from gfm.repos inside every
// live.repo job would mean a second query this job already paid for.
type liveRepoPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	RunID          string `json:"run_id"`
	RepoID         string `json:"repo_id"`
	InstallationID int64  `json:"installation_id"`
	FullName       string `json:"full_name"`
}

// LivePlanWorker runs live.plan: ADR-0046 point 3's fan-out.
type LivePlanWorker struct {
	pool  *pgxpool.Pool
	queue *jobs.Queue
}

// NewLivePlanWorker wires the handler over one database.
func NewLivePlanWorker(pool *pgxpool.Pool) *LivePlanWorker {
	return &LivePlanWorker{pool: pool, queue: jobs.New(pool)}
}

// Handlers maps the job kind this worker runs.
func (w *LivePlanWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{live.KindPlan: w.Run}
}

// planTarget is one repository this plan resolved, before its target row
// exists.
type planTarget struct {
	repoID         string
	installationID int64
	fullName       string
	skipReason     string // "" means queued; anything else is TargetSkipped
}

// Run executes one live.plan job.
func (w *LivePlanWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload livePlanPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode live.plan payload: %w", e))
	}
	if payload.SchemaVersion != live.PayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported live.plan payload schema_version %q", payload.SchemaVersion))
	}
	if payload.OrgID != t.Job.OrgID || payload.RunID == "" {
		return worker.Permanent(errors.New("live.plan payload does not match its job row"))
	}

	targets, e := w.resolveTargets(ctx, payload.OrgID)
	if e != nil {
		return e
	}

	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}

	limits, e := w.startRun(ctx, tx, payload.OrgID, payload.RunID)
	if e != nil {
		return e
	}

	for _, tg := range targets {
		if e := w.writeTarget(ctx, tx, payload.OrgID, payload.RunID, tg, limits); e != nil {
			return e
		}
	}

	// Every target this job leaves in a terminal state — none at all, or a set
	// where each repository was skipped for want of an installation — has no
	// live.repo job coming to end the run, so the plan ends it here.
	// maybeFinishRun is a no-op while any target is still queued or running, so
	// the ordinary case is unaffected. Doing this only for zero targets left a
	// run whose every repository was skipped saying "running" for ever, which
	// is the worst of the states to be wrong about: an owner waits for an
	// answer that is already complete.
	if e := maybeFinishRun(ctx, tx, payload.OrgID, payload.RunID); e != nil {
		return e
	}

	if e := tx.Commit(ctx); e != nil {
		return e
	}
	t.Result = mustJSON(map[string]any{"targets": len(targets)})
	return nil
}

// startRun locks the run row, moves it from queued to running (the
// bookkeeping this job kind owns before any repository starts), and
// appends run.started exactly once — API-CONTRACT §8 lists it as this job
// kind's own output, and the create endpoint may already have written one,
// so this checks before appending rather than trusting that it is first.
// It returns the effective limits, writing the package defaults into the
// run row when none were set (see limits.go).
func (w *LivePlanWorker) startRun(ctx context.Context, tx pgx.Tx, orgID, runID string) (Limits, error) {
	var provider, model, state string
	var rawLimits []byte
	e := tx.QueryRow(ctx, `SELECT provider, model, state, limits::text FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid FOR UPDATE`, orgID, runID).Scan(&provider, &model, &state, &rawLimits)
	if errors.Is(e, pgx.ErrNoRows) {
		return Limits{}, worker.Permanent(fmt.Errorf("live.plan: no such run %s", runID))
	}
	if e != nil {
		return Limits{}, e
	}
	limits := decodeLimits(rawLimits)
	if len(rawLimits) == 0 || string(rawLimits) == "{}" {
		if _, e := tx.Exec(ctx, `UPDATE gfm.live_runs SET limits=$3::jsonb
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID, string(mustJSON(limits))); e != nil {
			return Limits{}, e
		}
	}
	if state == live.StateQueued {
		if _, e := tx.Exec(ctx, `UPDATE gfm.live_runs SET state=$3, started_at=COALESCE(started_at, now())
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID, live.StateRunning); e != nil {
			return Limits{}, e
		}
	}
	var alreadyStarted bool
	if e := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND type=$3)`, orgID, runID, live.EventRunStarted).
		Scan(&alreadyStarted); e != nil {
		return Limits{}, e
	}
	if !alreadyStarted {
		if _, e := live.Append(ctx, tx, orgID, runID, "", live.EventRunStarted, live.EventRunStartedText,
			map[string]any{"provider": provider, "model": model}); e != nil {
			return Limits{}, e
		}
	}
	return limits, nil
}

// writeTarget inserts one target row (ON CONFLICT DO NOTHING, so a
// re-leased live.plan after a crash produces no second row) and, for a
// resolvable target, enqueues its live.repo job and records the job id on
// the row.
func (w *LivePlanWorker) writeTarget(ctx context.Context, tx pgx.Tx, orgID, runID string, tg planTarget, limits Limits) error {
	state := live.TargetQueued
	if tg.skipReason != "" {
		state = live.TargetSkipped
	}
	tag, e := tx.Exec(ctx, `INSERT INTO gfm.live_run_targets(org_id,run_id,repo_id,state,error)
 VALUES($1::uuid,$2::uuid,$3,$4,$5)
 ON CONFLICT (org_id,run_id,repo_id) DO NOTHING`,
		orgID, runID, tg.repoID, state, nullable(tg.skipReason))
	if e != nil {
		return e
	}
	if tag.RowsAffected() == 0 || tg.skipReason != "" {
		return nil
	}
	payload := mustJSON(liveRepoPayload{SchemaVersion: liveRepoPayloadVersion, OrgID: orgID, RunID: runID,
		RepoID: tg.repoID, InstallationID: tg.installationID, FullName: tg.fullName})
	job := jobs.Job{OrgID: orgID, Kind: live.KindRepo, RepoID: tg.repoID, Payload: payload,
		InputDigest: runID + ":" + tg.repoID, Limits: mustJSON(limits),
		IdempotencyKey: live.KindRepo + ":" + runID + ":" + tg.repoID}
	created, e := w.queue.Enqueue(ctx, tx, job)
	if e != nil {
		return e
	}
	_, e = tx.Exec(ctx, `UPDATE gfm.live_run_targets SET job_id=$4::uuid
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, orgID, runID, tg.repoID, created.JobID)
	return e
}

// resolveTargets is every repository of the organisation (API-CONTRACT
// §4.9, 1.6.0: a run always covers all of them, never a chosen subset),
// each matched against its GitHub App installation (installation.go) —
// never filtered by whether that match succeeds: a repository with none
// becomes a skipped target with a named reason, exactly what API-CONTRACT
// §4.9 requires ("never silently pominięte").
func (w *LivePlanWorker) resolveTargets(ctx context.Context, orgID string) ([]planTarget, error) {
	repoRows, e := w.pool.Query(ctx, `SELECT repo_id, git_host_url FROM gfm.repos
 WHERE org_id=$1::uuid ORDER BY repo_id`, orgID)
	if e != nil {
		return nil, e
	}
	defer repoRows.Close()
	type repoRow struct{ id, url string }
	var order []string
	byID := map[string]repoRow{}
	for repoRows.Next() {
		var r repoRow
		if e := repoRows.Scan(&r.id, &r.url); e != nil {
			return nil, e
		}
		byID[r.id] = r
		order = append(order, r.id)
	}
	if e := repoRows.Err(); e != nil {
		return nil, e
	}

	lookup, e := loadInstallationLookup(ctx, w.pool, orgID)
	if e != nil {
		return nil, e
	}

	targets := make([]planTarget, 0, len(order))
	for _, repoID := range order {
		r := byID[repoID]
		installationID, fullName, ok := lookup.resolve(r.url)
		if !ok {
			targets = append(targets, planTarget{repoID: repoID, skipReason: live.ErrorGitHubNotWired})
			continue
		}
		targets = append(targets, planTarget{repoID: repoID, installationID: installationID, fullName: fullName})
	}
	return targets, nil
}
