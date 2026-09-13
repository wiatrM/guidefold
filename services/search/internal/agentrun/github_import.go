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

// errGuidefoldYAMLMissing is fetchRepositoryImport's own sentinel for "this
// repository is not managed by Guidefold" (API-CONTRACT §8, ADR-0046 point
// 9): no guidefold.yaml at all, or one listed but too large to read
// (ghapp.ErrFileTooLarge) — both read the same to a caller, which is why
// live.repo already named them identically at both of its own call sites
// before this extraction. Its text mirrors live.ErrorGuidefoldYAMLMissing
// so a caller's %v keeps saying what an error log already did.
var errGuidefoldYAMLMissing = errors.New(live.ErrorGuidefoldYAMLMissing)

// repoFetchResult is fetchRepositoryImport's success outcome: the import it
// created (already finalized, import.parse already enqueued by
// FinalizeImport), that job's id, and how many files were fetched. The two
// callers write their own bookkeeping around this differently (live.repo:
// a checkpoint plus a live-run event; github.import_repo: nothing but its
// own job checkpoint), so this returns the raw count rather than writing
// anything itself.
type repoFetchResult struct {
	ImportID   string
	ParseJobID string
	Files      int
}

// fetchRepositoryImport is live.repo's own fetch/import core (ADR-0046,
// API-CONTRACT §8), pulled out of live_repo.go so github.import_repo (Task
// 3, API-CONTRACT §8 1.13.0) can run exactly the same fetch → manifest →
// CreateImport → PutBlob → FinalizeImport pipeline without reproducing it a
// second time — ADR-0046's own amendment warns against exactly that ("a
// second, worse ... call beside it"). It never touches a live run's own
// bookkeeping (checkpoints, target state, events) or a *worker.Task: a
// caller decides for itself what a transient error, ghapp.ErrTreeTruncated,
// ghapp.ErrInstallationNotFound and errGuidefoldYAMLMissing each mean for
// its own job kind.
func fetchRepositoryImport(ctx context.Context, pool *pgxpool.Pool, gh *ghapp.Client, imp *importer.Service,
	installationID int64, fullName, orgID, repoID, actor, requestID string, limits Limits) (repoFetchResult, error) {
	files, e := gh.ListSkillFiles(ctx, installationID, fullName, defaultReadRef)
	if e != nil {
		return repoFetchResult{}, e
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
		return repoFetchResult{}, errGuidefoldYAMLMissing
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
			return repoFetchResult{}, e
		}
		content, e := gh.ReadFile(ctx, installationID, fullName, defaultReadRef, path)
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
			return repoFetchResult{}, e
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
		return repoFetchResult{}, errGuidefoldYAMLMissing
	}

	publish := false
	manifestMap := map[string]any{
		"format": domain.Format, "org": orgID, "repo": repoID,
		"commit": nil, "complete": false, "dirty": false, "publish": publish,
		"cli_version": "live-agent", "scan_profile": "live", "root": ".",
		"files": fileEntries, "excluded": []any{}, "aliases": []any{}, "suggestions": []any{},
		"limits": map[string]any{"max_files": 0, "max_bytes": 0},
	}
	raw, e := json.Marshal(manifestMap)
	if e != nil {
		return repoFetchResult{}, worker.Permanent(fmt.Errorf("encode repository import manifest: %w", e))
	}
	manifest, e := domain.ParseManifest(raw)
	if e != nil {
		return repoFetchResult{}, worker.Permanent(fmt.Errorf("build repository import manifest: %w", e))
	}

	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return repoFetchResult{}, e
	}
	created, e := imp.CreateImport(ctx, tx, orgID, repoID, manifest,
		importer.CreateImportOptions{RawManifest: raw, Actor: actor, RequestID: requestID})
	if e != nil {
		_ = tx.Rollback(ctx)
		return repoFetchResult{}, fmt.Errorf("%s: create import: %w", actor, e)
	}
	if e := tx.Commit(ctx); e != nil {
		return repoFetchResult{}, e
	}

	for _, sha := range created.Missing {
		content, ok := contentBySHA[sha]
		if !ok {
			return repoFetchResult{}, worker.Permanent(fmt.Errorf("%s: no fetched content for blob %s", actor, sha))
		}
		if _, e := imp.PutBlob(ctx, orgID, sha, content); e != nil {
			return repoFetchResult{}, fmt.Errorf("%s: store blob %s: %w", actor, sha, e)
		}
	}

	tx2, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return repoFetchResult{}, e
	}
	_, e = imp.FinalizeImport(ctx, tx2, orgID, repoID, created.ImportID,
		importer.FinalizeOptions{Actor: actor, RequestID: requestID})
	if e != nil {
		_ = tx2.Rollback(ctx)
		return repoFetchResult{}, fmt.Errorf("%s: finalize import: %w", actor, e)
	}
	if e := tx2.Commit(ctx); e != nil {
		return repoFetchResult{}, e
	}

	// Read the parse job back by import rather than trusting
	// FinalizeResult.QueuedJobIDs: a resumed attempt after a crash between
	// FinalizeImport's commit and the caller's own checkpoint finds the same
	// import already queued (FinalizeImport is a no-op the second time) and
	// still needs the job id it queued the first time.
	parseJobID, e := findJob(ctx, pool, orgID, created.ImportID, importer.KindParse)
	if e != nil {
		return repoFetchResult{}, fmt.Errorf("%s: find import.parse job for %s: %w", actor, created.ImportID, e)
	}
	return repoFetchResult{ImportID: created.ImportID, ParseJobID: parseJobID, Files: len(fileEntries)}, nil
}

