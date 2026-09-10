#!/usr/bin/env python3
"""Replay an execution telemetry log into the E6.7 quality scorecard.

This is deliberately a small, stdlib-only companion to ``tools/pilot/analyze.py``.
It summarizes raw task/harness events; it does not infer task success from a
skill load and it never converts missing observations into zeroes.  Input may
be JSONL, a JSON list, or ``{"events": [...]}``.  Event payloads nested under
``payload`` are accepted for exported ledger rows.

    python3 tools/pilot/telemetry_report.py --events run.jsonl --json-out report.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUCCESS = {"success", "succeeded", "pass", "passed"}
FAILURE = {"failure", "failed", "fail"}


def _event_rows(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if "events" in parsed or "rows" in parsed:
                parsed = parsed.get("events", parsed.get("rows", []))
            else:
                # A one-line JSONL file is also valid JSON. Treat an object
                # carrying an event marker as one event instead of silently
                # turning it into an empty report.
                parsed = [parsed] if any(key in parsed for key in ("event_type", "type", "payload")) else []
        if isinstance(parsed, list):
            rows = parsed
        else:
            raise ValueError("JSON root must be a list or an events/rows object")
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("every telemetry event must be an object")
    return [_flatten(row) for row in rows]


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten an exported ledger row without allowing payload to overwrite IDs."""
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return dict(row)
    result = dict(payload)
    for key, value in row.items():
        if key != "payload" or key not in result:
            result[key] = value
    if "event_type" not in result and isinstance(row.get("type"), str):
        result["event_type"] = row["type"]
    return result


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str):
            return value.strip().lower()
    return ""


def _number(row: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip():
            try:
                return int(float(value))
            except ValueError:
                continue
    return None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tasks_started = tasks_finished = tasks_succeeded = tasks_failed = tasks_unknown = 0
    harness_errors = search_requests = search_results = search_errors = 0
    use_requests = ask_count = input_tokens = output_tokens = tool_calls = latency_ms = 0
    latency_samples = 0
    task_ids: set[str] = set()
    for row in rows:
        kind = _text(row, "event_type", "type")
        task_id = _text(row, "task_id")
        if task_id:
            task_ids.add(task_id)
        if kind == "task_started":
            tasks_started += 1
        elif kind == "task_finished":
            tasks_finished += 1
            outcome = _text(row, "outcome")
            if outcome in SUCCESS:
                tasks_succeeded += 1
            elif outcome in FAILURE:
                tasks_failed += 1
            else:
                tasks_unknown += 1
            terminal = _text(row, "terminal_status", "status")
            if any(word in terminal for word in ("harness", "error", "timeout")):
                harness_errors += 1
            for key, target in (("input_tokens", "input"), ("output_tokens", "output"), ("tool_calls", "tools")):
                value = _number(row, key)
                if value is not None:
                    if target == "input":
                        input_tokens += value
                    elif target == "output":
                        output_tokens += value
                    else:
                        tool_calls += value
            value = _number(row, "duration_ms")
            if value is not None:
                latency_ms += value
                latency_samples += 1
        elif kind == "search_requested":
            search_requests += 1
        elif kind == "search_results":
            search_results += 1
            status = _text(row, "status")
            if status and status not in {"ok", "abstained"}:
                search_errors += 1
            timings = row.get("timings")
            if isinstance(timings, dict):
                value = _number(timings, "total_ms")
                if value is not None:
                    latency_ms += value
                    latency_samples += 1
        elif kind == "skill_load_requested":
            use_requests += 1
        elif kind == "skill_load_completed":
            status = _text(row, "status", "delivery_status")
            if status in {"ask", "denied"}:
                ask_count += 1
        elif kind in {"harness_error", "harness_failed"}:
            harness_errors += 1

    observed_tasks = tasks_started + tasks_finished > 0
    cost_observed = any(_number(row, key) is not None for row in rows for key in ("input_tokens", "output_tokens", "tool_calls"))
    latency_observed = latency_samples > 0
    finished_known = tasks_succeeded + tasks_failed
    return {
        "coverage": {
            "events": len(rows),
            "task_ids_present": bool(task_ids),
            "tasks_observed": observed_tasks,
            "cost_observed": cost_observed,
            "latency_observed": latency_observed,
        },
        "tasks": {
            "started": tasks_started,
            "finished": tasks_finished,
            "succeeded": tasks_succeeded,
            "failed": tasks_failed,
            "unknown": tasks_unknown,
            "success_rate": (tasks_succeeded / tasks_finished if tasks_finished else None),
            "known_success_rate": (tasks_succeeded / finished_known if finished_known else None),
        },
        "harness": {"errors": harness_errors},
        "routing": {
            "search_requests": search_requests,
            "search_results": search_results,
            "search_errors": search_errors,
            "use_requests": use_requests,
            "ask_count": ask_count,
        },
        "cost_time": {
            "input_tokens": input_tokens if cost_observed else None,
            "output_tokens": output_tokens if cost_observed else None,
            "total_tokens": input_tokens + output_tokens if cost_observed else None,
            "tool_calls": tool_calls if cost_observed else None,
            "latency_ms": latency_ms if latency_observed else None,
            "latency_samples": latency_samples,
            "avg_latency_ms": latency_ms / latency_samples if latency_observed else None,
        },
        "notes": [
            "Unknown outcomes and missing observations are preserved; unknown is not zero.",
            "Counts are event counts. Deduplication and paired-task inference belong to the ledger/analyze tools.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = summarize(_event_rows(args.events))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
