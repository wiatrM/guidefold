package live

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// SetTargetState updates one target's state and error, stamping started_at
// the first time it crosses into running and finished_at the first time it
// reaches a finished state. It is the worker's path through one repository's
// row (queued -> running -> done|failed|skipped). The API's own cancel path
// does not call this: it acts on every unfinished target of a run at once,
// which is a single statement rather than one call per repository.
func SetTargetState(ctx context.Context, tx jobs.Tx, orgID, runID, repoID, state, errText string) error {
	finished := state == TargetDone || state == TargetFailed || state == TargetSkipped
	_, e := tx.Exec(ctx, `UPDATE gfm.live_run_targets SET state=$4, error=$5,
 started_at=CASE WHEN $4=$6 AND started_at IS NULL THEN now() ELSE started_at END,
 finished_at=CASE WHEN $7 THEN now() ELSE finished_at END
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`,
		orgID, runID, repoID, state, nullable(errText), TargetRunning, finished)
	return e
}

// terminalState computes a run's terminal state from its targets. The
// precedence is cancelled > failed > partial > succeeded: a cancelled run has
// to read as cancelled even though cancelling leaves skipped targets behind
// it, and a run whose own attempt failed before any target could be judged
// must not read as the vacuous "every target is done" that zero targets would
// otherwise produce. partial is a terminal state and is never success — a run
// with even one failed or skipped target answers partial (ADR-0046 §3, §7;
// API-CONTRACT §5.5a).
func terminalState(cancelled, runFailed bool, targets, done, failed, skipped int) string {
	switch {
	case cancelled:
		return StateCancelled
	case runFailed:
		return StateFailed
	case failed > 0 || skipped > 0:
		return StatePartial
	case targets > 0 && done == targets:
		return StateSucceeded
	default:
		// No target ever ran — every connected repository could have lacked a
		// GitHub App installation, say — and the run itself did not fail.
		// There is nothing here to call a success.
		return StatePartial
	}
}

// Finish ends a run: it reads the current target counts, computes the
// terminal state with terminalState, writes it to the run row along with the
// caller's cost and error, and appends run.finished. It is the one place that
// decision is made, so the API's cancel path and the worker's end-of-run path
// can never disagree about what a run's final state means. cost may be nil to
// leave the run's existing cost column untouched, which is what a
// cancellation does — cancelling spends nothing new.
func Finish(ctx context.Context, tx jobs.Tx, orgID, runID string, cancelled, runFailed bool,
	errCode string, cost json.RawMessage) (string, error) {
	var targets, done, failed, skipped int
	if e := tx.QueryRow(ctx, `SELECT count(*), count(*) FILTER (WHERE state=$3),
 count(*) FILTER (WHERE state=$4), count(*) FILTER (WHERE state=$5)
 FROM gfm.live_run_targets WHERE org_id=$1::uuid AND run_id=$2::uuid`,
		orgID, runID, TargetDone, TargetFailed, TargetSkipped).
		Scan(&targets, &done, &failed, &skipped); e != nil {
		return "", e
	}
	state := terminalState(cancelled, runFailed, targets, done, failed, skipped)
	var costArg any
	if len(cost) > 0 {
		costArg = string(cost)
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.live_runs SET state=$3, error=$4,
 cost=COALESCE($5::jsonb,cost), finished_at=now()
 WHERE org_id=$1::uuid AND run_id=$2::uuid`,
		orgID, runID, state, nullable(errCode), costArg); e != nil {
		return "", e
	}
	payload := map[string]any{"state": state}
	if errCode != "" {
		payload["error"] = errCode
	}
	if _, e := Append(ctx, tx, orgID, runID, "", EventRunFinished, payload); e != nil {
		return "", e
	}
	return state, nil
}

// handleCancel stops a run that has not already finished. Every target still
// queued or running is reported skipped with ErrorCancelled rather than
// dropped silently — a cancelled sweep that quietly forgot three repositories
// would be worse than one that says so — and any job this run still owns is
// cancelled the same way importer.handleCancel cancels an import's jobs,
// fenced by generation so a worker mid-lease is stopped at its next write
// rather than finishing into a run that is already cancelled (ADR-0046 §7).
func (s *Service) handleCancel(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	runID := c.Param("run_id")
	if !looksLikeUUID(runID) {
		return mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	tx, e := c.Tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()

	var state string
	e = tx.QueryRow(c.Ctx(), `SELECT state FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid FOR UPDATE`, org.ID, runID).Scan(&state)
	if isNoRows(e) {
		return mgmt.NotFound("live_run_not_found", "No such Live Agent run in this organization.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	if isTerminal(state) {
		// Including a run this same call already cancelled: cancel is
		// idempotent in its effect on the row (it stays cancelled), not in
		// its response — a second call answers the conflict rather than a
		// silent 200, so a caller cannot mistake it for having just stopped
		// something.
		return mgmt.Conflict("live_run_not_cancellable", "This run already finished.")
	}

	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.live_run_targets SET state=$3, error=$4, finished_at=now()
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND state IN ($5,$6)`,
		org.ID, runID, TargetSkipped, ErrorCancelled, TargetQueued, TargetRunning); e != nil {
		return mgmt.Internal(e)
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.jobs SET state='cancelled', worker_id=NULL, lease_until=NULL,
 finished_at=now(), generation=generation+1
 WHERE org_id=$1::uuid AND kind IN ($3,$4) AND payload->>'run_id'=$2 AND state IN ('queued','leased')`,
		org.ID, runID, KindPlan, KindRepo); e != nil {
		return mgmt.Internal(e)
	}
	if _, e := Finish(c.Ctx(), tx, org.ID, runID, true, false, ErrorCancelled, nil); e != nil {
		return mgmt.Internal(e)
	}
	if e := c.Audit(c.Ctx(), tx, org.ID, "live.cancel", "live_run:"+runID, ""); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}

	run, e := s.loadRunByID(c.Ctx(), org.ID, runID)
	if e != nil {
		return e
	}
	return c.JSON(http.StatusOK, run)
}
