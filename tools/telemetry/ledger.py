#!/usr/bin/env python3
"""tools/telemetry/ledger.py -- reference SEARCH/USE/telemetry event ledger (E6.4).

Stdlib-only (sqlite3). This is a REFERENCE implementation of the server-side ingest half of
docs/SEARCH-USE-TELEMETRY.md -- "build the ledger's client side and a reference of its server
side so the service can port it" (brief E6.4/E2.7/E6.5-lite). It is not a product server: no
auth, no multi-process concurrency story, no network transport of its own --
tools/telemetry/ingest_server.py wraps this module's `ingest()` in a minimal stdlib HTTP handler
purely so the CLI's `telemetry flush` (skills/guidefold/scripts/guidefold) has something real to
flush to in tests and the demo run. Report rollups (tools/telemetry/report.py) read this ledger.

Contract (docs/SEARCH-USE-TELEMETRY.md):
  Sec3  event vocabulary and each event type's required fields (REQUIRED_FIELDS below). The CLI
        client today emits only a subset (search_requested, search_results, card_injected,
        skill_load_requested, skill_load_completed, telemetry_health); the rest of the vocabulary
        is recognised here anyway so this reference matches the FULL contract the service must
        eventually implement, and so tests can build the self-report / observed-invocation /
        feedback / task scenarios Sec8 asks for without waiting on a client that emits them yet.
  Sec4  every event carries schema_version, event_id, event_type, occurred_at, sequence, producer,
        adapter_version, environment, and session_id/task_id/correlation_id "where available".
        "Store an append-only event ledger with unique (tenant_id, event_id). Distinguish
        transport duplication from a legitimate second use." Out-of-order events join by IDs
        later; missing links remain unknown -- this ledger stores whatever IDs an event carries
        (search_id, load_id, exposure_id, parent_load_id, ...) inside its JSON payload and never
        requires them to arrive in any particular order; a join is just a query by that ID once
        both sides exist.
  Sec5  retention: "Retain event-level product telemetry for 90 days ... Enforce expiry and
        deletion in both events and derived tables." There are no derived rollup tables here --
        report.py computes rollups on read -- so retention_delete() only needs one table.

ingest(conn, tenant_id, batch) never raises on a malformed event: each event is judged
independently ("the rest of the batch still accepted", Sec3/Sec8 "partial acknowledgement"), and
the per-event outcome is what a transport layer (ingest_server.py) turns into the
accepted/duplicate/rejected response HARNESS-SERVICE-CONTRACT.md/SEARCH-USE-TELEMETRY.md Sec2
describes. `tenant_id` is a parameter, never read from the event body: accepting a client-claimed
tenant would let one tenant write into another's ledger (Sec2 "client-supplied tenant/scope never
grants access"; Sec4 "Events retain their original tenant/principal binding"). The caller (the
ingest server, having checked its own auth, or a direct test standing in for that) is responsible
for having verified tenant_id already -- this module trusts its caller on that one point only.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path

SCHEMA_VERSIONS = ("1.0",)
ENVIRONMENTS = ("dev", "eval", "pilot")
VERDICTS = ("helped", "hindered", "mixed", "not_applicable", "unknown")

# Full Sec3 vocabulary. See module docstring: the CLI emits a subset today.
EVENT_TYPES = (
    "search_requested", "search_results", "card_injected",
    "skill_load_requested", "skill_load_completed",
    "skill_use_reported", "skill_use_observed", "skill_feedback",
    "task_started", "task_finished",
    "telemetry_health",
)

# Envelope fields every event must carry (Sec4). All required non-null; session_id/task_id/
# correlation_id are deliberately absent from this list -- "where available" means optional, not
# required-but-nullable.
ENVELOPE_REQUIRED = ("schema_version", "event_id", "event_type", "occurred_at", "sequence",
                     "producer", "adapter_version", "environment")

# Per event type: "required" fields that must be present with a non-null/non-empty value, and
# "nullable" fields that must be present (the key always exists) but may legitimately be null --
# e.g. search_results.fallback_reason is required-to-be-present because "no fallback happened" is
# itself information (distinct from an adapter that never even considered the question), but its
# value is null in the (overwhelmingly common) case where nothing was falling back at all. Field
# names match the contract's own vocabulary exactly (e.g. "skill_id" is the contract's name for a
# skill's URN -- this ledger does not rename it to "urn" even though the rest of the guidefold
# codebase says "urn").
REQUIRED_FIELDS = {
    "search_requested": {
        "required": ("search_id", "profile", "scope", "deadline_ms"),
        "nullable": (),
    },
    "search_results": {
        "required": ("search_id", "status", "results", "timings"),
        "nullable": ("fallback_reason",),
    },
    "card_injected": {
        "required": ("exposure_id", "skill_id", "revision", "position", "surface",
                     "delivery_evidence"),
        "nullable": ("search_id",),
    },
    "skill_load_requested": {
        "required": ("load_id", "skill_id", "revision", "source"),
        "nullable": ("use_id", "search_id"),
    },
    "skill_load_completed": {
        "required": ("load_id", "status", "cache_source", "bytes", "duration_ms",
                      "closure_status"),
        "nullable": ("skill_id", "revision"),
    },
    "skill_use_reported": {
        "required": ("skill_id", "revision", "source", "report_category"),
        "nullable": ("load_id", "use_id"),
    },
    "skill_use_observed": {
        "required": ("skill_id", "revision", "adapter_evidence_type", "evidence_ref"),
        "nullable": ("load_id", "use_id"),
    },
    "skill_feedback": {
        "required": ("judgment_id", "skill_id", "revision", "verdict", "reason_category",
                      "source"),
        "nullable": (),
    },
    "task_started": {
        "required": ("task_id", "pilot_cohort", "eligible", "observation_capability"),
        "nullable": (),
    },
    "task_finished": {
        "required": ("task_id", "terminal_status", "outcome", "outcome_source",
                     "observation_coverage"),
        "nullable": (),
    },
    "telemetry_health": {
        "required": ("produced", "acknowledged", "dropped", "oldest_queued_age_s",
                     "capability_flags", "window"),
        "nullable": (),
    },
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    tenant_id       TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    occurred_at     TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    sequence        INTEGER,
    producer        TEXT,
    adapter_version TEXT,
    environment     TEXT NOT NULL,
    session_id      TEXT,
    task_id         TEXT,
    correlation_id  TEXT,
    payload         TEXT NOT NULL,
    PRIMARY KEY (tenant_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_type ON events(tenant_id, event_type);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);
"""


