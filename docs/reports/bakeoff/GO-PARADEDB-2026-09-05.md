# Go + ParadeDB service: performance and retrieval reference — 2026-09-05

**Latency passes on loopback; retrieval admission fails harmful-sibling exposure.**
The complete resident SEARCH/USE API, policy, publisher and migration executable is
Go. BM25 executes in ParadeDB's Rust/Tantivy index. Docker Compose is running locally.
No GPU encoding is active in this backend. This is implementation delivery and an
explicitly requested new backend reference, not production sign-off or promotion of
ParadeDB as the admitted sparse profile. The unchanged CLI and the earlier admitted
Python sparse profile retain their existing status.

## Performance

6006 skills, the same 200 distinct frozen DEV query texts in each arm, one ready
resident API/index, four arms and 800/800 successful requests. Latencies are ms.

| Arm | Client p50 | Client p95 | Client p99 | Server p95 | OK / attempts | Over 400 ms |
|---|---:|---:|---:|---:|---:|---:|
| http_c1 | 17.159 | 21.035 | 23.291 | 19.261 | 200/200 | 0 |
| http_c4 | 19.817 | 28.395 | 35.190 | 25.188 | 200/200 | 0 |
| fresh_c1 | 96.509 | 116.866 | 137.944 | 20.213 | 200/200 | 0 |
| burst_fresh_c4 | 117.694 | 137.548 | 146.762 | 24.335 | 200/200 | 0 |

All four arms also had zero requests above 300 ms. The new service protocol's
whole-client p95 <=400 ms and server-side p95 <=300 ms gates pass at c1 and c4.
600 paired query responses have identical ranking/selection hashes across arms.
This establishes determinism within `paradedb_bm25_v1`, not rank parity with Python
BM25F. HTTP errors and non-200 attempts would remain in the denominator.

HTTP arms open a new TCP connection per request. Fresh arms start a new Python 3.12
stdlib HTTP client for every request; the timer includes process startup/imports,
reading the token file, authentication, connection, response parsing and process
exit. Burst c4 launches four fresh clients together, then proceeds to the next group.
The server header covers HTTP admission, auth/validation, queues, retrieval, policy,
response serialization and synchronous diagnostic logging; socket transmission is
covered by the client timer. Ten warmup requests are separate from the 800 measured.
The source query file, DEV split, selected IDs, text hash and snapshot are recorded.
No qrels are used for this latency workload.

Environment: Windows host, Ubuntu 24.04 / WSL2, Docker Desktop, 16 visible CPUs,
Linux 6.18.33.2, PostgreSQL 17 / pg_search 0.25.6. Resources were not isolated from
other local activity. This measures SEARCH on loopback, not installed harnesses,
WAN/TLS/IAM, USE load, high concurrency saturation or production availability. The
service index is warm; fresh *server* startup and peak memory were not benchmarked.
The 26-skill smoke suite verifies startup/recovery and USE correctness separately.

Runtime source was frozen before quality evaluation, on base commit
`ecf53fba4ac4434e48436711068f38e0a072aed2`; source hashes identify the then-uncommitted
implementation. Final API image digest:
`sha256:2e03741b7302523326794396590debde89c903d12557983d4434d7da65263a44`.
The final artifact also records the ParadeDB digest and environment.

### What made it fast

The initial SQL path fetched/filter-scanned about 2867 rows and measured c1 p95
593.88 ms / c4 810.95 ms. Removing the redundant per-URN predicate when every card
was admissible was insufficient alone. Indexing exact metadata as `pdb.literal`
removed heap filtering; using bytewise `urn COLLATE "C"` allowed Top K execution.
The final smoke EXPLAIN confirms `TopKScanExecState` and a limit of 50. Routing
metadata/negative phrases are cached, and the Go API uses a bounded pgx pool.
The gain is a combined index/query/runtime change, not an isolated Python-vs-Go test.

A separate correctness fix gives every tenant/repository/snapshot its own physical
BM25 index. Filtering a global index does not isolate IDF: publishing an unrelated
repository or old snapshot would otherwise change another catalog's ranks. The
smoke test explicitly verifies publication of unrelated content leaves ranks intact.

