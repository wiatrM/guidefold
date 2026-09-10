---
name: guidefold-positioning
description: Use when writing or reviewing any Guidefold marketing copy, landing page, deck, README intro or pitch. Owner-set positioning, 2026-09-09. The problem is organisation-scale skill sprawl; the answer is extraction into a knowledge pyramid plus the search and USE service, harness integration and automatic CI.
---

# Guidefold positioning

Owner decision, 2026-09-09. This is how Guidefold is sold. A reader has five
seconds to learn the pain and what we solve. Ninety-nine percent of the rest of
the text does not matter, and copy that buries this is wrong even when every
sentence in it is true.

## The pain, in the owner's own framing

A large organisation ends up with on the order of **30,000 skills**, spread
across many repositories and a monorepo, sitting in many folders. Every team
writes its own. That produces three problems, and they are the only three the
page has to name:

1. **Duplication.** The same rule, written five times, five ways, in five
   places, drifting apart.
2. **Management.** Nobody owns the whole set. Nobody can see it. Nobody knows
   what an agent will actually read.
3. **Extraction into the organisation's knowledge pyramid.** Knowledge has to be
   lifted from the specific to the general: one service, one component, one
   platform, the whole company. That climb is the product.

## What Guidefold does about it

Guidefold solves and automates that, with three concrete parts. Name them:

- **The search and USE service.** Retrieval picks the few skills that apply to
  the folder and the task; USE checks exact revisions and returns the immutable
  body. Field-aware integer BM25F, scope-constrained, no LLM on the default
  request path.
- **Harness integration.** A hook wires it into the coding tool the team already
  uses, so nothing has to be pasted into a prompt.
- **Automatic CI.** Changes to skills are checked on the way in, so the pyramid
  stays true instead of rotting.

## How to write it

- The hero states the organisation-scale pain and the answer. Not the mechanism,
  not the philosophy, not the file format.
- Say **organisation** early and often. The unit of the problem is an
  organisation, never a prompt and never a file.
- Name the three problems as three problems. Duplication, management,
  extraction.
- Then name the three parts of the answer. Search and USE, harness, CI.
- Plain and warm. "I feel your pain" over vendor voice. Short sentences.
- Never claim a hosted product that is not open, a launch date, a customer, or a
  benchmark number the repository cannot back.

## How extraction actually works (owner clarification, 2026-09-10)

Extraction is not a one-way cage that keeps a team's rule locked to that team.
Where knowledge was written should not be where it stays stuck. A team can
write something that turns out to be useful to the whole organisation, and
Guidefold's job is to let it climb there, deliberately, not silently.

The flow, in order:

1. A team writes its own skill: "this is how we deploy our service."
2. Guidefold finds the part of it that is not specific to that service: "check
   the tests and have a rollback plan before you deploy."
3. It proposes that part as a skill one level up, in the organisation's shared
   library. Server names, local commands and team-specific exceptions stay
   with the team; only the general part moves up.
4. Once reviewed, the shared version serves every other team, and it still
   shows where it came from and what it rests on.

This is usually extraction of the common part, not a relocation of the whole
skill: the local skill keeps its specifics and now layers them on top of the
shared one. Two things must stay distinct and must never be collapsed into
each other: "this works for us" is a good reason to *propose* the knowledge to
the organisation; it is not the same as "everyone must do this," which needs a
review, or a decision from whoever owns that rule, before it goes out.

One line for a deck or a pitch: **Guidefold helps knowledge grow from a single
team to the whole organisation, keeping local exceptions and the ability to
check where a shared rule came from.**

## Layout

The owner rejected a two-column landing layout outright: it made the project
unreadable at a glance. Lead with one column the reader falls down, hero first,
pain second, answer third. Do not put the pain and the answer side by side and
expect the reader to assemble them.
