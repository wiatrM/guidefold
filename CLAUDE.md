# Guidefold — project instructions

Git-native skill CI for a monorepo. Skills (`SKILL.md` dirs) live next to the code they govern,
CI validates and publishes them to Google Cloud Agent Registry, and one bootstrap skill + a tiny
CLI let any harness (Claude Code, Copilot CLI, Codex, Gemini CLI) discover them by location.

Read `docs/DESIGN.md` (v0.3) first, then `docs/CONVENTIONS.md`. Decisions are in `docs/adr/`;
ADR-0008..0010 are Proposed. `docs/ASSESSMENT.md` holds every verified fact about the registry API.

## Layout

| Path | What |
|------|------|
| `skills/guidefold/` | **The distributable unit.** Bootstrap `SKILL.md`, `scripts/guidefold` (CLI), `hooks/*.json` (harness hook templates). This whole dir is what a consumer monorepo copies to `.agents/skills/guidefold/`. |
| `docs/` | Design doc, conventions, ADRs, assessment. |
| `templates/` | Files a consumer monorepo copies: CI workflow, example `guidefold.yaml`. |
| `examples/monorepo/` | "Meridian" playground: fictional Palantir-style data platform, 17 nodes / 26 skills / stub code, `registry.backend: local`. Fixture for demos and tests. |
| `tests/` | pytest suite (to be built). |

Two repos are involved and must not be confused: **this repo** (the tool) and the **consumer
monorepo** (where `guidefold.yaml`, `.agents/skills/**`, generated `AGENTS.md` cards and the
CI workflow live). `templates/` and `skills/` are copied into the consumer; nothing else is.

## Hard constraints (from the design)

- `scripts/guidefold` stays a **single-file Python 3 script, stdlib + PyYAML only**. It ships
  inside the skill ZIP to the registry, so no package layout, no third-party deps.
- Git is the source of truth; the registry is a build artifact (ADR-0001). Never design a
  flow that edits the registry by hand.
- Generated files (`AGENTS.md`, `CLAUDE.md`/`GEMINI.md` one-liners, `.github/instructions/*`,
  `_index-hierarchy` skill) are produced only by `guidefold materialize` / `index`.
- Scope cards are capped at 80 lines. Digests only, no procedures.
- All registry access goes through the `Registry` class in the CLI so it can be swapped for
  MCP or an ARD endpoint later (ADR-0003).
- Preview API: `gcloud alpha agent-registry skills ...` — pin the gcloud version in CI.

## Working here

- Run the CLI: `cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold <cmd>`.
  The monorepo root is the nearest ancestor with `guidefold.yaml` (or `$GUIDEFOLD_ROOT`).
- Real registry: GCP project `guidefold-test-b6a18a`, location `global`, needs
  `roles/agentregistry.admin`. Publish flow and ID mapping: `docs/adr/ADR-0008-*.md`.
- Tests: `pytest` from repo root (once `tests/` exists). Registry calls must be mocked; never
  hit GCP in unit tests.
- Syntax check: `python3 -m py_compile skills/guidefold/scripts/guidefold`.
- New decision → new `docs/adr/ADR-000N-<slug>.md` (same format as existing ones).
- Keep `docs/DESIGN.md` and `docs/CONVENTIONS.md` in sync with the CLI's behaviour.

## Naming

- Node: dotted path from `guidefold.yaml` (`mosaic.identity.turnstile`); root is `_root`.
- URN: `urn:skill:<publisher>:<node>:<skill-name>` — derived, never hand-written.
- Skill `description` starts with `[node/path]`; root uses `[sabre]`.

## Relevant installed skills (global, `~/.agents/skills`)

Invoke via the Skill tool when the task matches. Reinstall with `npx skills add <repo> --skill <name> -g -y`.

| Skill | Repo | Use for |
|-------|------|---------|
| `skill-creator`, `skill-development` | anthropics/skills, anthropics/claude-code | authoring/reviewing `SKILL.md`, frontmatter rules `validate` must enforce |
| `agent-platform-skill-registry` | google/skills | Google's own skill for the Skill Registry API (search/upload/revisions/LROs) — cross-check with `gcloud alpha agent-registry` |
| `gcloud` | google/skills | safe `gcloud` invocation patterns, auth, `--format` flags |
| `hook-development` | anthropics/claude-code | `SessionStart`/`UserPromptSubmit` hook contract for the `hook` subcommand |
| `python-testing-patterns` | wshobson/agents | pytest fixtures, mocking `subprocess`, tmp repos |
| `github-actions-templates` | wshobson/agents | the consumer CI workflow in `templates/` |
| `create-agentsmd`, `copilot-instructions-blueprint-generator` | github/awesome-copilot | reference for `materialize` output (AGENTS.md, `*.instructions.md` with `applyTo`) |
| `architecture-decision-records` | wshobson/agents | new ADRs in `docs/adr/` |
| `mermaid-diagrams` | softaworks/agent-toolkit | diagrams in `docs/DESIGN.md` |
| `mcp-builder` | anthropics/skills | Phase 2+ MCP server, if the registry never exposes skill tools |

Already installed from before and also relevant: `superpowers:*` (brainstorming, tdd, writing-plans), `tdd`, `codebase-design`, `writing-great-skills`, `setup-pre-commit`.
