"""tests/test_telemetry_ledger.py -- the exact 8 E6.4 replay scenarios from
docs/SEARCH-USE-TELEMETRY.md Sec8: "replay tests cover deduplication, partial acknowledgement,
out-of-order joins, explicit USE, cached reuse, dependencies, retention/deletion and tenant
isolation."

These build event dicts by hand (never by driving the CLI) so the ledger's own contract is tested
independent of whatever subset the CLI client currently emits (tools/telemetry/ledger.py's module
docstring: the CLI emits only a subset of the full Sec3 vocabulary today, but the ledger recognises
all of it).
"""
import datetime
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.telemetry import ledger

TENANT = "acme-corp"


@pytest.fixture(params=("sqlite", "postgres") if os.environ.get("GUIDEFOLD_TEST_POSTGRES_LEDGER") == "1" else ("sqlite",))
def gf_conn(tmp_path, request):
    if request.param == "postgres":
        from tools.search_service.telemetry_backend import contract_connection
        conn = contract_connection()
    else:
        conn = ledger.connect(tmp_path / "ledger.sqlite3")
    yield conn
    conn.close()


def _envelope(event_type, **extra):
    event = {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": _iso_now(),
        "sequence": 1,
        "producer": "test-producer",
        "adapter_version": "test-1.0",
        "environment": "dev",
    }
    event.update(extra)
    return event


def _iso_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_days_ago(days):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _card_injected(**extra):
    base = dict(exposure_id=str(uuid.uuid4()), skill_id="urn:skill:acme:widget", revision="rev1",
                position=1, surface="interactive", delivery_evidence="printed_stdout",
                search_id=str(uuid.uuid4()))
    base.update(extra)
    return _envelope("card_injected", **base)


def _load_requested(load_id, **extra):
    base = dict(load_id=load_id, skill_id="urn:skill:acme:widget", revision="rev1",
                source="explicit", use_id=None, search_id=None)
    base.update(extra)
    return _envelope("skill_load_requested", **base)


def _load_completed(load_id, **extra):
    base = dict(load_id=load_id, status="ok", cache_source="download", bytes=1024,
                duration_ms=42, closure_status="complete", skill_id="urn:skill:acme:widget",
                revision="rev1")
    base.update(extra)
    return _envelope("skill_load_completed", **base)


def test_deduplication_replaying_an_event_id_is_duplicate_not_a_second_accept(gf_conn):
    event = _card_injected()
    r1 = ledger.ingest(gf_conn, TENANT, [event])
    assert r1["accepted"] == [event["event_id"]]
    assert r1["duplicate"] == []

    r2 = ledger.ingest(gf_conn, TENANT, [event])
    assert r2["accepted"] == []
    assert r2["duplicate"] == [event["event_id"]]
    assert r2["rejected"] == []

    stored = ledger.fetch(gf_conn, TENANT, event_type="card_injected")
    assert len(stored) == 1  # replay never doubles the stored row


def test_partial_acknowledgement_one_bad_event_never_blocks_the_rest_of_the_batch(gf_conn):
    good = _card_injected()
    bad = _envelope("card_injected")  # missing skill_id/revision/position/surface/delivery_evidence
    del bad["environment"]  # also missing an envelope-required field, for good measure

    result = ledger.ingest(gf_conn, TENANT, [good, bad])
    assert result["accepted"] == [good["event_id"]]
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["event_id"] == bad["event_id"]
    assert result["rejected"][0]["reason"].startswith("missing_required_field:")
    assert result["rejected"][0]["retryable"] is False

    stored_ids = {e["event_id"] for e in ledger.fetch(gf_conn, TENANT)}
    assert good["event_id"] in stored_ids
    assert bad["event_id"] not in stored_ids


def test_out_of_order_joins_completed_arriving_before_requested_still_joins_by_load_id(gf_conn):
    load_id = str(uuid.uuid4())
    completed = _load_completed(load_id)
    requested = _load_requested(load_id)

    # Completed arrives in the batch BEFORE its own request -- transport does not guarantee order.
    result = ledger.ingest(gf_conn, TENANT, [completed, requested])
    assert set(result["accepted"]) == {completed["event_id"], requested["event_id"]}

    events = ledger.fetch(gf_conn, TENANT)
    by_type = {e["event_type"]: e for e in events}
    assert by_type["skill_load_requested"]["load_id"] == load_id
    assert by_type["skill_load_completed"]["load_id"] == load_id  # joins on load_id, not arrival order


