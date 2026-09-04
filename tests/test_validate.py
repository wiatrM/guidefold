import pytest

from _helpers import build_tmp_repo, write_guidefold_yaml, write_skill


def _run_validate(gf, root):
    """Call cmd_validate the way main() does and return (exit_code, printed_output)."""
    cfg = gf.load_map(root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_validate(None, root, cfg)
    return exc.value.code


def test_validate_passes_on_fixture(gf, fixture_root, capsys):
    code = _run_validate(gf, fixture_root)
    out = capsys.readouterr().out
    assert code == 0
    assert "26 skills, 0 errors" in out


def test_validate_passes_on_freshly_built_tmp_repo(gf, tmp_path):
    root = build_tmp_repo(tmp_path / "acme")
    code = _run_validate(gf, root)
    assert code == 0


def test_name_mismatches_directory(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="not-widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform", "status": "active"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "name != directory" in out


def test_wrong_metadata_scope(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "teamA", "owner": "platform", "status": "active"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "metadata.scope=teamA but path node=_root" in out


def test_disallowed_owner(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "some-other-team", "status": "active"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "owner some-other-team not allowed for node _root" in out


def test_non_scalar_metadata_value(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                raw_metadata="  scope: _root\n  owner: platform\n  status: active\n  weird: [a, b]\n")
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "metadata.weird must be a scalar string" in out


def test_description_missing_node_tag(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="widget skill with no scope tag at all. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform", "status": "active"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "description must start with [acme]" in out


def test_unknown_requires(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform", "status": "active",
                          "requires": "urn:skill:acme:_root:does-not-exist"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "requires unknown skill urn:skill:acme:_root:does-not-exist" in out


def test_missing_status(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "metadata.status must be active or deprecated" in out


def test_deprecated_without_replaced_by(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform", "status": "deprecated"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "deprecated skill must set metadata.replaced_by" in out


def test_broken_reference_path(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/widget", name="widget",
                description="[acme] widget skill. Use when touching widgets.",
                metadata={"scope": "_root", "owner": "platform", "status": "active",
                          "references": "does/not/exist.md"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "reference not found: does/not/exist.md" in out


def test_requires_cycle_detected(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(root / ".agents/skills/alpha", name="alpha",
                description="[acme] alpha skill. Use for alpha things.",
                metadata={"scope": "_root", "owner": "platform", "status": "active",
                          "requires": "urn:skill:acme:_root:beta"})
    write_skill(root / ".agents/skills/beta", name="beta",
                description="[acme] beta skill. Use for beta things.",
                metadata={"scope": "_root", "owner": "platform", "status": "active",
                          "requires": "urn:skill:acme:_root:alpha"})
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "requires cycle:" in out


def test_two_nodes_collide_after_flat_node(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    nodes = {
        "_root": {"paths": ["**"], "owner": "platform"},
        "foo.bar": {"paths": ["foo/bar/**"], "owner": "platform"},
        "foo-bar": {"paths": ["foobar/**"], "owner": "platform"},
    }
    write_guidefold_yaml(root, nodes=nodes)
    code = _run_validate(gf, root)
    out = capsys.readouterr().out
    assert code == 1
    assert "collide after flattening to 'foo-bar'" in out
