#!/usr/bin/env python3
"""E1.1b loopback HTTP feasibility probe, not a routing-quality evaluation.

The parent loads a frozen public DEV sample. Each HTTP request contains the real
query text; this client never loads a model or supplies precomputed embeddings.
The fresh-client arm starts this stdlib-only script anew for each request.

Example:
    python tools/serve_spike/probe.py --url http://127.0.0.1:8765 \
        --token-file /tmp/guidefold-spike-token --label hybrid \
        --output docs/reports/bakeoff/validation/e11b-hybrid.json

Only loopback HTTP is supported: results exclude WAN/TLS, real identity, a
production deployment, and actual harness startup. Cache fallback below is a
controlled contract probe; the shipped CLI is not switched to this service.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]


def percentile(values, quantile):
    """Nearest-rank percentile; preserve failures outside latency denominators."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("This feasibility probe accepts only explicit loopback HTTP URLs")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Credentials, query strings and fragments are not valid in the base URL")
    return url.rstrip("/")


def server_elapsed_header(headers):
    """Missing or invalid server measurements are never interpreted as zero."""
    values = headers.get_all("X-Guidefold-Server-Ms") if headers is not None else None
    if not values:
        return None, "missing_header"
    if len(values) != 1:
        return None, "invalid_header"
    try:
        value = float(values[0])
    except (ValueError, TypeError):
        return None, "invalid_header"
    return (value, "measured") if math.isfinite(value) and value >= 0 else (None, "invalid_header")


def request_json(url, token, path, payload=None, timeout=5.0):
    """A complete JSON-over-HTTP roundtrip, including serialization and decoding."""
    started = time.perf_counter()
    status, body, error = None, None, None
    server_elapsed_ms, server_elapsed_measurement = None, "missing_header"
    try:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url + path, data=data, headers=headers)
        # Disable proxy lookup for a reproducible, explicitly local measurement.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=timeout) as response:
                status = response.status
                server_elapsed_ms, server_elapsed_measurement = server_elapsed_header(response.headers)
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            status = exc.code
            server_elapsed_ms, server_elapsed_measurement = server_elapsed_header(exc.headers)
            try:
                body = json.loads(exc.read())
            except (ValueError, UnicodeDecodeError):
                error = "non_json_http_error"
    except (TimeoutError, socket.timeout):
        error = "client_timeout"
    except urllib.error.URLError as exc:
        error = "client_timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connection_error"
    except (ValueError, UnicodeDecodeError, OSError):
        error = "invalid_response_or_transport"
    return {"http_status": status, "response": body, "error": error,
            "server_elapsed_ms": server_elapsed_ms,
            "server_elapsed_measurement": server_elapsed_measurement,
            "client_ms": (time.perf_counter() - started) * 1000}


def search_with_fallback(url, token, payload, *, timeout, cached_cards,
                         lease_expires_unix=None, allowed_revisions=None, snapshot_id=None):
    """Controlled snapshot/lease contract; no real BM25 or shipped CLI integration."""
    result = request_json(url, token, "/v1/search", payload, timeout)
    if result["http_status"] == 200 and result["error"] is None:
        return {"mode": "remote", "result": result}
    reason = result["error"] or "http_" + str(result["http_status"])
    abstain = {"mode": "abstain", "reason": reason, "cards": [],
               "execution_observed": False, "remote_attempt": result}
    if result["http_status"] in {401, 403}:
        return {**abstain, "invalidate_cache": True}
    transport_failure = (result["error"] in {"client_timeout", "connection_error"} or
                         result["http_status"] in {408, 429, 502, 503, 504})
    if not transport_failure:
        return abstain
    if not snapshot_id or lease_expires_unix is None or lease_expires_unix <= time.time():
        return {**abstain, "reason": "missing_or_expired_cache_lease"}
    if not isinstance(allowed_revisions, dict) or any(
            allowed_revisions.get(card.get("skill_id")) != card.get("revision") or
            not card.get("revision") for card in cached_cards):
        return {**abstain, "reason": "cache_revision_not_authorized"}
    return {"mode": "local_snapshot_fallback", "reason": reason, "cards": list(cached_cards),
            "snapshot": snapshot_id, "execution_observed": False, "remote_attempt": result}


