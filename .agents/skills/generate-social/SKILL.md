---
name: generate-social
description: Generate approved platform-sized social SVG templates from a validated active Brand Forge profile. Use for Instagram posts or stories, Open Graph cards, YouTube thumbnails, and banners that need editable on-brand copy zones.
---

# Generate Social

Use only after the `brand-forge` router approves creation of a new social asset.

## Resource routing

- Always load the [pinned upstream workflow](./resources/upstream-skill.md) for prerequisites, presets, generation, outputs, and errors.
- Load [platform sizes](./resources/platform-sizes.md) for canvas dimensions, safe zones, layout, and extension rules.
- Execute through the pinned shared modules at `.agents/lib/brand.mjs`, `.agents/lib/social.mjs`, and `.agents/lib/svg.mjs`. Upstream `../../lib/*` paths map to `.agents/lib/*` in this project.

Keep copy in editable SVG zones. If the upstream visual-guardian agent is unavailable, perform the same palette, contrast, overflow, and typography checks locally.
