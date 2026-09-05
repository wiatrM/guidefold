#!/usr/bin/env python3
"""tools/eval/dev_composer.py — family C (composition, DENSE-PROGRAM.md v2.4 §4 / ADR-0022 §4 /
ADR-0024 §4): dev-only comparison of the deterministic composer (`compose_mode="on"` in the
shipped CLI) and the model composer (tools/eval/composer_model.py, never wired into the CLI)
against **C0** (shipped `select()`, `compose_mode="off"`) on the frozen SKILLRET-train dev split
(tools/eval/corpora.py::load_skillret_dev(), DENSE-PROGRAM.md v2 §3 — the same 1 000-query pool
tools/eval/dev_sparse.py and tools/eval/dev_expand.py use, never test-A/test-B).

Reused, never reimplemented (import tools/eval/dev_sparse.py wholesale, per its own precedent in
tools/eval/dev_expand.py's header):
  * corpus_to_cards / queries_to_cases   dev pool -> Guidefold cards / golden-schema cases.
  * _load_cli / _load_metrics            SourceFileLoader for the no-suffix CLI / metrics.py.
  * write_jsonl_gz                       per-arm per-query JSONL (gzip), same file convention.
  * RECORD_TOPN / K_CARDS / EVAL_K       the same constants every dev/* script shares.
Also reused: tools/eval/skillret.py::paired_bootstrap_ci — the percentile-bootstrap CI function
named in this family's own DENSE-PROGRAM.md row as the comparison method, shared with the test-A/
test-B runners rather than re-derived here.

What composition can and cannot change, stated once: every arm here shares the *same* ranking
(`policy_filter -> candidates -> score`, identical Index/Router configuration for C0 and every
C-det-* arm; C-model-* arms reuse C0's own Router for scoring and only replace the fill step) — so
`hit@1`/`nDCG@10`/`recall@10` computed on the raw ranked list are, and are checked to be, identical
across all 7 arms. What differs is `select()`'s output (the "injected" list a caller actually
receives): `all_required@4` computed on THAT list is this family's primary metric, per
DENSE-PROGRAM.md's "Why C exists" paragraph — no family above this one can move it, because
`select()` had no composition stage until this one.

Arms (<=6 non-baseline, per the pre-registered DENSE-PROGRAM.md v2.4 §4 row; C0 itself is the
family's zero-budget reference, the same convention F0 uses in §4's own table):
  C0          shipped `select()`, `compose_mode="off"` — every query's real product behaviour.
  C-det-1..4  deterministic composer, `compose_mode="on"`, a 2x2 (tau_pct x compose_coverage)
              grid: tau_pct in {15, 30} (bracketing the CLI's own default of 20), compose_coverage
              in {True, False}. Full 1 000-query dev split (in-process, no network — cheap).
  C-model-1   model composer (tools/eval/composer_model.py), GATED by the same score-plateau
              bundle detector the deterministic composer uses (tau_pct=20): the model is called
              only on queries the detector flags as a bundle; every other query falls back to
              C0's own `_select_closure` (byte-identical to C0 on non-bundle queries, exactly as
              ADR-0024 §4 specifies the cost-bounding gate). Run on a fixed, k-stratified 150-query
              subsample of the dev split (see "Why a subsample" below), replay-cached.
  C-model-2   model composer, UNGATED: called on every query in the same 150-query subsample,
              bundle or not. Isolates what the cost-bounding gate (C-model-1) costs in quality,
              at higher $ and latency cost, per ADR-0024 §4's own design tension.

Why a subsample for C-model-*, not the full 1 000: the model composer is a real, metered
`claude -p --model haiku` subprocess call (measured 2026-09-05: ~$0.003, ~3-7s wall each, see
composer_model.py's module docstring) — the deterministic arms cost nothing to run at full scale,
the model arms are declared "offline eval only" in this family's own DENSE-PROGRAM.md row for
exactly this reason. A 150-query, k-stratified (k in {1,2,3}, proportional to the full split's own
328/333/339 split), fixed-seed (1337) subsample bounds real dollar/wall-clock cost while remaining
a genuine paired comparison against C0 restricted to the same 150 queries (every CI below is
computed only over the queries actually run by both arms being compared — see
`skillret.paired_bootstrap_ci`'s own qid-intersection behaviour). This is a scope decision, stated
here before any model call is made, not a result-driven one.

Freeze rule (pre-registered before this script's first `run`, per the brief this family was
built from): within each of the two families (C-det-*, C-model-*) independently, a configuration
QUALIFIES iff (a) its paired-bootstrap 95% CI on Δall_required@4 (arm - C0, over the queries that
arm actually ran) excludes zero on the low side (ci_low > 0), AND (b) its Δhit@1 on the injected
list is not worse than -1.0 percentage points (mean_delta >= -0.01). Among qualifiers in a family,
freeze the one with the highest point-estimate Δall_required@4; ties broken by (lower cannot_fit
rate, then lexicographic arm name). If no configuration in a family qualifies, freeze NONE for
that family and report why the closest candidate fell short. `cmd_freeze` implements this
mechanically off the JSON `run` writes — it does not re-derive the rule from the numbers.

Subcommands:
  convert   report corpus/query conversion stats only (no Router run, fast — for tests/CI)
  bundle-stats   report the score-plateau bundle rate (tau_pct=20) over the full dev split with
                 NO model calls — a free diagnostic used to size the model-arm subsample honestly
                 before any $ is spent.
  det       run C0 + the 4 deterministic arms over the full 1 000-query dev split; write JSONL
            (gzip) + a JSON summary. Fast, in-process, no network.
  model     run C-model-1/C-model-2 over the fixed 150-query subsample, using the persistent
            replay cache (tools/eval/.composer-model-cache/cache.jsonl); safe to invoke repeatedly
            — cached queries cost nothing, `--model-limit N` bounds how many NEW live calls this
            one invocation makes (for foreground-timeout chunking), and the JSONL/summary it
            writes reflects whatever is cache-complete at the time it is run.
  freeze    apply the pre-registered rule above to the `det`/`model` JSON summaries; print and
            write the freeze decision (or "none qualifies" per family).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — ONLY pinned-corpus loader
import dev_sparse  # noqa: E402  reused wholesale — see module docstring
import composer_model  # noqa: E402  tools/eval/composer_model.py — the model composer
import skillret  # noqa: E402  for skillret.paired_bootstrap_ci

RECORD_TOPN = dev_sparse.RECORD_TOPN
K_CARDS = dev_sparse.K_CARDS
EVAL_K = dev_sparse.EVAL_K
BUNDLE_TAU_PCT_DEFAULT = 20   # the CLI's own Index.DEFAULT_WEIGHTS["compose_tau_pct"]
SUBSAMPLE_N = 150
SUBSAMPLE_SEED = 1337
CACHE_PATH = EVAL_DIR / ".composer-model-cache" / "cache.jsonl"

DET_GRID = [  # (arm_name, tau_pct, coverage)
    ("C-det-1", 15, True),
    ("C-det-2", 15, False),
    ("C-det-3", 30, True),
    ("C-det-4", 30, False),
]


# ============================================================================ shared setup
def _load_dev(cli):
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return None
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    return cards, nodes, cases, corpus_report, query_report


def _build_c0(cli, cards, nodes):
    idx = cli.Index.from_cards(cards, nodes)
    return idx, cli.Router(idx)


def _build_det_arm(cli, cards, nodes, tau_pct, coverage):
    idx = cli.Index.from_cards(cards, nodes, weights={
        "compose_mode": "on", "compose_tau_pct": tau_pct, "compose_coverage": coverage,
    })
    return idx, cli.Router(idx)


# ============================================================================ subsample
def stratified_subsample(cases: list, n: int = SUBSAMPLE_N, seed: int = SUBSAMPLE_SEED) -> list:
    """n queries, proportionally stratified by `k` (the dev split's own 328/333/339 split at
    k in {1,2,3}), fixed seed, sorted by id before sampling so the result is independent of the
    corpus loader's own dict/JSONL iteration order."""
    by_k: dict = {}
    for c in sorted(cases, key=lambda c: c["id"]):
        by_k.setdefault(c["k"], []).append(c)
    total = sum(len(v) for v in by_k.values())
    rng = random.Random(seed)
    chosen = []
    for k in sorted(by_k):
        group = by_k[k]
        take = round(n * len(group) / total)
        chosen.extend(rng.sample(group, min(take, len(group))))
    # rounding may leave us 1-2 short/over `n` -- top up/trim deterministically from the sorted pool
    chosen_ids = {c["id"] for c in chosen}
    if len(chosen) < n:
        pool = [c for c in sorted(cases, key=lambda c: c["id"]) if c["id"] not in chosen_ids]
        rng.shuffle(pool)
        chosen.extend(pool[: n - len(chosen)])
    elif len(chosen) > n:
        rng.shuffle(chosen)
        chosen = chosen[:n]
    return sorted(chosen, key=lambda c: c["id"])


