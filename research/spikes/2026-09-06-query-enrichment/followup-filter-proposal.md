# Follow-up proposal: expansion filtering and scope retention

Prepared before this pilot's retrieval outcomes. This is a proposed next experiment, not a change to the frozen current run. No classifier, filter, generation, or evaluation is executed here.

A round-trip BM25F check is cheap and corpus-only, but it measures lexical self-retrievability rather than semantic support. Score each generated item as a query against the ORIGINAL 10,123-document index, with no generated text in any document. Retain the item only if its originating skill appears in the top 10 under the frozen product candidate/scoring procedure. Do not apply the filter to an already expanded index: the item would directly improve its own source's match, creating a circular criterion. Do not use real evaluation queries or labels to choose the cutoff.

Doc2Query-- uses a relevance model to score document/generated-query pairs; its official code exposes QueryScorer and QueryFilter. A sparse round-trip cutoff is a different proxy, so call it a low-cost alternative rather than a reproduction. [Paper](https://arxiv.org/abs/2301.03266), [official implementation](https://github.com/terrierteam/pyterrier_doc2query).

There is a concrete reason to expect a precision/recall trade-off: a SIGIR 2024 reproduction found that filtering could preserve or improve early precision while harming recall. [Mansour et al., 2024](https://jmmackenzie.io/pdf/mzzm24-sigir.pdf), [authors' code](https://github.com/175edda-sps/d2qminus-repro). My inference for Guidefold is that original-index self-retrieval will favor documents that were already easy to find and phrases with familiar vocabulary, potentially discarding the useful unfamiliar synonyms that expansion is intended to add. It can also retain a misleading phrase if a distinctive copied token retrieves the document. Duplicate or closely related skills can cause a good phrase to fail an arbitrary top-10 boundary. These mechanisms must be measured, not assumed to be failures in the current pilot.

Use the existing frozen 512-document assignment and 1,603 accepted items for a bounded CPU-only filter experiment. Keep the full 10,123-document bank and unchanged BM25F/policy/selection settings. Suggested six configurations:

| Arm | Content added to existing triggers |
|---|---|
| A | None: original product baseline |
| B | All accepted metadata and pseudoqueries from the completed pilot |
| C | B filtered by original-index own-skill top 10 |
| D | Matched random removal: for each document and item kind, retain exactly C's count, chosen by fixed hash rather than score |
| E | B plus a source-grounded scope prefix per item, where a scope anchor exists |
| F | C plus the same scope prefix; decide retention before adding the prefix |

D distinguishes selective filtering from simply removing text and changing field normalization. It is a diagnostic single fixed random realization, not an estimate over all random filters. Apply C to all accepted item kinds; additionally report retention separately for intents and pseudoqueries. Keep all 512 documents assigned even if their retained count is zero.

The scope variants need an additional corpus-only annotation step before they are runnable. Freeze a sidecar with at most one explicit organization/platform/framework qualifier (up to six words) per document, linked to a verbatim span in the source supplied to the generator. An independent reviewer must validate that it is a positive applicability restriction, not an example, dependency, excluded platform, or merely a rare token. If no clear qualifier exists, use no prefix and report anchor coverage. Examples of the intended distinction are Dafthunk workflow nodes and BTDP IT masterdata; simply adding the document UUID or rare title words is not a scope-preservation intervention. Keep the original phrase; prepend the qualifier without silently dropping vocabulary. Do not infer anchors from a query, a gold label, or the round-trip result. If these annotations cannot be completed within the agreed budget, run A-D only and retain E-F as a separate prospective proposal.

Use a new internal TRAIN holdout, selected by a fixed new hash salt, excluding all previously exposed query IDs and normalized texts, including the current 2,048 and prior 3,000. Freeze size, IDs, anchor sidecar and filter outputs before evaluation. The existing exposed cohorts can serve only as labeled diagnostic/regression sets, not the decisive fresh result. The public test sets remain untouched. Sharing the same public TRAIN corpus still limits independence.

Prespecify C-B as the primary filter contrast: overall macro recall@10 with paired query and shared-gold component intervals, plus all-gold-selected@4. Report A as context; C-D, E-B and F-C are secondary. If using an advancement rule, freeze it before results: positive C-B recall@10 with a positive lower 95% bound and nonnegative completeness point change. Smaller indexes with a recall loss are a measured cost/quality trade-off, not automatic admission. Report candidate recall@50 as a diagnostic, k=1/2/3 completeness and companion-gold recall, any/no/all assigned-gold strata, and documents/items/bytes retained.

Before seeing real query outcomes, log each item's original-index source rank, original-source lexical overlap, novel token count, item kind and source length. After evaluation, compare retention against scope-audit labels and these measures to expose easy-document/paraphrase preference. Self-retrieval success must never be reported as user-query recall or semantic faithfulness. No novel-method or paper-ready claim follows from this small pilot alone.
