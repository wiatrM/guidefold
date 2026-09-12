# ADR-0037: Nearest wins for same-name skills in local delivery

**Status:** Accepted · 2026-09-08 · owner directive the same day ("wykonaj zmiany w aplikacji"),
implemented in `skills/guidefold/scripts/guidefold` (`Router.policy_filter`) with
`tests/test_nearest_wins.py`. Measured before the change in
`research/conflicting-siblings-delivery-2026-09-08/` (committed write-up:
`docs/reports/market/2026-09-08-conflicting-siblings-delivery.md`).
**Amends:** [ADR-0022](ADR-0022-admissibility-relevance-and-bundle-completeness.md): admissibility
now includes a shadowing rule, applied inside the policy filter before ranking, so the ranker never
sees a shadowed copy. Ranking itself is unchanged (ADR-0029 rule on production ranking holds).
**Governs:** `guidefold find`, `guidefold hook` and hosted Go SEARCH; the `drops` reasons recorded by
`policy_filter` and the service's aggregate `policy_drops`.

## Context

A monorepo that edits a team-level rule at a service level ends up with the same skill name at two
depths: the team's copy and the service's edit. This is how `AGENTS.md` and `CLAUDE.md` work in
every location-scoped tool (the nearer file takes precedence), and it is how authors in a monorepo
override a parent convention without deleting it.

The CLI made both copies visible at the service (ancestors are visible) and let BM25F rank them.
The two copies differ by a few numbers, so their scores are nearly identical and the ancestor copy,
which is indexed first, came out on top. In the E2 run of 2026-09-08 (24 questions x 3 conflict
types, Haiku-class model, one pass): the ancestor copy ranked first in 24 of 24 cells; the agent,
given the shipped cards, applied the ancestor's stale values in 23 of 24 cells on the
"nearest" type and 23 of 24 on the "narrow scope placed higher" type. A concatenating tool that
simply lists files root-first and is told that nearer files take precedence got 24 of 24 right on
the first value stated. The shipped product was worse than concatenation on the one case where
the product's own metadata said what the right answer was.

## Decision

In `Router.policy_filter`, after the existing deprecated, visibility and negative-trigger drops:
group the surviving skills by name (the last URN segment); where a name is visible at more than
one depth, keep only the copy at the deepest node (the one closest to the requesting node) and
record every other copy as a drop with reason `shadowed-by-nearer:<winning urn>`.

Visible nodes are ancestors-or-self of the requesting node, so "closest" is "deepest". A copy at
a sibling node was never visible and is unaffected. A deprecated copy is dropped by the earlier
rule and does not participate. `--include-deprecated` does not restore a shadowed copy; the flag
is about lifecycle, not precedence.

This is the D3 "nearest wins" rule from the 2026-09-08 design note
(`docs/research/2026-09-06-agent-skill-scan/design-2026-09-08-scan-deltas.md`), and only that
rule. Scope resolution beyond the node tree, supersedes edges and family abstention (`ASK`) are
not implemented here; they need their own evidence.

## Consequences

- With the rule prototyped in the harness, the same run scored 23 of 24 on the "nearest" type and
  every cell of the "deprecated" type answered; the harness prototype and this implementation
  apply the same rule, and the run must be repeated on the shipped path before the number is
  quoted for the product.
- Authors can override a parent rule by copying it to a child scope under the same name. This is
  now documented in `docs/CONVENTIONS.md`; `guidefold validate` does not yet warn when a child copy
  drifts from its parent, which `guidefold report` (P12) should surface.
- The hosted Go service (`services/search`) now applies the same boundary before lexical, dense
  and fused retrieval. Its public response remains schema-compatible: `policy_drops` includes
  shadowed copies and `policy_revision` identifies the policy configuration. The live-path
  benchmark must still be rerun before quoting the local 23/24 result as a hosted-product result.
- Telemetry: `drops` now carries the new reason; the shadow record and the ledger event vocabulary
  (`docs/SEARCH-USE-TELEMETRY.md`) treat it as an admissibility drop like `not-visible`.

## Rejected

- Ranking the nearer copy higher instead of dropping the ancestor: leaves two near-identical cards
  in the four-card budget and still shows the agent the stale values.
- Resolving by `replaced_by` only: requires authors to deprecate the parent copy, which is not what
  a service-level override means and is not what any location-scoped tool requires.
