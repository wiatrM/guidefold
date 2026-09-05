# D query decomposition on dev — 2026-09-05

**Corpus:** SKILLRET **train** split only (`tools/eval/corpora.py::load_skillret_dev()`) — 10,123
train skills, 1,000 train queries, frozen `skillret-dev-split.json`; k = 1/2/3 (required-skill
count) splits into 328/333/339 queries. **Test-A (SKILLRET-test) and test-B (SkillRetBench) are
not touched anywhere in this report or its code** — this family's dev budget is spent here, per
`DENSE-PROGRAM.md` §5/§7 and the pre-registration commit (PR #51). The 6,006-skill SKILLRET-test
corpus is used **once**, for its `skills` list only (never queries/qrels), purely to measure
in-process latency at that scale — see "Cost" below.

**Pre-registered motivation (`DENSE-PROGRAM.md` v2.5, family D):** D0 (=C0, the shipped product
path unmodified) measures `all_required@4` **0.842 / 0.069 / 0.000** and `recall@10`
**0.881 / 0.512 / 0.361** by k = 1/2/3 on this exact split — three-skill queries almost never get
every required skill into the top 4, and 64% of required skills for k = 3 queries sit outside the
top 10 of a single whole-query retrieval. Family D asks whether splitting a multi-intent query
into ≤ 4 clauses, retrieving per clause, and RRF-merging before the real `select()` call recovers
those skills **without hurting k = 1** (the pre-registered guard: `hit@1` not worse than D0 by more
than 1.0 pp overall and at k = 1).

**Result: no arm is frozen.** Four of five arms clear the primary completeness bar
(`all_required@4` overall ≥ D0 + 2.0 pp, CI excluding 0); every arm fails the `hit@1` guard by a
wide margin (4×–11× the ±1.0 pp tolerance). This is a **valid, reportable gate failure**, not
tuned away — see "Freeze decision" below for why, and "Relation to PR #55" for how this dev-only
finding is consistent with a decision already made elsewhere in the programme.

Runner: `tools/eval/dev_decompose.py` (`convert` / `model-cache` / `latency` / `run`
subcommands — the `run` subcommand is checkpointed and resumable, see "Verification" below).
Tests: `tests/test_dev_decompose.py` (37 cases: clause-splitter unit tests including the one-clause
guard and Unicode punctuation, model-call mocking, RRF/compose arithmetic, retrieval-pipeline
integration). Per-arm per-query output: `docs/reports/bakeoff/validation/dev-decompose-{d0,
d-det-1,d-det-2,d-det-3,d-model-1,d-model-2}.jsonl.gz`. Aggregated metrics:
`dev-decompose-metrics.json`. Model-decomposition replay cache (1,000/1,000 dev queries cached):
`dev-decompose-model-cache.json`. Every arm's final admitted set went through the real
`Index.from_cards → Router.policy_filter → candidates → score → select(admissible=…)` path —
`select()` is never reimplemented; per-clause/whole-query rankings are merged into a single
synthetic `[{"urn", "score"}, …]` list one level **above** `select()` (`compose_priority_order`),
exactly like `Router.score`'s own internal channel fusion, then handed to the unmodified real
`router.select()`.

## Arms

| arm | splitter | per-clause candidate depth | whole-query RRF voter |
|---|---|---|---|
| D0 | none (= C0, shipped product, unmodified) | — | — |
| D-det-1 | deterministic clause splitter | 10 | no |
| D-det-2 | deterministic clause splitter | 20 | no |
| D-det-3 | deterministic clause splitter | 10 | **yes** |
| D-model-1 | `claude -p --model haiku` (replay-cached) | 10 | no |
| D-model-2 | `claude -p --model haiku` (**same cache** as D-model-1) | 20 | no |

The deterministic splitter regex-splits on ASCII `.`/`!`/`?`/`;` **only when followed by
whitespace-or-end-of-string**, non-ASCII sentence/semicolon punctuation (`…。؟！？؛；`)
unconditionally, and the brief's own coordinating-marker list (", and then" / "and then" / ", and"
/ "as well as" / "also" / "plus" / "then", case-insensitive, longest-first) — no heuristics beyond
what the brief specifies. Fragments below 3 content tokens (`gf_tokenize`) are dropped; fewer than
2 surviving fragments means "not decomposed" and the **whole original query** is used, so an
undecomposed query is retrieved byte-identically to D0, never as a subtly trimmed variant. The
model splitter prompts haiku for a numbered clause list, strips numbering/bullets, applies the
same short-fragment/one-clause-guard rules, and is replay-cached by `sha256(query)` so
`D-model-1`/`D-model-2` never re-invoke the model (both configs are looked up from one shared,
fully-populated 1,000-entry cache).

