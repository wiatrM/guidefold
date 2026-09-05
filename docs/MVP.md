# Guidefold MVP — scope agreement, epics, user stories, plan

**Status:** Proposed · 2026-09-04 · reconciles `docs/KNOWLEDGE-DESIGN.md` v0.1, `docs/AGENT-SKILLS-RESEARCH.md`, the research deck, and the two competitive briefs (competitive brief, Guidefold-vs-Tessl brief)
**Decision owner:** you · **Delivery:** 2 engineers + 0.5 ML engineer · **Duration:** 8 weeks · **Design partner:** three the design partner teams on the code monorepo (the Meridian fixture until access is granted)

## 1. What the four inputs say, and where they disagree

| Source | Core recommendation | Applied? | Where I disagree or narrow |
|---|---|---|---|
| Research registry + deck | Build **Router 0.1** (swappable 0.6B retrievers/rerankers, field-aware hybrid, hard policy filter, graph-constrained composer, paired eval); fix B0 first; add `knowledge_unit`; 12-week plan; ten concrete code fixes | Yes, the trust engine of the MVP is Router 0.1 and the ten fixes become stories | Field-aware MLP, composer roles, knowledge compiler from traces, own training: **post-MVP**, they need labels the pilot has not produced yet. 12 weeks compressed to 8 by cutting these |
| Competitive brief | Promotion-first: 5-day concierge scan, 4-week pilot; build `scan / propose / eval / promotion PR / probationary serving`; defer Cloud SQL, GCS/CDN, L4 HA, 16 kinds, full G0–G7, UI; P0 = routing bug, P0 = zero-to-value onboarding | Yes: the promotion vertical is the product spine; onboarding and routing are P0 stories | The 4-week pilot assumes routing that already works; Router 0.1 needs ~3 weeks first, so the vertical lands in week 6, not 4. One small Postgres is kept (the decision log must survive; JSON-in-Git would recreate the conflict problem) |
| Tessl brief | Do not compete on registry/evals/governance lists; category = *Agent Knowledge Promotion Control Plane*; moat = decision data; kill criteria | Yes: positioning and kill criteria adopted verbatim | GTM (pricing, ICP, LOI) is out of scope for an internal design partner; the validation gate (owners accept ≥ 30 % of proposals) stays |
| KNOWLEDGE-DESIGN v0.1 | Dedicated skills repos, Knowledge API + Cloud SQL, gates G0–G7, SkillPyramid induction, self-hosted models | Partly: lifecycle, induction and models approved; **dedicated repos rejected** (not possible at the design partner) | Storage redesigned in §2; the full platform is the target after the MVP proves owner acceptance |

Common ground of all four: skills as data are commodity, the trustworthy router is table stakes, and the only thing worth proving first is that **owners accept promoted knowledge**. That is the MVP's success criterion.

## 2. Storage decision (replaces KNOWLEDGE-DESIGN §1.1–§3 and ADR-0011)

**Skills stay in the code monorepo, next to the code they govern. One Postgres. GCS for artifacts. Registry downstream.**

Why the monorepo is fine after all: the workflow's own analysis showed ≥ 95 % of v0.3's projected conflicts were *synthetic*, caused by two committed generated files (`.guidefold/index.lock`, `AGENTS.md` cards), not by skill edits. Remove those and 2,000 engineers editing independent `SKILL.md` files produce an estimated 1–3 genuine same-file conflicts per day org-wide, which is normal. What must change:

| Concern | Mechanism |
|---|---|
| Generated files | **Nothing generated is committed** (ADR-0012). Cards and index are CI artifacts in GCS; `guidefold card` renders the node card at SessionStart; local materialization goes to gitignored paths only |
| Merge-queue throughput | Skill-only PRs (`**/.agents/skills/**`, `guidefold.yaml`) run a **path-filtered fast check** (validate, dedup, drift, index --check, golden eval: minutes); heavy code checks report success without running when only skills changed |
| Bot volume | `guidefold-bot` writes only `proposal/*` branches, ≤ 3 open PRs per node, ≤ 50/day org-wide, never merges; humans never push `proposal/*` (ruleset) |
| Ownership | CODEOWNERS already covers skill directories because they sit under the owning path (ADR-0005 stands); nightly check that `guidefold.yaml` owners match |
| Drift | v0.3 in-repo drift (code diff ∩ `references`) keeps working because skills and code share the repo; fiberplane-style `#symbol` anchors are an optional upgrade |