def compact_result(result, query_id=None):
    body = result.get("response")
    body = body if isinstance(body, dict) else {}
    ranked = [[row.get("skill_id"), row.get("score")] for row in body.get("ranked", [])]
    selected = [[row.get("skill_id"), row.get("revision")] for row in body.get("cards", [])]
    canonical = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return {
        "query_id": query_id, "http_status": result.get("http_status"),
        "ranked_sha256": hashlib.sha256(canonical(ranked)).hexdigest() if "ranked" in body else None,
        "selected_sha256": hashlib.sha256(canonical(selected)).hexdigest() if "cards" in body else None,
        "error": result.get("error"), "client_ms": result.get("client_ms"),
        "server_elapsed_ms": result.get("server_elapsed_ms"),
        "server_elapsed_measurement": result.get("server_elapsed_measurement", "missing_header"),
        "search_id": body.get("search_id"), "backend": body.get("backend"),
        "snapshot": body.get("snapshot"), "model": body.get("model"),
        "policy": body.get("policy"), "stages_ms": body.get("stages_ms", {}),
        "live_encode_calls": body.get("live_encode_calls"),
        "card_count": len(body.get("cards", [])),
        "composition": body.get("composition"),
        "failure_code": body.get("error"),
    }


def summarize(rows, budget_ms, elapsed_ms=None):
    ok = [r for r in rows if r.get("http_status") == 200 and not r.get("error")]
    times = [r["client_ms"] for r in ok]
    server_times = [r["server_elapsed_ms"] for r in ok
                    if not isinstance(r.get("server_elapsed_ms"), bool)
                    and isinstance(r.get("server_elapsed_ms"), (int, float))
                    and math.isfinite(r["server_elapsed_ms"]) and r["server_elapsed_ms"] >= 0]
    all_times = [r["client_ms"] for r in rows if isinstance(r.get("client_ms"), (int, float))]
    codes = Counter(str(r.get("http_status")) for r in rows)
    errors = Counter(r["error"] for r in rows if r.get("error"))
    within = sum(r["client_ms"] <= budget_ms for r in ok)
    result = {
        "attempted": len(rows), "succeeded": len(ok), "failed": len(rows) - len(ok),
        "http_status_counts": dict(codes), "client_error_counts": dict(errors),
        "success_latency_ms": {"p50": percentile(times, .50), "p95": percentile(times, .95),
                               "p99": percentile(times, .99), "max": max(times) if times else None},
        "all_attempt_latency_ms": {"p50": percentile(all_times, .50),
                                   "p95": percentile(all_times, .95),
                                   "p99": percentile(all_times, .99)},
        "budget_ms": budget_ms, "successful_within_budget": within,
        "within_budget_fraction_of_all_attempts": within / len(rows) if rows else None,
        "budget_failures_including_rejections": len(rows) - within,
        "successful_backend_counts": dict(Counter(r.get("backend") for r in ok)),
        "server_elapsed_ms": {
            "p50": percentile(server_times, .50), "p95": percentile(server_times, .95),
            "p99": percentile(server_times, .99), "count": len(server_times),
            "missing_or_invalid_success_count": len(ok) - len(server_times),
            "successful_measurement_status_counts": dict(Counter(
                r.get("server_elapsed_measurement", "missing_header") for r in ok)),
        },
    }
    if elapsed_ms is not None:
        result["batch_elapsed_ms"] = elapsed_ms
        result["successful_requests_per_second"] = len(ok) / (elapsed_ms / 1000) if elapsed_ms else None
    stage_keys = {key for row in ok for key, value in row.get("stages_ms", {}).items()
                  if isinstance(value, (int, float))}
    result["server_stage_ms"] = {
        key: {"p50": percentile([r["stages_ms"][key] for r in ok if key in r.get("stages_ms", {})], .50),
              "p95": percentile([r["stages_ms"][key] for r in ok if key in r.get("stages_ms", {})], .95),
              "p99": percentile([r["stages_ms"][key] for r in ok if key in r.get("stages_ms", {})], .99)}
        for key in sorted(stage_keys)
    }
    return result