class RejectionError(ValueError):
    """Internal: carries one rejection reason string. Never escapes ingest()."""


def connect(db_path) -> sqlite3.Connection:
    """Open (creating if needed) the sqlite ledger at db_path, with the schema applied.

    check_same_thread=False: the CLI and tests use a connection from a single thread as sqlite3
    defaults expect, but ingest_server.py's HTTP handler runs on whatever thread accepts the
    request, which is not necessarily the thread that called connect(). This module does not
    itself serialize concurrent writers -- ingest_server.py is a single-threaded HTTPServer (not
    ThreadingHTTPServer) specifically so at most one request touches this connection at a time;
    it is a reference/demo component, not a product server, and callers needing real concurrency
    must add their own locking.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def _parse_ts(value) -> datetime.datetime:
    if not isinstance(value, str):
        raise ValueError("occurred_at must be a string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    return dt


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require(event: dict, spec: dict) -> None:
    for f in spec["required"]:
        if f not in event or event[f] in (None, ""):
            raise RejectionError(f"missing_required_field:{f}")
    for f in spec["nullable"]:
        if f not in event:
            raise RejectionError(f"missing_required_field:{f}")


def _validate(event) -> None:
    if not isinstance(event, dict):
        raise RejectionError("event_not_an_object")
    if not isinstance(event.get("event_id"), str) or not event["event_id"]:
        raise RejectionError("missing_required_field:event_id")
    _require(event, {"required": ENVELOPE_REQUIRED, "nullable": ()})
    if event["schema_version"] not in SCHEMA_VERSIONS:
        raise RejectionError("unsupported_schema_version")
    event_type = event["event_type"]
    if event_type not in EVENT_TYPES:
        raise RejectionError("unknown_event_type")
    if event["environment"] not in ENVIRONMENTS:
        raise RejectionError("invalid_environment")
    try:
        _parse_ts(event["occurred_at"])
    except Exception:
        raise RejectionError("invalid_occurred_at") from None
    _require(event, REQUIRED_FIELDS[event_type])
    if event_type == "skill_feedback" and event.get("verdict") not in VERDICTS:
        raise RejectionError("invalid_verdict")


def ingest(conn: sqlite3.Connection, tenant_id: str, batch: list) -> dict:
    """Validate and store `batch` (a list of event dicts) under `tenant_id`.

    Returns {"accepted": [event_id, ...], "duplicate": [event_id, ...],
             "rejected": [{"event_id": event_id_or_None, "reason": str, "retryable": bool}, ...]}.

    Every event is judged independently; one malformed event never blocks the rest of the batch.
    Replaying an event_id already stored for this tenant is a `duplicate`, not an error, and
    changes no count (idempotent replay). All of this reference ledger's rejection reasons are
    permanent schema violations (bad version, unknown type, missing field) -- `retryable` is
    always False here; a real service could add transient reasons (e.g. rate limiting) that are
    retryable without changing this shape.
    """
    if not tenant_id:
        raise ValueError("ingest() requires a verified tenant_id")
    received_at = _iso(_utc_now())
    accepted, duplicate, rejected = [], [], []
    for event in batch:
        event_id = event.get("event_id") if isinstance(event, dict) else None
        try:
            _validate(event)
        except RejectionError as exc:
            rejected.append({"event_id": event_id, "reason": str(exc), "retryable": False})
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO events (tenant_id, event_id, event_type, schema_version, "
            "occurred_at, received_at, sequence, producer, adapter_version, environment, "
            "session_id, task_id, correlation_id, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id, event["event_id"], event["event_type"], event["schema_version"],
             event["occurred_at"], received_at, event.get("sequence"), event.get("producer"),
             event.get("adapter_version"), event["environment"], event.get("session_id"),
             event.get("task_id"), event.get("correlation_id"),
             json.dumps(event, sort_keys=True)),
        )
        (accepted if cur.rowcount == 1 else duplicate).append(event["event_id"])
    conn.commit()
    return {"accepted": accepted, "duplicate": duplicate, "rejected": rejected}


def retention_delete(conn: sqlite3.Connection, older_than_days: int = 90, now=None) -> int:
    """Delete events whose occurred_at is older than `older_than_days` (Sec5). Returns the number
    of rows deleted. No derived rollup tables exist in this reference ledger to also expire --
    report.py always computes rollups fresh from `events`."""
    now = now or _utc_now()
    cutoff = _iso(now - datetime.timedelta(days=older_than_days))
    cur = conn.execute("DELETE FROM events WHERE occurred_at < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def fetch(conn: sqlite3.Connection, tenant_id: str, event_type: str = None) -> list:
    """All events for one tenant (optionally filtered by type), oldest occurred_at first, decoded
    from their stored payload JSON. Callers must never pass a tenant_id whose data the ultimate
    caller is not entitled to see -- this module has no authorization model of its own."""
    if event_type:
        rows = conn.execute(
            "SELECT payload FROM events WHERE tenant_id=? AND event_type=? ORDER BY occurred_at",
            (tenant_id, event_type)).fetchall()
    else:
        rows = conn.execute(
            "SELECT payload FROM events WHERE tenant_id=? ORDER BY occurred_at",
            (tenant_id,)).fetchall()
    return [json.loads(r[0]) for r in rows]


def tenants(conn: sqlite3.Connection) -> list:
    """Distinct tenant_ids present in the ledger -- report.py iterates this to produce one report
    per tenant rather than silently pooling every tenant's events together."""
    return [r[0] for r in
            conn.execute("SELECT DISTINCT tenant_id FROM events ORDER BY tenant_id").fetchall()]
