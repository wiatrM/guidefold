# Demo research — how pi.dev and mintlify.com show the product

Status: Research input. Not a decision record and not an implementation claim.
Captured 2026-09-12 at 1440×900, headless Chromium via Playwright, DPR 1.
Evidence screenshots: `/tmp/claude-1000/-home-mike-projects-guidefold/f65164e3-ab02-4d5c-904a-4a7136f96241/scratchpad/shots/`
Source files pulled for reading: same scratchpad (`home-inline.js`, `pi-style.css`).

Why this exists: the owner's verdict on the current landing page — *"when someone lands on the page
they still do not know what it is for; it must be simple, not scientific."* Both reference sites
solve exactly that problem, and they solve it with mechanics we can copy without new dependencies.

A caution on method: the browser session was shared with another process and twice navigated itself
to the local Guidefold dev server mid-capture. Every observation below was re-taken with
`location.href` asserted in the same call. One accidental capture of our own page
(`mint-s1750.png`, despite its filename) is used deliberately in §A.3 as the "before" evidence.

---

# A. Per site

## A.1 pi.dev

### A.1.1 Stack

| Layer | What it is | Evidence |
|---|---|---|
| Framework | **None.** Static HTML, no hydration root. `__NEXT_DATA__` false, `__nuxt` false, no `#root`/`#__next`/`astro-island`, no `meta[generator]` | `browser_evaluate` on `https://pi.dev/` |
| JS | Six hand-written vanilla modules: `pi-dev.js` (551 B), `home-inline.js` (76.2 KB), `logo-context-menu.js`, `nav-sheet.js`, `theme-toggle.js`, `copy-buttons.js` | `performance.getEntriesByType('resource')`; `wc -c` on fetched files |
| Animation library | **None.** No framer-motion, no motion, no GSAP, no ScrollTrigger, no Lenis, no Lottie, no Rive, no three/spline | full resource list contains no library chunk |
| Demo runtime | **asciinema-player** (`/asciinema/asciinema-player.min.js` + its CSS) | resource list; `window.AsciinemaPlayer.create(...)` called 7× in `home-inline.js` |
| Media | Zero video files, zero image sequences, zero raster hero art. Ten `.cast` terminal recordings: `default, hello, mobile-cal, extension, models, tree, arrr, steering, print, install` | `document.querySelectorAll('[data-src]')` |
| Canvas | One: `<canvas id="heroLogo" width="140" height="421">` — the logo assembly | DOM inspection |
| SVG | Logo marks, the asciinema cell-background layer (`svg.ap-term-bg`, `viewBox="0 0 80 24"`), small icons | DOM inspection |
| Fonts | **PlantinNow Variable** (Upright + Italic) for display serif, **Departure Mono** for labels, **Commit Mono** 400/700 for the terminal | `/fonts/*.woff2`, `/fonts/CommitMono-*.otf`; `--term-font-family: Commit Mono` on the player |
| Motion tokens | **None.** Zero `--*` custom properties defined on `:root` in the whole 185 KB stylesheet | iterated `document.styleSheets` for `:root` rules → 0 properties |
| CSS keyframes | Exactly **five** in 185 KB: `terminal-cursor-blink`, `hero-rise-fade`, `hero-opacity-fade`, `hero-line-focus-in`, `packages-preview-media-enter` | scanned `pi-style.css` for `@keyframes` |
| Reduced motion | 8 `@media (prefers-reduced-motion: reduce)` blocks | `grep -c` on `pi-style.css` |

The headline number: **five keyframes and no animation library for the whole site.** Everything
that appears to move is either a recorded terminal being replayed, a canvas drawn by hand, or a CSS
transition on a state attribute.

### A.1.2 Inventory of animated / interactive components

1. **Hero logo assembly (canvas, Tetris drop).** Four tetromino pieces named `BASE`, `LEFT`, `TOP`,
   `RIGHT` fall into a 140×421 canvas and lock into the Pi wordmark. From `home-inline.js`:
   `LOGO_SEQUENCE = [{piece: BASE, duration: 91, holdAfter: 11}, {LEFT, 91, 11}, {TOP, 91, 11},
   {RIGHT, 91, 49}]`, then `LOGO_TIMING = {initialHold: 28, clearFlashCount: 5, clearFlashStep: 35,
   postClearHold: 49, postDropHold: 154}`. Total ≈ 850 ms. Settles to
   `FINAL_LOGO = ["3:2","3:3","3:4","4:2","4:4","5:2","5:3","5:5","6:2","6:5"]`.
   *Trigger:* autoplay at load; replayable by clicking (`button "Play the Pi logo animation"` is the
   only accessible-tree node in the hero at t=0).
   *Communicates:* the brand, and — because pieces snap into a grid — "this thing is assembled from
   parts you place."
2. **Staged intro state machine.** `document.documentElement[data-intro]` walks
   `staged → headline → collapsing → full`, with `HOME_INTRO_TIMING = {headingLeadIn: 175,
   heroLiftSettle: 826, restRevealLag: 350, terminalReveal: 0, navReveal: 0, introMaxWait: 10000}`.
   Observed as: at t=0 only the logo + headline exist (nav is `aria-hidden` + `inert`); by t=1 s the
   nav, subline, install box and terminal are all present. CSS drives the whole thing off the
   attribute; the JS only sets it.
   *Communicates:* a reading order. You read the sentence before anything else can distract you.
3. **`hero-rise-fade` entrance**, 1540 ms, `linear` at the animation level (the shaping lives in the
   keyframe stops), one iteration, applied to three elements: the subline `<p class="hero-orient">`,
   `div.install-box`, and `div.landing-stage--hero`. Measured via `getAnimations()`.
4. **Install command switcher.** Base-UI-less tab strip: `CURL / POWERSHELL / NPM / PNPM / BUN` with
   a sliding `.install-tabs-indicator`, plus a `[ COPY ]` button. Reduced motion sets
   `.install-tabs-indicator { transition: none }`.
   *Communicates:* "you can have this in one line, in your package manager."
