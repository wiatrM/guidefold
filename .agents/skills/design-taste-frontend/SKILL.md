---
name: design-taste-frontend
description: Anti-slop frontend skill for landing pages, portfolios, and redesigns. The agent reads the brief, infers the right design direction, and ships interfaces that do not look templated. Real design systems when applicable, audit-first on redesigns, strict pre-flight check.
---

# Design Taste Frontend

Use the pinned upstream guide as the authority for design rules. Keep this file as the workflow router; load only the relevant resource sections.

## Required workflow

1. Read the brief, audience, references, brand assets, and quiet constraints before proposing an aesthetic.
2. Declare one sentence beginning `Reading this as:` and set `DESIGN_VARIANCE`, `MOTION_INTENSITY`, and `VISUAL_DENSITY` with one-line reasons.
3. For an existing site, audit it before choosing Preserve, Overhaul, or Greenfield-with-content-preserved. Do not silently change URLs, navigation, forms, anchors, legal copy, or brand identity.
4. Choose one coherent theme and one implementation foundation. Match layout families, motion, density, imagery, and copy to the brief instead of using an AI-default composition.
5. Build with stable semantic DOM order, responsive behavior, reduced-motion support, accessible interactions, and explicit asset fallbacks.
6. Run the upstream pre-flight and task-specific audits in writing. Treat any failure as release-blocking.

## Resource routing

The complete vendor text is preserved at [resources/upstream-skill.md](./resources/upstream-skill.md). Locate sections first with:

```bash
rg -n '^## ' resources/upstream-skill.md
```

Read targeted sections rather than loading the whole guide:

- **Every task:** Sections 0 (brief inference), 1 (three dials), 6 (performance/accessibility), 9 (AI tells), and 14 (pre-flight).
- **Fresh landing or portfolio:** Sections 2-5 for system choice, architecture, design engineering, and motion patterns; Section 10 for precise pattern vocabulary.
- **Existing-site redesign:** Section 11 before implementation, then the fresh-build sections needed by the declared mode.
- **Reusable pattern work:** Section 12 only when creating or consuming block-library entries.
- **Design-system installation:** Appendix A plus the relevant canonical source in Appendix B. Verify current packages before installing.
- **Liquid-glass requests:** Section 8 and Appendix C; describe web treatments as approximations, not Apple-native implementations.
- **Scope decision:** Section 13 before accepting dashboard, data-table, or multi-step product-UI work.

Use heading boundaries from the `rg` output to read the selected slice. Load the entire upstream guide only when the task genuinely spans most of its domains.

## Completion rules

- Never invent proof, customers, metrics, URLs, assets, or product capabilities.
- Keep one theme and at least four distinct layout families when the requested page scope calls for a long-form landing page.
- Preserve explicit brand and SEO constraints.
- Complete the em-dash, section-repetition, hero-discipline, preservation, and pre-flight audits that apply to the task.
