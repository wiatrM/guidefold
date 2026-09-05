#!/usr/bin/env python3
"""report_b6.py — the E1.6 B6 golden-set row: the reranker applied to B5's top-20.

Reuses, never reimplements:
  * `corpus.load_corpus`               -- the Meridian fixture corpus every arm is graded on.
  * `arms.arm_b5` / `arms.Reranker`    -- B5's candidate list and the batched cross-encoder.
  * `tools/eval/run_golden.load_cases` -- the 220 labelled golden queries (same 5 category files
                                           the CLI's own Router is graded on).
  * `tools/eval/metrics.evaluate` / `by_category` / `format_table` -- the SAME metric definitions
                                           and table layout used for every other retrieval report
                                           in this repo, so a B6 number and a Router number are
                                           never computed by two different formulas.
  * `rerank_shadow._spearman`          -- the same no-tie Spearman helper the shadow-verdict
                                           writer uses, not a second implementation.

Retrieval order only. Bake-off arms (arms.py) produce a single ranked URN list each -- unlike the
shipped CLI's Router, they have no separate candidates->score->select pipeline, so there is no
"injection order" distinct from "retrieval order" to report here (see docs/reports/golden/README.md
for that distinction, which applies to the Router, not to these arms).

KNOWN LIMITATION, not fixed here (out of scope for E1.6): arms.py's B1-B6 rank over the WHOLE
corpus regardless of a case's `node`/cwd -- there is no per-node visibility filter, unlike the
CLI's own Router.candidates(). A case whose correct answer is only visible from one node is graded
exactly the same as if every skill were visible everywhere. This affects B5 and B6 identically
(B6 only reorders B5's own candidate list), so it should not bias the *B5-vs-B6 comparison* this
script exists to make, but it does mean neither row here is directly comparable to the CLI
Router's own golden-set numbers in docs/reports/golden/.

FULL-SET COST is hardware-dependent, which is why the default below is still a stratified sample
rather than assuming `--full` is always cheap: batched B6 scoring was measured at ~100s/query on a
CPU-only dev machine (20 candidates/query, one forward pass, warm model -- see
tools/bakeoff/README.md's batched-timing note), which puts the full 220-query set at ~6 hours --
infeasible for a normal PR pass. On a CUDA GPU (this class of 0.6B model, `Encoder`/`Reranker` are
both device-aware -- see encode.py's `DEVICE`/`_local_model_path`/CUDA selection), the same 220 queries
measured 172s wall-clock end to end, ~0.78s/query mean -- cheap enough that `--full` should be the
default choice whenever a GPU is available; see README.md's "E1.6: batched B6, GPU-verified, full
golden set" section for the real numbers from that run. `STRATA_SAMPLE_SIZE` below picks the same
number of cases from EVERY one of the 5 strata (multi_skill, sibling_ambiguity, no_applicable,
stale_adversarial, simple) with a fixed seed, so a CPU-only run still represents every stratum and
stays reproducible -- never a silent scope cut. Pass `--full` to run all 220 (seconds on a GPU,
budget ~6h on CPU alone), or `--per-stratum N` for a different sample size.

Usage:
    python3 tools/bakeoff/report_b6.py                    # stratified sample (default size below)
    python3 tools/bakeoff/report_b6.py --per-stratum 15    # bigger sample
    python3 tools/bakeoff/report_b6.py --full              # all 220 (very slow, see above)
"""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import time
from pathlib import Path

BAKEOFF_DIR = Path(__file__).resolve().parent
REPO_ROOT = BAKEOFF_DIR.parents[1]
EVAL_DIR = BAKEOFF_DIR.parents[0] / "eval"
sys.path.insert(0, str(BAKEOFF_DIR))
sys.path.insert(0, str(EVAL_DIR))

# Mirrors tools/eval/run_golden.py's docs/reports/golden/<sha>.md convention -- same idea (a
# plain, committed, per-run snapshot for humans), no regression gate/baseline.json here: B6 is a
# one-off "does the reranker earn its cost" measurement, not something CI enforces on every push.
REPORTS_DIR = Path(os.environ["GUIDEFOLD_BAKEOFF_REPORTS"]) if os.environ.get("GUIDEFOLD_BAKEOFF_REPORTS") \
    else REPO_ROOT / "docs" / "reports" / "bakeoff"

