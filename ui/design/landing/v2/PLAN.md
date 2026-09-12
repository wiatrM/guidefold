# Guidefold landing v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `ui/src/routes/landing/` as the nine-section, film-led v2 landing page specified in `v2/copy.md` and `v2/DESIGN.md`, with scroll entrance motion, Spectrum components where they exist, every protected string verbatim, and only citable evidence on the page.

**Architecture:** One route (`src/routes/landing/index.tsx`) composes nine section components that each own their own `*.module.css`, so tasks are file-disjoint and parallelisable. `FilmBackdrop` keeps the poster-first media contract and gains a piecewise-linear playhead anchor map keyed to measured section offsets. A new `Reveal.tsx` entrance layer over `motion` implements the four patterns P1–P4 with reduced-motion fallback and `once` semantics. All values live in `src/tokens/tokens.css`; Tailwind only inside `src/components/ui` and `src/components/spectrumui`.

**Tech Stack:** React 19, Vite 8, TypeScript, CSS Modules, `motion` 13.2.0, `@base-ui/react` 1.8.0, Phosphor icons, Vitest 5, Playwright 1.63, axe-core 4.13, pnpm 10.

**Spec:** `ui/design/landing/v2/` — `value-brief.md` (what we sell), `copy.md` (every string, protected map, the build rule), `DESIGN.md` (composition, tokens, P1–P4, playhead ranges, performance/accessibility contract, anti-slop gate), `components.md` (registry scouting inventory and check-contracts constraints). Read `copy.md` and `DESIGN.md` §3 for your section before implementing it.

**Branch:** `landing/why-how-value`. All paths below are relative to the repo root `/home/mike/projects/guidefold` unless they start with `ui/`, in which case commands run from `ui/`.

---

## Global Constraints

Every task's requirements implicitly include this section. These are binding controller rulings plus the spec's own contract; do not reopen them.

### Binding controller rulings (2026-09-11)

1. **Entrance motion is required.** The owner verdict overrides the old "no section reveals" / "no scroll-triggered content motion" / "nothing exceeds 240 ms" rules in `ui/src/routes/landing/DESIGN.md`. The background film stays: `FilmBackdrop`, poster first with `fetchpriority="high"`, conditional video mount, and **reduced motion and Save-Data render posters only and create no video element**.
2. **Protected strings survive verbatim.** Source of truth: `preservationMap` in `ui/design/landing/design-brief.json`, summarised in `ui/design/landing/DESIGN.md` §2 and in `v2/copy.md` §4. Repositioning is allowed; rewording, re-punctuating and summarising are not. **Move the existing JSX nodes out of `index.tsx` rather than retyping them** — the curly apostrophes in `You’re all set.` and `You’ve been unsubscribed from the Guidefold waitlist.` are contractual and a transcription typo is the most likely way this rebuild breaks preservation.
3. **Citable evidence, complete list.** Only these may appear on the page:
   - `0/76` harmful loaded (written as "76 of 76 harmful rules refused" / "ASK for all 76 harmful mutations"), the flat control loading all 76, and the one-sided Wilson 95% upper bound **4.81%**.
   - `4/4` safe cases LOAD, and `4/4` through the production USE 1.2 HTTP path with `reason=source_proof_complete`, source hash and range verified by the service.
   - Source for both: `docs/RESEARCH.md` §5.30 and §5.32 on branch `origin/codex/e2-proof-gate-matrix-20260910`, dated **2026-09-11**, label **`delivery boundary, not task success`**.
   - `+8.53 pp Recall@10` on SRA-Bench, 5,400 queries over 26,262 skills, from `ui/src/data/research-evidence.json`, 10 September 2026, status *measured, exploratory offline retrieval*.
   - Task 1 mirrors the two proof-gate rows into `ui/src/data/research-evidence.json` with source path, date and label.
   - **Nothing else is citable.** Specifically forbidden anywhere on the page, including in a softened form: the E6.7 replay (17/20 vs 16/20), `25/25` hierarchical SEARCH requests, and any latency figure for the 30k corpus.
4. **Film re-encode** (Task 3): `public/assets/landing/hero-flight.mp4` and `.webm` re-encoded with `-g 12`, same resolution, similar bitrate. `ffmpeg` is at `/usr/bin/ffmpeg`. Posters unchanged.
5. **`backdrop-filter` only over the static poster.** At most one blurred surface per viewport. Implemented as the token swap in `DESIGN.md` §2.4: `:root{--glass-blur:14px}` / `[data-film="on"]{--glass-blur:0px}`.
6. **The extraction chapter may split `copy.md` sentences across beats verbatim.** No rewording.
7. **Commits stage only landing-scoped paths, by explicit path.** Never `git add -A`, never `git add .`. The branch carries ~137 unrelated dirty files that must not be touched or committed. The git guard hook blocks commits on `main` and pattern-matches git commands inside heredocs: write commit messages with `git commit -m "…"` or `git commit -F <file>`, never a heredoc containing git lines.
8. **Spectrum is mandatory where a suitable component exists**; `@magicui` / `@aceternity` for the recorded gaps; handmade `motion` last. Every installed registry file gets a provenance entry in `ui/qa/spectrum-registry.json` (`file`, `sha256`, `source`, `allowInlineGeometry`) so `node qa/check-contracts.mjs` passes. **Installs must not overwrite `src/components/ui/button.tsx`** (hash-pinned, MIT base-nova adaptation). Dry-run every install; no `--all`, no `--overwrite`.
9. **`src/tokens/tokens.css` is the only place values live.** No hex, no literal dimension, no literal zero length, no literal font-weight or line-height in any CSS module or inline `style={{}}`. No custom property declared outside `tokens.css`. No literal breakpoint in a module media query — redefine tokens inside the existing `@media(max-width:1080px)` and `@media(max-width:720px)` blocks. Tailwind utilities are allowed **only** inside `src/components/ui` and `src/components/spectrumui`.

### Structural constraints from the codebase

- **New landing components go in `src/routes/landing/`.** `src/components/` outside `ui/` and `spectrumui/` is a fixed allowlist of exactly 15 directories (`ActionButton`, `BrandMark`, `Panel`, `StateBadge`, `RouteState`, `Tabs`, `ProvenanceTrail`, `ScopeTree`, `DataTable`, `SkillDiff`, `MetricRow`, `Urn`, `SkillContent`, `Field`, `PyramidChart`). A 16th directory fails `component-count`. Registry installs land in `src/components/spectrumui/`.
- **Route files may import `src/data/*.json` directly.** The `data-boundary` check traverses only from the 15 component roots and `src/domain/**`. `ResearchEvidence.tsx` already does `import evidence from '../../data/research-evidence.json'`; the hero proof rail does the same.
- Each section owns its own `*.module.css` under `src/routes/landing/`, so section tasks are file-disjoint. Do not add section styles to `landing.module.css`; it keeps only page chrome (page, skip, nav, film, dialog, footer, waitlist form internals) plus whatever a task explicitly says.

### Performance and accessibility contract (DESIGN.md §5, verbatim obligations)

| Item | Contract |
|---|---|
| LCP | `hero-poster.webp`, `fetchpriority="high"`, 1920×1080, 126 KB, ≤ 2.0 s throttled 4G. No new element may paint above it; no font, script or ticker may block it. P4 never runs inside the LCP window — the hero proof rail renders final values in the base DOM. |
| CLS | **0.** Every media slot carries intrinsic `width`/`height` or an aspect-ratio box; the pinned stage reserves `--landing-stage-height` before enhancement; the chart tile has a minimum-height token; no font swap moves layout. |
| JS budget | **≤ +34 KB gzipped** on the landing route chunk over today's build. Record before/after in `docs/reports/readme/build-notes.md`. No new runtime dependency. |
| Frame budget | Main-thread work **< 4 ms/frame** during a full scroll pass, **zero long tasks**. One rAF, one passive scroll listener, one resize listener, one `IntersectionObserver` for the whole page. No `getBoundingClientRect` outside the batched sampler. `transform`/`opacity` only. `will-change` on the film layer and the pinned stage only. **No `content-visibility: auto`.** No `backdrop-filter` while `[data-film="on"]`. |
| Focus order | Equals DOM order equals visual order at every breakpoint. **No CSS `order` anywhere.** All three pinned beats are in the DOM and reachable. |
| Contrast over film | Body ≥ 4.5:1, large text ≥ 3:1, hero display ≥ 7:1, measured against the brightest sampled frame inside each copy-safe region (sample at the §3.0 anchors and at the sunrise window, 0.0–1.4 s). |
| Targets | 44 px minimum for every control at 720, including the consent checkbox row and the FAQ triggers. |
| Keyboard | Skip link → header → hero actions → demo dialog (focus trap and restore) → waitlist form → FAQ triggers → footer. The film is `aria-hidden` and unreachable. |
| Axe | Clean at 1440 and 390, with the FAQ closed and open and with the dialog open. |
| Reduced motion | Static composition, no video element created, no sampler installed, ticker renders final value, route renders complete. |

### Anti-slop gate (DESIGN.md §6, enforced by Task 13)

