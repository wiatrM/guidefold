"""Shared pytest fixtures for the guidefold test suite.

The CLI (`skills/guidefold/scripts/guidefold`) is a single extension-less script, so it is
loaded as a module named "guidefold" via importlib rather than a normal package import.
"""
import json
import os
import shutil
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
FIXTURE_ROOT = REPO_ROOT / "examples" / "monorepo"


def _load_cli_module():
    loader = SourceFileLoader("guidefold", str(CLI_PATH))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    sys.modules["guidefold"] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gf():
    """The guidefold CLI, imported as a module."""
    return _load_cli_module()


@pytest.fixture
def fixture_root():
    """The 'Meridian' example monorepo (examples/monorepo) used as a read-only fixture."""
    assert FIXTURE_ROOT.is_dir(), f"fixture missing: {FIXTURE_ROOT}"
    return FIXTURE_ROOT


@pytest.fixture
def fixture_copy(tmp_path, fixture_root):
    """A throwaway copy of the fixture monorepo, for commands that write files (index, materialize)."""
    dest = tmp_path / "meridian-copy"
    shutil.copytree(fixture_root, dest)
    return dest


@pytest.fixture(autouse=True)
def _guard_fixture_root_read_only(fixture_root):
    """`fixture_root` is documented above as read-only for the suite -- `fixture_copy` exists
    precisely for commands that write files. `find`/`hook`/`load` now also emit SEARCH/USE
    telemetry (docs/SEARCH-USE-TELEMETRY.md) into `<cwd>/.guidefold/telemetry/...` on every
    invocation, including from tests that intentionally call `run_cli` with `cwd=fixture_root`
    (e.g. test_acceptance_smoke.py, test_cli_smoke.py) because search itself is still read-only
    from their point of view. Strip any such generated `.guidefold/` state after every test so it
    can never leak into another test's `fixture_copy` (shutil.copytree would otherwise copy it in
    and break tests that assert `.guidefold` is absent/pristine in a fresh copy)."""
    yield
    shutil.rmtree(fixture_root / ".guidefold", ignore_errors=True)


@pytest.fixture
def tmp_repo(tmp_path):
    """A tiny, fully-valid throwaway monorepo (guidefold.yaml + 3 skills) for tests that mutate it."""
    from _helpers import build_tmp_repo
    return build_tmp_repo(tmp_path / "acme")


class FakeGcloud:
    """Stands in for the real `gcloud` binary: records every invocation and dispatches to
    scripted responses. Anything that isn't a `gcloud ...` call (e.g. `git ...`, used by
    repo_root()/cmd_drift/cmd_publish) passes through to the real subprocess.run untouched, so
    only the Registry's gcloud plumbing is ever faked."""

    def __init__(self):
        self.calls = []       # list[list[str]], full argv, in call order
        self._rules = []      # list[(matcher, handler)]
        self._real_run = subprocess.run

    def rule(self, *substrings, json_body=None, text=None, returncode=0, handler=None):
        """Respond to any call whose argv contains every one of `substrings` (as whole tokens).

        `handler(cmd)` (if given) takes full control and must return an object with
        `.returncode`/`.stdout`/`.stderr` — use it when the response needs side effects (e.g.
        writing files for `revisions download`). Otherwise a canned response is built from
        `json_body` (serialised only when the call asked for --format=json), `text` (raw stdout
        for non-JSON calls) and `returncode`. Rules are matched most-recently-registered-first,
        so a later, more specific rule can override an earlier catch-all one.
        """
        def matches(cmd):
            return all(s in cmd for s in substrings)

        if handler is None:
            def handler(cmd, _json_body=json_body, _text=text, _rc=returncode):
                if "--format=json" in cmd:
                    stdout = "" if _json_body is None else json.dumps(_json_body)
                else:
                    stdout = _text or ""
                return SimpleNamespace(returncode=_rc, stdout=stdout, stderr="" if _rc == 0 else "fake gcloud error")

        self._rules.append((matches, handler))

    def __call__(self, cmd, capture_output=True, text=True, cwd=None, **kw):
        if not cmd or cmd[0] != "gcloud":
            return self._real_run(cmd, capture_output=capture_output, text=text, cwd=cwd, **kw)
        self.calls.append(list(cmd))
        for matches, handler in reversed(self._rules):
            if matches(cmd):
                return handler(cmd)
        raise AssertionError(f"fake_gcloud: no rule scripted for: {cmd!r}")


@pytest.fixture
def fake_gcloud(gf, monkeypatch):
    """Monkeypatches subprocess.run as seen by the CLI module so Registry never calls real gcloud."""
    fake = FakeGcloud()
    monkeypatch.setattr(gf.subprocess, "run", fake)
    return fake


@pytest.fixture
def run_cli(tmp_path):
    """Run the CLI as a real subprocess (end-to-end smoke tests).

    Defaults $GUIDEFOLD_CACHE to a per-test tmp dir so `index`/`hook` (E1.4/E1.5's real on-disk
    artifact) and `load`/`prewarm` (E1.7's skill cache) never touch the developer's actual
    ~/.cache/guidefold as a side effect of running the test suite. Pass env=... to override."""
    def _run(args, cwd, **kw):
        env = kw.pop("env", None)
        if env is None:
            env = {**os.environ, "GUIDEFOLD_CACHE": str(tmp_path / ".cache-guidefold")}
        return subprocess.run([sys.executable, str(CLI_PATH), *args], cwd=str(cwd),
                               capture_output=True, text=True, env=env, **kw)
    return _run
