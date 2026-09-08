# From Retrieval Scores to Delivered Guidance: An Audit of Agent Skill Routing Under a Four-Card Budget

Internal research-note draft, 6 September2026. Not submitted; not peer-reviewed; authors and affiliations require owner input. This is an empirical contribution candidate, not a claim of established novelty. Source code and recorded evidence accompany the draft.


**CPU follow-up and label-quality update (6 September 2026):** Six additional sparse variants completed on a fresh internal 2,048-query cohort. None establishes a breakthrough. Inspection also found semantically suspect positive labels in SKILLRET TRAIN; structural joins are correct. Interpret TRAIN-based retrieval/completeness results as scores against the recorded labels pending independent relevance adjudication. This issue does not automatically apply to the separate historical SkillRetBench audit. See [CPU results](cpu-enrichment-controls.md) and [label audit](skillret-train-label-audit.md).

## Abstract

Skill routing systems are commonly compared using retrieval metrics, although agents receive bounded instruction sets through a separate delivery path. We audit saved Guidefold experiments and the implementation of this path. A paired reanalysis of1250 SkillRetBench queries finds that a contextual-encoder reference improves any-gold Hit@1 by8.40 percentage points over the shipped sparse comparator, while all-gold completeness within four injected cards changes by1.12 points with an interval spanning zero. Among300 distractor queries, labelled distractor exposure decreases by10.00 points while completeness decreases by11.00 points. We identify215 queries whose gold lists exceed the four-card budget, making AND-all-gold success impossible under this metric. Separate regression-fixture checks expose uncalibrated abstention and a byte-based hydration budget. An exact pilot-design calculation shows why20–40 paired tasks cannot reliably establish modest downstream benefits. These observations motivate evaluation that reports eligibility, budget feasibility, coverage, set completeness, harmful exposure and actual execution separately. They do not establish general superiority of a retrieval family or developer productivity gains.

## 1. Question and relation to prior work

