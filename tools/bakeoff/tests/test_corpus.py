"""Tests for corpus.py -- loading the Meridian fixture into SkillRecord objects."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from corpus import load_corpus  # noqa: E402


def test_loads_expected_skill_count():
    corpus = load_corpus()
    # 26 real SKILL.md files under examples/monorepo, excluding the generated hierarchy-index.
    assert len(corpus) == 26


def test_excludes_generated_hierarchy_index():
    corpus = load_corpus()
    names = {r.name for r in corpus}
    urns = {r.urn for r in corpus}
    assert "hierarchy-index" not in names
    assert not any("hierarchy-index" in u for u in urns)


def test_includes_known_deprecated_skill_with_status_flag():
    corpus = load_corpus()
    by_urn = {r.urn: r for r in corpus}
    deprecated = [r for r in corpus if r.status == "deprecated"]
    assert len(deprecated) == 1
    assert deprecated[0].urn == "urn:skill:meridian:atlas.identity:legacy-session-auth"
    assert deprecated[0].replaced_by  # points at its replacement, whatever the exact URN spelling


def test_records_are_sorted_by_urn():
    corpus = load_corpus()
    urns = [r.urn for r in corpus]
    assert urns == sorted(urns)


def test_urns_are_unique():
    corpus = load_corpus()
    urns = [r.urn for r in corpus]
    assert len(urns) == len(set(urns))


def test_fields_text_has_five_named_fields():
    corpus = load_corpus()
    sample = corpus[0]
    fields = sample.fields_text()
    assert set(fields) == {"name", "description", "digest", "triggers", "body"}
    assert all(isinstance(v, str) for v in fields.values())


def test_concat_text_contains_name_and_description():
    corpus = load_corpus()
    for r in corpus:
        concat = r.concat_text()
        assert r.name in concat
        if r.description:
            assert r.description in concat
