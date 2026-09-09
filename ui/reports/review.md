# Guidefold landing — independent review

**Reviewer role:** read-only. No file under `ui/src`, `ui/e2e`, `ui/qa/contracts.json` or `ui/design` was modified. Only this report and `ui/qa/review/*.png` were written.

**Build under review:** `src/routes/landing/` (index.tsx, landing.module.css, scroll.ts, HeroMedia.tsx, IntroFigure.tsx, DemoDialog.tsx, InstructionReader.tsx, RouteRule.tsx, WaitlistForm.tsx, Footer.tsx, instruction.ts) + `src/tokens/tokens.css` + `src/components/ui/button.tsx`.

**Method:** `pnpm typecheck && pnpm build`, then the production bundle served by `pnpm preview` on 127.0.0.1:4331 and driven with Playwright chromium 1.63.0 at 360×800, 390×844, 768×1024 and 1440×900. axe-core 4.13.0 injected from `node_modules`. Skills applied in order: `cloudfloo-quality-gate/resources/gate.md`, `audit-release-quality/resources/workflow.md`, `review-animations` + `resources/STANDARDS.md`, `cloudfloo-premium-scroll-motion/resources/motion-system.md` (validation), `avoid-ai-writing/resources/workflow.md`. Preview server was stopped after capture; port 4331 confirmed free.

Per the task, the placeholder state of `hero-poster.webp` / `plane-*.webp` and the absence of `hero-loop.mp4|webm` are **not** reported as findings. The *code path* around them was tested and passes (see F-PASS-3/4).

---

## Verdict

# PASS — no blocking or high-severity finding

Two medium findings should be fixed before ship (F1 mobile navigation, F2 scroll-sampler recalc cost), but neither is blocking and neither is high. Preservation is intact: no protected URL, id, form field, FAQ answer or legal string was changed, and every branch of the waitlist, confirm and unsubscribe flows was exercised at runtime against a locally stubbed endpoint. Several parts of the implementation are notably above the bar.

| Severity | Count |
|---|---|
| Blocking | 0 |
| High | 0 |
| Medium | 2 |
| Low | 8 |

**Note on F1's severity.** I first rated the hidden mobile header nav as high, on a strict instance-level reading of the `/docs/` acceptance check ("Both anchors … are reachable by keyboard"). I have lowered it to medium on reconsideration, and the reasoning is worth stating because it is the one call that decides the verdict. This preservation map is framed comparatively throughout — "unchanged from today", "resolve to the same targets as today", "behaviour unchanged from `ui/src/routes/Landing.tsx`" — so a preservation failure requires demonstrating a *change*. I cannot: `build-notes.md` records that the previous landing sources were untracked in git, so no baseline exists to diff, and the brief's own `motionGrammar.stateModel` contemplates the outcome with "menuOpen (mobile nav, **if kept**)". Meanwhile the protected destination itself is keyboard-reachable at all four required viewports via the footer `Documentation` anchor, and no URL or label changed anywhere. What remains is a real responsive/UX regression risk at priority 2 — worth fixing, not a demonstrated preservation breach. Rating it high would have rested the verdict on an unverifiable regression claim.

Deterministic gates: `pnpm typecheck` pass, `pnpm build` pass. Zero console errors, zero page errors, zero failed same-origin requests and zero 4xx/5xx responses at all four viewports. Zero horizontal overflow at all four viewports. One axe violation (low, decorative).

---

## Findings, ordered by severity

### F1 — MEDIUM — Header navigation is removed at ≤720px with no replacement

*Review priority 2 (responsive / accessibility). Not a demonstrated preservation failure — see the severity note in the verdict.*

**Evidence**
- `src/tokens/tokens.css:171` — `--landing-nav-display:none` inside `@media(max-width:720px)`.
- `src/routes/landing/landing.module.css:30` — `.nav nav{display:var(--landing-nav-display);…}`.
- Measured: at **360×800** and **390×844**, `getComputedStyle(header nav).display === "none"` and all three links (`How it works` → `#how-it-works`, `Docs` → `/docs/`, `GitHub` → `https://github.com/wiatrM/guidefold`) report `visible: false`. At 768×1024 and 1440×900 the same nav is `flex` and all three are visible and keyboard-reachable.
- There is no hamburger, disclosure or any other affordance in `index.tsx:67-71`. The header at mobile is brand + "Join the waitlist" only.
- Screenshots: `qa/review/first-360x800.png`, `qa/review/first-390x844.png` (compare `qa/review/first-768x1024.png`).

**Why this is medium, and why it is not a preservation failure**
The preservation map's `/docs/` entry states the acceptance check as *"Both anchors point at /docs/ and are reachable by keyboard."* Read at the level of the instance, the header anchor fails at 360 and 390. Read at the level of the protected destination — which is what this map protects, and how its other entries are worded — it passes: the footer `Documentation` anchor resolves to `/docs/` and is keyboard-reachable at all four viewports, both anchors still point at `/docs/`, and no URL, label or anchor was removed. I take the second reading, because every acceptance check in this map is comparative ("unchanged", "same targets as today"), and I cannot demonstrate a change: `build-notes.md` records the previous landing sources as untracked in git, so there is no baseline to diff, and the brief's `motionGrammar.stateModel` explicitly contemplates the outcome with "menuOpen (mobile nav, **if kept**)".

