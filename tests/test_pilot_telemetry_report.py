"""Independent replay checks for the end-to-end quality scorecard."""

import importlib.util
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "guidefold_telemetry_report", ROOT / "tools" / "pilot" / "telemetry_report.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


R = _load()


def test_replay_counts_task_routing_safety_and_cost_without_collapsing_unknown():
    rows = [
        {"event_type": "task_started", "task_id": "t1"},
        {
            "event_type": "search_requested", "search_id": "s1",
            "task_id": "t1",
        },
        {
            "event_type": "search_results", "search_id": "s1", "status": "ok",
            "timings": {"total_ms": 40}, "task_id": "t1",
        },
        {"event_type": "skill_load_requested", "task_id": "t1"},
        {
            "event_type": "skill_load_completed", "status": "ask", "task_id": "t1",
        },
        {
            "event_type": "task_finished", "task_id": "t1", "outcome": "success",
            "terminal_status": "completed", "input_tokens": 100,
            "output_tokens": 25, "tool_calls": 2, "duration_ms": 500,
        },
        {
            "event_type": "task_finished", "task_id": "t2", "outcome": "partial",
            "terminal_status": "harness_error", "duration_ms": 200,
        },
    ]

    report = R.summarize(rows)

    assert report["tasks"] == {
        "started": 1, "finished": 2, "succeeded": 1, "failed": 0,
        "unknown": 1, "success_rate": 0.5, "known_success_rate": 1.0,
    }
    assert report["harness"] == {"errors": 1}
    assert report["routing"] == {
        "search_requests": 1, "search_results": 1, "search_errors": 0,
        "use_requests": 1, "ask_count": 1,
    }
    assert report["cost_time"] == {
        "input_tokens": 100, "output_tokens": 25, "total_tokens": 125,
        "tool_calls": 2, "latency_ms": 740, "latency_samples": 3,
        "avg_latency_ms": 740 / 3,
    }
    assert report["coverage"]["task_ids_present"] is True
    assert report["coverage"]["cost_observed"] is True


def test_replay_accepts_nested_ledger_payload_and_unknown_measurements():
    rows = [{
        "event_id": "e1", "event_type": "task_finished",
        "payload": {
            "task_id": "t1", "outcome": "unknown",
            "terminal_status": "timeout",
        },
    }]
    report = R.summarize([R._flatten(row) for row in rows])
    assert report["tasks"]["unknown"] == 1
    assert report["tasks"]["success_rate"] == 0.0
    assert report["tasks"]["known_success_rate"] is None
    assert report["harness"]["errors"] == 1
    assert report["cost_time"]["total_tokens"] is None
    assert report["coverage"]["cost_observed"] is False


def test_json_loader_supports_jsonl_and_json_object(tmp_path):
    event = {"event_type": "search_requested", "search_id": "s1"}
    jsonl = tmp_path / "events.jsonl"
    jsonl.write_text(json.dumps(event) + "\n", encoding="utf-8")
    assert len(R._event_rows(jsonl)) == 1

    wrapped = tmp_path / "events.json"
    wrapped.write_text(json.dumps({"events": [event]}), encoding="utf-8")
    assert len(R._event_rows(wrapped)) == 1
