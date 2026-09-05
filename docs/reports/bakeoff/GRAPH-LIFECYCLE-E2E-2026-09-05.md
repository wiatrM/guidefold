# Go graph lifecycle E2E

**410 checks passed; 2,121/2,121 concurrent SEARCH responses were consistent and HTTP 200.**
Both `closure` and `pagerank` completed the full lifecycle against real Go and Postgres.
No runtime graph defect was found in these cases. This is stronger coverage than matching a
static corpus, but it is not proof that every possible graph is valid or complete.

The publisher has a separate admission limitation: it accepts cyclic/dangling graph metadata.
The bounded router tolerates those inputs; the CLI catalog validator rejects cycles and
invalid references. These tests document runtime tolerance, not a decision to admit malformed
production catalogs. No Go/CLI runtime, graph policy or API version changed in this extension.

## Reproduce

```sh
# Use an isolated checkout and dedicated Compose project: this suite injects a DB failure.
export COMPOSE_PROJECT_NAME=guidefold-graph-parity
export GUIDEFOLD_IMAGE=guidefold-search:graph-parity
export GUIDEFOLD_PORT=29765
python tools/search_service/dev.py deploy
python tools/search_service/graph_lifecycle.py
```

The tool refuses project names outside `guidefold-graph-*`. It creates synthetic repositories
and an additional test tenant in that project's database. To test transaction rollback, it
briefly installs a trigger which raises an error only for the current synthetic repository
when the active snapshot is updated. Trigger cleanup is in `finally`; the original configured
repository is restored after the suite. The local post-run audit found zero remaining failure
triggers. This is not a tool to run against a shared or production database.

CI runs the suite in `compose-service`, whose project is now explicitly `guidefold-graph-ci`.
The graph lifecycle JSON is uploaded alongside the existing Meridian and 1,000-query DEV
parity artifacts. The required branch check remains **compose-service**; this PR does not
change branch protection rules.

## Coverage and independent expectations

The synthetic catalog has 22 cards and four scope nodes. Five cases specify expected selected
URNs by hand; the larger matrix independently invokes the unchanged CLI reference for exact
ranking and selection. The suite does not alter the Meridian, SKILLRET or held-out corpora.

| Area | What the real service must demonstrate |
|---|---|
| Graph persistence | Postgres metadata equals every submitted card field except the separately stored body, for both original and updated snapshots. |
| Chain | Return an anchor plus depth-one/two prerequisites; omit a depth-three dependency. Order broader scopes before narrower scopes. |
| Cycles and self-edge | Terminate; return unique skills without repeated closure members. |
| Diamond and duplicate edge | Include the shared prerequisite once, even with repeated first-hop edges. |
| Graph-only discovery | Selected prerequisites have no matching query token and are absent from the lexical candidate pool. |
| Policy filtering | Hidden sibling-scope, deprecated, negative-trigger and missing targets do not enter the selected bundle. |
| PageRank edge types | `refines` and replacement paths have an observable integer-score effect in the fixture. The full output matches CLI. |
| Budgets and scopes | Eight queries × five caps (0..4) × four scopes × two graph modes: 320 exact comparisons, including an unmatched query. |
| Loaded context | A hydrated dependency with its current revision is omitted without backfill; an exposed or stale dependency remains in delivery. |
| USE | Exact body/checksum for selected dependencies; 403 for scope violation, 409 for deprecated/stale revision, 404 after removal. |
| Publication | Idempotent republish; add a dependency, remove the old card and replace the anchor's edge without restarting the API. |
| Isolation | Publishing conflicting graphs with identical skill IDs under another repository or tenant does not alter the current API's graph. |
| Atomic visibility | Four readers continue through publication. Each response must match either the complete old or complete new snapshot, including card revisions. |
| Transaction failure | Error at active-head update, after graph rows have been written inside the transaction; old head/output stays active and the rejected snapshot row does not persist. |
| Recovery | Republish the original snapshot to restore the old graph and USE revisions; restart Go and obtain the same result. |

The atomic-read observation counts were:

| Mode | Old snapshot | New snapshot | Mixed/incorrect/error |
|---|---:|---:|---:|
| closure | 912 | 141 | 0 |
| pagerank | 920 | 148 | 0 |

These counts depend on process/container scheduling; CI must observe both versions and zero
invalid responses, not reproduce the exact count. The suite uses a 5-second request timeout
for functional checks and does not redefine the 300/400 ms latency gates.

## Evidence and limits

[Raw local evidence](validation/graph-lifecycle-e2e.json.gz) records all 410 assertions and
2,121 concurrent observations. It contains synthetic identifiers, statuses and digests, not
secrets or skill bodies. Reference CLI SHA-256:
`c2a5f7d2a02455e758118b67c921ac23562dccb49b4d458f1e34ed4e78888987`.

This extends [the Meridian graph parity investigation](MERIDIAN-GRAPH-PARITY-2026-09-05.md),
which already found zero differences in 3,448 successful graph-aware SEARCH responses.
The PR #61 omitted selection-budget defect remains a client-owner handoff, not a graph fix.

Depth-two traversal and the delivery cap can omit prerequisites; the service correctly keeps
`composition.status: not_evaluated`. Successful graph execution/publication does not certify
catalog validity, complete dependency delivery, retrieval quality, GPU behavior or production
readiness. Full publisher-side graph admission validation is still a gap; the adversarial
fixture must not be mistaken for a valid catalog approved by `guidefold validate`.