package agentrun_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// githubTreeAndContents wires a fake api.github.com that answers the git
// trees listing with a fixed set of files and their contents, plus the token
// exchange every ghapp.Client call needs. bodies overrides the generic
// placeholder body for any path it names — a test that drives a real
// import.parse or proposal.generate needs a real guidefold.yaml and real
// SKILL.md frontmatter, not a placeholder the trusted builder would refuse
// or a generator would find nothing to consolidate in.
func githubTreeAndContents(t *testing.T, fullName string, paths []string, bodies map[string]string) *httptest.Server {
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
			body, ok := bodies[p]
			if !ok {
				body = "---\nname: " + p + "\n---\n\nContent of " + p + ".\n"
			}
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

// rootGuidefoldYAML is the Meridian fixture's own guidefold.yaml, proven
// valid by every other test that already runs the real builder over it
// (internal/importer/parse_test.go et al.): a `_root` node covering `**`,
// owned by platform-engineering, plus everything else the fixture declares.
// Reading it from disk rather than hand-writing a minimal one avoids
// guessing at fields tools/worker/build_tree.py's own CLI import requires
// beyond `publisher`.
func rootGuidefoldYAML(t *testing.T) string {
	t.Helper()
	tree := pivottest.Monorepo(t)
	data, e := os.ReadFile(filepath.Join(tree, "guidefold.yaml"))
	if e != nil {
		t.Fatal(e)
	}
	return string(data)
}

// sharedProcedureSkill is internal/review/api_test.go's own sharedProcedure
// fixture, duplicated rather than imported: it is review_test's unexported
// consolidation fixture (two skills marking the same procedure, so a
// consolidation group finds them), and this package has no dependency on
// that test package. Root-level (no platforms/ prefix), so it falls into the
// Meridian fixture's `_root` scope exactly as api_test.go's own copy does.
func sharedProcedureSkill(name, owner string) string {
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

// liveRepoFixture is the realistic setup every test below shares: a real run
// started through the API, live.plan drained once so the target row and the
// real live.repo job exist exactly as production creates them, and a
// *ghapp.Client wired at a fake GitHub serving the given files.
type liveRepoFixture struct {
	h      *pivottest.Harness
	owner  *pivottest.Client
	org    string
	runID  string
	repoID string
	gh     *ghapp.Client
}

const liveRepoFullName = "acme/meridian"

func setUpLiveRepoTarget(t *testing.T, key string, files []string, bodies map[string]string) *liveRepoFixture {
	t.Helper()
	h, owner, org := newHarness(t)
	const repoID = "meridian"
	owner.CreateRepo(t, org, repoID, "https://github.com/"+liveRepoFullName)
	registerInstallation(t, h, org, 1, liveRepoFullName)
	setCredential(t, owner, org, "sk-or-v1-0123456789abcdef")
	runID := startRun(t, owner, org, key)
	drainOnce(t, h, live.KindPlan, agentrun.NewLivePlanWorker(h.Pool).Handlers())

	server := githubTreeAndContents(t, liveRepoFullName, files, bodies)
	gh, _ := newGHClient(t, server.URL)
	return &liveRepoFixture{h: h, owner: owner, org: org, runID: runID, repoID: repoID, gh: gh}
}

func (f *liveRepoFixture) newWorker() *agentrun.LiveRepoWorker {
	w := agentrun.NewLiveRepoWorker(f.h.Pool, f.gh, importer.New(f.h.Pool, f.h.Blobs))
	w.PollInterval = 20 * time.Millisecond
	return w
}

func (f *liveRepoFixture) targetPhase(t *testing.T) (state, phase string) {
	t.Helper()
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT state, phase FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, f.org, f.runID, f.repoID).
		Scan(&state, &phase); e != nil {
		t.Fatal(e)
	}
	return state, phase
}

func (f *liveRepoFixture) waitForPhase(t *testing.T, phase string) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		if _, p := f.targetPhase(t); p == phase {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("target %s never reached phase %s", f.repoID, phase)
}

func (f *liveRepoFixture) eventTypes(t *testing.T) []string {
	t.Helper()
	rows, e := f.h.Pool.Query(context.Background(), `SELECT type FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3 ORDER BY seq`, f.org, f.runID, f.repoID)
	if e != nil {
		t.Fatal(e)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var typ string
		if e := rows.Scan(&typ); e != nil {
			t.Fatal(e)
		}
		out = append(out, typ)
	}
	return out
}

// runLiveRepoOnce leases and runs the one queued live.repo job, in the
// calling goroutine, and returns worker.Run's own error (about the lease
// loop itself, never about the handler's outcome — a failed or skipped job
// is recorded on the row, not returned here).
func runLiveRepoOnce(t *testing.T, f *liveRepoFixture, w *agentrun.LiveRepoWorker) error {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	return worker.Run(ctx, f.h.Pool, "test-worker", w.Handlers(), worker.Options{Once: true, Lease: 30 * time.Second})
}

// runLiveRepoInBackground is runLiveRepoOnce run concurrently with the
// caller, for tests that need to act (cancel, fence) while live.repo is
// still inside its own wait loop.
func runLiveRepoInBackground(f *liveRepoFixture, w *agentrun.LiveRepoWorker) <-chan error {
	done := make(chan error, 1)
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		done <- worker.Run(ctx, f.h.Pool, "test-worker", w.Handlers(), worker.Options{Once: true, Lease: 30 * time.Second})
	}()
	return done
}

