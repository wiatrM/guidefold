# Offline harness refinement

## Candidate contract

Accept a HarnessCandidate only with job outcome, per-phase timing, route snapshot, last valid checkpoint, stable failure taxonomy, redacted failure pattern, proposed change, expected benefit, runtime/cost effect, and reproducible evidence. Remove customer copy, URLs, screenshots, credentials, generated proprietary assets, and personal data unless explicitly licensed for evaluation.

## Evaluation sequence

1. Normalize and deduplicate candidates by root cause.
2. Reject changes that overfit one aesthetic, merely rewrite style, weaken a gate, or hide a failure.
3. Apply the candidate to an isolated harness checkout with immutable source digests.
4. Replay the golden set and hidden holdout with fixed provider and time budgets.
5. Compare quality, preservation accuracy, critical failures, runtime, provider usage, and operator minutes to the current release.
6. Require independent Codex review, Claude review, and operator approval.
7. Create an immutable signed manifest with skill/source digests, evaluation results, canary scope, rollback digest, and expiry/review date.
8. Canary on selected alpha jobs, then promote the read-only release pointer or roll back by digest.
9. Feed accepted lessons back into the smallest owning skill or deterministic runtime contract. Never add a broad prompt rule when a schema default, validator, checkpoint-resume rule, or typed error would solve the failure more reliably.

## Required outputs

- `candidate/redaction-report.json`
- `evaluation/results.json`
- `evaluation/review-codex.json`
- `evaluation/review-claude.json`
- `release/manifest.json`
- `release/rollback.json`

PRIME `autoRefine` and trace sharing remain off. Runtime agents cannot promote. Model-weight training is outside MVP. Promotion fails on holdout regression, weaker security/preservation, missing digests, or unapproved cost/latency increase.

For speed regressions, compare median and P95 phase time, repeated model work, provider wait, retries, and time-to-first-valid-preview against the active release. A candidate that improves taste but pushes the declared tier beyond its wall-time budget needs a separate paid profile, not silent promotion into `fast`.
