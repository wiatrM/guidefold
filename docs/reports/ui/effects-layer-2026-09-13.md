# Premium visual effects layer — 2026-09-13

Owner instruction 2026-09-13, recorded in [ADR-0049](../../adr/ADR-0049-premium-visual-effects-layer.md).
Fourteen effect components in `ui/src/components/effects/*`, a shared gate hook, a WebGL
capability helper, one export barrel, a gallery section for each, Vitest coverage (render +
reduced-motion path) for each, and this report. No route was changed — wiring these into the
seven product views is the owner's declared "following pass."

## Sources chosen, and why

The task named several candidate registries. What was actually usable, checked live against the
installed [`ui/components.json`](../../../ui/components.json) registries (`@shadcn`, `@spectrumui`,
`@shadcn-space`) via the shadcn MCP tools:

- **Magic UI / Aceternity**: no registry for either is configured in `components.json`, and
  `search_items_in_registries` for "border beam", "shader", "marquee", "orbiting" against the
  configured registries returned hundreds of unrelated dashboard blocks (fuzzy match against the
  whole shadcn-space catalogue), not the named components. Adding a third registry for a handful
  of small, well-understood CSS/motion patterns was not worth the dependency surface; every effect
  below is hand-built instead, using the animation library already in `ui/package.json`
  (`motion`/`framer-motion` 13.2.0 — both installed; new code imports from `motion/react` only,
  matching `app.tsx` and the existing `number-ticker.tsx`).
- **`border-beam` (npm, already a direct dependency)** and **Spectrum's vendored
  `beam-card.tsx`/`border-beam.tsx`/`number-ticker.tsx`/`spotlight.tsx`** in
  `ui/src/components/spectrumui/` were the actual starting point for the animation *techniques*
  (conic-gradient mask border, digit-roll ticker, pointer spotlight) — but not the code itself.
  Those vendored files use Tailwind utility classes with raw values (`bg-white`,
  `text-neutral-500`, `rounded-2xl`) and literal `rgba()` colours, which violate this task's
  "tokens only, no raw hex" requirement and the codebase's own CSS-Modules-plus-tokens convention
  for public components (`IconTile`, `ActionButton`, `Panel`). Fixing those vendored files was out
  of scope (they are pinned by SHA-256 in `qa/spectrum-registry.json` as explicit Spectrum-source
  adaptations); every effect below is freshly written against `ui/src/tokens/tokens.css` instead,
  reusing the technique, not the file.
- **`@paper-design/shaders-react`** (installed, `pnpm add`, +2 packages, ~8 KB on disk before
  gzip) is the one real WebGL dependency, used for exactly one effect (`ShaderField`). It ships
  its own tiny GLSL runtime — no `three`, no external asset — and exposes `MeshGradient` with
  built-in `minPixelRatio`/`maxPixelCount` (DPR/pixel-count capping) and a `speed` prop, which is
  what makes the pause-without-unmount design possible. `@types/three` was already a
  devDependency with no `three` runtime package present; nothing in this change uses it.
- **Spectrum decorative items** (`holographic`, `ink`, `text-states`, `loading-state`,
  `skeleton-reveal`) were inspected via `mcp__spectrum-ui__search_components` and are genuinely
  named, single-purpose components — but each ships as Tailwind-with-raw-values source too, and
  installing them via the CLI would add the same tokens-only violation as the vendored files
  above. Their *ideas* (a swapping label, a skeleton that un-blurs into content) informed
  `AnimatedText` and `ShimmerSkeleton`'s design instead of their code.

## The fourteen effects

