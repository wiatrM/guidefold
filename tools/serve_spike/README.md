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

The recommended local service is **optimized sparse** (`--disable-model --optimized`).
It keeps the index resident and provides revision-pinned SEARCH/USE. The optional
Python/C++ hybrid is a measured shadow experiment, not an admitted product profile.
The service does not switch or modify the shipped hook/CLI.

The implemented [harness contract 1.1](../../docs/HARNESS-SERVICE-CONTRACT.md) adds
repository-relative cwd/targets, snapshot resolution, trace IDs, loaded revisions,
delivery budgets and explicit unused-signal reporting. It is backed by
[ADR-0025](../../docs/adr/ADR-0025-harness-service-context-contract.md), a
[JSON Schema](contracts/harness-service-v1.1.schema.json) and real HTTP conformance tests.
For actual monorepo paths, build a committed repository snapshot as documented there;
the corpus benchmark backend cannot resolve real repository paths.

Recommended corpus benchmark server, after the sparse prerequisites below:

```bash
"$GF_PY" tools/serve_spike/server.py --disable-model --optimized \
  --port 8765 --max-inflight 4 --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/sparse-events.jsonl
```

Architecture and MVP sequencing: [ADR-0023](../../docs/adr/ADR-0023-search-use-service-and-measured-utility.md).
The shared admissibility/ranking/selection contract remains
[ADR-0022](../../docs/adr/ADR-0022-admissibility-relevance-and-bundle-completeness.md).

## Offline prerequisites

The commands below run in **Ubuntu WSL bash**, not PowerShell. From Windows,
enter `wsl -d Ubuntu-24.04` first. The existing GPU environment must already have
its dependencies installed; this procedure downloads nothing.

```bash
cd /path/to/your/guidefold-checkout
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
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/hybrid.json

"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8766 --label sparse \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/sparse.json
```

Each run uses 200 distinct frozen public DEV query texts. It measures sequential
HTTP, four concurrent clients, and one fresh Python client process per request.
The four initial client warmups are excluded. USE is measured separately with an
exact revision returned by SEARCH, and verifies the returned body checksum.
The fresh-client arm includes Python startup, imports, token-file read, HTTP and
process exit; it is not the actual product harness or whole-hook measurement.

The current versioned acceptance is whole-client p95 <=400 ms and server-side
p95 <=300 ms, including fresh c1 and c4. Compare with `--inclusive-budget
--server-budget-ms 300`; its default strict comparison preserves historical artifacts.
The 1000 ms primary deadline, 400 ms burst deadline and five-second transport timeout
are separate controls. Historical 300/400 ms results remain unchanged. Results report attempted/succeeded/
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
  --port 8767 --max-inflight 4 --optimized --torch-threads 16 \
  --cli-path .guidefold/serve-spike/guidefold-pinned \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/optimized-t16-events.jsonl
```

`--torch-threads` overrides CPU PyTorch threads **after** the encoder adapter has
loaded the model and set its own default, and before warmup. Readiness records
both requested and effective values. The canonical comparison uses 16 threads.
One thread is a separate ablation: stop the first process, restart with
`--torch-threads 1` and a distinct log/output label, then run the same workload.
Do not run the model arms simultaneously.

After readiness, in a second terminal with the same setup variables:

```bash
"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8767 --label optimized-t16 \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --fresh-concurrency 1 \
  --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/optimized-t16.json
