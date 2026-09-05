# tools/bakeoff — E1.3 phase 1: model harness, shared tokenizer, static-embedding distillation

This directory is the **tier-2** half of Guidefold's two-tier dense retrieval design. It exists
to answer one question with real numbers: *which retrieval arm should the shipped hook run?*
It is never shipped, never imported by `skills/guidefold/scripts/guidefold`, and never installed
into a consumer monorepo.

## Why torch is OK here but not in `scripts/guidefold`

`skills/guidefold/scripts/guidefold` (the CLI) is a **single-file, stdlib + PyYAML only** script
(see the repo's top-level `CLAUDE.md`): it ships inside the skill ZIP to the registry and runs as
a lightweight hook on every harness invocation, so it can never depend on torch/transformers.

Everything in `tools/bakeoff/` runs at **CI / offline-evaluation time**, on a developer or CI
machine, never inside a harness hook. That is "tier 2" in the router design: a place to freely
use torch, sentence-transformers, and transformers to (a) run full teacher-model encoders as a
quality baseline and (b) *distill* one of those teachers down into a small, stdlib-representable
artifact (`words.bin` / `vectors.i8`) that tier 1 — the actual shipped hook — can load and score
with plain Python integer arithmetic. `scripts/guidefold` will eventually implement a byte-
identical tokenizer to `tokenizer.py` (see that file's docstring) and a reader for `words.bin` /
`vectors.i8`'s format (documented below); it will never import anything in this directory.

## Layout

| File | Purpose |
|---|---|
| `corpus.py` | Loads the Meridian fixture (`examples/monorepo`) into `SkillRecord`s, reusing the CLI's own frontmatter parser via `importlib.machinery.SourceFileLoader` (never reimplements it). |
| `tokenizer.py` | The shared tokenizer contract: NFKD-normalize + strip combining marks (folds accents onto their base letter) → ASCII-only lowercase → split on `[a-z0-9]+`. `scripts/guidefold` implements this **byte-identically**. |
| `encode.py` | One `Encoder(hf_id, revision).encode(texts) -> np.ndarray[float32]` interface over every teacher model, with each model's own pooling/prompting, disk-cached. |
| `distill.py` | Builds the tier-1 static int8 word table (`words.bin`) and skill vectors (`vectors.i8`), model2vec-style. |
| `arms.py` | The bake-off retrieval arms (B0–B6), each `(query, corpus) -> ranked URN list`. |
| `tests/` | Real pytest tests against the real fixture and real (pre-downloaded) models — no mocking. |
| `build/<teacher>/` | `distill.py`'s output. Only `words.json` (the manifest) is committed; `words.bin`/`vectors.i8`/`teacher.f16` are build artifacts (`.gitignore`d). |
| `.bakeoff-cache/` | Disk cache of `encode.py` embeddings, keyed by content hash. Never committed. |

**Any `words.bin`/`vectors.i8` built before the tokenizer accent-folding fix (PR "fix: shared
tokenizer accent folding, Zipf direction, and document normalisation") is invalid and must be
regenerated.** That fix changes `tokenizer.py`'s output for any accented word (folds it onto its
base letter instead of dropping it), which changes the vocabulary's word-id assignment (alphabetical
order over a different set of distinct words — 2260 vs. the prior 2257 on this fixture) and every
word's Zipf rank. A pre-fix `words.bin` and a post-fix one do not agree on what word id N means;
regenerate with `distill.py` rather than mixing builds. The committed `words.json` manifest under
`build/<teacher>/` already reflects the post-fix vocabulary as of this PR, so `git pull` + rerunning
`distill.py` is enough — nothing to hand-migrate.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/bakeoff/requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cpu
# On a box with a CUDA GPU, install the matching torch build instead (e.g.
# --index-url https://download.pytorch.org/whl/cu128) -- Encoder/Reranker pick up
# torch.cuda.is_available() automatically, no other change needed.

export HF_HOME=/path/to/pre-downloaded/hf/cache   # models below must already be there
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1    # this harness never re-downloads anything
# Alternatively, mirror each model to GUIDEFOLD_MODELS_ROOT/<org>__<name>/<revision>/ (default
# ~/.cache/guidefold/models) -- _local_model_path() in encode.py prefers that flat layout over
# HF_HOME's own hub cache when both are set, so a machine that already has the weights (e.g. via
# the GCS mirror URIs in the table above) never touches HuggingFace at all.

.venv/bin/python -m pytest tools/bakeoff/tests/ -v
.venv/bin/python tools/bakeoff/distill.py            # writes tools/bakeoff/build/<teacher>/...
.venv/bin/python tools/bakeoff/arms.py "some query"   # top-5 URNs + wall-clock, every arm
.venv/bin/python tools/bakeoff/report_b6.py --full    # B6 vs B5 over the full 220-query golden set
```

## Pinned models

All five models were pre-downloaded to `HF_HOME` at the exact commit SHAs below; nothing in this
directory re-downloads them. Weights are mirrored to
`gs://guidefold-models-b6a18a/<hf_id with / -> __>/<commit sha>/`.

| HF id | Commit SHA | License | Role | GCS URI |
|---|---|---|---|---|
| `Qwen/Qwen3-Embedding-0.6B` | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | apache-2.0 | generic dense teacher (B2a) | `gs://guidefold-models-b6a18a/Qwen__Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/` |
| `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | **mit** | generic dense teacher (B2b) | `gs://guidefold-models-b6a18a/BAAI__bge-m3/5617a9f61b028005a4858fdac845db406aefb181/` |
| `pipizhao/SkillRouter-Embedding-0.6B` | `c03c9bcee9fce92ab0262bb6dcf54d174a8ba558` | apache-2.0 | skill-tuned dense teacher (B3a); default static-table teacher (B4) | `gs://guidefold-models-b6a18a/pipizhao__SkillRouter-Embedding-0.6B/c03c9bcee9fce92ab0262bb6dcf54d174a8ba558/` |
| `ThakiCloud/SKILLRET-Embedding-0.6B` | `0e10886e80a0aacc9efddc28282a258e2ab7eae1` | apache-2.0 | skill-tuned dense teacher (B3b) | `gs://guidefold-models-b6a18a/ThakiCloud__SKILLRET-Embedding-0.6B/0e10886e80a0aacc9efddc28282a258e2ab7eae1/` |
| `pipizhao/SkillRouter-Reranker-0.6B` | `78986e1142d12857cfd85b8005e62902cd42d858` | apache-2.0 | cross-encoder reranker (B6, E1.6) | `gs://guidefold-models-b6a18a/pipizhao__SkillRouter-Reranker-0.6B/78986e1142d12857cfd85b8005e62902cd42d858/` |

**License correction**: `BAAI/bge-m3`'s stated license was verified directly against the model's
own README (not just the metadata tag) — it **is** `mit`, as stated. No other license discrepancy
was found across the five models.

## Retrieval arms (`arms.py`)

| Arm | What | Notes |
|---|---|---|
| B0 | `skills/guidefold/scripts/guidefold`'s own `Index.build()` + `Router.route()`, called unmodified | today's baseline (PR #7's router split replaced the single `rank_cards()` this arm used to call in phase 1) |
| B1 | Field-weighted BM25 (name×3, triggers×2.5, description×2, digest×1.5, body×1; k1=1.2, b=0.75) | own implementation, `tokenizer.py` |
| B2a | Dense, Qwen3-Embedding-0.6B, encoded fresh | generic teacher |
| B2b | Dense, bge-m3, encoded fresh | generic teacher |
| B3a | Dense, SkillRouter-Embedding-0.6B, encoded fresh | skill-tuned teacher |
| B3b | Dense, SKILLRET-Embedding-0.6B, encoded fresh | skill-tuned teacher |
| B4 | Dense, the tier-1 static int8 student table alone | **the arm the shipped hook actually runs** |
| B5 | B1 + B4, fused by Reciprocal Rank Fusion (k=60) | candidate shipped configuration |
| B6 | B5's top-20, reranked by SkillRouter-Reranker-0.6B (yes/no logit difference) | E1.6, CI-time only |

`B1+` (BM25 over teacher-generated query expansions, ADR-0009 §1) is a **documented, un-
implemented extension point** — see the module docstring in `arms.py`. It needs a CI-time
expansion-generation step (an LLM call cached by body hash) that this corpus-and-arms-only phase
has no golden set to justify building yet.

## `words.bin` / `vectors.i8` / `teacher.f16` binary format

The spec named these artifacts but not their byte layout, so the layout below is this harness's
own design (documented here and in `distill.py`'s docstrings, so it can be reimplemented
byte-identically by a future stdlib-only reader):

- **`words.bin`**: header `<4sHHIfI` (magic `b"GFW1"`, version, dims, vocab size, scale, words-blob
  length), then the newline-joined UTF-8 words blob, then `vocab_size * dims` int8 values (word
  id = position in the words blob, alphabetical).
- **`vectors.i8`**: header `<4sHHIfI` (magic `b"GFV1"`, version, dims, skill count, scale,
  URNs-blob length), then the newline-joined UTF-8 URNs blob (sorted order), then
  `n_skills * dims` int8 values, then `n_skills` uint32 values (`|d|²` per skill, for cosine
  without a sqrt on the word side).
- **`teacher.f16`** (`--experimental` only, never shipped): header `<4sHHII` (magic `b"GFT1"`,
  version, dims, skill count, URNs-blob length), URNs blob, then `n_skills * dims` float16 values
  — the teacher's own document embeddings, for comparison only.

## Distillation pipeline (`distill.py`) and the interpretive decisions behind it

The task spec fixed the *shape* of the pipeline but left several numeric details to this harness's
judgment. All are documented inline in `distill.py`; the load-bearing ones:

- **Word id = alphabetical order** of the corpus vocabulary (separate from the frequency rank used
  only for Zipf weighting).
- **"Common-English core ... derived from document frequency"** = the subset of the corpus
  vocabulary whose document frequency clears `max(3, ceil(0.2 * num_docs))` — not any external
  stopword list, since the corpus is the only source the spec permits.
- **Zipf weight = `log(1 + rank)`, rank 0-indexed (0 = most frequent)** — corrected (coordinator
  review) from phase-1's literal-per-spec `1 / log(1 + rank)` (1-indexed), which was *anti-IDF*:
  it weighted frequent words **up**, the opposite of the standard model2vec-style downweighting.
  Rank 0 ("the" on this fixture) now contributes exactly zero weight; rarer words get strictly
  more weight. See the "Known limitation" section below (now resolved) for the numbers this fixed.
- **Quantization scale = `max(|word_table_f32|) / 127`** — derived from the word table alone, not
  the (much larger-magnitude) skill sums, so individual word vectors stay usably non-zero. See the
  long comment above the scale computation in `distill.distill()`.
- `words.bin` and `vectors.i8` **no longer share this scale** (corrected, coordinator review, from
  phase-1's literal-per-spec "requantized ... with the same scale"): each skill's raw float32 sum
  is L2-normalised to unit length before quantising (`distill.quantize_skill_vectors()`), so
  `vectors.i8` uses a fixed, universal `1/127` scale instead of the word table's measured one. By
  Cauchy-Schwarz a unit-L2-norm vector's components are all ≤1 in magnitude, so this makes int8
  clipping on the document side structurally impossible — see "Known limitation" below.
- BLAS/LAPACK pinned to one thread (`OMP_NUM_THREADS=1` etc., set before numpy import) plus
  `numpy.linalg.svd`'s determinism, sorted-URN skill ordering, and alphabetical word ordering
  together give bit-for-bit reproducible reruns — verified by `tests/test_distill.py`'s
  `test_rerun_is_byte_identical` (also independently checked by hand with `cmp`).

### Resolved: B4 static-table retrieval quality (was "Known limitation")

Phase-1's verification pass (found by actually running the arms against the fixture, not by
inspection) surfaced two compounding defects in the literally-specified pipeline, both since
corrected on coordinator review — this section is kept as a record of the finding and the fix,
not a live limitation:

- **Zipf-weight direction was inverted.** The literal spec formula `1 / log(1 + rank)` (1-indexed)
  is *anti-IDF*: it weights frequent words **up**, the opposite of standard model2vec-style
  downweighting. Combined with raw **sum** (not mean) aggregation over a skill's tokens, a
  skill's vector magnitude scaled with its length and its use of common words, largely independent
  of what the query actually asked for.
- **A single shared int8 scale across word table and skill sums was structurally lossy.** A single
  word vector's max-abs value is ~0.32; a skill-sum's max-abs value is ~26.3 — an ~83× gap. A
  single shared scale that avoids clipping the skill sums quantized **2251 of 2257 words (99.7%)
  to the all-zero int8 vector** on this fixture — i.e. the query side of B4 was almost always the
  zero vector, and every skill tied at cosine 0 (verified: this produced an exact
  alphabetical-tiebreak ranking, identical for three unrelated queries). Deriving the scale from
  the word table alone (phase-1's first fix) kept every word vector non-zero, but then clipped
  **~71.7%** of skill-vector int8 *dimensions* to the boundary instead — the two magnitudes cannot
  share one 8-bit scale without sacrificing one side or the other.

**The fix (coordinator review, folded into the tokenizer-accent-folding PR):**
`log(1 + rank)`, rank 0-indexed (0 = most frequent = zero weight, since "the" carries no signal)
for the Zipf direction; per-document L2-normalisation to unit length *before* int8-scaling
(`distill.quantize_skill_vectors()`) for the shared-scale problem — by Cauchy-Schwarz a unit-L2-norm
vector's components are all ≤1 in magnitude, so scaling by 127 can no longer clip, structurally,
not just empirically. Query vectors (the hook, at query time) stay a plain unnormalised integer
sum: for one fixed query, ranking documents by `dot(q,d)/|d|` is invariant to any positive rescaling
of the query's own vector, so only the document side needed normalising.

**Measured after both fixes** (`words.json`'s `skill_vector_clip_rate`, this fixture):
`skill_vector_clip_rate` is now exactly **`0.0`** (down from 0.716796875) — every skill vector
uses the full int8 range with zero saturation, and no word's int8 vector is zeroed by scale
mismatch (the sole exception being rank 0's word itself, whose Zipf weight of `log(1)=0` zeroes
it *by design*, not by quantization). Vocabulary size moved from 2257 to 2260 words as a side
effect of the same PR's tokenizer fix (see below) folding a few previously-dropped accented words
back into distinct vocabulary entries.

Re-running the sample queries post-fix:
- `"add RBAC to this new admin-only endpoint"` — B4 top-5: `postgres-auth`, `auth-sdk-usage`,
  `atlas-api-conventions`, `rbac-policies` (#4), `terraform-conventions`; B5 (B1+B4 RRF) top-5:
  `rbac-policies` (#1), `auth-sdk-usage`, `postgres-auth`, `atlas-api-conventions`,
  `turnstile-oncall-runbook`. B4 alone is no longer degenerate (distinct, query-sensitive
  rankings, not an alphabetical tie), though `rbac-policies` itself still isn't B4's own #1 on
  this fixture — B5's fusion with B1's exact lexical match is still doing real work, exactly as
  designed, not compensating for a broken B4 anymore.

Whether B4 alone is good enough without B1 fusion, or whether further weighting/aggregation
choices are worth exploring, is still a question for the golden-set evaluation pass (phase 2),
not something this fixture-of-26 sample query can settle.

## Measured timings (this fixture: 26 skills, CPU only, no GPU)

Machine: `nproc` reported 16 cores in this environment during this pass (an earlier check in the
same environment reported 8 — the visible core count was not stable across checks, worth noting
for anyone budgeting CI time from these numbers), ~14-19GB RAM.

**Per-arm, one sample query (`"add RBAC to this new admin-only endpoint"`), all embedding/build
caches warm** (i.e. the steady-state a CI pipeline would see on a rerun):

| Arm | Wall-clock |
|---|---|
| B0 | 0.038s |
| B1 | 0.012s |
| B2a | 0.004s |
| B2b | 0.003s |
| B3a | 0.003s |
| B3b | 0.003s |
| B4 | 0.92s |
| B5 | 0.000s |
| B6 | 159.5s |

**B6's number above predates E1.6's batching + GPU support and is now stale for the current code
-- see "E1.6: batched B6, GPU-verified, full golden set" below for the current, much lower number
and the real 220-query metrics it produces.**

**Cold (first-ever, cache-empty) dense-encoding cost for the 26-skill corpus** — this is the real
cost a CI pipeline pays once per corpus change, per teacher, and it is *not* small:

| Teacher | Backend / pooling | 26 docs, cold | 1 query |
|---|---|---|---|
| Qwen/Qwen3-Embedding-0.6B (B2a) | sentence-transformers, last-token | 249.1s | 0.22s |
| BAAI/bge-m3 (B2b) | sentence-transformers, CLS | 61.7s | 0.11s |
| pipizhao/SkillRouter-Embedding-0.6B (B3a, also B4's teacher) | raw transformers, last-token | 92.5s | 0.23s |
| ThakiCloud/SKILLRET-Embedding-0.6B (B3b) | sentence-transformers, last-token | 251.4s | included above |

Two of four dense teachers (Qwen3-Embedding, SKILLRET-Embedding) take **~4 minutes** to encode
just 26 documents on this CPU-only machine; bge-m3 is ~4× faster than those two, likely because
it is a bidirectional/CLS-pooled encoder rather than a causal, last-token-pooled one. This scales
linearly with corpus size in the worst case — a real monorepo with hundreds of skills would need
minutes-to-tens-of-minutes of CI time per teacher, per rebuild, for the two slower models. This is
squarely tier-2/CI-time cost (never paid by the shipped hook), but it is a genuine data point for
sizing the CI job that will eventually run `distill.py` for real.

`distill.py`'s own word-vocabulary encoding (2257 words, one teacher) took ~101s cold in earlier
testing and 0.98-1.09s with a warm `.bakeoff-cache/` — a one-time-per-corpus-change cost, not a
per-query one.

B6 (the reranker) is always cold — it is not cache-backed by design — and costs ~8s/candidate on
this CPU (159.5-165.5s for 20 candidates). That is fine for E1.6's CI-time use case; it would not
be fine as a live per-request hook path, which matches ADR-0015/ROUTER-SPEC-v2's design (reranking
is a CI-time evaluation step here, not something the shipped hook runs per query).

**No arm failed to run.** Every arm returns a valid, deduplicated ranked list of fixture URNs for
the sample query (`tests/test_arms.py::test_every_arm_returns_valid_deduplicated_urns`); the
concern above is retrieval *quality* and *CI wall-clock*, not correctness or crashes.

**Historical note (superseded below):** this section originally flagged B6's ~8s/pair reranking and
the two slowest dense teachers' cold-encoding cost as unbatched, one-at-a-time forward passes, and
guessed that batching alone would bring both "down to low minutes." E1.6 batched B6 and measured
that guess directly: it was only half right (see next section).

## E1.6: batched B6, GPU-verified, full golden set

`Reranker.score_batch()` (and `Encoder`, for the same reason) now score every candidate of a query
in **one forward pass** instead of one `AutoModelForCausalLM`/`AutoModel` call per candidate, and
both classes are device-aware: CUDA when `torch.cuda.is_available()` (fp16), CPU otherwise (fp32,
unchanged) -- the same module-level `DEVICE`/`DTYPE` globals in `encode.py` that E1.3 phase 2's GPU
pass (#14) landed, so `Reranker` and `Encoder` never disagree about which device a run is on. Model
weights load from a local machine mirror when present (`_local_model_path()` in `encode.py`, default
`~/.cache/guidefold/models/<org>__<name>/<revision>/`, override with `GUIDEFOLD_MODELS_ROOT`) so a
machine that already has the weights never re-downloads them from HuggingFace;
`HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` are set unconditionally by `encode.py` so a cache miss
fails loudly instead of silently hitting the network.

**Batching alone, on CPU, was a modest win, not the hoped-for one:** measured separately (not
re-verified in this PR — the CPU-only venv used for that run no longer exists), batching B6's 20
candidates into one CPU forward pass brought the unbatched 159.5s/query down to roughly 100s/query
— about a 35% improvement. That confirms the original guess was wrong on CPU: the cost is
FLOPs/compute-bound (a 0.6B-parameter forward pass over 20 sequences is still a lot of arithmetic
on 16 threads), not per-Python-call-dispatch overhead, so batching without more compute underneath
it was never going to reach "low minutes."

**What actually got there was a GPU, not batching.** This dev machine has a passed-through RTX
4090 (see the `wsl-gpu-compute` skill). Running `tools/bakeoff/report_b6.py --full` — the entire
220-query golden set, all 5 strata, no sampling — end to end:

```
golden set: 220 cases total across 5 strata
running the FULL set (--full)
  multi_skill          66/66
  no_applicable        44/44
  sibling_ambiguity    66/66
  simple               22/22
  stale_adversarial    22/22
total cases this run: 220

B5  (RRF of B1 BM25 + B4 static dense -- retrieval order)
stratum                  n     hit@1  recall@8  ndcg@10  completeness@4  distractor_rate@4
multi_skill             66    0.9242    0.9798   0.8890          0.9848             0.0000
no_applicable           44         —         —        —               —             0.4318
sibling_ambiguity       66    0.7424    1.0000   0.8844          0.9545             0.4545
simple                  22    0.8636    1.0000   0.9204          0.9545                  —
stale_adversarial       22    0.7500    1.0000   0.8200          0.8500             0.7727
OVERALL                220    0.8276    0.9923   0.8833          0.9540             0.4962

B6  (B5's top-20 reranked by SkillRouter-Reranker-0.6B, batched -- retrieval order)
stratum                  n     hit@1  recall@8  ndcg@10  completeness@4  distractor_rate@4
multi_skill             66    0.8939    0.9697   0.8612          0.9545             1.0000
no_applicable           44         —         —        —               —             0.3864
sibling_ambiguity       66    0.8636    0.9848   0.9357          0.9848             0.4697
simple                  22    0.8182    1.0000   0.9119          1.0000                  —
stale_adversarial       22    0.5000    1.0000   0.7419          0.9000             0.5909
OVERALL                220    0.8276    0.9828   0.8821          0.9655             0.4662

rank-1 changed (B6 vs B5): 98/220 (44.5%)
Spearman rank correlation, B6 vs B5 order: mean 0.3813 over 220 queries (min -0.4241, max 0.8421)
batched reranker time per query: mean 0.48s (min 0.31s, max 8.09s), total 106.0s over 220 queries
wall-clock for this run (B5 + B6 + bookkeeping, 220 queries): 109.6s
```

(`abstention_precision` is omitted above for width; both arms print `—` for it on this fixture —
no case here has the router abstaining when it should not, so precision's denominator is 0.)
The full, unabridged run (including `abstention_precision`'s column) is committed verbatim at
`docs/reports/bakeoff/52ea203.md`.

B5's own numbers moved slightly from the run quoted in an earlier draft of this section (e.g.
`sibling_ambiguity` hit@1 0.7727 → 0.7424) purely because `encode.py`'s upstream GPU batching
(E1.3 phase 2, #14 — length-sorted batches, default batch size 64 on CUDA) changed the reduction
order of the *same* floating-point embeddings B4/B5 depend on. This is not a bug and not new
information — it is a live demonstration of the determinism note below: B5 and B6 are both
GPU-float paths, and neither is bit-reproducible across a batching change, let alone across
machines. Nothing about the shipped CLI's own numbers is affected.

**Timing**: 109.6s wall-clock for the *entire* 220-query golden set, batched top-20 reranking
included — roughly three orders of magnitude below the 159.5s **per query** the unbatched CPU
number above implied for the same workload (which would have cost ~10 hours over 220 queries).
The 8.09s max is the one cold-start query in the run (model load + first CUDA kernel
compilation/autotune); every subsequent query measured ~0.3-0.4s, matching an isolated warm-model
measurement taken separately.

**Does the reranker earn its cost? On this golden set, no — not as configured, and it could not
have gone in the hook path even if the quality had come out ahead.** ADR-0020's own budget for the
shipped CLI is 300 ms end to end (measured at ~210 ms including interpreter start-up); B6's batched
reranker measured 0.48s **mean** per query (min 0.31s, max 8.09s for the one cold-start query) —
already above the *entire* hook budget on the mean case alone, on a GPU this class of dev machine
happens to have, with no allowance yet for the CPU-only reality of a typical hook invocation. This
is the latency finding that justifies E1.6 measuring the reranker in shadow mode rather than
wiring it in directly: it is disqualified on cost before quality is even considered.

Quality-wise, the overall numbers hide a more interesting split than they show: B6 ties B5 on
hit@1 in aggregate this run (0.8276 both) but is worse on ndcg@10 (0.8821 vs 0.8833) and recall@8
(0.9828 vs 0.9923); per stratum the reranker is not uniformly bad — `sibling_ambiguity` clearly
**improves** (hit@1 0.7424 → 0.8636), while `stale_adversarial` **collapses** (hit@1 0.75 → 0.50, a
25-point drop). Averaging those two together into one "B6 vs B5" number erases the fact that this
reranker seems to help exactly the kind of case it is named for (disambiguating between sibling
skills) while actively hurting a stratum built to catch stale/wrong answers — a real, actionable
signal a single overall row would have hidden.

`multi_skill`'s distractor_rate@4 — lower is better, 0.0 is the target — goes from **0.0 to 1.0**,
which looks like a bug (NaN silently coerced, say) at a glance. It is not: checked against
`tests/golden/multi_skill.yaml`, only **one of the stratum's 66 cases** (`multi-004`, "moving the
geo indexing code into a shared library, what do I need to update") has a `distractors` entry at
all — `metrics.distractor_rate` returns NaN (excluded from the mean, not coerced to anything) for
every case without one, per its own docstring. So this 0.0→1.0 swing is a real, single-case flip,
not a stratum-wide effect: B5 kept `atlas.geo:geospatial-indexing` (a same-topic, wrong-node
distractor — the query says "geo indexing" but the case is scoped to `shared`/`libs` and the real
answer is about move/versioning mechanics, not H3 index design) out of the top 4, and B6's reranker,
which sees only text and has no node-scoping, pulled it in. Real, but an n=1 result for this
metric on this stratum — not "every multi-skill query now has a distractor," which is what this
line would otherwise misleadingly suggest.

Rank-1 changes 44.5% of the time and the mean Spearman correlation between the two orders is only
0.38 — the reranker is not making small corrections to B5's order, it is substantially reshuffling
it, and on net (latency disqualification aside) that reshuffling helps one stratum and hurts
another more. This is exactly the measurement E1.6 asked for ("measure the reranker before it
touches the hook"): the answer, today, is don't wire it in yet — on cost grounds alone, and the
quality picture is genuinely mixed rather than uniformly bad.

**Determinism note, do not conflate these numbers with the CLI's guarantee**: GPU floating-point
reductions are not bit-reproducible across batch sizes or hardware (cuBLAS/cuDNN kernel selection
varies), so nothing in this section is part of `find`/`hook`'s determinism claim — that guarantee
lives entirely in the integer-only, torch-free CLI path (`Index`/`Router`, ADR-0020). B6 is offline
evidence about whether the reranker is worth productionising, produced by a tier-2, GPU-optional
tool that never ships.
