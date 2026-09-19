package mgmt

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// Role orders the two membership roles. RoleAny only requires membership.
type Role int

// Roles, in increasing order of privilege.
const (
	RoleAny Role = iota
	RoleMember
	RoleOwner
)

// Org is a resolved organisation plus the caller's role in it.
type Org struct {
	ID        string    `json:"org_id"`
	Slug      string    `json:"slug"`
	Name      string    `json:"name"`
	Role      string    `json:"my_role"`
	CreatedAt time.Time `json:"created_at"`
}

// Context carries one request through the middleware and into a handler.
type Context struct {
	W         http.ResponseWriter
	R         *http.Request
	RequestID string
	Principal *Principal
	Body      []byte

	router *Router
	orgID  string // set by Authorize, for the request log
}

// Param returns a path wildcard, for example Param("org").
func (c *Context) Param(name string) string { return c.R.PathValue(name) }

// Query returns a query-string parameter.
func (c *Context) Query(name string) string { return c.R.URL.Query().Get(name) }

// Pool is the database handle.
func (c *Context) Pool() interface {
	Exec(context.Context, string, ...any) (pgconn.CommandTag, error)
	Query(context.Context, string, ...any) (pgx.Rows, error)
	QueryRow(context.Context, string, ...any) pgx.Row
} {
	return c.router.opts.Pool
}

// Now is the router's clock.
func (c *Context) Now() time.Time { return c.router.now() }

// Ctx is the request context.
func (c *Context) Ctx() context.Context { return c.R.Context() }

// Tx opens a read-write transaction. The API role runs read-only by default, so
// every management write goes through here.
func (c *Context) Tx(ctx context.Context) (pgx.Tx, error) {
	return c.router.opts.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
}

// Decode reads the JSON request body into v, rejecting unknown fields so a
// typo in a client is an error rather than a silently ignored setting.
func (c *Context) Decode(v any) error {
	if len(c.Body) == 0 {
		return Invalid("invalid_body", "A JSON body is required.")
	}
	d := json.NewDecoder(newReader(c.Body))
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return Invalid("invalid_json", "The request body is not valid JSON for this endpoint.")
	}
	return nil
}

// JSON writes a response.
func (c *Context) JSON(status int, v any) error {
	body, e := json.Marshal(v)
	if e != nil {
		return Internal(e)
	}
	c.W.Header().Set("Content-Type", "application/json")
	c.W.WriteHeader(status)
	_, _ = c.W.Write(body)
	return nil
}

// NoContent answers 204. Deletions and sign-out carry nothing worth returning.
func (c *Context) NoContent() error {
	c.W.WriteHeader(http.StatusNoContent)
	return nil
}

// Redirect sends a 302 to a same-origin path. A value that is not a relative
// path is replaced by the root, so a caller-supplied return_to can never turn
// a login link into an open redirect.
func (c *Context) Redirect(path string) error {
	if !Relative(path) {
		path = "/"
	}
	return c.RedirectTo(path)
}

// RedirectTo sends a 302 to a location the server itself built, such as the
// identity provider's authorize URL. Never pass caller input here.
func (c *Context) RedirectTo(location string) error {
	c.W.Header().Set("Location", location)
	c.W.WriteHeader(http.StatusFound)
	return nil
}

