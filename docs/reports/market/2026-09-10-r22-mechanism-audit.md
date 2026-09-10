# R22 retained-output mechanism audit

Status: post-hoc analysis, 10 September 2026; no new model or retrieval calls.
Purpose: interpret the positive result during the owner's pause in experiments.
Inputs: retained map-only R22 report, map, assignments, corpus and six query files.
Scope: supplements [the product update](2026-09-10-research-product-update.md); corrects sample-cap and validation wording. Does not replace the protocol or change the experiment.

## What held up

An independent standard-library implementation of map-only TF-IDF reproduced all 21,600 scope selections in the four text-based arms, with zero substantive mismatches and zero numerical tie differences. It reconstructs the query analyzer, vocabulary, IDF, sublinear term weights, normalization and score ordering. This complements the previous verifier, which reconstructed rankings using retained scope choices; it does not independently audit the map-generation model or k-means clustering.

Full-map Recall@10 gained 8.5272 pp versus flat. Its exact query-weighted decomposition is +6.0756 pp from promoting relevant candidates already in dense top-50, +7.9108 pp from recovering relevant candidates outside top-50, and −5.4593 pp from losing previously retrieved relevant candidates. The corresponding query-skill occurrence counts are 540, 561 and 461; they are not counts of distinct skills or queries.

Complete@4 gained on 551 queries and lost on 288, giving 263 net gains. Of the 551 gains, 351 had all required skills already in dense top-50 and **200 required at least one skill outside that pool**. The method recovers missing candidates as well as reorders existing ones. This decomposition is descriptive; it is not a causal ablation or a task-completion measure.

## Reused labels and uncertainty

Queries contain 1,113 distinct `(dataset, exact gold skill set)` groups. A post-hoc bootstrap resampled these groups, computing the query-weighted mean from sampled group sums and sizes (10,000 draws, seed 20260910).

| Comparison | Recall@10 delta, 95% interval | Complete@4 delta, 95% interval |
|---|---|---|
| Full map minus flat | +8.53 pp [3.64, 14.10] | +4.87 pp [0.83, 9.39] |
| Full map minus metadata | +7.45 pp [2.87, 13.07] | +4.19 pp [0.52, 8.67] |

These positive intervals partially address label reuse. They do not establish that the groups are independent: different sets can share skills and dataset properties. The existing bootstrap across six datasets still includes zero; CHAMP and TheoremQA still regress. No inference about universal improvement follows.

## The main generalization risk

Only 636 distinct skills appear in gold sets. The 25,626 web skills are unlabelled distractors. Every query's gold skills come from its own dataset prefix, and the hierarchy uses precisely those corpus prefixes before clustering. That is an informative partition, even though query labels were not used for selection. On ToolQA, 1,430 queries reuse just 14 distinct gold sets; on LogicBench, 760 queries reuse 19.

Full-map top-ten results contained 19.64% web skills versus 59.86% for flat search. Scope-name routing removed even more (14.26%) but lost 7.29 pp Recall@10. This control shows that reducing distractors is insufficient by itself; it does not remove source-family routing as a confound. A future, separately authorized evaluation should use natural repository scopes or a prefix-blind hierarchy to assess that risk. No such experiment was started.

Map generation used a cap of twelve sampled names/descriptions per leaf: **263 cards in total, 2–12 per leaf**, with ten leaves below twelve. Source-ID and format checks do not validate the generated meaning. Wording in RESEARCH, the protocol description and presentation was corrected accordingly on 10 September after inspecting the inputs; the experiment itself is unchanged.

## Product and publication interpretation

The strongest supported product hypothesis is that LLM-written descriptions of task families help a second search find useful skills missed by the first. The positive same-budget metadata control comparison and the 200 recovered complete sets make this worth retaining as an experimental search path. They do not measure the value of additional tree depth, natural monorepo hierarchy, knowledge ascent or task execution.

This strengthens an empirical method result, while identifying a benchmark shortcut that a convincing paper must address. Novelty and the end-to-end product claim remain unresolved. The evidence does not justify a numeric paper-acceptance probability or the word breakthrough.

## Reproduction

Bundled Windows Python with NumPy, against the unchanged WSL-mounted artifacts:

```text
python tools/research/audit_r22_mechanism.py
python tools/research/export_product_evidence.py
```

PASS: source hashes, query/gold alignment, all text-arm scope choices and exact Recall decomposition. Output: [r22-mechanism-audit.json](../../../research/sra-external-pyramid-2026-09-08/r22-mechanism-audit.json); implementation: [audit_r22_mechanism.py](../../../tools/research/audit_r22_mechanism.py). The [public record](../../../ui/public/evidence/research-2026-09-10.json) contains the audit hash and compact results. Detailed output is retained in `.guidefold/checks/research-product-update-20260910/mechanism-audit.log`.
