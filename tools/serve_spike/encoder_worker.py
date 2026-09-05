"""Owned spawn-only batch-one encoder worker; this module imports no torch.

Normal query deadlines do not preempt an in-flight forward. The parent drains
one matching reply under its RPC lock, then its normal deadline check can emit
504. Only crash, protocol failure or a separate finite watchdog eject the worker.
"""
from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


class EncoderWorkerError(RuntimeError):
    pass


class EncoderDeadlineExceeded(TimeoutError):
    pass


def _parent_death_guard(parent_pid):
    # PR_SET_PDEATHSIG follows the creating THREAD, which is our short-lived
    # initialization thread. Monitor process parentage instead (also on SIGKILL).
    if not sys.platform.startswith("linux"):
        raise RuntimeError("encoder_worker_requires_linux_parent_guard")
    def watch_parent():
        while os.getppid() == parent_pid:
            time.sleep(0.1)
        os._exit(1)
    if os.getppid() != parent_pid:
        os._exit(1)
    threading.Thread(target=watch_parent, name="encoder-parent-watch", daemon=True).start()


def _worker_entry(connection, config, parent_pid, target):
    try:
        _parent_death_guard(parent_pid)
        target(connection, config)
    except BaseException as exc:
        try:
            connection.send({"type": "startup_error", "error": type(exc).__name__})
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


def encoder_worker_main(connection, config):
    """GPU imports and weights exist only in this spawned process."""
    started = time.monotonic()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(ROOT / "tools/bakeoff"))
    import encode
    import numpy as np

    imported = time.monotonic()
    if encode.DEVICE != config.get("device", "cuda"):
        raise RuntimeError("encoder_worker_requested_device_unavailable")
    hf_id, revision = config["model_id"], config["model_revision"]
    if encode._local_model_path(hf_id, revision) is None:
        raise RuntimeError("encoder_worker_pinned_model_missing")
    encoder = encode.Encoder(hf_id, revision, batch_size=1)
    encoder._ensure_loaded()
    if config.get("torch_threads") is not None:
        encode.torch.set_num_threads(config["torch_threads"])
    loaded = time.monotonic()
    warm = encoder._encode_uncached(["Find a skill for validating a local API."], is_query=True)
    if (warm.shape != (1, config["dims"]) or not np.isfinite(warm).all()
            or not np.linalg.norm(warm) > 0):
        raise RuntimeError("encoder_worker_invalid_warmup")
    ready = time.monotonic()
    metadata = {
        "pid": os.getpid(), "parent_pid": os.getppid(), "start_method": "spawn",
        "parent_death_guard": "parent_pid_watchdog_100ms", "device": encode.DEVICE,
        "model_id": hf_id, "model_revision": revision, "dtype": str(encode.DTYPE),
        "dims": config["dims"], "batch_size": 1, "vector_format": "float32-le",
        "model_load_calls": 1, "warmup_calls": 1,
        "torch_threads_effective": encode.torch.get_num_threads(),
        "gil_switch_ms_effective": sys.getswitchinterval() * 1000,
        "embedding_cache_dir": str(encoder.cache_dir),
        "startup_ms": {"import": (imported - started) * 1000,
            "model_load": (loaded - imported) * 1000, "model_warmup": (ready - loaded) * 1000,
            "total": (ready - started) * 1000},
        "live_encode_calls": 0, "query_cache": False,
    }
    connection.send({"type": "ready", "metadata": metadata})
    calls = 0
    while True:
        try:
            request = connection.recv()
        except EOFError:
            return
        if not isinstance(request, dict):
            return
        if request.get("type") == "stop":
            return
        request_id = request.get("request_id")
        if (request.get("type") != "encode" or type(request_id) is not int
                or not isinstance(request.get("query"), str)
                or len(request["query"]) > 4096):
            connection.send({"type": "fatal", "request_id": request_id,
                             "error": "invalid_request", "live_encode_calls": calls})
            return
        if time.monotonic() >= request["deadline"]:
            connection.send({"type": "expired", "request_id": request_id,
                             "live_encode_calls": calls})
            continue
        try:
            # Match the reference adapter. The parent still performs its exact
            # extra float32 normalization and int8 quantization after this IPC.
            vec = encoder._encode_uncached([request["query"]], is_query=True)
            calls += 1
            if vec.shape != (1, config["dims"]) or not np.isfinite(vec).all():
                raise RuntimeError("invalid_encoder_output")
            connection.send({"type": "encoded", "request_id": request_id,
                "vector_bytes": np.asarray(vec, dtype="<f4").tobytes(), "dims": config["dims"],
                "live_encode_calls": calls})
        except Exception as exc:
            connection.send({"type": "fatal", "request_id": request_id,
                             "error": type(exc).__name__, "live_encode_calls": calls})
            return


