"""Tests for tools/eval/dev_sibling.py — family F6's offline sibling map and query-time rule.
Real product Index/Router on a 3-card fixture: two near-identical siblings that differ in one
discriminating term, plus an unrelated card."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "eval"))

import dev_sibling  # noqa: E402
import dev_sparse  # noqa: E402

np = pytest.importorskip("numpy")


def test_build_sibling_map_same_leaf_threshold_topn_symmetric():
    urns = ["a", "b", "c", "d"]
    vec = np.array([[1.0, 0.0], [0.99, 0.14], [0.0, 1.0], [1.0, 0.0]])  # a~b (cos .99), a==d but other leaf
    leaf = {"a": "x", "b": "x", "c": "x", "d": "y"}
    m = dev_sibling.build_sibling_map(urns, vec, leaf, tau=0.9, n_max=3)
    assert m == {"a": ["b"], "b": ["a"]}          # c is orthogonal; d is in another leaf
    assert "d" not in m


def _cards():
    base = {"digest": "", "triggers": [], "negative_triggers": [], "requires": [], "refines": [],
            "status": "active", "replaced_by": None, "kind": None, "layer": None, "owner": "t"}
    return {
        "urn:skill:t:n:alpha": {**base, "urn": "urn:skill:t:n:alpha", "node": "n", "name": "deploy helper",
                                "description": "deploy the service to kubernetes clusters", "_body": "deploy rollout kubernetes"},
        "urn:skill:t:n:beta": {**base, "urn": "urn:skill:t:n:beta", "node": "n", "name": "deploy helper",
                               "description": "deploy the service to nomad clusters", "_body": "deploy rollout nomad"},
        "urn:skill:t:n:gamma": {**base, "urn": "urn:skill:t:n:gamma", "node": "n", "name": "invoice parser",
                                "description": "parse vendor invoices", "_body": "invoices pdf"},
    }


def _nodes():
    return {"_root": {"paths": ["_root/**"], "owner": "t"}, "n": {"paths": ["n/**"], "owner": "t"}}


def _router(rule):
    cli = dev_sparse._load_cli()
    cards, nodes = _cards(), _nodes()
    index = cli.Index.from_cards(cards, nodes)
    toks = {u: dev_sibling.card_tokens(cli, c) for u, c in cards.items()}
    smap = {"urn:skill:t:n:alpha": ["urn:skill:t:n:beta"], "urn:skill:t:n:beta": ["urn:skill:t:n:alpha"]}
    Sib = dev_sibling.make_sibling_router_class(cli)
    return cli, Sib(index, smap, toks, rule)


def _inject(router, query):
    admissible, _ = router.policy_filter("_root", query)
    cands = router.candidates(query, "_root", top_n=50)
    scored = router.score(cands, query, "_root")
    return [c["urn"] for c in router.select(scored, k=4, admissible=set(admissible), query=query)]


def test_rule_removes_the_sibling_the_query_does_not_discriminate_for():
    cli, r = _router("margin")
    out = _inject(r, "deploy the service to kubernetes")
    assert "urn:skill:t:n:alpha" in out and "urn:skill:t:n:beta" not in out
    assert r.last_fired == 1 and r.last_removed == ["urn:skill:t:n:beta"]


def test_tie_never_fires_both_siblings_stay():
    cli, r = _router("margin")
    out = _inject(r, "deploy the service")          # no discriminating term in the query
    assert "urn:skill:t:n:alpha" in out and "urn:skill:t:n:beta" in out
    assert r.last_fired == 0


def test_strict_rule_requires_loser_zero_and_winner_positive():
    cli, r = _router("strict")
    out = _inject(r, "deploy the service to kubernetes")
    assert "urn:skill:t:n:beta" not in out and r.last_fired == 1


def test_proxy_counts_non_gold_sibling_of_a_gold_skill():
    ref = {"g": ["s"], "s": ["g"]}
    assert dev_sibling.proxy_exposed(["s", "x"], {"g"}, ref) == 1.0
    assert dev_sibling.proxy_exposed(["g", "x"], {"g"}, ref) == 0.0   # gold itself is not exposure
    assert dev_sibling.proxy_exposed(["x"], {"g"}, ref) == 0.0
