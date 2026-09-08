---
title: Evidence
description: What we measured, what held up, and what we dropped.
---

We test every mechanism before we ship it and we publish the negatives. Here is what stood and what fell, with the numbers as they are. The newest run is first, and it did not go the way we expected.

## Concatenation did not lose at 1,000 skills, because it never hit its limit

Our first value proposition says that location-scoped tools concatenate every applicable rule file until a hard limit and truncate, while Guidefold ranks and injects at most four cards with the full text loaded on demand. On 8 September we built three real monorepos of 70, 250 and 1,000 skills, put the same 61 questions to a Haiku-class model under three arms, and scored the answers with a strict keyword check written before the run.

| Repository size | Full text of the one right rule | Everything applicable, cut at 32 KiB like Codex | Guidefold cards, full text on request |
|---|---|---|---|
| 70 skills | 57% | 74% | 77% |
| 250 skills | 61% | 79% | 72% |
| 1,000 skills | 43% | 74% | 59% |

The last row includes ten questions that got no answer in any arm because the run outlasted the account's usage window. With those removed the 1,000-skill row reads 51%, 88% and 71%.

The concatenating arm did not degrade as the repository grew. Guidefold did not hold. Two things explain why, and neither is "ranking is worse".

> The answer reached the agent in every one of the 183 cells, in both arms. Under the nearest-wins convention a leaf directory sees only its own rules and its ancestors' rules, and that set stayed under the 32 KiB cut in 178 of 183 cells. A bigger repository was a wider tree, not a heavier path. The run never created the truncation regime it set out to test.

> The strict check rewards quoting the source. Its phrases are copied from the rule bodies, so an arm that holds the full text of every rule and quotes it scores higher than an arm that reads one rule and answers in its own words. That is why the arm given only the right rule, an upper bound on the question, scores below both delivery arms at every size. A lenient rescore that we chose after seeing the data puts all three arms between 90% and 100%, with concatenation still a few points ahead.

What the run does establish: the shipped ranker returned the right rule as the first card in 61 of 61 questions at every size, including 1,000 skills. Retrieval was never the bottleneck. The gap the ranked arm did show came from the extra round trip, in cells where the agent answered from the card or from general knowledge without asking for the body. That is a real cost of progressive disclosure and we are not going to hide it.

The protocol said the claim would be refuted if concatenation matched ranking at 1,000 skills. It did better than match. On this corpus, as built, the value proposition is not supported, and it will stay unsupported until a run places enough rules on the ancestor path that a concatenating tool actually has to drop the answer. That run is designed and not yet done.

Full write-up with every table, the failure anatomy and the second-run design: `docs/reports/market/2026-09-08-delivery-vs-concatenation.md` in the repository; raw artefacts stay local under `research/`.

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

Whether ranked delivery beats concatenation once the applicable set really exceeds a tool's limit. The 8 September run above did not reach that regime; the second design places filler on the ancestor path and pre-registers a scoring rule that does not reward quotation.

Whether a summary lifted to a parent scope helps an agent working in a sibling scope. That is the number the product's main claim rests on, and it needs a run on a real multi-team repository with a held-out sibling. The benchmark design is in `docs/reports/market/2026-09-08-ascent-benchmark-and-positioning.md`. Until it runs, knowledge ascent is a reviewed proposal mechanism, not a measured gain.
