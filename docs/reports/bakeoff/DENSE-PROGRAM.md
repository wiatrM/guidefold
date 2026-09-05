# Dense retrieval programme — pre-registered, v2.2

**Status:** Pre-registered 2026-09-05 (v1, PR #26); amended to v2 the same day after methodological
review; v2.1 added family F5 (offline enrichment). **v2.2 adds family F6 (offline dense sibling map), derived from a measured result and registered before F6 itself is measured.** The v1 text is in git history. Results are appended under
§7 as they land; §1–6 are frozen from v2 onward.
**Goal (user, verbatim intent):** make dense earn its place by beating everything else *methodically*
— on real data, through the product path, inside the budget — and **stop honestly if it cannot.**
**Governs:** ADR-0020 (gate wording), ADR-0022 (product path, cache identity), `CLAUDE.md` § Evaluation corpora.

## 0. What v2 changed, and why (the reviewer's five points, all accepted)

| # | v1 said | v2 says | why |
|---|---|---|---|
| 1 | R1 (one skill-tuned encoder) is a **ceiling**; if it fails, "no served dense can" — programme ends | R1 is a **strong reference point**. Every method *family* gets its own bounded budget; none is gated on another family's result | one checkpoint bounds nothing else; Model2Vec's own docs note teacher order ≠ student order; doc2query is lexical and independent of embedding quality |
| 2 | fusion tuned only at R3, after families were already kept/dropped on **test** results; "retain ≥ 50 % of R1's gain" | **all selection on a dev split carved from SKILLRET *train***; fusion tuned per family on dev; freeze; **test corpora touched once per frozen variant**; pre-specified minimum benefit + tolerated regression + paired CI replace the 50 % rule | using test results to choose what to run next makes them selection sets; 50 % of a noisy gain is arbitrary |
| 3 | "Python is not the bottleneck; a rewrite buys nothing" and "0.6B = 0.5–1 s, MiniLM = 20–50 ms" as facts | **two latency tiers, 300 ms and 500 ms, both measured**; small contextual encoders tried via **onnxruntime from Python first**; the 0.6B and MiniLM timings are estimates to be **measured**, not quoted | the 65 ms sparse hook does not show that +200 ms buys nothing under a different architecture |
| 4 | "word table keyed by teacher version, downloaded once" | word table keyed by the **full distillation identity** (teacher revision + vocabulary + weighting + projection + quantisation) per ADR-0022 §6; download limit may be relaxed deliberately, but memory, cold start and update cost are still measured | v1 regressed a correction already accepted in ADR-0022 |
| 5 | "+30 nDCG → +0.3 % Terminal-Bench success" and "static averaging caused the sibling regression" | SkillRet's execution result compares **no retrieval vs SkillRet**, not BM25 vs SkillRet — no NDCG-to-success attribution is possible; the static-averaging explanation of the sibling regression is a **hypothesis** | both were already corrected in RESEARCH.md; v1 reintroduced them |

Rules that survive from v1 unchanged: product path only; coverage before re-ordering; both test
corpora must agree; per-query rankings for every run; latency is the whole hook in a fresh process;
the SKILLRET overlap caveat; the report says "none of the studied variants earned deployment" if that
is the answer.

---

## 1. The constraint, stated as a variable rather than a wall

The hook is a fresh process, currently stdlib + PyYAML, currently ≤ 300 ms warm. Measured: whole
hook p50 65.7 / p95 71.8 ms at 26 skills; BM25 + a static table is 37 ms of query work at 2 000
skills. That is the cost of the *current* architecture — it says nothing about what a different one
could buy for more time. So the programme carries **two tiers**:

- **T300** — the existing budget; integer arithmetic over a shipped table; stdlib only.
- **T500** — 500 ms; a small contextual encoder allowed via onnxruntime **from Python** (no rewrite
  is a precondition of this experiment); stdlib-only and bit-reproducibility are then open ADR
  questions, decided on the measured trade, not assumed either way.

Every latency figure is warm p50/p95 for the whole hook, fresh process, on the **6 006-skill**
index, machine stated, cold start reported separately. Batch time ÷ n is not latency. "Zero
query-time cost" (document expansion) is a hypothesis to measure: a larger index can cost time and
memory.

Artifact economics (ADR-0021/0022): teacher weights never reach the user. The word table's identity
is the full distillation identity; it is cached until any element of that identity changes. Shard
size, memory and cold start are measured for every survivor; the download limit is a deliberate
choice, not a law.

## 2. What the literature says we should expect (read before, not after)

| source | expectation | how the programme uses it |
|---|---|---|
| **SkillRet v3**, leaderboard | untuned 0.6B +10 nDCG over BM25; skill-tuned 0.6B +30 | the encoder family is worth a real budget; the reference run R1 shows what a tuned encoder does *on our path* |
| **SkillRet v3**, Terminal-Bench | retrieval (vs *none*) preserved success and cut cost 10 % | retrieval quality is a proxy for execution; no NDCG→success attribution; execution eval stays a separate P2 |
| **BEIR** | dense weak out-of-domain; BM25 robust; rerank/late-interaction best zero-shot at high cost | expect static students to lose a lot; expect small contextual encoders to be the T500 candidates |
| **SkillRouter v5** | body signal 37–44 pp; 4-source hard negatives essential; fine-tuning > scale | body in every encoder input; any trained student uses 4-source negatives |
| **Graph of Skills** | dependency bundle > top-1 | judge on `all_required@4`; closure stays in every arm |
| **SkillResolve** | risky same-capability siblings are the failure mode | HSR@4 is a gate where labels exist (SkillRetBench) |
| **Model2Vec** | teacher order ≠ student order; weighting `a/(a+p)`; potion-retrieval exists | static family tests a prebuilt retrieval-trained model *and* distillation from more than one teacher |
| **doc2query** | index-time expansion, lexical search | its own family; independent of any embedding result |
| **RRF** (Cormack) | rank fusion for large pools; discards magnitudes | fusion is tuned per family on dev; score-level fusion is the default candidate |

## 3. Splits — the rule that makes everything else honest

| split | source | used for |
|---|---|---|
| **dev** | a stratified subset of SKILLRET **train** (queries + their own skill pool; disjoint from test by construction), frozen once, id list committed | *every* choice: which configuration, which fusion, which weights, whether a family continues |
| **test-A** | SKILLRET-test, 6 006 skills / 4 392 queries, pinned `a050ad23` | final gates only, once per frozen variant; flattered for the SKILLRET-tuned encoder (same distribution) |
| **test-B** | SkillRetBench, 501 skills / 1 250 queries, pinned `4bdbf59b` | final gates only, once per frozen variant; carries HSR@4 and the outdated/redundant labels |
| regression | Meridian fixture, 220 queries | CI only; never evidence |

A result on test-A or test-B never decides what to run next. If a family needs more tries, it uses
its dev budget.

## 4. Method families and budgets

Each family gets a **bounded budget of dev configurations**. Within it, coverage is measured first
(gold skills added to the candidate pool that BM25F's top-50 missed), then fusion is tuned on dev,
then the best-on-dev configuration is frozen and run once on each test corpus.

| family | what | tier | dev budget |
|---|---|---|---|
| **F0 sparse** | BM25F + filter + closure, `w_dense = 0` — the shipped product | T300 | reference; 0 |
| **F1 encoder hybrid** | `SKILLRET-Embedding-0.6B` (and one generic, `Qwen3-Embedding-0.6B`) as dense candidate source, fused with BM25F; latency **not** a gate here — this is the reference for what a tuned encoder does on our path | — | ≤ 4 (fusion, k, w) |
| **F2 static** | (a) prebuilt `potion-retrieval-32M` quantised to our table; (b) Model2Vec-proper distillation from **two** teachers (SKILLRET, Qwen3), their weighting, PCA-256, int8; (c) if budget remains, a static student trained on SKILLRET train with 4-source negatives | T300 | ≤ 8 total |
| **F3 document expansion** | doc2query-T5 pseudo-queries per skill at index time, indexed as a sixth BM25F field; lexical at query time | T300 | ≤ 4 (n queries per doc, field weight) |
| **F4 small contextual** | MiniLM-class ONNX (~22M) via onnxruntime from Python; measured, not estimated | T500 | ≤ 4 |
| **F6 offline dense sibling map** *(v2.2)* | use the encoder **offline** to compute, per skill, its confusable set (same-capability neighbours above a cosine threshold); ship it as a small typed graph in the artifact; at query time apply a deterministic integer rule when two confusables both reach the top 4 — demote the one the query matches less on discriminating terms. **No model, no vectors at query time.** | T300 | ≤ 4 (threshold, neighbours per skill, the tie-break rule) |
| **F5 offline enrichment** *(v2.1)* | derive the fields real skills lack — `triggers` from "when to use" sections, `negative_triggers` from "do not use", `requires`/`similar` edges from body mentions of other skills — at index time (GoS "parser-first normalisation"; SkillRetBench's own `trigger_phrases`); the runtime is unchanged sparse | T300 | ≤ 4 (which sections; edge threshold; whether an LLM pass is allowed) |

**Why F6 exists (v2.2).** The full-encoder reference on test-B (PR #35) failed the completeness
gate (`all_required@4` +0.67 pp, CI straddles zero) but **reduced harmful-sibling exposure by
10.00 pp [−15.67, −4.00]** — the one clean, significant dense win in the programme, and exactly the
failure mode SkillResolve-Bench isolates (a router finds the right capability family and exposes the
wrong representative). Every dense arm so far used the encoder as a *candidate source*, which is
where it is weakest here (coverage 8.76 %). F6 tests the hypothesis that its real value is
**discrimination between near-identical skills**, a job that can be precomputed: the pairs are a
property of the corpus, not of the query. If it holds, we get the −10 pp exposure without any
query-time model — the only shape in which a dense signal can pass the T300 gate at all.

**Why F5 exists (v2.1).** Real skills do not carry our fields. Measured 2026-09-05: SkillRetBench
has analogues (85 % `trigger_phrases`, 100 % `anti_triggers`, 66 % with `composable_skills`,
1 241 edges); SKILLRET-test has none (name, description, body, taxonomy only); of 2 037 real local
skills, 4 have any of our fields — yet **93 % mention another skill by name in the body (9 274
candidate edges), 84 % have a "when to use" section, 25 % a "do not use" section.** The fields are
derivable. F5 tests whether deriving them recovers what authored fields give, on corpora that have
none. Its evaluation is the same as every family's: dev budget, freeze, both tests once. Its
gate is the same too — a derived `requires` graph must raise `all_required@4`, not merely exist.

Families are independent: F3 runs regardless of F1/F2; F4 runs regardless of F2. F1's result may
inform how much *effort* is spent, never whether another family is *allowed* to run.

## 5. Gates — fixed now, with minimum benefit and tolerated regression

A frozen variant is **adopted** only if, on **both** test-A and test-B:

| gate | rule |
|---|---|
| bundle completeness | `all_required@4` ≥ F0 + **2.0 pp**, paired bootstrap over queries (1 000 resamples) 95 % CI excluding 0 |
| harmful exposure | `distractor_rate@4` (test-A: NaN, no labels) and **HSR@4** (test-B) not worse than F0 by more than **1.0 pp** |
| primary quality | `hit@1` and `nDCG@10` not worse than F0 by more than 1.0 pp (a bundle win must not cost the headline) |
| cost | warm p95 ≤ its tier (300 or 500 ms), whole hook, 6 006-skill index; artifact per ADR-0021 budget; cold start and memory reported |

A variant that clears every gate on one corpus and fails one on the other is **not adopted** —
reported as "corpus-dependent". A variant that clears all gates only at T500 is reported as a T500
candidate for the ADR that would open that tier; it is not shipped by this programme.

**Termination.** When every family has spent its dev budget and every frozen variant has been
tested once: if none clears the gates on both corpora, the programme ends with the sentence
*"none of the studied variants earned deployment"*, plus the best dev result per family and the
gate each failed, so the next attempt starts from evidence.

## 6. Reference run R1 — what it is and is not

R1 (already running on both test corpora, unfused config chosen from tooling defaults, latency
ignored) is kept as a **reference**: it shows what a tuned encoder does through the product path
before any dev tuning. Its numbers are reported. They gate nothing. Its coverage figure — gold
skills BM25F missed that the encoder finds — is the most useful number it produces, because it
bounds how much *any* dense signal could add to candidates on these corpora.

---

## 7. Results (appended as they land; §1–6 are frozen from v2)

### 7.1 SKILLRET-test (test-A) — F0/R0 and R1, 2026-09-05

Full report: `docs/reports/bakeoff/SKILLRET-test-2026-09-05.md`. Code: `tools/eval/skillret.py`.
Raw per-query evidence (gzip JSONL) and summary JSON: `docs/reports/bakeoff/validation/
skillret-{r0,r1,latency}*`. Corpus: 6,006 skills / 4,392 queries / 7,187 qrels
(`ThakiCloud/SKILLRET`, revision `a050ad23`). No dev split carved here — test-only, per §3;
the programme's SKILLRET-train dev split (frozen separately) is untouched by this run.

**Coverage first (§6's framing)**: gold skills BM25F's top-50 misses that the encoder's top-50
adds — **root 39.6%** (2,849/7,187), **major 22.8%** (1,638/7,187). This is the number that bounds
how much any dense signal could add to this product path on this corpus; it is reported before
quality metrics on purpose.

**Quality (retrieval order for hit@1/nDCG@10, injection order for all_required@4)**:

| arm | setting | hit@1 | nDCG@10 (paper-style) | all_required@4 |
|---|---|---|---|---|
| F0/R0 (`w_dense=0`) | root | 0.3825 | 0.3999 | 0.2700 |
| F0/R0 (`w_dense=0`) | major | 0.3663 | 0.3957 | 0.2862 |
| R1 (`w_dense=1`, reference) | root | 0.6004 | 0.6324 | 0.4497 |
| R1 (`w_dense=1`, reference) | major | 0.5685 | 0.5873 | 0.4185 |

Paper's published BM25 nDCG@10 = 51.69; our paper-style (binary-relevance) F0 nDCG@10 is
39.99 (root) / 39.57 (major) — not apples-to-apples (different BM25 configuration/field
construction; see the full report §1).

**Paired bootstrap vs F0/R0** (1,000 resamples, 95% CI), overall: `all_required@4` root
+17.96pp [16.80, 19.08], major +13.23pp [12.23, 14.23]; `hit@1` root +21.79pp [20.56, 23.11],
major +20.22pp [19.15, 21.43]. Per-k, every stratum's CI excludes 0 in the improving direction;
one stratum (major/k3, `all_required@4` +0.92pp [0.18, 1.83]) is statistically significant but
below the gate's +2.0pp minimum-benefit bar — see the full report §3 for the complete per-k table
and gate-by-gate detail.

**Gate status (evidence only — R1 is the unfused §6 reference, not a frozen fusion variant; no
adoption decision is made here)**: bundle completeness clears at every k for root, clears overall
and at k1/k2 for major (k3/major is significant but under +2.0pp); harmful exposure is N/A on
test-A (`distractor_rate@4` is `NaN` — no distractor labels in SKILLRET-test); primary quality
clears trivially (both hit@1 and nDCG@10 improve, they do not regress); cost was **not** evaluated
for R1 (§6: latency ignored for the reference run) because **F0 itself already fails both the
300ms and 500ms tiers** at 6,006 skills (see below) — any dense arm can only add cost on top of
that. **Adoption is decided only after a dev-tuned frozen variant is run once here**, and only
jointly with test-B (SkillRetBench, run separately).

**Latency (R4 evidence, the headline cost figure)**: whole-hook, fresh subprocess, 6,006-card
on-disk artifact, 200 warm queries, Intel Core i7-10700K WSL2 machine. Cold start 584.8ms; warm
p50 561.5ms; warm p95 638.9ms. **Both the 300ms and 500ms tiers fail** — for the shipped F0
baseline alone, with `w_dense=0` and no dense channel in play at all. Contrast: the same whole-hook
measurement at 26 skills (§1) was p50/p95 65.7/71.8ms; isolated bare-subprocess overhead is
~14-45ms, ruling out process startup as the explanation. This is a genuine architectural-scaling
finding at 6,006 skills, not a harness bug.

**Overlap caveat** (per §3): `SKILLRET-Embedding-0.6B` was trained on SkillRet train;
SKILLRET-test is a disjoint pool from the same construction — the "flattered corpus" this
programme names in advance. Test-B is the check against an unrelated corpus.

### 7.2 F5 offline enrichment

Extractor built (`tools/enrich/derive.py` + `apply.py`); the numbers
below are the sanity check against authored fields specified in the family's plan, **not** the F5
quality gate (`all_required@4` on dev/test, still pending). On SkillRetBench, deriving from
`full_text` alone (pretending authored `trigger_phrases`/`anti_triggers`/`composable_skills` don't
exist): edges (`requires ∪ similar` vs 1,241 gold `composable_skills`) precision 0.60 / recall 0.95;
`negative_triggers` token-recall of authored `anti_triggers` 0.81 / token-precision 0.69; `triggers`
token-recall of authored `trigger_phrases` 0.43 / token-precision 0.59 (token-level agreement, not
semantic — see report). On the real 2,037-skill local corpus: 97.5% of skills gained `triggers`,
24.5% `negative_triggers`, 95.5% at least one graph edge (9,484 edges total, mostly low-confidence
`similar`). Two precision bugs found and fixed this session (boilerplate `negative_triggers`
duplicated across 49–221 skills; "do not use for X" sentences misread as a trigger for X); one
precision issue found and **not** fixed — generic-English-word skill ids (`architecture`,
`onboarding`, ...) produce false-positive `similar`/`requires` edges via bare mention, documented as
a known limitation for family evaluation to address. Full report:
`docs/reports/bakeoff/F5-enrichment-2026-09-05.md`.

### 2026-09-05 — F0 and R1 on test-B (SkillRetBench), PR #30

- **F0 (shipped sparse), fair `_root` setting (no scope leak):** IR-aligned nDCG@10 **0.436** vs the
  dataset's own BM25 **0.534**; recall@10 0.519 vs 0.598. We lose on 4 of 5 settings by 6–16 pp.
  Under `node_scoped` (gold category as cwd) we read 0.676 — that number is a leak of the answer and
  is **not** the comparison. Diagnosis so far: the policy filter drops **0 / 6 473** gold skills at
  `_root`, so `negative_triggers` are not the cause; the gap is in BM25F construction (field
  weighting, tokenizer, k1/b) or protocol. The dataset does not ship `run_baselines.py`, so its
  BM25 protocol cannot be reproduced exactly. **The diagnosis moves to dev (SKILLRET train), where
  a config may be chosen**; test-B is not touched again until a frozen variant exists.
- **Structural findings that constrain every family:** `budget_constrained` has 25 required skills
  per query, so `all_required@4` is 0 by construction — that setting is excluded from the
  completeness gate and reported on its own. In `multi_skill_composition`, 77.5 % of queries have a
  required companion in a *different* category, so hard scope admissibility conflicts with bundle
  completeness — F0-closure gains +2.67 pp `all_required@4` at +2.67 pp HSR@4.
- **R1 reference (static student distilled from SKILLRET-0.6B, tooling defaults, no tuning):**
  coverage ceiling **7.64 %** overall (gold skills the dense candidates add that BM25F's top-50
  missed); every quality gate fails; HSR@4 passes where defined. Gates nothing (v2 §6). Note: this
  reference used the *distilled student*, not the full encoder; the full-encoder reference is on
  test-A (pending).
- **Korean:** 151/1 250 queries (12.1 %); all 50 abstentions in the run are Korean single-skill
  queries; Latin-only numbers are 2–4 pp higher throughout.
- **Latency at 501 skills (real hook, fresh process):** measured **p50 210.7 / p95 255.0 ms** by
  the run; profiled afterwards — the query path was 9 ms of which **84 % was `policy_filter`
  re-tokenising every skill's `negative_triggers` on every query**. Fixed (phrases tokenised once
  per Router): **p50 126.6 / p95 145.3 ms**. Remaining fixed costs: interpreter + CLI import 60 ms,
  artifact load 49.5 ms (`cards.jsonl` parsed eagerly) — the latter scales with corpus size and is
  the next R4 target once the 6 006-skill number lands.

### 2026-09-05 — F5 extractor built, PR #31

Derived from `full_text` alone on test-B, agreement vs authored fields: edges P/R **0.60 / 0.95**
(precision hurt by common-word skill ids, documented), triggers token P/R 0.59 / 0.43,
**negative triggers P/R 0.69 / 0.81**. On 2 037 local skills: 97.5 % gain triggers, 24.5 %
negative triggers, 91.1 % `similar`, 4.5 % `requires`. A semantic-reversal bug ("do not use for X"
read as a trigger for X) was found and fixed; a corpus-wide frequency guard drops boilerplate
negative phrases. Family evaluation (`all_required@4` on dev, then tests) pending.

### 2026-09-05 — full-encoder R1 reference on test-B (SkillRetBench), PR #35

Resolves the "(pending)" note in the PR #30 entry above: **the full `SKILLRET-Embedding-0.6B`
encoder** (same pinned revision as the test-A reference, not the distilled static student) run
through the product path on test-B, both `node_scoped` and fair `_root`, tooling defaults,
`w_dense=1`, no tuning. Gates nothing (v2.1 §6).

- **Fair `_root` setting:** `hit@1` **+8.33 pp** [+5.75,+11.25], `nDCG@10` +8.05 pp — both clear
  improvements, roughly a third of test-A's `hit@1` gain (+21.79 pp). `all_required@4` **+0.67 pp
  [−1.50,+2.83]** — CI straddles zero, fails the +2 pp/CI-excludes-0 gate rule outright, in sharp
  contrast to test-A's +17.96 pp [+16.80,+19.08]. HSR@4 (distractor exposure) **−10.00 pp
  [−15.67,−4.00]** — a significant reduction, the strongest unambiguous win in this run; the one
  regression is `distractor`@`_root` `hit@1` (−7.33 pp, outside tolerance).
- **Candidate coverage** (BM25F top-50 misses the dense candidates recover): **8.76 %** at `_root`,
  11.50 % at `node_scoped` — both far below test-A's **39.6 %**, and close to (a little above) the
  distilled student's 7.64 % from PR #30. Read together with the quality deltas above, this
  separates two previously-conflated effects: the full encoder generalises to an unrelated corpus
  *modestly* (hit@1/nDCG@10/HSR@4 all improve; `all_required@4` does not), while PR #30's
  distillation *separately and additionally* destroyed quality (every gate failed there, vs several
  passing here) — the cross-corpus generalisation gap (test-A → test-B) is the larger of the two
  effects and is not a distillation artifact.
- Full tables (all 5 settings × 2 node settings × all-queries/Latin-only), the IR-aligned
  comparison against the dataset's own BM25 (`_root`, where R1 now beats it on recall@10/MRR),
  the new full paired-bootstrap CI on HSR@4/`distractor_rate@4` (`hsr_bootstrap_report`, extending
  `dense_vs_b1_gate_report`'s point-estimate-only HSR row), and the overlap caveat (6/501 skill
  names, 1.2 %, exact-match with SkillRet's 6 006 — quoted from PR #30):
  `docs/reports/bakeoff/SkillRetBench-R1-encoder-2026-09-05.md`.
- Code: the encoder-backed `DenseCandidateRouter`/quantisation/cache machinery was factored out of
  `tools/eval/skillret.py` into a corpus-agnostic `tools/eval/dense_ref.py`; both `skillret.py`
  (test-A) and the new `tools/eval/skillretbench_r1.py` (test-B) now call it, rather than each
  reimplementing it.

### 2026-09-05 — dev-only diagnosis of the F0 BM25F gap, PR #36

Isolated why F0 (shipped sparse) trails each dataset's own BM25 baseline (test-B −9.8 pp, test-A
−11.7 pp nDCG@10), using only SKILLRET **train** (dev split, 10,123 skills / 1,000 queries) —
**test-A and test-B were not touched**. Nine-arm coordinate-descent ablation through the real
product path (`Index.from_cards → policy_filter → candidates → score → select`) against an
independent textbook-BM25 reference (R-BM25) on the same corpus/queries. **Attribution: the
shipped differential field weights, not BM25F's per-field normalisation, cause the gap.** Setting
`field.*` weights uniform (P-flat) closes 99.5% of the dev-measured deficit (P-shipped −3.74 pp
[−4.34,−3.07] vs R-BM25 → P-flat −0.01 pp [−0.27,+0.25], CI straddles zero) while collapsing to a
single field (P-onefield, matching R-BM25's normalisation structure) does **not** close it
(−3.90 pp, statistically indistinguishable from P-shipped) — ruling out per-field normalisation
as the driver. k1/b retuning (`0.9/0.4`) made things markedly worse (−10.60 pp); tokenizer choice
moved nothing meaningful (+0.04 pp); IDF is algebraically identical to textbook IDF (not run as a
separate arm); the abstain gate never fires (0/1,000 queries, every arm). P-noscope/P-nopprocl/
P-top200 are confirmed byte-identical to P-shipped on all 1,000 real queries (predicted from
`Router.score`/`candidates` structure: per-query-constant `w_scope`, zero-edge `requires` graph,
and a candidate-pool cap that never bound). Frozen-config proposal: `field.*` weights → 1,
everything else unchanged — a one-line `DEFAULT_WEIGHTS` change, not a structural rewrite; not
yet validated on test-A/test-B (out of scope for this diagnosis). Full report, tables, and CIs:
`docs/reports/bakeoff/DEV-sparse-diagnosis-2026-09-05.md`.
