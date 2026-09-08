"""`guidefold report --base <ref>` — the pre-merge change report (P12 / PRODUCT-PIVOT §10 U7).

Every test builds a real, throwaway git repo in `tmp_path` (`git init` + commits) and runs the
CLI as a subprocess, because the command's whole job is to compare a *git ref* against the
working tree: mocking git away would test something else. Nothing here touches the network, GCP
or the developer's caches (`run_cli` pins `GUIDEFOLD_CACHE` into `tmp_path`).

Severity doctrine under test, straight from U7: "Struktura blokuje; przypuszczalna kolizja
ostrzega" and "Test retrievalu nie dowodzi wykonania procedury" — a cycle / missing dependency /
missing declared resource / invalid card fails the run; a trigger collision and every retrieval
example only warn.
"""
import json
import os
import subprocess

import pytest

from _helpers import write_guidefold_yaml, write_skill


# --------------------------------------------------------------------------------- git plumbing
def _git(repo, *args):
    out = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Guidefold Test",
         "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
         "-c", "core.autocrlf=false", "-c", "gc.auto=0", *args],
        capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
    assert out.returncode == 0, f"git {' '.join(args)} failed:\n{out.stdout}\n{out.stderr}"
    return out.stdout.strip()


def _init_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    return root


def _commit(root, message="change"):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _nodes():
    return {
        "_root": {"paths": ["**"], "owner": "platform"},
        "teamA": {"paths": ["teamA/**"], "owner": "team-a"},
        "teamA.sub": {"paths": ["teamA/sub/**"], "owner": "team-a-sub"},
    }


def _base_repo(tmp_path, name="repo"):
    """A committed two-skill monorepo: `billing-basics` and `payouts-runbook`, both in `_root`."""
    root = _init_repo(tmp_path / name)
    write_guidefold_yaml(root, nodes=_nodes())
    write_skill(
        root / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[acme] How acme handles billing and invoices. Use when touching invoicing code.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "triggers": "billing invoice, invoice run"},
        body="# Billing basics\n\nInvoices are generated nightly from the billing ledger.\n")
    write_skill(
        root / ".agents" / "skills" / "payouts-runbook",
        name="payouts-runbook",
        description="[acme] Payout runbook for the acme platform. Use when a payout batch fails.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "triggers": "payout batch, payout failure"},
        body="# Payouts\n\nRe-run the failed payout batch from the payouts console.\n")
    base = _commit(root, "base")
    return root, base


def _run_report(run_cli, root, tmp_path, base, *extra, prefix="r"):
    """Run `guidefold report`, always writing both artifacts OUTSIDE the repo so the run never
    dirties the tree it is reporting on. Returns (completed_process, json_path, md_path)."""
    jpath = tmp_path / f"{prefix}.json"
    mpath = tmp_path / f"{prefix}.md"
    proc = run_cli(["report", "--base", base, "--json", str(jpath), "--markdown", str(mpath),
                    *extra], cwd=root)
    return proc, jpath, mpath


def _payload(jpath):
    return json.loads(jpath.read_text())


def _codes(payload, severity=None):
    return sorted(f["code"] for f in payload["findings"]
                  if severity is None or f["severity"] == severity)


