# ADR-0026: Go SEARCH/USE with ParadeDB and Docker Compose

**Status:** Accepted · 2026-09-05 · explicit product-owner request for ParadeDB,
container deployment and a native service. Acceptance covers this implementation
choice; production admission and retrieval-quality gates remain separate.
**Amends:** ADR-0018 and ADR-0023 for the T1 serving backend; ADR-0025 for its
implementation mapping. T0 and historical experiments remain unchanged.

## Context

The owner requested a database-backed BM25 service in native code and Docker Compose,
with Kubernetes as the next deployment stage. The earlier Python/C++ spike remains
useful evidence but is not the selected implementation target.

## Decision

Implement the complete resident HTTP/validation/policy/selection/database client in
Go. Use ParadeDB 0.25.6 on Postgres 17 for BM25 through Rust/Tantivy, with pinned Docker
image digests and a Compose deployment. The shipped single-file Python CLI is unchanged;
Python remains operator/evaluation tooling, outside the service runtime. Existing C++
dense experiments are retained as evidence, not presented as active sparse execution.

Git commits remain the source of reviewed skill content. Publish digest-verified,
immutable snapshots into Postgres. Activate each head atomically after cards and a
search index exist. Store bodies as bytea and return exact revision/checksum from USE.
Do not fetch bodies into an API-wide cache. Cache immutable routing metadata and read
the authoritative DB head on every request.

BM25 statistics must be isolated per tenant/repository/snapshot. Use a separate
physical search projection/index derived from a trusted identity hash; filtering a
global index would still mix IDF across repositories and versions. Use literal fields
for exact filters and bytewise URN ties so ParadeDB can execute Top K. Preserve the
scope/negative-trigger/closure/selection policy with shared-CLI conformance cases.
The retrieval backend itself is new and advertises its revision; Python BM25F rank
parity is not an acceptance claim. Compare quality on the same pinned inputs.

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

This backend serves sparse BM25. pgvector availability is not dense implementation.
GPU encoding and hybrid fusion need a versioned corpus/model/prompt identity and
independent quality/latency evaluation. Historical dense results remain valid under
their original protocol; neither Go nor ParadeDB establishes a dense-quality verdict.
The native service's frozen comparison is recorded in
[the service protocol](../reports/bakeoff/validation/go-paradedb-protocol-v1.json).
The [completed reference](../reports/bakeoff/GO-PARADEDB-2026-09-05.md) passes loopback
latency but fails quality admission: test-B HSR increases 10.67 pp (allowed +1 pp).
The implementation may be evaluated locally; this does not promote ParadeDB as the
admitted sparse production profile. No default client routing changed.

## Consequences

T1 SEARCH and USE now depend on Postgres availability. The ADR-0018 statement that the
hot path never touches a database applies to T0, not this service. Database loss is
reported explicitly; the current Go API provides no hidden local fallback. Per-snapshot
indexes preserve ranking isolation at a storage/DDL cost; retention/GC and index-build
capacity are required before large multi-tenant rollout.

Runbook and reproducible checks: [services/search](../../services/search/README.md).
ParadeDB documents [literal fields](https://www.paradedb.com/blog/v2api) and
[index configuration](https://www.paradedb.com/docs/documentation/indexing/create-index).
