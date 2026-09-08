# Frozen pilot: corpus-only query enrichment, 2026-09-06

User explicitly requested continued offline research and LLM metadata enrichment. This is a new bounded research experiment, not product admission. All settings below fixed before generation or ranking results.

## Hypothesis and arms
Vocabulary mismatch can be reduced by offline grounded intent phrases and pseudoqueries. Use the actual shipped Python BM25F/policy/candidates/score/select pipeline, default field weights 6/4/3/5/2, top50 candidates and four selected cards. No new model or LLM at query time.
A original cards; B same cards + up to3 grounded intent phrases in existing triggers; C exactly B + up to3 grounded pseudoqueries in triggers. No original descriptions/bodies, negative_triggers, requires, or policies edited. No weight fitting. B-A estimates metadata-package effect; C-B additional pseudoqueries. Unequal added text length is intrinsic to these treatments, not controlled away; no attribution to quality alone.

## Corpus and exposure
Full 10,123-skill pinned SKILLRET TRAIN bank in every arm. Select512 treatment docs by SHA256(enrichment-v1 + skills-file SHA256 + skill ID), independent of query labels/results. No replacement for failed generation. Partial coverage pilot (~5%), NOT expected effect of enriching the entire bank.
Choose2,048 queries by a separate fixed SHA256 ordering from TRAIN after excluding all3,000 known query IDs in prior field-aware manifest AND normalized duplicate query texts. This is an internal unused-query sample relative to recorded prior run, not a new source/domain or guaranteed never-seen benchmark. Generic model pretraining overlap and older unrecorded experiments unknown. Frozen test-A/test-B not opened or run.
Primary population = all2,048 queries. Predeclared diagnostic strata any_gold_selected, no_gold_selected, all_gold_selected and gold cardinality. Strata use intended512 assignment, not successful generations. No all-gold-only headline; it favors singleton tasks.

## Generator
Local cached Qwen2.5-7B-Instruct a09a35458c702b33eeacc393d103063234e8bc28, fp16, greedy, no fine-tuning, no API calls. Prompt contains only one selected skill name/description and corpus body excerpt. Body budget first1,200 + last400 tokens; name+description first350 tokens. No real query, qrel, ID semantics or retrieval result supplied. Three short intent phrases and three user requests, each with a short verbatim source evidence quote. Strict JSON; max448 new tokens; batch8; deterministicseed20260906. Truncation, failures, generated/input tokens logged. No post-result prompt changes or retry of failed docs.
Filter: parse JSON, bounds (intent2-10words/query5-32words; evidence4-35words), quote must occur in whitespace/case-normalized provided source, remove exact normalized duplicate entries. This is a mechanical provenance filter, NOT an entailment verifier or a guarantee against hallucinated capabilities. Manual blinded semantic spot audit before results.

## Evaluation and gates
Freeze generated sidecar/hash before evaluation. Independently verify qrels, output metrics and unchanged source corpus. Primary Recall@10; guardrails Hit@1, binary nDCG@10, all gold actually selected@4, recall/completeness regressions on no_gold_selected. Paired2,000-replicate bootstrap descriptive95% CI; shared-skill dependence and multiple comparisons caveated. Report helpful/harmful ranking flips, generation costs, original/new index sizes and local search-only timings; no whole-hook/network claim.
Proceed to a NEW full-coverage protocol only if C-A overall Recall@10 delta>0 and CI lower>0, all-gold@4 point delta>=0, and no_gold_selected Recall@10 point delta>=-0.5pp. This gate screens feasibility, not deployment or scientific novelty. B-A and C-B remain diagnostic; no winner-switching to call this gate passed. Failure leads documented diagnosis, not tuning on these2,048 labels. No scientific-breakthrough guarantee.
