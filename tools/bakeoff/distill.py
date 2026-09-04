"""distill.py — the tier-1 static word->int8 table (ROUTER-SPEC-v2.md "Tier 1 — static distilled
embeddings"), model2vec-style.

Pipeline:
  1. Build the corpus vocabulary with `tokenizer.tokenize()` over every field of every fixture
     skill, plus a "common core" of high-document-frequency words *derived from the corpus itself*
     (never a hard-coded stopword list — see `build_vocabulary()`).
  2. Encode each vocabulary word **on its own** with the teacher (`encode.Encoder`).
  3. PCA the teacher's native dimension down to `--dims` (256 by default), with a fixed,
     deterministic sign convention so reruns are byte-stable (`_pca()`).
  4. Zipf-weight every word vector by `1 / log(1 + rank_by_frequency)` (most-frequent word = rank 1).
  5. Quantise to int8 with one global scale, recorded in `words.json`.
  6. Write `words.bin` (word -> id, + the int8 word-vector table) and the `words.json` manifest
     sidecar.
  7. **The single most important rule (ROUTER-SPEC-v2.md, [R]):** `vectors.i8` — the skills'
     own vectors — are built by summing this *same static table*'s word vectors (Zipf weight
     already baked in at step 4) over each skill's concatenated fields, using this *same
     tokenizer*, then requantising the sum to int8 with the *same global scale*. The teacher is
     never called again for this file. Teacher-space documents against student-space queries are
     not comparable (see the spec), so mixing them here would silently corrupt B4/B5.
  8. `teacher.f16` is a **separate, clearly `--experimental`-only** file: the teacher's own
     document embeddings of each skill, encoded directly (this is the shortcut step 7 forbids for
     the shipped file).

Determinism: every source of randomness is removed. Word/scale encodings are disk-cached by
`encode.py`, so a warm-cache rerun never touches the teacher again. PCA uses full (non-randomized)
`numpy.linalg.svd`, which is deterministic for a fixed input matrix; BLAS thread count is pinned to
1 before numpy is imported so summation order cannot vary between runs on the same machine. No
`set`/dict-ordering leaks into any written file: vocabulary ids are alphabetical, skill ids are
sorted by URN.
"""
from __future__ import annotations

import os

# Must happen before numpy/torch import: pin BLAS/LAPACK to one thread so the SVD in `_pca()`
# sums in the same order on every run (ROUTER-SPEC-v2.md: "there is no such thing as a
# bit-identical numpy fast path" once more than one thread is involved).
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import json
import math
import struct
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corpus import SkillRecord, load_corpus  # noqa: E402
from encode import Encoder  # noqa: E402
from tokenizer import tokenize  # noqa: E402

DEFAULT_DIMS = 256
WORDS_MAGIC = b"GFW1"
VECTORS_MAGIC = b"GFV1"
TEACHER_MAGIC = b"GFT1"
BUILD_ROOT = Path(__file__).resolve().parent / "build"


# --------------------------------------------------------------------------------------
# Step 1: vocabulary
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Vocabulary:
    words: list         # id -> word, alphabetical order (deterministic id assignment)
    counts: dict         # word -> total occurrence count across the whole corpus
    doc_freq: dict        # word -> number of skill records containing the word at least once
    rank_of: dict         # word -> 1-indexed frequency rank (1 = most frequent), ties broken alphabetically
    common_core: list    # words whose document frequency clears the corpus-derived threshold


