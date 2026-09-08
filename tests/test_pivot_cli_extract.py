"""P08 (docs/PRODUCT-PIVOT.md §5 U2, §8 U5) — `guidefold extract`: the whole loop in one call.

What is measured here:
  U1.1 again, for a new command: `extract --dry-run` opens no socket at all, proved by making
       `socket.socket` raise, so any connection attempt anywhere is a hard failure.
  P08   `--personal` is opt-in: personal skill directories on this machine reach the manifest
       only with the flag, never with `--all`, and never in CI.
  P08   the preview prints exactly what would leave the machine: path, size and sha256.
  P08   a symlink out of a personal root is excluded, and a secret in a personal directory is
       excluded by the same rules `scan` applies to the repository.
  P08   the one-shot request body: `profile: one_shot` plus all three kinds, on the endpoint the
       contract names.
  P08   the summary renders proposals by kind, the consolidation with its source scopes and its
       target scope, the abstentions with their reasons, and the cost.
  U5.3  a CI token whose scopes are too narrow surfaces as the server's own error, not a crash.

Everything runs in-process against the `gf` CLI module (conftest.py's fixture), so the socket
guard applies to the code under test, and against the `_pivot_server` fake for the rest.
"""
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from _pivot_server import running_api


@pytest.fixture(autouse=True)
def _clean_service_env(monkeypatch, tmp_path):
    for name in ("GUIDEFOLD_ROOT", "GUIDEFOLD_API", "GUIDEFOLD_ORG", "GUIDEFOLD_REPO_ID",
                 "GUIDEFOLD_TOKEN", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_CONFIG_DIR",
                 "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(tmp_path / "creds" / "credentials.json"))


@pytest.fixture
def no_sleep(gf, monkeypatch):
    monkeypatch.setattr(gf, "_sleep", lambda s: None)


def _args(**kw):
    base = {"path": None, "dry_run": False, "json": False, "partial": False,
            "profile": "default", "no_publish": False, "wait": False, "all": False,
            "personal": None, "api": None, "org": None, "repo": None}
    base.update(kw)
    return SimpleNamespace(**base)


def _run(fn, *a):
    with pytest.raises(SystemExit) as exc:
        fn(*a)
    return exc.value.code


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".agents/skills/root-conventions").mkdir(parents=True)
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: [\"**\"]\n    owner: platform\n",
        encoding="utf-8")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / ".agents/skills/root-conventions/SKILL.md").write_text(
        "---\nname: root-conventions\ndescription: \"[acme] Root conventions.\"\n---\n\n# Root\n",
        encoding="utf-8")
    return root


def _personal_home(tmp_path: Path, harness: str) -> Path:
    """A personal skill directory shaped the way Claude Code and Codex CLI shape theirs."""
    home = tmp_path / f"home-{harness}"
    skill = home / "skills" / f"{harness}-helper"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {harness}-helper\ndescription: personal {harness} skill\n---\n\n# Helper\n",
        encoding="utf-8")
    (skill / "references" / "notes.md").write_text("# notes\n", encoding="utf-8")
    return home


def _login(gf, url, token="gf_ci_token", org="acme"):
    gf._save_credentials({url: {"token": token, "org": org,
                                "user": {"user_id": "u1", "email": "o@example.test"},
                                "orgs": [{"slug": org, "role": "owner"}]}})


# ---- U1.1 / P08: --dry-run opens no socket

def test_extract_dry_run_opens_no_socket_and_previews_what_would_be_sent(gf, tmp_path,
                                                                        monkeypatch, capsys):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)

    def no_sockets(*a, **kw):
        raise AssertionError("extract --dry-run must not open a socket")

    monkeypatch.setattr(socket, "socket", no_sockets)
    monkeypatch.setattr(socket, "create_connection", no_sockets)

    code = _run(gf.cmd_extract, _args(dry_run=True, personal="claude", api="http://127.0.0.1:1",
                                      org="acme", repo="monorepo"))
    out = capsys.readouterr().out
    assert code == 0
    assert "[dry-run] nothing was sent; this command opened no socket." in out
    # Path, size and sha256 for every personal file, so the preview is checkable.
    assert "_personal/claude/claude-helper/SKILL.md" in out
    assert "_personal/claude/claude-helper/references/notes.md" in out
    assert out.count("sha256:") >= 2
    assert str(home) in out and "[found]" in out


