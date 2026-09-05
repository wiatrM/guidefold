# SkillRetBench bake-off — 2026-09-05

**Corpus:** SkillRetBench (thaki-AI/SkillRetBench, Apache-2.0), pinned HuggingFace revision
`4bdbf59b` — 501 skills / 102 categories, 1,250 queries across five settings (`single_skill`,
`multi_skill_composition`, `distractor`, `outdated_redundant`, `budget_constrained`). Loaded
exclusively via `tools/eval/corpora.py`'s `load_skillretbench()` / `verify("skillretbench")` —
never raw JSON. Fetched once, never re-downloaded for this report.

**This is the first report written under `CLAUDE.md`'s "Evaluation corpora" rule** (added
2026-09-05): routing-quality claims must be measured on real, independently labelled corpora
run through the actual product path, not on the 26-skill Meridian dev fixture. Everything below
went through `policy_filter → candidates → score → select(admissible=…)` via `Index.from_cards`
— the real `Router`, never a reimplementation.

**Relationship to `docs/reports/bakeoff/DENSE-PROGRAM.md` v2.1:** this is the **test-B**
(SkillRetBench) half of that programme's pre-registered **F0 baseline** and **reference run R1**.
Per DENSE-PROGRAM.md §6, R1 "shows what a tuned encoder does through the product path before any
dev tuning. Its numbers are reported. They gate nothing." Nothing observed on this corpus chose
`w_dense` or any other configuration — `w_dense=1` (ON) was fixed from the CLI's own
`DEFAULT_WEIGHTS` ON/OFF guidance (`build_arms()`) before this script ever ran against
SkillRetBench. Gate columns below are reported as observed, not as an adoption decision; adoption
is decided only for a future dev-tuned frozen variant, run once per family on both test corpora.

Converter + runner: `tools/eval/skillretbench.py` (`convert` / `run` / `overlap` / `distill` /
`materialize` / `latency` subcommands). Tests: `tests/test_skillretbench.py` (24 cases, all
passing; full repo suite, 328 tests, all passing). Per-query output:
`docs/reports/bakeoff/validation/skillretbench-rankings.jsonl.gz`; aggregated metrics:
`docs/reports/bakeoff/validation/skillretbench-metrics.json`. No tuning was performed against
this set.

## Arms

| Arm | What |
|---|---|
| **B1** | Shipped config: integer BM25F retrieval, RRF fusion, `w_scope=200`, node-scoped admissibility. |
| **B1-scope** | B1 with `w_scope=0` (scope-preference term off). |
| **B1-closure** | B1 with hard `requires`-closure injection inside `select()`. |
| **B3b+B5** | RRF fusion of B1 BM25F with a static dense signal from `SKILLRET-Embedding-0.6B`, distilled into a tier-1 int8 word table over this corpus's own vocabulary (`tools/bakeoff/distill.py`, unmodified). This is R1. |

Every arm ran under two node-resolution policies:

- **`node_scoped`** — the query resolves to its `category` field as the caller node (the
  interpretation applied to every setting, not just `single_skill`/`multi_skill_composition`,
  since SkillRetBench queries always carry a definite category).
- **`node_root`** — the query resolves to `_root`, i.e. the full 501-skill visible universe,
  matching the search scope the dataset's own BM25/Dense/Hybrid/NaiveLLM/SADO baselines use.
  Run only for B1, as a scope ablation (`b1_scope_ablation_root` / `..._ir` in the metrics JSON).

## Corpus and query facts

```
n_skills                       501
n_categories                   102
total_composable_edges (requires) 1,241
dangling_requires               0    (checked exhaustively — clean)
n_korean_trigger_phrases_dropped 1,044   (korean_triggers field; see "Korean" below)
n_queries                     1,250
n_hangul (Korean-script) queries 151 / 1,250 = 12.08%
  single_skill              103 / 400
  multi_skill_composition     4 / 200
  distractor                  39 / 300
  outdated_redundant           1 / 150
  budget_constrained           4 / 200
```

`dangling_requires: []` — every `requires` edge in this corpus resolves to a real skill in the
same corpus; no data-integrity problem here.

