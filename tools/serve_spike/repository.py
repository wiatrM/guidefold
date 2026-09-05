#!/usr/bin/env python3
"""Build a serving snapshot from a Git commit, never from dirty working-tree files."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.serve_spike.context import string

FORMAT = "guidefold-service-snapshot-v1"
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def load(path, cli, cli_sha):
    path = Path(path)
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("repository_snapshot_too_large")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    data = envelope["snapshot"]
    digest = hashlib.sha256(canonical(data)).hexdigest()
    if envelope["sha256"] != digest or data["format"] != FORMAT:
        raise ValueError("repository_snapshot_integrity_mismatch")
    if data["cli_sha256"] != cli_sha:
        raise ValueError("repository_snapshot_cli_mismatch")
    string(data["repo_id"], identifier=True)
    string(data["revision"], identifier=True)
    nodes, cards = data["nodes"], data["cards"]
    if "_root" not in nodes or not cards:
        raise ValueError("empty_repository_snapshot")
    for node, spec in nodes.items():
        string(node, identifier=True)
        if not isinstance(spec.get("paths"), list) or not all(isinstance(p, str) for p in spec["paths"]):
            raise ValueError("invalid_scope_map")
    for urn, card in cards.items():
        if card["urn"] != urn or card["node"] not in nodes or not isinstance(card["_body"], str):
            raise ValueError("invalid_repository_card")
    index = cli.Index.from_cards(cards, nodes, weights={**data["weights"], "w_dense": 0})
    return index, {"repo_id": data["repo_id"], "revision": data["revision"]}, "repository:" + digest


def build(repo_root, repo_id, revision, cli, cli_sha):
    repo_root = Path(repo_root).resolve()
    string(repo_id, identifier=True)
    git_cwd = repo_root
    def git(*args):
        return subprocess.run(["git", "-C", str(git_cwd), *args], check=True,
                              capture_output=True, timeout=120).stdout
    commit = git("rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
    prefix = git("rev-parse", "--show-prefix").decode().strip()
    git_cwd = Path(git("rev-parse", "--show-toplevel").decode().strip())
    paths = git("ls-tree", "-rz", "--name-only", commit).decode().split("\0")
    wanted = [path for path in paths if path == prefix + "guidefold.yaml"
              or (path.startswith(prefix) and path.endswith("/SKILL.md"))]
    if prefix + "guidefold.yaml" not in wanted:
        raise ValueError("repository_revision_has_no_guidefold_yaml")
    archive = git("archive", "--format=tar", commit, "--", *wanted)
    with tempfile.TemporaryDirectory(prefix="guidefold-service-snapshot-") as directory:
        temporary = Path(directory).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            for member in tar:
                if member.isdir():
                    continue
                if not member.isfile() or member.name not in wanted:
                    raise ValueError("unsupported_snapshot_entry")
                destination = (temporary / member.name).resolve()
                if not destination.is_relative_to(temporary):
                    raise ValueError("invalid_snapshot_entry_path")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(tar.extractfile(member).read())
        root = temporary / prefix
        cfg = cli.load_map(root)
        index = cli.Index.build(root, cfg)
        data = {"format": FORMAT, "repo_id": repo_id, "revision": commit,
                "cli_sha256": cli_sha, "nodes": index.nodes, "cards": index.cards,
                "weights": {**index.weights, "w_dense": 0},
                "source": "git_commit_only", "assets_included": False}
    return {"snapshot": data, "sha256": hashlib.sha256(canonical(data)).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--cli-path", type=Path, default=ROOT / "skills/guidefold/scripts/guidefold")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from tools.serve_spike.server import load_cli_snapshot
    cli, cli_sha = load_cli_snapshot(args.cli_path)
    bundle = build(args.repo_root, args.repo_id, args.revision, cli, cli_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(bundle) + b"\n")
    print(json.dumps({"repo_id": args.repo_id, "revision": bundle["snapshot"]["revision"],
                      "sha256": bundle["sha256"], "cards": len(bundle["snapshot"]["cards"])}))


if __name__ == "__main__":
    main()
