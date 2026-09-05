# Harness-service contract 1.1

**Status:** implemented by the Go/ParadeDB Compose service and the historical local E1.1b service; architecture decision [ADR-0025](adr/ADR-0025-harness-service-context-contract.md). This is the shared request contract for adapters and the service, not evidence that any vendor harness integration or production deployment has shipped.

Machine-readable requests and success/error envelopes: [JSON Schema](../tools/serve_spike/contracts/harness-service-v1.1.schema.json). A complete request is in [search-example.json](../tools/serve_spike/contracts/search-example.json). The normative behavioral tests are [test_service_context.py](../tests/test_service_context.py). Both schema and service validation must accept valid requests and reject invalid ones in CI.

## Versioning and ownership

- New contextual requests require `schema_version: "1.1"`. Valid unversioned legacy requests keep their request and response semantics within a backend. Retrieval changes are identified by `backend` and retrieval revision; this does not promise identical ranks or scores between Python BM25F and ParadeDB. Explicit `"1.0"` is not a wire version.
- Unknown versions, unknown fields at every request object level, duplicate JSON keys, invalid types and limits fail with HTTP400. Unknown request fields are never silently ignored. Clients tolerate additive response fields.
- An incompatible field meaning requires a new negotiated schema version. New versions are published with schemas, examples, runtime validation and conformance tests in the same PR. Readiness advertises supported versions. A client must not retry an unsupported version by silently dropping workspace context.
- The adapter owns observed repository-relative paths, request IDs, declared capabilities and actual context delivery. The agent supplies a task query and labels inferred information. The server owns the loaded repository identity, versioned scope map, routing policy, returned revisions and explicit feature status.
- Transport retries reuse `request_id`; each server attempt has its own log `attempt_id`. These IDs enable downstream deduplication. This stateless spike does not cache idempotent responses or verify `search_id` membership. `session_id` and `task_id` are optional; absence means unknown, not a fabricated task.

## Requests and implemented effects

The endpoints remain `GET /health/ready`, `POST /v1/search` and `POST /v1/use`. POST requires the configured local bearer token. Compose publishes the Go API on loopback (the container listens internally on port 8080). Tenant/repository identity is operator-configured; production tenant IAM is not implemented. Each body is limited to 16,384 bytes; SEARCH query is a nonblank UTF-8 string of at most 4,096 characters. Deadline is an integer from 1 to 5,000 ms, default 1,000. Both profiles currently select at most four cards and return at most ten diagnostic ranked candidates.

| Field | Required / effect in 1.1 |
|---|---|
| `query` | SEARCH required. Passed unchanged to the configured retrieval backend: ParadeDB in Go, shared Router/encoder in the historical hybrid experiment. No hidden LLM rewrite, metadata concatenation or translation. |
| `query_source` | Optional `user`, `agent`, `adapter`; diagnostic provenance, not a score multiplier. |
| `workspace.repo_id` | Required within workspace; must exactly match the server-configured repository snapshot. A client cannot select another repository by claiming its ID. |
| `workspace.revision` | Optional exact commit ID. If supplied, must match the loaded snapshot; no silent switch to current. Absence produces `repository_revision_not_supplied` and returns the actual revision. |
| `workspace.cwd` | Repository-relative POSIX path. `.` explicitly means root. No drive prefixes, absolute paths, backslashes, empty segments, `.` segments or `..`. |
| `workspace.target_paths` | Up to 32 `{path, source}` objects. `user_explicit` and `edited` targets take precedence over `inferred` targets; targets take precedence over cwd. Each remaining path must resolve. Up to four distinct scopes. |
| `node` | Legacy/direct-node mode only, mutually exclusive with workspace. It is a routing scope, never proof of identity or permission. |
| `harness` | Name, optional version and adapter version. Recorded for diagnostics and conformance; never changes ranking. |
| `intent`, `stack`, `constraints`, `capabilities` | Validated and explicitly returned under `context.unused_fields` with `ranking_signal_not_admitted`. They do not filter, boost, or rewrite query yet. Do not interpret accepted metadata as admitted ranking behavior. |
| `loaded_skills` | SEARCH: up to 32 exact IDs/revisions and explicit `state`. Only `hydrated` plus matching current revision omits a card from delivery. `exposed`, `unknown` and stale revisions do not suppress it. This is a client assertion of context presence, not observed use or authorization. |
| `budget.max_cards` | SEARCH delivery cap, integer 0..4. Shared selection runs before loaded-card omission; omitted cards are not backfilled. |
| `budget.max_bytes` | SEARCH cap on the UTF-8 bytes of canonical `card_context`; USE cap on the exact body. 0..262,144 bytes. Diagnostic `ranked` data is not intended for injection and is outside this card-rendering cap. |
| `budget.remaining_skill_tokens` | Optional 0..65,536 hint. Uses a deliberately conservative UTF-8-byte proxy, explicitly labelled in SEARCH accounting. This is not an exact model tokenizer. The adapter must verify final harness token count, including wrappers. |
| `request_id`, `session_id`, `task_id` | Opaque identifiers for correlation. No ranking/personal-productivity signal. Request/task/session IDs are returned and recorded after validation. |

