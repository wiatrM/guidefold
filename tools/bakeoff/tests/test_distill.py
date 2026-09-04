"""Tests for distill.py -- the tier-1 static word/skill int8 table.

Uses the real fixture corpus and the real (already-pinned, already-downloaded) teacher model,
so these tests exercise the actual pipeline end to end, not a mock of it. On a machine with a
warm `.bakeoff-cache/`, a full run completes in well under a second; cold, it pays the one-time
cost of encoding ~2.2k vocabulary words with the teacher (a couple of minutes on 16 CPU cores --
see tools/bakeoff/README.md for measured numbers).
"""
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import distill  # noqa: E402
from corpus import load_corpus  # noqa: E402

TEACHER_ID = "pipizhao/SkillRouter-Embedding-0.6B"
TEACHER_REVISION = "c03c9bcee9fce92ab0262bb6dcf54d174a8ba558"
BUILD_ROOT = Path(__file__).resolve().parent.parent / "build" / "_pytest"


def _run(out_dir: Path, dims: int = 64) -> dict:
    corpus = load_corpus()
    return distill.distill(corpus, TEACHER_ID, TEACHER_REVISION, out_dir, dims=dims)


def test_rerun_is_byte_identical():
    """The core determinism requirement: two independent runs of distill() over the same corpus
    and teacher must produce bit-for-bit identical words.bin and vectors.i8 (fixed PCA sign
    convention, single-threaded deterministic SVD, sorted-URN / alphabetical-word ordering --
    see the comments in distill.py's _pca() and build_vocabulary())."""
    out_a = BUILD_ROOT / "rerun_a"
    out_b = BUILD_ROOT / "rerun_b"
    shutil.rmtree(out_a, ignore_errors=True)
    shutil.rmtree(out_b, ignore_errors=True)
    try:
        result_a = _run(out_a)
        result_b = _run(out_b)
        words_a = result_a["words_bin"].read_bytes()
        words_b = result_b["words_bin"].read_bytes()
        vectors_a = result_a["vectors_i8"].read_bytes()
        vectors_b = result_b["vectors_i8"].read_bytes()
        assert words_a == words_b, "words.bin differs between two runs over the same inputs"
        assert vectors_a == vectors_b, "vectors.i8 differs between two runs over the same inputs"
    finally:
        shutil.rmtree(out_a, ignore_errors=True)
        shutil.rmtree(out_b, ignore_errors=True)


