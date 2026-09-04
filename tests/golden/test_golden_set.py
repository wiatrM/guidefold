"""pytest wrapper around validate_golden.py's checks.

Run with: pytest tests/golden/test_golden_set.py
(or just `pytest` from the repo root, once other suites join tests/).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_golden as vg  # noqa: E402


def _prefixed(errors: list[str], marker: str) -> list[str]:
    return [e for e in errors if marker in e]


def test_total_case_count_in_range():
    errors, total = vg.run_checks()
    assert 150 <= total <= 300, f"total case count {total} not in [150, 300]"


def test_no_check_failures_at_all():
    """Single source of truth: every one of the 9 mandated checks, in one pass."""
    errors, _total = vg.run_checks()
    assert errors == [], "\n" + "\n".join(errors)


def test_ids_unique_and_prefixed():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 2 FAILED") == []


def test_category_proportions_within_tolerance():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 3 FAILED") == []


def test_all_urns_exist_in_fixture():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 4 FAILED") == []


def test_all_cwds_exist():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 5 FAILED") == []


def test_all_nodes_match_node_for_cwd():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 6 FAILED") == []


def test_no_deprecated_skill_marked_relevant():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 7 FAILED") == []


def test_no_near_duplicate_queries():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 8 FAILED") == []


def test_no_applicable_cases_have_empty_relevant():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "CHECK 9 FAILED") == []


def test_mvp_smoke_prompts_present_and_distinct():
    errors, _ = vg.run_checks()
    assert _prefixed(errors, "BONUS CHECK FAILED") == []
