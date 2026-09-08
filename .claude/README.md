# .claude/ — Claude Code wiring for the Guidefold repository

Status: aktywne, 2026-09-06. Decyzja: [ADR-0032](../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md). Indeks skilli: [AGENTS.md](../AGENTS.md).

| Path | What |
|---|---|
| `settings.json` | Project-shared hooks (checked in). Personal overrides go to `settings.local.json` (gitignored by Claude Code convention). |
| `hooks/*.sh` | Hook scripts. Stdin = hook JSON; `_lib.sh` parses it with python3. Hooks warn or block, never edit files. |
| `skills/<name>` | Symlinks to `../../.agents/skills/<name>`. Skills are authored once in `.agents/skills/` (harness-neutral, the layout Guidefold itself promotes); Claude Code discovers them here by name. |

## Hooks

| Event | Script | Effect |
|---|---|---|
| SessionStart | `session-start.sh` | Prints entry documents and which skills to read first. |
| PreToolUse Edit/Write | `guard-frozen-paths.sh` | Denies edits in `prototypes/industrial-surveyor/` and `prototypes/pipeline-hifi/`; adds a warning for fixture skills, the distributable bootstrap and hook templates. |
| PreToolUse Edit/Write | `guard-tokens.sh` | Denies a hex colour in `ui/src/**` outside `ui/src/tokens/tokens.css`. |
| PreToolUse Bash | `guard-git.sh` | Denies force push, `--no-verify`, commits on `main`; asks before `reset --hard`, `clean -f`, `branch -D`. Matches `git` in command position only (line start or after `&&`, `;`, `\|`); a heredoc line that starts with `git commit` also matches, so write such text with the Write tool. |
| PostToolUse Edit/Write | `check-cli-single-file.sh` | After editing `skills/guidefold/scripts/guidefold`: syntax check and non-stdlib import scan (PyYAML allowed). Failure is reported back to Claude. |
| PostToolUse Edit/Write | `check-slop.sh` | Banned vocabulary from `docs/ui/UX.md` §6 in `ui/`, `docs/ui/` (except UX.md and the pipeline prompt, which quote the list), `prototypes/pipeline-*`, README, PRODUCT-FOCUS, bootstrap skill. Lines that state the rule itself are skipped. |

Test a hook by hand:

```sh
echo '{"tool_input":{"file_path":"prototypes/industrial-surveyor/src/App.jsx"}}' | bash .claude/hooks/guard-frozen-paths.sh
echo '{"tool_input":{"command":"git push --force origin main"}}' | bash .claude/hooks/guard-git.sh
```

## Adding a skill

1. Create `.agents/skills/<name>/SKILL.md` in the format of the existing ones (frontmatter `name`/`description`, Polish body, `Status/Data/Cel/Źródło/Indeks` header, 40–70 lines, links to canonical docs).
2. `ln -s ../../.agents/skills/<name> .claude/skills/<name>`
3. Add one row to the table in `AGENTS.md`.
4. Verify: `python3 tools/check_skills.py` (frontmatter, name = directory, link targets exist, line limits, every skill linked from `.claude/skills` and `AGENTS.md`).
