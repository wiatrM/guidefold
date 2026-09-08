# 2026-09-08 — Knowledge ascent: what we sell, how we measure it, how harnesses must be wired

**Status:** proposal, stands alongside `docs/PRODUCT-FOCUS.md`; does not edit it. Product-owner pass
required before any of this reaches a landing page (ADR-0029 rule 4).
**Scope:** the one number to sell, the benchmark that produces it honestly, the use case that makes
it concrete, and the harness configuration without which the mechanism cannot work in practice.
Companion to [ADR-0035](../../adr/ADR-0035-knowledge-ascent-in-ci.md).

## 1. The claim we can defend

Not "AI writes your documentation". Not "smarter search". The claim is narrower and testable:

> **A rule written once by one team is followed by every other team's agent, without anyone
> copying it.** Knowledge moves up the tree to the scope where it is true, and every agent below
> that scope receives it as a card it can act on.

The number behind it is the **sibling transfer rate**: the share of tasks in a sibling scope that an
agent solves correctly *only because* of knowledge ascended from a neighbouring team, measured
paired — with the ascended parent skill and without it — on the same tasks, the same model, the
same budget. It is the monorepo analogue of SkillPyramid's "unseen task" split, where removing
abstract skills cost 5.2 points while seen tasks barely moved. That is the effect a platform team
buys: the team that never wrote the rule still gets it.

Three secondary numbers, each one already measurable with what exists in this repository:

| Number | What it shows a buyer | Where it comes from |
|---|---|---|
| Unknown-component rate | how often an agent invents a service, flag or team that does not exist; a map skill at the parent should drive it toward zero | the paired harness (`research/progressive-disclosure-execution-2026-09-07/`), scoring answers against the scope's real child list |
| Context cost per task at equal correctness | tokens an agent consumed to reach the same pass rate: card-first delivery vs. concatenating every applicable file (what Gemini CLI and Codex `AGENTS.md` do today) | `exposures_expanded` / `loads_unlinked` from contract 1.1.4 on real traffic; the naive-vs-progressive token count from the same harness |
| Duplication avoided | paragraphs that now live once at a parent instead of N times below it | deterministic: `derived_from` edges written by `guidefold ascend`, counted by `guidefold report` |

What we do **not** claim until measured on a real repository: any blended percentage. The
7-skill and 70-skill pilots produced 43% and 9% token savings from the *same* mechanism because the
task mix differed; the honest statement is conditional (about 86% when a card suffices, about 0
when it does not). The same discipline applies to sibling transfer: report the paired delta with
its interval, on named repositories, never a single marketing integer.

## 2. The benchmark: sibling transfer on real monorepos

Name it plainly: **monorepo sibling transfer**. It is not a retrieval benchmark and must not be
scored with Recall@k; every number is a task outcome.

