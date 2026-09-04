---
name: object-type-migrations
description: "[forge/ontology] Migrating released ontology object types: adding, renaming, widening, or dropping properties and links on types that already hold rows in Postgres. Use when changing an object type that exists in a tagged ontology version. Do not use for brand-new object types (ontology-modeling) or for application-table migrations outside the ontology."
license: Apache-2.0
compatibility: "Needs forge-cli, psql, and read access to a staging Postgres with a production-shaped ontology; production apply is done by the release pipeline only."
metadata:
  scope: forge.ontology
  owner: ontology-team
  requires: "urn:skill:meridian:forge.ontology:ontology-modeling, urn:skill:meridian:_root:postgres-production"
  references: "platforms/forge/ontology/migrations/README.md"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: team
  refines: "urn:skill:meridian:_root:postgres-production"
  triggers: "object type migration, expand contract phase, migration.yaml, backfill batches, rename property, ontology release version"
  digest: >-
    Changes to released object types are expressed as numbered migration directories under
    ontology/migrations and applied in expand and contract phases so readers never see a broken type.
    Renames and drops need a deprecation window of at least one ontology release.
---
# Object type migrations

## When to use / when NOT to use
Use when an object type or link type present in a tagged ontology release (`ontology/v*`) needs to
change: new property, property rename, type widening, dropped property, changed link cardinality, or
a different backing dataset.

Do NOT use when:
- the object type is not yet released; edit `object-types.yaml` directly (`forge.ontology:ontology-modeling`),
- you are migrating non-ontology tables; application schemas follow `_root:postgres-production` on their own,
- the change is only inside the backing dataset and the compiled columns are unaffected.

## Steps
1. Edit `platforms/forge/ontology/schema/object-types.yaml` to the target state.
2. Generate the skeleton: `forge ontology migrate new --name <verb>_<ObjectType>_<detail>` creates
   `platforms/forge/ontology/migrations/NNNN_<name>/{migration.yaml,expand.sql,contract.sql}`.
3. Fill `migration.yaml`: `objectType`, `kind` (`add-property` | `rename-property` | `drop-property` |
   `widen-type` | `change-link` | `rebackfill`), `deprecates` (old names), `backfill` (SQL file or pipeline name).
4. Write `expand.sql`: additive only (new nullable column, `CREATE INDEX CONCURRENTLY`, view alias for old name).
5. Write `contract.sql`: the destructive half, guarded by a `-- requires-release: <next-version>` header.
6. Apply to a staging snapshot: `forge ontology migrate apply --phase expand --db "$STAGING_DB_URL"`.
7. Run the backfill and the compatibility tests (see Verify). Attach timing output to the PR.
8. Ship the expand phase in release N; the contract phase ships in release N+1 at the earliest.

## Conventions specific to this scope
- Migration directories are zero-padded, monotonically increasing, and never renumbered or reused.
- One migration touches exactly one object type or one link type. Multi-type changes are several migrations.
- Renames are never `ALTER COLUMN ... RENAME`; they are add-new, backfill, view alias, drop-old-later.
- Drops require `deprecatedSince` on the property in `object-types.yaml` for at least one release.
- Type changes are widen-only (`integer` to `bigint`, `string` to `text`). Narrowing is a new property.
- Backfills over one million rows run as a Forge batch pipeline, not inline SQL; name it in `migration.yaml`.
- Index creation always uses `CONCURRENTLY` and lives in `expand.sql`, never in `contract.sql`.
- Lock timeouts, statement timeouts, and batch sizes follow `_root:postgres-production` exactly.
- Migration PRs carry the `ontology-migration` label and a rollback note describing how to undo `expand`
  if `contract` never ships.
- The rules in `platforms/forge/ontology/migrations/README.md` are the authoritative checklist for reviewers.

## Verify
```bash
forge ontology migrate lint platforms/forge/ontology/migrations/            # numbering, one-type rule, phase guards
forge ontology migrate apply --phase expand --dry-run --db "$STAGING_DB_URL"
pytest platforms/forge/ontology/tests/migrations -k NNNN                    # old readers still resolve the type
forge ontology diff --from ontology/v<prev> --to HEAD                       # only the expected properties changed
```

## See also
- urn:skill:meridian:forge.ontology:ontology-modeling
- urn:skill:meridian:_root:postgres-production
- urn:skill:meridian:forge:dataset-conventions
