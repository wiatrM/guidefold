#!/usr/bin/env python3
"""tools/telemetry/report.py -- per-skill, per-revision usage report from the reference ledger
(tools/telemetry/ledger.py), for E6.5-lite ("As Owner, see usage and usability per skill
revision").

Computed straight from the ledger's raw event rows -- there are no derived rollup tables to keep
in sync, so replaying an already-ingested batch (ledger.ingest() dedups by (tenant_id, event_id))
leaves every number in this report unchanged (tested in tests/test_telemetry_report.py).

Per (skill_id, revision) this reports:
  - exposures        : count of card_injected events (a card was put in front of an agent/user --
                        not proof of attention, docs/SEARCH-USE-TELEMETRY.md Sec1/Sec3).
  - loads             : count of skill_load_completed events with status == "ok" only. A denied,
                        errored or otherwise non-"ok" completed load is never counted as a load
                        (docs/SEARCH-USE-TELEMETRY.md Sec6: "Denied loads ... never become
                        successful use").
  - use_rate          : loads / exposures, shown alongside both raw counts -- "unknown" (not 0 and
                        not 1.0) when exposures is 0, since a rate with a zero denominator is not
                        evidence of anything.
  - distinct_scopes   : the set of `scope` values seen across this skill's exposure/load events --
                        cross-team reuse. distinct_producers likewise (adapter diversity).
  - last_exposure / last_load : most recent occurred_at for each, i.e. staleness.
  - feedback          : counts by verdict (skill_feedback events), all zero if none exist yet.
  - state             : "never_exposed" / "exposed_never_loaded" / "loaded" -- the three states
                        docs/SEARCH-USE-TELEMETRY.md Sec6 separates. A skill can only be classified
                        "never_exposed" if it is named in an external roster (--roster-file): a
                        skill with zero events of any kind is, by construction, invisible to a
                        ledger that only stores events that happened -- this report cannot invent
                        knowledge of skills nobody ever searched, injected or loaded.

No per-person breakdown of any kind is computed or printed -- "no individual leaderboard"
(docs/SEARCH-USE-TELEMETRY.md Sec5/Sec6) is satisfied by never grouping by session_id/task_id here,
not by suppressing a column after the fact.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.telemetry import ledger

STATES = ("never_exposed", "exposed_never_loaded", "loaded")


def _parse_ts(value: str) -> datetime.datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.datetime.fromisoformat(text)


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _max_ts(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if _parse_ts(a) >= _parse_ts(b) else b


def compute_report(conn, tenant_id: str, roster: list = None) -> dict:
    """Build the per-(skill_id, revision) report for one tenant. `roster`, if given, is a list of
    skill_id (URN) strings known to exist independent of telemetry -- any roster entry with zero
    ledger events at all is reported once as `never_exposed` with revision=None."""
    events = ledger.fetch(conn, tenant_id)
    by_skill: dict = {}   # (skill_id, revision) -> accumulator

    def bucket(skill_id, revision):
        key = (skill_id, revision)
        if key not in by_skill:
            by_skill[key] = {
                "skill_id": skill_id, "revision": revision,
                "exposures": 0, "loads": 0,
                "scopes": set(), "producers": set(),
                "last_exposure": None, "last_load": None,
                "feedback": {v: 0 for v in ledger.VERDICTS},
            }
        return by_skill[key]

    for event in events:
        event_type = event.get("event_type")
        producer = event.get("producer")
        scope = event.get("scope")
        if event_type == "card_injected":
            b = bucket(event.get("skill_id"), event.get("revision"))
            b["exposures"] += 1
            b["last_exposure"] = _max_ts(b["last_exposure"], event.get("occurred_at"))
            if producer:
                b["producers"].add(producer)
            if scope:
                b["scopes"].add(scope)
        elif event_type == "skill_load_requested":
            skill_id, revision = event.get("skill_id"), event.get("revision")
            if skill_id:
                b = bucket(skill_id, revision)
                if producer:
                    b["producers"].add(producer)
                if scope:
                    b["scopes"].add(scope)
        elif event_type == "skill_load_completed":
            skill_id, revision = event.get("skill_id"), event.get("revision")
            if skill_id:   # an unresolved selector (skill_id unknown) cannot be attributed
                b = bucket(skill_id, revision)
                if event.get("status") == "ok":
                    b["loads"] += 1
                    b["last_load"] = _max_ts(b["last_load"], event.get("occurred_at"))
                if producer:
                    b["producers"].add(producer)
                if scope:
                    b["scopes"].add(scope)
        elif event_type == "skill_feedback":
            skill_id, revision = event.get("skill_id"), event.get("revision")
            b = bucket(skill_id, revision)
            verdict = event.get("verdict")
            if verdict in b["feedback"]:
                b["feedback"][verdict] += 1

    for skill_id in (roster or []):
        already = any(k[0] == skill_id for k in by_skill)
        if not already:
            bucket(skill_id, None)

    skills = []
    summary = {s: 0 for s in STATES}
    for (skill_id, revision), b in sorted(by_skill.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")):
        exposures, loads = b["exposures"], b["loads"]
        use_rate = "unknown" if exposures == 0 else round(loads / exposures, 4)
        if loads > 0:
            state = "loaded"
        elif exposures > 0:
            state = "exposed_never_loaded"
        else:
            state = "never_exposed"
        summary[state] += 1
        skills.append({
            "skill_id": skill_id, "revision": revision,
            "exposures": exposures, "loads": loads, "use_rate": use_rate,
            "distinct_scopes": sorted(b["scopes"]), "distinct_producers": sorted(b["producers"]),
            "last_exposure": b["last_exposure"], "last_load": b["last_load"],
            "feedback": b["feedback"], "state": state,
        })

    return {"tenant_id": tenant_id, "generated_at": _iso_now(), "skills": skills,
            "summary": summary}


def render_markdown(report: dict) -> str:
    lines = [f"### Per-skill usage -- tenant `{report['tenant_id']}` "
             f"(generated {report['generated_at']})", "",
             "| skill_id | revision | exposures | loads | use_rate | scopes | last_exposure | "
             "last_load | state |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in report["skills"]:
        lines.append(
            f"| {s['skill_id']} | {s['revision'] or '-'} | {s['exposures']} | {s['loads']} | "
            f"{s['use_rate']} | {len(s['distinct_scopes'])} | {s['last_exposure'] or '-'} | "
            f"{s['last_load'] or '-'} | {s['state']} |")
    summary = report["summary"]
    lines.append("")
    lines.append(
        f"Summary: never_exposed={summary['never_exposed']} "
        f"exposed_never_loaded={summary['exposed_never_loaded']} loaded={summary['loaded']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="sqlite ledger path")
    ap.add_argument("--tenant", help="report only this tenant (default: every tenant present)")
    ap.add_argument("--roster-file", help="JSON array of skill_id (URN) strings known to exist, "
                                          "for the never_exposed bucket")
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = ap.parse_args()

    roster = None
    if args.roster_file:
        roster = json.loads(Path(args.roster_file).read_text(encoding="utf-8"))

    conn = ledger.connect(args.db)
    tenant_ids = [args.tenant] if args.tenant else ledger.tenants(conn)
    reports = [compute_report(conn, t, roster=roster) for t in tenant_ids]

    if args.format == "json":
        print(json.dumps(reports if args.tenant is None else reports[0], indent=2))
    else:
        for report in reports:
            print(render_markdown(report))
            print()


if __name__ == "__main__":
    main()
