# Guidefold landing — implemented system

Status: **Implemented**. Date: 2026-09-12.
Purpose: the durable record of what `ui/src/routes/landing/` actually contains after the v2
rebuild, and of the places where implementation had to choose.
Inputs: `ui/design/landing/v2/DESIGN.md` (the direction this implements), `v2/copy.md`,
`v2/components.md`, `v2/value-brief.md`, and the preservation contract in
`ui/design/landing/design-brief.json` (`preservationMap`), summarised in
`ui/design/landing/DESIGN.md` §2.
Replacement scope: this file replaces the v1 implemented-system record for this directory,
including the rules the owner verdict of 2026-09-11 overrode. It replaces nothing outside
`ui/src/routes/landing/`.

Authority order is unchanged: preservation contract → owner verdict → `v2/DESIGN.md` →
`design-brief.json` → craft skills.

Nothing below is described as done unless a command in the task 13 QA gate checked it. The
measurements are in **Measured** at the end and in `ui/qa/landing-v2-gate.json`.

## Reading order and ids

`hero → extraction → how-it-works → proof-gate → telemetry → research-results →
availability → waitlist → questions`, then the footer.

DOM order equals visual order equals tab order at every breakpoint; no CSS `order` anywhere.
One `h1`; one `h2` per section; `h3` only inside the FAQ triggers.

| # | Section id | `h2` | What it renders |
|---|---|---|---|
| 1 | `hero` | (the `h1`) | Two-line masked headline, subline, body, the two primary actions, the evidence link, the scroll cue (dropped at ≤ 720, see **The hero at 390**), the tier glyph and the two-figure proof rail |
| 2 | `extraction` | One team's fix becomes everyone's rule. | The pinned chapter: three beats over one sticky stage, each with its own instrument (the promotion diff, the scope table with per-node rule counts, the tier bars) |
| 3 | `how-it-works` | Thirty thousand rules. Four reach the agent. | The retrieval instrument: the query, the 27-candidate funnel and the four delivered cards, general first |
| 4 | `proof-gate` | Seventy-six harmful rules. Seventy-six refusals. | The safety boundary: two figures with their qualifiers, and the ASK trace |
| 5 | `telemetry` | You see which rule failed, and why. | The telemetry panel and the promotion table, over the Meridian fixture |
| 6 | `research-results` | Plus 8.53 points of recall over flat. | The evidence bento: chart tile, ticker tile, the open-method tile and the scale tile, plus the dated table and its limitations |
| 7 | `availability` | Clone it today. It is open. | Open-source status, harness list, the hosting statement |
| 8 | `waitlist` | Be first on hosted Guidefold. | The protected `WaitlistForm` (form id `waitlist-form`), its success state and its four error strings |
| 9 | `questions` | Before you join | Four FAQ triggers, every one shipped closed; `#privacy` deep-links its panel open |

`?confirm=` / `?unsubscribe=` renders `EmailAction` instead of the nine sections, drops the
token from the URL and never mounts the film.

## Files

| File | Job |
|---|---|
| `index.tsx` | Page shell, header, the nine sections in order, the email-action branch |
| `Hero.tsx` | Section 1; the headline is `RevealLines`, the proof rail is one P3 panel |
| `Extraction.tsx` | Section 2; the pinned stage, `activeBeat`, the stacked fallback |
| `Retrieval.tsx` | Section 3; the funnel instrument |
| `ProofGate.tsx` | Section 4; figures with qualifiers, the ASK trace |
| `Telemetry.tsx` | Section 5 |
| `ResearchEvidence.tsx` | Section 6; the bento, the lazily imported chart, the tickers, the dated table |
| `Availability.tsx` | Section 7 |
| `WaitlistForm.tsx` | Section 8; protected markup, untouched by the rebuild |
| `Questions.tsx` | Section 9 |
| `Footer.tsx` | Wordmark, link groups, the protected bottom line |
| `FilmBackdrop.tsx` | Poster-first page film, `FILM_ANCHORS`, `playheadAt`, the damped seek |
| `Reveal.tsx` / `reveal.module.css` | The entrance layer: `Reveal`, `RevealGroup`, `RevealLines`, `useRevealed` |
| `scroll.ts` | The shared sampler: one rAF, one passive `scroll`, one `resize`, one `IntersectionObserver` |
| `InstructionReader.tsx`, `IntroFigure.tsx`, `DemoDialog.tsx`, `instruction.ts` | The `SKILL.md` reader, the mechanism clip, the demo dialog, the Meridian fixture and its protected URLs |
| `*.module.css` | One module per section plus `landing.module.css` for the shell |

