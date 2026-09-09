# Guidefold landing rebuild - build notes

Branch `landing/why-how-value`. Writer: Claude (sole writer). Nothing committed.
Sources of authority, in order: `preservationMap` in `ui/design/landing/design-brief.json`,
the owner verdict recorded there, `ui/design/landing/DESIGN.md`,
`ui/design/landing/motion-prompt-packet.md`, then the craft skills.

## Gates

| Command | Result |
|---|---|
| `pnpm typecheck` (`tsc --noEmit`) | passed |
| `pnpm build` (`tsc --noEmit && vite build`) | passed |
| `pnpm test` (vitest) | 32 files, 306 tests passed |
| `node qa/check-contracts.mjs` | passed - 15 components, 25 CSS files, 270 tokens, 0 inline style properties, 0 diagnostics (`qa/contracts.json` regenerated) |
| Screenshots | `ui/qa/landing-v2-390.png`, `ui/qa/landing-v2-1440.png` - full page from the production build served by `pnpm preview` on 4331; horizontal overflow 0 at both widths; zero console errors, page errors or failed requests |

E2E was rewritten but not run (allowed by the task): `ui/e2e/landing-flow.spec.ts` now
targets the new DOM under `playwright.landing.config.ts`.

## Sections as built

`hero → why → how-it-works → value → availability → waitlist → questions → footer`.
Layout families A, B, C, D, E, F, G, plus E reused for the footer. One `h1`, one `h2` per
section, `h3` only inside the FAQ triggers. Semantic DOM order equals visual order equals
tab order at every breakpoint.

## UI UX Pro Max implementation check

Accepted rules, all applied:

1. **Spacing scale 4/8/16/24/32/48/64** - `--space-1..7` only. `check-contracts.mjs`
   proves no off-scale literal survived: it rejects any literal dimension in a module.
2. **Category "Developer Tool / IDE", `must_have: documentation`** - `/docs/` in the
   header nav, in the availability band (`Read the docs`) and in the footer.
3. **Mono + humanist-sans pairing** - JetBrains Mono for paths, URNs and the fixture
   excerpt; Manrope body; Instrument Sans display. No font added, none fetched.
4. **Dark ground, not light-mode default** - `color-scheme: dark` and the graphite token
   set are unchanged; no light theme was introduced.
5. **Staggered fade-in entrance, reduced** - the hero copy stack only: opacity plus a 2px
   rise, 200ms, 40ms stagger, four items, chain 120ms. Below the fold there is no
   entrance at all.
6. **Lead-magnet form: ≤3 fields, visible submission progress** - one visible text input,
   one required checkbox, one honeypot. Loading is `disabled` + `Saving…` + `aria-busy`.
   No field was added.
7. **Trust & authority: transparent pricing, low-friction form** - the pricing answer and
   both availability statements stay on the page.
8. **Heading/body weight separation, sequential `h1→h2→h3`, one modular scale** - applied.

Rejected rules, all kept out - verified by reading the built page: no bento grid, no
floating action button, no glassmorphism or blur backdrop, no gradient button, no spring
or `.96` haptic press (press is the existing `--press-scale` .98 with `--ease-out`), no
`#22C55E`/`#0F172A` palette, no IBM Plex Sans or Google Fonts URL, no pulsing status dot,
no per-segment hero, no scroll-triggered storytelling chapters or progress indicator, no
before/after or comparison-table conversion claims, no coloured three-step funnel, no
light mode.

**Riskiest implemented interaction, checked against the accepted UX guidance:** the FAQ
`Collapsible`. Accepted UX guidance requires sequential heading hierarchy and a real
control; the preservation contract additionally requires all four answers to be *in the
DOM on load with the panel closed*. Base UI unmounts a closed panel by default, so the
first implementation satisfied "closed" but failed "present". Disposition: `keepMounted`
on `Collapsible.Panel`, and a test asserts both the `aria-expanded="false"` state and the
presence of the `$99` and 30-day strings on load.

## Motion Prompt Packet check

Archetype implemented: **ambient loop with copy-safe field**, with scroll-linked depth
planes as the secondary mechanic. Layer order L0 ground, L1 topo, L2 survey grid, L3
section plane, L4 poster, L5 loop, L6 scrim, L7 content at zero movement. Amplitudes 16 /
40 / 20 / 12px, halved at 720px, all under the 40px cap. One rAF, one passive `scroll`
listener, one `resize` listener, one `IntersectionObserver`, no React state per frame.

