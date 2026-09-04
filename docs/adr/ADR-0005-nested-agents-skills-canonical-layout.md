# ADR-0005: Canonical skill location is nested `.agents/skills/` under the owning directory

**Status:** Accepted · 2026-09-04 · **stands after the 2026-09-04 storage review** (skills remain in the code monorepo, see ADR-0018); generated files are no longer committed (ADR-0012)

## Context
Codex walks from cwd to repo root scanning every `.agents/skills/`; Gemini CLI reads `.agents/skills/` as an interoperable alias; Copilot reads `.github/skills/`; Claude Code reads `.claude/skills/`. A single central `skills/` folder would lose the "nearest skill wins" behaviour and make ownership implicit.

## Decision
Skills live next to the code they govern: `<node-path>/.agents/skills/<name>/`. Root `.agents/skills/` holds org-wide skills and the bootstrap skill. `.github/skills/` and `.claude/skills/` contain only the bootstrap skill (symlink or copy maintained by `guidefold sync-harness`). Everything else is reached through the registry.

## Consequences
- CODEOWNERS for the code path automatically covers its skills.
- Harnesses with native nesting get ambient skills; others get them via `guidefold find` — behaviour is consistent, only latency differs.
- Open question tracked in DESIGN.md Q3: if a harness starts supporting nested skills natively, no change needed.
