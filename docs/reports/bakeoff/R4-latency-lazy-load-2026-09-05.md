# R4: lazy artifact load — hook latency at 6,006 skills

2026-09-05. Machine: WSL2, Intel Core i7-10700K @ 3.80GHz, 16 threads, CPython 3.12.3, glibc 2.39
(Ubuntu). All latency numbers below are genuinely fresh `guidefold hook` subprocesses (never an
in-process call) — the real Claude Code / Codex hook invocation model — measured before and after
on this same machine, in this session, using the existing harnesses (`tools/eval/skillret.py
latency` for 6,006 skills, `tools/eval/skillretbench.py latency` for 501, `tools/eval/
measure_hook_latency.py` for 26 — none written or modified for this fix; all three already existed
on `main` before this branch).

## Verdict, first

**T300 not met at 6,006 skills. T500 not met either.** p95 went from 639ms (original bug report)
/ 677ms (this session's fresh "before" rerun) to 581ms after this fix — a genuine ~50-90ms
improvement, but still short of the 500ms tier, let alone the 300ms one. Both 501-skill and
26-skill scales were already comfortably under 300ms before this fix and remain so after.

The fix's four numbered requirements (lazy cards, lazy graph, cut import cost, unchanged
reproducibility) were implemented correctly and delivered the saving they targeted — profiling
below shows the R4-owned portion of `load_index_artifact` (cards + graph) shrank from ~46ms to
~7ms at 6,006 skills. But that was never the dominant cost. The dominant cost — eager parsing of
`terms.bin` (idf) and `postings.idx` (postings offsets), **pre-existing, untouched by R4, out of
its four numbered requirements** — is roughly 5x larger and scales with vocabulary size (89,630
distinct terms at 6,006 real skills), not doc count. An honest 581ms with this breakdown is worth
more than a claim of having closed the gate.

## 1. Whole-hook latency, before/after, at three corpus sizes

Each row is a full fresh-interpreter subprocess (`python3 startup + import + hook logic`) — there
is no long-lived warm process in this design, so this is the real cost a harness pays on every
prompt.

| Corpus | n | p50 before → after | p95 before → after | cold before → after |
|---|---|---|---|---|
| 26 (Meridian fixture) | 220 | 77.0 → 68.2 ms | 92.4 → 82.9 ms | not isolated by this harness (n/a) |
| 501 (SkillRetBench) | 220 | 134.9 → 113.9 ms | 158.2 → 129.7 ms | not isolated by this harness (n/a) |
| 6,006 (SKILLRET-test) | 200 | 581.8 → 511.3 ms | 677.3 → 581.2 ms | 603.8 → 480.3 ms |

