package schema

// Additive DDL for the proposal kind that carries an organisation scope map
// (ADR-0051, API-CONTRACT 1.15.0 §7).
//
// Only `gfm.proposals` is here. The `gfm.scopes` half — the two nullable
// columns and the widened `source` domain — lives next to ADR-0050's own block
// in `importer.go`, because a column has one constraint: two CHECKs on it would
// both have to pass, so a second one naming a different set would reject every
// value the first allows.
//
// Widening a CHECK is additive in effect: every row that was legal before is
// still legal. It is still a schema change, so production runs the migrate Job
// and verifies it before the new image digests (CLAUDE.md, "Production is
// sacred", point 2) — new code writing `kind='scope_map'` against an
// unmigrated database is an outage, not a degraded feature.
//
// The `CREATE TABLE` text in `review.go` already carries the widened CHECKs for
// a fresh database; an existing one keeps the constraint `CREATE TABLE IF NOT
// EXISTS` skipped, so it is replaced here by name.
const scopeMapSQL = `
ALTER TABLE gfm.proposals DROP CONSTRAINT IF EXISTS proposals_kind_check;
ALTER TABLE gfm.proposals ADD CONSTRAINT proposals_kind_check
 CHECK(kind IN ('extraction','enrichment','consolidation','scope_map'));
ALTER TABLE gfm.proposals DROP CONSTRAINT IF EXISTS proposals_state_check;
ALTER TABLE gfm.proposals ADD CONSTRAINT proposals_state_check
 CHECK(state IN ('draft','approved_for_export','awaiting_git','published','applied','rejected','superseded'));
`
