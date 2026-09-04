#!/usr/bin/env python3
"""E1.2 acceptance: run the Router over the whole golden set and report ranking metrics.

Loads every case in tests/golden/*.yaml (220 labelled queries over the Meridian fixture),
resolves each case's `node` against a single shared Index/Router built from
examples/monorepo (Router 0.1, E0.2 + E1.1), and feeds each case's `(ranked_urns, case)` pair
into tools/eval/metrics.evaluate / metrics.by_category — the same pure functions a reviewer can
call by hand, so this script's numbers are never the only place a metric is computed.

Usage:
    python3 tools/eval/run_golden.py                    print the table, write a dated report
    python3 tools/eval/run_golden.py --check             also exit 1 on a regression vs baseline
    python3 tools/eval/run_golden.py --update-baseline   accept current numbers as the new baseline

Every run writes docs/reports/golden/<git-sha>.md (E1.2 acceptance: "results are committed per
run") — this is a plain snapshot for humans, not itself the regression gate. The gate compares
against docs/reports/golden/baseline.json, a small machine-readable snapshot updated deliberately
via --update-baseline whenever a weight or ranking change is intentional (analogous to updating a
golden-file test's expected output — a reviewed act, not something CI does on its own).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
MONOREPO_DIR = REPO_ROOT / "examples" / "monorepo"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
REPORTS_DIR = REPO_ROOT / "docs" / "reports" / "golden"
BASELINE_PATH = REPORTS_DIR / "baseline.json"

CATEGORY_FILES = (
    "multi_skill.yaml", "sibling_ambiguity.yaml", "no_applicable.yaml",
    "stale_adversarial.yaml", "simple.yaml",
)

# >= the largest k any metric slices (nDCG@10); completeness@4/distractor_rate@4 slice down from
# this same ranked list, so one Router.route() call per case serves every metric.
EVAL_K = 10

# The hook's real card cap (E1.5): what `select` emits and what an agent actually receives.
K_CARDS = 4

# Regression gate tolerance, in absolute metric points. "Worse" is metric-specific: lower is worse
# for the first group, higher is worse for distractor_rate (see tools/eval/metrics.py docstring on
# why distractor_rate and abstention are scored on their own axes rather than folded into hit/recall).
TOLERANCE = 0.02
HIGHER_IS_BETTER = ("hit@1", "recall@8", "ndcg@10", "completeness@4", "abstention_precision", "abstention_recall")
LOWER_IS_BETTER = ("distractor_rate@4",)


def _load_cli():
    """Import skills/guidefold/scripts/guidefold (no .py extension), same pattern as
    tests/golden/validate_golden.py, so node/URN resolution can never drift from the CLI."""
    loader = SourceFileLoader("guidefold_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load_metrics():
    spec = importlib.util.spec_from_file_location("gf_metrics", Path(__file__).resolve().parent / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cases() -> list:
    """Every case across the five category files, with `category` copied down from the
    file-level key onto each case dict (metrics.by_category reads case["category"])."""
    cases = []
    for fname in CATEGORY_FILES:
        doc = yaml.safe_load((GOLDEN_DIR / fname).read_text())
        category = doc.get("category")
        for c in doc.get("cases", []):
            c = dict(c)
            c.setdefault("category", category)
            cases.append(c)
    return cases


def run_cases(router, cases: list, k: int = EVAL_K) -> tuple:
    """Two result sets, because the Router produces two different orderings and conflating them
    silently measures the wrong thing.

    `Router.select` deliberately emits cards **general -> specific** (root-most first): that is the
    *injection* order E1.5 requires, so an agent reads org-wide guidance before team-specific
    guidance. It is a presentation decision made *after* ranking has already chosen membership.

    Feeding that order to a ranking metric asks "is the root-most card the most relevant one?",
    which is false almost by construction -- root skills are the general ones. Doing so understates
    hit@1 by ~64 points against this fixture. So:

      retrieval  -- `Router.score` order (score desc, tie-broken on urn). Answers "did ranking put
                    the right skills at the top?"  -> hit@1, recall@8, nDCG@10.
      injection  -- the <=4 cards `Router.select` actually emits, as a set. Answers "did the cards
                    the agent receives contain the whole answer, and no plausible-but-wrong one?"
                    -> completeness@4, distractor_rate@4.

    Both are reported. Neither alone is the router's quality.
    """
    retrieval, injection = [], []
    for c in cases:
        cands = router.candidates(c["query"], c["node"])
        scored = router.score(cands, c["query"], c["node"])
        retrieval.append(([s["urn"] for s in scored[:k]], c))
        injection.append(([r["urn"] for r in router.select(scored, k=K_CARDS)], c))
    return retrieval, injection


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                          cwd=REPO_ROOT).stdout.strip()
    return out or "nogit"


def _json_safe(m: dict) -> dict:
    """json has no NaN literal; store undefined metrics (e.g. hit@1 on an abstention-only
    stratum) as null so a later --check can tell "undefined" from "zero" apart."""
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in m.items()}


def write_report(sha: str, table: str, weights: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{sha}.md"
    lines = [
        f"# Golden-set report — {sha}", "",
        "Router 0.1 weights (`Index.weights` at build time):", "",
        "```json", json.dumps(weights, indent=2, sort_keys=True), "```", "",
        "```", table, "```", "",
    ]
    path.write_text("\n".join(lines))
    return path


def check_regression(overall: dict, per_cat: dict, baseline: dict) -> list:
    problems = []

    def _compare(cur: dict, base: dict, label: str):
        for m in HIGHER_IS_BETTER:
            c, b = cur.get(m), base.get(m)
            if c is None or b is None:
                continue
            if c < b - TOLERANCE:
                problems.append(f"{label}: {m} {c:.4f} regressed vs baseline {b:.4f} (tolerance {TOLERANCE})")
        for m in LOWER_IS_BETTER:
            c, b = cur.get(m), base.get(m)
            if c is None or b is None:
                continue
            if c > b + TOLERANCE:
                problems.append(f"{label}: {m} {c:.4f} regressed vs baseline {b:.4f} (tolerance {TOLERANCE})")

    _compare(overall, baseline.get("overall", {}), "OVERALL")
    for cat, base_m in (baseline.get("by_category") or {}).items():
        _compare(per_cat.get(cat, {}), base_m, cat)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                     help="exit 1 on a metric regression vs docs/reports/golden/baseline.json")
    ap.add_argument("--update-baseline", action="store_true",
                     help="write current metrics as the new committed baseline (a deliberate act, not automatic)")
    args = ap.parse_args(argv)

    cli = _load_cli()
    metrics = _load_metrics()

    cfg = cli.load_map(MONOREPO_DIR)
    idx = cli.Index.build(MONOREPO_DIR, cfg)
    router = cli.Router(idx)

    cases = load_cases()
    retrieval, injection = run_cases(router, cases)

    # Retrieval quality: did ranking put the right skills on top? (score order)
    overall = metrics.evaluate(retrieval)
    per_cat = metrics.by_category(retrieval)
    # Injection quality: did the <=4 cards the agent receives hold the answer, and no distractor?
    inj_overall = metrics.evaluate(injection, k_cards=K_CARDS)
    inj_per_cat = metrics.by_category(injection, k_cards=K_CARDS)

    table = ("RETRIEVAL  (Router.score order — hit@1 / recall@8 / nDCG@10 are read from here)\n"
             + metrics.format_table(overall, per_cat)
             + "\n\nINJECTION  (the <=4 cards Router.select emits — completeness@4 / "
               "distractor_rate@4 are read from here)\n"
             + metrics.format_table(inj_overall, inj_per_cat))
    print(table)

    # The gate reads each metric from the table that actually answers its question.
    for k in ("completeness@4", "distractor_rate@4"):
        overall[k] = inj_overall.get(k, float("nan"))
        for c in per_cat:
            if c in inj_per_cat:
                per_cat[c][k] = inj_per_cat[c].get(k, float("nan"))

    sha = git_sha()
    report_path = write_report(sha, table, idx.weights)
    print(f"\nwrote {report_path.relative_to(REPO_ROOT)}")

    exit_code = 0
    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "sha": sha,
            "overall": _json_safe(overall),
            "by_category": {c: _json_safe(m) for c, m in per_cat.items()},
        }, indent=2, sort_keys=True) + "\n")
        print(f"updated baseline: {BASELINE_PATH.relative_to(REPO_ROOT)}")
    elif args.check:
        if not BASELINE_PATH.exists():
            print(f"\nno baseline at {BASELINE_PATH.relative_to(REPO_ROOT)} yet — "
                  f"run with --update-baseline once to create it")
        else:
            baseline = json.loads(BASELINE_PATH.read_text())
            problems = check_regression(overall, per_cat, baseline)
            if problems:
                print("\nREGRESSION vs baseline:")
                for p in problems:
                    print(f"  - {p}")
                exit_code = 1
            else:
                print("\nno regression vs baseline")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
