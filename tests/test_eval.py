"""E7.5: `guidefold eval` -- the CLI's port of tools/eval/{metrics,run_golden}.py.

Parity is checked at two levels:

  * function-level -- the `_eval_*` functions spliced into the CLI (immediately above
    `cmd_drift`) reproduce tools/eval/metrics.py's numbers to 4 decimal places on identical
    (ranked_urns, case) input, including every individual pure function, not just the aggregate.

  * end-to-end -- `guidefold eval`'s JSON output on the real 220-case tests/golden/*.yaml set
    matches tools/eval/run_golden.py's RETRIEVAL table (hit@1/recall@8/nDCG@10) and INJECTION
    table (completeness@k/all_required@k/distractor_rate@k) at OVERALL.

`cmd_eval` deliberately widens run_golden.py's own narrower overwrite: abstention_precision/
abstention_recall/coverage/n_answered are read from the *injection* evaluation here (run_golden.py
leaves those retrieval-computed, only re-sourcing completeness@4/distractor_rate@4) -- because
`select()`'s abstain_threshold, not an empty `candidates()`, is what actually decides "no answer".
On the current fixture the two sources happen to agree (the router never abstains via either
path), so that wiring is proven with synthetic retrieval/injection results that disagree, not by
relying on fixture behaviour that could stop distinguishing the two sources with no test failure.

Tests must never write into docs/reports/golden/ or mutate tests/golden/ or examples/monorepo/
(the PR #10 lesson) -- every baseline/report path here is a pytest tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
CATEGORY_FILES = (
    "multi_skill.yaml", "sibling_ambiguity.yaml", "no_applicable.yaml",
    "stale_adversarial.yaml", "simple.yaml",
)


def _load_metrics_module():
    spec = importlib.util.spec_from_file_location(
        "gf_metrics_ref", REPO_ROOT / "tools" / "eval" / "metrics.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


METRICS = _load_metrics_module()


def _load_golden_cases():
    cases = []
    for fname in CATEGORY_FILES:
        doc = yaml.safe_load((GOLDEN_DIR / fname).read_text())
        category = doc.get("category")
        for c in doc.get("cases", []):
            c = dict(c)
            c.setdefault("category", category)
            cases.append(c)
    return cases


def _router(gf, root):
    cfg = gf.load_map(root)
    cfg.setdefault("registry", {})
    idx = gf.Index.build(root, cfg)
    return gf.Router(idx)


def _eval_args(**overrides):
    base = dict(queries=str(GOLDEN_DIR), k=4, json=None, baseline=None,
                write_baseline=None, gate=False)
    base.update(overrides)
    return SimpleNamespace(**base)


def _assert_close(ref, got, label):
    if isinstance(ref, float) and math.isnan(ref):
        assert isinstance(got, float) and math.isnan(got), f"{label}: expected nan, got {got!r}"
    elif isinstance(ref, float):
        assert round(ref, 4) == round(got, 4), f"{label}: {ref!r} vs {got!r}"
    else:
        assert ref == got, f"{label}: {ref!r} vs {got!r}"


def _break_adr_process_skill(root):
    """The brief's engineered regression: strip the ADR-specific description/triggers from the
    _root `adr-process` skill, so ADR-related golden queries can no longer route to it."""
    path = root / ".agents" / "skills" / "adr-process" / "SKILL.md"
    text = path.read_text()
    old_description = (
        'description: "[meridian] How Meridian records architecture decisions as ADRs under '
        'docs/adr: numbering, template sections, status lifecycle and who must approve. Use '
        'when a change affects more than one platform, introduces a new datastore, protocol or '
        'external dependency, or when a reviewer asks for an ADR. Do not use for routine '
        'refactors, bug fixes or per-team runbooks."'
    )
    new_description = (
        'description: "[meridian] miscellaneous platform-engineering notes of no specific '
        'applicability to any recurring task."'
    )
    old_triggers = (
        '  triggers: "ADR, architecture decision record, docs/adr, ADR template sections, '
        'propose accept supersede a decision"'
    )
    new_triggers = '  triggers: "miscellaneous notes, general information"'
    assert old_description in text and old_triggers in text, \
        "fixture's adr-process SKILL.md frontmatter text has drifted -- update this test's literals"
    text = text.replace(old_description, new_description).replace(old_triggers, new_triggers)
    path.write_text(text)


# ============================================================== function-level parity
def test_ported_evaluate_matches_metrics_py_on_golden_set(gf, fixture_root):
    router = _router(gf, fixture_root)
    cases = _load_golden_cases()
    retrieval, injection = gf._eval_run_cases(router, cases, k_cards=4)

    ref_overall = METRICS.evaluate(retrieval)
    ported_overall = gf._eval_evaluate(retrieval)
    assert set(ref_overall) == set(ported_overall)
    for key in ref_overall:
        _assert_close(ref_overall[key], ported_overall[key], f"retrieval overall.{key}")

    ref_inj_overall = METRICS.evaluate(injection, k_cards=4)
    ported_inj_overall = gf._eval_evaluate(injection, k_cards=4)
    assert set(ref_inj_overall) == set(ported_inj_overall)
    for key in ref_inj_overall:
        _assert_close(ref_inj_overall[key], ported_inj_overall[key], f"injection overall.{key}")


def test_ported_by_category_matches_metrics_py_on_golden_set(gf, fixture_root):
    router = _router(gf, fixture_root)
    cases = _load_golden_cases()
    retrieval, injection = gf._eval_run_cases(router, cases, k_cards=4)

    ref_per_cat = METRICS.by_category(retrieval)
    ported_per_cat = gf._eval_by_category(retrieval)
    assert set(ref_per_cat) == set(ported_per_cat)
    for cat in ref_per_cat:
        assert set(ref_per_cat[cat]) == set(ported_per_cat[cat])
        for key in ref_per_cat[cat]:
            _assert_close(ref_per_cat[cat][key], ported_per_cat[cat][key], f"{cat}.{key}")

    ref_inj_per_cat = METRICS.by_category(injection, k_cards=4)
    ported_inj_per_cat = gf._eval_by_category(injection, k_cards=4)
    for cat in ref_inj_per_cat:
        for key in ref_inj_per_cat[cat]:
            _assert_close(ref_inj_per_cat[cat][key], ported_inj_per_cat[cat][key],
                          f"injection {cat}.{key}")


_PAIRED_FUNCTIONS = (
    ("_eval_graded", "graded"),
    ("_eval_distractors", "distractors"),
    ("_eval_is_abstention_case", "is_abstention_case"),
)
_RANKED_FUNCTIONS = (
    ("_eval_hit_at_1", "hit_at_1"),
    ("_eval_recall_at_k", "recall_at_k"),
    ("_eval_ndcg_at_k", "ndcg_at_k"),
    ("_eval_completeness_at_k", "completeness_at_k"),
    ("_eval_all_required_at_k", "all_required_at_k"),
    ("_eval_distractor_rate", "distractor_rate"),
)


@pytest.mark.parametrize("ranked,case", [
    (["u1"], {"relevant": [{"urn": "u1", "grade": 3}], "distractors": [{"urn": "u2", "why": "x"}]}),
    ([], {"relevant": []}),
    (["u9", "u1", "u2"],
     {"relevant": [{"urn": "u1", "grade": 2}, {"urn": "u2", "grade": 1}],
      "distractors": [{"urn": "u9", "why": "y"}]}),
    (["u1", "u2", "u3", "u4", "u5"],
     {"relevant": [{"urn": "u3", "grade": 3}, {"urn": "u5", "grade": 2}], "distractors": []}),
])
def test_every_ported_pure_function_matches_its_reference(gf, ranked, case):
    for ported_name, ref_name in _PAIRED_FUNCTIONS:
        ref_val = getattr(METRICS, ref_name)(case)
        got_val = getattr(gf, ported_name)(case)
        _assert_close(ref_val, got_val, ported_name)
    for ported_name, ref_name in _RANKED_FUNCTIONS:
        ref_val = getattr(METRICS, ref_name)(ranked, case)
        got_val = getattr(gf, ported_name)(ranked, case)
        _assert_close(ref_val, got_val, ported_name)


# ============================================================== end-to-end parity vs run_golden.py
def test_cli_eval_json_overall_matches_run_golden_retrieval_and_injection_tables(
        gf, fixture_root, tmp_path):
    out_path = tmp_path / "out.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(json=str(out_path)), fixture_root, cfg)
    assert exc.value.code == 0
    payload = json.loads(out_path.read_text())

    router = _router(gf, fixture_root)
    cases = _load_golden_cases()
    retrieval, injection = gf._eval_run_cases(router, cases, k_cards=4)
    ref_retrieval_overall = METRICS.evaluate(retrieval)            # run_golden's RETRIEVAL table
    ref_injection_overall = METRICS.evaluate(injection, k_cards=4)  # run_golden's INJECTION table

    overall = payload["overall"]
    for key in ("hit@1", "recall@8", "ndcg@10"):
        _assert_close(ref_retrieval_overall[key], overall[key], key)
    for key in ("completeness@4", "all_required@4", "distractor_rate@4"):
        _assert_close(ref_injection_overall[key], overall[key], key)


def test_cli_eval_uses_all_220_golden_cases(gf, fixture_root, tmp_path):
    out_path = tmp_path / "out.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit):
        gf.cmd_eval(_eval_args(json=str(out_path)), fixture_root, cfg)
    payload = json.loads(out_path.read_text())
    assert payload["overall"]["n"] == 220
    assert set(payload["by_category"]) == {
        "multi_skill", "sibling_ambiguity", "no_applicable", "stale_adversarial", "simple"}


def test_cmd_eval_overall_abstention_and_coverage_come_from_injection_not_retrieval(
        gf, fixture_root, tmp_path, monkeypatch):
    """Prove the injection-sourced merge with synthetic data that disagrees between the two
    sources, since the real fixture's router happens not to abstain via either path today."""
    case_answer = {"id": "c-answer", "category": "x", "relevant": [{"urn": "u1", "grade": 3}],
                    "distractors": []}
    case_abstain = {"id": "c-abstain", "category": "x", "relevant": [], "distractors": []}
    retrieval = [(["u1"], case_answer), (["u9"], case_abstain)]   # retrieval never abstains
    injection = [(["u1"], case_answer), ([], case_abstain)]        # injection correctly abstains

    monkeypatch.setattr(gf, "_eval_run_cases",
                         lambda router, cases, k_cards=4: (retrieval, injection))
    monkeypatch.setattr(gf, "_eval_load_queries",
                         lambda path: ([case_answer, case_abstain], "golden"))

    # _eval_query_file_sha256 reads the real path even though _eval_load_queries is stubbed out,
    # so this must be a real (if empty) file, not a placeholder string.
    queries_path = tmp_path / "unused-queries.jsonl"
    queries_path.write_text("")
    out_path = tmp_path / "out.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(queries=str(queries_path), json=str(out_path)), fixture_root, cfg)
    assert exc.value.code == 0

    ret_abstention_recall = gf._eval_evaluate(retrieval)["abstention_recall"]
    inj_abstention_recall = gf._eval_evaluate(injection, k_cards=4)["abstention_recall"]
    assert ret_abstention_recall != inj_abstention_recall, \
        "synthetic data must actually distinguish the two sources, or this proves nothing"

    payload = json.loads(out_path.read_text())
    assert payload["overall"]["abstention_recall"] == inj_abstention_recall
    assert payload["overall"]["abstention_recall"] != ret_abstention_recall