// findJob reads back the one job of a kind an import has, regardless of
// whether this attempt or an earlier one queued it.
func findJob(ctx context.Context, pool *pgxpool.Pool, orgID, importID, kind string) (string, error) {
	var jobID string
	e := pool.QueryRow(ctx, `SELECT job_id::text FROM gfm.jobs
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND kind=$3 ORDER BY created_at LIMIT 1`,
		orgID, importID, kind).Scan(&jobID)
	return jobID, e
}

// waitForChildJob is the design ADR-0046 point 9 calls out by name: one job
// polling the row of the job it enqueued, renewing its own lease as it goes
// (extracted from LiveRepoWorker.waitForChild so github.import_repo can
// reuse it verbatim). The lease is 30 s and the heartbeat interval at most
// 10 s (API-CONTRACT §8); pollInterval is expected to stay comfortably
// under that ceiling. A heartbeat that returns jobs.ErrFenced — a stale
// generation, because this job's own lease expired and was re-leased, or
// because an owner cancelled the run and the cancel route bumped this very
// job's generation — ends the wait immediately, before any further write:
// the caller must return the error as-is rather than finalise anything,
// exactly the same rule fenceJob enforces for this package's transactional
// writes.
func waitForChildJob(ctx context.Context, queue *jobs.Queue, t *worker.Task, pollInterval time.Duration, orgID, childJobID string) (*jobs.Job, error) {
	for {
		job, e := queue.Get(ctx, orgID, childJobID)
		if e != nil {
			return nil, e
		}
		switch job.State {
		case jobs.StateDone, jobs.StateFailed, jobs.StateSkipped, jobs.StateCancelled:
			return job, nil
		}
		if e := queue.Heartbeat(ctx, t.Job.JobID, t.Job.Generation); e != nil {
			return nil, e
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(pollInterval):
		}
	}
}

// KindGitHubImportRepo is the job Task 3 (API-CONTRACT §4.2/§8, 1.13.0)
// enqueues so importing a GitHub-registered repository's skills works
// without an organisation model key: it runs exactly live.repo's own first
// two stages (fetch, import.parse) through fetchRepositoryImport above, and
// never generates proposals, so it never opens an organisation's model key
// the way live.repo's own consolidation step does.
const KindGitHubImportRepo = "github.import_repo"

const githubImportPayloadVersion = "github.import_repo-1"

// githubImportPayload mirrors internal/importer's own unexported payload
// type for github.import_repo byte for byte — duplicated rather than
// imported for the same reason internal/identity's githubSyncPayload
// mirrors this package's: the job payload is the only channel between the
// API and the worker (internal/README.md), so the two sides share a JSON
// contract, not a Go type.
type githubImportPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	RepoID         string `json:"repo_id"`
	InstallationID int64  `json:"installation_id"`
}

// githubImportCheckpoint is what a resumed github.import_repo job reads to
// avoid redoing the fetch: empty before FinalizeImport has queued
// import.parse, then the import and child job ids while this job waits for
// it — the same shape repoCheckpoint uses for live.repo's own parse stage.
type githubImportCheckpoint struct {
	ImportID   string `json:"import_id,omitempty"`
	ChildJobID string `json:"child_job_id,omitempty"`
}

// GitHubImportWorker runs github.import_repo. gh nil (the GitHub App not
// configured) is the same named, valid deployment state live.repo and
// github.sync_repositories already use — every job ends worker.Skipped
// with live.ErrorGitHubNotWired, never retried.
type GitHubImportWorker struct {
	pool  *pgxpool.Pool
	gh    *ghapp.Client
	imp   *importer.Service
	queue *jobs.Queue
	// PollInterval overrides defaultLiveRepoPollInterval, mainly for tests
	// that want the wait loop to turn over in milliseconds rather than
	// seconds.
	PollInterval time.Duration
}

