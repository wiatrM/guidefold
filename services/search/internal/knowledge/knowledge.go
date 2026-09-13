// Package knowledge is the read side of the catalog: the skill list and its
// facets, one skill and its immutable revisions, the exact bytes of a revision,
// the three maps (repository tree, scopes, layers), the relation neighbourhood,
// the module page, and the one write it owns — a person's feedback on a
// revision, which is an event in the ledger rather than a table of its own.
//
// Everything here reads what the import module wrote. It never writes gfm.skills
// or gfm.skill_revisions: a catalog that the read path can edit is a catalog
// whose provenance means nothing.
//
// Two rules run through every handler. A revision that does not exist is 404,
// never quietly the latest one — hydrating a different revision than the caller
// asked for is how an agent ends up acting on instructions nobody reviewed. And
// every query filters by the organisation the request proved, so the same
// repo_id in two organisations is two separate catalogs.
package knowledge

import (
	"context"
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// BlobSource reads the exact bytes of a stored revision. The import module owns
// the store; this package only needs to read one object by digest.
type BlobSource interface {
	Get(ctx context.Context, orgID, sha256 string) ([]byte, error)
}

// EventSink appends validated telemetry events to the ledger. It is a port on
// purpose: feedback from the UI and feedback from an adapter must go through
// one definition and one validator, so a rating means the same thing whoever
// sent it (API-CONTRACT §7, "Feedback z UI nie ma własnej tabeli").
type EventSink func(ctx context.Context, tenantID string, events []any) (map[string]any, error)

// Service holds the knowledge endpoints.
type Service struct {
	pool   *pgxpool.Pool
	blobs  BlobSource
	events EventSink
	// Environment labels feedback events (dev|eval|pilot).
	environment string
}

// New builds the service. A nil sink disables the feedback endpoint's write
// rather than pretending a rating was recorded.
func New(pool *pgxpool.Pool, blobs BlobSource, events EventSink, environment string) *Service {
	if environment == "" {
		environment = "pilot"
	}
	return &Service{pool: pool, blobs: blobs, events: events, environment: environment}
}

// Register mounts the knowledge surface. Everything is a member read except the
// feedback write, which is a member mutation and therefore idempotent.
func (s *Service) Register(r *mgmt.Router) {
	// Spelled out rather than composed, so the contract checker can compare
	// these patterns with docs/API-CONTRACT.md §4.3 literally.
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills", s.handleListSkills)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills/facets", s.handleFacets)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills/facets/lookup", s.handleFacetLookup)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills/{skill_id}", s.handleSkill)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills/{skill_id}/revisions/{revision_id}",
		s.handleRevision)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/skills/{skill_id}/revisions/{revision_id}/raw",
		s.handleRaw)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/skills/{skill_id}/revisions/{revision_id}/feedback",
		s.handleFeedback, mgmt.Idempotent())
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/map/repository", s.handleMapRepository)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/map/scopes", s.handleMapScopes)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/map/layers", s.handleMapLayers)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/map/relations", s.handleMapRelations)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/modules/{scope}", s.handleModule)

	// Organisation-scope twins (API-CONTRACT §4.10): the same handlers, whose
	// scope is every repository the caller may read unless `?repo=` narrows it.
	// On these routes c.Param("repo") is "", so AuthorizeScope falls through to
	// the query parameter and then to the organisation. Feedback stays per
	// repository: a mutation names the row it acts on.
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills", s.handleListSkills)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/facets", s.handleFacets)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/facets/lookup", s.handleFacetLookup)
	// Organisation scope only (§4.10 item 9): a duplicate across repositories
	// needs more than one. The literal segment outranks {skill_id} in ServeMux.
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/duplicates", s.handleDuplicates)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/{skill_id}", s.handleSkill)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/{skill_id}/revisions/{revision_id}", s.handleRevision)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/skills/{skill_id}/revisions/{revision_id}/raw", s.handleRaw)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/map/repository", s.handleMapRepository)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/map/scopes", s.handleMapScopes)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/map/layers", s.handleMapLayers)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/map/relations", s.handleMapRelations)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/modules/{scope}", s.handleModule)
}

// repoByID reads one repository of the organisation, for the source permalink
// of a revision read at organisation scope. Access was already decided by
// AuthorizeScope; this only fetches the git host of a repository the scope
// contains, so it never widens what the caller may see.
func (s *Service) repoByID(ctx context.Context, orgID, repoID string) (*mgmt.Repo, error) {
	repo := &mgmt.Repo{ID: repoID}
	e := s.pool.QueryRow(ctx, `SELECT name,git_host_url FROM gfm.repos
 WHERE org_id=$1::uuid AND repo_id=$2`, orgID, repoID).Scan(&repo.Name, &repo.GitHostURL)
	if e != nil {
		return nil, e
	}
	return repo, nil
}

// reposHoldingScope narrows an organisation-scope read of one scope id to the
// repository that declares it (API-CONTRACT §4.10.6). Scope ids are unique per
// repository, not per organisation: a scope in none of the readable
// repositories is not found, and one in several needs `repo=` — guessing would
// answer for a module the caller did not name.
func (s *Service) reposHoldingScope(ctx context.Context, orgID string, repos []string, scope string) ([]string, error) {
	rows, e := s.pool.Query(ctx, `SELECT repo_id FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id = ANY($2::text[]) AND scope=$3 ORDER BY repo_id`, orgID, repos, scope)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	holders := []string{}
	for rows.Next() {
		var id string
		if e = rows.Scan(&id); e != nil {
			return nil, mgmt.Internal(e)
		}
		holders = append(holders, id)
	}
	if e = rows.Err(); e != nil {
		return nil, mgmt.Internal(e)
	}
	switch len(holders) {
	case 0:
		return nil, mgmt.NotFound("not_found", "No such scope in the repositories you can read.")
	case 1:
		return holders, nil
	default:
		return nil, mgmt.Conflict("scope_ambiguous",
			"This scope exists in more than one repository; add repo=.")
	}
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}
