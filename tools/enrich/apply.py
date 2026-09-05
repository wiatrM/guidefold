#!/usr/bin/env python3
"""apply.py — run F5 derivation (`derive.derive`) over a real corpus and emit:

  (a) an enriched cards JSONL, one JSON object per line, in exactly the shape
      `Index.from_cards` (skills/guidefold/scripts/guidefold) expects — see `build_cards`;
  (b) a stats report (JSON) — coverage counts, provenance-rule breakdown, top headings;
  (c) for SkillRetBench only, the agreement table against its authored `trigger_phrases` /
      `anti_triggers` / `composable_skills` (DENSE-PROGRAM.md §4, F5's own sanity check, run
      by pretending the authored fields do not exist and deriving from `full_text` alone).

Usage:
    python3 tools/enrich/apply.py local <skills-dir> --out-cards cards.jsonl --out-stats stats.json
    python3 tools/enrich/apply.py skillretbench --out-cards cards.jsonl --out-stats stats.json \\
        --out-agreement agreement.json

`local` walks <skills-dir> for `**/SKILL.md` (e.g. `experiment/skills`, the gitignored
2 037-skill real corpus — see CLAUDE.md/DENSE-PROGRAM.md §4; never commit that directory).
`skillretbench` uses `tools/eval/corpora.py::load_skillretbench()` (must already be fetched:
`python3 tools/eval/corpora.py fetch`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "tools" / "enrich", _ROOT / "tools" / "eval", _ROOT / "tools" / "bakeoff"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import derive as derive_mod  # noqa: E402
import corpora  # noqa: E402
from tokenizer import tokenize  # noqa: E402

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_SAFE_RE = re.compile(r"[^a-z0-9\-]+")


def _slug(s: str) -> str:
    return _SAFE_RE.sub("-", str(s).strip().lower()).strip("-") or "skill"


# ------------------------------------------------------------------------------- corpus loaders
def _parse_skill_md(path: Path) -> "dict | None":
    import yaml

    text = path.read_text(encoding="utf-8", errors="ignore")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1))
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    name = meta.get("name")
    if not name:
        return None
    description = meta.get("description")
    if not isinstance(description, str):
        description = "" if description is None else str(description)
    return {"id": str(name), "name": str(name), "description": description, "body": m.group(2)}


def load_directory_corpus(root: Path) -> list:
    """Every `**/SKILL.md` under `root`. Real ids collide extremely rarely (0/2037 measured on
    the reference corpus); a collision is disambiguated with the parent directory path so no
    skill is silently dropped."""
    skills = []
    seen = {}
    for md in sorted(root.rglob("SKILL.md")):
        s = _parse_skill_md(md)
        if s is None:
            continue
        sid = s["id"]
        if sid in seen:
            sid = f"{md.parent.relative_to(root)}"
            s["id"] = sid
        seen[sid] = True
        skills.append(s)
    return skills


def load_skillretbench_as_skills():
    """(skills, authored) — `skills` carries only id/name/description/body (from `full_text`,
    frontmatter stripped) so `derive()` never sees `trigger_phrases`/`anti_triggers`/
    `composable_skills`; `authored` keeps those aside, keyed by id, for the agreement eval."""
    bench = corpora.load_skillretbench()
    skills, authored = [], {}
    for s in bench["corpus"]["skills"]:
        sid = s["skill_id"]
        full_text = s.get("full_text") or ""
        m = FRONTMATTER_RE.match(full_text)
        body = m.group(2) if m else full_text
        skills.append({
            "id": sid, "name": s.get("skill_name") or sid,
            "description": s.get("description") or "", "body": body,
        })
        authored[sid] = {
            "trigger_phrases": list(s.get("trigger_phrases") or []),
            "anti_triggers": list(s.get("anti_triggers") or []),
            "composable_skills": list(s.get("composable_skills") or []),
        }
    return skills, authored


# ------------------------------------------------------------------------------- card building
def build_cards(skills: list, enrichment: dict, node: str = "_root", publisher: str = "enrich") -> dict:
    """{urn: card} in exactly the shape `Index.from_cards` consumes (tests/_router_helpers.py::
    make_card). `similar` is carried as an extra key — CONVENTIONS.md: generated, not yet
    consumed by the shipped index, but this is exactly the generator that would feed a future one."""
    urns = {s["id"]: f"urn:skill:{publisher}:{node}:{_slug(s['id'])}" for s in skills}
    cards = {}
    for s in skills:
        sid = s["id"]
        u = urns[sid]
        e = enrichment[sid]
        cards[u] = {
            "urn": u, "node": node, "name": _slug(sid),
            "description": s.get("description") or "",
            "digest": (s.get("description") or "")[:200],
            "triggers": list(e.triggers),
            "negative_triggers": list(e.negative_triggers),
            "requires": [urns[t] for t in e.requires if t in urns],
            "refines": [],
            "status": "active",
            "replaced_by": None,
            "kind": None,
            "layer": None,
            "owner": None,
            "_body": s.get("body") or "",
            "similar": [urns[t] for t in e.similar if t in urns],
        }
    return cards


def write_cards_jsonl(cards: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for card in cards.values():
            f.write(json.dumps(card, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------- stats
def compute_stats(skills: list, enrichment: dict) -> dict:
    n = len(skills)
    n_trig = sum(1 for s in skills if enrichment[s["id"]].triggers)
    n_neg = sum(1 for s in skills if enrichment[s["id"]].negative_triggers)
    n_req = sum(1 for s in skills if enrichment[s["id"]].requires)
    n_sim = sum(1 for s in skills if enrichment[s["id"]].similar)

    rule_counts = Counter()
    heading_counts = Counter()
    confidence_counts = Counter()
    for s in skills:
        e = enrichment[s["id"]]
        for field_name in ("triggers", "negative_triggers", "requires", "similar"):
            for p in e.provenance[field_name]:
                rule_counts[(field_name, p["rule"])] += 1
                if p.get("heading"):
                    heading_counts[(field_name, p["heading"])] += 1
                if "confidence" in p:
                    confidence_counts[(field_name, p["confidence"])] += 1

    total_edges = sum(len(enrichment[s["id"]].requires) + len(enrichment[s["id"]].similar) for s in skills)

    return {
        "n_skills": n,
        "n_with_triggers": n_trig, "pct_with_triggers": round(100 * n_trig / n, 1) if n else 0,
        "n_with_negative_triggers": n_neg, "pct_with_negative_triggers": round(100 * n_neg / n, 1) if n else 0,
        "n_with_requires": n_req, "pct_with_requires": round(100 * n_req / n, 1) if n else 0,
        "n_with_similar": n_sim, "pct_with_similar": round(100 * n_sim / n, 1) if n else 0,
        "total_edges": total_edges,
        "rule_counts": {f"{k[0]}/{k[1]}": v for k, v in rule_counts.most_common()},
        "confidence_counts": {f"{k[0]}/{k[1]}": v for k, v in confidence_counts.most_common()},
        "top_headings": {f"{k[0]}: {k[1]!r}": v for k, v in heading_counts.most_common(20)},
    }


# --------------------------------------------------------------------------------- agreement
def _mean(xs: list):
    return round(sum(xs) / len(xs), 4) if xs else None


def evaluate_skillretbench(skills: list, enrichment: dict, authored: dict) -> dict:
    """DENSE-PROGRAM.md §4, F5's sanity check: agreement between what `derive()` produces from
    `full_text` alone and SkillRetBench's own authored fields. NOT the family evaluation gate
    (`all_required@4` on dev/test, run later) — see the F5 report."""
    trig_jaccards, trig_recalls, trig_precisions = [], [], []
    neg_jaccards, neg_recalls, neg_precisions = [], [], []

    for s in skills:
        sid = s["id"]
        e = enrichment[sid]
        derived_trig = {t for p in e.triggers for t in tokenize(p)}
        derived_neg = {t for p in e.negative_triggers for t in tokenize(p)}
        auth_trig = {t for p in authored[sid]["trigger_phrases"] for t in tokenize(p)}
        auth_neg = {t for p in authored[sid]["anti_triggers"] for t in tokenize(p)}

        if derived_trig or auth_trig:
            union = derived_trig | auth_trig
            trig_jaccards.append(len(derived_trig & auth_trig) / len(union) if union else 1.0)
        if auth_trig:
            trig_recalls.append(len(derived_trig & auth_trig) / len(auth_trig))
        if derived_trig:
            trig_precisions.append(len(derived_trig & auth_trig) / len(derived_trig))

        if derived_neg or auth_neg:
            union = derived_neg | auth_neg
            neg_jaccards.append(len(derived_neg & auth_neg) / len(union) if union else 1.0)
        if auth_neg:
            neg_recalls.append(len(derived_neg & auth_neg) / len(auth_neg))
        if derived_neg:
            neg_precisions.append(len(derived_neg & auth_neg) / len(derived_neg))

    tp = fp = fn = 0
    gold_edge_total = 0
    for s in skills:
        sid = s["id"]
        e = enrichment[sid]
        derived_edges = set(e.requires) | set(e.similar)
        gold_edges = set(authored[sid]["composable_skills"])
        gold_edge_total += len(gold_edges)
        tp += len(derived_edges & gold_edges)
        fp += len(derived_edges - gold_edges)
        fn += len(gold_edges - derived_edges)

    precision = round(tp / (tp + fp), 4) if (tp + fp) else None
    recall = round(tp / (tp + fn), 4) if (tp + fn) else None

    return {
        "edges": {
            "gold_edges": gold_edge_total, "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall,
        },
        "triggers": {
            "mean_jaccard": _mean(trig_jaccards), "n_jaccard_scored": len(trig_jaccards),
            "mean_recall_of_authored_tokens": _mean(trig_recalls), "n_recall_scored": len(trig_recalls),
            "mean_token_precision_vs_authored": _mean(trig_precisions), "n_precision_scored": len(trig_precisions),
        },
        "negative_triggers": {
            "mean_jaccard": _mean(neg_jaccards), "n_jaccard_scored": len(neg_jaccards),
            "mean_recall_of_authored_tokens": _mean(neg_recalls), "n_recall_scored": len(neg_recalls),
            "mean_token_precision_vs_authored": _mean(neg_precisions), "n_precision_scored": len(neg_precisions),
            "note": "token-level agreement with the authored anti_triggers phrasing, not semantic "
                    "correctness — a derived phrase using different words for the same real "
                    "exclusion scores as imprecise here even when it is a correct negative trigger; "
                    "see the F5 report for phrase-level manual review of the worst cases.",
        },
    }


# ------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_local = sub.add_parser("local", help="a directory of **/SKILL.md")
    p_local.add_argument("root", type=Path)
    p_local.add_argument("--out-cards", type=Path, required=True)
    p_local.add_argument("--out-stats", type=Path, required=True)

    p_bench = sub.add_parser("skillretbench", help="the pinned SkillRetBench corpus")
    p_bench.add_argument("--out-cards", type=Path, required=True)
    p_bench.add_argument("--out-stats", type=Path, required=True)
    p_bench.add_argument("--out-agreement", type=Path, required=True)

    args = ap.parse_args(argv)

    if args.cmd == "local":
        skills = load_directory_corpus(args.root)
        enrichment = derive_mod.derive(skills)
        cards = build_cards(skills, enrichment)
        write_cards_jsonl(cards, args.out_cards)
        stats = compute_stats(skills, enrichment)
        args.out_stats.parent.mkdir(parents=True, exist_ok=True)
        args.out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(f"local: {len(skills)} skills -> {args.out_cards} ({len(cards)} cards), stats -> {args.out_stats}")

    elif args.cmd == "skillretbench":
        skills, authored = load_skillretbench_as_skills()
        enrichment = derive_mod.derive(skills)
        cards = build_cards(skills, enrichment, node="_root", publisher="skillretbench")
        write_cards_jsonl(cards, args.out_cards)
        stats = compute_stats(skills, enrichment)
        args.out_stats.parent.mkdir(parents=True, exist_ok=True)
        args.out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        agreement = evaluate_skillretbench(skills, enrichment, authored)
        args.out_agreement.parent.mkdir(parents=True, exist_ok=True)
        args.out_agreement.write_text(json.dumps(agreement, indent=2), encoding="utf-8")
        print(f"skillretbench: {len(skills)} skills -> {args.out_cards}, stats -> {args.out_stats}, "
              f"agreement -> {args.out_agreement}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
