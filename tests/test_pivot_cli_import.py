"""U1/U5 — the network half of the pivot CLI: `login`/`org`, `import`/`sync`/`status`,
`proposals`.

Everything runs against a real `http.server` speaking the management-API contract
(`tests/_pivot_server.py`), in-process against the `gf` CLI module, so what is asserted is the
bytes the CLI actually put on a socket.

AC covered here:
  U1.1  the manifest `import` sends is byte-identical to the one `scan --json` printed.
  U1.3  no excluded path's bytes are ever PUT (the server records every upload).
  U1.4  a second `sync` of an unchanged tree uploads 0 new blobs.
  U1.5  an interrupted upload followed by a re-run yields ONE import id and no duplicate upload.
  U5.2  device login handles pending / slow_down / denied / expired, and stores the token in a
        0600 file that is never inside the repository.
"""
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from _pivot_server import ManagementAPI, running_api


# ---------------------------------------------------------------------------------- fixtures

@pytest.fixture(autouse=True)
def _clean_service_env(monkeypatch, tmp_path):
    for name in ("GUIDEFOLD_ROOT", "GUIDEFOLD_API", "GUIDEFOLD_ORG", "GUIDEFOLD_REPO_ID",
                 "GUIDEFOLD_TOKEN", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(tmp_path / "creds" / "credentials.json"))


@pytest.fixture
def no_sleep(gf, monkeypatch):
    """Device polling and blob backoff go through gf._sleep; record instead of waiting."""
    slept = []
    monkeypatch.setattr(gf, "_sleep", lambda s: slept.append(s))
    return slept


def _args(**kw):
    base = {"path": None, "dry_run": False, "json": False, "partial": False, "profile": "default",
            "no_publish": False, "wait": False, "api": None, "org": None, "repo": None,
            "all": False, "write": False, "base_check": None}
    base.update(kw)
    return SimpleNamespace(**base)


def _repo(tmp_path: Path, *, secrets=True) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n")
    (root / "README.md").write_text("# acme monorepo\n")
    skill = root / ".agents" / "skills" / "root-conventions"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: root-conventions\n---\nbody\n")
    if secrets:
        (root / ".env").write_text("API_TOKEN=super-secret-value\n")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "README.md").write_text("# vendored dependency\n")
    return root


def _login(gf, url, token="gf_test_token", org="acme"):
    gf._save_credentials({url: {"token": token, "org": org,
                                "user": {"id": "u1", "email": "owner@acme.test"},
                                "orgs": [{"org_id": "o1", "slug": org, "name": "Acme",
                                          "role": "owner"}]}})


def _run(fn, *a):
    with pytest.raises(SystemExit) as exc:
        fn(*a)
    return exc.value.code


# --------------------------------------------------------------------------------- U1.1/U1.3

def test_import_sends_exactly_the_manifest_scan_printed(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_scan, _args(json=True, api=url, org="acme", repo="monorepo")) == 0
        scanned = json.loads(capsys.readouterr().out)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        sent = api.manifests()
    assert len(sent) == 1
    assert gf._canonical_json(sent[0]) == gf._canonical_json(scanned)
    # The idempotency key the CLI used is the digest of exactly those bytes.
    post = next(r for r in api.requests if r["method"] == "POST" and r["path"].endswith("/imports"))
    assert post["json"]["idempotency_key"] == gf._sha256_bytes(gf._canonical_json(scanned))
    assert post["headers"]["Idempotency-Key"] == post["json"]["idempotency_key"]


