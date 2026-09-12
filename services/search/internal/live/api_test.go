package live_test

import (
	"context"
	"net/http"
	"testing"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

func runsPath(org string) string { return "/api/v1/orgs/" + org + "/live/runs" }

func credentialPath(org string) string {
	return "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderOpenRouter
}

// addMember mirrors secrets_test's own shortcut: the harness has no route for
// it, so the membership row is inserted directly, the way an accepted
// invitation would leave it.
func addMember(t *testing.T, h *pivottest.Harness, org string, member *pivottest.Client) {
	t.Helper()
	if _, e := h.Pool.Exec(context.Background(),
		`INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'member')`,
		org, member.User["id"]); e != nil {
		t.Fatal(e)
	}
}

func setCredential(t *testing.T, owner *pivottest.Client, org string) {
	t.Helper()
	if status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-0123456789abcdef"}}); status != http.StatusOK {
		t.Fatalf("PUT credential: %d %v", status, body)
	}
}

// A run spends the organisation's money the moment it starts, so it must not
// be startable without a key to spend from — the very first thing ADR-0046 §5
// names as non-optional.
func TestStartRequiresACredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "scan every repository for skills with no owner"}, Key: "start-1"})
	if status != http.StatusConflict || body["error"] != "model_credential_missing" {
		t.Fatalf("start without a credential answered %d %v", status, body)
	}

	setCredential(t, owner, org)
	// The failed attempt released its idempotency key (mgmt's replayable
	// releases on error), so reusing it is itself part of what this test
	// checks: a retried start is not stuck behind its own first failure.
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "scan every repository for skills with no owner"}, Key: "start-1"})
	if status != http.StatusAccepted {
		t.Fatalf("start with a credential answered %d %v", status, body)
	}
	if body["state"] != "queued" || body["run_id"] == nil || body["run_id"] == "" {
		t.Fatalf("started run: %v", body)
	}
	if body["provider"] != secrets.ProviderOpenRouter {
		t.Fatalf("default provider: %v", body["provider"])
	}
	counts, _ := body["counts"].(map[string]any)
	if counts["targets"] != float64(0) {
		t.Fatalf("a freshly planned run already has targets: %v", counts)
	}
	cost, _ := body["cost"].(map[string]any)
	if cost["usd_estimated"] != false {
		t.Fatalf("an unstarted run's cost should not read as estimated: %v", cost)
	}
}

// One run at a time per organisation (ADR-0046 §6): a second start names the
// run that is already active rather than just refusing.
func TestSecondStartIsConflictWithRunID(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)

	status, first, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "first sweep"}, Key: "first"})
	if status != http.StatusAccepted {
		t.Fatalf("first start: %d %v", status, first)
	}
	runID, _ := first["run_id"].(string)

	status, second, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "second sweep, should not start"}, Key: "second"})
	if status != http.StatusConflict || second["error"] != "live_run_already_active" {
		t.Fatalf("second start answered %d %v", status, second)
	}
	details, _ := second["details"].(map[string]any)
	if details["run_id"] != runID {
		t.Fatalf("details.run_id = %v, want %q", details["run_id"], runID)
	}
}

// Starting one spends money, so only an owner may; reading is every member's
// right, because a member has to be able to see whether a run is happening at
// all (ADR-0046 §1).
func TestMemberCanReadButNotStartOrCancel(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "member visibility check"}, Key: "owner-start"})
	if status != http.StatusAccepted {
		t.Fatalf("owner start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	member := h.SignIn(t, "member", "member@example.test")
	addMember(t, h, org, member)

	if status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "a member should not be able to spend the org's money"},
		Key:  "member-start"}); status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("member start answered %d %v", status, body)
	}
	if status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(org) + "/" + runID + "/cancel"}); status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("member cancel answered %d %v", status, body)
	}
	if status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: runsPath(org)}); status != http.StatusOK {
		t.Fatalf("member list answered %d %v", status, body)
	}
	status, detail, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: runsPath(org) + "/" + runID})
	if status != http.StatusOK {
		t.Fatalf("member get answered %d %v", status, detail)
	}
	got, _ := detail["run"].(map[string]any)
	if got["run_id"] != runID {
		t.Fatalf("member read a different run: %v", got)
	}
}

