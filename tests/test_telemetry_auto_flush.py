"""Telemetry upload is automatic (background, detached, no manual `telemetry flush` needed) and
**on by default** once the adapter has a bearer credential and a configured endpoint -- owner
decision 2026-09-13 ("klient automatycznie powinien miec opt in na telemetrie"), recorded in
[ADR-0048](../docs/adr/ADR-0048-telemetry-upload-on-by-default.md), which amends the earlier
opt-in reading of docs/SEARCH-USE-TELEMETRY.md §5 and docs/DESIGN.md R7.

This suite locks the DEFAULT at ON and tests the opt-out mechanism around it: the persisted
`guidefold telemetry disable`/`enable` switch, the `GUIDEFOLD_TELEMETRY` env override, the
harder pre-existing `GUIDEFOLD_TELEMETRY_DISABLE`, the single-flight trigger under a burst, the
one-time notice (printed before the first upload, naming the exact opt-out command), and the
detached spawn shape. Nothing here widens what an event contains or changes the hook's
zero-socket-in-process guarantee (E1.5) -- only the default state of the switch moved.

`_isolate_guidefold_credentials` (conftest.py, autouse) points GUIDEFOLD_CREDENTIALS at a
per-test tmp file; `_settings_path()` derives `settings.json` as a SIBLING of that file
(`with_name`), so settings.json is isolated from the developer's real ~/.config for free, same
as credentials.json already is.
"""
import json
import os
import urllib.request
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _clear_telemetry_env(monkeypatch):
    """GUIDEFOLD_TELEMETRY / GUIDEFOLD_TELEMETRY_DISABLE must start unset in every test here --
    a value leaking in from the invoking shell would silently change which branch is exercised."""
    monkeypatch.delenv("GUIDEFOLD_TELEMETRY", raising=False)
    monkeypatch.delenv("GUIDEFOLD_TELEMETRY_DISABLE", raising=False)


# -------------------------------------------------------------------------------- default is on

def test_upload_is_on_by_default(gf):
    assert gf.TELEMETRY_UPLOAD_ENABLED_DEFAULT is True
    assert gf._telemetry_upload_enabled() is True


