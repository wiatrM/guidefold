# SKILLRET-test bake-off: F0 (shipped baseline) and R1 (reference run) — 2026-09-05

Runs F0/R0 and R1 of `docs/reports/bakeoff/DENSE-PROGRAM.md` (v2.1) on **SKILLRET-test**
(`ThakiCloud/SKILLRET`, HuggingFace, pinned revision `a050ad23`): 6,006 skills, 4,392 queries,
7,187 qrels, through the unmodified product path (`policy_filter -> candidates -> score ->
select(admissible=...)`, ADR-0022 — no arm bypasses the filter). Code: `tools/eval/skillret.py`.
Tests: `tests/test_skillret_eval.py`. Raw per-query JSONL (gzip) and summary JSON are committed
under `docs/reports/bakeoff/validation/skillret-{r0,r1,latency}*`.

**This is test-A only.** Test-B (SkillRetBench, HSR@4) is a separate, parallel run; adoption
gates need both. **Nothing here chose a configuration** — this report carves no dev split (the
programme's dev split, 1,000 stratified SKILLRET-*train* queries, was frozen separately in
`skillret-dev-split.json` and is out of scope for this run).

## 0. Corpus and construction

- 6,006 skills / 4,392 queries / 7,187 qrels; taxonomy: 6 majors, 18 subs, 25 nodes incl. `_root`.
- Cases by `k` (gold skills per query): k1=2,143, k2=1,703, k3=546.
- Every card has empty `requires`/`triggers`/`negative_triggers`/`refines` — SKILLRET-test carries
  none of these fields, so the requires-closure step of `select()` is a no-op on this corpus (a
  reported fact, not an omission — see F5 in DENSE-PROGRAM.md §4 for the derivation approach this
  motivates on real skill corpora).
- Two synthetic node settings per query, since the corpus gives no `cwd`: **root** (`_root`, no
  context — all 6,006 skills visible) and **major** (gold[0]'s major, slugified — a coarse
  "somewhere in this platform" signal). **Never the leaf** sub-node, which would leak the answer
  into the scope feature.
- Retrieval order (`Router.score`) and injection order (`Router.select`) are kept as two separate
  lists throughout, per the convention `tools/eval/run_golden.py` already established (and the bug
  it already found once — commit `931055d`, conflating them understated hit@1 by 64 points).
  `hit@1`/`recall@10`/`nDCG@10` come from retrieval order; `all_required@4`/`completeness@4`/
  `distractor_rate@4` come from injection order (post-abstention-gate, post-closure).

## 1. F0 / R0 — the shipped baseline (`w_dense=0`)

`Index.from_cards(cards, nodes, weights={"w_dense": 0})` — every other weight
(`w_scope=200`, `w_ppr=250`, `abstain_threshold=1200`, `ppr_mode=closure`, ...) stays at
`DEFAULT_WEIGHTS`; verified byte-identical to the shipped defaults in
`tests/test_skillret_eval.py::test_build_r0_index_merges_default_weights`.

| setting | n | hit@1 | nDCG@10 (ours) | nDCG@10 (paper-style, binary) | recall@10 | completeness@4 | all_required@4 |
|---|---|---|---|---|---|---|---|
| root  | 4,392 | 0.3825 | 0.3850 | 0.3999 | 0.4700 | 0.3921 | 0.2700 |
| major | 4,392 | 0.3663 | 0.4069 | 0.3957 | 0.4706 | 0.4517 | 0.2862 |

By k (root setting):

| k | n | hit@1 | nDCG@10 (paper-style) | all_required@4 |
|---|---|---|---|---|
| 1 | 2,143 | 0.3584 | 0.4645 | 0.5002 |
| 2 | 1,703 | 0.4110 | 0.3585 | 0.0669 |
| 3 | 546   | 0.3883 | 0.2762 | 0.0000 |

