"""E2.6/E2.9: `search.backend: service` -- the client talks to the SEARCH/USE service with one
monotonic deadline and a concurrent local fallback (ADR-0023 Sec3), plus the runtime parity
counter (E2.9) that compares the selected-set hash when both sides finish in time.

Everything here is exercised in-process against the actual CLI module (the `gf` fixture from
conftest.py) with a real stdlib `http.server.ThreadingHTTPServer` standing in for the Go/ParadeDB
service -- no vendored HTTP client, no mocked `http.client` internals. Most tests monkeypatch
`gf._local_selected` to a fixed, controlled answer instead of depending on real Router/ranking
output: this file's job is the transport/deadline/fallback/parity layer (E2.6/E2.9), not ranking
quality, and Router.select() is being changed concurrently by another agent in the same file --
depending on its real output here would make these tests fragile to unrelated changes.
"""
import hashlib
import http.server
import json
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest


# --------------------------------------------------------------------- mock contract-1.1 service

class _Handler(http.server.BaseHTTPRequestHandler):
    def _dispatch(self, method):
        ctrl = self.server.ctrl
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = None
        ctrl.requests.append({"method": method, "path": self.path,
                               "headers": dict(self.headers), "payload": payload})
        if ctrl.delay_s:
            time.sleep(ctrl.delay_s)
        status, body = ctrl.responder(self.path, payload, dict(self.headers))
        data = b"" if body is None else json.dumps(body).encode("utf-8")
        try:
            self.send_response(status)
            if data:
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # the client already abandoned the socket (deadline hit) -- expected, not a bug

    def do_POST(self):
        self._dispatch("POST")

    def do_GET(self):
        self._dispatch("GET")

    def log_message(self, *a):
        pass


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True  # never blocks process/test exit even if a handler is mid-sleep


class _Controller:
    def __init__(self, responder, delay_s=0.0):
        self.responder = responder
        self.delay_s = delay_s
        self.requests = []


def _find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@contextmanager
def running_service(responder, delay_s=0.0):
    """Starts a real HTTP server on 127.0.0.1 implementing whatever `responder(path, payload,
    headers) -> (status, body_dict_or_None)` says. Yields (base_url, controller) -- controller
    accumulates every request received (`.requests`), for asserting on headers/payloads sent."""
    port = _find_free_port()
    server = _Server(("127.0.0.1", port), _Handler)
    server.ctrl = _Controller(responder, delay_s=delay_s)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", server.ctrl
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def _card(urn, revision="rev-1", description="a card"):
    return {"urn": urn, "revision": revision, "description": description}


def _search_ok(cards, search_id="srv-search-1", request_id="req-1"):
    def responder(path, payload, headers):
        if path == "/v1/search":
            return 200, {"schema_version": "1.1", "request_id": request_id, "search_id": search_id,
                          "cards": cards, "ranked": [], "context": {}, "card_context": {},
                          "composition": {}}
        return 404, {"error": "not_found"}
    return responder


def _spool_events(root):
    out = []
    spool = Path(root) / ".guidefold" / "telemetry" / "spool"
    if not spool.is_dir():
        return out
    for f in spool.rglob("events-*.jsonl"):
        out += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return out


# ------------------------------------------------------------------------------- resolve_search_config

def test_default_backend_is_local_with_no_config_error(gf):
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg == {"backend": "local", "url": None,
                   "deadline_ms": gf.DEFAULT_SEARCH_DEADLINE_INTERACTIVE_MS,
                   "token": None, "config_error": False}


def test_hook_profile_uses_the_smaller_default_deadline(gf):
    cfg = gf.resolve_search_config(None, profile="hook")
    assert cfg["deadline_ms"] == gf.DEFAULT_SEARCH_DEADLINE_HOOK_MS
    assert gf.DEFAULT_SEARCH_DEADLINE_HOOK_MS < gf.DEFAULT_SEARCH_DEADLINE_INTERACTIVE_MS


