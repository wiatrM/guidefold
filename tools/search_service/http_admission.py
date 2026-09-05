#!/usr/bin/env python3
"""Real HTTP/1 slow-upload admission and recovery E2E; run on a dedicated Compose stack."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.smoke import request


def run(args):
    address = urlsplit(args.url)
    if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit(
            "This slow-upload test requires a dedicated loopback HTTP service"
        )
    token = (ROOT / ".guidefold/compose/secrets/api_token").read_text().strip()
    rows = []
    opened = []
    completed = False

    def record(name, passed, **details):
        rows.append({"name": name, "passed": bool(passed), **details})
        if not passed and not args.baseline:
            raise AssertionError((name, details))

    def wire(path, auth=True, expect_continue=True):
        sock = socket.create_connection(
            (address.hostname, address.port or 80), timeout=2
        )
        sock.settimeout(2)
        opened.append(sock)
        # 100 Continue proves Go has begun reading this body. Send no body bytes.
        # An overloaded server must instead send its final 429 immediately.
        headers = (
            f"POST {path} HTTP/1.1\r\nHost: localhost\r\n"
            f'Authorization: Bearer {token if auth else "invalid"}\r\n'
            "Content-Type: application/json\r\nContent-Length: 1\r\n"
            + ("Expect: 100-continue\r\n" if expect_continue else "")
            + "\r\n"
        )
        start = time.monotonic()
        sock.sendall(headers.encode())
        stream = sock.makefile("rb")
        try:
            first = stream.readline().decode().strip()
        except socket.timeout:
            stream.close()
            if expect_continue:
                raise
            return sock, 0, {}, (time.monotonic() - start) * 1000
        status = int(first.split()[1])
        received = {}
        while True:
            line = stream.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            key, value = line.decode().split(":", 1)
            received[key.lower()] = value.strip()
        stream.close()
        return sock, status, received, (time.monotonic() - start) * 1000

    def call(name, path, payload=None, expected=200):
        status, body, ms, headers = request(args.url, path, token, payload)
        record(
            name,
            status == expected,
            status=status,
            expected_status=expected,
            elapsed_ms=ms,
        )
        return body, headers

    query = {
        "schema_version": "1.1",
        "query": "postgres production",
        "node": "_root",
        "deadline_ms": 1000,
    }
    try:
        initial, _ = call("warm_search", "/v1/search", query)
        card = initial["cards"][0]
        use = {"skill_id": card["skill_id"], "revision": card["revision"]}
        for repeat in range(3):
            for path, capacity in (("/v1/search", 8), ("/v1/events:batch", 2)):
                label = str(repeat) + ":" + path
                current = []
                try:
                    for i in range(capacity):
                        sock, status, _, _ = wire(path)
                        current.append(sock)
                        record(
                            label + ":admitted:" + str(i), status == 100, status=status
                        )
                    sock, status, headers, ms = wire(path)
                    current.append(sock)
                    record(
                        label + ":reject_before_upload",
                        status == 429,
                        status=status,
                        elapsed_ms=ms,
                    )
                    record(
                        label + ":retry_and_close",
                        headers.get("retry-after") == "1"
                        and headers.get("connection", "").lower() == "close",
                    )
                    sock, status, _, ms = wire(path, expect_continue=False)
                    current.append(sock)
                    record(
                        label + ":reject_plain_slow_upload",
                        status == 429,
                        status=status,
                        elapsed_ms=ms,
                    )
                    sock, status, _, _ = wire(path, auth=False)
                    current.append(sock)
                    record(label + ":auth_before_body", status == 401, status=status)
                    call(label + ":live", "/health/live")
                    call(label + ":ready", "/health/ready")
                    if path == "/v1/search":
                        call(label + ":search_overload", "/v1/search", query, 429)
                        call(label + ":use_overload", "/v1/use", use, 429)
                        call(
                            label + ":telemetry_independent",
                            "/v1/events:batch",
                            {"events": []},
                        )
                    else:
                        call(
                            label + ":telemetry_overload",
                            "/v1/events:batch",
                            {"events": []},
                            429,
                        )
                        call(label + ":search_independent", "/v1/search", query)
                        call(label + ":use_independent", "/v1/use", use)
                finally:
                    for sock in current:
                        sock.close()
                # Closing partial uploads cancels their reads; every reserved slot must return.
                deadline = time.monotonic() + 2
                status = event_status = None
                while time.monotonic() < deadline:
                    status, body, _, _ = request(args.url, "/v1/search", token, query)
                    event_status, _, _, _ = request(
                        args.url, "/v1/events:batch", token, {"events": []}
                    )
                    if status == 200 and event_status == 200:
                        break
                    time.sleep(0.02)
                record(
                    label + ":recovery",
                    status == 200 and event_status == 200,
                    search_status=status,
                    telemetry_status=event_status,
                )
                call(label + ":use_after_cancelled_upload", "/v1/use", use)
        completed = True
    finally:
        for sock in opened:
            sock.close()
        result = {
            "schema_version": 1,
            "kind": "http_body_admission_e2e",
            "baseline_observation": args.baseline,
            "completed": completed,
            "admission_passed": completed and all(r["passed"] for r in rows),
            "checks_count": len(rows),
            "failed_checks": sum(not r["passed"] for r in rows),
            "quality_evaluated": False,
            "latency_admission": False,
            "checks": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in result.items() if k != "checks"}), flush=True
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="http://127.0.0.1:" + os.environ.get("GUIDEFOLD_PORT", "8765")
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/checks/http-admission.json"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Record old behavior without treating it as passing admission",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