### A bug found and fixed before any measurement: bare periods inside identifiers

An early pass at the ASCII sentence-ender pattern (`[.!?…。؟！？]+`, no lookahead) matched *any*
period regardless of context, corrupting real dev queries — e.g. `docs.json`, `Node.js`,
`krakend.json`, `vite.config.ts`, `mkdocs.yml` were split mid-token. Fixed by requiring
whitespace-or-end-of-string after an ASCII sentence-ender (`[.!?]+(?=\s|$)`); non-ASCII
sentence/semicolon punctuation keeps no lookahead (it essentially never appears inside a code
identifier, and CJK convention often omits trailing whitespace — the Unicode-boundary unit tests
deliberately have no trailing whitespace and still pass). Confirmed on real corpus text after the
fix:

```
>>> split_clauses('... check the current docs.json structure and add the new "..." guide ...')
1 clause — "docs.json" intact
>>> split_clauses('Can you create a ... Dockerfile for our Node.js API that builds the Prisma
    client ... during the build stage, then runs the app as a non-root user ...')
2 clauses, split only at the coordinating "then" — "Node.js" intact in clause 1
>>> split_clauses('Before we push the updated krakend.json to production, can you run a full
    security audit ...')
1 clause — "krakend.json" intact
```

### Decomposition rate is high — a genuine result, not a bug

After the fix, 95.2% of the 1,000 dev queries still get split by the deterministic splitter
(99.2% by the model splitter) into a mean 2.96 / 3.66 clauses. Sampling confirms this is **not**
residual mis-splitting of identifiers — it is the brief's own marker list firing inside long,
paragraph-style enumerations typical of this corpus's queries ("Card, Button, and Select" via
", and"; multi-sentence requests via "."/"then"). This over-decomposition, and its cost, is exactly
what the freeze rule below is designed to catch, so it is reported as a finding, not patched away
by narrowing the marker list past what was pre-registered.

## Cost: decomposition rate, clause count, extra retrievals

| arm | break | n | decomposed | mean n_clauses | mean extra `candidates()`+`score()` calls |
|---|---|---:|---:|---:|---:|
| D-det-1/2/3 | overall | 1000 | 0.952 | 2.962 | 2.914 |
| D-det-1/2/3 | k=1 | 328 | 0.951 | 2.845 | 2.796 |
| D-det-1/2/3 | k=2 | 333 | 0.940 | 2.964 | 2.904 |
| D-det-1/2/3 | k=3 | 339 | 0.965 | 3.074 | 3.038 |
| D-model-1/2 | overall | 1000 | 0.992 | 3.659 | 3.651 |
| D-model-1/2 | k=1 | 328 | 0.982 | 3.637 | 3.619 |
| D-model-1/2 | k=2 | 333 | 0.997 | 3.676 | 3.673 |
| D-model-1/2 | k=3 | 339 | 0.997 | 3.664 | 3.661 |

(Decomposition rate/clause count/extra-calls depend only on the splitter and query text, not on
per-clause depth or the whole-query-RRF toggle, so D-det-1/2/3 share one row-set and D-model-1/2
share another. D-det-3's whole-query voter reuses D0's own already-computed ranking at **zero**
extra `candidates()` cost.)

**In-process latency** (`candidates()+score()`, one call = D0's own cost; a decomposed query pays
this once per clause) — freshly measured this run:

| scale | n | p50 | p95 | mean |
|---|---:|---:|---:|---:|
| fixture (`examples/monorepo`, 26 skills) | 220 | 0.15 ms | 0.24 ms | 0.16 ms |
| SKILLRET-test scale (6,006 skills, timing only — never its queries/qrels) | 200 | 147.00 ms | 209.87 ms | 149.01 ms |

