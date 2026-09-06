#!/usr/bin/env python3
"""tools/authoring/collision_report.py — authoring loop, part 1, deliverable #1
(docs/MVP.md §5 "3-6 authoring loop": "a per-PR collision report — 'this description takes N dev
queries from skill X'").

Search quality is 80% the quality of what is searched. A new or edited skill description can
silently steal queries from a sibling in the same node — that is the HSR@4 failure the E7.5 gate
catches *after* the fact. This script shows a skill author, in the PR, *before* merge, what their
text does to retrieval and injection. Nothing here is auto-applied; nothing here gates the build
(that is E7.5's separate, later gate) — it only informs.

Method — never a second ranking implementation:
    1. Build two independent `Index` snapshots via `git archive` (base ref, head ref) into a temp
       dir, never the working tree (`tools/authoring/_snapshot.py`).
    2. Run every query through the *exact* product path on both snapshots, replicated stage by
       stage exactly as `tools/eval/run_golden.py.run_cases` does:
           policy_filter -> candidates -> score -> select(admissible=...)
       keeping RETRIEVAL (`Router.score` order — ranking quality) and INJECTION (the <=k cards
       `Router.select` emits — what the agent actually receives) apart. Conflating the two
       understated hit@1 by ~64 points before it was caught (PR #9) — this script must not repeat
       that.
    3. Diff the two snapshots' cards (`_snapshot.diff_cards`) and the two runs' injection sets per
       query, and report: which queries flipped top-k; for each changed/new skill, which sibling
       queries it took or lost (same-node pairs only — the HSR proxy); which new/changed skills
       are exposed by *zero* queries; and, when the queries file carries graded labels (the golden
       format), paired Δhit@1 / Δall_required@k / Δdistractor_rate@k with a 95% CI
       (`tools/eval/metrics.paired_delta_ci` — otherwise "unlabelled: exposure changes only".

Usage:
    python3 tools/authoring/collision_report.py --root <consumer root> --base <ref> --head <ref> \\
        --queries tests/golden/*.yaml [--k 4] [--json out.json] [--md out.md]

    --queries is optional: omit it (or point a consumer's `guidefold.yaml` at nothing under
    `eval.queries` — see `templates/ci.yml`) to fall back to exposure-only mode, whose synthetic
    query set is the union of the skills' own `triggers` phrases.

Deterministic, stdlib + PyYAML only. Runs in seconds on the Meridian fixture (26 skills).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import yaml

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
import _snapshot as snap  # noqa: E402  (sibling-script import, same idiom as tools/enrich/derive.py's tokenizer import)

REPO_ROOT = snap.REPO_ROOT


def load_metrics_module():
    spec = importlib.util.spec_from_file_location(
        "gf_authoring_metrics", REPO_ROOT / "tools" / "eval" / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------- query loading
def _stem_id(path, i: int) -> str:
    return f"{Path(path).stem}-{i:04d}"


def load_queries_from_files(paths: list) -> tuple:
    """Golden-format YAML (a mapping with a top-level `cases` list, `tests/golden/*.yaml`'s own
    shape) or a bare list of query strings/dicts. Returns (cases, labelled) — labelled is True the
    moment any case carries `relevant` or `distractors`, which is what unlocks the Δmetric/CI
    section of the report."""
    cases = []
    labelled = False
    for p in paths:
        doc = yaml.safe_load(Path(p).read_text())
        if isinstance(doc, dict) and "cases" in doc:
            category = doc.get("category")
            for i, c in enumerate(doc["cases"] or []):
                c = dict(c)
                c.setdefault("category", category)
                c.setdefault("id", _stem_id(p, i))
                c.setdefault("node", "_root")
                if c.get("relevant") or c.get("distractors"):
                    labelled = True
                cases.append(c)
        elif isinstance(doc, list):
            for i, item in enumerate(doc):
                if isinstance(item, str):
                    cases.append({"id": _stem_id(p, i), "query": item, "node": "_root"})
                elif isinstance(item, dict):
                    c = dict(item)
                    c.setdefault("id", _stem_id(p, i))
                    c.setdefault("node", "_root")
                    if c.get("relevant") or c.get("distractors"):
                        labelled = True
                    cases.append(c)
                else:
                    raise SystemExit(f"collision_report: cannot parse entry {i} of {p}")
        else:
            raise SystemExit(
                f"collision_report: cannot parse queries file {p} "
                "(expected a golden-format mapping with a 'cases' key, or a list of queries)")
    _dedupe_ids(cases)
    return cases, labelled


def _dedupe_ids(cases: list) -> None:
    seen = set()
    for c in cases:
        base_id = c["id"]
        cid, n = base_id, 1
        while cid in seen:
            n += 1
            cid = f"{base_id}-{n}"
        c["id"] = cid
        seen.add(cid)


def derive_unlabelled_queries(*indexes) -> tuple:
    """No --queries given: fall back to the skills' own `triggers` phrases (union across every
    snapshot passed in, so a skill only present on one side is still tested) as the query set — a
    skill with no triggers at all falls back to the first 8 words of its description so it is
    still exercised. Same "unlabelled: exposure changes only" mode `templates/ci.yml` documents for
    a consumer with no `eval.queries` key."""
    seen = set()
    queries = []
    for idx in indexes:
        for u in sorted(idx.cards.keys()):
            c = idx.cards[u]
            phrases = list(c.get("triggers") or [])
            if not phrases:
                words = (c.get("description") or "").split()
                if words:
                    phrases = [" ".join(words[:8])]
            for phrase in phrases:
                key = phrase.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                queries.append({"query": phrase, "node": "_root"})
    for i, q in enumerate(queries):
        q["id"] = f"trig{i:04d}"
    return queries, False


# --------------------------------------------------------------------------------- product path
def route_one(router, query: dict, k: int) -> tuple:
    """Exactly `run_golden.py.run_cases`'s per-case body, stage by stage — never `Router.route()`,
    which would collapse retrieval and injection into one list."""
    q, node = query["query"], query.get("node") or "_root"
    cands = router.candidates(q, node)
    scored = router.score(cands, q, node)
    admissible, _ = router.policy_filter(node, q)
    injected = router.select(scored, k=k, admissible=set(admissible), query=q)
    retrieval = [c["urn"] for c in scored]
    injection = [c["urn"] for c in injected]
    return retrieval, injection


def run_queries(router, queries: list, k: int) -> dict:
    """qid -> {"retrieval": [...], "injection": [...], "case": <the case dict>}"""
    out = {}
    for q in queries:
        retrieval, injection = route_one(router, q, k)
        out[q["id"]] = {"retrieval": retrieval, "injection": injection, "case": q}
    return out


# --------------------------------------------------------------------------------- report core
def compute_metric_deltas(metrics_mod, queries: list, base_runs: dict, head_runs: dict, k: int) -> dict:
    """Δhit@1 (retrieval order), Δall_required@k and Δdistractor_rate@k (injection order — the
    metric that "answers the whole instruction bundle", `metrics.py`'s own docstring on
    `all_required_at_k`), paired on query id, each with a 95% CI (`metrics.paired_delta_ci`).

    Deliberate divergence from `run_golden.py`: that script reports the *overall* `all_required@4`
    from RETRIEVAL (a historical choice, unchanged there). Here it is read from INJECTION, because
    a collision report's job is "did this PR change what the agent actually receives" — the
    all_required@k docstring calls that "the completeness the product actually promises". Both
    scripts remain independently correct for what each answers.
    """
    hit_pairs, allreq_pairs, distr_pairs = [], [], []
    for q in queries:
        qid = q["id"]
        if not (q.get("relevant") or q.get("distractors")):
            continue
        if metrics_mod.is_abstention_case(q):
            continue
        b_ret, h_ret = base_runs[qid]["retrieval"], head_runs[qid]["retrieval"]
        if b_ret and h_ret:
            hit_pairs.append((metrics_mod.hit_at_1(b_ret, q), metrics_mod.hit_at_1(h_ret, q)))
        b_inj, h_inj = base_runs[qid]["injection"], head_runs[qid]["injection"]
        ar_b, ar_h = metrics_mod.all_required_at_k(b_inj, q, k), metrics_mod.all_required_at_k(h_inj, q, k)
        if not (math.isnan(ar_b) or math.isnan(ar_h)):
            allreq_pairs.append((ar_b, ar_h))
        dr_b, dr_h = metrics_mod.distractor_rate(b_inj, q, k), metrics_mod.distractor_rate(h_inj, q, k)
        if not (math.isnan(dr_b) or math.isnan(dr_h)):
            distr_pairs.append((dr_b, dr_h))
    return {
        "hit@1": metrics_mod.paired_delta_ci(hit_pairs),
        f"all_required@{k}": metrics_mod.paired_delta_ci(allreq_pairs),
        f"distractor_rate@{k}": metrics_mod.paired_delta_ci(distr_pairs),
    }


def compute_report(cli, metrics_mod, base_idx, head_idx, queries: list, labelled: bool, k: int = 4) -> dict:
    """The pure(ish) core: everything past this point depends only on two already-built `Index`
    objects (from `Index.build` or `Index.from_cards` — tests use the latter with a tiny synthetic
    corpus, no git and no filesystem tree needed) and a query list, so it is unit-testable without
    ever shelling out to git.

    Collision/gain/loss bookkeeping is deliberately read from RETRIEVAL (`Router.score` order,
    truncated to top-k), not injection. Two same-node siblings that both already fit inside
    `select`'s k=4 cap can swap RANK (which one a developer sees listed first, which one wins
    Hit@1) with the *injected set* staying byte-identical — injection order is a presentation
    decision (general -> specific), not a ranking signal (see `run_golden.py`'s retrieval-vs-
    injection docstring). A collision report whose whole job is "did this text change make the
    router prefer a different skill" must be sensitive to that swap, so top-k here means the
    ordered retrieval list, and a "takeover" is a pairwise rank inversion between two same-node
    urns, not a change in set membership. `never_exposed`, below, is the one place injection is
    still the right signal — it asks the different, product-facing question "does the agent ever
    actually receive this card"."""
    added, removed, changed = snap.diff_cards(base_idx, head_idx)

    def node_of(u):
        c = head_idx.cards.get(u) or base_idx.cards.get(u)
        return c.get("node") if c else None

    base_router, head_router = cli.Router(base_idx), cli.Router(head_idx)
    base_runs = run_queries(base_router, queries, k)
    head_runs = run_queries(head_router, queries, k)

    worse = k + 1   # placeholder rank for "outside top-k" -- worse than any real in-top-k rank
    changed_qids = []
    gained_qids = defaultdict(set)   # urn -> {qid, ...} rank improved (entered top-k or beat a sibling)
    lost_qids = defaultdict(set)     # urn -> {qid, ...} rank worsened (left top-k or beaten by a sibling)
    sibling_takes = defaultdict(lambda: defaultdict(list))  # winner -> victim -> [qid, ...] (same node — HSR proxy)
    for q in queries:
        qid = q["id"]
        br = base_runs[qid]["retrieval"][:k]
        hr = head_runs[qid]["retrieval"][:k]
        if br == hr:
            continue
        changed_qids.append(qid)
        base_rank = {u: i + 1 for i, u in enumerate(br)}
        head_rank = {u: i + 1 for i, u in enumerate(hr)}
        for g in sorted(set(hr) - set(br)):
            gained_qids[g].add(qid)
        for l in sorted(set(br) - set(hr)):
            lost_qids[l].add(qid)
        pool = set(br) | set(hr)
        for g in sorted(pool):
            for l in sorted(pool):
                if g == l or node_of(g) is None or node_of(g) != node_of(l):
                    continue
                bg, bl = base_rank.get(g, worse), base_rank.get(l, worse)
                hg, hl = head_rank.get(g, worse), head_rank.get(l, worse)
                if bg > bl and hg < hl:   # g used to trail l; now leads it -- a takeover on this query
                    sibling_takes[g][l].append(qid)
                    gained_qids[g].add(qid)
                    lost_qids[l].add(qid)

    # "never exposed" is the one place injection (the <=k cards the agent actually receives) is the
    # right signal, not retrieval rank -- a skill can rank respectably and still never be selected.
    head_injection_total = defaultdict(int)
    for run in head_runs.values():
        for u in run["injection"]:
            head_injection_total[u] += 1
    never_exposed = sorted(u for u in (added | changed) if head_injection_total.get(u, 0) == 0)
    never_exposed_set = set(never_exposed)

    sibling_collisions = []
    for winner, victims in sibling_takes.items():
        for victim, qids in victims.items():
            sibling_collisions.append({
                "winner": winner, "victim": victim, "node": node_of(winner),
                "n_queries": len(qids), "query_ids": sorted(qids),
            })
    sibling_collisions.sort(key=lambda r: (-r["n_queries"], r["winner"], r["victim"]))

    per_skill = {}
    for urn in sorted(added | changed | removed):
        g_qids, l_qids = sorted(gained_qids.get(urn, ())), sorted(lost_qids.get(urn, ()))
        takes = {victim: sorted(qids) for victim, qids in sibling_takes.get(urn, {}).items()}
        attributed_gain = {q for qids in takes.values() for q in qids}
        loses_to = {winner: sorted(victims[urn]) for winner, victims in sibling_takes.items() if urn in victims}
        attributed_loss = {q for qids in loses_to.values() for q in qids}
        per_skill[urn] = {
            "status": "new" if urn in added else ("removed" if urn in removed else "changed"),
            "node": node_of(urn),
            "gains_total": len(g_qids), "gains_query_ids": g_qids,
            "loses_total": len(l_qids), "loses_query_ids": l_qids,
            "takes_from": takes, "loses_to": loses_to,
            "newly_exposed_query_ids": sorted(q for q in g_qids if q not in attributed_gain),
            "newly_hidden_query_ids": sorted(q for q in l_qids if q not in attributed_loss),
            "never_exposed": urn in never_exposed_set,
        }

    report = {
        "k": k, "labelled": labelled, "n_queries": len(queries),
        "n_changed_queries": len(changed_qids), "changed_query_ids": sorted(changed_qids),
        "added": sorted(added), "removed": sorted(removed), "changed": sorted(changed),
        "sibling_collisions": sibling_collisions,
        "per_skill": per_skill,
        "never_exposed": never_exposed,
        "metrics": compute_metric_deltas(metrics_mod, queries, base_runs, head_runs, k) if labelled else None,
    }
    return report


