# What the literature says, and what we measured

**Status:** Living synthesis, reviewed 2026-09-05 against main `c08c58c`.
**Companions:** [full source and architecture review](reports/bakeoff/E1.3-architecture-after-research.md), [source manifest](reports/bakeoff/validation/papers-manifest-2026-09-05.json), [ADR-0022](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md), [first peer review](reports/bakeoff/E1.3-peer-review-2026-09-05.md), [E1 closure plan](reports/bakeoff/E1-closure-plan.md).

The current choice is a local sparse router with dense disabled and experimental reranking in shadow mode. The evidence supports that configuration as a working baseline while measurement and bundle selection improve. It does not establish that semantic retrieval cannot help, or that domain fine-tuning is its only credible route back.

The original bake-off, later diagnostic experiments, and current CLI are different measured objects. Every comparison below names which one it describes. Full third-party publications remain outside the repository; the manifest records versions, content hashes, incomplete downloads and duplicate files.

## 1. All cached sources, with explicit coverage

The current cache contains **16 files representing 11 sources**: 10 publications and Model2Vec software documentation. An earlier snapshot had 12 files and 9 sources. Named SkillRouter/SkillRet full copies duplicate the existing full-text files. `fetch.sh` is a download script, not scientific evidence, and was inspected without execution.