At fixture scale the ~2.9–3.7 extra calls/query cost nothing that matters (+0.7–0.9 ms p95). At
6,006-skill scale it does: the deterministic arms' mean 2.9 extra calls add **≈610 ms** at p95, the
model arms' mean 3.65 extra calls add **≈766 ms** — both far past this programme's 300 ms warm T0
budget for a *single* call, before even counting the model splitter's own ~6–7 s per-call latency
(amortized to zero here only because the replay cache is fully populated; a cold call would dominate
end-to-end latency completely). Cost alone would be a serious adoption obstacle even if the quality
gate had passed.

## Quality — overall and by k

D0 replicates the pre-registered fact exactly (`all_required@4` 0.8415/0.0691/0.0000 at k=1/2/3
vs. the brief's quoted 0.842/0.069/0.000; `recall@10` 0.8811/0.5120/0.3609 vs. 0.881/0.512/0.361 —
matches to rounding).

| arm | break | n | hit@1 | nDCG@10 | recall@10 | all_required@4 |
|---|---|---:|---:|---:|---:|---:|
| D0 | overall | 1000 | 0.7100 | 0.6101 | 0.5818 | 0.2990 |
| D0 | k=1 | 328 | 0.7378 | 0.8082 | 0.8811 | 0.8415 |
| D0 | k=2 | 333 | 0.7027 | 0.5630 | 0.5120 | 0.0691 |
| D0 | k=3 | 339 | 0.6903 | 0.4647 | 0.3609 | 0.0000 |
| D-det-1 | overall | 1000 | 0.6320 | 0.6069 | 0.6270 | 0.3210 |
| D-det-1 | k=1 | 328 | 0.6250 | 0.7509 | 0.8780 | 0.7896 |
| D-det-1 | k=2 | 333 | 0.6366 | 0.5805 | 0.5796 | 0.1562 |
| D-det-1 | k=3 | 339 | 0.6342 | 0.4934 | 0.4307 | 0.0295 |
| D-det-2 | overall | 1000 | 0.6140 | 0.5974 | 0.6317 | 0.3210 |
| D-det-2 | k=1 | 328 | 0.6280 | 0.7519 | 0.8902 | 0.7957 |
| D-det-2 | k=2 | 333 | 0.6216 | 0.5740 | 0.5856 | 0.1502 |
| D-det-2 | k=3 | 339 | 0.5929 | 0.4707 | 0.4267 | 0.0295 |
| D-det-3 | overall | 1000 | 0.6700 | 0.6070 | 0.6040 | 0.3160 |
| D-det-3 | k=1 | 328 | 0.6707 | 0.7797 | 0.8872 | 0.7927 |
| D-det-3 | k=2 | 333 | 0.6667 | 0.5682 | 0.5435 | 0.1441 |
| D-det-3 | k=3 | 339 | 0.6726 | 0.4782 | 0.3894 | 0.0236 |
| D-model-1 | overall | 1000 | 0.6460 | 0.6149 | 0.6415 | 0.3270 |
| D-model-1 | k=1 | 328 | 0.6585 | 0.7596 | 0.8689 | 0.7774 |
| D-model-1 | k=2 | 333 | 0.6456 | 0.5733 | 0.5871 | 0.1742 |
| D-model-1 | k=3 | 339 | 0.6342 | 0.5156 | 0.4749 | 0.0413 |
| D-model-2 | overall | 1000 | 0.6480 | 0.6058 | 0.6293 | 0.3250 |
| D-model-2 | k=1 | 328 | 0.6646 | 0.7709 | 0.8872 | 0.7805 |
| D-model-2 | k=2 | 333 | 0.6396 | 0.5507 | 0.5495 | 0.1652 |
| D-model-2 | k=3 | 339 | 0.6401 | 0.5003 | 0.4582 | 0.0413 |

### Candidate ceiling — is the required skill anywhere in the top N?

`ceiling_N` = required-skill-set is a subset of the top-N candidates (before the k-cap/abstain
gate — the retrieval ceiling, not what `select()` actually admits).

