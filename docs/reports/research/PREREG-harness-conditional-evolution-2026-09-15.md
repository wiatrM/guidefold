# Pre-registration — does an organisation's skill library evolve differently per harness?

**Status:** Proposed · pre-registration, frozen before the first pilot session · 2026-09-15 ·
frozen at sha256 `[PLACEHOLDER: 64-char lowercase hex sha256 of this file, stamped into the
analysis script header once the owner signs off — see §7]` on the owner's sign-off date.
**Cel:** fix the hypotheses, the conditions, the data, the sample statement and the analysis of a
harness-comparison study *before* the first real session, so that the 20 sessions required by
[PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) "The next four weeks" become evidence rather than an
anecdote. The reason is on the record: the 2026-09-05 peer review
([E1.3-peer-review](../bakeoff/E1.3-peer-review-2026-09-05.md)) found six spec-level errors that
all shared one cause — a number quoted before its method was written down.
**Wejścia:** [DENSE-PROGRAM](../bakeoff/DENSE-PROGRAM.md) §3, §4a (splits, multiplicity);
[E6.7-PROTOCOL](../../pilot/E6.7-PROTOCOL.md) (the structure mirrored here: hypotheses, conditions,
stop rules, freeze with sha256); [PIVOT-RUBRIC](../../pilot/PIVOT-RUBRIC.md) (U11 labels R/Q/P;
rows 3 and 9 are the harness rows); [SEARCH-USE-TELEMETRY](../../SEARCH-USE-TELEMETRY.md) §3–§6;
[TELEMETRY-REPLAY](../../pilot/TELEMETRY-REPLAY.md); [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md)
("The next four weeks", "Kill criteria", "Design partner");
[status report 2026-09-15](../product/2026-09-15-mvp-closure-status.md) §4a rows 5–7 and §6;
[eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md);
[pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md).
**Zakres zastępowania:** none. A research pre-registration, not a contract and not a protocol
amendment: it does not change E6.7-PROTOCOL (which tests with/without skills on paired tasks) or
PIVOT-RUBRIC's thresholds, and authorises no product change (§8).
**New subdirectory:** `docs/reports/research/` is created here, because
[pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md) lists only `bakeoff/`, `golden/`
and `tuning/` and sends pilot procedures to `docs/pilot/`. `.gitignore`'s blanket `research/` rule
matches this path, so the file was added with `git add -f` and is tracked from here on — the same
handling the repository already used for committed research copies. `.gitignore` is not changed.

## 0. Why this is frozen before the first session, and what would make it an anecdote

Production held `imports 0, skills 0, publications 0, tokens 0, gf.events 0` on 2026-09-15
([status report](../product/2026-09-15-mvp-closure-status.md) §3). Every session that follows is
therefore the first observation of its kind, and there will be at most a few dozen of them before
2026-10-04. A question decided after looking at data that small is decided by the analyst.

This becomes an anecdote if any of the following happens: the metric is chosen after the
loaded-skill sets are seen; a week boundary moves so an awkward week falls outside; builder
sessions are counted when the harness split is thin; sessions per harness are reported without the
number of *distinct people*; or a descriptive difference between two harnesses is reported as a
difference *caused by* the harness. §§1–6 make each of those visible.

## 1. Hypotheses

Each hypothesis states its metric, its direction, its null and what makes us drop it. All three
are registered now; none is elevated or swapped after data collection (§6, mirroring
[DENSE-PROGRAM §4a](../bakeoff/DENSE-PROGRAM.md) rule 3).

### H1 — divergence

**Claim.** For one organisation and one library snapshot, the set of skills agents actually load,
and the owner-queue signatures those sessions produce, differ between harnesses by more than the
difference in session counts explains.

**Metric 1 (loaded-skill sets).** For harness `h` and ISO week `w`, let `L(h, w)` be the set of
logical skill ids (URN; the revision is recorded separately, because
[SEARCH-USE-TELEMETRY §4](../../SEARCH-USE-TELEMETRY.md) forbids combining revisions into one
quality estimate without a version filter) with at least one `skill_load_completed` in that
harness-week. The statistic is the mean over weeks of `J(w) = |L(A,w) ∩ L(B,w)| / |L(A,w) ∪ L(B,w)|`.

