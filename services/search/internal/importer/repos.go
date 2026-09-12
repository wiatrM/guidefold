package importer

import (
	"net/http"
	"strings"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// repoView is the `Repo` DTO (API-CONTRACT §5.2 / decoders.ts `repo`).
type repoView struct {
	RepoID     string    `json:"repo_id"`
	Name       string    `json:"name"`
	GitHostURL string    `json:"git_host_url"`
	CreatedAt  time.Time `json:"created_at"`
}

func (s *Service) handleListRepos(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT r.repo_id,r.name,r.git_host_url,r.created_at
 FROM gfm.repos r WHERE r.org_id=$1::uuid
   AND ($2='owner'
     OR (NOT EXISTS(SELECT 1 FROM gfm.repo_acl_policies p WHERE p.org_id=r.org_id AND p.repo_id=r.repo_id AND p.enabled)
         AND NOT EXISTS(SELECT 1 FROM gfm.repo_members m WHERE m.org_id=r.org_id AND m.repo_id=r.repo_id))
     OR EXISTS(SELECT 1 FROM gfm.repo_members m WHERE m.org_id=r.org_id AND m.repo_id=r.repo_id AND m.user_id=$3::uuid))
 ORDER BY r.repo_id`, org.ID, org.Role, c.Principal.UserID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []repoView{}
	for rows.Next() {
		var v repoView
		if err = rows.Scan(&v.RepoID, &v.Name, &v.GitHostURL, &v.CreatedAt); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, v)
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID,
		"items": items, "next_cursor": nil})
}

type createRepoRequest struct {
	RepoID         string `json:"repo_id"`
	Name           string `json:"name"`
	GitHostURL     string `json:"git_host_url"`
	IdempotencyKey string `json:"idempotency_key"`
}

// handleCreateRepo registers a repository. Registering one that already exists
// is success, not a conflict: the CLI calls this before every import and two
// engineers connecting the same monorepo must not race each other into an
// error. The status distinguishes the two — 201 created, 200 already there.
func (s *Service) handleCreateRepo(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req createRepoRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if !repoPattern.MatchString(req.RepoID) {
		return mgmt.Invalid("invalid_repo_id", "repo_id must match [A-Za-z0-9_.-]{1,64}.")
	}
	req.Name = strings.TrimSpace(req.Name)
	if len(req.Name) > 200 {
		return mgmt.Invalid("invalid_request", "name must be at most 200 characters.")
	}
	if len(req.GitHostURL) > 500 || strings.ContainsAny(req.GitHostURL, " \r\n") {
		return mgmt.Invalid("invalid_request", "git_host_url must be a single absolute URL.")
	}
	if req.GitHostURL != "" && !strings.HasPrefix(req.GitHostURL, "https://") &&
		!strings.HasPrefix(req.GitHostURL, "http://") {
		return mgmt.Invalid("invalid_request", "git_host_url must be an http(s) URL.")
	}
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	tag, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.repos(org_id,repo_id,name,git_host_url)
 VALUES($1::uuid,$2,$3,$4) ON CONFLICT (org_id,repo_id) DO NOTHING`,
		org.ID, req.RepoID, req.Name, strings.TrimSuffix(req.GitHostURL, "/"))
	if err != nil {
		return mgmt.Internal(err)
	}
	created := tag.RowsAffected() == 1
	if created {
		if err = c.Audit(c.Ctx(), tx, org.ID, "repo.create", "repo:"+req.RepoID, ""); err != nil {
			return mgmt.Internal(err)
		}
	}
	var v repoView
	if err = tx.QueryRow(c.Ctx(), `SELECT repo_id,name,git_host_url,created_at FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, org.ID, req.RepoID).
		Scan(&v.RepoID, &v.Name, &v.GitHostURL, &v.CreatedAt); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	status := http.StatusOK
	if created {
		status = http.StatusCreated
	}
	return c.JSON(status, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID,
		"repo_id": v.RepoID, "name": v.Name, "git_host_url": v.GitHostURL,
		"created_at": v.CreatedAt, "created": created})
}