| arm | break | ceiling@4 | ceiling@10 | ceiling@15 | ceiling@50 |
|---|---|---:|---:|---:|---:|
| D0 | overall | 0.2990 | 0.3290 | 0.3460 | 0.4000 |
| D0 | k=1 | 0.8415 | 0.8811 | 0.8963 | 0.9360 |
| D0 | k=2 | 0.0691 | 0.1201 | 0.1471 | 0.2462 |
| D0 | k=3 | 0.0000 | 0.0000 | 0.0088 | 0.0324 |
| D-det-1 | overall | 0.3190 | 0.3780 | 0.3930 | 0.4370 |
| D-det-1 | k=1 | 0.8140 | 0.8780 | 0.8902 | 0.9177 |
| D-det-1 | k=2 | 0.1381 | 0.2252 | 0.2523 | 0.3303 |
| D-det-1 | k=3 | 0.0177 | 0.0442 | 0.0501 | 0.0767 |
| D-det-2 | overall | 0.2990 | 0.3810 | 0.4020 | 0.4620 |
| D-det-2 | k=1 | 0.8018 | 0.8902 | 0.9116 | 0.9299 |
| D-det-2 | k=2 | 0.0961 | 0.2252 | 0.2583 | 0.3754 |
| D-det-2 | k=3 | 0.0118 | 0.0413 | 0.0501 | 0.0944 |
| D-det-3 | overall | 0.3010 | 0.3490 | 0.3720 | 0.4550 |
| D-det-3 | k=1 | 0.8384 | 0.8872 | 0.9055 | 0.9360 |
| D-det-3 | k=2 | 0.0781 | 0.1622 | 0.2012 | 0.3604 |
| D-det-3 | k=3 | 0.0000 | 0.0118 | 0.0236 | 0.0826 |
| D-model-1 | overall | 0.3110 | 0.4010 | 0.4220 | 0.4600 |
| D-model-1 | k=1 | 0.7896 | 0.8689 | 0.8963 | 0.9329 |
| D-model-1 | k=2 | 0.1231 | 0.2643 | 0.2943 | 0.3423 |
| D-model-1 | k=3 | 0.0324 | 0.0826 | 0.0885 | 0.1180 |
| D-model-2 | overall | 0.2830 | 0.3800 | 0.4200 | 0.4830 |
| D-model-2 | k=1 | 0.7957 | 0.8872 | 0.9146 | 0.9421 |
| D-model-2 | k=2 | 0.0511 | 0.1952 | 0.2703 | 0.3874 |
| D-model-2 | k=3 | 0.0147 | 0.0708 | 0.0885 | 0.1327 |

`ceiling@4` (== `all_required4_injected`, since k-cap is 4) drops **below D0** at k=1 for every
decomposed arm — decomposing an already single-intent query pushes its one correct answer *out* of
the top 4 for a meaningful fraction of k=1 queries more often than decomposition recovers anything
there. Every arm gains steadily at k=2/k=3 and at every larger N — the ceiling keeps rising through
N=50, meaning most of the recovered skills for multi-intent queries are still outside a top-10 cut,
consistent with the pre-registered 64%-outside-top-10 motivation.

### Paired bootstrap deltas vs D0 (1,000 resamples, 95% percentile CI)

Primary metric bold; guard metric marked **[guard]**.

