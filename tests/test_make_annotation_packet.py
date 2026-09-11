"""The source-disjoint annotation packet is reproducible and label-free."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "tools" / "pilot" / "make_annotation_packet.py"
    spec = importlib.util.spec_from_file_location("make_annotation_packet", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _record(family: str, role: str, root: Path) -> dict[str, str]:
    path = root / "snapshots" / family / f"{role}.SKILL.md"
    return {"record_id": f"{family}-{role}", "family_id": family, "role": role,
            "source_sha256": "", "snapshot_path": str(path)}


def test_build_creates_four_blank_packets_without_labels(tmp_path):
    module = _module()
    snapshot_root = tmp_path / "snapshots-root"
    records = []
    for family in ("engineering", "documentation"):
        for role in ("A", "B", "C", "C_prime"):
            path = snapshot_root / "snapshots" / family / f"{role}.SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {family} {role}\nsource\n", encoding="utf-8")
            records.append(_record(family, role, snapshot_root))
    manifest_path = tmp_path / "manifest.json"
    manifest = {"schema": "source-disjoint-urct-1", "status": "PREPARED_NOT_ANNOTATED",
                "families": ["engineering", "documentation"], "records": records}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "packet"

    result = module.build(manifest, manifest_path, snapshot_root, output)

    assert len(result["packets"]) == 4
    assert result["model_calls_allowed"] is False
    assert result["labels_are_blank"] is True
    for entry in result["packets"]:
        packet_dir = output / "packets" / entry["packet_id"]
        assert (packet_dir / "packet.json").is_file()
        for reviewer in module.REVIEWERS:
            review = json.loads((packet_dir / f"{reviewer}.json").read_text())
            assert review["adjudication_complete"] is False
            assert all(row["label"] is None and row["evidence"] == [] for row in review["labels"])
