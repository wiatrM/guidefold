# SEARCH, USE and skill telemetry — MVP contract

**Status:** Proposed · 2026-09-05 · implementation scope: [MVP E6](MVP.md).
**Owners:** Platform owns collection and availability; ML owns retrieval evaluation;
skill owners review usability evidence and decide changes through GitHub.

This contract refines [KNOWLEDGE-DESIGN](KNOWLEDGE-DESIGN.md) §4 telemetry,
§5 probation and §9 privacy. The older `loaded → outcome` shorthand, plain prompt
hashes and treating salt rotation as erasure do not apply to the proposed MVP.
The [local E1.1b spike](../tools/serve_spike/README.md) implements experimental
SEARCH/USE endpoints. This production contract remains Proposed; the spike does
not implement its full authorization, dependency, delivery or event guarantees.
Its server event `use_hydrated` means a revision response was prepared, not that a
client verified or hydrated it, an agent used it, or anyone assessed its usability.
It is not `skill_load_completed`, `skill_use_observed` or usefulness evidence.

## 1. What SEARCH and USE mean

SEARCH returns permission-filtered skill cards for an intent and scope. USE resolves
an explicit skill selection to permitted immutable content, verifies its revision
and dependencies, and lets the adapter hydrate it into the agent's context.
USE does not execute arbitrary remote code. A successful HTTP response proves
content transport/availability, not that the agent read or applied its instructions.

Keep these distinct: returned result, injected card, requested load, completed load,
reported application, observed invocation, and assessed outcome. A rendered card is
an exposure; even observed invocation does not prove correct procedural execution.

The journey is not always linear: explicit USE may have no SEARCH; a cached revision
may be reused without another download; a task may SEARCH several times; one USE
may expand into several dependencies. Record explicit links, not nearest timestamps.

## 2. API boundary

| Endpoint | Request | Response / contract |
|---|---|---|
| `POST /v1/search` | `request_id`, `search_id`, task/session IDs, transient query, scope, profile (`hook`/`interactive`), remaining deadline, optional pinned snapshot | Ordered cards with URN + revision, reasons, scores, dependency metadata, snapshot/model/policy versions, timings and terminal status. Hook returns ≤4 cards; interactive ≤8; debug candidates ≤20. |
| `POST /v1/use` | `request_id`, `use_id`, task/session IDs, optional `search_id`/`exposure_id`, selected URN + revision or explicit `current` selector, scope | Permission-revalidated immutable revision, integrity digest, dependency closure, body or scoped download reference, per-item status. Default hydration ≤4 skills including required dependencies, under a configured token/byte cap. If the required closure does not fit, return `cannot_fit`; never count a digest as a fully hydrated body. Further resources require explicit requests. |
| `POST /v1/events:batch` | Schema-versioned events with stable `event_id`; no raw query or skill body | Per-event `accepted` / `duplicate` / `rejected`, with retryability and reason; retry only unacknowledged/retryable items using the same IDs. |

Authenticate each request. Derive tenant and effective principal from the verified
credential; client-supplied tenant/scope never grants access. Apply authorization
before retrieval and again at USE, including all dependencies and cached revisions.
Scope filters and ranking preferences cannot bypass permissions.

For an explicit revision, return it only if still allowed; never silently substitute
`current`. For `current`, resolve once and return the exact revision selected. An
authorization change between SEARCH and USE may produce `denied`. Offline loads
follow an explicitly bounded cached authorization policy and identify its age;
without valid offline authority, the client abstains. Signed download references are
short-lived and never logged. Cached content itself does not establish permission.

Use stable operation IDs across transport retries. Revalidate permission on retries;
idempotency does not freeze authorization. Do not count retries as extra usage.
Partial dependency failures are explicit: the response cannot label an incomplete
required closure as a complete load. The client confirms actual hydration separately.

SEARCH status includes `ok`, `abstained`, `deadline_exceeded`, `denied`, `unavailable`
and `error`; backend is `online_hybrid`, `online_sparse`, `local_sparse` or `none` (no backend ran). Cache source is a separate field; composition status separately identifies `complete`, `unresolved` or `cannot_fit`.
Also return `fallback_reason`, actual snapshot, candidate/selected counts and caps
applied. A zero-result abstention is different from a service failure. A late remote
result never replaces an already emitted fallback within the same hook invocation.

## 3. Event vocabulary and evidence

