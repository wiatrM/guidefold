---
title: What Guidefold is
description: The short version, for someone who has five minutes.
---

Guidefold gives coding agents the rules of your organisation, in the place where those rules apply.

Big companies have many teams and many rules. Each team writes down how its part of the code works: how to deploy, what not to touch, who to ask. AI coding agents (Claude Code, GitHub Copilot, Codex, Gemini CLI) cannot read all of that at once. There is too much of it. So they guess, or they read the wrong file, or they read nothing.

Guidefold fixes this in three steps.

1. Rules live next to the code they describe. A team writes a short file called `SKILL.md` inside its own folder. Git is the only source of truth. Nothing is stored in a separate wiki that goes stale.
2. An agent working in a folder gets only the few rules that apply there. Guidefold ranks every rule in the repository and hands the agent at most four short cards. The agent asks for the full text only when it needs it.
3. Rules that are true for a whole platform climb up the tree. When one team writes something that also holds for its neighbours, Guidefold proposes a short summary one level up, and the owner of that level reviews it as a normal pull request.

## Who it is for

Platform teams in large organisations that run several agent harnesses over one monorepo. If you have one repository, one team and one agent, the vendor's own features are probably enough.

## What you get

- One command installs the adapter for your harness and wires the hook.
- Every pull request that touches a rule gets a report before merge: what changed, what collides, what an agent would now see.
- Usage numbers per rule: how often it was shown, how often the agent opened the full text, whether people said it helped.
- A review screen for rule owners.

## What it is not

It is not a wiki, not a marketplace, and not a chatbot. It does not run code from your repository. It does not promote anything on its own; a person always merges.

Next: [How it works](/how-it-works), then [Quickstart](/quickstart).