**Riskiest acceptance check: #21 - "reduced motion: the route rule is fully drawn on
first paint via its explicit `q = 1` override, not via the `--p` formula".** This is the
one element whose `--p = .5` evaluation (`q = .727`) is wrong at rest. Implementation:
the base rules paint the route complete (`stroke-dashoffset: var(--zero)`, both waypoints
at opacity 1) and the `--p` mapping is applied only under a `[data-p-ready]` attribute
that `scroll.ts` writes when it actually registers an element. Under reduced motion,
Save-Data and no-JS the sampler never installs, the attribute never appears, and the rule
rests drawn - and the reduced-motion media query repeats the override so a stale attribute
cannot defeat it. **Result: pass.** Verified two ways: the drawn state is the default in
the stylesheet, and with the sampler running at `--p = .4945` the computed
`stroke-dashoffset` is `159.7px` of a 560 dash array, i.e. the formula is live only when
the sampler is.

Other packet items verified at build time: nothing exceeds 240ms; stagger chain 120ms;
the only scroll-driven properties are `transform` and `opacity`; content layers do not
move; scrolling to the footer and back returns identical transforms (a pure function of
geometry - covered by a new e2e assertion); reduced motion and Save-Data create no video
element and request no video bytes, because the elements are conditionally mounted rather
than merely `preload="none"`.

## Copy audit

`copy.md` used verbatim for every line, in reading order. Every protected string is
byte-identical to the previous implementation: the waitlist note, label, placeholder,
submit and loading labels, consent text, honeypot label, the three success strings, the
four error strings, the confirm/unsubscribe titles, bodies, results and buttons, all four
FAQ answers with the pricing figures and the full privacy answer, both availability
statements, the footer bottom line, the document title and `Skip to content`, and the
Meridian fixture excerpt.

Deliberate deviations from the previous page, all mandated by `copy.md`:

- Hero lede replaced with the README line; the unverified `opt-in proof checks` claim is
  gone.
- `Try the demo` renamed `Play demo` in the hero and the footer.
- Signup heading `Bring your team’s knowledge into focus.` → `Get availability updates`.
- The cut sections (`Instructions, selected by task.`, `Trace the instruction.`,
  `One monorepo…`, `A shared library…`, the workbench caption) are gone with their
  components.

No new editable copy was written beyond `copy.md`, so `humanizer` / `avoid-ai-writing`
had nothing to re-audit; the audit recorded in `copy.md` stands.

## Files added

`src/routes/landing/`: `index.tsx`, `landing.module.css`, `scroll.ts`, `HeroMedia.tsx`,
`IntroFigure.tsx`, `DemoDialog.tsx`, `InstructionReader.tsx`, `RouteRule.tsx`,
`WaitlistForm.tsx`, `Footer.tsx`, `instruction.ts`, `DESIGN.md`.
Plus `ui/reports/build-notes.md` (this file).

## Files edited

- `src/tokens/tokens.css` - the dead landing, workbench, film, pyramid and material-pyramid
  token groups replaced by one landing-v2 block plus its `1080px` and `720px` swaps.
- `src/main.tsx` - lazy import now `./routes/landing`.
- `src/routes/Landing.test.tsx` - rewritten (13 tests).
- `e2e/landing-flow.spec.ts` - rewritten for the new DOM.
- `qa/contracts.json` - regenerated by `qa/check-contracts.mjs`.

## Files deleted

`src/routes/`: `Landing.tsx`, `Landing.module.css`, `LandingDemo.tsx(+css)`,
`LandingMotion.tsx(+css)`, `LandingWorkbench.tsx(+css)`, `LandingPyramid.tsx(+css)`,
`MaterialPyramid.tsx(+css)`, `pyramidThree.ts`, `HeroAtmosphere.tsx(+css)`,
`LandingFooter.tsx(+css)`.
`e2e/landing-pyramid.spec.ts`, `e2e/landing-workbench.spec.ts`.
`qa/check-pyramid-production.mjs` - it asserted `[data-slot="pyramid-explainer"]` against
the live site; the slot no longer exists.

## JS delta

`three` no longer appears anywhere in `dist/` (`grep -rl THREE dist/assets/*.js` returns
nothing), so the whole WebGL pyramid, `pyramidThree.ts` and `@types/three` surface left
the shipped bundle rather than moving to another chunk. `SchemaFlow`, `beam-card` and the
`spectrumui` chunks still build because the management app imports them; the landing entry
no longer reaches any of them. The landing route chunk is now **55.5 kB raw / 18.7 kB
gzip** plus its lazy `CollapsiblePanel`, `DialogTrigger` and `SkillContent` chunks. An
exact before/after number is not reportable: the previous landing sources were untracked
in git, so there is no clean tree to rebuild for comparison.

