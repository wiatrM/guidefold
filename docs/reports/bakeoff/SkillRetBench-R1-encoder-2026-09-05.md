# SkillRetBench (test-B): the full SKILLRET-Embedding-0.6B encoder reference run

**Status: REFERENCE RUN (DENSE-PROGRAM.md v2.1 §6). Tooling defaults, `w_dense=1`, no tuning of
anything on this corpus. Gates nothing — every "PASS/fail" column below answers "would this
reference run have cleared the rule", never "is dense adopted". Adoption is decided only for the
eventual dev-tuned frozen variant, run once per family on both test corpora together.**

Code: `tools/eval/skillretbench_r1.py` (thin runner) + `tools/eval/dense_ref.py` (encoder-backed
`DenseCandidateRouter`, quantisation, and on-disk cache — shared verbatim with
`tools/eval/skillret.py`'s own R1 runner for test-A; see "Code reuse" below). Reused, never
reimplemented, from `tools/eval/skillretbench.py`: `corpus_to_cards`, `queries_to_cases`,
`build_arms` (for F0 only), `run_arm`, `ir_alignment_metrics`, `_bootstrap_paired_delta`,
`dense_coverage_report`, `dense_vs_b1_gate_report`, `format_*`. Raw per-query evidence and the
summary JSON: `docs/reports/bakeoff/validation/skillretbench-r1-encoder.jsonl.gz` /
`skillretbench-r1-encoder-summary.json`.

## Why this run exists

Two variables differ between the flattering test-A dense result (PR #33: full encoder, a
same-distribution corpus, `all_required@4` root +17.96pp [16.80,19.08], `hit@1` root +21.79pp
[20.56,23.11]) and the unflattering test-B result already on record (PR #30: coverage 7.64%,
every quality gate fails). PR #30's dense arm on test-B was the **distilled static word-table
student** (`B3b+B5`), not the full encoder — so that comparison could not tell you whether test-B's
poor result was (a) the encoder generalising badly to an independently-authored, out-of-distribution
corpus, or (b) the *distillation* itself throwing away most of the signal. This run holds the
corpus fixed at test-B and swaps only the dense arm back to the full encoder, isolating (a) from
(b) for the first time. It is the missing cell in DENSE-PROGRAM.md's 2×2 (test-A/test-B ×
full-encoder/distilled-student).

## Setup

