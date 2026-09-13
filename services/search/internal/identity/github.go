package identity

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// githubRepoRef is one entry of gfm.github_installations.repositories, the
// shape this package itself writes ({"full_name":..., "repo_id":...}) —
// API-CONTRACT §5.1's GitHubInstallation.repositories.
type githubRepoRef struct {
	FullName string `json:"full_name"`
	RepoID   any    `json:"repo_id"`
}

// githubInstallationPayload decodes the subset of GitHub's "installation"
// and "installation_repositories" event bodies handleGitHubWebhook needs to
// keep gfm.github_installations current. The two events are distinguished
// by the X-GitHub-Event header, not by shape: "installation" carries the
// account's full repository list on installation.repositories, while
// "installation_repositories" never repeats that list and instead carries
// the delta on top-level repositories_added/repositories_removed — a
// handler that read only installation.repositories for both would silently
// wipe the stored list on every add/remove.
type githubInstallationPayload struct {
	Action       string `json:"action"`
	Installation struct {
		ID      int64 `json:"id"`
		Account struct {
			Login string `json:"login"`
		} `json:"account"`
		Repositories []struct {
			FullName string `json:"full_name"`
		} `json:"repositories"`
		SuspendedAt any `json:"suspended_at"`
		// RepositorySelection is GitHub's own "all"|"selected" on the
		// installation object — API-CONTRACT §5.1. Unlike Repositories
		// (carried only on "created", the comment below explains why),
		// GitHub includes this on the installation object for every
		// "installation" and "installation_repositories" delivery, so
		// upsertGitHubInstallationMirror can read it the same way for
		// every action.
		RepositorySelection string `json:"repository_selection"`
	} `json:"installation"`
	RepositoriesAdded []struct {
		FullName string `json:"full_name"`
	} `json:"repositories_added"`
	RepositoriesRemoved []struct {
		FullName string `json:"full_name"`
	} `json:"repositories_removed"`
}

// githubPullRequestPayload decodes the subset of GitHub's "pull_request"
// event body the coverage-bot report (ADR-0036 points 1, 1a) needs.
type githubPullRequestPayload struct {
	Action       string `json:"action"`
	Installation struct {
		ID int64 `json:"id"`
	} `json:"installation"`
	Repository struct {
		FullName string `json:"full_name"`
	} `json:"repository"`
	PullRequest struct {
		Number int `json:"number"`
		Head   struct {
			SHA string `json:"sha"`
		} `json:"head"`
		Base struct {
			Ref string `json:"ref"`
		} `json:"base"`
	} `json:"pull_request"`
}

// prReportPayload mirrors internal/agentrun's own unexported payload type
// byte for byte (schema_version "pr.report-1", API-CONTRACT §8's `pr.report`
// row). It is not imported from there because the job payload is the only
// channel between the API (this package) and the worker (agentrun) —
// internal/README.md — so the two sides share a JSON contract, not a Go
// type; agentrun's own prReportPayload decodes exactly this shape.
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

// prReportPayloadVersion must stay identical to agentrun's own
// prReportPayloadVersion constant; agentrun.PRReportWorker.Run rejects any
// other schema_version as a permanent job failure.
const prReportPayloadVersion = "pr.report-1"

// kindPRReport must stay identical to agentrun.KindPRReport
// ("pr.report", API-CONTRACT §8). Duplicated rather than imported for the
// same reason as prReportPayload above.
const kindPRReport = "pr.report"

// githubSyncPayload mirrors internal/agentrun's own unexported payload type
// for github.sync_repositories, for the same reason prReportPayload mirrors
// pr.report's.
type githubSyncPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	InstallationID int64  `json:"installation_id"`
}

// githubSyncPayloadVersion and kindGitHubSyncRepositories must stay
// identical to agentrun's githubSyncPayloadVersion and
// KindGitHubSyncRepositories constants.
const (
	githubSyncPayloadVersion   = "github.sync_repositories-1"
	kindGitHubSyncRepositories = "github.sync_repositories"
)

