# E1 config selection: coordinate descent over a held-out split

A configuration-selection experiment over the six router parameters the coordinator's brief
identified as tunable (`RRF_K`, `K1`, `B`, `field.*` weights, `w_scope`, `w_ppr`), plus two open
questions (reverse PPR vs. a decayed `requires` closure; whether the rank-1/rank-2 score margin
is a usable abstention signal). The brief was explicit that with only 220 golden cases, a naive
sweep "will always find an improvement — including on pure noise," so the deliverable is the
*methodology* as much as the numbers: a committed, stratified tune/holdout split; coordinate
descent instead of a Cartesian grid; a per-stratum non-regression check on every candidate; and a
single holdout look at the end that can veto anything found during tuning.

**Headline result: nothing changed the shipped defaults.** The largest, cleanest gain found during
tuning — an all-equal `field.*` weighting — reversed on holdout. `K1=0.9` likewise reversed. `b`,
`w_scope`, `w_ppr`, and `RRF_K` all produced null results on tune itself. The two open questions
each have a clear answer: PPR and the decayed closure are measurement-identical (adopted, as a
zero-risk simplification, not a "did it survive holdout" call), and the margin abstention signal
is real but weak, and does not survive holdout either. This is reported as the complete, honest
result the brief said was welcome, not a partial one.

## Methodology

**Reused, not reimplemented.** Every metric is computed by `tools/eval/metrics.py`
(`evaluate`, `by_category`) — the same module the CI golden-set runner uses. This report adds no
new metric definitions.

