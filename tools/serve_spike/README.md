# E1.1b: resident SEARCH / USE feasibility spike

> **Provenance note (2026-09-05).** These files first reached `main` inside commit `314f3ec`
> ("Dense programme v2.3: a multiplicity rule…", PR #40), whose message describes only the dense
> programme and does not mention this work at all. That was an accident, not a decision: the dense
> programme's TL ran `git add -A` in the **shared** main checkout while a concurrent session was
> writing this service spike into the same working tree, and swept 21 files / ~65 800 lines of it
> into an unrelated documentation commit. Nothing here was reviewed as part of PR #40 and its
> commit message should not be read as describing it. The work itself is this spike's own; see
> `docs/adr/ADR-0023-search-use-service-and-measured-utility.md`. Git history cannot be rewritten
> after a squash-merge, so this note is the correction.

This tool validates a local HTTP boundary around the existing retrieval pipeline.
It keeps the index and full SKILLRET encoder resident, encodes every SEARCH query
live, and records request timings and revision-pinned USE hydration. It does not
switch the shipped hook/CLI to a service.

Architecture and MVP sequencing: [ADR-0023](../../docs/adr/ADR-0023-search-use-service-and-measured-utility.md).
The shared admissibility/ranking/selection contract remains
[ADR-0022](../../docs/adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md).

## Offline prerequisites

The commands below run in **Ubuntu WSL bash**, not PowerShell. From Windows,
enter `wsl -d Ubuntu-24.04` first. The existing GPU environment must already have
its dependencies installed; this procedure downloads nothing.

```bash
cd /home/mike/projects/guidefold
GF_PY=/home/mike/.cache/guidefold/gpu-venv/bin/python
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
```

Repeat those assignments in each terminal used below. Required local inputs:

- Corpus `skillret` at revision `a050ad233a504a43135bafe8cdf45574052b5729`,
  normally under `/home/mike/.cache/guidefold/corpora/skillret`. The server
  verifies its test files against `docs/reports/bakeoff/validation/corpora-manifest.json`.
  `GUIDEFOLD_CORPORA` can override the corpus cache root.
- For the probe, the same corpus's `data/queries/train.jsonl` and the committed
  `docs/reports/bakeoff/validation/skillret-dev-split.json`. Only frozen DEV query texts are sampled;
  labels are not consulted. Probe output records source/sample hashes.
- Model `ThakiCloud/SKILLRET-Embedding-0.6B` at revision
  `0e10886e80a0aacc9efddc28282a258e2ab7eae1`, under
  `/home/mike/.cache/guidefold/models/ThakiCloud__SKILLRET-Embedding-0.6B/0e10886e80a0aacc9efddc28282a258e2ab7eae1/`.
  `GUIDEFOLD_MODELS_ROOT` can override its parent model root. The full service
  requires this local snapshot; it does not fall back to a network download.
- CUDA for the default full-model run. `--disable-model` needs no GPU.

Check the corpus and GPU before building:

```bash
"$GF_PY" tools/eval/skillret.py stats
/usr/lib/wsl/lib/nvidia-smi
```

Build the full document cache once, unless it already exists and verifies:

```bash
"$GF_PY" tools/eval/skillret.py encode \
  --skill-batch-size 4 --skill-chunk-size 200
```

This existing offline encoder writes the aggregate cache into
`tools/eval/.skillret-cache/` and content-addressed float vectors into
`tools/bakeoff/.bakeoff-cache/`. Keep both: service startup verifies **every**
aggregate document vector against the exact source text's float cache, pinned
model and quantization. A copied aggregate alone is insufficient. `--cache-dir`
on the server can relocate the aggregate; float-cache location follows the
existing encoder adapter. A partial `encode --sample` cache is rejected.

The existing builder also writes query vectors for offline evaluations. The
service never opens those files. Every accepted hybrid SEARCH that reaches the
encoder calls `_encode_uncached`, including repeated query texts.

## Run the two backends

Create a private local token and output directory once. The `.guidefold/`
directory is ignored by git; the token is not printed or passed as a command-line
argument to the server.

```bash
umask 077
mkdir -p .guidefold/serve-spike
"$GF_PY" -c 'from pathlib import Path; import secrets; p=Path(".guidefold/serve-spike/token"); p.exists() or p.write_text(secrets.token_urlsafe(32))'
```

Start the full-model arm in one terminal:

```bash
"$GF_PY" tools/serve_spike/server.py \
  --port 8765 --max-inflight 4 \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/hybrid-events.jsonl
```

For the resident sparse baseline, start another process on a separate port:

```bash
"$GF_PY" tools/serve_spike/server.py \
  --port 8766 --max-inflight 4 --disable-model \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/sparse-events.jsonl
```

`--disable-model` is a startup choice. An individual request cannot disable the
encoder or switch to a weaker policy. Both arms use the same existing Router
policy, candidates, score and select functions and expose at most four selected
cards. Both `hook` and `interactive` profiles currently use the same computation;
this spike contains no reranker. The USE response body has no configured byte/token cap in this spike; production hydration needs one.

Readiness is available while startup runs:

```bash
curl --silent http://127.0.0.1:8765/health/ready
curl --silent http://127.0.0.1:8766/health/ready
```

HTTP 503 means initialization is incomplete or failed. HTTP 200 with `ready:true`
means corpus/index initialization and, for hybrid, verification, model loading
and one warmup forward pass have completed. On initialization failure, inspect
the process stderr and readiness `error`; fix the inputs and restart. The spike
does not retry initialization or reload a snapshot in place. Stop each server
with Ctrl-C after its measurements.

## Measure HTTP and fresh-client latency

Wait for readiness and for any cache-building process to exit. Measure one arm
at a time; unrelated CPU/GPU work changes the result and should be recorded.

```bash
"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8765 --label hybrid \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 300 \
  --output .guidefold/serve-spike/hybrid.json

"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8766 --label sparse \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 300 \
  --output .guidefold/serve-spike/sparse.json
```

Each run uses 200 distinct frozen public DEV query texts. It measures sequential
HTTP, four concurrent clients, and one fresh Python client process per request.
The four initial client warmups are excluded. USE is measured separately with an
exact revision returned by SEARCH, and verifies the returned body checksum.
The fresh-client arm includes Python startup, imports, token-file read, HTTP and
process exit; it is not the actual product harness or whole-hook measurement.

The 300 ms value is an evaluation threshold, distinct from the 1000 ms request
deadline and five-second transport timeout. Results report attempted/succeeded/
failed requests, successful and all-attempt latencies, errors, budget misses,
throughput, server stages, readiness evidence and the live-forward counter audit.
A fast rejection is counted as a failed attempt, not a successful low latency.
The p99 from a 200-request sample should not be treated as a production tail SLO.

Run the isolated contract tests without loading a model:

```bash
"$GF_PY" -m pytest -q tests/test_service_spike.py
```

## Optional optimization experiment: whole client p95 below 400 ms

The reference behavior above remains the default. `--optimized` moves immutable
BM25 per-term contributions into a startup cache and retains a dense int64 matrix
instead of copying/casting document rows for every query. It preserves integer
scores and the shared policy/rank/selection functions; it introduces no query
result cache. Dense scoring computes all rows and exposes only admissible rows.
The sparse cache's default budget is 256 MiB, separate from the resident dense
matrix; readiness reports actual estimated cache size and coverage. A partially
cached index remains exact via uncached per-term computation, but must not be
reported as fully precomputed.

Freeze the CLI source before comparisons so another task cannot change the
reference between runs. The service hashes and executes the exact same source
bytes from `--cli-path`; readiness `policy_revision` identifies the loaded bytes.
`--cli-path` also works without `--optimized` for a pinned reference run.

```bash
cp --no-clobber skills/guidefold/scripts/guidefold .guidefold/serve-spike/guidefold-pinned
sha256sum .guidefold/serve-spike/guidefold-pinned

"$GF_PY" tools/serve_spike/server.py \
  --port 8767 --max-inflight 4 --optimized --torch-threads 1 \
  --cli-path .guidefold/serve-spike/guidefold-pinned \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/optimized-t1-events.jsonl
```

`--torch-threads` overrides CPU PyTorch threads **after** the encoder adapter has
loaded the model and set its own default, and before warmup. Readiness records
both requested and effective values. To compare 1 versus 16 threads, stop the
first process, restart with `--torch-threads 16` and a distinct log/output label,
then run the same workload. Do not run the model arms simultaneously.

After readiness, in a second terminal with the same setup variables:

```bash
"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8767 --label optimized-t1 \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --fresh-concurrency 4 \
  --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/optimized-t1.json
```

The optimization command measures 200 fresh processes with four concurrent
workers (`--fresh-concurrency 4`). Repeat with `--fresh-concurrency 1` and a
distinct output name for the sequential whole-client comparison. Ordered ranking
and selected-card digests are retained for parity checks across runs.

Compare against a reference process started with the **same** pinned CLI and
thread count, without `--optimized`. Evaluate fresh-client p95 and success rate,
as well as HTTP c1/c4 and queue stages. A passing HTTP-only verdict does not by
itself establish the requested whole-client gate. These are still Python client
process measurements, not the product harness or WAN path. Any language rewrite,
dynamic batching or wider concurrency redesign should follow the measured stage
costs and retain score/policy parity.

## API and telemetry contract

`POST /v1/search` requires `Authorization: Bearer <token>` and JSON:

```json
{"query":"Validate an HTTP API", "profile":"hook", "node":"_root", "deadline_ms":1000}
```

It returns `search_id`, actual `backend`, corpus `snapshot`, pinned `model`,
`policy` and source `policy_revision`, admissible `ranked` results, selected
`cards`, `stages_ms` and `live_encode_calls`. `composition.status` remains
`not_evaluated`, with `incomplete:null`: the spike does not establish whether all
skills required by a task have been selected. Empty selection reports abstention.

`POST /v1/use` requires the exact `skill_id` and `revision` returned by SEARCH;
`search_id` and `deadline_ms` are optional. Missing/invalid inputs return 400,
unknown skills 404, and stale revisions or inactive skills 409. Success returns
`status:"hydrated"`, current state, body, SHA-256 checksum and
`execution_observed:false`. The supplied `search_id` is echoed with
`search_id_verified:false`; a server-validated search/use ledger is future work.

JSONL telemetry records request identity, outcome, versions, returned skill IDs
and stage timings. It omits query text, skill bodies and the bearer token.
Successful events are `search_completed` and `use_hydrated`; failed requests have
HTTP status/error. Write failures increment readiness `telemetry_errors`; this
is observable loss, not guaranteed delivery. There is no analytics database,
retention policy, deduplication, user/session identity or outcome attribution yet.

## What this validates and leaves open

- **Latency scope:** loopback HTTP with resident weights/index and serialized
  encoder/Router access. Admission and connection-worker counts are bounded;
  saturation returns 429. This is not a WAN, TLS, multi-tenant or production-load
  result. No cloud resource is created.
- **Request limits:** JSON payloads are limited to 16 KiB, queries to 4096 characters,
  deadline to 1..5000 ms. Deadlines are checked between stages and while acquiring
  the engine lock. A running model forward pass is not preempted; the client may
  time out before the server finishes work. There is no dynamic batching.
- **Readiness scope:** startup readiness verifies the data and one forward pass.
  It is not a continuous GPU health check; a later encoder error does not
  automatically eject/restart the process. Readiness and model counters are
  process-local and reset on restart.
- **Counter meaning:** `model_load_calls` counts completed explicit model loads;
  it is one for a ready hybrid process and zero for sparse. `live_encode_calls`
  excludes the startup warmup and increments after a query forward returns.
  Work that later exceeds its deadline can still increment the counter. Failed
  forward calls are not counted. No simultaneous external traffic should occur
  during the probe's counter audit.
- **Cache scope:** source files, exact document text bindings, model revision,
  document order/dimensions and integer vectors are checked at startup. Model
  snapshot directory naming is trusted locally; this is not a signed supply-chain
  attestation. The immutable resident snapshot has no live update or revocation
  mechanism. It contains 6006 test skills, not 30,000.
- **Authorization scope:** loopback binding and a shared bearer token only.
  There is no production IAM, tenant isolation, TLS, key rotation or signed
  offline policy lease. The shared retrieval policy is not tenant authorization.
- **Fallback scope:** `probe.search_with_fallback` exercises a controlled
  snapshot/revision/lease contract; it is not a real local BM25 fallback, registry
  lease verification or shipped CLI integration. Authentication denial must not
  be converted into cached disclosure.
- **Quality and usefulness:** the probe does not measure routing quality, bundle
  completeness, usability, application, successful execution or usefulness.
  SEARCH counts retrieval; USE counts hydration. Outcome and usefulness require
  explicit later client events/evaluation. A successful local latency gate cannot
  close those product gates.