# ============================================================== gate: pass / fail demo
def test_gate_passes_on_unchanged_tree_and_fails_on_engineered_regression(
        gf, fixture_copy, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    cfg = gf.load_map(fixture_copy)
    cfg.setdefault("registry", {})

    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(write_baseline=str(baseline_path)), fixture_copy, cfg)
    assert exc.value.code == 0
    assert baseline_path.exists()

    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(baseline_path), gate=True), fixture_copy, cfg)
    assert exc.value.code == 0, "gate must pass against its own just-written baseline"

    _break_adr_process_skill(fixture_copy)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(baseline_path), gate=True), fixture_copy, cfg)
    assert exc.value.code != 0, "gate must fail once adr-process's routing signal is broken"


def test_gate_margin_is_configurable_via_guidefold_yaml(gf, fixture_copy, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    cfg = gf.load_map(fixture_copy)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit):
        gf.cmd_eval(_eval_args(write_baseline=str(baseline_path)), fixture_copy, cfg)

    _break_adr_process_skill(fixture_copy)

    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(baseline_path), gate=True), fixture_copy, cfg)
    assert exc.value.code != 0, "default 1.0pp margin must not absorb this regression"

    cfg_wide_margin = dict(cfg)
    cfg_wide_margin["eval"] = {"gate": {"hit_at_1_margin": 5.0, "all_required_margin": 5.0,
                                         "distractor_rate_margin": 5.0}}
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(baseline_path), gate=True), fixture_copy, cfg_wide_margin)
    assert exc.value.code == 0, "a 5.0pp margin must absorb this regression"


