"""U1 — what leaves the machine, and what the server does with it.

Every row here is measured on a throwaway organisation with its own git work tree, so a test
that deliberately breaks a repository cannot change what another test reads.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import urllib.parse
from pathlib import Path

import pytest

from gf_acceptance_support import (PASS, FAIL, NOT_MEASURED, authored_skills, commit_all,
                                   make_git_tree, percentile, set_metadata, sha256_bytes,
                                   wait_until)

pytestmark = pytest.mark.acceptance


@pytest.mark.acc("U1-1")
def test_u1_1_scan_is_offline_and_is_exactly_what_import_sends(fresh_org, report, socket_guard):
    """U1-1: `scan --dry-run` opens no socket, and the manifest it prints is the one the
    server ends up holding — same paths, same digests, same commit."""
    w = fresh_org("u1-scan")
    make_git_tree(w.tree)

    first = w.cli.json(["scan", "--dry-run", "--json"], cwd=w.tree, PYTHONPATH=str(socket_guard))
    second = w.cli.json(["scan", "--dry-run", "--json"], cwd=w.tree, PYTHONPATH=str(socket_guard))
    assert first == second, "two scans of the same commit must be byte-identical"

    imported = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    status = w.get(f"/imports/{imported['import_id']}")

    scanned = {(f["path"], f["sha256"]) for f in first["files"]}
    served = {(f["path"], f["sha256"]) for f in status["files"] if f["status"] != "omitted"}
    omitted = [{"path": f["path"], "reason": f.get("reason")}
               for f in status["files"] if f["status"] == "omitted"]
    # Every file the server holds came from the manifest, and every file the manifest offered
    # is either held or omitted with a stated reason. Nothing appears from nowhere and nothing
    # disappears silently.
    assert served <= scanned, sorted(served - scanned)[:5]
    assert served | {(f["path"], sha) for f in omitted for sha in
                     [next(x["sha256"] for x in first["files"] if x["path"] == f["path"])]} == scanned

    report.record("U1-1", prd_ac="U1 AC1 (scan --dry-run is offline)",
                  scenario="`scan --dry-run --json` under a sitecustomize socket guard, twice, then "
                           "`import --wait`; the manifest is compared file-by-file with what the API holds",
                  command_or_endpoint="guidefold scan --dry-run --json; guidefold import --wait; "
                                      "GET {repo_base}/imports/{import_id}",
                  data_origin="examples/monorepo in a fresh git work tree",
                  result=PASS,
                  evidence={"files": len(first["files"]), "commit": first["commit"],
                            "excluded": len(first["excluded"]),
                            "omitted_by_the_server": omitted,
                            "import_id": imported["import_id"],
                            "manifest_digest": imported["manifest_digest"],
                            "socket_guard": "socket.socket.connect/create_connection raise"},
                  limitation="Proves no connect() call, not the absence of a side channel such as DNS "
                             "resolution in another process.")


@pytest.mark.acc("U1-2")
def test_u1_2_the_fixture_is_detected_whole(fresh_org, report, bring_up):
    """U1-2: 27 skills, their scopes, and the requires/refines relations between them."""
    w = fresh_org("u1-inv")
    bring_up(w, publish=False)

    skills = _all_skills(w)
    relations = w.get("/map/relations?limit=200")
    kinds = {}
    for rel in relations["items"]:
        kinds[rel["type"]] = kinds.get(rel["type"], 0) + 1

    expected = authored_skills(w.tree)
    assert len(skills) == len(expected), (len(skills), len(expected))
    assert {s["path"] for s in skills} == set(expected)
    scopes = sorted({s["scope"] for s in skills})
    assert "_root" in scopes

    report.record("U1-2", prd_ac="U1 AC2 (fixture detection)",
                  scenario="import the fixture, then read the catalog and the declared relations",
                  command_or_endpoint="GET {repo_base}/skills; GET {repo_base}/map/relations",
                  data_origin="examples/monorepo (27 SKILL.md files, one of them a "
                              "generated hierarchy index the builder deliberately skips)",
                  result=PASS,
                  evidence={"skills": len(skills),
                            "skill_md_files_on_disk": len(list(w.tree.rglob("SKILL.md"))),
                            "generated_cards_excluded":
                                len(list(w.tree.rglob("SKILL.md"))) - len(expected),
                            "scopes": scopes,
                            "relation_types": kinds,
                            "owners": sorted({s["owner"] for s in skills})[:10]},
                  limitation="Counts declared structure; says nothing about routing quality.")


@pytest.mark.acc("U1-3")
def test_u1_3_secrets_ignored_files_and_escaping_symlinks_never_leave(fresh_org, report,
                                                                     socket_guard, gf_stack):
    """U1-3: a key, an ignored directory and a symlink out of the tree are excluded by the
    scan, and the server refuses the blob even when it is offered directly."""
    w = fresh_org("u1-secrets")
    make_git_tree(w.tree)
    secret_bytes = b"-----BEGIN RSA PRIVATE KEY-----\nnot-a-real-key\n-----END RSA PRIVATE KEY-----\n"
    (w.tree / ".agents/skills/adr-process/deploy.pem").write_bytes(secret_bytes)
    (w.tree / ".agents/skills/adr-process/innocent.md").write_bytes(secret_bytes)
    outside = w.tree.parent / f"outside-{w.org}"
    outside.mkdir(exist_ok=True)
    (outside / "leak.md").write_text("secrets that live outside the repository\n")
    os.symlink(outside, w.tree / ".agents/skills/adr-process/references")
    ignored = w.tree / ".agents/skills/adr-process/node_modules"
    ignored.mkdir(parents=True, exist_ok=True)
    (ignored / "vendor.md").write_text("vendored\n")
    commit_all(w.tree, "add a key, an escaping symlink and an ignored directory")

    manifest = w.cli.json(["scan", "--dry-run", "--json"], cwd=w.tree, PYTHONPATH=str(socket_guard))
    reasons = {e["path"]: e["reason"] for e in manifest["excluded"]}
    offered = {f["path"] for f in manifest["files"]}
    assert not any(p.endswith("deploy.pem") for p in offered), offered
    assert not any("node_modules" in p for p in offered), offered
    assert not any(p.endswith("leak.md") for p in offered), offered

    imported = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    secret_digest = sha256_bytes(secret_bytes)
    # The real bytes, correctly hashed: the refusal has to be "this blob is not in the
    # manifest", not "your digest is wrong", or the check proves nothing about exclusion.
    status_code, body, _ = w.owner.request(
        "PUT", f"{w.base}/imports/{imported['import_id']}/blobs/{secret_digest}",
        raw=secret_bytes, headers={"Content-Type": "application/octet-stream"})
    stored = gf_stack.sql("SELECT count(*) FROM gfm.blobs WHERE sha256='" + secret_digest + "'")

    assert status_code in (400, 403, 404, 409, 422), (status_code, body)
    assert body.get("error") in ("blob_not_in_manifest", "import_already_finalized",
                                "invalid_request", "not_found"), body
    assert int(stored[0][0]) == 0, "the key's bytes reached blob storage"

    report.record("U1-3", prd_ac="U1 AC3 (secrets, ignored paths, symlinks)",
                  scenario="a PEM by name, a PEM by content under an innocent name, an ignored "
                           "directory and a symlink escaping the tree; then the same key offered "
                           "straight to the blob endpoint",
                  command_or_endpoint="guidefold scan --dry-run --json; PUT {repo_base}/imports/"
                                      "{id}/blobs/{sha256}; SELECT count(*) FROM gfm.blobs",
                  data_origin="examples/monorepo plus deliberately planted files",
                  result=PASS,
                  evidence={"excluded_reasons": sorted(set(reasons.values())),
                            "secret_digest": secret_digest,
                            "blob_upload_status": status_code,
                            "blob_upload_error": body.get("error"),
                            "rows_in_gfm_blobs": int(stored[0][0])},
                  limitation="Covers the patterns this scan implements; it is not a general "
                             "secret scanner.")


@pytest.mark.acc("U1-4")
def test_u1_4_the_same_commit_produces_the_same_import(fresh_org, report):
    """U1-4: determinism and zero new blobs on the second run."""
    w = fresh_org("u1-determinism")
    make_git_tree(w.tree)
    first = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    second = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)

    assert second["manifest_digest"] == first["manifest_digest"], (first, second)
    assert second["import_id"] == first["import_id"], "the same tree must reuse its import"
    assert second["new_blobs"] == 0, second
    assert second["uploaded_blobs"] == 0, second

    report.record("U1-4", prd_ac="U1 AC4 (determinism, zero new blobs)",
                  scenario="import the same commit twice; compare manifest digest, import id and "
                           "the new/reused blob split",
                  command_or_endpoint="guidefold import --wait --json; guidefold sync --wait --json",
                  data_origin="examples/monorepo in a fresh git work tree",
                  result=PASS,
                  evidence={"manifest_digest": first["manifest_digest"],
                            "import_id": first["import_id"],
                            "second_new_blobs": second["new_blobs"],
                            "second_reused_blobs": second["reused_blobs"]},
                  limitation="One machine, one clock; not a cross-platform determinism claim.")


@pytest.mark.acc("U1-5")
def test_u1_5_an_interrupted_upload_resumes_into_one_import_and_a_rename_keeps_its_identity(
        fresh_org, report):
    """U1-5: an import created and only partly uploaded is *resumed*, not duplicated; and a
    declared alias keeps a moved skill's identity."""
    w = fresh_org("u1-resume")
    make_git_tree(w.tree)

    # Start the import the way the CLI does, upload exactly one blob, then walk away.
    manifest = w.cli.json(["scan", "--json"], cwd=w.tree)
    created = w.owner.expect("POST", w.base + "/imports", ok=(200, 201),
                             body={"idempotency_key": "u1-5-import", "manifest": manifest})
    interrupted_id = created["import_id"]
    missing = created["missing_blobs"] if "missing_blobs" in created else created.get("missing", [])
    first_sha = missing[0]
    path = next(f["path"] for f in manifest["files"] if f["sha256"] == first_sha)
    uploaded = w.owner.request("PUT", f"{w.base}/imports/{interrupted_id}/blobs/{first_sha}",
                               raw=(w.tree / path).read_bytes())[0]
    assert uploaded in (200, 201), uploaded

    resumed = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    assert resumed["import_id"] == interrupted_id, (resumed, interrupted_id)
    imports = w.get("/imports")
    assert len(imports["items"]) == 1, "an interrupted upload must not leave a second import"

    # A rename with a declared alias keeps the skill id.
    before = {s["path"]: s["skill_id"] for s in _all_skills(w)}
    old_dir = w.tree / ".agents/skills/adr-process"
    new_dir = w.tree / ".agents/skills/adr-process-v2"
    old_id = before[".agents/skills/adr-process/SKILL.md"]
    shutil.move(str(old_dir), str(new_dir))
    yaml_path = w.tree / "guidefold.yaml"
    yaml_path.write_text(yaml_path.read_text() +
                         "\nimport:\n  aliases:\n"
                         "    - from: .agents/skills/adr-process/SKILL.md\n"
                         "      to: .agents/skills/adr-process-v2/SKILL.md\n")
    commit_all(w.tree, "rename one skill directory and declare the alias")
    renamed = w.cli.json(["sync", "--wait", "--json"], cwd=w.tree)
    after = {s["path"]: s["skill_id"] for s in _all_skills(w)}
    new_id = after.get(".agents/skills/adr-process-v2/SKILL.md")

    report.record("U1-5", prd_ac="U1 AC5 (interrupt + retry, rename)",
                  scenario="create an import and upload one blob, then let the CLI finish it; "
                           "then move a skill directory with a declared alias and re-sync",
                  command_or_endpoint="POST {repo_base}/imports; PUT .../blobs/{sha}; "
                                      "guidefold import --wait; guidefold sync --wait",
                  data_origin="examples/monorepo in a fresh git work tree",
                  result=PASS if new_id == old_id else "fail",
                  evidence={"interrupted_import_id": interrupted_id,
                            "resumed_import_id": resumed["import_id"],
                            "imports_for_this_repo": len(imports["items"]),
                            "partial_blob_path": path,
                            "renamed_import_id": renamed["import_id"],
                            "skill_id_before": old_id, "skill_id_after": new_id},
                  limitation="The interruption is modelled at the protocol level (an import left "
                             "with unuploaded blobs), not by killing the process mid-socket.")
    assert new_id == old_id, (old_id, new_id)


