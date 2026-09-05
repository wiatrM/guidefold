# What the literature says, and what we measured

**Status:** Living document · first written 2026-09-05
**Companion to:** [ADR-0009](adr/ADR-0009-hybrid-retrieval-client-side.md),
[ADR-0015](adr/ADR-0015-self-hosted-skill-tuned-models.md),
[ADR-0020](adr/ADR-0020-two-tier-dense-retrieval.md),
[`docs/reports/bakeoff/E1.3-embedder-selection.md`](reports/bakeoff/E1.3-embedder-selection.md)

E1.3 concluded that the dense channel does not earn its place and E1.6 that the reranker does not
either. Both are negative results, and a negative result is only trustworthy if it is placed against
what the field already knows. This document does that placement: for each of our decisions, what the
literature reports, what we measured, and whether the two agree.

**Reading note.** Papers are cited from their abstracts and, where marked, their full texts, fetched
2026-09-05. The PDFs and HTML are cached locally under `~/.cache/guidefold/papers/` and are
deliberately **not** committed — they are third-party copyrighted works, and this repository is
Apache-2.0. What is committed is this analysis and the citations needed to find them.

---

## 1. The two papers that are directly on our task

Most retrieval literature is about web pages, passages and QA. Two 2026 papers are about **skill
routing for LLM agents specifically**, which is exactly our problem, and both are the source of
models already in our bake-off.

### SkillRouter — *Skill Routing for LLM Agents at Scale* (arXiv 2603.22455)

Benchmark of ~80 000 candidate skills with heavy overlap. The headline finding is about **what you
index**, not which model you use:

> "hiding the skill body causes a **37–44 percentage point drop** in routing accuracy … the missing
> signal is **body-resident** rather than a simple length artifact: body-distilled descriptions
> recover part of the gap, but remain **7–21 points below** direct all-field routing, while a
> metadata-only encoder trained with the same data remains **14.0 points below** its all-field
> counterpart."

Three consequences worth separating, because they are usually conflated:

1. The body carries most of the routing signal.
2. **Summarising the body into a description does not recover it** — body-distilled metadata still
   trails by 7–21 points. This is a direct argument against the "progressive disclosure" pattern
   (expose name + description, hide the body) that most agent stacks use.
3. You cannot train your way out of it: a metadata-only encoder fine-tuned on the same data is still
   14 points behind.

Their recipe is a **bi-encoder retrieve → cross-encoder rerank** pipeline at 1.2B, reaching 74.0 %
Hit@1, 13× smaller and 5.8× faster than the strongest baseline they tested. Two training choices are
called essential: **hard-negative mining** (10 negatives per query from four sources — 4 semantic
neighbours, 3 BM25 lexical matches, 2 same-category taxonomy distractors, 1 random) and **false-negative
filtering**. And, importantly for us: *"Fine-tuning is more valuable than scale alone"* and
*"Base rerankers help, but tuned reranking helps more."*

### SkillRet — *A Large-Scale Benchmark for Skill Retrieval in LLM Agents* (arXiv 2605.05726)

16 129 public agent skills, 63 259 training samples, 4 392 evaluation queries, a two-level taxonomy
of 6 categories and 18 sub-categories. Its published leaderboard contains the single most relevant
number in this document:

| type | model | params | NDCG@10 |
|---|---|---|---|
| **sparse** | **BM25** (Robertson & Walker 1994) | — | **51.69** |
| encoder | e5-small-v2 | 118M | 44.66 |
| encoder | e5-large-v2 | 335M | 53.41 |

**On a skill-retrieval benchmark 620× larger than our fixture, BM25 beats a 118M dense model
outright and lands within 1.7 points of a 335M one.** Task-specific fine-tuning on their training
split then adds +12.9 NDCG@10 over the strongest prior retriever, which they attribute to fine-tuned
models "better focus[ing] on the small skill-relevant signals within long and noisy queries".

---

## 2. Decision by decision

### 2.1 Dense channel — we ship `w_dense = 0`

