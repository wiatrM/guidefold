---
title: Harnesses
description: What each agent tool gets, and how.
---

Guidefold has two ways to reach an agent. A hook runs at the start of a session and prints the ranked cards. Files on disk carry the same cards for tools that read a folder but cannot run a hook. `guidefold install` sets up both.

| Harness | Hook | Files on disk | Full text |
|---|---|---|---|
| Claude Code | `.claude/settings.json`, SessionStart and UserPromptSubmit | `CLAUDE.md` in each scope folder points at `AGENTS.md` | `guidefold load <urn>` |
| GitHub Copilot | `.github/hooks/guidefold.json` | `.github/instructions/<scope>.instructions.md` with `applyTo` globs | `guidefold load <urn>` |
| Codex | `.codex/hooks.json` | `AGENTS.md` in each scope folder, nearest wins | `guidefold load <urn>` |
| Gemini CLI | none | `GEMINI.md` in each scope folder points at `AGENTS.md` | `guidefold load <urn>` |

## The hook

The hook is the same Python file for every harness. It reads a pre-built index for the current commit and nothing else: not `guidefold.yaml`, not the rule files, not YAML at all. That keeps it fast (about 100 ms at 500 rules) and safe to run on every prompt. On any failure it prints nothing and exits cleanly, so a broken index never breaks a session.

It prints at most four cards, general first. If the scope has a map above it (see [Knowledge ascent](/knowledge-ascent)), that map is the first card.

The index is built by `guidefold index`. `install` runs it once; CI or a git hook should run it again when rules change, because the index is tied to a commit.

## The files on disk

`guidefold materialize` writes one card per scope. The card lists the scope, its owner, the chain above it, and every rule visible from there with its summary. If any scope above has a map, the card opens with a "Scope map" section, so a tool that only reads files still learns the shape of the organisation first.

These files are generated. Do not edit them; edit `guidefold.yaml` or the rules and run `materialize` again. `materialize --check` in CI fails when they are stale.

## Loading the full text

Whichever way the agent got the card, the full text comes from one command:

```bash
python3 .agents/skills/guidefold/scripts/guidefold load urn:skill:acme:payments:refunds
```

With the hosted service configured, `load` fetches the exact revision the card named and checks its checksum. Without it, `load` reads the file from the repository. Either way it records that the full text was opened, which is how the usage numbers know a card was not enough on its own.

## Uninstall

```bash
python3 .agents/skills/guidefold/scripts/guidefold uninstall --harness claude
```

It removes exactly what `install` wrote for that harness, using the manifest, and leaves everything else alone.
