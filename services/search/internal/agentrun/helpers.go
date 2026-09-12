package agentrun

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

func mustJSON(v any) json.RawMessage {
	b, e := json.Marshal(v)
	if e != nil {
		// Every value this package marshals is its own struct literal, never
		// something that can fail to encode; a panic here means a
		// programming mistake, not bad input.
		panic(e)
	}
	return b
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// plural is the regular English count noun live.repo's own event sentences
// need (files, skills, proposals — every noun this package counts happens to
// take a plain -s): 1 file, 0 or 2+ files. Never used for a noun with an
// irregular plural; there is none among live.repo's own event text today.
func plural(n int, noun string) string {
	if n == 1 {
		return noun
	}
	return noun + "s"
}

// fenceJob refuses to write when the job's lease has moved on, the same
// check internal/review/generate.go's own fence() makes before a group's
// candidates are stored. A worker that lost its lease mid-transaction must
// write nothing, not half of a repository's findings.
func fenceJob(ctx context.Context, tx pgx.Tx, t *worker.Task) error {
	var ok bool
	e := tx.QueryRow(ctx, `SELECT true FROM gfm.jobs
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased' FOR UPDATE`,
		t.Job.JobID, t.Job.Generation).Scan(&ok)
	if errors.Is(e, pgx.ErrNoRows) {
		return jobs.ErrFenced
	}
	if e != nil {
		return fmt.Errorf("check job fence: %w", e)
	}
	return nil
}

// isRunTerminal mirrors live's own terminal check using only the four
// exported state constants that answer say a run will never move again —
// live.go keeps the actual switch unexported, so this package names the
// same four values rather than reaching for something live does not
// export.
func isRunTerminal(state string) bool {
	switch state {
	case live.StateSucceeded, live.StatePartial, live.StateFailed, live.StateCancelled:
		return true
	}
	return false
}

// maybeFinishRun ends the run when every target has reached a terminal
// state, whichever live.repo job happens to be the last one to check. It
// takes the run row's own lock before counting, so two targets finishing
// within the same instant cannot both conclude "I am last" and both call
// live.Finish — the second sees the state Finish's own writes to.
//
// The run's error code is read back from the target rows rather than
// carried in from the caller: several live.repo jobs may race to be the one
// that finds the run empty, and only the target rows — not any one caller's
// local knowledge of why it stopped — agree on why the run, as a whole,
// ended short of every repository.
func maybeFinishRun(ctx context.Context, tx pgx.Tx, orgID, runID string) error {
	var state string
	if e := tx.QueryRow(ctx, `SELECT state FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid FOR UPDATE`, orgID, runID).Scan(&state); e != nil {
		return e
	}
	if isRunTerminal(state) {
		return nil
	}
	var remaining int
	if e := tx.QueryRow(ctx, `SELECT count(*) FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND state IN ($3,$4)`,
		orgID, runID, live.TargetQueued, live.TargetRunning).Scan(&remaining); e != nil {
		return e
	}
	if remaining > 0 {
		return nil
	}
	var budgetHit bool
	if e := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND error=$3)`,
		orgID, runID, live.ErrorBudgetExhausted).Scan(&budgetHit); e != nil {
		return e
	}
	errCode := ""
	if budgetHit {
		errCode = live.ErrorBudgetExhausted
	}
	_, e := live.Finish(ctx, tx, orgID, runID, false, false, errCode, nil)
	return e
}
