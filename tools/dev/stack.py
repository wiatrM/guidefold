#!/usr/bin/env python3
"""Bring up the whole Guidefold pivot stack locally, without Docker or sudo.

Starts a non-root PostgreSQL (via ``tools/dev/pg.py``), builds and runs the
``guidefold-search`` Go service (``migrate`` once, then ``serve`` and
``worker`` as long-running processes) and, optionally, the React UI. Meant
for E2E and acceptance runs against the real product path, not for
production or CI (see ``.github/workflows/`` for that).

    python3 tools/dev/stack.py up     [--name dev] [--pg-port 54329] [--api-port 8765]
                                       [--ui] [--generator none|deterministic] [--reset]
    python3 tools/dev/stack.py seed   [--name dev] [--api-port 8765] [--org acme]
                                       [--repo meridian] [--email ...] [--tree DIR]
    python3 tools/dev/stack.py down   [--name dev] [--stop-pg]
    python3 tools/dev/stack.py status [--name dev]
    python3 tools/dev/stack.py logs   {api,worker,pg,ui} [--name dev] [-n LINES] [-f]
    python3 tools/dev/stack.py env    [--name dev]

Runtime files live under ``.guidefold/dev/`` (gitignored, see ``.gitignore``):
secrets in ``.guidefold/dev/secrets/`` (0700 dir, 0600 files, never printed),
the built binary in ``.guidefold/dev/bin/``, PIDs in ``.guidefold/dev/*.pid``
and logs in ``.guidefold/dev/*.log``. PostgreSQL's own data/log live under
``~/.cache/guidefold/pg/<name>`` (owned by ``tools/dev/pg.py``, reused here
by import rather than re-implemented) and are not deleted by ``down``.

Toolchain: Go at ``~/.cache/guidefold/toolchain/go/bin`` (module dir
``services/search``, built with ``go build -C ... -o ...`` since there is no
``go.mod`` at the repository root); PostgreSQL binaries at
``~/.cache/guidefold/toolchain/pg18/bin`` (no ``psql``/``createdb`` required,
see ``tools/dev/pg.py``); ``pnpm``/``node`` from ``PATH`` for ``--ui``.

``--api-port`` really moves the service: ``serve`` binds ``GUIDEFOLD_LISTEN``
(``services/search/main.go``'s ``listenAddress()``), and ``healthcheck`` probes
the same value. The default is 8765 because that is the target
``ui/vite.config.ts``'s dev proxy sends ``/api`` and ``/v1`` to, so the browser
reaches the API same-origin through ``pnpm dev`` and never needs CORS.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# tools/ has no __init__.py (see tests/conftest.py's own loader for the CLI script for the
# same reason), so tools/dev/pg.py is loaded by path rather than by package import. This is
# the "reuse its functions by import; do not duplicate" instruction from the task.
_PG_SPEC = importlib.util.spec_from_file_location("guidefold_dev_pg", Path(__file__).resolve().parent / "pg.py")
pg = importlib.util.module_from_spec(_PG_SPEC)
_PG_SPEC.loader.exec_module(pg)  # type: ignore[union-attr]

# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------

HOME = Path.home()
GO_HOME = HOME / ".cache/guidefold/toolchain/go"
GO_BIN_DIR = GO_HOME / "bin"
GOPATH_DIR = HOME / ".cache/guidefold/gopath"
GOMODCACHE_DIR = GOPATH_DIR / "pkg/mod"
GOCACHE_DIR = HOME / ".cache/guidefold/gocache"

DEFAULT_NAME = "dev"
DEFAULT_PG_PORT = 54329
# ui/vite.config.ts proxies /api and /v1 to http://127.0.0.1:8765, so this default is what
# makes the browser reach the API same-origin through `pnpm dev` -- no CORS, no second origin.
DEFAULT_API_PORT = 8765
UI_PORT = 4331  # ui/vite.config.ts pins both dev and preview to this port
DEFAULT_GENERATOR = "deterministic"
DEFAULT_ORG_SLUG = "acme"
DEFAULT_REPO_ID = "meridian"
DEFAULT_SEED_EMAIL = "owner@example.test"

SECRET_NAMES = ("app_password", "api_token", "postgres_password")
SECRET_DIR_MODE = 0o700
SECRET_FILE_MODE = 0o600
MIN_SECRET_LEN = 32  # services/search/contract.go's secret() rejects anything shorter

STOP_GRACE_SECONDS = 10.0


# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Paths:
    repo_root: Path
    dev_dir: Path
    secrets_dir: Path
    bin_dir: Path
    binary: Path
    state_file: Path
    api_pid: Path
    api_log: Path
    worker_pid: Path
    worker_log: Path
    ui_pid: Path
    ui_log: Path
    migrate_log: Path
    contract: Path
    policy_source: Path
    ui_dir: Path

    @property
    def secret_paths(self) -> dict:
        return {name: self.secrets_dir / name for name in SECRET_NAMES}


def paths_for(repo_root: Path, subdir: str = "dev") -> Paths:
    """Pure, deterministic layout under ``<repo_root>/.guidefold/<subdir>``.

    ``subdir`` exists so a second stack (``tests/acceptance``'s session fixture) can hold its
    own pids, logs and binary without overwriting a developer's running ``stack.py up``.

    Not namespaced by ``--name``: only one API/worker/UI triple is meant to run at a
    time locally (``--name`` selects the PostgreSQL instance, matching tools/dev/pg.py's
    own single-purpose ``--name``), and the task's own file list (``.guidefold/dev/*.pid``,
    ``.guidefold/dev/*.log``) is flat.
    """
    dev_dir = repo_root / ".guidefold" / subdir
    return Paths(
        repo_root=repo_root,
        dev_dir=dev_dir,
        secrets_dir=dev_dir / "secrets",
        bin_dir=dev_dir / "bin",
        binary=dev_dir / "bin" / "guidefold-search",
        state_file=dev_dir / "state.json",
        api_pid=dev_dir / "api.pid",
        api_log=dev_dir / "api.log",
        worker_pid=dev_dir / "worker.pid",
        worker_log=dev_dir / "worker.log",
        ui_pid=dev_dir / "ui.pid",
        ui_log=dev_dir / "ui.log",
        migrate_log=dev_dir / "migrate.log",
        contract=repo_root / "tools/serve_spike/contracts/harness-service-v1.1.schema.json",
        policy_source=repo_root / "skills/guidefold/scripts/guidefold",
        ui_dir=repo_root / "ui",
    )


# --------------------------------------------------------------------------------------
# Pure helpers: port resolution
# --------------------------------------------------------------------------------------

def listen_address(api_port: int) -> str:
    """``GUIDEFOLD_LISTEN`` for a local stack: loopback only, never a wildcard bind.

    ``services/search/main.go``'s ``listenAddress()`` reads this variable for both ``serve``
    and ``healthcheck``, so the port moves in one place."""
    if not (1 <= int(api_port) <= 65535):
        raise ValueError(f"--api-port out of range: {api_port}")
    return f"127.0.0.1:{int(api_port)}"


def free_port() -> int:
    """An unused loopback TCP port, for callers (the acceptance suite) that must not collide
    with a developer's own stack. Classic bind-to-0 + close; the small race is acceptable
    because the caller binds immediately afterwards."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------------------
# Pure helpers: secrets
# --------------------------------------------------------------------------------------

def generate_secret() -> str:
    return secrets.token_urlsafe(32)  # 43 chars, well above MIN_SECRET_LEN


def ensure_secret_file(path: Path, value_factory=generate_secret) -> None:
    """Idempotent: creates the 0700 parent dir and a 0600 file once; never overwrites an
    existing secret and never returns/prints its content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, SECRET_DIR_MODE)
    if not path.exists():
        path.write_text(value_factory(), encoding="utf-8")
    os.chmod(path, SECRET_FILE_MODE)


def ensure_secrets(secrets_dir: Path) -> dict:
    """Ensures app_password/api_token/postgres_password exist; returns their paths (not
    values). ``postgres_password`` is an unchecked placeholder: tools/dev/pg.py initialises
    PostgreSQL with ``--auth=trust``, so its content is never verified, only its length
    (services/search/contract.go's secret() rejects anything under 32 bytes)."""
    result = {}
    for n in SECRET_NAMES:
        p = secrets_dir / n
        ensure_secret_file(p)
        result[n] = p
    return result


# --------------------------------------------------------------------------------------
# Pure helpers: environment assembly
# --------------------------------------------------------------------------------------

def base_pg_env(pg_port: int, pguser: str, password_file: Path) -> dict:
    return {
        "PGHOST": "127.0.0.1",
        "PGPORT": str(pg_port),
        "PGDATABASE": "guidefold",
        "PGUSER": pguser,
        "PGSSLMODE": "disable",
        "PG_PASSWORD_FILE": str(password_file),
    }


def migrate_env(*, pg_port: int, secret_paths: dict, policy_source: Path) -> dict:
    """PGUSER=postgres (the superuser migrate needs to create/alter guidefold_api), plus
    APP_PASSWORD_FILE -- the password schema.Migrate sets on that role. GUIDEFOLD_POLICY_SOURCE
    is required even for `migrate`: main.go's run() calls policySHA() unconditionally before
    dispatching on the subcommand."""
    env = base_pg_env(pg_port, "postgres", secret_paths["postgres_password"])
    env["APP_PASSWORD_FILE"] = str(secret_paths["app_password"])
    env["GUIDEFOLD_POLICY_SOURCE"] = str(policy_source)
    return env


def serve_env(*, pg_port: int, api_port: int, secret_paths: dict, contract: Path,
              policy_source: Path, generator: str, repo_root: Path,
              auth: str = "dev", workos_client_id: str = "", workos_api_key_file: str = "") -> dict:
    env = base_pg_env(pg_port, "guidefold_api", secret_paths["app_password"])
    env.update({
        "GUIDEFOLD_AUTH": auth,
        # This stack always serves over plain http://127.0.0.1 (see the module docstring:
        # local/E2E only, never production), independent of --auth -- a real workos
        # deployment sets this to "false" (or omits it) itself, behind real TLS.
        "GUIDEFOLD_INSECURE_COOKIES": "true",
        # services/search/main.go's listenAddress(): `serve` binds this and `healthcheck`
        # probes it, so --api-port really moves the service instead of being advisory.
        "GUIDEFOLD_LISTEN": listen_address(api_port),
        "GUIDEFOLD_PUBLIC_URL": f"http://127.0.0.1:{api_port}",
        "GUIDEFOLD_TENANT": "local",
        "GUIDEFOLD_REPO": "meridian",
        "GUIDEFOLD_TOKEN_FILE": str(secret_paths["api_token"]),
        "GUIDEFOLD_CONTRACT": str(contract),
        "GUIDEFOLD_POLICY_SOURCE": str(policy_source),
        "GUIDEFOLD_LEXICAL_ENGINE": "router",
        # services/search/internal/review/generator/generator.go's Select(): picks the
        # `proposal.generate` backend. `deterministic` (recipe det-1) is the default here
        # because an offline stack that silently skips every generation job cannot exercise
        # the review loop at all.
        "GUIDEFOLD_GENERATOR": generator,
        "GUIDEFOLD_REPO_ROOT": str(repo_root),
        "GUIDEFOLD_PYTHON": "python3",
    })
    if auth == "workos":
        # identity.ConfigFromEnv() reads the secret key from a file path, never from an
        # inline env value -- same convention as PG_PASSWORD_FILE/GUIDEFOLD_TOKEN_FILE, so
        # the key never appears in `ps`/`/proc/<pid>/environ` as a bare value.
        env["WORKOS_CLIENT_ID"] = workos_client_id
        env["WORKOS_API_KEY_FILE"] = workos_api_key_file
    return env


def worker_env(**kwargs) -> dict:
    """Operator credentials, matching compose.yaml's `worker` service.

    `publish.build` writes the immutable catalog (`gf.snapshots`, `gf.skills`, `gf.heads`,
    `gf.router_*`), and `schema.grantsSQL` deliberately gives `guidefold_api` no INSERT there
    -- only SELECT on `gf.*` plus INSERT on the two append-only event tables -- so that a
    compromised request-serving process cannot rewrite what every agent reads. The worker is
    an operator job in that split, so it connects as `postgres`, like `migrate` and
    `publish`. Running it as `guidefold_api` makes every publication fail with
    `permission denied for table snapshots`."""
    env = serve_env(**kwargs)
    env["PGUSER"] = "postgres"
    env["PG_PASSWORD_FILE"] = str(kwargs["secret_paths"]["postgres_password"])
    env["GUIDEFOLD_WORKER_ID"] = "dev-1"
    return env


def full_env(overrides: dict) -> dict:
    """Overlay ``overrides`` onto a copy of the current process environment (PATH, HOME,
    locale, etc. still apply to the child)."""
    merged = dict(os.environ)
    merged.update(overrides)
    return merged


def go_build_env() -> dict:
    env = dict(os.environ)
    env["PATH"] = f"{GO_BIN_DIR}{os.pathsep}{env.get('PATH', '')}"
    env["GOPATH"] = str(GOPATH_DIR)
    env["GOMODCACHE"] = str(GOMODCACHE_DIR)
    env["GOCACHE"] = str(GOCACHE_DIR)
    return env


# --------------------------------------------------------------------------------------
# Pure helpers: readiness parsing
# --------------------------------------------------------------------------------------

def is_live_response(status: int) -> bool:
    return status == 200


def describe_ready(status: int, body: dict) -> str:
    """Human-readable one-liner for a /health/ready response. A 503
    ``snapshot_not_published`` is an expected state before the first import/publish, not a
    failure -- see the module docstring and services/search/store.go's `fail(503,
    "snapshot_not_published")`."""
    if status == 200:
        return f"ready: backend={body.get('backend')!r} n_skills={body.get('n_skills')!r}"
    if status == 503 and body.get("error") == "snapshot_not_published":
        return "not ready yet: snapshot_not_published (expected before the first import)"
    return f"not ready ({status}): {body}"


def parse_json_body(raw: bytes) -> dict:
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw": raw[:500].decode("utf-8", "replace")}


# --------------------------------------------------------------------------------------
# Pure helpers: state file (best-effort memory of the last `up`, so `down`/`status`/`env`/
# `logs` do not require repeating every flag; always overridable by explicit CLI flags)
# --------------------------------------------------------------------------------------

def load_state(paths: Paths) -> dict:
    try:
        return json.loads(paths.state_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(paths: Paths, state: dict) -> None:
    paths.dev_dir.mkdir(parents=True, exist_ok=True)
    paths.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolved_value(cli_value, state: dict, key: str, default):
    if cli_value is not None:
        return cli_value
    if key in state:
        return state[key]
    return default


def state_for_name(state: dict, name: str) -> dict:
    """Guards against a state.json written by a differently-``--name``d run (pg is
    namespaced by ``--name``, but the API/worker/ui triple in state.json is not -- see
    paths_for's docstring). Only trust the recorded pg_port/api_port when they were saved
    for this same pg instance name; otherwise fall back to the caller's defaults."""
    if state.get("name") != name:
        return {}
    return state


# --------------------------------------------------------------------------------------
# Process helpers (not pure: touch pids/signals; excluded from the hermetic test file)
# --------------------------------------------------------------------------------------

def read_pid(pid_path: Path) -> Optional[int]:
    try:
        return int(pid_path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_cmdline_contains(pid: int, needle: str) -> bool:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return needle.encode() in raw


def stop_pid(pid_path: Path, label: str, needle: Optional[str] = None,
             timeout: float = STOP_GRACE_SECONDS) -> None:
    pid = read_pid(pid_path)
    if pid is None or not process_alive(pid):
        print(f"{label}: not running")
        pid_path.unlink(missing_ok=True)
        return
    if needle and not process_cmdline_contains(pid, needle):
        print(f"{label}: pid {pid} does not look like {needle!r} any more; leaving it alone, clearing stale pidfile")
        pid_path.unlink(missing_ok=True)
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and process_alive(pid):
        time.sleep(0.2)
    if process_alive(pid):
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)
    pid_path.unlink(missing_ok=True)
    print(f"{label}: stopped (pid {pid})")


def spawn(argv: list, env: dict, log_path: Path, pid_path: Path, cwd: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log_fh:
        log_fh.write(f"\n--- start {datetime.now(timezone.utc).isoformat()} {argv!r} ---\n".encode())
        proc = subprocess.Popen(argv, env=env, cwd=str(cwd), stdout=log_fh,
                                 stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
    pid_path.write_text(str(proc.pid))
    return proc.pid


def tail_lines(path: Path, n: int) -> str:
    if not path.exists():
        return f"(no log yet: {path})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def http_get(url: str, timeout: float = 2.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, parse_json_body(r.read())
    except urllib.error.HTTPError as e:
        return e.code, parse_json_body(e.read())


def wait_for_live(url: str, timeout: float = 30.0, interval: float = 0.3) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = http_get(url, timeout=2.0)
            if is_live_response(status):
                return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(interval)
    return False


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def build_binary(paths: Paths) -> subprocess.CompletedProcess:
    paths.bin_dir.mkdir(parents=True, exist_ok=True)
    module_dir = paths.repo_root / "services" / "search"
    go = GO_BIN_DIR / "go"
    return subprocess.run(
        [str(go), "build", "-C", str(module_dir), "-o", str(paths.binary), "."],
        env=go_build_env(), capture_output=True, text=True,
    )


def run_migrate(paths: Paths, pg_port: int, secret_paths: dict) -> subprocess.CompletedProcess:
    env = full_env(migrate_env(pg_port=pg_port, secret_paths=secret_paths, policy_source=paths.policy_source))
    paths.migrate_log.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.migrate_log, "ab") as log:
        log.write(f"\n--- migrate {datetime.now(timezone.utc).isoformat()} ---\n".encode())
        result = subprocess.run([str(paths.binary), "migrate"], cwd=str(paths.repo_root),
                                 env=env, stdout=log, stderr=subprocess.STDOUT)
    return result


def ensure_ui_deps(ui_dir: Path) -> None:
    if (ui_dir / "node_modules").is_dir():
        return
    print("ui: installing dependencies (pnpm install --frozen-lockfile)")
    subprocess.run(["pnpm", "--dir", str(ui_dir), "install", "--frozen-lockfile"], check=True)


def build_ui(ui_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["pnpm", "--dir", str(ui_dir), "build"], capture_output=True, text=True)


# --------------------------------------------------------------------------------------
# Seeding: one signed-in owner, one organisation, one repository, one imported monorepo.
#
# Everything here goes through the same HTTP surface a browser and the shipped CLI use --
# no direct SQL, no in-process shortcut -- so what `seed` proves is what a person would
# get. It is a convenience for manual work and for the live UI E2E run; the acceptance
# suite calls these functions rather than shelling out to the subcommand.
# --------------------------------------------------------------------------------------

class SeedError(RuntimeError):
    """A seeding step the API refused. Carries the status and the parsed body."""


class ApiSession:
    """A cookie-jar HTTP client for one signed-in person, with CSRF double-submit."""

    def __init__(self, base_url: str):
        import http.cookiejar
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect())
        self.csrf: Optional[str] = None
        self.user: dict = {}

    def request(self, method: str, path: str, *, body=None, form=None, raw: Optional[bytes] = None,
                headers=None, token: Optional[str] = None, timeout: float = 30.0):
        """``raw`` sends bytes verbatim -- blob upload is an octet-stream route, not JSON."""
        url = path if path.startswith("http") else self.base_url + path
        data = None
        hdrs = dict(headers or {})
        if raw is not None:
            data = raw
            hdrs.setdefault("Content-Type", "application/octet-stream")
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif body is not None:
            data = json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        if self.csrf and method not in ("GET", "HEAD"):
            hdrs.setdefault("X-CSRF-Token", self.csrf)
        if token:
            hdrs["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                return r.status, parse_json_body(r.read()), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, parse_json_body(e.read()), dict(e.headers)

    def expect(self, method: str, path: str, ok=(200, 201), **kw) -> dict:
        status, body, _ = self.request(method, path, **kw)
        if status not in ok:
            raise SeedError(f"{method} {path}: {status} {body}")
        return body


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The dev provider answers 302 with the session cookie; following it would hit the UI."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_302(self, req, fp, code, msg, headers):
        return _Response(code, fp.read(), headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class _Response:
    def __init__(self, status, body, headers):
        self.status, self._body, self.headers = status, body, headers

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def dev_login(base_url: str, *, subject: str, email: str, name: Optional[str] = None) -> ApiSession:
    """Sign in through `GUIDEFOLD_AUTH=dev`'s form, exactly as the browser does."""
    session = ApiSession(base_url)
    status, body, _ = session.request("POST", "/api/v1/auth/dev", form={
        "provider": "google", "subject": subject, "email": email, "name": name or subject})
    if status not in (200, 302, 303):
        raise SeedError(f"dev sign-in: {status} {body}")
    me = session.expect("GET", "/api/v1/me")
    session.csrf = me.get("csrf_token")
    session.user = me.get("user") or {}
    return session


def ensure_org(session: ApiSession, slug: str, name: Optional[str] = None) -> str:
    """Create the organisation, or return the existing one this person already owns."""
    status, body, _ = session.request("POST", "/api/v1/orgs",
                                       body={"name": name or slug, "slug": slug},
                                       headers={"Idempotency-Key": "seed-org-" + slug})
    if status in (200, 201):
        return body["org_id"]
    if status == 409 and body.get("error") == "slug_taken":
        me = session.expect("GET", "/api/v1/me")
        for org in me.get("orgs") or []:
            if org.get("slug") == slug:
                return org["org_id"]
    raise SeedError(f"create org {slug}: {status} {body}")


def ensure_repo(session: ApiSession, org: str, repo_id: str, git_host_url: str = "") -> None:
    status, body, _ = session.request(
        "POST", f"/api/v1/orgs/{org}/repos",
        body={"repo_id": repo_id, "name": repo_id, "git_host_url": git_host_url},
        headers={"Idempotency-Key": f"seed-repo-{org}-{repo_id}"})
    if status not in (200, 201, 409):
        raise SeedError(f"create repo {repo_id}: {status} {body}")


def device_token(base_url: str, session: ApiSession) -> str:
    """The CLI's own login path: anonymous start, approval from the session, exchange."""
    anon = ApiSession(base_url)
    start = anon.expect("POST", "/api/v1/auth/device")
    session.expect("POST", "/api/v1/auth/device/approve",
                   body={"user_code": start["user_code"]})
    exchanged = anon.expect("POST", "/api/v1/auth/device/token",
                            body={"device_code": start["device_code"]})
    token = exchanged.get("token", "")
    if not token.startswith("gf_"):
        raise SeedError("the device flow returned no personal token")
    return token


def prepare_tree(source: Path, dest: Path) -> Optional[str]:
    """A throwaway git work tree holding a copy of ``source``. Returns HEAD, or None when
    git is unavailable (the manifest is then `commit: null, dirty: true`, which is a valid
    scan, just not a publishable-by-commit one)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git", ".guidefold"))
    if shutil.which("git") is None:
        return None
    env = dict(os.environ, GIT_AUTHOR_NAME="guidefold seed", GIT_AUTHOR_EMAIL="seed@example.test",
               GIT_COMMITTER_NAME="guidefold seed", GIT_COMMITTER_EMAIL="seed@example.test")
    for argv in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                 ["git", "commit", "-q", "-m", "seed"]):
        r = subprocess.run(argv, cwd=str(dest), env=env, capture_output=True, text=True)
        if r.returncode != 0:
            return None
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(dest), env=env,
                          capture_output=True, text=True)
    return head.stdout.strip() or None


def cli_env(*, api: str, org: str, repo: str, token: str, home: Path) -> dict:
    """Environment for one shelled-out CLI run: its own HOME and credentials file, so it can
    never read or write the developer's own `~/.config/guidefold/credentials.json`."""
    home.mkdir(parents=True, exist_ok=True)
    return full_env({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GUIDEFOLD_CREDENTIALS": str(home / "credentials.json"),
        "GUIDEFOLD_CACHE": str(home / ".cache-guidefold"),
        "GUIDEFOLD_API": api,
        "GUIDEFOLD_ORG": org,
        "GUIDEFOLD_REPO_ID": repo,
        "GUIDEFOLD_TOKEN": token,
    })


def run_cli(paths: Paths, args: list, *, cwd: Path, env: dict,
            timeout: float = 900.0) -> subprocess.CompletedProcess:
    cli = paths.repo_root / "skills" / "guidefold" / "scripts" / "guidefold"
    return subprocess.run([sys.executable, str(cli), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=timeout)


def last_json_object(text: str) -> dict:
    """The CLI prints progress lines before its `--json` result."""
    start = text.find("{")
    while start >= 0:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
    raise SeedError(f"no JSON object in CLI output:\n{text}")


def write_secret(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, SECRET_DIR_MODE)
    path.write_text(value, encoding="utf-8")
    os.chmod(path, SECRET_FILE_MODE)
    return path


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def cmd_up(args: argparse.Namespace) -> int:
    paths = paths_for(REPO_ROOT)
    api_port = args.api_port
    listen_address(api_port)  # validates the range before anything is started

    if args.auth == "workos":
        if not args.workos_client_id or not args.workos_api_key_file:
            print("--auth workos requires --workos-client-id and --workos-api-key-file "
                  "(identity.ConfigFromEnv() refuses to start otherwise)", file=sys.stderr)
            return 1
        if not Path(args.workos_api_key_file).is_file():
            print(f"--workos-api-key-file {args.workos_api_key_file!r} does not exist", file=sys.stderr)
            return 1

    if args.reset:
        print(f"--reset: stopping any running components and wiping the '{args.name}' PostgreSQL data dir")
        cmd_down(argparse.Namespace(name=args.name, stop_pg=True))
        shutil.rmtree(paths.secrets_dir, ignore_errors=True)
        pg.reset(args.name, args.pg_port)
    else:
        pg.start(args.name, args.pg_port)  # idempotent: prints "already running" and returns

    secret_paths = ensure_secrets(paths.secrets_dir)

    print("building guidefold-search ...")
    build = build_binary(paths)
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        print("go build failed -- see above. Not patching services/search; report this to "
              "whoever is editing it.", file=sys.stderr)
        return 1
    print(f"built: {paths.binary}")

    print("running migrate ...")
    migrated = run_migrate(paths, args.pg_port, secret_paths)
    if migrated.returncode != 0:
        print(f"migrate failed (exit {migrated.returncode}); last lines of {paths.migrate_log}:")
        print(tail_lines(paths.migrate_log, 40))
        return 1
    print("migrate: ok")

    env_kwargs = dict(pg_port=args.pg_port, api_port=api_port, secret_paths=secret_paths,
                       contract=paths.contract, policy_source=paths.policy_source,
                       generator=args.generator, repo_root=paths.repo_root,
                       auth=args.auth, workos_client_id=args.workos_client_id,
                       workos_api_key_file=args.workos_api_key_file)

    print("starting serve ...")
    stop_pid(paths.api_pid, "api", needle="guidefold-search")
    spawn([str(paths.binary), "serve"], full_env(serve_env(**env_kwargs)),
          paths.api_log, paths.api_pid, paths.repo_root)

    live_url = f"http://127.0.0.1:{api_port}/health/live"
    ready_url = f"http://127.0.0.1:{api_port}/health/ready"
    ok = 0
    if wait_for_live(live_url):
        print(f"api: live ({live_url})")
        status, body = http_get(ready_url)
        print(f"api: {describe_ready(status, body)}")
    else:
        print(f"api: did NOT become live within the timeout; last lines of {paths.api_log}:")
        print(tail_lines(paths.api_log, 40))
        ok = 1

    print("starting worker ...")
    stop_pid(paths.worker_pid, "worker", needle="guidefold-search")
    spawn([str(paths.binary), "worker"], full_env(worker_env(**env_kwargs)),
          paths.worker_log, paths.worker_pid, paths.repo_root)
    time.sleep(0.5)
    wpid = read_pid(paths.worker_pid)
    if wpid and process_alive(wpid):
        print(f"worker: running (pid {wpid})")
    else:
        print(f"worker: exited immediately; last lines of {paths.worker_log}:")
        print(tail_lines(paths.worker_log, 40))
        ok = 1

    ui_started = False
    if args.ui:
        if shutil.which("pnpm") is None:
            print("ui: pnpm not found on PATH; skipping --ui", file=sys.stderr)
            ok = 1
        else:
            ensure_ui_deps(paths.ui_dir)
            print("building ui (pnpm build: tsc --noEmit && vite build) ...")
            built = build_ui(paths.ui_dir)
            if built.returncode != 0:
                sys.stderr.write(built.stdout)
                sys.stderr.write(built.stderr)
                print("ui build failed -- see above; not starting the ui dev server.", file=sys.stderr)
                ok = 1
            else:
                # ui/vite.config.ts's `preview` block has no `proxy` entry (only `server`
                # does), so `pnpm preview` cannot reach the API same-origin. Falling back
                # to `pnpm dev`, as instructed when preview does not proxy.
                print("ui: 'vite preview' has no proxy configured in ui/vite.config.ts "
                      "(only the dev server does); running 'pnpm dev' instead")
                stop_pid(paths.ui_pid, "ui", needle="vite")
                # Deliberately NOT setting VITE_GUIDEFOLD_API: with it, ui/src/api/client.ts
                # talks to a second origin and the browser blocks the credentialed request
                # (services/search sends no Access-Control-* headers). Unset, the client uses
                # same-origin /api and /v1, which `pnpm dev` proxies to 127.0.0.1:8765 --
                # so open the app with ?mode=api to select the API DataSource.
                ui_env = full_env({})
                spawn(["pnpm", "--dir", str(paths.ui_dir), "dev"], ui_env, paths.ui_log,
                      paths.ui_pid, paths.repo_root)
                time.sleep(1.0)
                upid = read_pid(paths.ui_pid)
                if upid and process_alive(upid):
                    print(f"ui: running (pid {upid}) at http://127.0.0.1:{UI_PORT}")
                    print(f"ui: open http://127.0.0.1:{UI_PORT}/?mode=api -- /api and /v1 are "
                          f"proxied same-origin to http://127.0.0.1:{api_port} by ui/vite.config.ts. "
                          "VITE_GUIDEFOLD_API is deliberately unset (a second origin would need CORS).")
                    ui_started = True
                else:
                    print(f"ui: exited immediately; last lines of {paths.ui_log}:")
                    print(tail_lines(paths.ui_log, 40))
                    ok = 1

    save_state(paths, {
        "name": args.name, "pg_port": args.pg_port, "api_port": api_port,
        "ui": ui_started, "generator": args.generator,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    print()
    print(f"GUIDEFOLD_API=http://127.0.0.1:{api_port}")
    print(f"GUIDEFOLD_TOKEN_FILE={secret_paths['api_token']}")
    print("Run 'python3 tools/dev/stack.py env' to source these, or 'status'/'logs' to inspect the stack.")
    return ok


def cmd_seed(args: argparse.Namespace) -> int:
    """Dev login -> org -> repo -> device token -> CLI import of a copy of examples/monorepo.

    Prints the resulting identifiers as JSON on stdout. The personal token is written to a
    0600 file and only its *path* is printed: a token in a terminal scrollback is a token in
    a log (security-baseline, "Nie trzymaj sekretów tam, gdzie ich nie ma")."""
    paths = paths_for(REPO_ROOT)
    state = state_for_name(load_state(paths), args.name)
    api_port = resolved_value(args.api_port, state, "api_port", DEFAULT_API_PORT)
    api = f"http://127.0.0.1:{api_port}"

    if not wait_for_live(f"{api}/health/live", timeout=5.0):
        print(f"seed: nothing is answering at {api}; run 'stack.py up' first", file=sys.stderr)
        return 1

    tree = Path(args.tree).resolve() if args.tree else (
        HOME / ".cache/guidefold/seed" / args.name / "monorepo")
    home = HOME / ".cache/guidefold/seed" / args.name / "home"

    try:
        session = dev_login(api, subject=args.subject, email=args.email, name=args.subject)
        org_id = ensure_org(session, args.org)
        ensure_repo(session, args.org, args.repo, args.git_host_url)
        token = device_token(api, session)
        commit = prepare_tree(paths.repo_root / "examples" / "monorepo", tree)
        env = cli_env(api=api, org=args.org, repo=args.repo, token=token, home=home)
        result = run_cli(paths, ["import", "--wait", "--json"], cwd=tree, env=env)
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        imported = last_json_object(result.stdout)
    except SeedError as e:
        print(f"seed failed: {e}", file=sys.stderr)
        return 1

    token_file = write_secret(paths.dev_dir / "seed" / f"{args.name}-token", token)
    out = {
        "api": api,
        "ui": f"http://127.0.0.1:{UI_PORT}/?mode=api&org={args.org}&repo={args.repo}",
        "org_slug": args.org,
        "org_id": org_id,
        "repo_id": args.repo,
        "user_id": session.user.get("id"),
        "email": args.email,
        "tree": str(tree),
        "commit": commit,
        "cli_home": str(home),
        "token_file": str(token_file),
        "import_id": imported.get("import_id"),
        "import_state": imported.get("state"),
        "manifest_digest": imported.get("manifest_digest"),
        "files": imported.get("files"),
        "new_blobs": imported.get("new_blobs"),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    paths = paths_for(REPO_ROOT)
    stop_pid(paths.ui_pid, "ui", needle="vite")
    stop_pid(paths.worker_pid, "worker", needle="guidefold-search")
    stop_pid(paths.api_pid, "api", needle="guidefold-search")
    if args.stop_pg:
        pg.stop(args.name)
    else:
        print(f"pg: left running (pass --stop-pg to stop '{args.name}')")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = paths_for(REPO_ROOT)
    state = state_for_name(load_state(paths), args.name)
    pg_port = resolved_value(None, state, "pg_port", DEFAULT_PG_PORT)
    api_port = resolved_value(None, state, "api_port", DEFAULT_API_PORT)

    running = pg.is_running(args.name)
    print(f"pg      : {'running' if running else 'stopped'}  "
          f"(postgresql://127.0.0.1:{pg_port}/guidefold, data {pg.data_dir(args.name)})")

    api_pid = read_pid(paths.api_pid)
    api_alive = bool(api_pid and process_alive(api_pid))
    print(f"api     : {'running (pid ' + str(api_pid) + ')' if api_alive else 'stopped'}  "
          f"(http://127.0.0.1:{api_port})")
    if api_alive:
        try:
            status, body = http_get(f"http://127.0.0.1:{api_port}/health/ready", timeout=2.0)
            print(f"          {describe_ready(status, body)}")
        except (urllib.error.URLError, OSError) as e:
            print(f"          health check failed: {e}")

    worker_pid = read_pid(paths.worker_pid)
    worker_alive = bool(worker_pid and process_alive(worker_pid))
    print(f"worker  : {'running (pid ' + str(worker_pid) + ')' if worker_alive else 'stopped'}  "
          f"(no HTTP endpoint; leases gfm.jobs)")

    ui_pid = read_pid(paths.ui_pid)
    ui_alive = bool(ui_pid and process_alive(ui_pid))
    print(f"ui      : {'running (pid ' + str(ui_pid) + ')' if ui_alive else 'stopped'}  "
          f"(http://127.0.0.1:{UI_PORT})")
    return 0


LOG_PATHS = {
    "api": lambda p: p.api_log,
    "worker": lambda p: p.worker_log,
    "ui": lambda p: p.ui_log,
}


def cmd_logs(args: argparse.Namespace) -> int:
    paths = paths_for(REPO_ROOT)
    if args.component == "pg":
        log_path = pg.data_dir(args.name).parent / f"{args.name}.log"
    else:
        log_path = LOG_PATHS[args.component](paths)
    print(tail_lines(log_path, args.lines))
    if args.follow:
        if not log_path.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch()
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, os.SEEK_END)
            try:
                while True:
                    line = fh.readline()
                    if line:
                        print(line, end="")
                    else:
                        time.sleep(0.5)
            except KeyboardInterrupt:
                pass
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    paths = paths_for(REPO_ROOT)
    state = state_for_name(load_state(paths), args.name)
    pg_port = resolved_value(None, state, "pg_port", DEFAULT_PG_PORT)
    api_port = resolved_value(None, state, "api_port", DEFAULT_API_PORT)
    secret_paths = {n: paths.secrets_dir / n for n in SECRET_NAMES}
    print(f"export GUIDEFOLD_API=http://127.0.0.1:{api_port}")
    print(f"export GUIDEFOLD_TOKEN_FILE={secret_paths['api_token']}")
    print("export GUIDEFOLD_TENANT=local")
    print("export GUIDEFOLD_REPO=meridian")
    print(f"export PGHOST=127.0.0.1 PGPORT={pg_port} PGDATABASE=guidefold PGUSER=guidefold_api PGSSLMODE=disable")
    print(f"export PG_PASSWORD_FILE={secret_paths['app_password']}")
    print(f"export GUIDEFOLD_PG_BIN={pg.pg_bin()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="build and start pg, the API, the worker and (optionally) the UI")
    up.add_argument("--name", default=DEFAULT_NAME)
    up.add_argument("--pg-port", type=int, default=DEFAULT_PG_PORT)
    up.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    up.add_argument("--ui", action="store_true")
    up.add_argument("--generator", choices=["none", "deterministic"], default=DEFAULT_GENERATOR)
    up.add_argument("--reset", action="store_true")
    up.add_argument("--auth", choices=["dev", "workos"], default="dev",
                     help="dev: local sign-in form (default). workos: real AuthKit login -- "
                          "requires --workos-client-id and --workos-api-key-file")
    up.add_argument("--workos-client-id", default="",
                     help="WorkOS AuthKit client ID (not secret, an OAuth-style client identifier)")
    up.add_argument("--workos-api-key-file", default="",
                     help="path to a file holding the WorkOS secret API key (sk_...); never "
                          "pass the key value itself on the command line")
    up.set_defaults(func=cmd_up)

    seed = sub.add_parser("seed", help="dev login + org + repo + device token + CLI import of "
                                       "a copy of examples/monorepo; prints the ids as JSON")
    seed.add_argument("--name", default=DEFAULT_NAME)
    seed.add_argument("--api-port", type=int, default=None)
    seed.add_argument("--org", default=DEFAULT_ORG_SLUG)
    seed.add_argument("--repo", default=DEFAULT_REPO_ID)
    seed.add_argument("--email", default=DEFAULT_SEED_EMAIL)
    seed.add_argument("--subject", default="seed-owner")
    seed.add_argument("--git-host-url", default="https://github.example.test/acme/meridian")
    seed.add_argument("--tree", default=None, help="where to materialise the monorepo copy "
                                                   "(default ~/.cache/guidefold/seed/<name>/monorepo)")
    seed.set_defaults(func=cmd_seed)

    down = sub.add_parser("down", help="stop the API/worker/UI; pg is left running unless --stop-pg")
    down.add_argument("--name", default=DEFAULT_NAME)
    down.add_argument("--stop-pg", action="store_true")
    down.set_defaults(func=cmd_down)

    status = sub.add_parser("status", help="show each component and its health URL")
    status.add_argument("--name", default=DEFAULT_NAME)
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="print (optionally follow) one component's log")
    logs.add_argument("component", choices=["api", "worker", "pg", "ui"])
    logs.add_argument("--name", default=DEFAULT_NAME)
    logs.add_argument("-n", "--lines", type=int, default=200)
    logs.add_argument("-f", "--follow", action="store_true")
    logs.set_defaults(func=cmd_logs)

    env = sub.add_parser("env", help="print shell exports for the running stack")
    env.add_argument("--name", default=DEFAULT_NAME)
    env.set_defaults(func=cmd_env)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
