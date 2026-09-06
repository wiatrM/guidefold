# Bounded metadata/pseudoquery enrichment pilot — protocol proposal

This is the current user-authorized experiment to execute before the separate objective-family
proposal. The coordinating agent owns the actual frozen protocol/script. This document explains
how partial document coverage can be evaluated without selecting documents from evaluation gold.

## Generator and document selection

Pin the existing10,123-document bank and select512 document IDs by
SHA256(protocol_id, source_snapshot_sha256, skill_id), with no query or gold information in the
selection rule. Freeze IDs and original texts first. All remaining9,611 documents stay unchanged.
Do not reduce the search bank to the enriched subset.

Use the local pinned Qwen2.5-7B model. The generator receives only original document name,
description and body, plus a fixed instruction to extract applicability metadata and produce
three realistic task paraphrases supported by that document. No evaluation query, qrel, retrieval
result or model error is supplied. Pin sampling parameters, input truncation, output token limit,
batch size, model/tokenizer hashes and the JSON schema before generation. Do not regenerate
weak-looking metadata after seeing retrieval outcomes.

Prefer one structured record with bounded trigger phrases, applicability terms, three pseudoqueries,
and exact evidence quotes from the supplied document. Validate JSON type/length, quote substring
membership and absence of generated executable instructions. Exact quotes establish provenance,
not full semantic correctness; independently inspect a fixed hash-selected sample for unsupported
terms, wrong applicability and metadata copied from embedded instructions. Record generator errors
and unsupported records. Invalid output yields an empty augmentation, retaining the document in
its originally selected cohort; do not replace it with a more convenient document.

Store all enrichment as experiment artifacts; do not rewrite source SKILL.md, owner/status/policy
fields or the production index. Freeze output and validation hashes before evaluation starts.

## Three fixed scoring arms

| Arm | Retrieval score |
|---|---|
| E0 | Original matched flat TF-IDF cosine |
| E1 | max(original cosine, metadata-field cosine) |
| E2 | max(original cosine, metadata cosine, pseudoquery1 cosine, pseudoquery2 cosine, pseudoquery3 cosine) |

Only selected documents have augmentation fields. Empty augmentation fields contribute no score.
Use a fixed TF-IDF construction and full original bank across arms. Freeze whether augmentation
channels share the original vocabulary/IDF or fit their own document-only vocabulary; the latter
admits new vocabulary but changes channel statistics. Do not choose it from evaluation results.
Record the exact choice. No weights, learned calibration, thresholds or additional arms in this
pilot. MAX is a transparent fixed rule that preserves each document's original numeric score;
it does NOT preserve its rank, because other documents can receive larger boosts.

E2 has more opportunities to match because it has three pseudoqueries. That is a deliberate
system-level treatment and its compute/storage cost must be reported; it is not a pure isolated
semantic-quality comparison. A matched sum/mean/MAX sweep would be a separate family, not a
post-hoc continuation after the better result is known.

All arms retain identical policy, complete document bank, card budget and actual selection code.
Report retrieval metrics and injected-set metrics separately. Positive-only corpus labels cannot
support a NO_SKILL or calibrated-abstention claim.

## Fresh evaluation without gold-conditioned document selection

Merge the recorded exposure inventory with other known experiments. Exclude old fit/DEV IDs and
exact normalized query duplicates. Select a new fixed internal holdout of1,200 query IDs,400 each
for k1/k2/k3, proportionally stratified by first-gold major and ordered by a frozen hash. This
balanced population is a diagnostic target; report natural source-weighted estimates separately
only if weights were frozen. Public test-A/test-B remain untouched.

After document and query selection, but BEFORE any retrieval outcome, partition the fixed holdout:

* `any_gold_augmented`: at least one annotated gold belongs to the512 selected documents.
* `no_gold_augmented`: no annotated gold belongs to that cohort.
* `all_gold_augmented`: every annotated gold belongs to that cohort; subset of the first group.

Report all three plus overall and k strata. Selection uses the ORIGINAL512 cohort, including
failed generation outputs, so treatment success does not choose the evaluation subset. The
untouched-gold group is essential: new metadata can steal rank from a correct unaugmented skill.
A positive targeted-subset delta cannot excuse worse overall/collateral outcomes.

The primary estimate is the paired E1-E0 difference on the full holdout. E2-E1 is a prespecified
secondary incremental-pseudoquery contrast. Report CIs, counts and coverage, with no claim that
512-document partial augmentation estimates a fully enriched10k bank. Low exposure can dilute
the overall effect; lack of significance is not evidence that metadata can never help.

A supplementary targeted diagnostic may be preregistered for power: up to600 additional fresh
queries,200 per k, with `any_gold_augmented`, selected by hash from remaining eligible TRAIN
queries before outcomes. Keep it separate from the primary full holdout and label the estimand
as conditional on augmentation touching at least one gold. Do not select ONLY all-gold-contained
queries and then present their result as whole-bank performance; that heavily favors single-skill
and unusually concentrated multi-skill queries. If a stratum has too few examples, keep all
available and report n rather than changing document selection to manufacture coverage.

## Pilot decision and stopping

Freeze one primary retrieval metric, recommended macro Recall@10, with paired query-bootstrap95%
CI. Use overall completeness@4 and no-gold-augmented Recall/completeness as guardrails. With
partial coverage this is a feasibility pilot: preserve positive, null and negative outcomes,
per-stratum intervals, generator validation failures and cost. No paper/product claim from a
small conditional subgroup or an uncorrected search across arms/strata.

Choose a fixed local generation deadline and no cloud/API fallback. If the job ends before all
512 documents complete, retain the original cohort and report incomplete coverage, available
output count and failure reasons. Do not spend extra retries selected by retrieval quality.
An incomplete run may diagnose operational feasibility; it must not silently masquerade as the
full frozen512-document treatment. No queries can be used to improve the generator mid-run.

Useful deliverables: selected document IDs, fresh query split, exact generator prompt/config,
raw structured outputs and evidence-validation flags, deterministic transformed representations,
all three per-query ranked/injected lists, paired metric report, no-gold collateral analysis,
wall/GPU time and bytes/index growth. These make the experiment auditable regardless of outcome.
