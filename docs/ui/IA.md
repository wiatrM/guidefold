# Guidefold UI — Information Architecture

**Status:** Proposed · 2026-09-04 · covers MVP stories E5.1 (`guidefold ui`) and E5.2 (promotion review)
**Companion documents:** [`UX.md`](UX.md) (interaction principles), [`UI.md`](UI.md) (visual system + React port)

---

## 1. What this UI is for

Guidefold's product surface is a CLI and two hooks. The UI is **not** where work happens; it is
where two questions get answered that a terminal answers badly:

| Question | Who asks it | Today's answer | UI answer |
|---|---|---|---|
| "What guidance governs this part of the repo, and where did it come from?" | Dev, Owner, new joiner | `guidefold find` + reading YAML | **Atlas** — the scope graph |
| "Should this piece of knowledge be promoted, and what happens if I say yes?" | Owner (CODEOWNER) | a GitHub PR with a Markdown pack | **Review** — the promotion desk |

Everything else the UI shows exists to support those two. Nothing in the UI writes to Git or to
the registry: **the UI proposes and explains; GitHub decides** (ADR-0017). The only state the UI
owns is the decision log in Postgres (ADR-0013/0018), and even there it records decisions made in
GitHub rather than making them.

### Non-goals for MVP

- No skill *authoring* in the browser. `SKILL.md` is edited in the repo, reviewed in a PR.
- No registry administration. The registry is a build artifact (ADR-0001).
- No dashboards-for-dashboards. Every metric on screen must be one a weekly report (MVP §6) names.

---

## 2. Audiences and their entry points

| Role | Arrives from | First screen | Success in one sentence |
|---|---|---|---|
| **Owner** (CODEOWNER) | e-mail / Slack link on a `proposal/*` PR | **Review · Proposal** (deep link) | Decides in < 15 min with evidence in front of them (M3 criterion). |
| **Dev** | `guidefold ui` in a terminal, cwd = their node | **Atlas** focused on their node | Sees which 4 cards the hook would inject for a task, and why. |
| **Platform** | bookmark | **Health** | Sees propagation time, routing metrics, and acceptance rate for the week. |
| **ML** | bookmark | **Routing · Eval** | Compares a candidate ranking config against the golden set. |

Owner is the **primary** audience. If a trade-off appears, the owner's 15-minute review wins.

---

## 3. Top-level structure

Four sections. Flat, not nested — a fifth section is a design smell, and a sub-navigation level
inside a section must be justified against the 15-minute review budget.

```
Guidefold
├── Atlas        the scope graph: nodes, skills, edges, coverage        (E5.1)
├── Review       proposals awaiting a decision + the decision log       (E5.2)
├── Routing      what the hook would return, and how good that is       (E1.2, E1.5)
└── Health       propagation, drift, probation, weekly metrics          (E2.3, E4.1)
```

### 3.1 Atlas — "where is this knowledge?"

The scope graph is the product's spine, so it is the default landing view.

```
Atlas
├── Graph view          nodes as a tree/DAG, skills as leaves,
│                       edges: requires · refines · replaces · similar
├── Node inspector      (right panel, opens on select)
│     ├── Identity      dotted path, owner, subteams, path globs
│     ├── Card          the exact L0 card `guidefold card` renders  ≤ 6 KB
│     ├── Skills        this node's skills, status, last revision, drift flag
│     └── Inherited     ancestors' skills, general → specific
└── Skill inspector     (drill-down from a node)
      ├── Body          rendered SKILL.md
      ├── Metadata      kind, triggers, negative triggers, layer, status
      ├── Edges         requires closure ▸ refines parent ▸ replaces ▸ similar
      ├── Provenance    lifted_from urn@sha, revisions, publishing history
      └── References    code paths + anchors, with drift state
```

**Object model shown to the user** (matches the CLI, no UI-only concepts):

- **Node** — dotted path (`atlas.identity.turnstile`), owner, path globs. Root is `_root`.
- **Skill** — `urn:skill:<publisher>:<node>:<name>`, a `kind` (5 families in MVP), a `status`.
- **Edge** — `requires` (hard, closure is followed at selection), `refines` (child specialises
  parent), `replaces` (supersedes a deprecated skill), `similar` (retrieval neighbour, advisory).
- **Revision** — immutable, `(urn, revision)`; the cache key (E1.7).
- **Index** — an immutable artifact identified by a git sha; every routing answer cites one.

The four edge kinds are visually distinct and independently toggleable. `similar` is off by default —
it is dense and machine-derived, and leaving it on turns the graph into hairball soup.

### 3.2 Review — "should this be promoted?"

One proposal is one page, and that page is the deep-link target from the PR. Section order is fixed
and mirrors the Promotion Review Pack (E3.2), because a fixed order is what makes repeated review fast:

```
Review
├── Queue               proposals by state · filter by node, owner, age
└── Proposal            (the 15-minute page)
      1. Decision bar   Approve in GitHub ▸ Request changes ▸ Reject   (always visible)
      2. Summary        target node · kind · one-paragraph claim · proposer (human or model)
      3. Sources        the 2–8 team skills this was lifted from, each linked, each with a diff
      4. Parent diff    what the promoted parent will say
      5. Child patches  per-source `refines` link + the text each child loses
      6. Evidence       routing before/after on the golden set + paired scenarios (E3.3)
      7. Impact         nodes affected · devs in scope · injections per week (estimated)
      8. Gates          G1 structure · G2 novelty · policy · owner quorum
      9. Provenance     model, prompt hash, input URNs, shard sha
```

The **decision bar is a link to GitHub**, never a write. Rejections capture a reason and feed the
90-day rejection memory (E3.5); the UI is the only comfortable place to type that reason, so the
reject path gets a first-class form rather than a free-text afterthought.

