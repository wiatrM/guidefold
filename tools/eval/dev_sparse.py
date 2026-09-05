#!/usr/bin/env python3
"""tools/eval/dev_sparse.py — dev-only diagnosis of why the shipped BM25F trails plain textbook
BM25 by roughly 12 points of nDCG@10 on two independent real corpora (test-A SKILLRET-test,
test-B SkillRetBench; see docs/reports/bakeoff/DENSE-PROGRAM.md SS7). This script never touches
test-A or test-B: every arm here runs on the frozen dev split
(tools/eval/corpora.py::load_skillret_dev(), DENSE-PROGRAM.md v2 SS3) — 1 000 SKILLRET *train*
queries, stratified by k and major, against the full 10 123-skill SKILLRET train pool. The
frozen configuration this script proposes is evaluated on test-A/test-B by someone else, later,
not here.

Reused, never reimplemented:
  * tools/eval/corpora.py       load_skillret_dev() — the ONLY place that opens the pinned dev
                                 split / cached SKILLRET train files.
  * tools/eval/metrics.py       hit_at_1 / recall_at_k / ndcg_at_k / all_required_at_k / evaluate
                                 / by_category.
  * tools/bakeoff/tokenizer.py  tokenize() — THE shared tokenizer, used by every "ours" arm
                                 (product path) AND by the R-BM25 reference arm, so a tokenizer
                                 difference can be isolated as its own arm (R-BM25-simple-tok)
                                 instead of being a hidden confound in every comparison.
  * skills/guidefold/scripts/guidefold   Index.from_cards, Router (policy_filter -> candidates ->
                                 score -> select(admissible=...)) — the actual product code, for
                                 every "P-*" arm. Never a reimplementation of the Router.

Two families of arm:
  R-*   a from-scratch textbook Okapi BM25 reference, deliberately independent of the product's
        Index/Router code (only the tokenizer is optionally shared). This is the yardstick.
  P-*   the real product path (Index.from_cards -> Router), varied by exactly ONE parameter per
        arm (coordinate descent, not a grid), each compared against R-BM25 and against P-shipped.

Card construction (dev skills -> Guidefold cards), stated once, not re-derived per arm:
  urn        urn:skill:skillret:<major-slug>.<sub-slug>:<slug(id)> — id is already a UUID (lower
             hex + hyphens), so slug(id) == id; the slug function is still applied literally, per
             spec, rather than assumed to be a no-op.
  node       "<major-slug>.<sub-slug>", a two-level tree under `_root` (majors are intermediate
             nodes with no cards of their own; 6 majors, 18 major.sub leaves, matching the
             dataset's own major/sub taxonomy exactly — no re-bucketing).
  name       the skill's own human name (e.g. "brainstorming") — feeds the highest-weighted BM25F
             field (field.name=6). Not part of the URN (the URN's last segment is the id slug),
             so Index.build's own urn==urn(cfg,node,name) invariant does not apply here; from_cards
             does not enforce it either (confirmed by reading Index.from_cards/Router.__init__).
  description  the dataset's own `description` field, verbatim.
  digest     description[:200] — Index.build's own fallback when a real SKILL.md carries no
             metadata.digest, not an invented convention (see skills/guidefold/scripts/guidefold's
             Index.build).
  body       the dataset's `body` field (confirmed byte-identical to `skill_md` for all 10 123
             train skills) with the skill's OWN embedded frontmatter block stripped first
             (`strip_own_frontmatter`) — otherwise the BM25F body field would double-count every
             name/description word already scored in its own dedicated field. 10 102/10 123
             bodies matched the `---\\n...\\n---` frontmatter pattern; the other 21 are left
             unchanged (a no-op sub, not a special case).
  triggers, negative_triggers, requires, refines   all [] — per the task brief ("no
             triggers/negatives/requires"): this corpus carries none of those fields, and F5-style
             offline enrichment is out of scope for this diagnosis.
  status     "active" for every card (no deprecation signal in this corpus).

Because every dev card has `requires: []`, `Router.select()`'s dependency-closure walk is always a
no-op here (confirmed by reading `_requires_closure`) — `all_required@4` on this corpus measures
pure retrieval quality (all required gold skills landing in the top 4 by score alone), never
graph-assisted completeness. See the report for what that implies for k=3 queries (3 required
skills, k_cards=4, zero structural closure to help).

Because every dev query is scored at node="_root" (Setting: _root only, per brief) and there is
no BM25/derived requires-graph in this corpus, several of the ablations below are PREDICTED to be
byte-identical to P-shipped's ranking before they are ever run (RRF is a strictly monotonic
transform of bm25_rank; w_scope adds one per-query CONSTANT since every major.sub node is exactly
2 hops from _root; the closure/PPR propagation step is a per-candidate affine rescale of its own
seed value when the graph has zero requires edges; top_n only changes which urns enter the
candidate pool, never their bm25_rank, and the true top-10 by bm25_rank always sits inside the
top-50 pool already). Each such prediction is still run and empirically checked, not assumed away.

Subcommands:
  convert   report corpus/query conversion stats only (no Router run, fast — for tests/CI)
  run       build every arm, run all 1 000 dev cases through each, write per-arm per-query JSONL
            (gzip) under docs/reports/bakeoff/validation/, compute metrics + paired bootstrap CIs
            vs R-BM25 and vs P-shipped, print the tables, and write a JSON summary.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import random
import re
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
BAKEOFF_DIR = REPO_ROOT / "tools" / "bakeoff"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — ONLY pinned-corpus loader

sys.path.insert(0, str(BAKEOFF_DIR))
from tokenizer import tokenize as gf_tokenize  # noqa: E402  THE shared tokenizer

PUBLISHER = "skillret"
EVAL_K = 10        # hit@1 / nDCG@10 / recall@10's k
K_CARDS = 4        # all_required@4's k (select()'s k)
RECORD_TOPN = 50   # per-query JSONL keeps the top-N of each ranking, not all 10 123 — see report


def _load_cli():
    """Same pattern as tools/eval/skillretbench.py: the CLI has no .py suffix (it ships as a
    single executable file inside the skill ZIP), so a plain `import` cannot find it."""
    loader = SourceFileLoader("guidefold_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load_metrics():
    spec = importlib.util.spec_from_file_location("gf_metrics", EVAL_DIR / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------------- naive tokenizer (R-BM25-simple-tok)
_SIMPLE_WORD_RE = re.compile(r"[a-z0-9]+")


def simple_tokenize(text: str) -> list:
    """The naive tokenizer the task asks R-BM25-simple-tok to isolate: plain `str.lower()` (NOT
    ASCII-only, NOT accent-folded — the opposite of tools/bakeoff/tokenizer.py's deliberate NFKD
    fold) then split on [a-z0-9]+. An accented word ("café") therefore tokenizes to nothing
    useful ("caf") instead of folding to its base letters ("cafe")."""
    if not text:
        return []
    return _SIMPLE_WORD_RE.findall(text.lower())


# ------------------------------------------------------------------------- slugify (card/node construction)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    return _SLUG_RE.sub("-", (s or "").strip().lower()).strip("-")


# ------------------------------------------------------------------------- frontmatter stripping
# Same rationale/pattern as tools/eval/skillretbench.py's strip_own_frontmatter: a real skill's
# body is a complete SKILL.md file, frontmatter included; the shipped product's Index.build()
# only ever tokenizes a real skill's body AFTER its frontmatter closes, so leaving it in would
# double-count name/description words in the BM25 body field on top of their own dedicated fields.
_OWN_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.S)


def strip_own_frontmatter(full_text: str) -> str:
    return _OWN_FRONTMATTER_RE.sub("", full_text, count=1).lstrip("\n")


# ============================================================================ R-BM25 reference
class ReferenceBM25:
    """Textbook single-field Okapi BM25 (Robertson/Sparck-Jones): k1=1.2, b=0.75, standard IDF
    ln((N-n+0.5)/(n+0.5)+1). One document = one concatenated text; every doc in `docs` is scored,
    no candidate cap, no policy filter. Deliberately independent of
    skills/guidefold/scripts/guidefold's Index/Router — it shares nothing with the product code
    except, optionally, the tokenizer function it is constructed with (that dependency is exactly
    what R-BM25 vs R-BM25-simple-tok isolates). Kept plain and short so it can be hand-verified
    (see tests/test_dev_sparse.py) rather than trusted.
    """

    K1 = 1.2
    B = 0.75

    def __init__(self, docs: dict, tokenize_fn):
        self.tokenize = tokenize_fn
        self.doc_ids = list(docs)
        doc_toks = {u: tokenize_fn(t) for u, t in docs.items()}
        self.doc_len = {u: len(toks) for u, toks in doc_toks.items()}
        n_docs = len(self.doc_ids)
        self.n_docs = n_docs
        self.avgdl = (sum(self.doc_len.values()) / n_docs) if n_docs else 1.0
        postings: dict = {}
        for u, toks in doc_toks.items():
            tf: dict = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            for t, n in tf.items():
                postings.setdefault(t, {})[u] = n
        self.postings = postings
        self.idf = {
            t: math.log((n_docs - len(post) + 0.5) / (len(post) + 0.5) + 1.0)
            for t, post in postings.items()
        }

    def score_all(self, query: str) -> dict:
        scores: dict = {}
        for t in self.tokenize(query):
            post = self.postings.get(t)
            idf = self.idf.get(t)
            if not post or idf is None:
                continue
            for u, tf in post.items():
                dl = self.doc_len[u] or 1
                denom = tf + self.K1 * (1 - self.B + self.B * dl / self.avgdl)
                scores[u] = scores.get(u, 0.0) + idf * (tf * (self.K1 + 1)) / denom
        return scores

    def rank(self, query: str) -> list:
        """Every doc in the pool, ranked — "no filter, no cap" per the task brief. Scored docs
        come first (score desc, urn asc — the same deterministic tie-break convention as the
        product Router's own `sort(key=lambda c: (-c["score"], c["urn"]))`); unscored docs (no
        query term matched them at all) follow, sorted by urn, so the full ranking is total and
        deterministic."""
        scores = self.score_all(query)
        ranked = [u for u, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]
        rest = sorted(u for u in self.doc_ids if u not in scores)
        return ranked + rest


# ============================================================================ corpus -> cards
def corpus_to_cards(skills: list) -> tuple:
    """SKILLRET train skill dict -> Guidefold card dict. Returns (cards, nodes, id_to_urn, report).
    `id_to_urn` is this script's own bookkeeping (not a card field) so queries_to_cases can resolve
    a query's raw `skill_ids` to the card urn without guessing at a naming convention."""
    majors = sorted({s["major"] for s in skills})
    major_slug = {m: slugify(m) for m in majors}
    sub_slug = {}
    for s in skills:
        sub_slug[(s["major"], s["sub"])] = slugify(s["sub"])

    def _collisions(pairs):
        seen: dict = {}
        for key, slug in pairs:
            seen.setdefault(slug, []).append(key)
        return {slug: keys for slug, keys in seen.items() if len(keys) > 1}

    major_slug_collisions = _collisions(major_slug.items())
    sub_slug_collisions = _collisions(
        ((f"{major_slug[m]}.{sub}", f"{major_slug[m]}.{ss}") for (m, sub), ss in sub_slug.items())
    )

    nodes = {"_root": {"paths": ["_root/**"], "owner": PUBLISHER}}
    for m in majors:
        ms = major_slug[m]
        nodes[ms] = {"paths": [f"{ms}/**"], "owner": PUBLISHER}
    for (m, sub), ss in sub_slug.items():
        ms = major_slug[m]
        nodes[f"{ms}.{ss}"] = {"paths": [f"{ms}/{ss}/**"], "owner": PUBLISHER}

    cards, id_to_urn = {}, {}
    dup_ids = []
    for s in skills:
        sid = s["id"]
        if sid in id_to_urn:
            dup_ids.append(sid)
            continue
        ms = major_slug[s["major"]]
        ss = sub_slug[(s["major"], s["sub"])]
        node = f"{ms}.{ss}"
        u = f"urn:skill:{PUBLISHER}:{node}:{slugify(sid)}"
        id_to_urn[sid] = u
        description = str(s.get("description", ""))
        cards[u] = {
            "urn": u, "node": node, "name": str(s.get("name", "")),
            "description": description,
            "digest": description[:200],
            "triggers": [], "negative_triggers": [],
            "requires": [], "refines": [],
            "status": "active", "replaced_by": None,
            "kind": None, "layer": None, "owner": PUBLISHER,
            "_body": strip_own_frontmatter(str(s.get("body", ""))),
        }
    report = {
        "n_skills": len(skills), "n_cards": len(cards),
        "n_majors": len(majors), "n_major_sub_nodes": len(sub_slug),
        "n_nodes_total": len(nodes),
        "dup_ids": dup_ids,
        "major_slug_collisions": major_slug_collisions,
        "sub_slug_collisions": sub_slug_collisions,
    }
    return cards, nodes, id_to_urn, report


