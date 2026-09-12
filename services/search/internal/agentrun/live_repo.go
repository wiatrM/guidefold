package agentrun

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// Named reasons this handler writes to a target's `error` column, beyond the
// ones internal/live already exports for its own use (ErrorGitHubNotWired,
// ErrorCancelled, ...). Their spelling is this package's own judgment call:
// API-CONTRACT §5.5a and ADR-0046 do not name a target-level reason for a
// failed import.parse or proposal.generate, only the run-level ones already
// in internal/live.
const (
	reasonImportFailed           = "import_failed"
	reasonProposalGenerateFailed = "proposal_generate_failed"
	reasonTreeTruncated          = "repository_tree_truncated"
	// reasonModelCredentialMissing, reasonSecretUnavailable and
	// reasonModelQuotaExhausted no longer describe anything this file does
	// — live.repo never opens the organisation's model key itself — but
	// pr_report.go's own model call still needs exactly these three
	// spellings (API-CONTRACT §5.5a), so they stay declared here rather
	// than being redeclared a second time in that file.
	reasonModelCredentialMissing = "model_credential_missing"
	reasonSecretUnavailable      = "secret_encryption_unavailable"
	reasonModelQuotaExhausted    = "model_quota_exhausted"
)

// defaultReadRef is passed to ghapp for every read when a target carries no
// more specific ref. Neither API-CONTRACT §8 nor ADR-0046 names which
// commit a live run reads a repository at; "HEAD" — the repository's
// default branch — is this package's own judgment call for "the current
// state of the organisation's repositories" ADR-0046's own context section
// asks for.
const defaultReadRef = "HEAD"

// defaultLiveRepoPollInterval is how often live.repo checks a child job's
// row and renews its own lease while it waits (API-CONTRACT §8: "one job
// owns one repository end to end ... czekając na joby, które sam
// zakolejkował"). It is well under the queue's own heartbeat ceiling (10 s)
// so a fenced or cancelled run is noticed within one poll, not one lease.
const defaultLiveRepoPollInterval = 2 * time.Second

// ProposalGenerator is the narrow seam live.repo needs once import.parse has
// refreshed the catalog: compute which skills group into which consolidation
// targets and enqueue proposal.generate for them — exactly what
// POST {repo_base}/imports/{import_id}/proposals:generate does over HTTP
// (API-CONTRACT §8, internal/review's Service.GenerateProposals/handleGenerate).
//
// review.NewReviewProposalGenerator (proposal_generator.go) is the real
// implementation, wired in services/search/worker_handlers.go: it calls
// internal/review's own exported GenerateProposals seam — the in-process
// path over Service.plan, added alongside this seam so live.repo never
// reproduces the grouping rule itself (parent scope plus direct children, at
// most max_neighbours contributing skills per scope, the owner of the
// widened scope becoming the proposal's owner — API-CONTRACT §8). Copying
// that rule here instead would risk exactly the kind of drift ADR-0046's own
// amendment exists to warn about ("I wrote a second, worse ... call beside
// it"). A nil ProposalGenerator is therefore a wiring mistake, not a named
// deployment state: Run treats it as a programming error (worker.Permanent),
// never as a target outcome a caller of the API is meant to see.
type ProposalGenerator interface {
	// GenerateConsolidation enqueues proposal.generate with
	// payload.kind = "consolidation" for the given import, the way the HTTP
	// route does, and returns the job's id. callerJobID is this live.repo
	// job's own id, threaded through so the implementation can audit the
	// call under the same request identity CreateImportOptions/
	// FinalizeOptions already use (internal/importer): a worker names its
	// own job as the request, never the resource the call happens to act
	// on. An empty jobID with a nil error means the route found nothing to
	// group (fewer than two contributing scopes anywhere) and legitimately
	// enqueued nothing.
	GenerateConsolidation(ctx context.Context, orgID, repoID, importID, callerJobID string) (jobID string, err error)
}

