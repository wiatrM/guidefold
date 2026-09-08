#!/usr/bin/env bash
# SessionStart: point the agent at the entry documents and the project skill index. Prints context only.
cat <<'TXT'
Guidefold repo. Entry: AGENTS.md (skill index) -> docs/DOCUMENTATION-RULES.md (which document is canonical).
Product direction: docs/PRODUCT-PIVOT.md (U1-U11), docs/PIVOT-BACKLOG.md (P01-P15), docs/PRODUCT-FOCUS.md (what we do not do).
Engineering rules: docs/adr/ADR-0032 (hexagonal architecture required; KISS/YAGNI/DRY/SOLID; Definition of Done).
Project skills live in .agents/skills/ and are linked from .claude/skills/. Before coding: product-direction-guard, definition-of-done.
Hooks active (.claude/settings.json): frozen paths, single-file CLI check, hex outside tokens.css, banned UI words, git guard.
TXT
