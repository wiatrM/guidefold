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


# 2026-09-15 rehearsal: `install` ends in `materialize`, and `build_card` sorted each node's
# skills with a bare `sorted()` over `(name, frontmatter)` pairs. Two skills of one node may
# carry the same name (this repository holds `security-baseline` both in `.agents/skills/` and
# inside the Meridian fixture); Python then compared the two frontmatter dicts and the whole
# command died with `TypeError: '<' not supported between instances of 'dict' and 'dict'`.
def test_install_survives_two_skills_of_one_node_sharing_a_name(gf, tmp_path, monkeypatch, capsys):
    root = _consumer(tmp_path)
    # The two cards must not be byte-identical: tuple comparison only reaches the dicts when
    # the names tie AND the frontmatter differs, which is exactly the real shape.
    for where, what in ((".agents/skills/security-baseline", "the repository's own rules"),
                        ("vendor/example/.agents/skills/security-baseline", "the vendored copy")):
        d = root / where
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: security-baseline\n"
            "description: \"[acme] Security rules for " + what + ": no secrets in the browser. "
            "Use when touching auth.\"\n"
            "metadata:\n  scope: _root\n  owner: platform\n  status: active\n---\n\nBody.\n",
            encoding="utf-8")
    monkeypatch.chdir(root)
    assert _run(gf.cmd_install, _args(api="https://api.example", org="acme", repo="monorepo")) == 0
    assert "+ create" in capsys.readouterr().out


# 2026-09-15 rehearsal: with a personal token from `guidefold login`, the CLI sends
# `X-Guidefold-Org` / `X-Guidefold-Repo` on every service call (API-CONTRACT §2/§3).
# `resolve_search_config` derived the repo from the CHECKOUT's name alone, ignoring
# `GUIDEFOLD_REPO_ID` and guidefold.yaml's `service.repo` — the precedence
# `resolve_service_config` documents three lines above it. A clone whose directory is not named
# exactly like the repo id (the normal case: `gf-pilot-core` for repo id `guidefold`) sent the
# wrong header, the API answered 403, and `guidefold load` printed
# "service USE failed (auth)" — an authentication problem that was not one.
def test_search_config_takes_the_repo_id_from_config_not_from_the_checkout_name(
        gf, tmp_path, monkeypatch):
    root = tmp_path / "some-clone-directory"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n"
        "service:\n  api: https://api.example\n  org: acme\n  repo: monorepo\n"
        "search:\n  backend: service\n  url: https://api.example\n")
    creds = tmp_path / "credentials.json"
    creds.write_text(json.dumps({"https://api.example": {
        "org": "acme", "token": "gf_" + "x" * 32,
        "orgs": [{"slug": "acme", "org_id": "o1", "role": "owner", "name": "acme"}]}}))
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(creds))
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    monkeypatch.delenv("GUIDEFOLD_REPO_ID", raising=False)

    cfg = gf.load_map(root)
    resolved = gf.resolve_search_config(cfg, profile="interactive", root=root)
    assert resolved["token_source"] == "login"
    assert resolved["repo"] == "monorepo", "the repo id comes from service.repo, not the directory"

    monkeypatch.setenv("GUIDEFOLD_REPO_ID", "from-env")
    assert gf.resolve_search_config(cfg, profile="interactive", root=root)["repo"] == "from-env"


# ---------------------------------------------------------------- D16 (rehearsal v2, 2026-09-15)
# `guidefold install --harness claude` ended with `materialize/index: skipped (no guidefold.yaml
# yet)` in a repository that ADR-0050 says never needs the file. Both commands work perfectly
# well on the inferred map — run by hand they wrote the full set of cards and a 109-card index —
# so the only thing between the owner and a working hook was a gate on a file the product no
# longer requires. Until someone ran `guidefold index` by hand, the harness stayed idle.

