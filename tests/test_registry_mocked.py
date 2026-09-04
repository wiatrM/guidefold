"""Registry (Google Cloud Agent Registry backend) tests. Every gcloud call goes through the
fake_gcloud fixture (conftest.py) — subprocess.run inside the CLI module is monkeypatched, so
these tests never touch GCP. Assertions are made on the recorded argv, not on stdout."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from _helpers import call_kind


@pytest.fixture
def cfg(gf, fixture_root):
    return gf.load_map(fixture_root)


@pytest.fixture
def reg(gf, cfg):
    return gf.Registry(cfg)


# --------------------------------------------------------------------------------- search_scope
def test_search_scope_issues_one_prefix_query_per_top_level_segment(reg, fake_gcloud):
    nodes = ["atlas.identity.turnstile", "atlas.identity", "atlas", "_root"]
    fake_gcloud.rule(
        "skills", "search", "--search-type=keyword", "--query=skillId:private-meridian--atlas*",
        json_body=[
            {"skillId": "urn:skill:projects-1:locations:global:private-meridian--atlas-identity-turnstile--postgres-auth",
             "description": "[atlas/identity/turnstile] auth"},
            {"skillId": "urn:skill:projects-1:locations:global:private-meridian--atlas-geo--geospatial-indexing",
             "description": "[atlas/geo] not part of the wanted scope chain"},
        ],
    )
    fake_gcloud.rule(
        "skills", "search", "--search-type=keyword", "--query=skillId:private-meridian--root*",
        json_body=[
            {"skillId": "urn:skill:projects-1:locations:global:private-meridian--root--monorepo-conventions",
             "description": "[meridian] conventions"},
        ],
    )

    cards = reg.search_scope(nodes)

    assert {c["urn"] for c in cards} == {
        "urn:skill:meridian:atlas.identity.turnstile:postgres-auth",
        "urn:skill:meridian:_root:monorepo-conventions",
    }
    search_calls = [c for c in fake_gcloud.calls if call_kind(c) == "search"]
    assert len(search_calls) == 2  # one per distinct top-level segment: "atlas" and "root"


def test_search_scope_filters_out_hits_whose_node_is_unwanted(reg, fake_gcloud):
    """A hit can share the query's top-level prefix (both start with "atlas") yet still belong
    to a node that isn't in the requested scope chain; it must be dropped."""
    fake_gcloud.rule(
        "skills", "search", "--search-type=keyword", "--query=skillId:private-meridian--atlas*",
        json_body=[
            {"skillId": "urn:skill:projects-1:locations:global:private-meridian--atlas-geo--geospatial-indexing",
             "description": "[atlas/geo] geo indexing"},
        ],
    )
    cards = reg.search_scope(["atlas.identity.turnstile"])
    assert cards == []


# ------------------------------------------------------------------------------ search_semantic
def test_search_semantic_maps_results_to_cards(reg, fake_gcloud):
    fake_gcloud.rule(
        "skills", "search", "--search-type=semantic",
        json_body=[
            {"skillId": "urn:skill:projects-1:locations:global:private-meridian--atlas-identity-turnstile--postgres-auth",
             "description": "[atlas/identity/turnstile] auth"},
        ],
    )
    cards = reg.search_semantic("how do I add an auth check")
    assert len(cards) == 1
    assert cards[0]["urn"] == "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
    assert cards[0]["name"] == "postgres-auth"
    assert cards[0]["node"] == "atlas.identity.turnstile"


