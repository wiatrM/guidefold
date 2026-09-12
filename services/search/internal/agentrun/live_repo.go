package agentrun

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/model"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// Named reasons this handler writes to a target's `error` column or a run's
// `error` column, beyond the ones internal/live already exports for its own
// use. Their exact spelling follows API-CONTRACT §5.5a's prose everywhere
// that prose names one (model_credential_missing, model_quota_exhausted,
// model_not_available is even quoted verbatim in internal/live's own
// defaultModel comment); the handful with no contract wording
// (model_credential_invalid, repository_tree_truncated) are this package's
// own judgment call, kept in the same shape as the rest so a console that
// does not special-case them still shows a readable slug.
const (
	reasonModelCredentialMissing = "model_credential_missing"
	reasonModelCredentialInvalid = "model_credential_invalid"
	reasonSecretUnavailable      = "secret_encryption_unavailable"
	reasonModelQuotaExhausted    = "model_quota_exhausted"
	reasonModelNotAvailable      = "model_not_available"
	reasonTreeTruncated          = "repository_tree_truncated"
)

// defaultReadRef is passed to ghapp for every read when a target carries no
// more specific ref. Neither API-CONTRACT §8 nor ADR-0046 names which
// commit a live run reads a repository at; "HEAD" — the repository's
// default branch — is this package's own judgment call for "the current
// state of the organisation's repositories" ADR-0046's own context section
// asks for.
const defaultReadRef = "HEAD"

// LiveRepoWorker runs live.repo: ADR-0046 points 2, 4, 5 for one repository.
type LiveRepoWorker struct {
	pool    *pgxpool.Pool
	gh      *ghapp.Client // nil means the deployment has not wired the GitHub App network path (ADR-0046 consequences).
	keyring *secrets.Keyring
	env     func(string) string
	// newModel builds the provider client. A field, not a direct call to
	// model.New, so a test can substitute a fake without an httptest server
	// per provider.
	newModel func(provider string, env func(string) string) (model.Client, error)
}

// NewLiveRepoWorker wires the handler. gh may be nil — that is a valid,
// named deployment state (ADR-0046 consequences: "the worker's NetworkPolicy
// needs egress to the OpenRouter endpoint in addition to GitHub; until that
// exists, live.repo terminates skipped with a named reason"), not a
// programming error to guard against with a panic.
func NewLiveRepoWorker(pool *pgxpool.Pool, gh *ghapp.Client, keyring *secrets.Keyring, env func(string) string) *LiveRepoWorker {
	return &LiveRepoWorker{pool: pool, gh: gh, keyring: keyring, env: env, newModel: model.New}
}

// Handlers maps the job kind this worker runs.
func (w *LiveRepoWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{live.KindRepo: w.Run}
}

type repoCheckpoint struct {
	LastPath string `json:"last_path"`
}

