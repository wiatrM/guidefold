// Package live is the API half of the Live Agent (ADR-0046, amended by the
// owner's "one button, no prompt, no composer" decision recorded in
// API-CONTRACT 1.6.0): an owner-started, on-demand run across every connected
// repository, watched through an append-only event log rather than a
// streaming transport.
//
// The start route takes no fields (§4.9): there is no prompt, no repository
// selection and no provider/model choice on the request. A run resolves its
// provider and model once, at start, from the organisation's PREFERRED
// stored credential (CredentialSource below) and copies both onto the run
// row, because a later settings change must not rewrite the history of what
// produced that result.
//
// It owns gfm.live_runs, gfm.live_run_targets and gfm.live_run_events, and the
// live.plan job every run fans out through. live.repo — the per-repository
// worker job that reads a repository, builds an import from it and generates
// consolidation proposals — belongs to the worker, not to this package: this
// package only ever enqueues live.plan, and reads the target and event rows
// the worker writes. It never opens the organisation's model key itself;
// CredentialSource resolves provider and model without ever handing back the
// plaintext, and Append, SetTargetState, SetTargetPhase and Finish are the
// surface the worker calls to make its progress visible. The key itself never
// appears in a run row, an event payload, a job payload or an error
// (ADR-0045, ADR-0046 §5).
package live

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
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

// Target phases (§7 gfm.live_run_targets CHECK, §5.5a LiveRunTarget.phase).
// phase says where a target still running has got to: the three stages of
// this run's own work are fetching a repository's files, building an import
// from them, and generating proposals from that import. It advances
// independently of state through SetTargetPhase, so a client watching
// mid-run sees the same progress the worker just wrote.
const (
	PhaseFetch   = "fetch"
	PhaseParse   = "parse"
	PhasePropose = "propose"
	PhaseDone    = "done"
)

// Event types (§7 gfm.live_run_events CHECK, §5.5a LiveRunEvent.type). These
// are progress through the import-and-proposal pipeline, not a model
// transcript: the 1.6.0 amendment removed model.delta and finding along with
// the prompt they narrated, because there is no prompt left to narrate an
// answer to.
const (
	EventRunStarted   = "run.started"
	EventRepoStarted  = "repo.started"
	EventRepoFetched  = "repo.fetched"
	EventRepoParsed   = "repo.parsed"
	EventRepoProposed = "repo.proposed"
	EventRepoFinished = "repo.finished"
	EventRunFinished  = "run.finished"
	EventError        = "error"
)

// EventRunStartedText is run.started's payload.text (§5.5a): the API's own
// handleCreate and the worker's live.plan (agentrun/live_plan.go) can each be
// first to append it — whichever wins the race between a fast worker pickup
// and the create request's own write — so both call sites share this one
// constant rather than risk two different English sentences for the same
// event type.
const EventRunStartedText = "The run started."

// Named termination reasons LiveRun.error carries (ADR-0046 §5, §7;
// API-CONTRACT §5.5a). model_not_available, model_quota_exhausted,
// model_provider_unavailable, github_app_not_configured and
// guidefold_yaml_missing are the worker's to write; they are named here only
// so the domain is documented in one place. guidefold_yaml_missing is also a
// target-level reason (API-CONTRACT §3): a repository with no guidefold.yaml
// is not managed by Guidefold and its target ends TargetSkipped, not
// TargetFailed.
const (
	ErrorCancelled            = "cancelled_by_owner"
	ErrorBudgetExhausted      = "live_run_budget_exhausted"
	ErrorLogTruncated         = "live_run_log_truncated"
	ErrorProviderDown         = "model_provider_unavailable"
	ErrorGitHubNotWired       = "github_app_not_configured"
	ErrorGuidefoldYAMLMissing = "guidefold_yaml_missing"
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
// instead of guessing what the fields mean. The payload carries only
// org_id and run_id (§8): a run always covers every connected repository,
// so there is nothing else for the API to tell live.plan.
const PayloadVersion = "live.plan-1"

// maxEventsPerRun is the log's ceiling (ADR-0046 "20,000 events", §5.5a).
// Past it, Append drops every event except repo.finished and run.finished —
// the two that end something — so a repository or a run that will not stop
// producing progress cannot turn one run into an unbounded table, while the
// two events a client actually needs to see a run reach an end are never
// the ones dropped.
const maxEventsPerRun = 20000

// defaultEventLimit / maxEventLimit bound one page of .../events (§4.9).
const (
	defaultEventLimit = 200
	maxEventLimit     = 500
)

// CredentialSource is the narrow read this package needs from
// internal/secrets to resolve which provider and model a run uses (§4.8,
// §4.9): the organisation's preferred stored credential. live depends on
// this interface rather than on internal/secrets directly, so the two
// packages can be developed independently; the concrete adapter over
// *secrets.Service is wired in at the composition root (see
// NewSecretsCredentialSource).
//
// PreferredProvider must never return the credential's plaintext key: a run
// only ever needs to know which provider and model produced it, and this
// package is documented above as never opening the key itself.
type CredentialSource interface {
	PreferredProvider(ctx context.Context, orgID string) (provider, model string, err error)
}

// ErrNoPreferredCredential is what a CredentialSource returns when the
// organisation has no preferred credential. handleCreate translates it to
// model_credential_missing before queueing anything (§4.9).
var ErrNoPreferredCredential = errors.New("live: organisation has no preferred credential")

// ErrCredentialStoreUnavailable is what a CredentialSource returns when
// credentials cannot be opened at all — the deployment has no secret master
// key. handleCreate translates it to secret_encryption_unavailable (§4.9),
// distinct from model_credential_missing: this organisation may well have a
// preferred credential, it just cannot be resolved right now. Any other
// error from a CredentialSource is internal.
var ErrCredentialStoreUnavailable = errors.New("live: credential store is unavailable")

// Service holds the live-run endpoints.
type Service struct {
	pool        *pgxpool.Pool
	queue       *jobs.Queue
	credentials CredentialSource
}

// New builds the service over one database and the CredentialSource it
// resolves a run's provider and model from.
func New(pool *pgxpool.Pool, credentials CredentialSource) *Service {
	return &Service{pool: pool, queue: jobs.New(pool), credentials: credentials}
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
