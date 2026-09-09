# Guidefold landing - design system

The durable system for the writer. Authority order when two things disagree: **preservation contract → owner verdict → this file → `design-brief.json` → the craft skills**. The craft skills are reference, never authority.

Companion files in this directory: `design-brief.json` (the direction and its evidence), `copy.md` (final copy in reading order), `asset-plan.json` (image and video slots), `motion-prompt-packet.md` (the motion contract).

**Do not edit anything under `ui/src`** on the basis of this file alone; it is the specification, the writer is the executor.

---

## 1. Brand essence and audience

A surveyor's table, not a dashboard. Guidefold gives coding agents the rules of an organisation in the place where those rules apply. The visual world is the Industrial Surveyor variant: cream folded paper maps with printed contour lines, on a near-black graphite field marked with a dashed survey grid, one orange route line showing where a human decided something.

Audience: platform teams, tech leads, and the developers who work in their monorepo. Tone: precise, calm, engineering. They are evaluating whether this is real, not being sold to.

**Design mode: overhaul with content preserved.** Structure, motion and component set are replaced; every protected string survives verbatim.

---

## 2. Protected elements

Never edit, never restyle out of existence, never move behind an interaction that could fail:

- The waitlist form, its every string, its ids, its aria wiring, its 12s abort, its honeypot.
- The success state and all four error strings.
- The `?confirm=` / `?unsubscribe=` flows and all their copy.
- All four FAQ answers, including the pricing figures and the privacy answer in full.
- `Open source today.` and `Paid hosting is planned.`
- Every GitHub URL, the `/docs/` link, `mailto:hello@cloudfloo.io`, the `#privacy` anchor.
- The YouTube demo `e350wBr1W8c` as the **Play demo** action.
- Document title `Guidefold | Team instructions for coding agents` and the `Skip to content` link.
- The Meridian fixture excerpt in the instruction reader, and its "not a live run" label.

The full map with acceptance checks is `preservationMap` in `design-brief.json`.

---

## 3. Tokens

**Reuse `ui/src/tokens/tokens.css`. Do not create a second palette, a second type scale, or a second set of motion durations.**

### Colour roles

| Role | Token | Value |
|---|---|---|
| Page ground | `--graphite-950` | `#07090c` |
| Section band | `--graphite-900` | `#0c1014` |
| Raised surface (panel, card, form) | `--graphite-850` | `#11161b` |
| Inset (code block, input) | `--graphite-800` | `#171d23` |
| Primary text | `--stone-100` | `#eef1f3` |
| Secondary text | `--stone-300` | `#a3adb6` |
| Tertiary / disabled | `--steel` | `#5f6c77` |
| Hero headline only | `--landing-ivory` | `#efe3d0` |
| System state, active, focus | `--survey-teal` | `#3fb8b1` |
| Human decision, the route line | `--safety-orange` | `#ff7a3d` |
| Hairline | `--line` / `--line-strong` / `--line-hover` | rgba stone at 12 / 22 / 38% |

Teal and orange are not interchangeable accents. **Teal describes the system. Orange marks the one place a person decides.** Orange appears at most twice on the page: the HOW route rule, and the route line inside `plane-value`. Signal red never decorates.

**Contrast:** body ≥ 4.5:1, large text ≥ 3:1, hero headline ≥ 7:1 against the brightest frame of the loop inside the copy-safe field. Colour is never the only carrier of meaning.

**The asset palette is not the UI palette.** Generated images and video use `#0F1418 / #E6E8EA / #2BA6A0 / #FF6A28 / #677681` because that is what the existing demo assets were authored against. Those hexes belong in prompts only. Do not retune tokens toward them; they are shared with every product screen.

### Type

| Use | Family | Size | Leading |
|---|---|---|---|
| h1 | `--font-display` Instrument Sans | `--landing-title` `clamp(38px, 4.5vw, 64px)` | 1.08, tracking −.02em |
| h2 | `--font-display` | `--landing-heading` `clamp(28px, 3vw, 38px)` | 1.15 |
| Lede | `--font-body` Manrope | `--landing-lede` 18px (16px ≤720) | 1.6 |
| Body | `--font-body` | `--landing-body` 16px | 1.6 |
| Small / caption / fixture label | `--font-body` | `--font-size-small` 12px | 1.35 |
| Eyebrow | `--font-body`, uppercase | 12px, `--tracking-label` .14em | 1 |
| Paths, URNs, code | `--font-mono` JetBrains Mono | 12px | 1.6 |