```

The primary optimization command measures 200 sequential fresh processes alongside
HTTP c1/c4. A separate burst uses four fresh workers and a 400 ms server deadline,
as shown below. Ordered ranking and selected-card digests are retained for parity
checks across runs; no successful-request-only result establishes the whole gate.

Compare against a reference process started with the **same** pinned CLI and
thread count, without `--optimized`. Evaluate fresh-client p95 and success rate,
as well as HTTP c1/c4 and queue stages. A passing HTTP-only verdict does not by
itself establish the requested whole-client gate. These are still Python client
process measurements, not the product harness or WAN path. Any language rewrite,
dynamic batching or wider concurrency redesign should follow the measured stage
costs and retain score/policy parity.

## Separate pipeline and native ranking switches

`--pipeline` uses separate encoder and Router locks. Each query is encoded and
quantized into its own vector, then releases the encoder lock before waiting for
the Router. That permits the next GPU forward to overlap the preceding request's
CPU routing. Batch size stays one. The vector is bound to the Router only while
holding its lock; all error/deadline paths release their own locks and never
clear another request's vector. Pipeline timings expose `encoder_queue` and
`router_queue`; the reference continues to expose `engine_queue`.

`--native-dense-rank` requires both `--optimized` and the full-model backend.
It replaces only dense ordering with the exact integer comparator from
`native_dense_rank.cpp`; policy, candidate assembly and selection remain the
shared Router implementation. It uses signed 128-bit intermediates, preserving
negative scores and tie ordering. Linux and a local C++17 compiler are required.
The compiler defaults to `/usr/bin/g++`; override it with `--native-compiler`.
Build output defaults to the ignored `.guidefold/serve-spike/native` directory,
with an optional `--native-build-dir` override.

Compilation/library verification/loading happen before readiness. If explicitly
requested native support cannot compile or load, startup fails; it never reports
native success while silently running the reference. Readiness exposes compiler
path/version/flags, source/compiler/library hashes, prepare/load times and build
reuse. Values outside the supported numeric contract use the original Python
comparator with explicit `fallback_calls` and `fallback_reasons`; native and empty
calls have separate counters. No compiler or file lookup runs inside a request.

Run the combined candidate after stopping other service instances:

```bash
"$GF_PY" tools/serve_spike/server.py \
  --port 8767 --max-inflight 4 --optimized --pipeline --native-dense-rank \
  --torch-threads 16 --cli-path .guidefold/serve-spike/guidefold-pinned \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/pipeline-native-events.jsonl
```

After readiness, capture both the primary run and a separate burst using the same
distinct-query workload. The primary server deadline is 1000 ms so tails remain
visible; the burst uses a 400 ms server deadline. Both are evaluated against the
strictly below 400 ms client threshold; transport timeout remains separate.

```bash
"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8767 --label optimized-pipeline-native-primary-t16 \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --fresh-concurrency 1 \
  --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/pipeline-native-primary-t16.json

"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8767 --label optimized-pipeline-native-burst-t16 \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --fresh-concurrency 4 \
  --use-count 20 --concurrency 1,4 \
  --deadline-ms 400 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/pipeline-native-burst-t16.json
```

For an ablation, remove only `--pipeline` or only `--native-dense-rank`, keep the
same pinned CLI, workload, thread count and client, and use a distinct output
name. All switches remain opt-in. Compare failures and ordered result digests,
not just successful-request latency. These commands describe a reproducible
candidate; passing a gate requires its actual measured result.

## Compare the complete primary and burst evidence

Capture the pinned reference before or after the contender, with other service
instances stopped. Start this reference in one terminal:

```bash
"$GF_PY" tools/serve_spike/server.py \
  --port 8765 --max-inflight 4 --torch-threads 16 \
  --cli-path .guidefold/serve-spike/guidefold-pinned \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/reference-t16-events.jsonl
```

After readiness, probe it from a second terminal, then stop it:

```bash
"$GF_PY" tools/serve_spike/probe.py \
  --url http://127.0.0.1:8765 --label reference-t16 \
  --token-file .guidefold/serve-spike/token \
  --count 200 --fresh-count 200 --fresh-concurrency 1 \
  --use-count 20 --concurrency 1,4 \
  --deadline-ms 1000 --timeout 5 --budget-ms 400 \
  --output .guidefold/serve-spike/reference-t16.json
