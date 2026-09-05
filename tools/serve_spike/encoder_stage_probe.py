#!/usr/bin/env python3
"""Offline, batch-one profiling of the unchanged live SKILLRET encoder.

Run only after other scheduled benchmarks have stopped. Baseline forwards run
first without wrappers; instrumented and optional torch-profiler passes follow.
These diagnostic timings are not SEARCH/server/client latency admission evidence.
The output contains public query IDs, hashes and statistics, never query text or
vectors. Importing this module does not import torch or load a model.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WARMUP = "Find a skill for validating a local API."


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def union_duration(intervals):
    """Duration of interval union, avoiding nested-wrapper double counting."""
    total, left, right = 0.0, None, None
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError("negative_stage_interval")
        if left is None:
            left, right = start, end
        elif start <= right:
            right = max(right, end)
        else:
            total += right - left
            left, right = start, end
    return total + (right - left if left is not None else 0.0)


class Patches:
    """Restore inherited methods by deleting instance overrides, even on error."""
    def __init__(self):
        self.saved = []

    def set(self, owner, attribute, replacement):
        owned = attribute in vars(owner)
        original = getattr(owner, attribute)
        setattr(owner, attribute, replacement)
        self.saved.append((owner, attribute, owned, original))
        return original

    def close(self):
        while self.saved:
            owner, attribute, owned, original = self.saved.pop()
            if owned:
                setattr(owner, attribute, original)
            else:
                delattr(owner, attribute)


class StageRecorder:
    """Reversible wrappers around installed ST6 entry points in one process.

    CPU duration is host wall time. CUDA events span the current stream, including
    idle gaps during Python dispatch; they are NOT summed active kernel time.
    No intermediate CUDA synchronization is inserted. Events are read only after
    the adapter has returned its numpy vector (the existing device-to-host sync).
    """
    def __init__(self, encoder, torch):
        self.encoder, self.torch = encoder, torch
        self.model = encoder._model
        self.patches = Patches()
        self.active = False
        self.normalize_depth = 0
        self.records = []
        self.token_lengths = []

    def wrap(self, original, stage, cuda=False, normalization_module=False, capture_tokens=False):
        def timed(*args, **kwargs):
            if not self.active:
                return original(*args, **kwargs)
            started = time.perf_counter()
            begin = self.torch.cuda.Event(enable_timing=True) if cuda else None
            end = self.torch.cuda.Event(enable_timing=True) if cuda else None
            if begin is not None:
                begin.record()
            if normalization_module:
                self.normalize_depth += 1
            try:
                result = original(*args, **kwargs)
            finally:
                if normalization_module:
                    self.normalize_depth -= 1
                if end is not None:
                    end.record()
                finished = time.perf_counter()
                self.records.append({"stage": stage, "start": started, "end": finished,
                                     "cuda_begin": begin, "cuda_end": end})
            if capture_tokens:
                mask, ids = result.get("attention_mask"), result.get("input_ids")
                if mask is None or ids is None or mask.device.type != "cpu":
                    raise RuntimeError("expected_cpu_tokenizer_features")
                self.token_lengths.append({"padded_tokens": int(ids.shape[-1]),
                    "nonpadding_tokens": [int(value) for value in mask.sum(dim=1).tolist()]})
            return result
        return timed

    def __enter__(self):
        try:
            children = list(self.model.named_children())
            if [type(module).__name__ for _, module in children] != ["Transformer", "Pooling", "Normalize"]:
                raise RuntimeError("unsupported_sentence_transformer_module_layout")
            st_module = importlib.import_module(type(self.model).__module__)
            for name in ("to", "eval"):
                original = getattr(self.model, name)
                self.patches.set(self.model, name, self.wrap(original, "model_" + name))
            self.patches.set(self.model, "preprocess", self.wrap(
                self.model.preprocess, "preprocess", capture_tokens=True))
            self.patches.set(st_module, "batch_to_device", self.wrap(
                st_module.batch_to_device, "host_to_device", cuda=True))
            for (_, module), stage in zip(children, ("transformer_forward", "pooling", "normalize_module")):
                self.patches.set(module, "forward", self.wrap(module.forward, stage, cuda=True,
                    normalization_module=stage == "normalize_module"))
            tokenizer = children[0][1].tokenizer
            tokenizer_type = type(tokenizer)
            original_call = tokenizer_type.__call__
            timed_call = self.wrap(original_call, "tokenizer")
            def tokenize(instance, *args, **kwargs):
                if instance is tokenizer:
                    return timed_call(instance, *args, **kwargs)
                return original_call(instance, *args, **kwargs)
            self.patches.set(tokenizer_type, "__call__", tokenize)
            functional = self.torch.nn.functional
            original_normalize = functional.normalize
            timed_normalize = self.wrap(original_normalize, "normalize_final", cuda=True)
            def normalize(*args, **kwargs):
                if self.normalize_depth:
                    return original_normalize(*args, **kwargs)
                return timed_normalize(*args, **kwargs)
            self.patches.set(functional, "normalize", normalize)
            return self
        except BaseException:
            self.patches.close()
            raise

    def __exit__(self, *_):
        self.active = False
        self.patches.close()

    def measure(self, query):
        self.records, self.token_lengths = [], []
        self.torch.cuda.synchronize()  # Outside the reported encoder wall time.
        started = time.perf_counter()
        self.active = True
        try:
            vector = self.encoder._encode_uncached([query], is_query=True)
        finally:
            finished = time.perf_counter()
            self.active = False
        cpu, cuda, counts = defaultdict(float), defaultdict(float), defaultdict(int)
        post_return_waits = 0
        for record in self.records:
            stage = record["stage"]
            cpu[stage] += (record["end"] - record["start"]) * 1000
            counts[stage] += 1
            if record["cuda_end"] is not None:
                if not record["cuda_end"].query():
                    post_return_waits += 1
                    record["cuda_end"].synchronize()
                cuda[stage] += record["cuda_begin"].elapsed_time(record["cuda_end"])
        required = ("preprocess", "tokenizer", "host_to_device", "transformer_forward",
                    "pooling", "normalize_module", "normalize_final")
        if any(counts[stage] == 0 for stage in required) or len(self.token_lengths) != 1:
            raise RuntimeError("instrumentation_did_not_observe_required_stages")
        last_compute_end = max(record["end"] for record in self.records
            if record["stage"] in ("transformer_forward", "pooling", "normalize_module", "normalize_final"))
        # The installed ST path now calls .cpu(), makes numpy arrays, and returns.
        # This is not an isolated DMA duration: it includes waiting for the GPU.
        intervals = [(record["start"], record["end"]) for record in self.records]
        intervals.append((last_compute_end, finished))
        total_ms = (finished - started) * 1000
        return vector, {"encoder_wall_ms": total_ms,
            "cpu_stage_wall_ms": dict(cpu), "cuda_stream_span_ms": dict(cuda),
            "stage_calls": dict(counts), "token_lengths_with_prompt": self.token_lengths[0],
            "return_and_sync_cpu_ms": (finished - last_compute_end) * 1000,
            "other_cpu_ms": max(0.0, total_ms - union_duration(intervals) * 1000),
            "event_waits_after_numpy_return": post_return_waits}


def vector_evidence(vector, np, quantize):
    if vector.shape != (1, 1024) or vector.dtype != np.float32 or not np.isfinite(vector).all():
        raise RuntimeError("invalid_live_encoder_vector")
    norms = np.linalg.norm(vector, axis=1, keepdims=True)
    if not (norms > 0).all():
        raise RuntimeError("invalid_live_encoder_norm")
    quantized = quantize(vector / norms)
    return {"float32_sha256": hashlib.sha256(vector.tobytes()).hexdigest(),
            "service_int8_sha256": hashlib.sha256(quantized.tobytes()).hexdigest()}


def distribution(values, percentile):
    return {"count": len(values), "p50": percentile(values, .5),
            "p95": percentile(values, .95), "p99": percentile(values, .99)}


def profile_operators(encoder, torch, queries):
    """Separate heavyweight pass: operator aggregates only, no trace/input export."""
    activities = [torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA]
    torch.cuda.synchronize()
    with torch.profiler.profile(activities=activities, record_shapes=False,
                               profile_memory=False, with_stack=False) as profile:
        for query in queries:
            encoder._encode_uncached([query["query"]], is_query=True)
    rows = []
    for item in profile.key_averages():
        name = str(item.key)
        rows.append({"operator": name, "calls": item.count,
            "self_cpu_ms": item.self_cpu_time_total / 1000,
            "self_device_ms": getattr(item, "self_device_time_total", 0.0) / 1000})
    terms = ("memcpy", "synchron", "scaled_dot", "flash", "efficient_attention", "sdpa", "aten::cpu", "aten::to", "aten::_to_copy")
    relevant = [row for row in rows if any(term in row["operator"].lower() for term in terms)]
    kernels = defaultdict(lambda: {"calls": 0, "device_ms": 0.0})
    for event in profile.events():
        if str(event.device_type).endswith("CUDA"):
            kernels[str(event.name)]["calls"] += 1
            kernels[str(event.name)]["device_ms"] += event.time_range.elapsed_us() / 1000
    return {"query_ids": [query["id"] for query in queries], "operator_count": len(rows),
        "relevant_operators": sorted(relevant, key=lambda row: -row["self_cpu_ms"])[:80],
        "top_self_cpu_operators": sorted(rows, key=lambda row: -row["self_cpu_ms"])[:20],
        "top_self_device_operators": sorted(rows, key=lambda row: -row["self_device_ms"])[:20],
        "top_cuda_kernel_or_transfer_events": [dict(name=name, **values) for name, values in
            sorted(kernels.items(), key=lambda pair: -pair[1]["device_ms"])[:30]],
        "interpretation": "profiler overhead; inclusive/nested events are not additive; no SLO claim"}


def run(count, profiler_count):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    for path in (ROOT, ROOT / "tools/bakeoff", ROOT / "tools/eval"):
        sys.path.insert(0, str(path))
    from tools.serve_spike.probe import load_queries, percentile
    from tools.serve_spike.encoder_probe import observe_gpu
    report = {"schema_version": "e11b-encoder-stages-v1", "complete": False,
        "created_unix": time.time(), "pid": os.getpid(), "count_requested": count,
        "scope": "hybrid shadow stage diagnosis; no quality, server or whole-client admission",
        "query_text_or_vectors_persisted": False, "query_cache_used": False,
        "batch_size": 1, "threads_requested": 16, "rows": [],
        "order": "all uninstrumented forwards, then all instrumented forwards, then optional torch profiler",
        "source_sha256": {name: sha256_file(ROOT / name) for name in (
            "tools/serve_spike/encoder_stage_probe.py", "tools/serve_spike/probe.py",
            "tools/bakeoff/encode.py", "tools/eval/dense_ref.py")},
        "platform": platform.platform(), "python": platform.python_version(),
        "limitations": [
            "CPU stage wall time includes dispatch and any blocking inside that call",
            "CUDA event spans include stream idle gaps; they are not pure active kernel time",
            "Tokenizer is nested inside preprocess; never add both durations",
            "Return/sync includes GPU wait, device-to-host conversion, numpy construction and adapter return",
            "Wrappers and CUDA events add overhead; instrumented wall time is not an SLO measurement",
            "Baseline-before-profile order can drift with temperature and external GPU load",
            "Batch-one measurements do not predict batch-four latency or throughput",
            "No assumptions of 15-25 ms encoder latency or production viability are made"],
        "gpu_observations": [observe_gpu("before_load")],
    }
    phase = "load_workload"
    try:
        queries, workload = load_queries(count)
        report["workload"] = workload
        phase = "load_encoder"
        import numpy as np
        import encode
        import skillret
        from dense_ref import quantize
        torch = encode.torch
        if encode.DEVICE != "cuda":
            raise RuntimeError("cuda_required")
        source = encode._local_model_path(skillret.MODEL_HF_ID, skillret.MODEL_REV)
        if source is None:
            raise RuntimeError("pinned_model_missing")
        started = time.perf_counter()
        encoder = encode.Encoder(skillret.MODEL_HF_ID, skillret.MODEL_REV, batch_size=1)
        encoder._ensure_loaded()
        torch.set_num_threads(16)
        report["model_load_ms"] = (time.perf_counter() - started) * 1000
        if encoder._backend != "sentence-transformers":
            raise RuntimeError("sentence_transformers_backend_required")
        transformer = list(encoder._model.children())[0]
        auto_model = transformer.model
        config = auto_model.config
        report["model"] = {"id": skillret.MODEL_HF_ID, "revision": skillret.MODEL_REV,
            "dtype": str(next(auto_model.parameters()).dtype), "configured_dtype": str(encode.DTYPE),
            "device": encode.DEVICE, "gpu_name": torch.cuda.get_device_name(),
            "use_cache": getattr(config, "use_cache", None),
            "attention_implementation": getattr(config, "_attn_implementation", None),
            "attention_implementation_internal": getattr(config, "_attn_implementation_internal", None),
            "hidden_layers": getattr(config, "num_hidden_layers", None),
            "max_seq_length": encoder._model.max_seq_length,
            "module_types": [type(module).__name__ for module in encoder._model.children()],
            "query_prompt_sha256": hashlib.sha256(encode.QUERY_PROMPTS[skillret.MODEL_HF_ID].encode()).hexdigest(),
            "config_sha256": sha256_file(source / "config.json"),
            "weight_files_sha256": {path.name: sha256_file(path) for path in sorted(source.glob("*.safetensors"))}}
        report["runtime"] = {"versions": {name: importlib.metadata.version(name) for name in
                ("torch", "transformers", "sentence-transformers", "numpy")},
            "cuda_version": torch.version.cuda, "cudnn_version": torch.backends.cudnn.version(),
            "threads_effective": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(),
            "gil_switch_ms": sys.getswitchinterval() * 1000,
            "sdpa_enabled": {name: getattr(torch.backends.cuda, name)() for name in
                ("flash_sdp_enabled", "mem_efficient_sdp_enabled", "math_sdp_enabled", "cudnn_sdp_enabled")
                if hasattr(torch.backends.cuda, name)}}
        report["installed_source_sha256"] = {name: sha256_file(inspect.getfile(type(value)))
            for name, value in (("sentence_transformer", encoder._model), ("transformer_wrapper", transformer),
                                 ("hf_model", auto_model), ("tokenizer", transformer.tokenizer))}
        phase = "warmup"
        for _ in range(2):
            encoder._encode_uncached([WARMUP], is_query=True)
        report["warmup_calls"] = 2
        report["gpu_observations"].append(observe_gpu("after_warmup"))
        phase = "uninstrumented"
        for index, query in enumerate(queries):
            torch.cuda.synchronize()
            started = time.perf_counter()
            vector = encoder._encode_uncached([query["query"]], is_query=True)
            elapsed_ms = (time.perf_counter() - started) * 1000
            report["rows"].append({"query_id": query["id"],
                "query_sha256": hashlib.sha256(query["query"].encode()).hexdigest(),
                "uninstrumented_ms": elapsed_ms, "uninstrumented_vector": vector_evidence(vector, np, quantize)})
            if (index + 1) % 10 == 0:
                print("uninstrumented " + str(index + 1) + "/" + str(count), flush=True)
        report["gpu_observations"].append(observe_gpu("after_uninstrumented"))
        phase = "instrumented"
        with StageRecorder(encoder, torch) as recorder:
            for index, (query, row) in enumerate(zip(queries, report["rows"])):
                vector, evidence = recorder.measure(query["query"])
                row["instrumented"] = evidence
                row["instrumented_vector"] = vector_evidence(vector, np, quantize)
                row["float32_exact"] = row["uninstrumented_vector"]["float32_sha256"] == row["instrumented_vector"]["float32_sha256"]
                row["int8_exact"] = row["uninstrumented_vector"]["service_int8_sha256"] == row["instrumented_vector"]["service_int8_sha256"]
                if (index + 1) % 10 == 0:
                    print("instrumented " + str(index + 1) + "/" + str(count), flush=True)
        report["gpu_observations"].append(observe_gpu("after_instrumented"))
        rows = report["rows"]
        report["summary"] = {
            "uninstrumented_encoder_ms": distribution([row["uninstrumented_ms"] for row in rows], percentile),
            "instrumented_encoder_ms": distribution([row["instrumented"]["encoder_wall_ms"] for row in rows], percentile),
            "float32_exact_queries": sum(row["float32_exact"] for row in rows),
            "int8_exact_queries": sum(row["int8_exact"] for row in rows),
            "return_and_sync_cpu_ms": distribution([row["instrumented"]["return_and_sync_cpu_ms"] for row in rows], percentile),
            "cpu_stage_wall_ms": {stage: distribution([row["instrumented"]["cpu_stage_wall_ms"].get(stage, 0.0) for row in rows], percentile)
                for stage in sorted(set().union(*(row["instrumented"]["cpu_stage_wall_ms"] for row in rows)))},
            "cuda_stream_span_ms": {stage: distribution([row["instrumented"]["cuda_stream_span_ms"].get(stage, 0.0) for row in rows], percentile)
                for stage in sorted(set().union(*(row["instrumented"]["cuda_stream_span_ms"] for row in rows)))}}
        if profiler_count:
            phase = "torch_profiler"
            report["torch_profiler"] = profile_operators(encoder, torch, queries[:profiler_count])
        report["live_forward_calls"] = count * 2 + profiler_count
        report["complete"] = True
        report["numerical_parity"] = all(row["float32_exact"] and row["int8_exact"] for row in rows)
    except Exception as exc:
        report["failure"] = {"phase": phase, "type": type(exc).__name__}
    finally:
        report["gpu_observations"].append(observe_gpu("before_exit"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40, help="Frozen DEV queries, 20..40")
    parser.add_argument("--profiler-count", type=int, default=0, help="Optional separate heavyweight profiler pass, 0..3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 20 <= args.count <= 40:
        parser.error("--count must be in 20..40")
    if not 0 <= args.profiler_count <= 3:
        parser.error("--profiler-count must be in 0..3")
    report = run(args.count, args.profiler_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"complete": report["complete"], "numerical_parity": report.get("numerical_parity"),
                      "failure": report.get("failure"), "output": str(args.output)}), flush=True)
    return 0 if report["complete"] and report.get("numerical_parity") else 1


if __name__ == "__main__":
    raise SystemExit(main())