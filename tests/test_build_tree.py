"""`tools/worker/build_tree.py` — the publish worker's snapshot builder.

The claim under test is the one the publish job depends on: building from a materialised import
tree produces the SAME serving snapshot as building from the equivalent git commit. If those
ever diverge, a published snapshot would no longer be reproducible from git, which is the whole
point of ADR-0001. So the test builds both ways over the same bytes and compares nodes, cards
and weights field by field, allowing only `source` to differ.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.serve_spike import repository
from tools.serve_spike.server import load_cli_snapshot
from tools.worker import build_tree

CLI_PATH = ROOT / "skills" / "guidefold" / "scripts" / "guidefold"


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


@pytest.fixture(scope="module")
def cli_pair():
    return load_cli_snapshot(CLI_PATH)


@pytest.fixture
def committed_tree(tmp_path, fixture_root):
    """A throwaway git repo holding the Meridian fixture, so both builders see identical bytes:
    `repository.build` reads them out of the commit, `build_tree.build` off the work tree."""
    tree = tmp_path / "meridian"
    shutil.copytree(fixture_root, tree)
    shutil.rmtree(tree / ".guidefold", ignore_errors=True)
    _git(tree, "init", "-q", "-b", "main")
    _git(tree, "config", "user.email", "t@e.st")
    _git(tree, "config", "user.name", "T")
    _git(tree, "add", "-A", "-f")
    _git(tree, "commit", "-q", "-m", "fixture")
    return tree


def test_import_tree_snapshot_matches_the_git_commit_snapshot(committed_tree, cli_pair):
    cli, cli_sha = cli_pair
    commit = _git(committed_tree, "rev-parse", "HEAD").stdout.strip()
    from_git = repository.build(committed_tree, "meridian", "HEAD", cli, cli_sha)
    from_tree, _cfg = build_tree.build(committed_tree, "meridian", commit, cli, cli_sha)

    git_snapshot, tree_snapshot = from_git["snapshot"], from_tree["snapshot"]
    assert git_snapshot["revision"] == tree_snapshot["revision"] == commit
    assert git_snapshot["nodes"] == tree_snapshot["nodes"]
    assert git_snapshot["cards"] == tree_snapshot["cards"]
    assert git_snapshot["weights"] == tree_snapshot["weights"]
    assert git_snapshot["cli_sha256"] == tree_snapshot["cli_sha256"] == cli_sha
    assert git_snapshot["format"] == tree_snapshot["format"] == repository.FORMAT
    # Provenance is the ONLY difference, and it is explicit.
    assert git_snapshot["source"] == "git_commit_only"
    assert tree_snapshot["source"] == "import_tree"
    differing = {k for k in set(git_snapshot) | set(tree_snapshot)
                 if git_snapshot.get(k) != tree_snapshot.get(k)}
    assert differing == {"source"}


def test_the_snapshot_loads_back_through_the_serving_path(committed_tree, cli_pair, tmp_path):
    """The envelope must satisfy `repository.load`'s integrity checks (digest, format, cli sha),
    or the service would reject a snapshot the worker just produced."""
    cli, cli_sha = cli_pair
    commit = _git(committed_tree, "rev-parse", "HEAD").stdout.strip()
    bundle, _cfg = build_tree.build(committed_tree, "meridian", commit, cli, cli_sha)
    path = tmp_path / "snapshot.json"
    path.write_bytes(repository.canonical(bundle) + b"\n")
    index, meta, tag = repository.load(path, cli, cli_sha)
    assert meta == {"repo_id": "meridian", "revision": commit}
    assert tag.startswith("repository:")
    assert len(index.cards) == len(bundle["snapshot"]["cards"])


def test_source_proof_flows_from_import_tree_into_the_serving_snapshot(committed_tree, cli_pair):
    """The worker path must preserve the structured source proof that USE 1.2 gates on.

    This is propagation coverage only: the proof below is deliberately unverified, so it must be
    present in the immutable card and inventory without becoming a ranking or publication claim.
    """
    cli, cli_sha = cli_pair
    skill = next(
        md for md in build_tree._skill_files(committed_tree)
        if str((cli.frontmatter(md).get("metadata") or {}).get("generated", "")).lower() != "true"
    )
    original = skill.read_text(encoding="utf-8")
    marker = "\n---\n"
    assert marker in original
    proof = """source_proof:
  schema: source-proof-v1
  verified: false
  snapshot: pending
  claims:
    - id: operation
      status: partial
