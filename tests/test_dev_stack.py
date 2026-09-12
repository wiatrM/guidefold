"""tools/dev/stack.py — the stdlib-only local pivot-stack helper (pg + guidefold-search
serve/worker + optional ui), used for E2E/acceptance runs without Docker or sudo.

Two-layer convention, same as tests/test_dev_sparse.py and tests/test_dev_decompose.py:
pure-logic tests (path layout, env assembly, secret file modes, port resolution, readiness
parsing, state load/save) always run and never touch a socket or spawn a process. The one
integration test that actually runs `up`/`down` against real pg + a built Go binary is
opt-in, guarded by GUIDEFOLD_STACK_INTEGRATION=1, since it needs the Go/Postgres toolchains
and takes real wall-clock time.
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STACK_PATH = ROOT / "tools" / "dev" / "stack.py"

spec = importlib.util.spec_from_file_location("gf_dev_stack", STACK_PATH)
stack = importlib.util.module_from_spec(spec)
sys.modules["gf_dev_stack"] = stack
spec.loader.exec_module(stack)


# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

def test_paths_for_are_under_dot_guidefold_dev(tmp_path):
    p = stack.paths_for(tmp_path)
    assert p.dev_dir == tmp_path / ".guidefold" / "dev"
    assert p.secrets_dir == p.dev_dir / "secrets"
    assert p.bin_dir == p.dev_dir / "bin"
    assert p.binary == p.dev_dir / "bin" / "guidefold-search"
    assert p.api_pid == p.dev_dir / "api.pid"
    assert p.api_log == p.dev_dir / "api.log"
    assert p.worker_pid == p.dev_dir / "worker.pid"
    assert p.worker_log == p.dev_dir / "worker.log"
    assert p.ui_pid == p.dev_dir / "ui.pid"
    assert p.ui_log == p.dev_dir / "ui.log"


def test_paths_for_contract_and_policy_source_match_repo_layout(tmp_path):
    p = stack.paths_for(tmp_path)
    assert p.contract == tmp_path / "tools/serve_spike/contracts/harness-service-v1.1.schema.json"
    assert p.policy_source == tmp_path / "skills/guidefold/scripts/guidefold"


def test_paths_for_takes_a_subdir_so_a_second_stack_does_not_clobber_the_first(tmp_path):
    # tests/acceptance runs its own API/worker; it must not overwrite a developer's
    # .guidefold/dev/*.pid or rebuild over their binary.
    dev = stack.paths_for(tmp_path)
    acceptance = stack.paths_for(tmp_path, subdir="acceptance")
    assert acceptance.dev_dir == tmp_path / ".guidefold" / "acceptance"
    assert acceptance.api_pid != dev.api_pid
    assert acceptance.binary != dev.binary


def test_paths_for_is_deterministic_not_name_namespaced(tmp_path):
    # `--name` selects the PostgreSQL instance (tools/dev/pg.py's own axis); the API/worker/ui
    # triple is singular per checkout, matching the task's flat .guidefold/dev/*.pid layout.
    a = stack.paths_for(tmp_path)
    b = stack.paths_for(tmp_path)
    assert a == b


def test_secret_paths_cover_all_three_names():
    p = stack.paths_for(Path("/repo"))
    assert set(p.secret_paths) == {"app_password", "api_token", "postgres_password"}


# --------------------------------------------------------------------------------------
# Port resolution
# --------------------------------------------------------------------------------------

def test_listen_address_is_loopback_and_carries_the_requested_port():
    # services/search/main.go's listenAddress() reads GUIDEFOLD_LISTEN for both `serve` and
    # `healthcheck`, so --api-port really moves the service.
    assert stack.listen_address(8765) == "127.0.0.1:8765"
    assert stack.listen_address(stack.DEFAULT_API_PORT) == "127.0.0.1:8765"


def test_listen_address_refuses_a_port_outside_the_range():
    for bad in (0, -1, 70000):
        with pytest.raises(ValueError):
            stack.listen_address(bad)


def test_default_api_port_matches_the_vite_dev_proxy_target():
    # ui/vite.config.ts proxies /api and /v1 to http://127.0.0.1:8765; a different default
    # would make the browser's same-origin API mode silently unreachable.
    proxy = (ROOT / "ui" / "vite.config.ts").read_text()
    assert f"http://127.0.0.1:{stack.DEFAULT_API_PORT}" in proxy


def test_free_port_returns_a_bindable_loopback_port():
    import socket
    port = stack.free_port()
    assert 1024 < port <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))          # nothing else claimed it


# --------------------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------------------

def test_ensure_secret_file_creates_0700_dir_and_0600_file(tmp_path):
    path = tmp_path / "secrets" / "app_password"
    stack.ensure_secret_file(path)
    assert path.exists()
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(path.read_text()) >= stack.MIN_SECRET_LEN


def test_ensure_secret_file_is_idempotent_never_overwrites(tmp_path):
    path = tmp_path / "secrets" / "app_password"
    stack.ensure_secret_file(path)
    first = path.read_text()
    stack.ensure_secret_file(path)
    assert path.read_text() == first


def test_ensure_secrets_creates_every_secret(tmp_path):
    result = stack.ensure_secrets(tmp_path / "secrets")
    assert set(result) == {"app_password", "api_token", "postgres_password", "secret_keyring"}
    for name, path in result.items():
        assert path.exists()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_secret_keyring_is_a_usable_aes_key(tmp_path):
    # ADR-0045: a keyring with a key of any other length makes every credential route answer
    # secret_encryption_unavailable, which would look like a bug in the stack rather than a
    # malformed key file.
    import base64
    import json
    result = stack.ensure_secrets(tmp_path / "secrets")
    ring = json.loads(result["secret_keyring"].read_text())
    assert ring["active"] in ring["keys"]
    for encoded in ring["keys"].values():
        assert len(base64.b64decode(encoded)) == 32


def test_generate_secret_is_long_enough_for_gos_secret_check():
    # services/search/contract.go's secret() rejects anything under 32 chars after trimming.
    assert len(stack.generate_secret().strip()) >= stack.MIN_SECRET_LEN


# --------------------------------------------------------------------------------------
# Env assembly
# --------------------------------------------------------------------------------------

def _secret_paths(tmp_path):
    d = tmp_path / "secrets"
    return stack.ensure_secrets(d)


def test_migrate_env_uses_postgres_superuser_and_app_password_file(tmp_path):
    sp = _secret_paths(tmp_path)
    env = stack.migrate_env(pg_port=54329, secret_paths=sp, policy_source=Path("policy"))
    assert env["PGUSER"] == "postgres"
    assert env["PG_PASSWORD_FILE"] == str(sp["postgres_password"])
    assert env["APP_PASSWORD_FILE"] == str(sp["app_password"])
    assert env["PGPORT"] == "54329"
    # main.go's run() calls policySHA() unconditionally, even for `migrate`.
    assert env["GUIDEFOLD_POLICY_SOURCE"] == "policy"


def test_serve_env_uses_app_role_and_dev_auth(tmp_path):
    sp = _secret_paths(tmp_path)
    env = stack.serve_env(pg_port=54329, api_port=8080, secret_paths=sp,
                           contract=Path("contract.json"), policy_source=Path("policy"),
                           generator="none", repo_root=Path("/repo"))
    assert env["PGUSER"] == "guidefold_api"
    assert env["PG_PASSWORD_FILE"] == str(sp["app_password"])
    assert env["GUIDEFOLD_AUTH"] == "dev"
    assert env["GUIDEFOLD_INSECURE_COOKIES"] == "true"
    assert env["GUIDEFOLD_PUBLIC_URL"] == "http://127.0.0.1:8080"
    assert env["GUIDEFOLD_LISTEN"] == "127.0.0.1:8080"
    assert env["GUIDEFOLD_TENANT"] == "local"
    assert env["GUIDEFOLD_REPO"] == "meridian"
    assert env["GUIDEFOLD_TOKEN_FILE"] == str(sp["api_token"])
    assert env["GUIDEFOLD_CONTRACT"] == "contract.json"
    assert env["GUIDEFOLD_LEXICAL_ENGINE"] == "router"
    assert env["GUIDEFOLD_GENERATOR"] == "none"
    assert env["GUIDEFOLD_REPO_ROOT"] == "/repo"
    assert env["GUIDEFOLD_PYTHON"] == "python3"
    assert "GUIDEFOLD_WORKER_ID" not in env


def test_worker_env_uses_operator_credentials_because_publish_writes_the_catalog(tmp_path):
    # schema.grantsSQL gives guidefold_api SELECT on gf.* and INSERT only on gf.events /
    # gf.search_shadow, so publish.build (gf.snapshots, gf.skills, gf.heads, gf.router_*)
    # fails with "permission denied for table snapshots" under the API role. The worker is
    # an operator job, like `migrate` and `publish` in compose.yaml.
    sp = _secret_paths(tmp_path)
    kwargs = dict(pg_port=54329, api_port=8080, secret_paths=sp, contract=Path("c"),
                  policy_source=Path("p"), generator="deterministic", repo_root=Path("/repo"))
    serve = stack.serve_env(**kwargs)
    worker = stack.worker_env(**kwargs)
    assert serve["PGUSER"] == "guidefold_api"
    assert worker["PGUSER"] == "postgres"
    assert worker["PG_PASSWORD_FILE"] == str(sp["postgres_password"])
    assert worker["GUIDEFOLD_WORKER_ID"] == "dev-1"
    differing = {k for k in worker if worker[k] != serve.get(k)}
    assert differing == {"PGUSER", "PG_PASSWORD_FILE", "GUIDEFOLD_WORKER_ID"}


def test_full_env_overlays_onto_process_environment(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    merged = stack.full_env({"FOO": "bar"})
    assert merged["PATH"] == "/usr/bin"
    assert merged["FOO"] == "bar"


def test_go_build_env_prepends_go_bin_and_sets_caches(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    env = stack.go_build_env()
    assert env["PATH"].startswith(str(stack.GO_BIN_DIR))
    assert env["GOPATH"] == str(stack.GOPATH_DIR)
    assert env["GOMODCACHE"] == str(stack.GOMODCACHE_DIR)
    assert env["GOCACHE"] == str(stack.GOCACHE_DIR)


# --------------------------------------------------------------------------------------
# Readiness parsing
# --------------------------------------------------------------------------------------

def test_is_live_response_true_only_for_200():
    assert stack.is_live_response(200) is True
    assert stack.is_live_response(503) is False
    assert stack.is_live_response(0) is False


def test_describe_ready_reports_ok_body():
    msg = stack.describe_ready(200, {"ready": True, "backend": "plain-postgres", "n_skills": 17})
    assert "ready" in msg
    assert "plain-postgres" in msg
    assert "17" in msg


def test_describe_ready_treats_snapshot_not_published_as_expected():
    msg = stack.describe_ready(503, {"error": "snapshot_not_published"})
    assert "not ready yet" in msg
    assert "expected" in msg


def test_describe_ready_other_failures_are_reported_plainly():
    msg = stack.describe_ready(500, {"error": "boom"})
    assert "not ready (500)" in msg


def test_parse_json_body_falls_back_to_raw_on_bad_json():
    body = stack.parse_json_body(b"not json")
    assert body == {"raw": "not json"}


def test_parse_json_body_parses_valid_json():
    body = stack.parse_json_body(json.dumps({"a": 1}).encode())
    assert body == {"a": 1}


# --------------------------------------------------------------------------------------
# State file
# --------------------------------------------------------------------------------------

def test_save_and_load_state_roundtrip(tmp_path):
    p = stack.paths_for(tmp_path)
    stack.save_state(p, {"name": "dev", "pg_port": 54329})
    loaded = stack.load_state(p)
    assert loaded["name"] == "dev"
    assert loaded["pg_port"] == 54329


def test_load_state_missing_file_returns_empty_dict(tmp_path):
    p = stack.paths_for(tmp_path)
    assert stack.load_state(p) == {}


def test_resolved_value_prefers_explicit_cli_value():
    assert stack.resolved_value(123, {"k": 456}, "k", 789) == 123


def test_resolved_value_falls_back_to_state_then_default():
    assert stack.resolved_value(None, {"k": 456}, "k", 789) == 456
    assert stack.resolved_value(None, {}, "k", 789) == 789


def test_state_for_name_matches_returns_state():
    state = {"name": "dev", "pg_port": 54329}
    assert stack.state_for_name(state, "dev") == state


def test_state_for_name_mismatch_is_ignored():
    # A state.json saved by a `--name pytest-stack` run must not leak its pg_port/api_port
    # into a `status`/`env` call for the default `dev` name (pg is namespaced by --name,
    # the API/worker/ui state.json is not -- see paths_for's and state_for_name's docstrings).
    state = {"name": "pytest-stack", "pg_port": 54399}
    assert stack.state_for_name(state, "dev") == {}


def test_state_for_name_empty_state_is_ignored():
    assert stack.state_for_name({}, "dev") == {}


# --------------------------------------------------------------------------------------
# Process helpers that don't require a real process
# --------------------------------------------------------------------------------------

def test_read_pid_missing_file_returns_none(tmp_path):
    assert stack.read_pid(tmp_path / "nope.pid") is None


def test_read_pid_non_integer_contents_returns_none(tmp_path):
    p = tmp_path / "bad.pid"
    p.write_text("not-a-pid")
    assert stack.read_pid(p) is None


def test_read_pid_reads_integer(tmp_path):
    p = tmp_path / "ok.pid"
    p.write_text("12345\n")
    assert stack.read_pid(p) == 12345


def test_process_alive_true_for_self():
    assert stack.process_alive(os.getpid()) is True


def test_process_alive_false_for_bogus_pid():
    # PID 1 always exists on Linux; use a PID far outside any realistic range instead.
    assert stack.process_alive(2**30) is False


def test_tail_lines_missing_file_reports_no_log_yet(tmp_path):
    out = stack.tail_lines(tmp_path / "missing.log", 10)
    assert "no log yet" in out


def test_tail_lines_returns_last_n_lines(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("\n".join(f"line{i}" for i in range(10)) + "\n")
    out = stack.tail_lines(p, 3)
    assert out.splitlines() == ["line7", "line8", "line9"]


# --------------------------------------------------------------------------------------
# CLI wiring (argparse only, no side effects)
# --------------------------------------------------------------------------------------

def test_parser_up_defaults():
    parser = stack.build_parser()
    args = parser.parse_args(["up"])
    assert args.name == stack.DEFAULT_NAME
    assert args.pg_port == stack.DEFAULT_PG_PORT
    assert args.api_port == stack.DEFAULT_API_PORT
    assert args.ui is False
    assert args.generator == stack.DEFAULT_GENERATOR == "deterministic"
    assert args.reset is False
    assert args.func is stack.cmd_up


def test_parser_logs_requires_component():
    parser = stack.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["logs"])
    args = parser.parse_args(["logs", "api"])
    assert args.component == "api"
    assert args.func is stack.cmd_logs


def test_parser_down_stop_pg_flag():
    parser = stack.build_parser()
    args = parser.parse_args(["down", "--stop-pg"])
    assert args.stop_pg is True
    assert args.func is stack.cmd_down


# --------------------------------------------------------------------------------------
# Opt-in integration: real up -> health checks -> down against the real toolchains.
# --------------------------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("GUIDEFOLD_STACK_INTEGRATION") != "1",
                     reason="set GUIDEFOLD_STACK_INTEGRATION=1 to run the real stack up/down")
def test_stack_up_and_down_against_real_toolchains():
    env = dict(os.environ)
    up = subprocess.run([sys.executable, str(STACK_PATH), "up", "--name", "pytest-stack",
                         "--pg-port", "54399"], cwd=str(ROOT), env=env,
                        capture_output=True, text=True, timeout=180)
    print(up.stdout)
    print(up.stderr)
    try:
        assert up.returncode == 0, f"up failed:\n{up.stdout}\n{up.stderr}"

        live_req = urllib.request.Request(f"http://127.0.0.1:{stack.DEFAULT_API_PORT}/health/live")
        with urllib.request.urlopen(live_req, timeout=5) as r:
            assert r.status == 200
            print("health/live:", r.read().decode())

        providers_req = urllib.request.Request(
            f"http://127.0.0.1:{stack.DEFAULT_API_PORT}/api/v1/auth/providers")
        with urllib.request.urlopen(providers_req, timeout=5) as r:
            assert r.status == 200
            print("auth/providers:", r.read().decode())
    finally:
        down = subprocess.run([sys.executable, str(STACK_PATH), "down", "--name", "pytest-stack",
                               "--stop-pg"], cwd=str(ROOT), env=env,
                              capture_output=True, text=True, timeout=60)
        print(down.stdout)
        print(down.stderr)
