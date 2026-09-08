---
name: generate-graphic
description: Generate an explicitly approved on-brand raster hero, advertisement, background, or texture from a validated Brand Forge profile. Use only for photographic or illustrative assets when network generation and provider credentials are authorized.
---

# Generate Graphic

Use only after the `brand-forge` router approves raster generation and the current job explicitly authorizes the provider call.

## Resource routing

- Always load the [pinned upstream workflow](./resources/upstream-skill.md) for opt-in checks, prompting, generation, compositing, outputs, and errors.
- Load [brand raster prompting](./resources/brand-raster-prompting.md) for provider behavior, text handling, and steering.
- Execute through the pinned shared modules at `.agents/lib/brand.mjs`, `.agents/lib/raster.mjs`, `.agents/lib/genimage.mjs`, `.agents/lib/composite.mjs`, and `.agents/lib/svg.mjs`. Use `.agents/lib/rasterize.mjs` only for an approved local flattening step. Upstream `../../lib/*` paths map to `.agents/lib/*` in this project.

Never call a provider without both explicit approval and the required opt-in environment. Keep literal copy out of model pixels and add it as a vector overlay.
