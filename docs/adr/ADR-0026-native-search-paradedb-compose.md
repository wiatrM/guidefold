# ADR-0026: Go/Postgres hosting and Docker Compose for SEARCH/USE

**Status:** Accepted · 2026-09-05 · explicit product-owner request for ParadeDB,
container deployment and a native service. Acceptance covers this implementation
choice only. **Corrected 2026-09-05 after PR #50 review:** this ADR does not authorize a second default ranker. ADR-0024 tier parity remains binding; production admission remains separate.
**Amends:** ADR-0018 and ADR-0023 for the T1 serving backend; ADR-0025 for its
implementation mapping. T0 and historical experiments remain unchanged.

## Context

The owner requested a database-backed BM25 service in native code and Docker Compose,
with Kubernetes as the next deployment stage. The earlier Python/C++ spike remains
useful evidence but is not the selected implementation target.

## Decision

Implement the resident HTTP/validation/policy/selection/database client in Go, with
Postgres (the pinned ParadeDB distribution) and Docker Compose. The shipped
single-file Python CLI remains unchanged. Python is operator/evaluation tooling,
outside the service runtime.

**The default ranker is the same integer BM25F Router as T0.** Its build-time IDF,
field norms and postings are exported by the reference CLI, bound to the CLI SHA
and immutable snapshot. Go compiles the identical per-term fixed-point contribution
and stores packed postings in Postgres. At query time Go reads only matching term
postings, sums contributions including query term frequency, applies admissibility
before top-50, and uses the shared RRF/scope/closure/selection policy. There is no
Tantivy candidate cap on this path: it could discard a true BM25F top candidate.
Use all-integer arithmetic, including Python-equivalent arbitrary precision while
compiling large weighted term frequencies. CI compares complete BM25F score maps
from the CLI and policy vectors; the service gate compares 1,000 frozen DEV queries
through HTTP with CLI top-10 scores/order, selected skills and revisions.

`GUIDEFOLD_LEXICAL_ENGINE=router` is the default. The previous
`paradedb-experimental` mode is retained only for reproducing the explicitly failed
Tantivy experiment. It advertises a different backend and makes no tier-parity
claim. It is not an automatic fallback. Changing the default ranking requires its
own decision and quality admission; this hosting ADR cannot grant either.

Git remains the source of reviewed content. Cards, reference router index, optional
Tantivy search projection and active head publish atomically. Index identity is
immutable per tenant/repository/snapshot. An old snapshot without a router index
fails readiness until re-published by the updated operator tooling. USE returns
exact stored bytes, revision and checksum; API metadata caches omit bodies, and
every request reads the authoritative DB head. Retained experimental Tantivy
indexes isolate IDF per snapshot and use literal fields and bytewise ties.

API 1.1 remains normative for both runtimes and harness adapters. Tests cover schemas,
real HTTP, multi-scope behavior, exact revision hydration, loaded-state/budget handling,
publication, tenant/repository isolation, failure and restart. Allowlisted diagnostics
carry correlation/harness IDs, resolved scopes, map versions and card revisions;
queries, source paths and bodies are not logged. These logs do not implement the
E6.4 durable event ledger, client spool or observed-use attribution.

Compose uses a non-root static Go image, a read-only API DB role, separate admin jobs,
local secret files, persistent DB volume, loopback-only API port, probes and graceful
shutdown. It is the current deployment target. Kubernetes is the next stage, using
Deployment/Service plus migration/publication Jobs and a compatible Postgres operator
or managed provider. TLS/IAM, HA, backups/restore, retention, network load and durable
telemetry require their own validation. A working Compose stack is not production sign-off.

## Dense and quality

The default backend serves reference sparse BM25F. pgvector availability is not dense implementation.
GPU encoding and hybrid fusion need a versioned corpus/model/prompt identity and
independent quality/latency evaluation. Historical dense results remain valid under
their original protocol; neither Go nor ParadeDB establishes a dense-quality verdict.
The native service's frozen comparison is recorded in
[the service protocol](../reports/bakeoff/validation/go-paradedb-protocol-v1.json).
The [completed reference](../reports/bakeoff/GO-PARADEDB-2026-09-05.md) passes loopback
latency but fails quality admission: test-B HSR increases 10.67 pp (allowed +1 pp).
Those measurements describe the experimental Tantivy ranker, not the corrected
default BM25F path. They remain unchanged and do not admit that ranker. No default
client routing changed. GPU remains a separate experiment with its own admission.

## Consequences

T1 SEARCH and USE now depend on Postgres availability. The ADR-0018 statement that the
hot path never touches a database applies to T0, not this service. Database loss is
reported explicitly; the current Go API provides no hidden local fallback. Per-snapshot
indexes preserve ranking isolation at a storage/DDL cost; retention/GC and index-build
capacity are required before large multi-tenant rollout.

Runbook and reproducible checks: [services/search](../../services/search/README.md).
ParadeDB documents [literal fields](https://www.paradedb.com/blog/v2api) and
[index configuration](https://www.paradedb.com/docs/documentation/indexing/create-index).