def test_no_excluded_bytes_are_ever_uploaded(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        uploaded = b"".join(api.blobs.values())
        paths_in_manifest = {f["path"] for f in api.manifests()[0]["files"]}
    assert b"super-secret-value" not in uploaded
    assert b"vendored dependency" not in uploaded
    assert ".env" not in paths_in_manifest
    assert not any(p.startswith("node_modules") for p in paths_in_manifest)


def test_authorization_header_is_sent_and_the_token_never_reaches_stdout(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url, token="gf_super_secret_token")
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        out = capsys.readouterr()
        assert all(r["headers"].get("Authorization") == "Bearer gf_super_secret_token"
                   for r in api.requests if r["path"].startswith("/api/v1/orgs"))
    assert "gf_super_secret_token" not in out.out
    assert "gf_super_secret_token" not in out.err


# ------------------------------------------------------------------------------------- U1.4

def test_second_sync_of_an_unchanged_tree_uploads_zero_new_blobs(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_sync, _args(api=url, org="acme", repo="monorepo")) == 0
        first = capsys.readouterr().out
        n_first = len(api.puts())
        assert _run(gf.cmd_sync, _args(api=url, org="acme", repo="monorepo", json=True)) == 0
        second = json.loads(capsys.readouterr().out)
        n_second = len(api.puts()) - n_first
    assert n_first > 0 and "new_blobs" in first
    assert n_second == 0
    assert second["new_blobs"] == 0
    assert second["reused_blobs"] == second["unique_blobs"]
    assert second["uploaded_blobs"] == 0


# ------------------------------------------------------------------------------------- U1.5

def test_interrupted_upload_then_rerun_gives_one_import_and_no_duplicate_uploads(
        gf, tmp_path, monkeypatch, capsys, no_sleep):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        manifest, _blobs, _stats = gf.scan_manifest(root, gf._tolerant_config(root),
                                                    org="acme", repo="monorepo")
        second_sha = sorted(f["sha256"] for f in manifest["files"])[1]
        # The upload of one blob fails for good (more than the CLI's retry budget), exactly like
        # a connection dropped mid-import.
        api.fail_next_put(second_sha, times=gf.BLOB_RETRY_ATTEMPTS + 2)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 1
        capsys.readouterr()
        first_ids = set(api.imports)
        assert api.finalized == []

        api.fail_put_shas.clear()
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        assert set(api.imports) == first_ids, "the re-run created a second import"
        assert len(api.imports) == 1
        assert api.finalized == list(first_ids)
        # No blob was successfully stored twice: the re-run asked the server what was still
        # missing instead of replaying its own upload list.
        assert len(api.blob_puts) == len(set(api.blob_puts))


def test_a_transient_upload_failure_is_retried_within_the_budget(gf, tmp_path, monkeypatch,
                                                                 capsys, no_sleep):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        manifest, _b, _s = gf.scan_manifest(root, gf._tolerant_config(root),
                                            org="acme", repo="monorepo")
        api.fail_next_put(sorted(f["sha256"] for f in manifest["files"])[0], times=1)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        assert api.finalized
    assert no_sleep and no_sleep[0] == gf.BLOB_RETRY_BACKOFF_S


def test_a_renamed_skill_keeps_its_identity_through_an_alias(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    old = root / ".agents/skills/root-conventions"
    new = root / ".agents/skills/acme-conventions"
    old.rename(new)
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n"
        "import:\n  aliases:\n"
        "    - from: .agents/skills/root-conventions/SKILL.md\n"
        "      to: .agents/skills/acme-conventions/SKILL.md\n")
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        manifest = api.manifests()[0]
    assert manifest["aliases"] == [{"from": ".agents/skills/root-conventions/SKILL.md",
                                    "to": ".agents/skills/acme-conventions/SKILL.md"}]
    assert ".agents/skills/acme-conventions/SKILL.md" in {f["path"] for f in manifest["files"]}


# ------------------------------------------------------------------------- wait / status view

def test_wait_prints_the_per_file_result_and_the_publication_state(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo", wait=True)) == 0
        out = capsys.readouterr().out
        import_id = next(iter(api.imports))
    assert "state:     ready" in out
    assert "accepted=" in out
    assert "import.parse" in out and "publish.build" in out
    assert "state=published" in out
    assert import_id in out


def test_status_renders_the_same_view(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo")) == 0
        capsys.readouterr()
        import_id = next(iter(api.imports))
        assert _run(gf.cmd_status, _args(api=url, org="acme", repo="monorepo",
                                         import_id=import_id)) == 0
        out = capsys.readouterr().out
    assert f"import {import_id}" in out
    assert "state:" in out and "publication:" in out


def test_no_publish_is_carried_in_the_manifest(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        assert _run(gf.cmd_import, _args(api=url, org="acme", repo="monorepo",
                                          no_publish=True)) == 0
        capsys.readouterr()
    assert api.manifests()[0]["publish"] is False


def test_missing_org_is_a_config_error_not_a_request(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        gf._save_credentials({url: {"token": "gf_t"}})
        assert _run(gf.cmd_import, _args(api=url, repo="monorepo")) == 2
        assert api.requests == []
    assert "org" in capsys.readouterr().err


# ------------------------------------------------------------------------------------- U5.2

def _device(status, code=None, body=None):
    if body is not None:
        return status, body
    return status, {"error": {"code": code, "message": ""}, "code": code, "request_id": "req-test"}


def test_device_login_handles_pending_then_slow_down_then_success(gf, tmp_path, monkeypatch,
                                                                  capsys, no_sleep):
    monkeypatch.chdir(tmp_path)
    api = ManagementAPI()
    api.device_start = {"device_code": "dev-1", "user_code": "WXYZ-1234",
                        "verification_uri": "/organization?tab=integrations&device=WXYZ-1234",
                        "expires_in": 600, "interval": 5}
    api.device_token_script = [
        _device(400, "authorization_pending"),
        _device(400, "slow_down"),
        _device(200, body={"token": "gf_new_token", "token_id": "t1",
                           "user": {"id": "u1", "email": "owner@acme.test"},
                           "orgs": [{"org_id": "o1", "slug": "acme", "name": "Acme",
                                     "role": "owner"}]}),
    ]
    with running_api(api) as (url, _api):
        assert _run(gf.cmd_login, _args(api=url)) == 0
        out = capsys.readouterr().out
    assert "WXYZ-1234" in out
    assert url + "/organization?tab=integrations&device=WXYZ-1234" in out
    assert "gf_new_token" not in out                      # the token is never printed
    assert no_sleep == [5, 5, 10]                         # slow_down widened the interval
    stored = json.loads(Path(os.environ["GUIDEFOLD_CREDENTIALS"]).read_text())
    assert stored[url]["token"] == "gf_new_token"
    assert stored[url]["org"] == "acme"


@pytest.mark.parametrize("code,message", [("access_denied", "denied"),
                                          ("expired_token", "expired")])
def test_device_login_reports_denial_and_expiry_without_storing_anything(
        gf, tmp_path, monkeypatch, capsys, no_sleep, code, message):
    monkeypatch.chdir(tmp_path)
    api = ManagementAPI()
    api.device_token_script = [_device(400, code)]
    with running_api(api) as (url, _api):
        assert _run(gf.cmd_login, _args(api=url)) == 1
    err = capsys.readouterr().err
    assert message in err
    assert not Path(os.environ["GUIDEFOLD_CREDENTIALS"]).exists()


def test_device_login_gives_up_when_the_code_expires_locally(gf, tmp_path, monkeypatch,
                                                             capsys, no_sleep):
    monkeypatch.chdir(tmp_path)
    api = ManagementAPI()
    api.device_start = {"device_code": "dev-1", "user_code": "AAAA-0000",
                        "verification_uri": "/device", "expires_in": 0, "interval": 0}
    with running_api(api) as (url, _api):
        assert _run(gf.cmd_login, _args(api=url)) == 1
    assert "expired" in capsys.readouterr().err


def test_credentials_are_0600_and_never_inside_the_repository(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    api = ManagementAPI()
    api.device_token_script = [_device(200, body={"token": "gf_x", "user": {"email": "a@b.c"},
                                                   "orgs": [{"slug": "acme", "role": "owner"}]})]
    with running_api(api) as (url, _api):
        assert _run(gf.cmd_login, _args(api=url)) == 0
    path = Path(os.environ["GUIDEFOLD_CREDENTIALS"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not str(path.resolve()).startswith(str(root.resolve()))

    # Pointing the credentials file inside the work tree is refused, not silently obeyed.
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(root / ".guidefold-credentials.json"))
    with pytest.raises(SystemExit) as exc:
        gf._save_credentials({"x": {}}, root)
    assert exc.value.code == 2
    assert "inside the repository" in capsys.readouterr().err
    assert not (root / ".guidefold-credentials.json").exists()


def test_logout_clears_only_the_selected_api(gf, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    gf._save_credentials({"https://a.example": {"token": "t1"},
                          "https://b.example": {"token": "t2"}})
    assert _run(gf.cmd_logout, _args(api="https://a.example")) == 0
    left = json.loads(Path(os.environ["GUIDEFOLD_CREDENTIALS"]).read_text())
    assert set(left) == {"https://b.example"}
    capsys.readouterr()


def test_org_list_and_use_read_membership_from_the_api(gf, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with running_api() as (url, api):
        api.me = {"user": {"id": "u1", "email": "owner@acme.test"},
                  "orgs": [{"org_id": "o1", "slug": "acme", "name": "Acme", "role": "owner"},
                           {"org_id": "o2", "slug": "beta", "name": "Beta", "role": "member"}]}
        _login(gf, url, org="acme")
        assert _run(gf.cmd_org, _args(api=url, org_cmd="list")) == 0
        out = capsys.readouterr().out
        assert "acme" in out and "beta" in out and "owner" in out
        assert _run(gf.cmd_org, _args(api=url, org_cmd="use", slug="beta")) == 0
        capsys.readouterr()
        assert json.loads(Path(os.environ["GUIDEFOLD_CREDENTIALS"]).read_text())[url]["org"] == "beta"
        assert _run(gf.cmd_org, _args(api=url, org_cmd="use", slug="nope")) == 1
    assert "not one of your organisations" in capsys.readouterr().err


def test_precedence_is_flags_over_env_over_yaml_over_credentials(gf, tmp_path, monkeypatch):
    root = _repo(tmp_path)
    (root / "guidefold.yaml").write_text(
        "publisher: acme\nnodes:\n  _root:\n    paths: ['**']\n    owner: platform\n"
        "service:\n  api: https://yaml.example\n  org: yaml-org\n  repo: yaml-repo\n")
    monkeypatch.chdir(root)
    gf._save_credentials({"https://yaml.example": {"token": "cred-token", "org": "cred-org"}})
    cfg = gf._tolerant_config(root)

    from_yaml = gf.resolve_service_config(cfg, None, root)
    assert (from_yaml["api"], from_yaml["org"], from_yaml["repo"]) == (
        "https://yaml.example", "yaml-org", "yaml-repo")
    assert from_yaml["token"] == "cred-token" and from_yaml["token_source"] == "credentials"

    monkeypatch.setenv("GUIDEFOLD_ORG", "env-org")
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "env-token")
    from_env = gf.resolve_service_config(cfg, None, root)
    assert from_env["org"] == "env-org"
    assert from_env["token"] == "env-token" and from_env["token_source"] == "GUIDEFOLD_TOKEN"

    from_flags = gf.resolve_service_config(cfg, SimpleNamespace(api=None, org="flag-org", repo=None), root)
    assert from_flags["org"] == "flag-org"


# --------------------------------------------------------------------------------- proposals

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def test_proposals_apply_prints_a_diff_and_writes_only_with_write(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, secrets=False)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@e.st")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    monkeypatch.chdir(root)
    new_path = ".agents/skills/deploy-runbook/SKILL.md"
    with running_api() as (url, api):
        _login(gf, url)
        body = "---\nname: deploy-runbook\n---\nsteps\n"
        api.exports["exp1"] = {"export_id": "exp1", "base_commit": head,
                               "files": [{"path": new_path,
                                          "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                          "content": body}],
                               "patch": ""}
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1")) == 0
        out = capsys.readouterr().out
        assert "+++ b/" + new_path in out
        assert "Nothing was written" in out
        assert not (root / new_path).exists()

        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1",
                                            write=True)) == 0
        out = capsys.readouterr().out
    assert (root / new_path).read_text().startswith("---\nname: deploy-runbook")
    assert "wrote " + new_path in out
    assert "never commits" in out
    assert _git(root, "log", "--oneline").stdout.strip().count("\n") == 0   # still one commit


# S3 -- `path` comes straight from the server's export document and `--write` turns it into a
# filesystem write in the user's repository. Nothing checked containment, so
# `root / "../../.ssh/authorized_keys"` resolved outside the tree and mkdir(parents=True)
# created the directories to get there.
@pytest.mark.parametrize("bad", [
    "../escape.md",
    "docs/../../escape.md",
    "/etc/guidefold-escape",
    "a//b.md",
    "./a.md",
    "..",
])
def test_proposals_apply_refuses_a_path_outside_the_repository(gf, tmp_path, monkeypatch,
                                                               capsys, bad):
    root = _repo(tmp_path, secrets=False)
    monkeypatch.chdir(root)
    outside = tmp_path / "escape.md"
    with running_api() as (url, api):
        _login(gf, url)
        api.exports["exp1"] = {"export_id": "exp1", "base_commit": None,
                               "files": [{"path": bad, "content": "pwned\n"}], "patch": "x"}
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1",
                                            write=True, base_check=False)) == 2
    assert "refusing the export path" in capsys.readouterr().err
    assert not outside.exists()
    assert not (tmp_path / ".ssh").exists()


# S3 -- an export that omits `content` used to truncate the existing file to zero bytes
# (`str(entry.get("content") or "")`), and the sha256 the contract carries was never checked.
def test_proposals_apply_refuses_missing_content_and_a_wrong_digest(gf, tmp_path, monkeypatch,
                                                                    capsys):
    root = _repo(tmp_path, secrets=False)
    monkeypatch.chdir(root)
    target = root / "docs" / "keep.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original\n", encoding="utf-8")
    with running_api() as (url, api):
        _login(gf, url)
        api.exports["exp1"] = {"export_id": "exp1", "base_commit": None,
                               "files": [{"path": "docs/keep.md"}], "patch": "x"}
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1",
                                            write=True, base_check=False)) == 1
        assert "carries no content" in capsys.readouterr().err
        assert target.read_text(encoding="utf-8") == "original\n"

        api.exports["exp2"] = {"export_id": "exp2", "base_commit": None,
                               "files": [{"path": "docs/keep.md", "content": "replaced\n",
                                          "sha256": "0" * 64}], "patch": "x"}
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp2",
                                            write=True, base_check=False)) == 1
        assert "declared sha256" in capsys.readouterr().err
        assert target.read_text(encoding="utf-8") == "original\n"


def test_proposals_apply_refuses_a_stale_base_commit(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, secrets=False)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@e.st")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        api.exports["exp1"] = {"export_id": "exp1", "base_commit": "b" * 40,
                               "files": [{"path": "docs/README.md", "content": "# x\n"}]}
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1",
                                            write=True)) == 1
        assert not (root / "docs" / "README.md").exists()
        assert "base_commit" in capsys.readouterr().err
        # --no-base-check applies it anyway, deliberately.
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="apply", export_id="exp1",
                                            write=True, base_check=False)) == 0
    assert (root / "docs" / "README.md").read_text() == "# x\n"
    capsys.readouterr()


