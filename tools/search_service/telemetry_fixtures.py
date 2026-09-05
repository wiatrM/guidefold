#!/usr/bin/env python3
"""Export the reference ledger vocabulary and validation cases for the Go port."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.telemetry import ledger
from tools.serve_spike.repository import canonical


def main():
    schema = {
        "schema_versions": ledger.SCHEMA_VERSIONS,
        "environments": ledger.ENVIRONMENTS,
        "verdicts": ledger.VERDICTS,
        "event_types": ledger.EVENT_TYPES,
        "envelope_required": ledger.ENVELOPE_REQUIRED,
        "required_fields": ledger.REQUIRED_FIELDS,
        "reference_sha256": hashlib.sha256(
            Path(ledger.__file__).read_bytes()
        ).hexdigest(),
    }
    # The constants, not the reference storage implementation, define this ID.
    (ROOT / "services/search/telemetry-schema.json").write_bytes(
        canonical(schema) + b"\n"
    )
    events = [None, [], "bad", {}, {"event_id": ""}, {"event_id": 5}]
    for kind in ledger.EVENT_TYPES:
        event = {
            "schema_version": "1.0",
            "event_id": "event-" + kind,
            "event_type": kind,
            "occurred_at": "2026-09-05T12:34:56Z",
            "sequence": 1,
            "producer": "fixture",
            "adapter_version": "1",
            "environment": "dev",
        }
        event.update(
            {field: "value" for field in ledger.REQUIRED_FIELDS[kind]["required"]}
        )
        event.update(
            {field: None for field in ledger.REQUIRED_FIELDS[kind]["nullable"]}
        )
        if kind == "skill_feedback":
            event["verdict"] = "helped"
        events.append(event)
        for key in (
            list(ledger.ENVELOPE_REQUIRED)
            + list(ledger.REQUIRED_FIELDS[kind]["required"])
            + list(ledger.REQUIRED_FIELDS[kind]["nullable"])
        ):
            bad = copy.deepcopy(event)
            bad.pop(key)
            events.append(bad)
        for key, value in [
            ("schema_version", "future"),
            ("event_type", "unknown"),
            ("environment", "prod"),
            ("occurred_at", "yesterday"),
            ("occurred_at", "2026-09-05T12:00:00"),
            ("occurred_at", "2026-09-05T14:00:00+02:00"),
            ("occurred_at", "2026-09-05 12:00:00.123456+00:00"),
        ]:
            altered = copy.deepcopy(event)
            altered[key] = value
            events.append(altered)
    rows = []
    for event in events:
        try:
            ledger._validate(event)
            reason = ""
        except ledger.RejectionError as e:
            reason = str(e)
        rows.append({"event": event, "reason": reason})
    (ROOT / "services/search/testdata/telemetry.json").write_bytes(
        canonical(rows) + b"\n"
    )
    print(json.dumps({"validation_cases": len(rows)}))


if __name__ == "__main__":
    main()
