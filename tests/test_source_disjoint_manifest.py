import json
from pathlib import Path


MANIFEST = Path(__file__).parents[1] / "docs" / "reports" / "bakeoff" / "SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json"


def test_source_disjoint_manifest_is_prepared_and_owner_disjoint():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] == "PREPARED_NOT_ANNOTATED"
    assert manifest["human_annotation"]["model_calls_allowed"] is False
    assert len(manifest["families"]) == 2
    assert len(manifest["records"]) == 8
    assert len(manifest["cases"]) == 4
    for family in manifest["families"]:
        owners = {
            row["source_owner"]
            for row in manifest["records"]
            if row["family_id"] == family and row["role"] in {"A", "B", "C"}
        }
        assert len(owners) == 3
