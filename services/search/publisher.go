package main

import (
	"context"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
)

// snapshotPublisher lets the publication worker write a built snapshot with the
// operator subcommand's own code.
//
// The review module declares the port; this is the only implementation, and it
// is the same `publishBundle` that `guidefold-search publish` calls. A second
// snapshot writer is how a catalog and a ranker start disagreeing about what a
// card says (ADR-0028, module-boundaries-go).
type snapshotPublisher struct {
	// PolicySHA is the CLI revision this deployment serves. When it is set, a
	// bundle built by a different CLI is refused at publication rather than at
	// the first search.
	PolicySHA string
	Caps      schema.Capabilities
}

var _ review.Publisher = (*snapshotPublisher)(nil)

// Publish writes gf.snapshots, gf.skills, the router index and — when the
// caller asks for it — gf.heads, all inside the caller's transaction, so the
// publication row and the head it describes commit together or not at all.
func (p *snapshotPublisher) Publish(ctx context.Context, tx pgx.Tx, in review.PublishInput) (review.PublishResult, error) {
	out, e := publishBundle(ctx, tx, in.Bundle, publishOptions{
		Tenant: in.Tenant, Repo: in.Repo, PolicySHA: p.PolicySHA,
		Activate: in.Activate, Caps: p.Caps})
	if e != nil {
		return review.PublishResult{}, e
	}
	return review.PublishResult{SnapshotID: out.SnapshotID, Cards: out.Cards,
		CLISHA: out.PolicySHA, Revision: out.Revision}, nil
}