## Protected exceptions and deviations

1. **`transition-all` in `src/components/ui/button.tsx`.** The prohibited list bans
   `transition: all`, but that file is hash-pinned in `qa/spectrum-registry.json` and
   editing it fails the contract check. The landing module declares its own explicit
   `transition` on the button classes, which wins the cascade (CSS modules are unlayered;
   Tailwind utilities are layered). Recorded, not fixed.
2. **Skip link before nav.** `motion-prompt-packet.md` acceptance 22 lists the tab order
   as "nav → skip target", while `preservationMap` and `design/landing/DESIGN.md` §9 both
   require the skip link to be the first focusable element. The preservation contract is
   higher authority, so the skip link is first.
3. **Press and dialog scale.** The task prompt paraphrased these as `.97`; the packet's
   own table says `--press-scale` `.98` and dialog popup `.95 → 1`. The packet was
   followed.
4. **No section entrance animations.** The task prompt asked for "one reveal per section,
   opacity + translateY(8px)". `design/landing/DESIGN.md` §11 and the packet both remove
   reveal-on-scroll section wrappers and ban entrance animations below the fold. The
   binding documents were followed: the hero entrance is the only entrance on the page.
5. **HOW column order at ≤1080px.** `design/landing/DESIGN.md` §5 says "intro figure
   first" when HOW collapses to one column. Implementing that with CSS `order` would break
   §9's rule that DOM order equals reading order. Instead the copy column was split into
   `howIntro` (h2 + answer sentence) and `howDetail` (beats, route rule, links,
   disclosure), with the figure between them in the DOM. Mobile therefore reads heading →
   answer → figure → beats, and desktop still places the figure in the right column
   spanning both rows, with no CSS reordering anywhere.
6. **Focus ring colour.** `global.css` uses `--safety-orange` for the whole product;
   `design/landing/DESIGN.md` §9 requires `--survey-teal` on the landing page. Scoped to
   `.page :focus-visible` so no management screen changes.
7. **No-JS demo fallback.** The packet asks the demo trigger to degrade to a plain link
   without JavaScript. The app is a client-rendered SPA, so nothing renders without
   JavaScript at all; the plain `Watch on YouTube` link is present inside the dialog as the
   non-embed path. This is a pre-existing property of the shell, not a regression.

## Hero fallback path taken

**Generated keyframe only.** `hero-loop.mp4` / `.webm` do not exist on disk, so the hero
renders `hero-poster.webp` and the `<video>` fails closed with no message and no layout
shift - which is exactly the path the screenshots show. `hero-poster.webp`,
`plane-why/how/value.webp` are still byte-identical copies of `topographic-route-bg.webp`,
so the hero and the section planes currently show one texture; the composition is written
against the final 1920×1080 keyframes and needs no code change when they land.
`intro.mp4` / `.webm` / `intro-poster.webp` are real and the HOW figure plays.

## Instruction reader

Successfully reduced, not cut: one bordered panel, two tabs (`Read instruction` /
`Markdown source`) with the sliding indicator, `SkillContent`, `CodeBlock`, the
`Repository source` badge, the fixture label and `Open the original file`. The
`BeamCard` frame, the `BeamSearch` filter, the five-rule sidebar, the keyboard/pointer
data attributes and the workbench caption are gone.

## Unresolved findings

- **Sampler cost per frame was not measured on a throttled profile.** The engine is one
  rAF that writes at most five custom properties per frame with no layout read outside
  `getBoundingClientRect`, but the 1ms/frame budget on a mid-range Android is unverified.
  If it misses, the fix named in the brief is to disable the sampler under Save-Data.
- **Hero headline contrast against the brightest loop frame is not measurable yet** - the
  loop does not exist. Against the current poster inside the copy-safe field the scrim is
  `rgba(7,9,12,.94)` at x=0 falling to `.06` at x=68%, and `--landing-ivory` on that ground
  clears 7:1 comfortably. Re-measure when `hero-loop` lands.
- **Loop seam, `ffprobe` audio-stream check and the poster/frame-0 comparison** cannot be
  run: no loop asset.
- The e2e suite was rewritten but not executed.

## Addendum, same session: the scroll film and the scope pyramid