# ============================================================== baseline / gate edge cases
def test_missing_baseline_file_without_gate_is_informational_only(gf, fixture_root, tmp_path, capsys):
    missing = tmp_path / "no-such-baseline.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(missing)), fixture_root, cfg)
    assert exc.value.code == 0
    assert "no baseline" in capsys.readouterr().out.lower()


def test_missing_baseline_file_with_gate_exits_nonzero(gf, fixture_root, tmp_path):
    missing = tmp_path / "no-such-baseline.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(baseline=str(missing), gate=True), fixture_root, cfg)
    assert exc.value.code != 0


def test_gate_without_baseline_errors(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(gate=True), fixture_root, cfg)
    assert exc.value.code != 0


def test_k_mismatch_against_baseline_errors(gf, fixture_root, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit):
        gf.cmd_eval(_eval_args(k=4, write_baseline=str(baseline_path)), fixture_root, cfg)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(k=8, baseline=str(baseline_path)), fixture_root, cfg)
    assert exc.value.code != 0


# ============================================================== JSON shapes / NaN handling
def test_write_baseline_json_shape_and_no_nan_literal(gf, fixture_root, tmp_path):
    baseline_path = tmp_path / "baseline.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(write_baseline=str(baseline_path)), fixture_root, cfg)
    assert exc.value.code == 0

    raw = baseline_path.read_text()
    assert "NaN" not in raw
    payload = json.loads(raw)
    assert set(payload) == {"cli_version", "git_sha", "index_checksum", "query_file_sha256",
                             "k", "overall", "by_category", "per_case"}
    assert payload["k"] == 4
    assert len(payload["per_case"]) == 220
    for entry in payload["per_case"].values():
        assert "category" in entry
        # every stored metric must be a real number -- NaN-valued metrics are omitted, not null
        for key, value in entry.items():
            if key != "category":
                assert isinstance(value, (int, float)) and not (
                    isinstance(value, float) and math.isnan(value))
    # a case with no distractors must omit distractor_rate@4 rather than store it as NaN/null
    no_distractor_entries = [e for e in payload["per_case"].values() if "distractor_rate@4" not in e]
    assert no_distractor_entries, "expected at least one case with distractor_rate@4 omitted"