By k (major setting): k1 hit@1=0.4004/nDCG=0.5177/all_required@4=0.5544; k2 hit@1=0.3470/
nDCG=0.3003/all_required@4=0.0399; k3 hit@1=0.2930/nDCG=0.2143/all_required@4=0.0018. Full detail
in `skillret-r0-summary.json`. `distractor_rate@4` is `NaN` on both settings — SKILLRET-test
carries no distractor/negative labels, only graded gold (see §4).

**Paper's published BM25 nDCG@10 = 51.69** (SkillRet v3 leaderboard). Our paper-style nDCG@10 (same
binary-relevance formula, retrieval order, k=10) is 39.99 (root) / 39.57 (major) — roughly 12
points below. This is **not** an apples-to-apples baseline comparison: our BM25F is a five-field
weighted variant (name/description/digest/triggers/body, integer-scaled IDF, accent-folding
tokenizer) built for routing through `policy_filter`/RRF, not the paper's own BM25 configuration
(field construction, k1/b, tokenizer are unstated in the leaderboard entry). The gap is reported,
not explained away, and is not a gate — F0 is the reference the encoder is measured against, not a
reproduction target.

## 2. R1 — reference run (`SKILLRET-Embedding-0.6B`, unfused, tooling defaults)

Per DENSE-PROGRAM.md §6: **R1 is a reference, not a stop test.** It shows what a skill-tuned
encoder does through the product path with `w_dense=1` and no other change — before any dev
tuning, latency ignored. It gates nothing.

Encoding: `tools/bakeoff/encode.py`'s `Encoder` class, unmodified (only its documented
`batch_size` constructor kwarg used, plus outer chunking of the call for OOM safety — skill bodies
run up to 184k chars / near the model's 8192-token cap; a batch of 64 such sequences at the
encoder's own CUDA default OOM'd on a 24GB RTX 4090, fixed by encoding skills at
`batch_size=4`/chunks of 200 while queries kept the encoder's own default `batch_size=64`). All
6,006 skills + 4,392 queries encoded fp16 on GPU, quantised to int8 (`_dense_rank`'s integer
cosine, unchanged): skills 386.8s (64.4 ms/item), queries 32.0s (7.3 ms/item), mean cosine
similarity after quantisation 0.9974 (skills) / 0.9974 (queries) — negligible quantisation loss.
`HF_HUB_OFFLINE=1`, revision `0e10886e80a0aacc9efddc28282a258e2ab7eae1` pinned.

### 2.1 Coverage — reported first, because it bounds everything else

**Coverage** = gold skills that BM25F's top-50 candidate pool misses, which the encoder's top-50
candidate pool contains (both measured from the *same* `Router.candidates()` call, before RRF
fusion or selection — a pure candidate-generation question). This is the single most useful number
R1 produces, because it is a hard ceiling on how much *any* dense signal could add to this
particular product path on this corpus, independent of how fusion is eventually tuned.

| setting | gold qrels | covered by BM25F top-50 | **added by dense top-50** | missed by both |
|---|---|---|---|---|
| root  | 7,187 | 3,969 (55.2%) | **2,849 (39.6%)** | 369 (5.1%) |
| major | 7,187 | 3,763 (52.4%) | **1,638 (22.8%)** | 1,786 (24.9%) |

By k (root setting): k1 added 544/2,143 gold (25.4%), k2 added 1,474/3,406 (43.3%), k3 added
831/1,638 (50.7%). By k (major setting): k1 added 413/2,143 (19.3%), k2 added 818/3,406 (24.0%),
k3 added 407/1,638 (24.8%). Full detail in `skillret-r1-summary.json`.

Two things worth stating plainly:
- **Node scope changes how much headroom dense has.** At `root` (no context, full 6,006-skill
  pool), BM25F's top-50 already misses a lot that a wide, unconstrained lexical ranking would
  eventually surface anyway — dense recovers 39.6% of gold overall. At `major` (a coarser but
  still real candidate-pool restriction), BM25F already covers relatively more of what's left,
  and 24.9% of gold is missed by *both* channels — a ceiling neither channel's top-50 can reach
  without a larger `top_n` or a different candidate strategy.