# ============================================================================ per-case runners
def run_composed_case(router, case: dict, top_n: int = 50, k_cards: int = K_CARDS) -> dict:
    """dev_sparse.run_product_case + `query=case['query']` passed into select(), + the composer's
    own last_multi_skill/last_cannot_fit flags read off the Router right after the call. Used for
    C0 (compose_mode="off", where these flags are always False -- see Router.select) and every
    C-det-* arm."""
    node, query = case["node"], case["query"]
    admissible, drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node, top_n=top_n)
    scored = router.score(cands, query, node)
    injected = router.select(scored, k=k_cards, admissible=admissible_set, query=query)
    return {
        "query_id": case["id"], "k": case["k"],
        "ranked": [s["urn"] for s in scored[:RECORD_TOPN]],
        "injected": [c["urn"] for c in injected],
        "abstained": not injected,
        "admissible_size": len(admissible_set),
        "is_bundle": bool(router.last_multi_skill),
        "cannot_fit": bool(router.last_cannot_fit),
    }


def run_model_case(router, case: dict, cards: dict, cache, gated: bool,
                    tau_pct: int = BUNDLE_TAU_PCT_DEFAULT, k_cards: int = K_CARDS,
                    top_n: int = 50, model: str = composer_model.DEFAULT_MODEL) -> dict:
    """Bypasses Router.select() entirely (the model composer is never wired into it) but
    replicates its abstain check exactly, since that check must still apply -- an abstained query
    has nothing to compose. `cards` is dev_sparse.corpus_to_cards' own card dict, keyed by urn, so
    each pool candidate can be turned into a composer_model prompt entry (name/description)."""
    node, query = case["node"], case["query"]
    admissible, drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node, top_n=top_n)
    scored = router.score(cands, query, node)

    idx = router.index
    mode = idx.weights.get("abstain_mode", "magnitude")
    abstain_threshold = (idx.weights["abstain_margin_threshold"] if mode == "margin"
                         else idx.weights["abstain_threshold"])
    signal = router._top_margin(scored) if mode == "margin" else (scored[0]["score"] if scored else 0)

    rec = {"query_id": case["id"], "k": case["k"],
           "ranked": [s["urn"] for s in scored[:RECORD_TOPN]],
           "admissible_size": len(admissible_set),
           "is_bundle": False, "cannot_fit": False, "model_called": False,
           "model_cached": None, "model_error": None, "model_latency_s": 0.0, "model_cost_usd": None}

    if not scored or signal < abstain_threshold:
        rec["injected"] = []
        rec["abstained"] = True
        return rec

    pool = [c for c in scored if c["urn"] in admissible_set][:15]
    is_bundle = router._detect_bundle(pool, tau_pct) if pool else False
    rec["is_bundle"] = is_bundle
    call_now = is_bundle if gated else True

    if call_now and pool:
        candidate_dicts = [cards[c["urn"]] for c in pool]
        result = composer_model.compose(case["id"], query, candidate_dicts, k=k_cards,
                                         model=model, cache=cache)
        rec["injected"] = list(result["selected"])
        rec["cannot_fit"] = bool(result["cannot_fit"])
        rec["model_called"] = True
        rec["model_cached"] = result["cached"]
        rec["model_error"] = result["error"]
        rec["model_latency_s"] = result["latency_s"]
        rec["model_cost_usd"] = result["cost_usd"]
    else:
        chosen = router._select_closure(scored, k_cards, admissible_set)
        rec["injected"] = [c["urn"] for c in chosen]

    rec["abstained"] = not rec["injected"]
    return rec