**Corpus.** Real multi-team repositories with a scope hierarchy, not the Meridian fixture (which is
dev/regression by this repo's own rule, and has exactly one planted consolidation pair). Candidates
already touched by this project: the 183-skill `wshobson/agents` import from the 2026-09-07
acceptance run, and any design-partner monorepo from the pilot. Each repository is split into
scopes by its `guidefold.yaml`; for every parent scope with at least two children, one child is the
**held-out sibling**.

**Ascent.** `guidefold ascend` runs on every *non-held-out* child's skills, producing the parent's
map and convention skills. The held-out sibling's own skills are never shown to the model that
writes the parent — that is the transfer condition.

**Tasks.** For the held-out sibling, generate body-only questions from its own skills with the
leakage gate already built in `research/progressive-disclosure-execution-2026-09-07/generate_tasks.py`
(a keyword that appears in the skill's name or description is rejected), plus **structural
questions** whose answer lives only in siblings: "which service authorizes requests in this
platform", "who owns the policy bundle", "what convention do all pipelines here follow". Structural
questions are the ones a map skill exists to answer; they are scored against the parent's real child
list, so an invented component is a scored failure, not a stylistic one.

**Arms, per task, same model, same context budget.**

| Arm | Agent sees |
|---|---|
| `own` | the held-out sibling's own skill cards, body on demand |
| `own + ascended parent` | the above plus the parent map/convention card written from the *other* children |
| `flat` | every skill under the parent concatenated until the budget is exhausted (what location-scoped competitors do) |
| `none` | nothing |

**Metrics.** Pass rate per arm; the paired delta `own + ascended parent` minus `own` with a
bootstrap interval (this is the sibling transfer rate); unknown-component rate; tokens per passed
task. Three seeds per task, temperature pinned where the provider allows it. Use
`docs/pilot/PIVOT-RUBRIC.md` and `tools/pilot/pivot_report.py` for the paired statistics; they
already implement Wilson and bootstrap intervals and label anything unmeasured as
`not_measured_here`.

**Gate for the landing page.** The claim goes public only when, on at least two real repositories,
the paired delta's interval excludes zero and the unknown-component rate with the parent card is at
or below the `flat` arm's. Anything weaker is a research note.

## 3. The use case that makes it concrete

A platform organisation with dozens of teams under `platforms/atlas/`. The identity team ships
`turnstile`, the `ext_authz` service every atlas API goes through. A new team, `ias` (identity
admin service), lands in `platforms/atlas/identity/ias/` with no skills yet.

- The turnstile team's PR that changes `postgres-auth` triggers `ascend`. The model writes
  `atlas/identity`'s map: turnstile authorizes requests, the RBAC bundle defines roles, who owns
  what. Every claim cites the turnstile and rbac skills. The identity platform owner reviews one
  80-line file in a separate PR and merges it.
- The ias team's agent, on its first task ("add an admin endpoint"), gets the identity map card in
  its four injected cards. It knows turnstile exists, that it must not re-implement authorization,
  and who to ask. It never wrote a line of that knowledge.
- The climb continues: `atlas`'s map now says identity, geo and graph exist and what each is for;
  `_root`'s map says atlas, forge and relay are the platforms. A newcomer anywhere in the tree
  starts with the shape of the organisation, not a blank context.

That is the story for the landing page, and it is exactly the sibling-transfer measurement in §2
with `ias` as the held-out sibling.

## 4. Harness configuration: what has to be true for this to work at all

An ascended skill only helps if the agent actually receives it. Three requirements, in order of
how much they are already met:

1. **Cards, not bodies, at injection time.** The hook and `find` already inject at most four cards
   (ADR-0006 ordering: general to specific, root-most first). Ascended skills are digests capped at
   80 lines and marked `knowledge_layer: abstract`, so they fit that budget. Already true.
2. **The parent map rides along with any selected child — implemented 2026-09-08.** Ascended
   skills carry deterministic names (`<scope>-map`, `<scope>-conventions`), so the hook finds the
   nearest map above the best-ranked card by URN alone, from the pre-built artifact, and prints it
   ahead of the child in a fourth slot (hook selects 3, cap 4). Ranking is untouched:
   `search_results` telemetry carries only the selected cards, the map is a `card_injected`
   exposure at position 1, and the hook path still imports no PyYAML
   (`tests/test_parent_map_delivery.py`). The service-side `family` field stays decorative until
   the paired evaluation in §2 says it may influence anything.
3. **Harnesses without a hook still see the map — implemented 2026-09-08.** `guidefold materialize`
   opens every scope card (`AGENTS.md`, `CLAUDE.md`/`GEMINI.md` via `@AGENTS.md`, and Copilot's
   `.github/instructions/<scope>.instructions.md`) with a "Scope map (general → specific)" section
   listing the ascended maps on the scope's ancestor chain, root-most first, each stated once, before
   the inherited guidance. A scope with no map above it renders exactly as before.

Two things to keep out of the harness on purpose: the full body of an ascended skill (it is a
digest; if an agent needs more it should load the cited child, which is where the procedure lives),
and any ranking influence from `knowledge_layer` — the contract forbids it until a separately
pre-registered evaluation on a real corpus says otherwise.

## 5. What this report does not do

It does not change `docs/PRODUCT-FOCUS.md`, does not claim a transfer number, and does not make
the hook read `family`. It names the number, the benchmark that would produce it, the use case that
explains it and the three harness requirements. The next concrete step is running §2 on one real
repository with `guidefold ascend` and the existing paired harness, and reporting the interval.
