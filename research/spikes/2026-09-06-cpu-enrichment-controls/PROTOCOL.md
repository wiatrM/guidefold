# CPU-only enrichment controls, frozen before outcomes

Date: 2026-09-06. Internal sequential research; not external confirmation or product admission.
No GPU access, no new generation, no changes to production code or router weights.

## Fixed data and arms
Full 10,123-skill SKILLRET train bank. Reuse the preceding pilot's fixed 512 assigned skills and 1,603 mechanically accepted generated items. Select 2,048 queries by SHA256("cpu-enrichment-controls-v1" + query ID), excluding the recorded field-aware train/DEV and enrichment evaluation IDs, and all normalized duplicate query texts of those exposed queries. No new training or tuning on these queries. Corpus-level/public-data and shared-skill dependence remain.

A_original: unchanged cards.
B_generated: all accepted intents and pseudoqueries in triggers.
C_roundtrip: retain an item only when its source skill ranks in the top 10 of the ORIGINAL product index when that item text is the query. Threshold fixed at 10. This is a self-retrievability proxy, not an entailment validator.
D_matched_random: deterministic hash selection (salt cpu-random-control-v1) of the same number of items per document AND item kind as C, from B. This matches item counts, not word/token lengths.
E_extractive: for each assigned document take the first N whitespace words of original name + description + stripped original body, where N is its B added word count; append as one trigger phrase. No LLM output or evidence selection is used for text selection. Match whitespace length, report token differences. The prefix choice is fixed, not optimized.

The original index alone determines the C retention mask. Freeze all arm texts and item decisions, with hashes, before evaluating any new query. Fixed order A,B,C,D,E. Product path policy_filter -> candidates(50) -> score -> select(k=4), unchanged defaults. Store top 50 and selected IDs. No skills added/removed.

## CPU execution
Only stdlib plus NumPy for statistics. At most one evaluation process, OMP/BLAS one thread, CUDA_VISIBLE_DEVICES empty. A research-only per-term integer BM25 score cache may reuse the original product scorer for the immutable all-visible index. It must assert all-visible membership, use the product tokenizer and query-term multiplicity, and pass full candidate/score/select equality against the unmodified product router on a preselected hash sample of 64 queries per arm, plus 64 generated items in A. No timing or production-speed claim from this cache. No production file modification.

## Outcomes and decision
Primary contrast C minus B, macro Recall@10. Primary screening criteria: positive mean, two-sided gold-component sign-flip p < .05 after Holm correction across the four planned Recall@10 contrasts below, and nonnegative mean completeness@4. This is a research continuation gate, not a breakthrough or deployment gate. No alpha recycling, no threshold selection after outcomes.
Four planned Recall@10 contrasts: C-B (filter effect), C-D (selectivity vs count removal), B-E (generative versus extractive), B-A (replication). Report all four, including negative results. Descriptive E-A is exploratory. Completeness@4, Recall@50, Hit@1, nDCG@10, first-gold versus companion-gold recall and k=1/2/3 strata are secondary descriptive outcomes; no additional significance claims.

Report paired query bootstrap and gold-connected-component bootstrap 95% percentile intervals (5,000 draws; seeds 202609061 and 202609062). Construct components by shared positive gold skills; preserve query weighting with variable bootstrap denominator. Sign-flip test randomizes sums within these components: exact enumeration for <=20 nonzero components, otherwise 100,000 draws with fixed seed 202609063 and plus-one correction. Shared-gold components do not cover all semantic or corpus dependence. Percentile intervals can mislead for rare changes; show discordant query counts and sign-flip p. Holm across the four planned Recall@10 tests only.

Report overall and assigned-gold/no-assigned-gold/all-assigned-gold strata and gold count. Freeze direction and guard before new outcomes, retain all results. Independent script must reconstruct metrics from rankings and qrels, validate hashes/cohort/arm counts and controls, and independently recompute tests. Single public synthetic train corpus, partial enrichment coverage and no execution/no-skill labels limit claims. Selection by earlier pilot means evidence is sequential and not a registered external confirmatory study.
