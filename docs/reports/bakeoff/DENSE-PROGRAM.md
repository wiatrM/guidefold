# Dense retrieval programme — pre-registered, v2.1

**Status:** Pre-registered 2026-09-05 (v1, PR #26); amended to v2 the same day after methodological
review; **v2.1 adds family F5 (offline enrichment) — still before any result was measured.** The v1 text is in git history. Results are appended under
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
| **F5 offline enrichment** *(v2.1)* | derive the fields real skills lack — `triggers` from "when to use" sections, `negative_triggers` from "do not use", `requires`/`similar` edges from body mentions of other skills — at index time (GoS "parser-first normalisation"; SkillRetBench's own `trigger_phrases`); the runtime is unchanged sparse | T300 | ≤ 4 (which sections; edge threshold; whether an LLM pass is allowed) |

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
