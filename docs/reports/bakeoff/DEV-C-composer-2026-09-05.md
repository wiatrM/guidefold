# C composition on dev — 2026-09-05

**Corpus:** SKILLRET **train** split only (`tools/eval/corpora.py::load_skillret_dev()`) — 10,123
train skills, 1,000 train queries, frozen `skillret-dev-split.json`; k = 1/2/3 (required-skill
count) splits into 328/333/339 queries — the same split F0/F3/D0 use. **Test-A (SKILLRET-test) and
test-B (SkillRetBench) are not touched by this report**: nothing froze (see "Freeze decision"
below), so per `DENSE-PROGRAM.md` §5/§7 and the pre-registration commit (PR #47) the test-once
budget is not spent.

**Pre-registered motivation (`DENSE-PROGRAM.md` v2.4, family C; ADR-0022 §4, ADR-0024 §4):**
`select()` has no composition stage — it takes the literal top-k by score plus a `requires`
closure, and neither test corpus carries `requires` edges. This family asks whether an explicit
composer stage — (a) deterministic: score-plateau bundle detection + coverage-aware term-overlap
fill, in the CLI; (b) model: `claude -p --model haiku`, gated by (a)'s detector, evaluated only in
`tools/eval/` — recovers `all_required@4` completeness on queries the detector flags as multi-skill
bundles, without hurting `hit@1` on the queries it should leave alone.

**Result: no arm is frozen in either family.** All four deterministic configurations and both model
configurations fail the pre-registered qualification rule. Two deterministic arms (`C-det-2`,
`C-det-4`) are **byte-identical to C0** on all 1,000 queries — the bundle detector fires on
essentially every query, but their fallback path reproduces C0's own ranking exactly, so they
measure a delta of precisely zero. The other two (`C-det-1`, `C-det-3`) do change the composed
list, and **regress**: `all_required@4` falls 3.2 pp overall, entirely because coverage-greedy fill
demotes the single best match at k = 1 (−12.5 pp there). Both model arms show a positive point
estimate on completeness but neither excludes zero on the low side of its CI, and the run that
produced these numbers spent real, unusual engineering effort resolving a live infrastructure
reliability problem — see "Model-arm reliability" below. This is a **valid, reportable gate
failure**, not tuned away.

Runner: `tools/eval/dev_composer.py` (`convert` / `bundle-stats` / `det` / `model` / `freeze`
subcommands). Tests: `tests/test_composer_model.py` (25 cases: prompt building, response parsing
incl. hallucinated/oversized/malformed selections, the replay cache incl. failure-is-never-cached,
subprocess invocation incl. timeout/missing-binary). Per-arm per-query output:
`docs/reports/bakeoff/validation/dev-composer-{c0,c-det-1,c-det-2,c-det-3,c-det-4}.jsonl.gz` (full
1,000-query dev split) and `dev-composer-{c0-sub,c-model-1,c-model-2}.jsonl.gz` (150-query
subsample). Aggregated metrics: `dev-composer-det-metrics.json`, `dev-composer-model-metrics.json`.
Freeze decision: `dev-composer-freeze.json`. Every arm's final admitted set goes through the real
`Index.from_cards → Router.policy_filter → candidates → score` path; the deterministic composer is
`Router._select_closure`'s own composed branch (`compose_mode="on"`, unmodified `select()` API),
and the model composer bypasses `select()` entirely (never wired into the CLI — ADR-0024 §4's "two
implementations behind one interface") but replicates its abstain check exactly.

## Arms

| arm | detector τ (score-plateau, pct) | coverage-aware fill | gated by detector |
|---|---|---|---|
| C0 | — (baseline, `compose_mode="off"`) | — | — |
| C-det-1 | 15 | on | — (always composes when flagged) |
| C-det-2 | 15 | off (plain pool order) | — |
| C-det-3 | 30 | on | — |
| C-det-4 | 30 | off (plain pool order) | — |
| C-model-1 | 20 (`Router`'s own default) | n/a — model chooses | **yes**, only on detected bundles |
| C-model-2 | 20 | n/a | **no** — called on every query |

Both model arms share one replay cache keyed by `(query_id, sha256 of the exact candidate list
sent)`, so a query answered once is never re-paid for by the other arm.

## Bundle-detector firing rate — the mechanism, measured exactly

The score-plateau detector (`threshold = top_score * (100 − τ) // 100`; a query is a "bundle" if
≥ 2 of the top-15 admissible candidates score at or above it) **fires on 100.00% of dev queries, at
every k, for all four deterministic τ/coverage combinations**:

| arm | k=1 (n=328) | k=2 (n=333) | k=3 (n=339) | overall (n=1000) |
|---|---:|---:|---:|---:|
| C-det-1 (τ=15) | 1.000 | 1.000 | 1.000 | 1.000 |
| C-det-2 (τ=15) | 1.000 | 1.000 | 1.000 | 1.000 |
| C-det-3 (τ=30) | 1.000 | 1.000 | 1.000 | 1.000 |
| C-det-4 (τ=30) | 1.000 | 1.000 | 1.000 | 1.000 |

This corpus's BM25F score distribution is dense enough near the top that even τ=15% (the tighter
grid point) always finds a second candidate within the plateau — "is this query a bundle" is not a
discriminating question here at either τ; the detector is, in effect, always on. `cannot_fit` also
fires at 93.6–100% (below) but for a **different reason on each pair of arms** — this is the part
worth reading carefully, not summarizing as "always cannot fit":

| arm | cannot_fit rate | identical to C0 (composed list, 1,000 queries) |
|---|---:|---:|
| C-det-1 | 0.936 | 11/1000 |
| C-det-2 | 1.000 | **1000/1000** |
| C-det-3 | 0.976 | 11/1000 |
| C-det-4 | 1.000 | **1000/1000** |

**C-det-2 and C-det-4 (coverage=off) are byte-identical to C0 on every single query.** Their
`cannot_fit=True` is correct and not a bug: the bundle pool genuinely has more plateau members than
fit in the k=4 budget, so the flag fires — but with coverage off, the fill step falls back to
"plain pool order" (top-k by score), which is exactly what `select()` already does. The detector
correctly identifies these as bundles it cannot fully satisfy; it just has nothing better to offer
than the ranking already gives, so the composed output is provably unchanged. This is the
byte-identical fallback guarantee ADR-0024 §4 requires, confirmed empirically rather than assumed.

**C-det-1 and C-det-3 (coverage=on) differ from C0 on 989/1000 queries and regress.**
Coverage-aware greedy fill picks, at each step, the candidate with the largest *uncovered
query-term* gain — a criterion that is not "highest remaining score." At k = 1 (single-required-skill
queries, where the top-scored candidate already answers the whole query) this criterion has no
reason to prefer the top-scored item once its terms are "covered" by an earlier, lower-scored pick,
so it demotes the single correct answer out of the composed list 12.5% of the time it would
otherwise have been in it. This is the −12.5 pp at k=1 in the CI table below; it is coverage-fill's
own logic doing exactly what it is designed to do (maximize term coverage, not score), on a stratum
where that is the wrong objective.

## Composer ceiling — is the required skill anywhere in the top N?

`ceiling@N` = the required-skill set is a subset of the top-N candidates by score, **before** any
k-cap or composition — the best any composer (rule or model) sitting downstream of this ranking
could ever achieve. Computed once, from C0's `ranked` (identical across every arm — composition
never touches retrieval, only injection).

| break (n) | ceiling@4 | ceiling@10 | ceiling@15 | ceiling@50 | *(for comparison)* C0 recall@10 |
|---|---:|---:|---:|---:|---:|
| overall (1000) | 0.2990 | 0.3290 | 0.3460 | 0.4000 | 0.5818 |
| k=1 (328) | 0.8415 | 0.8811 | 0.8963 | 0.9360 | 0.8811 |
| k=2 (333) | 0.0691 | 0.1201 | 0.1471 | 0.2462 | 0.5120 |
| k=3 (339) | 0.0000 | 0.0000 | 0.0088 | 0.0324 | 0.3609 |

`ceiling@4` equals C0's own `all_required@4` at every k (0.8415 / 0.0691 / 0.0000) — expected,
since `select()`'s k=4 admission is exactly "top-4 by score" on this corpus with no composition.
The gap this table makes visible: **at k=3, no composer downstream of this ranking can ever recover
more than 3.24% of queries even given 50 candidates to choose from** — three-required-skill queries
are overwhelmingly a *retrieval* gap (only 36.1% of their required skills are anywhere in the top
10 at all, per `recall@10`), not a composition gap. Composition (this family) can only reorder or
select from what retrieval already surfaced; the fact that `ceiling@50` for k=3 is still 0.0324
means the missing skills for those queries are typically **not in the top 50 either**. This is the
same gap family D (query decomposition, `DEV-D-decomposition-2026-09-05.md`) measured from the
retrieval side and could not close without an unacceptable `hit@1` cost — the two families are
independent, consistent measurements of the same underlying shortfall.

## Quality — per-k, all arms (raw ranking metrics identical by construction; composed metrics are the comparison surface)

`hit1`/`ndcg10`/`recall10` are computed on the raw ranked list (retrieval only) and are, by
construction, byte-identical across every arm in a family — composition never touches ranking, only
what gets injected. `all_required4`/`hit1_injected` are computed on the **composed/selected** list
and are the primary comparison surface.

| arm | break | n | hit1 | ndcg10 | recall10 | **all_required4** | hit1_injected |
|---|---|---:|---:|---:|---:|---:|---:|
| C0 | overall | 1000 | 0.7100 | 0.6101 | 0.5818 | 0.2990 | 0.7100 |
| C0 | k=1 | 328 | 0.7378 | 0.8082 | 0.8811 | 0.8415 | 0.7378 |
| C0 | k=2 | 333 | 0.7027 | 0.5630 | 0.5120 | 0.0691 | 0.7027 |
| C0 | k=3 | 339 | 0.6903 | 0.4647 | 0.3609 | 0.0000 | 0.6903 |
| C-det-1 | overall | 1000 | 0.7100 | 0.6101 | 0.5818 | 0.2670 | 0.6500 |
| C-det-1 | k=1 | 328 | 0.7378 | 0.8082 | 0.8811 | 0.7165 | 0.6524 |
| C-det-1 | k=2 | 333 | 0.7027 | 0.5630 | 0.5120 | 0.0931 | 0.6456 |
| C-det-1 | k=3 | 339 | 0.6903 | 0.4647 | 0.3609 | 0.0029 | 0.6519 |
| C-det-2 | overall | 1000 | 0.7100 | 0.6101 | 0.5818 | 0.2990 | 0.7100 |
| C-det-2 | k=1..3 | — | *(identical to C0 at every break — byte-identical composed list)* |
| C-det-3 | *(identical to C-det-1 at every break)* |
| C-det-4 | *(identical to C0 at every break — byte-identical composed list)* |
| C0-sub *(150-q subsample)* | overall | 150 | 0.7133 | 0.5923 | 0.5900 | 0.2800 | 0.7133 |
| C0-sub | k=1 | 49 | 0.7143 | 0.7968 | 0.8980 | 0.8163 | 0.7143 |
| C0-sub | k=2 | 50 | 0.7800 | 0.5453 | 0.5100 | 0.0400 | 0.7800 |
| C0-sub | k=3 | 51 | 0.6471 | 0.4420 | 0.3725 | 0.0000 | 0.6471 |
| C-model-1 | overall | 150 | 0.7133 | 0.5923 | 0.5900 | 0.3067 | 0.6800 |
| C-model-1 | k=1 | 49 | 0.7143 | 0.7968 | 0.8980 | 0.7755 | 0.6939 |
| C-model-1 | k=2 | 50 | 0.7800 | 0.5453 | 0.5100 | 0.1400 | 0.7600 |
| C-model-1 | k=3 | 51 | 0.6471 | 0.4420 | 0.3725 | 0.0196 | 0.5882 |
| C-model-2 | overall | 150 | 0.7133 | 0.5923 | 0.5900 | 0.3200 | 0.7133 |
| C-model-2 | k=1 | 49 | 0.7143 | 0.7968 | 0.8980 | 0.8163 | 0.7347 |
| C-model-2 | k=2 | 50 | 0.7800 | 0.5453 | 0.5100 | 0.1400 | 0.8000 |
| C-model-2 | k=3 | 51 | 0.6471 | 0.4420 | 0.3725 | 0.0196 | 0.6078 |

## Paired bootstrap deltas vs C0 (1,000 resamples, 95% percentile CI, seed 0)

Primary metric bold; guard metric marked **[guard]**. Model-arm CIs use `C0-sub` (C0 restricted to
the same 150-query subsample) as the paired baseline.

| arm | break | **all_required@4** Δ (95% CI) | **[guard]** hit@1_injected Δ (95% CI) |
|---|---|---|---|
| C-det-1 | overall | **−3.20 pp** [−5.10, −1.40] | **−6.00 pp** [−8.60, −3.60] |
| C-det-1 | k=1 | **−12.50 pp** [−16.77, −7.93] | −8.54 pp [−12.80, −4.57] |
| C-det-1 | k=2 | +2.40 pp [−0.30, +5.11] | −5.71 pp [−9.61, −1.80] |
| C-det-1 | k=3 | +0.29 pp [0.00, +0.88] | −3.83 pp [−7.96, +0.59] |
| C-det-2 | overall | 0.00 pp [0.00, 0.00] | 0.00 pp [0.00, 0.00] |
| C-det-3 | *(identical to C-det-1 at every break — same τ/coverage=on regression)* |
| C-det-4 | overall | 0.00 pp [0.00, 0.00] | 0.00 pp [0.00, 0.00] |
| C-model-1 | overall | +2.67 pp [−1.33, +6.67] | −3.33 pp [−11.33, +4.67] |
| C-model-1 | k=1 | −4.08 pp [−14.29, +6.12] | −2.04 pp [−18.37, +12.24] |
| C-model-1 | k=2 | **+10.00 pp** [+2.00, +18.00] | −2.00 pp [−16.00, +12.00] |
| C-model-1 | k=3 | +1.96 pp [0.00, +5.88] | −5.88 pp [−17.65, +7.84] |
| C-model-2 | overall | +4.00 pp [0.00, +8.00] | 0.00 pp [−7.33, +7.33] |
| C-model-2 | k=1 | 0.00 pp [−8.16, +8.16] | +2.04 pp [−12.24, +16.33] |
| C-model-2 | k=2 | **+10.00 pp** [+2.00, +18.00] | +2.00 pp [−12.00, +16.00] |
| C-model-2 | k=3 | +1.96 pp [0.00, +5.88] | −3.92 pp [−15.69, +9.80] |

## Freeze decision

Pre-registered rule (`tools/eval/dev_composer.py` module docstring, committed before this
script's first `run`): within each family independently, a configuration **qualifies** iff (a) its
paired-bootstrap 95% CI on Δ`all_required@4` excludes zero on the low side (`ci_low > 0`), **AND**
(b) its Δ`hit@1` on the injected list is not worse than −1.0 pp (`mean_delta >= −0.01`). Among
qualifiers, freeze the one with the highest point-estimate Δ`all_required@4`; ties broken by
(lower `cannot_fit` rate, then lexicographic arm name). If none qualifies, freeze **none** and
report why the closest candidate fell short. `cmd_freeze` applies this mechanically off the JSON
`det`/`model` summaries — it does not re-derive the rule from the numbers.

| arm | passes primary (ci_low > 0) | Δhit1_injected | passes guard (≥ −1.0 pp) | **qualifies** | reason |
|---|---|---:|---|---|---|
| C-det-1 | no (ci_low=−0.0510) | −6.00 pp | no | **no** | CI does not exclude 0; guard also fails |
| C-det-2 | no (ci_low=0.0000) | 0.00 pp | yes | **no** | CI does not exclude 0 (delta is exactly 0) |
| C-det-3 | no (ci_low=−0.0510) | −6.00 pp | no | **no** | CI does not exclude 0; guard also fails |
| C-det-4 | no (ci_low=0.0000) | 0.00 pp | yes | **no** | CI does not exclude 0 (delta is exactly 0) |
| C-model-1 | no (ci_low=−0.0133) | −3.33 pp | no | **no** | CI does not exclude 0; guard also fails |
| C-model-2 | no (ci_low=0.0000) | 0.00 pp | yes | **no** | CI does not exclude 0 (delta touches, does not exceed, 0) |

**No deterministic arm and no model arm is frozen.** In the deterministic family, the only two
arms with any nonzero effect (`C-det-1`/`C-det-3`, coverage=on) move the wrong direction on the
primary metric; the two arms with a zero-or-better guard (`C-det-2`/`C-det-4`, coverage=off) have
no effect at all because their fallback path is provably identical to C0. There is no
τ/coverage point in this 2×2 grid where the detector both changes anything and helps. In the model
family, both arms' point estimates are positive and `C-model-2`'s CI low edge sits exactly at zero
— one point-estimate closer to qualifying than either deterministic arm — but "exactly zero" is not
"excludes zero on the low side" under the pre-registered rule, and the rule is applied mechanically,
not rounded in the arm's favor. This is reported as the closest near-miss in either family, not as
a qualifying result.

## Model-arm reliability — an infrastructure-failure investigation, reported in full

The first complete pass over the 150-query subsample (`--model-limit 130`) measured a 65.3%
(98/150) model-call failure rate even at the (already-doubled) 60 s timeout, dominating both arms'
`cannot_fit_rate`/`abstain_rate` (both ≈0.65) and making that run's quality numbers primarily a
measurement of infrastructure reliability, not composer quality. Root-cause investigation before
accepting or re-running that result found:

- **97% of the failures (95/98) were not timeouts.** They were `claude` exiting with code 1 in a
  mean 3.9 s (not the 60 s cap) with **empty captured stderr** — a distinct failure mode from the
  timeout hypothesis the 30s→60s raise was built on. Only 3/98 were genuine `timeout after 60s`.
- A manual, isolated invocation of the exact same CLI/flags succeeded cleanly (9.3 s, exit 0).
- Six fresh, sequential `composer_model.call_model()` calls (bypassing the harness, run directly)
  all succeeded once ambient system load had dropped (`load average` 6.85 → 3.0–4.6 across this
  session) — none reproduced the fast exit-1 pattern.
- An 8-way *concurrent* stress test reproduced real, slow timeouts (3/8 at the 60 s cap) but, again,
  no fast exit-1 failures — confirming raw concurrency causes timeouts, but does not explain the
  earlier run's dominant failure mode.

No single root cause for the exit-1/empty-stderr pattern was conclusively identified at the process
level (most likely a resource-exhaustion condition specific to the earlier, more heavily loaded
period of this shared machine — competing agent sessions, a local token-compression proxy, browser
processes — that has since eased). Given the replay cache's fix earlier this session (a failed call
is never cached, only genuine responses are — see "Verification" below), the correct and cheapest
response was to **retry**, not to redesign: `tools/eval/dev_composer.py model` was re-invoked
(unchanged 150-query subsample, unchanged code) and foreground-polled to completion. The retry
produced **zero exit-1 failures**; its only errors were genuine 60 s timeouts, at a far lower rate:

| arm | live attempts this run | errors | error type | cache hits reused | cumulative attributed cost |
|---|---:|---:|---|---:|---:|
| C-model-1 | 98 | 15 (15.3%) | 100% `timeout after 60s` | 52 | $2.62 |
| C-model-2 | 15 | 4 (26.7%) | 100% `timeout after 60s` | 135 | $2.88 |

Final cache state: **146/150 subsample queries answered by a genuine model response** (4 residual
timeouts remain unanswered — `injected=[]`, `cannot_fit=True`, `abstained=True` for those, exactly
as a real "no answer" would look, and correctly excluded from `hit1_injected`'s denominator only
where the case's own required-skill set is empty; they otherwise count as misses, which is the
conservative, honest treatment). **True unique dollar cost for the whole family, both arms, shared
cache: $2.88** (146 genuine model calls; failures are never billed or cached). Total wall-clock for
the full retry-to-completion: 75 minutes, run as 8 chunked foreground `Bash` invocations (the
harness's own cache made every chunk resumable; nothing was lost when a chunk hit its time budget).

This also resolves an open question from earlier in this work: `abstain_rate` and `cannot_fit_rate`
had appeared suspiciously identical in the confounded run (both ≈0.65). They are not the same
signal — `compose()`'s failure path sets `cannot_fit=True` **and** an empty selection (hence
`abstained=True`) on any infra failure, a defensible fail-closed default, but one that makes both
flags indistinguishable from a genuine model judgment exactly to the extent the failure rate is
high. At the failure rate observed in the confounded run this made the two metrics look identical;
at this run's much lower failure rate they diverge as expected (C-model-1: `cannot_fit_rate`
0.133 vs `abstain_rate` 0.100; C-model-2: 0.073 vs 0.027) — most `cannot_fit=True` calls now
reflect a genuine model judgment, not a failure. This conflation is a real, minor metric-design
caveat worth carrying forward if this family is ever revisited: a future version should distinguish
"the model said it couldn't fit everything" from "the call failed" in the persisted record, rather
than only in re-derived rates.

