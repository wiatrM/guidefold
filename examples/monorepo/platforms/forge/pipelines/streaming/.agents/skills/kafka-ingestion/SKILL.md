---
name: kafka-ingestion
description: "[forge/pipelines/streaming] Building Kafka ingestion jobs with Spark Structured Streaming: topic declaration, consumer groups, checkpointing, dead-letter handling, and landing into Forge _event datasets. Use when adding a topic to config/topics.yaml, writing or changing a streaming consumer, or tuning retention and checkpoint settings. Do not use for scheduled batch pipelines or for Kafka producers owned by other platforms."
license: Apache-2.0
compatibility: "Needs the pipelines virtualenv plus a local single-broker Kafka (`make kafka-up` via docker compose); cluster credentials are not needed for local work."
metadata:
  scope: forge.pipelines.streaming
  owner: streaming-team
  requires: "urn:skill:meridian:forge.pipelines:spark-pipeline-conventions, urn:skill:meridian:forge:dataset-conventions"
  references: "platforms/forge/pipelines/streaming/config/topics.yaml#retentionMs"
  status: active
  since: "2026-09-04"
  digest: >-
    Streaming consumers are StreamingPipeline subclasses that read one declared Kafka topic,
    checkpoint to their own path, and merge records into an _event dataset by idempotency key.
    Topics, partitions, and retentionMs are declared in topics.yaml and reviewed by streaming-team.
---
# Kafka ingestion

## When to use / when NOT to use
Use when you:
- declare a new topic or change `retentionMs`, `partitions`, or `schemaRef` in
  `platforms/forge/pipelines/streaming/config/topics.yaml`,
- write or modify a consumer under `platforms/forge/pipelines/streaming/src/meridian_streaming/consumers/`,
- change checkpointing, trigger interval, watermark, or dead-letter handling.

Do NOT use when:
- the job runs on a schedule and reads tables or files (`forge.pipelines:spark-pipeline-conventions`),
- you are producing to Kafka from another platform; producers own their schema and contract tests,
- you only need to name the landing dataset (`forge:dataset-conventions`).

## Steps
1. Declare the topic in `config/topics.yaml`: `name`, `partitions`, `retentionMs`, `schemaRef`
   (Avro schema path), `owner`, `landingDataset`.
2. Create `consumers/<domain>/<entity>_event.py` subclassing `StreamingPipeline` (itself a `BasePipeline`).
   Set `topic`, `output_dataset` (must end in `_event`), and `idempotency_key`.
3. Implement `transform(df)` on the decoded Avro payload; keep it pure, same rules as batch.
4. Implement `validate(df)`; malformed records go to `<topic>.dlq` through `self.dead_letter(df, reason)`.
5. Set `checkpoint_path = f"checkpoints/{self.name}"` relative to the streaming root; never share checkpoints.
6. Run locally: `make kafka-up && forge streaming run <name> --local --from-beginning`.
7. Publish sample events with `forge streaming produce <topic> --file tests/events/<entity>.jsonl` and
   confirm rows land in the `_event` dataset.
8. Open a PR labelled `streaming`; streaming-team reviews topic config, the dataset owner reviews the landing schema.

## Conventions specific to this scope
- Topic names: `meridian.<domain>.<entity>.<version>` (`meridian.fleet.vehicle-position.v1`). A version bump
  is a new topic; the old one stays until `retentionMs` drains it.
- `retentionMs` is mandatory and explicit even when it equals the default of 7 days (`604800000`).
  Anything above 30 days needs a reason comment next to the value in `topics.yaml`.
- Partitions: minimum 3, always a multiple of 3; changing partition count means a new topic version.
- Consumer group id equals the pipeline `name`; one consumer group per topic per landing dataset.
- Trigger interval defaults to `30 seconds`; `availableNow` is only for backfills and runs with `--once`.
- Exactly-once is a `MERGE` on `idempotency_key` into the `_event` dataset; never rely on Kafka offsets alone.
- Checkpoints are never deleted by hand. To reprocess, deploy a new consumer with `--reset-offsets earliest`
  under a change ticket.
- Payloads are Avro with a registered schema; JSON is accepted only on `*.dlq` topics.
- Watermark is `ingested_at` with 10 minutes of allowed lateness; late records go to the `_late` partition, not the DLQ.
- SASL credentials come from the mounted `kafka-auth` secret, never from `topics.yaml` or code.

## Verify
```bash
forge streaming lint platforms/forge/pipelines/streaming/config/topics.yaml   # names, retentionMs present, partitions % 3
forge streaming run <name> --local --from-beginning --max-batches 3
forge datasets lint platforms/forge/schemas/<domain>/<entity>_event.schema.json
pytest platforms/forge/pipelines/streaming/tests -k <entity>
```

## See also
- urn:skill:meridian:forge.pipelines:spark-pipeline-conventions
- urn:skill:meridian:forge:dataset-conventions
- urn:skill:meridian:forge.pipelines:pipeline-testing
