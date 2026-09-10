---
title: Evidence
description: What we measured, what held up, and what we dropped.
---

Here are the measured results and their limits. The 10 September research update found a positive pooled retrieval result on SRA-Bench and checked one missing-proof interaction in Pi. The older negative results remain below.

## A generated skill map improved retrieval

On 10 September, our exploratory R22 experiment evaluated 5,400 annotated queries against 26,262 skills. Qwen2.5-7B wrote summaries, terms and example tasks from samples of skill names and descriptions for 28 groups. A fixed search procedure used that map to choose two additional regions to search, alongside the flat Qwen3-Embedding-0.6B top-50. Query annotations were used for scoring only. The map-only replay fitted its vocabulary and IDF on the map documents.

| Measure | Flat dense search | LLM map + scoped search | Change, percentage points |
|---|---:|---:|---:|
| Recall@10 | 56.69% | 65.22% | +8.53 |
| Complete@4 | 42.31% | 47.19% | +4.87 |
| Hit@1 | 36.22% | 36.22% | 0.00, preserved by design |

Recall@10 is the average fraction of labelled relevant skills among the first ten results. Complete@4 is the fraction of queries whose complete labelled set appears among the first four. These measure retrieval, not coding-task completion.

Paired query bootstrap 95% intervals are +7.46 to +9.60 pp for Recall@10 and +3.83 to +5.91 pp for Complete@4. Compared with a control using the same sampled names and descriptions without LLM-generated text, and the same extra search budget, the full map gained +7.45 pp Recall@10 and +4.19 pp Complete@4. Thus the result is not explained solely by permitting additional searches. Flat search itself uses fewer searches; this is not a latency-matched comparison.

The pooled result hides differences that matter:

| Dataset | Queries | Recall@10 change | Complete@4 change |
|---|---:|---:|---:|
| BigCodeBench | 1,140 | +7.44 pp | +2.02 pp |
| CHAMP | 223 | −8.67 pp | −5.83 pp |
| LogicBench | 760 | +10.92 pp | +8.16 pp |
| MedCalcBench | 1,100 | +1.64 pp | +1.00 pp |
| TheoremQA | 747 | −6.29 pp | −12.18 pp |
| ToolQA | 1,430 | +23.85 pp | +18.95 pp |

The equal-weight mean across datasets was +4.81 pp Recall@10 and +2.02 pp Complete@4. Bootstrap intervals over those six datasets include zero. This supports the mechanism in the pooled benchmark; it does not establish a universal improvement.

A post-hoc audit of the same retained outputs independently reproduced all 21,600 scope selections for the four text-based map arms, without a mismatch. Grouping queries by dataset and exact labelled skill set gave wider 95% intervals: +3.64 to +14.10 pp Recall@10 and +0.83 to +9.39 pp Complete@4 against flat search. This partially accounts for reused answer labels; the cross-dataset uncertainty above still applies.

The map gained a complete top-four set on 551 queries and lost it on 288, a net 263. Of the 551 gains, 200 required a skill outside the original dense top-50. The map therefore recovered missing candidates as well as changing their order. This is descriptive attribution within one run, not a new causal experiment or a task-completion result.

There are 636 distinct skills in the answer labels; the other 25,626 are unlabelled `web` distractors. Every query's labelled answers belong to its dataset's source family. The full map reduced the share of web results in the top ten from 59.86% to 19.64%. The scope-name control reduced it further to 14.26% yet lost 7.29 pp Recall@10, so removing distractors alone is not sufficient. The use of source-family partitions remains a material limitation. Map inputs contained up to 12 cards per leaf (263 total); ten of the 28 leaves were smaller than that cap.

The hierarchy uses seven benchmark corpus prefixes, each split into four embedding clusters. It is not a real monorepo scope tree, and checking generated source IDs does not prove that the generated summaries are semantically correct. The corpus was already exposed; R22 is exploratory, not a new preregistered holdout. The generated-map path remains experimental and is not presented as the default deployed search path.

The retained source verifier recomputed 5,400 flat rankings and 32,400 experimental rankings. A fresh arithmetic audit checked all 37,800 retained rankings and the input/report hashes before these figures were added to the landing page. [Download the compact results, all arms, source hashes and limitations](/evidence/research-2026-09-10.json). The reproducible audit is `tools/research/export_product_evidence.py`; the interpretation is `docs/reports/market/2026-09-10-research-product-update.md`.

