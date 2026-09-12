package identity

import (
	"context"
	"encoding/json"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

type createOrgRequest struct {
	Name           string `json:"name"`
	Slug           string `json:"slug"`
	IdempotencyKey string `json:"idempotency_key"`
}

func (s *Service) handleCreateOrg(c *mgmt.Context) error {
	if !c.Principal.IsUser() {
		return mgmt.Forbidden()
	}
	var req createOrgRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	req.Name = strings.TrimSpace(req.Name)
	if req.Name == "" || len(req.Name) > 200 {
		return mgmt.Invalid("invalid_name", "name must be between 1 and 200 characters.")
	}
	if !slugPattern.MatchString(req.Slug) {
		return mgmt.Invalid("invalid_slug", "slug must match [a-z0-9-]{2,40}.")
	}
	orgID := NewID()
	tx, e := s.tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(c.Ctx())
	var taken bool
	if e = tx.QueryRow(c.Ctx(), `SELECT EXISTS(SELECT 1 FROM gfm.orgs WHERE slug=$1)`, req.Slug).Scan(&taken); e != nil {
		return mgmt.Internal(e)
	}
	if taken {
		return mgmt.Conflict("slug_taken", "That slug is already in use.")
	}
	if _, e = tx.Exec(c.Ctx(), `INSERT INTO gfm.orgs(org_id,slug,name) VALUES($1::uuid,$2,$3)`,
		orgID, req.Slug, req.Name); e != nil {
		return mgmt.Internal(e)
	}
	if _, e = tx.Exec(c.Ctx(), `INSERT INTO gfm.memberships(org_id,user_id,role)
 VALUES($1::uuid,$2::uuid,'owner')`, orgID, c.Principal.UserID); e != nil {
		return mgmt.Internal(e)
	}
	if e = c.Audit(c.Ctx(), tx, orgID, "org.create", "org:"+orgID, ""); e != nil {
		return mgmt.Internal(e)
	}
	if e = tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusCreated, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": orgID, "slug": req.Slug,
		"name": req.Name, "my_role": "owner"})
}

func (s *Service) handleListOrgs(c *mgmt.Context) error {
	if !c.Principal.IsUser() {
		return mgmt.Forbidden()
	}
	orgs, e := s.orgsOf(c.Ctx(), c.Principal.UserID)
	if e != nil {
		return e
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "items": orgs})
}

func (s *Service) handleGetOrg(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	var members, repos int
	if e := s.pool.QueryRow(c.Ctx(), `SELECT
 (SELECT count(*) FROM gfm.memberships WHERE org_id=$1::uuid),
 (SELECT count(*) FROM gfm.repos WHERE org_id=$1::uuid)`, org.ID).Scan(&members, &repos); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "slug": org.Slug,
		"name": org.Name, "my_role": org.Role, "created_at": org.CreatedAt,
		"counts": map[string]int{"members": members, "repos": repos}})
}

type memberView struct {
	UserID   string    `json:"user_id"`
	Email    string    `json:"email"`
	Name     string    `json:"name"`
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
}

