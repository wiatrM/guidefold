#!/usr/bin/env python3
"""tools/eval/dev_decompose.py — dev-only evaluation of family D (query decomposition for
multi-skill queries), DENSE-PROGRAM.md v2.5 §4. Never touches test-A/test-B/SkillRetBench (that
run happens once, later, together with family C's frozen composer — see the brief). Every arm
here runs on the same frozen dev split as dev_sparse.py/dev_expand.py
(tools/eval/corpora.py::load_skillret_dev(), 1 000 SKILLRET *train* queries, stratified by k).

The measured fact this family answers (E7.3 dev, 2026-09-05): the shipped whole-query path (D0)
has `all_required@4` 0.842 / 0.069 / 0.000 by k and recall@10 = 0.881 / 0.512 / 0.361 by k — for
three-skill queries, 64% of required skills never make it into the top-10 candidates at all, which
composition (family C) cannot fix because it only re-orders/fills from what candidate generation
already retrieved. D asks whether splitting a multi-intent query into clauses, retrieving per
clause, and merging by RRF gets more of the required skills into the candidate pool in the first
place.

Reused, never reimplemented (import tools/eval/dev_sparse.py wholesale, same convention as
tools/eval/dev_expand.py):
  * corpus_to_cards / queries_to_cases    dev pool -> Guidefold cards / golden-schema cases.
  * _load_cli / _load_metrics             SourceFileLoader for the no-suffix CLI / metrics.py.
  * gf_tokenize                            tools/bakeoff/tokenizer.py's shared tokenizer — used
                                           here only to count a clause candidate's "content
                                           tokens" (the >=3 threshold the brief sets), never to
                                           retokenize anything the product path itself tokenizes.
  * write_jsonl_gz                        per-arm per-query JSONL (gzip), same file convention.
  * PUBLISHER / EVAL_K / K_CARDS / RECORD_TOPN   same constants, same meaning.
tools/eval/skillret.py (never reimplemented either):
  * paired_bootstrap_ci                   the task brief specifically asks for THIS function
                                           (numpy-backed, 1 000 resamples) rather than
                                           dev_sparse.py's own stdlib `bootstrap_paired_delta` —
                                           both compute the same statistic; the brief's choice is
                                           followed literally so family D's CIs are produced by
                                           the same code path a reviewer would use by hand.

skills/guidefold/scripts/guidefold is READ ONLY here — never edited (another agent owns `select()`
in this programme's parallel work). Every arm below calls the REAL, unmodified
`Router.policy_filter` / `Router.candidates` / `Router.score` / `Router.select`; nothing here
reimplements ranking, RRF fusion within a single ranking, requires-closure, admissibility, or the
abstain decision. The one thing built here is what sits ABOVE those calls: splitting a query into
clauses, calling the real per-clause pipeline once per clause, and fusing the per-clause rankings
with a second, higher-level RRF step (same formula, k=60, as the product's own internal
bm25_rank/dense_rank fusion — see `rrf_merge`) before handing a synthetic-but-real `scored`-shaped
list to the REAL `Router.select()` so composition (requires closure, admissibility, the abstain
check, general->specific display order) is exactly what the product would do, never re-derived.

Because every SKILLRET-train dev card has `requires: []` (see dev_sparse.py's own docstring), the
requires-closure walk inside `select()` is a no-op on this corpus for every arm here too — D
measures pure candidate-generation completeness, same caveat dev_sparse.py's `all_required@4`
carries.

Arms (<=6, frozen at pre-registration, DENSE-PROGRAM.md v2.5 §4):
  D0          = the shipped whole-query path (policy_filter -> candidates(top_n=50) -> score ->
                select(k=4)). Never decomposed. The baseline every other arm is paired against.
  D-det-1     deterministic clause splitter (`split_clauses`), per-clause candidate depth 10,
                whole-query ranking NOT in the merge RRF.
  D-det-2     same splitter, per-clause depth 20, whole-query NOT in the RRF.
                (isolates depth: D-det-1 vs D-det-2 change exactly one parameter)
  D-det-3     same splitter, per-clause depth 10, whole-query ranking INCLUDED as an extra RRF
                voter. (isolates the whole-query-in-RRF toggle: D-det-1 vs D-det-3 change exactly
                one parameter) — three configs, coordinate-descent style, per dev_sparse.py's own
                established discipline ("one changed parameter per arm").
  D-model-1   local `claude -p --model haiku` decomposition (replay-cached by sha256(query)),
                per-clause depth 10, whole-query NOT in the RRF — the single-parameter-changed
                pairing against D-det-1 (splitter: deterministic -> model, everything else equal).
  D-model-2   same model decomposition (SAME cache as D-model-1 — the decomposition text does not
                depend on depth), per-clause depth 20, whole-query NOT in the RRF — isolates depth
                for the model splitter, mirroring D-det-1 -> D-det-2.

Cost accounting: a query the splitter does NOT decompose (<=1 usable clause — "the k=1 guard")
costs the arm exactly what D0 already cost: its D-det/D-model record is D0's own record, copied
verbatim, `extra_calls=0`. A query that IS decomposed into n clauses costs n extra
`candidates()`+`score()` calls (one per clause); the optional whole-query RRF voter (D-det-3)
reuses D0's own already-computed ranking for that query at zero extra cost, since D0 runs first
and its full (untruncated to RECORD_TOPN) `scored` list is kept for exactly this reuse.

Subcommands:
  convert       report corpus/query conversion stats only (no Router run, fast — for CI).
  model-cache   populate/extend the on-disk model-decomposition cache by calling the real
                `claude -p --model haiku` once per NOT-YET-CACHED dev query (bounded by
                `--limit`, so a long populate run can be split into several sub-10-minute
                foreground invocations — see the task brief's resumable-chunk rule). Never
                computes metrics. `run` refuses to start unless every dev query already has a
                cached decomposition (fail fast with the missing count, rather than silently
                calling the model mid-metrics-run).
  latency       in-process p95 delta for one product `candidates()+score()` call, at the
                examples/monorepo fixture scale and at SKILLRET-test's 6 006-skill scale (timing
                only — SKILLRET-test's queries/qrels are never read here, per the brief's "do not
                run the test corpora" rule; only its `skills` list is used, to build an Index of
                the right SIZE). Extra cost of a decomposed query is (n_clauses - 1) x this
                per-call cost, reported as an explicit multiplication, not a separately-timed
                "arm p95" (clause-count varies per query, so there is no single such number).
  run           build the shared Index/Router (one Index for the whole file — every arm queries
                the SAME Index, per the brief: "product candidates()+score() on the same Index"),
                run D0 + D-det-1..3 + D-model-1..2 over all 1 000 dev cases, write per-arm
                per-query JSONL (gzip), compute metrics + paired bootstrap CIs vs D0, decomposition
                rates, candidate-ceiling table, cost table, apply the pre-registered freeze rule,
                print tables, write a JSON summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
MONOREPO_DIR = REPO_ROOT / "examples" / "monorepo"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — ONLY pinned-corpus loader
import dev_sparse  # noqa: E402  reused wholesale — see module docstring
import skillret as gf_skillret  # noqa: E402  paired_bootstrap_ci — see module docstring

gf_tokenize = dev_sparse.gf_tokenize
PUBLISHER = dev_sparse.PUBLISHER
EVAL_K = dev_sparse.EVAL_K
K_CARDS = dev_sparse.K_CARDS
RECORD_TOPN = dev_sparse.RECORD_TOPN

# Matches skills/guidefold/scripts/guidefold's Index.RRF_SCALE / Index.RRF_K exactly — the merge
# below is the SAME formula the product uses internally for bm25_rank/dense_rank fusion, applied
# one level up (across per-clause rankings instead of per-channel ones), never a different one.
RRF_SCALE = 1 << 20
RRF_K = 60

MIN_CONTENT_TOKENS = 3
MAX_CLAUSES = 4

MODEL_CACHE_PATH = VALIDATION_DIR / "dev-decompose-model-cache.json"


# ============================================================================ deterministic clause splitter
# Sentence boundaries: ASCII '.', '!', '?' only count as a boundary when followed by whitespace
# or end-of-string -- WITHOUT that lookahead, a bare '.'/'!'/'?' also matches mid-identifier
# ('vite.config.ts', 'mkdocs.yml', 'entry.py') and inside decimals ('3.12'), which are not
# sentence boundaries at all and were confirmed (by hand, on a random sample of real SKILLRET-train
# dev queries -- long, code-dense developer requests where this is common) to inflate the
# decomposition rate with garbage sub-token "clauses". Non-ASCII sentence terminators (ideographic
# full stop U+3002, Arabic question mark U+061F, fullwidth '!'/'?' U+FF01/U+FF1F, horizontal
# ellipsis U+2026) essentially never occur inside a code identifier or a decimal number, so those
# match unconditionally (also: CJK typography conventionally has no space after them). Semicolons:
# ASCII ';' gets the same whitespace-or-EOS lookahead as ASCII sentence enders, for the same
# reason; Arabic ';' U+061B and fullwidth '；' U+FF1B match unconditionally. Coordinating markers
# (word-boundary, case-insensitive), longest/most-specific alternative first so "and then" / ", and
# then" are consumed whole rather than leaving a dangling "then"/"and": ", and then", "and then",
# ", and", "as well as", "also", "plus", "then" — literally the brief's own list, unmodified. This
# splitter is deliberately the naive, over-eager heuristic the brief specifies, not a grammar-aware
# one: it will also fire inside a plain comma-separated enumeration ("Card, Button, and Select")
# that is not really two coordinated clauses, since "sentence boundaries, ;, and coordinating
# markers" is the whole rule pre-registered — over-decomposition on this corpus is itself a
# measured result (the brief's own "decomposing a single-intent query wrongly is the known failure
# mode"), not something patched away here.
_CLAUSE_SPLIT_RE = re.compile(
    r"[.!?]+(?=\s|$)"
    r"|[…。؟！？]+"
    r"|[;]+(?=\s|$)"
    r"|[؛；]+"
    r"|,\s+and\s+then\b"
    r"|\band\s+then\b"
    r"|,\s+and\b"
    r"|\bas\s+well\s+as\b"
    r"|\balso\b"
    r"|\bplus\b"
    r"|\bthen\b",
    re.IGNORECASE,
)


def split_clauses(query: str, max_clauses: int = MAX_CLAUSES,
                   min_content_tokens: int = MIN_CONTENT_TOKENS) -> list:
    """Deterministic stdlib clause splitter (D-det). Splits on sentence boundaries, semicolons,
    and coordinating markers (see `_CLAUSE_SPLIT_RE`); drops any fragment with fewer than
    `min_content_tokens` tokens (per `gf_tokenize`, the shared product tokenizer) — too short to
    be its own retrieval query; caps at `max_clauses` (extra fragments beyond the cap are simply
    dropped, not merged back in — a documented simplification, not silently lossy: `run`'s
    decomposition-rate report counts how often this cap is hit).

    **One-clause guard** (the brief's own k=1 protection): if fewer than 2 usable fragments
    remain, the query is NOT decomposed — returns `[query.strip()]`, a single-element list, so
    every caller can test `len(clauses) >= 2` for "was this query split" without a separate flag.
    """
    raw = _CLAUSE_SPLIT_RE.split(query)
    fragments = [f.strip(" \t\n\r,.;:") for f in raw]
    fragments = [f for f in fragments if f]
    kept = [f for f in fragments if len(gf_tokenize(f)) >= min_content_tokens]
    if len(kept) > max_clauses:
        kept = kept[:max_clauses]
    if len(kept) < 2:
        return [query.strip()]
    return kept


# ============================================================================ model-backed clause splitter (D-model)
_MODEL_PROMPT_TEMPLATE = (
    "Split the following user request into at most 4 short, atomic sub-tasks, one per line, with "
    "no numbering, bullets, or extra commentary -- just the sub-task text on each line. If the "
    "request is already a single atomic task, output it completely unchanged as the only line.\n\n"
    "Request: {query}"
)


def _invoke_claude_haiku(prompt: str, timeout: int = 60) -> str:
    """The ONLY function that spawns the real `claude -p` process. Piped via stdin, not a
    positional argument -- passing the prompt positionally alongside `--tools ""` makes that
    flag's variadic parser swallow it, leaving no prompt (validated by hand during this family's
    development). `--safe-mode` skips CLAUDE.md/skills/hooks/plugins while keeping normal OAuth
    auth (no API key needed in this environment, unlike `--bare`); `--tools ""` disables tool
    access; both together bring real per-call cost down to ~$0.005 with zero cache_creation
    overhead (measured by hand). Tests replace this function with a stub — it is never invoked
    for real during `pytest`."""
    result = subprocess.run(
        ["claude", "-p", "--model", "haiku", "--output-format", "json", "--safe-mode",
         "--tools", ""],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p exited {result.returncode}: {result.stderr[:500]}")
    return result.stdout


def _parse_model_result_text(raw_stdout: str) -> str:
    """Extract the reply text from `claude -p --output-format json`'s envelope (`{"result": ...}`,
    plus cost/duration/session fields this function ignores)."""
    payload = json.loads(raw_stdout)
    return str(payload.get("result", ""))


def _parse_model_lines(result_text: str, max_clauses: int = MAX_CLAUSES,
                        min_content_tokens: int = MIN_CONTENT_TOKENS) -> list:
    lines = [ln.strip(" \t\r-*.•") for ln in result_text.splitlines()]
    lines = [re.sub(r"^\d+[.)]\s*", "", ln).strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    kept = [ln for ln in lines if len(gf_tokenize(ln)) >= min_content_tokens]
    if len(kept) > max_clauses:
        kept = kept[:max_clauses]
    return kept


def load_model_cache(path: Path = MODEL_CACHE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_model_cache(cache: dict, path: Path = MODEL_CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def decompose_via_model(query: str, cache: dict, *, max_clauses: int = MAX_CLAUSES,
                         min_content_tokens: int = MIN_CONTENT_TOKENS, invoke=_invoke_claude_haiku) -> tuple:
    """(clauses, called) — `called` is True only on a genuine cache miss (the real subprocess ran),
    so callers can count real model calls. `cache` is a plain dict keyed by sha256(query) shared,
    on purpose, between D-model-1 and D-model-2 (same decomposition, different per-clause depth —
    the brief's own "D-model-2 may share its cache with D-model-1" rule). Applies the SAME
    one-clause guard as `split_clauses`: fewer than 2 usable lines -> `[query.strip()]`, not
    decomposed — the model is asked, explicitly, to return a one-task query unchanged rather than
    force a split, and this is where that instruction is enforced structurally, not just hoped
    for."""
    key = hashlib.sha256(query.encode("utf-8")).hexdigest()
    if key in cache:
        return list(cache[key]), False
    raw = invoke(_MODEL_PROMPT_TEMPLATE.format(query=query))
    text = _parse_model_result_text(raw)
    lines = _parse_model_lines(text, max_clauses=max_clauses, min_content_tokens=min_content_tokens)
    clauses = lines if len(lines) >= 2 else [query.strip()]
    cache[key] = clauses
    return clauses, True


# ============================================================================ RRF merge + compose
def _rrf_contribution(rank: int) -> int:
    return RRF_SCALE // (RRF_K + rank)


def rrf_merge(voter_ranked_lists: list) -> dict:
    """{urn: merged_rrf_score}. Each voter is an already-best-first urn list (a clause's, or the
    whole query's, product `score()` output); rank is 1-indexed position within that voter's own
    list. Same arithmetic as `Router.score()`'s internal bm25_rank/dense_rank fusion
    (RRF_SCALE // (RRF_K + rank)), applied one level up. A urn absent from a voter's list
    contributes 0 for that voter, standard RRF."""
    merged: dict = {}
    for ranked in voter_ranked_lists:
        for i, u in enumerate(ranked):
            merged[u] = merged.get(u, 0) + _rrf_contribution(i + 1)
    return merged


def compose_priority_order(clause_ranked_lists: list, merged_scores: dict) -> list:
    """"best-scored skill of each clause first, then fill by the merged order" (brief, family D).

    Phase 1 walks the REAL clauses only (never the optional whole-query voter — its own top
    candidate is, in practice, already a clause's top candidate more often than not, so folding it
    into phase 1 too would be redundant at best); each clause contributes its own single best
    urn, first-seen order, deduplicated. Phase 2 appends every remaining urn from the merged RRF
    order. The result is a total order over every candidate any voter produced — a full
    permutation of `merged_scores`'s keys, not a top-k slice — because `select()` itself decides
    the k-cap and the requires-closure expansion; this function only decides priority, never
    membership."""
    phase1, seen = [], set()
    for ranked in clause_ranked_lists:
        if not ranked:
            continue
        top = ranked[0]
        if top not in seen:
            phase1.append(top)
            seen.add(top)
    merged_order = sorted(merged_scores, key=lambda u: (-merged_scores[u], u))
    return phase1 + [u for u in merged_order if u not in seen]


# ============================================================================ per-query product-path runners
def run_d0_case(router, case: dict, top_n: int = 50, k_cards: int = K_CARDS) -> tuple:
    """policy_filter -> candidates -> score -> select, the exact product pipeline — the same four
    calls dev_sparse.py's own `run_product_case` makes, duplicated here (not imported) only
    because this function additionally returns the UNTRUNCATED `scored` list (dev_sparse's version
    truncates to RECORD_TOPN urns with no score attached), so it can be reused as an optional RRF
    voter by D-det-3 at zero extra `candidates()` cost. Never a reimplementation of any Router
    method itself."""
    node, query = case["node"], case["query"]
    admissible, _drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node, top_n=top_n)
    scored = router.score(cands, query, node)
    injected = router.select(scored, k=k_cards, admissible=admissible_set)
    return scored, injected


def d0_record(case: dict, scored: list, injected: list) -> dict:
    return {
        "query_id": case["id"], "k": case["k"], "arm": "D0",
        "ranked": [s["urn"] for s in scored[:RECORD_TOPN]],
        "injected": [c["urn"] for c in injected],
        "abstained": not injected,
        "n_clauses": 1, "decomposed": False, "extra_calls": 0,
    }


def run_decomposed_case(router, case: dict, clauses: list, *, depth: int,
                         whole_query_scored: list = None, include_whole_query_in_rrf: bool = False,
                         k_cards: int = K_CARDS) -> dict:
    """Per clause: real `candidates(top_n=depth)` + `score()` on the SAME Index/query node as D0.
    Merge every clause's ranking (plus, optionally, D0's own already-computed whole-query ranking)
    by RRF; compose the priority order (`compose_priority_order`); hand a synthetic-but-real
    `scored`-shaped list (`[{"urn":..., "score": merged_rrf_score}, ...]`) to the REAL
    `Router.select()` — `select()` reads `c["urn"]`/`c["score"]` from this list and everything else
    (node/name/description, the `requires` graph, admissibility, the abstain threshold) from the
    real `Index`/`admissible_set`, so composition is exactly what the product would do, never
    re-derived."""
    node, query = case["node"], case["query"]
    admissible, _drops = router.policy_filter(node, query)
    admissible_set = set(admissible)

    clause_ranked_lists = []
    for clause in clauses:
        cands = router.candidates(clause, node, top_n=depth)
        scored = router.score(cands, clause, node)
        clause_ranked_lists.append([c["urn"] for c in scored])

    voters = list(clause_ranked_lists)
    if include_whole_query_in_rrf and whole_query_scored is not None:
        voters.append([c["urn"] for c in whole_query_scored])

    merged_scores = rrf_merge(voters)
    priority = compose_priority_order(clause_ranked_lists, merged_scores)
    pseudo_scored = [{"urn": u, "score": merged_scores[u]} for u in priority]
    injected = router.select(pseudo_scored, k=k_cards, admissible=admissible_set)

    ranked_top = sorted(merged_scores, key=lambda u: (-merged_scores[u], u))[:RECORD_TOPN]
    return {
        "query_id": case["id"], "k": case["k"],
        "ranked": ranked_top,
        "injected": [c["urn"] for c in injected],
        "abstained": not injected,
        "n_clauses": len(clauses), "decomposed": True, "extra_calls": len(clauses),
    }


# ============================================================================ arm configuration
ARM_CONFIGS = {
    "D-det-1":   {"splitter": "det",   "depth": 10, "whole_query_rrf": False},
    "D-det-2":   {"splitter": "det",   "depth": 20, "whole_query_rrf": False},
    "D-det-3":   {"splitter": "det",   "depth": 10, "whole_query_rrf": True},
    "D-model-1": {"splitter": "model", "depth": 10, "whole_query_rrf": False},
    "D-model-2": {"splitter": "model", "depth": 20, "whole_query_rrf": False},
}


# ============================================================================ metrics
def per_query_metrics_d(metrics, records: list, cases_by_id: dict) -> dict:
    """{query_id: {...}} — `ranked` (raw merged/D0 list) feeds hit@1/nDCG@10/recall@10 and the
    candidate-ceiling columns (same convention as dev_sparse.py: retrieval-order metrics never use
    the select()-injected list); `injected` (the real select() output) feeds
    `all_required4_injected`, the PRIMARY metric for this family — "did the developer receive the
    whole bundle", which is the number family C's own dev measurement quotes and this family is
    pre-registered against."""
    out = {}
    for rec in records:
        case = cases_by_id[rec["query_id"]]
        ranked, injected = rec["ranked"], rec["injected"]
        out[rec["query_id"]] = {
            "hit1": metrics.hit_at_1(ranked, case),
            "ndcg10": metrics.ndcg_at_k(ranked, case, 10),
            "recall10": metrics.recall_at_k(ranked, case, 10),
            "all_required4_injected": metrics.all_required_at_k(injected, case, 4),
            "ceiling4": metrics.all_required_at_k(ranked, case, 4),
            "ceiling10": metrics.all_required_at_k(ranked, case, 10),
            "ceiling15": metrics.all_required_at_k(ranked, case, 15),
            "ceiling50": metrics.all_required_at_k(ranked, case, 50),
            "decomposed": 1.0 if rec["decomposed"] else 0.0,
            "n_clauses": float(rec["n_clauses"]),
            "extra_calls": float(rec["extra_calls"]),
        }
    return out


def _isnan(x) -> bool:
    return isinstance(x, float) and x != x


def _mean_col(per_q: dict, qids: list, col: str) -> float:
    vals = [per_q[q][col] for q in qids if not _isnan(per_q[q][col])]
    return sum(vals) / len(vals) if vals else float("nan")


def arm_summary_d(per_q: dict, cases: list) -> dict:
    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    cols = ["hit1", "ndcg10", "recall10", "all_required4_injected",
            "ceiling4", "ceiling10", "ceiling15", "ceiling50",
            "decomposed", "n_clauses", "extra_calls"]
    all_qids = [c["id"] for c in cases]

    def block(qids):
        return {"n": len(qids), **{c: _mean_col(per_q, qids, c) for c in cols}}

    out = {"overall": block(all_qids)}
    for k in sorted(by_k):
        out[f"k={k}"] = block(by_k[k])
    return out


def paired_ci(per_q_a: dict, per_q_b: dict, qids: list, metric: str) -> dict:
    """`paired_bootstrap_ci` from tools/eval/skillret.py (the brief's mandated CI function), fed
    the two arms' {query_id: value} maps directly — it already restricts to the common,
    non-NaN-paired qids internally."""
    a = {q: per_q_a[q][metric] for q in qids}
    b = {q: per_q_b[q][metric] for q in qids}
    return gf_skillret.paired_bootstrap_ci(a, b)


# ============================================================================ freeze rule
MIN_BENEFIT = 0.02          # +2.0 pp
HIT1_TOLERANCE = 0.01       # not worse by > 1.0 pp


def evaluate_freeze_gate(d0_per_q: dict, arm_per_q: dict, cases: list) -> dict:
    """The pre-registered rule (DENSE-PROGRAM.md v2.5 / the brief): `all_required@4` overall >=
    D0 + 2.0 pp with the CI excluding 0, AND `hit@1` not worse than D0 by > 1.0 pp overall AND at
    k = 1."""
    all_qids = [c["id"] for c in cases]
    k1_qids = [c["id"] for c in cases if c["k"] == 1]

    primary_ci = paired_ci(d0_per_q, arm_per_q, all_qids, "all_required4_injected")
    passes_primary = (primary_ci["n"] > 0 and primary_ci["mean_delta"] >= MIN_BENEFIT
                       and primary_ci["ci_low"] > 0)

    hit1_overall_delta = _mean_col(arm_per_q, all_qids, "hit1") - _mean_col(d0_per_q, all_qids, "hit1")
    hit1_k1_delta = (_mean_col(arm_per_q, k1_qids, "hit1") - _mean_col(d0_per_q, k1_qids, "hit1")
                      if k1_qids else float("nan"))
    passes_hit1 = (not _isnan(hit1_overall_delta) and hit1_overall_delta >= -HIT1_TOLERANCE
                   and (not k1_qids or (not _isnan(hit1_k1_delta) and hit1_k1_delta >= -HIT1_TOLERANCE)))

    return {
        "primary_ci": primary_ci, "hit1_overall_delta": hit1_overall_delta,
        "hit1_k1_delta": hit1_k1_delta, "passes_primary": passes_primary,
        "passes_hit1": passes_hit1, "passes": bool(passes_primary and passes_hit1),
    }


# ============================================================================ JSONL writer (reused)
write_jsonl_gz = dev_sparse.write_jsonl_gz


# ============================================================================ latency
def _time_calls(router, queries: list, node: str, top_n: int = 50) -> list:
    durations = []
    for q in queries:
        t0 = time.perf_counter()
        cands = router.candidates(q, node, top_n=top_n)
        router.score(cands, q, node)
        durations.append(time.perf_counter() - t0)
    return durations


def _percentile(sorted_vals: list, pct: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = max(0, min(len(sorted_vals) - 1, int(round(pct / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def cmd_latency(_args) -> int:
    cli = dev_sparse._load_cli()

    sys.path.insert(0, str(EVAL_DIR))
    import run_golden  # noqa: E402  load_cases() — real fixture queries, each with its own node

    cfg = cli.load_map(MONOREPO_DIR)
    idx_fixture = cli.Index.build(MONOREPO_DIR, cfg)
    router_fixture = cli.Router(idx_fixture)
    fixture_cases = run_golden.load_cases()
    _time_calls(router_fixture, [fixture_cases[0]["query"]], fixture_cases[0]["node"])  # warm-up
    fixture_times = sorted(
        d for c in fixture_cases
        for d in _time_calls(router_fixture, [c["query"]], c["node"])
    )

    needs = gf_corpora.verify("skillret")
    if needs:
        print(f"skillret corpus not available ({needs[0]}) — 6,006-skill latency scale skipped",
              file=sys.stderr)
        scale_times = []
    else:
        data = gf_corpora.load_skillret()   # TIMING ONLY — never its queries/qrels for metrics
        cards, nodes, _id_to_urn, _report = dev_sparse.corpus_to_cards(data["skills"])
        idx_scale = cli.Index.from_cards(cards, nodes)
        router_scale = cli.Router(idx_scale)
        sample = [q["query"] for q in data["queries"][:200]]
        _time_calls(router_scale, sample[:1], "_root")  # warm-up
        scale_times = sorted(_time_calls(router_scale, sample, "_root"))

    def report(name, times):
        if not times:
            print(f"{name}: (skipped)")
            return
        p50, p95 = _percentile(times, 50), _percentile(times, 95)
        print(f"{name}: n={len(times)} p50={p50*1000:.2f}ms p95={p95*1000:.2f}ms "
              f"mean={ (sum(times)/len(times))*1000 :.2f}ms")
        for extra in (1, 2, 3):
            print(f"  + {extra} extra clause call(s) at this p95: "
                  f"+{extra*p95*1000:.2f}ms added to a decomposed query")

    print("in-process candidates()+score() latency (one call = D0's own cost; a decomposed query "
          "pays this once per extra clause, per the brief's 2-4-retrievals-per-query cost model). "
          "T0 budget is 300ms warm; this is compute only, excludes index-artifact load (R4b: the "
          "dominant fixed cost at 6,006 skills, ~250ms, already accounted for separately).")
    report("fixture (examples/monorepo, 26 skills)", fixture_times)
    report("SKILLRET-test scale (6,006 skills, timing only)", scale_times)
    return 0


# ============================================================================ CLI
def cmd_convert(_args) -> int:
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    det_decomposed = sum(1 for c in cases if len(split_clauses(c["query"])) >= 2)
    print(json.dumps({
        "corpus": corpus_report, "queries": query_report,
        "det_decomposition_rate": det_decomposed / len(cases) if cases else float("nan"),
    }, indent=2, ensure_ascii=False))
    return 0


CHECKPOINT_DIR = VALIDATION_DIR / "dev-decompose-checkpoints"
ALL_ARMS = ["D0"] + list(ARM_CONFIGS)


def _checkpoint_path(arm_name: str) -> Path:
    return CHECKPOINT_DIR / f"{arm_name.lower()}.json"


def _load_checkpoint(arm_name: str) -> dict:
    path = _checkpoint_path(arm_name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(arm_name: str, records_by_qid: dict) -> None:
    path = _checkpoint_path(arm_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(records_by_qid, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _load_dev_cases():
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    return cards, nodes, cases, corpus_report, query_report


def cmd_model_cache(args) -> int:
    """Populate/extend the on-disk model-decomposition cache. Each real `claude -p --model haiku`
    call is ~6-7s (mostly extended-thinking tokens on a trivial task, measured by hand; `--effort
    low` barely moves this), so 1,000 dev queries serially would be ~100 minutes -- fine in
    aggregate but not in a single foreground call under the task's 10-minute Bash timeout.
    `--workers N` runs N independent `claude -p` subprocesses concurrently via a thread pool (each
    call is a fresh, stateless `-p` invocation -- no `--continue`/session reuse, so concurrent
    calls do not share or race on any session state); only the single main thread ever mutates the
    shared cache dict or writes it to disk, so this stays safe under concurrency without a
    cross-process lock. Flushes to disk every 10 completions (or at the end), so a run killed by
    the outer Bash timeout loses at most a small, bounded batch of in-flight calls, never the
    whole chunk -- the next invocation resumes from what is already on disk."""
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    _cards, _nodes, cases, _cr, _qr = _load_dev_cases()
    cache = load_model_cache(args.cache_path)
    already = len(cache)

    to_do = []
    seen_keys = set()
    for case in cases:
        key = hashlib.sha256(case["query"].encode("utf-8")).hexdigest()
        if key not in cache and key not in seen_keys:
            to_do.append((key, case["query"]))
            seen_keys.add(key)
    if args.limit is not None:
        to_do = to_do[:args.limit]

    t0 = time.time()
    done = 0
    errors = 0

    def _work(item):
        key, query = item
        raw = _invoke_claude_haiku(_MODEL_PROMPT_TEMPLATE.format(query=query))
        text = _parse_model_result_text(raw)
        lines = _parse_model_lines(text)
        clauses = lines if len(lines) >= 2 else [query.strip()]
        return key, clauses

    if to_do:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(_work, item): item for item in to_do}
            for fut in as_completed(futures):
                key, query = futures[fut]
                try:
                    k, clauses = fut.result()
                    cache[k] = clauses
                    done += 1
                except Exception as exc:  # noqa: BLE001 -- log and continue, never crash the batch
                    errors += 1
                    print(f"ERROR decomposing (query sha256={key[:12]}...): {exc}", file=sys.stderr)
                if (done + errors) % 10 == 0:
                    save_model_cache(cache, args.cache_path)
                    print(f"[{time.time()-t0:6.1f}s] {done} done / {errors} errors this run "
                          f"({len(cache)}/{len(cases)} cached total)", file=sys.stderr)
        save_model_cache(cache, args.cache_path)

    missing = sum(1 for c in cases if hashlib.sha256(c["query"].encode("utf-8")).hexdigest() not in cache)
    print(f"model cache: {len(cache)} cached ({already} at start, {done} new this run, {errors} "
          f"errors), {missing} dev queries still uncached", file=sys.stderr)
    return 0 if missing == 0 or args.limit is not None else 1


def cmd_run(args) -> int:
    """Case-by-case, checkpointed, resumable (per the brief's "split long runs into resumable
    chunks with on-disk caches" rule): in-process product-pipeline calls at ~120ms/case for D0
    alone, and up to ~4x that per decomposed arm, put a full 6-arm x 1,000-case pass at 15-25
    minutes -- well past a single 600s foreground Bash call. Each of the 6 arms
    (D0 + D-det-1..3 + D-model-1..2) gets its own on-disk JSON checkpoint
    (`{query_id: record}`, flushed atomically every CHECKPOINT_EVERY cases); `--limit` bounds how
    many not-yet-fully-checkpointed cases this invocation processes, so repeated foreground
    invocations make steady, resumable progress. Once every case is present in every arm's
    checkpoint, this same subcommand proceeds straight to writing the per-arm JSONL(gzip),
    metrics, paired CIs, freeze rule, and console tables -- no separate "finalize" step."""
    t0 = time.time()
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    metrics = dev_sparse._load_metrics()
    cli = dev_sparse._load_cli()

    cards, nodes, cases, corpus_report, query_report = _load_dev_cases()
    cases_by_id = {c["id"]: c for c in cases}
    print(f"[{time.time()-t0:6.1f}s] cards={len(cards)} nodes={len(nodes)} cases={len(cases)}",
          file=sys.stderr)
    if query_report["qrel_mismatches"] or query_report["missing_urn"]:
        print("WARNING query/qrel report:", json.dumps(query_report), file=sys.stderr)

    model_cache = load_model_cache()
    missing = [c for c in cases
               if hashlib.sha256(c["query"].encode("utf-8")).hexdigest() not in model_cache]
    if missing:
        print(f"ERROR: {len(missing)}/{len(cases)} dev queries have no cached model decomposition "
              f"— run `dev_decompose.py model-cache` first (see the brief's resumable-chunk "
              f"rule). First missing id: {missing[0]['id']}", file=sys.stderr)
        return 1

    det_clauses_by_qid = {c["id"]: split_clauses(c["query"]) for c in cases}
    model_clauses_by_qid = {}
    for c in cases:
        clauses, _called = decompose_via_model(c["query"], model_cache)
        model_clauses_by_qid[c["id"]] = clauses
    print(f"[{time.time()-t0:6.1f}s] clause splits ready", file=sys.stderr)

    checkpoints = {arm: _load_checkpoint(arm) for arm in ALL_ARMS}
    n_done_at_start = {arm: len(checkpoints[arm]) for arm in ALL_ARMS}
    print(f"[{time.time()-t0:6.1f}s] checkpoints at start: "
          + ", ".join(f"{a}={n_done_at_start[a]}/{len(cases)}" for a in ALL_ARMS), file=sys.stderr)

    remaining = [c for c in cases if any(c["id"] not in checkpoints[arm] for arm in ALL_ARMS)]
    if remaining:
        idx = cli.Index.from_cards(cards, nodes)
        router = cli.Router(idx)
        print(f"[{time.time()-t0:6.1f}s] built shared Index ({len(cards)} cards); "
              f"{len(remaining)} cases still need at least one arm", file=sys.stderr)

        processed_this_run = 0
        CHECKPOINT_EVERY = 20
        for case in remaining:
            if args.limit is not None and processed_this_run >= args.limit:
                break
            qid = case["id"]
            needed_arms = [a for a in ALL_ARMS if qid not in checkpoints[a]]
            d0_scored = d0_injected = None
            if needed_arms:
                d0_scored, d0_injected = run_d0_case(router, case, top_n=50, k_cards=K_CARDS)
            if "D0" in needed_arms:
                checkpoints["D0"][qid] = d0_record(case, d0_scored, d0_injected)
            for arm_name in ARM_CONFIGS:
                if arm_name not in needed_arms:
                    continue
                cfg = ARM_CONFIGS[arm_name]
                clauses = (det_clauses_by_qid if cfg["splitter"] == "det" else model_clauses_by_qid)[qid]
                if len(clauses) < 2:
                    rec = {**d0_record(case, d0_scored, d0_injected), "arm": arm_name}
                else:
                    whole = d0_scored if cfg["whole_query_rrf"] else None
                    rec = run_decomposed_case(router, case, clauses, depth=cfg["depth"],
                                               whole_query_scored=whole,
                                               include_whole_query_in_rrf=cfg["whole_query_rrf"],
                                               k_cards=K_CARDS)
                    rec["arm"] = arm_name
                checkpoints[arm_name][qid] = rec
            processed_this_run += 1
            if processed_this_run % CHECKPOINT_EVERY == 0:
                for arm in ALL_ARMS:
                    _save_checkpoint(arm, checkpoints[arm])
                print(f"[{time.time()-t0:6.1f}s] {processed_this_run}/{len(remaining)} cases "
                      f"this run ({len(checkpoints['D0'])}/{len(cases)} D0 total)", file=sys.stderr)
        for arm in ALL_ARMS:
            _save_checkpoint(arm, checkpoints[arm])
        save_model_cache(model_cache)   # no-op if unchanged (verified fully cached above)
        print(f"[{time.time()-t0:6.1f}s] processed {processed_this_run} cases this invocation",
              file=sys.stderr)

    still_missing = {arm: [c["id"] for c in cases if c["id"] not in checkpoints[arm]]
                      for arm in ALL_ARMS}
    if any(still_missing.values()):
        print("not yet complete -- re-run `dev_decompose.py run` to continue (checkpoints on "
              "disk under docs/reports/bakeoff/validation/dev-decompose-checkpoints/):",
              file=sys.stderr)
        for arm, ids in still_missing.items():
            if ids:
                print(f"  {arm}: {len(ids)} cases remaining", file=sys.stderr)
        return 0

    records_by_arm = {arm: [checkpoints[arm][c["id"]] for c in cases] for arm in ALL_ARMS}

    # ---- write per-arm JSONL (gzip) ----
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for arm_name, records in records_by_arm.items():
        fname = f"dev-decompose-{arm_name.lower()}.jsonl.gz"
        write_jsonl_gz(VALIDATION_DIR / fname, records)
        print(f"[{time.time()-t0:6.1f}s] wrote {fname}", file=sys.stderr)

    # ---- per-query metrics / summaries ----
    per_query_by_arm = {arm: per_query_metrics_d(metrics, recs, cases_by_id)
                        for arm, recs in records_by_arm.items()}
    summary = {arm: arm_summary_d(per_q, cases) for arm, per_q in per_query_by_arm.items()}

    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    all_qids = [c["id"] for c in cases]
    breakdowns = {"overall": all_qids, **{f"k={k}": qids for k, qids in sorted(by_k.items())}}

    # ---- paired CIs vs D0 (all_required4_injected primary; hit1/ndcg10/recall10 guard/context) ----
    comparisons = {}
    for arm_name in ARM_CONFIGS:
        comparisons[arm_name] = {}
        for bd_name, qids in breakdowns.items():
            comparisons[arm_name][bd_name] = {
                metric: paired_ci(per_query_by_arm["D0"], per_query_by_arm[arm_name], qids, metric)
                for metric in ("all_required4_injected", "hit1", "ndcg10", "recall10")
            }

    # ---- freeze rule ----
    freeze = {arm_name: evaluate_freeze_gate(per_query_by_arm["D0"], per_query_by_arm[arm_name], cases)
              for arm_name in ARM_CONFIGS}
    det_candidates = [a for a in ("D-det-1", "D-det-2", "D-det-3") if freeze[a]["passes"]]
    model_candidates = [a for a in ("D-model-1", "D-model-2") if freeze[a]["passes"]]
    frozen_det = max(det_candidates, key=lambda a: freeze[a]["primary_ci"]["mean_delta"], default=None)
    frozen_model = max(model_candidates, key=lambda a: freeze[a]["primary_ci"]["mean_delta"], default=None)

    # "how many model calls did THIS run make" is 0 by construction (cache verified complete
    # above, `run` never calls the model itself) -- what the report wants instead is how many of
    # the 1,000 dev queries required a (cached, already-paid-for) model decomposition at all.
    model_calls_total = sum(
        1 for c in cases if hashlib.sha256(c["query"].encode("utf-8")).hexdigest() in model_cache
    )

    out = {
        "corpus_report": corpus_report, "query_report": query_report, "n_cases": len(cases),
        "summary": summary, "comparisons": comparisons, "freeze": freeze,
        "frozen_det": frozen_det, "frozen_model": frozen_model,
        "model_cache_size": len(model_cache), "model_calls_covering_dev": model_calls_total,
        "runtime_s": time.time() - t0,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {args.out}", file=sys.stderr)

    # ---- console tables ----
    cols = ["n", "hit1", "ndcg10", "recall10", "all_required4_injected",
            "ceiling4", "ceiling10", "ceiling15", "ceiling50", "decomposed", "n_clauses", "extra_calls"]
    head = f"{'arm':<12}{'break':<8}" + "".join(f"{c:>16}" for c in cols)
    print(head)
    print("-" * len(head))
    for arm_name, blocks in summary.items():
        for bd_name in ["overall"] + [f"k={k}" for k in sorted(by_k)]:
            m = blocks[bd_name]
            row = f"{arm_name:<12}{bd_name:<8}"
            for c in cols:
                v = m[c]
                row += f"{v:>16}" if isinstance(v, int) else (
                    f"{'—':>16}" if _isnan(v) else f"{v:>16.4f}")
            print(row)

    print("\nfreeze rule: all_required4_injected overall >= D0+2.0pp (CI excl. 0) AND hit@1 not "
          "worse by >1.0pp overall/k=1")
    for arm_name, f in freeze.items():
        ci = f["primary_ci"]
        print(f"  {arm_name:<12} delta={ci['mean_delta']*100:+.2f}pp "
              f"[{ci['ci_low']*100:+.2f},{ci['ci_high']*100:+.2f}]  "
              f"hit1_overall={f['hit1_overall_delta']*100:+.2f}pp "
              f"hit1_k1={f['hit1_k1_delta']*100:+.2f}pp  PASSES={f['passes']}")
    print(f"\nfrozen D-det:   {frozen_det or 'NONE — no D-det arm passed the freeze rule'}")
    print(f"frozen D-model: {frozen_model or 'NONE — no D-model arm passed the freeze rule'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("convert", help="report corpus/query/decomposition-rate stats only")
    p_mc = sub.add_parser("model-cache", help="populate the on-disk model-decomposition cache")
    p_mc.add_argument("--limit", type=int, default=None,
                       help="max NEW real model calls this invocation (resumable chunking)")
    p_mc.add_argument("--workers", type=int, default=6,
                       help="concurrent claude -p subprocesses (each call is independent/stateless)")
    p_mc.add_argument("--cache-path", type=Path, default=MODEL_CACHE_PATH)
    sub.add_parser("latency", help="in-process candidates()+score() latency, fixture + 6,006-skill scale")
    p_run = sub.add_parser("run", help="run every arm (D0 + D-det-1..3 + D-model-1..2) over the dev split")
    p_run.add_argument("--out", type=Path, default=VALIDATION_DIR / "dev-decompose-metrics.json")
    p_run.add_argument("--limit", type=int, default=None,
                        help="max not-yet-fully-checkpointed cases to process this invocation "
                             "(resumable chunking; omit to attempt all remaining cases)")
    args = ap.parse_args(argv)
    if args.cmd == "convert":
        return cmd_convert(args)
    if args.cmd == "model-cache":
        return cmd_model_cache(args)
    if args.cmd == "latency":
        return cmd_latency(args)
    if args.cmd == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
