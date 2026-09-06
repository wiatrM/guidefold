# Proposed next six-configuration objective study

Status: proposal, not executed or frozen. The current priority is the separately authorized
metadata-enrichment pilot. This objective family should start only when its data/exposure
manifest and all settings have been frozen; no outcomes from the fresh internal holdout may
be used to choose these configurations.

## Data and holdout

1. Pin the10,123-skill corpus, source hashes, code and complete exposure ledger. Exclude the
   previously recorded3,000 query IDs and exact normalized text duplicates from prospective
   evaluation eligibility. Merge any additional known external exposure before sampling.
2. Select1,200 fresh internal holdout queries by stable SHA256(protocol_id,query_id), stratified
   as400 each for k1/k2/k3 and proportionally by first-gold major category. Fix exact tie/order
   handling in code. Save only the frozen IDs/labels; no model predictions until all six arms
   finish fitting. This is a balanced diagnostic population, not natural traffic prevalence.
3. Reserve all holdout gold skill IDs plus exact normalized document duplicates. Exclude them
   from ALL positive and negative training pairs. The documents remain unlabelled in the known
   retrieval bank. Group semantic duplicates if reliable source identifiers are available.
4. Select6,000 training queries by the same independent hash rule from the remainder,2,000 per k,
   after excluding any query whose gold intersects blocked holdout skills. If fewer are available,
   stop before fitting and amend the planned size transparently; do not relax isolation silently.
5. Use the already exposed old DEV only for implementation debugging without choosing hyperparameters.
   All models start from scratch. Public SKILLRET-test and SkillRetBench stay untouched.

## Fixed representations and negatives

Use only sparse TF-IDF similarities for name/description/body, with identical tokenizer, document
bank and fixed IDF behavior across the trained heads. No dense model, generator, new corpus or
query decomposition in this family. A30k collection can later be a separately pinned scale and
distractor stress test; its unlabelled documents must not silently become gold-negative evidence.

Shared pair pool per query: all gold positives, top20 from each of the three sparse channels,
and20 seeded random documents. Remove blocked holdout documents and known exact aliases of gold
from negatives; do not refill. Save counts by k. No arm gets different negatives. Standardization
uses training pairs only. All trainable heads use3->16->1, fixed initialization seed20260907,
Adam lr0.003,30 epochs; no early stopping or alternative seeds selected on holdout. Query-based
arms batch64 queries, accumulating mean query losses, not variable-sized flattened pair batches.

## Six arms, including both controls

| ID | Method | Purpose |
|---|---|---|
| C0 | Unchanged shipped BM25F, same corpus/root scope and k4 | Product reference; scorer differences explicitly retained |
| C1 | Uniform mean of three sparse cosine fields | Matched representation baseline without training |
| C2 | Unconstrained3->16->1, original global class-balanced BCE | Replicated shallow-head recipe on new training split |
| C3 | Same head, query-balanced multi-positive listwise loss | Test a query-aware ranking recipe |
| C4 | C3 plus per-query per-channel standardization | Test robustness to query score-scale differences |
| C5 | C4 with nonnegative effective hidden/output weights | Test monotonic regularization at matched parameter count |

C3 loss for query q with gold P and shared candidates C:

    L(q) = -(1 / |P|) sum_{p in P} log( exp(s_p) / sum_{d in C} exp(s_d) )

Use stable logsumexp and mean L(q) over queries. This is a sampled-candidate multi-positive
softmax objective. It is not exactly a Recall@10 or all-gold@4 loss and is not a claimed ListNet
reproduction. C3 versus C2 changes both query weighting and objective; interpret it as a ranking
recipe, not a causal isolation of loss alone. Pairwise logistic is an alternative for a future
family, not a seventh arm or a replacement selected after seeing this result.

C4 computes each query's field mean/std across the full unlabelled document bank, with fixed
std floor1e-6. Query identity/gold labels are never features. This is available at inference but
adds scoring work; report full latency. In C5 use softplus of unconstrained weight parameters in
both affine layers with ordinary learned biases and ReLU; this guarantees each score is
nondecreasing in each standardized similarity for fixed query normalization.

## Evaluation and decision

All arms retain the same policy and selected-card cap; no calibrated NO_SKILL claim from this
positive-only query set. For new arms use full-bank scoring and report retrieval top10 separately
from actual product selection@4. Keep the production reference's scorer/abstention explicit.

Primary contrast C3-C2; primary endpoint macro Recall@10. Gate for further study: at least+2 pp
with paired95% CI lower bound above0, plus all-gold@4 lower CI above-1 pp and Hit@1 lower CI
above-1 pp. Report k strata, first/companion-gold coverage, and all predictions regardless of gate.
C4-C3 and C5-C4 are prespecified secondary exploratory contrasts; do not pick a secondary winner
as a substitute primary success. If making confirmatory claims across contrasts, use a declared
family correction or a new holdout. Bootstrap query clusters by source/skill group where feasible;
at minimum show query bootstrap and explicitly retain its dependence limitation.

One run per frozen arm. Save every loss curve, source/model hash, normalization vector and output.
No additional configuration on this holdout. A negative primary closes the family; a promising
secondary can only nominate a new pre-registered experiment. No product promotion from this
internal holdout without target-harness latency and paired real-task utility.
