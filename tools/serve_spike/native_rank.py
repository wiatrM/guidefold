"""Optional exact C++ dense ranking for a single supplied Router instance.

Compilation is an explicit prepare/startup operation, never a request operation.
Only candidates' function-global _dense_rank binding is changed in an instance
copy; the shared CLI module and all other Router instances remain untouched.
"""
from __future__ import annotations

from array import array
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
import types
import uuid

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("native_dense_rank.cpp")
DEFAULT_BUILD_DIR = ROOT / ".guidefold" / "serve-spike" / "native"
BOUND = 1 << 40
MAX_ITEMS = 1_000_000
FLAGS = ("-std=c++17", "-O3", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_native_rank(build_dir=None, compiler="/usr/bin/g++"):
    """Explicitly compile/reuse an identified local .so; fail before readiness.

    Source, compiler executable, flags and platform identify the build. Reuse
    checks the recorded library digest. Requires Linux/g++; no runtime download.
    """
    started = time.perf_counter()
    if not sys.platform.startswith("linux"):
        raise RuntimeError("native_dense_rank_requires_linux")
    candidate = shutil.which(str(compiler))
    if candidate is None:
        raise RuntimeError("native_dense_rank_compiler_unavailable")
    compiler_path = Path(candidate).resolve()
    try:
        version = subprocess.run([str(compiler_path), "--version"], check=True,
            capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        raise RuntimeError("native_dense_rank_compiler_probe_failed") from exc
    identity = {
        "source_sha256": _sha(SOURCE), "compiler_sha256": _sha(compiler_path),
        "compiler_path": str(compiler_path), "compiler_version": version,
        "compiler_flags": list(FLAGS), "platform": sys.platform,
        "machine": platform.machine(), "abi_version": 1,
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = Path(build_dir) if build_dir is not None else DEFAULT_BUILD_DIR
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / ("dense_rank_" + key[:20] + ".so")
    manifest = directory / ("dense_rank_" + key[:20] + ".json")
    existing = None
    if library.exists() and manifest.exists():
        try:
            saved = json.loads(manifest.read_text())
            if saved.get("build_identity") == identity and saved.get("library_sha256") == _sha(library):
                existing = saved
        except (OSError, ValueError):
            pass
    if existing is None:
        temporary = directory / (library.name + ".tmp-" + uuid.uuid4().hex)
        try:
            subprocess.run([str(compiler_path), *FLAGS, str(SOURCE), "-o", str(temporary)],
                check=True, capture_output=True, text=True, timeout=60)
            library_sha = _sha(temporary)
            os.replace(temporary, library)
            saved = {"build_identity": identity, "library_sha256": library_sha}
            manifest.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n")
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("native_dense_rank_compile_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)
    else:
        library_sha = existing["library_sha256"]
    return {
        **identity, "build_identity_sha256": key, "library_path": str(library),
        "library_sha256": library_sha, "build_reused": existing is not None,
        "prepare_ms": (time.perf_counter() - started) * 1000,
    }


class NativeDenseRank:
    def __init__(self, original, prepared):
        started = time.perf_counter()
        if _sha(prepared["library_path"]) != prepared.get("library_sha256"):
            raise ValueError("native_dense_rank_library_digest_mismatch")
        self.original = original
        self.library = ctypes.CDLL(prepared["library_path"])
        abi = self.library.guidefold_dense_rank_abi
        abi.argtypes, abi.restype = [], ctypes.c_int
        if abi() != 1:
            raise ValueError("native_dense_rank_abi_mismatch")
        self.kernel = self.library.guidefold_dense_rank
        self.kernel.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64),
                                ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.kernel.restype = ctypes.c_int
        self._counter_lock = threading.Lock()
        self.metadata = {
            **prepared, "kind": "exact_int128_native_dense_rank",
            "load_ms": (time.perf_counter() - started) * 1000,
            "absolute_dot_max": BOUND, "norm_min_exclusive": 0, "norm_max": BOUND,
            "max_items": MAX_ITEMS, "native_calls": 0, "fallback_calls": 0,
            "empty_calls": 0, "request_time_compilation": False,
            "fallback_reasons": {key: 0 for key in (
                "unsupported_keys", "unsupported_values", "numeric_bounds",
                "too_many_items", "native_status")},
        }

    def _fallback(self, scores, reason):
        with self._counter_lock:
            self.metadata["fallback_calls"] += 1
            self.metadata["fallback_reasons"][reason] += 1
        return self.original(scores)

    def rank(self, scores):
        count = len(scores)
        if not count:
            with self._counter_lock:
                self.metadata["empty_calls"] += 1
            return []
        if count > MAX_ITEMS:
            return self._fallback(scores, "too_many_items")
        if not all(isinstance(urn, str) for urn in scores):
            return self._fallback(scores, "unsupported_keys")
        urns = sorted(scores)
        dots, norms = array("q"), array("q")
        if dots.itemsize != 8:
            return self._fallback(scores, "unsupported_values")
        for urn in urns:
            value = scores[urn]
            if (not isinstance(value, (tuple, list)) or len(value) != 2
                    or type(value[0]) is not int or type(value[1]) is not int):
                return self._fallback(scores, "unsupported_values")
            dot, norm = value
            if dot < -BOUND or dot > BOUND or norm <= 0 or norm > BOUND:
                return self._fallback(scores, "numeric_bounds")
            dots.append(dot)
            norms.append(norm)
        dot_pointer = (ctypes.c_int64 * count).from_buffer(dots)
        norm_pointer = (ctypes.c_int64 * count).from_buffer(norms)
        output = (ctypes.c_size_t * count)()
        status = self.kernel(dot_pointer, norm_pointer, count, output)
        if status != 0:
            return self._fallback(scores, "native_status")
        with self._counter_lock:
            self.metadata["native_calls"] += 1
        return [urns[i] for i in output]


def install_native_dense_rank(router, prepared):
    """Attach to one Router using a copy of candidates' globals, not a module patch.

    Call prepare_native_rank explicitly first. No compile, rebuild, subprocess,
    file lookup or library reload occurs when rank() handles a request.
    """
    if hasattr(router, "native_rank_adapter"):
        raise ValueError("native dense rank is already installed on this router")
    original_candidates = router.candidates
    function = getattr(original_candidates, "__func__", None)
    if not isinstance(function, types.FunctionType):
        raise TypeError("native_rank_requires_bound_Python_candidates")
    original_rank = function.__globals__.get("_dense_rank")
    if not callable(original_rank) or "_dense_rank" not in function.__code__.co_names:
        raise TypeError("native_rank_requires_shared_dense_rank_binding")
    adapter = NativeDenseRank(original_rank, prepared)
    namespace = dict(function.__globals__)
    namespace["_dense_rank"] = adapter.rank
    cloned = types.FunctionType(function.__code__, namespace, function.__name__,
                                function.__defaults__, function.__closure__)
    cloned.__kwdefaults__ = function.__kwdefaults__
    cloned.__annotations__ = dict(function.__annotations__)
    cloned.__dict__.update(function.__dict__)
    cloned.__doc__, cloned.__module__, cloned.__qualname__ = function.__doc__, function.__module__, function.__qualname__
    router.candidates = types.MethodType(cloned, router)
    router.native_rank_adapter = adapter
    router.native_rank_metadata = adapter.metadata
    return adapter.metadata