"""
    skill.write_text(original.replace(marker, "\n" + proof + "---\n", 1), encoding="utf-8")

    bundle, _cfg = build_tree.build(committed_tree, "meridian", "0" * 40, cli, cli_sha)
    card = next(card for card in bundle["snapshot"]["cards"].values()
                if card["name"] == skill.parent.name)
    assert card["proof"]["schema"] == "source-proof-v1"
    assert card["proof"]["verified"] is False
    rows = build_tree.inventory(cli, committed_tree, cli.load_map(committed_tree), "meridian", "0" * 40)
    row = next(row for row in rows["skills"] if row["path"] == skill.relative_to(committed_tree).as_posix())
    assert row["frontmatter"]["source_proof"]["verified"] is False


def test_cli_writes_a_snapshot_and_an_inventory(committed_tree, tmp_path):
    commit = _git(committed_tree, "rev-parse", "HEAD").stdout.strip()
    out = tmp_path / "out" / "snapshot.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "worker" / "build_tree.py"),
         "--tree", str(committed_tree), "--repo-id", "meridian", "--commit", commit,
         "--output", str(out)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["source"] == "import_tree"
    assert summary["errors"] == 0
    bundle = json.loads(out.read_text())
    assert bundle["snapshot"]["source"] == "import_tree"
    # The Go publisher's BM25F export travels with the snapshot.
    assert bundle["router_index"]["format"] == "guidefold-bm25f-build-v1"
    assert bundle["router_index"]["policy_sha256"] == bundle["snapshot"]["cli_sha256"]
    assert bundle["router_index"]["snapshot_sha256"] == bundle["sha256"]

    inventory = json.loads((out.parent / "inventory.json").read_text())
    assert inventory["format"] == "guidefold-import-inventory-v1"
    assert summary["skills"] == len(inventory["skills"])


def test_inventory_carries_scope_owner_relations_and_digests(committed_tree, cli_pair):
    cli, _cli_sha = cli_pair
    cfg = cli.load_map(committed_tree)
    rows = build_tree.inventory(cli, committed_tree, cfg, "meridian", "0" * 40)
    assert rows["errors"] == []
    # W3 — 26 authored cards, and the generated hierarchy-index named as skipped rather than
    # carried as a 27th row the snapshot has no card for.
    assert len(rows["skills"]) == 26, [r["path"] for r in rows["skills"]]
    assert not any(r["generated"] for r in rows["skills"])

    by_path = {r["path"]: r for r in rows["skills"]}
    # Deterministic order, by path bytes.
    assert [r["path"] for r in rows["skills"]] == sorted(by_path, key=lambda p: p.encode())

    for row in rows["skills"]:
        assert row["urn"].startswith("urn:skill:")
        assert row["scope"] and row["name"]
        assert len(row["sha256"]) == 64
        assert row["size"] == (committed_tree / row["path"]).stat().st_size
        assert isinstance(row["frontmatter"], dict)
        for key in ("requires", "refines", "references", "triggers"):
            assert isinstance(row[key], list)

    scoped = [r for r in rows["skills"] if r["scope"] not in ("_root", "_index")]
    assert scoped, "the fixture must exercise nested scopes"
    assert any(r["owner"] for r in scoped)
    assert any(r["requires"] for r in rows["skills"]), "the fixture declares requires relations"
    assert any(r["refines"] for r in rows["skills"]), "the fixture declares refines relations"
    assert {r["status"] for r in rows["skills"]} <= {"active", "deprecated", None}

    # The inventory's own digests are the ones `guidefold scan` would upload. The scan carries
    # every SKILL.md in the tree, so the generated one is compared out explicitly.
    manifest, _blobs, _stats = cli.scan_manifest(committed_tree, cfg, org="acme", repo="meridian")
    scanned = {f["path"]: f["sha256"] for f in manifest["files"] if f["kind"] == "skill"}
    for path in rows["generated_skipped"]:
        scanned.pop(path, None)
    assert {r["path"]: r["sha256"] for r in rows["skills"]} == scanned


def test_one_unparseable_skill_is_reported_and_the_rest_still_build(committed_tree, cli_pair):
    cli, _cli_sha = cli_pair
    broken = committed_tree / "platforms" / "atlas" / ".agents" / "skills" / "broken-skill"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\nname: [unclosed\ndescription: x\n---\nbody\n")
    cfg = cli.load_map(committed_tree)
    rows = build_tree.inventory(cli, committed_tree, cfg, "meridian", "0" * 40)
    assert len(rows["skills"]) == 26
    assert len(rows["errors"]) == 1
    assert rows["errors"][0]["path"].endswith("broken-skill/SKILL.md")
    assert rows["errors"][0]["error"]


def test_a_tree_without_guidefold_yaml_is_rejected(tmp_path, cli_pair):
    cli, cli_sha = cli_pair
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError) as exc:
        build_tree.build(tmp_path / "empty", "meridian", "0" * 40, cli, cli_sha)
    assert "guidefold_yaml" in str(exc.value)


# W3 — the inventory used to enumerate every `.agents/skills/*/SKILL.md` while `Index.build`
# went through `all_skills(include_generated=False)`, so a tree carrying a generated
# hierarchy-index produced `{"cards": 26, "skills": 27}` and put a skill in the catalog that
# SEARCH could never return.
def test_generated_skills_are_named_not_carried_as_rows(committed_tree, cli_pair):
    cli, cli_sha = cli_pair
    cfg = cli.load_map(committed_tree)
    rows = build_tree.inventory(cli, committed_tree, cfg, "meridian", "0" * 40)
    bundle, _cfg = build_tree.build(committed_tree, "meridian", "0" * 40, cli, cli_sha)

    generated = rows["generated_skipped"]
    assert generated, "the fixture must carry a generated hierarchy-index at this baseline"
    assert all(path.endswith("SKILL.md") for path in generated)
    assert generated == sorted(generated)
    # The two now agree: one row per card, no row without one.
    assert len(rows["skills"]) == len(bundle["snapshot"]["cards"])
    assert not (set(generated) & {r["path"] for r in rows["skills"]})


# W2 — `guidefold.yaml` is client input. Every malformed shape used to fall through to the CLI
# and surface as the last line of a Python traceback in `gfm.imports.error`.
@pytest.mark.parametrize("body,reason", [
    ("", "import_tree_guidefold_yaml_not_a_mapping"),
    ("- one\n- two\n", "import_tree_guidefold_yaml_not_a_mapping"),
    ("just a string\n", "import_tree_guidefold_yaml_not_a_mapping"),
    ("nodes:\n  _root:\n    paths: ['**']\n", "import_tree_missing_publisher"),
    ("publisher: acme\nnodes: [a, b]\n", "import_tree_nodes_not_a_mapping"),
    ("publisher: acme\nnodes:\n  _root:\n   paths: ['**'\n", "import_tree_guidefold_yaml_unparseable"),
])
def test_a_malformed_guidefold_yaml_fails_with_a_named_reason(tmp_path, cli_pair, body, reason):
    cli, cli_sha = cli_pair
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "guidefold.yaml").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        build_tree.build(tree, "meridian", "0" * 40, cli, cli_sha)
    assert str(exc.value).startswith(reason), str(exc.value)
    # Never a Python traceback's vocabulary in what the owner is shown.
    assert "NoneType" not in str(exc.value) and "KeyError" not in str(exc.value)
