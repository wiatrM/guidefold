# R4b: lazy terms.bin/postings.idx ("R4 cont'd") — closing R4's open item, T0 size curve

2026-09-05. Machine: WSL2, Intel Core i7-10700K @ 3.80GHz, 16 threads, CPython 3.12.3, glibc 2.39
(Ubuntu) — same physical machine as the prior R4 report. Branch `fix/lazy-terms-postings`,
merged to `origin/main` (fast-forward, no conflicts; `main` had not touched
`skills/guidefold/scripts/guidefold` since this branch forked — confirmed via
`git log --name-only 5086406..5d0f686 -- skills/guidefold/scripts/guidefold`, empty).

Prior report: `docs/reports/bakeoff/R4-latency-lazy-load-2026-09-05.md` (cards/graph made lazy;
`terms.bin`/`postings.idx` identified as the *larger* remaining cost — ~250ms of ~271ms
`load_index_artifact` at 6,006 skills — and named "R5" as the natural follow-on). This report
closes that item: `terms.bin` and `postings.idx` get the same mmap+binary-search treatment
`postings.bin` already had, replacing a whole-file parse into a Python dict with an on-disk
sorted directory searched in `O(log V)` per term. Context: ADR-0024 §1 names tier T0 as "admitted
only where `guidefold doctor` measures warm p95 < 300ms on the consumer's own corpus" — this
report supplies that number, at the real corpus size and across a size curve.

## 1. Correctness review of the uncommitted diff

The diff (`skills/guidefold/scripts/guidefold`, +291/-72, inherited from a previous agent's
mid-run state) replaces:
- `terms.bin`: was `[varint term_len, term utf-8, varint idf]*` sorted by term, parsed whole into
  a `dict` at load time. Now: `u32 n_terms` + `(n_terms+1)` fixed `<II>` directory records
  `(string_offset, idf)` + a concatenated string blob, never parsed into a dict — `_LazyTerms`
  binary-searches the directory directly on the mmap and returns `(term_id, idf)`, where
  `term_id` is the term's rank in this same sorted order.
- `postings.idx`: was `[varint field_index, varint term_len, term utf-8, varint offset, varint
  length]*` sorted by `(field, term)`, parsed whole into a `{(field, term): (offset, length)}`
  dict. Now: `u32 n_entries` + `(n_entries+1)` fixed `<II>` records `(combined_key, offset)`
  where `combined_key = field_index * n_terms + term_id` — since every `term_id < n_terms`, this
  key is strictly monotonic across field boundaries too, so one flat sorted array and one binary
  search (`_LazyPostingsIndex.find`) serve every field; no term bytes are stored here at all (a
  term string is compared exactly once, in `_LazyTerms`).

