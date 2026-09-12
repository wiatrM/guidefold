package agentrun

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/model"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// KindPRReport is the job kind ADR-0036 points 1, 1a name for the coverage
// bot's own report. It is defined here, not in internal/review (where the
// ADR text says the job "lives"), because this task's file boundary does
// not include editing that package; RegisterHandlers in worker_handlers.go
// is where it is wired into gfm.jobs.kind.
const KindPRReport = "pr.report"

const prReportPayloadVersion = "pr.report-1"

// reasonGitHubNotConfigured mirrors live.ErrorGitHubNotWired's exact text
// without importing internal/live for it — pr.report never touches a live
// run and has no other reason to depend on that package.
const reasonGitHubNotConfigured = "github_app_not_configured"

// ascendPayloadVersion is this package's own guess at ascend.run's payload
// version: API-CONTRACT §8 names the job's input fields but not a
// schema_version literal, and ascend.run's own handler (worker_handlers.go,
// pre-existing) does not check one yet. It is carried anyway, so a future
// real ascend.run implementation has something to validate against rather
// than inheriting an unversioned payload from its first caller.
const ascendPayloadVersion = "ascend.run-1"

type prReportPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	InstallationID int64  `json:"installation_id"`
	RepoID         string `json:"repo_id"`
	FullName       string `json:"full_name,omitempty"`
	PRNumber       int    `json:"pr_number"`
	HeadSHA        string `json:"head_sha"`
	BaseRef        string `json:"base_ref"`
}

// PRReportWorker runs pr.report.
type PRReportWorker struct {
	pool     *pgxpool.Pool
	gh       *ghapp.Client
	keyring  *secrets.Keyring
	env      func(string) string
	queue    *jobs.Queue
	newModel func(provider string, env func(string) string) (model.Client, error)
}

// NewPRReportWorker wires the handler. gh and ghCfg must agree: both set
// when the deployment has the GitHub App configured, both zero/nil
// otherwise — the same "not wired yet" state ADR-0036 point 5 names for the
// worker's network path.
func NewPRReportWorker(pool *pgxpool.Pool, gh *ghapp.Client, ghCfg ghapp.Config, keyring *secrets.Keyring,
	env func(string) string) *PRReportWorker {
	w := &PRReportWorker{pool: pool, gh: gh, keyring: keyring, env: env, queue: jobs.New(pool), newModel: model.New}
	if gh != nil {
	}
	return w
}

// Handlers maps the job kind this worker runs.
func (w *PRReportWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindPRReport: w.Run}
}

