---
name: postgres-production
description: "[meridian] Production Postgres conventions shared by every Meridian service: schema migrations with golang-migrate, connection pooling through libs/db and pgxpool, index, locking and timeout rules, and backup or restore expectations. Use when you add or change a migration, tune pool settings such as maxConns, write a hot-path query or bring up a new Postgres-backed service. Do not use for analytical Spark datasets, the Kafka layer or throwaway local dev databases."
license: Apache-2.0
compatibility: "Needs the migrate CLI (golang-migrate), psql 15+ and a Go toolchain for libs/db."
metadata:
  scope: _root
  owner: platform-engineering
  references: "libs/db/migrations/README.md, libs/db/pool.go#maxConns"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: org
  triggers: "Postgres migration, golang-migrate, maxConns pool size, pgxpool, lock_timeout, hot-path query"
  negative_triggers: "Spark dataset, Kafka topic, local dev database"
  digest: >-
    Every Meridian service that owns a Postgres database uses libs/db for pooling and golang-migrate for
    forward-only, numbered SQL migrations. Pool sizes, lock timeouts and index rules are fixed here so that
    ontology, geo and identity services behave the same under load and during upgrades.
---

# Postgres in production

## When to use / when NOT to use
Use when you:
- add, edit or squash a migration under any `**/migrations/` directory;
- change `libs/db/pool.go` or a service's pool settings (`maxConns`, `MinConns`, lifetimes);
- write a query that runs on a request path or in a scheduled job;
- create a new Postgres-backed service or database.

Do not use for Spark or Parquet datasets in forge, for Kafka topic configuration, or for throwaway
databases in `docker-compose.dev.yaml`; those have their own conventions.

## Steps
1. Create the migration pair: `migrate create -ext sql -dir <service>/migrations -seq <short_name>`.
   This yields `000012_add_object_type_index.up.sql` and the matching `.down.sql`.
2. Write the `up` file so it is safe on a live database: `SET lock_timeout = '5s';` at the top,
   `CREATE INDEX CONCURRENTLY`, `ADD COLUMN` without a volatile default.
3. Write the `down` file even when it is a no-op comment; CI refuses migrations without one.
4. Open the pool with `db.NewPool(ctx, cfg)` from `libs/db`. Do not construct `pgxpool.Config` by hand;
   lower `MaxConns` only through the service config file and justify it in the PR. Raising it above the
   `maxConns` ceiling needs platform-engineering review.
5. In CI run `migrate -path <dir> -database "$DATABASE_URL" up`, then `down 1`, then `up` again against a
   fresh container to prove reversibility.
6. For hot queries paste an `EXPLAIN (ANALYZE, BUFFERS)` excerpt into the PR description.
7. If the change touches a table over 10 million rows, announce it in the release notes and use the
   two-phase pattern: add nullable column, backfill in batches, add constraint `NOT VALID`, validate.

## Conventions specific to this scope
- Migrations are sequential, six-digit, forward-only. Never edit a merged migration; add a new one.
- One schema per service, named after the node (`atlas_identity`, `forge_ontology`). Cross-service access
  goes through APIs, never foreign keys across schemas.
- `maxConns` defaults to 20 per replica and must stay below `max_connections / replicas - 10`. The constant
  lives in `libs/db/pool.go`; services read it, they do not redefine it.
- `statement_timeout` is 30s for request paths and 15m for jobs, set per role, not per query.
- Primary keys are `bigint generated always as identity` or UUIDv7; no natural composite keys.
- Every table has `created_at` and `updated_at` (`timestamptz`); a trigger keeps `updated_at` current.
- Indexes are named `<table>_<cols>_idx`, unique ones `<table>_<cols>_key`; partial indexes need a comment.
- Backups: WAL archiving plus nightly base backups; restore drills are part of the quarterly release check.
- Secrets come from the platform secret store; `DATABASE_URL` is never committed, not even for tests.

## Verify
```bash
migrate -path libs/db/migrations -database "$DATABASE_URL" version   # database is at the expected version
go test ./libs/db/...                                              # pool config and helpers
! grep -rn "pgxpool.New(" --include=*.go platforms/                # no direct pool construction
psql "$DATABASE_URL" -c "select count(*) from pg_stat_activity"      # stays under maxConns * replicas
```

## See also
- urn:skill:meridian:forge.ontology:object-type-migrations
- urn:skill:meridian:atlas.geo:geospatial-indexing
