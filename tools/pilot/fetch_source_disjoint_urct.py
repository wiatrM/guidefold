#!/usr/bin/env python3
"""Fetch and verify the source-disjoint URCT snapshots from its manifest.

Only the pinned source blobs are materialized.  The C-prime records are deterministic controlled
derivatives of the fetched C snapshot and are rebuilt from the manifest's explicit append text.
The command never writes into a Git checkout and never changes the manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.parse


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def repo_name(remote: str) -> str:
    parsed = urllib.parse.urlparse(remote)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"only GitHub HTTPS remotes are accepted: {remote}")
    name = parsed.path.strip("/").removesuffix(".git")
    if name.count("/") != 1:
        raise ValueError(f"invalid GitHub repository URL: {remote}")
    return name.replace("/", "__")


def ensure_checkout(remote: str, commit: str, cache: Path) -> Path:
    checkout = cache / repo_name(remote)
    if not (checkout / ".git").exists():
        cache.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1", remote, str(checkout)])
    run(["git", "fetch", "--depth", "1", "origin", commit], cwd=checkout)
    return checkout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-cache", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = {record["record_id"]: record for record in manifest["records"]}
    args.output.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for record in manifest["records"]:
        target = args.output / "snapshots" / record["family_id"] / f"{record['role']}.SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        if record["role"] == "C_prime":
            base_id = record["drift"]["base_record_id"]
            base = args.output / "snapshots" / records[base_id]["family_id"] / "C.SKILL.md"
            data = base.read_bytes() + record["drift"]["append_text"].encode("utf-8")
        else:
            checkout = ensure_checkout(record["git_remote"], record["git_revision_observed"], args.repo_cache)
            data = subprocess.check_output(["git", "show", f"{record['git_revision_observed']}:{record['source_path']}"], cwd=checkout)
        digest = sha256(data)
        if digest != record["source_sha256"]:
            raise SystemExit(f"hash mismatch for {record['record_id']}: {digest} != {record['source_sha256']}")
        target.write_bytes(data)
        written[record["record_id"]] = digest
    print(json.dumps({"status": "PASS", "records": len(written), "hashes": written}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
