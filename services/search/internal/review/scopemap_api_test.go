package review_test

import (
	"context"
	"net/http"
	"path/filepath"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// codeowners is the file the organisation's owners actually come from: it is
// the only place a real team name is attached to a real path (CONVENTIONS
// line 34), and an owner it does not name is refused.
const codeowners = "* @acme/platform\n/platforms/atlas/ @acme/atlas\n"

// scopeMapEnv is one organisation with two imported repositories, which is the
// smallest thing a map of an *organisation* can be about.
type scopeMapEnv struct {
	h       *pivottest.Harness
	owner   *pivottest.Client
	orgID   string
	orgBase string
	repos   []string
}

func setupScopeMap(t *testing.T) *scopeMapEnv {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	orgID := owner.CreateOrg(t, "acme")
	repos := []string{"meridian", "meridian-two"}
	for i, repo := range repos {
		owner.CreateRepo(t, orgID, repo, "https://git.example.test/acme/"+repo)
		tree := pivottest.Monorepo(t)
		write(t, filepath.Join(tree, "CODEOWNERS"), codeowners)
		manifest := pivottest.Manifest(t, tree, "acme", repo, true)
		pivottest.Push(t, owner, orgID, repo, tree, manifest, "import-"+string(rune('1'+i)))
	}
	if n := h.RunParse(t, pivottest.Scratch(t, "parse")); n == 0 {
		t.Fatal("the parse worker ran nothing")
	}
	return &scopeMapEnv{h: h, owner: owner, orgID: orgID,
		orgBase: "/api/v1/orgs/" + orgID, repos: repos}
}

// oneScopeMapProposal runs the propose job and returns the single proposal it
// produced.
func (e *scopeMapEnv) oneScopeMapProposal(t *testing.T) string {
	t.Helper()
	if n := e.h.RunScopeMap(t); n == 0 {
		t.Fatal("no scope_map.propose job was queued by the import")
	}
	// A job that failed says why. Reporting its error here rather than the empty
	// list two lines below is the difference between "the map was rejected
	// because X" and "there is no proposal".
	var state, jobErr string
	if err := e.h.Pool.QueryRow(context.Background(), `SELECT state,COALESCE(error,'')
 FROM gfm.jobs WHERE kind=$1 ORDER BY created_at DESC LIMIT 1`,
		review.KindScopeMapPropose).Scan(&state, &jobErr); err != nil {
		t.Fatal(err)
	}
	if state != "done" {
		t.Fatalf("scope_map.propose ended %s: %s", state, jobErr)
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.orgBase + "/proposals?kind=scope_map"})
	if status != http.StatusOK {
		t.Fatalf("list proposals: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("expected exactly one scope_map proposal, got %d: %v", len(items), body)
	}
	row := items[0].(map[string]any)
	if row["state"] != "draft" {
		t.Fatalf("a fresh proposal must be a draft, got %v", row["state"])
	}
	return row["proposal_id"].(string)
}

// The whole path runs with no provider: the deterministic generator proposes
// the inferred map, so propose, read, diff and approve are provable without a
// model (ADR-0051 decision 7).
func TestScopeMapProposalIsDraftUntilApproved(t *testing.T) {
	e := setupScopeMap(t)
	id := e.oneScopeMapProposal(t)

	// Nothing has been written: a proposal is not policy.
	if n := countScopes(t, e, "llm_approved"); n != 0 {
		t.Fatalf("a draft proposal wrote %d scope rows", n)
	}

	status, detail, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.orgBase + "/proposals/" + id})
	if status != http.StatusOK {
		t.Fatalf("read proposal: %d %v", status, detail)
	}
	m, ok := detail["scope_map"].(map[string]any)
	if !ok {
		t.Fatalf("a scope_map proposal must carry scope_map: %v", detail)
	}
	if m["origin"] != "inferred" {
		t.Fatalf("the deterministic generator proposes the inferred map, got %v", m["origin"])
	}
	if nodes, _ := m["nodes"].([]any); len(nodes) == 0 {
		t.Fatal("the proposed map has no nodes")
	}
	if findings, _ := m["findings"].([]any); len(findings) != 0 {
		t.Fatalf("a stored proposal validated when it was written: %v", findings)
	}
	if _, ok := m["diff"].(map[string]any); !ok {
		t.Fatalf("the proposal must carry a diff against the scopes that exist now: %v", m)
	}
	// The map is about the organisation, not one repository.
	repos, _ := m["repos"].([]any)
	if len(repos) != len(e.repos) {
		t.Fatalf("expected the map to cover %d repositories, got %v", len(e.repos), repos)
	}
}

