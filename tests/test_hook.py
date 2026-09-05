"""E1.5: the hook pipeline (`guidefold hook`) -- policy filter -> BM25 + dense (local) -> RRF ->
reverse PPR -> selection, surfaced through the actual UserPromptSubmit/SessionStart stdin/stdout
contract, not through Router directly (that's covered in test_router.py / test_index_artifact.py).

Every test here runs the CLI as a real subprocess (via the `run_cli` fixture) rather than calling
cmd_hook() in-process, for two reasons specific to this PR's acceptance criteria:

  1. "identical output for identical (prompt, cwd, sha)" and the PYTHONHASHSEED audit are only
     meaningful across genuinely independent interpreters -- each subprocess gets its own random
     hash seed unless pinned, so an in-process call would make the determinism claim tautological.
  2. The watchdog is a real SIGALRM against wall-clock time; forcing it requires actual elapsed
     time inside a real process, not a monkeypatched clock.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def _hook(run_cli, cwd, *, prompt=None, extra_cwd=None, env=None):
    payload = {}
    if extra_cwd or cwd:
        payload["cwd"] = str(extra_cwd or cwd)
    if prompt is not None:
        payload["prompt"] = prompt
    kw = {"input": json.dumps(payload)}
    if env is not None:
        kw["env"] = env
    return run_cli(["hook"], cwd=cwd, **kw)


def test_hook_session_start_announces_root_scope_and_owner_without_a_prompt(run_cli, fixture_copy):
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    result = _hook(run_cli, fixture_copy)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "[guidefold] scope=_root owner=platform-engineering chain=_root\n"


def test_hook_session_start_at_nested_cwd_reports_the_most_specific_node_and_full_chain(run_cli, fixture_copy):
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    nested = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    result = _hook(run_cli, fixture_copy, extra_cwd=nested)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "[guidefold] scope=atlas.identity.turnstile owner=turnstile-team "
        "chain=atlas.identity.turnstile→atlas.identity→atlas→_root\n"
    )


def test_hook_returns_relevant_cards_for_a_real_prompt(run_cli, fixture_copy):
    """One of the real golden cases (tests/golden/simple.yaml, simple-002): an outage prompt at
    atlas.identity.turnstile must surface the on-call runbook among the <=3 cards the hook prints
    (cmd_hook calls Router.route(..., k=3))."""
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    result = _hook(run_cli, fixture_copy, extra_cwd=cwd,
                    prompt="we're paged right now, help me handle this outage")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "[guidefold] Relevant organizational guidance for scope atlas.identity.turnstile:"
    assert any("urn:skill:meridian:atlas.identity.turnstile:turnstile-oncall-runbook" in l for l in lines)
    assert lines[-1] == ("Load with: .agents/skills/guidefold/scripts/guidefold load <urn>  "
                          "(follow metadata.requires).")


def test_hook_prints_nothing_for_a_trivial_short_prompt(run_cli, fixture_copy):
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    result = _hook(run_cli, fixture_copy, prompt="yes")  # len < 12
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_hook_prints_nothing_when_no_index_artifact_exists_yet(run_cli, fixture_copy):
    """No `guidefold index` has ever run for this sha -- load_index_artifact raises, cmd_hook's
    outer `except Exception: return` swallows it. Silent no-op, not a crash."""
    result = _hook(run_cli, fixture_copy, prompt="a perfectly reasonable, long enough prompt")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_hook_ignores_a_guidefold_yaml_edit_that_would_change_node_resolution_if_reread(run_cli, fixture_copy):
    """E1.5 binding constraint: 'cwd -> node resolves from the artifact's nodes.json, never the
    working-tree guidefold.yaml'. `repo_root()` still needs guidefold.yaml to exist as a landmark
    (that's how the monorepo root is located at all, unrelated to this PR) -- so this test leaves
    the file in place but edits the one node whose *path glob* decides which node "wins" for our
    test cwd: it disables atlas.identity.turnstile's own glob, so a live re-read of guidefold.yaml
    would resolve platforms/atlas/identity/turnstile down to the LESS specific atlas.identity node
    (a different owner and a different candidate set) instead of atlas.identity.turnstile. The hook
    must still report atlas.identity.turnstile with its original owner and still surface the
    turnstile on-call runbook -- proving node_for() only ever consulted the artifact's own
    nodes.json, never re-parsed the edited guidefold.yaml."""
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    nested = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    prompt = "we're paged right now, help me handle this outage"

    before_scope = _hook(run_cli, fixture_copy, extra_cwd=nested)
    before_cards = _hook(run_cli, fixture_copy, extra_cwd=nested, prompt=prompt)
    assert before_scope.returncode == 0 and before_cards.returncode == 0
    assert before_scope.stdout and before_cards.stdout  # sanity: this test would be vacuous on empty output

    yaml_path = fixture_copy / "guidefold.yaml"
    text = yaml_path.read_text()
    needle = 'paths: ["platforms/atlas/identity/turnstile/**"]'
    assert needle in text, "fixture guidefold.yaml layout changed -- update this test's glob edit"
    yaml_path.write_text(text.replace(needle, 'paths: ["platforms/atlas/identity/turnstile-DISABLED/**"]'))

    after_scope = _hook(run_cli, fixture_copy, extra_cwd=nested)
    after_cards = _hook(run_cli, fixture_copy, extra_cwd=nested, prompt=prompt)
    assert after_scope.returncode == 0, after_scope.stderr
    assert after_cards.returncode == 0, after_cards.stderr
    assert after_scope.stdout == before_scope.stdout
    assert after_cards.stdout == before_cards.stdout
    assert "scope=atlas.identity.turnstile owner=turnstile-team" in after_scope.stdout


def test_hook_determinism_five_independent_subprocesses_byte_identical_stdout(run_cli, fixture_copy):
    """Same (prompt, cwd, sha) five times, each a genuinely fresh interpreter (own random
    PYTHONHASHSEED unless the environment already pins one -- confirmed absent in this sandbox).
    Any set/dict iteration-order leak into the printed card list would show up here as flaky
    output across runs, not as a deterministic failure every time."""
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    prompt = "we're paged right now, help me handle this outage"
    outputs = [_hook(run_cli, fixture_copy, extra_cwd=cwd, prompt=prompt).stdout for _ in range(5)]
    assert all(o == outputs[0] for o in outputs), outputs
    assert outputs[0] != ""  # sanity: not vacuously identical because all runs produced nothing


def test_hook_watchdog_times_out_silently_and_emits_telemetry_marker(run_cli, fixture_copy, tmp_path):
    """A sub-millisecond deadline (signal.setitimer supports float seconds) forces the SIGALRM to
    fire somewhere inside cmd_hook's try block on real hardware -- real subprocess startup and file
    I/O alone dwarf 10 microseconds. Contract: exit 0, print nothing, one hook_timeout record in
    .guidefold/telemetry/hook.jsonl.

    Builds its own explicit GUIDEFOLD_CACHE (matching run_cli's own convention: tmp_path /
    ".cache-guidefold") rather than relying on run_cli's env=None default, because this test needs
    to ADD GUIDEFOLD_HOOK_TIMEOUT_S on top of that same cache directory for the second call."""
    cache_dir = tmp_path / ".cache-guidefold"
    env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir)}

    built = run_cli(["index"], cwd=fixture_copy, env=env)
    assert built.returncode == 0, built.stderr

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    prompt = "we're paged right now, help me handle this outage"
    payload = json.dumps({"cwd": str(cwd), "prompt": prompt})

    sane = run_cli(["hook"], cwd=fixture_copy, env=env, input=payload)
    assert sane.returncode == 0 and sane.stdout, "sanity: artifact + payload must work with no watchdog override"

    timeout_env = {**env, "GUIDEFOLD_HOOK_TIMEOUT_S": "0.00001"}
    result = run_cli(["hook"], cwd=fixture_copy, env=timeout_env, input=payload)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    telemetry = fixture_copy / ".guidefold" / "telemetry" / "hook.jsonl"
    assert telemetry.is_file(), "expected a hook_timeout telemetry record to be written"
    records = [json.loads(l) for l in telemetry.read_text().splitlines() if l.strip()]
    assert any(r["event"] == "hook_timeout" for r in records)


def test_hook_never_imports_pyyaml(run_cli, fixture_copy, tmp_path):
    """E1.5 binding constraint: the hook path imports zero PyYAML, provable via
    `python3 -X importtime`. main() special-cases `hook` to call cmd_hook() and return *before*
    load_map() (the only function that imports yaml) is ever reached."""
    cache_dir = tmp_path / ".cache-guidefold"
    env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir)}

    built = run_cli(["index"], cwd=fixture_copy, env=env)
    assert built.returncode == 0, built.stderr

    cwd = fixture_copy / "platforms" / "atlas" / "identity" / "turnstile"
    payload = json.dumps({"cwd": str(cwd), "prompt": "we're paged right now, help me handle this outage"})
    # run_cli builds argv as [sys.executable, CLI_PATH, *args] -- "-X importtime" must be a
    # Python interpreter flag, not a CLI arg, so build the subprocess call directly here instead.
    cli_path = Path(__file__).resolve().parent.parent / "skills" / "guidefold" / "scripts" / "guidefold"
    result = subprocess.run(
        [sys.executable, "-X", "importtime", str(cli_path), "hook"],
        cwd=str(fixture_copy), input=payload, capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "yaml" not in result.stderr, "hook path must never import PyYAML (see main()'s hook special-case)"
