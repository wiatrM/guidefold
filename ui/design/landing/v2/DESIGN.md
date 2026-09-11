# Guidefold landing v2 — design direction

Status: proposed direction for the plan writer, 2026-09-11. Author: design direction pass.
This file is the **system**; it is not an implementation and nothing under `ui/src` may be changed
on the basis of this file alone.

## 0. Authority and inputs

Authority order, highest first:

1. **Preservation contract** (`preservationMap` in `ui/design/landing/design-brief.json`, summarised in
   `ui/design/landing/DESIGN.md` §2). "Rebuild from zero" does **not** reach these strings.
2. **Owner verdict, 2026-09-11**: the page reads as generated filler, no marketing, nothing that
   invites curiosity, too much text, wrong structure. Rebuild the content on premium components,
   keep the film, Awwwards level, professional entrance animation on scroll.
3. **Owner value brief** (`v2/value-brief.md`): three pillars in order, extraction → retrieval →
   telemetry and gated promotion, plus seven supporting pillars. Hero shows the value at first sight.
4. **Component inventory** (`v2/components.md`) and the contract checker it documents.
5. `docs/ui/UI.md`, `docs/ui/UX.md` §6, this project's tokens, then craft skills as reference.

What the owner verdict overrides in `ui/src/routes/landing/DESIGN.md`: the rules "no section reveals",
"no scroll-triggered content motion", "nothing exceeds 240 ms", and the single hero entrance. What it
does **not** override: the media contract (poster first, conditional mount, reduced motion and
Save-Data render posters and create no video element), the scroll engine (one rAF, one passive
listener, `--p` written to the element and consumed in CSS), the token-only rule, and the standing
bans in "What must not come back" (3D pyramid, WebGL hero atmosphere, schema-flow canvas,
autoplaying feature demos, typewriter, shine sweep, new fonts, new icon library).

**Protected strings, unchanged and verbatim, restyling only.** The waitlist form and every string,
id and aria relationship in it, the 12 s abort, the honeypot, the success state, all four error
strings, the `?confirm=` and `?unsubscribe=` flows, all four FAQ answers in full including the $99
and $9/$10 figures and the complete privacy answer, `Open source today.`, `Paid hosting is planned.`,
every GitHub URL, `/docs/`, `mailto:hello@cloudfloo.io`, the `#privacy` anchor, the YouTube demo
`e350wBr1W8c` behind **Play demo**, the document title, the skip link, and the Meridian fixture
excerpt with its "not a live run" label. Each section below repeats its own protected items.

Copy status: **`v2/copy.md` exists and is binding** (read 2026-09-11). Its nine-section structure,
its headline, subline and body lengths, its figure-plus-qualifier rule, its protected-string
checklist and its own anti-slop self-check govern §3 of this file; where an earlier draft of this
direction differed, `copy.md` wins and §3 has been rewritten to it. This file does not restate the
copy; it specifies where each block sits, what carries it and how it moves.

---

## 1. Direction

### The concept

The film is not a background. It is **one continuous survey flight, and the page is its subtitle
track**: a cartographer's table above the clouds where one orange route has been drawn by a person,
the camera falls into that terrain until the contours become real ground, a few cream cards stand up
around a single lit marker, the ground resolves into stacked plateaus with the route climbing from
the crowded lower tier to the sparse upper one, and the flight ends with the map folded and standing
on the desk with the route running across its folds. That sequence already *is* the product argument:
rules are written on the ground where the work happens, the reusable part is lifted out, it lands one
level up, and what the organisation ends up holding is a single folded map. The page keeps the film
on screen from the first pixel to the last, never cuts to a different world, and moves the playhead
with the reader's own scroll, so the visitor is flying the survey rather than watching an ambient
loop behind text. Panels of real product surface (a scope tree, a SEARCH result with four cards, an
organisation telemetry excerpt) rise **onto** that terrain as glass instruments, which is the only
place translucency is allowed, because an instrument over a map is the one material that has a
reason to be see-through.

Archetype, in the vocabulary of `direct-motion-site-prompts`: **Scroll film** (meaningful
intermediate frames carry a transformation), one archetype for the whole page, with parallax,
stagger and glass as mechanics rather than second theses.

### References and the mechanic taken from each

| Reference | Mechanic borrowed |
|---|---|
| Apple AirPods Pro / Mac product pages | Scroll-scrubbed product film with a **pinned stage**: the media holds still in the viewport while copy beats advance over it, and the playhead is a pure function of scroll position, so reverse scroll is exact. We take the pinned chapter and the "one media, many captions" discipline. |
| Stripe Sessions / Stripe product pages | **Instruments over atmosphere**: real product surfaces, rendered at real fidelity with real strings, placed as flat panels over an atmospheric field. Credibility comes from the panel being a genuine artefact, not a stylised icon. |
| Linear (releases and changelog pages) | **Typographic rank over decoration**: a very large display line, one quiet lede at a short measure, and a hairline that separates rather than a card that boxes. Also the restraint of one accent colour used as meaning. |
| Rauno Freiberg's interface experiments (rauno.me) | **Hairline geometry and origin-aware motion**: 1 px rules that carry structure, transforms that start where the trigger is, and entrances measured in a dozen pixels rather than a hundred. |
| Corpus reference 006, asymmetric studio hero over a spatial loop (`direct-motion-site-prompts`) | Dark void with one bright focal portal, copy anchored left at top and bottom, `object-position` controlled per breakpoint, simple entrance cascade. |
| Corpus reference 003, bottom-anchored video hero with glass utility cards | Value statement and **proof at the lower edge** of the hero frame, breakpoint-dependent foreground contrast, glass reserved for real utilities. |
| Corpus reference 001, layered landmark sticky-scroll | Reversible scroll segments driven from CSS custom properties, story panels in semantic order, late reveal of an interactive element. |

Rejected references: any horizontal-scroll journey (fights the film's vertical fall and the keyboard
flow), any custom-cursor or WebGL atmosphere layer (standing ban, and the film already supplies
atmosphere), any page-transition system (single-route page).

### Three things that stop this reading as a template

1. **The film is load-bearing and the page never leaves it.** There is one visual protagonist for
   nine sections and the playhead is mapped to named beats, so the retrieval section literally shows
   the four cards standing around one lit marker and the safety section literally shows the route
   crossing a boundary. A template puts a video in the hero and a flat grey background under
   everything else.