| Event | Producer and meaning | Required specific fields |
|---|---|---|
| `search_requested` | Client begins one logical SEARCH. | `search_id`, profile, scope, deadline, optional query HMAC |
| `search_results` | Client receives the result it actually uses, including a local fallback or terminal failure. | `search_id`, mode/status, ordered skill revisions, scores/ranks, timings, fallback reason |
| `card_injected` | Adapter emitted a card into harness context; exposure is not confirmed attention. | `exposure_id`, `search_id` if known, skill revision, position, surface, delivery evidence |
| `skill_load_requested` | Client requests a selected revision, directly or through USE. | `use_id`, `load_id`, skill revision/selector, source (`search`/`explicit`/`dependency`/`cache`) |
| `skill_load_completed` | Client verified and hydrated that revision, or records terminal failure. | `load_id`, resolved revision if known, status, cache source, bytes/chars, duration, closure completeness |
| `skill_use_reported` | Agent/user explicitly says it applied a skill. This is self-report. | skill revision, source, linked load/use if known, report category |
| `skill_use_observed` | Adapter captures an explicit skill invocation or invocation of its identified script. | skill revision, adapter/evidence type, opaque evidence reference, linked load/use if known |
| `skill_feedback` | A user or named evaluator assesses one task–skill–revision episode. | `judgment_id`, verdict (`helped`/`hindered`/`mixed`/`not_applicable`/`unknown`), reason category, source |
| `task_started` | Adapter marks every eligible pilot task, including tasks with no SEARCH or USE. | task ID, pilot cohort, eligibility and observation capability |
| `task_finished` | Adapter observes task termination and, when available, its assessed result. | task ID, terminal status, outcome (`success`/`failure`/`unknown`), outcome source, observation coverage |
| `telemetry_health` | Client publishes aggregate delivery diagnostics. | produced/acknowledged/dropped counts, oldest queued age, capability flags, reporting window |

Server request logs and traces measure transport, auth, GPU, queue and index behavior;
they are not extra client usage events. A server response is never relabelled as
`skill_load_completed` or `skill_use_observed`. `card_injected.delivery_evidence`
distinguishes context emitted from harness receipt acknowledged; unsupported receipt
and invocation observation are `unknown`, not fabricated successes.

An adapter emits `skill_use_observed` only for supported evidence types such as
`native_skill_invocation` or `skill_script_invocation`. Reading Markdown, mentioning
its name, or the agent claiming it used the skill is insufficient. Record adapter
capability/version; measure self-report and observation separately, deduplicating
their linked episode when showing a combined count. Never add them blindly.

## 4. IDs, versions and event grain

Every event carries `schema_version`, `event_id`, `event_type`, `occurred_at`, client
sequence, `producer`, adapter version, environment (`pilot`/`eval`/`dev`), and
`session_id`, `task_id`, `correlation_id` where available. Ingestion adds server
`received_at`, verified `tenant_id` and a scoped pseudonymous principal identifier.
Absent task/session IDs are explicitly unknown and excluded from task-level ratios.

SEARCH links use `search_id`; USE uses `use_id`; each skill's hydration has `load_id`;
each exposure has `exposure_id`. Child loads carry `parent_use_id` and relation type.
Resolved skill events carry logical `skill_id` (URN) **and exact immutable revision**.
Unresolved requests retain their selector; exclude them from revision-level outcomes.
Never combine revisions into one quality estimate without a version filter.

Capture `index_snapshot`, `model_profile` (model + pinned revision or `none`),
`router_version`, `policy_version`, configuration/experiment version and cache mode.
Authorization decisions include policy version; cached result keys also include the
authorization boundary, snapshot and model/router versions. Backend and client
timings use their own monotonic clocks; do not subtract unsynchronized timestamps.

Events retain their original tenant/principal binding and pseudonym-key epoch. Partition the local spool by that origin; flush only with a verified matching identity/tenant. A login or tenant switch must quarantine the old partition until the original authorized identity returns, never relabel it as the new uploader. Delegated upload is deferred. Do not store bearer tokens in the spool.

Store an append-only event ledger with unique `(tenant_id, event_id)`. Distinguish
transport duplication from a legitimate second use. Rollups count unique
`(tenant, task, skill, revision)` episodes for adoption/usability, and logical
`search_id`/`load_id` for operations. Retain invocation counts as a separate diagnostic.
Out-of-order events join by IDs; missing links remain unknown. A correction references
the prior `judgment_id`; it does not create two votes for the same evaluator/episode.

