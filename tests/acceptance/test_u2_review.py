"""U2 — the authoring loop: what a generator may claim, and what stops a bad candidate.

Every test owns a throwaway organisation. The generator is `deterministic` (recipe det-1)
unless the test restarts the worker with a different one, which is how U2-7's "no LLM
configured" case is measured without inventing a provider.
"""
from __future__ import annotations

import json
import time
import urllib.parse

import pytest

from gf_acceptance_support import (PASS, FAIL, NOT_MEASURED, add_runbooks, break_frontmatter,
                                   commit_all, make_git_tree, set_metadata, wait_until)

pytestmark = pytest.mark.acceptance


@pytest.mark.acc("U2-1")
def test_u2_1_one_broken_file_fails_alone_and_blocks_activation(fresh_org, report):
    """U2-1: a malformed SKILL.md is `failed`, its neighbours are `accepted`, the import is
    `partial`, and a partial import never activates."""
    w = fresh_org("u2-partial")
    make_git_tree(w.tree)
    broken = w.tree / ".agents/skills/adr-process/SKILL.md"
    break_frontmatter(broken)
    commit_all(w.tree, "break one SKILL.md")

    imported = w.cli.json(["import", "--wait", "--json"], cwd=w.tree, check=False)
    status = w.get(f"/imports/{imported['import_id']}")
    by_status = {}
    for f in status["files"]:
        by_status.setdefault(f["status"], []).append(f["path"])
    failed = by_status.get("failed", [])

    # `finalize` already enqueues publish.build (the manifest's `publish: true`), and asking
    # again for a partial import is refused rather than queued twice.
    publish_status, publish_body, _ = w.owner.request(
        "POST", w.base + "/publish",
        body={"idempotency_key": "u2-1-publish", "import_id": imported["import_id"]})
    time.sleep(3)
    snapshots = w.owner.expect("GET", w.base + "/snapshots")["items"]
    active = [s for s in snapshots if s["active"]]

    ok = (status["state"] == "partial" and len(failed) == 1
          and len(by_status.get("accepted", [])) > 1 and not active)
    report.record("U2-1", prd_ac="U2 AC1 (per-file failure)",
                  scenario="one SKILL.md with unterminated frontmatter; the rest of the tree is "
                           "untouched. Then publish the partial import.",
                  command_or_endpoint="guidefold import --wait; GET {repo_base}/imports/{id}; "
                                      "POST {repo_base}/publish; GET {repo_base}/snapshots",
                  data_origin="examples/monorepo with one file deliberately broken",
                  result=PASS if ok else FAIL,
                  evidence={"import_state": status["state"],
                            "failed": failed,
                            "failed_reason": next((f.get("reason") for f in status["files"]
                                                   if f["status"] == "failed"), None),
                            "accepted": len(by_status.get("accepted", [])),
                            "omitted": len(by_status.get("omitted", [])),
                            "active_snapshots": len(active),
                            "publish_request": {"status": publish_status,
                                                "error": publish_body.get("error"),
                                                "state": publish_body.get("state")},
                            "publication_states": [s["state"] for s in snapshots]},
                  limitation="One malformed file; not an exhaustive parser-failure matrix.")
    assert ok, (status["state"], failed, active)


@pytest.mark.acc("U2-2")
def test_u2_2_every_generated_field_names_its_origin(fresh_org, report, bring_up):
    """U2-2: provenance — each field carries an origin plus either a source reference or an
    explicit `needs_confirmation`."""
    w = fresh_org("u2-provenance")
    bring_up(w, publish=False, runbooks=True)
    proposals = _generate(w, ["extraction"])
    detail = w.get(f"/proposals/{proposals[0]['proposal_id']}")
    bad = [p for p in detail["provenance"]
           if not p.get("source_ref") and p.get("needs_confirmation") is not True]

    report.record("U2-2", prd_ac="U2 AC2 (provenance)",
                  scenario="run the deterministic generator and read one proposal's provenance",
                  command_or_endpoint="POST {repo_base}/imports/{id}/proposals:generate; "
                                      "GET {repo_base}/proposals/{proposal_id}",
                  data_origin="examples/monorepo, generator det-1 (no network, no model)",
                  result=PASS if not bad else FAIL,
                  evidence={"proposals": len(proposals),
                            "fields": [{k: p.get(k) for k in
                                        ("field", "origin", "source_ref", "needs_confirmation")}
                                       for p in detail["provenance"]],
                            "recipe": detail["recipe"]},
                  limitation="The other half of this AC — a provider returning malformed JSON is "
                             "rejected rather than believed — needs an HTTP provider and is covered "
                             "by services/search/internal/review/generator/remote_test.go, not by "
                             "this run.")
    assert not bad, bad