// Authorize resolves the {org} path parameter and checks the caller's role.
//
// A caller who is not a member and a caller naming an organisation that does
// not exist get the same 403 body: membership is the only thing the API is
// willing to confirm.
func (c *Context) Authorize(orgParam string, min Role) (*Org, error) {
	if c.Principal == nil {
		return nil, Unauthenticated("Sign in to continue.")
	}
	ref := c.Param(orgParam)
	if ref == "" {
		return nil, Invalid("org_required", "The organization is missing from the path.")
	}
	// Machine tokens act on the delivery endpoints, not on management routes.
	if !c.Principal.IsUser() {
		return nil, Forbidden()
	}
	org := &Org{}
	e := c.router.opts.Pool.QueryRow(c.Ctx(), `SELECT o.org_id::text,o.slug,o.name,o.created_at,m.role
 FROM gfm.orgs o JOIN gfm.memberships m ON m.org_id=o.org_id AND m.user_id=$2::uuid
 WHERE o.org_id::text=$1 OR o.slug=$1`, ref, c.Principal.UserID).
		Scan(&org.ID, &org.Slug, &org.Name, &org.CreatedAt, &org.Role)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, Forbidden()
	}
	if e != nil {
		return nil, Internal(e)
	}
	if min == RoleOwner && org.Role != "owner" {
		return nil, Fail(http.StatusForbidden, "forbidden", "This action requires the owner role.")
	}
	c.orgID = org.ID
	return org, nil
}

// Repo is a resolved repository of the authorised organisation.
type Repo struct {
	ID         string `json:"repo_id"`
	Name       string `json:"name"`
	GitHostURL string `json:"git_host_url"`
}

// SourceURL builds the link to one file at one commit, or "" when the
// repository has no git host configured or the commit is unknown. It is never
// guessed: a wrong permalink is worse than no permalink.
func (r *Repo) SourceURL(commit, path string) string {
	if r == nil || r.GitHostURL == "" || commit == "" || path == "" {
		return ""
	}
	return strings.TrimSuffix(r.GitHostURL, "/") + "/blob/" + commit + "/" + path
}

// AuthorizeRepo resolves {org} and {repo} together and checks the caller's
// role. It is here rather than in each feature package because "which tenant is
// this request for" has to have exactly one answer: a repository of an
// organisation the caller does not belong to is the same 403 as an
// organisation that does not exist, and only a member ever learns that a
// repository id is unknown *inside* their own organisation.
func (c *Context) AuthorizeRepo(orgParam, repoParam string, min Role) (*Org, *Repo, error) {
	org, e := c.Authorize(orgParam, min)
	if e != nil {
		return nil, nil, e
	}
	repo, e := c.resolveRepo(org, c.Param(repoParam))
	if e != nil {
		return nil, nil, e
	}
	return org, repo, nil
}

