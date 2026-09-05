# ADR-0024: Target architecture — one contract, three deployment tiers, a telemetry flywheel for dense, and model-based composition

**Status:** Proposed · 2026-09-05 · the target system beyond the MVP; nothing here is deployed, trained or admitted by this ADR · request boundary amended by [ADR-0025](ADR-0025-harness-service-context-contract.md) (Accepted); architecture status unchanged
**Implemented request contract:** [Harness-service 1.1](../HARNESS-SERVICE-CONTRACT.md); repository/path resolution and delivery limits are covered by schema/runtime/HTTP tests. Broader production and telemetry guarantees below remain proposed.
**Amends:** ADR-0023 (adds deployment tiers; the admitted service profile is sparse-only until dense earns admission per tenant), ADR-0020 (the static student is closed as a quality path and kept only as an optional offline artifact), ADR-0021 (sharding is scoped to the local tier), ADR-0022 (the composition stage may be a model), ADR-0009 (client-side hybrid becomes tier T0 only).
**Confirms:** ADR-0001 (Git is the source of truth), ADR-0003 (bootstrap skill + CLI, not per-harness plumbing), ADR-0006/0012 (deterministic L0 delivery, nothing generated committed), ADR-0015 (self-hosted skill-tuned models — this ADR names where their training data comes from), ADR-0017, ADR-0019.
**Delivery:** [MVP](../MVP.md) §2 (tiers), §4 (E2.9, E6.2, new E7), §5 (plan).

## Context

Three weeks of pre-registered experiments — [DENSE-PROGRAM](../reports/bakeoff/DENSE-PROGRAM.md) and the
[E1.1b service spike](../reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md) (branch
`feat/e11b-service-optimization`, commit f29f8ac) — fixed the shape of this system more firmly than any design
discussion could. Everything below was measured through the product path
(`policy_filter → candidates → score → select(admissible=…)`) on real labelled corpora, with paired-bootstrap
95 % confidence intervals (1 000 resamples):