## Tokens

Every value lives in `src/tokens/tokens.css`; `qa/check-contracts.mjs` rejects a custom
property declared anywhere else, a literal dimension or colour in a module, and a literal
breakpoint inside a module `@media`. **Responsive recomposition is a token swap inside the
1080 px and 720 px blocks, not a media query in the module.** The only module media queries
are `(hover: hover) and (pointer: fine)` and `(prefers-reduced-motion: reduce)`. The
reduced-motion `:root` block is last in `tokens.css` and wins by source order.

Token groups added for v2, by name:

- Entrance: `--duration-entrance` 420 ms, `--duration-panel` 360 ms, `--duration-draw` 520 ms,
  `--duration-count` 900 ms, `--ease-entrance` `cubic-bezier(.16,1,.3,1)`,
  `--stagger-entrance` 60 ms, `--stagger-1/2/3` 60/120/180 ms, `--stagger-cap` 240 ms,
  `--stagger-panel` 70 ms with `--stagger-panel-1/2/3` 70/140/210 ms, `--stagger-count` 40 ms,
  `--duration-draw-offset` 80 ms, `--enter-rise` 12 px, `--enter-blur` 3 px,
  `--enter-scale` .985, `--mask-hidden`, `--mask-shown`, `--full-opacity`, `--scale-full`,
  `--zero-length`.
- Film and material: `--film-lerp`, `--film-scrim-hero`, `--film-scrim-band`,
  `--film-scrim-chapter`, `--landing-film-opacity`, `--glass-backdrop` (the whole
  `backdrop-filter` value, `none` under `[data-film="on"]`), `--glass-blur` (its radius),
  `--glass-border`,
  `--glass-ground`, `--glass-highlight`, `--glass-panel`, `--glass-panel-strong`,
  `--glow-route`, `--glow-system`, `--parallax-panel` 12 px, `--parallax-chapter` 32 px.
- Type and rhythm: `--landing-display`, `--landing-display-leading`,
  `--landing-display-tracking`, `--landing-heading`, `--landing-h3`, `--landing-kicker`,
  `--landing-body`, `--landing-metric`, `--landing-metric-leading`, `--landing-metric-unit`,
  `--landing-copy-width`, `--landing-measure-gutter`, `--landing-tracking-mono`,
  `--landing-eyebrow-rule`, `--landing-section-padding`, `--landing-band-gap`,
  `--landing-grid`, `--landing-panel-pad`, `--landing-radius-panel` 16 px.
- Colour: `--landing-muted-ink` (the one muted-text token; the batched fix of 2026-09-12
  replaced `--steel` on roughly fourteen muted classes), `--tier-1` … `--tier-4`.
- Layout: the `--landing-hero-*`, `--landing-rail-*`, `--landing-retrieval-*`,
  `--landing-proofgate-*`, `--landing-telemetry-*`, `--landing-evidence-*`,
  `--landing-availability-*`, `--landing-waitlist-*`, `--landing-stage-*` and
  `--landing-scope-width-*` families.

Two radii on landing surfaces and no third: `--landing-radius` 8 px and
`--landing-radius-panel` 16 px. The task 13 audit replaced the seven remaining
`--radius-small` uses in `extraction.module.css` and `landing.module.css`. A small element
that would need a literal 50% reuses `--landing-radius`, which CSS clamps to a circle; the
reasoning is written out at `retrieval.module.css:152`.

## The entrance layer