@pytest.mark.slow
@pytest.mark.acc("U1-6")
def test_u1_6_ten_thousand_paths_scan_inside_the_budget(fresh_org, report, scratch, socket_guard):
    """U1-6: p95 of `scan` over a 10 000-path tree. Local hardware, not the pilot box."""
    w = fresh_org("u1-scale")
    tree = scratch / "scale-10k"
    if not (tree / "guidefold.yaml").is_file():
        _build_scale_tree(tree, 10_000)
    runs = []
    for _ in range(20):
        start = time.monotonic()
        w.cli.run(["scan", "--json"], cwd=tree, PYTHONPATH=str(socket_guard))
        runs.append(time.monotonic() - start)
    p95 = percentile(runs, 95)

    report.record("U1-6", prd_ac="U1 AC6 (10 000 paths, p95 <= 10 s)",
                  scenario="20 `scan --json` runs over a generated 10 000-path tree",
                  command_or_endpoint="guidefold scan --json",
                  data_origin="synthetic tree generated for this run (not the Meridian fixture)",
                  result=PASS if p95 <= 10.0 else "fail",
                  evidence={"runs": len(runs), "p95_s": round(p95, 3),
                            "median_s": round(percentile(runs, 50), 3),
                            "max_s": round(max(runs), 3), "paths": 10_000},
                  limitation="Local measurement on this developer machine's filesystem, warm page "
                             "cache after the first run. Not the pilot hardware and not an SLA.")
    assert p95 <= 10.0, runs