| Source | Verified version/material | Applicable lesson and limit |
|---|---|---|
| [Robertson–Zaragoza BM25/BM25F](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf) | 2009 full PDF | Field weights, normalization and saturation interact. Both aggregated-field and per-field variants are described; benchmark/runtime parity must be explicit. |
| [DPR](https://arxiv.org/html/2004.04906v3) | v3; local abstract supplemented with full text | Contextual retrieval can complement lexical matching; hybrid gains are task-dependent. A static student is a different model. |
| [BEIR](https://arxiv.org/html/2104.08663v4) | v4; abstract supplemented with full text | Strong BM25 baseline, strong reranking results, and demonstrated annotation bias. It does not resolve our status/scope/composition policy. |
| [monoBERT](https://arxiv.org/html/1901.04085v5) | v5; abstract supplemented with full text | Reranking improves ordering of an existing candidate pool. It is not dependency selection, abstention or a hook latency guarantee. |
| [RRF](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) | 2009 full author PDF | Rank fusion is not calibrated confidence. The cached 279-byte file is a 404 page caused by the wrong author-path spelling. |
| [SIF author explanation](https://www.offconvex.org/2018/06/17/textembeddings/) and [code](https://github.com/PrincetonML/SIF) | Final paper unavailable through OpenReview challenge | Weighted averaging and sentence-level component removal are supported by author materials. We do not claim to have read the inaccessible final PDF. |
| [Model2Vec](https://minish.ai/packages/model2vec/distillation/) | Local GitHub snapshot `94cbc1b1ee36cec0f462a0b142a041e1af488203`, official results/docs | Better teachers need not produce better students. Vocabulary, pooling, PCA and quantization need separate evaluation; this is software documentation, not another peer-reviewed paper. |
| [SkillRouter](https://arxiv.org/html/2603.22455v5) | v5 full text | Body access, false-negative filtering and complete skill sets matter. Body removal is not a BM25 field-weight experiment. |
| [SkillRet](https://arxiv.org/html/2605.05726v3) | v3 full text | Correct functional alternatives and train/eval overlap before judging a retriever. Evaluate execution separately from ranking. |
| [Graph of Skills](https://arxiv.org/html/2604.05333v3) | v3 full text | Evaluate dependency bundles under a budget. Joint lexical/reranking ablation does not isolate a neural cross-encoder; propagation is not automatically beneficial at every scale. |
| [SkillResolve-Bench](https://arxiv.org/html/2606.10388v1) | v1 full text | Report harmful sibling exposure alongside helpful retrieval. Representative selection assumes valid alternative groups, not mere similarity. |

## 2. Skill routing evidence and its boundaries

### SkillRet: contextual encoders, not our static student

The corrected v3 benchmark has 16,129 skills overall, including 6,006 evaluation skills and 4,392 evaluation queries. Its NDCG@10 table includes:

| Model | Parameters | NDCG@10 |
|---|---:|---:|
| BM25 | — | 51.69 |
| e5-small-v2 | about 33M | 44.66 |
| e5-large-v2 | 335M | 53.41 |
| Qwen3-Embedding-0.6B | 0.6B | 61.94 |
| SkillRouter encoder | 0.6B | 73.54 |
| SkillRet encoder | 0.6B | 81.12 |

The source table's 118M entry for e5-small-v2 is inconsistent with the checkpoint; the 73.54 SkillRouter row is its encoder, not the 1.2B retrieve-and-rerank pipeline. A small encoder losing to BM25 does not establish that small encoders generally lose.

The paper's separate Terminal-Bench experiment compares **no retrieval with SkillRet retrieval**, yielding 65.5% versus 65.8% success and mean cost $0.86 versus $0.78. It does **not** measure the downstream effect of the roughly 30-point NDCG advantage over BM25. The practical implication is to evaluate success and cost together; reduced cost at demonstrated success non-inferiority can also be valuable. [SkillRet v3](https://arxiv.org/html/2605.05726v3).

### SkillRouter: information access and set semantics

The reported 37–44 pp loss after hiding the body is correct for v5. The core benchmark has 75 expert-verified queries; a supplementary benchmark adds 256 generated queries. Inputs are budgeted: encoder body 2,500 characters, reranker body 2,000. Better Hit@1 is not necessarily better full completeness: the compact system's multi-skill FC@10 is 35.3%, versus 38.2% for a larger baseline.

Use body-aware input and measure truncation. Do not infer a BM25 weight from this ablation. Multi-skill annotations include complementary, substitute and mixed cases: AND between task requirements, OR only between verified substitutes. The four-source hard-negative recipe is a **training** method, not the paper's independent evaluation construction. [SkillRouter v5](https://arxiv.org/html/2603.22455v5).

### GoS and SkillResolve: two different set operations

GoS motivates including necessary companions even when their standalone semantic relevance is low. Our old 26-skill sweep found equivalent PPR and closure rankings; this supports the simpler measured configuration at that snapshot. Neither it nor the paper proves the outcome at pilot scale. The paper's two-run averages, joint component ablations and weaker result at 200 skills limit generalization. [GoS v3](https://arxiv.org/html/2604.05333v3).

SkillResolve addresses choosing the helpful member of a confusing family. In its representative-selection ablation, helpful recall changes little while harmful exposure rises substantially. Its main comparison uses a released family relation and a trained utility scorer; several baselines are zero-shot. HSR measures pre-execution exposure, not a safety guarantee. Use this selection operator for **verified substitutes**; applying one-per-family to complementary dependencies would undermine bundle completeness. A `similar` edge alone does not establish substitutability. [SkillResolve v1](https://arxiv.org/html/2606.10388v1).

## 3. What our experiments establish

### Historical B1/B5: a local negative result with measurement limits

The original unfiltered-corpus bake-off measured B1 Hit@1 0.8736 and B5 (BM25 plus static student via RRF) 0.8276, including a 16.67 pp sibling regression. Those are real reproduced/recorded results for those arms. B1 used a weighted-field pseudo-document; it was not the CLI's per-field scorer.

B1 Recall@8 was 0.9799, making a +3 pp gate impossible. That gate has been retired. Historical completeness@4 counted grade-3 primary skills only: multi-skill 63/66 = 95.45%. Counting every required grade >= 2 gives 49/66 = 74.24%. These values describe **historical B1**, not the newly repaired CLI. Keep both definitions and their denominators. [Audit data](reports/bakeoff/validation/e13-review-data.json).

### Reranker: eligibility explains part of the regression

In a new diagnostic experiment on 22 stale cases, including 20 answerable, B6 promoted deprecated to rank 1 in 10/22 cases versus B5's 4/22. Applying the same deprecated filter to the scored top-20 lists, without refilling candidates:

| Variant | Hit@1, answerable | nDCG@10 |
|---|---:|---:|
| B5 | 15/20 | 0.8200 |
| B6 default input | 10/20 | 0.7419 |
| B5, deprecated filtered | 16/20 | 0.8453 |
| B6, deprecated filtered | 15/20 | 0.8490 |
| B6, filtered, full body | 16/20 | 0.8803 |

The measured gap shrinks from 25 pp to 5 pp after filtering. Full body plus filtering equalizes hit counts in this small subset; it does not establish generalization. Full body alone did not recover top-1 quality. The checkpoint was already skill-tuned; adaptation to our domain remains a hypothesis.

Default warm scoring median/p95 was 314/342 ms. Full-body median was 595 ms with a long, unstable tail. The default median alone exceeds the whole-hook 300 ms median target. Do not claim unchanged cost across input policies. [Per-case results and timings](reports/bakeoff/validation/e13-reranker-review-data.json).

### Body weights and abstention

The historical B1 body sweep at weights 0/1/2/3/6 gave Hit@1 78.16/87.36/85.63/82.76/80.46%. Body access helped, while simply increasing its weight did not. Body accounted for about 66.9% of weighted token mass in this B1 representation, not 66.9% of score. Neither this sweep nor PR #19's reused fixture independently validates weights for the corrected CLI.

The 46 should-abstain cases remain measurable even when ranking metrics are undefined: false injection, false abstention and coverage have their own denominators. RRF rank scores are not probabilities. A narrow score range alone does not prevent a threshold, but a single-list top-1 always has the same value. Preserve raw lexical/semantic evidence and calibrate a separate decision rule on dev; a repeatedly inspected test is not a fresh holdout.

## 4. Current implementation and next decisions

Main `c08c58c` includes the BM25 fixed-point, zero-weight dense and dependency admissibility repairs. The preceding `c2cc812` already repaired cosine, added `all_required@4` and retired the impossible gate. A [portable CPU audit](../tools/eval/audit_router_contract.py) and [fingerprinted results](reports/bakeoff/validation/router-contract-review-2026-09-05.json) distinguish those revisions.

The BM25 unit defect affected the CLI, **not** the historical float B1 calculation. Route/find now pass an admissible set into selection; direct legacy `select(..., admissible=None)` remains a compatibility path. Skipping an excluded prerequisite does not yet produce an explicit unresolved requirement or guarantee a complete task bundle.

[ADR-0022](adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md) records the proposed separation of admissibility, relevance, composition and sufficiency. The implementation order is:

1. Verify repaired arithmetic and policy against independent references, and measure a new runtime baseline.
2. Run evaluation through the production stages with full per-query provenance and matched budgets.
3. Implement dependency-aware, budget-aware composition with explicit unresolved outcomes and verified AND/OR semantics.
4. Build independent pilot data and calibrate abstention using useful and harmful outcomes.
5. Evaluate additional contextual candidates, reranking and static students as separate hypotheses; admit them for measured product value.
6. Compare no-skill, selected, oracle and wrong-sibling task execution, including cost. If even oracle guidance does not help, investigate content and how the agent uses it before training another retriever.

Sharding and PPR require measured justification. A corpus-derived vocabulary makes a word table corpus-dependent; model revision alone is not its identity. Record content, tokenizer, instructions, truncation, pooling, projection, weighting, quantization and compiler identity. The fast hook remains local and within the single-file stdlib-plus-PyYAML constraint.