func (s *Service) handleGitHubWebhook(c *mgmt.Context) error {
	if s.cfg.GitHubWebhookSecret == "" {
		return mgmt.Fail(http.StatusServiceUnavailable, "github_app_not_configured", "The GitHub App webhook secret is not configured.")
	}
	signature := strings.TrimSpace(c.R.Header.Get("X-Hub-Signature-256"))
	mac := hmac.New(sha256.New, []byte(s.cfg.GitHubWebhookSecret))
	_, _ = mac.Write(c.Body)
	want := "sha256=" + hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(signature), []byte(want)) {
		return mgmt.Fail(http.StatusUnauthorized, "invalid_webhook_signature", "The GitHub webhook signature is invalid.")
	}
	event := strings.TrimSpace(c.R.Header.Get("X-GitHub-Event"))
	delivery := strings.TrimSpace(c.R.Header.Get("X-GitHub-Delivery"))
	if event == "" || delivery == "" {
		return mgmt.Invalid("invalid_request", "GitHub event and delivery headers are required.")
	}
	digest := sha256.Sum256(c.Body)
	tx, err := c.Tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	result, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_deliveries(delivery_id,payload_sha256) VALUES($1,$2) ON CONFLICT (delivery_id) DO NOTHING`, delivery, hex.EncodeToString(digest[:]))
	if err != nil {
		return mgmt.Internal(err)
	}
	if result.RowsAffected() == 0 {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "duplicate_delivery"})
	}

	// The handler never calls GitHub or a model (ADR-0036 point 1): every
	// branch below only reads/writes gfm.github_installations,
	// gfm.github_installation_links and gfm.jobs inside this one
	// transaction. It never writes gfm.repos itself either — reconciling
	// repositories from a linked installation calls GitHub
	// (ListInstallationRepositories) and belongs entirely to
	// github.sync_repositories, which this handler only enqueues.
	switch event {
	case "installation", "installation_repositories":
		return s.handleGitHubInstallationEvent(c, tx, event, delivery)
	case "pull_request":
		return s.handleGitHubPullRequestEvent(c, tx, digest)
	default:
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
}

// handleGitHubInstallationEvent keeps gfm.github_installations current for
// the "installation" and "installation_repositories" events. Which
// organisation an installation belongs to is decided only by
// gfm.github_installation_links, written by handleGitHubInstallCallback's
// proven OAuth link (ADR-0034) — never guessed from an account or
// organisation login, and never resolved here. An installation nobody has
// linked yet still gets its mirror row maintained (an "installation"
// webhook event can arrive before the owner completes the linking
// callback); it just has nothing to reconcile until the link exists.
func (s *Service) handleGitHubInstallationEvent(c *mgmt.Context, tx pgx.Tx, event, delivery string) error {
	var payload githubInstallationPayload
	if err := json.Unmarshal(c.Body, &payload); err != nil {
		return mgmt.Invalid("invalid_json", "The GitHub webhook body is not valid JSON.")
	}
	if payload.Installation.ID == 0 {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
	installationID := payload.Installation.ID

	var syncJobID any
	switch {
	case event == "installation" && payload.Action == "deleted":
		// The installation no longer exists on GitHub's side at all: detach
		// (never delete) anything it had reconciled for its linked
		// organisation, then remove the mirror row — which cascades to
		// gfm.github_installation_links, since a link cannot outlive its
		// installation.
		if orgID, linked, err := linkedOrg(c.Ctx(), tx, installationID); err != nil {
			return mgmt.Internal(err)
		} else if linked {
			if _, err := tx.Exec(c.Ctx(), `UPDATE gfm.repos SET github_installation_id=NULL WHERE org_id=$1::uuid AND github_installation_id=$2`,
				orgID, installationID); err != nil {
				return mgmt.Internal(err)
			}
		}
		if _, err := tx.Exec(c.Ctx(), `DELETE FROM gfm.github_installations WHERE installation_id=$1`, installationID); err != nil {
			return mgmt.Internal(err)
		}
	case event == "installation" && (payload.Action == "created" || payload.Action == "suspend" || payload.Action == "unsuspend"):
		repositories := make([]githubRepoRef, 0, len(payload.Installation.Repositories))
		for _, repo := range payload.Installation.Repositories {
			if strings.TrimSpace(repo.FullName) != "" {
				repositories = append(repositories, githubRepoRef{FullName: repo.FullName})
			}
		}
		if err := upsertGitHubInstallationMirror(c.Ctx(), tx, s.now, installationID,
			payload.Installation.Account.Login, repositories, payload.Installation.RepositorySelection, payload.Action); err != nil {
			return mgmt.Internal(err)
		}
		if payload.Action == "created" {
			jobID, err := s.syncIfLinked(c.Ctx(), tx, installationID, "github-sync:"+strconv.FormatInt(installationID, 10)+":"+delivery)
			if err != nil {
				return mgmt.Internal(err)
			}
			syncJobID = jobID
		}
	case event == "installation_repositories" && (payload.Action == "added" || payload.Action == "removed"):
		existing, err := currentGitHubRepositories(c.Ctx(), tx, installationID)
		if err != nil {
			return mgmt.Internal(err)
		}
		var added, removed []string
		for _, r := range payload.RepositoriesAdded {
			if strings.TrimSpace(r.FullName) != "" {
				added = append(added, r.FullName)
			}
		}
		for _, r := range payload.RepositoriesRemoved {
			if strings.TrimSpace(r.FullName) != "" {
				removed = append(removed, r.FullName)
			}
		}
		merged := mergeGitHubRepositories(existing, added, removed)
		if err := upsertGitHubInstallationMirror(c.Ctx(), tx, s.now, installationID,
			payload.Installation.Account.Login, merged, payload.Installation.RepositorySelection, ""); err != nil {
			return mgmt.Internal(err)
		}
		jobID, err := s.syncIfLinked(c.Ctx(), tx, installationID, "github-sync:"+strconv.FormatInt(installationID, 10)+":"+delivery)
		if err != nil {
			return mgmt.Internal(err)
		}
		syncJobID = jobID
	default:
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	// job_id is non-nil only when this event's installation is linked and
	// the event can change its repository list: github.sync_repositories,
	// never ascend.run/pr.report — those two stay exclusive to a pull
	// request event, exactly as before this organisation-linking change.
	return c.JSON(http.StatusAccepted, map[string]any{"accepted": true, "job_id": syncJobID, "reason": nil})
}

// syncIfLinked enqueues github.sync_repositories when installationID is
// linked to an organisation, and does nothing (nil, nil) otherwise.
func (s *Service) syncIfLinked(ctx context.Context, tx pgx.Tx, installationID int64, idempotencyKey string) (any, error) {
	orgID, linked, err := linkedOrg(ctx, tx, installationID)
	if err != nil {
		return nil, err
	}
	if !linked {
		return nil, nil
	}
	jobID, err := s.enqueueGitHubSync(ctx, tx, orgID, installationID, idempotencyKey)
	if err != nil {
		return nil, err
	}
	return jobID, nil
}

// linkedOrg reports the organisation gfm.github_installation_links ties
// installationID to, if any.
func linkedOrg(ctx context.Context, tx pgx.Tx, installationID int64) (string, bool, error) {
	var orgID string
	err := tx.QueryRow(ctx, `SELECT org_id::text FROM gfm.github_installation_links WHERE installation_id=$1`, installationID).Scan(&orgID)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	return orgID, true, nil
}

// enqueueGitHubSync queues exactly one github.sync_repositories job. Its
// payload must decode identically in agentrun.GitHubSyncWorker.Run.
func (s *Service) enqueueGitHubSync(ctx context.Context, tx pgx.Tx, orgID string, installationID int64, idempotencyKey string) (string, error) {
	payload, err := json.Marshal(githubSyncPayload{
		SchemaVersion: githubSyncPayloadVersion, OrgID: orgID, InstallationID: installationID,
	})
	if err != nil {
		return "", err
	}
	job, err := jobs.New(s.pool).Enqueue(ctx, tx, jobs.Job{
		OrgID: orgID, Kind: kindGitHubSyncRepositories, RecipeVersion: githubSyncPayloadVersion,
		IdempotencyKey: idempotencyKey, Payload: payload,
	})
	if err != nil {
		return "", err
	}
	return job.JobID, nil
}

// upsertGitHubInstallationMirror writes one gfm.github_installations row,
// keyed by installation_id alone — it mirrors GitHub's own installation
// object and exists independently of any Guidefold organisation.
//
// action controls suspended_at exactly as before ("suspend" sets it to
// now, "unsuspend" clears it); an empty action (the installation_repositories
// path, which never suspends anything) leaves whatever is already stored —
// NULL for a brand new row — untouched.
//
// repositories is written only for "created": GitHub's own "installation"
// payload carries the account's full repository list solely on that
// action, not on "suspend"/"unsuspend" — the same shape of bug the
// installation_repositories fix addresses on its own action pair. Writing
// an empty repositories here for suspend/unsuspend would silently wipe the
// stored list on every suspend, so those two actions (and the empty-action
// installation_repositories path is unaffected — it always passes the
// already-merged list) preserve whatever is already stored.
func upsertGitHubInstallationMirror(ctx context.Context, tx pgx.Tx, now func() time.Time, installationID int64,
	account string, repositories []githubRepoRef, repositorySelection, action string) error {
	encoded, err := json.Marshal(repositories)
	if err != nil {
		return err
	}
	var suspended any
	suspendedClause := "suspended_at=excluded.suspended_at"
	reposClause := "repositories=excluded.repositories"
	switch action {
	case "suspend":
		suspended = now()
		reposClause = "repositories=gfm.github_installations.repositories"
	case "unsuspend":
		suspended = nil
		reposClause = "repositories=gfm.github_installations.repositories"
	default:
		suspendedClause = "suspended_at=gfm.github_installations.suspended_at"
	}
	// repositorySelection is a scalar property of the installation object
	// GitHub includes on every action of both event types, unlike
	// repositories above, so it is not gated by action: whenever the caller
	// has it, it is written; otherwise COALESCE keeps whatever is already
	// stored, NULL for a brand new row.
	var selection any
	if v := strings.TrimSpace(repositorySelection); v != "" {
		selection = v
	}
	_, err = tx.Exec(ctx, `INSERT INTO gfm.github_installations(installation_id,account,repositories,repository_selection,suspended_at,updated_at)
 VALUES($1,$2,$3::jsonb,$4,$5,now())
 ON CONFLICT (installation_id) DO UPDATE SET account=excluded.account,`+reposClause+`,
   repository_selection=COALESCE(excluded.repository_selection,gfm.github_installations.repository_selection),
   `+suspendedClause+`,updated_at=now()`,
		installationID, account, encoded, selection, suspended)
	return err
}

// currentGitHubRepositories reads the repository list already stored for an
// installation, or nil when the row does not exist yet (an
// installation_repositories delta arriving before any installation event —
// not expected from GitHub, but not an error either).
func currentGitHubRepositories(ctx context.Context, tx pgx.Tx, installationID int64) ([]githubRepoRef, error) {
	var raw []byte
	err := tx.QueryRow(ctx, `SELECT repositories FROM gfm.github_installations WHERE installation_id=$1`,
		installationID).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var repos []githubRepoRef
	if err := json.Unmarshal(raw, &repos); err != nil {
		return nil, err
	}
	return repos, nil
}

// mergeGitHubRepositories applies an installation_repositories delta to the
// stored list: every entry in added that is not already present (matched
// case-insensitively on full_name) is appended, then every entry in removed
// is dropped. GitHub sends only the delta for this event, never the full
// list, so the merge is this package's own responsibility.
func mergeGitHubRepositories(existing []githubRepoRef, added, removed []string) []githubRepoRef {
	byName := map[string]githubRepoRef{}
	var order []string
	for _, r := range existing {
		key := strings.ToLower(r.FullName)
		if _, ok := byName[key]; !ok {
			order = append(order, key)
		}
		byName[key] = r
	}
	for _, full := range added {
		key := strings.ToLower(full)
		if _, ok := byName[key]; !ok {
			order = append(order, key)
			byName[key] = githubRepoRef{FullName: full}
		}
	}
	for _, full := range removed {
		delete(byName, strings.ToLower(full))
	}
	out := make([]githubRepoRef, 0, len(order))
	for _, key := range order {
		if r, ok := byName[key]; ok {
			out = append(out, r)
		}
	}
	return out
}

// handleGitHubPullRequestEvent enqueues exactly one `pr.report` job per
// (installation, pull request, head sha) for a linked installation and a
// matched repository (API-CONTRACT §4.7). It never calls GitHub or a
// model: the changed-file list `pr.report` needs is not on this payload, so
// fetching it is the worker's job (ADR-0036 point 1). Which organisation an
// installation belongs to comes only from gfm.github_installation_links —
// there is no login-based fallback: an installation nobody has linked
// answers unknown_installation exactly like an installation whose
// repository does not match.
func (s *Service) handleGitHubPullRequestEvent(c *mgmt.Context, tx pgx.Tx, digest [sha256.Size]byte) error {
	var payload githubPullRequestPayload
	if err := json.Unmarshal(c.Body, &payload); err != nil {
		return mgmt.Invalid("invalid_json", "The GitHub webhook body is not valid JSON.")
	}
	if payload.Action != "opened" && payload.Action != "synchronize" && payload.Action != "reopened" {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
	unmatched := func() error {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "unknown_installation"})
	}

	// A genuine GitHub App pull_request delivery always carries all four of
	// these; a body missing one cannot be matched to any installation or
	// repository either, so it gets the same 202 unknown_installation as a
	// real mismatch — deliberately, not as a side effect of the checks
	// below, and for the same reason §4.7 gives for a real mismatch:
	// GitHub must never see a 4xx for this route.
	fullName := strings.TrimSpace(payload.Repository.FullName)
	if payload.Installation.ID == 0 || fullName == "" || payload.PullRequest.Number == 0 || payload.PullRequest.Head.SHA == "" {
		return unmatched()
	}

	orgID, linked, err := linkedOrg(c.Ctx(), tx, payload.Installation.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	if !linked {
		return unmatched()
	}

	hasRepo, err := installationHasRepository(c.Ctx(), tx, payload.Installation.ID, fullName)
	if err != nil {
		return mgmt.Internal(err)
	}
	if !hasRepo {
		return unmatched()
	}
	repoID, ok, err := resolveRepoIDByFullName(c.Ctx(), tx, orgID, fullName)
	if err != nil {
		return mgmt.Internal(err)
	}
	if !ok {
		return unmatched()
	}

	payloadJSON, err := json.Marshal(prReportPayload{
		SchemaVersion:  prReportPayloadVersion,
		OrgID:          orgID,
		InstallationID: payload.Installation.ID,
		RepoID:         repoID,
		FullName:       fullName,
		PRNumber:       payload.PullRequest.Number,
		HeadSHA:        payload.PullRequest.Head.SHA,
		BaseRef:        payload.PullRequest.Base.Ref,
	})
	if err != nil {
		return mgmt.Internal(err)
	}
	idempotencyKey := fmt.Sprintf("pr:%d:%d:%s", payload.Installation.ID, payload.PullRequest.Number, payload.PullRequest.Head.SHA)
	job, err := jobs.New(s.pool).Enqueue(c.Ctx(), tx, jobs.Job{
		OrgID: orgID, RepoID: repoID, Kind: kindPRReport, InputDigest: hex.EncodeToString(digest[:]),
		RecipeVersion: prReportPayloadVersion, IdempotencyKey: idempotencyKey, Payload: payloadJSON,
	})
	if err != nil {
		return mgmt.Internal(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusAccepted, map[string]any{"accepted": true, "job_id": job.JobID, "reason": nil})
}

// installationHasRepository reports whether fullName is among the
// repositories stored for this installation (case-insensitive), i.e. that
// this pull request's repository was actually installed there — rejecting
// a delivery that names a real installation_id but a repository GitHub
// never granted it.
func installationHasRepository(ctx context.Context, tx pgx.Tx, installationID int64, fullName string) (bool, error) {
	repos, err := currentGitHubRepositories(ctx, tx, installationID)
	if err != nil {
		return false, err
	}
	want := strings.ToLower(fullName)
	for _, r := range repos {
		if strings.ToLower(r.FullName) == want {
			return true, nil
		}
	}
	return false, nil
}

// resolveRepoIDByFullName matches a GitHub "owner/repo" full name against
// gfm.repos.git_host_url for the organisation. Since part 3 of ADR-0034's
// explicit link (github.sync_repositories), git_host_url for an
// installation-managed repository is written by Guidefold itself from the
// installation's own repository list, not typed by a human — but the match
// here is still string comparison against a derived URL, and
// GitHubInstallation.repositories[].repo_id is still never populated, so
// this remains a narrower workaround (API-CONTRACT §8), not an actual
// foreign key.
func resolveRepoIDByFullName(ctx context.Context, tx pgx.Tx, orgID, fullName string) (string, bool, error) {
	rows, err := tx.Query(ctx, `SELECT repo_id, git_host_url FROM gfm.repos WHERE org_id=$1::uuid`, orgID)
	if err != nil {
		return "", false, err
	}
	defer rows.Close()
	want := strings.ToLower(fullName)
	for rows.Next() {
		var repoID, gitHostURL string
		if err := rows.Scan(&repoID, &gitHostURL); err != nil {
			return "", false, err
		}
		if got, ok := fullNameFromGitHostURL(gitHostURL); ok && strings.ToLower(got) == want {
			return repoID, true, nil
		}
	}
	return "", false, rows.Err()
}

// fullNameFromGitHostURL extracts "owner/repo" from a repository's stored
// git_host_url. Duplicated from internal/agentrun's function of the same
// name for the same reason as prReportPayload above: the two packages meet
// only at the job payload, never at a shared Go type.
func fullNameFromGitHostURL(gitHostURL string) (string, bool) {
	u, e := url.Parse(strings.TrimSpace(gitHostURL))
	if e != nil || u.Host == "" {
		return "", false
	}
	host := strings.ToLower(u.Host)
	if host != "github.com" && !strings.HasSuffix(host, ".github.com") {
		return "", false
	}
	path := strings.Trim(u.Path, "/")
	path = strings.TrimSuffix(path, ".git")
	segments := strings.Split(path, "/")
	if len(segments) != 2 || segments[0] == "" || segments[1] == "" {
		return "", false
	}
	return segments[0] + "/" + segments[1], true
}

func (s *Service) handleListGitHubInstallations(c *mgmt.Context) error {
	org, err := c.Authorize("org", mgmt.RoleAny)
	if err != nil {
		return err
	}
	// registered_repositories is gfm.repos, not the webhook mirror's own
	// repositories[] list: github.sync_repositories (agentrun/github_sync.go)
	// is the only writer of gfm.repos.github_installation_id, so this count
	// is what the owner actually gets, not what GitHub merely reported it
	// could see. synced comes from repositories_synced_at, written inside
	// that same job's own transaction (never from gfm.jobs, retained only 90
	// days) — a real "reconciliation has run at least once" flag, not an
	// inference from created_at/updated_at.
	rows, err := s.pool.Query(c.Ctx(), `SELECT gi.installation_id,gi.account,gi.repositories,gi.repository_selection,gi.suspended_at,gi.created_at,gi.updated_at,
 l.linked_at,l.repositories_synced_at,
 (SELECT count(*) FROM gfm.repos r WHERE r.org_id=$1::uuid AND r.github_installation_id=gi.installation_id)
 FROM gfm.github_installations gi JOIN gfm.github_installation_links l ON l.installation_id=gi.installation_id
 WHERE l.org_id=$1::uuid ORDER BY gi.installation_id`, org.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	for rows.Next() {
		var id int64
		var account string
		var repositories []byte
		var repositorySelection *string
		var suspended, created, updated, linkedAt, syncedAt any
		var registered int64
		if err := rows.Scan(&id, &account, &repositories, &repositorySelection, &suspended, &created, &updated,
			&linkedAt, &syncedAt, &registered); err != nil {
			return mgmt.Internal(err)
		}
		var repoList []any
		if err := json.Unmarshal(repositories, &repoList); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, map[string]any{
			"installation_id": id, "account": account, "repositories": repoList,
			"repository_selection": repositorySelection, "suspended": suspended != nil,
			"created_at": created, "updated_at": updated, "linked_at": linkedAt,
			"registered_repositories": registered, "synced": syncedAt != nil,
		})
	}
	if err := rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "items": items})
}

// handleDeleteGitHubInstallation unlinks an installation from this
// organisation. It never deletes the gfm.github_installations mirror row —
// the installation may still exist on GitHub's side, covering nothing to do
// with this organisation any more — and it detaches (never deletes) every
// repository this installation had reconciled, the same rule
// github.sync_repositories applies to a repository GitHub itself stops
// reporting.
func (s *Service) handleDeleteGitHubInstallation(c *mgmt.Context) error {
	org, err := c.Authorize("org", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	id, err := strconv.ParseInt(c.Param("installation_id"), 10, 64)
	if err != nil || id <= 0 {
		return mgmt.NotFound("installation_not_found", "That GitHub installation does not exist.")
	}
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	result, err := tx.Exec(c.Ctx(), `DELETE FROM gfm.github_installation_links WHERE org_id=$1::uuid AND installation_id=$2`, org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	if result.RowsAffected() == 0 {
		return mgmt.NotFound("installation_not_found", "That GitHub installation does not exist.")
	}
	if _, err := tx.Exec(c.Ctx(), `UPDATE gfm.repos SET github_installation_id=NULL WHERE org_id=$1::uuid AND github_installation_id=$2`, org.ID, id); err != nil {
		return mgmt.Internal(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.NoContent()
}
