"""Tests for arms.py -- the E1.3 bake-off retrieval arms.

Every arm is exercised against the real fixture corpus with the real, pinned, already-downloaded
models (no mocking): the point of a bake-off harness is to prove each arm actually runs and
returns sane output, not just that its Python is syntactically valid. On a machine with a warm
`.bakeoff-cache/`, the whole module runs in well under a minute; B3b (ThakiCloud/SKILLRET-
Embedding-0.6B, cold) and B6 (the reranker, always uncached by design) are the two genuinely slow
arms on CPU -- see tools/bakeoff/README.md's measured timings.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arms  # noqa: E402
from corpus import load_corpus  # noqa: E402

QUERY = "add RBAC to this new admin-only endpoint"


def _corpus_and_valid_urns():
    corpus = load_corpus()
    return corpus, {r.urn for r in corpus}


def test_every_arm_returns_valid_deduplicated_urns():
    corpus, valid_urns = _corpus_and_valid_urns()
    for name, arm in arms.ARMS.items():
        ranked = arm(QUERY, corpus)
        assert ranked, f"{name} returned an empty ranking for a query that should match something"
        assert len(ranked) == len(set(ranked)), f"{name} returned duplicate URNs: {ranked}"
        unknown = [u for u in ranked if u not in valid_urns]
        assert not unknown, f"{name} returned URNs not in the fixture corpus: {unknown}"


def test_b0_matches_cli_rank_cards_directly():
    """B0 must be a call-through to the shipped CLI's own rank_cards(), not a reimplementation."""
    from corpus import cli

    corpus, _ = _corpus_and_valid_urns()
    cfg = cli.load_map(arms.FIXTURE_ROOT)
    reg = cli.registry_for(cfg, arms.FIXTURE_ROOT)
    expected_cards = cli.rank_cards(reg, arms.DEFAULT_NODE, QUERY, arms.DEFAULT_LIMIT)
    expected = []
    seen = set()
    for c in expected_cards:
        if c["urn"] not in seen:
            seen.add(c["urn"])
            expected.append(c["urn"])
    assert arms.arm_b0(QUERY, corpus) == expected


def test_b1_ranks_the_lexically_obvious_skill_first():
    corpus, _ = _corpus_and_valid_urns()
    ranked = arms.arm_b1(QUERY, corpus)
    assert ranked[0] == "urn:skill:meridian:atlas.identity:rbac-policies"


def test_b4_is_deterministic_across_two_runs():
    corpus, _ = _corpus_and_valid_urns()
    first = arms.arm_b4(QUERY, corpus)
    second = arms.arm_b4(QUERY, corpus)
    assert first == second


def test_b5_is_deterministic_across_two_runs():
    corpus, _ = _corpus_and_valid_urns()
    first = arms.arm_b5(QUERY, corpus)
    second = arms.arm_b5(QUERY, corpus)
    assert first == second


def test_b5_fuses_b1_and_b4_via_rrf_not_a_reimplementation():
    corpus, _ = _corpus_and_valid_urns()
    b1 = arms.arm_b1(QUERY, corpus, limit=arms.DEFAULT_LIMIT)
    b4 = arms.arm_b4(QUERY, corpus, limit=arms.DEFAULT_LIMIT)
    expected_scores = arms._rrf_fuse(b1, b4)
    expected_order = sorted(expected_scores, key=lambda u: (-expected_scores[u], u))
    assert arms.arm_b5(QUERY, corpus) == expected_order


def test_bm25_index_field_weights_favor_name_matches():
    """A query that is exactly one skill's name should score that skill above a skill that only
    mentions the term once in its body -- field-weighted BM25's whole point (name x3 vs body x1)."""
    corpus, _ = _corpus_and_valid_urns()
    by_urn = {r.urn: r for r in corpus}
    target = by_urn["urn:skill:meridian:atlas.identity:rbac-policies"]
    idx = arms._bm25_index(corpus)
    scores = idx.scores(["rbac", "policies"])
    target_idx = [i for i, r in enumerate(corpus) if r.urn == target.urn][0]
    assert scores[target_idx] == max(scores)