Banned on this page: gradient text or a differently coloured/weighted word inside a headline; a row of three identical cards; glow blobs, mesh gradients, radial aurora; stock icons in circles, an icon per feature, emoji as icons; all-caps tracked eyebrow above a heading; a `→` glued to link or button text (directional glyphs are icon elements with `aria-hidden`, on the **two primary actions only** — today's `Try the open-source version <ArrowUpRight/>` and `Read the numbers…` links lose their icons); meta strings joined with middle dots; glass on anything that is not a real instrument; more than two radii (`--landing-radius` 8 px, `--landing-radius-panel` 16 px); a number without its denominator, date or status word; "zero risk", "no unsafe deliveries ever", "100% safe", any rounding of 76; the seven banned words in `docs/ui/UX.md` §6; reflexive rule of three; anonymous "research shows"; "it is not X, it is Y"; em-dash chains. Standing bans that survive: 3D pyramid, WebGL hero atmosphere, schema-flow canvas, autoplaying feature demos, typewriter, shine sweep, per-word text reveals, `MorphButton` on this page, any new dependency, any new font fetch, any new icon library.

### Verification commands (from `ui/package.json`)

```
cd ui
pnpm typecheck          # tsc --noEmit
pnpm build              # tsc --noEmit && vite build
pnpm test               # vitest run
pnpm test:contracts     # node qa/check-contracts.mjs
pnpm test:e2e           # playwright test   (after: pnpm exec playwright install chromium)
pnpm test:visual        # node qa/compare-gallery.mjs   — never regenerate the baseline to accept a change
```

---

## Pre-flight conflict table

### Contradictions found across the four spec files, and their resolution

Resolution order: controller rulings win; otherwise `DESIGN.md` wins on layout and `copy.md` wins on words.

| # | Conflict | Resolution |
|---|---|---|
| 1 | `DESIGN.md` §3.3 specifies two mono proof figures under the retrieval instrument: `25/25` hierarchical SEARCH with no 422, and `4/4` source proof complete. `copy.md` §1 rules `25/25` **"Must not appear on the page in any form, including a softened one"**, §3 lists its removal, and ruling 3 omits it. | Ruling 3 + `copy.md` win. **The retrieval section ships no proof figures at all** — only the microcopy line "Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here." The `4/4` figure lives in the proof-gate section (Task 9) where `copy.md` puts it. `@spectrumui/number-ticker` therefore has no consumer in §3.3; it is installed for the evidence bento only (Task 10). |
| 2 | Proof-rail cell count: `copy.md` §2 §1 and `DESIGN.md` §3.1 both specify **two** cells; `DESIGN.md` §7 decision 9 says **four**, adding a `≤ 4` cards figure that is not in the citable set. | `DESIGN.md` contradicts itself; `copy.md` wins on words. **Two cells.** |
| 3 | The status label: ruling 3 summarises it as "delivery boundary, not task success"; `copy.md` §1 fixes it verbatim and says it is never shortened. | `copy.md` wins. The string is exactly **`Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.`**, in full, at every breakpoint, under both proof-gate figures and under the hero safety figure. |
| 4 | `components.md` is a **scouting inventory** ("No installs were run") and recommends items `DESIGN.md` rejects by name: Orbital Letters (§7 decision 4), FAQ Tabs Card (§3.9), Status Tracker (§3.5), marquee (§4.6), border-beam on data (§3.3), hover lift on bento tiles (§4.6). Shimmer Button collides with the standing shine-sweep ban. Testimonials collide with `copy.md` §6's fabrication check. | `DESIGN.md` wins. **Sanctioned installs are exactly two: `@spectrumui/bento-grid` and `@spectrumui/number-ticker`.** Every other item is a recorded Spectrum exception in the change description. |
| 5 | The pinned extraction stage: `components.md` "Sticky scroll reveal: not found in any registry" → handmade (`DESIGN.md` §3.2 records the exception), but `components.md`'s later `@magicui`/`@aceternity` pass recommends `@aceternity/sticky-scroll-reveal` and ruling 8 puts registry before handmade. | Not resolved by fiat. **Task 7 begins with a dry-run and a source read of `@aceternity/sticky-scroll-reveal`**, checked against the §5 frame budget, CLS 0 and reversibility. Hand-build with a written exception only if it fails those. |
| 6 | Eyebrow: `DESIGN.md` §2.1 retires the eyebrow from this page; §3 reinstates four of them as copy. | §3 is the later, copy-driven form and wins. Eyebrows render as **sentence-case JetBrains Mono at `--font-size-code`, `--landing-tracking-mono`, colour `--steel`, preceded by a 12 px hairline** — never uppercase, never tracked out. The hero has no eyebrow. |
| 7 | Evidence section heading: `ResearchEvidence.tsx` renders `<h2 id="research-title">More relevant skills found</h2>` and the e2e locates the region by that accessible name; `copy.md` §6 gives the headline "Plus 8.53 points of recall over flat." | `copy.md` wins on words. The `h2` text changes; the chart, table, interval paragraphs, Pi trace and `<details>` block below it are untouched. Task 12 retargets the e2e region locator. |
| 8 | `DESIGN.md` §4.4 lists `--enter-blur` and `--enter-scale` only in their reduced-motion zeros; §4.1 P3 implies `3px` and `.985`. | Task 1 declares both base values explicitly, or P3 silently resolves to nothing. |

### Task pairs that share a file or an interface

| Producer → Consumer | Shared file / interface | What passes across |
|---|---|---|
| T1 → T4, T5, T7–T11 | `ui/src/tokens/tokens.css` | Every new token name and value. T1 is the **only** task that edits `tokens.css`; a later task needing a token adds it in its own commit and says so in the commit message. |
| T1 → T13 | `docs/reports/readme/build-notes.md` | The pre-change landing-chunk gzip baseline. T13 computes the `+34 KB` delta from it instead of stashing the branch's dirty tree. |
| T1 → T5, T9 | `ui/src/data/research-evidence.json` | The `proof_gate` block (76/4/4.81%) with path, date and label. T5's hero rail and T9's proof lines both read it; if the block is absent the hero ships one cell and T9 runs on prose (`copy.md` §5 empty-state row). |
| T2 → T10 | `src/components/spectrumui/bento-grid.tsx`, `bento-card.tsx`, `spotlight.tsx`, `border-beam.tsx`, `lib/ease.ts`, `number-ticker.tsx`; `ui/qa/spectrum-registry.json` | Exact exported component names, read from the installed source and recorded in T2's commit message. |
| T3 → T13 | `public/assets/landing/hero-flight.{mp4,webm}` | New files in place, dimensions and duration unchanged. |
| T4 → T5, T7–T11 | `ui/src/routes/landing/Reveal.tsx` | `<Reveal pattern="p1"|"p2"|"p3" as={…} stagger={n}>`, `<RevealGroup>`, `useReveal()`. Exact signatures in T4's Interfaces block. |
| T5 → T6 | Nine section `id` strings | `hero`, `extraction`, `how-it-works`, `proof-gate`, `telemetry`, `research-results`, `availability`, `waitlist`, `questions`. T6's anchor map keys on these exact strings. |
| T5 → T7–T11 | `ui/src/routes/landing/index.tsx` section slots | T5 creates every section component file as a minimal shell that renders its heading and `id`; T7–T11 fill them in. `index.tsx` is **not** edited again after T5. |
| T5 → T12 | Protected JSX nodes moved, not retyped | FAQ answers, availability statements and waitlist strings move from `index.tsx` into `Questions.tsx` / `Availability.tsx` unchanged. |
| T3, T6 → T13 | Film scrub behaviour | Keyframe density and the anchor map together determine whether beats land; T13's screenshot pass is the check. |

### Task order and parallel groups

| Group | Tasks | Notes |
|---|---|---|
| **A** (parallel, no deps) | T1, T2, T3 | Disjoint: tokens+data / registry+registry.json / binary assets. |
| **B** (after A) | T4 | Needs T1's motion tokens. |
| **C** (after B) | T5 | Needs T1 and T4. Creates `index.tsx` and every section shell. |
| **D** (parallel, after C) | T6, T7, T8, T9, T10, T11 | File-disjoint: each owns one `*.tsx` + one `*.module.css`; T6 owns `FilmBackdrop.tsx` + `scroll.ts`. T10 also needs T2. |
| **E** (after D) | T12 | Tests against the finished page. |
| **F** (after E) | T13 | QA gate and the implemented-system record. |

---

## Task 1: Tokens and the evidence mirror

**Model tier: standard.** Mechanical values, but the reduced-motion and breakpoint blocks must stay consistent and the evidence mirror carries a citation contract.

**Parallel group: A** (with T2, T3).

**Implements:** `DESIGN.md` §2.1, §2.2, §2.3, §2.4, §4.1, §4.4; controller ruling 3.

**Files:**
- Modify: `ui/src/tokens/tokens.css` (the `:root` landing block starting at the `Landing v2` comment, plus the `@media(max-width:1080px)`, `@media(max-width:720px)` and `@media(prefers-reduced-motion:reduce)` blocks)
- Modify: `ui/src/data/research-evidence.json`
- Modify: `docs/reports/readme/build-notes.md` (the pre-change JS baseline)
- Test: `ui/src/routes/landing/evidence.test.ts` (create)

**Interfaces:**
- Produces: every token name below, the `proof_gate` block in `research-evidence.json`, and the pre-change landing-chunk gzip baseline that T13 computes its `+34 KB` delta against.
- Consumes: nothing.

- [ ] **Step 1: Record the pre-change JS baseline**

Before touching anything, capture the landing route chunk's gzip size on unchanged code, so T13 can compute the `+34 KB` delta without a `git stash` round trip over the branch's ~137 unrelated dirty files:

```bash
cd ui && pnpm build
cd ui && ls -l dist/assets | grep -i landing
cd ui && gzip -c dist/assets/<landing-chunk>.js | wc -c
```

Append to `docs/reports/readme/build-notes.md`, under a dated `Landing v2 JS budget` heading: the chunk filename, its raw and gzip bytes, the date, and the line `Budget: +34 KB gzipped (DESIGN.md v2 §5). After-figure recorded by the landing v2 QA gate task.` Stage that file with this task's commit.

- [ ] **Step 2: Read the current landing token block**

Read `ui/src/tokens/tokens.css` from the `Landing v2` comment to the end. Note that `--landing-heading`, `--landing-body`, `--landing-copy-width`, `--landing-film-opacity`, `--landing-radius`, `--landing-section-padding` already exist and are referenced by `landing.module.css`. Those are **value changes in place**, not renames. `--landing-enter-rise`, `--landing-enter-duration`, `--landing-enter-delay-1..4` also already exist and are consumed today; **leave them declared** — the new names below do not collide.

- [ ] **Step 3: Edit the existing token values in place**

In the `:root` landing block:

```
--landing-heading:clamp(30px,3.2vw,46px);
--landing-body:17px;
--landing-copy-width:46ch;
--landing-film-opacity:.86;
--landing-section-padding:clamp(104px,9vw,168px);
```

- [ ] **Step 4: Add the new typography tokens**

```
--landing-display:clamp(46px,6.4vw,92px);
--landing-display-leading:1.02;
--landing-display-tracking:-.035em;
--landing-kicker:clamp(19px,1.5vw,23px);
--landing-kicker-measure:34ch;
--landing-h3:20px;
--landing-metric:clamp(34px,3.4vw,52px);
--landing-metric-leading:1;
--landing-metric-unit:16px;
--landing-tracking-mono:.04em;
--landing-eyebrow-rule:12px;
```

- [ ] **Step 5: Add the colour, material and scrim tokens**

```
--film-scrim-hero:linear-gradient(100deg,rgba(7,9,12,.94) 0%,rgba(7,9,12,.8) 34%,rgba(7,9,12,.1) 66%,rgba(7,9,12,0) 100%);
--film-scrim-chapter:radial-gradient(120% 90% at 30% 55%,rgba(7,9,12,.86) 0%,rgba(7,9,12,.52) 48%,rgba(7,9,12,.24) 100%);
--film-scrim-band:linear-gradient(180deg,rgba(7,9,12,.58) 0%,rgba(7,9,12,.86) 100%);
--glass-panel:rgba(12,16,20,.62);
--glass-panel-strong:rgba(12,16,20,.86);
--glass-blur:14px;
--glass-ground:var(--glass-panel);
--glass-border:rgba(163,173,182,.16);
--glass-highlight:linear-gradient(180deg,rgba(238,241,243,.06),rgba(238,241,243,0) 38%);
--glow-route:0 0 0 1px rgba(255,122,61,.24),0 14px 44px -20px rgba(255,122,61,.45);
--glow-system:0 0 0 1px rgba(63,184,177,.2),0 14px 44px -22px rgba(63,184,177,.4);
--tier-1:rgba(63,184,177,.26);
--tier-2:rgba(63,184,177,.2);
--tier-3:rgba(63,184,177,.14);
--tier-4:rgba(63,184,177,.09);
```

- [ ] **Step 6: Add the film-running material swap**

Immediately after the landing `:root` block, add:

```
[data-film="on"]{--glass-blur:0px;--glass-ground:var(--glass-panel-strong);}
```

This is ruling 5: real blur appears only over the static poster.

- [ ] **Step 7: Add the spacing, grid and stage tokens**

```
--landing-band-gap:clamp(32px,3.2vw,56px);
--landing-panel-pad:clamp(20px,2vw,32px);
--landing-bento-gap:12px;
--landing-stage-height:100dvh;
--landing-stage-scroll:260vh;
--landing-measure-gutter:clamp(24px,6vw,120px);
--landing-radius-panel:16px;
--landing-chart-min-height:280px;
--landing-tier-glyph-height:96px;
```

- [ ] **Step 8: Add the motion tokens**

```
--duration-entrance:420ms;
--duration-draw:520ms;
--duration-panel:360ms;
--duration-count:900ms;
--ease-entrance:cubic-bezier(.16,1,.3,1);
--stagger-entrance:60ms;
--stagger-cap:240ms;
--stagger-panel:70ms;
--stagger-count:40ms;
--enter-rise:12px;
--enter-blur:3px;
--enter-scale:.985;
--parallax-panel:12px;
--parallax-chapter:32px;
--film-lerp:.14;
```

`--enter-blur` and `--enter-scale` base values are conflict-table row 8: without them P3 resolves to nothing.

- [ ] **Step 9: Update the 1080 breakpoint block**

Inside the existing `@media(max-width:1080px){:root{ … }}` landing block, add:

```
--landing-stage-height:auto;
```

(The pin is above 1080 only, `DESIGN.md` §7 decision 3.)

- [ ] **Step 10: Update the 720 breakpoint block**

Inside the existing `@media(max-width:720px){:root{ … }}` landing block, change/add:

```
--landing-film-opacity:.7;
--landing-display:clamp(34px,9vw,46px);
--landing-section-padding:72px;
--landing-band-gap:24px;
--landing-panel-pad:16px;
--landing-bento-gap:10px;
--landing-measure-gutter:0px;
--landing-stage-height:auto;
--parallax-panel:6px;
--parallax-chapter:16px;
--landing-tier-glyph-height:96px;
```

- [ ] **Step 11: Extend the reduced-motion block**

Replace `@media(prefers-reduced-motion:reduce){:root{--transparent:transparent;--duration:0ms;}}` with:

```
@media(prefers-reduced-motion:reduce){:root{
 --transparent:transparent;--duration:0ms;
 --duration-entrance:0ms;--duration-panel:0ms;--duration-draw:0ms;--duration-count:0ms;
 --enter-rise:0px;--enter-blur:0px;--enter-scale:1;
 --parallax-panel:0px;--parallax-chapter:0px;
 --landing-stage-height:auto;
}}
```

- [ ] **Step 12: Mirror the proof-gate evidence into the data file**

Add a top-level `proof_gate` key to `ui/src/data/research-evidence.json`, after `pi` and before `limitations`. Values are ruling 3 and were read from `docs/RESEARCH.md` §5.30 / §5.32 on `origin/codex/e2-proof-gate-matrix-20260910`:

```json
"proof_gate": {
  "date": "2026-09-11",
  "branch": "codex/e2-proof-gate-matrix-20260910",
  "label": "delivery boundary, not task success",
  "microcopy": "Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.",
  "matrix": {
    "harmful_mutations": 76,
    "harmful_asked": 76,
    "harmful_loaded": 0,
    "safe_cases": 4,
    "safe_loaded": 4,
    "flat_control_loaded": 76,
    "wilson_upper_bound_pct": 4.81,
    "source": "docs/RESEARCH.md#530-source-backed-e2-delivery-matrix",
    "reproduce": "research/e2-source-backed-20260911/README.md"
  },
  "http_path": {
    "targets": 4,
    "loaded": 4,
    "reason": "source_proof_complete",
    "handler": "USE 1.2",
    "service_verified": "source hash and range",
    "source": "docs/RESEARCH.md#532-source-backed-e2-through-the-go-http-path",
    "reproduce": "research/e2-source-backed-http-20260911/README.md"
  }
}
```

Do not touch any other key in the file.

- [ ] **Step 13: Write the failing test**

Create `ui/src/routes/landing/evidence.test.ts`:

```ts
import {describe,it,expect} from 'vitest';
import evidence from '../../data/research-evidence.json';

describe('citable evidence contract',()=>{
 it('mirrors the proof-gate matrix with its source, date and label',()=>{
  const gate=evidence.proof_gate;
  expect(gate.date).toBe('2026-09-11');
  expect(gate.label).toBe('delivery boundary, not task success');
  expect(gate.microcopy).toBe('Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.');
  expect(gate.matrix.harmful_mutations).toBe(76);
  expect(gate.matrix.harmful_loaded).toBe(0);
  expect(gate.matrix.flat_control_loaded).toBe(76);
  expect(gate.matrix.wilson_upper_bound_pct).toBe(4.81);
  expect(gate.matrix.source).toContain('docs/RESEARCH.md');
  expect(gate.http_path.loaded).toBe(4);
  expect(gate.http_path.reason).toBe('source_proof_complete');
 });

 it('keeps the retrieval figure and its denominators intact',()=>{
  expect(evidence.vs_flat.recall10.delta_pp).toBeCloseTo(8.527,3);
  expect(evidence.queries).toBe(5400);
  expect(evidence.skills).toBe(26262);
  expect(evidence.date).toBe('2026-09-10');
 });
});
```

- [ ] **Step 14: Run the tests**

Run: `cd ui && pnpm test -- evidence` — expect both to PASS (the data was written in step 11). Then `pnpm test:contracts` — expect `"result": "passed"`.

- [ ] **Step 15: Commit**

```bash
git add ui/src/tokens/tokens.css ui/src/data/research-evidence.json ui/src/routes/landing/evidence.test.ts docs/reports/readme/build-notes.md
git commit -m "feat(landing): add v2 design tokens and mirror the proof-gate evidence"
```

---

## Task 2: Registry installs and provenance

**Model tier: standard.** Two installs, but each needs a source read, a collision check against the pinned Button, and a hash entry.

**Parallel group: A** (with T1, T3).

**Implements:** `DESIGN.md` §7 decisions 6 and 7; `components.md` "Constraints the implementer must respect"; ruling 8.

**Files:**
- Create: `ui/src/components/spectrumui/bento-grid.tsx`, `bento-card.tsx`, `spotlight.tsx`, `border-beam.tsx` (whatever paths the install writes)
- Create: `ui/src/components/spectrumui/number-ticker.tsx` and its `lib/ease.ts`
- Modify: `ui/qa/spectrum-registry.json`
- Modify: `ui/public/licenses/spectrum-ui.txt` if the install adds a notice

**Interfaces:**
- Produces: the exact exported names of the bento, card, spotlight and ticker components, recorded in the commit message; provenance entries in `spectrum-registry.json`.
- Consumes: nothing.

- [ ] **Step 1: Record the pre-install state**

Run:

```bash
cd ui && git status --porcelain src/components/spectrumui qa/spectrum-registry.json src/components/ui/button.tsx
sha256sum src/components/ui/button.tsx
```

The Button hash must be `d321f83520e6ffd1db6cba664ae580a379d70acc7f34991578d2a546b62446b1` before and after every install. If it changes, revert the file and re-run the install without the colliding dependency.

- [ ] **Step 2: Dry-run the bento grid install**

Run: `cd ui && pnpm dlx shadcn@latest add @spectrumui/bento-grid --dry-run` (if the flag is unsupported, use `--help` to find the equivalent, or fetch `https://ui.spectrumhq.in/r/bento-grid.json` and read the file list). Record the file list and `registryDependencies`. Refuse any overwrite of `src/components/ui/button.tsx`.

- [ ] **Step 3: Install the bento grid**

Run: `cd ui && pnpm dlx shadcn@latest add @spectrumui/bento-grid`. Do not pass `--all` or `--overwrite`.

- [ ] **Step 4: Read every installed file**

Read each written file in full. Check for: Next.js/RSC-only APIs (`next/`, `"use server"`), remote asset fetches, `next-themes`, literal colours in inline `style={{}}` objects. Per `DESIGN.md` §7 decision 6, `border-beam.tsx` ships with this install and is **left unused on this page**; keep it installed (it is a registry dependency) but import it nowhere in `src/routes/landing/`.

- [ ] **Step 5: Install the number ticker**

Run: `cd ui && pnpm dlx shadcn@latest add @spectrumui/number-ticker`. Read the source. Per `DESIGN.md` §7 decision 7: if it carries **literal colours** rather than only geometry, delete it and hand-build a twenty-line per-digit roll in `src/routes/landing/NumberTicker.tsx` instead, with `font-variant-numeric: tabular-nums` and a `--duration-count` transition; record the exception in the commit message. If it carries only rolling geometry, keep it and set `allowInlineGeometry: true`.

- [ ] **Step 6: Add provenance entries**

For every file written by both installs, append an entry to the `components` array in `ui/qa/spectrum-registry.json`:

```json
{
  "file": "src/components/spectrumui/bento-grid.tsx",
  "sha256": "<sha256sum of the file>",
  "source": "https://ui.spectrumhq.in/r/bento-grid.json",
  "allowInlineGeometry": false
}
```

Compute each hash with `sha256sum <file>`. Set `allowInlineGeometry: true` only on files that genuinely need inline geometry (the ticker's rolling digits; `spotlight.tsx` if it writes measured pointer coordinates inline). Bump `reviewedAt` to `2026-09-11`.

- [ ] **Step 7: Verify the contract checker**

Run: `cd ui && pnpm test:contracts`. Expect `"result": "passed"` and no `registry-review`, `token-value`, `inline-style`, `component-count` or `component-name` diagnostics. A `registry-review` diagnostic means a hash is wrong; recompute it. A `token-value` diagnostic on an installed `.css` or inline style means the file needs `allowInlineGeometry: true` **and** a written justification in the commit message, or it must not be installed.

- [ ] **Step 8: Verify the build and the Button**

Run: `cd ui && pnpm typecheck && sha256sum src/components/ui/button.tsx`. Typecheck must pass; the Button hash must be unchanged.

- [ ] **Step 9: Commit**

Include in the message the exact exported component names T10 will import.

```bash
git add ui/src/components/spectrumui ui/qa/spectrum-registry.json ui/public/licenses/spectrum-ui.txt ui/package.json ui/pnpm-lock.yaml
git commit -m "feat(landing): install the Spectrum bento grid and number ticker with provenance"
```

If `package.json` / `pnpm-lock.yaml` were not touched by the install, drop them from the `git add` line rather than staging unrelated changes.

---

## Task 3: Re-encode the film with denser keyframes

**Model tier: cheap.** Fully mechanical; the spec fixes every value.

**Parallel group: A** (with T1, T2).

**Implements:** ruling 4; `DESIGN.md` §7 decision 1.

**Files:**
- Modify: `ui/public/assets/landing/hero-flight.mp4`
- Modify: `ui/public/assets/landing/hero-flight.webm`
- Create: `ui/qa/film-keyframes.json`

**Interfaces:**
- Produces: the two re-encoded files and a before/after keyframe record.
- Consumes: nothing.

**Measured input, 2026-09-11** (put these in the record so "similar bitrate" is checkable): `hero-flight.mp4` is H.264, 1280×720, 24/1 fps, duration 10.041667 s, bit rate 1 838 914 b/s, 2.2 MB, 21 I-frames, maximum inter-keyframe gap 0.5 s. The WebM is 2.1 MB. Posters are **not** touched.

- [ ] **Step 1: Record the before state**

```bash
cd ui/public/assets/landing
/usr/bin/ffprobe -v error -select_streams v -show_entries frame=pict_type,pts_time -of csv=p=0 hero-flight.mp4 \
 | awk -F, '$2=="I"{n++;if(p!=""){g=$1-p;if(g>m)m=g}p=$1}END{print "mp4 I-frames:",n,"max gap:",m}'
/usr/bin/ffprobe -v error -select_streams v -show_entries frame=pict_type,pts_time -of csv=p=0 hero-flight.webm \
 | awk -F, '$2=="I"{n++;if(p!=""){g=$1-p;if(g>m)m=g}p=$1}END{print "webm I-frames:",n,"max gap:",m}'
/usr/bin/ffprobe -v error -show_entries format=duration,bit_rate,size -show_entries stream=codec_name,width,height,r_frame_rate -of default=nw=1 hero-flight.mp4
```

Write the output into `ui/qa/film-keyframes.json` under a `before` key.

- [ ] **Step 2: Back up the originals**

```bash
cd ui/public/assets/landing && cp hero-flight.mp4 /tmp/hero-flight.mp4.bak && cp hero-flight.webm /tmp/hero-flight.webm.bak
```

- [ ] **Step 3: Re-encode the MP4**

```bash
cd ui/public/assets/landing
/usr/bin/ffmpeg -y -i /tmp/hero-flight.mp4.bak -an -c:v libx264 -g 12 -keyint_min 12 -sc_threshold 0 \
  -b:v 1840k -maxrate 2200k -bufsize 3680k -pix_fmt yuv420p -movflags +faststart hero-flight.mp4
```

`-sc_threshold 0` forces an even GOP rather than scene-cut placement. `-an` because the film has no audio track and must not gain one.

- [ ] **Step 4: Re-encode the WebM**

```bash
cd ui/public/assets/landing
/usr/bin/ffmpeg -y -i /tmp/hero-flight.webm.bak -an -c:v libvpx-vp9 -g 12 -keyint_min 12 \
  -b:v 1700k -deadline good -cpu-used 2 -pix_fmt yuv420p hero-flight.webm
```

- [ ] **Step 5: Record the after state and verify the invariants**

Re-run every command from step 1 and write the output under an `after` key in `ui/qa/film-keyframes.json`. Assert, by reading the output:
- width 1280, height 720, `r_frame_rate` 24/1, duration within 0.05 s of 10.041667 for **both** files;
- MP4 bit rate within ±25% of 1 838 914 b/s;
- I-frame count ≥ 21 and maximum inter-keyframe gap ≤ 0.5 s for both files.

If the maximum gap did not shrink, say so plainly in the record and in the commit message — the input already measured 0.5 s, so `-g 12` may be close to a no-op here. Do not change `-g` to compensate; ruling 4 fixes it.

- [ ] **Step 6: Verify in the browser**

Run `cd ui && pnpm dev`, open `http://127.0.0.1:4331/`, scroll top to bottom and back, and confirm the film still decodes and scrubs. Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add ui/public/assets/landing/hero-flight.mp4 ui/public/assets/landing/hero-flight.webm ui/qa/film-keyframes.json
git commit -m "perf(landing): re-encode the survey film at -g 12 for precise scrubbing"
```

---

## Task 4: The entrance layer (P1–P4)

**Model tier: capable.** The `once` semantics, the resting-state discipline and the reduced-motion fallback are where this goes wrong silently.

**Parallel group: B** (after T1).

**Implements:** `DESIGN.md` §4.1, §4.4; §5 frame budget.

**Files:**
- Create: `ui/src/routes/landing/Reveal.tsx`
- Create: `ui/src/routes/landing/reveal.module.css`
- Create: `ui/src/routes/landing/Reveal.test.tsx`

**Interfaces:**
- Consumes: motion tokens from T1 (`--duration-entrance`, `--duration-draw`, `--duration-panel`, `--ease-entrance`, `--stagger-entrance`, `--stagger-cap`, `--stagger-panel`, `--enter-rise`, `--enter-blur`, `--enter-scale`).
- Produces, imported by T5 and T7–T11:

```ts
export type RevealPattern='p1'|'p2'|'p3';
export function Reveal(props:{
  pattern:RevealPattern;
  as?:keyof JSX.IntrinsicElements;   // default 'div'
  index?:number;                     // stagger slot, 0-based; capped at 4
  className?:string;
  id?:string;
  children:React.ReactNode;
}):JSX.Element;
export function RevealGroup(props:{
  pattern:RevealPattern;
  as?:keyof JSX.IntrinsicElements;
  className?:string;
  children:React.ReactNode;          // each direct child becomes a staggered slot
}):JSX.Element;
/**
 * The hero headline treatment: DESIGN.md 4.1 P1's per-line clip-path mask, chosen
 * over @spectrumui/orbital-letters in 7 decision 4. Splits `text` on the supplied
 * line breaks, wraps each line in a masked <span>, staggers them, and keeps the
 * element's accessible name equal to the whole sentence.
 */
export function RevealLines(props:{
  as?:keyof JSX.IntrinsicElements;   // default 'h1'
  id?:string;
  className?:string;
  lines:readonly string[];           // at most three; DESIGN.md 2.1
  label?:string;                     // accessible name; defaults to lines.join(' ')
}):JSX.Element;
export function useRevealed(ref:React.RefObject<HTMLElement|null>,threshold?:number):boolean;
```

**Base-state discipline, non-negotiable:** every element's **resting state is its final state**. The entrance CSS applies only to elements carrying `data-reveal-ready="true"`, which the component sets in an effect *after* the observer is installed. A missed callback, a thrown error, reverse scroll, a refresh mid-page or JavaScript off leaves all content visible. Nothing is ever hidden by default.

- [ ] **Step 1: Write the failing test**

Create `ui/src/routes/landing/Reveal.test.tsx`:

```tsx
import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Reveal,RevealGroup,RevealLines} from './Reveal';

const observers:{cb:IntersectionObserverCallback;opts?:IntersectionObserverInit}[]=[];
function stubObserver(){
 observers.length=0;
 (globalThis as unknown as {IntersectionObserver:unknown}).IntersectionObserver=class{
  constructor(cb:IntersectionObserverCallback,opts?:IntersectionObserverInit){observers.push({cb,opts});}
  observe(){}unobserve(){}disconnect(){}
 };
}
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false})) as unknown as typeof window.matchMedia;
}
afterEach(()=>{vi.restoreAllMocks();});

