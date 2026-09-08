#!/usr/bin/env python3
"""Build a serving snapshot from a materialised import tree (no git), for the publish worker.

`tools/serve_spike/repository.py::build` is the git path: it resolves a commit, extracts
`guidefold.yaml` + every `SKILL.md` from the object store and builds the snapshot from those
bytes. The hosted pivot needs the same snapshot from a tree the worker materialised out of
import blobs under `.guidefold/worker/`, where there is no git repository at all. Everything
else is deliberately identical -- same CLI, hashed and executed from the same bytes
(`load_cli_snapshot`), same `load_map`/`Index.build`, same envelope, same `canonical()` digest,
same `with_router_index` export for the Go publisher. Only `source` differs
(`import_tree` instead of `git_commit_only`), so a snapshot's provenance stays visible.

Alongside the snapshot it writes `inventory.json`: one row per parsed `SKILL.md` with the fields
the importer stores as `skill`/`skill_revision` (scope, owner, layer, status, relations, digest).
Frontmatter parsing/validation is the CLI's own (`cli.frontmatter`, `cli.md_list`,
`cli.md_phrases`, `cli.node_for`, `cli.urn`) -- never a second implementation that could drift.
A file that fails to parse is recorded in `errors[]` and skipped; it does not abort the run.

    python3 tools/worker/build_tree.py --tree DIR --repo-id R --commit SHA --output snapshot.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.serve_spike.repository import FORMAT, canonical
from tools.search_service.index import with_router_index

SOURCE = "import_tree"
INVENTORY_FORMAT = "guidefold-import-inventory-v1"


def _skill_files(tree: Path):
    """Same enumeration as the CLI's `all_skills`, but yielding paths only so each file can be
    parsed (and fail) on its own."""
    for md in sorted(tree.rglob(".agents/skills/*/SKILL.md")):
        if ".guidefold" in md.parts:
            continue
        yield md


def _row(cli, tree: Path, md: Path, cfg: dict) -> dict:
    raw = md.read_bytes()
    fm = cli.frontmatter(md)
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a YAML mapping")
    meta = fm.get("metadata") or {}
    if not isinstance(meta, dict):
        raise ValueError("metadata is not a YAML mapping")
    directory = md.parent
    generated = str(meta.get("generated", "")).lower() == "true"
    node = meta.get("scope") or "_index" if generated else cli.node_for(cfg, cli.rel(tree, directory))
    name = fm.get("name") or directory.name
    return {
        "path": md.relative_to(tree).as_posix(),
        "urn": cli.urn(cfg, node, directory.name),
        "name": str(name),
        "scope": node,
        "owner": meta.get("owner"),
        "layer": meta.get("layer"),
        "status": meta.get("status"),
        "kind": meta.get("kind"),
        "generated": generated,
        "description": str(fm.get("description", "")),
        "requires": cli.md_list(meta, "requires"),
        "refines": cli.md_list(meta, "refines"),
        "replaces": cli.md_list(meta, "replaces"),
        "references": cli.md_list(meta, "references"),
        "triggers": cli.md_phrases(meta, "triggers"),
        "negative_triggers": cli.md_phrases(meta, "negative_triggers"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        # The whole frontmatter is carried verbatim so the importer never has to re-read the
        # file to store a field this row does not name yet.
        "frontmatter": {k: v for k, v in fm.items() if isinstance(k, str)},
    }


def inventory(cli, tree: Path, cfg: dict, repo_id: str, commit: str) -> dict:
    """One row per authored SKILL.md, plus what was skipped and what would not parse.

    Generated cards (`metadata.generated: true` -- the `hierarchy-index` an earlier
    `guidefold index` left in the tree) are NOT rows. `Index.build` goes through
    `all_skills(root, cfg)`, which defaults `include_generated=False`, so the snapshot has no
    card for them; a row here would put a skill in `gfm.skills` and in the catalog that SEARCH
    can never return, and make `cards` and `skills` disagree by exactly their number. They are
    listed under `generated_skipped` instead, so the omission is stated rather than silent
    (ADR-0012: nothing generated is committed, so finding one is worth being able to see)."""
    skills, errors, skipped = [], [], []
    for md in _skill_files(tree):
        rel_path = md.relative_to(tree).as_posix()
        try:
            row = _row(cli, tree, md, cfg)
        except Exception as exc:                       # one bad SKILL.md never fails the import
            errors.append({"path": rel_path, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if row["generated"]:
            skipped.append(rel_path)
            continue
        skills.append(row)
    skills.sort(key=lambda row: row["path"].encode("utf-8", "surrogateescape"))
    errors.sort(key=lambda row: row["path"].encode("utf-8", "surrogateescape"))
    skipped.sort(key=lambda path: path.encode("utf-8", "surrogateescape"))
    return {"format": INVENTORY_FORMAT, "repo_id": repo_id, "revision": commit,
            "skills": skills, "errors": errors, "generated_skipped": skipped}


def _load_config(cli, tree: Path) -> dict:
    """`guidefold.yaml` as the CLI reads it, with the malformed shapes named.

    The file is client input. `cli.load_map` assumes a mapping with a `publisher`, so an empty
    file, a list at the top level or a file with `nodes:` and no `publisher:` reached the worker
    as `AttributeError: 'NoneType' object has no attribute 'setdefault'` or `KeyError:
    'publisher'`. `builder.go` puts the last line of that traceback into `gfm.imports.error`,
    so the owner was shown a Python traceback for a fixable mistake in their own repository.
    Each shape gets a name instead; the reasons are the strings the UI renders."""
    try:
        import yaml
    except ImportError:                              # pragma: no cover - the image pins PyYAML
        raise ValueError("import_tree_pyyaml_missing")
    try:
        raw = yaml.safe_load((tree / "guidefold.yaml").read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or "it is not valid YAML"
        raise ValueError(f"import_tree_guidefold_yaml_unparseable: {problem}") from None
    except (OSError, UnicodeDecodeError):
        raise ValueError("import_tree_guidefold_yaml_unreadable") from None
    if not isinstance(raw, dict):
        raise ValueError("import_tree_guidefold_yaml_not_a_mapping")
    if not raw.get("publisher"):
        raise ValueError("import_tree_missing_publisher")
    nodes = raw.get("nodes")
    if nodes is not None and not isinstance(nodes, dict):
        raise ValueError("import_tree_nodes_not_a_mapping")
    # Parsed and checked; now let the CLI apply its own defaults, so the config the snapshot is
    # built from is byte-for-byte the one every other guidefold command would have produced.
    return cli.load_map(tree)


def build(tree, repo_id, commit, cli, cli_sha):
    """The snapshot envelope `tools/serve_spike/repository.build` produces, from a plain
    directory instead of a git commit."""
    tree = Path(tree).resolve()
    if not (tree / "guidefold.yaml").is_file():
        raise ValueError("import_tree_has_no_guidefold_yaml")
    cfg = _load_config(cli, tree)
    index = cli.Index.build(tree, cfg)
    data = {"format": FORMAT, "repo_id": repo_id, "revision": commit,
            "cli_sha256": cli_sha, "nodes": index.nodes, "cards": index.cards,
            "weights": {**index.weights, "w_dense": 0},
            "source": SOURCE, "assets_included": False}
    return {"snapshot": data, "sha256": hashlib.sha256(canonical(data)).hexdigest()}, cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True, help="materialised import tree (holds guidefold.yaml)")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--commit", required=True, help="the import's commit, or its manifest digest when the scan was dirty")
    parser.add_argument("--cli-path", type=Path, default=ROOT / "skills/guidefold/scripts/guidefold")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, default=None,
                        help="where to write the per-skill inventory (default: inventory.json next to --output)")
    args = parser.parse_args()

    from tools.serve_spike.server import load_cli_snapshot
    cli, cli_sha = load_cli_snapshot(args.cli_path)

    # The inventory is written FIRST, before the snapshot, because `Index.build`
    # aborts on a SKILL.md the CLI cannot parse. The importer needs to know
    # *which* file that was: one broken file has to fail on its own while the
    # rest of the import is accepted (PRODUCT-PIVOT U2.1). The inventory records
    # every parse error in `errors[]`, so a caller whose build fails can read
    # this file, drop the named paths from its own materialised tree and try
    # again. On a tree that builds cleanly the two output files are identical to
    # what the previous order produced.
    tree = Path(args.tree).resolve()
    inventory_path = args.inventory or args.output.with_name("inventory.json")
    rows = inventory(cli, tree, cli.load_map(tree), args.repo_id, args.commit)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_bytes(canonical(rows) + b"\n")

    bundle, _cfg = build(args.tree, args.repo_id, args.commit, cli, cli_sha)
    bundle = with_router_index(cli, bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(bundle) + b"\n")

    print(json.dumps({"repo_id": args.repo_id, "revision": args.commit,
                      "sha256": bundle["sha256"], "source": SOURCE,
                      "cards": len(bundle["snapshot"]["cards"]),
                      "skills": len(rows["skills"]), "errors": len(rows["errors"]),
                      "inventory": str(inventory_path)}))


if __name__ == "__main__":
    main()
