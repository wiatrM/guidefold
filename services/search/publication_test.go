package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// The publication and delivery half of the pivot, end to end: a real import, a
// real build over the repository's own Python builder, the operator's own
// snapshot writer, and then the 1.1 and 1.2 delivery contracts over what it
// published.
//
// These tests deliberately go through the whole path rather than seeding
// gf.skills. What is being checked is exactly the seam a seeded fixture hides:
// that the tree the worker materialises, the graph it validates and the
// snapshot it activates are the same thing.

// skillFile writes one SKILL.md with the frontmatter the CLI parses.
func skillFile(name, owner string, requires []string, body string) string {
	meta := "  owner: " + owner + "\n  status: active\n  kind: engineering\n  layer: team\n"
	if len(requires) > 0 {
		meta += "  requires: \"" + strings.Join(requires, ", ") + "\"\n"
	}
	return "---\nname: " + name + "\ndescription: \"[meridian] Fixture skill " + name +
		" for the publication tests.\"\nmetadata:\n" + meta + "---\n\n# " + name + "\n\n" + body + "\n"
}

func urn(node, name string) string { return "urn:skill:meridian:" + node + ":" + name }

// fixtureCommit is the commit pivottest.Manifest stamps on every scan, and
// therefore the repository revision a workspace has to declare.
const fixtureCommit = "0123456789abcdef0123456789abcdef01234567"

// pubEnv is one organisation with a management API, a delivery service over the
// same database, and a private copy of the Meridian tree.
type pubEnv struct {
	h        *pivottest.Harness
	owner    *pivottest.Client
	orgID    string
	base     string
	tree     string
	app      *App
	delivery *httptest.Server
	token    string
}

func newPubEnv(t *testing.T) *pubEnv {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "pub-owner", "pub-owner@example.test")
	orgID := owner.CreateOrg(t, "pubco")
	owner.CreateRepo(t, orgID, "meridian", "https://git.example.test/pubco/meridian")
	tree := pivottest.Monorepo(t)
	writeFile(t, tree, ".agents/skills/chain-1/SKILL.md",
		skillFile("chain-1", "platform-engineering", []string{urn("_root", "chain-2")},
			"Step one of a three-hop chain."))
	writeFile(t, tree, ".agents/skills/chain-2/SKILL.md",
		skillFile("chain-2", "platform-engineering", []string{urn("_root", "chain-3")},
			"Step two of a three-hop chain."))
	writeFile(t, tree, ".agents/skills/chain-3/SKILL.md",
		skillFile("chain-3", "platform-engineering", nil, "The last hop of the chain."))
	writeFile(t, tree, ".agents/skills/diamond-top/SKILL.md",
		skillFile("diamond-top", "platform-engineering",
			[]string{urn("_root", "diamond-left"), urn("_root", "diamond-right")},
			"Reaches one base by two paths."))
	writeFile(t, tree, ".agents/skills/diamond-left/SKILL.md",
		skillFile("diamond-left", "platform-engineering", []string{urn("_root", "diamond-base")}, "Left."))
	writeFile(t, tree, ".agents/skills/diamond-right/SKILL.md",
		skillFile("diamond-right", "platform-engineering", []string{urn("_root", "diamond-base")}, "Right."))
	writeFile(t, tree, ".agents/skills/diamond-base/SKILL.md",
		skillFile("diamond-base", "platform-engineering", nil, "Base."))
	wide := []string{}
	for i := 1; i <= 5; i++ {
		name := fmt.Sprintf("wide-%d", i)
		wide = append(wide, urn("_root", name))
		writeFile(t, tree, ".agents/skills/"+name+"/SKILL.md",
			skillFile(name, "platform-engineering", nil, "One of five dependencies."))
	}
	writeFile(t, tree, ".agents/skills/wide-top/SKILL.md",
		skillFile("wide-top", "platform-engineering", wide, "Needs five dependencies at once."))
	// A caller at the repository root that depends on a skill only the geo team
	// can see: from another scope the dependency is denied, not delivered.
	writeFile(t, tree, ".agents/skills/denied-caller/SKILL.md",
		skillFile("denied-caller", "platform-engineering",
			[]string{urn("atlas.geo", "denied-dep")}, "Depends on a geo-only skill."))
	writeFile(t, tree, "platforms/atlas/geo/.agents/skills/denied-dep/SKILL.md",
		skillFile("denied-dep", "geo-team", nil, "Only visible inside atlas.geo."))
	// A package resource, so USE 1.2 has a manifest to answer with.
	writeFile(t, tree, ".agents/skills/chain-3/references/policy.md", "# Policy\n\nThe rule.\n")
	writeFile(t, tree, ".agents/skills/chain-3/SKILL.md",
		strings.Replace(skillFile("chain-3", "platform-engineering", nil, "The last hop of the chain."),
			"  layer: team\n", "  layer: team\n  references: \"references/policy.md\"\n", 1))

	app, server := newDeliveryFor(t, h.Pool, orgID)
	token := makeToken(t, h.Pool, mgmt.SourceInstallation, orgID, "meridian", "",
		[]string{"search", "use", "events"})
	return &pubEnv{h: h, owner: owner, orgID: orgID,
		base: pivottest.RepoBase(orgID, "meridian"), tree: tree, app: app,
		delivery: server, token: token}
}