Weights: `--weight-semibold` 600 on headings, `--weight-normal` 400 on body. Never bold display type at these sizes. Measure: `--landing-copy-width` 48ch for lede and body; never exceed 68ch. One `h1`; `h2` per section; `h3` only inside FAQ triggers. No font is added, no font is fetched.

### Spacing and grid

`--space-1..7` = 4 / 8 / 16 / 24 / 32 / 48 / 64px. Nothing off this scale. No `13px`, no `17px`.

- Between sections: `--landing-section-padding` 64px desktop, 48px ≤720px.
- Heading to its body: 24px. Inside a panel: 16px. Icon to label: 4px.
- Container `--landing-width` 1400px, gutter `--landing-gutter` `clamp(20px, 4vw, 64px)`.
- Breakpoints: 1080px and 720px only. No new breakpoint.
- Radius `--landing-radius` 8px on panels, `--radius-small` 4px on inputs and chips. One radius system.
- Borders 1px `--line-strong`. Shadows only `--shadow-card` on raised panels; hierarchy comes from spacing, type and lines, not from elevation.

### Motion tokens

Use these. Do not invent a curve.

```css
--ease-out: cubic-bezier(.23, 1, .32, 1);
--duration: 120ms;         /* hover, colour, press */
--duration-menu: 180ms;    /* tabs indicator, dialog backdrop */
--duration-drawer: 240ms;  /* dialog popup, collapsible, media cross-in */
--duration-reduced: 80ms;
--press-scale: .98;
```

**Retire these landing-only tokens** - all are above the 300ms bar or belong to removed components:

`--landing-reveal-duration` (650ms) · `--landing-card-duration` (500ms) · `--landing-stagger-1..5` (70-350ms) · `--landing-fold-duration` (900ms) · `--landing-fold-scale` · `--landing-fold-hover` · `--duration-shine` (900ms) · `--shine-gradient` · `--shine-width` · `--shine-start` · `--shine-travel` · `--landing-preview-period` (3600ms) · `--landing-card-enter-scale` · the whole `--pyramid-*` and `--material-pyramid-*` groups.

**Add these:**

```css
--p: .5;                 /* scroll progress default: the static composition */
--amp-topo: 16px;
--amp-grid: 40px;
--amp-plane: 20px;
--amp-hero-media: 12px;
--plane-opacity-why: .42;
--plane-opacity-how: .38;
--plane-opacity-value: .34;
@media (max-width: 720px) { --amp-topo: 8px; --amp-grid: 20px; --amp-plane: 12px; --amp-hero-media: 6px; }
```

**Three separated motion roles.** Do not blend them.

| Role | What it is | Budget |
|---|---|---|
| Entry | One bounded hero entrance on first paint | 200ms, 40ms stagger, 4 items, ≤120ms chain |
| Ambient | The hero loop, and nothing else | continuous, gated, pausable |
| Scroll | Background planes and one decorative SVG | ≤40px travel, linear in `--p`, reversible |
| UI | `data-state` transitions | 120-240ms, never >300ms |

---

## 4. Components

Build from what is installed. **No new dependency.**

| Component | Built from | Notes |
|---|---|---|
| `Button` | `ui/src/components/ui/button.tsx` (cva + Base UI) | **The only button on the page.** `variant="default"` for Join the waitlist, `outline` for Play demo and the nav action, `ghost` for Replay, `link` for text links. |
| `CinematicField` | new, plain CSS + one `<div>` stack | L0-L2, fixed, behind everything. Owns nothing but two background images. |
| `SectionPlane` | new | L3. One `<div>` with a background image and `--p`-driven transform. |
| `ScrollProgress` | new, one module | The single sampler described in §6. Exports a `useSectionProgress(ref)` that registers an element and returns nothing - it writes `--p` directly. |
| `HeroMedia` | new `<video>` + `<img>` | Poster-first, gated. Reuse the gating structure from `HeroAtmosphere.tsx`, then delete that file. |
| `IntroFigure` | new `<video>` | Plays once on 40% visibility, holds last frame, Replay button. **Fallback:** the source is HEVC + AAC, which many Chrome installs will not decode, so the transcoded `/assets/landing/intro.mp4` and `.webm` are required. If neither exists, or on any decoder error, render `intro-poster.webp` alone inside the same 16:9 bordered panel with its caption, and do not render the video element or the Replay button. The poster is the resolved final frame and is a complete composition on its own, so this fallback loses nothing but the motion. Same path under reduced motion and Save-Data. |
| `RouteRule` | new inline `<svg>` | `stroke-dashoffset` driven by `--p`. `aria-hidden`. |
| `DemoDialog` | existing `ProductFilm` in `LandingDemo.tsx`, reduced | Keep the Dialog, the nocookie iframe, the close/focus handling and the external link. Drop the fold-film cover choreography and the `data-motion` scale tokens. |
| `InstructionReader` | `LandingWorkbench.tsx`, reduced | Keep: `Tabs` + indicator, `SkillContent`, `CodeBlock`, the `Repository source` badge, the fixture label, the source link. **Remove: `BeamCard`, `BeamSearch`, the five-rule sidebar and its filter, the keyboard/pointer data attributes, the caption.** Result: one bordered panel, two tabs, one document. If it cannot be made that simple, cut it and leave HOW as prose. |
| `RoleCard` | new, static | `--graphite-850`, 1px `--line-strong`, 8px radius, 24px padding. Hover brightens the border only. |
| `Question` | existing `Collapsible` wrapper in `Landing.tsx` | Unchanged behaviour, including the hash and click reveal. All panels closed on load. |
| `WaitlistForm` | existing, unchanged | Restyle only. Swap `MorphButton` for `Button` and express loading with `disabled` + `Saving…` + `aria-busy`. |
| `LandingFooter` | existing, de-animated | Keep structure and links. Rename "Try the demo" to "Play demo". |

