#!/usr/bin/env python3
"""CPU-only decomposition/profile of the resident native candidate path.

Uses the exact frozen CLI, 6006 real cached DOCUMENT vectors, and one document
row as a fixed stand-in query vector. No encoder, GPU, query embedding cache or
routing-quality claim. Query texts are public frozen DEV workload only.
"""
import argparse
import cProfile
import hashlib
import importlib.util
import json
from pathlib import Path
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/eval"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args()
    import numpy as np
    import skillret
    import dense_ref
    from tools.serve_spike.sparse_cache import install_bm25_cache
    from tools.serve_spike.native_rank import prepare_native_rank, install_native_dense_rank
    server = load("cpu_profile_server", ROOT / "tools/serve_spike/server.py")
    probe = load("cpu_profile_probe", ROOT / "tools/serve_spike/probe.py")
    cli_path = ROOT / ".guidefold/serve-spike/frozen-cli.py"
    cli, revision = server.load_cli_snapshot(cli_path)
    queries, workload = probe.load_queries(args.count)
    started = time.perf_counter()
    data, nodes, cards, _, _, _ = skillret.load_corpus_and_build(cli)
    directory = ROOT / "tools/eval/.skillret-cache"
    matrix_path = directory / "skill_vectors.i8.npy"
    matrix = np.load(matrix_path, allow_pickle=False)
    order = json.loads((directory / "skill_order.json").read_text())
    assert order == sorted(cards) and matrix.shape == (6006, 1024)
    index, router = dense_ref.build_dense_index_and_router(
        cli, cards, nodes, {u: i for i, u in enumerate(order)}, matrix, {})
    sparse_meta = install_bm25_cache(router)
    dense_meta = server.install_resident_dense(router)
    native_meta = install_native_dense_rank(router, prepare_native_rank())
    router.query_vec_of = {"document-row-probe": matrix[0].astype(np.int64)}
    router._current_qid = "document-row-probe"
    initialization_ms = (time.perf_counter() - started) * 1000
    print("resident 6006-row CPU router initialized; no GPU/model loaded", flush=True)

    def route(query):
        admissible, _ = router.policy_filter("_root", query)
        candidates = router.candidates(query, "_root")
        scored = router.score(candidates, query, "_root")
        return router.select(scored, k=4, admissible=set(admissible))

    for query in queries[:2]:
        route(query["query"])
    plain = []
    for query in queries:
        times = {}
        def timed(name, function):
            before = time.perf_counter()
            value = function()
            times[name] = (time.perf_counter() - before) * 1000
            return value
        admissible, _ = timed("outer_policy", lambda: router.policy_filter("_root", query["query"]))
        candidates = timed("candidates", lambda: router.candidates(query["query"], "_root"))
        scored = timed("score", lambda: router.score(candidates, query["query"], "_root"))
        timed("select", lambda: router.select(scored, k=4, admissible=set(admissible)))
        plain.append({"query_id": query["id"], "stages_ms": times})

    decomposed = []
    for query in queries:
        times = {}
        def timed(name, function):
            before = time.perf_counter()
            value = function()
            times[name] = (time.perf_counter() - before) * 1000
            return value
        visible, drops = timed("policy_inside_candidates", lambda: router.policy_filter("_root", query["query"]))
        visible_set = timed("visible_set", lambda: set(visible))
        bm25 = timed("bm25_cached_accumulation", lambda: router._bm25_scores(query["query"], visible_set))
        dense = timed("dense_dot_and_python_dict", lambda: router._dense_scores(query["query"], visible_set))
        bm25_order = timed("bm25_sort", lambda: sorted(bm25, key=lambda u: (-bm25[u], u)))
        bm25_rank = timed("bm25_rank_dict", lambda: {u: i + 1 for i, u in enumerate(bm25_order)})
        dense_order = timed("native_rank_including_python_marshalling", lambda: router.native_rank_adapter.rank(dense))
        dense_rank = timed("dense_rank_dict", lambda: {u: i + 1 for i, u in enumerate(dense_order)})
        urns = timed("union_top50_and_sort", lambda: sorted(set(bm25_order[:50]) | set(dense_order[:50])))
        rebuilt = timed("candidate_cards", lambda: [
            {"urn": u, "node": index.cards[u]["node"], "bm25_rank": bm25_rank.get(u),
             "dense_rank": dense_rank.get(u)} for u in urns])
        expected = router.candidates(query["query"], "_root")
        assert rebuilt == expected, "decomposition diverged from exact frozen candidates"
        decomposed.append({"query_id": query["id"], "stages_ms": times,
                           "bm25_items": len(bm25), "dense_items": len(dense),
                           "parity_with_actual_candidates": True})
    profiler = cProfile.Profile()
    profiler.enable()
    for query in queries:
        route(query["query"])
    profiler.disable()
    stats = pstats.Stats(profiler)
    functions = []
    for (filename, line, name), (primitive, calls, self_seconds, cumulative, _) in stats.stats.items():
        functions.append({"file": filename, "line": line, "name": name,
                          "calls": calls, "self_ms": self_seconds * 1000,
                          "cumulative_ms": cumulative * 1000})

    def summarize(rows):
        keys = rows[0]["stages_ms"]
        return {key: {"p50": probe.percentile([row["stages_ms"][key] for row in rows], .5),
                      "p95": probe.percentile([row["stages_ms"][key] for row in rows], .95),
                      "mean": sum(row["stages_ms"][key] for row in rows) / len(rows)}
                for key in keys}

    report = {
        "schema_version": "e11b-cpu-candidate-profile-v1", "created_unix": time.time(),
        "scope": "CPU only; fixed document row stands in for query embedding; no quality or end-to-end SLO claim",
        "workload": workload, "frozen_cli_sha256": revision,
        "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in
                          ("tools/serve_spike/candidate_profile.py", "tools/serve_spike/server.py",
                           "tools/serve_spike/sparse_cache.py", "tools/serve_spike/native_rank.py")},
        "document_matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "query_vector_source": "cached DOCUMENT matrix row 0; no query_vectors file read",
        "query_vector_sha256": hashlib.sha256(router.query_vec_of["document-row-probe"].tobytes()).hexdigest(),
        "initialization_ms": initialization_ms,
        "optimizations": {"sparse": sparse_meta, "dense": dense_meta, "native": native_meta},
        "uninstrumented_rows": plain, "uninstrumented_summary_ms": summarize(plain),
        "decomposition_rows": decomposed, "decomposition_summary_ms": summarize(decomposed),
        "cprofile": {"note": "Profiler adds overhead; use uninstrumented latency above for timing",
                     "self_time_top30": sorted(functions, key=lambda row: -row["self_ms"])[:30],
                     "cumulative_time_top30": sorted(functions, key=lambda row: -row["cumulative_ms"])[:30]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"uninstrumented": report["uninstrumented_summary_ms"],
                      "decomposition": report["decomposition_summary_ms"],
                      "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()
