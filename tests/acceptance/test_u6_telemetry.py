"""U6 — the control ledger: what an event proves, and what a report must refuse to say.

The parity check is run against the reference implementation the Go validator was ported from
(`tools/telemetry/ledger.py` + `tools/telemetry/report.py`), on one event set fed to both.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from gf_acceptance_support import PASS, FAIL, NOT_MEASURED, ApiSession, REPO_ROOT

pytestmark = pytest.mark.acceptance

sys.path.insert(0, str(REPO_ROOT))
from tools.telemetry import ledger, report as ledger_report  # noqa: E402


@pytest.mark.acc("U6-1")
def test_u6_1_the_service_ledger_agrees_with_the_reference_report(fresh_org, report, bring_up,
                                                                  gf_stack, tmp_path):
    """U6-1: the same events through `/v1/events:batch` and through the reference ledger produce
    the same per-(skill, revision) numbers; a replayed batch changes nothing."""
    w = fresh_org("u6-parity")
    bring_up(w)
    skills = w.get("/skills?limit=3")["items"]
    events = _event_set(skills)
    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u6-1", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["search", "use", "events"], "harness": "claude-code"},
                           headers={"Idempotency-Key": "u6-1-inst"})["token"]

    client = ApiSession(gf_stack.api)
    first_status, first, _ = client.request("POST", "/v1/events:batch", token=token,
                                            body={"events": events})
    replay_status, replay, _ = client.request("POST", "/v1/events:batch", token=token,
                                              body={"events": events})

    database = tmp_path / "ledger.sqlite3"
    conn = ledger.connect(str(database))
    ledger.ingest(conn, w.org_id, events)
    ledger.ingest(conn, w.org_id, events)          # the same replay, same guarantee
    reference = ledger_report.compute_report(conn, w.org_id)

    usage = w.get("/usage?window=30d")
    served = {(row["skill_id"], row["revision"]): row for row in usage["skills"]}
    expected = {(row["skill_id"], row["revision"]): row for row in reference["skills"]}

    mismatches = []
    for key, want in expected.items():
        got = served.get(key)
        if got is None:
            mismatches.append({"key": list(key), "problem": "absent from the service report"})
            continue
        if got["exposures"] != want["exposures"]:
            mismatches.append({"key": list(key), "field": "exposures",
                               "service": got["exposures"], "reference": want["exposures"]})
        if got["loads_verified"] != want["loads"]:
            mismatches.append({"key": list(key), "field": "loads",
                               "service": got["loads_verified"], "reference": want["loads"]})
        service_feedback = (got["feedback"] or {}).get("helped", 0)
        if service_feedback != want["feedback"]["helped"]:
            mismatches.append({"key": list(key), "field": "feedback.helped",
                               "service": service_feedback,
                               "reference": want["feedback"]["helped"]})

    accepted_first = len(first["accepted"])
    duplicate_second = len(replay["duplicate"])

    ok = (first_status == 200 and replay_status == 200 and not mismatches
          and not first["rejected"] and duplicate_second == accepted_first)
    report.record("U6-1", prd_ac="U6 AC1 (control ledger; replay changes nothing)",
                  scenario="one event set posted to /v1/events:batch twice and ingested into the "
                           "reference SQLite ledger twice; the two reports are compared per "
                           "(skill_id, revision)",
                  command_or_endpoint="POST /v1/events:batch; GET {repo_base}/usage; "
                                      "tools/telemetry/ledger.py + report.py",
                  data_origin="synthetic events built from this run's own published skills "
                              "[synthetic, n=%d]" % len(events),
                  result=PASS if ok else FAIL,
                  evidence={"events": len(events),
                            "first_batch": {"accepted": accepted_first,
                                            "duplicate": len(first["duplicate"]),
                                            "rejected": first["rejected"]},
                            "replayed_batch_duplicates": duplicate_second,
                            "rows_compared": len(expected),
                            "mismatches": mismatches,
                            "service_totals": usage["totals"]},
                  limitation="Synthetic events written by this test, not adapter traffic. It proves "
                             "the two implementations count the same thing, not that the counts "
                             "describe real use.")
    assert ok, mismatches


@pytest.mark.acc("U6-2")
def test_u6_2_an_http_200_is_not_a_use(fresh_org, report, bring_up, gf_stack):
    """U6-2: a successful USE with nothing reported leaves `use_reported`/`use_observed` at zero
    and the helped ratio null — Unknown, not 0 %."""
    w = fresh_org("u6-unknown")
    bring_up(w)
    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u6-2", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["search", "use", "events"]},
                           headers={"Idempotency-Key": "u6-2-inst"})["token"]
    client = ApiSession(gf_stack.api)
    _, search, _ = client.request("POST", "/v1/search", token=token, body={
        "schema_version": "1.1", "query": "handle an outage in turnstile auth",
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    card = search["cards"][0]
    use_status, used, _ = client.request("POST", "/v1/use", token=token, body={
        "schema_version": "1.1", "search_id": search["search_id"], "skill_id": card["urn"],
        "revision": card["revision"],
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    # One exposure and one verified load that carries no `context_confirmation`. The report
    # derives context_loaded/context_unknown from `skill_load_completed`, so an adapter that
    # cannot observe the model's context must land in `context_unknown`, never in a zero that
    # reads as "did not reach it". Nothing here claims the skill was applied.
    client.request("POST", "/v1/events:batch", token=token, body={"events": [
        _event("card_injected", exposure_id=str(uuid.uuid4()), skill_id=card["urn"],
               revision=card["revision"], position=1, surface="hook",
               delivery_evidence="unknown", search_id=search["search_id"]),
        _event("skill_load_completed", load_id=str(uuid.uuid4()), status="ok",
               cache_source="miss", bytes=len(_used_body(used)), duration_ms=9,
               closure_status="complete", skill_id=card["urn"], revision=card["revision"])]})

    usage = w.get("/usage?window=30d")
    row = next(r for r in usage["skills"] if r["skill_id"] == card["urn"])

    ok = (use_status == 200 and row["use_reported"] == 0 and row["use_observed"] == 0
          and row["helped_ratio"] is None and row["feedback"] is None
          and row["loads_verified"] == 1 and row["context_loaded"] == 0
          and row["context_unknown"] == 1)
    report.record("U6-2", prd_ac="U6 AC2 (HTTP 200 is not use; unknown is not zero)",
                  scenario="one successful USE, one exposure and one verified load with no "
                           "context confirmation; nothing reports an applied episode",
                  command_or_endpoint="POST /v1/use; POST /v1/events:batch; GET {repo_base}/usage",
                  data_origin="this run's published snapshot [synthetic, n=1 exposure]",
                  result=PASS if ok else FAIL,
                  evidence={"use_status": use_status,
                            "row": {k: row.get(k) for k in
                                    ("skill_id", "exposures", "loads_verified", "context_loaded",
                                     "context_unknown", "use_reported", "use_observed",
                                     "feedback", "helped_ratio", "zero_loads")},
                            "totals": usage["totals"]},
                  limitation="One skill, one exposure. It proves the definition, not its behaviour "
                             "under adapter diversity.")
    assert ok, row


@pytest.mark.acc("U6-3")
def test_u6_3_a_ratio_shows_its_own_arithmetic_and_flags_a_small_sample(fresh_org, report,
                                                                        bring_up, gf_stack):
    """U6-3: numerator, denominator, window and revision — and `small_sample` below 20."""
    w = fresh_org("u6-ratio")
    bring_up(w)
    skill = w.get("/skills?limit=1")["items"][0]
    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u6-3", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["events"]},
                           headers={"Idempotency-Key": "u6-3-inst"})["token"]
    client = ApiSession(gf_stack.api)

    small = [_event("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=skill["skill_id"],
                    revision=skill["revision_id"], verdict="helped" if i % 3 else "hindered",
                    reason_category="acceptance", source="ui") for i in range(5)]
    client.request("POST", "/v1/events:batch", token=token, body={"events": small})
    below = _row(w, skill["skill_id"])

    large = [_event("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=skill["skill_id"],
                    revision=skill["revision_id"], verdict="helped" if i % 4 else "hindered",
                    reason_category="acceptance", source="ui") for i in range(20)]
    client.request("POST", "/v1/events:batch", token=token, body={"events": large})
    above = _row(w, skill["skill_id"])
    usage = w.get("/usage?window=30d")

    ok = (below["helped_ratio"]["small_sample"] is True
          and above["helped_ratio"]["small_sample"] is False
          and above["helped_ratio"]["denominator"] == 25
          and above["revision"] == skill["revision_id"]
          and usage["window"]["from"] and usage["window"]["to"])
    report.record("U6-3", prd_ac="U6 AC3 (numerator, denominator, window, revision)",
                  scenario="5 judgments, then 20 more, on one revision; read the ratio each time",
                  command_or_endpoint="POST /v1/events:batch; GET {repo_base}/usage?window=30d",
                  data_origin="synthetic judgments [synthetic, n=25]",
                  result=PASS if ok else FAIL,
                  evidence={"below_floor": below["helped_ratio"], "at_floor": above["helped_ratio"],
                            "small_sample_floor": 20,
                            "revision_on_the_row": above["revision"],
                            "window": usage["window"]},
                  limitation="Synthetic verdicts. Also note the two revision namespaces recorded "
                             "in the ACT-01 row: telemetry from the delivery path carries "
                             "gf.skills.skill_revision, while UI feedback carries the catalog's "
                             "revision_id, so a skill judged in the UI and delivered to a harness "
                             "occupies two rows in this report.")
    assert ok, (below["helped_ratio"], above["helped_ratio"])


@pytest.mark.acc("U6-4")
def test_u6_4_filters_and_exports_carry_no_prompts_or_paths(fresh_org, report, bring_up,
                                                            gf_stack):
    """U6-4: every documented filter is echoed and applied; CSV and JSON export the counts and
    nothing a prompt or a local path could hide in."""
    w = fresh_org("u6-export")
    bring_up(w)
    skill = w.get("/skills?limit=1")["items"][0]
    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u6-4", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["events"], "harness": "claude-code"},
                           headers={"Idempotency-Key": "u6-4-inst"})["token"]
    client = ApiSession(gf_stack.api)
    client.request("POST", "/v1/events:batch", token=token, body={"events": [
        _event("card_injected", exposure_id=str(uuid.uuid4()), skill_id=skill["skill_id"],
               revision=skill["revision_id"], position=1, surface="hook",
               delivery_evidence="client_confirmed", search_id=str(uuid.uuid4())),
        _event("skill_feedback", judgment_id=str(uuid.uuid4()), skill_id=skill["skill_id"],
               revision=skill["revision_id"], verdict="helped",
               reason_category="acceptance", source="ui")]})

    # The query parameter for a skill is `skill_id`, and the echo object is `usage.Filter`,
    # which carries no JSON tags -- so its keys are the Go field names (`Scope`, `SkillID`,
    # `Revision`, `Harness`), not the query-parameter names. Read them as the server sends
    # them rather than as they are typed in the URL.
    echo_key = {"scope": "Scope", "skill_id": "SkillID", "revision": "Revision",
                "harness": "Harness"}
    echoes = {}
    for name, value in (("scope", skill["scope"]), ("skill_id", skill["skill_id"]),
                        ("revision", skill["revision_id"]), ("harness", "claude-code")):
        body = w.get(f"/usage?{name}={_quote(str(value))}")
        filters = body.get("filters") or {}
        echoed = filters.get(echo_key[name], filters.get(name))
        echoes[name] = {"requested": str(value), "echoed": echoed,
                        "applied": echoed == str(value), "rows": len(body["skills"])}
    nonsense = w.get("/usage?skill_id=" + _quote("urn:skill:nobody:none:none"))

    csv_status, csv_body, csv_headers = w.owner.request(
        "GET", w.base + "/usage/export?format=csv")
    json_status, json_body, _ = w.owner.request("GET", w.base + "/usage/export?format=json")
    csv_text = csv_body.get("raw", "") if isinstance(csv_body, dict) else str(csv_body)
    suspicious = [word for word in ("prompt", "query_text", "/home/", "cwd", "token")
                  if word in csv_text.lower()]

    ok = (all(e["applied"] for e in echoes.values())
          and not nonsense["skills"]
          and csv_status == 200 and json_status == 200 and not suspicious)
    report.record("U6-4", prd_ac="U6 AC4 (filters and export)",
                  scenario="each documented filter applied and echoed, a filter matching nothing, "
                           "then CSV and JSON export",
                  command_or_endpoint="GET {repo_base}/usage?scope|skill|revision|harness=…; "
                                      "GET {repo_base}/usage/export?format=csv|json",
                  data_origin="synthetic events on this run's published snapshot",
                  result=PASS if ok else FAIL,
                  evidence={"filter_echoes": echoes,
                            "rows_for_an_unknown_skill": len(nonsense["skills"]),
                            "csv_status": csv_status, "json_status": json_status,
                            "csv_header": csv_text.splitlines()[:1],
                            "csv_bytes": len(csv_text),
                            "suspicious_tokens_in_csv": suspicious},
                  limitation="Checks the export's own columns for prompt text and local paths; it "
                             "is not a general PII scan.")
    assert ok, (echoes, suspicious, csv_status, json_status)


@pytest.mark.acc("U6-6")
def test_u6_6_owner_decision_after_four_weeks_is_not_measured_here(report):
    report.record("U6-6", prd_ac="U6 AC6 P (an owner decision after four weeks of observation)",
                  scenario="an owner of a design-partner repository changes something because of "
                           "the usage report, during the four-week observation window",
                  command_or_endpoint="—", data_origin="—",
                  result=NOT_MEASURED, evidence={},
                  limitation="P-level pilot evidence: needs real sessions over four weeks and a "
                             "decision by someone who is not building Guidefold. A test recording "
                             "its own queue decision (ACT-01) is the mechanism working, not the "
                             "evidence this criterion asks for.")


# ---------------------------------------------------------------------------------------


def _quote(value: str) -> str:
    import urllib.parse
    return urllib.parse.quote(value, safe="")


def _row(w, skill_id: str) -> dict:
    for row in w.get("/usage?window=30d")["skills"]:
        if row["skill_id"] == skill_id and row["feedback"]:
            return row
    raise AssertionError(f"no judged row for {skill_id}")


def _used_body(used: dict) -> bytes:
    return (used.get("body") or "").encode("utf-8")


def _event(event_type: str, **fields) -> dict:
    event = {"schema_version": "1.0", "event_id": str(uuid.uuid4()), "event_type": event_type,
             "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "sequence": 1, "producer": "guidefold-acceptance", "adapter_version": "1",
             "environment": "pilot"}
    event.update(fields)
    return event


def _event_set(skills: list) -> list:
    """Exposures, one verified load, one denied load and judgments — the shapes whose counting
    rules the two implementations must agree on."""
    events = []
    for index, skill in enumerate(skills):
        search_id = str(uuid.uuid4())
        events.append(_event("card_injected", exposure_id=str(uuid.uuid4()),
                             skill_id=skill["skill_id"], revision=skill["revision_id"],
                             position=index + 1, surface="hook",
                             delivery_evidence="client_confirmed", search_id=search_id))
        events.append(_event("skill_load_completed", load_id=str(uuid.uuid4()), status="ok",
                             cache_source="miss", bytes=1234, duration_ms=12,
                             closure_status="complete", context_confirmation="context_loaded",
                             skill_id=skill["skill_id"], revision=skill["revision_id"]))
        # A load whose adapter cannot see the model's context: verified, but unknown.
        events.append(_event("skill_load_completed", load_id=str(uuid.uuid4()), status="ok",
                             cache_source="hit", bytes=1234, duration_ms=4,
                             closure_status="complete", skill_id=skill["skill_id"],
                             revision=skill["revision_id"]))
        # A denied load is never a load.
        events.append(_event("skill_load_completed", load_id=str(uuid.uuid4()), status="denied",
                             cache_source="miss", bytes=0, duration_ms=3,
                             closure_status="unresolved", skill_id=skill["skill_id"],
                             revision=skill["revision_id"]))
        events.append(_event("skill_feedback", judgment_id=str(uuid.uuid4()),
                             skill_id=skill["skill_id"], revision=skill["revision_id"],
                             verdict="helped", reason_category="acceptance", source="ui"))
    return events