# ============================================================================ metrics
def per_query_metrics(metrics, records: list, cases_by_id: dict) -> dict:
    """{query_id: {hit1, ndcg10, recall10 (raw ranked -- identical across arms by construction),
    all_required4, hit1_injected (the composed/select()-injected list -- what a caller actually
    sees; THE primary comparison surface for this family)}}."""
    out = {}
    for rec in records:
        case = cases_by_id[rec["query_id"]]
        ranked, injected = rec["ranked"], rec["injected"]
        out[rec["query_id"]] = {
            "hit1": metrics.hit_at_1(ranked, case),
            "ndcg10": metrics.ndcg_at_k(ranked, case, EVAL_K),
            "recall10": metrics.recall_at_k(ranked, case, EVAL_K),
            "all_required4": metrics.all_required_at_k(injected, case, K_CARDS),
            "hit1_injected": metrics.hit_at_1(injected, case),
        }
    return out


def _isnan(x) -> bool:
    return isinstance(x, float) and x != x


def _mean_block(per_q: dict, qids: list) -> dict:
    def col(name):
        vals = [per_q[q][name] for q in qids if q in per_q and not _isnan(per_q[q][name])]
        return sum(vals) / len(vals) if vals else float("nan")
    return {"n": len(qids), "hit1": col("hit1"), "ndcg10": col("ndcg10"),
            "recall10": col("recall10"), "all_required4": col("all_required4"),
            "hit1_injected": col("hit1_injected")}


