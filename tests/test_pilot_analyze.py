"""Tests for tools/pilot/analyze.py — the E6.7 pilot's paired-analysis script.

docs/pilot/E6.7-PROTOCOL.md §6 forbids re-running a condition, switching the primary outcome or
analyzing anything against an unfrozen protocol; these tests pin down that analyze.py actually
enforces the parts of that discipline a script can enforce (duplicate detection, the frozen-sha
gate) and that its statistics are arithmetically what the protocol claims they are (discordant-pair
Wilson/exact intervals, paired bootstrap deltas), including the edge cases a real pilot will hit:
every outcome unknown, zero discordant pairs, and a re-run condition.
"""
import importlib.util
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "gf_pilot_analyze", ROOT / "tools" / "pilot" / "analyze.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gf_pilot_analyze"] = mod
    spec.loader.exec_module(mod)
    return mod


A = _load()

FROZEN_SHA = "a" * 64
OTHER_SHA = "b" * 64

HEADER = "task,condition,order,developer_pseudonym,outcome,time_seconds,tokens,loads,feedback_verdict,evaluator,notes"


def _sheet(tmp_path, rows, sha=FROZEN_SHA, name="sheet.csv"):
    text = f"# protocol_sha256={sha}\n{HEADER}\n" + "\n".join(rows) + "\n"
    p = tmp_path / name
    p.write_text(text)
    return p


def row(task, condition, order=1, dev="dev1", outcome="success", t="100", tok="100", loads="1",
        verdict="helped", evaluator="auto", notes=""):
    return f"{task},{condition},{order},{dev},{outcome},{t},{tok},{loads},{verdict},{evaluator},{notes}"


# --------------------------------------------------------------- header / freeze gate

def test_parse_protocol_sha_header_accepts_valid_sha():
    assert A.parse_protocol_sha_header(f"# protocol_sha256={FROZEN_SHA}") == FROZEN_SHA


def test_parse_protocol_sha_header_rejects_template_placeholder():
    with pytest.raises(A.UnfrozenProtocolError):
        A.parse_protocol_sha_header("# protocol_sha256=PLACEHOLDER-UNFROZEN")


def test_parse_protocol_sha_header_rejects_missing_prefix():
    with pytest.raises(A.UnfrozenProtocolError):
        A.parse_protocol_sha_header("not a header at all")


def test_parse_protocol_sha_header_rejects_uppercase_hex():
    # 64 chars but uppercase — not what a real hashlib.hexdigest() ever produces; reject rather
    # than silently case-fold, since a mismatched case here usually means a hand-typed value.
    with pytest.raises(A.UnfrozenProtocolError):
        A.parse_protocol_sha_header("# protocol_sha256=" + "A" * 64)


def test_load_scoring_sheet_unfrozen_raises(tmp_path):
    p = _sheet(tmp_path, [row("t1", "no_skills")], sha="PLACEHOLDER-UNFROZEN")
    with pytest.raises(A.UnfrozenProtocolError):
        A.load_scoring_sheet(p)


