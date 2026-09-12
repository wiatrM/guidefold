# Guidefold landing — implemented system (v3)

Status: **Implemented**. Date: 2026-09-12.
Purpose: the durable record of what `ui/src/routes/landing/` actually contains after the v3
rebuild, and of the places where implementation had to choose.
Inputs: `ui/design/landing/v3/SPEC.md` — binding, and the only direction this implements —
the preservation contract in `ui/design/landing/design-brief.json` (`preservationMap`), and
the measured scroll investigation whose remedies R1 and R2 the spec adopts.
Replacement scope: this file replaces the v2 implemented-system record for this directory.
It replaces nothing outside `ui/src/routes/landing/`. Where `ui/design/landing/v2/` still
describes a section this page no longer has, v3 wins.

Authority order: preservation contract → owner instruction → `v3/SPEC.md` → craft skills.

Nothing below is described as done unless a command checked it. The numbers are in
**Measured** at the end, with the commands that produced them.

## 1. Reading order and ids

Nine sections inside `<main>`, then the footer outside it. DOM order is reading order is
tab order is visual order at every width; no module uses CSS `order`.

| # | id | file | what it carries |
|---|----|------|-----------------|
| 1 | `hero` | `Hero.tsx` | H1, one sentence, two actions, the trust line, the arrow-down cue, and the organisation portal in a device frame |
| 2 | `why` | `Why.tsx` | three roles as a `dl`, hairlines between, one value panel |
| 3 | `extraction` | `Extraction.tsx` | the pinned chapter, three beats, as the owner approved it, plus its value panel |
| 4 | `portal` | `Portal.tsx` | the review view in a device frame |
| 5 | `how-it-works` | `Retrieval.tsx` | the instrument: what was typed, what the service did, the four cards; the usage view; the protected reader in a `details` |
| 6 | `under-the-hood` | `UnderTheHood.tsx` | SEARCH / USE / ASK in plain words, the footnote, the rule library in a device frame |
| 7 | `proof` | `Proof.tsx` | two figures from the evidence mirror, two small-print lines, one link |
| 8 | `waitlist` | `BelowHero.tsx` | the two protected availability statements and the untouched `WaitlistForm` |
| 9 | `questions` | `Questions.tsx` | the four protected Collapsible answers |
| — | `footer` | `Footer.tsx` | unchanged from 39f2396 apart from its id and its container |

Removed with v3, and the files deleted with them: the use-case chapter, `ProofGate.tsx`,
`Telemetry.tsx`, `ResearchEvidence.tsx` (and `proofgate/telemetry/evidence.module.css` and
their three test files), `Availability.tsx` and `availability.module.css`, `IntroFigure.tsx`,
the hero proof rail, the tier glyph, the demo stage and the pre-JS text shell in
`index.html`. `evidence.test.ts` stays: it guards the data mirror, not a component.

New files: `DeviceFrame.tsx`, `ValuePanel.tsx` (+ `value.module.css` + `ValuePanel.test.tsx`),
`Why.tsx`, `Portal.tsx`, `UnderTheHood.tsx`, `Proof.tsx` and their four modules.

## 2. The page grid

One container, and every section's content box is it. `landing.module.css` declares
`.shell` (max-width `--landing-container`, auto side margins, `--landing-gutter` side
padding) and `.grid` (which composes `.shell` and adds the twelve columns and
`--landing-column-gap`). Every section composes one of the two.

The sections themselves are full-bleed. That split is the whole point: a band's background,
the hero scrim and the film run to the viewport edge while the content keeps the page's
margins. Before it, `.page` carried the max-width and the padding, and a strip of film
showed down the right edge of a 1440 viewport while the FAQ stopped 500 px short of the
waitlist form above it.

`--landing-container` is 1280 px. `--landing-gutter` is 72 / 48 / 24 / 20 px at
1440 / 1080 / 720 / 390. Measured content edges are in **Measured**.

Two-column blocks split on the same twelve columns: the hero is copy 1–6 and screen 7–12,
the waitlist is copy 1–5 and form 7–12, and everything else is 1–12. No block's copy is
narrower than its column: the 34ch and 46ch measures are gone, and the value panel and the
headline end on the same pixel.

## 3. The value panel

`ValuePanel.tsx` is the one implementation of the spec's `What you get:` line, used on six
blocks and nowhere else. Glass surface, `--landing-radius-panel`, `--landing-panel-pad`,
a 2 px teal rule inset down the left edge, the label in the accent colour at the eyebrow
size, the sentence at the lede size in `--landing-ivory`. The label is inside the sentence
rather than a badge above it, so the rendered text is exactly the spec's string and a
screen reader hears one sentence.

