#!/usr/bin/env python3
"""Evaluate the frozen end-to-end quality gate from replay rows.

The evaluator deliberately treats missing evidence as ``inconclusive`` rather than as a
pass.  It consumes task-level rows produced by a harness and optional E2 delivery rows; it
does not infer semantic usefulness from a retrieval hit.  The expected row shape is JSONL or
JSON list, for example::

    {"task_id":"t1", "arm":"map+gate+evolution", "outcome":"success",
     "useful_delivery":true, "harmful_load":false,
     "stale_conflict_delivery":false}

E2 rows may use ``actual_action``/``expected_action`` and ``harmful``.  A harmful ``LOAD`` is
counted as a harmful delivery; a harmful ``ASK`` is safe.  The output is a report, not an
adoption decision: the report names every unmet condition and preserves unknown coverage.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

ARMS = ("flat", "navigate", "graph", "map", "map+gate", "map+gate+evolution")
CANDIDATE = "map+gate+evolution"
NON_GATED = ("flat", "navigate", "graph", "map")
OUTCOMES = {"success", "failure", "unknown"}


def _rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(value, dict):
        value = value.get("rows") or value.get("events") or []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{path}: expected a JSON list, wrapped rows/events, or JSONL")
    return value


def _bool(row: dict[str, Any], *names: str) -> bool:
    for name in names:
        value = row.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
    return False


def _observed_bool(row: dict[str, Any], *names: str) -> tuple[bool, bool]:
    """Return (value, observed), preserving a missing/null measurement."""
    candidates: list[dict[str, Any]] = [row]
    telemetry = row.get("telemetry")
    if isinstance(telemetry, dict):
        candidates.append(telemetry)
    for candidate in candidates:
        for name in names:
            if name not in candidate or candidate[name] is None:
                continue
            value = candidate[name]
            if isinstance(value, bool):
                return value, True
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value), True
            if isinstance(value, str) and value.lower() in {"true", "false"}:
                return value.lower() == "true", True
    return False, False


def _number(row: dict[str, Any], *names: str) -> int | float | None:
    """Read an optional numeric task metric, including an exported telemetry object."""
    candidates: list[dict[str, Any]] = [row]
    telemetry = row.get("telemetry")
    if isinstance(telemetry, dict):
        candidates.append(telemetry)
    for candidate in candidates:
        for name in names:
            value = candidate.get(name)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str) and value.strip():
                try:
                    return float(value)
                except ValueError:
                    continue
    return None


def _sum_metric(rows: Iterable[dict[str, Any]], *names: str) -> int | float | None:
    values = [_number(row, *names) for row in rows]
    observed = [value for value in values if value is not None]
    return sum(observed) if observed else None


def _harness_error(row: dict[str, Any]) -> bool:
    if _bool(row, "harness_error", "harness_failed"):
        return True
    terminal = str(row.get("terminal_status") or row.get("status") or "").lower()
    return any(word in terminal for word in ("harness", "timeout", "error"))


def _wilson_upper(k: int, n: int, z: float = 1.959963985) -> float | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return min(1.0, (centre + radius) / denom)


def _outcome(row: dict[str, Any]) -> str:
    outcome = str(row.get("outcome") or row.get("task_outcome") or "unknown").lower()
    return outcome if outcome in OUTCOMES else "unknown"


def _success_rate(rows: Iterable[dict[str, Any]]) -> tuple[float | None, int, int]:
    rows = list(rows)
    known = [row for row in rows if _outcome(row) in {"success", "failure"}]
    if not known:
        return None, 0, len(rows)
    return sum(_outcome(row) == "success" for row in known) / len(known), len(known), len(rows) - len(known)


def _arm_rows(rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("arm") or row.get("strategy") or row.get("condition") or "") == arm]


def _duplicate_pairs(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for row in rows:
        task = str(row.get("task_id") or row.get("task") or "")
        arm = str(row.get("arm") or row.get("strategy") or row.get("condition") or "")
        if not task or not arm:
            continue
        pair = (task, arm)
        if pair in seen:
            duplicates.append(pair)
        seen.add(pair)
    return duplicates


def _paired_delta(rows: list[dict[str, Any]], candidate: str, baseline: str) -> float | None:
    by_task: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        task = str(row.get("task_id") or row.get("task") or "")
        arm = str(row.get("arm") or row.get("strategy") or row.get("condition") or "")
        if task and arm in {candidate, baseline}:
            by_task.setdefault(task, {})[arm] = row
    values = []
    for pair in by_task.values():
        if candidate not in pair or baseline not in pair:
            continue
        candidate_outcome, baseline_outcome = _outcome(pair[candidate]), _outcome(pair[baseline])
        if candidate_outcome not in {"success", "failure"} or baseline_outcome not in {"success", "failure"}:
            continue
        values.append((candidate_outcome == "success") - (baseline_outcome == "success"))
    return sum(values) / len(values) if values else None


def _arm_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate optional execution telemetry without treating absent data as zero."""
    elapsed = _sum_metric(rows, "elapsed_ms", "duration_ms", "latency_ms")
    observed_elapsed = sum(
        1 for row in rows if _number(row, "elapsed_ms", "duration_ms", "latency_ms") is not None
    )
    return {
        "harness_errors": sum(_harness_error(row) for row in rows),
        "search_requests": _sum_metric(rows, "search_requests", "search_count"),
        "use_requests": _sum_metric(rows, "use_requests", "skill_load_requests", "use_count"),
        "ask_count": _sum_metric(rows, "ask_count", "asks"),
        "input_tokens": _sum_metric(rows, "input_tokens"),
        "output_tokens": _sum_metric(rows, "output_tokens"),
        "tool_calls": _sum_metric(rows, "tool_calls"),
        "elapsed_ms": elapsed,
        "elapsed_samples": observed_elapsed,
        "avg_elapsed_ms": (elapsed / observed_elapsed if observed_elapsed else None),
    }


