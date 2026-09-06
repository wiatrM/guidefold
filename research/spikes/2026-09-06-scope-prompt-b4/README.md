# Paired scope prompt experiment, batch4 restart

See [PROTOCOL.md](PROTOCOL.md). Both arms restart on the same32 source-only documents after the batch8 execution encountered GPU memory pressure. The original incomplete run is preserved at ../2026-09-06-scope-prompt/. Do not pool partial and restarted outputs. No Recall@10 is evaluated in this source-only experiment.

## Completed results

Mechanical acceptance on32 paired documents: pseudoqueries38→57, intent phrases57→62, empty docs4→1. The independent8-pair source audit found supported/specific11/28→18/29, weak/generic17→11, and0 unsupported in both among accepted items. Docs with a specific supported item4/8→6/8; nonempty8/8→7/8 because scoped Xcode reached448tokens and invalid JSON. These denominators differ; do not claim universal improvement.

[Semantic review](semantic-review.md), [item labels](semantic-review.json), [mechanical QA](mechanical-qa.json), [generation summary](generation-summary.json). No retrieval claim; no benchmark queries or qrels read by this experiment/reviewer.
