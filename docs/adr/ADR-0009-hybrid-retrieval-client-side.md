# ADR-0009 (v2): The router is Guidefold's index + pipeline; the registry is storage

**Status:** Proposed · 2026-09-04 · v2 replaces v1 of the same day (v1 assumed a small, hierarchy-only library) · [ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) proposes an amendment; the status here is unchanged. · [ADR-0024](ADR-0024-target-architecture-tiers-flywheel-composer.md) (Proposed) proposes an amendment: client-side hybrid becomes tier T0 only
amended by ADR-0015 (Accepted: model choice for the dense/rerank legs)

## Context
Evidence base: DESIGN.md §8.1 (19 papers/systems, checked 2026-09-04).
The target library is 2,000+ skills of mixed kind (generic engineering, corporate, domain,
project, AI-SDLC) and mixed generality, to be delivered general → specific. Scope filtering
alone cannot select among hundreds of generic and corporate skills that are not bound to a
path. Two papers quantify what flat retrieval loses at this scale:

- Graph-of-Skills (arXiv 2604.05333): on 1,000 skills, vector top-k scored below loading
  everything (21.5 vs 27.4); removing the lexical leg and rerank cost the most (34.4 → 26.7);
  removing graph propagation cost 34.4 → 29.3. Dependency edges are built deterministically.
- SkillRouter (arXiv 2603.22455): description-only routing loses 37–44 pp versus body-aware
  embeddings on ~80k skills; listwise reranking (.740) beats pointwise (.433).

Agent Registry (verified live 2026-09-04) offers keyword and dense search as separate calls
with no scores, fusion, reranking, relations or hierarchy, at ~3 s per `gcloud` call and
20 QPS per project. Both papers built their router *on top of* a plain store; no registry
provides one.

## Decision
1. **Index artifact, built in CI** (`guidefold index`): cards, model-generated expansion per skill
   (when-to-use, limitations, tags; cached by body hash), field-weighted BM25 postings, int8
   embeddings (Vertex embedding model, changed-skills-only), and the skill graph (`requires`,
   `refines`, `replaces`, scope, topics, deterministic `similar`). Sharded: `global` (all `_root`
   skills) + one shard per L1 org; distributed via GCS by git sha, pinned by
   `.guidefold/index.lock`, cached locally. `backend: local` builds it in memory.
2. **Pipeline per query** (DESIGN.md §8): where → deterministic anchors + one cached rewrite call
   (intent + sub-tasks, ≤ 600 ms, else skipped) → governance filter (other scopes' `project`/`operations` skills
   out, expired programs out; all other kinds never scope-filtered, provider kinds matched by topics;
   negative triggers) → per-sub-task
   dense top-40 and BM25 top-40 fused by RRF **for recall only** → personalized PageRank over
   the graph → score (dense 0.40, PPR 0.25, lexical evidence 0.15, scope proximity 0.10, BM25
   0.10; golden-set-tuned) → listwise rerank of top-20 with SKIP (always in `find`/UI, in the
   hook only on cache hit) → selection: sub-task coverage backfill, one-hop `requires`/`refines`
   closure, **caps by family** (governance ≤ 2, ways-of-working ≤ 1, engineering ≤ 2,
   knowledge ≤ 3, temporal ≤ 1; ≤ 2 per level; matching policy/compliance never capped out),
   ordered general → specific, ≤ 8 cards, hook injects ≤ 4 → hydration ≤ 12k chars.
3. **Model calls are bounded and cached:** rewrite + query embedding on cache miss in the hook
   (deterministic fallback on timeout), listwise reranker in `find`/UI, expansion and lift in CI.
4. **Caches:** index by sha, queries by hash (sqlite, TTL 7 d), bodies by (urn, revision)
   forever. Registry semantic search is a fallback leg when embeddings are unavailable.
5. **Evaluation is part of the product:** ≥ 60 golden queries on the playground with expected
   URNs and level order; Hit@1, Recall@8, per-stratum recall, stratification score, latency;
   CI gate; nightly on the real registry; ablations for hybrid-vs-dense, hierarchy-aware-vs-flat,
   lint on/off, caps-vs-flat — the stratified ordering is our own, unproven contribution.
6. **Fine-tuned models (SkillRouter / R3-Skill style bi-encoder and reranker) are Phase 3**,
   adopted only if the golden set shows headroom the deterministic pipeline cannot close.

## Consequences
- The CLI stays stdlib + PyYAML; the dense leg is int8 dot products over the filtered set.
- Agent Registry keeps distribution, versions, IAM and audit; nothing in the router depends on
  its search API or its latency.
- The same index feeds the demo UI, so what the demo shows is what the hook does.
- Full design: `docs/DESIGN.md` v0.3 §7–§9, §13.
