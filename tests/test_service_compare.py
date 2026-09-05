"""Lightweight frozen-result comparisons; no model, server or benchmark."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.serve_spike.compare import compare_runs


def _run(*, optimized, latency=100, fresh_concurrency=1):
    ids = [f"q{i:03d}" for i in range(200)]
    ready = {
        "ready": True, "policy": "frozen-policy", "policy_revision": "a" * 64,
        "snapshot": "frozen-snapshot", "backend": "hybrid_full",
        "model": {"id": "pinned-model", "revision": "b" * 40},
        "optimized": optimized, "torch_threads_effective": 1 if optimized else 8,
        "optimizations": {"exact_cache": optimized},
    }

    def rows():
        return [{"query_id": q, "http_status": 200, "error": None, "client_ms": latency,
                 "ranked_sha256": "1" * 64, "selected_sha256": "2" * 64} for q in ids]

    return {
        "workload": {"sample_size": 200, "sample_query_ids": ids,
                     "sample_text_sha256": "c" * 64, "source_query_file_sha256": "d" * 64,
                     "frozen_dev_split_sha256": "e" * 64},
        "probe_sha256": "f" * 64, "request_profile": "hook", "request_node": "_root",
        "requested_deadline_ms": 1000, "client_timeout_seconds": 5,
        "ready_before_measurement": ready, "ready_after": copy.deepcopy(ready),
        "http_arms": [{"concurrency": c, "rows": rows()} for c in (1, 4)],
        "fresh_process_arm": {"concurrency": fresh_concurrency, "rows": rows()},
    }


def test_strict_400_gate_includes_fresh_and_optional_burst():
    reference = _run(optimized=False, latency=600)
    contender = _run(optimized=True, latency=100)
    burst = _run(optimized=True, latency=150, fresh_concurrency=4)
    burst["requested_deadline_ms"] = 400  # Intentional hard deadline vs primary 1000.
    result = compare_runs(reference, contender, burst=burst)
    assert result["gates"]["overall_passed"]
    assert result["gates"]["complete"]
    assert result["burst_deadline_comparison"]["comparative_speedup_allowed"] is False
    assert result["burst"]["http_c4"]["output_parity"]["paired_reference_over_contender_speedup"]["p95"] is None
    assert result["comparisons"]["http_c1"]["output_parity"]["paired_count"] == 200
    assert result["comparisons"]["http_c4"]["output_parity"]["paired_reference_over_contender_speedup"]["p95"] == 6
    assert result["burst"]["fresh_c4"]["output_parity"]["paired_reference_over_contender_speedup"]["p95"] is None

    # Equal to 400 is not under 400, and burst fresh c4 is a required gate.
    for row in burst["fresh_process_arm"]["rows"]:
        row["client_ms"] = 400
    result = compare_runs(reference, contender, burst=burst)
    assert result["gates"]["complete"]
    assert result["gates"]["performance_passed"] is False
    assert result["gates"]["exact_output_parity_passed"] is True
    assert result["burst"]["fresh_c4"]["burst"]["strictly_under_budget_successes"] == 0

    # The primary fresh-process arm is also required even when every HTTP arm passes.
    for row in contender["fresh_process_arm"]["rows"]:
        row["client_ms"] = 400
    result = compare_runs(reference, contender)
    assert result["gates"]["performance_passed"] is False
    assert result["comparisons"]["fresh_c1"]["contender"]["strict_success_fraction_of_all_attempts"] == 0


def test_failures_missing_rows_and_digests_do_not_shrink_denominators():
    reference, contender = _run(optimized=False), _run(optimized=True)
    reference["http_arms"][0]["rows"][0].update(http_status=504, client_ms=1000, failure_code="deadline_exceeded")
    rows = contender["http_arms"][0]["rows"]
    rows.pop(1)  # q001 has no recorded contender attempt.
    rows[1].update(http_status=429, client_ms=12, failure_code="overloaded")  # q002
    rows[2]["ranked_sha256"] = "9" * 64  # q003 differs.
    rows[3]["selected_sha256"] = None  # q004 is not parity evidence.
    result = compare_runs(reference, contender)
    arm = result["comparisons"]["http_c1"]
    assert arm["contender"]["attempted"] == 199
    assert arm["contender"]["succeeded"] == 198
    assert arm["contender"]["error_counts"] == {"overloaded": 1}
    assert arm["contender"]["strict_success_fraction_of_all_attempts"] == 198 / 199
    assert arm["contender"]["strict_success_fraction_of_expected"] == 198 / 200
    pair = arm["output_parity"]
    assert pair["paired_count"] == 197
    assert pair["digest_compared_count"] == 196
    assert pair["reference_failed_query_ids"] == ["q000"]
    assert pair["contender_failed_query_ids"] == ["q002"]
    assert pair["missing_contender_query_ids"] == ["q001"]
    assert pair["missing_digest_query_ids"] == ["q004"]
    assert pair["mismatch_query_ids"] == ["q003"]
    assert result["gates"]["complete"] is False
    assert result["gates"]["performance_passed"] is None
    assert result["gates"]["exact_output_parity_passed"] is False

    # Duplicates cannot be cherry-picked into a successful paired result.
    rows.append(copy.deepcopy(rows[4]))
    result = compare_runs(reference, contender)
    assert result["comparisons"]["http_c1"]["contender"]["duplicate_query_ids"] == ["q005"]
    assert result["gates"]["complete"] is False


def test_missing_or_different_identity_never_claims_complete():
    reference, contender = _run(optimized=False), _run(optimized=True)
    contender["probe_sha256"] = None
    contender["ready_before_measurement"]["model"]["revision"] = "changed"
    contender["workload"]["sample_text_sha256"] = "8" * 64
    result = compare_runs(reference, contender)
    assert result["identity_checks"]["complete"] is False
    assert "contender:missing_or_invalid:probe_sha256" in result["identity_checks"]["issues"]
    assert "contender:identity_changed_during_run:model" in result["identity_checks"]["issues"]
    assert "contender:identity_mismatch:sample_text_sha256" in result["identity_checks"]["issues"]
    assert result["gates"]["performance_passed"] is None
    assert result["gates"]["exact_output_parity_passed"] is None
    assert result["gates"]["complete"] is False
    assert result["gates"]["overall_passed"] is False