# Frozen sparse variant, once on both tests: flat BM25F field weights — 2026-09-05

**Decision: NOT ADOPTED.** `Index.DEFAULT_WEIGHTS` is unchanged; nothing in
`skills/guidefold/scripts/guidefold` is touched by this report. Test-A passes every acceptance
criterion cleanly. Test-B passes three of four at the fair `_root` setting but **fails the
harmful-exposure guardrail**: `distractor_rate@4` (HSR@4) is **4.67 pp worse**, more than four
times the ±1.0 pp tolerance, isolated entirely to the adversarial `distractor` query category
(n=300). Per the pre-registered rule, adoption requires all four criteria to hold on **both**
corpora at `_root` — one miss on either corpus is a no. This report is that one, single,
frozen-config run on each of test-A and test-B; per DENSE-PROGRAM.md v2.1 §3's "touched once"
rule, flat `field.*` weights may not be evaluated against either test corpus again.

## Candidate under test

One arm, no tuning: `field.name`/`field.description`/`field.digest`/`field.triggers`/`field.body`
all set to `1` (uniform), every other weight (`w_scope`, `w_ppr`, `abstain_threshold`, `ppr_mode`,
`edge.*`, `k1`/`b`, ...) left at its shipped default. Selected by `docs/reports/bakeoff/
DEV-sparse-diagnosis-2026-09-05.md` (PR #36): on SKILLRET-train dev only, this recovers 99.5% of
the shipped-vs-plain-BM25 gap (+3.72 pp nDCG@10 [+3.16, +4.34] vs the shipped weights). That
report explicitly left test-A/test-B validation "out of scope" — this report is that validation.

Both runners already build the product `Index`/`Router` for every arm (no metric
reimplementation); this run only added a `weights_arm="flat"` override:
- test-A: `tools/eval/skillret.py` — `FLAT_FIELD_WEIGHTS`, `build_r0_index(..., weights_arm=)`,
  `cmd_r0 --weights-arm flat`.
- test-B: `tools/eval/skillretbench.py` — a fifth arm, `B1-flat`, alongside `B1`/`B1-scope`/
  `B1-closure`/`B3b+B5`.

Per-query JSONL (gzip, committed): `docs/reports/bakeoff/validation/skillret-r0-flat-{root,major}.
jsonl.gz` (test-A) and `docs/reports/bakeoff/validation/skillretbench-rankings-flat.jsonl.gz`
(test-B). Aggregate JSON: `skillret-r0-flat-summary.json`, `skillretbench-metrics-flat.json`.
The shipped baseline (`skillret-r0-summary.json` + its two `.jsonl.gz`) was regenerated once,
deterministically, to add `ndcg@10`/`recall@10` to its per-query records (needed so this run's
paired bootstrap has something to pair against) — this is not a second touch of the flat
candidate, only a re-emission of the unchanged shipped arm's own predictions.

## Test-A (SKILLRET-test, 6,006 skills / 4,392 queries), `_root` fair setting

Retrieval-order metrics (`hit@1`, `ndcg@10`, `recall@10`); injection-order metric
(`all_required@4`). Paired bootstrap, 1,000 resamples, 95% CI, vs shipped F0.

| metric | shipped | flat | Δ | 95% CI |
|---|---|---|---|---|
| hit@1 | 0.3825 | 0.4597 | **+7.72 pp** | [+6.94, +8.58] |
| nDCG@10 | 0.3850 | 0.4494 | **+6.44 pp** | [+6.04, +6.85] |
| recall@10 | 0.4700 | 0.5391 | +6.91 pp | [+6.27, +7.60] |
| all_required@4 | 0.2700 | 0.3199 | +4.99 pp | [+4.37, +5.62] |

`distractor_rate@4`: not applicable to test-A (no distractor labels; `NaN` on both arms, as for
every arm this corpus has ever run — see DENSE-PROGRAM.md §7.1).

Per-k (`k1`/`k2`/`k3` = 1/2/3 required gold skills), all four metrics: every stratum's CI excludes
zero in the improving direction, weakest at `all_required@4`/k3 (+0.73 pp [+0.18, +1.47], n=546) —
still a genuine improvement, just a small one on the hardest stratum.

**`_major` (completeness only, not the decision setting):** hit@1 +6.56 pp [+5.83, +7.35], nDCG@10
+5.85 pp [+5.49, +6.27], recall@10 +5.62 pp [+4.99, +6.27], all_required@4 +4.23 pp
[+3.67, +4.83] — same direction and similar magnitude as `_root`; per-k also fully non-negative
(`all_required@4`/k3 = 0.0000 [0.0000, 0.0000] exactly — no queries changed outcome on that
stratum at `_major`).

**IR-aligned nDCG@10 vs the dataset's own reported BM25 (0.517):**

| setting | shipped | flat | dataset BM25 | gap closed |
|---|---|---|---|---|
| `_root` | 0.3999 | 0.4680 | 0.517 | **58.2%** (11.71 pp → 4.90 pp remaining) |
| `_major` | 0.3957 | 0.4530 | 0.517 | 47.3% (12.13 pp → 6.40 pp remaining) |

Test-A: **every criterion passes**, comfortably, at both settings.

## Test-B (SkillRetBench, 501 skills / 1,250 queries), `node_root` fair setting

Same shape: retrieval order for `hit@1`/`ndcg@10`; injection order for `all_required@4`,
`distractor_rate@4` (named `HSR@4` in this codebase, see `dense_vs_b1_gate_report`). Point deltas
+ CI where computed (HSR@4 has no bootstrap CI in the existing gate machinery — only a
point-estimate vs the pre-registered ≤1.0 pp tolerance, same threshold the orchestrator specified).

**OVERALL, `node_root` (n=1,200-1,250 depending on pairing filter):**

| metric | B1 (shipped) | B1-flat | Δ | 95% CI | vs ±1.0pp tolerance |
|---|---|---|---|---|---|
| hit@1 | 0.3800 | 0.4325 | **+5.25 pp** | [+3.75, +6.83] | improves — n/a |
| nDCG@10 | 0.4361 (IR-aligned OVERALL) | 0.4783 | **+4.31 pp** | [+3.70, +5.00] | improves — n/a |
| all_required@4 | 0.3750 | 0.4042 | +2.92 pp | [+1.67, +4.25] | improves — n/a |
| **distractor_rate@4 (HSR@4)** | 0.3967 | 0.4433 | **+4.67 pp (worse)** | point estimate only | **FAILS** (limit 1.0 pp) |

Per-category breakdown (injection order) shows the HSR@4 regression is isolated to the
`distractor` category (n=300) — the only category where `distractor_rate@4` is even defined:

| category (n) | hit@1 Δ | all_required@4 Δ | HSR@4 Δ |
|---|---|---|---|
| single_skill (400) | +6.29 pp | +5.14 pp | n/a |
| multi_skill_composition (200) | +4.00 pp | +0.50 pp (CI straddles 0) | n/a |
| **distractor (300)** | +3.00 pp | +1.67 pp (CI straddles 0) | **+4.67 pp worse** |
| outdated_redundant (150) | +8.67 pp | +7.33 pp | n/a |
| budget_constrained (200) | +5.50 pp | 0.00 pp | n/a |

Reading across the `distractor` row: flat weights rank *both* more correct required skills
**and** more labeled distractors into the top-4 at the same time on this category — a genuine
broadening of what gets retrieved, not a simple quality regression. That is still a real
harmful-exposure increase against the pre-registered ≤1.0 pp guardrail (which reads it in
isolation, not netted against the completeness gain), and this run treats the guardrail as
written, per the orchestrator's brief.

**`node_scoped` (completeness only, not the decision setting — this setting leaks the gold
category as cwd; kept only for comparison):** hit@1 +3.92 pp [+2.75, +5.33], nDCG@10 +2.24 pp
[+1.79, +2.71], all_required@4 +1.08 pp [+0.25, +1.92], **HSR@4 Δ = 0.0000** (unchanged — no
regression under this setting). The opposite-sign HSR@4 finding between settings is itself
informative: the distractor-exposure cost is specific to full-corpus (`_root`) retrieval, where
BM25F has to distinguish distractors from genuine matches across the whole index rather than
within a single pre-selected category.

**IR-aligned nDCG@10 vs the dataset's own reported BM25 (0.534), n-weighted OVERALL across all
1,250 queries and all 5 categories (same convention as DENSE-PROGRAM.md §7.1's F0-vs-test-B
entry, where shipped's 0.4361 here reproduces the previously reported 0.436 exactly):**

| setting | B1 (shipped) | B1-flat | dataset BM25 | gap closed |
|---|---|---|---|---|
| `node_root` (fair) | 0.4361 | 0.4783 | 0.534 | **43.1%** (9.79 pp → 5.57 pp remaining) |
| `node_scoped` (leaks answer, completeness only) | 0.6761 | 0.6972 | 0.534 | n/a — B1 already exceeds the dataset BM25 under this leaking setting |

## Reading the two corpora together

Both corpora show the *same qualitative pattern* the dev diagnosis predicted: flat weights
recover a large share (43–58%, root/fair settings) of the shipped-vs-BM25 gap, with every quality
metric (`hit@1`, `nDCG@10`, `recall@10`, `all_required@4`) improving with confidence intervals
excluding zero everywhere it was measured. This is markedly less than the 99.5% recovered on the
dev split — the frozen config transfers only partially from dev to held-out test, which is itself
a useful finding for future dev-tuning work (dev is not a perfect proxy for either test corpus).

The reason this is **not adopted**: acceptance was pre-registered as a **conjunction**, not a
weighted average — "not worse by more than 1.0 pp" on `distractor_rate@4` is a hard guardrail
against the sparse baseline swap making the retriever more likely to inject a labeled-harmful
distractor alongside genuine matches, independent of how much ranking quality improves elsewhere.
Test-B's `distractor` category breaches that guardrail by 4.67 pp, nearly 5x the tolerance. Test-A
offers no counter-evidence either way (it has no distractor labels), so it cannot rescue the
decision. One corpus failing one criterion is enough, by the pre-registered rule, to not adopt.

## What did not happen, because of this decision

Per the pre-registered "if NOT adopted" branch: `Index.DEFAULT_WEIGHTS` is unchanged; no golden
baseline regeneration; no R1-encoder reference rerun over a new base (there is no new base); no
ADR-0020 note; no DENSE-PROGRAM.md §7 entry. This report and its per-query JSONL are the complete
deliverable, plus one test per runner pinning that the `flat` weights arm differs from shipped in
exactly the five `field.*` keys (`tests/test_skillret_eval.py::
test_build_r0_index_flat_arm_differs_from_shipped_only_in_field_weights`,
`tests/test_skillretbench.py::test_arms_differ_by_exactly_one_parameter_from_b1`).

## Verification

`pytest -q` — full suite green (all tests pass, no failures) after adding the flat-arm coverage
above. `python3 -m py_compile` on all four touched eval files
(`tools/eval/skillret.py`, `tools/eval/skillretbench.py`, `tools/eval/skillretbench_r1.py`,
`tests/test_skillret_eval.py`) passes.
