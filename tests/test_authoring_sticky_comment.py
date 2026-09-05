"""Tests for tools/authoring/sticky_comment.py — authoring loop, part 1, deliverable #3's "one
sticky PR comment... never a new comment per push" requirement (deliverable #5: "tests ... for
the sticky-comment marker logic (mock the API)").

`find_marked_comment`/`plan_upsert` are pure (no I/O) and tested directly with hand-built comment
lists. `upsert_sticky_comment`/`list_issue_comments` take an injectable `runner` in place of
`subprocess.run`, so the "does it call `gh api` PATCH vs POST, with which id" behaviour is tested
by asserting on the argv a fake runner recorded -- no network, no real `gh` binary required.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


SC = _load("gf_test_sticky_comment", "tools/authoring/sticky_comment.py")


# --------------------------------------------------------------------------- pure marker logic
def test_render_comment_body_puts_marker_on_its_own_first_line():
    body = SC.render_comment_body("## report\n\nsome text", marker="<!-- m -->")
    assert body.splitlines()[0] == "<!-- m -->"
    assert "some text" in body


def test_find_marked_comment_none_when_no_comment_carries_the_marker():
    comments = [{"id": 1, "body": "unrelated comment"}, {"id": 2, "body": "another one"}]
    assert SC.find_marked_comment(comments, marker="<!-- guidefold:skill-authoring-report -->") is None


def test_find_marked_comment_finds_first_match_by_default_marker():
    comments = [
        {"id": 1, "body": "unrelated"},
        {"id": 2, "body": "<!-- guidefold:skill-authoring-report -->\nold report"},
        {"id": 3, "body": "<!-- guidefold:skill-authoring-report -->\nanother marked one (should not happen)"},
    ]
    found = SC.find_marked_comment(comments)
    assert found["id"] == 2   # first match wins, in list order


def test_find_marked_comment_tolerates_missing_body_key():
    comments = [{"id": 1}, {"id": 2, "body": None}]
    assert SC.find_marked_comment(comments) is None


def test_plan_upsert_creates_when_no_marked_comment_exists():
    plan = SC.plan_upsert([{"id": 1, "body": "unrelated"}], "NEW BODY", marker="<!-- m -->")
    assert plan == {"action": "create", "comment_id": None, "body": "NEW BODY"}


def test_plan_upsert_updates_the_existing_marked_comment_not_a_new_one():
    comments = [{"id": 1, "body": "unrelated"}, {"id": 42, "body": "<!-- m -->\nold"}]
    plan = SC.plan_upsert(comments, "NEW BODY", marker="<!-- m -->")
    assert plan == {"action": "update", "comment_id": 42, "body": "NEW BODY"}


def test_plan_upsert_never_produces_two_marked_comments_across_repeated_calls():
    """Simulates three CI pushes: the same PR comment thread is fed back into plan_upsert each
    time, and the plan must always target the *same* comment id -- proving the "never a new
    comment per push" contract at the decision-logic level."""
    comments = [{"id": 1, "body": "unrelated"}]
    ids_targeted = []
    for push_body in ["report v1", "report v2", "report v3"]:
        plan = SC.plan_upsert(comments, SC.render_comment_body(push_body), marker=SC.DEFAULT_MARKER)
        if plan["action"] == "create":
            new_id = 999  # what the fake "gh api POST" would hand back
            comments.append({"id": new_id, "body": plan["body"]})
            ids_targeted.append(new_id)
        else:
            comments[-1]["body"] = plan["body"]   # what the fake "gh api PATCH" would apply
            ids_targeted.append(plan["comment_id"])
    assert ids_targeted == [999, 999, 999]
    assert sum(1 for c in comments if SC.DEFAULT_MARKER in (c.get("body") or "")) == 1


