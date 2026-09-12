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

// setCredential stores a bare key with no explicit model or preferred flag.
// It is still the organisation's preferred credential once this returns:
// secrets.handlePut marks an organisation's first-ever credential preferred
// implicitly, exactly like an owner who never touched the "preferred"
// checkbox because there was nothing yet to prefer over.
func setCredential(t *testing.T, owner *pivottest.Client, org string) {
	t.Helper()
	if status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-0123456789abcdef"}}); status != http.StatusOK {
		t.Fatalf("PUT credential: %d %v", status, body)
	}
}

// setPreferredCredentialWithModel is setCredential's sibling for tests that
// need to see a specific model travel from the credential onto a run.
func setPreferredCredentialWithModel(t *testing.T, owner *pivottest.Client, org, model string) {
	t.Helper()
	if status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-0123456789abcdef", "model": model, "preferred": true}}); status != http.StatusOK {
		t.Fatalf("PUT credential: %d %v", status, body)
	}
}

// A run spends the organisation's money the moment it starts, so it must not
// be startable without a key to spend from — the very first thing ADR-0046 §5
// names as non-optional. No run row survives the refusal: the credential
// check happens before any transaction opens (§4.9).
func TestStartRequiresACredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "start-1"})
	if status != http.StatusConflict || body["error"] != "model_credential_missing" {
		t.Fatalf("start without a credential answered %d %v", status, body)
	}
	var runs int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.live_runs WHERE org_id=$1::uuid`, org).Scan(&runs); e != nil {
		t.Fatal(e)
	}
	if runs != 0 {
		t.Fatalf("a refused start wrote %d run rows, want 0", runs)
	}

	setCredential(t, owner, org)
	// The failed attempt released its idempotency key (mgmt's replayable
	// releases on error), so reusing it is itself part of what this test
	// checks: a retried start is not stuck behind its own first failure.
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "start-1"})
	if status != http.StatusAccepted {
		t.Fatalf("start with a credential answered %d %v", status, body)
	}
	if body["state"] != "queued" || body["run_id"] == nil || body["run_id"] == "" {
		t.Fatalf("started run: %v", body)
	}
	if body["provider"] != secrets.ProviderOpenRouter {
		t.Fatalf("default provider: %v", body["provider"])
	}
	if _, has := body["prompt"]; has {
		t.Fatalf("run still carries a prompt field: %v", body)
	}
	counts, _ := body["counts"].(map[string]any)
	if counts["targets"] != float64(0) {
		t.Fatalf("a freshly planned run already has targets: %v", counts)
	}
	summary, _ := body["summary"].(map[string]any)
	if summary["skills_indexed"] != float64(0) || summary["proposals_created"] != float64(0) {
		t.Fatalf("an unstarted run's summary should read as real zeros: %v", summary)
	}
	cost, _ := body["cost"].(map[string]any)
	if cost["usd_estimated"] != false {
		t.Fatalf("an unstarted run's cost should not read as estimated: %v", cost)
	}
}

// The request has no fields (§4.9): an absent body, and an explicitly empty
// one, both start a run.
func TestStartWithNoOrEmptyBodySucceeds(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "no-body"})
	if status != http.StatusAccepted {
		t.Fatalf("start with no body answered %d %v", status, body)
	}

	status, cancelled, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(org) + "/" + body["run_id"].(string) + "/cancel"})
	if status != http.StatusOK {
		t.Fatalf("cancel to free the org up for the next start: %d %v", status, cancelled)
	}

	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{}, Key: "empty-body"})
	if status != http.StatusAccepted {
		t.Fatalf("start with an empty object body answered %d %v", status, body)
	}
}

// A field that does not exist cannot be filled in wrong either — but a body
// naming one anyway is refused the same way every other route refuses an
// unknown field, not silently ignored.
func TestStartWithUnknownFieldIsRejected(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Body: map[string]any{"prompt": "scan every repository for skills with no owner"}, Key: "unknown-field"})
	if status != http.StatusBadRequest || body["error"] != "invalid_json" {
		t.Fatalf("start with an unknown field answered %d %v, want 400 invalid_json", status, body)
	}
}

// The provider and model a run uses are the organisation's preferred
// credential's, copied onto the run row at start (§4.8, §4.9) — never a
// caller's choice, since the request has no such field.
func TestStartCopiesThePreferredCredentialsProviderAndModel(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setPreferredCredentialWithModel(t, owner, org, "openrouter/big-model")

	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "provider-model"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	if run["provider"] != secrets.ProviderOpenRouter || run["model"] != "openrouter/big-model" {
		t.Fatalf("run provider/model = %v/%v, want %s/openrouter/big-model",
			run["provider"], run["model"], secrets.ProviderOpenRouter)
	}
}

// A run's provider and model are a snapshot of the credential at the moment
// it started: a later settings change must not rewrite the history of what
// produced that run's result (§4.9).
func TestLaterCredentialChangeDoesNotRewriteAStartedRunsHistory(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setPreferredCredentialWithModel(t, owner, org, "openrouter/model-a")

	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "history-start"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)
	if run["model"] != "openrouter/model-a" {
		t.Fatalf("run model = %v, want openrouter/model-a", run["model"])
	}

	setPreferredCredentialWithModel(t, owner, org, "openrouter/model-b")

	status, detail, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: runsPath(org) + "/" + runID})
	if status != http.StatusOK {
		t.Fatalf("get: %d %v", status, detail)
	}
	got, _ := detail["run"].(map[string]any)
	if got["model"] != "openrouter/model-a" {
		t.Fatalf("a later credential change rewrote the run's model: %v, want openrouter/model-a", got["model"])
	}
}

// One run at a time per organisation (ADR-0046 §6): a second start names the
// run that is already active rather than just refusing.
func TestSecondStartIsConflictWithRunID(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)

	status, first, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "first"})
	if status != http.StatusAccepted {
		t.Fatalf("first start: %d %v", status, first)
	}
	runID, _ := first["run_id"].(string)

	status, second, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "second"})
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
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "owner-start"})
	if status != http.StatusAccepted {
		t.Fatalf("owner start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	member := h.SignIn(t, "member", "member@example.test")
	addMember(t, h, org, member)

	if status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org),
		Key: "member-start"}); status != http.StatusForbidden || body["error"] != "forbidden" {
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
// with, `done` must stay false the entire time the run has not reached a
// terminal state, and every event must carry payload.text — the console
// prints it as-is rather than translating a type code on its own side, so a
// second reader of the same run sees exactly what the first one saw live.
func TestEventCursorReturnsEachEventOnceWithTextWhileRunning(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "cursor-start"})
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
		if _, e := live.Append(ctx, tx, org, runID, "meridian/atlas", live.EventRepoFetched,
			"Repozytorium meridian/atlas: pobrano pliki.", map[string]any{"files": i + 1}); e != nil {
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
			payload, _ := ev["payload"].(map[string]any)
			text, _ := payload["text"].(string)
			if text == "" {
				t.Fatalf("event seq %v has no payload.text: %v", seq, ev)
			}
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
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "cancel-start"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	status, cancelled, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(org) + "/" + runID + "/cancel"})
	if status != http.StatusOK || cancelled["state"] != "cancelled" || cancelled["error"] != live.ErrorCancelled {
		t.Fatalf("cancel: %d %v", status, cancelled)
	}

	// run.finished is the other event this package appends itself (besides
	// run.started); it must carry payload.text like every event, and §5.5a
	// names its payload shape explicitly: {counts, summary}.
	status, events, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: runsPath(org) + "/" + runID + "/events"})
	if status != http.StatusOK {
		t.Fatalf("events after cancel: %d %v", status, events)
	}
	items, _ := events["items"].([]any)
	if len(items) == 0 {
		t.Fatalf("no events after cancel: %v", events)
	}
	last, _ := items[len(items)-1].(map[string]any)
	if last["type"] != live.EventRunFinished {
		t.Fatalf("last event = %v, want type run.finished", last)
	}
	payload, _ := last["payload"].(map[string]any)
	if text, _ := payload["text"].(string); text == "" {
		t.Fatalf("run.finished has no payload.text: %v", payload)
	}
	if _, ok := payload["counts"].(map[string]any); !ok {
		t.Fatalf("run.finished payload has no counts object: %v", payload)
	}
	if _, ok := payload["summary"].(map[string]any); !ok {
		t.Fatalf("run.finished payload has no summary object: %v", payload)
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

// summary, phase, skills and proposals are read straight from the columns
// the worker writes; they round-trip through both the run's own response and
// the per-target list, and findings is gone from the wire shape even though
// the column stays in the schema, unused (§5.5a, 1.6.0).
func TestSummaryPhaseSkillsAndProposalsRoundTripThroughHTTP(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	setCredential(t, owner, org)
	status, run, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(org), Key: "summary-start"})
	if status != http.StatusAccepted {
		t.Fatalf("start: %d %v", status, run)
	}
	runID, _ := run["run_id"].(string)

	// Poke the rows the way live.plan/live.repo would (agentrun's own rewrite
	// for this contract is a different task's work): one target mid-propose,
	// and a run summary as if a repository had already left something behind.
	ctx := context.Background()
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.live_run_targets(org_id,run_id,repo_id,state,phase,skills,proposals)
 VALUES($1::uuid,$2::uuid,'meridian/atlas','running','propose',3,1)`, org, runID); e != nil {
		t.Fatal(e)
	}
	if _, e := h.Pool.Exec(ctx, `UPDATE gfm.live_runs SET summary=$3::jsonb WHERE org_id=$1::uuid AND run_id=$2::uuid`,
		org, runID, `{"skills_indexed":3,"proposals_created":1}`); e != nil {
		t.Fatal(e)
	}

	status, detail, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: runsPath(org) + "/" + runID})
	if status != http.StatusOK {
		t.Fatalf("get: %d %v", status, detail)
	}
	gotRun, _ := detail["run"].(map[string]any)
	summary, _ := gotRun["summary"].(map[string]any)
	if summary["skills_indexed"] != float64(3) || summary["proposals_created"] != float64(1) {
		t.Fatalf("summary = %v, want skills_indexed=3 proposals_created=1", summary)
	}
	targets, _ := detail["targets"].([]any)
	if len(targets) != 1 {
		t.Fatalf("targets = %v, want exactly 1", targets)
	}
	target, _ := targets[0].(map[string]any)
	if target["phase"] != "propose" || target["skills"] != float64(3) || target["proposals"] != float64(1) {
		t.Fatalf("target = %v, want phase=propose skills=3 proposals=1", target)
	}
	if _, has := target["findings"]; has {
		t.Fatalf("target still carries a findings field: %v", target)
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

	status, run, _ := first.Call(t, pivottest.Call{Method: http.MethodPost, Path: runsPath(orgA), Key: "org-a-start"})
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
