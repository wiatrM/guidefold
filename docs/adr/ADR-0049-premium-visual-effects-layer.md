# ADR-0049: A premium visual effects layer is allowed everywhere in the console — glow, animated borders, shaders and the decorative motion categories

**Status:** Accepted · 2026-09-13 · owner, explicit: "the console gets a premium visual effects
layer — glow, animated borders (border beams, shine borders), shaders, and the decorative
categories (animated lists, animated text, number tickers, marquee, orbiting circles, dock-style
effects) — and it is allowed everywhere, on every page, with no placement restriction."
**Amends:** [docs/ui/UX.md](../ui/UX.md) §6 (Anti-slop) rows 1 and 8 of the visual table;
[.agents/skills/ui-anti-slop-gate/SKILL.md](../../.agents/skills/ui-anti-slop-gate/SKILL.md)'s
identical two rows; [docs/ui/UI.md](../ui/UI.md) §1 row 3 ("hierarchia bez efektu szkła") and row
4 (the removed `survey-grid-pattern`), narrowed rather than reversed — see Consequences.
**Purpose:** reverse the specific visual bans on gradients/glow/neon/glassmorphism and on
automatic motion/pulsing statuses, and record what the owner did **not** change: the banned-words
list, the copy rules, and every accessibility-driven constraint on motion.
**Inputs:** owner instruction 2026-09-13, given directly to the agent building
`ui/src/components/effects/*`. Builds on the shadcn/Spectrum allowances already recorded in
[ADR-0044](ADR-0044-console-on-shadcn-and-spectrum.md) and `CLAUDE.md`'s Spectrum-mandatory rule.

## Context

UX §6 and the anti-slop skill both banned, as visual patterns, "gradients as a surface,
glassmorphism, glow, neon" and "automatic motion, confetti, pulsing statuses." Those rules were
correct for the console's first read: a flat, evidence-first surveyor tool with no decorative
motion competing with the data. UI.md §1 recorded the same decision as a removal — the old
prototype's `survey-grid-pattern` and every image background were stripped from the nav rail and
mobile sheet, and short shadows replaced glass and floating tiles ("hierarchia bez efektu szkła i
pływających kafli" — hierarchy without a glass effect or floating tiles).

The owner's 2026-09-13 instruction is the opposite call for the *decorative* layer specifically:
build a coherent kit of about a dozen effects — animated borders, glow on the primary action and
on focus, a shader or animated background for chrome and empty states, number tickers, an
animated list for logs, a marquee, orbiting circles, animated text, a success moment, and loading
shimmer — and make all of it available on every page, not gated to a landing surface. This is a
taste decision about the console's visual register, not a withdrawal of the accessibility floor
those bans also happened to protect.

## Decision

1. **UX §6, row 1** ("Gradienty jako powierzchnia, glassmorphism, glow, neon → Płaskie tło
   graphite i obrys 1 px") is replaced: gradients, glow and animated borders are permitted as a
   decorative layer, sourced from `ui/src/components/effects/*`, anywhere in the console.
   Glassmorphism (`backdrop-filter` blur panels) stays out of this reversal — the owner named
   glow, animated borders and shaders, not blurred glass — and remains banned as before.
2. **UX §6, row 8** ("Automatyczne ruchy, confetti, pulsujące statusy → Ruch wyłącznie po zmianie
   stanu, z reduced motion") is replaced for the effects layer: continuous decorative motion
   (a rotating border, a drifting grid, an orbiting satellite) is permitted, not only motion tied
   to a state change. **Pulsing status badges stay banned** — the owner's list names glow,
   borders, shaders and the decorative categories, never a state indicator that pulses instead of
   reading Unknown/Partial/Unavailable; `StateBadge` is unchanged by this ADR. Confetti is not
   named in the owner's list either; the kit's success moment (`SuccessBurst`) is a check mark and
   a brief glow, not a particle celebration — see Consequences for why.
3. The same two rows in `.agents/skills/ui-anti-slop-gate/SKILL.md`'s table are amended
   identically, in the same change.
4. **UI.md §1** row 3 keeps "Krótkie cienie tylko dla kontroli, kart i warstw portalowych" as the
   base geometry, and adds: a card or panel may additionally carry a `BorderBeam` or
   `ShineBorder` from the effects kit. Row 4's removal of `survey-grid-pattern` from the nav rail
   and mobile sheet is **not** reopened — `GridField`, the new drifting-grid background, is a
   distinct component for page chrome and empty states that a route opts into, not a restored nav
   background image.
5. **What stays binding because it is accessibility, not taste** — none of this is loosened:
   - `prefers-reduced-motion: reduce` turns continuous motion off or to a single static frame.
     Every effect component gates on it (`useMotionGate`/the shader's own speed-0 path); this is
     the one requirement a screenshot cannot verify, so it is enforced in code and in tests.
   - Text contrast over or beside any effect still meets WCAG AA on the graphite ground; a glow or
     gradient never substitutes for the measured `--control-border`/ink tokens.
   - No effect carries information on its own — a status is still read from `StateBadge`'s label
     and tone, never inferred from which panel happens to glow.
   - Focus stays visible: `GlowAction`'s focus state is an *addition* to the existing
     `--focus-width`/`--focus-offset` outline, never a replacement for it.
   - No effect flashes faster than three times a second (the kit's fastest loop, the shimmer
     sweep, runs at 1600ms — roughly 0.6 Hz).
6. The banned-words list and copy rules in UX §6/§7 and the anti-slop skill are **unchanged** —
   the owner changed visuals, not language. The screenshot test and the read-aloud test still
   apply to every screen an effect touches.

## Consequences

- `ui/src/components/effects/*` is a components kit, not one more entry in the 17-component
  `expected` list `qa/check-contracts.mjs` enforces (`docs/reports/ui/effects-layer-2026-09-13.md`
  lists all fourteen). The checker's CSS/token-literal and import-boundary scans still run over
  every file in it; only the fixed CSF-story-per-component requirement is exempt, the same way
  `spectrumui` and the shadcn `ui` directory already are.
- No confetti/particle library was added. A large organisation's evidence tool does not need a
  celebration set piece for "97 skills imported," and the owner's decorative list did not name
  one; `SuccessBurst` is deliberately smaller than what Magic UI or Aceternity ship under that
  name.
- Dock-style magnification effects were read as an allowed category, not a requirement: nothing
  in the console currently has a taskbar-shaped surface for one, and building a UI element to
  justify an effect is what §3 of the owner's own instruction warns against ("a coherent kit, not
  a pile"). Recorded as a deliberate scope cut, not an oversight.
- Wiring the kit into the seven product routes (the view header treatment, a beam on the
  proposals panel, tickers on the Overview KPIs, and so on) is explicitly the *next* pass per the
  owner's instruction ("will be integrated into every page in a following pass"); this ADR and the
  kit it accepts do not themselves change any route.
