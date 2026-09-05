"""E1.1b HTTP contract tests with a deterministic engine and controlled transport.

These tests do not measure model quality or production latency. The real GPU and
revision hydration paths are measured by tools/serve_spike/probe.py separately.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = load_module("guidefold_service_probe", "tools/serve_spike/probe.py")


@pytest.fixture(scope="module")
def service():
    return load_module("guidefold_service_spike", "tools/serve_spike/server.py")


class FakeEngine:
    """Only routing/hydration internals are fake; requests use real TCP and JSON."""
    ready = True

    def __init__(self):
        self.calls = []
        self.live_encode_calls = 0
        self.body = "# Fixture skill\nRead the contract; do not run any command.\n"
        self.revision = hashlib.sha256(self.body.encode()).hexdigest()
        self.release = None
        self.entered = threading.Event()

    def status(self):
        return {"ready": self.ready, "backend": "hybrid_full",
                "live_encode_calls": self.live_encode_calls, "snapshot": "fixture-only"}

    def search(self, payload, deadline):
        self.calls.append(("search", payload))
        self.entered.set()
        if self.release:
            self.release.wait(3)
        self.live_encode_calls += 1
        return {
            "search_id": "fixture-search-" + str(self.live_encode_calls),
            "backend": "hybrid_full", "snapshot": "fixture-only",
            "live_encode_calls": self.live_encode_calls,
            "cards": [{"skill_id": "fixture-skill", "revision": self.revision}],
            "ranked": [{"skill_id": "fixture-skill", "revision": self.revision}],
            "stages_ms": {}, "composition": {"status": "not_evaluated", "incomplete": None},
        }

    def use(self, payload, deadline):
        self.calls.append(("use", payload))
        return {"status": "hydrated", "skill_id": payload["skill_id"],
                "revision": payload["revision"], "body": self.body,
                "checksum": hashlib.sha256(self.body.encode()).hexdigest(),
                "execution_observed": False, "search_id": payload.get("search_id")}


@contextmanager
def running_server(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.fixture
def live_service(service, tmp_path):
    engine = FakeEngine()
    log_path = tmp_path / "events.jsonl"
    server = service.make_server(engine, token="fixture-token-123456789", port=0, log_file=log_path)
    with running_server(server) as url:
        yield engine, url, log_path


def search_payload():
    return {"query": "How do I check this contract?", "profile": "hook",
            "node": "_root", "deadline_ms": 1000}


def test_readiness_reflects_engine_state(live_service):
    engine, url, _ = live_service
    result = probe.request_json(url, "", "/health/ready")
    assert result["http_status"] == 200
    assert result["response"]["ready"] is True
    engine.ready = False
    result = probe.request_json(url, "", "/health/ready")
    assert result["http_status"] == 503
    assert result["response"]["ready"] is False


def test_unauthorized_search_never_reaches_engine(live_service):
    engine, url, _ = live_service
    for token in ("", "wrong"):
        result = probe.request_json(url, token, "/v1/search", search_payload())
        assert result["http_status"] == 401
    assert engine.calls == []


def test_live_query_crosses_http_and_repeat_is_not_client_cached(live_service):
    engine, url, _ = live_service
    first = probe.request_json(url, "fixture-token-123456789", "/v1/search", search_payload())
    second = probe.request_json(url, "fixture-token-123456789", "/v1/search", search_payload())
    assert first["http_status"] == second["http_status"] == 200
    assert [call[1]["query"] for call in engine.calls] == [search_payload()["query"]] * 2
    assert second["response"]["live_encode_calls"] == 2
    assert first["response"]["search_id"] != second["response"]["search_id"]


def test_malformed_json_is_rejected_before_engine(live_service):
    import urllib.error
    import urllib.request

    engine, url, _ = live_service
    request = urllib.request.Request(url + "/v1/search", data=b"{broken",
        headers={"Authorization": "Bearer fixture-token-123456789", "Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=2)
    assert error.value.code == 400
    assert engine.calls == []


def test_oversized_body_is_rejected_before_engine(live_service):
    import http.client
    import urllib.parse

    engine, url, _ = live_service
    parsed = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
    # Advertise an oversized body without transmitting it: rejection must precede reading it.
    connection.putrequest("POST", "/v1/search")
    connection.putheader("Authorization", "Bearer fixture-token-123456789")
    connection.putheader("Content-Length", "1000000")
    connection.endheaders()
    assert connection.getresponse().status == 413
    connection.close()
    assert engine.calls == []


@pytest.mark.parametrize("payload", [
    [], {"query": ""}, {"query": 123}, {**search_payload(), "profile": "unknown"},
    {**search_payload(), "deadline_ms": -1},
])
def test_invalid_search_schema_never_reaches_engine(live_service, payload):
    engine, url, _ = live_service
    result = probe.request_json(url, "fixture-token-123456789", "/v1/search", payload)
    assert result["http_status"] == 400
    assert engine.calls == []


def test_use_requires_explicit_revision(live_service):
    engine, url, _ = live_service
    result = probe.request_json(url, "fixture-token-123456789", "/v1/use",
                               {"skill_id": "fixture-skill", "deadline_ms": 1000})
    assert result["http_status"] == 400
    assert engine.calls == []


def test_hydration_preserves_revision_and_is_not_execution(live_service):
    engine, url, _ = live_service
    payload = {"skill_id": "fixture-skill", "revision": engine.revision,
               "search_id": "fixture-search", "deadline_ms": 1000}
    responses = [probe.request_json(url, "fixture-token-123456789", "/v1/use", payload) for _ in range(2)]
    for result in responses:
        assert result["http_status"] == 200
        body = result["response"]
        assert body["revision"] == engine.revision
        assert body["checksum"] == hashlib.sha256(body["body"].encode()).hexdigest()
        assert body["search_id"] == "fixture-search"
        assert body["status"] == "hydrated"
        assert body["execution_observed"] is False


def test_overload_rejection_is_counted_separately(service):
    engine = FakeEngine()
    engine.release = threading.Event()
    server = service.make_server(engine, token="fixture-token-123456789", port=0, max_inflight=1)
    with running_server(server) as url:
        first = {}
        thread = threading.Thread(target=lambda: first.update(
            probe.request_json(url, "fixture-token-123456789", "/v1/search", search_payload(), timeout=4)))
        thread.start()
        assert engine.entered.wait(2)
        try:
            rejected = probe.request_json(url, "fixture-token-123456789", "/v1/search", search_payload())
            assert rejected["http_status"] in {429, 503}
        finally:
            engine.release.set()
            thread.join(4)
        assert first["http_status"] == 200
        summary = probe.summarize([probe.compact_result(first), probe.compact_result(rejected)], 300)
        assert summary["attempted"] == 2
        assert summary["succeeded"] == 1
        assert summary["failed"] == 1


def test_fresh_client_process_can_search_without_model_imports(live_service, tmp_path):
    engine, url, _ = live_service
    token_file = tmp_path / "token"
    token_file.write_text("fixture-token-123456789")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/serve_spike/probe.py"), "--one-shot",
         "--url", url, "--token-file", str(token_file)],
        input=json.dumps({"path": "/v1/search", "payload": search_payload()}),
        capture_output=True, text=True, timeout=10, check=True)
    assert json.loads(completed.stdout)["http_status"] == 200
    assert len(engine.calls) == 1


def test_controlled_transport_timeout_returns_only_available_snapshot():
    class DelayHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            time.sleep(.15)
            encoded = b'{"cards": []}'
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), DelayHandler)
    server.daemon_threads = True
    cards = [{"skill_id": "local", "revision": "immutable-fixture"}]
    with running_server(server) as url:
        result = probe.search_with_fallback(url, "fixture-token-123456789", search_payload(),
                                            timeout=.01, cached_cards=cards, lease_expires_unix=time.time() + 60,
                                            allowed_revisions={"local": "immutable-fixture"},
                                            snapshot_id="fixture-snapshot")
    assert result["mode"] == "local_snapshot_fallback"
    assert result["reason"] == "client_timeout"
    assert result["cards"] == cards
    assert result["execution_observed"] is False


def test_failure_denominators_do_not_disappear_from_percentiles():
    rows = [{"http_status": 200, "client_ms": 100, "error": None},
            {"http_status": 503, "client_ms": 5, "error": None},
            {"http_status": None, "client_ms": 500, "error": "client_timeout"}]
    summary = probe.summarize(rows, 300)
    assert summary["success_latency_ms"]["p95"] == 100
    assert summary["succeeded"] == 1
    assert summary["attempted"] == 3
    assert summary["successful_within_budget"] == 1
    assert summary["within_budget_fraction_of_all_attempts"] == 1 / 3
    assert summary["budget_failures_including_rejections"] == 2


def test_probe_rejects_external_destinations():
    for url in ("https://example.com", "http://example.com", "http://user:secret@localhost"):
        with pytest.raises(ValueError):
            probe.validate_url(url)


def test_explicit_deny_never_falls_back_and_requires_cache_invalidation(live_service):
    _, url, _ = live_service
    result = probe.search_with_fallback(
        url, "wrong", search_payload(), timeout=2,
        cached_cards=[{"skill_id": "cached", "revision": "r1"}],
        lease_expires_unix=time.time() + 60, allowed_revisions={"cached": "r1"},
        snapshot_id="fixture-snapshot")
    assert result["mode"] == "abstain"
    assert result["cards"] == []
    assert result["invalidate_cache"] is True


@pytest.mark.parametrize("lease,allowed,snapshot,reason", [
    (None, {"cached": "r1"}, "s1", "missing_or_expired_cache_lease"),
    (0, {"cached": "r1"}, "s1", "missing_or_expired_cache_lease"),
    (float("inf"), {"cached": "r1"}, None, "missing_or_expired_cache_lease"),
    (float("inf"), {}, "s1", "cache_revision_not_authorized"),
    (float("inf"), {"cached": "r2"}, "s1", "cache_revision_not_authorized"),
])
def test_transport_failure_requires_valid_lease_and_revision(monkeypatch, lease, allowed, snapshot, reason):
    monkeypatch.setattr(probe, "request_json", lambda *a, **kw:
                        {"http_status": None, "error": "client_timeout", "client_ms": 10})
    result = probe.search_with_fallback(
        "http://127.0.0.1:1", "fixture-token-123456789", search_payload(),
        timeout=.01, cached_cards=[{"skill_id": "cached", "revision": "r1"}],
        lease_expires_unix=lease, allowed_revisions=allowed, snapshot_id=snapshot)
    assert result["mode"] == "abstain"
    assert result["cards"] == []
    assert result["reason"] == reason


def test_real_engine_hydration_pins_revision_and_current_state(service):
    engine = service.Engine(disable_model=True)
    engine.ready = True
    engine.snapshot = "fixture-snapshot"
    engine.id_to_urn = {"skill-1": "urn:fixture"}
    engine.revisions = {"skill-1": "card-revision-1"}
    engine.cards = {"urn:fixture": {"status": "active", "_body": "# Skill\nRead-only instructions.\n"}}
    payload = {"skill_id": "skill-1", "revision": "card-revision-1",
               "search_id": "correlation-only", "deadline_ms": 1000}
    result = engine.use(payload, time.monotonic() + 1)
    assert result["body"] == engine.cards["urn:fixture"]["_body"]
    assert result["checksum"] == hashlib.sha256(result["body"].encode()).hexdigest()
    assert result["execution_observed"] is False
    assert result["search_id_verified"] is False
    with pytest.raises(service.ApiError) as stale:
        engine.use({**payload, "revision": "old"}, time.monotonic() + 1)
    assert stale.value.status == 409
    engine.cards["urn:fixture"]["status"] = "deprecated"
    with pytest.raises(service.ApiError) as inactive:
        engine.use(payload, time.monotonic() + 1)
    assert inactive.value.status == 409


def test_telemetry_excludes_raw_prompt_token_and_skill_body(live_service):
    engine, url, log_path = live_service
    prompt = "private prompt text must not enter event file"
    result = probe.request_json(url, "fixture-token-123456789", "/v1/search",
                                {**search_payload(), "query": prompt})
    assert result["http_status"] == 200
    hydrated = probe.request_json(
        url, "fixture-token-123456789", "/v1/use",
        {"skill_id": "fixture-skill", "revision": engine.revision,
         "search_id": result["response"]["search_id"], "deadline_ms": 1000})
    assert hydrated["http_status"] == 200
    log = log_path.read_text()
    assert prompt not in log
    assert "fixture-token-123456789" not in log
    assert engine.body not in log
    events = [json.loads(line) for line in log.splitlines()]
    assert len(events) == 2
    assert events[1]["event"] == "use_hydrated"
    assert events[1]["execution_observed"] is False


def test_real_engine_does_not_expose_policy_dropped_ranked_cards(service):
    class Router:
        def policy_filter(self, node, query):
            return ["urn:allowed"], {"urn:denied": "policy_drop"}

        def candidates(self, query, node):
            return ["urn:denied", "urn:allowed"]

        def score(self, candidates, query, node):
            return [{"urn": "urn:denied", "score": 10}, {"urn": "urn:allowed", "score": 1}]

        def select(self, scored, k, admissible):
            return [row for row in scored if row["urn"] in admissible]

    engine = service.Engine(disable_model=True)
    engine.ready = True
    engine.snapshot = "fixture-snapshot"
    engine.nodes = {"_root": {}}
    engine.router = Router()
    engine.cards = {urn: {"name": urn, "description": urn} for urn in ("urn:allowed", "urn:denied")}
    engine.urn_to_id = {"urn:allowed": "allowed", "urn:denied": "denied"}
    engine.revisions = {"allowed": "r1", "denied": "r1"}
    result = engine.search(search_payload(), time.monotonic() + 1)
    assert [row["skill_id"] for row in result["ranked"]] == ["allowed"]
    assert [row["skill_id"] for row in result["cards"]] == ["allowed"]


def test_document_cache_must_match_text_and_quantized_rows(service, tmp_path):
    from types import SimpleNamespace
    np = pytest.importorskip("numpy")
    engine = service.Engine()
    vector = np.array([.15, .55, .75], dtype=np.float32)
    engine.quantize = lambda array: np.clip(np.rint(array * 127), -127, 127).astype(np.int8)
    normalized = vector[None, :] / np.linalg.norm(vector[None, :], axis=1, keepdims=True)
    engine.router = SimpleNamespace(row_of={"urn:one": 0}, skill_mat=engine.quantize(normalized))
    engine.urn_to_id = {"urn:one": "one"}
    engine.skills = {"one": {"description": "description", "body": "body"}}
    engine.cache_evidence = {}
    encode = SimpleNamespace(
        _cache_dir=lambda *_: tmp_path,
        _cache_key=lambda text, is_query: hashlib.sha256((str(is_query) + text).encode()).hexdigest())
    corpus = SimpleNamespace(MODEL_HF_ID="fixture-model", MODEL_REV="fixed-revision")
    text = "description\n\nbody"
    path = tmp_path / (encode._cache_key(text, False) + ".npy")
    np.save(path, vector)
    engine._verify_text_cache(encode, corpus, np)
    assert engine.cache_evidence["text_binding"] == "all_rows_verified_against_content_addressed_float_cache"
    engine.router.skill_mat[0, 0] += 1
    with pytest.raises(ValueError, match="document_cache_text_mismatch"):
        engine._verify_text_cache(encode, corpus, np)
    engine.router.skill_mat = engine.quantize(normalized)
    engine.skills["one"]["body"] = "changed body"
    with pytest.raises(FileNotFoundError):
        engine._verify_text_cache(encode, corpus, np)


def test_cli_snapshot_hashes_exact_bytes_and_survives_source_edit(service, tmp_path):
    source = tmp_path / "frozen_cli.py"
    initial = b"VALUE = 1\n"
    source.write_bytes(initial)
    module, revision = service.load_cli_snapshot(source)
    assert revision == hashlib.sha256(initial).hexdigest()
    assert module.VALUE == 1
    source.write_bytes(b"VALUE = 2\n")  # Same size, no timestamp sleep: stale-pyc regression.
    updated, updated_revision = service.load_cli_snapshot(source)
    assert updated_revision != revision
    assert updated.VALUE == 2
    assert module.VALUE == 1
    assert module.__file__ == str(source.resolve())


def test_resident_dense_preserves_integer_scores_visibility_and_live_queries(service):
    from types import SimpleNamespace
    np = pytest.importorskip("numpy")
    dense = load_module("e11b_dense_reference", "tools/eval/dense_ref.py")
    rng = np.random.default_rng(20260905)
    matrix = rng.integers(-128, 128, size=(11, 1024), dtype=np.int8)
    matrix[0] = 127
    matrix[1] = -128
    matrix[2] = 0
    rows = {"urn:" + str(i): i for i in range(len(matrix))}
    norms = {urn: int((matrix[row].astype(np.int64) ** 2).sum()) for urn, row in rows.items()}
    router = SimpleNamespace(skill_mat=matrix, row_of=rows,
                             query_vec_of={}, _current_qid="live",
                             index=SimpleNamespace(skill_normsq=norms))
    metadata = service.install_resident_dense(router)
    resident = router.resident_dense_i64
    assert resident.dtype == np.int64
    assert resident.flags.writeable is False
    assert metadata["per_query_document_matrix_copy"] is False
    for vector in (np.full(1024, 127, dtype=np.int64),
                   np.full(1024, -128, dtype=np.int64),
                   rng.integers(-128, 128, size=1024, dtype=np.int64)):
        # Reuse the same query ID with new contents; no query result may be reused.
        router.query_vec_of["live"] = vector
        for visible in (list(rows), ["urn:5", "missing", "urn:0", "urn:2"], [], ["missing"]):
            expected = dense.DenseCandidateRouter._dense_scores(router, "query", visible)
            actual = router._dense_scores("query", visible)
            assert list(actual) == list(expected)
            assert actual == expected
            assert all(type(dot) is int and type(norm) is int for dot, norm in actual.values())
            assert router.resident_dense_i64 is resident
    router.query_vec_of.clear()
    assert router._dense_scores("query", list(rows)) == {}


@pytest.mark.parametrize("threads", [0, -1, 257, True, 1.5])
def test_engine_rejects_invalid_torch_thread_configuration(service, threads):
    with pytest.raises(ValueError, match="invalid_torch_threads"):
        service.Engine(torch_threads=threads)


def test_parity_digests_detect_order_scores_and_revisions():
    response = {
        "ranked": [{"skill_id": "one", "score": 2}, {"skill_id": "two", "score": 1}],
        "cards": [{"skill_id": "one", "revision": "r1"}, {"skill_id": "two", "revision": "r2"}],
    }
    base = probe.compact_result({"response": response})
    repeated = probe.compact_result({"response": json.loads(json.dumps(response))})
    assert base["ranked_sha256"] == repeated["ranked_sha256"]
    assert base["selected_sha256"] == repeated["selected_sha256"]
    reordered = probe.compact_result({"response": {
        "ranked": list(reversed(response["ranked"])), "cards": list(reversed(response["cards"]))}})
    assert reordered["ranked_sha256"] != base["ranked_sha256"]
    assert reordered["selected_sha256"] != base["selected_sha256"]
    changed = probe.compact_result({"response": {
        "ranked": [{"skill_id": "one", "score": 3}, response["ranked"][1]],
        "cards": [{"skill_id": "one", "revision": "r3"}, response["cards"][1]]}})
    assert changed["ranked_sha256"] != base["ranked_sha256"]
    assert changed["selected_sha256"] != base["selected_sha256"]


def test_fresh_client_burst_starts_four_workers_without_timing_assertions(monkeypatch, tmp_path):
    from types import SimpleNamespace
    barrier = threading.Barrier(4)
    worker_ids = set()
    lock = threading.Lock()

    def fake_run(command, **kwargs):
        with lock:
            worker_ids.add(threading.get_ident())
        barrier.wait(timeout=3)
        result = {"http_status": 200, "client_ms": 10, "error": None,
                  "response": {"ranked": [], "cards": [], "stages_ms": {}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(result))

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    args = SimpleNamespace(fresh_count=4, fresh_concurrency=4, deadline_ms=1000,
                           url="http://127.0.0.1:1", token_file=tmp_path / "unused",
                           timeout=5, budget_ms=400)
    queries = [{"id": str(i), "query": "fixture " + str(i)} for i in range(4)]
    result = probe.benchmark_fresh(args, queries)
    assert len(worker_ids) == 4
    assert result["concurrency"] == 4
    assert result["parent_queue_included_in_per_request_ms"] is False
    assert result["summary"]["attempted"] == result["summary"]["succeeded"] == 4
    assert [row["query_id"] for row in result["rows"]] == ["0", "1", "2", "3"]
    assert all(row["http_roundtrip_ms"] == 10 for row in result["rows"])
