"""`guidefold init` bootstraps a *consumer* monorepo: guidefold.yaml skeleton,
.agents/skills/guidefold, harness hooks, CI workflow, .gitignore entries — idempotently, and
`--dry-run` must write nothing at all. Tests call gf.cmd_init(...) in-process against a
throwaway tmp_path repo (monkeypatch.chdir), the same way test_repo_helpers.py exercises
gf.repo_root()."""
import json

import pytest


def _init(gf, monkeypatch, root, *, publisher=None, harness="all", dry_run=False):
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    a = type("Args", (), {"publisher": publisher, "harness": harness, "dry_run": dry_run})()
    gf.cmd_init(a)


ARTIFACTS = [
    "guidefold.yaml",
    ".agents/skills/guidefold/SKILL.md",
    ".agents/skills/guidefold/scripts/guidefold",
    ".claude/settings.json",
    ".github/hooks/guidefold.json",
    ".codex/hooks.json",
    ".github/workflows/skills.yml",
    ".gitignore",
]


def test_init_on_empty_repo_creates_every_artifact(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    missing = [p for p in ARTIFACTS if not (root / p).is_file()]
    assert not missing, f"missing artifacts: {missing}"
    assert ".guidefold/" in (root / ".gitignore").read_text()


def test_init_twice_is_idempotent(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    before = {p: (root / p).read_text() for p in ARTIFACTS if (root / p).is_file() and p != ".agents/skills/guidefold/scripts/guidefold"}
    _init(gf, monkeypatch, root)
    after = {p: (root / p).read_text() for p in before}
    assert before == after


def test_init_dry_run_writes_nothing(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root, dry_run=True)
    assert list(root.rglob("*")) == []


def test_init_never_overwrites_existing_guidefold_yaml(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    custom = "publisher: custom-thing\nregistry:\n  backend: local\nnodes:\n  _root:\n    paths: [\"**\"]\n    owner: custom-owner\n"
    (root / "guidefold.yaml").write_text(custom)
    _init(gf, monkeypatch, root)
    assert (root / "guidefold.yaml").read_text() == custom


def test_init_merges_existing_claude_settings_without_clobbering(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir(parents=True)
    (root / ".claude").mkdir()
    existing = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]},
    }
    (root / ".claude" / "settings.json").write_text(json.dumps(existing, indent=2))
    _init(gf, monkeypatch, root)
    merged = json.loads((root / ".claude" / "settings.json").read_text())
    # unrelated top-level key preserved
    assert merged["permissions"] == {"allow": ["Bash(ls:*)"]}
    # pre-existing hook event preserved
    assert merged["hooks"]["Stop"] == [{"hooks": [{"type": "command", "command": "echo done"}]}]
    # guidefold hook events added
    assert "SessionStart" in merged["hooks"]
    assert "UserPromptSubmit" in merged["hooks"]
    assert any("scripts/guidefold hook" in json.dumps(e) for e in merged["hooks"]["SessionStart"])


def test_init_gitignore_appended_not_rewritten(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    (root / ".gitignore").write_text("node_modules/\n*.pyc\n")
    _init(gf, monkeypatch, root)
    text = (root / ".gitignore").read_text()
    assert "node_modules/" in text
    assert "*.pyc" in text
    assert ".guidefold/" in text


def test_init_publisher_override(gf, tmp_path, monkeypatch):
    root = tmp_path / "whatever-dir-name"
    root.mkdir()
    _init(gf, monkeypatch, root, publisher="Explicit Corp")
    text = (root / "guidefold.yaml").read_text()
    assert "publisher: explicit-corp" in text


def test_init_harness_claude_only_installs_only_that_hook(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root, harness="claude")
    assert (root / ".claude" / "settings.json").is_file()
    assert not (root / ".github" / "hooks" / "guidefold.json").exists()
    assert not (root / ".codex" / "hooks.json").exists()


# --- reconciling a partial or drifted install -------------------------------------------------
# Raised on the public repo: `init` writes several files and merges hook config; if a later write
# fails after guidefold.yaml and the bootstrap files have landed, a rerun has to reconcile that
# partial install rather than declare "already exists" or append a second guidefold hook entry.

MARKER = ".agents/skills/guidefold/scripts/guidefold"


def _guidefold_entries(settings: dict, event: str):
    return [e for e in settings.get("hooks", {}).get(event, []) if MARKER in json.dumps(e)]


def test_init_restores_a_file_missing_from_a_partial_skill_dir(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    victim = root / ".agents/skills/guidefold/SKILL.md"
    assert victim.is_file()
    victim.unlink()
    _init(gf, monkeypatch, root)
    assert victim.is_file(), "a rerun must restore a file an interrupted copy never wrote"


def test_init_keeps_a_locally_modified_skill_file(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    edited = root / ".agents/skills/guidefold/SKILL.md"
    edited.write_text(edited.read_text() + "\n<!-- local edit -->\n")
    before = edited.read_text()
    _init(gf, monkeypatch, root)
    assert edited.read_text() == before, "a rerun must not clobber a file the consumer edited"


def test_init_writes_an_install_manifest(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    manifest = json.loads((root / ".agents/skills/guidefold/INSTALL-MANIFEST.json").read_text())
    assert manifest["format"] == gf.INSTALL_MANIFEST_FORMAT
    assert ".agents/skills/guidefold/SKILL.md" in manifest["files"]
    assert manifest["hooks"][".claude/settings.json"] == "claude.settings.json"


def test_init_replaces_a_stale_guidefold_hook_entry(gf, tmp_path, monkeypatch):
    """Template drift is the duplicate path: an older guidefold version left an entry that is
    no longer byte-identical to the shipped template, so equality-based dedupe appends a second
    one and the hook fires twice."""
    root = tmp_path / "acme"
    root.mkdir()
    (root / ".claude").mkdir()
    stale = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": MARKER + " hook", "timeout": 5}]},
            ],
        },
    }
    (root / ".claude" / "settings.json").write_text(json.dumps(stale, indent=2))
    _init(gf, monkeypatch, root)
    merged = json.loads((root / ".claude" / "settings.json").read_text())
    ours = _guidefold_entries(merged, "SessionStart")
    assert len(ours) == 1, f"expected exactly one guidefold SessionStart entry, got {ours}"
    assert ours[0]["hooks"][0]["timeout"] == 15, "the stale entry must be replaced by the template"


def test_init_leaves_foreign_hook_entries_in_the_same_event(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    (root / ".claude").mkdir()
    foreign = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}
    (root / ".claude" / "settings.json").write_text(json.dumps(foreign, indent=2))
    _init(gf, monkeypatch, root)
    merged = json.loads((root / ".claude" / "settings.json").read_text())
    assert {"hooks": [{"type": "command", "command": "echo hi"}]} in merged["hooks"]["SessionStart"]
    assert len(_guidefold_entries(merged, "SessionStart")) == 1


def test_init_fails_loudly_when_a_hook_file_cannot_be_parsed(gf, tmp_path, monkeypatch):
    """An interrupted write leaves truncated JSON. Reporting that as a warning and exiting 0
    is how a broken install survives a CI retry unnoticed."""
    root = tmp_path / "acme"
    root.mkdir()
    (root / ".claude").mkdir()
    truncated = '{\n  "hooks": {\n    "SessionStart": [\n      { "hoo'
    (root / ".claude" / "settings.json").write_text(truncated)
    with pytest.raises(SystemExit) as exc:
        _init(gf, monkeypatch, root, harness="claude")
    assert exc.value.code != 0
    assert (root / ".claude" / "settings.json").read_text() == truncated


def test_init_leaves_no_temporary_files_behind(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    leftovers = [p.name for p in root.rglob("*") if ".guidefold-tmp" in p.name]
    assert leftovers == []


def test_atomic_write_keeps_the_old_content_when_the_write_fails(gf, tmp_path, monkeypatch):
    import os as _os
    dest = tmp_path / "settings.json"
    dest.write_text("original\n")

    def boom(_fd):
        raise OSError("disk full")

    monkeypatch.setattr(_os, "fsync", boom)
    with pytest.raises(OSError):
        gf._atomic_write_bytes(dest, b"replacement\n")
    assert dest.read_text() == "original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