**One database: Cloud SQL for PostgreSQL 16 with `pgvector`** holds everything that is not skill text: candidates, proposals, assignments, evidence, `knowledge_unit`, telemetry (90 d, hashed principals), rejection memory, provenance, audit log, golden-set results, training pairs. It also holds skill embeddings **for offline uses only** (novelty/dedup at G2, lift candidate search, consolidation). The hot path never touches it: the hook uses the local shard (int8 vectors, ~10 MB at 10k skills, brute-force cosine in stdlib). No Firestore, no Vertex Vector Search, no BigQuery in the MVP; telemetry rollups live in Postgres, BigQuery export is a later one-liner.

**GCS** holds immutable index shards (`index/<shard>/<sha>/`), `latest.json`, body bundles, and pinned model weights (safetensors copied from Hugging Face at a fixed commit SHA). **Agent Registry** receives active revisions from CI for Gemini Enterprise consumers; it is never on the hook path (v1alpha, 3 s per call).

**Plan B, only if skill files are banned from the monorepo entirely:** skill text as versioned objects in GCS (`skills/<urn>/<rev>/SKILL.md`), review workflow and approvals in the Knowledge API with a minimal web UI, CODEOWNERS emulated from `guidefold.yaml`. Cost: we rebuild PR review, diff, comments and audit that GitHub gives for free, ~4 extra weeks. Not recommended; kept as a documented fallback (ADR-0018).

## 3. MVP definition

**One promise:** *Guidefold finds knowledge repeated across teams, proposes its right organizational level with provenance and a before/after evaluation, and serves it general → specific to coding agents only after the owner approves.*

**In scope (8 weeks):**

1. Router 0.1 that beats the current scope-first ranking on a golden set, using public skill-tuned models as-is.
2. Serving without committed generated files, from GCS shards, in Claude Code and Copilot CLI (two harnesses).
3. The promotion vertical: `scan → propose → eval → promotion PR → probationary serving`, with the decision log in Postgres.
4. Minimal lifecycle: statuses `proposed / probationary / active / deprecated`, gates G1 structure, G2 novelty, G3 golden delta, G4 owner approval, G5 probation with a lower-bound posterior; SkillPyramid induction comment-only on two pilot nodes, lift PRs after the first ten manual proposals are reviewed.
5. A one-page demo UI: scope graph, query playground showing router stages, promotion feed.
6. Onboarding in under 30 minutes: `guidefold init`, `guidefold doctor`, one GitHub Action.

**Out of scope (deferred, see §7):** field-aware fusion MLP, composer roles (Start/Support/Check/Avoid), `knowledge_unit` mined from traces, fine-tuning, 16 kinds (MVP uses 5 families as `kind`), full G0–G7, HA GPU endpoint, Codex and Gemini CLI adapters, Vertex AI Skill Registry dual-publish, BigQuery, ARD façade, Backstage export.

## 4. Epics and user stories

Story format: *As a `<role>`, I want `<capability>` so that `<outcome>`.* Roles: **Dev** (engineer using an agent), **Owner** (CODEOWNER of a node), **Platform** (platform/DevEx engineer operating Guidefold), **Agent** (coding agent), **ML** (ML engineer).

### E0 — Foundation and hygiene (week 1)

| # | Story | Acceptance |
|---|---|---|
| E0.1 | As Platform, I want the repo committed with CI (pytest, `py_compile`, validate on the fixture) so that every later claim has a baseline SHA | first commit on `main`; GitHub Action green; `tests/` with ≥ 20 tests incl. mocked gcloud |
| E0.2 | As Platform, I want `Router` separated from `Registry` in the CLI so that storage never defines ranking | `Router` class with `candidates / score / select`; `Registry` only stores and downloads; unit tests per stage |
| E0.3 | As Platform, I want the bootstrap skill and README free of the design partner-specific text so that the product demos anywhere | `[<publisher>]` templated; README status matches code; quickstart ≤ 5 min on the fixture |
| E0.4 | As Platform, I want `guidefold init` and `guidefold doctor` so that a consumer repo is configured in one command | `init` writes `guidefold.yaml` skeleton, hooks, Action, `.gitignore` entries; `doctor` checks gcloud/ADC/roles/models/hook wiring and prints fixes |
| E0.5 | As Platform, I want the ADR set cleaned (superseded deleted, approved marked Accepted) so that the design record is trustworthy | see §8 |

