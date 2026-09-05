#!/usr/bin/env python3
"""tools/eval/skillretbench.py — Guidefold's first bake-off on real, independently labelled skill
data: SkillRetBench (thaki-AI/SkillRetBench, pinned revision 4bdbf59b via tools/eval/corpora.py),
501 skills / 102 categories / 1250 queries, run entirely through the shipped product path
(ADR-0022's five-stage pipeline: admissibility -> candidates -> relevance -> composition ->
sufficiency). This is the first evaluation written under CLAUDE.md's "Evaluation corpora" rule
(2026-09-05): quality claims come only from real labelled corpora through the product path, never
from the 26-skill Meridian fixture (CI dev/regression only) and never from a reimplementation of
the Router.

Reused, never reimplemented:
  * tools/eval/corpora.py       load_skillretbench() / load_skillret() / verify() — the ONLY
                                 place that opens the pinned JSON files.
  * tools/eval/metrics.py       hit_at_1 / recall_at_k / ndcg_at_k / all_required_at_k /
                                 distractor_rate / evaluate / by_category / format_table.
  * skills/guidefold/scripts/guidefold   Index.from_cards, Router (policy_filter -> candidates ->
                                 score -> select(admissible=...)) — the actual product code.
  * tools/bakeoff/corpus.py     SkillRecord (fields_text/concat_text) — reused, not re-shaped,
                                 as the input contract distill.py already expects.
  * tools/bakeoff/distill.py    distill() — the model2vec-style teacher -> int8 word table
                                 pipeline; called only from the `distill` subcommand (GPU venv).

Two arms differ from B1 by a card-level change, not a Router change: B1-closure zeroes every
card's `requires` list before building the Index (Router's dependency-closure walk inside
`select()` is unconditional -- no weight gates it -- so ablating it product-side means ablating
the *input*, not patching the Router).

Subcommands:
  convert   report corpus/query conversion stats only (no Router run)
  run       build all four arms, run every case through the product path, write the per-query
            JSONL and print the per-setting x arm metrics table (stdlib + PyYAML only)
  distill   build the SKILLRET-Embedding-0.6B student word table for this corpus's vocabulary
            (GPU venv only: needs torch/transformers/sentence-transformers, imported lazily here
            so `run`/`convert`/pytest never pay for or require them)
  materialize   write a real <category>/.agents/skills/<skill_id>/SKILL.md monorepo tree, for
            `latency` to time via genuine `guidefold index` / `guidefold hook` subprocesses
  latency   build the E1.4 on-disk artifact for the materialized tree and report warm p50/p95
            for the shipped (B1) config, the same protocol as tools/eval/measure_hook_latency.py
  overlap   SkillRet (training corpus for the B3b teacher) vs SkillRetBench id/name overlap
"""
from __future__ import annotations

import argparse
import array
import gzip
import json
import re
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
BAKEOFF_DIR = REPO_ROOT / "tools" / "bakeoff"
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — the ONLY pinned-corpus loader

PUBLISHER = "srb"
EVAL_K = 10          # >= nDCG@10's k; retrieval lists are sliced from this one ranking per case
K_CARDS = 4           # the hook's real card cap (E1.5) — same constant tools/eval/run_golden.py uses

# SkillRetBench's five query "settings" onto the golden set's category vocabulary
# (tests/golden/README.md / docs/reports/golden/README.md), per the bake-off brief's own mapping.
SETTING_TO_CATEGORY = {
    "single_skill": "simple",
    "multi_skill_composition": "multi_skill",
    "distractor": "sibling_ambiguity",
    "outdated_redundant": "stale_adversarial",
    "budget_constrained": "budget_constrained",   # its own stratum — no golden-set analogue
}

# Hangul syllables (AC00-D7A3), Hangul Jamo (1100-11FF), Compatibility Jamo (3130-318F).
_HANGUL_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")

# Byte-identical to the CLI's own `FM` frontmatter pattern (skills/guidefold/scripts/guidefold),
# reused here (not reimplemented differently) to strip a skill's OWN embedded frontmatter out of
# `full_text` before it becomes card["_body"]. `full_text` is the complete original SKILL.md file,
# frontmatter included (confirmed by inspection of skill_corpus.json); the shipped CLI's own
# Index.build() always sets `_body` to a real file's content AFTER its frontmatter closes (the
# frontmatter block is metadata, consumed separately into name/description/triggers/etc, never
# re-tokenized as body text). Leaving it in would double-count every skill's own name/description/
# metadata-field words in the BM25 "body" field (weight 2) on top of their dedicated fields
# (name weight 6, description weight 4, triggers weight 5) -- a self-inflicted, uniform-but-real
# scoring bias that has nothing to do with router quality, and would also leave a materialized
# SKILL.md with a nested, non-representative second frontmatter block sitting inside its body.
_OWN_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.S)


def strip_own_frontmatter(full_text: str) -> str:
    return _OWN_FRONTMATTER_RE.sub("", full_text, count=1).lstrip("\n")


def has_hangul(text: str) -> bool:
    return bool(_HANGUL_RE.search(text or ""))


