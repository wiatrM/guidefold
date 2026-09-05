# ADR-0018: Skills stay in the code monorepo; one Postgres for knowledge; GCS for artifacts

**Status:** Proposed · 2026-09-04 · replaces the deleted ADR-0011 · [ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) proposes an amendment; the status here is unchanged.

## Context
Dedicated skills repositories are not possible at the design partner. The workflow analysis behind KNOWLEDGE-DESIGN v0.1 showed that ≥ 95 % of the conflicts projected for v0.3 were synthetic, caused by committed generated files, not by engineers editing independent `SKILL.md` files. The user requires a single database at most and accepts GCS.

## Options
1. **Monorepo-native, conflict-engineered** (chosen): skills next to code; nothing generated committed; path-filtered fast CI for skill-only PRs; bot writes only `proposal/*`; one Cloud SQL Postgres (+ pgvector) for proposals, evidence, telemetry, audit and offline vectors; GCS for immutable index shards, bodies and pinned model weights; Agent Registry downstream.
2. **GCS-native text store** (Plan B): skill text as versioned GCS objects, review workflow and approvals rebuilt in the Knowledge API with a web UI, CODEOWNERS emulated. ~4 extra weeks; loses GitHub review, diff, comments and audit for free.
3. Database as system of record for skill text: rejected in the judge panel (rebuilds review; no offline story).
4. Agent Registry as system of record: rejected (v1alpha, quotas, 3 s calls, no MCP skill tools).

## Decision
Option 1. Plan B is documented and only triggered if skill files are banned from the monorepo by policy.

## Consequences
- ADR-0005 stands; ADR-0011 deleted; ADR-0013 and ADR-0014 revised accordingly.
- Merge-queue impact is bounded by the path-filtered check; genuine conflicts are estimated at 1–3 per day org-wide and measured from week 4 (MVP.md K1).
- The hot path never touches the database or the registry; both can be down without breaking injection.