- Model `ThakiCloud/SKILLRET-Embedding-0.6B` @ `0e10886e80a0aacc9efddc28282a258e2ab7eae1`, fp16,
  GPU venv, `HF_HUB_OFFLINE=1`. Skill text = raw `description` + `full_text` (frontmatter **not**
  stripped — unlike the cards' own `_body`, which strips it for BM25F; the encoder sees the whole
  document, capped by the tokenizer's own 8192-token window, applied automatically).
  `skill_batch_size=4` (test-A, PR #33, hit CUDA OOM on long bodies at the default 64); queries at
  the default batch size. 501 skills, 1,250 surviving queries (none dropped — SkillRetBench has no
  empty-gold queries on this corpus revision), 1,099 Latin-only.
- Quantisation (float32 → int8, scale 127): mean cosine after dequantisation 0.9974 (skills) /
  0.9974 (queries), min 0.9972 / 0.9971 — same quality band as test-A's own cache.
- Encode wall-clock: 30.5s for 501 skills, 4.6s for 1,250 queries, on an otherwise-idle GPU
  (24 GB total, 1.5 GB used beforehand).
- Product path, unmodified: `policy_filter → candidates → score → select(admissible=…)`,
  `K_CARDS=4`. **Retrieval order** (`Router.score`, truncated to `EVAL_K=10`) for
  hit@1/nDCG@10/recall@8; **injection order** (`Router.select`, ≤4 cards) for
  `all_required@4`/`distractor_rate@4` — these are never conflated (commit `931055d` fixed a real
  bug from doing so). Both `node_scoped` (gold's own category as caller node — what PR #30 already
  measured for the dense arm) and `node_root` (`_root`, the full 501-skill visible universe — the
  scope the dataset's own BM25/Dense/Hybrid baselines actually search, and the fair one) are run
  for **both** F0 and R1-encoder here; PR #30 only ever ran the dense arm at `node_scoped` and F0 at
  both — the `node_root` dense numbers below did not exist anywhere before this run.
- `w_dense_f0=0`, `w_dense_r1=1`; every other weight at its shipped `DEFAULT_WEIGHTS` value in
  both arms (Index construction differs from F0 only in `w_dense` and in which vectors back the
  dense channel — see "Code reuse" below for how this is enforced/tested).

## Per-setting quality (product-path metrics)

F0 = shipped sparse (`w_dense=0`). R1-static = the **distilled word-table student** from PR #30
(quoted verbatim, `node_scoped` only — it was never run at `node_root`). R1-encoder = this run,
the full encoder.

### `node_scoped` — ALL queries

```
                              hit@1  nDCG@10 recall@8 all_required@4 distractor_rate@4
F0            OVERALL n=1250 0.7025  0.7296   0.7153          0.5658            0.7433
R1-static     OVERALL n=1250 0.5842  0.6527   0.6686          0.5042            0.7500   (quoted, PR #30)
R1-encoder    OVERALL n=1250 0.7544  0.7736   0.7582          0.5792            0.7367   (this run)
```

Per setting (this run only; F0/R1-static per-setting figures are in the PR #30 report):

```
setting                                  n             hit@1           ndcg@10          recall@8    all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------------------------------------------
single_skill                           400            0.7450            0.8492            0.9475            0.8400                 —
multi_skill_composition                200            0.8600            0.6878            0.5324            0.1500                 —
distractor                             300            0.5800            0.7630            0.9367            0.7167            0.7367
outdated_redundant                     150            0.8867            0.9521            1.0000            0.9533                 —
budget_constrained                     200            0.8300            0.5901            0.1562            0.0000                 —
OVERALL                               1250            0.7544            0.7736            0.7582            0.5792            0.7367
```

The full encoder clears F0 on every column, OVERALL and on 4/5 settings (`budget_constrained`'s
`all_required@4=0` is structurally guaranteed — every case there has 25 required skills against a
4-card budget; see PR #30's report). It also clears the distilled student (R1-static) by a wide
margin on hit@1/nDCG@10/recall@8 — the student's PR #30 failure was not simply "dense doesn't work
on test-B".

### `node_root` — ALL queries (the fair setting; new, PR #30 never ran the dense arm here)

```
                              hit@1  nDCG@10 recall@8 all_required@4 distractor_rate@4
F0            OVERALL n=1250 0.3800  0.4635   0.5158          0.3750            0.3967
R1-encoder    OVERALL n=1250 0.4488  0.5255   0.5887          0.3712            0.2967
```

```
setting                                  n             hit@1           ndcg@10          recall@8    all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------------------------------------------
single_skill                           400            0.4850            0.6142            0.7375            0.5625                 —
multi_skill_composition                200            0.6350            0.6330            0.6657            0.3200                 —
distractor                             300            0.1400            0.3188            0.4900            0.1733            0.2967
outdated_redundant                     150            0.7200            0.8734            0.9867            0.8200                 —
budget_constrained                     200            0.4500            0.2894            0.0638            0.0000                 —
OVERALL                               1250            0.4488            0.5255            0.5887            0.3712            0.2967
```

R1-static has no `node_root` figure to compare against (PR #30 gap). At `node_root`, R1-encoder
clearly beats F0 on hit@1/nDCG@10/recall@8 OVERALL and on every setting except `distractor` (where
it *trails* F0 by 7.3pp hit@1 — the one setting where the full encoder's recall of the *labelled
distractor itself* apparently outcompetes recall of the true gold more than F0's sparse signal
does; see the gate table below, which shows this is also where `all_required@4` regresses most).
`all_required@4` OVERALL is flat to slightly down (−0.4pp naive), and distractor exposure
(`distractor_rate@4`/HSR@4) drops materially (−10pp) — a genuinely different profile of gains than
`node_scoped` shows.

## IR-aligned comparison against the dataset's own BM25 (`node_root`, the fair scope)

Simple mean over the five settings (unweighted — same convention `baseline_results.json`'s own
`summary_table` and PR #30's fairness-caveat table use):

```
                     R@1     R@3     R@5     R@10    nDCG@10  MRR     MAP
Dataset's own BM25   0.3803  0.4917  0.5419  0.5979  0.5344   0.5726  0.4777
Guidefold F0 @ root  0.2798  0.4018  0.4572  0.5302  0.4549   0.4924  0.3783   (matches PR #30 exactly)
Guidefold R1 @ root  0.3154  0.4749  0.5318  0.6098  0.5300   0.5899  0.4388   (this run)
```

F0 trailed the dataset's real BM25 on every column (PR #30's own finding, reproduced
byte-for-byte here as a consistency check). The full encoder closes most of that gap: it now
*beats* the dataset's BM25 on recall@10 (0.6098 vs 0.5979) and MRR (0.5899 vs 0.5726), and is
within 1–2pp on recall@3/recall@5/nDCG@10, only clearly trailing on recall@1 (0.3154 vs 0.3803) and
MAP (0.4388 vs 0.4777). This is a materially better-calibrated comparison against an external BM25
implementation than F0 alone gives — the shipped sparse ranker's `node_root` shortfall (PR #30,
still unexplained — tokenization/field-weighting/IDF variant) is partially, not fully, masked by
adding the dense channel.

## Coverage — gold skills BM25F's top-50 misses that the encoder's candidates recover

Rank-bounded exactly as `dense_coverage_report` computes it (`dense_rank <= bm25_cutoff`, never
`is not None` — the bug PR #33 fixed):

```
node_scoped:
setting                   missed_by_bm25   recovered    coverage
----------------------------------------------------------------
single_skill                          50          36      0.7200
multi_skill_composition              299           0      0.0000
distractor                             0           0           —
outdated_redundant                     0           0           —
budget_constrained                  3174         369      0.1163
OVERALL                             3523         405      0.1150

node_root:
setting                   missed_by_bm25   recovered    coverage
----------------------------------------------------------------
single_skill                         102          10      0.0980
multi_skill_composition               89           5      0.0562
distractor                           123          10      0.0813
outdated_redundant                     1           0      0.0000
budget_constrained                  3955         349      0.0882
OVERALL                             4270         374      0.0876
```

`node_scoped` OVERALL coverage is **11.50%** — noticeably higher than the distilled student's
7.64% on the same setting (PR #30), but far below test-A's encoder coverage of **39.6%** (root).
`node_root` OVERALL coverage is **8.76%**, in the same low band. Per DENSE-PROGRAM.md §6, this is
"the most useful number [R1] produces" here: even the full, un-distilled encoder has a low ceiling
on how much it could add to candidates on this corpus — the distillation loss (PR #30) explains
only part of the gap to test-A's 39.6%; the rest is a property of the corpus/encoder pairing
itself (see "Cross-corpus reading" below).

## Gates, as observed (three-state: PASS / fail / n/a — n/a is "undetermined", never "fail")

**Reference run — gates nothing.** Table format and gate rules exactly as
`dense_vs_b1_gate_report`/`format_gate_table` already print for test-B's PR #30 dense arm; shown
here only so a reader can see, evidence-only, how this reference run would have scored against the
same rules DENSE-PROGRAM.md §5 fixes for an eventual frozen variant.

```
node_scoped:
setting                   all_req D          [95% CI]  gate   hit@1 D  gate  ndcg@10 D  gate   HSR@4 D  gate
------------------------------------------------------------------------------------------------------------
single_skill                +0.0343 [+0.0000,+0.0686]  fail   +0.0771  PASS    +0.1069  PASS         —   n/a
multi_skill_composition     -0.0050 [-0.0150,+0.0000]  fail   +0.0400  PASS    +0.0147  PASS         —   n/a
distractor                  +0.0300 [-0.0033,+0.0633]  fail   +0.0467  PASS    +0.0658  PASS   -0.0067  PASS
outdated_redundant          +0.0133 [-0.0267,+0.0533]  fail   +0.1000  PASS    +0.0584  PASS         —   n/a
budget_constrained          +0.0000 [+0.0000,+0.0000]  fail   +0.1000  PASS    +0.0861  PASS         —   n/a
OVERALL                     +0.0183 [+0.0058,+0.0317]  fail   +0.0700  PASS    +0.0732  PASS   -0.0067  PASS

node_root:
setting                   all_req D          [95% CI]  gate   hit@1 D  gate  ndcg@10 D  gate   HSR@4 D  gate
------------------------------------------------------------------------------------------------------------
single_skill                +0.0971 [+0.0486,+0.1514]  PASS   +0.1143  PASS    +0.1265  PASS         —   n/a
multi_skill_composition     -0.0350 [-0.0850,+0.0150]  fail   +0.0700  PASS    +0.0474  PASS         —   n/a
distractor                  -0.1100 [-0.1500,-0.0667]  fail   -0.0733  fail    +0.0064  PASS   -0.1000  PASS
outdated_redundant          +0.0933 [+0.0067,+0.1800]  fail   +0.1067  PASS    +0.1025  PASS         —   n/a
budget_constrained          +0.0000 [+0.0000,+0.0000]  fail   +0.2600  PASS    +0.1165  PASS         —   n/a
OVERALL                     +0.0067 [-0.0150,+0.0283]  fail   +0.0833  PASS    +0.0805  PASS   -0.1000  PASS
```

`all_required@4` clears the +2.0pp/CI-excludes-0 bar on exactly one setting/scope cell
(`single_skill`@`node_root`, +9.71pp); OVERALL clears the +2.0pp bar at `node_scoped` on the point
estimate but the CI's own lower bound (+0.58pp) sits below it, so it's marked `fail` under the
strict rule (CI must exclude 0 **and clear +2.0pp**); at `node_root` OVERALL is flat (+0.67pp,
CI includes 0). `hit@1`/`nDCG@10` PASS (improve or are flat) everywhere except `distractor`@
`node_root`, where hit@1 regresses by 7.33pp — outside the 1.0pp tolerance, the one primary-quality
failure in this entire run. HSR@4 PASSes wherever determined (harmful exposure *drops*, never
rises).

## HSR@4 / `distractor_rate@4` — full paired-bootstrap 95% CI (new: not just a point delta)

`dense_vs_b1_gate_report`'s own HSR@4 row is a **point-estimate delta only** (see its docstring);
DENSE-PROGRAM.md v2.1 §5's gate rule for harmful exposure is stated as a CI-worthy claim, and
SkillRetBench is the one corpus with real distractor labels (test-A has none, so this gate could
never even be attempted there — see PR #33). `tools/eval/skillretbench_r1.py::hsr_bootstrap_report`
adds that CI here, reusing `skillretbench._bootstrap_paired_delta` (never a second bootstrap
implementation) over the same per-setting population `dense_vs_b1_gate_report` itself uses for
HSR@4/nDCG@10, after dropping cases where distractor_rate is itself undetermined (NaN — no labelled
distractor in that case) for either arm — `_bootstrap_paired_delta` has no NaN handling of its own.
Only `distractor` has any labelled cases; the other four settings are `n=0` (undetermined) by
construction, not a bug:

```
node_scoped:
setting                      delta            [95% CI]       n
--------------------------------------------------------------
distractor                 -0.0067   [-0.0333,+0.0200]     300
OVERALL                    -0.0067   [-0.0333,+0.0200]     300   (CI includes 0 -- not significant)

node_root:
setting                      delta            [95% CI]       n
--------------------------------------------------------------
distractor                 -0.1000   [-0.1567,-0.0400]     300
OVERALL                    -0.1000   [-0.1567,-0.0400]     300   (CI excludes 0 -- a real, significant
                                                                   REDUCTION in harmful distractor
                                                                   exposure at the fair scope)
```

At `node_root`, the full encoder's reduction in distractor exposure is not just within the 1.0pp
tolerance (as the point-estimate-only gate table already showed) — it is a statistically
significant *improvement* over F0, the strongest unambiguously-positive finding in this run. At
`node_scoped` the same delta is smaller and not significant (CI straddles 0).

## Latin-only queries (1,099 / 1,250 — Korean queries excluded)

Derived by filtering the ALL-queries run's already-computed per-query (retrieval, injection) pairs
by `case["id"] not in <hangul ids>`, rather than a second `run_arm` call — every stage of the
product path is computed per query with no cross-query state, so the two are mathematically
identical; this halves the number of `run_arm` calls this script needs (2 per node setting instead
of 4), a deliberate efficiency choice over `skillretbench.py`'s own `cmd_run`, which re-runs
instead.

```
                          hit@1  nDCG@10 recall@8 all_required@4 distractor_rate@4
node_scoped, F0          0.7225  0.7425   0.7198          0.5623            0.7356
node_scoped, R1-encoder  0.7871  0.7916   0.7565          0.5769            0.7280
node_root,   F0          0.4067  0.4944   0.5502          0.4013            0.4406
node_root,   R1-encoder  0.4886  0.5703   0.6321          0.4022            0.3180
```

Latin-only numbers are uniformly a few points higher for both arms at both scopes (consistent with
PR #30's own observation that all 50 F0 abstentions in that run were Korean `single_skill`
queries) — the encoder does not close, or widen, the Korean/Latin gap in any qualitatively
different way than F0 already shows.

## Cross-corpus reading: test-A encoder gain vs test-B encoder gain

|  | test-A (SKILLRET-test), root | test-B (SkillRetBench), root |
|---|---|---|
| corpus relationship to encoder's training data | same construction/distribution as the encoder's SkillRet fine-tuning data (the "flattered corpus", named as such in advance) | independently authored; only 6/501 skill names (1.2%) overlap by exact string match, 0 id overlap (see caveat below) |
| `hit@1` Δ vs F0 (bootstrap, 95% CI) | **+21.79pp** [+20.56,+23.11] | **+8.33pp** [+5.75,+11.25] |
| `all_required@4`/bundle-completeness Δ vs F0 (bootstrap, 95% CI) | **+17.96pp** [+16.80,+19.08] | **+0.67pp** [−1.50,+2.83] (not significant) |
| `nDCG@10` Δ vs F0 | +23.25pp (0.3999→0.6324, paper-style) | **+8.05pp** (0.4449→0.5255) |
| dense-candidate coverage of BM25's top-50 misses | **39.6%** | **8.76%** |
| distractor labels available? | no (`distractor_rate@4`=NaN throughout) | yes — HSR@4 CI: **−10.00pp** [−15.67,−4.00], a significant *reduction* in harmful exposure |

The headline gain shrinks by roughly 2.6× on `hit@1` (21.79pp → 8.33pp) and, more strikingly,
collapses almost entirely on the completeness gate (17.96pp, clearly significant, → 0.67pp, not
even significant — CI straddles zero) moving from test-A to test-B. Candidate-coverage tells the
same story at a different layer: the encoder finds only 8.76% of test-B's BM25-missed golds inside
its own candidate pool, against 39.6% on test-A — nearly 4.5× lower. This is the *full, un-distilled*
encoder in both cases, so the collapse is not a distillation artifact (contrast the distilled
student's 7.64% node_scoped coverage from PR #30, which is close to this run's own 8.76%/11.5% —
the student's headline failure was mostly *already baked in* by the corpus/encoder mismatch, and
distillation only compounded a problem that was already large, rather than being the primary cause
of it). Put plainly: **this run separates two previously-conflated effects — "the encoder
generalises to an unrelated corpus" (yes, modestly: hit@1/nDCG@10/HSR@4 all improve, `all_required@4`
does not clearly help or hurt) from "distillation destroys the signal" (yes, separately and badly:
PR #30's static student failed every quality gate even at the one scope where this full-encoder
run passes several)**. Both effects are real; the full-encoder cross-corpus generalisation gap
(test-A → test-B) is by far the larger of the two, and it is a property of the corpus/encoder
pairing (training-distribution overlap, or lack of it) that dev-time tuning on a third corpus
(SKILLRET-train, per DENSE-PROGRAM.md §3) cannot be assumed to fix.

## Overlap caveat (quoted from PR #30, `tools/eval/skillretbench.py overlap`)

> `SKILLRET-Embedding-0.6B` (the encoder behind this run and PR #30's B3b+B5) was fine-tuned on
> **SkillRet**, a different, larger, public-GitHub-scrape dataset from the same organisation — not
> on SkillRetBench itself.
>
> ```
> skillret_skills: 6,006   skillretbench_skills: 501
> id_overlap_count: 0        (different id namespaces entirely: UUIDs vs slugs — not informative alone)
> name_overlap_count: 6
>   "requesting code review"        "skill creator"              "testing strategy"
>   "user research"                 "using git worktrees"        "verification before completion"
> ```
>
> Six SkillRetBench skill names have an exact-match (case-folded) counterpart in SkillRet's 6,006.
> ... Given it's 6 of 501 skills (1.2%) and name-based only (no id overlap), the leakage risk is
> judged small, but is disclosed rather than assumed away.

This run's use of the same encoder is subject to the identical caveat; the near-total collapse of
the completeness gain reported above (§"Cross-corpus reading") argues against material leakage
inflating this run's numbers — a leaking encoder would be expected to look *better*, not worse, on
test-B.

## Latency

Reported as GPU wall-clock only, per DENSE-PROGRAM.md §6 — **not a gate for a reference run, and
not representative of servable in-hook latency** (this run never goes through the CLI's own
subprocess/artifact-load path; that measurement is R4's, tracked separately and already reported
for F0 alone in PR #30: p50 126.6 / p95 145.3ms at 501 skills after the `policy_filter`
retokenisation fix).

- Encode (offline, one-time per corpus revision): 30.5s / 501 skills (60.9 ms/skill,
  `skill_batch_size=4`), 4.6s / 1,250 queries (3.7 ms/query, default batch size). GPU: fp16, 24GB
  total, idle otherwise.
- `run` (both node settings, both arms, ALL + Latin-only derived views, full paired bootstrap CIs
  at 1,000 resamples each): 33.7s wall-clock total, in-process, no GPU (dense scores are int8
  dot-products against the cached matrices — no model forward pass at query time in this
  evaluation harness).

## Code reuse

Per DENSE-PROGRAM.md v2.1 §6's instruction not to duplicate the encoder-backed dense Router
between test-A and test-B: `tools/eval/skillret.py`'s original `DenseCandidateRouter`,
`make_dense_router_class`, `build_r1_index_and_router`, `quantize`, `quant_cosine`,
`encode_chunked`, and the on-disk dense-cache read/write were factored out, unmodified in
behaviour, into the new corpus-agnostic `tools/eval/dense_ref.py` in this same change.
`tools/eval/skillret.py` now delegates to it (`skillret.build_r1_index_and_router` is a thin
wrapper around `dense_ref.build_dense_index_and_router`; `tests/test_skillret_eval.py`'s existing
9 tests pass unchanged, confirming the refactor is behaviour-preserving). `skillretbench_r1.py`
(this run) is the *second* caller, using `dense_ref.py` directly rather than reimplementing any of
it. `tools/eval/skillretbench.py::run_case` gained one additive, backward-compatible line
(`if hasattr(router, "_current_qid"): router._current_qid = case["id"]`) so its existing
`run_case`/`run_arm` sequential drivers work unmodified for an encoder-backed Router too — a no-op
for the four existing word-table arms (`B1`/`B1-scope`/`B1-closure`/`B3b+B5`), none of which carry
a `_current_qid` attribute.

A separate `tools/eval/skillretbench_r1.py` script (rather than a fifth arm inside
`skillretbench.py`'s `build_arms()`) was chosen because the encoder-backed Router is a structurally
different subclass (keyed by precomputed per-document/per-query embeddings selected by query id),
not a `weights`-only variant of the same Router `build_arms()` already builds — see that script's
own module docstring for the full rationale.

## Tests

`tests/test_skillretbench_r1.py` (8 new tests, all pure-logic except one corpus-presence check
that ran for real on this machine, not skipped): the torch-import boundary
(module-scope code in `skillretbench_r1.py`, and transitively `dense_ref.py`/`skillretbench.py`,
never imports torch), `_filter_by_ids`, the retrieval-vs-injection metric assembly
(`_per_setting_metrics`/`_per_setting_ir`), and — the key new coverage — `hsr_bootstrap_report`
against a hand-computed 4-case fixture (delta, CI containment, NaN-pair exclusion, and the
all-undetermined degrade-gracefully path). The encoder-backed Router itself
(`DenseCandidateRouter`/`build_dense_index_and_router`, including the R0-vs-R1-Index-differs-only-
in-`w_dense`-and-vectors contract and the missing-embedding `SystemExit`) is already covered by
`tests/test_skillret_eval.py` via `skillret.py`'s thin wrappers around the same `dense_ref.py`
functions this script calls directly — not duplicated here. Full suite: `pytest -q`, 372 passed, 0
skipped (both pinned corpora verified present on this machine).
