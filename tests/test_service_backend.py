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
                   "token": None, "config_error": False,
                   "token_source": None, "org": None, "repo": None}


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


# --------------------------------------------------------------- resolve_search_config: login token

def _write_credentials(monkeypatch, tmp_path, entries, filename="creds-under-test.json"):
    """`entries`: {api_url: {"token": ..., "org": ...}} -- the same shape `guidefold login`
    writes to `_credentials_path()`. Points the already-isolated GUIDEFOLD_CREDENTIALS
    (conftest's `_isolate_guidefold_credentials`) at a fresh file holding them."""
    path = tmp_path / filename
    path.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setenv("GUIDEFOLD_CREDENTIALS", str(path))
    return path


def test_login_token_used_as_last_resort_when_exactly_one_api_is_stored(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    _write_credentials(monkeypatch, tmp_path,
                        {"https://api.example.com": {"token": "login-token-1", "org": "acme"}})
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg["token"] == "login-token-1"
    assert cfg["token_source"] == "login"
    assert cfg["org"] == "acme"


def test_login_token_is_used_by_the_hook_profile_with_no_guidefold_yaml(gf, monkeypatch, tmp_path):
    """`hook` calls `resolve_search_config(None, profile="hook", root=...)` -- cfg stays None
    (E1.5: no guidefold.yaml/PyYAML on the hook path), so this exercises the exact call hook
    makes, not just the interactive one."""
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    _write_credentials(monkeypatch, tmp_path,
                        {"https://api.example.com": {"token": "login-token-hook", "org": "acme"}})
    root = tmp_path / "repo"
    root.mkdir()
    cfg = gf.resolve_search_config(None, profile="hook", root=root)
    assert cfg["token"] == "login-token-hook"
    assert cfg["token_source"] == "login"
    assert cfg["org"] == "acme"
    assert cfg["repo"]     # `_default_repo_id(root)`, no guidefold.yaml needed


def test_explicit_env_token_wins_over_a_stored_login_token(gf, monkeypatch, tmp_path):
    """The explicit override must still win (GUIDEFOLD_TOKEN > token_file > login), even when a
    login token is also on disk."""
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "env-wins-token")
    _write_credentials(monkeypatch, tmp_path,
                        {"https://api.example.com": {"token": "login-token-1", "org": "acme"}})
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg["token"] == "env-wins-token"
    assert cfg["token_source"] == "env"
    assert cfg["org"] is None


