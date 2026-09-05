"""Tests for tools/authoring/collision_report.py — authoring loop, part 1, deliverable #1
(docs/MVP.md §5 "3-6 authoring loop").

`compute_report` is the pure(ish) core (its own docstring: "everything past this point depends
only on two already-built Index objects ... so it is unit-testable without ever shelling out to
git"), so every test here builds two tiny synthetic `Index` snapshots directly with
`Index.from_cards` via `tests/_router_helpers.make_card` — no git archive, no filesystem tree, no
network. The `_snapshot.py`/git-archive/CLI-loading half of the module (`main()`, `build_snapshot_index`)
is exercised only by the real end-to-end run against `examples/monorepo` documented in the PR
description, not here.

The sibling-collision fixture below (cards "u:a"/"u:b", query "alpha widget provisioning") is not
illustrative pseudo-data: the exact vocabulary was chosen by running it through the real BM25F
scorer and confirming the rank order it produces (base: only u:a matches at all; head: u:b
overtakes u:a) — see the git history of this file's construction. Because BM25 here is integer
fixed-point and fully deterministic, that rank order is guaranteed to reproduce, not a coin flip.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from _router_helpers import make_card, make_nodes

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "monorepo"


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CR = _load("gf_test_collision_report", "tools/authoring/collision_report.py")


@pytest.fixture(scope="module")
def metrics_mod():
    return CR.load_metrics_module()


# --------------------------------------------------------------------------- synthetic corpora
def _sibling_pair(gf):
    """(base_idx, head_idx): two same-node cards where head's "u:b" text is edited so that it
    steals the query "alpha widget provisioning" from "u:a" — a real rank inversion, not just a
    changed description. At base, u:b shares zero tokens with the query and never even reaches
    `candidates()`; at head it does, and outranks u:a."""
    nodes = make_nodes("_root")
    base_cards = {
        "u:a": make_card("u:a", "_root", description="alpha widget provisioning setup guide",
                          body="Use this for alpha widget provisioning tasks."),
        "u:b": make_card("u:b", "_root", description="beta gadget maintenance procedures",
                          body="Use this for beta gadget upkeep tasks."),
    }
    head_cards = dict(base_cards)
    head_cards["u:b"] = make_card(
        "u:b", "_root",
        description="alpha widget provisioning setup guide alpha widget provisioning",
        body="Use this for alpha widget provisioning tasks. alpha widget provisioning alpha widget provisioning",
    )
    return gf.Index.from_cards(base_cards, nodes), gf.Index.from_cards(head_cards, nodes)


def _no_change_pair(gf):
    nodes = make_nodes("_root")
    cards = {
        "u:a": make_card("u:a", "_root", description="alpha widget provisioning setup guide",
                          body="Use this for alpha widget provisioning tasks."),
        "u:b": make_card("u:b", "_root", description="beta gadget maintenance procedures",
                          body="Use this for beta gadget upkeep tasks."),
    }
    base_idx = gf.Index.from_cards(cards, nodes)
    head_idx = gf.Index.from_cards(dict(cards), nodes)  # independent Index, byte-identical cards
    return base_idx, head_idx


# --------------------------------------------------------------------------- sibling collision
def test_sibling_collision_detected_via_retrieval_rank_inversion(gf, metrics_mod):
    base_idx, head_idx = _sibling_pair(gf)
    queries = [{"id": "q1", "query": "alpha widget provisioning", "node": "_root"}]

    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, queries, labelled=False, k=2)

    assert report["n_changed_queries"] == 1
    assert report["changed_query_ids"] == ["q1"]
    assert report["added"] == [] and report["removed"] == []
    assert report["changed"] == ["u:b"]   # only u:b's card text differs base->head

    assert len(report["sibling_collisions"]) == 1
    row = report["sibling_collisions"][0]
    assert row["winner"] == "u:b" and row["victim"] == "u:a"
    assert row["node"] == "_root"
    assert row["n_queries"] == 1
    assert row["query_ids"] == ["q1"]

    info = report["per_skill"]["u:b"]
    assert info["status"] == "changed"
    assert info["gains_total"] == 1 and info["gains_query_ids"] == ["q1"]
    assert info["takes_from"] == {"u:a": ["q1"]}
    assert info["never_exposed"] is False
    # u:a's card text is unchanged base->head, so it never gets its own per_skill entry even
    # though it *lost* the query -- "per-skill" is scoped to added|changed|removed cards, exactly
    # like `_snapshot.diff_cards`.
    assert "u:a" not in report["per_skill"]


def test_no_change_diff_yields_empty_report(gf, metrics_mod):
    base_idx, head_idx = _no_change_pair(gf)
    queries = [{"id": "q1", "query": "alpha widget provisioning", "node": "_root"},
               {"id": "q2", "query": "beta gadget maintenance", "node": "_root"}]

    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, queries, labelled=False, k=2)

    assert report["n_changed_queries"] == 0
    assert report["changed_query_ids"] == []
    assert report["added"] == report["removed"] == report["changed"] == []
    assert report["sibling_collisions"] == []
    assert report["per_skill"] == {}
    assert report["never_exposed"] == []


# --------------------------------------------------------------------------- unlabelled vs labelled
def test_unlabelled_mode_skips_metrics(gf, metrics_mod):
    base_idx, head_idx = _sibling_pair(gf)
    queries = [{"id": "q1", "query": "alpha widget provisioning", "node": "_root"}]

    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, queries, labelled=False, k=2)

    assert report["labelled"] is False
    assert report["metrics"] is None
    md = CR.render_markdown(report)
    assert "unlabelled: exposure changes only" in md
    assert "95% CI" not in md.split("### Retrieval-quality deltas")[1] or "no graded cases" not in md


def test_labelled_mode_computes_paired_delta_ci_and_shows_a_real_regression(gf, metrics_mod):
    """The same vocabulary edit that produces a sibling takeover also produces a measurable,
    negative Δhit@1 once the query carries a graded label naming u:a as the required answer and
    u:b as a distractor -- this is the exact "does the PR's edit look bad" signal the report
    exists to surface."""
    base_idx, head_idx = _sibling_pair(gf)
    queries = [{
        "id": "q1", "query": "alpha widget provisioning", "node": "_root",
        "relevant": [{"urn": "u:a", "grade": 3}],
        "distractors": [{"urn": "u:b"}],
    }]

    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, queries, labelled=True, k=2)

    assert report["labelled"] is True
    metrics = report["metrics"]
    assert set(metrics) == {"hit@1", "all_required@2", "distractor_rate@2"}

    hit = metrics["hit@1"]
    assert hit["n"] == 1
    assert hit["mean_base"] == 1.0     # base: u:a ranked first, grade 3 -> hit
    assert hit["mean_head"] == 0.0     # head: u:b (not relevant) now ranked first -> miss
    assert hit["mean_delta"] == -1.0
    assert hit["ci_lo"] == hit["ci_hi"] == -1.0   # n=1: CI collapses to the point estimate

    distr = metrics["distractor_rate@2"]
    assert distr["mean_base"] == 0.0   # u:b (the distractor) wasn't even injected at base
    assert distr["mean_head"] == 1.0   # ... and is injected at head
    assert distr["mean_delta"] == 1.0

    allreq = metrics["all_required@2"]
    assert allreq["mean_base"] == allreq["mean_head"] == 1.0   # u:a still injected on both sides
    assert allreq["mean_delta"] == 0.0

    md = CR.render_markdown(report)
    assert "Retrieval-quality deltas" in md
    assert "hit@1" in md and "-1.000" in md


def test_labelled_flag_true_but_no_graded_cases_reports_n_zero(gf, metrics_mod):
    """A query file can flip `labelled=True` globally (README's contract: "labelled the moment
    ANY case carries relevant/distractors") while a specific query still has none -- that query
    must simply be excluded from the paired samples, not crash the CI computation."""
    base_idx, head_idx = _no_change_pair(gf)
    queries = [{"id": "q1", "query": "alpha widget provisioning", "node": "_root"}]  # no labels
    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, queries, labelled=True, k=2)
    for stats in report["metrics"].values():
        assert stats["n"] == 0
        assert math.isnan(stats["mean_delta"])
    md = CR.render_markdown(report)
    assert "no graded cases" in md


# --------------------------------------------------------------------------- query loading
def test_load_queries_from_files_golden_format_sets_labelled(tmp_path):
    p = tmp_path / "cat.yaml"
    p.write_text(
        "category: simple\n"
        "cases:\n"
        "  - query: find the widget skill\n"
        "    node: _root\n"
        "    relevant: [{urn: 'u:a', grade: 3}]\n"
        "  - query: unrelated query\n"
        "    node: _root\n"
    )
    cases, labelled = CR.load_queries_from_files([str(p)])
    assert labelled is True
    assert len(cases) == 2
    assert all(c["category"] == "simple" for c in cases)
    assert {c["id"] for c in cases} == {"cat-0000", "cat-0001"}


def test_load_queries_from_files_bare_list_is_unlabelled(tmp_path):
    p = tmp_path / "plain.yaml"
    p.write_text("- first query\n- second query\n")
    cases, labelled = CR.load_queries_from_files([str(p)])
    assert labelled is False
    assert [c["query"] for c in cases] == ["first query", "second query"]
    assert [c["node"] for c in cases] == ["_root", "_root"]


def test_load_queries_from_files_dedupes_ids_across_files(tmp_path):
    p1 = tmp_path / "a.yaml"
    p2 = tmp_path / "b.yaml"
    p1.write_text("- one query\n")
    p2.write_text("- another query\n")
    # Force a collision by giving both files the same stem.
    p3 = tmp_path / "sub"
    p3.mkdir()
    p4 = p3 / "a.yaml"
    p4.write_text("- third query\n")
    cases, _ = CR.load_queries_from_files([str(p1), str(p4)])
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_derive_unlabelled_queries_unions_triggers_across_snapshots_and_dedupes(gf):
    nodes = make_nodes("_root")
    base_cards = {"u:a": make_card("u:a", "_root", triggers=["find the widget", "shared phrase"])}
    head_cards = {"u:a": make_card("u:a", "_root", triggers=["find the widget", "shared phrase"]),
                  "u:b": make_card("u:b", "_root", triggers=["shared phrase", "gadget maintenance"])}
    base_idx = gf.Index.from_cards(base_cards, nodes)
    head_idx = gf.Index.from_cards(head_cards, nodes)

    queries, labelled = CR.derive_unlabelled_queries(base_idx, head_idx)

    assert labelled is False
    phrases = [q["query"] for q in queries]
    assert phrases.count("shared phrase") == 1, "duplicate trigger phrase across snapshots must be deduped"
    assert "find the widget" in phrases and "gadget maintenance" in phrases
    assert all(q["id"].startswith("trig") for q in queries)
    assert len({q["id"] for q in queries}) == len(queries)


def test_derive_unlabelled_queries_falls_back_to_description_when_no_triggers(gf):
    nodes = make_nodes("_root")
    cards = {"u:a": make_card("u:a", "_root", description="one two three four five six seven eight nine ten")}
    idx = gf.Index.from_cards(cards, nodes)
    queries, _ = CR.derive_unlabelled_queries(idx)
    assert len(queries) == 1
    assert queries[0]["query"] == "one two three four five six seven eight"  # first 8 words


# --------------------------------------------------------------------------- rendering
def test_render_markdown_reports_no_sibling_collisions_and_no_changed_cards(gf, metrics_mod):
    base_idx, head_idx = _no_change_pair(gf)
    report = CR.compute_report(gf, metrics_mod, base_idx, head_idx, [], labelled=False, k=4)
    md = CR.render_markdown(report)
    assert "No same-node sibling collisions detected." in md
    assert "No skill cards changed between base and head." in md


# --------------------------------------------------------------------------- real end-to-end (no mocks)
def test_cli_end_to_end_against_the_real_fixture_base_equals_head(tmp_path):
    """Same invocation the CI job makes (git archive, real CLI load, real 220-query golden set),
    run as a subprocess against the tracked `examples/monorepo` fixture, base==head==HEAD so the
    only thing under test is the git-archive/_snapshot/CLI-loading plumbing itself -- no network,
    no mutation of the working tree (git-archive-into-tempdir is the whole point of `_snapshot.py`)."""
    out_json = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "authoring" / "collision_report.py"),
         "--root", str(FIXTURE_ROOT), "--base", "HEAD", "--head", "HEAD",
         "--queries", str(REPO_ROOT / "tests" / "golden" / "simple.yaml"),
         "--json", str(out_json)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(out_json.read_text())
    assert report["labelled"] is True
    assert report["n_changed_queries"] == 0   # base and head are the identical commit
    assert report["added"] == report["removed"] == report["changed"] == []
    for stats in report["metrics"].values():
        # n==0 (e.g. "simple" has no distractor-labelled cases) legitimately comes back NaN
        # (metrics.paired_delta_ci's documented n==0 contract) rather than 0.0.
        assert stats["mean_delta"] == 0.0 or (stats["n"] == 0 and math.isnan(stats["mean_delta"]))