## 5. Collection and data boundaries

Reuse the Knowledge API and **one Postgres** for events, metadata and daily rollups.
Keep the SEARCH index and warmed models in serving memory; do not add an analytics
database or require a telemetry database write before returning SEARCH/USE.
Git remains canonical for skill text; telemetry stores revision references.

Collection is asynchronous through a bounded local spool: proposed defaults 10 MB,
7-day maximum age, and batches ≤100 events / 256 KB. Spool only allowlisted fields;
never spool queries, content, secrets, file paths, download URLs or tool output.
Retry with capped exponential backoff and jitter; process partial acknowledgements.
Eviction/drop reasons increment health counters. A telemetry outage never blocks the
hook; lost events reduce reported coverage and cannot be interpreted as no usage.

Enable upload through explicit organization configuration with visible diagnostics.
Retain event-level product telemetry for 90 days; proposed daily aggregate retention
is 12 months. Enforce expiry and deletion in both events and derived tables, with
backup handling documented before rollout. Security audit retention is a separate
policy; product prompts and individual performance data do not enter that log.

Raw prompts exist transiently for SEARCH inference and are not saved by default,
including in access logs, traces, exception reports or telemetry spools. Optional
query grouping uses a tenant-scoped keyed HMAC, never an unkeyed prompt hash.
Principal pseudonyms use a rotating tenant-scoped HMAC key; rotate monthly and label
cross-month person-based counts incomparable. HMACs are pseudonymous, not anonymous;
key rotation is not a substitute for deletion. Curated evaluation examples require
separate redaction and consent/organization policy, storage and access rules.

Tenant access controls apply to events and rollups. Show owner/team aggregates,
suppress small person-based cohorts, and provide no individual productivity ranking.
No raw agent traces or external analytics exporter is required by this MVP.

## 6. Three primary KPIs

| KPI / decision | Grain, numerator / denominator | Eligibility, caveat and owner |
|---|---|---|
| **Observed skill adoption**: decide where onboarding/integration needs work. | Pilot task: tasks with ≥1 `skill_use_observed` / completed instrumented pilot tasks with known IDs and supported, complete observation. | Fix pilot scope before measurement; include tasks with zero skill use. Report excluded/unknown tasks and adapter coverage beside the ratio. Self-reported adoption is separate. Platform owns it. |
| **Judged skill usability**: decide which skill revision needs repair. | Task–skill–revision episode: `helped` / (`helped` + `hindered`), using one designated user/evaluator judgment per episode. | Show `mixed`, `not_applicable`, `unknown`, missing feedback and judgment coverage separately. Do not pool agent self-ratings with human/evaluator ratings. Skill owner owns it. |
| **Controlled task utility**: decide whether serving skills improves work. | Paired evaluated scenario: gain rate = baseline failure → selected-skill success / all paired evaluable scenarios; regression rate reverses the transition. | Pin inputs, model, harness and evaluator; compare selected skills with no skills and sparse routing; include oracle and wrong-sibling controls. Report residual failures, time/tokens and unknown evaluations. ML owns it. |

Operational usage includes unique loads, reported/observed application episodes,
invocations and repeat use across distinct tasks/scopes. Observation coverage is
fully observed closed pilot tasks / all known closed pilot tasks; show open tasks and
missing terminal markers separately. Feedback coverage is judged episodes / known
loaded-or-applied episodes, deduplicated by task–skill–revision. Unsupported adapters,
telemetry gaps and missing IDs remain unknown; exclusions cannot silently improve KPIs.

Per-skill cards show revision/owner/scope, eligible search results, actual exposures,
loads, observed/reported episodes, unique scopes, judged usability, feedback coverage,
reason categories, freshness and the reporting window. Compare within the same
adapter, mode, rank/position and cohort where possible: exposure and task selection
bias usage. Low usage alone is neither poor usability nor a retirement trigger.

Use a 95% Wilson **lower confidence bound** for the binary judged usability proportion
when displaying conservative evidence; its denominator is judged positive + negative
episodes, never loads. At least five judged episodes is an eligibility floor, not
proof of adequate sample size. A bound ≥0.6 can support an owner's probation review
only alongside no unresolved harmful/wrong report, coverage and controlled evaluation.
Usage volume, a successful task, or absent negative feedback never promotes a skill.

## 7. Guardrails and diagnosis