def test_explicit_token_file_wins_over_a_stored_login_token(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    token_file = tmp_path / "token.txt"
    token_file.write_text("file-token-value\n")
    _write_credentials(monkeypatch, tmp_path,
                        {"https://api.example.com": {"token": "login-token-1", "org": "acme"}})
    cfg = gf.resolve_search_config({"search": {"token_file": str(token_file)}}, profile="interactive")
    assert cfg["token"] == "file-token-value"
    assert cfg["token_source"] == "token_file"
    assert cfg["org"] is None


def test_login_token_picks_the_entry_matching_configured_service_api(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    _write_credentials(monkeypatch, tmp_path, {
        "https://api.acme.example": {"token": "acme-token", "org": "acme"},
        "https://api.other.example": {"token": "other-token", "org": "other"},
    })
    cfg = gf.resolve_search_config({"service": {"api": "https://api.other.example"}}, profile="interactive")
    assert cfg["token"] == "other-token"
    assert cfg["org"] == "other"


def test_login_token_is_ambiguous_with_two_apis_and_no_configured_service_api(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    _write_credentials(monkeypatch, tmp_path, {
        "https://api.acme.example": {"token": "acme-token", "org": "acme"},
        "https://api.other.example": {"token": "other-token", "org": "other"},
    })
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg["token"] is None
    assert cfg["token_source"] is None


def test_no_stored_credentials_leaves_token_none(gf, monkeypatch, tmp_path):
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    cfg = gf.resolve_search_config(None, profile="interactive")
    assert cfg["token"] is None
    assert cfg["token_source"] is None


# ------------------------------------------------------------------------ _search_extra_headers

def test_search_extra_headers_empty_for_env_or_token_file_source(gf):
    assert gf._search_extra_headers({"token_source": "env", "org": "acme", "repo": "r"}) == {}
    assert gf._search_extra_headers({"token_source": "token_file", "org": "acme", "repo": "r"}) == {}
    assert gf._search_extra_headers({}) == {}


def test_search_extra_headers_set_for_login_source(gf):
    headers = gf._search_extra_headers({"token_source": "login", "org": "acme", "repo": "myrepo"})
    assert headers == {"X-Guidefold-Org": "acme", "X-Guidefold-Repo": "myrepo"}


def test_search_extra_headers_omits_missing_org_or_repo(gf):
    assert gf._search_extra_headers({"token_source": "login", "org": None, "repo": "myrepo"}) \
        == {"X-Guidefold-Repo": "myrepo"}
    assert gf._search_extra_headers({"token_source": "login", "org": "acme", "repo": None}) \
        == {"X-Guidefold-Org": "acme"}


def test_login_token_sends_org_and_repo_headers_over_the_wire(gf, monkeypatch, tmp_path):
    """End-to-end: a `search.backend: service` request authenticated with a stored login token
    (no GUIDEFOLD_TOKEN, no token_file) carries X-Guidefold-Org/X-Guidefold-Repo (API-CONTRACT
    §2/§3) so the server can resolve the request's org/repo -- a personal token is not bound to
    one the way an installation token is."""
    monkeypatch.delenv("GUIDEFOLD_TOKEN", raising=False)
    _write_credentials(monkeypatch, tmp_path,
                        {"https://api.example.com": {"token": "login-token-1", "org": "acme"}})
    remote_cards = [_card("urn:skill:m:n:remote-a")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: ([], []))
    root = tmp_path / "repo"
    root.mkdir()
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = gf.resolve_search_config({"search": {"backend": "service", "url": url}},
                                               profile="interactive", root=root)
        assert search_cfg["token_source"] == "login"
        result = gf.search_with_backend(root, object(), "q", "_root", profile="interactive",
                                         k=3, search_id="sid-login-headers", search_cfg=search_cfg)
    assert result["backend"] == "online_sparse"
    assert len(ctrl.requests) == 1
    sent = ctrl.requests[0]["headers"]
    assert sent["Authorization"] == "Bearer login-token-1"
    assert sent["X-Guidefold-Org"] == "acme"
    assert "X-Guidefold-Repo" in sent


def test_installation_token_never_sends_org_or_repo_headers(gf, monkeypatch, tmp_path):
    """An env/token_file credential (typically an installation token, already bound to one
    org/repo server-side) must never carry these headers -- a mismatched header there is a hard
    403, not a no-op (API-CONTRACT §2)."""
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "installation-token-1")
    remote_cards = [_card("urn:skill:m:n:remote-a")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: ([], []))
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = gf.resolve_search_config({"search": {"backend": "service", "url": url}},
                                               profile="interactive", root=tmp_path)
        assert search_cfg["token_source"] == "env"
        gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive",
                                k=3, search_id="sid-install-headers", search_cfg=search_cfg)
    assert len(ctrl.requests) == 1
    sent = ctrl.requests[0]["headers"]
    assert "X-Guidefold-Org" not in sent
    assert "X-Guidefold-Repo" not in sent


# --------------------------------------------------------------------------------- _parse_search_url

def test_parse_search_url_rejects_non_http_scheme(gf):
    with pytest.raises(ValueError):
        gf._parse_search_url("ftp://host/path")


def test_parse_search_url_defaults_port_by_scheme(gf):
    assert gf._parse_search_url("http://host/prefix") == ("http", "host", 80, "/prefix")
    assert gf._parse_search_url("https://host") == ("https", "host", 443, "")


def test_download_service_resource_checks_bytes_and_digest(gf):
    resource = b"source bytes\n"
    digest = hashlib.sha256(resource).hexdigest()
    port = _find_free_port()

    class ResourceHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/v1/skills/u/revisions/r/resources/references%2Fsource.md"
            assert self.headers.get("Authorization") == "Bearer t"
            self.send_response(200)
            self.send_header("Content-Length", str(len(resource)))
            self.send_header("X-Content-SHA256", digest)
            self.end_headers()
            self.wfile.write(resource)

        def log_message(self, *a):
            pass

    server = _Server(("127.0.0.1", port), ResourceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cfg = {"url": f"http://127.0.0.1:{port}", "deadline_ms": 2000, "token": "t"}
        data, reason = gf._download_service_resource(cfg, {
            "url": "/v1/skills/u/revisions/r/resources/references%2Fsource.md",
            "sha256": digest, "size": len(resource)})
        assert data == resource and reason is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_download_service_resource_rejects_redirected_or_query_urls(gf):
    digest = hashlib.sha256(b"x").hexdigest()
    cfg = {"url": "http://127.0.0.1:1", "deadline_ms": 2000, "token": "t"}
    for url in (
        "https://evil.example/v1/skills/u/revisions/r/resources/x",
        "/v1/search?query=secret",
        "/other-endpoint",
    ):
        data, reason = gf._download_service_resource(cfg, {
            "url": url, "sha256": digest, "size": 1})
        assert data is None and reason == "invalid_response"


def test_fetch_service_resources_rejects_skill_body_overwrite(gf):
    digest = hashlib.sha256(b"x").hexdigest()
    cfg = {"url": "http://127.0.0.1:1", "deadline_ms": 2000, "token": "t"}
    data, reason = gf._fetch_service_resources(cfg, {"resources": [{
        "path": "skill.md", "url": "/v1/skills/u/revisions/r/resources/skill.md",
        "sha256": digest, "size": 1, "required": True}]})
    assert data is None and reason == "invalid_response"


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
    assert ctrl.requests[0]["payload"]["budget"] == {"max_cards": 3}


@pytest.mark.parametrize("k", [0, 1, 3, 4])
def test_budget_max_cards_is_sent_for_every_representable_k(gf, monkeypatch, tmp_path, k):
    """E2.9 fixture audit (2026-09-05, cross-checked against the service worktree's independent
    MERIDIAN-GRAPH-PARITY-2026-09-05.md finding of the same defect): the client used to omit
    `budget` entirely, so the Go/ParadeDB service silently applied its OWN default of 4 regardless
    of the caller's actual local k (hook's k=3, find's default k=8, any --limit). `budget.max_cards`
    is 0..4 per contract v1.1 -- the client must send the real k whenever it fits so both sides
    target the same selection size."""
    remote_cards = [_card(f"urn:skill:m:n:r{i}") for i in range(4)]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: ([], []))
    with running_service(_search_ok(remote_cards)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=k,
                                search_id=f"sid-budget-{k}", search_cfg=search_cfg)
    assert ctrl.requests[0]["payload"]["budget"] == {"max_cards": k}


@pytest.mark.parametrize("k", [5, 8, -1])
def test_unrepresentable_k_never_races_the_service_backend(gf, monkeypatch, tmp_path, k):
    """Contract v1.1's `budget.max_cards` tops out at 4 (and bottoms out at 0): find's default
    k=8 (and any k outside 0..4) cannot be expressed on the wire at all. Clamping it and comparing
    against a different local limit would still misreport a budget difference as a ranking parity
    mismatch (the service worktree's report is explicit that this must not happen) -- so, exactly
    like include_deprecated, never open the socket and fall back to local with a visible reason."""
    def _forbidden(*a, **kw):
        raise AssertionError(f"k={k} must never race the service backend")
    monkeypatch.setattr(socket, "socket", _forbidden)
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    search_cfg = {"backend": "service", "url": "http://127.0.0.1:1", "deadline_ms": 2000,
                  "token": "t", "config_error": False}
    result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=k,
                                     search_id=f"sid-k-{k}", search_cfg=search_cfg)
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == "config"
    assert result["selected"] == local_fixed


