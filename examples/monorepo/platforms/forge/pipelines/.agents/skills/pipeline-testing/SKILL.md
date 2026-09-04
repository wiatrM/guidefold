---
name: pipeline-testing
description: "[forge/pipelines] Unit and golden-file testing of PySpark batch pipelines with pytest, a local SparkSession, and shared conftest fixtures. Use when adding or changing tests for a pipeline, fixing a flaky Spark test, or adding a fixture to conftest.py. Do not use for integration runs against a cluster or for testing streaming consumers."
license: Apache-2.0
compatibility: "Needs the platforms/forge/pipelines virtualenv with pytest, pyspark, and chispa installed; runs on a laptop with a local Spark master."
metadata:
  scope: forge.pipelines
  owner: pipelines-team
  requires: "urn:skill:meridian:forge.pipelines:spark-pipeline-conventions"
  references: "platforms/forge/pipelines/tests/conftest.py"
  status: active
  since: "2026-09-04"
  digest: >-
    Pipeline tests exercise the transform and validate hooks against small in-memory DataFrames
    built from conftest fixtures, plus one golden-file test per output dataset. Tests are
    deterministic, cluster-free, and finish in under thirty seconds per module.
---
# Pipeline testing

## When to use / when NOT to use
Use when you:
- add tests for a new or changed pipeline under `platforms/forge/pipelines/tests/`,
- add or change a fixture in `platforms/forge/pipelines/tests/conftest.py`,
- update golden outputs after an intentional transform change,
- debug a flaky or slow Spark test.

Do NOT use when:
- you need an end-to-end run against staging (`forge pipelines run --env staging`, owned by CI),
- you are testing a Kafka consumer (`forge.pipelines.streaming:kafka-ingestion` has its own harness),
- the change is in the pipeline code itself (`forge.pipelines:spark-pipeline-conventions`).

## Steps
1. Mirror the job path: `tests/jobs/<domain>/test_<entity>_<grain>.py` for `jobs/<domain>/<entity>_<grain>.py`.
2. Use the `spark` fixture from `conftest.py` (session-scoped, `local[2]`, two shuffle partitions).
3. Build inputs with `make_df(spark, rows, schema)` or the domain fixtures (`sample_vehicles`, `sample_facilities`).
4. Test `transform` directly: `Pipeline().transform({"vehicles": df})`, then
   `chispa.assert_df_equality(actual, expected, ignore_row_order=True, ignore_nullable=True)`.
5. Test `validate` with one passing DataFrame and at least one failing one (`pytest.raises(ValidationError)`).
6. Add the golden test: `tests/golden/<name>/input.jsonl` and `expected.jsonl`; `test_golden` is
   parametrised by `pytest_generate_tests` in conftest, so only the files are needed.
7. Regenerate goldens on purpose with `pytest --update-golden -k <name>` and review the diff in the PR.

## Conventions specific to this scope
- No test touches the network, a real Delta table, or a path outside `tmp_path`.
- Every test module runs in under 30 s locally; anything slower is `@pytest.mark.slow` with a justification.
- Row order is never asserted; use `ignore_row_order=True`. Sort explicitly only when testing sort logic.
- Timestamps in fixtures are explicit UTC (`datetime(2026, 9, 1, tzinfo=timezone.utc)`), never `now()`.
- Use `ignore_nullable=True`; nullability drift is caught by the golden schema check, not unit tests.
- Golden files hold at most 50 rows and no real identifiers; use the `fake_id("VEH")` helper.
- Fixtures are named for what they contain (`sample_incidents`), not for the test that uses them.
- `conftest.py` at the tests root exposes only session-wide fixtures; per-domain fixtures live in
  `tests/jobs/<domain>/conftest.py`.
- A failing validation test asserts on the error `code` attribute, not on the message text.
- Coverage gate: `transform` and `validate` at 100 % line coverage per pipeline; `read` and `write` are excluded.

## Verify
```bash
cd platforms/forge/pipelines && pytest -q -m "not slow"
pytest -q --cov=meridian_pipelines --cov-report=term-missing tests/jobs/<domain>
pytest -q tests/golden -k <name>
pytest --collect-only -q | grep -c "test_"          # sanity: new tests are collected
```

## See also
- urn:skill:meridian:forge.pipelines:spark-pipeline-conventions
- urn:skill:meridian:forge:dataset-conventions