# ------------------------------------------------------------------------------------- download
def test_download_handles_flat_payload_layout(reg, fake_gcloud, tmp_path):
    rname = reg.registry_name("atlas.identity.turnstile", "postgres-auth")
    full = reg.full_name("atlas.identity.turnstile", "postgres-auth")
    fake_gcloud.rule("skills", "describe", rname, json_body={"defaultRevision": f"{full}/revisions/rev-flat"})

    def download_handler(cmd):
        dest = Path(next(a.split("=", 1)[1] for a in cmd if a.startswith("--destination=")))
        (dest / "SKILL.md").write_text("---\nname: postgres-auth\n---\nflat payload\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    fake_gcloud.rule("skills", "revisions", "download", handler=download_handler)

    dest = tmp_path / "out-flat"
    reg.download("urn:skill:meridian:atlas.identity.turnstile:postgres-auth", dest)
    assert (dest / "SKILL.md").read_text() == "---\nname: postgres-auth\n---\nflat payload\n"


def test_download_handles_nested_revision_id_payload_layout(reg, fake_gcloud, tmp_path):
    rname = reg.registry_name("atlas.identity.turnstile", "postgres-auth")
    full = reg.full_name("atlas.identity.turnstile", "postgres-auth")
    fake_gcloud.rule("skills", "describe", rname, json_body={"defaultRevision": f"{full}/revisions/rev-nested"})

    def download_handler(cmd):
        dest = Path(next(a.split("=", 1)[1] for a in cmd if a.startswith("--destination=")))
        nested = dest / "rev-nested"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "SKILL.md").write_text("---\nname: postgres-auth\n---\nnested payload\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    fake_gcloud.rule("skills", "revisions", "download", handler=download_handler)

    dest = tmp_path / "out-nested"
    reg.download("urn:skill:meridian:atlas.identity.turnstile:postgres-auth", dest)
    assert (dest / "SKILL.md").read_text() == "---\nname: postgres-auth\n---\nnested payload\n"


def test_download_with_no_default_revision_exits(reg, fake_gcloud):
    rname = reg.registry_name("atlas.identity.turnstile", "postgres-auth")
    fake_gcloud.rule("skills", "describe", rname, json_body={"defaultRevision": ""})
    with pytest.raises(SystemExit):
        reg.download("urn:skill:meridian:atlas.identity.turnstile:postgres-auth", Path("/tmp/unused"))


# -------------------------------------------------------------------------------------- publish
def test_publish_new_skill_issues_expected_call_sequence(reg, fixture_root, fake_gcloud):
    node, name = "atlas.identity.turnstile", "postgres-auth"
    skill_dir = fixture_root / "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth"
    rname = reg.registry_name(node, name)
    full = reg.full_name(node, name)
    rev_id = "rev-new-001"

    fake_gcloud.rule("skills", "describe", rname, returncode=1)      # not found -> brand new skill
    fake_gcloud.rule("skills", "create", returncode=0)
    fake_gcloud.rule("skills", "revisions", "create", returncode=0)
    fake_gcloud.rule("skills", "update", returncode=0)
    fake_gcloud.rule("skills", "revisions", "list", f"--skill={rname}",
                      json_body=[{"name": f"{full}/revisions/{rev_id}", "state": "ACTIVE",
                                  "createTime": "2026-09-04T00:00:00Z"}])

    reg.publish(node, name, skill_dir, display=f"{node}/{name}",
                desc="[atlas/identity/turnstile] test skill", rev_id=rev_id)

    kinds = [call_kind(c) for c in fake_gcloud.calls]
    assert kinds[0] == "describe"
    assert "create" in kinds
    assert (kinds.index("create") < kinds.index("revisions-create")
            < kinds.index("update-default-revision") < kinds.index("update-target-active"))


def test_publish_existing_skill_skips_create(reg, fixture_root, fake_gcloud):
    node, name = "atlas.identity.turnstile", "postgres-auth"
    skill_dir = fixture_root / "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth"
    rname = reg.registry_name(node, name)
    full = reg.full_name(node, name)
    display, desc, rev_id = f"{node}/{name}", "[atlas/identity/turnstile] test skill", "rev-existing-001"

    fake_gcloud.rule("skills", "describe", rname,
                      json_body={"description": desc[:2048], "displayName": display[:63],
                                 "targetState": "TARGET_STATE_ACTIVE"})
    fake_gcloud.rule("skills", "revisions", "create", returncode=0)
    fake_gcloud.rule("skills", "update", returncode=0)
    fake_gcloud.rule("skills", "revisions", "list", f"--skill={rname}",
                      json_body=[{"name": f"{full}/revisions/{rev_id}", "state": "ACTIVE",
                                  "createTime": "2026-09-04T00:00:00Z"}])

    reg.publish(node, name, skill_dir, display=display, desc=desc, rev_id=rev_id)

    kinds = [call_kind(c) for c in fake_gcloud.calls]
    assert "create" not in kinds
    assert "revisions-create" in kinds
    assert "update-default-revision" in kinds


def test_publish_prunes_failed_and_caps_at_keep_revisions(reg, fixture_root, fake_gcloud, gf):
    node, name = "atlas.identity.turnstile", "postgres-auth"
    skill_dir = fixture_root / "platforms/atlas/identity/turnstile/.agents/skills/postgres-auth"
    rname = reg.registry_name(node, name)
    full = reg.full_name(node, name)
    display, desc, rev_id = f"{node}/{name}", "[atlas/identity/turnstile] test skill", "rev-current"

    fake_gcloud.rule("skills", "describe", rname,
                      json_body={"description": desc[:2048], "displayName": display[:63],
                                 "targetState": "TARGET_STATE_ACTIVE"})
    fake_gcloud.rule("skills", "revisions", "create", returncode=0)
    fake_gcloud.rule("skills", "update", returncode=0)
    fake_gcloud.rule("skills", "revisions", "delete", returncode=0)

    failed = [{"name": f"{full}/revisions/rev-failed-{i}", "state": "FAILED",
               "createTime": f"2026-01-{i + 1:02d}T00:00:00Z"} for i in range(3)]
    old = [{"name": f"{full}/revisions/rev-old-{i:02d}", "state": "ACTIVE",
            "createTime": f"2026-02-{i + 1:02d}T00:00:00Z"} for i in range(25)]
    current = [{"name": f"{full}/revisions/{rev_id}", "state": "ACTIVE", "createTime": "2026-03-01T00:00:00Z"}]
    fake_gcloud.rule("skills", "revisions", "list", f"--skill={rname}", json_body=failed + old + current)

    reg.publish(node, name, skill_dir, display=display, desc=desc, rev_id=rev_id)

    delete_calls = [c for c in fake_gcloud.calls if call_kind(c) == "revisions-delete"]
    deleted_ids = {c[c.index("delete") + 1] for c in delete_calls}

    expected_failed = {f"rev-failed-{i}" for i in range(3)}
    # `old` is sorted ascending by createTime; oldest (25 - (KEEP_REVISIONS - 1)) = 6 get pruned
    # so that 19 old + 1 current == KEEP_REVISIONS survive.
    n_pruned_old = len(old) - (gf.KEEP_REVISIONS - 1)
    expected_pruned_old = {f"rev-old-{i:02d}" for i in range(n_pruned_old)}

    assert deleted_ids == expected_failed | expected_pruned_old
    assert len(deleted_ids) == len(expected_failed) + n_pruned_old
    # never delete the current revision or a kept-recent one
    assert rev_id not in deleted_ids
    assert "rev-old-24" not in deleted_ids
