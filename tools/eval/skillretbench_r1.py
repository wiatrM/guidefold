#!/usr/bin/env python3
"""tools/eval/skillretbench_r1.py — DENSE-PROGRAM.md v2.1 §6 R1 reference run: the full
SKILLRET-Embedding-0.6B *encoder* (not the distilled B3b+B5 static word-table arm already reported
in docs/reports/bakeoff/SkillRetBench-2026-09-05.md, PR #30) on SkillRetBench (test-B), through
the unmodified product path.

Why a separate script rather than a fifth arm inside tools/eval/skillretbench.py's `build_arms()`:
the encoder-backed dense Router (tools/eval/dense_ref.py's `DenseCandidateRouter`) is keyed by
precomputed per-document/per-query embeddings selected by query id, not by the base Router's
word-table `_dense_scores` (which `build_arms()`'s existing B3b+B5 arm uses unmodified) — a
structurally different Router subclass, not a `weights`-only variant of the same one. Retrofitting
`build_arms()`'s signature to build either kind of dense Router would touch a well-tested,
already-reported function (24 tests, PR #30) for no shared benefit; this script instead IMPORTS
`build_arms()` only to obtain F0 (`arms["B1"]`) as a guaranteed byte-identical baseline, and
otherwise reuses skillretbench.py's converter/runner/metrics/report functions verbatim — see that
module's own docstring "reused, never reimplemented" list, which applies here unchanged. The
encoder-backed Router plumbing itself (`DenseCandidateRouter`, `build_dense_index_and_router`,
`quantize`/`quant_cosine`/`encode_chunked`, the on-disk cache read/write) lives in
tools/eval/dense_ref.py, shared verbatim with tools/eval/skillret.py's R1 runner (test-A,
SKILLRET-test, PR #33) — factored out of skillret.py rather than reimplemented here.

This is a REFERENCE run only (DENSE-PROGRAM.md v2.1 §6): tooling defaults, w_dense=1, no tuning of
anything on this corpus, gates nothing. Every "gate" field this script prints answers "would this
reference run have cleared the rule", never "is dense adopted" — adoption is decided only for the
eventual dev-tuned frozen variant, run once per family on both test corpora.

Subcommands:
    encode   [GPU venv only] embed all 501 skills + every surviving query, quantise int8, cache
             them under tools/eval/.skillretbench-r1-cache/
    run      run F0 (skillretbench.py's `build_arms()["B1"]`) and R1-encoder through the product
             path at both node_scoped and node_root, over ALL queries and Latin-only; write gzip
             per-query JSONL + a summary JSON with paired-bootstrap 95% CIs (1,000 resamples) on
             the delta vs F0 for all_required@4, hit@1, AND distractor_rate@4/HSR@4 (per setting
             and overall) — HSR@4's full CI is new orchestration here: skillretbench.py's own
             `dense_vs_b1_gate_report` computes only a point-estimate delta for it (matching what
             PR #30 actually asked for), and SKILLRET-test (test-A) carries no distractor labels
             at all, so this gate could never get a CI there.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "tools" / "eval"
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"
CACHE_DIR = Path(__file__).resolve().parent / ".skillretbench-r1-cache"

if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import corpora  # tools/eval/corpora.py — stdlib only, the ONLY pinned-corpus loader
import dense_ref  # tools/eval/dense_ref.py — encoder-backed dense Router, shared w/ skillret.py
import skillretbench  # tools/eval/skillretbench.py — converter/runner/metrics/report, reused verbatim

MODEL_HF_ID = "ThakiCloud/SKILLRET-Embedding-0.6B"
MODEL_REV = "0e10886e80a0aacc9efddc28282a258e2ab7eae1"
GPU_VENV_PYTHON = "/home/mike/.cache/guidefold/gpu-venv/bin/python"  # same venv as tools/eval/skillret.py
K_CARDS = skillretbench.K_CARDS
BOOTSTRAP_RESAMPLES = 1000


# --------------------------------------------------------------------------- shared corpus load
def _load_corpus():
    problems = corpora.verify("skillretbench")
    if problems:
        raise SystemExit("skillretbench_r1: corpus verification FAILED:\n" + "\n".join(problems))
    data = corpora.load_skillretbench()
    skills = data["corpus"]["skills"]
    queries = data["queries"]["queries"]
    cards, nodes, corpus_report = skillretbench.corpus_to_cards(skills)
    cases, query_report = skillretbench.queries_to_cases(queries, cards)
    return data, skills, cards, nodes, cases, corpus_report, query_report


# --------------------------------------------------------------------------- cmd: encode (GPU venv)
def cmd_encode(args):
    if sys.executable != GPU_VENV_PYTHON and not args.force_any_python:
        raise SystemExit(f"skillretbench_r1 encode: must run under {GPU_VENV_PYTHON} "
                          f"(got {sys.executable}); pass --force-any-python to override")
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(REPO_ROOT / "tools" / "bakeoff"))
    import numpy as np
    import encode as bakeoff_encode  # tools/bakeoff/encode.py — Encoder class, reused verbatim

    data, skills, cards, nodes, cases, _corpus_report, _query_report = _load_corpus()
    skill_id_to_skill = {s["skill_id"]: s for s in skills}

    skill_order = sorted(cards.keys())
    skill_texts = []
    for u in skill_order:
        s = skill_id_to_skill[cards[u]["name"]]  # card["name"] == skill_id, by corpus_to_cards's own invariant
        skill_texts.append((s.get("description") or "") + "\n\n" + (s.get("full_text") or ""))
    # Query text/order comes from `cases` (post queries_to_cases), not the raw query list: cases
    # already dropped the (zero, on this pinned corpus revision) empty-gold queries, and
    # case["id"] is exactly what run_case's `_current_qid` keys DenseCandidateRouter's
    # query_vec_of lookup by (skillretbench.py's run_case sets `router._current_qid = case["id"]`
    # whenever the router has that attribute).
    query_order = [c["id"] for c in cases]
    query_texts = [c["query"] for c in cases]
    if args.sample:
        skill_order, skill_texts = skill_order[: args.sample], skill_texts[: args.sample]
        query_order, query_texts = query_order[: args.sample], query_texts[: args.sample]

    # Same batch-size split as tools/eval/skillret.py's cmd_encode, for the same measured reason:
    # SkillRetBench's own full_text bodies run long enough that the encoder's own default
    # batch_size=64 risks a CUDA OOM once several near-8192-token sequences land in one forward
    # pass (sentence-transformers sorts a batch by length before padding). Queries are short.
    enc_skills = bakeoff_encode.Encoder(MODEL_HF_ID, MODEL_REV, batch_size=args.skill_batch_size)
    enc_queries = bakeoff_encode.Encoder(MODEL_HF_ID, MODEL_REV)

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


# --------------------------------------------------------------------------- cmd: run
def _write_jsonl_gz(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _filter_by_ids(pairs, ids):
    return [(r, c) for r, c in pairs if c["id"] in ids]


def _per_setting_metrics(metrics_mod, retrieval, injection):
    """Same per-setting-then-OVERALL shape skillretbench.py's own `cmd_run`/`_quality` builds
    inline — factored here as a small helper so `run` below doesn't repeat it four times (once per
    arm x query-subset)."""
    out = {}
    for setting in skillretbench.SETTING_TO_CATEGORY:
        ret_s = [(r, c) for r, c in retrieval if c["setting"] == setting]
        inj_s = [(r, c) for r, c in injection if c["setting"] == setting]
        ev = metrics_mod.evaluate(ret_s, k_cards=K_CARDS)
        ev_inj = metrics_mod.evaluate(inj_s, k_cards=K_CARDS)
        ev[f"all_required@{K_CARDS}"] = ev_inj.get(f"all_required@{K_CARDS}")
        ev[f"distractor_rate@{K_CARDS}"] = ev_inj.get(f"distractor_rate@{K_CARDS}")
        out[setting] = ev
    ov = metrics_mod.evaluate(retrieval, k_cards=K_CARDS)
    ov_inj = metrics_mod.evaluate(injection, k_cards=K_CARDS)
    ov[f"all_required@{K_CARDS}"] = ov_inj.get(f"all_required@{K_CARDS}")
    ov[f"distractor_rate@{K_CARDS}"] = ov_inj.get(f"distractor_rate@{K_CARDS}")
    out["OVERALL"] = ov
    return out


def _per_setting_ir(metrics_mod, retrieval):
    out = {setting: skillretbench.ir_alignment_metrics(
               [(r, c) for r, c in retrieval if c["setting"] == setting], metrics_mod)
           for setting in skillretbench.SETTING_TO_CATEGORY}
    out["OVERALL"] = skillretbench.ir_alignment_metrics(retrieval, metrics_mod)
    return out


def hsr_bootstrap_report(metrics_mod, injection_a, injection_b, k_cards=K_CARDS,
                          n_resamples=BOOTSTRAP_RESAMPLES, seed=3):
    """DENSE-PROGRAM.md v2.1 §5 requires a paired-bootstrap 95% CI — not just the point-estimate
    delta `skillretbench.dense_vs_b1_gate_report` computes — for distractor_rate@4/HSR@4 on THIS
    corpus: SkillRetBench carries real distractor labels; SKILLRET-test (test-A, PR #33) has none,
    so this gate could not even be attempted there. Reuses skillretbench.py's own
    `_bootstrap_paired_delta` primitive (never a second bootstrap implementation) over the SAME
    unfiltered per-setting population `dense_vs_b1_gate_report` itself uses for HSR@4/ndcg@10
    (every case in the setting, not the "answered" pairing hit@1/all_required@4 use — see that
    function's own docstring). A case is dropped from a resample only when distractor_rate is
    itself undetermined (NaN — no labelled distractor in that case) for either arm, since
    `_bootstrap_paired_delta` has no NaN handling of its own."""
    out = {}
    for setting in list(skillretbench.SETTING_TO_CATEGORY) + ["OVERALL"]:
        idx = [i for i, (_, c) in enumerate(injection_a)
               if setting == "OVERALL" or c["setting"] == setting]
        a = [metrics_mod.distractor_rate(injection_a[i][0], injection_a[i][1], k_cards) for i in idx]
        b = [metrics_mod.distractor_rate(injection_b[i][0], injection_b[i][1], k_cards) for i in idx]
        pairs = [(x, y) for x, y in zip(a, b) if x == x and y == y]  # drop NaN ("undetermined") pairs
        av = [p[0] for p in pairs]
        bv = [p[1] for p in pairs]
        out[setting] = skillretbench._bootstrap_paired_delta(av, bv, n_resamples=n_resamples, seed=seed)
    return out


def format_hsr_bootstrap_table(hsr_boot: dict) -> str:
    lines = ["\n=== R1-encoder vs F0 -- HSR@4/distractor_rate@4 paired bootstrap (95% CI) ==="]
    head = f"{'setting':<24}{'delta':>10}{'[95% CI]':>20}{'n':>8}"
    lines.append(head); lines.append("-" * len(head))
    for setting, v in hsr_boot.items():
        d = v["delta"]
        d_s = "—" if d != d else f"{d:+.4f}"
        lo, hi = v["ci_lo"], v["ci_hi"]
        ci_s = "—" if lo != lo else f"[{lo:+.4f},{hi:+.4f}]"
        lines.append(f"{setting:<24}{d_s:>10}{ci_s:>20}{v['n']:>8}")
    return "\n".join(lines)


def cmd_run(args):
    cli = skillretbench._load_cli()
    metrics_mod = skillretbench._load_metrics()
    data, skills, cards, nodes, cases, corpus_report, query_report = _load_corpus()
    if args.sample:
        cases = cases[: args.sample]
    meta, row_of, skill_mat, query_vec_of = dense_ref.load_dense_cache(CACHE_DIR)

    latin_ids = {c["id"] for c in cases if not c["has_hangul"]}

    arms = skillretbench.build_arms(cli, cards, nodes)   # F0 == arms["B1"], byte-identical baseline
    f0_router = arms["B1"]
    idx_r1, r1_router = dense_ref.build_dense_index_and_router(
        cli, cards, nodes, row_of, skill_mat, query_vec_of, weights={"w_dense": 1})

    summary = {
        "header": {
            "corpus": "skillretbench", "n_skills": len(cards), "n_queries_run": len(cases),
            "n_queries_latin": len(latin_ids),
            "w_dense_f0": f0_router.index.weights.get("w_dense", 0),
            "w_dense_r1": idx_r1.weights.get("w_dense", 0),
            "encoder": meta,
            "status": "REFERENCE RUN R1 per docs/reports/bakeoff/DENSE-PROGRAM.md v2.1 §6: "
                      "tooling defaults, w_dense=1, no tuning of anything on this corpus, gates "
                      "nothing; adoption is decided only for the eventual dev-tuned frozen "
                      "variant, run once per family on both test corpora",
        },
        "settings": {},
    }
    all_records = []
    for setting in ("node_scoped", "node_root"):
        t0 = time.time()
        ret_f0, inj_f0, rec_f0 = skillretbench.run_arm(f0_router, cases, setting)
        f0_elapsed = time.time() - t0
        t0 = time.time()
        ret_r1, inj_r1, rec_r1 = skillretbench.run_arm(r1_router, cases, setting)
        r1_elapsed = time.time() - t0
        for r in rec_f0:
            r["arm"] = "F0"; r["node_key"] = setting
        for r in rec_r1:
            r["arm"] = "R1-encoder"; r["node_key"] = setting
        all_records.extend(rec_f0)
        all_records.extend(rec_r1)

        # Latin-only metrics are derived by filtering this SAME full-corpus run down to the
        # Latin-query ids, rather than a second run_arm() call over the Latin subset: every stage
        # of the product path (policy_filter/candidates/score/select) is computed per query with
        # no cross-query state, so the two are mathematically identical -- skillretbench.py's own
        # `cmd_run` re-runs instead (an equally valid but 2x-costlier choice); filtering here keeps
        # this reference run to 2 run_arm() calls per node setting (F0 + R1-encoder) instead of 4.
        ret_f0_latin = _filter_by_ids(ret_f0, latin_ids)
        inj_f0_latin = _filter_by_ids(inj_f0, latin_ids)
        ret_r1_latin = _filter_by_ids(ret_r1, latin_ids)
        inj_r1_latin = _filter_by_ids(inj_r1, latin_ids)

        coverage = skillretbench.dense_coverage_report(r1_router, cases, setting)
        gates = skillretbench.dense_vs_b1_gate_report(
            metrics_mod, cases, ret_f0, inj_f0, ret_r1, inj_r1, k_cards=K_CARDS,
            n_resamples=BOOTSTRAP_RESAMPLES)
        hsr_boot = hsr_bootstrap_report(metrics_mod, inj_f0, inj_r1, k_cards=K_CARDS,
                                         n_resamples=BOOTSTRAP_RESAMPLES)

        summary["settings"][setting] = {
            "elapsed_s": {"F0": f0_elapsed, "R1-encoder": r1_elapsed},
            "all_queries": {
                "F0": {"metrics": _per_setting_metrics(metrics_mod, ret_f0, inj_f0),
                       "ir": _per_setting_ir(metrics_mod, ret_f0)},
                "R1-encoder": {"metrics": _per_setting_metrics(metrics_mod, ret_r1, inj_r1),
                               "ir": _per_setting_ir(metrics_mod, ret_r1)},
            },
            "latin_only": {
                "F0": {"metrics": _per_setting_metrics(metrics_mod, ret_f0_latin, inj_f0_latin),
                       "ir": _per_setting_ir(metrics_mod, ret_f0_latin)},
                "R1-encoder": {"metrics": _per_setting_metrics(metrics_mod, ret_r1_latin, inj_r1_latin),
                               "ir": _per_setting_ir(metrics_mod, ret_r1_latin)},
            },
            "coverage": coverage,
            "gates_vs_f0": gates,
            "hsr_bootstrap_vs_f0": hsr_boot,
        }

        print(f"\n########## setting={setting} (ALL QUERIES) ##########")
        print(skillretbench.format_setting_arm_table({
            "F0": summary["settings"][setting]["all_queries"]["F0"]["metrics"],
            "R1-encoder": summary["settings"][setting]["all_queries"]["R1-encoder"]["metrics"],
        }))
        print(skillretbench.format_ir_alignment_table({
            "F0": summary["settings"][setting]["all_queries"]["F0"]["ir"],
            "R1-encoder": summary["settings"][setting]["all_queries"]["R1-encoder"]["ir"],
        }))
        print(skillretbench.format_coverage_table(coverage))
        print(skillretbench.format_gate_table(gates))
        print(format_hsr_bootstrap_table(hsr_boot))

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl_gz(args.jsonl, all_records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "corpus_report": corpus_report, "query_report": query_report, **summary,
    }, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"\nwrote {args.out}")
    print(f"wrote {args.jsonl}")


# --------------------------------------------------------------------------- main
def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encode")
    p_enc.add_argument("--force-any-python", action="store_true")
    p_enc.add_argument("--sample", type=int, default=0, help="only encode the first N skills/queries (dev)")
    p_enc.add_argument("--skill-batch-size", type=int, default=4,
                        help="Encoder batch_size for the long skill (description+full_text) texts")
    p_enc.add_argument("--skill-chunk-size", type=int, default=200,
                        help="how many skills per Encoder.encode() call (checkpoint granularity)")
    p_enc.set_defaults(fn=cmd_encode)

    p_run = sub.add_parser("run")
    p_run.add_argument("--sample", type=int, default=0, help="only run the first N cases (dev)")
    p_run.add_argument("--jsonl", type=Path, default=VALIDATION_DIR / "skillretbench-r1-encoder.jsonl.gz")
    p_run.add_argument("--out", type=Path, default=VALIDATION_DIR / "skillretbench-r1-encoder-summary.json")
    p_run.set_defaults(fn=cmd_run)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