IDs use `[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}`. List/string limits and required nested fields are in the schema. `intent.action` is one of implement/debug/review/test/migrate/deploy/document/explore; `intent.source` identifies user/agent/adapter. Stack supports languages, technologies, source (manifest/user/inferred) and manifest revision. Constraint and capability values are bounded strings, not executable directives.

USE requires the `skill_id` and exact `revision` returned by SEARCH; optional `search_id` is correlation only. For contextual USE, the service rechecks active status, revision and visibility within the resolved scopes. It does not claim a production ACL check. Missing resources, stale revisions and disallowed scopes never silently hydrate another revision.

## Scope resolution and retrieval

The immutable serving snapshot binds repository ID, exact Git commit, scope map, card bodies, weights and builder CLI SHA. Its content digest is returned as `snapshot`; `scope_map_revision` identifies the map. A snapshot built with a different CLI source is rejected before readiness. Operator-provided bundles are local trusted configuration with integrity checks, not signed authorization artifacts.

The builder reads only committed `guidefold.yaml` and skill files. Uncommitted edits, current terminal paths on the server and filesystem changes after startup cannot change routing. The server never opens a path supplied through HTTP. Repository bundles currently support optimized sparse only; hybrid remains the pinned SKILLRET experiment until a separately verified repository embedding builder exists.

Path matching preserves the current node resolver's longest matching glob rule. Equal-specificity matches across distinct nodes fail as ambiguous. A non-root path covered only by the root catch-all fails as unmapped; `.` is an explicit root request. Missing or stale context cannot silently broaden to root. Scope identifies a code area and its owner, not the requester's team membership. Authentication and future tenant authorization remain separate.

For one scope, the existing `policy_filter → candidates → score → select(admissible)` pipeline is preserved. For multiple scopes, each runs the same query and shared policy; only admissible rows participate. Duplicate URNs retain their maximum score, then sort by descending score and URN. Selection runs once over the admissible union. Scope input order cannot change the result. This deterministic merge is a contextual routing feature; it is not a retrieval-quality admission or a new composer. Full bundle completeness stays `not_evaluated`.

The C++ kernel remains the exact dense ordering implementation behind the same candidate boundary. It does not infer teams, parse JSON, grant access or change metadata weights. CPU tests exercise Python/C++ parity with different resolved scopes and guarded integer bounds.

## Response and delivery semantics

SEARCH returns cards with immutable revisions, diagnostic ranked rows, `search_id`, snapshot/policy identity, timings and context evidence. Context includes resolved scopes/owners, map revision, scope source, used fields, unused fields and warnings. Per-card `eligible_scopes` means policy eligibility, not a claim that a lexical/semantic match caused selection.

Only canonical `card_context` is eligible for automatic injection. The adapter must not inject the diagnostic candidates or the request's unused metadata. If the selected delivery pack exceeds a byte/proxy budget, return no cards and `delivery_status: cannot_fit`; never truncate a pack into a supposedly complete closure. Removing already-hydrated cards is reported separately from retrieval abstention. The adapter remains responsible for the actual token budget and prerequisite handling.

