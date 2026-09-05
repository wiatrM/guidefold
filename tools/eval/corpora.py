#!/usr/bin/env python3
"""Pinned real-data evaluation corpora: fetch, verify, load.

From 2026-09-05 every routing-quality claim in this repository is measured on real, independently
labelled skill corpora rather than on the 26-skill Meridian fixture (which remains the CI
dev/regression set). This module is the single place that knows where those corpora live, which
revision is under test, and whether the bytes on disk are the ones the manifest names.

    python3 tools/eval/corpora.py fetch            # download both, at the pinned revisions
    python3 tools/eval/corpora.py verify           # sha256 every file against the manifest
    python3 tools/eval/corpora.py info

The data is deliberately not committed (117 MB, third-party Apache-2.0 works); the manifest at
docs/reports/bakeoff/validation/corpora-manifest.json pins the HuggingFace revision and the
SHA-256 of every file, so "latest version" means one specific commit, not whatever is on `main`
today. `fetch` needs `huggingface_hub` (present in the GPU venv, not in the stdlib CLI — this is a
tools/ script and may depend on it). `verify` and `load_*` are stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation" / "corpora-manifest.json"
CACHE_ROOT = pathlib.Path(os.environ.get("GUIDEFOLD_CORPORA", "~/.cache/guidefold/corpora")).expanduser()


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def corpus_dir(name: str) -> pathlib.Path:
    return CACHE_ROOT / name


def _sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(name: str) -> list[str]:
    """Return a list of problems (empty == the corpus on disk is exactly the pinned one)."""
    spec = manifest()["corpora"][name]
    problems = []
    for rel, want in spec["files"].items():
        p = corpus_dir(name) / rel
        if not p.exists():
            problems.append(f"{name}/{rel}: missing — run `python3 tools/eval/corpora.py fetch`")
            continue
        got = _sha256(p)
        if got != want["sha256"]:
            problems.append(f"{name}/{rel}: sha256 {got[:12]} != pinned {want['sha256'][:12]} "
                            f"(revision {spec['revision'][:8]})")
    return problems


def available(name: str) -> bool:
    return not verify(name)


def fetch(name: str) -> pathlib.Path:
    from huggingface_hub import snapshot_download  # tools/ only; never imported by the CLI
    spec = manifest()["corpora"][name]
    return pathlib.Path(snapshot_download(
        spec["hf_repo"], repo_type=spec["repo_type"], revision=spec["revision"],
        allow_patterns=list(spec["files"]) + ["README.md"], local_dir=str(corpus_dir(name))))


# ----------------------------------------------------------------------------- loaders
def _jsonl(p: pathlib.Path):
    with p.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_skillret() -> dict:
    """SkillRet v3 test split: 6 006 skills (disjoint pool), 4 392 queries, 7 187 qrels.

    skills: id, name, namespace, description, major, sub, primary_action, primary_object,
            domain, body, skill_md, license, repo, ...
    queries: id, query, skill_ids (1..3 gold — 51 % are multi-skill), k, generator_model
    qrels:   query_id, skill_id, relevance
    """
    d = corpus_dir("skillret") / "data"
    return {"skills": list(_jsonl(d / "skills" / "test.jsonl")),
            "queries": list(_jsonl(d / "queries" / "test.jsonl")),
            "qrels": list(_jsonl(d / "qrels" / "test.jsonl")),
            "taxonomy": json.loads((d / "taxonomy.json").read_text())}


def load_skillretbench() -> dict:
    """SkillRetBench: 501 skills / 102 categories, 1 250 queries in five settings
    (single_skill, multi_skill_composition, distractor, outdated_redundant, budget_constrained),
    plus the dataset's own BM25 / dense / hybrid baseline table.

    skills carry trigger_phrases, anti_triggers, composable_skills — the same shape as our
    triggers / negative_triggers / requires. Queries may be English or Korean.
    """
    d = corpus_dir("skillretbench")
    return {"corpus": json.loads((d / "skill_corpus.json").read_text()),
            "queries": json.loads((d / "skillretbench_queries.json").read_text()),
            "baselines": json.loads((d / "baseline_results.json").read_text())}


# ----------------------------------------------------------------------------- cli
def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    cmd = args[0] if args else "info"
    names = list(manifest()["corpora"])
    if cmd == "fetch":
        for n in names:
            print(f"fetch {n} @ {manifest()['corpora'][n]['revision'][:8]} -> {fetch(n)}")
        cmd = "verify"
    if cmd == "verify":
        bad = [p for n in names for p in verify(n)]
        print("\n".join(bad) if bad else f"OK: {', '.join(names)} match the pinned manifest")
        return 1 if bad else 0
    for n in names:
        c = manifest()["corpora"][n]
        print(f"{n}: {c['hf_repo']} @ {c['revision'][:8]} ({c['last_modified']}) — "
              f"{'present' if available(n) else 'NOT on disk'} under {corpus_dir(n)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
