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

## Plain Postgres profile

The service also runs on a stock PostgreSQL server, without ParadeDB `pg_search`
and without `pgvector`. That is what `python3 tools/dev/pg.py start` gives you: a
non-root instance under `~/.cache/guidefold/pg/dev` on 127.0.0.1:54329, and what
`services/search/internal/testdb` starts for the Go tests.

`migrate` attempts both extensions inside an exception block and continues without
them. Without `pgvector` it creates neither the `embedding` column nor the dense
tables; without `pg_search` it creates no per-snapshot BM25 table. A later `migrate`
builds them for every published snapshot once the extension exists.

`serve` starts with the default `router` engine, which reads the integer BM25F
postings in `gf.router_terms` and never touches either extension, so ranking is
unchanged. `/health/ready` reports `"pg_search_version": "absent"`.
The reproduction-only `GUIDEFOLD_LEXICAL_ENGINE=paradedb-experimental` refuses to
start without the extension (`paradedb_engine_requires_pg_search`) rather than
silently answering from a different scorer, and the GPU profile needs `pgvector`.

```sh
python3 tools/dev/pg.py start
export PGHOST=127.0.0.1 PGPORT=54329 PGUSER=postgres PGDATABASE=guidefold PGSSLMODE=disable
export APP_PASSWORD_FILE=... PG_PASSWORD_FILE=... GUIDEFOLD_POLICY_SOURCE=...
./search migrate && ./search serve
```

## Management API and workers

`/api/v1/**` is the management surface: authentication, organisations, membership,
installation tokens and the device flow, plus repositories, imports and the
knowledge catalog, described by
[`openapi/management-v1.yaml`](openapi/management-v1.yaml) and served at
`GET /api/v1/openapi.yaml`. `GUIDEFOLD_AUTH=dev|workos` selects the identity
provider; the development provider renders a local form and exists only when it is
asked for by name. See [`internal/README.md`](internal/README.md) for the packages.

`/v1/search`, `/v1/use` and `/v1/events:batch` resolve the same principal. The
organisation is the token's own for an installation or CI token, and for a
session or personal token it comes from the `X-Guidefold-Org` header (org_id or
slug), or is implied when the person belongs to exactly one organisation. The
repository is the token's binding when it has one, else `X-Guidefold-Repo`, else
`workspace.repo_id`, else the organisation's only repository. Naming another
organisation's repository is `403`, never a different tenant's answer. The legacy
operator token keeps the configured `GUIDEFOLD_TENANT`/`GUIDEFOLD_REPO` and
consults no management table.

## Importing a monorepo

    guidefold import --wait          # scan, upload the missing blobs, finalize

`POST {repo_base}/imports` takes the CLI's scan manifest and answers with the
blob digests it does not already hold; `PUT …/blobs/{sha256}` accepts exactly
those and nothing else, so a file the scan excluded — a key, an ignored
directory, a symlink out of the tree — has no route into storage. `POST
…/finalize` moves the import to `queued` and enqueues `import.parse` (and
`publish.build` unless the manifest says `publish: false`) in one transaction.
Sending the same tree twice reuses the same import, uploads nothing and queues
no second parse.

`state: ready` is not `published`. The publication has its own field: an import
that parsed is not an import that is serving.

The catalog is then readable under the same repository prefix: `GET …/skills`
with filters and facets, `…/skills/{skill_id}` and its immutable revisions,
`…/revisions/{revision_id}/raw` for the exact imported bytes with an
`X-Content-SHA256` header, the three maps (`repository`, `scopes`, `layers`),
`…/map/relations` and `…/modules/{scope}`. A revision that does not exist is
`404` — never the latest one instead.

`guidefold-search worker [--once]` runs queued jobs from `gfm.jobs` with leases,
heartbeats and generation fencing. Its handler registry lives in
`worker_handlers.go` and holds `import.parse`, `proposal.generate` and
`publish.build`. A module whose configuration is broken — a generator naming an
unknown provider, a missing API key file — makes the worker refuse to start
rather than quietly dropping its kind from the registry and leaving those jobs
queued for ever.

