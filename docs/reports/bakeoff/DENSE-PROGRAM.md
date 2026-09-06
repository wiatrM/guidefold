# Dense retrieval programme — pre-registered, v2.8

**Status:** Pre-registered 2026-09-05 (v1, PR #26); amended to v2 the same day after methodological
review; v2.1 added family F5 (offline enrichment). **v2.2 adds family F6 (offline dense sibling map), derived from a measured result and registered before F6 itself is measured.** **v2.4 adds family C (composition, ADR-0022 §4 / ADR-0024 §4), a test-corpus power rule in §3, and a §7 correction entry on what the test-B R1 result did and did not show.** **v2.5 adds family D (query decomposition for multi-skill queries), registered — per §4a's own rule — before any dev run.** **v2.6 adds family E (synthetic in-distribution training over the tenant's own skill pool), registered before any generation or training, with an explicit no-label-leakage rule.** **v2.7 (2026-09-06, owner-approved, written before any E1–E5 dev result was read) adds a family-E premise check on test-B when no E arm clears the dev gate — §4b.** **v2.8 (2026-09-06 18:20Z, owner-approved, written after E1 and its §3b diagnostic, before any E2/E3 number) adds a forgetting guard in front of §4b and fixes the E5 slot — §4c.** The v1 text is in git history. Results are appended under
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