| Fact | Where | Number |
|---|---|---|
| Full 0.6B encoder, zero-shot, **in-distribution** (SKILLRET test: 6 006 skills / 4 392 queries) | PR #33, [report](../reports/bakeoff/SKILLRET-test-2026-09-05.md) | hit@1 **+21.79 pp** [20.56, 23.11]; `all_required@4` **+17.96 pp** [16.80, 19.08] vs sparse |
| Same encoder, zero-shot, **out-of-distribution** (SkillRetBench: 501 / 1 250) | PR #35, [report](../reports/bakeoff/SkillRetBench-R1-encoder-2026-09-05.md) | hit@1 +8.33 pp [5.75, 11.25]; HSR@4 −10.00 pp [−15.67, −4.00]; `all_required@4` **+0.67 pp [−1.50, +2.83] — not significant** |
| Distilled static student (family F2) | DENSE-PROGRAM §7 | covers 7.64 % of BM25 misses vs 8.76 % for its own teacher; every gate fails |
| Document expansion, T5-base doc2query (F3) | PR #41 | nDCG@10 +0.81 / +0.90 pp; `all_required@4` +0.5–0.7 pp against a +2.0 pp gate |
| Flat BM25F field weights | PR #39, [report](../reports/bakeoff/FROZEN-sparse-flat-2026-09-05.md) | +5–8 pp headline on both corpora; HSR@4 **+4.67 pp** against a ±1.0 pp guardrail — not adopted |
| Bundle completeness, every arm | PR #36, [diagnosis](../reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md) | `all_required@4` at k = 3 is **0.000**: `select()` takes the literal top-4; nothing composes |
| Local in-process hook at 6 006 skills | [R4](../reports/bakeoff/R4-latency-lazy-load-2026-09-05.md) | warm p95 **581 ms**; ~250 ms was eager parsing of 89 630 terms — cost scales with the vocabulary, not the document count. After lazy terms/postings ([R4b](../reports/bakeoff/R4b-lazy-terms-postings-2026-09-05.md), PR #45): **320 ms**, still above T300; ranking bit-identical (0/1 000 mismatches) |
| Service, **sparse-only**, optimised (BM25 contributions cached, resident snapshot) | E1.1b | HTTP c = 1 p95 **56 ms**, c = 4 **152 ms**, fresh client process **119 ms**, burst of four fresh clients **179 ms**, 200/200, **no GPU** |
| Service, hybrid with a resident 0.6B encoder, optimised + C++ ranking | E1.1b | c = 1 152 ms, fresh 206 ms, **c = 4 444 ms**: one encode costs 86 ms and `encoder_queue` p95 is 289 ms ≈ three encodes — the encoder is a serialised resource |

Read together, four things follow:

1. **Dense did not lose; zero-shot on foreign data lost.** +17.96 pp and +0.67 pp on the same metric, from the
   same model, is the distance between the encoder's training distribution and the deployment corpus. That
   distance is a property of the training data, not of the model — and an organisation that logs which skill the
   agent actually used after a query owns exactly the data that removes it.
2. **Bundle completeness is a decision problem, not a retrieval problem.** No ranking change moved k = 3 off
   zero. A stage whose job is "I took A; the task still needs B" does not exist yet.
3. **Serving is cheap; the local process does not scale.** One CPU core answers a sparse query in ~50 ms. The
   local artifact fails its budget at 6 006 skills for a reason — vocabulary — that only sharding or a service
   removes.
4. **Every injected card is paid for at the agent model's token price on every prompt.** The ≤ 4-card / 80-line
   cap (ADR-0006) is a cost gate as much as an attention gate; §Cost puts numbers on it.

What large agent vendors do with the same problem is visible in their harnesses: most tools stay out of the
context window and the model is given a *search tool* it calls on demand (Claude Code's deferred tools and
`ToolSearch`, for one); retrieval over tool or skill descriptions narrows the set, and the model composes.
Guidefold's bootstrap-skill + CLI design (ADR-0003) is already that pattern. What the vendors add is a hosted
engine, a feedback loop that trains the retriever on their own traffic, and model-based selection. This ADR
adopts those three additions and closes the parts that did not survive our measurements.

## Decision

### 1. One contract, three deployment tiers

The router contract is fixed (ADR-0022): `policy_filter → candidates → score → compose(admissible=…) → ≤ 4 cards
| cannot_fit | abstain`, integer-only sparse path, identity-keyed cache, one index format. What varies is
**where** `candidates`/`score` run:

| Tier | For | Search backend | Dense | Added infrastructure | Measured / expected |
|---|---|---|---|---|---|
| **T0 local** | one team; offline or air-gapped; a corpus small enough | in-process `skills/guidefold/scripts/guidefold` (stdlib + PyYAML), sharded by node (ADR-0021) | none; the static table only if it ever clears a gate | none | admitted only where `guidefold doctor` measures warm p95 < 300 ms on the consumer's own corpus. Measured curve (R4b, PR #45): p95 113 ms at 500 skills, 188 ms at 2 000, 262 ms at 4 000, **320 ms at 6 006** — the T300 crossover is **≈ 5 300 skills**; above it, T1 or sharding |
| **T1 department** | up to ~10 000 skills, one region | single-node `serve` (CPU), resident sparse snapshot, atomic swap | shadow only | one small VM + the existing Postgres | sparse c = 4 p95 **152 ms** measured at 6 006 skills on one node |
| **T2 organisation** | full catalogue, thousands of developers | HA regional SEARCH/USE service (ADR-0023): CPU API + GPU encoder worker with dynamic batching | admitted **per tenant** after the flywheel (§3) clears the gates in-distribution | 2 CPU nodes, 2 GPUs, HA Postgres, CDN | designed for 100 QPS; hybrid c = 4 must reach ≤ 300 ms server-side through batching — **not yet measured** |

Rules. The consumer selects a tier in `guidefold.yaml` (`search.backend: local | service`, `search.url`). The
client is the same single file at every tier and falls back service → local sparse on deadline or outage
(ADR-0023 §3). The **sparse ranking is bit-identical across tiers**, and CI proves it with the frozen-CLI parity
check E1.1b already uses (`ranked_sha256` / `selected_sha256` per query on the frozen dev queries). A tier is a
deployment choice, never a fork of the product.

### 2. Three delivery layers, priced in tokens

| Layer | What the agent gets | When | Cost driver |
|---|---|---|---|
| **L0 scope card** | ≤ 6 KB card for the current location, digests only (ADR-0006/0012) | SessionStart; stable for the session, so prompt-cached | ~1 500 tokens once per session |
| **L1 search** | `guidefold find` as a tool the agent calls, or the hook profile (≤ 4 cards) | on demand / per prompt | ~60 tokens × cards × prompts |
| **L2 use** | the exact `urn@revision` body, checksummed, from object storage/CDN; emits the USE event | when the agent decides to apply a skill | bytes, not tokens |

The per-prompt hook injects **at most four cards** and prefers the cached L0 card; the 15-candidate shortlist is
reserved for the explicit L1 tool call. §Cost shows why: the same 5 000 developers cost roughly $650 or roughly
$24 000 a month in agent-context tokens depending on that one choice.

### 3. Quality is earned by a flywheel, not by a zero-shot model

Dense retrieval is admitted **per tenant**, **in-distribution**, by the same frozen gates every family in
DENSE-PROGRAM faced (`all_required@4` ≥ sparse + 2.0 pp with the CI excluding 0; HSR@4 and hit@1/nDCG@10 not
worse by more than 1.0 pp; cost within the tier), on a dev set built from that tenant's own traffic:

1. **Labels come from telemetry** (ADR-0023 §5, [SEARCH/USE contract](../SEARCH-USE-TELEMETRY.md)):
   `search_id → exposed cards → USE(urn@rev)` yields (query, positive) pairs; cards exposed and *not* used in the
   same search yield hard negatives — the HSR failure mode, mined directly. Query text enters the training corpus
   only through the separate redacted opt-in (ADR-0023 §5); the flywheel runs on whatever volume that opt-in
   yields and reports its size.
2. **The encoder is fine-tuned weekly** on those pairs — self-hosted, open weights (ADR-0015) — and the snapshot
   pipeline (ADR-0023 §4) re-embeds the affected vector set under a new model identity.
3. **Admission is a CI run** of the frozen gates on a held-out slice of the tenant's dev set. A model that fails
   stays in shadow; a model that passes is served for that tenant, with rollback to the previous snapshot and to
   sparse-only.
4. Until a tenant clears the gates its service profile is **sparse-only** — the profile measured at 56/152 ms —
   and the hybrid runs in shadow, producing the comparison.

This turns the +17.96 pp in-distribution result from a flattered benchmark into the target the flywheel is
expected to approach, while the +0.67 pp out-of-distribution result stays the honest floor for a tenant with no
data yet.

### 4. Composition is a model's job when the query is a bundle

ADR-0022 stage 4 becomes a **composer** with two admitted implementations behind one interface, selected per
tier: (a) the deterministic integer composer — bundle detection by score gap, coverage-aware selection,
`requires` closure — at T0 and as the fallback everywhere; (b) a **model composer** — a small self-hosted
fine-tuned model on the T2 GPU worker, or an LLM call — that receives the query and ≤ 15 admissible candidates
and returns ≤ 4 cards or `cannot_fit`. Both are gated on `all_required@4` on SKILLRET-train dev (it carries
k = 1/2/3 labels) and then once on both test corpora. The model composer runs only for queries the detector marks
multi-skill, so its cost is bounded (§Cost). Admissibility binds before the composer sees anything (ADR-0022 §1).

### 5. Synthetic queries at index time, with a strong generator

F3 is closed for T5-base. The index build may add an `expansion` field generated by a strong LLM (≈ 10 queries
per skill, incremental per changed skill, ≈ $300 once for 30 000 skills) — the InPars/Promptagator result, not
the doc2query-T5 one. It is an experiment under the standard budget (≤ 6 dev configurations, once on test), not a
dependency.

### 6. Evaluation is part of CI

Every snapshot build runs the frozen dev set through the product path and blocks the manifest-pointer swap on a
gate regression; the same run produces the per-query JSONL the composer and the flywheel consume. The 26-skill
fixture stays a unit-level regression; quality claims cite only real labelled corpora (project rule since
2026-09-05).

### 7. What is closed

Closed as quality paths, numbers on record in DENSE-PROGRAM §7: F1 zero-shot encoder hybrid *as an admitted
profile*, F2 static student, F3 with T5, F4 small contextual model in the client. F5 derived edges and F6
sibling maps stop being families and become inputs to the composer. Sharding (ADR-0021) stays for T0 and the
offline fallback; T1/T2 do not need it — the whole index fits in RAM (6 006 skills ≈ 30 MB of int8 vectors plus
postings).

## Considered options

| Option | Outcome |
|---|---|
| **A. Stay local-only and optimise harder** | p95 581 ms at 6 006 skills is vocabulary-bound; sharding fixes it for T0 but yields no feedback loop and no shared telemetry. Kept as T0. |
| **B. Service with the zero-shot encoder as the default profile** (ADR-0023 as written) | fails `all_required@4` out-of-distribution and pays an idle GPU for +0.67 pp; the c = 4 gate is unmet. Kept as shadow. |
| **C. Managed hybrid engine** (Vespa Cloud, Elastic, Vertex AI Search, Postgres with pgvector + pg_search) | viable at T2 and engine-agnostic under the contract; deferred because it adds a control plane before 100 QPS needs one. Revisit if the in-house `serve` cannot hold the T2 envelope. |
| **D. Put every card in context and let the agent choose** | does not scale past a few hundred skills and costs ≈ $24 000 a month in tokens at 5 000 developers before any quality gain. |
| **E. This ADR: tiers + flywheel + composer** | chosen — every claim it depends on is measured or scheduled for measurement, and the expensive parts are gated per tenant. |

## Cost model — 5 000 developers (an estimate; GCP on-demand list prices, September 2026)

Assumptions, stated so they can be changed: 70 % daily active (3 500); ~80 agent prompts per developer per day
→ **≈ 300 k searches/day, ≈ 9 M/month**; ≈ 8 QPS average in working hours, ≈ 25 QPS peak, designed for 100 QPS;
5 000–30 000 skills (≈ 220 k terms at 30 k by Heaps' law; ≈ 30 MB of int8 vectors).

| Item | Sizing | $/month |
|---|---|---|
| Sparse retrieval + RRF, 2 CPU nodes HA (4–8 vCPU) | ≈ 50 ms CPU per request in Python ≈ 20 QPS/core; a Rust/Vespa engine ≈ 10× cheaper | 300–600 |
| Encoder + reranker, 2 × L4 (24 GB) HA | fine-tuned 0.6B with dynamic batching: hundreds of QPS per GPU | 700–1 050 |
| Composer **A**: self-hosted 1–3B on the same GPUs | — | ≈ 0 |
| Composer **B**: Haiku-class API, multi-skill queries only (≈ 25 %) | ≈ 1 700 input + 60 output tokens ≈ $0.002 × 2.25 M | 4 000–6 000 |
| Postgres HA (≈ 45 M event rows/month at 90-day retention; revisions; rollups) | 4 vCPU / 16 GB | 500–700 |
| Object storage + CDN (bodies, snapshots) | | < 50 |
| Load balancer, egress, KMS, secrets | | 100–200 |
| Observability | | 300–800 |
| Weekly encoder fine-tune | 1–2 GPU-hours/week | < 50 |
| Synthetic queries at index time | 30 k × 10, then incremental | ≈ 20 (after ≈ $300 once) |
| **Infrastructure total** | | **≈ $2 000–3 500 (A) · ≈ $6 000–9 500 (B)** — $0.40–1.90 per developer per month |

**Agent-context tokens** — paid to the agent model on every prompt (Sonnet-class input at $3/M; prompt cache
≈ 10 % of that):

| What the hook injects | tokens/prompt | uncached | cached |
|---|---|---|---|
| a 15-candidate shortlist | ≈ 900 | ≈ $24 000 | ≈ $2 400 |
| ≤ 4 cards (this design) | ≈ 240 | ≈ $6 500 | ≈ $650 |
| L0 scope card, stable per session | ≈ 1 500 once | — | ≈ $400 |

**People** — the real cost: build 6–9 months at 5–6 FTE (PM; 2–3 backend/infra; 1–2 ML for retrieval and
evaluation; 0.5 SRE; 0.5 security/compliance); run 2–3 FTE. At EU loaded rates (€10–15 k per FTE-month): build
€50–90 k/month, run €20–45 k/month; US roughly 2×. **Steady state ≈ €25–55 k/month, infrastructure under 15 % of
it.**

**Against it:** if the system saves each active developer **one minute a day** (no hunting for the right skill,
no wrong-skill detour), 3 500 × 1 min × 21 days ≈ 1 225 hours/month ≈ $98 k/month at $80/h; two minutes ≈ $196 k.
That minute is a hypothesis. E6.7 (paired pilot tasks) exists to measure it, and no adoption claim is made
before it does.

At T0 the infrastructure line is $0; at T1 it is one small VM plus the existing Postgres (≈ $100–300/month). The
people line does not scale down as kindly — a T1 department still needs an owner.

## Measured vs assumed

| Claim this ADR relies on | Status |
|---|---|
| A sparse-only service clears 300 ms at c = 4 and 6 006 skills without a GPU | **measured** (E1.1b, f29f8ac) |
| The local in-process hook fails at 6 006 skills for vocabulary reasons; the T0 crossover is ≈ 5 300 skills | **measured** (R4, R4b: 320 ms at 6 006 after lazy terms/postings; size curve 500 → 6 006) |
| Zero-shot dense fails the completeness gate out-of-distribution and passes it in-distribution | **measured** (PR #33, #35) |
| Composition, not ranking, is where `all_required@4` is lost | **measured** (PR #36: k = 3 → 0.000) |
| Token cost of injected cards | arithmetic on list prices; volumes assumed |
| Fine-tuning on a tenant's USE pairs closes that tenant's out-of-distribution gap | **assumed** — strong prior from the in/out-of-distribution pair; needs a pilot with real USE events (E7.2) |
| A model composer lifts `all_required@4` by ≥ 2 pp within budget | **assumed** — measurable in a week on SKILLRET-train dev (E7.3) |
| Dynamic batching brings the hybrid c = 4 under 300 ms server-side | **assumed** — and 86 ms per single encode on an RTX 4090 is ≈ 4× the expected cost and itself unexplained |
| Strong-LLM synthetic queries beat T5 doc2query | literature (InPars, Promptagator); **unmeasured here** (E7.4) |
| One minute per developer per day | **hypothesis** — E6.7 |

## Consequences

**Positive.** One product from a single team to a whole organisation, with the same client, index and tests.
Dense is bought only where it pays, per tenant, with rollback. The composition gap gets a component whose job it
is. The plan carries its own cost model and an explicit list of what is still assumed.

**Negative.** T2 adds a GPU worker, a training pipeline and a model-identity dimension to every cache key and
snapshot (ADR-0023 §4). A model composer is non-deterministic across model versions and must be pinned and
replay-logged like the encoder. A tenant with little traffic never leaves sparse-only — and the plan says so
rather than pretending otherwise.

**Risks.** The flywheel depends on the opt-in redacted query corpus; if opt-in volume is low, dense stays in
shadow for that tenant (acceptable — sparse-only is the measured floor). The 86 ms encode may be a serving bug;
if it is a hardware floor, T2 hybrid needs more GPUs than costed. Composer-B spend is bounded by the multi-skill
detector's precision — a detector that fires on every query quadruples that line.

## Implementation notes

Delivery is mapped in [MVP](../MVP.md): tiers and portability in §2 and E2.9; the sparse-only admitted profile
and the shadow encoder in E6.2; the composer decision in E7.3; evaluation-as-CI in E7.5; the flywheel in
E7.1–E7.2 (beyond the 8-week horizon, because it needs pilot telemetry). This ADR becomes `Accepted` when the
decision owner accepts the tier table and the per-tenant admission rule; nothing in it is retroactively marked
done.

## Related decisions

ADR-0003 (the tool pattern this extends); ADR-0006/0012 (L0); ADR-0015 (self-hosted tuned models — the flywheel
is how they get their data); ADR-0020/0021/0022/0023 (amended as listed in the Status line).

## References

- [DENSE-PROGRAM v2.3](../reports/bakeoff/DENSE-PROGRAM.md); [E1.1b service feasibility](../reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md); [SkillRetBench R1](../reports/bakeoff/SkillRetBench-R1-encoder-2026-09-05.md); [SKILLRET test](../reports/bakeoff/SKILLRET-test-2026-09-05.md); [sparse diagnosis](../reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md); [R4 latency](../reports/bakeoff/R4-latency-lazy-load-2026-09-05.md); [flat weights](../reports/bakeoff/FROZEN-sparse-flat-2026-09-05.md); F3 in PR #41.
- Cormack, Clarke, Büttcher, *Reciprocal rank fusion outperforms Condorcet and individual rank learning methods*, SIGIR 2009 — the fusion used by `score`.
- Nogueira et al., *Document expansion by query prediction*, arXiv:1904.08375 (doc2query — the closed F3 generator); Bonifacio et al., *InPars*, arXiv:2202.05144; Dai et al., *Promptagator*, arXiv:2209.11755 — LLM-generated training queries, the E7.4 hypothesis.
- [SkillRouter v5](https://arxiv.org/html/2603.22455v5) — the bundle-completeness metric family and the encoder latency figures already cited in ADR-0023.