def arm_summary(per_q: dict, cases: list) -> dict:
    by_k: dict = {}
    for case in cases:
        if case["id"] in per_q:
            by_k.setdefault(case["k"], []).append(case["id"])
    qids = list(per_q.keys())
    out = {"overall": _mean_block(per_q, qids)}
    for k in sorted(by_k):
        out[f"k={k}"] = _mean_block(per_q, by_k[k])
    return out


def extra_stats(records: list) -> dict:
    n = len(records)
    n_bundle = sum(1 for r in records if r.get("is_bundle"))
    n_cannot_fit = sum(1 for r in records if r.get("cannot_fit"))
    n_abstained = sum(1 for r in records if r.get("abstained"))
    out = {"n": n, "bundle_rate": n_bundle / n if n else float("nan"),
           "cannot_fit_rate": n_cannot_fit / n if n else float("nan"),
           "abstain_rate": n_abstained / n if n else float("nan")}
    if any("model_called" in r for r in records):
        n_called = sum(1 for r in records if r.get("model_called"))
        live = [r["model_latency_s"] for r in records if r.get("model_called") and not r.get("model_cached")]
        cost = [r["model_cost_usd"] for r in records if r.get("model_cost_usd") is not None]
        n_errors = sum(1 for r in records if r.get("model_error"))
        out.update({
            "model_call_rate": n_called / n if n else float("nan"),
            "model_calls_total": n_called,
            "model_calls_live": len(live),
            "model_calls_cached": n_called - len(live),
            "model_errors": n_errors,
            "model_latency_p95_s": (sorted(live)[int(0.95 * (len(live) - 1))] if live else float("nan")),
            "model_cost_total_usd": sum(cost) if cost else 0.0,
        })
    return out


def paired_deltas(base_by_q: dict, chal_by_q: dict, breakdowns: dict) -> dict:
    out = {}
    for bd_name, qids in breakdowns.items():
        out[bd_name] = {}
        for metric in ("all_required4", "hit1_injected", "hit1", "ndcg10", "recall10"):
            a = {q: base_by_q[q][metric] for q in qids if q in base_by_q and q in chal_by_q}
            b = {q: chal_by_q[q][metric] for q in qids if q in base_by_q and q in chal_by_q}
            out[bd_name][metric] = skillret.paired_bootstrap_ci(a, b)
    return out


# ============================================================================ JSONL writer
write_jsonl_gz = dev_sparse.write_jsonl_gz


# ============================================================================ CLI: convert
def cmd_convert(args) -> int:
    cli = dev_sparse._load_cli()
    loaded = _load_dev(cli)
    if loaded is None:
        return 1
    cards, nodes, cases, corpus_report, query_report = loaded
    sub = stratified_subsample(cases)
    by_k = {}
    for c in sub:
        by_k[c["k"]] = by_k.get(c["k"], 0) + 1
    print(json.dumps({"corpus": corpus_report, "queries": query_report,
                       "subsample_n": len(sub), "subsample_by_k": by_k}, indent=2, ensure_ascii=False))
    return 0


