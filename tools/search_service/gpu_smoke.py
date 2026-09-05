#!/usr/bin/env python3
"""Real GPU worker recovery and transactional vector publication checks."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request
from tools.serve_spike.repository import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18765")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/checks/gpu-smoke.json"
    )
    args = parser.parse_args()
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    envelope = json.loads(args.bundle.read_bytes())
    data = envelope["embeddings"]
    checks = []
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (
            ROOT / "tools/serve_spike/contracts/harness-service-v1.1.schema.json"
        ).read_text()
    )
    validators = {
        kind: Draft202012Validator(
            {**schema, "$ref": "#/$defs/" + kind + "_response", "oneOf": [{}]}
        )
        for kind in ("search", "use")
    }
    compose = [
        "docker",
        "compose",
        "--env-file",
        ".guidefold/compose/gpu.env",
        "-f",
        "compose.yaml",
        "-f",
        "compose.gpu.yaml",
    ]

    def expect(name, path, payload=None, statuses=(200,)):
        code, body, ms, _ = request(args.url, path, token, payload)
        checks.append({"name": name, "status": code, "elapsed_ms": round(ms, 3)})
        assert code in statuses, (name, code, body)
        if code == 200 and path.startswith("/v1/"):
            validators[path.rsplit("/", 1)[1]].validate(body)
        return body

    base = {
        "schema_version": "1.1",
        "query": "create reusable python tests",
        "node": "_root",
        "deadline_ms": 5000,
    }
    before = expect("ready", "/health/ready")
    search = expect("live_gpu_search", "/v1/search", base)
    assert search["live_encode_calls"] == 1 and search["model"] == before["encoder_id"]
    assert (
        search["snapshot"] == data["snapshot_id"]
        and search["retrieval"]["quality_admitted"] is False
    )
    card = search["cards"][0]
    use = {
        "schema_version": "1.1",
        "skill_id": card["skill_id"],
        "revision": card["revision"],
        "search_id": search["search_id"],
    }
    loaded = expect("search_to_use", "/v1/use", use)
    assert loaded["checksum"] == hashlib.sha256(loaded["body"].encode()).hexdigest()
    try:
        subprocess.run(
            compose + ["stop", "tei"], cwd=ROOT, check=True, capture_output=True
        )
        expect("live_without_gpu", "/health/live")
        expect("not_ready_without_gpu", "/health/ready", statuses=(503, 504))
        failed = expect("no_silent_sparse_fallback", "/v1/search", base, (503, 504))
        assert "cards" not in failed and "ranked" not in failed
        assert (
            expect("use_survives_worker_loss", "/v1/use", use)["checksum"]
            == loaded["checksum"]
        )
    finally:
        started = time.perf_counter()
        subprocess.run(
            compose + ["start", "tei"], cwd=ROOT, check=True, capture_output=True
        )
    for _ in range(120):
        if request(args.url, "/health/ready")[0] == 200:
            break
        time.sleep(0.5)
    restart_ms = (time.perf_counter() - started) * 1000
    recovered = expect("same_ranking_after_worker_restart", "/v1/search", base)
    assert (
        recovered["ranked"] == search["ranked"]
        and recovered["cards"] == search["cards"]
    )

    candidate = ROOT / ".guidefold/compose/gpu-invalid-embeddings.json"

    def publish(bundle, expected_error=None):
        candidate.write_bytes(canonical(bundle) + b"\n")
        result = subprocess.run(
            compose
            + [
                "--profile",
                "tools",
                "run",
                "--rm",
                "-e",
                "GUIDEFOLD_REPO=" + data["repo_id"],
                "publish-embeddings",
                "publish-embeddings",
                "/input/gpu-invalid-embeddings.json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if expected_error:
            assert (
                result.returncode != 0
                and expected_error in result.stdout + result.stderr
            ), (result.stdout + result.stderr)
        else:
            assert (
                result.returncode == 0
                and "embeddings_already_published" in result.stdout
            ), (result.stdout + result.stderr)
        assert (
            expect("publication_keeps_head", "/health/ready")["snapshot"]
            == before["snapshot"]
        )
        checks.append(
            {"name": expected_error or "idempotent_embeddings_publish", "passed": True}
        )

    publish(envelope)
    partial = copy.deepcopy(data)
    partial["vectors"].pop(next(iter(partial["vectors"])))
    publish(
        {
            "embeddings": partial,
            "sha256": hashlib.sha256(canonical(partial)).hexdigest(),
        },
        "embedding_snapshot_count_mismatch",
    )
    wrong = copy.deepcopy(data)
    wrong["encoder"]["query_prompt"] = "wrong prompt"
    publish(
        {"embeddings": wrong, "sha256": hashlib.sha256(canonical(wrong)).hexdigest()},
        "embedding_deployment_identity_mismatch",
    )
    result = {
        "passed": True,
        "checks": checks,
        "worker_restart_to_ready_ms": round(restart_ms, 3),
        "health": before,
        "production_ready": False,
    }
    args.output.write_bytes(canonical(result) + b"\n")
    print(
        json.dumps(
            {
                "passed": True,
                "checks": len(checks),
                "worker_restart_to_ready_ms": result["worker_restart_to_ready_ms"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
