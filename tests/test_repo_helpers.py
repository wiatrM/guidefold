import pytest


def test_repo_root_via_env_var(gf, fixture_root, monkeypatch):
    monkeypatch.setenv("GUIDEFOLD_ROOT", str(fixture_root))
    assert gf.repo_root() == fixture_root.resolve()


def test_repo_root_via_ancestor_walk(gf, fixture_root, monkeypatch):
    monkeypatch.delenv("GUIDEFOLD_ROOT", raising=False)
    monkeypatch.chdir(fixture_root / "platforms" / "atlas" / "identity" / "turnstile")
    assert gf.repo_root() == fixture_root.resolve()


def test_rel_returns_forward_slash_relative_path(gf, fixture_root):
    p = fixture_root / "platforms" / "atlas" / "geo"
    assert gf.rel(fixture_root, p) == "platforms/atlas/geo"


@pytest.mark.parametrize("relpath, expected_node", [
    ("platforms/atlas/identity/turnstile/src/auth", "atlas.identity.turnstile"),
    ("platforms/atlas/identity/rbac", "atlas.identity"),
    ("platforms/atlas/geo/tiles", "atlas.geo"),
    ("libs/auth-sdk/go", "shared.auth-sdk"),   # hyphenated node name on purpose (CLAUDE.md)
    ("libs/db", "shared"),
    ("some/totally/unmapped/path", "_root"),
])
def test_node_for_longest_glob_wins(gf, fixture_root, relpath, expected_node):
    cfg = gf.load_map(fixture_root)
    assert gf.node_for(cfg, relpath) == expected_node


def test_ancestors_chain_for_nested_node(gf):
    assert gf.ancestors("atlas.identity.turnstile") == [
        "atlas.identity.turnstile", "atlas.identity", "atlas", "_root",
    ]


def test_ancestors_chain_for_root(gf):
    assert gf.ancestors("_root") == ["_root"]
