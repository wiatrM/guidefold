package agentrun_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// prGitHubServer wires the token exchange, one pull request's changed
// files and the sticky-comment listing/posting a pr.report run needs, and
// hands back a pointer the test reads the posted comment body from once the
// job has run.
func prGitHubServer(t *testing.T, fullName string, changedFiles []map[string]string) (*httptest.Server, *string) {
	t.Helper()
	posted := new(string)
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", tokenHandler)
	mux.HandleFunc("/repos/"+fullName+"/pulls/2/files", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(changedFiles)
	})
	mux.HandleFunc("/repos/"+fullName+"/issues/2/comments", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			_ = json.NewEncoder(w).Encode([]any{})
		case http.MethodPost:
			var body struct {
				Body string `json:"body"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			*posted = body.Body
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": 1})
		}
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server, posted
}

func enqueuePRReportJob(t *testing.T, h *pivottest.Harness, orgID, repoID, fullName string) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	tx, e := h.Pool.Begin(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	payload, _ := json.Marshal(map[string]any{"schema_version": "pr.report-1", "org_id": orgID,
		"installation_id": 1, "repo_id": repoID, "full_name": fullName, "pr_number": 2,
		"head_sha": "deadbeef", "base_ref": "main"})
	q := jobs.New(h.Pool)
	job, e := q.Enqueue(ctx, tx, jobs.Job{OrgID: orgID, RepoID: repoID, Kind: agentrun.KindPRReport,
		Payload: payload, IdempotencyKey: "pr:1:2:deadbeef"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return job
}

func runOnce(t *testing.T, h *pivottest.Harness, handlers map[string]worker.Handler) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	if e := worker.Run(ctx, h.Pool, "test-worker", handlers, worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
		t.Fatal(e)
	}
}

// The rule check needs a model call, but posting the deterministic half of
// the comment does not — ADR-0036 point 4a requires the comment to name the
// applicable rules and say the promotion half did not run, and the job to
// end skipped, when the organisation stores no key.
func TestPRReportMissingKeyStillProducesCommentAndSkippedJob(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")
	publishRule(t, h, org, "meridian", "atlas", "atlas", "rotate-cache", "Rotate the cache",
		"Steps:\n1. Pause writers.\n2. Rotate.\n3. Resume writers.\n")

	ghServer, posted := prGitHubServer(t, "acme/meridian",
		[]map[string]string{{"filename": "atlas/service.py", "patch": "@@ -1,2 +1,3 @@\n+bad_thing()"}})
	gh, ghCfg := newGHClient(t, ghServer.URL)

	w := agentrun.NewPRReportWorker(h.Pool, gh, ghCfg, h.Keyring, modelEnv(""))
	job := enqueuePRReportJob(t, h, org, "meridian", "acme/meridian")
	runOnce(t, h, w.Handlers())

	if *posted == "" {
		t.Fatal("no comment was posted")
	}
	if !strings.Contains(*posted, "Rotate the cache") {
		t.Fatalf("comment does not name the applicable rule: %s", *posted)
	}
	if !strings.Contains(*posted, "no model key") {
		t.Fatalf("comment does not say the promotion half did not run for want of a key: %s", *posted)
	}

	stored, e := jobs.New(h.Pool).Get(context.Background(), org, job.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if stored.State != jobs.StateSkipped || stored.Error != "model_credential_missing" {
		t.Fatalf("job = %s/%q, want skipped/model_credential_missing", stored.State, stored.Error)
	}
}

// A provider that answers "out of credit" must end the job failed, name the
// provider in the comment, and never be retried — a retry against an
// exhausted account spends someone else's money for no output (ADR-0036
// point 4a).
func TestPRReportQuotaExhaustedFailsWithoutRetry(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")
	publishRule(t, h, org, "meridian", "atlas", "atlas", "rotate-cache", "Rotate the cache",
		"Steps:\n1. Pause writers.\n2. Rotate.\n3. Resume writers.\n")

	ghServer, posted := prGitHubServer(t, "acme/meridian",
		[]map[string]string{{"filename": "atlas/service.py", "patch": "@@ -1,2 +1,3 @@\n+bad_thing()"}})
	gh, ghCfg := newGHClient(t, ghServer.URL)

	var modelCalls int
	modelServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		modelCalls++
		w.WriteHeader(http.StatusPaymentRequired)
		_, _ = w.Write([]byte(`{"error":{"type":"insufficient_quota","message":"account has no funds"}}`))
	}))
	t.Cleanup(modelServer.Close)

	w := agentrun.NewPRReportWorker(h.Pool, gh, ghCfg, h.Keyring, modelEnv(modelServer.URL))
	job := enqueuePRReportJob(t, h, org, "meridian", "acme/meridian")
	runOnce(t, h, w.Handlers())

	if !strings.Contains(*posted, "out of budget") || !strings.Contains(*posted, "openrouter") {
		t.Fatalf("comment does not name the exhausted provider: %s", *posted)
	}

	stored, e := jobs.New(h.Pool).Get(context.Background(), org, job.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if stored.State != jobs.StateFailed || stored.Error != "model_quota_exhausted" {
		t.Fatalf("job = %s/%q, want failed/model_quota_exhausted", stored.State, stored.Error)
	}

	// A second pass over the queue must find nothing to retry: a
	// permanently-failed job never returns to 'queued'.
	runOnce(t, h, w.Handlers())
	if modelCalls != 1 {
		t.Fatalf("model was called %d times, want exactly 1 (no retry against an exhausted account)", modelCalls)
	}
}

// A pull request that touched a skill file must promote through ascend.run;
// one that did not must not.
func TestPRReportEnqueuesAscendOnlyWhenSkillFilesChanged(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")

	ghServer, _ := prGitHubServer(t, "acme/meridian",
		[]map[string]string{{"filename": "atlas/.agents/skills/rotate/SKILL.md", "patch": "@@ -1 +1 @@\n-a\n+b"}})
	gh, ghCfg := newGHClient(t, ghServer.URL)

	w := agentrun.NewPRReportWorker(h.Pool, gh, ghCfg, h.Keyring, modelEnv(""))
	enqueuePRReportJob(t, h, org, "meridian", "acme/meridian")
	runOnce(t, h, w.Handlers())

	var ascendCount int
	if e := h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind='ascend.run'`, org).Scan(&ascendCount); e != nil {
		t.Fatal(e)
	}
	if ascendCount != 1 {
		t.Fatalf("ascend.run jobs = %d, want 1 when a skill file changed", ascendCount)
	}
}
