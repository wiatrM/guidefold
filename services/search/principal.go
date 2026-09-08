package main

import (
	"context"
	"crypto/subtle"
	"net/http"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Headers a client uses to name the organisation and repository it is acting
// for. They stay out of the JSON contract so the harness schema is untouched.
const (
	orgHeader  = "X-Guidefold-Org"
	repoHeader = "X-Guidefold-Repo"
)

// scopeFor maps a delivery endpoint to the token scope it needs.
func scopeFor(endpoint string) string {
	switch endpoint {
	case "search":
		return "search"
	case "use":
		return "use"
	case "events:batch":
		return "events"
	}
	return ""
}

// authenticate resolves who is calling a delivery endpoint. It runs before the
// request body is read or an admission slot is taken, so an unauthenticated
// request costs nothing.
//
// The legacy operator token keeps its exact previous meaning: the tenant and
// repository come from process configuration, and no management table is
// consulted. Session cookies and gf_ bearer tokens are the multi-tenant path.
func (a *App) authenticate(r *http.Request, endpoint string) (*mgmt.Principal, error) {
	header := r.Header.Get("Authorization")
	if a.Token != "" && subtle.ConstantTimeCompare([]byte(header), []byte("Bearer "+a.Token)) == 1 {
		return &mgmt.Principal{Source: mgmt.SourceOperator,
			OrgID: a.tenantDefault(), RepoID: a.repoDefault()}, nil
	}
	if a.Identity == nil {
		return nil, fail(401, "unauthorized")
	}
	p, e := a.Identity.Resolve(r.Context(), r)
	if e != nil {
		// A revoked or unknown token is an authentication failure, not a leak
		// of which of the two it was.
		return nil, fail(401, "unauthorized")
	}
	if p == nil {
		return nil, fail(401, "unauthorized")
	}
	if scope := scopeFor(endpoint); scope != "" && !p.HasScope(scope) {
		return nil, fail(403, "insufficient_token_scope")
	}
	return p, nil
}

// resolveTenant picks the organisation this request acts for.
//
// A machine token is bound to one organisation and cannot be pointed at
// another. A person may belong to several, so the client names one; when they
// belong to exactly one, naming it is unnecessary.
func (a *App) resolveTenant(ctx context.Context, p *mgmt.Principal, r *http.Request) (string, error) {
	requested := r.Header.Get(orgHeader)
	if p.Source == mgmt.SourceOperator {
		return p.OrgID, nil
	}
	if a.Identity == nil {
		return "", fail(403, "organization_not_permitted")
	}
	if p.OrgID != "" {
		if requested != "" {
			id, e := a.Identity.OrgIDForRef(ctx, requested)
			if e != nil {
				return "", e
			}
			if id != p.OrgID {
				return "", fail(403, "organization_not_permitted")
			}
		}
		return p.OrgID, nil
	}
	if !p.IsUser() {
		return "", fail(403, "organization_not_permitted")
	}
	if requested != "" {
		id, e := a.Identity.OrgIDForRef(ctx, requested)
		if e != nil {
			return "", e
		}
		if id == "" {
			return "", fail(403, "organization_not_permitted")
		}
		role, e := a.Identity.Membership(ctx, id, p.UserID)
		if e != nil {
			return "", e
		}
		if role == "" {
			// Same answer as an organisation that does not exist.
			return "", fail(403, "organization_not_permitted")
		}
		return id, nil
	}
	orgs, e := a.Identity.OrgIDsOf(ctx, p.UserID)
	if e != nil {
		return "", e
	}
	if len(orgs) == 1 {
		return orgs[0], nil
	}
	return "", fail(400, "organization_required")
}

// resolveRepo picks the repository. A token bound to one repository may only
// use that one, whatever the request body claims.
func (a *App) resolveRepo(ctx context.Context, p *mgmt.Principal, r *http.Request, payload M, tenant string) (string, error) {
	claimed := str(obj(payload["workspace"])["repo_id"])
	if p.Source == mgmt.SourceOperator {
		return a.repoDefault(), nil
	}
	if a.Identity == nil {
		return "", fail(403, "repository_not_permitted")
	}
	if p.RepoID != "" {
		if claimed != "" && claimed != p.RepoID {
			return "", fail(403, "repository_not_permitted")
		}
		if requested := r.Header.Get(repoHeader); requested != "" && requested != p.RepoID {
			return "", fail(403, "repository_not_permitted")
		}
		return p.RepoID, nil
	}
	repo := r.Header.Get(repoHeader)
	if repo == "" {
		repo = claimed
	}
	if repo == "" {
		repos, e := a.Identity.Repos(ctx, tenant)
		if e != nil {
			return "", e
		}
		if len(repos) == 1 {
			return repos[0], nil
		}
		return "", fail(400, "repository_required")
	}
	ok, e := a.Identity.HasRepo(ctx, tenant, repo)
	if e != nil {
		return "", e
	}
	if !ok {
		return "", fail(403, "repository_not_permitted")
	}
	return repo, nil
}

// installationOf names the installation behind a telemetry batch, or "" when a
// person or the legacy operator token sent it. It is the only identifier the
// adapter-health projection keeps: an installation is a machine, not a person,
// so recording it does not turn the health table into a per-person ledger.
func installationOf(p *mgmt.Principal) string {
	if p == nil || p.Source != mgmt.SourceInstallation {
		return ""
	}
	return p.TokenID
}

// managementRequest reports whether a path belongs to the management API.
func managementRequest(r *http.Request) bool {
	return len(r.URL.Path) >= 5 && r.URL.Path[:5] == "/api/"
}

// The operator profile keeps its configured tenant and repository. Both helpers
// tolerate a store-less App so the contract tests can exercise the HTTP surface
// without a database.
func (a *App) tenantDefault() string {
	if a.Store == nil {
		return ""
	}
	return a.Store.Tenant
}
func (a *App) repoDefault() string {
	if a.Store == nil {
		return ""
	}
	return a.Store.Repo
}
