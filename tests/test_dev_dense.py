"""Tests for tools/eval/dev_dense.py — family E's dev-split dense-arm runner (DENSE-PROGRAM.md
v2.6). Pure logic only: cache-key naming, the summary aggregation, the resumable-checkpoint
encoder wrapper (against a fake, GPU-free encoder), and — the one property this whole family's
"primary metric" claim rests on — that `all_required@4` is computed from `injected`
(select()'s real output) while hit@1/nDCG@10/recall@10 are computed from `ranked` (raw retrieval
order), never the other way around. `cmd_encode`/`cmd_run`/`cmd_latency` need the GPU venv and the
real SKILLRET corpus and are exercised manually (see docs/reports/bakeoff/DEV-E-synthetic-training-
*.md for that transcript), not here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO_ROOT / "tools" / "eval"
sys.path.insert(0, str(EVAL_DIR))

import dev_dense  # tools/eval/dev_dense.py -- itself inserts EVAL_DIR onto sys.path


# --------------------------------------------------------------------------- torch-free module boundary
def test_dev_dense_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """encode/latency are the only subcommands that need torch/transformers/sentence-transformers,
    and they reach them only inside Encoder._ensure_loaded/.encode (function/method-scoped),
    never at module scope — so importing dev_dense (and, transitively, corpora/dense_ref/
    dev_sparse) must succeed even with torch poisoned. Same technique as
    tests/test_skillretbench_r1.py's own torch-boundary test."""
    monkeypatch.setitem(sys.modules, "torch", None)
    import importlib
    import importlib.util
    from importlib.machinery import SourceFileLoader

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("torch must not be imported at dev_dense module scope")
            return None

    blocker = _TorchIsForbidden()
    sys.meta_path.insert(0, blocker)
    try:
        loader = SourceFileLoader("dev_dense_torch_check", str(EVAL_DIR / "dev_dense.py"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        assert hasattr(module, "Encoder")
    finally:
        sys.meta_path.remove(blocker)


# --------------------------------------------------------------------------- naming
def test_slug_identity_strips_unsafe_characters():
    assert dev_dense._slug_identity("E1: per-skill (v1)") == "E1-per-skill-v1"


def test_cache_dir_for_is_keyed_by_identity_not_source():
    a = dev_dense.cache_dir_for("E0")
    b = dev_dense.cache_dir_for("E1")
    assert a != b
    assert a.name == "E0" and b.name == "E1"


def test_default_query_prompt_known_and_unknown_sources():
    assert "skill search query" in dev_dense._default_query_prompt("ThakiCloud/SKILLRET-Embedding-0.6B")
    assert dev_dense._default_query_prompt("some/unlisted-model") is None


# --------------------------------------------------------------------------- _summarize
def _case(id_, k, urn, grade=3):
    return {"id": id_, "query": "q", "node": "_root", "k": k,
            "relevant": [{"urn": urn, "grade": grade}], "distractors": []}


def test_summarize_overall_and_per_k_means():
    cases = [_case("q1", 1, "urn:a"), _case("q2", 1, "urn:b"), _case("q3", 2, "urn:c")]
    per_q = {
        "q1": {"hit1": 1.0, "ndcg10": 1.0, "recall10": 1.0, "all_required4": 1.0,
               "ceiling4": 1.0, "ceiling10": 1.0, "ceiling15": 1.0, "ceiling50": 1.0},
        "q2": {"hit1": 0.0, "ndcg10": 0.0, "recall10": 0.0, "all_required4": 0.0,
               "ceiling4": 0.0, "ceiling10": 1.0, "ceiling15": 1.0, "ceiling50": 1.0},
        "q3": {"hit1": 1.0, "ndcg10": 0.5, "recall10": 0.5, "all_required4": 0.0,
               "ceiling4": 0.0, "ceiling10": 0.0, "ceiling15": 1.0, "ceiling50": 1.0},
    }
    out = dev_dense._summarize(per_q, cases)
    assert out["overall"]["n"] == 3
    assert out["overall"]["hit1"] == pytest.approx(2 / 3)
    assert out["k=1"]["n"] == 2
    assert out["k=1"]["hit1"] == pytest.approx(0.5)
    assert out["k=2"]["n"] == 1
    assert out["k=2"]["all_required4"] == 0.0
    assert out["overall"]["ceiling4"] == pytest.approx(1 / 3)
    assert out["overall"]["ceiling50"] == pytest.approx(1.0)


def test_summarize_skips_nan_in_means_not_zeros():
    cases = [_case("q1", 1, "urn:a")]
    per_q = {"q1": {"hit1": float("nan"), "ndcg10": 0.0, "recall10": 0.0, "all_required4": 0.0,
                    "ceiling4": 0.0, "ceiling10": 0.0, "ceiling15": 0.0, "ceiling50": 0.0}}
    out = dev_dense._summarize(per_q, cases)
    assert dev_dense._isnan(out["overall"]["hit1"])  # all values NaN -> mean stays NaN, not 0
    assert out["overall"]["ndcg10"] == 0.0


# --------------------------------------------------------------------------- resumable_encode
class _FakeEncoder:
    """Deterministic, GPU-free stand-in: encode(chunk) -> one row per text, value = hash-derived
    from the text so equality checks are meaningful without any real model."""

    def __init__(self, fail_after_chunks=None):
        self.calls = []
        self.fail_after_chunks = fail_after_chunks
        self._n_calls = 0

    def encode(self, texts, is_query=False):
        import numpy as np
        self._n_calls += 1
        self.calls.append(list(texts))
        if self.fail_after_chunks is not None and self._n_calls > self.fail_after_chunks:
            raise RuntimeError("simulated crash mid-run")
        return np.asarray([[float(len(t)), float(is_query)] for t in texts], dtype=np.float32)


def test_resumable_encode_matches_plain_chunking_with_no_checkpoint(tmp_path):
    import numpy as np
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    enc = _FakeEncoder()
    out = dev_dense.resumable_encode(enc, texts, is_query=False, chunk_size=2, label="t",
                                      checkpoint_path=tmp_path / "ckpt.npy")
    expected = np.asarray([[float(len(t)), 0.0] for t in texts], dtype=np.float32)
    assert np.array_equal(out, expected)
    assert enc._n_calls == 3  # ceil(5/2)


def test_resumable_encode_resumes_after_simulated_crash(tmp_path):
    import numpy as np
    texts = ["a", "bb", "ccc", "dddd", "eeeee", "ffffff"]
    ckpt = tmp_path / "ckpt.npy"

    crashy = _FakeEncoder(fail_after_chunks=1)  # succeeds on chunk 1, raises on chunk 2
    with pytest.raises(RuntimeError):
        dev_dense.resumable_encode(crashy, texts, is_query=False, chunk_size=2, label="t",
                                    checkpoint_path=ckpt)
    assert ckpt.exists()
    done_meta = json.loads(Path(str(ckpt) + ".done.json").read_text())
    assert done_meta["n_done"] == 2  # only the first chunk committed

    healthy = _FakeEncoder()
    out = dev_dense.resumable_encode(healthy, texts, is_query=False, chunk_size=2, label="t",
                                      checkpoint_path=ckpt)
    # the resumed run must not re-encode the first (already-checkpointed) chunk
    assert healthy.calls == [["ccc", "dddd"], ["eeeee", "ffffff"]]
    expected = np.asarray([[float(len(t)), 0.0] for t in texts], dtype=np.float32)
    assert np.array_equal(out, expected)


def test_resumable_encode_ignores_stale_checkpoint_for_a_different_text_count(tmp_path):
    """A checkpoint recorded against a different `total` (e.g. the corpus grew) must never be
    silently reused — `total` mismatch means start over, not corrupt-resume."""
    import numpy as np
    ckpt = tmp_path / "ckpt.npy"
    first = _FakeEncoder()
    dev_dense.resumable_encode(first, ["a", "bb"], is_query=False, chunk_size=2, label="t",
                                checkpoint_path=ckpt)
    second = _FakeEncoder()
    out = dev_dense.resumable_encode(second, ["a", "bb", "ccc"], is_query=False, chunk_size=2,
                                      label="t", checkpoint_path=ckpt)
    assert second.calls == [["a", "bb"], ["ccc"]]  # started fresh, did not trust the stale checkpoint
    expected = np.asarray([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]], dtype=np.float32)
    assert np.array_equal(out, expected)


# --------------------------------------------------------------------------- retrieval-vs-injection (the load-bearing property)
def test_records_to_per_q_computes_all_required_from_injected_not_ranked(monkeypatch):
    """The one property the whole family's "primary metric" report line depends on: hit@1/nDCG@10/
    recall@10 read `ranked` (raw retrieval order); all_required@4 reads `injected` (the actual
    select() output). A record where the two disagree must show it."""
    cases = [{
        "id": "q1", "query": "x", "node": "_root", "k": 1,
        "relevant": [{"urn": "urn:a", "grade": 3}], "distractors": [],
    }]
    monkeypatch.setitem(dev_dense._DEV_CACHE, "cards", ({}, {}, {}, cases, {}, {}))
    records = [{
        "query_id": "q1", "k": 1,
        "ranked": ["urn:a", "urn:zzz"],   # gold is rank 1 in raw retrieval
        "injected": ["urn:zzz"],          # but select() dropped it (e.g. abstention/closure)
    }]
    per_q, k_by_id = dev_dense._records_to_per_q(records)
    assert per_q["q1"]["hit1"] == 1.0          # from `ranked`: gold IS rank 1
    assert per_q["q1"]["all_required4"] == 0.0  # from `injected`: gold is NOT in what shipped
    assert k_by_id["q1"] == 1


def test_records_to_per_q_skips_records_with_no_matching_case(monkeypatch):
    cases = [{"id": "q1", "query": "x", "node": "_root", "k": 1,
              "relevant": [{"urn": "urn:a", "grade": 3}], "distractors": []}]
    monkeypatch.setitem(dev_dense._DEV_CACHE, "cards", ({}, {}, {}, cases, {}, {}))
    records = [{"query_id": "unknown-qid", "k": 1, "ranked": [], "injected": []}]
    per_q, k_by_id = dev_dense._records_to_per_q(records)
    assert per_q == {}
    assert k_by_id == {}


# --------------------------------------------------------------------------- dense-only ("pure dense") mode
# DENSE-PROGRAM.md v2.6 family E addendum (2026-09-05): every model must also be measured with
# candidates/scores sourced from the dense channel EXCLUSIVELY (w_sparse=0), not merely with
# lexical field weights zeroed -- Router._bm25_scores/candidates()'s bm25_order[:top_n] union would
# still admit lexically-matching URNs into the pool at weight 0. These tests use the real,
# dynamically-loaded guidefold CLI module (same pattern as tests/test_skillret_eval.py's `cli`
# fixture) against tiny synthetic cards, never the real SKILLRET/dev corpus.
import dev_sparse  # tools/eval/dev_sparse.py -- already on sys.path via EVAL_DIR insert above
from _router_helpers import make_card, make_nodes


@pytest.fixture(scope="module")
def cli():
    return dev_sparse._load_cli()


def test_make_dense_only_router_class_candidates_never_carry_a_bm25_rank(cli):
    np = pytest.importorskip("numpy")
    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    cards = {urn_a: make_card(urn_a, "a", description="alpha beta")}
    row_of = {urn_a: 0}
    skill_mat = np.array([[1, 0]], dtype=np.int8)
    query_vec_of = {"q1": np.array([1, 0], dtype=np.int8)}

    idx, router = dev_dense.build_dense_only_index_and_router(
        cli, cards, nodes, row_of, skill_mat, query_vec_of)
    router._current_qid = "q1"
    cands = router.candidates("alpha", "a", top_n=50)
    assert len(cands) == 1
    assert cands[0]["urn"] == urn_a
    assert cands[0]["bm25_rank"] is None
    assert cands[0]["dense_rank"] == 1

    scored = router.score(cands, "alpha", "a")
    # score() adds w_scope/w_ppr structural bonuses on top of RRF -- with a single candidate and
    # bm25_rank=None throughout, the RRF term can only ever come from dense_rank.
    assert scored[0]["score"] > 0


def test_dense_only_candidate_pool_excludes_lexical_matches_outside_dense_top_n(cli):
    """The load-bearing property: a card that matches the query lexically (would enter a hybrid
    pool's bm25_order[:top_n] at score 0) but ranks outside the dense channel's top_n must NOT
    appear in the dense-only candidate pool at all."""
    np = pytest.importorskip("numpy")
    nodes = make_nodes("a")
    urn_lex = "urn:skill:skillret:a:lexical-match"   # shares the term "alpha" with the query
    urn_dense = "urn:skill:skillret:a:dense-match"   # no lexical overlap, but dense-closest
    cards = {
        urn_lex: make_card(urn_lex, "a", description="alpha beta"),
        urn_dense: make_card(urn_dense, "a", description="gamma delta"),
    }
    row_of = {urn_lex: 0, urn_dense: 1}
    skill_mat = np.array([[1, 0], [0, 1]], dtype=np.int8)
    query_vec_of = {"q1": np.array([0, 1], dtype=np.int8)}  # dot=0 vs urn_lex, dot=1 vs urn_dense

    idx, router = dev_dense.build_dense_only_index_and_router(
        cli, cards, nodes, row_of, skill_mat, query_vec_of)
    router._current_qid = "q1"

    # sanity: the base BM25 channel really does see urn_lex as a match (the thing a naive
    # "just zero field.* weights" approach would still leak into a hybrid pool)
    bm25 = router._bm25_scores("alpha", {urn_lex, urn_dense})
    assert urn_lex in bm25

    cands = router.candidates("alpha", "a", top_n=1)
    urns = {c["urn"] for c in cands}
    assert urns == {urn_dense}       # dense top-1 only -- the lexical-only match never leaks in
    assert all(c["bm25_rank"] is None for c in cands)


def test_dense_only_candidates_empty_when_query_has_no_cached_vector(cli):
    """Unlike hybrid mode (which falls back to the bm25-only pool), dense-only mode has no lexical
    fallback by construction: a query with no cached embedding yields zero candidates for that
    query, not a bm25-only pool. Worth asserting explicitly since it changes how a missing-encode
    row shows up in the dev table (all_required@4 == 0 for that query, not "silently hybrid")."""
    np = pytest.importorskip("numpy")
    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    cards = {urn_a: make_card(urn_a, "a", description="alpha beta")}
    row_of = {urn_a: 0}
    skill_mat = np.array([[1, 0]], dtype=np.int8)
    query_vec_of = {}  # no cached vector for any qid

    idx, router = dev_dense.build_dense_only_index_and_router(
        cli, cards, nodes, row_of, skill_mat, query_vec_of)
    router._current_qid = "qid-not-cached"
    assert router.candidates("alpha", "a", top_n=50) == []


def test_build_dense_only_index_and_router_raises_on_missing_embedding(cli):
    np = pytest.importorskip("numpy")
    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    urn_b = "urn:skill:skillret:a:two"
    cards = {
        urn_a: make_card(urn_a, "a", description="alpha"),
        urn_b: make_card(urn_b, "a", description="beta"),
    }
    row_of = {urn_a: 0}  # urn_b has no cached row -- must raise, not silently skip it
    skill_mat = np.array([[1, 0]], dtype=np.int8)
    with pytest.raises(SystemExit):
        dev_dense.build_dense_only_index_and_router(cli, cards, nodes, row_of, skill_mat, {})


def test_build_dense_only_index_and_router_leaves_w_scope_and_w_ppr_at_shipped_defaults(cli):
    """'Everything else unchanged' (coordinator addendum): only candidate sourcing changes for
    dense-only mode -- w_scope/w_ppr/abstain_threshold/... stay at Index.DEFAULT_WEIGHTS, same as
    the existing hybrid build_dense_index_and_router. Only w_dense itself differs from R0."""
    np = pytest.importorskip("numpy")
    nodes = make_nodes("a")
    urn_a = "urn:skill:skillret:a:one"
    cards = {urn_a: make_card(urn_a, "a", description="alpha")}
    row_of = {urn_a: 0}
    skill_mat = np.array([[1, 0]], dtype=np.int8)

    idx, router = dev_dense.build_dense_only_index_and_router(cli, cards, nodes, row_of, skill_mat, {})
    for key, val in cli.Index.DEFAULT_WEIGHTS.items():
        if key == "w_dense":
            continue
        assert idx.weights[key] == val, f"{key} was not left at its shipped default"
    assert idx.weights["w_dense"] == 1


def test_run_subcommand_mode_defaults_to_hybrid_and_accepts_dense_only(monkeypatch):
    """Exercises dev_dense.main's REAL argparse tree (not a re-derived copy): patch cmd_run to
    just capture the parsed Namespace instead of touching the GPU venv / real corpus, then confirm
    --mode defaults to "hybrid" and "--mode dense-only" round-trips correctly."""
    seen = []
    monkeypatch.setattr(dev_dense, "cmd_run", lambda args: seen.append(args) or 0)

    dev_dense.main(["run", "--identity", "E0"])
    assert seen[-1].mode == "hybrid"

    dev_dense.main(["run", "--identity", "E0", "--mode", "dense-only"])
    assert seen[-1].mode == "dense-only"

    with pytest.raises(SystemExit):
        dev_dense.main(["run", "--identity", "E0", "--mode", "bogus"])