Gate check at 6,006 (the only scale the programme's cost gate applies to, DENSE-PROGRAM.md §5):
**p95 300ms — FAIL (581.2ms). p95 500ms — FAIL (581.2ms).** Both failed before this fix too
(677.3ms); this fix narrows the miss but does not close it.

Only `tools/eval/skillret.py latency` (6,006-skill harness) isolates a true cold-start sample (1
cold + 1 warm-up + n timed, per its own protocol); the 26- and 501-skill harnesses both do a single
throwaway warm-up before their timed loop, so every one of their samples already has the artifact
in the OS page cache — there is no cold figure to report at those two scales without changing
harnesses this task explicitly says not to touch.

The original bug report's numbers (p50 561ms/p95 639ms/cold 585ms) predate this session's fresh
"before" rerun (581.8/677.3/603.8) — both are the same code, the difference is ordinary
run-to-run variance on this machine, not a discrepancy in the fix.

## 2. Peak RSS memory, before/after (`/usr/bin/time -v`, one hook invocation each)

| Corpus | RSS before | RSS after | Δ |
|---|---|---|---|
| 26 | 26,420 KB | 22,392 KB | -4,028 KB (-15.2%) |
| 501 | 37,260 KB | 31,964 KB | -5,296 KB (-14.2%) |
| 6,006 | 93,316 KB | 82,704 KB | -10,612 KB (-11.4%) |

Memory scales with corpus size in both variants (as expected — `idf`/`field_norm`/postings-offset
dicts are still fully materialized in both), and the fix reduces it by a consistent ~11-15% at
every scale — the direct effect of no longer building one Python dict entry per card and one
adjacency-list entry per graph node on every hook invocation.

## 3. `-X importtime` — CLI's own interpreter-import cost

| | before | after |
|---|---|---|
| total self time, all imports | 35.597ms | 23.280ms |

Top self-time contributors moved from `json.encoder`/`_hashlib`/`argparse`/`enum` (before) to
`signal`/`site`/`ipaddress`/`enum` (after) — consistent with heavy imports (hashlib-backed
checksum verification, JSON encoding machinery) having moved out of the always-imported path and
into the commands that actually need them, leaving the hook path's own import graph smaller. This
is bounded below by CPython's own ~20ms interpreter-startup floor (confirmed in a prior session,
not chased further per this task's own instruction not to optimize below ~40ms).

## 4. Artifact size

| Corpus | before | after | Δ |
|---|---|---|---|
| 26 | 132,323 B | 126,837 B | -5,486 B (-4.1%) |
| 501 | 1,923,287 B | 1,793,768 B | -129,519 B (-6.7%) |
| 6,006 | 14,882,560 B | 13,325,453 B | -1,557,107 B (-10.5%) |

At 6,006 skills: `cards.jsonl` (4,170,972 B) is kept on disk unchanged — other tooling still reads
it, and `cards.idx`'s offsets point into it — but is no longer parsed by the hook path. `graph.json`
(2,429,981 B) is dropped entirely; `graph.bin`+`graph.idx` (24,024 + 48,052 B) replace it, a >97%
size cut on that file, since reproducibility only requires the binary form to be reconstructible,
not a JSON mirror on disk (ADR-0021's 15MB budget forced exactly this call). `cards.idx`
(48,052 B) + `cards.hdr` (752,492 B) are new. Net: artifact shrinks even though two small new
header files were added, because `graph.json`'s removal dominates.

## 5. `load_index_artifact` component breakdown at 6,006 skills — where the time actually goes

This is the measurement that explains section 1's modest improvement. Breakdown by file/section,
`timeit()`-style, isolating each parse step of `load_index_artifact` before and after this fix,
against the same 6,006-card Index built from `tools/eval/skillret.py`'s corpus:

| Section | Before | After |
|---|---|---|
| `cards.jsonl` full parse (every doc → dict) | ~38.5ms | — (removed; lazy, mmap) |
| `graph.json` full parse | ~7.9ms | — (removed; file no longer exists) |
| `cards.hdr` parse | — | ~4.7ms |
| `cards.idx` parse | — | ~0.9ms |
| `graph.idx` parse | — | ~0.9ms |
| **R4-owned subtotal** | **~46.4ms** | **~6.5ms** |
| `terms.bin` (idf) + `postings.idx` (offsets), both eager, both pre-existing, both untouched | ~274.7ms | ~264.3ms |
| **Total `load_index_artifact`** | **~321.1ms** | **~270.8ms** |

R4's fix removed almost exactly what it targeted (~40ms, matching section 1's whole-hook delta
within measurement noise) — but that portion was never more than ~15% of `load_index_artifact`'s
total cost at this corpus size. `terms.bin`+`postings.idx` — a per-term IDF dict and a
`(field,term)→(offset,length)` dict, both parsed whole in a Python loop, both pre-existing and
outside this fix's four numbered requirements — is the true dominant cost, and it scales with
**vocabulary size** (89,630 distinct terms across `Index.FIELDS`'s 5 fields at 6,006 real skills),
not doc count. A separate, also pre-existing cost sits at query time rather than load time:
`_LazyFieldPostings.get()` decodes a term's postings list via varint on every lookup, so per-query
BM25 scoring cost also grows with how many documents share common terms as the corpus grows —
unaffected by any load-time fix.

**Methodology note on precision:** the table above reproduces the clean sample taken earlier in
this session. A same-session repeat attempt, made while writing this report, landed during a
period of severe, unrelated CPU contention on this shared machine (load average 25-30 on this
16-thread box, from other concurrently-running background jobs) and produced grossly inflated,
internally-inconsistent numbers (`FULL load_index_artifact` samples up to 2,960ms) unsuitable for
reporting; those samples are discarded rather than included. The *structural* finding — cards/
graph now cost single-digit milliseconds either way, `terms.bin`/`postings.idx` dominate by a wide
margin — held in every sample taken, contended or not; only the absolute millisecond figures above
come from the clean run.

At 501 skills, the same `load_index_artifact` call (measured directly, not inside a subprocess)
went from a 57.5ms median to a 45.1ms median across 10 repeated in-process calls against a real
`guidefold index`-built artifact — consistent in direction and rough magnitude with the whole-hook
delta at that scale (134.9→113.9ms p50, of which interpreter startup + CLI import is the other
large fixed component).

## 6. Reproducibility — unchanged, verified

- **Byte-identical rebuild across fresh interpreters**: `test_index_artifact.py::
  test_index_artifact_bytes_are_identical_across_two_fresh_interpreter_builds` runs `guidefold
  index` as two genuinely separate subprocesses (each with its own random `PYTHONHASHSEED`,
  confirmed unset in this environment) and diffs every file byte-for-byte, including the new
  `cards.idx`/`cards.hdr`/`graph.bin`/`graph.idx`. This is the empirical backstop for the audited
  claim that no hash-order-dependent iteration (e.g. `Index._build_bm25`'s per-document
  `doc_terms = set()`) leaks into serialized bytes.
- **`index --check` still detects tampering, including the new files**: `cards.idx`, `cards.hdr`,
  `graph.bin`, `graph.idx` all flow through `_serialize_artifact_files`'s generic per-file
  `hashlib.sha256` loop into `manifest.json`'s `checksums`, exactly like every pre-existing file —
  so `check_index_artifact`'s tamper detection covers them for free, not as a special case.
  `test_check_index_artifact_detects_a_tampered_file_on_disk` (tampers `graph.bin`) and
  `test_check_index_artifact_detects_a_tampered_cards_idx` (tampers `cards.idx`) both assert this
  directly; staleness detection (`test_check_index_artifact_fails_on_a_deliberately_stale_artifact_
  then_passes_after_rebuild`, `test_index_check_subprocess_fails_stale_then_passes_after_rebuild`)
  is unaffected since it works the same way regardless of which files exist.
- **Sorted-URN order preserved everywhere**: `cards.hdr` and `cards.idx`/`graph.idx` are all built
  by iterating `doc_urns = sorted(idx.cards.keys())`, the same order every other artifact file
  uses (`test_cards_hdr_header_table_is_in_sorted_urn_order`).
- **PYTHONHASHSEED determinism**: covered by the same fresh-interpreter-pair test above; this
  environment runs with `PYTHONHASHSEED` unset (randomized per-process) by default, so the test is
  non-tautological.

Full suite: 390 tests, 0 failures, 0 skips (`pytest -q`, this branch, after rebasing onto
`origin/main`).

## 7. Artifact layout change (see `docs/DESIGN.md` §7 for the full table)

`graph.json` removed. `cards.idx`, `cards.hdr`, `graph.bin`, `graph.idx` added. `cards.jsonl`
stays on disk (unchanged bytes) but is no longer eagerly parsed — `load_index_artifact` now reads
it lazily via mmap, one byte-range per card, only when a card is actually materialized. The
`load_index_artifact` docstring was corrected: it previously described `idf`/`field_norm` as
"small" alongside the genuinely-small per-doc header tables; section 5 above shows that claim is
false at real-corpus vocabulary sizes, and the docstring now says so plainly, with a pointer to
this report.

## 8. What's next (not this PR)

The natural follow-on ("R5", informal name) is making `terms.bin`/`postings.idx` lazy — but unlike
cards/graph, term lookups are by string, not by doc-id, so the doc-id-offset-table pattern used
here (`cards.idx`/`graph.idx`) does not directly transfer; it needs an on-disk structure searchable
by term (e.g. a sorted term list with a binary-searchable offset table, or a small on-disk hash
index). That is a materially larger design change than this PR's header-table approach, and is
explicitly out of scope for R4's four numbered requirements. Per-query `_LazyFieldPostings.get()`
decode cost (the other ~150-220ms/query component visible in earlier profiling) is a related but
separate query-time cost that any such redesign should also address.
