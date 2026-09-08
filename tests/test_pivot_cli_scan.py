"""U1 (docs/PRODUCT-PIVOT.md §4) — `guidefold scan`: the offline import manifest.

AC covered here:
  U1.1  `scan --dry-run` opens no socket at all (proved by making `socket.socket` raise, so any
        attempt to connect anywhere would be a hard failure rather than a silent success).
  U1.2  the Meridian fixture's supported sources are all detected, with their kinds.
  U1.3  `.env`, an ignored directory and a symlink out of the tree never reach `files`.
  U1.4  the same tree produces byte-identical manifests.
  U1.6  the 10 000-path budget, and limits as an explicit error instead of silent truncation.
  U1.2/AC2  `manifest["suggestions"]`: advisory scope/owner guesses (directories, CODEOWNERS)
        for a `skill` file guidefold.yaml does not map on its own, each with a reasons[] list.
        Never changes `files[]`/`excluded[]`, never used by the CLI's own scope resolution.

Everything runs in-process against the `gf` CLI module (conftest.py's fixture) so the socket
guard actually applies to the code under test.
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


def _args(**kw):
    base = {"path": None, "dry_run": False, "json": False, "partial": False,
            "profile": "default", "api": None, "org": None, "repo": None}
    base.update(kw)
    return SimpleNamespace(**base)


def _scan(gf, root, **kw):
    """Run scan_manifest the way cmd_scan does, without argparse or sys.exit."""
    cfg = gf._tolerant_config(Path(root))
    return gf.scan_manifest(Path(root), cfg, org="acme", repo="monorepo", **kw)


def _simple_tree(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / "guidefold.yaml").write_text("publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n")
    (root / "README.md").write_text("# repo\n")
    skill = root / ".agents" / "skills" / "root-conventions"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: root-conventions\n---\nbody\n")
    (skill / "references").mkdir()
    (skill / "references" / "api.md").write_text("reference\n")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
    (skill / "notes.txt").write_text("not an importable format\n")
    (root / "src").mkdir()
    (root / "src" / "main.go").write_text("package main\n")
    return root


# ------------------------------------------------------------------------------- U1.1

def test_scan_dry_run_opens_no_socket(gf, tmp_path, monkeypatch, capsys):
    root = _simple_tree(tmp_path / "repo")

    def explode(*a, **kw):
        raise AssertionError("scan opened a socket")

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_scan(_args(dry_run=True, json=True))
    assert exc.value.code == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["format"] == "guidefold-import-manifest-v1"
    assert {f["path"] for f in manifest["files"]} >= {"README.md", "guidefold.yaml",
                                                      ".agents/skills/root-conventions/SKILL.md"}


def test_scan_does_not_import_the_http_stack(gf, tmp_path, monkeypatch):
    """A stronger form of the same rule: the *offline* commands must not even load urllib /
    http.client, so an accidental future `import urllib` at the top of a scan helper is caught
    here rather than by a firewall in production."""
    root = _simple_tree(tmp_path / "repo")
    probe = (
        "import sys, runpy, json;"
        "sys.argv=['guidefold','scan','--dry-run','--json'];"
        "\ntry:\n runpy.run_path(sys.argv0 if False else CLI, run_name='__main__')\nexcept SystemExit:\n pass\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] in ('urllib','http'))), file=sys.stderr)"
    )
    script = tmp_path / "probe.py"
    script.write_text("CLI = %r\n" % str(Path(gf.__file__)) + probe)
    out = subprocess.run([sys.executable, str(script)], cwd=str(root), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    loaded = json.loads(out.stderr.strip().splitlines()[-1])
    assert [m for m in loaded if m.startswith(("urllib.request", "http.client"))] == [], loaded


# ------------------------------------------------------------------------------- U1.2

def test_meridian_fixture_detects_every_supported_source(gf, fixture_root):
    manifest, blobs, stats = _scan(gf, fixture_root)
    by_kind = {}
    for f in manifest["files"]:
        by_kind.setdefault(f["kind"], []).append(f["path"])
    assert len(by_kind["skill"]) == 27, sorted(by_kind["skill"])
    assert by_kind["config"] == ["guidefold.yaml"]
    assert "README.md" in by_kind["document"]
    assert "docs/adr/README.md" in by_kind["document"]
    assert len(blobs) == stats["unique_blobs"]
    assert manifest["complete"] is True and manifest["publish"] is True


def test_scan_classifies_kinds_and_flags_unsupported_files_inside_a_skill_dir(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    manifest, _blobs, _stats = _scan(gf, root)
    kinds = {f["path"]: f["kind"] for f in manifest["files"]}
    assert kinds["guidefold.yaml"] == "config"
    assert kinds["README.md"] == "document"
    assert kinds[".agents/skills/root-conventions/SKILL.md"] == "skill"
    assert kinds[".agents/skills/root-conventions/references/api.md"] == "resource"
    assert kinds[".agents/skills/root-conventions/scripts/run.sh"] == "resource"
    # A file outside every skill dir that guidefold does not import is simply not listed…
    assert "src/main.go" not in kinds
    assert not any(e["path"] == "src/main.go" for e in manifest["excluded"])
    # …but the same thing inside a skill dir is reported, with the reason.
    assert {"path": ".agents/skills/root-conventions/notes.txt",
            "reason": "unsupported_format"} in manifest["excluded"]


def test_scan_excludes_a_skill_md_outside_the_agents_skills_convention(gf, tmp_path):
    """A `SKILL.md` that does not sit at `<any>/.agents/skills/<name>/SKILL.md` can never be
    published: `all_skills()` (find/load/validate/materialize/doctor/report, and the worker's
    build_tree.py) only ever discovers that one shape. Before this fix `scan`/`import` accepted
    any `SKILL.md` anywhere and registered it as `kind:"skill"`, so a real monorepo using a
    different layout (e.g. `plugins/<x>/skills/<y>/SKILL.md`) imported cleanly and then could
    never publish (`invalid_snapshot_dimensions`, n_skills:0) -- a confusing failure three steps
    after the point an operator could have been told. `scan` must say so immediately instead."""
    root = _simple_tree(tmp_path / "repo")
    stray = root / "plugins" / "backend" / "skills" / "cqrs-implementation"
    stray.mkdir(parents=True)
    (stray / "SKILL.md").write_text("---\nname: cqrs-implementation\n---\nbody\n")
    manifest, _blobs, _stats = _scan(gf, root)
    kinds = {f["path"]: f["kind"] for f in manifest["files"]}
    # The canonical skill is still recognised…
    assert kinds[".agents/skills/root-conventions/SKILL.md"] == "skill"
    # …but the stray one is never a `skill` file, and never silently just disappears either.
    assert "plugins/backend/skills/cqrs-implementation/SKILL.md" not in kinds
    assert {"path": "plugins/backend/skills/cqrs-implementation/SKILL.md",
            "reason": "non_canonical_skill_path"} in manifest["excluded"]


def test_scan_records_the_executable_bit(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    os.chmod(root / ".agents/skills/root-conventions/scripts/run.sh", 0o755)
    manifest, _b, _s = _scan(gf, root)
    modes = {f["path"]: f["mode"] for f in manifest["files"]}
    assert modes[".agents/skills/root-conventions/scripts/run.sh"] == "100755"
    assert modes["README.md"] == "100644"


# ------------------------------------------------------------------------------- U1.3

def test_secrets_ignored_dirs_and_escaping_symlinks_never_reach_files(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SECRETS.md").write_text("# not ours\n")
    (root / ".env").write_text("API_TOKEN=super-secret\n")
    (root / ".env.local").write_text("API_TOKEN=also-secret\n")
    (root / "deploy.pem").write_text("cert\n")
    (root / "id_rsa").write_text("key\n")
    (root / "svc-credentials.json").write_text("{}\n")
    (root / "node_modules" / "left-pad").mkdir(parents=True)
    (root / "node_modules" / "left-pad" / "README.md").write_text("# dep\n")
    (root / "vendor").mkdir()
    (root / "vendor" / "README.md").write_text("# vendored\n")
    # An innocent-looking name whose *content* is a private key.
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----\n")
    (root / "escape.md").symlink_to(outside / "SECRETS.md")

    manifest, blobs, _stats = _scan(gf, root)
    listed = {f["path"] for f in manifest["files"]}
    reasons = {e["path"]: e["reason"] for e in manifest["excluded"]}

    for secret in (".env", ".env.local", "deploy.pem", "id_rsa", "svc-credentials.json"):
        assert secret not in listed
        assert reasons[secret] == "secret_pattern"
    assert reasons["docs/README.md"] == "secret_pattern"     # content sniff, not the name
    assert "docs/README.md" not in listed
    assert reasons["escape.md"] == "symlink_outside_root"
    assert "escape.md" not in listed
    assert reasons["node_modules"] == "ignored_directory"
    assert reasons["vendor"] == "ignored_directory"
    assert not any(p.startswith(("node_modules/", "vendor/")) for p in listed)

    # The bytes of every excluded path are absent from the upload set, not merely unlisted.
    uploadable = {p.read_bytes() for p in blobs.values()}
    assert not any(b"super-secret" in b or b"PRIVATE KEY" in b or b"not ours" in b for b in uploadable)


def test_guidefoldignore_and_gitignore_subset_are_honoured_off_git(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("# docs\n")
    (root / "generated").mkdir()
    (root / "generated" / "README.md").write_text("# generated\n")
    (root / ".gitignore").write_text("generated/\n*.tmp.md\n")
    (root / "keep.tmp.md").write_text("temp\n")
    (root / ".guidefoldignore").write_text("docs/README.md\n")

    manifest, _b, _s = _scan(gf, root)
    listed = {f["path"] for f in manifest["files"]}
    reasons = {e["path"]: e["reason"] for e in manifest["excluded"]}
    assert "generated/README.md" not in listed        # gitignored: silent, like git itself
    assert "keep.tmp.md" not in listed
    assert "docs/README.md" not in listed             # .guidefoldignore: recorded, it is our own file
    assert reasons["docs/README.md"] == "guidefoldignore"


def test_gitignore_negation_re_includes_a_file(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    (root / "notes").mkdir()
    (root / "notes" / "README.md").write_text("# a\n")
    (root / "notes" / "AGENTS.md").write_text("# b\n")
    (root / ".gitignore").write_text("*.md\n!AGENTS.md\n")
    manifest, _b, _s = _scan(gf, root)
    listed = {f["path"] for f in manifest["files"]}
    assert "notes/AGENTS.md" in listed
    assert "notes/README.md" not in listed


# ------------------------------------------------------------------------------- U1.4

def test_the_same_tree_produces_byte_identical_manifests(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    first, _b1, _s1 = _scan(gf, root)
    second, _b2, _s2 = _scan(gf, root)
    assert gf._canonical_json(first) == gf._canonical_json(second)
    # Ordering is by raw path bytes, never by locale or discovery order.
    paths = [f["path"] for f in first["files"]]
    assert paths == sorted(paths, key=lambda p: p.encode("utf-8"))
    assert "timestamp" not in gf._canonical_json(first).decode()


def test_manifest_carries_no_wall_clock_field(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    manifest, _b, _s = _scan(gf, root)
    flat = gf._canonical_json(manifest).decode()
    for banned in ("scanned_at", "created_at", "generated_at", "timestamp"):
        assert banned not in flat


# ------------------------------------------------------------------------- git integration

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=True)


def _git_repo(root: Path):
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    return root


def test_commit_is_recorded_only_when_the_listed_files_are_clean(gf, tmp_path):
    root = _git_repo(_simple_tree(tmp_path / "repo"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    manifest, _b, stats = _scan(gf, root)
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    assert stats["git"] is True
    assert manifest["commit"] == head
    assert manifest["dirty"] is False

    (root / "README.md").write_text("# changed\n")
    dirty_manifest, _b2, _s2 = _scan(gf, root)
    assert dirty_manifest["commit"] is None
    assert dirty_manifest["dirty"] is True


def test_outside_git_the_manifest_is_dirty_with_no_commit(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    manifest, _b, stats = _scan(gf, root)
    assert stats["git"] is False
    assert manifest["commit"] is None and manifest["dirty"] is True


def test_submodules_are_listed_as_an_explicit_exclusion(gf, tmp_path):
    inner = _git_repo(_simple_tree(tmp_path / "inner"))
    _git(inner, "add", "-A")
    _git(inner, "commit", "-q", "-m", "inner")
    root = _git_repo(_simple_tree(tmp_path / "repo"))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    add = subprocess.run(["git", "-C", str(root), "-c", "protocol.file.allow=always",
                          "submodule", "add", "-q", str(inner), "libs/inner"],
                         capture_output=True, text=True)
    if add.returncode != 0:
        pytest.skip(f"git submodule add unavailable here: {add.stderr.strip()}")
    manifest, _b, _s = _scan(gf, root)
    reasons = {e["path"]: e["reason"] for e in manifest["excluded"]}
    assert reasons.get("libs/inner") == "submodule"
    assert not any(f["path"].startswith("libs/inner/") for f in manifest["files"])


def test_partial_scan_is_marked_incomplete(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    manifest, _b, _s = _scan(gf, root, complete=False)
    assert manifest["complete"] is False


# ------------------------------------------------------------------------------- U1.5 alias

def test_aliases_from_guidefold_yaml_are_copied_into_the_manifest(gf, tmp_path):
    root = _simple_tree(tmp_path / "repo")
    (root / "guidefold.yaml").write_text(
        "publisher: acme\n"
        "nodes:\n  _root:\n    paths: ['**']\n    owner: platform\n"
        "import:\n"
        "  aliases:\n"
        "    - from: teamA/.agents/skills/old-name/SKILL.md\n"
        "      to: teamA/.agents/skills/new-name/SKILL.md\n"
    )
    manifest, _b, _s = _scan(gf, root)
    assert manifest["aliases"] == [{"from": "teamA/.agents/skills/old-name/SKILL.md",
                                    "to": "teamA/.agents/skills/new-name/SKILL.md"}]


# ------------------------------------------------------------------------------- U1.6 limits

def test_limits_raise_an_explicit_error_instead_of_truncating(gf, tmp_path, monkeypatch):
    root = _simple_tree(tmp_path / "repo")
    docs = root / "docs"
    docs.mkdir()
    for i in range(12):
        (docs / f"n{i}").mkdir()
        (docs / f"n{i}" / "README.md").write_text(f"# {i}\n")
    monkeypatch.setattr(gf, "SCAN_MAX_FILES", 5)
    with pytest.raises(gf.ScanLimitExceeded) as exc:
        _scan(gf, root)
    assert exc.value.limit == "max_files"

    monkeypatch.setattr(gf, "SCAN_MAX_FILES", 10_000)
    monkeypatch.setattr(gf, "SCAN_MAX_BYTES", 10)
    with pytest.raises(gf.ScanLimitExceeded) as exc:
        _scan(gf, root)
    assert exc.value.limit == "max_bytes"


def test_cmd_scan_exits_two_on_a_limit(gf, tmp_path, monkeypatch, capsys):
    root = _simple_tree(tmp_path / "repo")
    monkeypatch.setattr(gf, "SCAN_MAX_FILES", 1)
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_scan(_args())
    assert exc.value.code == 2
    assert "limit_exceeded" in capsys.readouterr().err


def test_a_file_over_the_blob_limit_is_excluded_not_silently_dropped(gf, tmp_path, monkeypatch):
    root = _simple_tree(tmp_path / "repo")
    (root / "big").mkdir()
    (root / "big" / "README.md").write_text("x" * 5000)
    monkeypatch.setattr(gf, "SCAN_MAX_FILE_BYTES", 1000)
    manifest, _b, _s = _scan(gf, root)
    assert {"path": "big/README.md", "reason": "file_too_large"} in manifest["excluded"]


@pytest.mark.slow
def test_ten_thousand_paths_scan_well_inside_the_ci_budget(gf, tmp_path):
    """U1 AC6 targets p95 ≤ 10 s for 10 000 paths on a 2 vCPU pilot box. This asserts a
    deliberately generous CI bound (20 s) on one run: it is a guard against an accidental
    quadratic pass, not the AC6 measurement itself (that needs the pinned hardware and 20
    trials). RSS is not measured here."""
    root = tmp_path / "big"
    root.mkdir()
    (root / "guidefold.yaml").write_text("publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n")
    made = 1
    d = 0
    while made < 10_000:
        directory = root / "docs" / f"d{d:04d}"
        directory.mkdir(parents=True)
        for i in range(40):
            if made >= 10_000:
                break
            (directory / f"n{i}").mkdir()
            (directory / f"n{i}" / "README.md").write_text(f"# {d}-{i}\n")
            made += 1
        d += 1
    started = time.monotonic()
    manifest, _blobs, _stats = _scan(gf, root)
    elapsed = time.monotonic() - started
    assert len(manifest["files"]) == 10_000
    assert elapsed < 20.0, f"scan of 10 000 paths took {elapsed:.1f}s"


# --------------------------------------------------------------- U1 AC2 scope/owner suggestions

def _tree_without_guidefold_yaml(root: Path):
    """No guidefold.yaml at all: legitimate ("scan on a plain directory is a legitimate first
    step before guidefold.yaml exists", `_pivot_root`'s own docstring) but every skill's scope
    is necessarily unmapped."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# repo\n")
    nested = root / "platforms" / "forge" / "pipelines" / ".agents" / "skills" / "pipeline-testing"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: pipeline-testing\n---\nbody\n")
    at_root = root / ".agents" / "skills" / "root-conventions"
    at_root.mkdir(parents=True)
    (at_root / "SKILL.md").write_text("---\nname: root-conventions\n---\nbody\n")
    return root