def queries_to_cases(queries: list, qrels: list, id_to_urn: dict) -> tuple:
    """SKILLRET train query -> a golden-schema case dict (tests/golden/*.yaml shape, plus the `k`
    the dev split stratified on). `skill_ids[0]` -> grade 3 (must be rank 1), the rest -> grade 2
    (required companions) — literally the task brief's grading rule, read off the query's own
    field. `qrels` is cross-checked (not re-derived from): every dev query's qrel set is asserted
    against its own `skill_ids`, and a mismatch is counted, not silently trusted either way."""
    qrel_by_query: dict = {}
    for r in qrels:
        qrel_by_query.setdefault(r["query_id"], set()).add(r["skill_id"])

    cases = []
    qrel_mismatches = []
    missing_urn = []
    dropped_empty_gold = 0
    for q in queries:
        gold = list(q.get("skill_ids") or [])
        if not gold:
            dropped_empty_gold += 1
            continue
        qr = qrel_by_query.get(q["id"], set())
        if set(gold) != qr:
            qrel_mismatches.append(q["id"])
        relevant = []
        for i, sid in enumerate(gold):
            u = id_to_urn.get(sid)
            if u is None:
                missing_urn.append((q["id"], sid))
                continue
            relevant.append({"urn": u, "grade": 3 if i == 0 else 2})
        if not relevant:
            continue
        cases.append({
            "id": q["id"], "query": q["query"], "node": "_root",
            "k": q.get("k", len(gold)),
            "relevant": relevant, "distractors": [],
        })
    report = {
        "n_queries": len(queries), "n_cases": len(cases),
        "dropped_empty_gold": dropped_empty_gold,
        "qrel_mismatches": qrel_mismatches, "missing_urn": missing_urn,
    }
    return cases, report


