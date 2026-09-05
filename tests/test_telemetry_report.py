"""tests/test_telemetry_report.py -- tools/telemetry/report.py, per docs/SEARCH-USE-TELEMETRY.md
Sec6/Sec8 (E6.5): "a per-skill view computes adoption/usability with coverage from known events;
rollups reconcile with raw counts and duplicate replay leaves counts unchanged. Denied loads,
absent feedback and unknown outcomes never become successful use."
"""
import datetime
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.telemetry import ledger, report

TENANT = "acme-corp"
SKILL = "urn:skill:acme:widget"
REV = "rev1"


@pytest.fixture
def gf_conn(tmp_path):
    conn = ledger.connect(tmp_path / "ledger.sqlite3")
    yield conn
    conn.close()


def _iso_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(event_type, **extra):
    event = {
        "schema_version": "1.0", "event_id": str(uuid.uuid4()), "event_type": event_type,
        "occurred_at": _iso_now(), "sequence": 1, "producer": "guidefold-cli",
        "adapter_version": "test-1.0", "environment": "dev",
    }
    event.update(extra)
    return event


def _card_injected(skill_id=SKILL, revision=REV, scope="atlas.identity", **extra):
    base = dict(exposure_id=str(uuid.uuid4()), skill_id=skill_id, revision=revision, position=1,
                surface="interactive", delivery_evidence="printed_stdout",
                search_id=str(uuid.uuid4()), scope=scope)
    base.update(extra)
    return _envelope("card_injected", **base)


def _load_completed(status="ok", skill_id=SKILL, revision=REV, **extra):
    # No `scope` here: the real CLI never puts one on skill_load_completed (a bare `load <urn>`
    # has no node/scope concept of its own) -- see cmd_load.
    base = dict(load_id=str(uuid.uuid4()), status=status, cache_source="download", bytes=100,
                duration_ms=5, closure_status="complete", skill_id=skill_id, revision=revision)
    base.update(extra)
    return _envelope("skill_load_completed", **base)


def test_never_exposed_exposed_never_loaded_and_loaded_are_the_three_states(gf_conn):
    never = "urn:skill:acme:never-touched"
    exposed_only = "urn:skill:acme:exposed-only"
    loaded_one = SKILL

    ledger.ingest(gf_conn, TENANT, [
        _card_injected(skill_id=exposed_only),
        _card_injected(skill_id=loaded_one),
        _load_completed(skill_id=loaded_one),
    ])
    rep = report.compute_report(gf_conn, TENANT, roster=[never, exposed_only, loaded_one])
    by_id = {s["skill_id"]: s for s in rep["skills"]}

    assert by_id[never]["state"] == "never_exposed"
    assert by_id[never]["revision"] is None
    assert by_id[never]["exposures"] == 0 and by_id[never]["loads"] == 0
    assert by_id[never]["use_rate"] == "unknown"

    assert by_id[exposed_only]["state"] == "exposed_never_loaded"
    assert by_id[exposed_only]["exposures"] == 1 and by_id[exposed_only]["loads"] == 0
    assert by_id[exposed_only]["use_rate"] == 0.0

    assert by_id[loaded_one]["state"] == "loaded"
    assert by_id[loaded_one]["exposures"] == 1 and by_id[loaded_one]["loads"] == 1
    assert by_id[loaded_one]["use_rate"] == 1.0


def test_denied_and_error_loads_never_count_as_use(gf_conn):
    ledger.ingest(gf_conn, TENANT, [
        _card_injected(),
        _load_completed(status="denied"),
        _load_completed(status="error"),
    ])
    rep = report.compute_report(gf_conn, TENANT)
    row = rep["skills"][0]
    assert row["exposures"] == 1
    assert row["loads"] == 0   # neither denied nor error status is a use
    assert row["state"] == "exposed_never_loaded"


def test_duplicate_replay_leaves_every_number_in_the_report_unchanged(gf_conn):
    batch = [
        _card_injected(),
        _card_injected(),
        _load_completed(),
        _envelope("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=SKILL, revision=REV,
                   verdict="helped", reason_category="accurate", source="self_report"),
    ]
    ledger.ingest(gf_conn, TENANT, batch)
    rep1 = report.compute_report(gf_conn, TENANT)

    # Replay the exact same batch (transport-level retry) -- ledger.ingest dedups by
    # (tenant_id, event_id), so the report must be byte-for-byte identical except generated_at.
    ledger.ingest(gf_conn, TENANT, batch)
    rep2 = report.compute_report(gf_conn, TENANT)

    assert rep1["skills"] == rep2["skills"]
    assert rep1["summary"] == rep2["summary"]


def test_distinct_scopes_and_producers_are_tracked_across_events(gf_conn):
    # scope is an extra (non-required) field the CLI puts on card_injected only (it is the one
    # place scope/node is already known at emit time -- see cmd_find/cmd_hook); skill_load_* events
    # don't carry it since a bare `load <urn>` has no node/scope concept of its own.
    ledger.ingest(gf_conn, TENANT, [
        _card_injected(scope="atlas.identity", producer="guidefold-cli"),
        _card_injected(scope="atlas.geo", producer="guidefold-cli"),
        _load_completed(producer="other-adapter"),
    ])
    rep = report.compute_report(gf_conn, TENANT)
    row = rep["skills"][0]
    assert row["distinct_scopes"] == ["atlas.geo", "atlas.identity"]
    assert row["distinct_producers"] == ["guidefold-cli", "other-adapter"]


def test_feedback_counts_by_verdict_default_to_zero(gf_conn):
    ledger.ingest(gf_conn, TENANT, [
        _card_injected(),
        _envelope("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=SKILL, revision=REV,
                   verdict="helped", reason_category="accurate", source="self_report"),
        _envelope("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=SKILL, revision=REV,
                   verdict="helped", reason_category="accurate", source="self_report"),
        _envelope("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=SKILL, revision=REV,
                   verdict="hindered", reason_category="wrong", source="self_report"),
    ])
    rep = report.compute_report(gf_conn, TENANT)
    row = rep["skills"][0]
    assert row["feedback"]["helped"] == 2
    assert row["feedback"]["hindered"] == 1
    assert row["feedback"]["mixed"] == 0
    assert row["feedback"]["not_applicable"] == 0


def test_no_per_person_leaderboard_session_or_task_id_never_appear_in_output(gf_conn):
    ledger.ingest(gf_conn, TENANT, [
        _card_injected(session_id="sess-1", task_id="task-1"),
        _load_completed(session_id="sess-2", task_id="task-2"),
    ])
    rep = report.compute_report(gf_conn, TENANT)
    dumped = str(rep)
    assert "sess-1" not in dumped and "sess-2" not in dumped
    assert "task-1" not in dumped and "task-2" not in dumped


def test_render_markdown_produces_a_table_with_a_summary_line(gf_conn):
    ledger.ingest(gf_conn, TENANT, [_card_injected(), _load_completed()])
    rep = report.compute_report(gf_conn, TENANT)
    md = report.render_markdown(rep)
    assert "| skill_id |" in md
    assert SKILL in md
    assert "Summary:" in md
    assert "loaded=1" in md