**Metric 2 (signature vectors).** The per-harness per-week signature counts defined in the
sibling brief H2 (`search_no_hit`, `ask_without_delivery`, `exposed_never_used`, `used_negative`,
`revision_mismatch`), normalised to shares within the harness-week, compared by L1 distance.
**Availability:** these signatures are computed by a branch that is not merged as of 2026-09-15.
Until it lands, metric 2 is `unavailable`, never zero
([pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md): "Brak obserwacji to Unknown,
nie porażka i nie zero").

**Null.** The harness label is exchangeable across sessions within a week: the null distribution
permutes harness labels among the week's sessions while holding each week's per-label session
counts fixed. That is what removes the session-count explanation — every permuted assignment has
the same `|L|` growth pressure as the observed one.

**Direction.** H1 predicts an observed mean Jaccard *below* the permutation null mean, and an
observed L1 signature distance *above* it. Both p-values are two-sided (§5).

**Drop rule.** If the smaller harness contributes fewer than 3 admissible sessions across the
window, H1 is not tested: it is reported descriptively with an interval and labelled underpowered
(§4 shows the arithmetic).

### H2 — transfer

**Claim.** A library change accepted on harness A's evidence (a description or trigger revision, a
consolidation accepted from the owner queue) does not improve, and may harm, harness B's outcome.

**Metric.** Paired before/after on replayed queries per harness, via
[`tools/pilot/telemetry_report.py`](../../pilot/TELEMETRY-REPLAY.md) against the pinned pre- and
post-change snapshots. The paired outcome per query is whether the skill the owner's change was
meant to surface appears in the returned cards, plus, where a task ran, `task_finished.outcome`
(`success`/`failure`/`unknown`) from the execution fields in the ledger
([SEARCH-USE-TELEMETRY §3](../../SEARCH-USE-TELEMETRY.md)). `unknown` is excluded from the
discordant-pair counts and reported as its own column, never coerced (E6.7-PROTOCOL §4).

**Clustering.** Queries within one session are not independent. The analysis unit is the
**session**: per-session outcome shares are paired, and the number of replayed queries is reported
but never used as `n`. Counting queries as independent observations is the easiest way to
fabricate power here.

**Null.** The change has the same signed effect on both harnesses; the sign of (B's delta − A's
delta) is symmetric around zero.

**Drop rule.** H2 needs at least one owner-accepted library change inside the window *and* both
harnesses active before and after it. With zero accepted changes by 2026-10-04, H2 is reported as
not measured. [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) "Kill criteria" already treats four weeks of
sessions with no owner decision as a kill for value proposition 3; H2 inherits that trigger rather
than adding a new one.

### H3 — shared core plus per-harness overlays

