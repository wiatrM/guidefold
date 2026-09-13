package agentrun

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// KindGitHubSyncRepositories is the job ADR-0034's explicit link and
// API-CONTRACT §4.7/§8 name for reconciling gfm.repos from one linked
// GitHub App installation's actual repository list. It runs here, not in
// the webhook handler (internal/identity), because it calls GitHub: a
// large "All repositories" installation's own `installation` webhook
// payload is not guaranteed to list every repository, so the authoritative
// source is GET /installation/repositories, paginated, with the
// installation token only the worker holds.
const KindGitHubSyncRepositories = "github.sync_repositories"

const githubSyncPayloadVersion = "github.sync_repositories-1"

// Sync failure reasons (API-CONTRACT §4.7/§5.1
// GitHubInstallation.sync_failure_reason): the vocabulary
// classifySyncFailure maps a ListInstallationRepositories error onto,
// written to gfm.github_installation_links.last_sync_failure_reason. The
// first two are the named sentinels internal/ghapp already distinguishes
// (errors.go) — this job invents nothing beyond them. Everything ghapp does
// not name (network failures, unexpected HTTP statuses, unreadable bodies)
// becomes reasonSyncProviderUnavailable, the same generic "GitHub did not
// answer" bucket §4.7's own install-callback flow already uses for the
// equivalent case, rather than a new made-up category. A fourth value,
// reasonGitHubNotConfigured (pr_report.go), is not something
// classifySyncFailure produces — it is written directly by Run below when
// w.gh is nil, the worker's own half of the App not being configured.
const (
	reasonSyncInstallationNotFound = "installation_not_found"
	reasonSyncPermissionRefused    = "permission_refused"
	reasonSyncProviderUnavailable  = "provider_unavailable"
)

// classifySyncFailure turns a ListInstallationRepositories error into the
// reason this job records and whether it is worth retrying at all.
//
// An installation GitHub no longer recognises (deleted, or the App was
// uninstalled) will not start working by trying again — nothing this
// worker does changes that outcome — and neither will one whose
// permissions the organisation has not (re)approved (ghapp/errors.go's own
// doc comments on both ErrInstallationNotFound and ErrPermissionRefused
// say exactly this: "a caller should say that, not retry"). Both are
// permanent regardless of attempts left. Everything else may be transient
// (a timeout, a 5xx, a momentary rate limit) and keeps retrying until
// jobs.Fail's own attempts<max_attempts runs out.
func classifySyncFailure(e error) (reason string, permanent bool) {
	switch {
	case errors.Is(e, ghapp.ErrInstallationNotFound):
		return reasonSyncInstallationNotFound, true
	case errors.Is(e, ghapp.ErrPermissionRefused):
		return reasonSyncPermissionRefused, true
	default:
		return reasonSyncProviderUnavailable, false
	}
}

// recordGitHubSyncFailure writes the outcome of a reconciliation that did
// not succeed: gfm.github_installation_links.last_sync_failed_at/
// last_sync_failure_reason, the console's only honest "the last attempt
// failed, and here is why" signal (API-CONTRACT §5.1), set outside any
// transaction this job may have opened — a permanent failure or the last
// attempt of a retryable one can both happen before the repos
// attach/detach transaction below ever starts (the GitHub call itself
// failed), so this is always its own single-statement write. A later
// success clears both columns in the same UPDATE that sets
// repositories_synced_at (below), never here.
func recordGitHubSyncFailure(ctx context.Context, pool *pgxpool.Pool, orgID string, installationID int64, reason string) error {
	_, e := pool.Exec(ctx, `UPDATE gfm.github_installation_links
 SET last_sync_failed_at=now(), last_sync_failure_reason=$3
 WHERE installation_id=$1 AND org_id=$2::uuid`, installationID, orgID, reason)
	return e
}

type githubSyncPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	InstallationID int64  `json:"installation_id"`
}

// GitHubSyncWorker runs github.sync_repositories. It is the only writer of
// gfm.repos.github_installation_id: the webhook handler enqueues this job
// but never touches gfm.repos itself, so there is exactly one place that
// decides which repositories an organisation gets from its GitHub
// installation.
type GitHubSyncWorker struct {
	pool *pgxpool.Pool
	gh   *ghapp.Client
}

