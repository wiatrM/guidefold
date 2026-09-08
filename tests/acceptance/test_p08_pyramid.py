"""P08 — konsolidacja i piramida, end to end against the running stack.

One row, `P08-oneshot`: point `extract`'s server-side flow at a repository that contains the
planted pair, run it in one call, and check the two things the story promises.

  1. The shared procedure that lives in `atlas.geo` and `atlas.graph` becomes **one** element in
     their parent scope `atlas`, owned by the parent scope's owner, naming both sources in both
     directions (`derived_from` down, proposed `refines` up).
  2. The lookalike beside it — the same three opening steps, then the opposite instruction — is
     **declined with a stated reason**, not merged and not silently dropped.

The planted documents are committed in the fixture and marked there:
`examples/monorepo/docs/runbooks/README.md`, "Meridian fixture, planted for U2 AC5".
Consolidation reads skills, so this test walks the real product path — extract the documents,
approve the two extractions, then consolidate — rather than asserting on a hand-built catalog.

This is an R-level acceptance row on a dev fixture. It proves the rule holds end to end; it says
nothing about recall on a real repository, which needs a labelled corpus (eval-evidence-rules).
"""
from __future__ import annotations

import json

import pytest

from gf_acceptance_support import PASS, FAIL, make_git_tree, wait_until

pytestmark = pytest.mark.acceptance

# The three planted documents, and the scope each one belongs to under `guidefold.yaml`.
PLANTED = {
    "platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md": "atlas.geo",
    "platforms/atlas/graph/docs/runbooks/rotate-link-cache.md": "atlas.graph",
    "platforms/atlas/geo/docs/runbooks/rotate-legacy-tile-cache.md": "atlas.geo",
}
PARENT_SCOPE = "atlas"


def _import_id(w) -> str:
    return w.get("/imports")["items"][0]["import_id"]


def _wait_generation(w, import_id: str, job_ids: list) -> list:
    terminal = {"done", "failed", "skipped", "cancelled"}

    def look():
        jobs = [j for j in w.get(f"/imports/{import_id}")["jobs"]
                if not job_ids or j.get("job_id") in job_ids]
        generation = [j for j in jobs if j["kind"] == "proposal.generate"]
        if generation and all(j["state"] in terminal for j in generation):
            return generation
        return None

    return wait_until(look, timeout=300, what="the one-shot generation jobs to finish")


def _generate(w, import_id: str, kinds: list, key: str, profile: str = "one_shot") -> dict:
    body = {"idempotency_key": key, "kinds": kinds}
    if profile:
        body["profile"] = profile
    return w.owner.expect("POST", f"{w.base}/imports/{import_id}/proposals:generate",
                          ok=(200, 201, 202), body=body)


def _proposals(w, kind: str) -> list:
    return list(w.get(f"/proposals?kind={kind}").get("items") or [])


def _detail(w, proposal_id: str) -> dict:
    return w.get(f"/proposals/{proposal_id}")


def _approve(w, proposal_id: str, reason: str) -> dict:
    detail = _detail(w, proposal_id)
    return w.owner.expect("POST", f"{w.base}/proposals/{proposal_id}/decision", ok=(200,),
                          body={"idempotency_key": "p08-" + proposal_id, "decision": "approve",
                                "reason": reason,
                                "expected_revision": detail.get("expected_revision")},
                          headers={"Idempotency-Key": "p08-" + proposal_id})


def _abstentions(gf_stack, org_id: str) -> list:
    out = []
    rows = gf_stack.sql("SELECT result FROM gfm.jobs WHERE org_id='" + org_id
                        + "'::uuid AND kind='proposal.generate' AND result IS NOT NULL")
    for row in rows:
        try:
            result = json.loads(row[0])
        except (TypeError, ValueError):
            continue
        for entry in result.get("abstentions") or []:
            out.append({"reason": entry.get("reason"), "detail": entry.get("detail"),
                        "skills": entry.get("skills") or []})
    return out


