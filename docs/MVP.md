# Guidefold MVP — searchable skills, observable use, and measured usefulness

**Status:** Proposed revision · 2026-09-05 · replaces the 2026-09-04 delivery scope, not historical completion records
**Decision owner:** product owner · **Capacity assumption:** 2 engineers + 0.5 ML engineer · **Planning horizon:** 8 weeks from this rebaseline · **Pilot:** 3 partner teams; access and labelled tasks are dependencies
**Architecture:** [ADR-0023](adr/ADR-0023-search-use-service-and-measured-utility.md) · **Measurement:** [SEARCH/USE contract](SEARCH-USE-TELEMETRY.md)

This update prepares the requested plan; it does not deploy a service, enable uploads or adopt a new model. Existing story IDs remain stable: **E2 is client/distribution; E3 already means promotion; E6 is the new SEARCH/USE and measurement epic.** Delivery order is E1 repairs -> E2 + E6 -> a thin E3/E4 pilot, not numerical epic order.

## 1. What changes and why

| Earlier plan | Revised MVP |
|---|---|
| Promotion acceptance is the sole success criterion | Prove skills can be found, delivered, used and judged useful; retain owner-reviewed promotion as a small parallel experiment |
| Every hook runs local BM25 + a distilled table under a 15 MB cap | Thin client, explicit local fallback, central SEARCH with a resident sparse index and optional full contextual encoder; 15 MB is a local artifact target, not a constraint on the server |
| Neural serving only in experimental find/CI | Add a measured online encoder profile; reranking belongs to explicit SEARCH with a separate deadline, not the default hook |
| Telemetry follows lifecycle work | Instrument SEARCH, delivery, USE evidence, feedback and outcomes before production rollout |
| Loads imply usefulness/probation success | Delivery, invocation, self-report, judged usefulness and task success are separate observations |
| Full promotion, automated probation, induction and graph UI in 8 weeks | Defer automation and full UI; deliver a usable service, a report and a concierge promotion slice within the same capacity |

The prior static-student failure does not prove dense retrieval cannot help. Full-encoder reference runs are hybrids with BM25, use precomputed query vectors and are not online latency tests. Sparse itself measured p95 638.9 ms on 6,006 skills; the current shipped field weights also need comparison with the dev-selected uniform weights. These are release blockers to measure, not reasons to declare a winner. See [E1 closure](reports/bakeoff/E1-closure-plan.md), [sparse diagnosis](reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md) and [reference latency](reports/bakeoff/SKILLRET-test-2026-09-05.md).

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

SEARCH is one module of the planned Knowledge API, not a second registry/control plane. Begin with in-memory exact vector search; benchmark ANN only if useful. No extra Qdrant/OpenSearch cluster, event bus, telemetry microservice or warehouse in MVP. One pilot region and at most one warm GPU replica; monthly spend cap, region and capacity envelope must be recorded before provisioning. GPU availability/price is not assumed from checkpoint file size.

Online access/status checks may depend on Postgres; telemetry writes are asynchronous and cannot block serving. A database failure is not an excuse to bypass authorization. Offline protected delivery requires a scoped unexpired authorization lease (proposed max 10 minutes; restricted scopes disabled by default), and explicit denials invalidate caches. Offline revocation is bounded by that lease, not instantaneous. Public/local-only skills may have a different policy.

CI publishes matching sparse/vector/body/graph revisions together and changes the pointer only after verification/preload. Add/update/delete propagation target: <=10 minutes to the active server snapshot and online clients, measured. Changing encoder/tokenizer/input policy rebuilds the affected vector set. Client caches and responses include exact revision, snapshot, profile and policy/model/pipeline identity. Unpublished local edits stay in a declared local profile; no automatic source upload.

## 3. MVP definition and release contract

**Promise:** Guidefold finds eligible skills for a task, delivers approved revisions under a context budget, and shows owners where those skills were delivered, used with observable evidence, and useful or problematic. Promotion remains human-reviewed.

**Must ship:** corrected ranking/evaluation contracts; usable local fallback; central SEARCH with online sparse and an evaluated encoder challenger; explicit USE/hydration; traceable events and a weekly skill report; controlled usefulness/usability evaluation; verified primary Claude Code integration and a second Copilot CLI explicit find/load path with honest capability limits; onboarding <=30 minutes.

**Not required to ship:** a winning dense model, a 15 MB global catalog, mandatory reranking, automatic skill generation/promotion/retirement, own fine-tuning, full custom UI, HA/multi-region GPU serving, additional harnesses or analytics databases. If no neural profile clears the gate, release the observable API with the corrected sparse profile and disclose that result.