What is left is still worth fixing on its own terms: on half the mandated viewports the page loses all in-page navigation, including the only header path to the repository, with no hamburger or disclosure to replace it. `reports/build-notes.md` records no deviation for dropping it, so it is at least undocumented. Priority 2, medium.

**Acceptance check for the fix:** at 360×800 and 390×844, an anchor with `href="/docs/"` and an anchor with `href="https://github.com/wiatrM/guidefold"` are focusable within the header region — either by keeping the nav visible (it is three short links) or by adding a disclosure control — and tab order still reaches them before `#main` content.

---

### F2 — MEDIUM — The scroll sampler writes `--p` on `.page`, invalidating 248 descendants every frame; measured 2.7 ms/frame of style recalc against a stated 1 ms budget

*Review priority 5 (performance). Cannot block.*

**Evidence**
- `src/routes/landing/index.tsx:56` — `useSectionProgress(page)` registers the page wrapper alongside the four sections.
- `src/routes/landing/scroll.ts:33` — `element.style.setProperty('--p',p.toFixed(4));`
- Registered elements and their subtree sizes, measured live: `.page` **248 descendants**, `.hero` 15, `.why` 7, `.how` 81, `.value` 17.
- CDP `Performance.getMetrics` across 120 rAF-paced scroll frames at 1440×900 (desktop-class machine):

  | Metric | Total over 120 frames | Per frame |
  |---|---|---|
  | `RecalcStyleDuration` | 323.4 ms | **2.695 ms** |
  | `LayoutDuration` | 11.3 ms | 0.094 ms |
  | `ScriptDuration` | 18.6 ms | 0.155 ms |

- `design-brief.json` → `performanceBudget.mainThread`: *"Budget: under 1ms per frame on a mid-range Android."* Desktop already exceeds it by ~2.7×.

**Diagnosis.** The sampler's own JavaScript is cheap (0.155 ms/frame) and layout is cheap (0.094 ms/frame). The whole cost is style invalidation: `--p` is an unregistered inherited custom property, so writing it on `.page` forces the engine to re-resolve style for the entire document subtree once per frame. This is exactly the `review-animations` escalation trigger *"Updating a CSS variable on a parent to drive a child transform (style recalc storm)."* The four section-level writes are fine — their subtrees are 7–81 nodes and their consumers are direct children.

**Fix (cheap and safe).** `.page`'s `--p` has exactly two consumers, `.topo` and `.survey` (`landing.module.css:17-18`), both children of `.field` (2 descendants). Register the page-level progress on `.field` instead of `.page`. `[data-p-ready] .routeLine` (`landing.module.css:91`) still matches through `.how`, so nothing else changes. Optionally also declare `@property --p{syntax:'<number>';inherits:true;initial-value:.5}` so the engine can invalidate more narrowly.

**Acceptance check:** `RecalcStyleDuration` per frame < 1 ms over a 120-frame scroll at 1440×900, with `--p` on `.hero`/`.why`/`.how`/`.value` unchanged and the reverse-scroll identity in F-PASS-2 still exact.

---

### F3 — LOW — `getBoundingClientRect()` is read live every frame, not cached as the brief specifies

`src/routes/landing/scroll.ts:31`. `design-brief.json` → `motionGrammar.scrollEngine.implementation` says the rAF *"reads each registered section's **cached** rect"*. It reads a live rect per element per frame. Measured impact is small (0.094 ms/frame; the five reads are batched before any write, so there is one layout flush per frame, not five). This is a conformance nit against the brief's own wording, not a performance problem. Viewport: all. **Acceptance:** either cache rects and invalidate on resize/rotation/font-load, or amend the brief sentence.

### F4 — LOW — The FAQ collapsible animates `height`, a layout property

`src/routes/landing/landing.module.css:172-174` — `.questionPanel{overflow:hidden;height:var(--collapsible-panel-height)}` with `transition:height var(--duration-menu) …`. `review-animations` standard 7 and its escalation list ban animating layout properties. Strongly mitigated: this is Base UI's idiomatic accordion mechanism, it animates only on pointer interaction, its measured layout cost is negligible, and reduced motion removes it (`landing.module.css:214`). A craft objection alone is never blocking. Viewport: all. **Acceptance:** none required; if changed, `grid-template-rows: 0fr→1fr` or `clip-path` are the GPU-friendlier equivalents.

### F5 — LOW — `transition-all` survives in `button.tsx`, but is verifiably neutralised (no action)

