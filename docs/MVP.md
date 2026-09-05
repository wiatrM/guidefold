# Guidefold MVP — searchable skills, observable use, and measured usefulness

**Status:** Proposed revision · 2026-09-05, second revision the same day (E1.1b measured; target system in ADR-0024; new epic E7) · replaces the 2026-09-04 delivery scope, not historical completion records
**Decision owner:** product owner · **Capacity assumption:** 2 engineers + 0.5 ML engineer · **Planning horizon:** 8 weeks from this rebaseline · **Pilot:** 3 partner teams; access and labelled tasks are dependencies
**Harness request contract:** [ADR-0025](adr/ADR-0025-harness-service-context-contract.md) · [schema and semantics](HARNESS-SERVICE-CONTRACT.md)

**Architecture:** [ADR-0023](adr/ADR-0023-search-use-service-and-measured-utility.md) · **Target system beyond the MVP:** [ADR-0024](adr/ADR-0024-target-architecture-tiers-flywheel-composer.md) · **Measurement:** [SEARCH/USE contract](SEARCH-USE-TELEMETRY.md)

This plan includes a runnable, isolated local SEARCH/USE service and the versioned harness request contract. It does not deploy the proposed production service, enable uploads or adopt a new neural model. Existing story IDs remain stable: **E2 is client/distribution; E3 already means promotion; E6 is the new SEARCH/USE and measurement epic.** Delivery order is **E1.1b service feasibility + E1 correctness repairs -> E2 + E6 -> a thin E3/E4 pilot**, not numerical epic order. Per the user correction, E1.1b is an immediate blocking experiment, not deferred service validation in E6.

**What this MVP builds, in one sentence (ADR-0024):** the first two of three deployment tiers on one router contract — a local in-process tier for a single team and a single-node sparse-only service for a department — plus the telemetry that lets the organisation-scale tier earn dense retrieval per tenant later. The system must scale from one team to the whole organisation without a fork, and its search quality is governed by frozen gates on real labelled data, never by a benchmark it was trained on.

## 1. What changes and why

| Earlier plan | Revised MVP |
|---|---|
| Promotion acceptance is the sole success criterion | Prove skills can be found, delivered, used and judged useful; retain owner-reviewed promotion as a small parallel experiment |
| Every hook runs local BM25 + a distilled table under a 15 MB cap | Thin client, explicit local fallback, central SEARCH with a resident sparse index and optional full contextual encoder; 15 MB is a local artifact target, not a constraint on the server |
| Neural serving only in experimental find/CI | Add a measured online encoder profile; reranking belongs to explicit SEARCH with a separate deadline, not the default hook |
| Telemetry follows lifecycle work | Instrument SEARCH, delivery, USE evidence, feedback and outcomes before production rollout |
| Loads imply usefulness/probation success | Delivery, invocation, self-report, judged usefulness and task success are separate observations |
| Full promotion, automated probation, induction and graph UI in 8 weeks | Defer automation and full UI; deliver a usable service, a report and a concierge promotion slice within the same capacity |
| Dense is admitted once it clears the gates on a public benchmark | Dense is admitted **per tenant, in-distribution**, from a telemetry flywheel (E7); the shipped service profile is sparse-only until then, the hybrid runs in shadow |
| Composition is whatever `select()` does | Composition is a component with two implementations — deterministic and model-based — decided on dev by `all_required@4` before it is built (E7.3) |
| One deployment shape | Three tiers on one contract — local, single-node, organisation — chosen in `guidefold.yaml`; the same client file everywhere and bit-identical sparse ranking across tiers (E2.9) |

**Measured since the morning revision (2026-09-05).** The E1.1b spike ran. A sparse-only service with cached BM25 contributions answers at p95 **54 ms** (HTTP, one client), **128 ms** (four concurrent), **121 ms** from a fresh client process and **173 ms** for a burst of four fresh clients — 200/200, no GPU — so the **sparse profile proceeds to E2/E6 integration**; actual-harness and target-network pilot admission remains separate. The hybrid with a resident 0.6B encoder reaches 152 ms for one client but **444 ms at four**, because a single encode costs 86 ms and encodes serialise; it stays in **shadow** until dynamic batching is measured. DENSE-PROGRAM closed families F1–F4 with negative results on record (zero-shot encoder `all_required@4` +0.67 pp [−1.50, +2.83] on the independent corpus; the static student and T5 expansion below every gate) and found bundle completeness at k = 3 to be **0.000 for every arm** — a composition gap, not a ranking one. Sources: [E1.1b](reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md) (branch `feat/e11b-service-optimization`, final-code v3 artifacts), [DENSE-PROGRAM §7](reports/bakeoff/DENSE-PROGRAM.md), [ADR-0024](adr/ADR-0024-target-architecture-tiers-flywheel-composer.md) with its measured-vs-assumed table.

