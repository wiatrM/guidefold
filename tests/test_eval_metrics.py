"""Tests for tools/eval/metrics.py — the golden-set metric definitions (E1.2).

These are definition tests: each one pins down a choice that could reasonably have gone the
other way, so that a later change to the numbers has to argue with a named expectation rather
than silently drift.
"""
import importlib.util
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("gf_metrics", ROOT / "tools" / "eval" / "metrics.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gf_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load()

A, B, C, D = "urn:skill:m:n:a", "urn:skill:m:n:b", "urn:skill:m:n:c", "urn:skill:m:n:d"


def case(relevant=(), distract=(), category="simple"):
    return {
        "category": category,
        "relevant": [{"urn": u, "grade": g} for u, g in relevant],
        "distractors": [{"urn": u, "why": "x"} for u in distract],
    }


# ------------------------------------------------------------------ hit@1
def test_hit_at_1_true_for_grade_3_first():
    assert M.hit_at_1([A, B], case([(A, 3)])) == 1.0


def test_hit_at_1_true_for_grade_2_first():
    assert M.hit_at_1([A], case([(A, 2)])) == 1.0


def test_hit_at_1_false_for_grade_1_first():
    """Grade 1 is 'acceptable', not a hit — otherwise a router is rewarded for near-misses."""
    assert M.hit_at_1([A], case([(A, 1), (B, 3)])) == 0.0


def test_hit_at_1_false_when_relevant_is_second():
    assert M.hit_at_1([B, A], case([(A, 3)])) == 0.0


def test_hit_at_1_zero_on_empty_ranking():
    assert M.hit_at_1([], case([(A, 3)])) == 0.0


# ------------------------------------------------------------------ recall@8
def test_recall_counts_only_required_grades():
    """Grade-1 items must not enter the denominator: missing one is not a miss."""
    c = case([(A, 3), (B, 2), (C, 1)])
    assert M.recall_at_k([A, B], c, 8) == 1.0


def test_recall_partial():
    assert M.recall_at_k([A], case([(A, 3), (B, 2)]), 8) == 0.5


def test_recall_respects_the_cutoff():
    ranked = ["x"] * 8 + [A]
    assert M.recall_at_k(ranked, case([(A, 3)]), 8) == 0.0


def test_recall_undefined_for_abstention_case():
    assert math.isnan(M.recall_at_k([], case(), 8))


# ------------------------------------------------------------------ ndcg@10
def test_ndcg_perfect_order_is_one():
    c = case([(A, 3), (B, 2), (C, 1)])
    assert M.ndcg_at_k([A, B, C], c, 10) == pytest.approx(1.0)


def test_ndcg_penalises_inversion():
    c = case([(A, 3), (B, 2)])
    assert M.ndcg_at_k([B, A], c, 10) < M.ndcg_at_k([A, B], c, 10)


def test_ndcg_uses_exponential_gain():
    """2**g - 1, not linear g: a grade-3 skill is worth 7, a grade-1 skill 1.

    With linear gain, [B(g1), A(g3)] would score 1/1 + 3/1.585 = 2.89 against an ideal of
    3/1 + 1/1.585 = 3.63, i.e. 0.796. Exponential gain punishes the inversion much harder,
    which is the behaviour we want when rank 1 is the only slot most prompts really use.
    """
    c = case([(A, 3), (B, 1)])
    got = M.ndcg_at_k([B, A], c, 10)
    assert got == pytest.approx((1 + 7 / math.log2(3)) / (7 + 1 / math.log2(3)), rel=1e-9)
    assert got < 0.8


def test_ndcg_ignores_unlabelled_results():
    c = case([(A, 3)])
    assert M.ndcg_at_k([A, "unlabelled"], c, 10) == pytest.approx(1.0)


# ------------------------------------------------------------------ completeness@k
def test_completeness_requires_every_must_have():
    c = case([(A, 3), (B, 3)])
    assert M.completeness_at_k([A, "x", "y", "z"], c, 4) == 0.0
    assert M.completeness_at_k([A, B, "x", "y"], c, 4) == 1.0


def test_completeness_ignores_grade_2_and_below():
    c = case([(A, 3), (B, 2)])
    assert M.completeness_at_k([A], c, 4) == 1.0


def test_completeness_respects_the_card_cap():
    c = case([(A, 3), (B, 3)])
    assert M.completeness_at_k(["x", "y", "z", A, B], c, 4) == 0.0


# ------------------------------------------------------------------ distractors
def test_distractor_rate_flags_a_plausible_wrong_answer():
    c = case([(A, 3)], distract=[B])
    assert M.distractor_rate([A, B], c, 4) == 1.0
    assert M.distractor_rate([A, C], c, 4) == 0.0


def test_distractor_rate_undefined_without_distractors():
    assert math.isnan(M.distractor_rate([A], case([(A, 3)]), 4))


# ------------------------------------------------------------------ abstention
def test_abstention_true_positive():
    assert M.abstention_counts([], case(category="no_applicable")) == (1, 0, 0, 0)


def test_abstention_false_positive_is_silence_on_a_real_question():
    assert M.abstention_counts([], case([(A, 3)])) == (0, 1, 0, 0)


def test_abstention_false_negative_is_noise():
    assert M.abstention_counts([A], case(category="no_applicable")) == (0, 0, 1, 0)


def test_abstention_true_negative():
    assert M.abstention_counts([A], case([(A, 3)])) == (0, 0, 0, 1)


# ------------------------------------------------------------------ aggregation
def test_evaluate_excludes_abstentions_from_ranking_metrics():
    """The load-bearing convention: silence is not a Hit@1 of zero.

    Two answerable cases, one answered perfectly and one abstained. Hit@1 must be 1.0 over the
    single answered case, and `coverage` must expose the silence instead of hiding it.
    """
    results = [([A], case([(A, 3)])), ([], case([(B, 3)]))]
    m = M.evaluate(results)
    assert m["hit@1"] == 1.0
    assert m["coverage"] == 0.5
    assert m["n_answerable"] == 2 and m["n_answered"] == 1


def test_a_router_that_never_answers_cannot_look_good():
    """Abstain on everything: perfect abstention recall, but precision collapses and coverage is 0."""
    results = [([], case([(A, 3)])) for _ in range(9)] + [([], case(category="no_applicable"))]
    m = M.evaluate(results)
    assert m["abstention_recall"] == 1.0
    assert m["abstention_precision"] == pytest.approx(0.1)
    assert m["coverage"] == 0.0
    assert math.isnan(m["hit@1"])


def test_a_router_that_always_answers_cannot_hide_noise():
    results = [([A], case([(A, 3)]))] + [([C], case(category="no_applicable")) for _ in range(4)]
    m = M.evaluate(results)
    assert m["hit@1"] == 1.0
    assert math.isnan(m["abstention_precision"])   # never abstained -> undefined, not 1.0
    assert m["abstention_recall"] == 0.0


def test_by_category_splits_strata():
    results = [
        ([A], case([(A, 3)], category="simple")),
        ([B], case([(A, 3)], category="sibling_ambiguity")),
    ]
    per = M.by_category(results)
    assert per["simple"]["hit@1"] == 1.0
    assert per["sibling_ambiguity"]["hit@1"] == 0.0


def test_format_table_renders_every_stratum_and_overall():
    results = [([A], case([(A, 3)], category="simple"))]
    txt = M.format_table(M.evaluate(results), M.by_category(results))
    assert "simple" in txt and "OVERALL" in txt and "hit@1" in txt
    assert len(txt.splitlines()) == 4          # header, rule, one stratum, overall


# ------------------------------------------------------------------ all_required@k (peer review P1)
def test_all_required_counts_grade_2_companions():
    """The gap the peer review measured: primary present, required companion missing.
    completeness@4 says 1.0 (primary is there); all_required@4 must say 0.0."""
    c = case([(A, 3), (B, 2)])
    assert M.completeness_at_k([A, C, D], c, 4) == 1.0
    assert M.all_required_at_k([A, C, D], c, 4) == 0.0
    assert M.all_required_at_k([A, B], c, 4) == 1.0


def test_all_required_ignores_grade_1():
    assert M.all_required_at_k([A], case([(A, 3), (B, 1)]), 4) == 1.0


def test_evaluate_reports_both_completeness_series():
    m = M.evaluate([([A], case([(A, 3), (B, 2)]))])
    assert m["completeness@4"] == 1.0 and m["all_required@4"] == 0.0


# ------------------------------------------------------------------ paired_delta_ci (authoring loop)
def test_paired_delta_ci_empty_is_all_nan():
    out = M.paired_delta_ci([])
    assert out["n"] == 0
    for key in ("mean_base", "mean_head", "mean_delta", "ci_lo", "ci_hi"):
        assert math.isnan(out[key])


def test_paired_delta_ci_single_pair_collapses_ci_to_the_point_estimate():
    """n=1 has no defined standard error (denominator n-1 == 0); the CI must collapse to the
    delta itself rather than raise or return NaN -- "one query flipped" is still a fact worth
    reporting even without a confidence interval."""
    out = M.paired_delta_ci([(1.0, 0.0)])
    assert out["n"] == 1
    assert out["mean_base"] == 1.0 and out["mean_head"] == 0.0
    assert out["mean_delta"] == -1.0
    assert out["ci_lo"] == out["ci_hi"] == -1.0


def test_paired_delta_ci_zero_delta_when_base_equals_head():
    out = M.paired_delta_ci([(1.0, 1.0), (0.0, 0.0), (1.0, 1.0)])
    assert out["n"] == 3
    assert out["mean_delta"] == 0.0
    assert out["ci_lo"] == 0.0 and out["ci_hi"] == 0.0


def test_paired_delta_ci_pairing_affects_ci_width_not_the_point_estimate():
    """`mean_delta` is mean(head) - mean(base) regardless of how base/head values are paired up
    (it's linear), so pairing cannot change the point estimate -- but it changes the *within-pair*
    variance, which is exactly what a paired test is for. Same base multiset, same head multiset,
    same mean_delta; a consistent per-pair improvement gives a zero-width CI, an inconsistent one
    (same marginals, per-pair deltas that partly cancel) gives a much wider CI."""
    consistent = M.paired_delta_ci([(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)])     # every pair: +1
    shuffled = M.paired_delta_ci([(0.0, 2.0), (1.0, 3.0), (2.0, 1.0)])       # same base/head sets, re-paired
    assert consistent["mean_base"] == shuffled["mean_base"] == 1.0
    assert consistent["mean_head"] == shuffled["mean_head"] == 2.0
    assert consistent["mean_delta"] == shuffled["mean_delta"] == 1.0
    assert consistent["ci_lo"] == consistent["ci_hi"] == 1.0   # zero variance: every pair agrees
    assert shuffled["ci_hi"] - shuffled["ci_lo"] > 0            # per-pair deltas [2, 2, -1] disagree


def test_paired_delta_ci_narrows_as_n_grows_for_the_same_consistent_signal():
    # a perfectly consistent per-pair delta has zero variance regardless of n (both would collapse
    # to a zero-width CI), so mix in one dissenting case to give a nonzero SEM that can shrink.
    small = M.paired_delta_ci([(0.0, 1.0), (0.0, 0.0)])
    large = M.paired_delta_ci([(0.0, 1.0), (0.0, 0.0)] * 100)
    assert small["mean_delta"] == large["mean_delta"] == pytest.approx(0.5)
    assert (large["ci_hi"] - large["ci_lo"]) < (small["ci_hi"] - small["ci_lo"])


def test_paired_delta_ci_default_z_is_95_percent():
    out = M.paired_delta_ci([(0.0, 1.0), (0.0, 0.0), (1.0, 1.0), (0.0, 0.0)])
    out_explicit = M.paired_delta_ci([(0.0, 1.0), (0.0, 0.0), (1.0, 1.0), (0.0, 0.0)], z=1.96)
    assert out == out_explicit
