# Ontology migrations

Numbered migrations for object types and link types that already exist in a tagged ontology release.
Unreleased types are edited directly in `../schema/object-types.yaml` and need no migration.

## Layout

    migrations/
      0001_add_Facility_location/
        migration.yaml     # objectType, kind, deprecates, backfill
        expand.sql         # additive: new nullable columns, CREATE INDEX CONCURRENTLY, view aliases
        contract.sql       # destructive: guarded by `-- requires-release: <version>`

## Rules

1. Directories are zero-padded, monotonically increasing, never renumbered or reused.
2. One migration touches exactly one object type or one link type.
3. Expand ships in release N; contract ships no earlier than release N+1.
4. Renames are add-new + backfill + view alias + drop-old-later, never `ALTER COLUMN ... RENAME`.
5. Drops need `deprecatedSince` on the property in `object-types.yaml` for at least one release.
6. Type changes are widen-only (`integer` to `bigint`, `string` to `text`).
7. Backfills over one million rows run as a Forge batch pipeline named in `migration.yaml`.
8. Indexes are created `CONCURRENTLY` in `expand.sql` only.
9. Lock and statement timeouts follow the root Postgres production skill.
10. Every migration PR carries the `ontology-migration` label and a rollback note.

`forge ontology migrate lint` enforces 1, 2, 3, and 8; reviewers check the rest.
