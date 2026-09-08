"""Acceptance suite — the real stack, the real CLI, the real report.

Opt-in: nothing here is collected unless ``GUIDEFOLD_ACCEPTANCE=1``. The suite builds the Go
binary, wipes and starts its own PostgreSQL cluster on a free port, migrates, and runs
``serve`` + ``worker`` on another free port, so it never collides with a developer's
``tools/dev/stack.py up``. Teardown stops all three and writes
``.guidefold/checks/acceptance-<UTC date>.{json,md}``.

    GUIDEFOLD_ACCEPTANCE=1 python3 -m pytest tests/acceptance -q

What this suite proves is level **R** (release acceptance on the product path). It does not
prove routing quality (that needs the pinned labelled corpora), and it does not prove pilot
value (that needs people). Rows it cannot measure are written as ``not_measured_here``.
"""
from __future__ import annotations

import importlib.util
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

ENABLED = os.environ.get("GUIDEFOLD_ACCEPTANCE") == "1"
if not ENABLED:
    # `pytest tests` (the default run) must stay hermetic and fast: no Go build, no PostgreSQL.
    collect_ignore_glob = ["test_*.py"]

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("gf_acceptance_support", _HERE / "_support.py")
support = importlib.util.module_from_spec(_spec)
sys.modules["gf_acceptance_support"] = support
_spec.loader.exec_module(support)

REPO_ROOT = support.REPO_ROOT
PASS, FAIL, NOT_MEASURED = support.PASS, support.FAIL, support.NOT_MEASURED


def pytest_configure(config):
    config.addinivalue_line("markers", "acceptance: opt-in acceptance run against the real stack")
    config.addinivalue_line("markers", "acc(acc_id): the acceptance criterion this test measures")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Keep each phase's result on the item so `_acc_row_is_never_lost` can see a failure."""
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())


@pytest.fixture(autouse=True)
def _acc_row_is_never_lost(request, report):
    """A test that dies before `report.record` must still leave a row.

    Without this a crash silently removes the criterion from the report, and a shorter table
    reads like a smaller problem than it is. The row it writes is a `fail` carrying the
    exception, never a pass."""
    yield
    marker = request.node.get_closest_marker("acc")
    if marker is None or not marker.args:
        return
    acc_id = marker.args[0]
    if any(row["acc_id"] == acc_id for row in report.rows):
        return
    outcome = getattr(request.node, "rep_call", None) or getattr(request.node, "rep_setup", None)
    if outcome is None or outcome.passed:
        return
    report.record(acc_id, prd_ac=marker.kwargs.get("prd_ac", acc_id),
                  scenario=marker.kwargs.get("scenario", request.node.name),
                  command_or_endpoint=marker.kwargs.get("command", "see the test body"),
                  data_origin="this run's local stack",
                  result=FAIL,
                  evidence={"pytest_node": request.node.nodeid,
                            "phase": "setup" if outcome is getattr(request.node, "rep_setup", None)
                                     else "call",
                            "error": _short(outcome.longreprtext)},
                  limitation="The test did not reach its own recording point; this row is the "
                             "harness reporting its own failure, not a measurement.")


def _short(text: str, limit: int = 1500) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " …[truncated]"


# ---------------------------------------------------------------------------------------
# Session stack + report
# ---------------------------------------------------------------------------------------


def _version(argv: list) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:  # pragma: no cover - informational only
        return "unavailable"


