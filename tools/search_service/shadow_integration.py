#!/usr/bin/env python3
"""GPU shadow HTTP parity, immutable snapshot correlation and actual CLI event join."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request
from tools.serve_spike.server import load_cli_snapshot
from tools.serve_spike.repository import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".guidefold/checks/shadow-integration.json",
    )
    args = parser.parse_args()
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    env = dict(
        os.environ,
        GUIDEFOLD_REPO="meridian",
        GUIDEFOLD_RETRIEVAL_MODE="sparse",
        GUIDEFOLD_SHADOW="false",
    )
    command = [
        "docker",
        "compose",
        "--env-file",
        ".guidefold/compose/gpu.env",
        "-f",
        "compose.yaml",
        "-f",
        "compose.gpu.yaml",
    ]

    def compose(*cmd, check=True):
        p = subprocess.run(
            command + list(cmd), cwd=ROOT, env=env, capture_output=True, text=True
        )
        if check and p.returncode:
            raise RuntimeError(p.stderr + p.stdout)
        return p

    def shadow(search_id):
        for _ in range(80):
            p = compose(
                "exec",
                "-T",
                "api",
                "/app/guidefold-search",
                "shadow-export",
                search_id,
                check=False,
            )
            if p.returncode == 0:
                return json.loads(p.stdout)
            time.sleep(0.1)
        raise AssertionError("shadow record not persisted")

    from jsonschema import Draft202012Validator

    schema = json.loads(
        (
            ROOT / "tools/serve_spike/contracts/harness-service-v1.1.schema.json"
        ).read_text()
    )
    validator = Draft202012Validator(
        {**schema, "$ref": "#/$defs/search_response", "oneOf": [{}]}
    )
    base = "http://127.0.0.1:18765"
    queries = [
        "add RBAC to this new admin-only endpoint",
        "test python pipeline",
        "deploy kubernetes service",
    ]
    payloads = [
        {"schema_version": "1.1", "query": q, "node": "_root", "deadline_ms": 1000}
        for q in queries
    ]

    def search(payload):
        code, body, ms, _ = request(base, "/v1/search", token, payload)
        assert code == 200, (code, body)
        validator.validate(body)
        assert (
            body["backend"] == "router_bm25f_v1" and body["degradation_reason"] is None
        )
        assert (
            body["model"] is None
            and body["live_encode_calls"] == 0
            and not body["encoder_process"]
        )
        assert body["retrieval"]["exact_legacy_ranking_parity"] is True
        return body, ms

    def stable(body):
        # Independent HTTP executions necessarily have fresh UUIDs and timings.
        return {
            k: v
            for k, v in body.items()
            if k not in ("request_id", "search_id", "stages_ms")
        }

    compose("--profile", "tools", "run", "--rm", "publish")
    compose(
        "--profile",
        "tools",
        "run",
        "--rm",
        "publish-embeddings",
        "publish-embeddings",
        "/input/fixture-embeddings.json",
    )
    compose("up", "-d", "--wait", "api")
    control = [search(p)[0] for p in payloads]
    env["GUIDEFOLD_SHADOW"] = "true"
    compose("up", "-d", "--wait", "api")
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(search, payloads * 4))
    rows = []
    for i, (answer, ms) in enumerate(answers):
        assert stable(answer) == stable(control[i % len(control)])
        capture = shadow(answer["search_id"])
        assert capture["status"] == "ok", capture
        assert capture["snapshot"] == answer["snapshot"]
        expected = [{"urn": r["urn"], "score": r["score"]} for r in answer["ranked"]]
        assert capture["sparse_ranked"][:10] == expected
        assert capture["selected"] == [
            {"urn": r["urn"], "revision": r["revision"]} for r in answer["cards"]
        ]
        assert (
            len(capture["sparse_ranked"]) <= 20 and len(capture["hybrid_ranked"]) <= 20
        )
        assert capture["hybrid_ranked"]
        rows.append(
            {
                "search_id": answer["search_id"],
                "snapshot": answer["snapshot"],
                "elapsed_ms": ms,
                "stable_response_sha256": hashlib.sha256(
                    canonical(stable(answer))
                ).hexdigest(),
                "shadow_status": capture["status"],
            }
        )
    answer = answers[0][0]
    card = answer["cards"][0]
    status, loaded, ms, _ = request(
        base,
        "/v1/use",
        token,
        {
            "schema_version": "1.1",
            "search_id": answer["search_id"],
            "skill_id": card["skill_id"],
            "revision": card["revision"],
        },
    )
    assert (
        status == 200
        and loaded["checksum"] == hashlib.sha256(loaded["body"].encode()).hexdigest()
    )
    cli, cli_sha = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
    with tempfile.TemporaryDirectory(prefix="guidefold-shadow-events-") as temp:
        temp = Path(temp)
        load_id = cli._new_id()
        cli._emit_telemetry(
            temp,
            "search_results",
            {
                "search_id": answer["search_id"],
                "status": "ok",
                "results": answer["ranked"],
                "timings": answer["stages_ms"],
                "fallback_reason": None,
            },
        )
        cli._emit_telemetry(
            temp,
            "skill_load_requested",
            {
                "search_id": answer["search_id"],
                "load_id": load_id,
                "use_id": None,
                "skill_id": card["skill_id"],
                "revision": card["revision"],
                "source": "explicit",
            },
        )
        cli._emit_telemetry(
            temp,
            "skill_load_completed",
            {
                "search_id": answer["search_id"],
                "load_id": load_id,
                "skill_id": card["skill_id"],
                "revision": card["revision"],
                "status": "ok",
                "cache_source": "service",
                "bytes": len(loaded["body"].encode()),
                "duration_ms": ms,
                "closure_status": "complete",
            },
        )
        events = [
            json.loads(line)
            for p in temp.rglob("events-*.jsonl")
            for line in p.read_text().splitlines()
        ]
        assert len(events) == 3
        status, ack, _, _ = request(base, "/v1/events:batch", token, {"events": events})
        assert status == 200 and len(ack["accepted"]) == 3
    joined = shadow(answer["search_id"])
    assert joined["joined_event_counts"] == {
        "search_results": 1,
        "skill_load_requested": 1,
        "skill_load_completed": 1,
    }
    try:
        compose("stop", "tei")
        assert request(base, "/health/ready")[0] == 200
        unavailable, ms = search(payloads[0])
        assert stable(unavailable) == stable(control[0])
        failure = shadow(unavailable["search_id"])
        assert failure["status"] == "error" and not failure["hybrid_ranked"]
    finally:
        compose("start", "tei")
        for _ in range(120):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:18766/health", timeout=2
                ) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            time.sleep(0.5)
    recovered, _ = search(payloads[0])
    assert shadow(recovered["search_id"])["status"] == "ok"
    result = {
        "passed": True,
        "http_attempts_shadow_on": len(answers),
        "concurrency": 4,
        "full_stable_payload_parity_passed": True,
        "excluded_volatile_fields": ["request_id", "search_id", "stages_ms"],
        "byte_exact_delivery_unit_test": "TestShadowCannotChangeDeliveredBytesOrWaitForGPU",
        "byte_exact_across_independent_http_requests_claimed": False,
        "search_results_and_load_join_passed": True,
        "joined_event_counts": joined["joined_event_counts"],
        "client_emitter_sha256": cli_sha,
        "client_file_modified": False,
        "gpu_outage_keeps_sparse_ready_and_identical_stable_payload": True,
        "worker_recovery_passed": True,
        "snapshot_pinned": True,
        "rows": rows,
        "production_ready": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)


if __name__ == "__main__":
    main()