### E1 — Router 0.1 (weeks 1–3)

| # | Story | Acceptance |
|---|---|---|
| E1.1 | As Dev, I want ranking to depend on my task, not only on my directory, so that "write an ADR", "handle an outage" and "add RBAC" return different skills | scope becomes a feature and filter, never the first sort key; the three smoke-test prompts return three different top-3 lists; deprecated excluded by default |
| E1.2 | As ML, I want a golden set of 150–300 queries on the fixture (30 % multi-skill, 30 % sibling ambiguity, 20 % no-applicable-skill, 10 % stale/adversarial, 10 % simple) so that every ranking change is measured | `tests/golden/*.yaml`; metrics Hit@1, Recall@8, nDCG@10, Completeness@K, abstention precision; runner in CI; results table committed per run |
| E1.3 | As ML, I want a bake-off of B0 (current), B1 BM25, B2 generic Qwen3/BGE-M3, B3 SkillRouter-Emb / SKILLRET-Emb, run in batch on one L4 or CPU, so that we pick the index embedder on evidence | one report; model + HF commit SHA + license pinned; weights copied to GCS |
| E1.4 | As Platform, I want `guidefold index` to build an immutable artifact (cards, field-weighted BM25 postings, int8 vectors, graph with `requires/refines/replaces/similar`, `nodes.json`, manifest with git sha) so that the hook never searches the registry | artifact reproducible from a SHA; ≤ 15 MB at 2k skills; `index --check` in CI |
| E1.5 | As Dev, I want the hook to run policy filter → BM25 + dense (local) → RRF → reverse PPR → selection with `requires` closure, ≤ 4 cards, general → specific order, within 300 ms warm / 3 s watchdog, so that injection is fast and deterministic | latency measured on the fixture and on a corporate laptop; identical output for identical (prompt, cwd, sha) |
| E1.6 | As ML, I want `find --experimental` to add top-20 reranking with `SkillRouter-Reranker-0.6B` (USE/SKIP score) in shadow mode with telemetry, so that we measure the reranker before it touches the hook | shadow results logged to `.guidefold/telemetry/*.jsonl`; B6 row in the bake-off |
| E1.7 | As Platform, I want caches keyed by `(urn, revision)` and index sha so that stale bodies are impossible | cache layout `skills/<urn>/<rev>/`, `index/<sha>/`; tests |

### E2 — Serving without generated files (weeks 2–4)

| # | Story | Acceptance |
|---|---|---|
| E2.1 | As Platform, I want no generated file committed so that skill merges never conflict | `materialize` removed; `.guidefold/` gitignored; monorepo keeps a static root stub and `applyTo: "**"` instructions file |
| E2.2 | As Dev, I want `guidefold card` to render my node's card at SessionStart in Claude Code and Copilot CLI so that L0 context is present without committed files | card ≤ 6 KB; Claude Code SessionStart hook and Copilot `sessionStart` `additionalContext` verified; Copilot-from-root degradation documented |
| E2.3 | As Platform, I want CI on `main` to build the shard, embed changed skills, upload to GCS `index/<shard>/<sha>/`, flip `latest.json`, and publish revisions to Agent Registry, so that a merged skill reaches hooks within 10 minutes | end-to-end run on the fixture; propagation time measured |
| E2.4 | As Dev, I want `prewarm` to fetch `latest.json` and only changed shards with checksums so that startup costs ≤ 1.5 s cold | measured; offline works from cache |
| E2.5 | As Platform, I want skill-only PRs to run a fast path-filtered check so that skill review is not queued behind code builds | required check passes in ≤ 5 min for skill-only diffs; drift comment posted |

### E3 — Promotion vertical (weeks 3–6)

