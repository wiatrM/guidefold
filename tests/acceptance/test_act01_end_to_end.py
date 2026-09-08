"""ACT-01 — the whole product path in one run, on the real stack.

Login, organisation, device login, scan, import, catalog, publication, installer, SEARCH,
USE, telemetry, feedback, usage, owner decision, audit — then the authoring loop (plan,
generate, approve, export, apply, re-import, published) and the drift loop (changed source,
removed source, partial scan). One report row, with every identifier it produced.

Nothing here is stubbed. The CLI is the shipped script in a subprocess, the HTTP client is
the one a browser drives, and the worker is the real Go binary running the real Python
builder.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance


@pytest.mark.acc("ACT-01")
def test_act01_end_to_end(world, installation, report, socket_guard, gf_stack):
    """The whole chain, recorded whatever happens.

    ACT-01 is one row, and a row that vanishes when step nine of twenty fails is worse than a
    failing row: it hides the eight steps that did work. So the evidence is accumulated as the
    walk proceeds, the current step is named, and the row is written from a `finally`."""
    from gf_acceptance_support import add_runbooks, commit_all

    w, ev = world, {}
    try:
        _act01(w, ev, installation, socket_guard, gf_stack, add_runbooks, commit_all)
    except BaseException as failure:                       # noqa: BLE001 - reported, not swallowed
        ev["failed_at_step"] = ev.get("step")
        ev["failure"] = f"{type(failure).__name__}: {failure}"[:1500]
        _record_act01(report, ev, result="fail")
        raise
    _record_act01(report, ev, result="pass")


def _record_act01(report, ev, *, result):
    report.record("ACT-01", prd_ac="Backlog ACT-01; U1, U2, U4, U5, U6, U9",
                  scenario="dev login -> org -> device login -> scan --dry-run -> import --wait -> "
                           "catalog -> publish -> install -> find/USE via the snapshot -> telemetry "
                           "-> feedback -> usage -> owner decision -> audit -> propose/approve/export/"
                           "apply/re-import -> drift",
                  command_or_endpoint="guidefold login|org use|scan|import|install|find|load|"
                                      "telemetry flush|proposals apply + /api/v1/** + /v1/search|use|events:batch",
                  data_origin="examples/monorepo copied into a fresh git work tree; local stack "
                              "(PostgreSQL + Go API + worker), deterministic generator",
                  result=result, evidence=ev,
                  limitation="Loopback only, one machine, synthetic telemetry produced by this "
                             "run's own CLI. Proves R (release acceptance), not pilot value."
                             + ("" if result == "pass" else
                                " This run stopped at the step named in `failed_at_step`; every "
                                "field above it is a measurement that did happen."))


def _act01(w, ev, installation, socket_guard, gf_stack, add_runbooks, commit_all):
    ev["step"] = "runbooks"
    ev["org_id"] = w.org_id
    ev["api"] = w.api

    # Two runbooks with an ordered procedure. The fixture's own README files are prose, so
    # det-1 abstains on all of them with `no_procedure_found` -- correct behaviour, but it
    # leaves the authoring loop nothing to work on.
    ev["runbooks"] = [str(p.relative_to(w.tree)) for p in add_runbooks(w.tree)]
    ev["runbook_commit"] = commit_all(w.tree, "add two runbooks with ordered procedures")

    # --- `org use` --------------------------------------------------------------------
    ev["step"] = "org use"
    w.cli.run(["org", "use", w.org], cwd=w.tree)
    creds = json.loads(w.cli.credentials.read_text())
    assert creds[w.api]["org"] == w.org
    ev["credentials_mode"] = oct(w.cli.credentials.stat().st_mode & 0o777)
    assert ev["credentials_mode"] == "0o600", "the CLI credential file must be 0600 (U5 AC2)"

    # --- `scan --dry-run` opens no socket, and is byte-identical to what import sends ---
    ev["step"] = "scan --dry-run"
    scanned = w.cli.json(["scan", "--dry-run", "--json"], cwd=w.tree,
                         PYTHONPATH=str(socket_guard))
    assert scanned["format"] == "guidefold-import-manifest-v1"
    assert scanned["complete"] is True and scanned["dirty"] is False
    ev["scan_files"] = len(scanned["files"])
    ev["scan_commit"] = scanned["commit"]
    ev["scan_excluded"] = len(scanned["excluded"])

    # --- import --wait ------------------------------------------------------------------
    ev["step"] = "import --wait"
    imported = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    w.import_id = imported["import_id"]
    ev["import_id"] = w.import_id
    ev["import_state"] = imported["state"]
    ev["new_blobs"] = imported["new_blobs"]
    assert imported["state"] == "ready", imported
    assert imported["manifest_digest"], imported

    status = w.get(f"/imports/{w.import_id}")
    assert status["complete"] is True
    ev["import_counts"] = status["counts"]

    # --- the catalog: 27 skills, each with scope, owner and source ---------------------
    ev["step"] = "catalog"
    listed, cursor = [], None
    while True:
        page = w.get("/skills" + (f"?cursor={cursor}" if cursor else "?limit=100"))
        listed.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            break
    from gf_acceptance_support import authored_skills
    expected = authored_skills(w.tree)
    ev["skills"] = len(listed)
    ev["skill_md_files_on_disk"] = len(list(w.tree.rglob("SKILL.md")))
    # A card carrying `metadata.generated: true` (the committed hierarchy index) is skipped by
    # the builder on purpose and reported as `generated_skipped`, so the catalog holds the
    # authored cards, not every file on disk (ADR-0012).
    ev["generated_cards_excluded"] = ev["skill_md_files_on_disk"] - len(expected)
    assert {s["path"] for s in listed} == set(expected), \
        sorted(set(expected) ^ {s["path"] for s in listed})
    assert all(s["scope"] for s in listed), "every skill must carry a routing scope"
    assert all(s["owner"] for s in listed), "every skill must carry an owner"
    assert all(s["path"] for s in listed), "every skill must carry its source path"
    ev["scopes"] = sorted({s["scope"] for s in listed})[:8]

    # --- publication: a job that activates a snapshot ----------------------------------
    ev["step"] = "publish"
    queued = w.owner.expect("POST", w.base + "/publish", ok=(200,),
                            body={"idempotency_key": "act01-publish",
                                  "import_id": w.import_id})
    ev["publish_job_id"] = queued["job_id"]
    snapshot = _wait_publication(w)
    assert snapshot["state"] == "active", f"publication failed: {snapshot.get('error')}"
    w.snapshot_id = snapshot["snapshot_id"]
    ev["snapshot_id"] = w.snapshot_id
    ev["snapshot_n_skills"] = snapshot["n_skills"]
    ev["snapshot_active"] = snapshot["active"]
    assert snapshot["active"] is True

    # --- installer ----------------------------------------------------------------------
    ev["step"] = "install"
    install = w.cli.run(["install", "--harness", "claude"], cwd=w.tree)
    manifest_path = w.tree / ".agents/skills/guidefold/INSTALL-MANIFEST.json"
    assert manifest_path.is_file(), install.stdout
    manifest = json.loads(manifest_path.read_text())
    ev["install_manifest_files"] = len(manifest["files"])
    assert (w.tree / ".claude/settings.json").is_file(), "the Claude hook must be wired"
    again = w.cli.run(["install", "--harness", "claude"], cwd=w.tree)
    assert "nothing to do" in again.stdout, again.stdout   # idempotent (U5 AC1)

    # --- find through search.backend: service, with the installation token --------------
    ev["step"] = "find via search.backend: service"
    token_file = w.cli.home / "installation-token"
    token_file.write_text(installation)
    token_file.chmod(0o600)
    yaml_path = w.tree / "guidefold.yaml"
    yaml_path.write_text(yaml_path.read_text() +
                         f"\nsearch:\n  backend: service\n  url: {w.api}\n"
                         f"  deadline_ms: 4000\n  token_file: {token_file}\n")
    found = w.cli.run(["find", "handle an outage in turnstile auth", "--limit", "4"],
                      cwd=w.tree / "platforms/atlas/identity")
    urns = [line.strip()[2:] for line in found.stdout.splitlines()
            if line.strip().startswith("- urn:skill:")]
    ev["find_urns"] = urns
    assert urns, found.stdout

    # The same query straight at the contract, so the revisions can be tied to the snapshot.
    anon = _anon(gf_stack)
    _, search, _ = anon.request("POST", "/v1/search", token=installation, body={
        "schema_version": "1.1", "query": "handle an outage in turnstile auth",
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    ev["search_id"] = search["search_id"]
    ev["search_cards"] = [(c["urn"], c["revision"][:12]) for c in search["cards"]]
    assert search["cards"], search
    catalogue = {s["skill_id"]: s for s in listed}
    for card in search["cards"]:
        assert card["urn"] in catalogue, f"{card['urn']} is not in this repository's catalog"
        assert card["revision"], "a card without a revision cannot be loaded reproducibly"

    # --- load / USE 1.2: body, verified checksum, closure -------------------------------
    ev["step"] = "USE 1.2"
    card = search["cards"][0]
    status_code, used, _ = anon.request("POST", "/v1/use", token=installation, body={
        "schema_version": "1.2", "search_id": search["search_id"],
        "skill_id": card["urn"], "revision": card["revision"],
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    assert status_code == 200, used
    body = used["body"]
    import hashlib
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == used["checksum"], \
        "USE's checksum must be the checksum of the bytes it returned"
    assert used["snapshot"] == w.snapshot_id, "USE must answer from the activated snapshot"
    assert used["closure"]["status"] in ("complete", "unresolved", "cannot_fit")
    ev["use"] = {"skill_id": used["skill_id"], "revision": used["revision"][:12],
                 "checksum_verified": True, "body_bytes": len(body.encode()),
                 "closure_status": used["closure"]["status"],
                 "closure_depth_limit": used["closure"]["depth_limit"],
                 "resources": len(used["resources"]), "snapshot": used["snapshot"]}

    # `backend: service` requires the exact revision: a body without one is not reproducible.
    cli_load = w.cli.run(["load", f"{card['urn']}@{card['revision']}"],
                         cwd=w.tree / "platforms/atlas/identity")
    assert cli_load.stdout.strip(), "guidefold load printed nothing"
    ev["cli_load_bytes"] = len(cli_load.stdout)

    # --- telemetry: the CLI's own spool, flushed to the ledger ---------------------------
    ev["step"] = "telemetry"
    spool = sorted((w.tree / ".guidefold/telemetry/spool").rglob("events-*.jsonl"))
    assert spool, "find/load must have written SEARCH/USE events to the local spool"
    kinds = {}
    for path in spool:
        for line in path.read_text().splitlines():
            if line.strip():
                name = json.loads(line).get("event_type") or json.loads(line).get("type")
                kinds[name] = kinds.get(name, 0) + 1
    ev["spooled_event_types"] = kinds
    assert "card_injected" in kinds, kinds

    flushed = w.cli.run(["telemetry", "flush", "--url", w.api,
                         "--token-file", str(token_file)], cwd=w.tree)
    summary = flushed.stdout.strip().splitlines()[-1]
    ev["telemetry_flush"] = summary
    counts = dict(part.split("=", 1) for part in summary.split() if "=" in part)
    assert int(counts["accepted"]) > 0, summary
    assert int(counts["rejected"]) == 0, summary

    # `skill_load_completed` is what a client-confirmed load looks like; the CLI's `load`
    # emits it, and the ledger must have taken it.
    accepted = _ledger_types(gf_stack, w.org_id)
    ev["ledger_event_types"] = accepted
    assert accepted.get("card_injected", 0) > 0, accepted
    assert accepted.get("skill_load_completed", 0) > 0, accepted

    # --- feedback, exactly as the UI posts it -------------------------------------------
    # The UI posts feedback from the Skill view, so it carries the *catalog* revision id
    # (gfm.skill_revisions), which is not the delivery revision USE answered with
    # (gf.skills.skill_revision). Both ids are recorded below.
    ev["step"] = "feedback"
    skill_id = used["skill_id"]
    catalog_revision = catalogue[skill_id]["revision_id"]
    judgment = w.owner.expect(
        "POST", f"{w.base}/skills/{_seg(skill_id)}/revisions/{catalog_revision}/feedback",
        ok=(200, 201),
        body={"idempotency_key": "act01-feedback", "verdict": "helped",
              "reason": "the runbook matched the incident"})
    ev["judgment_id"] = judgment["judgment_id"]
    ev["revision_ids"] = {"delivery_from_use": used["revision"],
                          "catalog_from_skills": catalog_revision,
                          "content_sha256": catalogue[skill_id]["content_sha256"],
                          "identical": used["revision"] == catalog_revision}

    # --- usage: numerators, denominators, and unknown that is not zero -------------------
    ev["step"] = "usage"
    usage = _wait_usage(w)
    rows = [r for r in usage["skills"] if r["skill_id"] == skill_id]
    delivered = next(r for r in rows if r["exposures"] >= 1)
    judged = next(r for r in rows if r["feedback"] and r["feedback"]["n"] >= 1)
    ev["usage_rows_for_this_skill"] = [
        {k: r.get(k) for k in ("revision", "exposures", "loads_verified", "context_loaded",
                               "context_unknown", "use_reported", "use_observed", "feedback",
                               "helped_ratio", "zero_loads")} for r in rows]
    ev["usage_totals"] = usage["totals"]
    ev["usage_coverage"] = usage["coverage"]
    ev["usage_window"] = usage["window"]
    assert delivered["loads_verified"] >= 1, delivered
    assert delivered["context_unknown"] >= 1, \
        "an adapter that cannot confirm context is unknown, not zero"
    ratio = judged["helped_ratio"]
    assert ratio and ratio["denominator"] >= 1, judged
    assert ratio["numerator"] <= ratio["denominator"], ratio
    assert ratio["small_sample"] is True, "fewer than 20 judgments must be flagged small_sample"
    # HTTP 200 on USE is not "used": nothing reported an applied episode.
    assert delivered["use_reported"] == 0 and delivered["use_observed"] == 0, delivered
    assert usage["totals"]["context_unknown"] >= 1, usage["totals"]

    # --- the owner records a decision on a queue item ------------------------------------
    ev["step"] = "owner queue decision"
    queue = usage.get("queue") or []
    ev["queue_reasons"] = sorted({q["reason"] for q in queue})
    assert queue, "the owner's review queue is empty; nothing to decide on"
    item = queue[0]
    decided = w.owner.expect(
        "POST", f"{w.base}/usage/queue/{item['item_id']}/decision", ok=(200, 201),
        body={"idempotency_key": "act01-queue", "action": "reviewed",
              "reason": "reviewed during the acceptance run"})
    ev["queue_decision"] = {"item_id": item["item_id"], "reason": item["reason"],
                            "decision": decided["item"]["decision"]}

    # --- audit ---------------------------------------------------------------------------
    ev["step"] = "audit"
    audit = w.owner.expect("GET", w.org_base + "/audit")
    actions = [a["action"] for a in audit["items"]]
    ev["audit_actions"] = sorted(set(actions))
    for expected in ("publication.request", "org.create", "repo.create"):
        assert expected in actions, (expected, actions)

    # --- the authoring loop ---------------------------------------------------------------
    ev["step"] = "authoring loop"
    ev["authoring"] = _authoring_loop(w, gf_stack)

    # --- the drift loop --------------------------------------------------------------------
    ev["step"] = "drift loop"
    ev["drift"] = _drift_loop(w)



# ---------------------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------------------


def _authoring_loop(w, gf_stack) -> dict:
    """plan -> proposals:generate -> approve -> export -> apply --write -> commit -> import."""
    from gf_acceptance_support import wait_until

    out = {}
    plan = w.get(f"/imports/{w.import_id}/plan")
    out["plan_groups"] = len(plan.get("groups", []))
    out["plan_limits"] = plan.get("limits")

    generated = w.owner.expect(
        "POST", f"{w.base}/imports/{w.import_id}/proposals:generate", ok=(200, 201, 202),
        body={"idempotency_key": "act01-generate", "kinds": ["extraction"]})
    out["generate_job_ids"] = generated.get("job_ids")

    proposals = wait_until(
        lambda: (w.get("/proposals?state=draft").get("items") or None),
        timeout=240, what="the deterministic generator to write at least one proposal")
    out["proposals"] = len(proposals)
    proposal = proposals[0]
    detail = w.get(f"/proposals/{proposal['proposal_id']}")
    out["provenance_fields"] = sorted({p["field"] for p in detail["provenance"]})
    assert detail["provenance"], "every generated field needs an origin (U2 AC2)"
    for entry in detail["provenance"]:
        assert entry.get("source_ref") or entry.get("needs_confirmation") is True, entry

    decided = w.owner.expect(
        "POST", f"{w.base}/proposals/{proposal['proposal_id']}/decision", ok=(200, 201),
        body={"idempotency_key": "act01-approve", "decision": "approve",
              "reason": "accurate for this scope",
              "expected_revision": detail.get("expected_revision")})
    out["decision_state"] = decided["state"]
    assert decided["state"] == "approved_for_export", decided

    exported = w.owner.expect(
        "POST", f"{w.base}/proposals/{proposal['proposal_id']}/export", ok=(200, 201),
        body={"idempotency_key": "act01-export"})
    out["export_id"] = exported["export_id"]
    out["export_state"] = exported["state"]
    assert exported["state"] == "awaiting_git", "export is not publication"

    applied = w.cli.run(["proposals", "apply", exported["export_id"], "--write"], cwd=w.tree)
    out["apply_stdout_tail"] = applied.stdout.strip().splitlines()[-3:]
    from gf_acceptance_support import commit_all
    out["commit"] = commit_all(w.tree, "apply the approved proposal")

    second = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    out["second_import_id"] = second["import_id"]
    out["second_import_state"] = second["state"]
    assert second["state"] == "ready", second

    w.owner.expect("POST", w.base + "/publish", ok=(200,),
                   body={"idempotency_key": "act01-publish-2",
                         "import_id": second["import_id"]})
    _wait_publication(w, after=out["second_import_id"])

    state = wait_until(
        lambda: (w.get(f"/proposals/{proposal['proposal_id']}")["state"] == "published"
                 and "published"),
        timeout=180, what="the proposal to become published once its bytes landed in git")
    out["proposal_final_state"] = state

    skill_id = detail.get("target_skill_id")
    if skill_id:
        skill = w.get(f"/skills/{_seg(skill_id)}")
        out["skill_publication_status"] = skill["publication_status"]
        assert skill["publication_status"] == "published", skill
    return out


def _drift_loop(w) -> dict:
    """A changed source is `needs_review`; a removed one is `source_removed`; a partial scan
    never removes anything."""
    from gf_acceptance_support import commit_all, wait_until

    out = {}
    # Only a skill the *catalog* holds can drift. A committed generated card
    # (frontmatter `generated: true`, e.g. the hierarchy index) never gets a catalog
    # row — the builder makes no snapshot card for it — so deleting one is not a
    # `source_removed`. Choose from what the catalog actually knows.
    catalog = {item["path"] for item in w.get("/skills?limit=100")["items"]}
    candidates = [p for p in sorted(w.tree.rglob(".agents/skills/*/SKILL.md"))
                  if p.relative_to(w.tree).as_posix() in catalog]
    assert len(candidates) >= 2, sorted(catalog)
    changed = candidates[0]
    changed.write_text(changed.read_text() + "\n\nAn extra paragraph, added during acceptance.\n")
    commit_all(w.tree, "edit one SKILL.md")
    synced = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    out["sync_import_id"] = synced["import_id"]
    out["sync_new_blobs"] = synced["new_blobs"]

    usage = wait_until(
        lambda: next((q for q in (w.get("/usage").get("queue") or [])
                      if q["reason"] == "source_changed"), None),
        timeout=90, what="a source_changed queue item")
    out["source_changed_item"] = {"reason": usage["reason"], "skill_id": usage.get("skill_id"),
                                  "source": usage.get("source")}

    # `published -> needs_review` is written by the drift pass, which runs after the parse
    # that raised the queue item, so the status is polled rather than read once.
    changed_skill = wait_until(
        lambda: (lambda skill: skill if skill["publication_status"] == "needs_review" else None)(
            w.get(f"/skills/{_seg(usage['skill_id'])}")),
        timeout=90, what="the changed skill to be marked needs_review")
    out["changed_publication_status"] = changed_skill["publication_status"]
    out["changed_source_status"] = changed_skill["source_status"]

    # A partial scan must never imply a deletion.
    removed = next(p for p in candidates if p != changed)
    removed_dir = removed.parent
    import shutil
    shutil.rmtree(removed_dir)
    commit_all(w.tree, "remove one skill")
    partial = w.cli.json(["sync", "--partial", "--wait", "--json"], cwd=w.tree)
    out["partial_import_id"] = partial["import_id"]
    out["partial_complete"] = partial["complete"]
    assert partial["complete"] is False
    time.sleep(2)
    archived_after_partial = [q for q in (w.get("/usage").get("queue") or [])
                              if q["reason"] == "source_removed"]
    out["source_removed_after_partial"] = len(archived_after_partial)
    assert not archived_after_partial, "a partial scan must never imply a removal (U1.5, U9)"

    complete = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    out["complete_import_id"] = complete["import_id"]
    item = wait_until(
        lambda: next((q for q in (w.get("/usage").get("queue") or [])
                      if q["reason"] == "source_removed"), None),
        timeout=90, what="a source_removed queue item after a complete scan")
    out["source_removed_item"] = {"reason": item["reason"], "skill_id": item.get("skill_id")}
    return out


# ---------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------


def _seg(skill_id: str) -> str:
    import urllib.parse
    return urllib.parse.quote(skill_id, safe="")


def _anon(gf_stack):
    from gf_acceptance_support import ApiSession
    return ApiSession(gf_stack.api)


def _wait_publication(w, after: str = None):
    from gf_acceptance_support import wait_until

    def look():
        for snap in w.owner.expect("GET", w.base + "/snapshots")["items"]:
            if after and snap.get("import_id") != after:
                continue
            if snap["state"] in ("active", "failed"):
                return snap
        return None

    return wait_until(look, timeout=240, what="a terminal publication state")


def _wait_usage(w):
    from gf_acceptance_support import wait_until
    def look():
        report = w.get("/usage")
        return report if report.get("skills") else None

    return wait_until(look, timeout=120, what="a usage report with at least one measured row")


def _ledger_types(gf_stack, org_id: str) -> dict:
    rows = gf_stack.sql(
        "SELECT event_type, count(*) FROM gf.events WHERE tenant_id='" + org_id
        + "' GROUP BY event_type")
    return {r[0]: int(r[1]) for r in rows}
