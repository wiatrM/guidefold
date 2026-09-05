# GPU SEARCH: Go + Postgres + TEI

This is an explicit experimental profile. Default Compose stays on exact CLI BM25F.
The GPU overlay also returns exact sparse results; it runs hybrid retrieval in
background shadow and stores the comparison in Postgres. Direct neural responses
require an explicit research-only override. DEV results cannot establish HSR or
independent transfer. See [ADR-0027](../../docs/adr/ADR-0027-gpu-retrieval-profile.md)
and the [registered protocol](../../docs/reports/bakeoff/GPU-HYBRID-PROTOCOL-v1.md).

## Deploy a local fixture

Requires Docker Compose with NVIDIA GPU support, a supported Ada GPU (measured on
RTX 4090), Python/PyYAML for operator tooling and a local pinned checkpoint. Download
the checkpoint with `huggingface_hub.snapshot_download`, model
`ThakiCloud/SKILLRET-Embedding-0.6B`, revision
`0e10886e80a0aacc9efddc28282a258e2ab7eae1`. Pass the resulting directory below.
`prepare` verifies the weights hash and creates a separate TEI-compatible adapter;
it does not modify the original checkpoint. The API image contains no Python.

From the repository root:

```sh
python3 tools/search_service/dev.py prepare
python3 tools/search_service/gpu.py prepare --source /path/to/pinned/checkpoint
# This helper generates .guidefold/compose/gpu.env (model identity/path and port).
dc() { docker compose --env-file .guidefold/compose/gpu.env -f compose.yaml -f compose.gpu.yaml "$@"; }
dc build api
dc up -d --wait db tei
dc --profile tools run --rm publish
python3 tools/search_service/gpu.py encode --snapshot .guidefold/compose/snapshot.json
dc --profile tools run --rm publish-embeddings
dc up -d --wait api
curl -fsS http://127.0.0.1:18765/health/ready
```

This creates project `guidefold-search-gpu`, a separate database volume and loopback
ports 18765 (API) / 18766 (TEI). It shares local secret files with base Compose;
secrets are not printed. For a real committed repository use `dev.py prepare` with
`--repo-root`, `--repo-id` and `--revision`, and export matching `GUIDEFOLD_REPO`
for all later Compose calls. The [base runbook](README.md) covers API 1.1 and USE.
Tenant and repository identity come from deployment, not from client metadata.

`publish` stages cards/postings without changing the active head. `publish-embeddings`
requires all vectors and matching skill revisions; only its successful transaction
activates the new snapshot. Repeating the same bundle is idempotent. Older complete
bundles can be reactivated. Do not bypass staging with the sparse publisher when
updating a GPU deployment. Model identity changes require matching vectors and an
API/worker deployment configured with that identity.

## Serving profile

Online default: FP16, last-token pooling, normalized vectors, 8192-token maximum,
two tokenizer workers, 32 TEI concurrent requests, eight API slots, one request per
forward. After delivering the sparse response, one of four background workers runs an encode
while reusing that request's sparse ranks and policy mask, then exact pgvector cosine search
and equal RRF k=60 over the top-50 union, retaining full channel ranks. The same
scope/negative/status policy applies before retrieval; existing closure/select and
SEARCH/USE schemas apply afterwards. No query embedding cache is used.

`GUIDEFOLD_TEI_BATCH_REQUESTS=16 dc up -d --wait tei api` enables the measured
throughput experiment. It produced small cross-batch FP16 ranking changes; its first
run changed 3/600 selections. Restore `GUIDEFOLD_TEI_BATCH_REQUESTS=1` for the
repeatability profile. Set this value on every relevant Compose invocation, or save
it in the generated local env file. Shadow records an error for a mismatched worker limit; primary readiness remains sparse.
Document preparation can use batches of eight with the worker at 16, but do not mix
bulk indexing with online traffic/SLO measurement. The published vectors are fixed.

Shadow has a 128-job bounded queue, four workers, a one-second encode timeout and a
two-second compute deadline. `GUIDEFOLD_SHADOW_QUEUE_CAPACITY` accepts 1–256
(default 128). Each queued request stores compact per-scope admissibility and full
BM25 ranks, plus its top 50 candidates; this is request-local reuse, not a query cache.
The masks/ranks use five bytes per catalog document per scope, excluding top candidates
and other job overhead. The larger queue absorbs short bursts; sustained overload can
still lose comparisons and increases the age of shadow observations. Each job pins
the snapshot observed by the sparse request.
`gf.search_shadow` retains the top 20 sparse/hybrid ranks, delivered sparse selection,
hybrid selection, timings, encoder identity and `search_id`; no query or path text.
Queue overflow and persistence failure log the search ID. GPU failure records an
error, never inserts neural cards into SEARCH, and leaves sparse readiness available.
Shutdown or queue overflow can lose shadow jobs; this observational queue is not a
durable event spool. Compare records with client search events to report coverage.

