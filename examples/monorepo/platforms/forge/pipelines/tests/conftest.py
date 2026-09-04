"""Session-wide pytest fixtures for Forge batch pipeline tests.

Per-domain fixtures live in tests/jobs/<domain>/conftest.py.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone

import pytest
from pyspark.sql import SparkSession

_ids = itertools.count(1)


def fake_id(prefix: str) -> str:
    return f"{prefix}-{next(_ids):06d}"


def make_df(spark: SparkSession, rows: list[dict], schema: str):
    return spark.createDataFrame(rows, schema=schema)


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", default=False)


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("meridian-pipelines-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def sample_vehicles(spark):
    ts = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = [
        {"id": fake_id("VEH"), "call_sign": "V-01", "in_service": True, "ingested_at": ts},
        {"id": fake_id("VEH"), "call_sign": "V-02", "in_service": False, "ingested_at": ts},
    ]
    return make_df(spark, rows, "id string, call_sign string, in_service boolean, ingested_at timestamp")
