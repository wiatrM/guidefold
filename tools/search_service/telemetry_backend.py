#!/usr/bin/env python3
"""Operator/test storage adapter for the unchanged telemetry ledger/report APIs.

Writes go through the authenticated HTTP service. Reads and retention use the Go
operator commands over Docker Compose; there is no public cross-tenant read API.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request


class PostgresLedger:
    def __init__(self, project="guidefold-search", urls=None):
        self.project = project
        self.urls = urls or {"local": "http://127.0.0.1:8765"}
        self.env = dict(os.environ, GUIDEFOLD_TENANT="local", GUIDEFOLD_REPO="meridian")
        if project == "guidefold-ledger-contract":
            self.env["GUIDEFOLD_PORT"] = "19765"
        self.token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()

    def compose(self, *args):
        result = subprocess.run(
            ["docker", "compose", "-p", self.project, "-f", "compose.yaml", *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout

    def ingest_events(self, tenant_id, batch):
        if tenant_id not in self.urls:
            raise ValueError("no authenticated endpoint for tenant")
        code, body, _, _ = request(
            self.urls[tenant_id], "/v1/events:batch", self.token, {"events": batch}
        )
        if code != 200:
            raise RuntimeError(f"ingest HTTP {code}: {body}")
        return {key: body[key] for key in ("accepted", "duplicate", "rejected")}

    def fetch_events(self, tenant_id, event_type=None):
        raw = self.compose(
            "exec",
            "-T",
            "-e",
            "GUIDEFOLD_TENANT=" + tenant_id,
            "api",
            "/app/guidefold-search",
            "telemetry-export",
        )
        data = json.loads(raw)
        if data["tenant_id"] != tenant_id:
            raise ValueError("export tenant mismatch")
        return [
            e
            for e in data["events"]
            if event_type is None or e["event_type"] == event_type
        ]

    def tenants(self):
        return json.loads(
            self.compose(
                "exec", "-T", "api", "/app/guidefold-search", "telemetry-tenants"
            )
        )

    def retention_delete(self, older_than_days=90, now=None):
        args = [
            "--profile",
            "tools",
            "run",
            "--rm",
            "--no-deps",
            "publish",
            "telemetry-retain",
            str(older_than_days),
        ]
        if now is not None:
            args.append(now.isoformat())
        return json.loads(self.compose(*args))["deleted"]

    def reset_test_ledger(self):
        if self.project != "guidefold-ledger-contract":
            raise ValueError(
                "test reset is restricted to the isolated contract-test project"
            )
        self.compose(
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "guidefold",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "TRUNCATE gf.events",
        )

    def close(self):
        pass


def contract_connection():
    conn = PostgresLedger(
        "guidefold-ledger-contract",
        {
            "local": "http://127.0.0.1:19765",
            "acme-corp": "http://127.0.0.1:19766",
            "tenant-a": "http://127.0.0.1:19767",
            "tenant-b": "http://127.0.0.1:19768",
        },
    )
    conn.reset_test_ledger()
    return conn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="guidefold-search")
    parser.add_argument("--tenant", default="local")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    from tools.telemetry import report

    result = report.compute_report(PostgresLedger(args.project), args.tenant)
    print(
        json.dumps(result, indent=2)
        if args.format == "json"
        else report.render_markdown(result)
    )


if __name__ == "__main__":
    main()
