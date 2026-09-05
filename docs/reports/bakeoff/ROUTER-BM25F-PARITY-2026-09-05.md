# Reference BM25F in Go/Postgres — parity repair, 2026-09-05

The default native SEARCH now matches the unchanged CLI BM25F Router: **0 / 1,000
DEV query mismatches** through HTTP, including top-10 integer scores/order, selected
skill order and exact card revisions. The prior Tantivy experiment remains explicit
and unadmitted; its test-B HSR failure is not relabeled or waived.

## Implementation and decision

ADR-0026 selects hosting (Go/Postgres/Compose), not another default scorer. The CLI
exports the authoritative rounded IDF, field norms and postings. Go compiles the
same fixed-point BM25F per-term contributions with arbitrary-precision intermediates;
Postgres stores packed per-term postings per immutable tenant/repo/snapshot. Go
reads matching terms, sums query-frequency-weighted contributions, filters scope and
negative triggers before top-50, and applies the existing integer policy/selection.
There is no Tantivy top-k bottleneck on this path. The API does not cache bodies.

Publication validates index/snapshot/CLI identities and commits index, cards and head
atomically. Existing snapshots lacking a canonical router index fail readiness until
re-published. No implicit fallback changes the ranker. `GUIDEFOLD_LEXICAL_ENGINE`
defaults to `router`; `paradedb-experimental` is opt-in reproduction only.

## Parity evidence

- Frozen SKILLRET-train DEV: 1,000 queries, 10,123 documents, c=4; 1,000/1,000 HTTP 200.
- Top-10 URN plus integer score mismatches: 0; selected ordered URN mismatches: 0;
  exact card revision mismatches: 0. The CLI source SHA is recorded in the JSON.
- The first comparator compared CLI `select()` card objects with API URN strings.
  The corrected comparison projects both to ordered URNs. It was recomputed from
  the same saved 1,000 CLI results and HTTP responses, with no service/output change
  or additional requests. The original capture hash and correction are recorded.
  The permanent runner is fixed, and CI runs the real HTTP comparison anew.
- No test-A/test-B query evaluation or new quality tuning was performed. This is an
  equivalence gate, not a new favorable quality trial or GPU admission.
- 54 independent CLI-generated fixtures compare complete BM25F score maps, including
  repeated query terms, field weighting, normalization, Unicode, filtering, zero
  weights and weights of 1,000,000. Existing 144 policy fixtures remain in place.

## Loopback latency

Same 200 frozen DEV texts per arm, 6,006 public documents, 10 warmups. The process
start arms include imports, token-file read, TCP/HTTP, parsing and exit. Every HTTP
request opens a new connection; no query cache. Environment is WSL2/Docker Desktop,
shared host, not isolated production infrastructure.

| arm | client p95 ms | server p95 ms | OK |
|---|---:|---:|---:|
| HTTP c1 | 21.623 | 19.827 | 200/200 |
| HTTP c4 | 29.079 | 27.191 | 200/200 |
| fresh process c1 | 115.811 | 20.614 | 200/200 |
| burst fresh process c4 | 135.636 | 26.080 | 200/200 |

All 800 requests stayed below 300 ms; p95 client <=400 ms and server <=300 ms pass
in all arms. All 600 paired cross-arm ranked/selected hashes match. These are new
BM25F measurements; the old Tantivy numbers remain unchanged. WAN/TLS/IAM and
production scale are separate gates. Cold model startup is irrelevant to this sparse
path; this run does not claim cold service/index-build or saturation measurements.

## Validation and remaining work

Go race tests and vet pass. Full Python pytest passes (exit 0). Real Compose smoke:
39 checks, 40 concurrent requests, database/API stop and recovery, immutable USE,
failed publication and reactivation, repository isolation, read-only database role.
CI regenerates policy and BM25F fixtures and runs the 1,000-query parity gate.

GPU work is separate: TEI FlashQwen3 was numerically checked against PyTorch and
shows promising encoder latency. This repair does not enable GPU or claim hybrid
quality. Production IAM, telemetry integration, WAN and Kubernetes remain separate.

Evidence: [parity](validation/router-bm25f-parity.json),
[per-query hashes](validation/router-bm25f-parity-rows.jsonl.gz),
[latency](validation/router-bm25f-latency.json),
[Compose smoke](validation/router-bm25f-smoke.json).
