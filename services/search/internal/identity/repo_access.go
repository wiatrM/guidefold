package identity

import (
	"net/http"
	"regexp"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

var repoUserIDPattern = regexp.MustCompile(`^[0-9a-fA-F-]{36}$`)

type repoAccessRequest struct {
	Access         string `json:"access"`
	IdempotencyKey string `json:"idempotency_key"`
}

func (s *Service) repoUser(c *mgmt.Context) (string, error) {
	id := strings.TrimSpace(c.Param("user_id"))
	if !repoUserIDPattern.MatchString(id) {
		return "", mgmt.Invalid("invalid_user_id", "user_id must be a UUID.")
	}
	return id, nil
}

func (s *Service) handleListRepoAccess(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT r.user_id::text,u.email,u.name,r.access,r.created_at
 FROM gfm.repo_members r JOIN gfm.users u ON u.user_id=r.user_id
 WHERE r.org_id=$1::uuid AND r.repo_id=$2 ORDER BY u.email`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	for rows.Next() {
		var id, email, name, access string
		var created any
		if err := rows.Scan(&id, &email, &name, &access, &created); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, map[string]any{"user_id": id, "email": email, "name": name, "access": access, "created_at": created})
	}
	if err := rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "repo_id": repo.ID, "items": items})
}

func (s *Service) handlePutRepoAccess(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	userID, err := s.repoUser(c)
	if err != nil {
		return err
	}
	var req repoAccessRequest
	if err := c.Decode(&req); err != nil {
		return err
	}
	req.Access = strings.TrimSpace(req.Access)
	if req.Access != "read" && req.Access != "write" {
		return mgmt.Invalid("invalid_access", "access must be read or write.")
	}
	var member bool
	if err := s.pool.QueryRow(c.Ctx(), `SELECT EXISTS(SELECT 1 FROM gfm.memberships WHERE org_id=$1::uuid AND user_id=$2::uuid)`, org.ID, userID).Scan(&member); err != nil {
		return mgmt.Internal(err)
	}
	if !member {
		return mgmt.NotFound("member_not_found", "That person is not a member of this organization.")
	}
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	if _, err = tx.Exec(c.Ctx(), `INSERT INTO gfm.repo_acl_policies(org_id,repo_id,created_by)
 VALUES($1::uuid,$2,$3::uuid) ON CONFLICT(org_id,repo_id) DO UPDATE SET enabled=true`, org.ID, repo.ID, c.Principal.UserID); err != nil {
		return mgmt.Internal(err)
	}
	if _, err = tx.Exec(c.Ctx(), `INSERT INTO gfm.repo_members(org_id,repo_id,user_id,access,created_by)
 VALUES($1::uuid,$2,$3::uuid,$4,$5::uuid)
 ON CONFLICT(org_id,repo_id,user_id) DO UPDATE SET access=excluded.access`, org.ID, repo.ID, userID, req.Access, c.Principal.UserID); err != nil {
		return mgmt.Internal(err)
	}
	if err = c.Audit(c.Ctx(), tx, org.ID, "repo.access.set", "repo:"+repo.ID+"/user:"+userID, req.Access); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "repo_id": repo.ID, "user_id": userID, "access": req.Access})
}

func (s *Service) handleDeleteRepoAccess(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	userID, err := s.repoUser(c)
	if err != nil {
		return err
	}
	result, err := s.pool.Exec(c.Ctx(), `DELETE FROM gfm.repo_members WHERE org_id=$1::uuid AND repo_id=$2 AND user_id=$3::uuid`, org.ID, repo.ID, userID)
	if err != nil {
		return mgmt.Internal(err)
	}
	if result.RowsAffected() == 0 {
		return mgmt.NotFound("repo_access_not_found", "That repository access grant does not exist.")
	}
	return c.NoContent()
}

func (s *Service) handleListReviewers(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT r.user_id::text,u.email,u.name,r.created_at
 FROM gfm.repo_reviewers r JOIN gfm.users u ON u.user_id=r.user_id
 WHERE r.org_id=$1::uuid AND r.repo_id=$2 ORDER BY u.email`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	for rows.Next() {
		var id, email, name string
		var created any
		if err := rows.Scan(&id, &email, &name, &created); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, map[string]any{"user_id": id, "email": email, "name": name, "created_at": created})
	}
	if err := rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "repo_id": repo.ID, "items": items})
}

func (s *Service) handlePutReviewer(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	userID, err := s.repoUser(c)
	if err != nil {
		return err
	}
	var member bool
	if err := s.pool.QueryRow(c.Ctx(), `SELECT EXISTS(SELECT 1 FROM gfm.memberships WHERE org_id=$1::uuid AND user_id=$2::uuid)`, org.ID, userID).Scan(&member); err != nil {
		return mgmt.Internal(err)
	}
	if !member {
		return mgmt.NotFound("member_not_found", "That person is not a member of this organization.")
	}
	if _, err := s.pool.Exec(c.Ctx(), `INSERT INTO gfm.repo_reviewers(org_id,repo_id,user_id,assigned_by) VALUES($1::uuid,$2,$3::uuid,$4::uuid) ON CONFLICT DO NOTHING`, org.ID, repo.ID, userID, c.Principal.UserID); err != nil {
		return mgmt.Internal(err)
	}
	return c.NoContent()
}

func (s *Service) handleDeleteReviewer(c *mgmt.Context) error {
	org, repo, err := c.AuthorizeRepo("org", "repo", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	userID, err := s.repoUser(c)
	if err != nil {
		return err
	}
	result, err := s.pool.Exec(c.Ctx(), `DELETE FROM gfm.repo_reviewers WHERE org_id=$1::uuid AND repo_id=$2 AND user_id=$3::uuid`, org.ID, repo.ID, userID)
	if err != nil {
		return mgmt.Internal(err)
	}
	if result.RowsAffected() == 0 {
		return mgmt.NotFound("reviewer_not_found", "That reviewer is not assigned to this repository.")
	}
	return c.NoContent()
}