def test_env_overrides_win_over_yaml_search_block(gf, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_SEARCH_BACKEND", "service")
    monkeypatch.setenv("GUIDEFOLD_SEARCH_URL", "http://env-wins:9")
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "tok-env")
    cfg = gf.resolve_search_config({"search": {"backend": "local", "url": "http://yaml:1"}},
                                    profile="interactive")
    assert cfg["backend"] == "service"
    assert cfg["url"] == "http://env-wins:9"
    assert cfg["token"] == "tok-env"
    assert cfg["config_error"] is False


def test_unknown_backend_value_falls_back_to_local_with_config_error(gf):
    cfg = gf.resolve_search_config({"search": {"backend": "carrier-pigeon"}}, profile="interactive")
    assert cfg["backend"] == "local"
    assert cfg["config_error"] is True


def test_service_backend_without_url_falls_back_to_local_with_config_error(gf, monkeypatch):
    monkeypatch.delenv("GUIDEFOLD_SEARCH_URL", raising=False)
    cfg = gf.resolve_search_config({"search": {"backend": "service"}}, profile="interactive")
    assert cfg["backend"] == "local"
    assert cfg["config_error"] is True


def test_service_backend_without_token_falls_back_to_local_with_config_error(gf, monkeypatch):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    cfg = gf.resolve_search_config({"search": {"backend": "service", "url": "http://x:1"}},
                                    profile="interactive")
    assert cfg["backend"] == "local"
    assert cfg["config_error"] is True


def test_token_file_is_read_when_env_token_absent(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    token_file = tmp_path / "token.txt"
    token_file.write_text("file-token-value\n")
    cfg = gf.resolve_search_config(
        {"search": {"backend": "service", "url": "http://x:1", "token_file": str(token_file)}},
        profile="interactive")
    assert cfg["token"] == "file-token-value"
    assert cfg["backend"] == "service"
    assert cfg["config_error"] is False


def test_deadline_out_of_range_falls_back_to_default_with_config_error(gf):
    cfg = gf.resolve_search_config({"search": {"deadline_ms": 99999}}, profile="interactive")
    assert cfg["config_error"] is True
    assert cfg["deadline_ms"] == gf.DEFAULT_SEARCH_DEADLINE_INTERACTIVE_MS


def test_token_is_never_present_in_a_resolved_config_repr_when_absent(gf, monkeypatch):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg["token"] is None


# --------------------------------------------------------------------------------- _parse_search_url

def test_parse_search_url_rejects_non_http_scheme(gf):
    with pytest.raises(ValueError):
        gf._parse_search_url("ftp://host/path")


def test_parse_search_url_defaults_port_by_scheme(gf):
    assert gf._parse_search_url("http://host/prefix") == ("http", "host", 80, "/prefix")
    assert gf._parse_search_url("https://host") == ("https", "host", 443, "")


# ---------------------------------------------------------------- backend: local opens no socket

def test_backend_local_never_constructs_a_socket(gf, monkeypatch, tmp_path):
    def _forbidden(*a, **kw):
        raise AssertionError("backend: local must never open a socket")
    monkeypatch.setattr(socket, "socket", _forbidden)
    search_cfg = {"backend": "local", "url": None, "deadline_ms": 300, "token": None, "config_error": False}
    fixed = [_card("urn:skill:x:y:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (fixed, fixed))
    result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=3,
                                     search_id="sid-1", search_cfg=search_cfg)
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] is None
    assert result["selected"] == fixed


# ------------------------------------------------------------------------------------- happy path

def test_happy_path_remote_replaces_local_selection_and_sends_bearer_token(gf, monkeypatch, tmp_path):
    remote_cards = [_card("urn:skill:m:n:remote-a", "rev-a"), _card("urn:skill:m:n:remote-b", "rev-b")]
    local_fixed = [_card("urn:skill:m:n:local-only", "rev-local")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000,
                      "token": "secret-token-abc", "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-happy", search_cfg=search_cfg)
    assert result["backend"] == "online_sparse"
    assert result["degradation_reason"] is None
    assert [c["urn"] for c in result["selected"]] == [c["urn"] for c in remote_cards]
    assert len(ctrl.requests) == 1
    assert ctrl.requests[0]["headers"]["Authorization"] == "Bearer secret-token-abc"
    assert ctrl.requests[0]["payload"]["schema_version"] == "1.1"
    assert ctrl.requests[0]["payload"]["query"] == "q"


def test_client_uses_the_services_ordered_selection_as_is(gf, monkeypatch, tmp_path):
    """Contract: 'the client uses the service's ordered selection as-is' -- no client-side
    resort even though the synthetic display `score` the client assigns is descending anyway."""
    remote_cards = [_card("urn:skill:m:n:third", "r3"), _card("urn:skill:m:n:first", "r1"),
                     _card("urn:skill:m:n:second", "r2")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: ([], []))
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-order", search_cfg=search_cfg)
    assert [c["urn"] for c in result["selected"]] == ["urn:skill:m:n:third", "urn:skill:m:n:first",
                                                        "urn:skill:m:n:second"]


# --------------------------------------------------------------------------- failure classification

@pytest.mark.parametrize("status,expected_reason", [
    (500, "http_5xx"), (503, "http_5xx"),
    (404, "http_4xx"), (400, "http_4xx"),
    (401, "auth"), (403, "auth"),
])
def test_http_error_status_falls_back_to_local_with_the_right_reason(gf, monkeypatch, tmp_path,
                                                                       status, expected_reason):
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))

    def responder(path, payload, headers):
        return status, {"error": "boom"}
    with running_service(responder) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-err", search_cfg=search_cfg)
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == expected_reason
    assert result["selected"] == local_fixed


