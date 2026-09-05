# ADR-0013: A Knowledge API over Cloud SQL holds proposals and evidence; Git keeps skill text; one bot writer

**Status:** Proposed · 2026-09-04 (revised after the storage review) · amends ADR-0001 · [ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) proposes an amendment; the status here is unchanged.

## Context
The lift pipeline, agent proposals, telemetry, provenance and rejection memory had no home in v0.3. A database as system of record for skill text would rebuild GitHub review; the registry is v1alpha.

## Decision
**One database.** Cloud SQL for PostgreSQL 16 with `pgvector`, behind a Knowledge API (Cloud Run), stores candidates, proposals, assignments, gate results, evidence, `knowledge_unit`, telemetry (90 d, hashed principals), rejection memory, provenance, golden-set results, training pairs and a hash-chained audit log; skill embeddings are stored there for offline novelty, dedup and lift candidate search only. The hot path uses the local index shard (int8 vectors, brute force) and never queries the database. No Firestore, no Vertex Vector Search, no BigQuery in the MVP. The code monorepo remains the system of record for `SKILL.md` (ADR-0018). `guidefold-bot` is the only non-human writer to the repo and only on `proposal/*` branches; it never merges. Agent Registry stays downstream of CI.

## Consequences
- Humans never conflict with bots; every model-generated row carries provenance.
- Rebuild-from-git of the DB projections is rehearsed quarterly; the DB is not needed to serve skills.