def test_telemetry_status_reports_on_by_default(run_cli, fixture_copy):
    result = run_cli(["telemetry", "status"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    assert "automatic upload is ON" in result.stdout


# --------------------------------------------------------------------- enable / disable persist

def test_disable_then_enable_round_trip(gf, run_cli, fixture_copy):
    """Disable is the meaningful action now (upload starts ON); `enable` is what undoes it."""
    off = run_cli(["telemetry", "disable"], cwd=fixture_copy)
    assert off.returncode == 0, off.stderr
    assert "automatic upload is now OFF" in off.stdout
    assert gf._telemetry_upload_enabled() is False

    status = run_cli(["telemetry", "status"], cwd=fixture_copy)
    assert "automatic upload is OFF" in status.stdout

    on = run_cli(["telemetry", "enable"], cwd=fixture_copy)
    assert on.returncode == 0, on.stderr
    assert "automatic upload is now ON" in on.stdout
    assert gf._telemetry_upload_enabled() is True


def test_disable_persists_to_the_isolated_settings_file(gf, run_cli, fixture_copy):
    run_cli(["telemetry", "disable"], cwd=fixture_copy)
    settings_path = gf._settings_path()
    assert settings_path.is_file()
    assert settings_path.parent == gf._credentials_path().parent, \
        "settings.json must live next to credentials.json, not scattered elsewhere"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["telemetry"]["enabled"] is False
    # Non-secret: unlike credentials.json this never needs mode 0600's confidentiality, but it
    # is still written 0600 by the same shared atomic writer -- checking the writer is reused,
    # not re-litigating file permissions here.
    assert oct(settings_path.stat().st_mode)[-3:] == "600"


def test_enable_persists_to_the_isolated_settings_file(gf, run_cli, fixture_copy):
    run_cli(["telemetry", "enable"], cwd=fixture_copy)
    settings_path = gf._settings_path()
    assert settings_path.is_file()
    assert settings_path.parent == gf._credentials_path().parent, \
        "settings.json must live next to credentials.json, not scattered elsewhere"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["telemetry"]["enabled"] is True
    # Non-secret: unlike credentials.json this never needs mode 0600's confidentiality, but it
    # is still written 0600 by the same shared atomic writer -- checking the writer is reused,
    # not re-litigating file permissions here.
    assert oct(settings_path.stat().st_mode)[-3:] == "600"


# ------------------------------------------------------------------------------- env override

def test_env_override_forces_off_even_when_setting_says_on(gf, monkeypatch):
    monkeypatch.setattr(gf, "_load_settings", lambda: {"telemetry": {"enabled": True}})
    monkeypatch.setenv("GUIDEFOLD_TELEMETRY", "0")
    assert gf._telemetry_upload_enabled() is False


def test_env_override_forces_on_even_when_setting_says_off_or_absent(gf, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_TELEMETRY", "1")
    assert gf._telemetry_upload_enabled() is True
    monkeypatch.setattr(gf, "_load_settings", lambda: {"telemetry": {"enabled": False}})
    assert gf._telemetry_upload_enabled() is True


def test_hard_disable_wins_over_everything(gf, monkeypatch):
    """GUIDEFOLD_TELEMETRY_DISABLE (pre-existing, stops local spooling entirely) also forces
    upload off -- nothing to upload should never be dressed up as "upload enabled"."""
    monkeypatch.setattr(gf, "_load_settings", lambda: {"telemetry": {"enabled": True}})
    monkeypatch.setenv("GUIDEFOLD_TELEMETRY", "1")
    monkeypatch.setenv("GUIDEFOLD_TELEMETRY_DISABLE", "1")
    assert gf._telemetry_upload_enabled() is False


def test_telemetry_status_reports_the_env_override(run_cli, fixture_copy):
    env = {**os.environ, "GUIDEFOLD_TELEMETRY": "1"}
    result = run_cli(["telemetry", "status"], cwd=fixture_copy, env=env)
    assert result.returncode == 0, result.stderr
    assert "automatic upload is ON" in result.stdout
    assert "GUIDEFOLD_TELEMETRY" in result.stdout


# ------------------------------------------------------------- the trigger: never before a token

def test_trigger_does_nothing_when_explicitly_disabled(gf, monkeypatch, tmp_path):
    """Upload is ON by default (ADR-0048) -- this exercises the opt-out itself, not the
    ambient default, so it forces the disabled state explicitly rather than relying on it."""
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: False)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root = tmp_path / "repo"; root.mkdir()
    gf.maybe_trigger_telemetry_auto_flush(root, {"token": "tok", "url": "http://x:1"})
    assert spawned == []


def test_trigger_does_nothing_without_a_token(gf, monkeypatch, tmp_path):
    """Never send before the user has a token -- true before `guidefold login` or an
    installation token is configured at all, regardless of the enable/disable switch."""
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root = tmp_path / "repo"; root.mkdir()
    gf.maybe_trigger_telemetry_auto_flush(root, {"token": None, "url": "http://x:1"})
    assert spawned == []


def test_trigger_does_nothing_without_a_url(gf, monkeypatch, tmp_path):
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root = tmp_path / "repo"; root.mkdir()
    gf.maybe_trigger_telemetry_auto_flush(root, {"token": "tok", "url": None})
    assert spawned == []


def test_trigger_never_raises_even_if_popen_itself_fails(gf, monkeypatch, tmp_path):
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    def _boom(*a, **kw):
        raise OSError("no fork slots left")
    monkeypatch.setattr(gf.subprocess, "Popen", _boom)
    root = tmp_path / "repo"; root.mkdir()
    gf.maybe_trigger_telemetry_auto_flush(root, {"token": "tok", "url": "http://x:1"})  # must not raise


# --------------------------------------------------------- single flush under a burst of calls

def test_a_burst_of_calls_spawns_at_most_one_flush(gf, monkeypatch, tmp_path):
    """"A burst of hook calls starts at most one flush" -- the minimum-interval marker, not the
    OS scheduler, is what this test proves: ten calls to the trigger in the same process, same
    repo, same instant, spawn exactly once."""
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root = tmp_path / "repo"; root.mkdir()
    search_cfg = {"token": "tok", "url": "http://x:1"}
    for _ in range(10):
        gf.maybe_trigger_telemetry_auto_flush(root, search_cfg)
    assert len(spawned) == 1


def test_a_second_burst_after_the_interval_elapses_spawns_again(gf, monkeypatch, tmp_path):
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root = tmp_path / "repo"; root.mkdir()
    search_cfg = {"token": "tok", "url": "http://x:1"}
    gf.maybe_trigger_telemetry_auto_flush(root, search_cfg)
    assert len(spawned) == 1
    # Rewind the marker written by the first call, simulating that the minimum interval has
    # since elapsed, without sleeping the test for real seconds.
    marker = gf._auto_flush_marker_path(root)
    state = json.loads(marker.read_text(encoding="utf-8"))
    state["last_attempt_at"] -= gf.TELEMETRY_AUTO_FLUSH_MIN_INTERVAL_S + 1
    marker.write_text(json.dumps(state), encoding="utf-8")
    gf.maybe_trigger_telemetry_auto_flush(root, search_cfg)
    assert len(spawned) == 2


def test_different_repos_get_independent_intervals(gf, monkeypatch, tmp_path):
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    spawned = []
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    root_a = tmp_path / "repo-a"; root_a.mkdir()
    root_b = tmp_path / "repo-b"; root_b.mkdir()
    search_cfg = {"token": "tok", "url": "http://x:1"}
    gf.maybe_trigger_telemetry_auto_flush(root_a, search_cfg)
    gf.maybe_trigger_telemetry_auto_flush(root_b, search_cfg)
    assert len(spawned) == 2


# ------------------------------------------------------------------------------ the one-time notice

def test_notice_is_printed_once_then_never_again(gf, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: None)
    # Bypass the min-interval gate so both calls reach the notice check -- this test is about
    # the notice's own persisted flag, not the interval covered above.
    monkeypatch.setattr(gf, "_claim_auto_flush_attempt", lambda root: True)
    root = tmp_path / "repo"; root.mkdir()
    search_cfg = {"token": "tok", "url": "http://x:1"}

    gf.maybe_trigger_telemetry_auto_flush(root, search_cfg)
    first_err = capsys.readouterr().err
    assert "telemetry" in first_err.lower()
    assert "disable" in first_err.lower()

    gf.maybe_trigger_telemetry_auto_flush(root, search_cfg)
    second_err = capsys.readouterr().err
    assert second_err == ""


def test_notice_never_appears_on_stdout(gf, monkeypatch, tmp_path, capsys):
    """stdout on the hook path is the harness's own context channel (E1.5) -- a human-facing
    aside belongs on stderr only."""
    monkeypatch.setattr(gf, "_telemetry_upload_enabled", lambda: True)
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: None)
    root = tmp_path / "repo"; root.mkdir()
    gf.maybe_trigger_telemetry_auto_flush(root, {"token": "tok", "url": "http://x:1"})
    assert capsys.readouterr().out == ""


def test_notice_flag_persists_across_processes(gf, run_cli, fixture_copy):
    """Once shown, `settings.json` remembers it -- a fresh CLI invocation (a real subprocess,
    like the detached background flush itself would be) must not show it again."""
    run_cli(["telemetry", "enable"], cwd=fixture_copy)
    settings = gf._load_settings()
    settings.setdefault("telemetry", {})["notice_shown"] = True
    gf._save_settings(settings)
    assert gf._load_settings()["telemetry"]["notice_shown"] is True


# --------------------------------------------------------------------------- the detached spawn

def test_spawn_is_fully_detached_and_carries_no_secret_on_argv(gf, monkeypatch, tmp_path):
    calls = []
    def _fake_popen(argv, **kw):
        calls.append((argv, kw))
        class _P:
            pid = 4242
        return _P()
    monkeypatch.setattr(gf.subprocess, "Popen", _fake_popen)
    root = tmp_path / "repo"; root.mkdir()
    gf._spawn_auto_flush(root)
    assert len(calls) == 1
    argv, kw = calls[0]
    assert argv[0] == gf.sys.executable
    assert argv[1] == str(gf.SCRIPT_PATH)
    assert argv[2:5] == ["telemetry", "flush", "--auto"]
    assert "--budget-s" in argv
    # No bearer token, no --url: the child re-resolves both itself (it is a normal CLI
    # invocation, free to read guidefold.yaml, unlike the hook process that spawned it).
    joined = " ".join(argv)
    assert "gf_" not in joined and "Bearer" not in joined
    assert kw["cwd"] == str(root)
    assert kw["stdin"] is gf.subprocess.DEVNULL
    assert kw["stdout"] is gf.subprocess.DEVNULL
    assert kw["stderr"] is gf.subprocess.DEVNULL
    assert kw["start_new_session"] is True


def test_spawn_never_raises_and_swallows_popen_failures(gf, monkeypatch, tmp_path):
    monkeypatch.setattr(gf.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(OSError("boom")))
    root = tmp_path / "repo"; root.mkdir()
    gf._spawn_auto_flush(root)  # must not raise


# ------------------------------------------------------------------ flush --auto: url and budget
#
# `cmd_telemetry_flush` does `import urllib.request, urllib.error` LOCALLY inside itself (module
# docstring: urllib is one of the imports E1.5 keeps off the hook path). That local `import`
# binds `urllib` inside the function, not as a `gf.urllib` module attribute -- but it still
# resolves to the exact same `sys.modules['urllib.request']` object this file's own top-level
# `import urllib.request` gets, so patching `urllib.request.urlopen` here reaches it. Likewise
# `time.monotonic` (`gf.time` IS the same singleton `time` module `cmd_telemetry_flush`'s local
# `import time as _time` re-binds).

def test_flush_url_defaults_to_configured_search_url(gf, monkeypatch, tmp_path):
    """`--auto` (and any manual run) may omit `--url` when `search.url`/`GUIDEFOLD_SEARCH_URL`
    is configured -- the automatic trigger relies on exactly this."""
    root = tmp_path / "repo"; root.mkdir()
    a = SimpleNamespace(url=None, token_file=None, budget_s=None, auto=True)
    cfg = {"search": {"url": "http://configured-search:9"}}
    gf.cmd_telemetry_flush(a, root, cfg)   # empty spool: no request, but must not die for lack of --url


def test_flush_dies_when_no_url_anywhere(gf, tmp_path):
    root = tmp_path / "repo"; root.mkdir()
    a = SimpleNamespace(url=None, token_file=None, budget_s=None, auto=False)
    with pytest.raises(SystemExit):
        gf.cmd_telemetry_flush(a, root, None)


def test_flush_respects_a_wall_clock_budget_and_drops_nothing(gf, monkeypatch, tmp_path):
    """A budget so small it expires before the first request is even sent must leave every
    queued event exactly as it was -- "never fail or slow the user's command" also means never
    silently discarding what a budget cutoff didn't get to."""
    root = tmp_path / "repo"; root.mkdir()
    env_dir = gf._telemetry_spool_dir(root, "local", "dev")
    env_dir.mkdir(parents=True)
    record = {"event_id": "e1", "event_type": "search_requested", "occurred_at": gf._utc_now_iso()}
    spool_file = env_dir / "events-2026-01-01.jsonl"
    spool_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    sent = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=10: sent.append(req.full_url), raising=False)

    a = SimpleNamespace(url="http://x:1", token_file=None, budget_s=0.0, auto=True)
    gf.cmd_telemetry_flush(a, root, None)

    assert sent == [], "budget_s=0 must expire before any request is sent"
    assert spool_file.is_file()
    assert json.loads(spool_file.read_text(encoding="utf-8").splitlines()[0])["event_id"] == "e1"


