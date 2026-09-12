package agentrun_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// githubTreeAndContents wires a fake api.github.com that answers the git
// trees listing with three skill files and their contents, plus the token
// exchange every ghapp.Client and prFilesClient call needs.
func githubTreeAndContents(t *testing.T, fullName string, paths []string, onRead func(path string)) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", tokenHandler)
	mux.HandleFunc("/repos/"+fullName+"/git/trees/HEAD", func(w http.ResponseWriter, r *http.Request) {
		tree := make([]any, 0, len(paths))
		for _, p := range paths {
			tree = append(tree, map[string]any{"path": p, "type": "blob"})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"tree": tree, "truncated": false})
	})
	for _, p := range paths {
		p := p
		mux.HandleFunc("/repos/"+fullName+"/contents/"+p, func(w http.ResponseWriter, r *http.Request) {
			if onRead != nil {
				onRead(p)
			}
			body := "---\nname: " + p + "\n---\n\nContent of " + p + ".\n"
			_ = json.NewEncoder(w).Encode(map[string]any{
				"content": jsonBase64(body), "encoding": "base64", "size": len(body), "type": "file",
			})
		})
	}
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

func jsonBase64(s string) string {
	const table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var b strings.Builder
	data := []byte(s)
	for i := 0; i < len(data); i += 3 {
		var chunk [3]byte
		n := copy(chunk[:], data[i:])
		b.WriteByte(table[chunk[0]>>2])
		b.WriteByte(table[(chunk[0]&0x03)<<4|chunk[1]>>4])
		if n > 1 {
			b.WriteByte(table[(chunk[1]&0x0F)<<2|chunk[2]>>6])
		} else {
			b.WriteByte('=')
		}
		if n > 2 {
			b.WriteByte(table[chunk[2]&0x3F])
		} else {
			b.WriteByte('=')
		}
	}
	return b.String()
}

// enqueueLiveRepoJob writes a target row and its live.repo job directly,
// bypassing live.plan, so a test can set its own tight Limits without
// waiting on the package's own default ceiling.
func enqueueLiveRepoJob(t *testing.T, h *pivottest.Harness, orgID, runID, repoID string, installationID int64,
	fullName string, limits agentrun.Limits) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.live_run_targets(org_id,run_id,repo_id,state)
 VALUES($1::uuid,$2::uuid,$3,'queued')`, orgID, runID, repoID); e != nil {
		t.Fatal(e)
	}
	tx, e := h.Pool.Begin(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	payload, _ := json.Marshal(map[string]any{"schema_version": "live.repo-1", "org_id": orgID,
		"run_id": runID, "repo_id": repoID, "installation_id": installationID, "full_name": fullName})
	limitsRaw, _ := json.Marshal(limits)
	q := jobs.New(h.Pool)
	job, e := q.Enqueue(ctx, tx, jobs.Job{OrgID: orgID, Kind: live.KindRepo, RepoID: repoID,
		Payload: payload, Limits: limitsRaw, IdempotencyKey: "live.repo:" + runID + ":" + repoID})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return job
}

// A run must not spend past its own ceiling — and it must keep every event
// it already wrote rather than discarding progress made before the ceiling
// was reached (ADR-0046 §5).
func TestLiveRepoStopsAtSpendCeilingAndKeepsEvents(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")
	runID := startRun(t, owner, org, "scan for gaps", []string{"meridian"})

	var reads int32
	ghServer := githubTreeAndContents(t, "acme/meridian",
		[]string{"AGENTS.md", ".agents/skills/a/SKILL.md", ".agents/skills/b/SKILL.md"},
		func(string) { atomic.AddInt32(&reads, 1) })
	gh, _ := newGHClient(t, ghServer.URL)

	var modelCalls int32
	modelServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&modelCalls, 1)
		sseChatResponse(w, "looks fine to me", 1000, 1000)
	}))
	t.Cleanup(modelServer.Close)

	// $1000/M tokens each way: one call of 1000 in + 1000 out costs $2, so a
	// $1 ceiling is exceeded after exactly one call.
	env := func(name string) string {
		switch name {
		case "GUIDEFOLD_LIVE_USD_PER_MTOK_IN", "GUIDEFOLD_LIVE_USD_PER_MTOK_OUT":
			return "1000"
		case "OPENROUTER_BASE_URL":
			return modelServer.URL
		}
		return ""
	}

	limits := agentrun.Limits{MaxUSD: 1.0, MaxTokens: 100000, MaxFiles: 10, MaxOutputTokens: 256}
	enqueueLiveRepoJob(t, h, org, runID, "meridian", 1, "acme/meridian", limits)

	w := agentrun.NewLiveRepoWorker(h.Pool, gh, h.Keyring, env)
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	if e := worker.Run(ctx, h.Pool, "test-worker", w.Handlers(),
		worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
		t.Fatal(e)
	}

	if got := atomic.LoadInt32(&modelCalls); got != 1 {
		t.Fatalf("model calls = %d, want exactly 1 (stopped before the second file)", got)
	}
	if got := atomic.LoadInt32(&reads); got != 1 {
		t.Fatalf("files read = %d, want exactly 1", got)
	}

	state, errText := targetRow(t, h, org, runID, "meridian")
	if state != live.TargetFailed || errText != live.ErrorBudgetExhausted {
		t.Fatalf("target = %s/%s, want failed/%s", state, errText, live.ErrorBudgetExhausted)
	}
	runState, runErr := runRowState(t, h, org, runID)
	if runState != live.StatePartial || runErr == nil || *runErr != live.ErrorBudgetExhausted {
		t.Fatalf("run = %s/%v, want partial/%s", runState, runErr, live.ErrorBudgetExhausted)
	}

	// The event this package's own model call wrote before the ceiling
	// stopped it must still be there.
	var deltaCount int
	if e := h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND type=$3`, org, runID, live.EventModelDelta).
		Scan(&deltaCount); e != nil {
		t.Fatal(e)
	}
	if deltaCount == 0 {
		t.Fatal("the model.delta written before the ceiling was reached was not kept")
	}
}