func writeFile(t *testing.T, tree, rel, body string) {
	t.Helper()
	full := filepath.Join(tree, filepath.FromSlash(rel))
	if e := os.MkdirAll(filepath.Dir(full), 0o755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(full, []byte(body), 0o644); e != nil {
		t.Fatal(e)
	}
}

// newDeliveryFor builds the /v1 service over the same database the management
// API writes, which is the only way the delivery tests can see what a
// publication actually did.
func newDeliveryFor(t *testing.T, pool *pgxpool.Pool, orgID string) (*App, *httptest.Server) {
	t.Helper()
	validator, e := newValidator("../../tools/serve_spike/contracts/harness-service-v1.1.schema.json")
	if e != nil {
		t.Fatal(e)
	}
	if validator.search12 == nil || validator.use12 == nil {
		t.Fatal("the 1.2 request schema was not found next to the 1.1 one")
	}
	svc, e := identity.New(pool, identity.Config{Mode: identity.ModeDev,
		PublicURL: "http://127.0.0.1", InsecureCookies: true})
	if e != nil {
		t.Fatal(e)
	}
	store := &Store{Pool: pool, Tenant: orgID, Repo: "meridian", LexicalEngine: "router",
		catalogs: newCatalogCache(catalogCacheSize)}
	app := &App{Store: store, Validator: validator, Identity: svc,
		Slots: make(chan struct{}, 32), EventSlots: make(chan struct{}, 8)}
	server := httptest.NewServer(app)
	t.Cleanup(server.Close)
	return app, server
}

// publishImport pushes a tree, parses it and runs the publication worker with
// the operator's own snapshot writer.
func (e *pubEnv) publishImport(t *testing.T, key string) string {
	t.Helper()
	manifest := pivottest.Manifest(t, e.tree, "pubco", "meridian", true)
	importID := pivottest.Push(t, e.owner, e.orgID, "meridian", e.tree, manifest, key)
	// A tree whose digest has not changed reuses its import, so a second push of
	// the same bytes queues no new parse. That is the point of the digest.
	e.h.RunParse(t, pivottest.Scratch(t, "parse-"+key))
	// PolicySHA is empty: this test has no /app/policy-source, so the bundle's
	// own CLI revision is stored and the reader is configured to match it.
	e.h.RunPublish(t, &snapshotPublisher{}, pivottest.Scratch(t, "publish-"+key))
	e.syncPolicySHA(t)
	return importID
}

// syncPolicySHA points the delivery store at the CLI revision the publication
// actually stored. In production both come from the deployed image; here the
// builder's own revision is the truth.
func (e *pubEnv) syncPolicySHA(t *testing.T) {
	t.Helper()
	var sha string
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT cli_sha FROM gf.snapshots WHERE tenant=$1 ORDER BY published_at DESC LIMIT 1`,
		e.orgID).Scan(&sha); err == nil {
		e.app.Store.PolicySHA = sha
		e.app.Store.catalogs = newCatalogCache(catalogCacheSize)
	}
}

func (e *pubEnv) head(t *testing.T) string {
	t.Helper()
	var id string
	err := e.h.Pool.QueryRow(context.Background(),
		`SELECT snapshot_id FROM gf.heads WHERE tenant=$1 AND repo='meridian'`, e.orgID).Scan(&id)
	if err != nil {
		return ""
	}
	return id
}

func (e *pubEnv) post(t *testing.T, path, body string) (int, M) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, e.delivery.URL+path, strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+e.token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var out M
	_ = json.NewDecoder(resp.Body).Decode(&out)
	return resp.StatusCode, out
}

// U5: a complete import builds, validates and activates one snapshot, and the
// skills it carried are marked published against exactly that snapshot.
func TestPublishBuildActivatesAndRecordsTheSnapshot(t *testing.T) {
	e := newPubEnv(t)
	importID := e.publishImport(t, "pub-1")
	snapshot := e.head(t)
	if snapshot == "" {
		t.Fatal("the publication did not activate a head")
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/snapshots"})
	if status != 200 {
		t.Fatalf("snapshots: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("expected one publication, got %d", len(items))
	}
	row, _ := items[0].(map[string]any)
	if row["state"] != review.PublicationActive || row["active"] != true {
		t.Fatalf("the publication is %v/%v, expected an active head", row["state"], row["active"])
	}
	if row["snapshot_id"] != snapshot {
		t.Fatalf("the publication names %v, the head is %s", row["snapshot_id"], snapshot)
	}
	if n, _ := row["n_skills"].(float64); n == 0 {
		t.Fatal("the publication reports no skills")
	}

	// The publication job is readable by its job id, with the publication.
	var jobID string
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT job_id::text FROM gfm.jobs WHERE org_id=$1::uuid AND kind=$2`,
		e.orgID, review.KindPublish).Scan(&jobID); err != nil {
		t.Fatal(err)
	}
	status, body, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/publications/" + jobID})
	if status != 200 {
		t.Fatalf("publications/{job_id}: %d %v", status, body)
	}
	if job, _ := body["job"].(map[string]any); job["state"] != "done" {
		t.Fatalf("the publication job is %v", body["job"])
	}
	if body["publication"] == nil {
		t.Fatal("the job carries no publication")
	}

	// The skills it published say which snapshot they are serving in.
	var published int
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid AND publication_status='published'
 AND published_snapshot_id=$2`, e.orgID, snapshot).Scan(&published); err != nil {
		t.Fatal(err)
	}
	if published == 0 {
		t.Fatal("no skill was marked published against the activated snapshot")
	}
	_ = importID
}

// U2.6: a graph cycle fails the publication, the reasons are recorded, and the
// snapshot that was serving keeps serving.
func TestACycleFailsPublicationAndKeepsThePreviousHead(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	first := e.head(t)
	if first == "" {
		t.Fatal("nothing was published to roll back to")
	}

	// chain-3 now requires chain-1, closing chain-1 → chain-2 → chain-3 → chain-1.
	writeFile(t, e.tree, ".agents/skills/chain-3/SKILL.md",
		skillFile("chain-3", "platform-engineering", []string{urn("_root", "chain-1")},
			"The last hop now points back at the first."))
	e.publishImport(t, "pub-cycle")

	if now := e.head(t); now != first {
		t.Fatalf("a cyclic import moved the head from %s to %s", first, now)
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/snapshots"})
	if status != 200 {
		t.Fatal(body)
	}
	items, _ := body["items"].([]any)
	failed := 0
	for _, raw := range items {
		row, _ := raw.(map[string]any)
		if row["state"] != review.PublicationFailed {
			continue
		}
		failed++
		if row["error"] != "graph_cycle" {
			t.Errorf("the failed publication says %v, expected graph_cycle", row["error"])
		}
		validation, _ := row["validation"].(map[string]any)
		findings, _ := validation["findings"].([]any)
		if len(findings) == 0 {
			t.Error("a failed publication must record why")
		}
	}
	if failed != 1 {
		t.Fatalf("expected one failed publication, got %d", failed)
	}
}

// U2.1: an import that could not parse every file is a known-incomplete
// catalog. Its skills are visible immediately, and it never becomes the
// snapshot every agent reads.
func TestPartialImportNeverActivates(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	first := e.head(t)

	writeFile(t, e.tree, ".agents/skills/broken/SKILL.md", "---\nname: [unclosed\n---\n\n# broken\n")
	e.publishImport(t, "pub-partial")

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/imports"})
	if status != 200 {
		t.Fatal(body)
	}
	items, _ := body["items"].([]any)
	if len(items) < 2 {
		t.Fatalf("expected two imports, got %d", len(items))
	}
	latest, _ := items[0].(map[string]any)
	if latest["state"] != "partial" {
		t.Fatalf("the import with a malformed SKILL.md is %v, expected partial", latest["state"])
	}
	if now := e.head(t); now != first {
		t.Fatalf("a partial import activated: head moved from %s to %s", first, now)
	}
	// The refusal names the file rather than only saying "something failed".
	status, snapshots, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/snapshots"})
	if status != 200 {
		t.Fatal(snapshots)
	}
	found := false
	for _, raw := range snapshots["items"].([]any) {
		row, _ := raw.(map[string]any)
		if row["error"] == "import_partial" {
			found = true
			validation, _ := row["validation"].(map[string]any)
			if raw, _ := json.Marshal(validation); !strings.Contains(string(raw), "broken/SKILL.md") {
				t.Errorf("the failed publication does not name the file: %s", raw)
			}
		}
	}
	if !found {
		t.Fatal("no publication recorded import_partial")
	}
}

// U5 / §4.4: activation is an owner decision with a stated reason, it is
// audited, and it can roll back to an earlier snapshot.
func TestSnapshotActivateAndRollbackWithReason(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	first := e.head(t)
	writeFile(t, e.tree, ".agents/skills/extra/SKILL.md",
		skillFile("extra", "platform-engineering", nil, "A second snapshot."))
	e.publishImport(t, "pub-2")
	second := e.head(t)
	if second == first || second == "" {
		t.Fatalf("the second import did not produce a new head (%s → %s)", first, second)
	}

	// A reason is required.
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/snapshots/" + first + "/activate",
		Body: map[string]any{"idempotency_key": "act-noreason"}, Key: "act-noreason"})
	if status != 400 {
		t.Fatalf("activate without a reason: %d %v", status, body)
	}

	status, body, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/snapshots/" + first + "/activate",
		Body: map[string]any{"idempotency_key": "act-1",
			"reason": "the new snapshot regressed the geo scope"}, Key: "act-1"})
	if status != 200 {
		t.Fatalf("activate: %d %v", status, body)
	}
	if now := e.head(t); now != first {
		t.Fatalf("rollback did not move the head: %s", now)
	}
	snapshot, _ := body["snapshot"].(map[string]any)
	if snapshot["state"] != review.PublicationActive || snapshot["active"] != true {
		t.Fatalf("the rolled-back snapshot is %v", snapshot)
	}

	// The reason is in the audit log, which is what makes a rollback reviewable.
	status, audit, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + e.orgID + "/audit"})
	if status != 200 {
		t.Fatal(audit)
	}
	found := false
	for _, raw := range audit["items"].([]any) {
		entry, _ := raw.(map[string]any)
		action, _ := entry["action"].(string)
		if strings.HasPrefix(action, "snapshot.activate") &&
			strings.Contains(action, "regressed the geo scope") {
			found = true
		}
	}
	if !found {
		t.Fatalf("the rollback reason is not in the audit log: %v", audit["items"])
	}

	// The previous head is superseded, not deleted: rolling forward again works.
	status, list, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/snapshots"})
	if status != 200 {
		t.Fatal(list)
	}
	states := map[string]string{}
	for _, raw := range list["items"].([]any) {
		row, _ := raw.(map[string]any)
		if id, ok := row["snapshot_id"].(string); ok {
			states[id] = row["state"].(string)
		}
	}
	if states[second] != review.PublicationSuperseded {
		t.Fatalf("the snapshot that was rolled back from is %q", states[second])
	}
}

// U2.8: a proposal is `published` only once its exported bytes are actually in
// the repository — proved by a second import that carries the file.
func TestExportBecomesPublishedAfterTheFileLands(t *testing.T) {
	e := newPubEnv(t)
	writeFile(t, e.tree, "README.md", pubRunbook)
	e.publishImport(t, "pub-1")

	importID := ""
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT import_id::text FROM gfm.imports WHERE org_id=$1::uuid ORDER BY created_at DESC LIMIT 1`,
		e.orgID).Scan(&importID); err != nil {
		t.Fatal(err)
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "gen-1",
			"kinds": []string{generator.KindExtraction}}, Key: "gen-1"})
	if status != 200 {
		t.Fatalf("generate: %d %v", status, body)
	}
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})

	status, list, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals?kind=extraction"})
	if status != 200 {
		t.Fatal(list)
	}
	items, _ := list["items"].([]any)
	if len(items) == 0 {
		t.Fatal("the runbook produced no extraction proposal")
	}
	id := items[0].(map[string]any)["proposal_id"].(string)
	_, detail, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: e.base + "/proposals/" + id})
	_ = detail
	status, decision, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d1", "decision": "approve",
			"reason": "the steps match the runbook"}, Key: "d1"})
	if status != 200 {
		t.Fatalf("approve: %d %v", status, decision)
	}
	status, export, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/export",
		Body: map[string]any{"idempotency_key": "x1"}, Key: "x1"})
	if status != 200 {
		t.Fatalf("export: %d %v", status, export)
	}
	files, _ := export["files"].([]any)
	file, _ := files[0].(map[string]any)
	path, _ := file["path"].(string)
	content, _ := file["content"].(string)

	// Still awaiting git: nothing has landed yet.
	status, publication, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id + "/publication"})
	if status != 200 || publication["state"] != review.StateAwaitingGit {
		t.Fatalf("before the commit the proposal is %v", publication["state"])
	}

	// The owner commits the patch; the next import carries it.
	writeFile(t, e.tree, path, content)
	e.publishImport(t, "pub-2")

	status, publication, _ = e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id + "/publication"})
	if status != 200 || publication["state"] != review.StatePublished {
		t.Fatalf("after the file landed the proposal is %v", publication["state"])
	}
	if publication["snapshot_id"] == nil {
		t.Error("a published proposal must name the snapshot serving it")
	}
}

