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
