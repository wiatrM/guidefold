# Native SEARCH/USE: Go + ParadeDB

The running API, migrations and publisher are one static Go executable. BM25 runs
in ParadeDB's Rust/Tantivy index. The API image contains no Python interpreter.
Python is used only by existing repository tooling, operator preparation and tests.

**Measured status:** loopback latency passes (fresh-client p95 117/138 ms at c1/c4),
but retrieval admission fails test-B HSR (+10.67 pp). This is a local evaluation
backend, not the admitted production profile. See the [full report](../../docs/reports/bakeoff/GO-PARADEDB-2026-09-05.md).

## Run with Docker Compose

From the repository root, with Docker Compose, Python 3.10+ and PyYAML installed:

```sh
python3 tools/search_service/dev.py deploy
```

This builds the image, starts persistent PostgreSQL/ParadeDB, migrates the schema,
publishes the committed Meridian fixture and starts the API at
`http://127.0.0.1:8765`. Secrets are generated once under
`.guidefold/compose/secrets/`; the helper never prints them. The secret directory is
0700; files are readable by the non-root container through Compose file secrets.
Existing passwords and the named database volume survive subsequent deployments.
DB readiness checks TCP, so the temporary socket-only bootstrap server cannot start
migration jobs prematurely.

For another committed monorepo:

```sh
export GUIDEFOLD_REPO=my-repository
python3 tools/search_service/dev.py deploy --repo-id "$GUIDEFOLD_REPO" --repo-root /path/to/repo --revision HEAD
```

Keep `GUIDEFOLD_REPO` set for later Compose commands. `GUIDEFOLD_PORT` overrides the
host port; `GUIDEFOLD_TENANT` selects the operator-configured tenant. Client-supplied
repository/path metadata never changes that identity. The database has no host port.

```sh
TOKEN="$(cat .guidefold/compose/secrets/api_token)"
curl -fsS http://127.0.0.1:8765/health/ready
curl -fsS http://127.0.0.1:8765/v1/search \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"schema_version":"1.1","query":"test a PySpark pipeline","workspace":{"repo_id":"meridian","cwd":"platforms/forge/pipelines"}}'
```

Use the returned `skill_id` and exact `revision` in `POST /v1/use`. The full
[contract](../../docs/HARNESS-SERVICE-CONTRACT.md) covers targets, loaded revisions,
budgets, correlation and compatibility. `GET /health/live` reports process liveness;
readiness checks the DB head and compatible published metadata. Database loss causes
an explicit 503/504, without an in-memory search/body fallback. `docker compose stop`
stops this stack while preserving data. Deployment does not run `down -v`.

## Data and request path

`dev.py` extracts only a Git commit, using the existing repository snapshot builder.
The Go publisher checks content digest, builder identity, card identities and policy
configuration. One transaction writes the immutable cards, builds their search index
and activates the head. Re-publishing the same snapshot is idempotent. Publishing a
previous bundle reactivates it. Bodies are bytea, so USE preserves exact UTF-8 bytes,
including NUL; only the indexed text replaces NUL with a space.

Each tenant/repo/snapshot has its own physical BM25 projection and index. Otherwise
Postgres filtering would restrict returned rows while BM25 document frequencies still
included other repositories and old snapshots. The publisher derives table names from
a hash of trusted identity; request values never become SQL identifiers. Metadata
filters use `pdb.literal`; score/URN ordering uses `COLLATE "C"` to enable Top K and
avoid locale-dependent tie ordering. Filters apply before the top-50 limit.

The API reads the active DB head for each request. It caches immutable policy/card
metadata, without bodies. It resolves cwd/target scopes, checks negative triggers and
status, retrieves BM25 candidates from SQL, then applies the Go policy/score/closure/
selection port. USE reads the exact body from SQL. The API DB role has SELECT only;
admin credentials exist only in migration/publication jobs.

The backend is `paradedb_bm25_v1`: Unicode BM25 over concatenated name, description,
digest, triggers and body. It is a new retrieval implementation, so exact rankings
against the historical Python BM25F are not promised. Policy conformance and retrieval
quality are evaluated separately. The CLI remains unchanged. The old Python/C++
`tools/serve_spike` implementation remains reproducible experimental evidence.

Dense is explicitly disabled in this Go backend. The installed pgvector extension and
nullable vector column are preparation, not an embedding or GPU service. A separately
versioned encoder/index and measured fusion are required before enabling dense.

## Verify and measure

```sh
python3 -m pip install pyyaml 'jsonschema>=4.23,<5'
python3 tools/search_service/smoke.py --recovery
(cd services/search && go test -race ./... && go vet ./...)
python3 tools/search_service/contract_fixtures.py
```

The smoke test uses the committed Meridian fixture. It checks real SQL, Top K,
SEARCH/USE schemas, scope and revision policies, budgets, duplicate JSON, parallel
requests, exact body checksums, idempotent/atomic publication, isolated BM25 statistics,
redacted logs and restart recovery. `--recovery` stops only this Compose project's
DB/API. CI builds and deploys the real image and repeats these checks.

The latency workload requires the existing pinned SKILLRET cache:

```sh
python3 tools/search_service/benchmark.py prepare
docker compose --profile tools run --rm -e GUIDEFOLD_REPO=skillret-service-bench publish publish /input/benchmark-snapshot.json
GUIDEFOLD_REPO=skillret-service-bench docker compose up -d --wait api
python3 tools/search_service/benchmark.py run --output .guidefold/checks/go-paradedb-latency.json
GUIDEFOLD_REPO=meridian docker compose up -d --wait api
```

It measures 200 requests in each of HTTP c1/c4 and fresh-client c1/burst-c4 arms.
Fresh timing includes launching a Python stdlib HTTP client, token-file I/O, connection, response
parse and exit. These are loopback measurements, not installed harness or WAN SLOs.
The quality runner uses existing converters/metrics and records per-query results:
`python3 tools/search_service/quality.py --dataset dev` (or `test_a`, `test_b`,
`regression`). Test corpora are run once per frozen variant, never used for tuning;
completed reports cannot be overwritten. It restores the Meridian API afterwards.

## Kubernetes follow-up

Reuse the immutable API image as a Deployment and Service, with the same live/ready
probes, graceful SIGTERM and externally mounted secrets. Run schema migration and
snapshot publication as ordered Jobs. Budget eight DB connections per replica.
Choose a Postgres operator or managed service that actually permits the pinned
`pg_search` extension; ordinary managed Postgres compatibility is not sufficient.
Add TLS/IAM, tenant credentials/RLS, backup/restore and failover drills, network/load
SLOs, bounded snapshot retention/garbage collection and durable E6.4 telemetry before
production admission. A retained snapshot currently retains its table and index;
automatic GC is deliberately not implemented. No Kubernetes deployment or HA claim
is made by this Compose release.
