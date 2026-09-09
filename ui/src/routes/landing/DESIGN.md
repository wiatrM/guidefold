# Guidefold landing - implemented system

The durable record for `src/routes/landing/`. The approved specification is
`ui/design/landing/DESIGN.md`, `copy.md`, `motion-prompt-packet.md` and
`design-brief.json`; this file records what was actually built and the places where
implementation had to choose. Authority order is unchanged: preservation contract →
owner verdict → `design/landing/DESIGN.md` → `design-brief.json` → craft skills.

## Reading order

`hero → why → how-it-works → value → availability → waitlist → questions → footer`.
One `h1`, one `h2` per section, `h3` only inside the FAQ triggers. Semantic DOM order
equals visual order equals tab order at every breakpoint; nothing is reordered with CSS
`order`.

## Files

| File | Job |
|---|---|
| `index.tsx` | Page composition, the `?confirm=` / `?unsubscribe=` branch, the FAQ `Collapsible` wrapper |
| `landing.module.css` | The whole page's styling. Values are tokens; no literal dimension, colour or breakpoint lives here |
| `scroll.ts` | The single scroll sampler: one rAF, one passive `scroll`, one `resize`, one `IntersectionObserver` |
| `FilmBackdrop.tsx` | Poster-first page-wide film, playhead tied to scroll progress |
| `IntroFigure.tsx` | The HOW mechanism clip, played once, held on its last frame |
| `InstructionReader.tsx` | One bordered panel, two tabs, one real `SKILL.md` |
| `DemoDialog.tsx` | The recorded demo; the nocookie iframe exists only while the dialog is open |
| `RouteRule.tsx` | The decorative scroll-drawn survey route |
| `WaitlistForm.tsx` | The protected form, the success state, the four error strings, the email-action flows |
| `Footer.tsx` | Wordmark, four link groups, the protected bottom line |
| `instruction.ts` | The Meridian fixture excerpt and the protected URLs |

## Tokens

Everything lives in `src/tokens/tokens.css`; `qa/check-contracts.mjs` rejects a custom
property declared anywhere else, a literal dimension or colour in a module, and a literal
breakpoint inside a module's `@media`. **Responsive recomposition is therefore a token
swap, not a media query in the module.** The only media queries in
`landing.module.css` are `(hover: hover) and (pointer: fine)` and
`(prefers-reduced-motion: reduce)`; every width-dependent value is a token redefined in
the `1080px` and `720px` blocks of `tokens.css`.

Motion tokens are the existing ones: `--ease-out` `cubic-bezier(.23,1,.32,1)`,
`--duration` 120ms, `--duration-menu` 180ms, `--duration-drawer` 240ms,
`--duration-reduced` 80ms, `--press-scale` .98. Nothing on the page exceeds 240ms.

## The scroll engine

```
p = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1)
```

`scroll.ts` writes `--p` onto the page root and onto the hero, WHY, HOW and VALUE
sections with `element.style.setProperty`, never through React state. Sections register
on intersect and unregister on exit; a section that leaves the viewport keeps its own
clamped resting value rather than inheriting the page's. Consumption is CSS only:

```css
transform: translate3d(var(--zero), calc((var(--p) - .5) * var(--amp-plane)), var(--zero));
```

Amplitudes: topo 16px, survey grid 40px, section plane 20px, hero media 12px, all
halved at 720px. Linear in `--p`, so reverse scrolling is exact by construction.

`--p` defaults to `.5`. With JavaScript off, under reduced motion and under Save-Data the
sampler is never installed and the page renders its static composition.

**The one exception is the route rule.** Its `--p = .5` evaluation is a route drawn 73% of
the way, which reads as broken. The base rules therefore paint it complete
(`stroke-dashoffset: var(--zero)`, both waypoints at full opacity) and only an element the
sampler is actually driving — marked `data-p-ready` by `scroll.ts` — gets the `--p`
mapping. No-JS, reduced motion and a disabled sampler all land on the finished state.

## Media contract

- Hero: `hero-poster.webp` paints first with `fetchpriority="high"` and is never removed.
  The `<video>` is **mounted** only when the hero is in view, motion is allowed,
  Save-Data is off and the poster has decoded - conditional mounting, not `preload="none"`,
  is what guarantees zero requests. It crosses in on `canplay` over 240ms, pauses on
  `visibilitychange`, on leaving the viewport, on user pause and while the demo dialog is
  open, and unmounts on `error` or if `canplay` has not fired within 8s.
- HOW figure: `intro.mp4` / `.webm`, played once at 40% visibility, held on its final
  frame, which is also its poster. No `loop`. One `Replay` control.
- Reduced motion and Save-Data render the posters and create no video element at all.

## Motion vocabulary

Dialog backdrop 180ms opacity; dialog popup 240ms opacity with `scale .95 → 1`;
collapsible height + opacity 180ms; tabs indicator `translateX` + `width` 180ms; hover on
colour only, gated by `(hover: hover) and (pointer: fine)`; press `scale(.98)`. One hero
entrance: opacity plus a 2px rise, 200ms, 40ms stagger, four items, cancelled by
`:focus-within`. No section reveals, no scroll-triggered content motion, no springs.

## What must not come back

The 3D pyramid, the schema-flow canvas, autoplaying feature demos, beam cards and beam
search, shine sweeps, the typewriter, per-word text reveals, `MorphButton`, reveal-on-scroll
section wrappers, the WebGL hero atmosphere, fold-film hover choreography, and any new
dependency, font fetch or icon library. Those components remain in the repository for the
management UI; the landing page does not import them.
