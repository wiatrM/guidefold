#!/usr/bin/env python3
"""One-configuration-at-a-time evaluation harness for the E1 config-selection experiment
(docs/reports/tuning/E1-config-selection.md).

Deliberately NOT an automated grid search. The coordinator's brief is explicit that a naive
sweep "will always find an improvement -- including on pure noise" with only 220 golden cases,
and asks for coordinate descent driven by judgement (principled field-weight alternatives, a
per-stratum non-regression check, a hard split between tuning and verification) rather than a
script picking the best of a Cartesian product. So this tool evaluates exactly one configuration
per invocation and prints/writes the numbers; a human (or the agent doing the tuning) decides
what to try next and records the trail in the report.

Reuses, never reimplements:
  - tools/eval/metrics.py (`evaluate`, `by_category`) for every metric.
  - tools/eval/run_golden.py's own CLI-loading and case-loading approach (duplicated in
    miniature here because run_golden.py's module-level REPORTS_DIR side effect and argparse
    main() aren't reusable as a library import without side effects -- see _load_cli below).
  - docs/reports/tuning/split.json (tools/eval/split_golden.py) for which cases are tune vs
    holdout. This script never lets a "holdout" split combine with "coordinate descent is still
    in progress" -- that discipline is enforced by the operator (only look at holdout once, at
    the end), not by code, but every invocation prints which split it used so a transcript is
    self-documenting.

A "configuration" is:
  - `weights`: a dict merged over Index.DEFAULT_WEIGHTS (field.*, w_scope, w_ppr, ppr_mode,
    abstain_mode, abstain_margin_threshold, closure_decay_num/den, ...) -- exactly the mechanism
    guidefold.yaml's `router.weights` already uses, so this never needs a code change.
  - `cls`: a dict of Index class-attribute overrides not exposed as weights (K1, B, RRF_K,
    RRF_SCALE) -- monkeypatched onto the Index class for the duration of one build, then
    restored, so configurations never leak into each other.

Usage:
    python3 tools/eval/sweep.py --split tune
    python3 tools/eval/sweep.py --split tune --weights '{"w_scope": 100}'
    python3 tools/eval/sweep.py --split holdout --cls '{"RRF_K": 20}' --json-out result.json
    python3 tools/eval/sweep.py --split all --name "baseline"
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
MONOREPO_DIR = REPO_ROOT / "examples" / "monorepo"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
SPLIT_PATH = REPO_ROOT / "docs" / "reports" / "tuning" / "split.json"

CATEGORY_FILES = (
    "multi_skill.yaml", "sibling_ambiguity.yaml", "no_applicable.yaml",
    "stale_adversarial.yaml", "simple.yaml",
)
EVAL_K = 10
K_CARDS = 4

# Class attributes that live outside Index.weights (not exposed via guidefold.yaml router.weights
# today) but that the coordinator's brief explicitly asks to sweep (RRF_K, K1, B).
CLASS_OVERRIDABLE = ("K1", "B", "RRF_K", "RRF_SCALE")


def _load_cli():
    loader = SourceFileLoader("guidefold_sweep_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load_metrics():
    spec = importlib.util.spec_from_file_location("gf_sweep_metrics", Path(__file__).resolve().parent / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cases() -> list:
    cases = []
    for fname in CATEGORY_FILES:
        doc = yaml.safe_load((GOLDEN_DIR / fname).read_text())
        category = doc.get("category")
        for c in doc.get("cases", []):
            c = dict(c)
            c.setdefault("category", category)
            cases.append(c)
    return cases


def load_split() -> dict:
    return json.loads(SPLIT_PATH.read_text())["split"]


def select_cases(cases: list, split_name: str, split_map: dict) -> list:
    if split_name == "all":
        return cases
    if split_name not in ("tune", "holdout"):
        raise ValueError(f"unknown split {split_name!r} (want tune, holdout, or all)")
    return [c for c in cases if split_map.get(c["id"]) == split_name]


def run_cases(cli, router, cases: list, k: int = EVAL_K) -> tuple:
    """Identical shape to run_golden.run_cases -- retrieval (Router.score order) and injection
    (Router.select order) reported separately, per docs/reports/golden/README.md."""
    retrieval, injection = [], []
    for c in cases:
        cands = router.candidates(c["query"], c["node"])
        scored = router.score(cands, c["query"], c["node"])
        retrieval.append(([s["urn"] for s in scored[:k]], c))
        injection.append(([r["urn"] for r in router.select(scored, k=K_CARDS)], c))
    return retrieval, injection


def build_router(cli, weights: dict, cls: dict):
    """Build a fresh Index+Router with `weights` merged over DEFAULT_WEIGHTS and `cls` applied as
    temporary Index class-attribute overrides. Returns (router, restore) -- caller must call
    restore() when done (a context manager would be nicer but this keeps the call sites in main()
    linear and obviously correct: build, use, restore, in that order, every time)."""
    originals = {}
    for k, v in (cls or {}).items():
        if k not in CLASS_OVERRIDABLE:
            raise ValueError(f"not a recognised class override: {k} (want one of {CLASS_OVERRIDABLE})")
        originals[k] = getattr(cli.Index, k)
        setattr(cli.Index, k, v)

    def restore():
        for k, v in originals.items():
            setattr(cli.Index, k, v)

    try:
        cfg = cli.load_map(MONOREPO_DIR)
        cfg.setdefault("router", {})["weights"] = dict(weights or {})
        idx = cli.Index.build(MONOREPO_DIR, cfg)
        router = cli.Router(idx)
        return router, idx, restore
    except Exception:
        restore()
        raise


def evaluate_config(split_name: str, weights: dict = None, cls: dict = None) -> dict:
    """The one function every caller (this script's main(), and any ad-hoc analysis) should use.
    Returns retrieval/injection overall + by_category metrics over exactly the cases in
    `split_name` ("tune", "holdout", or "all")."""
    cli = _load_cli()
    metrics = _load_metrics()
    cases = load_cases()
    split_map = load_split()
    chosen = select_cases(cases, split_name, split_map)

    router, idx, restore = build_router(cli, weights, cls)
    try:
        retrieval, injection = run_cases(cli, router, chosen)
    finally:
        restore()

    return {
        "split": split_name,
        "n_cases": len(chosen),
        "weights_override": weights or {},
        "cls_override": cls or {},
        "effective_weights": idx.weights,
        "retrieval": {
            "overall": metrics.evaluate(retrieval),
            "by_category": metrics.by_category(retrieval),
        },
        "injection": {
            "overall": metrics.evaluate(injection, k_cards=K_CARDS),
            "by_category": metrics.by_category(injection, k_cards=K_CARDS),
        },
    }


def _fmt_row(label: str, m: dict) -> str:
    def g(k):
        v = m.get(k)
        return "     —" if v is None or (isinstance(v, float) and v != v) else f"{v:>6.4f}"
    return (f"{label:<22}{m.get('n', 0):>4}"
            f"{g('hit@1')}{g('recall@8')}{g('ndcg@10')}{g('completeness@4')}"
            f"{g('distractor_rate@4')}{g('abstention_precision')}{g('abstention_recall')}{g('coverage')}")


def print_table(title: str, overall: dict, by_cat: dict):
    print(f"\n{title}")
    header = (f"{'stratum':<22}{'n':>4}{'hit@1':>7}{'recall@8':>7}{'ndcg@10':>7}"
              f"{'comp@4':>7}{'distr@4':>7}{'abs_p':>7}{'abs_r':>7}{'cov':>7}")
    print(header)
    print("-" * len(header))
    for cat, m in by_cat.items():
        print(_fmt_row(cat, m))
    print(_fmt_row("OVERALL", overall))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True, choices=("tune", "holdout", "all"))
    ap.add_argument("--weights", default="{}", help="JSON dict merged over Index.DEFAULT_WEIGHTS")
    ap.add_argument("--cls", default="{}", help="JSON dict of Index class-attribute overrides "
                                                 f"({', '.join(CLASS_OVERRIDABLE)})")
    ap.add_argument("--name", default=None, help="label for the printed tables")
    ap.add_argument("--json-out", default=None, help="also write the full result dict as JSON here")
    args = ap.parse_args(argv)

    weights = json.loads(args.weights)
    cls = json.loads(args.cls)
    result = evaluate_config(args.split, weights, cls)

    label = args.name or f"weights={weights} cls={cls}"
    print(f"=== {label}  (split={args.split}, n={result['n_cases']}) ===")
    print_table("RETRIEVAL (Router.score order)", result["retrieval"]["overall"], result["retrieval"]["by_category"])
    print_table("INJECTION (Router.select order)", result["injection"]["overall"], result["injection"]["by_category"])

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