// resolveRepo checks one repository id against the organisation and the
// caller's repository ACL. It is the one place that rule lives, so a
// `{repo_base}` route and an `{org_base}` route narrowed with `?repo=` cannot
// disagree about what the same member may read.
func (c *Context) resolveRepo(org *Org, id string) (*Repo, error) {
	if !repoID.MatchString(id) {
		return nil, Invalid("invalid_repo_id", "repo_id must match [A-Za-z0-9_.-]{1,64}.")
	}
	repo := &Repo{ID: id}
	e := c.router.opts.Pool.QueryRow(c.Ctx(), `SELECT name,git_host_url FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, org.ID, id).Scan(&repo.Name, &repo.GitHostURL)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, NotFound("not_found", "No such repository in this organization.")
	}
	if e != nil {
		return nil, Internal(e)
	}
	// Repository ACLs are opt-in. Owners retain access to administer the
	// policy; members are admitted only when the repository has no ACL rows or
	// when their user is explicitly listed. The check lives here so every
	// importer, knowledge, review and usage endpoint gets the same isolation.
	if org.Role != "owner" {
		var restricted, allowed bool
		if e = c.router.opts.Pool.QueryRow(c.Ctx(), `SELECT
		 (EXISTS(SELECT 1 FROM gfm.repo_acl_policies WHERE org_id=$1::uuid AND repo_id=$2 AND enabled)
		  OR EXISTS(SELECT 1 FROM gfm.repo_members WHERE org_id=$1::uuid AND repo_id=$2)),
 EXISTS(SELECT 1 FROM gfm.repo_members WHERE org_id=$1::uuid AND repo_id=$2 AND user_id=$3::uuid)`,
			org.ID, repo.ID, c.Principal.UserID).Scan(&restricted, &allowed); e != nil {
			return nil, Internal(e)
		}
		if restricted && !allowed {
			return nil, Forbidden()
		}
	}
	return repo, nil
}

// Scope is the set of repositories one read may cover (API-CONTRACT §4.10).
//
// A `{repo_base}` route always has a scope of exactly one repository. An
// `{org_base}` route covers every repository the caller may read, unless its
// `repo` query parameter narrows it to one — in which case the answer must be
// the same as the `{repo_base}` route's.
type Scope struct {
	// Repos is the id of every repository the answer may include, in id order.
	// It is never nil: an organisation with no readable repository has an empty
	// scope, and `repo_id = ANY(scope.Repos)` over it selects no row rather
	// than every row.
	Repos []string
	// Repo is the one repository when the route or `?repo=` named it; nil when
	// the scope spans the organisation.
	Repo *Repo
}

// Single reports whether the scope is exactly one named repository.
func (s *Scope) Single() bool { return s != nil && s.Repo != nil }

// RepoID is what a list envelope reports as `repo_id`: the repository when
// the scope is one, nil when the answer spans several (API-CONTRACT §4.10.3).
func (s *Scope) RepoID() any {
	if s.Single() {
		return s.Repo.ID
	}
	return nil
}

// Contains reports whether a repository id is inside the scope.
func (s *Scope) Contains(repoID string) bool {
	for _, id := range s.Repos {
		if id == repoID {
			return true
		}
	}
	return false
}

// AuthorizeScope resolves {org} and then the repository scope of the request:
// the {repo} path parameter when the route has one, otherwise the optional
// `repo` query parameter, otherwise every repository of the organisation the
// caller may read. Both readers go through resolveRepo, so a member's
// repository ACL is applied identically whichever route they take.
func (c *Context) AuthorizeScope(orgParam, repoParam string, min Role) (*Org, *Scope, error) {
	org, e := c.Authorize(orgParam, min)
	if e != nil {
		return nil, nil, e
	}
	id := ""
	if repoParam != "" {
		id = c.Param(repoParam)
	}
	if id == "" {
		id = strings.TrimSpace(c.Query("repo"))
	}
	if id != "" {
		repo, e := c.resolveRepo(org, id)
		if e != nil {
			return nil, nil, e
		}
		return org, &Scope{Repos: []string{repo.ID}, Repo: repo}, nil
	}
	repos, e := c.ReadableRepos(org)
	if e != nil {
		return nil, nil, e
	}
	return org, &Scope{Repos: repos}, nil
}

// ReadableRepos is every repository of the organisation the caller may read,
// in id order and never nil: the unnarrowed scope of AuthorizeScope. A read
// that must look beyond a `?repo=` filter (duplicates across repositories,
// API-CONTRACT §4.10 item 9) takes it from here, so the ACL rule stays in one place.
func (c *Context) ReadableRepos(org *Org) ([]string, error) {
	rows, e := c.router.opts.Pool.Query(c.Ctx(), `SELECT r.repo_id FROM gfm.repos r
 WHERE r.org_id=$1::uuid
   AND ($2 OR NOT (EXISTS(SELECT 1 FROM gfm.repo_acl_policies p WHERE p.org_id=r.org_id AND p.repo_id=r.repo_id AND p.enabled)
                OR EXISTS(SELECT 1 FROM gfm.repo_members m WHERE m.org_id=r.org_id AND m.repo_id=r.repo_id))
        OR EXISTS(SELECT 1 FROM gfm.repo_members m WHERE m.org_id=r.org_id AND m.repo_id=r.repo_id AND m.user_id=$3::uuid))
 ORDER BY r.repo_id`, org.ID, org.Role == "owner", c.Principal.UserID)
	if e != nil {
		return nil, Internal(e)
	}
	defer rows.Close()
	repos := []string{}
	for rows.Next() {
		var id string
		if e := rows.Scan(&id); e != nil {
			return nil, Internal(e)
		}
		repos = append(repos, id)
	}
	if e := rows.Err(); e != nil {
		return nil, Internal(e)
	}
	return repos, nil
}

// AuthorizeReviewerRepo is the narrow permission used for proposal decisions
// and exports. An assigned reviewer may review a repository without gaining
// organization administration or publication rights. Owners remain reviewers
// implicitly, and the normal repository ACL is checked first.
func (c *Context) AuthorizeReviewerRepo(orgParam, repoParam string) (*Org, *Repo, error) {
	return c.AuthorizeReviewerRepoID(orgParam, c.Param(repoParam))
}

// AuthorizeReviewerRepoID is the same check for a repository the caller did not
// name in the address.
//
// The organisation-scope decision route (API-CONTRACT §4.10 point 10) takes its
// repository from the proposal row rather than from a path segment, and it must
// then be checked exactly as if the caller had asked for that repository
// directly -- same ACL, same reviewer rule, same 403. Sharing one function is
// how the two routes are made unable to disagree.
func (c *Context) AuthorizeReviewerRepoID(orgParam, repoID string) (*Org, *Repo, error) {
	org, err := c.Authorize(orgParam, RoleAny)
	if err != nil {
		return nil, nil, err
	}
	repo, err := c.resolveRepo(org, repoID)
	if err != nil {
		return nil, nil, err
	}
	if org.Role == "owner" {
		return org, repo, nil
	}
	var assigned bool
	if err := c.router.opts.Pool.QueryRow(c.Ctx(), `SELECT EXISTS(
 SELECT 1 FROM gfm.repo_reviewers WHERE org_id=$1::uuid AND repo_id=$2 AND user_id=$3::uuid)`,
		org.ID, repo.ID, c.Principal.UserID).Scan(&assigned); err != nil {
		return nil, nil, Internal(err)
	}
	if !assigned {
		return nil, nil, Fail(http.StatusForbidden, "forbidden", "This action requires an assigned reviewer or owner role.")
	}
	return org, repo, nil
}

var repoID = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,64}$`)

// Audit appends one immutable entry. Every mutation writes one, in the same
// transaction as the change it describes.
func (c *Context) Audit(ctx context.Context, tx pgx.Tx, orgID, action, entity, revision string) error {
	actor := "system"
	if c.Principal != nil {
		actor = c.Principal.ID()
	}
	return Audit(ctx, tx, orgID, actor, action, entity, revision, c.RequestID)
}

// Writer is the subset of pgx.Tx an audit entry needs. The worker writes audit
// rows too — a drift decision has an actor and a request identifier just like a
// button press — and it holds its own transaction type.
type Writer interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
}

// Audit appends one immutable entry on behalf of a caller that has no HTTP
// request: the worker names itself as the actor and its job as the request.
func Audit(ctx context.Context, tx Writer, orgID, actor, action, entity, revision, requestID string) error {
	var rev any
	if revision != "" {
		rev = revision
	}
	_, e := tx.Exec(ctx, `INSERT INTO gfm.audit(org_id,actor,action,entity,revision,request_id)
 VALUES($1::uuid,$2,$3,$4,$5,$6)`, orgID, actor, action, entity, rev, requestID)
	return e
}

// ResolveOrgID maps an org_id or slug to the org_id, or "" when unknown. It
// deliberately does not check membership: callers that care use Authorize.
func (c *Context) ResolveOrgID(ctx context.Context, ref string) string {
	if ref == "" {
		return ""
	}
	var id string
	e := c.router.opts.Pool.QueryRow(ctx,
		`SELECT org_id::text FROM gfm.orgs WHERE org_id::text=$1 OR slug=$1`, ref).Scan(&id)
	if e != nil {
		return ""
	}
	return id
}