**The worker image needs Python 3 and PyYAML; the API image does not.** The parse
job materialises an import's blobs into a private tree and runs the repository's
own `tools/worker/build_tree.py` over it, which imports the CLI's parser so the
catalog cannot disagree with the ranker about what a `SKILL.md` says. It never
executes anything from the imported repository. Configure it with
`GUIDEFOLD_REPO_ROOT` (the checkout holding the builder), `GUIDEFOLD_PYTHON`
(default `python3`), `GUIDEFOLD_BUILD_TREE` (default
`tools/worker/build_tree.py`) and `GUIDEFOLD_WORKER_DIR` (scratch trees, default
`~/.cache/guidefold/worker`).

## Review, publication and delivery

`{repo_base}/imports/{import_id}/plan` says what a generation run would do and
what it could cost — the groups, every limit, and how many scopes the
`max_groups` ceiling left out — before anything is enqueued.
`…/proposals:generate` writes one `proposal.generate` job per requested kind in
one transaction. `GUIDEFOLD_GENERATOR` selects the backend:

| Value | Behaviour |
|---|---|
| `none` (default) | The job ends `skipped` with `llm_not_configured` and the import stays exactly as the parse left it. |
| `deterministic` | Recipe `det-1`: extraction, enrichment and consolidation with no network and no model. Every field it emits carries a source reference or `needs_confirmation`; every consolidation it declines says why. |
| `openai`, `anthropic` | HTTP providers reading `OPENAI_API_KEY_FILE` / `ANTHROPIC_API_KEY_FILE`, with `GUIDEFOLD_GENERATOR_MODEL`, `GUIDEFOLD_GENERATOR_TIMEOUT_SECONDS` (default 60) and the optional price list `GUIDEFOLD_GENERATOR_USD_PER_MTOK_IN`/`_OUT`. Output is validated against a JSON Schema and retried at most twice; a citation to a document the request did not supply is dropped rather than believed; a call that timed out after the request left is charged to `usd_uncertain`, never to zero. |

A decision (`approve`, `edit`, `reject`) always carries a `reason`. An `edit`
may change prose only — frontmatter, scope, owner and relations are identity and
answer `422 invalid_candidate_change`. An `expected_revision` that no longer
matches is `409 stale_revision` with the current one. Approving writes a
revision with `origin: human`; exporting writes a patch and moves the proposal to
`awaiting_git`. **Export is not publication**: the proposal becomes `published`
only when a later import carries the exported bytes at the same path.

`publish.build` materialises the import's accepted config, skill and resource
blobs into a private tree, runs the same `tools/worker/build_tree.py`, validates
the graph and the package resources, and only then writes `gf.snapshots`,
`gf.skills`, the router index and `gf.heads` in one transaction with the
`gfm.publications` row. A cycle, a missing dependency or a missing required
resource fails the publication, records the findings in `publications.validation`
and leaves the previous head serving. An import in state `partial` never
activates: a catalog known to be missing skills must not silently become what
every agent reads.

`POST {repo_base}/snapshots/{snapshot_id}/activate` rolls forward or back. It
requires a `reason`, re-validates the snapshot's own graph before the head moves,
and records the reason in the audit log.

Delivery contract 1.2 is additive. A `1.1` request answers exactly as before. A
`1.2` request may carry `search_snapshot` — a head that has moved since is `409
snapshot_changed` — and its `/v1/use` answer adds `closure` (the `requires`
walk, bounded at depth 8, honouring `budget.max_cards` and `loaded_skills`, with
status `complete`, `unresolved` or `cannot_fit`) and `resources` (the package
manifest, with paths relative to the skill directory). `GET
/v1/skills/{skill_id}/revisions/{revision}/resources/{path}` serves one of those
files, re-checking access rather than trusting the URL. The 1.2 request schema is
`tools/serve_spike/contracts/harness-service-v1.2.schema.json`, found next to the
1.1 document or named by `GUIDEFOLD_CONTRACT_12`; without it a `1.2` request is
`400 unsupported_schema_version` rather than being validated as 1.1.

