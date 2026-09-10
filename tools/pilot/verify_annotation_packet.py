#!/usr/bin/env python3
"""Verify the blinded URCT annotation packet before it is used by E2.

The command has two intentionally separate modes:

* ``blank`` checks that the packet is intact and contains no labels or model
  output before independent human review.
* ``annotated`` checks that both reviewers supplied complete, allowed labels
  with line-bounded evidence and reports inter-reviewer agreement.  It does
  not adjudicate disagreements and never converts them into gold labels.

The packet format is the local ``source-disjoint-urct-annotation-1`` format.
This verifier is a readiness/integrity gate, not a semantic judge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


FIELD_LABELS: dict[str, set[str]] = {
    "applicable": {"yes", "no", "unclear"},
    "revision_current": {"yes", "no", "unknown"},
    "scope_valid": {"yes", "no", "unclear"},
    "closure_complete": {"yes", "no", "unknown"},
    "semantically_useful": {"yes", "no", "unclear"},
    "should_ask": {"yes", "no", "unclear"},
}
REVIEWERS = ("reviewer-1", "reviewer-2")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _line_count(path: Path) -> int:
    # splitlines() matches the line_count recorded by the packet generator and
    # does not invent an extra line for a trailing newline.
    return len(path.read_text(encoding="utf-8").splitlines())


def _validate_evidence(
    evidence: Any,
    *,
    packet_dir: Path,
    allowed_files: dict[str, int],
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(evidence, list):
        _fail(errors, f"{location}: evidence must be a list")
        return
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            _fail(errors, f"{location}[{index}]: evidence must be an object")
            continue
        filename = item.get("file")
        start = item.get("start_line")
        end = item.get("end_line")
        if not isinstance(filename, str) or filename not in allowed_files:
            _fail(errors, f"{location}[{index}]: file is not in this packet")
            continue
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            _fail(errors, f"{location}[{index}]: start_line/end_line must be integers")
            continue
        if start < 1 or end < start or end > allowed_files[filename]:
            _fail(errors, f"{location}[{index}]: line range is outside {filename}")
        if not (packet_dir / filename).is_file():
            _fail(errors, f"{location}[{index}]: referenced file is missing")


def _validate_packet(packet_root: Path, packet_entry: dict[str, Any], mode: str, errors: list[str]) -> dict[str, Any]:
    packet_id = packet_entry.get("packet_id")
    packet_dir = packet_root / "packets" / str(packet_id)
    spec_path = packet_dir / "packet.json"
    if not spec_path.is_file():
        _fail(errors, f"{packet_id}: packet.json is missing")
        return {"packet_id": packet_id, "agreement": None}
    spec = _read(spec_path)
    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields or any(field not in FIELD_LABELS for field in fields):
        _fail(errors, f"{packet_id}: fields are not the canonical annotation fields")
        return {"packet_id": packet_id, "agreement": None}
    allowed_files: dict[str, int] = {}
    for filename, meta in (spec.get("source_files") or {}).items():
        if not isinstance(meta, dict) or not isinstance(meta.get("line_count"), int):
            _fail(errors, f"{packet_id}: invalid source file metadata for {filename}")
            continue
        allowed_files[filename] = meta["line_count"]
        path = packet_dir / filename
        if not path.is_file():
            _fail(errors, f"{packet_id}: source file {filename} is missing")
        elif _sha(path) != meta.get("sha256"):
            _fail(errors, f"{packet_id}: source file {filename} hash mismatch")
    target_meta = spec.get("target_file")
    if not isinstance(target_meta, dict) or not isinstance(target_meta.get("line_count"), int):
        _fail(errors, f"{packet_id}: invalid target file metadata")
    else:
        allowed_files["target.md"] = target_meta["line_count"]
        target_path = packet_dir / "target.md"
        if not target_path.is_file():
            _fail(errors, f"{packet_id}: target.md is missing")
        elif _sha(target_path) != target_meta.get("sha256"):
            _fail(errors, f"{packet_id}: target.md hash mismatch")

    labels_by_reviewer: dict[str, dict[str, str]] = {}
    for reviewer in REVIEWERS:
        path = packet_dir / f"{reviewer}.json"
        if not path.is_file():
            _fail(errors, f"{packet_id}: {reviewer}.json is missing")
            continue
        review = _read(path)
        if review.get("packet_id") != packet_id or review.get("reviewer_id") != reviewer:
            _fail(errors, f"{packet_id}: reviewer identity mismatch in {reviewer}.json")
        rows = review.get("labels")
        if (not isinstance(rows, list) or len(rows) != len(fields)
                or {row.get("field") for row in rows if isinstance(row, dict)} != set(fields)):
            _fail(errors, f"{packet_id}: {reviewer} does not label each field exactly once")
            continue
        labels: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                _fail(errors, f"{packet_id}: {reviewer} has a non-object label row")
                continue
            field = row.get("field")
            label = row.get("label")
            if mode == "blank":
                if label is not None or row.get("evidence") not in ([], None) or row.get("notes", ""):
                    _fail(errors, f"{packet_id}: {reviewer} is not blank for {field}")
            else:
                if not isinstance(label, str) or label not in FIELD_LABELS.get(str(field), set()):
                    _fail(errors, f"{packet_id}: {reviewer} has an invalid label for {field}")
                else:
                    labels[str(field)] = label
                _validate_evidence(row.get("evidence"), packet_dir=packet_dir, allowed_files=allowed_files,
                                   location=f"{packet_id}/{reviewer}/{field}/evidence", errors=errors)
        if mode == "blank" and review.get("adjudication_complete") is not False:
            _fail(errors, f"{packet_id}: {reviewer} must not be adjudicated in blank mode")
        labels_by_reviewer[reviewer] = labels

    agreement = None
    if mode == "annotated" and all(reviewer in labels_by_reviewer for reviewer in REVIEWERS):
        compared = [field for field in fields if field in labels_by_reviewer["reviewer-1"] and field in labels_by_reviewer["reviewer-2"]]
        matches = sum(labels_by_reviewer["reviewer-1"][field] == labels_by_reviewer["reviewer-2"][field] for field in compared)
        agreement = {"fields_compared": len(compared), "matches": matches,
                     "disagreements": len(compared) - matches,
                     "raw_agreement": matches / len(compared) if compared else None}
    return {"packet_id": packet_id, "agreement": agreement}


def verify(packet_root: Path, mode: str) -> dict[str, Any]:
    manifest_path = packet_root / "annotation-manifest.json"
    errors: list[str] = []
    if not manifest_path.is_file():
        return {"status": "FAIL", "mode": mode, "errors": ["annotation-manifest.json is missing"]}
    manifest = _read(manifest_path)
    if manifest.get("schema") != "source-disjoint-urct-annotation-1":
        _fail(errors, "unsupported annotation packet schema")
    if manifest.get("model_calls_allowed") is not False:
        _fail(errors, "model calls must remain disabled while annotating")
    if manifest.get("reviewers_per_packet") != 2 or manifest.get("requires_adjudication") is not True:
        _fail(errors, "packet must require two reviewers and adjudication")
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        _fail(errors, "manifest has no packets")
        packets = []
    results = [_validate_packet(packet_root, entry, mode, errors) for entry in packets if isinstance(entry, dict)]
    if errors:
        status = "FAIL"
    elif mode == "blank":
        status = "BLANK_PACKET_VALID"
    else:
        status = "ANNOTATION_READY_FOR_ADJUDICATION"
    return {"status": status, "mode": mode, "packet_count": len(results),
            "manifest_sha256": _sha(manifest_path), "packets": results, "errors": errors,
            "model_calls_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True, help="annotation_packet directory")
    parser.add_argument("--mode", choices=("blank", "annotated"), required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = verify(args.packet, args.mode)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
