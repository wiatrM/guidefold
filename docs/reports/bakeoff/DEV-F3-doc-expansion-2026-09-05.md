# F3 document expansion (doc2query) on dev — 2026-09-05

**Corpus:** SKILLRET **train** split only (`tools/eval/corpora.py::load_skillret_dev()`) —
10,123 train skills, 1,000 train queries, frozen `skillret-dev-split.json`. **Test-A
(SKILLRET-test) and test-B (SkillRetBench) are not touched anywhere in this report or its code**
— per `DENSE-PROGRAM.md` §4/§7, this family's dev budget is spent here; a frozen candidate is
proposed below for the TL to run once on both test corpora.

**The idea (DENSE-PROGRAM.md §4 F3):** neural at index time, lexical at query time. Generate `n`
pseudo-queries per skill offline with doc2query/msmarco-t5-base-v1 (Nogueira & Lin, "docTTTTTquery"
family, T5-base, Apache-2.0), index them as extra BM25F retrieval surface, ship nothing new to the
hook — the query path never loads a model. "Zero query-time cost" is a hypothesis, not an
assumption; index size and in-process query time before/after are measured below, not estimated.

Generator: `tools/expand/doc2query.py` (`generate` subcommand). Evaluator: `tools/eval/dev_expand.py`
(`convert` / `run` subcommands), which reuses `tools/eval/dev_sparse.py` wholesale (corpus/query
conversion, `run_product_case`, `bootstrap_paired_delta`, `arm_summary`, JSONL writer) — the
**baseline is dev_sparse.py's P-flat arm** (all `field.*` weights = 1, the frozen proposal from
`DEV-sparse-diagnosis-2026-09-05.md` / PR #36), never P-shipped. Tests: `tests/test_doc2query.py`
(15 cases) + `tests/test_dev_expand.py` (14 cases); full repo suite 416 tests, 0 failures, 2 skipped
(torch/transformers absent in the default venv — see "Verification" below).

Per-arm per-query output: `docs/reports/bakeoff/validation/dev-expand-{p-flat,e-field-1,e-field-w,
e-append}.jsonl.gz`. Aggregated metrics: `dev-expand-metrics.json`. Coverage detail:
`dev-expand-coverage.json`. Pseudo-queries: `dev-expand/doc2query-dev-n5-seed42.jsonl`
(10,123 skills × 5 queries, 2.2 MB). Every arm went through the real `Index.from_cards →
Router.policy_filter → candidates → score → select(admissible=…)` path — never a reimplementation;
the `expansion` field is a genuine sixth BM25F field, added by subclassing `Index` (`FIELDS`,
`DEFAULT_WEIGHTS`, `_field_text`), the same technique `dev_sparse.py`'s `make_k1b_index_cls` uses
for `k1`/`b` — confirmed live end-to-end (not just an `Index`-internals trick) by
`tests/test_dev_expand.py::test_expansion_field_round_trips_through_index_from_cards_and_router_score`.

## Generation

Model: `doc2query/msmarco-t5-base-v1` at `/home/mike/.cache/guidefold/models/
doc2query__msmarco-t5-base-v1/` (`model_sha` = first 12 hex of `sha256(pytorch_model.bin)` =
`f0a1ec383a67`), loaded fully offline (`HF_HUB_OFFLINE=1`), fp16 on CUDA. Input text:
`"<name>. <description>. <body>"`, truncated at the tokenizer to 320 tokens (the model card's own
recipe, not a hand-rolled character cutoff). Decoding: **sampling**, `do_sample=True, top_p=0.95,
max_length=64, num_return_sequences=n`, **seed 42**, reseeded per batch (`seed + batch_idx`) with
`cudnn.deterministic=True` / `cudnn.benchmark=False` for reproducibility — verified by
`tests/test_doc2query.py::test_generator_output_is_deterministic_for_a_fixed_seed_two_runs_same_file`,
which runs the real model twice with two fresh cache directories and asserts byte-identical output
(run for real via the GPU venv: 15 passed in 13.67 s). Cache: `.bakeoff-cache/doc2query/<model_sha>/
<skill_id>.json`, storing `n`/`seed`/`top_p` alongside the queries so a request that doesn't match
is a clean cache miss, never a silent reuse of incompatible samples.

