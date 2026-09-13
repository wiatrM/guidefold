package importer

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// kindGitHubImportRepo and githubImportPayloadVersion mirror
// internal/agentrun's own KindGitHubImportRepo / githubImportPayloadVersion
// constants byte for byte — duplicated rather than imported for the same
// reason internal/identity's githubSyncPayload mirrors agentrun's own: the
// job payload is the only channel between the API and the worker
// (internal/README.md), so the two sides share a JSON contract, not a Go
// type.
const (
	kindGitHubImportRepo       = "github.import_repo"
	githubImportPayloadVersion = "github.import_repo-1"
)

type githubImportPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	RepoID         string `json:"repo_id"`
	InstallationID int64  `json:"installation_id"`
}

type githubImportRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
}

// handleImportGitHubRepo enqueues github.import_repo for one repository
// already registered from a linked GitHub installation (API-CONTRACT
// §4.2/§8, Task 3, 1.13.0). It never requires an organisation model key:
// proposals stay exclusive to live.repo (ADR-0046) — this route only
// re-runs the fetch and import.parse stages, over exactly the same
// installation reconciliation github.sync_repositories already performed,
// without a manifest upload.
func (s *Service) handleImportGitHubRepo(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req githubImportRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	installationID, e := s.repoInstallationID(c.Ctx(), rc.Org.ID, rc.RepoID)
	if e != nil {
		return e
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	job, e2 := enqueueGitHubImportRepo(c.Ctx(), tx, s.queue, rc.Org.ID, rc.RepoID, installationID, req.IdempotencyKey)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "github.import.request", "repo:"+rc.RepoID, ""); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusAccepted, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID, "job_id": job.JobID})
}

// handleImportAllGitHubRepos enqueues github.import_repo for every
// repository of this organisation registered from a linked GitHub
// installation — "Import all" as one call (Task 3, API-CONTRACT §4.2
// 1.13.0), never a repository the owner would have to click through one at
// a time.
func (s *Service) handleImportAllGitHubRepos(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req githubImportRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	rows, e := s.pool.Query(c.Ctx(), `SELECT repo_id,github_installation_id FROM gfm.repos
 WHERE org_id=$1::uuid AND github_installation_id IS NOT NULL ORDER BY repo_id`, org.ID)
	if e != nil {
		return mgmt.Internal(e)
	}
	type target struct {
		RepoID         string
		InstallationID int64
	}
	var targets []target
	for rows.Next() {
		var t target
		if e := rows.Scan(&t.RepoID, &t.InstallationID); e != nil {
			rows.Close()
			return mgmt.Internal(e)
		}
		targets = append(targets, t)
	}
	if e := rows.Err(); e != nil {
		return mgmt.Internal(e)
	}
	rows.Close()

	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	items := make([]map[string]any, 0, len(targets))
	for _, t := range targets {
		// A per-repository key derived from the caller's own one, exactly
		// the single-repository route's own key shape below: a retry of the
		// same "Import all" click joins the same set of jobs instead of
		// racing a second one per repository.
		job, e := enqueueGitHubImportRepo(c.Ctx(), tx, s.queue, org.ID, t.RepoID, t.InstallationID,
			req.IdempotencyKey+":"+t.RepoID)
		if e != nil {
			return mgmt.Internal(e)
		}
		items = append(items, map[string]any{"repo_id": t.RepoID, "job_id": job.JobID})
	}
	if e := c.Audit(c.Ctx(), tx, org.ID, "github.import_all.request", "org:"+org.ID, ""); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusAccepted, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "items": items, "count": len(items)})
}

// repoInstallationID reads the installation a repository is registered
// from, or repo_not_github_linked when it is not managed by one (registered
// by hand or the CLI instead — github.sync_repositories is the only writer
// of gfm.repos.github_installation_id).
func (s *Service) repoInstallationID(ctx context.Context, orgID, repoID string) (int64, error) {
	var installationID int64
	e := s.pool.QueryRow(ctx, `SELECT github_installation_id FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2 AND github_installation_id IS NOT NULL`, orgID, repoID).Scan(&installationID)
	if errors.Is(e, pgx.ErrNoRows) {
		return 0, mgmt.NotFound("repo_not_github_linked",
			"That repository is not registered from a linked GitHub installation.")
	}
	if e != nil {
		return 0, mgmt.Internal(e)
	}
	return installationID, nil
}

// enqueueGitHubImportRepo queues exactly one github.import_repo job. Its
// payload must decode identically in agentrun.GitHubImportWorker.Run.
func enqueueGitHubImportRepo(ctx context.Context, tx pgx.Tx, queue *jobs.Queue, orgID, repoID string,
	installationID int64, idempotencyKey string) (*jobs.Job, error) {
	payload, e := json.Marshal(githubImportPayload{
		SchemaVersion: githubImportPayloadVersion, OrgID: orgID, RepoID: repoID, InstallationID: installationID})
	if e != nil {
		return nil, e
	}
	return queue.Enqueue(ctx, tx, jobs.Job{
		OrgID: orgID, RepoID: repoID, Kind: kindGitHubImportRepo, RecipeVersion: githubImportPayloadVersion,
		IdempotencyKey: idempotencyKey, Payload: payload,
	})
}