The 26-skill fixture/220 queries remains regression evidence. Real labelled tasks determine quality; real corpora at 6k and about 30k skills determine scale/latency. Unlabelled scale data is not quality evidence. The frozen historical [DENSE-PROGRAM](reports/bakeoff/DENSE-PROGRAM.md) is not retroactively rewritten; remote admission gets a separate prospective protocol under E6.7.

## 2. Storage and service boundary

**Skills stay in the code monorepo. Git review owns text and approval. Nothing generated is committed in consumer repos. One Postgres, GCS artifacts, registry downstream.**

| Component | Responsibility |
|---|---|
| Monorepo + CI | Skill text, owners, dependencies and reviews; path-filtered validation; changed-only embeddings and coherent snapshot publication |
| Knowledge API with SEARCH/USE module (CPU) | Auth, eligibility, sparse/vector retrieval from resident snapshots, composition, revision hydration, events and read-only reports |
| Inference worker (GPU) | Pinned full encoder; optional interactive reranker; isolated bounded work queues so indexing/reranking cannot starve hooks |
| One Cloud SQL Postgres (+ pgvector where needed) | Revision/access metadata, vector projections, events, rollups and the minimum owner decision log; canonical skill text remains in Git |
| GCS | Immutable sparse/vector/graph snapshots and checksummed body bundles; atomic manifest pointers and rollback |
| Single-file client, stdlib + PyYAML | Existing find/load entry points, proposed search/use aliases, hooks, scoped cache, local sparse fallback and bounded telemetry spool |
| Existing observability backend | Technical traces, latency/error counters and alerts; business metrics stay in Postgres |
| Agent Registry | Optional downstream mirror for existing consumers; never required for SEARCH latency or MVP release |

**Deployment tiers (ADR-0024 §1).** One router contract, one index format, one client file; only *where* `candidates`/`score` run changes.

