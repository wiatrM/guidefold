from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "run_agent_tasks.py"
spec = importlib.util.spec_from_file_location("run_agent_tasks", MODULE)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


def _args(tasks, root, evaluator_root, output, fake_pi, skill, token):
    return type("Args", (), {
        "tasks": tasks, "workspace_root": root, "evaluator_root": evaluator_root,
        "output": output, "arm": "map+gate", "strategy": "flat",
        "guidefold_skill": skill, "token_file": token, "url": "http://127.0.0.1:8765",
        "bridge": Path("bridge.py"), "nodes_file": Path("nodes.json"),
        "pi_bin": f"{sys.executable} {fake_pi}", "provider": None, "model": None,
        "tools": "read,bash,edit,write,ls", "delivery_policy": "proof_gated",
        "timeout": 10.0, "resume": False,
    })()


def _fake_pi(path: Path) -> None:
    path.write_text(
        "import json, os, pathlib\n"
        "pathlib.Path('answer.txt').write_text('done')\n"
        "trace = pathlib.Path(os.environ['GUIDEFOLD_TRACE_FILE'])\n"
        "trace.parent.mkdir(parents=True, exist_ok=True)\n"
        "trace.write_text(json.dumps({'path':'/v1/search','elapsed_ms':2})+'\\n' + json.dumps({'path':'/v1/use','action':'ASK','body_chars':0,'elapsed_ms':3})+'\\n')\n"
        "answer = {'selected_skill_ids':['s'], 'used_skill_ids':[], 'answer':'ASK'}\n"
        "event = {'type':'message_end','message':{'role':'assistant','usage':{'input_tokens':11,'output_tokens':7},'content':[{'type':'text','text':json.dumps(answer)}]}}\n"
        "print(json.dumps(event))\n",
        encoding="utf-8",
    )


def test_agent_runner_scores_verifier_and_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_auth_available", lambda: True)
    root = tmp_path / "workspaces"
    source = root / "task-1"
    source.mkdir(parents=True)
    evaluator = tmp_path / "evaluator"
    evaluator.mkdir()
    (evaluator / "verify.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "root = Path(sys.argv[1])\n"
        "raise SystemExit(0 if (root / 'answer.txt').read_text() == 'done' else 1)\n",
        encoding="utf-8",
    )
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{
        "task_id": "task-1", "query": "create the answer file", "workspace": "task-1",
        "verifier": ["python3", "verify.py", "{workspace}"],
    }]), encoding="utf-8")
    fake = tmp_path / "fake_pi.py"
    _fake_pi(fake)
    rows = runner.run(_args(tasks, root, evaluator, tmp_path / "out", fake, tmp_path / "skill.md", tmp_path / "token"))
    row = rows[0]
    assert row["outcome"] == "success"
    assert row["harness_error"] is False
    assert row["search_requests"] == 1
    assert row["use_requests"] == 1
    assert row["ask_count"] == 1
    assert row["useful_delivery"] is None
    assert row["input_tokens"] == 11
    assert row["output_tokens"] == 7
    assert row["token_samples"] == 1


def test_agent_runner_rejects_workspace_escape_without_running_verifier(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_auth_available", lambda: True)
    root = tmp_path / "workspaces"
    root.mkdir()
    evaluator = tmp_path / "evaluator"
    evaluator.mkdir()
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{
        "task_id": "escape", "query": "x", "workspace": "../outside",
        "verifier": ["python3", "verify.py", "{workspace}"],
    }]), encoding="utf-8")
    fake = tmp_path / "fake_pi.py"
    _fake_pi(fake)
    rows = runner.run(_args(tasks, root, evaluator, tmp_path / "out", fake, tmp_path / "skill.md", tmp_path / "token"))
    assert rows[0]["outcome"] == "unknown"
    assert rows[0]["harness_error"] is True
    assert rows[0]["terminal_status"] == "workspace_missing_or_outside_root"


def test_agent_runner_keeps_verifier_failure_distinct_from_harness_error(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_auth_available", lambda: True)
    root = tmp_path / "workspaces"
    source = root / "task-1"
    source.mkdir(parents=True)
    evaluator = tmp_path / "evaluator"
    evaluator.mkdir()
    (evaluator / "verify.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{
        "task_id": "task-1", "query": "create the answer file", "workspace": "task-1",
        "verifier": ["python3", "verify.py", "{workspace}"],
    }]), encoding="utf-8")
    fake = tmp_path / "fake_pi.py"
    _fake_pi(fake)
    rows = runner.run(_args(tasks, root, evaluator, tmp_path / "out", fake, tmp_path / "skill.md", tmp_path / "token"))
    assert rows[0]["outcome"] == "failure"
    assert rows[0]["harness_error"] is False
    assert rows[0]["verifier_exit_code"] == 7
