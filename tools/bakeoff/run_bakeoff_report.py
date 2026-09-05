#!/usr/bin/env python3
"""run_bakeoff_report.py — E1.3 phase 2: every bake-off arm over the 220-query golden set.

Computes ranking metrics (tools/eval/metrics.py, never reimplemented) per stratum and overall,
plus index-build time and query latency, for every arm the coordinator's phase-2 brief names:

    B0   the ORIGINAL pre-Router-split scope-only CLI (commit 984d08c), via tools/eval/compare_b0.py.
         NOTE: this is a different B0 than tools/bakeoff/arms.py's own `arm_b0`, which calls the
         CURRENT Router (used only for the phase-1 harness smoke test / sample query). The current
         Router 0.1's own golden-set numbers are already published in docs/reports/golden/README.md.
    B1   field-weighted BM25            (arms.arm_b1)
    B2a  Qwen3-Embedding-0.6B, fresh    (arms.arm_b2a, but batched here -- see below)
    B2b  bge-m3, fresh                  (arms.arm_b2b, batched)
    B3a  SkillRouter-Embedding-0.6B     (arms.arm_b3a, batched)
    B3b  SKILLRET-Embedding-0.6B        (arms.arm_b3b, batched)
    B4   static student table alone     (arms.arm_b4)
    B5   B1 + B4 via RRF                (arms.arm_b5)
    B6   NOT RUN HERE -- being built on feat/e1-shadow-rerank; left as a placeholder row.

B2a/B2b/B3a/B3b are run with one batched `Encoder.encode()` call per teacher over all 220 query
texts, instead of arms.py's `_dense_rank` (which encodes one query at a time -- fine for a single
sample query, far too slow for 220 queries x 4 teachers). Every encoding is still disk-cached by
`encode.py` (keyed by exact text + is_query), so a rerun of this script is cheap.

Every arm's ranked list is fed to `tools/eval/metrics.py` exactly once, in the single order each
arm produces (its own score-descending ranking) -- there is no separate "injection order" for
these arms the way there is for the *current* Router's `.select()` (see
docs/reports/golden/README.md's "two orderings" warning); that distinction only applies to code
that goes through `Router.select()`, which none of B0-B6 do here.

Usage:
    <venv>/bin/python3 tools/bakeoff/run_bakeoff_report.py [--out results.json]

Writes a JSON blob of every arm's metrics + timing + raw per-case rankings to `--out` (default:
a scratch path printed at the end) so the markdown report can be authored from exact numbers
rather than retyped from terminal output.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

REPO_ROOT = Path(__file__).resolve().parents[2]
BAKEOFF_DIR = REPO_ROOT / "tools" / "bakeoff"
EVAL_DIR = REPO_ROOT / "tools" / "eval"
sys.path.insert(0, str(BAKEOFF_DIR))
sys.path.insert(0, str(EVAL_DIR))

import numpy as np  # noqa: E402

import arms  # noqa: E402
import compare_b0  # noqa: E402
import encode  # noqa: E402
import metrics  # noqa: E402
from corpus import load_corpus  # noqa: E402

RANK_K = 50  # >= every metric's k (nDCG@10 is the largest); cheap for these arms either way.

DENSE_TEACHERS = {
    "B2a": arms.QWEN3_EMBEDDING,
    "B2b": arms.BGE_M3,
    "B3a": arms.SKILLROUTER_EMBEDDING,
    "B3b": arms.SKILLRET_EMBEDDING,
}


def _now() -> float:
    return time.time()


def _json_safe(m: dict) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in m.items()}


def _metrics_block(results: list) -> dict:
    overall = metrics.evaluate(results)
    per_cat = metrics.by_category(results)
    return {
        "overall": _json_safe(overall),
        "by_category": {c: _json_safe(m) for c, m in per_cat.items()},
    }


def run_b0(cases: list) -> dict:
    print("B0 (original scope-only CLI, commit 984d08c)...", file=sys.stderr)
    results, elapsed = compare_b0.run_b0(cases, limit=8, progress=False)
    block = _metrics_block(results)
    block["timing"] = {
        "build_s": None,  # stateless: no persisted index, scans the fixture tree per query
        "query_s_total": elapsed,
        "query_ms_avg": elapsed / len(cases) * 1000,
    }
    block["artifact"] = "none (stateless scope-distance scan of the fixture tree; no persisted index)"
    return block


def run_b1(cases: list, corpus: list) -> dict:
    print("B1 (field-weighted BM25)...", file=sys.stderr)
    t0 = _now()
    idx = arms._bm25_index(corpus)  # noqa: SLF001 -- populates the module cache arm_b1 reads
    build_s = _now() - t0
    t0 = _now()
    results = [(arms.arm_b1(c["query"], corpus, limit=RANK_K), c) for c in cases]
    query_s = _now() - t0
    block = _metrics_block(results)
    block["timing"] = {"build_s": build_s, "query_s_total": query_s, "query_ms_avg": query_s / len(cases) * 1000}
    block["artifact"] = (
        "none persisted by this harness; the shipped equivalent is the E1.4 index artifact's "
        "precomputed integer IDF/field-weight table (small, O(vocab_size) ints) -- out of this "
        "report's scope, owned by the E1.4 index-format work."
    )
    return block


def run_dense(name: str, hf_id: str, revision: str, cases: list, corpus: list) -> dict:
    print(f"{name} ({hf_id}, fresh, batched)...", file=sys.stderr)
    t0 = _now()
    doc_vecs = arms._dense_doc_vectors(hf_id, revision, corpus)  # noqa: SLF001
    build_s = _now() - t0
    enc = arms._encoder(hf_id, revision)  # noqa: SLF001
    queries = [c["query"] for c in cases]
    t0 = _now()
    qvecs = enc.encode(queries, is_query=True)  # ONE batched call over all 220 queries
    encode_s = _now() - t0
    scores = doc_vecs @ qvecs.T  # (n_docs, n_queries); both sides unit-normalised -> cosine
    urns = [r.urn for r in corpus]
    results = []
    for j, c in enumerate(cases):
        order = sorted(range(len(corpus)), key=lambda i: (-scores[i, j], urns[i]))
        results.append(([urns[i] for i in order[:RANK_K]], c))
    block = _metrics_block(results)
    block["timing"] = {
        "build_s": build_s,  # 26-doc corpus encode (cold unless .bakeoff-cache is warm)
        "query_s_total": encode_s,  # ONE batched call for all 220 queries
        "query_ms_avg": encode_s / len(cases) * 1000,
        "device": encode.DEVICE,
        "dtype": str(encode.DTYPE).rsplit(".", 1)[-1],
        "batch_size": enc.batch_size,
    }
    block["artifact"] = (
        f"none shippable -- {hf_id} weights alone are ~2.4GB fp32 on disk (0.6B params), GCS-"
        "mirrored for CI/--experimental only (ADR-0020), never in the shipped hook path."
    )
    return block


def run_b4(cases: list, corpus: list) -> dict:
    print("B4 (static student table alone)...", file=sys.stderr)
    t0 = _now()
    table = arms._student_table(corpus)  # noqa: SLF001 -- runs distill.distill() under the hood
    build_s = _now() - t0
    t0 = _now()
    results = [(arms.arm_b4(c["query"], corpus, limit=RANK_K), c) for c in cases]
    query_s = _now() - t0
    block = _metrics_block(results)
    block["timing"] = {
        "build_s": build_s,  # distill.distill() -- vocab + skill teacher encodes run on encode.DEVICE
        "query_s_total": query_s,
        "query_ms_avg": query_s / len(cases) * 1000,
        "distill_device": encode.DEVICE,
        "distill_dtype": str(encode.DTYPE).rsplit(".", 1)[-1],
    }
    dims = table["word_table_i8"].shape[1]
    vocab = table["word_table_i8"].shape[0]
    n_skills = table["skill_table_i8"].shape[0]
    out_dir = arms.distill.BUILD_ROOT / ("_b4_student__" + arms.DEFAULT_STUDENT_TEACHER[0].replace("/", "__"))
    words_bin_bytes = (out_dir / "words.bin").stat().st_size if (out_dir / "words.bin").exists() else None
    vectors_i8_bytes = (out_dir / "vectors.i8").stat().st_size if (out_dir / "vectors.i8").exists() else None
    size_str = (
        f"{words_bin_bytes/1024:.1f}KiB + {vectors_i8_bytes/1024:.2f}KiB (measured on disk)"
        if words_bin_bytes and vectors_i8_bytes else "(sizes unavailable -- files not found on disk)"
    )
    block["artifact"] = (
        f"words.bin + vectors.i8, the shipped tier-1 static table: dims={dims}, vocab={vocab}, "
        f"n_skills={n_skills} -> {size_str}."
    )
    return block


def run_b5(cases: list, corpus: list) -> dict:
    print("B5 (B1 + B4 via RRF)...", file=sys.stderr)
    t0 = _now()
    arms._bm25_index(corpus)  # noqa: SLF001 -- both already warm from run_b1/run_b4 if run first
    arms._student_table(corpus)  # noqa: SLF001
    build_s = _now() - t0
    t0 = _now()
    results = [(arms.arm_b5(c["query"], corpus, limit=RANK_K), c) for c in cases]
    query_s = _now() - t0
    block = _metrics_block(results)
    block["timing"] = {"build_s": build_s, "query_s_total": query_s, "query_ms_avg": query_s / len(cases) * 1000}
    block["artifact"] = "same artifacts as B1 + B4 -- RRF fusion itself is a runtime computation, no artifact of its own."
    return block


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--out",
        default="/tmp/claude-1000/-home-mike-projects-guidefold/09c78073-93c2-488d-876e-3b1fc5515053/"
        "scratchpad/e13/report_data.json",
    )
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these arm names (debugging)")
    args = ap.parse_args(argv)

    cases = compare_b0.load_cases()
    corpus = load_corpus()
    print(f"{len(cases)} golden cases, {len(corpus)} skills in the fixture", file=sys.stderr)

    import platform
    import subprocess

    gpu_name = gpu_driver = None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        if out:
            gpu_name, gpu_driver = [s.strip() for s in out.split(",")]
    except Exception:
        pass

    report: dict = {
        "n_cases": len(cases),
        "n_skills": len(corpus),
        "hardware": {
            "device": encode.DEVICE,
            "dtype": str(encode.DTYPE).rsplit(".", 1)[-1],
            "gpu_name": gpu_name,
            "gpu_driver_version": gpu_driver,
            "torch_version": __import__("torch").__version__,
            "torch_cuda_version": __import__("torch").version.cuda,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "arms": {},
    }

    steps = [
        ("B0", lambda: run_b0(cases)),
        ("B1", lambda: run_b1(cases, corpus)),
        ("B2a", lambda: run_dense("B2a", *DENSE_TEACHERS["B2a"], cases, corpus)),
        ("B2b", lambda: run_dense("B2b", *DENSE_TEACHERS["B2b"], cases, corpus)),
        ("B3a", lambda: run_dense("B3a", *DENSE_TEACHERS["B3a"], cases, corpus)),
        ("B3b", lambda: run_dense("B3b", *DENSE_TEACHERS["B3b"], cases, corpus)),
        ("B4", lambda: run_b4(cases, corpus)),
        ("B5", lambda: run_b5(cases, corpus)),
    ]
    for name, fn in steps:
        if args.only and name not in args.only:
            continue
        t0 = _now()
        report["arms"][name] = fn()
        print(f"  {name} done in {_now() - t0:.1f}s wall", file=sys.stderr)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nwrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
