---
name: link-analysis-api
description: "[atlas/graph] Design and implementation rules for the atlas graph endpoints (/v1/graph/neighbors, /v1/graph/paths): request shape, bounded BFS traversal, depth/fan-out/result limits, truncation reporting and in-traversal RBAC filtering. Use when adding or changing a graph query endpoint, modifying traversal.go, tuning traversal limits, or exposing a new edge type. Do not use for general HTTP conventions (see atlas-api-conventions) or for batch graph analytics pipelines."
license: Apache-2.0
compatibility: "Needs Go 1.22+, the graph fixture database (make graph-fixture) and the atlas API toolchain (make api-lint, make api-gen)."
metadata:
  scope: atlas.graph
  owner: graph-team
  requires: "urn:skill:meridian:atlas:atlas-api-conventions"
  references: "platforms/atlas/graph/src/query/traversal.go"
  status: active
  since: "2026-09-04"
  digest: >-
    The atlas graph API exposes neighbourhood and path queries over ontology entities and links
    through one bounded breadth-first traversal engine. Depth, fan-out, result size and time budget
    are capped server-side, truncation is always reported, and RBAC filtering happens inside the
    traversal so unreadable nodes are never expanded.
---
# Link analysis API

## When to use / when NOT to use
Use this skill when you:
- add or change an endpoint under `/v1/graph/` (neighbours, paths, subgraph export)
- modify the traversal engine in `platforms/atlas/graph/src/query/traversal.go`
- tune depth, fan-out, result-size or time limits for graph queries
- expose a new edge type or edge property through the API

Do NOT use it for:
- envelope, pagination and versioning rules; those come from `atlas-api-conventions`, loaded with this skill
- defining what entities and links *mean*; object and link types are owned by forge.ontology
- bulk graph analytics (centrality, community detection) that run as forge pipelines

## Steps
1. Model the request as a `GraphQuery` in the graph `openapi.yaml`: `seeds[]` (entity ids),
   `edgeTypes[]`, `direction` (`out|in|both`), `maxDepth`, `maxFanOut`, `limit`, `pageToken`.
2. Implement the query on top of `query.BoundedBFS` in `traversal.go`. Never write a new traversal
   loop; extend `TraversalLimits` if a new bound is needed.
3. Enforce limits server-side regardless of the request: `maxDepth ≤ 4`, `maxFanOut ≤ 200` per node,
   `limit ≤ 5000` nodes per page, wall-clock budget 5 s via the request context. Requests above a cap
   get `INVALID_ARGUMENT`, never a silently clamped result.
4. Return a flat `nodes[]` + `edges[]` pair with `truncated: true` and `truncationReason`
   (`depth|fanOut|limit|timeBudget`) whenever a bound was hit.
5. Pass the caller's RBAC decision as the `VisitFilter` so unreadable nodes are neither returned nor
   expanded; do not post-filter the result.
6. Add a golden test in `src/query/testdata/` with a small fixture graph and the expected node sets
   for each `direction` and each truncation reason.

## Conventions specific to this scope
- Entity ids are `ent_` prefixed; edge ids are `lnk_` prefixed and stable across re-ingestion.
- Edge types are lower_snake strings from the ontology (`part_of`, `located_in`, `derived_from`);
  the API validates them against the ontology cache and rejects unknown types with `INVALID_ARGUMENT`.
- `/v1/graph/paths` is bidirectional BFS with the same limits; `maxDepth` counts hops from either end,
  so the longest returned path has 8 hops.
- Every traversal emits a `graph.query` audit event with seed ids, limits and truncation reason
  (see `security.audit:audit-logging`), never the returned node ids.
- `traversal.go` uses a frontier queue, not recursion, so depth bounds cannot depend on stack size.
- Results are cached for 60 s keyed on the canonicalised request plus the caller's role set.
- No endpoint returns the whole graph; exports go through the pipeline platform as datasets.

## Verify
- `go test ./platforms/atlas/graph/src/query/...` passes, including the property test that
  `BoundedBFS` never visits more than `maxDepth * maxFanOut` nodes per seed.
- `go test -bench BFS ./platforms/atlas/graph/src/query/` stays under 50 ms on the 10k-node fixture.
- `curl -s -X POST localhost:8080/v1/graph/neighbors -d '{"seeds":["ent_x"],"maxDepth":9}'` returns
  400 with `error.code == "INVALID_ARGUMENT"`.
- `make api-lint` passes for the graph `openapi.yaml`.

## See also
- urn:skill:meridian:atlas:atlas-api-conventions (required)
- urn:skill:meridian:atlas.identity:rbac-policies
- urn:skill:meridian:forge.ontology:ontology-modeling