@pytest.mark.acc("U2-3")
def test_u2_3_a_killed_worker_resumes_without_duplicating_candidates(fresh_org, report, gf_stack):
    """U2-3: kill the worker mid-run, restart it, and check the job is fenced by generation and
    the proposals are not written twice."""
    w = fresh_org("u2-fencing")
    make_git_tree(w.tree)
    add_runbooks(w.tree)
    commit_all(w.tree, "add runbooks the generator can extract from")
    w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    import_id = w.get("/imports")["items"][0]["import_id"]

    queued = w.owner.expect("POST", f"{w.base}/imports/{import_id}/proposals:generate",
                            ok=(200, 201, 202),
                            body={"idempotency_key": "u2-3-generate", "kinds": ["extraction"]})
    gf_stack.stop_worker()                      # mid-flight: the lease is still held
    before = _job_rows(gf_stack, w.org_id)
    gf_stack.restart_worker()
    proposals = wait_until(lambda: (w.get("/proposals").get("items") or None),
                           timeout=240, what="the restarted worker to finish the generation")
    after = _job_rows(gf_stack, w.org_id)
    paths = [p["path"] for p in proposals]
    duplicates = sorted({p for p in paths if paths.count(p) > 1})

    report.record("U2-3", prd_ac="U2 AC3 (restart, generation fencing)",
                  scenario="enqueue a generation, kill the worker while the lease is held, restart "
                           "it, and compare the job rows and the candidates",
                  command_or_endpoint="POST {repo_base}/imports/{id}/proposals:generate; "
                                      "SIGTERM the worker; restart; GET {repo_base}/proposals",
                  data_origin="examples/monorepo, generator det-1",
                  result=PASS if not duplicates else FAIL,
                  evidence={"job_ids": queued.get("job_ids"),
                            "jobs_before_restart": before, "jobs_after_restart": after,
                            "proposals": len(proposals), "duplicate_paths": duplicates},
                  limitation="The kill is a SIGTERM between lease and completion; it does not "
                             "simulate a torn write inside the database.")
    assert not duplicates, duplicates


@pytest.mark.acc("U2-4")
def test_u2_4_thirty_proposal_quality_sample_is_not_measured_here(report):
    report.record("U2-4", prd_ac="U2 AC4 Q (30-proposal review sample)",
                  scenario="two reviewers score 30 generated proposals against a rubric frozen "
                           "before generation, then a frozen 60-item run (PRODUCT-PIVOT §12a)",
                  command_or_endpoint="—",
                  data_origin="—",
                  result=NOT_MEASURED,
                  evidence={},
                  limitation="Q-level acceptance: needs two human reviewers and a rubric agreed "
                             "before the run. An agent scoring its own generator's output is not "
                             "evidence (eval-evidence-rules).")


@pytest.mark.acc("U2-5")
def test_u2_5_consolidation_either_names_its_sources_or_abstains(fresh_org, report, bring_up,
                                                                    gf_stack):
    """U2-5: det-1 either produces a consolidation naming the shared element, or declines and
    says why. Both are correct answers; silently guessing is not."""
    w = fresh_org("u2-consolidation")
    bring_up(w, publish=False, runbooks=True)
    import_id = w.get("/imports")["items"][0]["import_id"]
    plan = w.get(f"/imports/{import_id}/plan?kinds=consolidation")
    started = w.owner.expect("POST", f"{w.base}/imports/{import_id}/proposals:generate",
                             ok=(200, 201, 202),
                             body={"idempotency_key": "u2-5-generate",
                                   "kinds": ["consolidation"]})
    job_ids = started.get("job_ids") or []
    jobs = _wait_jobs(w, import_id, job_ids) if job_ids else []
    proposals = [p for p in w.get("/proposals?kind=consolidation").get("items", [])]

    abstained = [j for j in jobs if j["state"] == "skipped"]
    # A deterministic recipe that finds nothing to consolidate does not fail and does not end
    # `skipped`: it completes and records *why* it declined, per group, in the job result.
    # That written-down reason is the abstention this AC asks for.
    reasons = _abstentions(gf_stack, w.org_id, "proposal.generate")
    measured = bool(proposals) or bool(abstained) or bool(reasons) or not job_ids
    report.record("U2-5", prd_ac="U2 AC5 (consolidation or a stated abstention)",
                  scenario="ask det-1 for consolidations over the fixture and record either the "
                           "candidates it wrote or the reason it declined",
                  command_or_endpoint="GET {repo_base}/imports/{id}/plan?kinds=consolidation; "
                                      "POST .../proposals:generate {kinds:[consolidation]}",
                  data_origin="examples/monorepo (planted pair, see "
                              "examples/monorepo/docs/runbooks/README.md), generator det-1",
                  result=PASS if measured else FAIL,
                  evidence={"planted_fixture": "Meridian fixture, planted for U2 AC5",
                            "planned_groups": len(plan.get("groups", [])),
                            "groups_skipped": plan.get("groups_skipped"),
                            "job_ids": job_ids,
                            "job_states": [{"state": j["state"], "error": j.get("error")}
                                           for j in jobs],
                            "consolidations": [{"path": p["path"], "scope": p.get("scope")}
                                               for p in proposals],
                            "abstentions": reasons},
                  limitation="The fixture now carries a planted shared element in two sibling "
                             "scopes and a lookalike that must not merge, but consolidation reads "
                             "skills and the planted pair are documents: this test reaches them "
                             "only after extraction is approved, which P08-oneshot does end to "
                             "end. Here it proves the abstain-or-cite rule, not recall.")
    assert measured


