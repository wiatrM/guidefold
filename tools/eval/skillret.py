#!/usr/bin/env python3
"""tools/eval/skillret.py — dense-programme runs F0 (shipped baseline) and R1 (reference run,
`SKILLRET-Embedding-0.6B`) on SKILLRET-test, through the unmodified product path.

See docs/reports/bakeoff/DENSE-PROGRAM.md (v2) and ADR-0022. Corpus: tools/eval/corpora.py's
`load_skillret()`, pinned revision a050ad23 (verify() must pass before anything here runs).

SKILLRET-test carries no `requires`/`triggers`/location signal: every card here has empty
`triggers`/`negative_triggers`/`requires`/`refines` (closure is therefore a no-op on this corpus —
itself a reported fact, not an omission), and every query is run at two synthetic node settings
since the corpus gives no `cwd`:
    root  — node = "_root"                    (honest no-context case)
    major — node = gold[0]'s major (slugified) (coarse "somewhere in this platform" signal)
Never the leaf sub-node — that would leak the answer into the scope feature.

Two arms, same `Router` code, same `policy_filter -> candidates -> score -> select(admissible=...)`
pipeline (ADR-0022, no arm bypasses the filter):
    F0 (called R0/"r0" below) — Index.from_cards(..., weights={"w_dense": 0}), no dense channel.
    R1 (called "r1" below)   — same Index, `weights["w_dense"] = 1`, plus a `DenseCandidateRouter`
                                subclass that overrides only `_dense_scores` to serve int8-quantised
                                `SKILLRET-Embedding-0.6B` embeddings (precomputed offline by the
                                `encode` subcommand, which must run under the GPU venv). Everything
                                else — policy_filter/candidates/score/select/route — is the
                                unmodified `Router` from skills/guidefold/scripts/guidefold.

Subcommands:
    stats                print corpus/taxonomy/node/card stats; no side effects
    encode               [GPU venv only] embed all skills+queries, quantise int8, cache them
    r0                    run the F0 arm, both node settings, write JSONL + summary json
    r1                    run the R1 arm, both node settings; needs `encode`'s cache and r0's
                          summary json (for the paired bootstrap delta); write JSONL + summary
    latency               build a scratch on-disk artifact for the 6 006-skill corpus and measure
                          the whole `guidefold hook` subprocess, fresh-process, warm + cold

Every long-running subcommand parallelises across queries with a fork-started
`multiprocessing.Pool` (the Router/Index is built once in the parent; fork gives every worker a
copy-on-write view of it, no re-pickling) so a full 4 392-query x 2-setting run fits comfortably
inside a single foreground shell call.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path
from multiprocessing import get_context

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "tools" / "eval"
TESTS_DIR = REPO_ROOT / "tests"
for _p in (str(EVAL_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import corpora  # tools/eval/corpora.py — stdlib only
import dense_ref  # tools/eval/dense_ref.py — encoder-backed dense Router, shared w/ skillretbench_r1
import metrics  # tools/eval/metrics.py — stdlib only
from _router_helpers import make_card  # tests/_router_helpers.py — the card shape

CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
CACHE_DIR = Path(__file__).resolve().parent / ".skillret-cache"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

MODEL_HF_ID = "ThakiCloud/SKILLRET-Embedding-0.6B"
MODEL_REV = "0e10886e80a0aacc9efddc28282a258e2ab7eae1"
CORPUS_REVISION = "a050ad233a504a43135bafe8cdf45574052b5729"
GPU_VENV_PYTHON = "/home/mike/.cache/guidefold/gpu-venv/bin/python"

K_CARDS = 4
EVAL_K = 10
BOOTSTRAP_RESAMPLES = 1000

# Frozen sparse variant (docs/reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md, PR #36):
# uniform `field.*` weights recover 99.5% of the dev-corpus gap to plain BM25 (P-flat, +3.72 pp
# nDCG@10 [+3.16, +4.34] vs shipped). This is the ONE frozen candidate this test run touches --
# see DENSE-PROGRAM.md v2.1 SS3's "touched once" rule.
FLAT_FIELD_WEIGHTS = {
    "field.name": 1, "field.description": 1, "field.digest": 1,
    "field.triggers": 1, "field.body": 1,
}
CANDIDATE_TOP_N = 50  # must match Router.candidates()'s own `top_n` default (guidefold CLI)

_ID_SLUG_RE = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- CLI module loader
def load_cli():
    """Load skills/guidefold/scripts/guidefold as a module (it has no .py extension). Same
    pattern as tools/eval/run_golden.py's `_load_cli()`."""
    loader = SourceFileLoader("guidefold_cli", str(CLI_PATH))
    spec = __import__("importlib.util", fromlist=["spec_from_loader"]).spec_from_loader(
        loader.name, loader)
    mod = __import__("importlib.util", fromlist=["module_from_spec"]).module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- corpus -> model
def slugify(cli, s: str) -> str:
    return cli._slugify(s)


def _slug_id(s: str) -> str:
    return _ID_SLUG_RE.sub("-", s.lower()).strip("-") or "x"


def build_taxonomy(cli, taxonomy: dict):
    """Two-level node tree from the taxonomy: one node per major, one per major.sub.

    Returns (nodes, major_slug_of, node_of):
        nodes           guidefold.yaml-shaped {node: {"paths": [...], "owner": ...}}
        major_slug_of   major name -> its node ("_root" is not a major)
        node_of         (major, sub) -> "major-slug.sub-slug"
    """
    nodes = {"_root": {"paths": ["**"], "owner": "skillret"}}
    major_slug_of = {}
    node_of = {}
    for m in taxonomy["taxonomy"]:
        mslug = slugify(cli, m["major"])
        major_slug_of[m["major"]] = mslug
        nodes[mslug] = {"paths": [f"{mslug}/**"], "owner": "skillret"}
        for sub in m["subs"]:
            sslug = slugify(cli, sub["sub"])
            node = f"{mslug}.{sslug}"
            nodes[node] = {"paths": [f"{mslug}/{sslug}/**"], "owner": "skillret"}
            node_of[(m["major"], sub["sub"])] = node
    return nodes, major_slug_of, node_of


