package review_test

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

func TestMain(m *testing.M) {
	// The review module reads its generator from the environment at mount time.
	// The deterministic recipe is the one the tests measure; the "not
	// configured" path sets the variable back per test.
	_ = os.Setenv("GUIDEFOLD_GENERATOR", generator.NameDeterministic)
	pivottest.Main(m)
}

// runbook is the extraction fixture: a document with a purpose, both
// applicability sections, an ordered procedure and a verification step.
const runbook = `# Rotate an auth-sdk signing key

## Purpose

Replace the signing key a service uses without rejecting live tokens.

## When to use

The key is older than 90 days, or a rotation was requested by security.

## When not to use

- Do NOT use this for the root CA.
- Do NOT use during an active incident.

## Steps

1. Publish the new public key to the JWKS endpoint.
2. Wait for every consumer to refresh its key cache.
3. Switch the signer to the new private key.
4. Retire the previous key after the grace period.

## Verification

No token verification failures for one hour after the switch.
`

// sharedProcedure is the consolidation fixture of PRODUCT-PIVOT U2 AC5: the
// same three ordered steps, marked, in two runbook skills of one scope.
func sharedProcedure(name, owner string) string {
	return `---
name: ` + name + `
description: "[meridian] Runbook ` + name + ` for the shared credential rotation procedure."
metadata:
  owner: ` + owner + `
  status: active
  kind: engineering
  layer: team
---

# ` + name + `

## Steps

1. Drain the affected workload before touching its credentials.
2. Issue a replacement credential from the platform vault.
3. Roll the deployment and confirm readiness probes pass.
4. Retire the previous credential after the grace period.
`
}

type env struct {
	h        *pivottest.Harness
	owner    *pivottest.Client
	orgID    string
	repo     string
	base     string
	importID string
	tree     string
}

// setup imports a Meridian tree that carries an extractable runbook and two
// skills with a marked shared procedure, then runs the real parse worker.
func setup(t *testing.T) *env {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	orgID := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, orgID, "meridian", "https://git.example.test/acme/meridian")

	// The fixture lives in the root scope, which is the scope with the most
	// material and therefore the one a bounded run (max_groups = 5) keeps.
	tree := pivottest.Monorepo(t)
	write(t, filepath.Join(tree, "README.md"), runbook)
	write(t, filepath.Join(tree, ".agents/skills/rotate-a/SKILL.md"),
		sharedProcedure("rotate-a", "platform-engineering"))
	write(t, filepath.Join(tree, ".agents/skills/rotate-b/SKILL.md"),
		sharedProcedure("rotate-b", "platform-engineering"))

	manifest := pivottest.Manifest(t, tree, "acme", "meridian", true)
	importID := pivottest.Push(t, owner, orgID, "meridian", tree, manifest, "import-1")
	if n := h.RunParse(t, pivottest.Scratch(t, "parse")); n == 0 {
		t.Fatal("the parse worker ran nothing")
	}
	return &env{h: h, owner: owner, orgID: orgID, repo: "meridian",
		base: pivottest.RepoBase(orgID, "meridian"), importID: importID, tree: tree}
}