| Component | Owner category | Console placement (next pass) | Notes |
|---|---|---|---|
| `HeaderGlow` | view header treatment | Wraps the `IconTile` in every route header | Radial halo (reuses `--effect-header-glow`) plus a one-shot sweep on mount, built on the existing `--shine-gradient`/`--duration-shine` tokens already used by the route-header shine in `App.module.css` |
| `BorderBeam` | animated card/panel border | Panel headers or the one "hero" card on a view (Overview KPI, Live Agent run) | Conic-gradient mask-border ring, continuous rotation, frozen (not removed) under reduced motion/off-screen/hidden tab |
| `ShineBorder` | animated card/panel border | Replays on a state change — an import finishing, a run completing | One light pass along the top edge, replayed via a `trigger` prop or looped via `repeat` |
| `GlowSurface` | glow | Panel/card hover on desktop (Library, Map) | Pointer-tracked spotlight; position written with `element.style.setProperty` on pointermove (no React re-render per move); desktop pointers only |
| `GlowAction` | glow (primary action + focus) | Wraps the one primary `ActionButton` per view (Import, Connect GitHub) | Halo at rest, amplified via `:focus-within`; additive to the existing focus outline, never a replacement |
| `ShaderField` | shader/animated background | Import/Live Agent empty states, page chrome behind a hero panel | See §4 below |
| `GridField` | animated background (lighter alternative) | Cheaper empty-state background where a shader is more than the moment needs | Reuses `IconTile`'s own `--tile-pattern`, drifting; distinct from the nav rail's removed `survey-grid-pattern` (UI.md §1) |
| `NumberTicker` | number tickers | Overview KPI row, Usage & quality metrics | Digit-roll on first view, screen reader gets the plain formatted number (`sr-only`), rolling glyphs are `aria-hidden` |
| `AnimatedList` | animated lists | Live Agent event log, Organization repository list | `AnimatePresence`-driven enter/exit; plain unanimated `<ul>` under reduced motion |
| `Marquee` | marquee | A connected-repositories or integrations strip | Duplicated track for a seamless loop, the copy `aria-hidden`; paused on hover/focus; single copy under reduced motion |
| `OrbitingCircles` | orbiting circles | A repository's connected sources around its own icon | Six fixed satellite angles; the whole ring plus each satellite's counter-rotation keeps icons upright while orbiting |
| `AnimatedText` | animated text | A section subhead that should draw the eye once, not repeatedly | Word-by-word rise/fade, `sr-only` plain text underneath |
| `SuccessBurst` | (owner: a success moment) | After an import or a Live Agent run finishes | Check mark + brief teal glow, `role="status"`; deliberately not confetti/particles — see ADR-0049 Consequences |
| `ShimmerSkeleton` | loading shimmer | Any list/panel loading state before `RouteState`'s own text lands | Pure CSS; its animation duration is a token that collapses to 0ms under reduced motion, so no JS gating is needed |

**Not built: dock-style effects.** Named in the owner's allowed list, not in the required
eight-category coverage. Nothing in the console has a taskbar-shaped surface a dock effect would
attach to, and building one to justify the effect would be the "pile, not a kit" the task warned
against. Recorded as a deliberate cut (ADR-0049 Consequences), not an oversight — allowed if a
concrete use appears.

## Tokens-only discipline

`ui/qa/check-contracts.mjs` is a strict source-contract checker: every CSS declaration and every
JSX inline `style=` attribute in `ui/src` is parsed and any literal dimension, colour, or
undeclared custom property fails the check (`node qa/check-contracts.mjs`, part of
`pnpm run test:contracts`). All new values live in `ui/src/tokens/tokens.css` under a new
"Effects layer (ADR-0049)" block (`--effect-beam-conic`, `--effect-header-glow`,
`--effect-glow-surface`, `--effect-shimmer-gradient`, `--effect-grid-cell`,
`--effect-orbit-angle-1..6`, `--effect-success-glow`, `--effect-focus-glow-route/system`,
`--effect-shader-fallback`, `--effect-ticker-digit-height/width`, and the shared
`--zero-deg`/`--full-turn`/`--effect-mask-solid` mechanics tokens the border/orbit math needs);
every component CSS module consumes them by `var()` only. Where a value must be written at
runtime (the pointer position in `GlowSurface`), the property still gets a static default in
`tokens.css` first — the same pattern the codebase already uses for Base UI's
`--collapsible-panel-height` — and the write happens imperatively
(`element.style.setProperty(...)`), never through a dynamic JSX `style=` attribute.

`qa/check-contracts.mjs` itself needed one addition: `effects` was added to the `registryDirs`
exemption set (alongside the existing `spectrumui` and shadcn `ui` exemptions) so a components kit
of fourteen small effects is not required to carry a full CSF `.stories.tsx` per component the way
the 17 named "stable product API" components are. Every token/CSS/import check still runs over
every file in it; only that one structural requirement is exempt.

