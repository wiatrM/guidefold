# Landing v2 — component inventory

Scope: candidate premium components for the Awwwards-grade marketing landing page, sourced
through the MCP tools reachable from this project (`@shadcn`, `@spectrumui`). No installs were
run and no source under `ui/` was edited; this is a scouting inventory only.

Stack assumptions verified from the repo: React 19 + Vite, Tailwind 4 scoped to
`src/components/ui` and `src/components/spectrumui` via `src/registry.css`
(`@source "./components/spectrumui"`, `@source "./components/ui"`, no Preflight reset),
shadcn `new-york` / base-nova style with `@base-ui/react` primitives (see
`src/components/ui/button.tsx`), lucide icons, both `framer-motion` and `motion` present as
dependencies. `src/components/spectrumui/` already contains real installs to reuse rather than
reinstall: `beam-card.tsx`, `beam-search.tsx`, `morph-button.tsx`, `use-typewriter.ts`,
`use-beam-motion.ts`, `use-surface-theme.ts`, `tree-nav.tsx`, plus `charts/*` — all hash-pinned
in `ui/qa/spectrum-registry.json`.

Registries actually configured in `ui/components.json`: `@shadcn` (471 items — the official
core primitives + examples + fonts; no marquee/bento/ticker/beam/spotlight items exist there)
and `@spectrumui` (proxied to `https://ui.spectrumhq.in/r/{name}.json`, ~270 items across 15
categories, the source of nearly every "premium/animated" candidate below).

## Hero: text reveal

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Orbital Letters** — *recommended* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/orbital-letters` | `framer-motion` | Yes | Per-character orbit-in entrance for a headline; no RSC/Next assumptions in the install metadata; framer-motion is already a project dependency. |
| useTypewriter | @spectrumui | already installed (`src/components/spectrumui/use-typewriter.ts`) | none | Yes | Reduced-motion-aware typing/deleting loop hook; good for a rotating sub-headline under the hero title, not the title itself. |
| Text States | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/text-states` | none listed | Yes | Blur-exit/enter swap, but designed for a short status label, not a multi-word headline — needs adaptation (font-size, line-wrap) to carry a hero line. |

## Animated / shimmer / gradient buttons

No Spectrum or shadcn item is a pure shimmer/gradient CTA button. Closest primitives:

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| Morph Button — *closest, adapt* | @spectrumui | already installed (`src/components/spectrumui/morph-button.tsx`) | `framer-motion` | Yes | Idle→loading→success→error state morph with arc spinner and drawn-in check; reuse as the *interaction* layer and add a gradient/shimmer background via Tailwind, don't reinstall. |
| Metal Button — *heavy alt* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/metal-button` | `metal-fx` (WebGL) | Needs adaptation: real-time WebGL liquid-metal ring is a new runtime dependency and a GPU/reduced-motion fallback must be built; verify it renders under Vite (no Next asset pipeline assumed by the registry, but unverified against this bundler). | Genuinely premium chromatic/silver/gold ring effect, but disproportionate weight for a single CTA button. |

**Recommended pick: handmade with `motion`** — a Tailwind gradient background + `motion`
hover/tap scale + a CSS shimmer sweep (`background-position` keyframe) on top of the existing
Button (`src/components/ui/button.tsx`) is lighter than either registry option and avoids a new
WebGL dependency for a landing-page CTA.

## Bento grid feature layout

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Bento Grid** — *recommended* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/bento-grid` | `framer-motion`, `lucide-react` | Yes | Ships 4 files in one install: `bento-grid.tsx`, `bento-card.tsx`, **`spotlight.tsx`** and **`border-beam.tsx`** — this single install also covers the spotlight/border-glow category below, so it should be installed once and reused. |

## Marquee / logo cloud

**Not found in any registry** — `@spectrumui` search for "marquee logo cloud" returned zero
results; `@shadcn`'s 471 items are core primitives/examples/fonts only, no marquee block;
`@magicui` and `@aceternity` are not reachable (see failed calls below). Must be handmade with
`motion` or a pure CSS `@keyframes` infinite-scroll track, with `prefers-reduced-motion` pause.

