"""Router.candidates: the fusion stage between policy_filter and score. Runs policy_filter (so a
deprecated/invisible/negative-triggered skill never becomes a candidate at all), computes the
bm25/dense rank per visible skill, and unions the top_n of each channel into one candidate list
carrying both ranks (or None where a channel didn't rank a skill)."""
from _router_helpers import make_card, make_nodes


def test_candidates_carries_bm25_rank_and_excludes_policy_drops(gf):
    cards = {
        "u:hit": make_card("u:hit", "_root", description="turnstile gate incident runbook"),
        "u:weak": make_card("u:weak", "_root", description="turnstile release train, incident-adjacent"),
        "u:miss": make_card("u:miss", "_root", description="release train schedule"),
        "u:old": make_card("u:old", "_root", description="turnstile gate incident", status="deprecated",
                            replaced_by="u:hit"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = router.candidates("turnstile gate incident", "_root")
    by_urn = {c["urn"]: c for c in cands}

    assert "u:old" not in by_urn  # dropped by policy (deprecated), never becomes a candidate
    assert "u:miss" not in by_urn  # no query-term overlap at all -> zero bm25 score, not a candidate
    assert set(by_urn) == {"u:hit", "u:weak"}
    assert by_urn["u:hit"]["bm25_rank"] == 1
    assert by_urn["u:hit"]["node"] == "_root"
    assert by_urn["u:weak"]["bm25_rank"] == 2
    assert router.last_drops == [("u:old", "deprecated")]


def test_candidates_dense_rank_is_none_when_no_word_vectors(gf):
    cards = {"u:a": make_card("u:a", "_root", description="hello world")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = router.candidates("hello", "_root")
    assert cands[0]["dense_rank"] is None
    assert cands[0]["bm25_rank"] == 1


def test_candidates_top_n_caps_each_channel_independently(gf):
    cards = {f"u:{i}": make_card(f"u:{i}", "_root", description=f"needle {i}" if i < 3 else "chaff")
             for i in range(10)}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = router.candidates("needle", "_root", top_n=2)
    urns = {c["urn"] for c in cands}
    # only the top_n=2 bm25-ranked skills should surface as candidates (no dense channel here).
    assert len(urns) == 2
    assert urns <= {"u:0", "u:1", "u:2"}


def test_candidates_returns_urns_sorted(gf):
    cards = {
        "u:zzz": make_card("u:zzz", "_root", description="same text"),
        "u:aaa": make_card("u:aaa", "_root", description="same text"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    cands = router.candidates("same text", "_root")
    assert [c["urn"] for c in cands] == ["u:aaa", "u:zzz"]


def test_dense_rank_is_true_cosine_not_dot_over_normsq(gf):
    """Peer-review counterexample. A=(dot 3, normsq 9) has cosine 3/3 = 1.00;
    B=(dot 1, normsq 2) has cosine 1/1.414 = 0.71. Cosine ranks A first. The old
    dot/normsq form gave A 0.33 and B 0.50 and ranked B first — an inverted ranking
    that would silently corrupt the dense channel the day w_dense > 0."""
    ranked = gf._dense_rank({"A": (3, 9), "B": (1, 2)})
    assert ranked == ["A", "B"]


def test_dense_rank_keeps_sign_and_zero_norms_safe(gf):
    ranked = gf._dense_rank({"neg": (-5, 4), "pos": (1, 100), "zero": (0, 7)})
    assert ranked == ["pos", "zero", "neg"]         # cos: 0.1 > 0 > -2.5


def test_w_dense_zero_disables_the_dense_channel_entirely(gf):
    """`w_dense` was never read; the channel ran whenever a word table existed. With w_dense = 0
    there must be no dense rank at all — otherwise the RRF vote is cast by a channel the manifest
    says is off (peer review, 2026-09-05)."""
    from _router_helpers import make_card
    cards = {"u:x": make_card("u:x", "_root", name="x", description="alpha beta", digest="", triggers=[], body="alpha")}
    table = {"alpha": (5, 0, 0), "beta": (0, 5, 0)}
    idx = gf.Index.from_cards(cards, {"_root": {"paths": ["**"], "owner": "p"}}, word_vectors=table)
    r = gf.Router(idx)
    idx.weights["w_dense"] = 0
    assert all(c["dense_rank"] is None for c in r.candidates("alpha", "_root"))
    idx.weights["w_dense"] = 1
    assert any(c["dense_rank"] is not None for c in r.candidates("alpha", "_root"))
