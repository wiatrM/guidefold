# Motion Prompt Packet - Guidefold landing

Human-readable companion to `motionPromptPacket` in `design-brief.json`. If the two disagree, the JSON wins.

---

## 1. The one motion idea

**One continuous cinematic field behind the page. It drifts with scroll and carries an ambient loop at the top. Everything in front of it is either static text or a shadcn state change.**

Backgrounds move. Text never does.

If you find yourself animating something that is not a background plane, the decorative route rule, or a `data-state` change on a control, stop: it is outside this packet.

---

## 2. Archetype ruling

**Primary archetype: Ambient loop with copy-safe field.** One archetype for the page, per the combination rule.

The scroll-driven depth planes over the rest of the page are a **secondary mechanic**, not a second archetype. They are one continuous field in the same material world. They never become a chaptered story, never pin a section, never carry required information, and never introduce a second visual thesis.

"Layered still-scene scroll story" was considered as the primary and **rejected**: it requires discrete spatial chapters with enter/hold/exit segments, and chaptered scroll narrative is exactly the over-explanation the owner is cutting.

**Reference basis**

| | |
|---|---|
| Primary | 006 Foldcraft - dark near-void, one bright focal object, large empty copy field, object-position control, locked wide camera |
| Secondary (one job: media readiness) | 002 AI builder - poster-first delivery, poster matches frame 0, entrance cascade confined to the hero |
| Rejected | 006's orange fish (literal subject, not ours) · 007's oversized absolute type (copy must read as a sentence) · 001's scroll-linked depth chapters as a *primary* (owner prohibits scroll choreography that takes over) · 004's marquee · 003's glass cards |

---

## 3. What "in the style of shadcn components" means, concretely

This is the section the writer should read twice. It is a checklist, not a mood.

**Driven by `data-state`, not by timers.** Every UI transition is a CSS transition on a state attribute that a Base UI primitive already sets (`data-open`, `data-closed`, `data-selected`, `aria-expanded`). No component owns an interval. No component animates on a schedule.

**The vocabulary, exhaustively:**

| Interaction | From → To | Duration | Easing |
|---|---|---|---|
| Dialog backdrop in | `opacity 0 → 1` | 180ms (`--duration-menu`) | `--ease-out` |
| Dialog popup in | `opacity 0 → 1`, `scale .95 → 1` | 200ms | `--ease-out` |
| Dialog out | same, reversed | 150ms (exit faster than enter) | `--ease-out` |
| Collapsible / FAQ open | `height 0 → var(--collapsible-panel-height)` + opacity | 200ms | `--ease-out` |
| Collapsible close | same, reversed | 150ms | `--ease-out` |
| Tabs indicator | `translateX` + `width` to the active tab | 180ms | `--ease-out` |
| Tab panel swap | `opacity` only | 120ms | `--ease-out` |
| Hover on button / link / card border | background, border and text colour only | 150ms | `ease` |
| Press | `scale(var(--press-scale))` = `.98` | 120ms | `--ease-out` |
| Focus ring | none | 0ms | - |
| Hero media cross-in | `opacity 0 → 1` on `canplay` | 240ms (`--duration-drawer`) | `--ease-out` |
| Hero entrance | `opacity 0 → 1`, `translateY 2px → 0` | 200ms, 40ms stagger, 4 items | `--ease-out` |

`--ease-out` is `cubic-bezier(.23, 1, .32, 1)`, already defined in `tokens.css`. Do not invent a curve. Do not use `cubic-bezier(0.4, 0, 0.2, 1)`.

**Rules that come with the vocabulary:**

- **Never `scale(0)`.** Entrances start at `.95` and up.
- **Never `ease-in` on UI.**
- **Never `transition: all`.**
- **Never animate `width`, `height`, `margin`, `padding`, `top` or `left`** - `height` on the FAQ collapsible is the single sanctioned exception, because Base UI measures it for you.
- Transform origin is at the trigger for popovers; **modals stay centred**.
- Exit the way you entered, faster.
- Transitions, not `@keyframes`, for anything a user can re-trigger. Keyframes restart from zero; transitions retarget from the current value.
- Hover motion is gated by `@media (hover: hover) and (pointer: fine)`.
- Nothing exceeds 300ms. The 240ms media cross-in is the longest thing on the page.
- Stagger is 30-80ms per item and the whole chain is under 200ms.

