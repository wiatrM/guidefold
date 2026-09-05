#!/usr/bin/env python3
"""tools/eval/dev_expand.py — F3 document expansion (DENSE-PROGRAM.md v2.1 SS4): dev-only
coordinate-descent evaluation of doc2query pseudo-queries (tools/expand/doc2query.py) as extra
BM25F index-time signal. Baseline is **P-flat** (tools/eval/dev_sparse.py's frozen proposal from
PR #36: every `field.*` weight = 1) -- never P-shipped, per the task brief. This script never
touches test-A/test-B and never invokes the doc2query model itself: it reads a pre-generated
pseudo-query JSONL (skill_id -> queries) and merges it into cards by skill_id.

Reused, never reimplemented (import tools/eval/dev_sparse.py wholesale):
  * corpus_to_cards / queries_to_cases    dev pool -> Guidefold cards / golden-schema cases.
  * _load_cli / _load_metrics             SourceFileLoader for the no-suffix CLI / metrics.py.
  * run_product_case                      policy_filter -> candidates -> score -> select, the
                                           actual product pipeline.
  * per_query_metrics / arm_summary       hit@1 / nDCG@10 / recall@10 / all_required@4, by k and
                                           overall.
  * bootstrap_paired_delta / paired_arrays  95% CI (percentile method), paired over queries.
  * write_jsonl_gz                        per-arm per-query JSONL (gzip), same file convention.

This module adds only what the F3 brief specifically asks for and dev_sparse.py has no reason to
contain: the `expansion` BM25F field (`make_expansion_index_cls`), the append-into-body variant
(`make_expansion_cards(..., mode="append")`), coverage (gold skills pulled into BM25F's top-50
that P-flat missed), an index-size estimator that is correct for a 6-field subclass (see
`estimate_index_bytes`'s docstring for why the shipped `_serialize_artifact_files` is NOT reused
here), and in-process per-query wall time.

Arms (<=4, coordinate descent, one changed parameter each, vs P-flat):
  E-field-1   pseudo-queries (n=5/skill) as a sixth BM25F field `expansion`, weight 1 -- flat,
              like every other field in P-flat.
  E-field-w   the `--field-w-mode` choice: "weight2" (same n=5 field, `field.expansion` -> 2) or
              "n10" (same weight 1, n=10/skill instead of 5) -- see the F3 report for which was
              picked and why.
  E-append    the SAME n=5 pseudo-queries, folded into `_body` instead of a separate field --
              P-flat's own 5-field Index, unchanged weights, only the body TEXT differs. Isolates
              whether the separate-field normalisation matters (the same question P-onefield
              asked of BM25F itself in the sparse diagnosis).
  (4th slot: reserved / not spent unless the report says otherwise.)

Requires docs/reports/bakeoff/validation/doc2query-dev-n5-seed42.jsonl (and, only for
`--field-w-mode n10`, doc2query-dev-n10-seed42.jsonl) to already exist -- built by
`tools/expand/doc2query.py generate`. This script never imports torch.

Subcommands:
  convert   report corpus/query/pseudo-query merge stats only (no Router run, fast — for CI).
  run       build every arm, run all 1 000 dev cases, write per-arm per-query JSONL (gzip),
            compute metrics + coverage + paired bootstrap CIs vs P-flat, measure index size /
            in-process query time, print tables, write a JSON summary.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — ONLY pinned-corpus loader
import dev_sparse  # noqa: E402  reused wholesale — see module docstring

PUBLISHER = dev_sparse.PUBLISHER
EVAL_K = dev_sparse.EVAL_K
K_CARDS = dev_sparse.K_CARDS
RECORD_TOPN = dev_sparse.RECORD_TOPN


# ============================================================================ pseudo-query merge
def load_pseudo_queries(path: Path) -> dict:
    """{skill_id: [queries]} from a tools/expand/doc2query.py `generate` JSONL output file."""
    out = {}
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[row["skill_id"]] = list(row.get("queries") or [])
    return out


def expansion_text(queries: list) -> str:
    return " ".join(queries)


def make_expansion_cards(cards: dict, id_to_urn: dict, pseudo: dict, mode: str) -> dict:
    """mode="field": add an `_expansion` key (the new field's text; `_body`/every other key
    untouched). mode="append": fold the pseudo-query text into `_body` itself, no new key at all.
    `pseudo` is keyed by the ORIGINAL SKILLRET skill id, not the card urn -- `id_to_urn` (from
    dev_sparse.corpus_to_cards) bridges that; a skill with no pseudo-queries (should not happen
    over the full dev pool, but handled) gets an empty-string expansion / an unmodified body."""
    if mode not in ("field", "append"):
        raise ValueError(f"unknown mode {mode!r}")
    urn_to_text = {}
    for sid, u in id_to_urn.items():
        qs = pseudo.get(sid)
        if qs:
            urn_to_text[u] = expansion_text(qs)

    out = {}
    for u, c in cards.items():
        text = urn_to_text.get(u, "")
        if mode == "field":
            out[u] = {**c, "_expansion": text}
        else:
            out[u] = {**c, "_body": (c["_body"] + "\n" + text) if text else c["_body"]}
    return out


# ============================================================================ the expansion field
def make_expansion_index_cls(cli, field_weight: int = 1):
    """Index subclass adding a sixth BM25F field, `expansion` -- the same subclassing technique
    dev_sparse.py's `make_k1b_index_cls` uses for K1/B (`Index.from_cards` is a classmethod, so
    calling it on the subclass builds a correctly-typed instance). Confirmed by reading
    `Index.__init__`/`_build_bm25`/`Router._bm25_scores`: every one of them reads `self.FIELDS` /
    `idx.FIELDS` (an INSTANCE attribute lookup, resolved through the subclass MRO) and
    `idx.weights[f"field.{field}"]` -- never a module-level `Index.FIELDS` constant -- so a
    subclass overriding `FIELDS` and `DEFAULT_WEIGHTS` is genuinely live end-to-end through the
    real product `Router.score()` path, not just `Index` internals (see
    tests/test_dev_expand.py's round-trip test).

    The ONE exception is `_serialize_artifact_files` (the E1.4 on-disk artifact writer), which
    DOES hardcode the module-level `Index.FIELDS` tuple -- confirmed by reading it -- so it would
    silently DROP the `expansion` field's postings/norms if called on one of these arms. This
    script never calls it for exactly that reason; `estimate_index_bytes` below reproduces its
    byte-counting logic directly against `idx.FIELDS` instead. Not a bug fixed here --
    `skills/guidefold/scripts/guidefold` is out of scope for this agent (two others are editing
    it); flagged in the F3 report as a incidental finding."""
    class _ExpansionIndex(cli.Index):
        FIELDS = cli.Index.FIELDS + ("expansion",)
        DEFAULT_WEIGHTS = {**cli.Index.DEFAULT_WEIGHTS, "field.expansion": field_weight}

        def _field_text(self, card, field):
            if field == "expansion":
                return card.get("_expansion", "")
            return super()._field_text(card, field)

    return _ExpansionIndex


# ============================================================================ index size (fair, 6-field-aware)
def estimate_index_bytes(idx) -> dict:
    """Reproduces `skills/guidefold/scripts/guidefold`'s own on-disk BM25 artifact byte format
    (terms.bin / norms.bin / postings.bin / postings.idx -- see `_serialize_artifact_files`)
    directly from `idx.FIELDS` / `idx.postings` / `idx.field_norm` / `idx.idf`, WITHOUT calling
    the shipped serializer -- see `make_expansion_index_cls`'s docstring for why that would
    silently under-count a 6-field subclass. varint length helper is duplicated (not imported)
    so this stays a read-only measurement, never a dependency on the CLI's private encoding
    helpers. Deliberately excludes cards.jsonl/graph.json/nodes.json/vectors.i8/words.bin: those
    are byte-identical across every arm in this report (same skill set, empty `requires` graph,
    dense channel off, `w_dense=0`), so they contribute nothing to a SIZE DELTA between arms --
    only the parts that can actually change size are measured."""
    def _varint_len(n: int) -> int:
        length = 1
        n >>= 7
        while n:
            length += 1
            n >>= 7
        return length

    doc_urns = sorted(idx.cards.keys())
    doc_id = {u: i for i, u in enumerate(doc_urns)}
    n_docs = len(doc_urns)

    terms_bytes = 0
    for term, v in idx.idf.items():
        term_b = term.encode("utf-8")
        terms_bytes += _varint_len(len(term_b)) + len(term_b) + _varint_len(v)

    norms_bytes = 4 * n_docs * len(idx.FIELDS)  # struct.pack(f"<{n_docs}I", ...) per field

    postings_bytes = 0
    postings_idx_bytes = 0
    for fi, field in enumerate(idx.FIELDS):
        offset = 0
        for term in sorted(idx.postings[field].keys()):
            post = idx.postings[field][term]
            plist = sorted((doc_id[u], tf) for u, tf in post.items())
            block_len = 0
            prev = 0
            for d, tf in plist:
                block_len += _varint_len(d - prev) + _varint_len(tf)
                prev = d
            term_b = term.encode("utf-8")
            postings_idx_bytes += (_varint_len(fi) + _varint_len(len(term_b)) + len(term_b)
                                   + _varint_len(offset) + _varint_len(block_len))
            postings_bytes += block_len
            offset += block_len

    return {
        "n_docs": n_docs, "n_fields": len(idx.FIELDS), "n_terms": len(idx.idf),
        "terms_bin_bytes": terms_bytes, "norms_bin_bytes": norms_bytes,
        "postings_bin_bytes": postings_bytes, "postings_idx_bytes": postings_idx_bytes,
        "total_bm25_bytes": terms_bytes + norms_bytes + postings_bytes + postings_idx_bytes,
    }


# ============================================================================ coverage
def compute_coverage(cases: list, baseline_ranked_by_qid: dict, arm_ranked_by_qid: dict,
                      topn: int = RECORD_TOPN) -> tuple:
    """'Coverage first': gold (grade>=2) skills the arm's BM25F top-`topn` pulls in that the
    baseline's top-`topn` missed (`recovered`), and the reverse (`lost`) -- both directions
    matter, a family that trades old coverage for new coverage is not obviously an improvement.
    Aggregated over every gold-skill INSTANCE across all cases (a case with 2 required skills
    contributes up to 2), plus per-case detail for inspection."""
    n_required_total = 0
    n_recovered = 0
    n_lost = 0
    n_queries_gained = 0
    n_queries_lost = 0
    per_query = {}
    for case in cases:
        qid = case["id"]
        required = {r["urn"] for r in case["relevant"] if r["grade"] >= 2}
        if not required:
            continue
        base_top = set(baseline_ranked_by_qid[qid][:topn])
        arm_top = set(arm_ranked_by_qid[qid][:topn])
        recovered = (required - base_top) & arm_top
        lost = (required & base_top) - arm_top
        n_required_total += len(required)
        n_recovered += len(recovered)
        n_lost += len(lost)
        if recovered:
            n_queries_gained += 1
        if lost:
            n_queries_lost += 1
        if recovered or lost:
            per_query[qid] = {"recovered": sorted(recovered), "lost": sorted(lost)}
    summary = {
        "n_required_total": n_required_total, "n_recovered": n_recovered, "n_lost": n_lost,
        "net_recovered": n_recovered - n_lost,
        "recovered_rate_of_required": (n_recovered / n_required_total) if n_required_total else float("nan"),
        "lost_rate_of_required": (n_lost / n_required_total) if n_required_total else float("nan"),
        "n_queries_gained": n_queries_gained, "n_queries_lost": n_queries_lost,
    }
    return summary, per_query


# ============================================================================ query timing
def _latency_stats(samples_s: list) -> dict:
    if not samples_s:
        return {"mean_ms": float("nan"), "median_ms": float("nan"), "p95_ms": float("nan")}
    ms = sorted(x * 1000.0 for x in samples_s)
    n = len(ms)
    p95_idx = min(n - 1, int(0.95 * n))
    return {"mean_ms": statistics.fmean(ms), "median_ms": statistics.median(ms), "p95_ms": ms[p95_idx]}


# ============================================================================ arms
def _build_arms(cli, cards: dict, nodes: dict, id_to_urn: dict, pseudo5: dict, pseudo10: dict,
                 field_w_mode: str) -> dict:
    """name -> (index, router, top_n, kind). Each F3 arm differs from P-flat by exactly ONE
    changed parameter -- see tests/test_dev_expand.py for the byte-level assertion of that."""
    arms = {}
    flat_weights = {f"field.{f}": 1 for f in cli.Index.FIELDS}

    idx_flat = cli.Index.from_cards(cards, nodes, weights=flat_weights)
    arms["P-flat"] = (idx_flat, cli.Router(idx_flat), 50, "baseline")

    exp_cls_1 = make_expansion_index_cls(cli, field_weight=1)
    cards_field5 = make_expansion_cards(cards, id_to_urn, pseudo5, mode="field")
    w_field1 = {**flat_weights, "field.expansion": 1}
    idx_e1 = exp_cls_1.from_cards(cards_field5, nodes, weights=w_field1)
    arms["E-field-1"] = (idx_e1, cli.Router(idx_e1), 50, "field")

    if field_w_mode == "weight2":
        exp_cls_w = make_expansion_index_cls(cli, field_weight=2)
        w_field2 = {**flat_weights, "field.expansion": 2}
        idx_ew = exp_cls_w.from_cards(cards_field5, nodes, weights=w_field2)
    elif field_w_mode == "n10":
        exp_cls_w = make_expansion_index_cls(cli, field_weight=1)
        cards_field10 = make_expansion_cards(cards, id_to_urn, pseudo10 or {}, mode="field")
        idx_ew = exp_cls_w.from_cards(cards_field10, nodes, weights=w_field1)
    else:
        raise ValueError(f"unknown field_w_mode {field_w_mode!r}")
    arms["E-field-w"] = (idx_ew, cli.Router(idx_ew), 50, "field")

    cards_append = make_expansion_cards(cards, id_to_urn, pseudo5, mode="append")
    idx_append = cli.Index.from_cards(cards_append, nodes, weights=flat_weights)
    arms["E-append"] = (idx_append, cli.Router(idx_append), 50, "append")

    return arms


# ============================================================================ CLI
def cmd_convert(args) -> int:
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)

    pseudo_report = {}
    for label, path in (("n5", args.pseudo_n5), ("n10", args.pseudo_n10)):
        if path and Path(path).exists():
            pseudo = load_pseudo_queries(path)
            n_matched = sum(1 for sid in id_to_urn if sid in pseudo)
            pseudo_report[label] = {"file": str(path), "n_skills": len(pseudo),
                                     "n_matched_to_dev_pool": n_matched,
                                     "n_dev_pool": len(id_to_urn)}
        else:
            pseudo_report[label] = {"file": str(path) if path else None, "present": False}

    print(json.dumps({"corpus": corpus_report, "queries": query_report, "pseudo": pseudo_report},
                      indent=2, ensure_ascii=False))
    return 0


def cmd_run(args) -> int:
    t0 = time.time()
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
        return 1
    if not Path(args.pseudo_n5).exists():
        print(f"pseudo-query file not found: {args.pseudo_n5} "
              f"(run: tools/expand/doc2query.py generate --n 5 --out {args.pseudo_n5})",
              file=sys.stderr)
        return 1
    if args.field_w_mode == "n10" and not (args.pseudo_n10 and Path(args.pseudo_n10).exists()):
        print(f"--field-w-mode n10 needs --pseudo-n10 (not found: {args.pseudo_n10})",
              file=sys.stderr)
        return 1

    metrics = dev_sparse._load_metrics()
    cli = dev_sparse._load_cli()

    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    print(f"[{time.time()-t0:6.1f}s] cards={len(cards)} nodes={len(nodes)} cases={len(cases)}",
          file=sys.stderr)
    if query_report["qrel_mismatches"] or query_report["missing_urn"]:
        print("WARNING query/qrel report:", json.dumps(query_report), file=sys.stderr)

    pseudo5 = load_pseudo_queries(args.pseudo_n5)
    pseudo10 = load_pseudo_queries(args.pseudo_n10) if args.pseudo_n10 and Path(args.pseudo_n10).exists() else {}
    n_matched5 = sum(1 for sid in id_to_urn if sid in pseudo5)
    print(f"[{time.time()-t0:6.1f}s] pseudo-n5 matched {n_matched5}/{len(id_to_urn)} dev-pool skills",
          file=sys.stderr)

    arms = _build_arms(cli, cards, nodes, id_to_urn, pseudo5, pseudo10, args.field_w_mode)
    print(f"[{time.time()-t0:6.1f}s] built {len(arms)} arms", file=sys.stderr)

    all_qids = [c["id"] for c in cases]
    per_query_by_arm = {}
    records_by_arm = {}
    ranked_by_qid_by_arm = {}
    latency_by_arm = {}
    index_bytes_by_arm = {}
    abstain_counts = {}

    for arm_name, (index, router, top_n, kind) in arms.items():
        ranked_by_qid, records, latencies = {}, [], []
        n_abstained = 0
        for case in cases:
            tq0 = time.perf_counter()
            rec = dev_sparse.run_product_case(router, case, top_n=top_n)
            latencies.append(time.perf_counter() - tq0)
            ranked_by_qid[rec["query_id"]] = rec["ranked"]
            n_abstained += int(rec["abstained"])
            records.append({**rec, "arm": arm_name})
        per_query_by_arm[arm_name] = dev_sparse.per_query_metrics(metrics, ranked_by_qid, cases)
        ranked_by_qid_by_arm[arm_name] = ranked_by_qid
        latency_by_arm[arm_name] = _latency_stats(latencies)
        index_bytes_by_arm[arm_name] = estimate_index_bytes(index)
        abstain_counts[arm_name] = n_abstained
        records_by_arm[arm_name] = records
        print(f"[{time.time()-t0:6.1f}s] ran {arm_name} (kind={kind}, abstained={n_abstained})",
              file=sys.stderr)

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for arm_name, records in records_by_arm.items():
        fname = f"dev-expand-{arm_name.lower()}.jsonl.gz"
        dev_sparse.write_jsonl_gz(VALIDATION_DIR / fname, records)
        print(f"[{time.time()-t0:6.1f}s] wrote {fname}", file=sys.stderr)

    summary = {arm_name: dev_sparse.arm_summary(metrics, per_q, cases)
               for arm_name, per_q in per_query_by_arm.items()}

    by_k = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    breakdowns = {"overall": all_qids, **{f"k={k}": qids for k, qids in sorted(by_k.items())}}

    comparisons = {}
    challengers = [a for a in per_query_by_arm if a != "P-flat"]
    for chal in challengers:
        key = f"{chal}_vs_P-flat"
        comparisons[key] = {}
        for bd_name, qids in breakdowns.items():
            comparisons[key][bd_name] = {}
            for metric in ("ndcg10", "recall10"):
                a, b = dev_sparse.paired_arrays(per_query_by_arm["P-flat"], per_query_by_arm[chal],
                                                 qids, metric)
                comparisons[key][bd_name][metric] = dev_sparse.bootstrap_paired_delta(a, b)

    coverage = {}
    coverage_per_query = {}
    for chal in challengers:
        cov_summary, cov_pq = compute_coverage(cases, ranked_by_qid_by_arm["P-flat"],
                                                ranked_by_qid_by_arm[chal])
        coverage[chal] = cov_summary
        coverage_per_query[chal] = cov_pq

    index_size_delta = {
        chal: {k: index_bytes_by_arm[chal][k] - index_bytes_by_arm["P-flat"][k]
               for k in index_bytes_by_arm[chal] if k != "n_docs"}
        for chal in challengers
    }
    latency_delta_ms = {
        chal: {k: latency_by_arm[chal][k] - latency_by_arm["P-flat"][k] for k in latency_by_arm[chal]}
        for chal in challengers
    }

    out = {
        "corpus_report": corpus_report, "query_report": query_report,
        "field_w_mode": args.field_w_mode,
        "n_cases": len(cases), "abstain_counts": abstain_counts,
        "summary": summary, "comparisons": comparisons,
        "coverage": coverage,
        "index_bytes": index_bytes_by_arm, "index_bytes_delta_vs_p_flat": index_size_delta,
        "query_latency_ms": latency_by_arm, "query_latency_delta_ms_vs_p_flat": latency_delta_ms,
        "runtime_s": time.time() - t0,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{time.time()-t0:6.1f}s] wrote {args.out}", file=sys.stderr)

    if args.coverage_out:
        args.coverage_out.write_text(json.dumps(coverage_per_query, indent=2, ensure_ascii=False))
        print(f"[{time.time()-t0:6.1f}s] wrote {args.coverage_out}", file=sys.stderr)

    cols = ["n", "hit1", "ndcg10", "recall10", "all_required4"]
    head = f"{'arm':<12}{'break':<8}" + "".join(f"{c:>14}" for c in cols)
    print(head)
    print("-" * len(head))
    for arm_name, blocks in summary.items():
        for bd_name in ["overall"] + [f"k={k}" for k in sorted(by_k)]:
            m = blocks[bd_name]
            row = f"{arm_name:<12}{bd_name:<8}"
            for c in cols:
                v = m[c]
                row += f"{v:>14}" if isinstance(v, int) else (
                    f"{'—':>14}" if dev_sparse._isnan(v) else f"{v:>14.4f}")
            print(row)

    print()
    print(f"{'arm':<12}{'recovered':>12}{'lost':>8}{'net':>8}{'q_gain':>8}{'q_lose':>8}"
          f"{'bytes_d':>12}{'lat_d_ms':>10}")
    for chal in challengers:
        c = coverage[chal]
        bd = index_size_delta[chal]["total_bm25_bytes"]
        ld = latency_delta_ms[chal]["mean_ms"]
        print(f"{chal:<12}{c['n_recovered']:>12}{c['n_lost']:>8}{c['net_recovered']:>8}"
              f"{c['n_queries_gained']:>8}{c['n_queries_lost']:>8}{bd:>12}{ld:>10.4f}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_n5 = VALIDATION_DIR / "doc2query-dev-n5-seed42.jsonl"
    default_n10 = VALIDATION_DIR / "doc2query-dev-n10-seed42.jsonl"

    p_conv = sub.add_parser("convert", help="report corpus/query/pseudo-query merge stats only")
    p_conv.add_argument("--pseudo-n5", type=Path, default=default_n5)
    p_conv.add_argument("--pseudo-n10", type=Path, default=default_n10)

    p_run = sub.add_parser("run", help="build every arm, run all dev cases, compute metrics")
    p_run.add_argument("--pseudo-n5", type=Path, default=default_n5)
    p_run.add_argument("--pseudo-n10", type=Path, default=default_n10)
    p_run.add_argument("--field-w-mode", choices=["weight2", "n10"], default="weight2")
    p_run.add_argument("--out", type=Path, default=VALIDATION_DIR / "dev-expand-metrics.json")
    p_run.add_argument("--coverage-out", type=Path,
                        default=VALIDATION_DIR / "dev-expand-coverage.json")

    args = ap.parse_args(argv)
    if args.cmd == "convert":
        return cmd_convert(args)
    if args.cmd == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
