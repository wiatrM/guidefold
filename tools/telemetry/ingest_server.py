#!/usr/bin/env python3
"""tools/telemetry/ingest_server.py -- minimal stdlib loopback HTTP handler for
POST /v1/events:batch, backed by tools/telemetry/ledger.py.

This exists only so `guidefold telemetry flush` (skills/guidefold/scripts/guidefold) has a real
HTTP endpoint to flush the local spool to in tests and the end-to-end demo -- it is NOT a product
server. In particular, tenant identity here comes from a plain `X-Guidefold-Tenant` request header,
which is a demo convenience, not authentication: docs/SEARCH-USE-TELEMETRY.md Sec2/Sec4 requires the
verified tenant to come from an authenticated credential, never a client-supplied value, and a real
service must not copy this header trick. Everything else (schema validation, dedup, partial
acknowledgement) is real -- it is exactly ledger.ingest().

Usage:
    python3 tools/telemetry/ingest_server.py --db path/to/ledger.sqlite3 --port 8765
    python3 tools/telemetry/ingest_server.py --db path/to/ledger.sqlite3 --port 0   # ephemeral

Prints "PORT <n>" as its first stdout line once bound (useful for a test/caller that requested an
ephemeral port with --port 0), then serves until killed (SIGINT/SIGTERM or the process is
terminated by its parent).
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.telemetry import ledger

MAX_BODY_BYTES = 2 * 1024 * 1024   # generous demo bound; the CLI's own spool/flush batching
MAX_BATCH_EVENTS = 2000            # (<=500 per brief) is the real product-shaped limit, not this.


class Handler(BaseHTTPRequestHandler):
    server_version = "guidefold-telemetry-ingest-reference/1.0"

    def log_message(self, fmt, *args):
        pass  # keep test/demo output quiet; nothing here is a production access log

    def _send_json(self, status: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path != "/v1/events:batch":
            self._send_json(404, {"error": "not_found"})
            return
        tenant_id = self.headers.get("X-Guidefold-Tenant")
        if not tenant_id:
            self._send_json(400, {"error": "missing_tenant_header"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "body_too_large_or_empty"})
            return
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "invalid_json"})
            return
        events = body.get("events") if isinstance(body, dict) else None
        if not isinstance(events, list):
            self._send_json(400, {"error": "missing_events_list"})
            return
        if len(events) > MAX_BATCH_EVENTS:
            self._send_json(413, {"error": "batch_too_large"})
            return
        result = ledger.ingest(self.server.ledger_conn, tenant_id, events)
        self._send_json(200, result)

    def do_GET(self):
        if self.path == "/v1/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "not_found"})


def serve(db_path, host="127.0.0.1", port=0):
    """Single-threaded on purpose (see ledger.connect docstring): requests are handled one at a
    time, so the shared sqlite3 connection is never touched by two threads at once."""
    conn = ledger.connect(db_path)
    httpd = HTTPServer((host, port), Handler)
    httpd.ledger_conn = conn
    return httpd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="sqlite ledger path (created if missing)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0, help="0 = pick an ephemeral free port")
    args = ap.parse_args()

    httpd = serve(args.db, args.host, args.port)
    bound_port = httpd.server_address[1]
    print(f"PORT {bound_port}", flush=True)

    def _stop(signum, frame):
        httpd.shutdown()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        httpd.serve_forever()
    finally:
        httpd.ledger_conn.close()


if __name__ == "__main__":
    main()