def test_include_deprecated_never_races_the_service_backend(gf, monkeypatch, tmp_path):
    """E2.9 fixture audit (2026-09-05): Contract v1.1's search_request has no field for
    include_deprecated, and the Go/ParadeDB service unconditionally excludes deprecated cards --
    no override exists on that side either. So `--include-deprecated --backend service` can never
    get an honest remote answer: racing it anyway would silently drop deprecated cards the caller
    explicitly asked to see, with no visible sign of the discrepancy. The fix is to never open the
    socket in this combination and fall back to local with a visible "config" degradation reason,
    exactly like any other backend:service config the service structurally cannot satisfy."""
    def _forbidden(*a, **kw):
        raise AssertionError("include_deprecated=True must never race the service backend")
    monkeypatch.setattr(socket, "socket", _forbidden)
    local_fixed = [_card("urn:skill:m:n:local-only")]
    monkeypatch.setattr(gf, "_local_selected", lambda *a, **kw: (local_fixed, local_fixed))
    search_cfg = {"backend": "service", "url": "http://127.0.0.1:1", "deadline_ms": 2000,
                  "token": "t", "config_error": False}
    result = gf.search_with_backend(tmp_path, object(), "q", "_root", profile="interactive", k=3,
                                     search_id="sid-incdep", include_deprecated=True,
                                     search_cfg=search_cfg)
    assert result["backend"] == "local_sparse"
    assert result["degradation_reason"] == "config"
    assert result["selected"] == local_fixed


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