2. **The proof is typeset as instrumentation, not as marketing.** Every figure is set in tabular mono
   at headline weight with its qualifier rendered underneath at every breakpoint, carrying the
   denominator, the date and the status words the copy assigns it, and one whole block carries no
   figure at all because what it says is that the question is still open. A page that publishes its
   own regressions and its own missing measurement is not a page a generator writes.
3. **Structure encodes the argument, not symmetry.** There is no three-identical-card row anywhere.
   Extraction is a pinned three-beat chapter because it is genuinely a sequence, the evidence section
   is an asymmetric bento because one tile holds a chart and another deliberately holds no number,
   and the availability band is two statements because there are exactly two facts.

### Dials

`DESIGN_VARIANCE` 8 (asymmetric, film-led, deliberate scale contrast; not 10, because the product is
bought by engineers who are checking whether it is real). `MOTION_INTENSITY` 7 (scrubbed film and
scroll entrances, no scroll-jacking, no ambient loops). `VISUAL_DENSITY` 6 (generous around the
display type, dense inside the instruments).

### What the current page gets wrong (source audit, from the 1440 and 390 captures)

Single left column at roughly half width with the right half empty for the entire page; the film
sitting at `.62` opacity under a scrim heavy enough that the survey table is invisible; three
identical role cards; prose paragraphs where the argument needs a diagram; an all-caps tracked
eyebrow over the hero; a trailing `→` glued to every link string; the proof number set in body copy;
and at 390 the sticky navigation covering the first line of the `h1`. Every one of these is on the
generated-page tell list in `frontend-design` or UX §6.

---

## 2. Visual system deltas

Everything here is a **delta on `ui/src/tokens/tokens.css`**. No second palette, no second type
scale, no second motion vocabulary. `qa/check-contracts.mjs` rejects a custom property declared
anywhere else, a literal colour or dimension in a CSS module and a literal breakpoint in a module
media query, so every value below is a token and every responsive change is a token redefined in the
existing `1080px` and `720px` blocks.

### 2.1 Typography

Fonts are the three already loaded: **Instrument Sans** (display), **Manrope** (body), **JetBrains
Mono** (data). No font is added and none is fetched.

| Role | Family | Token | Value |
|---|---|---|---|
| Hero display | Instrument Sans 600 | `--landing-display` | `clamp(46px,6.4vw,92px)` |
| | | `--landing-display-leading` | `1.02` |
| | | `--landing-display-tracking` | `-.035em` |
| Hero lede | Manrope 400 | `--landing-kicker` | `clamp(19px,1.5vw,23px)` |
| | | `--landing-kicker-measure` | `34ch` |
| Section heading (h2) | Instrument Sans 600 | `--landing-heading` **(value change)** | `clamp(30px,3.2vw,46px)`, was `clamp(28px,3vw,38px)` |
| Beat heading (h3) | Instrument Sans 600 | `--landing-h3` | `20px` |
| Body | Manrope 400 | `--landing-body` **(value change)** | `17px`, was `16px`; measure `--landing-copy-width` `46ch`, was `48ch` |
| Metric | JetBrains Mono 500, `font-variant-numeric: tabular-nums` | `--landing-metric` | `clamp(34px,3.4vw,52px)`, leading `--landing-metric-leading` `1` |
| Metric unit / delta | JetBrains Mono 500 | `--landing-metric-unit` | `16px` |
| Data label, path, URN, status | JetBrains Mono 400 | `--font-size-code` `12px`, `--landing-tracking-mono` `.04em` |
| Caption, source line, date | Manrope 400 | `--font-size-small` `12px` |

**Renames versus value changes.** Tokens marked *(value change)* keep their existing names and are
edited in place, because `landing.module.css` already references them and a surviving `var()` whose
declaration disappeared resolves to nothing and silently loses the size. New names are reserved for
genuinely new roles: `--landing-display`, `--landing-display-leading`, `--landing-display-tracking`,
`--landing-kicker`, `--landing-kicker-measure`, `--landing-h3`, `--landing-metric`,
`--landing-metric-leading`, `--landing-metric-unit`, `--landing-tracking-mono`, and the glass,
material and motion tokens in §2.2 and §4. The existing `--landing-title` and `--landing-lede` keep
their names; `--landing-title` is superseded on this page by `--landing-display` for the `h1` and
stays declared for any other consumer. If a rename is unavoidable, `tokens.css` and every consuming
module change in the same commit.

Rules. One `h1`. One `h2` per section. `h3` only inside the mechanism beats and the FAQ triggers.
**No all-caps tracked eyebrow above any heading** (the current `--tracking-label` eyebrow is retired
from this page; it survives only as a mono data label inside instruments, where it labels a value
rather than announcing a section). **No single accented word inside a headline.** No `→` appended to
link text; a directional glyph appears only as an icon element with `aria-hidden`, and only on the
two primary actions. Body never exceeds 46ch, the hero lede never exceeds 34ch, no line of display
type wraps to more than three lines at 390.

### 2.2 Colour roles over film

Palette is unchanged: graphite ground, stone ink, `--survey-teal` for the system, `--safety-orange`
for the one place a person decided. Orange still appears at most twice on the page. What is new is
that the film is now visible, so contrast is a **local** treatment rather than one page-wide slab.

| Role | Token | Value |
|---|---|---|
| Film opacity when running | `--landing-film-opacity` | `.86` at ≥1080, `.7` at 720 (raised from `.62`; the film has to be legible for the concept to work) |
| Hero copy-safe scrim | `--film-scrim-hero` | `linear-gradient(100deg,rgba(7,9,12,.94) 0%,rgba(7,9,12,.8) 34%,rgba(7,9,12,.1) 66%,rgba(7,9,12,0) 100%)` |
| Chapter scrim (pinned stage) | `--film-scrim-chapter` | `radial-gradient(120% 90% at 30% 55%,rgba(7,9,12,.86) 0%,rgba(7,9,12,.52) 48%,rgba(7,9,12,.24) 100%)` |
| Band scrim (text bands) | `--film-scrim-band` | `linear-gradient(180deg,rgba(7,9,12,.58) 0%,rgba(7,9,12,.86) 100%)` |
| Glass panel | `--glass-panel` | `rgba(12,16,20,.62)` |
| Glass panel, instrument | `--glass-panel-strong` | `rgba(12,16,20,.86)` |
| Glass blur | `--glass-blur` | `14px` while the film is **not** running; **`0px` while it is** (see below) |
| Glass border | `--glass-border` | `rgba(163,173,182,.16)` |
| Glass top highlight | `--glass-highlight` | `linear-gradient(180deg,rgba(238,241,243,.06),rgba(238,241,243,0) 38%)` |
| Route glow (used once) | `--glow-route` | `0 0 0 1px rgba(255,122,61,.24),0 14px 44px -20px rgba(255,122,61,.45)` |
| System glow (used once) | `--glow-system` | `0 0 0 1px rgba(63,184,177,.2),0 14px 44px -22px rgba(63,184,177,.4)` |
| Tier fills (scope pyramid) | `--tier-1..--tier-4` | `rgba(63,184,177,.26)`, `.2`, `.14`, `.09` |
| Status label ink | reuse `--system-ink`, `--warning-ink`, `--steel` | verified / feasibility / not measured |