// Run executes one live.repo job: one repository of one run.
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
		_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, live.ErrorGitHubNotWired)
		return worker.Skipped(live.ErrorGitHubNotWired)
	}

	run, e := w.loadRun(ctx, payload.OrgID, payload.RunID)
	if e != nil {
		return e
	}

	apiKey, e := secrets.OpenFor(ctx, w.pool, w.keyring, payload.OrgID, run.provider)
	switch {
	case errors.Is(e, secrets.ErrNoCredential):
		_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, reasonModelCredentialMissing)
		return worker.Skipped(reasonModelCredentialMissing)
	case errors.Is(e, secrets.ErrNoKeyring):
		_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, reasonSecretUnavailable)
		return worker.Skipped(reasonSecretUnavailable)
	case e != nil:
		return fmt.Errorf("open the organisation's %s credential: %w", run.provider, e)
	}
	// apiKey lives only in this function's stack from here on: it travels on
	// model.Request for one call at a time and is never assigned to a field
	// this handler logs, checkpoints or returns (ADR-0045 point 3).

	modelClient, e := w.newModel(run.provider, w.env)
	if e != nil {
		return worker.Permanent(fmt.Errorf("build a client for provider %q: %w", run.provider, e))
	}

	if e := w.startTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID); e != nil {
		return e
	}

	files, e := w.gh.ListSkillFiles(ctx, payload.InstallationID, payload.FullName, defaultReadRef)
	switch {
	case errors.Is(e, ghapp.ErrTreeTruncated):
		_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, reasonTreeTruncated)
		return worker.Permanent(e)
	case errors.Is(e, ghapp.ErrInstallationNotFound):
		_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, live.ErrorGitHubNotWired)
		return worker.Permanent(e)
	case e != nil:
		if w.outOfAttempts(t) {
			_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, live.ErrorProviderDown)
		}
		return e
	}
	sort.Strings(files)
	truncated := false
	if limits.MaxFiles > 0 && len(files) > limits.MaxFiles {
		files, truncated = files[:limits.MaxFiles], true
	}
	findings := 0
	if truncated {
		if e := w.appendFinding(ctx, payload.OrgID, payload.RunID, payload.RepoID, "", fmt.Sprintf(
			"Only the first %d of the repository's files were scanned; the rest were not read (max_files limit).",
			limits.MaxFiles), "warn"); e != nil {
			return e
		}
		findings++
	}

	var cp repoCheckpoint
	_ = json.Unmarshal(t.Job.Checkpoint, &cp)
	resumeIndex := 0
	if cp.LastPath != "" {
		for i, p := range files {
			if p == cp.LastPath {
				resumeIndex = i + 1
				break
			}
		}
	}

	stopReason := ""
	scanned := 0
	for i := resumeIndex; i < len(files); i++ {
		// Cancellation is checked at each checkpoint boundary, not once at
		// the end of the repository (ADR-0046 point 7): a run an owner
		// stopped a minute ago must not still be reading files a minute
		// from now.
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if exceeded, e := w.budgetExceeded(ctx, payload.OrgID, payload.RunID, limits); e != nil {
			return e
		} else if exceeded {
			stopReason = live.ErrorBudgetExhausted
			break
		}

		path := files[i]
		content, e := w.gh.ReadFile(ctx, payload.InstallationID, payload.FullName, defaultReadRef, path)
		if errors.Is(e, ghapp.ErrFileTooLarge) {
			// One oversize file is skipped, not fatal to the repository: the
			// rest of the scan is still evidence worth keeping.
			if e := t.Checkpoint(ctx, mustJSON(repoCheckpoint{LastPath: path})); e != nil {
				return e
			}
			continue
		}
		if e != nil {
			if w.outOfAttempts(t) {
				_ = w.failTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, live.ErrorProviderDown)
			}
			return e
		}

		found, usage, e := w.scanFile(ctx, modelClient, apiKey, run, limits, payload, path, string(content))
		if e != nil {
			return w.handleModelError(ctx, t, payload.OrgID, payload.RunID, payload.RepoID, e)
		}
		findings += found
		if e := w.addCost(ctx, payload.OrgID, payload.RunID, usage); e != nil {
			return e
		}
		if e := t.Checkpoint(ctx, mustJSON(repoCheckpoint{LastPath: path})); e != nil {
			return e
		}
		scanned++
	}

	if e := w.finishTarget(ctx, payload.OrgID, payload.RunID, payload.RepoID, findings, stopReason); e != nil {
		return e
	}
	t.Result = mustJSON(map[string]any{"files_scanned": scanned, "files_total": len(files),
		"findings": findings, "stopped": stopReason})
	return nil
}

// outOfAttempts reports whether this is the job's last permitted attempt.
// A transient failure on an earlier attempt is left for the queue's own
// backoff; on the last one, the target row must be finalised here, because
// nothing else will ever run for this repository once the job itself ends
// failed.
func (w *LiveRepoWorker) outOfAttempts(t *worker.Task) bool {
	return t.Job.MaxAttempts > 0 && t.Job.Attempts >= t.Job.MaxAttempts
}

type runRow struct {
	provider, model, prompt string
}

