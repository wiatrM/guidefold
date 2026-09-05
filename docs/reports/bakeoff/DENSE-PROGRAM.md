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

*(none yet — F0 and R1 running on both test corpora; dev split not yet carved)*
