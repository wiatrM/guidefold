package agentrun

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// reviewProposalGenerator implements ProposalGenerator over
// internal/review's own exported GenerateProposals seam — the in-process
// path over Service.plan added alongside this one, so live.repo never
// reproduces review's own grouping rule (see ProposalGenerator's doc
// comment). This is the real deployment wiring, done in
// services/search/worker_handlers.go; live_repo_test.go's own fake stands in
// for it in tests that do not need a real consolidation group.
type reviewProposalGenerator struct {
	pool   *pgxpool.Pool
	review *review.Service
}

// NewReviewProposalGenerator builds the seam. reviewer is the same
// review.Service the API mounts, sharing its pool, its blob store and its
// configured recipe — a live run's consolidation must land in the same
// gfm.proposals rows and cost the same cache key an HTTP-driven
// proposals:generate call would.
func NewReviewProposalGenerator(pool *pgxpool.Pool, reviewer *review.Service) ProposalGenerator {
	return &reviewProposalGenerator{pool: pool, review: reviewer}
}

// GenerateConsolidation runs review.Service.GenerateProposals for
// kind=consolidation only — the live run never asks for extraction or
// enrichment groups (ADR-0046 point 9) — in its own transaction, the same
// way live_repo.go's other importer-seam calls each open and commit their
// own transaction rather than sharing one across a job's whole run.
// callerJobID becomes the audit row's request id, exactly as
// internal/importer's CreateImportOptions/FinalizeOptions name a worker's
// own job as the request rather than the import it acted on.
func (g *reviewProposalGenerator) GenerateConsolidation(ctx context.Context, orgID, repoID, importID, callerJobID string) (string, error) {
	tx, e := g.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", e
	}
	defer func() { _ = tx.Rollback(ctx) }()
	result, e := g.review.GenerateProposals(ctx, tx, orgID, repoID, importID,
		[]string{generator.KindConsolidation}, review.GenerateOptions{Actor: "live.repo", RequestID: callerJobID})
	if e != nil {
		return "", e
	}
	if e := tx.Commit(ctx); e != nil {
		return "", e
	}
	if len(result.JobIDs) == 0 {
		// Fewer than two contributing scopes anywhere: a legitimate zero,
		// not a failure (ProposalGenerator's own doc comment).
		return "", nil
	}
	return result.JobIDs[0], nil
}

var _ ProposalGenerator = (*reviewProposalGenerator)(nil)
