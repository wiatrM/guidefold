# services/search/internal

Package main keeps the delivery contract (`/v1/search`, `/v1/use`,
`/v1/events:batch`) and the operator subcommands. Everything the product pivot
adds lives here, behind package boundaries, so a module can be reviewed and
replaced on its own.

| Package | Owns |
|---|---|
| `schema` | Every DDL statement, for both `gf` (immutable catalog) and `gfm` (management). `Migrate` holds the advisory lock, creates the `guidefold_api` role and its grants, and materialises per-snapshot BM25 tables. `Detect` reports the server's capabilities. |
| `testdb` | One throwaway PostgreSQL cluster per test process, from `GUIDEFOLD_PG_BIN`. `testdb.Main(m)` in `TestMain`, `testdb.Start(t)` for a migrated database. Skips with a clear message when the binaries are missing. |
| `mgmt` | The HTTP layer under `/api/`: route registration with `{org}`/`{repo}` wildcards, the JSON error envelope, `X-Request-Id`, `Cache-Control: no-store`, the 1 MiB body limit, the CSRF double submit, the idempotency replay and `Context.Authorize`/`Context.AuthorizeRepo`. `Stream` raises the body ceiling for one route (blob upload); `IdempotentLive` claims the key but re-runs the handler, for mutations whose body is a live view. |
| `identity` | Users, provider identities, organisations, memberships, invitations, sessions, personal/installation/CI tokens, the device flow, the audit log, and the per-request `Resolve` the delivery endpoints share. |
| `jobs` | The API–worker queue in `gfm.jobs`: enqueue inside the caller's transaction, lease, heartbeat, checkpoint, complete, fail with backoff, skip, cancel — every write fenced by generation. |
| `worker` | The runner: lease, heartbeat, run a handler, write the terminal state. `worker_handlers.go` in package main is the registry later modules fill. |
| `importer` | Repositories, scan manifests, blob upload, the import state machine and the `import.parse` job: everything between "a person points the CLI at a monorepo" and "the catalog holds skills". `domain/` holds the manifest rules, the package-resource derivation and the drift decisions, with no I/O. `BlobStore` is its outbound port — Postgres today, an object store later, without touching the domain. |
| `knowledge` | The read side of the catalog: skills and their facets, one skill and its immutable revisions, the exact bytes of a revision, the three maps, the module page, and the one write it owns — a judgment, which becomes an event in the ledger rather than a table of its own. |
| `usage` | The reporting side of the ledger: what the adapters did with the skills this organisation publishes, the owner's review queue, the CSV/JSON export and the adapter-health projection the ingest path writes. `domain/` holds the measure definitions — exposures, verified loads, context confirmation, applied episodes, judgments and their corrections — over decoded events, with no I/O. |
| `review` | Everything between "the catalog holds skills" and "a snapshot serves them": the generation plan, proposals and their provenance, the owner's decision, the patch that carries an approved candidate back to git, the publication that fills `gf.*`, and the admission rules both the decision and the publication apply. `generator/` is its outbound port — `none`, `deterministic` (recipe `det-1`, no network), `openai` and `anthropic` — so the same review pipeline runs in a test, offline and against a provider. |
| `graph` | The snapshot admission rules, moved out of `package main` unchanged: `requires`/`refines`/`replaced_by` must be acyclic, targets must exist, `refines` may not point deeper. `FindCycle` additionally names the loop, because a 422 has to tell an owner *which* skills form it. |
| `pivottest` | The shared test harness: one embedded PostgreSQL, one router with identity, import and knowledge mounted, one `httptest` server, plus the Meridian fixture helpers and the OpenAPI component checker. Imported only from `_test` files. |

Every module (`identity`, `importer`, `knowledge`, `review`, `usage`) registers its routes
with `mgmt.Router.Handle` and its job kinds with `RegisterHandlers`. They should not reach into each
other's tables: `knowledge` reads what `importer` wrote and never writes it back,
`usage` reads what both wrote and writes only an owner's decision, and none of
them touches `gf.*`, which only the publication job may fill — `usage` reads
`gf.events` and the delivery endpoint appends to it.

