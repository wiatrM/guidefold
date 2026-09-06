# Offline skill metadata and pseudoquery enrichment

This experiment addresses the user-requested question: improve skill representations before adding30k documents or training a larger ranking head. It uses a local cached Qwen2.5-7B model for index-time generation and the unchanged Python product BM25F pipeline for evaluation. No generated skill instructions are executed.

## Reproduce

Read [PROTOCOL.md](PROTOCOL.md). Run from the repository root with the existing research GPU environment:

```bash
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-query-enrichment/run.py prepare
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-query-enrichment/run.py generate
# Complete the blinded semantic audit of fixed16 IDs before evaluation.
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-query-enrichment/run.py evaluate
```

`prepare` refuses to replace a frozen manifest. `generate` refuses to replace a finished freeze. To rerun a completed experiment preserve this directory and use a separate run directory/protocol; do not delete provenance. Generation can resume only frozen input order; independently reconcile raw/sidecar IDs if a process was interrupted during writes. A hard-killed incomplete line is not silently repaired.

## Outputs

- `manifest.json`: source and protocol hashes, selected512 skill IDs and2,048 query IDs, known3,000-query exposure exclusion.
- `generation-raw.jsonl`: local model outputs and per-document token/failure records.
- `enrichment.jsonl`: accepted intent phrases and pseudoqueries with evidence quotes. This is a research sidecar, not a modified or installed SKILL.md pack.
- `generation-freeze.json`: immutable sidecar/input/model/run hashes, generation accounting.
- `rankings.jsonl.gz`, `results.json`, `timings.json`: three paired arms, original bank unchanged, primary and diagnostic cohorts. Ranking results exist only after generation freeze and semantic audit.
- `corpus-quality.json`: structural audit, not execution correctness or semantic deduplication.
- `pre-evaluation-qa.json`, `review.md`: independent pre-result audit and fixed semantic sample.
- `cache/`: ignored source excerpts and selected evaluation text. Generic model weights remain in the existing model cache.

The pilot enriches only512 of10,123 documents. It estimates a partial-coverage intervention; neither a positive subgroup nor an overall difference establishes the effect of full enrichment. No weights or prompts are tuned on these queries. Search timing is local Python only. See the [strategy](../../../docs/research/2026-09-06-agent-skill-scan/data-and-enrichment-strategy.md).

## Final readout

[Results and decision](../../../docs/research/2026-09-06-agent-skill-scan/query-enrichment-results.md). Independent QA reproduced6144 rows and84 contrast cells. Recall10 improved0.162760pp on5 queries with no recall regressions; completeness improved0.146484pp on3 singleton cases, no multi-skill completeness improvements. The frozen bootstrap screening gate passes, while posthoc exact two-sided sign-flip gives p=.0625 forrecall and .25 forcompleteness. This is a small, fragile internal partial-coverage signal. See [review.md](review.md) and [posthoc-fragility.json](posthoc-fragility.json).
