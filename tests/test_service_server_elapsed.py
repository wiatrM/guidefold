"""Server timing transport and explicit dual-budget comparison; no model/GPU."""
import copy
from email.message import Message
import io
import json
import math
import sys
from pathlib import Path
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.serve_spike import probe
from tools.serve_spike.compare import compare_runs, main
from test_service_compare import _run


def headers(*values):
    result = Message()
    for value in values:
        result["X-Guidefold-Server-Ms"] = value
    return result


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1", "oops", "", "1, 2"])
def test_server_elapsed_header_rejects_invalid_values(value):
    assert probe.server_elapsed_header(headers(value)) == (None, "invalid_header")


def test_missing_duplicate_and_zero_elapsed_are_distinct():
    assert probe.server_elapsed_header(headers()) == (None, "missing_header")
    assert probe.server_elapsed_header(headers("1", "2")) == (None, "invalid_header")
    assert probe.server_elapsed_header(headers("0")) == (0, "measured")
    assert probe.server_elapsed_header(headers("12.375")) == (12.375, "measured")


@pytest.mark.parametrize("status", [200, 503])
def test_request_json_captures_header_from_success_and_http_error(monkeypatch, status):
    class Response:
        headers = globals()["headers"]("12.375")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b"{}"
    Response.status = status

    class Opener:
        def open(self, request, timeout):
            if status == 503:
                raise urllib.error.HTTPError(request.full_url, status, "fixture",
                    headers("12.375"), io.BytesIO(b'{"error":"not_ready"}'))
            return Response()
    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *args: Opener())
    result = probe.request_json("http://127.0.0.1:8765", "fixture", "/v1/search", {})
    assert result["http_status"] == status
    assert result["server_elapsed_ms"] == 12.375
    assert result["server_elapsed_measurement"] == "measured"
    compact = probe.compact_result(result, "q001")
    assert compact["server_elapsed_ms"] == 12.375
    assert compact["server_elapsed_measurement"] == "measured"


def test_summary_counts_only_successful_finite_measurements_and_keeps_missing_explicit():
    rows = [{"http_status": 200, "client_ms": 10, "server_elapsed_ms": value}
            for value in [1, 3, None, float("nan"), float("inf"), -1, True]]
    rows.append({"http_status": 503, "client_ms": 11, "server_elapsed_ms": 999})
    result = probe.summarize(rows, 300)["server_elapsed_ms"]
    assert result["count"] == 2
    assert result["missing_or_invalid_success_count"] == 5
    assert result["p50"] == 1
    assert result["p95"] == result["p99"] == 3
    empty = probe.summarize([{"http_status": 200, "client_ms": 1}], 300)["server_elapsed_ms"]
    assert empty["count"] == 0
    assert empty["p50"] is empty["p95"] is empty["p99"] is None


def with_server(run, elapsed=300):
    for arm in run["http_arms"] + [run["fresh_process_arm"]]:
        for row in arm["rows"]:
            row["server_elapsed_ms"] = elapsed
    return run


def test_optional_server_gate_and_inclusive_boundaries_preserve_historical_strict_gate():
    reference = with_server(_run(optimized=False, latency=600), 500)
    contender = with_server(_run(optimized=True, latency=400))
    burst = with_server(_run(optimized=True, latency=400, fresh_concurrency=4))
    result = compare_runs(reference, contender, burst=burst, budget_ms=400,
                          server_budget_ms=300, inclusive_budget=True)
    assert result["budget_comparator"] == "less_than_or_equal"
    assert result["gates"]["overall_passed"]
    assert result["gates"]["server_performance_evidence_complete"]
    assert result["gates"]["server_performance_passed"]
    metric = result["burst"]["fresh_c4"]["burst"]
    assert metric["strictly_under_budget_successes"] == 0
    assert metric["within_budget_successes"] == 200
    assert metric["server_elapsed_ms"] == {"p50": 300, "p95": 300, "p99": 300, "count": 200}
    strict = compare_runs(reference, contender, burst=burst, server_budget_ms=300)
    assert strict["budget_comparator"] == "strictly_less_than"
    assert strict["gates"]["server_performance_passed"] is False
    assert strict["gates"]["performance_passed"] is False
    assert not strict["gates"]["overall_passed"]


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1, True])
def test_missing_or_invalid_server_evidence_fails_closed_only_when_requested(value):
    reference = with_server(_run(optimized=False), 80)
    contender = with_server(_run(optimized=True), 50)
    contender["fresh_process_arm"]["rows"][0]["server_elapsed_ms"] = value
    historical = compare_runs(reference, contender)
    assert historical["gates"]["overall_passed"]
    assert historical["gates"]["server_performance_evidence_complete"] is None
    result = compare_runs(reference, contender, server_budget_ms=300, inclusive_budget=True)
    metric = result["comparisons"]["fresh_c1"]["contender"]
    assert metric["server_elapsed_ms"]["count"] == 199
    assert metric["missing_or_invalid_server_elapsed_count"] == 1
    assert not result["gates"]["server_performance_evidence_complete"]
    assert result["gates"]["server_performance_passed"] is None
    assert not result["gates"]["complete"]
    assert not result["gates"]["overall_passed"]


def test_server_gate_requires_reference_completeness_and_burst_success():
    reference = with_server(_run(optimized=False), 80)
    contender = with_server(_run(optimized=True), 50)
    reference["http_arms"][0]["rows"][0].pop("server_elapsed_ms")
    result = compare_runs(reference, contender, server_budget_ms=300)
    assert not result["gates"]["server_performance_evidence_complete"]
    reference = with_server(reference, 80)
    burst = with_server(_run(optimized=True, fresh_concurrency=4), 50)
    burst["fresh_process_arm"]["rows"][0].update(http_status=429, error=None)
    result = compare_runs(reference, contender, burst=burst, server_budget_ms=300)
    assert result["gates"]["server_performance_evidence_complete"]
    assert result["gates"]["server_performance_passed"] is False
    assert result["burst"]["fresh_c4"]["burst"]["server_elapsed_ms"]["count"] == 199
    assert not result["gates"]["overall_passed"]


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "300"])
def test_server_budget_must_be_positive_finite(value):
    with pytest.raises(ValueError, match="server_budget_ms"):
        compare_runs(_run(optimized=False), _run(optimized=True), server_budget_ms=value)


def test_cli_emits_separate_300_and_400_client_gates_with_same_300_server_gate(tmp_path):
    reference = tmp_path / "reference.json"
    contender = tmp_path / "contender.json"
    reference.write_text(json.dumps(with_server(_run(optimized=False, latency=500), 400)))
    contender.write_text(json.dumps(with_server(_run(optimized=True, latency=350), 300)))
    outputs = []
    for budget in (300, 400):
        output = tmp_path / ("client" + str(budget) + ".json")
        assert main(["--reference", str(reference), "--contender", str(contender),
                     "--budget-ms", str(budget), "--server-budget-ms", "300",
                     "--inclusive-budget", "--output", str(output)]) == 0
        outputs.append(json.loads(output.read_text()))
    assert outputs[0]["gates"]["performance_passed"] is False
    assert outputs[1]["gates"]["performance_passed"] is True
    assert all(row["gates"]["server_performance_passed"] for row in outputs)
    assert outputs[0]["gates"]["overall_passed"] is False
    assert outputs[1]["gates"]["overall_passed"] is True