def test_proposals_list_renders_the_server_rows(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, secrets=False)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        api.proposals = [{"proposal_id": "p1", "state": "draft", "kind": "extraction",
                          "scope": "platforms.atlas", "title": "Extract deploy steps"}]
        assert _run(gf.cmd_proposals, _args(api=url, org="acme", repo="monorepo",
                                            proposals_cmd="list")) == 0
        out = capsys.readouterr().out
    assert "p1" in out and "draft" in out and "Extract deploy steps" in out


# ------------------------------------------------------------------- review findings S4/S5/L1-L7

# S4 — the API base flows into `urllib.request.Request(url, …)` with an `Authorization: Bearer`
# header. urllib opens `http://` (token in cleartext) and `file://` (`doctor` would read a local
# path as if it were `/health/ready`).
@pytest.mark.parametrize("bad", [
    "file:///etc/passwd",
    "ftp://example.test",
    "http://api.example.test",
    "https://",
    "not a url",
])
def test_api_base_url_must_be_https_or_loopback(gf, bad, capsys):
    with pytest.raises(SystemExit) as exc:
        gf._normalise_api(bad)
    assert exc.value.code == 2
    assert "http" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("good", [
    "https://api.example.test",
    "https://api.example.test:8443/base/",
    "http://127.0.0.1:8080",
    "http://localhost:8765",
    "http://[::1]:8080",
])
def test_api_base_url_accepts_https_and_loopback_http(gf, good):
    assert gf._normalise_api(good) == good.rstrip("/")


