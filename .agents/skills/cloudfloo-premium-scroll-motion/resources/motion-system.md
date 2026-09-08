# Premium scroll motion system

Provenance: condensed from the Cloudfloo skill and research resource at commit `ce8517ed2e0fe375d45fe97319db859c6cebb405`.

## Three layers

1. Entry motion communicates hierarchy once.
2. Ambient motion adds life without carrying essential information.
3. Scroll-linked motion maps normalized progress to a timeline and works in reverse.

Never use one observer flag to control all three.

## Implementation contract

- Start with semantic visible content and stable DOM order.
- Add a root enhancement class only after successful JavaScript initialization.
- Map document progress to a clamped 0–1 value; smooth visual sampling, not application truth.
- Use requestAnimationFrame for high-frequency rendering and passive listeners where appropriate.
- Recompute bounds on resize, rotation, font/media load, and layout changes.
- Clean up RAF, events, observers, decoders, frames, requests, and timers on unmount/error.
- Prefer transform and opacity; constrain composited layers and cap device pixel ratio.
- Entry stagger is typically 50–70 ms and capped at 300 ms. Avoid staggered exits.

## Video scrub

Show a poster immediately. Check save-data and reduced motion before downloading video. Prefer a memory-bounded frame cache; otherwise seek only when the time delta is meaningful. Preserve center-cropped object-cover math. On decoder, CORS, abort, or network failure, retain poster and content. A scroll-driven video never becomes an ordinary autoplay loop.

## Contrast and visibility

A light local underlay is correct when copy crosses variable footage. Do not remove all material merely to expose the film, and do not hide the film with a full opaque block. Section rows remain readable independent of transient `.is-visible` or intersection state.

## Validation

Test fast wheel/touch input, reverse scroll, refresh mid-page, resize, rotation, tab navigation, delayed JavaScript, reduced motion, save-data, decoder failure, and exact terminal progress on all required viewports.
