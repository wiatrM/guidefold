#!/usr/bin/env python3
"""Run isolated Pi agent tasks and score them with evaluator-only verifiers.

The runner is intentionally separate from the retrieval-only Pi benchmark.  Each task is copied
into a temporary workspace, Pi may edit only that copy, and a verifier command is executed after
the agent exits.  A verifier exit code is a task result; timeout, invalid task data, or an agent
failure is ``unknown`` with ``harness_error=true``.  The emitted JSONL is consumable by
``quality_gate.py`` and keeps delivery usefulness/harmfulness unknown unless telemetry or a
separate E2 label supplies it.

Task bank example::

    {"task_id":"t-01", "query":"...", "workspace":"fixtures/t-01",
     "verifier":["python3", "verify.py", "{workspace}"], "timeout_seconds":60}

No verifier command is run through a shell.  Verifiers are run from a separate evaluator root and
are never copied into the temporary Pi directory; ``{workspace}`` is replaced by its isolated
workspace path.  The agent receives neither the task bank nor evaluator labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any


def _load_tasks(path: Path) -> tuple[list[dict[str, Any]], str]:
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
        if not isinstance(row.get("query"), str) or not row["query"].strip():
            raise ValueError(f"{task_id}: query is required")
        verifier = row.get("verifier")
        if not isinstance(verifier, list) or not verifier or any(not isinstance(x, str) or not x for x in verifier):
            raise ValueError(f"{task_id}: verifier must be a non-empty argv list")
        if not isinstance(row.get("workspace"), str) or not row["workspace"]:
            raise ValueError(f"{task_id}: workspace is required")
    return value, hashlib.sha256(raw).hexdigest()


def _auth_available() -> bool:
    if any(os.environ.get(name) for name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN", "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    )):
        return True
    auth_file = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".pi/agent"))) / "auth.json"
    try:
        return auth_file.is_file() and auth_file.stat().st_size > 2
    except OSError:
        return False


def _pi_command(args: argparse.Namespace) -> list[str]:
    command = shlex.split(args.pi_bin) if args.pi_bin else ["npx", "--yes", "@earendil-works/pi-coding-agent"]
    command += ["--mode", "json", "--no-session", "--no-skills", "--no-context-files",
                "--tools", args.tools, "--skill", str(args.guidefold_skill), "-p"]
    if args.provider:
        command += ["--provider", args.provider]
    if args.model:
        command += ["--model", args.model]
    return command


def _parse_final(stdout: str) -> tuple[dict[str, Any], bool]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    texts: list[str] = []
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        content = message.get("content") or []
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
                if isinstance(block.get("text"), str):
                    texts.append(block["text"])
    final = texts[-1] if texts else ""
    candidates = [final] + re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", final, flags=re.S)
    candidates += ([re.search(r"\{.*\}", final, flags=re.S).group(0)]
                   if re.search(r"\{.*\}", final, flags=re.S) else [])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value, True
    return {}, False


def _trace_metrics(path: Path) -> dict[str, Any]:
    metrics = {"search_requests": 0, "use_requests": 0, "ask_count": 0,
               "loaded_body_chars": 0, "trace_elapsed_ms": 0.0, "trace_rows": 0}
    if not path.is_file():
        return metrics
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        metrics["trace_rows"] += 1
        endpoint = row.get("path")
        if endpoint == "/v1/search":
            metrics["search_requests"] += 1
        elif endpoint == "/v1/use":
            metrics["use_requests"] += 1
            if str(row.get("action") or "").upper() == "ASK":
                metrics["ask_count"] += 1
            body_chars = row.get("body_chars")
            if isinstance(body_chars, (int, float)) and not isinstance(body_chars, bool):
                metrics["loaded_body_chars"] += body_chars
        elapsed = row.get("elapsed_ms")
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
            metrics["trace_elapsed_ms"] += elapsed
    return metrics


def _unknown(task_id: str, arm: str, reason: str, bank_sha: str, verifier_sha: str = "") -> dict[str, Any]:
    return {"task_id": task_id, "arm": arm, "outcome": "unknown", "terminal_status": reason,
            "harness_error": True, "task_bank_sha256": bank_sha, "verifier_sha256": verifier_sha,
            "useful_delivery": None, "harmful_load": None, "elapsed_ms": None}


def _safe_relative(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _run_verifier(argv: list[str], cwd: Path, timeout: float) -> tuple[str, bool, int | None, str, str, float]:
    started = time.perf_counter()
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return "unknown", True, None, (exc.stdout or "")[-4000:], (exc.stderr or "")[-4000:], elapsed
    except OSError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return "unknown", True, None, "", str(exc)[-4000:], elapsed
    elapsed = (time.perf_counter() - started) * 1000
    return ("success" if result.returncode == 0 else "failure"), False, result.returncode, \
        result.stdout[-4000:], result.stderr[-4000:], elapsed


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks, bank_sha = _load_tasks(args.tasks)
    root = args.workspace_root.resolve()
    evaluator_root = args.evaluator_root.resolve()
    if not evaluator_root.is_dir():
        raise SystemExit(f"evaluator root does not exist: {evaluator_root}")
    if not _auth_available():
        raise SystemExit("Pi auth not found; authenticate Pi before running agent tasks")
    command = _pi_command(args)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "agent-results.jsonl"
    if results_path.exists() and not args.resume:
        raise SystemExit(f"{results_path} exists; use --resume or another --output")
    done: dict[str, dict[str, Any]] = {}
    if args.resume:
        for line in results_path.read_text(encoding="utf-8").splitlines() if results_path.exists() else []:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("task_id"):
                done[str(row["task_id"])] = row
    mode = "a" if args.resume else "w"
    with results_path.open(mode, encoding="utf-8") as results:
        for task in tasks:
            task_id = str(task.get("task_id") or task.get("id"))
            if task_id in done:
                continue
            source = _safe_relative(root, str(task["workspace"]))
            verifier = [str(x) for x in task["verifier"]]
            verifier_sha = hashlib.sha256(json.dumps(verifier, separators=(",", ":")).encode()).hexdigest()
            if source is None or not source.is_dir():
                row = _unknown(task_id, args.arm, "workspace_missing_or_outside_root", bank_sha, verifier_sha)
                results.write(json.dumps(row, ensure_ascii=False) + "\n"); results.flush(); continue
            task_started = time.perf_counter()
            trace = output / "traces" / f"{task_id}.jsonl"
            events_file = output / "events" / f"{task_id}.jsonl"
            trace.parent.mkdir(parents=True, exist_ok=True); events_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"guidefold-agent-{task_id}-") as temp:
                workspace = Path(temp) / "workspace"
                shutil.copytree(source, workspace)
                task_file = workspace / ".guidefold-task.txt"
                task_file.write_text(task["query"] + "\n", encoding="utf-8")
                prompt = (f"You are executing task {task_id} in the isolated workspace {workspace}. "
                          f"Read {task_file}. You MUST use the native Go Guidefold bridge. Run this "
                          f"SEARCH command first: python3 {args.bridge} search --strategy flat "
                          f"--query-file {task_file} --nodes-file {args.nodes_file}. Then run USE for "
                          f"every selected card with delivery policy "
                          f"{args.delivery_policy}. If USE returns delivery.action=ASK, do not use "
                          "that body. You may edit files only inside this workspace and run local "
                          "tests. Do not inspect parent directories, evaluator files, task banks, "
                          "labels or secrets. Finish with one JSON object containing "
                          "selected_skill_ids, used_skill_ids and a short answer.\n\nTASK:\n" + task["query"])
                env = {k: v for k, v in os.environ.items() if k in {
                    "HOME", "PATH", "LANG", "LC_ALL", "PI_CODING_AGENT_DIR", "PI_PACKAGE_DIR",
                    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN", "GOOGLE_API_KEY",
                    "GEMINI_API_KEY", "NODE_PATH",
                }}
                env.update({"GUIDEFOLD_URL": args.url, "GUIDEFOLD_TOKEN_FILE": str(args.token_file),
                            "GUIDEFOLD_TRACE_FILE": str(trace), "PI_OFFLINE": "0"})
                started = time.perf_counter()
                try:
                    proc = subprocess.run(command + [prompt], cwd=workspace, env=env,
                                          capture_output=True, text=True, timeout=args.timeout, check=False)
                    agent_timeout = False
                except subprocess.TimeoutExpired as exc:
                    proc = None; agent_timeout = True
                    stdout, stderr, agent_exit = exc.stdout or "", exc.stderr or "", None
                if proc is not None:
                    stdout, stderr, agent_exit = proc.stdout, proc.stderr, proc.returncode
                events_file.write_text(stdout[-20000:], encoding="utf-8")
                answer, parsed = _parse_final(stdout)
                telemetry = _trace_metrics(trace)
                if agent_timeout or agent_exit != 0 or not parsed:
                    status, verifier_error, verifier_exit, verifier_stdout, verifier_stderr, verifier_ms = (
                        "unknown", True, None, "", "agent_timeout_or_invalid_output", (time.perf_counter() - started) * 1000)
                else:
                    verifier_timeout = float(task.get("verifier_timeout_seconds", args.timeout))
                    expanded_verifier = [item.replace("{workspace}", str(workspace)) for item in verifier]
                    status, verifier_error, verifier_exit, verifier_stdout, verifier_stderr, verifier_ms = _run_verifier(
                        expanded_verifier, evaluator_root, verifier_timeout)
                row = {"task_id": task_id, "arm": args.arm, "outcome": status,
                       "terminal_status": "completed" if not verifier_error else "harness_error",
                       "harness_error": verifier_error, "agent_exit_code": agent_exit,
                       "verifier_exit_code": verifier_exit, "verifier_sha256": verifier_sha,
                       "task_bank_sha256": bank_sha, "verifier_stdout": verifier_stdout,
                       "verifier_stderr": verifier_stderr, "agent_answer": answer,
                       "parsed_agent_answer": parsed, "elapsed_ms": round((time.perf_counter() - task_started) * 1000, 3),
                       "verifier_elapsed_ms": round(verifier_ms, 3), "useful_delivery": None,
                       "harmful_load": None, **telemetry}
                results.write(json.dumps(row, ensure_ascii=False) + "\n"); results.flush()
                print(json.dumps({"task_id": task_id, "outcome": status, "harness_error": verifier_error,
                                  "search": telemetry["search_requests"], "use": telemetry["use_requests"],
                                  "ask": telemetry["ask_count"]}), flush=True)
    return [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True,
                        help="directory containing hidden verifiers; never copied into Pi workspace")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--guidefold-skill", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--bridge", type=Path, required=True,
                        help="read-only Go bridge used by the agent")
    parser.add_argument("--nodes-file", type=Path, required=True,
                        help="frozen hierarchy nodes file passed to SEARCH")
    parser.add_argument("--url", default=os.environ.get("GUIDEFOLD_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--pi-bin", help="Pi command; defaults to npx @earendil-works/pi-coding-agent")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--tools", default="read,bash,edit,write,ls")
    parser.add_argument("--delivery-policy", choices=("legacy", "proof_gated"), default="proof_gated")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
