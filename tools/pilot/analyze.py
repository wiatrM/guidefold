#!/usr/bin/env python3
"""Paired analysis for the E6.7 pilot (stdlib only; see docs/pilot/E6.7-PROTOCOL.md).

Reads a scoring sheet (docs/pilot/scoring-sheet.template.csv's schema: one row per
(task, condition) run) and reports, for each frozen contrast:

  * gain rate, regression rate and their difference (docs/pilot/E6.7-PROTOCOL.md §1 H1,
    SEARCH-USE-TELEMETRY.md §6 KPI 3, quoted verbatim there) with a discordant-pair Wilson
    score interval and an exact (Clopper-Pearson) interval on the same difference;
  * a paired bootstrap CI on the mean delta of time and of tokens (H2);
  * coverage: evaluable / excluded-unknown / duplicate counts, never silently dropped.

Refuses to run against an unfrozen protocol: the scoring sheet's first line must read
`# protocol_sha256=<64 lowercase hex chars>`, not the template's `PLACEHOLDER-UNFROZEN` token
(docs/pilot/E6.7-PROTOCOL.md §11 Freeze procedure; §6 forbidden moves — "one analysis per frozen
protocol version"). Pass --protocol-file to additionally verify that sha256 against the protocol
document's actual bytes on disk.

    python3 tools/pilot/analyze.py --csv path/to/scoring-sheet.csv
    python3 tools/pilot/analyze.py --csv path/to/scoring-sheet.csv --contrast contender_vs_sparse
    python3 tools/pilot/analyze.py --csv path/to/scoring-sheet.csv --protocol-file docs/pilot/E6.7-PROTOCOL.md

This script does not decide adoption. It reports the numbers the protocol pre-registered; §5
(Power and uncertainty) of the protocol states, separately, what n an adoption claim would need.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical condition codes (docs/pilot/E6.7-PROTOCOL.md §2): A/B/C/D in the protocol's prose.
NO_SKILLS = "no_skills"
SPARSE = "sparse"
CONTENDER = "contender"
ORACLE = "oracle"
CONDITIONS = (NO_SKILLS, SPARSE, CONTENDER, ORACLE)

# The two frozen, pre-registered pairwise contrasts (docs/pilot/E6.7-PROTOCOL.md §2/§5). Neither
# is added or swapped after seeing data; ORACLE is reported separately as a headroom diagnostic,
# never as a gain/regression hypothesis (it is not a deployable condition).
CONTRASTS = {
    "sparse_vs_no_skills": (NO_SKILLS, SPARSE),      # H1 headline: does shipping skills help at all
    "contender_vs_sparse": (SPARSE, CONTENDER),      # H1 promotion: does the contender beat what ships today
}

OUTCOME_VALUES = {"success", "failure"}  # anything else (blank, "unknown", garbage) is unknown
Z_95 = 1.959963985  # two-sided 95% normal quantile


# --------------------------------------------------------------------------- errors

class UnfrozenProtocolError(RuntimeError):
    """Raised when the scoring sheet's protocol_sha256 header is missing, malformed, or the
    template placeholder — i.e. there is no frozen protocol to analyze against."""


class DuplicateRunError(RuntimeError):
    """Raised when the same (task, condition) pair appears more than once — a re-run, which
    docs/pilot/E6.7-PROTOCOL.md §6 forbids."""


class ProtocolMismatchError(RuntimeError):
    """Raised when --protocol-file's actual sha256 does not match the scoring sheet's header."""


_SHA256_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------- loading

@dataclass
class Row:
    task: str
    condition: str
    order: str
    developer_pseudonym: str
    outcome: str
    time_seconds: float | None
    tokens: float | None
    loads: float | None
    feedback_verdict: str
    evaluator: str
    notes: str


def _parse_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s or s.lower() == "unknown":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_protocol_sha_header(first_line: str) -> str:
    """Extract the sha value from a `# protocol_sha256=<value>` header line.

    Raises UnfrozenProtocolError if the line is missing/malformed, or the value is not a
    64-lowercase-hex-char sha256 (the template's own placeholder, `PLACEHOLDER-UNFROZEN`, fails
    this check by design — see docs/pilot/scoring-sheet.template.csv).
    """
    line = (first_line or "").strip()
    prefix = "# protocol_sha256="
    if not line.startswith(prefix):
        raise UnfrozenProtocolError(
            f"scoring sheet's first line must be '{prefix}<sha256>'; got: {line!r}"
        )
    value = line[len(prefix):].strip()
    if not _SHA256_RE.match(value):
        raise UnfrozenProtocolError(
            "protocol is not frozen: scoring sheet's protocol_sha256 header is "
            f"{value!r}, not a 64-char lowercase hex sha256. Freeze docs/pilot/E6.7-PROTOCOL.md "
            "first (its §11), then stamp the resulting sha here before analyzing any data."
        )
    return value


def load_scoring_sheet(path: Path) -> tuple[str, list[Row]]:
    """Returns (protocol_sha256, rows). Raises UnfrozenProtocolError / DuplicateRunError."""
    text = Path(path).read_text()
    lines = text.splitlines()
    if not lines:
        raise UnfrozenProtocolError(f"empty scoring sheet: {path}")
    protocol_sha = parse_protocol_sha_header(lines[0])
    # Everything after the header line (further '#'-comment lines are skipped) is real CSV.
    body_lines = [ln for ln in lines[1:] if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(body_lines)))
    required = {"task", "condition", "order", "developer_pseudonym", "outcome", "time_seconds",
                "tokens", "loads", "feedback_verdict", "evaluator", "notes"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"scoring sheet missing columns: {sorted(missing)}")

    rows: list[Row] = []
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[tuple[str, str]] = []
    for raw in reader:
        task = (raw["task"] or "").strip()
        condition = (raw["condition"] or "").strip()
        if not task or not condition:
            continue  # a fully blank trailer row; not data
        key = (task, condition)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1 and key not in duplicates:
            duplicates.append(key)
        rows.append(Row(
            task=task,
            condition=condition,
            order=(raw["order"] or "").strip(),
            developer_pseudonym=(raw["developer_pseudonym"] or "").strip(),
            outcome=(raw["outcome"] or "").strip().lower(),
            time_seconds=_parse_float(raw["time_seconds"]),
            tokens=_parse_float(raw["tokens"]),
            loads=_parse_float(raw["loads"]),
            feedback_verdict=(raw["feedback_verdict"] or "").strip().lower(),
            evaluator=(raw["evaluator"] or "").strip(),
            notes=(raw["notes"] or "").strip(),
        ))
    if duplicates:
        formatted = ", ".join(f"{t}/{c}" for t, c in duplicates)
        raise DuplicateRunError(
            f"duplicate (task, condition) rows — a condition was re-run, which is forbidden "
            f"(docs/pilot/E6.7-PROTOCOL.md §6): {formatted}"
        )
    return protocol_sha, rows


def verify_protocol_file(protocol_sha: str, protocol_file: Path) -> None:
    actual = hashlib.sha256(Path(protocol_file).read_bytes()).hexdigest()
    if actual != protocol_sha:
        raise ProtocolMismatchError(
            f"scoring sheet declares protocol_sha256={protocol_sha}, but {protocol_file} "
            f"actually hashes to {actual}. Results and protocol are not bound; re-check which "
            "protocol revision this pilot ran under before analyzing."
        )


# --------------------------------------------------------------------------- statistics

def wilson_score_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """95% Wilson score interval on a raw proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _binom_tail_ge(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def _solve_increasing(f, target: float, iters: int = 100) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid) > target:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def clopper_pearson_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact 95% (default) Clopper-Pearson interval on a raw proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else _solve_increasing(lambda p: _binom_tail_ge(k, n, p), alpha / 2)
    hi = 1.0 if k == n else _solve_increasing(lambda p: _binom_tail_ge(k + 1, n, p), 1 - alpha / 2)
    return (lo, hi)