// Cancellation stops the job at its next checkpoint, not at the end of the
// repository (ADR-0046 §7): the second file must never be read once an
// owner cancelled while the first was still in flight.
func TestLiveRepoCancellationStopsAtNextCheckpoint(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")
	runID := startRun(t, owner, org, "scan for gaps", []string{"meridian"})

	var secondFileRead int32
	ghServer := githubTreeAndContents(t, "acme/meridian",
		[]string{".agents/skills/a/SKILL.md", ".agents/skills/b/SKILL.md"},
		func(path string) {
			if path == ".agents/skills/b/SKILL.md" {
				atomic.AddInt32(&secondFileRead, 1)
			}
		})
	gh, _ := newGHClient(t, ghServer.URL)

	var firstCall int32
	modelServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if atomic.AddInt32(&firstCall, 1) == 1 {
			// The owner cancels while the first file's model call is still
			// being answered — before this handler returns, and so before
			// live.repo reaches its first checkpoint.
			status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
				Path: runsPath(org) + "/" + runID + "/cancel"})
			if status != http.StatusOK {
				t.Fatalf("cancel: %d %v", status, body)
			}
		}
		sseChatResponse(w, "narrating the file", 10, 10)
	}))
	t.Cleanup(modelServer.Close)

	limits := agentrun.DefaultLimits()
	enqueueLiveRepoJob(t, h, org, runID, "meridian", 1, "acme/meridian", limits)

	w := agentrun.NewLiveRepoWorker(h.Pool, gh, h.Keyring, modelEnv(modelServer.URL))
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	// The job is expected to end up fenced by the cancel above, which
	// worker.Run reports as a normal (non-error) outcome — it is the queue's
	// own generation fencing at work, not a bug in the run loop.
	if e := worker.Run(ctx, h.Pool, "test-worker", w.Handlers(),
		worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
		t.Fatal(e)
	}

	if got := atomic.LoadInt32(&secondFileRead); got != 0 {
		t.Fatalf("the second file was read %d times; cancellation must stop the job before it", got)
	}

	var jobState string
	if e := h.Pool.QueryRow(context.Background(), `SELECT state FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind=$2 AND repo_id=$3`, org, live.KindRepo, "meridian").Scan(&jobState); e != nil {
		t.Fatal(e)
	}
	if jobState != jobs.StateCancelled {
		t.Fatalf("job state = %s, want cancelled", jobState)
	}
	state, errText := targetRow(t, h, org, runID, "meridian")
	if state != live.TargetSkipped || errText != live.ErrorCancelled {
		t.Fatalf("target = %s/%s, want skipped/%s (written by the cancel call itself)", state, errText, live.ErrorCancelled)
	}
}

// The organisation's own key must never reach anything this run persists:
// not the job's payload, not its checkpoint, not its result, not its error.
func TestLiveRepoKeyNeverLeaksIntoPersistedState(t *testing.T) {
	h, owner, org := newHarness(t)
	owner.CreateRepo(t, org, "meridian", "https://github.com/acme/meridian")
	registerInstallation(t, h, org, 1, "acme/meridian")
	const secretKey = "sk-or-v1-this-must-never-be-persisted-anywhere"
	setCredential(t, owner, org, secretKey)
	runID := startRun(t, owner, org, "scan for gaps", []string{"meridian"})

	ghServer := githubTreeAndContents(t, "acme/meridian", []string{".agents/skills/a/SKILL.md"}, nil)
	gh, _ := newGHClient(t, ghServer.URL)

	modelServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// A broken provider or proxy that echoes the request back is exactly
		// the case internal/model's own leak test covers; here the concern
		// is one layer up, in what agentrun itself persists.
		sseChatResponse(w, "some narration text here", 50, 50)
	}))
	t.Cleanup(modelServer.Close)

	limits := agentrun.DefaultLimits()
	job := enqueueLiveRepoJob(t, h, org, runID, "meridian", 1, "acme/meridian", limits)

	w := agentrun.NewLiveRepoWorker(h.Pool, gh, h.Keyring, modelEnv(modelServer.URL))
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	if e := worker.Run(ctx, h.Pool, "test-worker", w.Handlers(),
		worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
		t.Fatal(e)
	}

	stored, e := jobs.New(h.Pool).Get(context.Background(), org, job.JobID)
	if e != nil {
		t.Fatal(e)
	}
	fields := map[string]string{
		"payload":    string(stored.Payload),
		"checkpoint": string(stored.Checkpoint),
		"result":     string(stored.Result),
		"error":      stored.Error,
	}
	for name, value := range fields {
		if strings.Contains(value, secretKey) {
			t.Fatalf("the credential leaked into the job's %s: %s", name, value)
		}
	}

	rows, e := h.Pool.Query(context.Background(), `SELECT type, payload::text FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, org, runID)
	if e != nil {
		t.Fatal(e)
	}
	defer rows.Close()
	for rows.Next() {
		var typ, payload string
		if e := rows.Scan(&typ, &payload); e != nil {
			t.Fatal(e)
		}
		if strings.Contains(payload, secretKey) {
			t.Fatalf("the credential leaked into a %s event: %s", typ, payload)
		}
	}
}