## Pi respected ASK when source proof was missing

In one fresh Pi session against the Go service, the harness supplied a Guidefold bootstrap skill and explicit SEARCH/USE/ASK instructions. Pi searched the root and two narrower scopes, then requested two skills by revision. Both USE responses returned `ASK: proof_missing`, with no body. Pi reported no loaded skills and did not claim it had executed the task.

This demonstrates the observed delivery boundary in one instructed session. It does not show correct retrieval: neither selected skill matched the labelled answer set (0 of 2). It also does not measure spontaneous adoption, task success, or user productivity. The next useful product evidence is task execution with both deliverable and withheld skills. The [downloadable record](/evidence/research-2026-09-10.json) includes the Pi run identifier and result hash.

## Real monorepos load more rule text than their tools allow

Before arguing that ranked delivery beats concatenation we had to check that concatenation actually hits a limit anywhere. On 8 September we measured 40 public repositories that publish agent rule files, with no model and no cost: for every directory that holds source code, the characters of `AGENTS.md`, `CLAUDE.md` and similar files a nearest-wins tool would load there, from the root down. The decision rule was written first: over 30 percent of directories above the Windsurf default of 12,000 characters means the regime is common.

| Group | Directories over 12,000 characters | over 32,768 (the Codex default) |
|---|---|---|
| ten repositories with the most rule files, all conventions summed | 54% | 27% |
| the same ten, counting only the one convention a given tool reads | 53% | 27% |
| all 40 measured, one convention | 37% | 9% |

Three repositories (PostHog, Airflow, the OpenAI Agents JS SDK) keep a root file so long that a Codex user loses its tail on most directories today. The distribution is bimodal: a repository either has a 20,000 to 50,000 character root file that every directory inherits, or almost nothing. The candidate list was written from memory of projects that publish rule files, so it overstates the share for a random repository; the full per-repository table with commit ids is in `docs/reports/market/2026-09-08-applicable-set-real-monorepos.md`.

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

One number computed afterwards, from the same trees and without any model call, shows where the difference lives. The run used the Codex default cut of 32 KiB, the most generous of the tools we compare against. Under the Windsurf default of 12,000 characters the answer would have been cut away before the agent saw it in 27 of 61 questions at 250 and 1,000 skills. We chose that limit after seeing the data, so it is a pointer for the next run, not a result.

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

## Earlier topic filtering hurt search

We tried using the hierarchy as a search filter: pick the right category first, then search inside it. Two versions. With cosine similarity to a category centroid, completeness of the top 20 results dropped from 56.5% to 44.4%. With a language model reading real category descriptions, the model beat the centroid by 24.5 points at six categories, then lost that advantage entirely at eighteen. Even a cheating router that knew the right category in advance gained only about five points.

Those filtering variants were dropped. The newer R22 experiment above keeps the global candidate pool and adds scoped candidates using generated task descriptions. That is a different procedure, with a positive pooled result and remaining regressions. The result does not reverse this earlier negative measurement or establish a benefit from tree depth alone.

## Compressing a rule into a card for execution loses the conditions

A hand-made summary kept 18 of 18 policy decisions correct on one source, then 0 of 5 profiles on a second. Summaries lose the "unless" clauses. That is why the card is a pointer to the full text, never a replacement for it.

## Where the numbers come from

Each experiment has its own protocol and evidence boundary. R22 used local model generation followed by offline retrieval over cached embeddings; Pi r3 was one model session; the repository-size survey made no model calls. Exploratory and post-hoc analyses are labelled as such. The fixture is a development set. Raw research artefacts remain local under `research/`; public compact results and hashes are linked above. A verifier checks the recorded calculation, not the validity of a broad product claim.

## What is not yet measured

Whether ranked delivery beats concatenation once the applicable set really exceeds a tool's limit. The 8 September delivery run did not reach that regime; the repository measurement above shows the regime is common, and the second design reproduces the measured per-repository distributions instead of a synthetic tree, with a scoring rule that does not reward quotation.

Whether a summary lifted to a parent scope helps an agent working in a sibling scope. That is the number the product's main claim rests on, and it needs a run on a real multi-team repository with a held-out sibling. The benchmark design is in `docs/reports/market/2026-09-08-ascent-benchmark-and-positioning.md`. Until it runs, knowledge ascent is a reviewed proposal mechanism, not a measured gain.
