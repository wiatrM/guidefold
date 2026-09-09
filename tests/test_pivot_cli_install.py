"""U5.1/U5.3 — `guidefold install` / `uninstall` / the pivot `doctor` checks.

The installer is the only pivot command that writes into a consumer repo, so the properties
under test are the ones a developer notices when it goes wrong: it is idempotent, it says
exactly what it changed, it never touches somebody else's settings, it can be undone, and it
refuses to delete a file that was edited after installation.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from _pivot_server import running_api


@pytest.fixture(autouse=True)
def _clean_service_env(monkeypatch, tmp_path):
    for name in ("GUIDEFOLD_ROOT", "GUIDEFOLD_API", "GUIDEFOLD_ORG", "GUIDEFOLD_REPO_ID",
                 "GUIDEFOLD_TOKEN", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(tmp_path / "creds" / "credentials.json"))


def _args(**kw):
    base = {"path": None, "harness": "claude", "dry_run": False,
            "api": None, "org": None, "repo": None, "json": False}
    base.update(kw)
    return SimpleNamespace(**base)


def _consumer(tmp_path: Path) -> Path:
    root = tmp_path / "consumer"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "# Guidefold hierarchy\npublisher: acme\n"
        "registry:\n  backend: local\n"
        "nodes:\n  _root:\n    paths: ['**']\n    owner: platform\n")
    return root


def _run(fn, *a):
    with pytest.raises(SystemExit) as exc:
        fn(*a)
    return exc.value.code


FOREIGN_SETTINGS = {
    "permissions": {"allow": ["Bash(ls:*)"]},
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "./my-own-hook"}]}]},
}


# --------------------------------------------------------------------------------- U5.1

def test_install_is_idempotent_and_the_second_run_reports_no_changes(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    first = capsys.readouterr().out
    assert "+ create" in first
    cli = root / ".agents/skills/guidefold/scripts/guidefold"
    assert cli.is_file() and os.access(cli, os.X_OK)

    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    second = capsys.readouterr().out
    assert "nothing to do" in second
    assert "+ create" not in second


def test_install_dry_run_writes_nothing(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    before = sorted(p.name for p in root.iterdir())
    assert _run(gf.cmd_install, _args(dry_run=True, api="https://api.example",
                                      org="acme", repo="monorepo")) == 0
    out = capsys.readouterr().out
    assert "[dry-run] nothing was written." in out
    assert sorted(p.name for p in root.iterdir()) == before
    assert not (root / ".agents").exists()
    assert "service:" not in (root / "guidefold.yaml").read_text()


def test_install_preserves_foreign_claude_settings_and_uninstall_restores_them(
        gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    settings = root / ".claude" / "settings.json"
    settings.parent.mkdir()
    original = json.dumps(FOREIGN_SETTINGS, indent=2) + "\n"
    settings.write_text(original)
    monkeypatch.chdir(root)

    assert _run(gf.cmd_install, _args(harness="claude", api="https://api.example",
                                      org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    merged = json.loads(settings.read_text())
    assert merged["permissions"] == FOREIGN_SETTINGS["permissions"]
    assert {"type": "command", "command": "./my-own-hook"} in merged["hooks"]["SessionStart"][0]["hooks"]
    assert any("scripts/guidefold" in json.dumps(entry) for entry in merged["hooks"]["SessionStart"])
    assert "UserPromptSubmit" in merged["hooks"]

    assert _run(gf.cmd_uninstall, _args(harness="claude")) == 0
    capsys.readouterr()
    restored = json.loads(settings.read_text())
    assert restored["permissions"] == FOREIGN_SETTINGS["permissions"]
    assert restored["hooks"]["SessionStart"] == FOREIGN_SETTINGS["hooks"]["SessionStart"]
    assert "UserPromptSubmit" not in restored["hooks"]
    assert not (root / ".agents/skills/guidefold").exists()
    assert "service:" not in (root / "guidefold.yaml").read_text()
    assert "publisher: acme" in (root / "guidefold.yaml").read_text()


def test_uninstall_refuses_to_delete_a_file_edited_after_install(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    edited = root / ".agents/skills/guidefold/SKILL.md"
    edited.write_text(edited.read_text() + "\n<!-- local edit -->\n")

    assert _run(gf.cmd_uninstall, _args(harness="claude")) == 0
    out = capsys.readouterr().out
    assert "modified since install" in out
    assert edited.is_file(), "an edited file must survive uninstall"
    assert not (root / ".agents/skills/guidefold/scripts/guidefold").exists()


def test_install_does_not_overwrite_a_locally_modified_package_file(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    target = root / ".agents/skills/guidefold/SKILL.md"
    target.write_text("locally rewritten\n")
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    out = capsys.readouterr().out
    assert "modified locally" in out
    assert target.read_text() == "locally rewritten\n"


# ---------------------------------------------------------------------- manifest + checksum

def test_install_manifest_records_hashes_and_the_package_checksum(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    manifest = json.loads((root / ".agents/skills/guidefold/INSTALL-MANIFEST.json").read_text())
    assert manifest["format"] == "guidefold-install-manifest-v1"
    assert manifest["harnesses"] == ["claude"]
    cli_rel = ".agents/skills/guidefold/scripts/guidefold"
    installed = (root / cli_rel).read_bytes()
    assert manifest["package_sha256"] == gf._sha256_bytes(installed)
    assert manifest["files"][cli_rel] == manifest["package_sha256"]
    for rel_path, digest in manifest["files"].items():
        assert gf._sha256_bytes((root / rel_path).read_bytes()) == digest
    assert "INSTALL-MANIFEST.json" not in json.dumps(manifest["files"])
    # No timestamp: re-installing must not make the manifest look changed.
    assert not any(k in manifest for k in ("installed_at", "timestamp"))


def test_service_block_is_written_without_secrets_and_keeps_the_rest_of_the_yaml(
        gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    gf._save_credentials({"https://api.example": {"token": "gf_secret_token", "org": "acme"}})
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    text = (root / "guidefold.yaml").read_text()
    assert "service:" in text and "api: https://api.example" in text
    assert "org: acme" in text and "repo: monorepo" in text
    assert "gf_secret_token" not in text
    assert "token" not in text
    assert "publisher: acme" in text and "# Guidefold hierarchy" in text
    import yaml
    parsed = yaml.safe_load(text)
    assert parsed["service"] == {"api": "https://api.example", "org": "acme", "repo": "monorepo"}
    assert parsed["registry"]["backend"] == "local"

    # Re-installing with different coordinates replaces the block instead of appending one.
    assert _run(gf.cmd_install, _args(api="https://api2.example", org="beta", repo="other")) == 0
    capsys.readouterr()
    text = (root / "guidefold.yaml").read_text()
    assert text.count("service:") == 1
    assert yaml.safe_load(text)["service"]["org"] == "beta"


# ------------------------------------------------------------------------------- copilot

def test_copilot_install_writes_the_explicit_find_load_section_and_removes_it_again(
        gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    instructions = root / ".github" / "copilot-instructions.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# House rules\n\nAlways run the linter.\n")
    monkeypatch.chdir(root)

    assert _run(gf.cmd_install, _args(harness="copilot", api="https://api.example",
                                      org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    text = instructions.read_text()
    assert "Always run the linter." in text
    assert "guidefold find" in text or "scripts/guidefold find" in text
    assert "<!-- guidefold:begin -->" in text
    assert (root / ".github/hooks/guidefold.json").is_file()

    assert _run(gf.cmd_uninstall, _args(harness="copilot")) == 0
    capsys.readouterr()
    text = instructions.read_text()
    assert "Always run the linter." in text
    assert "guidefold:begin" not in text
    assert not (root / ".github/hooks/guidefold.json").exists()


def test_gemini_install_is_explicit_and_uninstall_is_reversible(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(harness="gemini", api="https://api.example",
                                      org="acme", repo="monorepo")) == 0
    capsys.readouterr()
    manifest = json.loads((root / ".agents/skills/guidefold/INSTALL-MANIFEST.json").read_text())
    assert manifest["harnesses"] == ["gemini"]
    assert (root / "GEMINI.md").is_file()
    # Gemini reads the generated scope card; it has no context hook to wire.
    assert not (root / ".github/hooks/guidefold.json").exists()
    assert _run(gf.cmd_uninstall, _args(harness="gemini")) == 0
    capsys.readouterr()
    assert not (root / ".agents/skills/guidefold").exists()
    # Materialized scope cards are shared generated artifacts and are intentionally preserved;
    # uninstall removes only the adapter-owned package and harness wiring.
    assert (root / "GEMINI.md").is_file()


def test_installing_both_harnesses_keeps_the_package_until_the_last_uninstall(
        gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    for harness in ("claude", "copilot"):
        assert _run(gf.cmd_install, _args(harness=harness, api="https://api.example",
                                          org="acme", repo="monorepo")) == 0
        capsys.readouterr()
    manifest = json.loads((root / ".agents/skills/guidefold/INSTALL-MANIFEST.json").read_text())
    assert manifest["harnesses"] == ["claude", "copilot"]

    assert _run(gf.cmd_uninstall, _args(harness="claude")) == 0
    capsys.readouterr()
    assert (root / ".agents/skills/guidefold/scripts/guidefold").is_file()
    assert not (root / ".claude/settings.json").exists()

    assert _run(gf.cmd_uninstall, _args(harness="copilot")) == 0
    capsys.readouterr()
    assert not (root / ".agents/skills/guidefold").exists()


def test_uninstall_without_a_manifest_deletes_nothing(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    (root / ".agents" / "skills" / "guidefold").mkdir(parents=True)
    (root / ".agents" / "skills" / "guidefold" / "SKILL.md").write_text("someone else's\n")
    monkeypatch.chdir(root)
    assert _run(gf.cmd_uninstall, _args(harness="claude")) == 0
    assert "refusing to delete" in capsys.readouterr().out
    assert (root / ".agents/skills/guidefold/SKILL.md").read_text() == "someone else's\n"


# --------------------------------------------------------------------------------- doctor

def test_doctor_reports_service_org_repo_token_scopes_and_the_installed_package(
        gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        gf._save_credentials({url: {"token": "gf_secret_token", "org": "acme",
                                    "user": {"id": "u1", "email": "owner@acme.test"},
                                    "orgs": [{"slug": "acme", "role": "owner"}]}})
        assert _run(gf.cmd_install, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        _run(gf.cmd_doctor, SimpleNamespace(json=False))
        out = capsys.readouterr().out
    # The exit code is decided by the pre-existing checks (this bare fixture has no .gitignore
    # and its bootstrap SKILL.md is not stamped for this publisher); what this test owns is that
    # every pivot line is present and correct.
    assert f"api={url} org=acme repo=monorepo" in out
    assert "/health/ready → HTTP 200" in out
    assert "user=owner@acme.test" in out and "role=owner" in out
    assert "scopes=search, use, events" in out
    assert "gf_secret_token" not in out
    assert "adapter-install" in out and "all files match the manifest" in out
    assert "capabilities-claude" in out and "hook_context_injection=true" in out
    assert "capabilities-copilot" in out and "explicit_find_load=true" in out


def test_doctor_flags_an_unreachable_api_and_a_modified_adapter(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, _api):
        gf._save_credentials({url: {"token": "gf_t", "org": "acme"}})
        assert _run(gf.cmd_install, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
    # The server is gone now; doctor must fail loudly with a fix, not crash.
    (root / ".agents/skills/guidefold/SKILL.md").write_text("edited\n")
    code = _run(gf.cmd_doctor, SimpleNamespace(json=True))
    payload = json.loads(capsys.readouterr().out)
    checks = {c["name"]: c for c in payload["checks"]}
    assert code == 1
    assert checks["service-api"]["status"] == "fail"
    assert checks["service-api"]["fix"]
    assert checks["adapter-install"]["status"] == "warn"
    assert "1 modified" in checks["adapter-install"]["detail"]


def test_doctor_without_a_hosted_api_stays_green(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    monkeypatch.chdir(root)
    code = _run(gf.cmd_doctor, SimpleNamespace(json=True))
    payload = json.loads(capsys.readouterr().out)
    checks = {c["name"]: c for c in payload["checks"]}
    assert checks["service-config"]["status"] == "warn"
    assert checks["service-api"]["status"] == "ok"
    assert checks["adapter-install"]["status"] == "warn"
    assert all(c["status"] != "fail" for name, c in checks.items()
               if name.startswith(("service-", "adapter-", "capabilities-")))
    assert code in (0, 1)   # other, pre-existing checks decide the exit code here
