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
    for row in manifest["records"]:
        if row["role"] == "C_prime":
            assert "stop if the check is not green" in row["drift"]["append_text"]
            assert row["drift"]["before_sha256"] != row["drift"]["after_sha256"]
    for family in manifest["families"]:
        owners = {
            row["source_owner"]
            for row in manifest["records"]
            if row["family_id"] == family and row["role"] in {"A", "B", "C"}
        }
        assert len(owners) == 3
