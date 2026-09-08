# tools/dev — local pivot stack, no Docker, no sudo

Two scripts, stdlib-only Python 3:

- `pg.py` — a local, non-root PostgreSQL for development and tests.
- `stack.py` — builds and runs `guidefold-search` (`migrate`, `serve`, `worker`) against
  that PostgreSQL, plus (optionally) the React UI. Imports `pg.py` rather than
  duplicating it.

Both are meant for local E2E/acceptance runs against the real product path (the same
Go binary and schema as `compose.yaml`/production), not for CI or deployment.

## Prerequisites

- Go toolchain at `~/.cache/guidefold/toolchain/go/bin` (module dir is
  `services/search`, which has its own `go.mod`; `stack.py` builds with
  `go build -C services/search -o ... .`, not `go build ./services/search`, since there
  is no `go.mod` at the repository root).
- PostgreSQL binaries at `~/.cache/guidefold/toolchain/pg18/bin` (override with
  `GUIDEFOLD_PG_BIN`). No `psql`/`createdb` install is required — `pg.py` uses
  `createdb` if present, otherwise a minimal built-in libpq client.
- `pnpm`/`node` on `PATH`, only needed for `--ui`.

## Usage

```sh
python3 tools/dev/stack.py up [--name dev] [--pg-port 54329] [--api-port 8765] \
    [--ui] [--generator none|deterministic] [--reset]
python3 tools/dev/stack.py seed [--name dev] [--api-port 8765] [--org acme] [--repo meridian] \
    [--email owner@example.test] [--subject seed-owner] [--git-host-url URL] [--tree DIR]
python3 tools/dev/stack.py down [--name dev] [--stop-pg]
python3 tools/dev/stack.py status [--name dev]
python3 tools/dev/stack.py logs {api,worker,pg,ui} [--name dev] [-n LINES] [-f]
python3 tools/dev/stack.py env [--name dev]
```

`seed` is the shortest path to a stack with data in it: dev login, organisation, repository,
device-flow token, and a CLI `import --wait` of a copy of `examples/monorepo` in a throwaway
git work tree under `~/.cache/guidefold/seed/<name>/`. Every step goes through the same HTTP
surface a browser and the shipped CLI use — no SQL, no in-process shortcut — so what it
produces is what a person would get. It prints the resulting identifiers as JSON on stdout:

```json
{
  "api": "http://127.0.0.1:8765",
  "ui": "http://127.0.0.1:4331/?mode=api&org=acme&repo=meridian",
  "org_slug": "acme", "org_id": "…", "repo_id": "meridian", "user_id": "…",
  "tree": "/home/…/.cache/guidefold/seed/dev/monorepo", "commit": "…",
  "import_id": "…", "import_state": "ready", "manifest_digest": "…",
  "token_file": "/…/.guidefold/dev/seed/dev-token"
}
```

The personal token is written to a 0600 file and only its **path** is printed: a token in a
terminal scrollback is a token in a log. `seed` imports but does not publish — `POST
{repo_base}/publish` with the `import_id` is the next step when you want SEARCH to answer.

`up` is idempotent: it reuses an already-running PostgreSQL instance and rebuilds/restarts
the API and worker each time. `--reset` stops everything and destroys the named
PostgreSQL data directory (via `pg.py reset`) plus the generated dev secrets first.

`--name`/`--pg-port` select the PostgreSQL instance, exactly like `pg.py`'s own flags (so
`tools/dev/stack.py up --name dev` and `tools/dev/pg.py start --name dev` talk about the
same cluster). There is only ever one API/worker/UI triple per checkout regardless of
`--name` — see "Known deviations" below for why.

Runtime files live under `.guidefold/dev/` (gitignored):

- `secrets/` (0700 dir, 0600 files: `app_password`, `api_token`, `postgres_password`).
  Generated once, on first `up`; never printed or logged. `postgres_password`'s content is
  a placeholder — PostgreSQL runs with `--auth=trust` (see `pg.py`), so it is never
  actually checked, only its length (`services/search/contract.go`'s `secret()` rejects
  anything under 32 bytes).
- `bin/guidefold-search` — the built binary.
- `api.pid`/`api.log`, `worker.pid`/`worker.log`, `ui.pid`/`ui.log`, `migrate.log`,
  `state.json` (small convenience cache of the last `up`'s ports/flags, so `status`/`env`/
  `down` do not require repeating them — always overridable by passing the flag again).