Intermediate engineering runs are retained locally. They are not the final result:
a global-index run measured c1/c4 26.20/33.05 ms; an isolated-index run before full
telemetry measured 20.22/22.69 ms; a full-telemetry run that read the client token in
the parent measured 21.11/24.24 ms and fresh c1/c4 122.69/139.90 ms. The table above
uses the final runtime and includes token-file I/O inside each fresh process.
No retrieval configuration was changed after test labels were evaluated.

## Skill matching quality

One configuration, zero label-based tuning, once on DEV, test-A, test-B and the
regression fixture. Both arms use the same pinned cards, nodes, weights and queries.
F0 is the unchanged local CLI with `w_dense=0`. The new engine uses default ParadeDB
BM25 over concatenated name/description/digest/triggers/body, then the shared-policy
Go port. Public corpora use `_root`, never a gold-derived scope; regression uses its
authored scope. Quality requests run through real HTTP/SQL. All 6862 requests returned
200, with the expected immutable snapshot and no labels sent to the service.

The table reports **F0 / ParadeDB**. Existing official metrics condition on answered
queries. hit@1 and graded nDCG@10 use retrieval order; all_required@4 uses the actual
selected injection. A good top result does not imply a complete bundle.

| Dataset | Queries / skills | Answered answerable F0 / Parade | hit@1 % | graded nDCG@10 | all_required@4 % |
|---|---:|---:|---:|---:|---:|
| dev | 1000 / 10123 | 1000 / 1000 | 71.30 / 76.30 | 0.6104 / 0.6518 | 30.00 / 32.60 |
| test_a | 4392 / 6006 | 4392 / 4392 | 38.25 / 46.79 | 0.3850 / 0.4537 | 27.00 / 32.38 |
| test_b | 1250 / 501 | 1200 / 1250 | 38.00 / 44.40 | 0.4635 / 0.5387 | 37.50 / 42.32 |
| regression | 220 / 26 | 174 / 174 | 84.48 / 85.63 | 0.8785 / 0.8830 | 81.61 / 82.76 |

DEV is developmental evidence, and Meridian is regression evidence only. The
regression set has 220 queries, of which 174 are answerable; both arms answer all
220, so its abstention recall is zero. It cannot establish real-corpus quality.

**The blocker is test-B HSR@4: 39.67% -> 50.33%, +10.67 pp**, paired 95% bootstrap
CI **[+5.33, +15.33] pp**, on the same 300 labelled distractor queries. The maximum
allowed regression is +1.00 pp. This fails regardless of the positive headline
metrics and remains a failure after excluding the impossible-budget stratum.
Test-A has no distractor labels; its HSR is null, not zero or a pass.

Paired 95% bootstrap CIs use 1000 resamples of query IDs (seed 0):

| Dataset / common answered cohort | hit@1 delta pp | graded nDCG@10 delta pp | all_required@4 delta pp |
|---|---:|---:|---:|
| DEV, n=1000 | +5.00 [3.30, 6.80] | +4.14 [3.28, 5.01] | +2.60 [1.50, 3.70] |
| test-A, n=4392 | +8.54 [7.60, 9.47] | +6.87 [6.41, 7.33] | +5.37 [4.69, 6.08] |
| test-B, n=1200 | +7.92 [5.75, 10.08] | +8.98 [7.50, 10.47] | +5.92 [3.92, 8.00] |

### Test-B denominators and limits

F0 abstains on 50 Korean-language queries; ParadeDB answers all 1250. Consequently,
subtracting the official full-table means does not equal the paired delta on the
1200 commonly answered queries. As a separately labelled diagnostic, counting empty
results as misses on **all 1250 answerable queries** gives hit@1 36.48% -> 44.40%,
graded nDCG@10 0.4449 -> 0.5387, and all_required@4 36.00% -> 42.32%. HSR still uses
the same 300 labelled cases and does not change. The existing metric functions and
official answered-only results have not been redefined.

The predeclared budget_constrained stratum has 200 queries requiring 25 skills,
which cannot fit a four-card answer. All 200 remain in the full report. Excluding
only this stratum for the completeness view gives 45.00% -> 50.38% on the official
answered cohorts (F0 1000/1050, ParadeDB 1050/1050); the common-answered paired delta
is +7.10 pp [4.60, 9.80]. This does not rescue the harmful-exposure gate.
The stale/adversarial stratum also regresses: all_required@4 72.67% -> 66.00%.