Our candidate contribution is an executable audit of the gap between score quality, admissible set construction, delivery constraints and downstream evaluation. We do not claim to introduce field-aware retrieval, reciprocal rank fusion, selective retrieval, or matched-task evaluation. Existing work already motivates field structure, body-aware selection, set compatibility and actual-use effects. The scientific question is whether conclusions about an agent skill router survive a consistent accounting of these stages and their denominators. [Field-Aware Agent Skill Retrieval](https://arxiv.org/html/2608.02880v3), [SkillRouter](https://arxiv.org/html/2603.22455v5), [R3-Skill](https://arxiv.org/abs/2606.03565), [Skill Following](https://arxiv.org/html/2609.00549v1).

A second exploratory question, requested during this audit, compares learned fusion of concatenated and per-field scores. Its preregistered DEV-only configuration and complete result belong in the separate [field-aware experiment](../../../research/spikes/2026-09-06-field-aware/PROTOCOL.md). This is a component feasibility study, not a reproduction of the paper or evidence of a new state of the art.

## 2. Materials and protocol

The recorded reference run contains two arms at two scopes: shipped F0 and SKILLRET-Embedding-0.6B-based R1. The root comparison exposes the same501-skill bank. The category-scoped comparison chooses scope from the first gold skill and is diagnostic rather than a measured deployment distribution. The raw JSONL has5000 unique query-arm-scope observations. All1250 query IDs align with the pinned labels; source SHA256 values and the code commit are recorded by [audit.py](../../../research/spikes/2026-09-06-evidence/audit.py).

Our reanalysis performs no retrieval or parameter selection on these test records. Hit@1 is binary any-gold relevance; unanswered queries score zero. Completeness means every listed gold item appears in the first four injected cards. We report the full1250-query denominator and the1200 queries answered by both arms. A2000-resample paired percentile bootstrap operates over queries. Repeated skill identities induce dependence not modelled by that interval. Diagnostic strata were specified during this post-hoc audit and are not confirmatory tests.

The gold-set interpretation follows the historical adapter. This is not proof that every gold item is a mandatory independent requirement. An annotation review must distinguish AND requirements from OR alternatives before using the findings to criticize the benchmark itself. We retain impossible-budget cases in the headline and show the feasible subset separately.

## 3. Recorded-reference reanalysis

All figures below are recomputed from saved outputs, not new model runs. Percentage-point intervals are exploratory95% query-bootstrap intervals.

| Root metric | F0 | R1 | Difference [95% interval] | n |
|---|---:|---:|---:|---:|
| Any-gold Hit@1, all queries |36.48%|44.88%|+8.40 [5.76,11.12]|1250|
| AND-all-gold injected@4, all queries |36.00%|37.12%|+1.12 [-1.12,3.44]|1250|
| AND-all-gold injected@4, both answered |37.50%|38.17%|+0.67 [-1.67,3.00]|1200|
| Completeness, gold cardinality<=4 |43.48%|44.83%|+1.35 [-1.26,4.15]|1035|
| Labelled distractor exposure@4 |39.67%|29.67%|-10.00 [-15.67,-4.00]|300|
| Completeness on distractor queries |28.33%|17.33%|-11.00 [-15.33,-6.67]|300|

The gold cardinalities are1:850,2:60,3:72,4:53,5:15,25:200. Thus215/1250 cases cannot achieve the declared four-card AND metric, regardless of ranking quality. The corpus has zero empty-gold cases, so it cannot validate a NO_SKILL decision. Its50 F0 abstentions and zero R1 abstentions also explain why per-arm answered-query summaries can differ from matched or all-query summaries.

The reduction in labelled distractor exposure is not interchangeable with improved task utility: correct set delivery regresses in the same stratum. Conversely, an interval spanning zero is not proof that dense has no benefit. Training distribution, corpus construction, original scorer configuration and document representation prevent a clean causal attribution to distribution shift or distillation alone.

## 4. Delivery-contract diagnostics

[The CTO spike](../../../research/spikes/2026-09-06-cto/README.md) executes the unchanged product on existing synthetic fixtures. All44 no-applicable cases return nonempty cards. The score of a first-ranked single-leg RRF result is largely a function of rank; interpreting it as calibrated relevance can fail even when a query contains an incidental known token. This is a reproducible regression diagnosis, not an estimate of production false-positive frequency.

The26 fixture bodies have median4658bytes. At the optional4096 budget, the current conservative byte proxy admits one body;16384 admits all26. These are size checks, not evidence that section compression preserves obligations. Explicit token accounting or a larger agreed budget may solve the immediate constraint. [SkillZip](https://arxiv.org/html/2608.05604v1) motivates contract-preserving hydration but does not establish that arbitrary truncation is safe.

The service client computes local ranking before consuming the remote result; its full index loading begins outside the network deadline clock. A separate Go loopback p95 therefore does not establish the production hook's end-to-end latency. This must be measured across startup, authentication, networking, search, delivery and fallback in the target environment.

## 5. Pilot feasibility and statistical limits

[Exact calculations](../../../research/spikes/2026-09-06-evidence/pilot-power.json) assume independent paired binary task outcomes. With40 pairs, improvement probability0.15 and regression probability0.05, a two-sided exact sign/McNemar test at alpha0.05 has17.24% power. Even with zero regressions among40 pairs, the one-sided95% upper bound is7.22%. Repeated developers, repositories or skill families further complicate inference.

We recommend20–40 paired tasks for usability, failure discovery and protocol feasibility, followed by an appropriately powered study. The control preserves ordinary native repository instructions and switches off Guidefold-specific discovery/delivery. Use paired task executions with a frozen model, independent verification and controlled order; a human should not solve the same task twice and then be treated as an independent counterfactual. Report all task outcomes as well as an explicitly labelled actual-use subset. The latter must not replace the full policy-level effect.

## 6. Work required before submission

1. Independent rerun of the artifact on a clean machine, with a unified manifest covering all historical model/scorer variants; preserve negative and inconclusive results.
2. Annotation review of budget-constrained gold lists, functional equivalents, stale siblings, NO_SKILL cases and label leakage; provenance of human versus generated queries.
3. Field-aware follow-up under equal aggregate token budgets and identical candidate/admission settings, more than one seed, a fresh holdout and uncertainty accounting for skill families. Publish all preregistered arms, not only a winner.
4. Real whole-hook timing and downstream paired tasks; report missing delivery, task failures and harmful flips. Do not infer utility from load/exposure.
5. Check novelty against the related evaluation literature, resolve authorship and third-party dataset/model release terms, and choose an empirical/workshop or systems venue appropriate to the evidence. Acceptance is not predictable from this audit.

A defensible submission can report a bounded negative or mixed result. It cannot claim that BM25 generally beats dense, that field-aware fusion is our invention, that an underpowered pilot proves no effect, or that the system already improves developer productivity.

## Reproducibility status

This note is **shareable with caveats as an internal empirical audit**, and **needs revision before scientific submission**. Raw rankings, source hashes, scripts and JSON results exist. No user study or publication was performed in this task. The field-aware experiment has a separate protocol/results/report so incomplete or exploratory runs cannot silently enter the confirmatory table above.

## Research extension: grounded index-time enrichment

The user-authorized follow-up tests whether document representations are a more useful intervention than increasing the unlabelled candidate bank. The frozen pilot selects512 documents independently of queries, retains the full10,123 candidate bank, and compares shipped BM25F, generated intent metadata, and metadata plus pseudoqueries on2,048 internal TRAIN queries. These queries exclude the3,000 IDs and exact normalized texts recorded in the earlier field-aware experiment. Local Qwen2.5-7B receives source documents only. A mechanical source-quote filter and a preselected blinded semantic audit precede ranking. This is a partial-coverage feasibility experiment; a new data source and full coverage are needed for stronger claims.

Document expansion itself is established prior work (doc2query/docTTTTTquery, Doc2Query--, Skill2Query). A defensible new empirical contribution would study the relation among grounding quality, retrieval completeness under a four-card budget, collateral ranking regressions, and the cost of maintaining enriched indexes. We do not claim this contribution is novel or established merely by implementing it. Source copying, text-length controls, stronger query validation, source-family splits and full-coverage replication remain important comparisons. Real user execution is required for any claim about productivity.

The data card identifies SKILLRET TRAIN queries as Qwen3.5-122B-A10B-generated; despite withholding query text from our Qwen2.5-7B generator, shared style and public-data pretraining cannot be ruled out. The pipeline preserves original instructions and never promotes generated retrieval metadata to mandatory policy. Detailed protocol and results are maintained separately in the query-enrichment experiment directory.

### Completed enrichment pilot readout

The fixed three-arm experiment completed on2048 internal queries. C versus A raised Recall@10 from0.57421875 to0.5758463542 (+0.162760 percentage points) and selected-set completeness from0.29052734375 to0.2919921875 (+0.146484 points). Only five queries improved recall, with no recall regressions; all three completeness improvements were singleton tasks. No multi-skill set became newly complete. The preregistered query-bootstrap screen passed; a pre-outcome gold-sharing component sensitivity also excluded zero for recall. Posthoc exact paired sign-flip sensitivity on the five changed queries/components gave two-sided p=.0625 (completeness p=.25). We therefore treat the result as a small, fragile signal rather than confirmatory evidence. Independent QA reproduced all6144 metric rows and84 comparison cells. See query-enrichment-results.md and the raw experiment artifacts.

### Source-only prompt iteration

A completed32-document paired generation study, disjoint from the first512 documents, compared the original prompt against an explicit scope-preserving task prompt. Accepted pseudoqueries increased38→57 and empty documents decreased4→1 across32 documents. In a fixed8-pair audit by one agent aware of arm identity, supported/specific items were11/28 versus18/29; weak/generic items17 versus11. However, nonempty audit documents fell8/8→7/8 due to one scoped response hitting the448-token cap and invalid JSON. There were no unsupported accepted items in this small audit. The partial batch8 run was interrupted for observed GPU memory pressure; both arms were restarted batch4 and only complete restarted pairs are analyzed. This is evidence about generation feasibility and a qualitative nomination for a future retrieval test, not a measured recall gain.

## CPU-only controlled follow-up and label-validity question

A five-arm protocol compared unchanged production routing, all previously accepted generated metadata, source-retrievability filtering, count-matched random item removal, and whitespace-length-matched source extraction. We kept the full 10,123-skill bank, reused the original 512 assigned documents, and selected 2,048 new internal TRAIN queries after excluding 5,048 previously used IDs and matching normalized texts. A separately frozen exploratory control added a 20-word source prefix for all skills. It was specified while the primary experiment ran, before inspecting this cohort's outcomes. No GPU, new query generation, or production changes were used.

All generated metadata changed macro Recall@10 from 58.0485% to 58.1217% (+0.0732 percentage points), with six improved and three regressed queries. Completeness@4 stayed at 28.7109%, with one improvement and one regression. The source-retrieval filter produced 58.0566% Recall@10 and 28.6621% completeness, failing the prespecified continuation gate. None of the four planned Recall@10 contrasts passed Holm correction; generated-versus-original had exact component sign-flip p=0.2578125 and Holm p=0.75. Full-source-prefix extraction also yielded 58.1217% Recall@10 and unchanged net completeness, but affected only four recall outcomes; its explicitly post-hoc exact sign-flip p was 0.125. Equal aggregate performance of the full prefix and partial generated arm is not an equivalence result because their coverage and text budgets differ.

Six arms provide 12,288 unique query-arm rankings. Independent code reconstructed qrels-based metrics, query and gold-component bootstraps, and the planned exact tests. The shared-gold graph has 1,329 components. A research-only cache reuses integer term scores from the original router; 448 query-arm/text parity checks confirmed identical full-pipeline outputs against its unmodified scorer. Full artifacts are in [the experiment directory](../../../research/spikes/2026-09-06-cpu-enrichment-controls/README.md).

A conditional oracle analysis exposed a severe apparent multi-skill ceiling: only 20/724 three-labelled-skill queries contained every positive within the baseline top 50, and only 3/724 had a complete selected set. However, manual inspection by the research assistant of a hash-selected six-query sample of such failures found semantically suspect positives: wireless penetration testing attached to MCP configuration synchronization, student exercise generation attached to payment-module refactoring, and Jira attached to Hugo/Lighthouse optimization. The raw query arrays and qrels agree on these pairs, and the respective full skill sources support the mismatch concern. The sample is conditioned on retrieval failure, inspected after outcomes, and reviewed by one assistant; it cannot estimate noise prevalence or replace independent relevance judgments.

A structural audit of all 63,259 TRAIN queries and 127,190 qrels found no orphaned pairs, duplicate query IDs, duplicate qrel pairs, or name/ID/count mismatches. Structural consistency therefore does not resolve the semantic concern. The [dataset card](https://huggingface.co/datasets/ThakiCloud/SKILLRET/blob/main/README.md) states that version 1.1 semantically filters TEST while TRAIN remains byte-identical to version 1.0; we do not generalize these examples to TEST. A balanced, outcome-independent 120-query/240-pair review packet is prepared, with randomized skill order and full source texts. Its reviewer fields remain empty.

The next empirical question is whether independently adjudicating required, optional, alternative, and irrelevant skills changes conclusions about sparse/dense/fusion rankings and four-card completeness. Do not automatically relabel positives missed by BM25. This is a candidate direction for further research, not a completed annotation study, a proven benchmark-wide defect, or an established novel contribution. The original frozen results remain available unchanged.

## Fresh evidence addendum (8 September 2026)

Subsequent source-disjoint and agent-driven controls sharpen the candidate
contribution. A fixed-budget set selector improves Complete@4 by +2.90 pp on
the 2,000-query internal source-family-disjoint confirmation
(51.00% to 53.90%, paired bootstrap 95% CI [+1.80, +4.05]) and transfers to the
pinned R3 multi-skill cohort (+7.72 pp versus dense). Exact global subset search
is a negative control: its R3 development gain (+1.98 pp) transfers by -0.25 pp
on source-disjoint data. LLM taxonomy routing is another negative control:
reasoning improves over centroid routing at six broad categories, but remains
16 pp below flat dense all-gold@20 and loses its edge at 18 finer categories.

A separate context-loading track is also viable. In a 75-task/70-skill pilot,
card-first progressive disclosure reaches 64.7% hard-task accuracy versus 69.1%
with the full body, expands on 97.1% of hard tasks and 0% of easy tasks, and
saves 86.3% of content tokens when the card is sufficient. The 9.3% blended
saving is task-mix dependent; the task generator was mechanically leakage-gated
but not independently adjudicated, and calls were single-pass with temperature
unfixed. This is evidence for a calibration/context-cost mechanism, not a
population or productivity result.

The revised paper plan is to report the fixed-budget set-composition study and
the progressive-disclosure mechanism as separate analyses with shared
provenance, explicit negative controls and independent replay. A submission
still requires temperature-pinned repeated trials, independent semantic QA,
realistic traffic sampling, and paired skill-enabled/no-skill execution with
safety and closure outcomes. The evidence supports an empirical retrieval or
systems paper; it does not support a universal retrieval or agent-use
breakthrough claim.

Raw protocols and replay outputs:
[set objective](../../../research/set-objective-transfer-2026-09-07/README.md),
[LLM routing](../../../research/pyramid-routing-llm-2026-09-07/README.md),
[progressive disclosure](../../../research/progressive-disclosure-execution-2026-09-07/README.md).

## New primary hypothesis: unseen-repository contract transfer

The semantic counterexample to PCL changes the paper axis. Exact provenance,
branch quorum and source hashes can show where a sentence came from and when it
is stale, but they cannot show that a parent abstraction preserves meaning.
The main study therefore asks whether a structured procedure contract extracted
from repositories `A` and `B` transfers to an unseen repository `C`, and whether
that value survives a meaningful source change `C'`.

The contract records scope-in/out, preconditions, obligations, exceptions and
forbidden cases, operations, verifier, outputs and source references. Compare
no-skill, source skills, free-text summary, PCL, structured contract, and
contract plus contradiction checking/CEGAR under the same model, harness and
execution budget. Freeze a lineage-aware split before generation and evaluate
paired target executions with task success, harmful-load rate, field retention,
useful abstention, repair cost, stale-load rate and token/latency cost.

This is the new publication gate. PCL, K-PCL and CGSR are supporting mechanisms
for provenance, freshness and sibling resolution; their synthetic or internal
replays are not transfer evidence. A result is a breakthrough only if the
contract arm improves paired execution on source-disjoint targets without
increasing harmful loads, retains exceptions and remains useful after `C` drifts
across multiple unrelated families. The complete protocol is in
[URCT](../../../research/unseen-repo-contract-transfer-2026-09-08/README.md).

## Candidate method: guarded signed-contract promotion

The PCL polarity counterexample motivates a narrow kernel intervention. GSCM
represents each extracted procedure as signed atoms with an explicit guard and
promotes only the conservative meet shared by all child branches. It rejects
opposite obligations under overlapping contexts, refuses to widen disjoint
contexts, and keeps a narrower exception only when every branch supplies that
exception. Its grounded mode requires non-empty source pointers on child atoms
and carries those pointers into the parent. On the saved two-source counterexample, the provenance-only PCL
accepts the polarity-reversed parent while GSCM returns `ASK`; control cases
load a common obligation and a shared exception. The implementation and fresh
process replay are in
[`semantic-contract-meet`](../../../research/semantic-contract-meet-2026-09-08/README.md).

This result is a conditional kernel property, not a semantic-entailment or
product-utility result. Atom extraction and guard ontologies can be wrong, and
the method is adjacent to contract-preserving compression, proof-carrying
certificates and CEGAR prior art. We will call it a contribution only if the
pre-registered URCT study shows source-disjoint execution transfer on unseen
repositories with retained exceptions, reduced harmful loads and useful
coverage after drift.

As a kernel regression check, we exhaustively enumerated 4,096 two-child,
one-atom combinations over the frozen guard/signature universe. An independent
support oracle labelled 92 cases safe and 4,004 unsafe; GSCM produced 92
`LOAD`s with zero false loads and zero false abstentions in that finite model.
The comparison to a quorum-only baseline is hypothetical because all its
evidence edges are assumed fresh. This experiment establishes only the finite
algebra behavior; it says nothing about atom-extraction accuracy, target-repo
transfer or developer outcomes.

The target study also has an executable manifest guard: it checks the frozen
`A/B/C/C'` roles, target drift, source/target lineage separation, source-ref
leakage and equal model/budget across arms before any model call. The checked-in
manifest is a schema fixture, not data or execution evidence.

The related-work boundary is narrow. SkillOps already combines typed skill
contracts with a hierarchical ecosystem graph, Formal Skill defines an
executable JSON/runtime abstraction, and SkillGuard treats role-bearing drift
as contract violation. GSCM should therefore be evaluated as a library-time
source-grounded promotion gate with guarded exception preservation; it is not a
new skill format, runtime or drift monitor. SkillResolve-Bench also already
defines helpful/risky same-capability pairs and harmful-sibling evaluation, so
the sibling-resolution component must be a baseline rather than a novelty
claim.

## Extraction-bridge stress test

The kernel's conditional property does not imply that a language model emits
sound atoms. To measure this gap, we ran a frozen local Qwen2.5-7B-Instruct
pilot on 16 synthetic source pairs covering common obligations, disjoint
guards, branch-local exceptions, shared exceptions, opposite polarity and
irrelevant text. With the strict JSON interface, only 2 atom matches were
correct against 34 labelled atoms, 11/16 responses failed to parse, and GSCM
made 0/16 `LOAD`s (zero false `LOAD`s, nine false `ASK`s).

A predeclared serialization ablation kept the same sources, checkpoint and
greedy decoding but requested scalar tabular records. The model copied the
literal `<TAB>` placeholder from the prompt, so the frozen strict score was
again 0/16 `LOAD`. A separate post hoc transport diagnostic replacing that
placeholder recovered 25/32 exact child contracts and 8/16 `LOAD`s, with zero
false `LOAD`s and one false `ASK`; this is reported only as an interface
diagnostic, not confirmatory evidence. A paired verifier-guided repair pass
then produced 7/16 `LOAD`s but two false `LOAD`s by dropping branch-local
exceptions, and its independent verifier failed the safety gate. The results
show why a paper must separate serialization, semantic extraction and promotion
safety. They do not establish a model or product breakthrough.

The raw outputs, hashes, frozen prompts and failure status are preserved in
[the v1 pilot](../../../research/gscm-qwen-extraction-2026-09-08/README.md),
[the serialization follow-up](../../../research/gscm-qwen-extraction-v2-2026-09-08/README.md)
and [the repair run](../../../research/gscm-qwen-cegar-2026-09-08/README.md).
The next publication gate remains URCT: independent source-disjoint
repositories, blinded semantic labels, paired target execution and drift
outcomes. A safe kernel plus a weak extractor is a useful systems hypothesis,
not evidence of end-user benefit.

As a safety diagnostic, we replayed the repair with a monotone fallback that
rejects any deletion from the first candidate, followed by a lexical exception
risk gate. If source text contains `except`, `unless`, `exception` or an
explicit `may/allowed to disable`, a `LOAD` requires branch-complete `forbid`
atoms; otherwise it abstains. This replay produced 8/16 `LOAD`s, zero false
`LOAD`s and one false `ASK` on the same synthetic cases. Both rules were
selected after inspecting the failure and therefore are not confirmatory
metrics. They motivate a pre-registered source-risk feature in URCT, where
coverage and useful abstention can be evaluated on unseen repositories.

A final pipe-format check removed the placeholder transport issue (three parse
failures in 16 cases) but still produced two false `LOAD`s by omitting
branch-local exceptions. In a shared-exception case the model narrowed the
contract to `admin_request`, dropping the all-request obligation; GSCM accepted
that narrower contract because its support check has no requested-scope input.
This is a separate completeness failure from polarity or provenance. The next
kernel revision therefore needs an explicit requested scope and a coverage
certificate for every source obligation, with `ASK` on missing scope coverage.
The v3 raw result is preserved in
[the pipe check](../../../research/gscm-qwen-extraction-v3-2026-09-08/README.md).

## Scope-complete PPACR oracle replay

We implemented the requested-scope extension as a separate research artifact.
SC-PPACR represents the proof target as `(mandatory requirement, requested
scope)` obligations. It permits complementary cards to cover different
obligations, while rejecting a narrower card, contradiction, partial label, or
invalid source pointer at the load boundary. Five adversarial unit cases cover
anchor preservation, disjoint-scope composition, narrow-scope rejection,
contradiction/partial rejection, and invalid-line rejection.

On the existing 12-case source-review packet, with one explicit `global` scope
token and no model calls, the oracle policy produced 7/12 complete proof-valid
bundles versus 6/12 for the earlier single-candidate ECCR policy and 2/12 fully
supported prior top-1 cards. Unsupported or contradictory proof exposure was
zero. The additional load used two complementary cards. Because the packet has
no independent scope labels, this replay does not test natural-language scope
extraction or source-disjoint transfer. It is a paired policy result that
motivates, but cannot replace, URCT on unseen repositories with explicit scope
labels and execution outcomes. Raw inputs, hashes, exact proof lines and an
independent verifier are in
[scope-complete-ppacr](../../../research/scope-complete-ppacr-2026-09-08/README.md).

The paired difference from ECCR is +8.3 percentage points, with one positive
discordant case and no negative discordant case. A deterministic 200,000-draw
paired bootstrap gives a descriptive 95% interval of 0.0–25.0 points; the
sample is therefore too small for a population-level improvement claim.

As a kernel-only safety check, we enumerated 3,600 two-card combinations over
three evidence labels, valid/invalid source pointers, contradiction flags, and
five scope sets. Against an independent finite oracle, SC-PPACR had zero false
loads and zero false abstentions; the earlier PPACR implementation produced
862 false loads for narrower evidence because it lacked a requested-scope
input. This establishes only conditional behavior of the finite gate. It does
not validate natural-language scope extraction, repository transfer, or task
execution, which remain the decisive URCT tests.

## Real-source URCT inventory

We froze 12 hash-addressed `SKILL.md` snapshots from three procedural
families, arranged as source roles `A/B`, an unseen target `C`, and a
controlled drift target `C'`. The inventory verifier passed snapshot hashes,
role and lineage checks, the single semantic edit per family, and a nine-row
lexical overlap audit (maximum 5-gram Jaccard 0.0). It is a reproducibility
artifact and a harness input, not a model or execution result.

The source-independence gate remains open. `A` and `B` in every family are
under the same `cloudfloo` GitHub owner, so distinct repository URLs do not
establish independent provenance. The paper must either replace those sources
with unrelated owners or report this as a pre-registered pilot limitation.
No URCT arm, target execution, or user outcome should be counted until blinded
field adjudication and this gate are resolved. See the
[inventory](../../../research/urct-real-skill-corpus-2026-09-08/README.md) and
[verification output](../../../research/urct-real-skill-corpus-2026-09-08/corpus-verification.json).

To make the pre-execution gate reviewable, we also froze six anonymized
annotation packets with two blank reviewer forms and 15 fields per packet.
The packet verifier confirms hash alignment and refuses to treat any filled
label as present; it reports `model_calls_allowed=false`. This separates
source adjudication from later arm execution and leaves the shared-owner
limitation visible to reviewers.

We then prepared a stronger URCT-2 corpus with six remote source repositories
owned by six different GitHub accounts, pinned to path-level commits. Across
three families, the integrity and owner-separation checks pass for 12
snapshots, six `C/C'` cases, and a maximum 5-gram Jaccard overlap of 0.0. This
is still a provenance screen rather than proof of independent authorship or
semantic correctness. A matching six-case, two-reviewer blind annotation
packet is frozen with all 15-field forms blank and model calls disabled. The
paper must keep this as a pre-execution gate until adjudication and paired
target execution are complete.

### Recursive scope-aware proof lattice

We extended the proof-carrying pyramid with an explicit requested-scope
dimension. A parent reference can export only scope tokens covered by a fresh
child proof; exact source spans, child commitments, branch quorum and distinct
leaf spans remain mandatory. A finite replay of 22,500 variants over five scope
declarations, three leaf states and structural faults loaded all 9 oracle-safe
cases, with zero false loads and zero false abstentions. A compatibility PCL
baseline without requested scope loaded 625 cases and produced 616 false loads.
This establishes a conditional safety property of the recursive kernel. It does
not establish natural-language extraction, retrieval quality or downstream
execution, which remain the URCT-2 gates.

URCT-2 additionally freezes the execution order and falsification rules in a
separate protocol and exposes a fail-closed preflight. The current preflight
returns `execution_allowed=false` because annotations and model/prompt locks
are missing. This prevents an unregistered model run from being mistaken for
confirmatory evidence.

### Proof-aware functional routing

We composed the recursive scope proof with a functional sibling gate. A
retrieved candidate is eligible only if its proof is valid and covers every
requested scope token, its family/repository/language/version/precondition
contract matches, and an explicit verifier passes. Close candidates with
different operation identities produce `ASK` rather than an unsupported
choice. In an independently implemented finite oracle replay of 139,968
two-candidate cases, the composed gate had zero false loads and zero false
abstentions; a scope-blind compatibility gate disagreed in 5,016 cases and a
rank-only policy in 137,418. This is a conditional contract-algebra result,
not evidence of semantic extraction, retrieval improvement or task success.
The implementation and digest-bound replay are in
[proof-aware-functional-routing](../../../research/proof-aware-functional-routing-2026-09-08/README.md).
An adapter smoke test also passes actual recursive-scope-PCL cards through the
gate: a complete two-branch proof loads, a narrow root abstains, and a fresh
lower-ranked card displaces a stale higher-ranked card. This validates the
composition path only; it is not a semantic or end-task evaluation.