func (s *Service) handleListMembers(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT u.user_id::text,u.email,u.name,m.role,m.joined_at
 FROM gfm.memberships m JOIN gfm.users u ON u.user_id=m.user_id
 WHERE m.org_id=$1::uuid ORDER BY m.joined_at,u.user_id`, org.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []memberView{}
	for rows.Next() {
		var v memberView
		if err = rows.Scan(&v.UserID, &v.Email, &v.Name, &v.Role, &v.JoinedAt); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, v)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "items": items})
}

type roleRequest struct {
	Role           string `json:"role"`
	IdempotencyKey string `json:"idempotency_key"`
}

// handleSetRole changes one member's role. Demoting the last owner would leave
// the organisation unadministrable, so it is refused.
func (s *Service) handleSetRole(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req roleRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if req.Role != "owner" && req.Role != "member" {
		return mgmt.Invalid("invalid_role", "role must be owner or member.")
	}
	target := c.Param("user_id")
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	var current string
	err = tx.QueryRow(c.Ctx(), `SELECT role FROM gfm.memberships
 WHERE org_id=$1::uuid AND user_id=$2::uuid FOR UPDATE`, org.ID, target).Scan(&current)
	if err == pgx.ErrNoRows {
		return mgmt.NotFound("member_not_found", "That person is not a member of this organization.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if current == "owner" && req.Role != "owner" {
		if e := lastOwnerGuard(c.Ctx(), tx, org.ID); e != nil {
			return e
		}
	}
	if _, err = tx.Exec(c.Ctx(), `UPDATE gfm.memberships SET role=$3
 WHERE org_id=$1::uuid AND user_id=$2::uuid`, org.ID, target, req.Role); err != nil {
		return mgmt.Internal(err)
	}
	if err = c.Audit(c.Ctx(), tx, org.ID, "member.role", "user:"+target, req.Role); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "user_id": target, "role": req.Role})
}

func (s *Service) handleRemoveMember(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	target := c.Param("user_id")
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	var current string
	err = tx.QueryRow(c.Ctx(), `SELECT role FROM gfm.memberships
 WHERE org_id=$1::uuid AND user_id=$2::uuid FOR UPDATE`, org.ID, target).Scan(&current)
	if err == pgx.ErrNoRows {
		return mgmt.NotFound("member_not_found", "That person is not a member of this organization.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if current == "owner" {
		if e := lastOwnerGuard(c.Ctx(), tx, org.ID); e != nil {
			return e
		}
	}
	if _, err = tx.Exec(c.Ctx(), `DELETE FROM gfm.memberships
 WHERE org_id=$1::uuid AND user_id=$2::uuid`, org.ID, target); err != nil {
		return mgmt.Internal(err)
	}
	if err = c.Audit(c.Ctx(), tx, org.ID, "member.remove", "user:"+target, ""); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.NoContent()
}

func lastOwnerGuard(ctx context.Context, tx pgx.Tx, orgID string) error {
	var owners int
	if e := tx.QueryRow(ctx, `SELECT count(*) FROM gfm.memberships
 WHERE org_id=$1::uuid AND role='owner'`, orgID).Scan(&owners); e != nil {
		return mgmt.Internal(e)
	}
	if owners <= 1 {
		return mgmt.Conflict("last_owner_protected",
			"An organization must keep at least one owner. Promote another member first.")
	}
	return nil
}

type inviteRequest struct {
	Email          string `json:"email"`
	Role           string `json:"role"`
	IdempotencyKey string `json:"idempotency_key"`
}

func (s *Service) handleInvite(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req inviteRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	req.Email = strings.TrimSpace(req.Email)
	if req.Email == "" || !strings.Contains(req.Email, "@") || len(req.Email) > 320 {
		return mgmt.Invalid("invalid_email", "A valid e-mail address is required.")
	}
	if req.Role == "" {
		req.Role = "member"
	}
	if req.Role != "owner" && req.Role != "member" {
		return mgmt.Invalid("invalid_role", "role must be owner or member.")
	}
	token, invitationID := newSecret(), NewID()
	expires := s.now().Add(InvitationTTL)
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	// Inviting somebody who is already here is a mistake worth naming. Minting
	// a second link would produce an invitation that can only ever be accepted
	// into a membership that already exists, and the owner would be waiting for
	// a join that never happens (contract 1.0.1).
	var alreadyMember bool
	if err = tx.QueryRow(c.Ctx(), `SELECT EXISTS(
 SELECT 1 FROM gfm.memberships m JOIN gfm.users u ON u.user_id=m.user_id
 WHERE m.org_id=$1::uuid AND lower(u.email)=lower($2))`, org.ID, req.Email).
		Scan(&alreadyMember); err != nil {
		return mgmt.Internal(err)
	}
	if alreadyMember {
		// The address is not echoed: an error message is not a place to
		// confirm which addresses an organisation holds.
		return mgmt.Conflict("member_exists",
			"That person is already a member of this organization.")
	}
	if _, err = tx.Exec(c.Ctx(), `INSERT INTO gfm.invitations
 (org_id,invitation_id,token_sha256,email,role,created_by,expires_at)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6::uuid,$7)`,
		org.ID, invitationID, digest(token), req.Email, req.Role, c.Principal.UserID, expires); err != nil {
		return mgmt.Internal(err)
	}
	// The audit entry names the invitation, never the address.
	if err = c.Audit(c.Ctx(), tx, org.ID, "invitation.create", "invitation:"+invitationID, req.Role); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusCreated, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"invitation_id":  invitationID,
		"org_id":         org.ID,
		"role":           req.Role,
		"accept_url":     s.cfg.PublicURL + "/api/v1/invitations/" + token + "/accept",
		"expires_at":     expires,
	})
}

// handleAcceptInvitation joins the signed-in user. The invited address is not
// checked against the account's address: the link is the capability, and the
// two addresses legitimately differ (an alias, a personal account).
func (s *Service) handleAcceptInvitation(c *mgmt.Context) error {
	if !c.Principal.IsUser() {
		return mgmt.Forbidden()
	}
	token := c.Param("token")
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	var orgID, role string
	var expires time.Time
	var accepted, revoked *time.Time
	err = tx.QueryRow(c.Ctx(), `SELECT org_id::text,role,expires_at,accepted_at,revoked_at
 FROM gfm.invitations WHERE token_sha256=$1 FOR UPDATE`, digest(token)).
		Scan(&orgID, &role, &expires, &accepted, &revoked)
	if err == pgx.ErrNoRows {
		return mgmt.NotFound("invitation_not_found", "This invitation is not valid.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if revoked != nil || accepted != nil {
		return mgmt.Conflict("invitation_used", "This invitation has already been used.")
	}
	if !expires.After(s.now()) {
		return mgmt.Conflict("invitation_expired", "This invitation has expired. Ask for a new one.")
	}
	if _, err = tx.Exec(c.Ctx(), `INSERT INTO gfm.memberships(org_id,user_id,role)
 VALUES($1::uuid,$2::uuid,$3) ON CONFLICT (org_id,user_id) DO NOTHING`,
		orgID, c.Principal.UserID, role); err != nil {
		return mgmt.Internal(err)
	}
	if _, err = tx.Exec(c.Ctx(), `UPDATE gfm.invitations SET accepted_by=$2::uuid,accepted_at=now()
 WHERE token_sha256=$1`, digest(token), c.Principal.UserID); err != nil {
		return mgmt.Internal(err)
	}
	if err = c.Audit(c.Ctx(), tx, orgID, "invitation.accept", "user:"+c.Principal.UserID, role); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": orgID, "role": role, "joined": true})
}

type installationRequest struct {
	Name           string          `json:"name"`
	Kind           string          `json:"kind"`
	RepoID         string          `json:"repo_id"`
	Scopes         []string        `json:"scopes"`
	Harness        string          `json:"harness"`
	Capabilities   json.RawMessage `json:"capabilities"`
	IdempotencyKey string          `json:"idempotency_key"`
}

type tokenSpec struct {
	Kind         string
	UserID       string
	OrgID        string
	RepoID       string
	Scopes       []string
	Name         string
	Harness      string
	Capabilities json.RawMessage
}

// issueToken writes the SHA-256 and returns the only copy of the secret.
func (s *Service) issueToken(ctx context.Context, tx pgx.Tx, spec tokenSpec) (string, string, error) {
	secret := TokenPrefix + newSecret()
	tokenID := NewID()
	if spec.Scopes == nil {
		spec.Scopes = []string{}
	}
	_, e := tx.Exec(ctx, `INSERT INTO gfm.tokens
 (token_id,token_sha256,kind,user_id,org_id,repo_id,scopes,name,harness,capabilities)
 VALUES($1::uuid,$2,$3,$4::uuid,$5::uuid,$6,$7,$8,$9,$10::jsonb)`,
		tokenID, digest(secret), spec.Kind, nullable(spec.UserID), nullable(spec.OrgID),
		nullable(spec.RepoID), spec.Scopes, spec.Name, nullable(spec.Harness),
		nullableJSON(spec.Capabilities))
	if e != nil {
		return "", "", mgmt.Internal(e)
	}
	return secret, tokenID, nil
}

func (s *Service) handleCreateInstallation(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req installationRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	req.Name = strings.TrimSpace(req.Name)
	if req.Name == "" || len(req.Name) > 200 {
		return mgmt.Invalid("invalid_name", "name must be between 1 and 200 characters.")
	}
	kind := req.Kind
	if kind == "" {
		kind = mgmt.SourceInstallation
	}
	scopes, err := normaliseScopes(kind, req.Scopes)
	if err != nil {
		return err
	}
	if req.RepoID != "" && !repoPattern.MatchString(req.RepoID) {
		return mgmt.Invalid("invalid_repo_id", "repo_id must match [A-Za-z0-9_.-]{1,64}.")
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	if req.RepoID != "" {
		if e := EnsureRepo(c.Ctx(), tx, org.ID, req.RepoID, ""); e != nil {
			return e
		}
	}
	secret, tokenID, e := s.issueToken(c.Ctx(), tx, tokenSpec{
		Kind: kind, OrgID: org.ID, RepoID: req.RepoID, Scopes: scopes,
		Name: req.Name, Harness: req.Harness, Capabilities: req.Capabilities})
	if e != nil {
		return e
	}
	if e := c.Audit(c.Ctx(), tx, org.ID, "installation.create", "token:"+tokenID,
		strings.Join(scopes, ",")); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	// The secret appears in this response and nowhere else, ever.
	return c.JSON(http.StatusCreated, map[string]any{
		"schema_version":  mgmt.SchemaVersion,
		"installation_id": tokenID,
		"org_id":          org.ID,
		"kind":            kind,
		"name":            req.Name,
		"repo_id":         req.RepoID,
		"scopes":          scopes,
		"token":           secret,
	})
}

func normaliseScopes(kind string, requested []string) ([]string, error) {
	switch kind {
	case mgmt.SourceCI:
		if len(requested) == 0 {
			return []string{"validate"}, nil
		}
		for _, s := range requested {
			if s != "validate" {
				return nil, mgmt.Invalid("invalid_scopes", "A CI token carries the validate scope only.")
			}
		}
		return []string{"validate"}, nil
	case mgmt.SourceInstallation:
		if len(requested) == 0 {
			return nil, mgmt.Invalid("invalid_scopes",
				"Choose at least one of search, use, events.")
		}
		seen := map[string]bool{}
		for _, s := range requested {
			if !contains(InstallationScopes, s) {
				return nil, mgmt.Invalid("invalid_scopes",
					"An installation token carries only search, use and events.")
			}
			seen[s] = true
		}
		out := make([]string, 0, len(seen))
		for s := range seen {
			out = append(out, s)
		}
		sort.Strings(out)
		return out, nil
	default:
		return nil, mgmt.Invalid("invalid_kind", "kind must be installation or ci.")
	}
}

func contains(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

type installationView struct {
	InstallationID string          `json:"installation_id"`
	Kind           string          `json:"kind"`
	Name           string          `json:"name"`
	RepoID         string          `json:"repo_id"`
	Scopes         []string        `json:"scopes"`
	Harness        string          `json:"harness"`
	AdapterVersion string          `json:"adapter_version"`
	Capabilities   json.RawMessage `json:"capabilities"`
	CreatedAt      time.Time       `json:"created_at"`
	LastSeenAt     *time.Time      `json:"last_seen_at"`
	RevokedAt      *time.Time      `json:"revoked_at"`
}

func (s *Service) handleListInstallations(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT token_id::text,kind,name,repo_id,scopes,harness,
 adapter_version,capabilities::text,created_at,last_seen_at,revoked_at
 FROM gfm.tokens WHERE org_id=$1::uuid AND kind<>'personal'
 ORDER BY created_at DESC,token_id`, org.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []installationView{}
	for rows.Next() {
		var v installationView
		var repo, harness, adapter, capabilities *string
		if err = rows.Scan(&v.InstallationID, &v.Kind, &v.Name, &repo, &v.Scopes, &harness,
			&adapter, &capabilities, &v.CreatedAt, &v.LastSeenAt, &v.RevokedAt); err != nil {
			return mgmt.Internal(err)
		}
		v.RepoID, v.Harness, v.AdapterVersion = str(repo), str(harness), str(adapter)
		if capabilities != nil {
			v.Capabilities = json.RawMessage(*capabilities)
		}
		items = append(items, v)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "items": items})
}