describe('Reveal',()=>{
 it('renders its children visible before any observer callback fires',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p1"><p>Seventy-six refusals.</p></Reveal>);
  expect(screen.getByText('Seventy-six refusals.')).toBeVisible();
 });

 it('marks itself entered only once and never re-enters on a second intersection',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<Reveal pattern="p1"><p>once</p></Reveal>);
  const node=container.firstElementChild as HTMLElement;
  const entry={isIntersecting:true,target:node} as unknown as IntersectionObserverEntry;
  observers[0].cb([entry],{} as IntersectionObserver);
  expect(node.dataset.revealEntered).toBe('true');
  observers[0].cb([{...entry,isIntersecting:false} as IntersectionObserverEntry],{} as IntersectionObserver);
  expect(node.dataset.revealEntered).toBe('true');
 });

 it('observes at 22% from the bottom for p1 and p2',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p1"><p>x</p></Reveal>);
  expect(observers[0].opts?.rootMargin).toBe('0px 0px -22% 0px');
 });

 it('observes p3 panels at 30% visibility',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p3"><p>panel</p></Reveal>);
  expect(observers[0].opts?.threshold).toBe(0.3);
 });

 it('installs no observer and sets no ready flag under reduced motion',()=>{
  stubObserver();reduceMotion(true);
  const {container}=render(<Reveal pattern="p1"><p>static</p></Reveal>);
  expect(observers).toHaveLength(0);
  expect((container.firstElementChild as HTMLElement).dataset.revealReady).toBeUndefined();
  expect(screen.getByText('static')).toBeVisible();
 });

 it('caps the stagger slot at five items',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<RevealGroup pattern="p1">
   {['a','b','c','d','e','f','g'].map(k=><p key={k}>{k}</p>)}
  </RevealGroup>);
  const slots=[...container.querySelectorAll('[data-reveal-slot]')].map(n=>(n as HTMLElement).dataset.revealSlot);
  expect(slots).toEqual(['0','1','2','3','4','4','4']);
 });

 it('renders every child of a group even when the observer never fires',()=>{
  stubObserver();reduceMotion(false);
  render(<RevealGroup pattern="p3">{['one','two'].map(k=><p key={k}>{k}</p>)}</RevealGroup>);
  expect(screen.getByText('one')).toBeVisible();
  expect(screen.getByText('two')).toBeVisible();
 });
});

describe('RevealLines',()=>{
 it('masks each line separately but keeps one accessible name',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<RevealLines as="h1" id="hero-title"
   lines={['Your repos are already','writing the handbook.']}/>);
  const heading=screen.getByRole('heading',{level:1});
  expect(heading).toHaveAccessibleName('Your repos are already writing the handbook.');
  expect(container.querySelectorAll('[data-reveal-line]')).toHaveLength(2);
  expect([...container.querySelectorAll('[data-reveal-slot]')].map(n=>(n as HTMLElement).dataset.revealSlot)).toEqual(['0','1']);
 });

 it('renders the whole headline visible before any observer callback',()=>{
  stubObserver();reduceMotion(false);
  render(<RevealLines as="h1" lines={['One line.']}/>);
  expect(screen.getByRole('heading',{level:1})).toBeVisible();
 });

 it('installs no observer and masks nothing under reduced motion',()=>{
  stubObserver();reduceMotion(true);
  const {container}=render(<RevealLines as="h1" lines={['a','b']}/>);
  expect(observers).toHaveLength(0);
  for(const line of container.querySelectorAll('[data-reveal-line]'))
   expect((line as HTMLElement).dataset.revealReady).toBeUndefined();
 });
});
```

`RevealLines` uses the `.p1Line` rules from step 3. Each line is a `<span data-reveal-line data-reveal-slot="n">`; the outer element carries `aria-label` equal to `label ?? lines.join(' ')` so a screen reader reads the sentence once, not line by line. Three lines maximum at 1440 (`DESIGN.md` §2.1); the caller supplies the break points.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ui && pnpm test -- Reveal`
Expected: FAIL, "Failed to resolve import ./Reveal".

- [ ] **Step 3: Write `reveal.module.css`**

Only `transform`, `opacity`, `clip-path` (P1 line mask) and `filter` (P3). Never a layout property. Every value a `var()`.

**Do not use an inline style for the stagger slot.** `style={{['--reveal-slot']:String(n)}}` is a dynamic inline style and `check-contracts` rejects it with `inline-style`; a `var(--reveal-slot)` that is never declared fires `unresolved-token`. The component emits `data-reveal-slot="0".."4"` and the CSS maps five static rules.

```css
.reveal{will-change:auto;}

/* P1 Lift: headings, captions, list rows. */
.p1[data-reveal-ready="true"]{
 opacity:var(--zero);
 transform:translateY(var(--enter-rise));
 transition:opacity var(--duration-entrance) var(--ease-entrance),transform var(--duration-entrance) var(--ease-entrance);
}
.p1[data-reveal-entered="true"]{opacity:var(--full-opacity);transform:translateY(var(--zero-length));}
.p1[data-reveal-slot="1"]{transition-delay:var(--stagger-1);}
.p1[data-reveal-slot="2"]{transition-delay:var(--stagger-2);}
.p1[data-reveal-slot="3"]{transition-delay:var(--stagger-3);}
.p1[data-reveal-slot="4"]{transition-delay:var(--stagger-cap);}

/* P1 line mask: the hero headline treatment, DESIGN.md 4.1 and 7 decision 4. */
.p1Line{display:block;overflow:hidden;}
.p1Line[data-reveal-ready="true"]{
 clip-path:var(--mask-hidden);
 transform:translateY(var(--enter-rise));
 transition:clip-path var(--duration-entrance) var(--ease-entrance),transform var(--duration-entrance) var(--ease-entrance);
}
.p1Line[data-reveal-entered="true"]{clip-path:var(--mask-shown);transform:translateY(var(--zero-length));}
.p1Line[data-reveal-slot="1"]{transition-delay:var(--stagger-1);}
.p1Line[data-reveal-slot="2"]{transition-delay:var(--stagger-2);}
.p1Line[data-reveal-slot="3"]{transition-delay:var(--stagger-3);}
.p1Line[data-reveal-slot="4"]{transition-delay:var(--stagger-cap);}

/* P2 Rule draw: hairlines, beat ticks, the tier route. */
.p2[data-reveal-ready="true"]{
 transform:scaleX(var(--zero));
 transform-origin:left;
 transition:transform var(--duration-draw) var(--ease-entrance);
 transition-delay:var(--duration-draw-offset);
}
.p2[data-reveal-entered="true"]{transform:scaleX(var(--scale-full));}

/* P3 Panel settle: glass instruments, bento tiles, the chart. */
.p3[data-reveal-ready="true"]{
 opacity:var(--zero);
 transform:scale(var(--enter-scale));
 filter:blur(var(--enter-blur));
 transition:opacity var(--duration-panel) var(--ease-entrance),transform var(--duration-panel) var(--ease-entrance),filter var(--duration-panel) var(--ease-entrance);
}
.p3[data-reveal-entered="true"]{opacity:var(--full-opacity);transform:scale(var(--scale-full));filter:blur(var(--zero-length));}
.p3[data-reveal-slot="1"]{transition-delay:var(--stagger-panel-1);}
.p3[data-reveal-slot="2"]{transition-delay:var(--stagger-panel-2);}
.p3[data-reveal-slot="3"]{transition-delay:var(--stagger-panel-3);}
.p3[data-reveal-slot="4"]{transition-delay:var(--stagger-cap);}
```

Slot 4 and above all use `--stagger-cap` (240 ms), which is `DESIGN.md` §4.1's "capped at 240 ms, never more than 5 items".

Add these tokens to the landing `:root` block in this task's commit (`--zero` already exists):

```
--full-opacity:1;
--scale-full:1;
--zero-length:0px;
--duration-draw-offset:80ms;
--stagger-1:60ms; --stagger-2:120ms; --stagger-3:180ms;
--stagger-panel-1:70ms; --stagger-panel-2:140ms; --stagger-panel-3:210ms;
--mask-hidden:inset(0 0 100% 0);
--mask-shown:inset(0 0 0 0);
```

and, in the `@media(prefers-reduced-motion:reduce)` block:

```
--mask-hidden:inset(0 0 0 0);
```

- [ ] **Step 4: Write `Reveal.tsx`**

Rules the implementation must satisfy:
- **One `IntersectionObserver` for the whole page**, module-scoped and shared, exactly like `scroll.ts` does it. Register elements in a `Map<HTMLElement,()=>void>`; create the observer lazily; disconnect when the last element unregisters. P1 and P2 use `{rootMargin:'0px 0px -22% 0px'}`; P3 needs `{threshold:0.3}` — that is a second observer configuration, so keep **two** module-scoped observers (one per config) and no more. Two observers total for the page is within the §5 budget; a per-component observer is not.
- On intersection: set `dataset.revealEntered='true'`, then `unobserve` the element. That is the `once` semantics.
- `motionAllowed()`: copy the exact predicate from `scroll.ts` — `prefers-reduced-motion: reduce` false **and** `navigator.connection?.saveData !== true`. If it returns false, render children with no `data-reveal-ready`, no observer, no transition.
- `data-reveal-ready="true"` is set in a `useEffect` **after** the observer is registered, so the pre-enhancement DOM is the finished composition.
- Do not use `motion`'s `<motion.div>` here. CSS transitions driven by data attributes are cheaper and keep every value in `tokens.css`. `motion` is reserved for the pinned chapter's `useScroll`/`useTransform` in T7.
- `RevealGroup` clones each direct child into a `Reveal` with `index` = `Math.min(i,4)`.
- `RevealLines` renders `<As id className aria-label={label ?? lines.join(' ')}>` containing one `<span data-reveal-line data-reveal-slot={Math.min(i,4)} className={css.p1Line}>` per line. This is the sanctioned hero headline treatment (`DESIGN.md` §7 decision 4: fewer animated nodes than per-character orbit, no LCP risk).
- P4 (count) is **not** part of this file. It is the number ticker, wired in T10 only, and it never runs in the hero (`DESIGN.md` §4.1: "P4 never runs inside the LCP window").