**Delete from the landing page:** `LandingPyramid.tsx`, `MaterialPyramid.tsx`, `pyramidThree.ts`, `LandingMotion.tsx` (all of `TextReveal`, `Reveal`, `FeatureDemos`, `ScopeDemo`, `ReviewDemo`, `usePreviewTimeline`), `HeroAtmosphere.tsx`, the `SchemaFlow` import and its `pipelineCards` / `pipelineLinks` / `pipelineDescriptions` data, and every landing import of `BeamCard`, `BeamSearch`, `use-beam-motion`, `use-typewriter` and `MorphButton`. Those components stay in the repository for the product UI; the landing page stops importing them.

---

## 5. Section specification

Final copy lives in `copy.md`. This is the layout and behaviour for each.

### Header - sticky, 80px, `--graphite-950` at 92% with a 1px bottom hairline

Wordmark left. Nav (`How it works`, `Docs`, `GitHub`) centre-right, hidden below 720px. `Join the waitlist` as `Button variant="outline"` on the right. No hamburger menu is added; below 720px the nav collapses to the wordmark plus the action, and every nav destination is reachable from the footer.

### 1. Hero - layout family A: full-bleed ambient media with a left copy-safe field

Media band 78vh desktop / 68vh mobile, fixed aspect box so the poster-to-video swap shifts nothing. Copy stack inside the left 55%, vertically centred: eyebrow, `h1`, lede, action row, trust line. Actions inline desktop, stacked full-width 44px on mobile.

Entrance: the four copy items fade in with a 2px rise, 200ms `--ease-out`, 40ms stagger. Any keyboard focus jumps the whole stack to its terminal state immediately.

### 2. WHY - layout family B: single-column editorial statement

Left-aligned, max 60ch, no cards, no icons, no diagram. `h2`, one answer sentence at lede size, two supporting paragraphs at body size. A 1px teal keyline draws across the top edge with `--p` (desktop only). **If this section ever grows a third supporting paragraph, cut it.**

### 3. HOW - layout family C: asymmetric split, `--landing-mechanism-columns` (.8fr / 1.2fr)

Left column: `h2`, answer sentence, three mechanism beats as labelled lines (label in `--stone-100` semibold, line in `--stone-300`), the `RouteRule` beneath them, a text link, and a native `<details>` disclosure holding `harness-integration.png` at `loading="lazy"`.

Right column: `IntroFigure` in a 16:9 bordered panel, and below it the `InstructionReader`.

Below 1080px this becomes one column, intro figure first. The section keeps `id="how-it-works"`.

### 4. VALUE - layout family D: 3-up role grid

`h2`, one answer sentence, then exactly three `RoleCard`s: platform teams, rule owners and tech leads, developers. Each is a role label (12px uppercase, `--survey-teal`), a promise line (18px `--stone-100`), and a detail line (16px `--stone-300`). Equal height, 24px gap. 3-up desktop, 2-up 721-1080 if the cards drop below a 32ch measure, stacked ≤720px. **Static. No entrance, no scroll movement.**

### 5. Availability - layout family E: inline two-statement band

`--graphite-900` band, 48px vertical padding, two statements side by side with a 1px vertical rule between them (horizontal rule when stacked). Bold lead phrase, regular remainder. Two text links beneath: `Try the open-source version`, `Read the docs`.

### 6. Waitlist - layout family F: split