```

Once the reference and both contender files above are complete, compare them:

```bash
"$GF_PY" tools/serve_spike/compare.py \
  --reference .guidefold/serve-spike/reference-t16.json \
  --contender .guidefold/serve-spike/pipeline-native-primary-t16.json \
  --burst .guidefold/serve-spike/pipeline-native-burst-t16.json \
  --budget-ms 400 \
  --output .guidefold/serve-spike/pipeline-native-comparison-t16.json
```

The complete performance gate requires 200/200 successful expected requests and
p95 <400 ms in contender HTTP c1/c4 and fresh c1, plus burst HTTP c4 and fresh c4.
The comparison validates workload/code/policy/model/snapshot identities and reports
missing, duplicate, failed and mismatched query IDs. Different primary/burst server
deadlines are recorded; no burst speedup is reported against an arm with a different
deadline or concurrency. Missing identities or evidence cannot produce a complete
verdict. Returned ranking/selection parity is separate from the latency gate and
establishes no retrieval-quality gain or task usefulness. Loopback success remains
separate from production harness, network, authorization and operational gates.

## Separate CPython scheduling ablation

`--gil-switch-ms 0.5` changes the interpreter scheduling interval only in the
dedicated service process. Accepted values are finite 0.1..10 ms; omitting the flag
preserves the existing interval. Startup readiness records requested and effective
values (the default observed on this host was 5 ms). It does not change the model,
batch size, ranking formulas or client. A shorter interval may reduce dispatch
waiting for the GIL, while more switching can reduce CPU throughput.

For this ablation, stop the other server and start:

```bash
"$GF_PY" tools/serve_spike/server.py \
  --port 8767 --max-inflight 4 --optimized --pipeline --native-dense-rank \
  --torch-threads 16 --gil-switch-ms 0.5 \
  --cli-path .guidefold/serve-spike/guidefold-pinned \
  --token-file .guidefold/serve-spike/token \
  --log-file .guidefold/serve-spike/pipeline-native-gil0p5-events.jsonl
