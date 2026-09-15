package agentrun_test

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// githubImportFixture is TestGitHubImportRepo*'s own setup: a repository
// registered from a linked GitHub installation exactly the way
// github.sync_repositories itself would leave it (github_installation_id
// set directly here, the same shortcut registerInstallation already takes
// for the mirror rows — these tests exercise github.import_repo, not
// reconciliation), and a *ghapp.Client wired at a fake GitHub serving the
// given files.
type githubImportFixture struct {
	h              *pivottest.Harness
	owner          *pivottest.Client
	org            string
	repoID         string
	installationID int64
	gh             *ghapp.Client
}

const githubImportFullName = "acme/widgets"

func setUpGitHubImportTarget(t *testing.T, files []string, bodies map[string]string) *githubImportFixture {
	t.Helper()
	h, owner, org := newHarness(t)
	const repoID = "widgets"
	const installationID = int64(1)
	owner.CreateRepo(t, org, repoID, "https://github.com/"+githubImportFullName)
	registerInstallation(t, h, org, installationID, githubImportFullName)
	linkRepoToInstallation(t, h, org, repoID, installationID)

	server := githubTreeAndContents(t, githubImportFullName, files, bodies)
	gh, _ := newGHClient(t, server.URL)
	return &githubImportFixture{h: h, owner: owner, org: org, repoID: repoID, installationID: installationID, gh: gh}
}

// linkRepoToInstallation writes gfm.repos.github_installation_id directly —
// there is no route that does only this (github.sync_repositories does it
// as part of a full reconciliation, tested separately in
// github_sync_test.go).
func linkRepoToInstallation(t *testing.T, h *pivottest.Harness, orgID, repoID string, installationID int64) {
	t.Helper()
	if _, e := h.Pool.Exec(context.Background(), `UPDATE gfm.repos SET github_installation_id=$3
 WHERE org_id=$1::uuid AND repo_id=$2`, orgID, repoID, installationID); e != nil {
		t.Fatal(e)
	}
}

func (f *githubImportFixture) newWorker() *agentrun.GitHubImportWorker {
	w := agentrun.NewGitHubImportWorker(f.h.Pool, f.gh, importer.New(f.h.Pool, f.h.Blobs))
	w.PollInterval = 20 * time.Millisecond
	return w
}

// requestGitHubImport calls the API route Task 3 adds (API-CONTRACT §4.2)
// and returns the job id it queued.
func (f *githubImportFixture) requestGitHubImport(t *testing.T, key string) string {
	t.Helper()
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: pivottest.RepoBase(f.org, f.repoID) + "/github/import", Body: map[string]any{"idempotency_key": key}})
	if status != http.StatusAccepted {
		t.Fatalf("POST github/import: %d %v", status, body)
	}
	jobID, _ := body["job_id"].(string)
	if jobID == "" {
		t.Fatalf("github/import returned no job_id: %v", body)
	}
	return jobID
}

// runGitHubImportOnce leases and runs the one queued github.import_repo job.
// Its own error is about the lease loop, never about the handler's outcome
// (skipped/failed is recorded on the job row) — the same contract
// runLiveRepoOnce documents for live.repo.
func runGitHubImportOnce(t *testing.T, f *githubImportFixture, w *agentrun.GitHubImportWorker) error {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	return worker.Run(ctx, f.h.Pool, "test-worker", w.Handlers(), worker.Options{Once: true, Lease: 30 * time.Second})
}

func githubImportJobState(t *testing.T, h *pivottest.Harness, orgID string) (state, errText string) {
	t.Helper()
	if e := h.Pool.QueryRow(context.Background(), `SELECT state,COALESCE(error,'') FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind=$2 ORDER BY created_at DESC LIMIT 1`,
		orgID, agentrun.KindGitHubImportRepo).Scan(&state, &errText); e != nil {
		t.Fatal(e)
	}
	return state, errText
}

func countRows(t *testing.T, h *pivottest.Harness, query string, args ...any) int {
	t.Helper()
	var n int
	if e := h.Pool.QueryRow(context.Background(), query, args...).Scan(&n); e != nil {
		t.Fatal(e)
	}
	return n
}