**Power rule (v2.4, added 2026-09-05).** (a) SKILLRET-test (test-A, 4,392 queries, paired-bootstrap
CI ≈ ±1.1 pp at the completeness gate's typical effect size) is the primary corpus for the
bundle-completeness gate (`all_required@4`, §5); SkillRetBench (test-B, 1,250 queries, CI ≈ ±2.2 pp)
is the transfer test for `hit@1`/`nDCG@10`/HSR@4, and reports `all_required@4` there as
**informative only** — its CI is wider than §5's own +2.0 pp minimum-benefit bar, so test-B alone
can neither exclude nor confirm a 2 pp effect on that metric with confidence (see the §7 correction
entry below). (b) A third corpus built from synthetic (LLM-generated) labels was considered for
exactly this reason and is registered here as **not run** in this programme.

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
| **C composition** *(v2.4)* | composer stage behind `select()`'s `compose_mode` key (ADR-0022 §4 / ADR-0024 §4): (a) **deterministic** — score-plateau bundle detection (no `requires` edges needed), coverage-aware fill, `requires` closure, integer-only, `(-score, urn)` ties, in the CLI; (b) **model** — `tools/eval/composer_model.py` (never the CLI), gated by (a)'s detector, replay-cached | T300 (a) / offline eval only (b) | ≤ 6 total: C0 baseline + C-det-1..4 (τ × coverage grid) + C-model-1..2 |
| **D query decomposition** *(v2.5)* | split a multi-intent query into ≤ 4 clauses **before** candidate generation (evaluated only in `tools/eval/dev_decompose.py`, never the CLI — `select()` itself is untouched): (a) **deterministic** — stdlib clause splitter (sentence boundaries, `;`, coordinating markers), a one-clause query is not decomposed; (b) **model** — local `claude -p --model haiku`, replay-cached by `sha256(query)`. Both: per-clause product `candidates()` + `score()` on the same `Index`, merged by RRF (k = 60) across clauses plus (configurable) the whole-query ranking, composed greedily (best-scored skill of each clause first, then the merged order, to k = 4) with `requires` closure and admissibility exactly as `select()` | T300 | ≤ 6 total: D0 baseline (= C0, whole query, no decomposition) + D-det-1..3 (per-clause depth 10/20 × whether the whole-query ranking joins the RRF) + D-model-1..2 (same merge/compose, model split, depth 10/20, cache shared with D-model-1) |
| **E synthetic in-distribution training** *(v2.6)* | generate synthetic training queries over the *tenant's own* skill pool at index time — 5 per-skill natural queries + composite 2–3-skill queries (≈30 % of pairs) + 3 same-category hard negatives per positive, all from skill text alone, via a local open LLM (`Qwen/Qwen2.5-7B-Instruct`, no API, no labels) — and fine-tune a sentence embedder on them (`MultipleNegativesRanking`, in-batch negatives), then use it exactly as R1's dense candidate source (`w_dense=1`, unmodified `select()`, no fusion tuning) | T500 (0.6B) / T300–T500 (small CPU-servable base) | ≤ 6: E0 zero-shot reference + E1 (per-skill queries only) + E2 (E1 + composite) + E3 (E2 + hard negatives) + E4 (E3 recipe on a small CPU-servable base) + E5 (one hyper-parameter variant, conditional on E3 clearing the dev gate) |

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

**Why C exists (v2.4).** Every family above changes *ranking* — the order `score()` returns
candidates in. None of them can move `all_required@4` on either test corpus by itself, because
`select()` has no composition stage: it takes the literal top-k by score plus a `requires` closure,
and neither test corpus carries `requires` edges (F5, above, addresses that gap in isolation; C
addresses what `select()` does once fields exist, or once a query is a bundle for other reasons).
ADR-0022 §4 and ADR-0024 §4 specify composition as its own pipeline stage, distinct from ranking,
with two admitted implementations behind one interface: (a) a **deterministic** integer composer
that detects a bundle from the score distribution alone (no `requires` edges required), fills by
term coverage against the query, and reports `cannot_fit` rather than silently truncating; (b) a
**model** composer, evaluated only in `tools/eval/` and never wired into the CLI, gated by (a)'s
detector to bound cost. This family measures both against **C0** (shipped `select()`,
`compose_mode="off"`) on SKILLRET-train dev, freezes at most one deterministic and at most one
model configuration by the pre-registered rule in
`docs/reports/bakeoff/DEV-C-composer-2026-09-05.md`, runs the frozen composer(s) once on each test
corpus, and — dense caches permitting — re-runs the R1 dense reference (§6) with the frozen
composer, since a composer that cannot see whether a bundle is needed cannot show what dense
candidates add to one either.

**Why D exists (v2.5).** On SKILLRET-train dev (1 000 queries, k = 1/2/3 = 328/333/339; E7.3 dev,
measured 2026-09-05, in `gf-c`) the shipped path C0 has `all_required@4` 0.842 / 0.069 / **0.000**
and — the binding number — **recall@10 = 0.881 / 0.512 / 0.361** by k. For three-skill queries,
**64 %** of the required skills are not in the top-10 at all. Composition cannot fix that (C, above,
only re-orders or fills from what candidate generation already retrieved); candidate generation
must. Multi-intent queries ("onboard three hires in Rippling and then run the full lint/type/test
suite on their scripts") split their terms across skills, and BM25 ranks by total match, so the
secondary skills sink. The literature's answer is decomposition: split the request into atomic
sub-requests, retrieve per sub-request, merge, and compose one skill per sub-request
(completeness-oriented tool retrieval, e.g. COLT, Qu et al. 2024; multi-hop/query-decomposition
retrieval; SkillRouter's FC@K framing). D is evaluated the same way every family is — dev budget,
freeze, both tests once, §5's gates unchanged — with one family-specific expectation stated up
front because it is the family's known failure mode: **D is judged on `all_required@4` at k ≥ 2
and, separately, on not hurting k = 1** (`hit@1` not worse than D0 by more than 1.0 pp overall and
at k = 1) — decomposing a single-intent query wrongly (splitting a query that was never a bundle)
is exactly the failure the deterministic splitter's one-clause guard exists to prevent, and the
model splitter is asked, explicitly, to return a one-task query unchanged rather than force a split.
D never touches `select()` or the shipped CLI; every arm is evaluated only in
`tools/eval/dev_decompose.py`, wrapping the product `Index`/`Router` (`candidates()`/`score()`),
the same discipline `tools/eval/dev_sparse.py` and `tools/eval/dev_expand.py` already use.

**Why E exists (v2.6).** The same `SKILLRET-Embedding-0.6B` encoder gave `all_required@4`
**+17.96 pp** [16.80, 19.08] on SKILLRET-test — skills from the distribution it was tuned on — and
**+0.67 pp** [−1.50, +2.83] on SkillRetBench, a disjoint corpus (§7, "full-encoder R1 reference on
test-B"; §5's overlap caveat above already names this as "the flattered corpus"). SkillRet's own
queries carry a `generator_model` field (`tools/eval/corpora.py::load_skillret()` docstring) —
they are synthetic, generated by an LLM over the dataset's own skill pool, which is exactly why R1
is in-distribution on SKILLRET-test and not on SkillRetBench. Family E reproduces that recipe over
the *tenant's own* skill pool at index time — no labels, no user traffic — so that a deployment is
in-distribution from day one, on whatever skills the monorepo actually has, not on SkillRet's. It
also targets the recall gap Family D names above: **recall@10 = 0.361 at k = 3 on dev** (same
number, same run) means 64 % of required skills for a three-skill query are outside the top-10
before ranking or composition ever runs; E's **composite** queries (one natural task whose answer
is a 2–3-skill set, ≈30 % of training pairs) train the encoder to place co-occurring skills near
each other in embedding space, which candidate generation can then surface. E is evaluated the same
way every family is — dev budget, freeze, both tests once, §5's gates unchanged, plus one rule
specific to this family's premise: a frozen E recipe must clear `all_required@4` ≥ F0 + 2.0 pp
**and** ≥ E0 (the zero-shot encoder, run once on dev as this family's baseline) + 2.0 pp, both CI
excluding 0, with `hit@1` not worse than E0 by > 1.0 pp — beating the zero-shot encoder, not only
sparse, because the entire premise is that generic zero-shot dense already regresses outside its
training distribution (the +0.67 pp number above). Full detail (data, configurations, measurement):
`docs/reports/bakeoff/DEV-E-synthetic-training-2026-09-05.md`. Two rules specific to this family,
because the whole point is to show the gain is not label leakage in a different shape:

1. **No labels, ever.** The generator and the trainer read skill text only (`name`, `description`,
   `body`/`skill_md`, taxonomy/`requires`/`similar` where present) — never a dev or test query
   string, never a qrel. `tools/train/synth_queries.py` ships a leakage check that asserts, for
   every generated training query, that neither the raw string nor a normalised form (lowercased,
   whitespace-collapsed, punctuation-stripped) of it appears among the dev or test query sets; the
   check is exercised for real (not mocked) in its own test on a tiny fixture, and is run once as
   part of every generation before that batch's output is used for training.
2. **The test-once run generates from each test corpus's own skill pool.** This is not test-label
   use: the generator never reads SKILLRET-test's or SkillRetBench's *queries* or *qrels*, only
   their *skills* — exactly the unsupervised document-adaptation step a real deployment performs
   against its own tenant catalogue, stated plainly as such and not as a second look at the answer
   key. Evaluation queries for the test-once run remain each corpus's own held-out query set,
   untouched by generation.

Families are independent: F3 runs regardless of F1/F2; F4 runs regardless of F2. F1's result may
inform how much *effort* is spent, never whether another family is *allowed* to run.

## 4a. Multiplicity — the rule that stops "keep trying until one passes" (v2.3, added 2026-09-05)

The programme runs several families, each frozen once and tested once. That is a **multiple
comparisons** setting, and the honest handling has to be written down *before* it becomes
convenient. Three rules:

1. **A family's budget is spent when its frozen variant has been run on both test corpora.** Flat
   BM25F weights are now spent (PR #39): they may not be re-tested alone, whatever a later idea suggests.
2. **A combination of two families is a new variant only if both were registered before either was
   tested.** F6 (sibling map) was registered in PR #37 from the R1 result, *before* PR #39's flat-weight
   test — so "flat weights + F6" is a legitimate single new variant with its own single test run.
   A combination invented *after* seeing a failure, to rescue it, is not.
3. **Every test-corpus run is counted in the final report**, so a reader can judge the multiplicity
   themselves. Running k variants and reporting the best of k without saying k is the failure mode
   this section exists to prevent.

## 4b. Family E premise check — v2.7 amendment (registered 2026-09-06T11:24Z, before any E1–E5 dev result)

**State at registration.** Per-skill generation complete (50,160 queries, 0 leakage violations
against dev/test-A/test-B), composite generation running, **no E1–E5 checkpoint, encode or dev run
exists** (`docs/reports/bakeoff/validation/` holds only E0). The owner approved this amendment on
the recommendation below, in writing, at this point.

**Why the dev gate cannot measure E's premise.** Family E exists because the zero-shot encoder
(E0) gave `all_required@4` +17.96 pp on SKILLRET-test (its own training distribution) and
+0.67 pp [−1.50, +2.83] on SkillRetBench (disjoint) — the premise is *out-of-distribution
recovery* through label-free adaptation on the tenant's own catalogue. But the dev split is
carved from SKILLRET-train, i.e. **E0 is already in-distribution on dev** (its training queries
include multi-skill tasks over these very skills). The freeze rule "≥ E0 + 2.0 pp on dev" is
therefore evaluated exactly where E0 is strongest and where E has the least to add; a recipe can
fail it while the premise is true, and pass it without saying anything about the premise. Left as
registered in v2.6, a dev failure would end the family with the actual question unanswered.

**Rule.** If, after E1–E5 are measured on dev, **no E arm clears the v2.6 freeze gate**, then:

1. The **best-on-dev E recipe** — highest `all_required@4` in its better retrieval mode
   (`hybrid` / `dense-only`, per the report's §0 addendum); ties broken by `hit@1`; the choice
   is mechanical and recorded before step 2 starts — is run **once on test-B (SkillRetBench)**:
   generate per-skill + composite queries + hard negatives from SkillRetBench's **501 skills only**
   (family rule 2 already permits this: skills, never queries or qrels), fine-tune the **same base
   with the identical recipe and hyper-parameters** (no re-tuning of anything on test-B), and
   evaluate through the unchanged product path in that recipe's chosen mode, on test-B's own
   1,250 queries. Leakage check against test-B's queries runs before training, as for dev.
2. Paired baselines on test-B, same mode: F0 (exists), and E0 in the same mode (the recorded
   test-B reference is the hybrid R1 run; if the chosen mode is `dense-only`, E0 is run in that
   mode on test-B as a fixed reference — no selection is involved in a zero-shot reference).
   Report `all_required@4`, `hit@1`, `nDCG@10`, `HSR@4` with paired-bootstrap 95 % CIs, both
   scopes as in the PR #35 entry.
3. **This consumes test-B's "once" for family E.** No second E variant, mode or hyper-parameter
   may be run on test-B afterwards, whatever the result. **test-A is not touched** by this
   amendment: it is in-distribution for E0 and would only repeat the flattered comparison; it is
   reached only by a recipe that freezes normally.
4. **What the result decides — and does not.** This is a *premise check*, not an adoption path.
   A positive result (E-on-tenant-catalogue ≥ E0 + 2.0 pp `all_required@4` on test-B, CI
   excluding 0, `hit@1` and `HSR@4` within the §5 tolerances) adopts nothing — §5 still requires
   both corpora — but earns the family a v2.8 that must first *build a labelled OOD dev split*
   (none exists today; that is the real gap) before any further configuration. A negative or
   inconclusive result terminates the family with numbers, per §5's termination sentence, and the
   programme records that per-tenant synthetic adaptation did not recover the OOD gap on the one
   corpus that could show it.

**Why this is not cherry-picking.** The rule, the recipe-selection criterion, the mode rule, the
baselines and the interpretation are all fixed here before any E dev number exists; the only
thing the dev results choose is *which* single recipe gets the one pre-committed run. Writing the
same rule after seeing dev results would be exactly the selection-set problem §0 point 2 exists to
prevent, and would not be allowed.

## 4c. Family E forgetting guard and the E5 slot — v2.8 amendment (registered 2026-09-06 18:20Z)

**State at registration.** E1 measured on dev (§3a of the family report: −9.5 pp `all_required@4`
dense-only vs E0) and diagnosed (§3b): +14.5 pp hit@1 on its own training pairs, −10.5 pp recall@10
on *unseen* queries from the same generator — memorisation with loss of general retrieval, i.e.
forgetting, not adaptation. E2 is at step ~300/1,122 with no dev number; E3/E4 not started. The
owner approved this amendment in writing at this point.

**Rule 1 — forgetting guard.** No family-E recipe takes the §4b premise check on test-B unless it
is *not worse than E0* on the held-out same-generator composite set of §3b (1,000 composite
queries never used in training; recall@10 Δ vs E0 ≥ 0 and its 95 % CI excluding a loss larger
than 2 pp; `tools/eval/dev_dense_diag_e1.py`). test-B cannot distinguish "adapted" from
"forgot"; the guard can, on data we own, so it goes first. A recipe that fails the guard is
recorded as *forgot*, and §4b is not spent on it.

**Rule 2 — the E5 slot (≤ 2 dev configurations, chosen for evidence, not tuned on dev).**
(a) **Weight-space interpolation** (WiSE-FT, Wortsman et al. 2022) between E0 and the fine-tuned
model: θ(α) = α·θ_E0 + (1−α)·θ_E1, α ∈ {0.5, 0.75}. *Both* αs are scored on the guard set
(cheap, CPU, our own synthetic data — not dev, not test); the α that passes Rule 1 with the higher
guard recall@10 is the **single** E5 dev configuration, measured exactly as E1–E4 (both modes, F0
and E0 baselines, paired CIs). If E3 later scores higher than E1 on the guard set, the
interpolation partner becomes E3 — same rule, still one dev configuration. (b) Only if no α
passes Rule 1: **LoRA** (rank 16, lr 1e-4, same data) with **round-trip filtering** of the
synthetic queries (keep a query only if E0 ranks its source skill in its top-10; doc2query-- /
SkillRet practice), one run, same guard, same dev measurement. (a) and (b) together are the
family's remaining budget; the ≤ 6 cap of §4 is unchanged (E0–E4 + one E5).

**Rule 3 — what the guard is not.** Passing the guard proves the recipe did not destroy the
encoder; it says nothing about the premise. The premise is still decided only by §4b, once, on
the guard-passing recipe with the best dev `all_required@4` in its better mode. If nothing
passes, the family terminates with "none of the studied variants earned deployment" and the
premise recorded as *untested by a sound recipe*, not refuted.

**Rule 3a (v2.8.1, 2026-09-06 18:50Z — written after the α = 0.75 guard result (PASS, Δ = 0.0 pp
[−0.68, …]) and before its dev run was read).** A guard-passing recipe takes §4b only if it also
shows a *gain* on dev over E0 in its better mode (`all_required@4` ≥ E0 + 2.0 pp, CI excluding 0)
or, failing that, at least a positive point estimate on both `all_required@4` and `hit@1`. A recipe
that passes the guard by being indistinguishable from E0 (the interpolation's trivial fixed point:
α → 1 recovers E0 exactly) has no adaptation signal to test on test-B, and running it there would
spend the family's one test-B run to re-measure E0. In that case the family terminates with
"no sound adaptation recipe found: the fine-tune direction carried memorisation, not transferable
signal" — and the premise stays *untested*, not refuted.

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

### E1.1b service protocol v2 — separate versioned note (2026-09-05)

This service-protocol note supplements the historical programme; it does not change the original T300/T500 cost row above, any quality gate, historical measurement or adoption decision. It does not authorize another test-corpus run; the frozen evaluation protocol still applies.

E1.1b service protocol v2 (2026-09-05) requires whole-client p95 ≤400 ms over loopback, measured separately at c1 and c4 with a fresh client process per request and a ready resident server/index. Server-side p95 must be ≤300 ms at both loads, measured from HTTP admission before authentication or queueing through synchronous logging and JSON response serialization. Whole-client timing includes startup/imports, local reads, auth, transport, queues, retrieval/composition, telemetry and output/exit. Report all attempts, errors and successful-within-budget counts under frozen workload, corpus, hardware and runtime identities. WAN/TLS/IAM and the actual harness remain a separate E6 integration gate, never implied by loopback success. Optimized sparse is the production candidate; hybrid remains shadow until independent latency and quality admission.

Protocol v2 uses inclusive ≤ comparisons. Historical T300/T500 budgets and E1.1b JSON evaluated with strict <400 retain their original definitions and results. Historical T300 means the whole hook in a fresh process, not an in-process kernel or the new server-side 300 ms target. A p95 target is not hard cancellation; the server allocation provides planning headroom, not a guarantee that the client target passes.

Measured service results and the sparse proceed / hybrid shadow decision are tracked in [E1.1b service feasibility](E1.1b-service-feasibility-2026-09-05.md).

## 6. Reference run R1 — what it is and is not

R1 (already running on both test corpora, unfused config chosen from tooling defaults, latency
ignored) is kept as a **reference**: it shows what a tuned encoder does through the product path
before any dev tuning. Its numbers are reported. They gate nothing. Its coverage figure — gold
skills BM25F missed that the encoder finds — is the most useful number it produces, because it
bounds how much *any* dense signal could add to candidates on these corpora.

---

## 7. Results (appended as they land; §1–6 are frozen from v2)

### 2026-09-05 — frozen sparse variant (flat BM25F weights) once on both tests, PR #39 — NOT ADOPTED

The dev diagnosis (PR #36) chose uniform `field.*` weights; this was its single test run.

| | test-A `_root` | test-B `_root` |
|---|---|---|
| hit@1 | **+7.72 pp** [6.94, 8.58] | **+5.25 pp** [3.75, 6.83] |
| nDCG@10 | **+6.44 pp** [6.04, 6.85] | **+4.31 pp** [3.70, 5.00] |
| `all_required@4` | **+4.99 pp** [4.37, 5.62] | **+2.92 pp** [1.67, 4.25] |
| HSR@4 (`distractor_rate@4`) | no labels | **+4.67 pp worse** — breaches the ±1.0 pp guardrail ~5× |

It closes **58.2 %** of the gap to test-A's own BM25 baseline and **43.1 %** of test-B's. Every
criterion passes on test-A; on test-B it passes three and fails the harmful-exposure guardrail,
isolated entirely to the adversarial `distractor` category (n=300), where flat weights pull in more
correct skills **and** more labelled distractors at once.

**Not adopted**, because acceptance was pre-registered as a conjunction across both corpora and one
breach is a no. The measured trade is now on record: **+5 to +8 pp of quality for +4.67 pp of
harmful exposure.** Whether that trade is worth taking is a product judgement, not a gate — and it
is precisely the trade family F6 (registered in PR #37, before this run) was designed to remove.
If F6 reduces exposure on dev, "flat weights + F6" is a legitimate new frozen variant under §4a.2
with its own single test run.


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

### 2026-09-05 — lazy artifact load (R4), hook p95 at test-A scale not yet under the T300 gate

Infra fix, not a retrieval-method arm: `cards.jsonl`/`graph.json` were parsed whole on every hook
invocation, cost scaling with corpus size (p95 639ms at 6,006 skills, both T300/T500 gates
failed). Made cards/graph lazily mmap-backed (`cards.idx`/`cards.hdr`, `graph.bin`/`graph.idx`;
`graph.json` dropped), cutting CLI import cost, artifact 14.9MB → 13.3MB. Result: p95 639 → 581ms
at 6,006 skills — saves the ~46ms this fix targeted, but **T300/T500 still fail**: profiling found
the larger, pre-existing, untouched cost is eager `terms.bin`/`postings.idx` parsing (~250ms of
~271ms load time), which scales with vocabulary (89,630 terms) not doc count — a natural "R5"
candidate. Full breakdown: `docs/reports/bakeoff/R4-latency-lazy-load-2026-09-05.md`.

### 2026-09-05 — F3 document expansion (doc2query) on dev, PR #41

Doc2query/msmarco-t5-base-v1 pseudo-queries (`n=5`/skill, deterministic sampling, seed 42) indexed
as a sixth BM25F field (`expansion`) or appended into `body`, against the frozen **P-flat**
baseline (not P-shipped), on the same 10,123-skill/1,000-query dev split as PR #36. All three
arms (field weight 1, field weight 2, append) beat P-flat on `nDCG@10`/`recall@10` with every
paired-bootstrap CI excluding zero (+0.8–0.9 pp / +1.0–1.2 pp overall) and are purely additive on
coverage (16–20 gold skill-instances recovered into BM25F's top-50, **zero lost**, of 2,011
required), at near-zero cost (index +1.1–3.9%, query latency indistinguishable from baseline, no
query-time model). `all_required@4` moves only **+0.5 to +0.7 pp**, well under §5's +2.0 pp
test-adoption bar for that metric, so the frozen proposal below is not expected to clear gates on
test with confidence. **Frozen proposal:** `expansion` field, `n=5`, weight 2 (best point estimate
of the three, best coverage recovery, negligible cost) — proposed for the TL's once-per-family
test-A/test-B run, with that calibrated caveat. 4th dev-budget slot intentionally not spent
(weight1→weight2 already shows diminishing/mixed returns). Full report, tables, samples, CIs:
`docs/reports/bakeoff/DEV-F3-doc-expansion-2026-09-05.md`.

### 2026-09-05 — R4b: lazy terms.bin/postings.idx closes R4's open item; T0 size curve

Infra fix, not a retrieval-method arm — closes R4's named follow-on ("R5"): `terms.bin`
(per-term IDF) and `postings.idx` (the `(field,term)→(offset,length)` table) were the *larger*
remaining eager-parse cost R4 left untouched (~250ms of ~271ms `load_index_artifact` at 6,006
skills, scaling with vocabulary, not doc count). Both now get the same mmap+binary-search
treatment `postings.bin` already had: a fixed-width sorted directory searched in `O(log V)` per
term, never materialised as a Python dict. **Parity**: 0/1,000 mismatches vs. `main`'s CLI on the
frozen SKILLRET-train dev queries, at 6,006 skills, hashing ranked list + selected set through the
real product path — no score changed. **Latency at 6,006 skills**: p95 581.2ms (R4-after) →
**320.5ms**, p50 511.3ms → 258.2ms; **T300 still FAILS** (320.5ms, stable on rerun at 347.5ms),
**T500 now passes with margin**. **T0 size curve** (deterministic subsets, sorted skill id, first
N): 500/1,000/2,000/4,000 skills all pass T300 (p50 91.5–206.7ms, p95 113.3–261.7ms); the
interpolated T300 crossover sits at **≈5,300 skills** — below that, ADR-0021 sharding buys a
consumer monorepo nothing not already free; at/above it (including this programme's own
6,006-skill benchmark corpus), sharding or a further load/query-time optimization is still
required for T0 admission per ADR-0024 §1. Artifact size: -4.6% net at 6,006 skills despite
`terms.bin` growing 20.6% (fixed directory overhead) — `postings.idx` shrinks 48.6% (a term's
bytes are now stored once, not once per field). Full breakdown, tables, machine-quiet log:
`docs/reports/bakeoff/R4b-lazy-terms-postings-2026-09-05.md`.

### Correction, 2026-09-05 — what R1 on test-B did and did not show

The full-encoder R1 reference on test-B (§7, "full-encoder R1 reference on test-B (SkillRetBench),
PR #35") is quoted elsewhere, correctly, as failing the adoption gate: `all_required@4` **+0.67 pp
[−1.50, +2.83]** on test-B, CI straddling zero, in contrast to test-A's **+17.96 pp
[16.80, 19.08]**. Read alone, that reads as "dense failed the completeness gate on foreign data."
The same run also measured `hit@1` **+8.33 pp [5.75, 11.25]** and `nDCG@10` **+8.05 pp** — both
clear, significant improvements — and HSR@4 (harmful-sibling exposure) **−10.00 pp
[−15.67, −4.00]**, the strongest unambiguous win measured anywhere in this programme so far. Three
of the gate's four criteria were clean wins; only `all_required@4` did not move, and it could not
have: this programme's own dev diagnosis of the k = 3 (three-required-skill) stratum reads
`all_required@4` at **0.000 for every arm**, sparse or dense, because `select()` has no composition
stage — a ranking change cannot lift a metric that composition alone gates (family C, §4, exists to
remove exactly this confound). The [−1.50, +2.83] interval is also, independently, underpowered:
at test-B's 1,250 queries, the gate's own +2.0 pp minimum-benefit bar sits inside the metric's
typical CI half-width (the §3 power rule). Net: R1 failed the pre-registered *gate*, correctly,
because the gate requires all four criteria and one was unmet — but "failed the gate" was true of
the gate's applicability here, not of the model's quality. Once family C's frozen composer exists,
§Step 2 of the E7.3 composer work re-runs this exact R1 configuration to check whether the
confound was the whole story.

### 2026-09-05 — requested Go/ParadeDB service reference, retrieval NOT ADOPTED

The owner explicitly requested a new database-backed native service and measurements.
[Its report](GO-PARADEDB-2026-09-05.md) records one configuration, zero quality tuning,
and one run on DEV/test-A/test-B/regression, separately from the spent F1–F6/C families.
Loopback latency passes: fresh-client p95 117/138 ms at c1/c4. Test-B HSR@4 worsens by
10.67 pp [5.33, 15.33], exceeding the +1 pp guardrail, so the new retrieval profile is
not admitted. All test outcomes are retained, and this entry grants no extra family
or test reruns. The [GPU serving proposal](DENSE-SERVING-NEXT-2026-09-05.md) concerns
inference engineering and future DEV work; it does not change frozen quality results.

### 2026-09-05 — GPU service integration audit (two fixed DEV treatments)

Cross-session accounting: the Codex service session ran **two prespecified neural
DEV treatments**, pure SKILLRET dense and equal RRF k=60 BM25F+dense, against the
unchanged F0. Registered before evaluation in `GPU-HYBRID-PROTOCOL-v1.md`, commit
`17220fd4498675c6d20bb9a31928dcb45e96a94e`. The batch=1 control was selected on numerical
repeatability/latency before quality labels were aggregated. No fusion weight was
fitted. These observations belong in the common ledger; they do not silently grant
a separate tuning budget to the service session. Any further tuning must use the
centrally allocated remaining family budget, including other sessions' trials.

The 1000 IDs are **q-train-*** from SKILLRET train. The encoder was trained on that
partition; exact query/pair overlap cannot be ruled out without training logs.
Hit@1 88.7% / all_required@4 47.0% (dense) reproduce in-distribution behavior and are
not new independent quality evidence. Equal hybrid gives 83.9% / 37.5%, counting its
one HTTP timeout as a miss. F0 is 71.3% / 30.0%. No test-A/test-B query was rerun.
HSR remains null; historical test-B +0.67 pp with CI crossing zero remains unchanged.
This does not reopen a spent family or admit a neural default.

Engineering progress is separate: pinned TEI pure dense passed loopback server c4
p95 130.7 ms and burst-fresh whole-client p95 288.1 ms; hybrid batch=1 passed 124.9 ms
server c4 and 332.3 ms burst-fresh whole-client. Both had 800/800 successful latency
requests and 0/600 cross-arm ranked/selected hash differences. The older serialized
86 ms encoder measurements retain their original scope. Budgets remain 300/400 ms.

[Full audit and all arms](GPU-SERVICE-2026-09-05.md). No more neural quality variants
are scheduled by this service change; the next integration is authenticated Postgres
event ingestion, then background shadow joined by search_id. Default responses stay sparse.

### 2026-09-05 — family D (query decomposition) dev run: no arm frozen, gate failed on the hit@1 guard

Six arms (D0 = C0, D-det-1/2/3, D-model-1/2 — pre-registered above, PR #51) on the same
SKILLRET-train dev split as F0/F3/C0 (10,123 skills, 1,000 queries). Splitting a multi-intent
query into ≤ 4 clauses (deterministic marker rules, or `claude -p --model haiku`, replay-cached),
retrieving per clause, and RRF-merging into a synthetic scored list before the real `select()`
call **does** recover completeness at k = 2/3 (`all_required@4` +7.5 to +10.5 pp) and clears the
primary bar overall (+1.70 to +2.80 pp, four of five arms with CI excluding 0 and ≥ +2.0 pp) — but
does so by demoting the single best match on already single-intent queries: `hit@1` falls
4.00–9.60 pp overall and 6.71–11.28 pp at k = 1, 4×–11× past the pre-registered ±1.0 pp guard, on
every one of the five arms. **No D-det arm and no D-model arm is frozen** — the guard fails
categorically, not marginally, so no amount of within-budget tuning was attempted to rescue it, per
the pre-registered "a gate that fails is a valid result" rule. Cost would have been independently
disqualifying: ≈610–770 ms extra p95 latency at 6,006 skills for the 2.9–3.7 mean extra
`candidates()` calls a decomposed query pays, before counting the model splitter's own 6–7 s/call
when uncached. A genuine bug (bare ASCII periods splitting inside code identifiers/filenames, e.g.
`Node.js`, `vite.config.ts`) was found and fixed pre-measurement by requiring trailing whitespace
after ASCII sentence-enders; the resulting ~95–99% decomposition rate on this corpus is a measured
finding (paragraph-style enumerations triggering the brief's own marker list), not a residual
splitter bug. This dev-only result is independent evidence for the direction PR #55 (also merged
2026-09-05) already took at the agent/harness layer — repeated `find()` calls composed by the
calling agent, rather than decomposition inside `candidates()`/`select()` — since decomposing
in-ranker recovers exactly the same completeness gap but cannot do so without the k = 1 damage this
gate exists to catch. Full tables (per-k quality, candidate ceiling @4/10/15/50, paired CIs vs D0,
cost/latency, freeze-gate detail): `docs/reports/bakeoff/DEV-D-decomposition-2026-09-05.md`.

### 2026-09-05 — family C (composition) dev run: no arm frozen in either family

Six arms (C0 + C-det-1..4, pre-registered grid over score-plateau τ ∈ {15,30} × coverage-aware
fill on/off; C-model-1/2, `claude -p --model haiku` gated/ungated, pre-registered on a 150-query
k-stratified subsample — PR #47) on the same SKILLRET-train dev split as F0/F3/C0/D0. The
score-plateau bundle detector fires on **100 % of dev queries at every τ**, but only changes
anything when coverage-aware fill is on: with it off, the fallback is provably byte-identical to
C0 on all 1,000 queries (`C-det-2`/`C-det-4`); with it on, `all_required@4` **regresses** −3.2 pp
overall, −12.5 pp at k = 1 (`C-det-1`/`C-det-3`), because covering unique query terms outranks
the single best-scored answer once that answer's terms are already "covered." Both model arms'
`all_required@4` point estimates are positive (+2.7 to +4.0 pp overall, +10.0 pp at k = 2) but
neither's CI excludes zero on the low side. `C-model-1`'s CI is negative on the low side
(ci_low=−0.0133) and its guard also fails — a clear non-qualifier. `C-model-2`'s CI is
`[0.0, +8.0]` pp — low edge exactly 0.0, entirely non-negative — which is **inconclusive, not
negative**: the pre-registered rule requires `ci_low > 0` strictly, so it does not qualify, but
the 150-query pre-registered subsample lacks the power to say whether the true effect is above or
below zero. Resolving that needs the full 1,000-query dev run (≈850 more queries beyond the
150-query subsample, ≈$16 at this run's own measured per-call rate) — not run here (would be a
result-driven scope expansion), recorded as an open follow-up in
`docs/reports/bakeoff/DEV-C-composer-2026-09-05.md` ("Open follow-up"). **No arm qualifies in
either family** — the deterministic family has no config that both changes the ranking and helps,
and the model family's best result is inconclusive at the boundary rather than clearing it; the
mechanical freeze decision is unaffected either way: **nothing frozen**. Test-once (both corpora)
and the R1 dense re-run this family exists to unblock
(§7, "requested Go/ParadeDB service" entry above, and the R1/test-B entry's own note) are both
skipped, per the pre-registered "freeze, then test" order — nothing froze, and R1's dense caches
are independently confirmed absent from `~/.cache/guidefold/` regardless. A live model-arm
infrastructure failure (65.3 % of calls failing, 97 % of those a fast `exit 1` with empty stderr
rather than the expected timeout) was root-caused as transient shared-machine load rather than a
composer_model.py defect (manual/sequential calls succeeded once load eased) and resolved by
retrying the same pre-registered scope, not by expanding it — 1,000-query expansion of the model
arms was considered and rejected as a result-driven, post-hoc scope change of exactly the kind
this project's dev/test corpus discipline exists to prevent (see PR #19). Full tables (per-k
quality, bundle-detector firing/identical-to-C0 rates, candidate ceiling @4/10/15/50, paired CIs
vs C0, freeze-gate detail, model-arm reliability investigation and $2.88 total cost):
`docs/reports/bakeoff/DEV-C-composer-2026-09-05.md`.

### 2026-09-06 — family E (synthetic in-distribution training) dev run: terminated under v2.8.1 rule 3a, nothing frozen, premise untested

Full detail: `docs/reports/bakeoff/DEV-E-synthetic-training-2026-09-05.md` (§1 data, §2 implementation
notes incl. four bugs caught before any number was read, §3a–§3c results, §3b diagnostic, §4 decision).
Data: 50,160 per-skill + 8,694 composite synthetic queries (local Qwen2.5-7B, 0 leakage against
dev/test-A/test-B), 18,720 hard-negative records, 100-group manual audit 74/25/1. **E1** (full
fine-tune, per-skill rows): dense-only `all_required@4` 37.1 % vs E0 46.6 % (**−9.5 pp
[−11.6, −7.6]**), `hit@1` −4.6 pp; still +7.2 pp over F0. Diagnostic: +14.5 pp hit@1 on its own
training pairs, **−10.5 pp recall@10 on unseen queries from the same generator** — memorisation,
not adaptation. **E5** (v2.8 WiSE-FT): α 0.5 fails the forgetting guard (−2.55 pp); α 0.75 passes
(Δ 0.0) and equals E0 on dev (`all_required@4` −0.9 pp [−2.1, +0.3], `hit@1` +1.3 pp [0.0, +2.7]).
Rule 3a: no dev gain → no test-B run. E2/E3/E4 not run (same recipe; pipeline stopped after the
E2 checkpoint was truncated by a reboot). **Decision: "no sound adaptation recipe found: the
fine-tune direction carried memorisation, not transferable signal."** The family's premise
(label-free per-tenant adaptation recovering the OOD gap) is untested, not refuted; a next attempt
needs a labelled OOD dev split first (§4b) and rule 2b's recipe (LoRA + round-trip-filtered
queries). GPU: ≈ 3.5 h training + ≈ 2.5 h encodes, local; API cost $0.

### 2026-09-06 — family F6 (offline dense sibling map): F6-2 frozen on dev, HSR@4 −0.3 pp on test-B, NOT ADOPTED; premise refuted on the labelled corpus

Full detail: `docs/reports/bakeoff/DEV-F6-sibling-map-2026-09-06.md`. Four configurations on dev
(harness bug — query not passed to the rule — found by the exposure diagnostic and fixed before
any number was read): F6-2 (τ 0.80, N 3, margin) freezes mechanically with exposure-proxy −1.5 pp
and `all_required@4` −0.9 pp [−1.6, −0.3]; the discriminating-term rule picks the gold 33 : 30 on
dev's rule-able pairs. Test-once on SkillRetBench: **HSR@4 0.7433 → 0.7400 (−0.3 pp [−1.0, 0.0])**,
`all_required@4` −0.1 pp, the map holds **6 pairs of 501 skills**. Post-hoc: the benchmark's 9,209
labelled (gold, distractor) pairs sit at E0 cosine **p50 0.12, p90 0.34; 0.1 % ≥ 0.80** — the
encoder's −10 pp HSR (PR #35) came from ranking distractors low against the *query*, not from
near-duplicate pair geometry. There is no precomputable pair structure to ship; the v2.2 premise
is wrong on this corpus. Test-A not run (gate of record failed). **Not adopted; budget spent.**

**Programme status after these two entries.** Families F1–F6, C, D, E have all spent their dev
budgets; no frozen variant cleared §5 on both corpora. Per §5's termination sentence: **"none of
the studied variants earned deployment."** Best dev result per family and the gate each failed
are in the entries above and in each family's report. The one dense measurement that remains
unrefuted and unexploited is the query-time encoder's HSR reduction on test-B, which no T300
shape captured; it is a T500/T1-service question, not a programme-level one, and it is parked.
