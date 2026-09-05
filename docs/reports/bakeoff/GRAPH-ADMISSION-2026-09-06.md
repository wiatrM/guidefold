# Graph publication validation — 2026-09-06

The Go publisher now rejects invalid graph imports **before opening a database transaction**.
The graph admission gap recorded in PR #62 is closed for requires/refines/replacement integrity.
SEARCH/USE contract 1.1 and the reference scorer are unchanged.

Local validation: **446 E2E assertions passed**, including 12 rejected import classes and
36 checks of error code, unchanged active SEARCH snapshot/output, and absence of a new snapshot
row. All **2,100 concurrent HTTP responses** during valid graph updates were consistent with
one complete old or new version. Both closure and PageRank completed publication, isolation,
transaction-failure, rollback and restart checks. Go race tests and `go vet` passed, including a
10,000-node chain and a disconnected cycle.

## Rejected imports

| Invalid graph | Publisher error suffix after `invalid_graph_` |
|---|---|
| requires self-edge or multi-hop cycle | requires_cycle |
| missing requires target | requires_target_missing |
| requires scalar instead of array, or non-string array member | requires_type |
| missing refines target | refines_target_missing |
| refines target at deeper scope | refines_deeper_target |
| refines cycle | refines_cycle |
| missing replacement target | replaced_by_target_missing |
| deprecated card without replacement | replacement_required |
| malformed replacement value | replaced_by_type |
| replacement cycle | replaced_by_cycle |

The publisher validates each relation independently. Duplicate edges remain legal; scope and
status delivery filtering stays in the router. Absent/null edge values represent no edges,
except a deprecated card must declare a replacement. The Go unit suite retains coverage of
runtime tolerance for historical malformed graphs. The lifecycle E2E baseline is now a valid
DAG; malformed variants must fail admission instead of becoming active.

E2E graph-only mutations retain a valid, snapshot-bound lexical artifact, so the Go publisher
itself detects the graph defect rather than failing earlier in Python's artifact builder.
For each rejected case the previous active graph is queried again and its exact result checked.
No production or quality corpus is modified to satisfy the new admission rule.

## Reproduction and evidence

```sh
export COMPOSE_PROJECT_NAME=guidefold-graph-parity
export GUIDEFOLD_IMAGE=guidefold-search:graph-admission
export GUIDEFOLD_PORT=29765
python tools/search_service/dev.py deploy
python tools/search_service/graph_lifecycle.py
```

Use an isolated test database; lifecycle E2E includes repository-scoped transaction fault
injection as described in [the earlier lifecycle report](GRAPH-LIFECYCLE-E2E-2026-09-05.md).
[Raw local evidence](validation/graph-admission-e2e.json.gz) contains all assertions and
concurrent observations, with synthetic identifiers and digests only. The unchanged reference
CLI SHA is `c2a5f7d2a02455e758118b67c921ac23562dccb49b4d458f1e34ed4e78888987`.
The existing `compose-service` CI job runs the strengthened lifecycle gate together with
Meridian graph parity and the 1,000-query DEV parity gate.

## Compatibility and limits

[ADR-0028](../../adr/ADR-0028-graph-publication-validation.md) records the exact rules. Validation
also applies to idempotent reactivation: an invalid historical artifact cannot be republished
as a rollback target. Existing stored snapshots are not deleted or rewritten, and the reader
retains bounded traversal; publish a validated replacement before claiming that historical
content has passed this gate.

This validates graph integrity, not the full catalog linter (owners, naming, referenced files,
etc.) or complete dependency delivery within the existing depth/budget limits. It does not
admit GPU ranking, modify quality metrics, or declare production readiness. The separate
PR #61 client selection-budget handoff remains unchanged; the CLI file was not edited.