// The claim Task 3 makes: importing a GitHub-registered repository's skills
// works with no organisation model key at all — this harness never sets one
// (unlike setUpLiveRepoTarget's own fixture, which must, because starting a
// Live Agent run requires it) — and it never touches proposals: no
// proposal.generate job is enqueued and gfm.org_credentials stays empty.
func TestGitHubImportRepoWorksWithoutModelKey(t *testing.T) {
	bodies := map[string]string{
		"guidefold.yaml":                 rootGuidefoldYAML(t),
		".agents/skills/widget/SKILL.md": sharedProcedureSkill("widget", "platform-engineering"),
	}
	files := []string{"guidefold.yaml", ".agents/skills/widget/SKILL.md"}
	f := setUpGitHubImportTarget(t, files, bodies)

	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.org_credentials WHERE org_id=$1::uuid`, f.org); n != 0 {
		t.Fatalf("fixture already has a stored credential, want none: %d", n)
	}

	jobID := f.requestGitHubImport(t, "import-widgets-1")
	if jobID == "" {
		t.Fatal("no job id returned")
	}

	scratch := pivottest.Scratch(t, "github-import-no-key")
	drainCtx, cancelDrain := context.WithCancel(context.Background())
	drained := make(chan struct{})
	t.Cleanup(func() { cancelDrain(); <-drained })
	go func() {
		defer close(drained)
		for {
			select {
			case <-drainCtx.Done():
				return
			default:
			}
			if !f.h.RunParseOnce(drainCtx, t, scratch) {
				time.Sleep(20 * time.Millisecond)
			}
		}
	}()

	w := f.newWorker()
	if e := runGitHubImportOnce(t, f, w); e != nil {
		t.Fatal(e)
	}

	state, errText := githubImportJobState(t, f.h, f.org)
	if state != "done" {
		t.Fatalf("github.import_repo job state = %s (%s), want done", state, errText)
	}

	var importState string
	var skills int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT i.state, (SELECT count(*) FROM gfm.skills s
 WHERE s.org_id=i.org_id AND s.repo_id=i.repo_id)
 FROM gfm.imports i WHERE i.org_id=$1::uuid AND i.repo_id=$2 ORDER BY i.created_at DESC LIMIT 1`,
		f.org, f.repoID).Scan(&importState, &skills); e != nil {
		t.Fatal(e)
	}
	if importState != importer.StateReady {
		t.Fatalf("import state = %s, want %s", importState, importer.StateReady)
	}
	if skills != 1 {
		t.Fatalf("skills = %d, want 1", skills)
	}

	var blocked *string
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT import_blocked_reason FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, f.org, f.repoID).Scan(&blocked); e != nil {
		t.Fatal(e)
	}
	if blocked != nil {
		t.Fatalf("import_blocked_reason = %v, want NULL after a successful import", *blocked)
	}

	// The whole point: no model key was ever needed or touched.
	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.org_credentials WHERE org_id=$1::uuid`, f.org); n != 0 {
		t.Fatalf("github.import_repo touched gfm.org_credentials: %d row(s)", n)
	}
	if n := len(f.h.Jobs(t, "proposal.generate")); n != 0 {
		t.Fatalf("github.import_repo enqueued %d proposal.generate job(s), want 0", n)
	}
	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.proposals WHERE org_id=$1::uuid AND repo_id=$2`,
		f.org, f.repoID); n != 0 {
		t.Fatalf("github.import_repo left %d gfm.proposals row(s), want 0", n)
	}
}