**On scope:** `tools/eval/dev_composer.py`'s own module docstring pre-registers the model arms on
a **150-query, k-stratified (seed 1337) subsample**, explicitly "a scope decision, stated here
before any model call is made, not a result-driven one" — the deterministic arms alone are
pre-registered on the full 1,000-query split. This report holds that pre-registered scope. Expanding
the model arms to 1,000 queries after seeing partial 150-query results, as this session was asked
to consider mid-run, would itself be the result-driven scope change the pre-registration exists to
rule out, and was independently infeasible at this run's measured throughput; it was not done.

## R1 re-run and test-once

Both are contingent on a composer being frozen (`DENSE-PROGRAM.md`, "Why C exists": "runs the
frozen composer(s) once on each test corpus, and — dense caches permitting — re-runs the R1 dense
reference... since a composer that cannot see whether a bundle is needed cannot show what dense
candidates add to one either"). **Neither condition is met**: no configuration froze in either
family (above), so test-once and the R1 re-run are both skipped — not run, not attempted, per the
brief's own "if nothing froze, skip test-once" instruction. Independently, `~/.cache/guidefold/`
was checked and holds no dense-encoder cache directory, so the R1 re-run could not have proceeded
even had a composer frozen.

## Verification

`python3 -m py_compile tools/eval/composer_model.py tools/eval/dev_composer.py` — clean.
`tests/test_composer_model.py`: 25/25 passing, including two added this session — a strengthened
cache-hit test that now asserts `cost_usd` is present and correct (closing the gap that let a real
`KeyError: 'cost_usd'` crash through originally), and a new test proving a failed call is never
cached and is retried on the next invocation while a subsequent success is cached (closing the gap
that let a transient infra failure permanently poison the replay cache). Full repo suite after
merging `origin/main` (PRs #48–#58: telemetry client + ledger, family D pre-registration and dev
run, family E pre-registration, Go/ParadeDB service, BM25F default restore, priority plan + agent-
side decomposition rule, system-map/C4 docs): `python3 -m pytest -q` → all green, 2 skipped
(pre-existing, unrelated to this family). One merge conflict in
`skills/guidefold/scripts/guidefold` (this family's `query=a.task` argument to `router.select()`
vs. PR #49's `t_select` telemetry timing line, both touching the same call site) — resolved by
keeping both.

## Deliverables

- Code: `tools/eval/composer_model.py` (model composer — cache-hit `cost_usd` fix, failure-never-
  cached fix, 60s timeout), `tools/eval/dev_composer.py` (dev harness, new this session).
- Tests: `tests/test_composer_model.py` (25 cases).
- Per-arm per-query JSONL (gzip): `docs/reports/bakeoff/validation/dev-composer-{c0,c-det-1,
  c-det-2,c-det-3,c-det-4}.jsonl.gz` (1,000 queries) and `dev-composer-{c0-sub,c-model-1,
  c-model-2}.jsonl.gz` (150-query subsample).
- Aggregated metrics: `dev-composer-det-metrics.json`, `dev-composer-model-metrics.json`.
- Freeze decision: `dev-composer-freeze.json`.
- Replay cache (146 genuine model answers, $2.88 total unique spend):
  `tools/eval/.composer-model-cache/cache.jsonl` (not committed — local, regenerable).
- This report; `DENSE-PROGRAM.md` §7 entry (below).
- PRs: #47 (pre-registration, merged as `43d541d`); this work (code, tests, dev-run results,
  this report) opened as a second PR from `feat/e73-composer-impl`, not merged.
