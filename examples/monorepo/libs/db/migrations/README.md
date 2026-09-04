# Database migrations

Meridian uses golang-migrate (the `migrate` CLI) for every Postgres schema. This directory holds the
migrations for the shared `libs/db` schema (lookup tables and the `classification_label` domain type);
each service keeps its own under `<service>/migrations/` with the same rules.

## Naming

```
000001_create_schema.up.sql
000001_create_schema.down.sql
000002_add_classification_domain.up.sql
000002_add_classification_domain.down.sql
```

- Sequential six-digit prefix from `migrate create -seq`; never a timestamp, never reused.
- Short snake_case description of what the migration does.
- Both `.up.sql` and `.down.sql` are mandatory; a no-op down file contains a comment explaining why.

## Rules

- Forward-only: never edit a merged migration, add a new one.
- Start every `up` with `SET lock_timeout = '5s';` and use `CREATE INDEX CONCURRENTLY` on existing tables.
- Large-table changes follow the two-phase pattern described in the root `postgres-production` skill.
- CI runs `up`, `down 1`, `up` against a fresh Postgres 15 container.

## Commands

```bash
migrate create -ext sql -dir libs/db/migrations -seq add_something
migrate -path libs/db/migrations -database "$DATABASE_URL" up
migrate -path libs/db/migrations -database "$DATABASE_URL" version
```
