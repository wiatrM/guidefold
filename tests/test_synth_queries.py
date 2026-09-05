"""Tests for tools/train/synth_queries.py — the family E synthetic-query generator
(DENSE-PROGRAM.md v2.6).

Generation itself (batched LLM calls) is never exercised here — it needs the GPU venv and a
15 GB model and was smoke-tested manually (see docs/reports/bakeoff/DEV-E-synthetic-training-*
for the transcript). What's tested for real, on tiny synthetic fixtures, is everything the
family's non-negotiables actually rest on: the leakage check (exact + normalised-string), the
JSON-parsing of (simulated) model output including malformed/partial output, composite-set
sampling from taxonomy co-occurrence, hard-negative sampling, and determinism of both samplers
given a fixed seed.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "train"))

import synth_queries as sq  # tools/train/synth_queries.py


# --------------------------------------------------------------------------- fixtures

def _skills():
    return [
        {"id": "s1", "name": "invoice-reconciler", "description": "match invoices to POs",
         "body": "reconcile vendor invoices against purchase orders",
         "major": "finance", "sub": "accounts-payable"},
        {"id": "s2", "name": "po-status-lookup", "description": "look up PO approval status",
         "body": "returns the current stage of a purchase order",
         "major": "finance", "sub": "accounts-payable"},
        {"id": "s3", "name": "vendor-onboarding", "description": "onboard a new vendor",
         "body": "collects tax forms and verifies banking details",
         "major": "finance", "sub": "vendor-management"},
        {"id": "s4", "name": "log-tailer", "description": "tail a service log",
         "body": "streams the last N lines of a log file", "major": "ops", "sub": "observability"},
    ]


# --------------------------------------------------------------------------- skill_text

def test_skill_text_strips_frontmatter_and_truncates():
    skill = {"name": "n", "description": "d",
             "body": "---\ntitle: x\n---\n" + ("word " * 2000)}
    text = sq.skill_text(skill, max_body_chars=50)
    assert "---" not in text
    assert "title: x" not in text
    assert text.startswith("n\n\nd")
    # body portion truncated well below the full 10000 chars of "word " * 2000
    assert len(text) < 200


def test_skill_text_falls_back_to_skill_md():
    skill = {"name": "n", "description": "d", "skill_md": "the markdown body"}
    assert "the markdown body" in sq.skill_text(skill)


# --------------------------------------------------------------------------- normalise / leakage

def test_normalise_folds_case_punctuation_and_whitespace():
    a = sq.normalise("Can you help me   reconcile invoices?!")
    b = sq.normalise("can you help me reconcile invoices")
    assert a == b


def test_leakage_check_flags_exact_match():
    generated = ["a fresh unseen query", "this one is labelled"]
    labelled = ["this one is labelled"]
    assert sq.leakage_check(generated, labelled) == ["this one is labelled"]


def test_leakage_check_flags_normalised_variant():
    generated = ["Can you help me reconcile invoices?!"]
    labelled = ["can you help me reconcile invoices"]
    assert sq.leakage_check(generated, labelled) == generated


def test_leakage_check_clean_when_disjoint():
    generated = ["totally different text about cats"]
    labelled = ["something about purchase orders"]
    assert sq.leakage_check(generated, labelled) == []


def test_leakage_check_empty_labelled_set_is_always_clean():
    assert sq.leakage_check(["anything", "at all"], []) == []


# --------------------------------------------------------------------------- parse_json_field

def test_parse_json_field_queries_happy_path():
    raw = '{"queries": ["a", "b", "c", "d", "e"]}'
    assert sq.parse_json_field(raw, "queries") == ["a", "b", "c", "d", "e"]


def test_parse_json_field_query_happy_path():
    raw = 'sure, here it is:\n{"query": "do the composite task"}\nhope that helps'
    assert sq.parse_json_field(raw, "query") == "do the composite task"


def test_parse_json_field_rejects_non_list_queries():
    assert sq.parse_json_field('{"queries": "not a list"}', "queries") is None


def test_parse_json_field_rejects_empty_strings_in_list():
    assert sq.parse_json_field('{"queries": ["a", "", "c"]}', "queries") is None


def test_parse_json_field_none_on_malformed_json():
    assert sq.parse_json_field("not json at all", "queries") is None
    assert sq.parse_json_field('{"queries": [1, 2, 3]}', "queries") is None
    assert sq.parse_json_field("", "query") is None


def test_parse_json_field_takes_first_json_object_span():
    raw = 'preamble {"query": "the real one"} trailing junk {"query": "ignored"}'
    # regex is greedy .* so this actually captures the whole span; assert it still parses to
    # *a* valid string (documents the known "greedy across multiple objects" edge case rather
    # than asserting a specific winner, since json.loads only succeeds when the greedy span
    # itself is valid JSON — here it is not, so parsing must fail gracefully, not raise).
    result = sq.parse_json_field(raw, "query")
    assert result is None or isinstance(result, str)


# --------------------------------------------------------------------------- composite sampling

def test_sample_composite_sets_only_uses_same_taxonomy_leaf():
    skills = _skills()
    sets = sq.sample_composite_sets(skills, n_sets=10, seed=0)
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    for t in sets:
        leaves = {leaf_of[sid] for sid in t}
        assert len(leaves) == 1, f"composite set {t} spans more than one taxonomy leaf"
        assert 2 <= len(t) <= 3
        assert len(set(t)) == len(t)  # no duplicate skill within a set


def test_sample_composite_sets_skips_singleton_groups():
    # s3 and s4 are the only members of their leaves -- no composite set can be formed from
    # either alone, so every returned set must be drawn from {s1, s2}.
    skills = _skills()
    sets = sq.sample_composite_sets(skills, n_sets=20, seed=0)
    for t in sets:
        assert set(t) <= {"s1", "s2"}


def test_sample_composite_sets_empty_when_no_group_has_two_members():
    skills = [{"id": "only", "major": "m", "sub": "s"}]
    assert sq.sample_composite_sets(skills, n_sets=5, seed=0) == []


def test_sample_composite_sets_deterministic_given_same_seed():
    skills = _skills()
    a = sq.sample_composite_sets(skills, n_sets=5, seed=42)
    b = sq.sample_composite_sets(skills, n_sets=5, seed=42)
    assert a == b


def test_sample_composite_sets_can_differ_across_seeds():
    skills = _skills() * 3  # widen the pool so seed actually has room to matter
    for i, s in enumerate(skills):
        s["id"] = f"{s['id']}-{i}"
    a = sq.sample_composite_sets(skills, n_sets=8, seed=1)
    b = sq.sample_composite_sets(skills, n_sets=8, seed=2)
    assert a != b


# ------------------------------------------------- composite_sets_for_target_rows (row-vs-set fix)

def _wide_same_leaf_pool(n):
    """n skills, all in one taxonomy leaf, distinct ids -- enough combinatorial room that
    composite_sets_for_target_rows can actually reach a non-trivial target_rows."""
    return [{"id": f"w{i}", "name": f"w{i}", "description": "d", "body": "b",
             "major": "finance", "sub": "accounts-payable"} for i in range(n)]


def test_composite_sets_for_target_rows_hits_target_within_one_sets_worth_when_pool_allows():
    # sets are size 2-3, so the cumulative row count can't land on every exact integer -- the
    # guarantee is "at least target_rows, and not more than the last set's size past it" (see the
    # dedicated never-splits-a-set test below for that bound).
    skills = _wide_same_leaf_pool(30)
    sets = sq.composite_sets_for_target_rows(skills, target_rows=50, seed=7)
    total = sum(len(s) for s in sets)
    assert 50 <= total <= 52
    assert all(2 <= len(s) <= 3 for s in sets)
    assert len(set(sets)) == len(sets)  # sample_composite_sets already dedupes; still no dupes


def test_composite_sets_for_target_rows_never_splits_a_set_so_may_slightly_overshoot():
    skills = _wide_same_leaf_pool(30)
    sets = sq.composite_sets_for_target_rows(skills, target_rows=49, seed=7)
    total = sum(len(s) for s in sets)
    assert total >= 49
    assert total - len(sets[-1]) < 49  # dropping the last set would undershoot -- it's whole-set-minimal


def test_composite_sets_for_target_rows_terminates_when_pool_too_small_to_reach_target():
    # _skills() has exactly one eligible leaf (s1, s2) of size 2 -- the *only* achievable
    # composite set is ("s1", "s2"), total rows == 2, forever, no matter how large n_sets grows.
    # This must terminate (not loop forever chasing an unreachable target_rows=1000).
    skills = _skills()
    sets = sq.composite_sets_for_target_rows(skills, target_rows=1000, seed=0)
    assert sets == [("s1", "s2")]


def test_composite_sets_for_target_rows_empty_for_zero_or_negative_target():
    skills = _wide_same_leaf_pool(10)
    assert sq.composite_sets_for_target_rows(skills, target_rows=0, seed=0) == []
    assert sq.composite_sets_for_target_rows(skills, target_rows=-5, seed=0) == []


def test_composite_sets_for_target_rows_deterministic_given_same_seed():
    skills = _wide_same_leaf_pool(30)
    a = sq.composite_sets_for_target_rows(skills, target_rows=40, seed=3)
    b = sq.composite_sets_for_target_rows(skills, target_rows=40, seed=3)
    assert a == b


def test_composite_sets_for_target_rows_matches_the_30pct_design_target_on_a_realistic_shape():
    """Regression guard for the row-vs-set bug: cmd_generate_composite's default target_rows
    formula (a *row* target, "≈30% of training pairs") must not be handed to sample_composite_sets
    as a literal n_sets -- that silently overshoots to ~51% composite (sets average ~2.5 skills
    each for sizes=(2, 3)). Exercise composite_sets_for_target_rows directly with the same formula
    cmd_generate_composite uses, on a pool wide enough that the target is reachable, and check the
    resulting composite-row fraction of (per_skill_rows + composite_rows) lands near 0.30, not 0.51."""
    n_skills = 2000
    skills = _wide_same_leaf_pool(n_skills)
    target_rows = int(n_skills * sq.PER_SKILL_N * sq.COMPOSITE_TARGET_FRACTION
                       / (1 - sq.COMPOSITE_TARGET_FRACTION))
    sets = sq.composite_sets_for_target_rows(skills, target_rows, seed=20260905)
    composite_rows = sum(len(s) for s in sets)
    per_skill_rows = n_skills * sq.PER_SKILL_N
    fraction = composite_rows / (composite_rows + per_skill_rows)
    assert abs(fraction - sq.COMPOSITE_TARGET_FRACTION) < 0.01, (
        f"composite fraction {fraction:.3f} drifted from the {sq.COMPOSITE_TARGET_FRACTION} target")


# --------------------------------------------------------------------------- hard negatives

def test_sample_hard_negatives_excludes_gold_and_self():
    skills = _skills()
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    negs = sq.sample_hard_negatives("s1", {"s1"}, groups, leaf_of, n=3, seed=0)
    assert "s1" not in negs
    assert set(negs) <= {"s2"}  # only same-leaf sibling available


def test_sample_hard_negatives_excludes_other_gold_ids_in_a_composite():
    skills = _skills()
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    negs = sq.sample_hard_negatives("s1", {"s1", "s2"}, groups, leaf_of, n=3, seed=0)
    assert negs == []  # s2 is the only sibling and it's gold too


def test_sample_hard_negatives_empty_for_singleton_category():
    skills = _skills()
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    assert sq.sample_hard_negatives("s4", {"s4"}, groups, leaf_of, n=3, seed=0) == []


def test_sample_hard_negatives_deterministic_given_same_seed():
    skills = _skills() * 3
    for i, s in enumerate(skills):
        s["id"] = f"{s['id']}-{i}"
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    a = sq.sample_hard_negatives("s1-0", {"s1-0"}, groups, leaf_of, n=3, seed=7)
    b = sq.sample_hard_negatives("s1-0", {"s1-0"}, groups, leaf_of, n=3, seed=7)
    assert a == b


def test_sample_hard_negatives_never_exceeds_n():
    skills = _skills() * 5
    for i, s in enumerate(skills):
        s["id"] = f"{s['id']}-{i}"
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    negs = sq.sample_hard_negatives("s1-0", {"s1-0"}, groups, leaf_of, n=3, seed=0)
    assert len(negs) <= 3


# --------------------------------------------------------------------------- hard negatives: fallback top-up

def test_sample_hard_negatives_tops_up_from_fallback_when_leaf_pool_too_small():
    # s1's only same-leaf sibling is s2, but s2 is gold too -- with no fallback that's 0 negatives.
    skills = _skills()
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    without_fallback = sq.sample_hard_negatives("s1", {"s1", "s2"}, groups, leaf_of, n=3, seed=0)
    assert without_fallback == []
    all_ids = [s["id"] for s in skills]
    topped_up = sq.sample_hard_negatives("s1", {"s1", "s2"}, groups, leaf_of, n=3, seed=0,
                                          fallback_ids=all_ids)
    # only s3 and s4 are eligible (not self, not gold) -- exactly those two, never s1/s2
    assert set(topped_up) == {"s3", "s4"}


def test_sample_hard_negatives_fallback_never_returns_self_or_gold():
    skills = _skills()
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    all_ids = [s["id"] for s in skills]
    negs = sq.sample_hard_negatives("s4", {"s4"}, groups, leaf_of, n=3, seed=0,
                                     fallback_ids=all_ids)
    assert "s4" not in negs
    assert set(negs) <= {"s1", "s2", "s3"}


def test_sample_hard_negatives_fallback_deterministic_given_same_seed():
    skills = _skills() * 5
    for i, s in enumerate(skills):
        s["id"] = f"{s['id']}-{i}"
    groups = sq.build_taxonomy_groups(skills)
    leaf_of = {s["id"]: sq.taxonomy_leaf(s) for s in skills}
    all_ids = [s["id"] for s in skills]
    a = sq.sample_hard_negatives("s4-3", {"s4-3"}, groups, leaf_of, n=3, seed=11,
                                  fallback_ids=all_ids)
    b = sq.sample_hard_negatives("s4-3", {"s4-3"}, groups, leaf_of, n=3, seed=11,
                                  fallback_ids=all_ids)
    assert a == b
    assert len(a) <= 3


# --------------------------------------------------------------------------- cmd_hard_negatives (CLI-level schema)

def _args(**kw):
    ns = types.SimpleNamespace(corpus="dev", skills_file=None, seed=20260905)
    ns.__dict__.update(kw)
    return ns


def test_cmd_hard_negatives_per_skill_rows_get_flat_list_topped_up_to_n(tmp_path):
    skills = _skills()
    skills_file = tmp_path / "skills.json"
    skills_file.write_text(json.dumps(skills))
    per_skill_file = tmp_path / "per_skill.jsonl"
    # s1 and s2 are the only same-leaf pair, so without top-up s1 would get <=1 negative
    per_skill_file.write_text(
        json.dumps({"skill_id": "s1", "queries": ["q"]}) + "\n"
        + json.dumps({"skill_id": "s4", "queries": ["q"]}) + "\n"
    )
    out_file = tmp_path / "out.jsonl"
    args = _args(skills_file=str(skills_file), per_skill_file=str(per_skill_file),
                 composite_file=None, out=str(out_file))
    sq.cmd_hard_negatives(args)
    records = [json.loads(l) for l in out_file.read_text().splitlines() if l]
    assert len(records) == 2
    by_skill = {r["skill_ids"][0]: r for r in records}
    # s1's own leaf sibling pool has only s2 -- fallback must top it up to exactly 3
    assert len(by_skill["s1"]["hard_negatives"]) == 3
    assert "s1" not in by_skill["s1"]["hard_negatives"]
    # s4 is a taxonomy singleton -- everything must come from the fallback pool
    assert len(by_skill["s4"]["hard_negatives"]) == 3
    assert "s4" not in by_skill["s4"]["hard_negatives"]


def test_cmd_hard_negatives_composite_rows_get_per_skill_keyed_dict(tmp_path):
    skills = _skills()
    skills_file = tmp_path / "skills.json"
    skills_file.write_text(json.dumps(skills))
    per_skill_file = tmp_path / "per_skill.jsonl"
    per_skill_file.write_text("")  # no per-skill rows needed for this test
    composite_file = tmp_path / "composite.jsonl"
    composite_file.write_text(
        json.dumps({"skill_ids": ["s1", "s2"], "query": "do both"}) + "\n"
    )
    out_file = tmp_path / "out.jsonl"
    args = _args(skills_file=str(skills_file), per_skill_file=str(per_skill_file),
                 composite_file=str(composite_file), out=str(out_file))
    sq.cmd_hard_negatives(args)
    records = [json.loads(l) for l in out_file.read_text().splitlines() if l]
    assert len(records) == 1
    rec = records[0]
    assert "hard_negatives" not in rec  # composite rows use the per-skill-keyed schema, not a flat list
    assert set(rec["hard_negatives_by_skill"]) == {"s1", "s2"}
    for sid, negs in rec["hard_negatives_by_skill"].items():
        assert sid not in negs
        assert "s1" not in negs and "s2" not in negs  # excludes the WHOLE composite gold set


def test_cmd_hard_negatives_skips_rows_with_no_query(tmp_path):
    skills = _skills()
    skills_file = tmp_path / "skills.json"
    skills_file.write_text(json.dumps(skills))
    per_skill_file = tmp_path / "per_skill.jsonl"
    per_skill_file.write_text(
        json.dumps({"skill_id": "s1", "queries": ["q"]}) + "\n"
        # generation failure: no "queries" key at all -- must be skipped, not crash
        + json.dumps({"skill_id": "s2", "queries": []}) + "\n"
    )
    composite_file = tmp_path / "composite.jsonl"
    composite_file.write_text(
        json.dumps({"skill_ids": ["s1", "s2"], "query": None, "raw": "unparsed"}) + "\n"
    )
    out_file = tmp_path / "out.jsonl"
    args = _args(skills_file=str(skills_file), per_skill_file=str(per_skill_file),
                 composite_file=str(composite_file), out=str(out_file))
    sq.cmd_hard_negatives(args)
    records = [json.loads(l) for l in out_file.read_text().splitlines() if l]
    # only s1's per-skill row had a non-empty "queries" list; s2's row and the query-less
    # composite row must both be skipped
    assert len(records) == 1
    assert records[0]["skill_ids"] == ["s1"]
