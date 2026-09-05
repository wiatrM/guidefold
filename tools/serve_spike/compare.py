#!/usr/bin/env python3
"""Compare frozen loopback probes with strict client latency and output parity.

No models, queries or benchmarks are loaded. This checks identical returned
ranked IDs/scores and selected IDs/revisions, not routing quality or usefulness.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

EXPECTED_COUNT = 200


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _latencies(values):
    return {"p50": _percentile(values, .50), "p95": _percentile(values, .95),
            "p99": _percentile(values, .99), "count": len(values)}


def _success(row):
    return row.get("http_status") == 200 and not row.get("error")


def _model(ready):
    model = ready.get("model")
    if isinstance(model, dict):
        return {"id": model.get("id"), "revision": model.get("revision")}
    return None


def _identity(run, label):
    issues = []
    workload = run.get("workload") or {}
    ready = run.get("ready_before_measurement") or {}
    after = run.get("ready_after") or {}
    identity = {
        "sample_text_sha256": workload.get("sample_text_sha256"),
        "source_query_file_sha256": workload.get("source_query_file_sha256"),
        "frozen_dev_split_sha256": workload.get("frozen_dev_split_sha256"),
        "sample_query_ids": workload.get("sample_query_ids"),
        "sample_size": workload.get("sample_size"),
        "policy": ready.get("policy"), "policy_revision": ready.get("policy_revision"),
        "snapshot": ready.get("snapshot"), "backend": ready.get("backend"),
        "model": _model(ready),
        "request_profile": run.get("request_profile"),
        "request_node": run.get("request_node"),
        "requested_deadline_ms": run.get("requested_deadline_ms"),
        "client_timeout_seconds": run.get("client_timeout_seconds"),
        "probe_sha256": run.get("probe_sha256"),
    }
    for key in ("sample_text_sha256", "source_query_file_sha256",
                "frozen_dev_split_sha256", "policy_revision", "probe_sha256"):
        if not _sha(identity[key]):
            issues.append(label + ":missing_or_invalid:" + key)
    for key in ("policy", "snapshot", "backend", "request_profile", "request_node"):
        if not isinstance(identity[key], str) or not identity[key]:
            issues.append(label + ":missing_or_invalid:" + key)
    ids = identity["sample_query_ids"]
    valid_ids = isinstance(ids, list) and all(isinstance(q, str) and q for q in ids)
    if (not valid_ids or len(ids) != EXPECTED_COUNT or len(set(ids)) != EXPECTED_COUNT
            or identity["sample_size"] != EXPECTED_COUNT):
        issues.append(label + ":expected_200_distinct_workload_ids")
    if not _number(identity["requested_deadline_ms"]) or not identity["requested_deadline_ms"]:
        issues.append(label + ":missing_or_invalid:requested_deadline_ms")
    if not _number(identity["client_timeout_seconds"]) or not identity["client_timeout_seconds"]:
        issues.append(label + ":missing_or_invalid:client_timeout_seconds")
    if identity["backend"] == "sparse_only":
        if ready.get("model") is not None:
            issues.append(label + ":sparse_backend_has_model")
    elif not identity["model"] or not all(isinstance(v, str) and v for v in identity["model"].values()):
        issues.append(label + ":missing_model_identity")
    if ready.get("ready") is not True or after.get("ready") is not True:
        issues.append(label + ":missing_ready_before_or_after")
    for key in ("policy", "policy_revision", "snapshot", "backend"):
        if ready.get(key) != after.get(key):
            issues.append(label + ":identity_changed_during_run:" + key)
    if _model(ready) != _model(after):
        issues.append(label + ":identity_changed_during_run:model")
    if not isinstance(ready.get("optimized"), bool):
        issues.append(label + ":missing_optimization_flag")
    if ready.get("optimized") != after.get("optimized"):
        issues.append(label + ":optimization_changed_during_run")
    code = {
        "policy_code_sha256": ready.get("policy_revision"),
        "probe_code_sha256": run.get("probe_sha256"),
        "optimized": ready.get("optimized"),
        "torch_threads_effective": ready.get("torch_threads_effective"),
        "optimizations": ready.get("optimizations"),
    }
    return identity, code, issues


def _arms(run, label):
    arms, issues = {}, []
    for arm in run.get("http_arms") or []:
        level = arm.get("concurrency")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            issues.append(label + ":invalid_http_concurrency")
            continue
        name = "http_c" + str(level)
        if name in arms:
            issues.append(label + ":duplicate_arm:" + name)
        arms[name] = arm
    fresh = run.get("fresh_process_arm")
    if isinstance(fresh, dict):
        level = fresh.get("concurrency")
        if isinstance(level, int) and not isinstance(level, bool) and level >= 1:
            arms["fresh_c" + str(level)] = fresh
        else:
            issues.append(label + ":missing_fresh_concurrency")
    return arms, issues


def _metrics(arm, expected, budget):
    rows = arm.get("rows") if isinstance(arm, dict) else None
    rows_valid = isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    rows = rows if rows_valid else []
    counts = Counter(row.get("query_id") for row in rows if isinstance(row.get("query_id"), str))
    duplicate = sorted(q for q, count in counts.items() if count > 1)
    unique = {row["query_id"]: row for row in rows
              if isinstance(row.get("query_id"), str) and counts[row["query_id"]] == 1}
    expected_set = set(expected)
    missing = sorted(expected_set - set(counts))
    unexpected = sorted(set(counts) - expected_set)
    unknown_ids = sum(not isinstance(row.get("query_id"), str) for row in rows)
    ok = [row for row in rows if _success(row)]
    success_times = [row["client_ms"] for row in ok if _number(row.get("client_ms"))]
    all_times = [row["client_ms"] for row in rows if _number(row.get("client_ms"))]
    within = sum(row["client_ms"] < budget for row in ok if _number(row.get("client_ms")))
    integrity = (rows_valid and len(rows) == EXPECTED_COUNT and not missing and not unexpected
                 and not duplicate and not unknown_ids and len(all_times) == len(rows))
    errors = Counter(str(row.get("error") or row.get("failure_code") or
                         ("http_" + str(row.get("http_status"))))
                     for row in rows if not _success(row))
    p95 = _percentile(success_times, .95)
    metrics = {
        "present": isinstance(arm, dict), "expected_requests": EXPECTED_COUNT,
        "attempted": len(rows), "succeeded": len(ok), "failed": len(rows) - len(ok),
        "missing_query_ids": missing, "unexpected_query_ids": unexpected,
        "duplicate_query_ids": duplicate, "missing_or_invalid_id_count": unknown_ids,
        "missing_or_invalid_latency_count": len(rows) - len(all_times),
        "http_status_counts": dict(Counter(str(row.get("http_status")) for row in rows)),
        "error_counts": dict(errors),
        "success_latency_ms": _latencies(success_times),
        "all_attempt_latency_ms": _latencies(all_times),
        "strictly_under_budget_successes": within,
        "strict_success_fraction_of_all_attempts": within / len(rows) if rows else None,
        "strict_success_fraction_of_expected": within / EXPECTED_COUNT,
        "budget_failures_including_rejections": len(rows) - within,
        "evidence_complete": integrity,
        "latency_gate_passed": bool(integrity and len(ok) == EXPECTED_COUNT and p95 is not None and p95 < budget),
    }
    return metrics, unique


def _pair(reference_rows, contender_rows, expected, comparable_concurrency=True):
    paired, missing_digest, ranked_mismatch, selected_mismatch = [], [], [], []
    for query_id in expected:
        ref, cont = reference_rows.get(query_id), contender_rows.get(query_id)
        if ref is None or cont is None or not _success(ref) or not _success(cont):
            continue
        paired.append(query_id)
        if not all(_sha(row.get(key)) for row in (ref, cont)
                   for key in ("ranked_sha256", "selected_sha256")):
            missing_digest.append(query_id)
            continue
        if ref["ranked_sha256"] != cont["ranked_sha256"]:
            ranked_mismatch.append(query_id)
        if ref["selected_sha256"] != cont["selected_sha256"]:
            selected_mismatch.append(query_id)
    ref_times = [reference_rows[q]["client_ms"] for q in paired if _number(reference_rows[q].get("client_ms"))
                 and _number(contender_rows[q].get("client_ms"))]
    cont_times = [contender_rows[q]["client_ms"] for q in paired if _number(reference_rows[q].get("client_ms"))
                  and _number(contender_rows[q].get("client_ms"))]
    ref_stats, cont_stats = _latencies(ref_times), _latencies(cont_times)
    speedup = {}
    for p in ("p50", "p95", "p99"):
        speedup[p] = (ref_stats[p] / cont_stats[p] if comparable_concurrency
                      and ref_stats[p] is not None and cont_stats[p] is not None and cont_stats[p] > 0 else None)
    complete = len(paired) == EXPECTED_COUNT and not missing_digest
    mismatches = sorted(set(ranked_mismatch) | set(selected_mismatch))
    return {
        "paired_count": len(paired), "digest_compared_count": len(paired) - len(missing_digest),
        "missing_reference_query_ids": [q for q in expected if q not in reference_rows],
        "missing_contender_query_ids": [q for q in expected if q not in contender_rows],
        "reference_failed_query_ids": [q for q in expected if q in reference_rows and not _success(reference_rows[q])],
        "contender_failed_query_ids": [q for q in expected if q in contender_rows and not _success(contender_rows[q])],
        "missing_digest_query_ids": missing_digest,
        "ranked_mismatch_query_ids": ranked_mismatch,
        "selected_mismatch_query_ids": selected_mismatch, "mismatch_query_ids": mismatches,
        "complete": complete,
        "parity_passed": False if mismatches else (True if complete else None),
        "paired_reference_latency_ms": ref_stats, "paired_contender_latency_ms": cont_stats,
        "paired_reference_over_contender_speedup": speedup,
        "speedup_scope": "same-concurrency/deadline common successful requests" if comparable_concurrency
                         else "not comparable: deadline and/or concurrency differs; only output parity is compared",
    }


def compare_runs(reference, contender, *, burst=None, budget_ms=400):
    if not _number(budget_ms) or budget_ms <= 0:
        raise ValueError("budget_ms must be finite and positive")
    identities, code, issues, runs = {}, {}, [], {"reference": reference, "contender": contender}
    if burst is not None:
        runs["burst"] = burst
    arm_sets = {}
    for label, run in runs.items():
        identities[label], code[label], found = _identity(run, label)
        issues.extend(found)
        arm_sets[label], found = _arms(run, label)
        issues.extend(found)
    ref_identity = identities["reference"]
    expected = ref_identity["sample_query_ids"]
    if not isinstance(expected, list) or not all(isinstance(q, str) for q in expected):
        expected = []
    expected = list(dict.fromkeys(expected))
    for label in ("contender", "burst") if burst is not None else ("contender",):
        for key, value in ref_identity.items():
            # A burst may deliberately enforce a shorter server deadline. Its
            # absolute budget gate remains valid, but its speedup is censored.
            if label == "burst" and key == "requested_deadline_ms":
                continue
            if identities[label].get(key) != value:
                issues.append(label + ":identity_mismatch:" + key)
    expected_flags = code["reference"]["optimized"] is False and code["contender"]["optimized"] is True
    if not expected_flags:
        issues.append("expected_reference_unoptimized_and_contender_optimized")
    if burst is not None and code["burst"]["optimized"] is not True:
        issues.append("burst:expected_optimized")
    identity_complete = not issues
    comparisons, required_metrics, parity_reports = {}, [], []
    for arm_name in ("http_c1", "http_c4", "fresh_c1"):
        ref_metrics, ref_rows = _metrics(arm_sets["reference"].get(arm_name), expected, budget_ms)
        cont_metrics, cont_rows = _metrics(arm_sets["contender"].get(arm_name), expected, budget_ms)
        parity = _pair(ref_rows, cont_rows, expected)
        comparisons[arm_name] = {"reference": ref_metrics, "contender": cont_metrics, "output_parity": parity}
        required_metrics.append(cont_metrics)
        parity_reports.append(parity)
    burst_report = {}
    if burst is not None:
        for burst_name, baseline_name in (("http_c4", "http_c4"), ("fresh_c4", "fresh_c1")):
            base_metrics, base_rows = _metrics(arm_sets["contender"].get(baseline_name), expected, budget_ms)
            burst_metrics, burst_rows = _metrics(arm_sets["burst"].get(burst_name), expected, budget_ms)
            same_conditions = (burst_name == baseline_name and
                               identities["burst"]["requested_deadline_ms"] == identities["contender"]["requested_deadline_ms"])
            parity = _pair(base_rows, burst_rows, expected, same_conditions)
            burst_report[burst_name] = {
                "compared_to_contender_arm": baseline_name, "contender": base_metrics,
                "burst": burst_metrics, "output_parity": parity,
            }
            required_metrics.append(burst_metrics)
            parity_reports.append(parity)
    perf_complete = identity_complete and all(row["evidence_complete"] for row in required_metrics)
    parity_complete = identity_complete and all(row["complete"] for row in parity_reports)
    perf_passed = all(row["latency_gate_passed"] for row in required_metrics) if perf_complete else None
    any_mismatch = any(row["mismatch_query_ids"] for row in parity_reports)
    parity_passed = False if any_mismatch else (True if parity_complete else None)
    complete = perf_complete and parity_complete and all(
        row["reference"]["evidence_complete"] for row in comparisons.values())
    return {
        "schema_version": "e11b-probe-comparison-v1", "budget_ms": budget_ms,
        "budget_comparator": "strictly_less_than", "expected_query_count": EXPECTED_COUNT,
        "identities": identities, "identity_checks": {"complete": identity_complete, "issues": issues},
        "code_and_optimization": {
            "runs": code, "optimization_flag_difference_expected": expected_flags,
            "note": "Pinned policy/probe code identities must match. Optimization flags and thread counts may differ intentionally.",
        },
        "comparisons": comparisons, "burst": burst_report if burst is not None else None,
        "burst_deadline_comparison": {
            "primary_deadline_ms": identities["contender"]["requested_deadline_ms"],
            "burst_deadline_ms": identities["burst"]["requested_deadline_ms"],
            "different_deadline_explicitly_allowed": True,
            "comparative_speedup_allowed": identities["burst"]["requested_deadline_ms"] == identities["contender"]["requested_deadline_ms"],
        } if burst is not None else None,
        "gates": {
            "performance_evidence_complete": perf_complete,
            "performance_passed": perf_passed,
            "output_parity_evidence_complete": parity_complete,
            "exact_output_parity_passed": parity_passed,
            "complete": complete,
            "overall_passed": bool(complete and perf_passed and parity_passed),
            "required_contender_arms": ["http_c1", "http_c4", "fresh_c1"],
            "required_burst_arms": ["http_c4", "fresh_c4"] if burst is not None else [],
        },
        "interpretation": "Output parity checks returned ranked IDs/scores and selected IDs/revisions on the same frozen policy. It is not a retrieval-quality gain, task-utility or production-SLO claim. Latencies are client-observed loopback measurements.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--contender", type=Path, required=True)
    parser.add_argument("--burst", type=Path)
    parser.add_argument("--budget-ms", type=float, default=400)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    reference = json.loads(args.reference.read_text())
    contender = json.loads(args.contender.read_text())
    burst = json.loads(args.burst.read_text()) if args.burst else None
    result = compare_runs(reference, contender, burst=burst, budget_ms=args.budget_ms)
    result["input_files"] = {key: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                             for key, path in (("reference", args.reference), ("contender", args.contender),
                                               ("burst", args.burst)) if path is not None}
    result["comparison_code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())