## Number ticker / animated counters

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Number Ticker** — *recommended* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/number-ticker` | `motion`, `clsx`, `tailwind-merge` | Yes — uses `motion` (already a dependency) rather than `framer-motion`, the better convergence choice | Per-digit rolling stagger with padding and blur; ships its own `lib/ease.ts` easing curve file. |

## Animated beam / connection lines

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| Beam Card / border-beam — *reuse, don't reinstall* | @spectrumui | already installed (`src/components/spectrumui/beam-card.tsx`, `use-beam-motion.ts`, `use-surface-theme.ts`) | `border-beam` package | Yes | Perimeter-traveling or pulsing border animation for a single card/panel. |

**Not found**: a node-to-node "connect these two DOM refs with an animated line" primitive
(the Magic UI `AnimatedBeam` pattern) does not exist in Spectrum or shadcn. If the "how it
works" or integration section needs literal connecting lines between icons/nodes, that must be
handmade with `motion` + inline SVG (`getBoundingClientRect` + a `path` `d` recompute on
resize), reusing `useBeamMotion`'s reduced-motion gate for consistency with the rest of the app.

## Timeline / stepper — 3-step "how it works"

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Status Tracker** — *recommended, adapt* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/status-tracker` | `lucide-react` | Needs adaptation: written for "long-running AI jobs" staged progress — strip the job/status-poll framing, keep the 3/4-stage horizontal progress visual and swap in generic step copy. | Clean staged-progress visual with the least ceremony of the two candidates. |
| Agent Steps | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/agent-steps` | `lucide-react` | Needs adaptation: built for a timeline of tool calls with args/results/parallel sub-steps — heavier than a 3-step marketing timeline needs. | More elaborate timeline visual if the "how it works" section wants expandable step detail. |

## Testimonial / quote card

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Testimonials** — *recommended* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/testimonials` | `lucide-react`, `framer-motion` | Needs adaptation: declares `registryDependencies: ["card"]` — shadcn CLI would try to fetch plain `@shadcn/card`; dry-run first and decline any overwrite since this project has no adapted card yet, or point it at an existing pattern. | Static/grid quote-card layout, easiest to drop into a testimonials section without reworking `Button`. |
| Animated Testimonials | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/animated-testimonials` | `framer-motion` | Needs adaptation: declares `registryDependencies: ["button"]` — this project's `Button` is a hash-pinned base-nova adaptation (`src/components/ui/button.tsx`, MIT, reviewed in `qa/spectrum-registry.json`); the CLI must **not** be allowed to overwrite it — dry-run and manually rewire the fetched demo to import the existing `Button` instead. | Rotating single-quote hero variant with photo/name swap animation — more "Awwwards" feel than a static grid, at the cost of the Button collision to manage. |

## Accordion / FAQ

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **FAQ Tabs Card** — *recommended* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/faq-tabs-card` | `motion`, `lucide-react` | Yes — uses `motion`, no registryDependency collisions | Tabbed FAQ card with animated accordion answers and a support footer in one file — most complete single unit for this category. |
| Accordion (Spectrum) | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/accordion` | none direct; pulls `@spectrumui/accordion-dependencies` | Yes, but thin | The fetched file targets `accordion-demo.tsx` — it is a styled demo, not an isolated reusable primitive; lower value than FAQ Tabs Card for this page. |
| Accordion (shadcn) | @shadcn | `pnpm dlx shadcn@latest add @shadcn/accordion` | `radix-ui` | Yes | Clean unstyled Radix primitive — the right base only if building a custom FAQ layout from scratch instead of FAQ Tabs Card. |

## Tabs

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Tabs (shadcn)** — *recommended* | @shadcn | `pnpm dlx shadcn@latest add @shadcn/tabs` | `radix-ui` | Yes | Accessible, unstyled Radix tabs primitive for any general content-tab need (e.g. product/feature tabs) outside the FAQ card, which already bundles its own tabs. |

## Before/after or comparison

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Dark Matrix** — *recommended, closest fit* | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/dark-matrix` | `lucide-react` | Yes | Dark plan/feature comparison table — dashed rows, mint checks, per-plan CTA pills, own `reveal.ts` scroll-reveal helper. Fits a "why us vs. status quo" feature-comparison table, not a literal two-image slider. |

