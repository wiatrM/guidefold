package importer

// Writing an approved organisation scope map (ADR-0051, API-CONTRACT §6, §7).
//
// `gfm.scopes` belongs to this module, so this is the only place an approved
// map becomes rows. The review module asks through a port; it never reaches
// into this table itself.
//
// Two rules are enforced here rather than left to the caller.
//
// **Approval never deletes.** A scope the map does not mention keeps its row.
// A node quietly disappearing would take its skills out of every view without
// anybody having decided that, which is the opposite of what a review is for.
//
// **A declared file outranks an approved proposal.** ADR-0050 fixes the
// precedence as `guidefold.yaml` > approved proposal > inferred, and it runs in
// both directions: a row this function wrote is overwritten by the next import
// that carries the file, and a row the file declared is **left alone** here. The
// `WHERE` on the upsert is that rule. Without it, approving a map on a
// repository that has a `guidefold.yaml` would silently relabel every node the
// file declares as `llm_approved`, and the map would then report the wrong
// source for exactly the nodes whose source was never in doubt.

import (
	"context"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/review/domain"
)

// SourceLLMApproved is the `gfm.scopes.source` value of a row an owner approved
// from a `scope_map` proposal. It is distinct from `guidefold_yaml` on purpose:
// the map has to be able to say that a node exists because somebody accepted a
// proposal, not because a file declared it.
const SourceLLMApproved = "llm_approved"

// ScopeMapWriter applies an approved map inside the caller's transaction.
//
// It holds no state, because everything it needs is an argument: the tenant,
// the reviewer and the map. That is the same rule the rest of this module
// follows — tenant and repository are arguments, never process state.
type ScopeMapWriter struct{}

// NewScopeMapWriter builds the adapter behind review's ScopeMapApplier port.
func NewScopeMapWriter() *ScopeMapWriter { return &ScopeMapWriter{} }

// ApplyScopeMap writes one row per (node, repository) pair the map names and
// returns how many it wrote.
//
// A node spanning three repositories becomes three rows, because a scope
// identifier is unique per repository and not per organisation (ADR-0047
// decision 4): one row per organisation would make the primary key lie about
// which repository the paths belong to.
//
// It is deliberately a separate function from `writeScopes` in parse.go, which
// mirrors one repository's `guidefold.yaml` and owns the `source` values that
// come with it. Folding the two together would mean one function whose
// behaviour depends on who called it.
func (ScopeMapWriter) ApplyScopeMap(ctx context.Context, tx pgx.Tx, orgID, proposalID,
	reviewerID string, m domain.ScopeMap) (int, error) {
	type key struct{ repo, scope string }
	paths := map[key][]string{}
	nodes := map[key]domain.ScopeMapNode{}
	for _, n := range m.Nodes {
		for _, p := range n.Paths {
			k := key{p.RepoID, n.Scope}
			paths[k] = append(paths[k], p.Path)
			nodes[k] = n
		}
	}
	written := 0
	for k, list := range paths {
		n := nodes[k]
		tag, e := tx.Exec(ctx, `INSERT INTO gfm.scopes
 (org_id,repo_id,scope,owner,parent,paths,source,reviewed_by,proposal_id,updated_at)
 VALUES($1::uuid,$2,$3,$4,$5,$6::text[],$7,$8::uuid,$9::uuid,now())
 ON CONFLICT (org_id,repo_id,scope) DO UPDATE SET
  owner=EXCLUDED.owner,parent=EXCLUDED.parent,paths=EXCLUDED.paths,source=EXCLUDED.source,
  reviewed_by=EXCLUDED.reviewed_by,proposal_id=EXCLUDED.proposal_id,updated_at=now()
 WHERE gfm.scopes.source <> 'guidefold_yaml'`,
			orgID, k.repo, k.scope, optional(n.Owner), optional(n.Parent), list,
			SourceLLMApproved, optional(reviewerID), optional(proposalID))
		if e != nil {
			return written, e
		}
		// The count is rows the database actually changed, not loop iterations:
		// a node the file declares is skipped by the `WHERE`, and reporting it as
		// written would make the response claim a change that did not happen.
		written += int(tag.RowsAffected())
	}
	return written, nil
}
