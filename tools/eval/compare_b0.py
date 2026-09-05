"""B0 (original CLI, scope-only ranking) vs Router 0.1 on the 220-case golden set.

B0 is the literal CLI from commit 984d08c, extracted from git and run as a subprocess at each
case's cwd -- no reimplementation, so a comparison against it cannot flatter newer code by
accident. See docs/reports/golden/README.md for the published Router-0.1-vs-B0 table this
script originally produced; E1.3 phase 2 (docs/reports/bakeoff/E1.3-embedder-selection.md)
reuses `run_b0` below as its own B0 row over the same 220 cases.

Usage:
    python3 tools/eval/compare_b0.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
B0_COMMIT = "984d08c"  # scope-only CLI, before the Router split (PR #7)
FIX = ROOT / "examples" / "monorepo"
GOLDEN_DIR = ROOT / "tests" / "golden"
URN_RE = re.compile(r"^- (urn:skill:\S+)", re.M)


def _load_metrics():
    spec = importlib.util.spec_from_file_location("gf_metrics", ROOT / "tools" / "eval" / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_b0_source(commit: str = B0_COMMIT) -> pathlib.Path:
    """Extract the CLI exactly as it existed at `commit`, straight from git, to a temp file.
    No reimplementation -- the comparison cannot flatter new code by accident."""
    out = subprocess.run(
        ["git", "show", f"{commit}:skills/guidefold/scripts/guidefold"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0 and out.stdout, (
        f"could not extract the B0 CLI from commit {commit}: {out.stderr}"
    )
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="guidefold-b0-"))
    path = tmp_dir / "guidefold_B0.py"
    path.write_text(out.stdout)
    return path


def load_cases() -> list:
    """Every case across the five golden-set category files, `category` copied down from the
    file-level key onto each case dict (same shape tools/eval/run_golden.py's load_cases uses)."""
    cases = []
    for fname in sorted(GOLDEN_DIR.glob("*.yaml")):
        doc = yaml.safe_load(fname.read_text())
        category = doc.get("category")
        for c in doc.get("cases", []):
            c = dict(c)
            c.setdefault("category", category)
            cases.append(c)
    return cases


def run_b0(cases: list, limit: int = 8, b0_path: pathlib.Path = None, progress: bool = True) -> tuple:
    """Run the extracted B0 CLI as a subprocess per case, at that case's own cwd (exactly how a
    developer would have invoked it). Returns `(results, elapsed_seconds)` where `results` is a
    list of `(ranked_urns, case)` pairs -- the same shape every other arm and `metrics.evaluate`
    expect."""
    b0_path = b0_path or extract_b0_source()
    results = []
    t0 = time.time()
    for i, c in enumerate(cases):
        cwd = FIX if c.get("cwd", ".") == "." else FIX / c["cwd"]
        out = subprocess.run(
            [sys.executable, str(b0_path), "find", c["query"], "--limit", str(limit)],
            cwd=cwd, capture_output=True, text=True,
        )
        results.append((URN_RE.findall(out.stdout), c))
        if progress and i % 40 == 0:
            print(f"  b0: {i}/{len(cases)}", file=sys.stderr)
    elapsed = time.time() - t0
    return results, elapsed


if __name__ == "__main__":
    metrics = _load_metrics()
    cases = load_cases()
    print(f"{len(cases)} golden cases", file=sys.stderr)
    results, elapsed = run_b0(cases)
    overall = metrics.evaluate(results)
    per_cat = metrics.by_category(results)
    print(metrics.format_table(overall, per_cat))
    print(f"\ntotal wall-clock: {elapsed:.1f}s ({elapsed / len(cases) * 1000:.1f}ms/query)", file=sys.stderr)
