# Brand asset workflow

## Decide whether to generate

Read `DESIGN.md`, the source asset inventory, customer rights confirmation, and preservation contract. A weak source design is not automatic permission to rebrand. If the logo or wordmark is protected, preserve it and derive supporting tokens instead.

## Brand profile

Create job-local `brand-profile.json` containing:

- canonical brand/product names and tagline rules;
- one-sentence thesis, audience, voice, and prohibited claims;
- palette roles and contrast constraints;
- typography roles and fallbacks;
- imagery, texture, illustration, and motion direction;
- logo clear space, minimum size, monochrome behavior, and prohibited treatment;
- required output formats, dimensions, channels, and background variants;
- motifs and AI-slop patterns to avoid;
- source and generation provenance.

## Route minimally

- `generate-logo`: only for an explicitly approved new/replacement identity.
- `generate-social`: campaign or reusable social templates.
- `generate-graphic`: hero art, marketing graphics, texture, and supporting imagery.
- `generate-doc-template`: branded report or document system.

Load and run only the component skill required. Respect its upstream license and pinned source.

## Validate and deliver

Check brand consistency, legibility, contrast, small-size behavior, transparent/light/dark variants, crop safety, and vector cleanliness where applicable. Preserve source assets unchanged, store candidates separately, record chosen/rejected rationale, and return a `design-delta.json`. Only the Codex writer may merge that delta into `DESIGN.md` and `brand-profile.json`.

Logo generation and any paid image call require explicit operator approval. Job assets never become shared harness fixtures without separate redaction and rights review.