// NewGitHubSyncWorker wires the handler. gh nil (GitHub App not configured)
// is a valid, expected state — Run then ends every job `skipped` with
// reasonGitHubNotConfigured, the same convention pr.report and live.repo
// use.
func NewGitHubSyncWorker(pool *pgxpool.Pool, gh *ghapp.Client) *GitHubSyncWorker {
	return &GitHubSyncWorker{pool: pool, gh: gh}
}

// Handlers maps the job kind this worker runs.
func (w *GitHubSyncWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindGitHubSyncRepositories: w.Run}
}

// Run reconciles gfm.repos for one (org, installation) pair against the
// installation's current, complete repository list.
//
// Every repository GitHub reports is attached: an existing gfm.repos row
// matched by git_host_url (case-insensitive) is claimed by setting its
// github_installation_id, and a repository with no existing row is created
// with an id derived by deriveRepoID. A repository this installation
// previously reconciled but which GitHub no longer lists is detached —
// github_installation_id set back to NULL — never deleted: gfm.imports,
// gfm.skills, gfm.proposals and gfm.publications all reference gfm.repos
// ON DELETE CASCADE, so deleting the row over a visibility change on
// GitHub's side would destroy an organisation's catalogue and review
// history along with it (API-CONTRACT §4.7).
func (w *GitHubSyncWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload githubSyncPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode github.sync_repositories payload: %w", e))
	}
	if payload.SchemaVersion != githubSyncPayloadVersion || payload.OrgID != t.Job.OrgID || payload.InstallationID == 0 {
		return worker.Permanent(errors.New("github.sync_repositories payload does not match its job row"))
	}
	if w.gh == nil {
		// This is the same honesty gap this whole change exists to close,
		// reached from a different terminal state: worker.Skipped is
		// always final (worker.finish never retries a skip), so a
		// deployment whose API half is configured (an owner can link an
		// installation) but whose worker half is not
		// (GITHUB_APP_ID/GITHUB_APP_PRIVATE_KEY_FILE unset — a separate
		// deployable, worker_handlers.go) would otherwise skip every
		// github.sync_repositories job forever while the link keeps
		// reading synced:false, indistinguishable from "not run yet". The
		// reason reuses reasonGitHubNotConfigured (pr_report.go) — the
		// same code the console's own deployment-problem state already
		// speaks (API-CONTRACT §3/§4.7).
		if werr := recordGitHubSyncFailure(ctx, w.pool, payload.OrgID, payload.InstallationID, reasonGitHubNotConfigured); werr != nil {
			return fmt.Errorf("github.sync_repositories: record failure: %w", werr)
		}
		return worker.Skipped(reasonGitHubNotConfigured)
	}
	fullNames, e := w.gh.ListInstallationRepositories(ctx, payload.InstallationID)
	if e != nil {
		reason, permanent := classifySyncFailure(e)
		// attempts is already incremented for this lease (jobs.Queue.Lease),
		// so attempts>=max_attempts here is exactly jobs.Fail's own
		// retry := retryable && attempts < maxAttempts condition, negated:
		// this is the last try regardless of what this handler returns.
		exhausted := t.Job.Attempts >= t.Job.MaxAttempts
		if permanent || exhausted {
			if werr := recordGitHubSyncFailure(ctx, w.pool, payload.OrgID, payload.InstallationID, reason); werr != nil {
				// A DB hiccup recording the outcome must not itself become
				// the permanent, unrecorded failure this whole change
				// exists to avoid: return it as a plain (retryable) error
				// so a later attempt tries the write again.
				return fmt.Errorf("github.sync_repositories: record failure: %w", werr)
			}
		}
		wrapped := fmt.Errorf("github.sync_repositories: list installation repositories: %w", e)
		if permanent {
			return worker.Permanent(wrapped)
		}
		return wrapped
	}

	tx, e := w.pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer func() { _ = tx.Rollback(ctx) }()

	wanted := make(map[string]bool, len(fullNames))
	for _, full := range fullNames {
		wanted[strings.ToLower(full)] = true
	}
	for _, full := range fullNames {
		if e := attachRepository(ctx, tx, payload.OrgID, payload.InstallationID, full); e != nil {
			return e
		}
	}
	detached, e := detachMissingRepositories(ctx, tx, payload.OrgID, payload.InstallationID, wanted)
	if e != nil {
		return e
	}
	// repositories_synced_at (API-CONTRACT §4.7, §7): the console's only
	// honest "reconciliation has run at least once" signal, written in the
	// same transaction as the gfm.repos attach/detach above so it can never
	// read true without those writes having actually committed. A success
	// also clears any recorded failure — the last reconciliation to
	// actually run is this one, and it worked.
	if _, e := tx.Exec(ctx, `UPDATE gfm.github_installation_links
 SET repositories_synced_at=now(), last_sync_failed_at=NULL, last_sync_failure_reason=NULL
 WHERE installation_id=$1 AND org_id=$2::uuid`, payload.InstallationID, payload.OrgID); e != nil {
		return e
	}
	if e := tx.Commit(ctx); e != nil {
		return e
	}
	t.Result = mustJSON(map[string]any{"repositories": len(fullNames), "detached": detached})
	return nil
}