# --------------------------------------------------------------------------- mocked-transport upsert
class _FakeRunner:
    """Stands in for subprocess.run: records every invocation and returns a canned stdout keyed
    off the first two argv tokens after "gh api" (so both a GET-list and a POST/PATCH call in the
    same test get distinct, deterministic responses without touching the network)."""

    def __init__(self, list_response):
        self.calls = []
        self.list_response = list_response

    def __call__(self, argv, capture_output=True, text=True, check=True):
        self.calls.append(argv)
        assert argv[:2] == ["gh", "api"]
        if "-X" not in argv:   # the plain GET-list call
            return SimpleNamespace(stdout=json.dumps(self.list_response), returncode=0)
        if argv[argv.index("-X") + 1] == "POST":
            return SimpleNamespace(stdout=json.dumps({"id": 555}), returncode=0)
        return SimpleNamespace(stdout="", returncode=0)   # PATCH: GitHub returns the updated comment; unused here


def test_upsert_sticky_comment_creates_when_nothing_marked_yet():
    runner = _FakeRunner(list_response=[{"id": 1, "body": "unrelated"}])
    result = SC.upsert_sticky_comment("owner/repo", 7, "## report body", runner=runner)
    assert result == {"action": "created", "id": 555}
    list_call, write_call = runner.calls
    assert list_call == ["gh", "api", "repos/owner/repo/issues/7/comments"]
    assert write_call[:2] == ["gh", "api"]
    assert write_call[2] == "repos/owner/repo/issues/7/comments"
    assert "-X" in write_call and write_call[write_call.index("-X") + 1] == "POST"
    body_arg = write_call[write_call.index("-f") + 1]
    assert body_arg.startswith(f"body={SC.DEFAULT_MARKER}")


def test_upsert_sticky_comment_updates_the_marked_comment_in_place():
    runner = _FakeRunner(list_response=[
        {"id": 1, "body": "unrelated"},
        {"id": 42, "body": f"{SC.DEFAULT_MARKER}\nold report"},
    ])
    result = SC.upsert_sticky_comment("owner/repo", 7, "## new report body", runner=runner)
    assert result == {"action": "updated", "id": 42}
    list_call, write_call = runner.calls
    assert write_call[2] == "repos/owner/repo/issues/comments/42"
    assert "-X" in write_call and write_call[write_call.index("-X") + 1] == "PATCH"
    body_arg = write_call[write_call.index("-f") + 1]
    assert "new report body" in body_arg


def test_upsert_sticky_comment_never_creates_a_second_comment_across_repeated_runs():
    """End-to-end (through the mocked transport) version of the repeated-push guarantee: three
    upserts against a runner whose list_response is updated between calls (as a real PR's comment
    list would be after the first POST) only ever PATCH the one comment created on push 1."""
    state = {"comments": [{"id": 1, "body": "unrelated"}]}

    class _StatefulRunner:
        def __call__(self, argv, capture_output=True, text=True, check=True):
            assert argv[:2] == ["gh", "api"]
            if "-X" not in argv:
                return SimpleNamespace(stdout=json.dumps(state["comments"]), returncode=0)
            x = argv[argv.index("-X") + 1]
            body = argv[argv.index("-f") + 1].split("=", 1)[1]
            if x == "POST":
                new_id = 555
                state["comments"].append({"id": new_id, "body": body})
                return SimpleNamespace(stdout=json.dumps({"id": new_id}), returncode=0)
            # PATCH
            comment_id = int(argv[2].rsplit("/", 1)[-1])
            for c in state["comments"]:
                if c["id"] == comment_id:
                    c["body"] = body
            return SimpleNamespace(stdout="", returncode=0)

    runner = _StatefulRunner()
    r1 = SC.upsert_sticky_comment("owner/repo", 7, "v1", runner=runner)
    r2 = SC.upsert_sticky_comment("owner/repo", 7, "v2", runner=runner)
    r3 = SC.upsert_sticky_comment("owner/repo", 7, "v3", runner=runner)
    assert r1 == {"action": "created", "id": 555}
    assert r2 == {"action": "updated", "id": 555}
    assert r3 == {"action": "updated", "id": 555}
    marked = [c for c in state["comments"] if SC.DEFAULT_MARKER in (c.get("body") or "")]
    assert len(marked) == 1
    assert "v3" in marked[0]["body"]
