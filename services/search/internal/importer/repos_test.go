package importer_test

import (
	"context"
	"net/http"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

func listRepos(t *testing.T, owner *pivottest.Client, org string) []map[string]any {
	t.Helper()
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: "/api/v1/orgs/" + org + "/repos"})
	if status != http.StatusOK {
		t.Fatalf("list repos: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	out := make([]map[string]any, len(items))
	for i, it := range items {
		out[i], _ = it.(map[string]any)
	}
	return out
}

func repoByID(t *testing.T, rows []map[string]any, repoID string) map[string]any {
	t.Helper()
	for _, r := range rows {
		if r["repo_id"] == repoID {
			return r
		}
	}
	t.Fatalf("no repository %q in %v", repoID, rows)
	return nil
}

// A repository registered by hand or the CLI carries none of the
// GitHub-sourced or import-status fields Task 2 (1.13.0) adds — all six
// read back as JSON null, never zero values that could be mistaken for a
// real state.
func TestListReposCarriesNoGitHubFieldsForAManuallyRegisteredRepository(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "manual", "")

	row := repoByID(t, listRepos(t, owner, org), "manual")
	for _, field := range []string{"github_installation_id", "github_account", "import_blocked_reason",
		"last_import_state", "last_import_error", "last_import_at"} {
		if row[field] != nil {
			t.Fatalf("manually registered repository has %s = %v, want null", field, row[field])
		}
	}
}

// A repository registered from a linked GitHub installation carries the
// installation's own id and account name (1.13.0).
func TestListReposCarriesGitHubInstallationAndAccount(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "widgets", "https://github.com/acme/widgets")
	if _, e := h.Pool.Exec(context.Background(), `INSERT INTO gfm.github_installations(installation_id,account)
 VALUES(42,'acme') ON CONFLICT (installation_id) DO UPDATE SET account=excluded.account`); e != nil {
		t.Fatal(e)
	}
	if _, e := h.Pool.Exec(context.Background(), `UPDATE gfm.repos SET github_installation_id=42
 WHERE org_id=$1::uuid AND repo_id='widgets'`, org); e != nil {
		t.Fatal(e)
	}

	row := repoByID(t, listRepos(t, owner, org), "widgets")
	if row["github_installation_id"] != float64(42) {
		t.Fatalf("github_installation_id = %v, want 42", row["github_installation_id"])
	}
	if row["github_account"] != "acme" {
		t.Fatalf("github_account = %v, want acme", row["github_account"])
	}
}

// import_blocked_reason (1.13.0, Task 3) names why the last
// github.import_repo attempt never reached CreateImport — never rendered as
// a failed import, because no gfm.imports row exists for it to attach to.
func TestListReposCarriesImportBlockedReason(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "no-yaml", "")
	if _, e := h.Pool.Exec(context.Background(), `UPDATE gfm.repos SET import_blocked_reason='guidefold_yaml_missing'
 WHERE org_id=$1::uuid AND repo_id='no-yaml'`, org); e != nil {
		t.Fatal(e)
	}

	row := repoByID(t, listRepos(t, owner, org), "no-yaml")
	if row["import_blocked_reason"] != "guidefold_yaml_missing" {
		t.Fatalf("import_blocked_reason = %v, want guidefold_yaml_missing", row["import_blocked_reason"])
	}
	if row["last_import_state"] != nil {
		t.Fatalf("last_import_state = %v, want null (no gfm.imports row exists)", row["last_import_state"])
	}
}

// last_import_state/last_import_error/last_import_at read the newest
// gfm.imports row — real, through CreateImport/FinalizeImport, not a
// hand-written row — the same fixture newFixture's own sibling tests
// already drive to a real "ready" state.
func TestListReposCarriesLastImportState(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	pivottest.Push(t, f.owner, f.org, f.repo, f.tree, manifest, "k1")
	scratch := pivottest.Scratch(t, "list-repos-last-import")
	if n := f.h.RunParse(t, scratch); n != 1 {
		t.Fatalf("import.parse ran %d times, want 1", n)
	}

	row := repoByID(t, listRepos(t, f.owner, f.org), f.repo)
	if row["last_import_state"] != "ready" {
		t.Fatalf("last_import_state = %v, want ready", row["last_import_state"])
	}
	if row["last_import_error"] != nil {
		t.Fatalf("last_import_error = %v, want null", row["last_import_error"])
	}
	if row["last_import_at"] == nil {
		t.Fatal("last_import_at is null after a finalized import")
	}
}
