"""Tests for E1.6 `find --experimental` shadow telemetry.

`find --experimental` must return byte-identical output to plain `find` -- shadow mode's whole
point is that the printed/injection result is never touched -- and, as a side effect, append one
JSON line to `.guidefold/telemetry/shadow-<UTC date>.jsonl` recording the *retrieval* order
(`Router.score`, not `Router.select`'s depth-based injection order); see
docs/reports/golden/README.md for why those two orders differ and why conflating them once
understated hit@1 by 64 points. Telemetry writing must never fail or block the command (E1.6
non-negotiable): a telemetry directory the CLI cannot create must not surface as a CLI error.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

QUERY = "add RBAC to this new admin-only endpoint"


def _telemetry_path(cwd) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path(cwd) / ".guidefold" / "telemetry" / f"shadow-{date}.jsonl"


def test_baseline_output_is_byte_identical_with_and_without_experimental(run_cli, fixture_copy):
    plain = run_cli(["find", QUERY], cwd=fixture_copy)
    assert plain.returncode == 0, plain.stderr

    experimental = run_cli(["find", QUERY, "--experimental"], cwd=fixture_copy)
    assert experimental.returncode == 0, experimental.stderr

    assert experimental.stdout == plain.stdout
    assert experimental.stderr == plain.stderr


def test_without_experimental_no_telemetry_is_written(run_cli, fixture_copy):
    result = run_cli(["find", QUERY], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    assert not (fixture_copy / ".guidefold" / "telemetry").exists()


def test_experimental_writes_one_shadow_request_hashed_by_default(run_cli, fixture_copy):
    result = run_cli(["find", QUERY, "--experimental"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr

    path = _telemetry_path(fixture_copy)
    assert path.is_file(), f"expected shadow telemetry at {path}"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])

    assert record["type"] == "shadow_request"
    assert len(record["request_id"]) == 36  # uuid4 with dashes
    assert record["node"]
    assert record["index_sha"]
    assert record["cli_version"]
    assert len(record["query_sha256"]) == 64
    assert "query" not in record  # hash-only by default -- privacy, see the CLI's --telemetry-raw help
    assert 0 < len(record["top20"]) <= 20
    assert all({"urn", "score"} <= set(c) for c in record["top20"])


def test_telemetry_raw_stores_the_raw_query_text(run_cli, fixture_copy):
    result = run_cli(["find", QUERY, "--experimental", "--telemetry-raw"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr

    path = _telemetry_path(fixture_copy)
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["query"] == QUERY
    assert len(record["query_sha256"]) == 64  # hash is still present alongside the raw text


def test_two_experimental_calls_same_day_append_two_lines(run_cli, fixture_copy):
    run_cli(["find", QUERY, "--experimental"], cwd=fixture_copy)
    run_cli(["find", "rotate the signing key", "--experimental"], cwd=fixture_copy)

    lines = _telemetry_path(fixture_copy).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    ids = {json.loads(l)["request_id"] for l in lines}
    assert len(ids) == 2  # distinct request ids, never reused


def test_shadow_record_top20_is_retrieval_order_not_injection_order(run_cli, fixture_copy):
    """The whole point of the shadow record: it must capture Router.score order (did ranking put
    the right skill on top?), not Router.select's depth-based injection order (root-most first).
    On this fixture the two orders visibly disagree for this query -- if a future change ever made
    them match, this assertion should be re-examined, not deleted (see docs/reports/golden/README.md's
    64-point hit@1 regression that once came from conflating the two orders)."""
    result = run_cli(["find", QUERY, "--experimental"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr

    printed_first_line = result.stdout.splitlines()[0]
    printed_first_urn = printed_first_line.split()[-1]  # "- <urn>"

    record = json.loads(_telemetry_path(fixture_copy).read_text(encoding="utf-8").splitlines()[-1])
    retrieval_first_urn = record["top20"][0]["urn"]

    assert retrieval_first_urn != printed_first_urn
    assert retrieval_first_urn == "urn:skill:meridian:atlas.identity:rbac-policies"


def test_telemetry_write_failure_never_fails_the_command(run_cli, fixture_copy):
    """Simulate a telemetry directory that cannot be created: a plain FILE sitting where
    `.guidefold/` should be a directory. `find --experimental` must still succeed and print the
    normal result -- the telemetry write must fail silently (the CLI's `_write_shadow_record`
    wraps the whole write in a bare `except Exception: pass`)."""
    (fixture_copy / ".guidefold").write_text("not a directory", encoding="utf-8")

    result = run_cli(["find", QUERY, "--experimental"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    assert "urn:skill:meridian:" in result.stdout
    # still just the file we planted -- no telemetry subtree was created underneath it
    assert (fixture_copy / ".guidefold").is_file()
