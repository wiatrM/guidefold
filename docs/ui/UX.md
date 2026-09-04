# Guidefold UI — UX principles, quality bar, and the anti-slop rules

**Status:** Proposed · 2026-09-04
**Companion documents:** [`IA.md`](IA.md) (structure), [`UI.md`](UI.md) (visual system + React port)

This document is a **gate**, not advice. A pull request that touches the UI is reviewed against
§7 (the checklist). "It looks fine" is not a review.

---

## 1. Who we are designing for, honestly

The primary user is a CODEOWNER who did not want this task. They are being asked to approve a piece
of guidance that will be injected into other engineers' agent sessions, and they have roughly
fifteen minutes between two other things. They are skeptical of the proposal, skeptical of the
model that wrote it, and entirely unwilling to click through four screens to find out what changed.

Everything below follows from that one sentence.

The secondary user is a developer who typed `guidefold ui` because the hook injected a card they
did not expect and they want to know why. They are debugging. They want numbers.

Neither of them is browsing. Neither of them is delighted by an onboarding tour.

---

## 2. Six principles

### P1 — Evidence before assertion
Never state a conclusion without the artifact that produced it within reach. "Routing improved by
12 pp" is a claim; "+12 pp Recall@8, golden set v3, 214 queries, index `8f2c1a0` vs `41bd903`,
open the diff" is evidence. Any number that cannot name its source does not go on screen.

### P2 — The decision is the interface
The proposal page exists to produce one of three outcomes. Every element earns its place by
shortening the path to a *correct* one of them. An element that neither supports nor challenges the
decision is decoration, and decoration on a governance surface is a lie about how easy the decision is.

Corollary: **make rejection as easy as approval.** UIs that make approving pleasant and rejecting
laborious manufacture consent. The reject path gets the same visual weight and a better form.

### P3 — Read-only until GitHub says otherwise
The UI never merges, never publishes, never edits a skill. It links out to the place where the
action is auditable (ADR-0017). Buttons that leave the app say so, with the destination named.

### P4 — Density is respect
This is an operator's tool. A 40 px data row, 14 px body text, real tables with real column
headers. Whitespace is used to group, not to impress. If a screen fits nine facts, do not spread
six of them over two folds of scroll and call it clarity.

### P5 — Determinism is visible
The router promises identical output for identical `(prompt, cwd, sha)`. The UI shows the sha.
Every list that came from a ranking shows what ranked it. Nothing "just appears".

### P6 — Degrade, never disappear
Postgres down: the Atlas still renders from the local index and says so. Reranker off: results
still return, badged "lexical + dense only". A blank screen with a sad emoji is a bug report the
user has to write for us.

---

## 3. Interaction rules

| Rule | Why |
|---|---|
| URL encodes full view state | Screenshots in PRs must be reproducible; deep links from Slack must land exactly. |
| One primary action per view, visually singular | Two orange buttons is zero orange buttons. |
| Inspector panels never navigate away | Owners compare; comparison dies if the back button loses the graph. |
| Destructive and irreversible actions confirm, with the consequence spelled out numerically | "Notifies 3 teams, 142 devs, activates Sep 05 09:00 UTC" beats "Are you sure?". |
| Keyboard: `⌘K` palette, `j/k` through queues, `Enter` opens, `Esc` closes | The audience lives in a terminal. |
| No auto-refresh on a page holding a decision | Content shifting under a reviewer's cursor is how wrong buttons get clicked. Show "3 new proposals — refresh" instead. |
| Latency budgets: interaction feedback < 100 ms, view transition < 300 ms, graph layout < 1 s at 500 nodes | Slower than that and the terminal wins. |
| Skeletons match final row geometry | Layout shift after load is the cheapest bug to avoid and the most common. |

## 4. Accessibility (non-negotiable, enforced in CI)

- Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI boundaries and graph edges, verified on the graphite palette.
- **Colour is never the only carrier of state.** Every badge has a word. Every graph edge kind has a
  distinct dash pattern in addition to a hue. Approximately 8 % of the male engineering audience
  cannot rely on the teal/orange distinction.
- Visible focus ring on every interactive element, safety-orange, 2 px, never removed.
- Full keyboard reachability including the graph: arrow keys traverse edges, and the node inspector
  is reachable without a pointer.
- Every icon-only control has an `aria-label`. Every table has real `<th scope>`.
- Respect `prefers-reduced-motion`: all transitions collapse to instant.
- The graph view has a **list equivalent** at the same URL (`?view=list`). A force-directed diagram
  is not accessible and will never be; the list is not a fallback, it is a peer.

---

## 5. Content and voice

- **Plain, specific, declarative.** "Blocked: 2 references no longer exist" — not "Oops! Something
  needs your attention."
- **Second person for actions, third person for system state.** "You approved this on Sep 3" /
  "The index was built from `8f2c1a0`."
- **Numbers get units and provenance.** `p95 240 ms (fixture, n=214)`.
- **Errors say what happened, what it means, and the next command.** Three sentences, maximum.
- **No exclamation marks. No "Great!", "Oops", "Uh-oh", "Let's get started".** Nobody is having fun;
  they are approving a policy change.
- Model-authored text is labelled where it is read, with the model and prompt hash one click away.

---

## 6. Anti-AI-slop rules

