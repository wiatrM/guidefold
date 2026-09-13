package agentrun_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

var repoIDPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,64}$`)

// installationRepositoriesServer stands in for api.github.com's
// GET /installation/repositories, the authoritative source
// github.sync_repositories reconciles from (API-CONTRACT §4.7/§8).
func installationRepositoriesServer(t *testing.T, fullNames []string) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", tokenHandler)
	mux.HandleFunc("/installation/repositories", func(w http.ResponseWriter, r *http.Request) {
		items := make([]map[string]any, 0, len(fullNames))
		for _, f := range fullNames {
			items = append(items, map[string]any{"full_name": f})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"total_count": len(items), "repositories": items})
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

func enqueueGitHubSyncJob(t *testing.T, h *pivottest.Harness, orgID string, installationID int64) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	tx, e := h.Pool.Begin(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	payload, _ := json.Marshal(map[string]any{
		"schema_version": "github.sync_repositories-1", "org_id": orgID, "installation_id": installationID,
	})
	q := jobs.New(h.Pool)
	job, e := q.Enqueue(ctx, tx, jobs.Job{OrgID: orgID, Kind: agentrun.KindGitHubSyncRepositories,
		Payload: payload, IdempotencyKey: "test-github-sync"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return job
}

func repoRow(t *testing.T, h *pivottest.Harness, orgID, repoID string) (gitHostURL string, installationID *int64) {
	t.Helper()
	var url string
	var inst *int64
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT git_host_url, github_installation_id FROM gfm.repos WHERE org_id=$1::uuid AND repo_id=$2`,
		orgID, repoID).Scan(&url, &inst); e != nil {
		t.Fatal(e)
	}
	return url, inst
}

func countRepos(t *testing.T, h *pivottest.Harness, orgID string) int {
	t.Helper()
	var n int
	if e := h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.repos WHERE org_id=$1::uuid`, orgID).Scan(&n); e != nil {
		t.Fatal(e)
	}
	return n
}

// A brand new repository the installation covers is created with a derived
// id and attached.
func TestGitHubSyncAttachesNewRepositories(t *testing.T) {
	h, _, org := newHarness(t)
	registerInstallation(t, h, org, 1, "acme/one", "acme/two")
	server := installationRepositoriesServer(t, []string{"acme/one", "acme/two"})
	gh, _ := newGHClient(t, server.URL)

	job := enqueueGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh).Handlers())

	if countRepos(t, h, org) != 2 {
		t.Fatalf("expected two reconciled repositories, got %d", countRepos(t, h, org))
	}
	var repoID1 string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid AND git_host_url='https://github.com/acme/one'`, org).
		Scan(&repoID1); e != nil {
		t.Fatal(e)
	}
	if !repoIDPattern.MatchString(repoID1) {
		t.Fatalf("derived repo_id %q does not match repoPattern", repoID1)
	}
	_, inst := repoRow(t, h, org, repoID1)
	if inst == nil || *inst != 1 {
		t.Fatalf("repo not attached to installation: %v", inst)
	}
	var state string
	if e := h.Pool.QueryRow(context.Background(), `SELECT state FROM gfm.jobs WHERE job_id=$1::uuid`, job.JobID).Scan(&state); e != nil {
		t.Fatal(e)
	}
	if state != jobs.StateDone {
		t.Fatalf("job state = %q, want done", state)
	}
}

// A repository already registered by hand (or the CLI) at the same
// git_host_url is claimed, not duplicated.
func TestGitHubSyncAttachesExistingRepositoryByGitHostURL(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "monorepo", "https://github.com/acme/repo")
	registerInstallation(t, h, org, 1, "acme/repo")
	server := installationRepositoriesServer(t, []string{"acme/repo"})
	gh, _ := newGHClient(t, server.URL)

	enqueueGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh).Handlers())

	if n := countRepos(t, h, org); n != 1 {
		t.Fatalf("expected the existing row to be claimed, not duplicated: %d rows", n)
	}
	_, inst := repoRow(t, h, org, "monorepo")
	if inst == nil || *inst != 1 {
		t.Fatalf("existing repo was not attached: %v", inst)
	}
}

