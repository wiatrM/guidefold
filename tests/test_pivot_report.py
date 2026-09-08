"""Tests for tools/pilot/pivot_report.py -- the P15 pilot/comparison report tool.

docs/pilot/PIVOT-RUBRIC.md and .agents/skills/pilot-evidence/SKILL.md set the rules this report
must not silently violate: unknown outcomes are a third bucket, never folded into failure; cost
per accepted/published skill is "unavailable" at a zero denominator, never 0; small samples
(<20 judgments) are flagged, not hidden; a report is reproducible (same inputs -> same output,
run_id included); and a --synthetic run is stamped everywhere so it is never mistaken for pilot
evidence. These tests pin each of those down, plus reference values for the reimplemented Wilson
interval (per .agents/skills/eval-evidence-rules/SKILL.md's reference-test rule) and the loaders'
handling of the pinned /usage/export column set (docs/API-CONTRACT.md Sec.5.5).
"""
import csv
import importlib.util
import io
import json
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "gf_pivot_report", ROOT / "tools" / "pilot" / "pivot_report.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gf_pivot_report"] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load()

GENERATED_AT = "2026-09-07T00:00:00Z"


# --------------------------------------------------------------------------- fixture helpers

def usage_row(**overrides):
    base = {
        "skill_id": "urn:skill:acme:atlas:x", "revision": "rev1", "scope": "atlas",
        "owner": "alice", "harness": "claude_code", "window_from": "2026-08-01",
        "window_to": "2026-09-01", "exposures": 1, "loads_verified": 1, "context_loaded": 1,
        "context_unknown": 0, "use_reported": 0, "use_observed": 0, "helped": 0, "hindered": 0,
        "mixed": 0, "not_applicable": 0, "unknown": 0, "feedback_n": 0, "helped_numerator": 0,
        "helped_denominator": 0, "small_sample": "true", "zero_loads": "false",
    }
    base.update(overrides)
    return base


def write_usage_csv(tmp_path, dict_rows, name="usage.csv"):
    p = tmp_path / name
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(R.USAGE_EXPORT_COLUMNS))
        w.writeheader()
        for d in dict_rows:
            w.writerow(d)
    return p


def write_usage_json(tmp_path, dict_rows, queue=None, name="usage.json"):
    payload = {"rows": dict_rows}
    if queue is not None:
        payload["queue"] = queue
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


def score_row(task, condition, outcome="success", time_seconds="100", tokens="100", **kw):
    base = {
        "task": task, "condition": condition, "order": "1", "developer_pseudonym": "dev1",
        "outcome": outcome, "time_seconds": time_seconds, "tokens": tokens, "loads": "1",
        "feedback_verdict": "helped", "evaluator": "auto", "notes": "",
    }
    base.update(kw)
    return base


def write_sheet_csv(tmp_path, dict_rows, name="sheet.csv"):
    p = tmp_path / name
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(R.SCORING_SHEET_COLUMNS))
        w.writeheader()
        for d in dict_rows:
            w.writerow(d)
    return p


def write_cost_json(tmp_path, entries, name="cost.json"):
    p = tmp_path / name
    p.write_text(json.dumps(entries))
    return p


def minimal_usage_csv(tmp_path):
    return write_usage_csv(tmp_path, [usage_row()])


# --------------------------------------------------------------------------- Wilson reference

def test_wilson_score_interval_zero_successes():
    lo, hi = R.wilson_score_interval(0, 10)
    assert lo == 0.0
    assert 0.0 < hi < 0.5


def test_wilson_score_interval_all_successes():
    lo, hi = R.wilson_score_interval(10, 10)
    assert hi == 1.0
    assert 0.5 < lo < 1.0


def test_wilson_score_interval_symmetric_at_half():
    lo, hi = R.wilson_score_interval(5, 10)
    assert lo < 0.5 < hi
    assert abs((0.5 - lo) - (hi - 0.5)) < 1e-9  # symmetric around phat=0.5 by construction


def test_wilson_score_interval_zero_n_is_nan():
    lo, hi = R.wilson_score_interval(0, 0)
    assert math.isnan(lo) and math.isnan(hi)


# --------------------------------------------------------------------------- scoring sheet

def test_load_scoring_sheet_missing_column_raises(tmp_path):
    p = tmp_path / "sheet.csv"
    p.write_text("task,condition,outcome\nt1,a,success\n")
    with pytest.raises(R.ScoringSheetError):
        R.load_scoring_sheet(p)


