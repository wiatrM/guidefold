---
name: ontology-modeling
description: "[forge/ontology] How to define object types, properties, and link types in the Forge ontology backed by Postgres. Use when adding a new object type, adding properties to an unreleased type, or introducing a link between object types. Do not use for changing an object type that already holds rows in a released ontology version (that is object-type-migrations) or for dataset schemas."
license: Apache-2.0
compatibility: "Needs a checkout of platforms/forge/ontology and forge-cli; a local Postgres 16 from docker compose is sufficient."
metadata:
  scope: forge.ontology
  owner: ontology-team
  references: "platforms/forge/ontology/schema/object-types.yaml"
  status: active
  since: "2026-09-04"
  kind: knowledge
  layer: team
  triggers: "object-types.yaml, define object type, link type cardinality, backingDataset primaryKey, titleProperty, forge ontology compile"
  digest: >-
    Ontology object types, properties, and links are declared in object-types.yaml and compiled
    into Postgres tables by forge-cli. Each object type maps to exactly one backing dataset with a
    single-column primary key, and links are declared on the side that owns the foreign key.
---
# Ontology modelling on Forge

## When to use / when NOT to use
Use when you:
- add a new object type (for example `Facility`, `Vehicle`, `Incident`) to `platforms/forge/ontology/schema/object-types.yaml`,
- add properties to an object type that has not yet shipped in a tagged ontology release,
- introduce a link type between two object types,
- decide which dataset backs an object type.

Do NOT use when:
- the object type exists in a released ontology version and has rows: follow `forge.ontology:object-type-migrations`,
- you are changing the dataset schema itself (`forge:dataset-conventions`),
- you need geospatial indexes on properties; that is owned by `atlas.geo`.

## Steps
1. Draft the object type under `objectTypes:` in `platforms/forge/ontology/schema/object-types.yaml`.
   Required keys: `id` (PascalCase), `backingDataset`, `primaryKey`, `titleProperty`, `properties`.
2. Declare each property with `name` (camelCase), `type` (`string`, `integer`, `double`, `boolean`,
   `timestamp`, `date`, `geopoint`, `geoshape`, or `array<...>`), and `nullable`.
3. Declare links under `linkTypes:` with `id`, `from`, `to`, `cardinality` (`one-to-many` | `many-to-many`),
   and `foreignKey` on the `from` side. Many-to-many links must name a `joinDataset`.
4. Compile locally: `forge ontology compile platforms/forge/ontology/schema/ --out build/ontology/`.
   This generates the Postgres DDL plus the Go and TypeScript typings.
5. Apply to a local database: `forge ontology apply --db "$DEV_DB_URL" build/ontology/`.
6. Add or update the fixture `platforms/forge/ontology/fixtures/<ObjectType>.jsonl` (3 to 10 rows).
7. Open a PR labelled `ontology`; ontology-team reviews naming, the backing dataset owner reviews mappings.

## Conventions specific to this scope
- Object type ids are singular PascalCase nouns (`Facility`, not `Facilities`). Link ids are
  `<From>At<To>` / `<From>AssignedTo<To>` style verb phrases, never bare concatenations.
- Exactly one `backingDataset` per object type, named per `forge:dataset-conventions`; the dataset's
  `id` column is the `primaryKey`. Composite keys are not allowed.
- `titleProperty` must be a non-nullable string; the analyst workspace renders it in lists and search results.
- Property names never repeat the object type name (`Facility.name`, not `Facility.facilityName`).
- Time is `timestamp` (UTC) or `date`; never model time as `string`.
- Every object type carries `classification` (string, non-nullable) copied from the dataset's `x-classification`.
- Enumerations are `string` plus an `enum:` list; the compiler emits a CHECK constraint.
- Derived or aggregated values are not properties; expose them as a separate object type backed by a
  `_daily` or `_current` dataset.
- Keep `objectTypes` sorted by id and `linkTypes` sorted by `from`, then `to`; lint enforces order.
- `ontologyVersion` at the top of the file is bumped only by the release process, never in a modelling PR.

## Verify
```bash
forge ontology lint platforms/forge/ontology/schema/               # naming, key, link, ordering rules
forge ontology compile platforms/forge/ontology/schema/ --check    # compiles without warnings
forge ontology apply --dry-run --db "$DEV_DB_URL" build/ontology/
pytest platforms/forge/ontology/tests -k fixtures                   # fixtures load against the compiled DDL
```

## See also
- urn:skill:meridian:forge.ontology:object-type-migrations
- urn:skill:meridian:forge:dataset-conventions