# L1 — `--org`/`--repo`/`GUIDEFOLD_*`/`service.*` reached the request path and guidefold.yaml raw.
@pytest.mark.parametrize("org,repo", [
    ("a/../../b", "monorepo"),
    ("acme", "a/../../b"),
    ("acme", "x#y"),
    ("ACME", "monorepo"),
    ("acme", "a b"),
])
def test_org_and_repo_are_validated_before_they_reach_a_path(gf, tmp_path, org, repo, capsys):
    with pytest.raises(SystemExit) as exc:
        gf.resolve_service_config({}, SimpleNamespace(api="https://a.test", org=org, repo=repo),
                                  tmp_path)
    assert exc.value.code == 2
    assert "invalid" in capsys.readouterr().err


def test_repo_base_percent_encodes_both_halves(gf):
    assert gf._repo_base({"org": "a.b-c", "repo": "x_y.z"}) == "/api/v1/orgs/a.b-c/repos/x_y.z"
    # Even a value that skipped validation cannot rewrite the path.
    assert gf._repo_base({"org": "a/b", "repo": "c/d"}) == "/api/v1/orgs/a%2Fb/repos/c%2Fd"


def test_the_service_block_never_emits_a_value_that_changes_the_yaml(gf):
    import yaml
    text = gf._render_service_block({"api": "https://a.test", "org": "acme", "repo": "mono"})
    assert "api: https://a.test" in text          # the familiar plain form is unchanged
    hostile = gf._render_service_block({"api": "https://a.test\nregistry: {backend: gcp}",
                                        "org": "acme", "repo": "mono"})
    parsed = yaml.safe_load(hostile.split("service:", 1)[0] + "service:" +
                            hostile.split("service:", 1)[1])
    assert set(parsed["service"]) == {"api", "org", "repo"}
    assert "registry" not in parsed


