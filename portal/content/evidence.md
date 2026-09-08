---
title: Evidence
description: What we measured, what held up, and what we dropped.
---

We test every mechanism before we ship it and we publish the negatives. Here is what stood and what fell, with the numbers as they are.

## Cards are enough most of the time, and the agent knows when they are not

We gave an agent 75 questions about 70 real rules (26 from our own fixture, 44 sampled from public skill repositories). For each question it saw either the full rule, only the card, or the card with permission to ask for the full text.

| Arm | Correct on questions the card answers (n=7) | Correct on questions only the full text answers (n=68) |
|---|---|---|
| full text | 100% | 69% |
| card only | 100% | 4% |
| card, ask if needed | 100% | 65% |

The card-only arm collapses where it must. The interesting number is the third arm: on the 68 questions that needed the full text, the agent asked for it 66 times (97%). On the 7 questions the card answered, it never asked. Where the card was enough it used about 86% fewer tokens than sending everything; where it was not, it cost about the same. What that blends to in your repository depends on your questions, which is why the usage numbers exist.

Full write-up: `docs/reports/market/2026-09-07-progressive-disclosure-evidence.md`.

## Routing through a topic tree does not help search

We tried using the hierarchy as a search filter: pick the right category first, then search inside it. Two versions. With cosine similarity to a category centroid, completeness of the top 20 results dropped from 56.5% to 44.4%. With a language model reading real category descriptions, the model beat the centroid by 24.5 points at six categories, then lost that advantage entirely at eighteen. Even a cheating router that knew the right category in advance gained only about five points.

We dropped this. The hierarchy is for delivery and ownership, not for ranking. The service returns family information on every card but it does not touch the order.

## Compressing a rule into a card for execution loses the conditions

A hand-made summary kept 18 of 18 policy decisions correct on one source, then 0 of 5 profiles on a second. Summaries lose the "unless" clauses. That is why the card is a pointer to the full text, never a replacement for it.

## Where the numbers come from

Everything above ran on real model calls, single pass, on fixed protocols written before the run. The fixture corpus is a development set; claims about search quality are made only on labelled public corpora. Research artefacts are kept under `research/` in the repository with their protocols, results and independent recheck scripts.

## What is not yet measured

Whether a summary lifted to a parent scope helps an agent working in a sibling scope. That is the number the product's main claim rests on, and it needs a run on a real multi-team repository with a held-out sibling. The benchmark design is in `docs/reports/market/2026-09-08-ascent-benchmark-and-positioning.md`. Until it runs, knowledge ascent is a reviewed proposal mechanism, not a measured gain.