@pytest.fixture(scope="session")
def report():
    """Collects one row per acceptance criterion and writes both twins at teardown."""
    r = support.Report()
    r.environment = {
        "host": platform.node(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "go": _version([str(support.stack.GO_BIN_DIR / "go"), "version"]),
        "postgres": _version([str(support.pg.pg_bin() / "postgres"), "--version"]),
        "git": _version(["git", "--version"]),
        "repo_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                                      capture_output=True, text=True).stdout.strip(),
        "network": "loopback only (127.0.0.1); no external network, no GCP, no vendor API",
        "evidence_level": "R (release acceptance on the product path)",
    }
    yield r
    json_path, md_path = r.write(REPO_ROOT / ".guidefold" / "checks")
    counts = r.counts()
    sys.stderr.write(
        f"\n\nacceptance report: {counts[PASS]} pass, {counts[FAIL]} fail, "
        f"{counts[NOT_MEASURED]} not_measured_here\n  {json_path}\n  {md_path}\n")


@pytest.fixture(scope="session")
def gf_stack(report):
    """The whole product stack on free ports: PostgreSQL, `serve`, `worker`."""
    s = support.start_stack(name="acceptance", generator="deterministic")
    report.environment["api"] = s.api
    report.environment["pg_port"] = s.pg_port
    report.environment["generator"] = s.generator
    try:
        yield s
    finally:
        support.stop_stack(s)


@pytest.fixture(scope="session")
def scratch() -> Path:
    """Working trees and CLI homes for the whole session, outside the repository and /tmp."""
    root = Path.home() / ".cache" / "guidefold" / "acceptance"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------------------
# The seeded world every test shares
# ---------------------------------------------------------------------------------------


@dataclass
class World:
    """One organisation, one repository, one imported monorepo, and the ways in."""
    stack: object
    owner: object                 # ApiSession — the browser's view
    org: str
    org_id: str
    repo: str
    tree: Path
    commit: str
    cli: object                   # Cli — the shipped script, personal token
    personal_token: str
    git_host_url: str
    import_id: Optional[str] = None
    installation_token: Optional[str] = None
    installation_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    facts: dict = field(default_factory=dict)

    @property
    def api(self) -> str:
        return self.stack.api

    @property
    def base(self) -> str:
        return f"/api/v1/orgs/{self.org}/repos/{self.repo}"

    @property
    def org_base(self) -> str:
        return f"/api/v1/orgs/{self.org}"

    def get(self, path: str, **kw) -> dict:
        return self.owner.expect("GET", self.base + path, **kw)

    def raw(self, method: str, path: str, **kw):
        return self.owner.request(method, self.base + path, **kw)


def _new_session(stack_obj, subject: str, email: str):
    return support.stack.dev_login(stack_obj.api, subject=subject, email=email, name=subject)


@pytest.fixture(scope="session")
def world(gf_stack, scratch) -> World:
    """ACT-01's own organisation: signed in, repository registered, CLI logged in.

    Deliberately stops short of importing -- ACT-01 owns every step from `scan` onwards, so the
    end-to-end row measures the product path rather than reporting on work a fixture did. Every
    other test takes a throwaway tenant from ``fresh_org`` instead, because ACT-01 ends by
    drifting this one on purpose."""
    owner = _new_session(gf_stack, "acc-owner", "owner@acceptance.test")
    org_id = support.stack.ensure_org(owner, "acme")
    git_host_url = "https://github.example.test/acme/meridian"
    support.stack.ensure_repo(owner, "acme", "meridian", git_host_url)

    tree = scratch / "meridian"
    commit = support.make_git_tree(tree)
    cli = support.Cli(home=scratch / "cli-home", api=gf_stack.api)
    support.cli_device_login(cli, owner, cwd=tree)
    creds = support.json.loads(cli.credentials.read_text())
    token = creds[gf_stack.api]["token"]
    cli.token, cli.org, cli.repo = token, "acme", "meridian"
    return World(stack=gf_stack, owner=owner, org="acme", org_id=org_id, repo="meridian",
                 tree=tree, commit=commit, cli=cli, personal_token=token,
                 git_host_url=git_host_url)


@pytest.fixture(scope="session")
def installation(world) -> str:
    """An installation token bound to this org and repo: the adapter's own credential.

    Bound tokens are how `find`/`load` reach the right tenant without the CLI ever sending an
    `X-Guidefold-Org` header (the shipped client sends only `Authorization`)."""
    created = world.owner.expect(
        "POST", world.org_base + "/installations", ok=(200, 201),
        body={"name": "acceptance-claude", "kind": "installation", "repo_id": world.repo,
              "scopes": ["search", "use", "events"], "harness": "claude-code"},
        headers={"Idempotency-Key": "acc-installation-1"})
    world.installation_token = created["token"]
    world.installation_id = created["installation_id"]
    return created["token"]


# ---------------------------------------------------------------------------------------
# Isolated worlds for destructive scenarios
# ---------------------------------------------------------------------------------------


@pytest.fixture
def fresh_org(gf_stack, scratch, request):
    """A throwaway organisation + repository + owner session + CLI, for tests that break things.

    Drift, partial scans, membership revocation and cross-organisation probes all mutate state
    another test would then read. Each gets its own tenant instead."""
    made = []

    def make(slug: str, *, repo: str = "monorepo", subject: Optional[str] = None,
             email: Optional[str] = None, git_host_url: str = "https://github.example.test/x/y"):
        session = _new_session(gf_stack, subject or f"{slug}-owner", email or f"{slug}@acceptance.test")
        org_id = support.stack.ensure_org(session, slug)
        support.stack.ensure_repo(session, slug, repo, git_host_url)
        home = scratch / f"cli-{slug}"
        cli = support.Cli(home=home, api=gf_stack.api, org=slug, repo=repo)
        token = support.stack.device_token(gf_stack.api, session)
        cli.token = token
        w = World(stack=gf_stack, owner=session, org=slug, org_id=org_id, repo=repo,
                  tree=scratch / f"tree-{slug}", commit="", cli=cli, personal_token=token,
                  git_host_url=git_host_url)
        made.append(w)
        return w

    yield make


# ---------------------------------------------------------------------------------------
# Shared moves
# ---------------------------------------------------------------------------------------


@pytest.fixture
def bring_up(gf_stack):
    """Import (and optionally publish) a tree into a world, through the CLI and the API.

    Returns ``(import_status, snapshot)``. Used by every test that needs a populated catalog
    but is not itself measuring the import."""

    def run(w: World, *, source: Optional[Path] = None, publish: bool = True,
            wait_active: bool = True, runbooks: bool = False):
        w.commit = support.make_git_tree(w.tree, source)
        if runbooks:
            support.add_runbooks(w.tree)
            w.commit = support.commit_all(w.tree, "add runbooks with ordered procedures")
        result = w.cli.json(["import", "--wait", "--json"], cwd=w.tree)
        w.import_id = result["import_id"]
        status = w.get(f"/imports/{w.import_id}")
        if not publish:
            return status, None
        gf_stack.assert_cli_unchanged()
        w.owner.expect("POST", w.base + "/publish", ok=(200,),
                       body={"idempotency_key": f"pub-{w.import_id}", "import_id": w.import_id})
        if not wait_active:
            return status, None
        snapshot = support.wait_until(
            lambda: next((s for s in w.owner.expect("GET", w.base + "/snapshots")["items"]
                          if s["state"] in ("active", "failed")), None),
            timeout=180, what="a terminal publication state")
        assert snapshot["state"] == "active", f"publication failed: {snapshot.get('error')}"
        w.snapshot_id = snapshot["snapshot_id"]
        return status, snapshot

    return run


@pytest.fixture(scope="session")
def socket_guard(scratch) -> Path:
    """A ``sitecustomize.py`` that makes any outbound connect() raise.

    Put on ``PYTHONPATH`` for a subprocess, it turns "this command opens no socket" from a
    claim into a check: the command dies loudly if it tries."""
    guard = scratch / "socket-guard"
    guard.mkdir(parents=True, exist_ok=True)
    (guard / "sitecustomize.py").write_text(
        "import socket\n"
        "\n"
        "def _deny(*args, **kwargs):\n"
        "    raise RuntimeError('acceptance socket guard: this command must open no socket')\n"
        "\n"
        "socket.socket.connect = _deny\n"
        "socket.socket.connect_ex = _deny\n"
        "socket.create_connection = _deny\n",
        encoding="utf-8")
    return guard
