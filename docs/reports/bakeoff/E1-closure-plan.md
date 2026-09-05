# E0 + E1 closure plan — what the peer review changes, and the system we ship

**Status:** Accepted by the TL · 2026-09-05
**Responds to:** [`E1.3-peer-review-2026-09-05.md`](E1.3-peer-review-2026-09-05.md)
**Inputs:** the review's two audit scripts and data, PR #19 (config sweep with a held-out split),
five papers analysed in [`docs/RESEARCH.md`](../../RESEARCH.md), followed by the full-cache
review [`E1.3-architecture-after-research.md`](E1.3-architecture-after-research.md) and
[ADR-0022](../../adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md) (Proposed).

**Revision note, 2026-09-05:** `c08c58c` has repaired CLI BM25F units, the dense zero-weight gate
and inadmissible dependency injection through the product entry points. This note preserves the
TL's Accepted status and historical findings; complete bundle composition, benchmark parity and
post-repair performance measurement remain open.

---

## 1. Assessment of the peer review

**Verdict: accepted.** The review is careful, reproducible (its audit scripts are now in
`tools/eval/`, its data under `validation/`), and correct on every technical point I could verify
independently. It found no fabrication. It found six errors, and **all six trace to the TL's own
specification or analysis, not to the implementing agents** — they built what the spec said.

