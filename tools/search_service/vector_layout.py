#!/usr/bin/env python3
"""Persistent, isolated exact-vector A/B; no relevance labels or model tuning.

prepare creates only guidefold-vector-external/inline, using frozen benchmark
bundles and the already running batch=1 TEI worker. run alternates A/B twice.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request
from tools.search_service.throughput import stats
from tools.serve_spike.probe import load_queries
from tools.serve_spike.repository import canonical

LAYOUTS = {
    "external": ("guidefold-vector-external", 28765),
    "inline": ("guidefold-vector-inline", 28767),
}


def settings(args, layout):
    assert layout in LAYOUTS
    project, port = LAYOUTS[layout]
    bundle = json.loads(
        (ROOT / ".guidefold/compose/benchmark-embeddings-full.json").read_text()
    )
    data = bundle["embeddings"]
    assert len(data["vectors"]) == 6006 and data["repo_id"] == "skillret-service-bench"
    assert hashlib.sha256(canonical(data)).hexdigest() == bundle["sha256"]
    encoder = hashlib.sha256(canonical(data["encoder"])).hexdigest()
    env = dict(
        os.environ,
        GUIDEFOLD_IMAGE=args.image,
        GUIDEFOLD_REPO="skillret-service-bench",
        GUIDEFOLD_PORT=str(port),
        GUIDEFOLD_BENCH_DB_HOST=project + "-db-1",
        GUIDEFOLD_ENCODER_ID=encoder,
        GUIDEFOLD_RETRIEVAL_MODE="hybrid",
        GUIDEFOLD_SHADOW="false",
        GUIDEFOLD_EXPERIMENTAL_OUTPUT="true",
    )
    return project, port, env, data


def dc(project, env, *cmd):
    assert project in {x[0] for x in LAYOUTS.values()}
    p = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            "compose.yaml",
            "-f",
            "compose.vector-benchmark.yaml",
            *cmd,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if p.returncode:
        raise RuntimeError(p.stderr + p.stdout)
    return p.stdout


def sql(project, env, text):
    return dc(
        project,
        env,
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "postgres",
        "-d",
        "guidefold",
        "-XAtq",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        text,
    )


def identity(project, env):
    return json.loads(
        sql(
            project,
            env,
            """SELECT json_build_object(
      'vectors',(SELECT count(*) FROM gf.embeddings),
      'vector_digest',(SELECT md5(string_agg(urn||':'||md5(embedding::text),'' ORDER BY urn COLLATE "C")) FROM gf.embeddings),
      'storage',(SELECT attstorage FROM pg_attribute WHERE attrelid='gf.embeddings'::regclass AND attname='embedding'),
      'options',(SELECT reloptions FROM pg_class WHERE oid='gf.embeddings'::regclass),
      'heap_bytes',pg_relation_size('gf.embeddings'), 'total_bytes',pg_total_relation_size('gf.embeddings'),
      'toast_bytes',(SELECT pg_total_relation_size(reltoastrelid) FROM pg_class WHERE oid='gf.embeddings'::regclass))""",
        )
    )


def prepare(args):
    for layout in LAYOUTS:
        project, port, env, data = settings(args, layout)
        dc(project, env, "up", "-d", "--wait", "db")
        dc(project, env, "run", "--rm", "migrate")
        n = int(sql(project, env, "SELECT count(*) FROM gf.embeddings"))
        assert n in (0, 6006), "Unexpected data in isolated benchmark project"
        if n == 0:
            if layout == "inline":
                sql(
                    project,
                    env,
                    "SET lock_timeout='2s'; ALTER TABLE gf.embeddings ALTER COLUMN embedding SET STORAGE PLAIN; ALTER TABLE gf.embeddings SET (toast_tuple_target=6144)",
                )
            dc(
                project,
                env,
                "--profile",
                "tools",
                "run",
                "--rm",
                "publish",
                "publish",
                "/input/benchmark-snapshot.json",
            )
            dc(
                project,
                env,
                "--profile",
                "tools",
                "run",
                "--rm",
                "-e",
                "GUIDEFOLD_PUBLISH_ACTIVATE=true",
                "publish",
                "publish-embeddings",
                "/input/benchmark-embeddings-full.json",
            )
        sql(project, env, "ANALYZE gf.embeddings")
        meta = identity(project, env)
        assert meta["vectors"] == 6006
        assert meta["storage"] == ("e" if layout == "external" else "p")
        if layout == "inline":
            assert "toast_tuple_target=6144" in meta["options"]
        dc(project, env, "up", "-d", "--wait", "api")
        print(
            json.dumps({"layout": layout, "project": project, "identity": meta}),
            flush=True,
        )


def run(args):
    out = ROOT / ".guidefold/checks" / ("vector-persistent-" + args.label + ".json")
    if out.exists():
        raise SystemExit("Refusing to overwrite measurement")
    out.parent.mkdir(parents=True, exist_ok=True)
    queries, provenance = load_queries(200)
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    result = {
        "schema_version": 1,
        "kind": "persistent_exact_vector_layout_ab",
        "quality_evaluated": False,
        "production_ready": False,
        "resources_isolated": False,
        "container_limits": {
            "api_cpus": 2,
            "api_memory_mib": 512,
            "db_cpus": 4,
            "db_memory_mib": 2048,
        },
        "shared_encoder_batch_requests": 1,
        "mode": "hybrid_experimental_no_quality_trial",
        "workload": provenance,
        "image": args.image,
        "image_id": subprocess.check_output(
            ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
        ).strip(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "layouts": {},
        "arms": {},
    }

    def invoke(port, query):
        code, body, elapsed, headers = request(
            "http://127.0.0.1:" + str(port),
            "/v1/search",
            token,
            {
                "schema_version": "1.1",
                "query": query["query"],
                "node": "_root",
                "profile": "hook",
                "deadline_ms": 5000,
            },
        )
        stable = {
            k: v
            for k, v in body.items()
            if k not in ("request_id", "search_id", "stages_ms")
        }
        return {
            "query_id": query["id"],
            "status": code,
            "elapsed_ms": elapsed,
            "server_ms": float(headers.get("X-Guidefold-Server-Ms", "nan")),
            "stages_ms": body.get("stages_ms", {}),
            "stable_sha256": hashlib.sha256(canonical(stable)).hexdigest(),
            "ranked_sha256": hashlib.sha256(canonical(body.get("ranked"))).hexdigest(),
            "selected_sha256": hashlib.sha256(canonical(body.get("cards"))).hexdigest(),
            "snapshot": body.get("snapshot"),
            "backend": body.get("backend"),
            "error": body.get("error"),
        }

    for layout in LAYOUTS:
        project, port, env, data = settings(args, layout)
        ident = identity(project, env)
        health = request("http://127.0.0.1:" + str(port), "/health/ready")[1]
        assert ident["vectors"] == health["n_skills"] == 6006
        assert ident["storage"] == ("e" if layout == "external" else "p")
        result["layouts"][layout] = {"identity": ident, "health": health}
    assert (
        result["layouts"]["external"]["identity"]["vector_digest"]
        == result["layouts"]["inline"]["identity"]["vector_digest"]
    )
    reference = None
    for repetition in (1, 2):
        for layout in LAYOUTS:
            project, port, env, data = settings(args, layout)
            warm = [invoke(port, q) for q in queries[:20]]
            assert all(r["status"] == 200 for r in warm), warm
            for concurrency in (1, 4):
                started = time.perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    rows = list(pool.map(lambda q: invoke(port, q), queries))
                ok = [r for r in rows if r["status"] == 200]
                if reference is None:
                    reference = rows
                mismatches = sum(
                    a["status"] != 200
                    or b["status"] != 200
                    or a["stable_sha256"] != b["stable_sha256"]
                    for a, b in zip(reference, rows)
                )
                stages = sorted({k for r in ok for k in r["stages_ms"]})
                arm = {
                    "layout": layout,
                    "repetition": repetition,
                    "concurrency": concurrency,
                    "attempted": 200,
                    "http_ok": len(ok),
                    "wall_seconds": time.perf_counter() - started,
                    "stable_response_mismatches": mismatches,
                    "client_ms": stats([r["elapsed_ms"] for r in ok]),
                    "server_ms": stats([r["server_ms"] for r in ok]),
                    "stages_ms": {
                        k: stats([r["stages_ms"][k] for r in ok if k in r["stages_ms"]])
                        for k in stages
                    },
                    "rows": rows,
                }
                result["arms"][f"{layout}_r{repetition}_c{concurrency}"] = arm
                out.write_text(json.dumps(result, indent=2) + "\n")
                print(
                    json.dumps({k: v for k, v in arm.items() if k != "rows"}),
                    flush=True,
                )
    result["exact_output_parity_passed"] = all(
        a["http_ok"] == 200 and a["stable_response_mismatches"] == 0
        for a in result["arms"].values()
    )
    result["adoption_rule"] = (
        "Exact stable outputs and >=15% reduction of dense_database p95 at c1 and c4 in both repetitions; no HTTP/server budget regression."
    )
    gains = {}
    for repetition in (1, 2):
        for concurrency in (1, 4):
            a = result["arms"][f"external_r{repetition}_c{concurrency}"]
            b = result["arms"][f"inline_r{repetition}_c{concurrency}"]
            gains[f"r{repetition}_c{concurrency}"] = (
                1
                - b["stages_ms"]["dense_database"]["p95"]
                / a["stages_ms"]["dense_database"]["p95"]
            )
    result["dense_database_p95_fraction_reduction"] = gains
    result["engineering_adoption_passed"] = (
        result["exact_output_parity_passed"]
        and all(g >= 0.15 for g in gains.values())
        and all(
            a["client_ms"]["p95"] <= 400 and a["server_ms"]["p95"] <= 300
            for a in result["arms"].values()
        )
    )
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "exact_output_parity_passed",
                    "dense_database_p95_fraction_reduction",
                    "engineering_adoption_passed",
                )
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--image", default="guidefold-search:throughput-final")
    parser.add_argument("--label", default="ab1")
    args = parser.parse_args()
    if not args.label or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.label
    ):
        raise SystemExit("Invalid label")
    (prepare if args.command == "prepare" else run)(args)


if __name__ == "__main__":
    main()