def _zero_config_repo(tmp_path: Path) -> Path:
    """A git repository with skills in two directories and NO guidefold.yaml."""
    import subprocess
    root = tmp_path / "zero-config"
    for where, name, desc in (
            (".agents/skills/deploy-runbook", "deploy-runbook",
             "Deploy the service to the cluster with helm and argocd. Use when releasing."),
            ("docs/.agents/skills/doc-rules", "doc-rules",
             "How documents are structured and reviewed here. Use when writing docs.")):
        d = root / where
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {json.dumps(desc)}\n"
            "metadata:\n  status: active\n---\n\n## Steps\n\n1. Do the thing.\n",
            encoding="utf-8")
    for cmd in (["init", "-q"], ["add", "-A"],
                ["-c", "user.email=t@example", "-c", "user.name=t", "commit", "-qm", "zero config"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)
    return root


def test_install_builds_the_index_in_a_repository_with_no_guidefold_yaml(
        gf, tmp_path, monkeypatch, capsys):
    root = _zero_config_repo(tmp_path)
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    monkeypatch.chdir(root)

    assert _run(gf.cmd_install, _args()) == 0
    out = capsys.readouterr().out
    assert "skipped (no guidefold.yaml yet)" not in out
    # the same inferred-map line `doctor` prints, so the owner sees which map was used
    assert "no guidefold.yaml — inferred" in out
    assert "skill directories" in out

    sha = gf._git_head_short(root)
    dest = gf.index_cache_dir(sha)
    assert (dest / "manifest.json").is_file(), "install must build the index artifact for this sha"
    nodes = json.loads((dest / "nodes.json").read_text(encoding="utf-8"))
    assert "docs" in nodes, f"the inferred node for docs/ must be in the artifact: {sorted(nodes)}"
    # the hook resolves its scope from that artifact alone (E1.5) — no guidefold.yaml anywhere
    idx = gf.load_index_artifact(dest)
    assert gf.node_for({"nodes": idx.nodes}, "docs") == "docs"
    assert not (root / "guidefold.yaml").exists()


# ------------------------------- ADR-0050 §4: service coordinates without a guidefold.yaml
# Rehearsal v2 workaround 2: with no file there was no `service:`/`search:` block, so `find`,
# `load` and the hook ran local and nothing reached the ledger — and nothing in `install` or
# `doctor` said so. Both now print the resolved SEARCH backend and which tier it came from.

def test_install_and_doctor_name_the_service_the_hook_will_use_without_a_yaml_file(
        gf, tmp_path, monkeypatch, capsys):
    root = _zero_config_repo(tmp_path)
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    creds = tmp_path / "credentials.json"
    creds.write_text(json.dumps({"https://api.example.com": {
        "org": "cloudfloo", "token": "gf_" + "y" * 32,
        "orgs": [{"slug": "cloudfloo", "org_id": "o1", "role": "owner", "name": "cloudfloo"}]}}))
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(creds))
    monkeypatch.setenv("GUIDEFOLD_REPO_ID", "guidefold")
    monkeypatch.chdir(root)

    assert _run(gf.cmd_install, _args()) == 0
    out = capsys.readouterr().out
    assert "hook search: service https://api.example.com" in out
    assert "source=login" in out and "org=cloudfloo" in out and "repo=guidefold" in out
    assert "gf_" not in out, "the bearer token is never printed"

    checks = {c["name"]: c for c in _doctor_checks(gf, capsys)}
    assert checks["search-config"]["detail"].startswith("service https://api.example.com")
    assert "source=login" in checks["search-config"]["detail"]
    assert checks["search-token"]["status"] == "ok"


def test_doctor_says_local_when_nothing_configures_a_service(gf, tmp_path, monkeypatch, capsys):
    root = _zero_config_repo(tmp_path)
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    monkeypatch.chdir(root)
    checks = {c["name"]: c for c in _doctor_checks(gf, capsys)}
    assert checks["search-config"]["status"] == "ok"
    assert checks["search-config"]["detail"].startswith("local — no hosted SEARCH service")


def _doctor_checks(gf, capsys):
    capsys.readouterr()
    _run(gf.cmd_doctor, SimpleNamespace(json=True, path=None))
    return json.loads(capsys.readouterr().out)["checks"]