@pytest.mark.acc("P08-oneshot")
def test_p08_one_shot_lifts_the_shared_procedure_and_declines_the_lookalike(
        fresh_org, report, gf_stack):
    """P08: one call plans every group; the planted pair becomes one shared element in the
    parent scope with both sources named; the lookalike is declined with a reason."""
    w = fresh_org("p08-pyramid")
    # `make_git_tree` copies the committed Meridian fixture and commits it, so the planted
    # documents arrive with it. Fail loudly rather than silently measuring a tree without them.
    w.commit = make_git_tree(w.tree)
    missing = [p for p in PLANTED if not (w.tree / p).exists()]
    assert not missing, f"the planted fixture is not in the tree: {missing}"

    w.cli.json(["import", "--wait", "--no-publish", "--json"], cwd=w.tree, check=False)
    import_id = _import_id(w)

    # The one-shot plan covers every group and shows its cost before anything runs.
    plan = w.get(f"/imports/{import_id}/plan?profile=one_shot")
    bounded = w.get(f"/imports/{import_id}/plan")
    profile_ok = plan.get("profile") == "one_shot" and bounded.get("profile") == "default"
    covered = len(plan.get("groups") or []) >= len(bounded.get("groups") or [])
    nothing_skipped = all(int(v or 0) == 0 for v in (plan.get("groups_skipped") or {}).values())
    budget_held = all(
        (plan.get("limits") or {}).get(k) == (bounded.get("limits") or {}).get(k)
        for k in ("max_usd", "max_calls", "max_tokens", "max_neighbours"))

    # Step 1: extract the planted documents into skill candidates and approve the two that
    # carry the shared procedure. Consolidation reads skills, so this is the real path.
    started = _generate(w, import_id, ["extraction"], "p08-extract")
    _wait_generation(w, import_id, started.get("job_ids") or [])
    extractions = _proposals(w, "extraction")
    # Match on the source document, not on the candidate's name: the recipe derives the name
    # from the document's title, and a test that guesses that name measures the slug function
    # rather than the pipeline.
    approved, approved_scopes, names = [], {}, {}
    for p in extractions:
        detail = _detail(w, p["proposal_id"])
        sources = [s.get("path") for s in (detail.get("sources") or []) if isinstance(s, dict)]
        planted = next((path for path in PLANTED if path in sources), None)
        if planted is None:
            continue
        _approve(w, p["proposal_id"], "planted fixture: approve the extracted runbook")
        approved.append(planted)
        approved_scopes[planted] = detail.get("scope") or PLANTED[planted]
        # The approved skill's name is the candidate directory, which is what its URN ends with.
        candidate_path = ((detail.get("candidate") or {}).get("path")
                          or detail.get("path") or "")
        names[planted] = candidate_path.rsplit("/", 2)[-2] if "/" in candidate_path else ""
    approved.sort()
    tile = names.get("platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md", "\0none")
    link = names.get("platforms/atlas/graph/docs/runbooks/rotate-link-cache.md", "\0none")
    legacy = names.get("platforms/atlas/geo/docs/runbooks/rotate-legacy-tile-cache.md", "\0none")

    # Step 2: one shared element out of the two sibling scopes, and a stated decline for the
    # lookalike beside them.
    started = _generate(w, import_id, ["consolidation"], "p08-consolidate")
    jobs = _wait_generation(w, import_id, started.get("job_ids") or [])
    consolidations = _proposals(w, "consolidation")

    lifted = []
    for p in consolidations:
        detail = _detail(w, p["proposal_id"])
        derived, refines = [], []
        for r in detail.get("relations") or []:
            if r.get("type") == "derived_from" and r.get("to"):
                derived.append(r["to"])
            if r.get("type") == "refines" and r.get("from"):
                refines.append(r["from"])
        ends = {d.rsplit(":", 1)[-1] for d in derived}
        if tile in ends and link in ends and legacy not in ends:
            lifted.append({"proposal_id": p["proposal_id"], "scope": detail.get("scope"),
                           "owner": detail.get("owner"), "path": detail.get("path"),
                           "derived_from": sorted(derived), "refines_from": sorted(refines)})

    reasons = _abstentions(gf_stack, w.org_id)
    declined = [r for r in reasons
                if any(s.rsplit(":", 1)[-1] == legacy for s in r["skills"])]

    one_element = len(lifted) == 1
    raised = one_element and lifted[0]["scope"] == PARENT_SCOPE
    both_ways = one_element and len(lifted[0]["derived_from"]) == 2 \
        and len(lifted[0]["refines_from"]) == 2
    lookalike_declined = bool(declined) and all(r["reason"] for r in declined)

    ok = (profile_ok and covered and nothing_skipped and budget_held
          and len(approved) == len(PLANTED) and one_element and raised and both_ways
          and lookalike_declined)

    report.record("P08-oneshot",
                  prd_ac="U2 AC5 (consolidation or a stated abstention) + owner decision "
                         "2026-09-07 in PRODUCT-PIVOT §5 U2 (sibling scopes, one_shot)",
                  scenario="import the Meridian fixture with the planted pair, run the one-shot "
                           "plan, approve the extracted runbooks, then consolidate: exactly one "
                           "shared element in the parent scope with both sources in both "
                           "directions, and a stated decline for the lookalike",
                  command_or_endpoint="GET {repo_base}/imports/{id}/plan?profile=one_shot; "
                                      "POST {repo_base}/imports/{id}/proposals:generate "
                                      "{profile:one_shot}; POST {repo_base}/proposals/{id}/decision",
                  data_origin="examples/monorepo, planted pair (docs/runbooks/README.md, "
                              "\"Meridian fixture, planted for U2 AC5\"), generator det-1 "
                              "(no network, no model)",
                  result=PASS if ok else FAIL,
                  evidence={"profile": plan.get("profile"),
                            "one_shot_groups": len(plan.get("groups") or []),
                            "default_groups": len(bounded.get("groups") or []),
                            "groups_skipped": plan.get("groups_skipped"),
                            "budget_unchanged": budget_held,
                            "approved_extractions": approved,
                            "approved_scopes": approved_scopes,
                            "approved_names": names,
                            "consolidations": lifted,
                            "job_states": [{"state": j["state"], "error": j.get("error")}
                                           for j in jobs],
                            "declined_lookalike": declined},
                  limitation="R-level on the Meridian dev fixture with a planted pair. It proves "
                             "the rule end to end — sibling scopes consolidate into their parent, "
                             "a contradicting lookalike does not — and says nothing about recall "
                             "or precision on a real repository, which needs a labelled corpus "
                             "(eval-evidence-rules). The generator is det-1: no model was called, "
                             "so the cost is zero by construction and is not evidence about a "
                             "provider recipe.")

    assert ok, {"profile_ok": profile_ok, "covered": covered,
                "nothing_skipped": nothing_skipped, "budget_held": budget_held,
                "approved": approved, "names": names, "lifted": lifted,
                "consolidations_seen": len(consolidations), "reasons": reasons[:8],
                "declined": declined}
