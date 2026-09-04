"""Tests for tools/eval/run_golden.py — the E1.2 golden-set runner that feeds Router.route()
output into tools/eval/metrics.evaluate/by_category and gates CI on a committed baseline.

Pure logic (load_cases, run_cases, check_regression, _json_safe) is tested in isolation with
synthetic data; one subprocess-level test exercises the real CLI end-to-end (`--check` against
the actual committed docs/reports/golden/baseline.json), the same invocation CI makes.
"""
from __future__ import annotations

import importlib.util
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("gf_run_golden", REPO_ROOT / "tools" / "eval" / "run_golden.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gf_run_golden"] = mod
    spec.loader.exec_module(mod)
    return mod


RG = _load()


# ---------------------------------------------------------------- load_cases
def test_load_cases_loads_all_five_categories_with_category_tagged():
    cases = RG.load_cases()
    assert len(cases) == 220  # tests/golden/README.md: total case count
    categories = {c["category"] for c in cases}
    assert categories == {"multi_skill", "sibling_ambiguity", "no_applicable", "stale_adversarial", "simple"}
    for c in cases:
        assert "query" in c and "node" in c


# ---------------------------------------------------------------- run_cases
class _FakeRouter:
    """route() returns deterministic, synthetic urns so run_cases can be tested without
    building a real Index/Router."""

    def route(self, query, node, k=10):
        return [{"urn": f"urn:skill:m:{node}:{i}"} for i in range(min(k, 3))]


def test_run_cases_pairs_ranked_urns_with_their_own_case():
    cases = [
        {"id": "a", "query": "q1", "node": "_root", "category": "simple"},
        {"id": "b", "query": "q2", "node": "teamA", "category": "simple"},
    ]
    results = RG.run_cases(_FakeRouter(), cases, k=2)
    assert len(results) == 2
    (ranked0, case0), (ranked1, case1) = results
    assert case0["id"] == "a" and ranked0 == ["urn:skill:m:_root:0", "urn:skill:m:_root:1"]
    assert case1["id"] == "b" and ranked1 == ["urn:skill:m:teamA:0", "urn:skill:m:teamA:1"]


# ---------------------------------------------------------------- _json_safe
def test_json_safe_converts_nan_to_none_and_leaves_others_untouched():
    out = RG._json_safe({"a": float("nan"), "b": 0.5, "n": 12})
    assert out == {"a": None, "b": 0.5, "n": 12}


# ---------------------------------------------------------------- check_regression
def test_check_regression_flags_a_drop_in_a_higher_is_better_metric():
    overall = {"hit@1": 0.50}
    per_cat = {}
    baseline = {"overall": {"hit@1": 0.60}, "by_category": {}}
    problems = RG.check_regression(overall, per_cat, baseline)
    assert any("hit@1" in p and "OVERALL" in p for p in problems)


def test_check_regression_flags_a_rise_in_distractor_rate():
    overall = {"distractor_rate@4": 0.40}
    baseline = {"overall": {"distractor_rate@4": 0.10}, "by_category": {}}
    problems = RG.check_regression(overall, {}, baseline)
    assert any("distractor_rate@4" in p for p in problems)


def test_check_regression_ignores_changes_within_tolerance():
    overall = {"hit@1": 0.59}   # 0.01 below baseline, tolerance is 0.02
    baseline = {"overall": {"hit@1": 0.60}, "by_category": {}}
    assert RG.check_regression(overall, {}, baseline) == []


def test_check_regression_ignores_improvements():
    overall = {"hit@1": 0.90}
    baseline = {"overall": {"hit@1": 0.60}, "by_category": {}}
    assert RG.check_regression(overall, {}, baseline) == []


def test_check_regression_skips_metrics_undefined_on_either_side():
    overall = {"hit@1": None}
    baseline = {"overall": {"hit@1": 0.60}, "by_category": {}}
    assert RG.check_regression(overall, {}, baseline) == []
    overall2 = {"hit@1": 0.10}
    baseline2 = {"overall": {"hit@1": None}, "by_category": {}}
    assert RG.check_regression(overall2, {}, baseline2) == []


def test_check_regression_checks_every_category_independently():
    per_cat = {"sibling_ambiguity": {"completeness@4": 0.10}}
    baseline = {"overall": {}, "by_category": {"sibling_ambiguity": {"completeness@4": 0.50}}}
    problems = RG.check_regression({}, per_cat, baseline)
    assert any("sibling_ambiguity" in p and "completeness@4" in p for p in problems)


# ---------------------------------------------------------------- write_report
def test_write_report_embeds_weights_and_table(tmp_path, monkeypatch):
    monkeypatch.setattr(RG, "REPORTS_DIR", tmp_path)
    path = RG.write_report("deadbee", "TABLE-CONTENT", {"w_scope": 200})
    assert path == tmp_path / "deadbee.md"
    text = path.read_text()
    assert "TABLE-CONTENT" in text
    assert '"w_scope": 200' in text


# ---------------------------------------------------------------- end-to-end (real fixture)
def test_cli_check_subprocess_matches_committed_baseline():
    """Same invocation the CI job makes, run as a real subprocess against the tracked repo."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "eval" / "run_golden.py"), "--check"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no regression vs baseline" in result.stdout
