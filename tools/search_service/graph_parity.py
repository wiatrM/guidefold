#!/usr/bin/env python3
"""Real Meridian graph SEARCH/USE parity, independent of retrieval quality tuning.

Run after dev.py deploy. Publishes test-only repositories in this Compose project,
then restores its original repository. Never changes the CLI or the corpus.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.index import with_router_index
from tools.search_service.smoke import request
from tools.serve_spike.context import ContextError, map_path
from tools.serve_spike.repository import canonical
from tools.serve_spike.server import load_cli_snapshot


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def reference(cli, index, case, k):
    router = cli.Router(index)
    query, node = case["query"], case["node"]
    allowed, _ = router.policy_filter(node, query)
    ranked = router.score(router.candidates(query, node), query, node)
    selected = router.select(ranked, k=k, admissible=set(allowed), query=query)
    return {
        "ranked": [[r["urn"], r["score"]] for r in ranked[:10]],
        "selected": [r["urn"] for r in selected],
    }


def response(body):
    return {
        "ranked": [[r["urn"], r["score"]] for r in body.get("ranked", [])],
        "selected": [r["urn"] for r in body.get("cards", [])],
    }


def run(args):
    cli, sha = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
    local = ROOT / ".guidefold/compose"
    original = json.loads((local / "snapshot.json").read_text())["snapshot"]
    assert original["cli_sha256"] == sha, "Re-run dev.py prepare for the current CLI"
    cases = []
    for path in sorted((ROOT / "tests/golden").glob("*.yaml")):
        cases.extend(yaml.safe_load(path.read_text())["cases"])
    assert len(cases) == 220, "Review the graph gate if the regression corpus changes"
    token = (local / "secrets/api_token").read_text().strip()
    env = dict(os.environ)
    restore_repo = env.get("GUIDEFOLD_REPO", "meridian")

    def compose(*command):
        subprocess.run(
            ["docker", "compose", *command],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    rows, uses, diagnostics, coverage = [], [], [], {}
    try:
        for mode in ("closure", "pagerank"):
            data = deepcopy(original)
            data["repo_id"] = "meridian-graph-parity-" + mode
            data["weights"]["ppr_mode"] = mode
            index = cli.Index.from_cards(
                data["cards"], data["nodes"], weights=data["weights"]
            )
            bundle = with_router_index(
                cli, {"snapshot": data, "sha256": digest(data)}, index
            )
            (local / "graph-parity-snapshot.json").write_bytes(
                canonical(bundle) + b"\n"
            )
            env["GUIDEFOLD_REPO"] = data["repo_id"]
            compose(
                "--profile",
                "tools",
                "run",
                "--rm",
                "publish",
                "publish",
                "/input/graph-parity-snapshot.json",
            )
            compose("up", "-d", "--wait", "api")
            expected = {
                (c["id"], k): reference(cli, index, c, k)
                for c in cases
                for k in (0, 1, 3, 4, 8)
            }
            graphless = deepcopy(index)
            graphless.graph = {
                kind: {u: [] for u in index.cards} for kind in index.graph
            }
            coverage[mode] = {
                "graph_sensitive_cases": sum(
                    reference(cli, graphless, c, 4) != expected[c["id"], 4]
                    for c in cases
                ),
                "graph_edges": {
                    kind: sum(map(len, edges.values()))
                    for kind, edges in index.graph.items()
                },
                "nodes": len(data["nodes"]),
                "snapshot_sha256": bundle["sha256"],
                "router_index_sha256": bundle["router_index_sha256"],
            }
            assert coverage[mode]["graph_sensitive_cases"] > 0, "Graph is not exercised"

            def invoke(item):
                case, k, addressing = item
                payload = {
                    "schema_version": "1.1",
                    "query": case["query"],
                    "budget": {"max_cards": k},
                    "deadline_ms": 5000,
                }
                if addressing == "node":
                    payload["node"] = case["node"]
                else:
                    payload["workspace"] = {
                        "repo_id": data["repo_id"],
                        "revision": data["revision"],
                        "cwd": case["cwd"],
                    }
                expected_status, expected_error = 200, None
                want = expected[case["id"], k]
                if addressing == "workspace":
                    try:
                        resolved = map_path(data["nodes"], case["cwd"])
                        want = reference(cli, index, {**case, "node": resolved}, k)
                    except ContextError as error:
                        expected_status, expected_error = error.status, str(error)
                        want = {"ranked": [], "selected": []}
                status, body, elapsed, _ = request(
                    args.url, "/v1/search", token, payload
                )
                got = response(body)
                revisions_ok = all(
                    r.get("revision")
                    == hashlib.sha256(
                        json.dumps(
                            data["cards"][r["urn"]], sort_keys=True, ensure_ascii=False
                        ).encode()
                    ).hexdigest()
                    for r in body.get("ranked", []) + body.get("cards", [])
                )
                passed = (
                    status == 200
                    and body.get("backend") == "router_bm25f_v1"
                    and body.get("degradation_reason") is None
                    and got == want
                    and revisions_ok
                )
                if expected_status != 200:
                    passed = (
                        status == expected_status
                        and body.get("error") == expected_error
                    )
                return {
                    "case_id": case["id"],
                    "mode": mode,
                    "k": k,
                    "addressing": addressing,
                    "expected_status": expected_status,
                    "status": status,
                    "passed": passed,
                    "elapsed_ms": elapsed,
                    "expected_sha256": digest(want),
                    "actual_sha256": digest(got),
                    **(
                        {"expected": want, "actual": got, "error": body.get("error")}
                        if not passed
                        else {}
                    ),
                }

            with ThreadPoolExecutor(max_workers=4) as pool:
                rows.extend(
                    pool.map(
                        invoke,
                        (
                            (c, k, addressing)
                            for c in cases
                            for k in (0, 1, 3, 4)
                            for addressing in ("node", "workspace")
                        ),
                    )
                )
            # Mirror E2.6's omitted budget at k=3 (hook) and k=8 (find).
            # This diagnostic is distinct from the equal-input scorer gate.
            for k, profile in ((3, "hook"), (8, "interactive")):
                case = next(
                    c for c in cases if expected[c["id"], k] != expected[c["id"], 4]
                )
                status, body, _, _ = request(
                    args.url,
                    "/v1/search",
                    token,
                    {
                        "schema_version": "1.1",
                        "query": case["query"],
                        "node": case["node"],
                        "profile": profile,
                        "deadline_ms": 5000,
                    },
                )
                got = response(body)
                diagnostics.append(
                    {
                        "case_id": case["id"],
                        "mode": mode,
                        "profile": profile,
                        "local_k": k,
                        "local": expected[case["id"], k],
                        "remote": got,
                        "status": status,
                        "remote_matches_k4": got == expected[case["id"], 4],
                        "omitted_budget_reproduces_mismatch": got
                        != expected[case["id"], k],
                    }
                )
            for urn, card in sorted(data["cards"].items()):
                revision = hashlib.sha256(
                    json.dumps(card, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                status, body, _, _ = request(
                    args.url, "/v1/use", token, {"skill_id": urn, "revision": revision}
                )
                checksum = hashlib.sha256(card["_body"].encode()).hexdigest()
                active = card["status"] == "active"
                passed = (
                    (
                        status == 200
                        and body.get("body") == card["_body"]
                        and body.get("checksum") == checksum
                    )
                    if active
                    else (status == 409 and body.get("error") == "skill_not_active")
                )
                uses.append(
                    {
                        "mode": mode,
                        "urn": urn,
                        "status": status,
                        "expected_status": 200 if active else 409,
                        "passed": passed,
                    }
                )
            print(
                mode,
                "SEARCH",
                sum(r["mode"] == mode for r in rows),
                "mismatches",
                sum(not r["passed"] for r in rows if r["mode"] == mode),
                flush=True,
            )
    finally:
        env["GUIDEFOLD_REPO"] = restore_repo
        compose("up", "-d", "--wait", "api")
    result = {
        "schema_version": 1,
        "kind": "meridian_graph_http_cli_parity",
        "cli_sha256": sha,
        "source_revision": original["revision"],
        "quality_evaluated": False,
        "corpus_changed": False,
        "attempted": len(rows),
        "search_success_expected": sum(r["expected_status"] == 200 for r in rows),
        "scope_rejections_expected": sum(r["expected_status"] != 200 for r in rows),
        "mismatches": sum(not r["passed"] for r in rows),
        "exact_output_parity_passed": all(r["passed"] for r in rows),
        "use_attempted": len(uses),
        "use_parity_passed": all(r["passed"] for r in uses),
        "coverage": coverage,
        "client_budget_diagnostics": diagnostics,
        "responses": rows,
        "use_responses": uses,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("responses", "use_responses", "client_budget_diagnostics")
            }
        ),
        flush=True,
    )
    if not result["exact_output_parity_passed"] or not result["use_parity_passed"]:
        raise SystemExit("GRAPH PARITY FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="http://127.0.0.1:" + os.environ.get("GUIDEFOLD_PORT", "8765")
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/checks/graph-parity.json"
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
