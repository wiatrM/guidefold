"""Exact parity tests for the opt-in resident service BM25 cache; no model/GPU."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.serve_spike.sparse_cache import install_bm25_cache
from _router_helpers import make_card, make_nodes


def _index(gf, weights=None):
    cards = {
        "u:a": make_card("u:a", "_root", name="alpha-beta", description="alpha beta beta",
                        body="alpha " * 17 + "gamma", triggers=["alpha gamma"]),
        "u:b": make_card("u:b", "team", description="gamma beta", body="beta gamma delta",
                        requires=["u:a"]),
        "u:c": make_card("u:c", "other", description="alpha delta", body="delta delta",
                        negative_triggers=["not delta"]),
        "u:z": make_card("u:z", "_root", name="empty", description="", body=""),
    }
    return gf.Index.from_cards(cards, make_nodes("_root", "team", "other"),
                               weights={"ppr_mode": "closure", **(weights or {})})


@pytest.mark.parametrize("weights", [
    {},
    {"field.name": 0, "field.description": 0, "field.digest": 0,
     "field.triggers": 0, "field.body": 0},
    {"field.name": -3, "field.description": 7, "field.digest": -1,
     "field.triggers": 0, "field.body": 2},
    {"field.name": 10**60, "field.description": 10**50, "field.body": -(10**40)},
])
@pytest.mark.parametrize("budget", [0, 1, 1024, 256 * 1024 * 1024])
def test_exact_scores_qtf_visibility_zero_keys_and_bound(gf, weights, budget):
    idx = _index(gf, weights)
    baseline, optimized = gf.Router(idx), gf.Router(idx)
    metadata = install_bm25_cache(optimized, max_bytes=budget)
    before = (metadata.copy(), tuple(optimized.bm25_cache.terms))
    for query in ("", "  -- ", "absent", "ALPHA alpha alpha", "alpha beta gamma",
                  "beta gamma beta -- DELTA", "alpha_beta", "CAFÉ alpha 한국어"):
        for visible in (set(), set(idx.cards), {"u:a"}, {"u:c", "u:z"},
                        {"u:a", "u:b", "not-in-index"}):
            wanted = baseline._bm25_scores(query, visible)
            actual = optimized._bm25_scores(query, visible)
            assert actual == wanted
            assert list(actual) == list(wanted)
    assert metadata["estimated_cache_bytes"] <= budget
    assert metadata["cached_terms"] <= metadata["total_terms"]
    assert metadata["cached_term_doc_pairs"] <= metadata["total_term_doc_pairs"]
    assert (metadata.copy(), tuple(optimized.bm25_cache.terms)) == before
    assert metadata["query_cache"] is False and metadata["lazy_warmup"] is False
    if budget == 256 * 1024 * 1024:
        assert metadata["fully_cached"]
        assert metadata["posting_coverage"] == 1.0
        assert metadata["term_coverage"] == 1.0
    if all(idx.weights["field." + f] == 0 for f in idx.FIELDS):
        assert optimized._bm25_scores("alpha", set(idx.cards))
        assert set(optimized._bm25_scores("alpha", set(idx.cards)).values()) == {0}


def test_exact_zero_denominator_and_arbitrary_precision(gf):
    idx = _index(gf, {"field." + f: 0 for f in gf.Index.FIELDS})
    idx.K1 = 1.0
    idx.weights["field.body"] = -1
    idx.field_norm["body"]["u:b"] = idx.IDF_SCALE
    base, opt = gf.Router(idx), gf.Router(idx)
    install_bm25_cache(opt)
    # u:b contains beta exactly once: wtf=-S and k1=S, so denominator=0.
    assert base._bm25_scores("beta", {"u:b"}) == {"u:b": 0}
    assert opt._bm25_scores("beta beta", {"u:b"}) == {"u:b": 0}


def _path(router, query, node, top_n):
    admissible, drops = router.policy_filter(node, query)
    candidates = router.candidates(query, node, top_n=top_n)
    scored = router.score(candidates, query, node)
    selected = router.select(scored, k=4, admissible=set(admissible))
    return admissible, drops, candidates, scored, selected


@pytest.mark.parametrize("seed", [11, 39, 104])
def test_random_corpora_full_pipeline_and_masks(gf, seed):
    rng = random.Random(seed)
    vocab = ["alpha", "beta", "gamma", "delta", "http", "ci", "kubernetes", "ab"]
    cards = {}
    for i in range(45):
        def words(maximum):
            return " ".join(rng.choices(vocab, k=rng.randrange(maximum + 1)))
        urn = f"u:{i:02d}"
        cards[urn] = make_card(
            urn, rng.choice(["_root", "team", "team.child", "other"]),
            name=words(3) or str(i), description=words(17), body=words(75),
            digest=words(12), triggers=[words(3)],
            negative_triggers=["no alpha"] if i % 11 == 0 else [],
            status="deprecated" if i % 13 == 0 else "active",
            requires=[f"u:{i - 1:02d}"] if i and i % 7 == 0 else [])
    idx = gf.Index.from_cards(cards, make_nodes("_root", "team", "team.child", "other"),
        weights={**{"field." + f: rng.choice([0, 1, 3, 9]) for f in gf.Index.FIELDS},
                 "ppr_mode": "closure"})
    baseline, optimized = gf.Router(idx), gf.Router(idx)
    install_bm25_cache(optimized)
    for _ in range(45):
        query = " ".join(rng.choices(vocab + ["absent", "no"], k=rng.randrange(15)))
        visible = {u for u in cards if rng.random() < .55}
        assert optimized._bm25_scores(query, visible) == baseline._bm25_scores(query, visible)
        node = rng.choice(list(idx.nodes))
        top_n = rng.choice([1, 2, 7, 50])
        assert _path(optimized, query, node, top_n) == _path(baseline, query, node, top_n)


def test_hybrid_cross_ranks_and_full_pipeline_unchanged(gf):
    cards = {f"u:{i}": make_card(f"u:{i}", "_root",
              description=" ".join(["needle"] * (8-i) + ["filler"] * i),
              body="context", requires=["u:1"] if i == 7 else [])
             for i in range(8)}
    idx = gf.Index.from_cards(cards, make_nodes("_root"),
        weights={"w_dense": 1, "ppr_mode": "closure"})

    class DenseRouter(gf.Router):
        def _dense_scores(self, query, visible):
            return {u: (900 if u == "u:7" else i + 1, 1)
                    for i, u in enumerate(sorted(visible))}

    baseline, optimized = DenseRouter(idx), DenseRouter(idx)
    install_bm25_cache(optimized)
    original = _path(baseline, "needle needle", "_root", 2)
    cross = next(c for c in original[2] if c["urn"] == "u:7")
    assert cross["dense_rank"] == 1
    assert cross["bm25_rank"] > 2
    assert _path(optimized, "needle needle", "_root", 2) == original


def test_partial_cache_explicit_coverage_and_no_request_time_growth(gf):
    idx = _index(gf)
    base, opt = gf.Router(idx), gf.Router(idx)
    meta = install_bm25_cache(opt, max_bytes=1024)
    assert 0 < meta["cached_terms"] < meta["total_terms"]
    assert 0 < meta["posting_coverage"] < 1
    assert not meta["fully_cached"]
    before = meta.copy(), tuple(opt.bm25_cache.terms)
    query = " ".join(idx.idf)
    for _ in range(3):
        assert opt._bm25_scores(query, set(idx.cards)) == base._bm25_scores(query, set(idx.cards))
    assert (meta.copy(), tuple(opt.bm25_cache.terms)) == before


def test_cache_disables_on_weights_or_index_replacement(gf):
    idx = _index(gf)
    base, opt = gf.Router(idx), gf.Router(idx)
    meta = install_bm25_cache(opt)
    idx.weights["field.body"] += 10
    assert opt._bm25_scores("alpha beta", set(idx.cards)) == base._bm25_scores("alpha beta", set(idx.cards))
    assert not meta["active"]

    opt = gf.Router(idx)
    meta = install_bm25_cache(opt)
    opt.index = _index(gf, {"field.body": 40})
    assert opt._bm25_scores("gamma", set(opt.index.cards)) == gf.Router(opt.index)._bm25_scores("gamma", set(opt.index.cards))
    assert not meta["active"]


def test_explicit_invalidation_and_single_install(gf):
    idx = _index(gf)
    router = gf.Router(idx)
    metadata = install_bm25_cache(router)
    assert metadata is router.bm25_cache_metadata
    with pytest.raises(ValueError, match="already installed"):
        install_bm25_cache(router)
    router.bm25_cache.invalidate("manual_snapshot_mutation")
    idx.idf["alpha"] += 32
    assert router._bm25_scores("alpha", set(idx.cards)) == gf.Router(idx)._bm25_scores("alpha", set(idx.cards))
    assert metadata["disabled_reason"] == "manual_snapshot_mutation"


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_invalid_budget_does_not_mutate_router(gf, budget):
    router = gf.Router(_index(gf))
    with pytest.raises(ValueError):
        install_bm25_cache(router, max_bytes=budget)
    assert not hasattr(router, "bm25_cache")


def test_full_cache_avoids_legacy_scoring_during_requests(gf):
    idx = _index(gf)
    baseline, optimized = gf.Router(idx), gf.Router(idx)
    query = "alpha alpha beta delta"
    wanted = baseline._bm25_scores(query, {"u:a", "u:b"})
    metadata = install_bm25_cache(optimized)
    assert metadata["fully_cached"]

    def must_not_score_again(*args):
        raise AssertionError("a fully precomputed term performed legacy scoring")
    optimized.bm25_cache.original = must_not_score_again
    assert optimized._bm25_scores(query, {"u:a", "u:b"}) == wanted
    assert baseline._bm25_scores(query, {"u:a", "u:b"}) == wanted


@pytest.mark.parametrize("term_in_index", [True, False])
def test_nonidempotent_term_falls_back_for_whole_query(gf, monkeypatch, term_in_index):
    cards = {
        "u:a": make_card("u:a", "_root", body="alpha"),
        "u:b": make_card("u:b", "_root", body="beta"),
    }
    if term_in_index:
        cards["u:r"] = make_card("u:r", "_root", body="redirect")
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    ordinary_tokenize = gf.tokenize

    def unusual_tokenize(text):
        if text == "trigger":
            return ["beta", "redirect", "redirect"]
        if text == "redirect":
            return ["alpha"]
        return ordinary_tokenize(text)

    monkeypatch.setattr(gf, "tokenize", unusual_tokenize)
    baseline, optimized = gf.Router(idx), gf.Router(idx)
    meta = install_bm25_cache(optimized)
    assert meta["uncacheable_term_keys"] == int(term_in_index)
    expected = baseline._bm25_scores("trigger", set(cards))
    original = optimized.bm25_cache.original
    calls = []

    def record_whole_query(query, visible):
        calls.append(query)
        return original(query, visible)

    optimized.bm25_cache.original = record_whole_query
    assert optimized._bm25_scores("trigger", set(cards)) == expected
    assert "u:a" not in expected
    assert calls == ["trigger"]  # no partial per-term accumulation or retokenizing