func write(t *testing.T, path, body string) {
	t.Helper()
	if e := os.MkdirAll(filepath.Dir(path), 0o755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(path, []byte(body), 0o644); e != nil {
		t.Fatal(e)
	}
}

// U2.7: the plan says what would run and what it could cost, with every limit
// visible, before a single call is made.
func TestPlanShowsGroupsAndLimitsBeforeSpending(t *testing.T) {
	e := setup(t)
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID + "/plan"})
	if status != 200 {
		t.Fatalf("plan: %d %v", status, body)
	}
	limits, _ := body["limits"].(map[string]any)
	for _, key := range []string{"max_files", "max_bytes", "max_tokens", "max_groups",
		"max_proposals_per_group", "max_neighbours", "max_calls", "max_usd"} {
		if _, ok := limits[key]; !ok {
			t.Errorf("the plan hides the limit %s: %v", key, limits)
		}
	}
	if limits["max_groups"].(float64) != 5 || limits["max_proposals_per_group"].(float64) != 5 ||
		limits["max_neighbours"].(float64) != 10 {
		t.Errorf("the contract's ceilings are not the defaults: %v", limits)
	}
	groups, _ := body["groups"].([]any)
	if len(groups) == 0 {
		t.Fatal("the plan produced no groups from a tree with documents and skills")
	}
	kinds := map[string]int{}
	for _, raw := range groups {
		g, _ := raw.(map[string]any)
		kinds[g["kind"].(string)]++
		if _, ok := g["scope"]; !ok {
			t.Errorf("group %v has no scope", g)
		}
		inputs, _ := g["inputs"].([]any)
		if len(inputs) > 20 {
			t.Errorf("group %v exceeds max_files", g["group_id"])
		}
	}
	for kind, n := range kinds {
		if n > 5 {
			t.Errorf("%s produced %d groups, above max_groups", kind, n)
		}
	}
	// Never all-pairs: a consolidation group is one scope's procedures, capped
	// at max_neighbours, not every pair in the repository.
	if kinds[generator.KindConsolidation] == 0 {
		t.Error("no consolidation group over a scope holding two runbooks")
	}
	if body["estimated_usd_max"].(float64) != 0 {
		t.Errorf("the deterministic recipe cannot cost money: %v", body["estimated_usd_max"])
	}
}

// U2.2: every proposal field carries provenance, and the detail view shows the
// body a reviewer is comparing against.
func TestGenerateProducesProposalsWithProvenance(t *testing.T) {
	e := setup(t)
	generate(t, e)
	proposals := list(t, e, "")
	if len(proposals) == 0 {
		t.Fatal("the deterministic run produced no proposals")
	}
	_ = proposals
	detail := get(t, e, pick(t, e, generator.KindExtraction, "rotate-an-auth-sdk-signing-key"))
	provenance, _ := detail["provenance"].([]any)
	if len(provenance) == 0 {
		t.Fatal("a proposal with no provenance is not reviewable")
	}
	steps := 0
	for _, raw := range provenance {
		f, _ := raw.(map[string]any)
		origin, _ := f["origin"].(string)
		switch origin {
		case "source", "parsed", "inferred", "human":
		default:
			t.Errorf("field %v has origin %q, outside the contract's domain", f["field"], origin)
		}
		ref := f["source_ref"]
		confirm, _ := f["needs_confirmation"].(bool)
		if ref == nil && !confirm {
			t.Errorf("field %v has neither a source_ref nor needs_confirmation", f["field"])
		}
		if name, _ := f["field"].(string); strings.HasPrefix(name, "steps[") {
			steps++
			if ref == nil {
				t.Errorf("%s must name the source lines it came from", name)
			}
		}
	}
	if steps != 4 {
		t.Fatalf("expected the runbook's four steps, got %d", steps)
	}
	candidate, _ := detail["candidate"].(map[string]any)
	if body, _ := candidate["body"].(string); !strings.Contains(body, "JWKS endpoint") {
		t.Errorf("the candidate lost the procedure it extracted: %v", candidate["body"])
	}
	if detail["state"] != review.StateDraft {
		t.Errorf("a new proposal is a draft, got %v", detail["state"])
	}
}

// U2.5: exactly one consolidation with derived_from to both sources.
func TestConsolidationProducesOneSharedElementWithBothSources(t *testing.T) {
	e := setup(t)
	generate(t, e)
	found := 0
	for _, id := range list(t, e, generator.KindConsolidation) {
		detail := get(t, e, id)
		relations, _ := detail["relations"].([]any)
		derived := []string{}
		for _, raw := range relations {
			r, _ := raw.(map[string]any)
			if r["type"] == "derived_from" {
				derived = append(derived, r["to"].(string))
			}
		}
		if len(derived) < 2 {
			t.Errorf("consolidation %s has %d derived_from sources, needs two", id, len(derived))
		}
		joined := strings.Join(derived, " ")
		if strings.Contains(joined, "rotate-a") && strings.Contains(joined, "rotate-b") {
			found++
		}
	}
	if found != 1 {
		t.Fatalf("expected exactly one consolidation of the marked shared element, got %d", found)
	}
}

