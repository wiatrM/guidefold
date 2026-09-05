"""Real Router + HTTP conformance. Fixtures prove behavior, not retrieval quality."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from _router_helpers import make_card
from test_service_spike import load_module, probe, running_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.serve_spike import context, repository
from tools.serve_spike.server import Engine, make_server, load_cli_snapshot

TOKEN = "contract-fixture-token-123456789"


@pytest.fixture(scope="module")
def cli_snapshot():
    return load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")


def make_engine(cli_snapshot, optimized=False):
    cli, sha = cli_snapshot
    engine = Engine(disable_model=True, optimized=optimized)
    nodes = {"_root": {"paths": ["**"], "owner": "platform"},
             "alpha": {"paths": ["services/alpha/**"], "owner": "team-alpha"},
             "beta": {"paths": ["services/beta/**"], "owner": "team-beta"}}
    cards = {f"urn:skill:fixture:{node}:retry": make_card(
        f"urn:skill:fixture:{node}:retry", node,
        description="Implement Kafka consumer retry backoff idempotency",
        body=f"# {node} retry\nUse the {node} idempotency store.") for node in ("alpha", "beta")}
    engine.cli, engine.policy_revision = cli, sha
    engine.cards, engine.nodes = cards, nodes
    engine.index = cli.Index.from_cards(cards, nodes, weights={"w_dense": 0})
    engine.router = cli.Router(engine.index)
    engine.repository = {"repo_id": "fixture-repo", "revision": "a" * 40}
    engine.snapshot = "fixture-content-v1"
    engine.id_to_urn = engine.urn_to_id = {u: u for u in cards}
    engine.revisions = {u: hashlib.sha256(c["_body"].encode()).hexdigest() for u, c in cards.items()}
    if optimized:
        from tools.serve_spike.sparse_cache import install_bm25_cache
        install_bm25_cache(engine.router)
    engine.ready = True
    return engine


def payload(path="services/alpha"):
    return {"schema_version": "1.1", "request_id": "req-1", "session_id": "session-1", "task_id": "task-1",
            "query": "Implement Kafka consumer retry backoff idempotency", "query_source": "agent",
            "workspace": {"repo_id": "fixture-repo", "revision": "a" * 40, "cwd": path},
            "harness": {"name": "fixture-harness", "adapter_version": "1.0"}, "deadline_ms": 1000}


def search(engine, data):
    return engine.search(data, time.monotonic() + 10)


def ids(result):
    return [c["skill_id"] for c in result["cards"]]


@pytest.mark.parametrize("optimized", [False, True])
def test_same_query_resolves_real_sibling_scopes(cli_snapshot, optimized):
    engine = make_engine(cli_snapshot, optimized)
    alpha, beta = search(engine, payload()), search(engine, payload("services/beta"))
    assert ids(alpha) == ["urn:skill:fixture:alpha:retry"]
    assert ids(beta) == ["urn:skill:fixture:beta:retry"]
    assert alpha["context"]["scope_owners"] == {"alpha": "team-alpha"}
    assert beta["context"]["resolved_scopes"] == ["beta"]
    assert alpha["context"]["scope_is_authorization"] is False


def test_explicit_targets_override_cwd_and_inferred_paths(cli_snapshot):
    engine = make_engine(cli_snapshot)
    data = payload()
    data["workspace"]["target_paths"] = [
        {"path": "services/beta/consumer.py", "source": "user_explicit"},
        {"path": "services/alpha/consumer.py", "source": "inferred"}]
    assert ids(search(engine, data)) == ["urn:skill:fixture:beta:retry"]


def test_multiple_scopes_merge_deterministically_without_sibling_leak(cli_snapshot):
    engine = make_engine(cli_snapshot)
    data = payload()
    paths = [{"path": f"services/{node}/consumer.py", "source": "edited"} for node in ("alpha", "beta")]
    data["workspace"]["target_paths"] = paths
    first = search(engine, data)
    data["workspace"]["target_paths"] = list(reversed(paths))
    second = search(engine, data)
    assert first["cards"] == second["cards"]
    assert set(ids(first)) == set(engine.cards)
    assert first["context"]["fusion"] == "max_score_then_urn"
    assert first["context"]["resolved_scopes"] == ["alpha", "beta"]


@pytest.mark.parametrize("path", ["/home/user/repo", "C:/repo", "services/../beta", "../repo", "services//alpha", "services\\alpha", "services/./alpha"])
def test_absolute_and_traversal_paths_are_rejected(path):
    with pytest.raises(context.ContextError, match="invalid_relative_path"):
        context.validate(payload(path), "/v1/search")


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p.update(team="trusted-admin"), "unknown_request_field"),
    (lambda p: p.update(schema_version="2.0"), "unsupported_schema_version"),
    (lambda p: p.pop("schema_version"), "unsupported_schema_version"),
    (lambda p: p["workspace"].update(team="team-alpha"), "invalid_context_fields"),
    (lambda p: p.update(node="_root"), "node_and_workspace_are_exclusive"),
    (lambda p: p.update(budget={"max_cards": True}), "invalid_context_budget"),
    (lambda p: p.update(budget={"max_cards": 5}), "invalid_context_budget"),
    (lambda p: p.update(harness={"name": "x", "secret": "hidden"}), "invalid_context_fields"),
    (lambda p: p.update(request_id="raw prompt\ntext"), "invalid_context_value"),
])
def test_malformed_context_fails_before_routing(mutation, code):
    data = payload()
    mutation(data)
    with pytest.raises(context.ContextError, match=code):
        context.validate(data, "/v1/search")


def test_unknown_legacy_fields_are_not_silently_ignored():
    with pytest.raises(context.ContextError, match="unknown_request_field"):
        context.validate({"query": "retry", "cwd": "services/alpha"}, "/v1/search")


def test_wrong_repo_revision_missing_map_and_ambiguity_fail_closed(cli_snapshot):
    engine = make_engine(cli_snapshot)
    for field, value, code in (("repo_id", "other", "repository_mismatch"),
                               ("revision", "b" * 40, "repository_revision_mismatch"),
                               ("cwd", "unknown/component", "unmapped_workspace_path")):
        data = payload()
        data["workspace"][field] = value
        with pytest.raises(context.ContextError, match=code):
            search(engine, data)
    engine.nodes["beta"]["paths"] = engine.nodes["alpha"]["paths"]
    with pytest.raises(context.ContextError, match="ambiguous_workspace_path"):
        search(engine, payload())
    engine.repository = None
    with pytest.raises(context.ContextError, match="repository_context_unavailable"):
        search(engine, payload())


def test_explicit_root_and_missing_revision_are_reported(cli_snapshot):
    engine = make_engine(cli_snapshot)
    data = payload(".")
    del data["workspace"]["revision"]
    result = search(engine, data)
    assert result["context"]["resolved_scopes"] == ["_root"]
    assert "repository_revision_not_supplied" in result["context"]["warnings"]


def test_unadmitted_signals_are_explicit_and_do_not_rewrite_query(cli_snapshot):
    engine = make_engine(cli_snapshot)
    data = payload()
    baseline = search(engine, data)
    data.update(intent={"action": "debug", "goal": "different task"},
                stack={"languages": ["rust"], "source": "inferred"},
                constraints=["offline"], capabilities=["terminal"])
    result = search(engine, data)
    assert result["cards"] == baseline["cards"]
    assert {x["field"] for x in result["context"]["unused_fields"]} == {"intent", "stack", "constraints", "capabilities"}


def test_loaded_revision_dedup_requires_explicit_hydration_and_exact_revision(cli_snapshot):
    engine = make_engine(cli_snapshot)
    card = search(engine, payload())["cards"][0]
    for state, revision, omitted in (("hydrated", card["revision"], True),
                                     ("exposed", card["revision"], False), ("hydrated", "old", False)):
        data = payload()
        data["loaded_skills"] = [{"skill_id": card["skill_id"], "revision": revision, "state": state}]
        result = search(engine, data)
        assert (result["cards"] == []) is omitted
        assert result["context"]["loaded_cards_omitted"] == int(omitted)
        assert result["abstained"] is False  # Already loaded is not a retrieval abstention.


def test_budget_rejects_whole_pack_and_preserves_ranked_diagnostics(cli_snapshot):
    engine = make_engine(cli_snapshot)
    data = payload()
    complete = search(engine, data)
    size = len(complete["card_context"].encode())
    data["budget"] = {"max_bytes": size}
    assert ids(search(engine, data)) == ids(complete)
    data["budget"]["max_bytes"] = size - 1
    result = search(engine, data)
    assert result["cards"] == [] and result["card_context"] == ""
    assert result["ranked"] == complete["ranked"]
    assert result["context"]["delivery_status"] == "cannot_fit"
    data["budget"] = {"max_cards": 0}
    assert search(engine, data)["cards"] == []
    data["budget"] = {"remaining_skill_tokens": 0}
    assert "verify_final_harness_token_count" in search(engine, data)["context"]["warnings"]


def test_context_http_search_use_trace_and_redacted_telemetry(cli_snapshot, tmp_path):
    engine = make_engine(cli_snapshot, optimized=True)
    log = tmp_path / "events.jsonl"
    server = make_server(engine, TOKEN, port=0, log_file=log)
    data = payload()
    with running_server(server) as url:
        reply = probe.request_json(url, TOKEN, "/v1/search", data)
        assert reply["http_status"] == 200
        result = reply["response"]
        assert result["request_id"] == data["request_id"]
        assert result["task_id"] == data["task_id"]
        card = result["cards"][0]
        use = {"schema_version": "1.1", "request_id": "use-1", "session_id": "session-1", "task_id": "task-1",
               "skill_id": card["skill_id"], "revision": card["revision"],
               "search_id": result["search_id"], "workspace": data["workspace"]}
        hydrated = probe.request_json(url, TOKEN, "/v1/use", use)
        assert hydrated["http_status"] == 200
        body = hydrated["response"]
        assert body["checksum"] == hashlib.sha256(body["body"].encode()).hexdigest()
        assert body["execution_observed"] is False
        assert body["search_id_verified"] is False
        use["workspace"] = {**data["workspace"], "cwd": "services/beta"}
        assert probe.request_json(url, TOKEN, "/v1/use", use)["http_status"] == 403
        use["workspace"] = data["workspace"]
        use["budget"] = {"max_bytes": 1}
        assert probe.request_json(url, TOKEN, "/v1/use", use)["http_status"] == 413
        bad = {**data, "team": "admin"}
        assert probe.request_json(url, TOKEN, "/v1/search", bad)["http_status"] == 400
    text = log.read_text()
    for excluded in (data["query"], data["workspace"]["cwd"], TOKEN, body["body"]):
        assert excluded not in text
    records = [json.loads(line) for line in text.splitlines()]
    assert records[0]["context"]["resolved_scopes"] == ["alpha"]
    assert records[0]["returned_skill_revisions"] == [{"skill_id": card["skill_id"], "revision": card["revision"]}]
    assert records[0]["request_id"] == "req-1"
    assert records[0]["attempt_id"] != records[0]["request_id"]


def test_native_and_python_rankers_preserve_context_scopes(cli_snapshot, tmp_path):
    np = pytest.importorskip("numpy")
    from tools.eval import dense_ref
    from tools.serve_spike.native_rank import prepare_native_rank, install_native_dense_rank
    import shutil
    if not sys.platform.startswith("linux") or not shutil.which("g++"):
        pytest.skip("C++ conformance requires Linux and g++")
    cli, _ = cli_snapshot
    engine = make_engine(cli_snapshot)
    order = sorted(engine.cards)
    matrix = np.array([[127, 1, 0], [126, 2, 1]], dtype=np.int8)
    engine.index, engine.router = dense_ref.build_dense_index_and_router(
        cli, engine.cards, engine.nodes, {u: i for i, u in enumerate(order)}, matrix, {})
    engine.backend = "hybrid_full"
    engine._encode_query_vector = lambda *_: np.array([127, 1, 0], dtype=np.int64)
    baseline = [search(engine, payload(path)) for path in ("services/alpha", "services/beta", ".")]
    meta = install_native_dense_rank(engine.router, prepare_native_rank(tmp_path))
    for path, expected in zip(("services/alpha", "services/beta", "."), baseline):
        actual = search(engine, payload(path))
        assert actual["cards"] == expected["cards"]
        assert actual["ranked"] == expected["ranked"]
    assert meta["native_calls"] > 0


def test_repository_builder_pins_committed_content_and_checks_integrity(cli_snapshot, tmp_path):
    cli, sha = cli_snapshot
    root = tmp_path / "repo"
    skill = root / "services/alpha/.agents/skills/retry/SKILL.md"
    skill.parent.mkdir(parents=True)
    (root / "guidefold.yaml").write_text("publisher: fixture\nnodes:\n  _root:\n    paths: ['**']\n  alpha:\n    paths: ['services/alpha/**']\n")
    skill.write_text("---\nname: retry\ndescription: Retry Kafka requests\nmetadata:\n  status: active\n---\nCommitted instructions.\n")
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    git("init", "-q")
    git("add", "guidefold.yaml", "services/alpha/.agents/skills/retry/SKILL.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
    bundle = repository.build(root, "fixture-repo", "HEAD", cli, sha)
    skill.write_text("DIRTY CONTENT MUST NOT BE SERVED")
    assert repository.build(root, "fixture-repo", "HEAD", cli, sha) == bundle
    file = tmp_path / "snapshot.json"
    file.write_bytes(repository.canonical(bundle))
    engine = Engine(disable_model=True, optimized=True, repository_snapshot=file)
    engine.initialize()
    assert engine.ready and engine.model_load_calls == 0
    result = search(engine, {**payload(), "workspace": {"repo_id": "fixture-repo", "cwd": "services/alpha"}})
    assert result["cards"]
    card = result["cards"][0]
    assert "Committed instructions" in engine.use({"skill_id": card["skill_id"], "revision": card["revision"]}, time.monotonic()+1)["body"]
    bundle["snapshot"]["cards"][card["skill_id"]]["_body"] = "tampered"
    file.write_bytes(repository.canonical(bundle))
    with pytest.raises(ValueError, match="integrity"):
        repository.load(file, cli, sha)