Four patterns, all keyed on `[data-reveal-ready="true"]`, which `Reveal.tsx` sets in an
effect only after the shared observer is installed. Nothing applies to the pre-enhancement
DOM, so a missed callback, a thrown error, a refresh mid-page, reverse scroll or JavaScript
off all leave the finished composition on screen. Only `transform`, `opacity`, `clip-path`
and `filter` — never a layout property.

| Pattern | What moves | Duration and easing | Stagger | Used by |
|---|---|---|---|---|
| **P1 lift** | `opacity` 0→1 and `translateY(12px)`→0 | 420 ms `--ease-entrance` | 60/120/180 ms, capped at 240 ms | Every heading, eyebrow, subline, body and list row: extraction, how-it-works, proof-gate, telemetry, availability, waitlist, questions, footer |
| **P1 line mask** | `clip-path` `inset(0 0 100% 0)`→`inset(0 0 0 0)` plus the same 12 px rise | 420 ms | same slots | The hero `h1` only, one block per line. `clip-path` is the whole mask, so no wrapper `overflow:hidden` cuts the descenders at the 1.02 display leading |
| **P2 rule draw** | `scaleX(0)`→1 from the left | 520 ms, delayed 80 ms | — | Hairlines, beat ticks, the tier route |
| **P3 panel settle** | `opacity` 0→1, `scale(.985)`→1, `blur(3px)`→0 | 360 ms | 70/140/210 ms, capped at 240 ms | The glass instruments: hero proof rail, extraction instruments, retrieval instrument, the four evidence bento tiles |
| **P4 count** | Per-digit rolling number | `--duration-count` 900 ms, `--stagger-count` 40 ms | — | **Only in the evidence bento**, through the Spectrum `number-ticker` at the wiring layer |

`useRevealed(ref)` fires at the shared **P3 threshold, 30% visible** — not the 60% the
direction asked for. The ruling of 2026-09-11 chose the two-observer cap over the nicer
trigger point; counters therefore start a little earlier. Under reduced motion no attribute
is written at all, which is also what makes the entrance state the e2e settle signal (see
**The test contract**).

## The film

`hero-flight.mp4` is 10.041667 s at 24 fps, 241 frames, re-encoded at `-g 6` (a keyframe
every 0.25 s) at 1.10× the original bytes; the webm was restored to its original bytes
because `-g 12` cost 1.42× for no scrub gain.

The playhead is a **piecewise-linear anchor map built from the measured offsets of the nine
section elements**, not a table of scroll fractions; it is recomputed on resize, rotation,
font load and after the film's metadata arrives. `FILM_ANCHORS` in `FilmBackdrop.tsx`:

| Section id | Playhead | Beat |
|---|---|---|
| `hero` | 0.00 | Table above the clouds, the drawn orange route, the sunrise window |
| `extraction` | 1.40 | The fall into the terrain: contour valley, teal rings, the map sheet lifting |
| `how-it-works` | **4.30** | Four cream cards standing in a fan around one lit orange marker |
| `proof-gate` | **5.75** | The route crossing a plateau edge, teal rim light on the boundary |
| `telemetry` | 6.80 | Stacked plateaus held wide, cubes across the lower tiers |
| `research-results` | 7.80 | Upper plateau, sparse cubes, the route arriving at the top tier |
| `availability` | 8.60 | Pull-back begins, the terrain reads as a map again |
| `waitlist` | 9.10 | The map rising into its folds |
| `questions` | 9.70 | The folded map on the desk beside the wordmark; a terminal anchor holds the last frame |

The two bold values are the **measured cuts**, not the design seconds. ffmpeg scene detection
put the hard cut to the four-card fan at **4.2083** (scene score 0.23) and the continuous
pull-back at which the plateau edge becomes the subject at **≈5.67**; the shipped anchors sit
the cut plus ≈0.09 s, because the scrub's delta gate stops writing once the residual is under
one frame and an anchor placed exactly on a cut still renders the previous shot on a forward
approach. The only other hard cut, the folded map at **8.8333**, falls inside `availability`,
whose own beat is the pull-back that precedes it.

The scrub keeps the damped seek `current += (wanted - current) * .14`, writes only when the
delta exceeds one frame, and never writes while `seeking`.