PostgreSQL's own data and log live under `~/.cache/guidefold/pg/<name>` (owned by `pg.py`,
untouched by `down` unless `--stop-pg`, and not deleted by anything except `--reset`).

`GUIDEFOLD_STACK_INTEGRATION=1 python3 -m pytest tests/test_dev_stack.py -k real_toolchains`
runs the one opt-in integration test: real `up` against the real toolchains, `GET
/health/live` and `GET /api/v1/auth/providers`, then `down`. Everything else in
`tests/test_dev_stack.py` is a hermetic test of the pure helpers (env assembly, path
layout, secret file modes, port resolution, readiness parsing) and never starts a real
process.

## Ports, generator and the browser

- **`--api-port` really moves the service.** `serve` binds `GUIDEFOLD_LISTEN`
  (`services/search/main.go`'s `listenAddress()`, default `:8080`) and the binary's own
  `healthcheck` subcommand probes the same value, so the port moves in one place.
  `stack.py` passes `GUIDEFOLD_LISTEN=127.0.0.1:<--api-port>`. The default is **8765**
  because that is the target `ui/vite.config.ts` proxies `/api` and `/v1` to, so the
  browser reaches the API same-origin and never needs CORS. `tests/test_dev_stack.py`
  asserts that default against the Vite config, so the two cannot drift apart silently.
- **`--generator` selects the `proposal.generate` backend**
  (`services/search/internal/review/generator/generator.go`'s `Select()`:
  `none|deterministic|openai|anthropic`). The default here is `deterministic` (recipe
  `det-1`, no network and no model), because a stack whose generation jobs all end
  `skipped` cannot exercise the review loop at all. Note that `det-1` extracts only from a
  document that holds an ordered procedure: it abstains on prose with
  `no_procedure_found`, which is why every `README.md` in `examples/monorepo` yields
  nothing.
- **`--ui` runs `pnpm dev`, not `pnpm preview`.** `ui/vite.config.ts` defines
  `server.proxy` only (for `vite dev`); its `preview` block has no `proxy`, so
  `vite preview` cannot reach the API same-origin. `stack.py` builds the UI first (as a
  typecheck/build gate) and then runs `pnpm --dir ui dev`.
- **`--ui` deliberately does not set `VITE_GUIDEFOLD_API`.** With it, `ui/src/api/client.ts`
  addresses a second origin, and the browser blocks the credentialed request because
  `services/search` sends no `Access-Control-*` headers. Unset, the client uses same-origin
  `/api` and `/v1`, which the dev server proxies to `127.0.0.1:8765`. Open the app at
  `http://127.0.0.1:4331/?mode=api` — the query parameter selects the API `DataSource`.
- **The worker runs with operator database credentials** (`PGUSER=postgres`), like
  `compose.yaml`'s `migrate` and `publish` services. `publish.build` writes the immutable
  catalog (`gf.snapshots`, `gf.skills`, `gf.heads`, `gf.router_*`), and
  `schema.grantsSQL` deliberately gives `guidefold_api` no INSERT there — only SELECT on
  `gf.*` plus INSERT on the two append-only event tables — so a compromised
  request-serving process cannot rewrite what every agent reads. A worker running as
  `guidefold_api` fails every publication with `permission denied for table snapshots`.
- **`/health/ready` may legitimately report `503 snapshot_not_published`** right after
  `up`, before anything has been imported and published into the `meridian` repo. It also
  reports on the *operator* tenant (`GUIDEFOLD_TENANT=local`), not on the organisations
  `seed` creates, so it stays 503 even after a successful organisation-scoped publication.
  `stack.py` treats `/health/live` as the up/down signal and prints the `/health/ready`
  body for information.

## A stack with data, end to end

```sh
export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH \
       GOPATH=$HOME/.cache/guidefold/gopath \
       GOMODCACHE=$HOME/.cache/guidefold/gopath/pkg/mod \
       GOCACHE=$HOME/.cache/guidefold/gocache
python3 tools/dev/stack.py up --ui --generator deterministic
python3 tools/dev/stack.py seed          # prints the ids as JSON
# then open http://127.0.0.1:4331/?mode=api&org=acme&repo=meridian
python3 tools/dev/stack.py down --stop-pg
```

The acceptance suite (`tests/acceptance/`, `GUIDEFOLD_ACCEPTANCE=1`) reuses these functions
rather than the subcommands: it brings up its own PostgreSQL and API/worker pair on free
ports under `.guidefold/acceptance/`, so it never overwrites a developer's running `up`.