| # | Story | Acceptance |
|---|---|---|
| E3.1 | As Platform, I want `guidefold scan` to import 50–200 skills/rules from ≥ 3 teams, map scope and owners, and output clusters of repeated knowledge with provenance, so that the pilot starts from real duplication | cluster report (cosine ≥ 0.85 and trigram Jaccard ≥ 0.4, same/adjacent level, ≥ 2 owner teams); runs on the fixture and on the partner's tree |
| E3.2 | As Owner, I want `guidefold propose` to pick the lowest common ancestor, compose a parent **only from grounded source units**, and produce child patches (`refines` link, replaced text), so that I review a small diff with sources | Promotion Review Pack: sources, target node and kind, parent diff, child patches, ≤ 5 lifted units, `lifted_from: urn@sha` |
| E3.3 | As Owner, I want `guidefold eval` to show routing regression on the golden set and 20–40 paired scenarios (no-skill / selected / oracle / wrong sibling) before I decide, so that I decide on evidence | before/after table; gain rate, regression rate, residual failure rate reported separately |
| E3.4 | As Owner, I want a promotion PR opened by `guidefold-bot` on `proposal/*` with the pack in the body and CODEOWNERS as reviewers, so that approval stays in GitHub | ruleset: only the app writes `proposal/*`; bot never merges; decision and reason captured on merge/close |
| E3.5 | As Platform, I want the decision log (proposal, gates, evidence, decision, reason, rejection memory) in one Postgres so that acceptance is measurable and rejections are not re-proposed for 90 days | Cloud SQL micro instance; schema from KNOWLEDGE-DESIGN §4 (subset); `report` command prints acceptance per node |
| E3.6 | As Dev, I want an accepted parent served as `probationary` inside the pilot scope only, ≤ 1 per injection, in two harnesses, so that impact is validated before full promotion | status honored by the router; telemetry records loads |
| E3.7 | As Platform, I want the first ten proposals produced by the concierge path (batch models, manual composition allowed) in week 3–4, so that owner acceptance is measured before more platform is built | ≥ 10 proposals reviewed; accept/reject/amend with reasons logged; go/no-go at week 4 |

### E4 — Lifecycle and governance (weeks 6–8)

| # | Story | Acceptance |
|---|---|---|
| E4.1 | As Platform, I want gates G1 structure, G2 novelty, G3 golden delta and G4 owner approval enforced in CI for every proposal, so that nothing unreviewed is served | gate results stored per proposal; failing gate blocks the PR check |
| E4.2 | As Owner, I want probation to end on a lower-bound posterior (≥ 5 loads, Wilson lower bound ≥ 0.6, no `report --wrong`) rather than a mean of three, so that promotion is not decided by noise | scorer job; `report --helped|--wrong` command in the CLI; 30-day cap |
| E4.3 | As Platform, I want SkillPyramid-style induction (grouping → screen → fine analysis → grounded build) to run comment-only on two pilot nodes, then open lift PRs once ≥ 30 % of manual proposals were accepted, so that automation follows proof | induction job; comment-only flag; budget ≤ 5 proposals per target node per week; halts below 10 % acceptance |
| E4.4 | As Platform, I want an append-only audit log (actor, action, entity, hashes) and provenance on every model-generated row, so that compliance can trace any served skill | hash-chained `audit_event`; `provenance {model, prompt_hash, input_urns, shard_sha}` |
| E4.5 | As Platform, I want `validate` to enforce `kind` (5 families in MVP), `triggers`, negative trigger, `layer`, `status`, and ZIP/body limits, so that library hygiene is a gate, not advice | fixture updated; lint messages actionable |

### E5 — Demo UI (weeks 7–8)

| # | Story | Acceptance |
|---|---|---|
| E5.1 | As Platform, I want `guidefold ui` (stdlib server + one HTML with d3) showing the scope graph with skills and `requires/refines` edges, so that the demo shows the tree growing | reads the index; replay by git history optional |
| E5.2 | As Dev, I want a query playground showing each router stage (filter, BM25, dense, RRF, PPR, selection) with scores and timings, so that ranking is explainable | runs the CLI in-process |
| E5.3 | As Owner, I want a promotion feed (proposals, decisions, probation status) so that the knowledge flow upward is visible | reads Postgres via the Knowledge API |

## 5. Plan and milestones

