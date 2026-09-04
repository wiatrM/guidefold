# ADR-0006: Deterministic context delivery — materialized scope cards + hooks, not model-decided skill activation

**Status:** Accepted · 2026-09-04 · amended by ADR-0012 (L0 cards are rendered at SessionStart, not committed)

## Context
v0.1 assumed the model would activate the `guidefold` bootstrap skill whenever a task might need org guidance. Skill activation is a model decision over a description and is known to be unreliable at scale. The team's current workaround — launching Copilot CLI inside the team directory so only that team's context loads — shows the real requirement: context must arrive **general → specific by location**, without the model having to ask for it.

Facts checked:
- Copilot CLI discovers instruction files along cwd → repo root and in directories nested on the path of files it works on; `*.instructions.md` with `applyTo` are path-scoped. From the repo root, nested `AGENTS.md` off the cwd→root path are not loaded until a file there is touched (copilot-cli #3051).
- Copilot CLI hooks exist (`sessionStart`, `userPromptSubmitted`, …) but config-file `userPromptSubmitted` output is dropped, so hooks cannot inject context there.
- Claude Code loads `CLAUDE.md` from cwd ancestors at start and nested `CLAUDE.md` lazily when reading files in that directory; `SessionStart`/`UserPromptSubmit` hook stdout is added to context.
- Codex merges `AGENTS.md` root → cwd and scans nested `.agents/skills`; Codex has Claude-Code-style hooks (context injection to verify).

## Decision
Three layers, in order of trust:
1. **L0 — materialized scope cards.** CI generates per node: `AGENTS.md` (node digest + inherited ancestor digests + skill URNs), `.github/instructions/<node>.instructions.md` with `applyTo` = node paths (same content), and one-line `CLAUDE.md`/`GEMINI.md` (`@AGENTS.md`). Every harness loads these by path. No LLM in generation; digests come from skill `description`/`metadata.digest`.
2. **L1 — prompt-time find via hooks** where the harness injects hook output (Claude Code, Codex, Gemini CLI if verified): `guidefold hook` reads the prompt + cwd, runs `find`, prints top-3 cards. For Copilot, the L0 card instructs the agent to run `find`; `sessionStart` pre-warms the cache.
3. **L2 — load on demand** via the bootstrap skill, unchanged.

## Consequences
- Copilot CLI can be launched from the repo root or from the node directory; both yield the same chain. The node-directory habit stays valid and fastest.
- Root context ("what is the design partner / the monorepo") is always present as a digest (L0) and available in full on demand (L2); heavy root skills never load implicitly.
- Generated files are committed and checked (`materialize --check`); hand-editing them fails CI.
- Context cost is bounded: cards are capped by CI; procedures live in skills, not cards.
