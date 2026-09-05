"""Spawn-only CPU fake-worker tests for the isolated encoder transport.

The child never imports a model or touches CUDA. Blocking Events exercise RPC
ownership and watchdog cleanup; latency values are not performance assertions.
"""
import importlib
import importlib.util
import ctypes
import select
import signal
import multiprocessing
import os
from pathlib import Path
import struct
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


def fake_encoder_worker(connection, config):
    """Top-level spawn-picklable implementation of the documented wire protocol."""
    mode = config.get("mode", "echo")
    if mode == "startup_crash":
        os._exit(19)
    if mode == "startup_hang":
        config["release"].wait(10)
        return
    connection.send({"type": "ready", "metadata": {
        "dims": 2, "model_load_calls": 1, "device": "cpu-fixture", "dtype": "float32",
        "live_encode_calls": 0}})
    count = 0
    while True:
        try:
            message = connection.recv()
        except EOFError:
            return
        if message.get("type") == "stop":
            return
        assert message["type"] == "encode"
        request_id = message["request_id"]
        query = message["query"]
        if query == "expired":
            connection.send({"type": "expired", "request_id": request_id,
                             "live_encode_calls": count})
            continue
        if config.get("entered") is not None:
            config["entered"].set()
        if mode == "crash":
            os._exit(23)
        if mode == "watchdog" or (mode == "late_once" and count == 0):
            config["release"].wait(10)
        count += 1
        reply = {"type": "encoded",
                 "request_id": request_id + 1 if mode == "wrong_id" else request_id,
                 "vector_bytes": struct.pack("<ff", *config["vectors"][query]) if query in config.get("vectors", {}) else struct.pack("<ff", float(request_id), float(query)),
                 "dims": 2, "live_encode_calls": count}
        if mode == "bad_vector":
            reply["vector_bytes"] = b"bad"
        connection.send(reply)


@pytest.fixture(scope="module")
def worker_api():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return importlib.import_module("tools.serve_spike.encoder_worker")


def proxy(worker_api, **config):
    return worker_api.EncoderProcessProxy(
        {"worker_timeout_s": 1, **config}, worker_target=fake_encoder_worker)


def active_pids():
    return {child.pid for child in multiprocessing.active_children()}


def assert_closed_without_new_children(client, previous):
    client.close()
    client.close()  # Cleanup remains safe after error cleanup or an earlier close.
    assert not client.health()["alive"]
    assert active_pids() <= previous


def test_spawn_echo_correlates_each_response_and_explicit_cleanup_has_no_orphans(worker_api):
    previous = active_pids()
    client = proxy(worker_api)
    try:
        metadata = client.start(timeout=5)
        assert metadata["dims"] == 2
        assert metadata["model_load_calls"] == 1
        assert client.health()["alive"]
        assert client.health()["pid"] != os.getpid()
        first = client.encode("11", time.monotonic() + 2)
        second = client.encode("22", time.monotonic() + 2)
        assert first.shape == second.shape == (1, 2)
        assert second[0, 0] == first[0, 0] + 1
        assert first[0, 1] == 11 and second[0, 1] == 22
        assert client.health()["live_encode_calls"] == 2
    finally:
        assert_closed_without_new_children(client, previous)


def test_expired_before_send_keeps_healthy_worker_and_next_result_is_fresh(worker_api):
    previous = active_pids()
    client = proxy(worker_api)
    try:
        client.start(timeout=5)
        with pytest.raises(worker_api.EncoderDeadlineExceeded):
            client.encode("11", time.monotonic() - 1)
        assert client.health()["alive"]
        assert client.health()["live_encode_calls"] == 0
        result = client.encode("22", time.monotonic() + 2)
        assert result[0, 1] == 22
        assert client.health()["live_encode_calls"] == 1
    finally:
        assert_closed_without_new_children(client, previous)


def test_worker_expired_reply_is_nonfatal_and_cannot_be_consumed_as_next_vector(worker_api):
    previous = active_pids()
    client = proxy(worker_api)
    try:
        client.start(timeout=5)
        with pytest.raises(worker_api.EncoderDeadlineExceeded):
            client.encode("expired", time.monotonic() + 2)
        assert client.health()["alive"]
        assert not client.health()["failed"]
        result = client.encode("33", time.monotonic() + 2)
        assert result[0, 1] == 33
        assert client.health()["live_encode_calls"] == 1
    finally:
        assert_closed_without_new_children(client, previous)