## The import pipeline

    guidefold scan  →  POST …/imports  →  PUT …/blobs/{sha}  →  POST …/finalize
                             │                                          │
                       manifest + file rows                 import.parse + publish.build
                                                                        │
                                       materialise blobs → build_tree.py → catalog + drift

The parse job materialises the manifest's files out of the blob store into a
private tree under `GUIDEFOLD_WORKER_DIR`, runs the repository's own trusted
`tools/worker/build_tree.py` over it, and writes `gfm.skills`,
`skill_revisions`, `skill_resources`, `documents`, `scopes`, `relations`, the
per-file outcomes and the drift decisions in **one** transaction, fenced by the
job's generation.

Four things about it are easy to get wrong.

**The worker needs Python and PyYAML; the API does not.** The builder is the
CLI's own parser, executed from the CLI's own bytes, so the catalog cannot
disagree with the ranker about what a `SKILL.md` says. The API image ships no
interpreter, and the worker never runs anything from the imported tree — the
tree is data.

**A restart must not duplicate rows.** Every write is an upsert keyed by a
digest: a revision id is `sha256(skill_id + "@" + content_sha256)`, a document
is unique on `(org, repo, path, sha256)`, a relation on its edge. The checkpoint
is an optimisation on top of that, not the thing that makes resuming safe.

**One broken file must not sink the import.** The snapshot builder is strict, so
a malformed `SKILL.md` aborts it. The builder therefore writes its inventory
*before* the snapshot; when the build fails the worker reads the inventory,
removes exactly the paths it names from its own materialised tree, and builds
again. Those files come back as `failed` and the import is `partial`.

**Drift observes, it never decides.** A changed source under a *published* skill
becomes `needs_review` plus one owner-queue item; a file missing from a
*complete* manifest archives its skill and keeps every revision. A partial scan
removes nothing, and re-running the same manifest adds nothing.

## What the usage numbers mean

    /v1/events:batch  →  gf.events  →  {repo_base}/usage  →  {repo_base}/usage/export
           │                                   │
     gfm.adapter_health              gfm.owner_queue + computed reasons

Four rules decide every number, and each one is a way the report would otherwise
lie.

**A server response is never evidence.** `/v1/use` answering 200 moves no
counter. An exposure exists because an adapter said it emitted a card, a load
because an adapter said it completed one. Nothing in `domain/` reads an HTTP
status (PRODUCT-PIVOT §9 AC2).

**Unknown is not zero.** A revision nobody judged has `feedback: null`, not five
zeros. A ratio with no denominator is `null`, not 0 %. An adapter that cannot
confirm the bytes reached the model's context produces `context_unknown`, which
is not a failed load. An organisation whose adapters never reported has
`oldest_lag_s: null`, not a healthy zero.

**Transport repetition is not use.** Exposures dedupe on `exposure_id`, verified
loads on `load_id`, applied episodes on `(task, skill, revision)`. A retried
batch is `duplicate` at the ledger and changes nothing — including the
adapter-health counters, which only accepted events feed.

**A correction replaces a judgment.** A `skill_feedback` event naming
`corrects_judgment_id` takes the place of the judgment it names, ordered by
`occurred_at`, so a late correction still wins. `tools/telemetry/report.py`,
the reference, has no notion of a correction and counts both votes; the parity
test compares exposures and loads with the reference and asserts the correction
against a value computed by hand.

Two more things are easy to get wrong. The ledger is organisation-scoped and
these endpoints are repository-scoped, so a row belongs here when the catalog
says its skill does, and a skill the catalog has never seen is still counted
without a scope or an owner. And the window is anchored on the **watermark** —
the newest `received_at` — not on the reader's clock, so two people looking at
different moments see the same numbers.

The review queue merges what the import worker wrote (`source_changed`,
`source_removed`, `missing_dependency`) with two reasons this module computes
from telemetry (`negative_feedback`, `zero_loads`). A computed item has the
stable identifier `<reason>:<skill_id>:<revision>` and can be decided like any
other; the decision writes a resolved `gfm.owner_queue` row whose `item_id` is
derived from that identifier, so the same observation neither returns nor
duplicates.

