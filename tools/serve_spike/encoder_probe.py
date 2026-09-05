#!/usr/bin/env python3
"""Paired, interleaved 1-vs-16-thread GPU encoder diagnostic on frozen DEV texts.

One resident model, real uncached query forwards, batch size one. This measures
encoder latency and numerical parity only, not whole-client performance or
retrieval quality. Thread-setting and GPU observation costs are outside timing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/serve_spike"))
import probe


def file_sha256(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observe_gpu(stage):
    executable = pathlib.Path("/usr/lib/wsl/lib/nvidia-smi")
    command = str(executable) if executable.exists() else "nvidia-smi"
    result = {"stage": stage, "unix": time.time()}
    for name, query in (
        ("gpu", "--query-gpu=name,utilization.gpu,memory.used,memory.total"),
        ("compute_processes", "--query-compute-apps=pid,process_name,used_memory")):
        try:
            completed = subprocess.run([command, query, "--format=csv,noheader,nounits"],
                                       capture_output=True, text=True, timeout=5, check=False)
            result[name] = completed.stdout.strip() if completed.returncode == 0 else None
            result[name + "_available"] = completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            result[name] = None
            result[name + "_available"] = False
    try:
        result["first_gpu_utilization_percent"] = float(result["gpu"].splitlines()[0].split(",")[1].strip())
    except (AttributeError, IndexError, ValueError):
        result["first_gpu_utilization_percent"] = None
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    if not 2 <= args.count <= 40 or args.count % 2:
        parser.error("--count must be even and in 2..40 for balanced order")
    queries, workload = probe.load_queries(args.count)
    report = {
        "schema_version": "e11b-encoder-threads-v1", "workload": workload,
        "created_unix": time.time(), "pid": os.getpid(),
        "scope": "paired encoder latency and numerical parity; no quality or whole-client SLO claim",
        "flags": {"thread_settings": [1, 16], "batch_size": 1,
                  "warmups_per_setting": 2, "query_disk_cache_used": False,
                  "order": "even pairs 1->16, odd pairs 16->1",
                  "set_num_threads_cost_excluded": True, "GPU_to_CPU_copy_in_timed_region": True,
                  "pre_call_cuda_synchronize_outside_timed_region": True},
        "source_sha256": {"encoder_probe": file_sha256(__file__),
                          "frozen_probe": file_sha256(ROOT / "tools/serve_spike/probe.py"),
                          "encoder": file_sha256(ROOT / "tools/bakeoff/encode.py")},
        "gpu_observations": [observe_gpu("before_model_load")],
        "rows": [],
        "limitations": ["Concurrent external GPU load can confound latency and ordering",
                        "NVML/WSL process IDs may refer to host IDs; no reliable ownership inference after load",
                        "Exact int8 vector parity does not replace end-to-end routing parity",
                        "This process exits after the finite diagnostic; no service is left running"],
    }
    baseline_util = report["gpu_observations"][0]["first_gpu_utilization_percent"]
    report["external_gpu_utilization_before_our_model_load_percent"] = baseline_util
    report["external_gpu_busy_before_our_model_load"] = baseline_util >= 80 if baseline_util is not None else None
    try:
        sys.path.insert(0, str(ROOT / "tools/bakeoff"))
        sys.path.insert(0, str(ROOT / "tools/eval"))
        import numpy as np
        import encode
        import skillret
        from dense_ref import quantize

        torch = encode.torch
        if encode.DEVICE != "cuda":
            raise RuntimeError("cuda_required_for_this_paired_probe")
        started = time.perf_counter()
        encoder = encode.Encoder(skillret.MODEL_HF_ID, skillret.MODEL_REV, batch_size=1)
        encoder._ensure_loaded()
        report["model_load_ms"] = (time.perf_counter() - started) * 1000
        source = encode._local_model_path(skillret.MODEL_HF_ID, skillret.MODEL_REV)
        if source is None:
            raise RuntimeError("pinned_local_model_missing")
        model_config = json.loads((source / "config.json").read_text())
        report["model"] = {
            "id": skillret.MODEL_HF_ID, "revision": skillret.MODEL_REV,
            "model_config_sha256": file_sha256(source / "config.json"),
            "weight_files_sha256": {path.name: file_sha256(path) for path in sorted(source.glob("*.safetensors"))},
            "device": encode.DEVICE, "gpu_name": torch.cuda.get_device_name(0),
            "dtype": str(encode.DTYPE), "config_use_cache": model_config.get("use_cache"),
            "query_prompt_sha256": hashlib.sha256(encode.QUERY_PROMPTS[skillret.MODEL_HF_ID].encode()).hexdigest(),
        }
        report["runtime_versions"] = {
            package: importlib.metadata.version(package)
            for package in ("torch", "transformers", "sentence-transformers", "numpy")}
        report["source_sha256"]["installed_sentence_transformer"] = file_sha256(inspect.getfile(type(encoder._model)))
        report["torch_interop_threads_unchanged"] = torch.get_num_interop_threads()
        report["environment_thread_limits"] = {key: os.environ.get(key) for key in
                                               ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
        report["warmups"] = []
        for threads in (1, 16):
            change_started = time.perf_counter()
            torch.set_num_threads(threads)
            change_ms = (time.perf_counter() - change_started) * 1000
            durations = []
            for query in queries[:2]:
                torch.cuda.synchronize()
                started = time.perf_counter()
                encoder._encode_uncached([query["query"]], is_query=True)
                durations.append((time.perf_counter() - started) * 1000)
            report["warmups"].append({"threads": threads, "set_threads_ms": change_ms,
                                      "uncached_ms": durations})
        report["gpu_observations"].append(observe_gpu("after_warmups"))
        print("one model warm; starting " + str(args.count) + " balanced query pairs", flush=True)
        for number, query in enumerate(queries):
            order = (1, 16) if number % 2 == 0 else (16, 1)
            vectors, quantized, settings = {}, {}, {}
            for threads in order:
                change_started = time.perf_counter()
                torch.set_num_threads(threads)
                change_ms = (time.perf_counter() - change_started) * 1000
                torch.cuda.synchronize()
                started = time.perf_counter()
                vector = encoder._encode_uncached([query["query"]], is_query=True)
                elapsed_ms = (time.perf_counter() - started) * 1000
                if not np.isfinite(vector).all() or vector.shape != (1, 1024):
                    raise RuntimeError("invalid_encoder_output")
                # Match the live service's explicit float32 normalization before int8 quantization.
                norm = np.linalg.norm(vector, axis=1, keepdims=True)
                if not (norm > 0).all():
                    raise RuntimeError("zero_encoder_output")
                qvec = quantize(vector / norm)
                vectors[threads] = vector
                quantized[threads] = qvec
                settings[str(threads)] = {
                    "threads_effective": torch.get_num_threads(), "elapsed_ms": elapsed_ms,
                    "set_threads_ms_excluded": change_ms,
                    "float32_sha256": hashlib.sha256(vector.tobytes()).hexdigest(),
                    "quantized_sha256": hashlib.sha256(qvec.tobytes()).hexdigest(),
                }
            left, right = vectors[1].astype(np.float64).ravel(), vectors[16].astype(np.float64).ravel()
            cosine = float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))
            report["rows"].append({
                "query_id": query["id"], "order": list(order), "settings": settings,
                "float_cosine": min(1.0, max(-1.0, cosine)),
                "float_max_abs_diff": float(np.max(np.abs(left - right))),
                "float_exact_match": bool(np.array_equal(vectors[1], vectors[16])),
                "int8_exact_match": bool(np.array_equal(quantized[1], quantized[16])),
                "int8_changed_dimensions": int(np.count_nonzero(quantized[1] != quantized[16])),
            })
            if (number + 1) % 8 == 0:
                report["gpu_observations"].append(observe_gpu("after_pair_" + str(number + 1)))
                print("measured " + str(number + 1) + "/" + str(args.count) + " pairs", flush=True)
        timings = {threads: [row["settings"][str(threads)]["elapsed_ms"] for row in report["rows"]]
                   for threads in (1, 16)}
        report["summary"] = {
            "pairs": len(report["rows"]),
            "thread_latency_ms": {
                str(threads): {"p50": probe.percentile(values, .5), "p95": probe.percentile(values, .95),
                               "p99": probe.percentile(values, .99)}
                for threads, values in timings.items()},
            "int8_exact_pairs": sum(row["int8_exact_match"] for row in report["rows"]),
            "float_exact_pairs": sum(row["float_exact_match"] for row in report["rows"]),
            "minimum_float_cosine": min(row["float_cosine"] for row in report["rows"]),
            "paired_thread1_minus_thread16_ms": {
                "p50": probe.percentile([a - b for a, b in zip(timings[1], timings[16])], .5),
                "p95": probe.percentile([a - b for a, b in zip(timings[1], timings[16])], .95)},
        }
        report["complete"] = len(report["rows"]) == args.count
    except Exception as exc:
        report["complete"] = False
        report["failure"] = {"type": type(exc).__name__}
        if isinstance(exc, RuntimeError):
            report["failure"]["code"] = str(exc)
    finally:
        report["gpu_observations"].append(observe_gpu("before_process_exit"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"complete": report["complete"], "summary": report.get("summary"),
                      "failure": report.get("failure"), "output": str(args.output)}), flush=True)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