@pytest.mark.acc("U1-7")
def test_u1_7_declared_resources_are_recorded_and_a_missing_required_one_blocks_publication(
        fresh_org, report):
    """U1-7: `references`/`scripts` become resource rows; a required one that is absent fails
    the publication instead of shipping a broken package."""
    w = fresh_org("u1-resources")
    make_git_tree(w.tree)
    package = w.tree / ".agents/skills/adr-process"
    skill = package / "SKILL.md"
    (package / "references").mkdir(exist_ok=True)
    (package / "references/template.md").write_text("# ADR template\n")
    # `domain.ResourcesFor` only treats a declared path as a *package* resource when the scan
    # carried something from that directory -- otherwise `metadata.references` pointing at a
    # repository file would invent a path and block publication on its absence. So the package
    # needs a real `scripts/` directory before an absent script inside it counts.
    (package / "scripts").mkdir(exist_ok=True)
    (package / "scripts/present.sh").write_text("#!/bin/sh\necho present\n")
    set_metadata(skill, references=["references/template.md"],
                 scripts=["scripts/present.sh", "scripts/absent.sh"])
    commit_all(w.tree, "declare one present reference, one present and one absent script")

    imported = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
    skills = {s["path"]: s for s in _all_skills(w)}
    entry = skills[".agents/skills/adr-process/SKILL.md"]
    detail = w.get(f"/skills/{_seg(entry['skill_id'])}")
    resources = detail.get("resources") or []

    w.owner.expect("POST", w.base + "/publish", ok=(200,),
                   body={"idempotency_key": "u1-7-publish", "import_id": imported["import_id"]})
    snapshot = wait_until(
        lambda: next((s for s in w.owner.expect("GET", w.base + "/snapshots")["items"]
                      if s["state"] in ("active", "failed")), None),
        timeout=180, what="a terminal publication state")

    findings = (snapshot.get("validation") or {}).get("findings") or []
    codes = sorted({f.get("code") for f in findings})

    report.record("U1-7", prd_ac="U1 AC7 (package resources)",
                  scenario="a skill declaring one present reference and one absent required "
                           "script: read the resource rows, then publish",
                  command_or_endpoint="GET {repo_base}/skills/{skill_id}; POST {repo_base}/publish",
                  data_origin="examples/monorepo with an edited SKILL.md",
                  result=PASS if snapshot["state"] == "failed" else "fail",
                  evidence={"resources": [{k: r.get(k) for k in ("path", "required", "available")}
                                          for r in resources],
                            "publication_state": snapshot["state"],
                            "validation_codes": codes,
                            "error": snapshot.get("error")},
                  limitation="One missing required resource; not an exhaustive package-validation "
                             "matrix.")
    assert snapshot["state"] == "failed", snapshot
    assert any("resource" in (c or "") for c in codes) or "resource" in (snapshot.get("error") or ""), \
        (codes, snapshot.get("error"))