# ------------------------------------------------------------------------- module loaders
def _load_cli():
    """Same pattern as tools/eval/run_golden.py: the CLI has no .py suffix (it ships as a
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


# ------------------------------------------------------------------------- Deliverable 1: corpus -> cards
def corpus_to_cards(skills: list) -> tuple:
    """SkillRetBench skill dict -> Guidefold card dict, per the bake-off brief's mapping.

      skill_id            -> urn's last segment: urn:skill:srb:<category>:<skill_id>
                              (also card["name"] — Index.build's own invariant is
                              urn == urn(cfg, node, card["name"]), preserved here by construction)
      category              -> node (one node per category; `_root` is the implicit ancestor —
                              a `nodes` map entry `{category}/** ` is built for every category)
      description            -> card["description"]
      full_text               -> card["_body"], with the skill's OWN embedded frontmatter block
                              stripped first (`strip_own_frontmatter`, same pattern as the CLI's
                              own `FM` regex) -- full_text is a complete original SKILL.md file,
                              frontmatter included; the shipped product's Index.build() only ever
                              tokenizes a real skill's body AFTER its frontmatter closes, so
                              leaving it in would double-count name/description/metadata words in
                              the BM25 body field on top of their own dedicated fields.
                              (interpretive: two source fields map onto two distinct card fields,
                              not the same field twice — see the report)
      trigger_phrases          -> card["triggers"]
      anti_triggers            -> card["negative_triggers"]
      composable_skills         -> card["requires"], URN-resolved, ONLY for ids that exist in
                              this corpus; dangling references are counted and returned in
                              `report`, never silently dropped without a trace. (This corpus
                              revision has zero: see the report/test.)
      (no digest field exists) -> card["digest"] falls back to description[:200], identical to
                              Index.build's own fallback when a real SKILL.md carries no
                              `metadata.digest` — not an invented convention.
      status                  -> "active" for every skill. SkillRetBench's outdated_redundant
                              setting DOES populate `outdated_skill_id` on all 150 of its queries
                              (checked exhaustively, corpus revision 4bdbf59b) — but every single
                              value is the synthetic marker "<gold_skill_id>__v1_deprecated",
                              which resolves to zero real entries in this corpus's own `skills`
                              list (also checked exhaustively: 0/150). There is no actual
                              successor skill in this corpus for `replaced_by` to point to, and
                              `distractor_skills` is separately empty on those same 150 queries —
                              so nothing in this corpus revision identifies which OTHER real skill,
                              if any, replaces the deprecated one. Marking every card "active" is
                              therefore still the only defensible mapping, for a narrower reason
                              than "the field is unpopulated": the field IS populated, but always
                              as a dangling reference to a skill version that was never a corpus
                              entry. Flagged in the report/tests as a clean non-mapping, not
                              silently defaulted.
      korean_triggers          -> NOT folded into triggers. The shared tokenizer (both
                              tools/bakeoff/tokenizer.py and the CLI's own tokenize()) folds only
                              Latin diacritics and drops every other script outright, so a
                              Hangul-only phrase tokenizes to nothing and could never match a
                              query term; folding it in would be a silent no-op, not a real
                              language feature. Counted, not silently discarded (see `report`).

    Returns (cards, nodes, report).
    """
    ids = {s["skill_id"] for s in skills}
    id_to_category = {s["skill_id"]: s["category"] for s in skills}
    categories = sorted({s["category"] for s in skills})
    nodes = {"_root": {"paths": ["_root/**"], "owner": PUBLISHER}}
    for cat in categories:
        nodes[cat] = {"paths": [f"{cat}/**"], "owner": PUBLISHER}

    def mk_urn(skill_id: str) -> str:
        return f"urn:skill:{PUBLISHER}:{id_to_category[skill_id]}:{skill_id}"

    cards = {}
    dangling_requires = []
    n_korean_trigger_phrases = 0
    for s in skills:
        skill_id = s["skill_id"]
        u = mk_urn(skill_id)
        requires = []
        for dep in s.get("composable_skills") or []:
            if dep in ids:
                requires.append(mk_urn(dep))
            else:
                dangling_requires.append((skill_id, dep))
        n_korean_trigger_phrases += len(s.get("korean_triggers") or [])
        description = str(s.get("description", ""))
        cards[u] = {
            "urn": u, "node": s["category"], "name": skill_id,
            "description": description,
            "digest": description[:200],
            "triggers": list(s.get("trigger_phrases") or []),
            "negative_triggers": list(s.get("anti_triggers") or []),
            "requires": requires,
            "refines": [],
            "status": "active",
            "replaced_by": None,
            "kind": None, "layer": None, "owner": PUBLISHER,
            "_body": strip_own_frontmatter(str(s.get("full_text", ""))),
        }
    report = {
        "n_skills": len(skills),
        "n_categories": len(categories),
        "dangling_requires": dangling_requires,
        "total_composable_edges": sum(len(s.get("composable_skills") or []) for s in skills),
        "n_korean_trigger_phrases_dropped": n_korean_trigger_phrases,
    }
    return cards, nodes, report


# ------------------------------------------------------------------------- Deliverable 1: queries -> cases
def queries_to_cases(queries: list, cards: dict) -> tuple:
    """SkillRetBench query dict -> a golden-schema case dict (tests/golden/*.yaml shape, plus
    bookkeeping this runner needs).

      gold_skills[0]    -> relevant, grade 3 (must be rank 1)
      gold_skills[1:]   -> relevant, grade 2 (required companions) — multi_skill_composition is
                          SkillRetBench's own setting for "these skills are jointly required";
                          treating every non-primary gold id as a grade-2 companion is the
                          dataset's own definition of the setting, not an invented grading.
      distractor_skills  -> distractors (plausible wrong answers; scored on distractor_rate@4,
                          never folded into recall/nDCG — same convention as the golden set).

    `node`: SkillRetBench queries carry no cwd/location, so each case gets TWO node candidates:

      node_scoped  gold_skills[0]'s category — what a harness would resolve `cwd` to if this
                   corpus were a real monorepo and the caller sat inside that category's tree.
      node_root    "_root" — no scope signal at all: policy_filter's visible-node set becomes
                   every node in the corpus, and the scope ranking feature (w_scope) degenerates
                   to a constant offset that cannot affect relative order (every category is
                   exactly one hop from _root). This isolates the *visibility* effect of scope
                   from the *ranking* effect the B1-scope arm ablates separately.

    INTERPRETIVE DECISION: the brief names "the single_skill/multi settings" for node_scoped: this
    runner applies node_scoped to every setting, not only those two, and reports the full
    node_root run across every setting too. Restricting scope to only two settings would make the
    `distractor` setting's cross-category-visibility design (the whole point of mapping it to
    sibling_ambiguity) untestable, and there is no principled reason budget_constrained/
    outdated_redundant should be treated differently. Reported here, not silently assumed.

    Returns (cases, report). A query with an empty gold_skills list is dropped (SkillRetBench,
    unlike the golden set, has no no_applicable/abstention stratum — none exist in this corpus).
    """
    id_to_urn = {c["name"]: u for u, c in cards.items()}   # card["name"] == skill_id by construction
    cases = []
    missing_gold_urn = []
    missing_distractor_urn = []
    dropped_empty_gold = 0
    for q in queries:
        gold = q.get("gold_skills") or []
        if not gold:
            dropped_empty_gold += 1
            continue
        relevant = []
        for i, g in enumerate(gold):
            u = id_to_urn.get(g)
            if u is None:
                missing_gold_urn.append((q["query_id"], g))
                continue
            relevant.append({"urn": u, "grade": 3 if i == 0 else 2})
        if not relevant:
            dropped_empty_gold += 1
            continue
        distractors = []
        for d in q.get("distractor_skills") or []:
            u = id_to_urn.get(d)
            if u is None:
                missing_distractor_urn.append((q["query_id"], d))
                continue
            distractors.append({"urn": u, "why": "distractor_skills"})
        node_scoped = cards[relevant[0]["urn"]]["node"]
        cases.append({
            "id": q["query_id"], "query": q["query"],
            "setting": q["setting"], "category": SETTING_TO_CATEGORY[q["setting"]],
            "node_scoped": node_scoped, "node_root": "_root",
            "relevant": relevant, "distractors": distractors,
            "has_hangul": has_hangul(q["query"]),
            "notes": {"difficulty": q.get("difficulty"), "source": q.get("source"),
                      "budget_tokens": q.get("budget_tokens")},
        })
    report = {
        "n_queries": len(queries), "n_cases": len(cases),
        "dropped_empty_gold": dropped_empty_gold,
        "missing_gold_urn": missing_gold_urn, "missing_distractor_urn": missing_distractor_urn,
        "n_hangul": sum(1 for c in cases if c["has_hangul"]),
        "n_hangul_by_setting": {
            setting: sum(1 for c in cases if c["has_hangul"] and c["setting"] == setting)
            for setting in SETTING_TO_CATEGORY
        },
    }
    return cases, report


# ------------------------------------------------------------------------- word table (dense arm)
# Reads tools/bakeoff/distill.py's words.bin format WITHOUT importing distill.py/encode.py (which
# transitively import torch/transformers/sentence-transformers at module load time — tier-2-only
# dependencies this eval/report path must never require: `run`/`convert` must stay runnable under
# plain python3, no GPU venv, exactly like tools/eval/metrics.py and run_golden.py already are).
# Byte layout verbatim from distill.py:write_words_bin / read_words_bin: header
# struct.pack("<4sHHIfI", MAGIC, version, dims, vocab_size, scale, blob_len), then the newline-
# joined UTF-8 word list (blob_len bytes), then vocab_size * dims signed int8 bytes. The CLI's own
# on-disk artifact loader decodes int8 rows the same stdlib way (`array.array('b', ...)`, see
# skills/guidefold/scripts/guidefold's _LazyVectors).
_WORDS_MAGIC = b"GFW1"


def read_word_table(path: Path) -> dict:
    """words.bin -> {word: tuple[int, ...]}, directly usable as Index.from_cards(word_vectors=...)."""
    data = path.read_bytes()
    magic, version, dims, vocab_size, scale, blob_len = struct.unpack_from("<4sHHIfI", data, 0)
    if magic != _WORDS_MAGIC:
        raise ValueError(f"bad magic in {path}: {magic!r}")
    offset = struct.calcsize("<4sHHIfI")
    words = data[offset:offset + blob_len].decode("utf-8").split("\n")
    offset += blob_len
    table = {}
    for i, w in enumerate(words):
        row = data[offset + i * dims: offset + (i + 1) * dims]
        table[w] = tuple(array.array("b", row))
    return table


# ------------------------------------------------------------------------- Deliverable 2: arms
def build_arms(cli, cards: dict, nodes: dict, word_vectors: dict = None) -> dict:
    """Four arms, each differing from B1 by exactly ONE parameter (see
    tests/test_skillretbench.py::test_arms_differ_by_exactly_one_parameter_from_b1):

      B1          Index.from_cards(cards, nodes, word_vectors=word_vectors)  -- shipped defaults
                  (BM25F, w_dense=0, hard requires-closure inside select()). The SAME
                  `word_vectors` table is passed here too: with w_dense=0 the dense channel never
                  runs (Router.candidates()/`_dense_scores` both gate on weights["w_dense"] > 0,
                  ADR-0022 finding 3), so an inert word table changes nothing about B1's behaviour
                  -- this is what makes the dense arm's diff exactly one parameter (w_dense),
                  not two (w_dense AND the table's mere presence).
      B1-scope    weights={"w_scope": 0}                     -- one weight changed
      B1-closure  every card's requires=[] before from_cards  -- one input changed, no weight
                  touched (Router's `_requires_closure` walk inside select() is unconditional;
                  there is no weight to gate it on the Router side)
      B3b+B5      weights={"w_dense": 1}                     -- one weight changed (w_dense is a
                  pure ON/OFF gate everywhere it is read, never a fusion magnitude -- confirmed by
                  grep across the whole CLI; any positive value is equivalent). Word vectors come
                  from `SKILLRET-Embedding-0.6B`, distilled by `distill` subcommand.
    """
    wv = word_vectors or {}
    b1_idx = cli.Index.from_cards(cards, nodes, word_vectors=wv)
    noscope_idx = cli.Index.from_cards(cards, nodes, weights={"w_scope": 0}, word_vectors=wv)
    cards_no_requires = {u: {**c, "requires": []} for u, c in cards.items()}
    noclosure_idx = cli.Index.from_cards(cards_no_requires, nodes, word_vectors=wv)
    dense_idx = cli.Index.from_cards(cards, nodes, weights={"w_dense": 1}, word_vectors=wv)
    return {
        "B1": cli.Router(b1_idx),
        "B1-scope": cli.Router(noscope_idx),
        "B1-closure": cli.Router(noclosure_idx),
        "B3b+B5": cli.Router(dense_idx),
    }


# ------------------------------------------------------------------------- product-path runner
def run_case(router, case: dict, node_key: str, k: int = EVAL_K) -> dict:
    """One case through policy_filter -> candidates -> score -> select — the exact product
    pipeline, never a reimplementation. `admissible` is computed once and governs both candidate
    visibility and the (unconditional) requires-closure walk inside select(), per ADR-0022."""
    node = case[node_key]
    query = case["query"]
    admissible, drops = router.policy_filter(node, query)
    admissible_set = set(admissible)
    cands = router.candidates(query, node)
    scored = router.score(cands, query, node)
    injected = router.select(scored, k=K_CARDS, admissible=admissible_set)
    drop_reasons: dict = {}
    for _, reason in drops:
        key = reason.split(":", 1)[0]
        drop_reasons[key] = drop_reasons.get(key, 0) + 1
    return {
        "query_id": case["id"], "setting": case["setting"], "node": node,
        "retrieval": [{"urn": s["urn"], "score": s["score"]} for s in scored[:k]],
        "injection": [r["urn"] for r in injected],
        "admissible_size": len(admissible_set),
        "drops": drop_reasons,
    }


def run_arm(router, cases: list, node_key: str, k: int = EVAL_K) -> tuple:
    """Returns (retrieval_results, injection_results, records) — the same
    (ranked_urns, case) pairs tools/eval/metrics.py's evaluate()/by_category() consume, plus the
    per-query bookkeeping records for the committed JSONL."""
    retrieval, injection, records = [], [], []
    for case in cases:
        rec = run_case(router, case, node_key, k=k)
        retrieval.append(([e["urn"] for e in rec["retrieval"]], case))
        injection.append((rec["injection"], case))
        records.append(rec)
    return retrieval, injection, records


# ------------------------------------------------------------------------- baseline-aligned IR metrics
def _mean(xs) -> float:
    vals = [x for x in xs if not (isinstance(x, float) and x != x)]  # drop NaN
    return sum(vals) / len(vals) if vals else float("nan")


def _binary_case(case: dict) -> dict:
    """A view of `case` with every relevant urn forced to grade 2 (uniform "required"), so
    tools/eval/metrics.py's own recall_at_k/ndcg_at_k compute the dataset's binary-relevance
    Recall@k / nDCG@k exactly (nDCG's exponential gain 2**g-1 is a positive constant factor for
    any single uniform grade g>0, so it cancels in the DCG/IDCG ratio; recall_at_k's >= grade-2
    threshold already becomes "every gold item" once every grade is 2). This reuses the existing
    pure functions instead of a second nDCG/recall implementation."""
    return {**case, "relevant": [{"urn": r["urn"], "grade": 2} for r in case.get("relevant") or []]}


def reciprocal_rank(ranked, case: dict) -> float:
    rel = {r["urn"] for r in case.get("relevant") or []}
    if not rel:
        return float("nan")
    for i, u in enumerate(ranked):
        if u in rel:
            return 1.0 / (i + 1)
    return 0.0


def average_precision(ranked, case: dict, k: int = 10) -> float:
    """Standard AP over the top k: mean precision at each rank a relevant item appears,
    normalised by the TOTAL number of relevant items (not capped at k) — matches BM25/single_skill's
    published mrr == map (a single gold item makes AP and RR the same number by construction)."""
    rel = {r["urn"] for r in case.get("relevant") or []}
    if not rel:
        return float("nan")
    hits, total = 0, 0.0
    for i, u in enumerate(ranked[:k]):
        if u in rel:
            hits += 1
            total += hits / (i + 1)
    return total / len(rel)


def ir_alignment_metrics(retrieval_results, metrics_mod, ks=(1, 3, 5, 10)) -> dict:
    """Recall@k / nDCG@k / MRR / MAP over `(ranked_urns, case)` pairs, comparable to
    baseline_results.json's own per-setting table. Differs from that table in protocol, stated
    once here rather than per-number: our rankings come from `router.candidates()` already
    filtered by `policy_filter` (admissibility/scope/negative-triggers), never the raw 501-skill
    pool; the dataset's own BM25/Dense/Hybrid baselines rank the unfiltered corpus. MAP divides by
    the total relevant count (not capped at k) — the exact convention is not published alongside
    baseline_results.json, so an exact match to their numbers is not guaranteed even when our
    ranking agrees with theirs skill-for-skill; the formula is stated here so a reviewer can
    check it by hand."""
    out = {}
    for k in ks:
        out[f"recall@{k}"] = _mean(
            metrics_mod.recall_at_k(r, _binary_case(c), k) for r, c in retrieval_results)
        out[f"ndcg@{k}"] = _mean(
            metrics_mod.ndcg_at_k(r, _binary_case(c), k) for r, c in retrieval_results)
    out["mrr"] = _mean(reciprocal_rank(r, c) for r, c in retrieval_results)
    out["map"] = _mean(average_precision(r, c, k=10) for r, c in retrieval_results)
    out["n"] = len(retrieval_results)
    return out


# ------------------------------------------------------------------------- dense reference-run reporting (R1)
# DENSE-PROGRAM.md v2 (docs/reports/bakeoff/DENSE-PROGRAM.md, PRs #26-28, landed on main after this
# branch rebased) reframes the B3b+B5 arm: it is a PRE-REGISTERED REFERENCE RUN (SS6: "R1 ...
# unfused config chosen from tooling defaults, latency ignored"), never a stop test and never
# tuned on this corpus. SkillRetBench is test-B (SS3): a result here never chooses a
# configuration -- w_dense=1 was set from the CLI's own DEFAULT_WEIGHTS ON/OFF-gate guidance
# before this script ever saw a SkillRetBench number, and that timing is stated in the report.
# SS6 names ONE number as the most useful thing a reference run produces: coverage -- gold skills
# BM25F's top-50 missed that the encoder's real candidate pool contains. SS5 additionally requires
# a paired bootstrap (1,000 resamples over queries) 95% CI on the delta vs B1 for `all_required@4`
# and `hit@1`, so this reference run can be read against the eventual adoption gates even though
# SS6 states plainly it gates nothing -- adoption is decided only for the dev-tuned frozen variant,
# run once per family on both test corpora.

def _bootstrap_paired_delta(vals_a: list, vals_b: list, n_resamples: int = 1000, seed: int = 0) -> dict:
    """95% CI (percentile method) on mean(vals_b) - mean(vals_a), resampling QUERY INDICES with
    replacement together for both arms -- a *paired* bootstrap: the same resampled query set
    scores both systems in each replicate, so per-query noise cancels rather than compounds
    (standard practice for comparing two rankers on the same query set). `seed` is fixed so the
    report's numbers are exactly reproducible on re-run. Per DENSE-PROGRAM.md SS5: 1,000 resamples."""
    import random
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


def dense_coverage_report(dense_router, cases: list, node_key: str = "node_scoped",
                           bm25_cutoff: int = 50) -> dict:
    """DENSE-PROGRAM.md SS4/SS6's coverage number: "gold skills added to the candidate pool that
    BM25F's top-50 missed". Uses `Router.candidates()` exactly as run_case calls it for the dense
    arm (default top_n=50, the product's own cutoff) -- never a parallel computation. bm25_rank
    and dense_rank in the returned dicts are TRUE (unbounded) ranks even for a candidate that only
    entered the pool via the OTHER channel (candidates()'s bm25_rank/dense_rank dicts are built
    from the full bm25/dense score maps before the top_n slice -- see
    skills/guidefold/scripts/guidefold's Router.candidates()), so this reads real product state,
    not an approximation of it.

      missed_by_bm25    gold urn is absent from candidates() entirely, or present with
                         bm25_rank is None or > bm25_cutoff.
      recovered         missed_by_bm25 AND present with dense_rank <= bm25_cutoff -- i.e. the
                         ONLY reason this skill is in the real candidate pool is the encoder.
    """
    per_setting: dict = {}
    for setting in SETTING_TO_CATEGORY:
        missed = recovered = 0
        for case in cases:
            if case["setting"] != setting:
                continue
            cands = dense_router.candidates(case["query"], case[node_key])
            by_urn = {c["urn"]: c for c in cands}
            for r in case["relevant"]:
                entry = by_urn.get(r["urn"])
                bm25_rank = entry["bm25_rank"] if entry else None
                if bm25_rank is None or bm25_rank > bm25_cutoff:
                    missed += 1
                    dense_rank = entry["dense_rank"] if entry else None
                    if dense_rank is not None and dense_rank <= bm25_cutoff:
                        recovered += 1
        per_setting[setting] = {
            "n_gold_missed_by_bm25_top50": missed,
            "n_recovered_by_encoder": recovered,
            "coverage": (recovered / missed) if missed else float("nan"),
        }
    tm = sum(v["n_gold_missed_by_bm25_top50"] for v in per_setting.values())
    tr = sum(v["n_recovered_by_encoder"] for v in per_setting.values())
    per_setting["OVERALL"] = {
        "n_gold_missed_by_bm25_top50": tm, "n_recovered_by_encoder": tr,
        "coverage": (tr / tm) if tm else float("nan"),
    }
    return per_setting


def format_coverage_table(coverage: dict) -> str:
    lines = ["\n=== B3b+B5 dense coverage of B1/BM25F's top-50 misses (DENSE-PROGRAM.md SS6) ==="]
    head = f"{'setting':<24}{'missed_by_bm25':>16}{'recovered':>12}{'coverage':>12}"
    lines.append(head); lines.append("-" * len(head))
    for setting, v in coverage.items():
        cov = v["coverage"]
        cov_s = "—" if cov != cov else f"{cov:.4f}"
        lines.append(f"{setting:<24}{v['n_gold_missed_by_bm25_top50']:>16}"
                      f"{v['n_recovered_by_encoder']:>12}{cov_s:>12}")
    return "\n".join(lines)


def dense_vs_b1_gate_report(metrics_mod, cases: list,
                             retrieval_b1: list, injection_b1: list,
                             retrieval_dense: list, injection_dense: list,
                             k_cards: int = K_CARDS, n_resamples: int = 1000) -> dict:
    """Per-setting delta (B3b+B5 - B1) + gate status against DENSE-PROGRAM.md SS5's rules. R1 is a
    REFERENCE run -- SS6 states explicitly it gates nothing -- so `gate_*` fields here answer
    "would this reference run have cleared the rule", never "is dense adopted"; adoption is a
    decision for the eventual dev-tuned frozen variant, on both test corpora, not for this run.

    `all_required@4` and `hit@1` get the paired bootstrap (1,000 resamples over queries) SS5
    requires; `ndcg@10` and `distractor_rate@4` (named HSR@4 for SkillRetBench in SS5 -- computed
    by the exact same tools/eval/metrics.py::distractor_rate() function, not a second metric) get
    a point-estimate delta only, matching what was actually requested. "answered" pairing (both
    arms must have produced a non-empty ranking/injection for a query to count) matches
    tools/eval/metrics.py::evaluate()'s own "answered" population convention."""
    out: dict = {}
    for setting in list(SETTING_TO_CATEGORY) + ["OVERALL"]:
        idx = [i for i, (_, c) in enumerate(retrieval_b1)
               if setting == "OVERALL" or c["setting"] == setting]
        hit_idx = [i for i in idx if retrieval_b1[i][0] and retrieval_dense[i][0]]
        req_idx = [i for i in idx if injection_b1[i][0] and injection_dense[i][0]]

        hit_a = [metrics_mod.hit_at_1(retrieval_b1[i][0], retrieval_b1[i][1]) for i in hit_idx]
        hit_b = [metrics_mod.hit_at_1(retrieval_dense[i][0], retrieval_dense[i][1]) for i in hit_idx]
        req_a = [metrics_mod.all_required_at_k(injection_b1[i][0], injection_b1[i][1], k_cards) for i in req_idx]
        req_b = [metrics_mod.all_required_at_k(injection_dense[i][0], injection_dense[i][1], k_cards) for i in req_idx]

        hit_boot = _bootstrap_paired_delta(hit_a, hit_b, n_resamples=n_resamples, seed=1)
        req_boot = _bootstrap_paired_delta(req_a, req_b, n_resamples=n_resamples, seed=2)

        ndcg_a = _mean(metrics_mod.ndcg_at_k(retrieval_b1[i][0], retrieval_b1[i][1], 10) for i in idx)
        ndcg_b = _mean(metrics_mod.ndcg_at_k(retrieval_dense[i][0], retrieval_dense[i][1], 10) for i in idx)
        hsr_a = _mean(metrics_mod.distractor_rate(injection_b1[i][0], injection_b1[i][1], k_cards) for i in idx)
        hsr_b = _mean(metrics_mod.distractor_rate(injection_dense[i][0], injection_dense[i][1], k_cards) for i in idx)

        # None means "undetermined" (the underlying delta is NaN -- e.g. HSR@4 has no labelled
        # distractors in this setting), which is NOT the same as "fail" and must be rendered
        # differently (format_gate_table below prints "n/a", never "fail", for None).
        bundle_gate = (req_boot["ci_lo"] > 0.02) if req_boot["ci_lo"] == req_boot["ci_lo"] else None
        hit_gate = (hit_boot["delta"] >= -0.01) if hit_boot["delta"] == hit_boot["delta"] else None
        ndcg_gate = ((ndcg_b - ndcg_a) >= -0.01) if (ndcg_a == ndcg_a and ndcg_b == ndcg_b) else None
        hsr_gate = ((hsr_b - hsr_a) <= 0.01) if (hsr_a == hsr_a and hsr_b == hsr_b) else None

        out[setting] = {
            "all_required@4": {**req_boot, "gate_bundle_completeness": bundle_gate},
            "hit@1": {**hit_boot, "gate_primary_quality": hit_gate},
            "ndcg@10": {"b1": ndcg_a, "dense": ndcg_b, "delta": ndcg_b - ndcg_a,
                        "gate_primary_quality": ndcg_gate},
            "HSR@4": {"b1": hsr_a, "dense": hsr_b, "delta": hsr_b - hsr_a,
                      "gate_harmful_exposure": hsr_gate,
                      "note": "computed via metrics.py's distractor_rate(); named HSR@4 for "
                              "SkillRetBench per DENSE-PROGRAM.md SS5, not a second metric"},
        }
    return out


def format_gate_table(gates: dict) -> str:
    def _f(v):
        return "—" if v != v else f"{v:+.4f}"

    def _g(v):
        # v is True / False / None ("undetermined": the underlying delta is NaN, e.g. HSR@4 has
        # no labelled distractors in this setting) -- None must never render as "fail".
        return "n/a" if v is None else ("PASS" if v else "fail")

    lines = ["\n=== B3b+B5 vs B1 -- DENSE-PROGRAM.md SS5 gate rules ===",
              "    (REFERENCE RUN R1: gates nothing per SS6; adoption is decided only for the",
              "     eventual dev-tuned frozen variant, run once per family on both test corpora)"]
    head = (f"{'setting':<24}{'all_req D':>11}{'[95% CI]':>18}{'gate':>6}"
            f"{'hit@1 D':>10}{'gate':>6}{'ndcg@10 D':>11}{'gate':>6}{'HSR@4 D':>10}{'gate':>6}")
    lines.append(head); lines.append("-" * len(head))
    for setting, g in gates.items():
        req, hit, ndcg, hsr = g["all_required@4"], g["hit@1"], g["ndcg@10"], g["HSR@4"]
        ci = f"[{_f(req['ci_lo'])},{_f(req['ci_hi'])}]"
        row = (f"{setting:<24}{_f(req['delta']):>11}{ci:>18}"
               f"{_g(req['gate_bundle_completeness']):>6}"
               f"{_f(hit['delta']):>10}{_g(hit['gate_primary_quality']):>6}"
               f"{_f(ndcg['delta']):>11}{_g(ndcg['gate_primary_quality']):>6}"
               f"{_f(hsr['delta']):>10}{_g(hsr['gate_harmful_exposure']):>6}")
        lines.append(row)
    return "\n".join(lines)


# ------------------------------------------------------------------------- overlap: SkillRet vs SkillRetBench
def overlap_report() -> dict:
    """Quantifies the caveat the brief requires for the B3b arm: SKILLRET-Embedding-0.6B was
    fine-tuned on SkillRet (a different, larger, public-GitHub-scrape dataset from the same org),
    not on SkillRetBench itself -- but if the two datasets share skills, the teacher may have seen
    (a close paraphrase of) an eval skill during its own fine-tuning, which would make any B3b
    coverage gain look better than it would on a truly unseen corpus."""
    needs = gf_corpora.verify("skillret") + gf_corpora.verify("skillretbench")
    if needs:
        return {"skipped": True, "reason": needs[0]}
    skillret = gf_corpora.load_skillret()
    srb = gf_corpora.load_skillretbench()
    ret_ids = {s["id"] for s in skillret["skills"]}
    ret_names = {str(s.get("name", "")).strip().lower() for s in skillret["skills"] if s.get("name")}
    srb_ids = {s["skill_id"] for s in srb["corpus"]["skills"]}
    srb_names = {str(s.get("skill_name", "")).strip().lower() for s in srb["corpus"]["skills"] if s.get("skill_name")}
    id_overlap = sorted(ret_ids & srb_ids)
    name_overlap = sorted(ret_names & srb_names)
    return {
        "skipped": False,
        "skillret_skills": len(skillret["skills"]), "skillretbench_skills": len(srb["corpus"]["skills"]),
        "id_overlap_count": len(id_overlap), "id_overlap_sample": id_overlap[:10],
        "name_overlap_count": len(name_overlap), "name_overlap_sample": name_overlap[:10],
    }


# ------------------------------------------------------------------------- distillation (GPU venv only)
def distill_word_table(cards: dict, out_dir: Path,
                        teacher_id: str = "ThakiCloud/SKILLRET-Embedding-0.6B",
                        teacher_revision: str = "0e10886e80a0aacc9efddc28282a258e2ab7eae1",
                        dims: int = 256) -> dict:
    """Distils the SKILLRET-Embedding-0.6B teacher into a tier-1 int8 word table over THIS
    corpus's vocabulary, using tools/bakeoff/distill.py verbatim (never reimplemented). Imports
    distill.py (and transitively encode.py -> torch/sentence-transformers) lazily, INSIDE this
    function, specifically so importing this module (skillretbench.py) never requires a GPU venv:
    `run`/`convert`/pytest must stay on stdlib + PyYAML alone. Run this function only under
    /home/mike/.cache/guidefold/gpu-venv/bin/python, with HF_HUB_OFFLINE=1 set (the model is
    already pinned on disk under GUIDEFOLD_MODELS_ROOT; nothing here re-downloads it)."""
    sys.path.insert(0, str(BAKEOFF_DIR))
    import distill as gf_distill          # noqa: E402  (torch/transformers only from here on)
    from corpus import SkillRecord        # noqa: E402  tools/bakeoff/corpus.py's own dataclass

    records = [
        SkillRecord(
            urn=u, node=c["node"], name=c["name"], description=c["description"],
            digest=c["digest"], triggers=tuple(c["triggers"]), body=c["_body"],
            status=c["status"], requires=tuple(c["requires"]), replaced_by=c["replaced_by"],
        )
        for u, c in sorted(cards.items())
    ]
    return gf_distill.distill(records, teacher_id, teacher_revision, out_dir,
                               dims=dims, license_str="apache-2.0", write_teacher=False)


# ------------------------------------------------------------------------- latency (materialized tree)
def materialize_monorepo(cards: dict, nodes: dict, out_root: Path) -> None:
    """Writes a real <category>/.agents/skills/<skill_id>/SKILL.md tree + guidefold.yaml, so
    `latency` can measure genuine `guidefold index` / `guidefold hook` subprocesses (never an
    in-process Index.from_cards) against this corpus's real scale (501 skills, ~500-4000 tokens of
    body text each). Frontmatter uses YAML LISTS for triggers/negative_triggers/requires (not the
    comma-joined phrase strings production skills use) -- 52 of this corpus's own trigger/
    anti-trigger phrases contain a literal comma, which `md_phrases()`'s comma-split would
    mis-parse; the CLI's frontmatter reader accepts a list for exactly this reason, so this is a
    format the CLI already documents as first-class, not a deviation invented for this fixture."""
    import yaml

    out_root.mkdir(parents=True, exist_ok=True)
    cfg = {
        "publisher": PUBLISHER,
        "nodes": {n: {"paths": spec["paths"], "owner": spec["owner"]}
                  for n, spec in nodes.items() if n != "_root"},
    }
    (out_root / "guidefold.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    for u, c in cards.items():
        skill_dir = out_root / c["node"] / ".agents" / "skills" / c["name"]
        skill_dir.mkdir(parents=True, exist_ok=True)
        fm = {
            "name": c["name"],
            "description": c["description"],
            "metadata": {
                "triggers": list(c["triggers"]),
                "negative_triggers": list(c["negative_triggers"]),
                "requires": list(c["requires"]),
                "status": c["status"],
            },
        }
        front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        (skill_dir / "SKILL.md").write_text(f"---\n{front}---\n\n{c['_body']}\n")


def _machine_spec() -> str:
    import os
    uname = os.uname()
    cpu = "unknown CPU"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    glibc = "unknown glibc"
    try:
        out = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        glibc = out.stdout.splitlines()[0].strip()
    except Exception:
        pass
    return (f"{uname.sysname} {uname.release} ({uname.machine}), {cpu}, "
            f"{os.cpu_count()} threads, {glibc}, CPython {sys.version.split()[0]}")


def _percentile(sorted_vals: list, pct: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = max(0, min(len(sorted_vals) - 1, int(round(pct / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def measure_latency(monorepo_root: Path, cases: list, n_queries: int = 220) -> dict:
    """Same protocol as tools/eval/measure_hook_latency.py: build the E1.4 artifact via a real
    `guidefold index` subprocess into a scratch cache, then time one `guidefold hook` subprocess
    per query (one warm-up excluded), p50/p95 via nearest-rank percentile. Only the shipped (B1)
    config is measurable this way: `write_index_artifact` hardcodes
    `Index.build(root, cfg, word_vectors=None)` (skills/guidefold/scripts/guidefold), so the E1.4
    on-disk artifact format has no wiring today (no CLI flag) to inject a distilled word table --
    the dense arm's real hook-subprocess latency is a stated limitation, not a measured number."""
    import os
    with tempfile.TemporaryDirectory(prefix="skillretbench-latency-") as tmp:
        cache_dir = Path(tmp) / ".cache-guidefold"
        env = {**os.environ, "GUIDEFOLD_CACHE": str(cache_dir)}
        build = subprocess.run([sys.executable, str(CLI_PATH), "index"], cwd=str(monorepo_root),
                                capture_output=True, text=True, env=env)
        if build.returncode != 0:
            return {"error": build.stderr}

        sample = cases[:n_queries] if n_queries else cases

        def _run_hook(cwd: Path, prompt: str) -> float:
            payload = json.dumps({"cwd": str(cwd), "prompt": prompt})
            t0 = time.perf_counter()
            result = subprocess.run([sys.executable, str(CLI_PATH), "hook"], cwd=str(cwd),
                                     input=payload, capture_output=True, text=True, env=env)
            elapsed = time.perf_counter() - t0
            if result.returncode != 0:
                raise RuntimeError(f"hook exited {result.returncode}: {result.stderr}")
            return elapsed

        first = sample[0]
        _run_hook(monorepo_root / first["node_scoped"], first["query"])   # warm the page cache

        durations = [_run_hook(monorepo_root / c["node_scoped"], c["query"]) for c in sample]
        durations_sorted = sorted(durations)
        return {
            "n": len(durations),
            "p50_ms": _percentile(durations_sorted, 50) * 1000,
            "p95_ms": _percentile(durations_sorted, 95) * 1000,
            "mean_ms": statistics.fmean(durations) * 1000,
            "min_ms": min(durations) * 1000, "max_ms": max(durations) * 1000,
            "machine": _machine_spec(),
        }


# ------------------------------------------------------------------------- report table
def format_setting_arm_table(all_metrics: dict) -> str:
    """all_metrics: {arm_name: {setting: metrics_dict}}. Product-path columns from
    tools/eval/metrics.py's own evaluate(): hit@1, ndcg@10 (that module always computes nDCG at
    k=10 regardless of the key name), recall@8 (metrics.py hardcodes k=8 -- the golden set's own
    convention, reused verbatim rather than re-parametrised), all_required@4, distractor_rate@4.
    Baseline-comparable recall@10/ndcg@10/mrr/map live in `format_ir_alignment_table` instead,
    because those need the different (uncapped-at-8, per-k) definitions in `ir_alignment_metrics`."""
    cols = ["n", "hit@1", "ndcg@10", "recall@8", f"all_required@{K_CARDS}", f"distractor_rate@{K_CARDS}"]
    lines = []
    for arm, per_setting in all_metrics.items():
        lines.append(f"\n=== {arm} ===")
        head = f"{'setting':<24}" + "".join(f"{c:>18}" for c in cols)
        lines.append(head)
        lines.append("-" * len(head))
        for setting, m in per_setting.items():
            row = f"{setting:<24}"
            for c in cols:
                v = m.get(c, float("nan"))
                if isinstance(v, int):
                    row += f"{v:>18}"
                elif isinstance(v, float) and v != v:
                    row += f"{'—':>18}"
                else:
                    row += f"{v:>18.4f}"
            lines.append(row)
    return "\n".join(lines)


def format_ir_alignment_table(all_ir: dict) -> str:
    """all_ir: {arm_name: {setting: ir_alignment_metrics_dict}}. Same column shape as
    baseline_results.json's own per-setting rows (recall@{1,3,5,10}, ndcg@{1,3,5,10}, mrr, map),
    over the SAME `retrieval` (Router.score-order, top-EVAL_K) rankings the product table above
    is built from -- so a reviewer can put this table next to the dataset's own BM25/Dense/Hybrid
    rows without re-deriving anything."""
    cols = ["n", "recall@1", "recall@3", "recall@5", "recall@10",
            "ndcg@1", "ndcg@3", "ndcg@5", "ndcg@10", "mrr", "map"]
    lines = []
    for arm, per_setting in all_ir.items():
        lines.append(f"\n=== {arm} (baseline-comparable) ===")
        head = f"{'setting':<24}" + "".join(f"{c:>10}" for c in cols)
        lines.append(head)
        lines.append("-" * len(head))
        for setting, m in per_setting.items():
            row = f"{setting:<24}"
            for c in cols:
                v = m.get(c, float("nan"))
                if isinstance(v, int):
                    row += f"{v:>10}"
                elif isinstance(v, float) and v != v:
                    row += f"{'—':>10}"
                else:
                    row += f"{v:>10.4f}"
            lines.append(row)
    return "\n".join(lines)


# ------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("convert", help="report corpus/query conversion stats only")

    p_run = sub.add_parser("run", help="run all four arms through the product path")
    p_run.add_argument("--dense-words", type=Path, default=None,
                        help="path to a words.bin built by `distill` (B3b+B5 arm); omitted -> "
                             "dense arm runs with an empty table (byte-identical to B1)")
    p_run.add_argument("--jsonl", type=Path,
                        default=VALIDATION_DIR / "skillretbench-rankings.jsonl")
    p_run.add_argument("--out", type=Path,
                        default=VALIDATION_DIR / "skillretbench-metrics.json")

    p_distill = sub.add_parser("distill", help="build the SKILLRET student word table (GPU venv only)")
    p_distill.add_argument("--out-dir", type=Path,
                            default=BAKEOFF_DIR / "build" / "ThakiCloud__SKILLRET-Embedding-0.6B__skillretbench")
    p_distill.add_argument("--dims", type=int, default=256)

    p_mat = sub.add_parser("materialize", help="write the on-disk monorepo tree for `latency`")
    p_mat.add_argument("--out-dir", type=Path, required=True)

    p_lat = sub.add_parser("latency", help="measure real hook-subprocess p50/p95 on the materialized tree")
    p_lat.add_argument("--monorepo", type=Path, required=True)
    p_lat.add_argument("--n", type=int, default=220)

    sub.add_parser("overlap", help="SkillRet vs SkillRetBench id/name overlap")

    args = ap.parse_args(argv)

    if args.cmd == "overlap":
        print(json.dumps(overlap_report(), indent=2, ensure_ascii=False))
        return 0

    needs = gf_corpora.verify("skillretbench")
    if needs:
        print("skillretbench corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillretbench()
    skills = data["corpus"]["skills"]
    queries = data["queries"]["queries"]
    cards, nodes, corpus_report = corpus_to_cards(skills)
    cases, query_report = queries_to_cases(queries, cards)

    if args.cmd == "convert":
        print(json.dumps({"corpus": corpus_report, "queries": query_report}, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "materialize":
        materialize_monorepo(cards, nodes, args.out_dir)
        print(f"materialized {len(cards)} skills / {len(nodes) - 1} categories under {args.out_dir}")
        return 0

    if args.cmd == "latency":
        result = measure_latency(args.monorepo, cases, n_queries=args.n)
        print(json.dumps(result, indent=2))
        return 0 if "error" not in result else 1

    if args.cmd == "distill":
        result = distill_word_table(cards, args.out_dir, dims=args.dims)
        m = result["manifest"]
        print(f"teacher: {m['teacher_id']} @ {m['teacher_revision']}")
        print(f"vocab_size: {m['vocab_size']}  dims: {m['dims']}")
        print(f"words.bin: {result['words_bin']}")
        return 0

    if args.cmd == "run":
        cli = _load_cli()
        metrics = _load_metrics()
        word_vectors = read_word_table(args.dense_words) if args.dense_words else {}
        arms = build_arms(cli, cards, nodes, word_vectors=word_vectors)

        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)

        def _quality(cases_subset, label):
            per_arm = {}
            per_arm_ir = {}
            per_arm_retrieval = {}
            per_arm_injection = {}
            all_records = []
            for arm_name, router in arms.items():
                retrieval, injection, records = run_arm(router, cases_subset, "node_scoped")
                per_arm_retrieval[arm_name] = retrieval
                per_arm_injection[arm_name] = injection
                for r in records:
                    r["arm"] = arm_name
                    r["node_key"] = "node_scoped"
                all_records.extend(records)
                per_setting = {}
                per_setting_ir = {}
                for setting in SETTING_TO_CATEGORY:
                    ret_s = [(r, c) for r, c in retrieval if c["setting"] == setting]
                    inj_s = [(r, c) for r, c in injection if c["setting"] == setting]
                    ev = metrics.evaluate(ret_s, k_cards=K_CARDS)
                    ev_inj = metrics.evaluate(inj_s, k_cards=K_CARDS)
                    ev[f"all_required@{K_CARDS}"] = ev_inj.get(f"all_required@{K_CARDS}")
                    ev[f"distractor_rate@{K_CARDS}"] = ev_inj.get(f"distractor_rate@{K_CARDS}")
                    per_setting[setting] = ev
                    per_setting_ir[setting] = ir_alignment_metrics(ret_s, metrics)
                ov = metrics.evaluate(retrieval, k_cards=K_CARDS)
                ov_inj = metrics.evaluate(injection, k_cards=K_CARDS)
                ov[f"all_required@{K_CARDS}"] = ov_inj.get(f"all_required@{K_CARDS}")
                ov[f"distractor_rate@{K_CARDS}"] = ov_inj.get(f"distractor_rate@{K_CARDS}")
                per_setting["OVERALL"] = ov
                per_setting_ir["OVERALL"] = ir_alignment_metrics(retrieval, metrics)
                per_arm[arm_name] = per_setting
                per_arm_ir[arm_name] = per_setting_ir
            print(f"\n########## {label} ##########")
            print(format_setting_arm_table(per_arm))
            print(format_ir_alignment_table(per_arm_ir))
            return per_arm, per_arm_ir, all_records, per_arm_retrieval, per_arm_injection

        all_cases = cases
        latin_cases = [c for c in cases if not c["has_hangul"]]

        results_all, ir_all, records_all, retrieval_all, injection_all = _quality(all_cases, "ALL QUERIES")
        results_latin, ir_latin, records_latin, retrieval_latin, injection_latin = _quality(
            latin_cases, "LATIN-ONLY QUERIES")

        # Dense reference run (R1) reporting -- DENSE-PROGRAM.md v2 SS4/SS5/SS6. Computed over ALL
        # QUERIES at node_scoped (the primary setting); this run gates nothing (SS6) and chooses
        # nothing on this corpus (SkillRetBench is test-B, SS3) -- w_dense=1 was fixed from the
        # CLI's own DEFAULT_WEIGHTS ON/OFF-gate guidance in build_arms() before this script was
        # ever run against SkillRetBench.
        dense_coverage = dense_coverage_report(arms["B3b+B5"], all_cases, "node_scoped")
        print(format_coverage_table(dense_coverage))
        dense_gates = dense_vs_b1_gate_report(
            metrics, all_cases,
            retrieval_all["B1"], injection_all["B1"],
            retrieval_all["B3b+B5"], injection_all["B3b+B5"],
        )
        print(format_gate_table(dense_gates))
        dataset_dense_backend = data["baselines"].get("meta", {}).get("dense_backend")
        dense_reference_run_r1 = {
            "status": "reference run R1 per docs/reports/bakeoff/DENSE-PROGRAM.md v2 SS6; "
                      "gates nothing; adoption is decided only for the eventual dev-tuned frozen "
                      "variant, run once per family on both test corpora",
            "no_tuning_on_this_corpus": "w_dense=1 (ON) was fixed from the CLI's own "
                      "DEFAULT_WEIGHTS ON/OFF-gate guidance (build_arms()) before this script was "
                      "ever run against SkillRetBench; SkillRetBench is test-B (SS3) and gates/"
                      "chooses nothing",
            "dataset_dense_baseline_caveat": (
                f"baseline_results.json meta.dense_backend == {dataset_dense_backend!r} -- the "
                "dataset's own published \"Dense\" row is not a model (jaccard_fallback); this "
                "run is the first real dense number measured on this benchmark and is compared "
                "only against the dataset's own BM25 row"),
            "coverage": dense_coverage,
            "gates_vs_b1": dense_gates,
        }

        # Supplementary scope ablation: B1 at node_root, over every query, ALL queries only.
        retrieval_root, injection_root, records_root = run_arm(arms["B1"], all_cases, "node_root")
        for r in records_root:
            r["arm"] = "B1"; r["node_key"] = "node_root"
        per_setting_root = {}
        for setting in SETTING_TO_CATEGORY:
            ret_s = [(r, c) for r, c in retrieval_root if c["setting"] == setting]
            inj_s = [(r, c) for r, c in injection_root if c["setting"] == setting]
            ev = metrics.evaluate(ret_s, k_cards=K_CARDS)
            ev_inj = metrics.evaluate(inj_s, k_cards=K_CARDS)
            ev[f"all_required@{K_CARDS}"] = ev_inj.get(f"all_required@{K_CARDS}")
            ev[f"distractor_rate@{K_CARDS}"] = ev_inj.get(f"distractor_rate@{K_CARDS}")
            per_setting_root[setting] = ev
        ov = metrics.evaluate(retrieval_root, k_cards=K_CARDS)
        ov_inj = metrics.evaluate(injection_root, k_cards=K_CARDS)
        ov[f"all_required@{K_CARDS}"] = ov_inj.get(f"all_required@{K_CARDS}")
        ov[f"distractor_rate@{K_CARDS}"] = ov_inj.get(f"distractor_rate@{K_CARDS}")
        per_setting_root["OVERALL"] = ov
        ir_root = {setting: ir_alignment_metrics(
            [(r, c) for r, c in retrieval_root if c["setting"] == setting], metrics)
            for setting in SETTING_TO_CATEGORY}
        ir_root["OVERALL"] = ir_alignment_metrics(retrieval_root, metrics)
        print("\n########## B1 @ node=_root (scope ablation, ALL QUERIES) ##########")
        print(format_setting_arm_table({"B1@_root": per_setting_root}))
        print(format_ir_alignment_table({"B1@_root": ir_root}))

        with gzip.open(str(args.jsonl) + ".gz", "wt") if False else open(args.jsonl, "w") as f:
            for r in records_all + records_root:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if args.jsonl.stat().st_size > 5 * 1024 * 1024:
            with open(args.jsonl, "rb") as fin, gzip.open(str(args.jsonl) + ".gz", "wb") as fout:
                fout.writelines(fin)
            args.jsonl.unlink()
            print(f"wrote {args.jsonl}.gz (gzipped, >5MB)")
        else:
            print(f"wrote {args.jsonl}")

        args.out.write_text(json.dumps({
            "corpus_report": corpus_report, "query_report": query_report,
            "all_queries": results_all, "ir_alignment_all": ir_all,
            "latin_only": results_latin, "ir_alignment_latin": ir_latin,
            "b1_scope_ablation_root": per_setting_root,
            "b1_scope_ablation_root_ir": ir_root,
            "dense_reference_run_r1": dense_reference_run_r1,
            "dataset_baseline_bm25": data["baselines"].get("baselines", {}).get("BM25"),
            "dataset_dense_backend": dataset_dense_backend,
        }, indent=2, ensure_ascii=False))
        print(f"\nwrote {args.out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
