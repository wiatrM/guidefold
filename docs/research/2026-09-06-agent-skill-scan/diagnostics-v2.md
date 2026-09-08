# CPU diagnosis of field fusion — 2026-09-06

The field+dense model's loss is not specifically a multi-skill failure and cannot be explained
as simply underweighting multi-skill queries. Saved predictions show comparable Recall@10 losses
at every gold cardinality. The next experiment should separately test representation enrichment
and query-aware ranking objectives, with fresh internal holdout queries and no public-test reruns.

This is an exploratory diagnosis of the exposed first-spike DEV, not another model selection run.
No GPU, fitting, new scoring treatment or threshold search was used. Reproduction:

```sh
wsl -d Ubuntu-24.04 --cd /home/mike/projects/guidefold -- /home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-cto-v2/diagnose.py
```

The CPU command took12.1 seconds. It reads the original feature memmap and JSON weights in
read-only mode, saved ranked outputs and train labels. It writes only its own `diagnostics.json`
and `recorded-exposure-ids.json`. The original spike, weights and results remain unchanged.

## Observed failure location

| Gold skills | Queries | Flat MLP Recall@10 | Field MLP Recall@10 | Sparse-field MLP Recall@10 |
|---:|---:|---:|---:|---:|
| 1 | 328 | 94.21% | 90.55% | 93.60% |
| 2 | 333 | 62.31% | 58.56% | 62.31% |
| 3 | 339 | 47.39% | 43.95% | 48.38% |

Field-minus-flat losses are -3.66,-3.75,-3.44 pp respectively. The average loss is not driven
only by k3 queries. Across the1,000 first-gold instances, field loses63 previously retrieved
items and gains9. Across1,011 companion-gold instances, it loses33 and gains15. The larger net
loss is on the first listed gold, not the companions. Gold-list order is a dataset annotation;
calling it a universally required execution order would be unjustified.

There is nevertheless a common multi-skill representation problem. For k3 queries, flat MLP
retrieves the first listed gold at78.17% but companion instances at32.01%; sparse-field MLP
gets76.70% and34.22%. Field MLP gets71.98% and29.94%. All-gold injection@4 on k3 is3.24%,
2.36%,4.72% for flat, field and sparse-field respectively. Most multi-skill completeness failure
already exists before final top4 selection, and improves little by merely having a tiny head.

The union of the eight single-channel top20 lists covers average gold recall98.48%,74.92%,61.65%
for k1/k2/k3. This is a candidate-recall ceiling ONLY for a retriever restricted to that union.
The existing experiment scored all documents and can recover documents outside every channel's
top20, so61.65% is not a mathematical ceiling on its full-bank MLP. It is relevant when deciding
whether an inexpensive production candidate stage can support a reranker.

## What the training weights actually do

The exact original pair sampler was reconstructed from the feature memmap, with the corrected
DEV-document exclusion. It reproduces186,673 pairs,3,774 positives and36,953 excluded candidate
pairs exactly. Global BCE `pos_weight` is48.4629.

| Gold count | Training queries | Share of queries | Share of BCE coefficient mass | Mean coefficient mass/query |
|---:|---:|---:|---:|---:|
| 1 | 772 | 38.6% | 29.49% | 139.73 |
| 2 | 682 | 34.1% | 35.10% | 188.25 |
| 3 | 546 | 27.3% | 35.41% | 237.26 |

Coefficient mass means negative_count + pos_weight * positive_count before actual loss values,
not measured gradient magnitude. Multi-skill queries receive more positive coefficient mass per
query; the statement "BCE ignores multi-skill examples" is not supported. Oversampling k3 alone
is therefore not an evidence-based fix. Negative counts also vary by query (overall ranges56-123),
so flattening all pairs creates unequal query importance unrelated to the macro query metric.

