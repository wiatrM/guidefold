---
name: dataset-conventions
description: "[forge] Naming, schema registration, and lineage tagging rules for datasets produced or consumed on the Forge data-integration platform. Use when creating a new dataset, renaming or re-partitioning an existing one, or registering a schema in the Forge schema registry. Do not use for ontology object types (forge.ontology) or for Kafka topic definitions (forge.pipelines.streaming)."
license: Apache-2.0
compatibility: "Needs a checkout of platforms/forge and forge-cli (`forge datasets ...`) in PATH; no cluster access required."
metadata:
  scope: forge
  owner: forge-platform
  references: "platforms/forge/schemas/README.md"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: platform
  triggers: "dataset naming domain.entity_grain, schema registry, x-lineage tags, forge datasets register, grain suffix, schema evolution"
  digest: >-
    Every Forge dataset is named <domain>.<entity>_<grain>, registered in the schema registry
    before its first write, and tagged with lineage metadata pointing at the producing pipeline.
    Schema changes are additive by default; breaking changes mean a new dataset name.
---
# Forge dataset conventions

## When to use / when NOT to use
Use this skill when you:
- create a dataset under `platforms/forge/**` (batch or streaming output),
- rename, re-partition, or change the schema of an existing dataset,
- register or update a schema in the Forge schema registry,
- add or fix lineage tags on a dataset.

Do NOT use it for:
- ontology object types, links, or properties (`forge.ontology:ontology-modeling`),
- Kafka topic naming and retention (`forge.pipelines.streaming:kafka-ingestion`),
- PySpark job structure (`forge.pipelines:spark-pipeline-conventions`).

## Steps
1. Pick the name: `<domain>.<entity>_<grain>`, e.g. `fleet.vehicle_daily`, `facilities.site_current`.
   Registered domains are listed in `platforms/forge/schemas/README.md`; add a new one via PR to forge-platform.
2. Write the schema file `platforms/forge/schemas/<domain>/<entity>_<grain>.schema.json`
   (JSON Schema draft 2020-12, one top-level object, `additionalProperties: false`).
3. Register it: `forge datasets register platforms/forge/schemas/<domain>/<entity>_<grain>.schema.json`.
   The command fails if the name is taken or the schema is not backward-compatible with the last revision.
4. Fill the `x-lineage` block: `producer` (pipeline name), `inputs` (upstream dataset names),
   `refresh` (`batch-daily`, `batch-hourly`, `streaming`).
5. Add the dataset to the catalogue table in `platforms/forge/schemas/README.md` with owner and refresh cadence.
6. Open the PR with the `dataset` label; forge-platform reviews naming and lineage, the domain team reviews columns.

## Conventions specific to this scope
- Names are lowercase snake_case; the only dot separates domain from entity. No environment prefixes
  (`dev_`, `prod_`): environments are selected by the writer, never encoded in the name.
- Grain suffixes are fixed: `_current` (latest state), `_daily`, `_hourly`, `_event` (append-only),
  `_snapshot_<yyyymm>`. Anything else fails `forge datasets lint`.
- Every dataset has `id` (string, stable), `ingested_at` (timestamp, UTC), and `source_system` (string).
- Timestamps are ISO-8601 UTC; no local-time columns. Geometries are WKT strings with a `_wkt` suffix.
- Schema evolution: adding nullable columns is allowed in place. Removing or retyping a column requires a
  new dataset name (`_v2` suffixes are forbidden; change the grain or entity) plus a deprecation note in the README.
- Partitioning defaults to `ingested_date`; override only with a written reason in the `x-partitioning` block.
- Every schema carries `x-classification` using the platform classification labels.
- Lineage tags are mandatory; `forge datasets lint` rejects schemas without `x-lineage.producer`.
- The producing pipeline's `name` must equal the dataset name, so lineage is resolvable without a lookup table.

## Verify
```bash
forge datasets lint platforms/forge/schemas/                     # naming, required columns, lineage block
forge datasets diff <domain>.<entity>_<grain> --against registry  # backward-compat vs last registered revision
grep -n "x-lineage" platforms/forge/schemas/<domain>/<entity>_<grain>.schema.json
```
CI runs `forge datasets lint` on every PR that touches `platforms/forge/schemas/**`.

## See also
- urn:skill:meridian:forge.ontology:ontology-modeling
- urn:skill:meridian:forge.pipelines.streaming:kafka-ingestion
