// Package review owns everything between "the catalog holds skills" and "a
// snapshot serves them": the generation plan, the proposals a generator
// produces, the owner's decision on each one, the patch that carries an
// approved candidate back to git, and the publication that turns an import into
// the immutable catalog SEARCH and USE read.
//
// Three rules shape the whole module.
//
// **Export is not publish.** Approving a candidate writes a revision and a
// patch; it does not put anything in front of an agent. A proposal becomes
// `published` only after its file has actually landed in git and come back in a
// later import — which is why `awaiting_git` is a state and not a spinner
// (error-handling-and-states, "Rozdzielaj obserwacje").
//
// **A draft never reaches SEARCH or USE.** The publication job materialises the
// *import's* files, so a candidate that has not been exported and committed has
// no bytes to publish. Nothing in this package writes a proposal body into
// `gf.*` (PRODUCT-PIVOT U2.6).
//
// **Validation runs before the head moves.** Cycles in `requires`/`refines`, a
// dependency that is not in the snapshot and a required package resource whose
// bytes are missing all fail the publication and leave the previous head
// serving, with the reasons recorded in `gfm.publications.validation`
// (ADR-0028, U5).
package review

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// Job kinds this module runs (API-CONTRACT §8). There is exactly one generation
// kind; `payload.kind` says which of extraction, enrichment and consolidation a
// job performs (tech-lead decision 9).
const (
	KindGenerate = "proposal.generate"
	KindPublish  = "publish.build"
)

// GeneratePayloadVersion labels the generation job's payload. A worker that does
// not know the version refuses the job rather than guessing what the fields mean.
const GeneratePayloadVersion = "proposal.generate-1"

// Proposal states (API-CONTRACT §6).
const (
	StateDraft             = "draft"
	StateApprovedForExport = "approved_for_export"
	StateAwaitingGit       = "awaiting_git"
	StatePublished         = "published"
	StateRejected          = "rejected"
	StateSuperseded        = "superseded"
)

// Publication states. The engine keeps five; the import DTO shows four
// (API-CONTRACT §5.2).
const (
	PublicationBuilding   = "building"
	PublicationValidated  = "validated"
	PublicationActive     = "active"
	PublicationFailed     = "failed"
	PublicationSuperseded = "superseded"
)

// BlobStore is the outbound port for content-addressed bytes. The review module
// needs to read the source it proposes from and to store the candidate it
// proposes, and it needs neither to know that both live in one table today.
type BlobStore interface {
	Put(ctx context.Context, orgID, sha256 string, data []byte) (created bool, err error)
	Get(ctx context.Context, orgID, sha256 string) ([]byte, error)
}

// Service holds the review and publication endpoints.
type Service struct {
	pool  *pgxpool.Pool
	blobs BlobStore
	queue *jobs.Queue
	// recipe describes the configured generator, so the plan can say what would
	// run and the cache key can include it without instantiating a provider.
	recipe generator.Recipe
}

// New builds the service. The generator is selected from the environment here
// rather than per request: which model a deployment pays for is operator
// configuration, never a caller's choice (security-baseline).
func New(pool *pgxpool.Pool, blobs BlobStore) (*Service, error) {
	_, recipe, e := generator.Select(nil)
	if e != nil {
		return nil, e
	}
	return &Service{pool: pool, blobs: blobs, queue: jobs.New(pool), recipe: recipe}, nil
}

// Register mounts the review surface (API-CONTRACT §4.4, plus the two planning
// routes of §4.2). The patterns are spelled out rather than composed, so the
// contract checker can compare them with the document literally.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}/plan", s.handlePlan)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}/proposals:generate",
		s.handleGenerate, mgmt.Idempotent())

	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/proposals", s.handleListProposals)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/proposals/{proposal_id}", s.handleProposal)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/proposals/{proposal_id}/decision",
		s.handleDecision, mgmt.Idempotent())
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/proposals/{proposal_id}/export",
		s.handleExport, mgmt.Idempotent())
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/proposals/{proposal_id}/publication",
		s.handleProposalPublication)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/exports/{export_id}", s.handleGetExport)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/exports/{export_id}/patch", s.handleExportPatch)

	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/publish", s.handlePublish, mgmt.Idempotent())
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/snapshots", s.handleListSnapshots)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/snapshots/{snapshot_id}/activate",
		s.handleActivate, mgmt.Idempotent())
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/publications/{job_id}", s.handlePublicationJob)
}

// repoContext is the authorised (organisation, repository) pair of one request.
type repoContext struct {
	Org  *mgmt.Org
	Repo *mgmt.Repo
	// RepoID is the repository identifier, repeated for readability in queries.
	RepoID string
}

func (s *Service) authorize(c *mgmt.Context, min mgmt.Role) (*repoContext, error) {
	org, repo, e := c.AuthorizeRepo("org", "repo", min)
	if e != nil {
		return nil, e
	}
	return &repoContext{Org: org, Repo: repo, RepoID: repo.ID}, nil
}

func (s *Service) authorizeReviewer(c *mgmt.Context) (*repoContext, error) {
	org, repo, e := c.AuthorizeReviewerRepo("org", "repo")
	if e != nil {
		return nil, e
	}
	return &repoContext{Org: org, Repo: repo, RepoID: repo.ID}, nil
}

func (s *Service) tx(ctx context.Context) (pgx.Tx, error) {
	return s.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
}

// auditActor mirrors mgmt.Context.Audit's own rule, so a caller of an
// exported seam that has no *mgmt.Context (a worker) can supply the same
// actor string an HTTP request would have produced. The same duplication
// internal/importer's own auditActor already carries — one package, one
// small rule, not worth a shared dependency between the two.
func auditActor(c *mgmt.Context) string {
	if c.Principal == nil {
		return "system"
	}
	return c.Principal.ID()
}

// reasonRequired enforces the one field every decision in this module carries.
// A rollback, a rejection and an approval are all owner decisions, and a
// decision without a stated reason is an audit row nobody can act on
// (tech-lead decision 13).
func reasonRequired(reason string) error {
	reason = strings.TrimSpace(reason)
	if len(reason) < 3 || len(reason) > 500 {
		return mgmt.Invalid("invalid_request", "reason must be between 3 and 500 characters.")
	}
	return nil
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func mustJSON(v any) json.RawMessage {
	raw, e := json.Marshal(v)
	if e != nil {
		return json.RawMessage(`null`)
	}
	return raw
}

// parseUUID refuses a path parameter that is not a uuid before it reaches a
// query, so a malformed identifier is 404 rather than a database error.
func parseUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, c := range s {
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return false
			}
		default:
			if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
				return false
			}
		}
	}
	return true
}

// notFound answers for a resource that does not exist inside the caller's own
// organisation. Outside it, Authorize already answered 403.
func notFound(code, message string) error { return mgmt.NotFound(code, message) }

func newID() string { return mgmt.NewID() }

// digest is the sha256 of a value, used both as a blob address and as the
// `value_sha256` that lets a reviewer see that a field's text did not change
// between the proposal they read and the one they approved.
func digest(value string) string {
	if value == "" {
		return ""
	}
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

var errNoRows = pgx.ErrNoRows

func isNoRows(e error) bool { return errors.Is(e, errNoRows) }
