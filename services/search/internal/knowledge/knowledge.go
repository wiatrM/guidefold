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
