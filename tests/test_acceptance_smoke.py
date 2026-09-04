"""E1.1 acceptance test, verbatim from the spec: "scope becomes a feature and filter, never the
first sort key; the three smoke-test prompts return three different top-3 lists; deprecated
excluded by default." Runs the real CLI end-to-end (run_cli) against the Meridian fixture, from
the atlas/identity node, exactly as a harness invoking `guidefold find` would."""
import re

PROMPTS = [
    "write an ADR for the new session store",
    "handle an outage in turnstile auth",
    "add RBAC to the graph service",
]
DEPRECATED_URN = "urn:skill:meridian:atlas.identity:legacy-session-auth"
URN_RE = re.compile(r"^- (urn:skill:\S+)$", re.M)


def _cwd(fixture_root):
    return fixture_root / "platforms" / "atlas" / "identity"


def _top_urns(run_cli, fixture_root, prompt, extra=()):
    result = run_cli(["find", prompt, "--limit", "3", *extra], cwd=_cwd(fixture_root))
    assert result.returncode == 0, result.stderr
    return URN_RE.findall(result.stdout), result.stdout


def test_three_smoke_prompts_yield_three_different_top3_lists(run_cli, fixture_root):
    lists = [_top_urns(run_cli, fixture_root, p)[0] for p in PROMPTS]
    for urns in lists:
        assert len(urns) == 3, "expected 3 results per prompt against the full fixture"
    assert lists[0] != lists[1]
    assert lists[1] != lists[2]
    assert lists[0] != lists[2]


def test_deprecated_skill_excluded_by_default_across_all_three_prompts(run_cli, fixture_root):
    for prompt in PROMPTS:
        result = run_cli(["find", prompt, "--limit", "10"], cwd=_cwd(fixture_root))
        assert result.returncode == 0, result.stderr
        assert DEPRECATED_URN not in result.stdout, prompt


def test_deprecated_skill_reappears_with_include_deprecated_flag(run_cli, fixture_root):
    # legacy-session-auth is topically closest to the session-store / turnstile-outage prompts;
    # a generous limit is enough to surface it once the policy drop is lifted.
    found_at_least_once = False
    for prompt in PROMPTS:
        result = run_cli(["find", prompt, "--limit", "10", "--include-deprecated"],
                          cwd=_cwd(fixture_root))
        assert result.returncode == 0, result.stderr
        if DEPRECATED_URN in result.stdout:
            found_at_least_once = True
    assert found_at_least_once


def test_repeated_identical_invocation_is_byte_identical(run_cli, fixture_root):
    prompt = PROMPTS[1]
    r1 = run_cli(["find", prompt, "--limit", "3"], cwd=_cwd(fixture_root))
    r2 = run_cli(["find", prompt, "--limit", "3"], cwd=_cwd(fixture_root))
    assert r1.returncode == r2.returncode == 0
    assert r1.stdout == r2.stdout