## Main results — node_scoped, all queries (product-path metrics)

```
=== B1 ===
setting                       n    hit@1  ndcg@10 recall@8 all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------
single_skill                 400   0.7286   0.8484   0.9457          0.8600                —
multi_skill_composition      200   0.8200   0.6730   0.5208          0.1550                —
distractor                   300   0.5333   0.6972   0.8300          0.6867            0.7433
outdated_redundant           150   0.7867   0.8937   0.9800          0.9400                —
budget_constrained           200   0.7300   0.5040   0.1360          0.0000                —
OVERALL                     1250   0.7025   0.7296   0.7153          0.5658            0.7433

=== B1-scope (w_scope=0) ===
byte-identical to B1 on every metric, every setting — see "w_scope is provably inert" below.

=== B1-closure (hard requires-closure) ===
setting                       n    hit@1  ndcg@10 recall@8 all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------
single_skill                 400   0.7286   0.8484   0.9457          0.8886                —
multi_skill_composition      200   0.8200   0.6730   0.5208          0.1350                —
distractor                   300   0.5333   0.6972   0.8300          0.7633            0.7700
outdated_redundant           150   0.7867   0.8937   0.9800          0.9600                —
budget_constrained           200   0.7300   0.5040   0.1360          0.0000                —
OVERALL                     1250   0.7025   0.7296   0.7153          0.5925            0.7700

=== B3b+B5 (dense reference run R1) ===
setting                       n    hit@1  ndcg@10 recall@8 all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------
single_skill                 400   0.6171   0.7696   0.9000          0.7943                —
multi_skill_composition      200   0.7150   0.6220   0.5128          0.1350                —
distractor                   300   0.3933   0.5795   0.7267          0.5800            0.7500
outdated_redundant           150   0.6067   0.7737   0.9267          0.8400                —
budget_constrained           200   0.6650   0.4978   0.1390          0.0000                —
OVERALL                     1250   0.5842   0.6527   0.6686          0.5042            0.7500
```

`hit@1`, `ndcg@10`, `all_required@4`, `distractor_rate@4` follow `tools/eval/metrics.py`'s own
definitions verbatim (grade-3 = must-be-first, grade-2 = required companion, `recall@8` is that
module's own hardcoded k=8 golden-set convention). `distractor_rate@4` is `metrics.py`'s
`distractor_rate()`; SkillRetBench calls this **HSR@4** (harmful-skill-served rate) per
DENSE-PROGRAM.md §5 — same function, not a second metric.

**B1 vs B1-scope: byte-identical.** Not a coincidence and not evidence `w_scope` is generally
useless — see the mechanistic explanation below.

**B1 vs B1-closure:** closure raises OVERALL `all_required@4` by +2.67pp (0.5658→0.5925), driven
entirely by `single_skill` (+2.86pp), `distractor` (+7.67pp), `outdated_redundant` (+2.00pp).
`multi_skill_composition` moves the *other* way, -2.00pp (0.155→0.135) — plausibly because that
setting's required companions are query-labelled gold skills, not necessarily linked to the
primary pick via a `requires` edge in the corpus, so forcibly injecting the `requires`-closure
can occupy a card slot that would otherwise have held one of those un-linked companions (not
root-caused further here). The `all_required@4` gain on `distractor` also comes with a matching
+2.67pp rise in `distractor_rate@4` (0.7433→0.7700) — closure is a real trade, not a free win.
`budget_constrained` is unaffected in both directions (see the structural ceiling below).

## Main results — node_scoped, all queries (baseline-comparable IR metrics)

```
=== B1 (baseline-comparable) ===
setting                          n  recall@1  recall@3  recall@5 recall@10    ndcg@1    ndcg@3    ndcg@5   ndcg@10       mrr       map
----------------------------------------------------------------------------------------------------------------------------------------
single_skill                   400    0.6375    0.7525    0.7850    0.8450    0.6375    0.7094    0.7231    0.7423    0.7098    0.7098
multi_skill_composition         200    0.2798    0.4498    0.4995    0.5358    0.8200    0.5615    0.5510    0.5670    0.8870    0.4399
distractor                      300    0.5333    0.7233    0.7833    0.8600    0.5333    0.6480    0.6729    0.6972    0.6454    0.6454
outdated_redundant              150    0.7867    0.9600    0.9600    0.9800    0.7867    0.8873    0.8873    0.8937    0.8648    0.8648
budget_constrained               200    0.0292    0.0664    0.0974    0.1594    0.7300    0.5927    0.5367    0.4580    0.8282    0.1282
OVERALL                        1250    0.4758    0.6122    0.6499    0.7056    0.6744    0.6737    0.6734    0.6761    0.7602    0.5767

=== B3b+B5 -- see the coverage/gate tables in the "Dense reference run R1" section below for
    its full baseline-comparable row-by-row deltas against B1. ===
```

`ir_alignment_metrics`'s `ndcg@10`/`mrr`/`map` use a different, uncapped-at-8 per-k definition
than the product table's `ndcg@10` above (`format_ir_alignment_table`'s own docstring states this
explicitly) — the two `ndcg@10` columns are deliberately not the same number; use the
product-path table for product claims and this table only for baseline-comparable claims.

