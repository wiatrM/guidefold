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