Retrieval release gates include Completeness@4 (all judged required skill groups in four
cards / all answerable labelled queries, with empty or infeasible bundles scoring zero), Hit@1, nDCG and abstention correctness. Also report feasible-only completeness and its denominator; never remove disallowed required skills from gold to inflate completeness. Run the
product policy→candidate→score→select path on pinned real held-out corpora and partner
queries when available. The fixture is regression evidence only. These diagnose
SEARCH quality separately from product adoption, usability and controlled task utility.

Guardrails are (1) delivery reliability/cost and (2) evidence quality/safety. Break
down client SEARCH p50/p95, whole-hook p50/p95, timeout/fallback rates, load completion
rate and rejection reasons, queue depth, GPU utilization and cost per 1,000 requests.
Pair them with unauthorized disclosures (target zero), closure/cap violations (zero),
event delivery coverage, unsupported observation share and feedback coverage. Include
all logical requests in reliability denominators; publish offline/denied/error slices.

Proposed latency targets follow the same service protocol as MVP §3:

E1.1b service protocol v2 (2026-09-05) requires whole-client p95 ≤400 ms over loopback, measured separately at c1 and c4 with a fresh client process per request and a ready resident server/index. Server-side p95 must be ≤300 ms at both loads, measured from HTTP admission before authentication or queueing through synchronous logging and JSON response serialization. Whole-client timing includes startup/imports, local reads, auth, transport, queues, retrieval/composition, telemetry and output/exit. Report all attempts, errors and successful-within-budget counts under frozen workload, corpus, hardware and runtime identities. WAN/TLS/IAM and the actual harness remain a separate E6 integration gate, never implied by loopback success. Optimized sparse is the production candidate; hybrid remains shadow until independent latency and quality admission.

Protocol v2 uses inclusive ≤ comparisons. Historical T300/T500 budgets and E1.1b JSON evaluated with strict <400 retain their original definitions and results. Historical T300 means the whole hook in a fresh process, not an in-process kernel or the new server-side 300 ms target. A p95 target is not hard cancellation; the server allocation provides planning headroom, not a guarantee that the client target passes.

Measured results and the final decision are tracked in [E1.1b service feasibility](reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md). Interactive online SEARCH retains client-observed p95 ≤1 s under declared pilot concurrency and network conditions.
Measure startup/index loading, auth, network, queue, ranking and output costs; report
cold/warm modes separately. Retain a separate portable 3 s crash watchdog; validate it on every supported OS, without treating it as the normal latency target.
Optional interactive reranking is included in its profile budget; a warmed GPU is no latency guarantee.
These are acceptance targets to test, not current benchmark results or promises.

Usability reasons route work: `wrong_match` → ranking/triggers; `unclear_steps` → text;
`missing_prerequisite` → dependencies/setup; `stale` → references/revision;
`incompatible_environment` → compatibility; `unsafe_or_conflicting` → owner review;
`excess_context` → digest/budget; `load_failed` → delivery. Zero result and abandoned
load are investigated, not automatically labelled bad skills.

Task success is a separate outcome with its evaluator/source. To estimate impact,
run paired controlled scenarios with no skill, selected skills, oracle skills and
wrong siblings; pin task/model/harness/revision and report gain, regression, residual
failure, time and tokens. Observational usage and task success do not establish
causal skill benefit. Set adoption/usability targets after a two-week covered baseline.

## 8. Acceptance evidence for E6.4–E6.7

- E6.4: schema and adapters distinguish exposure, hydration, self-report and invocation;
  replay tests cover deduplication, partial acknowledgement, out-of-order joins,
  explicit USE, cached reuse, dependencies, retention/deletion and tenant isolation.
  E2.7 supplies the bounded local spool and observable adapter capability contract.
- E6.5: a per-skill view computes adoption/usability with coverage from known events;
  rollups reconcile with raw counts and duplicate replay leaves counts unchanged.
  Denied loads, absent feedback and unknown outcomes never become successful use.
- E6.6: client-level latency/load/failure tests measure the proposed targets and prove
  timeout, stale revision, partial closure, outage and recovery behavior; telemetry
  loss is visible and no telemetry database outage blocks the hook.
- E6.7: paired controlled pilot evaluations report gain, regression, residual failure,
  time/tokens, usability judgments and coverage. Display unavailable results as such.

Before launch, Platform publishes adapter evidence types, pilot cohorts, authorization/
cache expiry rules and measured load profile. GPU capacity/cost and empirical KPI
thresholds remain open; neither changes event semantics.