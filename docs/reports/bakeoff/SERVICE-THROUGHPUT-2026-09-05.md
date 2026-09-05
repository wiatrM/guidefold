# Service throughput: ordered event batches and bounded GPU shadow

**Date:** 2026-09-05. **Decision:** adopt prepared/pipelined event INSERTs and
compact request-local sparse preparation with a configurable 128-job shadow queue.
Keep one request per TEI forward. Do not change vector storage or retrieval quality
settings. **Production admission: false.**

The repeated event-ingest measurements improved new-event throughput from
3.7–3.9k to 15.7–16.0k events/s at c=1, and from 7.2–7.9k to 26.3–28.2k at c=2.
The final 200-request shadow burst retained 200/200 comparisons at c=4, versus
96/200 before. It retained 189/200 at c=8: the observational queue can still overflow.
All foreground rankings matched the sparse control. This is an engineering result,
not evidence that dense generalizes to another tenant's skills.

## Scope and reproducibility

Base commit: `2fd9645` (merged PR #58), CLI SHA-256
`8a0795d31c993a9d1cd76015a413856e1b3d3b826ea326a8f19e57feabe02c4e`.
The API remains Go, canonical integer BM25F, Postgres and API 1.1. Neither the CLI,
corpora, quality thresholds, RRF weights nor 300/400 ms latency budgets changed.
GPU remains an optional shadow profile. Checkpoint, TEI digest, FP16 formatter,
last-token pooling and batch=1 identities remain those in
[GPU-SERVICE](GPU-SERVICE-2026-09-05.md).

All runs used the same shared WSL2 / Docker Desktop host and RTX 4090. Resources
were not isolated. Builds, indexing and performance arms were run sequentially.
These are short local measurements, not a capacity forecast or a sustained-load SLO.
Nearest-rank p95 uses 30 HTTP batches per telemetry arm and 200 SEARCH requests per
latency/coverage arm. Repetitions are retained rather than selecting the fastest run.

The [manifest](validation/service-throughput/manifest.json) contains readable
summaries, final Go source hashes, image IDs, denominators and SHA-256 digests.
Every original JSON artifact is preserved byte-for-byte in a deterministic gzip
file beside it; decompress with Python `gzip.open` or `gzip -dc`. Raw artifacts
contain synthetic events, public-corpus query IDs, hashes, timings and query plans,
without raw query/skill bodies or local secrets. Earlier 300 ms and GPU reports
remain unchanged.

`source_commit` in a diagnostic identifies its checkout base, not a claim that an
uncommitted candidate image equals that commit. Image IDs and final source hashes
identify the tested binary. The final image is
`sha256:8d378985742f090beba5f900da7ffdd1d3363c2e9c4e169f02bf3ab2c232483d`.

## Event ingest

Previously each event INSERT waited for its own PostgreSQL round trip. The new
path validates events, prepares one statement per pooled connection, and sends the
ordered INSERTs as one pgx protocol batch within the existing transaction. It reads
every command result and closes the batch before committing and returning ACK.

This preserves `(tenant_id, event_id)` idempotency, partial validation rejection,
ACK ordering and first-payload-wins behavior for duplicates within one batch. A
storage failure after an earlier INSERT rolls back the entire transaction and
returns no false accepted IDs. No schema, retention or report semantics change.

Workload: 500 synthetic `task_started` events per HTTP batch, five warmup batches,
30 batches per arm. Every insert arm accepted 15,000 events; every replay arm
accepted zero and acknowledged 15,000 duplicates. Every arm had 30/30 HTTP 200,
zero rejections and zero lost ACKs.

| Run | insert c1 p95 / events/s | insert c2 p95 / events/s | replay c1 p95 | replay c2 p95 |
|---|---:|---:|---:|---:|
| A: baseline | 182.313 ms / 3,856 | 133.899 ms / 7,862 | 114.940 ms | 172.838 ms |
| B: pipeline, unprepared | 54.413 ms / 10,131 | 56.751 ms / 18,940 | 56.252 ms | 47.000 ms |
| C: final prepared pipeline | 32.512 ms / 16,015 | 39.691 ms / 28,180 | 22.582 ms | 30.219 ms |
| D: baseline repeated | 185.013 ms / 3,683 | 189.054 ms / 7,184 | 124.806 ms | 124.741 ms |
| E: final repeated | 34.392 ms / 15,676 | 67.771 ms / 26,274 | 33.356 ms | 26.860 ms |

These are descriptive measured ratios, without a throughput confidence interval.
Per-request rows, including the slower c2 tail in repeat E, are in the artifacts.

## Shadow reuse, coverage and foreground cost

The foreground request now captures compact admissibility masks and full BM25 ranks
before its unchanged top-50 truncation. Its own shadow reuses this preparation,
bound to the query digest, snapshot and scopes. Fusion retains full lexical ranks
for dense candidates beyond the lexical top 50. No cross-request query cache is
introduced and no encoder call moves onto the foreground response path.

Masks plus rank arrays require five bytes per catalog document per scope. At 6006
documents and four scopes, 128 waiting jobs use approximately 14.7 MiB for those
arrays, plus top candidates, payloads, catalog references and runtime overhead.
This is an allocation estimate, not a measured RSS bound for arbitrary catalogs.
The limit is 128 jobs by default, configurable from 1 to 256; four workers and
all existing deadlines remain unchanged.

For each run the harness first takes 200 sparse-control responses, then enables
shadow and sends the same 200 queries at c=4 and c=8. It records each `search_id`,
waits for draining, and counts persisted successful/error/missing comparisons.
The stable-count timeout is four seconds, with a 35-second maximum wait. This is
burst coverage, not durable delivery. Recorded queue time is additional shadow
observation delay; it is not included in the foreground SEARCH latency.

| Run / c | SEARCH client p95 | shadow OK / error / missing | shadow queue p95 |
|---|---:|---:|---:|
| baseline, batch=1 / 4 | 46.667 ms | 96 / 0 / 104 | 745.698 ms |
| baseline, batch=1 / 8 | 75.040 ms | 72 / 0 / 128 | 969.035 ms |
| baseline, batch=4 / 4 | 61.941 ms | 106 / 7 / 87 | see artifact |
| baseline, batch=4 / 8 | 67.055 ms | 71 / 0 / 129 | see artifact |
| initial full-object reuse, batch=1 / 4 | 84.715 ms | 114 / 0 / 86 | 919.363 ms |
| initial full-object reuse, batch=1 / 8 | 77.631 ms | 72 / 0 / 128 | 979.487 ms |
| final compact reuse, queue=128 / 4 | 96.039 ms | 200 / 0 / 0 | 2615.583 ms |
| final compact reuse, queue=128 / 8 | 137.447 ms | 189 / 0 / 11 | 2527.874 ms |

Every row attempted and received 200/200 successful SEARCH responses, with zero
ranked/selected hash mismatches against that run's sparse control. In historical
raw shadow diagnostics, `passed: true` means foreground HTTP/parity passed; it does
not mean complete shadow coverage. The current runner names those outcomes separately.

The final c4 burst completed all comparisons, while doing more background work and
increasing foreground p95 from 47 to 96 ms in these runs. It is a coverage/latency
tradeoff within the budget, not a demonstrated foreground speedup. Queueing also
increased shadow observation age to about 2.6 seconds p95. At c8, 11 missing records
remain visible in the denominator. Sustained arrival rates above worker capacity
will still overflow; this queue cannot replace the durable client event spool.

The initial noncompact reuse experiment did not establish an end-to-end speedup.
TEI batch=4 produced seven shadow errors in c4 and did not improve c8 coverage, so
it was rejected. Batch=1 stays configured. No neural relevance weights were tuned.

## Final latency and correctness gates

The established latency harness ran the same 200-query / 6006-document workload in
four arms with the final image, sparse responses, shadow enabled, queue=128 and
TEI batch=1. This is a separate run from the coverage diagnostic above. Different
observed times on the shared host are not used as a paired speedup claim.

| Arm | HTTP OK / attempted | client p95 | server p95 |
|---|---:|---:|---:|
| HTTP c1 | 200 / 200 | 31.690 ms | 29.815 ms |
| HTTP c4 | 200 / 200 | 46.997 ms | 44.803 ms |
| fresh process c1 | 200 / 200 | 140.561 ms | 25.464 ms |
| fresh burst c4 | 200 / 200 | 179.628 ms | 37.374 ms |

All four client <=400 ms and server <=300 ms gates passed. None of these 800
requests exceeded 300 ms. All 600 paired ranked/selected hashes matched. Server
configuration and the final image were separately verified; the latest 810 shadow
records after this run were all successful. That aggregate is a health check, not
a per-search coverage assertion for this harness (it does not store search IDs).

Validation of the final implementation:

- 731 Python regression tests passed; fixture validation and the 220-case golden
  regression check passed without a change to the committed baseline.
- Go race tests and vet passed, including full-channel-rank fusion and preparation
  isolation tests. A fixed-response unit test checks byte-exact delivery before enqueue.
- The same ledger assertions passed 34 SQLite/Postgres cases. Fault injection,
  concurrent replay, tenant isolation, retention and database/API restart passed.
- Actual CLI fixture cycle: 20 find + 5 load commands, 210 events accepted, replay
  zero accepted / 210 duplicate; Postgres and SQLite reports equal.
- GPU fixture integration: 12 concurrent SEARCH responses preserve all stable
  response fields, immutable snapshots and USE checksums. Client `search_results`
  and load events join by tenant/search_id. Sparse remains ready and returns the
  same stable response during GPU outage; worker recovery passed. The test also
  verifies preparation reuse. Fresh UUIDs/timings are excluded across separate requests.
- Independent 1000-query HTTP-to-CLI parity: 1000/1000 HTTP 200, zero
  mismatches, `exact_output_parity_passed: true`. This checks top-10 URNs/integer
  scores, ordered selected URNs and immutable revisions on frozen DEV queries;
  it is not another quality treatment.

## Vector layout investigation: not deployed

The pgvector documentation notes that out-of-line storage is not accounted for by
the planner and describes inline storage as an option. This motivated a bounded
physical-layout probe, not an assumption that a database migration would help.
[Primary source](https://github.com/pgvector/pgvector#why-isnt-a-query-using-a-parallel-table-scan).

Both arms copied only one 6006-vector public benchmark snapshot into temporary
session-local tables, dropped at transaction end. The original table and its
statistics were unchanged. Thirty alternating paired iterations used one fixed
stored vector and the same exact cosine/rank query. All returned ranks matched.

| Paired probe | external p95 | inline p95 | total external / inline bytes |
|---|---:|---:|---:|
| STORAGE PLAIN, target=2048 | 49.800 ms | 67.772 ms | 37,601,280 / 54,624,256 |
| STORAGE PLAIN, target=6144 | 54.681 ms | 39.713 ms | 37,601,280 / 51,232,768 |

Plain storage alone was slower and is rejected. A 6144-byte tuple target reduced
p95 in this probe, with about 36% more storage. Temporary-table buffer behavior,
a single query vector and fresh physical layout prevent extrapolation to service
latency or other queries. A dedicated persistent-table A/B test with snapshot
publication/rollback and concurrency would be needed before adopting it. No live
embedding rewrite, schema migration, ANN index or scoring change is included.

## Remaining release work

Dense's independent test-B result and quality admission remain unchanged. DEV
SKILLRET queries come from its train partition and cannot prove generalization.
T1 clean-VM installation/reboot, separate backup restoration, authenticated E2.6
client transport, target-network behavior and production capacity are still separate
acceptance work. This change improves event collection and burst observability;
it does not close those gates or claim Kubernetes/production readiness.