Entrance, once, at 30 % of the panel in view — the same threshold and the same shared
observer pool the page's P3 panels already use, so it opens no new observer. The rule draws
top to bottom over `--duration-draw`, the label fades at 80 ms, the sentence lifts 12 px and
fades at 160 ms, and a teal glow settles out of the rule over 900 ms. That glow is the one
`@keyframes` on the page: a transition cannot express a there-and-back.

Base-state discipline as everywhere else: every entrance rule is keyed on
`[data-value-ready="true"]`, written in an effect after the observer exists. A missed
callback, a thrown error or a platform without `IntersectionObserver` leaves the finished
panel. Under reduced motion the durations are zero in tokens.css and `useRevealed` reports
entered on mount, which is the resting state.

## 4. Motion

**Entrances.** P1 lift for copy, P3 settle for the device frames and the service panels,
once, through `Reveal.tsx` unchanged. P2 is used only by the value panel's rule. P4 Count is
the proof band's two tickers and runs nowhere near the LCP window.

**The film.** Scrubbed by scroll, never played. The poster still is gone: `.film` paints
`--graphite-950` and the video fades up over it once it can seek, so every failure path —
reduced motion, Save-Data, a decoder error, a missing file, no `canplay` inside eight
seconds — leaves the graphite field with nothing left to load. `mounted` no longer waits on
a decoded still.

**R1, the measured seek fix** (`FilmBackdrop.tsx`). Scrubbing used to write `currentTime`
on every rAF tick that cleared `!node.seeking`: about 66 writes a second into a decoder
presenting 21–28 frames a second, which the investigation measured as 41–44 % of all
main-thread busy time during a scroll pass and 80 % of paint time. A write now needs three
things: no seek in flight, 33 ms of wall clock since the last write, and more than one
frame of drift. "In flight" clears on `requestVideoFrameCallback`, on `seeked` where that
API is absent, **or** on a 100 ms timer — the escape hatch is not optional, because a seek
that resolves to the frame already on screen fires no callback at all and a naive flag
would freeze the film permanently with every test still green. The loop also parks itself
once the damper has arrived (`|wanted − current| < FRAME/4`) and is restarted from the
`useDocumentProgress` callback, instead of running forever on a page at rest. That wake-up
lives in `FilmBackdrop` rather than as a `lastScrollAt` clock in `scroll.ts`, because
`scroll.ts` is shared by every registered section and only this one consumer needs it.

**R2, the pinned chapter** (`Extraction.tsx`, `extraction.module.css`). `--landing-stage-scroll`
is 150vh, down from 260vh: about 1 100 px of document at 1440 and no beat lost, since the
three windows are fractions of the track. The window arithmetic now exists in exactly one
place — `beatOpacity` — and the sampler writes its result as `--o` onto the three beats and
the three ticks, plus `--p` onto the three beats for the parallax and the tier route, which
inherit it. Before, one `--p` on the stage invalidated style for the whole pinned subtree
every frame. `--o` rests at 1 in tokens.css, so with no sampler all three beats are simply
visible, which is the stacked fallback this chapter already rendered. `.instrument` carries
`contain: layout style` — not `paint`, which would clip the glass panel's backdrop. The
permanent `will-change: transform` is gone from `.stage`.

The `--p`/`--o` writes deliberately target the beats and the ticks rather than the panels:
`Instrument` swaps its element type when the pin engages, so a reference to a panel captured
in the layout effect would be detached by the time the sampler ran.

**Reduced motion** installs no sampler at all, mounts no video, and rests on the finished
composition. No scroll-linked motion exists outside the film and the extraction pin; the
hero screen's 12 px parallax that the spec allows was not built (see §8).

## 5. Film anchors

`FILM_ANCHORS` in `FilmBackdrop.tsx`. Seconds are fixed; the scroll offsets they sit at are
measured from the live rects on every resize, font settle and body resize.

| id | second | shot |
|----|--------|------|
| `hero` | 0 | table above the clouds, the drawn route, sunrise window |
| `why` | 0.7 | the first push towards the terrain, horizon still wide |
| `extraction` | 1.4 | the fall into the terrain: contour valley, teal rings, map sheet lifting |
| `portal` | 3.1 | the sheet settling over the valley, tiers reading as one surface |
| `how-it-works` | 4.4 | four cream cards in a fan around one lit marker (cut 4.2083) |
| `under-the-hood` | 5.85 | the route crossing a plateau edge, teal rim light on the boundary |
| `proof` | 7.0 | stacked plateaus held wide, cubes across the lower tiers |
| `waitlist` | 8.4 | pull back begins, the terrain reads as a map again |
| `questions` | 9.1 | the map rising into its folds |
| `footer` | 9.7 | the folded map on the desk beside the wordmark |