def _use_proof_ask(skill_id, revision, request_id="req-proof-ask"):
    """Minimal valid USE 1.2 abstention: the body is empty and provenance is bounded."""
    def responder(path, payload, headers):
        if path == "/v1/use":
            return 200, {
                "schema_version": "1.2", "request_id": request_id, "skill_id": skill_id,
                "revision": revision, "status": "ask", "body": "",
                "checksum": hashlib.sha256(b"").hexdigest(), "context": {},
                "execution_observed": False, "search_id_verified": False,
                "delivery": {
                    "action": "ASK", "reason": "proof_missing",
                    "missing": [{"requirement": "source_proof", "reason": "no proof"}],
                    "provenance": {"schema": "source-proof-v1", "snapshot": "snap",
                                   "skill_id": skill_id, "revision": revision,
                                   "body_sha256": "0" * 64, "scopes": [], "claims": []},
                },
            }
        return 404, {"error": "not_found"}
    return responder


def _use_proof_load(skill_id, revision, body_text, request_id="req-proof-load"):
    checksum = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    def responder(path, payload, headers):
        if path == "/v1/use":
            return 200, {
                "schema_version": "1.2", "request_id": request_id, "skill_id": skill_id,
                "revision": revision, "status": "hydrated", "body": body_text,
                "checksum": checksum, "context": {},
                "execution_observed": False, "search_id_verified": False,
                "delivery": {
                    "action": "LOAD", "reason": "source_proof_complete", "missing": [],
                    "provenance": {"schema": "source-proof-v1", "snapshot": "snap",
                                   "skill_id": skill_id, "revision": revision,
                                   "body_sha256": checksum, "scopes": ["_root"],
                                   "claims": [{"id": "body", "status": "supported",
                                               "source_refs": [{"path": "SKILL.md",
                                                                "sha256": checksum,
                                                                "line_from": 1, "line_to": 1}]}]},
                },
            }
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