def build_reference_docs(cards: dict) -> dict:
    """One concatenated text per card: name + description + body — exactly R-BM25's stated
    input, built once and shared by both R-BM25 and R-BM25-simple-tok so the two differ by
    tokenizer alone."""
    return {u: " ".join([c["name"], c["description"], c["_body"]]) for u, c in cards.items()}


# ============================================================================ product-path (P-*) arms
def concat_all_fields(c: dict) -> str:
    """Same "squash a card into one bag of text" convention as the product's own
    Index._build_dense (read from skills/guidefold/scripts/guidefold) — reused here, not
    reinvented, for P-onefield's card transform."""
    return " ".join([c["name"].replace("-", " "), c["description"], c["digest"],
                      " ".join(c["triggers"]), c["_body"]])


def onefield_cards(cards: dict) -> dict:
    """P-onefield: concat everything into `body`, every other field emptied — isolates
    Index._build_bm25's per-field independent length normalisation/weighting from the single-field
    textbook shape R-BM25 uses."""
    out = {}
    for u, c in cards.items():
        text = concat_all_fields(c)
        out[u] = {**c, "name": "", "description": "", "digest": "", "triggers": [], "_body": text}
    return out


def make_k1b_index_cls(cli):
    """P-k1b: k1=0.9, b=0.4. K1/B are class attributes on Index (not weights-dict entries), so a
    subclass is the only way to override them; `Index.from_cards` is a classmethod (`cls(...)`),
    so calling it on the subclass builds a real, correctly-typed instance — confirmed by reading
    `Index.from_cards`/`Index._build_bm25`/`Router._bm25_scores` (all read `self.K1`/`idx.K1`,
    which resolves through the subclass's MRO)."""
    class _K1BIndex(cli.Index):
        K1 = 0.9
        B = 0.4
    return _K1BIndex


