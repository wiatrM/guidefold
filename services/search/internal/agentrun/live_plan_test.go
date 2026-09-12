package agentrun_test

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

func runsPath(org string) string { return "/api/v1/orgs/" + org + "/live/runs" }

// startRun creates a run through the real API (the credential check, the
// one-active-run index and the opening event all live there) and returns
// its run_id. The start request has no fields (API-CONTRACT §4.9, 1.6.0):
// no prompt, no repository picker — a run always covers every connected
// repository — so the body key only needs to make each call's idempotency
// key distinct between tests.
func startRun(t *testing.T, owner *pivottest.Client, org, key string) string {
	t.Helper()
	status, resp, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Key: "start-" + key})
	if status != http.StatusAccepted {
		t.Fatalf("start run: %d %v", status, resp)
	}
	runID, _ := resp["run_id"].(string)
	if runID == "" {
		t.Fatalf("start run answered no run_id: %v", resp)
	}
	return runID
}

// drainOnce leases and runs every currently-queued job of one kind, once
// each, the same "at most twenty passes" shape pivottest.Harness.drain uses
// for the pipelines it already knows about — agentrun's own worker structs
// are not part of that harness, so this package drives worker.Run directly.
func drainOnce(t *testing.T, h *pivottest.Harness, kind string, handlers map[string]worker.Handler) int {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	ran := 0
	for i := 0; i < 20; i++ {
		var n int
		if e := h.Pool.QueryRow(ctx, `SELECT count(*) FROM gfm.jobs WHERE kind=$1 AND state='queued'`, kind).
			Scan(&n); e != nil {
			t.Fatal(e)
		}
		if n == 0 {
			break
		}
		if e := worker.Run(ctx, h.Pool, "test-worker", handlers,
			worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
			t.Fatal(e)
		}
		ran++
	}
	return ran
}

func targetRow(t *testing.T, h *pivottest.Harness, orgID, runID, repoID string) (state, errText string) {
	t.Helper()
	var errPtr *string
	if e := h.Pool.QueryRow(context.Background(), `SELECT state, error FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, orgID, runID, repoID).
		Scan(&state, &errPtr); e != nil {
		t.Fatalf("read target row for %s: %v", repoID, e)
	}
	if errPtr != nil {
		errText = *errPtr
	}
	return state, errText
}

func runRowState(t *testing.T, h *pivottest.Harness, orgID, runID string) (state string, errText *string) {
	t.Helper()
	if e := h.Pool.QueryRow(context.Background(), `SELECT state, error FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID).Scan(&state, &errText); e != nil {
		t.Fatalf("read run row: %v", e)
	}
	return state, errText
}

// A repository the organisation registered but never connected to the
// GitHub App must appear in the run's own targets as skipped, never simply
// missing — API-CONTRACT §4.9's "a sweep that silently covered part of the
// organisation would be worse than one that names what it could not reach".
func TestRepoWithoutInstallationIsSkippedNotOmitted(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "connected", "https://github.com/acme/connected")
	owner.CreateRepo(t, org, "not-connected", "https://github.com/acme/not-connected")
	registerInstallation(t, h, org, 1, "acme/connected")
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")

	runID := startRun(t, owner, org, "scan-everything")
	drainOnce(t, h, live.KindPlan, agentrun.NewLivePlanWorker(h.Pool).Handlers())

	if state, errText := targetRow(t, h, org, runID, "not-connected"); state != live.TargetSkipped || errText != live.ErrorGitHubNotWired {
		t.Fatalf("not-connected target = %s/%s, want skipped/%s", state, errText, live.ErrorGitHubNotWired)
	}
	if state, _ := targetRow(t, h, org, runID, "connected"); state != live.TargetQueued {
		t.Fatalf("connected target state = %s, want queued", state)
	}

	// Both repositories still show up — neither is dropped from the list.
	var count int
	if e := h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, org, runID).Scan(&count); e != nil {
		t.Fatal(e)
	}
	if count != 2 {
		t.Fatalf("targets = %d, want 2 (one per registered repository)", count)
	}

	var repoJobs int
	if e := h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind=$2`, org, live.KindRepo).Scan(&repoJobs); e != nil {
		t.Fatal(e)
	}
	if repoJobs != 1 {
		t.Fatalf("live.repo jobs enqueued = %d, want exactly 1 (the connected repository only)", repoJobs)
	}
}

// A run whose organisation has zero connected repositories still has to end
// somewhere: it must not read as a success it never earned.
func TestZeroTargetsFinishesPartial(t *testing.T) {
	h, owner, org := newHarness(t)
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")

	runID := startRun(t, owner, org, "scan-everything")
	drainOnce(t, h, live.KindPlan, agentrun.NewLivePlanWorker(h.Pool).Handlers())

	state, _ := runRowState(t, h, org, runID)
	if state != live.StatePartial {
		t.Fatalf("run state = %s, want partial", state)
	}
}

// Found by driving the console in a browser: a run whose every repository was
// skipped had no live.repo job coming to end it, so it said "running" for ever
// while its answer was already complete. The worst state to be wrong about is
// the one that makes an owner wait.
func TestRunWhoseEveryRepositoryIsSkippedStillFinishes(t *testing.T) {
	h, owner, org := newHarness(t)
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")
	owner.CreateRepo(t, org, "not-connected", "https://example.test/acme/not-connected")

	runID := startRun(t, owner, org, "scan-everything")
	drainOnce(t, h, live.KindPlan, agentrun.NewLivePlanWorker(h.Pool).Handlers())

	if state, errText := targetRow(t, h, org, runID, "not-connected"); state != live.TargetSkipped || errText != live.ErrorGitHubNotWired {
		t.Fatalf("target = %s/%s, want skipped/%s", state, errText, live.ErrorGitHubNotWired)
	}
	state, _ := runRowState(t, h, org, runID)
	if state != live.StatePartial {
		t.Fatalf("run state = %s, want partial: nothing else will ever finish it", state)
	}
}