`--graphite-850` panel, 8px radius, 48px padding (24px ≤720px). Left: `h2` and one context line. Right: the form, `--landing-form-columns` inline at ≥1081px, stacked below. Every string protected. The success state replaces the form in place and takes focus.

### 7. Before you join - layout family G: disclosure list

`h2`, then four `Collapsible` items, each a full-width row with a 1px bottom hairline, 20px vertical padding, a caret that rotates 90° over 200ms. **All closed on load.** Panels animate height over 200ms. This is how the pricing and privacy answers are preserved word for word without spending them in the reading order.

### Footer

Wordmark, tagline, four link groups, the oversized display wordmark (`--landing-footer-wordmark`, type only, no motion), the protected bottom line, the Cloudfloo credit. Global planes continue behind it.

---

## 6. The scroll engine

One module. One `rAF`. One passive `scroll` listener, one `resize` listener, one `IntersectionObserver`.

```
p = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1)
```

Written to each registered section as `--p` via `element.style.setProperty`. Never through React state. Sections register on intersect and unregister on exit, so off-screen work is zero and the frame is not scheduled when nothing is in view. Cleanup cancels the frame and disconnects the observer.

Consumed only in CSS:

```css
.plane { transform: translate3d(0, calc((var(--p) - .5) * var(--amp-plane)), 0); }
```

Linear in `--p`, never eased. Because every value is a pure function of geometry, reverse scrolling is exact and needs no separate code path.

**`--p` defaults to `.5`.** With JS disabled, under reduced motion, and before the first frame, the page is already a correct static composition. Budget: under 1ms per frame on a mid-range Android; `will-change: transform` only while a section is in view.

Full per-section amplitudes, opacity ramps and the route-rule mapping are in `motion-prompt-packet.md` §6.

---

## 7. Hero video contract

> **Read this before implementing the hero.** The owner asked twice for `guidefold-intro.mp4` to be the hero's opening shot. **This brief deviates from that**, on frame evidence: the clip's G mark is centred at x 35-65%, leaving only a 33%-wide dark field on the left, which cannot host the 55% copy-safe hero the owner also specified, and the clip is a resolved shot rather than a loop. The intro clip is placed in the HOW section instead. The reasoning and the exact one-line override, should the owner insist, are in `heroMediaDecision` in `design-brief.json`. **Do not ship a left-copy hero with the intro clip behind it** - the measurements say it will not fit.

1. **Poster first.** `/assets/landing/hero-poster.webp`, `fetchpriority="high"`, inside a fixed aspect box. It is the LCP element and is never removed.
2. **Gate before mounting the `<video>`:** hero in view, `prefers-reduced-motion` not `reduce`, `navigator.connection?.saveData` not true, poster decoded.
3. **Cross in** on `canplay`: `opacity 0 → 1`, 240ms `--ease-out`. Poster stays mounted underneath and is `aria-hidden`.
4. **Attributes:** `muted playsInline loop preload="none"`, `object-fit: cover`, `object-position: 62% 50%` desktop / `74% 50%` mobile.
5. **Pause** on `visibilitychange` hidden, on leaving the viewport, on user pause, and while the demo dialog is open.
6. **Fail closed:** on `error`, on CORS failure, or if `canplay` has not fired within 8s - unmount the video, keep the poster, show the user nothing. No message, no layout shift.
7. **Underlay for contrast:** `--landing-hero-scrim`, a left-to-right graphite gradient from `rgba(7,9,12,.94)` at x=0 to `rgba(7,9,12,.06)` at x=68%. Mobile: bottom-up, `rgba(7,9,12,.94)` at y=100% to `rgba(7,9,12,.10)` at y=44%. The scrim is what guarantees ≥7:1 on the headline; never rely on the video being dark.
8. **Pause control** rendered only while the loop is playing, top-right of the media band on mobile, bottom-right on desktop, with a real accessible label.

Reuse the gating structure from `ui/src/routes/HeroAtmosphere.tsx` - it already does the `matchMedia` `change` listener, the `visibilitychange` pause, the `IntersectionObserver` pause and the failure teardown correctly. Then delete that file.

The intro clip in HOW follows the same gating, with `loop` removed, `poster` set to its own last frame, and a single `Replay` button.

---

## 8. Responsive recomposition

Real recomposition, not a scaled desktop.

**≥1081px** - hero copy in the left 55%, focal right, horizontal scrim, actions inline. HOW split .8fr/1.2fr. VALUE 3-up. Waitlist split with an inline form row.