| # | finding | verified | root cause | fixed in |
|---|---|---|---|---|
| 1 | `_dense_rank` computes `dot/normsq`, not cosine; inverts orderings | yes — counterexample A=(3,9), B=(1,2) | ROUTER-SPEC wrote `a·q·\|b\|² ⋛ b·q·\|a\|²` verbatim; the correct sqrt-free form is `(a·q)²·\|b\|² ⋛ (b·q)²·\|a\|²` with sign | this PR, with the counterexample as a test |
| 2 | the `w_dense` gate was unreachable: B1 Recall@8 = 0.9799, +3 pp → 1.0099 | yes, arithmetic | TL wrote the gate against a saturated metric | gate retired, §3 |
| 3 | `completeness@4` checks only grade 3; grade-2 *required companions* ignored; B1 multi_skill 95.45 % → 74.24 % | yes — README defines grade 2 as "required companion" | TL's metric definition, and a test that pinned it | `all_required@4` added, both series kept |
| 4 | benchmark arms B1–B6 ran on the full corpus with no policy filter; B0 and the product see 8–18 filtered candidates | yes | TL's bake-off brief did not require the product's filter | §3, benchmark = product path |
| 5 | `RESEARCH.md` quoted only the SkillRet rows BM25 beats; the same table has SkillRet-0.6B at 81.12 | yes | TL cherry-picked | RESEARCH.md rewritten |
| 6 | B6's −25 pp on stale was mostly a **deprecated leak** into the reranker's candidates (10/22 vs 4/22 promoted to #1), not domain shift; with a fair filter −5 pp, with full body 0 | yes, from the review's data | TL over-explained a result the review then measured | RESEARCH.md §2.2 |

Where the review and the TL still differ, it is on emphasis, not fact:
- "RRF's narrow range does not prevent thresholding" — true; the substantive point (RRF discards
  magnitudes, so the top-1 in a single list always scores 1/61) is the same conclusion. Restated.
- "revisit the reranker only if fine-tuned" — withdrawn. The review's order is right: filter,
  input, metrics, cost, *then* tuning.

Two things the review did **not** change: `w_dense = 0` ships, and the reranker stays in shadow
mode. The reranker's measured scoring latency exceeds the hook budget. Dense remains disabled
pending a comparison on the corrected product path; historical unfiltered results do not establish
which method wins after all repairs.

---

## 2. What the five papers say, condensed to decisions

| paper | its evidence | our measurement | decision |
|---|---|---|---|
| SkillRet | BM25 51.69 vs off-the-shelf 0.6B 61.94 vs **tuned 0.6B 81.12** NDCG@10 | historical unfiltered B1 hit@1 0.8736; skill-tuned SKILLRET teacher 0.8678 | test released checkpoints fairly after repairs; own fine-tuning is conditional on residual errors and pilot evidence |
| SkillRet | Terminal-Bench: no retrieval 65.5 % success / $0.86 vs SkillRet 65.8 % / $0.78 per trial | a different experiment from its BM25 comparison; no reported confidence interval for this difference | measure success and cost directly; do not attribute the execution delta to the NDCG gain over BM25 |
| SkillRouter | body access 37–44 pp; compact pipeline multi FC@10 35.3 % | historical B1 sweep preferred body weight 1; its all_required@4 was 49/66 on multi_skill | preserve body access; retest weights with corrected BM25F and measure complete bundles separately from primary hits |
| GoS | graph propagation +5.1 reward at 1 000 skills; bundle > top-1 | PPR ≡ closure at 26 skills, byte-identical | ship closure; re-test PPR at pilot scale (§3, P2) |
| SkillResolve | HSR@K — harmful sibling exposure | B6 exposed deprecated at #1 in 10/22 | **adopt HSR@K** on (helpful, risky) pairs; deprecated/postgres-auth is pair #1 |

---

## 3. The experiments that close E0 + E1 — in order, with stop conditions

Measurement infrastructure and product parity precede model selection. Historical float B1,
pre-repair CLI baselines and corrected CLI runs are separate series; each run records its scorer,
policy, composer, metric version and code SHA.

### E1.1b — immediate service feasibility and latency optimization (2026-09-05)

The product owner requested this experiment before service-dependent E2/E6 implementation.
The current product path to validate is the optimized sparse service; resident full-encoder
and separate-worker experiments remain shadow work and do not block its feasibility decision.

E1.1b service protocol v2 (2026-09-05) requires whole-client p95 ≤400 ms over loopback, measured separately at c1 and c4 with a fresh client process per request and a ready resident server/index. Server-side p95 must be ≤300 ms at both loads, measured from HTTP admission before authentication or queueing through synchronous logging and JSON response serialization. Whole-client timing includes startup/imports, local reads, auth, transport, queues, retrieval/composition, telemetry and output/exit. Report all attempts, errors and successful-within-budget counts under frozen workload, corpus, hardware and runtime identities. WAN/TLS/IAM and the actual harness remain a separate E6 integration gate, never implied by loopback success. Optimized sparse is the production candidate; hybrid remains shadow until independent latency and quality admission.

Protocol v2 uses inclusive ≤ comparisons. Historical T300/T500 budgets and E1.1b JSON evaluated with strict <400 retain their original definitions and results. Historical T300 means the whole hook in a fresh process, not an in-process kernel or the new server-side 300 ms target. A p95 target is not hard cancellation; the server allocation provides planning headroom, not a guarantee that the client target passes.

Measure the resident 6,006-skill sparse index, exact revision delivery and local operational
traces. Publish cold process readiness, HTTP/fresh-client p50/p95/p99, all failure denominators,
deadline/denial/outage/restart behavior and an explicit proceed/change/stop decision in
[E1.1b service feasibility](E1.1b-service-feasibility-2026-09-05.md). Publish hybrid shadow
measurements separately; latency success alone cannot admit a neural profile.

Optimize the measured hot path before deciding whether a native rewrite is needed. Precomputed
integer BM25 contributions and resident dense matrices must preserve scores and ranking;
encoder/runtime changes require paired vector/rank checks. Freeze the same CLI source bytes
across comparisons because other work may update the shared checkout. Record hardware and
concurrent load; a local result never establishes WAN/TLS/IAM or actual harness performance.

The spike does not adopt a neural model for quality, execute skill bodies, or turn hydration
into a usefulness metric. Controlled cache/lease tests are distinct from the shipped local
fallback, whose integration remains in E2.6. A missed latency/queue gate requires another
bounded optimization or a narrower supported profile before dependent serving commitments.

### P0 — fix the ruler *(this PR + one follow-up, ~1 day)*

| work | done when |
|---|---|
| `all_required@4` alongside `completeness@4`; both series in every table, never rewritten | ✅ this PR |
| `_dense_rank` is true cosine; counterexample is a test | ✅ merged before `c08c58c` |
| CLI BM25F units, effective `w_dense=0`, excluded dependencies skipped by `route`/`find` | ✅ `c08c58c`; explicit unresolved results and atomic full closure remain open |
| retire the Recall@8 gate; **new gate written before the next run**: `all_required@4` non-inferior and HSR@4 non-worsening on filtered candidates, at the real 4-card budget | ADR-0020 amended, this PR |
| explicit denominators in every report (174 answerable, 46 should-abstain, 133 with distractors, **1** multi_skill with a distractor) | this PR, report headers |
| runner records **per-query** rankings, scores, filtered/unfiltered candidates, drop reasons, and the input hashes — so paired bootstrap is possible next time | follow-up PR |

### P0 — benchmark = product *(follow-up, ~1 day)*

| work | done when |
|---|---|
| every arm shares the shipped policy, sparse scorer and composer, at the shipped 4-card cap, from the case's `cwd`; neural adapters stay outside the CLI | candidate sets, scores and rankings match the CLI on all 220 cases |
| one BM25 definition: the arms' pseudo-document BM25 is replaced by the CLI's per-field-normalised BM25F | identical scores, not just identical order |
| dense artifact round-trip test: build → serialise → load → rank, offline and in CLI, same result | passes on the fixture with a synthetic word table |

### P1 — fair ablations on the fixed ruler *(~2 days)*

Run **once**, all arms, on filtered candidates, reporting `hit@1 · nDCG@10 · all_required@4 · HSR@4 ·
warm p50/p95`: sparse · sparse + closure · sparse + PPR · sparse + static student · sparse + tuned
teacher (SKILLRET) · each + reranker. Compare the checkpoint's documented prefix-capped input
with full-body input up to 4 096 tokens as separate arms; record truncation and latency for each.
Measure candidate union and an oracle candidate pool separately from final bundle selection.
Freeze configurations before the run; no expected winner is an acceptance criterion.

### P1 — golden set repair *(~1 day)*

- Build independently judged distractors from semantic, lexical, taxonomy and random candidates.
  This adapts SkillRouter's **training** recipe (Appendix F); its Hard evaluation instead uses
  three synthetic strategies (Appendix B). Audit functional substitutes before labelling negatives.
- HSR pairs: label helpful/risky siblings where a valid helpful skill exists; retain no-applicable
  cases separately rather than inventing a positive. Report both query and pair denominators.
- Label AND requirements, OR alternatives and transitive prerequisites separately. Mark cases whose
  eligible complete bundle **cannot fit in 4 cards**; report feasibility and incomplete responses
  separately instead of hiding them by changing the metric denominator (review §6).
- The current 220 stays as the **dev/regression** set. It is not evidence of generalisation.

### P2 — the pilot test set *(blocks any model decision)*

Real tasks from 2–3 teams on the pilot corpus (200–500 skills). Frozen before use, split by
task-family, labels reviewed independently, candidates from *different methods* judged blind so the
set does not favour lexical matching. **Paired bootstrap on task families, not on paraphrases.**
Minimum detectable difference agreed before sizing.

### P2 — execution-level evaluation *(the metric the MVP actually promises)*

No Guidefold · sparse + closure · contender bundle · eligible oracle bundle, on paired tasks:
**task success, policy violations, tokens, cost and wall-clock.** Keep execution conditions matched.
SkillRet's Terminal-Bench comparison is no retrieval versus SkillRet, not BM25 versus SkillRet; it
reports similar success and lower cost without establishing a significant success gain. A cost
reduction can justify deployment under a predeclared success non-inferiority bound. If even oracle
skills do not help, investigate skill content and use before further retrieval optimisation. Owner
acceptance of proposed knowledge (MVP §3) remains a separate product metric.

---

## 4. The system we ship, and the next decision

At `c08c58c`, the product uses **integer BM25F over all fields, a policy filter, greedy depth-2
`requires` selection and general→specific injection, up to 4 cards**. Dense is disabled; the
reranker stays in shadow. Decayed closure is the default propagation mode; its equivalence to PPR
was measured on the earlier shallow fixture, not established for arbitrary graphs.

The merge fixes BM25F units, enforces the dense zero-weight gate and passes admissibility into
selection through `route` and `find`. Selection now skips excluded dependencies but does not yet
report unresolved requirements or reject an incomplete bundle atomically. Direct legacy
`select(admissible=None)` calls keep only the deprecated dependency check. ADR-0022 records the
remaining target contract.

Historical B1 hit@1 0.8736 versus the skill-tuned SKILLRET teacher's 0.8678, B1 multi-skill
`all_required@4 = 49/66`, and the earlier 65 ms timing remain labelled historical results. They do
not establish corrected product completeness, superiority or latency. Measure a fresh baseline
with numerator/denominator, machine and SHA before selecting a challenger.

A released contextual checkpoint may earn a place without further training. Admission requires
measured marginal eligible coverage, complete-bundle and harmful-sibling guardrails on the frozen
pilot set, and useful execution or cost improvement within the relevant artifact and whole-hook
budgets. Own fine-tuning follows only if controlled residual errors and available labels justify it.
Neither retrieval papers nor a single local sweep establish that a larger model cannot improve
completeness, or that improving completeness necessarily improves execution.

---

## 5. What this closes in E0 + E1

| item | state after this plan |
|---|---|
| E0.1–E0.5 | closed; unaffected by the review |
| E1.1, E1.7 | historical closure retained; shared eligibility across all adapters and complete model/cache identity require follow-up under ADR-0022 |
| E1.2 golden set + metrics | **reopened** for P0 (metric versioning, denominators) and P1 (distractors, HSR pairs); the 220 cases stand as dev/regression |
| E1.3 bake-off | conclusion (`w_dense = 0`) stands; **report re-labelled**: unreachable gate retired, denominators stated, arms marked as unfiltered-corpus, SkillRet table complete |
| E1.4, E1.5 | original implementation milestones retained; `c08c58c` changes scoring/selection behavior, so corrected baseline, parity and whole-hook latency must be measured; full composer remains open |
| E1.6 | conclusion (shadow) stands **on cost**; quality re-attributed from domain shift to the deprecated leak |

The repairs change product scoring and dependency selection. The justified release decision is
to keep dense disabled and the reranker in shadow while measuring the corrected sparse baseline,
then compare optional models on eligible complete bundles and execution utility at pilot scale.
The original 26-skill fixture remains regression evidence, not a claim that sparse retrieval is
universally superior.

---

## 6. Contract audit on the landed fixes (added 2026-09-05, after PR #21)

The reviewer's `tools/eval/audit_router_contract.py` probes four numerical/policy contracts with
hand-controlled statistics — no tokenizer, no index build, CPU only — so a failure is a formula
error, not a corpus effect. Their run compared the pre-fix baseline with the fix branch
(`router-contract-review-2026-09-05.json`, status "dirty worktree, proposed fixes"). The same
probe re-run on **landed `main` `c08c58c`, clean tree** (`router-contract-main-c08c58c.json`):

| contract | pre-fix | landed main |
|---|---|---|
| BM25 fixed-point units, tf 1/10/100 vs reference | scores 4 / 49 / 499; abs. error 0.83–0.99 | error ≤ 6.5e-7 · **passes** |
| dense cosine ordering | counterexample inverted | 1 000 non-tied pairs, **0 violations** |
| dependency eligibility via `route()` | — | negative-trigger and out-of-scope deps **not re-introduced** |
| `w_dense = 0` contributes nothing | channel voted | **no contribution** |

**Closed (PR after #22):** `admissible` is now a **keyword-only, mandatory** parameter of
`select()`; the legacy deprecated-only fallback is gone. The reviewer's probe records the direct
call as rejected by signature. Both evaluation tools (`run_golden.py`, `sweep.py`) now pass the
product's admissible set, so injection metrics are measured exactly as the product injects. That
moved `all_required@4` on multi_skill from 0.6061 to **0.5758** (overall 0.8276 → 0.8161): the
benchmark had been crediting closure dependencies the product rejects. Baseline regenerated.

`papers-manifest-2026-09-05.json` inventories the local paper cache with SHA-256 per file and
verifies SkillRouter v5 / SkillRet v3 as the versions cited; it records that the SIF and RRF local
copies are not the publications (a JS challenge page and a 279-byte error page respectively).
