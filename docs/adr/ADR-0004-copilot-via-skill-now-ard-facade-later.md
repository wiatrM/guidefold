# ADR-0004: Copilot integration — bootstrap skill now, ARD façade for Agent Finder in Phase 2

**Status:** Accepted · 2026-09-04

## Context
GitHub Agent Finder discovers skills at runtime from GitHub's catalog or a private registry implementing the ARD spec (`ai-catalog.json` + `POST /search`), governed by enterprise managed settings. Google's Agent Registry participates in the ARD federation but does not document a customer-facing ARD search endpoint yet. Private MCP registries in Copilot apply to CLI/IDE, not to cloud agents.

## Decision
MVP: Copilot uses the `guidefold` skill (ADR-0003) placed in `.github/skills/` and optionally `~/.copilot/skills/`.
Phase 2: deploy a stateless Cloud Run service ("ARD façade", ~200 LOC) exposing `GET /.well-known/ai-catalog.json` and `POST /search`, translating ARD queries into Agent Registry skill search (semantic) and returning ARD entries with URN, scope and owner. Point Agent Finder at it via managed settings. The façade also serves any other ARD client.

## Consequences
- Day-one Copilot support without waiting for Google's ARD endpoint.
- The façade is the only custom service in the whole design and is optional.
- If Google ships an ARD endpoint for Agent Registry, the façade is deleted.
