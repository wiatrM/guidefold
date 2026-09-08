---
name: refactoring-ui
description: Audit and fix visual hierarchy, spacing, color, depth, component styling, design tokens, dark mode, data-visualization clarity, and launch polish in web interfaces. Use when a UI looks amateur, inconsistent, visually flat, or poorly structured and needs systematic professional refinement.
---

# Refactoring UI

Refactor the visual system before polishing isolated details. Use this file as the router; consult only the detailed resources required by the interface under review.

## Workflow

1. Capture the current UI at representative desktop and mobile widths before judging it.
2. Audit the eight upstream Quick Diagnostic rows and record the baseline score.
3. Establish hierarchy and spacing in grayscale before using color to carry meaning.
4. Define constrained scales for spacing, type, color, radii, borders, and elevation; remove arbitrary one-off values.
5. Repair composition and component states from largest structural issue to smallest detail.
6. Recheck contrast, keyboard focus, responsive behavior, overflow, reduced motion, and dark mode where applicable.
7. Report the final score and every remaining gap to 10/10.

## Resource routing

- **Core seven-principle system, scoring, common mistakes, and Quick Diagnostic:** read the relevant headings in [resources/upstream-skill.md](./resources/upstream-skill.md). Locate them with `rg -n '^## |^### ' resources/upstream-skill.md`.
- **Interactive components, forms, empty states, truncation, radii, and breakpoints:** read [resources/references/advanced-patterns.md](./resources/references/advanced-patterns.md).
- **Dark themes, shade scales, surfaces, and elevation:** read [resources/references/theming-dark-mode.md](./resources/references/theming-dark-mode.md).
- **Contrast, keyboard, focus, screen readers, and depth accessibility:** read [resources/references/accessibility-depth.md](./resources/references/accessibility-depth.md).
- **Motion, feedback, loading, and reduced-motion behavior:** read [resources/references/animation-microinteractions.md](./resources/references/animation-microinteractions.md).
- **Charts, tables, dashboard density, and categorical color:** read [resources/references/data-visualization.md](./resources/references/data-visualization.md).

Load the core headings plus only the references that match the visible problems. Preserve an established brand system unless the brief explicitly authorizes an overhaul.

## Output contract

Provide the baseline and final diagnostic, token decisions, prioritized fixes, changed states and breakpoints, accessibility findings, and unresolved risks. Do not hide important pricing, terms, destructive consequences, or cancellation paths through visual de-emphasis.