**Claim (ours, not a paper's).** A shared core library plus small per-harness overlays produces a
better paired outcome on *both* harnesses than one shared library serving both.

**Provenance, stated precisely.** EvoOntology ([arXiv:2609.15779v1](https://arxiv.org/html/2609.15779v1),
fetched 2026-09-15) reports that ontologies evolved under different LLM backbones diverge — "no
pair exceeds 0.62 overlap" in term identifiers, Claude models at 0.55 and GPT models at 0.61
("Divergence across Backbones") — and that transfer costs: "every off-diagonal drops by at least
6.6 points", average column drop from diagonal to off-diagonal −6.6 (Sonnet-5) to −10.9 (GPT-5.5).
Its own architectural finding is the *opposite* of a core+overlay recommendation: tool-only
evolution recovers +13.2 but "none reaches the +20.0 of the full three-level loop", i.e. the
levels are complementary. H3 is therefore **motivated by** EvoOntology's divergence and
transfer-drop results and is **not** attributed to it as its claim. The paper also supplies the
discipline this document borrows: "backbone-conditional paired evaluation", where a candidate
update is retained only when its improvement clears a margin τ on a held-out set under identical
decoding and interaction budgets.

**Minimum effect worth reporting.** 10 percentage points on the paired per-harness outcome of H2's
metric, in the same direction on both harnesses. Below that, the difference is not worth a
per-harness overlay's maintenance cost, and we report it as a null result.

**Sample it needs.** §4 computes it: a 10 pp effect is far outside this window's reach.

**Null.** Overlay and shared-core arms are exchangeable; their paired difference is symmetric
around zero on each harness.

**Drop rule for the whole study.** If, by 2026-10-04, the second harness has zero admissible
sessions, all three hypotheses are unmeasured and the study is not run — it is recorded as a
precondition failure against issue #82, not as a negative result.

## 2. Conditions

| Dimension | Value | Source / limit |
|---|---|---|
| Harness A | Claude Code, adapter `guidefold install` + device login to the hosted instance | the only adapter with a shipped path ([status report](../product/2026-09-15-mvp-closure-status.md) §4a row 5) |
| Harness B | Copilot CLI, explicit `find` / `load` | issue #82 requires a real session for at least 10 prompts and forbids promising sessionStart injection until demonstrated; no such session exists on 2026-09-15 ([status report](../product/2026-09-15-mvp-closure-status.md) §4a row 6). Copilot CLI is not installed on the builder's machine, so B is a **precondition**, not an assumption |
| Adapter capability | per-stage cells from issue #83's matrix (`observed` / `not supported` / `unknown`) | a KPI whose stage a harness cannot observe is not computed for that harness. Where `.github/instructions/*.instructions.md` `applyTo` globs fire alongside Guidefold retrieval, #82 requires recording which one wins; that interaction is a documented confound for H1 metric 1 on harness B |
| Organisation | `cloudfloo` on `guidefold.cloudfloo.io`, **self-use**, every result labelled `self-use` | [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) "Design partner"; [status report](../product/2026-09-15-mvp-closure-status.md) §6 records the PO/PM finding that self-use is a labelled fallback, the weaker branch of the 2026-09-20 kill row, not a design partner |
| Library snapshot | pinned `index_snapshot`, plus `router_version` and `policy_version`, recorded on every event | [SEARCH-USE-TELEMETRY §4](../../SEARCH-USE-TELEMETRY.md). A session under a different pin is a different experiment and is excluded with a reason (§6) |
| Developer population | the owner plus at least one person who did not build Guidefold | [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) "The next four weeks"; that person is to be named by the owner |
| Person attribution | scoped pseudonymous principal identifier on ingested events; the count reported is *distinct pseudonyms per harness*, never a name and never a per-person outcome | [SEARCH-USE-TELEMETRY §5](../../SEARCH-USE-TELEMETRY.md): pseudonyms are a rotating tenant-scoped HMAC, rotated monthly; HMAC is pseudonymous, not anonymous; small person-based cohorts are suppressed and no individual ranking is produced |
| Key-epoch boundary | the window 2026-09-15 → 2026-10-04 crosses a monthly rotation on 2026-10-01 | person-level counts are computed within one epoch only; any session on or after 2026-10-01 has its person-level count labelled **incomparable** with September's, per §5 of the telemetry contract. Session-level and harness-level metrics are unaffected, because `session_id` does not rotate |

## 3. Data

**Events used** ([SEARCH-USE-TELEMETRY §3](../../SEARCH-USE-TELEMETRY.md)): `search_requested`,
`search_results`, `card_injected`, `skill_load_requested`, `skill_load_completed`,
`skill_use_reported`, `skill_use_observed`, `skill_feedback`, `task_started`, `task_finished`,
`telemetry_health`.

**Fields used**: `schema_version`, `event_id`, `event_type`, `occurred_at`, `producer`, adapter
identity and version, `environment` (must be `pilot`), `session_id`, `task_id`, `correlation_id`,
`search_id` / `use_id` / `load_id` / `exposure_id` / `parent_use_id`, logical `skill_id` (URN) with
its exact immutable revision, result status and `fallback_reason`, ranks and positions,
`context_confirmation` where supported, feedback verdict and reason category, `outcome` and outcome
source, `index_snapshot`, `router_version`, `policy_version`, and the scoped pseudonymous principal
identifier added at ingestion.

**Never collected, and therefore never analysed**: prompt or query text (only a tenant-scoped keyed
HMAC, if query grouping is used at all), file paths, targets, skill bodies, download URLs, tool
output, bearer tokens, e-mail ([SEARCH-USE-TELEMETRY §5](../../SEARCH-USE-TELEMETRY.md)). Free-text
session notes stay local and are not uploaded, as E6.7-PROTOCOL §7 treats its `notes` column.

**Week boundaries.** ISO weeks in UTC. A session belongs, in its entirety, to the week of its
first `search_requested.occurred_at`; a late spool flush therefore cannot move a session between
weeks. The window is exactly three ISO weeks: **2026-W38** (2026-09-14 → 2026-09-20), **2026-W39**
(2026-09-21 → 2026-09-27), **2026-W40** (2026-09-28 → 2026-10-04); the last of those ends on the
2026-10-04 date in [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) "The next four weeks".

**Admissible session.** One `session_id`, `environment = pilot`, under the pinned snapshot, with
at least one `search_requested` **and** at least one `skill_load_completed`. The SEARCH-and-LOAD
requirement is PRODUCT-FOCUS's own wording ("a search and a load for each of them") and is applied
here, not invented.

**Exclusions**, each counted and shown, never a silent subtraction:

1. **Builder sessions.** Sessions whose principal pseudonym is the owner's are excluded from the
   H1 and H2 denominators and reported as a separate labelled row: the builder knows which skill
   exists, so their loaded-skill set is not a sample of what the library surfaces. Both counts are
   published; nothing is deleted.
2. **Agent-run and synthetic sessions.** Anything from `tools/pilot/run_agent_tasks.py`,
   `pivot_report.py --synthetic`, or a fixture is excluded entirely.
   [PIVOT-RUBRIC](../../pilot/PIVOT-RUBRIC.md) states what a synthetic run never establishes.
3. **Off-pin sessions.** A different `index_snapshot`, `router_version` or `policy_version` than
   the frozen one (§6).
4. **Sessions missing IDs.** Absent `session_id` or `task_id` is explicitly unknown and excluded
   from session-level ratios ([SEARCH-USE-TELEMETRY §4](../../SEARCH-USE-TELEMETRY.md)).
5. **Deduplication.** Unique `(tenant_id, event_id)`; transport duplication is distinguished from
   a second genuine use; retries are not extra usage (§4 of the telemetry contract).

## 4. Sample and power

Everything below is arithmetic over the window, not an assumption about it.

**What the permutation null can attain at all.** For an exact two-sided permutation test, the
smallest reachable p-value is `2 / (number of distinct label assignments)`. The choice of
exchangeable unit therefore decides whether α = 0.05 is reachable *before* any data exists:

| Exchangeable unit | Assignments | Smallest attainable two-sided p | Verdict |
|---|---:|---:|---|
| **Matched weeks** (3 weeks, sign of the per-week A−B difference) | 2³ = 8 | 2/8 = 0.25 | α = 0.05 is **unreachable**; a week-paired test cannot produce a significant result in this window, whatever the effect |
| **Sessions**, 20 split 10/10 | C(20,10) = 184 756 | ≈ 1.1 × 10⁻⁵ | reachable |
| **Sessions**, 20 split 15/5 | C(20,5) = 15 504 | ≈ 1.3 × 10⁻⁴ | reachable |
| **Sessions**, 20 split 17/3 | C(20,3) = 1 140 | ≈ 1.8 × 10⁻³ | reachable |
| **Sessions**, 20 split 18/2 | C(20,2) = 190 | ≈ 0.011 | reachable, but only a unanimous extreme clears α |
| **Sessions**, 20 split 19/1 | C(20,1) = 20 | 2/20 = 0.10 | **unreachable** |

**Decision.** The exchangeable unit is the **session**, stratified by week: labels are permuted
within each week, preserving that week's per-harness session counts. A 14/6 split spread as
(5,5,4) and (2,2,2) over W38/W39/W40 gives C(7,2)·C(7,2)·C(6,2) = 21·21·15 = 6 615 assignments,
smallest two-sided p ≈ 3.0 × 10⁻⁴. Because the unit is the session, "over matched weeks" means
*stratified by* week, not *paired on* week: `J` is computed per week and averaged, but weeks are
strata, not observations.

**Floor.** H1 is testable only if the smaller harness contributes **≥ 3** admissible sessions
(row 4 of the table is the boundary; row 5 is below it). This is the §1 drop rule's arithmetic.

**What 20 sessions cannot do.** For H2 and H3, the statistic is the discordant-pair logic of
[E6.7-PROTOCOL §5](../../pilot/E6.7-PROTOCOL.md), and that protocol already computed the answer on
the same n: at n = 20 with 25 % discordance (5 discordant pairs), *no possible split of those 5
pairs clears the exact interval* — a unanimous 5-for-0 has an exact lower bound of ≈ 0.478 against
a 0.5 bar. At n = 20 the detectable |diff| is 0.40 (50 % discordance), 0.45 (75 %) or 0.50 (100 %).
Our minimum effect worth reporting for H3 is 0.10. **Twenty sessions cannot power H2 or H3**, and
no amount of within-session query counting changes that, because the analysis unit is the session
(§1, H2).

**What 20 sessions can establish**: a descriptive H1 — the mean per-week Jaccard and the L1
signature distance, each with a percentile bootstrap interval resampling **sessions**, plus the
stratified permutation p-value when the ≥ 3 floor is met. That is a single-organisation,
`self-use`-labelled observation: P-grade evidence under
[pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md) for *this* organisation, not a
population claim.

**What a powered follow-up needs.** Using E6.7-PROTOCOL §5's formula
`m* = [z_(α/2)·√0.25 + z_β·√(p(1−p))]² / (p − 0.5)²` and `n* = m* / d̂` (two-sided α = 0.05, 80 %
power, `z_{0.025} = 1.960`, `z_{0.20} = 0.842`), with the target gain-share `p` **chosen now, in
advance, at p = 0.65** for a follow-up harness-transfer study:

| target `p` | `m*` (discordant pairs) | `n*` at `d̂` = 0.40 | `n*` at `d̂` = 0.25 |
|---:|---:|---:|---:|
| 0.55 | 783 | 1 958 | 3 132 |
| 0.60 | 194 | 485 | 776 |
| **0.65** | **85** | **213** | **340** |
| 0.70 | 47 | 118 | 188 |
| 0.75 | 29 | 73 | 116 |

The `m*` column for 0.60–0.75 reproduces E6.7-PROTOCOL §5's own table exactly; 0.55 is computed
here with the same formula, and `n*` is rounded up (E6.7 §5's worked example writes ≈117 for the
p = 0.70 / `d̂` = 0.40 cell). So the follow-up this document points to needs on the order of **213 to 340
paired sessions per harness pair**, not 20 — and `d̂` is supplied by the descriptive H1 run, which
is the one thing this window can deliver.

## 5. Analysis plan

1. **H1, metric 1.** Compute `J(w)` per week, then the unweighted mean over weeks with ≥ 1
   admissible session in both harnesses. Permutation: 20 000 stratified relabellings (or the exact
   enumeration when the assignment count is below 20 000, as in the 6 615 example above), two-sided
   p. Interval: percentile bootstrap over sessions, 10 000 resamples, 95 %.
2. **H1, metric 2.** Same permutation and bootstrap machinery on the L1 distance between
   normalised signature vectors. Reported as `unavailable` until the sibling signature branch is
   merged (§1).
3. **H2.** Per-harness paired session-level outcome shares before and after each owner-accepted
   change; discordant-pair counts with both the Wilson and the exact (Clopper–Pearson) interval on
   the same `diff` scale, exactly as `tools/pilot/analyze.py` computes them for E6.7. Where the
   two disagree, the exact interval is decisive (E6.7-PROTOCOL §5).
4. **H3.** Reported only as a descriptive per-harness delta with its interval, against the 10 pp
   minimum, with the §4 statement that the window is underpowered for it printed beside the number.
5. **Multiplicity** (mirroring [DENSE-PROGRAM §4a](../bakeoff/DENSE-PROGRAM.md)): H1 metric 1 is the
   single primary test. The secondary family is **registered now at size 3** — H1 metric 2, H2, H3 —
   and the Holm correction is applied over 3 however many of them actually run, with the number
   that ran printed beside it. Shrinking the family to the tests that survived would hand the
   survivors a weaker correction than the registered design allows, which is DENSE-PROGRAM §4a
   rule 2's "registered before either was tested" applied to this study. No hypothesis is promoted
   to primary after the fact; a secondary result never replaces an unfavourable primary. Every test
   run is counted in the report, so a reader can judge the multiplicity themselves (rule 3).
6. **Pre-specified tables** (the only tables the report contains). **T1**: sessions per harness per
   week — admissible, excluded-builder, excluded-synthetic, excluded-off-pin, missing-ID; distinct
   pseudonyms per harness per key epoch. **T2**: `|L(A,w)|`, `|L(B,w)|`, intersection, union,
   `J(w)` per week; mean `J`, bootstrap CI, permutation p, assignment count. **T3**: signature
   shares per harness per week and their L1 distance, or `unavailable`. **T4**: H2 discordant-pair
   counts, gain rate, regression rate, `diff` with Wilson and exact CI, excluded-unknown count.
   **T5**: H3 per-harness delta against the 10 pp bar, with the underpowered label. **T6**: `d̂`
   observed, and `n*` read off §4's table at the pre-chosen p = 0.65.
7. **No post-hoc metrics.** A metric not listed in §1 is not computed. A metric listed in §1 that
   turns out to be uncomputable is reported as such with the reason.

## 6. Stop rules and what does not count

- **Not a session:** anything synthetic, fixture-driven, or produced by an agent runner; anything
  lacking both a SEARCH and a LOAD; anything under a different snapshot pin.
- **Not evidence for H1/H2:** a builder's own session (counted, labelled, excluded from the
  denominators).
- **Not a replay:** a `telemetry_report.py` run without a frozen snapshot on both sides of the
  change. [TELEMETRY-REPLAY](../../pilot/TELEMETRY-REPLAY.md) is explicit that the tool counts
  event occurrences and does not deduplicate retries, infer that a loaded skill helped, or pair
  conditions.
- **No re-analysis under new rules.** One analysis per frozen sha. A change to a metric, a null or
  an exclusion rule is a new dated addendum appended below §9 with its own sha, never an edit to
  the text above it — the convention E6.7-PROTOCOL §11 and DENSE-PROGRAM use.
- **No week trimming.** All three ISO weeks are in the denominator; a week with zero sessions in
  one harness is reported as such and drops out of `J` only by the rule in §5 item 1, which was
  written before any data existed.
- **Precondition failure is not a result.** Zero Copilot CLI sessions by 2026-10-04 means the
  study was not run; it does not mean the harnesses are the same.

## 7. Freeze procedure

1. Owner review of this document, with the one `[PLACEHOLDER]` in the Status line the only open item.
2. Compute `sha256sum docs/reports/research/PREREG-harness-conditional-evolution-2026-09-15.md` on
   the approved content **before** the Status line is edited, so the hash covers the frozen text
   and not a hash of a hash.
3. Record that value and the sign-off date in the Status line in a follow-up, append-only commit.
4. Stamp the same value into the header of the analysis script that computes §5, following
   `tools/pilot/analyze.py`'s pattern (`# protocol_sha256=<64 lowercase hex>`, which its
   `parse_protocol_sha_header` already refuses to run without), and into the `config_version` field
   of the cohort's events ([SEARCH-USE-TELEMETRY §4](../../SEARCH-USE-TELEMETRY.md)), so a mid-study
   amendment shows up as a version change in the event stream rather than untracked drift.