// A repository the installation no longer covers is detached, not deleted:
// gfm.repos keeps the row (and everything that references it) so an
// organisation's catalogue and review history survive a visibility change
// on GitHub's side.
func TestGitHubSyncDetachesRemovedRepositories(t *testing.T) {
	h, _, org := newHarness(t)
	registerInstallation(t, h, org, 1, "acme/one", "acme/two")
	firstServer := installationRepositoriesServer(t, []string{"acme/one", "acme/two"})
	gh, _ := newGHClient(t, firstServer.URL)
	enqueueGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh).Handlers())
	if countRepos(t, h, org) != 2 {
		t.Fatalf("setup: expected two repositories after the first sync")
	}
	var repoIDOne string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid AND git_host_url='https://github.com/acme/one'`, org).
		Scan(&repoIDOne); e != nil {
		t.Fatal(e)
	}

	// GitHub now reports only acme/two.
	secondServer := installationRepositoriesServer(t, []string{"acme/two"})
	gh2, _ := newGHClient(t, secondServer.URL)
	enqueueSecondGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh2).Handlers())

	if n := countRepos(t, h, org); n != 2 {
		t.Fatalf("detach must not delete the row: %d repositories remain", n)
	}
	_, inst := repoRow(t, h, org, repoIDOne)
	if inst != nil {
		t.Fatalf("acme/one should be detached (NULL), got installation %v", *inst)
	}
}

// enqueueSecondGitHubSyncJob uses a different idempotency key so the second
// sync in a test is a distinct job rather than a replay of the first.
func enqueueSecondGitHubSyncJob(t *testing.T, h *pivottest.Harness, orgID string, installationID int64) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	tx, e := h.Pool.Begin(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	payload, _ := json.Marshal(map[string]any{
		"schema_version": "github.sync_repositories-1", "org_id": orgID, "installation_id": installationID,
	})
	q := jobs.New(h.Pool)
	job, e := q.Enqueue(ctx, tx, jobs.Job{OrgID: orgID, Kind: agentrun.KindGitHubSyncRepositories,
		Payload: payload, IdempotencyKey: "test-github-sync-2"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return job
}

// Two different owners' repository of the same name must not collide: the
// hash-suffixed derivation is keyed on the whole full name, not just the
// trailing path segment.
func TestGitHubSyncDerivedRepoIDsDoNotCollideAcrossOwners(t *testing.T) {
	h, _, org := newHarness(t)
	registerInstallation(t, h, org, 1, "acme/widgets", "othercorp/widgets")
	server := installationRepositoriesServer(t, []string{"acme/widgets", "othercorp/widgets"})
	gh, _ := newGHClient(t, server.URL)

	enqueueGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh).Handlers())

	if n := countRepos(t, h, org); n != 2 {
		t.Fatalf("expected two distinct repositories, got %d", n)
	}
	var idAcme, idOther string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid AND git_host_url='https://github.com/acme/widgets'`, org).
		Scan(&idAcme); e != nil {
		t.Fatal(e)
	}
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid AND git_host_url='https://github.com/othercorp/widgets'`, org).
		Scan(&idOther); e != nil {
		t.Fatal(e)
	}
	if idAcme == idOther {
		t.Fatalf("acme/widgets and othercorp/widgets derived the same repo_id %q", idAcme)
	}
	if !repoIDPattern.MatchString(idAcme) || !repoIDPattern.MatchString(idOther) {
		t.Fatalf("derived ids must match repoPattern: %q %q", idAcme, idOther)
	}
}

// syncedAt reads gfm.github_installation_links.repositories_synced_at
// (API-CONTRACT §4.7, §7) directly.
func syncedAt(t *testing.T, h *pivottest.Harness, installationID int64) *time.Time {
	t.Helper()
	var at *time.Time
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT repositories_synced_at FROM gfm.github_installation_links WHERE installation_id=$1`, installationID).
		Scan(&at); e != nil {
		t.Fatal(e)
	}
	return at
}

// A successful run is the only thing that may claim reconciliation has
// happened: repositories_synced_at starts NULL and is written inside the
// same transaction as the gfm.repos attach/detach it reports on, never
// inferred from gfm.jobs (retained only 90 days, API-CONTRACT §7) or from
// gfm.github_installations.created_at/updated_at (the webhook mirror's own
// timestamps, untouched by this worker).
func TestGitHubSyncMarksReconciliationDone(t *testing.T) {
	h, _, org := newHarness(t)
	registerInstallation(t, h, org, 1, "acme/one")
	if at := syncedAt(t, h, 1); at != nil {
		t.Fatalf("a freshly linked installation must not read as already synced: %v", at)
	}
	server := installationRepositoriesServer(t, []string{"acme/one"})
	gh, _ := newGHClient(t, server.URL)

	enqueueGitHubSyncJob(t, h, org, 1)
	runOnce(t, h, agentrun.NewGitHubSyncWorker(h.Pool, gh).Handlers())

	if at := syncedAt(t, h, 1); at == nil {
		t.Fatal("a completed sync must record repositories_synced_at")
	}
}
