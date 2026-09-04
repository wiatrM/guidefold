# ADR-0007: Claude Code on Vertex AI (Model Garden) is the reference harness; one gcloud identity for model + registry

**Status:** Accepted · 2026-09-04

## Context
the design partner is on GCP with Gemini Enterprise and Model Garden; the team plans to move from Copilot to Claude Code with Claude served through Vertex AI. Claude Code supports Vertex natively (`CLAUDE_CODE_USE_VERTEX=1`, `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, Application Default Credentials) and supports hooks that inject context, remote MCP with OAuth, and enterprise-managed settings.

## Decision
- Claude Code on Vertex is the reference implementation for L0+L1+L2; Copilot and Codex are supported at L0+L2 (L1 where hooks allow).
- Authentication for everything (model calls, `gcloud alpha agent-registry skills search`, payload download, later the registry MCP) is the developer's ADC from `gcloud auth application-default login`. No API keys, no per-tool tokens.
- Hook config (`.claude/settings.json`) and the bootstrap skill are pushed via Claude Code managed settings once the pilot passes; until then they are committed in the repo.
- Gemini/ADK agents consume the same registry natively (`list_skills`/`load_skill`, governed by Agent Skills Lifecycle policies) — no adapter.

## Consequences
- Zero custom services for the Claude Code path; the only optional service in the whole design remains the ARD façade for Copilot Agent Finder.
- Vendor lock-in is limited to distribution (Agent Registry) and hosting (Vertex); skills stay portable SKILL.md in Git.
- When the registry MCP exposes skill tools, `find/load` switch from CLI to MCP in Claude Code by config; SKILL.md and cards do not change.