**Explicitly not shadcn, and therefore banned here:** springs with bounce, gradient buttons, glassmorphism, beam borders, shine sweeps, per-word text reveals, typewriters, pulsing dots, bobbing FABs, hover lifts with growing shadows, 3D transforms on content, `scale(0)` pops, entrance animations below the fold.

---

## 4. Composition and layers

**Layer order, back to front:**

| | Layer | Scope | Scroll amplitude |
|---|---|---|---|
| L0 | `--graphite-950` flat ground | global, fixed | 0 |
| L1 | `topo-plane.webp`, cover, `opacity .32`, `saturate(.85)` | global, fixed | 16px |
| L2 | `survey-grid.webp` tiled 512px, `opacity .10` | global, fixed | 40px |
| L3 | generated section plane (`plane-why` / `plane-how` / `plane-value`) | per section | 20px |
| L4 | `hero-poster.webp`, cover, `object-position 62% 50%` (74% on mobile) | hero only | 12px |
| L5 | `hero-loop` video, same box, same object-position | hero only | 12px |
| L6 | scrim underlay | hero: left→right gradient; other sections: flat `rgba(12,16,20,.72)` band | 0 |
| L7 | all content | - | **0, always** |

Nearer layers travel further. That is what makes it read as depth rather than as a slide.

**Copy-safe field**

- Desktop: left edge to x=55%, y=16% to y=84%. Nothing brighter than 22% luminance may appear there in any frame.
- Mobile: full width, y=50% to y=96%. Same ceiling.

**Focal region**

- Desktop: right 40%, ridge apex at x≈74%, y≈46%.
- Mobile: upper 46% after the `74% 50%` crop. The apex must survive the crop at 390×844.

**Typography relation:** in front of the media, on the scrim. The headline never overlaps the focal object, is never split around it, and is never behind it.

---

## 5. The scroll engine

**Progress formula**

```
p = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1)
```

`p` is 0 the instant a section's top edge reaches the bottom of the viewport, and 1 the instant its bottom edge leaves the top. It is a pure function of geometry, so **scrolling up is exact by construction** and needs no separate reverse specification.

**Implementation - one engine for the whole page**

- One passive `scroll` listener and one `resize` listener. Both only schedule; neither computes.
- One `requestAnimationFrame` that reads each registered section's cached rect and writes `--p` with `element.style.setProperty`.
- One `IntersectionObserver` registers and unregisters sections, so off-screen sections cost nothing and the frame is not scheduled when nothing is in view.
- **No React state is set per frame.** No component owns a listener.
- Cleanup cancels the frame and disconnects the observer.
- Budget: under 1ms per frame on a mid-range Android.

**Consumption - all movement lives in CSS**

```css
transform: translate3d(0, calc((var(--p) - .5) * var(--amp)), 0);
```

`--amp` is per-layer and never exceeds 40px. Opacity ramps are `clamp()` on `--p`. The mapping is **linear** in `--p`; do not ease it, because an eased scroll mapping feels like lag on a trackpad.

**Default value.** `--p` defaults to `.5` in CSS. That means with JavaScript disabled, under reduced motion, and before the first frame, every plane renders at its mid state and the page is a correct static composition. The static state is the default, not a special case.

---

## 6. Per-section choreography

### Hero

- L1 topo −16px · L2 grid −40px · L4/L5 media −12px · scrim 0 · copy 0.
- Hero media additionally ramps `opacity 1 → .55` across `p` 0.55 → 1.0, so the WHY headline below is never fighting a bright plate.
- No sticky. No pinning.
- Mobile: amplitudes halved. Media box fixed at 68vh so the ramp cannot cause reflow.

### WHY

- `plane-why` amp 20px; `opacity = clamp((p - .10) / .35, 0, 1) * .42`.
- One 1px teal keyline draws across the section's top edge: `scaleX .2 → 1`, `transform-origin: left`, mapped to `clamp((p - .05) / .25, 0, 1)`. Decoration only. At `p = .5` it is already `scaleX 1`, so the reduced-motion state shows it complete.
- Mobile: amp 12px, keyline removed (it reads as a glitch at narrow widths).