- [ ] **Step 5: Run the tests**

Run: `cd ui && pnpm test -- Reveal`
Expected: all ten PASS (seven `Reveal`, three `RevealLines`).

- [ ] **Step 6: Run the contract checker**

Run: `cd ui && pnpm test:contracts && pnpm typecheck`
Expected: `"result": "passed"` and no TypeScript errors. A `token-location` diagnostic means a custom property was declared in `reveal.module.css` instead of `tokens.css`.

- [ ] **Step 7: Commit**

```bash
git add ui/src/routes/landing/Reveal.tsx ui/src/routes/landing/reveal.module.css ui/src/routes/landing/Reveal.test.tsx ui/src/tokens/tokens.css
git commit -m "feat(landing): add the P1-P3 scroll entrance layer with reduced-motion fallback"
```

---

## Task 5: Page skeleton, navigation and hero

**Model tier: capable.** The hero is the LCP surface, the proof rail carries the citation contract, and this task fixes the nine section ids every later task keys on.

**Parallel group: C** (after T1 and T4). Blocks group D.

**Implements:** `DESIGN.md` §3.1, §3.0 reading order, §2.1 typography rules, §5 LCP and focus-order rows; `copy.md` §2 section 1 and §5 microcopy.

**Files:**
- Modify: `ui/src/routes/landing/index.tsx` (rewrite the composition; keep the `EmailAction` branch, the `Question` helper move, the document title effect and the `emailAction` URL handling exactly as they behave today)
- Create: `ui/src/routes/landing/Hero.tsx`, `hero.module.css`
- Create shells only: `ui/src/routes/landing/Extraction.tsx` + `extraction.module.css`, `Retrieval.tsx` + `retrieval.module.css`, `ProofGate.tsx` + `proofgate.module.css`, `Telemetry.tsx` + `telemetry.module.css`, `Availability.tsx` + `availability.module.css`, `Questions.tsx` + `questions.module.css`
- Modify: `ui/src/routes/landing/landing.module.css` (nav, skip, page chrome only; delete the `.why`, `.how`, `.value`, `.roles`, `.roleCard`, `.roleHeader`, `.roleLabel`, `.rolePromise`, `.roleDetail`, `.beats`, `.integrationDetail`, `.plane*`, `.keyline`, `.scrollCue*`, `.heroProof` and `.eyebrow` rules)
- Delete: `ui/src/routes/landing/RouteRule.tsx`, `ui/src/routes/landing/ScopePyramid.tsx`

**Interfaces:**
- Consumes: `Reveal`, `RevealGroup` from T4; tokens from T1; `evidence.proof_gate` from T1.
- Produces, for T6 and T7–T11: the nine section `id` strings, in DOM order —

```
hero · extraction · how-it-works · proof-gate · telemetry · research-results · availability · waitlist · questions
```

  `how-it-works` stays on the retrieval section so the v1 inbound anchor resolves (`copy.md` §5). `research-results` is already the id on `ResearchEvidence.tsx`'s `<section>`; do not add a second one.
- Produces: `Extraction`, `Retrieval`, `ProofGate`, `Telemetry`, `Availability`, `Questions` as zero-prop named exports, each rendering `<section id=… aria-labelledby=…>` with its `h2` and eyebrow and nothing else. T7–T11 fill them.

**Copy blocks rendered by this task**, verbatim from `copy.md` §2 section 1 and §5:

| Slot | String |
|---|---|
| Skip link (protected) | `Skip to content` → `#main` |
| Nav | `How it works` → `#extraction`; `Docs` → `/docs/`; `GitHub` → `https://github.com/wiatrM/guidefold` |
| Header action | `Join the waitlist` → `#waitlist` |
| h1 | `Your repos are already writing the handbook.` |
| Subline | `Guidefold promotes what generalises, then hands your agent the four rules that apply, each one proven.` |
| Body | `Ranking runs across the whole hierarchy in real time, designed for a 30k-skill corpus. Every rule arrives with its source proof attached, and the ones that cannot prove themselves never arrive at all.` |
| Proof cell 1 figure | `76 of 76 harmful rules refused.` |
| Proof cell 1 qualifier | `Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.` |
| Proof cell 2 figure | `+8.53 pp Recall@10 on SRA-Bench.` |
| Proof cell 2 qualifier | `Measured, exploratory offline retrieval. 10 September 2026.` |
| CTA primary | `Join the waitlist` → `#waitlist` |
| CTA secondary (protected) | `Play demo` — the existing `DemoDialog`, unchanged |
| Trust line (protected) | `Open source today. The hosted service is planned.` |
| Text link | `Read the numbers and how we got them` → `#research-results`, **no trailing icon** |
| Scroll cue | visible `How rules move up`, `aria-label="Scroll to the extraction section"`, `href="#extraction"` |

**No eyebrow in the hero.** No `→` in any link text.

- [ ] **Step 1: Write the failing test**

Add to `ui/src/routes/Landing.test.tsx`, replacing the existing `'answers why, then how, then value, under one h1'` test:

```tsx
 it('opens on the outcome and orders the nine sections',()=>{
  const {container}=render(<Landing/>);
  expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1);
  expect(screen.getByRole('heading',{level:1})).toHaveTextContent('Your repos are already writing the handbook.');
  const ids=[...container.querySelectorAll('main section[id]')].map(n=>n.id);
  expect(ids).toEqual(['hero','extraction','how-it-works','proof-gate','telemetry','research-results','availability','waitlist','questions']);
  expect(container.querySelector('a[href="#extraction"]')).toBeInTheDocument();
 });

 it('renders both hero proof cells with their qualifiers in full',()=>{
  render(<Landing/>);
  expect(screen.getByText('76 of 76 harmful rules refused.')).toBeVisible();
  expect(screen.getAllByText('Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.').length).toBeGreaterThan(0);
  expect(screen.getByText('+8.53 pp Recall@10 on SRA-Bench.')).toBeVisible();
  expect(screen.getByText('Measured, exploratory offline retrieval. 10 September 2026.')).toBeVisible();
 });

 it('gives the scroll cue one agreeing label, name and destination',()=>{
  render(<Landing/>);
  const cue=screen.getByRole('link',{name:'Scroll to the extraction section'});
  expect(cue).toHaveAttribute('href','#extraction');
  expect(cue).toHaveTextContent('How rules move up');
 });
```

Also fix, in the same file, the two assertions this task breaks — **T5 must leave `pnpm test` green**, because every group-D task uses `pnpm test` as its own gate and cannot otherwise tell its breakage from an inherited one:

- Line 40–42, inside `'answers why, then how, then value, under one h1'`: that whole test is replaced by the first new test above. Delete it.
- Line 48, inside `'keeps every protected destination and the availability statements'`: `expect(href('a[href="#how-it-works"]')).toBeInTheDocument();` becomes two assertions —

```tsx
  expect(href('a[href="#extraction"]')).toBeInTheDocument();      // nav, copy.md 5
  expect(container.querySelector('section#how-it-works')).toBeInTheDocument(); // v1 inbound anchor still resolves
```

- Inside `'requires an explicit %s action and hides third-party content'`, add the film assertion for `DESIGN.md` §3.8 ("the hero video never mounts" on the email branch):

```tsx
  expect(document.querySelector('video')).toBeNull();
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && pnpm test -- Landing`
Expected: FAIL on the h1 text and the section-id array.

- [ ] **Step 3: Create the six section shells**

Each file, e.g. `Extraction.tsx`:

```tsx
import {Reveal} from './Reveal';
import css from './extraction.module.css';

export function Extraction(){
 return <section id="extraction" className={css.section} aria-labelledby="extraction-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>Where the rules come from</Reveal>
  <Reveal pattern="p1" as="h2" id="extraction-title" className={css.heading}>One team&rsquo;s fix becomes everyone&rsquo;s rule.</Reveal>
 </section>;
}
```

Use the straight apostrophe `'` as written in `copy.md` ("One team's fix…") — `copy.md` §6 states new copy carries no curly quotes; only protected strings keep theirs. Write it as `{"One team's fix becomes everyone's rule."}` to avoid JSX escaping confusion.

The six shells, with their eyebrow and heading from `copy.md`:

| File | id | aria-labelledby | Eyebrow | h2 |
|---|---|---|---|---|
| `Extraction.tsx` | `extraction` | `extraction-title` | `Where the rules come from` | `One team's fix becomes everyone's rule.` |
| `Retrieval.tsx` | `how-it-works` | `retrieval-title` | `What the agent gets` | `Thirty thousand rules. Four reach the agent.` |
| `ProofGate.tsx` | `proof-gate` | `proof-gate-title` | `Safety boundary` | `Seventy-six harmful rules. Seventy-six refusals.` |
| `Telemetry.tsx` | `telemetry` | `telemetry-title` | `For the organisation` | `You see which rule failed, and why.` |
| `Availability.tsx` | `availability` | `availability-title` | *(none)* | `Clone it today. It is open.` |
| `Questions.tsx` | `questions` | `questions-title` | *(none)* | `Before you join` |

Each `*.module.css` gets, at minimum:

```css
.section{padding-block:var(--landing-section-padding);}
.eyebrow{font-family:var(--font-mono);font-size:var(--font-size-code);letter-spacing:var(--landing-tracking-mono);color:var(--steel);display:flex;align-items:center;gap:var(--space-2);}
.eyebrow::before{content:"";display:block;inline-size:var(--landing-eyebrow-rule);block-size:var(--landing-pixel);background:var(--line-strong);}
.heading{font-family:var(--font-display);font-size:var(--landing-heading);line-height:var(--landing-heading-leading);font-weight:var(--weight-semibold);}
```

Sentence case, never uppercase, never `--tracking-label` (conflict-table row 6).

- [ ] **Step 4: Move the protected nodes into `Questions.tsx` and `Availability.tsx`**

