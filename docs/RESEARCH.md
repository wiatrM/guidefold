# What the literature says, and what we measured

**Status:** Living document · 2026-09-05, **revised the same day after peer review**
**Companion to:** [ADR-0020](adr/ADR-0020-two-tier-dense-retrieval.md), [ADR-0021](adr/ADR-0021-index-sharding-and-a-global-word-table.md),
[`E1.3-embedder-selection.md`](reports/bakeoff/E1.3-embedder-selection.md),
[`E1.3-peer-review-2026-09-05.md`](reports/bakeoff/E1.3-peer-review-2026-09-05.md),
[`E1-closure-plan.md`](reports/bakeoff/E1-closure-plan.md)

E1.3 concluded the dense channel does not earn its place and E1.6 that the reranker does not either.
A negative result is only trustworthy once placed against what the field knows. This document does
that placement, per decision. **The first version of this document cherry-picked one table and
over-explained one result; both are corrected below and marked.**

Papers are cached under `~/.cache/guidefold/papers/` and deliberately **not committed** — they are
third-party copyrighted works and this repository is Apache-2.0.

---

## 1. Five papers on our task

| paper | what it is | the one number that matters here |
|---|---|---|
| **SkillRet v3** (arXiv 2605.05726) | 16 129 skills; eval on 6 006 skills / 4 392 queries, disjoint pools | fine-tuned SkillRet-0.6B **81.12** NDCG@10 vs BM25 **51.69** |
| **SkillRouter v5** (arXiv 2603.22455) | ~80K-skill routing benchmark, 75 core queries + 256 supplementary, 4-agent downstream eval | hiding the body costs **37–44 pp** Hit@1 |
| **Graph of Skills v3** (arXiv 2604.05333) | dependency-aware bundle retrieval: hybrid seeding → reverse-aware PPR → budgeted hydration | +25.55 % reward, −56.72 % tokens; ablation: 34.4 full, 29.3 without graph propagation |
| **SkillResolve-Bench** (arXiv 2606.10388) | 661 helpful/risky sibling pairs; the risky sibling shares the capability but points at a stale resource or missing precondition | defines **HSR@K** — harmful sibling rate |
| **BEIR** (arXiv 2104.08663) | zero-shot IR across 18 datasets | *"BM25 is a robust baseline"*; rerankers best *"at high computational costs"* |

### 1.1 SkillRet — the full table, not the convenient half

**Correction.** The first version of this document quoted only the two encoders that BM25 beats.
The same table continues:

| type | model | params | NDCG@10 |
|---|---|---|---|
| sparse | BM25 | — | 51.69 |
| off-the-shelf | e5-small-v2 | 118M | 44.66 |
| off-the-shelf | e5-large-v2 | 335M | 53.41 |
| off-the-shelf | Qwen3-Embedding-0.6B | 0.6B | 61.94 |
| **skill-tuned** | **SkillRouter** | 1.2B | **73.54** |
| **skill-tuned** | **SkillRet-0.6B** | 0.6B | **81.12** |

The honest reading is two-sided. BM25 beats *off-the-shelf small* encoders and stays within 10
points of an off-the-shelf 0.6B one — that part supports our `w_dense = 0`. But a **0.6B model
fine-tuned on skill data beats BM25 by 30 points**, and beats the same-size off-the-shelf model by
19. The lever is task-specific training, not parameter count. We measured `SKILLRET-Embedding-0.6B`
as the best teacher on our fixture (hit@1 0.8678, within 0.6 pp of BM25) — consistent with this
table, and a reason the dense channel is *disabled*, not *dead*.

**The number that should temper everyone's enthusiasm:** on Terminal-Bench, SkillRet's +30 NDCG@10
over BM25 moved agent success from **65.5 % to 65.8 %** and cost from $0.86 to $0.78. A large
retrieval gain bought a tiny execution gain. Ranking metrics are a proxy, and a leaky one.

### 1.2 SkillRouter — body access, with the caveats the review added

37–44 pp is correct for v5 (37.3 / 38.7 / 44.0 in their three settings). It measures **whether the
router can see the body at all**, not what BM25F weight the body should carry. Their "all-field"
input is *budgeted*: body capped at 2 500 chars for the encoder and 2 000 for the reranker. And a
better Hit@1 did not mean better completeness: their compact model's multi-skill FC@10 is **35.3 %**
against 38.2 % for a larger baseline.

### 1.3 Graph of Skills — the paper our E1.5 pipeline already resembles

GoS is, almost verbatim, the E1.5 design: lexical + semantic seeding, **reverse-aware Personalized
PageRank** over typed edges (dependency, workflow, semantic, alternative), then a budgeted bundle.
Their motivation is ours too: *"semantic proximity does not imply executable sufficiency … the top
semantic match is a high-level solver, while the actual solution also requires a lower-level
parser … that is semantically weak but functionally necessary."*

