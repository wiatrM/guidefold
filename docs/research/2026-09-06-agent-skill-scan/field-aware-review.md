# Independent review: field-aware feasibility spike — 2026-09-06

Reviewed `research/spikes/2026-09-06-field-aware/run.py` and `PROTOCOL.md` while document
encoding was running. No experiment code was edited; no model was imported and no GPU work
was started by this reviewer. The initial methodology/code review is followed below by a readout
of completed results and saved QA evidence; no additional model or evaluation run was performed.

Source reviewed: run.py SHA-256
`63049f844cf07d777536ded1790624327db7b614e8594e6ba5ee82e1728438c2`, protocol SHA-256
`2af71da9b421e6690f6a318f3c1cdc8f55da5d27da1684ce17c5658d1198b482`, from the experiment's
initial manifest. Later source/protocol amendments should be dated and distinguished from this
snapshot. The six treatments were specified before outcomes. No retrieval-weight or scientific
setting change is requested on the basis of DEV results.

## Verdict

The code can answer an exploratory question about learned field fusion on these fixed DEV
queries. No blocking numerical error was found in the ranking metrics or paired calculation.
The initial sampling code exposed DEV gold documents as training negatives. That defect was
corrected before any training or DEV evaluation. The corrected implementation excludes blocked
documents from all labelled training pairs and may proceed under the declared known-document,
held-out labelled-skill protocol, subject to the statistical and attribution limits below.

## Corrected before training: negative labels exposed held-out skills

The initial code excluded DEV gold skill IDs and duplicate document IDs when choosing training
queries but subsequently mined negatives from the entire 10,123-document bank. Independent CPU
reproduction of its exact random generator found the following counterfactual exposure from
random negatives alone:

| Exposure the original sampler would have produced | Count |
|---|---:|
| Training negative pairs containing a DEV gold document | 7,347 |
| Distinct DEV gold documents exposed as negatives | 1,793 |
| Total distinct DEV gold documents | 1,832 |

These counts describe the identified bug, not actual training data used for reported results.
The coordinator stopped the first process during body encoding, before features, training or DEV
predictions. The initial manifest remains in `pretraining-manifest-v1.json`, and PROTOCOL.md has
an explicit pre-training correction. No arm, learning rate, epoch count or outcome-based choice
changed. This is an implementation repair before outcomes rather than a new result-driven trial.

I verified the corrected source `run.py` SHA-256
`002f91e942c00bd6d0a97f45eba56263e5449b9ce05cf5562dbbd599759ce687` and protocol SHA-256
`b4c8aac72873c09d5c2eb408532f4e4b8d8e57c50daf18d5c6a3ba9049becd06`:

* `blocked_rows` maps all held-out gold and duplicate document IDs to corpus rows.
* Each training candidate set is `proposed - blocked_rows`, with no replacement negatives.
* An assertion requires zero blocked-row intersection and retains every positive.
* Standardization and model training occur only after this filtering.
* `training-overlap-audit.json` will record excluded pair count and zero remaining labelled-skill
  exposure when that stage executes; at review time encoding was still running.

The correction resolves the holdout defect for exact IDs/full-document duplicates. Reuse of
name/description embeddings is guarded by identical train/DEV IDs and source data/split hashes;
reviewed model, prompt and max length are unchanged. Encoded inputs were not affected by negative
label filtering. The first process had no trained head or outcome to select from.

The valid resulting claim remains narrower than complete cold-domain generalization: held-out
skills are present unlabelled in the document bank and in corpus-only TF-IDF fitting, generic
encoder pretraining is not audited, and semantic near-duplicates may cross splits. A future
confirmation still requires a fresh evaluation set and stronger deduplication if that is its aim.

## Binary nDCG and other metric checks

`metric` computes binary DCG@10 as the sum of `relevance / log2(rank+1)`, with ideal DCG equal
to the first `min(10, number_of_gold)` discounts. Recall@10 divides retrieved gold count by the
full gold cardinality. Hit@1 means any annotated gold document. All-gold injection@4 checks the
set of delivered documents. These definitions are internally consistent and correctly labelled
`ndcg10_binary`, including the historical reference recomputed using the same function.

Independent CPU checks extracted only the metric function from the AST, without executing the
experiment module or importing torch. All100 randomized rankings/gold sets matched a separate
stdlib-math implementation within1e-12. The historical D0 replay contains1,000 records, the
expected `ranked`/`injected` fields, and50 ranked documents each. Thus its schema is compatible
with the recomputation.