# L2 — the credentials file is the whole multi-API token store; O_TRUNC destroyed it before the
# new content landed, and O_CREAT left a pre-existing 0644 file world-readable until the chmod.
def test_credentials_are_replaced_atomically_and_are_never_world_readable(gf, tmp_path, monkeypatch):
    path = tmp_path / "creds" / "credentials.json"
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(path))
    gf._save_credentials({"https://a.test": {"token": "one"}})
    path.chmod(0o644)                                   # somebody, or an old version, loosened it
    gf._save_credentials({"https://a.test": {"token": "one"}, "https://b.test": {"token": "two"}})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert set(json.loads(path.read_text())) == {"https://a.test", "https://b.test"}
    # No temp file is left behind.
    assert sorted(p.name for p in path.parent.iterdir()) == ["credentials.json"]


# L4 — the client cap was ten times tighter than the contract's, so the stated target repo size
# could not be imported at all.
def test_the_client_file_cap_is_the_contract_number(gf):
    assert gf.SCAN_MAX_FILES == 100_000
    assert gf.SCAN_MAX_BYTES == 100 * 1024 * 1024


# L5 — 401/403/404/409/429 all exited 1 with no hint, so an expired token was indistinguishable
# from a 500 to a CI script.
@pytest.mark.parametrize("status,code,expected_exit,hint", [
    (401, "unauthenticated", 2, "guidefold login"),
    (403, "forbidden", 2, "scopes"),
    (404, "not_found", 1, "--org/--repo"),
    (409, "stale_revision", 1, "re-read"),
    (429, "overloaded", 1, "rate limited"),
])
def test_service_failures_exit_by_status_with_a_next_step(gf, capsys, status, code,
                                                          expected_exit, hint):
    err = gf.ServiceError(status, code, "the server said no")
    with pytest.raises(SystemExit) as exc:
        gf._die_service("status", err, {"api": "https://a.test"})
    assert exc.value.code == expected_exit
    assert hint in capsys.readouterr().err