def test_missing_guidefold_yaml_flags_every_skill_and_derives_scope_from_directories(gf, tmp_path):
    root = _tree_without_guidefold_yaml(tmp_path / "repo")
    manifest, _b, _s = _scan(gf, root)
    by_path = {s["path"]: s for s in manifest["suggestions"]}
    skill_paths = {f["path"] for f in manifest["files"] if f["kind"] == "skill"}
    assert skill_paths == set(by_path), "every skill file must have a suggestion when the map is absent"
    for entry in by_path.values():
        assert "guidefold_yaml_missing" in entry["reasons"]
        # No CODEOWNERS file either in this fixture, so the owner guess is equally uncertain —
        # both kinds of uncertainty are visible on the same entry (PRODUCT-PIVOT U1: "niepewna
        # hierarchia/owner są widoczne").
        assert "no_codeowners_rule" in entry["reasons"]
        assert entry["suggested_owner"] is None
    root_entry = by_path[".agents/skills/root-conventions/SKILL.md"]
    assert root_entry["suggested_scope"] == "_root"
    nested_entry = by_path["platforms/forge/pipelines/.agents/skills/pipeline-testing/SKILL.md"]
    assert nested_entry["suggested_scope"] == "platforms/forge/pipelines"
    assert "candidates" not in nested_entry