**Not found**: a draggable image before/after slider (two images + drag divider) does not exist
in either registry. If the page needs a literal visual before/after, it must be handmade with
`motion`'s drag gesture + `clip-path`.

## Spotlight / border-glow cards

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Spotlight (bundled with Bento Grid)** — *recommended* | @spectrumui | comes free with `@spectrumui/bento-grid` (see above) — no separate install | `framer-motion` | Yes | Mouse-follow spotlight/glow on card hover; already required for the bento grid so it costs nothing extra. |
| Beam Card — *reuse* | @spectrumui | already installed | `border-beam` | Yes | Animated traveling/pulsing border-glow for a standalone highlighted card outside the grid. |

## Sticky scroll reveal

**Not found in any registry.** The search terms only matched unrelated items (infinite scroll,
skeleton reveal, disclose-image door-panel reveal, scratch card, follow button) — none implement
scroll-linked sticky pinning. Must be handmade with `motion`'s `useScroll`/`useTransform` plus
CSS `position: sticky`. The project already has `.agents/skills/cloudfloo-premium-scroll-motion/`
covering exactly this pattern (deterministic progress, reversible state, reduced-motion
fallback) — consult it before hand-building.

## Text generate / blur-in effects

| Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|
| **Orbital Letters** — *recommended, shared with hero* | @spectrumui | same as hero section above | `framer-motion` | Yes | Same component as the hero reveal; character-level entrance doubles as the "text generate" effect. |
| Text States | @spectrumui | `pnpm dlx shadcn@latest add @spectrumui/text-states` | none listed | Yes | Genuine blur exit/enter transition, but scoped to short label swaps (e.g. a stat label or status word), not a paragraph-level generate effect. |

