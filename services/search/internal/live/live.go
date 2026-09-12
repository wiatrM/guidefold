// Package live is the API half of the Live Agent (ADR-0046): an owner-started,
// on-demand run across every connected repository, watched through an
// append-only event log rather than a streaming transport.
//
// It owns gfm.live_runs, gfm.live_run_targets and gfm.live_run_events, and the
// live.plan job every run fans out through. live.repo — the per-repository
// worker job that actually reads a repository and calls the model — belongs
// to the worker, not to this package: this package only ever enqueues
// live.plan, and reads the target and event rows the worker writes. It never
// opens the organisation's model key; Append, SetTargetState and Finish are
// the surface the worker calls to make its progress visible, and the key
// itself never appears in a run row, an event payload, a job payload or an
// error (ADR-0045, ADR-0046 §5).
package live

import (
	"context"
	"errors"
	"regexp"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

// Run states (API-CONTRACT §7 gfm.live_runs CHECK, §5.5a LiveRun.state).
const (
	StateQueued    = "queued"
	StateRunning   = "running"
	StateSucceeded = "succeeded"
	StatePartial   = "partial"
	StateFailed    = "failed"
	StateCancelled = "cancelled"
)

// activeStates are the two states the one-active-run-per-organisation index
// (gfm.live_runs_one_active) and live_run_already_active both mean.
var activeStates = []string{StateQueued, StateRunning}

// terminalStates are the four states GET .../events reads to decide `done`:
// a run that has reached one of these will never append another event.
func isTerminal(state string) bool {
	switch state {
	case StateSucceeded, StatePartial, StateFailed, StateCancelled:
		return true
	}
	return false
}

// Target states (§7 gfm.live_run_targets CHECK). There is no "cancelled"
// state for a target: one dropped by an owner's cancel is reported skipped,
// with ErrorCancelled as its reason, because that is what happened to it — it
// was never run to a result of its own.
const (
	TargetQueued  = "queued"
	TargetRunning = "running"
	TargetDone    = "done"
	TargetFailed  = "failed"
	TargetSkipped = "skipped"
)

// Event types (§7 gfm.live_run_events CHECK, §5.5a LiveRunEvent.type).
const (
	EventRunStarted   = "run.started"
	EventRepoStarted  = "repo.started"
	EventModelDelta   = "model.delta"
	EventFinding      = "finding"
	EventRepoFinished = "repo.finished"
	EventRunFinished  = "run.finished"
	EventError        = "error"
)

// Named termination reasons LiveRun.error carries (ADR-0046 §5, §7;
// API-CONTRACT §5.5a). model_provider_unavailable and github_app_not_configured
// are the worker's to write; they are named here only so the domain is
// documented in one place.
const (
	ErrorCancelled       = "cancelled_by_owner"
	ErrorBudgetExhausted = "live_run_budget_exhausted"
	ErrorLogTruncated    = "live_run_log_truncated"
	ErrorProviderDown    = "model_provider_unavailable"
	ErrorGitHubNotWired  = "github_app_not_configured"
)

// Job kinds this module reads and writes (API-CONTRACT §8). This package
// enqueues KindPlan only; KindRepo is enqueued by the worker's live.plan
// handler, one per target, and is named here so the cancel path can
// recognise and stop both kinds by the same rule.
const (
	KindPlan = "live.plan"
	KindRepo = "live.repo"
)

// PayloadVersion labels the live.plan payload the same way importer labels
// import.parse: a worker that does not know the version refuses the job
// instead of guessing what the fields mean.
const PayloadVersion = "live.plan-1"

// maxEventsPerRun is the log's ceiling (ADR-0046 "20,000 events", §5.5a).
// Past it, Append drops model.delta and keeps writing every structured event,
// so a model that will not stop talking cannot turn one run into an unbounded
// table.
const maxEventsPerRun = 20000

// defaultEventLimit / maxEventLimit bound one page of .../events (§4.9).
const (
	defaultEventLimit = 200
	maxEventLimit     = 500
)

// maxPromptLen is §3's invalid_prompt bound.
const maxPromptLen = 4000

// defaultModel names what a run uses when the caller does not choose. It is a
// default, not a catalog: which models exist is the provider's business and
// changes weekly, so a list kept here would be wrong within a month and would
// refuse an organisation its own fine-tune. A model this provider does not know
// comes back from the provider itself and ends the run with model_not_available
// (§5.5a), which is the honest place for that answer.
var defaultModel = map[string]string{
	secrets.ProviderOpenRouter: "openrouter/auto",
	secrets.ProviderAnthropic:  "claude-3-5-sonnet-latest",
	secrets.ProviderOpenAI:     "gpt-4o-mini",
}

// modelShape is what a model identifier may look like: providers use slashes,
// dots, colons and dashes, never whitespace. Checking the shape catches a
// pasted sentence at the door; checking a list would catch a legitimate model.
var modelShape = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,119}$`)

// Service holds the live-run endpoints.
type Service struct {
	pool  *pgxpool.Pool
	queue *jobs.Queue
}

// New builds the service over one database. It mints its own job queue, the
// same way every other module with a job to enqueue does.
func New(pool *pgxpool.Pool) *Service {
	return &Service{pool: pool, queue: jobs.New(pool)}
}

// Register mounts the five routes of API-CONTRACT §4.9, no more: starting a
// run spends the organisation's money and is idempotent like every other
// mutation of §3; reading is a member's right; cancelling is real and is not
// idempotent, because a second cancel of an already-terminal run has to
// answer live_run_not_cancellable rather than silently succeed.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle("POST", "/api/v1/orgs/{org}/live/runs", s.handleCreate, mgmt.Idempotent())
	r.Handle("GET", "/api/v1/orgs/{org}/live/runs", s.handleList)
	r.Handle("GET", "/api/v1/orgs/{org}/live/runs/{run_id}", s.handleGet)
	r.Handle("GET", "/api/v1/orgs/{org}/live/runs/{run_id}/events", s.handleEvents)
	r.Handle("POST", "/api/v1/orgs/{org}/live/runs/{run_id}/cancel", s.handleCancel)
}

// validateRun checks the fields §4.9 names for this route and resolves the
// provider and model defaults a caller may omit. An unknown provider is
// invalid_provider, the same code the credential routes use for the same
// mistake; a malformed model identifier is invalid_model. Whether a
// well-formed model actually exists is the provider's answer, not ours.
func validateRun(rawPrompt, rawProvider, rawModel string) (prompt, provider, model string, err error) {
	prompt = strings.TrimSpace(rawPrompt)
	if prompt == "" || len(prompt) > maxPromptLen {
		return "", "", "", mgmt.Invalid("invalid_prompt", "prompt must contain 1 to 4000 characters.")
	}
	provider = strings.TrimSpace(rawProvider)
	if provider == "" {
		// Fixed, not credential-aware: defaulting to whichever provider the
		// organisation happens to have a key for would make
		// model_credential_missing unreachable for an org that holds any key
		// at all.
		provider = secrets.ProviderOpenRouter
	}
	fallback, known := defaultModel[provider]
	if !known {
		return "", "", "", mgmt.Invalid("invalid_provider", "That model provider is not supported.")
	}
	model = strings.TrimSpace(rawModel)
	if model == "" {
		model = fallback
	}
	if !modelShape.MatchString(model) {
		return "", "", "", mgmt.Invalid("invalid_model", "A model identifier has no spaces and is at most 120 characters.")
	}
	return prompt, provider, model, nil
}

// isUniqueViolation reports whether err is a Postgres unique-constraint
// failure — here, always the live_runs_one_active partial index racing a
// concurrent start.
func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

func isNoRows(err error) bool { return errors.Is(err, pgx.ErrNoRows) }

// looksLikeUUID is the same shape check importer.parseUUID does. A malformed
// run_id must answer live_run_not_found, not a 500 from a failed ::uuid cast.
func looksLikeUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, c := range s {
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return false
			}
		default:
			if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
				return false
			}
		}
	}
	return true
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// queryRower is the narrow read used by activeRunID, satisfied by both a
// transaction and the bare pool: the create handler checks inside its
// transaction, and the conflict path checks again after rolling one back.
type queryRower interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// activeRunID returns the organisation's queued-or-running run, or "" when it
// has none. It backs both the friendly pre-check (which can race) and the
// message built after a unique-violation on live_runs_one_active (which
// cannot).
func activeRunID(ctx context.Context, q queryRower, orgID string) (string, error) {
	var id string
	e := q.QueryRow(ctx, `SELECT run_id::text FROM gfm.live_runs
 WHERE org_id=$1::uuid AND state = ANY($2::text[]) LIMIT 1`, orgID, activeStates).Scan(&id)
	if isNoRows(e) {
		return "", nil
	}
	if e != nil {
		return "", mgmt.Internal(e)
	}
	return id, nil
}

func alreadyActive(runID string) error {
	return mgmt.Conflict("live_run_already_active",
		"This organisation already has a queued or running Live Agent run.").
		WithDetails(map[string]any{"run_id": runID})
}
