import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "verify_annotation_packet.py"
spec = importlib.util.spec_from_file_location("verify_annotation_packet", MODULE)
verifier = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verifier)


FIELDS = list(verifier.FIELD_LABELS)


def _packet(tmp_path: Path, *, labels=None, evidence=None):
    root = tmp_path / "annotation_packet"
    packet = root / "packets" / "packet-01"
    packet.mkdir(parents=True)
    source = "one\ntwo\nthree\n"
    target = "target one\ntarget two\n"
    (packet / "source-1.md").write_text(source, encoding="utf-8")
    (packet / "target.md").write_text(target, encoding="utf-8")
    import hashlib
    sha = lambda value: hashlib.sha256(value.encode()).hexdigest()
    (packet / "packet.json").write_text(json.dumps({
        "packet_id": "packet-01", "fields": FIELDS,
        "source_files": {"source-1.md": {"sha256": sha(source), "line_count": 3}},
        "target_file": {"sha256": sha(target), "line_count": 2},
    }), encoding="utf-8")
    for reviewer in verifier.REVIEWERS:
        rows = []
        for field in FIELDS:
            row = {"field": field, "label": None, "evidence": [], "notes": ""}
            if labels is not None:
                row["label"] = labels[field]
                row["evidence"] = evidence or [{"file": "source-1.md", "start_line": 1, "end_line": 1}]
            rows.append(row)
        (packet / f"{reviewer}.json").write_text(json.dumps({
            "packet_id": "packet-01", "reviewer_id": reviewer, "labels": rows,
            "adjudication_complete": False,
        }), encoding="utf-8")
    (root / "annotation-manifest.json").write_text(json.dumps({
        "schema": "source-disjoint-urct-annotation-1",
        "status": "BLANK_TWO_REVIEWER_PACKET", "packets": [{"packet_id": "packet-01"}],
        "reviewers_per_packet": 2, "model_calls_allowed": False,
        "requires_adjudication": True,
    }), encoding="utf-8")
    return root


def test_blank_packet_is_valid_and_model_calls_are_disabled(tmp_path):
    report = verifier.verify(_packet(tmp_path), "blank")
    assert report["status"] == "BLANK_PACKET_VALID"
    assert report["errors"] == []


def test_annotated_packet_reports_disagreement_without_adjudicating(tmp_path):
    labels = {field: next(iter(verifier.FIELD_LABELS[field])) for field in FIELDS}
    root = _packet(tmp_path, labels=labels)
    second = root / "packets" / "packet-01" / "reviewer-2.json"
    data = json.loads(second.read_text(encoding="utf-8"))
    data["labels"][0]["label"] = "no" if labels["applicable"] != "no" else "yes"
    second.write_text(json.dumps(data), encoding="utf-8")
    report = verifier.verify(root, "annotated")
    assert report["status"] == "ANNOTATION_READY_FOR_ADJUDICATION"
    agreement = report["packets"][0]["agreement"]
    assert agreement["fields_compared"] == len(FIELDS)
    assert agreement["disagreements"] == 1


def test_annotated_packet_rejects_out_of_range_evidence(tmp_path):
    labels = {field: next(iter(verifier.FIELD_LABELS[field])) for field in FIELDS}
    root = _packet(tmp_path, labels=labels, evidence=[{"file": "source-1.md", "start_line": 2, "end_line": 9}])
    report = verifier.verify(root, "annotated")
    assert report["status"] == "FAIL"
    assert any("outside" in error for error in report["errors"])