## The dataset's own baselines

SkillRetBench ships its own baseline run (`baseline_results.json`, loaded via the same
`load_skillretbench()`). Its BM25 row is a real, independent implementation — everything else in
that file is **not**: `meta.dense_backend == "jaccard_fallback"` (its "Dense" row is a Jaccard
string-overlap stand-in, not a real embedding model) and its own `summary_table` footnote states
"NaiveLLM / SADO: simulated (no API)". This report compares Guidefold **only** against the
dataset's real BM25 row; Dense/Hybrid/NaiveLLM/SADO are reproduced below for completeness but are
never treated as real comparators.

```
Dataset's own per-setting BM25 (recall@k / ndcg@k / mrr / map):
setting                     recall@1 recall@3 recall@5 recall@10  ndcg@1  ndcg@3  ndcg@5 ndcg@10    mrr    map
------------------------------------------------------------------------------------------------------------------
single_skill                  0.4950   0.6125   0.6575   0.7025  0.4950  0.5642  0.5827  0.5971  0.5636  0.5636
multi_skill_composition        0.2659   0.5022   0.6077   0.7611  0.7700  0.6047  0.6221  0.6928  0.8498  0.5630
distractor                    0.2700   0.3700   0.4300   0.5033  0.2700  0.3283  0.3525  0.3759  0.3365  0.3365
outdated_redundant            0.8667   0.9600   0.9933   1.0000  0.8667  0.9186  0.9323  0.9346  0.9131  0.9131
budget_constrained            0.0040   0.0138   0.0210   0.0224  0.1000  0.1118  0.1060  0.0715  0.1998  0.0123

Dataset's own macro-mean-over-settings summary (from baseline_results.json's own summary_table):
Baseline   R@1     R@3     R@5     R@10    nDCG@10  MRR     MAP
BM25       0.3803  0.4917  0.5419  0.5979  0.5344   0.5726  0.4777
Dense*     0.1178  0.2223  0.2884  0.3652  0.2683   0.2906  0.2043   (* jaccard_fallback, not real)
Hybrid*    0.2277  0.3298  0.3968  0.4820  0.3912   0.4255  0.3231   (* built on the fake Dense row)
NaiveLLM*  0.3017  0.4038  0.4708  0.5560  0.4512   0.4995  0.3891   (* simulated, no API)
SADO*      0.2657  0.3678  0.4348  0.5200  0.4292   0.4675  0.3611   (* simulated, no API)
```

## The node_scoped-vs-node_root fairness caveat — an honest "did not map cleanly" finding

Comparing Guidefold's `node_scoped` numbers directly against the dataset's own BM25 row is
**not** a like-for-like comparison: `node_scoped` benefits from an assumed-correct category
resolution that shrinks the visible candidate universe (down to one category + `_root`, which
holds no cards in this corpus) before BM25F ever ranks anything. The dataset's own BM25 baseline
searches the full 501-skill corpus for every query. The fair, same-visible-universe comparison is
`node_root`.