No literal "type-and-blur-in word by word" effect (à la Aceternity's TextGenerateEffect) exists
in either registry; Orbital Letters + Text States are the two adaptable building blocks.

## Dot / grid patterns

**Not found in any registry.** "Offset Tiers" mentions a dot grid only as a decorative backdrop
inside a full pricing block, not as a standalone pattern component. This is the cheapest item on
the list to hand-build: a single CSS `background-image: radial-gradient(...)` tile with a
Tailwind arbitrary-value or a tokenized utility — no library needed.

## CTA section with glow

No single "CTA section" block exists in either registry. Recommended composition rather than a
single install: wrap the CTA panel in the **Spotlight** or **Beam Card** primitives above (both
already available cheaply — Beam Card is already installed, Spotlight ships with Bento Grid),
then place the handmade gradient/shimmer button (see the buttons section) inside it. **Serif
Tiers** (`@spectrumui/serif-tiers`, a pricing-tier component with "a black featured card lit by a
crimson glow") is worth opening as a reference for the exact glow recipe even though it is not
meant to be installed as-is for a plain CTA band.

## Not found in any registry, must be handmade with `motion`

- Marquee / logo cloud (infinite horizontal scroll track)
- Node-to-node animated connection beam between two DOM refs (Magic UI `AnimatedBeam`-style)
- Sticky scroll reveal (scroll-linked pinning) — see `cloudfloo-premium-scroll-motion` skill
- Draggable image before/after comparison slider
- Dot/grid decorative background pattern
- Pure shimmer/gradient CTA button (not a state-morph button)
- A single-component "CTA section with glow" — compose from Spotlight/Beam Card + a handmade button instead

## Constraints the implementer must respect

From `ui/qa/check-contracts.mjs` (Stage 8 source-contract check, run via
`cd ui && node qa/check-contracts.mjs`):

- It parses every `.css` file under `src/` and every inline JSX `style={{...}}` object for
  literal hex colors, literal dimensions/zero-lengths, literal font-weights/line-heights, and
  literal keyword colors, and requires all custom properties to be declared once in
  `src/tokens/tokens.css` and referenced via `var()`. **Tailwind utility classes inside
  `src/components/ui` and `src/components/spectrumui` are exempt** because they are plain
  `className` strings, not parsed CSS — this is what makes registry components installable at
  all under this contract. Any `.css` file a registry component ships, or any inline
  `style={{}}` it uses with literal values, is **not** exempt and will fail unless the file is
  registered in `ui/qa/spectrum-registry.json` with `allowInlineGeometry: true` (as done today
  for `tree-nav.tsx` and the `charts/*` files) — this will matter for Number Ticker's rolling
  digits, Dynamic Island's morph geometry, and Metal Button's WebGL canvas sizing if any of
  those are installed.
- Every file listed in `qa/spectrum-registry.json` is hash-checked (`sha256`); editing a
  registered file without updating its hash and re-reviewing it fails the check
  (`registry-review`). New installs are not required by the checker's current loop (it only
  walks entries already in the file), but the existing project convention is to add a
  provenance entry (file, sha256, source URL, `allowInlineGeometry`) for every new Spectrum/
  shadcn file, and the workflow skill (below) expects the same.
- `src/components/` outside `ui/` and `spectrumui/` is checked against a **fixed allowlist of
  exactly 15 named product components** (`ActionButton`, `BrandMark`, `Panel`, …); a registry
  install must never land as a 16th "public" component or under an unlisted name, or the check
  fails on `component-count`/`component-name`.
- A **data-boundary** check forbids any of those 15 components (or `src/domain/**`) from
  importing `src/data/**`, `src/sample.ts`, or a `.json` file directly — a registry component
  wired into the page must stay pure and receive content as props from the composing page/
  entrypoint, not import sample or API data itself.
- License/provenance notices (`public/licenses/spectrum-ui.txt`, `shadcn-ui.txt`) must stay in
  sync — Spectrum components are Apache-2.0, the shadcn Button is MIT.

From `.agents/skills/spectrum-ui-workflow/SKILL.md` (mandatory Spectrum workflow, owner
instruction 2026-09-09):

- Spectrum is mandatory when a suitable component exists; this is a search/compare obligation,
  not "install the whole catalog" — an install is still scoped to only the chosen items and
  their required dependencies.
- No `--all`, no `--overwrite` on existing files; dry-run/diff before installing, which matters
  here specifically for **Testimonials** and **Animated Testimonials** (`registryDependencies`
  on plain `card`/`button` that would collide with this project's already-adapted, hash-pinned
  `Button`).
- Verify before adopting: no Next.js/RSC-only APIs, correct aliases, Tailwind/CSS variable
  compatibility, peer dependencies, remote assets, license, portal/focus-trap needs, and browser
  requirements (WebGL for Metal Button) — the MCP `get_component` calls used here returned
  install metadata, not full file source, so this file-level verification still needs to happen
  against the actual fetched source before installing any item.
- All motion must ship a `prefers-reduced-motion` fallback, pause off-screen/long sequences, and
  any modal-like overlay (not used by this inventory's picks, but relevant if Responsive Modal
  or Animated Drawer are pulled in later) needs focus-trap, Escape-to-close and focus restore.
- Record an explicit exception (searched items, concrete obstacle, smallest adaptation) rather
  than silently handmaking a substitute when Spectrum has no equivalent — the "not found"
  sections above are written to satisfy that requirement for this pass.
- A written recommendation or an installed component is not itself a completed migration —
  build/typecheck, behavior tests, the 390px/desktop + axe check, and computed-style
  verification are still required after any real install.

## Public registries (@magicui, @aceternity)

Added to `ui/components.json` for this pass: `"@magicui": "https://magicui.design/r/{name}.json"`
and `"@aceternity": "https://ui.aceternity.com/registry/{name}.json"`. Both resolved through
`mcp__shadcn__get_project_registries` and returned real search/view results — no revert needed.
One access boundary surfaced while viewing sources: **every `registry:ui` item from both
registries viewed cleanly, but every `registry:block` item tried from `@aceternity` returned
`UNAUTHORIZED`** (`logo-cloud-marquee`, `logo-cloud-with-blur-animation`, `spotlight-shader`) —
Aceternity's composed marketing "blocks" appear to sit behind a Pro/paid tier the MCP's
credentials don't clear, while its base `ui` primitives (`sticky-scroll-reveal`,
`text-generate-effect`) are open and installable. Only registry:ui items are used as picks below
for that reason.

