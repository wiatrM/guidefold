import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "run_verifiers.py"
spec = importlib.util.spec_from_file_location("run_verifiers", MODULE)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


def invoke(tasks, root, arm="map+gate+evolution", timeout=1.0):
    task_file = root / "tasks.json"
    output = root / "rows.jsonl"
    task_file.write_text(json.dumps(tasks), encoding="utf-8")
    rows = runner.run(SimpleNamespace(tasks=task_file, workspace_root=root, arm=arm, timeout=timeout))
    return rows


def test_runner_reports_success_failure_and_timeout(tmp_path):
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    (tmp_path / "slow").mkdir()
    py = sys.executable
    rows = invoke([
        {"task_id": "ok", "workspace": "ok", "verifier": [py, "-c", "raise SystemExit(0)"]},
        {"task_id": "bad", "workspace": "bad", "verifier": [py, "-c", "raise SystemExit(3)"]},
        {"task_id": "slow", "workspace": "slow", "verifier": [py, "-c", "import time; time.sleep(2)"]},
    ], tmp_path, timeout=0.05)
    assert [row["outcome"] for row in rows] == ["success", "failure", "unknown"]
    assert rows[2]["terminal_status"] == "timeout"
    assert rows[2]["harness_error"] is True
    assert all(row["arm"] == "map+gate+evolution" for row in rows)
    assert rows[0]["useful_delivery"] is None
    assert rows[0]["harmful_load"] is None


def test_runner_rejects_workspace_escape_and_invalid_spec(tmp_path):
    rows = invoke([
        {"task_id": "escape", "workspace": "../outside", "verifier": [sys.executable, "-c", "pass"]},
        {"task_id": "missing-verifier", "workspace": ".", "verifier": []},
    ], tmp_path)
    assert rows[0]["terminal_status"] == "workspace_outside_root"
    assert rows[1]["terminal_status"] == "invalid_task_spec"
    assert all(row["outcome"] == "unknown" for row in rows)


def test_runner_rejects_duplicate_task_ids(tmp_path):
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps([
        {"task_id": "same", "workspace": ".", "verifier": [sys.executable, "-c", "pass"]},
        {"task_id": "same", "workspace": ".", "verifier": [sys.executable, "-c", "pass"]},
    ]), encoding="utf-8")
    try:
        runner.run(SimpleNamespace(tasks=task_file, workspace_root=tmp_path, arm="flat", timeout=1))
    except ValueError as exc:
        assert "duplicate task_id" in str(exc)
    else:
        raise AssertionError("duplicate tasks must be rejected")
