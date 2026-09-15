package schema

// Additive DDL for the LLM-proposed organisation scope map (ADR-0051,
// API-CONTRACT 1.14.0 §7).
//
// It lives in its own statement rather than inside `importerSQL` and
// `reviewSQL` for one reason: everything here widens a CHECK constraint or adds
// a nullable column to a table another change is likely editing at the same
// time. A `DROP CONSTRAINT IF EXISTS` / `ADD CONSTRAINT` pair at the end of the
// migration says exactly what the domain of each column is now, is idempotent,
// and does not touch the `CREATE TABLE` text that two branches would otherwise
// both rewrite.
//
// Widening a CHECK is additive in effect: every row that was legal before is
// still legal. It is still a schema change, so production runs the migrate Job
// and verifies it before the new image digests (CLAUDE.md, "Production is
// sacred", point 2) -- new code writing `source='llm_approved'` against an
// unmigrated database is an outage, not a degraded feature.
//
// Note for whoever merges the inferred-scope-map branch (ADR-0050): its
// `source` value `inferred` belongs in the *same* constraint below, not in a
// second one. Two constraints on one column both have to pass, so a second
// constraint naming a different set would reject every value the first allows
// and vice versa.
const scopeMapSQL = `
ALTER TABLE gfm.scopes ADD COLUMN IF NOT EXISTS reviewed_by uuid;
ALTER TABLE gfm.scopes ADD COLUMN IF NOT EXISTS proposal_id uuid;
ALTER TABLE gfm.scopes DROP CONSTRAINT IF EXISTS scopes_source_check;
ALTER TABLE gfm.scopes ADD CONSTRAINT scopes_source_check
 CHECK(source IN ('guidefold_yaml','directory','codeowners','llm_approved','unknown'));

ALTER TABLE gfm.proposals DROP CONSTRAINT IF EXISTS proposals_kind_check;
ALTER TABLE gfm.proposals ADD CONSTRAINT proposals_kind_check
 CHECK(kind IN ('extraction','enrichment','consolidation','scope_map'));
ALTER TABLE gfm.proposals DROP CONSTRAINT IF EXISTS proposals_state_check;
ALTER TABLE gfm.proposals ADD CONSTRAINT proposals_state_check
 CHECK(state IN ('draft','approved_for_export','awaiting_git','published','applied','rejected','superseded'));
`