| Requirement | Proposed acceptance / how measured |
|---|---|
| Fast hook | Whole client warm p95 <=300 ms on a named laptop, supported OS and named corpus; includes startup, auth, network, queue, retrieval, composition, telemetry enqueue and output. Separate portable 3 s crash watchdog, not the normal deadline |
| Interactive SEARCH | Client-observed p95 <=1 s, separately for encoder-only and reranked profiles; record cold start and p99. The reranked profile is disabled if it misses its budget |
| USE/hydration | Exact approved revision and verified checksum; no remote code execution. Separate cache-hit/cold p50/p95 and bytes; freeze the cold target against actual bundle sizes in week 1 |
| Reliability | Provisional API availability target >=99.5% over the instrumented pilot window; valid zero-result/abstention separate from transport/server failure. Report semantic-profile availability/fallback separately so sparse degradation cannot hide GPU failure |
| Bounded resources | Query/body/top-k/token/event-batch limits, queue/concurrency limits and rate limits; record sustained/burst load envelope and hardware before tests at pilot, 6k and ~30k skills |
| Policy and version safety | Server-derived tenant/access, eligibility shared across retrieval/rerank/dependencies/hydration; approved statuses only; cross-tenant, revoked, stale/missing revision and checksum cases covered; cache lease expiry enforced |
| Complete declared bundles | Full transitive requires, cycle handling, verified alternatives and explicit unresolved/cannot-fit under <=4-card/token budgets; no unsupported claim of complete task coverage |
| Traceability and privacy | Versioned IDs/events, dedupe, async retry, recorded loss/lag; no prompt/source text in normal logs/traces/spool; separate opt-in redacted evaluation corpus; 90-day event retention and actual deletion |
| Usability | Task-based pilot covers discovery, loading, following instructions, dependencies, tool permissions/compatibility, stale instructions and feedback; report failures and unknowns, not one opaque score |

These are proposed targets, not achieved measurements. Freeze pilot load/SLO definitions and quality non-inferiority margins before the admission run. Any missed must-ship requirement narrows the supported profile/scope or delays release; it is not waived because the GPU is warm.

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

### E6 — SEARCH/USE service and evidence (new epic, weeks 1–8)

| # | Story | Acceptance |
|---|---|---|
| E6.1 | As Platform, expose a stable authenticated contract | OpenAPI for POST /v1/search, /v1/use, /v1/events:batch; tenant/access from verified identity; bounded inputs; versions, errors, deadlines and readiness contract; replayable conformance fixtures |
| E6.2 | As Dev, search a resident full catalog | CPU resident sparse/vector index + pinned warm encoder worker; hook and interactive profiles; exact search first; isolated queues, atomic index swap, sparse rollback; no startup per request |
| E6.3 | As Agent, explicitly USE an approved skill revision | Current auth/status/dependency check; body/resource checksum and exact revision returned; cache/direct use supported; service does not execute code or label delivery as application |
| E6.4 | As Platform, retain reliable events without slowing use | One Postgres ingest/rollup module; idempotency by tenant+event_id, retry/partial-batch/out-of-order handling, backlog/loss metrics, retention/deletion; no duplicated client/server counting |
| E6.5 | As Owner, see usage and usability per skill revision | CLI/read-only report from same API: exposure, loads, observed/reported use, feedback reasons/coverage, compatibility/staleness and cross-team reuse; 3 primary KPIs from telemetry contract; no individual leaderboard |
| E6.6 | As Platform, operate and roll back the service | Client->API->encoder/index/composer/hydration traces, p50/p95/p99, queue/fallback/errors, GPU/index readiness, snapshot age and cost; sustained/burst plus outage/denial/index-swap/spool tests; named operator and spend cap |
| E6.7 | As Product/ML, establish usefulness before broad adoption | Prospective dev/holdout protocol, 20–40 paired pilot tasks as a feasibility study (minimum 20, aim for 40; expand from the predeclared power/uncertainty requirement for an adoption claim), no-skills/sparse/contender/oracle comparisons, task success/regression/cost/time; hands-on usability sessions in 3 teams; no adoption from cached-query or popularity evidence |

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

Eight weeks starts at this planning revision. Completed E0/E1 work is reused. Staffing assumes one engineer owns client/distribution, one API/events, and 0.5 ML owns evaluation/model admission; shared auth/ops support and partner access must be available. If those assumptions fail, narrow pilot/harness scope explicitly or re-estimate instead of silently extending the plan.