def run_product_case(router, case: dict, top_n: int = 50, k_cards: int = K_CARDS) -> dict:
    """policy_filter -> candidates -> score -> select, the exact product pipeline, never a
    reimplementation."""
    node, query = case["node"], case["query"]
    admissible, drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node, top_n=top_n)
    scored = router.score(cands, query, node)
    injected = router.select(scored, k=k_cards, admissible=admissible_set)
    drop_reasons: dict = {}
    for _, reason in drops:
        key = reason.split(":", 1)[0]
        drop_reasons[key] = drop_reasons.get(key, 0) + 1
    return {
        "query_id": case["id"], "k": case["k"],
        "ranked": [s["urn"] for s in scored[:RECORD_TOPN]],
        "injected": [c["urn"] for c in injected],
        "abstained": not injected,
        "admissible_size": len(admissible_set),
        "drops": drop_reasons,
    }


def run_reference_case(ref: ReferenceBM25, case: dict) -> dict:
    ranked = ref.rank(case["query"])
    return {"query_id": case["id"], "k": case["k"], "ranked": ranked[:RECORD_TOPN]}


# ============================================================================ metrics / bootstrap
def bootstrap_paired_delta(vals_a: list, vals_b: list, n_resamples: int = 1000, seed: int = 0) -> dict:
    """95% CI (percentile method) on mean(vals_b) - mean(vals_a); paired bootstrap over query
    indices (the same resampled query set scores both arms per replicate, so per-query noise
    cancels rather than compounds). Same method, 1 000 resamples, as
    tools/eval/skillretbench.py's own `_bootstrap_paired_delta` (DENSE-PROGRAM.md SS5) —
    reimplemented here (not imported) so this script has no import-time dependency on another
    eval script's internals; `vals_a`/`vals_b` must already be paired (same query order,
    same length, no NaN)."""
    n = len(vals_a)
    if n == 0 or n != len(vals_b):
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"),
                "n_resamples": n_resamples, "n": n}
    observed = sum(vals_b) / n - sum(vals_a) / n
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        a = sum(vals_a[i] for i in idx) / n
        b = sum(vals_b[i] for i in idx) / n
        deltas.append(b - a)
    deltas.sort()
    lo = deltas[int(0.025 * n_resamples)]
    hi = deltas[min(n_resamples - 1, int(0.975 * n_resamples))]
    return {"delta": observed, "ci_lo": lo, "ci_hi": hi, "n_resamples": n_resamples, "n": n}