// A repository going all the way from fetch to a finished repository,
// through the real pipeline both gaps this package closed were blocking:
// guidefold.yaml is fetched alongside two skills sharing a marked procedure,
// the real Python builder runs inside import.parse (pivottest.RunParseOnce,
// no fake), and the real proposal.generate runs through
// agentrun.NewReviewProposalGenerator — internal/review's own
// GenerateProposals seam. What this proves is the fetch → real builder →
// real seam → gfm.proposals row path — the claim that pressing the button
// leaves a proposal a human can review, not just that live.repo's own event
// sequencing is internally consistent.
//
// It does not exercise resolveGenerator's organisation-credential branch
// (API-CONTRACT §8): deleting gfm.org_credentials after the run starts —
// which handleCreate required — is what lets this test run the
// deterministic recipe instead of a real call to OpenRouter, so in
// production, where an active run always has a stored credential, this
// branch is not the one this test drives. internal/review's own
// api_test.go exercises the same ErrNoCredential fallback for the same
// reason; a real-provider path would need a fake OpenRouter server and
// OPENROUTER_BASE_URL pointed at it (generator.ForOrganisation hard-codes
// nil for env, so only the process environment reaches it) and is left
// for whoever adds coverage of that branch specifically.
func TestLiveRepoGoesFetchParseProposeDone(t *testing.T) {
	bodies := map[string]string{
		"guidefold.yaml":                   rootGuidefoldYAML(t),
		".agents/skills/rotate-a/SKILL.md": sharedProcedureSkill("rotate-a", "platform-engineering"),
		".agents/skills/rotate-b/SKILL.md": sharedProcedureSkill("rotate-b", "platform-engineering"),
	}
	files := []string{"guidefold.yaml", ".agents/skills/rotate-a/SKILL.md", ".agents/skills/rotate-b/SKILL.md"}
	f := setUpLiveRepoTarget(t, "happy-path", files, bodies)

	// review.GenerateWorker prefers an organisation's own stored credential
	// over WithGenerator (API-CONTRACT §8: "proposal.generate uruchomiony
	// przez przebieg bierze klucz preferowanego dostawcy tej organizacji").
	// The run's own creation required that credential (internal/live's
	// handleCreate); dropping it now, before proposal.generate resolves its
	// generator, is what lets this test run the deterministic recipe
	// instead of a real network call to OpenRouter — the same
	// ErrNoCredential fallback path internal/review/api_test.go's own
	// consolidation tests exercise.
	if _, e := f.h.Pool.Exec(context.Background(), `DELETE FROM gfm.org_credentials WHERE org_id=$1::uuid`,
		f.org); e != nil {
		t.Fatal(e)
	}

	scratch := pivottest.Scratch(t, "live-repo-happy-path")
	recipe := generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion}
	drainCtx, cancelDrain := context.WithCancel(context.Background())
	t.Cleanup(cancelDrain)
	go func() {
		for {
			select {
			case <-drainCtx.Done():
				return
			default:
			}
			ranParse := f.h.RunParseOnce(drainCtx, t, scratch)
			ranGenerate := f.h.RunGenerate(t, &generator.Deterministic{}, recipe) > 0
			if !ranParse && !ranGenerate {
				time.Sleep(20 * time.Millisecond)
			}
		}
	}()

	w := f.newWorker().WithProposalGenerator(agentrun.NewReviewProposalGenerator(f.h.Pool, f.h.Review))
	if e := runLiveRepoOnce(t, f, w); e != nil {
		t.Fatal(e)
	}

	events := f.eventTypes(t)
	want := []string{live.EventRepoStarted, live.EventRepoFetched, live.EventRepoParsed,
		live.EventRepoProposed, live.EventRepoFinished}
	if len(events) != len(want) {
		t.Fatalf("events = %v, want %v", events, want)
	}
	for i, typ := range want {
		if events[i] != typ {
			t.Fatalf("events[%d] = %s, want %s (full sequence %v)", i, events[i], typ, events)
		}
	}

	var state, phase, errText *string
	var skills, proposalCount int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT state, phase, skills, proposals, error
 FROM gfm.live_run_targets WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`,
		f.org, f.runID, f.repoID).Scan(&state, &phase, &skills, &proposalCount, &errText); e != nil {
		t.Fatal(e)
	}
	if state == nil || *state != live.TargetDone {
		t.Fatalf("target state = %v, want %s", state, live.TargetDone)
	}
	if phase == nil || *phase != live.PhaseDone {
		t.Fatalf("target phase = %v, want %s", phase, live.PhaseDone)
	}
	if skills != 2 {
		t.Fatalf("skills = %d, want 2", skills)
	}
	if proposalCount == 0 {
		t.Fatal("target.proposals = 0, want the shared procedure to have been consolidated")
	}
	if errText != nil {
		t.Fatalf("target error = %v, want none", *errText)
	}

	// The claim the whole feature makes: a proposal row exists in the
	// database a human can review, not merely a count on the target row.
	var proposalsInDB int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.proposals
 WHERE org_id=$1::uuid AND repo_id=$2 AND kind=$3`,
		f.org, f.repoID, generator.KindConsolidation).Scan(&proposalsInDB); e != nil {
		t.Fatal(e)
	}
	if proposalsInDB == 0 {
		t.Fatal("live.repo's real proposal.generate left no row in gfm.proposals")
	}

	runState, runErr := runRowState(t, f.h, f.org, f.runID)
	if runState != live.StateSucceeded {
		t.Fatalf("run state = %s/%v, want %s", runState, runErr, live.StateSucceeded)
	}
}