| Week | Focus | Milestone |
|---|---|---|
| 1 | E0 all; E1.1, E1.2 start | **M0** first commit, CI green, routing bug fixed, golden set drafted |
| 2 | E1.2–E1.4; E2.1 | **M1** bake-off report: embedder chosen; index artifact reproducible |
| 3 | E1.5–E1.7; E2.2–E2.3; E3.1 concierge scan on partner data | **M2** shadow router beats B0 on the golden set (≥ +10 pp Recall@8, no regression on no-applicable-skill); first cluster report |
| 4 | E2.4–E2.5; E3.2–E3.3; E3.7 ten proposals | **M3 go/no-go:** ≥ 10 proposals reviewed by owners; ≥ 30 % accepted or accepted after one amendment; review time p50 < 15 min |
| 5–6 | E3.4–E3.6 | **M4** promotion PRs live; first parent served probationary in two harnesses |
| 7–8 | E4, E5 | **M5** gates enforced; probation scorer; induction comment-only; demo UI; final report and decision on the platform phase |

Kill / pivot criteria at M3 (from the briefs, kept verbatim): < 20 % of proposals judged useful; owners need > 30 minutes per review; promoted layers do not improve routing or create general ↔ specific conflicts; teams have too few cross-team artifacts.

## 6. Metrics reported every week

Routing: Hit@1, Recall@8, nDCG@10, Completeness@K, abstention precision, hook p50/p95. Promotion: proposals, acceptance rate, review time p50, cross-team reuse (≥ 2 scopes loading a parent), rejection reasons. Safety: unapproved activations (must be 0), unsafe-accept rate (0). Paired end-to-end (from week 5): gain rate, regression rate, residual failure rate, tokens, steps.

## 7. Deferred to the platform phase (after M5)

**Post-bake-off follow-up (open):** [ADR-0022](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md)
remains Proposed. The first three repairs landed in `c08c58c`; this does not complete its target
architecture. Next: benchmark/CLI parity and per-query evidence; shared eligibility plus complete
AND/OR bundles and transitive `requires`; a frozen pilot holdout and calibrated abstention; then
optional contextual models and execution/cost evaluation. See the
[closure plan](reports/bakeoff/E1-closure-plan.md) and
[research architecture review](reports/bakeoff/E1.3-architecture-after-research.md). These repairs
and validation steps precede the platform work below; they are not marked complete by this plan.

Field-aware score tensor + fusion MLP (needs hundreds of labelled judgements); composer roles and generative ordering (≥ 5k ordered bundles); `knowledge_unit` compiled from traces with redacted opt-in corpus; fine-tuning embedder/reranker (≥ 2k / ≥ 5k pairs); full G0–G7 and 16 kinds; HA GPU endpoint and laptop daemon; Codex and Gemini CLI adapters; Vertex AI Skill Registry dual-publish; BigQuery export; ARD façade; Backstage export; RL/self-play never before a stable reward, replay holdout and kill switch.

## 8. ADR cleanup applied with this document

| ADR | Action | Reason |
|---|---|---|
| 0002 hierarchy in URN namespace | **deleted** | superseded by 0008 (URN is server-assigned) |
| 0011 dedicated skills repos | **deleted** | rejected: not possible at the design partner |
| 0005 nested `.agents/skills` layout | stands, note added | skills stay in the monorepo |
| 0006 deterministic context delivery | amended by 0012 | L0 cards no longer committed |
| 0008 identity, 0010 flat metadata | **Accepted** | forced by the registry, verified live |
| 0015 models, 0016 lifecycle + SkillPyramid, 0017 owner review | **Accepted** | approved by you on 2026-09-04 |
| 0009 v2 retrieval, 0012 nothing generated, 0013 Knowledge API (revised: single Postgres), 0014 drift (revised: in-repo) | Proposed | await your decision with this MVP |
| 0018 skills stay in the monorepo; one Postgres; GCS artifacts; Plan B GCS-native | **new, Proposed** | replaces 0011 |
| [0020 two-tier dense retrieval](adr/ADR-0020-two-tier-dense-retrieval.md) | **Accepted** | static student and neural teacher remain separate; dense admission requires evidence |
| [0021 index sharding and global word table](adr/ADR-0021-index-sharding-and-a-global-word-table.md) | Proposed | scale and cache identity require measurement |
| [0022 admissibility, relevance and bundle completeness](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md) | Proposed | first repairs implemented in `c08c58c`; remaining work tracked in §7 and the closure plan |
