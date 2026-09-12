from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "bridge.py"
spec = importlib.util.spec_from_file_location("pilot_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bridge)


class _Handler(BaseHTTPRequestHandler):
    requests: list[tuple[str, dict]] = []
    search_count = 0

    def do_POST(self):  # noqa: N802 - stdlib handler API
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        self.requests.append((self.path, payload))
        if self.path == "/v1/search":
            type(self).search_count += 1
            body = {"search_id": f"search-{self.search_count}", "snapshot": "repository:test",
                    "cards": [{"skill_id": f"skill-{self.search_count}", "revision": "rev-1", "name": "test", "node": "scope"}],
                    "ranked": [{"skill_id": f"skill-{self.search_count}", "score": 10 if self.search_count == 1 else 100}],
                    "card_context": "card", "context": {"delivery_status": "complete"}}
        elif self.path == "/v1/use":
            body = {"status": "ask", "delivery": {"action": "ASK", "reason": "proof_conflict"}, "body": "", "missing": ["proof_conflict"]}
        else:
            self.send_response(404); self.end_headers(); return
        encoded = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)

    def log_message(self, *_args):
        return


def _server():
    _Handler.requests = []
    _Handler.search_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_hierarchical_search_merges_scoped_calls_and_redacts_trace(tmp_path, monkeypatch, capsys):
    server, thread = _server()
    try:
        query = tmp_path / "query.txt"; query.write_text("do the task\n", encoding="utf-8")
        nodes = tmp_path / "nodes.json"; nodes.write_text(json.dumps({"repo_id": "repo", "revision": "rev", "scopes": ["root/deep", "root"]}), encoding="utf-8")
        token = tmp_path / "token"; token.write_text("secret-token", encoding="utf-8")
        trace = tmp_path / "trace.jsonl"
        monkeypatch.setenv("GUIDEFOLD_TRACE_FILE", str(trace)); monkeypatch.setenv("GUIDEFOLD_TASK_ID", "task-1")
        code = bridge.main(["--url", f"http://127.0.0.1:{server.server_port}", "--token-file", str(token), "--nodes-file", str(nodes), "search", "--strategy", "top_down", "--query-file", str(query)])
        assert code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["search_requests"] == 2
        assert output["cards"][0]["skill_id"] == "skill-2", "merge must use ranked scores, not lexical card order"
        assert [payload["workspace"]["cwd"] for path, payload in _Handler.requests if path == "/v1/search"] == ["root", "root/deep"]
        trace_text = trace.read_text(encoding="utf-8")
        assert "secret-token" not in trace_text and "do the task" not in trace_text
        assert '"path":"/v1/search"' in trace_text
        assert '"result_count":1' in trace_text
    finally:
        server.shutdown(); thread.join(timeout=2); server.server_close()


def test_use_reports_ask_without_body(tmp_path, monkeypatch, capsys):
    server, thread = _server()
    try:
        nodes = tmp_path / "nodes.json"; nodes.write_text(json.dumps({"repo_id": "repo", "revision": "rev", "cwd": "."}), encoding="utf-8")
        token = tmp_path / "token"; token.write_text("secret-token", encoding="utf-8")
        trace_path = tmp_path / "trace.jsonl"
        monkeypatch.setenv("GUIDEFOLD_TRACE_FILE", str(trace_path))
        monkeypatch.setenv("GUIDEFOLD_TASK_ID", "task-2")
        code = bridge.main(["--url", f"http://127.0.0.1:{server.server_port}", "--token-file", str(token), "--nodes-file", str(nodes), "use", "--skill-id", "skill-1", "--revision", "rev-1"])
        assert code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["action"] == "ASK" and output["body"] == ""
        assert _Handler.requests[-1][1]["delivery_policy"] == "proof_gated"
        trace = trace_path.read_text(encoding="utf-8")
        assert '"reason":"proof_conflict"' in trace
    finally:
        server.shutdown(); thread.join(timeout=2); server.server_close()


def test_legacy_use_keeps_the_1_1_wire_contract(tmp_path, monkeypatch, capsys):
    server, thread = _server()
    try:
        nodes = tmp_path / "nodes.json"; nodes.write_text(json.dumps({"repo_id": "repo", "cwd": "."}), encoding="utf-8")
        token = tmp_path / "token"; token.write_text("secret-token", encoding="utf-8")
        code = bridge.main(["--url", f"http://127.0.0.1:{server.server_port}", "--token-file", str(token), "--nodes-file", str(nodes), "use", "--delivery-policy", "legacy", "--skill-id", "skill-1", "--revision", "rev-1"])
        assert code == 0
        capsys.readouterr()
        payload = _Handler.requests[-1][1]
        assert payload["schema_version"] == "1.1" and "delivery_policy" not in payload
    finally:
        server.shutdown(); thread.join(timeout=2); server.server_close()
