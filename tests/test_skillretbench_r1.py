"""Tests for tools/eval/skillretbench_r1.py -- the DENSE-PROGRAM.md v2.1 SS6 R1-encoder reference
run of SKILLRET-Embedding-0.6B on SkillRetBench (test-B), through the unmodified product path.

Pure logic (id-filtering, per-setting metric assembly, the new HSR@4 paired-bootstrap CI helper)
is tested here with tiny synthetic data -- no network access, no GPU venv, and no dependency on
execution order. `encode`/`run`'s real-corpus wiring (`_load_corpus`) is exercised only when the
pinned SkillRetBench corpus is verified present on this machine (see `_needs`); a skip there is not
a pass, and the actual R1-encoder numbers must come from a run where this was NOT skipped.

The encoder-backed Router plumbing itself (`DenseCandidateRouter`, `build_dense_index_and_router`,
quantisation, on-disk cache read/write) is tools/eval/dense_ref.py and is already covered by
tests/test_skillret_eval.py (via skillret.py's thin wrappers around the same functions) -- not
duplicated here.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO_ROOT / "tools" / "eval"
sys.path.insert(0, str(EVAL_DIR))

import skillretbench_r1  # tools/eval/skillretbench_r1.py -- itself inserts EVAL_DIR onto sys.path
import corpora as gf_corpora  # tools/eval/corpora.py -- already imported as a side effect above; named here for _needs
import skillretbench  # tools/eval/skillretbench.py -- already imported as a side effect above; used by the corpus test


def _needs(name):
    problems = gf_corpora.verify(name)
    if problems:
        pytest.skip(f"{name} not on this machine or not the pinned revision: {problems[0]}")


def _metrics_module():
    """Fresh, independent load of metrics.py's pure functions -- same pattern
    test_skillretbench.py::_metrics_module uses, so this file never depends on the execution order
    of other test modules or on skillretbench.py's own module-level `_load_metrics` cache."""
    spec = importlib.util.spec_from_file_location("gf_metrics_r1_test", EVAL_DIR / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ torch-free module boundary
def test_skillretbench_r1_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """`run` (and pytest collecting this file) must never require a GPU venv: `encode` is the only
    subcommand that needs torch/transformers/sentence-transformers, and it reaches them only
    inside `cmd_encode` (via a function-scoped `import encode as bakeoff_encode`), never at module
    scope. Poisoning `torch` at both the sys.modules and import-machinery level (same technique as
    skillretbench.py's own torch-boundary test) proves module-level code in skillretbench_r1.py --
    and, transitively, in the sibling modules it imports at module scope (corpora, dense_ref,
    skillretbench) -- never imports it."""
    monkeypatch.setitem(sys.modules, "torch", None)

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at skillretbench_r1.py module scope: {name}")
            return None

    blocker = _TorchIsForbidden()
    sys.meta_path.insert(0, blocker)
    try:
        loader = SourceFileLoader("gf_skillretbench_r1_no_torch_check", str(EVAL_DIR / "skillretbench_r1.py"))
        mod_spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(mod_spec)
        loader.exec_module(module)  # raises if the module body imports torch anywhere
        assert hasattr(module, "cmd_encode")
        assert hasattr(module, "cmd_run")
        assert hasattr(module, "main")
    finally:
        sys.meta_path.remove(blocker)


# ------------------------------------------------------------------ _filter_by_ids
def test_filter_by_ids_keeps_only_matching_case_ids():
    pairs = [(["a"], {"id": "q1"}), (["b"], {"id": "q2"}), (["c"], {"id": "q3"})]
    kept = skillretbench_r1._filter_by_ids(pairs, {"q1", "q3"})
    assert [c["id"] for _, c in kept] == ["q1", "q3"]
    assert skillretbench_r1._filter_by_ids(pairs, set()) == []
    assert skillretbench_r1._filter_by_ids(pairs, {"q1", "q2", "q3"}) == pairs


# ------------------------------------------------------------------ per-setting metric/IR assembly
def _case(cid, setting, relevant, distractors=None):
    return {"id": cid, "setting": setting, "category": setting, "relevant": relevant,
            "distractors": distractors or []}


def test_per_setting_metrics_injects_all_required_and_distractor_rate_from_the_injection_pairing():
    """This is the retrieval-vs-injection contract skillretbench.py's own `cmd_run`/`_quality`
    closure hand-assembles inline (SS4/ADR: hit@1/ndcg@10/recall@8 come from the *retrieval*
    ordering, all_required@4/distractor_rate@4 from the *injection* ordering, K_CARDS=4) --
    `_per_setting_metrics` must reproduce it exactly rather than just running `evaluate` once."""
    metrics_mod = _metrics_module()
    case_a = _case("qA", "single_skill", [{"urn": "a1", "grade": 3}])
    case_b = _case("qB", "distractor", [{"urn": "b1", "grade": 2}], [{"urn": "d1"}])

    # Retrieval put the gold in rank 2 (hurts hit@1); injection (a differently-ordered, K_CARDS-
    # truncated selection) puts it at rank 1 (so all_required@4 should reflect THIS list, not the
    # retrieval list).
    retrieval = [(["x", "a1"], case_a), (["d1", "b1"], case_b)]
    injection = [(["a1", "x"], case_a), (["b1"], case_b)]

    out = skillretbench_r1._per_setting_metrics(metrics_mod, retrieval, injection)
    assert set(out) == {"single_skill", "multi_skill_composition", "distractor",
                         "outdated_redundant", "budget_constrained", "OVERALL"}

    ss = out["single_skill"]
    assert ss["hit@1"] == pytest.approx(0.0)          # from the retrieval ordering (a1 is rank 2)
    assert ss[f"all_required@{skillretbench_r1.K_CARDS}"] == pytest.approx(1.0)  # from injection (a1 is rank 1)

    dd = out["distractor"]
    assert dd[f"distractor_rate@{skillretbench_r1.K_CARDS}"] == pytest.approx(0.0)  # injection dropped d1

    untouched = out["multi_skill_composition"]
    assert untouched["n"] == 0

    overall = out["OVERALL"]
    assert overall["n"] == 2


def test_per_setting_ir_matches_ir_alignment_metrics_per_setting_and_overall():
    metrics_mod = _metrics_module()
    case_a = _case("qA", "single_skill", [{"urn": "a1", "grade": 3}])
    retrieval = [(["a1"], case_a)]

    out = skillretbench_r1._per_setting_ir(metrics_mod, retrieval)
    assert out["single_skill"]["n"] == 1
    assert out["single_skill"]["recall@1"] == pytest.approx(1.0)
    assert out["OVERALL"]["n"] == 1
    assert out["multi_skill_composition"]["n"] == 0


# ------------------------------------------------------------------ hsr_bootstrap_report (new: full CI on HSR@4)
def test_hsr_bootstrap_report_matches_hand_computed_delta_and_ci_and_drops_undetermined_pairs():
    """Mirrors skillretbench.py's own dense_vs_b1_gate_report test fixture, but exercises the
    NEW orchestration this script adds: a full paired-bootstrap 95% CI on distractor_rate@4/HSR@4
    (skillretbench.dense_vs_b1_gate_report computes only a point-estimate delta for this metric --
    see its own docstring/tests). Four distractor-setting cases: two have a real labelled
    distractor (determinate), two have none (NaN/undetermined, must be dropped from the pairing
    entirely -- never scored as 0 'no exposure')."""
    metrics_mod = _metrics_module()

    case_c = _case("qC", "distractor", [{"urn": "c1", "grade": 2}], [{"urn": "d1"}])
    case_d = _case("qD", "distractor", [{"urn": "e1", "grade": 2}], [{"urn": "f1"}])
    case_no_distractor_1 = _case("qN1", "distractor", [{"urn": "g1", "grade": 2}])  # no distractors labelled
    case_no_distractor_2 = _case("qN2", "distractor", [{"urn": "h1", "grade": 2}])

    f0 = {"qC": ["d1", "c1"], "qD": ["e1", "f1"], "qN1": ["g1"], "qN2": ["h1"]}
    r1 = {"qC": ["c1"], "qD": ["e1", "f1"], "qN1": ["g1"], "qN2": ["h1"]}

    cases = [case_c, case_d, case_no_distractor_1, case_no_distractor_2]
    injection_f0 = [(f0[c["id"]], c) for c in cases]
    injection_r1 = [(r1[c["id"]], c) for c in cases]

    report = skillretbench_r1.hsr_bootstrap_report(metrics_mod, injection_f0, injection_r1,
                                                    k_cards=skillretbench_r1.K_CARDS, n_resamples=200)

    assert set(report) == {"single_skill", "multi_skill_composition", "distractor",
                            "outdated_redundant", "budget_constrained", "OVERALL"}

    dd = report["distractor"]
    # Only qC/qD carry a real distractor label; qN1/qN2 must be excluded from the pairing entirely.
    assert dd["n"] == 2
    # F0: distractor named in top 4 for both qC (d1) and qD (f1) -> rate 1.0.
    # R1: qC drops it (rate 0), qD keeps it (rate 1.0) -> mean 0.5. Delta (R1 - F0) = -0.5.
    assert dd["delta"] == pytest.approx(-0.5)
    assert dd["ci_lo"] <= dd["delta"] <= dd["ci_hi"]
    assert dd["n_resamples"] == 200

    # Settings with zero eligible (determinate) pairs must degrade gracefully to the all-NaN shape
    # `_bootstrap_paired_delta` already returns for n==0, never a crash or a silently-wrong 0.0.
    untouched = report["single_skill"]
    assert untouched["n"] == 0
    assert untouched["delta"] != untouched["delta"]  # NaN

    overall = report["OVERALL"]
    assert overall["n"] == 2
    assert overall["delta"] == pytest.approx(-0.5)


def test_hsr_bootstrap_report_is_all_nan_when_every_case_is_undetermined():
    metrics_mod = _metrics_module()
    case_no_distractor = _case("qN", "distractor", [{"urn": "g1", "grade": 2}])
    injection = [(["g1"], case_no_distractor)]
    report = skillretbench_r1.hsr_bootstrap_report(metrics_mod, injection, injection, n_resamples=50)
    assert report["distractor"]["n"] == 0
    assert math.isnan(report["distractor"]["delta"])


def test_format_hsr_bootstrap_table_smoke():
    metrics_mod = _metrics_module()
    case_c = _case("qC", "distractor", [{"urn": "c1", "grade": 2}], [{"urn": "d1"}])
    injection_f0 = [(["d1", "c1"], case_c)]
    injection_r1 = [(["c1"], case_c)]
    report = skillretbench_r1.hsr_bootstrap_report(metrics_mod, injection_f0, injection_r1, n_resamples=50)
    table = skillretbench_r1.format_hsr_bootstrap_table(report)
    assert "distractor" in table
    assert "OVERALL" in table


# ------------------------------------------------------------------ real-corpus wiring (skips gracefully)
def test_load_corpus_produces_cases_with_ids_the_encoder_cache_can_key_on():
    """`_load_corpus()` must return the exact shapes `cmd_encode`/`cmd_run` depend on: cases with
    a stable "id" (used both as the encode cache's query_order key and as `_current_qid`), a
    "query" string to embed, and a "has_hangul" flag (the ALL-vs-Latin-only split). Skips (not
    fails) when the pinned SkillRetBench corpus is not on this machine."""
    _needs("skillretbench")
    data, skills, cards, nodes, cases, corpus_report, query_report = skillretbench_r1._load_corpus()
    assert len(skills) > 0
    assert len(cards) == len(skills)
    assert len(cases) > 0
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))  # unique -- required for the query_vec_of / _current_qid keying
    for c in cases:
        assert isinstance(c["query"], str) and c["query"]
        assert "has_hangul" in c
        assert c["setting"] in skillretbench.SETTING_TO_CATEGORY
    # every card must be reachable by skill_id (cmd_encode's skill_id_to_skill lookup)
    skill_ids = {s["skill_id"] for s in skills}
    assert all(cards[u]["name"] in skill_ids for u in cards)
