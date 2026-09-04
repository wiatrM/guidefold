---
name: spark-pipeline-conventions
description: "[forge/pipelines] Structure, naming, and lifecycle hooks for PySpark batch pipelines in the meridian_pipelines package. Use when creating or modifying a batch pipeline, adding a transform, or registering a pipeline in the scheduler catalogue. Do not use for streaming Kafka consumers or for dataset naming rules."
license: Apache-2.0
compatibility: "Needs Python 3.12, PySpark 3.5, and the platforms/forge/pipelines virtualenv (`make venv`); no cluster access required for local runs."
metadata:
  scope: forge.pipelines
  owner: pipelines-team
  references: "platforms/forge/pipelines/src/meridian_pipelines/base.py"
  status: active
  since: "2026-09-04"
  digest: >-
    Batch pipelines subclass BasePipeline and implement read, transform, validate, and optionally
    write hooks; the base class owns session handling, lineage columns, and idempotent partition
    overwrites. One pipeline per output dataset, one module per pipeline, registered in the catalogue.
---
# Spark pipeline conventions

## When to use / when NOT to use
Use when you:
- add a new batch pipeline under `platforms/forge/pipelines/src/meridian_pipelines/jobs/`,
- change a transform, validation, or write step in an existing pipeline,
- register a pipeline in `platforms/forge/pipelines/catalogue.yaml` for scheduling.

Do NOT use when:
- the job consumes Kafka and runs continuously (`forge.pipelines.streaming:kafka-ingestion`),
- the question is what to call the output dataset (`forge:dataset-conventions`),
- you are only writing or fixing tests (`forge.pipelines:pipeline-testing`).

## Steps
1. Create `src/meridian_pipelines/jobs/<domain>/<entity>_<grain>.py`: one module per output dataset.
2. Subclass `BasePipeline` from `src/meridian_pipelines/base.py`; set `name`, `output_dataset`, `inputs`.
3. Implement the hooks: `read(spark) -> dict[str, DataFrame]`, `transform(inputs) -> DataFrame`,
   `validate(df) -> None` (raise `ValidationError`), and `write(df, run_date)` only if the default Delta write is wrong.
4. Keep `transform` pure: no I/O, no `spark.read`, no side effects. All I/O belongs in `read` and `write`.
5. Register the pipeline in `platforms/forge/pipelines/catalogue.yaml` with `schedule`, `owner`, `sla_minutes`.
6. Run locally: `forge pipelines run <name> --local --date 2026-09-01`.
7. Add tests per `forge.pipelines:pipeline-testing` and open a PR labelled `pipeline`.

## Conventions specific to this scope
- Module, class, and `name` are one identifier in three casings: `fleet/vehicle_daily.py`,
  `VehicleDailyPipeline`, `fleet.vehicle_daily`. The `name` equals the output dataset name.
- Never call `SparkSession.builder` inside a job; use the session passed into `BasePipeline.run()`.
- Column expressions use `pyspark.sql.functions` (`F.col`, `F.lit`); string SQL is allowed only in `read` for pushdown.
- Every output has `ingested_at` and `pipeline_run_id`; `BasePipeline.run` adds them before `validate`.
- Writes are idempotent per partition: `mode("overwrite")` with `replaceWhere` on the run date. No appends in batch.
- Validation is mandatory: at minimum non-null `id` and row-count bounds, via `self.expect(condition, code)`.
- UDFs only when no native function exists; they live in `src/meridian_pipelines/udfs/` with a benchmark note.
- Configuration comes from `self.config` (loaded from `catalogue.yaml`); jobs never read environment variables.
- Log through `self.log` (structured JSON); `print()` fails lint.
- Dependencies between pipelines are declared in `inputs`, never implied by scheduling order.
- Spark settings (`shuffle.partitions`, memory) are set in the catalogue entry, not in code.

## Verify
```bash
ruff check platforms/forge/pipelines/src && ruff format --check platforms/forge/pipelines/src
forge pipelines lint platforms/forge/pipelines/catalogue.yaml            # names match modules and datasets
forge pipelines run <name> --local --date 2026-09-01 --dry-run            # plan only; prints resolved lineage
pytest platforms/forge/pipelines/tests -k <entity>
```

## See also
- urn:skill:meridian:forge.pipelines:pipeline-testing
- urn:skill:meridian:forge:dataset-conventions