def discordant_diff_interval(n_gain: int, n_reg: int, n_evaluable: int,
                              method: str = "wilson") -> tuple[float, float]:
    """Map a Wilson/exact interval on (gains among discordant pairs) back onto the
    gain_rate - regression_rate scale (docs/pilot/E6.7-PROTOCOL.md §5).

    diff = (m/n) * (2p - 1), where m = discordant pairs, n = evaluable pairs, p = gains/m. With
    zero discordant pairs, diff is exactly 0 for this sample (no evidence either way) and the
    interval degenerates to (0.0, 0.0) rather than NaN — it is a real, if uninformative, result.
    """
    m = n_gain + n_reg
    if n_evaluable == 0:
        return (float("nan"), float("nan"))
    if m == 0:
        return (0.0, 0.0)
    if method == "wilson":
        lo, hi = wilson_score_interval(n_gain, m)
    elif method == "exact":
        lo, hi = clopper_pearson_interval(n_gain, m)
    else:
        raise ValueError(f"unknown method: {method!r}")
    scale = m / n_evaluable
    return (scale * (2 * lo - 1), scale * (2 * hi - 1))


def bootstrap_paired_delta(vals_a: list[float], vals_b: list[float], n_resamples: int = 1000,
                            seed: int = 0) -> dict:
    """95% CI (percentile method) on mean(vals_b) - mean(vals_a); paired bootstrap over the
    matched-pair index, so per-pair noise cancels rather than compounds (same method as
    tools/eval/dev_sparse.py's bootstrap_paired_delta / skillretbench.py's
    _bootstrap_paired_delta — reimplemented here, stdlib only, to keep tools/pilot independent
    of tools/eval)."""
    n = len(vals_a)
    assert n == len(vals_b)
    if n == 0:
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "n": 0}
    observed = sum(vals_b) / n - sum(vals_a) / n
    rng = random.Random(seed)
    deltas = []
    idx = range(n)
    for _ in range(n_resamples):
        sample = [rng.choice(idx) for _ in range(n)]
        a = sum(vals_a[i] for i in sample) / n
        b = sum(vals_b[i] for i in sample) / n
        deltas.append(b - a)
    deltas.sort()
    lo = deltas[max(0, int(0.025 * n_resamples) - 1)] if n_resamples else float("nan")
    hi = deltas[min(n_resamples - 1, int(0.975 * n_resamples))] if n_resamples else float("nan")
    return {"delta": observed, "ci_lo": lo, "ci_hi": hi, "n": n, "n_resamples": n_resamples}


