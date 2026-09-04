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
| `tokenizer.py` | The shared tokenizer contract: NFC normalize → ASCII-only lowercase → split on `[a-z0-9]+`. `scripts/guidefold` must implement this **byte-identically**. |
| `encode.py` | One `Encoder(hf_id, revision).encode(texts) -> np.ndarray[float32]` interface over every teacher model, with each model's own pooling/prompting, disk-cached. |
| `distill.py` | Builds the tier-1 static int8 word table (`words.bin`) and skill vectors (`vectors.i8`), model2vec-style. |
| `arms.py` | The bake-off retrieval arms (B0–B6), each `(query, corpus) -> ranked URN list`. |
| `tests/` | Real pytest tests against the real fixture and real (pre-downloaded) models — no mocking. |
| `build/<teacher>/` | `distill.py`'s output. Only `words.json` (the manifest) is committed; `words.bin`/`vectors.i8`/`teacher.f16` are build artifacts (`.gitignore`d). |
| `.bakeoff-cache/` | Disk cache of `encode.py` embeddings, keyed by content hash. Never committed. |

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
| B0 | `skills/guidefold/scripts/guidefold`'s own `rank_cards()`, called unmodified | today's baseline |
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
- **Zipf weight = `1 / log(1 + rank)`, rank 1 = most frequent** — implemented literally as
  specified, even though (see "Known limitation" below) this is the *opposite* of the IDF-style
  downweighting standard model2vec-style distillation uses.
- **Quantization scale = `max(|word_table_f32|) / 127`** — derived from the word table alone, not
  the (much larger-magnitude) skill sums. See the long comment above the scale computation in
  `distill.distill()` and the "Known limitation" section below for exactly why, with real numbers.
- Both `words.bin` and `vectors.i8` reuse this **one** scale, per spec ("requantized ... with the
  same scale").
- BLAS/LAPACK pinned to one thread (`OMP_NUM_THREADS=1` etc., set before numpy import) plus
  `numpy.linalg.svd`'s determinism, sorted-URN skill ordering, and alphabetical word ordering
  together give bit-for-bit reproducible reruns — verified by `tests/test_distill.py`'s
  `test_rerun_is_byte_identical` (also independently checked by hand with `cmp`).

### Known limitation: B4 static-table retrieval quality

This is the most important finding from this phase's verification pass, found by actually running
the arms against the fixture (not by inspection):

Combining the literal Zipf formula (favors *frequent* words) with a raw **sum** (not mean)
aggregation over a skill's tokens (per spec, step 7 — "the single most important rule") means a
skill's vector magnitude scales with its length and its use of common words, roughly independent
of int8 quantization. On this 26-skill fixture:

- A single word vector's max-abs value is ~0.32; a skill-sum's max-abs value is ~26.3 — an ~83×
  gap. A **single shared scale** (required by spec) that avoids clipping the skill sums quantizes
  **2251 of 2257 words (99.7%) to the all-zero int8 vector** — i.e. the query side of B4 is
  almost always the zero vector, and every skill ties at cosine 0 (verified: this produced an
  exact alphabetical-tiebreak ranking, identical for three unrelated queries).
- This harness's fix (see above) derives the scale from the word table alone instead, which keeps
  every word's int8 vector non-zero (2257/2257) — at the cost of **~71.7%** of skill-vector int8
  *dimensions* saturating at ±127 (`words.json`'s `skill_vector_clip_rate`).
- Even in **exact float32** (zero quantization error, to isolate the aggregation/weighting choice
  from the int8 encoding), B4's top-5 for `"add RBAC to this new admin-only endpoint"` puts a
  generic auth skill ahead of the actual `rbac-policies` skill (rank #4 of 5); for
  `"we are paged right now, help me handle this outage"` the on-call runbook skill is ranked #2,
  not #1. B4 alone is directionally query-sensitive but noisy on this fixture.
- **B5 (B1+B4 RRF) recovers well** in the one sample query tested — B1's exact lexical match
  pulls `rbac-policies` back to #1 even though B4 alone ranked it #5 — which is exactly the
  fusion arm's reason to exist, but it means B5's quality currently rides mostly on B1, not B4.

This is a real tension in the specified pipeline (Zipf-weight direction + sum aggregation +
single shared scale), not a code bug — confirmed by reproducing it in pure float32 with no
quantization at all. Fixing it would mean deviating from literally-specified mechanics (the exact
Zipf formula, "sum" not "mean", and the shared scale). This phase's code implements the literal
spec faithfully and documents the consequence; whether to (a) reverse the Zipf-weight direction
toward IDF-style downweighting of frequent words, (b) mean- or L2-normalize the skill aggregation
before quantizing, or (c) accept B4 as a weak-but-fusable signal and lean on B1+B5 is a judgment
call for the human + the golden-set evaluation pass this phase deliberately does not perform.

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