def build_vocabulary(corpus: list, common_core_doc_freq_ratio: float = 0.2) -> Vocabulary:
    """Vocabulary = every word `tokenizer.tokenize()` finds in any field of any fixture skill,
    plus a document-frequency-derived "common core" (function-word-like words used across many
    skills) — never a hard-coded stopword list, per the task's explicit instruction. The common
    core is a subset of `words` (it is discovered from the corpus, not appended from outside);
    it is recorded separately in the manifest as an audit trail, and — because this fixture is
    far under the 15 MB / 2k-skill vocabulary budget (ROUTER-SPEC-v2.md, "Index artifact") — it is
    never pruned out here the way a production build might drop df=1 tail words.
    """
    counts: Counter = Counter()
    doc_freq: Counter = Counter()
    for record in corpus:
        seen_in_this_doc = set()
        for field_text in record.fields_text().values():
            for word in tokenize(field_text):
                counts[word] += 1
                seen_in_this_doc.add(word)
        for word in seen_in_this_doc:
            doc_freq[word] += 1

    words = sorted(counts)  # alphabetical -> deterministic word -> id mapping
    ranked_by_frequency = sorted(words, key=lambda w: (-counts[w], w))
    rank_of = {w: i + 1 for i, w in enumerate(ranked_by_frequency)}

    threshold = max(3, math.ceil(common_core_doc_freq_ratio * len(corpus)))
    common_core = sorted(w for w in words if doc_freq[w] >= threshold)

    return Vocabulary(words=words, counts=dict(counts), doc_freq=dict(doc_freq), rank_of=rank_of,
                       common_core=common_core)


# --------------------------------------------------------------------------------------
# Steps 2-4: encode each word, PCA to `dims`, Zipf-weight
# --------------------------------------------------------------------------------------
def _pca(embeddings: np.ndarray, dims: int) -> np.ndarray:
    """Deterministic PCA via full SVD (not randomized) with a fixed component sign convention:
    for each output dimension, the teacher-space coordinate with the largest magnitude is forced
    positive. Without this, `numpy.linalg.svd` can (and does, across otherwise-identical reruns
    once LAPACK version/thread count differ) return `-component` instead of `component` — a
    numerically valid but non-reproducible flip.
    """
    mean = embeddings.mean(axis=0)
    centered = embeddings - mean
    # full_matrices=False: economy SVD, deterministic for a fixed input on a fixed machine.
    _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:dims]  # (dims, teacher_dim)

    for i in range(components.shape[0]):
        row = components[i]
        peak = np.argmax(np.abs(row))
        if row[peak] < 0:
            components[i] = -row

    return centered @ components.T  # (n_words, dims)


def zipf_weight(rank: int) -> float:
    """1 / log(1 + rank_by_frequency), rank 1 = most frequent word in the corpus."""
    return 1.0 / math.log(1 + rank)


def build_word_table(vocab: Vocabulary, teacher_id: str, teacher_revision: str,
                      dims: int = DEFAULT_DIMS, batch_size: int = 32) -> np.ndarray:
    """Returns the float32, PCA-reduced, Zipf-weighted word table, shape (len(vocab.words), dims).
    This is the *pre-quantisation* table; `quantize_int8()` turns it into what `words.bin` ships.
    """
    encoder = Encoder(teacher_id, teacher_revision, batch_size=batch_size)
    raw = encoder.encode(vocab.words, is_query=False)  # each word encoded on its own (step 2)
    reduced = _pca(raw, dims)  # step 3
    weights = np.array([zipf_weight(vocab.rank_of[w]) for w in vocab.words], dtype=np.float32)
    return (reduced * weights[:, None]).astype(np.float32)  # step 4


# --------------------------------------------------------------------------------------
# Step 5: quantisation
# --------------------------------------------------------------------------------------
def quantize_int8(vectors: np.ndarray, scale: float) -> np.ndarray:
    scaled = np.round(vectors / scale)
    return np.clip(scaled, -127, 127).astype(np.int8)


# --------------------------------------------------------------------------------------
# Step 7: skill vectors from the static table + shared tokenizer — NOT the teacher
# --------------------------------------------------------------------------------------
def build_skill_float_sums(corpus: list, vocab: Vocabulary, word_table_f32: np.ndarray) -> np.ndarray:
    """For each skill (sorted by URN — ROUTER-SPEC-v2.md: "Document ids are assigned in CI by
    sorted URN"), sum the Zipf-weighted word vectors of every token in its concatenated fields,
    counting repeats. OOV words (not in this corpus's own vocabulary — should not happen when the
    corpus IS the vocabulary source, but is possible in general) are skipped: they degrade to the
    BM25 channel, per the spec, rather than being dropped from the sum silently misrepresented.
    """
    id_of = {w: i for i, w in enumerate(vocab.words)}
    dims = word_table_f32.shape[1]
    sums = np.zeros((len(corpus), dims), dtype=np.float32)
    for row, record in enumerate(corpus):
        for word in tokenize(record.concat_text()):
            wid = id_of.get(word)
            if wid is not None:
                sums[row] += word_table_f32[wid]
    return sums


