"""Native exact-comparator parity. Explicit startup compilation; no GPU/model."""
import copy
import ctypes
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.serve_spike.native_rank import (
    BOUND, DEFAULT_BUILD_DIR, NativeDenseRank, install_native_dense_rank, prepare_native_rank,
)
from tools.serve_spike.sparse_cache import install_bm25_cache
from _router_helpers import make_card, make_nodes


@pytest.fixture(scope="module")
def prepared():
    return prepare_native_rank()


def test_prepare_records_source_compiler_library_identity_and_reuses(prepared):
    for key in ("source_sha256", "compiler_sha256", "library_sha256", "build_identity_sha256"):
        assert len(prepared[key]) == 64
    assert Path(prepared["library_path"]).parent == DEFAULT_BUILD_DIR
    again = prepare_native_rank()
    assert again["build_reused"]
    assert again["library_sha256"] == prepared["library_sha256"]
    assert again["library_path"] == prepared["library_path"]


def test_exact_random_sign_tie_and_boundary_parity(gf, prepared):
    adapter = NativeDenseRank(gf._dense_rank, prepared)
    tie_scores = {
        "positive-small": (1, 1), "positive-large": (2, 4),
        "negative-small": (-1, 1), "negative-large": (-2, 4),
        "zero-z": (0, 3), "zero-a": (0, 19), "żółć": (1, 1),
        "upper": (BOUND, BOUND), "lower": (-BOUND, BOUND),
    }
    assert adapter.rank(tie_scores) == gf._dense_rank(tie_scores)
    rng = random.Random(92841)
    for _ in range(100):
        scores = {f"urn:{i:04d}": (rng.randint(-BOUND, BOUND), rng.randint(1, BOUND))
                  for i in range(rng.randrange(2, 90))}
        # Insertion order must not affect exact tie order.
        scores = dict(reversed(list(scores.items())))
        assert adapter.rank(scores) == gf._dense_rank(scores)
    assert adapter.rank({}) == []
    assert adapter.metadata["native_calls"] == 101
    assert adapter.metadata["empty_calls"] == 1
    assert adapter.metadata["fallback_calls"] == 0


@pytest.mark.parametrize("value, reason", [
    ((BOUND + 1, 1), "numeric_bounds"),
    ((-(BOUND + 1), 1), "numeric_bounds"),
    ((1, BOUND + 1), "numeric_bounds"),
    ((1, 0), "numeric_bounds"),
    ((1, -1), "numeric_bounds"),
    ((10**200, 10**200), "numeric_bounds"),
    ((True, 1), "unsupported_values"),
    ((1.25, 2), "unsupported_values"),
])
def test_extreme_or_unsupported_values_use_original(gf, prepared, value, reason):
    calls = []

    def reference(scores):
        calls.append(scores)
        return gf._dense_rank(scores)

    adapter = NativeDenseRank(reference, prepared)
    scores = {"u:odd": value, "u:normal": (1, 2)}
    assert adapter.rank(scores) == gf._dense_rank(scores)
    assert calls == [scores]
    assert adapter.metadata["fallback_calls"] == 1
    assert adapter.metadata["fallback_reasons"][reason] == 1
    assert adapter.metadata["native_calls"] == 0


def test_cpp_rejects_invalid_bounds_even_without_python_guard(gf, prepared):
    adapter = NativeDenseRank(gf._dense_rank, prepared)
    output = (ctypes.c_size_t * 1)()
    for dot, norm in ((BOUND + 1, 1), (-(1 << 63), 1), (1, 0), (1, -1), (1, BOUND + 1)):
        dots, norms = (ctypes.c_int64 * 1)(dot), (ctypes.c_int64 * 1)(norm)
        assert adapter.kernel(dots, norms, 1, output) == 2


def test_full_pipeline_cross_ranks_and_instance_isolation(gf, prepared):
    cards = {f"u:{i:02d}": make_card(f"u:{i:02d}", "_root",
        description=" ".join(["needle"] * (20-i) + ["filler"] * i),
        body="context", requires=["u:01"] if i == 19 else [])
        for i in range(20)}
    idx = gf.Index.from_cards(cards, make_nodes("_root"),
                              weights={"w_dense": 1, "ppr_mode": "closure"})

    class DenseRouter(gf.Router):
        def _dense_scores(self, query, visible):
            return {u: (900 if u == "u:19" else i - 7, i + 1)
                    for i, u in enumerate(sorted(visible))}

    baseline, optimized = DenseRouter(idx), DenseRouter(idx)
    original_global = gf._dense_rank
    original_function = baseline.candidates.__func__
    install_bm25_cache(optimized)
    metadata = install_native_dense_rank(optimized, prepared)

    def pipeline(router, query, top_n):
        admissible, drops = router.policy_filter("_root", query)
        candidates = router.candidates(query, "_root", top_n=top_n)
        scored = router.score(candidates, query, "_root")
        selected = router.select(scored, k=4, admissible=set(admissible))
        return drops, candidates, scored, selected

    for top_n in (1, 2, 7, 50):
        for query in ("needle needle", "context filler", "unknown", ""):
            assert pipeline(optimized, query, top_n) == pipeline(baseline, query, top_n)
    cross = next(c for c in baseline.candidates("needle", "_root", top_n=2) if c["urn"] == "u:19")
    assert cross["dense_rank"] == 1 and cross["bm25_rank"] > 2
    assert gf._dense_rank is original_global
    assert baseline.candidates.__func__ is original_function
    assert optimized.candidates.__func__ is not original_function
    assert original_function.__globals__["_dense_rank"] is original_global
    assert metadata["native_calls"] == 16
    assert metadata["fallback_calls"] == 0
    assert optimized.native_rank_metadata is metadata
    with pytest.raises(ValueError, match="already installed"):
        install_native_dense_rank(optimized, prepared)


def test_missing_compiler_and_tampered_library_identity_fail_before_install(gf, prepared):
    with pytest.raises(RuntimeError, match="compiler_unavailable"):
        prepare_native_rank(compiler="/definitely/not/a/compiler")
    tampered = copy.deepcopy(prepared)
    tampered["library_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest_mismatch"):
        NativeDenseRank(gf._dense_rank, tampered)