// attachRepository claims the gfm.repos row for full name (creating it when
// none exists) by setting its github_installation_id.
func attachRepository(ctx context.Context, tx pgx.Tx, orgID string, installationID int64, fullName string) error {
	gitHostURL := "https://github.com/" + fullName
	var repoID string
	e := tx.QueryRow(ctx, `SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid AND lower(git_host_url)=lower($2)`,
		orgID, gitHostURL).Scan(&repoID)
	switch {
	case errors.Is(e, pgx.ErrNoRows):
		repoID = deriveRepoID(fullName)
		_, e = tx.Exec(ctx, `INSERT INTO gfm.repos(org_id,repo_id,name,git_host_url,github_installation_id)
 VALUES($1::uuid,$2,$3,$4,$5)
 ON CONFLICT (org_id,repo_id) DO UPDATE SET github_installation_id=excluded.github_installation_id`,
			orgID, repoID, fullName, gitHostURL, installationID)
		return e
	case e != nil:
		return e
	default:
		_, e = tx.Exec(ctx, `UPDATE gfm.repos SET github_installation_id=$3 WHERE org_id=$1::uuid AND repo_id=$2`,
			orgID, repoID, installationID)
		return e
	}
}

// detachMissingRepositories clears github_installation_id on every
// repository this installation previously attached that is not in wanted
// any more, and returns how many it detached.
func detachMissingRepositories(ctx context.Context, tx pgx.Tx, orgID string, installationID int64, wanted map[string]bool) (int, error) {
	rows, e := tx.Query(ctx, `SELECT repo_id, git_host_url FROM gfm.repos WHERE org_id=$1::uuid AND github_installation_id=$2`,
		orgID, installationID)
	if e != nil {
		return 0, e
	}
	var toDetach []string
	for rows.Next() {
		var repoID, gitHostURL string
		if e := rows.Scan(&repoID, &gitHostURL); e != nil {
			rows.Close()
			return 0, e
		}
		full, ok := fullNameFromGitHostURL(gitHostURL)
		if !ok || !wanted[strings.ToLower(full)] {
			toDetach = append(toDetach, repoID)
		}
	}
	rows.Close()
	if e := rows.Err(); e != nil {
		return 0, e
	}
	for _, repoID := range toDetach {
		if _, e := tx.Exec(ctx, `UPDATE gfm.repos SET github_installation_id=NULL WHERE org_id=$1::uuid AND repo_id=$2`,
			orgID, repoID); e != nil {
			return 0, e
		}
	}
	return len(toDetach), nil
}

// maxRepoNameForID leaves room for the "-" plus a 16-hex-character hash
// suffix within repoPattern's 64-character ceiling (API-CONTRACT §3
// invalid_repo_id, importer.repoPattern).
const maxRepoNameForID = 64 - 1 - 16

// deriveRepoID derives a repo_id from a GitHub "owner/repo" full name.
// repoPattern ("^[A-Za-z0-9_.-]{1,64}$") allows exactly the alphabet GitHub
// itself allows in both a login and a repository name, so no separator
// built from that alphabet can be unambiguous: "a-b/c" and "a/b-c" would
// derive the same id under a plain "-" join, and the same holds for "_" and
// ".". The hash suffix is computed over the whole lowercased full name, so
// two different full names collide only if SHA-256 itself collides, not
// merely because they share a naming pattern — including two different
// owners' repository of the same name, which a bare name-based id could
// not tell apart at all.
func deriveRepoID(fullName string) string {
	sum := sha256.Sum256([]byte(strings.ToLower(fullName)))
	suffix := hex.EncodeToString(sum[:])[:16]
	name := fullName
	if i := strings.LastIndex(fullName, "/"); i >= 0 {
		name = fullName[i+1:]
	}
	if len(name) > maxRepoNameForID {
		name = name[:maxRepoNameForID]
	}
	if name == "" {
		name = "repo"
	}
	return name + "-" + suffix
}
