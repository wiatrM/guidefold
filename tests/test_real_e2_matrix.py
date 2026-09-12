"""The source-backed E2 matrix keeps policy arms and source digests separate."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "tools" / "pilot" / "real_e2_matrix.py"
    spec = importlib.util.spec_from_file_location("real_e2_matrix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path: Path):
    snapshot = tmp_path / "snapshots"
    source = snapshot / "snapshots" / "family" / "C.SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# source\n", encoding="utf-8")
    module = _module()
    manifest = {
        "records": [{
            "record_id": "family-C",
            "family_id": "family",
            "role": "C",
            "source_sha256": module.sha256(source.read_bytes()),
        }],
    }
    return module, manifest, snapshot


def test_matrix_has_seventy_six_harmful_cases_and_safe_load(tmp_path):
    module, manifest, snapshot = _fixture(tmp_path)

    candidate = module.build(manifest, snapshot, "map+gate+evolution")
    flat = module.build(manifest, snapshot, "flat")

    assert len(candidate) == len(flat) == 20
    assert sum(row["harmful"] for row in candidate) == 19
    assert sum(row["harmful"] and row["actual_action"] == "LOAD" for row in candidate) == 0
    assert sum(row["harmful"] and row["actual_action"] == "LOAD" for row in flat) == 19
    assert candidate[-1]["actual_action"] == "LOAD"


def test_matrix_rejects_tampered_snapshot(tmp_path):
    module, manifest, snapshot = _fixture(tmp_path)
    source = snapshot / "snapshots" / "family" / "C.SKILL.md"
    source.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot digest mismatch"):
        module.build(manifest, snapshot, "map+gate+evolution")