func (w *LiveRepoWorker) loadRun(ctx context.Context, orgID, runID string) (runRow, error) {
	var r runRow
	e := w.pool.QueryRow(ctx, `SELECT provider, model, prompt FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID).Scan(&r.provider, &r.model, &r.prompt)
	if errors.Is(e, pgx.ErrNoRows) {
		return runRow{}, worker.Permanent(fmt.Errorf("live.repo: no such run %s", runID))
	}
	return r, e
}

func (w *LiveRepoWorker) startTarget(ctx context.Context, orgID, runID, repoID string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := live.SetTargetState(ctx, tx, orgID, runID, repoID, live.TargetRunning, ""); e != nil {
		return e
	}
	if _, e := live.Append(ctx, tx, orgID, runID, repoID, live.EventRepoStarted, map[string]any{}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// finishTarget writes the target's terminal state and findings count,
// appends repo.finished, and ends the run when this was the last target
// still in flight (helpers.go's maybeFinishRun).
func (w *LiveRepoWorker) finishTarget(ctx context.Context, orgID, runID, repoID string, findings int, stopReason string) error {
	state, errText := live.TargetDone, ""
	if stopReason != "" {
		state, errText = live.TargetFailed, stopReason
	}
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if e := live.SetTargetState(ctx, tx, orgID, runID, repoID, state, errText); e != nil {
		return e
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.live_run_targets SET findings=$4
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND repo_id=$3`, orgID, runID, repoID, findings); e != nil {
		return e
	}
	payload := map[string]any{"findings": findings}
	if stopReason != "" {
		payload["error"] = stopReason
	}
	if _, e := live.Append(ctx, tx, orgID, runID, repoID, live.EventRepoFinished, payload); e != nil {
		return e
	}
	if e := maybeFinishRun(ctx, tx, orgID, runID); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// failTarget is the best-effort path used from error branches that must not
// let a secondary write failure mask the error already being returned: its
// own error is deliberately swallowed by every caller.
func (w *LiveRepoWorker) failTarget(ctx context.Context, orgID, runID, repoID, reason string) error {
	return w.finishTarget(ctx, orgID, runID, repoID, 0, reason)
}

func (w *LiveRepoWorker) appendFinding(ctx context.Context, orgID, runID, repoID, path, summary, severity string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, e := live.Append(ctx, tx, orgID, runID, repoID, live.EventFinding,
		map[string]any{"path": nullable(path), "summary": summary, "severity": severity}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// findingMarker is the convention this package's own system prompt asks the
// model to use so a free-running narration can still surface a small number
// of structured findings — the one event type the UI shows outside the
// transcript (API-CONTRACT §5.5a). Nothing in the contract or either ADR
// specifies a wire format for what the model returns to live.repo (unlike
// proposal.generate's strict JSON schema); this line convention is this
// package's own choice, made because a Live Agent run is read as a live
// transcript, not decoded as structured output.
const findingMarker = "FINDING:"

func systemPromptFor(prompt string) string {
	return "You are Guidefold's Live Agent, scanning one connected repository's " +
		"AGENTS.md and SKILL.md files at the operator's request. Operator's request: " + prompt +
		"\n\nYou will be shown one file at a time. Narrate what you notice about it in plain " +
		"prose. When something is concretely worth flagging to the operator — a gap, a " +
		"contradiction, a stale instruction — put it on its own line starting with exactly " +
		"\"" + findingMarker + " info \" or \"" + findingMarker + " warn \" followed by one " +
		"sentence. Everything else is narration only and is not treated as a finding."
}

// scanFile calls the model once over one file's content and returns how
// many findings it reported plus the call's usage. Deltas are batched into
// model.delta events as they arrive (delta_batch.go); findings are parsed
// from the full response once streaming ends, because a marker line could
// itself be split across two delta chunks.
func (w *LiveRepoWorker) scanFile(ctx context.Context, client model.Client, apiKey string, run runRow,
	limits Limits, payload liveRepoPayload, path, content string) (int, model.Usage, error) {
	var full strings.Builder
	batcher := newDeltaBatcher(func(text string) error {
		return w.appendModelDelta(ctx, payload.OrgID, payload.RunID, payload.RepoID, text)
	})
	onDelta := func(text string) {
		full.WriteString(text)
		batcher.onDelta(text)
	}
	req := model.Request{APIKey: apiKey, Model: run.model, System: systemPromptFor(run.prompt),
		Messages:        []model.Message{{Role: model.RoleUser, Content: "File: " + path + "\n\n" + content}},
		MaxInputTokens:  limits.MaxTokens,
		MaxOutputTokens: limits.MaxOutputTokens}
	usage, e := client.Stream(ctx, req, onDelta)
	if flushErr := batcher.done(); e == nil {
		e = flushErr
	}
	if e != nil {
		return 0, usage, e
	}
	findings, e := w.emitFindings(ctx, payload.OrgID, payload.RunID, payload.RepoID, path, full.String())
	return findings, usage, e
}

func (w *LiveRepoWorker) appendModelDelta(ctx context.Context, orgID, runID, repoID, text string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	// Append's own 20,000-event cap drops a model.delta and returns (0, nil)
	// rather than an error once reached — that is not a failure this
	// package should surface as one; the run keeps going and its structured
	// events keep flowing.
	if _, e := live.Append(ctx, tx, orgID, runID, repoID, live.EventModelDelta, map[string]any{"text": text}); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

func (w *LiveRepoWorker) emitFindings(ctx context.Context, orgID, runID, repoID, path, fullText string) (int, error) {
	count := 0
	for _, line := range strings.Split(fullText, "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, findingMarker) {
			continue
		}
		rest := strings.TrimSpace(strings.TrimPrefix(line, findingMarker))
		severity := "info"
		if strings.HasPrefix(rest, "warn ") {
			severity, rest = "warn", strings.TrimSpace(strings.TrimPrefix(rest, "warn "))
		} else if strings.HasPrefix(rest, "info ") {
			rest = strings.TrimSpace(strings.TrimPrefix(rest, "info "))
		}
		if rest == "" {
			continue
		}
		if e := w.appendFinding(ctx, orgID, runID, repoID, path, rest, severity); e != nil {
			return count, e
		}
		count++
	}
	return count, nil
}

// budgetExceeded is a cheap, unlocked pre-check against the run's
// accumulated spend: several live.repo jobs read it concurrently, so it can
// be stale by one in-flight call, but that only ever means a run stops one
// call later than its ceiling, never one call short of it — addCost is
// where the number that matters is written, under the run row's lock.
func (w *LiveRepoWorker) budgetExceeded(ctx context.Context, orgID, runID string, limits Limits) (bool, error) {
	if limits.MaxUSD <= 0 {
		return false, nil
	}
	var raw []byte
	if e := w.pool.QueryRow(ctx, `SELECT cost::text FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID).Scan(&raw); e != nil {
		return false, e
	}
	var cost struct {
		USD float64 `json:"usd"`
	}
	_ = json.Unmarshal(raw, &cost)
	return cost.USD >= limits.MaxUSD, nil
}

// usdPerMillionTokens reads this package's own price configuration. Unset
// (the default) means a deployment has not named a price, and every call's
// dollar contribution is then 0 — the same choice
// internal/review/generator/remote.go makes for its own unpriced case,
// rather than inventing a number that would be presented as measured.
func (w *LiveRepoWorker) usdPerMillionTokens() (in, out float64) {
	return envFloat(w.env, "GUIDEFOLD_LIVE_USD_PER_MTOK_IN"), envFloat(w.env, "GUIDEFOLD_LIVE_USD_PER_MTOK_OUT")
}

// addCost folds one call's usage into the run's cumulative cost under the
// run row's own lock, so two live.repo jobs adding at the same instant
// still sum correctly. usd_estimated is OR-ed in, never overwritten: one
// call anywhere in the run that had to be estimated keeps the whole run's
// figure honest as an estimate (ADR-0046 §5).
func (w *LiveRepoWorker) addCost(ctx context.Context, orgID, runID string, usage model.Usage) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	var raw []byte
	if e := tx.QueryRow(ctx, `SELECT cost::text FROM gfm.live_runs
 WHERE org_id=$1::uuid AND run_id=$2::uuid FOR UPDATE`, orgID, runID).Scan(&raw); e != nil {
		return e
	}
	var cost struct {
		TokensIn     int64   `json:"tokens_in"`
		TokensOut    int64   `json:"tokens_out"`
		USD          float64 `json:"usd"`
		USDEstimated bool    `json:"usd_estimated"`
	}
	_ = json.Unmarshal(raw, &cost)
	inRate, outRate := w.usdPerMillionTokens()
	cost.TokensIn += int64(usage.TokensIn)
	cost.TokensOut += int64(usage.TokensOut)
	cost.USD += float64(usage.TokensIn)*inRate/1e6 + float64(usage.TokensOut)*outRate/1e6
	cost.USDEstimated = cost.USDEstimated || usage.Estimated
	if _, e := tx.Exec(ctx, `UPDATE gfm.live_runs SET cost=$3::jsonb
 WHERE org_id=$1::uuid AND run_id=$2::uuid`, orgID, runID, string(mustJSON(cost))); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// handleModelError turns one failed model call into either a retryable
// error (rate limits and anything unclassified, subject to the job's own
// backoff) or a terminal one, finalising the target row exactly when the
// job itself will not run again for this repository — on the last
// permitted attempt, or immediately for a failure retrying cannot fix.
func (w *LiveRepoWorker) handleModelError(ctx context.Context, t *worker.Task, orgID, runID, repoID string, e error) error {
	switch {
	case errors.Is(e, model.ErrQuotaExhausted):
		_ = w.failTarget(ctx, orgID, runID, repoID, reasonModelQuotaExhausted)
		return worker.Permanent(e)
	case errors.Is(e, model.ErrModelNotAvailable):
		_ = w.failTarget(ctx, orgID, runID, repoID, reasonModelNotAvailable)
		return worker.Permanent(e)
	case errors.Is(e, model.ErrUnauthorized):
		_ = w.failTarget(ctx, orgID, runID, repoID, reasonModelCredentialInvalid)
		return worker.Permanent(e)
	default:
		// model.ErrRateLimited and anything this package did not name a
		// branch for both get the same treatment: retry through the queue's
		// own backoff, and finalise the target only once no attempt is left.
		if w.outOfAttempts(t) {
			_ = w.failTarget(ctx, orgID, runID, repoID, live.ErrorProviderDown)
		}
		return e
	}
}

func envFloat(env func(string) string, name string) float64 {
	if env == nil {
		return 0
	}
	v := strings.TrimSpace(env(name))
	if v == "" {
		return 0
	}
	var f float64
	if _, e := fmt.Sscanf(v, "%g", &f); e != nil || f < 0 {
		return 0
	}
	return f
}