// handleRevokeInstallation revokes immediately: the next request with that
// token is rejected, because tokens are re-read on every request.
func (s *Service) handleRevokeInstallation(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	id := c.Param("installation_id")
	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer tx.Rollback(c.Ctx())
	tag, err := tx.Exec(c.Ctx(), `UPDATE gfm.tokens SET revoked_at=now()
 WHERE org_id=$1::uuid AND token_id=$2::uuid AND kind<>'personal' AND revoked_at IS NULL`, org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	if tag.RowsAffected() == 0 {
		var exists bool
		if err = tx.QueryRow(c.Ctx(), `SELECT EXISTS(SELECT 1 FROM gfm.tokens
 WHERE org_id=$1::uuid AND token_id=$2::uuid AND kind<>'personal')`, org.ID, id).Scan(&exists); err != nil {
			return mgmt.Internal(err)
		}
		if !exists {
			return mgmt.NotFound("installation_not_found", "No such installation in this organization.")
		}
	}
	if err = c.Audit(c.Ctx(), tx, org.ID, "installation.revoke", "token:"+id, ""); err != nil {
		return mgmt.Internal(err)
	}
	if err = tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}
	return c.NoContent()
}

type auditView struct {
	At        time.Time `json:"at"`
	Actor     string    `json:"actor"`
	Action    string    `json:"action"`
	Entity    string    `json:"entity"`
	Revision  string    `json:"revision"`
	RequestID string    `json:"request_id"`
}

