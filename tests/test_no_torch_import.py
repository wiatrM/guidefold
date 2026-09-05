"""E1.6 non-negotiable: no torch import is reachable from `skills/guidefold/scripts/guidefold`.

The shipped CLI is stdlib + PyYAML only (repo CLAUDE.md's hard constraint) -- it ships inside the
skill ZIP to the registry and can never depend on torch/transformers, which is exactly why
`find --experimental` (E1.6) only writes a shadow telemetry record instead of running the
reranker in-process (that happens offline, in `tools/bakeoff/rerank_shadow.py`, Tier 2).

Two checks, from different angles, both needed:
  * importing the CLI module with `torch` poisoned in `sys.modules` -- proves module-level code
    never does `import torch`.
  * running `find --experimental` as a real subprocess with `torch` poisoned the same way --
    proves no code path exercised by the command's normal flow (argument parsing, routing,
    telemetry writing) imports it either, not just the top-level module body.
"""
import os
import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"


class _TorchIsForbidden:
    """Any `import torch` (or `from torch import ...`) must raise, not silently succeed.

    Implements the modern `find_spec` finder protocol, not the legacy `find_module`/`load_module`
    pair -- CPython 3.12 dropped the compatibility shim that let a `find_spec`-less finder still
    be consulted via `find_module`, so a finder without `find_spec` is simply never asked and this
    guard would silently do nothing on the newest interpreter in this repo's CI matrix.
    """

    def find_spec(self, name, path=None, target=None):
        if name == "torch" or name.startswith("torch."):
            raise ImportError(f"torch must never be imported by the shipped CLI (attempted: {name})")
        return None


def test_cli_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """Load the CLI as a fresh module while `torch` is poisoned in sys.modules AND blocked at the
    import-machinery level, so neither `import torch` nor a cached `sys.modules['torch']` lookup
    can quietly succeed."""
    monkeypatch.setitem(sys.modules, "torch", None)  # a bare `import torch` raises ImportError
    blocker = _TorchIsForbidden()
    sys.meta_path.insert(0, blocker)
    try:
        loader = SourceFileLoader("guidefold_no_torch_check", str(CLI_PATH))
        spec = spec_from_loader(loader.name, loader)
        module = module_from_spec(spec)
        loader.exec_module(module)  # raises if the module body imports torch anywhere
        assert hasattr(module, "main")
        assert "torch" not in sys.modules or sys.modules["torch"] is None
    finally:
        sys.meta_path.remove(blocker)


def test_find_experimental_subprocess_never_imports_torch(run_cli, fixture_copy):
    """Same guarantee, exercised end-to-end: a real `find --experimental` invocation, in a fresh
    interpreter that cannot import torch at all, must still succeed and behave normally."""
    poison = (
        "import sys, importlib.abc\n"
        "class _Blocker(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name == 'torch' or name.startswith('torch.'):\n"
        "            raise ImportError('torch must never be imported by the shipped CLI')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Blocker())\n"
    )
    sitecustomize = fixture_copy / "sitecustomize.py"
    sitecustomize.write_text(poison, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(fixture_copy) + os.pathsep + env.get("PYTHONPATH", "")

    result = run_cli(["find", "add RBAC to this new admin-only endpoint", "--experimental"],
                      cwd=fixture_copy, env=env)
    assert result.returncode == 0, result.stderr
    assert "urn:skill:meridian:" in result.stdout
