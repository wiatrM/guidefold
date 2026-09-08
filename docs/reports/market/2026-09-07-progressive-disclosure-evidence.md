# 2026-09-07 — Evidence pass: does card-first retrieval preserve correctness?

**Date:** 2026-09-07 · **Status:** research evidence pass, stands alongside `docs/PRODUCT-FOCUS.md`
(2026-09-06); does not edit or replace it, and does not itself change the document's Accepted
status or its value-proposition list — that requires the product-owner/product-manager pass named
in [ADR-0029](../../adr/ADR-0029-product-focus-hard-rules.md) rule 4. **Scope:** supply the
correctness evidence value proposition 1 ("Retrieval, not concatenation, at monorepo scale")
currently lacks — the proposition is measured for latency, never for whether returning a card
instead of a full skill body costs an agent anything on the tasks that need the body.

## Why this report exists

`docs/PRODUCT-FOCUS.md` §"The three value propositions" states proposition 1 as measured, citing
two latency reports (`R4b-lazy-terms-postings-2026-09-05.md`, `E1.1b-service-feasibility-2026-09-05.md`).
Both answer "how fast is a search," not "what happens to task correctness when the agent gets a
4-line card instead of the full `SKILL.md`, and does the *existing* mechanism for getting the rest —
`docs/API-CONTRACT.md` §5.2's `SkillSummary` (`Bez body`) versus §5.3's `Revision` (`body:str?`,
fetched separately) — actually work when an agent has to decide whether it needs that second
call. That mechanism already exists in the contract. It had never been tested against a task an
agent could get wrong without the body.

## Method

Real `claude-haiku-4-5-20251001` calls (not a simulation), against 70 real skills: 26 from this
repo's own Meridian fixture (`examples/monorepo/`, the same fixture `docs/DESIGN.md` and the test
suite use) plus 44 sampled (fixed seed) from the public SkillRet corpus, for provenance diversity.
75 tasks — 7 hand-authored (one card-answerable, one body-only fact, per skill) plus 61 generated
(one body-only fact per skill, generated blind to the test, then passed through a mechanical
keyword-leakage gate that rejected 2 of 63 candidates outright before any scoring). Three arms per
task: full body only, card only (`name`+`description`+digest — Guidefold's own scope-card fields),
and **progressive** — card first, with the model allowed to answer `EXPAND: <skill>` instead of
guessing, triggering a second call with the full body.

Full protocol, raw results, and every caveat: `research/progressive-disclosure-execution-2026-09-07/`
(gitignored per this repo's research-corpus convention; not itself citable outside this repo, which
is exactly why this report exists as the durable artifact).

## Result

| | full body | card only | progressive (card, expand on demand) |
|---|---:|---:|---:|
| Card-answerable tasks (n=7) | 100.0% correct | 100.0% correct | 100.0% correct |
| Body-only tasks (n=68) | 69.1% correct | 4.4% correct | 64.7% correct |

Card-only collapses on body-only tasks, as it must — the fact genuinely is not in the card. The
question this report answers is whether an agent that only ever sees the card first can tell the
difference and ask for the body when it needs to:

| | card-answerable tasks | body-only tasks |
|---|---:|---:|
| Fraction that correctly triggered `EXPAND` | 0.0% (correctly never needed to) | 97.1% (66 of 68) |

Diagnosing the 5 (of 68) body-only tasks where progressive and full-body disagreed: one is a
genuine miscalibration (the model answered from the card when it should have asked for more, and
was wrong). The other four are full-vs-progressive disagreements on **identical** body content
across two independent, non-deterministic model calls (3 favoring full, 1 favoring progressive) —
sampling noise, not a case the mechanism handled differently. Net: **97% of body-only tasks
correctly triggered the existing "fetch the Revision" path**; the residual ~4-point accuracy gap
to full-body is one real miss plus noise, not systematic failure to recognize insufficiency.
Held consistent across both skill sources — `hard_meridian` 68.0/4.0/64.0, `hard_skillret`
69.8/4.7/65.1 — despite SkillRet cards having no digest field at all (`name`+`description` only),
a strictly thinner card than Meridian's.

## What this does and does not license

**Licensed:** value proposition 1 can add a second measured claim — not just "≤4 cards, fast," but
"agents that see the card first correctly recognize, 97% of the time, when they need the full
`Revision` instead of guessing from the card, and pay for that recognition in exactly the cost the
`SkillSummary`/`Revision` split already implies." That is direct evidence the *existing* SEARCH/USE
split (`docs/API-CONTRACT.md` §5.2-5.3) is the right shape, not an untested assumption underneath
an otherwise-measured latency number.

**Not licensed by this report alone:**
- A single blended "X% cheaper" cost claim. The first, smaller pilot (7 skills, a hand-balanced
  50/50 mix of card-answerable and body-only tasks) reported 43.2% token savings; the 70-skill run,
  whose 61 generated tasks are ~all body-only by construction, reported 9.3%. Neither number is a
  property of the mechanism — both are artifacts of an assumed task mix nobody has measured against
  real usage. The number that *does* replicate across both runs, identically: ~86% token savings
  when the card turns out to be sufficient, ~0-2% when it doesn't (because the agent correctly
  fetches the body either way, at close to the cost of having sent it up front). Real deployment
  savings depend on what fraction of real queries against real skills are card-sufficient — this
  report cannot supply that number; usage telemetry can (`docs/API-CONTRACT.md` §5.5's
  `UsageSkill.context_loaded`/`context_unknown` fields are close to what's needed, if `USE` is
  instrumented to distinguish "answered from card" from "fetched the Revision").
- A claim beyond this specific mechanism (SEARCH returns `SkillSummary` without body, USE/Revision
  fetch supplies it). Two other framings of "abstraction over skills" were tested the same day and
  killed: routing queries through a topic taxonomy before dense search (cosine-centroid and a real
  LLM reading category cards both lose badly to flat dense — `research/pyramid-routing-2026-09-07/`,
  `research/pyramid-routing-llm-2026-09-07/`), and substituting a compressed card for the full body
  during execution (negative replication on a second source — `research/skillbench-communication-
  compression-2026-09-07/`, 0/5 profiles retained). Progressive disclosure is a context-cost
  decision made by the agent that already selected a skill; it is not a retrieval mechanism, and
  should not be marketed as one.
- Single-pass calls, temperature not pinned — a repeat with pinned sampling would tighten the
  ~4-point accuracy gap estimate. Some generated check-phrases are multi-word and matched as one
  normalized substring, which likely understates raw accuracy for all three arms equally (a scoring
  strictness issue, not a between-arm bias). Neither caveat touches the calibration finding (97%
  correct expand-decisions), which is a discrete pass/fail count, not a magnitude estimate.

## Recommended next step, scoped to what this report can support

Do not edit `docs/PRODUCT-FOCUS.md`'s Accepted value-proposition list from this report alone — that
requires the ADR-0029 rule 4 pass. What this report supports today: instrument `USE` to record
whether the calling harness fetched a skill's `Revision` after `SEARCH` returned its `SkillSummary`
in the same session (a `context_loaded`-adjacent signal, `docs/API-CONTRACT.md` §5.5 already has
the shape), so the next revision of this evidence pass reports a *measured* real-world
card-sufficiency rate instead of an assumed one — closing exactly the gap this report's own
limitations section names.
