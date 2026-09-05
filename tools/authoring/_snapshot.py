"""tools/authoring/_snapshot.py — shared git-archive snapshot + CLI-loading helpers for the
authoring loop's per-PR tools (`collision_report.py`, `suggest_triggers.py`; docs/MVP.md §5
"3-6 authoring loop"). One place their git/Index plumbing lives, so a change to how a snapshot is
built or the CLI is loaded cannot drift between the two scripts.

This module never reimplements ranking. It loads the single-file CLI module exactly as
`tools/eval/run_golden.py` does (`SourceFileLoader`, no `.py` extension) and calls the CLI's own
`load_map`/`Index.build` — Index/Router/node/URN resolution stay the product's, always.

Snapshot isolation: `git archive <ref>` piped through stdlib `tarfile` into a temp directory,
never the working tree and never a second `git worktree` living in the repo (`git archive` is
read-only against the git object store and cannot race a concurrent checkout the way a worktree
add/remove can).
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
import tarfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_RELPATHS = ("skills/guidefold/scripts/guidefold", ".agents/skills/guidefold/scripts/guidefold")


def find_cli_path(repo_root: Path) -> Path:
    """`skills/guidefold/scripts/guidefold` in this repo, `.agents/skills/guidefold/scripts/guidefold`
    in a consumer that has already run `guidefold init` (deliverable #4's `templates/ci.yml` runs
    the same script against a consumer checkout)."""
    for rel in CLI_RELPATHS:
        p = repo_root / rel
        if p.is_file():
            return p
    raise SystemExit(f"authoring: no guidefold CLI found under {repo_root} (tried {CLI_RELPATHS})")


def load_cli(cli_path: Path):
    loader = SourceFileLoader("guidefold_cli_authoring", str(cli_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def git_toplevel(path: Path) -> Path:
    out = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def rel_root_of(root: Path, repo_root: Path) -> str:
    """`root`'s path relative to `repo_root`, as a snapshot-relative string ("." when they are the
    same directory — e.g. a consumer whose `guidefold.yaml` sits at the repo root)."""
    root = root.resolve()
    repo_root = repo_root.resolve()
    return "." if root == repo_root else str(root.relative_to(repo_root))


def archive_ref_into(repo_root: Path, ref: str, dest: Path) -> None:
    """Extract `ref` exactly as committed into `dest`. `git archive` piped through stdlib
    `tarfile` — no dependency on an external `tar` binary, no shell pipe."""
    proc = subprocess.run(["git", "archive", "--format=tar", ref], cwd=str(repo_root),
                           capture_output=True, check=True)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
        try:
            tf.extractall(dest, filter="data")   # Python >= 3.12: default-safe extraction filter
        except TypeError:
            tf.extractall(dest)                  # Python < 3.12 has no `filter` kwarg


def build_snapshot_index(cli, repo_root: Path, rel_root: str, ref: str, work: Path):
    """One clean git-archive checkout of `ref`, loaded through the product's own `Index.build`.
    `Index.build` reads every SKILL.md eagerly (no lazy mmap artifact — that's `guidefold index`,
    a different code path), so the returned Index is fully independent of `work` by the time this
    call returns; `work` may be torn down immediately afterwards."""
    dest = work / ref.replace("/", "_")
    archive_ref_into(repo_root, ref, dest)
    effective_root = dest if rel_root in ("", ".") else (dest / rel_root)
    cfg = cli.load_map(effective_root)
    idx = cli.Index.build(effective_root, cfg)
    return cfg, idx


# ------------------------------------------------------------------------------- card diffing
# Every field `Index.build` puts on a card (skills/guidefold/scripts/guidefold, class Index.build).
# Comparing all of them (not just `description`) means a body-only edit with an unchanged
# description still counts as "changed" — exactly the kind of edit that can shift BM25 field
# scores (the `body` field is itself BM25-weighted) without touching frontmatter at all.
_CARD_FIELDS = ("description", "digest", "triggers", "negative_triggers", "requires", "refines",
                "status", "replaced_by", "kind", "layer", "owner", "_body", "node", "name")


def _card_signature(card: dict) -> tuple:
    return tuple(card.get(f) for f in _CARD_FIELDS)


def diff_cards(base_idx, head_idx) -> tuple:
    """(added, removed, changed) URN sets between two Index snapshots."""
    base_urns = set(base_idx.cards.keys())
    head_urns = set(head_idx.cards.keys())
    added = head_urns - base_urns
    removed = base_urns - head_urns
    common = base_urns & head_urns
    changed = {u for u in common if _card_signature(base_idx.cards[u]) != _card_signature(head_idx.cards[u])}
    return added, removed, changed