# ============================================================================ CLI: bundle-stats
def cmd_bundle_stats(args) -> int:
    """Free diagnostic (no model calls): the score-plateau bundle rate at tau_pct=20 over the
    FULL 1 000-query dev split, using C0's own Router (compose_mode="off" -- _detect_bundle is
    called directly here, it does not depend on compose_mode)."""
    cli = dev_sparse._load_cli()
    loaded = _load_dev(cli)
    if loaded is None:
        return 1
    cards, nodes, cases, _, _ = loaded
    idx, router = _build_c0(cli, cards, nodes)
    n_bundle, by_k = 0, {}
    for case in cases:
        node, query = case["node"], case["query"]
        admissible, _ = router.policy_filter(node, query)
        admissible_set = set(admissible)
        cands = router.candidates(query, node, top_n=50)
        scored = router.score(cands, query, node)
        pool = [c for c in scored if c["urn"] in admissible_set][:15]
        is_bundle = router._detect_bundle(pool, BUNDLE_TAU_PCT_DEFAULT) if pool else False
        n_bundle += int(is_bundle)
        by_k.setdefault(case["k"], [0, 0])
        by_k[case["k"]][1] += 1
        by_k[case["k"]][0] += int(is_bundle)
    print(json.dumps({
        "tau_pct": BUNDLE_TAU_PCT_DEFAULT, "n": len(cases), "bundle_rate": n_bundle / len(cases),
        "by_k": {str(k): {"bundle": v[0], "n": v[1], "rate": v[0] / v[1]} for k, v in sorted(by_k.items())},
    }, indent=2, ensure_ascii=False))
    return 0


# ============================================================================ CLI: det
def cmd_det(args) -> int:
    t0 = time.time()
    cli = dev_sparse._load_cli()
    loaded = _load_dev(cli)
    if loaded is None:
        return 1
    cards, nodes, cases, corpus_report, query_report = loaded
    metrics = dev_sparse._load_metrics()
    cases_by_id = {c["id"]: c for c in cases}
    print(f"[{time.time()-t0:6.1f}s] cases={len(cases)}", file=sys.stderr)

    arms = {"C0": _build_c0(cli, cards, nodes)}
    for name, tau, cov in DET_GRID:
        arms[name] = _build_det_arm(cli, cards, nodes, tau, cov)

    per_query_by_arm, records_by_arm, extras_by_arm = {}, {}, {}
    for name, (idx, router) in arms.items():
        records = [run_composed_case(router, case) for case in cases]
        per_query_by_arm[name] = per_query_metrics(metrics, records, cases_by_id)
        records_by_arm[name] = records
        extras_by_arm[name] = extra_stats(records)
        print(f"[{time.time()-t0:6.1f}s] ran {name} "
              f"(bundle_rate={extras_by_arm[name]['bundle_rate']:.3f} "
              f"cannot_fit_rate={extras_by_arm[name]['cannot_fit_rate']:.3f})", file=sys.stderr)

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for name, records in records_by_arm.items():
        fname = f"dev-composer-{name.lower()}.jsonl.gz"
        write_jsonl_gz(VALIDATION_DIR / fname, [{**r, "arm": name} for r in records])

    summary = {name: arm_summary(per_q, cases) for name, per_q in per_query_by_arm.items()}
    by_k = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    breakdowns = {"overall": [c["id"] for c in cases], **{f"k={k}": q for k, q in sorted(by_k.items())}}
    comparisons = {name: paired_deltas(per_query_by_arm["C0"], per_query_by_arm[name], breakdowns)
                   for name in per_query_by_arm if name != "C0"}

    out = {"corpus_report": corpus_report, "query_report": query_report, "n_cases": len(cases),
           "extras": extras_by_arm, "summary": summary, "comparisons": comparisons,
           "runtime_s": time.time() - t0}
    out_path = args.out or (VALIDATION_DIR / "dev-composer-det-metrics.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {out_path}", file=sys.stderr)
    _print_table(summary)
    return 0


