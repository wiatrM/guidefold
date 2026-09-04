"""Index: builds cards + graph + field-weighted BM25 postings (integer IDF) from the tree, or
from hand-built cards via from_cards(). No ranking lives here (that's Router) -- just build-time
state that must be exact and integer-only."""
from _router_helpers import make_card, make_nodes


def test_build_scans_the_real_fixture(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    idx = gf.Index.build(fixture_root, cfg)
    assert len(idx.cards) == 26  # matches test_all_skills_finds_26_non_generated_skills
    u = "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
    assert idx.cards[u]["node"] == "atlas.identity.turnstile"
    assert idx.cards[u]["status"] == "active"
    dep = "urn:skill:meridian:atlas.identity:rbac-policies"
    assert dep in idx.graph["requires"][u]


def test_deprecated_skill_populates_replaces_edge(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    idx = gf.Index.build(fixture_root, cfg)
    legacy = "urn:skill:meridian:atlas.identity:legacy-session-auth"
    postgres_auth = "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
    assert idx.cards[legacy]["status"] == "deprecated"
    assert legacy in idx.graph["replaces"][postgres_auth]


def test_idf_and_field_norm_are_pure_integers(gf, fixture_root):
    """Determinism by construction: math.log runs once at build time for IDF, then everything
    is a scaled int -- no float may leak into state Router reads at query time."""
    cfg = gf.load_map(fixture_root)
    idx = gf.Index.build(fixture_root, cfg)
    assert idx.idf, "expected at least one term"
    assert all(isinstance(v, int) for v in idx.idf.values())
    for field in idx.FIELDS:
        assert all(isinstance(v, int) for v in idx.field_norm[field].values())
        assert all(isinstance(v, int) for v in idx.field_len[field].values())


def test_build_is_deterministic_across_repeated_calls(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    idx1 = gf.Index.build(fixture_root, cfg)
    idx2 = gf.Index.build(fixture_root, cfg)
    assert idx1.idf == idx2.idf
    assert idx1.postings == idx2.postings
    assert idx1.field_norm == idx2.field_norm
    assert idx1.graph == idx2.graph


def test_from_cards_bm25_ranks_the_relevant_card_first(gf):
    cards = {
        "urn:skill:acme:_root:turnstile-guide": make_card(
            "urn:skill:acme:_root:turnstile-guide", "_root",
            description="How to operate the turnstile gate service.",
            digest="turnstile gate operations",
            body="turnstile turnstile gate incidents and rollbacks",
        ),
        "urn:skill:acme:_root:unrelated": make_card(
            "urn:skill:acme:_root:unrelated", "_root",
            description="Release train scheduling for the whole org.",
            digest="release trains",
            body="release train schedule and changelog format",
        ),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scores = router._bm25_scores("turnstile gate incident", set(cards))
    ranked = sorted(scores, key=lambda u: -scores[u])
    assert ranked[0] == "urn:skill:acme:_root:turnstile-guide"
    assert all(isinstance(v, int) for v in scores.values())


def test_dense_channel_is_empty_by_default(gf):
    """w_dense ships at 0 and word_vectors is empty unless a caller supplies a table (E1.3/E1.4
    territory) -- Index must not silently build a dense channel out of nothing."""
    cards = {"u1": make_card("u1", "_root", description="hello world")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    assert idx.word_vectors == {}
    assert idx.skill_vectors == {}
    assert idx.weights["w_dense"] == 0


def test_dense_channel_with_a_synthetic_word_vector_table(gf):
    """Dense retrieval isn't dead code: with a hand-built word->vector table it must produce a
    skill_vectors/skill_normsq entry per card, summed from the card's matched words."""
    word_vectors = {"turnstile": (1, 0), "gate": (0, 1), "release": (-1, 0)}
    cards = {
        "urn:skill:acme:_root:turnstile-guide": make_card(
            "urn:skill:acme:_root:turnstile-guide", "_root",
            description="turnstile gate", digest="turnstile gate", body="turnstile gate",
        ),
        "urn:skill:acme:_root:release-guide": make_card(
            "urn:skill:acme:_root:release-guide", "_root",
            description="release", digest="release", body="release",
        ),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"), word_vectors=word_vectors)
    turnstile_urn = "urn:skill:acme:_root:turnstile-guide"
    release_urn = "urn:skill:acme:_root:release-guide"
    assert idx.skill_vectors[turnstile_urn] != (0, 0)
    assert idx.skill_normsq[turnstile_urn] == sum(x * x for x in idx.skill_vectors[turnstile_urn])
    assert idx.skill_normsq[release_urn] == sum(x * x for x in idx.skill_vectors[release_urn])
