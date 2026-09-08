# Motion landing build workflow

## Stack and authority

Start from `templates/vite-motion`: React, strict TypeScript, Vite, Tailwind CSS 4, Motion, and Lucide. `DESIGN.md`, `page-plan.json`, and the preservation contract are binding. Codex is the sole writer unless an operator explicitly switches provider after Codex is unavailable.

## Child-skill routing

Always load `ui-ux-pro-max`. For video, scroll choreography, pointer parallax, marquees,
layered stills, or a non-static motion profile, load `direct-motion-site-prompts` and read
the brief's `Motion Prompt Packet` before layout or animation work. Then load
`cloudfloo-visual-system`. Before editing user-facing copy, always load `humanizer`; after
the copy pass, always load `avoid-ai-writing` for the second-pass audit. For
`motionProfile=scroll-scrub` or a cinematic hero, load `cloudfloo-cinematic-landing` and
`cloudfloo-premium-scroll-motion`. For `loop`, load only the relevant loop section in
this skill's motion patterns. Load `brand-forge` only for an approved brand-asset
request. Route free raster generation to the harness-provided ImageGen capability;
route Higgsfield only when an operator approval record matches the job, asset request
digest, budget, and expiry. Never load every primitive by default.

## UI UX Pro Max implementation gate

Before tokens, layout, or component styling, read the `UI UX Pro Max evidence` section
in the approved brief. Apply its accepted recommendations and keep its rejected
recommendations out. Do not rerun broad generation, use `--persist`, install the CLI,
add GSAP, or create another design system. Check the riskiest implemented interaction
against the accepted UX or React guidance and record the finding plus disposition in
`reports/build-notes.md`. The selected provider must stay inside its command allowlist;
Claude uses the recorded evidence and bundled read-only data rather than running Python.

## Motion Prompt Packet implementation gate

When a packet exists, implement its named archetype, layer order, state model, timing or
scroll mapping, crop-safe composition, breakpoint substitutions, and fallbacks. Record
the riskiest packet acceptance check and its result in `reports/build-notes.md`. Do not
copy brands, claims, URLs, dependencies, or exact creative assets from the raw corpus.
The packet doesn't authorize paid generation or a second writer.

## Build order

1. Create semantic structure, landmarks, content order, design tokens, fluid typography, and responsive grid before animation.
2. Render all essential content visible and usable in the base state.
3. Build the hero and primary conversion path, then remaining sections by their declared layout families.
4. Preserve protected routes, nav labels, fields, anchors, logo, legal copy, and SEO headings.
5. Use approved real assets. While image or video generation runs in parallel, use aspect-correct local placeholders with stable dimensions.
6. Run `humanizer` on editable user-facing copy, then run `avoid-ai-writing` as the second-pass audit. Preserve every protected span and record deliberate exceptions in `reports/build-notes.md`.
7. Add motion as progressive enhancement after layout and copy are correct.
8. Implement mobile recomposition, loading, media failure, save-data, reduced-motion, and keyboard states before polish.
9. Update the generated project `DESIGN.md` when implementation exposes a durable token or component decision.

## Motion invariants

- Stable DOM and reading order; animation state never decides whether content exists.
- Content is visible by default. Add an enhancement class only after successful initialization.
- Entry, ambient, and scroll-linked motion are separate systems.
- Entry stagger is normally 50–70 ms and capped at 300 ms. Exit is simultaneous.
- No scroll-jacking. Scroll-linked behavior must work in reverse and after refresh mid-page.
- Use transform and opacity preferentially; cap high-DPI canvases and large composited layers.
- Clean up RAF loops, listeners, observers, decoders, bitmaps, fetches, and timeouts.
- Reduced motion shows everything immediately, uses static/poster media, removes parallax/filters/clips, and restores normal scrolling.

## Cinematic media

Poster first. Check reduced motion and save-data before download. On decoder, CORS, or network failure keep the poster and content. Recompute object-cover geometry on resize. A scrubbed film is not a normal autoplay loop.

Variable footage may use a local translucent or gradient underlay. Tune it from representative frames: strong enough for contrast, light enough that film remains visible. Never cover the entire film by default. Section rows must remain readable even when observers initialize late or never run.

## Composition

Prefer one viewport and one primary job. A hero headline is normally at most eight words and three mobile lines, with no more than two CTAs and compact proof. Avoid unrelated icon-card grids, arbitrary glass, repetitive centered sections, and effects that do not carry meaning.

## Outputs and gate

Write the runnable source, project `DESIGN.md`, `reports/build-notes.md`, and `reports/preservation-implementation.json`. The build notes must include the UI UX Pro Max implementation check, copy audit, edited files, protected exceptions, and unresolved findings. Typecheck and production build must pass, and the UI/UX evidence gate plus editable-copy gates must pass, before handing off to QA.

Return a machine result matching `/harness/schemas/build-phase-result.schema.json`; it describes the build phase, never final job completion.