def test_words_bin_and_vectors_i8_round_trip():
    """words.bin and vectors.i8 no longer share a scale (coordinator-review correction: skill
    vectors are now L2-normalised per document before quantising, see
    distill.quantize_skill_vectors()) -- each file's `scale` field is internally consistent with
    its own contents instead."""
    out_dir = BUILD_ROOT / "roundtrip"
    shutil.rmtree(out_dir, ignore_errors=True)
    try:
        result = _run(out_dir)
        words = distill.read_words_bin(result["words_bin"])
        vectors = distill.read_vectors_i8(result["vectors_i8"])
        manifest = result["manifest"]

        # words.bin's scale is still the word-table-derived scale from the manifest (packed
        # through struct "f" / float32, so only float32-precision-close to the float64 Python
        # value in the manifest, not bit-identical to it).
        assert abs(words["scale"] - manifest["quantization_scale"]) < 1e-6
        # vectors.i8's scale is the fixed per-document-normalisation constant 1/127 -- also
        # struct-packed through float32, and (verified empirically, not assumed) 1/127 does
        # NOT round-trip losslessly at float32 width: the packed value differs from the
        # float64 Python constant by ~2.9e-11, well under any ranking-relevant tolerance but
        # not bit-identical, so this is a tolerance comparison like the word-table scale above.
        assert abs(vectors["scale"] - manifest["skill_vector_int8_scale"]) < 1e-9
        assert abs(vectors["scale"] - (1.0 / 127.0)) < 1e-6

        assert words["table"].shape == (manifest["vocab_size"], manifest["dims"])
        assert vectors["table"].shape == (manifest["n_skills"], manifest["dims"])
        assert len(vectors["urns"]) == manifest["n_skills"]
        assert vectors["urns"] == sorted(vectors["urns"])  # doc order = sorted URN
        # |d|^2 recorded per skill must equal the actual sum of squares of its int8 row.
        recomputed_d2 = (vectors["table"].astype(np.int64) ** 2).sum(axis=1)
        assert np.array_equal(vectors["d2"].astype(np.int64), recomputed_d2)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_scale_is_derived_from_word_table_alone():
    """The word-table scale is fixed from max(|word_table_f32|)/127 -- NOT from the (much
    larger-magnitude) skill sums -- so that individual word vectors stay usably non-zero after
    quantisation. See the comment above the scale computation in distill.distill()."""
    out_dir = BUILD_ROOT / "scale_check"
    shutil.rmtree(out_dir, ignore_errors=True)
    try:
        corpus = load_corpus()
        vocab = distill.build_vocabulary(corpus)
        word_table_f32 = distill.build_word_table(vocab, TEACHER_ID, TEACHER_REVISION, dims=64)
        expected_scale = float(np.abs(word_table_f32).max()) / 127.0

        result = _run(out_dir, dims=64)
        assert abs(result["manifest"]["quantization_scale"] - expected_scale) < 1e-9

        # With the scale derived from the word table, every vocabulary word should keep a
        # non-zero int8 vector -- the whole point of the fix -- with exactly one, coordinator-
        # review-intended exception: rank 0 (the single most frequent word, "the" in this
        # fixture) has corrected Zipf weight log(1 + 0) == 0 by design (see zipf_weight()), so
        # its raw float32 row is an exact all-zero vector before quantisation ever runs -- not
        # a quantisation artifact, and not something a wider scale could fix.
        words = distill.read_words_bin(result["words_bin"])
        nonzero = (np.abs(words["table"].astype(np.int64)).sum(axis=1) > 0).sum()
        rank0_words = [w for w, r in vocab.rank_of.items() if r == 0]
        assert len(rank0_words) == 1
        assert nonzero == words["table"].shape[0] - 1
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_skill_vectors_are_l2_normalised_before_quantising_so_clip_rate_is_zero():
    """Coordinator-review correction: each skill's raw float32 sum is L2-normalised to unit
    length before quantising, instead of reusing the word table's scale. By Cauchy-Schwarz every
    component of a unit-L2-norm vector has |value| <= 1, so `unit * 127` can never exceed the
    int8 range -- the measured clip rate must be exactly 0.0, not just "low", and every skill's
    int8 row should actually use a meaningful fraction of the int8 range (not saturate)."""
    out_dir = BUILD_ROOT / "skill_norm_check"
    shutil.rmtree(out_dir, ignore_errors=True)
    try:
        result = _run(out_dir)
        assert result["manifest"]["skill_vector_clip_rate"] == 0.0

        vectors = distill.read_vectors_i8(result["vectors_i8"])
        # Every skill vector should be non-zero (this fixture has no all-OOV skill).
        row_abs_sum = np.abs(vectors["table"].astype(np.int64)).sum(axis=1)
        assert (row_abs_sum > 0).all()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_quantize_skill_vectors_matches_manual_l2_normalise_then_scale():
    rng_input = np.array(
        [
            [3.0, 4.0, 0.0, 0.0],   # norm 5 -> unit (0.6, 0.8, 0, 0) -> *127 -> (76.2, 101.6, 0, 0)
            [0.0, 0.0, 0.0, 0.0],   # all-zero (all-OOV skill) -> guarded, stays all-zero
            [1.0, 1.0, 1.0, 1.0],   # norm 2 -> unit 0.5 each -> *127 -> 63.5 each
        ],
        dtype=np.float32,
    )
    table_i8, d2, clip_rate = distill.quantize_skill_vectors(rng_input)
    assert clip_rate == 0.0
    assert table_i8[0].tolist() == [76, 102, 0, 0]  # round(76.2)=76, round(101.6)=102
    assert table_i8[1].tolist() == [0, 0, 0, 0]
    assert table_i8[2].tolist() == [64, 64, 64, 64]  # round-half-to-even: round(63.5) == 64
    assert np.array_equal(d2, (table_i8.astype(np.int64) ** 2).sum(axis=1).astype(np.uint32))


def test_zipf_weight_is_zero_at_rank_zero_and_increases_with_rarity():
    """Corrected formula: log(1 + rank), rank 0-indexed, 0 = most frequent. rank 0 contributes
    exactly zero weight; weight strictly increases with rank (rarer words weighted more), the
    opposite direction from the inverted phase-1 formula `1 / log(1 + rank)` (1-indexed)."""
    assert distill.zipf_weight(0) == 0.0
    weights = [distill.zipf_weight(r) for r in (0, 1, 100, 2000)]
    assert weights == sorted(weights)
    assert len(set(weights)) == len(weights)  # strictly increasing, no ties


def test_vocabulary_rank_of_is_zero_indexed_with_most_frequent_word_at_rank_zero():
    corpus = load_corpus()
    vocab = distill.build_vocabulary(corpus)
    # Recompute the same tie-break the production code uses (-count, word) to find the true
    # rank-0 word, then assert it independently.
    ranked = sorted(vocab.words, key=lambda w: (-vocab.counts[w], w))
    assert vocab.rank_of[ranked[0]] == 0
    assert min(vocab.rank_of.values()) == 0
    assert max(vocab.rank_of.values()) == len(vocab.words) - 1


def test_int8_round_trip_error_is_bounded_by_half_scale():
    """Round-to-nearest int8 quantisation of an UNCLIPPED value has error <= scale/2 by
    construction (`np.round`). This is the documented error bound consumers of words.bin /
    vectors.i8 can rely on for any value that did not saturate at +/-127."""
    scale = 0.0123
    # A representative, fixed (non-random -> no test flakiness) sweep across the representable
    # range, deliberately excluding the +/-127 boundary itself (which the clipping test below
    # covers separately).
    values = np.linspace(-126.9, 126.9, 4001, dtype=np.float64) * scale
    quantized = distill.quantize_int8(values, scale)
    dequantized = quantized.astype(np.float64) * scale
    max_error = np.abs(values - dequantized).max()
    assert max_error <= scale / 2 + 1e-12


def test_int8_quantization_clips_out_of_range_values_to_the_boundary():
    scale = 0.01
    values = np.array([-1000.0, -127.0, 0.0, 127.0, 1000.0]) * scale
    quantized = distill.quantize_int8(values, scale)
    assert quantized.tolist() == [-127, -127, 0, 127, 127]