5. **The sticky terminal stage — the main event.** A `figure.landing-demo-figure` (720 px wide, with
   four hairline corner brackets `figure-corner--tl/tr/bl/br`) pinned on the left while ~4 800 px of
   prose scrolls past on the right. Body height 7 317 px; the stage spans y≈706 → y≈5 495.
   Above it sits a caption bar `PI - <CHAPTER TITLE> ●`; the `●` is
   `terminal-cursor-blink`, 1 250 ms, linear, infinite.
   Scroll position swaps which `.cast` is mounted and plays. Measured titles by scroll depth:

   | scrollY | caption | what the terminal does |
   |---|---|---|
   | 0–~700 | `Pi - Make it yours` | idle, `$ scroll to continue` cue |
   | 900 | `Pi - manipulate the website` | a diff appears (`- 73 --recording-font-family: var(--serif);` / `+ 73 ... "Comic Sans MS"...`), then `Thinking...`, then `Done. The website font has been changed to Comic Sans.` |
   | 1800 | `Pi - Switch models mid-session` | user types `/model` |
   | 2700 | `Pi - Load project skills and instructions` | `[Context] AGENTS.md` appears, user types `hello pi`, agent replies `Ahoy! Me Pi. What ye need, friend?` |
   | 3600 | `Pi - Steer a running agent` | user types `please change the block c…` mid-run |
   | 4500–5400 | `Pi - Install a third-party extension` | `$ pi install npm` → `$ pi install npm:@termdraw/pi` typed character by character |

   The terminal content is **live DOM text** — `<pre class="ap-term-text">` with real text nodes,
   readable by `innerText`, selectable, with a separate `<svg class="ap-term-bg">` painting cell
   backgrounds. It is not a video and not an image.
   *Communicates:* six different capabilities, each as a thing that visibly happens.
6. **Per-chapter status line.** The bottom two rows of the terminal are the agent's real status bar:
   `~/Development/pi.dev (main)` / `↑6.4k ↓122 R9.3k $0.000 (sub) 5.5%/128k (auto)` /
   `grok-code-fast-1 • thinking off`. Different per cast (`~/Development/context-engineering`,
   `(openai-codex) gpt-5.4`).
   *Communicates:* token cost and model, without a single sentence of marketing.
7. **Inline chapter demos** further down the page, each its own player:
   `AsciinemaPlayer.create(config.src, mount, {autoPlay: !prefersReducedMotion,
   controls: prefersReducedMotion, loop: demo.repeat})`.
8. **Scroll-fade mask** on the callout sections (`.home-callout--viewport-mask` uses a CSS
   `mask-image`, disabled under reduced motion) — content dissolves at the band edges rather than
   being clipped.
9. **Sticky nav reveal.** *Mechanic:* `aria-hidden` + `inert` removed and the bar slid into place at
   the `full` intro state, with a hover-intent memory persisted to storage
   (`pi:sticky-nav-hovered-at`) and a `HOME_INTRO_NAV_REVEAL_MARGIN` of 20 px.
   *Trigger:* intro state reaching `full`, or a returning visitor's stored hover intent, which skips
   the wait. *Duration:* `navReveal: 0` — it has no delay of its own; it simply appears when the
   headline's turn is over. *Communicates:* "you have finished the sentence; now you may navigate."
10. **Button/link hover** via `::before`/`::after` transforms; all `transform: none` under reduced
    motion. `.action-button` is bracket-styled (`[ READ THE DOCUMENTATION ]`) — the terminal
    aesthetic carried into the chrome.
11. **Theme toggle.** *Mechanic:* the knob slides by `--theme-toggle-active-shift` while
    `.theme-toggle-icon` and `.theme-toggle-label` transition. *Trigger:* click. *Duration:* not
    declared in the base rule; under reduced motion both transitions are pinned to `0.01ms` and the
    shift to `0px`. *Communicates:* that the site has two grounds and the choice is the reader's.
12. **Two hidden toys** — a "crooked mode" callout and a hidden DOOM panel, both carrying the
    `hidden` attribute by default. *Mechanic:* the `hidden` attribute is removed and a callout panel
    is shown; the crooked mode also drives a `--recording-crookedness` angle used by the recording
    styles. *Trigger:* **not instrumented** — the reveal path was not traced. *Duration:* not
    instrumented. *Communicates:* that the page is a toy the authors play with, which is itself the
    "make it yours" argument.

Reduced-motion strategy (read from source, not emulated): 8 media blocks. Transitions collapse to
`0.01ms`; the `data-intro` staged states are forced to the final visible state via
`:root:is([data-intro="staged"],[data-intro="headline"],[data-intro="collapsing"])
.home-intro-hidden-until-full { visibility: visible; opacity: 1 }`; masks are removed; and the
demos stop autoplaying and grow a play control instead.

### A.1.3 Hero-demo anatomy

- **What it is made of:** real DOM text. A `<pre>` terminal buffer plus an SVG cell-background layer,
  driven by a recorded `.cast` file. Not video, not an image sequence, not Lottie/Rive, not WebGL.
- **How it loops:** per-chapter. `loop: demo.repeat` — some casts repeat, some play once and then
  swap their caption for an "ended" line via `getDemoEndedCaptionTemplate`.
- **What triggers it:** autoplay on load for the first cast; **scroll** thereafter. Scroll ranges are
  breakpoint-aware: `HOME_INTRO_SCROLL_RANGES = {mobile: 220, tablet: 260, desktop: 300}`.
- **Interactive?** Partly. The space-bar shortcut is deliberately disabled
  (`disableDemoSpaceShortcut()`) so the demo never steals page scrolling. Controls are hidden
  (`controls: false`) unless reduced motion is on.
- **Duration and easing:** the casts are real recordings, so timing is whatever the human typed.
  The *frame* around them uses `hero-rise-fade` at 1540 ms once.
- **Degradation:** no autoplay, visible controls, no transitions.

The design lesson is not "use asciinema". It is: **the hero shows one terminal doing one thing, and
a caption bar names that thing in five plain words.**

### A.1.4 Message test

- **After 3 seconds** — you have read exactly one sentence, because for the first second nothing else
  exists: *"There are many agent harnesses but this one is yours"*, set in a large italic serif with
  the last word in blue. You know it is a tool for coding agents, and that the pitch is ownership.
- **After 10 seconds** — the subline has arrived: *"Pi is a minimal agent harness. Adapt Pi to your
  workflows, not the other way around."* Below it, `$ curl -fsSL https://pi.dev/install.sh | sh`
  with a tab strip and a copy button. You now know the category, the promise, and the install cost.
- **After one scroll** — a terminal edits a CSS file in front of you, says `Thinking...`, then
  `Done. The website font has been changed to Comic Sans.` Beside it the prose says
  *"Change the harness, not your workflow."* You have now seen the product work.

The devices: (1) headline is a **stance**, not a description; (2) subline is a **flat category
sentence** — "Pi is a minimal agent harness" — five words that would survive being read aloud to a
stranger; (3) the first demo beat is a change you can *see happen*, deliberately trivial (a font
change) so nothing has to be explained.

---

## A.2 mintlify.com

### A.2.1 Stack

