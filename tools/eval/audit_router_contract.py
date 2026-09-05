#!/usr/bin/env python3
"""Portable CPU probes for router numerical and policy contracts, not retrieval quality.

Requires only the CLI's PyYAML dependency. Inspected worktrees are read-only.
Example: python tools/eval/audit_router_contract.py --compare-root ../gf-adr22 --out audit.json
Failing contracts are recorded in JSON rather than hidden behind an execution error.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import importlib.machinery
import importlib.util
import inspect
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace

def git(root, *args):
    return subprocess.run(["git", "-c", f"safe.directory={root}", *args], cwd=root,
                          text=True, capture_output=True, check=True).stdout.strip()

def inspect_root(root, revision=None):
    root = root.resolve()
    path = root / "skills/guidefold/scripts/guidefold"
    source_bytes = (subprocess.run(["git", "-c", f"safe.directory={root}", "show",
        f"{revision}:skills/guidefold/scripts/guidefold"], cwd=root, capture_output=True, check=True).stdout
        if revision else path.read_bytes())
    name = "router_audit_" + hashlib.sha256((str(root) + str(revision)).encode()).hexdigest()[:12]
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    cli = importlib.util.module_from_spec(spec)
    sys.modules[name] = cli
    exec(compile(source_bytes, str(path), 'exec'), cli.__dict__)
    scale = 1 << 20
    # Hand-controlled statistics isolate fixed-point units from tokenizer/index construction.
    idx = SimpleNamespace(IDF_SCALE=scale, K1=1.2, FIELDS=("name",),
        weights={"field.name": 6}, postings={"name": {"auth": {"a": 1, "b": 10, "c": 100}}},
        field_norm={"name": {u: scale for u in "abc"}}, idf={"auth": scale})
    actual = cli.Router(idx)._bm25_scores("auth", set("abc"))
    reference = {u: 6 * tf / (1.2 + 6 * tf) for u, tf in zip("abc", (1, 10, 100))}
    errors = {u: abs(actual[u] / scale - reference[u]) for u in "abc"}
    bm25 = {"tf": [1, 10, 100], "idf": 1.0, "field_weight": 6, "field_normalization": 1.0,
        "integer_scale": scale, "actual_integer_scores": actual, "reference_float_scores": reference,
        "absolute_errors_after_unscaling": errors, "passes_reference_tolerance": max(errors.values()) < 1e-5}
    # Direct cosine is an independent reference; numerical ties are excluded.
    dense = {"historical_counterexample": cli._dense_rank({"A": (3, 9), "B": (1, 2)}),
             "expected_counterexample_order": ["A", "B"]}
    rng = random.Random(42)
    checked = violations = 0
    for _ in range(1000):
        q, a, b = [[rng.randrange(-10, 11) for _ in range(4)] for _ in range(3)]
        da, db = sum(x*y for x,y in zip(q,a)), sum(x*y for x,y in zip(q,b))
        na, nb = sum(x*x for x in a), sum(x*x for x in b)
        ca, cb = (da/math.sqrt(na) if na else 0), (db/math.sqrt(nb) if nb else 0)
        if abs(ca-cb) < 1e-10:
            continue
        expected = ["A","B"] if ca > cb else ["B","A"]
        checked += 1
        violations += cli._dense_rank({"A": (da,na), "B": (db,nb)}) != expected
    dense.update(tested_nontied_pairs=checked, violations=violations)
    def _direct_select(router, seed):
    """After ADR-0022 the parameter is mandatory: a direct call without it must be rejected,
    not silently fall back to a weaker policy. Record which of the two happened."""
    try:
        return router.select(seed, k=4)
    except TypeError as e:
        return {"rejected": True, "error": str(e)}


def card(urn, node, negative=()):
        return {"urn": urn, "node": node, "name": urn, "description": "",
                "status": "active", "negative_triggers": list(negative)}
    weights = {**cli.Index.DEFAULT_WEIGHTS, "w_dense": 0, "w_scope": 0, "w_ppr": 0}
    di = cli.Index({"A": card("A","a"), "B": card("B","a")}, {"_root": {}, "a": {}}, weights)
    di.word_vectors = {"quasar": (1,0)}
    di.skill_vectors, di.skill_normsq = {"A": (1,0), "B": (0,1)}, {"A": 1, "B": 1}
    router = cli.Router(di)
    candidates = router.candidates("quasar", "a")
    disabled = {"weight": 0, "candidates_with_nonempty_table": candidates,
                "scored_with_nonempty_table": router.score(candidates, "quasar", "a")}
    di.word_vectors = {}
    disabled["candidates_with_empty_table"] = router.candidates("quasar", "a")
    disabled["passes_no_channel_contribution"] = not candidates
    pi = cli.Index({"A": card("A","a"), "NEG": card("NEG","a",["forbidden"]),
        "SIB": card("SIB","b")}, {"_root": {}, "a": {}, "b": {}}, weights)
    pi.graph["requires"] = {"A": ["NEG","SIB"]}
    pi.idf = {"quasar": scale}
    pi.postings["name"] = {"quasar": {"A": 1}}
    pi.field_norm["name"] = {"A": scale}
    router = cli.Router(pi)
    eligible, drops = router.policy_filter("a", "forbidden quasar")
    selected = router.route("forbidden quasar", "a", k=4)
    leaked = [c["urn"] for c in selected if c["urn"] not in eligible]
    # Keep the direct-call compatibility boundary separate from the production route.
    seed = [{"urn": "A", "node": "a", "score": 20000, "bm25_rank": 1, "dense_rank": None}]
    policy = {"eligible": eligible, "drops": drops, "route_selected": selected,
        "route_excluded_reintroduced": leaked, "passes_route_eligibility": not leaked,
        "direct_select_without_admissible": _direct_select(router, seed),
        "select_accepts_admissible": "admissible" in inspect.signature(router.select).parameters}
    return {"root": str(root), "git_head": git(root,"rev-parse","HEAD"),
        "source_kind": "git_revision" if revision else "working_tree",
        "source_revision": git(root, "rev-parse", revision) if revision else None,
        "cli_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "tracked_cli_diff": "" if revision else git(root,"diff","HEAD","--","skills/guidefold/scripts/guidefold"),
        "cli_is_dirty": False if revision else bool(git(root,"status","--porcelain","--","skills/guidefold/scripts/guidefold")),
        "bm25_units": bm25, "dense_cosine": dense, "zero_weight_dense": disabled,
        "dependency_eligibility": policy}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--baseline-ref", help="Read the baseline CLI directly from this git revision.")
    parser.add_argument("--compare-root", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = {"schema_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "purpose": "CPU contract audit; not retrieval quality or holdout evaluation.",
        "comparison_status": "Dirty worktree results describe proposed fixes, not landed changes.",
        "baseline": inspect_root(args.root, args.baseline_ref), "comparisons": [inspect_root(r) for r in args.compare_root]}
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())

