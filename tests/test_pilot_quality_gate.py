import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "quality_gate.py"
spec = importlib.util.spec_from_file_location("quality_gate", MODULE)
quality_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(quality_gate)


def row(task_id, arm, outcome, *, useful=False, harmful=False):
    return {"task_id": task_id, "arm": arm, "outcome": outcome,
            "useful_delivery": useful, "harmful_load": harmful}


def test_gate_requires_real_e2_and_preserves_unknowns():
    rows = [
        row("t1", "flat", "success", useful=True),
        row("t1", "map+gate+evolution", "success", useful=True),
        row("t2", "flat", "failure"),
        row("t2", "map+gate+evolution", "unknown"),
    ]
    report = quality_gate.evaluate(rows)
    assert report["verdict"] == "inconclusive"
    assert report["arms"]["map+gate+evolution"]["unknown"] == 1
    assert "E2 conflict/revision trigger cases" in report["missing_evidence"]


def test_rows_accepts_a_single_json_object_jsonl_file(tmp_path):
    path = tmp_path / "one-row.jsonl"
    path.write_text('{"task_id":"t1","arm":"flat","outcome":"success"}\n', encoding="utf-8")
    rows = quality_gate._rows(path)
    assert rows == [{"task_id": "t1", "arm": "flat", "outcome": "success"}]


def test_gate_passes_only_with_zero_harmful_trigger_deliveries_and_coverage():
    rows = []
    for i in range(100):
        task = f"t{i}"
        for arm in ("flat", "map+gate+evolution"):
            rows.append(row(task, arm, "success", useful=True))
    e2 = [
        {"scenario": "conflict", "harmful": True, "expected_action": "ASK", "actual_action": "ASK"}
        for _ in range(100)
    ]
    report = quality_gate.evaluate(rows, e2)
    assert report["verdict"] == "pass"
    assert all(report["checks"].values())
    assert report["e2"]["harmful_loads"] == 0


def test_gate_fails_when_conflicting_body_is_loaded():
    rows = []
    for i in range(100):
        task = f"t{i}"
        for arm in ("flat", "map+gate+evolution"):
            rows.append(row(task, arm, "success", useful=True))
    e2 = [{"scenario": "conflict", "harmful": True, "expected_action": "ASK", "actual_action": "LOAD", "conflicting": True}]
    report = quality_gate.evaluate(rows, e2)
    assert report["verdict"] == "fail"
    assert report["e2"]["stale_conflict_deliveries"] == 1
    assert not report["checks"]["zero_stale_or_conflicting_body_delivery"]


def test_gate_rejects_duplicate_task_arm_rows():
    rows = [
        row("t1", "flat", "success", useful=True),
        row("t1", "map+gate+evolution", "success", useful=True),
        row("t1", "map+gate+evolution", "success", useful=True),
    ]
    report = quality_gate.evaluate(rows, [
        {"harmful": True, "expected_action": "ASK", "actual_action": "ASK"}
        for _ in range(100)
    ])
    assert report["verdict"] == "inconclusive"
    assert report["duplicate_task_arm_rows"] == [("t1", "map+gate+evolution")]


def test_gate_rejects_mismatched_frozen_inputs():
    rows = [
        {"task_id": "t1", "arm": "flat", "outcome": "success", "useful_delivery": True,
         "task_bank_sha256": "bank-a", "verifier_sha256": "verify-a"},
        {"task_id": "t1", "arm": "map+gate+evolution", "outcome": "success", "useful_delivery": True,
         "task_bank_sha256": "bank-b", "verifier_sha256": "verify-b"},
    ]
    report = quality_gate.evaluate(rows, [
        {"harmful": True, "expected_action": "ASK", "actual_action": "ASK"}
        for _ in range(100)
    ])
    assert report["verdict"] == "inconclusive"
    assert "task bank hashes differ across arms" in report["missing_evidence"]
    assert "verifier hashes differ for a paired task" in report["missing_evidence"]


def test_quality_gate_reports_execution_telemetry_and_preserves_missing_as_unknown():
    rows = []
    for arm in quality_gate.ARMS:
        rows.extend([
            {
                "task_id": f"{arm}-1", "arm": arm, "outcome": "success",
                "harness_error": False,
                "telemetry": {"search_requests": 2, "use_requests": 1, "ask_count": 1,
                               "input_tokens": 100, "output_tokens": 25, "tool_calls": 3,
                               "elapsed_ms": 40},
            },
            {"task_id": f"{arm}-2", "arm": arm, "outcome": "failure",
             "terminal_status": "timeout", "elapsed_ms": 60},
        ])
    report = quality_gate.evaluate(rows, [
        {"harmful": True, "expected_action": "ASK", "actual_action": "ASK"}
        for _ in range(100)
    ])
    execution = report["arms"]["map+gate+evolution"]["execution"]
    assert execution == {
        "harness_errors": 1,
        "search_requests": 2,
        "search_results": None,
        "search_errors": None,
        "use_requests": 1,
        "ask_count": 1,
        "input_tokens": 100,
        "output_tokens": 25,
        "tool_calls": 3,
        "elapsed_ms": 100,
        "elapsed_samples": 2,
        "avg_elapsed_ms": 50.0,
    }
    missing = quality_gate.evaluate([
        {"task_id": "t", "arm": "flat", "outcome": "success"},
    ], None)["arms"]["flat"]["execution"]
    assert missing["search_requests"] is None
    assert missing["elapsed_ms"] is None


def test_quality_gate_marks_missing_usefulness_as_inconclusive():
    rows = [
        {"task_id": "t1", "arm": "flat", "outcome": "success"},
        {"task_id": "t1", "arm": "map+gate+evolution", "outcome": "success"},
    ]
    report = quality_gate.evaluate(rows, [
        {"harmful": True, "expected_action": "ASK", "actual_action": "ASK"}
        for _ in range(100)
    ])
    assert report["verdict"] == "inconclusive"
    assert report["arms"]["map+gate+evolution"]["useful_coverage"] is None
    assert any("useful-delivery" in item for item in report["missing_evidence"])


def test_harmful_bound_excludes_unknown_observations_without_calling_them_safe():
    report = quality_gate.evaluate([
        {"task_id": "t1", "arm": "flat", "outcome": "success", "harmful_load": None},
        {"task_id": "t1", "arm": "map+gate+evolution", "outcome": "success", "harmful_load": None},
    ], [{"harmful": True, "expected_action": "ASK", "actual_action": "ASK"} for _ in range(100)])
    assert report["arms"]["flat"]["harmful_load_upper_95"] is None
    assert report["arms"]["map+gate+evolution"]["harmful_load_upper_95"] is None
