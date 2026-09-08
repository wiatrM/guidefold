---
title: Quickstart
description: Install in one command, then write your first rule.
---

You need Python 3 and PyYAML on the machine that runs the agent, and a monorepo in git. The whole adapter is one Python file plus three small hook templates.

## 1. Describe the tree

At the root of your monorepo, create `guidefold.yaml`. Start small; you can add scopes later.

```yaml
publisher: acme
nodes:
  _root:
    paths: ["**"]
    owner: platform-engineering
  payments:
    paths: ["services/payments/**"]
    owner: payments-team
```

If you would rather have it generated, run `guidefold init` from the root. It reads `CODEOWNERS` when there is one.

## 2. Install the adapter for your harness

Copy the `skills/guidefold/` folder from the Guidefold repository into your monorepo as `.agents/skills/guidefold/`, then run one command:

```bash
python3 .agents/skills/guidefold/scripts/guidefold install --harness claude
```

Use `copilot` or `gemini` instead of `claude` for those harnesses. Run it once per harness you use. The command is safe to run again; it changes only what it wrote before.

What it does:

- copies the adapter package into `.agents/skills/guidefold/`;
- adds the session hook to your harness settings (Claude Code: `.claude/settings.json`, Copilot: `.github/hooks/guidefold.json`, Codex: `.codex/hooks.json`) and merges with what is already there;
- for Copilot, adds a short section to `.github/copilot-instructions.md` that tells the agent how to find and load a rule;
- builds the ranked index for the current commit;
- writes the scope cards every harness can read from disk: `AGENTS.md`, `CLAUDE.md` and `GEMINI.md` in each scope folder, and `.github/instructions/<scope>.instructions.md` for Copilot;
- writes a manifest so `uninstall` can remove exactly these files later.

Add `--dry-run` to see the plan without writing anything.

## 3. Write your first rule

Make a folder inside the scope, and one file in it:

```
services/payments/.agents/skills/refunds/SKILL.md
```

```markdown
---
name: refunds
description: "[payments] How refunds are issued and reversed, and which ledger entries they must produce."
metadata:
  scope: payments
  owner: payments-team
  status: active
  triggers: "refund, chargeback, reverse a payment, ledger entry"
  digest: >-
    A refund is a new ledger entry that references the original charge. It is never
    an edit of the charge. Partial refunds are allowed up to the captured amount.
---

## Steps
1. ...
```

Rules that apply: the folder name equals `name`; `description` starts with the scope in square brackets; `scope` and `owner` match `guidefold.yaml`; `digest` is a short summary, because that is what an agent sees first.

## 4. Check it

```bash
python3 .agents/skills/guidefold/scripts/guidefold validate
python3 .agents/skills/guidefold/scripts/guidefold find "how do I reverse a payment" --scope payments
```

`validate` reports every rule that breaks a convention. `find` shows what an agent would be handed for that question.

## 5. Try it in the agent

Open a terminal in `services/payments/` and start your harness. The first prompt triggers the hook. You should see a line like:

```
[guidefold] Relevant organizational guidance for scope payments:
- urn:skill:acme:payments:refunds — [payments] How refunds are issued and reversed ...
Load with: .agents/skills/guidefold/scripts/guidefold load <urn>
```

If you see nothing, run `guidefold doctor`. It checks the hook, the index and the settings file and tells you what is missing.

## 6. Turn on the pull request report

Copy `templates/ci.yml` from the Guidefold repository into `.github/workflows/`. It adds a comment to every pull request that touches a rule, and blocks the merge on structure errors only. The `ascend` job in the same file is off until you add a model key; see [Knowledge ascent](/knowledge-ascent).