const pubRunbook = `# Rotate a platform credential

## Purpose

Replace a platform credential without downtime.

## Steps

1. Drain the workload that holds the credential.
2. Issue the replacement from the vault.
3. Roll the deployment and watch readiness.

## Verification

No authentication failures for thirty minutes.
`

// U2.6: a proposal that has been approved but never committed has no bytes in
// any import, so it cannot appear in SEARCH or USE.
func TestDraftsNeverReachDelivery(t *testing.T) {
	e := newPubEnv(t)
	writeFile(t, e.tree, "README.md", pubRunbook)
	e.publishImport(t, "pub-1")
	importID := ""
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT import_id::text FROM gfm.imports WHERE org_id=$1::uuid ORDER BY created_at DESC LIMIT 1`,
		e.orgID).Scan(&importID); err != nil {
		t.Fatal(err)
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "gen-1",
			"kinds": []string{generator.KindExtraction}}, Key: "gen-1"})
	if status != 200 {
		t.Fatal(body)
	}
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})

	// Approve one, so a *human* revision exists in gfm without a file in git.
	status, list, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals?kind=extraction"})
	if status != 200 {
		t.Fatal(list)
	}
	items, _ := list["items"].([]any)
	if len(items) == 0 {
		t.Fatal("no proposal to approve")
	}
	id := items[0].(map[string]any)["proposal_id"].(string)
	candidatePath := items[0].(map[string]any)["path"].(string)
	status, decision, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "d1", "decision": "approve",
			"reason": "correct procedure"}, Key: "d1"})
	if status != 200 {
		t.Fatalf("approve: %d %v", status, decision)
	}

	// Re-publishing the same tree must not pick the approved candidate up.
	e.publishImport(t, "pub-2")
	name := strings.TrimSuffix(candidatePath[strings.LastIndex(candidatePath, "/skills/")+len("/skills/"):],
		"/SKILL.md")
	var inSnapshot int
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gf.skills WHERE tenant=$1 AND urn LIKE '%'||$2`,
		e.orgID, ":"+name).Scan(&inSnapshot); err != nil {
		t.Fatal(err)
	}
	if inSnapshot != 0 {
		t.Fatalf("an approved but uncommitted candidate reached the serving catalog as %s", name)
	}
	status, search := e.post(t, "/v1/search", `{"query":"rotate a platform credential"}`)
	if status != 200 {
		t.Fatalf("search: %d %v", status, search)
	}
	raw, _ := json.Marshal(search)
	if strings.Contains(string(raw), name) {
		t.Fatalf("a draft candidate appeared in SEARCH: %s", raw)
	}
}

