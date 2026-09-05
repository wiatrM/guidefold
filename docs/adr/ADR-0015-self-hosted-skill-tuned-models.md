# ADR-0015: Skill-tuned open models, self-hosted, from Phase 1

**Status:** Accepted · 2026-09-04 (approved: use public models now, build own later) · amends ADR-0009 · [ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) proposes an amendment; the status here is unchanged.

## Context
Public skill benchmarks show skill-tuned 0.6B embedders beat their base by 12–19 nDCG@10 (SkillRouter-Emb 73.54, SKILLRET-Emb 81.12, base 61.94) and MTEB rank predicts skill retrieval only at ρ = 0.70. Index and query embeddings must come from the same model. `pipizhao/SkillRouter-Reranker-0.6B` is the only released skill reranker. All are Apache-2.0.

## Decision
Phase-1 bake-off on our golden set between `pipizhao/SkillRouter-Embedding-0.6B` and `ThakiCloud/SKILLRET-Embedding-0.6B`; the winner embeds the index in CI and serves queries from a Cloud Run GPU (L4) endpoint, with a local daemon (`guidefold serve`) as laptop fallback. `SkillRouter-Reranker-0.6B` reranks top-20 in `find`; a Gemini Flash-Lite listwise call only behind `find --deep`. Fine-tune once ≥ 2k accepted (query, skill) pairs exist or golden nDCG@10 < 0.75. Managed embedding APIs only if the org refuses to host a model, accepting the quality loss.

## Consequences
- ~$500/month per 24/7 replica; fine-tuning < $5 per run.
- `training_pair` rows from accepted/rejected proposals feed later fine-tuning.
