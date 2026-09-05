"""Tests for tools/eval/composer_model.py — the model composer (ADR-0024 §4, DENSE-PROGRAM.md
v2.4 family C). Never invokes the real `claude` CLI: every test that reaches `compose()`/
`call_model()` monkeypatches `subprocess.run` with a canned CompletedProcess, so this suite runs
offline, deterministically, and at zero cost -- consistent with "the model composer is evaluated
only in tools/eval/" and never touched by CI's product-path tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "eval"))

import composer_model as cm  # tools/eval/composer_model.py


def _candidates():
    return [
        {"urn": "u:invoice", "name": "invoice", "description": "handles invoices"},
        {"urn": "u:payment", "name": "payment", "description": "handles payments"},
        {"urn": "u:reminder", "name": "reminder", "description": "sends reminders"},
    ]


def _fake_proc(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr=stderr)


def _wrapper(result_obj, cost=0.0015):
    return json.dumps({"result": json.dumps(result_obj), "cost_usd": cost})


# --------------------------------------------------------------------------- build_prompt
def test_build_prompt_includes_query_and_all_candidate_urns():
    prompt = cm.build_prompt("pay an invoice and remind the customer", _candidates())
    assert "pay an invoice and remind the customer" in prompt
    for c in _candidates():
        assert c["urn"] in prompt


def test_build_prompt_truncates_a_runaway_description():
    long_desc = "x" * 5000
    prompt = cm.build_prompt("q", [{"urn": "u:a", "name": "a", "description": long_desc}])
    assert len(prompt) < 5000


# --------------------------------------------------------------------------- call_model
def test_call_model_ok_path(monkeypatch):
    def fake_run(*a, **kw):
        return _fake_proc(_wrapper({"selected": ["u:invoice"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = cm.call_model("some prompt")
    assert out["ok"] is True
    assert out["error"] is None
    assert out["cost_usd"] == 0.0015
    parsed = json.loads(out["raw"])
    assert parsed["selected"] == ["u:invoice"]


def test_call_model_nonzero_exit_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_proc("", returncode=1, stderr="boom"))
    out = cm.call_model("p")
    assert out["ok"] is False
    assert "exit 1" in out["error"]


def test_call_model_timeout_is_reported_not_raised(monkeypatch):
    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=30)
    monkeypatch.setattr(subprocess, "run", raise_timeout)
    out = cm.call_model("p", timeout=30)
    assert out["ok"] is False
    assert "timeout" in out["error"]


def test_call_model_missing_binary_is_reported_not_raised(monkeypatch):
    def raise_missing(*a, **kw):
        raise FileNotFoundError("no such file: claude")
    monkeypatch.setattr(subprocess, "run", raise_missing)
    out = cm.call_model("p")
    assert out["ok"] is False
    assert "claude CLI not found" in out["error"]


def test_call_model_malformed_wrapper_json_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_proc("not json"))
    out = cm.call_model("p")
    assert out["ok"] is False
    assert "wrapper not JSON" in out["error"]


def test_call_model_passes_minimal_flags_and_no_tools(monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return _fake_proc(_wrapper({"selected": [], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    cm.call_model("p", model="haiku")
    cmd = captured["cmd"]
    assert "--model" in cmd and "haiku" in cmd
    assert "--output-format" in cmd and "json" in cmd
    assert "--tools" in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--system-prompt" in cmd
    assert "--safe-mode" in cmd
    assert "--no-session-persistence" in cmd


# --------------------------------------------------------------------------- parse_selection
def test_parse_selection_happy_path():
    urns = {"u:invoice", "u:payment"}
    out = cm.parse_selection(json.dumps({"selected": ["u:invoice", "u:payment"], "cannot_fit": False}), urns)
    assert out["selected"] == ["u:invoice", "u:payment"]
    assert out["cannot_fit"] is False
    assert out["error"] is None


def test_parse_selection_strips_markdown_fences():
    urns = {"u:invoice"}
    raw = '```json\n{"selected": ["u:invoice"], "cannot_fit": false}\n```'
    out = cm.parse_selection(raw, urns)
    assert out["selected"] == ["u:invoice"]


def test_parse_selection_drops_hallucinated_urn_and_flags_cannot_fit():
    urns = {"u:invoice"}
    out = cm.parse_selection(json.dumps({"selected": ["u:invoice", "u:made-up"], "cannot_fit": False}), urns)
    assert out["selected"] == ["u:invoice"]
    assert out["cannot_fit"] is True
    assert out["error"] is None


def test_parse_selection_truncates_over_k_and_flags_cannot_fit():
    urns = {"u:a", "u:b", "u:c", "u:d", "u:e"}
    out = cm.parse_selection(
        json.dumps({"selected": ["u:a", "u:b", "u:c", "u:d", "u:e"], "cannot_fit": False}), urns, k=4,
    )
    assert out["selected"] == ["u:a", "u:b", "u:c", "u:d"]
    assert out["cannot_fit"] is True


def test_parse_selection_malformed_json_degrades_to_empty_cannot_fit():
    out = cm.parse_selection("not json at all", {"u:a"})
    assert out["selected"] == []
    assert out["cannot_fit"] is True
    assert out["error"] is not None


def test_parse_selection_non_list_selected_degrades_to_empty_cannot_fit():
    out = cm.parse_selection(json.dumps({"selected": "u:a", "cannot_fit": False}), {"u:a"})
    assert out["selected"] == []
    assert out["cannot_fit"] is True


def test_parse_selection_preserves_model_reported_cannot_fit_true():
    urns = {"u:a"}
    out = cm.parse_selection(json.dumps({"selected": ["u:a"], "cannot_fit": True}), urns)
    assert out["cannot_fit"] is True


# --------------------------------------------------------------------------- ReplayCache
def test_replay_cache_round_trips_through_disk(tmp_path):
    path = tmp_path / "cache.jsonl"
    cache = cm.ReplayCache(path)
    assert len(cache) == 0
    key = cm._cache_key("q1", _candidates())
    cache.put(key, {"key": key, "query_id": "q1", "model": "haiku",
                     "result": {"selected": ["u:invoice"], "cannot_fit": False, "error": None},
                     "cost_usd": 0.001, "ts": 0.0})
    assert len(cache) == 1
    reloaded = cm.ReplayCache(path)
    assert len(reloaded) == 1
    assert reloaded.get(key)["result"]["selected"] == ["u:invoice"]


def test_replay_cache_key_changes_when_candidate_set_changes():
    key1 = cm._cache_key("q1", _candidates())
    changed = _candidates()
    changed[0]["description"] = "a totally different description"
    key2 = cm._cache_key("q1", changed)
    assert key1 != key2


def test_replay_cache_key_stable_regardless_of_dict_key_order():
    c1 = [{"urn": "u:a", "name": "a", "description": "d"}]
    c2 = [{"description": "d", "urn": "u:a", "name": "a"}]
    assert cm._cache_key("q1", c1) == cm._cache_key("q1", c2)


def test_replay_cache_missing_file_is_empty(tmp_path):
    cache = cm.ReplayCache(tmp_path / "does-not-exist.jsonl")
    assert len(cache) == 0
    assert cache.get("anything") is None


# --------------------------------------------------------------------------- compose (integration)
def test_compose_cache_miss_calls_model_and_populates_cache(monkeypatch, tmp_path):
    def fake_run(*a, **kw):
        return _fake_proc(_wrapper({"selected": ["u:invoice", "u:payment"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    cache = cm.ReplayCache(tmp_path / "cache.jsonl")
    out = cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    assert out["selected"] == ["u:invoice", "u:payment"]
    assert out["cached"] is False
    assert len(cache) == 1


def test_compose_cache_hit_never_calls_model(monkeypatch, tmp_path):
    calls = []
    def fake_run(*a, **kw):
        calls.append(1)
        return _fake_proc(_wrapper({"selected": ["u:invoice"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    cache = cm.ReplayCache(tmp_path / "cache.jsonl")
    out1 = cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    out2 = cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    assert len(calls) == 1
    assert out1["selected"] == out2["selected"]
    assert out2["cached"] is True
    assert out2["latency_s"] == 0.0
    # regression: a cache hit must carry the same shape as a fresh call, including
    # "cost_usd" -- a prior bug omitted this key on the cache-hit path entirely (KeyError
    # in any caller that reads result["cost_usd"] unconditionally, as the dev harness does).
    assert "cost_usd" in out2
    assert out2["cost_usd"] == out1["cost_usd"] == 0.0015


def test_compose_without_cache_never_persists_and_never_reuses(monkeypatch):
    calls = []
    def fake_run(*a, **kw):
        calls.append(1)
        return _fake_proc(_wrapper({"selected": ["u:invoice"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    cm.compose("q1", "pay an invoice", _candidates(), cache=None)
    cm.compose("q1", "pay an invoice", _candidates(), cache=None)
    assert len(calls) == 2


def test_compose_model_call_failure_yields_empty_cannot_fit_true(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_proc("", returncode=1, stderr="boom"))
    out = cm.compose("q1", "pay an invoice", _candidates(), cache=None)
    assert out["selected"] == []
    assert out["cannot_fit"] is True
    assert out["error"] is not None


def test_compose_call_failure_is_never_cached_and_is_retried(monkeypatch, tmp_path):
    # Regression: a transient infra failure (timeout, non-zero exit, missing binary) must never
    # be written to the replay cache -- it says nothing stable about this query/candidate pair,
    # and permanently caching it would poison every later run hit by one load spike or flaky
    # call. A cache-miss retry after a failure must call the model again, and a later success
    # must then be the one that gets cached.
    calls = []
    def failing_then_ok(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=30)
        return _fake_proc(_wrapper({"selected": ["u:invoice"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", failing_then_ok)
    cache = cm.ReplayCache(tmp_path / "cache.jsonl")

    out1 = cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    assert out1["error"] is not None
    assert len(cache) == 0  # failure must not be persisted

    out2 = cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    assert len(calls) == 2  # retried, not served from a poisoned cache entry
    assert out2["error"] is None
    assert len(cache) == 1  # the genuine success is the one that gets cached


def test_compose_reruns_model_when_candidate_set_changes_even_with_same_query_id(monkeypatch, tmp_path):
    calls = []
    def fake_run(*a, **kw):
        calls.append(1)
        return _fake_proc(_wrapper({"selected": ["u:invoice"], "cannot_fit": False}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    cache = cm.ReplayCache(tmp_path / "cache.jsonl")
    cm.compose("q1", "pay an invoice", _candidates(), cache=cache)
    changed = _candidates()
    changed.append({"urn": "u:extra", "name": "extra", "description": "an extra candidate"})
    cm.compose("q1", "pay an invoice", changed, cache=cache)
    assert len(calls) == 2
