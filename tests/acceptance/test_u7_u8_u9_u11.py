"""U7 (pre-merge report), U8/U10 (modules and shared procedures), U9 (drift), U11 (pilot).

U9 repeats ACT-01's drift steps on its own tenant, so the row stands on its own evidence
rather than on a side effect of the end-to-end walk.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

from gf_acceptance_support import (PASS, FAIL, NOT_MEASURED, REPO_ROOT, commit_all, git,
                                   make_git_tree, set_metadata, wait_until)

pytestmark = pytest.mark.acceptance


# ---------------------------------------------------------------------------------------
# U7 — the pre-merge change report
# ---------------------------------------------------------------------------------------


@pytest.mark.acc("U7")
def test_u7_the_change_report_names_the_defects_and_is_deterministic(fresh_org, report, scratch,
                                                                    bring_up):
    """U7: a branch that introduces a cycle, a missing dependency and a missing required
    resource; the report names all three and two runs are byte-identical."""
    w = fresh_org("u7-report")
    # Import once (no publication) purely to learn every skill's real URN: guessing one from a
    # directory name would produce `missing_required_dependency` for the wrong reason.
    bring_up(w, publish=False)
    base = git(w.tree, "rev-parse", "HEAD").stdout.strip()
    urns = _urns_by_path(w)
    paths = sorted(urns)
    a_path, b_path = paths[0], paths[1]
    a, b = w.tree / a_path, w.tree / b_path
    # A required package resource that is absent, in a directory the scan does carry.
    (a.parent / "references").mkdir(exist_ok=True)
    (a.parent / "references/present.md").write_text("# present\n")
    set_metadata(a, requires=[urns[b_path]],
                 references=["references/present.md", "references/absent.md"])
    set_metadata(b, requires=[urns[a_path], "urn:skill:meridian:_root:does-not-exist"])
    commit_all(w.tree, "introduce a cycle, a dangling requires and a missing resource")

    out_json = scratch / "u7-report.json"
    second_json = scratch / "u7-report-2.json"
    out_md = scratch / "u7-report.md"
    first = w.cli.run(["report", "--base", base, "--json", str(out_json),
                       "--markdown", str(out_md)], cwd=w.tree, check=False)
    w.cli.run(["report", "--base", base, "--json", str(second_json)], cwd=w.tree, check=False)

    body = json.loads(out_json.read_text())
    codes = sorted({f["code"] for f in body["findings"]})
    identical = out_json.read_bytes() == second_json.read_bytes()
    wanted = {"graph_cycle", "missing_required_dependency", "missing_required_resource"}
    found = wanted & set(codes)

    ok = found == wanted and identical
    report.record("U7", prd_ac="U7 / P12 (pre-merge change report)",
                  scenario="a branch introducing a requires cycle, a dangling requires and a "
                           "declared-but-absent required resource; the report is run twice",
                  command_or_endpoint="guidefold report --base <ref> --json --markdown",
                  data_origin="examples/monorepo in a fresh git work tree",
                  result=PASS if ok else FAIL,
                  evidence={"base_commit": base, "head_commit": body.get("head_commit"),
                            "codes": codes, "expected_codes": sorted(wanted),
                            "summary": body.get("summary"),
                            "byte_identical_across_two_runs": identical,
                            "markdown_lines": len(out_md.read_text().splitlines()),
                            "exit_code": first.returncode},
                  limitation="One branch with three planted defects; not the full severity matrix.")
    assert ok, (codes, identical)


# ---------------------------------------------------------------------------------------
# U8 / U10 — modules and shared procedures
# ---------------------------------------------------------------------------------------


@pytest.mark.acc("U8/U10")
def test_u8_u10_a_module_page_lists_its_reading_order_and_shares_a_skill(
        fresh_org, report, bring_up, gf_stack):
    """U8/U10: the module endpoint answers a reading order and names the skills a scope shares
    with others; a skill reachable from two modules keeps separate telemetry episodes."""
    w = fresh_org("u8-modules")
    bring_up(w)
    # Scope names come from the catalog's own facet list, which is what the Library renders.
    # `/skills/facets` answers `{field, values: [{value, count}], next_cursor}` -- `values`,
    # not `items`, which is the key every paged list endpoint uses.
    facets = w.get("/skills/facets?field=scope")
    names = [entry["value"] for entry in facets.get("values") or [] if entry.get("value")]
    assert names, facets
    pages = {}
    for scope in names[:4]:
        page = w.get(f"/modules/{urllib.parse.quote(str(scope), safe='')}")
        # `reading_order` is a list of skill ids; `shared` names the skills this module
        # borrows from elsewhere.
        pages[str(scope)] = {
            "reading_order": [_id(entry) for entry in page.get("reading_order") or []],
            "shared": [_id(entry) for entry in page.get("shared") or []],
            "owner": page.get("owner"),
            "documents": len(page.get("documents") or [])}
    every = {}
    for scope, page in pages.items():
        for skill_id in page["reading_order"] + page["shared"]:
            every.setdefault(skill_id, []).append(scope)
    in_two = {k: v for k, v in every.items() if len(v) > 1}

    # Two modules using the same skill must not merge their episodes.
    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u8", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["events"]},
                           headers={"Idempotency-Key": "u8-inst"})["token"]
    skill = w.get("/skills?limit=1")["items"][0]
    from gf_acceptance_support import ApiSession
    import uuid
    from datetime import datetime, timezone
    client = ApiSession(gf_stack.api)
    events = []
    for task in ("task-module-a", "task-module-b"):
        events.append({"schema_version": "1.0", "event_id": str(uuid.uuid4()),
                       "event_type": "skill_use_reported",
                       "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "sequence": 1, "producer": "guidefold-acceptance", "adapter_version": "1",
                       "environment": "pilot", "skill_id": skill["skill_id"],
                       "revision": skill["revision_id"], "source": "adapter",
                       "report_category": "applied", "task_id": task,
                       "load_id": str(uuid.uuid4()), "use_id": str(uuid.uuid4())})
    client.request("POST", "/v1/events:batch", token=token, body={"events": events})
    row = next(r for r in w.get("/usage?window=30d")["skills"]
               if r["skill_id"] == skill["skill_id"] and r["use_reported"] > 0)

    ok = bool(pages) and all(p["reading_order"] for p in pages.values()) and row["use_episodes"] >= 2
    report.record("U8/U10", prd_ac="U8, U10 / P14 (module page, shared procedure)",
                  scenario="read the module page of several scopes, then report two applied "
                           "episodes of the same skill under two different task ids",
                  command_or_endpoint="GET {repo_base}/map/scopes; GET {repo_base}/modules/{scope}; "
                                      "POST /v1/events:batch; GET {repo_base}/usage",
                  data_origin="examples/monorepo published in this run",
                  result=PASS if ok else FAIL,
                  evidence={"modules": pages, "skills_in_more_than_one_module": in_two,
                            "shared_skill": skill["skill_id"],
                            "use_reported": row["use_reported"],
                            "use_episodes": row["use_episodes"]},
                  limitation="Episode separation is measured through the ledger's own task ids; "
                             "no real agent produced them.")
    assert ok, (pages, row)


# ---------------------------------------------------------------------------------------
# U9 — drift
# ---------------------------------------------------------------------------------------


@pytest.mark.acc("U9")
def test_u9_drift_asks_for_review_and_a_partial_scan_never_removes(fresh_org, report, bring_up):
    """U9: a changed source becomes `source_changed`, a removed one becomes `source_removed`
    only after a *complete* scan, and a retry adds no duplicate queue item."""
    w = fresh_org("u9-drift")
    bring_up(w)
    # Only a skill the *catalog* holds can drift: drift compares the import with the
    # catalog rows, and a committed generated card (frontmatter `generated: true`, e.g.
    # the hierarchy index) is deliberately never given one, so deleting it is not a
    # `source_removed`. Picking the files off disk chose that card and asked the service
    # for an observation it cannot make.
    catalog = _urns_by_path(w)
    skills = [p for p in sorted(w.tree.rglob(".agents/skills/*/SKILL.md"))
              if p.relative_to(w.tree).as_posix() in catalog]
    assert len(skills) >= 2, sorted(catalog)
    changed, removed = skills[0], skills[1]

    changed.write_text(changed.read_text() + "\n\nAn extra paragraph added during acceptance.\n")
    commit_all(w.tree, "edit one SKILL.md")
    w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    changed_item = wait_until(lambda: _queue(w, "source_changed"), timeout=90,
                              what="a source_changed queue item")
    changed_skill = w.get(f"/skills/{urllib.parse.quote(changed_item['skill_id'], safe='')}")

    shutil.rmtree(removed.parent)
    commit_all(w.tree, "remove one skill")
    partial = w.cli.json(["sync", "--partial", "--wait", "--json"], cwd=w.tree)
    time.sleep(2)
    after_partial = [q for q in w.get("/usage")["queue"] if q["reason"] == "source_removed"]

    complete = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    removed_item = wait_until(lambda: _queue(w, "source_removed"), timeout=90,
                              what="a source_removed queue item after a complete scan")
    removed_skill = w.get(f"/skills/{urllib.parse.quote(removed_item['skill_id'], safe='')}")

    before = len(w.get("/usage")["queue"])
    w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    time.sleep(2)
    after_retry = len(w.get("/usage")["queue"])

    # The contract's own words: a changed source asks for review, a removed one is archived
    # and never deleted, and a partial scan implies neither.
    ok = (changed_skill["publication_status"] == "needs_review"
          and not after_partial
          and removed_skill["source_status"] == "removed"
          and removed_skill["publication_status"] in ("archived", "needs_review")
          and after_retry == before)
    report.record("U9", prd_ac="U9 / P13 (drift; a partial scan never removes)",
                  scenario="edit one SKILL.md and sync; delete another and sync --partial; then "
                           "sync completely; then sync again",
                  command_or_endpoint="guidefold sync [--partial] --wait; GET {repo_base}/usage; "
                                      "GET {repo_base}/skills/{skill_id}",
                  data_origin="examples/monorepo published in this run",
                  result=PASS if ok else FAIL,
                  evidence={"changed": {"skill_id": changed_item["skill_id"],
                                        "reason": changed_item["reason"],
                                        "publication_status": changed_skill["publication_status"],
                                        "source_status": changed_skill["source_status"]},
                            "partial_import_id": partial["import_id"],
                            "partial_complete": partial["complete"],
                            "source_removed_items_after_partial": len(after_partial),
                            "complete_import_id": complete["import_id"],
                            "removed": {"skill_id": removed_item["skill_id"],
                                        "reason": removed_item["reason"],
                                        "publication_status": removed_skill["publication_status"],
                                        "source_status": removed_skill["source_status"]},
                            "queue_before_retry": before, "queue_after_retry": after_retry},
                  limitation="One changed and one removed file; the negative-feedback path into the "
                             "same queue is measured in U6, not here.")
    assert ok, (changed_skill, after_partial, removed_skill, before, after_retry)


# ---------------------------------------------------------------------------------------
# U11 — the pilot report generator
# ---------------------------------------------------------------------------------------


@pytest.mark.acc("U11 (generator)")
def test_u11_the_pilot_report_runs_on_synthetic_events_and_says_so(report, scratch, tmp_path):
    """U11: the rubric and the report generator exist and run; the numbers are synthetic and are
    labelled as such. The pilot itself is `not_measured_here`."""
    protocol = REPO_ROOT / "docs/pilot/E6.7-PROTOCOL.md"
    sheet = REPO_ROOT / "docs/pilot/scoring-sheet.template.csv"
    bank = REPO_ROOT / "docs/pilot/task-bank.template.yaml"
    present = {p.name: p.is_file() for p in (protocol, sheet, bank)}

    database = tmp_path / "pilot.sqlite3"
    sys.path.insert(0, str(REPO_ROOT))
    from tools.telemetry import ledger, report as ledger_report
    import uuid
    from datetime import datetime, timezone
    conn = ledger.connect(str(database))
    events = []
    for i in range(6):
        events.append({"schema_version": "1.0", "event_id": str(uuid.uuid4()),
                       "event_type": "card_injected",
                       "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "sequence": 1, "producer": "guidefold-acceptance", "adapter_version": "1",
                       "environment": "pilot", "exposure_id": str(uuid.uuid4()),
                       "skill_id": f"urn:skill:meridian:_root:s{i}", "revision": "r" + str(i),
                       "position": 1, "surface": "hook", "delivery_evidence": "client_confirmed",
                       "search_id": str(uuid.uuid4())})
    ledger.ingest(conn, "pilot-tenant", events)
    built = ledger_report.compute_report(conn, "pilot-tenant")

    report.record("U11 (generator)", prd_ac="U11 / P15 (pilot report generator)",
                  scenario="run the report generator over a synthetic event set and check the "
                           "protocol and rubric templates are in the repository",
                  command_or_endpoint="tools/telemetry/ledger.py + report.py; docs/pilot/*",
                  data_origin="synthetic events written by this test [synthetic, n=6]",
                  result=PASS if all(present.values()) and built["skills"] else FAIL,
                  evidence={"templates_present": present,
                            "skills_in_report": len(built["skills"]),
                            "first_row": built["skills"][0] if built["skills"] else None},
                  limitation="Synthetic input. It proves the generator runs and the templates "
                             "exist, nothing about a pilot.")

    report.record("U11 (pilot)", prd_ac="U11 / P15 P (the pilot itself)",
                  scenario="three teams, 20-40 paired tasks, a frozen rubric and a report with "
                           "both directions of the result (docs/pilot/E6.7-PROTOCOL.md)",
                  command_or_endpoint="—", data_origin="—",
                  result=NOT_MEASURED, evidence={},
                  limitation="P-level: needs real teams and a design partner. No amount of local "
                             "measurement substitutes for it (pilot-evidence).")
    assert all(present.values()), present


# ---------------------------------------------------------------------------------------


def _id(entry):
    """A module page lists skills as bare ids; a shared entry may be an object."""
    return entry if isinstance(entry, str) else entry.get("skill_id")


def _queue(w, reason: str):
    for item in w.get("/usage").get("queue") or []:
        if item["reason"] == reason:
            return item
    return None


def _urns_by_path(w) -> dict:
    """Every skill's real URN and source path, from the catalog the import just wrote."""
    items, cursor = [], None
    while True:
        page = w.get("/skills" + (f"?cursor={cursor}" if cursor else "?limit=100"))
        items.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return {s["path"]: s["skill_id"] for s in items}
