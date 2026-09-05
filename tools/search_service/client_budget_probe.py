"""Diagnose the current CLI adapter selection budget against the local Compose service.

Diagnostic only: an omitted-budget mismatch is reported, never a passing parity gate.
"""

import argparse, json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.graph_parity import reference, response
from tools.search_service.smoke import request
from tools.serve_spike.server import load_cli_snapshot


def run(args):
    cli, sha = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
    data = json.loads((ROOT / ".guidefold/compose/snapshot.json").read_text())[
        "snapshot"
    ]
    idx = cli.Index.from_cards(data["cards"], data["nodes"], weights=data["weights"])
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    url = args.url
    case = {
        "id": "simple-001",
        "query": "write an ADR for this cross-platform decision",
        "node": "_root",
    }
    rows = []
    with tempfile.TemporaryDirectory(prefix="guidefold-client-parity-") as temp:
        root = Path(temp)
        (root / "guidefold.yaml").write_text("telemetry:\n  enabled: false\n")
        for k, profile in ((3, "hook"), (4, "interactive"), (8, "interactive")):
            got = cli.search_with_backend(
                root,
                cli.Router(idx),
                case["query"],
                case["node"],
                profile=profile,
                k=k,
                search_id="graph-budget-probe-" + str(k),
                search_cfg={
                    "backend": "service",
                    "url": url,
                    "token": token,
                    "deadline_ms": 300,
                    "config_error": False,
                },
            )
            row = {
                "k": k,
                "profile": profile,
                "backend": got["backend"],
                "parity_mismatch": got["parity_mismatch"],
                "local": [c["urn"] for c in got["local_selected"]],
                "remote": [c["urn"] for c in got["selected"]],
            }
            if k <= 4:
                status, body, _, _ = request(
                    url,
                    "/v1/search",
                    token,
                    {
                        "schema_version": "1.1",
                        "query": case["query"],
                        "node": case["node"],
                        "profile": profile,
                        "budget": {"max_cards": k},
                        "deadline_ms": 300,
                    },
                )
                row["explicit_budget_status"] = status
                row["explicit_budget_matches_local"] = response(body) == reference(
                    cli, idx, case, k
                )
            rows.append(row)
    result = {
        "cli_sha256": sha,
        "case_id": case["id"],
        "real_cli_adapter": True,
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    assert all(r["backend"] == "online_sparse" for r in rows)
    assert all(r.get("explicit_budget_matches_local", True) for r in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="http://127.0.0.1:" + os.environ.get("GUIDEFOLD_PORT", "8765")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".guidefold/checks/client-budget-probe.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