Computed the same way as the dataset's own `summary_table` (simple mean over the five settings,
not query-weighted):

```
                R@1     R@3     R@5     R@10    nDCG@10  MRR     MAP
Dataset BM25    0.3803  0.4917  0.5419  0.5979  0.5344   0.5726  0.4777
Guidefold B1
  @ node_scoped 0.4533  0.5904  0.6250  0.6760  0.6717   0.7870  0.5576   <- outperforms on every metric
  @ node_root   0.2798  0.4018  0.4572  0.5302  0.4549   0.4924  0.3783   <- underperforms on every metric
```

Under `node_scoped`, Guidefold's B1 beats the dataset's own BM25 on every column. Under
`node_root` — the scope the dataset's baseline actually searches — Guidefold's own BM25F trails
the dataset's reference BM25 implementation on every column instead. The apparent outperformance
is therefore largely an artifact of scope-narrowing, not necessarily evidence of a stronger core
BM25 implementation. Plausible causes for the `node_root` shortfall (different tokenization,
field weighting, or IDF variant) have not been root-caused here; this is flagged as an honest gap
rather than explained away. `node_scoped` remains the number that matters operationally (it is
what the shipped hook actually searches, since Guidefold always resolves a caller's real node),
but readers comparing against the dataset's published BM25 figure should use `node_root`.

## node_root scope ablation, full table (B1 only)

```
=== B1@_root (product-path metrics) ===
setting                       n    hit@1  ndcg@10 recall@8 all_required@4 distractor_rate@4
------------------------------------------------------------------------------------------------
single_skill                 400   0.4257   0.5574   0.6686          0.5286                —
multi_skill_composition      200   0.5650   0.5856   0.5890          0.3550                —
distractor                   300   0.2133   0.3124   0.4000          0.2833            0.3967
outdated_redundant           150   0.6133   0.7709   0.9133          0.7267                —
budget_constrained           200   0.1900   0.1729   0.0506          0.0000                —
OVERALL                     1250   0.3800   0.4635   0.5158          0.3750            0.3967

=== B1@_root (baseline-comparable) ===
setting                          n  recall@1  recall@3  recall@5 recall@10    ndcg@1    ndcg@3    ndcg@5   ndcg@10       mrr       map
----------------------------------------------------------------------------------------------------------------------------------------
single_skill                   400    0.3725    0.4900    0.5525    0.6175    0.3725    0.4417    0.4671    0.4877    0.4472    0.4472
multi_skill_composition         200    0.1923    0.3817    0.4874    0.6296    0.5650    0.4586    0.4828    0.5484    0.7006    0.4148
distractor                      300    0.2133    0.3133    0.3700    0.4167    0.2133    0.2742    0.2975    0.3124    0.2794    0.2794
outdated_redundant              150    0.6133    0.8067    0.8467    0.9267    0.6133    0.7275    0.7444    0.7709    0.7209    0.7209
budget_constrained               200    0.0076    0.0174    0.0292    0.0606    0.1900    0.1565    0.1534    0.1552    0.3137    0.0292
OVERALL                        1250    0.2760    0.3927    0.4499    0.5192    0.3648    0.3929    0.4120    0.4361    0.4589    0.3677
```

This is the per-setting table the macro-mean row in the fairness-caveat section above is built
from — laid alongside the dataset's own per-setting BM25 table earlier in this report, it lets a
reader compare `node_root` against the dataset's real baseline setting-by-setting rather than
only on the macro mean (e.g. `distractor`: Guidefold `node_root` recall@1=0.2133 vs dataset BM25
recall@1=0.2700 — trails there too, consistent with the macro-level shortfall).

Note `distractor`'s HSR@4 (`distractor_rate@4`) *drops* from 0.7433 (`node_scoped`) to 0.3967
(`node_root`) — with the full 501-skill universe visible, more genuine off-category competitors
out-rank the specific named distractors this setting labels, so a lower "labelled-distractor"
rate here is a side effect of a much larger, mostly-irrelevant candidate pool, not evidence of
better distractor rejection.

## Korean queries: a real, quantified retrieval gap

Trigger phrases in `korean_triggers` are **not folded into the shared tokenizer's index** (a
deliberate scope decision — the shared tokenizer's accent-folding pipeline is Latin-oriented, per
PR #11). 1,044 Korean trigger phrases are dropped as a result. This has a measurable, precisely
localized effect:

- Every one of the 50 abstentions in the `all_queries` / `node_scoped` run (`n_answered=1200` of
  1,250) occurs in `single_skill`, and **all 50 are Korean-script queries** — 0 of the 297 Latin
  `single_skill` queries ever abstain, and 0 queries in any other setting (`multi_skill_composition`,
  `distractor`, `outdated_redundant`, `budget_constrained`) ever abstain, in either language.
  Concretely: 50/103 (48.5%) of `single_skill`'s Korean queries get **zero** BM25F hits at all
  (`retrieval: []`) against their 2 admissible candidates; the other 53/103 (51.5%) still resolve
  fine (likely via Latin skill-id/description tokens the query text also happens to share).
- The `latin_only` slice (1,099/1,250 queries) shows **zero** abstentions anywhere
  (`coverage: 1.0`) and slightly higher OVERALL scores across the board (e.g. B1 `hit@1` 0.7225
  vs 0.7025 on all queries) — consistent with the Korean subset dragging the aggregate down
  specifically through this abstention mechanism, not through worse ranking once a query is
  answered at all.
- `status="active"` mapping and Korean handling are corpus-shape decisions the converter states
  up front (`corpus_to_cards`'s docstring), not silent defaults.

## Dense reference run R1 — coverage and gates (SS6/SS5 of DENSE-PROGRAM.md)

**This is a reference run. It gates nothing.** `w_dense=1` was fixed from tooling defaults before
this script ever touched SkillRetBench results; adoption is decided later, only for a dev-tuned
frozen variant, on both test corpora together.

### Coverage: gold skills BM25F's top-50 missed that the dense signal recovers

```
setting                   missed_by_bm25   recovered    coverage
----------------------------------------------------------------
single_skill                          50           0      0.0000
multi_skill_composition              299           0      0.0000
distractor                             0           0           —   (BM25 never misses gold here)
outdated_redundant                     0           0           —   (BM25 never misses gold here)
budget_constrained                  3174         269      0.0848
OVERALL                             3523         269      0.0764
```

Per DENSE-PROGRAM.md §6, this coverage figure is "the most useful number [R1] produces, because
it bounds how much *any* dense signal could add to candidates on these corpora." At **7.64%**
overall (and 8.48% on the one setting with real headroom, `budget_constrained`), the ceiling on
what this particular tuned encoder could add through RRF fusion on this corpus is small — a fact
about this run's coverage number, stated per-setting as required, not a claim that "the programme
ends here."

### Gates, as observed (three-state: PASS / fail / n/a — n/a is "undetermined", never "fail")

```
setting                   all_req D          [95% CI]  gate   hit@1 D  gate  ndcg@10 D  gate   HSR@4 D  gate
----------------------------------------------------------------------------------------------------------------
single_skill                -0.0657 [-0.1057,-0.0257]  fail   -0.1114  fail    -0.0689  fail         —   n/a
multi_skill_composition     -0.0200 [-0.0400,-0.0050]  fail   -0.1050  fail    -0.0510  fail         —   n/a
distractor                  -0.1067 [-0.1567,-0.0533]  fail   -0.1400  fail    -0.1178  fail   +0.0067  PASS
outdated_redundant          -0.1000 [-0.1667,-0.0400]  fail   -0.1800  fail    -0.1200  fail         —   n/a
budget_constrained           0.0000 [ 0.0000, 0.0000]  fail   -0.0650  fail    -0.0062  PASS         —   n/a
OVERALL                      -0.0617 [-0.0825,-0.0417]  fail   -0.1183  fail    -0.0739  fail   +0.0067  PASS
```

Paired bootstrap, 1,000 resamples over queries, 95% CI on the delta vs B1. Gate rules per
DENSE-PROGRAM.md §5: `all_required@4` needs its CI to exclude 0 with a lower bound at or above
+2.0pp (every setting fails this, most decisively — the CI never even crosses 0 in the positive
direction); `distractor_rate@4`/HSR@4 and `hit@1`/`ndcg@10` must not regress by more than 1.0pp
(hit@1 and ndcg@10 fail almost everywhere by a wide margin; HSR@4 is `n/a` — undetermined, not
"fail" — on the four settings with no labelled distractors, and PASSes on `distractor`/OVERALL
because the +0.67pp rise in harmful-skill exposure is within the 1.0pp tolerance).
`ndcg@10` PASSes only on `budget_constrained` (delta -0.62pp, inside tolerance) — the one setting
where B1's own product-path score is already so structurally capped (see below) that the dense
signal's relative miss is small in absolute terms. As a reference run, none of this decides
adoption; it is reported honestly, per-setting, exactly as required.

## Structural findings (not router defects — corpus geometry)

**`budget_constrained`'s `all_required@4=0.0000` is mathematically guaranteed, every arm, every
query.** Every one of its 200 cases has **exactly 25** grade≥2 required skills (`gold_skills`
always has length 25 in this setting — checked exhaustively), against a `k_cards=4` injection
budget. No router, however good, can fit 25 required items into 4 slots — `all_required@4=0` here
says nothing about ranking quality. `recall@8`'s ceiling for this setting is 8/25 = 0.32; B1
scores 0.1360, comfortably below even that ceiling, so real headroom does exist in `recall@8`
even though `all_required@4` structurally cannot move.

**`multi_skill_composition`'s cross-category gap, precisely split two ways.** 77.5% (155/200) of
its queries have at least one required companion skill outside the primary skill's own category
(permanently inadmissible under `node_scoped`, since `Router._visible_nodes()` only ever admits a
query's own category plus its ancestor chain in this flat, single-level corpus). At the
individual-companion level, 67.1% (284/423) of all required companion skills across this setting
cross that category boundary. This structurally caps `all_required@4` for `node_scoped` on this
setting regardless of ranking quality for the majority of its queries.

**`w_scope` is provably inert on this corpus — the exact mechanism.** `Router.score()` adds
`w_scope // (1 + self._hops(c["node"], node))` to every candidate. `_visible_nodes(node)` (the
hard admissibility gate `policy_filter` uses) admits only a query's own category plus its
ancestor chain — in this corpus that's exactly `{category, "_root"}`, and no card is ever
registered under `"_root"` (every skill lives directly in its own leaf category). Verified
directly against the shipped CLI: `Router._hops("cat_x", "cat_x") == 0` for every candidate under
`node_scoped`, so `w_scope // (1 + 0) == w_scope` is added identically to every admissible
candidate's score — a constant offset that provably cannot change relative order. This is why B1
(`w_scope=200`) and B1-scope (`w_scope=0`) produce byte-identical rankings here: a structural fact
about this corpus's flat category structure, not evidence `w_scope` is useless in a real,
multi-level monorepo where candidates would sit at different hop-distances from the caller.

## Corrected finding: `outdated_redundant`'s `outdated_skill_id`

All 150 `outdated_redundant` queries in this corpus revision **do** populate
`outdated_skill_id`, always as the synthetic marker `"<gold_skill_id>__v1_deprecated"` — checked
exhaustively (150/150) — which resolves to **zero** real corpus `skill_id` entries (also checked
exhaustively, 0/150). `distractor_skills` is separately empty on those same 150 queries. There is
no real successor skill in this corpus revision for `replaced_by` to point to. `status="active"`
therefore remains the only defensible mapping for every card, but for the narrower and more
precise reason that the field is populated yet always dangles — not, as an earlier draft of this
work incorrectly stated, because the field is unpopulated. Both `tools/eval/skillretbench.py`'s
docstring and `tests/test_skillretbench.py` state the corrected finding.

## SkillRet / SkillRetBench overlap (teacher fine-tuning caveat)

`SKILLRET-Embedding-0.6B` (the encoder behind B3b+B5) was fine-tuned on **SkillRet**, a
different, larger, public-GitHub-scrape dataset from the same organisation — not on SkillRetBench
itself. Computed via the product's own `overlap_report()` (`tools/eval/skillretbench.py overlap`):

```
skillret_skills: 6,006   skillretbench_skills: 501
id_overlap_count: 0        (different id namespaces entirely: UUIDs vs slugs — not informative alone)
name_overlap_count: 6
  "requesting code review"        "skill creator"              "testing strategy"
  "user research"                 "using git worktrees"        "verification before completion"
```

Six SkillRetBench skill names have an exact-match (case-folded) counterpart in SkillRet's 6,006.
If the teacher saw a close paraphrase of one of these six during its own fine-tuning, any B3b
coverage gain on those specific queries could look better than it would on a truly unseen corpus.
Given it's 6 of 501 skills (1.2%) and name-based only (no id overlap), the leakage risk is judged
small, but is disclosed rather than assumed away.

## Latency

```
{
  "n": 220, "p50_ms": 210.7, "p95_ms": 255.0, "mean_ms": 215.2,
  "min_ms": 180.8, "max_ms": 327.9,
  "machine": "Linux 6.18...-WSL2 (x86_64), Intel Core i7-10700K @ 3.80GHz, 16 threads, CPython 3.12.3"
}
```

Measured via a real `guidefold hook` subprocess per query (one warm-up excluded), fresh process,
against the real on-disk E1.4 artifact built by a real `guidefold index` subprocess — the same
protocol as `tools/eval/measure_hook_latency.py`. p50=210.7ms / p95=255.0ms clears both the 300ms
and 500ms latency tiers comfortably (possibly somewhat elevated versus an earlier, quieter-machine
measurement of ~125/149ms from CPU contention with other concurrently-running background agents
on this machine — noted for context, does not change the tier conclusion either way).

**The dense arm's (B3b+B5) real hook-subprocess latency is not measurable with the current CLI**
— a stated limitation, not a shortcut. `write_index_artifact` hardcodes
`Index.build(root, cfg, word_vectors=None)`; there is no CLI flag today to inject a distilled word
table into the on-disk E1.4 artifact the hook actually loads, so only the shipped B1 configuration
can be timed this way. Consistent with DENSE-PROGRAM.md's own stance that latency is not a gate
for F1/R1.

## Verdict

- **B1 (shipped)** is the only arm evaluated here that is actually adopted; it is not compared
  against any adoption gate in this report, only against the dataset's real BM25 baseline and the
  R1 reference. Its per-setting product-path numbers are reported above in full, alongside the
  honest caveat that its apparent edge over the dataset's own BM25 depends heavily on which scope
  (`node_scoped` vs `node_root`) is used for the comparison.
- **B1-scope** is byte-identical to B1 on this corpus, for a fully explained structural reason
  (flat, single-level category geometry), not a claim about `w_scope`'s value in general.
- **B1-closure** trades a real `distractor`-setting exposure increase (+2.67pp HSR@4) for a real
  `all_required@4` gain (+2.67pp OVERALL), with an inconsistent effect on `multi_skill_composition`
  (-2.00pp) — a genuine trade-off, not a strict improvement.
- **B3b+B5 (R1)** gates nothing on this reference run. Its coverage ceiling (7.64% overall) bounds
  how much this specific tuned encoder could add through fusion on this corpus; its gate table
  fails `all_required@4` and `hit@1` on every setting and `ndcg@10` on all but one, exactly as
  reported, without any adoption implication.
- Everything that did not map cleanly is disclosed rather than smoothed over: the
  `node_scoped`/`node_root` fairness gap, the Korean-query abstention mechanism, the
  `multi_skill_composition` cross-category ceiling, `budget_constrained`'s structural
  `all_required@4=0` floor, the corrected `outdated_redundant` finding, and the small
  SkillRet/SkillRetBench name-overlap caveat.
