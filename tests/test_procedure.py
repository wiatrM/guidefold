from types import SimpleNamespace

import pytest

from _helpers import write_guidefold_yaml, write_skill


def _run(gf, root, skill, **overrides):
    values = {"skill": str(skill), "run": False, "json": True}
    values.update(overrides)
    args = SimpleNamespace(**values)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_procedure(args, root, gf.load_map(root))
    return exc.value.code


def test_procedure_contract_and_local_verifier(gf, tmp_path, capsys):
    root = tmp_path / "repo"
    write_guidefold_yaml(root, nodes={"_root": {"paths": ["**"], "owner": "platform"}})
    verifier = root / "verify.py"
    verifier.write_text("print('verified')\n")
    skill = root / ".agents/skills/rotate/SKILL.md"
    write_skill(skill.parent, name="rotate",
                description="[acme] Rotation procedure. Use when rotating credentials.",
                metadata={"scope": "_root", "owner": "platform", "status": "active",
                          "verifier": "verify.py"},
                body=("# Rotate\n\n## Inputs\nsecret\n\n## Outputs\nrotated\n\n"
                      "## Preconditions\naccess\n\n## Steps\n1. Rotate\n\n"
                      "## Verification\nRun the verifier.\n"))
    assert _run(gf, root, skill, run=True) == 0
    out = capsys.readouterr().out
    assert '"status": "passed"' in out
    assert '"verifier_exit_code": 0' in out


def test_procedure_rejects_missing_sections(gf, tmp_path, capsys):
    root = tmp_path / "repo"
    write_guidefold_yaml(root, nodes={"_root": {"paths": ["**"], "owner": "platform"}})
    skill = root / ".agents/skills/weak/SKILL.md"
    write_skill(skill.parent, name="weak",
                description="[acme] Weak procedure. Use when checking a weak flow.",
                metadata={"scope": "_root", "owner": "platform", "status": "active"},
                body="# Weak\n\nNo steps.\n")
    assert _run(gf, root, skill) == 1
    out = capsys.readouterr().out
    assert "missing section: inputs" in out
    assert "steps section must contain at least one ordered step" in out
