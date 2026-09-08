"""In-process stand-in for the hosted management API (docs/PIVOT-ARCHITECTURE.md, the pivot
engineering brief) used by the pivot CLI tests.

Same rule as `tests/test_service_backend.py`: a real `http.server.ThreadingHTTPServer` on
127.0.0.1 speaking the actual wire contract, never a third-party HTTP mock and never a
monkeypatched `urllib` internal -- the point of these tests is the transport the CLI really
uses. The server records every request (method, path, headers, body) so a test can assert on
what was uploaded, how many times, and with which headers.
"""
import http.server
import json
import re
import socket
import threading
from contextlib import contextmanager


class ManagementAPI:
    """State + scripted behaviour for one test's server.

    Blob storage is real: `PUT .../blobs/{sha}` stores the bytes and `POST .../imports` answers
    with exactly the hashes it does not have yet, which is what makes "the second sync uploads
    0 new blobs" and "resume uploads only what is still missing" observable rather than
    asserted-by-construction.
    """

    def __init__(self):
        self.requests = []          # every request, in order
        self.blobs = {}             # sha256 -> bytes actually received
        self.blob_puts = []         # sha256 of every SUCCESSFUL put, in order (duplicate check)
        self.imports = {}           # import_id -> record
        self.import_by_key = {}     # manifest digest -> import_id
        self.repos = set()
        self.finalized = []
        self.next_import = 1

        # Scripted failures / flows.
        self.fail_put_shas = {}     # sha -> remaining number of times to fail with 500
        self.device_token_script = []   # list of (status, body) consumed per poll
        self.device_start = None
        self.me = None
        self.health = {"status": "ready", "api_schema_versions": ["1.1", "1.2"]}
        self.proposals = []
        self.exports = {}
        self.import_view_extra = {}
        # P08 `extract`: the one-shot plan the server answers with, the jobs it starts, and
        # the scope error a CI token with too few scopes gets instead.
        self.plan = {"profile": "one_shot", "groups": [], "limits": {}, "groups_skipped": {},
                     "estimated_usd_max": 0.0, "estimated_calls": 0}
        self.generate_job_ids = ["job_1"]
        self.generate_error = None
        self.extract_jobs = []

    # ---------------------------------------------------------------- helpers for the tests
    def fail_next_put(self, sha, times=1):
        self.fail_put_shas[sha] = times

    def puts(self):
        return [r for r in self.requests if r["method"] == "PUT"]

    def manifests(self):
        return [r["json"]["manifest"] for r in self.requests
                if r["method"] == "POST" and r["path"].endswith("/imports") and r["json"]]

    # ------------------------------------------------------------------------- the routing
    def handle(self, method, path, headers, body):
        raw_path = path.split("?", 1)[0]
        payload = None
        if body:
            try:
                payload = json.loads(body)
            except Exception:
                payload = None
        self.requests.append({"method": method, "path": path, "headers": headers,
                              "body": body, "json": payload})

        if raw_path == "/health/ready" and method == "GET":
            return 200, self.health
        if raw_path == "/api/v1/me" and method == "GET":
            if not headers.get("Authorization"):
                return 401, self._error("unauthenticated")
            return 200, self.me or {"user": {"id": "u1", "email": "owner@acme.test"},
                                    "orgs": [{"org_id": "o1", "slug": "acme", "name": "Acme",
                                              "role": "owner"}],
                                    "scopes": ["search", "use", "events"]}
        if raw_path == "/api/v1/auth/device" and method == "POST":
            return 200, self.device_start or {
                "device_code": "dev-123", "user_code": "WXYZ-1234",
                "verification_uri": "/organization?tab=integrations&device=WXYZ-1234",
                "expires_in": 600, "interval": 0}
        if raw_path == "/api/v1/auth/device/token" and method == "POST":
            if not self.device_token_script:
                return 400, self._error("authorization_pending")
            return self.device_token_script.pop(0)

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos", raw_path)
        if m and method == "POST":
            # API-CONTRACT §4.2: 201 on registration, 200 when it already existed,
            # `created` distinguishing them. Never 409 -- the fake used to answer
            # 409 and so encoded the wrong contract for the whole suite (L6).
            repo = (payload or {}).get("repo_id")
            existed = repo in self.repos
            self.repos.add(repo)
            return (200 if existed else 201), {"repo_id": repo, "name": repo,
                                               "git_host_url": "", "created": not existed}

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports", raw_path)
        if m and method == "POST":
            return self._create_import(payload)

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports/([^/]+)/blobs/([0-9a-f]{64})", raw_path)
        if m and method == "PUT":
            return self._put_blob(m.group(3), m.group(4), body)

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports/([^/]+)/finalize", raw_path)
        if m and method == "POST":
            return self._finalize(m.group(3))

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports/([^/]+)/plan", raw_path)
        if m and method == "GET":
            return 200, dict(self.plan, import_id=m.group(3))

        m = re.fullmatch(
            r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports/([^/]+)/proposals:generate", raw_path)
        if m and method == "POST":
            if self.generate_error is not None:
                return self.generate_error
            return 200, {"job_ids": list(self.generate_job_ids),
                         "profile": (payload or {}).get("profile"),
                         "plan": dict(self.plan, import_id=m.group(3))}

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/imports/([^/]+)", raw_path)
        if m and method == "GET":
            return self._import_view(m.group(3))

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/proposals", raw_path)
        if m and method == "GET":
            return 200, {"items": self.proposals}

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/proposals/([^/]+)", raw_path)
        if m and method == "GET":
            found = next((p for p in self.proposals if p.get("proposal_id") == m.group(3)), None)
            return (200, found) if found else (404, self._error("not_found"))

        m = re.fullmatch(r"/api/v1/orgs/([^/]+)/repos/([^/]+)/exports/([^/]+)", raw_path)
        if m and method == "GET":
            found = self.exports.get(m.group(3))
            return (200, found) if found else (404, self._error("not_found"))

        return 404, self._error("not_found", raw_path)

    # -------------------------------------------------------------------------- endpoints
    def _create_import(self, payload):
        payload = payload or {}
        key = payload.get("idempotency_key")
        manifest = payload.get("manifest") or {}
        if not key or not manifest:
            return 400, self._error("invalid", "idempotency_key and manifest are required")
        import_id = self.import_by_key.get(key)
        if import_id is None:
            import_id = f"imp_{self.next_import:04d}"
            self.next_import += 1
            self.import_by_key[key] = import_id
            self.imports[import_id] = {"import_id": import_id, "state": "created",
                                       "manifest": manifest, "manifest_digest": key,
                                       "commit": manifest.get("commit"),
                                       "complete": manifest.get("complete"),
                                       "wanted": {f["sha256"] for f in manifest.get("files", [])}}
        record = self.imports[import_id]
        missing = sorted(s for s in record["wanted"] if s not in self.blobs)
        # `new_blobs` for this import is fixed the first time it is created: what the server did
        # not already hold. A resumed import keeps that number, so a re-run does not look like a
        # fresh upload just because the first attempt succeeded partially.
        record.setdefault("new_at_create", len(missing))
        return 201, {"import_id": import_id, "state": record["state"], "missing_blobs": missing,
                     "limits": {"max_blob_bytes": 8388608, "max_total_bytes": 104857600,
                                "max_files": 100000}}

    def _put_blob(self, import_id, sha, body):
        record = self.imports.get(import_id)
        if record is None:
            return 404, self._error("not_found", "unknown import")
        if sha not in record["wanted"]:
            return 400, self._error("blob_not_in_manifest", "hash is not listed in the manifest")
        remaining = self.fail_put_shas.get(sha, 0)
        if remaining:
            self.fail_put_shas[sha] = remaining - 1
            return 500, self._error("upload_failed", "scripted failure")
        import hashlib
        if hashlib.sha256(body).hexdigest() != sha:
            return 400, self._error("blob_digest_mismatch")
        already = sha in self.blobs
        self.blobs[sha] = body
        self.blob_puts.append(sha)
        return (200 if already else 201), {"sha256": sha, "stored": not already}

    def _finalize(self, import_id):
        record = self.imports.get(import_id)
        if record is None:
            return 404, self._error("not_found", "unknown import")
        missing = sorted(s for s in record["wanted"] if s not in self.blobs)
        if missing:
            return 409, self._error("blobs_missing", json.dumps({"missing": missing}))
        record["state"] = "queued"
        self.finalized.append(import_id)
        new = record.get("new_at_create", len(record["wanted"]))
        return 200, {"import_id": import_id, "state": "queued",
                     "new_blobs": new,
                     "reused_blobs": max(0, len(record["wanted"]) - new)}

    def _import_view(self, import_id):
        record = self.imports.get(import_id)
        if record is None:
            return 404, self._error("not_found", "unknown import")
        manifest = record["manifest"]
        view = {"import_id": import_id, "state": "ready" if record["state"] == "queued" else record["state"],
                "manifest_digest": record["manifest_digest"], "commit": record["commit"],
                "complete": record["complete"],
                "files": [{"path": f["path"], "state": "accepted"} for f in manifest.get("files", [])],
                "jobs": [{"kind": "import.parse", "state": "done"},
                         {"kind": "publish.build", "state": "done"}] + self.extract_jobs,
                "publication": {"state": "published", "snapshot_id": "snap_1"}}
        view.update(self.import_view_extra)
        return 200, view

    @staticmethod
    def _error(code, message=""):
        return {"error": {"code": code, "message": message}, "code": code,
                "message": message, "request_id": "req-test"}


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _dispatch(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        status, payload = self.server.api.handle(method, self.path, dict(self.headers), body)
        data = b"" if payload is None else json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Request-Id", "req-test")
            self.end_headers()
            if data:
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def log_message(self, *a):
        pass


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@contextmanager
def running_api(api=None):
    """Yields (base_url, ManagementAPI)."""
    api = api or ManagementAPI()
    server = _Server(("127.0.0.1", _free_port()), _Handler)
    server.api = api
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", api
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