How the table was rebuilt: v2 had nine anchors, four of whose sections no longer exist
(`proof-gate`, `telemetry`, `research-results`, `availability`). The three sections that
stayed keep their seconds — hero 0, extraction 1.4, how-it-works 4.4, the last because the
four-card fan is a literal beat and belongs to the chapter about four cards. The seconds the
removed sections held are redistributed over the sections that replaced them, so the film
still spans the page end to end rather than finishing early. One reassignment is deliberate
and is recorded here rather than left as a stale comment: the tier-edge crossing at 5.85 used
to open `proof-gate` and now opens `under-the-hood`. The footer carries its own anchor, so
the terminal frame is reached by the last screen rather than by the synthetic anchor alone.

## 6. The loader

A fixed full-viewport overlay in `index.html`, above the app, `pointer-events: none`, so it
contributes no layout and traps no click. It exists because v3 removed the pre-JS text
shell: without it a visitor sees an empty document until React commits.

The mark breathes over 900 ms and is static under reduced motion. Two ways out, and the page
is never trapped by either: the default is a CSS-only fade after 4 s, whatever JavaScript
did; the normal path is `data-gone`, set once `document.fonts.ready` has resolved **and** the
app has committed. `data-gone` restates the whole `animation` shorthand with no delay, so it
replaces the fallback rather than racing it. A `noscript` rule removes the overlay outright
and keeps the plain message beside it.

The commit signal is `data-hero-mounted` on the document element, written from an effect in
`Hero.tsx`; the management shell writes `data-app-mounted` for the same purpose on its own
routes. The overlay removes itself on `animationend`.

The mark is its own 128 px encode, `guidefold-mark-loader.webp`, 7.7 kB. The site's 1024 px
mark is 177 kB, and preloading that at high priority cost the hero image roughly a second of
its LCP on emulated 4G; the header and footer brand marks now read the small one too.

## 7. Real output, and where it comes from

Every mono detail in the retrieval instrument is real output of the shipped CLI against
`examples/monorepo`, at commit 39f2396, on 2026-09-12:

```
$ cd examples/monorepo
$ echo '{"cwd":"…/platforms/atlas/identity/turnstile"}' \
    | python3 ../../skills/guidefold/scripts/guidefold hook
[guidefold] scope=atlas.identity.turnstile owner=turnstile-team \
    chain=atlas.identity.turnstile→atlas.identity→atlas→_root

$ python3 ../../skills/guidefold/scripts/guidefold find \
    --scope atlas.identity.turnstile --limit 4 "rotate the service token"
- urn:skill:meridian:atlas.identity.turnstile:postgres-auth      (score=17433 · node=atlas.identity.turnstile)
- urn:skill:meridian:atlas.identity:rbac-policies                (score=17063 · node=atlas.identity)
- urn:skill:meridian:atlas.identity.turnstile:turnstile-oncall-runbook (score=16872)
- urn:skill:meridian:_root:postgres-production                   (score=16484 · node=_root)

$ find . -iname SKILL.md | wc -l
27
```

So `scope: atlas.identity.turnstile` and `SEARCH · 27 candidates · 4 selected` are literal:
27 rules in the example repository, four selected by a real run at `--limit 4`.

The four cards the panel names are the spec's, and they are **not** the four that run
returned. They are the example repository's own rules at the four levels of its hierarchy —
`security-baseline` at `_root`, `atlas-api-conventions` at `atlas`, `rbac-policies` at
`atlas.identity`, `postgres-auth` at `atlas.identity.turnstile` — which is what the four
level labels say. Each card's line is the opening clause of that `SKILL.md`'s own
`description`. A ranked run for one particular prompt returns a different set; the panel
illustrates the hierarchy, which is the chapter's subject. This is the one place where the
page shows a set no single command produced, and it is recorded here rather than implied.

`USE · source hash and revision verified · LOAD` names the service's own delivery states as
`docs/API-CONTRACT.md` defines them; it is not quoted from a run.

## 8. Naming of sample content

Owner instruction, 2026-09-12: nobody outside the project knows "Meridian". Every caption,
label and tag that marks example content says `Sample data` or `sample data` — including the
extraction chapter's instrument labels and the proof band's `Sample repository`. The single
survivor is the protected instruction-reader label, which the preservation contract keeps
byte-identical, and `Landing.test.tsx` asserts that it is the only one left in the rendered
page. The word still appears inside the app screenshots themselves, which are captures of a
running UI and cannot be edited here (§10).

## 9. Measured