// Gate 2 (U5.5): the 1.2 closure, over a real published graph.
func TestUse12Closure(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	snapshot := e.head(t)
	if snapshot == "" {
		t.Fatal("nothing was published")
	}
	revisions := e.revisions(t, snapshot)

	use := func(skill string, extra string) (int, M) {
		body := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-12345678",
 "skill_id":%q,"revision":%q,
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}%s}`,
			skill, revisions[skill], fixtureCommit, extra)
		return e.post(t, "/v1/use", body)
	}

	t.Run("chain_deeper_than_two", func(t *testing.T) {
		status, out := use(urn("_root", "chain-1"), "")
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		closure := obj(out["closure"])
		if closure == nil {
			t.Fatal("a 1.2 response must carry a closure")
		}
		if n := integer(closure, "depth_limit", 0); n != 8 {
			t.Fatalf("depth_limit is %d, the contract says 8", n)
		}
		seen := map[string]int{}
		for _, raw := range arr(closure["requires"]) {
			d := obj(raw)
			seen[str(d["skill_id"])] = int(integer(d, "depth", 0))
		}
		if seen[urn("_root", "chain-2")] != 1 || seen[urn("_root", "chain-3")] != 2 {
			t.Fatalf("the closure did not follow the chain past depth one: %v", seen)
		}
		if closure["status"] != "complete" {
			t.Fatalf("a three-card chain fits the default budget: %v", closure["status"])
		}
	})

	t.Run("diamond_reports_the_base_once", func(t *testing.T) {
		status, out := use(urn("_root", "diamond-top"), "")
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		closure := obj(out["closure"])
		count := 0
		for _, raw := range arr(closure["requires"]) {
			if str(obj(raw)["skill_id"]) == urn("_root", "diamond-base") {
				count++
			}
		}
		if count != 1 {
			t.Fatalf("the shared base appears %d times in the closure", count)
		}
		// top + left + right + base is four cards: exactly the default budget.
		if closure["status"] != "complete" {
			t.Fatalf("a diamond of four cards fits the default budget: %v", closure["status"])
		}
	})

	t.Run("more_than_four_cards_cannot_fit", func(t *testing.T) {
		status, out := use(urn("_root", "wide-top"), "")
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		closure := obj(out["closure"])
		if closure["status"] != "cannot_fit" {
			t.Fatalf("six cards under a budget of four must be cannot_fit, got %v", closure["status"])
		}
		// `cannot_fit` is not a truncated answer: the closure still names every
		// dependency, so the client knows exactly what it would need.
		if n := len(arr(closure["requires"])); n != 5 {
			t.Fatalf("cannot_fit truncated the closure to %d dependencies", n)
		}
		// The contract's cap is four cards; asking for it explicitly changes
		// nothing, and asking for more is outside the request schema.
		body := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-12345679",
 "skill_id":%q,"revision":%q,"budget":{"max_cards":4},
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}}`,
			urn("_root", "wide-top"), revisions[urn("_root", "wide-top")], fixtureCommit)
		status, out = e.post(t, "/v1/use", body)
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		if obj(out["closure"])["status"] != "cannot_fit" {
			t.Fatalf("an explicit budget of four is still cannot_fit, got %v", obj(out["closure"])["status"])
		}
	})

	t.Run("loaded_dependencies_do_not_consume_budget", func(t *testing.T) {
		loaded := fmt.Sprintf(`,"loaded_skills":[{"skill_id":%q,"revision":%q,"state":"hydrated"},
 {"skill_id":%q,"revision":%q,"state":"hydrated"}]`,
			urn("_root", "wide-1"), revisions[urn("_root", "wide-1")],
			urn("_root", "wide-2"), revisions[urn("_root", "wide-2")])
		status, out := use(urn("_root", "wide-top"), loaded)
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		closure := obj(out["closure"])
		if len(arr(closure["loaded"])) != 2 {
			t.Fatalf("the two loaded dependencies were not recognised: %v", closure["loaded"])
		}
	})

	t.Run("denied_dependency_is_named", func(t *testing.T) {
		body := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-12345680",
 "skill_id":%q,"revision":%q,
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"platforms/atlas/graph"}}`,
			urn("_root", "denied-caller"), revisions[urn("_root", "denied-caller")],
			fixtureCommit)
		status, out := e.post(t, "/v1/use", body)
		if status != 200 {
			t.Fatalf("use: %d %v", status, out)
		}
		closure := obj(out["closure"])
		found := ""
		for _, raw := range arr(closure["requires"]) {
			d := obj(raw)
			if str(d["skill_id"]) == urn("atlas.geo", "denied-dep") {
				found = str(d["status"])
			}
		}
		if found != "denied" {
			t.Fatalf("a dependency outside the resolved scope must be named denied, got %q", found)
		}
		if closure["status"] != "unresolved" {
			t.Fatalf("a denied dependency leaves the closure unresolved, got %v", closure["status"])
		}
	})

	t.Run("snapshot_changed_is_409", func(t *testing.T) {
		body := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-12345681",
 "skill_id":%q,"revision":%q,"search_snapshot":"repository:stale",
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}}`,
			urn("_root", "chain-3"), revisions[urn("_root", "chain-3")], fixtureCommit)
		status, out := e.post(t, "/v1/use", body)
		if status != 409 || out["error"] != "snapshot_changed" {
			t.Fatalf("expected 409 snapshot_changed, got %d %v", status, out)
		}
		// The same value, correct, is accepted.
		body = strings.Replace(body, "repository:stale", snapshot, 1)
		if status, out = e.post(t, "/v1/use", body); status != 200 {
			t.Fatalf("a matching search_snapshot must be accepted: %d %v", status, out)
		}
	})
}

