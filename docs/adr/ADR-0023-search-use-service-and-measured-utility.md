# ADR-0023: Central SEARCH/USE service, bounded hooks, and measured skill utility

**Status:** Proposed · 2026-09-05 · requested MVP revision; no service is deployed by this ADR
**Proposes amendments to:** ADR-0009 (serving location), ADR-0013 and ADR-0018 (online service dependency), ADR-0015 and ADR-0020 (resident contextual models), ADR-0021 (local artifact budget), ADR-0016 (usage is not probation success).
**Preserves:** Git as source of truth, owner approval, one Postgres, GCS artifacts, single-file stdlib + PyYAML client, and ADR-0022's eligibility/composition requirements.
**Delivery:** [MVP](../MVP.md), immediate blocking **E1.1b service feasibility**, then E2 client/distribution and new E6 service/measurement. Existing E3 remains promotion; story IDs are not renumbered.

## Context

The user wants organization-scale SEARCH and USE, usage and usability measurement, and an updated MVP. A 15 MB static word table is one offline model profile, not a compressed contextual encoder. The sparse hook measured p95 638.9 ms at 6,006 skills. Cached full-encoder reference runs improve some quality metrics, but precomputed query vectors do not establish online latency. These facts justify testing resident serving, not declaring a neural winner.

The promotion-first MVP defers telemetry and assumes database vectors are offline-only. It also mixes loads with positive outcomes. We need an observable retrieval-to-use path before popularity informs improvement or lifecycle decisions.

## Decision

### 1. One product API, one inference worker

Implement SEARCH/USE as a module of the planned Knowledge API, not a second control plane. The CPU API owns authentication, authorization, policy, retrieval, composition, hydration and event ingestion. A separately deployable GPU worker holds the pinned encoder and optional reranker. Separate queues/budgets ensure reranking and CI indexing cannot starve hook queries. Start with one pilot region and at most one warm GPU replica; HA and multi-region routing are outside MVP. Deployment and cloud spend are future implementation actions, not performed by this plan.

Git keeps canonical skill text and approvals. GCS holds immutable checksummed bodies and index snapshots. One Postgres stores revision/permission metadata, vector projections, events, rollups and the thin promotion decision log. The CPU service loads a versioned sparse/vector snapshot into memory. Start with exact vector search at measured pilot size; ANN needs a measured recall/latency benefit. No additional Qdrant, OpenSearch, Kafka or BigQuery deployment is needed for MVP.

Online permission/status validation may depend on Postgres. A telemetry-write outage must not block retrieval; inability to establish authorization denies restricted hydration. Do not claim all database failures are harmless. Local fallback has a separate, bounded authorization lease.

### 2. Two SEARCH profiles and an explicit USE contract

| Operation | Contract |
|---|---|
| `POST /v1/search`, `profile=hook` | Task, permitted repo context and requested snapshot; eligibility, BM25 plus admitted contextual candidates, fusion and composition; <=4 cards and a configured token cap. No reranker by default. |
| `POST /v1/search`, `profile=interactive` | Same policy and version identity; explicit SEARCH/find may request bounded reranking. Candidate count, text truncation and deadline recorded. |
| `POST /v1/use` | Resolve selected `skill_id@revision`, revalidate current authorization/status/dependencies, and return a checksummed body/resource manifest or refusal. Optional `search_id` supports direct use. No arbitrary remote execution. Successful delivery does not prove application. |
| `POST /v1/events:batch` | Versioned, idempotent, bounded ingestion; accepted/duplicate/rejected IDs allow retries without duplicate usage counts. |

SEARCH responses contain `search_id`, snapshot/model/pipeline/policy versions, actual profile, ordered skill IDs/revisions, reasons, composition status, timings and degradation reason. Authenticated identity establishes tenant and permissions; `team`, `cwd` and scope supplied by the client are context, never authority. Eligibility applies to candidates, reranker inputs and dependency expansion. Return explicit `cannot_fit`/`unresolved`; retrieval cannot certify exhaustive task completeness.

`guidefold find` and `load` remain compatible entry points; proposed `search`/`use` aliases share their client code. Local/offline mode remains first class. No ML library is added to the distributed CLI. The reranker's predicted USE/SKIP score is a relevance estimate, unrelated to a runtime use event.

### 3. End-to-end deadlines and declared degradation

Proposed targets, to validate rather than advertise as achieved:

E1.1b service protocol v2 (2026-09-05) requires whole-client p95 ≤400 ms over loopback, measured separately at c1 and c4 with a fresh client process per request and a ready resident server/index. Server-side p95 must be ≤300 ms at both loads, measured from HTTP admission before authentication or queueing through synchronous logging and JSON response serialization. Whole-client timing includes startup/imports, local reads, auth, transport, queues, retrieval/composition, telemetry and output/exit. Report all attempts, errors and successful-within-budget counts under frozen workload, corpus, hardware and runtime identities. WAN/TLS/IAM and the actual harness remain a separate E6 integration gate, never implied by loopback success. Optimized sparse is the production candidate; hybrid remains shadow until independent latency and quality admission.

Protocol v2 uses inclusive ≤ comparisons. Historical T300/T500 budgets and E1.1b JSON evaluated with strict <400 retain their original definitions and results. Historical T300 means the whole hook in a fresh process, not an in-process kernel or the new server-side 300 ms target. A p95 target is not hard cancellation; the server allocation provides planning headroom, not a guarantee that the client target passes.

See [E1.1b service feasibility](../reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md) for measured results and the final decision.

- Retain a separate portable 3 s crash watchdog; it is not the normal timeout or SLO.
- Interactive SEARCH client-observed p95 <=1 s initially, including requested reranking. Measure encoder-only and reranked profiles separately; disable the latter if it cannot meet its budget.
- USE has separate cache-hit/cold-hydration p50/p95, error and byte metrics. It is outside the automatic hook budget. Freeze its pilot target from measured bundle sizes in week 1.