The existing converter drops 1044 Korean trigger phrases, but retains every query:
151 contain Hangul. No gold or distractor URNs are missing. That limitation is shared
by both arms and recorded in the JSON, rather than changing the corpus for this run.
Default ParadeDB Unicode analysis and body concatenation are part of the new variant;
this is not a controlled experiment isolating any one of those choices.

## Validation and evidence

- 663 Python tests passed after merging the latest main; fixture validation, golden
  regression gate and fresh `index --check` passed. The shipped CLI source is unchanged.
- Go race tests and vet passed. 144 deterministic policy conformance cases are
  regenerated from the unchanged CLI, including scope, negative triggers, dependency
  closure, PageRank, abstention and selection caps. This is policy conformance, not
  exact parity between different retrieval engines.
- Real Docker Compose smoke: 39 checks including 40 concurrent requests. SEARCH/USE
  schema 1.1 and legacy requests, monorepo context, loaded revisions, budgets, exact
  NUL-containing body/checksum, atomic/idempotent publication, rank isolation,
  read-only SQL role, redacted diagnostics, DB failure/recovery and API restart pass.
- A second install from an empty database caught a bootstrap readiness race. The
  Compose healthcheck now waits for TCP, not the temporary init socket. Fresh deploy
  and all 39 smoke/recovery checks then passed. The rebuilt image has byte-identical
  Go binary, contract and policy source to the measured container; the image manifest
  digest changes on rebuild. The original smoke evidence and this follow-up are both retained.
- Every saved quality aggregate and paired CI was recomputed from saved rank lists,
  without new HTTP/model calls. All aggregates match exactly.

Artifacts: [protocol](validation/go-paradedb-protocol-v1.json),
[latency with per-query timing/hashes](validation/go-paradedb-latency.json),
[smoke](validation/go-paradedb-smoke.json),
[admission decision](validation/go-paradedb-admission.json),
[evidence SHA-256 manifest](validation/go-paradedb-evidence-manifest.json).
Quality JSON: [DEV](validation/go-paradedb-quality-dev.json),
[test-A](validation/go-paradedb-quality-test_a.json),
[test-B](validation/go-paradedb-quality-test_b.json),
[regression](validation/go-paradedb-quality-regression.json).
Sibling `*-ranks.jsonl.gz` files retain per-query F0 and ParadeDB ordering, selected
URNs, revisions and status without copying query text or skill bodies. Corpus
revisions, conversion details, source and case hashes remain in the quality JSON.
Reproduction commands are in the [runbook](../../../services/search/README.md).

## Decision and next work

Mergeable implementation evidence is separate from retrieval adoption. The Go API,
ParadeDB publication and Compose deployment can be reviewed and exercised locally;
`paradedb_bm25_v1` must not replace the admitted profile based on these results.
No default client routing was changed. Further relevance work returns to DEV and
must respect the programme's spent-family/multiplicity rules; repeatedly tuning on
test-A/B to erase this failure is not allowed.

The [GPU serving proposal](DENSE-SERVING-NEXT-2026-09-05.md) explains the next dense
experiment and its independent correctness, latency and quality questions. Kubernetes,
production IAM/TLS, HA/backup/restore, index retention and durable E6.4 telemetry remain
separate follow-ups. Diagnostic SEARCH/USE logs are not an observed-use event ledger.

### Post-benchmark compatibility with main telemetry (PR #49)

Before final CI, main merged CLI telemetry and changed its full source SHA from
`75f8884e56b4551cbf9c0e922d068f74b50cff5d2f96d2e7c278957fc6dfcacd` to
`8a0795d31c993a9d1cd76015a413856e1b3d3b826ea326a8f19e57feabe02c4e`.
Only existing definitions `cmd_find`, `cmd_load`, `cmd_hook` and `main` changed;
`Index`, `Router` and all other existing definitions have identical ASTs. All 144
regenerated policy cases are identical except for the source SHA header. The Go
runtime source is unchanged. The conformance fixture now tracks main, while the
measurements above retain their original CLI/snapshot/image identities. No test
corpus was rerun or result relabelled. CLI spool/ledger tooling now exists on main;
Go diagnostic logs still do not constitute integration with that durable ledger.
