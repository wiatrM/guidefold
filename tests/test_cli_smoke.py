"""End-to-end tests that run the CLI as a real subprocess. `materialize` and `index` write
files, so those run against `fixture_copy` (a throwaway copy of the fixture) rather than the
committed `examples/monorepo` tree."""
import json


def test_where_at_repo_root(run_cli, fixture_root):
    result = run_cli(["where"], cwd=fixture_root)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["node"] == "_root"
    assert payload["owner"] == "platform-engineering"


def test_where_in_nested_node(run_cli, fixture_root):
    cwd = fixture_root / "platforms" / "atlas" / "identity" / "turnstile"
    result = run_cli(["where"], cwd=cwd)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["node"] == "atlas.identity.turnstile"
    assert payload["ancestors"] == ["atlas.identity.turnstile", "atlas.identity", "atlas", "_root"]


def test_find_uses_backend_from_guidefold_yaml(run_cli, fixture_root):
    # examples/monorepo/guidefold.yaml already sets registry.backend: local
    result = run_cli(["find", "authorization check for turnstile"], cwd=fixture_root)
    assert result.returncode == 0, result.stderr
    assert "urn:skill:meridian:" in result.stdout


def test_find_with_explicit_backend_override_before_subcommand(run_cli, fixture_root):
    result = run_cli(["--backend", "local", "find", "authorization check for turnstile"], cwd=fixture_root)
    assert result.returncode == 0, result.stderr
    assert "urn:skill:meridian:" in result.stdout


def test_validate_exits_zero_on_fixture(run_cli, fixture_root):
    result = run_cli(["validate"], cwd=fixture_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "26 skills, 0 errors" in result.stdout


def test_index_writes_hierarchy_index_skill(run_cli, fixture_copy):
    result = run_cli(["index"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    out_file = fixture_copy / ".agents" / "skills" / "hierarchy-index" / "SKILL.md"
    assert out_file.is_file()
    text = out_file.read_text()
    assert 'generated: "true"' in text
    assert "urn:skill:meridian:atlas.identity.turnstile:postgres-auth" in text


def test_materialize_check_detects_missing_then_clean_after_write(run_cli, fixture_copy):
    stale = run_cli(["materialize", "--check"], cwd=fixture_copy)
    assert stale.returncode == 1
    assert "STALE" in stale.stdout

    written = run_cli(["materialize"], cwd=fixture_copy)
    assert written.returncode == 0, written.stderr
    assert (fixture_copy / "AGENTS.md").is_file()
    assert (fixture_copy / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert (fixture_copy / "GEMINI.md").read_text() == "@AGENTS.md\n"

    clean = run_cli(["materialize", "--check"], cwd=fixture_copy)
    assert clean.returncode == 0, clean.stdout
