#!/usr/bin/env python3
"""Isolated Compose conformance plus real unchanged CLI spool/flush/report cycle."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.telemetry_backend import PostgresLedger, contract_connection
from tools.search_service.smoke import request
from tools.telemetry import ledger, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".guidefold/checks/telemetry-postgres.json",
    )
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    pg = PostgresLedger("guidefold-ledger-contract")
    pg.env["GUIDEFOLD_PORT"] = "19765"
    containers = []
    subprocess.run(
        [sys.executable, "tools/search_service/dev.py", "prepare"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    try:
        pg.compose("--profile", "tools", "run", "--rm", "publish")
        pg.compose("up", "-d", "--wait", "api")
        for tenant, port in [
            ("acme-corp", 19766),
            ("tenant-a", 19767),
            ("tenant-b", 19768),
        ]:
            cid = pg.compose(
                "run",
                "--rm",
                "-d",
                "--no-deps",
                "--publish",
                f"127.0.0.1:{port}:8080",
                "-e",
                "GUIDEFOLD_TENANT=" + tenant,
                "api",
            ).strip()
            assert len(cid) == 64 and all(c in "0123456789abcdef" for c in cid)
            containers.append(cid)
            for _ in range(40):
                try:
                    if request(f"http://127.0.0.1:{port}", "/health/live")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("tenant test API did not start")
        print(
            "Running unchanged ledger/report assertions on SQLite and HTTP/Postgres",
            flush=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_telemetry_ledger.py",
                "tests/test_telemetry_report.py",
            ],
            cwd=ROOT,
            env=dict(os.environ, GUIDEFOLD_TEST_POSTGRES_LEDGER="1"),
            check=True,
        )
        pg = contract_connection()
        checks = []
        base = "http://127.0.0.1:19765"
        event = {
            "schema_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "event_type": "task_started",
            "occurred_at": "2026-09-05T12:00:00Z",
            "sequence": 1,
            "producer": "integration",
            "adapter_version": "1",
            "environment": "eval",
            "task_id": "task1",
            "pilot_cohort": "fixture",
            "eligible": True,
            "observation_capability": "tool_calls",
        }
        assert (
            request(base, "/v1/events:batch", "invalid", {"events": [event]})[0] == 401
        )
        assert (
            request(base, "/v1/events:batch", pg.token, {"events": [event] * 501})[0]
            == 413
        )
        code, body, _, _ = request(
            base,
            "/v1/events:batch",
            pg.token,
            {"events": [None, {**event, "schema_version": "future"}, event]},
        )
        assert (
            code == 200
            and body["accepted"] == [event["event_id"]]
            and len(body["rejected"]) == 2
        )
        assert all(x["retryable"] is False for x in body["rejected"])
        checks.append("auth_batch_limit_partial_ack")
        with ThreadPoolExecutor(max_workers=4) as pool:
            # Two ingest slots may reject overload; successful replays must all dedup.
            result = list(
                pool.map(
                    lambda _: request(
                        base, "/v1/events:batch", pg.token, {"events": [event]}
                    ),
                    range(12),
                )
            )
        assert all(
            code == 429
            or (
                code == 200
                and body["duplicate"] == [event["event_id"]]
                and not body["accepted"]
            )
            for code, body, _, _ in result
        )
        assert len(pg.fetch_events("local")) == 1
        checks.append("concurrent_replay_never_double_counts")
        # Client-claimed identity is retained as payload, but never binds the tenant.
        claimed = {**event, "event_id": str(uuid.uuid4()), "tenant_id": "tenant-b"}
        pg.ingest_events("local", [claimed])
        assert claimed["event_id"] in {x["event_id"] for x in pg.fetch_events("local")}
        assert not pg.fetch_events("tenant-b")
        checks.append("client_tenant_cannot_choose_partition")
        pg.reset_test_ledger()

        # Inject a storage failure after the first valid insert. A success ACK must
        # never escape a rolled-back transaction; replay the same IDs after repair.
        def sql(statement):
            return pg.compose(
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
                statement,
            )

        fail_id = "contract-storage-failure"
        retry_events = [
            {**event, "event_id": "contract-before-failure"},
            {**event, "event_id": fail_id},
        ]
        sql(
            "CREATE OR REPLACE FUNCTION gf.contract_fail_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.event_id=convert_to('contract-storage-failure','UTF8') THEN RAISE EXCEPTION 'contract_failure'; END IF; RETURN NEW; END $$; CREATE TRIGGER contract_fail_insert BEFORE INSERT ON gf.events FOR EACH ROW EXECUTE FUNCTION gf.contract_fail_insert();"
        )
        try:
            code, ack, _, _ = request(
                base, "/v1/events:batch", pg.token, {"events": retry_events}
            )
            assert code == 503 and not ack.get("accepted")
            assert not pg.fetch_events("local")
        finally:
            sql(
                "DROP TRIGGER IF EXISTS contract_fail_insert ON gf.events; DROP FUNCTION IF EXISTS gf.contract_fail_insert();"
            )
        code, ack, _, _ = request(
            base, "/v1/events:batch", pg.token, {"events": retry_events}
        )
        assert code == 200 and len(ack["accepted"]) == 2
        checks.append("storage_failure_rolls_back_no_false_ack_retry_same_ids")
        pg.reset_test_ledger()
        with tempfile.TemporaryDirectory(prefix="guidefold-ledger-cycle-") as temp:
            temp = Path(temp)
            fixture = temp / "fixture"
            shutil.copytree(
                ROOT / "examples/monorepo",
                fixture,
                ignore=shutil.ignore_patterns(".guidefold", ".git"),
            )
            cli = ROOT / "skills/guidefold/scripts/guidefold"
            cli_env = dict(os.environ, GUIDEFOLD_CACHE=str(temp / "cache"))
            cli_env.pop("GUIDEFOLD_TELEMETRY_DISABLE", None)

            def cli_run(*cmd):
                done = subprocess.run(
                    [sys.executable, str(cli), *cmd],
                    cwd=fixture,
                    env=cli_env,
                    capture_output=True,
                    text=True,
                )
                assert done.returncode == 0, done.stderr
                return done.stdout

            for _ in range(20):
                cli_run("find", "add RBAC to this new admin-only endpoint")
            for _ in range(5):
                cli_run(
                    "load", "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
                )
            spool = fixture / ".guidefold/telemetry/spool/local/dev"
            saved = {p.name: p.read_bytes() for p in spool.glob("events-*.jsonl")}
            events = [
                json.loads(line)
                for content in saved.values()
                for line in content.decode().splitlines()
            ]
            types = Counter(e["event_type"] for e in events)
            assert (
                types["search_requested"] == 20 and types["skill_load_requested"] == 5
            )
            sqlite = ledger.connect(temp / "reference.sqlite3")
            ledger.ingest(sqlite, "local", events)
            expected = report.compute_report(sqlite, "local")
            expected.pop("generated_at")
            acks = []

            # The current CLI has no bearer-token option. This TEST-ONLY transport
            # supplies its already-authorized credential; it is not an auth bypass.
            class Bridge(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def do_POST(self):
                    if (
                        self.path != "/v1/events:batch"
                        or self.headers.get("X-Guidefold-Tenant") != "local"
                    ):
                        self.send_error(403)
                        return
                    n = int(self.headers.get("Content-Length", "0"))
                    if n > 2 * 1024 * 1024:
                        self.send_error(413)
                        return
                    code, body, _, _ = request(
                        base, self.path, pg.token, raw=self.rfile.read(n)
                    )
                    acks.append(body)
                    raw = json.dumps(body).encode()
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)

            bridge = ThreadingHTTPServer(("127.0.0.1", 0), Bridge)
            worker = threading.Thread(target=bridge.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{bridge.server_port}"
                cli_run("telemetry", "flush", "--url", url)
                assert sum(len(a["accepted"]) for a in acks) == len(events)
                assert not list(spool.glob("events-*.jsonl"))
                first_acks = list(acks)
                acks.clear()
                actual = report.compute_report(pg, "local")
                actual.pop("generated_at")
                assert actual == expected
                for name, content in saved.items():
                    (spool / name).write_bytes(content)
                cli_run("telemetry", "flush", "--url", url)
                assert sum(len(a["accepted"]) for a in acks) == 0
                assert sum(len(a["duplicate"]) for a in acks) == len(events)
                replay = report.compute_report(pg, "local")
                replay.pop("generated_at")
                assert replay == expected
            finally:
                bridge.shutdown()
                bridge.server_close()
                worker.join()
                sqlite.close()
            checks.append("20_find_5_load_spool_flush_sqlite_postgres_report_parity")
            checks.append("identical_spool_replay_zero_accept_N_duplicate")
            cycle = {
                "find_commands": 20,
                "load_commands": 5,
                "event_count": len(events),
                "event_types": dict(types),
                "first_flush_accepted": sum(len(a["accepted"]) for a in first_acks),
                "second_flush_accepted": sum(len(a["accepted"]) for a in acks),
                "second_flush_duplicate": sum(len(a["duplicate"]) for a in acks),
                "report_equal": True,
                "report": actual,
                "cli_changed": False,
                "auth_transport": "test-only loopback credential injection; current CLI has no bearer option",
            }
        # Derived shadow retention follows the raw ledger retention transaction.
        sql(
            "INSERT INTO gf.search_shadow(tenant_id,search_id,repo,snapshot_id,encoder_id,status,sparse_ranked,hybrid_ranked,selected,hybrid_selected,timings,created_at) SELECT 'local',id,'fixture','fixture','fixture','ok',convert_to('[]','UTF8'),convert_to('[]','UTF8'),convert_to('[]','UTF8'),convert_to('[]','UTF8'),'{}'::jsonb,at::timestamptz FROM (VALUES ('contract-old','2000-01-01T00:00:00Z'),('contract-current','2026-09-05T12:00:00Z')) AS input(id,at) ON CONFLICT(tenant_id,search_id) DO NOTHING;"
        )
        import datetime

        pg.retention_delete(
            now=datetime.datetime(2026, 9, 5, 13, tzinfo=datetime.timezone.utc)
        )
        retained = sql(
            "SELECT search_id FROM gf.search_shadow WHERE search_id IN ('contract-old','contract-current') ORDER BY search_id"
        )
        assert "contract-current" in retained and "contract-old" not in retained
        checks.append("retention_expires_derived_shadow_rows")
        pg.compose("restart", "db", "api")
        pg.compose("up", "-d", "--wait", "api")
        after_restart = report.compute_report(pg, "local")
        after_restart.pop("generated_at")
        assert after_restart == expected
        checks.append("committed_ledger_and_report_survive_db_api_restart")
        result = {
            "passed": True,
            "contract_tests_same_assertions_both_backends": True,
            "checks": checks,
            "cycle": cycle,
            "production_ready": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "passed": True,
                    "checks": checks,
                    "cycle": {k: v for k, v in cycle.items() if k != "report"},
                }
            ),
            flush=True,
        )
    finally:
        for cid in containers:
            subprocess.run(["docker", "stop", cid], capture_output=True, check=False)
        if not args.keep:
            pg.compose("down")


if __name__ == "__main__":
    main()