def test_invalid_json_body_falls_back_to_local_with_invalid_response_reason(gf, monkeypatch, tmp_path):
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))

    port = _find_free_port()

    class RawHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            data = b"not-json{{{"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    server = _Server(("127.0.0.1", port), RawHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        search_cfg = {"backend": "service", "url": f"http://127.0.0.1:{port}", "deadline_ms": 2000,
                      "token": "t", "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-badjson", search_cfg=search_cfg)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == "invalid_response"


def test_malformed_cards_missing_required_fields_falls_back_with_invalid_response_reason(gf, monkeypatch, tmp_path):
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))

    def responder(path, payload, headers):
        return 200, {"schema_version": "1.1", "request_id": "r", "search_id": "s",
                      "cards": [{"urn": "urn:skill:m:n:x"}],  # missing revision/description
                      "ranked": [], "context": {}, "card_context": {}, "composition": {}}
    with running_service(responder) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-malformed", search_cfg=search_cfg)
    assert result["degradation_reason"] == "invalid_response"
    assert result["selected"] == local_fixed


def test_connection_refused_falls_back_to_local_with_connection_reason(gf, monkeypatch, tmp_path):
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    port = _find_free_port()  # nothing is listening here
    search_cfg = {"backend": "service", "url": f"http://127.0.0.1:{port}", "deadline_ms": 2000,
                  "token": "t", "config_error": False}
    t0 = time.perf_counter()
    result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=3,
                                     search_id="sid-refused", search_cfg=search_cfg)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == "connection"
    assert elapsed_ms < 2000  # a refused connection must not wait out the full deadline


# ------------------------------------------------------------------------------------- deadline race

def test_timeout_falls_back_to_local_within_deadline_plus_small_epsilon(gf, monkeypatch, tmp_path):
    """The mock server never responds (holds the connection open past the deadline). The client
    must return within deadline_ms + a small epsilon -- NOT wait for the server's own delay.
    Wall time is measured around search_with_backend itself, isolating it from interpreter
    startup/Index.build() overhead that a subprocess-level measurement would also include."""
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))

    def responder(path, payload, headers):
        return 200, {"schema_version": "1.1", "request_id": "r", "search_id": "s", "cards": [],
                     "ranked": [], "context": {}, "card_context": {}, "composition": {}}
    with running_service(responder, delay_s=2.0) as (url, ctrl):  # far longer than deadline_ms below
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 200, "token": "t",
                      "config_error": False}
        t0 = time.perf_counter()
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-timeout", search_cfg=search_cfg)
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == "timeout"
    assert result["selected"] == local_fixed
    epsilon_ms = 100  # generous for a shared/loaded CI machine; see docs note on this constant
    assert elapsed_ms <= 200 + epsilon_ms, f"took {elapsed_ms:.1f}ms against a 200ms deadline"