**Known deviation, measured 2026-09-12.** With a section parked at its own top, the sticky
header leaves an 80 px scroll offset, and that offset eats the +0.09 s margin: `how-it-works`
settles at 4.2002 (0.008 s *before* its cut) and `proof-gate` at 5.6686. A visitor landing on
either section therefore sees the tail of the previous shot. `qa/landing-v2/retrieval-1440.png`
shows the map sheets rather than the four-card fan. Remedy recorded in
`ui/qa/landing-v2-gate.json` under `film-anchors`; `FilmBackdrop.tsx` was outside the gate
task's file scope.

## The pinned extraction chapter

One sticky stage with three beats, all three in the DOM and all three reachable. The track
carries `data-p-ready="true"` only when a sampler is actually installed, and
`data-active-beat` changes only when the beat changes. Base rules paint the **stacked
fallback**: at 720 px and below, with JavaScript off, under reduced motion and under
Save-Data the chapter is three stacked blocks and the pin never engages. The pyramid keeps a
stepped shape at 390 px through `--landing-scope-width-1..3` in the 720 block.

The sampler is motion's imperative `scroll()` rather than `scroll.ts`. This is a **recorded
exception to the one-sampler rule**: routing it through `scroll.ts` was out of the chapter
task's scope and the cost is a second passive scroll listener.

## Media contract

- The hero poster `hero-poster.webp` (1920×1080, 126 KB) is preloaded in `index.html` with
  `fetchpriority="high"` and is never removed.
- The `<video>` is **mounted** only when the hero is in view, motion is allowed, Save-Data is
  off and the poster has decoded. Conditional mounting, not `preload="none"`, is what
  guarantees zero requests.
- It crosses in on `canplay`, pauses on `visibilitychange`, on leaving the viewport, on user
  pause and while the demo dialog is open, and unmounts on `error` or if `canplay` has not
  fired within **8 s**.
- Reduced motion and Save-Data render the posters and create no video element at all.
- Blocking the film leaves `data-film` unset and the poster in place; the page renders
  complete.
- The demo dialog mounts the nocookie iframe only while it is open, traps focus and restores
  it to the Play demo button.

## Fonts and CLS

`index.html` preloads the four faces the first viewport actually uses — Manrope 400 and 600,
Instrument Sans 600, JetBrains Mono 400 — and Vite rewrites those `node_modules` paths to the
hashed build assets. `#root` carries `display:flow-root`, which stops the
pre-mount fallback heading's margin collapsing through to `body`; that collapse, plus three
un-preloaded above-the-fold faces swapping in, was the whole of the 0.047 cold CLS.

`index.html` preloads **no image**. It used to preload `guidefold-stone-hero-v1.webp`, which
no component renders. Repointing that hint at `hero-poster.webp` measured 2,696 ms LCP at
1440 on an emulated 4G profile; removing it measured 2,152 ms, because 126 KB of
`fetchpriority="high"` image sat ahead of the render-critical bundle while the LCP element is
the hero copy. The poster still paints: `FilmBackdrop.tsx` renders it with
`fetchPriority="high"` and it is requested exactly once.

## Spectrum decisions

Installed with provenance in `qa/spectrum-registry.json`, hash-pinned, never edited in place;
adaptation happens at the wiring layer.

| Item | Decision |
|---|---|
| `bento-grid`, `bento-card` | Installed; used for the evidence bento. Wiring passes `borderAnim={false}` and gates the spotlight on Save-Data. The hover transform is neutralised with one `!important` and a comment, because the file is hash-pinned |
| `number-ticker` | Installed; drives P4, and **only** in the evidence bento |
| `border-beam` | Installed by the component task, **unused** on this page |
| `spotlight` | Installed; gated on Save-Data |
| Pinned stage | Exception: aceternity sticky-scroll was rejected and the stage hand-built with `motion`. Obstacle: the registry component owns its own scroll sampler and its own DOM, neither of which can be reconciled with the anchor map or the stacked fallback |
| `faq-tabs-card` | Exception: the FAQ stays the existing `Collapsible`. Obstacle: the registry card is a tabbed container, not four independently deep-linkable panels, and `#privacy` must open one |
| `status-tracker` | Exception, recorded at `Telemetry.tsx:21`. Obstacle: its long-running-job framing would have to be rewritten to mean promotion state |
| `orbital-letters`, marquee | Exception: both are decoration without a data reason on a page whose atmosphere is already the film |