def test_flush_sends_everything_with_no_budget(gf, monkeypatch, tmp_path):
    """A manual run with no `--budget-s` (the default) is unbounded, unlike the automatic one."""
    root = tmp_path / "repo"; root.mkdir()
    env_dir = gf._telemetry_spool_dir(root, "local", "dev")
    env_dir.mkdir(parents=True)
    record = {"event_id": "e1", "event_type": "search_requested", "occurred_at": gf._utc_now_iso()}
    spool_file = env_dir / "events-2026-01-01.jsonl"
    spool_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    sent = []
    class _FakeResp:
        def read(self):
            return json.dumps({"accepted": ["e1"], "duplicate": [], "rejected": []}).encode()
    def _fake_urlopen(req, timeout=10):
        sent.append(req.full_url)
        return _FakeResp()
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen, raising=False)

    a = SimpleNamespace(url="http://x:1", token_file=None, budget_s=None, auto=False)
    gf.cmd_telemetry_flush(a, root, None)

    assert sent == ["http://x:1/v1/events:batch"]
    assert not spool_file.exists(), "the acknowledged event must be drained from the spool"


# ----------------------------------------------------------------- end to end, real hook process

def test_hook_triggers_auto_flush_end_to_end_when_enabled(gf, run_cli, fixture_copy, tmp_path):
    """The full loop, through a real `guidefold hook` subprocess: `telemetry enable` persisted,
    a stored login token, a configured search.url, a real prompt -- the hook must (a) still
    behave exactly as an ordinary hook call (prints the cards, exits 0, writes local telemetry)
    and (b) claim the per-repo auto-flush interval marker and print the one-time notice to
    stderr, proving `maybe_trigger_telemetry_auto_flush` reached and passed every gate. It does
    NOT wait for the spawned child to finish (that child hits GUIDEFOLD_SEARCH_URL, which points
    nowhere real here and will just fail its own network call harmlessly, in its own detached
    process) -- only that the hook itself returned promptly with the marker already written,
    which is exactly what a synchronous, non-blocking spawn guarantees."""
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    enabled = run_cli(["telemetry", "enable"], cwd=fixture_copy)
    assert enabled.returncode == 0, enabled.stderr

    api = "https://api.example.test"
    gf._save_credentials({api: {"token": "gf_stored-login-token", "org": "acme"}}, root=None)

    cache_dir = tmp_path / ".cache-guidefold"
    env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir),
           "GUIDEFOLD_SEARCH_URL": "http://127.0.0.1:1"}   # unreachable on purpose: never awaited

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    payload = {"cwd": str(cwd), "prompt": "we're paged right now, help me handle this outage"}
    result = run_cli(["hook"], cwd=fixture_copy, input=json.dumps(payload), env=env)

    assert result.returncode == 0, result.stderr
    assert "Relevant organizational guidance" in result.stdout
    assert "telemetry" in result.stderr.lower()
    assert "disable" in result.stderr.lower()

    marker = gf._auto_flush_marker_path(fixture_copy)
    assert marker.is_file(), "the hook must have claimed the auto-flush interval before returning"