Pointwise BCE still differs from the evaluation target: it separates global positive/negative
pairs but does not directly require every positive in one query to outrank that query's negatives.
Absolute cosine scales and query difficulty vary. This motivates a query-normalized ranking
objective; it does not prove that objective changes will improve this dataset. Pairwise ranking
and listwise objectives are established alternatives, not novel Guidefold algorithms.
[RankNet](https://www.microsoft.com/en-us/research/publication/learning-to-rank-using-gradient-descent/)
and [ListNet](https://www.microsoft.com/en-us/research/publication/learning-to-rank-from-pairwise-approach-to-listwise-approach/)
provide primary references for those distinctions. The proposed losses below are explicit small
variants inspired by that literature, not claimed reproductions.

## Saved-head sensitivity

Analytic local derivatives were evaluated at the2,011 DEV gold feature vectors using the saved
ReLU network weights, without fitting. For field MLP, increasing dense-description cosine while
holding every other feature fixed decreases the score at96.22% of those points; dense-name has
a negative local derivative at50.97%. Sparse body is mostly positive, with8.20% negative.

This proves the unconstrained head learned strong suppressive behavior for some dense signals.
It does not prove those features should always increase score: correlated similarities, generic
embeddings and hard-negative selection can make a high description match evidence for a wrong
candidate. Nor does a coordinate derivative identify the causal reason for the observed recall
loss. A monotonic head is a reasonable prospective regularization test, not an automatic repair.
The stronger claim that all negative derivatives are bugs would be incorrect.

The sparse-field head itself has negative coordinate derivatives at22.8%,24.2%,23.3% of gold
vectors for name, description and body. Thus monotonicity is an open hypothesis even for the
apparently promising sparse arm. It was not tested by the first run.

## Representation and negatives

The name field has weak independent top20 gold recall (k3:21.44% sparse,20.45% dense), while
body/flat sparse achieves53.88%/55.36%. Dense body/flat achieves40.71%. Giving every field equal
influence does not reflect these measured signal differences. The first run's learned field
head repaired some Hit@1 damage relative to uniform fields but retained the recall deficit.

Whole-query encoding can emphasize one intent; individually encoding name and description does
not add missing task coverage. Body truncation was64.6% and flat truncation66.0%. Metadata
and pseudoquery enrichment are concrete ways to expose applicability terms without a query-time
model, provided the generator sees documents only and all comparisons retain the original bank.
Their benefit still requires measurement; earlier F3 results in this repository remain prior
negative/limited evidence and are not overwritten by a new generator run.

Unlabelled hard negatives can be useful alternative skills. Treating all of them as verified
negative is an assumption. Keep gold protection and exact-duplicate exclusion, preserve the
list of mined candidates for an auditable sample, and measure disagreement/near-duplicate rates.
Do not silently relabel negatives from evaluation outcomes. A hard-negative candidate union
should be frozen across loss arms; changing both negatives and objective prevents attribution.

## Fresh internal holdout boundary

An inventory of JSON/gzip artifacts under `docs/reports/bakeoff/validation` and current
`research/spikes`, excluding caches, found3,000 distinct recorded q-train IDs: the2,000 first-fit
queries plus1,000 exposed DEV. There are60,259 train IDs not recorded in that inventory
(k1:19,676; k2:20,020; k3:20,563). The inventory is persisted and reproducible.

"Unrecorded in scanned artifacts" is the precise claim. Other local/remote logs and external
experiments are not covered. Before freezing another holdout, merge the coordinator's complete
exposure ledger. Exclude exact normalized query duplicates and all known previously evaluated
IDs. The raw corpus and all query labels were available to split construction; new holdout
means previously unscored query outcomes, not an unseen dataset or audited pretraining isolation.

The next method-family proposal is `protocol-v2-proposal.md`. The user subsequently prioritized
LLM metadata/pseudoquery enrichment; its directly actionable bounded design is in
`enrichment-protocol-proposal.md`. Run and close that pilot first rather than silently expanding
the six-config objective family alongside it.