`RevealGroup` must not wrap a `BentoCard`: it wraps component children in a slot div, which
would become the grid item and defeat `colSpan`/`rowSpan`. The bento applies P3 per tile with
`Reveal` as the grid item carrying the span class.

The evidence chart is **rendered once**, in the tall tile; the duplicate lower figure was
removed.

## The hero at 390

Controller ruling, 2026-09-12 (whole-branch review C1). **The body paragraph is in the DOM and
visible at every width.** It used to be `display:none` below 720 together with the scroll cue,
which removed the scale envelope and the "nothing unproven arrives" promise from the page and
from the accessibility tree for every phone reader. Only the scroll cue is still dropped at
≤ 720, and it is dropped whole: the header is static there, the next section is one thumb away,
and the cue is navigation, not an argument.

The fold is bought back from spacing and from the body's own type, never from content:
`--landing-hero-body-size` 14 px / `--landing-hero-body-leading` 1.4 (its own tokens, so the
six other sections keep `--landing-body` 17 px), `--landing-hero-body-margin`,
`--landing-hero-lede-margin` and `--landing-hero-actions-margin` 12 px, `--landing-rail-pad`
8 px, `--landing-rail-gap` 4 px, `--landing-rail-stack-pad` 6 px, `--landing-rail-figure`
18 px. No `order`, no grid-area move: DOM order is still visual order.

Measured at 390 × 844 in Chromium, document coordinates:

| Element | Top | Bottom |
|---|---|---|
| Proof rail | 684 | 888 |
| Cell 1 (figure + qualifier) | 693 | 781 |
| Cell 2 figure | 792 | 837 |
| Cell 2 qualifier | 841 | 879 |

The first cell is complete above the 844 px fold and the second figure is complete above it
too. The second qualifier crosses the fold by 35 px. Both cells complete would need another
35 px, which only the headline size or the wrapped header could give, and neither is a
spacing lever; the ruling's minimum is met and this is the recorded limit, not an oversight.
A qualifier below the fold is still rendered with its figure — nothing is dropped alone.

## Orange, three times

DESIGN v2 §2.2 says "at most twice"; the page ships three instances and `Hero.tsx:63-65`
states the count. The three are the hero tier route (`hero.module.css:164`), the extraction
promoted row, and the full stop in the footer wordmark (`landing.module.css:126`). Each is
the same meaning — the rule that was promoted — at the start, the middle and the end of the
page, and none of them is decoration. The implementation keeps three; the spec line is the
one that is out of date.

## The test contract

`e2e/landing-flow.spec.ts` no longer sleeps before axe. It sweeps the scroll to the bottom
and back so every `IntersectionObserver` fires, then waits until no
`[data-reveal-ready="true"]:not([data-reveal-entered="true"])` remains, then drains the
finite CSS animations. axe scans the document, not the viewport, so waiting only on what is
on screen is not enough: a section still at its pre-entrance opacity reads as a
colour-contrast violation on tokens that measure 7.98–12.84:1 at rest. Both the wait and the
drain are capped, so a stalled animation degrades to roughly the old fixed delay rather than
failing the suite for the wrong reason.

## Measured, 2026-09-12

Production build served by `vite preview`, Chromium via Playwright, one WSL2 machine. Full
table and limits in `ui/qa/landing-v2-gate.json`.