func (s *Service) handleAudit(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	cursor := int64(0)
	if v := c.Query("cursor"); v != "" {
		n, err := strconv.ParseInt(v, 10, 64)
		if err != nil || n < 0 {
			return mgmt.Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
		}
		cursor = n
	}
	// An owner reads every row of the org; a member reads only the rows the
	// audit writer stored under their own principal id (c.Principal.ID(), the
	// same value mgmt.Context.Audit uses as actor). "" is never a real actor,
	// so it is a safe sentinel for "no filter".
	actorFilter := ""
	if org.Role != "owner" {
		actorFilter = c.Principal.ID()
	}
	const limit = 100
	rows, err := s.pool.Query(c.Ctx(), `SELECT audit_id,at,actor,action,entity,revision,request_id
 FROM gfm.audit WHERE org_id=$1::uuid AND ($2=0 OR audit_id<$2) AND ($4='' OR actor=$4)
 ORDER BY audit_id DESC LIMIT $3`, org.ID, cursor, limit, actorFilter)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []auditView{}
	var lastID int64
	for rows.Next() {
		var v auditView
		var revision *string
		if err = rows.Scan(&lastID, &v.At, &v.Actor, &v.Action, &v.Entity, &revision, &v.RequestID); err != nil {
			return mgmt.Internal(err)
		}
		v.Revision = str(revision)
		items = append(items, v)
	}
	next := ""
	if len(items) == limit {
		next = strconv.FormatInt(lastID, 10)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID,
		"items": items, "next_cursor": next})
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}
func nullableJSON(b json.RawMessage) any {
	if len(b) == 0 {
		return nil
	}
	return string(b)
}
