#!/usr/bin/env python3
"""Validated graph lifecycle E2E against real Go/Postgres, in this Compose project.

Publishes only synthetic test repositories; restores the configured repository.
No GPU, quality corpora, production graph or CLI modifications are involved.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.graph_parity import digest, reference, response
from tools.search_service.index import with_router_index
from tools.search_service.smoke import request
from tools.serve_spike.repository import canonical
from tools.serve_spike.server import load_cli_snapshot


def urn(name):
    return "urn:skill:graph-e2e:" + name


def revision(card):
    return hashlib.sha256(
        json.dumps(card, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def fixture(cli, sha, mode):
    nodes = {
        "_root": {"paths": ["**"]},
        "alpha": {"paths": ["services/alpha/**"]},
        "alpha.child": {"paths": ["services/alpha/child/**"]},
        "beta": {"paths": ["services/beta/**"]},
    }
    cards = {}

    def add(name, node="_root", query="", requires=(), **extra):
        u = urn(name)
        cards[u] = {
            "urn": u,
            "name": name,
            "node": node,
            "description": query,
            "digest": "",
            "triggers": [query] if query else [],
            "negative_triggers": [],
            "requires": [urn(x) for x in requires],
            "refines": [],
            "status": "active",
            "replaced_by": None,
            "_body": "Synthetic body " + name + "\nUTF-8: café 😀\n",
            **extra,
        }

    add("chain", "alpha.child", "chainanchor", ("chain-b",))
    add("chain-b", "alpha", requires=("chain-c",))
    add("chain-c", requires=("chain-d",))
    add("chain-d")
    add("cycle", "alpha.child", "cycleanchor", ("cycle-b",))
    add("cycle-b", "alpha", requires=("cycle-c",))
    add("cycle-c")
    add("diamond", "alpha.child", "diamondanchor", ("left", "left", "right"))
    add("left", "alpha", requires=("shared",))
    add("right", "alpha", requires=("shared",))
    add("shared")
    add("self", "alpha.child", "selfanchor")
    add(
        "filtered",
        "alpha.child",
        "filteranchor",
        ("hidden", "retired", "negative", "eligible"),
    )
    add("hidden", "beta")
    add("retired", "alpha", status="deprecated", replaced_by=urn("eligible"))
    add("negative", "alpha", negative_triggers=["filteranchor"])
    add("eligible")
    add("refine", "alpha.child", "refineanchor", refines=[urn("refine-parent")])
    add("refine-parent", query="refineanchor")
    add("replacement", "alpha.child", "replaceanchor")
    add(
        "obsolete",
        "alpha",
        requires=("replacement-parent",),
        status="deprecated",
        replaced_by=urn("replacement"),
    )
    add("replacement-parent", query="replaceanchor")
    idx = cli.Index.from_cards(cards, nodes, weights={"ppr_mode": mode})
    data = {
        "format": "guidefold-service-snapshot-v1",
        "repo_id": "graph-lifecycle-" + mode,
        "revision": "synthetic-v1",
        "cli_sha256": sha,
        "nodes": nodes,
        "cards": cards,
        "weights": idx.weights,
        "source": "synthetic_graph_lifecycle",
        "assets_included": False,
    }
    manual = {
        "chainanchor": ["chain-c", "chain-b", "chain"],
        "cycleanchor": ["cycle-c", "cycle-b", "cycle"],
        "diamondanchor": ["shared", "left", "right", "diamond"],
        "selfanchor": ["self"],
        "filteranchor": ["eligible", "filtered"],
    }
    return data, manual


def run(args):
    cli, sha = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
    local = ROOT / ".guidefold/compose"
    token = (local / "secrets/api_token").read_text().strip()
    env = dict(os.environ)
    if not env.get("COMPOSE_PROJECT_NAME", "").startswith("guidefold-graph-"):
        raise SystemExit("Use a dedicated COMPOSE_PROJECT_NAME=guidefold-graph-* stack")
    restore = env.get("GUIDEFOLD_REPO", "meridian")
    completed = False
    completed_modes = []
    checks, atomic = [], []

    def check(name, passed, **details):
        checks.append({"name": name, "passed": bool(passed), **details})
        assert passed, (name, details)

    def compose(*command, must_pass=True):
        proc = subprocess.run(
            ["docker", "compose", *command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if must_pass and proc.returncode:
            raise RuntimeError(proc.stderr[-2000:])
        return proc

    def bundle(data):
        return with_router_index(cli, {"snapshot": data, "sha256": digest(data)})

    def publish(value, must_pass=True):
        (local / "graph-lifecycle.json").write_bytes(canonical(value) + b"\n")
        return compose(
            "--profile",
            "tools",
            "run",
            "--rm",
            "publish",
            "publish",
            "/input/graph-lifecycle.json",
            must_pass=must_pass,
        )

    def sql(statement):
        return compose(
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
            statement,
        ).stdout.strip()

    def metadata(value):
        # Only fixed synthetic identifiers and a locally computed SHA enter this SQL.
        sid = "repository:" + value["sha256"]
        data = value["snapshot"]
        actual = json.loads(
            sql(
                "SELECT jsonb_object_agg(urn,metadata) FROM gf.skills "
                "WHERE repo='" + data["repo_id"] + "' AND snapshot_id='" + sid + "'"
            )
        )
        wanted = {
            u: {k: v for k, v in c.items() if k != "_body"}
            for u, c in data["cards"].items()
        }
        check(
            data["repo_id"] + ":" + data["revision"] + ":metadata_exact",
            actual == wanted,
            cards=len(wanted),
            digest=digest(actual),
        )

    def search(query, k=4, node="alpha.child"):
        status, body, _, _ = request(
            args.url,
            "/v1/search",
            token,
            {
                "schema_version": "1.1",
                "query": query,
                "node": node,
                "budget": {"max_cards": k},
                "deadline_ms": 5000,
            },
        )
        return status, body

    def oracle(data, query, k=4, node="alpha.child"):
        idx = cli.Index.from_cards(
            data["cards"], data["nodes"], weights=data["weights"]
        )
        return reference(cli, idx, {"query": query, "node": node}, k)

    def use(data, name, expected_status=200, node="alpha.child", old_revision=None):
        card = data["cards"][urn(name)]
        status, body, _, _ = request(
            args.url,
            "/v1/use",
            token,
            {
                "schema_version": "1.1",
                "skill_id": urn(name),
                "revision": old_revision or revision(card),
                "workspace": {
                    "repo_id": data["repo_id"],
                    "cwd": (
                        "."
                        if node == "_root"
                        else data["nodes"][node]["paths"][0].removesuffix("/**")
                    ),
                },
            },
        )
        passed = status == expected_status
        if expected_status == 200:
            passed = (
                passed
                and body.get("body") == card["_body"]
                and body.get("checksum")
                == hashlib.sha256(card["_body"].encode()).hexdigest()
            )
        check(
            data["repo_id"] + ":use:" + name + ":" + str(expected_status),
            passed,
            status=status,
        )

    try:
        for mode in ("closure", "pagerank"):
            base, manual = fixture(cli, sha, mode)
            original = bundle(base)
            env["GUIDEFOLD_REPO"] = base["repo_id"]
            publish(original)
            compose("up", "-d", "--wait", "api")
            metadata(original)
            if mode == "closure":
                invalids = [
                    (
                        "requires_self",
                        "chain",
                        "requires",
                        [urn("chain")],
                        "requires_cycle",
                    ),
                    (
                        "requires_cycle",
                        "chain-d",
                        "requires",
                        [urn("chain")],
                        "requires_cycle",
                    ),
                    (
                        "requires_missing",
                        "chain",
                        "requires",
                        [urn("absent")],
                        "requires_target_missing",
                    ),
                    (
                        "requires_type",
                        "chain",
                        "requires",
                        urn("chain-b"),
                        "requires_type",
                    ),
                    (
                        "requires_element_type",
                        "chain",
                        "requires",
                        [123],
                        "requires_type",
                    ),
                    (
                        "refines_missing",
                        "refine",
                        "refines",
                        [urn("absent")],
                        "refines_target_missing",
                    ),
                    (
                        "refines_deeper",
                        "chain-c",
                        "refines",
                        [urn("chain")],
                        "refines_deeper_target",
                    ),
                    (
                        "refines_cycle",
                        "chain-c",
                        "refines",
                        [urn("chain-c")],
                        "refines_cycle",
                    ),
                    (
                        "replacement_missing",
                        "obsolete",
                        "replaced_by",
                        urn("absent"),
                        "replaced_by_target_missing",
                    ),
                    (
                        "replacement_required",
                        "obsolete",
                        "replaced_by",
                        None,
                        "replacement_required",
                    ),
                    (
                        "replacement_type",
                        "obsolete",
                        "replaced_by",
                        [urn("replacement")],
                        "replaced_by_type",
                    ),
                    (
                        "replacement_cycle",
                        "replacement",
                        "replaced_by",
                        urn("obsolete"),
                        "replaced_by_cycle",
                    ),
                ]
                valid_index = cli.Index.from_cards(
                    base["cards"], base["nodes"], weights=base["weights"]
                )
                for name, card_name, field, value, code in invalids:
                    bad = deepcopy(base)
                    bad["revision"] = "rejected-" + name
                    bad["cards"][urn(card_name)][field] = value
                    # Graph-only mutation: retain valid lexical postings so the publisher
                    # itself, rather than Python's index builder, validates the graph.
                    bad_bundle = with_router_index(
                        cli, {"snapshot": bad, "sha256": digest(bad)}, valid_index
                    )
                    proc = publish(bad_bundle, must_pass=False)
                    check(
                        "admission:" + name,
                        proc.returncode != 0
                        and "invalid_graph_" + code in proc.stdout + proc.stderr,
                    )
                    status, unchanged = search("chainanchor")
                    check(
                        "admission:" + name + ":head_unchanged",
                        status == 200
                        and unchanged["snapshot"] == "repository:" + original["sha256"]
                        and response(unchanged) == oracle(base, "chainanchor"),
                    )
                    count = sql(
                        "SELECT count(*) FROM gf.snapshots WHERE snapshot_id='repository:"
                        + bad_bundle["sha256"]
                        + "'"
                    )
                    check("admission:" + name + ":no_snapshot_written", count == "0")
            for query, names in manual.items():
                status, body = search(query)
                wanted = [urn(x) for x in names]
                check(
                    mode + ":manual:" + query,
                    status == 200 and response(body)["selected"] == wanted,
                    expected=wanted,
                    actual=response(body)["selected"],
                )
                # Dependencies have no query token: graph hydration, not lexical coincidence.
                if query in ("chainanchor", "diamondanchor"):
                    check(
                        mode + ":dependency_outside_lexical_pool:" + query,
                        len(body["ranked"]) == 1 and len(body["cards"]) > 1,
                    )
                for name in names:
                    use(base, name)
            shared = base["cards"][urn("shared")]
            for state, rev, omitted in (
                ("hydrated", revision(shared), True),
                ("exposed", revision(shared), False),
                ("hydrated", "stale", False),
            ):
                status, delivery, _, _ = request(
                    args.url,
                    "/v1/search",
                    token,
                    {
                        "schema_version": "1.1",
                        "query": "diamondanchor",
                        "node": "alpha.child",
                        "budget": {"max_cards": 4},
                        "deadline_ms": 5000,
                        "loaded_skills": [
                            {"skill_id": urn("shared"), "revision": rev, "state": state}
                        ],
                    },
                )
                wanted = [
                    urn(n)
                    for n in manual["diamondanchor"]
                    if not (omitted and n == "shared")
                ]
                check(
                    mode + ":loaded_dependency:" + state + ":" + rev[:6],
                    status == 200 and response(delivery)["selected"] == wanted,
                )
            status, capped = search("chainanchor", 1)
            check(
                mode + ":cap_does_not_claim_completeness",
                status == 200
                and response(capped)["selected"] == [urn("chain")]
                and capped.get("composition", {}).get("status") == "not_evaluated",
            )
            for query in (*manual, "refineanchor", "replaceanchor", "zzunmatchedtoken"):
                for k in range(5):
                    for node in ("_root", "alpha", "alpha.child", "beta"):
                        status, body = search(query, k, node)
                        check(
                            mode + ":oracle:" + query + ":" + node + ":" + str(k),
                            status == 200
                            and response(body) == oracle(base, query, k, node),
                        )
            use(base, "hidden", 403)
            use(base, "retired", 409)
            if mode == "pagerank":
                for query, edge, name in (
                    ("refineanchor", "refines", "refine"),
                    ("replaceanchor", "replaced_by", "obsolete"),
                ):
                    ablated = deepcopy(base)
                    ablated["cards"][urn(name)][edge] = (
                        [] if edge == "refines" else None
                    )
                    check(
                        mode + ":edge_has_score_effect:" + edge,
                        oracle(base, query) != oracle(ablated, query),
                    )
            again = publish(original)
            check(
                mode + ":idempotent_publication",
                '"already_present":true' in again.stdout,
            )
            # Publishing the same skill IDs elsewhere must not change this API's graph.
            for dimension in ("repository", "tenant"):
                isolated = deepcopy(base)
                isolated["cards"][urn("chain")]["requires"] = [urn("eligible")]
                old_repo = env["GUIDEFOLD_REPO"]
                old_tenant = env.get("GUIDEFOLD_TENANT")
                if dimension == "repository":
                    isolated["repo_id"] += "-isolated"
                    env["GUIDEFOLD_REPO"] = isolated["repo_id"]
                else:
                    env["GUIDEFOLD_TENANT"] = "graph-isolated-tenant"
                try:
                    publish(bundle(isolated))
                finally:
                    env["GUIDEFOLD_REPO"] = old_repo
                    if old_tenant is None:
                        env.pop("GUIDEFOLD_TENANT", None)
                    else:
                        env["GUIDEFOLD_TENANT"] = old_tenant
                status, unchanged = search("chainanchor")
                check(
                    mode + ":graph_isolation:" + dimension,
                    status == 200
                    and unchanged["snapshot"] == "repository:" + original["sha256"]
                    and response(unchanged) == oracle(base, "chainanchor"),
                )
            changed = deepcopy(base)
            changed["revision"] = "synthetic-v2"
            changed["cards"][urn("new-dependency")] = {
                **deepcopy(base["cards"][urn("chain-c")]),
                "urn": urn("new-dependency"),
                "name": "new-dependency",
                "requires": [],
                "_body": "New dependency body\n",
            }
            changed["cards"][urn("chain")]["requires"] = [urn("new-dependency")]
            del changed["cards"][urn("chain-b")]
            updated = bundle(changed)
            expected_versions = {
                "repository:"
                + b["sha256"]: (b["snapshot"], oracle(b["snapshot"], "chainanchor"))
                for b in (original, updated)
            }
            stop, ready = threading.Event(), threading.Event()

            def reader():
                rows = []
                deadline = time.monotonic() + 45
                tail = 8
                while time.monotonic() < deadline:
                    if stop.is_set():
                        tail -= 1
                        if tail < 0:
                            break
                    status, body = search("chainanchor")
                    sid = body.get("snapshot")
                    expected = expected_versions.get(sid)
                    valid = status == 200 and expected is not None
                    if valid:
                        data, want = expected
                        valid = response(body) == want and all(
                            c["revision"] == revision(data["cards"][c["urn"]])
                            for c in body["cards"] + body["ranked"]
                        )
                    rows.append(
                        {
                            "mode": mode,
                            "snapshot": sid,
                            "status": status,
                            "passed": valid,
                        }
                    )
                    ready.set()
                    stop.wait(0.01)
                return rows

            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(reader) for _ in range(4)]
                try:
                    check(mode + ":readers_started", ready.wait(8))
                    publish(updated)
                finally:
                    stop.set()
                samples = [r for f in futures for r in f.result()]
            atomic.extend(samples)
            counts = Counter(r["snapshot"] for r in samples)
            check(
                mode + ":atomic_live_graph_switch",
                all(r["passed"] for r in samples)
                and set(counts) == set(expected_versions),
                attempts=len(samples),
                snapshots=dict(counts),
            )
            metadata(updated)
            status, body = search("chainanchor")
            check(
                mode + ":new_dependency_replaces_old",
                status == 200
                and response(body)["selected"] == [urn("new-dependency"), urn("chain")],
            )
            use(changed, "new-dependency")
            use(
                changed,
                "chain",
                409,
                old_revision=revision(base["cards"][urn("chain")]),
            )
            use(base, "chain-b", 404)
            # Failure after graph/card COPY, inside the publication transaction: scoped to test repo.
            sql(
                "CREATE OR REPLACE FUNCTION public.graph_e2e_abort() RETURNS trigger LANGUAGE plpgsql AS "
                "'BEGIN IF NEW.repo = ''"
                + base["repo_id"]
                + "'' THEN RAISE EXCEPTION ''graph_e2e_abort''; END IF; RETURN NEW; END'; "
                "CREATE TRIGGER graph_e2e_abort BEFORE INSERT OR UPDATE ON gf.heads "
                "FOR EACH ROW EXECUTE FUNCTION public.graph_e2e_abort()"
            )
            rejected = deepcopy(changed)
            rejected["revision"] = "synthetic-failed-v3"
            rejected["cards"][urn("chain")]["requires"] = [urn("eligible")]
            failed_bundle = bundle(rejected)
            try:
                failed = publish(failed_bundle, must_pass=False)
                check(
                    mode + ":transaction_failure_observed",
                    failed.returncode != 0
                    and "graph_e2e_abort" in (failed.stdout + failed.stderr),
                )
            finally:
                sql(
                    "DROP TRIGGER IF EXISTS graph_e2e_abort ON gf.heads; DROP FUNCTION IF EXISTS public.graph_e2e_abort()"
                )
            status, body = search("chainanchor")
            check(
                mode + ":failed_publish_keeps_active_graph",
                status == 200
                and body["snapshot"] == "repository:" + updated["sha256"]
                and response(body) == oracle(changed, "chainanchor"),
            )
            count = sql(
                "SELECT count(*) FROM gf.snapshots WHERE snapshot_id='repository:"
                + failed_bundle["sha256"]
                + "'"
            )
            check(mode + ":failed_publish_rolls_back_rows", count == "0")
            publish(original)
            status, restored = search("chainanchor")
            check(
                mode + ":rollback_restores_graph",
                status == 200
                and restored["snapshot"] == "repository:" + original["sha256"]
                and response(restored) == oracle(base, "chainanchor"),
            )
            use(base, "chain-b")
            use(base, "chain")
            compose("restart", "api")
            compose("up", "-d", "--wait", "api")
            status, restarted = search("chainanchor")
            check(
                mode + ":restart_preserves_graph",
                status == 200 and response(restarted) == response(restored),
            )
            completed_modes.append(mode)
            print(mode, "lifecycle passed", flush=True)
        completed = True
    finally:
        env["GUIDEFOLD_REPO"] = restore
        compose("up", "-d", "--wait", "api")
        result = {
            "schema_version": 1,
            "kind": "graph_lifecycle_e2e",
            "cli_sha256": sha,
            "quality_evaluated": False,
            "checks": checks,
            "atomic_responses": atomic,
            "checks_count": len(checks),
            "atomic_requests": len(atomic),
            "passed": completed
            and len(checks) > 0
            and all(c["passed"] for c in checks),
            "completed_modes": completed_modes,
            "publisher_graph_admission": True,
            "publisher_full_catalog_lint": False,
            "production_ready": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in ("checks", "atomic_responses")
                }
            ),
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="http://127.0.0.1:" + os.environ.get("GUIDEFOLD_PORT", "8765")
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/checks/graph-lifecycle.json"
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
