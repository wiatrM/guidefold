# ADR-0025: One versioned harness-service context contract

**Status:** Accepted · 2026-09-05 · the product owner approved adding the context contract, service changes and conformance tests before the service PR.
**T1 implementation amended by:** [ADR-0026](ADR-0026-native-search-paradedb-compose.md) (Go/ParadeDB/Compose); retrieval and production admission remain separate.
**Amends:** ADR-0023 and ADR-0024, only for the harness-to-service request boundary and compatibility rules. Their production architecture and admission decisions remain Proposed.
**Contract:** [HARNESS-SERVICE-CONTRACT](../HARNESS-SERVICE-CONTRACT.md), [JSON Schema 1.1](../../tools/serve_spike/contracts/harness-service-v1.1.schema.json).

## Context

The E1.1b service originally accepted query and an explicit node. Harness cwd, task identity and other extra fields were silently ignored. The distributed hook already resolves cwd using a versioned index map, but the spike uses a taxonomy corpus without actual monorepo paths. An API that merely accepts metadata without resolving it would not deliver the requested behavior, and independently implemented adapters could disagree about path, team, query and usage semantics.

The owner approved repository-relative cwd and target paths, task/query provenance, harness capabilities, loaded revisions and budgets. The contract must distinguish fields that affect behavior now from future ranking signals. Current service measurements establish latency and exact optimization parity, not the usefulness of every new signal.

## Decision

1. Publish schema 1.1, bounded runtime validation, canonical examples and HTTP conformance tests together. New metadata requires the version. Reject unknown request fields/versions and duplicate keys; tolerate additive response fields on clients. Preserve valid unversioned legacy query/node behavior. Breaking semantics require another version and explicit adapter support.
2. Adapters collect observed facts; agents describe task intent; the server resolves code scope from a configured immutable repository snapshot. The snapshot binds the Git commit, scope map, skill bodies and CLI identity. Client paths never cause server filesystem reads. A path identifies a component/owner, not the user's identity, team membership or authorization.
3. Prefer explicit/edited target paths over inferred paths and cwd. Resolve all selected targets deterministically with at most four distinct scopes. Fail on mismatched repositories/revisions, ambiguous/unmapped paths or excessive scopes rather than silently broadening to root. An explicit `.` retains root semantics.
4. Preserve the shared single-scope Router and exact C++ dense comparator. Multi-scope requests run policy/candidates/score per scope, merge admissible URNs by maximum score then URN and select once. This is a versioned service feature; cross-tier parity is claimed only for equivalent scope/query/configuration. It does not amend the frozen quality gates or claim full composition.
5. Implement exact-revision loaded-card omission and explicit delivery budgets. Never treat exposed cards as hydrated or hydrated content as observed use. Use a labelled byte proxy when the adapter supplies a token hint; the actual harness tokenizer and final rendering remain adapter responsibilities. Return `cannot_fit` rather than silently clipping a pack/body.
6. Validate intent, stack, constraints and capabilities but report them as unused ranking signals until separately admitted. The query passes unchanged to retrieval. A documented agent query recipe and a stdlib reference adapter help harnesses produce useful inputs without an obligatory rewrite-model request.
7. Carry opaque request/session/task IDs, harness identity/version and query provenance through responses and allowlisted server logs. Reuse logical IDs across retries; retain a unique attempt ID. Log resolved scopes/map versions and skill revisions, not raw query, cwd, target paths, skill bodies, tokens or unused free-text hints. Stateless request correlation does not claim event-ledger deduplication; E6.4 retains that responsibility.
8. Gate adapter/service changes on machine-schema and runtime agreement plus real HTTP tests: sibling paths, explicit target precedence, multi-scope determinism, legacy output parity, Python/C++ parity, snapshot/revision mismatch, budgets, loaded-state distinctions and redacted telemetry. Reference adapters for two hook shapes are conformance fixtures, not a claim that vendor harness integrations are deployed.

## Consequences

The contract is executable and reviewable by service and adapter authors. Adding context does not require changing the single-file shipped CLI. A separate serving snapshot includes full skill bodies because the current compact CLI index omits them; one immutable bundle keeps SEARCH and USE aligned. Repository-backed serving is sparse-only until a verified repository embedding pipeline exists. Hybrid experiments remain available on the pinned SKILLRET corpus.

Metadata can now change scope selection and delivery in ways covered by tests. It does not automatically establish retrieval-quality gains, actual skill application, task utility, complete bundles, production IAM, network SLOs or an installed harness integration. Existing historical benchmarks remain immutable; new API code receives new regression/latency evidence. The event vocabulary, spool, ingestion and usability assessment remain governed by ADR-0023 and E6.4/E6.7.

## Native implementation amendment (ADR-0026)

The approved Go/ParadeDB service implements this same 1.1 wire/context contract.
The policy and selection port is checked against 144 shared-CLI cases; native race
checks and real Compose HTTP/publication/recovery tests supplement the Python suite.
Decision 4's Python/C++ implementation and optimization parity remain historical.
The default native backend advertises `router_bm25f_v1` and preserves the reference
CLI BM25F ranking/selection contract. Full BM25F fixtures and the 1,000-query HTTP
parity gate supplement schema compatibility. The explicitly experimental Tantivy
backend has a separate identity and is not admitted as a tier-equivalent ranker.
The active Go service does not run the C++ dense comparator or a GPU encoder.
