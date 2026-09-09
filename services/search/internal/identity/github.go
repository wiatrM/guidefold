package identity

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

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
	} `json:"installation"`
	Organization struct {
		Login string `json:"login"`
	} `json:"organization"`
}

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
	delivery := strings.TrimSpace(c.R.Header.Get("X-GitHub-Delivery"))
	if strings.TrimSpace(c.R.Header.Get("X-GitHub-Event")) == "" || delivery == "" {
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
	var payload githubInstallationPayload
	if err := json.Unmarshal(c.Body, &payload); err != nil {
		return mgmt.Invalid("invalid_json", "The GitHub webhook body is not valid JSON.")
	}
	if payload.Installation.ID == 0 {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
	orgRef := strings.TrimSpace(payload.Organization.Login)
	if orgRef == "" {
		orgRef = strings.TrimSpace(payload.Installation.Account.Login)
	}
	orgID := c.ResolveOrgID(c.Ctx(), orgRef)
	if orgID == "" {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "organization_not_found"})
	}
	repositories := make([]map[string]any, 0, len(payload.Installation.Repositories))
	for _, repo := range payload.Installation.Repositories {
		if strings.TrimSpace(repo.FullName) != "" {
			repositories = append(repositories, map[string]any{"full_name": repo.FullName, "repo_id": nil})
		}
	}
	if payload.Action == "deleted" {
		if _, err := tx.Exec(c.Ctx(), `DELETE FROM gfm.github_installations WHERE org_id=$1::uuid AND installation_id=$2`, orgID, payload.Installation.ID); err != nil {
			return mgmt.Internal(err)
		}
	} else if payload.Action == "created" || payload.Action == "added" || payload.Action == "removed" || payload.Action == "suspend" || payload.Action == "unsuspend" {
		encoded, err := json.Marshal(repositories)
		if err != nil {
			return mgmt.Internal(err)
		}
		var suspended any
		if payload.Action == "suspend" {
			suspended = s.now()
		}
		if payload.Action == "unsuspend" {
			suspended = nil
		}
		if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_installations(org_id,installation_id,account,repositories,suspended_at,updated_at)
 VALUES($1::uuid,$2,$3,$4::jsonb,$5,now())
 ON CONFLICT (org_id,installation_id) DO UPDATE SET account=excluded.account,repositories=excluded.repositories,suspended_at=excluded.suspended_at,updated_at=now()`, orgID, payload.Installation.ID, payload.Installation.Account.Login, encoded, suspended); err != nil {
			return mgmt.Internal(err)
		}
	} else {
		return c.JSON(http.StatusAccepted, map[string]any{"accepted": false, "job_id": nil, "reason": "event_ignored"})
	}
	job, err := jobs.New(s.pool).Enqueue(c.Ctx(), tx, jobs.Job{
		OrgID: orgID, Kind: "ascend.run", InputDigest: hex.EncodeToString(digest[:]), RecipeVersion: "ascend.run-1",
		IdempotencyKey: "github:" + delivery, Payload: c.Body,
	})
	if err != nil {
		return mgmt.Internal(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusAccepted, map[string]any{"accepted": true, "job_id": job.JobID, "reason": nil})
}

func (s *Service) handleListGitHubInstallations(c *mgmt.Context) error {
	org, err := c.Authorize("org", mgmt.RoleAny)
	if err != nil {
		return err
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT installation_id,account,repositories,suspended_at,created_at,updated_at
 FROM gfm.github_installations WHERE org_id=$1::uuid ORDER BY installation_id`, org.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	for rows.Next() {
		var id int64
		var account string
		var repositories []byte
		var suspended, created, updated any
		if err := rows.Scan(&id, &account, &repositories, &suspended, &created, &updated); err != nil {
			return mgmt.Internal(err)
		}
		var repoList []any
		if err := json.Unmarshal(repositories, &repoList); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, map[string]any{"installation_id": id, "account": account, "repositories": repoList, "suspended": suspended != nil, "created_at": created, "updated_at": updated})
	}
	if err := rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "items": items})
}

func (s *Service) handleDeleteGitHubInstallation(c *mgmt.Context) error {
	org, err := c.Authorize("org", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	id, err := strconv.ParseInt(c.Param("installation_id"), 10, 64)
	if err != nil || id <= 0 {
		return mgmt.NotFound("installation_not_found", "That GitHub installation does not exist.")
	}
	result, err := s.pool.Exec(c.Ctx(), `DELETE FROM gfm.github_installations WHERE org_id=$1::uuid AND installation_id=$2`, org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	if result.RowsAffected() == 0 {
		return mgmt.NotFound("installation_not_found", "That GitHub installation does not exist.")
	}
	return c.NoContent()
}