# ============================================================================ CLI: model
def cmd_model(args) -> int:
    t0 = time.time()
    cli = dev_sparse._load_cli()
    loaded = _load_dev(cli)
    if loaded is None:
        return 1
    cards, nodes, cases, corpus_report, query_report = loaded
    metrics = dev_sparse._load_metrics()
    sub = stratified_subsample(cases)
    sub_by_id = {c["id"]: c for c in sub}
    print(f"[{time.time()-t0:6.1f}s] subsample n={len(sub)}", file=sys.stderr)

    idx_c0, router_c0 = _build_c0(cli, cards, nodes)
    cache = composer_model.ReplayCache(CACHE_PATH)
    print(f"[{time.time()-t0:6.1f}s] replay cache loaded, {len(cache)} entries", file=sys.stderr)

    # C0 restricted to the subsample -- needed so the model arms have a same-N baseline to diff against.
    c0_records = [run_composed_case(router_c0, case) for case in sub]
    per_query_by_arm = {"C0-sub": per_query_metrics(metrics, c0_records, sub_by_id)}
    records_by_arm = {"C0-sub": c0_records}

    limit = args.model_limit
    for name, gated in (("C-model-1", True), ("C-model-2", False)):
        records = []
        live_calls_this_invocation = 0
        for case in sub:
            if limit is not None and live_calls_this_invocation >= limit:
                print(f"[{time.time()-t0:6.1f}s] {name}: hit --model-limit={limit}, "
                      f"stopping this invocation early ({len(records)}/{len(sub)} done)", file=sys.stderr)
                break
            before = len(cache)
            rec = run_model_case(router_c0, case, cards, cache, gated=gated)
            if len(cache) > before:
                live_calls_this_invocation += 1
            records.append(rec)
        per_query_by_arm[name] = per_query_metrics(metrics, records, sub_by_id)
        records_by_arm[name] = records
        n_live = sum(1 for r in records if r.get("model_called") and not r.get("model_cached"))
        print(f"[{time.time()-t0:6.1f}s] ran {name}: {len(records)}/{len(sub)} cases, "
              f"{n_live} live model calls this invocation", file=sys.stderr)

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for name, records in records_by_arm.items():
        fname = f"dev-composer-{name.lower()}.jsonl.gz"
        write_jsonl_gz(VALIDATION_DIR / fname, [{**r, "arm": name} for r in records])

    extras_by_arm = {name: extra_stats(records) for name, records in records_by_arm.items()}
    complete = all(len(records_by_arm[n]) == len(sub) for n in ("C-model-1", "C-model-2"))
    summary = {name: arm_summary(per_q, sub) for name, per_q in per_query_by_arm.items()}
    breakdowns = {"overall": [c["id"] for c in sub]}
    by_k = {}
    for c in sub:
        by_k.setdefault(c["k"], []).append(c["id"])
    breakdowns.update({f"k={k}": q for k, q in sorted(by_k.items())})
    comparisons = {name: paired_deltas(per_query_by_arm["C0-sub"], per_query_by_arm[name], breakdowns)
                   for name in ("C-model-1", "C-model-2") if name in per_query_by_arm}

    out = {"subsample_n": len(sub), "complete": complete, "extras": extras_by_arm,
           "summary": summary, "comparisons": comparisons, "runtime_s": time.time() - t0}
    out_path = args.out or (VALIDATION_DIR / "dev-composer-model-metrics.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {out_path} (complete={complete})", file=sys.stderr)
    _print_table(summary)
    return 0 if complete else 2   # 2: partial -- re-invoke to resume from cache


def _print_table(summary: dict) -> None:
    cols = ["n", "hit1", "ndcg10", "recall10", "all_required4", "hit1_injected"]
    head = f"{'arm':<14}{'break':<8}" + "".join(f"{c:>15}" for c in cols)
    print(head)
    print("-" * len(head))
    for arm_name, blocks in summary.items():
        for bd_name, m in blocks.items():
            row = f"{arm_name:<14}{bd_name:<8}"
            for c in cols:
                v = m[c]
                row += f"{v:>15}" if isinstance(v, int) else (f"{'—':>15}" if _isnan(v) else f"{v:>15.4f}")
            print(row)


# ============================================================================ CLI: freeze
def _qualifies(comparisons: dict, arm: str) -> tuple:
    """(qualifies: bool, ci: dict, delta_hit1: float, reason: str)."""
    overall = comparisons[arm]["overall"]
    ar4 = overall["all_required4"]
    h1 = overall["hit1_injected"]
    if ar4["n"] == 0:
        return False, ar4, float("nan"), "no paired queries"
    ci_excludes_zero = ar4["ci_low"] > 0
    hit1_ok = (not _isnan(h1["mean_delta"])) and h1["mean_delta"] >= -0.01
    if ci_excludes_zero and hit1_ok:
        return True, ar4, h1["mean_delta"], "qualifies"
    reasons = []
    if not ci_excludes_zero:
        reasons.append(f"CI on Δall_required4 does not exclude 0 (ci_low={ar4['ci_low']:.4f})")
    if not hit1_ok:
        reasons.append(f"Δhit1_injected too negative ({h1['mean_delta']:.4f} < -0.01)")
    return False, ar4, h1["mean_delta"], "; ".join(reasons)