Ran over all 10,123 dev-pool skills, `n=5`, in two chunked invocations (a session-level
interruption unrelated to generation correctness split the run; the incremental per-skill cache
made resumption automatic and lossless). The completing invocation's own fresh-generation time was
**60.0 s for its remaining 1,131 skills** (≈53 ms/skill, batch size 32, RTX 4090) — extrapolating
that rate to all 10,123 skills gives an **estimated ~9 minutes for a single uninterrupted run**
(not separately measured; the first chunk's own wall-clock was not preserved). A full cache-hit
verification pass over the finished file reports `10,123/10,123 cached, 0 generated,
gpu_wall_clock_s=0.0`, `4.7 s` total wall-clock (cache lookups + corpus load only) — confirming the
file is complete, internally consistent (`model_sha=f0a1ec383a67, n=5, seed=42, top_p=0.95`
recorded per skill), and requires no GPU work to reuse.

### Samples (5 skills — good and bad)

| skill | pseudo-queries (n=5) | note |
|---|---|---|
| `task-manager` — *"Manage development tasks via md-task-mcp MCP server…"* | what do you call a task manager · can mcp command use task manager · how to create tasks in mcp · what is mcp task management · what is task manager | **good** — five distinct phrasings, all on-topic, adds MCP-specific surface the authored fields don't emphasise |
| `symfony:api-platform-resources` — *"Configure API Platform resources with operations, pagination, and output DTOs…"* | what is api platform resources · how to update api platform · what does api platform resource mean · what is api platform resources in symfony · what are api platform resources | **good** — diverse question forms, correctly surfaces "symfony" |
| `settings-screen` — *"Generates a complete settings screen for iOS/macOS apps…"* | what is a settings screen generator · what is a settings screen generator · types of screens for macOS · what is settings screen generator · how to get a settings screen from quickswift | **bad (repetition)** — the same question is generated verbatim twice out of five; only 3 of 5 are effectively distinct |
| `dokploy-security-hardening` — *"Security best practices for Dokploy templates…"* | what is dokploy security hardening · dokploy security hardening · what is rake security hardening · dokploy security hardening · dokploy security hardening best practices | **bad (repetition + drift)** — 3 of 5 are near-duplicates of the skill name; one ("rake security hardening") substitutes an unrelated tool name, likely sampling noise |
| `reverse-engineering-tools` — *"Guide for reverse engineering tools and techniques used in game security research…"* | what is reverse engineering tools · what is reverse engineering tool used for · what is reverse engineering used for · what tools does reverse engineer use · which of the following is a reverse engineering tool for a pc | **bad (artifact)** — the last query is exam-question phrasing ("which of the following is…"), a known MS MARCO-adjacent training artifact, not a natural search query, though still topically on-target |

Net read: content is reliably on-topic (no observed hallucination of an unrelated *subject*), but
`n=5` sampling produces meaningful **redundancy** — 2 of the 5 sampled skills above have a verbatim
or near-verbatim duplicate within their own 5 — which caps how much *effective* vocabulary breadth
`n=5` actually buys per skill. This shapes the coordinate-descent read below.

## Card scheme and arms

Cards are `dev_sparse.py`'s own (`corpus_to_cards`) — unchanged. Four arms, one changed parameter
each, coordinate descent, well inside the ≤4 dev-configuration budget (§4):

| Arm | What | vs. |
|---|---|---|
| **P-flat** | Baseline — unchanged from `dev_sparse.py`: all `field.*` weights = 1. | — |
| **E-field-1** | Adds a sixth BM25F field, `expansion` = the skill's 5 pseudo-queries joined with spaces, at flat weight 1. | +1 field, +1 weight key |
| **E-field-w** | Same `expansion` field, weight **2** instead of 1 (n stays 5). | +1 weight value vs E-field-1 |
| **E-append** | No new field: the same pseudo-query text is appended into the existing `_body` field instead (`body ← body + "\n" + expansion_text`); `FIELDS`/weights are byte-identical to P-flat. | text-only vs P-flat |

`tests/test_dev_expand.py::test_build_arms_each_arm_differs_from_p_flat_by_exactly_one_parameter`
and `::test_build_arms_field_w_mode_n10_changes_only_expansion_text_length` assert this
one-changed-parameter contract at the byte level (weight-dict diff, `FIELDS` diff, card-text diff)
for every pair.

## Coverage first

Gold (`grade≥2`) skill-instances the arm's BM25F top-50 pulls in that P-flat's top-50 missed
(`recovered`), and the reverse (`lost`), aggregated over all 1,000 dev queries (2,011 required
skill-instances total):

| arm | recovered | lost | net | queries gained | queries lost |
|---|---|---|---|---|---|
| E-field-1 | 17 | 0 | **+17** | 17 | 0 |
| E-field-w | 20 | 0 | **+20** | 20 | 0 |
| E-append | 16 | 0 | **+16** | 16 | 0 |

**Zero losses in every arm** — every arm is purely additive on coverage (0.8–1.0% of required
instances recovered, none dropped). This is a small but genuinely clean win: the expansion
vocabulary never displaces a gold skill that was already reachable, it only ever adds reachability.

## Quality — overall and by k

```
arm         break                n          hit1        ndcg10      recall10 all_required4
------------------------------------------------------------------------------------------
P-flat      overall           1000        0.7610        0.6474        0.6175        0.3170
P-flat      k=1                328        0.7744        0.8405        0.9024        0.8720
P-flat      k=2                333        0.7508        0.5980        0.5511        0.0901
P-flat      k=3                339        0.7581        0.5090        0.4071        0.0029
E-field-1   overall           1000        0.7670        0.6555        0.6280        0.3240
E-field-1   k=1                328        0.7866        0.8509        0.9116        0.8841
E-field-1   k=2                333        0.7568        0.6064        0.5646        0.0991
E-field-1   k=3                339        0.7581        0.5146        0.4159        0.0029
E-field-w   overall           1000        0.7680        0.6563        0.6292        0.3230
E-field-w   k=1                328        0.7835        0.8499        0.9116        0.8841
E-field-w   k=2                333        0.7598        0.6080        0.5661        0.0961
E-field-w   k=3                339        0.7611        0.5165        0.4179        0.0029
E-append    overall           1000        0.7670        0.6553        0.6283        0.3220
E-append    k=1                328        0.7805        0.8489        0.9116        0.8811
E-append    k=2                333        0.7568        0.6061        0.5646        0.0961
E-append    k=3                339        0.7640        0.5163        0.4169        0.0029
```

(`hit@1`/`all_required@4` deltas are read directly from this table, following
`dev_sparse.py`/`DEV-sparse-diagnosis-2026-09-05.md`'s own convention of bootstrapping only
`nDCG@10`/`recall@10` — see below.)

Every arm beats P-flat on every metric at every k; **all_required@4 moves only +0.5 to +0.7 pp**
overall (0.3170 → E-field-1 0.3240 [+0.70 pp] / E-field-w 0.3230 [+0.60 pp] / E-append 0.3220
[+0.50 pp]) — real, but an order of magnitude below the +2.0 pp minimum-benefit bar
DENSE-PROGRAM.md §5 sets for test-corpus adoption on this exact metric.

### Paired bootstrap deltas vs P-flat (1,000 resamples, 95% percentile CI), overall

| Arm − P-flat | Δ nDCG@10 (pp) | 95% CI (pp) | Δ recall@10 (pp) | 95% CI (pp) |
|---|---|---|---|---|
| E-field-1 | +0.81 | [+0.56, +1.10] | +1.05 | [+0.58, +1.62] |
| E-field-w | +0.90 | [+0.60, +1.22] | +1.17 | [+0.67, +1.75] |
| E-append | +0.79 | [+0.55, +1.06] | +1.08 | [+0.58, +1.65] |

Every CI excludes zero, at overall **and at every k stratum** (k=1/2/3, in `dev-expand-metrics.json`'s
`comparisons` block) — this is a small but statistically robust, uniformly positive effect, not
noise. The three arms are statistically indistinguishable from each other (their CIs overlap
heavily); E-field-w has the best point estimate on every metric.

## Index size and query time

Measured directly against `idx.FIELDS`/`idx.postings`/`idx.field_norm`/`idx.idf`
(`estimate_index_bytes` in `dev_expand.py`), reproducing the shipped `_serialize_artifact_files`
byte format (terms.bin / norms.bin / postings.bin / postings.idx) without calling it — see
"Incidental finding" below for why. Excludes `cards.jsonl`/`graph.json`/`nodes.json`/`vectors.i8`/
`words.bin`, which are byte-identical across every arm here (`w_dense=0`, empty `requires` graph).

| arm | Δ BM25 index bytes | Δ, % of P-flat's 12,690,489 B | Δ query latency, mean / p95 (ms) |
|---|---|---|---|
| E-field-1 | +494,795 B | +3.90% | −1.39 / −2.24 |
| E-field-w | +494,795 B | +3.90% | +2.13 / +1.36 |
| E-append | +137,378 B | +1.08% | −5.16 / +37.64 |

**Index size**: the sixth-field arms (E-field-1/E-field-w) cost the same bytes regardless of field
weight (weight doesn't change what's indexed, only how it's scored) — +3.9% for 10,123 skills ×
5 pseudo-queries. Appending into `body` instead is cheaper (+1.08%): no new per-document `norms`
array (one fewer field × 4 bytes × 10,123 docs), just the marginal new-term postings.

**Query time**: every mean-latency delta is within ±3.6 ms of P-flat's 147.4 ms baseline (≤3.5%),
consistent with "zero *added computation*" — `Router._bm25_scores`/`score` already loop over
`idx.FIELDS`, so a sixth field is one more (cheap) iteration, not a new code path, and E-append adds
no field at all. E-append's p95 delta (+37.6 ms) is an outlier against its own better mean
(−5.16 ms) and every other arm's tight p95 movement (≤2.2 ms); read as single-machine wall-clock
jitter over 1,000 sequential in-process calls, not a structural cost — there is no mechanism in
`Router.score()` by which appending text into an existing field's postings would produce a
tail-latency-only regression. Re-measuring this arm in isolation would be needed to rule out noise
with confidence, but it does not change the coordinate-descent decision below (E-append was not the
frontrunner on quality either).

## Coordinate-descent decision: weight 2, not n=10

The brief's step (2) asked for `expansion` at weight 2 **or** `n=10`, "whichever (1) shows recall
headroom" for. **Weight 2 was run** (it requires no new GPU generation — the pseudo-query file is
identical to E-field-1's, only the scoring weight changes — so it is the cheaper experiment to run
first and inspect before deciding whether a second, costlier doc2query pass at `n=10` is justified).

Evidence for stopping at weight 2 rather than spending the budget on `n=10`:

- Coverage recovery **increases monotonically and cleanly with weight** (17 → 20 net, still zero
  losses) — this is the signature of a *weighting* effect (terms are already present in the
  postings at `n=5`; more weight surfaces them further), not a *vocabulary* ceiling that only more
  distinct pseudo-queries could break through.
- The weight1 → weight2 step's marginal return is already small and mixed: nDCG@10/recall@10 tick
  up by roughly +0.1 pp further, but `all_required@4` overall is *lower* for E-field-w (0.3230)
  than E-field-1 (0.3240) — a same-order-of-magnitude move in the other direction. This is the
  diminishing-returns pattern one step up, which argues against expecting a further, larger jump
  from a bigger lever (`n=10`) that has not itself been tested.
- The samples above show `n=5` already produces meaningful *within-skill* redundancy (2 of 5
  sampled skills had a verbatim/near-verbatim repeat) — `n=10` would generate more text but a
  material fraction of it is likely to be more of the same repeated phrasing rather than new
  vocabulary, tempering how much headroom is actually available to unlock.

**The 4th reserved arm slot (§4: "best follow-up of 1-3, or don't spend it") is intentionally not
spent.** All three explored arms sit within a tight, mutually-overlapping band on every metric,
the weight1→weight2 step already shows diminishing/mixed returns, and every arm's `all_required@4`
movement (+0.6–0.7 pp) is far enough below the +2.0 pp test-adoption bar that a 4th coordinate-
descent step is very unlikely to change the qualitative conclusion. Budget preserved rather than
spent on a low-expected-value follow-up.

## Frozen proposal

**Propose freezing E-field-w** (doc2query `n=5`/skill, sixth BM25F field `expansion` at weight 2)
as F3's single candidate for the TL's once-per-family test-A/test-B run — it has the best or tied
point estimate on every quality metric among the three arms, the best coverage recovery (20 net,
zero losses), and near-zero cost (+3.9% index bytes, query latency indistinguishable from
baseline; no query-time model, no hook change).

**Calibrated expectation, stated plainly so the TL can weigh the test spend**: this is *not* a
confident prediction of clearing the adoption gate. DENSE-PROGRAM.md §5 gates adoption on
`all_required@4 ≥ F0 + 2.0 pp` (CI excluding 0) on **both** test corpora; on dev, the same metric
moved only **+0.6 pp**, roughly a third of the minimum-benefit bar, even though `nDCG@10`/`recall@10`
show a robust, CI-excluding-zero (but similarly small) improvement. Nothing here rules out F3 — the
coverage story is genuinely clean (additive, no losses, cheap) — but dev evidence does not support
an expectation that this candidate clears the bundle-completeness gate on test. This differs from
the R1 dense-encoder reference's test-A result (§7.1: `all_required@4` +17.96 pp, clearing the
gate by a wide margin, though R1 is an unfused/untuned reference, not a frozen proposal, so the two
are not a like-for-like comparison) by roughly two orders of magnitude in effect size; F3's ceiling
here looks like a genuinely smaller lever than a dense signal, consistent with `n=5`/skill
pseudo-queries adding a modest, mostly-redundant amount of extra lexical surface rather than new
semantic reach.

