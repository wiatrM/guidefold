#!/usr/bin/env python3
"""tools/eval/dense_ref.py — shared encoder-backed dense-retrieval scaffolding for the
DENSE-PROGRAM.md R1 reference runs (`SKILLRET-Embedding-0.6B` through the unmodified product
path). Factored out of tools/eval/skillret.py (test-A / SKILLRET-test, PR #33) so that
tools/eval/skillretbench_r1.py (test-B / SkillRetBench) reuses it verbatim instead of
re-implementing it — see DENSE-PROGRAM.md v2.1 §6.

Everything here is corpus-agnostic: no assumption about a corpus's card shape, taxonomy, or case
schema. Callers own corpus loading, card/case building, node-setting selection, and per-query
orchestration (each already has its own `run_case`/`run_arm`-style driver — see
skillretbench.py's `run_case`/`run_arm` and skillret.py's `run_arm_parallel`).

Kept import-safe without GPU deps at module scope: no torch/transformers/sentence-transformers
anywhere in this file, and numpy is imported lazily inside each function (mirroring
skillret.py's own convention) so this module can be imported by pytest with no GPU venv and no
network access.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


# --------------------------------------------------------------------------- dense candidate router
class DenseCandidateRouter:
    """Mixin applied over a loaded guidefold CLI module's `Router` class (see
    `make_dense_router_class`). Overrides only `_dense_scores`; `candidates`/`score`/`select`/
    `route`/`policy_filter` are the unmodified base class (ADR-0022: no arm bypasses the filter).

    The base `_dense_scores` sums per-word vectors from `idx.word_vectors` (a global word table) —
    incompatible with precomputed per-document encoder embeddings, so it is replaced wholesale.
    `idx.skill_vectors` is left empty; encoder vectors live in `self.skill_mat` (int8) instead,
    keyed by `self.row_of[urn]`. Query vectors are also int8 and are selected by qid via
    `self._current_qid`, set by the caller immediately before `candidates()`/`route()` — the base
    `_dense_scores(query, visible)` signature carries query *text*, not an id, so this is the
    narrowest way to key the precomputed table without touching the base class.
    """

    def _dense_scores(self, query, visible):
        idx = self.index
        qvec = self.query_vec_of.get(self._current_qid)
        if qvec is None:
            return {}
        import numpy as np
        urns_visible = [u for u in visible if u in self.row_of]
        if not urns_visible:
            return {}
        rows = np.asarray([self.row_of[u] for u in urns_visible], dtype=np.int64)
        sub = self.skill_mat[rows].astype(np.int64)
        dots = sub @ qvec
        out = {}
        for u, d in zip(urns_visible, dots.tolist()):
            # Plain Python ints (arbitrary precision): _dense_rank's sign*dot*dot*normsq
            # comparison overflows numpy int64 at these magnitudes (dims=1024, int8 range).
            out[u] = (int(d), int(idx.skill_normsq.get(u, 0)))
        return out


def make_dense_router_class(cli):
    return type("DenseRefRouter", (DenseCandidateRouter, cli.Router), {})


def build_dense_index_and_router(cli, cards, nodes, row_of, skill_mat, query_vec_of, weights=None):
    """Generalized form of skillret.py's original `build_r1_index_and_router`: `weights` defaults
    to `{"w_dense": 1}` (the R1 reference weight — DENSE-PROGRAM.md v2.1 §6, tooling defaults, no
    tuning) but callers may pass any other weights dict, e.g. to reuse this for a future weighted
    fusion arm without duplicating the wiring."""
    import numpy as np
    if weights is None:
        weights = {"w_dense": 1}
    idx = cli.Index.from_cards(cards, nodes, weights=weights, word_vectors=None)
    normsq = (skill_mat.astype(np.int64) ** 2).sum(axis=1)
    missing = [u for u in cards if u not in row_of]
    if missing:
        raise SystemExit(f"dense_ref: {len(missing)} cards have no cached embedding "
                          f"(encode cache stale?) e.g. {missing[:3]}")
    idx.skill_normsq = {u: int(normsq[row_of[u]]) for u in cards}
    router_cls = make_dense_router_class(cli)
    router = router_cls(idx)
    router.row_of = row_of
    router.skill_mat = skill_mat
    router.query_vec_of = query_vec_of
    router._current_qid = None
    return idx, router


# --------------------------------------------------------------------------- quantisation
def quantize(mat):
    """float32 -> int8, symmetric scale 127 (unit-normalised encoder output assumed)."""
    import numpy as np
    return np.clip(np.round(mat * 127.0), -127, 127).astype(np.int8)


def quant_cosine(orig, q):
    """Per-row cosine similarity between the original float32 matrix and its int8-then-dequantised
    round trip — the quantisation-error diagnostic written into each corpus's encode `meta.json`."""
    import numpy as np
    deq = q.astype(np.float32) / 127.0
    num = (orig * deq).sum(axis=1)
    den = np.linalg.norm(orig, axis=1) * np.linalg.norm(deq, axis=1)
    den = np.where(den == 0, 1.0, den)
    return num / den


def encode_chunked(enc, texts, is_query, chunk_size, label):
    """Chunks the call to Encoder.encode() itself (not just its internal batch_size):
    encode() caches to disk only after the WHOLE list it was given returns successfully, so one
    call over a whole corpus would lose every result to a single OOM anywhere in the middle.
    Chunking means a crash only costs its own chunk, and a rerun of `encode` resumes for free
    (already-cached texts are a cache hit inside Encoder.encode)."""
    import numpy as np
    out = [None] * len(texts)
    for start in range(0, len(texts), chunk_size):
        chunk = texts[start:start + chunk_size]
        ct0 = time.time()
        vecs = enc.encode(chunk, is_query=is_query)
        dt = time.time() - ct0
        for i in range(len(chunk)):
            out[start + i] = vecs[i]
        print(f"  {label}: {start + len(chunk)}/{len(texts)} "
              f"({dt:.1f}s this chunk, {dt / max(len(chunk), 1) * 1000:.1f} ms/item)", flush=True)
    return np.stack(out, axis=0).astype(np.float32)


# --------------------------------------------------------------------------- dense cache (disk)
def write_dense_cache(cache_dir: Path, skill_order, query_order, skill_q, query_q, meta):
    import numpy as np
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache_dir / "skill_vectors.i8.npy", skill_q)
    np.save(cache_dir / "query_vectors.i8.npy", query_q)
    (cache_dir / "skill_order.json").write_text(json.dumps(skill_order))
    (cache_dir / "query_order.json").write_text(json.dumps(query_order))
    (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def load_dense_cache(cache_dir: Path):
    """Parameterized form of skillret.py's original module-level-`CACHE_DIR`-bound
    `load_dense_cache()`. Returns (meta, row_of, skill_mat, query_vec_of)."""
    import numpy as np
    if not (cache_dir / "meta.json").exists():
        raise SystemExit(f"dense_ref: no encode cache at {cache_dir} — run the corpus's `encode` "
                          f"subcommand under the GPU venv first")
    meta = json.loads((cache_dir / "meta.json").read_text())
    skill_order = json.loads((cache_dir / "skill_order.json").read_text())
    query_order = json.loads((cache_dir / "query_order.json").read_text())
    skill_mat = np.load(cache_dir / "skill_vectors.i8.npy")
    query_mat = np.load(cache_dir / "query_vectors.i8.npy")
    row_of = {u: i for i, u in enumerate(skill_order)}
    query_vec_of = {qid: query_mat[i].astype(np.int64) for i, qid in enumerate(query_order)}
    return meta, row_of, skill_mat, query_vec_of