def build_cards(skills: list, node_of: dict) -> tuple[dict, dict]:
    """One card per skill. SKILLRET has no requires/triggers fields: every card's
    triggers/negative_triggers/requires/refines is empty, so `select()`'s requires-closure and
    `policy_filter()`'s negative-trigger drop are both no-ops on this corpus — a real result
    about this corpus, not a shortcut we took.

    Returns (cards urn->card, id_to_urn skill_id->urn)."""
    cards = {}
    id_to_urn = {}
    for s in skills:
        node = node_of[(s["major"], s["sub"])]
        u = f"urn:skill:skillret:{node}:{_slug_id(s['id'])}"
        desc = s.get("description") or ""
        body = s.get("body") or ""
        cards[u] = make_card(u, node, name=s.get("name") or s["id"], description=desc, body=body)
        id_to_urn[s["id"]] = u
    assert len(id_to_urn) == len(skills), "skill id -> urn mapping must be 1:1"
    return cards, id_to_urn


def build_cases(queries: list, id_to_urn: dict) -> list:
    """Golden-schema cases: skill_ids[0] grade 3 (must be first), the rest grade 2 (required
    companions — `k` is the bundle size). No distractor labels exist in this corpus.
    `category` is `k{k}` so `metrics.by_category` gives the per-k breakdown the report needs."""
    cases = []
    for q in queries:
        gold_ids = q["skill_ids"]
        relevant = []
        for i, sid in enumerate(gold_ids):
            urn = id_to_urn.get(sid)
            if urn is None:
                continue  # would mean a qrel/skill_id that doesn't resolve to a skill row
            relevant.append({"urn": urn, "grade": 3 if i == 0 else 2})
        cases.append({
            "qid": q["id"], "query": q["query"], "k": q["k"],
            "relevant": relevant, "distractors": [], "category": f"k{q['k']}",
        })
    return cases


def node_settings(cli, cases: list, skills_by_id: dict, major_slug_of: dict) -> dict:
    """qid -> {"root": "_root", "major": <major-slug of gold[0]>}. Computed once, reused by
    every arm so "both settings differ only in node" is true by construction."""
    out = {}
    for c in cases:
        gold0 = None
        for r in c["relevant"]:
            if r["grade"] == 3:
                gold0 = r
                break
        # recover the underlying skill id for gold0's urn isn't needed: we index by qid instead,
        # using the original query's skill_ids[0] captured by the caller (see run_all_arms).
        out[c["qid"]] = gold0
    return out


# --------------------------------------------------------------------------- dense candidate router
# The encoder-backed dense Router (mixin overriding only `_dense_scores`) is corpus-agnostic and
# now lives in tools/eval/dense_ref.py, shared verbatim with tools/eval/skillretbench_r1.py (the
# test-B/SkillRetBench R1-encoder runner) — see DENSE-PROGRAM.md v2.1 §6. These names are kept as
# thin aliases/wrappers so this module's existing public API (and tests/test_skillret_eval.py,
# which calls `skillret.build_r1_index_and_router` directly) is unchanged.
DenseCandidateRouter = dense_ref.DenseCandidateRouter
make_dense_router_class = dense_ref.make_dense_router_class


def build_r0_index(cli, cards, nodes, weights_arm: str = "shipped"):
    """weights_arm="shipped" (default) is exactly the pre-existing call (byte-identical, no
    behaviour change for any existing caller). weights_arm="flat" additionally overrides the five
    `field.*` weights to 1 (FLAT_FIELD_WEIGHTS) -- the frozen sparse variant from PR #36 -- leaving
    every other weight (w_scope, w_ppr, abstain_threshold, ppr_mode, k1/b, ...) at its shipped
    default, same merge order as the shipped arm."""
    extra = dict(FLAT_FIELD_WEIGHTS) if weights_arm == "flat" else {}
    return cli.Index.from_cards(cards, nodes, weights={"w_dense": 0, **extra}, word_vectors=None)


def build_r1_index_and_router(cli, cards, nodes, row_of, skill_mat, query_vec_of):
    return dense_ref.build_dense_index_and_router(
        cli, cards, nodes, row_of, skill_mat, query_vec_of, weights={"w_dense": 1})