| Weeks | Critical work | Reviewable exit |
|---|---|---|
| 1–2 | E1 repairs and measurement; E6.1 contracts; freeze operational envelope, data/access policy and pilot corpus | Corrected sparse baseline, common metric denominators, composition contract, API/events fixtures; revised local latency; prospective remote evaluation protocol |
| 3–4 | E2 publication/client; E6.2 resident SEARCH in shadow; E6.3 USE; start E6.4 events | Coherent snapshot across server/client; SEARCH->USE correlation on real harness; online vs sparse shadow quality/latency; optional 10 concierge reviews |
| 5–6 | E2 cache/offline/adapter coverage; E6.4–E6.6 reporting/ops; E4 withdrawal; limited 3-team pilot | Load/timeout/denial/rollback tests; no double-counted prewarm/retries; observable unknowns; per-skill report; guarded rollout of only admitted profiles |
| 7–8 | E6.7 paired utility + hands-on usability; tune fixes on dev; final SLO/cost report | Evidence on task value, tool compatibility and user friction; declared supported capacity/latency/profile; owner/operator runbook; go/no-go for broader rollout and automated promotion |

**Release gates:** policy/revision correctness; bounded hook and supported SEARCH profile under the frozen workload; recoverable failures; trustworthy event accounting; measured quality non-inferiority to corrected sparse under the predeclared margin and harmful-exposure bound; useful execution improvement or lower cost at non-inferior task success. If utility evidence is underpowered, deliver a limited pilot with that label, not a proven-value claim. Owner acceptance remains an E3 hypothesis, not a proxy for retrieval relevance or downstream success.

**Scope trade:** restore full E3 bot orchestration, E4 automated lifecycle/induction or custom E5 UI only with a new estimate after the service pilot. Do not claim the original full feature list plus E6 fits the old 8 weeks.

## 6. What we measure and what decisions it enables

Normative definitions, event grains/IDs, numerators/denominators, unknown handling and deletion are in [SEARCH-USE-TELEMETRY.md](SEARCH-USE-TELEMETRY.md). Initial rate targets require the pilot baseline; only operational targets in §3 are proposed now.

| Primary view | Decision |
|---|---|
| Observed skill adoption and repeat use, with adapter/task coverage | Are teams integrating skills into work, or merely receiving cards? Separate direct use, cache and search-assisted use; self-reports remain separate |
| Judged usability per skill revision, with feedback coverage/reasons | Which instruction, compatibility, permissions, dependency or freshness problems should its owner fix? Missing feedback is unknown; popularity is exposure-biased |
| Controlled task utility (success/regression, cost/time) | Does selected guidance help compared with no-skills and corrected sparse under matched conditions? A successful task after a load does not establish causation |

Diagnostics: search count/no-result/abstention, result exposure/rank, successful hydration, observed invocation vs declared application, time to first delivery, cross-team reuse, requested-vs-missing dependencies, cannot-fit, token budget and onboarding friction. Guardrails: wrong/harmful sibling exposure, policy violations, p95/p99/fallback/errors, telemetry coverage/lag/loss, snapshot age and cost per profile. Every rate includes its population and skill revision; no denominator switch on empty results.

Weekly review owners: Platform for service/data quality, ML for held-out quality/utility, skill owners for actionable feedback, Product for adoption/usability and scope decisions. Report zero exposures separately from exposed-but-unused; never retire/promote automatically from usage counts.

## 7. Deferred work and remaining research

[ADR-0022](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md) remains Proposed; landed numerical fixes do not complete its full target. E1 closure/composition/parity and E6.7 evidence remain prerequisites to broader adoption. Preserve historical reports and their caveats, including conditional metrics and cached-query timing.

Deferred: full automated promotion workflow and probation, induction/consolidation/retirement jobs, generative composition roles, trajectory mining, own fine-tuning, fusion MLP, global graph UI, HA/multi-region GPU fleet, laptop neural daemon, additional harness adapters, extra vector/search databases, BigQuery, ARD facade and Backstage export. Static students, document expansion and smaller local contextual models remain separately budgeted experiments; none is a mandatory MVP dependency.

## 8. ADR reconciliation for this revision

| ADRs | Status / scope |
|---|---|
| 0001, 0003–0008, 0010, 0015–0017, 0019–0020 | Existing Accepted decisions remain recorded; any change proposed here is linked through 0023, not silently marked accepted |
| 0009, 0012–0014, 0018, 0021–0022 | Existing Proposed decisions remain Proposed |
| 0002, 0011 | Historical deleted decisions; do not reuse their IDs |
| [0023 SEARCH/USE and utility](adr/ADR-0023-search-use-service-and-measured-utility.md) | New Proposed amendment: central serving, bounded clients, event semantics and narrower MVP; proposes amendments to 0009/0013/0015/0016/0018/0020/0021 |

Older DESIGN/KNOWLEDGE-DESIGN remain historical target descriptions and current CLI notes where marked. Their local-only hot path, delayed telemetry, load-based probation and old phase schedules must not be read as acceptance criteria for this proposed MVP. No runtime behavior changed in this documentation revision.