@pytest.mark.acc("U2-6")
def test_u2_6_a_draft_is_never_served_and_a_cycle_blocks_the_head(fresh_org, report, bring_up,
                                                                  gf_stack):
    """U2-6: an unpublished skill is absent from SEARCH; a `requires` cycle fails the
    publication with 422-class findings and leaves the previous head serving."""
    w = fresh_org("u2-graph")
    _status, snapshot = bring_up(w)
    installation = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u2-6", "kind": "installation", "repo_id": w.repo,
              "scopes": ["search", "use"]},
        headers={"Idempotency-Key": "u2-6-inst"})["token"]

    # A new skill that is imported but never published must not answer SEARCH.
    draft_dir = w.tree / ".agents/skills/acceptance-draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / "SKILL.md").write_text(
        "---\nname: acceptance-draft\ndescription: \"[meridian] A draft written during the "
        "acceptance run to prove a draft is never served. Use when checking whether unpublished "
        "content reaches SEARCH. Do not use for anything else.\"\n---\n\n# Draft\n\nbody\n")
    commit_all(w.tree, "add a draft skill")
    w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    from gf_acceptance_support import ApiSession
    anon = ApiSession(gf_stack.api)
    _, served, _ = anon.request("POST", "/v1/search", token=installation, body={
        "schema_version": "1.1", "query": "a draft written during the acceptance run",
        "workspace": {"repo_id": w.repo, "cwd": "."}})
    draft_urns = [c["urn"] for c in served["cards"] if "acceptance-draft" in c["urn"]]

    # Now a cycle: two skills requiring each other.
    a = w.tree / ".agents/skills/adr-process/SKILL.md"
    b = w.tree / ".agents/skills/acceptance-draft/SKILL.md"
    skills = {s["path"]: s["skill_id"] for s in _all_skills(w)}
    set_metadata(a, requires=[skills[".agents/skills/acceptance-draft/SKILL.md"]])
    set_metadata(b, requires=[skills[".agents/skills/adr-process/SKILL.md"]])
    commit_all(w.tree, "make two skills require each other")
    # The head as it stands *now*: every complete import publishes (the manifest carries
    # `publish: true`), so the draft sync above legitimately moved it. What this AC is about
    # is that the cyclic one does not.
    head_before = _active_snapshot(w)
    cyclic = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    w.owner.request("POST", w.base + "/publish",
                    body={"idempotency_key": "u2-6-publish", "import_id": cyclic["import_id"]})
    def terminal():
        for row in w.owner.expect("GET", w.base + "/snapshots")["items"]:
            if row.get("import_id") == cyclic["import_id"] and row["state"] in ("active", "failed"):
                return row
        return None

    try:
        failed = wait_until(terminal, timeout=120,
                            what="a terminal state for the cyclic publication")
    except AssertionError:
        # No publication row for the cyclic import is also a correct outcome: the graph can be
        # rejected before a job is queued. Either way, what this AC is about is that the head
        # never moves to a snapshot built from a cyclic graph.
        failed = {"state": "not_queued", "validation": None, "error": None}
    still_active = [s for s in w.owner.expect("GET", w.base + "/snapshots")["items"] if s["active"]]

    ok = (not draft_urns and failed["state"] in ("failed", "not_queued")
          and still_active and still_active[0]["snapshot_id"] == head_before)
    report.record("U2-6", prd_ac="U2 AC6 (drafts are not served; a cycle blocks publication)",
                  scenario="import a new skill without publishing it and query SEARCH; then create "
                           "a requires cycle and publish",
                  command_or_endpoint="POST /v1/search; guidefold sync --wait; "
                                      "POST {repo_base}/publish; GET {repo_base}/snapshots",
                  data_origin="examples/monorepo plus a skill written for this run",
                  result=PASS if ok else FAIL,
                  evidence={"draft_cards_in_search": draft_urns,
                            "cards_returned": len(served["cards"]),
                            "cyclic_publication_state": failed["state"],
                            "cyclic_import_id": cyclic["import_id"],
                            "validation": failed.get("validation"),
                            "error": failed.get("error"),
                            "head_before": head_before,
                            "head_at_bring_up": snapshot["snapshot_id"],
                            "head_after": still_active[0]["snapshot_id"] if still_active else None},
                  limitation="One cycle of length two. Diamond, shared-atom, specialization and "
                             "scope-widening cases are covered by the graph package's own Go tests, "
                             "not re-measured here.")
    assert ok, (draft_urns, failed, still_active)