Independent reading of training qrels confirmed that all3,000 selected train/DEV query gold sets
match `data/qrels/train.jsonl` exactly (zero mismatches); all5,785 relevant qrels have relevance1.
No test-A/test-B file was read for these checks. Existing historical reports sometimes use graded
3/2 relevance derived from gold order; their printed nDCG numbers must not be compared directly
with these new binary nDCG values. Recomputing the saved baseline ranks, as this code does,
avoids that mismatch.

Metric preconditions are satisfied here: nonempty gold sets and nonempty ranked lists. The helper
would raise on empty rankings/gold rather than treating them as misses; that is not exercised by
these five full-bank, abstention-disabled arms and is not a NO_SKILL evaluation.

## Protocol/code differences and reporting requirements

1. **Candidate union.** The protocol says "rank candidate union capped200". Evaluation actually
   computes each head over every document, sorts the resulting10,123 scores and keeps the first200.
   There is no top-channel union restriction at evaluation. This is consistent across the five new
   arms and is a valid full-bank experiment. Correct the description; it does not yet demonstrate
   the performance of a production top50 candidate-plus-reranker path.
2. **Truncation accounting.** The tokenizer length check measures query text without `PROMPT`, but
   `model.encode` adds the prompt. Queries close to1,024 tokens can be truncated despite the saved
   counter saying otherwise. This does not change the actual query embedding or the equality of
   query embeddings across arms. Label counters as unprompted lengths or calculate actual prompted
   lengths in a read-only reporting pass. Document counts use the actual unprompted inputs.
3. **Reproducibility metadata.** The manifest saves Python/NumPy/torch versions and model config hash,
   but not sklearn, sentence-transformers or transformers versions; it hashes neither tokenizer
   files nor weight files. A pinned directory name is a useful identifier, not an integrity check.
   Save those versions and local artifact checksums before calling the package fully reproducible.
   Imported helper files (`dev_sparse.py`, the CLI) also influence fields and selection but are not
   included in the spike's source hash map. The saved commit identifies committed helpers; record
   whether they are unchanged in the working tree.
4. **Cache reporting.** On cache hits, truncation counters are omitted, and encoding timings become
   cache-read timings. A rerun should not present them as fresh encoding cost. Source/protocol hash
   changes invalidate the cache even for a prose-only amendment; preserve the original manifest
   and report actual cache use if later rerunning.
5. **Time bound.** The30-minute guard is checked inside encoding loops against process start; feature
   scoring/training/evaluation have no equivalent guard. This is acceptable if the stated limit
   means encoding time, but do not call it a hard30-minute bound on the whole experiment.

## Sound choices in the reviewed design

* Generic, locally pinned Qwen rather than the skill-tuned encoder with known SKILLRET training
  exposure; query embeddings shared across all field/flat arms.
* Exact normalized query text exclusion, DEV positive-skill exclusion, deterministic query-ID
  hashing and saved train/DEV IDs. Training and DEV query-ID overlap is zero.
* Corpus TF-IDF fitting uses document text only. Feature standardization uses only training pairs;
  the code does not fit means/scales on DEV queries.
* The same sampled training pairs and label rule feed all three heads; weighted BCE compensates
  class imbalance. Heads share a fixed Adam recipe,30 epochs, batch4096 and seed, with no DEV early
  stopping or tuning. Head sizes are65 (flat),129 (field) and81 (sparse-field) parameters.
* The five new arms share the real `policy_filter` and `select`, with identical explicit
  `abstain_threshold=0`, k4, inherited closure and an assertion that the whole corpus is admissible.
  Here all cards are active, have no negative triggers and no dependency edges. Calling the real
  functions ensures code reuse but does not test difficult policy/graph cases.
* Historical sparse replay is correctly designated descriptive context. Its production candidates,
  scorer and abstention differ, so gains against it are not a clean component ablation.
* The encoder token-budget and query-bootstrap clustering/multiplicity limitations are disclosed.
  Head-only GPU timing is explicitly separated from end-to-end latency.

## Statistical limits on the decision

The primary field-MLP versus flat-MLP contrast and the fixed2pp Recall@10 gate are clear. Paired
query bootstrapping is appropriate for a paired exploratory estimate on these fixed predictions;
it does not account for shared-skill/topic dependence, training-seed variation or model-selection
multiplicity. Reusing this DEV across prior experiments means it is not untouched confirmatory
holdout evidence. A gate pass nominates a fresh experiment; it does not admit a product model.

The field model has129 trainable parameters versus65 for flat, and three separately truncated
representations versus one. Improvements could reflect field semantics, doubled tiny-head
capacity, a larger encoder token budget, or their combination. The sparse-field head is useful
for checking whether dense features add value within this chosen setup. Negative results should
close this fixed configuration while retaining those attribution limits; positive results should
not be advertised as a faithful reproduction of arXiv:2608.02880 or a state-of-the-art result.

