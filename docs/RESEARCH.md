# What the literature says, and what we measured

**Status:** Living synthesis, updated 2026-09-10 against the working tree.
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

## 5. Proof-gated delivery: a new mechanism signal, not a breakthrough

The first complete local-model replay of the sibling-conflict mechanism is in
[`research/e2-qwen-proof-gated-2026-09-09`](../research/e2-qwen-proof-gated-2026-09-09/README.md).
Across 24 skills repeated in three synthetic conflict constructions, Qwen
2.5-7B answered 66/72 source-proof-validated leaf deliveries correctly
versus 57/72 for concatenated leaf-plus-variant context. The paired difference
is **+12.50 percentage points** (9 wins, 0 losses); the skill-cluster bootstrap
interval is [+1.39, +26.39] pp. A separate deterministic contract replay
loaded one complete proof and sent all 12 malformed/stale/conflicting
mutations to `ASK`.

A separately frozen query-only replication with Qwen2.5-1.5B is in
[`research/e2-qwen15-query-window-2026-09-09`](../research/e2-qwen15-query-window-2026-09-09/README.md).
It selects evidence from question overlap and generic field markers without
reading frozen answer values. Across the same 24 synthetic skills and three
conflict constructions, proof-load scored 27/72 versus 9/72 for concatenation:
**+25.00 pp** paired, with skill-cluster bootstrap [+6.94,+44.44] pp. This is a
cross-check of the mechanism, not a pooled estimate: it uses a smaller model,
the same exposed corpus and a compact evidence heuristic. It does not remove
the need for independent annotations, an unseen repository or execution-level
outcomes.

This result supports finishing proof-gated delivery, provenance and safe
abstention as the current product and paper direction. It does not establish
general retrieval improvement or user benefit: the corpus is synthetic, the
context is an evidence-window construction, one model and greedy pass were
used, and the scorer checks numeric values rather than independently reviewed
semantic actions. The corrected Claude E2 is still unavailable after a weekly
quota failure, and URCT-2 remains annotation-gated. The publication gate is a
complete E2 plus two independent URCT-2 assessments and at least one held-out
real repository with execution-level outcomes.

The LLM ascent path now emits the same safety state: generated abstract cards carry a
provisional `source_proof` with the contributing URNs and broad hash-bound `source_refs`, but
`verified:false`. They remain reviewable and searchable, but proof-gated USE returns `ASK` until
an importer or owner binds the claims to exact source ranges and the immutable snapshot,
revision and body hash. This closes the gap between an attractive generated pyramid and a
source-authorized delivery; it is an implementation safeguard, not an additional performance
claim.

The first positive automatic-ascent signal is the staged Qwen2.5-7B pilot in
[`research/ascend-qwen7b-staged-map-2026-09-09`](../research/ascend-qwen7b-staged-map-2026-09-09/README.md).
The model emitted only bounded child/summary/source atoms; deterministic code
assembled the map and the normal gate checked it. Four of eight parent scopes
passed, with 5/5 exact hash-bound references and no unknown URNs. Four larger
scopes failed format or coverage. This is structural feasibility for the
pipeline, not semantic or task evidence. Recursive fan-out plus independent
review is now the most valuable next experiment.

A forced-create ablation in
[`research/ascend-qwen7b-forced-map-2026-09-09`](../research/ascend-qwen7b-forced-map-2026-09-09/README.md)
also failed: Qwen2.5-7B produced only 3/8 parseable outputs and 0/8 complete
map objects when `no_change` was forbidden. This rules out a trivial prompt
fix. Automatic pyramid generation therefore needs staged bounded extraction
and a validator loop before it can be evaluated as a method; the current
evidence supports only the proof-gated delivery mechanism.

