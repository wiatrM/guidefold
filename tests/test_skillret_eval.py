"""Tests for tools/eval/skillret.py — the SKILLRET-test dense-programme runner (F0/R0 and R1).

Pure logic (taxonomy/card/case conversion, node-setting selection, R0-vs-R1 Index equivalence) is
tested here with tiny synthetic data, no network access and no real SKILLRET corpus on disk —
`corpora.verify("skillret")`/`corpora.load_skillret()` are never called by these tests. The real
corpus is exercised only by the `stats`/`encode`/`r0`/`r1`/`latency` subcommands themselves, run
manually (see docs/reports/bakeoff/SKILLRET-test-2026-09-05.md), not by CI.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "eval"))

import skillret  # tools/eval/skillret.py


@pytest.fixture(scope="module")
def cli():
    return skillret.load_cli()


# --------------------------------------------------------------------------- synthetic corpus
def _taxonomy():
    return {"taxonomy": [
        {"major": "Data Engineering", "subs": [{"sub": "ETL"}, {"sub": "Warehousing"}]},
        {"major": "ML Ops", "subs": [{"sub": "Serving"}]},
    ]}


def _skills():
    return [
        {"id": "sk-1", "major": "Data Engineering", "sub": "ETL",
         "name": "Build a Pipeline", "description": "extract transform load", "body": "body one"},
        {"id": "sk-2", "major": "Data Engineering", "sub": "ETL",
         "name": "Schema Migration", "description": "migrate a schema", "body": "body two"},
        {"id": "sk-3", "major": "Data Engineering", "sub": "Warehousing",
         "name": "Star Schema", "description": "warehouse modelling", "body": "body three"},
        {"id": "sk-4", "major": "ML Ops", "sub": "Serving",
         "name": "Model Serving", "description": "serve a model", "body": "body four"},
    ]


def _queries():
    return [
        {"id": "q-1", "query": "how do I migrate a database schema", "skill_ids": ["sk-2"], "k": 1},
        {"id": "q-2", "query": "pipeline plus warehouse design together",
         "skill_ids": ["sk-1", "sk-3"], "k": 2},
    ]


# --------------------------------------------------------------------------- build_taxonomy
def test_build_taxonomy_is_two_level_with_root(cli):
    nodes, major_slug_of, node_of = skillret.build_taxonomy(cli, _taxonomy())
    assert nodes["_root"]["paths"] == ["**"]
    de = major_slug_of["Data Engineering"]
    ml = major_slug_of["ML Ops"]
    assert de in nodes and ml in nodes
    # every (major, sub) maps to "major-slug.sub-slug", one level below the major node
    assert node_of[("Data Engineering", "ETL")] == f"{de}.etl"
    assert node_of[("Data Engineering", "Warehousing")] == f"{de}.warehousing"
    assert node_of[("ML Ops", "Serving")] == f"{ml}.serving"
    # exactly _root + one node per major + one node per (major, sub) — no deeper levels
    assert set(nodes) == {"_root", de, ml, f"{de}.etl", f"{de}.warehousing", f"{ml}.serving"}


# --------------------------------------------------------------------------- build_cards
def test_build_cards_urns_and_one_to_one_id_mapping(cli):
    nodes, major_slug_of, node_of = skillret.build_taxonomy(cli, _taxonomy())
    cards, id_to_urn = skillret.build_cards(_skills(), node_of)
    assert len(id_to_urn) == len(_skills())
    assert len(cards) == len(_skills())
    de = major_slug_of["Data Engineering"]
    expect_urn = f"urn:skill:skillret:{de}.etl:sk-1"
    assert id_to_urn["sk-1"] == expect_urn
    assert expect_urn in cards
    assert cards[expect_urn]["node"] == f"{de}.etl"
    # every card has no requires/triggers/refines -- SKILLRET carries none of these fields
    for c in cards.values():
        assert c["requires"] == []
        assert c["triggers"] == []
        assert c["negative_triggers"] == []
        assert c["refines"] == []


# --------------------------------------------------------------------------- build_cases
def test_build_cases_first_gold_is_grade_3_rest_grade_2_category_is_k(cli):
    nodes, major_slug_of, node_of = skillret.build_taxonomy(cli, _taxonomy())
    cards, id_to_urn = skillret.build_cards(_skills(), node_of)
    cases = skillret.build_cases(_queries(), id_to_urn)
    by_qid = {c["qid"]: c for c in cases}

    single = by_qid["q-1"]
    assert single["category"] == "k1"
    assert single["k"] == 1
    assert [r["grade"] for r in single["relevant"]] == [3]
    assert single["distractors"] == []

    multi = by_qid["q-2"]
    assert multi["category"] == "k2"
    assert multi["k"] == 2
    assert [r["grade"] for r in multi["relevant"]] == [3, 2]
    assert multi["relevant"][0]["urn"] == id_to_urn["sk-1"]
    assert multi["relevant"][1]["urn"] == id_to_urn["sk-3"]


def test_build_cases_skips_unresolvable_skill_ids(cli):
    nodes, major_slug_of, node_of = skillret.build_taxonomy(cli, _taxonomy())
    cards, id_to_urn = skillret.build_cards(_skills(), node_of)
    queries = [{"id": "q-x", "query": "ghost", "skill_ids": ["sk-1", "does-not-exist"], "k": 2}]
    cases = skillret.build_cases(queries, id_to_urn)
    assert len(cases[0]["relevant"]) == 1  # the unresolvable id is silently dropped, not KeyError
    assert cases[0]["relevant"][0]["grade"] == 3


# --------------------------------------------------------------------------- node_for_setting
def test_node_for_setting_root_is_always_root_never_the_leaf(cli):
    nodes, major_slug_of, node_of = skillret.build_taxonomy(cli, _taxonomy())
    cards, id_to_urn = skillret.build_cards(_skills(), node_of)
    cases = skillret.build_cases(_queries(), id_to_urn)
    major_of_qid = {
        "q-1": major_slug_of["Data Engineering"],
        "q-2": major_slug_of["Data Engineering"],
    }

    root_fn = skillret.node_for_setting("root", major_of_qid)
    major_fn = skillret.node_for_setting("major", major_of_qid)
    de = major_slug_of["Data Engineering"]
    for c in cases:
        assert root_fn(c) == "_root"
        assert major_fn(c) == de
        # "major" never resolves to a leaf sub-node (no "." in the value) -- that would leak
        # the gold answer's own sub-category into the scope feature
        assert "." not in major_fn(c)

    with pytest.raises(ValueError):
        skillret.node_for_setting("leaf", major_of_qid)


# --------------------------------------------------------------------------- R0 vs R1 Index equivalence
def test_r0_and_r1_index_differ_only_in_w_dense_and_skill_normsq(cli):
    """Index.from_cards's BM25/graph build (_build_graph/_build_bm25) never reads `weights` --
    only `_build_dense`/Router query-time code do. So the R0 index (weights={"w_dense": 0}) and
    the R1 index (weights={"w_dense": 1}, word_vectors=None so _build_dense is a no-op) must be
    byte-identical on postings/idf/field_len/field_norm/graph/cards/nodes, and differ from
    DEFAULT_WEIGHTS in exactly one key. skill_normsq is populated separately by
    build_r1_index_and_router (from the encoder cache) -- it, and skill_vectors, are the only
    dense-arm-specific attributes and are excluded from the "must be identical" comparison here
    on purpose.
    """
    from _router_helpers import make_card, make_nodes

    nodes = make_nodes("a", "b")
    cards = {
        "urn:skill:skillret:a:one": make_card(
            "urn:skill:skillret:a:one", "a", description="alpha beta gamma", body="delta epsilon"),
        "urn:skill:skillret:b:two": make_card(
            "urn:skill:skillret:b:two", "b", description="zeta eta theta", body="iota kappa"),
    }

    idx_r0 = skillret.build_r0_index(cli, cards, nodes)
    idx_r1 = cli.Index.from_cards(cards, nodes, weights={"w_dense": 1}, word_vectors=None)

    assert idx_r0.postings == idx_r1.postings
    assert idx_r0.idf == idx_r1.idf
    assert idx_r0.field_len == idx_r1.field_len
    assert idx_r0.field_norm == idx_r1.field_norm
    assert idx_r0.graph == idx_r1.graph
    assert idx_r0.cards == idx_r1.cards
    assert idx_r0.nodes == idx_r1.nodes
    # both sides leave the dense tables empty at this point (word_vectors=None); the R1 runner
    # (build_r1_index_and_router) is the one that overwrites skill_normsq from the encoder cache
    assert idx_r0.skill_vectors == idx_r1.skill_vectors == {}
    assert idx_r0.skill_normsq == idx_r1.skill_normsq == {}

    diff_keys = {k for k in idx_r1.weights if idx_r1.weights[k] != idx_r0.weights.get(k)}
    assert diff_keys == {"w_dense"}
    assert idx_r0.weights["w_dense"] == 0
    assert idx_r1.weights["w_dense"] == 1


def test_build_r0_index_merges_default_weights(cli):
    """Index.from_cards merges {**DEFAULT_WEIGHTS, **{"w_dense": 0}} -- every other weight
    (w_scope, w_ppr, abstain_threshold, ppr_mode, ...) stays at the shipped default, so R0 truly
    is 'the shipped product', not a hand-tuned variant."""
    from _router_helpers import make_card, make_nodes

    nodes = make_nodes("a")
    cards = {"urn:skill:skillret:a:one": make_card("urn:skill:skillret:a:one", "a", description="x")}
    idx = skillret.build_r0_index(cli, cards, nodes)
    for key, val in cli.Index.DEFAULT_WEIGHTS.items():
        if key == "w_dense":
            continue
        assert idx.weights[key] == val, f"{key} was not left at its shipped default"
    assert idx.weights["w_dense"] == 0


# --------------------------------------------------------------------------- DenseCandidateRouter wiring
def test_dense_candidate_router_returns_empty_without_a_query_vector(cli):
    """_dense_scores must fail closed (empty dict, not an exception) when _current_qid has no
    entry in query_vec_of -- candidates() then falls back to the bm25-only candidate pool for
    that query rather than crashing the whole run."""
    import numpy as np
    from _router_helpers import make_card, make_nodes

    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    cards = {urn_a: make_card(urn_a, "a", description="alpha beta")}
    row_of = {urn_a: 0}
    skill_mat = np.array([[1] * 8], dtype=np.int8)
    query_vec_of = {}  # no cached vector for any qid

    idx, router = skillret.build_r1_index_and_router(cli, cards, nodes, row_of, skill_mat, query_vec_of)
    router._current_qid = "qid-not-cached"
    assert router._dense_scores("alpha beta", {urn_a}) == {}


def test_build_r1_index_and_router_raises_on_missing_embedding(cli):
    import numpy as np
    from _router_helpers import make_card, make_nodes

    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    urn_b = "urn:skill:skillret:a:two"
    cards = {
        urn_a: make_card(urn_a, "a", description="alpha"),
        urn_b: make_card(urn_b, "a", description="beta"),
    }
    row_of = {urn_a: 0}  # urn_b has no cached row -- must raise, not silently skip it
    skill_mat = np.array([[1] * 8], dtype=np.int8)
    with pytest.raises(SystemExit):
        skillret.build_r1_index_and_router(cli, cards, nodes, row_of, skill_mat, {})