## The review pipeline

    plan → proposals:generate → proposal.generate → decision → export → git → import → publish.build
              (bounded, priced)      (provenance)    (reason)   (patch)          (bytes)   (validate → head)

Four things about it are easy to get wrong.

**Export is not publication.** Approving a candidate writes a revision with
`origin: human` and a patch; nothing is serving yet. The proposal becomes
`published` only when a later import carries the exported bytes at the same path
and digest, which is what `awaiting_git` means. A UI that collapses the two would
claim a change is live while the repository still disagrees.

**A draft never reaches SEARCH or USE.** The publication job materialises the
*import's* files, so a candidate that has not been exported and committed has no
bytes to publish. The rule holds by construction, not by a filter somebody has to
remember.

**Every field says where it came from.** A generated field carries a
`source_ref` naming the path, digest and line range it was read from, or
`needs_confirmation: true`. There is no third state, and a model's citation is
believed only when it points at a document the request actually supplied.

**The cache key is the dedupe rule.** `sha256(org, sorted input digests, recipe
version, model revision, candidate identity)` is unique per organisation, so a
restarted job produces no second candidate and a proposal an owner rejected is
never offered again. The checkpoint is an optimisation on top of that.

## Rules that are easy to break

**Every management write opens an explicit read-write transaction.** The
`guidefold_api` role runs with `default_transaction_read_only=on` so a mistake in
the catalog path cannot write to `gf.*`. `pool.Exec` on `gfm.*` therefore fails in
production and passes in a test run as the bootstrap superuser. Use
`Context.Tx`, `Service.tx` or `Queue.begin`.

**Tenant and repository are arguments, not process state.** The catalog cache is
keyed by `(tenant, repo, snapshot_id)` and `Catalog` carries its own tenant, so
every query that reads `gf.*` filters by the identity the request proved. The
legacy operator token is the one exception and keeps the configured tenant.

**Secrets are stored as SHA-256 and shown once.** Sessions, tokens, invitations,
device codes and OAuth states all follow the same rule. Nothing logs a token, a
cookie or an e-mail address; the log lines are allowlists of identifiers.

**Validation runs before the head moves.** Cycles in `requires`/`refines`, a
dependency that is not in the snapshot and a required package resource whose
bytes are missing all fail the publication and leave the previous head serving,
with the reasons in `gfm.publications.validation`. The same function runs at
approval, so an owner finds out that a candidate closes a cycle then rather than
two steps later. `similar` and `conflicts_with` are exempt from the cycle rule:
they are symmetric statements about two skills.

**1.2 is additive and nothing else.** A `1.1` request answers byte for byte as it
did before; the closure, the resource manifest and the `search_snapshot` check
run only when the caller asked for `1.2`. The two versions have separate schema
documents so a `1.1` request cannot carry a `1.2` field.

**Cross-organisation access is 403, never 404.** A non-member and a nonexistent
organisation must produce the same body, or the API becomes an existence oracle.
`mgmt.Forbidden()` is that body; there is a test that compares the two.

## Plain PostgreSQL profile

Tests and local development run on a stock server with neither `pg_search` nor
`pgvector`. `schema.Migrate` skips what it cannot build, the default `router`
engine reads `gf.router_terms` and needs neither, and `/health/ready` reports
`pg_search_version: "absent"`. See the "Plain Postgres profile" section of
[`../README.md`](../README.md) and `tools/dev/pg.py`.

## Tests

```sh
export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH
go test ./...          # skips database tests when GUIDEFOLD_PG_BIN has no binaries
go test -race ./...
```

The tests are API tests: `internal/testdb` plus `httptest.NewServer` over the real
handler and the development auth provider. `internal/identity/openapi_test.go`
validates the actual responses against the component schemas in
`openapi/management-v1.yaml` and checks that the document and the router describe
the same surface.