**What we measured** (220 golden queries, full GPU bake-off, E1.3): BM25 alone reaches hit@1 0.8736;
BM25 fused with the distilled static table reaches 0.8276. The dense channel makes it **worse**, and
regresses hit@1 by 16.67 pp on `sibling_ambiguity` specifically.

**Does the literature disagree?** No — and this is the part worth being careful about, because it
would be easy to present our result as contrarian when it is mainstream.

- **BEIR** (Thakur et al., NeurIPS 2021) is explicit: *"BM25 is a robust baseline … dense and
  sparse-retrieval models are computationally more efficient but often underperform other
  approaches, highlighting the considerable room for improvement in their generalization
  capabilities."* Our corpus is maximally out-of-distribution for any public encoder.
- **SkillRet's own leaderboard** puts BM25 above a 118M dense encoder **on skill retrieval**.
- **DPR** (Karpukhin et al., 2020) is the paper usually cited for the opposite — dense beating
  BM25 by 9–19 pp top-20. That result is *in-domain*, on open-domain QA, with a retriever trained on
  that distribution. It is not evidence about a 26-skill corpus of internal engineering jargon.

**Additional handicap, specific to us.** We do not ship the teacher; we ship a **static distilled
table** (model2vec-style, PCA to 256 dims, int8). Static mean-pooled vectors are known to be weak on
compositional queries, a limitation traceable to at least Arora et al. (2017, SIF). ADR-0020 wrote
this prediction down *before* the measurement: *"Static mean-pooled vectors are weakest exactly where
the golden set is heaviest (sibling ambiguity, multi-skill), which is why the probation gate above
exists."* The measurement confirmed the prediction rather than surprising us.

**Verdict: our result agrees with the on-task literature.** The one paper that points the other way
(DPR) is measuring a different regime.

### 2.2 Reranker — shadow mode only

**What we measured** (E1.6, 220 queries, GPU, batched): B6 ties B5 on hit@1 (0.8276), is slightly
worse on nDCG@10 and Recall@8, improves `sibling_ambiguity` and collapses `stale_adversarial`.
Mean latency **0.48 s per query** against ADR-0020's 300 ms hook budget.

**Does the literature disagree?** Partly, and the split matters.

- **On cost, no disagreement at all.** BEIR: reranking achieves the best zero-shot performance
  *"however, at high computational costs."* monoBERT (Nogueira & Cho, 2019) established the quality
  gains and the expense together. Our 0.48 s/query is that expense, measured on our hardware. The
  reranker is disqualified on latency before quality is weighed.
- **On quality, our mixed result is consistent once you account for fine-tuning.** SkillRouter states
  plainly that *"base rerankers help, but tuned reranking helps more"* and that *"fine-tuning is more
  valuable than scale alone."* We applied `SkillRouter-Reranker-0.6B` **off the shelf, to a corpus it
  was never tuned on**, with none of the hard-negative mining their recipe calls essential. Their own
  paper predicts that this is the weak configuration.

**Verdict: cost is confirmed by the literature; the disappointing quality is explained by our using
an untuned reranker off-distribution.** That is a fair reading, not an excuse — but it does mean our
result is not evidence that reranking is useless for skill routing, only that *this* reranker,
*unmodified*, on *our* corpus, is not worth 0.48 s.

### 2.3 Abstention — currently non-functional

**What we measured:** `abstention_precision` is undefined across all 220 cases because the router
never abstains. 44 cases (20 % of the golden set) therefore measure nothing.

**Does the literature disagree?** No, and no paper is needed. RRF scores are
`Σ 1/(k + rank)` with k=60; over ranks 1–8 that spans roughly 10 % of its range. A magnitude
threshold cannot discriminate against a near-constant. Cormack et al. (2009) never claimed RRF
scores were calibrated — RRF deliberately **discards magnitudes and uses only ranks**, which is
precisely why it is robust. We asked a rank-fusion score to behave like a confidence, which it is
not. The fix is a different signal (the rank-1/rank-2 margin is the obvious candidate), not a
different threshold.

**Verdict: a mechanical consequence of our own design, not a contradiction of anything.**