For an explicit source-integrity boundary, a 1.2 USE request may add
`delivery_policy:"proof_gated"`. The service evaluates the card's immutable
`source_proof` after closure calculation: a complete identity, revision,
snapshot, body hash, scope and claim record is followed by a check that every
cited path and SHA belongs either to the active package resource manifest or to
a skill/document published in the same repository snapshot, then content-
addressed source fetching from `gfm.blobs`; Go verifies every source SHA-256
and line range before returning `delivery.action:"LOAD"`. Abstract claims may
also carry content-addressed `claim_refs` to lower cards; those child proofs,
commitments, revisions, scopes and `refines` edges are checked recursively.
Missing,
stale, conflicting, unavailable or changed source proof returns
`delivery.action:"ASK"` with an empty body and redacted provenance. This is a
fail-closed delivery policy, not a semantic or execution guarantee. The default
and 1.1 paths retain their existing behavior; see
[ADR-0039](../../docs/adr/ADR-0039-proof-gated-source-grounded-delivery.md).
During publication, explicit `pending`/empty binding fields are filled from the
immutable snapshot and delivered bytes. `verified` is never upgraded by this
step, and a non-placeholder mismatch remains an `ASK` condition.

## Listening address

`guidefold-search serve` binds `GUIDEFOLD_LISTEN` (default `:8080`), and
`guidefold-search healthcheck` probes the same value, so moving the port does not
leave a health check pointing at the old one. A wildcard bind is probed on
loopback.

## Worker image

`services/search/Dockerfile.worker` builds a second image for `guidefold-search worker`,
sharing the exact same Go build stage as `services/search/Dockerfile` (same module, same
commit), so both images run the identical binary — the worker is the same program running a
different subcommand, not a fork. Its runtime stage is a digest-pinned
`python:3.12-slim-bookworm` plus a pinned `PyYAML`, not the API's distroless base:
`import.parse` shells out to the repository's own `tools/worker/build_tree.py`, which imports
`skills/guidefold/scripts/guidefold`'s parser and the `tools/serve_spike/`/`tools/search_service/`
modules it depends on, so it needs a real interpreter. Nothing else does —
`services/search/Dockerfile` stays Python-free on purpose (see `module-boundaries-go`), so a
compromised or malformed import can never reach an interpreter through the request-serving
process, and the worker itself never executes anything from an imported repository — only this
image's own copies of `build_tree.py` and the CLI ever run.

The image copies only the checked transitive import set of `build_tree.py` — the CLI,
`build_tree.py` itself, `tools/serve_spike/{repository,context,server}.py` and
`tools/search_service/index.py` — into `/app/repo`, mirroring the repository's own layout so
those modules' `tools.*` imports resolve exactly as they do here. It never copies `private/`,
`experiment/`, `.guidefold/` or `research/`. It runs as the same non-root UID the API image's
distroless user carries, and needs only a writable `/work` (`GUIDEFOLD_WORKER_DIR`, mounted as
tmpfs/emptyDir, never `/tmp`) to materialise import trees — the rest of the filesystem stays
read-only.

`docker compose up worker` builds and runs it from `compose.yaml`'s `worker` service: same
`guidefold_api` database role and `db`/`migrate` ordering as `api`, but no published port — it
only leases jobs from `gfm.jobs`, it never accepts a connection. `GUIDEFOLD_GENERATOR`
(`none|deterministic|openai|anthropic`) selects the `proposal.generate` backend once that handler
ships; `none` is the default and completes such jobs as skipped rather than guessing. The
publication job runs in the same image, over a tree materialised the same way. Static
shape — allowlisted `COPY` paths, a digest-pinned base image, a non-root `USER`, and no `ports:`
on the compose service — is enforced by
[`tests/test_worker_image.py`](../../tests/test_worker_image.py).

## Kubernetes deployment

The [portable Helm chart and release runbook](../../deploy/k8s/README.md) provide
pinned snapshots, staged publisher Jobs, separate CPU/GPU workloads, HPA, PDB,
NetworkPolicies and compare-and-swap promotion/rollback. Kubernetes >=1.33 is required.
`GUIDEFOLD_SNAPSHOT_ID` selects an immutable tenant/repo snapshot; unset, Compose keeps
following the active head. `/metrics` exposes aggregate load/error/latency metrics.
See [ADR-0030](../../docs/adr/ADR-0030-immutable-service-releases-on-kubernetes.md).
The kind validation is not a multi-node HA, GPU, TLS/IAM or production-load sign-off.

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