Production build, `pnpm build`, served by `vite preview` on 127.0.0.1:4432. Chromium 1.63.0
via Playwright, `deviceScaleFactor 1`, dark. 2026-09-12.

**Page height and overflow.** 7 511 px at 1440×900 — **8.35 viewports**, against the 8.5
budget. `documentElement.scrollWidth === clientWidth` at 1440, 1080, 720 and 390.

**Content edges**, every section's content box, at 1440: **152 .. 1288**, inside a container
padding box of 80 .. 1360. That is the nav card, the hero copy, every headline, every value
panel, every device frame, the waitlist copy, the waitlist submit button, the FAQ rows and
the footer — one pair of edges, no exceptions. The hero screen sits at 726 .. 1288, which is
columns 7–12 of the same grid. At 1080: 48 .. 1032. At 720: 24 .. 696. At 390: 20 .. 370.

**CLS 0.0000** at 1440 and at 390, cold production load on emulated 4G (CDP
`Network.emulateNetworkConditions`, latency 150 ms, 1.6 Mbps down; 4× CPU at 390),
`PerformanceObserver` `layout-shift`, buffered, `hadRecentInput` excluded. Before the
`Suspense` fallback was given a height this was **0.32** at 1440: v3's hero is shorter than
v2's, so the footer painted at y=612 and was pushed off screen when the deferred chunk
arrived. One viewport of reserved height keeps the footer below the fold until the screens
land, and the growth that replaces it happens off screen.

**LCP**, same emulation, cold cache, five runs per width, medians: **1440 2 132 ms**
[2132 2132 2132 2136 2136]; **390 2 276 ms** [2240 2264 2276 2280 2320]. The element is the
hero's `proposals.webp` at both widths. This is **above the spec's 2.0 s target** — see §10.
It began at 3 972 ms; the 177 kB loader mark, the 2880 px screenshot encodes and the absent
image preload were the three causes, in that order.

**Film cadence**, 60 px per frame scrub at 1440, presented frames counted with
`requestVideoFrameCallback` on the `<video>` itself: **25.2 presented frames per second**
over 2.03 s, median gap 33.4 ms, p95 66.6 ms. The investigation measured 21–28 fps with a
p95 gap of 67 ms before R1, and predicted the visible cadence would be "unchanged or
better" — it is at the top of that range. The 41–44 % main-thread saving is the
investigation's own measurement and was not re-measured here.

**Suites.** `pnpm test` 393 passed; the three failures in the same run are
`LibraryRoute.test.tsx` and come from an uncommitted `ui/src/data/apiSource.ts` change made
outside this task (verified: they pass with that file stashed). `pnpm typecheck` 0 errors.
`pnpm build` exit 0. `node qa/check-contracts.mjs` passed, 0 diagnostics.
`node qa/check-route-split.mjs` passed. Landing e2e **13 passed / 13**.

**Screenshots.** `ui/qa/landing-v3/<section>-{1440,390}.png`, every screen at both widths,
plus the two full-page captures the e2e suite writes.

## 10. Where implementation chose, and what is still open

1. **The hero screen's parallax was not built.** The spec allows it "at most 12 px" and the
   motion section says "no other scroll-linked motion". The second rule wins: a scroll
   registration for 12 px is exactly the cost R1 was written to remove. Recorded as a
   deviation.
2. **The trace rows enter on the page's own P1 stagger** (60 ms steps, capped at 240 ms),
   not the spec's 120 ms. A 120 ms ladder needs four new delay tokens for one block, and the
   spec's own motion section asks for the vocabulary unchanged.
3. **LCP is 2.13 s / 2.28 s, not under 2.0 s.** What is left is critical-path
   serialisation at 1.6 Mbps: HTML, then the preloaded image against three font files and
   the route chunk. The image is already 36 kB at 1280×800 and preloaded at high priority.
   Closing the last 130 ms needs a smaller above-the-fold payload than this page has —
   fewer preloaded faces, or an LCP element that is text.
4. **The page's marketing prose is about 636 words against the spec's 420.** Every string
   is byte-binding spec copy and the extraction chapter is owner-approved as committed, so
   nothing was cut. This is a conflict inside the spec, not a drift from it.
5. **The app screenshots still read "Meridian" and "meridian" inside the image.** They are
   captures of the running UI against that example repository. Re-capturing them against a
   differently named workspace is the fix; it is app work, not page work.
6. **`ui/qa/landing-v2/` was deleted.** Every capture in it was of a page that no longer
   exists. `ui/qa/landing-v2-gate.json` keeps its numbers and now cites captures that are
   gone; it stays as the dated record of the v2 wave.