def test_eval_json_report_shape_golden_mode(gf, fixture_root, tmp_path):
    out_path = tmp_path / "out.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(json=str(out_path)), fixture_root, cfg)
    assert exc.value.code == 0
    raw = out_path.read_text()
    assert "NaN" not in raw
    payload = json.loads(raw)
    assert payload["mode"] == "golden"
    assert set(payload) == {"mode", "cli_version", "git_sha", "index_checksum",
                             "query_file_sha256", "k", "overall", "by_category"}


# ============================================================== unlabelled (.jsonl) mode
def _write_unlabelled_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_unlabelled_mode_reports_exposure_only(gf, fixture_root, tmp_path, capsys):
    jsonl = tmp_path / "queries.jsonl"
    _write_unlabelled_jsonl(jsonl, [
        {"query": "write an ADR for this cross-platform decision", "node": "_root"},
        {"query": "we're paged right now, help me handle this outage", "node": "_root"},
    ])
    out_path = tmp_path / "out.json"
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(queries=str(jsonl), json=str(out_path)), fixture_root, cfg)
    assert exc.value.code == 0

    out = capsys.readouterr().out
    assert "exposure only" in out
    assert "hit@1" not in out

    payload = json.loads(out_path.read_text())
    assert payload["mode"] == "unlabelled"
    assert "hit@1" not in payload["exposure"]
    assert payload["exposure"]["n"] == 2


@pytest.mark.parametrize("flag,value", [("gate", True), ("baseline", "b.json"),
                                         ("write_baseline", "b.json")])
def test_unlabelled_mode_rejects_gate_and_baseline_flags(gf, fixture_root, tmp_path, flag, value):
    jsonl = tmp_path / "queries.jsonl"
    _write_unlabelled_jsonl(jsonl, [{"query": "q", "node": "_root"}])
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    kwargs = {flag: (value if flag != "gate" else True)}
    if flag != "gate":
        kwargs[flag] = str(tmp_path / value)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_eval(_eval_args(queries=str(jsonl), **kwargs), fixture_root, cfg)
    assert exc.value.code != 0


# ============================================================== query-loading formats
def test_single_yaml_file_loads_only_that_category(gf):
    cases, mode = gf._eval_load_queries(str(GOLDEN_DIR / "simple.yaml"))
    assert mode == "golden"
    assert len(cases) == 22
    assert all(c.get("category", "simple") == "simple" or "category" not in c for c in cases)


def test_directory_loads_every_category_file(gf):
    cases, mode = gf._eval_load_queries(str(GOLDEN_DIR))
    assert mode == "golden"
    assert len(cases) == 220