def test_load_scoring_sheet_missing_columns_raises(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(f"# protocol_sha256={FROZEN_SHA}\ntask,condition\nt1,no_skills\n")
    with pytest.raises(ValueError):
        A.load_scoring_sheet(p)


def test_verify_protocol_file_matches(tmp_path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen content\n")
    import hashlib
    sha = hashlib.sha256(protocol.read_bytes()).hexdigest()
    A.verify_protocol_file(sha, protocol)  # must not raise


def test_verify_protocol_file_mismatch_raises(tmp_path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen content\n")
    with pytest.raises(A.ProtocolMismatchError):
        A.verify_protocol_file(OTHER_SHA, protocol)


# --------------------------------------------------------------- duplicates (forbidden re-run)

def test_duplicate_task_condition_raises(tmp_path):
    p = _sheet(tmp_path, [
        row("t1", "sparse", order=1, outcome="success"),
        row("t1", "sparse", order=2, outcome="failure", notes="rerun"),
    ])
    with pytest.raises(A.DuplicateRunError) as exc:
        A.load_scoring_sheet(p)
    assert "t1/sparse" in str(exc.value)


def test_no_duplicate_when_conditions_differ(tmp_path):
    p = _sheet(tmp_path, [
        row("t1", "sparse", outcome="success"),
        row("t1", "no_skills", outcome="failure"),
    ])
    _, rows = A.load_scoring_sheet(p)
    assert len(rows) == 2


# --------------------------------------------------------------- all-unknown

def test_all_unknown_outcomes_yields_zero_evaluable(tmp_path):
    p = _sheet(tmp_path, [
        row("t1", "no_skills", outcome="unknown", t="", tok=""),
        row("t1", "sparse", outcome="unknown", t="", tok=""),
        row("t2", "no_skills", outcome="", t="", tok=""),
        row("t2", "sparse", outcome="", t="", tok=""),
    ])
    _, rows = A.load_scoring_sheet(p)
    cov = A.coverage_report(rows)
    assert cov.n_unknown_outcome == 4
    result = A.paired_contrast(rows, A.NO_SKILLS, A.SPARSE)
    assert result.n_evaluable == 0
    assert result.n_excluded_unknown == 2
    assert math.isnan(result.gain_rate)
    assert math.isnan(result.regression_rate)
    assert math.isnan(result.diff)
    lo, hi = result.wilson_ci
    assert math.isnan(lo) and math.isnan(hi)
    lo, hi = result.exact_ci
    assert math.isnan(lo) and math.isnan(hi)
    assert result.time_bootstrap["n"] == 0
    assert math.isnan(result.time_bootstrap["delta"])


# --------------------------------------------------------------- zero discordance

def test_zero_discordance_diff_is_exactly_zero(tmp_path):
    p = _sheet(tmp_path, [
        row("t1", "no_skills", outcome="success", t="100", tok="100"),
        row("t1", "sparse", outcome="success", t="90", tok="95"),
        row("t2", "no_skills", outcome="failure", t="200", tok="200"),
        row("t2", "sparse", outcome="failure", t="190", tok="190"),
    ])
    _, rows = A.load_scoring_sheet(p)
    result = A.paired_contrast(rows, A.NO_SKILLS, A.SPARSE)
    assert result.n_gain == 0 and result.n_regression == 0
    assert result.n_evaluable == 2
    assert result.diff == 0.0
    assert result.wilson_ci == (0.0, 0.0)
    assert result.exact_ci == (0.0, 0.0)
    # time/tokens deltas are still computed even with zero discordance in outcomes
    assert result.time_bootstrap["n"] == 2
    assert result.time_bootstrap["delta"] == pytest.approx(-10.0)


def test_discordant_diff_interval_zero_discordant_pairs_is_degenerate():
    assert A.discordant_diff_interval(0, 0, 10, "wilson") == (0.0, 0.0)
    assert A.discordant_diff_interval(0, 0, 10, "exact") == (0.0, 0.0)


def test_discordant_diff_interval_zero_evaluable_is_nan():
    lo, hi = A.discordant_diff_interval(0, 0, 0, "wilson")
    assert math.isnan(lo) and math.isnan(hi)


# --------------------------------------------------------------- gain/regression counting

def test_paired_contrast_counts_every_bucket(tmp_path):
    p = _sheet(tmp_path, [
        # gain: baseline fails, challenger succeeds
        row("t1", "no_skills", outcome="failure"), row("t1", "sparse", outcome="success"),
        # regression: baseline succeeds, challenger fails
        row("t2", "no_skills", outcome="success"), row("t2", "sparse", outcome="failure"),
        # concordant success
        row("t3", "no_skills", outcome="success"), row("t3", "sparse", outcome="success"),
        # concordant failure
        row("t4", "no_skills", outcome="failure"), row("t4", "sparse", outcome="failure"),
        # excluded: one side unknown
        row("t5", "no_skills", outcome="unknown"), row("t5", "sparse", outcome="success"),
        # only ran under one condition of this contrast — not counted at all
        row("t6", "contender", outcome="success"),
    ])
    _, rows = A.load_scoring_sheet(p)
    result = A.paired_contrast(rows, A.NO_SKILLS, A.SPARSE)
    assert result.n_gain == 1
    assert result.n_regression == 1
    assert result.n_concordant_success == 1
    assert result.n_concordant_failure == 1
    assert result.n_excluded_unknown == 1
    assert result.n_evaluable == 4
    assert result.gain_rate == pytest.approx(0.25)
    assert result.regression_rate == pytest.approx(0.25)
    assert result.diff == pytest.approx(0.0)


# --------------------------------------------------------------- Wilson / exact intervals

def test_wilson_score_interval_extremes():
    lo, hi = A.wilson_score_interval(0, 10)
    assert lo == 0.0
    lo, hi = A.wilson_score_interval(10, 10)
    assert hi == 1.0


def test_wilson_score_interval_n_zero_is_nan():
    lo, hi = A.wilson_score_interval(0, 0)
    assert math.isnan(lo) and math.isnan(hi)


def test_wilson_score_interval_centered_at_half_for_even_split():
    lo, hi = A.wilson_score_interval(5, 10)
    assert lo < 0.5 < hi


def test_clopper_pearson_bounds_extremes():
    lo, hi = A.clopper_pearson_interval(0, 10)
    assert lo == 0.0
    lo, hi = A.clopper_pearson_interval(10, 10)
    assert hi == 1.0


def test_clopper_pearson_more_conservative_than_wilson_at_small_n():
    # 5/5 "successes": exact lower bound is known to sit below 0.5 even though Wilson's does not
    # (worked example in docs/pilot/E6.7-PROTOCOL.md §5) — the reason the protocol requires the
    # exact interval, not just Wilson, before treating small-n pilot data as decisive.
    w_lo, _ = A.wilson_score_interval(5, 5)
    e_lo, _ = A.clopper_pearson_interval(5, 5)
    assert w_lo > 0.5
    assert e_lo < 0.5
    assert e_lo < w_lo


def test_clopper_pearson_interval_contains_wilson_is_not_assumed_but_is_wider_at_n5():
    # Sanity: the exact interval is never narrower than reality allows; check width ordering
    # holds at a second (k, n) point too.
    w_lo, w_hi = A.wilson_score_interval(3, 5)
    e_lo, e_hi = A.clopper_pearson_interval(3, 5)
    assert (e_hi - e_lo) >= (w_hi - w_lo) - 1e-9


# --------------------------------------------------------------- bootstrap paired delta

def test_bootstrap_paired_delta_zero_n():
    out = A.bootstrap_paired_delta([], [], n_resamples=100)
    assert out["n"] == 0
    assert math.isnan(out["delta"])


def test_bootstrap_paired_delta_identical_arrays_has_zero_delta():
    vals = [1.0, 2.0, 3.0, 4.0]
    out = A.bootstrap_paired_delta(vals, vals, n_resamples=200, seed=1)
    assert out["delta"] == 0.0
    assert out["ci_lo"] == pytest.approx(0.0, abs=1e-9)
    assert out["ci_hi"] == pytest.approx(0.0, abs=1e-9)


def test_bootstrap_paired_delta_is_deterministic_given_seed():
    a, b = [1.0, 2.0, 3.0], [2.0, 2.0, 5.0]
    out1 = A.bootstrap_paired_delta(a, b, n_resamples=500, seed=7)
    out2 = A.bootstrap_paired_delta(a, b, n_resamples=500, seed=7)
    assert out1 == out2


def test_bootstrap_paired_delta_observed_matches_plain_mean_difference():
    a, b = [1.0, 2.0, 3.0], [4.0, 4.0, 4.0]
    out = A.bootstrap_paired_delta(a, b, n_resamples=50, seed=0)
    assert out["delta"] == pytest.approx(sum(b) / 3 - sum(a) / 3)


# --------------------------------------------------------------- coverage report

def test_coverage_report_counts_rows_conditions_and_unknowns(tmp_path):
    p = _sheet(tmp_path, [
        row("t1", "no_skills", outcome="success", t="10", tok="10"),
        row("t1", "sparse", outcome="unknown", t="", tok=""),
        row("t2", "contender", outcome="success", t="20", tok="20"),
    ])
    _, rows = A.load_scoring_sheet(p)
    cov = A.coverage_report(rows)
    assert cov.n_rows == 3
    assert cov.n_distinct_tasks == 2
    assert cov.n_by_condition[A.NO_SKILLS] == 1
    assert cov.n_by_condition[A.SPARSE] == 1
    assert cov.n_by_condition[A.CONTENDER] == 1
    assert cov.n_by_condition[A.ORACLE] == 0
    assert cov.n_unknown_outcome == 1
    assert cov.n_missing_time == 1
    assert cov.n_missing_tokens == 1


# --------------------------------------------------------------- CLI end to end

def test_main_exits_2_on_unfrozen_protocol(tmp_path, capsys):
    p = _sheet(tmp_path, [row("t1", "no_skills")], sha="PLACEHOLDER-UNFROZEN")
    rc = A.main(["--csv", str(p)])
    assert rc == 2
    assert "not frozen" in capsys.readouterr().err


def test_main_exits_2_on_duplicate(tmp_path, capsys):
    p = _sheet(tmp_path, [
        row("t1", "sparse", order=1), row("t1", "sparse", order=2),
    ])
    rc = A.main(["--csv", str(p)])
    assert rc == 2
    assert "duplicate" in capsys.readouterr().err.lower()


def test_main_exits_0_and_reports_on_valid_sheet(tmp_path, capsys):
    p = _sheet(tmp_path, [
        row("t1", "no_skills", outcome="failure"), row("t1", "sparse", outcome="success"),
        row("t2", "no_skills", outcome="success"), row("t2", "sparse", outcome="success"),
    ])
    rc = A.main(["--csv", str(p), "--contrast", "sparse_vs_no_skills"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sparse_vs_no_skills" in out
    assert "gain_rate=" in out


def test_main_protocol_file_mismatch_exits_2(tmp_path, capsys):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen content\n")
    p = _sheet(tmp_path, [row("t1", "no_skills")], sha=OTHER_SHA)
    rc = A.main(["--csv", str(p), "--protocol-file", str(protocol)])
    assert rc == 2
    assert "not bound" in capsys.readouterr().err