5. From that point §6 applies. No analysis script is written against a version of this document
   whose sha it does not carry.

## 8. Relation to the product

| Already collected by the product | Research-only, built for this study |
|---|---|
| The ledger: every event and field in §3 ([SEARCH-USE-TELEMETRY §3–§4](../../SEARCH-USE-TELEMETRY.md)) | the per-week Jaccard statistic and its stratified permutation null |
| The owner-queue signatures of sibling brief H2 (unmerged on 2026-09-15) | the L1 signature-distance statistic built on top of them |
| `tools/pilot/telemetry_report.py` replay ([TELEMETRY-REPLAY](../../pilot/TELEMETRY-REPLAY.md)) | the pairing of replays across an owner-accepted change |
| `tools/pilot/analyze.py`'s Wilson and exact intervals | the Holm correction across secondary tests |

**Binding rule.** Nothing in this study changes ranking, thresholds, routing weights, skill text or
any published artefact. [ADR-0029](../../adr/ADR-0029-product-focus-hard-rules.md) rule 2 fixes the
product as T0/T1 sparse plus the authoring loop plus telemetry, and states that a research track
"never becomes a dependency of a shipped path and never claims quality without the pre-registered
test-once run". A result here is a written finding for the owner; any product change it suggests
needs its own decision and its own ADR. Nothing here publishes automatically, and the `self-use`
label travels with every number.

