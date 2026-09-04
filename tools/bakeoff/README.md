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

export HF_HOME=/path/to/pre-downloaded/hf/cache   # models below must already be there
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1    # this harness never re-downloads anything

.venv/bin/python -m pytest tools/bakeoff/tests/ -v
.venv/bin/python tools/bakeoff/distill.py            # writes tools/bakeoff/build/<teacher>/...
.venv/bin/python tools/bakeoff/arms.py "some query"   # top-5 URNs + wall-clock, every arm
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

**Not yet done, needed before phase 2 (flagged on coordinator review, tracked here, out of scope
for this PR):** both B6's ~8s/pair reranking and the two slowest dense teachers' cold-encoding cost
are shaped like unbatched, one-at-a-time forward passes rather than a genuine model-capacity limit.
At 159.5s for one query's top-20 rerank, the full 220-query golden set (phase 2) would cost
~10 hours on B6 alone; at ~10s/doc for the slowest teachers, encoding 220 queries per teacher would
cost ~35 minutes each. Batching B6's 20 pairs into one forward pass, and batching the dense
teachers' per-query/per-doc calls, should bring both down to low minutes — this needs doing before
phase 2 starts, not as part of this tokenizer/Zipf/normalisation fix.
