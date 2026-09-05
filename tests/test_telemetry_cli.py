"""tests/test_telemetry_cli.py -- E6.4/E2.7: the CLI's own SEARCH/USE telemetry pipeline
(skills/guidefold/scripts/guidefold's "E6.4/E2.7 SEARCH/USE telemetry" block), exercised through
`find`, `hook`, `load` and `telemetry status|flush`. docs/SEARCH-USE-TELEMETRY.md is normative for
event shape. See tests/test_telemetry_ledger.py / test_telemetry_report.py for the ledger/report
side, and tests/test_shadow_telemetry.py for the separate, older E1.6 shadow mechanism.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INGEST_SERVER = REPO_ROOT / "tools" / "telemetry" / "ingest_server.py"
sys.path.insert(0, str(REPO_ROOT))

QUERY = "add RBAC to this new admin-only endpoint"
URN = "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"


def _spool_dir(cwd, tenant="local", env="dev"):
    return Path(cwd) / ".guidefold" / "telemetry" / "spool" / tenant / env


def _spool_lines(cwd, tenant="local", env="dev"):
    d = _spool_dir(cwd, tenant, env)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("events-*.jsonl")):
        out += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return out


# --------------------------------------------------------------- find / hook / load emit events

def test_plain_find_writes_search_requested_results_and_card_injected(run_cli, fixture_copy):
    result = run_cli(["find", QUERY], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr

    events = _spool_lines(fixture_copy)
    types = [e["event_type"] for e in events]
    assert types.count("search_requested") == 1
    assert types.count("search_results") == 1
    assert types.count("card_injected") >= 1

    sr = next(e for e in events if e["event_type"] == "search_requested")
    assert sr["profile"] == "interactive"
    assert sr["scope"]
    assert sr["deadline_ms"] == 1000
    assert isinstance(sr["query_hmac"], str) and len(sr["query_hmac"]) == 64
    for envelope_field in ("schema_version", "event_id", "occurred_at", "sequence", "producer",
                           "adapter_version", "environment"):
        assert envelope_field in sr

    results = next(e for e in events if e["event_type"] == "search_results")
    assert results["status"] == "ok"
    assert results["search_id"] == sr["search_id"]
    assert results["timings"]["total_ms"] >= 0

    card = next(e for e in events if e["event_type"] == "card_injected")
    assert card["search_id"] == sr["search_id"]
    assert card["surface"] == "interactive"
    assert card["delivery_evidence"] == "printed_stdout"
    assert card["scope"]


def test_no_raw_prompt_text_in_the_spool_by_default_or_with_telemetry_raw(run_cli, fixture_copy):
    """Non-negotiable: prompt text stays out of the spool by default. --telemetry-raw is scoped to
    the OLD E1.6 shadow file only -- it must not leak the raw query into this new spool either."""
    result = run_cli(["find", QUERY, "--telemetry-raw"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    events = _spool_lines(fixture_copy)
    assert events
    assert QUERY not in json.dumps(events)


def test_telemetry_disable_kill_switch_suppresses_every_write(run_cli, fixture_copy):
    env = {**os.environ, "GUIDEFOLD_TELEMETRY_DISABLE": "1"}
    result = run_cli(["find", QUERY], cwd=fixture_copy, env=env)
    assert result.returncode == 0, result.stderr
    assert not _spool_dir(fixture_copy).exists()


def test_hook_writes_search_and_card_injected_events_carrying_session_id(run_cli, fixture_copy):
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    payload = {"cwd": str(cwd), "prompt": "we're paged right now, help me handle this outage",
               "session_id": "sess-abc-123"}
    result = run_cli(["hook"], cwd=fixture_copy, input=json.dumps(payload))
    assert result.returncode == 0, result.stderr

    events = _spool_lines(fixture_copy)
    sr = next(e for e in events if e["event_type"] == "search_requested")
    assert sr["profile"] == "hook"
    assert sr["session_id"] == "sess-abc-123"
    cards = [e for e in events if e["event_type"] == "card_injected"]
    assert cards and all(c["surface"] == "hook" for c in cards)
    assert all(c["session_id"] == "sess-abc-123" for c in cards)


def test_load_writes_skill_load_requested_and_completed_ok(run_cli, fixture_copy):
    result = run_cli(["load", URN], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr

    events = _spool_lines(fixture_copy)
    requested = next(e for e in events if e["event_type"] == "skill_load_requested")
    completed = next(e for e in events if e["event_type"] == "skill_load_completed")
    assert requested["load_id"] == completed["load_id"]
    assert requested["skill_id"] == URN
    assert completed["status"] == "ok"
    assert completed["cache_source"] in ("cache", "download")
    assert completed["bytes"] > 0
    assert completed["closure_status"] == "complete"


def test_load_of_unknown_urn_still_emits_a_failed_completed_event(run_cli, fixture_copy):
    bad_urn = "urn:skill:meridian:_root:does-not-exist"
    result = run_cli(["load", bad_urn], cwd=fixture_copy)
    assert result.returncode != 0

    events = _spool_lines(fixture_copy)
    completed = next(e for e in events if e["event_type"] == "skill_load_completed")
    assert completed["status"] == "error"
    assert completed["closure_status"] == "incomplete"


def test_no_bearer_token_or_secret_ever_lands_in_the_spool(run_cli, fixture_copy):
    run_cli(["find", QUERY], cwd=fixture_copy)
    run_cli(["load", URN], cwd=fixture_copy)
    dumped = json.dumps(_spool_lines(fixture_copy)).lower()
    assert "bearer" not in dumped
    assert "authorization" not in dumped


# --------------------------------------------------------------------- no network on hook path

def test_hook_makes_no_network_call(run_cli, fixture_copy, tmp_path):
    """Poison socket.socket at import time (sitecustomize.py on PYTHONPATH, same technique as
    tests/test_no_torch_import.py's torch guard) so ANY attempt anywhere in the hook's call graph
    to open a socket raises loudly instead of silently succeeding. `telemetry flush` is the only
    command that ever makes a network call, and it is never invoked from `hook`."""
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    poison = (
        "import socket\n"
        "class _NoNetwork(socket.socket):\n"
        "    def __init__(self, *a, **kw):\n"
        "        raise AssertionError('no network call is allowed on the guidefold hook path')\n"
        "socket.socket = _NoNetwork\n"
        "def _no_create_connection(*a, **kw):\n"
        "    raise AssertionError('no network call is allowed on the guidefold hook path')\n"
        "socket.create_connection = _no_create_connection\n"
    )
    (fixture_copy / "sitecustomize.py").write_text(poison, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(fixture_copy) + os.pathsep + env.get("PYTHONPATH", "")
    env["GUIDEFOLD_CACHE"] = str(tmp_path / ".cache-guidefold")  # match run_cli's own default so
    # the index artifact just built above (under that default env) is still visible here

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    payload = {"cwd": str(cwd), "prompt": "we're paged right now, help me handle this outage"}
    result = run_cli(["hook"], cwd=fixture_copy, input=json.dumps(payload), env=env)
    assert result.returncode == 0, result.stderr
    assert "Relevant organizational guidance" in result.stdout
    events = _spool_lines(fixture_copy)
    assert any(e["event_type"] == "search_requested" for e in events)  # telemetry still wrote --
    # only network access is forbidden, not local spool writes


# --------------------------------------------------------------------------- telemetry status

def test_telemetry_status_reports_queued_count_and_json_form(run_cli, fixture_copy):
    run_cli(["find", QUERY], cwd=fixture_copy)

    text = run_cli(["telemetry", "status"], cwd=fixture_copy)
    assert text.returncode == 0, text.stderr
    assert "local/dev" in text.stdout
    assert "queued=" in text.stdout

    as_json = run_cli(["telemetry", "status", "--json"], cwd=fixture_copy)
    assert as_json.returncode == 0, as_json.stderr
    row = json.loads(as_json.stdout)["partitions"][0]
    assert row["tenant"] == "local" and row["environment"] == "dev"
    assert row["queued"] >= 1


def test_telemetry_status_on_an_empty_spool_says_so_and_never_creates_one(run_cli, fixture_copy):
    result = run_cli(["telemetry", "status"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    assert "empty" in result.stdout
    assert not _spool_dir(fixture_copy).exists()


# ------------------------------------------------------------------------------ telemetry flush

@pytest.fixture
def ingest_server(tmp_path):
    db_path = tmp_path / "ledger.sqlite3"
    proc = subprocess.Popen(
        [sys.executable, str(INGEST_SERVER), "--db", str(db_path), "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = proc.stdout.readline()
    assert line.startswith("PORT "), f"ingest_server did not report a port: {line!r}"
    port = int(line.split()[1])
    try:
        yield f"http://127.0.0.1:{port}", db_path
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_flush_uploads_the_spool_and_drains_it_a_second_flush_sends_nothing(
        run_cli, fixture_copy, ingest_server):
    url, db_path = ingest_server
    run_cli(["find", QUERY], cwd=fixture_copy)
    assert _spool_lines(fixture_copy)

    first = run_cli(["telemetry", "flush", "--url", url], cwd=fixture_copy)
    assert first.returncode == 0, first.stderr
    assert "accepted=" in first.stdout
    assert not _spool_lines(fixture_copy)   # fully drained -- server accepted everything

    second = run_cli(["telemetry", "flush", "--url", url], cwd=fixture_copy)
    assert second.returncode == 0, second.stderr
    assert "sent=0" in second.stdout

    from tools.telemetry import ledger
    conn = ledger.connect(db_path)
    stored = ledger.fetch(conn, "local")
    assert len(stored) >= 3   # search_requested + search_results + >=1 card_injected
    conn.close()


def test_flush_is_never_invoked_from_the_hook_command(run_cli, fixture_copy):
    """Static check: `telemetry flush` and `hook` are two completely separate argparse subcommands
    and cmd_hook's source never calls cmd_telemetry_flush -- confirmed the exercised way too by
    test_hook_makes_no_network_call above (hook succeeds even when sockets are poisoned)."""
    src = (REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold").read_text(encoding="utf-8")
    hook_start = src.index("def cmd_hook(")
    hook_end = src.index("\ndef cmd_prewarm(")
    assert "cmd_telemetry_flush" not in src[hook_start:hook_end]
    assert "urllib" not in src[hook_start:hook_end]


# --------------------------------------------------------------- bounded spool: age eviction

def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_bounded_spool_eviction_by_age_drops_the_old_file_and_counts_it(gf, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tenant, env = "local", "dev"
    env_dir = gf._telemetry_spool_dir(root, tenant, env)
    env_dir.mkdir(parents=True)

    old_date = (datetime.now(timezone.utc)
                - timedelta(days=gf.TELEMETRY_SPOOL_MAX_AGE_DAYS + 3)).strftime("%Y-%m-%d")
    old_file = env_dir / f"events-{old_date}.jsonl"
    old_file.write_text(json.dumps({"event_type": "search_requested",
                                     "occurred_at": f"{old_date}T00:00:00Z"}) + "\n",
                         encoding="utf-8")

    new_record = {"event_type": "card_injected", "occurred_at": _utc_now_iso()}
    gf._prune_and_append(root, tenant, env, new_record)

    assert not old_file.exists()
    health = gf._read_health(gf._health_path(env_dir))
    assert health["dropped"] == 1

    lines = [json.loads(l) for l in
             gf._telemetry_spool_path(root, tenant, env).read_text(encoding="utf-8").splitlines()]
    health_event = next(l for l in lines if l.get("event_type") == "telemetry_health")
    assert health_event["dropped"] == 1
    assert health_event["produced"] == 1


def test_bounded_spool_eviction_by_size_drops_oldest_lines_and_counts_it(gf, tmp_path, monkeypatch):
    monkeypatch.setattr(gf, "TELEMETRY_SPOOL_MAX_BYTES", 2000)   # small bound for a fast test
    root = tmp_path / "repo"
    root.mkdir()
    tenant, env = "local", "dev"
    pad = "x" * 200
    for i in range(30):
        gf._prune_and_append(root, tenant, env,
                              {"event_type": "card_injected", "occurred_at": _utc_now_iso(),
                               "i": i, "pad": pad})

    env_dir = gf._telemetry_spool_dir(root, tenant, env)
    total_bytes = sum(f.stat().st_size for f in env_dir.glob("events-*.jsonl"))
    assert total_bytes <= gf.TELEMETRY_SPOOL_MAX_BYTES + 500   # eviction halves a file at a time,
    # not a byte-exact cap -- generous slack
    health = gf._read_health(gf._health_path(env_dir))
    assert health["produced"] == 30
    assert health["dropped"] > 0
