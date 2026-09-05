#!/usr/bin/env python3
"""Reference harness adapter: normalize observed context, emit a v1.1 request.

Reads one hook JSON object from stdin and writes one request JSON object. Does not
send network traffic, alter shipped hooks, inspect transcripts or call an LLM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.serve_spike.context import VERSION, validate, relative_path

ADAPTER_VERSION = "1.0"


def observed_relative(root, path):
    root = Path(root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        result = candidate.relative_to(root).as_posix()
    except ValueError:
        raise ValueError("observed_path_outside_repository") from None
    return relative_path(result)


def from_hook(event, *, harness, repo_id, repo_root, revision=None, query=None,
              request_id=None, session_id=None, task_id=None, target_paths=None):
    if not isinstance(event, dict):
        raise ValueError("hook_event_must_be_object")
    # A schema/example for an adapter, not a claim that every harness emits these fields.
    prompt = query if query is not None else event.get("prompt", event.get("user_prompt"))
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4096:
        raise ValueError("missing_or_invalid_query")
    work = {"repo_id": repo_id,
            "cwd": observed_relative(repo_root, event.get("cwd") or Path.cwd())}
    if revision is not None:
        work["revision"] = revision
    if target_paths:
        work["target_paths"] = [{"path": observed_relative(repo_root, item["path"]),
                                 "source": item["source"]} for item in target_paths]
    request = {"schema_version": VERSION, "request_id": request_id or str(uuid.uuid4()),
               "query": prompt, "query_source": "agent" if query is not None else "user",
               "workspace": work, "harness": {"name": harness, "adapter_version": ADAPTER_VERSION},
               "profile": "hook", "deadline_ms": 400}
    for key, value in (("session_id", session_id), ("task_id", task_id)):
        if value is not None:
            request[key] = value
    # Explicit arguments establish ID semantics; arbitrary provider IDs are not guessed.
    validate(request, "/v1/search")
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--revision")
    parser.add_argument("--request-id")
    parser.add_argument("--session-id")
    parser.add_argument("--task-id")
    args = parser.parse_args()
    event = json.load(sys.stdin)
    result = from_hook(event, harness=args.harness, repo_id=args.repo_id, repo_root=args.repo_root,
                       revision=args.revision, request_id=args.request_id,
                       session_id=args.session_id, task_id=args.task_id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
