# Guidefold UI — visual system and the React port of the Industrial Surveyor prototype

**Status:** Proposed · 2026-09-04
**Source of truth for the direction:** `prototypes/industrial-surveyor/design-reference/source-industrial-surveyor.png`
(option 6 of the folded-map exploration, `design-explorations/guidefold-folded-map-3x3/`)
**Companion documents:** [`IA.md`](IA.md) (structure), [`UX.md`](UX.md) (principles and the anti-slop gate)

---

## 1. What we keep from the prototype, and what we drop

`prototypes/industrial-surveyor/` is a **brand and direction prototype**, not an application. It is
already React 19 + Vite, but it is one 124-line `App.jsx` of hard-coded arrays rendering three
demo tabs (Route monitor / Component bay / Asset library) against fictional data ("Riverside Team",
"Vendor Risk Policy"). It proves the look. It is not a foundation.

| Keep | Drop |
|---|---|
| Palette, typography, 8 px grid, 2 px radius, `--line` borders | The three prototype tabs and their fictional data |
| The folded survey-map `G` mark and its usage rules | The asset-library and palette-showcase screens (they are a style guide, not product) |
| Route-node → arrow → route-node promotion motif | Full-bleed decorative topographic art behind live data |
| Gate list, state badges, provenance timeline as *patterns* | Their hard-coded contents |
| Phosphor icons, one weight | Icon-as-decoration usage |
| Dark graphite as the only theme | Nothing — the light theme is explicitly out of scope for MVP |

**The port is a rewrite, not a refactor.** We lift the design tokens and roughly six component
patterns into a typed component library, then build the four IA sections against real data. The
prototype stays in the repo, frozen, as the visual reference it is.

---

## 2. Design tokens

Lifted verbatim from `prototypes/industrial-surveyor/src/styles.css`, then extended for the
application surfaces the prototype never had (tables, graph, diffs, focus states).

### 2.1 Colour

```css
/* surfaces — darkest to lightest, 5 steps, no gradients anywhere */
--graphite-950: #081014;   /* page ground */
--graphite-900: #0f1418;   /* section ground */
--graphite-850: #121a1f;   /* panel */
--graphite-800: #162126;   /* raised panel, table header, hover */
--graphite-700: #253139;   /* pressed, selected row */

/* text */
--stone-100:    #e6e8ea;   /* primary text          on 950: 14.6:1  ✔ */
--stone-300:    #aeb8be;   /* secondary text        on 950:  8.7:1  ✔ */
--steel:        #677681;   /* tertiary / disabled   on 950:  3.4:1  — non-text only */

/* semantic — one hue per meaning, never mixed */
--survey-teal:  #2ba6a0;   /* healthy, passed, active, system-derived */
--survey-teal-dim: #174d4c;
--safety-orange:#ff6a28;   /* human action required, review, focus ring */
--warning:      #efad3f;   /* probationary, stale, degraded */
--signal-red:   #e24a4a;   /* failed, blocked, rejected */

/* structure */
--line:         rgba(174, 184, 190, 0.20);
--line-strong:  rgba(174, 184, 190, 0.34);
```

**Semantic discipline.** Teal = the system is fine. Orange = *a human must act*. Yellow = provisional.
Red = failure. Orange is scarce by construction: on the proposal page it appears on the focus ring,
the pending gate, and nothing else. If orange is everywhere, the page has no call to action.

New tokens required by the application and absent from the prototype:

```css
--diff-add:     #1c3a2a;   /* diff background, additions   */
--diff-del:     #3a1c20;   /* diff background, deletions   */
--edge-requires:#e6e8ea;   /* solid  2px */
--edge-refines: #2ba6a0;   /* dashed 4 2 */
--edge-replaces:#e24a4a;   /* dashed 2 2 */
--edge-similar: #677681;   /* dotted 1 3, hidden by default */
```

Every edge kind carries **both** a hue and a dash pattern (UX §4).

### 2.2 Typography

- **Barlow Condensed 500–700** — the operational voice: eyebrows, section labels, wordmark,
  telemetry numerals. Uppercase with `letter-spacing: 0.14em` for eyebrows only.
- **Inter 400–600** — everything a person reads as prose: body, forms, tables, descriptions.
- **`ui-monospace, SFMono-Regular, Menlo, monospace`** — new, required: URNs, shas, paths, diffs,
  and any string the user might paste into a terminal. These must never be set in a proportional face.
- Both webfonts bundled locally via `@fontsource` (no Google Fonts request from an enterprise browser).

| Role | Face | Size / line-height | Weight |
|---|---|---|---|
| Page title | Barlow Condensed | 28 / 32 | 700 |
| Eyebrow | Barlow Condensed | 12 / 16, `0.14em`, upper | 600 |
| Panel title | Barlow Condensed | 16 / 22 | 600 |
| Body | Inter | 14 / 22 | 400 |
| Body emphasis | Inter | 14 / 22 | 600 |
| Table cell | Inter | 13 / 20 | 400 |
| Caption / meta | Inter | 12 / 18 | 400 |
| Code, URN, sha | Mono | 12.5 / 20 | 400 |
| Metric numeral | Barlow Condensed | 32 / 34, tabular | 600 |