| Layer | What it is | Evidence |
|---|---|---|
| Framework | **Next.js App Router**, Turbopack build. `__next_f` present, `__NEXT_DATA__` absent (RSC, not pages router). RSC prefetches visible as `/pricing?_rsc=1134b` etc. | `browser_evaluate`; resource list |
| CSS | Tailwind utility classes throughout (`grid-layout`, `text-xs/4`, `motion-reduce:*`, arbitrary values like `ease-[var(--ease-out-soft)]`) | hero `outerHTML` |
| Animation library | **Rive** — `https://unpkg.com/@rive-app/webgl2@2.38.1/rive.wasm`. No framer-motion/motion global, no GSAP, no Lenis, no Lottie, no three/spline | resource list; `window.Motion` / `window.FramerMotion` both false |
| Rive assets | Six `.riv` files, one per feature card: `agent-native-platform.riv` 14 KB, `self-updating-knowledge.riv` 14 KB, `control-who-has-access.riv` 15 KB, `connect-with-your-systems.riv` 12 KB, `collaborate-with-your-team-and-agents.riv` 31 KB, `build-on-top-of-your-existing-setup.riv` 14 KB — **100 KB total for six animated scenes** | resource list |
| Canvas | 15 canvases. Hero field 1425×992; six bento cards (695×410, 4×339×410, 1052×410); four customer-story cards 536×472; three section bands 1440×504/546/617; one stats band 1086×304. Despite the `webgl2` package name, the bento canvases expose a **2D context** here (`getContext('webgl2')` null, `getContext('2d')` non-null) | DOM + context probe |
| Hero product mockup | **Static SVG**: `<img src="/images/docs-preview/preview-light.svg">` at 1055×641, 93 KB, with a `preview-dark.svg` twin also 93 KB. No video, no DOM mockup, no canvas | DOM inspection |
| Video | **None on the page.** Raster only for customer photos (`anthropic-sf.webp` 90 KB, `coinbase-ipo.webp` 175 KB, `hubspot-conference.webp` 94 KB, `att-photo.webp` 123 KB) | resource list |
| Fonts | **Inter Variable** (TTF, 453 KB), **ABC Arizona Flare** Regular (OTF, 81 KB — serif display), **Paper Mono** (woff2, 41 KB — used for numbers) | `/_next/static/media/*`; computed `font-family` |
| Motion tokens | `--ease-out-soft: cubic-bezier(.22,1,.36,1)`, `--ease-out-expo: cubic-bezier(.16,1,.3,1)`, `--ease-in-out-smooth: cubic-bezier(.4,0,.2,1)`, `--ease-out: cubic-bezier(0,0,.2,1)`, `--ease-in-out: cubic-bezier(.4,0,.2,1)`, `--text-swap-dur: .15s`, `--text-swap-ease: ease-in-out` | `:root` rule scan + computed style |
| Keyframes in use | `stats-scroll` (40 000 ms, linear, infinite), `carousel-card-dim`, `signal-ping` (1 050 ms, linear, infinite), `signal-flicker` (1 050 ms, linear, infinite) | `getAnimations()` |
| Scroll-reveal | WAAPI `Animation` (not `CSSAnimation`), **450 ms, `cubic-bezier(0.22, 1, 0.36, 1)`, 1 iteration** — i.e. exactly `--ease-out-soft` | `getAnimations()` |
| Reduced motion | 4 `@media (prefers-reduced-motion: reduce)` blocks plus Tailwind `motion-reduce:transition-none` inline on the digit reel | stylesheet scan + hero `outerHTML` |

Page height 8 457 px. Third-party: a Mintlify assistant widget (`widget.mintlify.com` v0.0.70),
c15t consent, PostHog.

### A.2.2 Inventory of animated / interactive components

1. **Hero flow-field canvas**, 1425×992, `aria-hidden="true"`, `pointer-events-none`,
   `absolute inset-y-0 left-1/2 -translate-x-1/2 max-w-[1920px]`, sitting at `z-0` behind everything.
   Draws dozens of thin gradient curves (teal→lime) that sweep continuously — the curve set is
   visibly different between the t=0 and t=3 s captures.
   *Trigger:* autoplay, continuous. *Communicates:* "traffic / flow", nothing literal; it is
   atmosphere, and it is kept strictly behind the words.
2. **Live digit-reel odometer** in the eyebrow: `Agent traffic [66.4718%] →`, a link to `/data`.
   Observed ticking 66.4718 → 66.4721 → 66.4733 across captures. The mechanic, read from the DOM:
   each digit is a `<span class="relative inline-flex h-[1em] overflow-hidden">` containing a
   `<span class="flex flex-col transition-transform duration-700 ease-[var(--ease-out-soft)]
   motion-reduce:transition-none" style="transform:translateY(-6em) translateZ(0)">` with ten
   children `0`…`9`, each `h-[1em]`. Changing the digit changes the `translateY(-Ne)`.
   Accessibility: the real value is in a `<span class="sr-only">66.4733</span>` and the whole reel is
   `aria-hidden="true"`. Set in Paper Mono with `tabular-nums`.
   *Communicates:* the central claim ("agents are the majority of your readers") as a live fact
   rather than a sentence. **No JS animation library touches this.**
3. **Hero product still.** The 1055×641 SVG of the Mintlify docs app — sidebar (`Ask Assistant`,
   `Quickstart`, `Global Settings`, `AI optimization`, `Components`, `Themes`, then a dimmed second
   group), tabs (`API Reference / Libraries / Changelog`), a `Search or ask` field, and four
   illustrated cards. It bleeds off the right and bottom edges of the viewport rather than sitting in
   a frame.
   *Trigger:* none — it is static. *Communicates:* "this is a documentation site product", instantly,
   at full sharpness on any display, for 93 KB and zero runtime cost.
4. **Logo marquee** — `stats-scroll`, 40 000 ms, linear, **infinite**, on a
   `flex w-max backface-hidden` track, under *"Join 20,000+ of the world's most ambitious companies
   building for agents."*
5. **Rive bento grid**, six cards in a 2-row asymmetric layout. Each card is a canvas scene plus a
   plain label beneath:
   - *Agent-native platform* — an `Ask AI anything…` pill floats over the flow lines
   - *Self-updating knowledge* — three skeleton rows re-sequence themselves
   - *Control who has access* — three member rows with `Editor` / `Admin` / `Collaborator` pills; the
     `Admin` row is highlighted green
   - *Connect with your systems* — three integration marks with flow lines running through them
   - *Collaborate with your team & agents* — a document with tabs `Guide.md`, `LLMs.txt`, `MCP`,
     `Skill.md` and named live cursors: `Agent 130` (purple), `Agent 152` (blue), `User 007` (amber)
   - *Build on top of your existing setup* — a full app layout in skeleton form

   **Measured trigger:** in-view autoplay, gated. Sampling the 695×410 card's 2D context:
   pixel checksum changed while in view (2 031 832 → 2 025 040), was **identical** across 1.3 s while
   scrolled off (2 023 678 → 2 023 678), and changed again on re-entry (2 035 273 → 2 037 121). So:
   plays when visible, freezes when not, resumes on return.
   *Communicates:* six capabilities, each as a wordless micro-scene plus three-to-six plain words.
