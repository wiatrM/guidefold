#!/usr/bin/env python3
"""Run a local, non-root PostgreSQL for Guidefold development and tests.

Uses plain PostgreSQL binaries (no ParadeDB) from ``$GUIDEFOLD_PG_BIN`` or
``~/.cache/guidefold/toolchain/pg18/bin``. Data directories live under
``~/.cache/guidefold/pg/<name>``; nothing is written to the repository or /tmp.

    python3 tools/dev/pg.py start   [--name dev] [--port 54329]
    python3 tools/dev/pg.py stop    [--name dev]
    python3 tools/dev/pg.py status  [--name dev]
    python3 tools/dev/pg.py reset   [--name dev] [--port 54329]   # destroys that data dir
    python3 tools/dev/pg.py env     [--name dev] [--port 54329]   # prints PG* exports

The server listens on 127.0.0.1 with trust authentication for the local user only;
it is a development instance, never a deployment.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
DEFAULT_BIN = HOME / ".cache/guidefold/toolchain/pg18/bin"
BASE = HOME / ".cache/guidefold/pg"


def pg_bin() -> Path:
    path = Path(os.environ.get("GUIDEFOLD_PG_BIN", str(DEFAULT_BIN)))
    if not (path / "postgres").exists():
        sys.exit(f"postgres binaries not found in {path}; set GUIDEFOLD_PG_BIN")
    return path


def data_dir(name: str) -> Path:
    return BASE / name


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def initdb(name: str) -> None:
    d = data_dir(name)
    if (d / "PG_VERSION").exists():
        return
    d.parent.mkdir(parents=True, exist_ok=True)
    run([str(pg_bin() / "initdb"), "-D", str(d), "-U", "postgres", "--auth=trust",
         "-E", "UTF8", "--locale=C.UTF-8"])


def is_running(name: str) -> bool:
    d = data_dir(name)
    if not (d / "postmaster.pid").exists():
        return False
    r = subprocess.run([str(pg_bin() / "pg_ctl"), "-D", str(d), "status"], capture_output=True, text=True)
    return r.returncode == 0


def start(name: str, port: int) -> None:
    initdb(name)
    d = data_dir(name)
    if is_running(name):
        print(f"already running: {d} port {port}")
        return
    log = d.parent / f"{name}.log"
    opts = f"-p {port} -k {d.parent} -c listen_addresses=127.0.0.1 -c max_connections=200 -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    run([str(pg_bin() / "pg_ctl"), "-D", str(d), "-o", opts, "-l", str(log), "-w", "-t", "60", "start"])
    for _ in range(60):
        if is_running(name):
            break
        time.sleep(0.5)
    ensure_database(name, port, "guidefold")
    print(f"started: {d} port {port} log {log}")


def ensure_database(name: str, port: int, db: str) -> None:
    """Create ``db`` when missing, using the ``postgres`` maintenance DB (no psql available)."""
    createdb = pg_bin() / "createdb"
    if createdb.exists():
        subprocess.run([str(createdb), "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", db],
                       capture_output=True, text=True)
        return
    # Fallback: single-user mode is not usable while running; use the postgres binary's
    # --single only when stopped. Prefer the Go test helper for database creation.
    try:
        import socket  # noqa: F401
        _pg_simple_query(port, "postgres", f'CREATE DATABASE "{db}"')
    except Exception as e:  # pragma: no cover - informational
        if "already exists" not in str(e):
            print(f"warning: could not create database {db}: {e}", file=sys.stderr)


def _pg_simple_query(port: int, dbname: str, sql: str) -> None:
    """Minimal PostgreSQL v3 protocol client (trust auth) for a single simple query."""
    import socket
    import struct

    def msg(kind: bytes, payload: bytes) -> bytes:
        return kind + struct.pack("!I", len(payload) + 4) + payload

    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    params = b"user\x00postgres\x00database\x00" + dbname.encode() + b"\x00\x00"
    s.sendall(struct.pack("!I", len(params) + 8) + struct.pack("!I", 196608) + params)
    buf = b""
    ready = False
    error = None
    sent = False
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
        while len(buf) >= 5:
            kind, ln = buf[0:1], struct.unpack("!I", buf[1:5])[0]
            if len(buf) < ln + 1:
                break
            body, buf = buf[5:ln + 1], buf[ln + 1:]
            if kind == b"E":
                fields = body.split(b"\x00")
                error = " ".join(f[1:].decode(errors="replace") for f in fields if f[:1] == b"M")
            elif kind == b"Z":
                if not sent:
                    s.sendall(msg(b"Q", sql.encode() + b"\x00"))
                    sent = True
                else:
                    ready = True
            if ready:
                break
        if ready:
            break
    s.sendall(msg(b"X", b""))
    s.close()
    if error:
        raise RuntimeError(error)


def stop(name: str) -> None:
    d = data_dir(name)
    if not is_running(name):
        print(f"not running: {d}")
        return
    run([str(pg_bin() / "pg_ctl"), "-D", str(d), "-m", "fast", "-w", "stop"])
    print(f"stopped: {d}")


def status(name: str) -> int:
    d = data_dir(name)
    running = is_running(name)
    print(f"{'running' if running else 'stopped'}: {d}")
    return 0 if running else 3


def reset(name: str, port: int) -> None:
    if is_running(name):
        stop(name)
    d = data_dir(name)
    if d.exists():
        shutil.rmtree(d)
    start(name, port)


def env(name: str, port: int) -> None:
    print(f"export PGHOST=127.0.0.1 PGPORT={port} PGUSER=postgres PGDATABASE=guidefold PGSSLMODE=disable")
    print(f"export GUIDEFOLD_PG_BIN={pg_bin()}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("start", "stop", "status", "reset", "env"))
    p.add_argument("--name", default="dev")
    p.add_argument("--port", type=int, default=54329)
    a = p.parse_args()
    if a.command == "start":
        start(a.name, a.port)
    elif a.command == "stop":
        stop(a.name)
    elif a.command == "status":
        return status(a.name)
    elif a.command == "reset":
        reset(a.name, a.port)
    elif a.command == "env":
        env(a.name, a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