def test_load_scoring_sheet_duplicate_task_condition_raises(tmp_path):
    p = write_sheet_csv(tmp_path, [
        score_row("t1", "a", outcome="success"),
        score_row("t1", "a", outcome="failure"),
    ])
    with pytest.raises(R.ScoringSheetError):
        R.load_scoring_sheet(p)


def test_load_scoring_sheet_skips_leading_comment_header(tmp_path):
    p = tmp_path / "sheet.csv"
    header = ",".join(R.SCORING_SHEET_COLUMNS)
    p.write_text(f"# protocol_sha256=PLACEHOLDER-UNFROZEN\n{header}\nt1,a,1,dev1,success,10,10,1,helped,auto,\n")
    rows = R.load_scoring_sheet(p)
    assert len(rows) == 1
    assert rows[0].task == "t1" and rows[0].condition == "a"


# --------------------------------------------------------------------------- unknown handling

def test_unknown_outcome_never_counted_as_failure(tmp_path):
    p = write_sheet_csv(tmp_path, [
        score_row("t1", "arm", outcome="success"),
        score_row("t2", "arm", outcome="failure"),
        score_row("t3", "arm", outcome="unknown"),
        score_row("t4", "arm", outcome=""),
    ])
    rows = R.load_scoring_sheet(p)
    [arm] = R.per_arm_success(rows)
    assert arm.n_success == 1
    assert arm.n_failure == 1
    assert arm.n_unknown == 2  # "unknown" and blank both land here, not in n_failure
    assert arm.n_judged == 2
    assert arm.success_rate == pytest.approx(0.5)


# --------------------------------------------------------------------------- small sample

def test_small_sample_marking_below_twenty(tmp_path):
    few = [score_row(f"t{i}", "arm_few", outcome="success") for i in range(5)]
    many = [score_row(f"t{i}", "arm_many", outcome="success") for i in range(25)]
    p = write_sheet_csv(tmp_path, few + many)
    rows = R.load_scoring_sheet(p)
    results = {a.arm: a for a in R.per_arm_success(rows)}
    assert results["arm_few"].n_judged == 5
    assert results["arm_few"].small_sample is True
    assert results["arm_many"].n_judged == 25
    assert results["arm_many"].small_sample is False


def test_small_sample_boundary_is_strictly_less_than_twenty(tmp_path):
    exactly_twenty = [score_row(f"t{i}", "arm", outcome="success") for i in range(20)]
    p = write_sheet_csv(tmp_path, exactly_twenty)
    [arm] = R.per_arm_success(R.load_scoring_sheet(p))
    assert arm.n_judged == 20
    assert arm.small_sample is False  # API-CONTRACT HelpedRatio: small_sample at denominator < 20


# --------------------------------------------------------------------------- both regression directions

def test_both_regression_directions_detected(tmp_path):
    rows_dicts = [
        score_row("t1", "baseline", outcome="failure"),
        score_row("t1", "challenger", outcome="success"),  # gain
        score_row("t2", "baseline", outcome="success"),
        score_row("t2", "challenger", outcome="failure"),  # regression
        score_row("t3", "baseline", outcome="success"),
        score_row("t3", "challenger", outcome="success"),  # concordant success
    ]
    p = write_sheet_csv(tmp_path, rows_dicts)
    rows = R.load_scoring_sheet(p)
    contrast = R.paired_contrast(rows, "baseline", "challenger")
    assert contrast.n_gain == 1
    assert contrast.n_regression == 1
    assert contrast.n_concordant_success == 1
    assert contrast.n_evaluable == 3

    rubric = R.build_rubric_verdicts(
        R.per_arm_success(rows), [contrast], None,
        R.AdapterCoverageReport(measured=False, harnesses=[], gaps=[]),
        R.OwnerDecisionSummary(measured=False, n_queue_items=0, n_with_decision=0),
    )
    regression_row = next(r for r in rubric if r.id == "regression:challenger_vs_baseline")
    assert regression_row.verdict == "regression_both_directions"


# --------------------------------------------------------------------------- cost: zero denominator

def test_zero_acceptance_cost_unavailable(tmp_path):
    imports = [{
        "import_id": "imp1", "calls": 5, "tokens_in": 100, "tokens_out": 50,
        "usd_certain": 1.0, "usd_uncertain": 0.0, "wall_s": 10, "review_minutes": 3,
        "accepted": 0, "published": 2,
    }]
    cost_imports = R.load_cost_json(write_cost_json(tmp_path, imports))
    summary = R.summarize_cost(cost_imports)
    assert summary.cost_per_accepted_certain == "unavailable"
    assert summary.cost_per_accepted_uncertain == "unavailable"
    assert summary.review_minutes_per_accepted == "unavailable"
    # published is non-zero, so cost-per-published stays a real number, not "unavailable"
    assert summary.cost_per_published_certain == pytest.approx(0.5)