// Run executes one pr.report job.
func (w *PRReportWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload prReportPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode pr.report payload: %w", e))
	}
	if payload.SchemaVersion != prReportPayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported pr.report payload schema_version %q", payload.SchemaVersion))
	}
	if payload.OrgID != t.Job.OrgID || payload.RepoID == "" || payload.PRNumber == 0 {
		return worker.Permanent(errors.New("pr.report payload does not match its job row"))
	}
	if w.gh == nil {
		return worker.Skipped(reasonGitHubNotConfigured)
	}

	fullName := payload.FullName
	if fullName == "" {
		var gitHostURL string
		if e := w.pool.QueryRow(ctx, `SELECT git_host_url FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, payload.OrgID, payload.RepoID).Scan(&gitHostURL); e != nil {
			return worker.Permanent(fmt.Errorf("pr.report: no such repository %s: %w", payload.RepoID, e))
		}
		resolved, ok := fullNameFromGitHostURL(gitHostURL)
		if !ok {
			return worker.Permanent(fmt.Errorf("pr.report: %s has no resolvable GitHub full name", payload.RepoID))
		}
		fullName = resolved
	}

	changed, e := w.gh.ListPullRequestFiles(ctx, payload.InstallationID, fullName, payload.PRNumber)
	if errors.Is(e, ghapp.ErrInstallationNotFound) {
		return worker.Permanent(fmt.Errorf("pr.report: %w", e))
	}
	if e != nil {
		return fmt.Errorf("pr.report: list changed files: %w", e)
	}
	paths := make([]string, 0, len(changed))
	skillFileChanged := false
	for _, f := range changed {
		paths = append(paths, f.Path)
		if looksLikeSkillFile(f.Path) {
			skillFileChanged = true
		}
	}

	rules, e := applicableRules(ctx, w.pool, payload.OrgID, payload.RepoID, paths)
	if e != nil {
		return fmt.Errorf("pr.report: resolve applicable rules: %w", e)
	}

	comment := prComment{rules: rules}
	comment.judgement, comment.judgementNote = w.judge(ctx, payload.OrgID, rules, changed)

	// The comment is upserted before this job reaches any terminal return —
	// including the two ADR-0036 point 4a paths that end the job itself
	// skipped or failed — because a return that happened first would leave
	// the pull request with no comment at all for exactly the two cases a
	// human most needs to see one.
	if e := w.gh.UpsertStickyComment(ctx, payload.InstallationID, fullName, payload.PRNumber, comment.render()); e != nil {
		if errors.Is(e, ghapp.ErrPermissionRefused) {
			return worker.Permanent(fmt.Errorf("pr.report: %w", e))
		}
		return fmt.Errorf("pr.report: upsert the sticky comment: %w", e)
	}

	if skillFileChanged {
		if e := w.enqueueAscend(ctx, payload, paths); e != nil {
			return e
		}
	}

	if comment.judgementNote == prJudgementNoteQuotaExhausted {
		// A quota failure is never retried on a backoff: an attempt against
		// an exhausted account produces charges on someone else's bill and
		// no output (ADR-0036 point 4a). The string is exactly
		// "model_quota_exhausted" — API-CONTRACT §5.5a's own spelling — with
		// nothing wrapped around it, so gfm.jobs.error matches the contract
		// byte for byte.
		return worker.Permanent(errors.New(reasonModelQuotaExhausted))
	}
	if comment.judgementNote == prJudgementNoteCredentialMissing {
		return worker.Skipped(reasonModelCredentialMissing)
	}
	if comment.judgementNote == prJudgementNoteSecretUnavailable {
		return worker.Skipped(reasonSecretUnavailable)
	}
	if comment.judgementNote == prJudgementNotePermanentError {
		return worker.Permanent(errors.New(comment.judgement))
	}
	if comment.judgementNote == prJudgementNoteTransientError {
		return errors.New(comment.judgement)
	}

	t.Result = mustJSON(map[string]any{"rules": len(rules), "changed_files": len(paths),
		"skill_files_changed": skillFileChanged})
	return nil
}

// judgement notes classify why comment.judgement holds what it holds, so
// Run can decide the job's own terminal state from the same value the
// comment already carries, rather than recomputing the classification a
// second time.
const (
	prJudgementNoteOK                = ""
	prJudgementNoteCredentialMissing = "credential_missing"
	prJudgementNoteSecretUnavailable = "secret_unavailable"
	prJudgementNoteQuotaExhausted    = "quota_exhausted"
	prJudgementNotePermanentError    = "permanent_error"
	prJudgementNoteTransientError    = "transient_error"
)

// judge asks the model whether the diff contradicts one of the applicable
// rules. It never returns an error: every failure mode becomes a note in
// the comment and a classification Run turns into the job's own terminal
// state, because ADR-0036 point 4a requires the comment to exist and say
// why, not merely for the job to fail quietly with a reason nobody reads.
func (w *PRReportWorker) judge(ctx context.Context, orgID string, rules []rule, changed []ghapp.ChangedFile) (text, note string) {
	if len(rules) == 0 {
		return "No published rule applies to the paths this pull request touches.", prJudgementNoteOK
	}
	var provider string
	if e := w.pool.QueryRow(ctx, `SELECT provider FROM gfm.org_credentials
 WHERE org_id=$1::uuid ORDER BY provider LIMIT 1`, orgID).Scan(&provider); errors.Is(e, pgx.ErrNoRows) {
		return "The promotion half of this report did not run: this organisation has no model key " +
			"configured. Add one on the credentials screen to enable it.", prJudgementNoteCredentialMissing
	} else if e != nil {
		return "The promotion half of this report did not run: could not read the organisation's " +
			"credentials.", prJudgementNoteTransientError
	}

	apiKey, e := secrets.OpenFor(ctx, w.pool, w.keyring, orgID, provider)
	switch {
	case errors.Is(e, secrets.ErrNoCredential):
		return "The promotion half of this report did not run: this organisation has no model key " +
			"configured. Add one on the credentials screen to enable it.", prJudgementNoteCredentialMissing
	case errors.Is(e, secrets.ErrNoKeyring):
		return "The promotion half of this report did not run: this deployment cannot open stored " +
			"model keys right now.", prJudgementNoteSecretUnavailable
	case e != nil:
		return "The promotion half of this report did not run: could not open the organisation's " +
			"model key.", prJudgementNoteTransientError
	}

	client, e := w.newModel(provider, w.env)
	if e != nil {
		return "The promotion half of this report did not run: no client is available for provider " +
			provider + ".", prJudgementNotePermanentError
	}

	req := model.Request{APIKey: apiKey, Model: defaultJudgeModel(provider), System: judgeSystemPrompt(),
		Messages:        []model.Message{{Role: model.RoleUser, Content: judgePrompt(rules, changed)}},
		MaxOutputTokens: DefaultMaxOutputTokens}
	var buf strings.Builder
	_, e = client.Stream(ctx, req, func(text string) { buf.WriteString(text) })
	switch {
	case errors.Is(e, model.ErrQuotaExhausted):
		return "The promotion half of this report did not run: the model key for " + provider +
			" is out of budget.", prJudgementNoteQuotaExhausted
	case errors.Is(e, model.ErrUnauthorized):
		return "The promotion half of this report did not run: the model key for " + provider +
			" was rejected.", prJudgementNotePermanentError
	case errors.Is(e, model.ErrModelNotAvailable):
		return "The promotion half of this report did not run: " + provider +
			" does not know the configured model.", prJudgementNotePermanentError
	case e != nil:
		return "The promotion half of this report did not run: the model call failed and will be " +
			"retried.", prJudgementNoteTransientError
	}
	text = strings.TrimSpace(buf.String())
	if text == "" {
		text = "The model returned no answer."
	}
	return text, prJudgementNoteOK
}

// defaultJudgeModel is this package's own default when nothing more
// specific is configured — pr.report has no per-run model choice the way a
// Live Agent run does (§4.9's create body), so it needs one of its own.
// Same judgment call live.go's own defaultModel map documents for the
// equivalent gap there.
func defaultJudgeModel(provider string) string {
	switch provider {
	case model.ProviderAnthropic:
		return "claude-3-5-sonnet-latest"
	case model.ProviderOpenAI:
		return "gpt-4o-mini"
	default:
		return "openrouter/auto"
	}
}

func judgeSystemPrompt() string {
	return "You review one pull request's diff against a short list of an organisation's own " +
		"engineering rules. Answer in a few sentences: say plainly whether the diff appears to " +
		"contradict any rule, and if so which one and why. If nothing contradicts, say so plainly. " +
		"Do not propose a code change; only rules published as skill files may change, through a " +
		"separate process."
}

func judgePrompt(rules []rule, changed []ghapp.ChangedFile) string {
	var b strings.Builder
	b.WriteString("Rules that apply to this pull request's changed paths:\n")
	for _, r := range rules {
		fmt.Fprintf(&b, "\n=== [%s] %s ===\n%s\n", r.Scope, r.Name, r.Body)
	}
	b.WriteString("\nChanged files and their diff:\n")
	for _, f := range changed {
		if f.Patch == "" {
			fmt.Fprintf(&b, "\n=== %s (no diff available) ===\n", f.Path)
			continue
		}
		fmt.Fprintf(&b, "\n=== %s ===\n%s\n", f.Path, f.Patch)
	}
	return b.String()
}

// prComment renders the sticky comment. The rules section is always
// present — the deterministic half ADR-0036 point 4a requires even when the
// promotion half could not run.
type prComment struct {
	rules         []rule
	judgement     string
	judgementNote string
}

func (c prComment) render() string {
	var b strings.Builder
	b.WriteString("## Guidefold coverage report\n\n")
	if len(c.rules) == 0 {
		b.WriteString("No published rule applies to the paths this pull request touches.\n\n")
	} else {
		b.WriteString("**Rules that apply to this pull request:**\n\n")
		for _, r := range c.rules {
			fmt.Fprintf(&b, "- `%s` **%s** — %s\n", r.Scope, r.Name, r.Description)
		}
		b.WriteString("\n")
	}
	b.WriteString("**Does this diff contradict an organisation rule?**\n\n")
	b.WriteString(c.judgement)
	b.WriteString("\n")
	return b.String()
}

// enqueueAscend queues ascend.run once a pull request's diff has touched a
// skill file — the coverage bot's own promotion path (ADR-0036 point 1).
// The idempotency key mirrors the webhook's own naming for pr.report jobs
// (ADR-0036 point 1: "pr:<installation_id>:<pr_number>:<head_sha>"), so a
// retried pr.report attempt enqueues the same ascend.run job rather than a
// second one.
func (w *PRReportWorker) enqueueAscend(ctx context.Context, payload prReportPayload, changedPaths []string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	body := mustJSON(map[string]any{
		"schema_version":  ascendPayloadVersion,
		"org_id":          payload.OrgID,
		"repo_id":         payload.RepoID,
		"installation_id": payload.InstallationID,
		"pr_number":       payload.PRNumber,
		"head_sha":        payload.HeadSHA,
		"base_ref":        payload.BaseRef,
		"changed_paths":   changedPaths,
	})
	job := jobs.Job{OrgID: payload.OrgID, RepoID: payload.RepoID, Kind: "ascend.run", Payload: body,
		InputDigest:    payload.HeadSHA,
		IdempotencyKey: "ascend:" + strconv.FormatInt(payload.InstallationID, 10) + ":" + strconv.Itoa(payload.PRNumber) + ":" + payload.HeadSHA}
	if _, e := w.queue.Enqueue(ctx, tx, job); e != nil {
		return e
	}
	return tx.Commit(ctx)
}