# --------------------------------------------------------------------------------- rendering
def _sample(qids: list, cap: int = 8) -> str:
    return ", ".join(qids[:cap]) + (" ..." if len(qids) > cap else "")


def render_markdown(report: dict) -> str:
    L = []
    L.append("## Skill authoring report — collisions & exposure")
    L.append("")
    mode = "labelled (golden format)" if report["labelled"] else "unlabelled: exposure changes only"
    L.append(f"k={report['k']} · queries={report['n_queries']} ({mode}) · "
              f"top-k changed on {report['n_changed_queries']} / {report['n_queries']} queries")
    L.append("")
    L.append(f"Cards: +{len(report['added'])} new, ~{len(report['changed'])} changed, "
              f"-{len(report['removed'])} removed")
    L.append("")
    L.append("### Sibling collisions (same-node — the HSR proxy)")
    if report["sibling_collisions"]:
        L.append("")
        L.append("| Winner | Victim | Node | Queries taken | Sample query ids |")
        L.append("|---|---|---|---|---|")
        for row in report["sibling_collisions"]:
            L.append(f"| `{row['winner']}` | `{row['victim']}` | {row['node']} | "
                      f"{row['n_queries']} | {_sample(row['query_ids'])} |")
    else:
        L.append("")
        L.append("No same-node sibling collisions detected.")
    L.append("")
    L.append("### Per-skill exposure changes")
    if not report["per_skill"]:
        L.append("")
        L.append("No skill cards changed between base and head.")
    for urn in sorted(report["per_skill"]):
        info = report["per_skill"][urn]
        L.append("")
        L.append(f"#### `{urn}` ({info['status']}, node `{info['node']}`)")
        if info["never_exposed"]:
            L.append("- **never exposed — check description/triggers**")
            continue
        if info["gains_total"]:
            plural = "query" if info["gains_total"] == 1 else "queries"
            L.append(f"- gains {info['gains_total']} {plural} ({_sample(info['gains_query_ids'])})")
            for victim, qids in sorted(info["takes_from"].items()):
                L.append(f"  - takes {len(qids)} from `{victim}` ({_sample(qids)})")
            if info["newly_exposed_query_ids"]:
                L.append(f"  - newly exposed on {len(info['newly_exposed_query_ids'])} "
                          f"({_sample(info['newly_exposed_query_ids'])})")
        if info["loses_total"]:
            plural = "query" if info["loses_total"] == 1 else "queries"
            L.append(f"- loses {info['loses_total']} {plural} ({_sample(info['loses_query_ids'])})")
            for winner, qids in sorted(info["loses_to"].items()):
                L.append(f"  - loses {len(qids)} to `{winner}` ({_sample(qids)})")
            if info["newly_hidden_query_ids"]:
                L.append(f"  - newly hidden on {len(info['newly_hidden_query_ids'])} "
                          f"({_sample(info['newly_hidden_query_ids'])})")
        if not info["gains_total"] and not info["loses_total"]:
            L.append("- no exposure change on this query set")
    L.append("")
    L.append("### Retrieval-quality deltas")
    if report["metrics"] is None:
        L.append("")
        L.append("unlabelled: exposure changes only (queries file has no graded `relevant`/`distractors`)")
    else:
        L.append("")
        L.append("| Metric | n | base | head | Δ | 95% CI |")
        L.append("|---|---|---|---|---|---|")
        for name, stats in report["metrics"].items():
            if stats["n"] == 0:
                L.append(f"| {name} | 0 | — | — | — | no graded cases |")
                continue
            L.append(f"| {name} | {stats['n']} | {stats['mean_base']:.3f} | {stats['mean_head']:.3f} | "
                      f"{stats['mean_delta']:+.3f} | [{stats['ci_lo']:+.3f}, {stats['ci_hi']:+.3f}] |")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="consumer monorepo root (nearest ancestor of guidefold.yaml)")
    ap.add_argument("--base", required=True, help="git ref: before")
    ap.add_argument("--head", required=True, help="git ref: after")
    ap.add_argument("--queries", nargs="+", default=None,
                     help="golden-format YAML file(s), e.g. tests/golden/*.yaml; omit for "
                          "unlabelled exposure-only mode using the skills' own triggers")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--json", default=None, help="write the machine-readable report here")
    ap.add_argument("--md", default=None, help="write the markdown report here")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    repo_root = snap.git_toplevel(root)
    rel_root = snap.rel_root_of(root, repo_root)
    cli_path = snap.find_cli_path(repo_root)
    cli = snap.load_cli(cli_path)
    metrics_mod = load_metrics_module()

    with tempfile.TemporaryDirectory(prefix="guidefold-collision-") as tmp:
        work = Path(tmp)
        _, base_idx = snap.build_snapshot_index(cli, repo_root, rel_root, args.base, work)
        _, head_idx = snap.build_snapshot_index(cli, repo_root, rel_root, args.head, work)

    if args.queries:
        queries, labelled = load_queries_from_files(args.queries)
    else:
        queries, labelled = derive_unlabelled_queries(head_idx, base_idx)

    report = compute_report(cli, metrics_mod, base_idx, head_idx, queries, labelled, k=args.k)
    markdown = render_markdown(report)
    print(markdown)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.md:
        Path(args.md).write_text(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
