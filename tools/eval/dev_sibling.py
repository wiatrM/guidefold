#!/usr/bin/env python3
"""tools/eval/dev_sibling.py — Family F6: offline dense sibling map, evaluated on the frozen dev split
through the unchanged product path (DENSE-PROGRAM.md v2.2 §4; protocol in
docs/reports/bakeoff/DEV-F6-sibling-map-2026-09-06.md, registered before any run).

Offline (index time, no labels): from the zero-shot encoder's skill vectors, each skill's
same-taxonomy-leaf neighbours with cosine >= tau (top-N), symmetrised — the *sibling map* — and, per
sibling pair, the *discriminating terms* D_a = tokens(a) - tokens(b) over the card's five BM25F
fields. Query time (integer, no model, no vectors): after the product's own select(), if two
injected cards are siblings, the one whose discriminating terms the query matches less is removed
from the candidate list and select() is re-run (closure/abstention/cannot_fit stay the product's).
Ties never fire. Rule variants: "margin" (any difference) / "strict" (loser matches 0, winner >= 1).

This module never edits the CLI: `SiblingRouter` subclasses the product Router and overrides
select() only, the same discipline as tools/eval/dev_dense.py's dense-only router. numpy is needed
only to build the map from the cached int8 vectors (the CLI stays stdlib-only).
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import dev_sparse  # noqa: E402

VALIDATION_DIR = dev_sparse.VALIDATION_DIR
DENSE_CACHE_ROOT = EVAL_DIR / ".dev-dense-cache"
CONFIGS = {  # frozen in the protocol §2
    "F6-1": {"tau": 0.85, "n_max": 3, "rule": "margin"},
    "F6-2": {"tau": 0.80, "n_max": 3, "rule": "margin"},
    "F6-3": {"tau": 0.80, "n_max": 3, "rule": "strict"},
    "F6-4": {"tau": 0.75, "n_max": 5, "rule": "strict"},
}
PROXY_MAP = {"tau": 0.75, "n_max": 5}   # one fixed reference map for the exposure proxy, every arm
MAX_ITER = 4


# ------------------------------------------------------------------------- offline artefacts
def build_sibling_map(urns: list, vectors, leaf_of: dict, tau: float, n_max: int) -> dict:
    """{urn: [sibling urn, ...]} — same leaf, cosine >= tau, top-n_max by cosine, symmetrised.
    `vectors` is an (n, d) array aligned with `urns` (any scale: rows are normalised here)."""
    import numpy as np
    V = np.asarray(vectors, dtype=np.float32)
    V = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-9)
    by_leaf: dict = {}
    for i, u in enumerate(urns):
        by_leaf.setdefault(leaf_of[u], []).append(i)
    out: dict = {u: set() for u in urns}
    for leaf, idx in by_leaf.items():
        if len(idx) < 2:
            continue
        M = V[idx] @ V[idx].T
        np.fill_diagonal(M, -1.0)
        for r, i in enumerate(idx):
            js = [j for j in np.argsort(-M[r]) if M[r, j] >= tau][:n_max]
            for j in js:
                a, b = urns[i], urns[idx[j]]
                out[a].add(b)
                out[b].add(a)
    return {u: sorted(s) for u, s in out.items() if s}


def card_tokens(cli, card: dict) -> set:
    """The product tokenizer over the card's five BM25F fields (name, description, digest,
    triggers, body) — the vocabulary discriminating terms are drawn from."""
    parts = [card.get("name") or "", card.get("description") or "", card.get("digest") or "",
             " ".join(card.get("triggers") or []), card.get("_body") or card.get("body") or ""]
    return set(cli.tokenize(" ".join(parts)))


def make_sibling_router_class(cli):
    class SiblingRouter(cli.Router):
        """Product Router + the F6 query-time rule in select(); nothing else overridden."""

        def __init__(self, index, sibling_map: dict, token_sets: dict, rule: str = "margin",
                     max_iter: int = MAX_ITER):
            super().__init__(index)
            self.sibling_map = sibling_map
            self.token_sets = token_sets
            self.rule = rule
            self.max_iter = max_iter
            self.last_fired = 0
            self.last_removed: list = []

        def _loser(self, injected: list, qtok: set):
            urns = [c["urn"] for c in injected]
            for i in range(len(urns)):
                for j in range(i + 1, len(urns)):
                    a, b = urns[i], urns[j]
                    if b not in self.sibling_map.get(a, ()):
                        continue
                    ta, tb = self.token_sets.get(a, set()), self.token_sets.get(b, set())
                    ma, mb = len(qtok & (ta - tb)), len(qtok & (tb - ta))
                    if ma == mb:
                        continue                      # ties never fire
                    loser, m_l, m_w = (a, ma, mb) if ma < mb else (b, mb, ma)
                    if self.rule == "strict" and not (m_l == 0 and m_w >= 1):
                        continue
                    return loser
            return None

        def select(self, scored: list, k: int = 4, abstain_threshold=None, *, admissible: set,
                   query: str = "") -> list:
            self.last_fired, self.last_removed = 0, []
            qtok = set(cli.tokenize(query))
            scored = list(scored)
            injected = super().select(scored, k, abstain_threshold, admissible=admissible, query=query)
            for _ in range(self.max_iter):
                loser = self._loser(injected, qtok)
                if loser is None:
                    break
                self.last_fired += 1
                self.last_removed.append(loser)
                scored = [s for s in scored if s["urn"] != loser]
                injected = super().select(scored, k, abstain_threshold, admissible=admissible,
                                          query=query)
            return injected
    return SiblingRouter


def proxy_exposed(injected: list, gold: set, ref_map: dict) -> float:
    """1.0 if any non-gold injected card is a mapped sibling of a gold skill (fixed reference
    map): the 'right family, wrong representative' shape the HSR label isolates on test-B."""
    for u in injected:
        if u in gold:
            continue
        for g in gold:
            if u in ref_map.get(g, ()):
                return 1.0
    return 0.0


# ------------------------------------------------------------------------- dev run
def _load_e0_vectors(urns_needed: set):
    import numpy as np
    order = json.loads((DENSE_CACHE_ROOT / "E0" / "skill_order.json").read_text())
    V = np.load(DENSE_CACHE_ROOT / "E0" / "skill_vectors.i8.npy")
    missing = urns_needed - set(order)
    if missing:
        raise SystemExit(f"dev_sibling: {len(missing)} card urns missing from the E0 vector cache")
    return order, V


def _run_arm(router, cases, top_n=50):
    records = []
    for case in cases:
        rec = dev_sparse.run_product_case(router, case, top_n=top_n)
        rec["fired"] = getattr(router, "last_fired", 0)
        rec["removed"] = list(getattr(router, "last_removed", []))
        records.append(rec)
    return records


def cmd_run(args) -> int:
    t0 = time.time()
    import corpora as gf_corpora
    needs = gf_corpora.verify("skillret")
    if needs:
        print("skillret corpus not available:", needs[0], file=sys.stderr)
        return 1
    metrics = dev_sparse._load_metrics()
    cli = dev_sparse._load_cli()
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, _ = dev_sparse.corpus_to_cards(data["skills"])
    cases, _ = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    if args.limit:
        cases = cases[:args.limit]
    urns_all = list(cards)
    order, V = _load_e0_vectors(set(urns_all))
    row_of = {u: i for i, u in enumerate(order)}
    vec = V[[row_of[u] for u in urns_all]]
    leaf_of = {u: cards[u]["node"] for u in urns_all}
    token_sets = {u: card_tokens(cli, cards[u]) for u in urns_all}
    print(f"[{time.time()-t0:6.1f}s] cards={len(cards)} cases={len(cases)} token sets built",
          file=sys.stderr)

    maps: dict = {}
    def get_map(tau, n_max):
        key = (tau, n_max)
        if key not in maps:
            maps[key] = build_sibling_map(urns_all, vec, leaf_of, tau, n_max)
        return maps[key]
    ref_map = get_map(PROXY_MAP["tau"], PROXY_MAP["n_max"])
    print(f"[{time.time()-t0:6.1f}s] reference map: {len(ref_map)} skills with siblings, "
          f"{sum(len(v) for v in ref_map.values())//2} pairs", file=sys.stderr)

    index = cli.Index.from_cards(cards, nodes)
    arms = {"F0": cli.Router(index)}
    Sib = make_sibling_router_class(cli)
    for cid in args.configs:
        c = CONFIGS[cid]
        arms[cid] = Sib(index, get_map(c["tau"], c["n_max"]), token_sets, c["rule"])
    gold_of = {case["id"]: {r["urn"] for r in case["relevant"]} for case in cases}

    per_q: dict = {}
    records_by_arm: dict = {}
    firing: dict = {}
    for name, router in arms.items():
        recs = _run_arm(router, cases)
        ranked_by_qid = {r["query_id"]: r["ranked"] for r in recs}
        pq = dev_sparse.per_query_metrics(metrics, ranked_by_qid, cases)
        for case, rec in zip(cases, recs):
            pq[case["id"]]["all_required4_injected"] = metrics.all_required_at_k(rec["injected"], case, 4)
            pq[case["id"]]["proxy_exposed"] = proxy_exposed(rec["injected"], gold_of[case["id"]], ref_map)
        per_q[name] = pq
        records_by_arm[name] = recs
        firing[name] = {"queries_fired": sum(1 for r in recs if r["fired"]),
                        "replacements": sum(r["fired"] for r in recs),
                        "abstained": sum(1 for r in recs if r["abstained"])}
        if name != "F0":
            m = arms[name].sibling_map
            firing[name]["map_skills"] = len(m)
            firing[name]["map_pairs"] = sum(len(v) for v in m.values()) // 2
        print(f"[{time.time()-t0:6.1f}s] ran {name} {firing[name]}", file=sys.stderr)

    # F0 must be bit-identical to the recorded P-shipped run before any F6 number is read
    rec_path = VALIDATION_DIR / "dev-sparse-p-shipped.jsonl.gz"
    identical = None
    if rec_path.is_file() and not args.limit:
        recorded = {json.loads(l)["query_id"]: json.loads(l)["injected"]
                    for l in gzip.open(rec_path, "rt")}
        identical = all(recorded.get(r["query_id"]) == r["injected"] for r in records_by_arm["F0"])
        print(f"[{time.time()-t0:6.1f}s] F0 identical to recorded P-shipped: {identical}",
              file=sys.stderr)

    qids = [c["id"] for c in cases]
    by_k: dict = {}
    for c in cases:
        by_k.setdefault(c["k"], []).append(c["id"])
    breakdowns = {"overall": qids, **{f"k={k}": v for k, v in sorted(by_k.items())}}
    METRICS = ("hit1", "ndcg10", "recall10", "all_required4_injected", "proxy_exposed")
    summary: dict = {}
    for name in arms:
        summary[name] = {}
        for bd, ids in breakdowns.items():
            blk = {"n": len(ids)}
            for met in METRICS:
                vals = [per_q[name][q][met] for q in ids]
                blk[met] = sum(vals) / len(vals) if vals else float("nan")
            if name != "F0":
                blk["delta_vs_F0"] = {}
                for met in METRICS:
                    a, b = dev_sparse.paired_arrays(per_q["F0"], per_q[name], ids, met)
                    blk["delta_vs_F0"][met] = dev_sparse.bootstrap_paired_delta(a, b, seed=args.seed)
            summary[name][bd] = blk

    # selection rule (protocol §3)
    chosen, reason = None, "no configuration reduces the proxy"
    cands = []
    for cid in args.configs:
        o = summary[cid]["overall"]["delta_vs_F0"]
        ok = (o["all_required4_injected"]["delta"] >= -0.01) and (o["hit1"]["delta"] >= -0.01)
        red = -o["proxy_exposed"]["delta"]
        cands.append((cid, ok, red))
        if ok and red > 0:
            c = CONFIGS[cid]
            key = (red, c["tau"], -c["n_max"])
            if chosen is None or key > chosen[1]:
                chosen, reason = (cid, key), "largest proxy reduction within the no-harm tolerance"
    out = {"protocol": "docs/reports/bakeoff/DEV-F6-sibling-map-2026-09-06.md", "configs": CONFIGS,
           "proxy_map": PROXY_MAP, "n_cases": len(cases), "f0_identical_to_recorded": identical,
           "firing": firing, "summary": summary,
           "selection": {"candidates": cands, "chosen": chosen[0] if chosen else None, "reason": reason},
           "runtime_s": time.time() - t0}
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    for name, recs in records_by_arm.items():
        if name == "F0":
            continue
        dev_sparse.write_jsonl_gz(VALIDATION_DIR / f"dev-sibling-{name.lower()}.jsonl.gz",
                                  [{**r, "arm": name} for r in recs])
    out_path = Path(args.out) if args.out else VALIDATION_DIR / "dev-sibling-summary.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[{time.time()-t0:6.1f}s] wrote {out_path}", file=sys.stderr)
    cols = ("hit1", "ndcg10", "recall10", "all_required4_injected", "proxy_exposed")
    print(f"{'arm':<6}{'break':<9}" + "".join(f"{c:>24}" for c in cols))
    for name in arms:
        for bd in breakdowns:
            blk = summary[name][bd]
            row = f"{name:<6}{bd:<9}"
            for c in cols:
                v = blk[c]
                if name != "F0":
                    d = blk["delta_vs_F0"][c]
                    row += f"{v:8.4f} ({100*d['delta']:+5.1f}pp [{100*d['ci_lo']:+.1f},{100*d['ci_hi']:+.1f}])"
                else:
                    row += f"{v:>24.4f}"
            print(row)
    print("selection:", out["selection"])
    return 0


# ------------------------------------------------------------------------- test-B (SkillRetBench), once per frozen configuration
def cmd_testb(args) -> int:
    """One configuration on SkillRetBench through the unchanged product path (both node settings,
    as the R1 reference run did): F0 = B1 vs F6-<config>. HSR@4 (distractor_rate@4) is the gate of
    record here; hit@1 / nDCG@10 / all_required@4 are the no-harm guards. The sibling map is built
    from the corpus's own E0 skill vectors (tools/eval/.skillretbench-r1-cache, the R1 reference's
    cache) — no labels, exactly what an index-time build would do. Runs ONLY after the protocol's
    freeze/amendment decision; this function does not check that for you."""
    import skillretbench
    import skillretbench_r1
    import dense_ref
    t0 = time.time()
    cli = skillretbench._load_cli()
    metrics_mod = skillretbench._load_metrics()
    data, skills, cards, nodes, cases, corpus_report, query_report = skillretbench_r1._load_corpus()
    meta, row_of, skill_mat, query_vec_of = dense_ref.load_dense_cache(skillretbench_r1.CACHE_DIR)
    urns = list(cards)
    missing = [u for u in urns if u not in row_of]
    if missing:
        raise SystemExit(f"dev_sibling testb: {len(missing)} card urns missing from the test-B vector cache")
    vec = skill_mat[[row_of[u] for u in urns]]
    leaf_of = {u: cards[u]["node"] for u in urns}
    token_sets = {u: card_tokens(cli, cards[u]) for u in urns}
    cfg = CONFIGS[args.config]
    smap = build_sibling_map(urns, vec, leaf_of, cfg["tau"], cfg["n_max"])
    f0 = skillretbench.build_arms(cli, cards, nodes)["B1"]
    Sib = make_sibling_router_class(cli)
    f6 = Sib(f0.index, smap, token_sets, cfg["rule"])
    summary = {"header": {"corpus": "skillretbench", "config": args.config, "params": cfg,
                          "n_skills": len(cards), "n_cases": len(cases), "encoder": meta,
                          "map_skills": len(smap), "map_pairs": sum(len(v) for v in smap.values()) // 2,
                          "protocol": "docs/reports/bakeoff/DEV-F6-sibling-map-2026-09-06.md"},
               "settings": {}}
    all_records = []
    for setting in ("node_scoped", "node_root"):
        ret0, inj0, rec0 = skillretbench.run_arm(f0, cases, setting)
        ret6, inj6, rec6 = [], [], []
        fired_q, replacements = 0, 0
        for case in cases:
            rec = skillretbench.run_case(f6, case, setting)
            rec["fired"], rec["removed"] = f6.last_fired, list(f6.last_removed)
            fired_q += int(f6.last_fired > 0)
            replacements += f6.last_fired
            ret6.append(([e["urn"] for e in rec["retrieval"]], case))
            inj6.append((rec["injection"], case))
            rec6.append(rec)
        for r in rec0:
            r["arm"], r["node_key"] = "F0", setting
        for r in rec6:
            r["arm"], r["node_key"] = f"F6-{args.config}", setting
        all_records.extend(rec0)
        all_records.extend(rec6)
        gates = skillretbench.dense_vs_b1_gate_report(metrics_mod, cases, ret0, inj0, ret6, inj6,
                                                       k_cards=skillretbench_r1.K_CARDS,
                                                       n_resamples=skillretbench_r1.BOOTSTRAP_RESAMPLES)
        hsr = skillretbench_r1.hsr_bootstrap_report(metrics_mod, inj0, inj6)
        summary["settings"][setting] = {
            "F0": skillretbench_r1._per_setting_metrics(metrics_mod, ret0, inj0),
            "F6": skillretbench_r1._per_setting_metrics(metrics_mod, ret6, inj6),
            "gates_vs_F0": gates, "hsr_bootstrap": hsr,
            "firing": {"queries_fired": fired_q, "replacements": replacements},
        }
        print(f"[{time.time()-t0:6.1f}s] {setting}: fired on {fired_q} queries ({replacements} removals)",
              file=sys.stderr)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"skillretbench-f6-{args.config.lower()}"
    dev_sparse.write_jsonl_gz(VALIDATION_DIR / f"{stem}.jsonl.gz", all_records)
    (VALIDATION_DIR / f"{stem}-summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[{time.time()-t0:6.1f}s] wrote {stem}.jsonl.gz / -summary.json", file=sys.stderr)
    for setting, s in summary["settings"].items():
        h = s["hsr_bootstrap"].get("OVERALL") or {}
        print(f"{setting}: HSR@4 OVERALL delta={h.get('delta')} ci=[{h.get('ci_lo')}, {h.get('ci_hi')}] "
              f"fired={s['firing']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_run)
    b = sub.add_parser("testb", help="ONE configuration on SkillRetBench (once, per protocol)")
    b.add_argument("--config", required=True, choices=list(CONFIGS))
    b.set_defaults(func=cmd_testb)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
