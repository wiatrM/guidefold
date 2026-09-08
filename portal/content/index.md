---
title: What Guidefold is
description: The short version, for someone who has five minutes.
---

Guidefold gives coding agents the rules of your organisation, in the place where those rules apply.

[Watch the Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c). Which step would you need to check in your own repository? Share a timestamp or question in the [Guidefold discussion](https://www.producthunt.com/p/guidefold).

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

## Planned hosted pricing

You can use the open-source version today. The paid hosted service is planned and is not yet available to purchase.

The hosted plan will cost **$99 per organisation per month**, excluding taxes, for a shared skill library, review and revision controls.

Bring your own model API key (BYOK) and run the agent in your CI. You pay your model provider and CI provider directly; Guidefold adds no AI usage charge for this route.

Prefer to use it without a key? The planned option adds a separate prepaid AI budget to the same $99 subscription. AI usage is charged at provider cost divided by 0.90: $9 of provider usage costs you $10. That gives Guidefold a 10% gross margin on AI usage. A hard spending limit stops new work before it exceeds your budget. There is no unlimited AI allowance.

Enterprise SSO is not included. Hosted runner pricing and plan quotas will be specified before purchase. A one-time setup or self-hosted add-on may be offered separately, with a defined scope and support period; it will not include lifetime hosting or AI.

Start with the [open-source quickstart](/quickstart). Which would your team use: its own API key and CI, or a prepaid AI budget? Tell us in the [Guidefold discussion](https://www.producthunt.com/p/guidefold).

## What it is not

It is not a wiki, not a marketplace, and not a chatbot. It does not run code from your repository. It does not promote anything on its own; a person always merges.

Next: [How it works](/how-it-works), then [Quickstart](/quickstart).