// ADR-0050 (owner decision 2026-09-15): a repository with no guidefold.yaml
// is IMPORTED, under a scope map inferred from its skill directories and
// CODEOWNERS — not blocked. This test asserted the opposite before that
// decision ("named not importable"): the code was stricter than U1, which has
// always said the file only takes precedence (PRODUCT-PIVOT:69).
func TestGitHubImportRepoImportsWithoutGuidefoldYAML(t *testing.T) {
	bodies := map[string]string{
		".agents/skills/widget/SKILL.md": sharedProcedureSkill("widget", "platform-engineering"),
	}
	f := setUpGitHubImportTarget(t, []string{".agents/skills/widget/SKILL.md"}, bodies)

	f.requestGitHubImport(t, "import-widgets-2")

	scratch := pivottest.Scratch(t, "github-import-inferred")
	drainCtx, cancelDrain := context.WithCancel(context.Background())
	drained := make(chan struct{})
	t.Cleanup(func() { cancelDrain(); <-drained })
	go func() {
		defer close(drained)
		for {
			select {
			case <-drainCtx.Done():
				return
			default:
			}
			if !f.h.RunParseOnce(drainCtx, t, scratch) {
				time.Sleep(20 * time.Millisecond)
			}
		}
	}()

	w := f.newWorker()
	if e := runGitHubImportOnce(t, f, w); e != nil {
		t.Fatal(e)
	}

	state, errText := githubImportJobState(t, f.h, f.org)
	if state != "done" {
		t.Fatalf("github.import_repo job state = %s (%s), want done", state, errText)
	}

	var blocked *string
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT import_blocked_reason FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, f.org, f.repoID).Scan(&blocked); e != nil {
		t.Fatal(e)
	}
	if blocked != nil {
		t.Fatalf("import_blocked_reason = %v, want NULL — absence no longer blocks", *blocked)
	}

	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.imports WHERE org_id=$1::uuid AND repo_id=$2`,
		f.org, f.repoID); n != 1 {
		t.Fatalf("gfm.imports rows = %d, want 1", n)
	}
	// The scope map the import stored says where it came from.
	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2 AND source='inferred'`, f.org, f.repoID); n == 0 {
		t.Fatal("no gfm.scopes row with source='inferred'")
	}
	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid AND repo_id=$2`,
		f.org, f.repoID); n != 1 {
		t.Fatalf("skills = %d, want 1", n)
	}
}

// A repository not registered from any linked installation is refused
// before anything is enqueued.
func TestGitHubImportRepoRefusesARepositoryNotLinkedToGitHub(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "manual", "")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: pivottest.RepoBase(org, "manual") + "/github/import",
		Body: map[string]any{"idempotency_key": "manual-import"}})
	if status != http.StatusNotFound || body["error"] != "repo_not_github_linked" {
		t.Fatalf("import of an unlinked repository: %d %v", status, body)
	}
	if n := countRows(t, h, `SELECT count(*) FROM gfm.jobs WHERE org_id=$1::uuid AND kind=$2`,
		org, agentrun.KindGitHubImportRepo); n != 0 {
		t.Fatalf("a refused import enqueued %d job(s), want 0", n)
	}
}

// "Import all" is one call that enqueues one job per GitHub-registered
// repository of the organisation (Task 3, API-CONTRACT §4.2) — never a
// client-side loop, and it must not pick up a repository registered by hand.
func TestGitHubImportAllEnqueuesOnlyGitHubRegisteredRepositories(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "widgets", "https://github.com/"+githubImportFullName)
	owner.CreateRepo(t, org, "manual", "")
	registerInstallation(t, h, org, 1, githubImportFullName)
	linkRepoToInstallation(t, h, org, "widgets", 1)

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + org + "/github/import", Body: map[string]any{"idempotency_key": "import-all-1"}})
	if status != http.StatusAccepted {
		t.Fatalf("POST org github/import: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("import all items = %v, want exactly the GitHub-registered repository", items)
	}
	first, _ := items[0].(map[string]any)
	if first["repo_id"] != "widgets" || first["job_id"] == "" {
		t.Fatalf("import all item = %v", first)
	}
	if count, _ := body["count"].(float64); count != 1 {
		t.Fatalf("import all count = %v, want 1", body["count"])
	}
}

// Contract 1.17.0 / ADR-0050: a repository with no guidefold.yaml but with a
// CODEOWNERS gets its owner from that file. Before the fetch list carried
// CODEOWNERS the builder never saw it on this path, so every inferred scope
// came out `owner: unknown` for a repository that states its owners plainly.
// The assertion is on gfm.scopes.owner, not on the skill's own
// metadata.owner: the card names its own owner either way, and the scope is
// the thing CODEOWNERS is evidence about.
func TestGitHubImportRepoTakesTheScopeOwnerFromCodeowners(t *testing.T) {
	const skillPath = ".agents/skills/widget/SKILL.md"
	bodies := map[string]string{
		skillPath:    sharedProcedureSkill("widget", "platform-engineering"),
		"CODEOWNERS": "# owners of this repository\n* @acme/platform-guild\n",
	}
	f := setUpGitHubImportTarget(t, []string{skillPath, "CODEOWNERS"}, bodies)

	f.requestGitHubImport(t, "import-widgets-codeowners")

	scratch := pivottest.Scratch(t, "github-import-codeowners")
	drainCtx, cancelDrain := context.WithCancel(context.Background())
	drained := make(chan struct{})
	t.Cleanup(func() { cancelDrain(); <-drained })
	go func() {
		defer close(drained)
		for {
			select {
			case <-drainCtx.Done():
				return
			default:
			}
			if !f.h.RunParseOnce(drainCtx, t, scratch) {
				time.Sleep(20 * time.Millisecond)
			}
		}
	}()

	w := f.newWorker()
	if e := runGitHubImportOnce(t, f, w); e != nil {
		t.Fatal(e)
	}
	if state, errText := githubImportJobState(t, f.h, f.org); state != "done" {
		t.Fatalf("github.import_repo job state = %s (%s), want done", state, errText)
	}

	var owner string
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT COALESCE(owner,'') FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2 AND scope='_root'`, f.org, f.repoID).Scan(&owner); e != nil {
		t.Fatal(e)
	}
	if owner != "platform-guild" {
		t.Fatalf("_root scope owner = %q, want platform-guild from CODEOWNERS", owner)
	}
	// The file is configuration, not knowledge: it must not turn up in the
	// Library as a document beside the skills.
	if n := countRows(t, f.h, `SELECT count(*) FROM gfm.documents
 WHERE org_id=$1::uuid AND repo_id=$2 AND path='CODEOWNERS'`, f.org, f.repoID); n != 0 {
		t.Fatalf("CODEOWNERS became %d gfm.documents row(s); it is manifest kind config", n)
	}
}