### HOW

- `plane-how` amp 20px; `opacity` ramp to `.38`.
- **Route rule.** An inline SVG polyline in `--safety-orange`, 2px, a shallow left-to-right survey route with two circular waypoints, sitting under the three mechanism beats. `stroke-dasharray: L`, `stroke-dashoffset: calc(L * (1 - q))` where `q = clamp((p - .18) / .44, 0, 1)`. Waypoint opacity steps at `q` = .38 and .78. This is the only scroll-driven element with a hint of meaning, and it is redundant with the text beside it, so losing it costs nothing.
  - **Static-state override, read this.** At the default `--p` of `.5`, that formula gives `q = .727`, a route drawn 73% of the way, which reads as broken rather than as a resting state. **This is the one element on the page whose static state is not the `--p = .5` evaluation.** Under `prefers-reduced-motion`, with JavaScript off, and wherever the sampler is disabled, set `q = 1` explicitly - `stroke-dashoffset: 0`, both waypoints at full opacity - as the element's default attribute value and as a rule inside the reduced-motion media query. Do not implement the formula literally and expect it to rest correctly.
- **Intro clip.** `guidefold-intro.mp4` (transcoded to `/assets/landing/intro.mp4` + `.webm`). **Not scrubbed.** It plays once at normal speed when the figure first reaches 40% visibility (`IntersectionObserver`, threshold `.4`, disconnect after firing), then holds its final frame. No `loop` attribute. `muted`, `playsInline`, `preload="none"`, `poster="/assets/landing/intro-poster.webp"` so the resolved mark is what the user sees before and after. A visible **Replay** text button re-runs it; that button is the only control.
- Mobile: plane amp 12px; the route rule keeps its full draw; the intro figure stacks above the beats at 16:9 full width.

### VALUE

- `plane-value` amp 20px; `opacity` ramp to `.34`.
- **The three role cards do not animate in.** They are static. Information-dense content the visitor is reading must not move for style. The only differentiation is a border that brightens from `--line` to `--line-hover` on hover, 150ms.
- Mobile: amp 12px, cards stack.

### Availability, Waitlist, Questions, Footer

- Global L1 and L2 keep drifting. Nothing local moves.
- This is where the visitor reads pricing, types an email, or opens a legal answer. Nothing behind them may compete.

---

## 7. Media contract

**Hero: still-first.**

1. `hero-poster.webp` (GPT Images 2 keyframe) paints first, `fetchpriority="high"`. It is the LCP element. It is never removed.
2. The `<video>` mounts only when: the hero is in view, motion is allowed, Save-Data is off, and the poster has decoded.
3. On `canplay`, video `opacity 0 → 1` over 240ms. The poster stays mounted underneath.
4. Pause on `visibilitychange` (hidden), on leaving the viewport (`IntersectionObserver`, threshold 0), on user pause, and while the demo dialog is open.
5. On `error`, on CORS failure, or if `canplay` has not fired within 8s: unmount the video, keep the poster, show nothing to the user.
6. `muted playsInline loop preload="none"`, fixed aspect-ratio box, `object-fit: cover`, `object-position: 62% 50%` desktop / `74% 50%` mobile.

**The gating pattern already exists in this repository.** `ui/src/routes/HeroAtmosphere.tsx` implements exactly this shape for a WebGL canvas: `matchMedia('(prefers-reduced-motion: reduce)')` with a `change` listener, `visibilitychange` pause, `IntersectionObserver` pause, context-loss teardown, DPR clamp. **Delete the component; reuse its structure for the `<video>`.** Do not reinvent it worse.

**HOW figure:** `intro.mp4`, plays once, holds last frame, poster is that frame. Audio stripped at transcode - the HEVC source carries an AAC track that must not ship.

**Delivery**

| | Hero loop | Intro clip |
|---|---|---|
| Ratio / size | 16:9, 1920×1080 | 16:9, 1920×1080 |
| Duration | 10s, looping | 5.042s, resolved |
| fps | 24 | 24 |
| Codec | H.264 MP4 + VP9 WebM | H.264 MP4 + VP9 WebM (source is HEVC; transcode is required, not optional) |
| Audio | none | none (stripped) |
| Budget | ≤ 3.5 MB | ≤ 1.6 MB |

