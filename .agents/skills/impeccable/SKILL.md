---
name: impeccable
description: Use when the user wants to design, redesign, shape, critique, audit, polish, clarify, distill, harden, optimize, adapt, animate, colorize, extract, or otherwise improve a frontend interface. Covers websites, landing pages, dashboards, product UI, app shells, components, forms, settings, onboarding, and empty states. Handles UX review, visual hierarchy, information architecture, cognitive load, accessibility, performance, responsive behavior, theming, anti-patterns, typography, fonts, spacing, layout, alignment, color, motion, micro-interactions, UX copy, error states, edge cases, i18n, and reusable design systems or tokens. Also use for bland designs that need to become bolder or more delightful, loud designs that should become quieter, live browser iteration on UI elements, or ambitious visual effects that should feel technically extraordinary. Not for backend-only or non-UI tasks.
---

# Impeccable

Route each request to the smallest relevant upstream playbook. Do not bulk-load `resources/`.

## Start

1. Run `node .agents/skills/impeccable/scripts/context.mjs` once per session from the user's project. Add `--target <path>` for a named source file or route. Follow its directives and do not rerun it.
2. Read [core guidance](./resources/core.md) for the design contract and surface modes.
3. Select one route below, then inspect the target and one representative source of incumbent visual truth before editing.
4. Immediately before any UI edit, read [the craft floor](./resources/craft-floor.md). Skip it for planning-only work.

## Route resources

- No argument: read [context-aware routing](./resources/routing.md); recommend commands but never auto-run one.
- Explicit or implied command: use [the complete command map](./resources/commands.md), then read only that command's linked playbook. Ask once if two commands fit.
- New surface, greenfield build, or replacement visual world: read [new work](./resources/new-work.md). Missing `PRODUCT.md` routes through [init](./resources/init.md) first.
- Operate or Read surface: additionally read [operate and read guidance](./resources/operate.md).
- Native iOS or Android: load [iOS](./resources/ios.md) or [Android](./resources/android.md), plus the native `audit` or `adapt` playbook when that command applies.
- Browser iteration, hooks, or drift repair: route to [live](./resources/live.md), [hooks](./resources/hooks.md), or [doctor](./resources/doctor.md) only when invoked.
- Degraded sub-agent handoffs: load the matching file under `resources/degraded/` only when an upstream playbook directs it; [manual edit applier](./resources/degraded/manual-edit-applier.md) is reserved for that explicit fallback.
- Upstream audit or update work: read [provenance and license routing](./resources/provenance.md); do not modify the pinned source implicitly.

Preserve the brief, product truth, behavior, and scope. Use bounded verification: one batched desktop/mobile inspection, one repair batch, and at most one confirmation pass.