### 2.4 Field weights — an open contradiction we are testing

This is the one place where the literature says we are probably **wrong right now**.

Our defaults weight `field.body` at **2 — the lowest of five fields** (name 6, triggers 5,
description 4, digest 3, body 2). SkillRouter measures the body as carrying 37–44 pp of routing
accuracy, and shows that a distilled description does not substitute for it.

If that transfers, our weighting is inverted on the most important field. It may not transfer: their
80K public registry has descriptions written by many hands, while our 26 fixture skills have
hand-written, deliberately discriminative descriptions. A config sweep with a held-out split is
measuring this now, including a **metadata-only arm** (body weight 0) so our number can be compared
directly against their 37–44 pp. **Whichever way it comes out is informative:** a large gap means our
corpus behaves like theirs; a small one is a real finding about hand-curated corpora.

### 2.5 Distractors in the golden set — independently arrived at, then validated

Our golden set labels **distractors**: plausible-but-wrong skills that must not reach the top 4. We
designed that before reading SkillRouter. Their hard-negative recipe is the same idea, more
systematic: 4 semantic neighbours, 3 BM25 lexical matches, 2 same-category taxonomy distractors, 1
random per query, plus false-negative filtering.

**Actionable gap:** our distractors are hand-authored and unevenly distributed — only 1 of the 66
`multi_skill` cases has one at all, which is why `distractor_rate@4` on that stratum is computed over
a single case and swung 0.0 → 1.0 between two arms. Their four-source recipe is the obvious way to
make that metric mean something.

---

## 3. Where we are ahead of, or orthogonal to, the literature

Not everything we do has a paper behind it, and two constraints we work under are barely addressed:

- **Determinism.** No retrieval paper we found treats bit-reproducible ranking as a requirement. Our
  integer-only ranking (ADR-0020) exists because a coding agent must be debuggable, not because
  anyone published it. The nearest relevant knowledge is Goldberg (1991) on floating-point.
- **A 300 ms budget in a fresh process.** The literature optimises throughput on warm servers; we pay
  interpreter start-up on every prompt. That is why the 193 ms → 0.3 ms postings measurement mattered
  more to us than any model choice.
- **Hierarchy as a feature, not a filter.** Scope proximity is a signal our corpus has and public
  benchmarks do not. SkillRet's two-level taxonomy is the closest analogue, used for distractor
  sampling rather than for ranking.

---

## 4. What to read, in order

| Paper | Why it matters here |
|---|---|
| **SkillRet** (arXiv 2605.05726) | On-task benchmark; its leaderboard is our best external evidence that BM25 is strong for skill retrieval |
| **SkillRouter** (arXiv 2603.22455) | The body-signal finding, and the hard-negative recipe our golden set should adopt |
| **BEIR** (arXiv 2104.08663) | The general statement of "BM25 is a robust out-of-domain baseline" |
| **DPR** (arXiv 2004.04906) | The strongest case for dense; read it to see why its regime is not ours |
| **monoBERT** (arXiv 1901.04085) | Cross-encoder reranking: the gains, and the cost |
| **RRF** (Cormack et al., SIGIR 2009) | Four pages; explains why RRF scores are not confidences |
| **BM25 / PRF** (Robertson & Zaragoza, 2009) | Where k1, b and field weighting come from |
| **SIF** (Arora et al., ICLR 2017) | Why static mean-pooled vectors struggle on compositional queries |

---

## 5. Open items this document creates

1. **Test the body weight** against SkillRouter's 37–44 pp, with a metadata-only arm. *(sweep running)*
2. **Adopt the four-source hard-negative recipe** for golden-set distractors, so `distractor_rate@4`
   stops being computed over single cases.
3. **Revisit the reranker only if fine-tuned.** Off-the-shelf is the configuration their paper
   predicts will underperform; a tuned one is a different experiment. Latency still gates it.
4. **Consider SkillRet as a second evaluation corpus.** 16 129 skills with disjoint pools would test
   generalisation far better than a 26-skill fixture, and would make Recall@8 discriminating again.