The novelty boundary is now explicit in light of newer adjacent work.
[SURE-RAG](https://arxiv.org/abs/2605.03534) already treats evidence sufficiency
as a set-level support/refute/insufficient decision with abstention, and
[SkillTrace](https://arxiv.org/abs/2608.05204) already audits multi-trace skill
provenance. A publishable Guidefold contribution therefore cannot be “RAG with
abstention” or provenance logging in isolation. The remaining testable claim is
the skill-specific authorization boundary: immutable snapshot/revision/body
binding plus hierarchical scope and dependency-closure checks, with a
fail-closed `ASK` that prevents an adapter from receiving any conflicting body.
The working manuscript [Context Is Not Control](https://symbolicsuite.com/context-is-not-control)
also names source admissibility as a general failure mode, so our paper must
state clearly what is specific to executable skills: hierarchical scope,
revision and closure are checked before the harness sees the body, rather than
treated as another prompt instruction.
The two E2-Qwen signals are useful only if that narrower boundary survives
independent semantic labels, an unseen real repository and execution-level
outcomes. The query-only replication increases confidence that the direction
is not solely caused by selecting lines with known answer values, but it does
not establish a general model-independent effect.

### 5.1 Literature update — the novelty boundary is narrower

The current literature now includes several close systems. [Corpus2Skill](https://arxiv.org/abs/2604.14572)
compiles bounded corpora into navigable hierarchies and reports that navigation
has a scope-dependent trade-off against flat retrieval. [SkillRAE](https://arxiv.org/abs/2605.10114)
already combines a multi-level skill graph, selected-subunit evidence export
and compact grounded context compilation. [SkillCorpus](https://arxiv.org/abs/2607.15557)
adds corpus curation, retrieval models and multi-harness end-to-end results.
[SkillResolve-Bench](https://arxiv.org/abs/2606.10388) directly measures harmful
same-capability sibling exposure. [SRA-Bench](https://arxiv.org/abs/2604.24594)
separates retrieval, incorporation and execution, showing why a ranked card is
not sufficient evidence of useful skill use.
[SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) provides a particularly
relevant warning: on fixed real repositories, most tested skills produced no
pass-rate gain and some harmed performance when their guidance conflicted with
the target version. [GitSkills](https://arxiv.org/abs/2608.10906) also shows that
the public skill population is millions of files, with substantial reuse and
lineage concerns.

These works rule out claiming hierarchy construction, context compression,
generic provenance, sibling filtering or Recall@k as the Guidefold novelty.
The remaining candidate is the **source-grounded authorization boundary**:
immutable snapshot/revision/body binding plus hierarchical scope and dependency
closure checks, with fail-closed `ASK` before an adapter receives any
conflicting or stale body. The full comparison matrix and the preregistered
next test are in [`research/literature-update-2026-09-09`](../research/literature-update-2026-09-09/README.md).

The newer [SkillCenter](https://arxiv.org/abs/2607.07676),
[GraSP](https://arxiv.org/abs/2604.17870),
[HiSkill](https://arxiv.org/abs/2607.25853),
[AIP](https://arxiv.org/abs/2606.04781) and
[SkillAlchemy](https://arxiv.org/abs/2608.23417) papers occupy exact source
quotations, typed execution graphs, hierarchical subgraph execution and
source-grounded procedure admission. They make the same boundary even more
specific: the proposed contribution has to stop a generated or stale skill
before the harness receives its body, using immutable monorepo scope, revision
and dependency evidence.

Sharding and PPR require measured justification. A corpus-derived vocabulary makes a word table corpus-dependent; model revision alone is not its identity. Record content, tokenizer, instructions, truncation, pooling, projection, weighting, quantization and compiler identity. The fast hook remains local and within the single-file stdlib-plus-PyYAML constraint.

### 5.2 Local ascent feasibility pilot: a negative structural result

The first frozen local-model ascent pilot is in
[`research/ascend-qwen15-structural-2026-09-09`](../research/ascend-qwen15-structural-2026-09-09/README.md).
Across 16 CUDA calls on eight real parent scopes, Qwen2.5-1.5B produced
parseable JSON in 10 cells (62.5%), chose `no_change` in eight, and produced
zero cards that passed the create/edit gate. The remaining cells were
truncated at the 512-token cap or omitted the requested kind. A compact,
single-kind ablation improved neither parse rate (5/8) nor accepted-card rate
(0/8), although it reduced wall time. The result is a useful feasibility
boundary for the proposed automatic pyramid, not evidence of semantic quality
or a breakthrough. The next model-facing test should use staged context and
constrained decoding or a larger checkpoint, then independent semantic labels.

The follow-up scale ablation in
[`research/ascend-qwen7b-compact-ablation-2026-09-09`](../research/ascend-qwen7b-compact-ablation-2026-09-09/README.md)
used the same compact prompt with Qwen2.5-7B. It parsed 8/8 responses and
returned the requested map object in 8/8, but selected `no_change` in every
cell and still produced zero accepted cards. Model scale fixes an operational
JSON failure without demonstrating automatic synthesis. The scientific path
remains proof-gated authorization plus independently reviewed semantic
outcomes; automatic LLM ascent is currently a product experiment, not a
claim.

The edgewise recursive pilot then removed the remaining fan-out bottleneck:
[`research/ascend-qwen7b-edgewise-2026-09-09`](../research/ascend-qwen7b-edgewise-2026-09-09/README.md)
evaluated all 16 parent→child edges. Every edge parsed and passed subtree
source checks; all eight parent maps passed the production gate with 20/20
exact source hashes. This is the first full-tree structural feasibility signal
for the proposed staged method. It still lacks independent semantic labels and
held-out execution outcomes, so it is not a retrieval or user-benefit claim.
The accompanying lexical sanity audit has mean source-token overlap 0.880
(minimum 0.667), but is explicitly not a semantic judge.
The calibrated model audit found one semantic risk: the `atlas.identity` parent summary combined
deprecated legacy session auth with active RBAC and was judged contradictory. The production
ascent gate now rejects claims citing any deprecated source, forcing owner review. This converts a
discovered failure mode into a deterministic safety invariant; it still does not replace semantic
labels.

The strict and calibrated model audits are retained in
[`research/ascend-edgewise-qwen15-judge-2026-09-09`](../research/ascend-edgewise-qwen15-judge-2026-09-09/README.md)
and [`research/ascend-edgewise-qwen15-entailment-2026-09-09`](../research/ascend-edgewise-qwen15-entailment-2026-09-09/README.md).

The subsequent deprecated-source safeguard is a post-hoc correction: replaying
the eight frozen cards through the strengthened gate accepts 7/8, rejecting
only the `atlas`→`atlas.identity` card that mixed a deprecated source with
RBAC. The original 8/8 structural count is retained as the pre-change run;
7/8 is the current safety-policy outcome.

The public-repository replication in
[`research/ascend-cloudflare-agents-edgewise-2026-09-09`](../research/ascend-cloudflare-agents-edgewise-2026-09-09/README.md)
did not transfer the full-tree result: empty intermediate scopes caused
grandchild selection. A same-source collapse-empty ablation is recorded in
[`research/ascend-cloudflare-collapsed-edgewise-2026-09-09`](../research/ascend-cloudflare-collapsed-edgewise-2026-09-09/README.md).
It still produced only 3/5 valid edges and 1/3 complete, gated parent maps.
This is evidence that hierarchy representation is a real failure boundary, not
evidence that collapsing empty scopes solves it. Explicit scope-boundary
metadata or constrained decoding is now required before a general ascent claim.

The external SkillRouter subset adds a separate body/provenance control:
[`research/skillrouter-proof-gated-subset-2026-09-09-r2`](../research/skillrouter-proof-gated-subset-2026-09-09-r2/README.md)
uses 75 expert tasks and 5,196 frozen candidates at a 1,024-token limit. The
released body-aware encoder reaches 73.33% Hit@1, 77.09% Recall@10 and 60.00%
FullCoverage@10, versus 66.67%, 74.97% and 54.67% for metadata-only input.
The paired exploratory intervals include zero. The fixture source-proof policy
returns `ASK` on 20.00% of body-aware top-1 choices and records zero unproven
loads; this measures authorization behavior separately from ranking quality.
The subset omits 358 degraded IDs named by relevance metadata, so it cannot
support a universal safety or retrieval claim.
An exploratory first-proof policy that scans the top three candidates raises
correct loads to 80.00% with 13.33% `ASK`; scanning ten raises correct loads to
85.33% with 5.33% `ASK`, while wrong proof-bearing loads rise from 6.67% to
9.33%. This is a candidate rank-budget tradeoff for a future real-provenance
test, not a production default.

The synthetic sibling stress test
[`research/skillrouter-proof-gated-synthetic-siblings-2026-09-09`](../research/skillrouter-proof-gated-synthetic-siblings-2026-09-09/README.md)
materializes the 358 degraded IDs missing from the public shards. Full-body
top-1 selects a synthetic degraded copy in 64.00% of 75 tasks; strict proof
delivery asks on 82.67% and makes zero unproven loads. A rank-3 proof scan
recovers 77.33% correct loads with 16.00% `ASK` and 6.67% wrong proof-bearing
loads. This is a synthetic mechanism result; real source revisions and human
conflict labels remain mandatory.

### 5.3 Frozen confirmatory direction: proof-budgeted skill delivery

The next research sequence is frozen in
[`research/proof-budgeted-skill-delivery-2026-09-09`](../research/proof-budgeted-skill-delivery-2026-09-09/README.md).
It treats retrieval as candidate generation and source authority as a separate
pre-context decision. The proposed PBSD policy scans a bounded ranked set and
delivers only a candidate whose immutable revision, body hash, leaf scope,
dependency closure and conflict state all pass; otherwise it returns `ASK`.

The acronym `PBSD` is already used by an unrelated arXiv training method,
*Privileged Bayesian Self-Distillation for Long-Horizon Credit Assignment*
([arXiv:2606.09348](https://arxiv.org/abs/2606.09348)). The manuscript name for
this project will therefore be **Proof-Gated Skill Delivery (PGSD)**. The frozen
research directory keeps `PBSD` for reproducibility and hash stability.
The rank budget is selected once on source-family-disjoint calibration data to
maximize delivery coverage subject to a one-sided 95% exact upper bound of 5%
on harmful loads.

The confirmatory corpus must contain actual repository revisions or sibling
scopes, two independent labels and repository-level splits. The primary result
is harmful risk at useful delivery coverage, followed by held-out agent task
execution; Recall@10 is secondary. The paper gate additionally requires at
least 60% delivery coverage, execution non-inferiority, a 50% reduction in
harmful task regressions and replication across two model and repository
families. Until those gates pass, PBSD remains a breakthrough candidate rather
than a completed discovery.

#### Label-free systems track

There is a publishable track that does not require human semantic labels, but it
must make a narrower claim. The proposed theorem is: for a fixed immutable
snapshot, `LOAD` is source-sound (every accepted reference resolves to bytes in
that snapshot and its declared line range), snapshot-consistent (body, proof and
source cannot come from different revisions), and non-interfering (a mutation in
an unrelated sibling cannot change a leaf's decision). The abstract meet adds a
fourth invariant: a parent claim is promoted only when every descendant resolves
to the same value; disagreement is excluded or `ASK`, never averaged by the
LLM. These are properties of the resolver and byte store, so they can be proved
by case analysis and exhaustively tested without deciding whether a prose claim
is semantically useful.

The protocol is to enumerate all finite authority states of generated sibling
trees (active, deprecated, stale, conflicting, missing and reordered), replay
every state through the Go gate, and then run the same mutation suite on every
leaf of the frozen public repositories. Report exact invariant violations,
context bytes, number of cards, fetch latency and `ASK` rate against flat
concatenation and retrieval-only delivery. Real repository trees supply scale;
the generated states supply exhaustive coverage. An objective harness check
(parser, type checker or repository test) may measure whether a delivered card
is executable, but no semantic benefit or user productivity claim is allowed on
this track.

This can support a formal/systems or artifact paper about **PGSD and the
scope-authority lattice**. It cannot replace E2/URCT-2 for the stronger claim
that the automatically generated pyramid improves agent task success. The
product claim is nevertheless clear now: Guidefold finds the right level of
repository guidance, keeps parent context compact, and refuses to inject a
stale or conflicting rule. That is a sellable governance and context-cost
benefit; task-success uplift remains a measured future outcome.

The first finite label-free replay is now recorded in
[`label-free-matrix-results.json`](../research/pyramid-claim-lattice-2026-09-08/label-free-matrix-results.json)
and regenerated by [`label_free_matrix.py`](../research/pyramid-claim-lattice-2026-09-08/label_free_matrix.py).
It covers 14 structural cases: three fresh/non-interfering `LOAD` cases and
eleven targeted leaf, child-card, commitment, identity and presentation
mutations. All 14 reached their predeclared outcome (`14/14`); each stale or
tampered proof asked, while an explicitly requested unaffected claim and a
presentation-only mutation still loaded. This is repeatable mechanism evidence
for the recursive proof boundary, not a semantic label, task-success or user-
productivity result. The fixture remains small, so the next label-free gate is
the same matrix over frozen public-repository snapshots and a Go/CLI replay.

The Go delivery path now accepts the same recursive boundary as an additive
proof field: `claim_refs` bind a parent claim to a child card's revision,
claim digest and commitment. The service checks the child proof, scope or
approved `refines` edge, cycle freedom and all nested references before source
byte verification; the legacy proof shape remains valid. This closes the main
implementation gap between the research hierarchy verifier and PGSD delivery,
while the recursive integration test keeps the method claim structural.

The product-scale check is now reproducible from the frozen M1 artifact rather
than a new repository sample. Ten public repositories contribute 30,555 source
leaves; nearest-wins counts 24,705 (80.85%) above 8,000 characters, 24,357
(79.72%) above 12,000 and 21,360 (69.91%) above 32,768. A repository-equal
bootstrap gives [27.95%, 82.79%] for the 12,000-character share and
[1.62%, 56.45%] for the 32,768-character share. The interval is intentionally
wide because repositories differ sharply; the pooled result is not a claim
about a random population. The source, seed and per-repository rows are in
[`public-repo-scale-results.json`](../research/pyramid-claim-lattice-2026-09-08/public-repo-scale-results.json)
and are regenerated by its script. This supports a real context-scale pain
point for the product, while semantic quality and task benefit remain open.

The structural gate also passed an exhaustive finite replay of 1,373 states
(all combinations of seven child states across three branches and four root
states, plus an unrelated-source control): 2/2 expected loads and 1,371/1,371
expected `ASK` outcomes. This is label-free mechanism evidence for recursive
freshness, scope and commitment handling, not evidence that an automatically
generated claim is semantically correct. The replay and limitations are in
[`exhaustive-lattice-results.json`](../research/pyramid-claim-lattice-2026-09-08/exhaustive-lattice-results.json).

This formulation is narrower than the latest adjacent work. Field-Aware Agent
Skill Retrieval ([arXiv:2608.02880](https://arxiv.org/abs/2608.02880)) learns
over field-level sparse and dense scores, but does not decide whether a source
revision is authorized for a monorepo leaf. Judge, Retrieve, or Abstain
([arXiv:2608.17994](https://arxiv.org/abs/2608.17994)) supplies the relevant
finite-sample risk-control pattern, while Learning When to Remember
([arXiv:2604.27283](https://arxiv.org/abs/2604.27283)) treats memory injection
as a risk-sensitive action. PBSD must therefore show value from its specific
source/scope/revision/closure authority relation, rather than claim abstention
or calibrated risk control as new by themselves.

The 2026-09-09 related-work scan adds four direct adjacency checks. SkillComposer
([arXiv:2606.32025](https://arxiv.org/abs/2606.32025)) jointly predicts a skill
subset, count and order and reports downstream task gains; CaSKG
([arXiv:2608.25500](https://arxiv.org/abs/2608.25500)) calibrates graph edges
with counterfactual probes for executable retrieval; Skill-Use
([arXiv:2608.04828](https://arxiv.org/abs/2608.04828)) evaluates trigger,
procedure compliance and boundary adherence in real-file tasks; and
*Demystifying Agent Skills* ([arXiv:2608.14036](https://arxiv.org/abs/2608.14036))
measures retrieval brittleness and procedural anchoring. These papers make a
new retrieval, composition or generic skill-use claim non-novel. Their stated
methods do not define a deterministic source-authority decision that binds a
delivered card to the exact monorepo scope, immutable revision, body hash and
source line ranges, with conflict or missing evidence producing `ASK`. PGSD
must be positioned and tested as that authorization boundary, with downstream
execution and harmful-load risk as primary outcomes.

The first C0 mining pass is now complete under the frozen repository manifest.
Twelve public monorepositories, each pinned to its earlier M1 revision, yielded
373 unique instruction-body transitions in 1,000-commit histories. Of these,
176 replace one set of control-bearing lines with another, 82 contain a
version/deprecation signal, 263 a normative signal and 266 a scope signal.
This establishes that a real-source candidate corpus is feasible; it does not
establish 373 valid conflict cases. Every row remains unlabelled in eight
direction-blinded packets with two empty reviewer forms. Semantic admission
still requires two independent people and adjudication before C1 may run.

Before semantic admission, the 176 bidirectional rows now support a separate
structural replay. For each actual commit/path/hash pair, the resolver was
instantiated with a deprecated old revision and an active new revision; the
same pair was then replayed as an equal-scope conflict and as a more-specific
leaf override. All six checks passed for all 176 pairs across 11 repositories,
including rejection of stale cards and preservation of root-scope conflicts.
This uses real revision metadata but treats line excerpts only as opaque
values, so it cannot say which policy is helpful or harmful. The exact output
is [`c0-transition-replay-results.json`](../research/proof-budgeted-skill-delivery-2026-09-09/c0-transition-replay-results.json)
and the replay is regenerated by its script.

An exact-risk re-analysis also narrows the mechanism. None of the earlier
first-proof rank budgets meets the frozen 5% risk and 60% coverage gate. On the
external subset, rank three accepts 65/75 cases with five wrong proof-bearing
loads: 7.69% observed harmful risk and a 15.50% one-sided 95% upper bound. The
synthetic rank-one arm has zero observed harmful loads but accepts only 13/75,
with a 20.58% risk upper bound. A provenance-bearing prefix is therefore not
the proposed method and cannot support a safety claim.

The new research-only reference operator is a scope-authority lattice. For
each claim at a target leaf it selects the most specific active, immutable
source; equal-precedence disagreement returns `ASK`. A delivered card must
match both the resolved value and authoritative source set. Automatic ascent
uses the corresponding meet: only claims with one resolved value across every
descendant leaf may enter an abstract parent. Eight deterministic tests cover
leaf override, deprecated sources, equal-scope conflict, stale root proofs,
dependency closure, sibling isolation and invariant-only promotion. This is
algorithmic feasibility, not yet evidence on human-labelled conflicts.

A local Qwen2.5-1.5B auxiliary screen then processed all 373 blinded revision
pairs in 362.5 seconds. It produced 320 closed-schema outputs (85.79%) and
prioritized 179 pairs; the independent bidirectional-diff signal prioritized
176, with only 70 overlapping. The 285-item union orders human work but does
not exclude any row. Model suggestions remain hidden from both reviewer forms,
and the human admission count remains zero.

The next authoring experiment rejected free-form task synthesis by the small
model: only 1/373 drafts passed a frozen contract requiring a neutral task,
different actions and two exact source quotes. Replacing copied quotes with
extractive line identifiers raised source-valid output to 45/176 (25.57%). A
controlled serialization ablation using `A=... B=... K=...` instead of JSON
raised it again to 65/176 (36.93%), +11.36 percentage points. The two anchor
runs overlap on 27 cases and produce an 83-case union.

This is an engineering and corpus-authoring result, not semantic evidence.
Inspection shows that some source-valid pairs concern different decisions.
Accordingly, the model can propose immutable evidence identifiers but cannot
admit a case or author an authority label. The 83 proposals are isolated in a
phase-2 packet that two reviewers may open only after completing the original
blind semantic screen. Human-accepted tasks and C1 admissions remain zero.

### 5.3 Pi/Go blind harness: next retrieval gate

The new [Pi + Go hierarchical harness](../research/pi-hierarchical-harness-2026-09-10/README.md)
freezes a 10,123-card SKILLRET train snapshot and 100 DEV tasks. It compares one flat Go SEARCH
with top-down scope descent and an explicit bottom-up leaf fan-out, then hydrates each selected
card through SEARCH→USE. Golden IDs stay in a separate evaluator file; the service and Pi receive
query text only. The runner records scope choices, request counts, latency, revisions, body hashes,
Pi JSON events and bridge traces. This is the right next product experiment because it tests the
actual 12k-card retrieval path and harness contract. The deterministic Go replay is now complete:
flat scored Hit@1 .57, Recall@10 .90 and Complete@4 .32; corrected greedy top-down scored
.57/.77/.26; beam top-down .18/.86/.29; bottom-up .05/.30/.07. The hierarchy replay therefore
exposes a real algorithmic failure boundary: naive descent loses multi-scope gold and raw-score
merging lets narrow scopes overwhelm the global ranking. These numbers are DEV evidence, not a
breakthrough claim; the next method must pre-register rank fusion or a learned scope router and
replay on a held-out split.

The first Pi replay used the same frozen inputs for 40 blind sessions (10 tasks × 4 strategies).
All 40 sessions reached `agent_end`; 34 retained bridge traces. In every retained trace the first
bridge operation was SEARCH, and 65 of 66 USE calls returned hydrated bodies; one stale/unknown
URN returned 404. No `ASK` was observed because that run used `legacy` delivery. The runner now
persists the complete redacted Pi JSONL event stream and accepts `--delivery-policy proof_gated`.
A six-session capture after this change reached the provider but was rejected before the first
tool call by `usage_limit_reached`, so it is recorded as an infrastructure-negative result rather
than folded into retrieval metrics. The detailed behavior audit is in
[`AGENT-BEHAVIOR.md`](../research/pi-hierarchical-harness-2026-09-10/AGENT-BEHAVIOR.md).
The event and delivery audit rules are frozen in
[`PROTOCOL-PI-R2.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-PI-R2.md).
An independent fresh SEARCH→proof-gated USE smoke returned HTTP 200 with `delivery.action=ASK`,
`reason=proof_missing` and zero body bytes for a card without source proof. This verifies the
service-side fail-closed path; Pi’s model-side response to `ASK` remains unmeasured until a provider
quota is available.

R4 then froze a fixed-beam reciprocal-rank-fusion operator over the same seven SEARCH responses:
the root ranking has weight four (the delivery cap) and every scoped ranking has weight one, with
the fixed RRF constant 60. On the same 100 DEV tasks, `beam_rrf` reached Hit@1 .57, Recall@10
.90 and Complete@4 .33, versus flat .57/.90/.32 and raw-score beam .18/.86/.29. The paired
Complete@4 difference was one win, zero losses and 99 ties; a 20,000-draw task bootstrap was
[0, +4] percentage points. The effect is too small to call a breakthrough, while the cost is
about 2.4× flat latency (mean 180 ms vs 74 ms) and 11 vs 5 total requests. The result validates
the diagnosis that raw cross-scope scores are the wrong merge signal, but it also sets a hard next
bar: a learned or source-calibrated scope router must improve held-out coverage enough to justify
the added calls, with RRF retained as the preregistered non-learned baseline.

### 5.4 Query-time Qwen routing over the generated pyramid

The next controlled router test used the byte-identical taxonomy-anchored map
from the preceding run and gave a local Qwen2.5-7B-Instruct model the 24 valid
scope summaries for each of the same 100 blind queries. The model returned up to
two majors and four leaves using canonical scope names; all 100/100 decisions
passed schema and scope validation. Gold URNs were not sent to the model or
service. The deterministic service still executed one root, two major and up to
four leaf searches, merged them with the frozen RRF rule, and hydrated four
cards.

The full replay scored Hit@1 .40, Recall@10 .90 and Complete@4 .25, with 400/400
successful `USE` calls and a median end-to-end latency of 207 ms. Against the
map-only lexical router (.37/.90/.31), the LLM router gained 3 pp Hit@1 but lost
6 pp Complete@4. Against the deterministic flat baseline (.57/.90/.32), it lost
17 pp Hit@1 and 7 pp Complete@4; against `beam_rrf` (.57/.90/.33), it lost 17
pp and 8 pp respectively. The query classification stage took 715 seconds on
the local GPU for 100 tasks, before service requests. These are paired DEV
diagnostics, not evidence of a generated-pyramid improvement.

An eight-task smoke initially returned natural-language leaf labels rather than
scope identifiers and therefore yielded zero valid decisions. The interface
amendment added explicit allowed-name lists; the separated rerun then reached
8/8 valid decisions. Both outputs are retained, with the failed smoke excluded
from the full comparison. The protocol, amendment, map copy, query decisions,
raw redacted model outputs and report are in
[`llm-pyramid-router-2026-09-10`](../research/llm-pyramid-router-2026-09-10/),
with the full replay under the corresponding `.guidefold/checks` directory.

The result narrows the research direction. A language model can serialize a
valid hierarchical routing decision over generated summaries, but the current
map abstractions and query-time classifier do not improve retrieval and add
substantial compute cost. The strongest current claim remains the deterministic
proof/authority boundary and the small RRF merge diagnostic; an automated
pyramid needs held-out maps, semantic labels and a better calibrated router
before it can support a task-success or novelty claim.

### 5.5 Routing ablations and replication splits

Several follow-up ablations now separate the remaining failure modes. Appending
generated leaf terms, definitions or abstract prefixes to scoped queries did not
improve the Qwen route: the three arms scored respectively .39/.90/.27,
.40/.90/.28 and .38/.90/.28 (Hit@1/Recall@10/Complete@4). A deterministic
diversity sampler for map generation reduced map validity to 21/25 nodes and
gave .30/.90/.28. A wider 3×3 beam kept .57/.90/.33, equal to the fixed 2×2
beam, while increasing the median request count from 11 to 13. A full-corpus
TF-IDF centroid map was complete (25/25 nodes) but scored .37/.90/.32.

The first held-out supervised router used the 63,158 remaining labelled
training queries (after removing the original 100 DEV queries and duplicate
texts). Multinomial NB plus root-preserving delivery scored .61/.90/.32 on the
original DEV split, versus flat Go .57/.90/.32. The paired Hit@1 difference was
6 wins, 2 losses and 92 ties; a 20,000-draw bootstrap was [-1, +10] pp, so the
signal is not yet statistically secure. On the disjoint SHA-selected split2,
the same protocol scored .52/.86/.36 versus flat .55/.86/.36, so the +4 pp
effect did not replicate.

Replacing NB with held-out nearest-query voting scored .46/.90/.31. A TF-IDF
class-centroid router had high scope agreement in an offline diagnostic but
scored only .44/.90/.32 on DEV and .43/.86/.34 on split2 after real scoped
SEARCH and RRF. These paired service replays show that scope classification
accuracy does not translate into better card ranking; the fixed flat Go path
remains the strongest retrieval baseline. Protocols and raw reports are under
[`pi-hierarchical-harness-2026-09-10`](../research/pi-hierarchical-harness-2026-09-10/)
and the corresponding `.guidefold/checks` directories.

### 5.6 Qwen reranking with a root anchor: 1,000-query replication

R13.2 was replayed on a larger SHA-selected holdout of 1,000 queries from the
same pinned SKILLRET train pool. The selection excluded the original DEV tasks,
the earlier R10 split, and duplicate query text; the frozen 10,123-card
snapshot was byte-identical. Gold URNs remained evaluator-only. A fresh flat Go
run completed all 1,000 searches and 4,000 `USE` requests without HTTP errors.

The flat baseline scored Hit@1 .577, Recall@10 .885 and Complete@4 .289. The
Qwen 7B reranker saw only the task and the ten flat candidate cards, returned a
valid decision for 1,000/1,000 tasks, and scored .525/.885/.302. The
`qwen_root_anchor` arm preserved the original flat top-one and reordered the
remaining candidates; it scored .577/.885/.309. Thus root anchoring produced a
paired Complete@4 gain of +2.0 percentage points (27 wins, 7 losses, 966 ties),
with a 20,000-draw paired bootstrap 95% interval of [+0.9, +3.1] pp. An
exploratory paired sign test on the 34 discordant tasks gives two-sided
`p=0.00082`. The gain did not change Hit@1 or Recall@10. The unconstrained
reranker reduced Hit@1 by 5.2 pp (bootstrap [-8.3, -2.0] pp), which is why the
root anchor is part of the hypothesis rather than an optional presentation
detail.

The model stage took 547.7 seconds on the RTX 4090, while flat Go search had
p50 78 ms and p95 99 ms per task. This is therefore a promising shadow or
batch reranking signal, not yet a default production route. The holdout shares
the source corpus with training and has no human task-execution labels; the
result supports a repeatable retrieval-completeness hypothesis, not a universal
skill-pyramid or user-success claim. Full paired rows, hashes and bootstrap
code are retained in
`.guidefold/checks/pi-hierarchical-harness-2026-09-10-r13-large-comparison.json`,
with the raw R13 report in the neighbouring `r13-large` directory.

### 5.7 External SKILLRET test-corpus replication

To test transfer rather than another draw from the same train pool, the exact
R13.2 method was run against the corpus's disjoint `test` split. The test
snapshot contains 6,006 skill cards whose IDs have zero overlap with the 10,123
train cards; the 4,392 test queries also have zero ID overlap with train. The
1,000 evaluated queries were selected by fixed SHA-256 order. Their query
generator is different as well (the test metadata reports Claude Opus 4.6,
whereas train reports Qwen3.5-122B-A10B). A separate Go API process served
`skillret-test` on port 8766; the existing `meridian` process and snapshot were
left untouched.

The fresh flat Go baseline scored Hit@1 .265, Recall@10 .638 and Complete@4
.257. With the same ten-candidate Qwen2.5-7B prompt, plain reranking scored
.366/.638/.323. The root-anchor arm, which pins the original flat top-one and
lets Qwen reorder the other nine, scored .265/.638/.324. Relative to flat,
root anchoring improved Complete@4 by +6.7 pp (68 wins, 1 loss, 931 ties), with
a 20,000-draw paired bootstrap 95% interval of [+5.2, +8.3] pp; the
exploratory paired sign test is two-sided `p=2.4e-19`. Hit@1 and Recall@10 are
exactly preserved by construction. Plain reranking's +10.1 pp Hit@1 and +6.6
pp Complete@4 are also positive (paired Complete@4 bootstrap [+5.0, +8.3] pp),
but it does not provide the safety property of preserving the strong flat
first result.

This is the strongest current retrieval result: the Complete@4 gain transfers
from a train holdout (+2.0 pp) to a disjoint skill and query corpus (+6.7 pp),
while the anchor prevents the reranker's Hit@1 regression seen on the larger
train holdout. It remains a method-level retrieval result, not proof of user
success, execution correctness, proof authorization or a universal generated
pyramid. The Qwen stage took 3,150.6 seconds for 1,000 tasks on the RTX 4090
(about 3.2 seconds per task), so production use requires distillation, caching,
or an asynchronous shadow path. Inputs, service health, reports and paired
hashes are retained under
`.guidefold/checks/pi-hierarchical-harness-2026-09-10-r13-external-test*`.

For orientation only, pooling the two disjoint populations gives 95 paired
wins, 8 losses and 1,897 ties: +4.35 pp Complete@4 with a descriptive paired
bootstrap interval of [+3.4, +5.35] pp. The split-specific estimates above
remain the primary report; this pool is not a substitute for a third corpus.

### 5.8 R14 budget-gated anchor: preregistered transfer block

R14 turns the observed anchor behavior into a fixed, budget-derived rule. Let
`r` be the zero-based rank of flat Go's top-one in the Qwen order. With a
four-card delivery budget, preserve that top-one when `r < 4`; when `r >= 4`,
allow the Qwen order to replace it. The threshold is the product's existing
delivery budget, so it was not fitted to gold labels. Applying it to the
retained R13 outputs was exploratory; the next block was frozen before its
model replay.

The confirmatory block is the next 1,000 SHA-ordered queries from the disjoint
SKILLRET test split (`offset=1000`), using the same 6,006-card Go snapshot,
candidate budget, Qwen prompt and decoder. Flat scored Hit@1 .280, Recall@10
.617 and Complete@4 .274. R14 scored .329/.617/.325. The paired Hit@1 gain is
+4.9 pp (55 wins, 6 losses, 939 ties; 20,000-draw bootstrap 95% interval
[+3.4, +6.5] pp). The paired Complete@4 gain is +5.1 pp (57 wins, 6 losses,
937 ties; interval [+3.6, +6.6] pp). Recall@10 is unchanged. One malformed Qwen
decision fell back to the flat order; all other decisions were valid.

This is a stronger method-level result than fixed anchoring: across two
disjoint test blocks the budget gate keeps the baseline's candidate recall,
improves bundle completeness, and can recover Hit@1 when the model strongly
disagrees with the sparse prior. The model stage took 6,038.8 seconds for this
block, so the method is still a teacher/shadow operator. A credible paper now
has a specific hypothesis and transfer evidence, but still needs a cheaper
distilled reranker and execution-level or human labels before claiming product
impact or a general skill-pyramid breakthrough. The frozen protocol and full
paired artifact are in
[`PROTOCOL-R14-BUDGET-GATE.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R14-BUDGET-GATE.md)
and `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r14-external-test2-budget-comparison.json`.

Descriptively combining the first external block (where the rule was
retrospective) with this confirmatory block gives +5.85 pp Complete@4 over
2,000 test queries (126 wins, 9 losses; bootstrap interval [+4.75, +7.00] pp).
This pooled number is retained for power planning only; the second block's
pre-frozen estimate is the confirmatory result.

### 5.9 R15: distilling the LLM reranker into a metadata-only student

The Qwen stage in R13/R14 is too slow for interactive retrieval, so the next
experiment tested whether its useful ordering signal can be distilled into a
small local ranker. The student never sees evaluator labels. It learns pairwise
preferences from the Qwen order on the 1,000-query train holdout, while its
features use only retrieval-time metadata: TF-IDF similarity to the card's name,
description, digest and scope, inverse flat rank, name and scope overlap, and
scope depth. The vocabulary is fitted on the train corpus only. At evaluation it
receives the ten candidates already returned by flat Go SEARCH; no online Qwen
call is made.

On the first 1,000-query block of the disjoint SKILLRET `test` corpus, the direct
student improved Hit@1 from .265 to .305 (+4.0 pp; paired bootstrap 95% CI
[+2.8, +5.3]) and Complete@4 from .257 to .322 (+6.5 pp; CI [+5.0, +8.1]);
Recall@10 stayed .638. It won on 41 and lost on 1 Hit@1 pair, and won 65 and
lost 0 Complete@4 pairs. On the next 1,000 SHA-ordered test queries, held out
from that replay, it improved Hit@1 from .280 to .318 (+3.8 pp; CI [+2.6,
+5.1]) and Complete@4 from .274 to .319 (+4.5 pp; CI [+3.2, +5.9]); Recall@10
stayed .617. The second block had 40/2 Hit@1 wins/losses and 47/2
Complete@4 wins/losses. Both replays took about 12 seconds of CPU time after
the teacher artifacts existed, compared with roughly 6,039 seconds for the
Qwen stage on the second 1,000-query block.

On a third untouched 1,000-query block (`offset=2000`), the flat baseline was
.275/.611/.270 and the direct student was .306/.611/.328: +3.1 pp Hit@1 (CI
[+1.8, +4.5]) and +5.8 pp Complete@4 (CI [+4.2, +7.4]), with 39/8 and 64/6
paired wins/losses. The student replay again took about 14 seconds of CPU time.

Descriptively pooling all three disjoint blocks gives +3.63 pp Hit@1 (120/11
wins/losses; bootstrap CI [+2.9, +4.4]) and +5.60 pp Complete@4 (176/8;
CI [+4.77, +6.47]) over 3,000 queries. The block-specific estimates remain
primary because the corpus is one benchmark family.

The R14 budget gate preserved the flat top-one and therefore preserved Hit@1
and Recall@10 exactly in these student replays, while retaining the Complete@4
gains (+6.5 pp and +4.5 pp). The direct student is the stronger retrieval arm,
with only one or two paired losses per 1,000 queries, but its small Hit@1
trade-off should be treated as an explicit product choice rather than hidden by
the gate. This is the first evidence that the transfer signal can be made cheap
enough for a shadow or interactive path. It is still a retrieval result: the
student uses generated teacher order rather than generated pyramid abstracts,
and no task-execution or human-utility labels are present. The third block
supports transfer within the disjoint test corpus, but a new corpus and
execution-level labels are still required for a general skill-hierarchy claim.

The frozen design and reproduction commands are in
[`PROTOCOL-R15-STUDENT.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R15-STUDENT.md).
Paired rows, hashes and bootstrap intervals are retained in
`.guidefold/checks/pi-hierarchical-harness-2026-09-10-r15-student-test1-comparison.json`
and the corresponding `r15-student-test2-comparison.json` and
`r15-student-test3-comparison.json` artifacts; the descriptive pool is in
`.guidefold/checks/pi-hierarchical-harness-2026-09-10-r15-student-pooled-comparison.json`.

### 5.10 R16 pyramid-abstraction ablation

To test whether the generated hierarchy itself adds signal after the student
has access to card metadata, R16 added one frozen feature: TF-IDF similarity
between the task and the Qwen-generated scope abstract, definition and terms.
The map was generated from the train snapshot and reused unchanged on the
disjoint test cards. The student, teacher order, candidate set, delivery gate
and evaluator were otherwise identical to R15.

The first external block changed the direct student's Hit@1/Complete@4 from
.305/.322 to .306/.321. The second changed .318/.319 to .317/.319. The third
left both arms at .306/.328. These sub-tenth-point differences provide no evidence of an incremental pyramid
benefit. The current gain is therefore best described as teacher-guided
metadata reranking; the generated abstracts are, so far, redundant with card
metadata for this distribution. This negative ablation is useful: the next
pyramid experiment should improve the abstract-generation target or encode
cross-scope transfer explicitly, instead of adding more scope text to the
query.

The ablation protocol and paired artifacts are retained in
[`PROTOCOL-R16-PYRAMID-STUDENT.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R16-PYRAMID-STUDENT.md)
and the adjacent `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r16-*`
files.

### 5.11 R17 pyramid-guided candidate expansion

R17 uses the generated map as a retrieval-stage selector instead of appending
its text to every card. For each task, the two leaf scopes with the highest
TF-IDF similarity to the frozen scope abstracts are searched through Go. Their
top ten results are unioned with the flat root top ten, and the R15 student
ranks the expanded pool. The top four are then hydrated with exact revisions;
all labels remain evaluator-only.

The method was replayed on four disjoint 1,000-query blocks of the external
SKILLRET test snapshot. Against flat Go, the two-scope arm improved
Hit@1/Recall@10/Complete@4 by +4.1/+3.8/+8.9 pp on block 1,
+3.9/+4.3/+6.5 pp on block 2, +3.2/+4.2/+7.2 pp on block 3, and
+6.0/+4.0/+7.0 pp on block 4. The paired bootstrap intervals on block 4 were
[+4.6, +7.5], [+2.8, +5.3] and [+5.4, +8.6] pp respectively. Every block
completed 3,000 SEARCH and 4,000 USE calls without an HTTP or hydration error.

The descriptive 4,000-query pool gives +4.30 pp Hit@1 (CI [+3.63, +4.98]),
+4.08 pp Recall@10 (CI [+3.43, +4.73]) and +7.40 pp Complete@4 (CI [+6.58,
+8.25]). This is the first result in the program where hierarchy expansion
adds candidates outside flat top ten and improves Recall@10 as well as bundle
completeness. It remains one public benchmark family: the first three blocks
are retrospective replays and the fourth is the fresh holdout. No user task
execution or human utility is measured.

The mechanism is active rather than cosmetic: on the four blocks, 31.0–33.7%
of tasks placed at least one newly retrieved scope candidate in the final four
(mean 0.36–0.39 new cards per task). The method therefore changes the
candidate set before ranking; the Recall@10 gain cannot be explained by a
reordering of the original flat ten.

The protocol and paired artifacts are in
[`PROTOCOL-R17-HIERARCHICAL-EXPAND.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R17-HIERARCHICAL-EXPAND.md)
and `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r17-*`.

### 5.12 R18 hierarchy scope-budget curve

R18 varied only the number of map-selected leaf scopes on block 4. One scope
gave +2.6 pp Recall@10 and +6.5 pp Complete@4; three gave +5.6 and +7.8 pp;
four gave +6.4 and +8.2 pp. The four-scope arm replicated on block 2 at
+6.4 and +7.1 pp. Across those two blocks its descriptive gains were +5.05 pp
Hit@1 (CI [+4.10, +6.05]), +6.4 pp Recall@10 (CI [+5.3, +7.5]) and +7.65 pp
Complete@4 (CI [+6.45, +8.9]). Four scopes cost about 231 ms median and
303 ms p95 end-to-end on block 4, versus approximately 71/89 ms for flat Go.

Because the curve was inspected after the R17 replay, R18 is an exploratory
cost/quality result. It identifies a promising shadow configuration and a
measurable latency trade-off; it is not a tuned production default or a claim
that four is universally optimal. The frozen two-scope R17 estimate remains the
primary method result.

### 5.13 R19: budget-matched scope-selection controls

R19 tested whether R17's improvement was only the result of making two extra
scope SEARCH calls. The `pyramid`, literal `scope_name`, globally `popular`, and
deterministic `random` arms each received the same root candidates, two scope
calls, train-only student and four USE calls. On the fresh block 4, pyramid
improved flat by +4.0 pp Recall@10 and +7.0 pp Complete@4; literal names gave
+3.6/+6.9, popular +5.2/+8.1, and random +2.1/+5.7. Pyramid was not
significantly better than the controls on that block, so the result rules out a
claim that the current LLM map is necessary.

The post hoc replication on block 2 preserved the same pattern: pyramid gave
+4.3/+6.5, names +2.8/+5.5, popular +4.8/+6.5 and random +0.8/+4.9 pp for
Recall@10/Complete@4. The complete per-task reports, hashes and paired
bootstrap intervals are in `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r19-budget-matched-test4`
and `...-test2`; the frozen design is
[`PROTOCOL-R19-BUDGET-MATCHED.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R19-BUDGET-MATCHED.md).
This is a method-isolation result, not user-utility evidence.

### 5.14 R20: coarse-to-fine parent/child routing

R20 used the same two-scope budget to test whether explicitly traversing the
generated pyramid from a major scope to its children adds signal. Direct leaf
selection scored +4.0 pp Recall@10 and +7.0 pp Complete@4 over flat on block 4;
one-major/two-child routing scored +3.4/+6.4 and two-major/one-child routing
+2.4/+6.6. The parent/child traversal therefore did not improve the direct
selector on this corpus. It is a useful negative ablation: the current gain is
from selecting additional leaf scopes, not from the number of hierarchy hops.
See [`PROTOCOL-R20-COARSE-TO-FINE.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R20-COARSE-TO-FINE.md)
and `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r20-coarse-to-fine-test4`.

### 5.15 R21: LLM-generated example-query pyramid

The R21 generator extended each source-grounded scope card with three to five
short natural-language `example_queries`. Qwen2.5-7B ran on the RTX 4090 over
the frozen 10,123-card train snapshot with the deterministic diverse sampler;
24 nodes and all 18 leaves passed validation. The generator recorded one
truncated documentation entry and repaired it in a separate, source-preserving
retry; no sources were invented. Generation metadata and map hash are retained
under `.guidefold/checks/llm-pyramid-router-2026-09-10-r21-examples`.

The retrieval replay held the root candidates, student, two scope calls and four
USE calls fixed. On block 4, `full_pyramid` (abstract, definition, terms and
examples) improved flat by +5.1 pp Recall@10 and +7.4 pp Complete@4; on block 2
the gains were +5.6/+6.8. Against the literal `scope_name` control, the paired
gains were +1.3/+0.4 pp on block 4 and +2.6/+1.2 pp on block 2. Pooling the two
blocks descriptively gives +1.95 pp Recall@10 (95% bootstrap CI [+1.0,+2.95])
and +0.8 pp Complete@4 (CI [+0.1,+1.5]); Hit@1 is unchanged within rounding.
`examples_only` was similar to the full map, so the evidence currently supports
natural-language task anchors more than a specific abstract field.

This is the strongest current evidence for the requested LLM-built pyramid:
its selector adds a small but positive signal over scope names while preserving
the larger R17 expansion gain. It remains descriptive on one public benchmark
family; a second corpus and task-execution labels are still needed for a broad
paper or product-success claim. Protocols, scripts and pooled hashes are in
[`PROTOCOL-R21-EXAMPLE-QUERY-PYRAMID.md`](../research/llm-pyramid-router-2026-09-10/PROTOCOL-R21-EXAMPLE-QUERY-PYRAMID.md),
[`PROTOCOL-R21-RETRIEVAL.md`](../research/pi-hierarchical-harness-2026-09-10/PROTOCOL-R21-RETRIEVAL.md)
and `.guidefold/checks/pi-hierarchical-harness-2026-09-10-r21-example-router-pooled-comparison.json`.

### 5.16 R22: external SRA replication of an LLM leaf pyramid

R22 moved the pyramid test to the independent public SRA-Bench corpus: 26,262
skills, including 25,626 `web` distractors, and 5,400 annotated queries. The
hierarchy was created without query annotations: each of seven corpus prefixes
was split into four deterministic embedding clusters. Qwen2.5-7B received only
up to twelve card names and descriptions per leaf and generated an abstract,
terms and three to five natural-language example queries. All 28 leaves passed
field-format and source-ID validation, not semantic validation; the final map had no provenance fallback (the runner
retains a deterministic fallback for future failed citations).

At a fixed budget of two scoped searches and ten local candidates per scope,
the primary replay fit TF-IDF on the 28 map documents only, then used fixed RRF
(`k=60`) to compose the root top-50 with scoped candidates. The full generated
map improved dense flat retrieval from 56.69% to 65.22% Recall@10
(**+8.53 pp**, paired bootstrap 95% CI **[+7.46,+9.60]**) and from 42.31% to
47.19% Complete@4 (**+4.87 pp**, CI **[+3.83,+5.91]**). Hit@1 was preserved by
the root rank-one anchor. The non-LLM `card_metadata` control (the same sampled
source card names and descriptions without generated text) gave +1.08/+0.69 pp;
full-pyramid versus this control was **+7.45 pp Recall@10** (CI **[+6.47,+8.44]**)
and **+4.19 pp Complete@4** (CI **[+3.32,+5.06]**). Examples alone gave
+4.70/+0.98 pp, while literal scope names gave −7.29/−14.00 pp; popular and
random controls also lost. An independent checker recomputed all 5,400 flat
rankings, 32,400 arm rankings and metrics and passed.

The signal is heterogeneous rather than universal. Full-pyramid Recall@10 and
Complete@4 changes were +23.85/+18.95 pp on ToolQA, +10.92/+8.16 on LogicBench,
+1.64/+1.00 on MedCalcBench, +7.44/+2.02 on BigCodeBench, −8.67/−5.83 on
CHAMP and −6.29/−12.18 on TheoremQA. The unweighted macro deltas across these
datasets were +4.81 pp Recall@10 and +2.02 pp Complete@4. A bootstrap over the
six datasets gives wide macro intervals, [−3.47,+13.93] and [−5.54,+10.16] pp,
for those two metrics, so the pooled positive result must not be described as a
universal cross-dataset improvement.

R22 is the first cross-corpus positive signal for the proposed mechanism: an
LLM-written, source-sampled task-anchor map can select useful hierarchical
search regions beyond a flat dense pool, and its natural-language anchors beat
literal node names under the same RRF budget. It is still exploratory because
the public release and model family were already available, RRF is established,
and SRA has no repository revisions, conflicts, proof delivery or task execution
outcomes. The result supports a paper hypothesis and a shadow product path; it
does not yet establish universal user benefit. Artifacts and the independent
checker are in
[`PROTOCOL-R22-LLM-PYRAMID.md`](../research/sra-external-pyramid-2026-09-08/PROTOCOL-R22-LLM-PYRAMID.md),
[`r22-retrieval-report.json`](../research/sra-external-pyramid-2026-09-08/r22-retrieval-report.json),
[`r22-retrieval-maponly-report.json`](../research/sra-external-pyramid-2026-09-08/r22-retrieval-maponly-report.json),
[`r22-strata.json`](../research/sra-external-pyramid-2026-09-08/r22-strata.json),
[`verify_r22.py`](../research/sra-external-pyramid-2026-09-08/verify_r22.py) and
[`r22-verification-maponly.json`](../research/sra-external-pyramid-2026-09-08/r22-verification-maponly.json).

### 5.17 Pi proof-gated harness replay

R22 jest wynikiem retrieval; osobny świeży replay sprawdził, czy agent rzeczywiście
przestrzega granicy dostawy. Przy `top_down` i polityce `proof_gated` Pi wykonał
trzy SEARCH w hierarchii Go, wybrał dwie karty i wykonał dwa USE z ich rewizjami.
Oba USE zwróciły HTTP 200 z `delivery.action=ASK`, `reason=proof_missing` i
`body_chars=0`, ponieważ karty nie miały source-proof-v1. Pi zakończył z pustym
`used_skill_ids` i jasno napisał, że nie zna treści kart. Trace nie zawierał
goldenów.

To jest bezpośrednia walidacja fail-closed i zgodności protokołu SEARCH/USE/ASK
w realnym harnessie. Nie dowodzi jeszcze, że wybrana karta była najlepsza ani że
agent wykonał zadanie lepiej. Pełny zapis znajduje się w
[`AGENT-BEHAVIOR.md`](../research/pi-hierarchical-harness-2026-09-10/AGENT-BEHAVIOR.md)
oraz w `.guidefold/checks/pi-hierarchical-harness-2026-09-10-pi-r3/`.
Automatyczna kontrola tego replayu jest w
[`verify_pi_r3.py`](../research/pi-hierarchical-harness-2026-09-10/verify_pi_r3.py).

### 5.18 Product interpretation and communication update

The [10 September interpretation](reports/market/2026-09-10-research-product-update.md)
connects R22 and Pi r3 to the landing page and a dated Polish presentation. A new
arithmetic audit recomputes metrics for all 37,800 retained rankings before
exporting the compact public evidence. It also records the important Pi limit:
zero of the two selected skills matched the labelled answer set. Correct handling
of ASK is distinct from correct retrieval and from task completion. The generated
map remains an experimental path; this communication update changes no default
production ranking.

### 5.19 Post-hoc mechanism and dependency audit of R22

The [mechanism audit](reports/market/2026-09-10-r22-mechanism-audit.md)
reproduced all 21,600 text-based scope selections independently. No new model
or retrieval runs were made. Among 551 Complete@4 wins, 200 needed a skill
outside dense top-50; 288 queries lost completeness. Grouping reused gold sets
leaves positive pooled intervals, but the source-prefix construction and the
636 distinct annotated skills limit generalization to natural monorepos. The
audit corrects the sample size to **up to** twelve cards per leaf and separates
source-ID validity from semantic validity. It does not change the run's method,
selection, scoring or original results. Experiments remain paused.

### 5.20 R22 novelty review: evolving skill graphs are direct baselines

The [10 September novelty and baseline review](reports/market/2026-09-10-r22-novelty-and-baselines.md)
adds SE-GoS and inspects pinned official Corpus2Skill/SkillDAG sources. Generated
hierarchies, structural expansion and guarded graph evolution already have close
precedents. The positive R22 result supports continuing the product direction;
it does not establish those components as new. The next distinguishing question
is whether the learned hierarchy improves actual monorepo tasks across unseen
scopes and repository revisions while delivery eligibility stays source-bound.
The report sets baseline and separation requirements for that comparison. This
was a primary-source/code review, with no baseline execution or new model calls.

### 5.21 Proof-gated evolving hierarchy protocol draft

The [protocol draft](../research/proof-gated-evolving-hierarchy-2026-09-10/PROTOCOL-DRAFT.md)
defines the next study that could separate Guidefold from Corpus2Skill, SkillDAG,
GoS and SE-GoS. It compares flat, navigable, graph, generated-map and
proof-gated/evolved-map arms on source-owner-disjoint repository scopes and a
later revision. Task success, harmful loads, stale/conflicting delivery and
false `ASK` are primary; Recall@k is secondary. The file is deliberately not a
frozen protocol and no execution has started.

### 5.22 E2 proof-gate regression matrix

The tracked [E2 matrix](reports/bakeoff/E2-PROOF-GATE-MATRIX-2026-09-10.md) is the next executable quality gate for the conflict and revision boundary. On a synthetic sibling catalog, the production proof gate produced two safe `LOAD` decisions and six fail-closed `ASK` decisions for conflict, deprecated status, scope mismatch, revision drift, body tampering and incomplete closure. This is regression evidence (R/Q), not pilot evidence: it contains no model, real repository or task evaluator. The next meaningful result is the same matrix on real monorepo snapshots plus the frozen paired-task harness, where task success, harness errors, SEARCH/USE/ASK, tokens, latency and unknown coverage are measured together.

### 5.23 End-to-end quality-gate evaluator

The new [`quality_gate.py`](../tools/pilot/quality_gate.py) evaluator joins task-level replay rows with a separate E2 decision file. It reports task success, unknown coverage, useful delivery, harmful-load Wilson bounds and paired candidate/baseline deltas. It requires conflict/revision trigger cases and known candidate outcomes before it can return `pass`; missing evidence returns `inconclusive`, while a loaded stale/conflicting body returns `fail`. The implementation and regression cases are documented in [`QUALITY-GATE-EVALUATOR.md`](pilot/QUALITY-GATE-EVALUATOR.md). This is instrumentation and a decision guard, not new experiment evidence; the real E2 and frozen paired-task replay remain outstanding.

### 5.24 Source-disjoint URCT preparation

The [source-disjoint URCT manifest](reports/bakeoff/SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json)
and [preparation report](reports/bakeoff/SOURCE-DISJOINT-URCT-2026-09-10.md) replace the earlier
same-owner input as a candidate corpus for the held-out hierarchy study. It contains two families,
eight hash-addressed public-repository snapshots and four C/C′ cases; A, B and C have distinct
GitHub owners within each family, and an independent hash check passed. The replay helper
[`fetch_source_disjoint_urct.py`](../tools/pilot/fetch_source_disjoint_urct.py) rebuilt all eight
records from the pinned public commits with matching hashes. It is still
`PREPARED_NOT_ANNOTATED`: C′ is a controlled drift derivative, both reviewer forms are pending,
and no model, retrieval or task execution has been run. The corpus therefore removes one
independence flaw but does not yet open the publication gate.

Fresh replay `urct-fetch-e5e4bdd-2026-09-10T21:54:09+02:00` ran in the Docker/WSL workspace with
new clone caches and returned `PASS`, records `8/8`, with every digest equal to the manifest.
Command: `python3 tools/pilot/fetch_source_disjoint_urct.py --manifest
docs/reports/bakeoff/SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json --output
/tmp/guidefold-urct-replay-e5e4bdd --repo-cache /tmp/guidefold-urct-cache-e5e4bdd`.

### 5.25 Annotation integrity gate

The new [`verify_annotation_packet.py`](../tools/pilot/verify_annotation_packet.py) adds the
mechanical boundary between corpus preparation and semantic evaluation. In `blank` mode it
verified the four generated C/C′ packets, both reviewer forms per packet, source hashes and the
`model_calls_allowed=false` invariant. In `annotated` mode it will reject incomplete labels,
unknown field values, duplicate reviewer fields and evidence ranges outside the immutable source
files; it reports raw reviewer agreement but leaves disagreements for adjudication. The local
replay returned `BLANK_PACKET_VALID` with manifest hash
`2e3887610dba163ec2118eb51bcd3b59c94640a1081a62c607c6ec264acb288e` on 2026-09-10. This is
input-integrity evidence, not a semantic, task-success or publication result.

### 5.26 Hidden-verifier Pi execution smoke

The new [`run_agent_tasks.py`](../tools/pilot/run_agent_tasks.py) separates the retrieval-only Pi
replay from task execution. It copies each task workspace into a temporary directory, keeps hidden
verifiers in a separate evaluator root, permits only the declared Pi tools, and emits rows accepted
by `quality_gate.py`. Verifier failures are `failure`; agent, timeout and harness failures are
`unknown` with `harness_error=true`. Unknown safety/usefulness observations remain null.

On 2026-09-10, one harmless task was run twice against the live 10,123-card Go snapshot with the
same task bank and hidden verifier. Both arms passed the verifier. `proof_gated` made 1 SEARCH and
4 USE calls, received 4 `ASK` responses and delivered zero body characters; `legacy` made 1 SEARCH
and 5 USE calls, delivered 155,728 body characters and received no `ASK`. The Pi output stayed
blind to the evaluator and correctly reported no used skills in the gated arm. This is direct
end-to-end harness evidence for fail-closed delivery and verifier plumbing, not evidence of a task
success advantage: the task was deliberately trivial and no useful-delivery or harmful-load labels
were available. The local artifacts are under
`.guidefold/checks/pi-task-execution-smoke-20260910/` and its legacy control directory.

### 5.27 Quality-gate parser correction

An evaluator audit found that a JSONL file containing exactly one object was parsed as an optional
`{"rows": [...]}` wrapper and therefore produced zero attempts. The parser now recognizes a
single task row, with a regression test covering the format. Replaying the existing Pi smoke
through the corrected evaluator reports one candidate attempt, task success `1/1`, zero harness
errors, `SEARCH=1`, `USE=4`, `ASK=4`, 34,282 ms and zero delivered body characters. Useful
delivery and harmful-load remain unknown for that deliberately trivial task, so this correction
improves accounting integrity but adds no task-quality claim.

### 5.28 Fresh source replay and annotation-packet regeneration

On 2026-09-10 a clean-cache replay of the source-disjoint manifest fetched the eight pinned
public blobs (two families, A/B/C/C′) and reproduced every manifest digest. The new
[`make_annotation_packet.py`](../tools/pilot/make_annotation_packet.py) then generated four
blank C/C′ packets (one current and one drift target per family), each with two independent
reviewer forms and six canonical fields. `verify_annotation_packet.py --mode blank` returned
`BLANK_PACKET_VALID`, `packet_count=4`, with `model_calls_allowed=false`.

This is a preparation result, not a semantic label or task outcome. The packet is deliberately
generated from the fresh snapshot directory rather than silently checked into the source corpus;
the manifest, generator, and verifier are the reproducible source of truth. The next meaningful
step is for two independent human reviewers to fill the blank forms, followed by adjudication
of disagreements. No model call may occur before that step.

### 5.29 Four-task Pi feasibility replay

The first shared-bank end-to-end feasibility replay ran four isolated hidden-verifier tasks in
both `map+gate+evolution`/`top_down`/`proof_gated` and `flat`/`flat`/`legacy`. After correcting a
fixture newline and repeating the full bank, both arms scored **3/4 (75%)** with no harness
errors. The candidate made 12 SEARCH and 16 USE calls, all 16 ending in `ASK` with zero body
characters; the legacy control made 4 SEARCH and 17 USE calls and exposed 457,275 body
characters. The one failed task was the same in both arms: the agent omitted a required final
period, so the hidden verifier correctly rejected it. Paired success delta was 0 pp.

This is a useful execution and delivery-boundary signal, not a quality or publication claim.
The quality gate remains `inconclusive` because E2 conflict/revision cases and independent
useful/harmful delivery labels are absent, and the bank has only four trivial tasks. The frozen
inputs and report are in
[`research/e6-feasibility-20260911/README.md`](../research/e6-feasibility-20260911/README.md).

### 5.30 Source-backed E2 delivery matrix

On 2026-09-11, the proof-gated policy was replayed against the fresh, hash-verified
engineering and documentation C/C′ snapshots. Each of the four targets contributed 19
harmful mutations covering conflict, deprecation, scope, stale revision, tampering,
incomplete closure and sibling transfer, plus one safe complete-proof case. The candidate
returned `ASK` for all 76 harmful cases and `LOAD` for all four safe cases; the flat exposure
control returned `LOAD` for all 76 harmful cases. The one-sided Wilson 95% upper bound for
harmful delivery is 4.81%, and stale/conflicting body delivery is zero.

This is source-backed deterministic R/Q evidence for the delivery boundary, not a human
semantic judgment, natural-hierarchy transfer result or task-success claim. The combined
task scorecard therefore remains `inconclusive` because the four-task Pi bank has no useful-
delivery labels and both arms score 3/4. Reproduce it from
[`research/e2-source-backed-20260911/README.md`](../research/e2-source-backed-20260911/README.md);
the runner rejects any snapshot whose digest differs from the frozen manifest.

### 5.31 Evaluator-only usefulness labels

The end-to-end runner now accepts optional boolean `useful_delivery`, `harmful_load`, and
`stale_conflict_delivery` fields from the hidden verifier's final JSON line. The fields are
parsed only after the agent exits and are never included in the agent prompt; plain-text
verifiers remain valid and keep the measurements `unknown`. This closes the instrumentation
gap needed for the useful-coverage part of the quality gate without treating task success or
body length as a proxy for semantic usefulness. A focused regression suite covers both labelled
and unlabelled verifier output.

### 5.32 Source-backed E2 through the Go HTTP path

An opt-in integration test now takes the fresh engineering and documentation C/C′ snapshots,
publishes their bytes through the real import/parse/build worker, and calls the production
`USE 1.2` handler with `delivery_policy: proof_gated`. The replay passed **4/4** targets:
each returned `delivery.action=LOAD`, `reason=source_proof_complete`, `status=hydrated` and a
non-empty body. The service itself verified the cited source hash and range. The test skips
only when its external snapshot directory is not supplied; with the variable set, missing
PyYAML or PostgreSQL is a failure, not a pass.

This closes the gap between the source-backed evaluator and the actual Go delivery path for
the safe current-proof case. It still does not replace the harmful-mutation matrix, human
semantic labels or end-to-end task evaluation. Reproduction details are in
[`research/e2-source-backed-http-20260911/README.md`](../research/e2-source-backed-http-20260911/README.md).