6. **Deliberate greeking.** Inside every mockup, body text is grey skeleton bars. Only the
   load-bearing words are real: `Ask AI anything…`, `Admin`, `Agent 130`, `Guide.md`, `Skill.md`.
   The eye reads "a document with people in it" without being asked to read anything.
7. **Customer-story carousel**, four 536×472 cards with their own canvases and photographs
   (Anthropic red, Coinbase blue, HubSpot, AT&T), driven by `‹` `›` buttons and a
   `carousel-card-dim` animation that fades the off-centre cards. Each card carries two stat pairs
   (`2M` monthly active developers / `4+` products serviced; `+50x` faster deployment).
8. **Section heading pair**, used four times identically: a black statement line and a grey
   explanatory line, with a small teal keyline in the left gutter and a black pill CTA to the right.
   *"Powering businesses of all sizes."* / *"Run your business on a reliable platform that adapts to
   your needs."* Same shape for *"Built to scale with the agent web."* and *"Enabling the next
   generation of startups."*
9. **Stat band** — `300M+ visitors in the past year`, `2B+ agents in the past year`,
   `99.99% uptime across all services`, each with a hairline icon and a 1086×304 canvas band behind.
10. **Signal dot** — `signal-ping` + `signal-flicker`, both 1 050 ms, linear, infinite, on a
    `rounded-full` span. A two-layer live indicator (an expanding ring plus an opacity flicker).
11. **Scroll-reveal on section blocks** — WAAPI, 450 ms, `cubic-bezier(0.22,1,0.36,1)`, once,
    on `div.flex.flex-col.gap-8` groups.
12. **Startup-logo tile grid** — saturated gradient tiles (pink/magenta, green, indigo, orange) each
    carrying a white rounded logo card, followed by a *"Latest updates"* section.
    *Mechanic, trigger and duration:* **not instrumented.** The tiles sit in the same
    horizontally-scrolling carousel shape as #7, so they are presumed to share its arrow controls and
    `carousel-card-dim`, but that was not verified. *Communicates:* breadth of named customers at a
    glance, by colour rather than by reading.
13. **Nav dropdowns** (`Products`, `Solutions`, `Resources`). *Mechanic:* colour transition on the
    trigger, `transition-colors`, plus a panel on open. *Trigger:* hover/click on the trigger.
    *Duration:* `duration-100` (100 ms) on the trigger colour. *Communicates:* responsiveness at the
    fastest tier — this is a control used constantly, so it barely animates.
14. **Persistent `Ask assistant` pill**, bottom-right, from `widget.mintlify.com` v0.0.70.
    *Mechanic:* static chrome until opened; no entrance motion observed. *Trigger:* click.
    *Duration:* n/a. *Communicates:* the strongest proof on the page — the product is running on its
    own marketing site, and you can ask it something right now.

Reduced-motion strategy (read from source): 4 media blocks plus Tailwind's
`motion-reduce:transition-none` applied inline to the digit reel — i.e. the odometer stops sliding
and simply shows the number. Rive playback under reduced motion was not instrumented.

### A.2.3 Hero-demo anatomy

- **What it is made of:** a **static SVG** of the real product UI (93 KB), layered on a
  continuously-animating 2D canvas flow field, with one live-updating number in the eyebrow. That is
  the entire hero demo. No video, no DOM mockup, no Rive, no WebGL in the hero.
- **How it loops:** the canvas field runs continuously; the SVG never changes; the odometer updates
  on its own cadence with a 700 ms `--ease-out-soft` slide per digit.
- **What triggers it:** autoplay on load. No scroll dependency in the hero.
- **Interactive?** No — `pointer-events-none` on the canvas, the SVG is an `<img>`. The interactive
  elements are the two CTAs and the `Agent traffic` link.
- **Degradation:** the odometer's slide is disabled by `motion-reduce:transition-none` and the
  value is available to screen readers as plain text; the SVG is already static.
- **Dark mode:** a second 93 KB `preview-dark.svg` is fetched — they pay twice rather than recolour.

The design lesson: **the hero does not need to animate the product. It needs to show the product,
sharply, half-bleeding off the edge, while one number proves the claim.**

### A.2.4 Message test

- **After 3 seconds** — *"The knowledge infrastructure agents build on"*, three lines, 56 px, near-black
  on off-white. To its right, a picture of a documentation site. You know it is docs software, and
  that the angle is agents.
- **After 10 seconds** — the subline: *"Self-updating documentation for **startups**, **enterprises**,
  and **agents**."* — plain category noun, three named audiences in bold. The eyebrow has ticked
  twice, so you have registered that `Agent traffic 66.47%` is live. Two CTAs: `Get started ›` and
  `Sign up with Google`.
- **After one scroll** — *"Join 20,000+ of the world's most ambitious companies building for agents"*
  over a logo marquee, then six labelled cards that each animate one capability in a wordless scene.
  You know what it does, who uses it, and roughly how big it is.

The devices: (1) headline states the **position in the stack** ("the infrastructure X builds on");
(2) subline is a **flat category sentence with the audience named**; (3) the product picture arrives
*with* the headline, not after it; (4) one live number does the work of a paragraph of proof.

---

## A.3 The control: Guidefold's current landing (the page the owner rejected)

Captured accidentally when the shared browser navigated to `http://127.0.0.1:4331/`
(`shots/mint-s1750.png`, despite the filename). Quoted verbatim because it is the thing to beat.

- Headline: **"Your repos are already writing the handbook."**
- Kicker: *"Guidefold promotes what generalises, then hands your agent the four rules that apply,
  each one proven."*
- Lede: *"Ranking runs across the whole hierarchy in real time, designed for a 30k-skill corpus.
  Every rule arrives with its source proof attached, and the ones that cannot prove themselves never
  arrive at all."*
- Proof strip: `76 of 76 harmful rules refused.` / `+8.53 pp Recall@10 on SRA-Bench.`
- Scroll cue: `How rules move up`

Message test: after 3 seconds you know there is a handbook metaphor and a repo. After 10 seconds you
have met *promotes*, *generalises*, *hierarchy*, *30k-skill corpus*, *source proof*, *Recall@10*,
*SRA-Bench* — seven research terms — and **no sentence has told you what Guidefold is**. There is no
equivalent of *"Pi is a minimal agent harness"* or *"Self-updating documentation for startups."*
After one scroll there is a cinematic mountain film and a stepped diagram, but still no picture of
the product doing anything.

Both references also carry a **verifiable number** in the hero (pi.dev: the live token/cost status
line inside the terminal; Mintlify: the ticking agent-traffic percentage). Ours carries two, but they
are benchmark deltas that require a paragraph of context to parse. The fix is not fewer numbers — it
is numbers a stranger can read.

