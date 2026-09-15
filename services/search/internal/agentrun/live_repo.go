package agentrun

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
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
		"Started scanning repository "+payload.RepoID+".", map[string]any{}); e != nil {
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
	// fetchRepositoryImport (github_import.go) is this same fetch → manifest
	// → CreateImport → PutBlob → FinalizeImport pipeline, shared with
	// github.import_repo (Task 3, API-CONTRACT §8 1.13.0). Everything below
	// this call is live.repo's own bookkeeping — a checkpoint, target phase
	// and event — which the shared core never touches.
	result, ferr := fetchRepositoryImport(ctx, w.pool, w.gh, w.imp, payload.InstallationID, payload.FullName,
		payload.OrgID, payload.RepoID, "live.repo", t.Job.JobID, limits)
	switch {
	case errors.Is(ferr, ghapp.ErrTreeTruncated):
		_ = w.failTarget(ctx, t, payload, reasonTreeTruncated)
		return "", "", worker.Permanent(ferr)
	case errors.Is(ferr, ghapp.ErrInstallationNotFound):
		_ = w.failTarget(ctx, t, payload, live.ErrorGitHubNotWired)
		return "", "", worker.Permanent(ferr)
	case errors.Is(ferr, errGuidefoldYAMLUnreadable):
		// ADR-0050: only an unreadable guidefold.yaml skips a target now. A
		// repository with none is imported under an inferred scope map.
		if e := w.skipTarget(ctx, t, payload, live.ErrorGuidefoldYAMLUnreadable); e != nil {
			return "", "", e
		}
		return "", "", worker.Skipped(live.ErrorGuidefoldYAMLUnreadable)
	case ferr != nil:
		if w.outOfAttempts(t) {
			_ = w.failTarget(ctx, t, payload, live.ErrorProviderDown)
		}
		return "", "", ferr
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
		fmt.Sprintf("Fetched %d %s from repository %s.", result.Files, plural(result.Files, "file"), payload.RepoID),
		map[string]any{"files": result.Files}); e != nil {
		return "", "", e
	}
	if e := tx3.Commit(ctx); e != nil {
		return "", "", e
	}
	return result.ImportID, result.ParseJobID, nil
}

// waitForChild is a thin wrapper over waitForChildJob (github_import.go),
// extracted so github.import_repo can reuse the same wait loop verbatim
// (ADR-0046 point 9). See that function's own doc comment for the design.
func (w *LiveRepoWorker) waitForChild(ctx context.Context, t *worker.Task, orgID, childJobID string) (*jobs.Job, error) {
	return waitForChildJob(ctx, w.queue, t, w.pollInterval(), orgID, childJobID)
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
	text := fmt.Sprintf("Imported repository %s: %d %s in the catalog.", payload.RepoID, skills, plural(skills, "skill"))
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
	text := fmt.Sprintf("Generated %d %s for repository %s.", proposals, plural(proposals, "proposal"), payload.RepoID)
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
	text := "Repository " + payload.RepoID + " finished."
	fields := map[string]any{}
	if reason != "" {
		state, errText = live.TargetFailed, reason
		text = fmt.Sprintf("Processing repository %s failed (%s).", payload.RepoID, reason)
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
	text := fmt.Sprintf("Repository %s was skipped (%s).", payload.RepoID, reason)
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