Contrast contract: body ≥ 4.5:1, large text ≥ 3:1, hero display ≥ 7:1, each measured against the
**brightest sampled frame inside its own copy-safe region**, not against the token ground. Sample
frames at the anchors in §3 and at the sunrise window frame (0.0–1.4 s), which is the brightest the
film ever gets. Colour is never the only carrier of meaning: every status label carries a word.

### 2.3 Spacing rhythm

One rhythm, based on the existing 8 px scale. Sections breathe far more than today; instruments stay
dense.

| Token | Value (≥1080) | 720 |
|---|---|---|
| `--landing-section-padding` | `clamp(104px,9vw,168px)` | `72px` |
| `--landing-band-gap` | `clamp(32px,3.2vw,56px)` | `24px` |
| `--landing-panel-pad` | `clamp(20px,2vw,32px)` | `16px` |
| `--landing-bento-gap` | `12px` | `10px` |
| `--landing-stage-height` | `100dvh` (pinned chapter stage) | `auto` (pin disabled) |
| `--landing-measure-gutter` | `clamp(24px,6vw,120px)` (offset of copy from the film's focal side) | `0` |

Grid: one 12-column container at `--landing-width` `1400px` with `--landing-gutter`
`clamp(20px,4vw,64px)`. Every section places on that one grid; the variation between sections comes
from **which columns are used**, never from a new container. Column plans are in §3.

### 2.4 Materials

Exactly **two radii** on the page, which is a system rather than a mix: `--landing-radius` `8px` for
controls, inputs, insets and small tiles, and `--landing-radius-panel` `16px` for large glass
panels and the pinned stage. Nothing else is rounded.

Three surfaces, in order of weight:

1. **On the film.** Type and hairlines only, over a bounded local scrim. No box. Used for the hero,
   the problem statement and each chapter beat caption.
2. **Glass panel** (`--glass-panel`, `--glass-blur`, 1 px `--glass-border`, `--glass-highlight` on the
   top edge only). Used where a real product surface sits over the terrain. Glass is never used for
   decoration and never for a text block that could be typed directly onto the film.
3. **Solid band** (`--graphite-900` over `--film-scrim-band`). Used where reading matters more than
   atmosphere: the FAQ, the footer, and the waitlist form.

**Blur is switched off while the film is scrubbing.** `backdrop-filter` repaints its backdrop every
time the backdrop paints, so a blurred panel over a video whose `currentTime` is being rewritten
costs a full-viewport blur pass per film frame, which is the single most likely way to miss the 4 ms
budget in §5. `FilmBackdrop` already sets `data-film="on"` on the document root when the film is
actually running. Bind the material to it, as a token swap rather than a module media query:

```
:root            { --glass-blur: 14px; --glass-ground: var(--glass-panel); }
[data-film="on"] { --glass-blur: 0px;  --glass-ground: var(--glass-panel-strong); }
```

Real blur therefore appears only over the static poster (reduced motion, Save-Data, decoder failure,
and before `canplay`), where the backdrop is a single decoded image and the cost is paid once. Blur
never exceeds 14 px, and **at most one blurred surface may be in the viewport at a time**; a second
overlapping panel uses `--glass-panel-strong` flat.

Borders are 1 px `--line` at rest, `--line-strong` on a panel edge, `--line-hover` on hover. Shadow
is the existing `--shadow-raised`. Glow exists twice on the page and both instances are semantic:
`--glow-route` under the one orange decision marker, `--glow-system` under the live retrieval
instrument. There are no ambient glow blobs.

---

## 3. Section composition and film mapping

**This section is written against `v2/copy.md` (read 2026-09-11), which supersedes the structure this
pass had drafted before it existed.** Nine sections; the header and the footer are microcopy, not
funnel sections. Reading order, which is also DOM order, tab order and visual order at every
breakpoint, with no CSS `order` anywhere:

`hero → extraction → retrieval → proof gate → telemetry and promotion → evidence → availability →
waitlist → before you join`

Two rules that come from the copy and bind every section below. **A figure is set at headline weight
and its qualifier is one line of microcopy directly beneath it, at every breakpoint; a figure that
cannot fit its qualifier is dropped whole.** And **eyebrows exist** ("Where the rules come from",
"What the agent gets", "Safety boundary", "For the organisation"), which reverses the draft ban in
§2.1: the ban was on the all-caps tracked label as template chrome, so the eyebrow survives as copy
and is restyled as **sentence-case JetBrains Mono at `--font-size-code` with `--landing-tracking-mono`,
in `--steel`, preceded by a 12 px hairline**, never uppercase and never tracked out. The hero has no
eyebrow, as the copy requires.

### 3.0 The playhead map

The film is 10.04 s at 24 fps. `FilmBackdrop` today maps whole-document progress linearly onto
duration. That must be **replaced by a piecewise-linear anchor map**, because the beats are not
evenly spaced in scroll: the pinned chapter consumes a lot of scroll and very little film, and the
hero consumes very little scroll and holds the establishing beat.

**The anchors are measured, never hardcoded scroll fractions.** `useDocumentProgress` supplies
`scrollY / (scrollHeight - innerHeight)`, a whole-document fraction that knows nothing about where a
section begins; a table of fractions would drift the moment copy length changes. The implementation
therefore builds the map from the **measured offsets of the nine section elements**, using the same
rects `scroll.ts` already samples: each section contributes one anchor `(sectionTop normalised
against the scrollable height) → playhead second`, the playhead is interpolated piecewise-linearly
between neighbouring anchors, and the table is recomputed on resize, on rotation, on font load and
after the film's own metadata arrives. The playhead seconds below are fixed; the scroll positions
they sit at are whatever the layout turns out to be.

Anchors live in one typed constant array in `FilmBackdrop.tsx` (JavaScript constants, not CSS, so
the contract checker is unaffected), each entry naming a section id and its playhead second. The
scrub keeps the existing damped seek (`current += (wanted - current) * .14`, write only when the
delta exceeds one frame, never while `seeking`); it is not replaced by a per-frame write.

| # | Section (copy.md) | Film beat | Playhead |
|---|---|---|---|
| 1 | Hero | Table above the clouds, one orange route drawn across the topographic desk, sunrise window | 0.00 → 1.40 |
| 2 | Extraction (pinned, 3 beats) | The fall along the desk into the terrain: contour valley, teal contour rings, the paper map sheet lifting into the sunlight | 1.40 → 4.20 |
| 3 | Retrieval | **Four cream cards standing in a fan around one lit orange marker** | 4.20 → 5.60 |
| 4 | Proof gate | The route crossing a plateau edge, teal rim light along the boundary | 5.60 → 6.80 |
| 5 | Telemetry and promotion | The stacked plateaus held wide, cubes across the lower tiers | 6.80 → 7.80 |
| 6 | Evidence | The upper plateau, sparse cubes, route arriving at the top tier | 7.80 → 8.60 |
| 7 | Availability | Pull back begins, the terrain reads as a map again | 8.60 → 9.10 |
| 8 | Waitlist | The map rising into its folds | 9.10 → 9.70 |
| 9 | Before you join, and the footer | **Exact terminal frame**: the folded map standing on the desk, the route running across its folds beside the wordmark | 9.70 → 10.04 |

Two beats are literal and must not be re-assigned: the four-card fan sits under the retrieval
section, and the tier-edge crossing sits under the proof gate. The last section holds the terminal
frame exactly; the flight never stops between beats.

#### Implemented anchors

Owner/controller ruling, 2026-09-11: **the film's own cuts are the truth and the seconds in the table
above were targets.** Two anchors sat one to four frames inside the previous shot, so a visitor parked
at the section top saw the tail of the wrong beat. The cuts were measured with ffmpeg scene detection
on `ui/public/assets/landing/hero-flight.mp4` (10.041667 s, 24 fps, 241 frames) and confirmed by
frame-by-frame inspection at 1/24 s. `FilmBackdrop.tsx` ships the third column; the seconds not listed
here are unchanged from the table above and were confirmed to open on their own beat.

| Section | Design second | Measured cut | Shipped anchor |
|---|---|---|---|
| Retrieval (`how-it-works`) | 4.20 | **4.2083** (hard cut, scene score 0.23: map sheets → the four-card fan) | **4.30** |
| Proof gate (`proof-gate`) | 5.60 | **≈5.67** (no hard cut; the continuous pull-back at which the cards clear frame and the teal-rimmed plateau edge becomes the subject) | **5.75** |

The shipped anchor is the cut plus ≈0.09 s, not the cut itself. The scrub's delta gate stops writing
once the residual is under one frame, so a settled playhead sits within ±0.042 s of its anchor
(±0.055 s measured); an anchor placed exactly on a cut therefore still renders the previous shot on a
forward approach. The margin is wider than that deadband and negligible against a section's own span.

Only two other hard cuts exist in the film and neither needed an anchor move: the fall into the terrain
is one continuous take from the hero (no cut at 1.40), and the cut to the folded map at **8.8333** falls
inside `availability`, whose own beat is the terrain pull-back that precedes it.

### 3.1 Hero

Copy: headline 6 words, subline 17, body 2 sentences, **two** proof items each with its qualifier
beneath, two actions, the protected trust line, one text link to the evidence section. No eyebrow.

**1440.** Full-bleed film, `object-position` `62% 50%`, `--film-scrim-hero` rotated to 100deg so the
sunrise window on the right stays uncovered. Copy occupies columns 1–6, anchored to the lower third:
display headline on three lines maximum, subline at `--landing-kicker` and 34ch, body at
`--landing-body` and 46ch, then the two actions (**Join the waitlist** primary, the protected
**Play demo** secondary), then the protected trust line as one caption, then the text link.

Across the lower edge of the frame, columns 1–9, the **proof rail**: one glass strip, two cells
divided by a single hairline. Each cell is a figure at `--landing-metric` in tabular mono and its
qualifier underneath at `--font-size-small` in `--steel`, both rendered in full:

| Figure | Qualifier, verbatim from copy.md |
|---|---|
| `76 of 76 harmful rules refused.` | Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11. |
| `+8.53 pp Recall@10 on SRA-Bench.` | Measured, exploratory offline retrieval. 10 September 2026. |

Columns 10–12 hold one small **tier glyph**: four stacked plateau bars in `--tier-1..4` with a single
orange route climbing them, drawn as one SVG polyline. That is the pyramid mechanic visible above the
fold without a paragraph, and it is the only decorative diagram on the page; its geometry is the same
as the tier instrument in §3.2 beat 3.

**390.** Film at `object-position` `74% 50%`, scrim rotated to vertical, copy stacked. Display drops
to `clamp(34px,9vw,46px)`; both actions full width at 44 px minimum; **both proof cells stack and
both stay above the fold**, each keeping its qualifier; the tier glyph moves below the actions at
96 px tall. **The header is static at 720, not sticky**, which is the fix for the defect in today's
capture where the navigation covers the first line of the `h1`.

On the film: headline, subline, body, actions, trust line, link. On glass: the proof rail only.

### 3.2 Extraction — pillar 1, pinned, three beats

The page's centrepiece and the section the hero headline has to make literal. A **pinned stage**:
`100dvh` sticky stage over roughly 240 vh of scroll, three beats advancing while the film falls from
the desk into the terrain beneath them.

Copy placement: the eyebrow and the 6-word headline are fixed at the top of the stage and do not
move between beats; the subline, the two-sentence body and the microcopy line ("Promotion is a
proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.") are distributed
as the three beat captions, in that order, so the copy is read once, in sequence, not repeated.

| Beat | Caption source | Instrument on glass |
|---|---|---|
| 1. Written where the work is | subline, first half | Path instrument: mono breadcrumb of a real Meridian fixture path with one `SKILL.md` row |
| 2. The reusable part is lifted | subline, second half, plus body sentence 1 | Diff instrument: two mono columns, "stays here" and "goes up", four real fixture rule names, the promoted row marked in `--safety-orange` (one of the page's two orange moments) |
| 3. It lands one level up | body sentence 2, plus the microcopy line | **Tier instrument**: `ScopePyramid` rebuilt as four tier bars with counts, upper tiers narrower, the promoted rule travelling one tier up as the beat advances |

Component: handmade against tokens in CSS Modules with `motion`'s `useScroll`/`useTransform` plus
`position: sticky`. A pinned narrative stage exists in neither registry (`components.md`, "Sticky
scroll reveal: not found in any registry"), so this is a **recorded Spectrum exception**, built
following `cloudfloo-premium-scroll-motion`.

**1440**: instrument columns 7–12, captions columns 1–5, a 1 px vertical rule with three ticks in
column 6 (numbering is legitimate here because this is a real sequence). **390**: the pin is
**disabled by a token** (`--landing-stage-height: auto`) and the three beats become three stacked
blocks, caption above instrument, in the same DOM order. Nothing is hidden and nothing is reordered.

### 3.3 Retrieval — pillar 2 with pillar 7

The film's four-card beat sits directly under this section, so the section's job is to make the
frame literal. Copy: eyebrow, 7-word headline ("Thirty thousand rules. Four reach the agent."),
15-word subline, 2-sentence body, the microcopy line that says the 30k figure is *designed for* and
that latency is not claimed, and the "Try the open-source version" link, which is the **only** copy
of that link in the body of the page.

**1440.** One glass instrument, columns 2–11, read left to right in three zones: a query line (mono:
the task and the repository path), a candidate column showing how many skills were considered, and
the four delivered cards with their proof state, general cards first. Beneath it one row of two mono
figures, each with its qualifier: `25/25` hierarchical SEARCH requests with no 422 (integration,
verified, 2026-09-11) and `4/4` source proof complete (integrity, verified, 2026-09-11). The existing
`IntroFigure` and `InstructionReader` stay in this section as the "full text only when the agent asks
for it" step, with the protected Meridian fixture label and the "not a live run" label intact.

Component: handmade panel; `@spectrumui/number-ticker` for the two figures. `border-beam`, already
installed, is **not** used: a travelling border on an instrument the reader is parsing is decoration
on data.

**390**: the panel becomes a vertical sequence, query → candidates → four cards, figures stacked,
`--landing-panel-pad` 16 px, the internal hairline grid kept so it still reads as an instrument.

### 3.4 Proof gate — pillar 4 with pillar 8

The best number on the page and the question a platform buyer asks first. Copy: eyebrow "Safety
boundary", 6-word headline, the 13-word subline that names the flat control, the 2-sentence body, and
**two proof lines whose labels are never shortened**, both carrying the full Wilson sentence and the
date.

**1440.** Type-on-film, not glass: columns 1–5 carry eyebrow, headline, subline, body; columns 7–12
carry the two proof lines as a two-row stack, figure at `--landing-metric-unit` weight because these
figures are sentences rather than digits, each with its qualifier beneath and a `--line-strong`
hairline between them. One `--glow-system` sits under this block; it is the page's second and last
glow. The film's tier-edge crossing is visible to the right of the copy, which is the point: the
boundary in the frame and the boundary in the argument are the same line.

**390**: single column, copy then the two proof lines, qualifiers never dropped. Both proof strings
wrap rather than truncate; no ellipsis, no "read more".

Forbidden here, from the copy and the value brief: "zero risk", "no unsafe deliveries ever",
"100% safe", any rounding of 76, and any presentation of the E6.7 replay as proof of task value.

### 3.5 Telemetry and promotion — pillar 3 with pillar 5

Copy: eyebrow "For the organisation", 7-word headline, the subline listing the per-team measures, the
2-sentence body about the fixed ASK vocabulary and the pull-request report, and the microcopy line
"Missing data reads Unknown, never zero."

**1440.** One glass instrument, columns 2–11: one row per team with task success, ASK count, the
SEARCH → USE funnel, cost and time, and an ASK reason drawn from the safe vocabulary. **Missing data
renders the word `Unknown`**, never a zero and never a dash; that rule is visible in the instrument
itself, not only in the microcopy. Beneath the rows, one mono line showing a promotion gate rule.
Labelled Meridian fixture, visibly.

Component: handmade rows against tokens. `@spectrumui/status-tracker` is **not** installed: its
long-running-job framing would have to be stripped down to less than it provides. Recorded exception.

**390**: each team row becomes a stacked definition list with the same labels and the same `Unknown`.

### 3.6 Evidence — pillar 2 measured, with pillar 9

The section where an engineer is invited to disbelieve the page. `ResearchEvidence.tsx` keeps its
chart, its table, its interval paragraphs, the Pi delivery-boundary trace and its `<details>` method
block **exactly as they are**; values keep coming from `ui/src/data/research-evidence.json` at render
time and are never hard-coded into markup. This design only specifies what sits **above** them, and
nothing here may soften them.

**1440.** Eyebrow (the existing dated "Research update" line), 7-word headline, 13-word subline, then
the figure block with its microcopy naming the regressions, then the two calm blocks: what is still
open, and the scale envelope. Layout: an asymmetric **bento**, `@spectrumui/bento-grid` (this install
also brings `spotlight.tsx` and `border-beam.tsx`; spotlight hover is used here and nowhere else).
Four tiles on a 12-column span, deliberately unequal: a tall tile (columns 1–5, two rows) for the
existing bar chart, loaded on intersection as today; a wide tile (columns 6–12) for `+8.53 pp` and
`+4.87 pp` as number tickers with their baselines `56.69 → 65.22` and `42.31 → 47.19` in tabular
mono; one tile for "what is still open", carrying **no figure**; one tile for the scale envelope with
the words *designed for, not yet measured* in `--warning-ink`. The two existing links, "Read the
evidence" and "Download results and source hashes", close the section.

Rule, enforced by QA: no number appears on this page without its denominator, its date and its status
word.

**390**: the bento collapses to one column in the same DOM order, chart first. The chart tile carries
a minimum-height token so it never renders as an empty box, which is the defect visible in today's
1440 capture.

### 3.7 Availability — pillars 6 and 10

Two facts, so two statements and no third for symmetry. Solid band over `--film-scrim-band`, because
this is where the reading matters more than the atmosphere. Copy: 6-word headline, the two protected
statements side by side verbatim (`Open source today.` / `Paid hosting is planned.` with their
sentences), the supporting line naming the four harnesses, and the "Read the docs" link. Per the
copy, the availability band's own "Try the open-source version" link is **removed**; section 3 and
the footer keep theirs.

**1440**: headline columns 1–4, the two statements columns 6–12 side by side with one hairline
between them, supporting line beneath at 60ch. **390**: stacked, hairline becomes a top rule on the
second statement.

### 3.8 Waitlist

The single conversion on the page. Solid band. Copy: 5-word headline, 9-word subline. Everything
inside `WaitlistForm` is protected and verbatim: the signup note, the label, the placeholder, the
submit label, the loading label, the consent text, the honeypot, the ids, the aria wiring, the 12 s
abort, the success state and the four error strings.

**1440**: headline and subline columns 1–5, form columns 7–12, one hairline between. **390**: stacked,
input and button full width, 44 px minimum, and the consent checkbox target 44 px including its label
row. The `?confirm=` / `?unsubscribe=` branch renders instead of every marketing section and **never
mounts the film**.

### 3.9 Before you join, and the footer

Solid band. Copy: 3-word headline, 10-word subline naming the four objections. The four protected FAQ
answers stay in full inside the existing Base UI `Collapsible` with their ids (`question-1`,
`question-2`, `question-3`, `privacy`), all panels closed on load, hash deep-linking and the consent
link behaviour intact. **`@spectrumui/faq-tabs-card` is not installed**: it would re-home protected
answers inside a tabbed card and put the `#privacy` anchor contract at risk for no gain. Recorded
exception. Restyling the trigger row, the caret and the panel is expected.

The footer closes this section rather than opening a tenth: four link groups, the protected bottom
line, its own "Try the open-source version" link, and the large wordmark, now sitting on the film's
terminal frame so the folded map and the wordmark share the last screen.

## 4. Motion choreography

### 4.1 The four entrance patterns

Exactly four across the page. Nothing else enters. All four animate `transform`, `opacity` and (P3
only) `filter`, never layout properties.

| Pattern | Properties | Duration | Easing | Stagger | Trigger | Once / reversible |
|---|---|---|---|---|---|---|
| **P1 Lift** (headings, captions, list rows) | `opacity 0→1`, `translateY var(--enter-rise) 12px→0`, headline lines additionally masked by `clip-path: inset(0 0 100% 0) → inset(0 0 0 0)` on a per-line wrapper | `--duration-entrance` 420 ms | `--ease-entrance` `cubic-bezier(.16,1,.3,1)` | `--stagger-entrance` 60 ms, capped at `--stagger-cap` 240 ms (never more than 5 items) | element crosses 22% from the bottom (`IntersectionObserver`, `rootMargin: 0px 0px -22% 0px`) | once |
| **P2 Rule draw** (hairlines, the tier route, beat ticks) | `transform: scaleX()` `0→1` from `transform-origin: left`, or `stroke-dashoffset` for the SVG route | `--duration-draw` 520 ms | `--ease-entrance` | 80 ms after its own heading | same as P1, on the section | once |
| **P3 Panel settle** (glass instruments, bento tiles, the chart) | `opacity 0→1`, `scale .985→1`, `filter: blur(3px)→0` | `--duration-panel` 360 ms | `--ease-entrance` | 70 ms between bento tiles, max 4 | 30% of the panel visible | once |
| **P4 Count** (digit-only figures, at most six on the page; a figure written as a sentence, as in the proof gate, never counts) | per-digit roll with tabular numerals, `@spectrumui/number-ticker` | `--duration-count` 900 ms | the ticker's bundled curve, pinned by hash | 40 ms per figure in a rail | figure 60% visible | once |

**P4 never runs inside the LCP window.** The hero proof rail sits above the fold, so its two figures
render their **final values in the base DOM**, server-shaped and static, and the count applies only
after enhancement has initialised and the LCP entry has been reported. If that ordering cannot be
guaranteed cheaply, the hero rail is excluded from P4 altogether and counts only if the reader
scrolls back to it; the numbers are the argument and a visitor's first read of them must never be a
roll. P4 anywhere else on the page (the evidence bento) is unaffected. No rail text may become the
LCP element: the poster paints first and stays the largest painted element.

Base state discipline: every element's **resting state is its final state**. The entrance is applied
only after the enhancement root class is set, and only to elements the observer is actually driving
(the `data-p-ready` pattern already in `scroll.ts`). A missed callback, a thrown error, reverse
scroll, a refresh mid-page or JavaScript off leaves all content visible. Nothing is ever hidden by
default.

### 4.2 Scroll-linked effects

| Effect | Mapping | Amplitude | Notes |
|---|---|---|---|
| **Film scrub** | document progress → playhead via the §3.0 anchor map, damped at `--film-lerp` `.14`, written only when the delta exceeds one frame | whole film | Reversible by construction; never becomes an autoplay loop |
| **Chapter pin** | mechanism section only: sticky `100dvh` stage over ~260 vh, `--p` 0→1 across the three beats | beat caption crossfade at 0.0–0.33, 0.33–0.66, 0.66–1.0 with a 0.06 overlap | Disabled at 720 by token. No scroll-jacking: the page never takes over the scroll, it only holds one element |
| **Panel parallax** | `translate3d(0, calc((var(--p) - .5) * var(--parallax-panel)), 0)` | `--parallax-panel` 12 px, 6 px at 720 | Linear in `--p`, exact in reverse |
| **Chapter parallax** | same expression on the instrument layer | `--parallax-chapter` 32 px, 16 px at 720 | |
| **Tier route draw** | scope tier instrument's route `stroke-dashoffset` mapped to beat-3 progress | full length | The one scroll-linked element that is also a diagram; its resting value is the finished route, as with today's `RouteRule` |

No pointer parallax, no mouse-tracking, no custom cursor. Pointer response on this page is limited to
hover and press.

### 4.3 Hover and press

Gated on `@media (hover: hover) and (pointer: fine)`.

| Surface | Hover | Press |
|---|---|---|
| Primary and secondary actions | background and border shift only, `--duration` 120 ms, `ease` | `transform: scale(var(--press-scale))` `.98`, 160 ms `--ease-out` |
| Text links | underline thickness and colour, 120 ms | none |
| Bento tiles | spotlight follow from the bento install, plus `--line` → `--line-hover`; no lift, no shadow bloom | none (tiles are not buttons) |
| FAQ trigger | caret rotation 180 ms, panel height and opacity 180 ms, Base UI transition, interruptible | none |
| Tabs in the instrument reader | indicator `translateX` and `width`, 180 ms, unchanged | none |

Transitions, not keyframes, for anything a person can retrigger quickly, so a rapid toggle retargets
instead of restarting.

### 4.4 Reduced motion, Save-Data and failure

`prefers-reduced-motion: reduce` and Save-Data are a **token swap plus a mount decision**, which is
how the rest of this repository handles responsive change:

```
--duration-entrance: 0ms; --duration-panel: 0ms; --duration-draw: 0ms; --duration-count: 0ms;
--enter-rise: 0px; --enter-blur: 0px; --enter-scale: 1;
--parallax-panel: 0px; --parallax-chapter: 0px;
--landing-stage-height: auto;   /* the pin is off; the chapter is three stacked beats */
```

plus: the sampler is never installed, the film element is never created, the poster remains, the
ticker renders its final value immediately, and the scope route renders complete. The page is a
correct static composition in that state, not a degraded one.

Media failure paths are unchanged from the current implementation and remain binding: poster paints
first with `fetchpriority="high"` and is never removed; the video mounts only when the hero is in
view, motion is allowed, Save-Data is off and the poster has decoded; it unmounts on `error` or if
`canplay` has not fired within 8 s; it pauses on `visibilitychange`, on leaving the viewport and
while the demo dialog is open. A decoder failure leaves every section readable, because no content
depends on the film.

### 4.5 Motion prompt packet (summary)

States: `entrance`, `progress`, `mediaReady`, `mediaFailed`, `menuOpen`, `activeBeat`. Every animated
value derives from one of those; no component owns a private timer. Layers, back to front: film,
scrim, section planes, instruments, type, chrome. Copy-safe regions: hero columns 1–6 at ≥1080 and
the lower 55% at 720; chapter captions columns 1–5. Crop-safe: the route line and the window must
survive `object-position` at both breakpoints; the terminal folded-map frame must keep the whole map
in frame at 390. Breakpoint substitution: pin off, parallax halved, film opacity lowered, hero
scrim rotated. Accepted mechanics: scrubbed film, pinned chapter, hairline draw, masked line lift,
per-digit count, spotlight hover. Rejected mechanics: pointer drift, marquee, custom cursor, text
scramble, per-character orbit on the `h1`, beam borders on data, page transitions, horizontal scroll.

### 4.6 Motion opportunities that were gated out

Required by `find-animation-opportunities`: candidates considered and rejected.

- Per-character orbit entrance on the hero `h1` (`@spectrumui/orbital-letters`). **Rejected**: the
  `h1` is adjacent to the LCP element and per-character motion on the first paint is both a
  generated-page tell and an LCP risk. P1's per-line mask gives the same rank with three animated
  nodes instead of forty.
- Travelling border beam on the retrieval instrument. **Rejected**: decoration on data the reader is
  trying to read.
- Hover lift on the evidence bento tiles. **Rejected**: tiles are not pressable; a lift would promise
  an action that does not exist. Spotlight follow is the whole hover vocabulary there.
- Animated funnel bars in the telemetry instrument. **Rejected**: a chart the reader is parsing
  should not move for style; the numbers appear at their final value.
- Marquee of harness logos. **Rejected**: no logo set exists that we have the right to show, and the
  page already names the harnesses in words.

---

## 5. Performance and accessibility contract

| Item | Contract | How it is checked |
|---|---|---|
| LCP | Still `hero-poster.webp`, `fetchpriority="high"`, 1920×1080, 126 KB, ≤ 2.0 s on a throttled 4G profile. No new element may paint above it, and no font, script or ticker may block it | Lighthouse at 1440 and on the mobile profile; the LCP element is asserted in the QA run |
| CLS | **0**. Every media slot carries intrinsic `width`/`height` or an aspect-ratio box; the pinned stage reserves `--landing-stage-height` before enhancement; the chart tile has a minimum-height token; no font swap moves layout | Lighthouse plus a scroll pass with layout-shift logging |
| JS budget | **≤ +34 KB gzipped** on the landing route chunk over today's build. `motion` and `framer-motion` are already dependencies; the allowance covers the bento grid with spotlight, the number ticker and the new scroll/anchor code. A new runtime dependency (WebGL button, beam packages beyond what is installed, a smooth-scroll library) is out of budget by definition | `pnpm build`, compare route chunk gzip size before and after, record both numbers in `docs/reports/readme/build-notes.md` |
| Frame budget | Main-thread work under **4 ms per frame** during a full scroll pass, zero long tasks. One rAF, one passive scroll listener, one resize listener, one `IntersectionObserver` for the whole page; no `getBoundingClientRect` outside the batched sampler; `transform`/`opacity` only; `will-change` on the film layer and the pinned stage only; **no `content-visibility: auto`** (without a per-section `contain-intrinsic-size` it reports zero height and shifts on reveal, breaking CLS 0, and it fights both the observer and the rect measurement the anchor map depends on); no `backdrop-filter` while `[data-film="on"]` (§2.4) | DevTools performance trace, scroll top to bottom and back, at 1440 and at 390 with 4× CPU throttling; long-task count must be 0 |
| Focus order | Equals DOM order equals visual order at every breakpoint. No CSS `order`. The pinned chapter's three beats are all in the DOM and all reachable; focusing a beat while the stage is pinned must not fight the scroll | Keyboard-only pass, tab from the skip link to the footer |
| Contrast over film | Body ≥ 4.5:1, large ≥ 3:1, hero display ≥ 7:1, measured against the brightest sampled frame inside each copy-safe region | Frame extraction at the §3.0 anchors, contrast measured on the composited result, recorded in the QA report |
| Targets | 44 px minimum for every control at 720, including the consent checkbox row and the FAQ triggers | Playwright measurement at 390 |
| Keyboard flow | Unchanged: skip link, header, hero actions, demo dialog with focus trap and restore, waitlist form, FAQ triggers, footer. The film is `aria-hidden` and unreachable | Manual pass plus the existing e2e |
| Axe | Clean at 1440 and 390, with the FAQ closed and open and with the dialog open | `pnpm test:e2e` axe step |
| Reduced motion | The page renders its static composition with no video element created and no sampler installed | Playwright with the media feature forced |

---

## 6. Anti-slop gate

### Bans that stand from "What must not come back"

3D pyramid, WebGL hero atmosphere, schema-flow canvas, autoplaying feature demos, the typewriter,
the shine sweep, per-word text reveals, `MorphButton` on this page, any new dependency, any new font
fetch, any new icon library.

### Bans lifted by the owner verdict

Section entrance motion, scroll-triggered content motion, the 240 ms ceiling, and the single-hero-
entrance rule. Motion above 240 ms is permitted **only** for the four patterns in §4.1 and the film.

### Banned specifically for this page

| Banned | Because |
|---|---|
| Gradient text, or any headline where one word is a different colour or weight | The commonest generated-page tell; rank comes from size and position here |
| A row of three identical cards, anywhere | The current page's worst structural habit; every group on this page is deliberately unequal |
| Generic glow blobs, mesh gradients, radial "aurora" backgrounds | The film is the atmosphere; a second atmosphere competes with it |
| Stock icons in circles, an icon per feature, emoji as icons | Instruments show real artefacts; Phosphor regular only, and only where an icon names an action |
| All-caps tracked eyebrow above a heading | Template chrome; retired from this page |
| A `→` glued to link or button text | Directional glyphs are icon elements, on the two primary actions only |
| Meta strings joined with middle dots, `WORD — fragment` labels | Template chrome |
| Glass on anything that is not a real instrument | Translucency needs a material reason |
| More than two radii, or a radius that varies by tile | 8 px and 16 px, nothing else |
| A number without its denominator, date or status word | Proof is instrumentation, not decoration |
| Presenting E6.7 (17/20) as proof of task-level value, or 0/76 as "zero risk" | The value brief forbids it, and it is the one claim a technical buyer will test |
| The seven banned words listed in UX §6, and their Polish calques (not restated here: the slop hook greps this directory, and this file must pass its own gate) | UX §6 and `.claude/hooks/check-slop.sh` |
| Reflexive rule of three, anonymous "research shows", "it is not X, it is Y" sentences, em-dash chains | UX §6 |
| Headlines written as advertising sentences | Headings are names |

### The screenshot test QA will run

1. Capture full-page at **1440×900** and **390×844**, plus viewport captures at each of the nine
   section anchors, plus one capture at the pinned chapter's mid-beat, plus one with reduced motion
   forced, plus one with the film failed (block the video request).
2. Remove the logo and the wordmark from the 1440 capture. Show it to an engineer outside the
   project and ask what the product does. An answer of the shape "some AI dashboard" or "a generic
   SaaS landing page" is a **P1**. A correct answer names rules, a hierarchy, or agents getting the
   right instructions.
3. On the same de-logoed capture, check that at least one screen shows a **real artefact** (a path, a
   `SKILL.md`, a tier count, a funnel row) rather than only prose.
4. Diff the reduced-motion capture against the normal one: all the same content must be present.
5. Read-aloud test on every new string: read it as if to a colleague; rewrite anything you would not
   say. Record both tests in the change description.
6. Grep the diff for the banned words, the `→` in link text, and any literal colour or dimension in a
   CSS module; `node qa/check-contracts.mjs` must pass.

---

## 7. Open decisions for the plan writer

| # | Decision | Recommendation |
|---|---|---|
| 1 | **Film keyframe density.** `hero-flight.mp4` has 21 keyframes across 241 frames, roughly one every 0.5 s, so a scrub lands on the nearest keyframe and beats read mushy | **Re-encode** from the source at `-g 12` (and keep the WebM in step), same dimensions and bitrate class, replacing both files in place. If the source is unavailable, re-encode from the existing MP4 and accept one generation loss; the scrub precision matters more than the artefact |
| 2 | **Film resolution.** The file is 1280×720 stretched across a 1400 px stage | Leave it. A 1440-wide re-render is a generation cost with a small return at `--landing-film-opacity` `.86`; revisit only if the terminal frame looks soft in QA |
| 3 | **Pinned chapter or stacked beats at ≥1080.** The pin is the single largest motion investment and the largest frame-budget risk | **Pin**, with the token escape hatch already specified: pin above 1080, stack at and below, stack under reduced motion. If the frame trace shows long tasks, drop the pin and keep the three beats as a scroll-linked triptych; the composition survives either way |
| 4 | **Hero headline treatment.** Orbital Letters versus the P1 per-line mask lift | **P1 mask lift.** Fewer animated nodes, no LCP risk, and per-character orbit is a generated-page signature |
| 5 | **FAQ component.** `@spectrumui/faq-tabs-card` versus the existing Base UI `Collapsible` | **Keep `Collapsible`**, restyled. The protected ids, the hash deep-link and the consent link's behaviour are contractual; record the Spectrum exception in the change description |
| 6 | **Bento install.** `@spectrumui/bento-grid` brings `spotlight.tsx` and `border-beam.tsx` | **Install it once**, use bento and spotlight in §3.6 (evidence) only, leave `border-beam` unused on this page. Dry-run first, add every file to `qa/spectrum-registry.json` with its hash and source URL, and keep the licence notices in sync |
| 7 | **Number ticker.** `@spectrumui/number-ticker` ships inline geometry for rolling digits | **Install**, and register it with `allowInlineGeometry: true`, as already done for `tree-nav.tsx` and `charts/*`. If the review of its source shows literal colours rather than geometry, hand-build the roll instead; the pattern is twenty lines |
| 8 | **Telemetry data source.** Fixture rows or a captured real run | **Labelled Meridian fixture**, with the label visible. Real rows would be a tenancy and privacy question for a public page |
| 9 | **Proof rail width.** Four cells or three above the fold at 1440 | **Four.** The fourth (`≤ 4` cards) is the retrieval promise, and the value brief requires both pillars visible at first sight |
| 10 | **Copy distribution in the pinned chapter.** `copy.md` gives extraction one subline, a two-sentence body and one microcopy line; §3.2 splits them across three beats | **Split as specified**, so each beat carries one idea and the copy is read once in sequence. If the writer prefers the copy intact, the alternative is caption-on-beat-3 only with beats 1 and 2 carrying instruments alone; decide before implementation, not during |

---

## 8. Handoff checklist

Before this direction is considered implementable: `v2/copy.md` exists; the token deltas in §2 are
added to `tokens.css` in one commit with the `1080px`, `720px` and `prefers-reduced-motion` blocks
updated together; the anchor map in §3.0 lives in one typed constant in `FilmBackdrop.tsx`; the four
entrance patterns are four implementations, not nine; and `node qa/check-contracts.mjs`,
`pnpm typecheck`, `pnpm test`, the axe pass and the screenshot test in §6 all run before the change
is described as done.