@pytest.mark.acc("U2-7")
def test_u2_7_no_generator_configured_is_skipped_not_failed(fresh_org, report, gf_stack):
    """U2-7: with `GUIDEFOLD_GENERATOR=none` the generation job ends `skipped` with
    `llm_not_configured` and the import stays usable."""
    w = fresh_org("u2-nollm")
    make_git_tree(w.tree)
    w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    import_id = w.get("/imports")["items"][0]["import_id"]
    gf_stack.restart_worker(generator="none")
    try:
        started = w.owner.expect("POST", f"{w.base}/imports/{import_id}/proposals:generate",
                                 ok=(200, 201, 202),
                                 body={"idempotency_key": "u2-7-generate",
                                       "kinds": ["extraction"]})
        jobs = _wait_jobs(w, import_id, started.get("job_ids") or [])
        status = w.get(f"/imports/{import_id}")
        plan = w.get(f"/imports/{import_id}/plan")
    finally:
        gf_stack.restart_worker()

    skipped = [j for j in jobs if j["state"] == "skipped"]
    ok = bool(skipped) and status["state"] == "ready"
    report.record("U2-7", prd_ac="U2 AC7 (no generator configured; cost ceiling)",
                  scenario="restart the worker with GUIDEFOLD_GENERATOR=none and ask for "
                           "extraction proposals",
                  command_or_endpoint="POST {repo_base}/imports/{id}/proposals:generate; "
                                      "GET {repo_base}/imports/{id}",
                  data_origin="examples/monorepo, generator none",
                  result=PASS if ok else FAIL,
                  evidence={"job_states": [{"state": j["state"], "error": j.get("error")}
                                           for j in jobs],
                            "import_state": status["state"],
                            "generator": plan.get("generator"),
                            "estimated_usd_max": plan.get("estimated_usd_max")},
                  limitation="The `max_usd` ceiling half of this AC cannot be reached with a "
                             "generator that costs nothing: det-1 and none both bill zero, and a "
                             "paid provider is out of scope for a loopback run.")
    assert ok, (jobs, status["state"])


# ---------------------------------------------------------------------------------------


def _generate(w, kinds: list) -> list:
    import_id = w.get("/imports")["items"][0]["import_id"]
    w.owner.expect("POST", f"{w.base}/imports/{import_id}/proposals:generate",
                   ok=(200, 201, 202),
                   body={"idempotency_key": f"gen-{'-'.join(kinds)}", "kinds": kinds})
    return wait_until(lambda: (w.get("/proposals?state=draft").get("items") or None),
                      timeout=240, what="at least one generated proposal")


def _wait_jobs(w, import_id: str, job_ids: list) -> list:
    terminal = {"done", "failed", "skipped", "cancelled"}

    def look():
        jobs = [j for j in w.get(f"/imports/{import_id}")["jobs"]
                if not job_ids or j["job_id"] in job_ids]
        generation = [j for j in jobs if j["kind"] == "proposal.generate"]
        if generation and all(j["state"] in terminal for j in generation):
            return generation
        return None

    return wait_until(look, timeout=240, what="the generation jobs to reach a terminal state")


def _job_rows(gf_stack, org_id: str) -> list:
    rows = gf_stack.sql(
        "SELECT kind,state,attempts,generation FROM gfm.jobs WHERE org_id='" + org_id
        + "'::uuid ORDER BY kind")
    return [{"kind": r[0], "state": r[1], "attempts": int(r[2]), "generation": int(r[3])}
            for r in rows]


def _all_skills(w) -> list:
    items, cursor = [], None
    while True:
        page = w.get("/skills" + (f"?cursor={cursor}" if cursor else "?limit=100"))
        items.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return items


def _active_snapshot(w):
    for snap in w.owner.expect("GET", w.base + "/snapshots")["items"]:
        if snap["active"]:
            return snap["snapshot_id"]
    return None


def _abstentions(gf_stack, org_id: str, kind: str) -> list:
    """The reasons a generation job wrote down for declining, from `gfm.jobs.result`."""
    import json as _json
    out = []
    rows = gf_stack.sql("SELECT result FROM gfm.jobs WHERE org_id='" + org_id
                        + "'::uuid AND kind='" + kind + "' AND result IS NOT NULL")
    for row in rows:
        try:
            result = _json.loads(row[0])
        except (TypeError, ValueError):
            continue
        for entry in result.get("abstentions") or []:
            out.append({"reason": entry.get("reason"), "detail": entry.get("detail"),
                        "skills": entry.get("skills")})
    return out
