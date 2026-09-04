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


def test_words_bin_and_vectors_i8_round_trip_and_share_scale():
    out_dir = BUILD_ROOT / "roundtrip"
    shutil.rmtree(out_dir, ignore_errors=True)
    try:
        result = _run(out_dir)
        words = distill.read_words_bin(result["words_bin"])
        vectors = distill.read_vectors_i8(result["vectors_i8"])
        manifest = result["manifest"]

        # Both files pack the *same* Python float `scale` through the *same* struct "f"
        # (little-endian float32) field, so their on-disk scales must match exactly bit for bit.
        # The higher-precision Python float in manifest["quantization_scale"] (float64, as
        # computed and before any struct packing) is only guaranteed to match to float32
        # precision, not exactly -- struct.pack("<f", ...) is a real, lossy narrowing.
        assert words["scale"] == vectors["scale"]
        assert abs(words["scale"] - manifest["quantization_scale"]) < 1e-6
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
    """The scale is fixed from max(|word_table_f32|)/127 -- NOT from the (much larger-magnitude)
    skill sums -- so that individual word vectors stay usably non-zero after quantisation. See
    the long comment above the scale computation in distill.distill() for the full rationale and
    tools/bakeoff/README.md's "Known limitation" section for what this trades away."""
    out_dir = BUILD_ROOT / "scale_check"
    shutil.rmtree(out_dir, ignore_errors=True)
    try:
        corpus = load_corpus()
        vocab = distill.build_vocabulary(corpus)
        word_table_f32 = distill.build_word_table(vocab, TEACHER_ID, TEACHER_REVISION, dims=64)
        expected_scale = float(np.abs(word_table_f32).max()) / 127.0

        result = _run(out_dir, dims=64)
        assert abs(result["manifest"]["quantization_scale"] - expected_scale) < 1e-9

        # With the scale derived from the word table, essentially every vocabulary word should
        # keep a non-zero int8 vector (this fixture: 2257/2257) -- the whole point of the fix.
        words = distill.read_words_bin(result["words_bin"])
        nonzero = (np.abs(words["table"].astype(np.int64)).sum(axis=1) > 0).sum()
        assert nonzero == words["table"].shape[0]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


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
