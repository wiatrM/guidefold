import pytest


def test_urn_format(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    u = gf.urn(cfg, "atlas.identity.turnstile", "postgres-auth")
    assert u == "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"


def test_parse_urn_round_trip(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    u = gf.urn(cfg, "shared.auth-sdk", "auth-sdk-usage")
    assert gf.parse_urn(u) == ("meridian", "shared.auth-sdk", "auth-sdk-usage")


def test_parse_urn_rejects_malformed_string(gf):
    with pytest.raises(SystemExit):
        gf.parse_urn("not-a-urn-at-all")


def test_parse_urn_rejects_wrong_scheme(gf):
    with pytest.raises(SystemExit):
        gf.parse_urn("urn:agent:meridian:atlas:foo")


@pytest.mark.parametrize("node, expected", [
    ("_root", "root"),
    ("atlas.identity.turnstile", "atlas-identity-turnstile"),
    ("shared.auth-sdk", "shared-auth-sdk"),
])
def test_flat_node(gf, node, expected):
    assert gf.flat_node(node) == expected


def test_registry_resource_id_registry_name_full_name(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    reg = gf.Registry(cfg)
    assert reg.resource_id("atlas.identity.turnstile", "postgres-auth") == \
        "meridian--atlas-identity-turnstile--postgres-auth"
    assert reg.registry_name("atlas.identity.turnstile", "postgres-auth") == \
        "private-meridian--atlas-identity-turnstile--postgres-auth"
    assert reg.full_name("atlas.identity.turnstile", "postgres-auth") == (
        f"projects/{cfg['registry']['project']}/locations/{cfg['registry'].get('location', 'global')}"
        "/skills/private-meridian--atlas-identity-turnstile--postgres-auth"
    )


def test_to_logical_maps_known_flat_node(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    reg = gf.Registry(cfg)
    rid = reg.registry_name("atlas.identity.turnstile", "postgres-auth")
    result = reg.to_logical({
        "skillId": f"urn:skill:projects-777:locations:global:{rid}",
        "description": "[atlas/identity/turnstile] add or change authorization checks",
    })
    assert result == (
        gf.urn(cfg, "atlas.identity.turnstile", "postgres-auth"),
        "atlas.identity.turnstile",
        "postgres-auth",
    )


def test_to_logical_none_for_foreign_skill(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    reg = gf.Registry(cfg)
    assert reg.to_logical({
        "skillId": "urn:skill:projects-1:locations:global:private-othervendor--atlas--foo",
        "description": "irrelevant, wrong publisher prefix",
    }) is None


def test_to_logical_description_tag_fallback_for_node(gf, fixture_root):
    """An unmapped flat segment (skillId doesn't match any current node) falls back to parsing
    the [node/path] tag out of the description."""
    cfg = gf.load_map(fixture_root)
    reg = gf.Registry(cfg)
    rid = "private-meridian--unmapped-flat--some-skill"
    result = reg.to_logical({
        "skillId": f"urn:skill:projects-1:locations:global:{rid}",
        "description": "[atlas/identity] some skill only findable via its description tag",
    })
    assert result == ("urn:skill:meridian:atlas.identity:some-skill", "atlas.identity", "some-skill")


def test_to_logical_description_tag_fallback_resolves_publisher_tag_to_root(gf, fixture_root):
    """The root-level description tag is just [<publisher>] (CLAUDE.md naming rule), which the
    fallback must resolve to node "_root", not a literal node called "meridian"."""
    cfg = gf.load_map(fixture_root)
    reg = gf.Registry(cfg)
    rid = "private-meridian--unmapped-flat--org-wide-skill"
    result = reg.to_logical({
        "skillId": f"urn:skill:projects-1:locations:global:{rid}",
        "description": "[meridian] some root-level skill",
    })
    assert result == ("urn:skill:meridian:_root:org-wide-skill", "_root", "org-wide-skill")
