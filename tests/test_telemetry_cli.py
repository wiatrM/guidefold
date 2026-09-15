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
    # 2026-09-15 rehearsal: the failing paths sent `cache_source: null`, and the ledger rejects
    # such an event with `missing_required_field:cache_source`
    # (services/search/telemetry-schema.json, a frozen reference). Failed loads were therefore
    # the one thing that never reached `gf.events` -- precisely the rows an owner needs.
    _assert_required_fields_present(completed)


def _assert_required_fields_present(event):
    """Every field the service's frozen telemetry schema marks `required` must be present and
    non-empty in the event the CLI spools; `nullable` fields only have to be present."""
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "services/search/telemetry-schema.json")
        .read_text(encoding="utf-8"))
    spec = schema["required_fields"][event["event_type"]]
    for key in spec.get("required", []):
        assert key in event, f"{event['event_type']}: missing required field {key}"
        assert event[key] is not None and event[key] != "", \
            f"{event['event_type']}: required field {key} is empty ({event[key]!r})"
    for key in spec.get("nullable", []):
        assert key in event, f"{event['event_type']}: missing nullable field {key}"


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
    command that ever makes a network call, and `cmd_hook`'s own process never runs it in-process
    (test_hook_never_calls_telemetry_flush_in_process). Since 2026-09-13, `hook` MAY spawn it as
    a fully separate, detached OS process (`maybe_trigger_telemetry_auto_flush`/
    `_spawn_auto_flush`) -- upload is ON by default (ADR-0048), but the trigger ALSO requires a
    bearer token AND a configured endpoint before it spawns anything, and this fixture has
    neither (no `guidefold login`, no installation token, no `search.url`/GUIDEFOLD_SEARCH_URL),
    so it no-ops before ever reaching a socket and this poison is never even exercised by it.
    tests/test_telemetry_auto_flush.py covers the trigger and the spawned child's shape directly,
    with `subprocess.Popen` mocked rather than poisoned, since a detached child's own crash would
    be invisible to this process's return code anyway."""
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


