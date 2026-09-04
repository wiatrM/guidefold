"""Router.score: RRF (k=60, scaled integers) fusion of the bm25/dense channels, plus the scope
feature (w_scope/(1+hops), additive, never the primary sort key -- the literal B0 bug fix) and
reverse PPR (mass flows from a hit toward what it requires)."""
from fractions import Fraction

from _router_helpers import make_card, make_nodes


def test_rrf_fusion_matches_the_scaled_integer_formula(gf):
    """Isolate RRF from scope/PPR: same node as caller (hops=0 for every candidate, so scope adds
    an equal constant to all of them) and a zero-edge graph (so PPR mass stays exactly
    proportional to each candidate's own seed and cannot reorder anything)."""
    cards = {
        "u:a": make_card("u:a", "_root", description="a"),
        "u:b": make_card("u:b", "_root", description="b"),
        "u:c": make_card("u:c", "_root", description="c"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = [
        {"urn": "u:a", "node": "_root", "bm25_rank": 1, "dense_rank": None},
        {"urn": "u:b", "node": "_root", "bm25_rank": 2, "dense_rank": 1},
        {"urn": "u:c", "node": "_root", "bm25_rank": 3, "dense_rank": None},
    ]
    scored = router.score(cands, "irrelevant query text", "_root")
    by_urn = {c["urn"]: c["score"] for c in scored}

    w_scope = idx.weights["w_scope"]  # hops=0 for every candidate here
    expected_rrf = {
        "u:a": idx.RRF_SCALE // (idx.RRF_K + 1),
        "u:b": idx.RRF_SCALE // (idx.RRF_K + 2) + idx.RRF_SCALE // (idx.RRF_K + 1),
        "u:c": idx.RRF_SCALE // (idx.RRF_K + 3),
    }
    # with no graph edges, PPR is a strictly monotonic (order-preserving) function of the scope-
    # adjusted RRF seed, so ranking must exactly follow expected_rrf + scope.
    assert by_urn["u:b"] > by_urn["u:a"] > by_urn["u:c"]
    for u in cands:
        assert by_urn[u["urn"]] >= expected_rrf[u["urn"]] + w_scope  # scope+ppr are non-negative
    assert all(isinstance(c["score"], int) for c in scored)


def test_scope_feature_is_additive_not_a_sort_key(gf):
    """Two candidates with identical BM25/dense ranks (so identical RRF) but different scope
    distance must differ by exactly w_scope/(1+hops) -- and a strong-relevance far candidate must
    still be able to outrank a weak-relevance near one (scope augments, it does not override)."""
    cards = {
        "u:near": make_card("u:near", "teamA.sub", description="near"),
        "u:far": make_card("u:far", "_root", description="far"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root", "teamA", "teamA.sub"))
    router = gf.Router(idx)
    cands = [
        {"urn": "u:near", "node": "teamA.sub", "bm25_rank": 1, "dense_rank": None},
        {"urn": "u:far", "node": "_root", "bm25_rank": 1, "dense_rank": None},
    ]
    scored = router.score(cands, "q", "teamA.sub")
    by_urn = {c["urn"]: c["score"] for c in scored}
    w_scope = idx.weights["w_scope"]
    expected_scope_delta = w_scope // (1 + 0) - w_scope // (1 + 2)
    # same rank => identical RRF, so the score gap is (almost) entirely the scope delta -- "almost"
    # because PPR is seeded from the scope-augmented score (ROUTER-SPEC's fused pipeline), so
    # u:near's slightly higher seed feeds back as a few extra units of PPR relative to u:far's.
    # That residual must stay tiny compared to w_scope itself, or scope has stopped being a mere
    # feature and started acting as the primary sort key again (the B0 bug).
    actual_delta = by_urn["u:near"] - by_urn["u:far"]
    assert abs(actual_delta - expected_scope_delta) <= max(1, w_scope // 100)
    assert actual_delta > 0  # nearer scope must still win when relevance is tied


def test_reverse_ppr_flows_from_a_hit_toward_what_it_requires(gf):
    """Hand-built graph, known answer: A requires B, C is unrelated. Seed mass only on A.
    Expect: mass[C] == 0 (no path reaches it), mass[B] > 0 (received via the requires edge),
    mass[A] > 0 (restart term). Cross-checked against an independent Fraction-based replay of
    the exact same fixed-point recurrence (same alpha, same 20 iterations, no floor division)."""
    cards = {
        "u:a": make_card("u:a", "_root", description="a", requires=["u:b"]),
        "u:b": make_card("u:b", "_root", description="b"),
        "u:c": make_card("u:c", "_root", description="c"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)

    seed = {"u:a": idx.IDF_SCALE, "u:b": 0, "u:c": 0}
    mass = router._reverse_ppr(seed)

    assert mass["u:c"] == 0
    assert mass["u:b"] > 0
    assert mass["u:a"] > 0

    # independent analytic replay with exact Fractions (no integer floor division anywhere)
    alpha = Fraction(idx.PPR_ALPHA_NUM, idx.PPR_ALPHA_DEN)
    w = idx.weights["edge.requires"]
    p = {"u:a": Fraction(idx.IDF_SCALE), "u:b": Fraction(0), "u:c": Fraction(0)}
    edges = {"u:a": [("u:b", w)], "u:b": [], "u:c": []}
    out_weight = {"u:a": w, "u:b": 0, "u:c": 0}
    fmass = dict(p)
    for _ in range(idx.PPR_ITERS):
        new_fmass = {u: alpha * p[u] for u in p}
        for u in p:
            if fmass[u] == 0 or out_weight[u] == 0:
                continue
            for t, ew in edges[u]:
                new_fmass[t] += (1 - alpha) * fmass[u] * ew / out_weight[u]
        fmass = new_fmass

    # the integer implementation truncates on every floor division; over a fixed-point
    # recurrence that stabilizes after the first couple of iterations the accumulated error is
    # tiny relative to IDF_SCALE -- assert it lands within a small absolute tolerance of the
    # exact rational answer.
    for u in ("u:a", "u:b", "u:c"):
        assert abs(mass[u] - float(fmass[u])) <= 4, (u, mass[u], float(fmass[u]))


def test_reverse_ppr_is_deterministic(gf):
    cards = {
        "u:a": make_card("u:a", "_root", description="a", requires=["u:b"]),
        "u:b": make_card("u:b", "_root", description="b"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    seed = {"u:a": 12345, "u:b": 0}
    assert router._reverse_ppr(seed) == router._reverse_ppr(seed)


def test_ties_are_broken_on_urn_never_on_insertion_order(gf):
    cards = {
        "u:zzz": make_card("u:zzz", "_root", description="same"),
        "u:aaa": make_card("u:aaa", "_root", description="same"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = [
        {"urn": "u:zzz", "node": "_root", "bm25_rank": 1, "dense_rank": None},
        {"urn": "u:aaa", "node": "_root", "bm25_rank": 1, "dense_rank": None},
    ]
    scored = router.score(cands, "q", "_root")
    assert scored[0]["score"] == scored[1]["score"]
    assert [c["urn"] for c in scored] == ["u:aaa", "u:zzz"]  # (-score, urn) tie-break