```
Review › Decision log     append-only: proposal · gates · evidence · decision · reason · actor
                          filterable by node and outcome; this is the acceptance-rate source
```

### 3.3 Routing — "what would the hook do?"

```
Routing
├── Probe               type a prompt, pick a cwd → the exact ≤ 4 cards the hook returns,
│                       with per-stage attribution: policy filter ▸ BM25 ▸ dense ▸ RRF ▸
│                       reverse PPR ▸ requires closure ▸ selection
├── Eval                golden-set run: Hit@1, Recall@8, nDCG@10, Completeness@K,
│                       abstention precision — one row per index sha / config
└── Shadow              `find --experimental` reranker telemetry: agreement, deltas, latency
```

The Probe is the debugging tool that makes routing arguable instead of mystical. It must show the
**score at each stage**, not only the final list — a card that lost at RRF and a card that lost at
the policy filter are different bugs.

### 3.4 Health

```
Health
├── Propagation     merge → hook, p50/p95 (E2.3 target: 10 min)
├── Hook latency    p50/p95 warm, watchdog trips (E1.5 target: 300 ms / 3 s)
├── Drift           skills whose referenced code changed, by owner
├── Probation       probationary skills, loads, Wilson lower bound, days remaining (E4.1)
└── Weekly report   the MVP §6 metric set, one printable page
```

---

## 4. Navigation model

- **Persistent left rail** — the four sections plus the current scope selector. The scope selector
  is global state: choosing `atlas.identity` in Atlas keeps you there when you switch to Routing.
- **Right inspector panel** — context for the selected object. Opens over content, never navigates
  away. Closing it returns you to exactly where you were.
- **URL is the state.** `/atlas/atlas.identity.turnstile/skills/postgres-auth?index=8f2c1a0`.
  Every view is deep-linkable and every screenshot in a PR comment is reproducible. This is not a
  nicety: E1.5 promises identical output for identical `(prompt, cwd, sha)`, and the UI must be able
  to demonstrate that claim.
- **Command palette (`⌘K`)** — jump to a node, a skill by URN, or a proposal by id. This is the
  power path for owners who live in the terminal, and it is the reason the nav rail can stay at four items.
- **No modals except confirmation.** A modal that contains information is a page that lost an argument.

---

## 5. Content model per screen

Each screen declares its **primary object**, its **evidence**, and its **one action**. If a screen
cannot name all three, it does not ship.

| Screen | Primary object | Evidence shown | The one action |
|---|---|---|---|
| Atlas · Graph | Node | coverage, skill count, drift count | Select a node |
| Atlas · Skill | Skill revision | references + drift, edges, provenance | Open in repo |
| Review · Proposal | Proposal | sources, diffs, routing delta, gates | Decide (in GitHub) |
| Routing · Probe | Ranked card list | per-stage scores, index sha | Copy as a golden-set case |
| Routing · Eval | Eval run | metric table vs. baseline | Promote config to default |
| Health | Time series | thresholds from MVP §6 | Open the offending object |

"Copy as a golden-set case" is deliberate: the fastest way to grow the golden set (E1.2) past 300
queries is to let a human turn any surprising probe result into a labelled case in one click.

---

## 6. States every view must define

Enterprise UIs die in the states nobody drew. Each view specifies all six:

1. **Empty** — no skills at this node yet; say what to run to create one.
2. **Loading** — skeleton with the correct row height, never a spinner over a jumping layout.
3. **Partial** — index is stale relative to `main`; show the index sha and its age.
4. **Error** — Postgres or GCS unreachable; the Atlas still renders from the last index.
5. **Degraded** — reranker disabled, telemetry off, or probation scorer behind.
6. **Restricted** — the viewer is not a CODEOWNER for this node: read everything, decide nothing.

---

## 7. Information hierarchy rules

1. **Provenance is never more than one click from any claim.** Every skill body, every promoted
   parent, every metric names its source object and index sha.
2. **General → specific, always.** Inherited guidance renders root-first; the hook injects in the
   same order. The UI must not invent a different sort or the mental model breaks.
3. **Scope is a filter, not a ranking.** Mirrors E1.1: never present scope proximity as relevance.
4. **Deprecated is visible but never default.** Shown greyed with its `replaces` target, excluded
   from counts and from routing previews unless explicitly enabled.
5. **Machine-generated content is labelled at the point of reading**, not in a footer.

---

## 8. Build order

| Phase | Ships | Serves |
|---|---|---|
| **UI-0** (week 6) | Review · Proposal + Decision log, read-only, deep-linked from the PR | E5.2, M3 review-time measurement |
| **UI-1** (week 7) | Atlas graph + node/skill inspectors | E5.1 |
| **UI-2** (week 7–8) | Routing Probe + Eval table | E1.2 debugging, ML workflow |
| **UI-3** (week 8) | Health | MVP §6 weekly report |

Review ships first because it is the only screen on the critical path of the M3 go/no-go. An Atlas
that nobody uses to make a decision is a demo; a review page that halves owner review time is the product.

---

## 9. Open questions

1. **Auth.** GitHub OAuth with CODEOWNERS-derived permissions is the obvious fit, but the
   probationary-serving story (E3.6) needs an identity for telemetry too. One identity or two?
2. **Graph scale.** The fixture has 17 nodes / 26 skills. The pilot has ~200 skills; a real monorepo
   has thousands. At what size does the graph view need semantic zoom rather than pan/zoom?
3. **Offline.** `guidefold ui` is a local command. Does it serve from the local index artifact only
   (works on a plane, no decision log) or require Postgres (full features, no offline)? Proposal:
   local index only for Atlas + Routing, Postgres required for Review + Health, stated in the UI.
