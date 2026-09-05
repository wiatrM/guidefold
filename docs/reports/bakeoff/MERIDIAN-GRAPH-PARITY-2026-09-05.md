# Meridian graph parity and the E2.6 budget mismatch

Go already implements the reference router's graph traversal. On the same Meridian snapshot,
query, scope and selection budget, **3,448 successful SEARCH responses have zero differences**
in top-10 ordered URNs/integer scores, selected ordered URNs and immutable card revisions.
Another 72 SEARCH requests correctly reject unmapped workspace paths. All 52 USE checks pass:
50 exact bodies/checksums and two refusals to hydrate the deprecated skill.

The mismatch observed through the PR #61 adapter is reproducible without a graph defect:
**the client omits `budget.max_cards`**. Hook computes local k=3, find defaults to local k=8,
and Go applies the documented default k=4. No scorer or production API semantics were changed
for this investigation. The client integration defect remains open for the CLI owner.

## Evidence and reproduction

Reference source: `695c847573d897d01e03a3d26de5aa8485a7ea1c` (main after PR #61).
CLI SHA-256: `c2a5f7d2a02455e758118b67c921ac23562dccb49b4d458f1e34ed4e78888987`.
The isolated Compose project `guidefold-graph-parity` used port 29765, its own Postgres volume,
and image `guidefold-search:graph-parity`. No encoder or GPU was involved.

Raw [graph evidence](validation/meridian-graph-parity.json.gz) includes every attempt, scope
addressing, budget, status, expected/actual digest and per-mode snapshot/postings digests.
The [actual CLI adapter probe](validation/meridian-client-budget-probe.json) contains the
ordered local and remote selections. Neither artifact includes bearer tokens, private inputs,
raw query text or skill bodies. All skill identifiers belong to the public fictional fixture.

```sh
# Use a dedicated checkout/project; these tools republish test repositories in that project.
export COMPOSE_PROJECT_NAME=guidefold-graph-parity
export GUIDEFOLD_IMAGE=guidefold-search:graph-parity
export GUIDEFOLD_PORT=29765
python tools/search_service/dev.py deploy
python tools/search_service/graph_parity.py
python tools/search_service/client_budget_probe.py
```

The graph test restores the project's original repository in a finally block. It is also a
step of `compose-service`, with JSON uploaded even when a parity assertion fails. Branch
protection must require **compose-service** to enforce the HTTP gate; `native-service` alone
only enforces the existing Go unit/fixture checks. This change does not update branch rules.

## What was exercised

The unchanged 220 Meridian regression queries are crossed with two graph modes (`closure`,
`pagerank`), four budgets (0, 1, 3, 4), and two addressing methods (`node`, `workspace.cwd`):
3,520 SEARCH attempts at concurrency four. This is deterministic implementation equivalence,
not a quality trial, latency admission or selection of new weights. The test's 5,000 ms
request timeout isolates functional checks; the separate 300/400 ms latency gates are unchanged.

| Check | Result |
|---|---:|
| Successful SEARCH, identical output | 3,448 / 3,448 |
| Required unmapped-path rejection (HTTP 422) | 72 / 72 |
| USE active revision body/checksum | 50 / 50 |
| USE deprecated skill rejection (HTTP 409) | 2 / 2 |
| Graph-sensitive queries per mode | 203 / 220 |

The catalog has 26 cards, 17 scope nodes, 16 requires edges, eight refines edges and one
replacement edge. Removing edges from a copy of the reference graph changes a score and/or
selection for 203 queries in each mode. This checks that the corpus actually exercises graph
behavior; it is **not** evidence that 203 answers improved. Existing synthetic Go conformance
fixtures additionally cover cyclic requires relationships and both abstention modes.

The first draft of the harness incorrectly expected successful SEARCH for nine catch-all-only
paths and successful USE for the deprecated card. Inspection showed these were required
contract rejections, not ranking mismatches. The final harness derives path outcomes from the
existing Python context contract and reports expected rejections separately from successful
parity. No fixture or service behavior was altered to make these checks pass.

## Reproduced client defect and handoff

For `simple-001` at `_root`, the real, unmodified `search_with_backend` adapter gives:

| Call | Local cards | Remote cards | parity_mismatch |
|---|---:|---:|---|
| hook, k=3, omitted budget | 3 | 4 | true |
| interactive, k=4, omitted budget | 4 | 4 | false |
| interactive, k=8, omitted budget | 8 | 4 | true |
| direct API, explicit max_cards=3 | 3 | 3 | exact match |

For k=3, the fourth remote card is `_root:release-process`; the first three cards are
identical and in the same order. This reproduces a sufficient cause of the parity alert,
not proof of the exact query used in the earlier TL session.

The CLI owner should pass `budget.max_cards: k` for supported k=0..4, including hook k=3.
For k>4 or `include_deprecated`, contract 1.1 cannot represent the local request: preserve
local behavior with explicit fallback, or negotiate a version that supports it. Do not clamp
k and compare against a different local limit, and do not hide the mismatch telemetry.
Add real-service client tests for k=0/1/3/4, default find k=8 and deprecated inclusion. The
service worktree deliberately leaves `skills/guidefold/scripts/guidefold` unchanged under the
existing ownership restriction.

## Relationship to Graph-of-Skills

The repository's research reference is
[Graph-of-Skills: Dependency-Aware Structural Retrieval for Massive Agent Skills](https://arxiv.org/html/2604.05333v3).
Its dependency-aware retrieval and budgeted skill bundles motivate this feature. Our implemented
contract is narrower: authored snapshot edges, integer scoring, bounded propagation and
selection closure. Default `closure` uses requires edges; `pagerank` additionally uses refines
and replacement edges. USE hydrates one selected revision at a time. The server does not infer
a new graph from a paper or automatically execute every dependency.

Depth-two closure and the delivery cap can leave a larger dependency bundle incomplete.
`composition.status: not_evaluated` is deliberately not a completeness guarantee. This report
establishes graph parity on this fixture, not general dependency completeness, better retrieval
quality, dense admission, or production readiness. Test-A/test-B and their labels were unused.