# ---------------------------------------------------------------------------------------


def _seg(skill_id: str) -> str:
    return urllib.parse.quote(skill_id, safe="")


def _all_skills(w) -> list:
    items, cursor = [], None
    while True:
        page = w.get("/skills" + (f"?cursor={cursor}" if cursor else "?limit=100"))
        items.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return items


def _build_scale_tree(tree: Path, paths: int) -> None:
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    (tree / "guidefold.yaml").write_text(
        "publisher: scale\nnodes:\n  _root:\n    paths: [\"**\"]\n    owner: scale-team\n")
    per_dir = 100
    for i in range(paths // per_dir):
        directory = tree / "services" / f"svc{i:04d}"
        directory.mkdir(parents=True)
        for j in range(per_dir):
            (directory / f"doc{j:03d}.md").write_text(f"# doc {i}/{j}\n\nbody\n")
    import subprocess
    env = dict(os.environ, GIT_AUTHOR_NAME="scale", GIT_AUTHOR_EMAIL="s@e.test",
               GIT_COMMITTER_NAME="scale", GIT_COMMITTER_EMAIL="s@e.test")
    for argv in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                 ["git", "commit", "-q", "-m", "scale"]):
        subprocess.run(argv, cwd=str(tree), env=env, check=True, capture_output=True)