def evaluate(task_rows: list[dict[str, Any]], e2_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    arms = {}
    for arm in ARMS:
        subset = _arm_rows(task_rows, arm)
        rate, known, unknown = _success_rate(subset)
        harmful_values = [_observed_bool(row, "harmful_load") for row in subset]
        useful_values = [_observed_bool(row, "useful_delivery", "useful_coverage") for row in subset]
        harmful = sum(value for value, observed in harmful_values if observed)
        useful = sum(value for value, observed in useful_values if observed)
        harmful_observed = sum(observed for _, observed in harmful_values)
        useful_observed = sum(observed for _, observed in useful_values)
        arms[arm] = {"attempts": len(subset), "known_outcomes": known, "unknown": unknown,
                     "unknown_rate": (unknown / len(subset) if subset else None),
                     "task_success_rate": rate, "harmful_loads": harmful,
                     "harmful_load_upper_95": _wilson_upper(harmful, len(subset)),
                     "useful_deliveries": useful,
                     "harmful_observed": harmful_observed,
                     "harmful_unknown": len(subset) - harmful_observed,
                     "useful_observed": useful_observed,
                     "useful_unknown": len(subset) - useful_observed,
                     "useful_coverage": (useful / useful_observed if useful_observed else None),
                     "execution": _arm_metrics(subset)}

    baseline_candidates = [(arm, arms[arm]["task_success_rate"]) for arm in NON_GATED
                           if arms[arm]["task_success_rate"] is not None]
    best_baseline = max(baseline_candidates, key=lambda item: item[1]) if baseline_candidates else None
    candidate = arms[CANDIDATE]
    if best_baseline:
        best_arm, best_rate = best_baseline
        success_noninferior = candidate["task_success_rate"] is not None and candidate["task_success_rate"] >= best_rate - 0.05
        paired_delta = _paired_delta(task_rows, CANDIDATE, best_arm)
        best_useful = arms[best_arm]["useful_coverage"]
        useful_ratio = (candidate["useful_coverage"] / best_useful if best_useful else None)
        useful_coverage_ok = useful_ratio is not None and useful_ratio >= 0.90
    else:
        best_arm = best_rate = paired_delta = useful_ratio = None
        success_noninferior = False
        useful_coverage_ok = False

    e2 = {"attempts": 0, "harmful_loads": 0, "triggered_cases": 0, "stale_conflict_deliveries": 0,
          "correct_asks": 0, "safety_upper_95": None, "evidence_present": False}
    if e2_rows:
        e2["evidence_present"] = True
        e2["attempts"] = len(e2_rows)
        for row in e2_rows:
            harmful = _bool(row, "harmful", "stale", "conflicting", "out_of_scope")
            actual = str(row.get("actual_action") or row.get("action") or "").upper()
            expected = str(row.get("expected_action") or "").upper()
            if harmful:
                e2["triggered_cases"] += 1
                if actual == "LOAD":
                    e2["harmful_loads"] += 1
                    if _bool(row, "stale", "conflicting", "out_of_scope") or expected == "ASK":
                        e2["stale_conflict_deliveries"] += 1
                elif actual == "ASK" and (expected in {"", "ASK"}):
                    e2["correct_asks"] += 1
        e2["safety_upper_95"] = _wilson_upper(e2["harmful_loads"], e2["triggered_cases"])

    checks = {
        "task_success_noninferior": success_noninferior,
        "useful_coverage_at_least_90_percent_of_best_baseline": useful_coverage_ok,
        "harmful_load_upper_bound_at_most_5_percent": e2["evidence_present"] and e2["triggered_cases"] > 0 and e2["safety_upper_95"] <= 0.05,
        "zero_stale_or_conflicting_body_delivery": e2["evidence_present"] and e2["triggered_cases"] > 0 and e2["stale_conflict_deliveries"] == 0,
    }
    missing = []
    duplicates = _duplicate_pairs(task_rows)
    if duplicates:
        missing.append(f"duplicate task/arm rows ({len(duplicates)})")
    if not best_baseline:
        missing.append("known task outcomes for candidate and a non-gated baseline")
    if not e2["evidence_present"] or e2["triggered_cases"] == 0:
        missing.append("E2 conflict/revision trigger cases")
    if candidate["unknown"]:
        missing.append(f"{candidate['unknown']} candidate outcomes are unknown")
    if best_arm and arms[best_arm]["unknown"]:
        missing.append(f"{arms[best_arm]['unknown']} {best_arm} baseline outcomes are unknown")
    if candidate["useful_unknown"]:
        missing.append(f"{candidate['useful_unknown']} candidate useful-delivery measurements are unknown")
    if best_arm and arms[best_arm]["useful_unknown"]:
        missing.append(f"{arms[best_arm]['useful_unknown']} {best_arm} useful-delivery measurements are unknown")
    return {"candidate": CANDIDATE, "best_non_gated_baseline": best_arm,
            "best_baseline_success_rate": best_rate, "paired_success_delta": paired_delta,
            "arms": arms, "e2": e2, "checks": checks,
            "missing_evidence": missing,
            "duplicate_task_arm_rows": duplicates,
            "verdict": "pass" if not missing and all(checks.values()) else ("inconclusive" if missing else "fail")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True, help="task-level JSONL/JSON replay rows")
    parser.add_argument("--e2", type=Path, help="optional E2 delivery decision rows")
    args = parser.parse_args(argv)
    report = evaluate(_rows(args.tasks), _rows(args.e2) if args.e2 else None)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