`src/components/ui/button.tsx:7` carries `transition-all` in the `cva` base string, which the brief's `prohibitedPatterns` bans. The writer recorded it as a protected exception (file hash-pinned in `qa/spectrum-registry.json`). **I verified the override empirically** rather than accepting the argument: computed `transitionProperty` on the hero primary CTA, the header `navAction`, the `Play demo` trigger and the waitlist submit is all four times

```
background, border-color, color, transform   /   0.12s ×4   /   ease-out ×3 + cubic-bezier(0.23, 1, 0.32, 1) on transform
```

matching `landing.module.css:34` exactly. `hasTailwindLayer: true` confirms the mechanism: Tailwind utilities sit in a cascade layer, CSS-module rules are unlayered and therefore win regardless of specificity or source order. The build-notes explanation is correct. Viewport: all. Informational only.

### F6 — LOW — Footer wordmark contrast 1.39:1 (the only axe violation)

`src/routes/landing/landing.module.css:196` — `.wordmark{color:var(--graphite-700)}` = `#232b33` on `#07090c`, 96px. axe `color-contrast`, impact `serious`, 1 node, expected 3:1. Mitigated: `Footer.tsx:17` marks it `aria-hidden="true"`, it carries no information, and it duplicates the adjacent footer brand link — so WCAG 1.4.3's incidental/decorative exemption plausibly applies. Viewport: all. **Acceptance:** either lift to ≥3:1 or record the decorative exemption in build-notes so the gate stops re-raising it.

### F7 — LOW — The scroll-drawn route rule is effectively never seen complete

`landing.module.css:91-93` maps the draw to `(--p - .18)/.44`, so the route only finishes at `p ≥ .62`. Measured on `#how-it-works`: at 30% into view `--p = 0.1261` → `stroke-dashoffset: 560px` (nothing drawn, both waypoints at `opacity: 0`); at 60% `--p = 0.2523` → `467.98px` (16% drawn). `p` reaches .62 only when HOW is nearly scrolled past. The element reserves 64px (`--landing-rule-height`) that is blank for most of the section's on-screen life. Craft only. Viewport: 1440×900, `qa/review/how-30-forward.png`, `qa/review/how-60.png`.

### F8 — LOW — At mobile, the code panel sits between the HOW answer and its three mechanism beats

`index.tsx:107` places `.howFigure` (IntroFigure + InstructionReader) between `howIntro` and `howDetail`, so at 360/390 the read is heading → answer → figure → full SKILL.md reader → beats. A tall reader panel separates the claim from its explanation. This is documented deviation #5 in build-notes and it correctly preserves DOM order = reading order, which is the higher rule (`DESIGN.md` §9). Reporting for the record, not for change. Viewport: 360×800, 390×844, `qa/review/full-390x844.png`.

### F9 — LOW — Hero entrance cancels with `animation:none` instead of retargeting

