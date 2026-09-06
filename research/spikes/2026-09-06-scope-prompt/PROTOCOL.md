# Source-only specificity prompt ablation

Frozen before this generation. Motivation: the first pilot blind source audit found18 weak/generic of44 accepted items, often missing platform/workflow scope. This does not establish a retrieval regression. Main retrieval results have not been read or used.

Select32 documents by SHA256(scope-prompt-v1 + corpus-file hash + ID), excluding all512 first-pilot documents. Compare original prompt versus same prompt plus explicit scope-preservation and direct-task-request instructions. Same source head/description/body excerpt, model revision, decoder(max448/greedy/fp16), batch8, mechanical evidence filter. No real query text, qrels or ranking outcomes supplied to either arm; no changes to the original experiment.

Choose8 paired documents for manual review by SHA256(scope-audit-v1 + ID), before generation. Reviewer labels individual accepted items supported/specific, weak/generic or unsupported, and records empty/parse failures. Retain all32 assigned docs and both arms, no retry or replacement. Review both outputs against the same supplied source, using anonymized A/B labels where practical; reviewer must disclose if arm identity is known. Report counts by document and item; item totals can differ and are not equal-size denominators. Mechanical acceptance counts do not measure semantic quality. No statistical power claim from8 documents.

This is a prompt-package feasibility test, not a ranking test or proof of recall improvement. A better semantic result would nominate a new separately frozen retrieval experiment; it cannot replace the original pilot's primary C-A gate. No experiment-driven production metadata changes.