def test_late_remote_reply_is_ignored_after_the_deadline(gf, monkeypatch, tmp_path):
    """The server eventually DOES answer (200, valid cards) -- but only after this call has
    already returned on the local fallback. The reply must never retroactively change the
    result (ADR-0023 Sec3: abandoned, never joined)."""
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    remote_cards = [_card("urn:skill:m:n:too-late")]
    with running_service(_search_ok(remote_cards), delay_s=0.6) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 150, "token": "t",
                      "config_error": False}
        t0 = time.perf_counter()
        result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-late", search_cfg=search_cfg)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms <= 150 + 100
        assert result["backend"] == "local_sparse"
        assert result["degradation_reason"] == "timeout"
        assert result["selected"] == local_fixed
        # let the server's delayed handler actually finish inside the `with` block so its thread
        # doesn't outlive the fixture's own shutdown by more than the delay above.
        time.sleep(0.7)
    assert len(ctrl.requests) == 1  # the request WAS received -- only its late reply is ignored


# ---------------------------------------------------------------------------- E2.9 parity counter

def test_matching_local_and_remote_selection_emits_no_parity_event(gf, monkeypatch, tmp_path):
    same = [_card("urn:skill:m:n:agree-a"), _card("urn:skill:m:n:agree-b")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (same, same))
    with running_service(_search_ok(same)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), "help with kafka ingestion", "_root",
                                         profile="interactive", k=3, search_id="sid-agree",
                                         search_cfg=search_cfg)
    assert result["parity_mismatch"] is False
    events = _spool_events(tmp_path)
    assert not [e for e in events if e["event_type"] == "telemetry_health.parity_mismatch"]


def test_mismatched_local_and_remote_selection_emits_hash_only_parity_event(gf, monkeypatch, tmp_path):
    local_fixed = [_card("urn:skill:m:n:local-answer")]
    remote_cards = [_card("urn:skill:m:n:remote-answer")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    secret_query = "a very specific proprietary query about our payment system"
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        result = gf.search_with_backend(tmp_path, object(), secret_query, "_root",
                                         profile="interactive", k=3, search_id="sid-mismatch",
                                         search_cfg=search_cfg)
    assert result["parity_mismatch"] is True
    events = _spool_events(tmp_path)
    mismatches = [e for e in events if e["event_type"] == "telemetry_health.parity_mismatch"]
    assert len(mismatches) == 1
    fields = mismatches[0]
    local_hash = gf._selected_set_hash(local_fixed)
    remote_hash = gf._selected_set_hash(remote_cards)
    assert fields["local_hash"] == local_hash
    assert fields["remote_hash"] == remote_hash
    assert fields["local_hash"] != fields["remote_hash"]
    assert fields["search_id"] == "sid-mismatch"
    # never the query text, never a card description/body -- hash-only per E2.9's own non-negotiable
    raw = json.dumps(fields)
    assert secret_query not in raw
    assert "local-answer" not in raw
    assert "remote-answer" not in raw
    assert "description" not in raw


def test_token_never_appears_anywhere_in_the_telemetry_spool(gf, monkeypatch, tmp_path):
    distinctive_token = "SUPER-SECRET-TOKEN-VALUE-0xdeadbeef"
    local_fixed = [_card("urn:skill:m:n:local-only")]
    remote_cards = [_card("urn:skill:m:n:remote-only")]  # deliberately different -> parity event too
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000,
                      "token": distinctive_token, "config_error": False}
        gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=3,
                                search_id="sid-token", search_cfg=search_cfg)
    spool = Path(tmp_path) / ".guidefold" / "telemetry" / "spool"
    for f in spool.rglob("events-*.jsonl") if spool.is_dir() else []:
        assert distinctive_token not in f.read_text(encoding="utf-8")
    # and it DID leave the client for the request itself (that's the point of Bearer auth) --
    # this asserts absence from OUR OWN local spool, not from the wire.
    assert ctrl.requests[0]["headers"]["Authorization"] == "Bearer " + distinctive_token


