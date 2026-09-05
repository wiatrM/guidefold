#!/usr/bin/env python3
"""tools/authoring/sticky_comment.py — authoring loop, part 1, deliverable #3's "one sticky PR
comment" requirement: find-and-update by a hidden marker, never a new comment per push.

The decision logic (`find_marked_comment`, `plan_upsert`) is pure — it takes an already-fetched
list of PR comments and returns *what to do*, so it is unit-testable with a hand-built comment
list and no network (deliverable #5: "sticky-comment marker logic, mock the API"). `upsert_sticky_comment`
is the thin, mockable-by-injection wrapper that actually calls `gh api` (GITHUB_TOKEN-authenticated,
same as `templates/github-workflows-skills.yml`'s existing drift comment) — every call to it takes a
`runner` (defaults to `subprocess.run`) so a test can substitute a fake one and assert on the argv
it was given, without ever making an HTTP request.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MARKER = "<!-- guidefold:skill-authoring-report -->"


def render_comment_body(markdown: str, marker: str = DEFAULT_MARKER) -> str:
    """The marker lives on its own first line so `find_marked_comment` can match it as a plain
    substring without parsing markdown."""
    return f"{marker}\n{markdown}"


def find_marked_comment(comments: list, marker: str = DEFAULT_MARKER):
    """First comment (in the given order) whose body contains `marker`, or None. `comments` is the
    GitHub REST "list issue comments" shape: a list of `{"id": ..., "body": ..., ...}` dicts."""
    for c in comments:
        if marker in (c.get("body") or ""):
            return c
    return None


def plan_upsert(comments: list, body: str, marker: str = DEFAULT_MARKER) -> dict:
    """Pure decision: given the current comment list and the new report body, say whether this run
    should PATCH an existing marked comment or POST a new one, and with what id/body. No I/O."""
    existing = find_marked_comment(comments, marker)
    if existing is not None:
        return {"action": "update", "comment_id": existing["id"], "body": body}
    return {"action": "create", "comment_id": None, "body": body}


# --------------------------------------------------------------------------------- gh api wrapper
def _gh_api(args: list, runner=subprocess.run) -> str:
    result = runner(["gh", "api", *args], capture_output=True, text=True, check=True)
    return result.stdout


def list_issue_comments(repo: str, pr_number: int, runner=subprocess.run) -> list:
    """First page (up to 30) of a PR's comments — plenty for a single sticky marker; avoids
    `--paginate`'s concatenated-JSON-array output, which would need extra parsing for no benefit
    here."""
    out = _gh_api([f"repos/{repo}/issues/{pr_number}/comments"], runner=runner)
    return json.loads(out) if out.strip() else []


def upsert_sticky_comment(repo: str, pr_number: int, markdown: str, marker: str = DEFAULT_MARKER,
                           runner=subprocess.run) -> dict:
    """Find-and-update by `marker`; create only if no marked comment exists yet. Never duplicates
    the sticky comment across pushes."""
    comments = list_issue_comments(repo, pr_number, runner=runner)
    body = render_comment_body(markdown, marker)
    plan = plan_upsert(comments, body, marker)
    if plan["action"] == "update":
        _gh_api([f"repos/{repo}/issues/comments/{plan['comment_id']}", "-X", "PATCH", "-f",
                 f"body={plan['body']}"], runner=runner)
        return {"action": "updated", "id": plan["comment_id"]}
    out = _gh_api([f"repos/{repo}/issues/{pr_number}/comments", "-X", "POST", "-f",
                   f"body={plan['body']}"], runner=runner)
    created = json.loads(out) if out.strip() else {}
    return {"action": "created", "id": created.get("id")}


# --------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/name, e.g. ${{ github.repository }}")
    ap.add_argument("--pr", required=True, type=int, help="pull request number")
    ap.add_argument("--body-file", required=True, help="markdown file to post/update as the sticky comment")
    ap.add_argument("--marker", default=DEFAULT_MARKER)
    args = ap.parse_args(argv)

    markdown = Path(args.body_file).read_text()
    result = upsert_sticky_comment(args.repo, args.pr, markdown, marker=args.marker)
    print(f"sticky_comment: {result['action']} comment {result.get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