# --------------------------------------------------------------------------- assembly

@dataclass
class PairedResult:
    contrast: str
    baseline: str
    challenger: str
    n_evaluable: int
    n_gain: int
    n_regression: int
    n_concordant_success: int
    n_concordant_failure: int
    n_excluded_unknown: int
    gain_rate: float
    regression_rate: float
    diff: float
    wilson_ci: tuple[float, float]
    exact_ci: tuple[float, float]
    time_bootstrap: dict
    tokens_bootstrap: dict


def _by_task_condition(rows: list[Row]) -> dict[tuple[str, str], Row]:
    return {(r.task, r.condition): r for r in rows}


def paired_contrast(rows: list[Row], baseline: str, challenger: str,
                     n_resamples: int = 1000, seed: int = 0) -> PairedResult:
    by_tc = _by_task_condition(rows)
    tasks = sorted({t for (t, c) in by_tc if c in (baseline, challenger)})

    n_gain = n_reg = n_concord_s = n_concord_f = n_excluded = 0
    time_a: list[float] = []
    time_b: list[float] = []
    tok_a: list[float] = []
    tok_b: list[float] = []

    for task in tasks:
        base_row = by_tc.get((task, baseline))
        chal_row = by_tc.get((task, challenger))
        if base_row is None or chal_row is None:
            continue  # this task was never run under both arms of this contrast
        base_out, chal_out = base_row.outcome, chal_row.outcome
        if base_out not in OUTCOME_VALUES or chal_out not in OUTCOME_VALUES:
            n_excluded += 1
            continue
        if base_out == "failure" and chal_out == "success":
            n_gain += 1
        elif base_out == "success" and chal_out == "failure":
            n_reg += 1
        elif base_out == "success" and chal_out == "success":
            n_concord_s += 1
        else:
            n_concord_f += 1

        if base_row.time_seconds is not None and chal_row.time_seconds is not None:
            time_a.append(base_row.time_seconds)
            time_b.append(chal_row.time_seconds)
        if base_row.tokens is not None and chal_row.tokens is not None:
            tok_a.append(base_row.tokens)
            tok_b.append(chal_row.tokens)

    n_evaluable = n_gain + n_reg + n_concord_s + n_concord_f
    gain_rate = n_gain / n_evaluable if n_evaluable else float("nan")
    regression_rate = n_reg / n_evaluable if n_evaluable else float("nan")
    diff = gain_rate - regression_rate if n_evaluable else float("nan")

    return PairedResult(
        contrast=f"{challenger}_vs_{baseline}",
        baseline=baseline,
        challenger=challenger,
        n_evaluable=n_evaluable,
        n_gain=n_gain,
        n_regression=n_reg,
        n_concordant_success=n_concord_s,
        n_concordant_failure=n_concord_f,
        n_excluded_unknown=n_excluded,
        gain_rate=gain_rate,
        regression_rate=regression_rate,
        diff=diff,
        wilson_ci=discordant_diff_interval(n_gain, n_reg, n_evaluable, "wilson"),
        exact_ci=discordant_diff_interval(n_gain, n_reg, n_evaluable, "exact"),
        time_bootstrap=bootstrap_paired_delta(time_a, time_b, n_resamples, seed),
        tokens_bootstrap=bootstrap_paired_delta(tok_a, tok_b, n_resamples, seed),
    )


