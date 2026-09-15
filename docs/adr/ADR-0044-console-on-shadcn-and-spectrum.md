# ADR-0044: The hosted console is built on shadcn/ui primitives, Spectrum UI items and Spectrum Charts

**Status:** Accepted · 2026-09-12 · records three owner instructions already binding in
`CLAUDE.md`: "Spectrum UI components are mandatory for new, redesigned or migrated Guidefold UI"
(2026-09-09), "migrate ALL existing telemetry visualizations and charting to actual Spectrum UI
Charts" (2026-09-09), "the management UI (every route after sign-in) is built on shadcn/ui
primitives" (2026-09-12). Written down as an ADR on the owner's 2026-09-12 audit instruction so
the rule has one file, one status and an index row. Merged to `main` on 2026-09-15 from the audit
branch; the counts below are dated 2026-09-12 and were not re-measured.
**Amends:** [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md) §3 (React/Vite stays; the
component layer is no longer hand-built), [ADR-0032](ADR-0032-engineering-principles-and-hexagonal-architecture.md)
(the "no component library" reading of KISS for `ui/` is lifted; the token, accessibility and
data-boundary rules stand).
**Extended by:** [ADR-0049](ADR-0049-premium-visual-effects-layer.md) (Accepted 2026-09-13: a
premium visual effects layer in `ui/src/components/effects/`; the token and accessibility rules
below are unchanged by it).
**Governs:** `ui/src/components/ui/*`, `ui/src/components/spectrumui/*`,
`ui/src/components/ui/shadcn-space/*`, `ui/src/components/*`, `docs/ui/UI.md` §4 and §7,
`.agents/skills/{react-component-rules,spectrum-ui-workflow,spectrum-charts-migration}`.

## Context

Until 2026-09-08 the hosted UI forbade component libraries and kept a hand-written library over
CSS Modules and `tokens.css`. On 2026-09-09 the owner made Spectrum UI items and Spectrum Charts
mandatory; on 2026-09-12 the owner ordered the post-login console rebuilt on shadcn/ui primitives
(base-nova style on Base UI) with a large `IconTile` per view, in the quickstart register of a
documentation site. [`docs/reports/ui/console-shadcn-20260912.md`](../reports/ui/console-shadcn-20260912.md)
records the refactor. The audit of 2026-09-12 found the rule enforced in code but stated in four
documents with three different component counts (14/15/16), and found four Overview visualisations
built on `shadcn-space` blocks over Recharts while the same documents label them "Spectrum".

## Decision

1. Every route after sign-in composes the public components in `ui/src/components/*` from the
   shadcn/ui primitives in `ui/src/components/ui/*`, installed with the pinned `pnpm exec shadcn`
   from the base-nova registry. Handmade lookalikes of an available primitive are a review defect.
2. Spectrum UI items are the first choice for anything the primitives do not cover; the item is
   installed from the Spectrum registry, its source and dependencies inspected, and its behaviour
   verified. A missing or framework-incompatible item gets a written exception in
   `docs/ui/UI.md` §7 (SC-07) naming the item searched for.
3. Every telemetry visualisation, metric card, sparkline, trend and distribution renders through a
   Spectrum Charts component adapted to `tokens.css`, with a text alternative and empty, partial,
   error and `Unknown` states. A chart that renders through any other library is either migrated
   or listed as an SC-07 exception with a reason; it is never labelled "Spectrum" in a document.
   On the date of this ADR the four Overview visualisations in `ui/src/routes/HomeRoute.tsx`
   (KPI cards, delivery funnel, feedback donut, proposals-by-state) are in violation and are a
   PRIO-1 item in the audit report. Re-checked on 2026-09-15: `HomeRoute.tsx` still imports its
   KPI, funnel, donut and table blocks from `ui/src/components/ui/shadcn-space/blocks`, so the
   violation stands on `main` @ `2a302f5`; the migration is in the open PR #164, not in `main`.
4. `tokens.css` stays the only source of values. shadcn semantic tokens are references into the
   Industrial Surveyor palette mapped through `ui/src/registry.css`. Registry code that ships hex
   literals in class strings is listed in `docs/ui/UI.md` §7 as a waiver with the file and line,
   or fixed.
5. The number of public components is stated in exactly one place,
   [`docs/ui/pipeline/08-components.md`](../ui/pipeline/08-components.md), and enforced by
   `ui/qa/check-contracts.mjs`; every other document links there instead of repeating a number.
6. Security, accessibility (`accessibility-contract`), the honesty of states (`Unknown` is not
   zero) and the data boundary (`ui/src/api`, `ui/src/data`) are unchanged by this ADR.

## Consequences

- The earlier "no component library" prohibition is closed for `ui/`. The landing page is not
  governed by this ADR beyond rule 4.
- A migration is complete when the chart renders through the Spectrum adapter in code, not when a
  requirement or an installed package exists.
- Bundle cost of Recharts and Base UI is accepted; `performance-budgets` still applies to each
  route and any regression is measured before and after.

## References

`CLAUDE.md` §§ "Mandatory Spectrum UI components", "Mandatory Spectrum Charts migration",
"Mandatory shadcn console"; [`docs/reports/ui/console-shadcn-20260912.md`](../reports/ui/console-shadcn-20260912.md);
[`docs/ui/UI.md`](../ui/UI.md) §7; `ui/qa/check-contracts.mjs`; audit
[`docs/reports/product/2026-09-12-assumptions-vs-implementation-audit.md`](../reports/product/2026-09-12-assumptions-vs-implementation-audit.md).