---

# B. Ten must-have techniques

Our target stack, taken from the live local build (`http://127.0.0.1:4331/` resource list):
React 19 + Vite + CSS Modules, `src/tokens/tokens.css` as the only value source, `motion` v13 +
`motion/react` already bundled, Base UI (`tabs`, `dialog`, `collapsible`, `button`), spectrumui
(`bento-card`, `number-ticker`, `border-beam`, `spotlight`, `code-block`, `charts/*`), `recharts`,
`lucide-react`, Manrope / Instrument Sans / JetBrains Mono.

Tokens already present and reusable (no new values needed):
`--ease-entrance: cubic-bezier(.16,1,.3,1)` (identical to Mintlify's `--ease-out-expo`),
`--ease-out: cubic-bezier(.23,1,.32,1)`, `--ease-drawer: cubic-bezier(.32,.72,0,1)`,
`--duration-entrance: 420ms`, `--duration-panel: 360ms`, `--duration-draw: 520ms`,
`--duration-count: 900ms`, `--stagger-entrance: 60ms`, `--stagger-cap: 240ms`,
`--enter-rise: 12px`, `--enter-blur: 3px`, `--enter-scale: .985`, `--press-scale: .98`,
`--mask-hidden: inset(0 0 100% 0)`, `--mask-shown: inset(0 0 0 0)`,
`--landing-stage-height: 100dvh`, `--landing-stage-scroll: 260vh`.

**Dependency verdict for all ten: zero new packages.** Rive (a wasm runtime from unpkg),
asciinema-player, GSAP/ScrollTrigger and Lenis are all rejected — every mechanic below is
reproducible with CSS transforms, one `IntersectionObserver`, and the `motion` we already ship.

---

### 1. Say the category in a flat sentence, directly under the stance

**What it does for comprehension:** the headline earns attention; the subline removes doubt. A
stranger cannot guess a category from a metaphor, and will not read a third line to find it.

**Evidence:** pi.dev — *"There are many agent harnesses but this one is yours"* / **"Pi is a minimal
agent harness."** Mintlify — *"The knowledge infrastructure agents build on"* / **"Self-updating
documentation for startups, enterprises, and agents."** Both sublines are one clause, present tense,
naming the thing and the audience.

**How to implement:** copy change in `Hero.tsx`, not code. Constrain the subline to
`--landing-kicker-measure: 34ch` (already defined) and ban from it: *generalises, corpus, hierarchy,
admissibility, ranking, Recall@10, SRA-Bench, promotion, retrieval*. Those words move to the
"Read the numbers" page behind the existing link. Set at `--landing-kicker`
(`clamp(19px,1.5vw,23px)`), weight 400, `--stone-100`.

---

### 2. The staged intro: one sentence exists before anything else

**What it does:** forces a reading order. pi.dev gives the headline ~1 s of monopoly, so the 3-second
test is passed before the page is even assembled.

**Evidence:** pi.dev's `:root[data-intro]` machine — `staged → headline → collapsing → full`,
`headingLeadIn: 175ms`, `heroLiftSettle: 826ms`, `restRevealLag: 350ms`, `introMaxWait: 10000ms`,
with the nav held `aria-hidden` + `inert` until `full`. Confirmed by capture: at t=0 the accessible
tree contains only the logo button and the `h1`; at t=1 s it contains everything.

**How to implement:** set `data-landing-intro` on `<html>` from one `useEffect` in `Hero.tsx`; drive
every reveal from CSS on that attribute, never from JS style writes. Reuse
`--landing-enter-duration: 200ms` and `--landing-enter-delay-1..4` (0/40/80/120 ms) for the cascade;
use `--duration-entrance: 420ms` with `--ease-entrance` for the hero lift. Under reduced motion,
emit the terminal state immediately — mirror pi.dev's
`:root:is([data-landing-intro="staged"],[data-landing-intro="headline"]) .gf-intro-hidden
{ visibility: visible; opacity: 1 }`. Hold the total under 1 100 ms; pi.dev's 826 ms settle is the
upper bound worth copying.

---

### 3. Live DOM as the demo, never video

**What it does:** real text is selectable, searchable, screen-readable, crisp at any DPR, diffable in
review, and correct by construction because it is the CLI's actual output. It also sidesteps
autoplay policy, poster flashes and bandwidth.

**Evidence:** pi.dev's terminal is `<pre class="ap-term-text">` with real text nodes —
`innerText` returned `pi v0.68.1 … Press ctrl+o to show full startup help and loaded resources.`
Zero video files on the entire site. Mintlify has zero video on the homepage too.

**How to implement:** build the stage from `div`/`pre`/`span` with CSS Modules, `--font-mono`
(JetBrains Mono), `--font-size-code: 12px`, `--graphite-900` ground, `--line-strong` hairlines. The
text content is the real output captured for §C. This also retires the hero `hero-flight.mp4` and
`intro.webm` currently loaded by `FilmBackdrop.tsx` from the demo path.

---

### 4. Caption bar + live dot: name the beat in five plain words

**What it does:** a viewer who joins mid-loop is never lost. The label does the explaining so the
scene doesn't have to.

**Evidence:** pi.dev's `figure-caption--terminal` — `PI - LOAD PROJECT SKILLS AND INSTRUCTIONS ●`,
with `terminal-cursor-blink` at 1 250 ms linear infinite on the dot, plus a `figcaption` below
carrying the plain takeaway (*"Pi supports skills, AGENTS.md files and is very token efficient due to
its minimal system prompt."*). Mintlify's equivalent is the single label under each bento card.

**How to implement:** a `<span aria-live="polite">` above the stage with
`--font-size-navigation-label: 10px`, `--tracking-label: .14em`, uppercase. Crossfade the text with
`--text-swap`-style timing: 150 ms opacity out / 150 ms in, `--ease-out`. The dot: a 6 px
`--survey-teal` circle with `opacity` keyframes at 1 250 ms linear infinite — one keyframe, and it is
the only infinite animation we should ship in the hero.

---

### 5. Greek the scenery, keep only load-bearing words real

**What it does:** it tells the eye where to look. A mockup full of real text is a reading task; a
mockup with four real words and grey bars is a glance.

**Evidence:** Mintlify's bento cards — body copy is grey skeleton bars everywhere; the only literal
text is `Ask AI anything…`, `Editor`/`Admin`/`Collaborator`, `Agent 130`/`Agent 152`/`User 007`,
`Guide.md`/`LLMs.txt`/`MCP`/`Skill.md`.

**How to implement:** a `.skel` CSS Module class — `height: 8px; border-radius: 2px;
background: var(--line-strong)` at randomised widths (60–95%), no shimmer. Real text only for: the
prompt, the four skill names, the rule title, the verdict, the numbers. Everything else is a bar.
Mark skeleton blocks `aria-hidden="true"` and give each beat a real `aria-label`.

---

### 6. The digit-reel odometer, as pure CSS transform

**What it does:** converts a claim into an observed event. A number that visibly moves is read as
live measurement; the same number printed flat is read as marketing.

**Evidence:** Mintlify's `Agent traffic 66.4718%` — per-digit `overflow: hidden` 1em window, a
`flex-col` column of `0`…`9`, `transform: translateY(-6em) translateZ(0)`,
`transition-transform duration-700 ease-[var(--ease-out-soft)] motion-reduce:transition-none`, the
visual reel `aria-hidden` with an `sr-only` twin carrying the real value. Observed ticking
66.4718 → 66.4721 → 66.4733.

**How to implement:** we already have `spectrumui/number-ticker.tsx` installed — use it, and if it
animates via JS per-frame, swap its inner mechanism for the reel: ten stacked `<span>`s per digit at
`height: 1em`, parent `overflow: hidden`, `transition: transform var(--duration-count) var(--ease-entrance)`
(900 ms is close to Mintlify's 700 ms and is already a token). `translateZ(0)` for a composited
layer. Add the `sr-only` value and `aria-hidden` on the reel; add
`@media (prefers-reduced-motion: reduce) { transition: none }`. Render in `--font-mono` with
`font-variant-numeric: tabular-nums`. Cost: ~0 KB JS.

---

### 7. Sticky stage + scrolling prose, one chapter per beat

**What it does:** it lets one demo carry six ideas without a six-item feature list, and it gives the
reader control of pacing.

**Evidence:** pi.dev pins a 720 px figure on the left across ~4 800 px of scroll (stage y≈706→5 495 of
a 7 317 px page) while six prose chapters pass on the right, each swapping the cast and the caption.
Breakpoint-aware scroll ranges: `{mobile: 220, tablet: 260, desktop: 300}`.

**How to implement:** `position: sticky; top: <nav height>` on the stage column inside a tall grid
row. We already have `--landing-stage-height: 100dvh` and `--landing-stage-scroll: 260vh`. Drive the
active beat with **one** `IntersectionObserver` over the prose chapters (`rootMargin: "-45% 0px -45% 0px"`,
`threshold: 0`) writing `data-beat="n"` on the stage — never a scroll listener, never a
`requestAnimationFrame` loop. All beat visuals are then pure CSS on `[data-beat="n"]`. Below
768 px, drop sticky and stack each beat above its paragraph.

---

### 8. In-view autoplay that actually stops off-screen

**What it does:** keeps the loop honest — the viewer always sees beat 1 first — and keeps the page
cheap when scrolled past.

**Evidence:** measured on Mintlify's 695×410 bento canvas by pixel checksum: changed in view
(2 031 832 → 2 025 040), **byte-identical** for 1.3 s off view (2 023 678 → 2 023 678), changed again
on re-entry (2 035 273 → 2 037 121). pi.dev does the same with the player object, and adds
`autoPlay: !prefersReducedMotion`.

**How to implement:** a `useInView` from `motion/react` (already bundled) on the stage; when false,
clear the beat timer and leave `data-beat` where it stands; when true, resume. Reset to beat 1 only
if the stage has been fully out of view — otherwise resuming mid-beat is less jarring. Pair with
`document.visibilityState` so a background tab costs nothing.

---

### 9. One background field, behind the words, `pointer-events: none`

**What it does:** supplies motion and depth without competing for attention. Both sites have exactly
one atmospheric layer and it is always the lowest one.

**Evidence:** Mintlify's 1425×992 hero canvas — `aria-hidden="true" pointer-events-none absolute
inset-y-0 left-1/2 z-0 w-full max-w-[1920px] -translate-x-1/2` — behind a `z-10` content grid.
Everything the user must read sits above it, on solid ground.

**How to implement:** we already have the field tokens (`--amp-topo: 16px`, `--amp-grid: 40px`,
`--amp-plane: 20px`, `--landing-topo-opacity: .32`, `--landing-grid-opacity: .1`) and the scrim
tokens (`--film-scrim-hero`, `--landing-hero-scrim`). Keep the field; **remove the video** behind the
demo stage. The demo panel gets `--glass-panel-strong: rgba(12,16,20,.86)` as an opaque ground so no
`backdrop-filter` runs under moving content (the git log already records one live-`backdrop-filter`
removal — do not reintroduce it).

---

### 10. Entrance = rise + fade + a whisper of blur, once, on a strong ease-out

**What it does:** prevents the jarring appearance of a block without ever making the page feel slow.
Both sites converge on almost the same curve and duration, independently.

**Evidence:** Mintlify — WAAPI, **450 ms, `cubic-bezier(0.22,1,0.36,1)`, 1 iteration**, on section
groups. pi.dev — `hero-rise-fade`, one iteration, shaping inside the keyframes. Neither uses
`ease-in` anywhere, and neither repeats an entrance.

**How to implement:** exactly the tokens we already ship —
`transform: translateY(var(--enter-rise)) scale(var(--enter-scale))`, `opacity: 0`,
`filter: blur(var(--enter-blur))` → all zeroed, over `--duration-entrance` (420 ms) with
`--ease-entrance` (`cubic-bezier(.16,1,.3,1)`). Stagger with `--stagger-entrance: 60ms`, capped at
`--stagger-cap: 240ms` — four items maximum, then everything lands together. `transition`, not
`@keyframes`, so a fast scroll can retarget mid-flight. Only `transform`, `opacity`, `filter`. Under
reduced motion, `--duration-reduced: 80ms` opacity only, no transform, no blur.

**Bonus rule carried from both sites:** no `ease-in` anywhere, no entrance from `scale(0)`
(`--enter-scale: .985` is right), and `--press-scale: .98` on every button. All three already exist
in `tokens.css`.

---

# C. Build-ready demo concept for Guidefold

## C.0 The problem this solves

A visitor must be able to answer, without reading a paragraph: *what does this do?* The answer is a
single physical story — **a developer opens a folder, the agent asks a question, the right team rules
arrive, and the team can see it happened.** Everything else on the page is elaboration.

## C.1 Asset reality check

`/tmp/claude-1000/-home-mike-projects-guidefold/f65164e3-ab02-4d5c-904a-4a7136f96241/scratchpad/app-shots/`
**does not exist yet** — nothing has been captured. The concept below is therefore written to build
**today** from real markup plus real CLI text, with screenshots as a later upgrade, never a
dependency. Asset manifest in §C.7.

Real text already captured, verbatim, usable now
(`cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold <cmd>`):

```
$ guidefold where
{ "node": "_root", "owner": "platform-engineering", "ancestors": ["_root"] }

$ guidefold find "add a column to the orders table"
- urn:skill:meridian:forge.ontology:object-type-migrations
    [forge/ontology] Migrating released ontology object types: adding, renaming, widening…
    (score=16721 · node=forge.ontology)
- urn:skill:meridian:_root:postgres-production
    [meridian] Production Postgres conventions shared by every Meridian service…
    (score=17145 · node=_root)
- urn:skill:meridian:forge:dataset-conventions
    [forge] Naming, schema registration, and lineage tagging rules for datasets…
    (score=16499 · node=forge)
- urn:skill:meridian:security:classification-labels
    [security] Data-classification labels in Meridian: the Label enum…
    (score=16246 · node=security)

$ guidefold validate
guidefold validate: 26 skills, 0 errors
```

Note for the copywriter: `score=16721` is exactly the kind of number that reads as research. **Strip
the scores from the hero beat**; keep the node paths, which read as folders. Scores can return in the
"how it works" chapter where there is room to explain them.

## C.2 The split — and why it is not six beats in the hero

The brief lists six moments. Six beats at 3 s is an 18-second loop; nobody waits 18 seconds in a
hero. pi.dev's own answer is the model: **the hero plays one short scene; the other chapters live in
a sticky stage further down with prose beside them.**

- **Hero: 4 beats × 2.5 s = 10 s loop.** Folder → prompt → four cards arrive → one rule loads.
- **"Who uses it" chapter: 2 beats, scroll-driven, no timer.** Review report → org telemetry.

Same component, same markup, two drivers (`mode="auto"` and `mode="scroll"`).

## C.3 Hero stage — shot list

The stage is a single 16:10 panel, `--landing-radius-panel: 16px`, `--glass-panel-strong` ground,
`--line-strong` hairline, four corner brackets (pi.dev's `figure-corner` device). Above it, the
caption bar: `GUIDEFOLD — <BEAT LABEL> ●`. Nothing inside ever reflows the panel: all four beats
occupy the same grid, and beats swap by opacity + 8 px translate, so the panel height never changes.

**Beat 1 — "A repo like yours" (2.5 s)**

- On screen: a file tree, left third. Real text, monospace:
  `meridian/`, `  services/`, `    checkout/`, `      api/`, `      SKILL.md`, `  forge/`,
  `    ontology/`, `      SKILL.md`, `  security/`, `      SKILL.md`. Three `SKILL.md` leaves carry a
  small teal dot. Right two-thirds: an editor pane, fully greeked (§B.5), with one real tab label
  `orders.sql`. A caret sits on a greeked line.
- Motion: tree rows stagger in, `--stagger-entrance: 60ms`, capped at 4 rows then all together;
  `--enter-rise: 12px`, `--duration-entrance: 420ms`, `--ease-entrance`.
- Caption: **"Your team's rules already live in the repo."**

**Beat 2 — "The agent asks" (2.5 s)**

- On screen: the editor pane slides 8 px left and dims to `opacity: .45`; a prompt bar rises from the
  bottom edge of the panel. Typed, character by character:
  `add a column to the orders table`. Then a caret blink, then a `/` spinner replaced by
  `searching 26 skills…`.
- Motion: the prompt bar enters on `--ease-drawer: cubic-bezier(.32,.72,0,1)` over
  `--duration-drawer: 240ms`. Typing is a `width`-in-`ch` reveal on an `overflow: hidden` span
  (`steps()` timing, ~40 ms/char, 32 chars ≈ 1 280 ms) — not a per-character React state update.
- Caption: **"Someone asks for a change."**

**Beat 3 — "Four rules arrive" (2.5 s)** — *the beat that carries the whole page*

- On screen: four cards land in the right two-thirds, staggered, each showing only:
  a node path chip (`forge/ontology`, `meridian`, `forge`, `security`), a skill name
  (`object-type-migrations`, `postgres-production`, `dataset-conventions`,
  `classification-labels`), and one greeked line of description. No scores. A fifth and sixth card
  ghost in at `opacity: .18` and fade out — the ones that did not make the cut.
- Motion: `--stagger-entrance: 60ms` between cards, capped at `--stagger-cap: 240ms`; each card
  `translateY(12px) scale(.985) blur(3px) → 0`, `--duration-entrance`, `--ease-entrance`. The
  rejected ghosts fade only (no transform) so they read as absence, not arrival.
- Caption: **"Only the rules that apply show up."**

**Beat 4 — "The rule opens" (2.5 s)**

- On screen: the first card expands to fill the right two-thirds — a `SKILL.md` header
  (`postgres-production`, `[meridian]`) over six greeked body lines with two real ones:
  `Always add columns with a default and backfill in a separate migration.` and
  `Never lock a released table during business hours.` A hairline connects the expanded card back to
  its `SKILL.md` leaf in the tree, drawn with `stroke-dashoffset` over `--duration-draw: 520ms`.
- Motion: card→panel is a scale + position transition on the same element (no crossfade between two
  copies), `--duration-panel: 360ms`, `--ease-entrance`.
- Caption: **"Your agent reads the real file, not a summary."**

Then hold 600 ms and loop to beat 1 with a 200 ms crossfade.

**Transitions between beats.** One rule: the panel frame never moves; only its contents change.
Elements that persist across beats (the file tree, the prompt bar) **transition in place** rather
than exiting and re-entering — this is what makes it read as one continuous scene rather than four
slides. Everything else is opacity + `translateY(8px)`, 200 ms, `--ease-out`.

## C.4 "Who uses it" chapter — shot list

Sticky stage, prose scrolling beside it (§B.7). Two beats, advanced by `IntersectionObserver` on the
prose blocks, no timer.

**Beat 5 — "The review" (scroll beat)**

- On screen: a pull-request review panel. Left: a greeked diff with three real changed-line markers.
  Right: a verdict list with three rows —
  `✓ migration adds a default` (teal), `✓ backfill in its own commit` (teal),
  `✗ table lock inside business hours` (amber) — each with the node path of the rule that produced
  it (`meridian / postgres-production`). Bottom: `guidefold validate: 26 skills, 0 errors` in mono.
- Motion: verdict rows stagger in at `--stagger-panel: 70ms`; the amber row gets a single
  `--shadow-selected` inset flash over `--duration-panel`, once, no pulse.
- Caption: **"Every review points at the rule it came from."**

**Beat 6 — "The whole org" (scroll beat)**

- On screen: three metric tiles using the existing `spectrumui/number-ticker` with the §B.6 reel —
  `26` skills indexed, `4` rules delivered per request, `0` unproven rules shipped. Beneath them a
  compact Spectrum bar chart (per `docs/ui/UI.md §7`) of rule deliveries by node, `--survey-teal`
  series, six bars, no gridline clutter.
- Motion: reels roll on entry, `--duration-count: 900ms`, staggered `--stagger-count: 40ms`; bars
  grow from the axis on `--duration-draw: 520ms`, `--ease-entrance`, staggered `--stagger-panel: 70ms`.
  Once. Never re-runs on scroll-back within the same visit.
- Caption: **"And the team can see which rules are actually doing work."**

## C.5 Reduced motion

One fallback, not six. Under `@media (prefers-reduced-motion: reduce)`:

- The hero stage renders **beat 4 as a static composite** — file tree, dimmed editor, the four
  arrived cards, and the first card expanded — with the connecting hairline drawn at full length. No
  timer is started, no `IntersectionObserver` beat driver runs.
- Caption bar shows the beat-4 caption, no dot animation.
- A visible `[ Play the demo ]` button appears below the panel (pi.dev's exact pattern:
  `autoPlay: !prefersReducedMotion, controls: prefersReducedMotion`). Pressing it runs the loop once.
- The chapter stage renders beat 6 statically, with numbers at final value and bars at full height.
- All transitions collapse to `--duration-reduced: 80ms`, opacity only.

The static composite must be legible on its own, because it is also what a screenshot, a print, and a
social preview will show.

## C.6 Performance envelope

| Budget | Target | How it is met |
|---|---|---|
| New dependencies | **0** | no Rive, no asciinema-player, no GSAP, no Lenis. `motion` v13 already bundled (`useInView` only) |
| Extra JS | **< 60 KB** — realistically ~4 KB gzipped of app code | one beat-driver hook (timer + `useInView` + `data-beat` attribute) and one `<Stage>` component; all visuals are CSS on `[data-beat]` |
| Video / image sequence | **none** in the demo path | retires `hero-flight.mp4` + `intro.webm` from the demo; the film backdrop, if kept, stays a separate decision |
| Animated properties | `transform`, `opacity`, `filter: blur` only | no `width`/`height`/`top`/`left`; the typing reveal uses `ch` width on a fixed-height span, which does not reflow siblings |
| Layers | `will-change: transform` only on the 4 beat cards, removed on beat exit | avoids the "everything is composited" memory cliff |
| `backdrop-filter` | **none under moving content** | the panel uses `--glass-panel-strong` (opaque) — see the fix already recorded in commit `944f6ef` |
| Infinite animations | **exactly one** (the 6 px caption dot, 1 250 ms) | matches pi.dev's restraint; Mintlify runs three and it is already at the limit |
| Off-screen cost | zero | `useInView` clears the timer; `visibilitychange` clears it in background tabs |
| Fonts | no new faces | Manrope / Instrument Sans / JetBrains Mono are already loaded |

Measure before and after per `performance-budgets`: first-beat-visible, JS transferred for the
landing route, and long-task count during the loop.

## C.7 Asset manifest — what a screenshot would replace

Every row degrades to the DOM version already specified; nothing is blocked on capture.

| Beat | Placeholder shipping now | Screenshot that could replace it | Size | Without it |
|---|---|---|---|---|
| 1 | DOM file tree + greeked editor | editor with a real repo tree open | 1 280×800, WebP ≤ 90 KB, dark theme | **No loss.** The DOM version is sharper and themeable; prefer keeping it |
| 2 | DOM prompt bar, CSS typing | harness prompt bar mid-type | 1 280×200 crop, ≤ 40 KB | **No loss** |
| 3 | DOM cards from real `find` output | — | — | Should stay DOM: the text is the point |
| 4 | DOM `SKILL.md` panel | a real rendered `SKILL.md` from `ui/` | 900×600, ≤ 60 KB | **No loss** |
| 5 | DOM review panel | real `guidefold report` output in the hosted UI review view | 1 280×800, ≤ 90 KB | Mild: a real PR view would add credibility. Ship DOM first |
| 6 | Spectrum bar chart + number reels | the hosted telemetry view | 1 280×720, ≤ 90 KB | Should stay live components — `docs/ui/UI.md §7` requires Spectrum Charts, and a screenshot of a chart is a regression |

If screenshots are captured, use SVG where the source is vector UI (Mintlify's 93 KB
`preview-light.svg` stays sharp at every DPR and needs no `2x` twin) and supply a `-dark` variant.

## C.8 Headline and subline — three variants

Test applied: show headline + subline alone to someone who has never heard of Guidefold. Can they say
**what it is** and **who it is for**? Fails immediately on: *generalises, corpus, hierarchy,
admissibility, promotion, retrieval, Recall@10, SRA-Bench*.

**Variant A — the category-first one (recommended)**

> ### Your coding agent doesn't know your team's rules. Now it does.
> **Guidefold is team instructions for coding agents.** Keep the rules next to the code they govern;
> every agent on the team gets the ones that apply.

**Variant B — the position-in-the-stack one (Mintlify's shape)**

> ### The house rules your coding agents build on.
> **Guidefold keeps your team's engineering rules in the repo and hands each agent only the ones
> that apply to the file it's touching.**

**Variant C — the stance one (pi.dev's shape)**

> ### Every agent gets the same onboarding. Yours.
> **Guidefold is team instructions for coding agents — written once, stored in the repo, delivered to
> whichever harness your team uses.**

**Recommended: Variant A.**

It is the only one whose subline opens with a bare copula — *"Guidefold is team instructions for
coding agents"* — which is the exact device both references use (*"Pi is a minimal agent harness"*,
*"Self-updating documentation for startups, enterprises, and agents"*) and the exact device our
current page is missing. The headline names the pain in words a manager and an engineer both already
own ("doesn't know your team's rules"), and resolves it in three syllables. It also happens to match
the site `<title>` already in production — *"Guidefold | Team instructions for coding agents"* —
so the page finally says out loud what the tab has been saying all along.

B is the most elegant but "house rules" is a metaphor doing category work, and its subline runs to 26
words before it names anything. C is the most distinctive and the closest to pi.dev's voice, but
"the same onboarding" asks the reader to hold an analogy while the real noun is still two lines away.

Whichever wins, the pairing rule is fixed: **the headline may take a stance; the subline must contain
a sentence of the form "Guidefold is ⟨plain noun phrase⟩ for ⟨named audience⟩."**

---

## Open items

- `app-shots/` has not been captured. §C.7 is written so this does not block the build.
- Mintlify's Rive playback under `prefers-reduced-motion` was not instrumented; our §C.5 fallback is
  derived from pi.dev's source, which is explicit.
- The Rive bento canvases exposed a 2D context in headless Chromium at DPR 1 despite the
  `@rive-app/webgl2` package name; on a WebGL2-capable client the runtime may take a different path.
  The in-view gating measurement is unaffected.
- The Guidefold "before" quotes in §A.3 come from the local dev server at the time of capture
  (branch `landing/why-how-value`); re-read `ui/src/routes/landing/Hero.tsx` before quoting them in
  any published document.