## 9. Paper skeleton

**Title candidates.** (1) "Harness-conditional evolution of an organisation's agent-skill
library"; (2) "One library, two harnesses: measuring divergence in what agents actually load";
(3) "What the ledger shows: per-harness skill usage in a single-organisation deployment".

**Contribution, one sentence.** We pre-register and report the first ledger-based measurement of
whether the same skill library, served through one retrieval service, is *used* differently by
different agent harnesses in one real organisation — with the exchangeable unit, the null and the
power statement fixed before the first session.

**What the related work does not measure.**

| Work | What it does | What it does not measure |
|---|---|---|
| EvoOntology, [arXiv:2609.15779v1](https://arxiv.org/html/2609.15779v1) (fetched 2026-09-15) | backbone-conditional divergence of an evolved ontology: Jaccard ≤ 0.62, transfer drop −6.6 to −10.9 points | different *models*, one agent loop, benchmark tasks — not different *harnesses* with different delivery mechanisms, and not a real organisation's ledger |
| SE-GoS, [PKUfudawei/SEGoS-data](https://huggingface.co/datasets/PKUfudawei/SEGoS-data) (fetched 2026-09-15; Apache-2.0, 1.19 GB, regenerated 2026-09-15, paper arXiv:2609.08228) | execution-backed graph edges (semantic / workflow / avoid) grown from traces over 87 SkillsBench dockerized tasks; 1 000 nodes, 863 cold-start edges → 1 118 → 1 375 → 1 502 | harness identity is never a variable; and the in-repo review ([2026-09-10 novelty and baselines](../market/2026-09-10-r22-novelty-and-baselines.md)) records that its separate 50/37 split reports +5.4 reward points, which the authors place inside their own noise band, and that no attributable implementation was located |
| CoSkill, [arXiv:2609.04865](https://arxiv.org/abs/2609.04865) | two-stage hierarchical retrieval and joint RL over a skill hierarchy | **withdrawn on 2026-09-11 (v2)**, "pending internal content review and approval by the authors' institution"; it is cited as withdrawn prior art, never as a result |
| "SkillLift", "Skill Issue" | — | **not located.** Searched on 2026-09-15 for both titles against arXiv and general web results; neither returned a matching paper. They are recorded here as unverified references, not citations, per [eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md) |

**Figure list.** F1: sessions per harness per week with exclusion bars (T1). F2: per-week Jaccard
with its bootstrap interval, over the permutation null (T2). F3: signature shares per harness,
stacked, with the L1 distance annotated (T3). F4: §4's attainability curve — smallest two-sided p
against the smaller harness's session count — the figure that says what this window can decide.