@dataclass
class Coverage:
    n_rows: int
    n_distinct_tasks: int
    n_by_condition: dict[str, int]
    n_unknown_outcome: int
    n_missing_time: int
    n_missing_tokens: int


def coverage_report(rows: list[Row]) -> Coverage:
    n_by_cond: dict[str, int] = {c: 0 for c in CONDITIONS}
    n_unknown = n_missing_time = n_missing_tokens = 0
    tasks = set()
    for r in rows:
        tasks.add(r.task)
        n_by_cond[r.condition] = n_by_cond.get(r.condition, 0) + 1
        if r.outcome not in OUTCOME_VALUES:
            n_unknown += 1
        if r.time_seconds is None:
            n_missing_time += 1
        if r.tokens is None:
            n_missing_tokens += 1
    return Coverage(
        n_rows=len(rows),
        n_distinct_tasks=len(tasks),
        n_by_condition=n_by_cond,
        n_unknown_outcome=n_unknown,
        n_missing_time=n_missing_time,
        n_missing_tokens=n_missing_tokens,
    )


# --------------------------------------------------------------------------- reporting

def format_report(protocol_sha: str, coverage: Coverage, results: list[PairedResult]) -> str:
    lines = [f"protocol_sha256: {protocol_sha}",
             f"rows: {coverage.n_rows}  distinct tasks: {coverage.n_distinct_tasks}  "
             f"unknown outcomes: {coverage.n_unknown_outcome}",
             "rows per condition: " + ", ".join(
                 f"{c}={coverage.n_by_condition.get(c, 0)}" for c in CONDITIONS),
             ""]
    for r in results:
        lines.append(f"--- {r.contrast} ({r.challenger} vs {r.baseline}) ---")
        lines.append(f"  evaluable pairs: {r.n_evaluable}  "
                      f"(gain={r.n_gain} regression={r.n_regression} "
                      f"concordant_success={r.n_concordant_success} "
                      f"concordant_failure={r.n_concordant_failure} "
                      f"excluded_unknown={r.n_excluded_unknown})")
        lines.append(f"  gain_rate={r.gain_rate:.3f}  regression_rate={r.regression_rate:.3f}  "
                      f"diff={r.diff:.3f}")
        lines.append(f"  diff 95% Wilson CI: [{r.wilson_ci[0]:.3f}, {r.wilson_ci[1]:.3f}]"
                      f"  exact CI: [{r.exact_ci[0]:.3f}, {r.exact_ci[1]:.3f}]")
        tb, kb = r.time_bootstrap, r.tokens_bootstrap
        lines.append(f"  time delta (s): {tb['delta']:.2f} "
                      f"CI [{tb['ci_lo']:.2f}, {tb['ci_hi']:.2f}] (n={tb['n']})")
        lines.append(f"  tokens delta: {kb['delta']:.1f} "
                      f"CI [{kb['ci_lo']:.1f}, {kb['ci_hi']:.1f}] (n={kb['n']})")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path, help="scoring sheet CSV path")
    parser.add_argument("--protocol-file", type=Path, default=None,
                         help="optional: verify the header sha256 against this file's actual bytes")
    parser.add_argument("--contrast", choices=[*CONTRASTS, "all"], default="all")
    parser.add_argument("--bootstrap-resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    try:
        protocol_sha, rows = load_scoring_sheet(args.csv)
        if args.protocol_file is not None:
            verify_protocol_file(protocol_sha, args.protocol_file)
    except (UnfrozenProtocolError, DuplicateRunError, ProtocolMismatchError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    coverage = coverage_report(rows)
    names = list(CONTRASTS) if args.contrast == "all" else [args.contrast]
    results = [paired_contrast(rows, *CONTRASTS[name], args.bootstrap_resamples, args.seed)
               for name in names]
    print(format_report(protocol_sha, coverage, results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
