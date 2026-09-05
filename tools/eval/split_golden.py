#!/usr/bin/env python3
"""Generate the tune/holdout split for the E1 config-selection experiment
(docs/reports/tuning/E1-config-selection.md).

Mandatory methodology (see that report and the coordinator's brief): a stratified 60/40 split of
the 220 golden cases into `tune` and `holdout`, seeded and committed so it is reproducible, with
every one of the five `category` strata represented in both halves in proportion. Coordinate
descent is tuned *only* on `tune`; the winning configuration is verified once, at the end, on
`holdout` -- never the other way around, and `holdout` is never consulted while choosing.

This script is the provenance record for how docs/reports/tuning/split.json was produced. Running
it again reproduces the exact same file (same seed, same fixed category-processing order, same
`random.Random` algorithm) -- it does not need to be re-run for the split to be trusted, but it
means the split is not a hand-edited artifact either.

Usage:
    python3 tools/eval/split_golden.py                 print counts, write the split file
    python3 tools/eval/split_golden.py --check          verify the on-disk file matches a fresh
                                                          regeneration (exits 1 on mismatch)
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
SPLIT_PATH = REPO_ROOT / "docs" / "reports" / "tuning" / "split.json"

# Fixed processing order -- the same order run_golden.py reads the five category files in. The
# split is a pure function of (SEED, this order, the case ids present in each file today).
CATEGORY_FILES = (
    "multi_skill.yaml", "sibling_ambiguity.yaml", "no_applicable.yaml",
    "stale_adversarial.yaml", "simple.yaml",
)

# Arbitrary but fixed: any constant works equally well for reproducibility, this is not a tuned
# hyperparameter and was never adjusted to make the split come out more favourably for any
# candidate configuration (it was picked once, before any config was evaluated).
SEED = 20260905

TUNE_FRACTION = 0.6


def _category_of(fname: str) -> str:
    return fname[: -len(".yaml")]


def load_ids_by_category() -> dict[str, list[str]]:
    """category -> sorted list of case ids, read straight from tests/golden/*.yaml."""
    out = {}
    for fname in CATEGORY_FILES:
        doc = yaml.safe_load((GOLDEN_DIR / fname).read_text())
        cat = doc.get("category") or _category_of(fname)
        ids = sorted(c["id"] for c in doc.get("cases", []))
        out[cat] = ids
    return out


def build_split() -> dict:
    ids_by_category = load_ids_by_category()
    rng = random.Random(SEED)
    split = {}
    counts = {}
    for fname in CATEGORY_FILES:
        cat = _category_of(fname)
        ids = list(ids_by_category[cat])
        rng.shuffle(ids)  # in place, advances the single shared Random in fixed category order
        n = len(ids)
        n_tune = round(n * TUNE_FRACTION)
        tune_ids, holdout_ids = ids[:n_tune], ids[n_tune:]
        for i in tune_ids:
            split[i] = "tune"
        for i in holdout_ids:
            split[i] = "holdout"
        counts[cat] = {"n": n, "tune": len(tune_ids), "holdout": len(holdout_ids)}
    return {
        "seed": SEED,
        "tune_fraction": TUNE_FRACTION,
        "category_order": [_category_of(f) for f in CATEGORY_FILES],
        "algorithm": "one random.Random(seed), categories processed in category_order; per "
                     "category, sort case ids, rng.shuffle in place, first round(n*tune_fraction) "
                     "ids are tune, the rest are holdout.",
        "counts": counts,
        "split": dict(sorted(split.items())),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                     help="verify docs/reports/tuning/split.json matches a fresh regeneration")
    args = ap.parse_args(argv)

    fresh = build_split()

    if args.check:
        if not SPLIT_PATH.exists():
            print(f"no split file at {SPLIT_PATH}")
            return 1
        on_disk = json.loads(SPLIT_PATH.read_text())
        if on_disk != fresh:
            print(f"{SPLIT_PATH} does NOT match a fresh regeneration from tests/golden/*.yaml")
            return 1
        print(f"{SPLIT_PATH} matches a fresh regeneration -- reproducible")
        return 0

    SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_PATH.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    total_tune = sum(c["tune"] for c in fresh["counts"].values())
    total_holdout = sum(c["holdout"] for c in fresh["counts"].values())
    print(f"wrote {SPLIT_PATH.relative_to(REPO_ROOT)}")
    print(f"{'category':<20}{'n':>6}{'tune':>8}{'holdout':>10}")
    for cat, c in fresh["counts"].items():
        print(f"{cat:<20}{c['n']:>6}{c['tune']:>8}{c['holdout']:>10}")
    print(f"{'TOTAL':<20}{total_tune + total_holdout:>6}{total_tune:>8}{total_holdout:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