| Tier | Who | Search backend | Dense | MVP status |
|---|---|---|---|---|
| **T0 local** | one team; offline/air-gapped; a corpus small enough that `guidefold doctor` measures warm p95 < 300 ms on it | in-process CLI, sharded by node (ADR-0021) | none | exists (E1.5); measured T300 crossover **≈ 5 300 skills** (p95 320 ms at 6 006 after R4b, PR #45); sharding needed only above it |
| **T1 department** | up to ~10 000 skills, one region | single-node `serve`, resident sparse snapshot, atomic swap | shadow only | **pilot target** (E6.2): sparse c = 4 p95 152 ms measured |
| **T2 organisation** | the full catalogue, thousands of developers | HA regional service + GPU encoder worker with dynamic batching | admitted per tenant through E7 | beyond the 8-week horizon |

Selected with `search.backend: local | service` and `search.url` in `guidefold.yaml`; fallback order is service → local sparse (ADR-0023 §3); the sparse ranking is bit-identical across tiers and CI proves it (E2.9).

SEARCH is one module of the planned Knowledge API, not a second registry/control plane. Begin with in-memory exact vector search; benchmark ANN only if useful. No extra Qdrant/OpenSearch cluster, event bus, telemetry microservice or warehouse in MVP. One pilot region and at most one warm GPU replica; monthly spend cap, region and capacity envelope must be recorded before provisioning. GPU availability/price is not assumed from checkpoint file size.

Online access/status checks may depend on Postgres; telemetry writes are asynchronous and cannot block serving. A database failure is not an excuse to bypass authorization. Offline protected delivery requires a scoped unexpired authorization lease (proposed max 10 minutes; restricted scopes disabled by default), and explicit denials invalidate caches. Offline revocation is bounded by that lease, not instantaneous. Public/local-only skills may have a different policy.

CI publishes matching sparse/vector/body/graph revisions together and changes the pointer only after verification/preload. Add/update/delete propagation target: <=10 minutes to the active server snapshot and online clients, measured. Changing encoder/tokenizer/input policy rebuilds the affected vector set. Client caches and responses include exact revision, snapshot, profile and policy/model/pipeline identity. Unpublished local edits stay in a declared local profile; no automatic source upload.

## 3. MVP definition and release contract

**Promise:** Guidefold finds eligible skills for a task, delivers approved revisions under a context budget, and shows owners where those skills were delivered, used with observable evidence, and useful or problematic. Promotion remains human-reviewed.

**Must ship:** corrected ranking/evaluation contracts; usable local fallback; central SEARCH with the admitted sparse profile (T1) and the encoder in shadow; tier selection in `guidefold.yaml` with bit-identical sparse ranking across tiers; a composer decision measured on dev before it is built; explicit USE/hydration; traceable events and a weekly skill report; controlled usefulness/usability evaluation; verified primary Claude Code integration and a second Copilot CLI explicit find/load path with honest capability limits; onboarding <=30 minutes.

**Not required to ship:** a winning dense model, a 15 MB global catalog, mandatory reranking, automatic skill generation/promotion/retirement, own fine-tuning (scheduled as E7.2 once the pilot yields USE labels), full custom UI, HA/multi-region GPU serving, additional harnesses or analytics databases. If no neural profile clears the gate, release the observable API with the corrected sparse profile and disclose that result.

| Requirement | Proposed acceptance / how measured |
|---|---|
| Fast hook / local service | E1.1b service protocol v2 below: whole-client p95 ≤400 ms over loopback for fresh-process c1/c4; server-side p95 ≤300 ms at both loads. The actual harness and WAN/TLS/IAM require separate E6 validation. Retain a portable 3 s crash watchdog, separate from normal deadlines |
| Interactive SEARCH | Client-observed p95 <=1 s, separately for encoder-only and reranked profiles; record cold start and p99. The reranked profile is disabled if it misses its budget |
| USE/hydration | Exact approved revision and verified checksum; no remote code execution. Separate cache-hit/cold p50/p95 and bytes; freeze the cold target against actual bundle sizes in week 1 |
| Reliability | Provisional API availability target >=99.5% over the instrumented pilot window; valid zero-result/abstention separate from transport/server failure. Report semantic-profile availability/fallback separately so sparse degradation cannot hide GPU failure |
| Bounded resources | Query/body/top-k/token/event-batch limits, queue/concurrency limits and rate limits; record sustained/burst load envelope and hardware before tests at pilot, 6k and ~30k skills |
| Policy and version safety | Server-derived tenant/access, eligibility shared across retrieval/rerank/dependencies/hydration; approved statuses only; cross-tenant, revoked, stale/missing revision and checksum cases covered; cache lease expiry enforced |
| Complete declared bundles | Full transitive requires, cycle handling, verified alternatives and explicit unresolved/cannot-fit under <=4-card/token budgets; no unsupported claim of complete task coverage |
| Traceability and privacy | Versioned IDs/events, dedupe, async retry, recorded loss/lag; no prompt/source text in normal logs/traces/spool; separate opt-in redacted evaluation corpus; 90-day event retention and actual deletion |
| Usability | Task-based pilot covers discovery, loading, following instructions, dependencies, tool permissions/compatibility, stale instructions and feedback; report failures and unknowns, not one opaque score |
| Retrieval quality | Frozen gates from DENSE-PROGRAM §5, on real labelled corpora, through the product path: any admitted change ≥ +2.0 pp `all_required@4` with the CI excluding 0; HSR@4 and hit@1/nDCG@10 not worse by > 1.0 pp; per-tenant dev set from telemetry once E7.1 exists. The fixture is regression only |
| Tier portability | The same client file at T0/T1/T2; sparse ranking and selection bit-identical across local and service on the frozen dev queries (`ranked_sha256`/`selected_sha256` parity in CI); fallback order service → local documented and tested |

E1.1b service protocol v2 (2026-09-05) requires whole-client p95 ≤400 ms over loopback, measured separately at c1 and c4 with a fresh client process per request and a ready resident server/index. Server-side p95 must be ≤300 ms at both loads, measured from HTTP admission before authentication or queueing through synchronous logging and JSON response serialization. Whole-client timing includes startup/imports, local reads, auth, transport, queues, retrieval/composition, telemetry and output/exit. Report all attempts, errors and successful-within-budget counts under frozen workload, corpus, hardware and runtime identities. WAN/TLS/IAM and the actual harness remain a separate E6 integration gate, never implied by loopback success. Optimized sparse is the production candidate; hybrid remains shadow until independent latency and quality admission.

Protocol v2 uses inclusive ≤ comparisons. Historical T300/T500 budgets and E1.1b JSON evaluated with strict <400 retain their original definitions and results. Historical T300 means the whole hook in a fresh process, not an in-process kernel or the new server-side 300 ms target. A p95 target is not hard cancellation; the server allocation provides planning headroom, not a guarantee that the client target passes.

These targets do not claim achieved measurements; see [E1.1b service feasibility](reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md) for results and the final decision. Freeze pilot load/SLO definitions and quality non-inferiority margins before the admission run. Any missed must-ship requirement narrows the supported profile/scope or delays release; it is not waived because the GPU is warm.

## 4. Epics and user stories

Roles: Dev, Owner (CODEOWNER), Platform and ML. Rows describe target acceptance, not claims of completion. Existing E0/E1 work is retained; outstanding repairs below must be verified against the current code.

### E0 — Foundation and onboarding (existing IDs)

| # | Scope | Acceptance |
|---|---|---|
| E0.1 | Repo/CI baseline | Tests, syntax check and fixture validation; external registry mocked |
| E0.2 | Router separated from storage | Product candidate/score/select stages shared by client, service and evaluator through a versioned contract; no independent drifting implementation |
| E0.3 | Portable bootstrap and README | No partner-specific values; executable fixture quickstart |
| E0.4 | init / doctor | Check local and remote profiles, auth, snapshot freshness, lease, telemetry state and harness wiring; onboarding <=30 minutes |
| E0.5 | Honest ADR/status record | Proposed amendments linked both ways; implemented state separate from planned service |

### E1 — Correct routing and a trustworthy evaluator (repair gate, weeks 1–2)

| # | Revised scope | Acceptance |
|---|---|---|
| E1.1 | Query-sensitive ranking with one eligibility policy | Deprecated/disallowed candidates stay out of ranking, dependencies and hydration; repository context is not authorization |
| E1.1b | **Validate the real SEARCH/USE service path now, before dependent E2/E6 work** | Runnable local HTTP service with an optimized sparse resident 6k-skill index and explicit revision hydration; optional pinned full encoder with live inference remains shadow. Contract 1.1 adds repository snapshots, cwd/target resolution, IDs, delivery limits and adapter/schema conformance (ADR-0025). Measure cold readiness, client/fresh-process p50/p95/p99, concurrency, malformed/auth-denied/deadline/outage handling and fallback. Publish reproducible code/results, a proceed/change/stop decision and explicit loopback-vs-target-network gaps. A failed budget changes the architecture before downstream commitments; local success is not a production SLO claim. **Measured 2026-09-05** (final-code v3): sparse-only p95 54 / 128 / 121 / 173 ms (one client / four / fresh process / burst of four fresh) → *proceed* for the sparse profile; hybrid four-client 444 ms → *change* (dynamic batching) — see §1 |
| E1.2 | Versioned quality metrics and data splits | Empty results count as failures on answerable tasks; no-applicable cases measured separately; common paired populations and explicit denominators; real holdout, fixture for regression only |
| E1.3 | Fair sparse/static/contextual comparison | Freeze dev-selected sparse weights and each challenger/fusion before holdout; separate teacher, student and hybrid; compare identical text-policy and eligibility contracts |
| E1.4 | Versioned index artifact | CI->serialize->load parity, complete identities/checksums; measured size/load cost. 15 MB retained as a local-profile experiment, removed as global service gate |
| E1.5 | Bounded local routing | Fast sparse baseline, calibrated abstention, <=4 cards/token cap; actual hook p95 at 6k and pilot scope; remote calls belong to E2.6 |
| E1.6 | Reranker challenger | Interactive/shadow profile only until admitted; USE/SKIP is predicted relevance, never usage telemetry; true online latency measured in E6 |
| E1.7 | Revision/cache correctness | Cache key covers revision, snapshot, profile, permissions/lease and all model/input transforms; stale/missing revision never silently substitutes latest |
| E1.8 | Declared dependency composition | Full requires, shared prerequisites, cycles, verified OR alternatives, unresolved/cannot-fit; out-of-category dependencies need explicit eligibility rules, never oracle category leakage |

### E2 — Distribution, thin client and observable delivery (weeks 2–5)

| # | Story | Acceptance |
|---|---|---|
| E2.1 | As Platform, keep generated consumer files out of Git | Static bootstrap only; cache/materialization gitignored; legacy materialize is not needed for the supported path |
| E2.2 | As Dev, receive scope context through a verified adapter | Primary Claude path and second Copilot explicit find/load path tested in real harnesses; <=6 KB L0 card. Copilot sessionStart context injection is not promised until demonstrated |
| E2.3 | As Platform, publish changed skills consistently | Add/update/delete -> embed/index -> checksums -> preload -> atomic snapshot activation; <=10 min propagation measured; failed build keeps prior snapshot; Agent Registry mirror does not block service |
| E2.4 | As Dev, prewarm only what the local profile needs | Checksummed scoped index/body cache, declared freshness/lease, measured cold startup target <=1.5 s on pilot profile; prewarm never increments USE |
| E2.5 | As Platform, keep skill-only CI fast | Path-filtered checks <=5 min excluding a separately measured async embedding/publish job; no skip of required validation |
| E2.6 | As Dev, use online SEARCH with bounded local fallback | Existing find/load compatibility; one hook deadline, concurrent permitted sparse fallback, cancellation, token/TLS cold path and denial tests; actual backend/reason visible; no ML dependency in CLI |
| E2.7 | As Owner, observe delivery even through cache/offline | Versioned local events, bounded spool/sync, duplicates/retries/loss tests; direct load without search supported; no synchronous network telemetry in hook |
| E2.8 | As Platform, know what each adapter observes | Capability matrix for search response, context delivery, load, read/invocation and outcome; unsupported stages unknown; real harness evidence, not only mocked stdin/stdout |
| E2.9 | As Platform, run the same client at every tier | `search.backend`/`search.url` in `guidefold.yaml`; `doctor` measures local warm p95 on the consumer's corpus and recommends a tier; a CI parity test proves bit-identical sparse ranking and selection between local and service on the frozen dev queries; fallback order service → local sparse documented and tested |

### E6 — SEARCH/USE service and evidence (new epic, weeks 1–8)

| # | Story | Acceptance |
|---|---|---|
| E6.1 | As Platform, expose a stable authenticated contract | OpenAPI for POST /v1/search, /v1/use, /v1/events:batch; tenant/access from verified identity; bounded inputs; versions, errors, deadlines and readiness contract; replayable conformance fixtures |
| E6.2 | As Dev, search a resident full catalog | CPU resident sparse index as the **admitted pilot profile** (measured p95 56 / 152 ms at 6 006 skills) plus a pinned warm encoder worker in **shadow** with dynamic batching; hook and interactive profiles; exact search first; isolated queues, atomic index swap, sparse rollback; no startup per request; the hybrid becomes servable only when four concurrent clients clear the server-side 300 ms budget |
| E6.3 | As Agent, explicitly USE an approved skill revision | Current auth/status/dependency check; body/resource checksum and exact revision returned; cache/direct use supported; service does not execute code or label delivery as application |
| E6.4 | As Platform, retain reliable events without slowing use | One Postgres ingest/rollup module; idempotency by tenant+event_id, retry/partial-batch/out-of-order handling, backlog/loss metrics, retention/deletion; no duplicated client/server counting |
| E6.5 | As Owner, see usage and usability per skill revision | CLI/read-only report from same API: exposure, loads, observed/reported use, feedback reasons/coverage, compatibility/staleness and cross-team reuse; 3 primary KPIs from telemetry contract; no individual leaderboard |
| E6.6 | As Platform, operate and roll back the service | Client->API->encoder/index/composer/hydration traces, p50/p95/p99, queue/fallback/errors, GPU/index readiness, snapshot age and cost; sustained/burst plus outage/denial/index-swap/spool tests; named operator and spend cap |
| E6.7 | As Product/ML, establish usefulness before broad adoption | Prospective dev/holdout protocol, 20–40 paired pilot tasks as a feasibility study (minimum 20, aim for 40; expand from the predeclared power/uncertainty requirement for an adoption claim), no-skills/sparse/contender/oracle comparisons, task success/regression/cost/time; hands-on usability sessions in 3 teams; no adoption from cached-query or popularity evidence — see [E6.7 protocol](pilot/E6.7-PROTOCOL.md) |

### E7 — Quality flywheel and composition (new epic; E7.3 and E7.5 inside the 8 weeks, the rest after the pilot)

Search quality is the product. This epic is how it improves after release without anyone re-running a benchmark by hand, and how dense retrieval earns its place per tenant instead of being assumed ([ADR-0024](adr/ADR-0024-target-architecture-tiers-flywheel-composer.md) §3–§6).

| # | Story | Acceptance |
|---|---|---|
| E7.1 | As ML, build a per-tenant dev set from telemetry | (query, USE) pairs from the opt-in redacted corpus joined by `search_id`; cards exposed and not used in the same search as hard negatives; frozen split; size and coverage reported; no query text outside the opt-in |
| E7.2 | As ML, fine-tune the encoder on tenant pairs and admit it per tenant | weekly self-hosted fine-tune (ADR-0015); a new model identity re-embeds the affected vector set; admission by the frozen gates on the held-out slice; fail → shadow, pass → served with rollback to the previous snapshot and to sparse-only |
| E7.3 | As ML, decide the composer on dev before building it | deterministic composer (score-gap bundle detection, coverage-aware selection, `requires` closure) vs a model composer over ≤ 15 admissible candidates, on SKILLRET-train dev (k = 1/2/3 labels), ≤ 6 configurations, then once on both test corpora; adopt only ≥ +2.0 pp `all_required@4` with the CI excluding 0, HSR@4 and hit@1 within 1.0 pp, cost within tier; `cannot_fit` emitted, never a truncated set labelled complete |
| E7.4 | As Platform, generate synthetic queries at index time | strong-LLM `expansion` field, incremental per changed skill, budgeted; standard experiment gates; the T5 variant is closed (PR #41) |
| E7.5 | As Platform, make evaluation part of the snapshot build | the frozen dev set runs through the product path on every index build; a gate regression blocks the manifest-pointer swap; per-query JSONL retained for E7.1–E7.3 |
| E7.6 | As Owner, see per-tenant retrieval quality and the dense admission state | one report row per tenant: sparse vs shadow dense on the tenant dev set, gate status, model identity, last admission or rollback |

### E3 — Promotion vertical (retain IDs, concierge slice only)

| # | Revised MVP scope | Acceptance / deferral |
|---|---|---|
| E3.1 | Concierge scan of 50–200 real skills from 3 teams | Scope/owner/provenance map and candidate duplicates; exact cosine thresholds validated, not universal constants |
| E3.2 | Manually assisted grounded proposals | Small source-backed parent/child diff; no ungrounded synthesized policy |
| E3.3 | Reuse E1/E6 evaluation for proposal evidence | Paired scenarios, conflicts, regressions and incomplete bundles visible to reviewer |
| E3.4 | Automated bot PR orchestration | Deferred; humans may open concierge PRs in ordinary review; bot never merges |
| E3.5 | Minimal decision log | Reuse E6 Postgres/API; accept/reject/amend plus reason; no second database |
| E3.6 | Automated probation serving workflow | Deferred; optional manually approved, scoped probation must honor current policy and measured evidence |
| E3.7 | Ten owner-reviewed concierge proposals | Small parallel discovery exercise by week 4 if partner data is ready; report acceptance/review burden; not the sole SEARCH release gate |

### E4 — Minimum governance; automatic lifecycle deferred

| # | Revised scope | Acceptance / deferral |
|---|---|---|
| E4.1 | Structure, evidence and owner approval checks | Unapproved revisions never published into permitted serving snapshots |
| E4.2 | Evidence-informed manual probation review | CLI helped/wrong/blocked feedback per task+revision; loads are not trials of success. Wilson intervals, if shown, use judged outcomes, not downloads; insufficient feedback remains unknown; no automatic activation |
| E4.3 | SkillPyramid induction | Deferred beyond MVP |
| E4.4 | Auditable administrative changes | Actor/action/entity/revision/request recorded; restricted audit separate from product telemetry; advanced hash-chain/export work deferred |
| E4.5 | Skill hygiene | Current scalar metadata/body/ZIP validation, owners and references; negative triggers only where meaningful, never forced onto every skill |
| E4.6 | Withdrawal and access change | Next online USE revalidates status/access; invalidation and offline lease expiry tested; stale/missing dependency refuses complete delivery; owner has rollback procedure |

### E5 — Diagnostic report, not a full UI project

| # | Revised scope | Acceptance / deferral |
|---|---|---|
| E5.1 | Scope graph/custom demo app | Deferred |
| E5.2 | Minimal query inspection | CLI or existing read-only shell displays version/profile, filtered reasons, stage timings and composition; no new frontend stack required |
| E5.3 | Owner report | Reuse E6.5 report for skill metrics and concierge decisions; full promotion feed deferred |

## 5. Rebaselined delivery plan and gates

**Priority plan — approved by the product owner on 2026-09-05 (evening), executed step by step.** It sits on top
of the week table below and wins where they differ. Each row names what it unblocks; each item has a
pre-registered measurement or a hard acceptance criterion, never a vibe.

| Weeks | Do | Unblocks |
|---|---|---|
| 1–2 | **Family E — synthetic in-distribution training** over the tenant's own skills (per-skill + composite multi-intent queries + hard negatives; local open generator on the GPU; no labels; leakage check; dev → freeze → once on both tests); **close family D** (query decomposition, dev); **agent-side decomposition** in the bootstrap `SKILL.md` (call `find` once per step of a multi-step task) | a reachable dense gate (`all_required@4`) and recall for k = 2/3, where today 64 % of required skills are outside the top-10 |
| 2–4 | **Go parity** — **done 2026-09-05 in PR #54**: the Go service compiles the CLI's exact fixed-point BM25F contributions from the exported artifact and proves **0/1 000 mismatches** against the CLI on dev (ordered URNs, integer scores, selections, revisions), enforced by a real-HTTP parity job in CI; ParadeDB is storage/prefilter, never the scorer (ADR-0026 amended to hosting only); p95 21.6 / 29.1 ms at c1/c4. Remaining in this row: `/v1/events:batch` on Postgres (port of `tools/telemetry/ledger.py`), shadow records keyed by `search_id`, T1 runbook | a production-shaped T1 on Go with one truth about the ranking (E2.9, ADR-0024 §1) |
| 3–6 | **Authoring loop**: F5 trigger/negative-trigger suggestions in `validate` (owner approves in the PR), a per-PR collision report ("this description takes N dev queries from skill X"), E7.5 evaluation in the snapshot build | search quality that improves with every skill PR, not only with every model |
| 5–8 | **Flywheel on real USE events** (E7.1–E7.2) + **pilot E6.7** (3 teams, 20–40 paired tasks, frozen protocol) | evidence of value for developers, not only better metrics |


Eight weeks starts at this planning revision. Completed E0/E1 work is reused. Staffing assumes one engineer owns client/distribution, one API/events, and 0.5 ML owns evaluation/model admission; shared auth/ops support and partner access must be available. If those assumptions fail, narrow pilot/harness scope explicitly or re-estimate instead of silently extending the plan.

| Weeks | Critical work | Reviewable exit |
|---|---|---|
| 1–2 | **E1.1b service spike first**; E1 repairs and measurement; E6.1 contracts; freeze operational envelope, data/access policy and pilot corpus | E1.1b go/change/stop report from actual HTTP/live-model tests — **done 2026-09-05: sparse profile *proceed* (54 / 128 / 121 / 173 ms; final-code v3), hybrid *change* (batching)**; corrected sparse baseline, common metric denominators, composition contract, API/events fixtures; revised local latency; prospective remote evaluation protocol |
| 3–4 | E2 publication/client; E2.9 tier selection + parity; E6.2 resident sparse SEARCH with the encoder in shadow; E6.3 USE; start E6.4 events; **E7.3 composer decision on dev** | Coherent snapshot across server/client; SEARCH->USE correlation on real harness; shadow hybrid vs sparse quality/latency; a composer chosen by `all_required@4` on dev; optional 10 concierge reviews |
| 5–6 | E2 cache/offline/adapter coverage; E6.4–E6.6 reporting/ops; **E7.5 evaluation in the snapshot build**; E4 withdrawal; limited 3-team pilot | Load/timeout/denial/rollback tests; no double-counted prewarm/retries; observable unknowns; per-skill report; a gate regression blocks a snapshot swap; guarded rollout of only admitted profiles |
| 7–8 | E6.7 paired utility + hands-on usability; tune fixes on dev; final SLO/cost report | Evidence on task value, tool compatibility and user friction; declared supported capacity/latency/profile; owner/operator runbook; go/no-go for broader rollout and automated promotion |
| 9–12 *(after the pilot; outside this horizon, sequenced here so it is not forgotten)* | E7.1 tenant dev set from pilot telemetry; E7.2 first fine-tune cycle and admission run; E7.4 if budget allows; T2: HA and the hybrid four-client measurement with batching | First per-tenant dense admission decision with rollback; hybrid four-client p95 measured against the server-side 300 ms budget; ADR-0024 tier table confirmed or revised from measurements |

**Dependency gate:** E1.1b was reviewed on 2026-09-05 — the sparse profile proceeds; the hybrid profile is a *change* (dynamic batching), and no E2.3/E2.6/E6.2 commitment assumes it. Other independent E1 correctness and event-schema work may continue. Unmeasured target-network/TLS/IAM behavior remains a named E6 integration gate, never implied by loopback results.

**Release gates:** policy/revision correctness; bounded hook and supported SEARCH profile under the frozen workload; recoverable failures; trustworthy event accounting; measured quality non-inferiority to corrected sparse under the predeclared margin and harmful-exposure bound; useful execution improvement or lower cost at non-inferior task success. If utility evidence is underpowered, deliver a limited pilot with that label, not a proven-value claim. Owner acceptance remains an E3 hypothesis, not a proxy for retrieval relevance or downstream success.

**Scope trade:** restore full E3 bot orchestration, E4 automated lifecycle/induction or custom E5 UI only with a new estimate after the service pilot. Do not claim the original full feature list plus E6 fits the old 8 weeks.

## 6. What we measure and what decisions it enables

Normative definitions, event grains/IDs, numerators/denominators, unknown handling and deletion are in [SEARCH-USE-TELEMETRY.md](SEARCH-USE-TELEMETRY.md). Initial rate targets require the pilot baseline; only operational targets in §3 are proposed now.

| Primary view | Decision |
|---|---|
| Observed skill adoption and repeat use, with adapter/task coverage | Are teams integrating skills into work, or merely receiving cards? Separate direct use, cache and search-assisted use; self-reports remain separate |
| Judged usability per skill revision, with feedback coverage/reasons | Which instruction, compatibility, permissions, dependency or freshness problems should its owner fix? Missing feedback is unknown; popularity is exposure-biased |
| Controlled task utility (success/regression, cost/time) | Does selected guidance help compared with no-skills and corrected sparse under matched conditions? A successful task after a load does not establish causation |
| Retrieval quality on the tenant dev set (`all_required@4`, HSR@4, hit@1) — sparse vs shadow dense | Admit, keep in shadow, or roll back dense for that tenant; never from popularity or exposure counts |

Diagnostics: search count/no-result/abstention, result exposure/rank, successful hydration, observed invocation vs declared application, time to first delivery, cross-team reuse, requested-vs-missing dependencies, cannot-fit, token budget and onboarding friction. Guardrails: wrong/harmful sibling exposure, policy violations, p95/p99/fallback/errors, telemetry coverage/lag/loss, snapshot age and cost per profile. Every rate includes its population and skill revision; no denominator switch on empty results.

Weekly review owners: Platform for service/data quality, ML for held-out quality/utility, skill owners for actionable feedback, Product for adoption/usability and scope decisions. Report zero exposures separately from exposed-but-unused; never retire/promote automatically from usage counts.

## 7. Deferred work and remaining research

[ADR-0022](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md) remains Proposed; landed numerical fixes do not complete its full target. E1 closure/composition/parity and E6.7 evidence remain prerequisites to broader adoption. Preserve historical reports and their caveats, including conditional metrics and cached-query timing.

Deferred: full automated promotion workflow and probation, induction/consolidation/retirement jobs, generative composition roles, trajectory mining, own fine-tuning before pilot telemetry exists (then E7.2), fusion MLP, global graph UI, HA/multi-region GPU fleet, laptop neural daemon, additional harness adapters, extra vector/search databases, BigQuery, ARD facade and Backstage export. Closed as quality paths, with their numbers on record (DENSE-PROGRAM §7, ADR-0024 §7): the distilled static student, T5 document expansion, the zero-shot encoder as a default profile, and a client-side small contextual model. The static table may return only as an optional offline T0 artifact if it ever clears a gate. Strong-LLM query generation is E7.4 and own fine-tuning is E7.2 — both after the pilot, neither an MVP dependency.

## 8. ADR reconciliation for this revision

| ADRs | Status / scope |
|---|---|
| 0001, 0003–0008, 0010, 0015–0017, 0019–0020 | Existing Accepted decisions remain recorded; any change proposed here is linked through 0023, not silently marked accepted |
| 0009, 0012–0014, 0018, 0021–0022 | Existing Proposed decisions remain Proposed |
| 0002, 0011 | Historical deleted decisions; do not reuse their IDs |
| [0023 SEARCH/USE and utility](adr/ADR-0023-search-use-service-and-measured-utility.md) | New Proposed amendment: central serving, bounded clients, event semantics and narrower MVP; proposes amendments to 0009/0013/0015/0016/0018/0020/0021; ADR-0024 proposes an amendment |
| [0024 target architecture](adr/ADR-0024-target-architecture-tiers-flywheel-composer.md) | New Proposed: one contract, three deployment tiers, per-tenant dense admission through a telemetry flywheel, model-based composition, a cost model for 5 000 developers with a measured-vs-assumed table; amends 0009/0020/0021/0022/0023 |
| [0026 native Go/ParadeDB](adr/ADR-0026-native-search-paradedb-compose.md) | Accepted Go/Postgres/Compose hosting only; default ranking must retain CLI BM25F parity; experimental Tantivy fails HSR admission |
| [0025 harness-service context](adr/ADR-0025-harness-service-context-contract.md) | Accepted request contract 1.1: versioning, repository-relative context, explicit feature semantics and schema/runtime/HTTP conformance; narrows the request boundary of 0023/0024 without admitting their production architecture |

Older DESIGN/KNOWLEDGE-DESIGN remain historical target descriptions and current CLI notes where marked. Their local-only hot path, delayed telemetry, load-based probation and old phase schedules must not be read as acceptance criteria for this proposed MVP. No runtime behavior changed in this documentation revision.

### Native T1 deployment (accepted implementation update, 2026-09-05)

The owner selected Go + ParadeDB for the resident SEARCH/USE backend, deployed by
Docker Compose; see [ADR-0026](adr/ADR-0026-native-search-paradedb-compose.md) and
[runbook](../services/search/README.md). The resident service is Go; default BM25F uses canonical CLI build statistics and
integer scoring over Postgres postings. Tantivy remains an explicit experiment. API 1.1 and the unchanged T0 CLI remain the boundaries.
This replaces the Python spike as the implementation target while preserving its
reports. Default sparse routing must pass exact CLI parity, including the full retrieval
stage; shared policy fixtures alone are insufficient. Dense remains a separate admitted/shadow evaluation.
Kubernetes deployment, production IAM/network/HA and durable E6.4 SEARCH/USE telemetry
are subsequent work, not implied by local Compose success.

**Completed reference:** [Go/ParadeDB report](reports/bakeoff/GO-PARADEDB-2026-09-05.md):
800/800 SEARCH requests, HTTP p95 21/28 ms and fresh-client p95 117/138 ms at c1/c4.
Retrieval quality **is not admitted**: test-B HSR rises from 39.67% to 50.33%, exceeding
the +1 pp guardrail. The prior admitted sparse profile keeps its status. These numbers describe only
the experimental Tantivy mode; the corrected default serves the reference BM25F. [GPU serving follow-up](reports/bakeoff/DENSE-SERVING-NEXT-2026-09-05.md)
is a proposal with no new test-budget authorization or active GPU implementation.

Default-router correction and measured parity/latency: [report](reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md).
