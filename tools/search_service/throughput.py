#!/usr/bin/env python3
"""Bounded service throughput diagnostics; no quality labels or fusion tuning."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request
from tools.serve_spike.repository import canonical


def stats(values):
    values = sorted(values)
    return (
        {
            f"p{p}": round(values[max(0, math.ceil(len(values) * p / 100) - 1)], 3)
            for p in (50, 95, 99)
        }
        if values
        else None
    )


def ledger(args, out):
    from tools.search_service.telemetry_backend import PostgresLedger

    pg = PostgresLedger("guidefold-ledger-contract")
    pg.env["GUIDEFOLD_IMAGE"] = args.image
    pg.compose("up", "-d", "--wait", "api")
    pg.reset_test_ledger()
    root_id = uuid.uuid4().hex
    counter = 0

    def batch():
        nonlocal counter
        counter += 1
        return [
            {
                "schema_version": "1.0",
                "event_id": f"{root_id}-{counter}-{j}",
                "event_type": "task_started",
                "occurred_at": "2026-09-05T19:00:00Z",
                "sequence": j,
                "producer": "throughput-fixture",
                "adapter_version": "1",
                "environment": "eval",
                "task_id": "throughput",
                "pilot_cohort": "synthetic",
                "eligible": True,
                "observation_capability": "tool_calls",
            }
            for j in range(500)
        ]

    def invoke(events):
        code, body, ms, headers = request(
            "http://127.0.0.1:19765", "/v1/events:batch", pg.token, {"events": events}
        )
        return {
            "status": code,
            "client_ms": ms,
            "server_ms": float(headers.get("X-Guidefold-Server-Ms", "nan")),
            "accepted": len(body.get("accepted", [])),
            "duplicate": len(body.get("duplicate", [])),
            "rejected": len(body.get("rejected", [])),
            "error": body.get("error"),
        }

    warm = [invoke(batch()) for _ in range(5)]
    assert all(x["status"] == 200 and x["accepted"] == 500 for x in warm)
    result = {
        "kind": "ledger_batch_throughput",
        "label": args.label,
        "quality_evaluated": False,
        "batch_size": 500,
        "batches_per_arm": 30,
        "warmup_batches": 5,
        "warmup_rows": warm,
        "resources_isolated": False,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "image": args.image,
        "arms": {},
        "production_ready": False,
    }
    result["image_id"] = subprocess.check_output(
        ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
    ).strip()
    for concurrency in (1, 2):
        batches = [batch() for _ in range(30)]
        for mode in ("insert", "replay"):
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                rows = list(pool.map(invoke, batches))
            elapsed = time.perf_counter() - started
            ok = [x for x in rows if x["status"] == 200]
            arm = {
                "attempted": len(rows),
                "http_ok": len(ok),
                "accepted": sum(x["accepted"] for x in rows),
                "duplicate": sum(x["duplicate"] for x in rows),
                "rejected": sum(x["rejected"] for x in rows),
                "wall_seconds": elapsed,
                "events_per_second": 500 * len(ok) / elapsed,
                "client_ms": stats([x["client_ms"] for x in ok]),
                "server_ms": stats([x["server_ms"] for x in ok]),
                "rows": rows,
            }
            name = f"{mode}_c{concurrency}"
            result["arms"][name] = arm
            out.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    {"arm": name, **{k: v for k, v in arm.items() if k != "rows"}}
                ),
                flush=True,
            )
            assert len(ok) == 30 and arm["rejected"] == 0
            assert arm["accepted"] == (15000 if mode == "insert" else 0)
            assert arm["duplicate"] == (15000 if mode == "replay" else 0)
    result["passed"] = True
    out.write_text(json.dumps(result, indent=2) + "\n")


def shadow(args, out):
    from tools.serve_spike.probe import load_queries

    queries, provenance = load_queries(200)
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    env = dict(
        os.environ,
        GUIDEFOLD_REPO="skillret-service-bench",
        GUIDEFOLD_IMAGE=args.image,
        GUIDEFOLD_RETRIEVAL_MODE="sparse",
        GUIDEFOLD_SHADOW="false",
        GUIDEFOLD_TEI_BATCH_REQUESTS=str(args.batch),
    )
    if args.queue is not None:
        env["GUIDEFOLD_SHADOW_QUEUE_CAPACITY"] = str(args.queue)
    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".guidefold/compose/gpu.env",
        "-f",
        "compose.yaml",
        "-f",
        "compose.gpu.yaml",
    ]

    def dc(*a):
        p = subprocess.run(
            cmd + list(a), cwd=ROOT, env=env, capture_output=True, text=True
        )
        if p.returncode:
            raise RuntimeError(p.stderr + p.stdout)
        return p.stdout

    def invoke(q):
        code, body, ms, headers = request(
            "http://127.0.0.1:18765",
            "/v1/search",
            token,
            {
                "schema_version": "1.1",
                "query": q["query"],
                "node": "_root",
                "deadline_ms": 5000,
            },
        )
        return {
            "query_id": q["id"],
            "search_id": body.get("search_id"),
            "status": code,
            "client_ms": ms,
            "server_ms": float(headers.get("X-Guidefold-Server-Ms", "nan")),
            "ranked_sha256": hashlib.sha256(canonical(body.get("ranked"))).hexdigest(),
            "selected_sha256": hashlib.sha256(canonical(body.get("cards"))).hexdigest(),
            "backend": body.get("backend"),
            "stages_ms": body.get("stages_ms", {}),
            "error": body.get("error"),
        }

    def metrics():
        text = (
            urllib.request.urlopen("http://127.0.0.1:18766/metrics", timeout=3)
            .read()
            .decode()
        )
        values = {}
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            key, value = line.split(" ", 1)
            if re.fullmatch(
                r"te_(request_(queue|inference|tokenization)_duration|batch_next_size)_(sum|count)",
                key,
            ):
                values[key] = float(value)
        return values

    def captures(ids):
        assert all(re.fullmatch(r"[0-9a-f-]{36}", x) for x in ids)
        literals = ",".join("'" + x + "'" for x in ids)
        sql = (
            "SELECT coalesce(json_agg(json_build_object('search_id',search_id,'status',status,'timings',timings,'error',error)),'[]') FROM gf.search_shadow WHERE tenant_id='local' AND search_id=ANY(ARRAY["
            + literals
            + "]::text[])"
        )
        return json.loads(
            dc(
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "guidefold",
                "-XAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            )
        )

    dc("up", "-d", "--wait", "tei", "api")
    health = request("http://127.0.0.1:18765", "/health/ready")[1]
    assert (
        health["n_skills"] == 6006
        and health["repository"]["repo_id"] == "skillret-service-bench"
    )
    result = {
        "kind": "sparse_response_under_gpu_shadow",
        "label": args.label,
        "batch_requests": args.batch,
        "queue_capacity_override": args.queue,
        "image_id": subprocess.check_output(
            ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
        ).strip(),
        "image": args.image,
        "resources_isolated": False,
        "quality_evaluated": False,
        "workload": provenance,
        "health": health,
        "arms": {},
        "production_ready": False,
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        reference = list(pool.map(invoke, queries))
    assert all(x["status"] == 200 for x in reference)
    result["control"] = {
        "attempted": 200,
        "client_ms": stats([x["client_ms"] for x in reference]),
        "server_ms": stats([x["server_ms"] for x in reference]),
        "rows": reference,
    }
    env["GUIDEFOLD_SHADOW"] = "true"
    dc("up", "-d", "--wait", "api")
    for q in queries[:10]:
        assert invoke(q)["status"] == 200
    time.sleep(3)
    for concurrency in (4, 8):
        before = metrics()
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows = list(pool.map(invoke, queries))
        wall = time.perf_counter() - started
        ids = [x["search_id"] for x in rows if x["status"] == 200]
        prior = -1
        stable_since = time.perf_counter()
        wait_started = stable_since
        while True:
            jobs = captures(ids)
            now = time.perf_counter()
            if len(jobs) != prior:
                prior = len(jobs)
                stable_since = now
            if (
                len(jobs) == len(ids)
                or now - stable_since >= 4
                or now - wait_started >= 35
            ):
                break
            time.sleep(0.5)
        after = metrics()
        delta = {k: after[k] - before.get(k, 0) for k in after}
        ok = [x for x in rows if x["status"] == 200]
        completed = [x for x in jobs if x["status"] == "ok"]
        parity = sum(
            a["status"] != 200
            or b["status"] != 200
            or a["ranked_sha256"] != b["ranked_sha256"]
            or a["selected_sha256"] != b["selected_sha256"]
            for a, b in zip(rows, reference)
        )
        stages = sorted({k for x in ok for k in x["stages_ms"]})
        arm = {
            "concurrency": concurrency,
            "attempted": 200,
            "http_ok": len(ok),
            "stable_ranking_mismatches": parity,
            "wall_seconds": wall,
            "requests_per_second": len(ok) / wall,
            "client_ms": stats([x["client_ms"] for x in ok]),
            "server_ms": stats([x["server_ms"] for x in ok]),
            "stages_ms": {
                k: stats([x["stages_ms"][k] for x in ok if k in x["stages_ms"]])
                for k in stages
            },
            "shadow_recorded": len(jobs),
            "shadow_ok": len(completed),
            "shadow_error": len(jobs) - len(completed),
            "shadow_missing_after_drain": len(ids) - len(jobs),
            "drain_wait_seconds": time.perf_counter() - wait_started,
            "shadow_compute_ms": stats([x["timings"]["compute_ms"] for x in jobs]),
            "shadow_queue_ms": stats([x["timings"]["queue_ms"] for x in jobs]),
            "tei_metric_deltas": delta,
            "rows": rows,
            "shadow_rows": jobs,
        }
        result["arms"][f"c{concurrency}"] = arm
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {k: v for k, v in arm.items() if k not in ("rows", "shadow_rows")}
            ),
            flush=True,
        )
        assert parity == 0 and len(ok) == 200
    result["foreground_parity_passed"] = True
    result["complete_shadow_coverage"] = all(
        a["shadow_ok"] == a["attempted"] and a["shadow_error"] == 0
        for a in result["arms"].values()
    )
    out.write_text(json.dumps(result, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=("ledger", "shadow"))
    p.add_argument("--label", required=True)
    p.add_argument("--image", default="guidefold-search:local")
    p.add_argument("--batch", type=int, choices=(1, 4), default=1)
    p.add_argument("--queue", type=int, choices=range(1, 257))
    args = p.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        raise SystemExit("invalid label")
    out = ROOT / ".guidefold/checks" / f"throughput-{args.kind}-{args.label}.json"
    if out.exists():
        raise SystemExit("Refusing to overwrite an existing measurement")
    out.parent.mkdir(parents=True, exist_ok=True)
    (ledger if args.kind == "ledger" else shadow)(args, out)


if __name__ == "__main__":
    main()