### 2.3 Space, geometry, motion

- Base unit **8 px**; scale 4, 8, 16, 24, 32, 48, 64.
- Radius **2 px** everywhere. One exception: the brand mark. No pills, no `rounded-full` chips.
- Border **1 px `--line`**; `--line-strong` for structural separation (rail, panel outer edge).
- Elevation: **one** shadow level, for the confirmation dialog only. Panels are separated by borders.
- Density modes (the one surviving user toggle, UX §6.3): row height **32 / 40 / 48 px**,
  default Balanced 40 px. Minimum touch target 44 px in the mobile breakpoint.
- Motion: 120 ms `ease-out` for hover and panel open; nothing else animates. All of it collapses to
  0 ms under `prefers-reduced-motion`.
- The survey-grid background texture is retained on the page ground and the left rail at ≤ 6 %
  effective contrast. It is **removed** behind tables, diffs and the graph canvas, where it
  competes with data.

---

## 3. Layout

```
┌──────────────┬─────────────────────────────────────────┬──────────────────┐
│  Rail 264px  │  Content  minmax(0, 1fr)                │ Inspector 420px  │
│  ─────────── │  ────────────────────────────────────── │ ──────────────── │
│  mark + word │  eyebrow                                │  object identity │
│  scope       │  Page title              [ one action ] │  ─────────────── │
│  ─ Atlas     │  ─────────────────────────────────────  │  tabs            │
│    Review    │                                         │                  │
│    Routing   │  content                                │  body            │
│    Health    │                                         │                  │
│  ─────────── │                                         │                  │
│  index sha   │                                         │                  │
│  ⌘K          │                                         │                  │
└──────────────┴─────────────────────────────────────────┴──────────────────┘
```

The prototype's 342 px brand rail is a showcase width; the application rail is **264 px** because it
carries navigation and a scope selector, not a logo presentation. The inspector is an overlay panel
at ≤ 1440 px and a third column above it.

Breakpoints: `≥1600` three columns · `1200–1599` inspector overlays · `900–1199` rail collapses to
icons · `<900` read-only mobile (queue and proposal only; the graph falls back to `?view=list`).

The bottom of the rail permanently shows the **index sha and its age** — the single most important
piece of provenance in the product, and the thing a screenshot must always carry (UX §P5).

---

## 4. Component inventory

Fourteen components. A fifteenth needs a written justification in the PR (UX §6.3).

**Lifted from the prototype** (pattern kept, contents replaced):

| Component | Prototype origin | Application use |
|---|---|---|
| `<BrandMark>` | `BrandMark` | rail, favicon, empty states |
| `<Eyebrow>` | `.eyebrow` | above every page and panel title |
| `<Panel>` / `<PanelTitle>` | `PanelTitle` + `.gate-panel` | every content container |
| `<StateBadge>` | `StateBadge` | status, gate result, lifecycle — **always with a word** |
| `<GateList>` | `gates` array | proposal gates G1/G2/policy/quorum |
| `<PromotionRoute>` | `RouteNode` + `ArrowRight` | team → division → company promotion path |
| `<ProvenanceTrail>` | `provenance` array | skill and proposal history |

**New, required by the IA:**

| Component | Purpose |
|---|---|
| `<ScopeGraph>` | nodes + 4 edge kinds, pan/zoom, keyboard traversal, `?view=list` peer |
| `<DataTable>` | queues, skill lists, eval runs — sortable, keyboard, sticky header |
| `<SkillDiff>` | parent diff and child patches, unified, mono, `--diff-add`/`--diff-del` |
| `<MetricRow>` | ≤ 4 metrics, each with value, unit, delta, and its source |
| `<StageTrace>` | the routing probe: one row per stage with the score it produced |
| `<Urn>` | mono, click-to-copy, truncation at the node segment, full value in `title` |
| `<CommandPalette>` | `⌘K` — nodes, URNs, proposal ids |

Each ships with: all six states (UX), an `aria` contract, a keyboard contract, and a story in the
component gallery rendered from **fixture data only** (`examples/monorepo`), never invented data.

---

## 5. The React port

### 5.1 Target stack