// The event cursor is the contract's only live channel (ADR-0046 §4): every
// event must come back exactly once across however many pages a client polls
// with, and `done` must stay false the entire time the run has not reached a
// terminal state — an empty page from a quiet agent is not completion.
func TestEventCursorReturnsEachEventOnceWhileRunning(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "narrate a few chunks"}, Key: "cursor-start"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	// Simulate the worker's own path: append five more events under a real
	// read-write transaction, the way live.repo would. The management pool
	// runs read-only by default, so this has to open its own transaction
	// exactly as the worker will.
	ctx := context.Background()
	tx, e := h.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	for i := 0; i < 5; i++ {
		if _, e := live.Append(ctx, tx, org, runID, "meridian/atlas", live.EventModelDelta,
			map[string]any{"text": "chunk"}); e != nil {
			t.Fatal(e)
		}
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	// run.started (seq 1) plus the five appended above.
	const wantEvents = 6

	seen := map[float64]bool{}
	after := 0
	for page := 0; page < wantEvents+2; page++ {
		status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
			Path: runsPath(org) + "/" + runID + "/events?after=" + itoa(after) + "&limit=2"})
		if status != http.StatusOK {
			t.Fatalf("events page: %d %v", status, body)
		}
		if body["done"] != false {
			t.Fatalf("done=%v on a run that is still queued", body["done"])
		}
		items, _ := body["items"].([]any)
		for _, raw := range items {
			ev, _ := raw.(map[string]any)
			seq, _ := ev["seq"].(float64)
			if seen[seq] {
				t.Fatalf("seq %v returned twice", seq)
			}
			seen[seq] = true
		}
		next, _ := body["next_after"].(float64)
		after = int(next)
		if len(items) == 0 {
			break
		}
	}
	if len(seen) != wantEvents {
		t.Fatalf("saw %d distinct events, want %d: %v", len(seen), wantEvents, seen)
	}
	for i := 1; i <= wantEvents; i++ {
		if !seen[float64(i)] {
			t.Fatalf("seq %d was never returned", i)
		}
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b []byte
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	if neg {
		b = append([]byte{'-'}, b...)
	}
	return string(b)
}

// Cancel is idempotent in its effect on the run — it stays cancelled — but
// not in its response: a second cancel of an already-terminal run has to say
// so rather than answer a silent second 200 (ADR-0046 §7).
func TestCancelIsIdempotentInEffectAndTerminalIsConflict(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "cancel me"}, Key: "cancel-start"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	status, cancelled, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(org) + "/" + runID + "/cancel"})
	if status != http.StatusOK || cancelled["state"] != "cancelled" || cancelled["error"] != live.ErrorCancelled {
		t.Fatalf("cancel: %d %v", status, cancelled)
	}

	status, again, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(org) + "/" + runID + "/cancel"})
	if status != http.StatusConflict || again["error"] != "live_run_not_cancellable" {
		t.Fatalf("second cancel: %d %v", status, again)
	}

	status, detail, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: runsPath(org) + "/" + runID})
	if status != http.StatusOK {
		t.Fatalf("get after second cancel: %d %v", status, detail)
	}
	got, _ := detail["run"].(map[string]any)
	if got["state"] != "cancelled" {
		t.Fatalf("state drifted after the refused second cancel: %v", got["state"])
	}
}

// Cross-organisation access is 403 through Authorize (the same organisation
// or a non-existent one are indistinguishable), and a run that is real but
// belongs to a different organisation is live_run_not_found once inside a
// caller's own organisation — never a leak of the other organisation's row.
func TestTwoOrganisationsNeverSeeEachOthersRuns(t *testing.T) {
	h := pivottest.New(t)
	first := h.SignIn(t, "first", "first@example.test")
	second := h.SignIn(t, "second", "second@example.test")
	orgA := first.CreateOrg(t, "org-a")
	orgB := second.CreateOrg(t, "org-b")
	setCredential(t, first, orgA)

	status, run, _ := first.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(orgA),
		Body: map[string]any{"prompt": "org A's own sweep"}, Key: "org-a-start"})
	if status != http.StatusAccepted {
		t.Fatalf("org A start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	if status, _, _ := second.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: runsPath(orgA)}); status != http.StatusForbidden {
		t.Fatalf("a non-member listing org A's runs answered %d, want 403", status)
	}
	status, body, _ := second.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: runsPath(orgB) + "/" + runID})
	if status != http.StatusNotFound || body["error"] != "live_run_not_found" {
		t.Fatalf("org A's run through org B's path answered %d %v, want 404 live_run_not_found", status, body)
	}
}