Generated UI has a recognisable house style, and that style reads as *unserious* on a governance
tool. These rules exist because the fastest way to lose a CODEOWNER's trust is to look like a
landing page for a product that does not exist yet.

### 6.1 Visual slop — banned outright

| Banned | Instead |
|---|---|
| Purple/indigo→pink gradients; any gradient as a surface | Flat graphite surfaces, one accent hue |
| Glassmorphism, `backdrop-blur`, translucent panel stacks | 1 px `--line` borders, opaque panels |
| Glow, neon, `box-shadow` with coloured spread | Shadow only on the one modal layer |
| Everything `rounded-2xl` / `rounded-3xl` | 2 px radius, square-shouldered geometry |
| Emoji as iconography or in headings | Phosphor icons, one weight |
| Hero section, oversized centred headline, marketing tagline inside the product | A page heading with an eyebrow and the object's identity |
| Three equal "feature cards" with an icon, a bold noun and two lines of filler | The actual data table |
| Decorative sparklines, gauges and progress rings with no defined scale | Numbers, or a chart with labelled axes |
| Fake data left in a shipped view ("Riverside Team", "Acme Corp", lorem) | Real objects, or a labelled empty state |
| Dark theme chosen for looks, then low-contrast grey-on-grey text | Dark chosen for long sessions, contrast verified |
| Animated gradient borders, shimmer, pulsing dots, confetti | Nothing moves unless state changed |
| A dashboard of tiles nobody asked for as the landing screen | The scope graph, which is the product |
| Icon + big number + tiny grey label, repeated six times across the top | At most four metrics, each one from MVP §6 |

### 6.2 Copy slop — banned outright

- "Unlock", "Seamless", "Effortless", "Powerful", "Robust", "Elevate", "Streamline",
  "Supercharge", "Delve", "Leverage" (as a verb), "Empower", "Journey", "In today's fast-paced…".
- The rule of three as a reflex ("fast, simple, and secure"). Say the one thing that is true.
- Vague attribution: "studies show", "experts agree", "it is widely considered".
- Em-dash-per-sentence rhythm and "It's not just X — it's Y" constructions.
- Headings that are complete sentences with a verb in the middle voice ("Understanding your scope
  graph"). Headings are noun phrases: "Scope graph".
- Tooltips that restate the label. If the label needs a tooltip, fix the label.
- Any sentence a person would not say out loud to a colleague.

### 6.3 Structural slop — the harder ones

- **Symmetry for its own sake.** Two panels of unequal importance rendered at equal size teaches the
  wrong hierarchy. The gate panel is narrower than the route panel because it matters less at the
  moment of reading.
- **Inventing content to fill a grid.** If the right column has three real facts, the column is
  short. Short is fine.
- **Component sprawl.** One badge component, one panel component, one table. A second variant needs
  a written reason in the PR.
- **Configurability instead of a decision.** Every user-facing toggle is a design decision we
  declined to make. Density (Compact/Balanced/Comfortable) survives because operators genuinely
  differ; theme switching does not.
- **Charts that answer no question.** Every chart states its question in its title.

### 6.4 The two tests

**The screenshot test.** Take any screen, remove the logo, show it to an engineer and ask what the
product does. If the honest answer is "some kind of AI dashboard", the screen has failed.

**The read-aloud test.** Read every string on the screen aloud in the voice you would use to a
colleague at their desk. Anything you would be embarrassed to say is slop. This catches copy the
eye skims over.

---

## 7. PR checklist (the gate)

A UI pull request states, in its description, that each line is true. A reviewer who cannot verify
a line rejects the PR.

- [ ] The view declares its **primary object, its evidence, and its one action** (IA §5).
- [ ] All six **states** are implemented: empty, loading, partial, error, degraded, restricted.
- [ ] **URL fully encodes view state**; reload lands identically.
- [ ] Every number on screen **names its source** (index sha, run id, n).
- [ ] **Colour is not the only** carrier of any state; every badge has a word; every edge kind a dash pattern.
- [ ] Keyboard path complete; focus visible; `aria-label` on every icon-only control.
- [ ] Contrast checked against the graphite palette (automated axe run in CI is green).
- [ ] `prefers-reduced-motion` honoured.
- [ ] **No item from §6.1 or §6.2 appears.** Grep the diff for the banned word list; CI does this too.
- [ ] No placeholder or fictional data in a shipped path.
- [ ] No new component variant without a written justification.
- [ ] Read-aloud test performed on all new strings.
- [ ] Latency budgets met on the fixture (§3).

---

## 8. What "clean" means here, concretely

Clean is not minimal. A dense table of twelve columns can be clean; a page with one centred card
and a gradient usually is not. Clean means:

1. **Every pixel is doing a job** that maps to a fact in the domain model.
2. **Alignment is systematic** — one 8 px grid, one type scale, one border colour.
3. **The visual hierarchy matches the decision hierarchy** — what matters most is what you see first,
   measured by asking someone what they looked at, not by asking a designer what they intended.
4. **Nothing is there because the framework made it easy.**

The Industrial Surveyor direction ([`UI.md`](UI.md)) already encodes most of this: graphite
surfaces, square geometry, one accent for human decisions, one for system health, red reserved for
failure. The job of this document is to stop that direction from drifting back toward the default.