| arm | break | **all_required@4** Δ (95% CI) | **[guard]** hit@1 Δ (95% CI) | nDCG@10 Δ (95% CI) | recall@10 Δ (95% CI) |
|---|---|---|---|---|---|
| D-det-1 | overall | **+2.20 pp** [+0.60, +3.80] | **−7.80 pp** [−10.50, −5.20] | −0.33 pp [−1.64, +0.99] | +4.52 pp [+3.18, +5.98] |
| D-det-1 | k=1 | −5.18 pp [−8.54, −1.83] | **−11.28 pp** [−15.24, −7.32] | −5.73 pp [−8.03, −3.40] | −0.30 pp [−3.35, +2.74] |
| D-det-1 | k=2 | +8.71 pp [+5.41, +12.01] | −6.61 pp [−11.11, −1.80] | +1.75 pp [−0.25, +4.00] | +6.76 pp [+4.35, +9.31] |
| D-det-1 | k=3 | +2.95 pp [+1.18, +4.72] | −5.60 pp [−10.62, −0.88] | +2.87 pp [+0.89, +4.93] | +6.98 pp [+5.01, +9.14] |
| D-det-2 | overall | **+2.20 pp** [+0.60, +3.80] | **−9.60 pp** [−12.20, −7.00] | −1.28 pp [−2.56, −0.01] | +4.98 pp [+3.75, +6.35] |
| D-det-2 | k=1 | −4.57 pp [−7.93, −1.22] | **−10.98 pp** [−14.94, −7.01] | −5.63 pp [−8.25, −3.23] | +0.91 pp [−1.52, +3.35] |
| D-det-2 | k=2 | +8.11 pp [+5.11, +11.41] | −8.11 pp [−12.61, −3.60] | +1.10 pp [−0.81, +3.20] | +7.36 pp [+5.11, +9.91] |
| D-det-2 | k=3 | +2.95 pp [+1.18, +4.72] | −9.73 pp [−14.45, −5.01] | +0.60 pp [−1.30, +2.66] | +6.59 pp [+4.62, +8.75] |
| D-det-3 | overall | +1.70 pp [+0.20, +3.30] | **−4.00 pp** [−6.10, −2.10] | −0.31 pp [−1.21, +0.58] | +2.22 pp [+1.28, +3.17] |
| D-det-3 | k=1 | −4.88 pp [−8.23, −1.83] | **−6.71 pp** [−9.76, −3.66] | −2.85 pp [−4.52, −1.19] | +0.61 pp [−1.52, +2.44] |
| D-det-3 | k=2 | +7.51 pp [+4.80, +10.51] | −3.60 pp [−7.51, +0.30] | +0.51 pp [−0.98, +2.16] | +3.15 pp [+1.65, +4.65] |
| D-det-3 | k=3 | +2.36 pp [+0.88, +4.13] | −1.77 pp [−5.01, +1.18] | +1.35 pp [+0.13, +2.54] | +2.85 pp [+1.57, +4.23] |
| D-model-1 | overall | **+2.80 pp** [+0.60, +4.80] | **−6.40 pp** [−9.40, −3.50] | +0.47 pp [−1.26, +2.06] | +5.97 pp [+4.23, +7.70] |
| D-model-1 | k=1 | −6.40 pp [−10.67, −2.44] | **−7.93 pp** [−12.20, −3.35] | −4.86 pp [−7.99, −1.80] | −1.22 pp [−4.27, +1.83] |
| D-model-1 | k=2 | +10.51 pp [+6.91, +14.41] | −5.71 pp [−10.81, −0.60] | +1.03 pp [−1.42, +3.65] | +7.51 pp [+4.80, +10.51] |
| D-model-1 | k=3 | +4.13 pp [+2.06, +6.49] | −5.60 pp [−11.50, +0.00] | +5.09 pp [+2.38, +7.89] | +11.41 pp [+8.85, +14.26] |
| D-model-2 | overall | **+2.60 pp** [+0.50, +4.50] | **−6.20 pp** [−9.10, −3.10] | −0.43 pp [−2.00, +1.29] | +4.75 pp [+3.18, +6.42] |
| D-model-2 | k=1 | −6.10 pp [−10.06, −2.13] | **−7.32 pp** [−11.59, −3.05] | −3.74 pp [−6.62, −0.93] | +0.61 pp [−2.13, +3.35] |
| D-model-2 | k=2 | +9.61 pp [+6.01, +13.21] | −6.31 pp [−11.41, −1.50] | −1.23 pp [−3.76, +1.23] | +3.75 pp [+1.35, +6.46] |
| D-model-2 | k=3 | +4.13 pp [+2.06, +6.49] | −5.01 pp [−10.91, +0.88] | +3.56 pp [+0.67, +6.33] | +9.73 pp [+7.18, +12.59] |

## Freeze decision

Pre-registered rule (`DENSE-PROGRAM.md` v2.5): freeze at most one D-det + one D-model arm, each
requiring `all_required@4` overall ≥ D0 + 2.0 pp with the CI excluding 0, **AND** `hit@1` not worse
than D0 by more than 1.0 pp overall and at k = 1.

| arm | passes primary (≥+2.0pp, CI>0) | hit@1 overall Δ | hit@1 k=1 Δ | passes hit@1 guard | **FREEZES** |
|---|---|---|---|---|---|
| D-det-1 | yes (+2.20 pp) | −7.80 pp | −11.28 pp | **no** | no |
| D-det-2 | yes (+2.20 pp) | −9.60 pp | −10.98 pp | **no** | no |
| D-det-3 | no (+1.70 pp < 2.0 pp) | −4.00 pp | −6.71 pp | **no** | no |
| D-model-1 | yes (+2.80 pp) | −6.40 pp | −7.93 pp | **no** | no |
| D-model-2 | yes (+2.60 pp) | −6.20 pp | −7.32 pp | **no** | no |

