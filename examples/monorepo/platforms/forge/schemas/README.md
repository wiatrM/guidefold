# Forge schemas

Schema registry source for every dataset produced on the Forge platform.
One JSON Schema (draft 2020-12) per dataset, at `<domain>/<entity>_<grain>.schema.json`.

## Dataset naming

`<domain>.<entity>_<grain>`: lowercase snake_case, exactly one dot.

| Part   | Rule                                                              | Example    |
|--------|-------------------------------------------------------------------|------------|
| domain | one of the registered domains below                               | `fleet`    |
| entity | singular noun                                                     | `vehicle`  |
| grain  | `_current`, `_daily`, `_hourly`, `_event`, `_snapshot_<yyyymm>`   | `_daily`   |

Registered domains: `facilities`, `fleet`, `incidents`, `reference`, `telemetry`.
Adding a domain is a PR to forge-platform.

## Schema registry

- `forge datasets register <schema>` publishes a revision; the registry keeps every revision.
- Revisions must be backward compatible (additive nullable columns only); anything else is a new dataset name.
- Required columns on every dataset: `id`, `ingested_at`, `source_system`.

## Lineage tags

Each schema carries an `x-lineage` block and a classification label:

    x-lineage:
      producer: fleet.vehicle_daily          # pipeline name (equals the dataset name)
      inputs: [telemetry.vehicle_position_event, reference.vehicle_current]
      refresh: batch-daily                   # batch-daily | batch-hourly | streaming
    x-classification: internal

## Catalogue

| Dataset                          | Owner           | Refresh     |
|----------------------------------|-----------------|-------------|
| facilities.site_current          | forge-platform  | batch-daily |
| fleet.vehicle_daily              | pipelines-team  | batch-daily |
| telemetry.vehicle_position_event | streaming-team  | streaming   |
| incidents.incident_event         | streaming-team  | streaming   |