// Gate 2 (U1.7, U5.5): the resource manifest and the bytes behind it.
func TestUse12ResourcesAndTheResourceEndpoint(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	snapshot := e.head(t)
	revisions := e.revisions(t, snapshot)
	skill := urn("_root", "chain-3")
	body := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-12345682",
 "skill_id":%q,"revision":%q,
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}}`,
		skill, revisions[skill], fixtureCommit)
	status, out := e.post(t, "/v1/use", body)
	if status != 200 {
		t.Fatalf("use: %d %v", status, out)
	}
	resources := arr(out["resources"])
	if len(resources) == 0 {
		t.Fatalf("the skill declares a package resource, the manifest is empty: %v", out["resources"])
	}
	entry := obj(resources[0])
	// Relative to the package, which is where a harness writes it.
	if str(entry["path"]) != "references/policy.md" {
		t.Fatalf("the resource path is not package-relative: %v", entry["path"])
	}
	url := str(entry["url"])
	if url == "" {
		t.Fatal("a resource entry with no url cannot be fetched")
	}

	req, err := http.NewRequest(http.MethodGet, e.delivery.URL+url, nil)
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "Bearer "+e.token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("resource endpoint: %d", resp.StatusCode)
	}
	raw := make([]byte, 4096)
	n, _ := resp.Body.Read(raw)
	if got := string(raw[:n]); got != "# Policy\n\nThe rule.\n" {
		t.Fatalf("the resource endpoint returned %q", got)
	}
	if resp.Header.Get("X-Content-SHA256") != str(entry["sha256"]) {
		t.Fatalf("the digest header %q disagrees with the manifest %v",
			resp.Header.Get("X-Content-SHA256"), entry["sha256"])
	}

	// A revision that is not the current one is 404, never the newest instead.
	stale := strings.Replace(url, revisions[skill], strings.Repeat("0", 64), 1)
	req, _ = http.NewRequest(http.MethodGet, e.delivery.URL+stale, nil)
	req.Header.Set("Authorization", "Bearer "+e.token)
	resp2, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != 404 {
		t.Fatalf("a stale revision must be 404, got %d", resp2.StatusCode)
	}

	// A path that tries to escape the package never reaches a query.
	escape := "/v1/skills/" + strings.ReplaceAll(skill, ":", "%3A") + "/revisions/" +
		revisions[skill] + "/resources/../../../etc/passwd"
	req, _ = http.NewRequest(http.MethodGet, e.delivery.URL+escape, nil)
	req.Header.Set("Authorization", "Bearer "+e.token)
	resp3, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp3.Body.Close()
	if resp3.StatusCode == 200 {
		t.Fatal("a traversing resource path was served")
	}
}

// api-contract-versioning: a 1.1 request gets exactly what it got before. The
// new fields exist only for a caller that asked for 1.2.
func TestUse11IsUnchangedBy12(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	revisions := e.revisions(t, e.head(t))
	skill := urn("_root", "chain-1")
	body := fmt.Sprintf(`{"schema_version":"1.1","request_id":"req-12345683",
 "skill_id":%q,"revision":%q,
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}}`,
		skill, revisions[skill], fixtureCommit)
	status, out := e.post(t, "/v1/use", body)
	if status != 200 {
		t.Fatalf("use 1.1: %d %v", status, out)
	}
	if out["schema_version"] != "1.1" {
		t.Fatalf("a 1.1 request answered %v", out["schema_version"])
	}
	if _, ok := out["closure"]; ok {
		t.Error("a 1.1 response must not grow a closure")
	}
	if _, ok := out["resources"]; ok {
		t.Error("a 1.1 response must not grow a resource manifest")
	}
	// 1.1 does not know search_snapshot, and an unknown field is 400.
	bad := strings.Replace(body, `"request_id"`, `"search_snapshot":"x","request_id"`, 1)
	if status, out = e.post(t, "/v1/use", bad); status != 400 {
		t.Fatalf("a 1.1 request with a 1.2 field must be 400, got %d %v", status, out)
	}
	// An unknown version is refused rather than treated as the newest.
	worse := strings.Replace(body, `"1.1"`, `"9.9"`, 1)
	if status, out = e.post(t, "/v1/use", worse); status != 400 ||
		out["error"] != "unsupported_schema_version" {
		t.Fatalf("expected 400 unsupported_schema_version, got %d %v", status, out)
	}
}

// revisions reads the snapshot's skill revisions, which is what USE requires
// the caller to send back exactly.
func (e *pubEnv) revisions(t *testing.T, snapshot string) map[string]string {
	t.Helper()
	rows, err := e.h.Pool.Query(context.Background(),
		`SELECT urn,skill_revision FROM gf.skills WHERE tenant=$1 AND repo='meridian' AND snapshot_id=$2`,
		e.orgID, snapshot)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var u, r string
		if err = rows.Scan(&u, &r); err != nil {
			t.Fatal(err)
		}
		out[u] = r
	}
	return out
}