# --------------------------------------------------------------------------- per-query run (single process body)
def _run_one(router, case, node, arm_is_dense):
    """Replicates Router.route()'s internal call sequence (candidates -> score -> select), but
    keeps the intermediate values the per-query JSONL record and the coverage analysis need.

    Returns TWO orderings, exactly like tools/eval/run_golden.py's run_cases() — conflating them
    is the bug this repo already found and fixed once (commit 931055d, "golden runner measured
    the injection order, understating hit@1 by 64 points"):
        retrieval  -- Router.score order (score desc, tie-broken on urn), truncated to EVAL_K.
                      Answers "did ranking put the right skills at the top?" -> hit@1, recall@10,
                      nDCG@10 (ours and the paper's).
        injection  -- the <=K_CARDS urns Router.select actually emits (general->specific order,
                      after the abstention gate and the requires-closure expansion — a no-op on
                      this corpus, but the abstention gate is real). Answers "did the cards the
                      agent receives contain the whole required bundle?" -> all_required@4,
                      completeness@4, distractor_rate@4.
    """
    query = case["query"]
    if arm_is_dense:
        router._current_qid = case["qid"]
    admissible, drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node)
    scored = router.score(cands, query, node)
    selected = router.select(scored, k=K_CARDS, admissible=admissible_set)

    retrieval_urns = [c["urn"] for c in scored[:EVAL_K]]
    injected = [c["urn"] for c in selected]
    drop_counts = {}
    for _u, reason in drops:
        key = reason.split(":", 1)[0]
        drop_counts[key] = drop_counts.get(key, 0) + 1
    record = {
        "qid": case["qid"], "k": case["k"], "node": node,
        "admissible_size": len(admissible_set), "drops": drop_counts,
        "ranked": [{"urn": u, "score": s["score"]} for u, s in zip(retrieval_urns, scored[:EVAL_K])],
        "injected": injected,
    }
    coverage = None
    if arm_is_dense:
        # NOTE: bm25_rank/dense_rank (from Router.candidates()) are each populated for the WHOLE
        # visible set that has any nonzero score in that channel -- not just the top-N urns that
        # channel actually contributed to the returned candidate pool. Dense cosine is virtually
        # never exactly zero, so `dense_rank is not None` is true for nearly every visible urn
        # regardless of rank; comparing against CANDIDATE_TOP_N (== candidates()'s own `top_n`
        # default) is required to ask "was this urn actually IN the top-50-by-that-channel pool".
        by_bm25 = {c["urn"] for c in cands
                   if c["bm25_rank"] is not None and c["bm25_rank"] <= CANDIDATE_TOP_N}
        by_dense = {c["urn"] for c in cands
                    if c["dense_rank"] is not None and c["dense_rank"] <= CANDIDATE_TOP_N}
        gold = {r["urn"] for r in case["relevant"]}
        coverage = {
            "qid": case["qid"], "k": case["k"], "gold_n": len(gold),
            "covered_bm25": len(gold & by_bm25),
            "added_by_dense": len((gold & by_dense) - by_bm25),
            "missed_both": len(gold - by_bm25 - by_dense),
        }
    return retrieval_urns, injected, record, coverage


# --------------------------------------------------------------------------- multiprocessing plumbing
_W_ROUTER = None
_W_ARM_IS_DENSE = None


def _pool_init(router, arm_is_dense):
    global _W_ROUTER, _W_ARM_IS_DENSE
    _W_ROUTER = router
    _W_ARM_IS_DENSE = arm_is_dense


def _pool_worker(args):
    case, node = args
    return _run_one(_W_ROUTER, case, node, _W_ARM_IS_DENSE)