import arms  # noqa: E402
from corpus import load_corpus  # noqa: E402
import metrics  # noqa: E402
from run_golden import load_cases  # noqa: E402
from rerank_shadow import _spearman  # noqa: E402 -- shared with the shadow-verdict writer

# Picked so every stratum is represented and a run finishes in well under two hours even at the
# measured ~100s/query (5 strata x 8 = 40 queries x ~100s =~ 65-70 minutes). See docstring above.
STRATA_SAMPLE_SIZE = 8
RANDOM_SEED = 1234  # fixed so the sample -- and therefore the reported numbers -- is reproducible

EVAL_K = 10  # matches tools/eval/run_golden.py's EVAL_K (>= nDCG@10's k)


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                          cwd=REPO_ROOT).stdout.strip()
    return out or "nogit"


def write_report(sha: str, header_lines: list, b5_table: str, b6_table: str, tail_lines: list) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{sha}.md"
    lines = [f"# B6 bake-off report — {sha}", "", *header_lines, "",
             "B5  (RRF of B1 BM25 + B4 static dense -- retrieval order)", "",
             "```", b5_table, "```", "",
             "B6  (B5's top-20 reranked by SkillRouter-Reranker-0.6B, batched -- retrieval order)", "",
             "```", b6_table, "```", "", *tail_lines, ""]
    path.write_text("\n".join(lines))
    return path


def stratified_sample(cases: list, n_per_stratum: int, seed: int) -> tuple:
    """n_per_stratum cases from each category (all of it if the stratum is smaller). Returns
    (sampled_cases, plan) where plan maps category -> (n_sampled, n_total) for the report header."""
    by_cat: dict = {}
    for c in cases:
        by_cat.setdefault(c.get("category", "unknown"), []).append(c)
    rng = random.Random(seed)
    sampled, plan = [], {}
    for cat, items in sorted(by_cat.items()):
        k = min(n_per_stratum, len(items))
        chosen = rng.sample(items, k) if k < len(items) else list(items)
        plan[cat] = (k, len(items))
        sampled.extend(chosen)
    return sampled, plan