The next confirmatory experiment should be designed after this feasibility result, use new holdout
queries, retain the corrected exclusion from positive and negative training pairs, and compare matched
encoder budgets and matched head capacities, and retain a known-document deployment setting as a
separate question. No additional treatment was run as part of this review.



## Completed-results readout

Independently read `results.json`, `qa-results.json` and `training-overlap-audit.json` after the
run completed. No further computation, treatment or evaluation run was requested or performed
for this readout. The conclusion to close this fixed dense field-fusion configuration is justified.

| Fixed arm | Recall@10 | Binary nDCG@10 | All-gold injection@4 |
|---|---:|---:|---:|
| Flat uniform hybrid | 67.83% | 67.23% | 36.9% |
| Flat MLP | 67.72% | 68.03% | 38.5% |
| Field MLP | 64.10% | 64.79% | 36.1% |
| Sparse-field MLP | 67.85% | 67.38% | 38.9% |
| Historical shipped sparse replay | 58.18% | 58.04% | 29.9% |

The predeclared primary contrast, field MLP minus flat MLP, is negative on all four metrics:
Recall@10 -3.62 pp, query-bootstrap 95% CI [-4.75,-2.53]; all-gold injection@4 -2.4 pp
[-3.8,-1.1]. It misses both the required Recall improvement and the completeness guardrail.
The saved `advance_fixed_gate:false` therefore follows directly from the registered rule.
This configuration should not advance to product admission or be retuned on this same DEV.

The result also separates two narrower findings. Training the field head improves Hit@1 and
nDCG over uniform field fusion (Hit@1 +10.4 pp, nDCG +4.58 pp), but does not repair its recall
loss relative to flat representations. Adding dense features to the field MLP in this setup
reduces Recall@10 by3.75 pp [-4.73,-2.77] and completeness by2.8 pp [-4.0,-1.7] relative to the
sparse-field head. These are evidence about the fixed representation/training recipe, not a
general result against embeddings, field-aware retrieval or the referenced paper.

### Status of previously identified correctness issues

Saved QA records5,000 rows,1,000 unique DEV rows for each new arm, with all independently
recomputed metrics matching and source hashes matching. The corrected sampler reports36,953
excluded proposed negative pairs, zero remaining positive/negative exposure of the1,832 blocked
DEV skills. This confirms the executed correction rather than merely the intended source logic.

The prompted-query length audit resolves the earlier query-truncation-counter concern for this
run: maximum291 tokens in train and219 in DEV, with zero over1,024 including the prompt.
Document truncation remains substantial:6,543/10,123 bodies (64.6%) and6,686/10,123 flat documents
(66.0%). This is an actual representation limit, not a metric bug or an excuse to rerun with a
new cutoff after seeing the result. A future full-context or matched-budget study is a separate
question and needs new frozen settings and holdout data.

### Judgment on the proposed next hypothesis

The sparse-field81-parameter head is a reasonable candidate for a new prospective experiment
because it avoids query-time dense encoding and retained competitive point estimates here.
It is not demonstrated to beat flat hybrid: its Recall@10 differs from flat uniform by only
about0.02 pp and from flat MLP by about0.13 pp. No equivalence or noninferiority test was registered
for those comparisons, so similar point estimates must not be described as proven equal quality.
Calling it the "winner" would overstate this exploratory comparison.

The observed38.9% versus29.9% completeness gap against shipped sparse is descriptive. It changes
TF-IDF features, ranking/candidate construction and abstention as well as training. It does not
show that training81 parameters alone causes a9-point improvement. The proposed next experiment
should compare the sparse-field MLP with both a matched uniform three-field sparse baseline and
the unchanged BM25F product path, with query/candidate/selection budgets held fixed. Label the
nomination as a post-hoc research hypothesis; do not grant product promotion from it.

All three heads trained in roughly2 seconds once features existed. Saved head-only GPU p95 is
below0.8 ms for10,123 document pairs. These numbers establish that the fusion head itself is
small and inexpensive on this GPU. They exclude encoder inference, sparse feature generation,
preprocessing, network and hook latency; CPU serving remains unmeasured. Name/description timings
in the resumed run are cache reads, not fresh encoding costs. The resumed wall time of516.6 s
also excludes work already spent by the interrupted pre-training process.

I support the coordinating conclusion: the user's suggestion to test a small trained model was
concrete and experimentally useful; the evidence favors investigating inexpensive learned sparse
fusion next, while closing this particular field+dense configuration. It does not justify saying
that learned fusion is already the MVP default, that a tiny head universally replaces an encoder,
or that arXiv:2608.02880 has been disproved. MVP scope stays sparse Go delivery plus the authoring
and telemetry loop until a fresh prospective experiment and real-user evidence justify a change.
