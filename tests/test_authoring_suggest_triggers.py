"""Tests for tools/authoring/suggest_triggers.py — authoring loop, part 1, deliverable #2
(docs/MVP.md §5 "3-6 authoring loop": "F5 trigger/negative-trigger suggestions in `validate`
(owner approves in the PR)").

`suggestions_for` is the pure(ish) core: it takes two already-built `Index` snapshots (built here
with `Index.from_cards`, no git and no filesystem tree) plus the real `tools/enrich/derive.py`
module (never a reimplementation of its extraction rules) and returns suggestions only — nothing
here ever writes a SKILL.md. The synthetic skill bodies below use the exact heading patterns
`derive.py`'s `USAGE_HEADING_RE`/`EXCLUSION_HEADING_RE` match ("## When to Use This Skill" /
"## When NOT to Use This Skill"), same as `tests/test_enrich_derive.py`'s own fixtures.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from _router_helpers import make_card, make_nodes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ST = _load("gf_test_suggest_triggers", "tools/authoring/suggest_triggers.py")


@pytest.fixture(scope="module")
def derive_mod():
    return ST.load_derive_module()


BODY_BOTH_SECTIONS = (
    "## When to Use This Skill\n\n"
    "- Use when the user asks for beta gadget provisioning\n"
    "- Use when the user wants beta gadget connection pooling tuned\n\n"
    "## When NOT to Use This Skill\n\n"
    "- Do not use for alpha widget setup\n"
)

BODY_NO_SECTIONS = "This skill does routine maintenance work with no particular trigger cues.\n"


# --------------------------------------------------------------------------- load_derive_module
def test_load_derive_module_returns_the_real_f5_extractor():
    mod = ST.load_derive_module()
    assert callable(mod.derive)
    # sanity: it is the actual module, not a stub -- the module docstring names family F5.
    assert "F5" in mod.__doc__


# --------------------------------------------------------------------------- find_evidence_line
def test_find_evidence_line_locates_the_source_bullet():
    line = ST.find_evidence_line(BODY_BOTH_SECTIONS, "the user asks for beta gadget provisioning")
    assert line == "- Use when the user asks for beta gadget provisioning"


def test_find_evidence_line_falls_back_when_nothing_matches():
    assert ST.find_evidence_line(BODY_NO_SECTIONS, "totally unrelated phrase xyz") == \
        "(no evidence line found)"


def test_find_evidence_line_truncates_long_lines():
    long_line = "- " + ("widget " * 100) + "provisioning"
    line = ST.find_evidence_line(long_line, "widget provisioning")
    assert len(line) <= 200


# --------------------------------------------------------------------------- build_skill_dicts
def test_build_skill_dicts_matches_index_cards(gf):
    nodes = make_nodes("_root")
    cards = {
        "u:a": make_card("u:a", "_root", description="desc a", body="body a",
                          triggers=["t1"], requires=["u:b"]),
        "u:b": make_card("u:b", "_root", description="desc b", body="body b"),
    }
    idx = gf.Index.from_cards(cards, nodes)
    skills = ST.build_skill_dicts(idx)
    assert [s["id"] for s in skills] == ["u:a", "u:b"]   # sorted-URN order
    a = next(s for s in skills if s["id"] == "u:a")
    assert a["description"] == "desc a"
    assert a["body"] == "body a"
    assert a["triggers"] == ["t1"]
    assert a["requires"] == ["u:b"]
    b = next(s for s in skills if s["id"] == "u:b")
    assert b["triggers"] == [] and b["negative_triggers"] == []


# --------------------------------------------------------------------------- render_frontmatter_block
def test_render_frontmatter_block_both_fields():
    block = ST.render_frontmatter_block(["a phrase", "b phrase"], ["c phrase"])
    assert block == 'metadata:\n  triggers: "a phrase, b phrase"\n  negative_triggers: "c phrase"'


def test_render_frontmatter_block_triggers_only():
    block = ST.render_frontmatter_block(["a phrase"], [])
    assert block == 'metadata:\n  triggers: "a phrase"'


def test_render_frontmatter_block_negative_only():
    block = ST.render_frontmatter_block([], ["c phrase"])
    assert block == 'metadata:\n  negative_triggers: "c phrase"'


def test_render_frontmatter_block_empty_is_bare_key():
    assert ST.render_frontmatter_block([], []) == "metadata:"


# --------------------------------------------------------------------------- suggestions_for
def test_suggestions_for_new_skill_missing_both_fields(gf, derive_mod):
    nodes = make_nodes("_root")
    base_cards = {"u:a": make_card("u:a", "_root", description="alpha widget setup",
                                    triggers=["alpha widget setup"])}
    head_cards = dict(base_cards)
    head_cards["u:b"] = make_card("u:b", "_root", description="beta gadget provisioning",
                                   body=BODY_BOTH_SECTIONS)
    base_idx = gf.Index.from_cards(base_cards, nodes)
    head_idx = gf.Index.from_cards(head_cards, nodes)

    suggestions = ST.suggestions_for(head_idx, base_idx, derive_mod)

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["urn"] == "u:b" and s["node"] == "_root"
    assert s["missing_triggers"] is True and s["missing_negative_triggers"] is True
    assert s["found_nothing"] is False
    assert "the user asks for beta gadget provisioning" in s["suggested_triggers"]
    assert "the user wants beta gadget connection pooling tuned" in s["suggested_triggers"]
    assert s["suggested_negative_triggers"], "exclusion section should have produced a negative_trigger"
    for phrase in s["suggested_triggers"] + s["suggested_negative_triggers"]:
        assert phrase in s["evidence"]
        assert s["evidence"][phrase] != "(no evidence line found)"
    assert s["frontmatter_block"].startswith("metadata:\n  triggers:")
    assert "negative_triggers:" in s["frontmatter_block"]
    # u:a is untouched base->head and already has triggers -- never a suggestion target.
    assert all(x["urn"] != "u:a" for x in suggestions)


def test_suggestions_for_only_missing_field_is_suggested(gf, derive_mod):
    """A changed skill that already has `triggers` but is missing `negative_triggers` gets
    suggestions for the missing field only -- `triggers` is never touched or re-suggested."""
    nodes = make_nodes("_root")
    base_cards = {"u:c": make_card("u:c", "_root", description="gamma widget",
                                    triggers=["gamma widget already set"], body=BODY_BOTH_SECTIONS)}
    head_cards = {"u:c": make_card("u:c", "_root", description="gamma widget changed",
                                    triggers=["gamma widget already set"], body=BODY_BOTH_SECTIONS)}
    base_idx = gf.Index.from_cards(base_cards, nodes)
    head_idx = gf.Index.from_cards(head_cards, nodes)

    suggestions = ST.suggestions_for(head_idx, base_idx, derive_mod)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["missing_triggers"] is False
    assert s["missing_negative_triggers"] is True
    assert s["suggested_triggers"] == []
    assert s["suggested_negative_triggers"]
    assert "triggers:" not in s["frontmatter_block"] or "negative_triggers:" in s["frontmatter_block"]
    assert "  triggers:" not in s["frontmatter_block"]


def test_suggestions_for_found_nothing_when_body_has_no_usage_material(gf, derive_mod):
    nodes = make_nodes("_root")
    base_cards = {}
    head_cards = {"u:d": make_card("u:d", "_root", description="delta service",
                                    body=BODY_NO_SECTIONS)}
    base_idx = gf.Index.from_cards(base_cards, nodes)
    head_idx = gf.Index.from_cards(head_cards, nodes)

    suggestions = ST.suggestions_for(head_idx, base_idx, derive_mod)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["found_nothing"] is True
    assert s["suggested_triggers"] == [] and s["suggested_negative_triggers"] == []


def test_suggestions_for_no_targets_returns_empty_list(gf, derive_mod):
    nodes = make_nodes("_root")
    cards = {"u:a": make_card("u:a", "_root", description="alpha", triggers=["t"], negative_triggers=["n"])}
    base_idx = gf.Index.from_cards(cards, nodes)
    head_idx = gf.Index.from_cards(dict(cards), nodes)
    assert ST.suggestions_for(head_idx, base_idx, derive_mod) == []


# --------------------------------------------------------------------------- render_markdown
def test_render_markdown_empty_suggestions():
    md = ST.render_markdown([])
    assert "No added or changed skill is missing" in md


def test_render_markdown_renders_paste_block_and_evidence():
    suggestions = [{
        "urn": "u:b", "node": "_root",
        "missing_triggers": True, "missing_negative_triggers": False,
        "suggested_triggers": ["a phrase"], "suggested_negative_triggers": [],
        "evidence": {"a phrase": "- Use when a phrase happens"},
        "frontmatter_block": 'metadata:\n  triggers: "a phrase"',
        "found_nothing": False,
    }]
    md = ST.render_markdown(suggestions)
    assert "`u:b`" in md
    assert "```yaml" in md and 'metadata:\n  triggers: "a phrase"' in md
    assert "trigger `a phrase` <- \"- Use when a phrase happens\"" in md


def test_render_markdown_renders_found_nothing_guidance():
    suggestions = [{
        "urn": "u:d", "node": "_root",
        "missing_triggers": True, "missing_negative_triggers": True,
        "suggested_triggers": [], "suggested_negative_triggers": [],
        "evidence": {}, "frontmatter_block": "metadata:", "found_nothing": True,
    }]
    md = ST.render_markdown(suggestions)
    assert "found no usage or exclusion material" in md