At 1 000 skills with GPT-5.2 Codex their ablation gives reward 34.4 with the full method, **29.3
without graph propagation**, 26.7 without lexical retrieval and reranking together. Two caveats the
review is right to raise: two repetitions, no significance test; and the last ablation removes two
components at once, so it does not isolate the reranker. **At our 26-skill scale, reverse PPR and a
decayed `requires` closure produced byte-identical rankings** on tune, holdout and the full set
(config sweep, PR #19) — so we ship the closure as default, and GoS is the evidence that propagation
starts to matter as the graph grows, not that it matters now.

### 1.4 SkillResolve-Bench — the metric our `stale_adversarial` stratum was missing

Their failure mode is exactly ours: *"a router can find the right capability family yet expose the
wrong same-capability representative"* — a sibling that leads to *"a stale resource, missing
precondition, or wrong procedure"*. They report helpful ranking **together with** HSR@K, the top-K
exposure of the risky sibling. Our `distractor_rate@4` is a coarse cousin; HSR@K on
(helpful, risky-sibling) pairs is the sharper instrument, and our deprecated `legacy-session-auth`
paired with `postgres-auth` is one such pair already in the fixture.

---

## 2. Decision by decision

### 2.1 Dense channel — `w_dense = 0`, and the gate that could not be passed

**Measured:** BM25 hit@1 0.8736; BM25 + static student via RRF 0.8276, with a 16.67 pp hit@1
regression on `sibling_ambiguity`.

**Two things the peer review established about the *gate*, both correct:**
- It was **unreachable**. B1's Recall@8 is 0.9799; "+3 pp over the better BM25 arm" would require
  1.0099. Failing an impossible threshold is not evidence against the method.
- The dense arms ran on the **full 26-skill corpus with no policy filter**, while B0 and the shipped
  Router see 8–18 filtered candidates. The arms were not the product.

**Does the literature disagree with `w_dense = 0`?** No — with the correction that it also does not
*support* the stronger claim the first draft made. BEIR and SkillRet's off-the-shelf rows say a
static or untuned dense channel should not be expected to beat BM25 here. SkillRet's tuned rows say
a *tuned* one might. The decision stands as *disabled pending a fair test*, per the closure plan.

### 2.2 Reranker — shadow only; and the regression was mostly ours

**Correction.** The first draft attributed E1.6's mixed quality to "an untuned reranker
off-distribution". The peer review measured something more specific: on the 22 `stale_adversarial`
cases, **B6 promoted the deprecated skill to rank 1 in 10/22 versus B5's 4/22** — because the
reranker's candidate list was never policy-filtered. Applying the same deprecated filter to both:

| variant | Hit@1 (20 answerable) | nDCG@10 |
|---|---|---|
| B5 | 15/20 | 0.8200 |
| B6 as shipped | 10/20 | 0.7419 |
| B5, deprecated filtered | 16/20 | 0.8453 |
| B6, deprecated filtered | 15/20 | 0.8490 |
| B6, filtered, full body | 16/20 | **0.8803** |

The −25 pp collapse becomes −5 pp with a fair filter, and disappears with the full body. The
checkpoint *is* skill-tuned; "off-distribution" remains a hypothesis, while the filter leak is a
measurement. **Cost is unchanged by any of this:** warm median **314 ms / p95 342 ms** for scoring
alone, over the whole 300 ms hook budget. Shadow mode stands — on cost, and now for a better reason.

### 2.3 Abstention — a design fact, restated more carefully

The router never abstains, so 46 cases (44 `no_applicable` + 2 stale) measure nothing. The review
is right that the *narrow range* of RRF scores is not itself the obstacle — any range can be
thresholded. The obstacle is that RRF **discards the original score magnitudes by design**: in a
single list the top-1 always scores exactly 1/61, carrying no information about whether it was a
good match. The config sweep tried a rank-1/rank-2 margin: measurable on tune (precision 0.545),
**collapsed on holdout (0.222)**. Not adopted. A real abstention decision needs raw lexical/dense
features and its own calibration on a dev split — a separate component, not a threshold.

### 2.4 Field weights — the hypothesis was wrong, and two independent sweeps agree

The first draft argued, from SkillRouter's 37–44 pp, that `field.body = 2` (lowest of five) was
inverted. **Two independent measurements say no:**
- Peer-review sweep on B1: body weight 0 → 1 → 2 → 3 → 6 gives Hit@1 78.16 → **87.36** → 85.63 →
  82.76 → 80.46 %. Removing the body costs 9.2 pp (not 37–44); adding weight *hurts*.
- Config sweep (PR #19): all-equal weights won on tune (+2.86 pp) and **reversed completely on
  holdout**, with the tune gain and holdout loss coming from unrelated strata — a textbook
  overfit. Defaults kept.

SkillRouter measured *access* to the body; our body already has full access at weight 2 and sits at
66.9 % of weighted token mass. The literature supplied a hypothesis; the split rejected it. That is
the process working.

---

## 3. Where we are ahead of, or orthogonal to, the literature

- **Determinism.** No retrieval paper we found treats bit-reproducible ranking as a requirement.
  Ours does (ADR-0020), and the peer review found the one place we broke it — `dot/normsq` where
  cosine needs `dot²/normsq` — before it mattered.
- **A 300 ms fresh-process budget.** The literature optimises warm throughput. GoS's 25.55 % reward
  gain is measured with no such constraint.
- **Hierarchy as a ranking feature.** Scope proximity is a signal public benchmarks do not have.
  SkillRet's taxonomy is used for distractor sampling, not ranking.

---

## 4. What the literature asks us to adopt — condensed

| from | adopt | status |
|---|---|---|
| SkillRouter | **FC@K** — full-bundle completeness | added as `all_required@4` |
| SkillResolve | **HSR@K** — harmful sibling exposure on (helpful, risky) pairs | closure plan, P1 |
| SkillRouter | four-source hard negatives (semantic, lexical, taxonomy, random) | closure plan, P1 |
| SkillRet | functional-duplicate audit, corrected qrels, disjoint pools | closure plan, P2 |
| SkillRet | **execution-level eval** — retrieval gains must show up in task success | closure plan, P2 |
| GoS | bundle evaluation, PPR vs closure at matched card budget | done at 26 skills; re-test at pilot scale |
| BEIR / SkillRet | fine-tune before judging dense | closure plan, gated |