def test_zero_published_cost_unavailable_independently(tmp_path):
    imports = [{
        "import_id": "imp1", "calls": 5, "tokens_in": 100, "tokens_out": 50,
        "usd_certain": 2.0, "usd_uncertain": 0.2, "wall_s": 10, "review_minutes": 3,
        "accepted": 4, "published": 0,
    }]
    cost_imports = R.load_cost_json(write_cost_json(tmp_path, imports))
    summary = R.summarize_cost(cost_imports)
    assert summary.cost_per_published_certain == "unavailable"
    assert summary.cost_per_published_uncertain == "unavailable"
    assert summary.cost_per_accepted_certain == pytest.approx(0.5)


def test_cost_rubric_row_verdict_unavailable_at_zero_acceptance(tmp_path):
    imports = [{"import_id": "imp1", "calls": 1, "tokens_in": 1, "tokens_out": 1,
                "usd_certain": 0.0, "usd_uncertain": 0.0, "wall_s": 1, "review_minutes": 1,
                "accepted": 0, "published": 0}]
    cost_imports = R.load_cost_json(write_cost_json(tmp_path, imports))
    summary = R.summarize_cost(cost_imports)
    rubric = R.build_rubric_verdicts(
        [], [], summary,
        R.AdapterCoverageReport(measured=False, harnesses=[], gaps=[]),
        R.OwnerDecisionSummary(measured=False, n_queue_items=0, n_with_decision=0),
    )
    cost_row = next(r for r in rubric if r.id == "cost_per_accepted")
    assert cost_row.verdict == "unavailable"


# --------------------------------------------------------------------------- usage export loaders

def test_load_usage_export_csv_missing_pinned_column_raises(tmp_path):
    p = tmp_path / "usage.csv"
    p.write_text("skill_id,harness\nurn:skill:x,claude_code\n")
    with pytest.raises(R.UsageExportError):
        R.load_usage_export(p)


def test_load_usage_export_csv_roundtrip(tmp_path):
    p = write_usage_csv(tmp_path, [usage_row(loads_verified=3, harness="claude_code")])
    export = R.load_usage_export(p)
    assert export.source_format == "csv"
    assert len(export.rows) == 1
    assert export.rows[0].loads_verified == 3
    assert export.queue_present is False


def test_load_usage_export_json_bare_list(tmp_path):
    p = tmp_path / "usage.json"
    p.write_text(json.dumps([usage_row()]))
    export = R.load_usage_export(p)
    assert export.source_format == "json"
    assert len(export.rows) == 1
    assert export.queue_present is False


def test_load_usage_export_json_with_queue_marks_owner_decisions_measured(tmp_path):
    queue = [
        {"item_id": "q1", "skill_id": "urn:skill:x", "reason": "zero_loads",
         "decision": {"action": "reviewed", "reason": "ok", "at": "2026-09-01T00:00:00Z"}},
        {"item_id": "q2", "skill_id": "urn:skill:y", "reason": "source_changed", "decision": None},
    ]
    p = write_usage_json(tmp_path, [usage_row()], queue=queue)
    export = R.load_usage_export(p)
    assert export.queue_present is True
    summary = R.summarize_owner_decisions(export)
    assert summary.measured is True
    assert summary.n_queue_items == 2
    assert summary.n_with_decision == 1


def test_usage_export_without_queue_is_not_measured_here(tmp_path):
    p = minimal_usage_csv(tmp_path)
    export = R.load_usage_export(p)
    summary = R.summarize_owner_decisions(export)
    assert summary.measured is False
    assert summary.n_queue_items == 0  # absence, not a measured zero


# --------------------------------------------------------------------------- adapter coverage

def test_adapter_capability_coverage_detects_gap(tmp_path):
    rows = [
        usage_row(skill_id="urn:skill:acme:a:one", harness="claude_code", loads_verified=1),
        usage_row(skill_id="urn:skill:acme:a:two", harness="claude_code", loads_verified=1),
        usage_row(skill_id="urn:skill:acme:a:one", harness="copilot", loads_verified=0),
    ]
    p = write_usage_csv(tmp_path, rows)
    export = R.load_usage_export(p)
    coverage = R.adapter_capability_coverage(export.rows)
    assert coverage.measured is True
    assert len(coverage.gaps) == 1
    gap = coverage.gaps[0]
    assert gap["harness_a"] == "claude_code" and gap["harness_b"] == "copilot"
    assert gap["only_in_a"] == ["urn:skill:acme:a:one", "urn:skill:acme:a:two"]
    assert gap["only_in_b"] == []


