# Additional related work for the proposed round-trip filter

This note adds literature context only; it changes none of the proposed configurations or current experiment settings.

Round-trip consistency already appears in Promptagator: an initial dual encoder trained on synthetic examples retains generated query/document pairs when the source document ranks within a fixed top-K. That is synthetic training-data filtering, whereas our proposed BM25F check filters document expansions. It is related prior art, not an identical pipeline. [Promptagator, ICLR 2023](https://openreview.net/pdf?id=gmL46YMpu2J).

A more direct lexical example is RaDeR (EMNLP 2025): for its term-matching synthetic training data, it keeps generated queries only when BM25 retrieves the associated theorem in the top 20. The authors explicitly describe the resulting queries as having large term overlap. This reinforces the need to measure lexical novelty and lost vocabulary bridges in our proposed top-10 filter. The theorem-retrieval training setting and cutoff do not validate top 10 for Guidefold skill expansion. [RaDeR, official ACL paper](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-main.1011v2.pdf).

Neither generic round-trip filtering nor a BM25 own-document cutoff is a novel research contribution by itself. A potential Guidefold contribution would require evidence about applicability-scope preservation, complete multi-skill retrieval and operational costs, with matched controls and an independent prospective evaluation.
