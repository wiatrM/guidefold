---
name: geospatial-indexing
description: "[atlas/geo] Indexing conventions for geospatial layers in atlas: PostGIS geometry columns, companion H3 cell columns, GiST/GIN/BRIN index choice and the h3_index Go helpers. Use when creating or altering a table with a geometry column, writing a bounding-box, radius or containment query, choosing a layer's H3 resolution, or tuning a slow spatial query. Do not use for vector tile rendering (see map-tile-serving) or for non-spatial Postgres schema work."
license: Apache-2.0
compatibility: "Needs PostGIS 3.4+ with the h3 and h3_postgis extensions, psql, and Go 1.22+ for the index helpers."
metadata:
  scope: atlas.geo
  owner: geo-team
  requires: "urn:skill:meridian:_root:postgres-production"
  references: "platforms/atlas/geo/src/index/h3_index.go"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: team
  refines: "urn:skill:meridian:_root:postgres-production"
  triggers: "PostGIS geometry column, H3 cell index, GiST GIN BRIN, h3_index helpers, spatial bounding-box query, H3 resolution"
  negative_triggers: "vector tile rendering"
  digest: >-
    Atlas geo layers store geometry in PostGIS together with an H3 cell column at a fixed resolution
    per layer. Spatial queries filter by H3 cells first and refine with ST_ functions, and the index
    helpers in geo/src/index are the only code that computes cells.
---
# Geospatial indexing for atlas layers

## When to use / when NOT to use
Use this skill when you:
- create or alter a table under `platforms/atlas/geo/` that has a `geometry` or `geography` column
- add a query that filters by bounding box, radius, polygon containment or "nearby" semantics
- choose or change the H3 resolution of a layer
- investigate a slow spatial query (`EXPLAIN` shows a seq scan on a geometry column)
- touch the helpers in `platforms/atlas/geo/src/index/h3_index.go`

Do NOT use it for:
- rendering or caching vector tiles; that is `map-tile-serving`
- pooling, migration mechanics or failover; follow `_root:postgres-production`
- defining what a location object *means* in the ontology (forge.ontology owns that)

## Steps
1. Pick the layer's H3 resolution from the guide below and record it in the layer manifest
   (`layers/<layer>/manifest.yaml`, key `h3Resolution`). The resolution is immutable once data exists.
2. Write the migration under `platforms/atlas/geo/migrations/` using the `_root` naming scheme
   (`NNNN_<verb>_<table>.sql`). The table must have:
   - `geom geometry(Geometry, 4326) NOT NULL`
   - `h3_cells h3index[] NOT NULL` (every cell of the polygon at the layer resolution, or one cell for points)
   - `h3_res smallint NOT NULL` copied from the manifest so mixed-resolution rows are detectable
3. Add indexes in the same migration: `USING gist (geom)` and `USING gin (h3_cells)`. Append-only,
   time-ordered layers additionally get `USING brin (observed_at)`.
4. Populate `h3_cells` through `index.CellsForGeometry(geom, res)`; never compute cells ad hoc in SQL
   or inside a handler.
5. Write the query cell-first: filter with `h3_cells && index.CoverCells(bbox, res)`, then refine with
   `ST_Intersects` or `ST_DWithin` in the same `WHERE` clause, not in application code.
6. Run `EXPLAIN (ANALYZE, BUFFERS)` on the new query against the `geo-bench` fixture and paste the
   plan into the PR.

## Conventions specific to this scope
- SRID is always 4326 in storage. Reproject in the query (`ST_Transform`) only for distance maths;
  prefer a `geography` cast for radius searches under 500 km.
- H3 resolution guide: region-scale layers 4–5, city-scale layers 7–8, building-scale layers 10–11.
  Anything above 12 needs geo-team sign-off because of index size.
- `h3_cells` is capped at 2 048 cells per row (`index.MaxCellsPerRow`). Larger polygons are stored
  compacted (`index.CompactCells`) and expanded at query time.
- Column names: `geom` for the primary geometry, `centroid` for a derived point; never `geometry`,
  `shape` or `location`.
- Every spatial table has `observed_at timestamptz` and `source_layer text`; both are required by the
  tile pipeline and by audit queries.
- Never store latitude and longitude as two float columns; convert at ingest if a feed delivers them.
- Go code calls the `index.*` wrappers only, so the H3 library version is upgraded in one place.

## Verify
- `make -C platforms/atlas/geo migrate-check` applies the migration to a scratch database.
- `go test ./platforms/atlas/geo/src/index/...` passes, including the property test that the union of
  `CellsForGeometry` cells `ST_Covers` the input geometry.
- `psql -f platforms/atlas/geo/bench/queries.sql` prints plans; none may contain `Seq Scan` on a
  table with more than 100k rows.
- `SELECT count(*) FROM <table> WHERE h3_res <> <manifest resolution>` returns 0.

## See also
- urn:skill:meridian:_root:postgres-production (required)
- urn:skill:meridian:atlas.geo:map-tile-serving
- urn:skill:meridian:atlas:atlas-api-conventions
