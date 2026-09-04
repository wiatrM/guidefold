# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Selected Product Direction

- Source of truth: `design-reference/source-industrial-surveyor.png`, option 6 from the folded-map Guidefold exploration.
- Preserve the folded cartographic `G` as the core brand asset. It should read as a survey map first and a letterform second, with an orange promotion route used sparingly.
- Product tone: regulated enterprise operations, not cinematic sci-fi. Prefer graphite surfaces, square geometry, compact data density, technical teal for healthy/system states, safety orange for review/action, and red only for failures.
- Primary prototype flow: inspect a candidate skill, review CI and governance gates, then approve promotion from team to division to company.