---

## 8. Reduced motion, Save-Data, failure

**`prefers-reduced-motion: reduce`** - a complete static page, not a slower one.

- No video element created, no video byte requested, for either clip. Posters are the images.
- The scroll sampler never starts. `--p` is `.5` everywhere. Planes sit at mid position and mid opacity. The route rule is fully drawn on first paint.
- Entrance transforms and opacities are **removed, not shortened**. The page is fully composed on first paint.
- Dialog, collapsible and tabs transitions reduce to an 80ms opacity change (`--duration-reduced`), no scale, no height animation.
- Hover and press transforms removed.
- No pause control is rendered, because nothing is playing.

**Save-Data** - identical media behaviour (posters only, zero video bytes). The scroll sampler *does* still run, because it costs no bandwidth. If measured above 1ms/frame on a mid-range Android, disable it here too and set `--p` to `.5`.

**No JavaScript** - every section renders from the base DOM. FAQ answers, mechanism beats, availability statements and footer links are all present. `--p` sits at its `.5` default. The demo trigger degrades to a plain link to the YouTube URL.

**Media failure** - poster stays, no error text, no layout shift, CLS contribution 0.

---

## 9. Acceptance checks

Test at **1440×900, 768×1024, 390×844 and 360×800**; first load; refresh mid-scroll; fast scroll; reverse scroll; resize; dialog interruption; reduced motion; Save-Data; blocked media.

**Composition and contrast**

1. Hero headline and lede sit entirely inside the copy-safe field at all four viewports and measure ≥ 7:1 against the brightest frame of the loop sampled inside that field.
2. The ridge apex is visible at all four viewports; no crop removes the focal object.
3. Poster composition is pixel-comparable to video frame 0. A poster that changes the composition is a rejection.
4. At every scroll position, in every section, body text is ≥ 4.5:1 against whatever the planes render behind it. Sample `p` = 0, .25, .5, .75, 1 per section.

**Scroll**

5. Scrolling to the footer and back to the top returns every plane to its exact initial transform and opacity. Any drift means a value is not a pure function of `--p`, which is a defect.
6. No layer's `translateY` exceeds 40px of total travel at any breakpoint.
7. No scroll-driven property other than `transform` and `opacity` exists on the page.
8. Exactly one `scroll` listener and one `resize` listener exist (`getEventListeners(window)`).
9. Fast scroll top to bottom: no layout or paint entries attributable to the sampler, long-task count zero.
10. No content layer moves with scroll.

**Media**

11. Loop seam: play through the wrap point ten times, observe no jump in subject position, no luminance step, no direction reversal. A first/last pixel diff alone is not sufficient evidence.
12. Intro clip plays once, does not loop, final frame equals its poster. Scrolling past and back does not replay it; the Replay button does.
13. `ffprobe` shows no audio stream in either delivered clip.
14. With `prefers-reduced-motion: reduce` set before load, DevTools shows **zero** requests for `hero-loop.*` or `intro.*`.
15. Same with Save-Data.
16. Blocking the media URLs leaves a correct page: posters visible, no layout shift, no error text.
17. Switching tabs pauses the loop; returning resumes it. Scrolling the hero out of view pauses it.
18. Opening the demo dialog pauses the loop; closing it unmounts the YouTube iframe.

**Motion discipline**

19. Nothing on the page exceeds 300ms except the deliberate 240ms media cross-in.
20. No stagger chain exceeds 120ms total.
21. Reduced motion: sampler never installed, `--p` is `.5` on every section, and the route rule is fully drawn on first paint **via its explicit `q = 1` override**, not via the `--p` formula (which would leave it 73% drawn). Verify the override is present, not merely the visual result at one viewport.

**Semantics**

22. Tab order is nav → skip target → hero actions → section content → form → FAQ → footer, matching DOM order regardless of z-order.
23. Every FAQ answer is present in the DOM on load with its panel closed; `#privacy` and `#question-2` deep links expand.
