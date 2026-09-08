# Paired specificity prompt experiment

A source-only follow-up to the first pilot's semantic audit.32 documents are disjoint from the first512. Both prompts use identical excerpts, model and decoding. The second prompt additionally preserves named technology/workflow scope and asks for direct task requests. No real retrieval-query text or qrels are read.

Run once from the repository root:

```bash
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-scope-prompt/run.py
```

The script refuses to replace its manifest. Read [PROTOCOL.md](PROTOCOL.md). `manifest.json` fixes the32 IDs and8 paired audit IDs before generation; `paired-generation.jsonl` preserves all64 responses and filter results; `source-inputs.json` preserves the exact excerpts, and `generation-summary.json` records counts/cost/hashes. The separate semantic review is required before making a quality claim. Reviewer arm visibility must be disclosed.

This experiment does not evaluate Recall@10. Better-looking metadata on32 documents cannot replace the first retrieval experiment's result or justify production admission. It motivates a separately frozen retrieval test only if source faithfulness and specificity are improved without discarding failures.
