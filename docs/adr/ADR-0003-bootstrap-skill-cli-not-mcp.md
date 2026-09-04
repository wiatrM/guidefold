# ADR-0003: One bootstrap skill + CLI instead of per-harness MCP configuration (MVP)

**Status:** Accepted · 2026-09-04

## Context
Four harnesses are in use (Copilot CLI/IDE, Claude Code, Codex, Gemini CLI). Agent Registry exposes a remote MCP server (`https://agentregistry.googleapis.com/mcp`, OAuth/IAM), but its documented discovery tools cover agents, MCP servers and endpoints — skill search/get tools are not documented. Each harness has different MCP + OAuth setup; supporting all four is ongoing work we don't want in MVP.

## Decision
Ship a single Agent Skill, `guidefold`, whose SKILL.md instructs the agent to run a bundled script: `guidefold where | find | load`. The script wraps `gcloud alpha agent-registry skills search` (semantic + URN prefixes) and the revision payload download, using the developer's existing gcloud credentials. The same skill directory is exposed to every harness (`.agents/skills`, `.github/skills`, `.claude/skills`, `~/.copilot/skills`).

## Consequences
- Zero per-harness configuration; onboarding = "install gcloud, run `gcloud auth application-default login`".
- Discovery quality is the registry's; we only add scope ranking.
- If the MCP server gains skill tools, `find/load` can be switched to MCP without touching SKILL.md.
- Trade-off: script execution must be allowed in the harness (all four support skill scripts today).
