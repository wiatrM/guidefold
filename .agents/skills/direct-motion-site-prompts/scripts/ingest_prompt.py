#!/usr/bin/env python3
"""Store an untrusted motion-site prompt and update its deterministic manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
URL_RE = re.compile(r"https?://[^\s`<>\"']+")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def extract_urls(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    urls = {match.rstrip("),.;]") for match in URL_RE.findall(text)}
    return sorted(urls)


def parse_args() -> argparse.Namespace:
    skill_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Input file or '-' for stdin")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--source-kind", required=True, choices=["attachment", "conversation", "operator-file"])
    parser.add_argument("--source-id", required=True, help="Opaque attachment ID, task label, or source hash")
    parser.add_argument("--occurrences", type=int, default=1)
    parser.add_argument("--corpus-dir", type=Path, default=skill_dir / "resources" / "corpus")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not SLUG_RE.fullmatch(args.slug):
        raise SystemExit("slug must use lowercase hyphen-case")
    if args.occurrences < 1:
        raise SystemExit("occurrences must be positive")

    data = sys.stdin.buffer.read() if args.source == "-" else Path(args.source).read_bytes()
    if not data:
        raise SystemExit("source prompt is empty")

    sha256 = hashlib.sha256(data).hexdigest()
    target = args.corpus_dir / f"{args.slug}.txt"
    if target.exists() and target.read_bytes() != data and not args.replace:
        raise SystemExit(f"refusing to replace different corpus entry: {target}")
    atomic_write(target, data)

    entry = {
        "slug": args.slug,
        "sourceKind": args.source_kind,
        "sourceId": args.source_id,
        "sha256": sha256,
        "bytes": len(data),
        "lines": data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
        "occurrences": args.occurrences,
        "urls": extract_urls(data),
    }
    manifest_path = args.corpus_dir.parent / "corpus-manifest.json"
    manifest = {"schemaVersion": 1, "entries": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [item for item in manifest.get("entries", []) if item.get("slug") != args.slug]
    entries.append(entry)
    manifest = {"schemaVersion": 1, "entries": sorted(entries, key=lambda item: item["slug"])}
    atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