// LiveRepoWorker runs live.repo: ADR-0046 points 2, 3, 9 for one repository.
// It never calls a model itself (that happens inside proposal.generate,
// under the organisation's own key — ADR-0046 point 9, API-CONTRACT §8):
// this worker only fetches a repository's files, drives them through the
// importer's own pipeline, and waits.
type LiveRepoWorker struct {
	pool  *pgxpool.Pool
	gh    *ghapp.Client // nil means the deployment has not wired the GitHub App network path (ADR-0046 consequences).
	imp   *importer.Service
	queue *jobs.Queue
	// proposals is the seam described on ProposalGenerator. nil is a wiring
	// mistake (see that type's doc comment), not a named deployment state:
	// Run reports it as worker.Permanent rather than a target-level reason.
	proposals ProposalGenerator
	// PollInterval overrides defaultLiveRepoPollInterval, mainly for tests
	// that want a wait loop to turn over in milliseconds rather than
	// seconds.
	PollInterval time.Duration
}

// NewLiveRepoWorker wires the handler. gh may be nil — that is a valid,
// named deployment state (ADR-0046 consequences: "the worker's NetworkPolicy
// needs egress to the OpenRouter endpoint in addition to GitHub; until that
// exists, live.repo terminates skipped with a named reason"), not a
// programming error to guard against with a panic. imp is the importer
// service whose in-process seam (CreateImport/PutBlob/FinalizeImport) this
// worker drives instead of going through HTTP.
func NewLiveRepoWorker(pool *pgxpool.Pool, gh *ghapp.Client, imp *importer.Service) *LiveRepoWorker {
	return &LiveRepoWorker{pool: pool, gh: gh, imp: imp, queue: jobs.New(pool)}
}

// WithProposalGenerator wires the seam ProposalGenerator describes. It is a
// setter rather than a constructor argument, the same shape
// review.GenerateWorker.WithGenerator uses to let a test substitute a fake
// without an httptest server per provider — here, without reproducing
// internal/review's own grouping logic.
func (w *LiveRepoWorker) WithProposalGenerator(p ProposalGenerator) *LiveRepoWorker {
	w.proposals = p
	return w
}

// Handlers maps the job kind this worker runs.
func (w *LiveRepoWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{live.KindRepo: w.Run}
}

func (w *LiveRepoWorker) pollInterval() time.Duration {
	if w.PollInterval > 0 {
		return w.PollInterval
	}
	return defaultLiveRepoPollInterval
}

// repoCheckpoint is what a resumed live.repo job reads to avoid redoing a
// finished stage (API-CONTRACT §8: "osiągnięty etap i job_id joba
// potomnego, na który czeka"). Stage names the stage this job is currently
// waiting to complete — live.PhaseParse while import.parse runs,
// live.PhasePropose while proposal.generate runs — and is empty before the
// repository has been fetched at all.
type repoCheckpoint struct {
	Stage      string `json:"stage"`
	ImportID   string `json:"import_id,omitempty"`
	ChildJobID string `json:"child_job_id,omitempty"`
}