**721-1080px** - hero media 62vh, scrim becomes bottom-up, copy in the lower half, actions still inline. HOW one column, intro figure first. VALUE 3-up while cards hold 32ch, else 2-up. Waitlist one column.

**≤720px** - hero media 68vh, `object-position: 74% 50%`, copy in the bottom 46%, both actions full width at `--touch-height` 44px, pause control top-right. All scroll amplitudes halved. WHY keyline removed. Section planes drop to `.28` opacity (a small viewport magnifies texture). Instruction reader keeps its tabs, drops nothing else because the sidebar is already gone. Nav collapses to wordmark + action; every destination stays reachable from the footer.

---

## 9. Accessibility

- One `h1`, sequential headings, no level skipped.
- Semantic DOM order equals reading order equals tab order, independent of z-order. Tab order: skip link → nav → hero actions → section content → form → FAQ → footer.
- Focus rings: `--focus-width` 2px, `--focus-offset` 3px, `--survey-teal`, visible against every surface on the page including over the hero media.
- Every decorative image, plane, video and SVG is `aria-hidden`. The intro figure has a text caption that carries its meaning.
- Status and error regions keep their existing `role="status"` and `role="alert"`, and focus moves to the success state.
- Colour is never the only carrier of meaning.
- Reduced motion is a complete static page (§ `motion-prompt-packet.md` §8), not a faster one.
- Touch targets ≥ 44px on mobile.
- The page is usable and complete with JavaScript disabled.

---

## 10. Performance budget

| Metric | Budget |
|---|---|
| LCP | ≤ 2.0s on 4G. The LCP element is the hero poster, preloaded. The video is never the LCP element. |
| CLS | < 0.02. Every media box has a fixed aspect ratio or explicit height. |
| Hero poster | ≤ 180 KB WebP |
| `topo-plane.webp` | ≤ 220 KB |
| `survey-grid.webp` | ≤ 60 KB (tiled, so it must be small) |
| Each section plane | ≤ 200 KB WebP, `loading="lazy"` |
| Total background imagery | ≤ 700 KB |
| `hero-loop.mp4` | ≤ 3.5 MB, requested only after the poster decodes and only when motion is allowed |
| `intro.mp4` | ≤ 1.6 MB, `preload="none"`, requested at 40% visibility |
| Main thread | Exactly one `rAF` loop, under 1ms/frame. No WebGL, no interval timer, no per-frame React state. |
| JS | Must not increase. Removing the pyramid, `pyramidThree`, `SchemaFlow`, `BeamCard`, `BeamSearch`, `MorphButton` and `HeroAtmosphere` should reduce it materially - report the delta in build notes. |
| Lazy | `SkillContent` and `CodeBlock` stay lazy. The integration diagram is lazy behind a `<details>`. The YouTube iframe mounts only while the dialog is open. |

---

## 11. Prohibited

Removed by owner verdict or by this system. The full judged list with reasons is `prohibitedPatterns` in `design-brief.json`.

3D pyramid · schema flow canvas · four- and six-step walkthroughs · autoplaying feature demos · beam cards and beam search · shine edges and `--shine-*` · typewriter · per-word text reveal · reveal-on-scroll section wrappers · WebGL · fold-film hover choreography · `MorphButton` on this page · springs with bounce · gradient buttons · glassmorphism · blur backdrops on content · hover lifts with growing shadows · `scale(0)` entrances · `ease-in` on UI · `transition: all` · animating width/height/margin/padding/top/left (the FAQ collapsible height is the one exception) · scroll-jacking · scrubbed video · pinned or sticky sections · scroll progress indicators · marquees · counters · pulsing dots · carousels · logo walls · testimonials · fabricated metrics · **animating any content the visitor is reading** · treating the asset hexes as UI tokens · any new dependency, font fetch, GSAP, Lottie or icon library.

The distinction that governs this page: **scroll-linked drift on background planes, ≤40px, capped, reversible and information-free, is the approved cinematic mechanic. Taking over the scroll, scrubbing a timeline, pinning a section, or moving text is not.**

---

## 12. Build-notes checklist

Record a disposition for each in `reports/build-notes.md`:

1. Every acceptance item in `motion-prompt-packet.md` §9.
2. Every acceptance check in `preservationMap`.
3. The JS bundle delta after the deletions in §4.
4. Measured sampler cost per frame on a throttled profile.
5. Measured contrast for the hero headline against the brightest loop frame inside the copy-safe field.
6. Whether the `InstructionReader` was successfully reduced to two tabs and one document, or cut.
7. Which fallback path the hero took at build time: generated loop, generated keyframe only, or owned topo plane only.
