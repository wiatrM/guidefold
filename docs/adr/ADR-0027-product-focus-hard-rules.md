# ADR-0027: Product focus — hard rules until the pilot decides

**Status:** Accepted · 2026-09-06 · decision of the product owner ("zapisz te ustalenia jako HARD RULE w ADR i trzymaj się tego")
**Amends:** ADR-0024 (the target architecture stands; this ADR fixes *what is built now* and forbids the rest), ADR-0023/0026 (service surface frozen at what is merged)
**Governs:** `docs/MVP.md` §5, the GitHub issue backlog, every agent dispatch

## Context

Two days, 68 pull requests, five research families closed with honest negatives, a Go service with proven
parity, telemetry, an authoring loop — and **no real developer has used any of it in a real harness**. The
router's flagship example printed the right skill 7th of 8 until PR #68. Meanwhile parallel tracks were
spawning components (GPU shadow worker, ParadeDB, k8s lifecycle, vector layout, graph admission) for a product
whose value, if it exists, sits in the local tier and a single-node service with sparse retrieval. The owner's
verdict: "we are supposed to deliver concrete value, not burn tokens." This ADR turns the 2026-09-06 assessment
into rules that bind the plan, the backlog and every agent brief.

### What the assessment established
- **Customer:** the platform team of a large organisation running several agent harnesses (Claude Code,
  Copilot, Codex, Gemini) over one monorepo with many teams. Not the individual developer — vendors will
  solve single-vendor/single-repo discovery themselves.
- **Defensible value:** (1) one discovery/scoping/measurement layer across harnesses and the monorepo's scope
  hierarchy; (2) the **authoring loop** — CI that tells a skill author, before merge, what their text does to
  retrieval (collisions, missing triggers, never-exposed skills); (3) **measurability** — gates, confidence
  intervals, per-tenant admission with rollback. Process and data, not an algorithm.
- **Not the value:** the model. Dense retrieval reproduces +17 pp in-distribution and +0.7 pp out of it; it is
  a research track with a pre-registered programme, not a product dependency.
- **The only number that decides:** developer value (the "one minute a day" hypothesis) — measured by the
  pilot E6.7, nothing else.

## Decision — the hard rules

1. **Surface freeze.** No new runtime components, languages, databases, workers or deployment targets until
   the pilot E6.7 has reported. The frozen product surface is: the single-file client (tiers T0/T1), the Go
   SEARCH/USE service exactly as merged (sparse-only, parity-gated, Postgres ledger), CI templates, the
   authoring loop, telemetry. Anything else that already exists (TEI/GPU shadow worker, k8s lifecycle, vector
   layout, graph admission) is **parked**: kept on its branch or behind a flag, not extended, not on the
   critical path, not in the runbook.
2. **Product = T0/T1 sparse + authoring loop + telemetry.** Dense retrieval (family E and successors) continues
   only as the single research track under DENSE-PROGRAM, on the GPU, with its own gates; it never becomes a
   dependency of a shipped path and never claims quality without the pre-registered test-once run.
3. **"Done" means used.** A feature is done when a real developer has used it in a real harness session on a
   real repository and the telemetry shows it (E2.2), not when tests pass on the fixture. Every epic names the
   user, the value and the measurement that proves it.
4. **One backlog, on GitHub Issues.** Epics and stories live as issues with labels, acceptance criteria and the
   measurement; `docs/MVP.md` §5 is the narrative, the issues are the source of truth for *what is next*. No
   agent is dispatched without an issue number in its brief, and no issue is opened without the value sentence.
5. **Research budget.** At most one research family in flight; dev budget ≤ 6 configurations; test corpora once
   per frozen variant; a negative result closes the family and is written down (unchanged from
   DENSE-PROGRAM §3–§5).
6. **Decision point.** The pilot E6.7 (3 teams, 20–40 paired tasks, frozen protocol, 8 owner placeholders
   filled) is the go/no-go for anything beyond T1. Until then, the order of work is: make T0/T1 usable by a
   design partner → four weeks of real use with telemetry → pilot → decide.
7. **KISS review before merge.** A PR that adds a component, a dependency or a configuration key must state
   which rule above permits it; the reviewer rejects by default.

## Consequences

- The Codex service tracks beyond what is merged are paused; their branches stay; their owners are told which
  rule applies. `deploy/t1/` is the only supported deployment until the pilot.
- Family E finishes its pre-registered run (it is the one research track) and reports; no family F/G opens.
- The backlog is rebuilt as GitHub Issues by a product-owner/product-manager pass that compares the current
  scope with the competition (vendor-native skill discovery, instruction-file conventions, MCP/tool registries)
  and keeps only what serves the customer above; everything else is closed or parked with a reason.
- Token spend follows value: agent briefs are short, cite an issue, and end when the acceptance is met.

## References

`docs/MVP.md` §5 (priority table), ADR-0024 (tiers, flywheel), DENSE-PROGRAM v2.6 §7 (closed families C, D,
F1–F4), `docs/reports/bakeoff/PARITY-STRUCTURED-CORPUS-2026-09-05.md`, PR #68 (the `find` ordering defect that
motivated rule 3), the owner's 2026-09-06 assessment conversation.
