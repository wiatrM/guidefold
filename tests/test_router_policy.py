"""Router.policy_filter: hard drops, recorded reason per drop, applied before any ranking
(E1.1). Never a demotion -- a dropped skill cannot be resurrected by score."""
from _router_helpers import make_card, make_nodes


def test_deprecated_excluded_by_default_and_included_with_flag(gf):
    cards = {
        "u:new": make_card("u:new", "_root", description="current guidance", status="active"),
        "u:old": make_card("u:old", "_root", description="old guidance", status="deprecated",
                            replaced_by="u:new"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    kept, drops = router.policy_filter("_root")
    assert kept == ["u:new"]
    assert ("u:old", "deprecated") in drops

    kept2, drops2 = router.policy_filter("_root", include_deprecated=True)
    assert set(kept2) == {"u:new", "u:old"}
    assert not any(reason == "deprecated" for _, reason in drops2)


def test_visibility_is_own_subtree_union_ancestor_chain(gf):
    nodes = make_nodes("_root", "teamA", "teamA.sub", "teamB")
    cards = {
        "u:root": make_card("u:root", "_root", description="root guidance"),
        "u:teamA": make_card("u:teamA", "teamA", description="team a guidance"),
        "u:teamA.sub": make_card("u:teamA.sub", "teamA.sub", description="team a sub guidance"),
        "u:teamB": make_card("u:teamB", "teamB", description="team b guidance, a sibling"),
    }
    idx = gf.Index.from_cards(cards, nodes)
    router = gf.Router(idx)
    kept, drops = router.policy_filter("teamA")
    # caller's own subtree (teamA + descendant teamA.sub) union the ancestor chain (_root) --
    # teamB is a sibling, not an ancestor or descendant, and must be dropped.
    assert set(kept) == {"u:root", "u:teamA", "u:teamA.sub"}
    assert ("u:teamB", "not-visible") in drops


def test_visibility_at_root_sees_everything(gf):
    nodes = make_nodes("_root", "teamA", "teamB")
    cards = {
        "u:teamA": make_card("u:teamA", "teamA", description="team a"),
        "u:teamB": make_card("u:teamB", "teamB", description="team b"),
    }
    idx = gf.Index.from_cards(cards, nodes)
    router = gf.Router(idx)
    kept, _ = router.policy_filter("_root")
    assert set(kept) == {"u:teamA", "u:teamB"}


def test_negative_trigger_drops_on_exact_match_but_not_otherwise(gf):
    """The fixture has no negative_triggers yet -- exercised here with a synthetic skill."""
    cards = {
        "u:noisy": make_card(
            "u:noisy", "_root", description="something usually irrelevant to outages",
            negative_triggers=["planned maintenance window"],
        ),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)

    kept, drops = router.policy_filter("_root", query="we are inside a planned maintenance window today")
    assert kept == []
    assert drops == [("u:noisy", "negative-trigger:planned maintenance window")]

    kept2, drops2 = router.policy_filter("_root", query="unrelated task about something else")
    assert kept2 == ["u:noisy"]
    assert drops2 == []


def test_negative_trigger_requires_all_its_words_present(gf):
    """A multi-word negative trigger only fires when every one of its tokens is in the query --
    a partial word overlap must not drop the skill."""
    cards = {
        "u:noisy": make_card("u:noisy", "_root", description="x", negative_triggers=["planned maintenance"]),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    # both trigger words ("planned", "maintenance") present, in any order/position -> dropped
    kept, drops = router.policy_filter("_root", query="a maintenance window was planned for tonight")
    assert kept == []
    assert drops == [("u:noisy", "negative-trigger:planned maintenance")]
    # only one of the two trigger words present -> not dropped
    kept2, drops2 = router.policy_filter("_root", query="a planned rollout, nothing else")
    assert kept2 == ["u:noisy"]
    assert drops2 == []


def test_policy_filter_tokenises_negative_triggers_once_per_router(gf, monkeypatch):
    """Profiled on a 501-skill real corpus: re-tokenising every skill's negative-trigger phrases on
    every query was 84 % of the query path. The phrases are static; tokenise them once."""
    from _router_helpers import make_card
    cards = {f"u:{i}": make_card(f"u:{i}", "_root", description=f"skill {i}",
                                 negative_triggers=["planned auth change", "policy edit"]) for i in range(50)}
    idx = gf.Index.from_cards(cards, {"_root": {"paths": ["**"], "owner": "p"}}, word_vectors=None)
    r = gf.Router(idx)
    calls = {"n": 0}; real = gf.tokenize
    def counting(s):
        calls["n"] += 1; return real(s)
    monkeypatch.setattr(gf, "tokenize", counting)
    for q in ("handle an outage", "write an adr", "add rbac", "deploy the widget", "planned auth change now"):
        r.policy_filter("_root", q)
    # 100 phrases tokenised once + 5 queries; NOT 100 phrases x 5 queries + 5
    assert calls["n"] <= 100 + 5, f"tokenize called {calls['n']} times — phrases re-tokenised per query"
    kept, drops = r.policy_filter("_root", "planned auth change now")
    assert kept == [] and all(d[1].startswith("negative-trigger") for d in drops)   # semantics unchanged
