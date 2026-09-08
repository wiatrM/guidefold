"""Nearest wins (ADR-0037): when the same skill name is visible at two depths, the policy filter
keeps only the copy closest to the requesting node and records the other as a drop.

Motivated by the 2026-09-08 conflicting-siblings run: BM25F ranked the team-level copy above the
service-level edit in 24/24 cells and the agent applied the stale values in 23/24."""
from _router_helpers import make_card, make_nodes


def _cards():
    return {
        "urn:skill:acme:atlas.core:api-conventions": make_card(
            "urn:skill:acme:atlas.core:api-conventions", "atlas.core",
            description="HTTP API conventions pageSize default 150 max 1500"),
        "urn:skill:acme:atlas.core.svc0:api-conventions": make_card(
            "urn:skill:acme:atlas.core.svc0:api-conventions", "atlas.core.svc0",
            description="HTTP API conventions pageSize default 50 max 500"),
        "urn:skill:acme:atlas.core:release-train": make_card(
            "urn:skill:acme:atlas.core:release-train", "atlas.core", description="release train schedule"),
    }


def test_leaf_copy_shadows_ancestor_copy_of_the_same_name(gf):
    idx = gf.Index.from_cards(_cards(), make_nodes("_root", "atlas", "atlas.core", "atlas.core.svc0"))
    router = gf.Router(idx)
    kept, drops = router.policy_filter("atlas.core.svc0", "api conventions pageSize")
    assert "urn:skill:acme:atlas.core.svc0:api-conventions" in kept
    assert "urn:skill:acme:atlas.core:api-conventions" not in kept
    assert "urn:skill:acme:atlas.core:release-train" in kept  # a different name is not shadowed
    assert ("urn:skill:acme:atlas.core:api-conventions",
            "shadowed-by-nearer:urn:skill:acme:atlas.core.svc0:api-conventions") in drops


def test_ancestor_copy_is_the_only_one_visible_from_a_sibling(gf):
    idx = gf.Index.from_cards(_cards(), make_nodes("_root", "atlas", "atlas.core", "atlas.core.svc0", "atlas.core.svc1"))
    router = gf.Router(idx)
    kept, drops = router.policy_filter("atlas.core.svc1", "api conventions pageSize")
    assert kept == ["urn:skill:acme:atlas.core:api-conventions", "urn:skill:acme:atlas.core:release-train"] or \
        set(kept) == {"urn:skill:acme:atlas.core:api-conventions", "urn:skill:acme:atlas.core:release-train"}
    assert not any(reason.startswith("shadowed") for _, reason in drops)


def test_shadowed_ancestor_never_reaches_route(gf):
    idx = gf.Index.from_cards(_cards(), make_nodes("_root", "atlas", "atlas.core", "atlas.core.svc0"))
    router = gf.Router(idx)
    urns = [c["urn"] if isinstance(c, dict) else c for c in router.route("api conventions pageSize", "atlas.core.svc0")]
    assert "urn:skill:acme:atlas.core:api-conventions" not in urns
    assert urns and urns[0] == "urn:skill:acme:atlas.core.svc0:api-conventions"