Inspect one comparison through the operator command:

```sh
dc exec -T api /app/guidefold-search shadow-export SEARCH_ID
```

It includes event counts joined by authenticated tenant and `search_id`.
[The T1 runbook](../../deploy/t1/README.md) covers event export, reports and retention.
Query truncation is disabled; document preparation truncates to 8192 tokens.

Only to reproduce an already registered direct-output experiment, set all three:

```sh
GUIDEFOLD_SHADOW=false GUIDEFOLD_EXPERIMENTAL_OUTPUT=true GUIDEFOLD_RETRIEVAL_MODE=dense dc up -d --wait api
# Restore the supported response path:
GUIDEFOLD_SHADOW=true GUIDEFOLD_EXPERIMENTAL_OUTPUT=false GUIDEFOLD_RETRIEVAL_MODE=sparse dc up -d --wait api
```

`hybrid` is the other recorded treatment. Inline experiments keep their 250 ms encode
timeout and explicit 503/504 failure; their historical latency is not a measurement
of shadow throughput. No new quality trial or weight tuning is authorized by these
commands. Coordinate every additional configuration in DENSE-PROGRAM section 7.

## Reproduce validation

```sh
python3 tools/search_service/gpu_probe.py --source /path/to/pinned/checkpoint
python3 tools/search_service/shadow_integration.py
# gpu_smoke.py is the historical direct-output experiment, requiring the overrides above.
```

The numerical probe additionally needs the pinned checkpoint's PyTorch /
SentenceTransformers environment, NumPy and the cached public corpus. It compares
40 DEV queries, 32 documents and four synthetic inputs against PyTorch FP16.
The shadow integration test needs the 26-card fixture bundle at
`.guidefold/compose/fixture-embeddings.json` (use `gpu.py encode --output .guidefold/compose/fixture-embeddings.json`), verifies
sparse response equivalence, exact USE checksums, client-event joins and GPU outage
recovery. It stops/starts only this project's TEI worker. Fresh UUIDs/timings are
excluded from comparisons across separate HTTP requests; a Go unit test verifies
byte-exact delivery of a fixed response before enqueue. Neither is a quality test.

For the established 200-query / 6006-document latency workload, first use
`benchmark.py prepare`, stage `benchmark-snapshot.json` with repo
`skillret-service-bench`, and run `gpu.py encode --skillret-split test` against that
snapshot. Publish that embedding bundle, set the API's repo accordingly, then run:

```sh
GUIDEFOLD_PORT=18765 python3 tools/search_service/benchmark.py run --output .guidefold/checks/gpu-latency.json
```

The raw public `skill_md` is used only after verifying its card conversion equals
the published snapshot. Historical corpus cards and labels are not modified.
The frozen 1000-query DEV quality runner is `gpu_quality.py --mode dense|hybrid`;
it requires the matching 10123-card `parity-snapshot.json` and complete train
embeddings to have been published to this GPU project. It refuses completed-arm
reruns and identity changes. Never point the old Tantivy quality runner at GPU
or treat repeated test-A/test-B measurements as new admission evidence.

## Throughput diagnostics

The [throughput report](../../docs/reports/bakeoff/SERVICE-THROUGHPUT-2026-09-05.md)
records telemetry insert/replay batches, shadow coverage, foreground latency and
rejected experiments. `throughput.py ledger` resets only the isolated
`guidefold-ledger-contract` fixture ledger; create it with
`telemetry_integration.py --keep` first. `throughput.py shadow` requires the
6006-document benchmark repository and complete vectors described above. Pass a
unique `--label` and `--image`; shadow also accepts `--batch` and `--queue`. These
are engineering measurements without relevance labels or quality tuning.

## Kubernetes boundary

Reuse Go and pinned TEI images with separate CPU/GPU Deployments, probes and bounded
queues; preserve the encoder/index identity on rollout. Migration and staged
publication remain Jobs. GPU autoscaling should observe queue time and request/token
load, with separate indexing capacity. No Kubernetes manifests, HA, WAN/TLS/IAM,
backup/restore or production admission are claimed by this Compose experiment.