USE returns full body and SHA-256 checksum, never a clipped body. An explicit body budget overflow returns HTTP413. The local response's `status: hydrated` means content was prepared; `execution_observed: false` and `search_id_verified: false` remain explicit. Client checksum verification, context injection, application and usefulness are separate evidence events in [SEARCH-USE-TELEMETRY](SEARCH-USE-TELEMETRY.md). The event ingestion endpoint and bounded durable spool remain E6.4/E2.7 work; this PR does not implement them.

Errors: 400 invalid schema/context/query; 403 contextual USE outside scope; 404 unknown skill; 409 wrong repository/revision or repository context unavailable; 413 request/body cap; 422 unresolved/ambiguous/too-many scopes; 429 overload; 503 not ready; 504 deadline exceeded. A deadline is checked around stages and does not hard-cancel a running GPU forward. Clients handle non-JSON transport errors and early overload replies without assuming correlation fields are available.

## Adapter and query recipe

The reference [harness_adapter.py](../tools/serve_spike/harness_adapter.py) accepts `prompt` or `user_prompt` plus observed cwd. It normalizes absolute local paths against an explicitly configured repository root, resolves symlinks locally and rejects paths outside that root. It emits a 1.1 JSON request; it does not install hooks, send HTTP or assume vendor-specific hook availability. Supplied task/session IDs must have adapter-defined semantics. The same request ID is reused for a retry.

An automatic hook may send the unchanged user prompt with observed metadata immediately. An agent can make another explicit SEARCH after identifying the precise task. Instruct it:

> Write action + concrete problem/artifact + material constraints. Preserve technology names, symbols and error identifiers. Use the current task rather than only a last message such as “fix it”. Do not invent facts or infer identity/permissions. Keep negative constraints and provenance. Do not paste transcripts or private chain-of-thought.

For example: “Fix duplicate payment processing after Kafka redelivery while preserving the event schema.” The adapter supplies paths and observed capabilities. The model is not responsible for guessing repository paths or the owner's team. No per-query rewriting service or training step is required.

## Running and verifying

From the repository root in Linux, with `GF_PY` pointing at the existing Python environment:

```bash
"$GF_PY" tools/serve_spike/repository.py \
  --repo-root examples/monorepo --repo-id meridian --revision HEAD \
  --output .guidefold/serve-spike/meridian.json

"$GF_PY" tools/serve_spike/server.py --disable-model --optimized \
  --repository-snapshot .guidefold/serve-spike/meridian.json \
  --token-file .guidefold/serve-spike/token --port 8765

"$GF_PY" -m pytest tests/test_service_context.py
```

Create the local token as described in the [service README](../tools/serve_spike/README.md). The snapshot builder supports a monorepo fixture nested inside this tool repository. It serves full SKILL.md bodies, not auxiliary asset download endpoints. Do not commit generated snapshots or tokens.

Every adapter release must pass schema validation, normalization examples and real HTTP SEARCH→USE tests against a pinned service version. Test observed path changes, explicit targets, multi-scope ordering, unknown/ambiguous paths, stale snapshots/revisions, capabilities unavailable to observe, loaded-state distinctions, budgets, retries and redacted logs. The fixture demonstrates contract behavior only. Retrieval gains require separate real task/context evaluation; SKILLRET latency queries do not contain real repository paths.

## Go/ParadeDB implementation

[ADR-0026](adr/ADR-0026-native-search-paradedb-compose.md) selects the native service.
It reads the active snapshot and candidate/body data from Postgres. Metadata alone
is cached. A separate BM25 index per immutable tenant/repo/snapshot keeps document
frequencies isolated. A client path never chooses a SQL table or server file.

`GET /health/live` is process liveness; readiness requires a compatible published
snapshot and a reachable database. Requests are bounded to eight simultaneous
operations; excess admission returns 429. Deadlines cover validation, pool waits and
SQL work; 504 means the deadline expired. Database errors return 503. Context policy,
budgets, checksums and exact revision checks retain the semantics above.

Native conformance: [Go tests](../services/search/routing_test.go),
[Compose integration tests](../tools/search_service/smoke.py) and the
[deployment runbook](../services/search/README.md). These use the existing normative
JSON Schema, including generated request IDs and safe additive response fields.
The native retrieval revision is distinct; performance and matching quality are
measured separately from policy compatibility. Dense is explicitly disabled.