**Two orderings, kept separate.** Per `docs/reports/golden/README.md`, `Router.score` (retrieval,
score-descending) feeds hit@1/recall@8/nDCG@10, and `Router.select` (injection, node-depth order)
feeds completeness@4/distractor_rate@4. Every table below reports both, labelled, never merged —
conflating them previously understated hit@1 by 64 points (see that README's history).

**The split.** `tools/eval/split_golden.py` (new) builds a seeded, reproducible 60/40 split,
stratified by `category` so all five strata appear in both halves in proportion. Algorithm: one
`random.Random(seed=20260905)`, categories processed in a fixed order
(`multi_skill, sibling_ambiguity, no_applicable, stale_adversarial, simple`); per category, case
ids are sorted, shuffled in place on the shared RNG, and the first `round(n * 0.6)` become `tune`,
the rest `holdout`. Committed as `docs/reports/tuning/split.json`; `--check` regenerates from the
same seed and diffs against the committed file to prove reproducibility (verified clean).

| category | n | tune | holdout |
|---|---:|---:|---:|
| multi_skill | 66 | 40 | 26 |
| sibling_ambiguity | 66 | 40 | 26 |
| no_applicable | 44 | 26 | 18 |
| stale_adversarial | 22 | 13 | 9 |
| simple | 22 | 13 | 9 |
| **TOTAL** | **220** | **132 (60.0%)** | **88 (40.0%)** |

**The harness.** `tools/eval/sweep.py` (new) evaluates exactly one configuration per invocation —
deliberately not an automated grid search. A configuration is a `weights` dict (merged over
`Index.DEFAULT_WEIGHTS`, the same mechanism `guidefold.yaml`'s `router.weights` already uses) plus
a `cls` dict of `Index` class-attribute overrides (`K1`, `B`, `RRF_K`, `RRF_SCALE` — not exposed as
weights today), applied by monkeypatching for the duration of one build and restored immediately
after. Verified against `tools/eval/run_golden.py`: `sweep.py --split all` with no overrides
exactly reproduces the shipped baseline (hit@1=0.8736 etc. over all 220 cases) before any
overrides were tried.

**Coordinate descent, not a grid.** One parameter swept at a time from the current defaults; a
change is kept as the new working baseline only if it improves `tune` and does not regress any
stratum; then the next parameter is swept holding that baseline fixed. Two passes maximum. A
per-stratum regression is flagged when a higher-is-better metric (hit@1, recall@8, nDCG@10,
completeness@4) drops, or a lower-is-better metric (distractor_rate@4) rises, by more than
`1/n_stratum` — one case-flip's worth of noise for that stratum's size in the split being
evaluated — relative to the immediately preceding baseline.

**Holdout discipline.** `holdout` was not touched until every tune-side decision below was final.
The one exception, done deliberately and reported as such: the combined "winner" was decomposed
into its three components (`K1`, `field.*`, `ppr_mode`) and each was *also* checked individually on
holdout, to attribute *which* part of the reversal came from where — this is diagnosis of a result
already known to have failed, not additional tune-side searching over holdout.

**Configuration count.** 44 distinct `(weights, cls)` builds were evaluated end to end (build →
score → select → metrics) across both passes, both open questions, and the holdout checks. A full
Cartesian product of the candidate table in the brief (4 RRF_K × 4 K1 × 4 B × 5 field arms × 4
w_scope × 4 w_ppr) would have been 25,600 configurations; 44 is smaller by three orders of
magnitude, which is the point — fewer, deliberately chosen configurations is stronger evidence
against overfitting than more, not weaker.

## Pass 1: sweeping from the current defaults

All pass-1 numbers below are on **tune** (n=132) only.

### RRF_K (default 60; candidates 5, 10, 20, 60)

Byte-identical on every metric, every stratum, across all four values. **Not a harness bug** —
verified directly: raw top-candidate scores scale with `RRF_K` exactly as the formula predicts
(roughly an order of magnitude larger at `RRF_K=5` than at `RRF_K=60`), and every candidate's
`dense_rank` is confirmed `None` (dense stays off per the E1.3 bake-off, `w_dense=0`, ADR-0020 —
that decision stays decided and was not revisited here). RRF fuses ranks, not scores; with exactly
one active channel, `RRF_SCALE // (RRF_K + rank)` is a strictly monotonic function of `rank` for
every value of `RRF_K` tested, so the *fused ranking* cannot change no matter what `RRF_K` is —
only its magnitude does, and magnitude alone never decides an ordering here.

**Verdict: REJECT. Keep RRF_K = 60.** A clean, mechanically-explained null result. Reconfirmed in
pass 2 under the updated `K1=0.9, field.*=equal` baseline (see below) — still byte-identical.

### K1 (default 1.2; candidates 0.9, 1.6, 2.0)

| K1 | retrieval ndcg@10 | retrieval completeness@4 | retrieval distr@4 | injection ndcg@10 | injection distr@4 | per-stratum regressions |
|---|---:|---:|---:|---:|---:|---|
| 0.9 | +0.0003 | +0.0095 | −0.0127 | +0.0007 | −0.0253 | none |
| 1.2 (baseline) | — | — | — | — | — | — |
| 1.6 | −0.0015 | −0.0095 | −0.0127 | +0.0000 | −0.0253 | none |
| 2.0 | −0.0011 | −0.0095 | −0.0127 | +0.0005 | −0.0253 | none |

K1=0.9 is the only candidate that improves (or ties) every metric with zero flagged regressions —
provisionally adopted as the pass-1 working baseline.

### b — BM25 length normalization (default 0.75; candidates 0.3, 0.5, 1.0), K1=0.9 held fixed

Under `K1=0.9` with default field weights: b=0.3 and b=0.5 show a negligible retrieval ndcg@10
uptick (+0.0016, well under one case-flip at n=132), b=1.0 is exactly flat. No other metric moves.
**Verdict at this point: no adoptable improvement.**

### field.* weights (default name=6/description=4/digest=3/triggers=5/body=2), K1=0.9 held fixed

A coordinator-supplied research pointer (SkillRouter, arXiv 2603.22455 — unverified by this agent
beyond the citation itself) reports that hiding the skill *body* costs 37–44 points of routing
accuracy on an ~80K-skill benchmark, and that the current defaults put the *lowest* weight on
`field.body`. Four principled arms were tested against the control, per that pointer:

| arm | weights | retrieval hit@1 | retrieval ndcg@10 | retrieval distr@4 | injection hit@1 | injection ndcg@10 | injection distr@4 | regressions |
|---|---|---:|---:|---:|---:|---:|---:|---|
| control | name6/desc4/digest3/trig5/body2 | — | — | — | — | — | — | — |
| body-dominant | body6/name5/trig4/desc3/digest2 | +0.0190 | +0.0156 | +0.0127 | +0.0190 | +0.0197 | −0.0127 | none |
| **body-equal** | **all = 4** | **+0.0286** | **+0.0174** | **+0.0000** | **+0.0190** | **+0.0204** | **−0.0127** | **none** |
| body-only | body6, rest 0 | +0.0190 | +0.0153 | +0.0380 | +0.0190 | +0.0200 | +0.0127 | sibling_ambiguity distr@4 +7.5pp (retrieval), +5.0pp (injection) |
| metadata-only | body0, rest unchanged | −0.0190 | −0.0146 | −0.0633 | −0.0381 | −0.0296 | −0.0633 | sibling_ambiguity ndcg@10 −3.4pp, completeness@4 −7.5pp (retrieval); hit@1 −7.5pp, recall@8 −7.5pp, ndcg@10 −6.9pp, completeness@4 −7.5pp (injection) |

`body-equal` (all fields weighted 4) strictly dominates `body-dominant` on every metric shown and
is the single best-performing candidate found in the entire sweep, with zero flagged regressions —
**provisionally adopted** as the pass-1 field-weight baseline.

**The metadata-only vs. all-field gap, as asked:** on this corpus, dropping the body costs at most
~7.5pp on any one stratum/metric (sibling_ambiguity, both orders) and ~2–6pp overall — roughly
5–10× smaller than SkillRouter's reported 37–44pp. Plausible reading, not proven: this repo's
26-skill fixture has hand-written `name`/`description`/`triggers` fields deliberately made
discriminative for the golden set; a public ~80K-skill registry's metadata was very likely not
curated to the same standard, so its body carries proportionally more of the signal. This is a
genuine difference in how our corpus behaves, not a refutation of the cited finding — and
`body-only`'s flagged regression is exactly on the stratum (sibling_ambiguity, near-duplicate
skills) where body text alone is *most* likely to blur what discriminative names/triggers keep
apart, which is the mechanism the coordinator's caveat predicted.

### w_scope (default 200; candidates 0, 100, 400), K1=0.9 + field.*=4 held fixed

w_scope ∈ {0, 100} is byte-identical to 200. w_scope=400 shows a marginal, mixed-direction wash
(retrieval ndcg@10 +0.0004, injection recall@8 +0.0032/ndcg@10 +0.0023, but injection distr@4
+0.0127 — recall goes up together with distractors, a wash, not an improvement) — well under one
case-flip. **Verdict: REJECT. Keep w_scope = 200.** Null result.

### w_ppr (default 250; candidates 0, 100, 500), K1=0.9 + field.*=4 held fixed

Byte-identical across all four values on every metric. Verified this is not the flag failing to
apply: for a representative multi-hop query, raw PPR mass is real (max mass ≈ 22,070 against
`IDF_SCALE=1,048,576`), so `(w_ppr * mass) // IDF_SCALE` evaluates to roughly 0/2/5/10 raw score
units across the tested range (0/100/250/500) — genuinely different numbers, just three-plus
orders of magnitude smaller than the RRF/scope gaps between adjacently-ranked candidates in this
corpus. **Verdict: REJECT. Keep w_ppr = 250.** A clean, mechanically-explained null result — this
parameter cannot matter at the scale tested, on a 26-skill graph this shallow.

## Pass 2

Two parameters changed in pass 1 (`K1`, `field.*`), so the null-result parameters were re-checked
under the new working baseline before finalizing.

- **b, re-swept with K1=0.9 + field.*=4 fixed:** the current default (0.75) is now the *best* of
  the four candidates tested — b∈{0.3, 0.5, 1.0} each show small, consistent, un-flagged
  regressions (e.g. injection hit@1 −0.95pp, ndcg@10 −0.95 to −1.09pp, distr@4 +1.27pp) relative to
  0.75. **Verdict unchanged: REJECT, keep b = 0.75** — pass 2 makes this a stronger null, not a
  weaker one.
- **RRF_K, re-swept with K1=0.9 + field.*=4 fixed:** still byte-identical across all four values,
  as the single-active-channel argument predicts regardless of K1/field weights. **Verdict
  unchanged: REJECT, keep RRF_K = 60.**

No further parameters changed in pass 2, so coordinate descent stopped there (within the two-pass
budget).

## Holdout verification of the tune-side "winner"

The tune-side working baseline after two passes was **K1=0.9, field.\*=4 (all equal)**. Checked
once against `holdout` (n=88), against the current shipped defaults:

| | retrieval hit@1 | retrieval ndcg@10 | retrieval distr@4 | injection hit@1 | injection ndcg@10 | injection distr@4 |
|---|---:|---:|---:|---:|---:|---:|
| tune (n=132) | +0.0286 | +0.0174 | +0.0000 | +0.0190 | +0.0204 | −0.0127 |
| **holdout (n=88)** | **−0.0145** | **−0.0024** | **+0.0370** | **−0.0145** | **−0.0007** | **+0.0370** |

**The gain does not survive holdout — it reverses.** No individual per-stratum delta on holdout
crosses the 1/n regression-flagging tolerance (the largest single-stratum move is exactly one
case-flip), which is itself the point: a per-stratum gate calibrated to absorb single-case noise
cannot, by design, catch a result that is *entirely* single-case noise stacked across strata.

**Per the brief's rule 3: this is reported as not surviving, and is NOT adopted.**

### Attribution: which change actually drove the reversal

Each component was checked individually on holdout to see where the reversal came from:

| component (holdout) | retrieval hit@1 Δ | injection hit@1 Δ | which stratum moved |
|---|---:|---:|---|
| K1=0.9 alone | +0.0000 | −0.0145 | multi_skill: injection hit@1 0.346→0.308 (one case, n=26) |
| field.\*=equal alone | −0.0145 | −0.0145 | multi_skill: same one-case flip as K1 above, on **both** orders |
| ppr_mode=closure alone | +0.0000 | +0.0000 | none — exact tie, every metric |

A striking detail: the tune-side gain was concentrated entirely in **sibling_ambiguity** (retrieval
hit@1 0.850→0.925, +7.5pp; injection hit@1 0.350→0.400, +5pp — a ~3-case shift out of 40 tune
cases). On holdout, sibling_ambiguity's numbers are **exactly unchanged** by the field-weight
change (0.846→0.846 retrieval hit@1, identical ndcg@10, identical injection numbers) — the pattern
that worked on the 40 tune-side sibling_ambiguity cases produced literally nothing on the 26
different sibling_ambiguity cases in holdout. The holdout-side loss instead appears in
**multi_skill**, a stratum that showed *zero* movement anywhere in tune. This is close to textbook
overfitting on a small stratified sample: gains and losses across the split are uncorrelated,
because the tune-side "signal" was mostly a handful of individual cases moving, not a real,
transferable property of the weighting.

**Verdicts, final:**

| parameter | tune result | holdout result | adopted? |
|---|---|---|---|
| RRF_K | null (mechanistic) | not applicable (null on tune) | **No — keep 60** |
| K1 | small gain (+K1=0.9) | reverses | **No — keep 1.2** |
| b | null | not applicable (null on tune) | **No — keep 0.75** |
| field.* | largest gain (all=4) | reverses | **No — keep name6/desc4/digest3/trig5/body2** |
| w_scope | null | not applicable (null on tune) | **No — keep 200** |
| w_ppr | null (mechanistic) | not applicable (null on tune) | **No — keep 250** |

**No routing-weight default changes.** Every candidate that showed movement on tune failed to
survive an independent look at held-out cases. This is reported as the complete, welcome result
the brief anticipated — "defaults win, change nothing" — not a partial finding.

## Open question 1: reverse PPR vs. a decayed `requires` closure

`_decayed_closure` was implemented behind `weights["ppr_mode"]` (`"pagerank"` = existing
`_reverse_ppr`, `"closure"` = new: mass halves per `requires`-hop, capped at depth 2, no
power-iteration, no out-degree normalisation — exactly hand-verifiable, see
`test_decayed_closure_matches_the_documented_per_hop_fraction`).

Measured against each other, holding the (rejected, but harmless-to-use-for-this-comparison)
K1=0.9 + field.*=4 configuration fixed: **byte-identical on every metric, both orders, on tune AND
independently on holdout.** Regenerating `docs/reports/golden/baseline.json` after flipping the
shipped default (below) over the **full 220-case** golden set changed exactly one field — the
recorded git SHA — every metric value was identical to the previous baseline. This is not
"indistinguishable within tolerance"; it is an exact tie on all 220 golden cases.

**Mechanism:** `w_ppr`'s own sweep (above) already showed that PPR's contribution to the final
score is 3+ orders of magnitude smaller than the RRF/scope gaps between candidates on this
26-skill graph (out-degree ≈ 0.6, few `refines`/`replaces` edges — ADR-0020's own description of
this graph). Whichever algorithm computes that already-negligible quantity cannot show up in the
outcome.

**Adopted: `ppr_mode` default flipped from `"pagerank"` to `"closure"`.** This is not a "did it
survive holdout" call in the improvement sense — there is no measured gain either way — it is a
zero-risk simplification, confirmed identical on 100% of the golden set across both splits: the
closure implementation is exactly hand-computable (a fixed fraction per hop) where the
power-iteration PageRank is not. `_reverse_ppr` stays in the code, selectable via
`weights: {ppr_mode: pagerank}`, since the equivalence was demonstrated specifically on a shallow,
sparse graph — ADR-0020 updated with this finding and the caveat that it should be re-measured if
a monorepo's `requires` graph grows deep or dense enough for out-degree normalisation to matter.

## Open question 2: is the rank-1/rank-2 margin a usable abstention signal

The magnitude-based gate (`abstain_mode="magnitude"`, the shipped default) is confirmed fully
non-functional on both splits: `coverage=1.0` (never abstains), `abstention_precision` undefined
(`nan`, no true or false abstentions to divide by), `abstention_recall=0.0` — exactly the failure
`docs/reports/golden/README.md` already documented.

`abstain_mode="margin"` (rank1-minus-rank2 raw score gap) was swept at five thresholds on tune
(K1=0.9 + field.\*=4 fixed, `w_ppr` contribution present but negligible per above):

| threshold | precision | recall | coverage | injection hit@1 (answered cases) |
|---:|---:|---:|---:|---:|
| 150 | 0.500 | 0.222 | 0.943 | 0.293 |
| 200 | 0.474 | 0.333 | 0.905 | 0.284 |
| **250** | **0.545** | **0.444** | **0.905** | 0.284 |
| 300 | 0.322 | 0.704 | 0.619 | 0.277 |
| 350 | 0.333 | 0.741 | 0.619 | 0.277 |

**This directly answers the question asked: yes, the margin signal makes the 44 `no_applicable`
cases measurable** — precision and recall are real, non-degenerate numbers at every threshold,
where magnitude-mode gives `nan`/`0.0`. Threshold 250 gives the best tune-side balance (dominates
150 and 200 on both precision and recall at the same coverage).

It is, however, a **weak** signal: the underlying score-margin distributions overlap heavily
across categories (no_applicable's tune-side p25 ≈ 175 vs. ~274–283 for the other four categories,
but all five categories' maxima cluster near 400–430) — there is no clean separation, only a mild
leftward shift for genuinely-unanswerable queries.

**Checked on holdout, threshold=250:** precision collapses to 0.222 (from 0.545), recall to 0.105
(from 0.444) — a reversal at least as sharp as the field-weight one above. Turning margin
abstention on also costs injection hit@1 among still-answered cases on *both* splits (tune:
0.324→0.284; holdout: 0.275→0.242) — a real, additional cost, not just a wash.

**Verdict: NOT adopted as the default.** The signal is genuinely better than the status quo on the
narrow question asked (measurable vs. undefined), but its quality is weak and does not survive
holdout at anything like the level needed to justify changing when the router answers at all.
`abstain_mode="margin"` ships as an available, tested, opt-in mode (`test_margin_mode_*` in
`tests/test_router_select.py`) for future refinement — e.g. combining it with magnitude, or
recalibrating once the golden set has more `no_applicable` examples — not as a shipped default.
`abstain_mode` stays `"magnitude"` by default (`test_magnitude_mode_is_still_the_default` pins
this).

## What actually shipped

1. `Index.DEFAULT_WEIGHTS["ppr_mode"]`: `"pagerank"` → **`"closure"`** — the only default value
   changed by this report, on the strength of an exact tie across all 220 golden cases on both
   the tune and holdout halves (see above).
2. New flag infrastructure, both defaulting to prior behaviour except the one flip above:
   `Router._decayed_closure` / `weights["ppr_mode"]` (`"pagerank"` | `"closure"`),
   `Router._top_margin` / `weights["abstain_mode"]` (`"magnitude"` | `"margin"`,
   `weights["abstain_margin_threshold"]`). Neither `abstain_mode` nor any routing weight besides
   `ppr_mode` changed from its previous default.
3. `docs/reports/golden/baseline.json` regenerated via `run_golden.py --update-baseline` after the
   `ppr_mode` flip: every metric value is unchanged; only the recorded git SHA differs, confirming
   the flip is a metrics no-op at the full-220-case level, not just in the split-level checks above.
4. `docs/adr/ADR-0020-two-tier-dense-retrieval.md`'s "Rejected alternative worth recording" section
   updated with this report's finding and the `ppr_mode` default decision.
5. New tests: `test_closure_mode_is_now_the_default` pins the flip; the existing
   `test_score_uses_decayed_closure_when_ppr_mode_is_closure` updated to request `"pagerank"` via
   an explicit override (it can no longer assume that is the default). All previously-added
   `ppr_mode`/`abstain_mode` tests from implementing the two flags continue to pass unchanged.
6. Nothing else in `Index.DEFAULT_WEIGHTS` or the `K1`/`B`/`RRF_K`/`RRF_SCALE` class constants
   changed. `RRF_K=60`, `K1=1.2`, `B=0.75`, `field.name=6`/`description=4`/`digest=3`/`triggers=5`/
   `body=2`, `w_scope=200`, `w_ppr=250` are all unchanged from before this report.

## Artifacts

- `docs/reports/tuning/split.json` — the committed, reproducible tune/holdout split.
- `tools/eval/split_golden.py` — builds the split; `--check` verifies reproducibility.
- `tools/eval/sweep.py` — one-configuration-at-a-time evaluation harness used for every number in
  this report.