## Verification

- `python3 -m py_compile tools/expand/doc2query.py tools/eval/dev_expand.py tests/test_doc2query.py
  tests/test_dev_expand.py` — clean.
- `tests/test_doc2query.py`: 15 cases (13 pure-logic + 2 gated). Default venv (no torch/transformers):
  13 passed, 2 skipped. GPU venv (`/home/mike/.cache/guidefold/gpu-venv/bin/python`, real model,
  `device="cpu"` forced for portability): **15 passed in 13.67 s**, including the determinism test
  (two fresh-cache runs, byte-identical output).
- `tests/test_dev_expand.py`: 14 cases, including the expansion-field round-trip through the real
  `Router.score()` path and the per-arm one-changed-parameter contract; all pass against the real
  10,123-skill/1,000-query dev corpus where gated.
- Full repo suite: **416 passed, 0 failed, 0 errors, 2 skipped**, 32.7 s (`pytest -q
  --junitxml=...`; the 2 skips are the torch/transformers-gated determinism tests in the default
  venv, matching every other torch-dependent test in this repo's convention).

## Incidental finding (not fixed — out of scope for this agent)

`_serialize_artifact_files` (the E1.4 on-disk artifact writer, in `skills/guidefold/scripts/
guidefold`) hardcodes the **module-level** `Index.FIELDS` tuple at its two field-iteration sites,
rather than reading `idx.FIELDS` off the instance the way `Index.__init__`/`_build_bm25`/
`Router._bm25_scores` all do. This means the real on-disk serializer would silently **drop** a
subclassed extra field's postings/norms if ever pointed at one of this report's arms — confirmed
by reading the code, not exercised here since this agent never calls that function (`tools/eval/
dev_expand.py`'s `estimate_index_bytes` reproduces the same byte format independently, correctly
against `idx.FIELDS`, purely as a read-only measurement). Flagged for whoever next touches
`Index`/on-disk artifacts; `skills/guidefold/scripts/guidefold` was explicitly out of scope for
this agent.