| Item | Measured | Contract | Verdict |
|---|---|---|---|
| Unit suite | 375 / 375, 42 files | — | pass |
| Contracts | passed, 398 tokens, 0 diagnostics | 0 diagnostics | pass |
| Landing e2e | 13 / 13, three consecutive runs (the third after the 2026-09-12 fix wave) | — | pass |
| JS budget | landing chunk 25,216 → 36,242 B gzip, **+10.77 KB** | ≤ +34 KB | pass |
| CLS, cold | **0.0000** at 1440 and 390, and under emulated 4G | 0 | pass |
| LCP | hero copy at 472 ms (1440) and 440 ms (390) local; 2,152 ms (1440) and 832 ms (390) on emulated 4G | ≤ 2.0 s | over at 1440 on that profile |
| LCP element | the hero copy, not the poster | — | recorded per the 2026-09-11 ruling |
| Frame budget, pinned chapter | 0 long tasks, frame median 16.7 / 16.8 ms at 4× CPU | 0 long tasks | pass |
| Frame budget, whole page | 1 long task (192 / 201 ms), attributed to the lazy chart by blocking it | 0 long tasks | fail, attributed |
| First-scroll long task | 0 at 1× CPU; at 4× two tasks that both land before the scroll | — | not the sampler |
| Contrast over film | worst case per section 4.66 – 12.18:1; hero display 10.92:1 at the sunrise anchor | body 4.5, large 3, display 7 | pass |
| Film scrub | 302 forward samples, 0 backward steps; fast reverse settles to 0.002 s | — | pass |
| Film anchors | `#how-it-works` settles at 4.317 s (cut 4.2083), `#proof-gate` at 5.770 s (cut ≈5.67) | past its own cut | pass |
| Observers and listeners | 2 scroll, 5 resize, 6 IntersectionObserver, 5 ResizeObserver | the page's own code opens one scroll sampler and the two-observer entrance pool; the remainder belong to the two recorded exceptions, motion's `scroll()` and the Spectrum bento's `whileInView`, neither of which the wiring layer can collapse without editing a hash-pinned file | pass, as built |
| `content-visibility: auto` | 0 | 0 | pass |
| `backdrop-filter` with `data-film="on"` | **0 live surfaces** (`--glass-backdrop: none`; swept with `getComputedStyle` over every element) | none | pass |
| Targets at 390 | every visible link and button ≥ 44 × 44 across the whole document, header included; the consent checkbox's target is its 44 px `label`; inline links inside a sentence are excluded by name | 44 × 44 px | pass |
| axe | clean at 1440 and 390, FAQ closed and open, dialog open, reduced motion | clean | pass |
| Console and network | 0 errors across the capture pass | 0 | pass |

**What these prove and do not.** They prove the page builds, types, passes its own suites and
behaves as described on this machine in Chromium. They do not prove field performance: the 4G
figures are DevTools emulation over a local preview, the frame interval is rAF cadence floored
at vsync rather than a reading of main-thread work per frame, contrast is sampled at each
section's own scroll position rather than on every frame, and the anti-slop screenshot test was
read by an agent, not by an engineer outside the project. The 30k envelope is designed for, not
measured; no latency figure appears on the page.

## What must not come back

Still banned: the 3D pyramid, the WebGL hero atmosphere, the schema-flow canvas, autoplaying
feature demos, the typewriter, the shine sweep, per-word text reveals, `MorphButton` on this
page, any new dependency, any new font fetch, any new icon library. Also banned for this page:
gradient text or a headline with one word in a different colour or weight; a row of three
identical cards; glow blobs, mesh gradients and radial aurora backgrounds; stock icons in
circles, an icon per feature, emoji as icons; the all-caps tracked eyebrow; a directional glyph
glued to link or button text outside the two primary actions; meta strings joined with middle
dots; glass on anything that is not a real instrument; a third radius; a figure without its
denominator, date or status word; presenting 17/20 as task-level proof or 0/76 as zero risk.

Lifted by the owner verdict of 2026-09-11 and now shipped: **section entrance motion**,
**scroll-triggered content motion**, **the 240 ms motion ceiling** and **the
single-hero-entrance rule**. Motion above 240 ms is permitted only for the four patterns above
and for the film. The v1 record's "no section reveals, no scroll-triggered content motion"
line no longer applies and has been removed rather than left to mislead.

Beam cards, beam search and the fold-film hover choreography remain in the repository for the
management UI; the landing route does not import them.
