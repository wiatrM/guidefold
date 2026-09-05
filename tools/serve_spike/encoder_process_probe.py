#!/usr/bin/env python3
"""Compare resident in-process and spawned encoders numerically, without timing claims.

Run explicitly in the GPU environment after other GPU experiments have stopped:
    python tools/serve_spike/encoder_process_probe.py --output comparison.json

Both pinned models remain resident; query forwards run sequentially in alternating
AB/BA order. Only IDs, provenance hashes and comparison statistics are persisted.
This is a hybrid-shadow validation tool, not product SEARCH admission evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DIMS = 1024
THREADS = 16
WARMUP = "Find a skill for validating a local API."
SOURCE_PATHS = (
    "tools/serve_spike/encoder_process_probe.py",
    "tools/serve_spike/encoder_worker.py",
    "tools/serve_spike/probe.py",
    "tools/bakeoff/encode.py",
    "tools/eval/dense_ref.py",
    "tools/eval/skillret.py",
    "tools/eval/corpora.py",
)


def source_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_PATHS}


def normalized_and_quantized(vector, np, quantize):
    """Exact extra normalization/quantization used after either service encoder."""
    if vector.shape != (1, DIMS) or vector.dtype != np.dtype("float32"):
        raise ValueError("invalid_vector_shape_or_dtype")
    norms = np.linalg.norm(vector, axis=1, keepdims=True)
    if not np.isfinite(vector).all() or not (norms > 0).all():
        raise ValueError("invalid_encoder_output")
    normalized = vector / norms
    return normalized, quantize(normalized)


def comparison_stats(reference, worker, np):
    """Bit equality catches signed-zero differences as well as numeric changes."""
    bit_differences = int(np.count_nonzero(reference.view(np.uint32) != worker.view(np.uint32)))
    return {
        "exact": bit_differences == 0,
        "bitwise_mismatched_elements": bit_differences,
        "numerically_mismatched_elements": int(np.count_nonzero(reference != worker)),
        "max_abs_difference": float(np.max(np.abs(reference.astype(np.float64)
                                                    - worker.astype(np.float64)))),
    }


def run(count):
    # Keep all GPU imports inside this function and after worker startup. Spawn
    # imports this module again, so module-scope imports must stay stdlib-only.
    for directory in (ROOT, ROOT / "tools/eval"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from tools.serve_spike.encoder_worker import EncoderProcessProxy
    from tools.serve_spike.probe import load_queries
    import skillret
    import dense_ref

    result = {
        "schema_version": "e11b-encoder-process-numeric-v1",
        "created_unix": time.time(),
        "scope": "paired encoder numerical comparison only; no latency, routing quality or production claim",
        "execution": "two resident models; sequential batch-one forwards; alternating reference-worker / worker-reference",
        "count_requested": count, "rows": [], "complete": False, "passed": False,
        "source_sha256": source_hashes(),
        "platform": platform.platform(), "python": platform.python_version(),
        "query_cache": False, "persists_query_text_or_vectors": False,
        "reference_live_encode_calls": 0, "reference_model_load_calls": 0,
        "reference_warmup_calls": 0,
    }
    proxy = None
    phase, query_id = "load_workload", None
    try:
        queries, workload = load_queries(count)
        workload["quality_claim"] = "none; frozen DEV texts are used only for numerical parity"
        result["workload"] = workload
        if workload["hf_revision"] != skillret.CORPUS_REVISION:
            raise ValueError("unexpected_corpus_revision")
        if any(len(query["query"]) > 4096 for query in queries):
            raise ValueError("query_exceeds_worker_limit")
        config = {
            "model_id": skillret.MODEL_HF_ID, "model_revision": skillret.MODEL_REV,
            "dims": DIMS, "torch_threads": THREADS, "device": "cuda",
            "worker_timeout_s": 30.0,
        }
        result["worker_config"] = config
        result["parent_torch_imported_before_worker_start"] = "torch" in sys.modules
        if result["parent_torch_imported_before_worker_start"]:
            raise RuntimeError("parent_gpu_import_precedes_worker_start")
        phase = "worker_start"
        proxy = EncoderProcessProxy(config)
        ready = proxy.start(timeout=120)
        result["worker_ready"] = ready
        if any(ready.get(key) != expected for key, expected in {
            "model_id": skillret.MODEL_HF_ID, "model_revision": skillret.MODEL_REV,
            "dims": DIMS, "device": "cuda", "batch_size": 1,
            "torch_threads_effective": THREADS, "model_load_calls": 1,
            "warmup_calls": 1, "live_encode_calls": 0,
        }.items()):
            raise RuntimeError("unexpected_worker_identity_or_initial_counters")
        phase = "reference_load"
        sys.path.insert(0, str(ROOT / "tools/bakeoff"))
        import encode
        import numpy as np
        if encode.DEVICE != "cuda":
            raise RuntimeError("reference_cuda_unavailable")
        if encode._local_model_path(skillret.MODEL_HF_ID, skillret.MODEL_REV) is None:
            raise RuntimeError("reference_pinned_model_missing")
        reference = encode.Encoder(skillret.MODEL_HF_ID, skillret.MODEL_REV, batch_size=1)
        reference._ensure_loaded()
        result["reference_model_load_calls"] = 1
        encode.torch.set_num_threads(THREADS)
        result["reference_identity"] = {
            "model_id": reference.hf_id, "model_revision": reference.revision,
            "device": encode.DEVICE, "dtype": str(encode.DTYPE), "batch_size": 1,
            "torch_threads_effective": encode.torch.get_num_threads(),
            "gpu_name": encode.torch.cuda.get_device_name(),
        }
        phase = "reference_warmup"
        warm = reference._encode_uncached([WARMUP], is_query=True)
        normalized_and_quantized(warm, np, dense_ref.quantize)
        result["reference_warmup_calls"] = 1
        result["warmup_text_sha256"] = hashlib.sha256(WARMUP.encode()).hexdigest()
        for index, query in enumerate(queries):
            query_id = query["id"]
            order = ("reference", "worker") if index % 2 == 0 else ("worker", "reference")
            outputs = {}
            for arm in order:
                phase = "encode_" + arm
                if arm == "reference":
                    outputs[arm] = reference._encode_uncached([query["query"]], is_query=True)
                    result["reference_live_encode_calls"] += 1
                else:
                    outputs[arm] = proxy.encode(query["query"], time.monotonic() + 30.0)
            phase = "compare_vectors"
            ref_norm, ref_i8 = normalized_and_quantized(outputs["reference"], np, dense_ref.quantize)
            worker_norm, worker_i8 = normalized_and_quantized(outputs["worker"], np, dense_ref.quantize)
            int8_mismatches = int(np.count_nonzero(ref_i8 != worker_i8))
            result["rows"].append({
                "query_id": query_id, "order": list(order),
                "float32": comparison_stats(outputs["reference"], outputs["worker"], np),
                "normalized_float32": comparison_stats(ref_norm, worker_norm, np),
                "int8_exact": int8_mismatches == 0,
                "int8_mismatched_elements": int8_mismatches,
                "int8_max_abs_difference": int(np.max(np.abs(ref_i8.astype(np.int16)
                                                            - worker_i8.astype(np.int16)))),
            })
        result["worker_after_queries"] = proxy.health()
        rows = result["rows"]
        result["summary"] = {
            "paired_count": len(rows),
            "float32_exact_pairs": sum(row["float32"]["exact"] for row in rows),
            "normalized_float32_exact_pairs": sum(row["normalized_float32"]["exact"] for row in rows),
            "int8_exact_pairs": sum(row["int8_exact"] for row in rows),
            "float32_max_abs_difference": max(row["float32"]["max_abs_difference"] for row in rows),
            "normalized_float32_max_abs_difference": max(row["normalized_float32"]["max_abs_difference"] for row in rows),
            "int8_mismatched_elements": sum(row["int8_mismatched_elements"] for row in rows),
            "mismatch_query_ids": [row["query_id"] for row in rows if not (
                row["float32"]["exact"] and row["normalized_float32"]["exact"] and row["int8_exact"])],
        }
        health = result["worker_after_queries"]
        result["counter_audit_passed"] = (
            result["reference_live_encode_calls"] == count
            and health["live_encode_calls"] == count
            and health["metadata"]["model_load_calls"] == 1
            and health["alive"] and not health["failed"])
        result["complete"] = len(rows) == count
    except BaseException as exc:
        # Exception messages/tracebacks from ML libraries can contain inputs.
        result["failure"] = {"phase": phase, "query_id": query_id, "type": type(exc).__name__}
    finally:
        if proxy is not None:
            try:
                result.setdefault("worker_after_queries", proxy.health())
                proxy.close()
                result["worker_after_close"] = proxy.health()
                result["owned_worker_cleanup_passed"] = (
                    result["worker_after_close"]["closed"] and not result["worker_after_close"]["alive"])
            except BaseException as exc:
                result["cleanup_failure_type"] = type(exc).__name__
                result["owned_worker_cleanup_passed"] = False
        result["source_sha256_after"] = source_hashes()
        result["source_unchanged_during_run"] = result["source_sha256"] == result["source_sha256_after"]
    result["passed"] = bool(
        result["complete"] and result.get("counter_audit_passed")
        and result.get("owned_worker_cleanup_passed") and result["source_unchanged_during_run"]
        and not result.get("failure") and not result.get("summary", {}).get("mismatch_query_ids"))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args(argv)
    if not 1 <= args.count <= 200:
        parser.error("--count must be in 1..200")
    result = run(args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "complete": result["complete"], "passed": result["passed"]}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