Findings from reading the diff before running anything:
- **No score can change.** `idx.idf[t]` and postings offsets/lengths are carried through
  byte-for-byte; only *where* they live (dict vs. mmap'd directory) and *when* they're paged in
  changed. `_LazyTerms.get(term, default)` and `_LazyFieldPostings.get(term, default)` preserve
  the exact dict-like contract Router's `_bm25_scores` already calls.
- **Integer arithmetic holds.** `idf = round(x * IDF_SCALE)` where
  `x = log(1 + (n_docs - df + 0.5)/(df + 0.5)) >= 0` always (BM25's `+1` variant never goes
  negative), so every idf value is a non-negative int comfortably inside `u32` at any real corpus
  size; `combined_key = field_index * n_terms + term_id` similarly stays far under `u32` (max
  observed: 5 fields × 89,630 terms ≈ 448,150). The one real constraint this format change adds
  is a `u32` cap (4 GiB) on `postings.bin`'s total length and on the terms-blob length, neither
  reachable at any corpus size this project targets.
- **Tamper detection is unaffected.** `index --check` verifies whole-file `sha256` against
  `manifest.json`, independent of internal layout — added two tests
  (`test_check_index_artifact_detects_a_tampered_terms_bin`,
  `..._detects_a_tampered_postings_idx`) confirming corruption of either new-format file is still
  caught; both pass.
- **`sorted_terms`/`term_rank` construction at write time is only ever called on a plain-dict
  `Index` built by `Index.build`/`_build_bm25`** (i.e. `_serialize_artifact_files` never runs
  against an already-loaded lazy `Index`) — checked every call site (`write_index_artifact`,
  `tools/eval/skillret.py`'s `build_r0_index`/`_serialize_artifact_files` path) to rule out a
  lazy-on-lazy double-wrap.

`python3 -m py_compile skills/guidefold/scripts/guidefold` — clean.

## 2. Test suite

Full suite: **488 passed, 0 failed, 2 skipped** (`python3 -m pytest -q --junit-xml=...`, 36.8s;
the 2 skips are the pre-existing numpy-backed R1 router tests, unrelated to this change — see PR
#34). `tests/test_index_artifact.py` alone: **40 passed**, including the two new tamper-detection
tests above.

`test_index_artifact_bytes_are_identical_across_two_fresh_interpreter_builds` (the
PYTHONHASHSEED-determinism test — runs `guidefold index` as separate subprocesses, each with its
own random hash seed, and diffs every artifact file byte-for-byte) run individually: **1 passed**
(`0.51s`). Confirms the new binary directory layout does not leak hash-order-dependent iteration
— both `sorted(idx.idf.keys())` and `sorted(idx.postings[field].keys())` are called before any
byte is written, exactly as before.

## 3. Parity: is ranking/selection bit-identical to `main`?

Built the 6,006-skill SKILLRET-test corpus's cards/nodes once (shared — `build_cards`/
`build_taxonomy` are untouched by this diff). For each of `main` (`origin/main`'s CLI, extracted
via `git show`) and this branch's CLI: built the in-memory R0 Index (shipped weights,
`w_dense=0`) from those same cards, serialized it to a scratch artifact with that variant's own
`_serialize_artifact_files`, read it back with that variant's own `load_index_artifact` — the
part that actually differs — and built a `Router` on the **loaded** (not in-memory) Index. For
each of the 1,000 frozen SKILLRET-train dev queries (`tools/eval/corpora.py
load_skillret_dev()`; query text only — gold ids belong to the train pool, not this test-pool
build, so this is a determinism probe, not a quality claim) at node `"_root"`: ran
`policy_filter → candidates → score → select(k=4, admissible=...)` — the real product path, same
call sequence `tools/eval/skillret.py`'s own quality runs use — and SHA-256-hashed the
`(ranked[:50] urn+score, injected urns)` pair per query.

**Result: 0/1000 mismatches**, at 6,006 skills — `main` and `fix/lazy-terms-postings` are
bit-identical in both ranking and selection on this frozen query set.

```json
{"n_skills": 6006, "n_queries": 1000, "mismatches": 0, "mismatch_qids": []}
```

## 4. Latency at 6,006 skills (T300/T500 gate)

Machine quiet check before measuring: `uptime` load1 `1.24` (< 2 ✓), `nvidia-smi` GPU util `2%`
(< 20% ✓) — no wait needed, single attempt. Harness: `tools/eval/skillret.py latency --n 200`
(unmodified from the prior R4 report — real `guidefold hook` subprocesses, fresh cache, page
cache warmed by one discarded call before the timed samples).

| | p50 | p95 | cold start |
|---|---|---|---|
| R4-before (baseline, prior report) | 581.8 ms | 677.3 ms | 603.8 ms |
| R4-after / R4b-before (cards+graph lazy only) | 511.3 ms | 581.2 ms | 480.3 ms |
| **R4b-after (this PR)** | **258.2 ms** | **320.5 ms** | **229.4 ms** |

**Gate check: p95 < 300ms — FAIL (320.5ms). p95 < 500ms — PASS.** A stability rerun (same quiet
machine, load1 `1.11`, GPU `0%`) gave p50 269.0ms / p95 347.5ms — consistently just over the
T300 line, comfortably under T500. This is not a fluke to chase: **it is the honest number**, and
it fails T300 by a small, repeatable margin.

## 5. T0 size curve

Deterministic subsets of SKILLRET-test — first N skills sorted by the dataset's own skill `id`
(stable, independent of node/urn construction) — via a new `--n-skills`/`--out-suffix` pair added
to `tools/eval/skillret.py latency` (defaults preserve prior behaviour exactly: `--n-skills 0` =
full corpus, `--out-suffix ""` = the canonical `skillret-latency.json`). Machine quiet before
every run (load1 stayed ≤ 1.49 throughout, well under the 2.0 ceiling; GPU util spiked to 39% once
during the 2,000-skill run with no CUDA compute process present in `nvidia-smi`'s process table
and memory flat at the ~1.7-1.9GB idle baseline — read as WSLg/Xwayland compositor noise, not a
concurrent benchmark, and CPU load1 — the metric that actually matters for this CPU-bound,
single-process harness — stayed quiet through that run).

| N skills | terms (vocab) | artifact bytes | p50 | p95 | n | T300 | T500 | load1 / GPU% at measurement |
|---:|---:|---:|---:|---:|---:|---|---|---|
| 500 | 21,784 | 1,426,703 | 91.5 ms | 113.3 ms | 100 | PASS | PASS | 0.97 / 19% |
| 1,000 | 31,627 | 2,564,324 | 107.7 ms | 134.0 ms | 100 | PASS | PASS | 1.40 / 14% |
| 2,000 | 47,707 | 4,713,208 | 138.9 ms | 188.1 ms | 100 | PASS | PASS | 1.35 / 39%* |
| 4,000 | 70,811 | 8,783,576 | 206.7 ms | 261.7 ms | 100 | PASS | PASS | 1.49 / 3% |
| 6,006 | 89,630 | 12,710,565 | 258.2 ms | 320.5 ms | 200 | **FAIL** | PASS | 1.24 / 2% |

(*39% GPU reading explained above; not treated as a disqualifying load.) Raw JSON per point:
`docs/reports/bakeoff/validation/skillret-latency-{500,1000,2000,4000}skills.json` and the
canonical `skillret-latency.json` for the 6,006 point (reused from §4's n=200 run — already
n ≥ 100).

p95 grows smoothly and roughly linearly with vocabulary size (which itself grows sub-linearly
with skill count as term reuse increases — 21,784 terms at 500 skills vs. 89,630 at 6,006, a
4.1× vocabulary growth for a 12× skill-count growth). Linearly interpolating p95 between the
4,000-skill point (261.7ms) and the 6,006-skill point (320.5ms) puts the T300 crossover at
**≈ 5,300 skills** — an interpolated estimate, not a measured point.

## 6. Artifact size at 6,006 skills

Total: 13,325,453 B (R4-after) → **12,710,565 B** (R4b-after), **-614,888 B (-4.6%)**. Component
breakdown of the two files this PR touches (measured directly, same 6,006-card in-memory Index
serialized both ways):

| file | main (old, eager dict) | branch (new, lazy directory) | Δ |
|---|---:|---:|---:|
| `terms.bin` | 1,309,620 B | 1,579,095 B | **+269,475 B (+20.6%)** |
| `postings.idx` | 1,818,951 B | 934,588 B | **-884,363 B (-48.6%)** |
| combined | 3,128,571 B | 2,513,683 B | -614,888 B (-19.7%), matching the whole-artifact delta exactly |

`terms.bin` grows: a fixed 8-byte directory record per term is less compact than a short varint
run for most real term lengths. `postings.idx` shrinks by nearly half: the old format repeated
each term's UTF-8 bytes once per field it posts to; the new format stores a term's bytes exactly
once (in `terms.bin`) and every posting entry is 8 fixed bytes regardless of term length. The net
is a clear win because postings entries (`n_entries` = Σ over fields of that field's distinct
term count) heavily outnumber terms.

## 7. What the T0 threshold is, and whether sharding is still needed below it

ADR-0024 §1's T0 gate is warm p95 < 300ms. At the real 6,006-skill SKILLRET-test corpus this PR
lands at 320.5ms (95% CI-free single-harness measurement, confirmed stable on rerun at 347.5ms)
— **still a FAIL**, though down from 581.2ms (R4-after) and 677.3ms (before either fix), a 52.7%
reduction in p95 from the original baseline. T500 passes with comfortable margin (320-350ms vs.
500ms) at every measured size. The size curve says the practical threshold is **around 5,000-5,300
skills**: every measured point at 4,000 skills and below passes T300 outright (261.7ms at 4,000,
with the smallest measured point, 500 skills, at 113.3ms — nearly 3x margin), and the interpolated
crossover sits at ≈5,300. Below that threshold, in-process sharding (ADR-0021, scoped to the
local tier) buys nothing that isn't already free — a consumer monorepo under ~5,000 skills clears
T0 today, unsharded, with this PR alone. Above it — including the 6,006-skill benchmark corpus
this programme has used throughout — sharding (or a further load-time/query-time optimization;
`load_index_artifact`'s own cost is now dominated by fixed overheads — interpreter startup,
`cards.hdr`/`norms.bin`'s O(doc-count) eager reads — rather than vocabulary, per this report's
§1-3 changes, so the next win is more likely in per-query cost or process startup than in another
lazy-load pass) is still required to bring corpora at or above roughly 5,300 skills under the T0
gate. That is unresolved by this PR and is the natural next open item.