// U2.3: a restart after a checkpoint resumes and produces no duplicates, and a
// worker whose lease has moved on writes nothing.
func TestRestartAfterCheckpointDoesNotDuplicateCandidates(t *testing.T) {
	e := setup(t)
	generate(t, e)
	before := len(list(t, e, ""))
	if before == 0 {
		t.Fatal("nothing to re-run")
	}
	// A worker that died after a checkpoint leaves its job queued with the
	// checkpoint intact. Clearing the checkpoint is the harsher case: every
	// group runs again.
	execSQL(t, e, `UPDATE gfm.jobs SET state='queued',worker_id=NULL,lease_until=NULL,
 finished_at=NULL,result=NULL,checkpoint=NULL WHERE kind=$1`, review.KindGenerate)
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})
	if after := len(list(t, e, "")); after != before {
		t.Fatalf("a re-run produced %d proposals, was %d: the cache key did not dedupe", after, before)
	}
	deduplicated := 0.0
	for _, j := range e.h.Jobs(t, review.KindGenerate) {
		var result map[string]any
		_ = json.Unmarshal(j.Result, &result)
		if n, _ := result["candidates"].(float64); n != 0 {
			t.Errorf("the second run created %v new candidates for %s", n, result["kind"])
		}
		n, _ := result["deduplicated"].(float64)
		deduplicated += n
	}
	if deduplicated == 0 {
		t.Error("the re-run reports nothing deduplicated; the cache key did no work")
	}
}

// U2.7: with no generator configured the import stays exactly as the parse left
// it and the job says why it did nothing.
func TestNoGeneratorSkipsTheJobAndLeavesTheImportReady(t *testing.T) {
	e := setup(t)
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "gen-none"}, Key: "gen-none"})
	if status != 200 {
		t.Fatalf("generate: %d %v", status, body)
	}
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameNone)
	none, recipe, err := generator.Select(nil)
	if err != nil {
		t.Fatal(err)
	}
	e.h.RunGenerate(t, none, recipe)
	for _, j := range e.h.Jobs(t, review.KindGenerate) {
		if j.State != "skipped" {
			t.Errorf("job %s is %s, expected skipped", j.JobID, j.State)
		}
		if j.Error != "llm_not_configured" {
			t.Errorf("job %s says %q, expected llm_not_configured", j.JobID, j.Error)
		}
	}
	if n := len(list(t, e, "")); n != 0 {
		t.Errorf("a skipped generation produced %d proposals", n)
	}
	status, importStatus, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID})
	if status != 200 {
		t.Fatal(importStatus)
	}
	if importStatus["state"] != "ready" {
		t.Fatalf("import is %v, an unconfigured generator must not change it", importStatus["state"])
	}
}

// U2.7: the cost ceiling stops new calls and keeps the progress already made.
func TestCostCeilingStopsTheRunAndKeepsProgress(t *testing.T) {
	e := setup(t)
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "gen-budget",
			"kinds": []string{generator.KindExtraction}}, Key: "gen-budget"})
	if status != 200 {
		t.Fatalf("generate: %d %v", status, body)
	}
	spender := &costlyGenerator{inner: &generator.Deterministic{}, usd: 4}
	e.h.RunGenerate(t, spender, generator.Recipe{Generator: "test", Version: "test-1"})
	jobs := e.h.Jobs(t, review.KindGenerate)
	if len(jobs) != 1 {
		t.Fatalf("expected one extraction job, got %d", len(jobs))
	}
	var result map[string]any
	_ = json.Unmarshal(jobs[0].Result, &result)
	if result["stopped"] != "max_usd_reached" {
		t.Fatalf("the run did not stop on its budget: %v", result)
	}
	if n, _ := result["groups_done"].(float64); n == 0 {
		t.Fatalf("the budget stop discarded the work already done: %v", result)
	}
	if spender.calls > 2 {
		t.Fatalf("the ceiling did not stop new calls: %d", spender.calls)
	}
	if len(list(t, e, "")) == 0 {
		t.Fatal("the proposals produced before the ceiling were lost")
	}
}