def test_explicit_use_self_report_and_observed_invocation_stay_separate_events(gf_conn):
    reported = _envelope("skill_use_reported", skill_id="urn:skill:acme:widget", revision="rev1",
                          source="self_report", report_category="applied",
                          load_id=None, use_id=None)
    observed = _envelope("skill_use_observed", skill_id="urn:skill:acme:widget", revision="rev1",
                          adapter_evidence_type="tool_call", evidence_ref="call-123",
                          load_id=None, use_id=None)

    result = ledger.ingest(gf_conn, TENANT, [reported, observed])
    assert set(result["accepted"]) == {reported["event_id"], observed["event_id"]}

    events = ledger.fetch(gf_conn, TENANT)
    types_seen = [e["event_type"] for e in events]
    assert "skill_use_reported" in types_seen
    assert "skill_use_observed" in types_seen
    # never conflated into one row/event -- two distinct event_ids, two distinct event_types
    assert len(events) == 2
    assert events[0]["event_id"] != events[1]["event_id"]


def test_cached_reuse_load_completed_from_cache_is_still_a_real_stored_load(gf_conn):
    load_id = str(uuid.uuid4())
    completed = _load_completed(load_id, cache_source="cache", duration_ms=3)

    result = ledger.ingest(gf_conn, TENANT, [completed])
    assert result["accepted"] == [completed["event_id"]]

    stored = ledger.fetch(gf_conn, TENANT, event_type="skill_load_completed")[0]
    assert stored["cache_source"] == "cache"
    assert stored["status"] == "ok"


def test_dependencies_a_dependency_load_links_to_its_parent_via_parent_load_id(gf_conn):
    parent_load_id = str(uuid.uuid4())
    dep_load_id = str(uuid.uuid4())
    parent = _load_completed(parent_load_id, skill_id="urn:skill:acme:widget")
    dependency = _load_completed(dep_load_id, skill_id="urn:skill:acme:widget-dep",
                                  parent_load_id=parent_load_id)

    result = ledger.ingest(gf_conn, TENANT, [parent, dependency])
    assert set(result["accepted"]) == {parent["event_id"], dependency["event_id"]}

    events = {e["load_id"]: e for e in ledger.fetch(gf_conn, TENANT, "skill_load_completed")}
    assert events[dep_load_id]["parent_load_id"] == parent_load_id
    assert "parent_load_id" not in events[parent_load_id]


def test_retention_deletion_only_events_older_than_the_cutoff_are_removed(gf_conn):
    old_event = _card_injected()
    old_event["occurred_at"] = _iso_days_ago(120)
    recent_event = _card_injected()
    recent_event["occurred_at"] = _iso_days_ago(1)

    ledger.ingest(gf_conn, TENANT, [old_event, recent_event])
    deleted = ledger.retention_delete(gf_conn, older_than_days=90)
    assert deleted == 1

    remaining_ids = {e["event_id"] for e in ledger.fetch(gf_conn, TENANT)}
    assert old_event["event_id"] not in remaining_ids
    assert recent_event["event_id"] in remaining_ids


def test_tenant_isolation_same_event_id_under_two_tenants_never_leaks_across_tenants(gf_conn):
    shared_event_id = str(uuid.uuid4())
    event_a = _card_injected()
    event_a["event_id"] = shared_event_id
    event_b = _card_injected(skill_id="urn:skill:acme:other")
    event_b["event_id"] = shared_event_id

    result_a = ledger.ingest(gf_conn, "tenant-a", [event_a])
    result_b = ledger.ingest(gf_conn, "tenant-b", [event_b])
    # (tenant_id, event_id) is the uniqueness key -- the same event_id under a different tenant
    # is a fresh accept, never a cross-tenant duplicate.
    assert result_a["accepted"] == [shared_event_id]
    assert result_b["accepted"] == [shared_event_id]

    fetched_a = ledger.fetch(gf_conn, "tenant-a")
    fetched_b = ledger.fetch(gf_conn, "tenant-b")
    assert len(fetched_a) == 1 and fetched_a[0]["skill_id"] == "urn:skill:acme:widget"
    assert len(fetched_b) == 1 and fetched_b[0]["skill_id"] == "urn:skill:acme:other"
    assert set(ledger.tenants(gf_conn)) == {"tenant-a", "tenant-b"}


def test_ingest_requires_a_verified_tenant_id_it_never_trusts_the_event_body(gf_conn):
    event = _card_injected()
    try:
        ledger.ingest(gf_conn, "", [event])
        assert False, "expected ValueError for empty tenant_id"
    except ValueError:
        pass


def test_same_batch_duplicate_keeps_first_payload_and_order(gf_conn):
    first = _card_injected()
    second = _card_injected()
    changed = dict(first, position=99)
    invalid = dict(first, schema_version="future")
    result = ledger.ingest(gf_conn, TENANT, [first, second, changed, invalid, second])
    assert result["accepted"] == [first["event_id"], second["event_id"]]
    assert result["duplicate"] == [first["event_id"], second["event_id"]]
    assert result["rejected"] == [
        {
            "event_id": first["event_id"],
            "reason": "unsupported_schema_version",
            "retryable": False,
        }
    ]
    stored = {row["event_id"]: row for row in ledger.fetch(gf_conn, TENANT)}
    assert stored[first["event_id"]] == first
    assert stored[second["event_id"]] == second
