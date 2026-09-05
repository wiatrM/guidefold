"""Deterministic lock/barrier tests for overlapping encoder and Router work.

No model, GPU, sleeps, or latency assertions. Events hold real critical sections;
bounded waits only fail a deadlocked test instead of leaving threads behind.
"""
import importlib.util
from pathlib import Path
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location("e11b_pipeline_service", ROOT / "tools/serve_spike/server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ObservedLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.b_attempted = threading.Event()

    def acquire(self, *args, **kwargs):
        if threading.current_thread().name == "req-B":
            self.b_attempted.set()
        return self.lock.acquire(*args, **kwargs)

    def release(self):
        self.lock.release()

    def locked(self):
        return self.lock.locked()


def fixture_engine(api, pipeline=True):
    np = pytest.importorskip("numpy")
    engine = api.Engine(pipeline=pipeline)
    engine.ready = True
    engine.nodes = {"_root": {}}
    engine.snapshot = "fixture"
    engine.cards = {"urn:" + q: {"name": q, "description": q} for q in ("A", "B")}
    engine.urn_to_id = {"urn:" + q: q for q in ("A", "B")}
    engine.revisions = {"A": "rA", "B": "rB"}
    engine._lock = ObservedLock()
    expected = {"A": (127, 0), "B": (0, 127)}

    class Encoder:
        def __init__(self):
            self.b_encoded = threading.Event()
            self.fail = set()
            # Reused output buffer proves the request-local quantized vector owns its memory.
            self.buffer = np.empty((1, 2), dtype=np.float32)

        def _encode_uncached(self, texts, is_query):
            query = texts[0]
            if query in self.fail:
                raise ValueError("controlled_encoder_failure")
            self.buffer[:] = [[1., 0.]] if query == "A" else [[0., 1.]]
            if query == "B":
                self.b_encoded.set()
            return self.buffer

    class Router:
        def __init__(self):
            self.query_vec_of = {}
            self._current_qid = None
            self.cpu_a_entered = threading.Event()
            self.release_cpu_a = threading.Event()
            self.block_a = True
            self.fail_score = set()
            self.selections = []

        def active(self):
            return tuple(int(x) for x in self.query_vec_of["live"])

        def policy_filter(self, node, query):
            assert self.active() == expected[query]
            return list(engine.cards), {}

        def candidates(self, query, node):
            assert self.active() == expected[query]
            if query == "A" and self.block_a:
                self.cpu_a_entered.set()
                assert self.release_cpu_a.wait(4), "test did not release request A's CPU stage"
            assert self.active() == expected[query]
            return ["urn:" + query]

        def score(self, candidates, query, node):
            assert self.active() == expected[query]
            if query in self.fail_score:
                raise ValueError("controlled_router_failure")
            return [{"urn": candidates[0], "score": 1, "query": query}]

        def select(self, scored, k, admissible):
            query = scored[0]["query"]
            self.selections.append((query, self.active()))
            assert self.active() == expected[query]
            return scored

    engine.encoder = Encoder()
    engine.router = Router()
    engine.quantize = lambda values: np.clip(np.rint(values * 127), -127, 127).astype(np.int8)
    return engine


def request(engine, query, *, deadline=None):
    return engine.search({"query": query, "node": "_root", "profile": "hook", "deadline_ms": 5000},
                         time.monotonic() + 5 if deadline is None else deadline)


def background(engine, query, deadline=None):
    state = {}

    def work():
        try:
            state["result"] = request(engine, query, deadline=deadline)
        except Exception as exc:
            state["error"] = exc
        finally:
            state["done"].set()

    state["done"] = threading.Event()
    thread = threading.Thread(target=work, name="req-" + query, daemon=True)
    thread.start()
    return thread, state


def joined(thread, state):
    thread.join(3)
    assert not thread.is_alive(), "request thread failed to finish"
    return state


def test_pipeline_overlaps_b_encoder_with_a_cpu_and_preserves_each_vector(api):
    engine = fixture_engine(api, pipeline=True)
    a, a_state = background(engine, "A")
    b = None
    try:
        assert engine.router.cpu_a_entered.wait(2)
        a_bound = engine.router.query_vec_of["live"]
        b, b_state = background(engine, "B")
        assert engine.encoder.b_encoded.wait(2)
        # This event is after B's entire encoder helper and before acquiring the Router.
        assert engine._lock.b_attempted.wait(2)
        assert engine.router.query_vec_of["live"] is a_bound
        assert engine.router.active() == (127, 0)
        assert not a_state["done"].is_set()
        assert not b_state["done"].is_set()
    finally:
        engine.router.release_cpu_a.set()
        joined(a, a_state)
        if b is not None:
            joined(b, b_state)
    assert "error" not in a_state and "error" not in b_state
    assert engine.router.selections == [("A", (127, 0)), ("B", (0, 127))]
    assert engine.router.query_vec_of == {}
    assert engine._encode_count() == 2
    assert not engine._encoder_lock.locked() and not engine._lock.locked()


def test_reference_single_lock_prevents_b_encoding_while_a_cpu_is_active(api):
    engine = fixture_engine(api, pipeline=False)
    a, a_state = background(engine, "A")
    b = None
    try:
        assert engine.router.cpu_a_entered.wait(2)
        b, b_state = background(engine, "B")
        assert engine._lock.b_attempted.wait(2)
        # B reached the locked Router acquisition; A still owns it, so B cannot encode.
        assert not engine.encoder.b_encoded.is_set()
        assert engine.router.active() == (127, 0)
    finally:
        engine.router.release_cpu_a.set()
        joined(a, a_state)
        if b is not None:
            joined(b, b_state)
    assert "error" not in a_state and "error" not in b_state
    assert engine.encoder.b_encoded.is_set()
    assert engine.router.selections == [("A", (127, 0)), ("B", (0, 127))]


def test_encoder_queue_timeout_does_not_release_other_lock_or_clear_other_vector(api):
    engine = fixture_engine(api)
    sentinel = object()
    foreign = {"live": sentinel}
    engine.router.query_vec_of = foreign
    engine._encoder_lock.acquire()
    try:
        with pytest.raises(api.ApiError) as failed:
            request(engine, "B", deadline=time.monotonic())
        assert failed.value.status == 504
        assert engine._encoder_lock.locked()
        assert engine.router.query_vec_of is foreign
        assert engine.router.query_vec_of["live"] is sentinel
        assert not engine.encoder.b_encoded.is_set()
        assert engine._encode_count() == 0
    finally:
        engine._encoder_lock.release()
    engine.router.block_a = False
    assert request(engine, "B")["cards"][0]["skill_id"] == "B"


def test_router_queue_timeout_keeps_active_a_vector_and_releases_encoder(api):
    engine = fixture_engine(api)
    a, a_state = background(engine, "A")
    b = None
    try:
        assert engine.router.cpu_a_entered.wait(2)
        a_bound = engine.router.query_vec_of["live"]
        # Actual timed acquire on a lock held by A; no assertion depends on elapsed duration.
        b, b_state = background(engine, "B", deadline=time.monotonic() + .25)
        assert engine._lock.b_attempted.wait(2)
        assert b_state["done"].wait(2)
        assert isinstance(b_state.get("error"), api.ApiError)
        assert b_state["error"].status == 504
        assert engine.router.query_vec_of["live"] is a_bound
        assert engine.router.active() == (127, 0)
        assert engine._lock.locked()
        assert not engine._encoder_lock.locked()
    finally:
        engine.router.release_cpu_a.set()
        joined(a, a_state)
        if b is not None:
            joined(b, b_state)
    assert "error" not in a_state
    assert engine.router.selections == [("A", (127, 0))]
    assert request(engine, "B")["cards"][0]["skill_id"] == "B"


def test_encoder_exception_does_not_touch_a_router_state_and_allows_recovery(api):
    engine = fixture_engine(api)
    engine.encoder.fail.add("B")
    a, a_state = background(engine, "A")
    try:
        assert engine.router.cpu_a_entered.wait(2)
        a_bound = engine.router.query_vec_of["live"]
        with pytest.raises(ValueError, match="controlled_encoder_failure"):
            request(engine, "B")
        assert engine.router.query_vec_of["live"] is a_bound
        assert engine.router.active() == (127, 0)
        assert engine._lock.locked()
        assert not engine._encoder_lock.locked()
        assert engine._encode_count() == 1
    finally:
        engine.router.release_cpu_a.set()
        joined(a, a_state)
    assert "error" not in a_state
    engine.encoder.fail.clear()
    assert request(engine, "B")["cards"][0]["skill_id"] == "B"
    assert engine._encode_count() == 2


@pytest.mark.parametrize("pipeline", [False, True])
def test_router_exception_cleans_own_state_and_both_modes_recover(api, pipeline):
    engine = fixture_engine(api, pipeline=pipeline)
    engine.router.block_a = False
    engine.router.fail_score.add("B")
    with pytest.raises(ValueError, match="controlled_router_failure"):
        request(engine, "B")
    assert engine.router.query_vec_of == {}
    assert not engine._lock.locked()
    assert not engine._encoder_lock.locked()
    assert engine._encode_count() == 1
    assert request(engine, "A")["cards"][0]["skill_id"] == "A"
    assert engine._encode_count() == 2


@pytest.mark.parametrize("kwargs,code", [
    ({"native_dense_rank": True}, "native_dense_rank_requires_optimized"),
    ({"native_dense_rank": True, "optimized": True, "disable_model": True},
     "native_dense_rank_requires_hybrid"),
])
def test_native_flag_combinations_fail_before_model_load(api, kwargs, code):
    with pytest.raises(ValueError, match=code):
        api.Engine(**kwargs)


@pytest.mark.parametrize("milliseconds", [None, 0.1, 0.5, 10])
def test_gil_switch_interval_is_explicit_and_restored(api, milliseconds):
    previous = sys.getswitchinterval()
    try:
        # A non-default sentinel proves None preserves the caller's runtime setting.
        sys.setswitchinterval(.003)
        engine = api.Engine(gil_switch_ms=milliseconds)
        assert sys.getswitchinterval() == pytest.approx(.003)
        engine._configure_runtime()
        expected = .003 if milliseconds is None else milliseconds / 1000
        assert sys.getswitchinterval() == pytest.approx(expected, abs=1e-6)
        assert engine.gil_switch_ms_effective == pytest.approx(expected * 1000, abs=.001)
        assert engine.status()["gil_switch_ms_requested"] == milliseconds
    finally:
        sys.setswitchinterval(previous)


@pytest.mark.parametrize("milliseconds", [float("nan"), float("inf"), float("-inf"),
                                        0, -.5, .099, 10.001, True, False, "0.5"])
def test_gil_switch_invalid_values_do_not_modify_process_runtime(api, milliseconds):
    previous = sys.getswitchinterval()
    with pytest.raises(ValueError, match="invalid_gil_switch_ms"):
        api.Engine(gil_switch_ms=milliseconds)
    assert sys.getswitchinterval() == previous


def test_cli_rejects_nan_gil_interval_before_listening_or_model_load(tmp_path):
    import subprocess
    token = tmp_path / "fixture-token"
    token.write_text("fixture-token-for-early-validation")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/serve_spike/server.py"),
         "--token-file", str(token), "--gil-switch-ms", "nan"],
        capture_output=True, text=True, timeout=5, check=False)
    assert completed.returncode != 0
    assert "invalid_gil_switch_ms" in completed.stderr
    assert "listening" not in completed.stdout
    assert "Loading weights" not in completed.stderr
