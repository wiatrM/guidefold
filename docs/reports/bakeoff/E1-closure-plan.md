# E0 + E1 closure plan — what the peer review changes, and the system we ship

**Status:** Accepted by the TL · 2026-09-05
**Responds to:** [`E1.3-peer-review-2026-09-05.md`](E1.3-peer-review-2026-09-05.md)
**Inputs:** the review's two audit scripts and data, PR #19 (config sweep with a held-out split),
five papers analysed in [`docs/RESEARCH.md`](../../RESEARCH.md)

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
mode. Both survive on cost and on fairly-filtered quality. What changed is *why*, and how honestly
the numbers are labelled.

---

## 2. What the five papers say, condensed to decisions

| paper | its evidence | our measurement | decision |
|---|---|---|---|
| SkillRet | BM25 51.69 vs off-the-shelf 0.6B 61.94 vs **tuned 0.6B 81.12** NDCG@10 | BM25 0.8736 hit@1; best untuned teacher 0.8678 | dense stays off; **fine-tuning is the only credible path back**, and it is gated on an execution-level win (§3, P2) |
| SkillRet | +30 NDCG → **+0.3 % Terminal-Bench success** | — | ranking metrics are a proxy; §3 adds an execution eval before any model change |
| SkillRouter | body access 37–44 pp; FC@10 only 35 % even for the winner | body weight 1 optimal; removing it −9.2 pp; **all_required@4 = 74 %** on multi_skill | keep weights; **completeness is the product gap**, not hit@1 |
| GoS | graph propagation +5.1 reward at 1 000 skills; bundle > top-1 | PPR ≡ closure at 26 skills, byte-identical | ship closure; re-test PPR at pilot scale (§3, P2) |
| SkillResolve | HSR@K — harmful sibling exposure | B6 exposed deprecated at #1 in 10/22 | **adopt HSR@K** on (helpful, risky) pairs; deprecated/postgres-auth is pair #1 |

---

## 3. The experiments that close E0 + E1 — in order, with stop conditions

Everything below is **measurement infrastructure first, models last.** The review's central point
is that we tuned against a ruler with three defects; nothing measured against it should be re-run
until the ruler is fixed.

### P0 — fix the ruler *(this PR + one follow-up, ~1 day)*

| work | done when |
|---|---|
| `all_required@4` alongside `completeness@4`; both series in every table, never rewritten | ✅ this PR |
| `_dense_rank` is true cosine; counterexample is a test | ✅ this PR |
| retire the Recall@8 gate; **new gate written before the next run**: `all_required@4` non-inferior and HSR@4 non-worsening on filtered candidates, at the real 4-card budget | ADR-0020 amended, this PR |
| explicit denominators in every report (174 answerable, 46 should-abstain, 133 with distractors, **1** multi_skill with a distractor) | this PR, report headers |
| runner records **per-query** rankings, scores, filtered/unfiltered candidates, drop reasons, and the input hashes — so paired bootstrap is possible next time | follow-up PR |

### P0 — benchmark = product *(follow-up, ~1 day)*

| work | done when |
|---|---|
| every arm runs `policy_filter → candidates → score → select` from the shipped `Router`, at the shipped 4-card cap, from the case's `cwd` | B1 reproduces the CLI's ranking 220/220 |
| one BM25 definition: the arms' pseudo-document BM25 is replaced by the CLI's per-field-normalised BM25F | identical scores, not just identical order |
| dense artifact round-trip test: build → serialise → load → rank, offline and in CLI, same result | passes on the fixture with a synthetic word table |

### P1 — fair ablations on the fixed ruler *(~2 days)*

Run **once**, all arms, on filtered candidates, reporting `hit@1 · nDCG@10 · all_required@4 · HSR@4 ·
warm p50/p95`: sparse · sparse + closure · sparse + PPR · sparse + static student · sparse + tuned
teacher (SKILLRET) · each + reranker (filtered, full body ≤ 4 096 tokens). One change per arm.
Expect: sparse + closure wins on `all_required@4`; reranker still fails on p95. Say so if not.

### P1 — golden set repair *(~1 day)*

- Distractors by SkillRouter's four-source recipe (semantic neighbour, BM25 lexical, same-taxonomy,
  random) so `distractor_rate@4` is never computed over one case again.
- HSR pairs: every `stale_adversarial` case gets an explicit (helpful, risky-sibling) label.
- Mark cases whose full required bundle **cannot fit in 4 cards** rather than penalising the ranker
  for an impossible target (review §6).
