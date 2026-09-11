#!/usr/bin/env python3
"""Build a blank, source-disjoint C/C-prime annotation packet.

The input manifest and already verified snapshots are treated as immutable.  This
command copies only source text and creates blank reviewer forms; it never calls a
model and never creates a label or an evidence range.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA = "source-disjoint-urct-annotation-1"
FIELDS = [
    "applicable",
    "revision_current",
    "scope_valid",
    "closure_complete",
    "semantically_useful",
    "should_ask",
]
REVIEWERS = ("reviewer-1", "reviewer-2")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def blank_review(packet_id: str, reviewer_id: str) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "reviewer_id": reviewer_id,
        "adjudication_complete": False,
        "labels": [
            {"field": field, "label": None, "evidence": [], "notes": ""}
            for field in FIELDS
        ],
    }


def source_path(snapshot_root: Path, record: dict[str, Any]) -> Path:
    return snapshot_root / "snapshots" / record["family_id"] / f"{record['role']}.SKILL.md"


def build(manifest: dict[str, Any], manifest_path: Path, snapshot_root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    packet_entries: list[dict[str, Any]] = []
    for family_id in manifest["families"]:
        family = [record for record in manifest["records"] if record["family_id"] == family_id]
        by_role = {record["role"]: record for record in family}
        for role in ("C", "C_prime"):
            target = by_role[role]
            packet_id = f"{family_id}-{role}"
            packet_dir = output / "packets" / packet_id
            packet_dir.mkdir(parents=True, exist_ok=True)
            source_roles = ["A", "B"] if role == "C" else ["A", "B", "C"]
            source_meta: dict[str, dict[str, Any]] = {}
            for source_role in source_roles:
                record = by_role[source_role]
                source = source_path(snapshot_root, record)
                if not source.is_file():
                    raise FileNotFoundError(source)
                filename = f"source-{source_role}.md"
                shutil.copyfile(source, packet_dir / filename)
                source_meta[filename] = {
                    "record_id": record["record_id"],
                    "sha256": sha256(source),
                    "line_count": line_count(source),
                }
            target_source = source_path(snapshot_root, target)
            if not target_source.is_file():
                raise FileNotFoundError(target_source)
            target_path = packet_dir / "target.md"
            shutil.copyfile(target_source, target_path)
            packet_spec = {
                "packet_id": packet_id,
                "family_id": family_id,
                "target_record_id": target["record_id"],
                "target_role": role,
                "fields": FIELDS,
                "source_files": source_meta,
                "target_file": {
                    "record_id": target["record_id"],
                    "sha256": sha256(target_source),
                    "line_count": line_count(target_source),
                },
            }
            (packet_dir / "packet.json").write_text(
                json.dumps(packet_spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            for reviewer in REVIEWERS:
                (packet_dir / f"{reviewer}.json").write_text(
                    json.dumps(blank_review(packet_id, reviewer), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            packet_entries.append({
                "packet_id": packet_id,
                "family_id": family_id,
                "target_record_id": target["record_id"],
                "source_record_ids": [by_role[item]["record_id"] for item in source_roles],
            })

    annotation_manifest = {
        "schema": SCHEMA,
        "source_manifest_schema": manifest.get("schema"),
        "source_manifest_status": manifest.get("status"),
        "families": manifest["families"],
        "packets": packet_entries,
        "reviewers_per_packet": 2,
        "requires_adjudication": True,
        "model_calls_allowed": False,
        "labels_are_blank": True,
        "recorded_source_manifest_sha256": sha256(manifest_path),
    }
    (output / "annotation-manifest.json").write_text(
        json.dumps(annotation_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return annotation_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = build(manifest, args.manifest, args.snapshots, args.output)
    print(json.dumps({"status": "BLANK_PACKET_CREATED", "packets": len(result["packets"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
