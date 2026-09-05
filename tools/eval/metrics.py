"""Ranking metrics for the Guidefold golden set (MVP story E1.2).

Pure functions over `(ranked_urns, case)`. No I/O, no router, no config — so that the metric
definitions can be reviewed and tested on their own, and so that every consumer (the CI runner,
the bake-off report, the future Routing.Eval screen) computes the *same* numbers.

Relevance grades in the golden set (see `tests/golden/README.md`):

    3  must appear at rank 1
    2  must appear in the top 8
    1  acceptable, neither required nor penalised

Two conventions are load-bearing and are stated here rather than buried in the code:

*   **A distractor is not merely "not relevant".** The golden set names distractors explicitly
    because they are the plausible wrong answers. They are scored separately (`distractor_rate`)
    rather than folded into the ranking metrics, because "the router put a plausible-but-wrong
    skill in front of a developer" is a different failure from "the router missed a good one".

*   **Abstention is a first-class answer.** An empty ranking is correct for a `no_applicable`
    case and wrong everywhere else. Ranking metrics therefore ignore abstained queries entirely
    (an abstention is not a Hit@1 of 0), and abstention is reported on its own axis. Folding the
    two together lets a router look good by never answering, which is precisely the failure mode
    the `no_applicable` stratum exists to catch.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

MUST_BE_FIRST = 3
MUST_BE_IN_TOP_K = 2


# ----------------------------------------------------------------- case helpers
def graded(case: Mapping) -> dict[str, int]:
    """urn -> grade for every relevant item of a case."""
    return {r["urn"]: int(r["grade"]) for r in case.get("relevant") or []}


def distractors(case: Mapping) -> set[str]:
    return {d["urn"] for d in case.get("distractors") or []}


def is_abstention_case(case: Mapping) -> bool:
    """True when the correct behaviour is to return nothing."""
    return not (case.get("relevant") or [])


# ----------------------------------------------------------------- ranking metrics
def hit_at_1(ranked: Sequence[str], case: Mapping) -> float:
    """1.0 when rank 1 is a relevant skill of grade >= 2.

    Grade-1 items are "acceptable", so putting one first is neither rewarded nor punished here;
    it simply is not a hit. An empty ranking scores 0 only if the caller decided this case was
    answerable — see `evaluate`, which excludes abstentions instead.
    """
    if not ranked:
        return 0.0
    return 1.0 if graded(case).get(ranked[0], 0) >= MUST_BE_IN_TOP_K else 0.0


def recall_at_k(ranked: Sequence[str], case: Mapping, k: int = 8) -> float:
    """Fraction of the case's grade>=2 skills that appear in the top k.

    Grade-1 items are excluded from the denominator: they are acceptable, not required, so
    missing one must not be counted as a miss.
    """
    required = {u for u, g in graded(case).items() if g >= MUST_BE_IN_TOP_K}
    if not required:
        return float("nan")           # undefined for abstention cases; caller filters these out
    return len(required & set(ranked[:k])) / len(required)


def ndcg_at_k(ranked: Sequence[str], case: Mapping, k: int = 10) -> float:
    """Graded nDCG with the standard exponential gain, 2**g - 1, and log2(rank+1) discount.

    Exponential gain is the right choice here because the grades are not a linear scale: a
    must-be-first skill is worth much more than an acceptable one, not three times as much.
    """
    rel = graded(case)
    if not rel:
        return float("nan")
    dcg = sum(
        (2 ** rel.get(u, 0) - 1) / math.log2(i + 2)
        for i, u in enumerate(ranked[:k])
    )
    ideal = sum(
        (2 ** g - 1) / math.log2(i + 2)
        for i, g in enumerate(sorted(rel.values(), reverse=True)[:k])
    )
    return dcg / ideal if ideal else float("nan")


def completeness_at_k(ranked: Sequence[str], case: Mapping, k: int = 4) -> float:
    """1.0 only when every grade-3 skill of the case is inside the top k.

    **Read this before quoting it.** On the current golden set every answerable case has exactly
    one grade-3 skill, so this metric collapses to "is the primary skill in the top k". It does
    NOT check the grade-2 companions the golden README defines as *required* (e.g. a `requires`
    dependency). The E1.3 peer review measured the gap: B1 multi_skill reads 95.45 % here but
    74.24 % once companions are required. Kept, unchanged, as the historical series; the metric
    that answers "did the agent receive the whole answer" is `all_required_at_k` below.
    """
    must = {u for u, g in graded(case).items() if g >= MUST_BE_FIRST}
    if not must:
        return float("nan")
    return 1.0 if must <= set(ranked[:k]) else 0.0


def all_required_at_k(ranked: Sequence[str], case: Mapping, k: int = 4) -> float:
    """1.0 only when EVERY required skill (grade >= 2) is inside the top k.

    Grade 2 is "a required companion" per tests/golden/README.md, so this is the completeness
    the product actually promises: the whole instruction bundle, not just its headline. This is
    the metric SkillRouter calls FC@K and Graph-of-Skills evaluates bundles on. Expect it to be
    materially lower than `completeness_at_k`; that difference is the product gap, not noise.
    """
    required = {u for u, g in graded(case).items() if g >= MUST_BE_IN_TOP_K}
    if not required:
        return float("nan")
    return 1.0 if required <= set(ranked[:k]) else 0.0


def distractor_rate(ranked: Sequence[str], case: Mapping, k: int = 4) -> float:
    """1.0 when any named distractor made it into the top k. Lower is better; target is 0."""
    d = distractors(case)
    if not d:
        return float("nan")
    return 1.0 if d & set(ranked[:k]) else 0.0


# ----------------------------------------------------------------- abstention
def abstention_counts(ranked: Sequence[str], case: Mapping) -> tuple[int, int, int, int]:
    """(tp, fp, fn, tn) treating "the router returned nothing" as the positive class.

    tp  correctly said nothing on a no-applicable case
    fp  said nothing when there was a real answer   <- the expensive error
    fn  answered a no-applicable case               <- the noisy error
    tn  answered an answerable case
    """
    abstained = not ranked
    should = is_abstention_case(case)
    return (
        int(abstained and should),
        int(abstained and not should),
        int(not abstained and should),
        int(not abstained and not should),
    )


# ----------------------------------------------------------------- aggregation
def _mean(xs: Iterable[float]) -> float:
    vals = [x for x in xs if not math.isnan(x)]
    return sum(vals) / len(vals) if vals else float("nan")


def evaluate(results: Sequence[tuple[Sequence[str], Mapping]], k_cards: int = 4) -> dict:
    """Aggregate every metric over `(ranked_urns, case)` pairs.

    Ranking metrics are macro-averaged over the cases where they are defined, and **abstained
    queries are excluded from them** — an abstention is scored on the abstention axis, not as a
    ranking failure. That keeps the two axes independent, so a router cannot buy Hit@1 by
    answering everything, nor abstention precision by answering nothing.
    """
    tp = fp = fn = tn = 0
    answerable = [(r, c) for r, c in results if not is_abstention_case(c)]
    answered = [(r, c) for r, c in answerable if r]

    for ranked, case in results:
        a, b, c_, d = abstention_counts(ranked, case)
        tp += a; fp += b; fn += c_; tn += d

    out = {
        "n": len(results),
        "n_answerable": len(answerable),
        "n_answered": len(answered),
        "hit@1": _mean(hit_at_1(r, c) for r, c in answered),
        "recall@8": _mean(recall_at_k(r, c, 8) for r, c in answered),
        "ndcg@10": _mean(ndcg_at_k(r, c, 10) for r, c in answered),
        f"completeness@{k_cards}": _mean(completeness_at_k(r, c, k_cards) for r, c in answered),
        f"all_required@{k_cards}": _mean(all_required_at_k(r, c, k_cards) for r, c in answered),
        f"distractor_rate@{k_cards}": _mean(distractor_rate(r, c, k_cards) for r, c in results if r),
        "abstention_precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "abstention_recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "coverage": len(answered) / len(answerable) if answerable else float("nan"),
    }
    return out


def by_category(results: Sequence[tuple[Sequence[str], Mapping]], k_cards: int = 4) -> dict[str, dict]:
    """Per-stratum breakdown. A single overall number hides exactly the regressions that matter:
    a change can lift `simple` while destroying `sibling_ambiguity` and look flat overall."""
    buckets: dict[str, list] = {}
    for ranked, case in results:
        buckets.setdefault(case.get("category", "unknown"), []).append((ranked, case))
    return {cat: evaluate(rs, k_cards) for cat, rs in sorted(buckets.items())}


def format_table(overall: Mapping, per_cat: Mapping[str, Mapping]) -> str:
    """Fixed-width table for the committed per-run results file (E1.2 acceptance)."""
    cols = ["n", "hit@1", "recall@8", "ndcg@10", "completeness@4", "all_required@4",
            "distractor_rate@4", "abstention_precision"]
    head = f"{'stratum':<20}" + "".join(f"{c:>22}" for c in cols)
    lines = [head, "-" * len(head)]
    for name, m in list(per_cat.items()) + [("OVERALL", overall)]:
        row = f"{name:<20}"
        for c in cols:
            v = m.get(c, float("nan"))
            row += f"{v:>22}" if isinstance(v, int) else (
                f"{'—':>22}" if isinstance(v, float) and math.isnan(v) else f"{v:>22.4f}")
        lines.append(row)
    return "\n".join(lines)


# ----------------------------------------------------------------- paired comparison (authoring loop)
def paired_delta_ci(pairs: Sequence[tuple[float, float]], z: float = 1.96) -> dict:
    """Paired base-vs-head comparison over the *same* query ids run through two Router snapshots
    (tools/authoring/collision_report.py: base ref vs head ref of a skill-authoring PR).

    Returns n, mean_base, mean_head, mean_delta (= mean_head - mean_base) and a 95 % CI on
    mean_delta via the normal approximation on the per-case deltas (mean +/- z * SEM). This is a
    paired-difference test, not two independent samples: pairing on query id is what lets a small,
    consistent shift show up as a narrow CI even with few queries, which is the common case for a
    single-PR report. Deterministic and stdlib-only by construction (no bootstrap) — this module
    has no I/O and no dependency beyond math, and collision_report.py must stay reviewable without
    a second, hidden ranking or statistics implementation.

    n == 0 has no defined mean; every field comes back NaN. n == 1 has a mean_delta but no defined
    SEM (denominator n-1 == 0), so the CI collapses to (mean_delta, mean_delta) rather than raising
    — "one query flipped" is still a fact worth reporting even without a confidence interval.
    """
    pairs = [(float(b), float(h)) for b, h in pairs]
    n = len(pairs)
    if n == 0:
        nan = float("nan")
        return {"n": 0, "mean_base": nan, "mean_head": nan, "mean_delta": nan, "ci_lo": nan, "ci_hi": nan}
    deltas = [h - b for b, h in pairs]
    mean_base = sum(b for b, _ in pairs) / n
    mean_head = sum(h for _, h in pairs) / n
    mean_delta = sum(deltas) / n
    if n < 2:
        return {"n": n, "mean_base": mean_base, "mean_head": mean_head, "mean_delta": mean_delta,
                "ci_lo": mean_delta, "ci_hi": mean_delta}
    var = sum((d - mean_delta) ** 2 for d in deltas) / (n - 1)
    sem = math.sqrt(var / n)
    return {"n": n, "mean_base": mean_base, "mean_head": mean_head, "mean_delta": mean_delta,
            "ci_lo": mean_delta - z * sem, "ci_hi": mean_delta + z * sem}