def per_query_metrics(metrics, ranked_by_qid: dict, cases: list, k: int = EVAL_K) -> dict:
    """{query_id: {"hit1":, "ndcg10":, "recall10":, "all_required4":}} — `all_required4` here is
    computed on the RAW ranked list's top-4 (never a select()-injected list), so it is comparable
    across every arm including the reference arms, which have no select() step. P-shipped's own
    select()-injected all_required@4 is computed separately (see `run` / the report) because the
    task specifically asks for the product's real injection behaviour (abstain included)."""
    out = {}
    for case in cases:
        qid = case["id"]
        ranked = ranked_by_qid[qid]
        out[qid] = {
            "hit1": metrics.hit_at_1(ranked, case),
            "ndcg10": metrics.ndcg_at_k(ranked, case, k),
            "recall10": metrics.recall_at_k(ranked, case, k),
            "all_required4": metrics.all_required_at_k(ranked, case, 4),
        }
    return out


def arm_summary(metrics, per_q: dict, cases: list) -> dict:
    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    out = {"overall": _mean_block(per_q, [c["id"] for c in cases])}
    for k in sorted(by_k):
        out[f"k={k}"] = _mean_block(per_q, by_k[k])
    return out


def _mean_block(per_q: dict, qids: list) -> dict:
    def col(name):
        vals = [per_q[q][name] for q in qids if not _isnan(per_q[q][name])]
        return sum(vals) / len(vals) if vals else float("nan")
    return {"n": len(qids), "hit1": col("hit1"), "ndcg10": col("ndcg10"),
            "recall10": col("recall10"), "all_required4": col("all_required4")}


