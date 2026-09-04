"""Router.select: requires closure (depth<=2) as a hard membership rule whose items count
toward the k cap, general->specific final ordering (root-most first), and abstention below
abstain_threshold."""
from _router_helpers import make_card, make_nodes


def _scored(urn, node, score):
    return {"urn": urn, "node": node, "score": score}


def test_requires_closure_counts_toward_k(gf):
    """top pick requires a dep that did not itself make the top-k by score; the dep must still
    appear, and must count against the k cap (so a lower-scored independent candidate gets
    bumped)."""
    cards = {
        "u:top": make_card("u:top", "_root", description="top", requires=["u:dep"]),
        "u:dep": make_card("u:dep", "_root", description="dep"),
        "u:mid": make_card("u:mid", "_root", description="mid"),
        "u:low": make_card("u:low", "_root", description="low"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [
        _scored("u:top", "_root", 100),
        _scored("u:mid", "_root", 90),
        _scored("u:low", "_root", 80),
        _scored("u:dep", "_root", 10),   # scores low enough it would not make k=2 on its own
    ]
    out = router.select(scored, k=2, abstain_threshold=0)
    urns = {c["urn"] for c in out}
    assert urns == {"u:top", "u:dep"}   # closure forced u:dep in, bumping u:mid out
    assert len(out) == 2


def test_requires_closure_respects_depth_cap_of_two(gf):
    """A -> B -> C -> D chain: selecting A must pull in B and C (depth 1 and 2) but not D
    (depth 3, beyond the hard cap), even with k large enough to fit it."""
    cards = {
        "u:a": make_card("u:a", "_root", description="a", requires=["u:b"]),
        "u:b": make_card("u:b", "_root", description="b", requires=["u:c"]),
        "u:c": make_card("u:c", "_root", description="c", requires=["u:d"]),
        "u:d": make_card("u:d", "_root", description="d"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [_scored("u:a", "_root", 100)]
    out = router.select(scored, k=4, abstain_threshold=0)
    urns = {c["urn"] for c in out}
    assert urns == {"u:a", "u:b", "u:c"}
    assert "u:d" not in urns


def test_requires_closure_never_pulls_in_a_deprecated_dependency(gf):
    cards = {
        "u:top": make_card("u:top", "_root", description="top", requires=["u:dep"]),
        "u:dep": make_card("u:dep", "_root", description="dep", status="deprecated", replaced_by="u:top"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [_scored("u:top", "_root", 100)]
    out = router.select(scored, k=4, abstain_threshold=0)
    assert [c["urn"] for c in out] == ["u:top"]


def test_final_order_is_general_to_specific_root_most_first(gf):
    nodes = make_nodes("_root", "teamA", "teamA.sub")
    cards = {
        "u:root": make_card("u:root", "_root", description="root"),
        "u:teamA": make_card("u:teamA", "teamA", description="team a"),
        "u:sub": make_card("u:sub", "teamA.sub", description="sub"),
    }
    idx = gf.Index.from_cards(cards, nodes)
    router = gf.Router(idx)
    # deliberately scored so the *specific* one is the best match -- selection order (by score)
    # differs from the required output order (by depth).
    scored = [
        _scored("u:sub", "teamA.sub", 300),
        _scored("u:teamA", "teamA", 200),
        _scored("u:root", "_root", 100),
    ]
    out = router.select(scored, k=4, abstain_threshold=0)
    assert [c["urn"] for c in out] == ["u:root", "u:teamA", "u:sub"]


def test_abstains_below_threshold(gf):
    cards = {"u:weak": make_card("u:weak", "_root", description="weak")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [_scored("u:weak", "_root", 50)]
    assert router.select(scored, k=4, abstain_threshold=51) == []
    assert router.select(scored, k=4, abstain_threshold=50) != []


def test_abstains_on_empty_candidate_list(gf):
    cards = {"u:x": make_card("u:x", "_root", description="x")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    assert router.select([], k=4) == []


def test_k_cap_is_enforced(gf):
    cards = {f"u:{i}": make_card(f"u:{i}", "_root", description=str(i)) for i in range(6)}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [_scored(u, "_root", 100 - i) for i, u in enumerate(cards)]
    out = router.select(scored, k=4, abstain_threshold=0)
    assert len(out) == 4