def test_missing_queries_path_errors(gf, tmp_path):
    with pytest.raises(SystemExit):
        gf._eval_load_queries(str(tmp_path / "does-not-exist.yaml"))


def test_unsupported_queries_extension_errors(gf, tmp_path):
    bad = tmp_path / "queries.txt"
    bad.write_text("nonsense")
    with pytest.raises(SystemExit):
        gf._eval_load_queries(str(bad))


# ============================================================== bootstrap CI / compare_to_baseline
def test_bootstrap_ci_empty_pairs_returns_nan_delta(gf):
    ci = gf._eval_bootstrap_ci([])
    assert ci["n"] == 0
    assert math.isnan(ci["delta"])


def test_bootstrap_ci_identical_pairs_gives_zero_width_ci(gf):
    ci = gf._eval_bootstrap_ci([(0.5, 0.5)] * 20, resamples=200, seed=0)
    assert ci["delta"] == 0.0
    assert ci["ci_lo"] == 0.0
    assert ci["ci_hi"] == 0.0


def test_bootstrap_ci_is_deterministic_with_fixed_seed(gf):
    pairs = [(0.4, 0.6), (0.2, 0.3), (0.9, 0.85), (0.1, 0.5)]
    ci1 = gf._eval_bootstrap_ci(pairs, resamples=500, seed=0)
    ci2 = gf._eval_bootstrap_ci(pairs, resamples=500, seed=0)
    assert ci1 == ci2


def test_compare_to_baseline_flags_hit1_drop_and_distractor_rise(gf):
    overall = {"hit@1": 0.50, "all_required@4": 0.80, "distractor_rate@4": 0.30}
    baseline = {"overall": {"hit@1": 0.60, "all_required@4": 0.80, "distractor_rate@4": 0.10},
                "per_case": {}}
    margins = {"hit_at_1": 0.01, "all_required": 0.01, "distractor_rate": 0.01}
    problems, lines = gf._eval_compare_to_baseline(overall, {}, baseline, 4, margins)
    assert any("hit@1" in p for p in problems)
    assert any("distractor_rate@4" in p for p in problems)
    assert not any("all_required@4" in p for p in problems)


def test_compare_to_baseline_within_margin_is_not_a_problem(gf):
    overall = {"hit@1": 0.595, "all_required@4": 0.80, "distractor_rate@4": 0.105}
    baseline = {"overall": {"hit@1": 0.60, "all_required@4": 0.80, "distractor_rate@4": 0.10},
                "per_case": {}}
    margins = {"hit_at_1": 0.01, "all_required": 0.01, "distractor_rate": 0.01}
    problems, _lines = gf._eval_compare_to_baseline(overall, {}, baseline, 4, margins)
    assert problems == []


def test_compare_to_baseline_skips_undefined_metrics(gf):
    overall = {"hit@1": float("nan"), "all_required@4": 0.8, "distractor_rate@4": 0.1}
    baseline = {"overall": {"hit@1": None, "all_required@4": 0.8, "distractor_rate@4": 0.1},
                "per_case": {}}
    margins = {"hit_at_1": 0.01, "all_required": 0.01, "distractor_rate": 0.01}
    problems, lines = gf._eval_compare_to_baseline(overall, {}, baseline, 4, margins)
    assert problems == []
    assert any("hit@1: undefined" in line for line in lines)


def test_per_case_metrics_omits_undefined_values(gf):
    case = {"id": "c1", "category": "x", "relevant": [{"urn": "u1", "grade": 3}], "distractors": []}
    retrieval = [(["u1"], case)]
    injection = [(["u1"], case)]
    per_case = gf._eval_per_case_metrics(retrieval, injection, 4)
    assert per_case["c1"]["hit@1"] == 1.0
    assert per_case["c1"]["all_required@4"] == 1.0
    assert "distractor_rate@4" not in per_case["c1"]  # no distractors -> NaN -> omitted


# ============================================================== determinism
def test_eval_output_deterministic_under_pythonhashseed(run_cli, fixture_root, tmp_path):
    env1 = {**os.environ, "PYTHONHASHSEED": "1", "GUIDEFOLD_CACHE": str(tmp_path / ".cache1")}
    env2 = {**os.environ, "PYTHONHASHSEED": "42", "GUIDEFOLD_CACHE": str(tmp_path / ".cache2")}
    r1 = run_cli(["eval", "--queries", str(GOLDEN_DIR), "--k", "4"], fixture_root, env=env1)
    r2 = run_cli(["eval", "--queries", str(GOLDEN_DIR), "--k", "4"], fixture_root, env=env2)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert r1.stdout == r2.stdout