def _isnan(x) -> bool:
    return isinstance(x, float) and x != x


def paired_arrays(per_q_a: dict, per_q_b: dict, qids: list, metric: str) -> tuple:
    a, b = [], []
    for q in qids:
        va, vb = per_q_a[q][metric], per_q_b[q][metric]
        if _isnan(va) or _isnan(vb):
            continue
        a.append(va)
        b.append(vb)
    return a, b


# ============================================================================ JSONL writer
def write_jsonl_gz(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ============================================================================ CLI
def cmd_convert(args) -> int:
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = corpus_to_cards(data["skills"])
    cases, query_report = queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    print(json.dumps({"corpus": corpus_report, "queries": query_report}, indent=2, ensure_ascii=False))
    return 0


def _build_product_arms(cli, cards: dict, nodes: dict) -> dict:
    """name -> (index, router, top_n). Each differs from P-shipped by exactly one parameter."""
    arms = {}
    idx_shipped = cli.Index.from_cards(cards, nodes)
    arms["P-shipped"] = (idx_shipped, cli.Router(idx_shipped), 50)

    flat_weights = {f"field.{f}": 1 for f in cli.Index.FIELDS}
    idx_flat = cli.Index.from_cards(cards, nodes, weights=flat_weights)
    arms["P-flat"] = (idx_flat, cli.Router(idx_flat), 50)

    idx_onefield = cli.Index.from_cards(onefield_cards(cards), nodes)
    arms["P-onefield"] = (idx_onefield, cli.Router(idx_onefield), 50)

    idx_nopprocl = cli.Index.from_cards(cards, nodes, weights={"w_ppr": 0})
    arms["P-nopprocl"] = (idx_nopprocl, cli.Router(idx_nopprocl), 50)

    idx_noscope = cli.Index.from_cards(cards, nodes, weights={"w_scope": 0})
    arms["P-noscope"] = (idx_noscope, cli.Router(idx_noscope), 50)

    # P-top200 reuses the SAME index/router as P-shipped -- only Router.candidates(top_n=) changes.
    arms["P-top200"] = (idx_shipped, cli.Router(idx_shipped), 200)

    k1b_cls = make_k1b_index_cls(cli)
    idx_k1b = k1b_cls.from_cards(cards, nodes)
    arms["P-k1b"] = (idx_k1b, cli.Router(idx_k1b), 50)
    return arms


def cmd_run(args) -> int:
    t0 = time.time()
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    metrics = _load_metrics()
    cli = _load_cli()

    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = corpus_to_cards(data["skills"])
    cases, query_report = queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    print(f"[{time.time()-t0:6.1f}s] cards={len(cards)} nodes={len(nodes)} cases={len(cases)}",
          file=sys.stderr)
    if query_report["qrel_mismatches"] or query_report["missing_urn"]:
        print("WARNING query/qrel report:", json.dumps(query_report), file=sys.stderr)

    all_qids = [c["id"] for c in cases]
    per_query_by_arm: dict = {}
    records_by_arm: dict = {}

    # ---- R-BM25 / R-BM25-simple-tok ----
    ref_docs = build_reference_docs(cards)
    for arm_name, tok in (("R-BM25", gf_tokenize), ("R-BM25-simple-tok", simple_tokenize)):
        ref = ReferenceBM25(ref_docs, tok)
        ranked_by_qid, records = {}, []
        for case in cases:
            rec = run_reference_case(ref, case)
            ranked_by_qid[rec["query_id"]] = rec["ranked"]
            records.append({**rec, "arm": arm_name})
        per_query_by_arm[arm_name] = per_query_metrics(metrics, ranked_by_qid, cases)
        records_by_arm[arm_name] = records
        print(f"[{time.time()-t0:6.1f}s] ran {arm_name}", file=sys.stderr)

    # ---- P-* (product path) ----
    arms = _build_product_arms(cli, cards, nodes)
    print(f"[{time.time()-t0:6.1f}s] built {len(arms)} product indices", file=sys.stderr)
    abstain_counts: dict = {}
    for arm_name, (index, router, top_n) in arms.items():
        ranked_by_qid, records = {}, []
        n_abstained = 0
        for case in cases:
            rec = run_product_case(router, case, top_n=top_n)
            ranked_by_qid[rec["query_id"]] = rec["ranked"]
            n_abstained += int(rec["abstained"])
            records.append({**rec, "arm": arm_name})
        per_query_by_arm[arm_name] = per_query_metrics(metrics, ranked_by_qid, cases)
        # P-shipped's real select()-injected all_required@4 (abstain included) -- the task's own
        # "confirm all_required@4 by k on dev for P-shipped" number, distinct from the raw-ranked
        # top-4 all_required4 every arm gets in per_query_metrics.
        for case in cases:
            rec = next(r for r in records if r["query_id"] == case["id"])
            per_query_by_arm[arm_name][case["id"]]["all_required4_injected"] = \
                metrics.all_required_at_k(rec["injected"], case, 4)
        abstain_counts[arm_name] = n_abstained
        records_by_arm[arm_name] = records
        print(f"[{time.time()-t0:6.1f}s] ran {arm_name} (abstained={n_abstained})", file=sys.stderr)

    # ---- write per-arm JSONL (gzip) ----
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for arm_name, records in records_by_arm.items():
        fname = f"dev-sparse-{arm_name.lower()}.jsonl.gz"
        write_jsonl_gz(VALIDATION_DIR / fname, records)
        print(f"[{time.time()-t0:6.1f}s] wrote {fname}", file=sys.stderr)

    # ---- per-arm summary tables ----
    summary = {}
    for arm_name, per_q in per_query_by_arm.items():
        summary[arm_name] = arm_summary(metrics, per_q, cases)

    # ---- paired bootstrap CIs: every P-* and R-BM25-simple-tok vs R-BM25, and vs P-shipped ----
    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    breakdowns = {"overall": all_qids, **{f"k={k}": qids for k, qids in sorted(by_k.items())}}

    comparisons = {}
    baselines = ["R-BM25", "P-shipped"]
    challengers = [a for a in per_query_by_arm if a not in ("R-BM25",)]
    for base in baselines:
        for chal in challengers:
            if chal == base:
                continue
            key = f"{chal}_vs_{base}"
            comparisons[key] = {}
            for bd_name, qids in breakdowns.items():
                comparisons[key][bd_name] = {}
                for metric in ("ndcg10", "recall10"):
                    a, b = paired_arrays(per_query_by_arm[base], per_query_by_arm[chal], qids, metric)
                    comparisons[key][bd_name][metric] = bootstrap_paired_delta(a, b)

    out = {
        "corpus_report": corpus_report, "query_report": query_report,
        "n_cases": len(cases), "abstain_counts": abstain_counts,
        "summary": summary, "comparisons": comparisons,
        "runtime_s": time.time() - t0,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {args.out}", file=sys.stderr)

    # ---- console table ----
    cols = ["n", "hit1", "ndcg10", "recall10", "all_required4"]
    head = f"{'arm':<20}{'break':<8}" + "".join(f"{c:>14}" for c in cols)
    print(head)
    print("-" * len(head))
    for arm_name, blocks in summary.items():
        for bd_name in ["overall"] + [f"k={k}" for k in sorted(by_k)]:
            m = blocks[bd_name]
            row = f"{arm_name:<20}{bd_name:<8}"
            for c in cols:
                v = m[c]
                row += f"{v:>14}" if isinstance(v, int) else (
                    f"{'—':>14}" if _isnan(v) else f"{v:>14.4f}")
            print(row)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("convert", help="report corpus/query conversion stats only")
    p_run = sub.add_parser("run", help="run every arm through the product path / reference BM25")
    p_run.add_argument("--out", type=Path, default=VALIDATION_DIR / "dev-sparse-metrics.json")
    args = ap.parse_args(argv)
    if args.cmd == "convert":
        return cmd_convert(args)
    if args.cmd == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
