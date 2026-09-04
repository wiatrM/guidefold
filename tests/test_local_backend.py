"""LocalRegistry (registry.backend: local) tests against the read-only Meridian fixture."""
import pytest


@pytest.fixture
def cfg(gf, fixture_root):
    return gf.load_map(fixture_root)


@pytest.fixture
def local_reg(gf, cfg, fixture_root):
    return gf.LocalRegistry(cfg, fixture_root)


def test_search_scope_returns_only_the_wanted_node(local_reg):
    cards = local_reg.search_scope(["atlas.identity.turnstile"])
    assert {c["name"] for c in cards} == {"postgres-auth", "turnstile-oncall-runbook"}
    assert all(c["node"] == "atlas.identity.turnstile" for c in cards)
    assert all(c["registry"].startswith("local:") for c in cards)


def test_search_scope_across_multiple_nodes(local_reg):
    cards = local_reg.search_scope(["atlas.geo", "security.audit"])
    assert {c["name"] for c in cards} == {"geospatial-indexing", "map-tile-serving", "audit-logging"}


def test_search_scope_unknown_node_returns_nothing(local_reg):
    assert local_reg.search_scope(["does.not.exist"]) == []


def test_search_semantic_finds_relevant_skill(local_reg):
    cards = local_reg.search_semantic("legacyAuthMode postgres bearer token authorization")
    assert "postgres-auth" in [c["name"] for c in cards]


def test_search_semantic_no_match_returns_empty(local_reg):
    assert local_reg.search_semantic("zzz_no_such_term_anywhere_xyz") == []


def test_download_copies_skill_directory(local_reg, fixture_root, tmp_path):
    dest = tmp_path / "downloaded"
    local_reg.download("urn:skill:meridian:atlas.identity.turnstile:postgres-auth", dest)
    src = fixture_root / "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth/SKILL.md"
    assert (dest / "SKILL.md").read_text() == src.read_text()


def test_download_overwrites_existing_destination(local_reg, tmp_path):
    dest = tmp_path / "downloaded"
    dest.mkdir()
    (dest / "stale.txt").write_text("leftover from a previous download")
    local_reg.download("urn:skill:meridian:atlas.identity.turnstile:postgres-auth", dest)
    assert (dest / "SKILL.md").exists()
    assert not (dest / "stale.txt").exists()


def test_download_unknown_urn_exits(local_reg):
    with pytest.raises(SystemExit):
        local_reg.download("urn:skill:meridian:_root:does-not-exist", None)


def test_publish_is_a_noop_that_exits(local_reg):
    with pytest.raises(SystemExit):
        local_reg.publish()