- The current 220 stays as the **dev/regression** set. It is not evidence of generalisation.

### P2 — the pilot test set *(blocks any model decision)*

Real tasks from 2–3 teams on the pilot corpus (200–500 skills). Frozen before use, split by
task-family, labels reviewed independently, candidates from *different methods* judged blind so the
set does not favour lexical matching. **Paired bootstrap on task families, not on paraphrases.**
Minimum detectable difference agreed before sizing.

### P2 — execution-level evaluation *(the metric the MVP actually promises)*

No Guidefold · sparse + closure · best bundle · oracle bundle, on paired tasks: **task success,
policy violations, tokens, wall-clock.** SkillRet's 65.5 → 65.8 % is the warning: a retrieval win
that does not move this row is not a win. Owner acceptance of proposed knowledge (MVP §3) is
measured here too.

---

## 4. The system we ship — and why it is the best available choice

**Sparse BM25F over all fields + policy filter + `requires` closure + general→specific injection,
4 cards, integer-only, fresh process, 65 ms.** Dense off. Reranker in shadow. PPR replaced by the
byte-identical closure.

This is not a fallback. It is the choice every piece of evidence in this document points at:

1. **It is the strongest thing we have measured on the product's own metric.** `all_required@4` —
   the whole bundle, not the headline — is where sparse + closure leads, and it is the metric
   GoS and SkillRouter both say predicts task success better than hit@1.
2. **It is the only configuration that is exact.** Integer ranking, no model at query time,
   identical output under any `PYTHONHASHSEED`. GoS's 25 % reward gain was measured with none of
   that discipline; ours has to hold on a developer laptop with no GPU.
3. **It is within 0.6 pp of the best untuned teacher on hit@1** (0.8736 vs 0.8678) at zero model
   cost, and SkillRet's table says untuned encoders are not the ceiling — tuned ones are, and
   tuning is a P2 experiment gated on an execution win, not a default.
4. **Its two known weaknesses are measured and owned**, not hidden: `all_required@4` on
   multi_skill is 74 %, and it never abstains. Both are on the P0/P1 list above, and neither is
   fixed by a bigger model — one is a selection-budget problem, the other a missing component.

What would change this recommendation: a tuned SKILLRET-class encoder, fine-tuned on pilot skills
with four-source hard negatives, that beats sparse + closure on `all_required@4` **and** HSR@4 on the
frozen pilot set, **and** moves the execution row — inside the artifact budget from ADR-0021.
That is a real experiment with a real chance of winning. It is P2 because it needs the ruler and
the pilot set first, and because SkillRet's own downstream result says to expect a small
execution gain even from a large retrieval one.

---

## 5. What this closes in E0 + E1

| item | state after this plan |
|---|---|
| E0.1–E0.5 | closed; unaffected by the review |
| E1.1, E1.7 | closed; unaffected |
| E1.2 golden set + metrics | **reopened** for P0 (metric versioning, denominators) and P1 (distractors, HSR pairs); the 220 cases stand as dev/regression |
| E1.3 bake-off | conclusion (`w_dense = 0`) stands; **report re-labelled**: unreachable gate retired, denominators stated, arms marked as unfiltered-corpus, SkillRet table complete |
| E1.4, E1.5 | closed; cosine fix is a latent-bug repair on a disabled path, measured artifact and latency unchanged |
| E1.6 | conclusion (shadow) stands **on cost**; quality re-attributed from domain shift to the deprecated leak |

Nothing in E0 + E1 ships differently tomorrow. What ships differently is the *claim*: from
"BM25 beat dense" to "on a 26-skill dev fixture, with a ruler we have since fixed, BM25 + closure
is the best-measured configuration, and the path back to dense is a tuned encoder judged on bundle
completeness and task success at pilot scale." That sentence is the one the review asked for, and
it is the true one.

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

**Still open, from the same audit:** `select()` called *directly* without `admissible` keeps the
legacy deprecated-only check and will still admit a rejected dependency. The product paths
(`route`, `find`, `hook`) all pass the admissible set; the direct call is used only by tests. Under
ADR-0022 §1 the parameter should become mandatory — follow-up, with the affected tests updated.

`papers-manifest-2026-09-05.json` inventories the local paper cache with SHA-256 per file and
verifies SkillRouter v5 / SkillRet v3 as the versions cited; it records that the SIF and RRF local
copies are not the publications (a JS challenge page and a 279-byte error page respectively).