# --------------------------------------------------------------------------------------
# Binary writers
# --------------------------------------------------------------------------------------
def write_words_bin(path: Path, vocab: Vocabulary, table_i8: np.ndarray, scale: float, dims: int) -> None:
    """Header (little-endian, 20 bytes): magic(4s) version(H) dims(H) vocab_size(I) scale(f) words_blob_len(I)
    Then: words_blob (UTF-8, '\\n'-joined, words_blob_len bytes) then vocab_size*dims int8 bytes,
    row-major (row i = the vector for the i-th word in the blob).
    """
    words_blob = "\n".join(vocab.words).encode("utf-8")
    header = struct.pack("<4sHHIfI", WORDS_MAGIC, 1, dims, len(vocab.words), scale, len(words_blob))
    with open(path, "wb") as f:
        f.write(header)
        f.write(words_blob)
        f.write(np.ascontiguousarray(table_i8, dtype="<i1").tobytes())


def write_vectors_i8(path: Path, urns: list, table_i8: np.ndarray, d2: np.ndarray, scale: float, dims: int) -> None:
    """Header (little-endian, 20 bytes): magic(4s) version(H) dims(H) n_skills(I) scale(f) urns_blob_len(I)
    Then: urns_blob (UTF-8, '\\n'-joined) then n_skills*dims int8 bytes (row-major) then n_skills
    uint32 values, one integer |d|^2 per skill, same row order as the int8 table.
    """
    urns_blob = "\n".join(urns).encode("utf-8")
    header = struct.pack("<4sHHIfI", VECTORS_MAGIC, 1, dims, len(urns), scale, len(urns_blob))
    with open(path, "wb") as f:
        f.write(header)
        f.write(urns_blob)
        f.write(np.ascontiguousarray(table_i8, dtype="<i1").tobytes())
        f.write(np.ascontiguousarray(d2, dtype="<u4").tobytes())


def write_teacher_f16(path: Path, urns: list, doc_vectors: np.ndarray) -> None:
    """--experimental only, never read by the hook. Header (little-endian, 16 bytes):
    magic(4s) version(H) dims(H) n_skills(I) urns_blob_len(I). Then urns_blob (UTF-8,
    '\\n'-joined) then n_skills*dims float16 values, row-major.
    """
    urns_blob = "\n".join(urns).encode("utf-8")
    dims = doc_vectors.shape[1]
    header = struct.pack("<4sHHII", TEACHER_MAGIC, 1, dims, len(urns), len(urns_blob))
    with open(path, "wb") as f:
        f.write(header)
        f.write(urns_blob)
        f.write(np.ascontiguousarray(doc_vectors, dtype="<f2").tobytes())


def read_words_bin(path: Path):
    """Inverse of write_words_bin(); used by arms.py (B4/B5) and tests. Pure stdlib + numpy."""
    with open(path, "rb") as f:
        data = f.read()
    magic, version, dims, vocab_size, scale, blob_len = struct.unpack_from("<4sHHIfI", data, 0)
    assert magic == WORDS_MAGIC, f"bad magic in {path}: {magic!r}"
    offset = struct.calcsize("<4sHHIfI")
    words = data[offset:offset + blob_len].decode("utf-8").split("\n")
    offset += blob_len
    table = np.frombuffer(data, dtype="<i1", count=vocab_size * dims, offset=offset).reshape(vocab_size, dims)
    return {"version": version, "dims": dims, "scale": scale, "words": words, "table": table}


