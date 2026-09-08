# Motion grammar

## State before effects

Name the smallest state set that explains the page:

- `entrance`: one bounded load sequence;
- `progress`: normalized scroll or chapter progress;
- `pointerX` and `pointerY`: clamped decorative response;
- `activeIndex`: finite carousel or slider selection;
- `menuOpen`: explicit navigation state;
- `mediaReady` and `mediaFailed`: delivery state.

Every animated value must derive from one of these states. Do not scatter unrelated timers through components.

## Temporal roles

- Entrance introduces hierarchy once, normally within 0.5–1.4 seconds.
- Ambient motion loops without carrying required information.
- Pointer response stays subtle, clamped, and decorative.
- Scroll motion has enter, hold, and exit beats that work in reverse.
- UI transitions confirm an action and cannot delay navigation or form use.

Specify duration, easing, delay, trigger, owner, initial state, final state, and interruption behavior. “Fade smoothly” is not a motion specification.

## Implementation rules

Use Motion for component and layout transitions. Use CSS keyframes for a simple perpetual marquee. Use one requestAnimationFrame loop for high-frequency pointer or scroll sampling, with cleanup and no React state per frame. Drive layered scenes through CSS custom properties or Motion values. Content exists in the base DOM and is visible when enhancement fails.

## Media rules

Pause ambient video when hidden. Use muted `playsInline`, a same-composition poster, stable dimensions, object-cover focal coordinates, and explicit decoder/CORS failure behavior. A first/last normalized pixel difference is only a seam warning; inspect motion continuity before calling a clip loop-safe.

## Fallbacks

Reduced motion removes pointer drift, parallax, scrub inertia, marquee travel, and nonessential entrances. Save-Data and failed media use the poster or layered still. Mobile recomposes the layout and focal crop instead of shrinking desktop coordinates. Keyboard and screen-reader order follow the semantic document, not the visual stack.

## Acceptance

Test 360×800, 390×844, 768×1024, and 1440×900; first load; refresh mid-scroll; fast and reverse scroll; resize; menu interruption; reduced motion; Save-Data; offline/media failure; and the exact terminal state.
