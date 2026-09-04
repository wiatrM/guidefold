# ADR-0012: No generated file is committed; L0 cards are delivered at SessionStart

**Status:** Proposed · 2026-09-04 · amends ADR-0006

## Context
Committed generated files were the dominant conflict source in v0.3 and coupled every skill merge to hundreds of directories.

## Decision
Cards, index shards, lock files and CODEOWNERS-derived artifacts are built by CI and served from GCS (`index/<shard>/<sha>/`, `latest.json`). `guidefold card` renders the node card at SessionStart on every harness; `prewarm` materializes cards only into gitignored local paths. Where a harness cannot inject at SessionStart, L0 degrades to the static instructions file plus the L1 hook.

## Consequences
- Zero synthetic conflicts; merged skills reach hooks within the `latest.json` TTL (≤ 10 min).
- Copilot launched from the repo root without hook injection sees less L0 context than in v0.3; accepted.
