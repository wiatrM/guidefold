"""`guidefold find` prints its cards in relevance order (best match first), while the hook keeps the
general -> specific injection order (ADR-0006). Before this test the flagship example from SKILL.md
("add authorization check to Turnstile Spanner path") printed the exact match 7th of 8, behind four
root-level convention cards."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "skills" / "guidefold" / "scripts" / "guidefold"
FIXTURE = REPO / "examples" / "monorepo"
QUERY = "add authorization check to Turnstile Spanner path"


def _run(args, stdin=None, cwd=FIXTURE):
    env = dict(os.environ, PYTHONHASHSEED="0")
    return subprocess.run([sys.executable, str(CLI), *args], input=stdin, cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def _urns(out: str) -> list:
    return [line.split()[1].split(" ")[0] for line in out.splitlines() if line.startswith("- urn:")]


def _scores(out: str) -> list:
    return [int(line.split("score=")[1].split(" ")[0]) for line in out.splitlines() if "(score=" in line]


def test_find_prints_best_match_first_and_scores_descending():
    r = _run(["find", QUERY, "--scope", "atlas.identity.turnstile"])
    assert r.returncode == 0, r.stderr
    urns = _urns(r.stdout)
    assert urns, r.stdout
    assert urns[0].endswith("atlas.identity.turnstile:postgres-auth"), urns
    scores = _scores(r.stdout)
    assert scores == sorted(scores, reverse=True), scores


def test_hook_keeps_general_to_specific_injection_order():
    payload = json.dumps({"session_id": "t", "hook_event_name": "UserPromptSubmit",
                          "cwd": str(FIXTURE / "platforms" / "atlas" / "identity" / "turnstile"),
                          "prompt": "the auth check in the Spanner path fails after the deploy, fix it"})
    r = _run(["hook"], stdin=payload)
    assert r.returncode == 0, r.stderr
    urns = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("- urn:")]
    assert urns, r.stdout
    # root-most card first: an atlas.identity card precedes the atlas.identity.turnstile cards
    depth = [u.split(":")[3].count(".") for u in urns]
    assert depth == sorted(depth), urns