def run_arm_parallel(router, cases, node_for, arm_is_dense: bool, n_workers: int = None):
    """node_for(case) -> node string. Runs every case through `_run_one`, fork-parallelised.
    Returns (retrieval_results, injection_results, records, coverage_rows): the first two are
    [(ranked_urns, case), ...] pairs ready for tools/eval/metrics.py — retrieval order and
    injection order respectively (see `_run_one`'s docstring for why both exist and must not be
    conflated) — records is the per-query JSONL payload list, coverage_rows is [] unless
    arm_is_dense."""
    n_workers = n_workers or min(12, os.cpu_count() or 1)
    args = [(c, node_for(c)) for c in cases]
    ctx = get_context("fork")
    with ctx.Pool(processes=n_workers, initializer=_pool_init,
                  initargs=(router, arm_is_dense)) as pool:
        chunksize = max(1, len(args) // (n_workers * 4))
        out = pool.map(_pool_worker, args, chunksize=chunksize)
    retrieval_results, injection_results, records, coverage_rows = [], [], [], []
    for (retrieval_urns, injected, record, coverage), case in zip(out, cases):
        retrieval_results.append((retrieval_urns, case))
        injection_results.append((injected, case))
        records.append(record)
        if coverage is not None:
            coverage_rows.append(coverage)
    return retrieval_results, injection_results, records, coverage_rows


# --------------------------------------------------------------------------- metrics helpers (paper + recall@10)
def _mean(xs):
    vals = [x for x in xs if not math.isnan(x)]
    return sum(vals) / len(vals) if vals else float("nan")


def _answered_pairs(results):
    answerable = [(r, c) for r, c in results if not metrics.is_abstention_case(c)]
    return [(r, c) for r, c in answerable if r]


def ndcg_at_k_binary(ranked, case, k=10):
    """Paper-style binary-relevance nDCG@k: every grade>=2 urn worth 1, not our exponential-gain
    grade-3-vs-2 weighting (see ndcg_at_k's own docstring in metrics.py for why we grade at all)."""
    rel = {u for u, g in metrics.graded(case).items() if g >= metrics.MUST_BE_IN_TOP_K}
    if not rel:
        return float("nan")
    dcg = sum(1.0 / math.log2(i + 2) for i, u in enumerate(ranked[:k]) if u in rel)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal if ideal else float("nan")


def evaluate_full(retrieval_results, injection_results, k_cards=K_CARDS):
    """Merges two independent `metrics.evaluate()` calls — retrieval-order metrics must never be
    read off the injection list or vice versa (see `_run_one`'s docstring; this repo already hit
    and fixed the "understating hit@1 by 64 points" version of this bug once).

    From retrieval order: hit@1, recall@8, nDCG@10 (ours), plus the paper-style metrics —
    nDCG@10 (binary relevance), Recall@10 (== our recall@10: both threshold at grade>=2, no
    separate function needed), Completeness@10 (`all_required_at_k` at k=10 over the *retrieval*
    ranking — the paper's metric is a pure top-10-ranking metric with no notion of a 4-card
    injection budget, so it is evaluated on the same list nDCG@10/Recall@10 use, not on the
    injected bundle).

    From injection order (the <=k_cards urns Router.select actually emits): all_required@{k},
    completeness@{k}, distractor_rate@{k} (NaN here, no distractor labels), and the abstention /
    coverage figures — abstention is a `select()`-level behaviour (the confidence gate), not a
    property of the retrieval ranking.
    """
    ret_ev = metrics.evaluate(retrieval_results, k_cards=k_cards)
    inj_ev = metrics.evaluate(injection_results, k_cards=k_cards)
    out = {
        "n": ret_ev["n"], "n_answerable": ret_ev["n_answerable"],
        "hit@1": ret_ev["hit@1"], "recall@8": ret_ev["recall@8"], "ndcg@10": ret_ev["ndcg@10"],
        f"completeness@{k_cards}": inj_ev[f"completeness@{k_cards}"],
        f"all_required@{k_cards}": inj_ev[f"all_required@{k_cards}"],
        f"distractor_rate@{k_cards}": inj_ev[f"distractor_rate@{k_cards}"],
        "abstention_precision": inj_ev["abstention_precision"],
        "abstention_recall": inj_ev["abstention_recall"],
        "coverage": inj_ev["coverage"],
        "n_answered_injection": inj_ev["n_answered"],
    }
    answered_ret = _answered_pairs(retrieval_results)
    out["recall@10"] = _mean(metrics.recall_at_k(r, c, 10) for r, c in answered_ret)
    out["paper_ndcg@10"] = _mean(ndcg_at_k_binary(r, c, 10) for r, c in answered_ret)
    out["paper_recall@10"] = out["recall@10"]  # identical: both threshold at grade>=2
    out["paper_completeness@10"] = _mean(metrics.all_required_at_k(r, c, 10) for r, c in answered_ret)
    return out


def by_category_full(retrieval_results, injection_results, k_cards=K_CARDS):
    ret_buckets, inj_buckets = {}, {}
    for ranked, case in retrieval_results:
        ret_buckets.setdefault(case.get("category", "unknown"), []).append((ranked, case))
    for ranked, case in injection_results:
        inj_buckets.setdefault(case.get("category", "unknown"), []).append((ranked, case))
    cats = sorted(set(ret_buckets) | set(inj_buckets))
    return {cat: evaluate_full(ret_buckets.get(cat, []), inj_buckets.get(cat, []), k_cards)
            for cat in cats}


def per_query_metric(results, fn, k):
    """qid -> fn(ranked, case, k) for every (ranked, case) pair, skipping abstained queries the
    same way metrics.evaluate() does (an abstention is not a ranking-metric 0; see metrics.py).
    Caller picks which `results` list (retrieval or injection) matches the metric being computed —
    see `evaluate_full`'s docstring."""
    out = {}
    for ranked, case in _answered_pairs(results):
        out[case["qid"]] = fn(ranked, case, k)
    return out


def paired_bootstrap_ci(a_by_qid: dict, b_by_qid: dict, n_resamples=BOOTSTRAP_RESAMPLES, seed=0):
    """95% CI on mean(b - a) over the qids present in both maps (paired over queries), via
    resampling query indices with replacement. `a` = baseline (R0/F0), `b` = the arm under test."""
    import numpy as np
    common = sorted(set(a_by_qid) & set(b_by_qid))
    deltas = [b_by_qid[q] - a_by_qid[q] for q in common
              if not (math.isnan(a_by_qid[q]) or math.isnan(b_by_qid[q]))]
    n = len(deltas)
    if n == 0:
        return {"n": 0, "mean_delta": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    arr = np.asarray(deltas, dtype=np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    means = arr[idx].mean(axis=1)
    means.sort()
    lo = float(means[int(0.025 * n_resamples)])
    hi = float(means[min(n_resamples - 1, int(0.975 * n_resamples))])
    return {"n": n, "mean_delta": float(arr.mean()), "ci_low": lo, "ci_high": hi,
            "n_resamples": n_resamples}


# --------------------------------------------------------------------------- shared setup
def load_corpus_and_build(cli):
    problems = corpora.verify("skillret")
    if problems:
        raise SystemExit("skillret: corpus verification FAILED:\n" + "\n".join(problems))
    data = corpora.load_skillret()
    nodes, major_slug_of, node_of = build_taxonomy(cli, data["taxonomy"])
    cards, id_to_urn = build_cards(data["skills"], node_of)
    cases = build_cases(data["queries"], id_to_urn)
    skills_by_id = {s["id"]: s for s in data["skills"]}
    # qid -> major-slug of skill_ids[0], computed directly from the query (not recovered from the
    # case, which only stores urns) so the "major" setting is exact.
    major_of_qid = {}
    for q in data["queries"]:
        gold0 = skills_by_id[q["skill_ids"][0]]
        major_of_qid[q["id"]] = major_slug_of[gold0["major"]]
    return data, nodes, cards, id_to_urn, cases, major_of_qid


def node_for_setting(setting: str, major_of_qid: dict):
    if setting == "root":
        return lambda case: "_root"
    if setting == "major":
        return lambda case: major_of_qid[case["qid"]]
    raise ValueError(setting)


# --------------------------------------------------------------------------- cmd: stats
def cmd_stats(args):
    cli = load_cli()
    data, nodes, cards, id_to_urn, cases, major_of_qid = load_corpus_and_build(cli)
    taxo = data["taxonomy"]["taxonomy"]
    print(f"skillret @ {CORPUS_REVISION[:8]}")
    print(f"skills={len(data['skills'])} queries={len(data['queries'])} qrels={len(data['qrels'])}")
    print(f"taxonomy: {len(taxo)} majors, {sum(len(m['subs']) for m in taxo)} subs, "
          f"{len(nodes)} nodes total (incl. _root)")
    print(f"cards built: {len(cards)}")
    k_counts = {}
    for c in cases:
        k_counts[c["k"]] = k_counts.get(c["k"], 0) + 1
    print("cases by k:", dict(sorted(k_counts.items())))
    print("nodes:")
    for m in taxo:
        print(f"  {slugify(cli, m['major'])}  ({m['major']})")
        for sub in m["subs"]:
            print(f"    {slugify(cli, m['major'])}.{slugify(cli, sub['sub'])}  ({sub['sub']})")


# --------------------------------------------------------------------------- cmd: encode (GPU venv)
def cmd_encode(args):
    if sys.executable != GPU_VENV_PYTHON and not args.force_any_python:
        raise SystemExit(f"skillret encode: must run under {GPU_VENV_PYTHON} "
                          f"(got {sys.executable}); pass --force-any-python to override")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(REPO_ROOT / "tools" / "bakeoff"))
    import numpy as np
    import encode as bakeoff_encode  # tools/bakeoff/encode.py — Encoder class, reused verbatim

    cli = load_cli()
    data, nodes, cards, id_to_urn, cases, major_of_qid = load_corpus_and_build(cli)
    skills_by_id = {s["id"]: s for s in data["skills"]}
    urn_to_skill_id = {u: sid for sid, u in id_to_urn.items()}

    skill_order = sorted(cards.keys())
    skill_texts = []
    for u in skill_order:
        s = skills_by_id[urn_to_skill_id[u]]
        skill_texts.append((s.get("description") or "") + "\n\n" + (s.get("body") or ""))
    query_order = [q["id"] for q in data["queries"]]
    query_texts = [q["query"] for q in data["queries"]]
    if args.sample:
        skill_order, skill_texts = skill_order[: args.sample], skill_texts[: args.sample]
        query_order, query_texts = query_order[: args.sample], query_texts[: args.sample]

    # Two Encoder instances, same model, different batch_size (a documented constructor kwarg —
    # not a modification of encode.py). Skill text is description+body: up to ~184k chars in this
    # corpus (461 skills > 20k chars, 122 > ~8192 tokens' worth), and sentence-transformers sorts
    # a batch by length internally before padding, so the model's *own* default batch_size=64 puts
    # dozens of near-max-length (8192-token) sequences in one forward pass -- confirmed via smoke
    # test to CUDA OOM on this corpus (attempted an 8 GiB single allocation, RTX 4090, 24 GiB).
    # Queries are short (a sentence), so they keep the encoder's own default batch size.
    enc_skills = bakeoff_encode.Encoder(MODEL_HF_ID, MODEL_REV, batch_size=args.skill_batch_size)
    enc_queries = bakeoff_encode.Encoder(MODEL_HF_ID, MODEL_REV)

    # encode_chunked/quantize/quant_cosine now live in tools/eval/dense_ref.py, shared verbatim
    # with tools/eval/skillretbench_r1.py's own `encode` subcommand (test-B) — see DENSE-PROGRAM.md
    # v2.1 §6. Behaviour here is byte-for-byte the same as before the extraction.
    t0 = time.time()
    skill_vecs = dense_ref.encode_chunked(
        enc_skills, skill_texts, False, args.skill_chunk_size, "skills")
    t1 = time.time()
    query_vecs = dense_ref.encode_chunked(enc_queries, query_texts, True, 500, "queries")
    t2 = time.time()

    skill_q = dense_ref.quantize(skill_vecs)
    query_q = dense_ref.quantize(query_vecs)

    skill_cos = dense_ref.quant_cosine(skill_vecs, skill_q)
    query_cos = dense_ref.quant_cosine(query_vecs, query_q)

    max_seq_len = getattr(getattr(enc_skills, "_model", None), "max_seq_length", None)
    meta = {
        "hf_id": MODEL_HF_ID, "revision": MODEL_REV, "dims": int(skill_vecs.shape[1]),
        "n_skills": len(skill_order), "n_queries": len(query_order),
        "device": bakeoff_encode.DEVICE, "dtype": str(bakeoff_encode.DTYPE),
        "batch_size": bakeoff_encode.DEFAULT_BATCH_SIZE, "max_seq_length": max_seq_len,
        "encode_time_skills_s": t1 - t0, "encode_time_queries_s": t2 - t1,
        "quant_error_skills": {"mean_cosine": float(skill_cos.mean()),
                                "min_cosine": float(skill_cos.min()),
                                "mean_abs_diff": float(np.abs(skill_vecs - skill_q.astype(np.float32) / 127.0).mean())},
        "quant_error_queries": {"mean_cosine": float(query_cos.mean()),
                                 "min_cosine": float(query_cos.min())},
    }
    dense_ref.write_dense_cache(CACHE_DIR, skill_order, query_order, skill_q, query_q, meta)
    print(json.dumps(meta, indent=2))


def load_dense_cache():
    """skillret.py's own convenience wrapper bound to its module-level CACHE_DIR; the shared,
    cache-dir-parameterized implementation is dense_ref.load_dense_cache."""
    try:
        return dense_ref.load_dense_cache(CACHE_DIR)
    except SystemExit:
        raise SystemExit(f"skillret: no encode cache at {CACHE_DIR} — run `skillret.py encode` "
                          f"under {GPU_VENV_PYTHON} first")


# --------------------------------------------------------------------------- cmd: r0 / r1
def _write_jsonl_gz(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def cmd_r0(args):
    cli = load_cli()
    data, nodes, cards, id_to_urn, cases, major_of_qid = load_corpus_and_build(cli)
    if args.sample:
        cases = cases[: args.sample]

    weights_arm = getattr(args, "weights_arm", "shipped")
    suffix = "" if weights_arm == "shipped" else f"-{weights_arm}"

    t0 = time.time()
    idx = build_r0_index(cli, cards, nodes, weights_arm=weights_arm)
    build_s = time.time() - t0
    router = cli.Router(idx)

    # Non-shipped arms (currently only "flat", DENSE-PROGRAM.md v2.1 §3-5) get a paired
    # bootstrap vs the CURRENT shipped F0 baseline, read from the committed shipped summary --
    # never re-derived by re-running the shipped arm through this same invocation.
    baseline_summary = None
    if weights_arm != "shipped":
        baseline_path = VALIDATION_DIR / "skillret-r0-summary.json"
        if baseline_path.exists():
            baseline_summary = json.loads(baseline_path.read_text())
        else:
            print("skillret r0: WARNING no shipped r0 summary found — "
                  "bootstrap deltas vs F0 omitted", file=sys.stderr)

    summary = {"header": {"revision": CORPUS_REVISION, "n_skills": len(cards),
                           "n_queries_run": len(cases), "index_build_s": build_s,
                           "w_dense": idx.weights.get("w_dense", 0),
                           "weights_arm": weights_arm},
               "settings": {}}
    for setting in ("root", "major"):
        node_for = node_for_setting(setting, major_of_qid)
        t0 = time.time()
        retrieval_results, injection_results, records, _cov = run_arm_parallel(
            router, cases, node_for, arm_is_dense=False)
        elapsed = time.time() - t0
        overall = evaluate_full(retrieval_results, injection_results)
        by_k = by_category_full(retrieval_results, injection_results)
        per_query = {
            "all_required@4": per_query_metric(injection_results, metrics.all_required_at_k, K_CARDS),
            "hit@1": per_query_metric(retrieval_results, lambda r, c, k: metrics.hit_at_1(r, c), 1),
            "ndcg@10": per_query_metric(retrieval_results, metrics.ndcg_at_k, 10),
            "recall@10": per_query_metric(retrieval_results, metrics.recall_at_k, 10),
        }
        setting_summary = {
            "overall": overall, "by_k": by_k, "elapsed_s": elapsed,
            "n_queries": len(cases), "per_query": per_query,
        }

        if baseline_summary is not None:
            base_pq = baseline_summary["settings"][setting]["per_query"]
            bootstrap = {}
            for metric_name in ("hit@1", "ndcg@10", "recall@10", "all_required@4"):
                base_vals = base_pq.get(metric_name)
                if base_vals is None:
                    continue  # older shipped summary predates this metric's per-query capture
                bootstrap[metric_name] = {"overall": paired_bootstrap_ci(
                    base_vals, per_query[metric_name])}
                qids_by_k = {}
                for c in cases:
                    qids_by_k.setdefault(c["category"], set()).add(c["qid"])
                for kcat, qids in sorted(qids_by_k.items()):
                    a_k = {q: v for q, v in base_vals.items() if q in qids}
                    b_k = {q: v for q, v in per_query[metric_name].items() if q in qids}
                    bootstrap[metric_name][kcat] = paired_bootstrap_ci(a_k, b_k)
            setting_summary["bootstrap_vs_shipped"] = bootstrap

        summary["settings"][setting] = setting_summary
        _write_jsonl_gz(VALIDATION_DIR / f"skillret-r0{suffix}-{setting}.jsonl.gz", records)
        print(f"r0{suffix}/{setting}: {elapsed:.1f}s ({elapsed/len(cases)*1000:.1f} ms/query), "
              f"n={len(cases)}, all_required@4={overall.get('all_required@4'):.4f}, "
              f"hit@1={overall.get('hit@1'):.4f}, ndcg@10={overall.get('ndcg@10'):.4f}, "
              f"coverage={overall.get('coverage'):.4f}")

    out_path = VALIDATION_DIR / f"skillret-r0{suffix}-summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {out_path}")


def cmd_r1(args):
    cli = load_cli()
    data, nodes, cards, id_to_urn, cases, major_of_qid = load_corpus_and_build(cli)
    if args.sample:
        cases = cases[: args.sample]
    meta, row_of, skill_mat, query_vec_of = load_dense_cache()

    r0_summary_path = args.baseline
    r0_summary = json.loads(r0_summary_path.read_text()) if r0_summary_path.exists() else None
    if r0_summary is None:
        print(f"skillret r1: WARNING no r0 summary found at {r0_summary_path} — "
              "paired bootstrap deltas will be omitted", file=sys.stderr)
    out_suffix = args.out_suffix

    t0 = time.time()
    idx, router = build_r1_index_and_router(cli, cards, nodes, row_of, skill_mat, query_vec_of)
    build_s = time.time() - t0

    summary = {"header": {"revision": CORPUS_REVISION, "n_skills": len(cards),
                           "n_queries_run": len(cases), "index_build_s": build_s,
                           "w_dense": idx.weights.get("w_dense", 0),
                           "encoder": meta},
               "settings": {}}
    for setting in ("root", "major"):
        node_for = node_for_setting(setting, major_of_qid)
        t0 = time.time()
        retrieval_results, injection_results, records, coverage_rows = run_arm_parallel(
            router, cases, node_for, arm_is_dense=True)
        elapsed = time.time() - t0
        overall = evaluate_full(retrieval_results, injection_results)
        by_k = by_category_full(retrieval_results, injection_results)

        # coverage first (DENSE-PROGRAM.md v2 §6): gold skills BM25F's top-50 missed that the
        # encoder's candidates contain, per k and overall.
        cov_by_k = {}
        for row in coverage_rows:
            b = cov_by_k.setdefault(f"k{row['k']}", {"gold_n": 0, "covered_bm25": 0,
                                                       "added_by_dense": 0, "missed_both": 0, "n": 0})
            b["gold_n"] += row["gold_n"]; b["covered_bm25"] += row["covered_bm25"]
            b["added_by_dense"] += row["added_by_dense"]; b["missed_both"] += row["missed_both"]
            b["n"] += 1
        cov_overall = {"gold_n": 0, "covered_bm25": 0, "added_by_dense": 0, "missed_both": 0,
                       "n": len(coverage_rows)}
        for b in cov_by_k.values():
            for key in ("gold_n", "covered_bm25", "added_by_dense", "missed_both"):
                cov_overall[key] += b[key]

        r1_per_query = {
            "all_required@4": per_query_metric(injection_results, metrics.all_required_at_k, K_CARDS),
            "hit@1": per_query_metric(retrieval_results, lambda r, c, k: metrics.hit_at_1(r, c), 1),
            "ndcg@10": per_query_metric(retrieval_results, metrics.ndcg_at_k, 10),
        }
        bootstrap = {}
        if r0_summary is not None:
            r0_pq = r0_summary["settings"][setting]["per_query"]
            for metric_name in ("all_required@4", "hit@1", "ndcg@10"):
                if metric_name not in r0_pq:
                    continue  # older baseline summary predates this metric's per-query capture
                bootstrap[metric_name] = {"overall": paired_bootstrap_ci(
                    r0_pq[metric_name], r1_per_query[metric_name])}
                # per-k: restrict both maps to qids of that k-stratum
                qids_by_k = {}
                for c in cases:
                    qids_by_k.setdefault(c["category"], set()).add(c["qid"])
                for kcat, qids in sorted(qids_by_k.items()):
                    a_k = {q: v for q, v in r0_pq[metric_name].items() if q in qids}
                    b_k = {q: v for q, v in r1_per_query[metric_name].items() if q in qids}
                    bootstrap[metric_name][kcat] = paired_bootstrap_ci(a_k, b_k)

        summary["settings"][setting] = {
            "overall": overall, "by_k": by_k, "elapsed_s": elapsed, "n_queries": len(cases),
            "coverage_by_k": cov_by_k, "coverage_overall": cov_overall,
            "bootstrap_vs_r0": bootstrap, "baseline_path": str(r0_summary_path),
        }
        _write_jsonl_gz(VALIDATION_DIR / f"skillret-r1{out_suffix}-{setting}.jsonl.gz", records)
        added = cov_overall["added_by_dense"]
        gold_n = cov_overall["gold_n"] or 1
        print(f"r1{out_suffix}/{setting}: {elapsed:.1f}s ({elapsed/len(cases)*1000:.1f} ms/query), "
              f"n={len(cases)}, all_required@4={overall.get('all_required@4'):.4f}, "
              f"hit@1={overall.get('hit@1'):.4f}, coverage(bundle)={overall.get('coverage'):.4f}, "
              f"dense-added-gold={added}/{gold_n} ({100*added/gold_n:.2f}%)")

    out_path = VALIDATION_DIR / f"skillret-r1{out_suffix}-summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {out_path}")


# --------------------------------------------------------------------------- cmd: latency
def _machine_spec():
    cpu_model = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    glibc = ""
    try:
        glibc = subprocess.run(["ldd", "--version"], capture_output=True, text=True
                                ).stdout.splitlines()[0]
    except Exception:
        pass
    return {"cpu": cpu_model, "glibc": glibc, "platform": "WSL2",
            "python": sys.version.split()[0]}


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, max(0, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def cmd_latency(args):
    import shutil
    import tempfile

    cli = load_cli()
    data, nodes, cards, id_to_urn, cases, major_of_qid = load_corpus_and_build(cli)
    if getattr(args, "n_skills", 0):
        # T0 size curve (R4b): a deterministic subset -- sorted by SKILLRET's own skill `id`
        # (stable across runs, independent of node/urn construction), first N -- not a random
        # sample, so the same --n-skills value always names the same subset.
        subset_ids = sorted(s["id"] for s in data["skills"])[: args.n_skills]
        subset_urns = {id_to_urn[sid] for sid in subset_ids if sid in id_to_urn}
        cards = {u: c for u, c in cards.items() if u in subset_urns}
    idx = build_r0_index(cli, cards, nodes)  # F0: w_dense=0, the shipped configuration

    scratch = Path(tempfile.mkdtemp(prefix="skillret-latency-"))
    root = scratch / "root"          # outside any git repo -> _git_head_short(root) == "worktree"
    root.mkdir(parents=True)
    cache_root = scratch / "cache"
    cache_root.mkdir(parents=True)
    sha = cli._git_head_short(root)
    assert sha == "worktree", f"expected scratch root outside git, got sha={sha!r}"
    dest = cache_root / "index" / sha
    dest.mkdir(parents=True)

    # Mirror write_index_artifact()'s exact manifest shape (skills/guidefold/scripts/guidefold),
    # not a hand-rolled subset — load_index_artifact() only strictly reads "weights" and
    # "student_dims", but matching the real shape (checksums included) means this scratch
    # artifact is indistinguishable from one `guidefold index` would have produced.
    import hashlib
    files = cli._serialize_artifact_files(idx)
    file_sizes, checksums = {}, {}
    for name, blob in files.items():
        data = blob if isinstance(blob, (bytes, bytearray)) else blob.encode("utf-8")
        p = dest / name
        p.write_bytes(data)
        file_sizes[name] = p.stat().st_size
        checksums[name] = hashlib.sha256(data).hexdigest()
    n_terms = len(idx.idf)
    manifest = {
        "format_version": 1, "git_sha": sha,
        "build_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "builder": "tools/eval/skillret.py latency",
        "teacher": {"id": None, "hf_commit_sha": None, "license": None},
        "student_dims": cli._dense_dims(idx), "quant_scale": 127,
        "weights": idx.weights,
        "counts": {"cards": len(idx.cards), "terms": n_terms, "words": len(idx.word_vectors)},
        "checksums": checksums,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    file_sizes["manifest.json"] = (dest / "manifest.json").stat().st_size
    total_bytes = sum(file_sizes.values())

    n = args.n
    env = dict(os.environ)
    env["GUIDEFOLD_ROOT"] = str(root)
    env["GUIDEFOLD_CACHE"] = str(cache_root)

    def one_hook_call(query_text, node):
        rel_dir = root / (node.replace(".", "/") if node != "_root" else ".")
        rel_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"cwd": str(rel_dir), "prompt": query_text})
        t0 = time.perf_counter()
        subprocess.run([sys.executable, str(CLI_PATH), "hook"], input=payload, text=True,
                        capture_output=True, env=env, cwd=str(rel_dir), timeout=30)
        return (time.perf_counter() - t0) * 1000.0

    queries = [c["query"] for c in cases[: max(n, 1)]] or ["migrate a database schema"]
    while len(queries) < n:
        queries.append(queries[len(queries) % len(queries)])
    queries = queries[:n]

    # cold start: first invocation ever against this fresh cache (page cache still cold for the
    # artifact files) — measured once, separately, before the warm-up call that primes the OS page
    # cache for every subsequent p50/p95 sample.
    cold_ms = one_hook_call(queries[0], "_root")
    one_hook_call(queries[0], "_root")  # warm the OS page cache; excluded from stats

    lat = []
    for q in queries:
        lat.append(one_hook_call(q, "_root"))
    lat_sorted = sorted(lat)
    p50 = _percentile(lat_sorted, 50)
    p95 = _percentile(lat_sorted, 95)
    result = {
        "n": n, "cold_start_ms": cold_ms, "p50_ms": p50, "p95_ms": p95,
        "mean_ms": statistics.mean(lat), "min_ms": min(lat), "max_ms": max(lat),
        "machine": _machine_spec(), "n_skills": len(cards), "n_terms": n_terms,
        "artifact_bytes_total": total_bytes, "artifact_files": file_sizes,
        "gate_t300_ms": 300, "gate_t500_ms": 500,
        "pass_t300": p95 <= 300, "pass_t500": p95 <= 500,
    }
    # --out-suffix (R4b size curve): a subset run (--n-skills < 6,006) must not clobber the
    # canonical skillret-latency.json that the full-corpus T300/T500 gate check reads.
    out_name = f"skillret-latency{getattr(args, 'out_suffix', '') or ''}.json"
    out_path = VALIDATION_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    shutil.rmtree(scratch, ignore_errors=True)


# --------------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats").set_defaults(fn=cmd_stats)

    p_enc = sub.add_parser("encode")
    p_enc.add_argument("--force-any-python", action="store_true")
    p_enc.add_argument("--sample", type=int, default=0, help="only encode the first N skills/queries (dev)")
    p_enc.add_argument("--skill-batch-size", type=int, default=4,
                        help="Encoder batch_size for the long skill (description+body) texts")
    p_enc.add_argument("--skill-chunk-size", type=int, default=200,
                        help="how many skills per Encoder.encode() call (checkpoint granularity)")
    p_enc.set_defaults(fn=cmd_encode)

    p_r0 = sub.add_parser("r0")
    p_r0.add_argument("--sample", type=int, default=0, help="only run the first N cases (dev)")
    p_r0.add_argument("--weights-arm", choices=("shipped", "flat"), default="shipped",
                       help="'flat' overrides the five field.* weights to 1 (frozen sparse "
                            "variant, PR #36) and adds a paired bootstrap vs the committed "
                            "shipped r0 summary")
    p_r0.set_defaults(fn=cmd_r0)

    p_r1 = sub.add_parser("r1")
    p_r1.add_argument("--sample", type=int, default=0, help="only run the first N cases (dev)")
    p_r1.add_argument("--baseline", type=Path, default=VALIDATION_DIR / "skillret-r0-summary.json",
                       help="which r0 summary json to treat as F0 for the bootstrap vs F0 "
                            "(point this at skillret-r0-flat-summary.json to measure R1 over "
                            "the frozen flat-weights base instead of shipped)")
    p_r1.add_argument("--out-suffix", default="",
                       help="appended to skillret-r1<suffix>-{summary.json,root/major.jsonl.gz} "
                            "so a rerun against a non-shipped --baseline does not clobber the "
                            "canonical shipped-baseline R1 files (e.g. '-over-flat')")
    p_r1.set_defaults(fn=cmd_r1)

    p_lat = sub.add_parser("latency")
    p_lat.add_argument("--n", type=int, default=200)
    p_lat.add_argument("--n-skills", type=int, default=0,
                        help="R4b size curve: measure a deterministic subset of the corpus -- "
                             "first N skills sorted by SKILLRET's own skill id -- instead of all "
                             "6,006 (0 = full corpus, the default)")
    p_lat.add_argument("--out-suffix", default="",
                        help="write to skillret-latency<suffix>.json instead of the canonical "
                             "file, so a --n-skills subset run does not clobber the full-corpus "
                             "gate-check result (e.g. '-500skills')")
    p_lat.set_defaults(fn=cmd_latency)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
