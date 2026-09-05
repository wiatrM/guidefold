"""`guidefold doctor` diagnoses a configured repo: every check reports ok/warn/fail plus a
one-line fix, exit code is 0 iff no check failed, and it must never crash even when gcloud is
absent or guidefold.yaml is missing/broken. Tests exercise the individual `_check_*` helpers
directly (precise, matches the existing unit-test style in test_repo_helpers.py) plus a couple
of full gf.cmd_doctor(...) runs for the end-to-end exit-code/--json contract."""
import json
import shutil
import time

import pytest

from _helpers import default_nodes, write_guidefold_yaml


def _doctor(gf, monkeypatch, root, *, as_json=False):
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    a = type("Args", (), {"json": as_json})()
    with pytest.raises(SystemExit) as exc:
        gf.cmd_doctor(a)
    return exc.value.code


def _init(gf, monkeypatch, root, **kw):
    monkeypatch.chdir(root)
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    a = type("Args", (), {"publisher": None, "harness": "all", "dry_run": False, **kw})()
    gf.cmd_init(a)


def test_doctor_on_healthy_init_repo_exits_zero(gf, tmp_path, monkeypatch, capsys):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    code = _doctor(gf, monkeypatch, root)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "0 failed" in out


def test_doctor_json_is_valid_with_stable_schema(gf, tmp_path, monkeypatch, capsys):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    capsys.readouterr()  # discard init's own prints
    _doctor(gf, monkeypatch, root, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {"root", "ok", "checks"}
    assert payload["ok"] is True
    assert payload["checks"]
    for c in payload["checks"]:
        assert set(c.keys()) == {"name", "status", "detail", "fix"}
        assert c["status"] in ("ok", "warn", "fail")


def test_doctor_missing_guidefold_yaml_reports_fail_with_fix(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    checks, cfg = gf._check_guidefold_yaml(root)
    assert cfg is None
    assert checks[0]["name"] == "guidefold-yaml"
    assert checks[0]["status"] == "fail"
    assert "init" in checks[0]["fix"]


def test_doctor_missing_cli_install_reports_fail(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    c = gf._check_cli_compiles(root)
    assert c["name"] == "cli-installed"
    assert c["status"] == "fail"
    assert "init" in c["fix"]


def test_doctor_missing_gitignore_reports_fail(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    c = gf._check_gitignore(root)
    assert c["status"] == "fail"
    assert "init" in c["fix"]


def test_doctor_missing_github_action_reports_actionable_warning(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    c = gf._check_github_action(root)
    assert c["status"] != "ok"
    assert c["fix"] and "init" in c["fix"]


@pytest.mark.parametrize("harness", ["claude", "copilot", "codex"])
def test_doctor_missing_hook_reports_actionable_warning(gf, tmp_path, harness):
    root = tmp_path / "acme"
    root.mkdir()
    c = gf._check_hook(root, harness)
    assert c["status"] != "ok"
    assert f"--harness {harness}" in c["fix"]


def test_doctor_hook_pointing_at_missing_cli_reports_fail(gf, tmp_path):
    root = tmp_path / "acme"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(json.dumps({
        "hooks": {"SessionStart": [{"hooks": [{"type": "command",
                                                 "command": ".agents/skills/guidefold/scripts/guidefold hook"}]}]}}
    ))
    c = gf._check_hook(root, "claude")
    assert c["status"] == "fail"
    assert "init" in c["fix"]


def test_doctor_gitignore_present_but_missing_marker_reports_fail(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    (root / ".gitignore").write_text("node_modules/\n")
    c = gf._check_gitignore(root)
    assert c["status"] == "fail"


def test_doctor_gcloud_absent_never_crashes(gf, tmp_path, monkeypatch, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root, nodes=default_nodes(), backend="agent-registry")
    # _check_registry imports shutil locally (E1.5 lazy-import: shutil is never touched on the
    # hook path), so patch the real `shutil` module object rather than a `gf.shutil` attribute --
    # `import shutil` inside the function fetches the same cached module from sys.modules.
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "gcloud" else real_which(name))
    cfg = gf.load_map(root)
    checks = gf._check_registry(root, cfg)
    assert checks[0]["name"] == "registry-gcloud"
    assert checks[0]["status"] == "fail"
    assert all(c["status"] in ("warn", "fail") for c in checks[1:])
    # and the full doctor run still produces a complete report, no traceback, no hang
    code = _doctor(gf, monkeypatch, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "guidefold doctor:" in out


def test_doctor_local_backend_reports_ok_with_skill_count(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    cfg = gf.load_map(root)
    checks = gf._check_registry(root, cfg)
    assert len(checks) == 1
    assert checks[0]["name"] == "registry-backend"
    assert checks[0]["status"] == "ok"
    assert "1 skill(s)" in checks[0]["detail"]


# ------------------------------------------------------------- E2.6 Deliverable 5: search checks

def test_doctor_search_checks_are_ok_when_backend_is_local(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    monkeypatch.delenv("GUIDEFOLD_SEARCH_URL", raising=False)
    cfg = gf.load_map(root)
    assert gf._check_search_service(root, cfg)["status"] == "ok"
    assert gf._check_search_token(cfg)["status"] == "ok"
    p95 = gf._check_search_latency(root, cfg)
    assert p95["status"] == "ok"
    assert "T0" in p95["detail"]


def test_doctor_search_latency_recommends_service_over_the_r4b_threshold(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    cfg = gf.load_map(root)
    # Simulate a corpus slow enough to cross the R4b 300ms guideline without needing an actually
    # huge fixture -- _local_selected is the only thing _measure_local_search_p95 times.
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (time.sleep(0.31), ([], []))[1])
    c = gf._check_search_latency(root, cfg)
    assert c["status"] == "warn"
    assert "service" in c["fix"]


def test_doctor_search_service_reachable_reports_contract_version(gf, tmp_path, monkeypatch):
    import http.server
    import json as _json
    import socket as _socket
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _json.dumps({"ready": True, "snapshot": "sha256:abc",
                                "repository": {"repo_id": "acme", "revision": "deadbeef"},
                                "api_schema_versions": ["legacy-unversioned", "1.1"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = tmp_path / "acme"
        root.mkdir()
        _init(gf, monkeypatch, root)
        monkeypatch.setenv("GUIDEFOLD_SEARCH_URL", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
        cfg = gf.load_map(root)
        c = gf._check_search_service(root, cfg)
        assert c["status"] == "ok"
        assert "1.1" in c["detail"]
        assert "revision=deadbeef" in c["detail"]
        assert "snapshot age" in c["detail"]  # documented gap, never invented
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_doctor_search_service_unreachable_reports_fail(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    monkeypatch.setenv("GUIDEFOLD_SEARCH_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    cfg = gf.load_map(root)
    c = gf._check_search_service(root, cfg)
    assert c["status"] == "fail"


def test_doctor_search_token_missing_reports_fail(gf, tmp_path, monkeypatch):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    monkeypatch.setenv("GUIDEFOLD_SEARCH_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    cfg = gf.load_map(root)
    c = gf._check_search_token(cfg)
    assert c["status"] == "fail"
    assert "GUIDEFOLD_TOKEN" in c["fix"]


def test_doctor_telemetry_spool_empty_reports_ok(gf, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    c = gf._check_telemetry_spool(root)
    assert c["status"] == "ok"
    assert "empty" in c["detail"]


def test_doctor_full_run_includes_search_checks(gf, tmp_path, monkeypatch, capsys):
    root = tmp_path / "acme"
    root.mkdir()
    _init(gf, monkeypatch, root)
    monkeypatch.delenv("GUIDEFOLD_SEARCH_URL", raising=False)
    code = _doctor(gf, monkeypatch, root)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "search-local-p95" in out
    assert "search-service" in out
    assert "search-token" in out
    assert "telemetry-spool" in out
