#!/usr/bin/env python3
"""E1.5 acceptance: measure `guidefold hook` latency over the 220-case golden set.

Each measurement is a genuinely fresh `python3 .../guidefold hook` subprocess (never an in-process
call) -- that's the real Claude Code / Codex hook invocation model, and it's also what makes the
determinism claim in tests/test_hook.py non-tautological (each subprocess gets its own randomised
PYTHONHASHSEED unless one is pinned). "Warm" here means "the on-disk artifact is already in the
OS page cache", not a long-lived process: one throwaway invocation primes the cache, then all 220
real cases are timed.

Usage:
    python3 tools/eval/measure_hook_latency.py

Builds the E1.4 index artifact for examples/monorepo fresh (into a scratch $GUIDEFOLD_CACHE, never
the developer's real ~/.cache/guidefold), then times one `guidefold hook` subprocess per golden
case, reporting p50/p95/mean/min/max and the machine this ran on -- honestly, not aspirationally.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MONOREPO_DIR = REPO_ROOT / "examples" / "monorepo"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_golden import load_cases  # noqa: E402  (needs the sys.path insert above)


def _machine_spec() -> str:
    """Report the real machine, not an aspirational one -- there is no corporate laptop."""
    uname = os.uname()
    cpu = "unknown CPU"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    glibc = "unknown glibc"
    try:
        out = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        glibc = out.stdout.splitlines()[0].strip()
    except Exception:
        pass
    return (f"{uname.sysname} {uname.release} ({uname.machine}), {cpu}, "
            f"{os.cpu_count()} threads, {glibc}, CPython {sys.version.split()[0]}")


def _run_hook(cache_dir: Path, cwd: Path, prompt: str) -> float:
    payload = json.dumps({"cwd": str(cwd), "prompt": prompt})
    env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir)}
    t0 = time.perf_counter()
    result = subprocess.run([sys.executable, str(CLI_PATH), "hook"], cwd=str(cwd), input=payload,
                             capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        raise RuntimeError(f"hook exited {result.returncode}: {result.stderr}")
    return elapsed


def _percentile(sorted_vals: list, pct: float) -> float:
    """Nearest-rank percentile over an already-sorted list (no numpy dependency -- stdlib only,
    per this repo's hard constraint)."""
    if not sorted_vals:
        return float("nan")
    k = max(0, min(len(sorted_vals) - 1, int(round(pct / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="guidefold-hook-latency-") as tmp:
        cache_dir = Path(tmp) / ".cache-guidefold"
        env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir)}

        build = subprocess.run([sys.executable, str(CLI_PATH), "index"], cwd=str(MONOREPO_DIR),
                                capture_output=True, text=True, env=env)
        if build.returncode != 0:
            print(build.stderr, file=sys.stderr)
            return 1

        cases = load_cases()
        print(f"loaded {len(cases)} golden cases")

        # Warm the OS page cache for the artifact files with one throwaway invocation.
        first = cases[0]
        _run_hook(cache_dir, MONOREPO_DIR / first["cwd"], first["query"])

        durations = []
        for c in cases:
            cwd = (MONOREPO_DIR / c["cwd"]).resolve()
            durations.append(_run_hook(cache_dir, cwd, c["query"]))

        durations_sorted = sorted(durations)
        p50 = _percentile(durations_sorted, 50)
        p95 = _percentile(durations_sorted, 95)
        mean = statistics.fmean(durations)

        print(f"\nmachine: {_machine_spec()}")
        print(f"n={len(durations)}  (one warm-up invocation excluded from these numbers)")
        print(f"p50={p50 * 1000:.1f}ms  p95={p95 * 1000:.1f}ms  "
              f"mean={mean * 1000:.1f}ms  min={min(durations) * 1000:.1f}ms  max={max(durations) * 1000:.1f}ms")
        print("\nROUTER-SPEC budget: 300ms warm / 3s hard watchdog. Each number above is a full "
              "fresh-interpreter subprocess (python3 startup + import + hook logic), which is the "
              "real invocation cost a harness pays on every prompt -- there is no long-lived "
              "warm process in this design.")
        if p95 > 0.300:
            print(f"NOTE: p95 ({p95 * 1000:.1f}ms) exceeds the 300ms warm budget on this measurement "
                  f"-- reported as measured, not adjusted.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