# L3 — the recovery branch parsed `message` for a list the transport had thrown away, so it was
# dead code and the client re-uploaded every blob.
def test_service_errors_carry_details_from_the_wire(gf):
    err = gf.ServiceError(409, "blobs_missing", "some are missing", details={"missing": ["aa", "bb"]})
    assert err.details["missing"] == ["aa", "bb"]
    assert gf.ServiceError(500, "internal").details == {}


# S5 — §4.1 defines the body as `{harness?}` and §3 rejects unknown request fields with
# `400 invalid_json`, so `client`/`cli_version` failed on the very first call.
def test_login_sends_only_the_contracted_device_body(gf, tmp_path, monkeypatch, capsys, no_sleep):
    monkeypatch.chdir(tmp_path)
    with running_api() as (url, api):
        api.device_token_script = [(200, {"access_token": "gf_tok", "token_type": "Bearer",
                                          "user": {"id": "u1", "email": "o@a.test"},
                                          "orgs": [{"org_id": "o1", "slug": "acme",
                                                    "name": "Acme", "role": "owner"}]})]
        _run(gf.cmd_login, _args(api=url, org=None, repo=None))
        capsys.readouterr()
        start = next(r for r in api.requests
                     if r["method"] == "POST" and r["path"] == "/api/v1/auth/device")
    assert set(start["json"]) == {"harness"}


