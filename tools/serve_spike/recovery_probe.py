#!/usr/bin/env python3
"""Real process outage/restart probe for the local E1.1b service.

Starts only its own loopback subprocess, discovers its ephemeral port, searches
one frozen public DEV query, hydrates a pinned revision, stops that process, and
proves connection failure before testing a controlled in-memory cache fixture.
It then restarts its own process on the same endpoint and repeats SEARCH/USE.

The lease is an unsigned test fixture, not production authorization. The cache
fallback returns existing cards; it is not BM25, a shipped CLI, or a harness test.
No query text, token, skill body, or cached card/revision contents enter the report.
The default runs the GPU service; --disable-model selects the sparse baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "tools/serve_spike/server.py"
PROBE = ROOT / "tools/serve_spike/probe.py"


def load_probe():
    spec = importlib.util.spec_from_file_location("e11b_frozen_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OwnService:
    """Own exactly one subprocess; never inspect or stop unrelated processes."""

    def __init__(self, args, probe, token_file, token, scratch, ordinal, port=0):
        self.args, self.probe, self.token = args, probe, token
        self.token_file, self.scratch, self.ordinal, self.port = token_file, scratch, ordinal, port
        self.process = None
        self.stream = None
        self.url = None
        self.stdout_file = scratch / ("service-" + str(ordinal) + ".log")
        self.stop_evidence = None

    def start(self):
        command = [sys.executable, str(SERVER), "--port", str(self.port),
                   "--token-file", str(self.token_file), "--max-inflight", "4"]
        if self.args.disable_model:
            command.append("--disable-model")
        if self.args.cache_dir is not None:
            command.extend(["--cache-dir", str(self.args.cache_dir)])
        self.stream = self.stdout_file.open("wb")
        started = time.perf_counter()
        self.process = subprocess.Popen(command, stdout=self.stream, stderr=subprocess.STDOUT,
                                        cwd=ROOT, stdin=subprocess.DEVNULL)
        timeout_at = time.monotonic() + self.args.startup_timeout
        while time.monotonic() < timeout_at:
            if self.process.poll() is not None:
                raise RuntimeError("owned_service_exited_before_ready")
            if self.url is None:
                for line in self.stdout_file.read_text(errors="replace").splitlines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict) and "listening" in row:
                        self.url = self.probe.validate_url(row["listening"])
                        break
            if self.url:
                ready = self.probe.request_json(self.url, self.token, "/health/ready",
                                                timeout=min(self.args.timeout, 1.0))
                body = ready.get("response") or {}
                if ready["http_status"] == 200 and body.get("ready") is True:
                    return {"pid": self.process.pid,
                            "process_start_to_ready_ms": (time.perf_counter() - started) * 1000,
                            "ready": body}
                if body.get("error"):
                    raise RuntimeError("owned_service_initialization_failed")
            time.sleep(.2)
        raise RuntimeError("owned_service_readiness_timeout")

    def stop(self):
        if self.stop_evidence is not None:
            return self.stop_evidence
        started = time.perf_counter()
        forced = False
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                forced = True
                self.process.kill()
                self.process.wait(timeout=5)
        if self.stream is not None:
            self.stream.close()
        self.stop_evidence = {
            "pid": self.process.pid if self.process is not None else None,
            "stopped": self.process is not None and self.process.poll() is not None,
            "exit_code": self.process.returncode if self.process is not None else None,
            "forced_kill_after_terminate_timeout": forced,
            "stop_ms": (time.perf_counter() - started) * 1000,
        }
        return self.stop_evidence


def hydrate(probe, args, url, token, card, search_id):
    result = probe.request_json(url, token, "/v1/use", {
        "skill_id": card["skill_id"], "revision": card["revision"],
        "search_id": search_id, "deadline_ms": args.deadline_ms}, args.timeout)
    body = result.get("response") or {}
    content = body.get("body")
    checks = {
        "http_200": result["http_status"] == 200 and result["error"] is None,
        "revision_matches_requested": body.get("revision") == card["revision"],
        "checksum_matches_body": isinstance(content, str) and
            body.get("checksum") == hashlib.sha256(content.encode()).hexdigest(),
        "search_correlation_echo_matches": body.get("search_id") == search_id,
        "hydration_not_execution": body.get("status") == "hydrated" and body.get("execution_observed") is False,
    }
    return {"http_status": result["http_status"], "error": result["error"],
            "client_ms": result["client_ms"], "checks": checks,
            "passed": all(checks.values()), "search_correlation_verified": body.get("search_id_verified"),
            "body_bytes": len(content.encode()) if isinstance(content, str) else None}


def compact_fallback(probe, result):
    return {"mode": result.get("mode"), "reason": result.get("reason"),
            "card_count": len(result.get("cards", [])),
            "execution_observed": result.get("execution_observed"),
            "remote_attempt": probe.compact_result(result["remote_attempt"])
                if result.get("remote_attempt") else None}


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--disable-model", action="store_true")
    parser.add_argument("--cache-dir", type=pathlib.Path)
    parser.add_argument("--startup-timeout", type=float, default=180)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--deadline-ms", type=int, default=1000)
    args = parser.parse_args(argv)
    if args.startup_timeout <= 0 or args.timeout <= 0 or not 1 <= args.deadline_ms <= 5000:
        parser.error("timeouts must be positive; deadline-ms must be 1..5000")
    probe = load_probe()
    queries, workload = probe.load_queries(1)
    query = queries[0]
    scratch_root = ROOT / ".guidefold/checks"
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="e11b-recovery-", dir=scratch_root))
    token_file = scratch / "token"
    token = secrets.token_urlsafe(32)
    # The token is ephemeral, owner-readable, and under the repository's ignored tree.
    with os.fdopen(os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(token)
    services = []
    report = {
        "schema_version": "e11b-process-recovery-v1",
        "created_unix": time.time(),
        "backend": "sparse_only" if args.disable_model else "hybrid_full",
        "scope": "real local service subprocess outage and restart; not a harness or production deployment",
        "source_sha256": {"recovery_probe": sha256_file(pathlib.Path(__file__)),
                          "server": sha256_file(SERVER), "frozen_probe": sha256_file(PROBE)},
        "workload": workload,
        "controlled_cache_fixture": {
            "storage": "in-memory actual SEARCH cards and exact revisions",
            "lease_is_signed_authorization": False,
            "lease_source": "unsigned local test fixture",
            "fallback_is_bm25": False,
            "production_tenant_acl_tested": False,
            "raw_cards_revisions_in_report": False,
        },
        "production_ready": False,
        "missing_validation": ["E2.6 real harness integration and whole-hook latency",
                               "signed lease issuance/revocation and actual offline BM25",
                               "WAN/TLS, production identity and tenant access"],
    }
    phase = "first_start"
    try:
        first = OwnService(args, probe, token_file, token, scratch, 1)
        services.append(first)
        report["first_start"] = first.start()
        print("first process ready", flush=True)
        phase = "initial_search_use"
        search = probe.request_json(first.url, token, "/v1/search",
                                    probe.search_payload(query, args.deadline_ms), args.timeout)
        report["initial_search"] = probe.compact_result(search, query["id"])
        body = search.get("response") or {}
        cards = body.get("cards") or []
        if search["http_status"] != 200 or not cards:
            raise RuntimeError("initial_search_failed_or_no_card")
        # Full cards and exact revisions remain local in RAM, never in the JSON report.
        cached_cards = [dict(card) for card in cards]
        allowed_revisions = {card["skill_id"]: card["revision"] for card in cached_cards}
        card = cached_cards[0]
        snapshot = body.get("snapshot")
        report["initial_use"] = hydrate(probe, args, first.url, token, card, body["search_id"])
        report["ready_after_initial_requests"] = probe.request_json(
            first.url, token, "/health/ready", timeout=args.timeout).get("response")
        phase = "outage"
        report["stopped_first_process"] = first.stop()
        outage = probe.request_json(first.url, token, "/v1/search",
                                    probe.search_payload(query, args.deadline_ms), args.timeout)
        report["outage_request"] = probe.compact_result(outage, query["id"])
        valid_fallback = probe.search_with_fallback(
            first.url, token, probe.search_payload(query, args.deadline_ms),
            timeout=args.timeout, cached_cards=cached_cards, lease_expires_unix=time.time() + 60,
            allowed_revisions=allowed_revisions, snapshot_id=snapshot)
        expired_fallback = probe.search_with_fallback(
            first.url, token, probe.search_payload(query, args.deadline_ms),
            timeout=args.timeout, cached_cards=cached_cards, lease_expires_unix=time.time() - 1,
            allowed_revisions=allowed_revisions, snapshot_id=snapshot)
        report["valid_lease_fixture_fallback"] = compact_fallback(probe, valid_fallback)
        report["expired_lease_fixture_fallback"] = compact_fallback(probe, expired_fallback)
        print("owned process stopped; outage and controlled cache fixtures measured", flush=True)
        phase = "restart"
        port = urllib.parse.urlsplit(first.url).port
        restarted = OwnService(args, probe, token_file, token, scratch, 2, port=port)
        services.append(restarted)
        report["restart"] = restarted.start()
        print("replacement process ready on the same endpoint", flush=True)
        phase = "recovered_search_use"
        recovered = probe.request_json(restarted.url, token, "/v1/search",
                                       probe.search_payload(query, args.deadline_ms), args.timeout)
        report["recovered_search"] = probe.compact_result(recovered, query["id"])
        recovered_body = recovered.get("response") or {}
        # Hydrate the SAME pre-outage revision; the post-restart SEARCH ID is an echo only.
        report["recovered_use_of_original_revision"] = hydrate(
            probe, args, restarted.url, token, card, recovered_body.get("search_id"))
        report["ready_after_recovery"] = probe.request_json(
            restarted.url, token, "/health/ready", timeout=args.timeout).get("response")
        first_ready = report["first_start"]["ready"]
        second_ready = report["restart"]["ready"]
        expected_loads = 0 if args.disable_model else 1
        expected_encodes = 0 if args.disable_model else 1
        checks = {
            "initial_search_http_200": search["http_status"] == 200 and search["error"] is None,
            "initial_use_correct": report["initial_use"]["passed"],
            "owned_first_process_stopped": report["stopped_first_process"]["stopped"],
            "stopped_endpoint_connection_error": outage["http_status"] is None and outage["error"] == "connection_error",
            "valid_lease_fixture_returns_identical_cached_cards":
                valid_fallback.get("mode") == "local_snapshot_fallback" and
                valid_fallback.get("cards") == cached_cards,
            "expired_lease_fixture_abstains": expired_fallback.get("mode") == "abstain" and
                expired_fallback.get("cards") == [] and
                expired_fallback.get("reason") == "missing_or_expired_cache_lease",
            "replacement_process_distinct": restarted.process.pid != first.process.pid,
            "same_endpoint_after_restart": restarted.url == first.url,
            "snapshot_unchanged_after_restart": recovered_body.get("snapshot") == snapshot,
            "recovered_search_http_200": recovered["http_status"] == 200 and recovered["error"] is None,
            "recovered_original_revision_use_correct": report["recovered_use_of_original_revision"]["passed"],
            "model_loaded_once_per_process": first_ready.get("model_load_calls") == expected_loads and
                second_ready.get("model_load_calls") == expected_loads,
            "query_counter_resets_on_restart": first_ready.get("live_encode_calls") == 0 and
                second_ready.get("live_encode_calls") == 0,
            "each_hybrid_search_runs_forward_pass": body.get("live_encode_calls") == expected_encodes and
                recovered_body.get("live_encode_calls") == expected_encodes,
        }
        report["checks"] = checks
        report["passed"] = all(checks.values())
    except Exception as exc:
        report["passed"] = False
        report["failure"] = {"phase": phase, "type": type(exc).__name__}
        if isinstance(exc, RuntimeError):
            report["failure"]["code"] = str(exc)
    finally:
        report["cleanup"] = [service.stop() for service in services]
        report["all_owned_processes_stopped"] = all(row["stopped"] for row in report["cleanup"])
        token_file.unlink(missing_ok=True)
        report["temporary_token_removed"] = not token_file.exists()
        report["passed"] = bool(report.get("passed") and report["all_owned_processes_stopped"]
                                and report["temporary_token_removed"])
        write_report(args.output, report)
    print(json.dumps({"passed": report["passed"], "output": str(args.output),
                      "failure": report.get("failure")}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
