#!/usr/bin/env python3
"""Frozen DEV only: one dense and one hybrid arm against the unchanged CLI F0.

Protocol: docs/reports/bakeoff/GPU-HYBRID-PROTOCOL-v1.md. No test-A/B path,
parameter sweep, quality tuning, or implicit retries of measured responses.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.quality import (
    aggregate,
    clean,
    compare,
    dataset,
    source_identity,
)
from tools.search_service.smoke import request
from tools.serve_spike.repository import canonical
from tools.serve_spike.server import load_cli_snapshot
from tools.eval import skillret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dense", "hybrid"), required=True)
    parser.add_argument("--url", default="http://127.0.0.1:18765")
    parser.add_argument("--tei-url", default="http://127.0.0.1:18766")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / ".guidefold/checks/gpu-quality"
    )
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    report = out / (args.mode + ".json")
    if report.exists():
        raise SystemExit("Completed arm exists; refusing to rerun.")
    cli, cli_sha = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
    cards, nodes, cases, index, revision, conversion = dataset("dev", cli)
    snapshot = json.loads(
        (ROOT / ".guidefold/compose/parity-snapshot.json").read_bytes()
    )
    assert canonical(cards) == canonical(snapshot["snapshot"]["cards"])
    assert canonical(nodes) == canonical(snapshot["snapshot"]["nodes"])
    assert canonical(index.weights) == canonical(snapshot["snapshot"]["weights"])
    assert len(cases) == 1000 and len(cards) == 10123
    status, health, _, _ = request(args.url, "/health/ready")
    assert status == 200 and health["retrieval_mode"] == args.mode
    assert health["snapshot"] == "repository:" + snapshot["sha256"]
    assert health["quality_admitted"] is False
    info = json.load(urllib.request.urlopen(args.tei_url + "/info"))
    assert (
        info["max_batch_requests"] == 1
    ), "DEV requires the preregistered repeatability profile"
    identity = {
        "dataset": "frozen_skillret_train_dev",
        "mode": args.mode,
        "n_queries": len(cases),
        "n_skills": len(cards),
        "cli_sha256": cli_sha,
        "snapshot_sha256": snapshot["sha256"],
        "cases_sha256": hashlib.sha256(canonical(cases)).hexdigest(),
        "corpus_revision": revision,
        "encoder_id": health["encoder_id"],
        "tei_info": info,
        "source_sha256": source_identity(),
        "protocol": "GPU-HYBRID-PROTOCOL-v1",
        "protocol_commit": "17220fd4498675c6d20bb9a31928dcb45e96a94e",
        "conversion": conversion,
        "labels_sent_to_service": False,
        "tuned_on_quality_results": False,
        "independent_generalization": False,
        "harmful_labels_available": False,
        "HSR@4": None,
        "quality_admitted": False,
        "production_ready": False,
    }
    identity_file = out / (args.mode + "-identity.json")
    if identity_file.exists():
        assert (
            json.loads(identity_file.read_text()) == identity
        ), "Identity changed; refusing resume"
    else:
        identity_file.write_bytes(canonical(identity) + b"\n")
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    rows_file = out / (args.mode + "-responses.jsonl")
    rows = [json.loads(line) for line in rows_file.open()] if rows_file.exists() else []
    done = {row["query_id"]: row for row in rows}
    assert len(done) == len(rows) and set(done) <= {c["qid"] for c in cases}

    def invoke(case):
        code, body, ms, _ = request(
            args.url,
            "/v1/search",
            token,
            {
                "schema_version": "1.1",
                "query": case["query"],
                "node": "_root",
                "profile": "hook",
                "deadline_ms": 5000,
            },
        )
        return {
            "query_id": case["qid"],
            "status": code,
            "snapshot": body.get("snapshot"),
            "model": body.get("model"),
            "backend": body.get("backend"),
            "ranked": [[r["urn"], r["score"]] for r in body.get("ranked", [])],
            "selected": [r["urn"] for r in body.get("cards", [])],
            "elapsed_ms": ms,
            "live_encode_calls": body.get("live_encode_calls"),
            "error": body.get("error"),
        }

    pending = [c for c in cases if c["qid"] not in done]
    with rows_file.open("a") as file, ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(invoke, pending):
            file.write(json.dumps(row) + "\n")
            file.flush()
            done[row["query_id"]] = row
            if len(done) % 100 == 0:
                print(
                    json.dumps(
                        {"mode": args.mode, "completed": len(done), "total": len(cases)}
                    ),
                    flush=True,
                )
    assert all(
        r["status"] == 200
        and r["snapshot"] == health["snapshot"]
        and r["model"] == health["encoder_id"]
        and r["live_encode_calls"] == 1
        and r["backend"] == health["backend"]
        for r in done.values()
    ), "HTTP/identity error retained; arm incomplete"
    baseline_file = out / "f0.json.gz"
    baseline_identity = {
        "cli_sha256": cli_sha,
        "snapshot_sha256": snapshot["sha256"],
        "cases_sha256": identity["cases_sha256"],
    }
    if baseline_file.exists():
        baseline = json.loads(gzip.decompress(baseline_file.read_bytes()))
        assert baseline["identity"] == baseline_identity
        baseline = baseline["rows"]
    else:
        print("Computing unchanged CLI F0 reference", flush=True)
        a_ret, a_inj, _, _ = skillret.run_arm_parallel(
            cli.Router(index), cases, lambda c: c["node"], False, n_workers=4
        )
        baseline = {
            c["qid"]: {"retrieval": r, "injection": inj}
            for (r, c), (inj, _) in zip(a_ret, a_inj)
        }
        baseline_file.write_bytes(
            gzip.compress(
                canonical({"identity": baseline_identity, "rows": baseline}), mtime=0
            )
        )
    a_ret = [(baseline[c["qid"]]["retrieval"], c) for c in cases]
    a_inj = [(baseline[c["qid"]]["injection"], c) for c in cases]
    b_ret = [([r[0] for r in done[c["qid"]]["ranked"]], c) for c in cases]
    b_inj = [(done[c["qid"]]["selected"], c) for c in cases]
    comparison = compare(a_ret, a_inj, b_ret, b_inj)
    # Shared historical helper names its treatment 'paradedb'; only rename the key.
    for metric in comparison["all_answerable_diagnostic"].values():
        metric[args.mode] = metric.pop("paradedb")
    result = {
        **identity,
        "f0": aggregate(a_ret, a_inj),
        args.mode: aggregate(b_ret, b_inj),
        "comparison": comparison,
        "http_attempts": len(done),
        "http_errors": 0,
        "latency_note": "Quality run timings are diagnostic; use the separate latency benchmark.",
    }
    report.write_text(json.dumps(clean(result), indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            clean(
                {
                    "mode": args.mode,
                    "f0": result["f0"]["official"],
                    args.mode: result[args.mode]["official"],
                }
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