Start a permitted local sparse fallback alongside the remote request; enforce one monotonic absolute deadline and cancel/ignore late work. A remote response may replace fallback only before output is finalized. Timeout equals remaining budget minus measured local/output costs, not a universal guessed 180 ms. Test cold token refresh/TLS, overload, model restart and index loading. Current full-index loading must be optimized or narrowed before it is a fast fallback.

Only scoped, checksummed caches with an unexpired authorization lease may serve protected content offline. Proposed lease maximum: 10 minutes since last online validation, with restricted scopes offline-disabled by default. An explicit online denial/revocation invalidates the cache and cannot trigger a bypass. Revocations during disconnection are detected within the lease, not instantly; expired leases refuse protected delivery. Explicitly public/local skills have a separate offline policy.

Record backend `online_hybrid`, `online_sparse`, `local_sparse` or `none` (no backend ran), separately from terminal status (including `abstained`) and cache source; include the degradation reason. Pinned local replay may retain deterministic output; network fallback changes results for the same prompt. Replay identity covers profile, snapshot, pipeline/policy/model versions and recorded inference output. No cross-GPU bit-identity promise.

### 4. CI publishes consistent versions

Embed only added/changed skill text using pinned model/tokenizer/template/truncation/pooling/normalization identity. Changing that identity rebuilds the affected complete vector set. Deletes remove sparse/vector entries and invalidate hydration eligibility. Publish a new manifest only after bodies, sparse/vector indices, dependencies and policy metadata verify together. Never mix embedding spaces or silently serve latest when a pinned revision is missing.

Preload then atomically swap a verified snapshot, retain a rollback version, and recheck current authorization/status at USE even for older content snapshots. Unpublished local edits default to a local-only profile; remote transmission of working-tree text needs a separate opt-in workflow. No background upload of source files is introduced.

### 5. Measure evidence, not a fictional USE counter

The normative [telemetry contract](../SEARCH-USE-TELEMETRY.md) separates search results, card exposure, hydration, self-reported application, adapter-observed invocation, feedback and task outcome. `/use` success means delivery. Applying free-form instructions is generally not directly observable. Cache delivery counts as loading; prewarm does not count as usage. Missing instrumentation/feedback is unknown, not success or zero use.

Three primary product views: observed adoption/reuse with coverage; revision-specific judged usability with feedback coverage; controlled task utility versus no-skills and sparse baselines. Offline completeness is a quality gate/diagnostic. Operational latency/errors/fallback, harmful exposure and delivery-policy violations are guardrails. Every rate includes counts, denominator, revision and profile. No individual productivity leaderboard, automatic retirement from low traffic, or promotion from popularity.

Prompt text is transient SEARCH input, excluded from normal logs/traces/spool by default. Opaque task IDs and tenant-scoped keyed fingerprints support joins; pseudonyms are not anonymous. Redacted query samples for evaluation/training require separate opt-in. Raw events have an initial 90-day retention with actual deletion of subject-linked events/rollups; salt rotation is not erasure. Service traces use the existing observability backend; business rollups use Postgres. No synchronous network telemetry exporter runs in the hook.

### 6. Rebaseline MVP around delivery and evidence

E1.1b first validates the optimized sparse HTTP service with startup, latency, concurrency, failure/fallback and revision delivery evidence; live-encoder and separate-worker experiments remain hybrid shadow work. Review its proceed/change/stop decision before service-dependent E2/E6 implementation; a local benchmark does not establish target-network/TLS/IAM performance. E2 then delivers distribution and thin clients; E6 delivers the operational service and measurement. E1 closes scorer/evaluation/composition blockers. Preserve a concierge owner-reviewed E3 slice, basic E4 validation/withdrawal and one diagnostic E5 view. Defer automated induction, full promotion orchestration, automatic probation promotion, custom graph UI, own training and HA. Eight weeks from this revision at 2 engineers +0.5 ML is a capacity estimate with narrower scope, not an extension that retains every old feature.

Admission requires a corrected sparse baseline, independent labelled tasks, common denominators including empty results, shared eligibility/composition, and whole-client latency under load. Cached query embeddings cannot pass the serving gate. Ship the same API with sparse retrieval if no contextual profile earns adoption. Freeze the prospective remote experiment separately; do not rewrite DENSE-PROGRAM's historical, pre-registered sections after seeing results.

## Consequences

- Central serving removes repeated catalog/model startup but adds network dependency, an idle GPU bill and an operational owner.
- 15 MB governs only a measured local artifact/profile, not the server model/catalog. A static student is optional if it improves the measured tradeoff.
- One service plus durable evidence is MVP work; a service fleet and warehouse are not. Telemetry loss/lag remains visible.
- This is a proposed amendment. No historical milestone, benchmark or approval is relabelled as completed by editing the plan.

## Evidence and operational references

- [Whole-hook latency and contextual reference](../reports/bakeoff/SKILLRET-test-2026-09-05.md), [test-B and limitations](../reports/bakeoff/SkillRetBench-R1-encoder-2026-09-05.md), [sparse diagnosis](../reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md).
- [SkillRouter v5](https://arxiv.org/html/2603.22455v5): authors' encoder/retrieval p95 20.8 ms; top-20 full pipeline 871.4 ms. Neither is our API SLO.
- [Cloud Run GPU](https://docs.cloud.google.com/run/docs/configuring/services/gpu): minimum GPU instances incur idle charges; [minimum instances](https://docs.cloud.google.com/run/docs/configuring/min-instances) reduce cold starts, not an end-to-end guarantee.
- [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/): technical traces/metrics/logs complement the product event contract.