def test_use_via_service_proof_gated_sends_12_and_returns_ask(gf):
    skill_id, revision = "urn:skill:m:n:x", "rev-9"
    with running_service(_use_proof_ask(skill_id, revision)) as (url, ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        body, reason = gf._use_via_service(search_cfg, skill_id, revision, "proof_gated")
    assert reason == "ask"
    assert body["delivery"]["action"] == "ASK"
    assert ctrl.requests[0]["payload"]["schema_version"] == "1.2"
    assert ctrl.requests[0]["payload"]["delivery_policy"] == "proof_gated"


def test_use_via_service_proof_gated_rejects_inconsistent_load(gf):
    skill_id, revision = "urn:skill:m:n:x", "rev-9"

    def responder(path, payload, headers):
        if path == "/v1/use":
            return 200, {
                "schema_version": "1.2", "request_id": "r", "skill_id": skill_id,
                "revision": revision, "status": "ask", "body": "must not cache",
                "checksum": "0" * 64, "delivery": {
                    "action": "LOAD", "reason": "source_proof_complete", "missing": [],
                    "provenance": {},
                },
            }
        return 404, {"error": "not_found"}

    with running_service(responder) as (url, _ctrl):
        search_cfg = {"backend": "service", "url": url, "deadline_ms": 2000, "token": "t",
                      "config_error": False}
        body, reason = gf._use_via_service(search_cfg, skill_id, revision, "proof_gated")
    assert body is None
    assert reason == "invalid_response"


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


def test_cmd_load_proof_gated_ask_does_not_write_cache(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    cache = tmp_path / "cache"
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(cache))
    root = tmp_path / "repo"
    root.mkdir()
    skill_id, revision = "urn:skill:m:n:x", "rev-9"
    with running_service(_use_proof_ask(skill_id, revision)) as (url, ctrl):
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": skill_id + "@" + revision,
                               "delivery_policy": "proof_gated"})()
        with pytest.raises(SystemExit) as exc:
            gf.cmd_load(a, root, cfg)
    assert "ASK" in str(exc.value)
    assert "proof_missing" in str(exc.value)
    assert not list(cache.rglob("SKILL.md"))
    assert ctrl.requests[0]["payload"]["schema_version"] == "1.2"
    completed = [e for e in _spool_events(root) if e["event_type"] == "skill_load_completed"]
    assert completed and completed[0]["status"] == "denied"


def test_cmd_load_proof_gated_load_writes_verified_body(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()
    skill_id, revision, body_text = "urn:skill:m:n:x", "rev-9", "# A proven skill\n"
    with running_service(_use_proof_load(skill_id, revision, body_text)) as (url, ctrl):
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": skill_id + "@" + revision,
                               "delivery_policy": "proof_gated"})()
        gf.cmd_load(a, root, cfg)
    assert ctrl.requests[0]["payload"]["delivery_policy"] == "proof_gated"
    cached = list((tmp_path / "cache").rglob("SKILL.md"))
    assert len(cached) == 1 and cached[0].read_text(encoding="utf-8") == body_text
    completed = [e for e in _spool_events(root) if e["event_type"] == "skill_load_completed"]
    assert completed and completed[0]["status"] == "ok" and completed[0]["bytes"] == len(body_text.encode())


def test_cmd_load_proof_gated_writes_verified_package_resources(gf, tmp_path, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()
    skill_id, revision, body_text = "urn:skill:m:n:x", "rev-9", "# Proven package\n"
    resource = b"# Source reference\n"
    with running_service(_use_proof_load(skill_id, revision, body_text)) as (url, _ctrl):
        monkeypatch.setattr(gf, "_fetch_service_resources",
                            lambda cfg, body: ([('references/policy.md', resource)], None))
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": skill_id + "@" + revision,
                               "delivery_policy": "proof_gated"})()
        gf.cmd_load(a, root, cfg)
    cached = list((tmp_path / "cache").rglob("SKILL.md"))
    assert len(cached) == 1
    assert cached[0].read_text(encoding="utf-8") == body_text
    assert (cached[0].parent / "references" / "policy.md").read_bytes() == resource


