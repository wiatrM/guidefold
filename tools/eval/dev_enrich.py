"""tools/eval/dev_enrich.py — F5 (offline enrichment) family evaluation, dev only.

The gate this script runs, which PR #31 explicitly did NOT run: does deriving triggers,
negative_triggers and requires/similar (tools/enrich/derive.py, pure function over
name+description+body, no authored fields) actually improve retrieval on the frozen dev split
(tools/eval/corpora.py::load_skillret_dev() — 1 000 SKILLRET *train* queries against the full
10 123-skill SKILLRET train pool)? PR #31's own numbers (edges P/R 0.60/0.95, triggers 0.59/0.43,
negative triggers 0.69/0.81) are agreement with SkillRetBench's AUTHORED fields — a sanity check
on the extractor's shape, not a retrieval gate. The dev corpus has ZERO authored triggers /
negative_triggers / requires on any of its 10 123 skills, so it is the honest test of whether the
extractor can manufacture useful signal on skills that were never hand-given one.

This script never touches test-A or test-B. It never edits skills/guidefold/scripts/guidefold —
that CLI is read-only here, loaded exactly as tools/eval/dev_sparse.py loads it. Every arm's
baseline is P-flat (dev_sparse's own frozen "all field weights = 1" variant, PR #36): each arm
below changes exactly ONE input relative to P-flat's cards, holding the index/router weights,
the candidate pool, and the product pipeline (policy_filter -> candidates -> score -> select)
fixed. `tools/eval/dev_sparse.py` is reused wholesale for card/case construction, the product-path
runner, the bootstrap CI method and the JSONL writer -- nothing here reimplements the ranking
pipeline or the metric definitions (tools/eval/metrics.py).

Arms (docs/reports/bakeoff/DENSE-PROGRAM.md F5 dev budget, <= 4 configurations):
  P-flat        baseline. No derived fields. (= dev_sparse's own P-flat.)
  E-triggers    derived `triggers` indexed as the `triggers` BM25F field (weight 1, like every
                other field under P-flat). Nothing else changes.
  E-negatives   derived `negative_triggers` made active in Router.policy_filter (a hard drop).
                The risky arm: PR #31 found a boilerplate phrase recurring on 221 skills before a
                frequency guard was added. This script asserts and reports, prominently, how many
                GOLD skills (case["relevant"]) the derived negatives drop -- policy_filter drops
                0/10 123 with no negatives, so any drop here is caused by this arm alone.
  E-edges       derived `requires` (and, inertly, `similar`) feeding Router.select()'s hard
                requires-closure injection (admissibility-bound, ADR-0022 SS1: a dependency
                policy_filter rejected is never re-admitted through `requires`). Confirmed by
                reading Index._build_graph: `similar` is NEVER read by the shipped runtime (always
                set to an empty adjacency list) -- only `requires` has any functional effect on
                ranking or select(); `similar` is still populated on cards and measured for
                coverage, per apply.py's own convention, but cannot move any metric here. Dev
                skills carry zero authored `requires` edges, so derived edges are the ONLY way
                select()'s closure injection or the soft PPR-style _decayed_closure can ever fire
                on this corpus -- this is the arm `all_required@4` (the bundle-completeness gate,
                distinct from the legacy single-skill `completeness@4`) is meant to move.

Subcommands:
  enrich    run derive() once over the 10 123 dev skills (name+description+body only); cache the
            Enrichment dict + tools/enrich/apply.py::compute_stats coverage report to
            docs/reports/bakeoff/validation/dev-enrich-enrichment.json. Deterministic: re-running
            must reproduce byte-identical output (see tests/test_dev_enrich.py).
  run       run ONE arm (--arm P-flat|E-triggers|E-negatives|E-edges) through the real product
            path for all 1 000 dev cases; write a per-arm gzip JSONL + a partial metrics JSON.
            One arm per invocation -- each run is a single ~6-8 minute foreground call.
  combine   merge every arm's partial JSON, compute paired bootstrap CIs (1 000 resamples) vs
            P-flat by k (1/2/3) and overall for hit@1/nDCG@10/recall@10/all_required@4 (raw top-4)
            and all_required@4 on the actual select()-injected list, print the console table, and
            write docs/reports/bakeoff/validation/dev-enrich-metrics.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
ENRICH_DIR = REPO_ROOT / "tools" / "enrich"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"
ENRICHMENT_CACHE = VALIDATION_DIR / "dev-enrich-enrichment.json"

sys.path.insert(0, str(EVAL_DIR))
import dev_sparse  # noqa: E402  card/case construction, product runner, bootstrap CI, JSONL writer
import corpora as gf_corpora  # noqa: E402  ONLY pinned-corpus loader

sys.path.insert(0, str(ENRICH_DIR))
import derive as derive_mod  # noqa: E402  the extractor -- imported, never edited
import apply as apply_mod  # noqa: E402  build_cards/compute_stats -- reused, never edited

EVAL_K = dev_sparse.EVAL_K
K_CARDS = dev_sparse.K_CARDS
RECORD_TOPN = dev_sparse.RECORD_TOPN

METRIC_COLS = ("hit1", "ndcg10", "recall10", "all_required4", "all_required4_injected")

# One arm = one change from P-flat's cards. `edges` overlays BOTH requires and similar (similar
# is inert in the shipped runtime -- see the module docstring -- but is populated for coverage
# parity with apply.py's own convention).
ARM_OVERLAY_KWARGS = {
    "P-flat": {},
    "E-triggers": {"triggers": True},
    "E-negatives": {"negatives": True},
    "E-edges": {"edges": True},
}


# ============================================================================ enrichment overlay
def overlay_enrichment(cards: dict, id_to_urn: dict, enrichment: dict, *,
                        triggers: bool = False, negatives: bool = False, edges: bool = False) -> dict:
    """Return a NEW cards dict, identical to `cards` except for the requested derived field(s).
    Never mutates `cards`. `enrichment` is {skill_id: Enrichment-like} (attribute access on
    .triggers/.negative_triggers/.requires/.similar -- works for a fresh derive_mod.derive() result
    or for a types.SimpleNamespace reconstructed from the JSON cache, see load_enrichment_cache)."""
    if not (triggers or negatives or edges):
        return cards
    out = {u: dict(c) for u, c in cards.items()}
    for sid, urn in id_to_urn.items():
        e = enrichment.get(sid)
        if e is None or urn not in out:
            continue
        c = out[urn]
        if triggers:
            c["triggers"] = list(e.triggers)
        if negatives:
            c["negative_triggers"] = list(e.negative_triggers)
        if edges:
            c["requires"] = [id_to_urn[t] for t in e.requires if t in id_to_urn]
            c["similar"] = [id_to_urn[t] for t in e.similar if t in id_to_urn]
    return out


def build_arm_index(cli, cards: dict, nodes: dict):
    """Same flat weights as dev_sparse's own P-flat arm: every field weight = 1. Every arm here
    uses this -- the whole point is that arms differ from P-flat by ONE input field, not by
    weights."""
    flat_weights = {f"field.{f}": 1 for f in cli.Index.FIELDS}
    return cli.Index.from_cards(cards, nodes, weights=flat_weights)


# ============================================================================ enrichment cache
def load_enrichment_cache():
    """{skill_id: SimpleNamespace(triggers=, negative_triggers=, requires=, similar=, provenance=)}
    loaded from the cache `enrich` wrote. Raises FileNotFoundError with a clear message if the
    `enrich` subcommand has not been run yet."""
    import types
    if not ENRICHMENT_CACHE.exists():
        raise FileNotFoundError(
            f"{ENRICHMENT_CACHE} missing -- run `python3 tools/eval/dev_enrich.py enrich` first")
    data = json.loads(ENRICHMENT_CACHE.read_text())
    return {sid: types.SimpleNamespace(**d) for sid, d in data["enrichment"].items()}


# ============================================================================ gold-drop check
def gold_drop_stats_for_arm(router, cases: list) -> dict:
    """For every case, ask the REAL Router.policy_filter (never reimplemented) which urns it
    dropped, and intersect with the case's gold set (case["relevant"], grade 2 AND grade 3 --
    both are part of the bundle the product must not silently remove). Only meaningful for an
    arm whose cards carry non-empty negative_triggers; harmless (always empty) otherwise, but
    callers should skip this for arms that do not touch negatives to save an extra
    policy_filter pass over ~10 123 cards x 1 000 queries."""
    n_cases_with_drop = 0
    total_dropped = 0
    examples = []
    for case in cases:
        admissible, drops = router.policy_filter(case["node"], case["query"])
        gold_urns = {r["urn"] for r in (case.get("relevant") or [])}
        dropped_gold = sorted(
            u for u, reason in drops
            if reason.startswith("negative-trigger") and u in gold_urns
        )
        if dropped_gold:
            n_cases_with_drop += 1
            total_dropped += len(dropped_gold)
            if len(examples) < 10:
                examples.append({"query_id": case["id"], "query": case["query"],
                                  "dropped_gold": dropped_gold})
    return {"n_cases_with_gold_drop": n_cases_with_drop,
            "n_gold_dropped_total": total_dropped,
            "examples": examples}


# ============================================================================ metrics aggregation
def _mean_block_ext(per_q: dict, qids: list) -> dict:
    def col(name):
        vals = [per_q[q][name] for q in qids if not dev_sparse._isnan(per_q[q][name])]
        return sum(vals) / len(vals) if vals else float("nan")
    return {"n": len(qids), **{c: col(c) for c in METRIC_COLS}}


def arm_summary_ext(per_q: dict, cases: list) -> dict:
    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    out = {"overall": _mean_block_ext(per_q, [c["id"] for c in cases])}
    for k in sorted(by_k):
        out[f"k={k}"] = _mean_block_ext(per_q, by_k[k])
    return out


# ============================================================================ CLI: enrich
def cmd_enrich(args) -> int:
    t0 = time.time()
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillret_dev()
    skills = data["skills"]
    print(f"[{time.time()-t0:6.1f}s] deriving enrichment for {len(skills)} skills "
          f"(name+description+body only)...", file=sys.stderr)
    enrichment = derive_mod.derive(skills)
    stats = apply_mod.compute_stats(skills, enrichment)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    cache = {sid: e.to_dict() for sid, e in sorted(enrichment.items())}
    ENRICHMENT_CACHE.write_text(json.dumps(
        {"n_skills": len(skills), "stats": stats, "enrichment": cache},
        indent=2, ensure_ascii=False, sort_keys=True))
    print(f"[{time.time()-t0:6.1f}s] wrote {ENRICHMENT_CACHE}", file=sys.stderr)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


# ============================================================================ CLI: run
def cmd_run(args) -> int:
    t0 = time.time()
    arm = args.arm
    if arm not in ARM_OVERLAY_KWARGS:
        print(f"unknown arm {arm!r}; known: {sorted(ARM_OVERLAY_KWARGS)}", file=sys.stderr)
        return 1
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    metrics = dev_sparse._load_metrics()
    cli = dev_sparse._load_cli()

    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    print(f"[{time.time()-t0:6.1f}s] arm={arm} cards={len(cards)} nodes={len(nodes)} "
          f"cases={len(cases)}", file=sys.stderr)

    kwargs = ARM_OVERLAY_KWARGS[arm]
    if kwargs:
        enrichment = load_enrichment_cache()
        arm_cards = overlay_enrichment(cards, id_to_urn, enrichment, **kwargs)
        print(f"[{time.time()-t0:6.1f}s] overlaid derived fields ({kwargs}) onto {len(arm_cards)} "
              f"cards", file=sys.stderr)
    else:
        arm_cards = cards

    idx = build_arm_index(cli, arm_cards, nodes)
    router = cli.Router(idx)
    print(f"[{time.time()-t0:6.1f}s] built index+router for {arm}", file=sys.stderr)

    per_q = {}
    records = []
    n_abstained = 0
    for i, case in enumerate(cases):
        rec = dev_sparse.run_product_case(router, case, top_n=50, k_cards=K_CARDS)
        n_abstained += int(rec["abstained"])
        rec_all_req_inj = metrics.all_required_at_k(rec["injected"], case, 4)
        records.append({**rec, "arm": arm})
        per_q[case["id"]] = {
            "hit1": metrics.hit_at_1(rec["ranked"], case),
            "ndcg10": metrics.ndcg_at_k(rec["ranked"], case, EVAL_K),
            "recall10": metrics.recall_at_k(rec["ranked"], case, EVAL_K),
            "all_required4": metrics.all_required_at_k(rec["ranked"], case, 4),
            "all_required4_injected": rec_all_req_inj,
        }
        if (i + 1) % 200 == 0:
            print(f"[{time.time()-t0:6.1f}s] {arm}: {i+1}/{len(cases)} cases", file=sys.stderr)

    print(f"[{time.time()-t0:6.1f}s] ran {arm} (abstained={n_abstained})", file=sys.stderr)

    # Gold-drop check: only meaningful (and only worth the extra policy_filter pass) for an arm
    # that actually populates negative_triggers -- see gold_drop_stats_for_arm's docstring.
    if kwargs.get("negatives"):
        gold_drops = gold_drop_stats_for_arm(router, cases)
        print(f"[{time.time()-t0:6.1f}s] gold-drop check: "
              f"{gold_drops['n_cases_with_gold_drop']} cases, "
              f"{gold_drops['n_gold_dropped_total']} gold urns dropped", file=sys.stderr)
    else:
        gold_drops = {"n_cases_with_gold_drop": 0, "n_gold_dropped_total": 0, "examples": []}

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = VALIDATION_DIR / f"dev-enrich-{arm.lower()}.jsonl.gz"
    dev_sparse.write_jsonl_gz(jsonl_path, records)
    print(f"[{time.time()-t0:6.1f}s] wrote {jsonl_path}", file=sys.stderr)

    partial = {
        "arm": arm, "per_query": per_q, "summary": arm_summary_ext(per_q, cases),
        "n_abstained": n_abstained, "gold_drops": gold_drops,
        "corpus_report": corpus_report, "query_report": query_report,
        "runtime_s": time.time() - t0,
    }
    partial_path = VALIDATION_DIR / f"dev-enrich-{arm.lower()}.partial.json"
    partial_path.write_text(json.dumps(partial, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {partial_path}", file=sys.stderr)
    return 0


# ============================================================================ CLI: combine
def cmd_combine(args) -> int:
    t0 = time.time()
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillret_dev()
    _, _, id_to_urn, _ = dev_sparse.corpus_to_cards(data["skills"])
    cases, _ = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)

    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    breakdowns = {"overall": [c["id"] for c in cases],
                  **{f"k={k}": qids for k, qids in sorted(by_k.items())}}

    arm_names = args.arms or [
        a for a in ARM_OVERLAY_KWARGS
        if (VALIDATION_DIR / f"dev-enrich-{a.lower()}.partial.json").exists()
    ]
    base = "P-flat"
    if base not in arm_names:
        print(f"{base} baseline partial missing -- run `run --arm {base}` first", file=sys.stderr)
        return 1

    partials = {}
    for arm in arm_names:
        p = VALIDATION_DIR / f"dev-enrich-{arm.lower()}.partial.json"
        if not p.exists():
            print(f"missing partial for {arm}: {p}", file=sys.stderr)
            return 1
        partials[arm] = json.loads(p.read_text())

    summary = {arm: partials[arm]["summary"] for arm in arm_names}

    comparisons = {}
    per_q_base = partials[base]["per_query"]
    for arm in arm_names:
        if arm == base:
            continue
        per_q_chal = partials[arm]["per_query"]
        comparisons[arm] = {}
        for bd_name, qids in breakdowns.items():
            comparisons[arm][bd_name] = {}
            for metric in METRIC_COLS:
                a, b = dev_sparse.paired_arrays(per_q_base, per_q_chal, qids, metric)
                comparisons[arm][bd_name][metric] = dev_sparse.bootstrap_paired_delta(a, b)

    coverage = None
    if ENRICHMENT_CACHE.exists():
        coverage = json.loads(ENRICHMENT_CACHE.read_text()).get("stats")

    out = {
        "n_cases": len(cases),
        "arms": arm_names,
        "baseline": base,
        "summary": summary,
        "comparisons": comparisons,
        "gold_drops": {arm: partials[arm].get("gold_drops") for arm in arm_names},
        "abstain_counts": {arm: partials[arm].get("n_abstained") for arm in arm_names},
        "coverage": coverage,
        "runtime_s": time.time() - t0,
    }
    out_path = VALIDATION_DIR / "dev-enrich-metrics.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {out_path}", file=sys.stderr)

    cols = ["n"] + list(METRIC_COLS)
    head = f"{'arm':<14}{'break':<8}" + "".join(f"{c:>18}" for c in cols)
    print(head)
    print("-" * len(head))
    for arm in arm_names:
        for bd_name in breakdowns:
            m = summary[arm][bd_name]
            row = f"{arm:<14}{bd_name:<8}"
            for c in cols:
                v = m[c]
                row += f"{v:>18}" if isinstance(v, int) else (
                    f"{'—':>18}" if dev_sparse._isnan(v) else f"{v:>18.4f}")
            print(row)
    print("-" * len(head))
    for arm in arm_names:
        if arm == base:
            continue
        gd = partials[arm].get("gold_drops") or {}
        print(f"{arm}: gold-dropped cases={gd.get('n_cases_with_gold_drop', 0)} "
              f"gold urns dropped={gd.get('n_gold_dropped_total', 0)}")
    return 0


# ============================================================================ CLI: dispatch
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("enrich", help="derive() once over the 10 123 dev skills; cache + coverage report")
    p_run = sub.add_parser("run", help="run one arm through the product path for all 1 000 dev cases")
    p_run.add_argument("--arm", required=True)
    p_combine = sub.add_parser("combine", help="merge per-arm partials -> bootstrap CIs vs P-flat")
    p_combine.add_argument("--arms", nargs="*", default=None,
                            help="subset of arms to combine (default: every arm with a partial on disk)")
    args = ap.parse_args(argv)
    if args.cmd == "enrich":
        return cmd_enrich(args)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "combine":
        return cmd_combine(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