def test_codeowners_supplies_the_owner_guess_from_the_last_matching_rule(gf, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    # guidefold.yaml exists but its only node does not cover team/special/** at all.
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  docs:\n    paths: ['docs/**']\n    owner: docs-team\n")
    (root / ".github").mkdir()
    (root / ".github" / "CODEOWNERS").write_text(
        "*  @acme/default-team\n"
        "/team/  @acme/team-owner\n"
        "/team/special/  @acme/special-owner\n"
    )
    skill = root / "team" / "special" / ".agents" / "skills" / "foo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: foo\n---\nbody\n")
    manifest, _b, _s = _scan(gf, root)
    [entry] = manifest["suggestions"]
    assert entry["path"] == "team/special/.agents/skills/foo/SKILL.md"
    assert "no_node_covers_path" in entry["reasons"]
    assert entry["suggested_owner"] == "special-owner"        # last matching CODEOWNERS rule
    assert "multiple_codeowners_rules" in entry["reasons"]     # *, /team/ and /team/special/ all hit


def test_nested_skill_dir_outside_every_node_gets_a_raw_directory_scope(gf, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: ['README.md']\n    owner: platform\n")
    nested = root / "teams" / "growth" / "experiments" / ".agents" / "skills" / "ab-testing"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: ab-testing\n---\nbody\n")
    manifest, _b, _s = _scan(gf, root)
    [entry] = manifest["suggestions"]
    assert entry["path"] == "teams/growth/experiments/.agents/skills/ab-testing/SKILL.md"
    assert entry["reasons"] == ["nested_skill_dir_without_node", "no_codeowners_rule",
                                 "no_node_covers_path"]
    assert entry["suggested_scope"] == "teams/growth/experiments"      # raw directory chain
    assert entry["suggested_owner"] is None


def test_a_declared_node_name_matching_a_directory_suffix_is_used_as_the_scope_guess(gf, tmp_path):
    """"platforms/forge/pipelines" -> "forge.pipelines" when a node named "forge.pipelines"
    already exists, even though ITS OWN glob does not happen to cover this particular file."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "publisher: acme\n"
        "nodes:\n"
        "  forge.pipelines:\n"
        "    paths: ['elsewhere/**']\n"
        "    owner: pipelines-team\n"
    )
    nested = root / "platforms" / "forge" / "pipelines" / ".agents" / "skills" / "new-thing"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: new-thing\n---\nbody\n")
    manifest, _b, _s = _scan(gf, root)
    [entry] = manifest["suggestions"]
    assert entry["suggested_scope"] == "forge.pipelines"


def test_two_nodes_tied_on_specificity_are_surfaced_as_ambiguous_not_excluded(gf, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "publisher: acme\n"
        "nodes:\n"
        "  alpha:\n"
        "    paths: ['shared/**']\n"
        "    owner: team-a\n"
        "  beta:\n"
        "    paths: ['shared/**']\n"
        "    owner: team-b\n"
    )
    skill = root / "shared" / ".agents" / "skills" / "contested"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: contested\n---\nbody\n")
    manifest, _b, _s = _scan(gf, root)
    skill_path = "shared/.agents/skills/contested/SKILL.md"
    [entry] = [s for s in manifest["suggestions"] if s["path"] == skill_path]
    assert "ambiguous_node_match" in entry["reasons"]
    assert entry["candidates"] == ["alpha", "beta"]
    # The tie is surfaced, not swallowed: the file is still an ordinary, fully-scanned entry.
    assert skill_path in {f["path"] for f in manifest["files"]}
    assert not any(e["path"] == skill_path for e in manifest["excluded"])


def test_meridian_fixture_has_no_suggestions(gf, fixture_root):
    """The Meridian fixture's guidefold.yaml maps every skill directory, including the
    generated `hierarchy-index` skill sitting directly under `.agents/skills/` with no
    platform-specific ancestor: it still resolves cleanly to the declared `_root: paths:
    ["**"]` node, which is an explicit policy choice, not an inferred fallback -- so it is
    "covered" and gets no suggestion."""
    manifest, _b, _s = _scan(gf, fixture_root)
    assert manifest["suggestions"] == []
    assert any(f["path"].endswith("hierarchy-index/SKILL.md") for f in manifest["files"])


def test_suggestions_section_appears_in_human_and_json_scan_output(gf, tmp_path, monkeypatch, capsys):
    root = _tree_without_guidefold_yaml(tmp_path / "repo")
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    with pytest.raises(SystemExit):
        gf.cmd_scan(_args(json=True))
    out = json.loads(capsys.readouterr().out)
    assert len(out["suggestions"]) == 2

    with pytest.raises(SystemExit):
        gf.cmd_scan(_args())
    human = capsys.readouterr().out
    assert "suggestions: 2" in human
    assert "guidefold_yaml_missing" in human


def test_suggestions_are_deterministic_across_scans(gf, tmp_path):
    root = _tree_without_guidefold_yaml(tmp_path / "repo")
    first, _b1, _s1 = _scan(gf, root)
    second, _b2, _s2 = _scan(gf, root)
    assert gf._canonical_json(first) == gf._canonical_json(second)
    assert first["suggestions"] == second["suggestions"]
    paths = [s["path"] for s in first["suggestions"]]
    assert paths == sorted(paths, key=lambda p: p.encode("utf-8"))
