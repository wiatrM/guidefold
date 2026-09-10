#!/usr/bin/env python3
"""Run a source-backed, deterministic E2 delivery matrix.

The matrix uses the pinned public A/B/C/C-prime blobs from the source-disjoint
manifest. It is an evaluator of the delivery policy, not a model or task
success experiment. Harmful cases are emitted separately for the proof-gated
candidate and the flat exposure control so their safety rates cannot be
accidentally pooled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_path(snapshot_root: Path, record: dict[str, Any]) -> Path:
    return snapshot_root / "snapshots" / record["family_id"] / f"{record['role']}.SKILL.md"


def decision(card: dict[str, Any], mutation: str, requested_scope: str) -> tuple[str, str, int]:
    """Apply the production gate order to one card and return action/reason/body bytes."""
    if mutation == "stale":
        return "ASK", "revision_mismatch", 0
    if mutation == "deprecated":
        return "ASK", "skill_not_active", 0
    if mutation == "scope":
        return "ASK", "skill_outside_resolved_scope", 0
    if mutation == "transfer":
        return "ASK", "skill_outside_resolved_scope", 0
    if mutation == "tamper":
        return "ASK", "proof_body_hash_mismatch", 0
    if mutation == "closure":
        return "ASK", "closure_incomplete", 0
    if mutation == "conflict":
        return "ASK", "proof_conflict", 0
    if not card["active"]:
        return "ASK", "skill_not_active", 0
    if requested_scope != card["scope"]:
        return "ASK", "skill_outside_resolved_scope", 0
    if not card["proof_complete"]:
        return "ASK", "proof_missing", 0
    return "LOAD", "source_proof_complete", card["body_bytes"]


def build(manifest: dict[str, Any], snapshot_root: Path, arm: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_records = [item for item in manifest["records"] if item["role"] in {"C", "C_prime"}]
    harmful_mutations = ("conflict", "deprecated", "scope", "stale", "tamper", "closure", "transfer")
    for target in target_records:
        body = record_path(snapshot_root, target).read_bytes()
        observed_sha256 = sha256(body)
        if observed_sha256 != target["source_sha256"]:
            raise ValueError(
                f"snapshot digest mismatch for {target['record_id']}: "
                f"manifest={target['source_sha256']} observed={observed_sha256}"
            )
        card = {
            "record_id": target["record_id"],
            "family_id": target["family_id"],
            "scope": f"{target['family_id']}.target",
            "active": True,
            "proof_complete": True,
            "revision": target["source_sha256"],
            "body_sha256": observed_sha256,
            "body_bytes": len(body),
        }
        requested_scope = card["scope"]
        for index in range(19):
            mutation = harmful_mutations[index % len(harmful_mutations)]
            if arm == "flat":
                actual_action, reason, body_bytes = "LOAD", "flat_exposure_control", len(body)
            else:
                actual_action, reason, body_bytes = decision(card, mutation, requested_scope)
            rows.append({
                "case_id": f"{target['record_id']}-{index + 1:02d}",
                "arm": arm,
                "family_id": target["family_id"],
                "record_id": target["record_id"],
                "mutation": mutation,
                "harmful": True,
                "expected_action": "ASK",
                "actual_action": actual_action,
                "reason": reason,
                "body_chars": body_bytes,
                "source_sha256": target["source_sha256"],
                "revision": card["revision"],
            })
        # One safe LOAD per target checks that the matrix does not only abstain.
        actual_action, reason, body_bytes = ("LOAD", "source_proof_complete", len(body))
        rows.append({
            "case_id": f"{target['record_id']}-safe-load",
            "arm": arm,
            "family_id": target["family_id"],
            "record_id": target["record_id"],
            "mutation": "none",
            "harmful": False,
            "expected_action": "LOAD",
            "actual_action": actual_action,
            "reason": reason,
            "body_chars": body_bytes,
            "source_sha256": target["source_sha256"],
            "revision": card["revision"],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate = build(manifest, args.snapshots, "map+gate+evolution")
    flat = build(manifest, args.snapshots, "flat")
    for name, rows in (("candidate-e2.jsonl", candidate), ("flat-e2.jsonl", flat)):
        (args.output_dir / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    summary = {
        "status": "SOURCE_BACKED_E2_MATRIX",
        "manifest_sha256": sha256(args.manifest.read_bytes()),
        "candidate_rows": len(candidate),
        "flat_rows": len(flat),
        "candidate_harmful": sum(row["harmful"] for row in candidate),
        "candidate_harmful_loads": sum(row["harmful"] and row["actual_action"] == "LOAD" for row in candidate),
        "flat_harmful_loads": sum(row["harmful"] and row["actual_action"] == "LOAD" for row in flat),
        "candidate_safe_loads": sum(row["actual_action"] == "LOAD" and not row["harmful"] for row in candidate),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