def test_flush_sends_a_bearer_token_so_it_can_reach_the_real_service(
        run_cli, fixture_copy, tmp_path):
    """`/v1/events:batch` authenticates exactly like `/v1/search` and `/v1/use`.

    Without an `Authorization` header the flush can only ever reach the unauthenticated demo
    ingest server; the hosted service answers `401 unauthorized` and the spool never drains.
    The token comes from `--token-file`, or from the same `search.token_file` the repository
    already configured for `find`/`load`.
    """
    import http.server
    import threading

    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            seen.append({"path": self.path,
                         "authorization": self.headers.get("Authorization"),
                         "tenant": self.headers.get("X-Guidefold-Tenant")})
            events = json.loads(body)["events"]
            payload = json.dumps({"results": [{"event_id": e["event_id"], "status": "accepted"}
                                              for e in events]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    token_file = tmp_path / "token"
    token_file.write_text("gf_acceptance-token-value")
    token_file.chmod(0o600)
    try:
        run_cli(["find", QUERY], cwd=fixture_copy)
        assert _spool_lines(fixture_copy)
        result = run_cli(["telemetry", "flush", "--url", url, "--token-file", str(token_file)],
                         cwd=fixture_copy)
        assert result.returncode == 0, result.stderr
    finally:
        server.shutdown()

    assert seen, "the flush sent nothing"
    assert all(r["path"] == "/v1/events:batch" for r in seen), seen
    assert all(r["authorization"] == "Bearer gf_acceptance-token-value" for r in seen), seen
    # The token is read from a file and never printed.
    assert "gf_acceptance-token-value" not in result.stdout
    assert "gf_acceptance-token-value" not in result.stderr


def test_hook_never_calls_telemetry_flush_in_process(run_cli, fixture_copy):
    """Static check: `cmd_hook`'s own source never calls `cmd_telemetry_flush` and never imports
    `urllib` -- E1.5's zero-sockets-in-the-hook-process invariant, unaffected by the 2026-09-13
    automatic upload feature. That feature (`maybe_trigger_telemetry_auto_flush`, called from
    `cmd_hook`) only ever asks the OS to start a SEPARATE process
    (`subprocess.Popen`/`_spawn_auto_flush`) that itself, in its own interpreter, calls
    `cmd_telemetry_flush` and imports `urllib` -- neither name is expected to appear in
    `cmd_hook`'s own source, and this test still checks exactly that, not merely that they don't
    appear together with a literal call. tests/test_telemetry_auto_flush.py covers the spawn
    itself (detached, argv shape, no secret on the command line) and the min-interval/opt-in
    gating that keeps it from firing on every single hook call."""
    src = (REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold").read_text(encoding="utf-8")
    hook_start = src.index("def cmd_hook(")
    hook_end = src.index("\ndef cmd_prewarm(")
    hook_src = src[hook_start:hook_end]
    assert "cmd_telemetry_flush" not in hook_src
    assert "urllib" not in hook_src
    assert "subprocess.Popen" not in hook_src, \
        "cmd_hook must spawn nothing directly -- only via maybe_trigger_telemetry_auto_flush"
    assert "maybe_trigger_telemetry_auto_flush" in hook_src, \
        "the automatic-upload trigger call itself must still be present in cmd_hook"


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


def test_a_load_after_a_find_carries_the_search_id_that_exposed_the_card(run_cli, fixture_copy):
    """Contract 1.1.4: `find` remembers its exposures locally (ids only, no query text); a later
    `load` of an exposed skill names that search on skill_load_requested and, additively, on
    skill_load_completed. A load of a skill no recent search exposed stays unlinked (null)."""
    session_a = dict(os.environ, GUIDEFOLD_SESSION_ID="sess-A")
    assert run_cli(["find", QUERY], cwd=fixture_copy, env=session_a).returncode == 0
    events = _spool_lines(fixture_copy)
    cards = [e for e in events if e["event_type"] == "card_injected"]
    assert cards
    exposed_urn = cards[0]["skill_id"]
    search_id = cards[0]["search_id"]

    memo = Path(fixture_copy) / ".guidefold" / "telemetry" / "recent-exposures.json"
    assert memo.exists()
    assert QUERY not in memo.read_text(encoding="utf-8")     # ids and timestamps only

    # A load that does not know its session links by recency: unknown is not "different".
    assert run_cli(["load", exposed_urn], cwd=fixture_copy).returncode == 0
    events = _spool_lines(fixture_copy)
    requested = next(e for e in events if e["event_type"] == "skill_load_requested")
    completed = next(e for e in events if e["event_type"] == "skill_load_completed")
    assert requested["search_id"] == search_id
    assert completed["search_id"] == search_id

    # A session known on both sides and different is not a link: another session's card is
    # not this one's.
    session_b = dict(os.environ, GUIDEFOLD_SESSION_ID="sess-B")
    assert run_cli(["load", exposed_urn], cwd=fixture_copy, env=session_b).returncode == 0
    last = [e for e in _spool_lines(fixture_copy) if e["event_type"] == "skill_load_completed"][-1]
    assert "search_id" not in last


def test_a_load_with_no_recent_exposure_stays_unlinked(run_cli, fixture_copy):
    assert run_cli(["load", URN], cwd=fixture_copy).returncode == 0
    events = _spool_lines(fixture_copy)
    requested = next(e for e in events if e["event_type"] == "skill_load_requested")
    completed = next(e for e in events if e["event_type"] == "skill_load_completed")
    assert requested["search_id"] is None
    assert "search_id" not in completed


# ------------------------------------------------- D11: flush races the automatic background flush

def _spool_event(event_id, event_type="card_injected"):
    return json.dumps({"schema_version": "1.1", "event_id": event_id, "event_type": event_type,
                       "occurred_at": _utc_now_iso(), "sequence": 1, "producer": "guidefold-cli",
                       "adapter_version": "test", "environment": "dev"})


def test_flush_survives_a_spool_file_that_vanished_between_listing_and_reading(
        run_cli, tmp_path):
    """D11 (pilot rehearsal 2026-09-15): `telemetry flush` lists the spool files, then reads them
    one by one. The automatic background flush (`--auto`, ADR-0048) drains and unlinks the same
    files, so a manual flush that started first can reach a file that no longer exists and used
    to die with a raw `FileNotFoundError` traceback. Nothing is lost when that happens -- the
    other process sent those events -- so the command must say so in one line and exit 0.

    The race is reproduced deterministically: the ingest server deletes the second spool file
    while it is answering the batch from the first one."""
    import http.server
    import threading

    from _helpers import write_guidefold_yaml
    root = tmp_path / "repo"
    write_guidefold_yaml(root)
    env_dir = root / ".guidefold" / "telemetry" / "spool" / "local" / "dev"
    env_dir.mkdir(parents=True)
    first = env_dir / "events-2026-09-14.jsonl"
    second = env_dir / "events-2026-09-15.jsonl"
    first.write_text(_spool_event("ev-first") + "\n", encoding="utf-8")
    second.write_text(_spool_event("ev-second") + "\n", encoding="utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            events = json.loads(body)["events"]
            second.unlink(missing_ok=True)   # the background flush drains it mid-run
            payload = json.dumps({"accepted": [e["event_id"] for e in events]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        result = run_cli(["telemetry", "flush", "--url", url], cwd=root)
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert "FileNotFoundError" not in result.stderr, result.stderr
    assert "accepted=1" in result.stdout, result.stdout
    assert "events-2026-09-15.jsonl" in result.stdout, result.stdout


def test_flush_with_an_empty_spool_says_there_is_nothing_to_flush_and_exits_0(run_cli, tmp_path):
    from _helpers import write_guidefold_yaml
    root = tmp_path / "empty-repo"
    write_guidefold_yaml(root)
    result = run_cli(["telemetry", "flush", "--url", "http://127.0.0.1:1"], cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "nothing to flush" in result.stdout, result.stdout
