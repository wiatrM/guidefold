// Package importer owns the repository, the scan manifest, the raw upload and
// the parse job: everything between "a person points the CLI at a monorepo" and
// "the catalog holds skills, revisions, resources, documents and scopes".
//
// The module's shape follows the architecture's boundaries. The API writes the
// import row, claims the blobs and enqueues; the worker parses and fills the
// catalog; both go through the same domain rules in ./domain, which know
// nothing about HTTP, SQL or Python. Nothing here writes gf.* — the serving
// catalog belongs to the publication job.
//
// Two rules run through every handler. Owners mutate and members read, checked
// per request against gfm.memberships, so a revoked membership stops the next
// call. And an organisation that the caller does not belong to answers exactly
// like one that does not exist: 403 with the same body, never a 404 that would
// confirm the repository is real.
package importer

import (
	"context"
	"net/http"
	"regexp"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Job kinds this module enqueues (API-CONTRACT §8).
const (
	KindParse   = "import.parse"
	KindPublish = "publish.build"
)

// PayloadVersion labels the parse job's payload. A worker that does not know
// the version refuses the job instead of guessing what the fields mean.
const PayloadVersion = "import.parse-1"

var repoPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,64}$`)

// Service holds the import endpoints.
type Service struct {
	pool  *pgxpool.Pool
	blobs BlobStore
	queue *jobs.Queue
}

// New builds the service over one database and one blob store.
func New(pool *pgxpool.Pool, blobs BlobStore) *Service {
	if blobs == nil {
		blobs = NewBlobStore(pool)
	}
	return &Service{pool: pool, blobs: blobs, queue: jobs.New(pool)}
}

// Register mounts the import surface. Every mutation is idempotent except the
// blob upload, which is idempotent by nature: the same bytes under the same
// digest are the same object.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos", s.handleListRepos)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos", s.handleCreateRepo, mgmt.IdempotentLive())

	// The patterns are spelled out rather than composed, so the contract
	// checker can compare them with docs/API-CONTRACT.md §4.2 literally.
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/imports", s.handleListImports)
	// Live rather than replayed: the answer names the blobs still missing, and
	// a resumed sync must be told what is missing now, not what was missing the
	// first time (U1.4).
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/imports", s.handleCreateImport,
		mgmt.IdempotentLive())
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}", s.handleGetImport)
	r.Handle(http.MethodPut, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}/blobs/{sha256}",
		s.handlePutBlob, mgmt.Stream(domain.MaxBlobBytes+1))
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}/finalize",
		s.handleFinalize, mgmt.IdempotentLive())
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/imports/{import_id}/cancel",
		s.handleCancel, mgmt.IdempotentLive())
}

// repoContext is the authorised (organisation, repository) pair of one request.
type repoContext struct {
	Org  *mgmt.Org
	Repo *mgmt.Repo
	// RepoID is the repository identifier, repeated for readability in queries.
	RepoID string
}

func (s *Service) authorizeRepo(c *mgmt.Context, min mgmt.Role) (*repoContext, error) {
	org, repo, e := c.AuthorizeRepo("org", "repo", min)
	if e != nil {
		return nil, e
	}
	return &repoContext{Org: org, Repo: repo, RepoID: repo.ID}, nil
}

func (s *Service) tx(ctx context.Context) (pgx.Tx, error) {
	return s.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
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