## Performance and robustness (task §4)

- **Lazy-loaded.** `ShaderField` dynamically imports `MeshGradientCanvas` (which imports
  `@paper-design/shaders-react`) only after `IntersectionObserver` reports the field has actually
  entered the viewport — a route's first paint never waits on the shader chunk. Confirmed in the
  build output: `MeshGradientCanvas-*.js` (25.28 kB, gzip 8.23 kB) is its own chunk, not part of
  `app-*.js` or any route entry.
- **Capped device pixel ratio.** `MeshGradient` is mounted with `maxPixelCount={2073600}`
  (1920×1080) and `minPixelRatio={1}`.
- **Paused, not unmounted, off-screen and while the tab is hidden.** The shared `useMotionGate`
  hook (`ui/src/components/effects/useMotionGate.ts`) tracks `IntersectionObserver` visibility and
  `document.visibilitychange`; `ShaderField` passes the resulting `active` flag through as
  `speed={active ? 0.25 : 0}` — the canvas keeps its current frame instead of remounting.
- **One static frame under reduced motion.** The same `speed={0}` path fires when
  `prefers-reduced-motion: reduce` is set (`useMotionGate`'s `reduced` folds into `active`), so the
  shader renders its composition once and holds it rather than showing a different treatment.
- **CSS fallback where WebGL is unavailable.** `ui/src/components/effects/webgl.ts`'s
  `supportsWebGL()` probes a detached canvas for a `webgl2`/`webgl` context before the lazy import
  is even requested; failing that (confirmed in every Vitest run — jsdom has no WebGL context),
  `ShaderField` renders `--effect-shader-fallback`, a flat token-based radial gradient, and never
  imports the shader chunk at all.
- **No layout shift, no blocked input.** Every effect is either `aria-hidden` decoration
  positioned absolutely inside a sized parent, or a wrapper around content the caller already
  renders (`BorderBeam`, `ShineBorder`, `GlowSurface`, `GlowAction` all render their `children`
  unchanged, with the effect as a sibling layer); none intercepts pointer or keyboard events
  (`pointer-events: none` on every purely decorative layer except `GlowSurface`'s own
  `onPointerMove`, which never calls `preventDefault`).

## Dependency audit (added after coordinator review of PR #168)

`@paper-design/shaders-react` is the only new dependency. It was installed with `pnpm add`
before checking this repo's exact-pin convention; the resulting `^0.0.80` range in
`package.json` was corrected to the exact installed version `0.0.80` (matching
`"border-beam": "1.3.0"`'s style) and `pnpm install` re-run to reconcile the lockfile.

```
$ pnpm why @paper-design/shaders-react
@paper-design/shaders-react@0.0.80
└── guidefold-ui@0.0.0 (dependencies)
Found 1 version of @paper-design/shaders-react

$ pnpm why @paper-design/shaders
@paper-design/shaders@0.0.80
└─┬ @paper-design/shaders-react@0.0.80
  └── guidefold-ui@0.0.0 (dependencies)
Found 1 version of @paper-design/shaders

$ pnpm why @radix-ui/react-slot
(no output — not in the lockfile)

$ pnpm why @radix-ui/react-dialog
(no output — not in the lockfile)
```

No `@radix-ui/*` package exists in the lockfile at all (the console is Base UI, not Radix, per
`CLAUDE.md`), and the two `@paper-design/*` packages are the only additions — no transitive
surprise the way `cmdk` pulled a dozen Radix packages in the failed parallel branch. Every other
effect reuses `motion`/`framer-motion` 13.2.0 (both already installed; new code imports from
`motion/react` only, matching `app.tsx` and the pre-existing `number-ticker.tsx`) and
`@phosphor-icons/react` 2.1.10 (already installed; `CheckCircleIcon`, `GitBranchIcon`,
`GithubLogoIcon`, `CircleIcon` newly used in the gallery demo, each verified present in
`node_modules/@phosphor-icons/react/dist/index.d.ts` before use).

## Bundle cost (task §4 and §8)

`cd ui && node_modules/.bin/vite build`, before adding the effects kit and after wiring it into
the gallery (the only current consumer — no route imports `ui/src/components/effects` yet), both
measured against the same base commit (3f9f80f, this branch's origin/main starting point, before
`origin/main` moved further with the organisation switcher and GitHub import fix):

| | Before | After | Δ |
|---|---|---|---|
| JS (raw) | 2003.25 kB | 2048.00 kB | +44.75 kB |
| JS (gzip) | 620.56 kB | 635.76 kB | +15.20 kB |
| CSS (raw) | 305.88 kB | 316.89 kB | +11.01 kB |
| CSS (gzip) | 54.71 kB | 57.01 kB | +2.30 kB |
| **Total (gzip)** | **675.27 kB** | **692.77 kB** | **+17.50 kB** |

Almost all of that delta is the dev-only gallery route (`Gallery-*.js` 8.19 kB → 26.91 kB raw, its
own lazy chunk, never loaded by a signed-in console route) and the new icon chunks
(`CheckCircle.es`, `GitBranch.es`, `GithubLogo.es` — 2.11 + 2.62 + 5.37 kB raw) plus the shader
chunk described above. The shell entry that every route actually loads, `app-*.js`, grew by
**0.16 kB gzip** (49.68 kB → 49.75 kB) — negligible, because no route imports any effect yet.

After merging `origin/main` (organisation switcher #166, GitHub import fix #167 — unrelated to
this task, not attributable to the effects layer) the build still succeeds:
`js=2056.31 kB (gzip 637.70 kB) css=316.94 kB (gzip 57.01 kB) total=2373.25 kB (gzip 694.71 kB)`.
The ~2 kB gzip difference from the effects-only "after" row above is `app-*.js` picking up
`OrgSwitcher` and its own domain module, not this change.

## Visual baseline check after the merge (coordinator review of PR #168)

PR #168 shifted an untouched `PyramidChart` baseline by 1 px through generated Tailwind CSS,
discovered only because a reviewer diffed the manifest. The same check here: `pnpm test:visual`
run against the pre-merge baseline first (fails closed on any drift), then compared record by
record.

Before regenerating anything, `node qa/compare-gallery.mjs` (no `--update`) against the baseline
already committed pre-merge reported exactly **3 of 87** cases changed, all three
`NumberTicker` (1280/820/390) — expected, because the gallery's own `NumberTicker` sample was
edited in this same change (`suffix=" skills"` → `suffix={' skills'}`, a rendering fix: a
plain leading space collapses in an inline `<span>`, a non-breaking space does not). Of the
remaining 84 (29 components × 3 widths, minus the 3 `NumberTicker` records): the **45 records
for the 15 pre-existing components were unchanged by the merge** — the actual drift check the
coordinator asked for, and the one PR #168 failed (an untouched `PyramidChart` shifted 1px through
generated Tailwind CSS). The other **39 records, for the thirteen other effects, reproduced
byte-identically on a second, independent run** — a determinism check, not a drift check: they
were captured minutes earlier in this same session and did not exist before this change, so this
proves they render the same twice, not that they survived the merge unchanged.
`git diff -- ui/qa/baseline/manifest.json` confirms the same: only the 3 `NumberTicker` sha256
entries and the top-level `capturedAt` timestamp changed. The baseline was then regenerated
(`--update`) and re-verified clean: `{"cases":87,"passed":true,"differences":[]}`.

**`OrgSwitcher` is not in this visual run.** `qa/check-contracts.mjs`'s `expected` list is now 18
(main's `OrgSwitcher` plus the 17 already there); `qa/compare-gallery.mjs`'s `components` list is
separate and only ever covered 15 (now 15 + these 14 effects) — `OrgSwitcher` has no gallery
entry and this change does not add one. The 87-case pass above proves the 29 named components
still render correctly; it says nothing about `OrgSwitcher`.

**`ShaderField`'s WebGL path was verified, not assumed.** Whether the captured baseline is the
live `MeshGradient` frame or the `--effect-shader-fallback` CSS gradient depends on whether the
capture browser has WebGL — a real risk if CI's headless Chromium differs from this sandbox's.
Checked directly against the same dev server `compare-gallery.mjs` used:
`document.createElement('canvas').getContext('webgl2')` succeeds, and
`document.querySelector('[data-slot=shader-field] canvas')` finds a mounted canvas — so
`ShaderField-*.png` in the committed baseline is a real shader frame, not the fallback.
`reducedMotion:'reduce'` drives `speed={0}` (§4 above), and the second, independent
`compare-gallery.mjs` run reproduced that frame byte-identically, so the capture is
frame-deterministic in this environment. The residual risk is a CI runner whose headless
Chromium has no software WebGL (SwiftShader) at all, which would make `ShaderField` fall back to
the CSS gradient and diff against this baseline on the very first CI run; if that happens, the
fix is either accepting a new CI-side baseline for that one record or removing `ShaderField`
alone from `compare-gallery.mjs`'s `components` list (the other thirteen effects do not depend on
WebGL and already carry the visual proof).

## Proof

Final run, after merging `origin/main` (9da8c55, organisation switcher + GitHub import fix) into
this branch:

- Gallery: `ui/src/Gallery.tsx` renders all fourteen effects at `/__components` (dev-only route),
  each in its own `[data-component=Name]` section, alongside the existing 15.
- Vitest: one `.test.tsx` per effect plus `webgl.test.ts`, each exercising a default render and,
  where the effect has motion, the reduced-motion path via `vi.spyOn(window,'matchMedia')` (not
  `motion/react`'s own `useReducedMotion`, which caches its query result once per module load and
  is therefore untestable across cases in one file — `useMotionGate` re-reads `matchMedia` live,
  the same guard pattern `components/spectrumui/use-beam-motion.ts` already used).
  `pnpm test`: **65 test files, 664 tests, all passing** (63/631 before the merge; the two extra
  files/33 extra tests are `origin/main`'s own `OrgSwitcher` work, not this change).
- `pnpm run test:contracts`: passed, 0 diagnostics, 18 components (the merged union — main's new
  `OrgSwitcher` plus this branch's `effects` registry-dir exemption), 57 CSS files, 476 declared
  tokens, 64 production files traversed.
- `pnpm run typecheck` (`tsc --noEmit`): clean.
- `pnpm run build`: succeeds; numbers in §"Bundle cost" above.
- `pnpm test:visual` (`qa/compare-gallery.mjs`, dev server via `GUIDEFOLD_DEV_UI_PORT`): 87/87
  cases pass against the regenerated baseline; see §"Visual baseline check" for the 3-record diff
  this change caused, the 45-record confirmation that the merge caused none in the pre-existing
  components, and the WebGL/shader-determinism verification for `ShaderField`.
- Screenshots: `ui/qa/baseline/<Effect>-{1280,820,390}.png` for all fourteen effects (42 files)
  plus the matching `ui/qa/gallery/<Effect>-*.png` actual captures; `ui/qa/pixel-diff.json` and
  `ui/qa/contracts.json` are the machine-readable reports from the same two runs.

Files changed: `ui/src/tokens/tokens.css`, `ui/src/components/effects/**` (new: 14 components ×
`index.tsx`/`*.module.css`/`*.test.tsx`, plus `useMotionGate.ts`, `webgl.ts`, `webgl.test.ts`,
`ShaderField/MeshGradientCanvas.tsx`, `index.ts` barrel), `ui/src/Gallery.tsx`,
`ui/src/Gallery.module.css`, `ui/qa/check-contracts.mjs` (the `registryDirs` exemption, merged
with main's `OrgSwitcher` addition to `expected`), `ui/qa/compare-gallery.mjs` (added the 14
effect names to the captured `components` list; added a `GUIDEFOLD_DEV_UI_PORT` override so this
script can target a dev server on a port other worktrees are not already holding),
`ui/qa/baseline/**` (42 new effect screenshots, 3 `NumberTicker` screenshots updated, manifest
regenerated), `ui/qa/gallery/**`, `ui/qa/contracts.json`, `ui/qa/pixel-diff.json`,
`ui/package.json`/`ui/pnpm-lock.yaml` (`@paper-design/shaders-react`, pinned exact),
`docs/adr/ADR-0049-premium-visual-effects-layer.md`, `docs/adr/README.md`, `docs/ui/UX.md`,
`docs/ui/UI.md`, `.agents/skills/ui-anti-slop-gate/SKILL.md`,
`docs/reports/ui/effects-layer-2026-09-13.md` (this file). `ui/src/registry.css` was left
unchanged — no new Tailwind theme entries were needed.