// Approving is applying: the rows appear, they say who approved them, and the
// proposal reaches `applied` rather than `published`.
func TestScopeMapApprovalWritesScopesWithTheReviewer(t *testing.T) {
	e := setupScopeMap(t)
	id := e.oneScopeMapProposal(t)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.orgBase + "/proposals/" + id + "/decision", Key: "decide-1",
		Body: map[string]any{"decision": "approve", "reason": "the hierarchy matches our teams"}})
	if status != http.StatusOK {
		t.Fatalf("approve: %d %v", status, body)
	}
	if body["state"] != review.StateApplied {
		t.Fatalf("an approved map is applied, got %v", body["state"])
	}
	if n := countScopes(t, e, importer.SourceLLMApproved); n == 0 {
		t.Fatal("approval wrote no llm_approved scope rows")
	}
	var reviewed int
	if err := e.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.scopes
 WHERE org_id=$1::uuid AND source=$2 AND reviewed_by IS NOT NULL AND proposal_id=$3::uuid`,
		e.orgID, importer.SourceLLMApproved, id).Scan(&reviewed); err != nil {
		t.Fatal(err)
	}
	if reviewed == 0 {
		t.Fatal("an approved row must name its reviewer and its proposal")
	}

	// The decision is once. A second one is a state conflict, not a second
	// application.
	status, body, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.orgBase + "/proposals/" + id + "/decision", Key: "decide-2",
		Body: map[string]any{"decision": "reject", "reason": "changed my mind too late"}})
	if status != http.StatusConflict || body["error"] != "proposal_state_invalid" {
		t.Fatalf("expected 409 proposal_state_invalid, got %d %v", status, body)
	}
}

// A scope map has no file, so the two decisions that assume one are refused by
// name rather than half-performed.
func TestScopeMapRefusesEditAndExport(t *testing.T) {
	e := setupScopeMap(t)
	id := e.oneScopeMapProposal(t)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.orgBase + "/proposals/" + id + "/decision", Key: "edit-1",
		Body: map[string]any{"decision": "edit", "reason": "let me fix the hierarchy",
			"candidate_body": `{"nodes":[]}`}})
	if status != http.StatusUnprocessableEntity || body["error"] != "invalid_candidate_change" {
		t.Fatalf("expected 422 invalid_candidate_change, got %d %v", status, body)
	}

	repoBase := pivottest.RepoBase(e.orgID, e.repos[0])
	status, body, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: repoBase + "/proposals/" + id + "/export", Key: "export-1", Body: map[string]any{}})
	if status != http.StatusConflict || body["error"] != "proposal_state_invalid" {
		t.Fatalf("expected 409 proposal_state_invalid on export, got %d %v", status, body)
	}
}

// The repository twin must not be a way around the organisation-owner check: the
// row is anchored to one repository, but the rows it writes reach the others, so
// a reviewer of the anchor repository would otherwise move every repository's
// scopes.
func TestScopeMapCannotBeDecidedOnTheRepositoryRoute(t *testing.T) {
	e := setupScopeMap(t)
	id := e.oneScopeMapProposal(t)
	repoBase := pivottest.RepoBase(e.orgID, e.repos[0])
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: repoBase + "/proposals/" + id + "/decision", Key: "repo-decide-1",
		Body: map[string]any{"decision": "approve", "reason": "through the wrong door"}})
	if status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("expected 403 forbidden on the repository route, got %d %v", status, body)
	}
	if n := countScopes(t, e, importer.SourceLLMApproved); n != 0 {
		t.Fatal("a refused decision wrote scope rows")
	}
}

// Another organisation's member gets the same answer for a proposal that exists
// and one that does not: the organisation view is never an existence oracle.
func TestScopeMapDecisionIsTenantIsolated(t *testing.T) {
	e := setupScopeMap(t)
	id := e.oneScopeMapProposal(t)

	intruder := e.h.SignIn(t, "intruder", "intruder@example.test")
	_ = intruder.CreateOrg(t, "other")
	status, body, _ := intruder.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.orgBase + "/proposals/" + id + "/decision", Key: "intrude-1",
		Body: map[string]any{"decision": "approve", "reason": "not my organisation"}})
	if status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("expected 403 forbidden, got %d %v", status, body)
	}
	if n := countScopes(t, e, importer.SourceLLMApproved); n != 0 {
		t.Fatal("a forbidden decision wrote scope rows")
	}
}

// With no generator configured every queued job ends `skipped` with a named
// reason, and the import stays exactly as useful as it was (#146, #167).
func TestScopeMapSkipsWhenNoGeneratorIsConfigured(t *testing.T) {
	e := setupScopeMap(t)
	// The jobs were queued under the deterministic generator; the worker that
	// picks them up is built with none, which is the deployment shape a
	// repository imports under when nobody has configured a model.
	t.Setenv("GUIDEFOLD_GENERATOR", "none")
	w, err := review.NewScopeMapWorker(e.h.Pool, e.h.Blobs, e.h.Keyring)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < len(e.repos)+1; i++ {
		if err := worker.Run(context.Background(), e.h.Pool, "test-worker", w.Handlers(),
			worker.Options{Once: true, Lease: time.Minute}); err != nil {
			t.Fatal(err)
		}
	}
	rows, err := e.h.Pool.Query(context.Background(), `SELECT state,COALESCE(error,'')
 FROM gfm.jobs WHERE kind=$1`, review.KindScopeMapPropose)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	seen := 0
	for rows.Next() {
		var state, reason string
		if err := rows.Scan(&state, &reason); err != nil {
			t.Fatal(err)
		}
		if state != "skipped" || reason != "llm_not_configured" {
			t.Fatalf("expected skipped/llm_not_configured, got %s/%s", state, reason)
		}
		seen++
	}
	if seen == 0 {
		t.Fatal("no scope_map.propose job was queued at all")
	}
	var proposals int
	if err := e.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.proposals
 WHERE org_id=$1::uuid AND kind='scope_map'`, e.orgID).Scan(&proposals); err != nil {
		t.Fatal(err)
	}
	if proposals != 0 {
		t.Fatalf("a skipped job produced %d proposals", proposals)
	}
}

func countScopes(t *testing.T, e *scopeMapEnv, source string) int {
	t.Helper()
	var n int
	if err := e.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.scopes
 WHERE org_id=$1::uuid AND source=$2`, e.orgID, source).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}