```

Use `pipeline-native-gil0p5` in distinct primary, burst and comparison labels/output
names. Repeat the complete protocol above with the same reference, workload
and comparison tool, including c1/c4, fresh processes and result digests. An interval
change is an experiment; no latency benefit or passing gate is implied.

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
`execution_observed:false`. Here `status:"hydrated"` means the server prepared the
revision body for its response; it does not confirm client receipt, integrity
verification or hydration into agent context. The supplied `search_id` is echoed
with `search_id_verified:false`; a server-validated search/use ledger is future work.

JSONL telemetry records request identity, outcome, versions, returned skill IDs
and stage timings. It omits query text, skill bodies and the bearer token.
Successful server events are `search_completed` and `use_hydrated`; the latter is
emitted when the response is prepared, before confirmed client hydration. Neither
is an observed skill-use or usability event. Failed requests have HTTP status/error.
Write failures increment readiness `telemetry_errors`; this
is observable loss, not guaranteed delivery. There is no analytics database,
retention policy, deduplication, user/session identity or outcome attribution yet.

## What this validates and leaves open

- **Latency scope:** loopback HTTP with resident weights/index. Encoder and Router
  access are each serialized; only --pipeline overlaps the two stages. Admission and connection-worker counts are bounded;
  saturation returns 429. This is not a WAN, TLS, multi-tenant or production-load
  result. No cloud resource is created.
- **Request limits:** JSON payloads are limited to 16 KiB, queries to 4096 characters,
  deadline to 1..5000 ms. Deadlines are checked between stages and while acquiring
  the relevant engine/encoder/Router lock. A running model forward pass is not preempted; the client may
  time out before the server finishes work. There is no dynamic batching.
- **Readiness scope:** startup readiness verifies the data and one forward pass.
  In the default in-process encoder mode it is not a continuous GPU health
  check, and a later encoder error does not automatically eject the process.
  The optional worker mode below fails readiness after child failure; neither
  mode restarts automatically. Counters reset on restart.
- **Counter meaning:** `model_load_calls` counts completed explicit model loads
  in the API process (`model_load_calls_scope:api_process`): one for the default
  hybrid mode, zero for sparse or the optional child-worker mode. The worker's
  own count is under `encoder_worker.metadata.model_load_calls`. `live_encode_calls`
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
  SEARCH records retrieval; USE records a revision response prepared by the server.
  Confirmed client hydration, observed use, outcomes and usefulness require explicit
  later client events/evaluation. A successful local latency gate cannot
  close those product gates.

## Optional encoder process: future hybrid shadow experiment

The next product measurement is optimized sparse-only. `--encoder-process` is
an opt-in hybrid experiment; CPU correctness tests do not establish model-vector
parity, retrieval quality or a latency admission result. It requires `--pipeline`
and a model, and leaves the default path unchanged.

For a later, explicitly scheduled offline GPU experiment, add
`--encoder-process` to the existing `--optimized --pipeline --native-dense-rank
--torch-threads 16` command, using a separate result label and log file. Omit the
failed `--gil-switch-ms` ablation to preserve the default CPython interval.
The owned child uses `multiprocessing.spawn`, loads and warms the pinned encoder
once, and runs uncached batch-one forwards. The API process does not import
`encode` or torch in this mode. IPC carries one query and its matching raw
float32 vector; the API performs the same extra normalization and int8
quantization used by the reference path. It does not batch, retry or cache queries.

A normal query deadline is checked before dispatch. Once dispatched, the encoder
lock is held until the matching reply is drained; a late result yields 504 under
the ordinary server deadline check, and a later query can still succeed. This
is not hard cancellation at the client deadline. A separate finite watchdog
(`--encoder-worker-timeout`, default 5 seconds, allowed 0.05..30) bounds the IPC
operation. Watchdog expiry, child death or a malformed/mismatched reply ends the
owned worker and makes requests/readiness fail; no stale vector is reused.

Readiness includes the child PID, spawn mode, model/load/warmup metadata, effective
torch/GIL settings and live forward count. `model_load_calls` remains zero in the
API process while the child's completed-load count is one. SIGTERM closes the
owned worker; a daemon checks the child's parent PID every 100 ms so parent
process death also exits the worker. This uses process parentage because Linux
`PR_SET_PDEATHSIG` follows the creating thread, and service initialization runs
in a short-lived thread. The guard still needs Python scheduling in the child.
CPU tests cover initialization-thread exit, parent SIGTERM/SIGKILL with a blocked
fake forward, deadline recovery, response isolation and failure cleanup.

## Current sparse admission comparison

Freeze the same CLI bytes and probe in a reference and optimized run. Retain the
primary c1/c4/fresh-c1 and burst HTTP-c4/fresh-c4 outputs. Run both budgets:

```bash
for budget in 300 400; do
  "$GF_PY" tools/serve_spike/compare.py \
    --reference .guidefold/serve-spike/sparse-reference.json \
    --contender .guidefold/serve-spike/sparse-optimized.json \
    --burst .guidefold/serve-spike/sparse-optimized-burst.json \
    --budget-ms "$budget" --server-budget-ms 300 --inclusive-budget \
    --output ".guidefold/serve-spike/sparse-comparison-$budget.json"
done
```

Each required arm must complete all 200 requests. Exact parity requires 1,000
successful matching pairs across the five arms (200 distinct queries), not a claim
about 1,000 independent tasks. The server-time header includes synchronous logging
and JSON serialization. Whole-client timing additionally includes the fresh process.
The benchmark does not exercise real harness hooks or prove metadata improves quality.

Run real process outage/restart checks separately:

```bash
"$GF_PY" tools/serve_spike/recovery_probe.py --disable-model --optimized \
  --cli-path .guidefold/serve-spike/guidefold-pinned \
  --output .guidefold/serve-spike/sparse-recovery.json
```

The recovery cache is an unsigned controlled fixture, not a shipped offline fallback.
The complete measured decision and preserved failed hybrid experiments are in the
[E1.1b report](../../docs/reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md).