# L6 — §4.2 answers 201/200 with `created:bool!`; 409 is not part of that contract.
def test_repo_registration_reads_created_from_the_body(gf, tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, secrets=False)
    monkeypatch.chdir(root)
    with running_api() as (url, api):
        _login(gf, url)
        svc = {"api": url, "org": "acme", "repo": "monorepo", "token": "gf_test_token"}
        assert gf._ensure_repo(svc, root) == "created"
        assert gf._ensure_repo(svc, root) == "exists"
        statuses = [r["path"] for r in api.requests if r["path"].endswith("/repos")]
    assert len(statuses) == 2
    capsys.readouterr()


# The device poll interval is clamped to at least a second: `interval: 0` from the server would
# otherwise buy an unthrottled poll loop.
def test_a_zero_device_interval_is_clamped(gf, tmp_path, monkeypatch, capsys, no_sleep):
    monkeypatch.chdir(tmp_path)
    with running_api() as (url, api):
        api.device_start = {"device_code": "d", "user_code": "WXYZ-1234",
                            "verification_uri": "/organization", "expires_in": 600, "interval": 0}
        api.device_token_script = [
            (400, {"error": "authorization_pending"}),
            (200, {"access_token": "gf_tok", "token_type": "Bearer",
                   "user": {"id": "u1", "email": "o@a.test"}, "orgs": []}),
        ]
        _run(gf.cmd_login, _args(api=url, org=None, repo=None))
        capsys.readouterr()
    assert no_sleep and min(no_sleep) >= 1
