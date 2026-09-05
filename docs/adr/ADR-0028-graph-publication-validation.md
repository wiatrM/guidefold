# ADR-0028: Validate graph integrity before publishing a serving snapshot

Status: Proposed (implemented in the accompanying PR; pending decision-owner review)

## Context

The Go publisher checked snapshot integrity, card identity and index compatibility but accepted
cyclic and dangling graph metadata. PR #62 proved bounded traversal and publication atomicity;
it deliberately did not equate tolerance of malformed graphs with admission of valid catalogs.
The CLI's catalog validator already rejects invalid references and requires/refines cycles.

## Decision

Validate the graph before opening the publication transaction, including idempotent reactivation.
Reject with a stable `invalid_graph_*` publisher error when:

- A requires/refines field is not an optional array of nonempty string identifiers, or a target
  does not exist in the same snapshot.
- Either requires or refines contains a cycle, including self-edges. Check each relation
  independently; a mixed-relation walk is not automatically a dependency cycle.
- A refines target is at a deeper scope than its source, matching the CLI's depth rule.
- A replacement target is malformed or absent from the snapshot; a deprecated card has no
  replacement; or the declared replacement chain contains a cycle.

Optional absent/null edge fields represent no edges. A replacement, when present, is one
nonempty string. Duplicate edges remain legal and preserve existing scoring semantics. Existing
scope/status/negative-trigger filtering still controls delivery; these are not publication-time
ACLs. Referencing an existing deprecated skill is not newly forbidden here.

Use iterative topological validation, with no recursive call-stack growth on long chains.
The HTTP SEARCH/USE contract remains 1.1. This changes operator-side snapshot admission, not
query scoring, selection budgets, or graph traversal. No scoring weights or quality corpora change.

## Consequences

Invalid publication leaves the active head unchanged and writes no snapshot rows. Importers must
repair graph metadata before retrying; rollback to an invalid historical artifact is also rejected.
Previously stored snapshots are not deleted or rewritten, and the reader retains bounded traversal
for historical data. This release therefore does not retroactively certify every stored snapshot;
operators should publish a validated replacement before treating it as admitted by this gate.

This is graph integrity validation, not the complete CLI catalog linter: ownership, referenced
repository files, descriptions, naming conventions, and full scope-map validation remain separate.
It also does not guarantee that a depth-two, budget-limited bundle contains every dependency.
The CLI file stays unchanged. Unit tests retain runtime cycle-tolerance coverage; publication E2E
uses valid DAGs and explicitly tests rejection of malformed graphs plus unchanged head/output.