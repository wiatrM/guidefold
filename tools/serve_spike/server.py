#!/usr/bin/env python3
"""E1.1b loopback-only feasibility service; NOT a production deployment.

Resident shared Router/index + live, uncached SKILLRET query encoding. USE only
hydrates an exact corpus revision: it is not evidence of skill execution/success.
Run --disable-model separately for the resident sparse baseline. No reranker.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_BODY_BYTES = 16_384
MAX_QUERY_CHARS = 4096
POLICY = "shared-router-policy-candidates-score-select-v1"


class ApiError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise ApiError(504, "deadline_exceeded")


def validate_payload(path, payload):
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_payload")
    budget = payload.get("deadline_ms", 1000)
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 5000:
        raise ApiError(400, "invalid_deadline")
    if path == "/v1/search":
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise ApiError(400, "invalid_query")
        if payload.get("profile", "hook") not in ("hook", "interactive"):
            raise ApiError(400, "invalid_profile")
        if not isinstance(payload.get("node", "_root"), str):
            raise ApiError(400, "invalid_node")
    elif path == "/v1/use":
        for key in ("skill_id", "revision"):
            if not isinstance(payload.get(key), str) or not payload[key] or len(payload[key]) > 512:
                raise ApiError(400, "invalid_" + key)
        sid = payload.get("search_id")
        if sid is not None and (not isinstance(sid, str) or len(sid) > 128):
            raise ApiError(400, "invalid_search_id")
    else:
        raise ApiError(404, "not_found")
    return budget


def load_cli_snapshot(path):
    """Hash and execute the SAME bytes, immune to later edits or stale pyc files."""
    from types import ModuleType
    path = Path(path).resolve()
    source = path.read_bytes()
    revision = hashlib.sha256(source).hexdigest()
    name = "guidefold_spike_cli_" + revision[:16]
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module, revision


def install_resident_dense(router):
    """Identical integer dot products; retain one int64 matrix across queries.

    Computes all rows then exposes only visible URNs. Integer operations and the
    existing rank comparison stay exact; sparse scopes may do extra dot work.
    """
    from types import MethodType
    import numpy as np
    started = time.monotonic()
    matrix = np.ascontiguousarray(router.skill_mat, dtype=np.int64)
    matrix.flags.writeable = False
    router.resident_dense_i64 = matrix

    def dense_scores(instance, query, visible):
        qvec = instance.query_vec_of.get(instance._current_qid)
        urns = [u for u in visible if u in instance.row_of]
        if qvec is None or not urns:
            return {}
        dots = instance.resident_dense_i64 @ qvec
        return {u: (int(dots[instance.row_of[u]]), int(instance.index.skill_normsq.get(u, 0)))
                for u in urns}

    router._dense_scores = MethodType(dense_scores, router)
    return {"startup_ms": (time.monotonic() - started) * 1000,
            "resident_bytes": matrix.nbytes, "dtype": str(matrix.dtype),
            "per_query_document_matrix_copy": False, "integer_dot_parity": True}

class Engine:
    def __init__(self, *, cache_dir=None, disable_model=False, device="cuda",
                 optimized=False, cli_path=None, torch_threads=None, pipeline=False,
                 native_dense_rank=False, native_compiler="/usr/bin/g++", native_build_dir=None, gil_switch_ms=None,
                 encoder_process=False, encoder_worker_timeout=5.0):
        if torch_threads is not None and (isinstance(torch_threads, bool) or
                not isinstance(torch_threads, int) or not 1 <= torch_threads <= 256):
            raise ValueError("invalid_torch_threads")
        if gil_switch_ms is not None:
            import math
            if (isinstance(gil_switch_ms, bool) or not isinstance(gil_switch_ms, (int, float))
                    or not math.isfinite(gil_switch_ms) or not 0.1 <= gil_switch_ms <= 10):
                raise ValueError("invalid_gil_switch_ms")
        if native_dense_rank and not optimized:
            raise ValueError("native_dense_rank_requires_optimized")
        if native_dense_rank and disable_model:
            raise ValueError("native_dense_rank_requires_hybrid")
        if encoder_process and not pipeline:
            raise ValueError("encoder_process_requires_pipeline")
        if encoder_process and disable_model:
            raise ValueError("encoder_process_requires_hybrid")
        if (isinstance(encoder_worker_timeout, bool) or not isinstance(encoder_worker_timeout, (int, float))
                or not 0.05 <= encoder_worker_timeout <= 30):
            raise ValueError("invalid_encoder_worker_timeout")
        self.encoder_process = encoder_process
        self.encoder_worker_timeout = encoder_worker_timeout
        self._worker_proxy = None
        self._closed = False
        self._lifecycle_lock = threading.Lock()
        self.ready = False
        self.error = None
        self.backend = "sparse_only" if disable_model else "hybrid_full"
        self.optimized = optimized
        self.pipeline = pipeline
        self.gil_switch_ms_requested = gil_switch_ms
        self.gil_switch_ms_effective = None
        self.native_dense_rank = native_dense_rank
        self.native_compiler = native_compiler
        self.native_build_dir = native_build_dir
        self.cli_path = Path(cli_path) if cli_path else REPO_ROOT / "skills/guidefold/scripts/guidefold"
        self.torch_threads_requested = torch_threads
        self.torch_threads_effective = None
        self.optimizations = {}
        self.device = None if disable_model else device
        self.cache_dir = Path(cache_dir) if cache_dir else REPO_ROOT / "tools/eval/.skillret-cache"
        self.live_encode_calls = 0
        self.initialization_ms = {}
        self._lock = threading.Lock()
        self._encoder_lock = threading.Lock()
        self._counter_lock = threading.Lock()
        self.model = None
        self.snapshot = None
        self.policy_revision = None
        self.model_load_calls = 0
        self.telemetry_errors = 0

    def _worker_health(self):
        if self._worker_proxy is None:
            return None
        state = self._worker_proxy.health()
        with self._counter_lock:
            self.live_encode_calls = state["live_encode_calls"]
        if state["failed"] or (self.ready and not state["alive"]):
            self.ready = False
            self.error = "encoder_worker_unavailable"
        return state

    def close(self):
        with self._lifecycle_lock:
            self._closed = True
            self.ready = False
            proxy = self._worker_proxy
        if proxy is not None:
            proxy.close()

    def status(self):
        worker = self._worker_health()
        optimizations = {name: dict(meta) for name, meta in self.optimizations.copy().items()}
        for meta in optimizations.values():
            if "fallback_reasons" in meta:
                meta["fallback_reasons"] = dict(meta["fallback_reasons"])
        return {"ready": self.ready, "backend": self.backend, "device": self.device,
                "snapshot": self.snapshot, "model": self.model, "policy": POLICY,
                "live_encode_calls": self._encode_count(),
                "model_load_calls": self.model_load_calls,
                "model_load_calls_scope": "api_process",
                "encoder_process": self.encoder_process, "encoder_worker": worker,
                "model_location": "encoder_process" if self.encoder_process else "api_process",
                "optimized": self.optimized, "pipeline": self.pipeline, "optimizations": optimizations,
                "native_dense_rank": self.native_dense_rank,
                "gil_switch_ms_requested": self.gil_switch_ms_requested,
                "gil_switch_ms_effective": self.gil_switch_ms_effective,
                "cli_path": str(self.cli_path.resolve()),
                "torch_threads_requested": self.torch_threads_requested,
                "torch_threads_effective": self.torch_threads_effective,
                "policy_revision": self.policy_revision,
                "initialization_ms": dict(self.initialization_ms), "error": self.error,
                "n_skills": len(getattr(self, "cards", {})),
                "reranker": False, "production_iam": False}

    def _configure_runtime(self):
        # Process-global CPython scheduling experiment. The server owns a
        # dedicated process; default None must not change its existing interval.
        if self.gil_switch_ms_requested is not None:
            sys.setswitchinterval(self.gil_switch_ms_requested / 1000.0)
        self.gil_switch_ms_effective = sys.getswitchinterval() * 1000.0

    def initialize(self):
        start = time.monotonic()
        self._configure_runtime()
        sys.path.insert(0, str(REPO_ROOT / "tools/eval"))
        import skillret
        self.cli, self.policy_revision = load_cli_snapshot(self.cli_path)
        data, self.nodes, self.cards, self.id_to_urn, _, _ = skillret.load_corpus_and_build(self.cli)
        self.skills = {s["id"]: s for s in data["skills"]}
        self.urn_to_id = {u: sid for sid, u in self.id_to_urn.items()}
        if len(self.urn_to_id) != len(self.cards):
            raise ValueError("nonunique_corpus_ids")
        self.snapshot = "skillret:" + skillret.CORPUS_REVISION
        self.revisions = {}
        for sid, urn in self.id_to_urn.items():
            serial = json.dumps(self.cards[urn], sort_keys=True, ensure_ascii=False).encode()
            self.revisions[sid] = hashlib.sha256(serial).hexdigest()
        self.initialization_ms["verified_corpus"] = (time.monotonic() - start) * 1000
        stage = time.monotonic()
        if self.backend == "sparse_only":
            self.index = skillret.build_r0_index(self.cli, self.cards, self.nodes)
            self.router = self.cli.Router(self.index)
        else:
            import numpy as np
            import dense_ref
            meta = json.loads((self.cache_dir / "meta.json").read_text())
            order = json.loads((self.cache_dir / "skill_order.json").read_text())
            matrix_path = self.cache_dir / "skill_vectors.i8.npy"
            matrix = np.load(matrix_path, allow_pickle=False)
            if meta.get("hf_id") != skillret.MODEL_HF_ID or meta.get("revision") != skillret.MODEL_REV:
                raise ValueError("document_cache_model_mismatch")
            if order != sorted(self.cards) or len(set(order)) != len(order):
                raise ValueError("document_cache_corpus_mismatch")
            if matrix.dtype != np.int8 or matrix.shape != (len(order), meta["dims"]):
                raise ValueError("document_cache_shape_mismatch")
            if meta.get("n_skills") != len(order) or (matrix.astype(np.int64) ** 2).sum(axis=1).min() <= 0:
                raise ValueError("document_cache_invalid_vectors")
            self.cache_evidence = {"matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
                "order_sha256": hashlib.sha256(json.dumps(order).encode()).hexdigest(),
                "corpus_files_verified": True, "model_revision_verified": True,
                "text_binding": "legacy_cache_ids_only"}
            self.index, self.router = dense_ref.build_dense_index_and_router(
                self.cli, self.cards, self.nodes, {u: i for i, u in enumerate(order)}, matrix, {})
            self.quantize = dense_ref.quantize
        self.initialization_ms["resident_index"] = (time.monotonic() - stage) * 1000
        if self.optimized:
            sys.path.insert(0, str(REPO_ROOT))
            from tools.serve_spike.sparse_cache import install_bm25_cache
            self.optimizations["bm25"] = install_bm25_cache(self.router)
            if self.backend != "sparse_only":
                self.optimizations["dense"] = install_resident_dense(self.router)
        if self.native_dense_rank:
            from tools.serve_spike.native_rank import prepare_native_rank, install_native_dense_rank
            started_native = time.monotonic()
            prepared = prepare_native_rank(build_dir=self.native_build_dir, compiler=self.native_compiler)
            self.optimizations["native_dense_rank"] = install_native_dense_rank(self.router, prepared=prepared)
            self.initialization_ms["native_dense_rank"] = (time.monotonic() - started_native) * 1000
        if self.backend != "sparse_only" and self.encoder_process:
            self._initialize_encoder_process(skillret, np)
        if self.backend != "sparse_only" and not self.encoder_process:
            stage = time.monotonic()
            # Force offline, even if the caller had explicitly disabled HF offline mode.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            sys.path.insert(0, str(REPO_ROOT / "tools/bakeoff"))
            import encode
            self.initialization_ms["model_import"] = (time.monotonic() - stage) * 1000
            if encode.DEVICE != self.device:
                raise ValueError("requested_device_unavailable")
            self.encoder = encode.Encoder(skillret.MODEL_HF_ID, skillret.MODEL_REV, batch_size=1)
            if encode._local_model_path(skillret.MODEL_HF_ID, skillret.MODEL_REV) is None:
                raise ValueError("pinned_local_model_missing")
            self._verify_text_cache(encode, skillret, np)
            stage = time.monotonic()
            self.encoder._ensure_loaded()
            self.model_load_calls += 1
            if self.torch_threads_requested is not None:
                encode.torch.set_num_threads(self.torch_threads_requested)
            self.torch_threads_effective = encode.torch.get_num_threads()
            self.initialization_ms["model_load"] = (time.monotonic() - stage) * 1000
            self.model = {"id": skillret.MODEL_HF_ID, "revision": skillret.MODEL_REV,
                          "dtype": str(encode.DTYPE), "cache_evidence": self.cache_evidence}
            stage = time.monotonic()
            warm = self.encoder._encode_uncached(["Find a skill for validating a local API."], is_query=True)
            if (warm.shape != (1, self.router.skill_mat.shape[1]) or not np.isfinite(warm).all() or not np.linalg.norm(warm) > 0):
                raise ValueError("model_dimension_mismatch")
            self.initialization_ms["model_warmup"] = (time.monotonic() - stage) * 1000
        self.initialization_ms["total"] = (time.monotonic() - start) * 1000
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("engine_closed_during_initialization")
            self.ready = True

    def _initialize_encoder_process(self, skillret, np):
        from types import SimpleNamespace
        sys.path.insert(0, str(REPO_ROOT))
        from tools.serve_spike.encoder_worker import EncoderProcessProxy
        started = time.monotonic()
        config = {"device": self.device, "model_id": skillret.MODEL_HF_ID,
                  "model_revision": skillret.MODEL_REV, "dims": self.router.skill_mat.shape[1],
                  "torch_threads": self.torch_threads_requested,
                  "worker_timeout_s": self.encoder_worker_timeout}
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("engine_closed_during_initialization")
            self._worker_proxy = EncoderProcessProxy(config)
        metadata = self._worker_proxy.start()
        self.initialization_ms["encoder_process_startup"] = (time.monotonic() - started) * 1000
        self.torch_threads_effective = metadata["torch_threads_effective"]
        # Same content-addressed cache key as encode.py, without importing
        # encode/torch into the API process. The owned child supplies its path.
        cache_adapter = SimpleNamespace(
            _cache_dir=lambda *_: Path(metadata["embedding_cache_dir"]),
            _cache_key=lambda text, is_query: hashlib.sha256(json.dumps(
                {"text": text, "is_query": is_query}, sort_keys=True).encode("utf-8")).hexdigest())
        self._verify_text_cache(cache_adapter, skillret, np)
        self.model = {"id": skillret.MODEL_HF_ID, "revision": skillret.MODEL_REV,
                      "dtype": metadata["dtype"], "cache_evidence": self.cache_evidence,
                      "location": "encoder_process", "worker_pid": metadata["pid"]}

    def _verify_text_cache(self, encode, skillret, np):
        # Legacy aggregate metadata binds IDs, not source text. Verify every int8
        # document row against its content-addressed, model-pinned float cache.
        # This is startup-only IO and uses no query vectors or network access.
        started = time.monotonic()
        directory = encode._cache_dir(skillret.MODEL_HF_ID, skillret.MODEL_REV)
        for urn, row in self.router.row_of.items():
            skill = self.skills[self.urn_to_id[urn]]
            text = (skill.get("description") or "") + "\n\n" + (skill.get("body") or "")
            path = directory / (encode._cache_key(text, False) + ".npy")
            vec = np.load(path, allow_pickle=False).astype(np.float32)
            if vec.shape != (self.router.skill_mat.shape[1],):
                raise ValueError("invalid_document_float_cache_shape")
            # Match Encoder.encode's axis reduction exactly: a 1D norm uses a
            # different float reduction and can cross an int8 rounding boundary.
            norm = np.linalg.norm(vec[None, :], axis=1, keepdims=True)
            if not np.isfinite(vec).all() or norm[0, 0] <= 0:
                raise ValueError("invalid_document_float_cache")
            expected = self.quantize(vec[None, :] / norm)[0]
            if not np.array_equal(expected, self.router.skill_mat[row]):
                raise ValueError("document_cache_text_mismatch")
        self.cache_evidence["text_binding"] = "all_rows_verified_against_content_addressed_float_cache"
        self.initialization_ms["cache_text_verification"] = (time.monotonic() - started) * 1000

    def _encode_count(self):
        with self._counter_lock:
            return self.live_encode_calls

    def _encode_query_vector(self, query, deadline=None):
        # The caller holds the encoder lock in pipeline mode, or the single
        # engine lock in reference mode. Batch size remains one in both modes.
        if self.encoder_process:
            from tools.serve_spike.encoder_worker import EncoderWorkerError, EncoderDeadlineExceeded
            try:
                vec = self._worker_proxy.encode(query, deadline)
            except EncoderDeadlineExceeded as exc:
                raise ApiError(504, "deadline_exceeded") from exc
            except EncoderWorkerError as exc:
                self.ready = False
                self.error = "encoder_worker_unavailable"
                raise ApiError(503, "encoder_worker_unavailable") from exc
            finally:
                self._worker_health()
        else:
            vec = self.encoder._encode_uncached([query], is_query=True)
            with self._counter_lock:
                self.live_encode_calls += 1
        import numpy as np
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        if not np.isfinite(vec).all() or not (norms > 0).all():
            raise ApiError(503, "encoder_invalid_output")
        return self.quantize(vec / norms)[0].astype("int64")

    def _pipeline_encode(self, query, deadline, stages):
        waited = time.monotonic()
        if not self._encoder_lock.acquire(timeout=max(0, deadline - waited)):
            raise ApiError(504, "deadline_exceeded")
        stages["encoder_queue"] = (time.monotonic() - waited) * 1000
        try:
            check_deadline(deadline)
            started = time.monotonic()
            qvec = self._encode_query_vector(query, deadline)
            stages["encode"] = (time.monotonic() - started) * 1000
            check_deadline(deadline)
            return qvec  # Request-local int64 copy; never bind Router state here.
        finally:
            # Release BEFORE this request even attempts the Router lock, so
            # the next GPU forward can overlap the previous request's CPU work.
            self._encoder_lock.release()

    def search(self, payload, deadline):
        validate_payload("/v1/search", payload)
        self._worker_health()
        if not self.ready:
            raise ApiError(503, "not_ready")
        query, node = payload["query"], payload.get("node", "_root")
        if node not in self.nodes:
            raise ApiError(400, "invalid_node")
        stages = {}
        qvec = None
        if self.pipeline and self.backend != "sparse_only":
            qvec = self._pipeline_encode(query, deadline, stages)
        waited = time.monotonic()
        if not self._lock.acquire(timeout=max(0, deadline - waited)):
            raise ApiError(504, "deadline_exceeded")
        stages["router_queue" if self.pipeline else "engine_queue"] = (time.monotonic() - waited) * 1000
        try:
            check_deadline(deadline)
            if self.backend != "sparse_only":
                if not self.pipeline:
                    stage = time.monotonic()
                    qvec = self._encode_query_vector(query, deadline)
                    stages["encode"] = (time.monotonic() - stage) * 1000
                    check_deadline(deadline)
                # Binding and cleanup happen only while owning the Router lock.
                self.router.query_vec_of = {"live": qvec}
                self.router._current_qid = "live"
            stage = time.monotonic()
            admissible, drops = self.router.policy_filter(node, query)
            stages["policy"] = (time.monotonic() - stage) * 1000
            check_deadline(deadline)
            stage = time.monotonic()
            candidates = self.router.candidates(query, node)
            stages["candidates"] = (time.monotonic() - stage) * 1000
            check_deadline(deadline)
            stage = time.monotonic()
            scored = self.router.score(candidates, query, node)
            stages["score"] = (time.monotonic() - stage) * 1000
            check_deadline(deadline)
            stage = time.monotonic()
            selected = self.router.select(scored, k=4, admissible=set(admissible))
            stages["select"] = (time.monotonic() - stage) * 1000
            check_deadline(deadline)
            def card(urn):
                sid = self.urn_to_id[urn]
                c = self.cards[urn]
                return {"skill_id": sid, "urn": urn, "revision": self.revisions[sid],
                        "name": c["name"], "description": c["description"]}
            return {"search_id": str(uuid.uuid4()), "backend": self.backend,
                    "snapshot": self.snapshot, "model": self.model, "policy": POLICY,
                    "policy_revision": self.policy_revision, "optimized": self.optimized, "pipeline": self.pipeline,
                    "native_dense_rank": self.native_dense_rank, "encoder_process": self.encoder_process,
                    "gil_switch_ms_effective": self.gil_switch_ms_effective,
                    "torch_threads_effective": self.torch_threads_effective,
                    "profile": payload.get("profile", "hook"), "reranker": False,
                    "ranked": [dict(card(c["urn"]), score=c["score"]) for c in scored if c["urn"] in admissible][:10],
                    "cards": [card(c["urn"]) for c in selected],
                    "composition": {"status": "not_evaluated", "incomplete": None},
                    "abstained": not bool(selected), "policy_drops": len(drops),
                    "stages_ms": stages, "live_encode_calls": self._encode_count()}
        finally:
            if self.backend != "sparse_only":
                self.router.query_vec_of = {}
            self._lock.release()

    def use(self, payload, deadline):
        validate_payload("/v1/use", payload)
        check_deadline(deadline)
        self._worker_health()
        if not self.ready:
            raise ApiError(503, "not_ready")
        sid = payload["skill_id"]
        if sid not in self.id_to_urn:
            raise ApiError(404, "skill_not_found")
        if payload["revision"] != self.revisions[sid]:
            raise ApiError(409, "revision_mismatch")
        c = self.cards[self.id_to_urn[sid]]
        if c["status"] != "active":
            raise ApiError(409, "skill_not_active")
        body = c["_body"]
        return {"status": "hydrated", "execution_observed": False, "skill_id": sid,
                "revision": self.revisions[sid], "search_id": payload.get("search_id"),
                "search_id_verified": False, "current_state": c["status"],
                "snapshot": self.snapshot, "body": body,
                "checksum": hashlib.sha256(body.encode()).hexdigest()}


class SpikeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def emit(self, record):
        if self.log_file is not None:
            with self.log_lock:
                try:
                    with self.log_file.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(record, sort_keys=True) + "\n")
                except OSError:
                    self.telemetry_errors += 1

    def process_request(self, request, client_address):
        if not self.workers.acquire(blocking=False):
            request.sendall(b"HTTP/1.0 429 Too Many Requests\r\nContent-Length: 22\r\n\r\n{\"error\":\"overloaded\"}")
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.workers.release()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass  # Never write request text/headers or the bearer token to logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health/ready":
            self.reply(404, {"error": "not_found"})
            return
        state = dict(self.server.engine.status(), telemetry_errors=self.server.telemetry_errors)
        self.reply(200 if self.server.engine.ready else 503, state)

    def do_POST(self):
        started = time.monotonic()
        status, result, acquired = 500, {"error": "internal_error"}, False
        record = {"event": "request", "request_id": str(uuid.uuid4()),
                  "endpoint": self.path if self.path in ("/v1/search", "/v1/use") else "unknown"}
        try:
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode()):
                raise ApiError(401, "unauthorized")
            if self.path not in ("/v1/search", "/v1/use"):
                raise ApiError(404, "not_found")
            if self.headers.get("Transfer-Encoding"):
                raise ApiError(400, "unsupported_transfer_encoding")
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                raise ApiError(400, "invalid_content_length")
            if size < 0:
                raise ApiError(411, "content_length_required")
            if size > MAX_BODY_BYTES:
                raise ApiError(413, "payload_too_large")
            acquired = self.server.slots.acquire(blocking=False)
            if not acquired:
                raise ApiError(429, "overloaded")
            body = self.rfile.read(size)
            if len(body) != size:
                raise ApiError(400, "incomplete_payload")
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "invalid_json")
            budget = validate_payload(self.path, payload)
            deadline = started + budget / 1000
            check_deadline(deadline)
            if not self.server.engine.ready:
                raise ApiError(503, "not_ready")
            call = self.server.engine.search if self.path == "/v1/search" else self.server.engine.use
            result = call(payload, deadline)
            check_deadline(deadline)
            status = 200
            for key in ("search_id", "skill_id", "revision", "snapshot", "backend", "policy",
                        "profile", "stages_ms", "live_encode_calls", "policy_revision", "optimized", "pipeline", "native_dense_rank", "encoder_process", "gil_switch_ms_effective", "torch_threads_effective", "execution_observed",
                        "search_id_verified", "current_state"):
                if key in result:
                    record[key] = result[key]
            if self.path == "/v1/search":
                record["event"] = "search_completed"
                record["returned_skill_ids"] = [c["skill_id"] for c in result.get("cards", [])]
            else:
                record["event"] = "use_hydrated"
        except ApiError as exc:
            status, result = exc.status, {"error": exc.code}
        except (TimeoutError, OSError):
            status, result = 408, {"error": "request_timeout"}
        except Exception:
            status, result = 500, {"error": "internal_error"}
        finally:
            if acquired:
                self.server.slots.release()
        record.update(status=status, total_ms=(time.monotonic() - started) * 1000,
                      timestamp=time.time())
        if status >= 400:
            record["error"] = result["error"]
        self.server.emit(record)
        try:
            self.reply(status, result)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass


def make_server(engine, token, host="127.0.0.1", port=0, max_inflight=2, log_file=None):
    if host != "127.0.0.1":
        raise ValueError("spike_requires_loopback")
    if not isinstance(token, str) or len(token) < 16:
        raise ValueError("token_requires_at_least_16_characters")
    if not isinstance(max_inflight, int) or not 1 <= max_inflight <= 32:
        raise ValueError("invalid_max_inflight")
    server = SpikeHTTPServer((host, port), Handler)
    server.engine, server.token = engine, token
    server.slots, server.log_lock = threading.BoundedSemaphore(max_inflight), threading.Lock()
    server.log_file = Path(log_file) if log_file else None
    server.telemetry_errors = 0
    server.workers = threading.BoundedSemaphore(max_inflight + 4)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--disable-model", action="store_true")
    parser.add_argument("--optimized", action="store_true", help="Enable exact resident sparse/dense caches")
    parser.add_argument("--pipeline", action="store_true", help="Overlap batch-one encoding with prior request routing")
    parser.add_argument("--encoder-process", action="store_true", help="Own a spawn-only encoder process; requires --pipeline and a model")
    parser.add_argument("--encoder-worker-timeout", type=float, default=5.0, help="In-flight worker watchdog seconds (0.05..30); independent of query deadline")
    parser.add_argument("--native-dense-rank", action="store_true", help="Use exact compiled dense ranking; requires --optimized and a model")
    parser.add_argument("--gil-switch-ms", type=float, help="Process-global CPython switch interval (0.1..10 ms); default unchanged")
    parser.add_argument("--native-compiler", default="/usr/bin/g++")
    parser.add_argument("--native-build-dir", type=Path)
    parser.add_argument("--cli-path", type=Path, help="Load a pinned CLI source snapshot")
    parser.add_argument("--torch-threads", type=int, help="Override CPU torch threads after model loading")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--max-inflight", type=int, default=4)
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    engine = Engine(cache_dir=args.cache_dir, disable_model=args.disable_model, device=args.device,
                    optimized=args.optimized, cli_path=args.cli_path, torch_threads=args.torch_threads, pipeline=args.pipeline,
                    native_dense_rank=args.native_dense_rank, native_compiler=args.native_compiler, native_build_dir=args.native_build_dir,
                    gil_switch_ms=args.gil_switch_ms, encoder_process=args.encoder_process,
                    encoder_worker_timeout=args.encoder_worker_timeout)
    server = make_server(engine, token, args.host, args.port, args.max_inflight, args.log_file)
    def initialize():
        try:
            engine.initialize()
            server.emit({"event": "ready", **engine.status(), "timestamp": time.time()})
            print(json.dumps(engine.status()), flush=True)
        except (Exception, SystemExit) as exc:
            engine.close()
            engine.error = type(exc).__name__
            server.emit({"event": "initialization_failed", "error": engine.error})
            print("Initialization failed: " + str(exc), file=sys.stderr, flush=True)
    import signal
    def stop_on_signal(signum, frame):
        raise KeyboardInterrupt
    previous_sigterm = signal.signal(signal.SIGTERM, stop_on_signal)
    threading.Thread(target=initialize, daemon=True).start()
    print(json.dumps({"listening": "http://" + args.host + ":" + str(server.server_port),
                      "local_feasibility_spike": True}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close()
        server.server_close()
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    main()