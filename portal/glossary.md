---
title: Glossary
description: The words this documentation uses, in plain terms.
---

**Scope.** One node of the tree in `guidefold.yaml`: a folder pattern, an owner, and a dotted name like `atlas.identity`. A scope sees its own subtree and the chain above it.

**Rule, skill.** The same thing. A folder under `.agents/skills/` with a `SKILL.md` file. "Skill" is the file format's name; "rule" is what it usually contains.

**Card.** The top of a skill file: name, one-sentence description, short digest, trigger phrases, owner. What an agent sees first. Capped at 80 lines when rendered.

**Full text, body.** The rest of the skill file. What an agent loads when the card is not enough.

**URN.** The stable id of a skill: `urn:skill:<publisher>:<scope>:<name>`. Derived from the file's place in the tree, never typed by hand.

**Hook.** A small program the harness runs at the start of a session or on each prompt. Guidefold's hook prints the ranked cards for the current folder.

**Harness.** The agent tool: Claude Code, GitHub Copilot, Codex, Gemini CLI.

**Index.** The pre-built ranking data for one commit. The hook reads only this.

**Materialize.** The command that writes scope cards to disk (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot instruction files) for harnesses that read files instead of running a hook.

**Ascent.** Writing a summary of a scope one level up, from the rules below it, gated and reviewed. Produces a map and, when justified, a convention.

**Map.** A generated skill at a scope that says what lives there and who owns it.

**Convention.** A generated skill at a scope that says what every child does the same way.

**Exposure.** One card printed to an agent. Counted once per print.

**Load.** One full text fetched and checksum-verified.

**Judgement.** A person saying a skill helped, hindered, or did not apply to a task.

**Unknown.** Data that was not reported. Shown as "unknown" with the reason, never as zero.

**Owner.** The team named for a scope in `guidefold.yaml`. Owners review proposals and decide queue items. Writing into a scope needs its owner.

**Proposal.** A generated change to a skill waiting for an owner's decision in the hosted review screen.
