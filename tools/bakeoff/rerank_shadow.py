#!/usr/bin/env python3
"""rerank_shadow.py — offline reranker over E1.6 shadow telemetry.

Tier 2 (ADR-0020): this script imports `arms.py` (torch/transformers) freely and is never
imported by `skills/guidefold/scripts/guidefold`.

`find --experimental` (the shipped CLI) writes one `shadow_request` JSON line per call to
`.guidefold/telemetry/shadow-<UTC date>.jsonl`: a request id, ISO timestamp, cli version, index
sha, node, the top-20 *retrieval-order* URNs with their baseline scores, a SHA-256 hash of the
query, and -- only with `--telemetry-raw` -- the raw query text itself. Shadow mode means the
CLI's own printed result is never touched; this script is the "measure the reranker" half of the
story, run offline, on a schedule, never on the request path.

For every `shadow_request` that does not already have a matching `shadow_verdict` (matched by
`request_id`), this script:
  1. loads the Meridian fixture corpus once (`corpus.load_corpus`, shared with every bake-off arm
     and the golden-set report -- never reimplemented here),
  2. resolves the request's top-20 URNs against that corpus,
  3. scores all of them against the query in ONE batched forward pass
     (`arms.Reranker.score_batch` -- the E1.6 non-negotiable: unbatched this is ~8s/pair, ~160s
     for one request's top-20),
  4. appends a `shadow_verdict` record to the SAME file: request_id, the reranked order+scores,
     whether rank-1 changed vs the baseline, the Spearman rank correlation between baseline and
     reranked order, and the batched wall-clock time actually measured for that request.

CAVEAT, not an oversight: a SHA-256 hash cannot be reversed into the query text the reranker
needs. A `shadow_request` written without `--telemetry-raw` has no `query` field and therefore
CANNOT be scored -- it is counted and skipped, never guessed at. Only requests captured with
`--telemetry-raw` can produce a verdict.

Resumable: every existing `shadow_verdict`'s `request_id` is collected before any scoring is
done, across every `shadow-*.jsonl` file in the telemetry directory, so a rerun (cron, or after
every fresh batch of `find --experimental` calls) never re-scores a request that already has a
verdict — see `tools/bakeoff/tests/test_rerank_shadow.py::test_resumable_skips_already_scored`.

Usage:
    python3 tools/bakeoff/rerank_shadow.py [--telemetry-dir DIR] [--fixture-root DIR]

Env (same as every other tools/bakeoff/ script; the model is Tier 2, CI/offline only):
    HF_HOME, HF_HUB_OFFLINE=1
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arms  # noqa: E402  (Reranker, SKILLROUTER_RERANKER)
from corpus import FIXTURE_ROOT, load_corpus  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TELEMETRY_DIR = REPO_ROOT / ".guidefold" / "telemetry"


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _spearman(baseline_urns: list, reranked_urns: list) -> float:
    """Spearman rank correlation between two orderings of the SAME set of urns.

    Both orderings are permutations of one another (the reranker only reorders the baseline's
    top-20, it never adds or drops a urn), so this is the no-ties case and `scipy.stats.spearmanr`
    on rank-position vectors is exact -- reused here and in `report_b6.py` rather than each
    re-deriving its own formula.
    """
    from scipy.stats import spearmanr

    if len(baseline_urns) < 2:
        return float("nan")
    baseline_rank = {u: i for i, u in enumerate(baseline_urns)}
    a = list(range(len(baseline_urns)))
    b = [baseline_rank[u] for u in reranked_urns]
    rho, _p = spearmanr(a, b)
    return float(rho)


def already_scored_request_ids(telemetry_dir: Path) -> set:
    """Every request_id that already has a `shadow_verdict`, across all shadow-*.jsonl files.

    Scanned fresh on every run (no separate state file) so resumability holds even if verdicts
    were appended by a different invocation, a different machine, or a manual edit.
    """
    seen = set()
    for path in sorted(telemetry_dir.glob("shadow-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "shadow_verdict" and rec.get("request_id"):
                seen.add(rec["request_id"])
    return seen


def pending_requests(telemetry_dir: Path, already_scored: set) -> list:
    """(path, shadow_request record) for every request without a verdict yet, oldest file first."""
    pending = []
    for path in sorted(telemetry_dir.glob("shadow-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "shadow_request":
                continue
            if rec.get("request_id") in already_scored:
                continue
            pending.append((path, rec))
    return pending


def score_pending(telemetry_dir: Path, corpus_records: list, reranker=None) -> dict:
    """Score every pending shadow_request and append a shadow_verdict for each, in place.

    `reranker` is injectable (defaults to a real `arms.Reranker()`) purely for testability --
    tests pass a fast `FakeReranker` so the resumability guarantee can be proven without loading
    the real 0.6B model. Returns a summary dict: counts of scored / skipped-no-raw-query /
    already-done, plus wall-clock timings for the scored requests.
    """
    if reranker is None:
        reranker = arms.Reranker()
    by_urn = {r.urn: r for r in corpus_records}

    already = already_scored_request_ids(telemetry_dir)
    pending = pending_requests(telemetry_dir, already)

    scored = 0
    skipped_no_raw_query = 0
    skipped_no_candidates = 0
    seconds = []

    for path, req in pending:
        query = req.get("query")
        if not query:
            # Hash-only request: cannot be reversed into the text the model needs. Not an error --
            # this is the expected shape of most production telemetry under the privacy default.
            skipped_no_raw_query += 1
            continue
        top20 = req.get("top20") or []
        baseline_urns = [c["urn"] for c in top20]
        candidate_urns = [u for u in baseline_urns if u in by_urn]
        if not candidate_urns:
            skipped_no_candidates += 1
            continue
        records = [by_urn[u] for u in candidate_urns]

        t0 = time.time()
        pair_scores = reranker.score_batch(query, records)
        elapsed = time.time() - t0
        seconds.append(elapsed)

        reranked = sorted(zip(pair_scores, candidate_urns), key=lambda x: (-x[0], x[1]))
        reranked_urns = [u for _, u in reranked]

        verdict = {
            "type": "shadow_verdict",
            "request_id": req["request_id"],
            "ts": _utc_now_iso(),
            "reranker_model": arms.SKILLROUTER_RERANKER[0],
            "reranker_revision": arms.SKILLROUTER_RERANKER[1],
            "batched_seconds": round(elapsed, 3),
            "n_candidates": len(candidate_urns),
            "reranked_top20": [{"urn": u, "score": s} for s, u in reranked],
            "rank1_baseline": baseline_urns[0] if baseline_urns else None,
            "rank1_reranked": reranked_urns[0] if reranked_urns else None,
            "rank1_changed": bool(baseline_urns and reranked_urns and baseline_urns[0] != reranked_urns[0]),
            "spearman_vs_baseline": _spearman(candidate_urns, reranked_urns),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(verdict, sort_keys=True) + "\n")
        scored += 1

    return {
        "pending": len(pending),
        "scored": scored,
        "skipped_no_raw_query": skipped_no_raw_query,
        "skipped_no_candidates": skipped_no_candidates,
        "already_scored": len(already),
        "seconds": seconds,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--telemetry-dir", type=Path, default=DEFAULT_TELEMETRY_DIR,
                     help=f"directory of shadow-*.jsonl files (default: {DEFAULT_TELEMETRY_DIR})")
    ap.add_argument("--fixture-root", type=Path, default=FIXTURE_ROOT,
                     help="monorepo whose skills the shadow requests were ranked over "
                          f"(default: {FIXTURE_ROOT})")
    args = ap.parse_args(argv)

    if not args.telemetry_dir.exists():
        print(f"no telemetry directory at {args.telemetry_dir} -- nothing to score")
        return 0

    corpus_records = load_corpus(args.fixture_root)
    summary = score_pending(args.telemetry_dir, corpus_records)

    print(f"pending requests found:      {summary['pending']}")
    print(f"already had a verdict:       {summary['already_scored']}")
    print(f"scored this run:             {summary['scored']}")
    print(f"skipped (hash-only query):   {summary['skipped_no_raw_query']}")
    print(f"skipped (no known urns):     {summary['skipped_no_candidates']}")
    if summary["seconds"]:
        avg = sum(summary["seconds"]) / len(summary["seconds"])
        print(f"batched per-query time:      avg {avg:.2f}s  "
              f"min {min(summary['seconds']):.2f}s  max {max(summary['seconds']):.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