def test_healthy_forward_may_finish_after_deadline_then_next_request_recovers(worker_api):
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    previous = active_pids()
    client = proxy(worker_api, mode="late_once", entered=entered, release=release, worker_timeout_s=2)
    timer = None
    try:
        client.start(timeout=5)
        deadline = time.monotonic() + .10
        # Hold the fake forward past its request deadline, within the separate worker watchdog.
        timer = threading.Timer(.25, release.set)
        timer.start()
        result = client.encode("41", deadline)
        assert entered.is_set()
        assert time.monotonic() >= deadline
        assert result[0, 1] == 41
        assert client.health()["alive"]
        assert not client.health()["failed"]
        # Engine checks the original deadline after this non-preemptible stage.
        spec = importlib.util.spec_from_file_location("worker_deadline_service", ROOT / "tools/serve_spike/server.py")
        service = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = service
        spec.loader.exec_module(service)
        with pytest.raises(service.ApiError) as failed:
            service.check_deadline(deadline)
        assert failed.value.status == 504
        recovered = client.encode("42", time.monotonic() + 2)
        assert recovered[0, 0] == result[0, 0] + 1
        assert recovered[0, 1] == 42
        assert client.health()["live_encode_calls"] == 2
    finally:
        release.set()
        if timer is not None:
            timer.cancel()
            timer.join(1)
        assert_closed_without_new_children(client, previous)


@pytest.mark.parametrize("mode", ["crash", "wrong_id", "bad_vector"])
def test_crash_or_protocol_error_fails_closed_and_never_reuses_a_stale_vector(worker_api, mode):
    previous = active_pids()
    client = proxy(worker_api, mode=mode)
    try:
        client.start(timeout=5)
        with pytest.raises(worker_api.EncoderWorkerError):
            client.encode("51", time.monotonic() + 2)
        assert client.health()["failed"]
        assert not client.health()["alive"]
        with pytest.raises(worker_api.EncoderWorkerError):
            client.encode("52", time.monotonic() + 2)
    finally:
        assert_closed_without_new_children(client, previous)


def test_hard_worker_watchdog_terminates_owned_stuck_child(worker_api):
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    previous = active_pids()
    client = proxy(worker_api, mode="watchdog", entered=entered, release=release, worker_timeout_s=.2)
    try:
        client.start(timeout=5)
        with pytest.raises(worker_api.EncoderWorkerError):
            client.encode("61", time.monotonic() + 2)
        assert entered.is_set()
        assert client.health()["failed"]
        assert not client.health()["alive"]
        with pytest.raises(worker_api.EncoderWorkerError):
            client.encode("62", time.monotonic() + 2)
    finally:
        # A child terminated inside Event.wait can leave its condition locked.
        # Do not reuse that synchronization fixture after fatal process cleanup.
        assert_closed_without_new_children(client, previous)


@pytest.mark.parametrize("mode", ["startup_crash", "startup_hang"])
def test_startup_failure_cleans_up_owned_child(worker_api, mode):
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    previous = active_pids()
    client = proxy(worker_api, mode=mode, release=release)
    try:
        with pytest.raises(worker_api.EncoderWorkerError):
            client.start(timeout=.5)
        assert client.health()["failed"]
        assert not client.health()["alive"]
    finally:
        # A child terminated inside Event.wait can leave its condition locked.
        # Do not reuse that synchronization fixture after fatal process cleanup.
        assert_closed_without_new_children(client, previous)


def test_worker_started_in_initialization_thread_survives_creator_thread_exit(worker_api):
    previous = active_pids()
    client = proxy(worker_api)
    results, failures = [], []

    def initialize():
        try:
            results.append(client.start(timeout=5))
        except BaseException as exc:
            failures.append(exc)

    initializer = threading.Thread(target=initialize)
    try:
        initializer.start()
        initializer.join(6)
        assert not initializer.is_alive()
        assert not failures
        assert results[0]["dims"] == 2
        result = client.encode("71", time.monotonic() + 2)
        assert result[0, 1] == 71
        assert client.health()["alive"]
    finally:
        assert_closed_without_new_children(client, previous)


def parent_process_with_blocked_worker(connection, config):
    """Independent API-parent fixture; killed abruptly, so it cannot call close."""
    api = importlib.import_module("tools.serve_spike.encoder_worker")
    client = api.EncoderProcessProxy(config, worker_target=fake_encoder_worker)
    client.start(timeout=5)
    connection.send(client.health()["pid"])
    client.encode("81", time.monotonic() + 20)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux process parent guard")
