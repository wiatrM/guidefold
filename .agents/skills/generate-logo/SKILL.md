---
name: generate-logo
description: Generate approved on-brand SVG wordmarks, monograms, and favicons from a validated active Brand Forge profile. Use when a redesign explicitly needs a missing logo asset; do not replace preserved customer identity without approval.
---

# Generate Logo

Use only after the `brand-forge` router confirms that new logo work is allowed by the preservation contract.

## Resource routing

- Always load the [pinned upstream workflow](./resources/upstream-skill.md) for prerequisites, generation, outputs, and errors.
- Load [logo construction](./resources/logo-construction.md) for geometry, clear space, color, typography, and accessibility.
- Execute through the pinned shared modules at `.agents/lib/brand.mjs`, `.agents/lib/logo.mjs`, and `.agents/lib/svg.mjs`. Upstream `../../lib/*` paths map to `.agents/lib/*` in this project.

Never overwrite a source logo. If the upstream visual-guardian agent is unavailable, perform the same palette, contrast, clear-space, and type checks locally before returning assets.