class EncoderProcessProxy:
    def __init__(self, config, *, worker_target=None):
        self.config = dict(config)
        self.worker_target = worker_target or encoder_worker_main
        watchdog = self.config.get("worker_timeout_s", 5.0)
        if isinstance(watchdog, bool) or not isinstance(watchdog, (int, float)) or not 0.05 <= watchdog <= 30:
            raise ValueError("invalid_encoder_worker_timeout")
        self.watchdog = float(watchdog)
        self._rpc_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._process = None
        self._connection = None
        self._closed = False
        self._failed = None
        self._started = False
        self._request_id = 0
        self._live_calls = 0
        self._metadata = {}

    def start(self, timeout=120):
        with self._state_lock:
            if self._closed or self._started:
                raise EncoderWorkerError("encoder_worker_not_startable")
            context = multiprocessing.get_context("spawn")
            parent_conn, child_conn = context.Pipe(duplex=True)
            self._connection = parent_conn
            self._process = context.Process(target=_worker_entry,
                args=(child_conn, self.config, os.getpid(), self.worker_target), daemon=True)
            try:
                self._process.start()
                self._started = True
            finally:
                child_conn.close()
        try:
            if not parent_conn.poll(timeout):
                raise EncoderWorkerError("encoder_worker_startup_timeout")
            reply = parent_conn.recv()
            if (not isinstance(reply, dict) or reply.get("type") != "ready"
                    or not isinstance(reply.get("metadata"), dict)):
                raise EncoderWorkerError("encoder_worker_startup_failed")
            metadata = reply["metadata"]
            if type(metadata.get("dims")) is not int or metadata["dims"] <= 0:
                raise EncoderWorkerError("encoder_worker_invalid_dimensions")
            with self._state_lock:
                self._metadata = dict(metadata)
            return dict(metadata)
        except (OSError, EOFError, ValueError, EncoderWorkerError) as exc:
            self._fail(str(exc) if isinstance(exc, EncoderWorkerError) else "encoder_worker_startup_disconnected")
            raise EncoderWorkerError(self._failed) from exc

    def _stop_process(self):
        with self._close_lock:
            connection, process = self._connection, self._process
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass
            if process is not None and process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1.0)

    def _fail(self, reason):
        with self._state_lock:
            self._failed = self._failed or reason
        self._stop_process()

    def health(self):
        with self._state_lock:
            alive = self._process is not None and self._process.is_alive()
            if self._started and not self._closed and not alive and self._failed is None:
                self._failed = "encoder_worker_died"
            return {"pid": self._process.pid if self._process is not None else None,
                    "alive": alive, "failed": self._failed, "closed": self._closed,
                    "live_encode_calls": self._live_calls, "metadata": dict(self._metadata),
                    "worker_watchdog_seconds": self.watchdog}

    def encode(self, query, deadline):
        if not isinstance(query, str) or len(query) > 4096:
            raise ValueError("invalid_encoder_query")
        if time.monotonic() >= deadline:
            raise EncoderDeadlineExceeded("deadline_exceeded")
        if not self._rpc_lock.acquire(timeout=max(0, deadline - time.monotonic())):
            raise EncoderDeadlineExceeded("deadline_exceeded")
        try:
            if time.monotonic() >= deadline:
                raise EncoderDeadlineExceeded("deadline_exceeded")
            state = self.health()
            if not state["alive"] or state["failed"] or state["closed"]:
                raise EncoderWorkerError(state["failed"] or "encoder_worker_unavailable")
            self._request_id += 1
            request_id = self._request_id
            watchdog = threading.Timer(self.watchdog, self._fail, args=("encoder_worker_watchdog_expired",))
            watchdog.daemon = True
            watchdog.start()
            try:
                self._connection.send({"type": "encode", "request_id": request_id,
                                       "query": query, "deadline": deadline})
                # Deliberately independent from the query deadline: drain the one
                # outstanding reply before another query can be dispatched.
                if not self._connection.poll(self.watchdog):
                    raise EncoderWorkerError("encoder_worker_watchdog_expired")
                reply = self._connection.recv()
                if not isinstance(reply, dict) or reply.get("request_id") != request_id:
                    raise EncoderWorkerError("encoder_worker_response_mismatch")
                calls = reply.get("live_encode_calls")
                if type(calls) is not int or calls < self._live_calls:
                    raise EncoderWorkerError("encoder_worker_invalid_counter")
                with self._state_lock:
                    self._live_calls = calls
                if reply.get("type") == "expired":
                    raise EncoderDeadlineExceeded("deadline_exceeded")
                if reply.get("type") != "encoded":
                    raise EncoderWorkerError("encoder_worker_inference_failed")
                dims = self._metadata["dims"]
                vector = reply.get("vector_bytes")
                if reply.get("dims") != dims or not isinstance(vector, bytes) or len(vector) != dims * 4:
                    raise EncoderWorkerError("encoder_worker_invalid_vector")
                import numpy as np
                result = np.frombuffer(vector, dtype="<f4").copy().reshape(1, dims)
                if not np.isfinite(result).all():
                    raise EncoderWorkerError("encoder_worker_invalid_vector")
                watchdog.cancel()
                with self._state_lock:
                    if self._failed or self._closed:
                        raise EncoderWorkerError(self._failed or "encoder_worker_closed")
                return result
            except EncoderDeadlineExceeded:
                raise
            except (OSError, EOFError, ValueError, EncoderWorkerError) as exc:
                reason = str(exc) if isinstance(exc, EncoderWorkerError) else "encoder_worker_disconnected"
                self._fail(reason)
                raise EncoderWorkerError(self._failed) from exc
            finally:
                watchdog.cancel()
        finally:
            self._rpc_lock.release()

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        self._stop_process()