def test_cmd_load_proof_gated_rejects_local_backend(gf, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    cfg = {"search": {"backend": "local"}}
    a = type("Args", (), {"urn": "urn:skill:m:n:x@rev-9", "delivery_policy": "proof_gated"})()
    with pytest.raises(SystemExit) as exc:
        gf.cmd_load(a, root, cfg)
    assert "requires search.backend: service" in str(exc.value)


# ------------------------------------------------------------------------------------------ py_compile

def test_cli_still_compiles_clean():
    import py_compile
    py_compile.compile(str(Path(__file__).resolve().parent.parent /
                            "skills" / "guidefold" / "scripts" / "guidefold"),
                        doraise=True)


# ---- D12 (pilot rehearsal 2026-09-15): every failed /v1/use used to print "(auth)"

def _use_error(status, code, message, hint=None):
    def responder(path, payload, headers):
        body = {"error": code, "message": message, "request_id": "req-d12"}
        if hint:
            body["hint"] = hint
        return status, body
    return responder


def _load_failure_message(gf, tmp_path, monkeypatch, responder):
    monkeypatch.setenv("GUIDEFOLD_TOKEN", "t")
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    with running_service(responder) as (url, _ctrl):
        cfg = {"search": {"backend": "service", "url": url}}
        a = type("Args", (), {"urn": "urn:skill:m:n:x@rev-9"})()
        with pytest.raises(SystemExit) as exc:
            gf.cmd_load(a, root, cfg)
    # `sys.exit(<message>)` prints the message and exits 1, which is the documented exit code
    # for a failed `load` (docs/CONVENTIONS.md §14).
    status = 1 if isinstance(exc.value.code, str) else exc.value.code
    return status, str(exc.value)


def test_cmd_load_names_a_403_as_a_repository_permission_not_as_auth(gf, tmp_path, monkeypatch):
    """403 is "this token may not read this org/repo", which is what made D5 look like a
    sign-in problem for a whole rehearsal (report §4 D12)."""
    code, message = _load_failure_message(gf, tmp_path, monkeypatch, _use_error(
        403, "forbidden", "This token may not read repository `guidefold`.",
        hint="Check the organisation and repository this checkout is configured for."))
    assert code == 1
    assert "403" in message and "forbidden" in message
    assert "This token may not read repository `guidefold`." in message
    assert "Check the organisation and repository" in message
    assert "guidefold doctor" in message


def test_cmd_load_names_a_409_revision_mismatch_and_says_which_revision_to_use(
        gf, tmp_path, monkeypatch):
    code, message = _load_failure_message(gf, tmp_path, monkeypatch, _use_error(
        409, "revision_mismatch", "revision rev-9 is not delivered by the active snapshot"))
    assert code == 1
    assert "409" in message and "revision_mismatch" in message
    assert "revision rev-9 is not delivered by the active snapshot" in message
    assert "guidefold find" in message
    assert "card_revision" in message


def test_cmd_load_names_a_503_snapshot_policy_mismatch_as_a_republish(gf, tmp_path, monkeypatch):
    code, message = _load_failure_message(gf, tmp_path, monkeypatch, _use_error(
        503, "snapshot_policy_mismatch", "the snapshot was built by another CLI"))
    assert code == 1
    assert "503" in message and "snapshot_policy_mismatch" in message
    assert "re-import" in message or "publish" in message


def test_the_three_failures_do_not_print_the_same_word(gf, tmp_path, monkeypatch):
    messages = set()
    for i, (status, code, text) in enumerate((
            (403, "forbidden", "no access"),
            (409, "revision_mismatch", "wrong revision"),
            (503, "snapshot_policy_mismatch", "stale snapshot"))):
        _c, message = _load_failure_message(gf, tmp_path / f"case{i}", monkeypatch,
                                            _use_error(status, code, text))
        messages.add(message)
    assert len(messages) == 3, messages
    assert not any(m.startswith("guidefold: service USE failed (auth)") for m in messages)
