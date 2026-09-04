import pytest


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