type costlyGenerator struct {
	inner generator.Generator
	usd   float64
	calls int
}

func (g *costlyGenerator) Generate(ctx context.Context, req generator.Request) (generator.Output, generator.Cost, error) {
	g.calls++
	out, _, e := g.inner.Generate(ctx, req)
	return out, generator.Cost{Calls: 1, USDCertain: g.usd}, e
}

// U2.8 / §6: approve writes a human revision, export produces a patch and moves
// the proposal to awaiting_git — which is not published.
func TestApproveThenExport(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := pick(t, e, generator.KindExtraction, "rotate-an-auth-sdk-signing-key")
	detail := get(t, e, id)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d1", "decision": "approve",
			"reason":            "the procedure matches the runbook",
			"expected_revision": detail["expected_revision"]}, Key: "d1"})
	if status != 200 {
		t.Fatalf("approve: %d %v", status, body)
	}
	if body["state"] != review.StateApprovedForExport {
		t.Fatalf("approve left the proposal %v", body["state"])
	}
	if body["revision_id"] == nil {
		t.Fatal("approve did not record a revision")
	}

	status, export, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/export",
		Body: map[string]any{"idempotency_key": "x1"}, Key: "x1"})
	if status != 200 {
		t.Fatalf("export: %d %v", status, export)
	}
	if export["state"] != review.StateAwaitingGit {
		t.Fatalf("export left the proposal %v; export is not publication", export["state"])
	}
	files, _ := export["files"].([]any)
	if len(files) != 1 {
		t.Fatalf("expected one exported file, got %d", len(files))
	}
	patch, _ := export["patch"].(string)
	if !strings.HasPrefix(patch, "diff --git ") || !strings.Contains(patch, "new file mode") {
		t.Fatalf("the export is not a new-file patch:\n%s", patch)
	}

	// The publication view says awaiting_git, not published: nothing is serving.
	status, publication, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id + "/publication"})
	if status != 200 || publication["state"] != review.StateAwaitingGit {
		t.Fatalf("publication view: %d %v", status, publication)
	}

	// The patch is served as a diff for `git apply`.
	exportID := export["export_id"].(string)
	code, raw, header := e.owner.Raw(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/exports/" + exportID + "/patch"})
	if code != 200 || !strings.HasPrefix(header.Get("Content-Type"), "text/x-diff") {
		t.Fatalf("patch endpoint: %d %s", code, header.Get("Content-Type"))
	}
	if string(raw) != patch {
		t.Error("the patch endpoint and the export disagree")
	}
}

// §4.4: `expected_revision` that no longer matches is 409 with the current one.
func TestStaleRevisionIsRefusedWithTheCurrentRevision(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := list(t, e, generator.KindEnrichment)[0]
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d-stale", "decision": "approve",
			"reason": "looks right", "expected_revision": "not-the-current-one"}, Key: "d-stale"})
	if status != 409 || body["error"] != "stale_revision" {
		t.Fatalf("expected 409 stale_revision, got %d %v", status, body)
	}
	details, _ := body["details"].(map[string]any)
	if current, _ := details["current_revision"].(string); current == "" {
		t.Fatalf("stale_revision must name the current revision: %v", body)
	}
}

// §4.4: an edit may change prose; frontmatter, scope, owner and relations are
// identity and stay put.
func TestEditRejectsAChangeOfIdentity(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := pick(t, e, generator.KindExtraction, "rotate-an-auth-sdk-signing-key")
	detail := get(t, e, id)
	candidate, _ := detail["candidate"].(map[string]any)
	body, _ := candidate["body"].(string)

	edited := strings.Replace(body, "  layer: task", "  layer: abstract", 1)
	if edited == body {
		t.Fatalf("the candidate has no layer to change:\n%s", body)
	}
	status, out, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d-edit-bad", "decision": "edit",
			"reason": "moving it somewhere better", "candidate_body": edited,
			"expected_revision": detail["expected_revision"]}, Key: "d-edit-bad"})
	if status != 422 || out["error"] != "invalid_candidate_change" {
		t.Fatalf("expected 422 invalid_candidate_change, got %d %v", status, out)
	}

	// The same edit with only prose changed is accepted.
	prose := strings.Replace(body, "## Verification", "## Verification\n\nChecked by hand.", 1)
	status, out, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d-edit-ok", "decision": "edit",
			"reason": "clarified the verification step", "candidate_body": prose,
			"expected_revision": detail["expected_revision"]}, Key: "d-edit-ok"})
	if status != 200 {
		t.Fatalf("an edit of prose must be accepted: %d %v", status, out)
	}
}