`landing.module.css:67` — `.heroCopy:focus-within>*{animation:none;}`. Focus arriving mid-entrance snaps the four hero children to their final state rather than easing there. A 200 ms window, above the fold, once per load; the intent (get out of a keyboard user's way immediately) is right and arguably worth the snap. Interruptibility nit per standard 6. Viewport: all.

### F10 — LOW — Triadic cadence clusters in the VALUE section (approved-voice exception, no action)

`index.tsx:126` — *"a platform team gets one place to keep the rules, an owner gets a review step before anything reaches an agent, and a developer gets the right instruction without asking for it"* — and the three role cards immediately restate the same triad. `avoid-ai-writing` lists *"repeated groups of three"* under fix-only-if-harmless. Here each element of the triad maps to a real, named audience and the line is verbatim from the approved `copy.md`, so it is an approved-voice exception. See the copy section below for the full scan.

---

## Verified passes worth recording

**F-PASS-1 — Deterministic gates and runtime cleanliness.** `pnpm typecheck` (tsc --noEmit) exit 0; `pnpm build` exit 0 in 1.27 s. Across 360×800, 390×844, 768×1024 and 1440×900: `console` errors 0, `pageerror` 0, failed same-origin requests 0, responses ≥400 0. `documentElement.scrollWidth === clientWidth` at every viewport (360/360, 390/390, 768/768, 1440/1440) — no horizontal overflow. The only elements extending past the viewport box are the deliberately inset decorative field (`--landing-field-inset:-48px`) and the `-10000px` honeypot, both clipped. No clipped text at 360 (`scrollWidth > clientWidth` on headings/paragraphs/links/code: none). The only failed requests anywhere are YouTube's own aborted teardown requests after the demo dialog closes.

**F-PASS-2 — Scroll reversibility is exact, by construction and by measurement.** `--p` is a pure function of geometry and returns bit-identically. Scrolling to `#how-it-works` at 30% in view, then to 60%, then to the document end, then back to 30%:

| | `--p` on `.how` | `stroke-dashoffset` | `--p` on `.hero` |
|---|---|---|---|
| 30% forward | `0.1261` | `calc(560px)` | `0.8895` |
| 60% | `0.2523` | `calc(467.982px)` | `1.0000` |
| **30% reverse** | **`0.1261`** | **`calc(560px)`** | **`0.8895`** |

Pixel diff of `how-30-forward.png` vs `how-30-reverse.png`: 24,925 of 1,296,000 pixels (1.92%), confined to a single bounding box `x 887–1105, y 745–899`. That box is the IntroFigure, whose one-shot animation has played and is holding a later frame — designed behaviour (`IntroFigure.tsx:29-39`, plays once at 40% visibility, holds its final frame). Every scroll-linked layer is identical. Viewport 1440×900.

**F-PASS-3 — Reduced motion is a complete static page, not a faster one.** With `reducedMotion:'reduce'`: `document.querySelectorAll('video').length === 0` (both the hero and the intro video are conditionally unmounted, not merely `preload="none"`), **zero** `.mp4`/`.webm` requests, `[data-p-ready]` count 0 (sampler never installs), `--p` on `#how-it-works` resolves to the token default `.5`, route `stroke-dashoffset: 0px` with both waypoints at `opacity: 1` (drawn, not the 73% that the `--p=.5` formula would give — the `[data-p-ready]` mechanism works as designed), hero `h1` `animation-name: none`, poster visible. Zero console errors. `qa/review/reduced-motion-1440x900.png`. Save-Data behaves identically: 0 videos, 0 `[data-p-ready]`, route drawn.

**F-PASS-4 — Hero media degrades correctly.** Three separate claims, with the evidence that actually supports each:

- *The reduced-motion / Save-Data gate holds* — **proven.** `HeroMedia.tsx:44` makes the `<video>` conditional on `allowed && inView && decoded && !failed`, so under `reducedMotion:'reduce'` and under Save-Data the element is not mounted at all: `querySelectorAll('video').length === 0` and zero `.mp4`/`.webm` requests. This is a real gate, not an artefact of the missing asset.
- *Error / timeout fallback holds* — **proven.** With `**/hero-loop.*` aborted at the route level, the poster stays at `opacity: 1`, width 1284.8px, `hidden: false`, no layout shift, no media control rendered (it is gated on `ready`), no console error. The `<video>` sits invisible until the 8 s `canplay` timeout (`HeroMedia.tsx:47-51`) marks it failed and unmounts it. `qa/review/video-blocked-1440x900.png`.
- *Poster-first ordering under normal conditions* — **not yet provable.** Zero `.mp4`/`.webm` requests were observed at every viewport, but that follows from `preload="none"` plus a `play()` that is never reached because `hero-loop.*` does not exist. It is consistent with poster-first but does not demonstrate it. Re-verify the request ordering (poster decodes → video requested, and the poster remains the LCP element) once the real loop asset lands.

**F-PASS-5 — Demo dialog.** Zero YouTube/ytimg requests before open (measured on a full page load). Opening mounts exactly one `youtube-nocookie` iframe; initial focus lands on `Close`; `Escape` unmounts the iframe (count 0) and returns focus to `Play demo`. `DemoDialog.tsx:23` `initialFocus`/`finalFocus`. `qa/review/dialog-1440x900.png`.

**F-PASS-6 — Focus and tab order.** Tab order equals DOM order equals visual order. Stop 1 is `Skip to content → #main`. Stops 3–5 are the nav links, 6–7 the two "Join the waitlist" controls, 8 `Play demo`, then the HOW figure, reader, links, disclosure, then the form (`waitlist-email` → submit → consent → `Privacy`), then the four FAQ triggers, then the footer. Every one of the first eight stops carries a visible ring: `2px solid rgb(63,184,177)`, offset `3px`. The honeypot is `tabIndex: -1` inside `aria-hidden="true"` and never receives focus. Only the selected tab (`Read instruction`) is in the tab order — correct roving tabindex. Sequential heading hierarchy: exactly one `h1`, `h2` per section, `h3` only on FAQ triggers. `qa/review/focus-trail-1440x900.png`.

**F-PASS-7 — Sampler shape.** Exactly **1** `scroll` listener and **1** `resize` listener on `window`, both passive and both schedule-only. 3 `IntersectionObserver` instances total: the shared sampler, `HeroMedia`'s viewport gate, `IntroFigure`'s play gate — the brief's "one IntersectionObserver" refers to the sampler, which is satisfied. rAF is properly coalesced: 32 frames scheduled across 60 scroll steps (0.53 per step). No `setInterval`, no per-frame React state, no WebGL. Only `transform` and `opacity` are scroll-driven.

**F-PASS-8 — Bundle.** Landing route chunk `landing-CUuWWoyf.js` **55.48 kB raw / 18.73 kB gzip**; `landing-D2rlgLih.css` **24.62 kB / 4.50 kB gzip**. Lazy `CollapsiblePanel` (15.55 kB), `DialogTrigger` (60.59 kB) and `SkillContent` (116.25 kB) load on demand. No `three`/WebGL in the landing path.

---

## Preservation contract — item by item

All 13 items verified against the rendered production DOM at 1440×900 unless a viewport is named. `in DOM (panel closed)` means the string is present in `innerHTML` but not in `innerText`, which is exactly what the contract requires of the `keepMounted` FAQ panels.

| # | Protected item | Result | Evidence |
|---|---|---|---|
| 1 | Waitlist form strings, ids, honeypot, maxLength, aria wiring | **pass** | `#waitlist` form id; `#waitlist-email` `name=email` `type=email` `maxLength=254` `required` `placeholder="you@company.com"` `autocomplete=email` `aria-describedby="waitlist-consent"`; `#waitlist-consent` label wraps the required `name=consent` checkbox; honeypot `#waitlist-website` `name=website` `tabIndex=-1` inside `aria-hidden="true"`; exactly one visible text input + one required checkbox; `Paid hosting is planned. Sign up for availability updates.`, `Your email`, `Join the waitlist`, `Email me about hosted Guidefold. Unsubscribe anytime.` all verbatim. 12 000 ms abort at `WaitlistForm.tsx:29`. |
| 2 | Waitlist success strings + `role=status` + focus move | **pass (exercised)** | Submitted with the endpoint stubbed locally (`page.route` on `**/api/v1/waitlist**` → `200 {schema_version:"1.0",request_id,data:{status:"pending"}}`; no request left 127.0.0.1). Rendered: `Check your inbox to confirm.` / `New signups receive one confirmation email. Repeat requests do not send another message. Already confirmed? You’re all set.` / `Missing the email? Contact hello@cloudfloo.io.` — all verbatim, in `role="status"`, and `document.activeElement` is the status region (`aria-label="Waitlist confirmation"`), so focus moved. `mailto:hello@cloudfloo.io` intact inside it. Request body `{"email":"you@company.com","consent":true,"website":""}` — honeypot sent empty. `qa/review/waitlist-success-1440x900.png`. |
| 3 | Confirm / unsubscribe flow strings, URL replaced, no hero video | **pass (exercised)** | `/?confirm=TESTTOKEN` renders `Confirm your email`, `Confirm that you want updates about hosted Guidefold.`, `Confirm email`, `Back to Guidefold` verbatim; final URL `http://127.0.0.1:4331/` (history replaced); `video` count **0**; hero poster absent. With a stubbed `200 …status:"confirmed"` the result reads `You’re on the hosted Guidefold waitlist. We’ll email you about availability.`; `/?unsubscribe=TOKEN` renders `Leave the waitlist` / `Stop receiving hosted Guidefold updates.` / `Unsubscribe` and on `…status:"unsubscribed"` reads `You’ve been unsubscribed from the Guidefold waitlist.` — all verbatim. Endpoints hit: `/api/v1/waitlist/confirm` and `/api/v1/waitlist/unsubscribe`. `qa/review/email-confirm-1440x900.png`. |
| 4 | Four error strings → `role=alert`, input retained | **pass (exercised)** | Each `WaitlistError` kind driven by a stubbed status. `429` → `Too many attempts. Please try again in an hour.` · `400` → `Please check your email and consent, then try again.` · `410` on `/confirm` → `This link is invalid or expired. Contact hello@cloudfloo.io for help.` · `500` → `We could not confirm the request. Please try again. Your input is still here.` All four verbatim in `<p role="alert" id="waitlist-error">`. On every join error the typed email is retained (`you@company.com`), `aria-invalid="true"` is set, and `aria-describedby` becomes `"waitlist-error waitlist-consent"`. |
| 5 | Privacy FAQ (`#privacy`) — Resend, 30/365 days, dedup hash, YouTube paragraph, mailto | **pass** | `aria-expanded="false"` on load and all of `Resend handles confirmation email delivery`, `Unconfirmed signups are scheduled for deletion after 30 days`, `Confirmed and unsubscribed records are scheduled for deletion 365 days after signup`, `deduplication hash is retained until deletion`, `The demo connects to YouTube only when played` present in DOM (panel closed). Trigger text `How is my email used?` unchanged. `mailto:hello@cloudfloo.io` present twice (privacy answer + footer). Consent `Privacy` link → `#privacy` opens the panel (`index.tsx:21`). |
| 6 | Pricing facts (`#question-2`) | **pass** | `aria-expanded="false"` on load; `$99 per organisation per month, excluding taxes`, `$9 of provider usage costs $10`, `There is no unlimited AI allowance`, `Enterprise SSO is not included`, `hosted runner pricing and quotas will be specified before purchase` all verbatim in DOM. No figure rounded, restated, or moved into a pricing card. Deep link `/#question-2` expands it (`aria-expanded="true"`, panel height 121.56px). `qa/review/faq-deeplink-1440x900.png`. |
| 7 | Availability (`#question-1`) and harness (`#question-3`) FAQs | **pass** | Both `aria-expanded="false"` on load; triggers `Is Guidefold available now?` and `Which coding tools can I use?` verbatim; the `integration documentation` link resolves to `https://github.com/wiatrM/guidefold#coding-harness-to-instruction-delivery`. |
| 8 | Availability statements + footer line | **pass** | `Open source today.` + `CLI and retrieval service.` and `Paid hosting is planned. Sign up for availability updates.` visible as text in the availability band; footer `Open-source tools. Hosted service planned.` unchanged. Neither softened, merged, nor moved into a tooltip. |
| 9 | Five GitHub URLs, `target`/`rel` retained | **pass** | 9 GitHub anchors resolving to exactly 4 distinct targets: repo root (header nav + footer), `#quickstart` ×3, `#coding-harness-to-instruction-delivery` ×2, and the fixture blob URL. `Open the original file` retains `target="_blank" rel="noreferrer"`. *Caveat: the header-nav instance is `display:none` at ≤720px — see F1. The URLs themselves are unchanged at every viewport.* |
| 10 | `/docs/` link in header nav and footer | **pass, with a caveat** | Three `/docs/` anchors exist (`Docs`, `Read the docs`, `Documentation`), all pointing at `/docs/`; no URL or label changed. At 768 and 1440 both named instances are keyboard-reachable. At 360 and 390 the header `Docs` anchor computes `display:none`, so the protected destination is reachable only via the footer `Documentation` anchor — which is keyboard-reachable at every viewport. The destination contract holds; the header instance's mobile reachability is tracked as **F1 (medium)**. |
| 11 | YouTube demo stays the `Play demo` action; no request before open | **pass** | Visible `<button>Play demo</button>` in the hero plus a footer `<a>Play demo</a>`; **0** YouTube/ytimg requests before open; opening mounts one `youtube-nocookie.com/embed/e350wBr1W8c` iframe; closing unmounts it (count 0); the plain `Watch on YouTube` → `https://www.youtube.com/watch?v=e350wBr1W8c` fallback link is present inside the dialog with `target="_blank" rel="noreferrer"`. |
| 12 | Document title and skip link | **pass** | `document.title === "Guidefold \| Team instructions for coding agents"`. First focusable element on the page is `Skip to content → #main`; `#main` has `tabIndex={-1}` (`index.tsx:72`). |
| 13 | Meridian fixture excerpt verbatim + labelled as a fixture | **pass** | Both tabs render all four bullets unchanged. Markdown-source tab reproduces them byte-for-byte including backticks: `` - Tokens are verified with the key set from `libs/auth-sdk`; turnstile never parses JWTs itself. `` … `` never log the token or the resource payload. `` The visible label reads *"`postgres-auth`, from the Meridian example repository in this project. Not a live run."* plus a `Repository source` badge. `qa/review/reader-source-1440x900.png`. |

**Preservation summary: 13 of 13 pass. 0 items where a protected URL, id, form field, FAQ answer or legal string was changed.** Items 2, 3 and 4 were exercised at runtime against a locally stubbed endpoint rather than read from source, so every branch of the join, confirm, unsubscribe, success and four-error paths is verified behaviour, not inferred behaviour. The only caveat anywhere in the table is item 10's header instance at ≤720px, carried as F1 (medium, priority 2) rather than as a preservation breach — reasoning in the verdict.

---

## axe-core summary

axe-core 4.13.0, tags `wcag2a, wcag2aa, wcag21a, wcag21aa, best-practice`, run on the full page at 1440×900.

| Rule | Impact | Nodes | Target | Disposition |
|---|---|---|---|---|
| `color-contrast` | serious | 1 | `._wordmark_1fu2h_196` | **Low** — 1.39:1 (`#232b33` on `#07090c`, 96px). Decorative footer watermark, `aria-hidden="true"`, duplicates the adjacent brand link. See F6. |

**Total violations: 1.** No violations for `aria-*`, `label`, `landmark-*`, `heading-order`, `link-name`, `button-name`, `image-alt`, `frame-title`, `region`, `tabindex` or `color-contrast` on any content text. Manual checks beyond axe: visible focus ring on every stop (F-PASS-6); touch targets — all controls carry `min-height:44px` (`--touch-height`), and the two sub-24px hit areas (the 18×18 consent checkbox and the 19px-tall inline `Privacy` link) are both covered by WCAG 2.5.8 — the checkbox by its 44px-tall wrapping `<label>`, the link by the inline-in-a-sentence exception.

---

## Animation review (`review-animations`)

### Part 1 — Findings table

| Before | After | Why |
| --- | --- | --- |
| `scroll.ts:33` writes `--p` on `.page` (248 descendants) every frame — `useSectionProgress(page)` at `index.tsx:56` | Register the page-level progress on `.field` (2 descendants), whose `.topo`/`.survey` children are `--p`'s only consumers; optionally add `@property --p{syntax:'<number>';inherits:true;initial-value:.5}` | Measured 2.695 ms/frame of `RecalcStyleDuration` vs the brief's 1 ms budget. Textbook "CSS variable on a parent drives a child transform" recalc storm; the four section-level writes are fine, the page-level one is not |
| `landing.module.css:172-174` — `.questionPanel{height:var(--collapsible-panel-height)}` with `transition:height 180ms` | `grid-template-rows:0fr→1fr` on a wrapper, or `clip-path` | Animating a layout property. Idiomatic for Base UI Collapsible and pointer-gated, so low — but it is the one non-GPU transition on the page |
| `button.tsx:7` — `transition-all` in the `cva` base string | Leave as-is; the module override already wins | Verified: computed `transitionProperty` is `background, border-color, color, transform`. Unlayered CSS-module rules beat layered Tailwind utilities. The prohibition is satisfied in effect; the file is hash-pinned and must not be edited |
| `landing.module.css:91-93` — route draws over `(--p - .18)/.44`, completing only at `p ≥ .62` | Compress to roughly `(--p - .10)/.30` so the route resolves while the section is still centred | Measured `dashoffset: 560px` (nothing drawn) at 30% in view and `467.98px` (16%) at 60%. A 64px band stays blank for most of the section's on-screen life; the payoff arrives after the reader has left |
| `landing.module.css:67` — `.heroCopy:focus-within>*{animation:none}` | `animation-play-state:paused`, or transition the same properties so the cancel retargets from the current value | `animation:none` snaps mid-flight rather than easing out. 200 ms, once per load, above the fold — a nit, and the intent (clear the way for a keyboard user immediately) is correct |
| `scroll.ts:31` — `getBoundingClientRect()` read live per element per frame | Cache rects; invalidate on resize, rotation and font/media load | The brief specifies a cached rect. Measured layout cost is only 0.094 ms/frame because the reads are batched ahead of the writes, so this is conformance rather than performance |

### Part 2 — Verdict

**1. Feel-breaking regressions** — none. Nothing uses `ease-in`, nothing enters from `scale(0)`, nothing animates on a keyboard or high-frequency action. Every duration on the page is inside the 300 ms bar: hover/colour 120 ms, tabs indicator and collapsible 180 ms, dialog and hero video fade 240 ms, hero entrance 200 ms with a 120 ms stagger chain (four items at 40 ms — inside the 30–80 ms per-item band and the 300 ms cap). Easing is `cubic-bezier(.23,1,.32,1)` throughout, a genuine custom curve rather than a built-in.

**2. Missed simplifications** — the route rule (F7) is the only motion whose value is questionable, and only because its mapping delays the payoff past the point of usefulness. Retiming is preferable to deleting it. Everything else on the page earns its place; the writer's deletion of the pyramid, beam, shine and fold-film choreography is a large and correct simplification.

**3. Performance** — one finding, F2, quantified above. The rest of the engine is exemplary: one passive `scroll` listener, one passive `resize` listener, one sampler `IntersectionObserver`, rAF coalesced to 0.53 schedules per scroll step, no interval timer, no per-frame React state, no WebGL, and only `transform` and `opacity` scroll-driven, with amplitudes of 16/40/20/12px halved below 720px — all inside the 40px cap.

**4. Interruptibility & timing** — all state motion is CSS transitions rather than keyframes, so it retargets from the current value. The single keyframe animation (`@keyframes enter`) is a one-shot first-paint entrance, which is the correct use of a keyframe. F9 is the one nit.

**5. Origin, physicality & cohesion** — the dialog is centre-origin, which standard 5 explicitly exempts for modals, and it enters `scale(.95) → 1` with opacity rather than from `scale(0)` (`landing.module.css:181-182`). The tabs indicator slides on `transform`+`width` from the real measured position. Motion personality — slow background drift, crisp UI state changes, content that never moves — matches a developer tool and matches the brief's thesis exactly.

**6. Accessibility** — the strongest part of the implementation. Every hover rule is gated behind `@media(hover:hover) and (pointer:fine)` (`landing.module.css:40-44, 109, 136, 199`) with no ungated hover motion anywhere. `:active` press is `scale(var(--press-scale))` = .98 (`:39`) and is disabled under reduced motion (`:210`). Reduced motion is a genuinely complete static composition, not a truncated one (F-PASS-3): durations drop to `--duration-reduced` and colour/opacity survive, movement is removed, and the `[data-p-ready]` mechanism ensures the route rests *drawn* rather than at the 73% its `--p=.5` default would produce. Best detail on the page: `index.tsx:26` sets `data-pointer-motion` on pointer-down and clears it on key-down, so a keyboard-opened FAQ panel gets **no** animation at all while a mouse-opened one does — that satisfies standard 2 more precisely than most production code.

**Decision: Approve on motion craft** (scope: this section only; the page-level verdict is set separately under the binding review priorities, and is also `pass`). **F2 should be fixed before ship.** No feel-breaking regression, no motion that should be deleted outright, durations and easing within bounds, interruptibility handled, reduced motion and hover gating handled properly. F2 is real and measured, but it is a recalc cost with a one-line fix, not a feel problem — and under the binding review priorities a performance finding is priority 5 and a craft objection alone never blocks.

---

## Copy: WHY → HOW → VALUE

**Order: pass.** DOM and visual order are `hero → why (#why) → how-it-works → value (#value) → availability → waitlist → questions → footer`, identical at all four viewports.

**First sentence of each section answers the section's question: pass.** Each carries the `.answer` class, is set at `--landing-lede` in `--stone-100`, and sits immediately under its `h2`:

| Section | h2 | First sentence | Answers it? |
|---|---|---|---|
| WHY | Why we built it | *"A rule for the payments service shouldn't become advice for every task in the monorepo."* | Yes — states the problem concretely, with a real example rather than an abstraction |
| HOW | How it works | *"Rules live in Git next to the code they describe, and Guidefold hands the agent only the few that apply where it is working."* | Yes — the whole mechanism in one sentence |
| VALUE | What your team gets | *"Day to day: a platform team gets one place to keep the rules, an owner gets a review step before anything reaches an agent, and a developer gets the right instruction without asking for it."* | Yes — names all three audiences and what each receives |

**AI-writing signals (report only, no edits).** Scanned the rendered user-facing prose per `avoid-ai-writing/resources/workflow.md`:

| Signal | Count | Note |
|---|---|---|
| Em dashes / en dashes | **0 / 0** | Notably disciplined |
| Negative parallelism (`not just X, it's Y`) | **0** | |
| AI vocabulary (`unlock`, `leverage`, `seamless`, `robust`, `delve`, `landscape`, `realm`, `empower`, `elevate`, `streamline`, `holistic`, `synergy`, …) | **0** | |
| Promotional filler (`powerful`, `effortless`, `world-class`, `industry-leading`, …) | **0** | |
| Leaked chatbot framing, citation tokens, placeholders, cutoff disclaimers, invented sourcing | **0** | |
| Title-case headings, emoji headings, decorative bold, inline-header lists | **0** | Headings are sentence case throughout |
| Repeated template openings / stock transitions / synonym cycling | **0** | Each section opens differently |
| Groups of three | **4** | Three are literal enumerations of real triples (three adapters, three hook steps, three audiences). The fourth (VALUE answer + the three role cards restating it) is the clustering noted in F10 |
| Unsupported notability or hype claims | **0** | The page is unusually careful: "planned", "Tool capabilities differ", "Not a live run", "not a hosted account or a guaranteed launch date". The previously flagged `opt-in proof checks` claim is gone |

**No high-confidence finding remains in editable copy.** The one soft signal (F10) is verbatim from the approved `copy.md` and maps to a real three-audience structure, so it qualifies as an approved-voice exception rather than a defect.

---

## Screenshots

All captures: **`/home/mike/projects/guidefold/ui/qa/review/`**

| File | What it shows |
|---|---|
| `first-360x800.png`, `first-390x844.png`, `first-768x1024.png`, `first-1440x900.png` | First viewport at each required width — note the header nav present at 768/1440 and absent at 360/390 (F1) |
| `full-360x800.png`, `full-390x844.png`, `full-768x1024.png`, `full-1440x900.png` | Full page at each required width |
| `how-30-forward.png`, `how-60.png`, `how-30-reverse.png` | Forward/reverse scroll stability on the HOW section (F-PASS-2) |
| `midpage-reload-1440x900.png` | Refresh from mid-page |
| `reduced-motion-1440x900.png` | `prefers-reduced-motion: reduce`, full page (F-PASS-3) |
| `video-blocked-1440x900.png` | `**/hero-loop.*` aborted — poster holds, no shift (F-PASS-4) |
| `dialog-1440x900.png` | Demo dialog open with the nocookie iframe mounted (F-PASS-5) |
| `faq-deeplink-1440x900.png` | `/#question-2` deep link expanding the pricing answer |
| `reader-source-1440x900.png` | Instruction reader, Markdown-source tab, fixture verbatim |
| `email-confirm-1440x900.png` | `/?confirm=TOKEN` EmailAction branch |
| `waitlist-success-1440x900.png` | Waitlist success state, endpoint stubbed locally (preservation item 2) |
| `focus-trail-1440x900.png` | Keyboard focus ring |
| `mobile-360-hero.png` | 360-wide hero, long-copy and clipping probe |

---

## What the writer owns

The verdict is `pass`; neither item below blocks. Both are narrow and worth doing before ship:

1. **F1** — restore keyboard-reachable `Docs` and `GitHub` in the header at ≤720px, either by keeping the three-link nav visible (they are short) or by adding a disclosure control. If hiding it is deliberate, record it as a deviation in `build-notes.md` so the next review does not re-raise it.
2. **F2** — move the page-level `--p` write from `.page` (248 descendants) to `.field` (2). One line, ~2.7 ms/frame of style recalc recovered.

Everything else is low and optional. Two items to re-verify when the hero loop asset lands: poster-first request ordering (F-PASS-4, third bullet) and headline contrast against the brightest loop frame, which `build-notes.md` also lists as unresolved. Review never patches the page — the selected writer owns repair.
