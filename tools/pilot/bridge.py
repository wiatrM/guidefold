#!/usr/bin/env python3
"""Small reference bridge for Pi's isolated Guidefold pilot runner.

The bridge is deliberately a dumb transport adapter: it reads the task query, sends the
unchanged query to the authenticated Go service, and prints only the fields an agent needs for
the next USE call. It never logs query text, bodies or bearer tokens. A nodes file may contain
``repo_id``, ``revision``, ``cwd`` and optional ``scopes``/``target_paths``; hierarchical
strategies issue one scoped SEARCH per listed path and merge cards deterministically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("nodes file must contain a JSON object")
    return value


def _context(path: Path) -> dict[str, Any]:
    value = _json_file(path)
    snapshot = value.get("snapshot") if isinstance(value.get("snapshot"), dict) else value
    workspace = snapshot.get("workspace") if isinstance(snapshot.get("workspace"), dict) else {}
    repo_id = str(value.get("repo_id") or snapshot.get("repo_id") or workspace.get("repo_id") or "")
    revision = str(value.get("revision") or snapshot.get("revision") or workspace.get("revision") or "")
    cwd = str(value.get("cwd") or workspace.get("cwd") or ".")
    if not repo_id:
        raise ValueError("nodes file needs repo_id")
    if not cwd:
        cwd = "."
    scopes = value.get("scopes") or value.get("search_scopes") or []
    if not isinstance(scopes, list) or any(not isinstance(item, str) or not item for item in scopes):
        raise ValueError("nodes file scopes must be a list of non-empty paths")
    targets = value.get("target_paths")
    if targets is not None and (not isinstance(targets, list) or any(not isinstance(item, dict) for item in targets)):
        raise ValueError("nodes file target_paths must be an array of objects")
    return {"repo_id": repo_id, "revision": revision, "cwd": cwd, "scopes": scopes, "target_paths": targets or []}


def _token(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("token file is empty")
    return token


def _trace(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _request(base: str, token: str, endpoint: str, payload: dict[str, Any], trace: Path | None) -> tuple[int, dict[str, Any], float]:
    request_id = str(payload.get("request_id") or uuid.uuid4())
    payload["request_id"] = request_id
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(base.rstrip("/") + endpoint, data=encoded, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            body = {"error": "non_json_http_error"}
    except (OSError, TimeoutError):
        status = 599
        body = {"error": "transport_error"}
    elapsed = (time.perf_counter() - started) * 1000
    if not isinstance(body, dict):
        body = {"error": "invalid_json_response"}
    _trace(trace, {
        "path": endpoint,
        "status": status,
        "elapsed_ms": round(elapsed, 3),
        "request_id": request_id,
        "search_id": body.get("search_id"),
        "action": (body.get("delivery") or {}).get("action") if isinstance(body.get("delivery"), dict) else None,
        "body_chars": len(str(body.get("body") or "")) if endpoint == "/v1/use" and status == 200 else 0,
    })
    return status, body, elapsed


def _workspace(context: dict[str, Any], cwd: str | None = None) -> dict[str, Any]:
    workspace: dict[str, Any] = {"repo_id": context["repo_id"], "cwd": cwd or context["cwd"]}
    if context["revision"]:
        workspace["revision"] = context["revision"]
    if context["target_paths"] and not cwd:
        workspace["target_paths"] = context["target_paths"]
    return workspace


def _search_payload(context: dict[str, Any], query: str, cwd: str, task_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.1", "query": query, "profile": "hook", "deadline_ms": 1000,
        "query_source": "agent", "workspace": _workspace(context, cwd),
        "harness": {"name": "pi", "adapter_version": "guidefold-pilot-1"},
        "budget": {"max_cards": 4},
    }
    if task_id:
        payload["task_id"] = task_id
    return payload


def _card_key(card: dict[str, Any]) -> tuple[float, str]:
    score = card.get("score")
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        numeric = 0.0
    return (-numeric, str(card.get("skill_id") or card.get("urn") or ""))


def _public_card(card: dict[str, Any]) -> dict[str, Any]:
    return {key: card.get(key) for key in ("skill_id", "urn", "revision", "name", "node", "status") if key in card}


def search(args: argparse.Namespace) -> int:
    context = _context(args.nodes_file)
    query = args.query_file.read_text(encoding="utf-8").strip()
    if not query:
        raise ValueError("query file is empty")
    task_id = os.environ.get("GUIDEFOLD_TASK_ID")
    token = _token(args.token_file)
    trace = Path(os.environ["GUIDEFOLD_TRACE_FILE"]) if os.environ.get("GUIDEFOLD_TRACE_FILE") else None
    scopes = context["scopes"] if args.strategy != "flat" and context["scopes"] else [context["cwd"]]
    if args.strategy in {"top_down", "beam_top_down"}:
        scopes = sorted(scopes, key=lambda item: (item.count("/"), item))
    elif args.strategy == "bottom_up":
        scopes = sorted(scopes, key=lambda item: (-item.count("/"), item))
    responses: list[dict[str, Any]] = []
    timings: list[float] = []
    for scope in scopes:
        status, body, elapsed = _request(args.url, token, "/v1/search", _search_payload(context, query, scope, task_id), trace)
        timings.append(elapsed)
        if status != 200:
            print(json.dumps({"status": status, "error": body.get("error", "search_failed"), "strategy": args.strategy}))
            return 2
        responses.append(body)
    cards_by_id: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}
    for response in responses:
        for ranked in response.get("ranked", []):
            if not isinstance(ranked, dict):
                continue
            key = str(ranked.get("skill_id") or ranked.get("urn") or "")
            if not key:
                continue
            try:
                score = float(ranked.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            scores[key] = max(scores.get(key, float("-inf")), score)
        for card in response.get("cards", []):
            if isinstance(card, dict):
                key = str(card.get("skill_id") or card.get("urn") or "")
                if key:
                    candidate = {**card, "score": scores.get(key, float("-inf"))}
                    if key not in cards_by_id or _card_key(candidate) < _card_key(cards_by_id[key]):
                        cards_by_id[key] = candidate
    cards = sorted(cards_by_id.values(), key=_card_key)[:4]
    first = responses[0]
    print(json.dumps({
        "status": 200, "strategy": args.strategy, "search_id": first.get("search_id"),
        "snapshot": first.get("snapshot"), "cards": [_public_card(card) for card in cards],
        "card_context": "\n".join(str(response.get("card_context") or "") for response in responses).strip(),
        "delivery_status": (first.get("context") or {}).get("delivery_status") if isinstance(first.get("context"), dict) else None,
        "search_requests": len(responses), "elapsed_ms": round(sum(timings), 3),
    }, ensure_ascii=False))
    return 0


def use(args: argparse.Namespace) -> int:
    context = _context(args.nodes_file)
    token = _token(args.token_file)
    payload: dict[str, Any] = {
        "schema_version": "1.2" if args.delivery_policy == "proof_gated" else "1.1",
        "skill_id": args.skill_id, "revision": args.revision, "workspace": _workspace(context),
    }
    if args.delivery_policy == "proof_gated":
        payload["delivery_policy"] = "proof_gated"
    if args.search_snapshot:
        payload["search_snapshot"] = args.search_snapshot
    if args.search_id:
        payload["search_id"] = args.search_id
    task_id = os.environ.get("GUIDEFOLD_TASK_ID")
    if task_id:
        payload["task_id"] = task_id
    trace = Path(os.environ["GUIDEFOLD_TRACE_FILE"]) if os.environ.get("GUIDEFOLD_TRACE_FILE") else None
    status, body, elapsed = _request(args.url, token, "/v1/use", payload, trace)
    delivery_action = body.get("delivery", {}).get("action") if isinstance(body.get("delivery"), dict) else None
    result = {"status": status, "elapsed_ms": round(elapsed, 3), "action": delivery_action or ("LOAD" if body.get("status") == "hydrated" else body.get("status")),
              "skill_id": args.skill_id, "revision": args.revision, "body": body.get("body", ""),
              "reason": body.get("reason"), "missing": body.get("missing"), "closure": body.get("closure")}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if status == 200 else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("GUIDEFOLD_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token-file", type=Path, default=(Path(os.environ["GUIDEFOLD_TOKEN_FILE"]) if os.environ.get("GUIDEFOLD_TOKEN_FILE") else None))
    parser.add_argument("--nodes-file", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    search_parser = sub.add_parser("search")
    search_parser.add_argument("--strategy", choices=("flat", "top_down", "beam_top_down", "beam_rrf", "bottom_up"), default="flat")
    search_parser.add_argument("--query-file", type=Path, required=True)
    search_parser.set_defaults(function=search)
    use_parser = sub.add_parser("use")
    use_parser.add_argument("--skill-id", required=True)
    use_parser.add_argument("--revision", required=True)
    use_parser.add_argument("--search-id")
    use_parser.add_argument("--search-snapshot")
    use_parser.add_argument("--delivery-policy", choices=("legacy", "proof_gated"), default="proof_gated")
    use_parser.set_defaults(function=use)
    args = parser.parse_args(argv)
    if args.token_file is None:
        parser.error("--token-file or GUIDEFOLD_TOKEN_FILE is required")
    try:
        return args.function(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": 400, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