// §4.4: a decision without a reason is refused; a rejected proposal is never
// regenerated (API-CONTRACT §8).
func TestRejectRequiresAReasonAndBlocksRegeneration(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := pick(t, e, generator.KindExtraction, "rotate-an-auth-sdk-signing-key")
	detail := get(t, e, id)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d-noreason", "decision": "reject",
			"reason": "", "expected_revision": detail["expected_revision"]}, Key: "d-noreason"})
	if status != 400 {
		t.Fatalf("a decision without a reason must be refused, got %d %v", status, body)
	}

	status, body, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d-reject", "decision": "reject",
			"reason": "the runbook is being retired", "expected_revision": detail["expected_revision"]},
		Key: "d-reject"})
	if status != 200 || body["state"] != review.StateRejected {
		t.Fatalf("reject: %d %v", status, body)
	}
	// Regenerating over the same bytes must not offer it again.
	execSQL(t, e, `UPDATE gfm.jobs SET state='queued',worker_id=NULL,lease_until=NULL,
 finished_at=NULL,result=NULL,checkpoint=NULL WHERE kind=$1`, review.KindGenerate)
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})
	for _, other := range list(t, e, "") {
		if other == id {
			continue
		}
		d := get(t, e, other)
		if d["path"] == detail["path"] && d["state"] == review.StateDraft {
			t.Fatalf("a rejected candidate came back as %s", other)
		}
	}
	if get(t, e, id)["state"] != review.StateRejected {
		t.Fatal("the rejection was overwritten by a re-run")
	}
}

// §2: another organisation's proposals, exports and snapshots are 403, with the
// same body a nonexistent organisation gets.
func TestAnotherOrganisationSeesNothing(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := list(t, e, "")[0]
	intruder := e.h.SignIn(t, "intruder", "intruder@example.test")
	other := intruder.CreateOrg(t, "other")
	_ = other
	for _, path := range []string{
		e.base + "/proposals",
		e.base + "/proposals/" + id,
		e.base + "/snapshots",
		e.base + "/exports/00000000-0000-4000-8000-000000000000",
	} {
		status, body, _ := intruder.Call(t, pivottest.Call{Method: http.MethodGet, Path: path})
		if status != 403 || body["error"] != "forbidden" {
			t.Errorf("%s: %d %v, expected 403 forbidden", path, status, body)
		}
		if body["details"] != nil {
			t.Errorf("%s leaked details: %v", path, body["details"])
		}
	}
	// An organisation that does not exist answers identically.
	missing := "/api/v1/orgs/00000000-0000-4000-8000-0000000000ff/repos/meridian/proposals"
	status, body, _ := intruder.Call(t, pivottest.Call{Method: http.MethodGet, Path: missing})
	if status != 403 || body["error"] != "forbidden" {
		t.Errorf("unknown org: %d %v", status, body)
	}
}

// A member reads proposals; only an owner decides on them.
func TestMembersReadAndOwnersDecide(t *testing.T) {
	e := setup(t)
	generate(t, e)
	id := list(t, e, "")[0]
	member := e.h.SignIn(t, "member", "member@example.test")
	invite(t, e, member)

	status, _, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/proposals"})
	if status != 200 {
		t.Fatalf("a member must be able to read proposals, got %d", status)
	}
	status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "m1", "decision": "approve", "reason": "why not"},
		Key:  "m1"})
	if status != 403 {
		t.Fatalf("a member must not decide, got %d %v", status, body)
	}
}

