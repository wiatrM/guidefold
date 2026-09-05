# Native SEARCH/USE: Go + ParadeDB

The running API, migrations and publisher are one static Go executable. Default
SEARCH uses the reference CLI's integer BM25F with Postgres postings. The API image
contains no Python interpreter; Python is operator and evaluation tooling only.

**Measured default:** 0/1000 HTTP/CLI parity mismatches; whole-client p95 116/136 ms
at c1/c4. See the [default report](../../docs/reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md).
The old Tantivy scorer is an explicit, unadmitted reproduction mode.
An opt-in [GPU profile](GPU.md) adds pinned TEI encoding and exact pgvector fusion;
it keeps separate quality admission and does not change default ranking.

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
selection port. USE reads the exact body from SQL. The API DB role has SELECT plus INSERT on the append-only event/shadow tables;
it cannot update or delete catalog rows. Admin credentials exist only in operator jobs.

The default backend is `router_bm25f_v1`: the reference CLI exports its integer IDF,
field norms and postings; Go compiles exactly the same BM25F term contributions and
stores them in Postgres. SEARCH reads only query-term postings, applies scope and
negative filters before top-50, then runs the shared integer policy/selection. It
never truncates candidates with a different search engine first. A missing canonical
index fails readiness: re-run `dev.py deploy` to upgrade an existing deployment.

`GUIDEFOLD_LEXICAL_ENGINE=paradedb-experimental` explicitly enables the old Tantivy
ranker for reproduction only. Its historical latency numbers do not describe the
corrected default, and its test-B harmful-skill exposure failed admission. There is
no automatic fallback to it. The CLI remains unchanged.

Dense stays disabled in the default deployment. The separate [GPU runbook](GPU.md)
provides the model/index publication lifecycle, Compose overlay and validation for
background hybrid shadow. Direct neural responses require a separate experiment flag. USE and the harness context contract remain shared.

## Verify and measure

```sh
python3 -m pip install pyyaml 'jsonschema>=4.23,<5'
python3 tools/search_service/smoke.py --recovery
(cd services/search && go test -race ./... && go vet ./...)
python3 tools/search_service/contract_fixtures.py
python3 tools/search_service/bm25f_fixtures.py
# Requires the pinned DEV corpus; 1,000 real HTTP vs CLI comparisons:
python3 tools/search_service/parity.py
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

## Request admission and recovery

The per-process limit covers authenticated body uploads and JSON parsing as well as
backend work: eight shared SEARCH/USE slots, and two independent telemetry slots.
An exhausted pool returns 429 before reading the body, with `Retry-After: 1` and an
HTTP/1 connection close. Retry on a new connection; preserve request/event IDs.
Malformed input and disconnected uploads release their slots. Authentication and
health probes run before admission. The existing six-second HTTP read timeout limits
slow uploads; this is not a bound on total connections or process memory. The JSON
`deadline_ms` is read after upload but measured from handler entry.

Run the slow-upload E2E **only on a dedicated test stack**: it deliberately fills both
pools, checks SEARCH/USE and ledger isolation, closes unfinished uploads, and verifies
recovery over three repetitions. It uses real HTTP/1 sockets with and without
`Expect: 100-continue`. `compose-service` runs this automatically:

```sh
python3 tools/search_service/http_admission.py --url http://127.0.0.1:8765
```

Evidence and before/after reproduction: [HTTP admission report](../../docs/reports/bakeoff/HTTP-ADMISSION-2026-09-06.md).

## Kubernetes follow-up

Reuse the immutable API image as a Deployment and Service, with the same live/ready
probes, graceful SIGTERM and externally mounted secrets. Run schema migration and
snapshot publication as ordered Jobs. Budget eight DB connections per replica.
Choose a Postgres operator or managed service that actually permits the pinned
`pg_search` extension; ordinary managed Postgres compatibility is not sufficient.
Add TLS/IAM, tenant credentials/RLS, backup/restore and failover drills, network/load
SLOs, bounded snapshot retention/garbage collection and authenticated harness integration before
production admission. A retained snapshot currently retains its table and index;
automatic GC is deliberately not implemented. No Kubernetes deployment or HA claim
is made by this Compose release.

Default-router correction and measured parity/latency: [report](../../docs/reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md).

## Telemetry and operations

`POST /v1/events:batch` accepts up to 500 schema-1.0 events with the same Bearer
credential as SEARCH/USE. The service binds tenant identity, uses `(tenant_id,event_id)`
idempotency, and returns `accepted`, `duplicate`, `rejected` after commit. A failed
transaction receives no success ACK. Two separate ingest slots bound work; retry 429/
transient 5xx with the same IDs. Unknown schema versions are permanent per-event rejects.

The Go validator consumes constants exported from `tools/telemetry/ledger.py`; the
same ledger/report pytest assertions run against SQLite and actual HTTP/Postgres in
`telemetry-service` CI. The original report calculations are reused unchanged.
The current CLI flush lacks Bearer support: its integration proof uses a test-only
credential adapter. Complete that adapter in E2.6 before claiming a direct harness flow.

[VM/systemd runbook, snapshots, rollback and retention](../../deploy/t1/README.md).
`compose-service` is the exact branch-protection check name for the 1000-query HTTP/CLI
parity gate; `native-service` checks the formula/policy port. Branch protection is
configured by the repository owner, not by these workflow changes.