// NewGitHubImportWorker wires the handler over the same importer seam
// live.repo drives (CreateImport/PutBlob/FinalizeImport).
func NewGitHubImportWorker(pool *pgxpool.Pool, gh *ghapp.Client, imp *importer.Service) *GitHubImportWorker {
	return &GitHubImportWorker{pool: pool, gh: gh, imp: imp, queue: jobs.New(pool)}
}

// Handlers maps the job kind this worker runs.
func (w *GitHubImportWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindGitHubImportRepo: w.Run}
}

func (w *GitHubImportWorker) pollInterval() time.Duration {
	if w.PollInterval > 0 {
		return w.PollInterval
	}
	return defaultLiveRepoPollInterval
}

// Run executes one github.import_repo job: fetch, then wait for the
// import.parse it queues, resuming from the checkpoint when this job has
// already reached that stage on an earlier attempt.
func (w *GitHubImportWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload githubImportPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode github.import_repo payload: %w", e))
	}
	if payload.SchemaVersion != githubImportPayloadVersion || payload.OrgID != t.Job.OrgID ||
		payload.RepoID == "" || payload.InstallationID == 0 {
		return worker.Permanent(errors.New("github.import_repo payload does not match its job row"))
	}
	if w.gh == nil {
		return worker.Skipped(live.ErrorGitHubNotWired)
	}

	var cp githubImportCheckpoint
	_ = json.Unmarshal(t.Job.Checkpoint, &cp)

	if cp.ChildJobID == "" {
		var gitHostURL string
		e := w.pool.QueryRow(ctx, `SELECT git_host_url FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2 AND github_installation_id=$3`,
			payload.OrgID, payload.RepoID, payload.InstallationID).Scan(&gitHostURL)
		if errors.Is(e, pgx.ErrNoRows) {
			return worker.Permanent(fmt.Errorf("github.import_repo: repository %s is not linked to installation %d",
				payload.RepoID, payload.InstallationID))
		}
		if e != nil {
			return e
		}
		fullName, ok := fullNameFromGitHostURL(gitHostURL)
		if !ok {
			return worker.Permanent(fmt.Errorf("github.import_repo: repository %s has no github.com git_host_url", payload.RepoID))
		}

		result, ferr := fetchRepositoryImport(ctx, w.pool, w.gh, w.imp, payload.InstallationID, fullName,
			payload.OrgID, payload.RepoID, "github.import_repo", t.Job.JobID, decodeLimits(t.Job.Limits))
		switch {
		case errors.Is(ferr, errGuidefoldYAMLMissing):
			if e := setImportBlockedReason(ctx, w.pool, t, payload.OrgID, payload.RepoID, live.ErrorGuidefoldYAMLMissing); e != nil {
				return e
			}
			return worker.Skipped(live.ErrorGuidefoldYAMLMissing)
		case errors.Is(ferr, ghapp.ErrTreeTruncated), errors.Is(ferr, ghapp.ErrInstallationNotFound):
			return worker.Permanent(ferr)
		case ferr != nil:
			return ferr // transient: the queue's own backoff retries it
		}
		// A repository that once had no guidefold.yaml and now does must not
		// keep reading blocked forever: this attempt actually reached
		// CreateImport, so whatever the column held before is stale.
		if e := setImportBlockedReason(ctx, w.pool, t, payload.OrgID, payload.RepoID, ""); e != nil {
			return e
		}
		cp = githubImportCheckpoint{ImportID: result.ImportID, ChildJobID: result.ParseJobID}
		if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
			return e
		}
	}

	job, e := waitForChildJob(ctx, w.queue, t, w.pollInterval(), payload.OrgID, cp.ChildJobID)
	if e != nil {
		return e
	}
	if job.State != jobs.StateDone {
		return worker.Permanent(fmt.Errorf("github.import_repo: import.parse %s ended %s: %s",
			cp.ChildJobID, job.State, job.Error))
	}
	t.Result = mustJSON(map[string]any{"import_id": cp.ImportID})
	return nil
}

// setImportBlockedReason writes gfm.repos.import_blocked_reason (API-CONTRACT
// §5.2/§7, 1.13.0): reason "" clears it back to NULL. Fenced first, the same
// rule live.repo's own target writes follow: a job whose lease already moved
// on when it was leased again elsewhere must write nothing.
func setImportBlockedReason(ctx context.Context, pool *pgxpool.Pool, t *worker.Task, orgID, repoID, reason string) error {
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := fenceJob(ctx, tx, t); e != nil {
		return e
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.repos SET import_blocked_reason=$3 WHERE org_id=$1::uuid AND repo_id=$2`,
		orgID, repoID, nullable(reason)); e != nil {
		return e
	}
	return tx.Commit(ctx)
}
