---
name: generate-doc-template
description: Generate approved branded SVG letterheads, slides, and one-pagers from a validated active Brand Forge profile. Use when a redesign needs a reusable document or deck template with editable title, subtitle, and body zones.
---

# Generate Document Template

Use only after the `brand-forge` router approves creation of a new branded document asset.

## Resource routing

- Always load the [pinned upstream workflow](./resources/upstream-skill.md) for prerequisites, kinds, generation, outputs, and errors.
- Load [layout grids](./resources/layout-grids.md) for dimensions, margins, editable zones, and extension rules.
- Execute through the pinned shared modules at `.agents/lib/brand.mjs`, `.agents/lib/doctpl.mjs`, and `.agents/lib/svg.mjs`. Upstream `../../lib/*` paths map to `.agents/lib/*` in this project.

Never overwrite customer templates. If the upstream visual-guardian agent is unavailable, perform the same palette, contrast, layout, and typography checks locally.