Two owner instructions arrived after the gates above passed. Both were implemented and
re-gated; both are deliberate departures from the approved brief and are recorded here.

### 1. The background is now a scroll-driven film

**Owner instruction.** "The generated video is terrible. The prompt has to call for
dynamic camera movement through the map world. It will change with scroll, so it needs
many sub-scenes." A reference frame was supplied: a cinematic stone table with etched
contours, a glowing orange route with waypoints, a teal accent and a window onto
mountains.

**Departure from the brief.** `DESIGN.md` prohibits scrubbed video, pinned sections and
scroll-jacking. Scrubbed video is now in the page on the owner's explicit instruction.
Pinning and scroll-jacking were not introduced: the page scrolls normally and only the
playhead follows.

**How it was produced.** Five reference stills were generated first, one per beat, then
fed to Seedance 2.0 as `start_image` (beat 1), `end_image` (beat 5) and three
`image_references`, so the render inherits the composition rather than inventing one.
Prompt and negatives are in `design/landing/video/flight-prompt.txt` and
`flight-negative.txt`; scene prompts are in `design/landing/scenes/`.

**Two rejected renders, and why.** A Seedance 2.5 ambient loop measured 34-57% maximum
luminance inside the declared copy-safe box against a 22% ceiling: the paper drifted under
the headline. A Kling 3.0 Turbo attempt anchored on the same keyframe was worse: up to 77%
in the same box, a 75% pixel change across the loop seam, and an audio track. Neither was
shipped. Evidence: `design/landing/video/acceptance.mjs`.

**Implementation.** `FilmBackdrop.tsx` holds a fixed full-viewport poster, the video and
one scrim. `useDocumentProgress` in `scroll.ts` feeds document progress to the same frame
that already writes `--p`, so there is still exactly one rAF, one scroll listener and one
resize listener on the page. The playhead eases toward the scroll target and is written
only when it has moved more than a frame, so a fast scrub does not queue a seek per tick.
The film is encoded at 1280x720 with a keyframe every twelve frames, which is what makes
seeking smooth; MP4 is offered before WebM because H.264 seeks faster.

Measured (`qa/landing-film.mjs`): scroll 0/0.25/0.5/0.75/1 maps to playhead
0/2.511/5.020/7.501/10.041s, and scrolling back to 0.25 returns 2.522s, a quarter of a
frame from the forward pass. Under reduced motion: zero video elements, zero film
requests, poster visible. With the film route aborted: no `data-film` flag, poster
visible, zero horizontal overflow. No console or page errors in any of the three runs.

The hero's own `<video>` and its scrim were removed. One film now carries every section,
which also removed a vertical seam where the hero scrim used to end.

### 2. The three-dimensional pyramid is now a scope ladder

**Owner instruction.** "In that 3D pyramid you cannot see at all that these are
organisations and skills. Nothing is visible."

`ScopePyramid.tsx` replaces it with four rows read from the bundled Meridian example
repository: `meridian` (security-baseline, release-process, monorepo-conventions),
`atlas` (atlas-api-conventions), `atlas / identity` (rbac-policies,
legacy-session-auth) and `atlas / identity / turnstile` (postgres-auth,
turnstile-oncall-runbook), each with its reach stated. Every scope path and skill name
is verbatim from `examples/monorepo`; nothing is invented. The bar widths narrow with
scope and are tokens; nothing in the block animates.

### Re-gated after both changes

| Check | Result |
|---|---|
| `pnpm typecheck` | passed |
| `pnpm build` | passed |
| `pnpm test` | 32 files, 306 tests passed |
| `node qa/check-contracts.mjs` | passed, 0 diagnostics |
| `pnpm exec playwright test --config playwright.landing.config.ts` | 7 passed |
| `node qa/landing-verify.mjs` | axe 0 violations, 0 horizontal overflow at 390 and 1440, 0 console errors |
| `node qa/landing-contrast.mjs` | worst-case text contrast over the running film, per section: hero 7.39, why 15.79, how 12.05, reader 10.84, value 16.04, availability 8.10, waitlist 7.98, questions 6.28. AA needs 4.5 |

Two findings from the read-only review were fixed in the same pass: the header nav is no
longer hidden below 720px (it wraps to a second row instead of disappearing), and `--p`
is written on the fixed background layer rather than on the page root, which took whole
document style invalidation off every scroll frame.

Not done: no throttled-device profile was measured, and the film's cost per frame on a
low-end Android is unknown.
