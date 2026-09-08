# Premium visual system

Provenance: generalized from Cloudfloo visual-system source at commit `ce8517ed2e0fe375d45fe97319db859c6cebb405`. The source brand's black/cyan/purple tokens are not defaults.

## Decision order

1. Brand thesis, audience, voice, and emotional register.
2. Background, ink, muted, border, and accent roles with measured contrast.
3. Type families, variable weights, fluid scale, line length, leading, and tracking.
4. Grid, containers, spacing rhythm, section density, and optical alignment.
5. Surfaces, borders, radii, shadow, texture, and media treatments.
6. Reusable buttons, links, inputs, navigation, badges only when semantic, and interaction states.
7. Motion tokens, durations, easings, and responsive/reduced-motion substitutions.

Expose durable decisions as CSS custom properties and reusable primitives. Document justified exceptions in `DESIGN.md` instead of scattering magic values.

## Quality rules

- Typography establishes hierarchy before effects.
- Accent color signals action or meaning; it is not decoration everywhere.
- Glass belongs over imagery only when translucency has a material reason.
- Different section layouts share one grid, token system, and rhythm.
- Use art-directed media and deliberate focal crops rather than decorative icon grids.
- Apply local contrast treatments over variable media and validate real frames.
- Mobile is a deliberate recomposition with correct reading and focus order.
- Loading, error, empty, focus, hover, active, disabled, and reduced-motion states belong to the system.

## Anti-slop

Reject default purple gradients, excessive rounded cards, floating pill labels, equal-weight feature grids, vague techno claims, ornamental glows, monotonous centered sections, mixed radius systems, and uniform animation unless the brief explicitly justifies them.

Update the generated project's `DESIGN.md` so future routes reuse the same tokens, component families, imagery rules, and motion grammar.