- **A first version of this coverage calculation was wrong and is documented as a fix, not a
  finding**: `Router.candidates()`'s `bm25_rank`/`dense_rank` fields are populated for the *entire*
  scored set (any nonzero score), not just the top-`top_n` urns that channel actually contributed
  to the returned pool — dense cosine is virtually never exactly zero, so `dense_rank is not
  None` is true for nearly every visible skill regardless of rank. The first pass checked
  `is not None` and measured **zero** added-by-dense coverage everywhere, which a manual
  cross-check (`by_dense` set was byte-identical to `by_bm25` on every sampled query) showed was a
  measurement artifact, not a result. The fix compares the rank *value* against
  `CANDIDATE_TOP_N=50` (matching `candidates()`'s own default). The metrics in §2.2 below
  (`hit@1`, `all_required@4`, the bootstrap CIs) were **unaffected** by this bug — they depend only
  on `Router.score`/`Router.select` output, never on the coverage sets — and are numerically
  identical between the pre-fix and post-fix runs.

### 2.2 Quality metrics

| setting | n | hit@1 | nDCG@10 (ours) | nDCG@10 (paper-style) | recall@10 | completeness@4 | all_required@4 |
|---|---|---|---|---|---|---|---|
| root  | 4,392 | 0.6004 | 0.6048 | 0.6324 | 0.7428 | 0.6093 | 0.4497 |
| major | 4,392 | 0.5685 | 0.6053 | 0.5873 | 0.6724 | 0.6726 | 0.4185 |

By k (root setting): k1 hit@1=0.5492/all_required@4=0.7270; k2 hit@1=0.6359/all_required@4=0.2319;
k3 hit@1=0.6905/all_required@4=0.0403. By k (major setting): k1 hit@1=0.5917/all_required@4=0.7592;
k2 hit@1=0.5473/all_required@4=0.1204; k3 hit@1=0.5440/all_required@4=0.0110. Full detail in
`skillret-r1-summary.json`. `distractor_rate@4` is `NaN` — SKILLRET-test has no distractor labels
(§4).

### 2.3 Paired bootstrap CI vs F0/R0 (1,000 resamples over queries, 95% CI)

| setting | metric | overall Δ (pp) | 95% CI (pp) |
|---|---|---|---|
| root  | all_required@4 | **+17.96** | [16.80, 19.08] |
| root  | hit@1           | **+21.79** | [20.56, 23.11] |
| major | all_required@4 | **+13.23** | [12.23, 14.23] |
| major | hit@1           | **+20.22** | [19.15, 21.43] |

By k, `all_required@4` Δ (pp) [95% CI]: root k1 +22.68 [20.72, 24.36], k2 +16.50 [14.86, 18.20],
k3 +4.03 [2.38, 5.86]; major k1 +20.49 [18.67, 22.21], k2 +8.04 [6.75, 9.40], **k3 +0.92 [0.18,
1.83]**. By k, `hit@1` Δ (pp): root k1 +19.09 [17.41, 20.77], k2 +22.49 [20.38, 24.60], k3 +30.22
[26.19, 34.25]; major k1 +19.13 [17.45, 20.81], k2 +20.02 [18.03, 22.02], k3 +25.09 [21.43, 29.12].

## 3. Gate status (v2 evidence form) — observed, not adopted

Per DENSE-PROGRAM.md §5, a frozen variant is adopted only if it clears every gate on **both**
test-A and test-B. R1 is not a frozen fusion variant (it is the unfused, tooling-default reference
of §6); this section reports where its numbers would sit against each gate on test-A only, as
evidence, not a verdict.

| gate | rule | root | major |
|---|---|---|---|
| bundle completeness | `all_required@4` ≥ F0+2.0pp, CI excl. 0 | **clears at every k** (min +4.03pp, k3) | **clears overall and at k1/k2; k3 (+0.92pp) is significant but below the 2.0pp minimum-benefit bar** |
| harmful exposure | `distractor_rate@4` not worse by >1.0pp | **N/A — NaN, no distractor labels on test-A** | **N/A — same** |
| primary quality | `hit@1`/`nDCG@10` not worse by >1.0pp | clears (both improve substantially) | clears (both improve substantially) |
| cost | warm p95 ≤ tier, whole hook, 6,006-skill index | **not evaluated for R1** (§6: latency ignored for the reference run) | same |

**The cost gate already fails for F0 itself at this scale** — see §4. Any dense arm can only add
latency on top of a baseline that already misses both tiers, so R1's own latency was not separately
measured (consistent with §6: "latency ignored" for the reference run).

**Adoption is decided only after a dev-tuned frozen variant is run once here.** This reference run
does not choose a configuration, does not carve a dev split, and clears no gate on test-B (a
separate, parallel run). None of the above is a stop-test verdict.

## 4. Latency (R4 evidence) — the headline cost figure, at 6,006 skills

Whole `guidefold hook` subprocess, fresh Python process per call (`subprocess.run`, no warm
server), scratch on-disk artifact built from the F0 (`w_dense=0`) index — 6,006 cards, outside any
git repo (`GUIDEFOLD_ROOT`/`GUIDEFOLD_CACHE` env vars, `_git_head_short` returns `"worktree"`), 200
queries from the real query set. Machine: Intel Core i7-10700K @ 3.80GHz, WSL2, glibc 2.39,
Python 3.12.3.

| | value |
|---|---|
| cold start (first call, cold OS page cache) | 584.8 ms |
| warm p50 (1 throwaway warm-up excluded) | 561.5 ms |
| warm p95 | 638.9 ms |
| warm mean / min / max | 564.1 / 467.5 / 862.0 ms |
| **T300 gate (≤300 ms)** | **FAIL** |
| **T500 gate (≤500 ms)** | **FAIL** (p50 alone already exceeds it) |
| artifact size, 6,006 cards | 14.88 MB total: cards.jsonl 4.17 MB, postings.bin 5.03 MB, graph.json 2.43 MB, postings.idx 1.82 MB, terms.bin 1.31 MB, norms.bin 0.12 MB, nodes.json 3.1 KB, manifest.json 1.7 KB (vectors.i8/words.bin/words.idx are 0 bytes — `w_dense=0`, no word table) |

Reference point from DENSE-PROGRAM.md §1: whole-hook warm p50/p95 was 65.7/71.8 ms measured at
**26** skills. Subprocess/interpreter startup alone accounts for only ~14 ms bare, ~30-45 ms with a
`yaml` import (measured directly, isolated from the hook) — the ~500+ ms difference at 6,006
skills is genuine artifact-loading-and-query cost at this corpus scale, not process overhead. This
is the clearest single piece of evidence in this report: **the currently-shipped architecture,
running its own sparse baseline with no dense channel at all, already misses both latency tiers at
6,006 skills** — a scale question the 26-skill reference figure could not have shown.

## 5. Overlap caveat

`SKILLRET-Embedding-0.6B` was trained on SkillRet *train*; SKILLRET-*test* is a disjoint skill/query
pool from the same dataset construction, i.e. the same distribution the encoder was tuned for.
This is the "flattered corpus" the programme names in advance (DENSE-PROGRAM.md §3): R1's numbers
here say what a matched-distribution skill-tuned encoder does, not what an arbitrary encoder does
on an arbitrary monorepo's skills. Test-B (SkillRetBench, a separate, non-overlapping corpus, run
in parallel) is the check on that.

## 6. What this run did not do

- No dev split was carved and none of these results chose a configuration — SKILLRET-test is
  test-only (DENSE-PROGRAM.md §3). The programme's dev split (1,000 stratified SKILLRET-train
  queries) already exists, frozen separately, and is untouched here.
- No fusion tuning: R1 is `w_dense=1` with every other weight at `DEFAULT_WEIGHTS`, exactly like
  F0 differs from it only in that one flag (verified in `tests/test_skillret_eval.py`) plus the
  injected dense vectors.
- `distractor_rate@4` could not be evaluated on test-A at all (`NaN` throughout) — SKILLRET-test's
  qrels are graded gold only, no negative/distractor labels.
- Test-B (SkillRetBench, HSR@4) is out of scope for this report; a parallel run covers it.