# ------------------------------------------------------------------------------------- _use_via_service

def _use_ok(skill_id, revision, body_text, request_id="req-use-1"):
    checksum = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    def responder(path, payload, headers):
        if path == "/v1/use":
            return 200, {"schema_version": "1.1", "request_id": request_id, "skill_id": skill_id,
                         "revision": revision, "body": body_text, "checksum": checksum,
                         "context": {}, "execution_observed": False, "search_id_verified": False}
        return 404, {"error": "not_found"}
    return responder


def test_use_via_service_happy_path_returns_body_and_checksum(gf):
    with running_service(_use_ok("urn:skill:m:n:x", "rev-9", "# Title\nbody\n")) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        body, reason = gf._use_via_service(search_cfg, "urn:skill:m:n:x", "rev-9")
    assert reason is None
    assert body["skill_id"] == "urn:skill:m:n:x"
    assert body["revision"] == "rev-9"
    assert body["checksum"] == hashlib.sha256(b"# Title\nbody\n").hexdigest()


def test_use_via_service_auth_failure_reports_auth_reason(gf):
    def responder(path, payload, headers):
        return 401, {"error": "unauthorized"}
    with running_service(responder) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "bad",
                      "config_error": False}
        body, reason = gf._use_via_service(search_cfg, "urn:skill:m:n:x", "rev-9")
    assert body is None
    assert reason == "auth"


# ------------------------------------------------------------------------------------- cmd_load service branch

def test_cmd_load_service_requires_urn_at_revision(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    root = tmp_path / "repo"
    root.mkdir()
    cfg = {"search": {"backend": "service", "url": "http://127.0.0.1:1"}}
    a = type("Args", (), {"urn": "urn:skill:m:n:x"})()  # no "@revision"
    with pytest.raises(SystemExit) as exc:
        gf.cmd_load(a, root, cfg)
    assert "@<revision>" in str(exc.value) or "@" in str(exc.value)


def test_cmd_load_service_happy_path_writes_cache(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()
    body_text = "# A Skill\n\nBody.\n"
    with running_service(_use_ok("urn:skill:m:n:x", "rev-9", body_text)) as (url, ctrl):
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": "urn:skill:m:n:x@rev-9"})()
        gf.cmd_load(a, root, cfg)
    events = _spool_events(root)
    completed = [e for e in events if e["event_type"] == "skill_load_completed"]
    assert completed and completed[0]["status"] == "ok"
    assert completed[0]["cache_source"] == "service"


def test_cmd_load_service_checksum_mismatch_refuses(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()

    def responder(path, payload, headers):
        return 200, {"schema_version": "1.1", "request_id": "r", "skill_id": "urn:skill:m:n:x",
                     "revision": "rev-9", "body": "tampered body", "checksum": "0" * 64,
                     "context": {}, "execution_observed": False, "search_id_verified": False}
    with running_service(responder) as (url, ctrl):
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": "urn:skill:m:n:x@rev-9"})()
        with pytest.raises(SystemExit) as exc:
            gf.cmd_load(a, root, cfg)
    assert "checksum" in str(exc.value)


# ------------------------------------------------------------------------------------------ py_compile

def test_cli_still_compiles_clean():
    import py_compile
    py_compile.compile(str(Path(__file__).resolve().parent.parent /
                            "skills" / "guidefold" / "scripts" / "guidefold"),
                        doraise=True)