def run_b5_b6(cases: list, corpus_records: list, reranker) -> dict:
    """One pass over `cases`: B5's own candidate order (baseline) and the batched reranked order
    (B6), plus the agreement stats the story asks for (rank-1 change rate, Spearman vs baseline)
    and the batched per-query wall-clock actually measured."""
    by_urn = {r.urn: r for r in corpus_records}
    b5_results, b6_results = [], []
    rank1_changed = 0
    spearmans = []
    seconds = []

    for case in cases:
        query = case["query"]
        baseline_urns = arms.arm_b5(query, corpus_records, limit=20)
        candidate_urns = [u for u in baseline_urns if u in by_urn]
        records = [by_urn[u] for u in candidate_urns]

        t0 = time.time()
        scores = reranker.score_batch(query, records) if records else []
        seconds.append(time.time() - t0)

        reranked = sorted(zip(scores, candidate_urns), key=lambda x: (-x[0], x[1]))
        reranked_urns = [u for _, u in reranked]

        b5_results.append((baseline_urns[:EVAL_K], case))
        b6_results.append((reranked_urns[:EVAL_K], case))

        if baseline_urns and reranked_urns and baseline_urns[0] != reranked_urns[0]:
            rank1_changed += 1
        spearmans.append(_spearman(candidate_urns, reranked_urns))

    return {
        "b5_results": b5_results,
        "b6_results": b6_results,
        "n": len(cases),
        "rank1_changed": rank1_changed,
        "spearmans": [s for s in spearmans if s == s],  # drop NaN (< 2 candidates)
        "seconds": seconds,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-stratum", type=int, default=STRATA_SAMPLE_SIZE,
                     help=f"cases to sample per stratum (default {STRATA_SAMPLE_SIZE})")
    ap.add_argument("--full", action="store_true", help="run all 220 cases (ignores --per-stratum)")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    ap.add_argument("--write-report", action="store_true",
                     help=f"also write docs/reports/bakeoff/<sha>.md (mirrors tools/eval/run_golden.py's "
                          f"docs/reports/golden/<sha>.md convention; override the dir with "
                          f"${{{'GUIDEFOLD_BAKEOFF_REPORTS'}}})")
    args = ap.parse_args(argv)

    all_cases = load_cases()
    per_stratum = 10 ** 9 if args.full else args.per_stratum
    cases, plan = stratified_sample(all_cases, per_stratum, args.seed)

    print(f"golden set: {len(all_cases)} cases total across {len(plan)} strata")
    if args.full:
        print("running the FULL set (--full) -- this is slow, see this script's docstring")
    else:
        print(f"stratified sample: {per_stratum} per stratum, seed={args.seed}")
    for cat, (k, total) in sorted(plan.items()):
        print(f"  {cat:<20} {k}/{total}")
    print(f"total cases this run: {len(cases)}\n")

    corpus_records = load_corpus()
    reranker = arms.Reranker()

    t_start = time.time()
    out = run_b5_b6(cases, corpus_records, reranker)
    wall_clock = time.time() - t_start

    b5_overall = metrics.evaluate(out["b5_results"])
    b5_per_cat = metrics.by_category(out["b5_results"])
    b6_overall = metrics.evaluate(out["b6_results"])
    b6_per_cat = metrics.by_category(out["b6_results"])

    b5_table = metrics.format_table(b5_overall, b5_per_cat)
    b6_table = metrics.format_table(b6_overall, b6_per_cat)

    print("B5  (RRF of B1 BM25 + B4 static dense -- retrieval order)")
    print(b5_table)
    print()
    print("B6  (B5's top-20 reranked by SkillRouter-Reranker-0.6B, batched -- retrieval order)")
    print(b6_table)
    print()

    n = out["n"]
    rate = out["rank1_changed"] / n if n else float("nan")
    tail_lines = [f"rank-1 changed (B6 vs B5): {out['rank1_changed']}/{n} ({rate:.1%})"]
    if out["spearmans"]:
        avg_rho = sum(out["spearmans"]) / len(out["spearmans"])
        tail_lines.append(
            f"Spearman rank correlation, B6 vs B5 order: mean {avg_rho:.4f} "
            f"over {len(out['spearmans'])} queries "
            f"(min {min(out['spearmans']):.4f}, max {max(out['spearmans']):.4f})")
    if out["seconds"]:
        avg_s = sum(out["seconds"]) / len(out["seconds"])
        tail_lines.append(
            f"batched reranker time per query: mean {avg_s:.2f}s "
            f"(min {min(out['seconds']):.2f}s, max {max(out['seconds']):.2f}s), "
            f"total {sum(out['seconds']):.1f}s over {len(out['seconds'])} queries")
    tail_lines.append(f"\nwall-clock for this run (B5 + B6 + bookkeeping, {n} queries): {wall_clock:.1f}s")
    for line in tail_lines:
        print(line)

    if args.write_report:
        sha = git_sha()
        header_lines = [
            f"golden set: {len(all_cases)} cases total across {len(plan)} strata",
            "running the FULL set (`--full`)" if args.full
            else f"stratified sample: {per_stratum} per stratum, seed={args.seed}",
        ]
        header_lines += [f"- {cat}: {k}/{total}" for cat, (k, total) in sorted(plan.items())]
        header_lines.append(f"- total cases this run: {len(cases)}")
        header_lines.append(
            "\n**Determinism note:** GPU floating-point reductions are not bit-reproducible across "
            "batch sizes or hardware (cuBLAS/cuDNN kernel selection varies), so these B6 numbers are "
            "offline evidence about the reranker only -- they are not part of, and do not affect, the "
            "shipped CLI's integer-only runtime determinism guarantee.")
        path = write_report(sha, header_lines, b5_table, b6_table, tail_lines)
        print(f"\nwrote {path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
