---
name: hooked-ux
description: Design habit-forming product loops using the Hook Model (Trigger, Action, Variable Reward, Investment). Use when users are not returning, habit formation or engagement loops are in scope, a streak or re-engagement strategy is needed, or post-signup drop-off needs diagnosis. Include an ethics evaluation for every recommendation.
---

# Hooked UX

Apply the Hook Model only where recurring behavior serves the user. Use this file as the router and preserve the pinned upstream material as the detailed authority.

## Workflow

1. Define the recurring user problem, desired behavior, cadence, and evidence of current drop-off.
2. Map Trigger, Action, Variable Reward, and Investment as one causal loop. Distinguish external from internal triggers.
3. Run the Manipulation Matrix and the upstream `When NOT to Use` gate before optimizing engagement.
4. Score the loop with the upstream Quick Diagnostic, name every missing row, and state what would raise the score.
5. Recommend the smallest ethical experiment, its success metric, a stopping rule, and a natural stopping point for the user.
6. Separate evidence from hypothesis. Do not claim that a habit formed without cohort or frequency data.

## Resource routing

- **Core model, scoring, ethics gate, onboarding audit, and Quick Diagnostic:** read the relevant headings in [resources/upstream-skill.md](./resources/upstream-skill.md). Locate them with `rg -n '^## |^### ' resources/upstream-skill.md`.
- **Trigger and emotion mapping:** read [resources/references/triggers.md](./resources/references/triggers.md).
- **Action and investment patterns by product type:** read [resources/references/product-applications.md](./resources/references/product-applications.md).
- **Reward selection and schedules:** read [resources/references/rewards.md](./resources/references/rewards.md); add [resources/references/neuroscience-foundations.md](./resources/references/neuroscience-foundations.md) only when mechanism-level reasoning matters.
- **Measurement and cohort tests:** read [resources/references/habit-testing.md](./resources/references/habit-testing.md).
- **Worked comparisons:** read [resources/references/case-studies.md](./resources/references/case-studies.md) only when an example will materially clarify the recommendation.
- **Vulnerable users, dark patterns, or regulatory risk:** read [resources/references/ethical-boundaries.md](./resources/references/ethical-boundaries.md) before proposing mechanics.

Do not load every reference by default. Always include the ethics gate even when the request is framed only as retention optimization.

## Output contract

Return the current score, four-phase map, ethical classification, gaps to 10/10, experiment plan, metrics, and guardrails. Refuse or redesign extractive loops rather than optimizing them.