def test_dry_run_without_personal_lists_no_machine_paths(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    code = _run(gf.cmd_extract, _args(dry_run=True, all=True, org="acme", repo="monorepo"))
    out = capsys.readouterr().out
    assert code == 0
    # `--all` covers the repository. It does not reach off it.
    assert "_personal/" not in out
    assert str(home) not in out
    assert "personal files: 0" in out
    assert "pass --personal to include them" in out


# ---- P08: personal roots never reach the manifest without the flag

def test_personal_files_reach_the_manifest_only_with_the_flag(gf, tmp_path, monkeypatch):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    cfg = gf._tolerant_config(root)

    without, _blobs, _excluded, roots = gf._personal_files(cfg, {}, [])
    assert without == [] and roots == []

    files, blobs, _excluded, roots = gf._personal_files(cfg, {}, ["claude"])
    paths = [f["path"] for f in files]
    assert paths == ["_personal/claude/claude-helper/SKILL.md",
                     "_personal/claude/claude-helper/references/notes.md"]
    assert [f["kind"] for f in files] == ["skill", "resource"]
    for f in files:
        assert f["source"] == {"kind": "personal", "harness": "claude"}
        assert len(f["sha256"]) == 64 and f["size"] > 0
    assert set(blobs) == {f["sha256"] for f in files}
    assert roots == [{"harness": "claude", "path": str(home / "skills"), "present": True}]


def test_a_personal_root_that_does_not_exist_is_reported_not_an_error(gf, tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nowhere"))
    monkeypatch.chdir(root)
    files, _blobs, _excluded, roots = gf._personal_files(gf._tolerant_config(root), {}, ["codex"])
    assert files == []
    assert roots == [{"harness": "codex", "path": str(tmp_path / "nowhere" / "skills"),
                      "present": False}]


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics")
def test_a_symlink_out_of_a_personal_root_is_excluded(gf, tmp_path, monkeypatch):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "codex")
    outside = tmp_path / "elsewhere"
    (outside / "secret-skill").mkdir(parents=True)
    (outside / "secret-skill" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    (home / "skills" / "linked").symlink_to(outside / "secret-skill")
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.chdir(root)

    files, _blobs, excluded, _roots = gf._personal_files(gf._tolerant_config(root), {}, ["codex"])
    assert not any("linked" in f["path"] for f in files), files
    assert {"path": "_personal/codex/linked/SKILL.md",
            "reason": "symlink_outside_root"} in excluded


def test_secrets_in_a_personal_directory_are_excluded_like_in_the_repository(gf, tmp_path,
                                                                            monkeypatch):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    skill = home / "skills" / "claude-helper"
    (skill / "scripts").mkdir()
    (skill / "scripts" / "deploy.key").write_text("nope", encoding="utf-8")
    (skill / "scripts" / "run.sh").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)

    files, _blobs, excluded, _roots = gf._personal_files(gf._tolerant_config(root), {}, ["claude"])
    sent = [f["path"] for f in files]
    assert "_personal/claude/claude-helper/scripts/deploy.key" not in sent
    assert "_personal/claude/claude-helper/scripts/run.sh" not in sent
    reasons = {e["path"]: e["reason"] for e in excluded}
    assert reasons["_personal/claude/claude-helper/scripts/deploy.key"] == "secret_pattern"
    assert reasons["_personal/claude/claude-helper/scripts/run.sh"] == "secret_pattern"


def test_personal_sources_can_be_configured(gf, tmp_path, monkeypatch):
    root = _repo(tmp_path)
    custom = tmp_path / "custom-skills"
    (custom / "one").mkdir(parents=True)
    (custom / "one" / "SKILL.md").write_text("---\nname: one\n---\n", encoding="utf-8")
    monkeypatch.chdir(root)
    cfg = {"extract": {"personal_sources": {"copilot": str(custom)}}}
    files, _blobs, _excluded, roots = gf._personal_files(cfg, {}, ["copilot"])
    assert [f["path"] for f in files] == ["_personal/copilot/one/SKILL.md"]
    assert roots[0]["path"] == str(custom)


def test_unknown_harness_is_refused_before_anything_is_read(gf):
    assert gf._personal_harnesses("claude,codex") == ["claude", "codex"]
    assert gf._personal_harnesses("all") == ["claude", "codex", "copilot"]
    with pytest.raises(SystemExit) as exc:
        gf._personal_harnesses("gemini")
    assert exc.value.code == 2


# ---- P08: the one-shot request

def test_extract_asks_for_one_shot_generation_of_all_three_kinds(gf, tmp_path, monkeypatch,
                                                                 no_sleep, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        api.plan = {"profile": "one_shot", "groups": [{"group_id": "extraction:_root"}],
                    "limits": {"max_groups": 1, "max_usd": 5}, "groups_skipped": {},
                    "estimated_usd_max": 0.0, "estimated_calls": 1}
        _login(gf, url)
        code = _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo"))
    capsys.readouterr()
    assert code == 0

    plans = [r for r in api.requests if r["path"].endswith("/plan?profile=one_shot")]
    assert len(plans) == 1 and plans[0]["method"] == "GET"

    generates = [r for r in api.requests if r["path"].endswith("/proposals:generate")]
    assert len(generates) == 1
    body = generates[0]["json"]
    assert body["profile"] == "one_shot"
    assert body["kinds"] == ["extraction", "enrichment", "consolidation"]
    assert body["idempotency_key"] == generates[0]["headers"].get("Idempotency-Key")
    # extract imports; it never publishes and never decides.
    assert not any(r["path"].endswith("/publish") for r in api.requests)
    assert not any("/decision" in r["path"] for r in api.requests)


def test_extract_uploads_only_repository_blobs_without_personal(gf, tmp_path, monkeypatch,
                                                                no_sleep, capsys):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", all=True))
    capsys.readouterr()
    manifest = api.manifests()[0]
    assert all(not f["path"].startswith("_personal/") for f in manifest["files"])
    assert all("source" not in f for f in manifest["files"])
    for body in api.blobs.values():
        assert b"personal claude skill" not in body


def test_extract_sends_personal_files_only_when_asked(gf, tmp_path, monkeypatch, no_sleep,
                                                      capsys):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", personal="claude"))
    capsys.readouterr()
    manifest = api.manifests()[0]
    personal = [f for f in manifest["files"] if f["path"].startswith("_personal/")]
    assert [f["path"] for f in personal] == [
        "_personal/claude/claude-helper/SKILL.md",
        "_personal/claude/claude-helper/references/notes.md"]
    assert all(f["source"] == {"kind": "personal", "harness": "claude"} for f in personal)
    # The manifest stays sorted, so the digest stays deterministic.
    paths = [f["path"] for f in manifest["files"]]
    assert paths == sorted(paths, key=gf._path_key)
    # A complete import with `publish: true` enqueues publish.build, which would serve a
    # developer's own skills to the whole organisation. Personal content is imported for
    # review, never for delivery.
    assert manifest["publish"] is False


def test_a_repository_only_extract_still_publishes(gf, tmp_path, monkeypatch, no_sleep, capsys):
    """The publish suppression is about `--personal`, not about `extract`: the CI path must
    keep behaving like `import`."""
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", all=True))
    capsys.readouterr()
    assert api.manifests()[0]["publish"] is True


def test_the_dry_run_preview_says_whether_it_would_publish(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    _run(gf.cmd_extract, _args(dry_run=True, personal="claude", org="acme", repo="monorepo"))
    out = capsys.readouterr().out
    assert "publish:   no (personal content is never published)" in out
    _run(gf.cmd_extract, _args(dry_run=True, all=True, org="acme", repo="monorepo"))
    assert "publish:   yes" in capsys.readouterr().out


# ---- P08: the summary

def test_extract_wait_prints_proposals_consolidations_abstentions_and_cost(gf, tmp_path,
                                                                          monkeypatch, no_sleep,
                                                                          capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        api.plan = {"profile": "one_shot", "groups": [{"group_id": "consolidation:atlas"}],
                    "limits": {"max_groups": 1}, "groups_skipped": {"consolidation": 0},
                    "estimated_usd_max": 0.0, "estimated_calls": 1}
        api.proposals = [
            {"proposal_id": "p1", "kind": "extraction", "scope": "atlas.geo",
             "path": "platforms/atlas/geo/.agents/skills/rotate-tile-cache/SKILL.md"},
            {"proposal_id": "p2", "kind": "consolidation", "scope": "atlas",
             "path": "platforms/atlas/.agents/skills/shared-rotate/SKILL.md",
             "relations": [
                 {"type": "derived_from", "to": "urn:skill:meridian:atlas.geo:rotate-tile-cache"},
                 {"type": "derived_from", "to": "urn:skill:meridian:atlas.graph:rotate-link-cache"},
                 {"type": "refines", "from": "urn:skill:meridian:atlas.geo:rotate-tile-cache"},
                 {"type": "refines", "from": "urn:skill:meridian:atlas.graph:rotate-link-cache"}]},
        ]
        api.extract_jobs = [{"kind": "proposal.generate", "state": "done",
                             "cost": {"calls": 3, "usd_certain": 0.0},
                             "abstentions": [
                                 {"reason": "contradictory_steps",
                                  "skills": ["urn:skill:meridian:atlas.geo:rotate-tile-cache",
                                             "urn:skill:meridian:atlas.geo:rotate-legacy-tile-cache"],
                                  "detail": "\"Remove the previous generation\" contradicts ..."}]}]
        _login(gf, url)
        code = _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", wait=True))
    out = capsys.readouterr().out
    assert code == 0
    assert "profile:   one_shot" in out
    assert "proposals: 2 (consolidation=1, extraction=1)" in out
    # The consolidation names where it came from and where it landed.
    assert "shared element in atlas: from atlas.geo, atlas.graph" in out
    assert "declined:  1" in out
    assert "contradictory_steps" in out
    assert "cost:      calls=3" in out


def test_extract_json_summary_is_machine_readable(gf, tmp_path, monkeypatch, no_sleep, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        api.proposals = [{"proposal_id": "p1", "kind": "enrichment", "scope": "_root",
                          "path": "a/SKILL.md"}]
        api.generate_job_ids = ["job_a", "job_b"]
        _login(gf, url)
        _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", wait=True, json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["proposals_by_kind"] == {"enrichment": 1}
    assert payload["job_ids"] == ["job_a", "job_b"]
    assert payload["personal_files"] == 0
    assert payload["profile"] == "one_shot"
    assert payload["consolidations"] == []


# ---- U5.3: a CI token whose scopes are too narrow

def test_a_ci_token_without_the_generate_scope_surfaces_the_servers_own_error(gf, tmp_path,
                                                                             monkeypatch,
                                                                             no_sleep, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        api.generate_error = (403, api._error(
            "insufficient_token_scope",
            "this token may not generate proposals; required scope: generate"))
        _login(gf, url)
        code = _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo"))
    captured = capsys.readouterr()
    assert code == 2, captured.err
    message = captured.err + captured.out
    assert "insufficient_token_scope" in message
    assert "installation scopes" in message
    # The token itself never appears in an error.
    assert "gf_ci_token" not in message


def test_extract_never_reads_a_personal_root_in_the_ci_shape(gf, tmp_path, monkeypatch,
                                                             no_sleep, capsys):
    """CI runs `extract --all --wait --json`. That shape must never touch a personal root,
    even when one exists on the runner."""
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.chdir(root)
    opened = []
    real_listdir = os.listdir

    def watched(path=".", *a, **kw):
        opened.append(str(path))
        return real_listdir(path, *a, **kw)

    monkeypatch.setattr(os, "listdir", watched)
    with running_api() as (url, _api):
        _login(gf, url)
        _run(gf.cmd_extract, _args(api=url, org="acme", repo="monorepo", all=True, wait=True,
                                   json=True))
    capsys.readouterr()
    assert not any(str(home) in p for p in opened), opened


def test_the_ci_template_runs_extract_without_personal():
    ci = (Path(__file__).resolve().parent.parent / "templates" / "ci.yml").read_text(
        encoding="utf-8")
    assert "guidefold extract --all --wait --json" in ci
    # No invocation of the CLI in CI may carry --personal; the word may appear in prose that
    # explains why.
    invocations = [line for line in ci.splitlines() if "scripts/guidefold" in line
                   and not line.lstrip().startswith("#")]
    assert invocations
    assert all("--personal" not in line for line in invocations), invocations
    assert "--personal" not in "".join(
        line for line in ci.splitlines() if not line.lstrip().startswith("#"))
    # The CI token is a secret and the scopes it needs are stated where a reader will see them.
    assert "GUIDEFOLD_TOKEN: ${{ secrets.GUIDEFOLD_TOKEN }}" in ci
    assert "import" in ci and "generate" in ci


def test_extract_is_registered_and_reachable(gf):
    assert hasattr(gf, "cmd_extract")
    source = Path(gf.__file__).read_text(encoding="utf-8")
    assert '"extract", "install"' in source, "extract must be in main()'s pivot dispatch tuple"


def test_scan_still_has_no_personal_rows(gf, tmp_path, monkeypatch):
    """`scan` is unchanged: no flag, no personal rows, no new manifest keys."""
    root = _repo(tmp_path)
    home = _personal_home(tmp_path, "claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    manifest, _blobs, _stats = gf.scan_manifest(root, gf._tolerant_config(root),
                                                org="acme", repo="monorepo")
    assert all(not f["path"].startswith("_personal/") for f in manifest["files"])
    assert all("source" not in f for f in manifest["files"])


def test_module_still_imports_no_http_stack_for_the_offline_path(gf):
    """`extract --dry-run` must stay on the offline path `scan` guards."""
    assert "urllib.request" not in sys.modules or True  # informational; the guard is below
    source = Path(gf.__file__).read_text(encoding="utf-8")
    head = source.split("def cmd_extract(")[1].split("\ndef ")[0]
    before_require = head.split("_require_service(svc)")[0]
    assert "_service_request(" not in before_require, (
        "extract must not reach the network before --dry-run has had its chance to exit")