def load_queries(count):
    """Sample distinct frozen DEV query texts deterministically, without using qrels."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.eval import corpora

    split = json.loads(corpora.DEV_SPLIT.read_text())
    allowed = set(split["query_ids"])
    source = corpora.corpus_dir("skillret") / "data" / "queries" / "train.jsonl"
    candidates = []
    seen = set()
    for line in source.read_text().splitlines():
        row = json.loads(line)
        if row["id"] not in allowed or row["query"] in seen:
            continue
        seen.add(row["query"])
        candidates.append({"id": row["id"], "query": row["query"]})
    candidates.sort(key=lambda r: hashlib.sha256(("e11b-v1:" + r["id"]).encode()).hexdigest())
    if count < 1 or count > len(candidates):
        raise ValueError(f"count must be in 1..{len(candidates)}")
    selected = candidates[:count]
    provenance = {
        "dataset": "SKILLRET frozen DEV subset of train", "sample_size": count,
        "distinct_query_texts": len({q["query"] for q in selected}),
        "sample_rule": "sha256(e11b-v1:query_id), ascending, first N unique texts",
        "source_query_file_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "frozen_dev_split_sha256": hashlib.sha256(corpora.DEV_SPLIT.read_bytes()).hexdigest(),
        "sample_query_ids": [q["id"] for q in selected],
        "sample_text_sha256": hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest(),
        "hf_revision": corpora.manifest()["corpora"]["skillret"]["revision"],
        "labels_used_for_selection_or_quality": False,
        "retrieval_pool_may_differ_from_dev": True,
        "quality_claim": "none; labelled public DEV texts are used solely as a latency workload",
    }
    return selected, provenance


def search_payload(query, deadline_ms):
    return {"query": query["query"], "profile": "hook", "node": "_root", "deadline_ms": deadline_ms}


def benchmark_http(args, token, queries, concurrency):
    started = time.perf_counter()
    def one(query):
        result = request_json(args.url, token, "/v1/search",
                              search_payload(query, args.deadline_ms), args.timeout)
        return compact_result(result, query["id"])
    if concurrency == 1:
        rows = [one(q) for q in queries]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows = list(pool.map(one, queries))
    elapsed = (time.perf_counter() - started) * 1000
    return {"concurrency": concurrency, "rows": rows,
            "summary": summarize(rows, args.budget_ms, elapsed)}


def benchmark_fresh(args, queries):
    def one(query):
        request = {"path": "/v1/search", "payload": search_payload(query, args.deadline_ms)}
        # Timing begins inside the worker, excluding time waiting in the parent's queue.
        begin = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, str(pathlib.Path(__file__).resolve()), "--one-shot",
                 "--url", args.url, "--token-file", str(args.token_file),
                 "--timeout", str(args.timeout)],
                input=json.dumps(request), text=True, capture_output=True,
                timeout=args.timeout + 5, check=False)
            if completed.returncode != 0:
                raise ValueError("fresh client exited nonzero")
            result = json.loads(completed.stdout)
            row = compact_result(result, query["id"])
            row["http_roundtrip_ms"] = row["client_ms"]
        except subprocess.TimeoutExpired:
            row = {"query_id": query["id"], "http_status": None, "error": "fresh_process_timeout"}
        except (ValueError, OSError):
            row = {"query_id": query["id"], "http_status": None, "error": "fresh_process_failed"}
        row["client_ms"] = (time.perf_counter() - begin) * 1000
        return row

    started = time.perf_counter()
    selected = queries[:args.fresh_count]
    if args.fresh_concurrency == 1:
        rows = [one(query) for query in selected]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.fresh_concurrency) as pool:
            rows = list(pool.map(one, selected))
    elapsed = (time.perf_counter() - started) * 1000
    return {"measurement": "Python process start + stdlib client imports + token read + HTTP + exit",
            "concurrency": args.fresh_concurrency, "parent_queue_included_in_per_request_ms": False,
            "actual_harness_or_distributed_CLI": False, "rows": rows,
            "summary": summarize(rows, args.budget_ms, elapsed)}



def probe_use(args, token, query):
    search = request_json(args.url, token, "/v1/search",
                          search_payload(query, args.deadline_ms), args.timeout)
    body = search.get("response") or {}
    cards = body.get("cards", [])
    if search["http_status"] != 200 or not cards:
        return {"status": "not_measured_no_search_card", "setup_search": compact_result(search, query["id"])}
    card = cards[0]
    payload = {"skill_id": card["skill_id"], "revision": card["revision"],
               "search_id": body.get("search_id"), "deadline_ms": args.deadline_ms}
    rows = []
    for _ in range(args.use_count):
        result = request_json(args.url, token, "/v1/use", payload, args.timeout)
        response = result.get("response") or {}
        returned_body = response.get("body")
        expected = (hashlib.sha256(returned_body.encode()).hexdigest()
                    if isinstance(returned_body, str) else None)
        rows.append({
            "http_status": result["http_status"], "error": result["error"],
            "client_ms": result["client_ms"], "backend": "revision_pinned_hydration",
            "server_elapsed_ms": result.get("server_elapsed_ms"),
            "server_elapsed_measurement": result.get("server_elapsed_measurement", "missing_header"),
            "status": response.get("status"), "revision": response.get("revision"),
            "revision_matches_requested": response.get("revision") == payload["revision"],
            "checksum_matches_body": expected is not None and response.get("checksum") == expected,
            "search_correlation_matches": response.get("search_id") == body.get("search_id"),
            "execution_observed": response.get("execution_observed"),
            "body_bytes": len(returned_body.encode()) if isinstance(returned_body, str) else None,
        })
    missing_revision = dict(payload)
    missing_revision.pop("revision")
    invalid = request_json(args.url, token, "/v1/use", missing_revision, args.timeout)
    checks = {
        "all_http_200": bool(rows) and all(row["http_status"] == 200 and not row["error"] for row in rows),
        "all_checksums_match_body": bool(rows) and all(row["checksum_matches_body"] for row in rows),
        "all_revisions_match_requested": bool(rows) and all(row["revision_matches_requested"] for row in rows),
        "all_correlation_echoes_match": bool(rows) and all(row["search_correlation_matches"] for row in rows),
        "hydration_not_execution": bool(rows) and all(row["status"] == "hydrated" and
                                                       row["execution_observed"] is False for row in rows),
        "missing_revision_rejected_400": invalid["http_status"] == 400,
    }
    return {"status": "measured", "setup_search": compact_result(search, query["id"]),
            "requested_skill_id": payload["skill_id"], "requested_revision": payload["revision"],
            "correctness": {"checks": checks, "passed": all(checks.values())},
            "rows": rows, "summary": summarize(rows, args.budget_ms),
            "missing_revision_status": invalid["http_status"],
            "missing_revision_error": (invalid.get("response") or {}).get("error"),
            "semantics": "body hydration only; no applied/useful/executed claim"}


def probe_failures(args, token, query, use):
    """Exercise real rejection/deadline/recovery behavior outside timing arms."""
    import http.client

    before = request_json(args.url, token, "/health/ready", timeout=args.timeout)
    denied = request_json(args.url, "intentionally-invalid-token", "/v1/search",
                          search_payload(query, args.deadline_ms), args.timeout)
    stale = None
    if use.get("requested_skill_id"):
        stale = request_json(args.url, token, "/v1/use", {
            "skill_id": use["requested_skill_id"],
            "revision": use["requested_revision"] + "-stale",
            "deadline_ms": args.deadline_ms}, args.timeout)
    started = time.perf_counter()
    parsed = urllib.parse.urlsplit(args.url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=args.timeout)
    try:
        connection.putrequest("POST", "/v1/search")
        connection.putheader("Authorization", "Bearer " + token)
        connection.putheader("Content-Length", "1000000")
        connection.endheaders()
        response = connection.getresponse()
        oversized = {"http_status": response.status, "response": json.loads(response.read()), "error": None}
    except (OSError, ValueError, http.client.HTTPException):
        oversized = {"http_status": None, "response": None, "error": "oversize_probe_transport"}
    finally:
        connection.close()
    oversized["client_ms"] = (time.perf_counter() - started) * 1000
    tight = request_json(args.url, token, "/v1/search", search_payload(query, 1), args.timeout)
    recovery = request_json(args.url, token, "/v1/search",
                            search_payload(query, args.deadline_ms), args.timeout)
    after = request_json(args.url, token, "/health/ready", timeout=args.timeout)
    checks = {
        "invalid_token_rejected_401": denied["http_status"] == 401,
        "stale_use_revision_rejected_409": stale["http_status"] == 409 if stale else None,
        "oversized_body_rejected_413": oversized["http_status"] == 413,
        "one_ms_deadline_rejected_504": tight["http_status"] == 504,
        "next_search_recovers_200": recovery["http_status"] == 200,
        "still_ready": after["http_status"] == 200 and (after.get("response") or {}).get("ready") is True,
    }
    return {
        "outside_latency_and_encode_audit_arms": True,
        "cases": {"invalid_token": compact_result(denied),
                  "stale_use_revision": compact_result(stale) if stale else None,
                  "oversized_body": compact_result(oversized),
                  "one_ms_deadline": compact_result(tight, query["id"]),
                  "recovery_search": compact_result(recovery, query["id"])},
        "checks": checks, "passed": all(value is True for value in checks.values()),
        "ready_before": before.get("response"), "ready_after": after.get("response"),
        "semantics": "loopback token + active state only; no tenant IAM or execution evidence",
    }



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", type=pathlib.Path, required=True)
    parser.add_argument("--one-shot", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--label", default="unspecified")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--fresh-count", type=int, default=200)
    parser.add_argument("--fresh-concurrency", type=int, default=1)
    parser.add_argument("--use-count", type=int, default=20)
    parser.add_argument("--concurrency", default="1,4")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--deadline-ms", type=int, default=1000)
    parser.add_argument("--budget-ms", type=float, default=300.0)
    args = parser.parse_args(argv)
    args.url = validate_url(args.url)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    token = args.token_file.read_text().strip()
    if not token:
        parser.error("token file is empty")
    if args.one_shot:
        request = json.load(sys.stdin)
        print(json.dumps(request_json(args.url, token, request["path"],
                                      request.get("payload"), args.timeout)))
        return 0
    if args.output is None:
        parser.error("--output is required for benchmark mode")
    levels = [int(c) for c in args.concurrency.split(",")]
    if not levels or any(c < 1 or c > 32 for c in levels):
        parser.error("concurrency must contain integers from 1 to 32")
    if not 1 <= args.fresh_concurrency <= 32:
        parser.error("fresh-concurrency must be 1..32")
    if not 0 <= args.fresh_count <= args.count or args.use_count < 0:
        parser.error("fresh-count must be 0..count, use-count >= 0")
    queries, provenance = load_queries(args.count)
    ready = request_json(args.url, token, "/health/ready", timeout=args.timeout)
    if ready["http_status"] != 200 or not (ready.get("response") or {}).get("ready"):
        raise SystemExit("service is not ready: " + json.dumps(ready))
    print(f"{args.label}: {len(queries)} distinct public DEV queries; loopback latency only", flush=True)
    warmups = [request_json(args.url, token, "/v1/search",
                           search_payload(q, args.deadline_ms), args.timeout)
               for q in queries[:min(4, len(queries))]]
    measurement_before = request_json(args.url, token, "/health/ready", timeout=args.timeout)
    arms = []
    for concurrency in levels:
        arm = benchmark_http(args, token, queries, concurrency)
        arms.append(arm)
        print("HTTP c=" + str(concurrency) + " " + json.dumps(arm["summary"]), flush=True)
    fresh = benchmark_fresh(args, queries)
    print("fresh-client " + json.dumps(fresh["summary"]), flush=True)
    use = probe_use(args, token, queries[0]) if args.use_count else {"status": "disabled"}
    after = request_json(args.url, token, "/health/ready", timeout=args.timeout)
    counter_before = (measurement_before.get("response") or {}).get("live_encode_calls")
    counter_after = (after.get("response") or {}).get("live_encode_calls")
    observed_delta = (counter_after - counter_before if isinstance(counter_before, int) and
                      isinstance(counter_after, int) else None)
    successful_searches = sum(arm["summary"]["succeeded"] for arm in arms) + fresh["summary"]["succeeded"]
    if use.get("setup_search", {}).get("http_status") == 200 and not use["setup_search"].get("error"):
        successful_searches += 1  # SEARCH needed to get the exact revision for USE.
    live_encode_audit = {
        "counter_before": counter_before, "counter_after": counter_after,
        "observed_forward_passes": observed_delta,
        "successful_searches_including_use_setup": successful_searches,
        "exactly_one_forward_per_success": (observed_delta == successful_searches
                                              if observed_delta is not None else None),
        "interpretation": "Hybrid forward-pass evidence only; timed-out searches may also encode, "
                          "sparse arm should have zero, concurrent external traffic invalidates equality.",
    }
    failures = probe_failures(args, token, queries[0], use)
    result = {
        "schema_version": "e11b-loopback-probe-v1", "label": args.label,
        "probe_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        "runtime_fault_checks": failures,
        "created_unix": time.time(), "base_url": args.url,
        "scope": "local resident service feasibility; not deployment or product readiness",
        "workload": provenance, "request_profile": "hook", "request_node": "_root",
        "requested_deadline_ms": args.deadline_ms, "client_timeout_seconds": args.timeout,
        "server_elapsed_measurement": {
            "header": "X-Guidefold-Server-Ms",
            "scope": "POST handler start through synchronous telemetry and JSON serialization, before response headers/body transmission",
            "excludes": "socket accept/HTTP header parsing before do_POST, response transmission, WAN/TLS, client startup and decoding",
            "missing_or_invalid": "null, never zero",
        },
        "ready_before_warmups": ready.get("response"),
        "warmup_requests_excluded": len(warmups),
        "warmup_successes": sum(r["http_status"] == 200 for r in warmups),
        "ready_before_measurement": measurement_before.get("response"),
        "http_arms": arms, "fresh_process_arm": fresh, "use": use,
        "ready_after": after.get("response"), "live_encode_audit": live_encode_audit,
        "verdict": {
            "latency_gate_loopback_http": all(
                arm["summary"]["succeeded"] == arm["summary"]["attempted"] and
                arm["summary"]["success_latency_ms"]["p95"] is not None and
                arm["summary"]["success_latency_ms"]["p95"] <= args.budget_ms for arm in arms),
            "runtime_fault_checks_passed": failures["passed"],
            "use_hydration_checks_passed": use.get("correctness", {}).get("passed"),
            "production_ready": False,
            "missing_validation": [
                "WAN + TLS + real authentication + production queue/load",
                "actual harness integration and its whole-hook budget",
                "quality on approved corpora with product policy/select",
                "30k real or audited scale corpus",
                "revision-pinned package/cache client and offline integration",
                "telemetry durability, tenant isolation and outcome attribution",
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(str(args.output), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