**No D-det arm and no D-model arm is frozen.** Four of the five arms clear the completeness bar on
their own terms; every one of the five fails the guard by 4×–11× its ±1.0 pp tolerance, entirely
concentrated at k = 1 (single-required-skill queries): decomposing an already single-intent query
demotes its one correct answer often enough to cost `hit@1` far more than the completeness gained
at k = 2/3 is worth under this programme's pre-registered trade-off. This is the exact failure mode
the brief itself named going in ("decomposing a single-intent query wrongly is the known failure
mode") — it is measured here, not hypothesized. D-det-3's whole-query RRF voter is the
closest-to-passing configuration (smallest hit@1 loss, −4.00/−6.71 pp) but its primary benefit
correspondingly shrinks below the +2.0 pp bar — the voter buys back some k=1 precision by directly
trading away the completeness gain that motivated the family. No amount of additional dev-budget
tuning within the pre-registered arm set closes this gap; per the brief's own instruction, this gate
failure is reported as a valid result, not tuned toward passing.

## Relation to PR #55 (main, merged before this report)

While this dev run was in flight, `d592ddf` (#55, already on `main`) added a four-row MVP §5
priority table naming **family D + "agent-side decomposition"** together, and added to the
bootstrap `SKILL.md`: for multi-step tasks the calling agent itself makes repeated `find()` calls
and composes the bundle, rather than asking the ranker to decompose one query — motivated by the
same E7.3 dev measurement this family's pre-registration also cites (64% of required skills for
k = 3 queries outside a single query's top 10). This report's finding is independent evidence for
that same direction: decomposing *inside* `candidates()`/`select()` does recover completeness at
k = 2/3, but only by systematically damaging k = 1 far past this programme's tolerance, at a cost
(≈610–770 ms extra p95 latency at 6,006 skills, plus 6–7 s/call for any *uncached* model
decomposition) that would already be disqualifying on its own. Nothing here changes or reruns the
already-merged #55 decision; it simply confirms, from the ranker side, why that decision was the
right one to make at the agent/harness layer instead.

## Verification

`python3 -m py_compile tools/eval/dev_decompose.py` — clean. `tests/test_dev_decompose.py`: 37
passed (clause-splitter unit tests incl. the one-clause guard and Unicode punctuation, model-call
mocking — the real `claude` CLI is never invoked in tests — RRF/compose arithmetic, retrieval
integration via a real `cli.Index.from_cards`/`cli.Router`). Full repo suite after merging
`origin/main` (PRs #49–#55): `python3 -m pytest tests/ -q` → all green, 2 skipped (torch/
transformers absent in the default venv, pre-existing and unrelated to this family). The `run`
subcommand is checkpointed per-arm under `docs/reports/bakeoff/validation/dev-decompose-checkpoints/
{d0,d-det-1,d-det-2,d-det-3,d-model-1,d-model-2}.json` (atomic tmp+rename, flushed every 20 cases)
so a kill mid-run loses at most a small in-flight batch; this run took 3 chunked foreground
invocations (`--limit 300`, `--limit 500`, then unlimited to finish the remaining 195 and run the
final metrics/tables/freeze tail), none exceeding the 600 s cap. The on-disk model-decomposition
replay cache (`dev-decompose-model-cache.json`) was separately populated to 1,000/1,000 dev queries
via `model-cache --workers 16` across 5 resumable chunked invocations before this run started, so
`D-model-1`/`D-model-2` made zero live `claude -p` calls during the run itself.

## Deliverables

- Code: `tools/eval/dev_decompose.py`.
- Tests: `tests/test_dev_decompose.py` (37 cases).
- Per-arm per-query JSONL(gzip): `docs/reports/bakeoff/validation/dev-decompose-{d0,d-det-1,
  d-det-2,d-det-3,d-model-1,d-model-2}.jsonl.gz`.
- Aggregated metrics: `docs/reports/bakeoff/validation/dev-decompose-metrics.json`.
- Model-decomposition replay cache: `docs/reports/bakeoff/validation/dev-decompose-model-cache.json`.
- Per-arm checkpoints (resumability infrastructure, not a result artifact):
  `docs/reports/bakeoff/validation/dev-decompose-checkpoints/*.json`.
- This report; `DENSE-PROGRAM.md` §7 entry (below).