| Choice | Decision | Why |
|---|---|---|
| Framework | **React 19 + TypeScript**, Vite 6 | Prototype is already React 19 + Vite 6; TS because the domain model (URN, node, edge kind, gate state) is exactly what a type system is for. |
| Routing | **React Router 7**, data-router mode | URL-is-state (UX §3) is a hard requirement; loaders make the six states explicit per route. |
| Server state | **TanStack Query** | Cache keyed by `(urn, revision)` and index sha mirrors the CLI cache contract (E1.7). |
| Styling | **CSS Modules + the token file**, no utility framework | Utility-class frameworks are the main vector for §6.1 slop; a token file plus modules keeps the system enforceable and greppable. |
| Graph | **`elkjs`** layered layout + hand-rolled SVG renderer | The graph is a layered DAG with typed edges, not a physics toy; SVG keeps it accessible, printable, and dash-patternable. |
| Icons | **`@phosphor-icons/react`**, one weight (`regular`; `fill` only inside `StateBadge`) | Carried over from the prototype. |
| Fonts | **`@fontsource`** Barlow Condensed + Inter | Carried over; no external font requests. |
| Charts | **Hand-rolled SVG** for the two charts we actually need | A charting library invites decorative charts (§6.1). |
| Tests | **Vitest** + Testing Library; **Playwright** for the review flow; **axe-core** in CI | The gate in UX §7 has to be machine-checked or it will rot. |

No component library (MUI/shadcn/Chakra). Fourteen components against a fixed token set is less code
than adapting a library away from its defaults, and the default look of every such library is
precisely what UX §6.1 bans.

### 5.2 Where it lives

```
ui/
├── package.json                  # separate workspace; the CLI stays stdlib-only (CLAUDE.md)
├── src/
│   ├── tokens/tokens.css         # §2, the single source of colour/type/space
│   ├── components/               # the 14, each: index.tsx · *.module.css · *.test.tsx · *.stories.tsx
│   ├── domain/                   # types + parsers: Urn, Node, Skill, Edge, Gate, Proposal, IndexRef
│   ├── data/                     # loaders: local index artifact, Knowledge API, telemetry
│   ├── routes/                   # atlas · review · routing · health, one folder per IA section
│   └── app.tsx
└── e2e/                          # Playwright: the owner's 15-minute review path
```

`ui/` is a sibling of `skills/`, never inside it. The skill ZIP that reaches the registry must stay
a single-file Python script plus hooks (CLAUDE.md hard constraint) — the UI must not be able to leak
into it.

### 5.3 Data sources

| Route | Source | Offline? |
|---|---|---|
| Atlas, Routing · Probe | the local index artifact (E1.4): cards, graph, `nodes.json`, manifest sha | **yes** |
| Routing · Eval | golden-set run results committed per run (E1.2) | yes |
| Routing · Shadow | `.guidefold/telemetry/*.jsonl` (E1.6) | yes |
| Review, Health | Knowledge API over the single Postgres (ADR-0013/0018) | no — state it in the UI |

`guidefold ui` serves `ui/dist` from the CLI over localhost and injects the index artifact path.
With no Postgres reachable, Atlas and Routing work fully and Review/Health render the **degraded**
state naming what is missing (UX §P6).

### 5.4 Port sequence

| Step | Work | Done when |
|---|---|---|
| **1** | Scaffold `ui/`, extract `tokens.css` from `styles.css`, wire fonts, axe + Vitest in CI | `npm run build` green; token file is the only place a hex appears |
| **2** | Port the 7 prototype components to TS + CSS Modules with the six states and a11y contracts | gallery renders all 7 from fixture data; axe clean |
| **3** | Domain types + the index-artifact loader against `examples/monorepo` | `Urn`, `Edge`, `Gate` parse the real fixture; unit-tested |
| **4** | **Review · Proposal + Decision log** (UI-0) | an owner can complete a decision path end to end; Playwright covers it |
| **5** | **Atlas** graph + inspectors (UI-1), with the `?view=list` peer | keyboard traversal works; 500-node layout < 1 s |
| **6** | **Routing** Probe + Eval (UI-2) | probe output matches `guidefold find` byte for byte for the same `(prompt, cwd, sha)` |
| **7** | **Health** (UI-3) | the MVP §6 weekly metric set renders and prints |

Step 6 has a hard correctness criterion: if the UI and the CLI disagree about what the hook would
inject, the UI is worse than useless, so the probe is tested against CLI output rather than against
its own snapshot.

### 5.5 What happens to `prototypes/industrial-surveyor/`

It stays, unmodified, with a `FROZEN.md` note pointing at this document. It is the visual reference
and the source of the raster assets (`guidefold-mark.png`, `survey-grid-pattern.png`,
`topographic-route-bg.png`), which move to `ui/public/assets/` at step 1. Its `npm run build` /
`test:sites` pipeline is not carried over.

---

## 6. Open questions

1. **Mark at small sizes.** The folded survey-map `G` is detailed; it needs a simplified 16/24 px
   variant for the favicon and the rail. Redraw as SVG rather than downscaling the raster.
2. **Graph at pilot scale.** `elkjs` layered layout is comfortable to a few hundred nodes. Beyond
   that we need semantic zoom (collapse to node level, expand on focus) — decide with real pilot data.
3. **Print.** The weekly report (Health) is the one thing people will print or paste into a deck.
   Print stylesheet, or an explicit PNG/PDF export?
4. **Light theme.** Out of scope for MVP; the palette above is dark-only by design. If an enterprise
   accessibility policy forces it, the token file is the single place it lands.
