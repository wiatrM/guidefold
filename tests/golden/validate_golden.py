#!/usr/bin/env python3
"""Self-validation for the Guidefold E1.2 golden evaluation set.

Runs 9 mandatory checks against tests/golden/*.yaml:

  1. total case count is within [150, 300]
  2. every case `id` is unique and matches its file's category prefix
  3. category proportions are within +/-3pp of the target split
     (multi_skill 30%, sibling_ambiguity 30%, no_applicable 20%,
      stale_adversarial 10%, simple 10%)
  4. every `urn` referenced (relevant or distractor) exists among the
     fixture's real skills (parsed from SKILL.md frontmatter, the
     generated `hierarchy-index` skill is ignored)
  5. every `cwd` is an existing directory under examples/monorepo
  6. every `node` equals node_for(cwd) per the fixture's guidefold.yaml
     (reusing the real CLI's node_for/ancestors via SourceFileLoader)
  7. no deprecated skill (status: deprecated) appears in any `relevant` list
  8. no two queries (repo-wide) are identical or near-duplicate
     (normalised token-set Jaccard >= 0.9)
  9. every `no_applicable` case has `relevant: []`

Usage:
    python3 tests/golden/validate_golden.py

Exits 0 on success, 1 on any failure, printing every violation found
(not just the first). Also importable from test_golden_set.py for
pytest-style assertions on the same checks.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import yaml

GOLDEN_DIR = Path(__file__).resolve().parent
REPO_ROOT = GOLDEN_DIR.parent.parent
MONOREPO_DIR = REPO_ROOT / "examples" / "monorepo"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"

TARGET_PROPORTIONS = {
    "multi_skill": 0.30,
    "sibling_ambiguity": 0.30,
    "no_applicable": 0.20,
    "stale_adversarial": 0.10,
    "simple": 0.10,
}
ID_PREFIX = {
    "multi_skill": "multi-",
    "sibling_ambiguity": "sib-",
    "no_applicable": "noapp-",
    "stale_adversarial": "stale-",
    "simple": "simple-",
}
CATEGORY_FILES = {
    "multi_skill": "multi_skill.yaml",
    "sibling_ambiguity": "sibling_ambiguity.yaml",
    "no_applicable": "no_applicable.yaml",
    "stale_adversarial": "stale_adversarial.yaml",
    "simple": "simple.yaml",
}


# ---------------------------------------------------------------- loading helpers
def load_cli_module():
    """Import skills/guidefold/scripts/guidefold (no .py extension) as a module."""
    loader = SourceFileLoader("guidefold_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def load_categories() -> dict:
    """category name -> parsed yaml doc (version/category/cases)."""
    docs = {}
    for cat, fname in CATEGORY_FILES.items():
        path = GOLDEN_DIR / fname
        if not path.is_file():
            raise SystemExit(f"missing golden file: {path}")
        with open(path) as f:
            docs[cat] = yaml.safe_load(f)
    return docs


def load_fixture_skills() -> dict:
    """urn -> {status, path} for every real SKILL.md under examples/monorepo,
    excluding the generated hierarchy-index skill."""
    cli = load_cli_module()
    cfg = cli.load_map(MONOREPO_DIR)
    skills = {}
    for skill_path in sorted(MONOREPO_DIR.glob("**/.agents/skills/*/SKILL.md")):
        text = skill_path.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1))
        metadata = fm.get("metadata", {}) or {}
        if str(metadata.get("generated", "")).lower() == "true":
            continue  # generated hierarchy-index skill: ignore
        name = fm.get("name") or skill_path.parent.name
        relpath = cli.rel(MONOREPO_DIR, skill_path.parent)
        node = cli.node_for(cfg, relpath)
        skill_urn = cli.urn(cfg, node, name)
        skills[skill_urn] = {
            "status": metadata.get("status", "active"),
            "path": str(skill_path),
        }
    return skills, cli, cfg


# ---------------------------------------------------------------- text similarity
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(s: str) -> set:
    return set(_TOKEN_RE.findall(s.lower()))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ---------------------------------------------------------------- checks
def run_checks():
    errors: list[str] = []
    docs = load_categories()
    fixture_skills, cli, cfg = load_fixture_skills()
    deprecated_urns = {u for u, info in fixture_skills.items() if info["status"] == "deprecated"}

    all_cases = []  # (category, case_dict)
    for cat, doc in docs.items():
        cases = doc.get("cases", [])
        for c in cases:
            all_cases.append((cat, c))

    total = len(all_cases)

    # ---- check 1: total count in [150, 300]
    print(f"[1] total case count: {total}")
    if not (150 <= total <= 300):
        errors.append(f"CHECK 1 FAILED: total case count {total} not in [150, 300]")

    # ---- check 2: unique ids, correct prefix
    seen_ids = {}
    for cat, c in all_cases:
        cid = c.get("id", "")
        prefix = ID_PREFIX[cat]
        if not cid.startswith(prefix):
            errors.append(f"CHECK 2 FAILED: id '{cid}' in category '{cat}' missing prefix '{prefix}'")
        if cid in seen_ids:
            errors.append(f"CHECK 2 FAILED: duplicate id '{cid}' (categories: {seen_ids[cid]}, {cat})")
        else:
            seen_ids[cid] = cat
    print(f"[2] unique ids: {len(seen_ids)} / {total}")

    # ---- check 3: category proportions within +/-3pp of target
    print("[3] category proportions:")
    for cat in TARGET_PROPORTIONS:
        n = len(docs[cat].get("cases", []))
        pct = 100.0 * n / total if total else 0.0
        target_pct = TARGET_PROPORTIONS[cat] * 100
        diff = abs(pct - target_pct)
        status = "OK" if diff <= 3.0 else "FAIL"
        print(f"    {cat:20s} n={n:3d}  {pct:5.1f}%  target={target_pct:4.1f}%  diff={diff:4.1f}pp  [{status}]")
        if diff > 3.0:
            errors.append(
                f"CHECK 3 FAILED: category '{cat}' proportion {pct:.1f}% deviates "
                f"{diff:.1f}pp from target {target_pct:.1f}% (max 3pp)"
            )

    # ---- check 4: every urn (relevant + distractors) exists in fixture
    bad_urns = set()
    for cat, c in all_cases:
        for rel_entry in c.get("relevant", []):
            u = rel_entry["urn"]
            if u not in fixture_skills:
                bad_urns.add((c["id"], u))
        for dist_entry in c.get("distractors", []) or []:
            u = dist_entry["urn"]
            if u not in fixture_skills:
                bad_urns.add((c["id"], u))
    print(f"[4] urns referencing nonexistent fixture skills: {len(bad_urns)}")
    for cid, u in sorted(bad_urns):
        errors.append(f"CHECK 4 FAILED: case '{cid}' references unknown urn '{u}'")

    # ---- check 5: cwd exists as a directory
    bad_cwds = set()
    for cat, c in all_cases:
        cwd = c.get("cwd", "")
        full = MONOREPO_DIR / cwd if cwd != "." else MONOREPO_DIR
        if not full.is_dir():
            bad_cwds.add((c["id"], cwd))
    print(f"[5] cases with nonexistent cwd: {len(bad_cwds)}")
    for cid, cwd in sorted(bad_cwds):
        errors.append(f"CHECK 5 FAILED: case '{cid}' has nonexistent cwd '{cwd}'")

    # ---- check 6: node == node_for(cwd)
    bad_nodes = []
    for cat, c in all_cases:
        cwd = c.get("cwd", "")
        full = MONOREPO_DIR / cwd if cwd != "." else MONOREPO_DIR
        if not full.is_dir():
            continue  # already reported in check 5
        relpath = cli.rel(MONOREPO_DIR, full)
        if relpath == ".":
            relpath = ""
        expected_node = cli.node_for(cfg, relpath)
        actual_node = c.get("node", "")
        if actual_node != expected_node:
            bad_nodes.append((c["id"], cwd, actual_node, expected_node))
    print(f"[6] cases with node != node_for(cwd): {len(bad_nodes)}")
    for cid, cwd, actual, expected in bad_nodes:
        errors.append(
            f"CHECK 6 FAILED: case '{cid}' cwd='{cwd}' has node='{actual}' "
            f"but node_for(cwd)='{expected}'"
        )

    # ---- check 7: no deprecated skill in any relevant list
    deprecated_hits = []
    for cat, c in all_cases:
        for rel_entry in c.get("relevant", []):
            if rel_entry["urn"] in deprecated_urns:
                deprecated_hits.append((c["id"], rel_entry["urn"]))
    print(f"[7] deprecated skills appearing in relevant lists: {len(deprecated_hits)}")
    print(f"    deprecated urns in fixture: {sorted(deprecated_urns)}")
    for cid, u in deprecated_hits:
        errors.append(f"CHECK 7 FAILED: case '{cid}' lists deprecated skill '{u}' as relevant")

    # ---- check 8: no duplicate / near-duplicate queries (Jaccard >= 0.9)
    query_tokens = [(c["id"], c["query"], tokenize(c["query"])) for _, c in all_cases]
    near_dupes = []
    for i in range(len(query_tokens)):
        id_i, q_i, tok_i = query_tokens[i]
        for j in range(i + 1, len(query_tokens)):
            id_j, q_j, tok_j = query_tokens[j]
            sim = jaccard(tok_i, tok_j)
            if sim >= 0.9:
                near_dupes.append((id_i, id_j, sim, q_i, q_j))
    print(f"[8] near-duplicate query pairs (Jaccard >= 0.9): {len(near_dupes)}")
    for id_i, id_j, sim, q_i, q_j in near_dupes:
        errors.append(
            f"CHECK 8 FAILED: '{id_i}' and '{id_j}' near-duplicate (Jaccard={sim:.2f}): "
            f"'{q_i}' vs '{q_j}'"
        )

    # ---- check 9: every no_applicable case has relevant: []
    bad_noapp = []
    for c in docs["no_applicable"].get("cases", []):
        if c.get("relevant", []) != []:
            bad_noapp.append(c["id"])
    print(f"[9] no_applicable cases with non-empty relevant: {len(bad_noapp)}")
    for cid in bad_noapp:
        errors.append(f"CHECK 9 FAILED: no_applicable case '{cid}' has non-empty relevant list")

    # ---- bonus sanity: MVP smoke-test prompts present and route differently
    smoke_cases = [c for _, c in all_cases if c.get("notes", "").startswith("MVP smoke-test prompt")]
    print(f"[bonus] MVP smoke-test prompt cases found: {len(smoke_cases)}")
    if len(smoke_cases) < 3:
        errors.append(f"BONUS CHECK FAILED: expected 3 MVP smoke-test prompt cases, found {len(smoke_cases)}")
    else:
        top3_sets = []
        for c in smoke_cases:
            urns = tuple(sorted(r["urn"] for r in c.get("relevant", [])[:3]))
            top3_sets.append(urns)
        if len(set(top3_sets)) != len(top3_sets):
            errors.append(
                "BONUS CHECK FAILED: MVP smoke-test prompts do not all have distinct top-3 relevant sets: "
                f"{top3_sets}"
            )

    return errors, total


def main():
    errors, total = run_checks()
    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: all checks passed ({total} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
