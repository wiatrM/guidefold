# ADR-0032: Engineering principles and hexagonal architecture as repository rules

**Status:** Accepted · 2026-09-06 · decyzja właściciela produktu ("Wymagana jest architektura heksagonalna", zasady KISS/YAGNI/DRY/SOLID, Definition of Done).
**Amends:** [ADR-0029](ADR-0029-product-focus-hard-rules.md) rule 7 (KISS review before merge) is generalised into the rules below.
**Governs:** `.agents/skills/*` (project skills), `.claude/settings.json` hooks, every code review in this repository.
**Applies to:** new and modified code in `services/`, `ui/`, the proposed Go API/worker ([PIVOT-ARCHITECTURE](../PIVOT-ARCHITECTURE.md)); the single-file CLI keeps its own constraint (CLAUDE.md) and applies the rules within one file.

## Context

Two working days produced a single-file CLI, a Go SEARCH/USE service in one `package main` (`services/search/main.go`, 22 KB), a React UI extracted from a hi-fi prototype, and a Proposed architecture with six modules and an API–worker contract. The rules that kept these consistent lived in the owner's head, in scattered document sections (UX §6, DOCUMENTATION-RULES, CONVENTIONS) and in ADR-0029 rule 7. Agents dispatched to the repository had no single place that told them how code is expected to be shaped, when a change is done, or when to stop adding.

The owner asked for thirty project skills covering best practices, Definition of Done, refactoring toward KISS, YAGNI and DRY, SOLID, good architecture with hexagonal architecture required, and skills that keep work on the product direction fixed by [PRODUCT-PIVOT](../PRODUCT-PIVOT.md), [PRODUCT-FOCUS](../PRODUCT-FOCUS.md) and [PIVOT-BACKLOG](../PIVOT-BACKLOG.md), plus hooks that enforce the mechanical parts.

## Decision

1. **Hexagonal architecture is required** for the Go API and worker and for the React UI. Domain code defines ports (interfaces) and never imports adapters (HTTP, Postgres, GCS, WorkOS, LLM providers, `fetch`, DOM). Adapters implement ports and are tested by contract; domain logic is tested without I/O. In the CLI, the `Registry` class is the port (ADR-0003) and stays the only path to the registry. Existing `package main` code is migrated incrementally, per touched module, never by a rewrite.
2. **KISS, YAGNI, DRY with the rule of three, SOLID** are review criteria, not aspirations. A PR that adds a component, dependency, configuration key, abstraction used once, or a second variant of an existing UI component states which requirement (U-story, P-id, or explicit owner request) needs it; the reviewer rejects by default.
3. **Definition of Done** is per change type and lives in the `definition-of-done` skill. Common to all: verification commands and their output are in the PR; docs that stop being true are updated in the same change; nothing is committed when the owner requested an uncommitted review; "done" for a feature means used by a real person on a real repository (ADR-0029 rule 3), not green on the fixture.
4. **Product direction is enforced by skills**, not by memory. Every task maps to a U-story and a P-id or is recorded as an explicit scope change through the `scope-change-protocol` skill. Work outside [PRODUCT-FOCUS](../PRODUCT-FOCUS.md) "what we do not do" is declined and written down as a question.
5. **Hooks enforce what a script can check**: frozen paths, single-file CLI constraint, hex colours outside `tokens.css`, banned UI vocabulary, commits on `main`, force pushes. Hooks warn or block; they never edit files.
6. **Skills live in `.agents/skills/`** (harness-neutral, the convention this product itself promotes). `.claude/skills/` contains links to them so Claude Code discovers them by name. The index is `AGENTS.md`.

## Consequences

- Thirty new skills and a `.claude/` directory are added; `AGENTS.md`, `DOCUMENTATION-RULES.md` and `CLAUDE.md` point at them.
- `services/search` does not comply today (single package, handlers holding logic). Compliance is reached module by module as code is touched; no dedicated refactoring epic is opened (YAGNI, ADR-0029 surface freeze).
- The proposed Go API/worker start compliant: `internal/<module>/{domain,ports,adapters,app}` is the expected layout; deviations need a written reason in the PR.
- Reviews get slower on PRs that add things and faster on PRs that remove them. That is intended.
- Skills are instructions for reading and doing; they do not become a second PRD and do not grant permissions ([DOCUMENTATION-RULES](../DOCUMENTATION-RULES.md)).