@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGKILL])
def test_actual_parent_death_stops_blocked_worker_without_orphan(worker_api, stop_signal):
    # Adopt and reap this test's orphan so the fixture itself leaves no zombie.
    # The setting is restored even when an assertion fails.
    libc = ctypes.CDLL(None, use_errno=True)
    old_subreaper = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(old_subreaper), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    receiver, sender = context.Pipe(duplex=False)
    parent = context.Process(target=parent_process_with_blocked_worker, args=(sender, {
        "mode": "watchdog", "entered": entered, "release": release,
        "worker_timeout_s": 20}))
    worker_pid, pidfd, reaped = None, None, False
    try:
        parent.start()
        sender.close()
        assert receiver.poll(7), "parent did not start its worker"
        worker_pid = receiver.recv()
        pidfd = os.pidfd_open(worker_pid)
        assert entered.wait(5), "worker did not enter blocked forward"
        os.kill(parent.pid, stop_signal)
        parent.join(3)
        assert not parent.is_alive()
        exits = select.poll()
        exits.register(pidfd, select.POLLIN)
        assert exits.poll(5000), "worker survived actual parent process death"
        waited, _ = os.waitpid(worker_pid, 0)
        reaped = waited == worker_pid
        assert reaped
    finally:
        if parent.pid is not None and parent.is_alive():
            parent.kill()
            parent.join(3)
        if worker_pid is not None and not reaped:
            try:
                os.kill(worker_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(worker_pid, 0)
            except ChildProcessError:
                pass
        if pidfd is not None:
            os.close(pidfd)
        receiver.close()
        sender.close()
        assert libc.prctl(36, old_subreaper.value, 0, 0, 0) == 0


def test_rpc_queue_deadline_cannot_steal_inflight_reply(worker_api):
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    previous = active_pids()
    client = proxy(worker_api, mode="late_once", entered=entered, release=release, worker_timeout_s=3)
    first = {}
    thread = None

    def encode_first():
        try:
            first["result"] = client.encode("91", time.monotonic() + 2)
        except BaseException as exc:
            first["error"] = exc

    try:
        client.start(timeout=5)
        thread = threading.Thread(target=encode_first)
        thread.start()
        assert entered.wait(2)
        with pytest.raises(worker_api.EncoderDeadlineExceeded):
            client.encode("92", time.monotonic() + .05)
        release.set()
        thread.join(3)
        assert not thread.is_alive()
        assert "error" not in first
        assert first["result"][0, 1] == 91
        third = client.encode("93", time.monotonic() + 2)
        assert third[0, 1] == 93
        assert third[0, 0] == first["result"][0, 0] + 1
        assert client.health()["live_encode_calls"] == 2
    finally:
        if thread is not None and thread.is_alive() and client.health()["alive"]:
            release.set()
            thread.join(3)
        assert_closed_without_new_children(client, previous)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -.1, .049, 30.1, True, "5"])
def test_worker_watchdog_rejects_invalid_values_before_start(worker_api, value):
    previous = active_pids()
    with pytest.raises(ValueError, match="invalid_encoder_worker_timeout"):
        proxy(worker_api, worker_timeout_s=value)
    assert active_pids() == previous


@pytest.fixture(scope="module")
def service_api():
    return importlib.import_module("tools.serve_spike.server")


def test_encoder_process_requires_pipeline_and_hybrid(service_api):
    with pytest.raises(ValueError, match="encoder_process_requires_pipeline"):
        service_api.Engine(encoder_process=True)
    with pytest.raises(ValueError, match="encoder_process_requires_hybrid"):
        service_api.Engine(encoder_process=True, pipeline=True, disable_model=True)
    engine = service_api.Engine(encoder_process=True, pipeline=True)
    assert engine.encoder_worker_timeout == 5
    assert engine._worker_proxy is None


def test_engine_worker_late_deadline_recovers_and_counts_forward(worker_api, service_api):
    from test_service_pipeline import fixture_engine, request
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    previous = active_pids()
    client = proxy(worker_api, mode="late_once", entered=entered, release=release,
                   vectors={"A": [1, 0], "B": [0, 1]}, worker_timeout_s=2)
    engine = fixture_engine(service_api)
    engine.encoder_process = True
    engine._worker_proxy = client
    engine.router.block_a = False
    timer = None
    try:
        client.start(timeout=5)
        timer = threading.Timer(.25, release.set)
        timer.start()
        with pytest.raises(service_api.ApiError) as expired:
            request(engine, "A", deadline=time.monotonic() + .10)
        assert expired.value.status == 504
        assert entered.is_set()
        assert engine.status()["ready"]
        assert engine._encode_count() == 1
        assert engine.router.query_vec_of == {}
        assert not engine._encoder_lock.locked()
        result = request(engine, "B")
        assert result["cards"][0]["skill_id"] == "B"
        assert engine.router.selections == [("B", (0, 127))]
        assert engine._encode_count() == 2
    finally:
        if timer is not None:
            timer.cancel()
            timer.join(1)
        engine.close()
        assert_closed_without_new_children(client, previous)


def test_engine_worker_crash_ejects_readiness_and_releases_query_state(worker_api, service_api):
    from test_service_pipeline import fixture_engine, request
    previous = active_pids()
    client = proxy(worker_api, mode="crash")
    engine = fixture_engine(service_api)
    engine.encoder_process = True
    engine._worker_proxy = client
    try:
        client.start(timeout=5)
        with pytest.raises(service_api.ApiError) as failed:
            request(engine, "A")
        assert failed.value.status == 503
        assert not engine.status()["ready"]
        assert engine.error == "encoder_worker_unavailable"
        assert engine.router.query_vec_of == {}
        assert not engine._encoder_lock.locked()
        with pytest.raises(service_api.ApiError) as again:
            request(engine, "B")
        assert again.value.status == 503
        assert engine.router.selections == []
    finally:
        engine.close()
        assert_closed_without_new_children(client, previous)