def test_adapter_capability_coverage_not_measured_without_harness(tmp_path):
    rows = [usage_row(harness="")]
    p = write_usage_csv(tmp_path, rows)
    export = R.load_usage_export(p)
    coverage = R.adapter_capability_coverage(export.rows)
    assert coverage.measured is False


# --------------------------------------------------------------------------- idempotency

def test_build_report_is_idempotent_for_same_inputs(tmp_path):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [
        score_row("t1", "a", outcome="success"),
        score_row("t1", "b", outcome="failure"),
    ])
    cost_p = write_cost_json(tmp_path, [{"import_id": "imp1", "calls": 1, "tokens_in": 1,
                                          "tokens_out": 1, "usd_certain": 1.0,
                                          "usd_uncertain": 0.0, "wall_s": 1, "review_minutes": 1,
                                          "accepted": 1, "published": 1}])

    r1 = R.build_report(usage_p, sheet_p, cost_p, synthetic=False, generated_at=GENERATED_AT)
    r2 = R.build_report(usage_p, sheet_p, cost_p, synthetic=False, generated_at=GENERATED_AT)

    assert r1.run_id == r2.run_id
    assert R.report_to_dict(r1) == R.report_to_dict(r2)
    assert R.render_markdown(r1) == R.render_markdown(r2)


def test_run_id_changes_when_an_input_changes(tmp_path):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [score_row("t1", "a", outcome="success")])
    r1 = R.build_report(usage_p, sheet_p, None, synthetic=False, generated_at=GENERATED_AT)

    sheet_p2 = write_sheet_csv(tmp_path, [score_row("t1", "a", outcome="failure")], name="sheet2.csv")
    r2 = R.build_report(usage_p, sheet_p2, None, synthetic=False, generated_at=GENERATED_AT)
    assert r1.run_id != r2.run_id


# --------------------------------------------------------------------------- synthetic stamp

def test_synthetic_stamp_present_in_json_and_markdown(tmp_path):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [score_row("t1", "a", outcome="success")])

    report = R.build_report(usage_p, sheet_p, None, synthetic=True, generated_at=GENERATED_AT)
    d = R.report_to_dict(report)
    assert d["synthetic"] is True
    assert d["synthetic_note"] == R.SYNTHETIC_NOTE
    for name, section in d["sections"].items():
        assert section["synthetic_note"] == R.SYNTHETIC_NOTE, f"section {name} missing the stamp"

    md = R.render_markdown(report)
    assert md.count(R.SYNTHETIC_NOTE) >= len(d["sections"]) + 1  # header + every section banner


def test_no_synthetic_stamp_when_flag_absent(tmp_path):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [score_row("t1", "a", outcome="success")])
    report = R.build_report(usage_p, sheet_p, None, synthetic=False, generated_at=GENERATED_AT)
    d = R.report_to_dict(report)
    assert "synthetic_note" not in d
    assert R.SYNTHETIC_NOTE not in R.render_markdown(report)


# --------------------------------------------------------------------------- no paths leaked

def test_report_never_embeds_input_file_paths(tmp_path):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [score_row("t1", "a", outcome="success")])
    report = R.build_report(usage_p, sheet_p, None, synthetic=False, generated_at=GENERATED_AT)
    js = json.dumps(R.report_to_dict(report))
    assert str(usage_p) not in js
    assert str(sheet_p) not in js
    md = R.render_markdown(report)
    assert str(usage_p) not in md
    assert str(sheet_p) not in md


# --------------------------------------------------------------------------- CLI smoke test

def test_cli_main_end_to_end(tmp_path, capsys):
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    sheet_p = write_sheet_csv(tmp_path, [
        score_row("t1", "a", outcome="success"),
        score_row("t1", "b", outcome="failure"),
    ])
    rc = R.main([
        "--usage-export", str(usage_p), "--scoring-sheet", str(sheet_p),
        "--generated-at", GENERATED_AT, "--format", "both",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Rubric verdicts" in out
    assert '"run_id"' in out


def test_cli_main_exit_code_two_on_malformed_input(tmp_path, capsys):
    bad_sheet = tmp_path / "sheet.csv"
    bad_sheet.write_text("task,condition\nt1,a\n")
    usage_p = write_usage_csv(tmp_path, [usage_row()])
    rc = R.main(["--usage-export", str(usage_p), "--scoring-sheet", str(bad_sheet)])
    assert rc == 2