| Gap category | Item | Registry | Install | Deps | Compat | Why premium |
|---|---|---|---|---|---|---|
| Marquee / logo cloud | **Marquee** — *now recommended, replaces handmade* | @magicui | `pnpm dlx shadcn@latest add @magicui/marquee` | none listed | Yes | Pure CSS-animation infinite scroll track for text/images/logos — exactly the missing primitive; pair with the `marquee-logos` example for the logo-cloud layout. |
| Marquee / logo cloud | Logo Cloud Marquee / Logo Cloud with blur or swap animation | @aceternity | n/a — `UNAUTHORIZED` | unknown | **Blocked**: registry:block, gated behind Aceternity auth this MCP doesn't have | Would have been a closer out-of-the-box logo-cloud block; record as the exception and use Magic UI's `marquee` + own logo assets instead. |
| Animated beam / connecting lines | **Animated Beam** — *now recommended, replaces handmade* | @magicui | `pnpm dlx shadcn@latest add @magicui/animated-beam` | `motion` | Yes — uses `motion`, already a project dependency | This is exactly the node-to-node "connect two DOM refs with a traveling light" primitive the earlier pass found missing everywhere; ships uni-/bidirectional and multi-input/output example variants. |
| Animated beam / connecting lines | Border Beam | @magicui | `pnpm dlx shadcn@latest add @magicui/border-beam` | none listed | Yes | Perimeter-travel beam equivalent to the Spectrum `border-beam` already installed in this repo via `beam-card.tsx` — no new value, skip. |
| Dot / grid patterns | **Dot Pattern** / **Grid Pattern** — *now recommended, replaces handmade* | @magicui | `pnpm dlx shadcn@latest add @magicui/dot-pattern` / `@magicui/grid-pattern` | none listed | Yes | Tailwind-customizable SVG background patterns — a direct, dependency-free hit for the missing category; `animated-grid-pattern` and `interactive-grid-pattern` exist too if the section wants motion/pointer response. |
| Sticky scroll reveal | **Sticky Scroll Reveal** — *now recommended, replaces handmade* | @aceternity | `pnpm dlx shadcn@latest add @aceternity/sticky-scroll-reveal` | `motion` | Yes — `registry:ui`, resolved and viewed without auth issues | Direct hit for the missing category: scroll-linked sticky panel with content swap keyed to scroll position, the exact pattern `cloudfloo-premium-scroll-motion` describes; still verify its scroll-progress math against that skill's determinism/reversibility requirements before wiring it in. |
| Text blur-in / generate | **Text Generate Effect** — *now recommended, replaces the Orbital Letters/Text States workaround* | @aceternity | `pnpm dlx shadcn@latest add @aceternity/text-generate-effect` | `motion` | Yes | The literal word-by-word opacity/blur generate effect (Vercel/Aceternity-style) the first pass could not find; use for body-copy or sub-headline reveals, keep **Orbital Letters** for the character-orbit hero title treatment since the two solve different reveal shapes. |
| Text blur-in / generate | Blur Fade | @magicui | `pnpm dlx shadcn@latest add @magicui/blur-fade` | `motion` | Yes | Simpler blur+fade-in wrapper for any element (cards, images) entering on scroll — a lighter-weight complement to Text Generate Effect for non-text content. |
| Shimmer or gradient button | **Shimmer Button** — *now recommended, replaces handmade* | @magicui | `pnpm dlx shadcn@latest add @magicui/shimmer-button` | none listed | Yes | Exact hit: a shimmering-light perimeter travel on a button, dependency-free — apply the same `Button` composition caution as the testimonial items below (build it as a wrapper around the existing base-nova `Button`, don't let it replace it). |
| Shimmer or gradient button | Rainbow Button | @magicui | `pnpm dlx shadcn@latest add @magicui/rainbow-button` | none listed | Yes | Animated conic-gradient border alternative to Shimmer Button if a more colorful CTA fits the palette better; also dependency-free. |
| CTA section with glow | **Magic Card** — *now recommended as the CTA wrapper, upgrades the prior "compose from Spotlight" answer* | @magicui | `pnpm dlx shadcn@latest add @magicui/magic-card` | `motion`, `next-themes` | Needs adaptation: pulls in `next-themes`, a Next.js-associated theme-context library. It is framework-agnostic at runtime (plain React context, no Next API), so it should work under Vite, but this must be verified directly — and this repo already has its own light/dark signal (`useSurfaceTheme` in `src/components/spectrumui`), so prefer wiring Magic Card to that existing hook instead of installing a second theme system. | Mouse-follow spotlight + border-highlight on hover — wrap the CTA panel in this, then put Shimmer Button or Rainbow Button inside it, for a complete glowing CTA section built from two small dependency-light primitives instead of one handmade composite. |
| CTA section with glow | Spotlight Shader | @aceternity | n/a — `UNAUTHORIZED` | unknown | **Blocked**: registry:block, gated behind Aceternity auth | Would have been the more literal "dynamic spotlight background" block; record as the exception, use Magic Card (above) or the Spectrum `spotlight.tsx` bundled with Bento Grid instead. |

## MCP calls that failed

- `mcp__shadcn__search_items_in_registries(query="marquee", registries=["@magicui"])` →
  `NOT_CONFIGURED`: `@magicui` is not defined in `ui/components.json`'s `registries` map.
- `mcp__shadcn__search_items_in_registries(query="marquee", registries=["@aceternity"])` →
  `NOT_CONFIGURED`: same cause, `@aceternity` is not configured.
- `mcp__spectrum-ui__get_component(name="fluid-ink-morph")` → not found (the category listing
  shows a "Fluid Ink Morph" item exists under `General`, but the display title does not resolve
  as a slug through `get_component`; not deep-dived further in this pass).
- `mcp__spectrum-ui__get_component(name="3d-tilt-card")` → not found, same cause as above for
  "3D Tilt Card".

These four were the only failures in the first pass. After adding `@magicui` and `@aceternity` to
`ui/components.json`'s `registries` map (this follow-up's scope), both registries resolved
successfully via `mcp__shadcn__get_project_registries` and every search against them returned
data — no revert was needed for either registry entry. Three later `view_items_in_registries`
calls did fail, all against `@aceternity` `registry:block` items specifically:

- `mcp__shadcn__view_items_in_registries(items=["@aceternity/logo-cloud-marquee"])` → `UNAUTHORIZED`
- `mcp__shadcn__view_items_in_registries(items=["@aceternity/logo-cloud-with-blur-animation"])` → `UNAUTHORIZED`
- `mcp__shadcn__view_items_in_registries(items=["@aceternity/spotlight-shader"])` → `UNAUTHORIZED`

All three are `registry:block` items (composed marketing sections); every `@aceternity`
`registry:ui` item tried (`sticky-scroll-reveal`, `text-generate-effect`) viewed without error,
so the boundary looks like a paid/Pro tier on Aceternity's composed blocks rather than a broken
registry connection — the `@aceternity` entry in `components.json` stays, since the registry
itself is reachable and useful for its free `ui` items.