// Run executes one live.repo job: one repository of one run, driven through
// fetch, parse and propose in order, resuming from whichever the checkpoint
// names.
func (w *LiveRepoWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload liveRepoPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode live.repo payload: %w", e))
	}
	if payload.SchemaVersion != liveRepoPayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported live.repo payload schema_version %q", payload.SchemaVersion))
	}
	if payload.OrgID != t.Job.OrgID || payload.RunID == "" || payload.RepoID == "" {
		return worker.Permanent(errors.New("live.repo payload does not match its job row"))
	}
	limits := decodeLimits(t.Job.Limits)

	if w.gh == nil {
		_ = w.failTarget(ctx, t, payload, live.ErrorGitHubNotWired)
		return worker.Skipped(live.ErrorGitHubNotWired)
	}

	var cp repoCheckpoint
	_ = json.Unmarshal(t.Job.Checkpoint, &cp)

	if cp.Stage == "" {
		if e := w.startTarget(ctx, t, payload); e != nil {
			return e
		}
		importID, parseJobID, e := w.fetchAndImport(ctx, t, payload, limits)
		if e != nil {
			return e
		}
		cp = repoCheckpoint{Stage: live.PhaseParse, ImportID: importID, ChildJobID: parseJobID}
		if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
			return e
		}
	}

	if cp.Stage == live.PhaseParse {
		job, e := w.waitForChild(ctx, t, payload.OrgID, cp.ChildJobID)
		if e != nil {
			return e
		}
		if job.State != jobs.StateDone {
			_ = w.failTarget(ctx, t, payload, failReason(reasonImportFailed, job))
			return worker.Permanent(fmt.Errorf("live.repo: import.parse %s ended %s: %s",
				cp.ChildJobID, job.State, job.Error))
		}
		skills := resultField(job.Result, "skills")
		if e := w.advanceParsed(ctx, t, payload, cp.ImportID, skills); e != nil {
			return e
		}
		if w.proposals == nil {
			// A wiring mistake, not a named deployment state (see
			// ProposalGenerator's own doc comment): every deployment that
			// runs this worker must wire the real seam
			// services/search/worker_handlers.go provides.
			err := errors.New("live.repo: ProposalGenerator not wired")
			_ = w.failTarget(ctx, t, payload, reasonProposalGenerateFailed+": "+err.Error())
			return worker.Permanent(err)
		}
		proposeJobID, e := w.proposals.GenerateConsolidation(ctx, payload.OrgID, payload.RepoID, cp.ImportID, t.Job.JobID)
		if e != nil {
			return fmt.Errorf("enqueue proposal.generate: %w", e)
		}
		if proposeJobID == "" {
			// Nothing to group (fewer than two contributing scopes anywhere):
			// a legitimate zero, not a failure of this repository's run.
			if e := w.advanceProposed(ctx, t, payload, skills, 0); e != nil {
				return e
			}
			return w.finishTarget(ctx, t, payload, "")
		}
		cp = repoCheckpoint{Stage: live.PhasePropose, ImportID: cp.ImportID, ChildJobID: proposeJobID}
		if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
			return e
		}
	}

	if cp.Stage == live.PhasePropose {
		job, e := w.waitForChild(ctx, t, payload.OrgID, cp.ChildJobID)
		if e != nil {
			return e
		}
		if job.State != jobs.StateDone {
			_ = w.failTarget(ctx, t, payload, failReason(reasonProposalGenerateFailed, job))
			return worker.Permanent(fmt.Errorf("live.repo: proposal.generate %s ended %s: %s",
				cp.ChildJobID, job.State, job.Error))
		}
		proposals := resultField(job.Result, "candidates")
		skills := 0 // read back from the target row rather than threaded through the checkpoint a second time
		if e := w.pool.QueryRow(ctx, `SELECT skills FROM gfm.live_run_targets
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, payload.OrgID, payload.RunID, payload.RepoID).
			Scan(&skills); e != nil {
			return e
		}
		if e := w.advanceProposed(ctx, t, payload, skills, proposals); e != nil {
			return e
		}
		if e := w.finishTarget(ctx, t, payload, ""); e != nil {
			return e
		}
	}

	t.Result = mustJSON(map[string]any{"stage": live.PhaseDone})
	return nil
}

// failReason prefers a child job's own error string, when it recorded one,
// over this package's generic fallback: "import.parse failed because the
// builder rejected every file" is more useful on the target row than
// "import_failed" alone.
func failReason(fallback string, job *jobs.Job) string {
	if job.Error != "" {
		return fallback + ":" + job.Error
	}
	return fallback
}

// resultField reads one integer field out of a finished job's Result JSON.
// A field that is absent, non-numeric or unparsable reads as zero rather
// than failing the caller — the count is a courtesy the console shows, not
// a value anything downstream depends on for correctness.
func resultField(raw json.RawMessage, key string) int {
	if len(raw) == 0 {
		return 0
	}
	var generic map[string]any
	if json.Unmarshal(raw, &generic) != nil {
		return 0
	}
	if v, ok := generic[key].(float64); ok {
		return int(v)
	}
	return 0
}

// outOfAttempts reports whether this is the job's last permitted attempt.
// A transient failure on an earlier attempt is left for the queue's own
// backoff; on the last one, the target row must be finalised here, because
// nothing else will ever run for this repository once the job itself ends
// failed.
func (w *LiveRepoWorker) outOfAttempts(t *worker.Task) bool {
	return t.Job.MaxAttempts > 0 && t.Job.Attempts >= t.Job.MaxAttempts
}

// startTarget marks one target running, phase fetch, and appends
// repo.started. Fenced first: a job whose lease already moved on when it
// was leased again elsewhere must write nothing.
func (w *LiveRepoWorker) startTarget(ctx context.Context, t *worker.Task, payload liveRepoPayload) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	if e := live.SetTargetState(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.TargetRunning, ""); e != nil {
		return e
	}
	if e := live.SetTargetPhase(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.PhaseFetch, 0, 0); e != nil {
		return e
	}
	if _, e := live.Append(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoStarted,
		"Rozpoczęto skanowanie repozytorium "+payload.RepoID+".", map[string]any{}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// fetchAndImport fetches guidefold.yaml, AGENTS.md and every
// **/.agents/skills/**/SKILL.md file through the GitHub adapter, builds an
// in-memory manifest from them and drives it through the importer's own
// in-process seam (CreateImport/PutBlob/FinalizeImport) — the same
// operations the HTTP route uses, without HTTP (API-CONTRACT §8).
// FinalizeImport enqueues import.parse itself; this never enqueues it a
// second time. The manifest is deliberately incomplete
// (domain.Manifest.Complete = false): a live run reads only three path
// shapes, and a manifest claiming completeness over that partial a tree
// would have import.parse read every other skill the repository has as
// deleted.
//
// A repository whose listing carries no guidefold.yaml is not managed by
// Guidefold (API-CONTRACT §8, ADR-0046 point 9): its target ends skipped
// with live.ErrorGuidefoldYAMLMissing before anything is imported, so an
// unmanaged repository never gets an import row.
func (w *LiveRepoWorker) fetchAndImport(ctx context.Context, t *worker.Task, payload liveRepoPayload,
	limits Limits) (importID, parseJobID string, err error) {
	files, e := w.gh.ListSkillFiles(ctx, payload.InstallationID, payload.FullName, defaultReadRef)
	switch {
	case errors.Is(e, ghapp.ErrTreeTruncated):
		_ = w.failTarget(ctx, t, payload, reasonTreeTruncated)
		return "", "", worker.Permanent(e)
	case errors.Is(e, ghapp.ErrInstallationNotFound):
		_ = w.failTarget(ctx, t, payload, live.ErrorGitHubNotWired)
		return "", "", worker.Permanent(e)
	case e != nil:
		if w.outOfAttempts(t) {
			_ = w.failTarget(ctx, t, payload, live.ErrorProviderDown)
		}
		return "", "", e
	}

	// guidefold.yaml is checked, and set aside, before the MaxFiles ceiling
	// below ever applies to it: it is the scope hierarchy import.parse's own
	// builder needs to build anything at all, not one more skill competing
	// with two hundred others for the same budget. Truncating it away would
	// turn a well-formed, merely large repository into one that fails with
	// "no guidefold.yaml" for a reason no owner watching the run could see.
	hasHierarchy := false
	rest := make([]string, 0, len(files))
	for _, p := range files {
		if p == "guidefold.yaml" {
			hasHierarchy = true
			continue
		}
		rest = append(rest, p)
	}
	if !hasHierarchy {
		err := w.skipTarget(ctx, t, payload, live.ErrorGuidefoldYAMLMissing)
		if err != nil {
			return "", "", err
		}
		return "", "", worker.Skipped(live.ErrorGuidefoldYAMLMissing)
	}
	sort.Strings(rest)
	if limits.MaxFiles > 0 {
		// -1 keeps the prepended hierarchy inside the declared ceiling
		// (API-CONTRACT §8 max_files) rather than one file over it; at
		// MaxFiles == 1 this fetches the hierarchy alone, which is the
		// correct precedence.
		max := limits.MaxFiles - 1
		if max < 0 {
			max = 0
		}
		if len(rest) > max {
			rest = rest[:max]
		}
	}
	files = append([]string{"guidefold.yaml"}, rest...)

	fileEntries := make([]map[string]any, 0, len(files))
	contentBySHA := map[string][]byte{}
	hierarchyFetched := false
	for _, path := range files {
		if e := ctx.Err(); e != nil {
			return "", "", e
		}
		content, e := w.gh.ReadFile(ctx, payload.InstallationID, payload.FullName, defaultReadRef, path)
		if errors.Is(e, ghapp.ErrFileTooLarge) {
			// One oversize file is left out of the manifest, not fatal to
			// the repository: the rest is still evidence worth keeping.
			// guidefold.yaml itself is checked for below: dropping it here
			// silently would leave the builder to fail with "no
			// guidefold.yaml", a cause that would contradict what actually
			// happened (the file exists; it is just too large to read).
			continue
		}
		if e != nil {
			if w.outOfAttempts(t) {
				_ = w.failTarget(ctx, t, payload, live.ErrorProviderDown)
			}
			return "", "", e
		}
		sum := sha256.Sum256(content)
		sha := hex.EncodeToString(sum[:])
		kind := domain.KindSkill
		switch path {
		case "AGENTS.md":
			kind = domain.KindDocument
		case "guidefold.yaml":
			kind = domain.KindConfig
			hierarchyFetched = true
		}
		fileEntries = append(fileEntries, map[string]any{
			"path": path, "sha256": sha, "size": len(content), "kind": kind, "mode": "100644"})
		contentBySHA[sha] = content
	}
	if !hierarchyFetched {
		// guidefold.yaml was listed but could not actually be read (today
		// only ghapp.ErrFileTooLarge takes this path) — the same named skip
		// as never having one, rather than a failed import.parse blaming
		// build_tree.py for an absence that is really an oversize read.
		err := w.skipTarget(ctx, t, payload, live.ErrorGuidefoldYAMLMissing)
		if err != nil {
			return "", "", err
		}
		return "", "", worker.Skipped(live.ErrorGuidefoldYAMLMissing)
	}

	publish := false
	manifestMap := map[string]any{
		"format": domain.Format, "org": payload.OrgID, "repo": payload.RepoID,
		"commit": nil, "complete": false, "dirty": false, "publish": publish,
		"cli_version": "live-agent", "scan_profile": "live", "root": ".",
		"files": fileEntries, "excluded": []any{}, "aliases": []any{}, "suggestions": []any{},
		"limits": map[string]any{"max_files": 0, "max_bytes": 0},
	}
	raw, e := json.Marshal(manifestMap)
	if e != nil {
		return "", "", worker.Permanent(fmt.Errorf("encode live.repo manifest: %w", e))
	}
	manifest, e := domain.ParseManifest(raw)
	if e != nil {
		return "", "", worker.Permanent(fmt.Errorf("build live.repo manifest: %w", e))
	}

	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", "", e
	}
	created, e := w.imp.CreateImport(ctx, tx, payload.OrgID, payload.RepoID, manifest,
		importer.CreateImportOptions{RawManifest: raw, Actor: "live.repo", RequestID: t.Job.JobID})
	if e != nil {
		_ = tx.Rollback(ctx)
		return "", "", fmt.Errorf("live.repo: create import: %w", e)
	}
	if e := tx.Commit(ctx); e != nil {
		return "", "", e
	}

	for _, sha := range created.Missing {
		content, ok := contentBySHA[sha]
		if !ok {
			return "", "", worker.Permanent(fmt.Errorf("live.repo: no fetched content for blob %s", sha))
		}
		if _, e := w.imp.PutBlob(ctx, payload.OrgID, sha, content); e != nil {
			return "", "", fmt.Errorf("live.repo: store blob %s: %w", sha, e)
		}
	}

	tx2, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", "", e
	}
	_, e = w.imp.FinalizeImport(ctx, tx2, payload.OrgID, payload.RepoID, created.ImportID,
		importer.FinalizeOptions{Actor: "live.repo", RequestID: t.Job.JobID})
	if e != nil {
		_ = tx2.Rollback(ctx)
		return "", "", fmt.Errorf("live.repo: finalize import: %w", e)
	}
	if e := tx2.Commit(ctx); e != nil {
		return "", "", e
	}

	// Read the parse job back by import rather than trusting
	// FinalizeResult.QueuedJobIDs: a resumed attempt after a crash between
	// FinalizeImport's commit and this job's own checkpoint finds the same
	// import already queued (FinalizeImport is a no-op the second time) and
	// still needs the job id it queued the first time.
	parseJobID, e = w.findJob(ctx, payload.OrgID, created.ImportID, importer.KindParse)
	if e != nil {
		return "", "", fmt.Errorf("live.repo: find import.parse job for %s: %w", created.ImportID, e)
	}

	tx3, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", "", e
	}
	defer func() { _ = tx3.Rollback(ctx) }()
	if e := fenceJob(ctx, tx3, t); e != nil {
		return "", "", e
	}
	if e := live.SetTargetPhase(ctx, tx3, payload.OrgID, payload.RunID, payload.RepoID, live.PhaseParse, 0, 0); e != nil {
		return "", "", e
	}
	if _, e := live.Append(ctx, tx3, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoFetched,
		fmt.Sprintf("Pobrano %d plików z repozytorium %s.", len(fileEntries), payload.RepoID),
		map[string]any{"files": len(fileEntries)}); e != nil {
		return "", "", e
	}
	if e := tx3.Commit(ctx); e != nil {
		return "", "", e
	}
	return created.ImportID, parseJobID, nil
}

// findJob reads back the one job of a kind an import has, regardless of
// whether this attempt or an earlier one queued it.
func (w *LiveRepoWorker) findJob(ctx context.Context, orgID, importID, kind string) (string, error) {
	var jobID string
	e := w.pool.QueryRow(ctx, `SELECT job_id::text FROM gfm.jobs
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND kind=$3 ORDER BY created_at LIMIT 1`,
		orgID, importID, kind).Scan(&jobID)
	return jobID, e
}

// waitForChild is the design ADR-0046 point 9 calls out by name: one job
// polling the row of the job it enqueued, renewing its own lease as it
// goes. The lease is 30 s and the heartbeat interval at most 10 s
// (API-CONTRACT §8); pollInterval() is comfortably under that ceiling. A
// heartbeat that returns jobs.ErrFenced — a stale generation, because this
// job's own lease expired and was re-leased, or because an owner cancelled
// the run and the cancel route bumped this very job's generation — ends the
// wait immediately, before any further write: the caller must return the
// error as-is rather than finalise anything, exactly the same rule
// fenceJob enforces for the package's transactional writes.
func (w *LiveRepoWorker) waitForChild(ctx context.Context, t *worker.Task, orgID, childJobID string) (*jobs.Job, error) {
	for {
		job, e := w.queue.Get(ctx, orgID, childJobID)
		if e != nil {
			return nil, e
		}
		switch job.State {
		case jobs.StateDone, jobs.StateFailed, jobs.StateSkipped, jobs.StateCancelled:
			return job, nil
		}
		if e := w.queue.Heartbeat(ctx, t.Job.JobID, t.Job.Generation); e != nil {
			return nil, e
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(w.pollInterval()):
		}
	}
}

// advanceParsed records import.parse's own result on the target and in the
// log: phase moves to propose (still zero proposals — none exist yet) and
// repo.parsed carries the skill count and the import id.
func (w *LiveRepoWorker) advanceParsed(ctx context.Context, t *worker.Task, payload liveRepoPayload,
	importID string, skills int) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	if e := live.SetTargetPhase(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.PhasePropose, skills, 0); e != nil {
		return e
	}
	text := fmt.Sprintf("Zaimportowano repozytorium %s: %d skilli w katalogu.", payload.RepoID, skills)
	if _, e := live.Append(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoParsed, text,
		map[string]any{"skills": skills, "import_id": importID}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// advanceProposed records proposal.generate's own result: phase moves to
// done and repo.proposed carries how many proposals it created.
func (w *LiveRepoWorker) advanceProposed(ctx context.Context, t *worker.Task, payload liveRepoPayload,
	skills, proposals int) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	if e := live.SetTargetPhase(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.PhaseDone, skills, proposals); e != nil {
		return e
	}
	text := fmt.Sprintf("Wygenerowano %d propozycji dla repozytorium %s.", proposals, payload.RepoID)
	if _, e := live.Append(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoProposed, text,
		map[string]any{"proposals": proposals}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// finishTarget writes the target's terminal state, appends repo.finished,
// and ends the run when this was the last target still in flight
// (helpers.go's maybeFinishRun). reason is "" for success.
func (w *LiveRepoWorker) finishTarget(ctx context.Context, t *worker.Task, payload liveRepoPayload, reason string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	state, errText := live.TargetDone, ""
	text := "Repozytorium " + payload.RepoID + " zostało przetworzone."
	fields := map[string]any{}
	if reason != "" {
		state, errText = live.TargetFailed, reason
		text = fmt.Sprintf("Przetwarzanie repozytorium %s zakończyło się niepowodzeniem (%s).", payload.RepoID, reason)
		fields["error"] = reason
	}
	if e := live.SetTargetState(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, state, errText); e != nil {
		return e
	}
	if _, e := live.Append(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoFinished, text, fields); e != nil {
		return e
	}
	if e := maybeFinishRun(ctx, tx, payload.OrgID, payload.RunID); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// skipTarget writes the target's terminal state as skipped rather than
// failed, appends repo.finished, and ends the run when this was the last
// target still in flight — exactly finishTarget's own bookkeeping, with a
// different terminal state for the one reason live.repo itself decides a
// repository was never this run's to fail: a repository not managed by
// Guidefold (live.ErrorGuidefoldYAMLMissing). Unlike failTarget, its own
// error is not swallowed by its callers: there is no other, more important
// error already in flight for this write to avoid masking.
func (w *LiveRepoWorker) skipTarget(ctx context.Context, t *worker.Task, payload liveRepoPayload, reason string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	text := fmt.Sprintf("Repozytorium %s zostało pominięte (%s).", payload.RepoID, reason)
	if e := live.SetTargetState(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.TargetSkipped, reason); e != nil {
		return e
	}
	if _, e := live.Append(ctx, tx, payload.OrgID, payload.RunID, payload.RepoID, live.EventRepoFinished, text,
		map[string]any{"error": reason}); e != nil {
		return e
	}
	if e := maybeFinishRun(ctx, tx, payload.OrgID, payload.RunID); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// failTarget is the best-effort path used from error branches that must not
// let a secondary write failure mask the error already being returned: its
// own error is deliberately swallowed by every caller.
func (w *LiveRepoWorker) failTarget(ctx context.Context, t *worker.Task, payload liveRepoPayload, reason string) error {
	return w.finishTarget(ctx, t, payload, reason)
}
