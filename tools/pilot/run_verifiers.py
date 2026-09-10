#!/usr/bin/env python3
"""Run pre-written hidden task verifiers and emit task-level replay rows.

The verifier command is an argv list from an evaluator-only task bank; it is never passed through
a shell. Workspaces must be children of ``--workspace-root``. A timeout, missing workspace or
invalid task specification produces an explicit ``unknown`` row and a harness error rather than a
false failure or success. The output is directly consumable by ``quality_gate.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any


def _load(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if isinstance(value, dict):
        value = value.get("tasks") or value.get("rows") or []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("task bank must be a JSON list, JSONL, or an object with tasks/rows")
    seen: set[str] = set()
    for row in value:
        task_id = str(row.get("task_id") or row.get("id") or "")
        if not task_id:
            raise ValueError("every task needs task_id")
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
    return value, hashlib.sha256(raw).hexdigest()


def _unknown(task_id: str, arm: str, reason: str, *, task_bank_sha256: str, verifier_sha256: str = "") -> dict[str, Any]:
    return {"task_id": task_id, "arm": arm, "outcome": "unknown", "terminal_status": reason,
            "harness_error": True, "task_bank_sha256": task_bank_sha256,
            "verifier_sha256": verifier_sha256, "useful_delivery": False,
            "harmful_load": False, "elapsed_ms": None}


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks, bank_sha = _load(args.tasks)
    root = args.workspace_root.resolve()
    rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("task_id") or task.get("id"))
        verifier = task.get("verifier")
        if not isinstance(verifier, list) or not verifier or any(not isinstance(x, str) or not x for x in verifier):
            rows.append(_unknown(task_id, args.arm, "invalid_task_spec", task_bank_sha256=bank_sha))
            continue
        verifier_sha = hashlib.sha256(json.dumps(verifier, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        raw_workspace = task.get("workspace")
        if not isinstance(raw_workspace, str) or not raw_workspace:
            rows.append(_unknown(task_id, args.arm, "invalid_workspace", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha))
            continue
        workspace = (root / raw_workspace).resolve()
        try:
            workspace.relative_to(root)
        except ValueError:
            rows.append(_unknown(task_id, args.arm, "workspace_outside_root", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha))
            continue
        if not workspace.is_dir():
            rows.append(_unknown(task_id, args.arm, "workspace_missing", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha))
            continue
        timeout = task.get("timeout_seconds", args.timeout)
        try:
            timeout = float(timeout)
            if timeout <= 0:
                raise ValueError
        except (TypeError, ValueError):
            rows.append(_unknown(task_id, args.arm, "invalid_timeout", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha))
            continue
        started = time.perf_counter()
        try:
            completed = subprocess.run(verifier, cwd=workspace, capture_output=True, text=True,
                                       timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            row = _unknown(task_id, args.arm, "timeout", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha)
            row.update({"elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                        "stdout": (exc.stdout or "")[-4000:], "stderr": (exc.stderr or "")[-4000:]})
            rows.append(row)
            continue
        except OSError as exc:
            row = _unknown(task_id, args.arm, "verifier_start_error", task_bank_sha256=bank_sha, verifier_sha256=verifier_sha)
            row.update({"elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "stderr": str(exc)[-4000:]})
            rows.append(row)
            continue
        rows.append({"task_id": task_id, "arm": args.arm,
                     "outcome": "success" if completed.returncode == 0 else "failure",
                     "terminal_status": "completed", "harness_error": False,
                     "verifier_exit_code": completed.returncode, "task_bank_sha256": bank_sha,
                     "verifier_sha256": verifier_sha,
                     "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:],
                     "useful_delivery": False, "harmful_load": False,
                     "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)
    rows = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"status": "PASS", "rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