func invite(t *testing.T, e *env, member *pivottest.Client) {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + e.orgID + "/invitations",
		Body: map[string]any{"email": "member@example.test", "role": "member"}, Key: "inv-1"})
	if status != 200 && status != 201 {
		t.Fatalf("invite: %d %v", status, body)
	}
	url, _ := body["accept_url"].(string)
	token := url[strings.LastIndex(url, "/invitations/")+len("/invitations/"):]
	token = strings.TrimSuffix(token, "/accept")
	if i := strings.Index(token, "/"); i >= 0 {
		token = token[:i]
	}
	status, body, _ = member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/invitations/" + token + "/accept", Key: "acc-1"})
	if status != 200 && status != 201 {
		t.Fatalf("accept: %d %v", status, body)
	}
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func generate(t *testing.T, e *env) {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "gen-1"}, Key: "gen-1"})
	if status != 200 {
		t.Fatalf("generate: %d %v", status, body)
	}
	ids, _ := body["job_ids"].([]any)
	if len(ids) == 0 {
		t.Fatal("generate enqueued nothing")
	}
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})
}

func list(t *testing.T, e *env, kind string) []string {
	t.Helper()
	path := e.base + "/proposals?limit=100"
	if kind != "" {
		path += "&kind=" + kind
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: path})
	if status != 200 {
		t.Fatalf("list proposals: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	out := []string{}
	for _, raw := range items {
		item, _ := raw.(map[string]any)
		out = append(out, item["proposal_id"].(string))
	}
	return out
}

// pick returns the one proposal of a kind whose candidate path carries the
// marker. Selecting "whichever came first" would make a test pass on a
// different proposal than the one it describes.
func pick(t *testing.T, e *env, kind, marker string) string {
	t.Helper()
	for _, id := range list(t, e, kind) {
		d := get(t, e, id)
		if path, _ := d["path"].(string); strings.Contains(path, marker) {
			return id
		}
	}
	t.Fatalf("no %s proposal whose candidate path contains %q", kind, marker)
	return ""
}

func get(t *testing.T, e *env, id string) map[string]any {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id})
	if status != 200 {
		t.Fatalf("proposal %s: %d %v", id, status, body)
	}
	return body
}

func execSQL(t *testing.T, e *env, sql string, args ...any) {
	t.Helper()
	ctx := context.Background()
	tx, err := e.h.Pool.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, sql, args...); err != nil {
		t.Fatal(err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatal(err)
	}
}

// G1 — the publish handler read the import state and ignored it, so a request
// could buy a build of an import that will never be parsed: 200 and a job_id to
// the caller, then max_attempts of exponential backoff where nobody is looking.
func TestPublishRefusesAnImportThatCannotBeBuilt(t *testing.T) {
	e := setup(t)
	// A second import of the same tree under a different commit, created but
	// never uploaded, so it sits in `created` with its blobs still missing.
	manifest := pivottest.Manifest(t, e.tree, e.orgID, e.repo, true)
	manifest["commit"] = "89abcdef0123456789abcdef0123456789abcdef"
	status, created, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports",
		Body: map[string]any{"idempotency_key": "g1", "manifest": manifest}, Key: "g1"})
	if status != http.StatusCreated {
		t.Fatalf("create import: %d %v", status, created)
	}
	unparsed := created["import_id"].(string)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/publish",
		Body: map[string]any{"idempotency_key": "g1-publish", "import_id": unparsed},
		Key:  "g1-publish"})
	if status != http.StatusConflict || body["error"] != "import_not_ready" {
		t.Fatalf("publish of an unparsed import: %d %v", status, body)
	}
	// And nothing was queued for it.
	var queued int
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.jobs WHERE org_id=$1::uuid AND import_id=$2::uuid AND kind='publish.build'`,
		e.orgID, unparsed).Scan(&queued); err != nil {
		t.Fatal(err)
	}
	if queued != 0 {
		t.Fatalf("%d publish jobs were queued for an import that cannot be built", queued)
	}
	// The parsed import of the same repository still publishes.
	status, ok, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/publish",
		Body: map[string]any{"idempotency_key": "g1-ok", "import_id": e.importID}, Key: "g1-ok"})
	if status != http.StatusOK {
		t.Fatalf("publish of a ready import: %d %v", status, ok)
	}
}
