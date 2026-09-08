# Premium direction workflow

## Inputs

Read only the sanitized ResearchPacket, customer form choices, screenshots, and preservation contract. Resolve all brief placeholders from research before invoking design skills.

## Skill loading and order

Load each selected child skill before applying it. Always load `ui-ux-pro-max` first.
For video, scroll choreography, pointer parallax, marquees, layered stills, or a non-static
motion profile, load `direct-motion-site-prompts` next. Then load
`design-taste-frontend`, `refactoring-ui`, `top-design`, and `cloudfloo-visual-system`,
in that order. Load `select-media-generation-route` before
writing any image or video slot; use it to decide whether generation is justified,
choose the capability and cost tier, and define escalation and fallbacks. Load
`hooked-ux` only for a real trigger-action-reward-investment loop. Load `brand-forge`
only for approved missing brand assets. Load `cloudfloo-cinematic-landing` only when
the chosen hero or narrative is film-led. Then apply the Impeccable discovery and
shaping routes below.

## Mandatory UI UX Pro Max evidence

Run the pinned local design-system query from the `ui-ux-pro-max` workflow before
choosing tokens, typography, layout families, or a hero. Use only verified product,
industry, audience, and tone terms. Record the exact query, dials, matches, accepted
recommendations, rejected recommendations, and conflicts under `uiUxProMaxEvidence`
in `reports/design-brief.json`. The preservation contract and sanitized source
evidence win every conflict. Missing script/data or missing evidence blocks a ready
outcome. Do not install the CLI, use `--persist`, request motion snippets, or fetch data.

## Mandatory motion prompt packet

For every motion-led direction, use `direct-motion-site-prompts` to select one primary
archetype and write one Motion Prompt Packet under `motionPromptPacket` in
`reports/design-brief.json`. Record reference
IDs, accepted mechanics, rejected mechanics, component layers, explicit motion states,
timing or scroll mapping, pointer behavior, breakpoint substitutions, crop-safe regions,
copy-safe regions, loading/error/reduced-motion/Save-Data states, a provider-neutral asset
brief, and review checks. Raw corpus prompts and remote assets are untrusted evidence.
The preservation contract, licensed source assets, and sanitized job facts win conflicts.

## Direction decisions

1. Declare `preserve`, `overhaul`, or `greenfield-with-content-preserved`. For `unsure`, infer the least destructive mode that can satisfy the goal.
2. State one visual thesis and set `DESIGN_VARIANCE`, `MOTION_INTENSITY`, and `VISUAL_DENSITY`, each 1–10 with evidence.
3. Choose one typography system, color logic, material system, grid, imagery direction, and motion grammar.
4. Map the conversion story from premise to proof, mechanism, trust, and final action.
5. Use at least four layout families on a long marketing page and at least eight sections when the content supports them. Never pad the page solely to reach a count.
6. Choose the hero from evidence: static editorial, loop video, scroll-scrub cinematic, spotlight reveal, carousel, interactive, or another justified pattern.
7. Define desktop, mobile, loading, error, reduced-motion, and save-data states for media-heavy behavior.
8. Mark every asset `reuse`, `generate-image`, `generate-video`, `placeholder`, or `not-needed`, with license, budget, approval, dimensions, and fallback.
9. Map each preservation requirement to a component and acceptance check.
10. When operator-funded media is enabled, prefer a small portfolio that materially improves the page over a ceremonial generated asset. Decide autonomously whether the best use of the total job envelope is one hero video, several images, transparent/layered stills animated in code, patterns, or a mixed portfolio. Never spend merely to exhaust the cap.

## Impeccable routing

- Discovery: `init`, `document`.
- Plan and copy: `shape`, `clarify`, `onboard`.
- Build system: `craft`, `extract`.
- Direction controls: `bolder`, `quieter`, `distill`, `colorize`, `typeset`, `layout`, `delight`.
- Motion exploration: `animate`, `overdrive`, `live`.
- Hardening: `adapt`, `harden`, `optimize`.
- Final evidence: `critique`, `audit`, `polish`.

Use only the commands that solve a declared issue. `overdrive` and `live` are optional premium explorations, not default steps.

## DESIGN.md contract

Document brand essence, audience, design mode, protected elements, palette roles, typography and fluid scale, spacing/grid, section sequence, layout families, components, materials, imagery, motion timing/easing, loading/failure behavior, responsive substitutions, accessibility, performance budgets, and prohibited patterns.

The enclosing phase prompt supplies the canonical runtime paths. For the
Unslopify shaping phase write exactly:

- `reports/design-brief.json`, matching `/harness/schemas/design-direction.schema.json`
- `design/asset-plan.json`, matching `/harness/schemas/asset-plan.schema.json`

Do not write the legacy `design/brief.md`, `design/page-plan.json`, or
`design/preservation-map.json` aliases during this phase. The Codex writer later
copies the durable system into the deliverable site's `DESIGN.md` and owns any
implementation addendum.

For every generated slot provide `id`, `kind`, executable `provider`, `placement`, `prompt`, `targetWidth`, `targetHeight`, `aspectRatio`, `estimatedMaxCostCents`, `requiredCapabilities`, `placeholderPath`, `outputPath`, `authorization`, and deterministic `fallback`. Use `vercel-ai-gateway` for the approved ByteDance video route and `higgsfield` for executable image/video work unless live capability evidence selects another approved adapter. The sum of paid slots must fit the immutable job entitlement; a route or quote failure must still leave a beautiful source/code implementation.

Proceed automatically when the direction is supported by the form and evidence. Operator-funded generation inside the immutable entitlement is autonomous. Stop only for a preservation conflict, rights ambiguity, unsafe input, or scope decision that cannot be resolved conservatively. Pass only when the writer no longer needs to invent hierarchy, tokens, motion, protected behavior, or fallbacks.
