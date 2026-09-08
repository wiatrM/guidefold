"""tests/test_ascend.py -- `guidefold ascend` (ADR-0035): bottom-up knowledge ascent gated on
grounding, digest-only, idempotency and `validate`. The model is a local OpenAI-compatible stub
so every test is offline and deterministic; the stub records what it was asked and answers from a
queue the test controls.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

TURNSTILE = "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth/SKILL.md"
IDENTITY_DIR = "platforms/atlas/identity/.agents/skills"
ATLAS_DIR = "platforms/atlas/.agents/skills"
SRC_TURNSTILE = "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
SRC_RBAC = "urn:skill:meridian:atlas.identity:rbac-policies"


class _Stub:
    """Serves `queue` responses in order; a request past the queue answers no_change for both kinds."""

    def __init__(self, queue):
        self.queue = list(queue)
        self.requests = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8"))
                stub.requests.append({"auth": self.headers.get("Authorization"), "body": payload})
                content = stub.queue.pop(0) if stub.queue else _no_change()
                out = json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def close(self):
        self.server.shutdown()


def _no_change():
    return {"results": [{"kind": "map", "action": "no_change", "reason": "nothing generic"},
                        {"kind": "convention", "action": "no_change", "reason": "nothing shared"}]}


def _map_identity(sources=(SRC_TURNSTILE, SRC_RBAC), body=None, name="atlas-identity-map"):
    body = body or (
        "Identity is the atlas authorization platform. Turnstile is the ext_authz service that "
        "authorizes every atlas API request; the RBAC policy bundle it evaluates is authored under "
        "identity's policies directory.\n\n"
        "Owners: turnstile-team runs the service, identity-platform owns the policy model."
    )
    return {"results": [
        {"kind": "map", "action": "create", "reason": "a new component appeared below",
         "skill": {"name": name,
                   "description": "What lives under atlas identity and who owns it",
                   "digest": "Turnstile authorizes atlas requests; RBAC policies define roles.",
                   "triggers": "identity platform overview, what is turnstile, who owns rbac",
                   "body": body,
                   "claims": [{"text": "Turnstile is the ext_authz service", "sources": [sources[0]]},
                              {"text": "RBAC bundle authored under identity", "sources": [sources[1]]}]}},
        {"kind": "convention", "action": "no_change", "reason": "only one service so far"},
    ]}


@pytest.fixture
def stub():
    holder = {}

    def make(queue):
        holder["s"] = _Stub(queue)
        return holder["s"]

    yield make
    if "s" in holder:
        holder["s"].close()


def _env(stub_url, key="test-key"):
    env = dict(os.environ)
    env["GUIDEFOLD_ASCEND_API_KEY"] = key
    env["GUIDEFOLD_ASCEND_BASE_URL"] = stub_url
    env["GUIDEFOLD_ASCEND_MODEL"] = "stub/model"
    return env


def _ascend(run_cli, root, env, *extra):
    return run_cli(["ascend", "--changed", TURNSTILE, "--json", "-", *extra], cwd=root, env=env)


def test_ascend_creates_the_parent_map_skill_from_a_leaf_change(run_cli, fixture_copy, stub):
    s = stub([_map_identity()])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    written = Path(fixture_copy) / IDENTITY_DIR / "atlas-identity-map" / "SKILL.md"
    assert written.exists(), out
    text = written.read_text(encoding="utf-8")
    assert text.startswith("---\nname: atlas-identity-map\n")
    assert 'description: "[atlas/identity] ' in text
    assert "  scope: atlas.identity\n" in text and "  owner: identity-platform\n" in text
    assert "  knowledge_layer: abstract\n" in text and "  generated_by: guidefold-ascend\n" in text
    assert SRC_TURNSTILE in text and SRC_RBAC in text          # derived_from cites both sources
    assert text.count("\n") <= 80
    # the model saw the field: target node, its owner, the sibling child scopes and their cards
    prompt = s.requests[0]["body"]["messages"][1]["content"]
    assert "# Target scope: atlas.identity" in prompt and "owner: identity-platform" in prompt
    assert "atlas.identity.turnstile" in prompt and SRC_RBAC in prompt
    assert s.requests[0]["auth"] == "Bearer test-key"
    # `validate` accepts the tree with the new file
    v = run_cli(["validate"], cwd=fixture_copy)
    assert v.returncode == 0, v.stdout + v.stderr


def test_ascend_climbs_until_a_level_has_nothing_generic(run_cli, fixture_copy, stub):
    # identity gets a map; atlas answers no_change; the climb stops there (no _root call).
    s = stub([_map_identity(), _no_change()])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    nodes = [lv["node"] for lv in out["levels"] if not lv.get("skipped")]
    assert nodes[:2] == ["atlas.identity", "atlas"]
    assert "_root" not in nodes
    assert len(s.requests) == 2
    # the atlas-level prompt carried the freshly written identity skill as a changed body
    assert "urn:skill:meridian:atlas.identity:atlas-identity-map" in s.requests[1]["body"]["messages"][1]["content"]


def test_ascend_rejects_a_claim_that_cites_a_skill_outside_the_context(run_cli, fixture_copy, stub):
    bad = _map_identity(sources=(SRC_TURNSTILE, "urn:skill:meridian:atlas.identity:made-up"))
    s = stub([bad])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["written"] == []
    item = next(x for x in out["levels"][0]["results"] if x["kind"] == "map")
    assert any("not in context" in reason for reason in item["rejected"])
    assert not (Path(fixture_copy) / IDENTITY_DIR / "atlas-identity-map").exists()


def test_ascend_rejects_a_procedure_dressed_as_a_digest(run_cli, fixture_copy, stub):
    body = "Identity overview.\n\n1. Run the migration.\n2. Restart turnstile.\n3. Verify with kubectl.\n"
    s = stub([_map_identity(body=body)])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    out = json.loads(r.stdout)
    item = next(x for x in out["levels"][0]["results"] if x["kind"] == "map")
    assert any("numbered steps" in reason for reason in item["rejected"])
    assert out["written"] == []


def test_ascend_rejects_three_lines_copied_from_a_child(run_cli, fixture_copy, stub):
    child = (Path(fixture_copy) / TURNSTILE).read_text(encoding="utf-8")
    lines = [l for l in child.split("\n---\n", 1)[1].splitlines() if l.strip()]
    body = "Identity overview.\n\n" + "\n".join(lines[3:6]) + "\n"
    s = stub([_map_identity(body=body)])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    out = json.loads(r.stdout)
    item = next(x for x in out["levels"][0]["results"] if x["kind"] == "map")
    assert any("copied verbatim" in reason for reason in item["rejected"])


def test_ascend_is_idempotent_without_a_second_model_call(run_cli, fixture_copy, stub):
    s = stub([_map_identity(), _no_change()])
    assert _ascend(run_cli, fixture_copy, _env(s.base_url)).returncode == 0
    first = (Path(fixture_copy) / IDENTITY_DIR / "atlas-identity-map" / "SKILL.md").read_bytes()
    calls_before = len(s.requests)
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["calls"] == 0 and out["written"] == []
    assert out["levels"][0].get("skipped", "").startswith("fingerprint unchanged")
    assert len(s.requests) == calls_before
    assert (Path(fixture_copy) / IDENTITY_DIR / "atlas-identity-map" / "SKILL.md").read_bytes() == first


def test_ascend_edits_the_existing_abstract_skill_instead_of_adding_a_second(run_cli, fixture_copy, stub):
    s = stub([_map_identity(), _no_change()])
    assert _ascend(run_cli, fixture_copy, _env(s.base_url)).returncode == 0
    # a real change below: the leaf skill's body grows, so the fingerprint moves
    leaf = Path(fixture_copy) / TURNSTILE
    leaf.write_text(leaf.read_text(encoding="utf-8") + "\nTurnstile now also emits audit events.\n", encoding="utf-8")
    s.queue[:] = [_map_identity(name="totally-different-name",
                                body="Identity is the atlas authorization platform; turnstile also emits audit events now."),
                  _no_change()]
    r = _ascend(run_cli, fixture_copy, _env(s.base_url))
    out = json.loads(r.stdout)
    item = next(x for x in out["levels"][0]["results"] if x["kind"] == "map")
    assert item["action"] == "edit" and item["path"].endswith("atlas-identity-map/SKILL.md")
    assert not (Path(fixture_copy) / IDENTITY_DIR / "totally-different-name").exists()
    assert len([p for p in (Path(fixture_copy) / IDENTITY_DIR).iterdir() if p.is_dir()
                and (p / "SKILL.md").exists() and "generated_by: guidefold-ascend" in (p / "SKILL.md").read_text()]) == 1


def test_ascend_dry_run_calls_no_model_and_writes_nothing(run_cli, fixture_copy, stub):
    s = stub([_map_identity()])
    r = _ascend(run_cli, fixture_copy, _env(s.base_url, key=""), "--dry-run")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["dry_run"] is True and out["calls"] == 0 and out["written"] == []
    assert [lv["node"] for lv in out["levels"]] == ["atlas.identity", "atlas", "_root"]
    assert not s.requests
    assert not (Path(fixture_copy) / IDENTITY_DIR / "atlas-identity-map").exists()
    assert not (Path(fixture_copy) / ATLAS_DIR / "atlas-map").exists()


def test_ascend_without_a_key_refuses_clearly(run_cli, fixture_copy):
    env = dict(os.environ)
    env.pop("GUIDEFOLD_ASCEND_API_KEY", None)
    r = run_cli(["ascend", "--changed", TURNSTILE], cwd=fixture_copy, env=env)
    assert r.returncode != 0
    assert "GUIDEFOLD_ASCEND_API_KEY" in r.stderr and "--dry-run" in r.stderr


def test_ascend_writes_a_pr_summary_with_the_marker(run_cli, fixture_copy, stub, tmp_path):
    s = stub([_map_identity(), _no_change()])
    md = tmp_path / "ascend.md"
    r = _ascend(run_cli, fixture_copy, _env(s.base_url), "--summary-md", str(md))
    assert r.returncode == 0, r.stderr
    text = md.read_text(encoding="utf-8")
    assert text.startswith("<!-- guidefold:ascend -->")
    assert "atlas-identity-map/SKILL.md" in text and "atlas.identity" in text
