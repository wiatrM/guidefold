import pytest
import yaml


def test_frontmatter_parses(gf, fixture_root):
    md = fixture_root / "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth/SKILL.md"
    fm = gf.frontmatter(md)
    assert fm["name"] == "postgres-auth"
    assert fm["metadata"]["scope"] == "atlas.identity.turnstile"
    assert fm["metadata"]["owner"] == "turnstile-team"


def test_frontmatter_returns_empty_dict_without_marker(gf, tmp_path):
    md = tmp_path / "PLAIN.md"
    md.write_text("# Just a heading\n\nNo frontmatter block here at all.\n")
    assert gf.frontmatter(md) == {}


@pytest.mark.parametrize("fields", [
    "source_proof:\n  body_sha256: 0\n  body_sha256: pending\n",
    "metadata:\n  owner: first-team\n  owner: second-team\n",
])
def test_frontmatter_rejects_duplicate_mapping_keys(gf, tmp_path, fields):
    md = tmp_path / "DUPLICATE.md"
    md.write_text("---\nname: duplicate\ndescription: '[test] duplicate key'\n" + fields + "---\n")

    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        gf.frontmatter(md)


def test_frontmatter_allows_explicit_yaml_merge_override(gf, tmp_path):
    md = tmp_path / "MERGED.md"
    md.write_text(
        "---\nname: merged\ndescription: '[test] YAML merge'\n"
        "defaults: &defaults\n  owner: base-team\n"
        "metadata:\n  <<: *defaults\n  owner: local-team\n---\n"
    )

    assert gf.frontmatter(md)["metadata"]["owner"] == "local-team"


@pytest.mark.parametrize("value, expected", [
    ("a.md, b.md,c.md", ["a.md", "b.md", "c.md"]),
    ("single.md", ["single.md"]),
    ("a.md b.md", ["a.md", "b.md"]),
])
def test_md_list_comma_or_whitespace_separated_string(gf, value, expected):
    assert gf.md_list({"references": value}, "references") == expected


def test_md_list_yaml_list(gf):
    assert gf.md_list({"references": ["a.md", "b.md"]}, "references") == ["a.md", "b.md"]


@pytest.mark.parametrize("md", [{}, {"references": None}, {"references": ""}])
def test_md_list_empty_or_missing(gf, md):
    assert gf.md_list(md, "references") == []


# ---- md_phrases: triggers/negative_triggers are comma-separated PHRASES, not words (PR #7
# review, defect 1) — md_list's whitespace-splitting would shred "planned auth change" into
# ["planned", "auth", "change"], turning a precise two-phrase suppressor into a blanket
# single-word ban. md_phrases must split on commas only.
def test_md_phrases_preserves_multi_word_phrases(gf):
    v = "planned auth change, policy edit"
    assert gf.md_phrases({"negative_triggers": v}, "negative_triggers") == [
        "planned auth change", "policy edit",
    ]


def test_md_phrases_single_word_phrase(gf):
    assert gf.md_phrases({"triggers": "outage"}, "triggers") == ["outage"]


def test_md_phrases_yaml_list(gf):
    assert gf.md_phrases({"triggers": ["a b", "c"]}, "triggers") == ["a b", "c"]


@pytest.mark.parametrize("md", [{}, {"triggers": None}, {"triggers": ""}])
def test_md_phrases_empty_or_missing(gf, md):
    assert gf.md_phrases(md, "triggers") == []


def test_md_phrases_does_not_split_on_internal_whitespace_unlike_md_list(gf):
    v = "planned auth change, policy edit"
    # md_list (whitespace+comma) would shred this into 5 single-word entries -- proving the two
    # accessors diverge for exactly the input where it matters.
    assert gf.md_list({"x": v}, "x") == ["planned", "auth", "change", "policy", "edit"]
    assert gf.md_phrases({"x": v}, "x") == ["planned auth change", "policy edit"]


def test_negative_trigger_phrase_match_requires_the_whole_phrase_not_one_word(gf, fixture_root):
    """Regression test for the P1 defect: the real fixture's turnstile-oncall-runbook sets
    negative_triggers: "planned auth change, policy edit". A query containing the bare word
    "auth" (e.g. a real turnstile outage) must NOT hard-drop it -- only a query containing every
    word of one whole phrase may. Runs the real Index/Router end-to-end against the fixture."""
    cfg = gf.load_map(fixture_root)
    idx = gf.Index.build(fixture_root, cfg)
    router = gf.Router(idx)
    u = "urn:skill:meridian:atlas.identity.turnstile:turnstile-oncall-runbook"

    kept, drops = router.policy_filter("atlas.identity", "handle an outage in turnstile auth")
    assert u in kept
    assert u not in [d[0] for d in drops]

    # the full phrase "planned auth change" (every word present) still hard-drops it.
    kept2, drops2 = router.policy_filter("atlas.identity", "planned auth change for turnstile")
    assert u not in kept2
    assert (u, "negative-trigger:planned auth change") in drops2


def test_all_skills_finds_26_non_generated_skills(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    skills = list(gf.all_skills(fixture_root, cfg))
    assert len(skills) == 26
    names = {d.name for d, _, _ in skills}
    assert "hierarchy-index" not in names
    assert "postgres-auth" in names


def test_all_skills_includes_generated_only_when_asked(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    skills = list(gf.all_skills(fixture_root, cfg, include_generated=True))
    assert len(skills) == 27
    generated = [(d, node, fm) for d, node, fm in skills if d.name == "hierarchy-index"]
    assert len(generated) == 1
    _, node, fm = generated[0]
    assert node == "_index"
    assert fm["metadata"]["generated"] == "true"


# 2026-09-15 rehearsal: this repository is itself the self-use pilot's import source, so its own
# cards have to survive the importer. Ten `.agents/skills/*/SKILL.md` carried an unquoted ":" in
# `description:`; the importer failed each of them (`ScannerError`), the import finished
# `partial`, and `publish.build` then refused the whole snapshot with `import_partial` — no
# publication was possible from this repository at all. Claude Code's own loader is lenient
# enough to hide it, so only a check like this one catches it.
def test_every_skill_md_in_this_repository_has_parseable_frontmatter():
    import re
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    fm_re = re.compile(r"^---\n(.*?)\n---", re.S)
    broken = []
    for md in sorted(root.rglob(".agents/skills/*/SKILL.md")):
        if ".guidefold" in md.parts:
            continue
        m = fm_re.match(md.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            parsed = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            broken.append(f"{md.relative_to(root)}: {str(exc).splitlines()[0]}")
            continue
        if not isinstance(parsed, dict):
            broken.append(f"{md.relative_to(root)}: frontmatter is not a mapping")
    assert not broken, "SKILL.md frontmatter the importer would reject:\n" + "\n".join(broken)