**Copy the JSX nodes, do not retype the strings.** From today's `index.tsx`:
- lines 163–171 (the `questions` section, the `Question` helper's four instances and all their `<p>` answers) → `Questions.tsx`, together with the `Question` component definition from lines 19–32. Ids stay `question-1`, `question-2`, `question-3`, `privacy`; all panels closed on load; hash deep-linking and the consent-link click handler unchanged.
- lines 147–156's two `<p>` statements → `Availability.tsx`. The availability band's own `Try the open-source version` link is **removed** (`copy.md` §3); the `Read the docs` link to `/docs/` stays.

T11 restyles both; this task only relocates them.

- [ ] **Step 5: Write `Hero.tsx`**

Structure, DOM order = tab order = visual order, no CSS `order`:

```
<section id="hero" aria-labelledby="hero-title">
  <div heroScrim aria-hidden="true"/>                     ← --film-scrim-hero
  <div heroCopy>
    <RevealLines as="h1" id="hero-title"
      lines={['Your repos are already','writing the handbook.']}/>   ← T4's masked line lift
    <Reveal p1 as="p" index=1>subline</Reveal>
    <Reveal p1 as="p" index=2>body</Reveal>
    <div heroActions>
      <a primary href="#waitlist">Join the waitlist <ArrowRight aria-hidden="true"/></a>
      <DemoDialog onOpenChange={setDemoOpen}/>
    </div>
    <p trust>Open source today. The hosted service is planned.</p>
    <a textLink href="#research-results">Read the numbers and how we got them</a>
    <a scrollCue href="#extraction" aria-label="Scroll to the extraction section">
      <span aria-hidden="true"><ArrowDown weight="bold"/></span><span>How rules move up</span>
    </a>
  </div>
  <Reveal p3 as="div" className={css.proofRail}>  ← glass strip, two cells, one hairline
    <div cell>
      <p figure>76 of 76 harmful rules refused.</p>
      <p qualifier>{evidence.proof_gate.microcopy}</p>
    </div>
    <div cell>
      <p figure>+8.53 pp Recall@10 on SRA-Bench.</p>
      <p qualifier>Measured, exploratory offline retrieval. 10 September 2026.</p>
    </div>
  </Reveal>
  <div tierGlyph aria-hidden="true"> … one SVG polyline over four <rect> tier bars … </div>
</section>
```

Hard requirements:
- **The proof cells render their final values in the base DOM.** No ticker, no count, nothing animated on the figure text (`DESIGN.md` §4.1: P4 never runs inside the LCP window). The `Reveal p3` on the rail animates opacity/scale/blur on the container only.
- **The first proof cell is conditional on the data.** `copy.md` §5: if `evidence.proof_gate` is absent, render the retrieval cell alone. Write it as `{evidence.proof_gate && <div …>}`. A one-item strip is fine; an unsourced one is not.
- Both cells keep their qualifier at every breakpoint; a cell that cannot fit its qualifier is dropped whole, never truncated.
- The tier glyph is `aria-hidden`, four `<rect>` in `--tier-1..4` with one `--safety-orange` polyline, `--landing-tier-glyph-height` tall at 720. It is the page's **first** orange moment; the second is the extraction diff row (T7). There are no others.
- Only the two primary actions carry a directional icon.

- [ ] **Step 6: Write `hero.module.css`**

1440: `object-position` comes from `--landing-hero-object`; copy occupies columns 1–6 of the 12-column `--landing-width` grid anchored to the lower third; proof rail spans columns 1–9 across the lower edge; tier glyph columns 10–12. `h1` uses `--landing-display`, `--landing-display-leading`, `--landing-display-tracking`. Subline `--landing-kicker` at `--landing-kicker-measure`. Body `--landing-body` at `--landing-copy-width`. Figures `--landing-metric` / `--landing-metric-leading` in `--font-mono` with `font-variant-numeric: tabular-nums`. Qualifiers `--font-size-small` in `--steel`.

390 (inside the existing 720 token block — **no literal breakpoint in this module**): copy stacked, both actions full width at `--touch-height` minimum, both proof cells stacked and both above the fold, tier glyph below the actions. **The header is static, not sticky, at 720** — set `--landing-nav-position:static` in the 720 token block and consume it in `landing.module.css`'s `.nav`. That is the fix for today's defect where the nav covers the first `h1` line.

The proof rail is the hero's only glass surface: `background:var(--glass-ground)`, `backdrop-filter:blur(var(--glass-blur))`, `border:var(--border-width) solid var(--glass-border)`, `border-radius:var(--landing-radius-panel)`, top-edge `--glass-highlight`. Because `[data-film="on"]` sets `--glass-blur:0px`, the blur is live only over the poster.

- [ ] **Step 7: Rewrite `index.tsx`**

Keep unchanged: the `emailAction` `URLSearchParams` branch, `window.history.replaceState(null,'','/')`, the `document.title='Guidefold | Team instructions for coding agents'` effect, `<a className={css.skip} href="#main">Skip to content</a>`, `<main id="main" tabIndex={-1}>`, `<LandingFooter emailAction={…}/>`.

**One change to the film mount.** `DESIGN.md` §3.8 requires that the `?confirm=` / `?unsubscribe=` branch "never mounts the film", but `<FilmBackdrop/>` today renders outside `<main>` and therefore mounts on that branch too. Gate it:

```tsx
{!emailAction && <FilmBackdrop/>}
```

The branch still renders `EmailAction` instead of all nine sections.

Remove: the `roles` array, the `Card`/`CardContent`/`CardHeader`/`CardTitle` imports, `RouteRule`, `ScopePyramid`, the `field`/`topo`/`survey` plane divs and their `useSectionProgress` calls for `why`/`how`/`value`, the `#why` section, the `#value` section.

Change the nav: `How it works` → `href="#extraction"`.

Compose:

```tsx
<Hero onDemoOpenChange={setDemoOpen}/>
<Extraction/>
<Retrieval/>
<ProofGate/>
<Telemetry/>
<ResearchEvidence/>
<Availability/>
<Waitlist/>       ← inline section, id="waitlist", or keep it inline in index.tsx
<Questions/>
```

The waitlist section stays inline in `index.tsx` (it is four lines wrapping `WaitlistForm`); T11 restyles it. Its `id` is `waitlist` and its heading becomes `Be first on hosted Guidefold.` with subline `One email when it is ready. Nothing else.` (`copy.md` §2 section 8).

- [ ] **Step 8: Delete the retired components**

```bash
rm ui/src/routes/landing/RouteRule.tsx ui/src/routes/landing/ScopePyramid.tsx
```

Remove their rules from `landing.module.css` (`.routeRule`, `.routeLine`, `.waypointNear`, `.scope*`). T12 retargets the e2e test that asserted `[class*="routeLine"]` strokeDashoffset onto the tier instrument's route (T7).

- [ ] **Step 9: Run the tests**

Run: `cd ui && pnpm test`
Expected: **the whole unit suite is green.** `pnpm test` is `vitest run` only; the e2e file is a separate script and T12 owns it. If any unit assertion is still red, it is one of the two named in step 1 — fix it here, not later. Every group-D task uses `pnpm test` as its gate and needs a green baseline.

- [ ] **Step 10: Run typecheck and contracts**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`
Expected: both clean.

- [ ] **Step 11: Commit**

```bash
git add ui/src/routes/landing/index.tsx ui/src/routes/landing/Hero.tsx ui/src/routes/landing/hero.module.css \
  ui/src/routes/landing/Extraction.tsx ui/src/routes/landing/extraction.module.css \
  ui/src/routes/landing/Retrieval.tsx ui/src/routes/landing/retrieval.module.css \
  ui/src/routes/landing/ProofGate.tsx ui/src/routes/landing/proofgate.module.css \
  ui/src/routes/landing/Telemetry.tsx ui/src/routes/landing/telemetry.module.css \
  ui/src/routes/landing/Availability.tsx ui/src/routes/landing/availability.module.css \
  ui/src/routes/landing/Questions.tsx ui/src/routes/landing/questions.module.css \
  ui/src/routes/landing/landing.module.css ui/src/routes/Landing.test.tsx ui/src/tokens/tokens.css
git rm ui/src/routes/landing/RouteRule.tsx ui/src/routes/landing/ScopePyramid.tsx
git commit -m "feat(landing): rebuild the page skeleton, navigation and hero on the v2 structure"
```

---

## Task 6: The film playhead anchor map

**Model tier: standard.** Contained, but the measurement discipline and the damped seek must survive.

**Parallel group: D** (after T5). Disjoint from T7–T11.

**Implements:** `DESIGN.md` §3.0, §4.2 film scrub row, §4.4 media failure paths, §5 frame budget.

**Files:**
- Modify: `ui/src/routes/landing/FilmBackdrop.tsx`
- Modify: `ui/src/routes/landing/scroll.ts` (only if a shared rect sampler is genuinely needed; prefer leaving it untouched)
- Create: `ui/src/routes/landing/FilmBackdrop.test.tsx`

**Interfaces:**
- Consumes: the nine section ids from T5.
- Produces: `export const FILM_ANCHORS` and `export function playheadAt(progress:number,anchors:readonly Anchor[]):number` for the test.

- [ ] **Step 1: Write the failing test**

Create `ui/src/routes/landing/FilmBackdrop.test.tsx`:

```tsx
import {describe,it,expect} from 'vitest';
import {FILM_ANCHORS,playheadAt} from './FilmBackdrop';

describe('film anchor map',()=>{
 it('names the nine sections in DOM order with their playhead seconds',()=>{
  expect(FILM_ANCHORS.map(a=>a.id)).toEqual(['hero','extraction','how-it-works','proof-gate','telemetry','research-results','availability','waitlist','questions']);
  expect(FILM_ANCHORS.map(a=>a.second)).toEqual([0,1.4,4.2,5.6,6.8,7.8,8.6,9.1,9.7]);
 });

 it('interpolates piecewise linearly between measured anchors',()=>{
  const anchors=[{id:'a',second:0,at:0},{id:'b',second:4,at:0.5},{id:'c',second:10,at:1}];
  expect(playheadAt(0,anchors)).toBeCloseTo(0,4);
  expect(playheadAt(0.25,anchors)).toBeCloseTo(2,4);
  expect(playheadAt(0.5,anchors)).toBeCloseTo(4,4);
  expect(playheadAt(0.75,anchors)).toBeCloseTo(7,4);
  expect(playheadAt(1,anchors)).toBeCloseTo(10,4);
 });

 it('clamps outside the measured range and never exceeds the film duration',()=>{
  const anchors=[{id:'a',second:0,at:0.1},{id:'b',second:10,at:0.9}];
  expect(playheadAt(-1,anchors)).toBe(0);
  expect(playheadAt(2,anchors)).toBe(10);
 });

 it('is monotonic and exact in reverse',()=>{
  const anchors=FILM_ANCHORS.map((a,i)=>({...a,at:i/(FILM_ANCHORS.length-1)}));
  const forward=[...Array(21).keys()].map(i=>playheadAt(i/20,anchors));
  const backward=[...Array(21).keys()].map(i=>playheadAt((20-i)/20,anchors)).reverse();
  expect(backward).toEqual(forward);
  for(let i=1;i<forward.length;i++)expect(forward[i]).toBeGreaterThanOrEqual(forward[i-1]);
 });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && pnpm test -- FilmBackdrop`
Expected: FAIL, `FILM_ANCHORS` is not exported.

- [ ] **Step 3: Add the typed anchor constant**

In `FilmBackdrop.tsx`, one typed constant array (JavaScript constants, not CSS, so the contract checker is unaffected):

```ts
type Anchor={id:string;second:number;at:number};
export const FILM_ANCHORS:readonly Omit<Anchor,'at'>[]=[
 {id:'hero',second:0},            // table above the clouds, the drawn orange route, sunrise window
 {id:'extraction',second:1.4},    // the fall into the terrain: contour valley, teal rings, map sheet lifting
 {id:'how-it-works',second:4.2},  // four cream cards standing in a fan around one lit orange marker
 {id:'proof-gate',second:5.6},    // the route crossing a plateau edge, teal rim light on the boundary
 {id:'telemetry',second:6.8},     // stacked plateaus held wide, cubes across the lower tiers
 {id:'research-results',second:7.8}, // upper plateau, sparse cubes, route arriving at the top tier
 {id:'availability',second:8.6},  // pull back begins, the terrain reads as a map again
 {id:'waitlist',second:9.1},      // the map rising into its folds
 {id:'questions',second:9.7},     // exact terminal frame: folded map on the desk beside the wordmark
] as const;
```

Two beats are literal and must not be re-assigned: the four-card fan under retrieval (`how-it-works`), the tier-edge crossing under `proof-gate`. The last section holds the terminal frame to 10.04 s exactly.

- [ ] **Step 4: Write `playheadAt`**

```ts
export function playheadAt(progress:number,anchors:readonly Anchor[]):number{
 if(!anchors.length)return 0;
 if(progress<=anchors[0].at)return anchors[0].second;
 const last=anchors[anchors.length-1];
 if(progress>=last.at)return last.second;
 for(let i=1;i<anchors.length;i++){
  const a=anchors[i-1],b=anchors[i];
  if(progress<=b.at){
   const span=b.at-a.at;
   return span<=0?b.second:a.second+((progress-a.at)/span)*(b.second-a.second);
  }
 }
 return last.second;
}
```

- [ ] **Step 5: Measure the anchor positions**

Add one `measure()` in `FilmBackdrop.tsx` that builds `Anchor[]` from the **measured offsets of the nine section elements**, never from hardcoded scroll fractions:

```ts
const scrollable=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);
const anchors=FILM_ANCHORS
 .map(a=>{const el=document.getElementById(a.id);return el?{...a,at:Math.min(1,Math.max(0,(el.getBoundingClientRect().top+window.scrollY)/scrollable))}:null;})
 .filter((a):a is Anchor=>a!==null);
```

Store it in a ref. Recompute on: `resize`, `orientationchange`, `document.fonts.ready`, and the video's `loadedmetadata`. **Do not** recompute inside the rAF step — `DESIGN.md` §5 forbids `getBoundingClientRect` outside the batched sampler. If an anchor's element is missing, drop it; interpolation degrades gracefully.

- [ ] **Step 6: Feed the map into the existing scrub**

In the `useDocumentProgress` callback, replace `target.current=progress` with the playhead in seconds:

```ts
useDocumentProgress((progress)=>{target.current=playheadAt(progress,anchorsRef.current);},mounted&&ready);
```

and in the rAF step, drop the `target.current * duration` multiplication — `target.current` is now already seconds. Clamp it to the real duration:

```ts
const duration=Number.isFinite(node.duration)&&node.duration>0?node.duration:DURATION_FALLBACK;
const wanted=Math.min(target.current,duration);
current.current+=(wanted-current.current)*0.14;
if(Math.abs(current.current-node.currentTime)>FRAME&&!node.seeking){try{node.currentTime=current.current;}catch{setFailed(true);}}
```

**Keep unchanged:** the damped seek at `.14`, the one-frame delta gate, the `seeking` guard, the poster-first contract with `fetchPriority="high"`, the conditional video mount, the 8 s `canplay` watchdog, the `data-film` root flag, and the `aria-hidden` on the film container. Add the pause behaviour `DESIGN.md` §4.4 requires if it is missing: pause on `visibilitychange`, on leaving the viewport and while the demo dialog is open.

- [ ] **Step 7: Run the tests**

Run: `cd ui && pnpm test -- FilmBackdrop`
Expected: all four PASS.

- [ ] **Step 8: Verify in the browser**

Run `cd ui && pnpm dev`. Scroll slowly top to bottom and back. Confirm: the four-card fan is on screen while the retrieval section is, the tier-edge crossing while the proof gate is, and the folded-map terminal frame while the FAQ and footer are. Reverse scroll returns to the same frames. Stop the server.

- [ ] **Step 9: Commit**

```bash
git add ui/src/routes/landing/FilmBackdrop.tsx ui/src/routes/landing/FilmBackdrop.test.tsx
git commit -m "feat(landing): map the film playhead to measured section anchors"
```

---

## Task 7: Extraction chapter (pinned, three beats)

**Model tier: capable.** The page's centrepiece, the largest frame-budget risk, and a registry-versus-handmade decision in the first step.

**Parallel group: D** (after T5).

**Implements:** `DESIGN.md` §3.2, §4.2 chapter pin and chapter parallax rows, §4.1 P1/P2/P3, §7 decisions 3 and 10; `copy.md` §2 section 2; ruling 6.

**Files:**
- Modify: `ui/src/routes/landing/Extraction.tsx`
- Modify: `ui/src/routes/landing/extraction.module.css`
- Create: `ui/src/routes/landing/Extraction.test.tsx`
- Possibly modify: `ui/qa/spectrum-registry.json` (only if step 1 adopts a registry component)

**Interfaces:**
- Consumes: `Reveal` from T4; tokens from T1 (`--landing-stage-height`, `--landing-stage-scroll`, `--parallax-chapter`, `--tier-1..4`, `--safety-orange`).
- Produces: for T12's e2e, a route element with a stable class containing `tierRoute` whose resting `stroke-dashoffset` is `0px`. This replaces the deleted `RouteRule`'s `[class*="routeLine"]` selector.

**Copy, split across the three beats verbatim** (ruling 6; `DESIGN.md` §7 decision 10 "split as specified"). The eyebrow `Where the rules come from` and the h2 `One team's fix becomes everyone's rule.` are fixed at the top of the stage and do not move between beats.

| Beat | h3 | Caption, verbatim from `copy.md` §2 section 2 | Instrument |
|---|---|---|---|
| 1 | `Written where the work is` | `Guidefold finds the reusable part of a service rule,` | Path instrument: mono breadcrumb of a real Meridian fixture path with one `SKILL.md` row |
| 2 | `The reusable part is lifted` | `promotes it a level, and shows an owner the diff.` + `Service, then team, then organisation.` | Diff instrument: two mono columns, `stays here` / `goes up`, four real fixture rule names, the promoted row in `--safety-orange` |
| 3 | `It lands one level up` | `The handbook nobody had time to write assembles itself out of work your teams already did, one reviewed diff at a time.` + `Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.` | Tier instrument: four tier bars with counts, upper tiers narrower, the promoted rule travelling one tier up as the beat advances |

The subline is split at its comma across beats 1 and 2; body sentence 1 joins beat 2; body sentence 2 and the microcopy line form beat 3. No word is changed, added or removed.

- [ ] **Step 1: Evaluate the registry option first**

This is conflict-table row 5 and it is a real obligation, not a formality.

```bash
cd ui && pnpm dlx shadcn@latest add @aceternity/sticky-scroll-reveal --dry-run
curl -s https://ui.aceternity.com/registry/sticky-scroll-reveal.json | head -c 8000
```

Read the actual source. Adopt it **only** if all of these hold:
- its scroll progress is a pure function of scroll position (reversible, exact on reverse scroll, no velocity or timer state);
- it reserves its stage height before enhancement (CLS 0);
- it does not call `getBoundingClientRect` per frame;
- it needs no `next/` API and no new runtime dependency;
- its literal colours and dimensions are either absent or confinable to a Tailwind `className` inside `src/components/spectrumui/`.

If adopted: install it, add its provenance entry to `ui/qa/spectrum-registry.json` with its `sha256`, and adapt it to receive beat content as props (it must not import `src/data/**`). If rejected: **write the exception into the commit message** — the items searched (`@aceternity/sticky-scroll-reveal`, `@spectrumui` search for sticky/scroll/pin), the concrete obstacle, and the smallest adaptation — and hand-build with `motion`'s `useScroll`/`useTransform` plus `position: sticky`, following `.agents/skills/cloudfloo-premium-scroll-motion/`. `DESIGN.md` §3.2 already records this as a Spectrum exception; your note records the `@aceternity` half.

- [ ] **Step 2: Write the failing test**

Create `ui/src/routes/landing/Extraction.test.tsx`:

```tsx
import {describe,it,expect,afterEach,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Extraction} from './Extraction';

function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false})) as unknown as typeof window.matchMedia;
}
afterEach(()=>vi.restoreAllMocks());

describe('extraction chapter',()=>{
 it('keeps all three beats in the DOM in reading order',()=>{
  reduceMotion(false);
  const {container}=render(<Extraction/>);
  const beats=[...container.querySelectorAll('[data-beat]')].map(n=>(n as HTMLElement).dataset.beat);
  expect(beats).toEqual(['1','2','3']);
  expect(screen.getByRole('heading',{level:3,name:'Written where the work is'})).toBeVisible();
  expect(screen.getByRole('heading',{level:3,name:'The reusable part is lifted'})).toBeVisible();
  expect(screen.getByRole('heading',{level:3,name:'It lands one level up'})).toBeVisible();
 });

 it('carries the copy.md sentences verbatim across the beats',()=>{
  reduceMotion(false);
  render(<Extraction/>);
  expect(screen.getByText('Guidefold finds the reusable part of a service rule,')).toBeVisible();
  expect(screen.getByText('promotes it a level, and shows an owner the diff.')).toBeVisible();
  expect(screen.getByText('Service, then team, then organisation.')).toBeVisible();
  expect(screen.getByText(/assembles itself out of work your teams already did, one reviewed diff at a time\./)).toBeVisible();
  expect(screen.getByText('Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.')).toBeVisible();
 });

 it('rests with the tier route drawn complete',()=>{
  reduceMotion(true);
  const {container}=render(<Extraction/>);
  const route=container.querySelector('[data-tier-route]');
  expect(route).toBeInTheDocument();
  expect(route).toHaveAttribute('stroke-dashoffset','0');
 });

 it('marks exactly one promoted row as the human decision',()=>{
  reduceMotion(false);
  const {container}=render(<Extraction/>);
  expect(container.querySelectorAll('[data-decision="human"]')).toHaveLength(1);
 });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd ui && pnpm test -- Extraction`
Expected: FAIL, no `[data-beat]` elements.

- [ ] **Step 4: Build the stage**

Structure: `<section id="extraction">` contains a scroll track of `--landing-stage-scroll` (260 vh) height; inside it one `position: sticky` stage of `--landing-stage-height` (100 dvh). The eyebrow and `h2` sit fixed at the top of the stage. Three `<div data-beat="1|2|3">` blocks hold caption + instrument.

Beat crossfade, from `DESIGN.md` §4.2: `--p` 0→1 across the three beats at 0.0–0.33, 0.33–0.66, 0.66–1.0 with a 0.06 overlap. Drive it from `motion`'s `useScroll` on the track (or from the adopted registry component), and expose it as a CSS custom property already declared in `tokens.css` — the existing `--p` is exactly this and defaults to `.5`. **Write `--p` on the stage element, not on React state.**

At 1080 and below, `--landing-stage-height` is `auto` and the pin is off: the three beats become three stacked blocks, caption above instrument, in the same DOM order. Nothing is hidden and nothing is reordered. This is a token swap, not a module media query.

Chapter parallax on the instrument layer only: `transform: translate3d(0, calc((var(--p) - .5) * var(--parallax-chapter)), 0)`. Linear in `--p`, exact in reverse. `will-change: transform` on the stage only.

1440 columns: instruments 7–12, captions 1–5, a 1 px vertical rule with three ticks in column 6 (P2 draw).

- [ ] **Step 5: Build the three instruments**

All three are glass panels (`--glass-ground`, `--glass-blur`, `--glass-border`, `--glass-highlight`, `--landing-radius-panel`, `--landing-panel-pad`), each wrapped in `<Reveal pattern="p3">`.

1. **Path instrument.** Mono breadcrumb of a real Meridian fixture path plus one `SKILL.md` row. Take the path from `examples/monorepo/` — read `ui/src/routes/landing/instruction.ts`'s `fixtureSource` for the path already used by `InstructionReader`, and reuse the same scope so the page stays literal.
2. **Diff instrument.** Two mono columns headed `stays here` and `goes up`, four real fixture rule names. The promoted row carries `data-decision="human"` and `--safety-orange` plus `--glow-route`. That is the page's second and last orange moment (the hero tier glyph was the first) and its first and only `--glow-route`.
3. **Tier instrument.** Four tier bars in `--tier-1..4`, widths from the existing `--landing-scope-width-0..3`, with counts; upper tiers narrower. One SVG polyline `data-tier-route` in `--safety-orange` whose `stroke-dashoffset` is mapped to beat-3 progress and whose **resting value is the finished route** — `stroke-dashoffset="0"` in the markup, animated only when the sampler is driving. The counts must be labelled Meridian fixture counts; do not invent a number.

Colour is never the only carrier: the promoted row carries the word `promoted`, each tier its name (`service`, `team`, `organisation`, `root`).

- [ ] **Step 6: Run the tests**

Run: `cd ui && pnpm test -- Extraction`
Expected: all four PASS.

- [ ] **Step 7: Verify the frame budget**

Run `cd ui && pnpm dev`, open DevTools Performance, record a scroll pass through the chapter at 1440 with 4× CPU throttling. Requirement: **zero long tasks**, main-thread work under 4 ms per frame. If the trace shows long tasks, apply `DESIGN.md` §7 decision 3's escape hatch — set `--landing-stage-height: auto` at all widths, keep the three beats as a scroll-linked triptych, and record the decision in the commit message. The composition survives either way.

- [ ] **Step 8: Contracts and typecheck**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`

- [ ] **Step 9: Commit**

```bash
git add ui/src/routes/landing/Extraction.tsx ui/src/routes/landing/extraction.module.css ui/src/routes/landing/Extraction.test.tsx ui/qa/spectrum-registry.json
git commit -m "feat(landing): build the pinned extraction chapter with its three beats"
```

Drop `ui/qa/spectrum-registry.json` from the `git add` line if step 1 rejected the registry component.

---

## Task 8: Retrieval chapter

**Model tier: standard.** One instrument, one clear layout, and a hard deletion (no proof figures).

**Parallel group: D** (after T5).

**Implements:** `DESIGN.md` §3.3 **as amended by conflict-table row 1**; `copy.md` §2 section 3.

**Files:**
- Modify: `ui/src/routes/landing/Retrieval.tsx`
- Modify: `ui/src/routes/landing/retrieval.module.css`
- Create: `ui/src/routes/landing/Retrieval.test.tsx`

**Interfaces:**
- Consumes: `Reveal` from T4; the existing `IntroFigure` and `InstructionReader` components, unchanged; tokens from T1.
- Produces: nothing other tasks consume.

**Copy, verbatim from `copy.md` §2 section 3** (the eyebrow and h2 already exist from T5's shell):

| Slot | String |
|---|---|
| Eyebrow | `What the agent gets` |
| h2 | `Thirty thousand rules. Four reach the agent.` |
| Subline | `Ranked by the task and by the place in the repository, in real time, every prompt.` |
| Body | `General cards first, then the local rule that sharpens them, and full text only when the agent asks for it. Your context window carries four cards instead of a filing cabinet.` |
| Microcopy | `Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.` |
| Text link | `Try the open-source version` → `https://github.com/wiatrM/guidefold#quickstart`, **no trailing icon**. This is the **only** copy of this link in the body of the page; the footer keeps its own. |

**Deleted from `DESIGN.md` §3.3 by ruling 3 and conflict-table row 1:** the `25/25` hierarchical-SEARCH figure and the `4/4` figure. **This section ships no proof figures.** No number ticker here. `border-beam` is not used: a travelling border on an instrument the reader is parsing is decoration on data (`DESIGN.md` §3.3, §4.6).

- [ ] **Step 1: Write the failing test**

Create `ui/src/routes/landing/Retrieval.test.tsx`:

```tsx
import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Retrieval} from './Retrieval';

describe('retrieval chapter',()=>{
 it('renders the copy.md block verbatim',()=>{
  render(<Retrieval/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Thirty thousand rules. Four reach the agent.');
  expect(screen.getByText('Ranked by the task and by the place in the repository, in real time, every prompt.')).toBeVisible();
  expect(screen.getByText(/Your context window carries four cards instead of a filing cabinet\./)).toBeVisible();
  expect(screen.getByText('Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.')).toBeVisible();
 });

 it('delivers exactly four cards, general first, each with a proof state',()=>{
  const {container}=render(<Retrieval/>);
  const cards=container.querySelectorAll('[data-delivered-card]');
  expect(cards).toHaveLength(4);
  for(const card of cards)expect((card as HTMLElement).dataset.proof).toBeTruthy();
 });

 it('carries no excluded figure in any form',()=>{
  const {container}=render(<Retrieval/>);
  const text=container.textContent??'';
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/\b\d+\s?ms\b/);
  expect(text).not.toMatch(/422/);
 });

 it('links to the open-source quickstart exactly once and without a glyph in the label',()=>{
  const {container}=render(<Retrieval/>);
  const links=container.querySelectorAll('a[href="https://github.com/wiatrM/guidefold#quickstart"]');
  expect(links).toHaveLength(1);
  expect(links[0].textContent).toBe('Try the open-source version');
 });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && pnpm test -- Retrieval`
Expected: FAIL on the copy assertions.

- [ ] **Step 3: Build the instrument**

One glass panel spanning columns 2–11 at 1440, wrapped in `<Reveal pattern="p3">`, read left to right in three zones separated by 1 px `--line` hairlines:

1. **Query line** (mono, `--font-size-code`): the task and the repository path, e.g. `task: rotate the service token` / `platforms/atlas/identity/turnstile/`.
2. **Candidate column**: how many skills the scope could see. Use a labelled Meridian fixture count, not an invented one; read it from `examples/monorepo/` or state it as the fixture's own number with the word `fixture` visible.
3. **Four delivered cards**, general first, each `data-delivered-card` with a `data-proof` state and a visible proof word (`proof complete`), never colour alone.

Beneath the instrument: the microcopy line, then `IntroFigure` and `InstructionReader` as the "full text only when the agent asks for it" step, with the protected Meridian fixture excerpt and its "not a live run" label intact. Then the text link.

`--glow-system` sits under this instrument — it is the page's first of exactly two glows; the second is the proof gate (T9). There are no others.

390: the panel becomes a vertical sequence query → candidates → four cards, `--landing-panel-pad` 16 px, internal hairline grid kept so it still reads as an instrument.

- [ ] **Step 4: Run the tests**

Run: `cd ui && pnpm test -- Retrieval`
Expected: all four PASS.

- [ ] **Step 5: Contracts and typecheck**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`

- [ ] **Step 6: Commit**

```bash
git add ui/src/routes/landing/Retrieval.tsx ui/src/routes/landing/retrieval.module.css ui/src/routes/landing/Retrieval.test.tsx
git commit -m "feat(landing): build the retrieval chapter instrument"
```

---

## Task 9: Proof gate and telemetry chapters

**Model tier: standard.** Two type-led sections of the same shape; the label string is the whole risk.

**Parallel group: D** (after T5).

**Implements:** `DESIGN.md` §3.4, §3.5, §7 decision 8; `copy.md` §2 sections 4 and 5; ruling 3.

**Files:**
- Modify: `ui/src/routes/landing/ProofGate.tsx`, `proofgate.module.css`
- Modify: `ui/src/routes/landing/Telemetry.tsx`, `telemetry.module.css`
- Create: `ui/src/routes/landing/ProofGate.test.tsx`, `ui/src/routes/landing/Telemetry.test.tsx`

**Interfaces:**
- Consumes: `Reveal` from T4; `evidence.proof_gate` from T1; tokens from T1.
- Produces: nothing other tasks consume.

**Proof-gate copy, verbatim from `copy.md` §2 section 4:**

| Slot | String |
|---|---|
| Eyebrow | `Safety boundary` |
| h2 | `Seventy-six harmful rules. Seventy-six refusals.` |
| Subline | `The flat control loaded all 76. Guidefold answered ASK every single time.` |
| Body | `Delivery requires a source proof: hash, revision, scope. Conflicting, stale and out-of-scope rules become an ASK, never a silent load and never a silent fallback, and every delivery traces back to the revision it came from.` |
| Proof line 1 | `ASK for all 76 harmful mutations, LOAD for all 4 safe cases. One-sided Wilson 95% upper bound for harmful delivery: 4.81%.` |
| Proof line 1 qualifier | `Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.` |
| Proof line 2 | `The same 4 safe targets came through the production USE 1.2 HTTP handler with reason=source_proof_complete, source hash and range verified by the service.` |
| Proof line 2 qualifier | `Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.` |

`reason=source_proof_complete` renders inside `<code>` (it is backticked in `copy.md`). The label renders **in full both times**, at every breakpoint, never shortened to "verified" or "safety". Both proof strings wrap rather than truncate: no ellipsis, no "read more". The figures here are sentences, so they set at `--landing-metric-unit` weight, not `--landing-metric`, and **P4 never applies** (`DESIGN.md` §4.1: a figure written as a sentence never counts).

**Telemetry copy, verbatim from `copy.md` §2 section 5:**

| Slot | String |
|---|---|
| Eyebrow | `For the organisation` |
| h2 | `You see which rule failed, and why.` |
| Subline | `Per team: task success, ASK reasons, the SEARCH to USE funnel, tokens, tool calls, time.` |
| Body | `ASK reasons come from a fixed vocabulary, so "Conflicting rules" and "Revision changed" arrive as counts you can act on rather than a log you have to read. Every pull request that touches a rule gets a report before merge: what changed, what collides, what an agent would now see.` |
| Microcopy | `Missing data reads Unknown, never zero.` |

- [ ] **Step 1: Write the failing tests**

`ui/src/routes/landing/ProofGate.test.tsx`:

```tsx
import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ProofGate} from './ProofGate';

const LABEL='Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.';

describe('proof gate',()=>{
 it('leads on the comparison and names the flat control',()=>{
  render(<ProofGate/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Seventy-six harmful rules. Seventy-six refusals.');
  expect(screen.getByText('The flat control loaded all 76. Guidefold answered ASK every single time.')).toBeVisible();
 });

 it('renders both proof lines with the unshortened label under each',()=>{
  render(<ProofGate/>);
  expect(screen.getByText(/One-sided Wilson 95% upper bound for harmful delivery: 4\.81%\./)).toBeVisible();
  expect(screen.getByText(/came through the production USE 1\.2 HTTP handler/)).toBeVisible();
  expect(screen.getAllByText(LABEL)).toHaveLength(2);
 });

 it('never rounds the count or claims zero risk',()=>{
  const {container}=render(<ProofGate/>);
  const text=(container.textContent??'').toLowerCase();
  expect(text).not.toContain('zero risk');
  expect(text).not.toContain('100% safe');
  expect(text).not.toContain('no unsafe deliveries');
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(container.textContent).toContain('76');
 });
});
```

`ui/src/routes/landing/Telemetry.test.tsx`:

```tsx
import {describe,it,expect} from 'vitest';
import {render,screen,within} from '@testing-library/react';
import {Telemetry} from './Telemetry';

describe('telemetry chapter',()=>{
 it('renders the copy.md block verbatim',()=>{
  render(<Telemetry/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('You see which rule failed, and why.');
  expect(screen.getByText('Per team: task success, ASK reasons, the SEARCH to USE funnel, tokens, tool calls, time.')).toBeVisible();
  expect(screen.getByText('Missing data reads Unknown, never zero.')).toBeVisible();
 });

 it('shows Unknown in the instrument itself, never a zero or a dash',()=>{
  const {container}=render(<Telemetry/>);
  const missing=container.querySelectorAll('[data-value="unknown"]');
  expect(missing.length).toBeGreaterThan(0);
  for(const cell of missing)expect(cell.textContent).toBe('Unknown');
 });

 it('labels the instrument as a Meridian fixture',()=>{
  const {container}=render(<Telemetry/>);
  expect(container.textContent).toMatch(/Meridian fixture/);
 });

 it('draws every ASK reason from the safe vocabulary',()=>{
  const {container}=render(<Telemetry/>);
  const allowed=['Conflicting rules','Missing dependencies','Revision changed'];
  const reasons=[...container.querySelectorAll('[data-ask-reason]')].map(n=>n.textContent);
  expect(reasons.length).toBeGreaterThan(0);
  for(const reason of reasons)expect(allowed).toContain(reason);
 });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ui && pnpm test -- ProofGate Telemetry`
Expected: FAIL on the copy assertions.

- [ ] **Step 3: Build the proof gate**

**Type on film, not glass** (`DESIGN.md` §3.4). 1440: columns 1–5 carry eyebrow, h2, subline and body, each in `<Reveal pattern="p1" index=n>`; columns 7–12 carry the two proof lines as a two-row stack with a `--line-strong` hairline between them, each row a `<Reveal pattern="p1">` with the figure at `--landing-metric-unit` and the qualifier beneath at `--font-size-small` in `--steel`. One `--glow-system` under this block; it is the page's second and last glow (the first was the retrieval instrument).

Read the figures from `evidence.proof_gate` rather than hard-coding them where the data supplies them (`evidence.proof_gate.matrix.wilson_upper_bound_pct`, `.harmful_mutations`, `.safe_cases`, `.microcopy`). If `evidence.proof_gate` is absent, render the section on its prose alone with no proof lines (`copy.md` §5).

390: single column, copy then the two proof lines, qualifiers never dropped, both strings wrapping.

- [ ] **Step 4: Build the telemetry instrument**

One glass panel spanning columns 2–11 at 1440, wrapped in `<Reveal pattern="p3">`: one row per team with task success, ASK count, the SEARCH → USE funnel, cost and time, and one ASK reason from the fixed vocabulary — exactly `Conflicting rules`, `Missing dependencies`, `Revision changed` and nothing else. Every missing cell carries `data-value="unknown"` and the literal word `Unknown`, never a zero and never a dash. Beneath the rows, one mono line showing a promotion gate rule. The panel carries a **visible** `Meridian fixture` label (`DESIGN.md` §7 decision 8: real rows would be a tenancy and privacy question for a public page).

Rows do not animate: `DESIGN.md` §4.6 rejects animated funnel bars — the numbers appear at their final value. Hand-built against tokens; `@spectrumui/status-tracker` is **not** installed (recorded exception, put it in the commit message).

390: each team row becomes a stacked definition list with the same labels and the same `Unknown`.

- [ ] **Step 5: Run the tests**

Run: `cd ui && pnpm test -- ProofGate Telemetry`
Expected: all seven PASS.

- [ ] **Step 6: Contracts and typecheck**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`

- [ ] **Step 7: Commit**

```bash
git add ui/src/routes/landing/ProofGate.tsx ui/src/routes/landing/proofgate.module.css ui/src/routes/landing/ProofGate.test.tsx \
  ui/src/routes/landing/Telemetry.tsx ui/src/routes/landing/telemetry.module.css ui/src/routes/landing/Telemetry.test.tsx
git commit -m "feat(landing): build the proof-gate and telemetry chapters"
```

---

## Task 10: Evidence section and the bento

**Model tier: standard.** Composition over an existing component whose internals must not move.

**Parallel group: D** (after T5 **and** T2).

**Implements:** `DESIGN.md` §3.6, §4.1 P4, §7 decision 6; `copy.md` §2 section 6.

**Files:**
- Modify: `ui/src/routes/landing/ResearchEvidence.tsx`
- Modify: `ui/src/routes/landing/landing.module.css` (the `.research*` rules only) — or move them into a new `ui/src/routes/landing/evidence.module.css` and import it from `ResearchEvidence.tsx`; prefer the move, so this task stays file-disjoint from T11
- Create: `ui/src/routes/landing/ResearchEvidence.test.tsx`

**Interfaces:**
- Consumes: the bento and ticker exports from T2 (names from T2's commit message); `Reveal` from T4; tokens from T1.
- Produces: nothing other tasks consume.

**Binding, from `copy.md` §6:** the chart, the table, the interval paragraphs, the Pi delivery-boundary trace and the `<details>` method block inside `ResearchEvidence.tsx` **stay exactly as they are**. Values keep coming from `ui/src/data/research-evidence.json` at render time, never hard-coded into markup. This task specifies only what sits **above** them, and nothing here may soften them.

**Copy, verbatim from `copy.md` §2 section 6:**

| Slot | String |
|---|---|
| Eyebrow (already rendered) | `Research update · 10 September 2026` |
| h2 (**replaces** `More relevant skills found`) | `Plus 8.53 points of recall over flat.` |
| Subline | `5,400 queries across 26,262 skills on SRA-Bench, against flat dense search.` |
| Microcopy under the figure | `Measured, exploratory offline retrieval, not completed coding tasks. Four of six datasets improved; CHAMP and TheoremQA regressed. The hierarchy came from benchmark corpus prefixes rather than real repository scopes.` |
| Second block (no figure) | `Task-level value is not settled. The delivery boundary in section 4 is deterministic and source-backed; it says nothing about whether a delivered rule helped somebody finish the work. That measurement needs real repository snapshots and frozen tasks, and we have not made it yet.` |
| Third block | `Corpora of 1k, 10k and 30k skills, cold and warm cache: in the Q6 validation plan. Designed for, not yet measured. No latency figure appears on this page until that run exists.` |
| CTAs (both existing, both kept) | `Read the evidence` · `Download results and source hashes` |

Replace the literal `section 4` in the second block with a link to `#proof-gate` whose **text is unchanged** — wrap `The delivery boundary in section 4` so the words stay verbatim while the phrase becomes navigable. If that cannot be done without altering the string, leave it as plain text.

- [ ] **Step 1: Write the failing test**

Create `ui/src/routes/landing/ResearchEvidence.test.tsx`:

```tsx
import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ResearchEvidence} from './ResearchEvidence';
import evidence from '../../data/research-evidence.json';

describe('evidence section',()=>{
 it('leads on the recall figure with its qualifier on the same screen',()=>{
  render(<ResearchEvidence/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Plus 8.53 points of recall over flat.');
  expect(screen.getByText('5,400 queries across 26,262 skills on SRA-Bench, against flat dense search.')).toBeVisible();
  expect(screen.getByText(/Four of six datasets improved; CHAMP and TheoremQA regressed\./)).toBeVisible();
 });

 it('keeps the open question and the scale envelope, neither carrying a figure',()=>{
  render(<ResearchEvidence/>);
  const open=screen.getByText(/Task-level value is not settled\./);
  expect(open).toBeVisible();
  expect(open.textContent).not.toMatch(/\d+\s*\/\s*\d+/);
  expect(screen.getByText(/Designed for, not yet measured\./)).toBeVisible();
 });

 it('renders every figure from the data file, not from markup',()=>{
  const {container}=render(<ResearchEvidence/>);
  expect(container.textContent).toContain(evidence.rates.full_pyramid.recall10.toFixed(2));
  expect(container.textContent).toContain(evidence.rates.flat.recall10.toFixed(2));
 });

 it('keeps both existing calls to action',()=>{
  render(<ResearchEvidence/>);
  expect(screen.getByRole('link',{name:'Read the evidence'})).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Download results and source hashes'})).toBeInTheDocument();
 });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && pnpm test -- ResearchEvidence`
Expected: FAIL on the h2 text.

- [ ] **Step 3: Build the bento above the existing content**

Four tiles on a 12-column span, deliberately unequal (there is no three-identical-card row anywhere on this page):

| Tile | Span | Content |
|---|---|---|
| Tall | columns 1–5, two rows | the **existing** bar chart, still lazy-loaded on intersection, with `min-block-size: var(--landing-chart-min-height)` so it never renders as an empty box |
| Wide | columns 6–12 | `+8.53 pp` and `+4.87 pp` as number tickers, with baselines `56.69 → 65.22` and `42.31 → 47.19` in tabular mono, plus the microcopy naming the regressions |
| Small | one cell | "what is still open" — **carries no figure** |
| Small | one cell | the scale envelope, with `designed for, not yet measured` set in `--warning-ink` |

Use `@spectrumui/bento-grid` and its `spotlight.tsx` from T2. Spotlight hover is used **here and nowhere else**. `border-beam.tsx` ships with the install and is imported nowhere. **No hover lift on the tiles** (`DESIGN.md` §4.6: tiles are not pressable; a lift would promise an action that does not exist). Hover vocabulary is spotlight follow plus `--line` → `--line-hover`.

P4 applies only to the two tickers (digit-only figures, `once`, 60% visible, `--duration-count` 900 ms, `--stagger-count` 40 ms). This is the **only** place P4 runs on the page. Under reduced motion the ticker renders its final value immediately.

Rule enforced by T13: no number appears without its denominator, its date and its status word.

390: the bento collapses to one column in the same DOM order, chart first.

- [ ] **Step 4: Change the h2 and add the copy blocks**

Replace `<h2 id="research-title">More relevant skills found</h2>` with `<h2 id="research-title">Plus 8.53 points of recall over flat.</h2>`. Keep `id="research-results"` on the `<section>` and `id="research-title"` on the `h2`. T12 retargets the e2e region locator to the new accessible name.

Insert the subline and the three copy blocks above the existing chart/table/interval/trace/`<details>` content. Touch none of it.

- [ ] **Step 5: Run the tests**

Run: `cd ui && pnpm test -- ResearchEvidence`
Expected: all four PASS.

- [ ] **Step 6: Contracts and typecheck**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`
A `registry-review` diagnostic means a bento or ticker file was edited: adapt by composing a wrapper in `src/routes/landing/`, not by editing the registry source. If a registry file genuinely must be edited, recompute and update its `sha256` in `ui/qa/spectrum-registry.json` and record the adaptation.

- [ ] **Step 7: Commit**

```bash
git add ui/src/routes/landing/ResearchEvidence.tsx ui/src/routes/landing/evidence.module.css ui/src/routes/landing/ResearchEvidence.test.tsx ui/src/routes/landing/landing.module.css ui/qa/spectrum-registry.json
git commit -m "feat(landing): compose the evidence bento above the existing research content"
```

---

## Task 11: Availability, waitlist, FAQ and footer

**Model tier: standard.** Restyling only, but this is the task that breaks preservation if it retypes anything.

**Parallel group: D** (after T5).

**Implements:** `DESIGN.md` §3.7, §3.8, §3.9; `copy.md` §2 sections 7–9 and §4; ruling 2.

**Files:**
- Modify: `ui/src/routes/landing/Availability.tsx`, `availability.module.css`
- Modify: `ui/src/routes/landing/Questions.tsx`, `questions.module.css`
- Modify: `ui/src/routes/landing/Footer.tsx`
- Modify: `ui/src/routes/landing/landing.module.css` (waitlist band, footer, form rules only)
- Modify: `ui/src/routes/landing/index.tsx` (the waitlist section's heading and subline only — **no other edit**; T5 owns the rest)
- Create: `ui/src/routes/landing/protected-strings.test.tsx`

**Interfaces:**
- Consumes: the protected JSX nodes relocated by T5; `Reveal` from T4; tokens from T1.
- Produces: nothing other tasks consume.

**Rule for this entire task: do not retype a protected string.** Move the existing nodes. If you must construct one, copy it character by character from `ui/design/landing/design-brief.json`'s `preservationMap`, never from `copy.md`'s tables (which are prose about the strings).

**New copy for this task, verbatim from `copy.md`:**

| Section | Slot | String |
|---|---|---|
| 7 Availability | h2 | `Clone it today. It is open.` |
| 7 | Supporting line | `Claude Code, Codex, Copilot and Gemini CLI read the same rules, Git stays the source of truth, and the registry is a build artifact you can rebuild.` |
| 7 | Link | `Read the docs` → `/docs/` |
| 8 Waitlist | h2 | `Be first on hosted Guidefold.` |
| 8 | Subline | `One email when it is ready. Nothing else.` |
| 9 FAQ | h2 | `Before you join` |
| 9 | Subline | `Price, availability, coding tools, and what happens to your email.` |

**Protected and unchanged:** `Open source today.` / `CLI and retrieval service.`; `Paid hosting is planned.` / `Sign up for availability updates.` (required in **both** section 7 and as the form's signup note); every `WaitlistForm` string, id, aria relationship, the 12 s abort, the honeypot, the success state and all four error strings; all four FAQ triggers and answers in full including `$99 per organisation per month`, the `$9`/`$10` prepaid budget, the 30-day and 365-day deletion schedule, the deduplication-hash sentence, the YouTube paragraph and the `mailto:hello@cloudfloo.io` link; `Open-source tools. Hosted service planned.` in the footer bottom; the footer group labels `Product: Play demo · Documentation · Sign in`, `Open source: GitHub · Integrations · Quickstart`, `Stay in touch: Join the waitlist · Email us · Privacy`; `Built by Cloudfloo`; the footer tagline `Instructions that stay close to the code.`; the `?confirm=` / `?unsubscribe=` flow strings.

`@spectrumui/faq-tabs-card` is **not** installed: it would re-home protected answers inside a tabbed card and put the `#privacy` anchor contract at risk for no gain (`DESIGN.md` §3.9). Record that exception in the commit message. Keep the Base UI `Collapsible`; restyling the trigger row, the caret and the panel is expected.

- [ ] **Step 1: Write the failing test**

Create `ui/src/routes/landing/protected-strings.test.tsx`. This is the preservation acceptance test and it must assert on **exact** strings including curly apostrophes:

```tsx
import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import Landing from '../landing';

const PROTECTED=[
 'Skip to content',
 'Open source today.','CLI and retrieval service.',
 'Paid hosting is planned.','Sign up for availability updates.',
 'Open-source tools. Hosted service planned.',
 'Instructions that stay close to the code.',
 'Your email','Join the waitlist','Play demo',
 'Is Guidefold available now?','What will hosting cost?','Which coding tools can I use?','How is my email used?',
];

describe('preservation contract',()=>{
 it('keeps every protected string verbatim',()=>{
  render(<Landing/>);
  for(const text of PROTECTED)expect(screen.getAllByText(text,{exact:true}).length).toBeGreaterThan(0);
 });

 it('keeps the pricing figures unrounded and unlifted',()=>{
  render(<Landing/>);
  expect(screen.getByText(/\$99 per organisation per month, excluding taxes\./)).toBeInTheDocument();
  expect(screen.getByText(/\$9 of provider usage costs \$10/)).toBeInTheDocument();
  expect(screen.getByText(/There is no unlimited AI allowance\./)).toBeInTheDocument();
  expect(screen.getByText(/Enterprise SSO is not included/)).toBeInTheDocument();
 });

 it('keeps the full privacy answer including both deletion schedules',()=>{
  render(<Landing/>);
  expect(screen.getByText(/Unconfirmed signups are scheduled for deletion after 30 days/)).toBeInTheDocument();
  expect(screen.getByText(/deletion 365 days after signup/)).toBeInTheDocument();
  expect(screen.getByText(/a deduplication hash is retained until deletion/)).toBeInTheDocument();
 });

 it('keeps both required instances of the hosting statement',()=>{
  render(<Landing/>);
  expect(screen.getAllByText('Paid hosting is planned.',{exact:true}).length).toBe(2);
 });

 it('links Try the open-source version exactly twice: section 3 and the footer',()=>{
  const {container}=render(<Landing/>);
  const links=[...container.querySelectorAll('a')].filter(a=>a.textContent==='Try the open-source version');
  expect(links).toHaveLength(2);
 });

 it('glues no directional glyph to any link label',()=>{
  const {container}=render(<Landing/>);
  for(const a of container.querySelectorAll('a'))expect(a.textContent??'').not.toMatch(/[→←↑↓➔]/);
 });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && pnpm test -- protected-strings`
Expected: FAIL on the two-instance assertion and/or the new section copy.

- [ ] **Step 3: Restyle the availability band**

Solid band: `--graphite-900` over `--film-scrim-band`, because reading matters more than atmosphere here. 1440: h2 columns 1–4; the two protected statements columns 6–12 side by side with one hairline between them (`--landing-availability-rule`); supporting line beneath at `--landing-measure` 60ch; `Read the docs` link. 390: stacked, the hairline becomes a top rule on the second statement (`--landing-availability-rule-top`). The band's own `Try the open-source version` link stays removed.

- [ ] **Step 4: Restyle the waitlist band**

Solid band. 1440: h2 and subline columns 1–5, form columns 7–12, one hairline between. 390: stacked, input and button full width at `--touch-height` minimum, and the consent checkbox target 44 px including its label row. Change **only** the heading and subline text in `index.tsx`; `WaitlistForm` itself is untouched. The `?confirm=` / `?unsubscribe=` branch still renders instead of every marketing section and never mounts the film.

- [ ] **Step 5: Restyle the FAQ**

Solid band. h2 `Before you join`, subline `Price, availability, coding tools, and what happens to your email.` The four protected answers stay in full inside the Base UI `Collapsible` with ids `question-1`, `question-2`, `question-3`, `privacy`, all panels closed on load, hash deep-linking and the consent-link behaviour intact. Trigger rows are ≥ 44 px at 390. Caret rotation 180 ms, panel height and opacity 180 ms, Base UI transition, interruptible.

- [ ] **Step 6: Restyle the footer**

The footer closes section 9 rather than opening a tenth: four link groups, the protected bottom line, its own `Try the open-source version` link, and the large wordmark (`--landing-footer-wordmark`), sitting on the film's terminal frame so the folded map and the wordmark share the last screen. Labels unchanged.

- [ ] **Step 7: Run the tests**

Run: `cd ui && pnpm test -- protected-strings`
Expected: all six PASS.

- [ ] **Step 8: Contracts and typecheck**

Run: `cd ui && pnpm typecheck && pnpm test:contracts`

- [ ] **Step 9: Commit**

```bash
git add ui/src/routes/landing/Availability.tsx ui/src/routes/landing/availability.module.css \
  ui/src/routes/landing/Questions.tsx ui/src/routes/landing/questions.module.css \
  ui/src/routes/landing/Footer.tsx ui/src/routes/landing/landing.module.css \
  ui/src/routes/landing/index.tsx ui/src/routes/landing/protected-strings.test.tsx
git commit -m "feat(landing): restyle availability, waitlist, FAQ and footer with every protected string intact"
```

---

## Task 12: Tests — unit, e2e, axe

**Model tier: standard.** Each breakage is named; the work is retargeting, not invention.

**Parallel group: E** (after all of D).

**Implements:** `DESIGN.md` §5 focus-order, targets, keyboard-flow, axe and reduced-motion rows; the accessibility contract's proof-from-test rule.

**Files:**
- Modify: `ui/src/routes/Landing.test.tsx`
- Modify: `ui/e2e/landing-flow.spec.ts`
- Modify: `ui/e2e/accessibility.spec.ts` if it asserts landing copy

**Interfaces:**
- Consumes: everything from T5–T11.
- Produces: a green suite.

**`ui/src/routes/Landing.test.tsx` is already green when this task starts** — T5 fixed the h1, the section order, the `#how-it-works` destination and the email-branch film assertion, and T9/T10/T11 added their own files. This task only **adds** the three tests below to it. If any assertion in it is red on arrival, stop and report: a group-D task shipped without running its gate.

**Named breakages in `ui/e2e/landing-flow.spec.ts`:**

| Line | Assertion | Fix |
|---|---|---|
| 10 | `getByRole('region',{name:'More relevant skills found'})` | → `{name:'Plus 8.53 points of recall over flat.'}` (T10 changed the `h2`) |
| 11 | `getByRole('link',{name:/New research:/}).click()` | that string is removed by `copy.md` §3 → `getByRole('link',{name:'Read the numbers and how we got them'}).click()` |
| 37 | `h1` equals `Team rules. Right where agents work.` | → `Your repos are already writing the handbook.` |
| 39–41 | the three `h2` texts | → `One team's fix becomes everyone's rule.`, `Thirty thousand rules. Four reach the agent.`, `Seventy-six harmful rules. Seventy-six refusals.` |
| 100 | `[class*="routeLine"]` strokeDashoffset `0px` under reduced motion | `RouteRule` is deleted → retarget to `[data-tier-route]` in the extraction chapter, whose resting value is also the finished line (`DESIGN.md` §4.2) |
| 110 | reversibility read of `[class*="plane"],[class*="topo"],[class*="survey"]` | those planes belong to deleted sections → retarget to the film layer and the parallax layers: `[class*="film"],[data-beat],[class*="proofRail"]`, asserting identical `transform` before and after a full scroll down and back |

- [ ] **Step 1: Confirm the unit suite is green on arrival**

Run: `cd ui && pnpm test`. Expected: green. Do not proceed on a red suite.

- [ ] **Step 2: Add the keyboard-order unit test**

```tsx
 it('puts the skip link first and keeps DOM order equal to reading order',()=>{
  const {container}=render(<Landing/>);
  const focusable=[...container.querySelectorAll('a[href],button:not([disabled]),input,summary,[tabindex]:not([tabindex="-1"])')];
  expect(focusable[0]).toHaveTextContent('Skip to content');
  expect(container.querySelector('[style*="order"]')).toBeNull();
 });
```

- [ ] **Step 3: Add the citable-evidence acceptance test**

```tsx
 it('publishes only the citable figures',()=>{
  const {container}=render(<Landing/>);
  const text=container.textContent??'';
  expect(text).toContain('76 of 76 harmful rules refused.');
  expect(text).toContain('4.81%');
  expect(text).toContain('+8.53 pp Recall@10 on SRA-Bench.');
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/16\s*\/\s*20/);
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/\b\d+(\.\d+)?\s?(ms|milliseconds)\b/);
  expect(text.toLowerCase()).not.toContain('zero risk');
 });
```

- [ ] **Step 4: Fix the e2e file**

Apply every row of the second table. Add one test for the pinned chapter at 1440 and its stacked form at 390:

```ts
test('the extraction chapter pins at 1440 and stacks at 390',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/');
 const stage=page.locator('#extraction [data-stage]');
 await expect(stage).toHaveCSS('position','sticky');
 for(const beat of ['1','2','3'])await expect(page.locator(`#extraction [data-beat="${beat}"]`)).toBeAttached();
 await page.setViewportSize({width:390,height:844});
 await expect(stage).not.toHaveCSS('position','sticky');
 for(const beat of ['1','2','3'])await expect(page.locator(`#extraction [data-beat="${beat}"]`)).toBeVisible();
 expect(await noHorizontalScroll(page)).toBe(true);
});
```

- [ ] **Step 5: Add the 44 px target test at 390**

```ts
test('every control meets 44px at 390',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/');
 const controls=page.locator('main a[href], main button:not([disabled]), main input[type="checkbox"]');
 const count=await controls.count();
 for(let i=0;i<count;i++){
  const box=await controls.nth(i).boundingBox();
  if(!box)continue;
  expect(box.height,`control ${i} height`).toBeGreaterThanOrEqual(44);
 }
});
```

If a text link inside a paragraph fails this, exempt inline links explicitly by narrowing the locator to `[data-slot="button"], .scrollCue, summary, input` and say so in the commit message — do not raise inline link heights and reflow the prose.

- [ ] **Step 6: Add the axe pass with the FAQ open and the dialog open**

```ts
for(const size of viewports)test('axe is clean with the FAQ open and the dialog open at '+size.width,async({page})=>{
 await page.setViewportSize(size);
 await page.goto('/');
 expect(await axeViolations(page)).toEqual([]);
 await page.getByRole('button',{name:'How is my email used?'}).click();
 expect(await axeViolations(page)).toEqual([]);
 await page.getByRole('button',{name:'Play demo',exact:true}).click();
 expect(await axeViolations(page)).toEqual([]);
});
```

- [ ] **Step 7: Run everything**

```bash
cd ui && pnpm exec playwright install chromium
cd ui && pnpm test && pnpm test:e2e
```

Expected: both green. If `pytest`-style output is garbled by the rtk hook, re-run through `rtk proxy`.

- [ ] **Step 8: Commit**

```bash
git add ui/src/routes/Landing.test.tsx ui/e2e/landing-flow.spec.ts ui/e2e/accessibility.spec.ts
git commit -m "test(landing): retarget the landing suite at the v2 structure and copy"
```

---

## Task 13: QA gate and the implemented-system record

**Model tier: capable.** Judgement calls: the anti-slop screenshot test, the contrast measurement over a moving film, and writing the record that replaces the direction.

**Parallel group: F** (after T12). Last task.

**Implements:** `DESIGN.md` §5 in full, §6 screenshot test, §8 handoff checklist; `cloudfloo-quality-gate`; `definition-of-done`.

**Files:**
- Rewrite: `ui/src/routes/landing/DESIGN.md` (the **implemented-system** record — what was built, not what was proposed)
- Create: `ui/qa/landing-v2-gate.json`
- Modify: `docs/reports/readme/build-notes.md` (the route-chunk gzip numbers)
- Screenshots land under `ui/qa/`

**Interfaces:**
- Consumes: the finished page.
- Produces: the gate record and the implemented-system document.

- [ ] **Step 1: Run the full command sequence**

```bash
cd ui
pnpm typecheck
pnpm build
pnpm test
pnpm test:contracts
pnpm test:e2e
```

Record each command, its result, the test count and the elapsed time. A skip is "not measured here", not a pass.

- [ ] **Step 2: Measure the JS budget against Task 1's recorded baseline**

```bash
cd ui && pnpm build
cd ui && ls -l dist/assets | grep -i landing
cd ui && gzip -c dist/assets/<landing-chunk>.js | wc -c
```

Compare against the **pre-change baseline Task 1 recorded** in `docs/reports/readme/build-notes.md`. Do **not** use `git stash` to recreate the baseline: the branch carries ~137 unrelated dirty files and a stash round trip risks exactly the loss ruling 7 exists to prevent.

Requirement: the increase is **≤ +34 KB gzipped**. The allowance must absorb the bento grid (four files), the number ticker plus its `lib/ease.ts`, and the new anchor and entrance code. Record both absolute numbers and the delta in `docs/reports/readme/build-notes.md` and in the gate record. If it is over budget, the fix is to drop the bento install and hand-build the four tiles, not to widen the budget.

- [ ] **Step 3: Capture the screenshot matrix**

Serve the production bundle (`pnpm preview`), then capture, via Playwright:
- full page at **1440×900** and **390×844**;
- viewport captures at each of the nine section anchors (`#hero`, `#extraction`, `#how-it-works`, `#proof-gate`, `#telemetry`, `#research-results`, `#availability`, `#waitlist`, `#questions`);
- one capture at the pinned chapter's mid-beat;
- one with reduced motion forced (`emulateMedia({reducedMotion:'reduce'})`);
- one with the film failed (route-block `**/hero-flight.*`).

Record console and network errors during the pass; any error is a gate failure.

- [ ] **Step 4: Run the anti-slop screenshot test**

1. Remove the logo and wordmark from the 1440 capture. Ask someone outside the project what the product does. An answer of the shape "some AI dashboard" or "a generic SaaS landing page" is a **P1**. A correct answer names rules, a hierarchy, or agents getting the right instructions.
2. On the same de-logoed capture, verify at least one screen shows a **real artefact** — a path, a `SKILL.md`, a tier count, a funnel row — rather than only prose.
3. Diff the reduced-motion capture against the normal one: all the same content must be present.
4. Read-aloud test on every new string: read it as if to a colleague; rewrite anything you would not say.
5. Grep the diff for banned words, `→` in link text, and any literal colour or dimension in a CSS module:

```bash
cd ui && grep -rn '#[0-9a-fA-F]\{3,6\}' src --include=*.css --include=*.tsx | grep -v tokens/tokens.css
cd ui && node qa/check-contracts.mjs
```

Both must return nothing / pass.

Record tests 1 and 4 in the change description by name and outcome.

- [ ] **Step 5: Measure contrast over the film**

Extract frames at each §3.0 anchor plus the sunrise window (0.0–1.4 s, the brightest the film ever gets):

```bash
cd ui/public/assets/landing
for t in 0.0 0.7 1.4 4.2 5.6 6.8 7.8 8.6 9.1 9.7 10.0; do
  /usr/bin/ffmpeg -y -ss $t -i hero-flight.mp4 -frames:v 1 /tmp/frame-$t.png
done
```

Composite each frame with its section's scrim and measure the ratio inside that section's copy-safe region: body ≥ 4.5:1, large text ≥ 3:1, hero display ≥ 7:1. Record the measured pairs, not a declaration. If a region fails, raise the scrim for that region only — a page-wide slab is the defect this rebuild removes.

- [ ] **Step 6: Trace the frame budget**

DevTools performance trace, scroll top to bottom and back, at 1440 and at 390 with 4× CPU throttling. Requirement: main-thread work under 4 ms per frame, **long-task count 0**. Also confirm: one rAF, one passive scroll listener, one resize listener, at most two `IntersectionObserver`s; no `backdrop-filter` active while `[data-film="on"]`; `will-change` on the film layer and the pinned stage only; no `content-visibility: auto` anywhere.

- [ ] **Step 7: Verify LCP and CLS**

Lighthouse at 1440 and on the mobile profile. Assert the LCP element is `hero-poster.webp` and LCP ≤ 2.0 s on a throttled 4G profile. Assert **CLS 0** — run a scroll pass with layout-shift logging as well as the Lighthouse number. If the proof rail text became the LCP element, the poster is not painting first: fix the ordering, do not accept the number.

- [ ] **Step 8: Write the gate record**

Create `ui/qa/landing-v2-gate.json`. Every check records `pass`, `fail` or `not_applicable`, with evidence and remediation. Build, security, critical accessibility, preservation, artifact or secret failure **blocks publishing**; do not downgrade a critical failure to a warning.

```json
{
  "schemaVersion": 1,
  "capturedAt": "<ISO timestamp>",
  "spec": "ui/design/landing/v2/",
  "evidenceLevel": "R",
  "checks": [
    {"id":"typecheck","status":"pass","evidence":"pnpm typecheck, 0 errors"},
    {"id":"build","status":"pass","evidence":"pnpm build, <n> modules, <t>s"},
    {"id":"unit","status":"pass","evidence":"pnpm test, <n> passed"},
    {"id":"contracts","status":"pass","evidence":"node qa/check-contracts.mjs, result passed, <n> tokens"},
    {"id":"e2e","status":"pass","evidence":"pnpm test:e2e, <n> passed"},
    {"id":"js-budget","status":"pass","evidence":"landing chunk <before> -> <after> gzip, delta +<d> KB, budget 34 KB"},
    {"id":"lcp","status":"pass","evidence":"hero-poster.webp, <t>s throttled 4G"},
    {"id":"cls","status":"pass","evidence":"0"},
    {"id":"frame-budget","status":"pass","evidence":"<t>ms/frame peak, 0 long tasks, 1440 and 390 at 4x CPU"},
    {"id":"contrast-over-film","status":"pass","evidence":"per-region measured ratios at 11 sampled frames"},
    {"id":"targets-390","status":"pass","evidence":"Playwright bounding boxes, min <n>px"},
    {"id":"keyboard","status":"pass","evidence":"skip link to footer, manual pass"},
    {"id":"axe","status":"pass","evidence":"1440 and 390, FAQ closed and open, dialog open"},
    {"id":"reduced-motion","status":"pass","evidence":"no video element, content diff empty"},
    {"id":"preservation","status":"pass","evidence":"protected-strings.test.tsx, <n> assertions"},
    {"id":"citable-evidence","status":"pass","evidence":"no 17/20, no 25/25, no latency figure, no zero-risk phrasing"},
    {"id":"anti-slop-screenshot","status":"pass","evidence":"<the answer the outside reader gave>"},
    {"id":"console-network","status":"pass","evidence":"0 errors across the capture pass"}
  ],
  "limits": [
    "Source and browser checks at R level on this machine; not a pilot measurement.",
    "The 30k scale envelope is designed for, not measured; no latency figure is published.",
    "Contrast measured on composited frames sampled at the anchor map, not on every frame."
  ]
}
```

- [ ] **Step 9: Rewrite `ui/src/routes/landing/DESIGN.md` as the implemented-system record**

This file currently carries the v1 direction, including the rules the owner verdict overrode. Rewrite it to describe **what was built**, with a header carrying status, date, purpose, inputs and replacement scope per `docs/DOCUMENTATION-RULES.md`. It must state:
- status `Implemented`, date `2026-09-11`, and that `ui/design/landing/v2/DESIGN.md` is the direction it implements;
- the nine sections, their ids and what each renders;
- the token deltas added, by name;
- the four entrance patterns as implemented, including which of P1–P4 each section uses and that P4 runs only in the evidence bento;
- the anchor map and its nine playhead seconds;
- the media contract as it stands (poster first, conditional mount, reduced motion and Save-Data render posters only, 8 s watchdog, pause rules);
- the Spectrum decisions: `bento-grid` and `number-ticker` installed with provenance; the recorded exceptions for the pinned stage, `faq-tabs-card`, `status-tracker`, `orbital-letters` and the marquee, each with its obstacle;
- the "What must not come back" list, updated: which bans the owner verdict lifted (section entrance motion, scroll-triggered content motion, the 240 ms ceiling, the single-hero-entrance rule) and which stand (3D pyramid, WebGL atmosphere, schema-flow canvas, autoplaying demos, typewriter, shine sweep, per-word reveals, `MorphButton`, new dependencies, new fonts, new icon libraries);
- the measured numbers from step 8, with what they do and do not prove.

Do not describe anything as done that was not checked by a command in this task.

- [ ] **Step 10: Final verification**

```bash
cd ui && pnpm build && pnpm test && pnpm test:contracts && pnpm test:e2e
git status --porcelain
```

`git status` must show only this task's files as unstaged; the ~137 unrelated dirty files must be exactly as they were at the start of the work. Compare against the snapshot in the task brief if in doubt.

- [ ] **Step 11: Commit**

```bash
git add ui/src/routes/landing/DESIGN.md ui/qa/landing-v2-gate.json docs/reports/readme/build-notes.md
git commit -m "docs(landing): record the implemented v2 system and its quality gate"
```

**Do not write `ui/qa/*.png` on the `git add` line.** QA screenshots under `ui/qa/` are untracked and not gitignored — the branch already carries dozens of unrelated untracked captures (`fold-film-*.png`, `landing-faq-*.png`, `demo-first-*.png`, …) and a glob would stage every one of them, which is exactly what ruling 7 forbids. If a specific new capture must be committed, name that one file explicitly. The gate record references the captures by filename; it does not require them to be in Git.

---

## Self-review

**Spec coverage.** `copy.md` sections 1–9: hero T5, extraction T7, retrieval T8, proof gate T9, telemetry T9, evidence T10, availability T11, waitlist T11, FAQ T11; §4 protected strings T5 (relocation) and T11 (acceptance test); §5 microcopy T5 (nav, scroll cue, buttons) and T11 (footer, empty states). `DESIGN.md` §2 tokens T1; §3.0 anchor map T6; §3.1–3.9 T5, T7–T11; §4.1 P1–P3 T4, P4 T10; §4.2 scrub T6, pin and parallax T7; §4.3 hover and press T5, T7–T11 in their own modules; §4.4 T4, T6; §5 T13; §6 T13; §7 decisions 1 (T3), 3 (T7), 4 (T5), 5 (T11), 6 and 7 (T2), 8 (T9), 9 and 10 (conflict table); §8 handoff checklist T13. `components.md` install constraints T2; check-contracts constraints in Global Constraints and every task's verification. `value-brief.md` pillars 1–10 map onto sections 2, 3, 5, 4, 5, 7, 3, 4, 6, 7 respectively.

**Placeholders.** None: every test is written out, every token has a value, every copy string is quoted in the task that renders it, every command is executable.

**Type consistency.** `Reveal` / `RevealGroup` / `useRevealed` (T4) are used by the same names in T5 and T7–T11. `FILM_ANCHORS` / `playheadAt` / `Anchor` (T6) appear only in T6. `evidence.proof_gate.microcopy` (T1) is read by T5 and T9 under that exact path. The nine section ids are identical in T5's test, T6's constant and T12's e2e. Data attributes are consistent: `data-beat`, `data-tier-route`, `data-decision`, `data-delivered-card`, `data-proof`, `data-value`, `data-ask-reason`, `data-stage`, `data-reveal-ready`, `data-reveal-entered`, `data-reveal-slot`.