# --------------------------------------------------------------------------------- the AC cases
def test_clean_tree_reports_no_findings_and_exits_zero(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    proc, jpath, mpath = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    p = _payload(jpath)
    assert p["schema"] == "guidefold-change-report-v1"
    assert p["summary"]["errors"] == 0
    assert p["changes"]["skills"] == {"added": [], "removed": [], "renamed": [], "changed": []}
    assert p["retrieval"] is None
    assert "generated_at" not in p                     # --reproducible is the default
    assert mpath.read_text().splitlines()[0] == "<!-- guidefold:change-report -->"


def test_requires_cycle_introduced_in_head_is_a_blocking_graph_cycle(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    # head introduces a two-node `requires` cycle that the base commit does not have
    write_skill(
        root / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[acme] How acme handles billing and invoices. Use when touching invoicing code.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "requires": "urn:skill:acme:_root:payouts-runbook"},
        body="# Billing basics\n\nInvoices are generated nightly.\n")
    write_skill(
        root / ".agents" / "skills" / "payouts-runbook",
        name="payouts-runbook",
        description="[acme] Payout runbook for the acme platform. Use when a payout batch fails.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "requires": "urn:skill:acme:_root:billing-basics"},
        body="# Payouts\n\nRe-run the failed payout batch.\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    p = _payload(jpath)
    cycles = [f for f in p["findings"] if f["code"] == "graph_cycle"]
    assert cycles, p["findings"]
    assert all(f["severity"] == "error" for f in cycles)
    # the path is printed, not just "there is a cycle"
    path = cycles[0]["details"]["path"]
    assert len(path) >= 3 and path[0] == path[-1]
    assert {"urn:skill:acme:_root:billing-basics", "urn:skill:acme:_root:payouts-runbook"} <= set(path)
    assert "requires cycle:" in cycles[0]["message"]
    assert " -> " in cycles[0]["message"]


def test_deleted_required_resource_file_is_a_blocking_error(run_cli, tmp_path):
    root = _init_repo(tmp_path / "repo")
    write_guidefold_yaml(root, nodes=_nodes())
    (root / "docs").mkdir()
    (root / "docs" / "runbook.md").write_text("# Runbook\n\nRestart the payout worker.\n")
    write_skill(
        root / ".agents" / "skills" / "payouts-runbook",
        name="payouts-runbook",
        description="[acme] Payout runbook. Use when a payout batch fails.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "references": "docs/runbook.md"},
        body="# Payouts\n\nSee the runbook.\n")
    base = _commit(root, "base")

    (root / "docs" / "runbook.md").unlink()            # head deletes the declared resource

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    p = _payload(jpath)
    missing = [f for f in p["findings"] if f["code"] == "missing_required_resource"]
    assert len(missing) == 1, p["findings"]
    assert missing[0]["severity"] == "error"
    assert missing[0]["skill_id"] == "urn:skill:acme:_root:payouts-runbook"
    assert missing[0]["details"]["entry"] == "docs/runbook.md"
    # and the same file shows up in the deterministic diff as a removed resource
    assert {"skill_id": "urn:skill:acme:_root:payouts-runbook", "path": "docs/runbook.md"} \
        in p["changes"]["resources"]["removed"]


def test_broken_frontmatter_is_an_invalid_card_error(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    broken = root / ".agents" / "skills" / "broken-card"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text(
        '---\nname: broken-card\ndescription: "[acme] unterminated quote\nmetadata:\n'
        '  scope: _root\n---\n# Broken\n')

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    p = _payload(jpath)
    invalid = [f for f in p["findings"] if f["code"] == "invalid_card"]
    assert len(invalid) == 1, p["findings"]
    assert invalid[0]["severity"] == "error"
    assert invalid[0]["details"]["path"] == ".agents/skills/broken-card/SKILL.md"
    assert "frontmatter does not parse" in invalid[0]["message"]
    # the broken card never enters the corpus, and the other two skills are still compared
    assert p["summary"]["skills_head"] == 2


def test_missing_frontmatter_block_is_an_invalid_card_error(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    nocard = root / ".agents" / "skills" / "no-card"
    nocard.mkdir(parents=True)
    (nocard / "SKILL.md").write_text("# Just a heading, no frontmatter at all\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    p = _payload(jpath)
    invalid = [f for f in p["findings"] if f["code"] == "invalid_card"]
    assert any("no YAML frontmatter block" in f["message"] for f in invalid), invalid


def test_rename_declared_in_import_aliases_is_a_rename_not_add_plus_remove(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    old = root / ".agents" / "skills" / "billing-basics"
    (old / "SKILL.md").unlink()
    old.rmdir()
    # moved into teamA AND edited, so only the alias — never an identical body sha — can match it
    write_skill(
        root / "teamA" / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[teamA] How team A handles billing and invoices. Use when touching invoicing.",
        metadata={"scope": "teamA", "owner": "team-a", "status": "active",
                  "triggers": "billing invoice, invoice run"},
        body="# Billing basics\n\nRewritten body: invoices come from the ledger service.\n")
    cfg_text = (root / "guidefold.yaml").read_text()
    (root / "guidefold.yaml").write_text(
        cfg_text
        + "import:\n  aliases:\n"
          "    - from: .agents/skills/billing-basics\n"
          "      to: teamA/.agents/skills/billing-basics\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    p = _payload(jpath)
    renamed = p["changes"]["skills"]["renamed"]
    assert len(renamed) == 1, p["changes"]["skills"]
    assert renamed[0]["from"] == "urn:skill:acme:_root:billing-basics"
    assert renamed[0]["to"] == "urn:skill:acme:teamA:billing-basics"
    assert renamed[0]["reason"] == "alias"
    assert p["changes"]["skills"]["added"] == []
    assert p["changes"]["skills"]["removed"] == []
    assert {f["field"] for f in renamed[0]["fields"]} >= {"scope", "owner", "body_sha256"}
    # a scope move is a warning, never a block
    scope_changes = [f for f in p["findings"] if f["code"] == "scope_changed"]
    assert scope_changes and all(f["severity"] == "warning" for f in scope_changes)


def test_rename_with_an_identical_body_is_detected_without_an_alias(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    body = "# Billing basics\n\nInvoices are generated nightly from the billing ledger.\n"
    old = root / ".agents" / "skills" / "billing-basics"
    (old / "SKILL.md").unlink()
    old.rmdir()
    write_skill(
        root / "teamA" / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[teamA] How acme handles billing and invoices. Use when touching invoicing code.",
        metadata={"scope": "teamA", "owner": "team-a", "status": "active",
                  "triggers": "billing invoice, invoice run"},
        body=body)

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    p = _payload(jpath)
    renamed = p["changes"]["skills"]["renamed"]
    assert len(renamed) == 1, p["changes"]["skills"]
    assert renamed[0]["reason"] == "identical_body_sha256"
    assert renamed[0]["to"] == "urn:skill:acme:teamA:billing-basics"


def test_probable_trigger_collision_only_warns_and_the_run_still_passes(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    write_skill(
        root / ".agents" / "skills" / "payouts-runbook",
        name="payouts-runbook",
        description="[acme] Payout runbook for the acme platform. Use when a payout batch fails.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "triggers": "billing invoice, payout failure"},   # steals a sibling's trigger
        body="# Payouts\n\nRe-run the failed payout batch from the payouts console.\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 0, proc.stdout + proc.stderr    # a collision never blocks
    p = _payload(jpath)
    collisions = [f for f in p["findings"] if f["code"] == "trigger_collision"]
    assert len(collisions) == 1, p["findings"]
    assert collisions[0]["severity"] == "warning"
    assert collisions[0]["details"]["shared_triggers"] == ["billing invoice"]
    assert collisions[0]["details"]["node"] == "_root"
    assert "billing invoice" in collisions[0]["message"]
    # ... unless the operator explicitly opts into blocking on warnings
    proc2, _, _ = _run_report(run_cli, root, tmp_path, base, "--fail-on", "any", prefix="any")
    assert proc2.returncode == 2


def test_fail_on_none_never_changes_the_exit_code(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    nocard = root / ".agents" / "skills" / "no-card"
    nocard.mkdir(parents=True)
    (nocard / "SKILL.md").write_text("# no frontmatter\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base, "--fail-on", "none")
    assert proc.returncode == 0
    assert _payload(jpath)["summary"]["errors"] >= 1


def test_retrieval_example_diff_reports_both_selected_sets_and_the_changed_list(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    queries = tmp_path / "queries.yaml"
    queries.write_text(
        "version: 1\ncategory: smoke\ncases:\n"
        "  - id: q-billing\n"
        "    query: billing invoice run\n"
        "    node: _root\n"
        "    relevant:\n"
        "      - urn: urn:skill:acme:_root:billing-basics\n"
        "        grade: 3\n"
        "  - id: q-payout\n"
        "    query: payout batch failure\n"
        "    node: _root\n"
        "    relevant:\n"
        "      - urn: urn:skill:acme:_root:payouts-runbook\n"
        "        grade: 3\n")
    # head adds a third skill that competes for the billing query
    write_skill(
        root / ".agents" / "skills" / "invoice-tax",
        name="invoice-tax",
        description="[acme] Tax rules applied to every billing invoice run. Use when invoice tax changes.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "triggers": "billing invoice, invoice tax"},
        body="# Invoice tax\n\nTax is applied to each billing invoice during the invoice run.\n")

    proc, jpath, mpath = _run_report(run_cli, root, tmp_path, base, "--queries", str(queries))
    assert proc.returncode == 0, proc.stdout + proc.stderr    # retrieval never blocks on its own
    p = _payload(jpath)
    r = p["retrieval"]
    assert r["mode"] == "golden"
    assert r["note"] == "retrieval example, not procedure execution"
    assert r["n_queries"] == 2
    ids = [q["id"] for q in r["per_query"]]
    assert ids == ["q-billing", "q-payout"]
    for q in r["per_query"]:
        assert isinstance(q["base_selected"], list) and isinstance(q["head_selected"], list)
        assert "hit@1" in q and "all_required@4" in q
    billing = next(q for q in r["per_query"] if q["id"] == "q-billing")
    assert "urn:skill:acme:_root:invoice-tax" in billing["head_selected"]
    assert "urn:skill:acme:_root:invoice-tax" not in billing["base_selected"]
    # a set change and a same-set reorder are reported apart: U7 asks for "the selected set
    # changed", and injection order is a presentation decision, not a ranking signal
    assert billing["changed"] is True
    assert billing["set_changed"] is True and billing["order_changed"] is False
    assert r["changed_query_ids"] == ["q-billing"]
    assert r["reordered_query_ids"] == [] and r["n_reordered"] == 0
    assert set(r["deltas"]) == {"hit@1", "all_required@4"}
    assert r["deltas"]["hit@1"]["n"] == 2
    # ... and it is reported as a warning, never an error
    retr = [f for f in p["findings"] if f["code"].startswith("retrieval_")]
    assert retr and all(f["severity"] == "warning" for f in retr)
    md = mpath.read_text()
    assert "## Retrieval examples" in md
    assert "retrieval example, not procedure execution" in md.lower()


def test_queries_default_to_guidefold_yaml_eval_queries(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    queries = root / "golden.yaml"
    queries.write_text(
        "version: 1\ncategory: smoke\ncases:\n"
        "  - id: q1\n    query: payout batch failure\n    node: _root\n")
    cfg_text = (root / "guidefold.yaml").read_text()
    (root / "guidefold.yaml").write_text(cfg_text + "eval:\n  queries: golden.yaml\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _payload(jpath)["retrieval"]["n_queries"] == 1


def test_two_runs_over_the_same_commits_produce_identical_bytes(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    queries = tmp_path / "queries.yaml"
    queries.write_text(
        "version: 1\ncategory: smoke\ncases:\n"
        "  - id: q1\n    query: billing invoice run\n    node: _root\n")
    write_skill(
        root / ".agents" / "skills" / "invoice-tax",
        name="invoice-tax",
        description="[acme] Tax rules applied to every billing invoice run. Use when invoice tax changes.",
        metadata={"scope": "_root", "owner": "platform", "status": "active",
                  "triggers": "billing invoice"},
        body="# Invoice tax\n\nTax is applied during the invoice run.\n")

    p1, j1, m1 = _run_report(run_cli, root, tmp_path, base, "--queries", str(queries), prefix="a")
    p2, j2, m2 = _run_report(run_cli, root, tmp_path, base, "--queries", str(queries), prefix="b")
    assert p1.returncode == p2.returncode == 0
    assert j1.read_bytes() == j2.read_bytes()
    assert m1.read_bytes() == m2.read_bytes()
    assert "generated_at" not in _payload(j1)

    p3, j3, _ = _run_report(run_cli, root, tmp_path, base, "--queries", str(queries),
                            "--no-reproducible", prefix="c")
    assert "generated_at" in _payload(j3)          # opt-in only, and it is the only clock read


def test_markdown_is_a_pr_comment_under_two_hundred_lines(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    for i in range(40):
        write_skill(
            root / ".agents" / "skills" / f"extra-{i:02d}",
            name=f"extra-{i:02d}",
            description=f"[acme] Extra skill {i} for the report size guard. Use when nothing else fits.",
            metadata={"scope": "_root", "owner": "platform", "status": "active",
                      "triggers": "billing invoice"},
            body=f"# Extra {i}\n\nBody {i}.\n")

    proc, _, mpath = _run_report(run_cli, root, tmp_path, base)
    md = mpath.read_text()
    lines = md.splitlines()
    assert len(lines) <= 200, len(lines)
    assert lines[0] == "<!-- guidefold:change-report -->"
    for heading in ("# Guidefold change report", "## Summary", "## Structure", "## Changes",
                    "## Retrieval examples"):
        assert heading in lines, heading


def test_base_commit_without_guidefold_yaml_fails_with_an_explicit_message(run_cli, tmp_path):
    root = _init_repo(tmp_path / "repo")
    (root / "README.md").write_text("# nothing configured yet\n")
    empty = _commit(root, "before guidefold")
    write_guidefold_yaml(root, nodes=_nodes())
    write_skill(
        root / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[acme] How acme handles billing. Use when touching invoicing code.",
        metadata={"scope": "_root", "owner": "platform", "status": "active"},
        body="# Billing\n")
    _commit(root, "configure guidefold")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, empty)
    assert proc.returncode == 2
    assert "guidefold.yaml" in proc.stderr and "no skill map" in proc.stderr
    assert empty[:7] in proc.stderr
    assert not jpath.exists()


def test_unknown_base_ref_fails_with_an_explicit_message(run_cli, tmp_path):
    root, _ = _base_repo(tmp_path)
    proc, _, _ = _run_report(run_cli, root, tmp_path, "origin/does-not-exist")
    assert proc.returncode == 2
    assert "is not a commit in this repository" in proc.stderr


def test_missing_dependency_and_no_owner_carry_the_documented_severities(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    write_skill(
        root / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[acme] How acme handles billing and invoices. Use when touching invoicing code.",
        metadata={"scope": "_root", "status": "active",           # no owner -> warning
                  "requires": "urn:skill:acme:_root:does-not-exist"},   # missing dep -> error
        body="# Billing basics\n\nInvoices.\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    assert proc.returncode == 2
    p = _payload(jpath)
    assert "missing_required_dependency" in _codes(p, "error")
    assert "missing_owner" in _codes(p, "warning")
    dep = next(f for f in p["findings"] if f["code"] == "missing_required_dependency")
    assert dep["details"] == {"relation": "requires", "target": "urn:skill:acme:_root:does-not-exist"}


def test_changes_carry_per_field_diffs_relations_and_resources(run_cli, tmp_path):
    root = _init_repo(tmp_path / "repo")
    write_guidefold_yaml(root, nodes=_nodes())
    write_skill(
        root / ".agents" / "skills" / "billing-basics",
        name="billing-basics",
        description="[acme] How acme handles billing and invoices in detail. Use when invoicing.",
        metadata={"scope": "_root", "owner": "platform", "status": "active"},
        body="# Billing\n")
    write_skill(
        root / "teamA" / ".agents" / "skills" / "team-a-basics",
        name="team-a-basics",
        description="[teamA] How team A builds and ships. Use when working under teamA/.",
        metadata={"scope": "teamA", "owner": "team-a", "status": "active"},
        body="# Team A\n")
    refs = root / ".agents" / "skills" / "billing-basics" / "references"
    refs.mkdir()
    (refs / "ledger.md").write_text("ledger v1\n")
    base = _commit(root, "base")

    (refs / "ledger.md").write_text("ledger v2\n")                 # resource changed
    write_skill(
        root / "teamA" / ".agents" / "skills" / "team-a-basics",
        name="team-a-basics",
        description="[teamA] How team A builds.",                  # description shortened
        metadata={"scope": "teamA", "owner": "team-a", "status": "active",
                  "requires": "urn:skill:acme:_root:billing-basics"},   # relation added
        body="# Team A\n")
    # a scope's owner changes in guidefold.yaml
    write_guidefold_yaml(root, nodes={**_nodes(), "teamA": {"paths": ["teamA/**"], "owner": "team-a"}})

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    p = _payload(jpath)
    changed = {c["skill_id"]: {f["field"] for f in c["fields"]} for c in p["changes"]["skills"]["changed"]}
    assert changed["urn:skill:acme:teamA:team-a-basics"] >= {"description", "requires"}
    assert p["changes"]["relations"]["added"] == [
        {"relation": "requires", "from": "urn:skill:acme:teamA:team-a-basics",
         "to": "urn:skill:acme:_root:billing-basics"}]
    assert p["changes"]["relations"]["removed"] == []
    assert [r["path"] for r in p["changes"]["resources"]["changed"]] == \
        [".agents/skills/billing-basics/references/ledger.md"]
    assert "description_shortened" in _codes(p, "warning")
    assert p["summary"]["errors"] == 0 and proc.returncode == 0


def test_head_view_includes_uncommitted_work_and_records_dirty(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    write_skill(
        root / ".agents" / "skills" / "brand-new",
        name="brand-new",
        description="[acme] A brand new uncommitted skill. Use when nothing is committed yet.",
        metadata={"scope": "_root", "owner": "platform", "status": "active"},
        body="# New\n")

    proc, jpath, _ = _run_report(run_cli, root, tmp_path, base)
    p = _payload(jpath)
    assert p["dirty"] is True
    assert p["head_commit"] == _git(root, "rev-parse", "HEAD")
    assert p["base_commit"] == base
    assert p["changes"]["skills"]["added"] == ["urn:skill:acme:_root:brand-new"]


@pytest.mark.parametrize("flag", ["--json", "--markdown"])
def test_artifacts_are_optional(run_cli, tmp_path, flag):
    root, base = _base_repo(tmp_path)
    out = tmp_path / ("only" + flag.strip("-"))
    proc = run_cli(["report", "--base", base, flag, str(out)], cwd=root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()
    assert "guidefold report:" in proc.stdout


# L7 — `report`'s two artifact writes were the only text writes in the CLI without an explicit
# encoding, and `_report_markdown` embeds skill descriptions verbatim. On a `LANG=C` runner one
# non-ASCII description raised UnicodeEncodeError and killed the gate job.
def test_artifacts_are_utf8_on_a_c_locale_runner(run_cli, tmp_path):
    root, base = _base_repo(tmp_path)
    # Two same-node cards sharing a non-ASCII trigger phrase: `_report_trigger_collisions`
    # embeds the phrases verbatim in the finding message, which `_report_markdown` writes out.
    for name in ("billing-basics", "payouts-runbook"):
        write_skill(
            root / ".agents" / "skills" / name,
            name=name,
            description=f"[acme] Rozliczenia płatności w {name} — użyj przy księgowaniu wpłat.",
            metadata={"scope": "_root", "owner": "platform", "status": "active",
                      "triggers": "księgowanie wpłat, rozliczenie płatności"},
            body=f"# {name}\n\nWpłaty są księgowane każdej nocy.\n")
    _commit(root, "non-ascii triggers")
    env = {**os.environ, "GUIDEFOLD_CACHE": str(tmp_path / ".cache-guidefold"),
           "LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0",
           "PYTHONIOENCODING": "utf-8"}
    jpath, mpath = tmp_path / "c.json", tmp_path / "c.md"
    proc = run_cli(["report", "--base", base, "--json", str(jpath), "--markdown", str(mpath)],
                   cwd=root, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "UnicodeEncodeError" not in proc.stderr and "UnicodeDecodeError" not in proc.stderr
    markdown = mpath.read_text(encoding="utf-8")
    assert "trigger_collision" in markdown
    assert "wpłat" in markdown
    # The JSON artifact escapes non-ASCII, so it is readable either way; assert it parses.
    assert json.loads(jpath.read_text(encoding="utf-8"))["schema"] == "guidefold-change-report-v1"