// A repository with no guidefold.yaml is not managed by Guidefold
// (API-CONTRACT §8, ADR-0046 point 9): live.repo skips it before ever
// calling CreateImport, rather than failing it the way a real import.parse
// failure does (the next test).
func TestLiveRepoSkipsRepositoryWithNoGuidefoldYAML(t *testing.T) {
	f := setUpLiveRepoTarget(t, "no-guidefold-yaml",
		[]string{"AGENTS.md", ".agents/skills/a/SKILL.md"}, nil)

	w := f.newWorker()
	if e := runLiveRepoOnce(t, f, w); e != nil {
		t.Fatal(e)
	}

	state, errText := targetRow(t, f.h, f.org, f.runID, f.repoID)
	if state != live.TargetSkipped || errText != live.ErrorGuidefoldYAMLMissing {
		t.Fatalf("target = %s/%s, want %s/%s", state, errText,
			live.TargetSkipped, live.ErrorGuidefoldYAMLMissing)
	}

	var imports int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2`, f.org, f.repoID).Scan(&imports); e != nil {
		t.Fatal(e)
	}
	if imports != 0 {
		t.Fatalf("an unmanaged repository got %d gfm.imports rows, want 0", imports)
	}

	runState, _ := runRowState(t, f.h, f.org, f.runID)
	if runState != live.StatePartial {
		t.Fatalf("run state = %s, want %s (one skipped target)", runState, live.StatePartial)
	}
}

// A repository whose guidefold.yaml is present but malformed is a real
// import.parse failure, driven through the real builder
// (pivottest.Harness.RunParseOnce, no fake) — distinct from
// TestLiveRepoSkipsRepositoryWithNoGuidefoldYAML's skip, and proving
// live.repo's own reaction to a genuine child-job failure: the target ends
// failed with a named reason and the run ends partial.
func TestLiveRepoChildJobFailureLeavesTargetFailedAndRunPartial(t *testing.T) {
	bodies := map[string]string{"guidefold.yaml": "- not\n- a\n- mapping\n"}
	f := setUpLiveRepoTarget(t, "parse-fails",
		[]string{"guidefold.yaml", "AGENTS.md", ".agents/skills/a/SKILL.md"}, bodies)
	scratch := pivottest.Scratch(t, "live-repo-parse-fail")
	drainCtx, cancelDrain := context.WithCancel(context.Background())
	t.Cleanup(cancelDrain)
	go func() {
		for {
			select {
			case <-drainCtx.Done():
				return
			default:
			}
			if f.h.RunParseOnce(drainCtx, t, scratch) {
				return
			}
			time.Sleep(20 * time.Millisecond)
		}
	}()

	w := f.newWorker()
	if e := runLiveRepoOnce(t, f, w); e != nil {
		t.Fatal(e)
	}

	var state string
	var errText *string
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT state, error FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, f.org, f.runID, f.repoID).
		Scan(&state, &errText); e != nil {
		t.Fatal(e)
	}
	if state != live.TargetFailed {
		t.Fatalf("target state = %s, want %s", state, live.TargetFailed)
	}
	if errText == nil || !strings.HasPrefix(*errText, "import_failed:") {
		t.Fatalf("target error = %v, want a reason starting with import_failed:", errText)
	}

	runState, _ := runRowState(t, f.h, f.org, f.runID)
	if runState != live.StatePartial {
		t.Fatalf("run state = %s, want %s", runState, live.StatePartial)
	}

	events := f.eventTypes(t)
	if len(events) == 0 || events[0] != live.EventRepoStarted || events[len(events)-1] != live.EventRepoFinished {
		t.Fatalf("events = %v, want to start with repo.started and end with repo.finished", events)
	}
	for _, typ := range events {
		if typ == live.EventRepoParsed || typ == live.EventRepoProposed {
			t.Fatalf("events = %v: a failed import.parse must never reach repo.parsed/repo.proposed", events)
		}
	}
}

// Cancellation must stop live.repo mid-wait, not only at the end of the
// repository (ADR-0046 point 7, point 9): the owner's cancel bumps this
// very job's generation, so the next Heartbeat inside the wait loop ends it
// before any further write — the target row is left exactly as the cancel
// route itself set it (skipped/cancelled_by_owner), never touched again by
// live.repo.
func TestLiveRepoCancellationStopsMidWait(t *testing.T) {
	f := setUpLiveRepoTarget(t, "cancel-mid-wait",
		[]string{"guidefold.yaml", "AGENTS.md", ".agents/skills/a/SKILL.md"}, nil)
	// import.parse is left queued forever: nothing drains it, so live.repo's
	// wait loop keeps polling until this test acts.

	w := f.newWorker()
	done := runLiveRepoInBackground(f, w)
	f.waitForPhase(t, live.PhaseParse)

	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: runsPath(f.org) + "/" + f.runID + "/cancel"})
	if status != http.StatusOK {
		t.Fatalf("cancel: %d %v", status, body)
	}

	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(15 * time.Second):
		t.Fatal("live.repo did not end after cancellation")
	}

	state, errText := targetRow(t, f.h, f.org, f.runID, f.repoID)
	if state != live.TargetSkipped || errText != live.ErrorCancelled {
		t.Fatalf("target = %s/%s, want %s/%s (written by the cancel call itself)",
			state, errText, live.TargetSkipped, live.ErrorCancelled)
	}
	for _, typ := range f.eventTypes(t) {
		if typ == live.EventRepoFinished {
			t.Fatalf("live.repo appended repo.finished after being cancelled: %v", f.eventTypes(t))
		}
	}
}

// A heartbeat that finds a stale generation — this job's own lease was
// re-leased elsewhere, simulated here by bumping gfm.jobs.generation
// directly rather than through cancel, so this test asserts fencing alone
// and not cancel's own target write — must end the job with no further
// write at all: not the target, not a new event.
func TestLiveRepoFencedHeartbeatEndsJobWithoutFurtherWrites(t *testing.T) {
	f := setUpLiveRepoTarget(t, "fenced-heartbeat",
		[]string{"guidefold.yaml", "AGENTS.md", ".agents/skills/a/SKILL.md"}, nil)

	w := f.newWorker()
	done := runLiveRepoInBackground(f, w)
	f.waitForPhase(t, live.PhaseParse)

	stateBefore, phaseBefore := f.targetPhase(t)
	eventsBefore := len(f.eventTypes(t))

	var generationBefore int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT generation FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind=$2 AND repo_id=$3`, f.org, live.KindRepo, f.repoID).Scan(&generationBefore); e != nil {
		t.Fatal(e)
	}
	if _, e := f.h.Pool.Exec(context.Background(), `UPDATE gfm.jobs SET generation=generation+1
 WHERE org_id=$1::uuid AND kind=$2 AND repo_id=$3`, f.org, live.KindRepo, f.repoID); e != nil {
		t.Fatal(e)
	}

	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(15 * time.Second):
		t.Fatal("live.repo did not end after being fenced")
	}

	stateAfter, phaseAfter := f.targetPhase(t)
	if stateAfter != stateBefore || phaseAfter != phaseBefore {
		t.Fatalf("target changed after fencing: %s/%s -> %s/%s, want no further write",
			stateBefore, phaseBefore, stateAfter, phaseAfter)
	}
	if got := len(f.eventTypes(t)); got != eventsBefore {
		t.Fatalf("event count changed after fencing: %d -> %d, want no further write", eventsBefore, got)
	}

	// finish()'s own Fail path would have added another +1 had it matched
	// the row's generation; it must not have, since the row is fenced
	// against exactly that write — the generation must be exactly the one
	// this test itself set, never higher.
	var generationAfter int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT generation FROM gfm.jobs
 WHERE org_id=$1::uuid AND kind=$2 AND repo_id=$3`, f.org, live.KindRepo, f.repoID).Scan(&generationAfter); e != nil {
		t.Fatal(e)
	}
	if generationAfter != generationBefore+1 {
		t.Fatalf("job generation = %d, want exactly %d (this test's own bump, nothing more)",
			generationAfter, generationBefore+1)
	}
}
