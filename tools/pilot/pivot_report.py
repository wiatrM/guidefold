#!/usr/bin/env python3
"""tools/pilot/pivot_report.py -- P15 ("Eksport porownania i pilot") report for U11.

Sources: docs/PRODUCT-PIVOT.md Sec.10 U11 and Sec.13 (pilot protocol, rubric, kill criteria, cost
report per import), docs/PIVOT-BACKLOG.md P15, docs/pilot/PIVOT-RUBRIC.md (frozen rubric this tool
implements), .agents/skills/pilot-evidence/SKILL.md, .agents/skills/eval-evidence-rules/SKILL.md,
.agents/skills/observability-telemetry/SKILL.md.

Reads three independent, optional-except-one inputs and writes one deterministic Markdown + JSON
report. Nothing here talks to a live service; every input is a file already exported by it.

  (a) --usage-export (required): the `GET {repo_base}/usage/export` payload, CSV or JSON, exactly
      as pinned in docs/API-CONTRACT.md Sec.5.5's closing paragraph -- one row per
      (skill_id, revision, harness) with columns, in this order:
        skill_id, revision, scope, owner, harness, window_from, window_to, exposures,
        loads_verified, context_loaded, context_unknown, use_reported, use_observed, helped,
        hindered, mixed, not_applicable, unknown, feedback_n, helped_numerator,
        helped_denominator, small_sample, zero_loads
      `format=json` per the contract returns "the same rows as objects with the same field
      names, plus `coverage` and `window`" -- the contract does not name the JSON list key, so
      this loader ASSUMES a top-level `{"window":..., "coverage":..., "rows": [...]}` object (a
      bare JSON list of row objects is also accepted). This is a documented assumption, not a
      pinned name; if the real endpoint ships a different key, update `load_usage_export` and
      this paragraph together.
      Leniently, and beyond what `/usage/export` itself is contracted to carry, a JSON object may
      also include a top-level `queue` list shaped like `GET {repo_base}/usage`'s
      `QueueItem` (docs/API-CONTRACT.md Sec.5.5) -- e.g. when a caller passes that endpoint's
      fuller payload instead. When `queue` is absent (always true for a CSV export, and true for
      a strict `/usage/export` JSON export), "owner decisions recorded" is reported as
      not_measured_here, never as zero.
      Adapter *capability* coverage (docs/API-CONTRACT.md `AdapterHealth.capabilities`) is not
      part of `/usage/export` either. This tool reports what the pinned export *can* answer for
      U11's "test adapterow porownuje URN/revision przy identycznym deterministycznym
      kontrakcie" AC instead: for every harness seen in the export, which (skill_id) were
      actually loaded (`loads_verified > 0`), and the symmetric difference between harnesses --
      i.e. coverage *parity*, not a capabilities list.

  (b) --scoring-sheet (required): the docs/pilot/scoring-sheet.template.csv schema (task,
      condition, order, developer_pseudonym, outcome, time_seconds, tokens, loads,
      feedback_verdict, evaluator, notes). `condition` is treated as a generic "arm" label here
      (not restricted to E6.7's no_skills/sparse/contender/oracle codes) so the same tool serves
      plainer "with skills vs without" and "harness A vs harness B" comparisons that
      docs/pilot/PIVOT-RUBRIC.md asks for. Unlike tools/pilot/analyze.py this tool does not
      require or verify a frozen `protocol_sha256` header -- it is a general P15 reporting tool,
      not the E6.7 pre-registered protocol's own analysis script; a leading `#`-prefixed line, if
      present, is skipped. `notes` is free text and is dropped on load -- it never reaches the
      report (docs/SEARCH-USE-TELEMETRY.md: free text stays local).

  (c) --cost-json (optional): one JSON object, or a JSON array of objects, shaped
        {import_id, calls, tokens_in, tokens_out, usd_certain, usd_uncertain, wall_s,
         review_minutes, accepted, published}
      (docs/PRODUCT-PIVOT.md Sec.12a point 7). usd_certain and usd_uncertain are never summed
      (docs/API-CONTRACT.md `JobCost`: "oplata po timeoucie modelu trafia do usd_uncertain; nie
      sumujemy jej z pewna"). Cost per accepted/published skill is reported as the string
      "unavailable" when the denominator is zero -- never as 0 (pilot-evidence SKILL.md: "Koszt
      na zaakceptowany skill przy zerze akceptacji jest niedostepny").

Statistics: the discordant-pair Wilson interval is docs/pilot/E6.7-PROTOCOL.md Sec.5's method and
the paired-delta bootstrap is the same percentile method as tools/pilot/analyze.py's
`bootstrap_paired_delta`; both are reimplemented stdlib-only here rather than imported from
analyze.py, following that module's own stated reason for not importing across tools/pilot ("to
keep tools/pilot independent"). Reference values are checked in tests/test_pivot_report.py.

--synthetic stamps every section of the report with "synthetic input, not pilot evidence" --
per docs/pilot/PIVOT-RUBRIC.md and .agents/skills/eval-evidence-rules/SKILL.md, no fixture or
demo run through this tool is ever pilot evidence, no matter how realistic the numbers look.

Usage:
    python3 tools/pilot/pivot_report.py --usage-export usage.json --scoring-sheet sheet.csv
    python3 tools/pilot/pivot_report.py --usage-export usage.csv --scoring-sheet sheet.csv \
        --cost-json cost.json --synthetic --generated-at 2026-09-07T00:00:00Z
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Z_95 = 1.959963985  # two-sided 95% normal quantile (same constant as tools/pilot/analyze.py)

OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
JUDGED_OUTCOMES = {OUTCOME_SUCCESS, OUTCOME_FAILURE}  # anything else is unknown, never a failure

SMALL_SAMPLE_FLOOR = 20  # docs/API-CONTRACT.md HelpedRatio.small_sample threshold, reused here
SYNTHETIC_NOTE = "synthetic input, not pilot evidence"

SCORING_SHEET_COLUMNS = (
    "task", "condition", "order", "developer_pseudonym", "outcome", "time_seconds", "tokens",
    "loads", "feedback_verdict", "evaluator", "notes",
)

# docs/API-CONTRACT.md Sec.5.5, closing paragraph of "Usage i jakosc": pinned column order for
# `GET {repo_base}/usage/export`. This tool only requires the columns to be *present*; it does
# not enforce the server's output order on an input file.
USAGE_EXPORT_COLUMNS = (
    "skill_id", "revision", "scope", "owner", "harness", "window_from", "window_to", "exposures",
    "loads_verified", "context_loaded", "context_unknown", "use_reported", "use_observed",
    "helped", "hindered", "mixed", "not_applicable", "unknown", "feedback_n", "helped_numerator",
    "helped_denominator", "small_sample", "zero_loads",
)

COST_FIELDS = (
    "import_id", "calls", "tokens_in", "tokens_out", "usd_certain", "usd_uncertain", "wall_s",
    "review_minutes", "accepted", "published",
)


class ScoringSheetError(ValueError):
    """Malformed or duplicate-run scoring sheet."""


class UsageExportError(ValueError):
    """Malformed usage export (missing pinned columns, or unreadable JSON/CSV)."""


class CostJsonError(ValueError):
    """Malformed per-import cost JSON."""


# --------------------------------------------------------------------------- small utilities

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _as_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _as_float(v: Any) -> float:
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def _opt_str(v: Any) -> str | None:
    if v in (None, ""):
        return None
    return str(v)


def fmt_value(v: Any, nd: int = 3) -> str:
    """Render a report value for Markdown: NaN and None both read as 'unavailable', a plain
    string (e.g. an already-computed 'unavailable' or 'not_measured_here') passes through."""
    if isinstance(v, str):
        return v
    if v is None:
        return "unavailable"
    if isinstance(v, float) and math.isnan(v):
        return "unavailable"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


# --------------------------------------------------------------------------- statistics

def wilson_score_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """95% (default) Wilson score interval for a raw proportion k/n. Reference-tested in
    tests/test_pivot_report.py against the same known extremes as tools/pilot/analyze.py's own
    test of the identical formula (Wilson 1927)."""
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def discordant_diff_wilson(n_gain: int, n_reg: int, n_evaluable: int) -> tuple[float, float]:
    """Wilson interval on gain_rate - regression_rate, mapped from the Wilson interval on the
    discordant-pair proportion n_gain / (n_gain + n_reg) -- docs/pilot/E6.7-PROTOCOL.md Sec.5's
    method, reimplemented stdlib-only here (see module docstring)."""
    if n_evaluable == 0:
        return (float("nan"), float("nan"))
    m = n_gain + n_reg
    if m == 0:
        return (0.0, 0.0)
    lo, hi = wilson_score_interval(n_gain, m)
    scale = m / n_evaluable
    return (scale * (2 * lo - 1), scale * (2 * hi - 1))


def bootstrap_paired_delta(vals_a: list[float], vals_b: list[float], n_resamples: int = 1000,
                            seed: int = 0) -> dict:
    """95% CI (percentile method) on mean(vals_b) - mean(vals_a), paired bootstrap over the
    matched-pair index -- identical method to tools/pilot/analyze.py's bootstrap_paired_delta,
    reimplemented here stdlib-only per that module's own "keep tools/pilot independent" choice.
    Deterministic for a fixed seed: no wall-clock or OS entropy involved."""
    n = len(vals_a)
    assert n == len(vals_b)
    if n == 0:
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "n": 0}
    observed = sum(vals_b) / n - sum(vals_a) / n
    rng = random.Random(seed)
    idx = range(n)
    deltas = []
    for _ in range(n_resamples):
        sample = [rng.choice(idx) for _ in range(n)]
        a = sum(vals_a[i] for i in sample) / n
        b = sum(vals_b[i] for i in sample) / n
        deltas.append(b - a)
    deltas.sort()
    lo = deltas[max(0, int(0.025 * n_resamples) - 1)] if n_resamples else float("nan")
    hi = deltas[min(n_resamples - 1, int(0.975 * n_resamples))] if n_resamples else float("nan")
    return {"delta": observed, "ci_lo": lo, "ci_hi": hi, "n": n, "n_resamples": n_resamples}


# --------------------------------------------------------------------------- scoring sheet

@dataclass
class ScoreRow:
    task: str
    condition: str  # generic "arm" label -- E6.7 codes or a plain "with_skills"/"without" etc.
    outcome: str
    time_seconds: float | None
    tokens: float | None


def load_scoring_sheet(path: Path) -> list[ScoreRow]:
    text = path.read_text(encoding="utf-8")
    body_lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(body_lines)))
    fieldnames = reader.fieldnames or []
    missing = set(SCORING_SHEET_COLUMNS) - set(fieldnames)
    if missing:
        raise ScoringSheetError(f"scoring sheet missing columns: {sorted(missing)}")

    rows: list[ScoreRow] = []
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[tuple[str, str]] = []
    for raw in reader:
        task = (raw.get("task") or "").strip()
        condition = (raw.get("condition") or "").strip()
        if not task or not condition:
            continue  # blank trailing line
        key = (task, condition)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1 and key not in duplicates:
            duplicates.append(key)
        rows.append(ScoreRow(
            task=task,
            condition=condition,
            outcome=(raw.get("outcome") or "").strip().lower(),
            time_seconds=_parse_optional_float(raw.get("time_seconds")),
            tokens=_parse_optional_float(raw.get("tokens")),
        ))
    if duplicates:
        pretty = ", ".join(f"{t}/{c}" for t, c in sorted(duplicates))
        raise ScoringSheetError(f"duplicate (task, condition) rows, forbidden re-run: {pretty}")
    return rows


def _parse_optional_float(s: str | None) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class ArmSuccess:
    arm: str
    n_rows: int
    n_success: int
    n_failure: int
    n_unknown: int
    n_judged: int
    success_rate: float  # nan when n_judged == 0
    wilson_ci: tuple[float, float]
    small_sample: bool


def per_arm_success(rows: list[ScoreRow]) -> list[ArmSuccess]:
    """Per-arm task success, Wilson interval computed only over judged outcomes (success or
    failure); unknown outcomes are counted separately and never folded into failure."""
    out: list[ArmSuccess] = []
    for arm in sorted({r.condition for r in rows}):
        arm_rows = [r for r in rows if r.condition == arm]
        n_success = sum(1 for r in arm_rows if r.outcome == OUTCOME_SUCCESS)
        n_failure = sum(1 for r in arm_rows if r.outcome == OUTCOME_FAILURE)
        n_judged = n_success + n_failure
        n_unknown = len(arm_rows) - n_judged
        success_rate = n_success / n_judged if n_judged else float("nan")
        wilson = wilson_score_interval(n_success, n_judged) if n_judged else (float("nan"), float("nan"))
        out.append(ArmSuccess(
            arm=arm, n_rows=len(arm_rows), n_success=n_success, n_failure=n_failure,
            n_unknown=n_unknown, n_judged=n_judged, success_rate=success_rate, wilson_ci=wilson,
            small_sample=(n_judged < SMALL_SAMPLE_FLOOR),
        ))
    return out


@dataclass
class Contrast:
    baseline: str
    challenger: str
    n_evaluable: int
    n_gain: int
    n_regression: int
    n_concordant_success: int
    n_concordant_failure: int
    n_excluded_unknown: int
    gain_rate: float
    regression_rate: float
    diff: float
    wilson_ci: tuple[float, float]
    time_bootstrap: dict


def paired_contrast(rows: list[ScoreRow], baseline: str, challenger: str,
                     n_resamples: int = 1000, seed: int = 0) -> Contrast:
    by_tc = {(r.task, r.condition): r for r in rows}
    tasks = sorted({t for (t, c) in by_tc if c in (baseline, challenger)})

    n_gain = n_reg = n_cs = n_cf = n_excl = 0
    time_base: list[float] = []
    time_chal: list[float] = []
    for task in tasks:
        b = by_tc.get((task, baseline))
        c = by_tc.get((task, challenger))
        if b is None or c is None:
            continue
        if b.outcome not in JUDGED_OUTCOMES or c.outcome not in JUDGED_OUTCOMES:
            n_excl += 1
            continue
        if b.outcome == OUTCOME_FAILURE and c.outcome == OUTCOME_SUCCESS:
            n_gain += 1
        elif b.outcome == OUTCOME_SUCCESS and c.outcome == OUTCOME_FAILURE:
            n_reg += 1
        elif b.outcome == OUTCOME_SUCCESS and c.outcome == OUTCOME_SUCCESS:
            n_cs += 1
        else:
            n_cf += 1
        if b.time_seconds is not None and c.time_seconds is not None:
            time_base.append(b.time_seconds)
            time_chal.append(c.time_seconds)

    n_eval = n_gain + n_reg + n_cs + n_cf
    gain_rate = n_gain / n_eval if n_eval else float("nan")
    reg_rate = n_reg / n_eval if n_eval else float("nan")
    diff = gain_rate - reg_rate if n_eval else float("nan")
    return Contrast(
        baseline=baseline, challenger=challenger, n_evaluable=n_eval, n_gain=n_gain,
        n_regression=n_reg, n_concordant_success=n_cs, n_concordant_failure=n_cf,
        n_excluded_unknown=n_excl, gain_rate=gain_rate, regression_rate=reg_rate, diff=diff,
        wilson_ci=discordant_diff_wilson(n_gain, n_reg, n_eval),
        time_bootstrap=bootstrap_paired_delta(time_base, time_chal, n_resamples, seed),
    )


def all_contrasts(rows: list[ScoreRow], n_resamples: int = 1000, seed: int = 0) -> list[Contrast]:
    """Every unordered pair of arms present, in deterministic sorted order -- this tool is not
    restricted to E6.7's fixed 4-condition design, so it enumerates whichever arm labels the
    scoring sheet actually uses (e.g. plain "with_skills"/"without", or "harness_a"/"harness_b")."""
    arms = sorted({r.condition for r in rows})
    out = []
    for i, a in enumerate(arms):
        for b in arms[i + 1:]:
            out.append(paired_contrast(rows, a, b, n_resamples, seed))
    return out


# --------------------------------------------------------------------------- usage export

@dataclass
class UsageRow:
    skill_id: str
    revision: str | None
    scope: str
    owner: str | None
    harness: str
    window_from: str | None
    window_to: str | None
    exposures: int
    loads_verified: int
    context_loaded: int
    context_unknown: int
    use_reported: int
    use_observed: int
    helped: int
    hindered: int
    mixed: int
    not_applicable: int
    unknown: int
    feedback_n: int
    helped_numerator: int
    helped_denominator: int
    small_sample: bool
    zero_loads: bool


@dataclass
class QueueItem:
    item_id: str
    skill_id: str
    reason: str
    has_decision: bool


@dataclass
class UsageExport:
    rows: list[UsageRow]
    queue: list[QueueItem]
    queue_present: bool
    source_format: str  # "json" or "csv"


def _row_from_dict(d: dict) -> UsageRow:
    return UsageRow(
        skill_id=str(d.get("skill_id", "")),
        revision=_opt_str(d.get("revision")),
        scope=str(d.get("scope", "")),
        owner=_opt_str(d.get("owner")),
        harness=str(d.get("harness", "")),
        window_from=_opt_str(d.get("window_from")),
        window_to=_opt_str(d.get("window_to")),
        exposures=_as_int(d.get("exposures")),
        loads_verified=_as_int(d.get("loads_verified")),
        context_loaded=_as_int(d.get("context_loaded")),
        context_unknown=_as_int(d.get("context_unknown")),
        use_reported=_as_int(d.get("use_reported")),
        use_observed=_as_int(d.get("use_observed")),
        helped=_as_int(d.get("helped")),
        hindered=_as_int(d.get("hindered")),
        mixed=_as_int(d.get("mixed")),
        not_applicable=_as_int(d.get("not_applicable")),
        unknown=_as_int(d.get("unknown")),
        feedback_n=_as_int(d.get("feedback_n")),
        helped_numerator=_as_int(d.get("helped_numerator")),
        helped_denominator=_as_int(d.get("helped_denominator")),
        small_sample=_as_bool(d.get("small_sample")),
        zero_loads=_as_bool(d.get("zero_loads")),
    )


def _queue_from_dict(d: dict) -> QueueItem:
    decision = d.get("decision")
    return QueueItem(
        item_id=str(d.get("item_id", "")),
        skill_id=str(d.get("skill_id", "")),
        reason=str(d.get("reason", "")),
        has_decision=isinstance(decision, dict) and bool(decision),
    )


def _check_required_columns(fieldnames: set[str], where: str) -> None:
    missing = set(USAGE_EXPORT_COLUMNS) - fieldnames
    if missing:
        raise UsageExportError(f"usage export {where} missing pinned columns: {sorted(missing)}")


def load_usage_export(path: Path) -> UsageExport:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UsageExportError(f"usage export JSON is not valid: {exc}") from exc
        if isinstance(data, list):
            rows_raw, queue_raw, queue_present = data, [], False
        elif isinstance(data, dict):
            rows_raw = data.get("rows", data.get("skills", []))
            queue_present = "queue" in data
            queue_raw = data.get("queue", []) or []
        else:
            raise UsageExportError("usage export JSON must be a list or an object")
        if rows_raw:
            keys: set[str] = set()
            for r in rows_raw:
                if isinstance(r, dict):
                    keys |= set(r.keys())
            _check_required_columns(keys, "JSON")
        rows = [_row_from_dict(r) for r in rows_raw
                if isinstance(r, dict) and str(r.get("skill_id", "")).strip()]
        queue = [_queue_from_dict(q) for q in queue_raw if isinstance(q, dict)]
        return UsageExport(rows=rows, queue=queue, queue_present=queue_present, source_format="json")

    body_lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(body_lines)))
    fieldnames = reader.fieldnames or []
    _check_required_columns(set(fieldnames), "CSV")
    rows = [_row_from_dict(r) for r in reader if (r.get("skill_id") or "").strip()]
    return UsageExport(rows=rows, queue=[], queue_present=False, source_format="csv")


@dataclass
class HarnessCoverage:
    harness: str
    n_skill_revisions: int
    n_exposed: int
    n_loaded: int
    n_used: int


@dataclass
class AdapterCoverageReport:
    measured: bool
    harnesses: list[HarnessCoverage]
    gaps: list[dict]  # {"harness_a", "harness_b", "only_in_a": [...], "only_in_b": [...]}


def adapter_capability_coverage(rows: list[UsageRow]) -> AdapterCoverageReport:
    """Coverage *parity* across harnesses/adapters seen in the usage export -- U11's AC ("test
    adapterow porownuje URN/revision przy identycznym deterministycznym kontrakcie"), computed
    from what /usage/export actually carries: which skill_id was loaded under which harness. Not
    an AdapterHealth.capabilities list -- that field lives on `GET {repo_base}/usage`, not on the
    export this tool reads (see module docstring)."""
    harnesses = sorted({r.harness for r in rows if r.harness})
    if not harnesses:
        return AdapterCoverageReport(measured=False, harnesses=[], gaps=[])

    loaded_by_harness: dict[str, set[str]] = {}
    coverage: list[HarnessCoverage] = []
    for h in harnesses:
        h_rows = [r for r in rows if r.harness == h]
        loaded = {r.skill_id for r in h_rows if r.loads_verified > 0}
        loaded_by_harness[h] = loaded
        coverage.append(HarnessCoverage(
            harness=h,
            n_skill_revisions=len({(r.skill_id, r.revision) for r in h_rows}),
            n_exposed=sum(1 for r in h_rows if r.exposures > 0),
            n_loaded=len(loaded),
            n_used=sum(1 for r in h_rows if r.use_reported > 0 or r.use_observed > 0),
        ))

    gaps = []
    for i, a in enumerate(harnesses):
        for b in harnesses[i + 1:]:
            only_a = sorted(loaded_by_harness[a] - loaded_by_harness[b])
            only_b = sorted(loaded_by_harness[b] - loaded_by_harness[a])
            gaps.append({"harness_a": a, "harness_b": b, "only_in_a": only_a, "only_in_b": only_b})

    return AdapterCoverageReport(measured=True, harnesses=coverage, gaps=gaps)


@dataclass
class OwnerDecisionSummary:
    measured: bool
    n_queue_items: int
    n_with_decision: int


def summarize_owner_decisions(usage: UsageExport) -> OwnerDecisionSummary:
    if not usage.queue_present:
        return OwnerDecisionSummary(measured=False, n_queue_items=0, n_with_decision=0)
    n = len(usage.queue)
    with_decision = sum(1 for q in usage.queue if q.has_decision)
    return OwnerDecisionSummary(measured=True, n_queue_items=n, n_with_decision=with_decision)


# --------------------------------------------------------------------------- cost per import

@dataclass
class CostImport:
    import_id: str
    calls: float
    tokens_in: float
    tokens_out: float
    usd_certain: float
    usd_uncertain: float
    wall_s: float
    review_minutes: float
    accepted: int
    published: int


def load_cost_json(path: Path) -> list[CostImport]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CostJsonError(f"cost JSON is not valid: {exc}") from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise CostJsonError("cost JSON must be an object or an array of objects")
    out = []
    for entry in data:
        if not isinstance(entry, dict):
            raise CostJsonError(f"cost JSON entry is not an object: {entry!r}")
        out.append(CostImport(
            import_id=str(entry.get("import_id", "")),
            calls=_as_float(entry.get("calls")),
            tokens_in=_as_float(entry.get("tokens_in")),
            tokens_out=_as_float(entry.get("tokens_out")),
            usd_certain=_as_float(entry.get("usd_certain")),
            usd_uncertain=_as_float(entry.get("usd_uncertain")),
            wall_s=_as_float(entry.get("wall_s")),
            review_minutes=_as_float(entry.get("review_minutes")),
            accepted=_as_int(entry.get("accepted")),
            published=_as_int(entry.get("published")),
        ))
    out.sort(key=lambda c: c.import_id)
    return out


@dataclass
class CostSummary:
    n_imports: int
    calls: float
    tokens_in: float
    tokens_out: float
    usd_certain: float
    usd_uncertain: float
    wall_s: float
    review_minutes: float
    accepted: int
    published: int
    cost_per_accepted_certain: float | str
    cost_per_accepted_uncertain: float | str
    cost_per_published_certain: float | str
    cost_per_published_uncertain: float | str
    review_minutes_per_accepted: float | str


def _per(numerator: float, denominator: float) -> float | str:
    """'unavailable' at a zero denominator -- never 0 (pilot-evidence SKILL.md)."""
    return "unavailable" if denominator == 0 else numerator / denominator


def summarize_cost(imports: list[CostImport]) -> CostSummary:
    calls = sum(c.calls for c in imports)
    tokens_in = sum(c.tokens_in for c in imports)
    tokens_out = sum(c.tokens_out for c in imports)
    usd_certain = sum(c.usd_certain for c in imports)
    usd_uncertain = sum(c.usd_uncertain for c in imports)
    wall_s = sum(c.wall_s for c in imports)
    review_minutes = sum(c.review_minutes for c in imports)
    accepted = sum(c.accepted for c in imports)
    published = sum(c.published for c in imports)
    return CostSummary(
        n_imports=len(imports), calls=calls, tokens_in=tokens_in, tokens_out=tokens_out,
        usd_certain=usd_certain, usd_uncertain=usd_uncertain, wall_s=wall_s,
        review_minutes=review_minutes, accepted=accepted, published=published,
        cost_per_accepted_certain=_per(usd_certain, accepted),
        cost_per_accepted_uncertain=_per(usd_uncertain, accepted),
        cost_per_published_certain=_per(usd_certain, published),
        cost_per_published_uncertain=_per(usd_uncertain, published),
        review_minutes_per_accepted=_per(review_minutes, accepted),
    )


# --------------------------------------------------------------------------- rubric verdicts

@dataclass
class RubricRow:
    id: str
    label: str  # R / Q / P, docs/pilot/PIVOT-RUBRIC.md
    measurement: str
    value: str
    verdict: str
    caveat: str


def build_rubric_verdicts(arm_success: list[ArmSuccess], contrasts: list[Contrast],
                           cost: CostSummary | None, adapters: AdapterCoverageReport,
                           owner: OwnerDecisionSummary) -> list[RubricRow]:
    rows: list[RubricRow] = []

    for a in arm_success:
        verdict = "not_measured_here" if a.n_judged == 0 else (
            "small_sample" if a.small_sample else "measured")
        rows.append(RubricRow(
            id=f"task_success:{a.arm}", label="P",
            measurement=f"Task success -- arm {a.arm}",
            value=fmt_value(a.success_rate),
            verdict=verdict,
            caveat=f"n_judged={a.n_judged} n_unknown={a.n_unknown}",
        ))

    for c in contrasts:
        pair = f"{c.challenger}_vs_{c.baseline}"
        if c.n_evaluable == 0:
            verdict = "not_measured_here"
        elif c.n_gain > 0 and c.n_regression > 0:
            verdict = "regression_both_directions"
        elif c.n_gain > 0 or c.n_regression > 0:
            verdict = "one_directional"
        else:
            verdict = "no_discordant_pairs"
        rows.append(RubricRow(
            id=f"regression:{pair}", label="P",
            measurement=f"Regression, both directions -- {c.challenger} vs {c.baseline}",
            value=f"gain={c.n_gain} regression={c.n_regression} diff={fmt_value(c.diff)}",
            verdict=verdict,
            caveat=f"excluded_unknown={c.n_excluded_unknown}",
        ))
        tb = c.time_bootstrap
        time_verdict = "not_measured_here" if tb["n"] == 0 else (
            "faster" if tb["delta"] < 0 else ("slower" if tb["delta"] > 0 else "no_change"))
        rows.append(RubricRow(
            id=f"time:{pair}", label="P",
            measurement=f"Time, paired delta -- {c.challenger} vs {c.baseline}",
            value=("unavailable" if tb["n"] == 0 else
                   f"delta_s={fmt_value(tb['delta'])} ci95=[{fmt_value(tb['ci_lo'])}, {fmt_value(tb['ci_hi'])}]"),
            verdict=time_verdict,
            caveat=f"n_pairs={tb['n']}",
        ))

    if cost is None:
        rows.append(RubricRow(
            id="cost_per_accepted", label="P", measurement="Cost per accepted skill",
            value="not_measured_here", verdict="not_measured_here",
            caveat="no --cost-json given",
        ))
        rows.append(RubricRow(
            id="cost_per_published", label="P", measurement="Cost per published skill",
            value="not_measured_here", verdict="not_measured_here",
            caveat="no --cost-json given",
        ))
        rows.append(RubricRow(
            id="review_minutes", label="P", measurement="Review minutes per accepted skill",
            value="not_measured_here", verdict="not_measured_here",
            caveat="no --cost-json given",
        ))
    else:
        rows.append(RubricRow(
            id="cost_per_accepted", label="P", measurement="Cost per accepted skill",
            value=f"certain={fmt_value(cost.cost_per_accepted_certain, 4)} "
                  f"uncertain={fmt_value(cost.cost_per_accepted_uncertain, 4)}",
            verdict="unavailable" if cost.accepted == 0 else "measured",
            caveat=f"accepted={cost.accepted} n_imports={cost.n_imports}",
        ))
        rows.append(RubricRow(
            id="cost_per_published", label="P", measurement="Cost per published skill",
            value=f"certain={fmt_value(cost.cost_per_published_certain, 4)} "
                  f"uncertain={fmt_value(cost.cost_per_published_uncertain, 4)}",
            verdict="unavailable" if cost.published == 0 else "measured",
            caveat=f"published={cost.published} n_imports={cost.n_imports}",
        ))
        rows.append(RubricRow(
            id="review_minutes", label="P", measurement="Review minutes per accepted skill",
            value=fmt_value(cost.review_minutes_per_accepted, 4),
            verdict="unavailable" if cost.accepted == 0 else "measured",
            caveat=f"review_minutes_total={cost.review_minutes:g}",
        ))

    if not owner.measured:
        rows.append(RubricRow(
            id="owner_decisions", label="P", measurement="Owner decisions recorded",
            value="not_measured_here", verdict="not_measured_here",
            caveat="usage export carried no queue section (not part of the pinned "
                   "/usage/export shape)",
        ))
    else:
        rate = "unavailable" if owner.n_queue_items == 0 else f"{owner.n_with_decision / owner.n_queue_items:.3f}"
        rows.append(RubricRow(
            id="owner_decisions", label="P", measurement="Owner decisions recorded",
            value=rate,
            verdict="unavailable" if owner.n_queue_items == 0 else "measured",
            caveat=f"n_queue_items={owner.n_queue_items} n_with_decision={owner.n_with_decision}",
        ))

    if not adapters.measured:
        rows.append(RubricRow(
            id="adapter_capability_coverage", label="R",
            measurement="Adapter capability coverage",
            value="not_measured_here", verdict="not_measured_here",
            caveat="usage export carried no harness column values",
        ))
    else:
        for h in adapters.harnesses:
            rows.append(RubricRow(
                id=f"adapter_capability_coverage:{h.harness}", label="R",
                measurement=f"Adapter capability coverage -- {h.harness}",
                value=f"exposed={h.n_exposed} loaded={h.n_loaded} used={h.n_used}",
                verdict="measured",
                caveat=f"n_skill_revisions={h.n_skill_revisions}",
            ))
        for g in adapters.gaps:
            gap_verdict = "parity" if not g["only_in_a"] and not g["only_in_b"] else "coverage_gap"
            rows.append(RubricRow(
                id=f"adapter_capability_coverage:{g['harness_a']}_vs_{g['harness_b']}", label="R",
                measurement=f"Adapter coverage parity -- {g['harness_a']} vs {g['harness_b']}",
                value=f"only_in_{g['harness_a']}={len(g['only_in_a'])} "
                      f"only_in_{g['harness_b']}={len(g['only_in_b'])}",
                verdict=gap_verdict,
                caveat="",
            ))

    return rows


# --------------------------------------------------------------------------- assembly

@dataclass
class PivotReport:
    run_id: str
    generated_at: str
    synthetic: bool
    input_sha256: dict
    arm_success: list[ArmSuccess]
    contrasts: list[Contrast]
    cost: CostSummary | None
    adapter_coverage: AdapterCoverageReport
    owner_decisions: OwnerDecisionSummary
    rubric: list[RubricRow]


def build_report(usage_export_path: Path, scoring_sheet_path: Path,
                  cost_json_path: Path | None, synthetic: bool,
                  generated_at: str | None = None, n_resamples: int = 1000,
                  seed: int = 0) -> PivotReport:
    usage = load_usage_export(usage_export_path)
    score_rows = load_scoring_sheet(scoring_sheet_path)
    cost_imports = load_cost_json(cost_json_path) if cost_json_path else []
    cost_summary = summarize_cost(cost_imports) if cost_json_path else None

    arm_success = per_arm_success(score_rows)
    contrasts = all_contrasts(score_rows, n_resamples, seed)
    adapter_cov = adapter_capability_coverage(usage.rows)
    owner_dec = summarize_owner_decisions(usage)
    rubric = build_rubric_verdicts(arm_success, contrasts, cost_summary, adapter_cov, owner_dec)

    input_sha256 = {
        "usage_export": sha256_file(usage_export_path),
        "scoring_sheet": sha256_file(scoring_sheet_path),
    }
    if cost_json_path:
        input_sha256["cost_json"] = sha256_file(cost_json_path)

    gen_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id_src = "|".join([
        input_sha256.get("usage_export", ""),
        input_sha256.get("scoring_sheet", ""),
        input_sha256.get("cost_json", ""),
        gen_at,
    ])
    run_id = sha256_bytes(run_id_src.encode("utf-8"))[:16]

    return PivotReport(
        run_id=run_id, generated_at=gen_at, synthetic=synthetic, input_sha256=input_sha256,
        arm_success=arm_success, contrasts=contrasts, cost=cost_summary,
        adapter_coverage=adapter_cov, owner_decisions=owner_dec, rubric=rubric,
    )


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return "unavailable"
    return obj


def report_to_dict(report: PivotReport) -> dict:
    def section(value: Any) -> dict:
        d: dict[str, Any] = {"data": _sanitize(value)}
        if report.synthetic:
            d["synthetic_note"] = SYNTHETIC_NOTE
        return d

    out = {
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "synthetic": report.synthetic,
        "input_sha256": report.input_sha256,
        "sections": {
            "arm_task_success": section([asdict(a) for a in report.arm_success]),
            "regression_contrasts": section([asdict(c) for c in report.contrasts]),
            "cost": section(asdict(report.cost) if report.cost else "not_measured_here"),
            "adapter_capability_coverage": section(asdict(report.adapter_coverage)),
            "owner_decisions": section(asdict(report.owner_decisions)),
            "rubric_verdicts": section([asdict(r) for r in report.rubric]),
        },
    }
    if report.synthetic:
        out["synthetic_note"] = SYNTHETIC_NOTE
    return out


# --------------------------------------------------------------------------- Markdown rendering

def render_markdown(report: PivotReport) -> str:
    lines: list[str] = []
    lines.append(f"# Pivot report -- run {report.run_id}")
    lines.append("")
    if report.synthetic:
        lines.append(f"**{SYNTHETIC_NOTE}**")
        lines.append("")
    lines.append(f"- generated_at: {report.generated_at}")
    for k, v in sorted(report.input_sha256.items()):
        lines.append(f"- {k}_sha256: {v}")
    lines.append("")

    def banner() -> None:
        if report.synthetic:
            lines.append(f"_{SYNTHETIC_NOTE}_")
            lines.append("")

    lines.append("## Per-arm task success (Q/P; Wilson 95% over judged outcomes only)")
    banner()
    lines.append("| arm | n_rows | n_judged | n_success | n_failure | n_unknown | success_rate | wilson_95 | small_sample |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for a in report.arm_success:
        wl = "n/a" if math.isnan(a.wilson_ci[0]) else f"[{a.wilson_ci[0]:.3f}, {a.wilson_ci[1]:.3f}]"
        lines.append(f"| {a.arm} | {a.n_rows} | {a.n_judged} | {a.n_success} | {a.n_failure} | "
                      f"{a.n_unknown} | {fmt_value(a.success_rate)} | {wl} | {a.small_sample} |")
    lines.append("")

    lines.append("## Regression, both directions, and paired time")
    banner()
    lines.append("| challenger vs baseline | n_evaluable | gain | regression | diff | wilson_95 | excluded_unknown | time_delta_s (n_pairs) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for c in report.contrasts:
        wl = "n/a" if math.isnan(c.wilson_ci[0]) else f"[{c.wilson_ci[0]:.3f}, {c.wilson_ci[1]:.3f}]"
        tb = c.time_bootstrap
        time_cell = "unavailable (n=0)" if tb["n"] == 0 else (
            f"{fmt_value(tb['delta'])} [{fmt_value(tb['ci_lo'])}, {fmt_value(tb['ci_hi'])}] (n={tb['n']})")
        lines.append(f"| {c.challenger} vs {c.baseline} | {c.n_evaluable} | {c.n_gain} | "
                      f"{c.n_regression} | {fmt_value(c.diff)} | {wl} | {c.n_excluded_unknown} | {time_cell} |")
    lines.append("")

    lines.append("## Cost per accepted / published skill")
    banner()
    if report.cost is None:
        lines.append("not_measured_here (no --cost-json given)")
    else:
        cs = report.cost
        lines.append(f"- imports: {cs.n_imports}, calls: {cs.calls:g}, tokens_in: {cs.tokens_in:g}, "
                      f"tokens_out: {cs.tokens_out:g}, wall_s: {cs.wall_s:g}")
        lines.append(f"- accepted: {cs.accepted}, published: {cs.published}, "
                      f"usd_certain: {cs.usd_certain:g}, usd_uncertain: {cs.usd_uncertain:g}, "
                      f"review_minutes: {cs.review_minutes:g}")
        lines.append(f"- cost_per_accepted (certain / uncertain): "
                      f"{fmt_value(cs.cost_per_accepted_certain, 4)} / {fmt_value(cs.cost_per_accepted_uncertain, 4)}")
        lines.append(f"- cost_per_published (certain / uncertain): "
                      f"{fmt_value(cs.cost_per_published_certain, 4)} / {fmt_value(cs.cost_per_published_uncertain, 4)}")
        lines.append(f"- review_minutes_per_accepted: {fmt_value(cs.review_minutes_per_accepted, 4)}")
    lines.append("")

    lines.append("## Adapter capability coverage (R -- coverage parity, not a capabilities list)")
    banner()
    ac = report.adapter_coverage
    if not ac.measured:
        lines.append("not_measured_here (usage export carried no harness column values)")
    else:
        lines.append("| harness | n_skill_revisions | n_exposed | n_loaded | n_used |")
        lines.append("|---|---|---|---|---|")
        for h in ac.harnesses:
            lines.append(f"| {h.harness} | {h.n_skill_revisions} | {h.n_exposed} | {h.n_loaded} | {h.n_used} |")
        if ac.gaps:
            lines.append("")
            lines.append("| harness A | harness B | only in A | only in B |")
            lines.append("|---|---|---|---|")
            for g in ac.gaps:
                lines.append(f"| {g['harness_a']} | {g['harness_b']} | {len(g['only_in_a'])} | {len(g['only_in_b'])} |")
    lines.append("")

    lines.append("## Owner decisions recorded")
    banner()
    od = report.owner_decisions
    if not od.measured:
        lines.append("not_measured_here (usage export carried no queue section)")
    else:
        rate = "unavailable" if od.n_queue_items == 0 else f"{od.n_with_decision / od.n_queue_items:.3f}"
        lines.append(f"- queue_items: {od.n_queue_items}, with_decision: {od.n_with_decision}, rate: {rate}")
    lines.append("")

    lines.append("## Rubric verdicts")
    banner()
    lines.append("| id | label | measurement | value | verdict | caveat |")
    lines.append("|---|---|---|---|---|---|")
    for r in report.rubric:
        lines.append(f"| {r.id} | {r.label} | {r.measurement} | {r.value} | {r.verdict} | {r.caveat} |")
    lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="P15 pilot/comparison report (docs/pilot/PIVOT-RUBRIC.md, U11).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--usage-export", required=True, type=Path)
    ap.add_argument("--scoring-sheet", required=True, type=Path)
    ap.add_argument("--cost-json", type=Path, default=None)
    ap.add_argument("--synthetic", action="store_true",
                     help="stamp every section as synthetic input, not pilot evidence")
    ap.add_argument("--generated-at", default=None,
                     help="override the generation timestamp (RFC3339 UTC) for reproducible "
                          "output; default: now")
    ap.add_argument("--bootstrap-resamples", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    ap.add_argument("--out-prefix", type=Path, default=None,
                     help="write <prefix>.md / <prefix>.json instead of stdout")
    args = ap.parse_args(argv)

    try:
        report = build_report(
            args.usage_export, args.scoring_sheet, args.cost_json, synthetic=args.synthetic,
            generated_at=args.generated_at, n_resamples=args.bootstrap_resamples, seed=args.seed,
        )
    except (ScoringSheetError, UsageExportError, CostJsonError, FileNotFoundError,
            json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    md = render_markdown(report) if args.format in ("markdown", "both") else None
    js = json.dumps(report_to_dict(report), indent=2, sort_keys=True) if args.format in ("json", "both") else None

    if args.out_prefix:
        if md is not None:
            args.out_prefix.with_suffix(".md").write_text(md, encoding="utf-8")
        if js is not None:
            args.out_prefix.with_suffix(".json").write_text(js, encoding="utf-8")
    else:
        if md is not None:
            print(md)
        if js is not None:
            print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