def read_vectors_i8(path: Path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, dims, n_skills, scale, blob_len = struct.unpack_from("<4sHHIfI", data, 0)
    assert magic == VECTORS_MAGIC, f"bad magic in {path}: {magic!r}"
    offset = struct.calcsize("<4sHHIfI")
    urns = data[offset:offset + blob_len].decode("utf-8").split("\n")
    offset += blob_len
    table = np.frombuffer(data, dtype="<i1", count=n_skills * dims, offset=offset).reshape(n_skills, dims)
    offset += n_skills * dims
    d2 = np.frombuffer(data, dtype="<u4", count=n_skills, offset=offset)
    return {"version": version, "dims": dims, "scale": scale, "urns": urns, "table": table, "d2": d2}


def read_teacher_f16(path: Path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, dims, n_skills, blob_len = struct.unpack_from("<4sHHII", data, 0)
    assert magic == TEACHER_MAGIC, f"bad magic in {path}: {magic!r}"
    offset = struct.calcsize("<4sHHII")
    urns = data[offset:offset + blob_len].decode("utf-8").split("\n")
    offset += blob_len
    table = np.frombuffer(data, dtype="<f2", count=n_skills * dims, offset=offset).reshape(n_skills, dims)
    return {"version": version, "dims": dims, "urns": urns, "table": table}


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def distill(corpus: list, teacher_id: str, teacher_revision: str, out_dir: Path,
            dims: int = DEFAULT_DIMS, license_str: str = "unknown", write_teacher: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    vocab = build_vocabulary(corpus)

    word_table_f32 = build_word_table(vocab, teacher_id, teacher_revision, dims=dims)
    skill_sums_f32 = build_skill_float_sums(corpus, vocab, word_table_f32)

    # Single global scale (step 5/6), derived from the WORD table alone: max_abs(word_table) / 127.
    #
    # This *sequential* reading of steps 6-7 (fix the scale while finishing step 6's artifact,
    # `words.bin`; step 7 then *reuses* that already-fixed number -- "requantized ... with the
    # same scale" -- rather than *re-deriving* a scale by looking ahead at the not-yet-computed
    # skill sums) is deliberate, not incidental. An earlier version of this function derived the
    # scale from max(|word_table|, |skill_sums|) instead. That is wrong in practice: a raw SUM of
    # a skill's (Zipf-weighted) per-token vectors is naturally ~1-2 orders of magnitude larger than
    # any single word vector (this corpus: word max-abs ~0.32, skill-sum max-abs ~26, a ~83x gap),
    # so a scale wide enough to cover the skill sums without clipping quantizes 2251/2257 (99.7%)
    # of this corpus's word vectors to the all-zero int8 vector -- i.e. B4's *query*-side
    # representation (built by summing looked-up word vectors, see arms.py:arm_b4) is almost
    # always the zero vector, and every skill then ties at cosine 0, falling back to an
    # alphabetical tiebreak that is blind to the query. Deriving the scale from the word table
    # alone keeps every word's int8 vector meaningfully non-zero (this corpus: 2257/2257), at the
    # cost of the (separately-computed, see below) skill sums saturating in their largest
    # dimensions -- a real, but far less damaging, precision loss than a fully query-blind arm.
    #
    # This does NOT fully fix retrieval quality: even measured in exact float32 (no quantization
    # at all), the literal "Zipf-weight = 1/log(1+rank), rank 1 = most frequent" formula (step 4)
    # applied to a raw SUM (not mean) aggregation (step 7) upweights a skill's most FREQUENT terms,
    # not its most DISCRIMINATING ones -- the opposite of the IDF-style downweighting standard
    # model2vec distillation uses. On this fixture that makes B4's top-5 for "add RBAC to this new
    # admin-only endpoint" put a generic auth skill ahead of the actual `rbac-policies` skill (rank
    # #4), even with zero quantization error. Fixing that would mean deviating from the literally
    # specified formula/aggregation (both called out as required, `vectors.i8`'s construction as
    # "the single most important rule") -- a judgement call left for the human + a later golden-set
    # evaluation pass, not something this phase's code changes unilaterally. See tools/bakeoff/README.md
    # ("Known limitation: B4 static-table retrieval quality") for the full writeup.
    word_max_abs = float(np.abs(word_table_f32).max())
    scale = word_max_abs / 127.0 if word_max_abs > 0 else 1.0

    word_table_i8 = quantize_int8(word_table_f32, scale)
    skill_table_i8 = quantize_int8(skill_sums_f32, scale)
    skill_d2 = (skill_table_i8.astype(np.int64) ** 2).sum(axis=1).astype(np.uint32)
    skill_clip_rate = float((np.abs(skill_sums_f32) / scale >= 127.0).mean()) if scale > 0 else 0.0

    urns = [r.urn for r in corpus]  # corpus is already sorted by URN (corpus.py)

    words_bin_path = out_dir / "words.bin"
    vectors_i8_path = out_dir / "vectors.i8"
    words_json_path = out_dir / "words.json"
    teacher_f16_path = out_dir / "teacher.f16"

    write_words_bin(words_bin_path, vocab, word_table_i8, scale, dims)
    write_vectors_i8(vectors_i8_path, urns, skill_table_i8, skill_d2, scale, dims)

    manifest = {
        "teacher_id": teacher_id,
        "teacher_revision": teacher_revision,
        "teacher_license": license_str,
        "dims": dims,
        "quantization_scale": scale,
        "vocab_size": len(vocab.words),
        "common_core_size": len(vocab.common_core),
        "common_core_sample": vocab.common_core[:40],
        "n_skills": len(corpus),
        "pca_sign_convention": "per-component: coordinate with the largest |value| is forced positive",
        "zipf_weight_formula": "1 / log(1 + rank_by_frequency), rank 1 = most frequent corpus word",
        "tokenizer": "tools/bakeoff/tokenizer.py:tokenize (NFC, ASCII-lower, split on [a-z0-9]+)",
        "skill_vectors_source": (
            "vectors.i8 is the Zipf-weighted sum of vocab word vectors from words.bin over each "
            "skill's concatenated fields, requantised with the SAME scale as words.bin -- NOT "
            "encoded by the teacher. See tools/bakeoff/README.md, 'the single most important rule'."
        ),
        "scale_derivation": (
            "max(|word_table_f32|) / 127 -- fixed from the word table alone, then reused as-is "
            "for the skill sums (see the comment above this block in distill.py for why: deriving "
            "it from max(|words|, |skills|) instead quantises almost every word vector to zero on "
            "this fixture)."
        ),
        "skill_vector_clip_rate": skill_clip_rate,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    words_json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    result = {
        "words_bin": words_bin_path,
        "vectors_i8": vectors_i8_path,
        "words_json": words_json_path,
        "manifest": manifest,
        "vocab": vocab,
    }

    if write_teacher:
        encoder = Encoder(teacher_id, teacher_revision)
        teacher_docs = encoder.encode([r.concat_text() for r in corpus], is_query=False)
        write_teacher_f16(teacher_f16_path, urns, teacher_docs)
        result["teacher_f16"] = teacher_f16_path

    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--teacher-id", default="pipizhao/SkillRouter-Embedding-0.6B")
    ap.add_argument("--teacher-revision", default="c03c9bcee9fce92ab0262bb6dcf54d174a8ba558")
    ap.add_argument("--license", dest="license_str", default="apache-2.0")
    ap.add_argument("--dims", type=int, default=DEFAULT_DIMS)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--no-teacher-f16", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir or (BUILD_ROOT / args.teacher_id.replace("/", "__"))
    corpus = load_corpus()

    t0 = time.time()
    result = distill(corpus, args.teacher_id, args.teacher_revision, out_dir,
                      dims=args.dims, license_str=args.license_str,
                      write_teacher=not args.no_teacher_f16)
    elapsed = time.time() - t0

    m = result["manifest"]
    print(f"teacher: {m['teacher_id']} @ {m['teacher_revision']}")
    print(f"vocab_size: {m['vocab_size']}  common_core_size: {m['common_core_size']}")
    print(f"dims: {m['dims']}  scale: {m['quantization_scale']:.8f}")
    print(f"n_skills: {m['n_skills']}")
    print(f"words.bin: {result['words_bin']} ({result['words_bin'].stat().st_size} bytes)")
    print(f"vectors.i8: {result['vectors_i8']} ({result['vectors_i8'].stat().st_size} bytes)")
    if "teacher_f16" in result:
        print(f"teacher.f16: {result['teacher_f16']} ({result['teacher_f16'].stat().st_size} bytes) [--experimental only]")
    print(f"elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
