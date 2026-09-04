"""Base class for Forge batch pipelines.

Subclasses implement ``read``, ``transform`` and ``validate``; ``write`` has a default
Delta implementation. ``run`` owns lineage columns and the idempotent partition overwrite.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession, functions as F


class ValidationError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BasePipeline(ABC):
    name: str
    output_dataset: str
    inputs: tuple[str, ...] = ()

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.log = logging.getLogger(f"meridian_pipelines.{self.name}")

    @abstractmethod
    def read(self, spark: SparkSession) -> dict[str, DataFrame]: ...

    @abstractmethod
    def transform(self, inputs: dict[str, DataFrame]) -> DataFrame: ...

    def validate(self, df: DataFrame) -> None:
        self.expect(df.filter(F.col("id").isNull()).limit(1).count() == 0, "null_primary_key")

    def write(self, df: DataFrame, run_date: str) -> None:
        (df.write.format("delta").mode("overwrite")
           .option("replaceWhere", f"ingested_date = '{run_date}'")
           .saveAsTable(self.output_dataset))

    def expect(self, condition: bool, code: str, message: str = "") -> None:
        if not condition:
            raise ValidationError(code, message or self.name)

    def run(self, spark: SparkSession, run_date: str, run_id: str) -> None:
        df = self.transform(self.read(spark))
        df = (df.withColumn("ingested_at", F.lit(datetime.now(timezone.utc)))
                .withColumn("pipeline_run_id", F.lit(run_id)))
        self.validate(df)
        self.write(df, run_date)