def cmd_freeze(args) -> int:
    det_path = args.det_summary or (VALIDATION_DIR / "dev-composer-det-metrics.json")
    model_path = args.model_summary or (VALIDATION_DIR / "dev-composer-model-metrics.json")
    det = json.loads(det_path.read_text())
    model = json.loads(model_path.read_text()) if model_path.exists() else None

    decision = {"deterministic": None, "model": None}

    det_candidates = [name for name, _, _ in DET_GRID]
    rows = []
    for name in det_candidates:
        ok, ar4, dh1, reason = _qualifies(det["comparisons"], name)
        cannot_fit_rate = det["extras"][name]["cannot_fit_rate"]
        rows.append((name, ok, ar4["mean_delta"], ar4["ci_low"], ar4["ci_high"], dh1,
                     cannot_fit_rate, reason))
    qualifying = [r for r in rows if r[1]]
    if qualifying:
        qualifying.sort(key=lambda r: (-r[2], r[6], r[0]))
        winner = qualifying[0]
        decision["deterministic"] = {
            "frozen": winner[0], "delta_all_required4": winner[2],
            "ci_low": winner[3], "ci_high": winner[4], "delta_hit1_injected": winner[5],
            "cannot_fit_rate": winner[6],
        }
    decision["deterministic_rows"] = [
        {"arm": r[0], "qualifies": r[1], "delta_all_required4": r[2], "ci_low": r[3],
         "ci_high": r[4], "delta_hit1_injected": r[5], "cannot_fit_rate": r[6], "reason": r[7]}
        for r in rows
    ]

    if model is not None and model.get("complete"):
        mrows = []
        for name in ("C-model-1", "C-model-2"):
            ok, ar4, dh1, reason = _qualifies(model["comparisons"], name)
            cannot_fit_rate = model["extras"][name]["cannot_fit_rate"]
            mrows.append((name, ok, ar4["mean_delta"], ar4["ci_low"], ar4["ci_high"], dh1,
                          cannot_fit_rate, reason))
        mqualifying = [r for r in mrows if r[1]]
        if mqualifying:
            mqualifying.sort(key=lambda r: (-r[2], r[6], r[0]))
            winner = mqualifying[0]
            decision["model"] = {
                "frozen": winner[0], "delta_all_required4": winner[2],
                "ci_low": winner[3], "ci_high": winner[4], "delta_hit1_injected": winner[5],
                "cannot_fit_rate": winner[6],
            }
        decision["model_rows"] = [
            {"arm": r[0], "qualifies": r[1], "delta_all_required4": r[2], "ci_low": r[3],
             "ci_high": r[4], "delta_hit1_injected": r[5], "cannot_fit_rate": r[6], "reason": r[7]}
            for r in mrows
        ]
    else:
        decision["model_rows"] = []
        decision["model_note"] = "model summary absent or incomplete (re-run `model` to completion first)"

    out_path = args.out or (VALIDATION_DIR / "dev-composer-freeze.json")
    out_path.write_text(json.dumps(decision, indent=2, ensure_ascii=False))
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}", file=sys.stderr)
    return 0


# ============================================================================ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("convert", help="report corpus/query/subsample conversion stats only")
    sub.add_parser("bundle-stats", help="free score-plateau bundle-rate diagnostic, no model calls")
    p_det = sub.add_parser("det", help="run C0 + the 4 deterministic arms on the full dev split")
    p_det.add_argument("--out", type=Path, default=None)
    p_model = sub.add_parser("model", help="run the 2 model arms on the 150-query subsample")
    p_model.add_argument("--out", type=Path, default=None)
    p_model.add_argument("--model-limit", type=int, default=None,
                          help="max NEW live model calls this invocation (chunking control)")
    p_freeze = sub.add_parser("freeze", help="apply the pre-registered freeze rule")
    p_freeze.add_argument("--det-summary", type=Path, default=None)
    p_freeze.add_argument("--model-summary", type=Path, default=None)
    p_freeze.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    return {"convert": cmd_convert, "bundle-stats": cmd_bundle_stats, "det": cmd_det,
            "model": cmd_model, "freeze": cmd_freeze}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
