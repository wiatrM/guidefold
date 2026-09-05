# Dense retrieval programme — pre-registered

**Status:** Pre-registered 2026-09-05, **before any result below was measured.** Results are appended
under §6 as they land; the hypotheses, gates and stop rules above §6 are frozen.
**Goal (user, verbatim intent):** make dense earn its place by beating everything else *methodically*
— on real data, through the product path, inside the budget — and **stop honestly if it cannot.**
**Governs:** ADR-0020 (gate wording), ADR-0022 (product path), `CLAUDE.md` § Evaluation corpora.

---

## 1. The constraint that shapes every option

The hook is a **fresh Python process, stdlib + PyYAML, ≤ 300 ms warm.** No torch, no numpy, no
resident model. Whatever "dense" means at query time, it must be integer arithmetic over a table
that ships inside a ≤ 15 MB artifact (ADR-0021). Everything neural therefore runs **offline** — at
index build — and the research question is:

> Which offline-computed signal, served through integer arithmetic at query time, adds the most to
> BM25F + `requires` closure on real labelled skill data?

## 1a. Why the budget is 300 ms and Python, and what a rewrite would and would not buy

Measured, fresh process, this machine: whole hook **p50 65.7 ms / p95 71.8 ms** at 26 skills, of
which ~40 ms is interpreter start-up; BM25 + static dense at **2 000 skills is 37 ms** of query
work. The static path has 4–5× headroom — Python is not the bottleneck for anything on rungs R0–R2d.

A 0.6B encoder is ~60 GFLOP per query: **0.5–1 s on a laptop CPU in any language** (torch is
already C++). A rewrite does not make the ceiling servable. What a compiled runtime *would* unlock
is a ~22M-parameter contextual encoder (~2 GFLOP, 20–50 ms CPU) — rung R2e — at the cost of the
stdlib-only constraint and bit-reproducibility. That trade is decided by R1's evidence, not up front.

Artifact economics under ADR-0021: teacher weights (1.2 GB) never reach the user; the word table
(8–15 MB) is keyed by teacher version, downloaded once, cached for months; postings shards (~3 MB)
are what change per merge. Table size is therefore not a constraint; **shard** size is.

## 2. What the literature says we should expect (read before, not after)

| source | expectation | implication for the ladder |
|---|---|---|
| **SkillRet v3**, leaderboard | untuned 0.6B encoder +10 nDCG over BM25; **skill-tuned** 0.6B **+30** | the ceiling is high *if* the encoder is task-tuned — test the tuned teacher first |
| **SkillRet v3**, Terminal-Bench | +30 nDCG → +0.3 % task success | retrieval gain is a proxy; do not over-claim |
| **BEIR** | dense weak out-of-domain; BM25 robust; late-interaction/rerank best zero-shot at high cost | a *static* student is further out-of-domain than any encoder; expect a large distillation loss |
| **SkillRouter v5** | body signal 37–44 pp; hard negatives from 4 sources essential; "fine-tuning > scale" | any trained student uses 4-source negatives; body must be in the encoder's input |
| **Graph of Skills** | dependency bundle > top-1; propagation +5 reward at 1 000 skills | judge on `all_required@4`, and keep closure in every arm |
| **SkillResolve** | same-capability risky siblings are the failure mode | HSR@4 is a gate, not a footnote |
| **SIF / model2vec** | mean-pooled static vectors lose compositionality; model2vec weighting is `a/(a+p)` not `log(1+rank)`; **potion-retrieval** static models exist, trained for retrieval | test a prebuilt retrieval-trained static model before training our own |
| **doc2query / document expansion** (ADR-0009 "B1+") | neural at index time, sparse at query time; strong zero-shot in BEIR-class results | the only option with **zero** query-time cost; must be on the ladder |
| **RRF** (Cormack) | rank fusion designed for TREC pools of thousands; discards magnitudes | on 8–18-candidate pools use **score-level** fusion with weights fixed on a *train* split |

## 3. The ladder — each rung has a stop test

Run in order. A rung is not started until the previous one's stop test is passed.

| rung | what | stop test (if it fails, the programme ends here) |
|---|---|---|
| **R0** | B1 (shipped: BM25F + filter + closure, `w_dense=0`) on SkillRetBench and SKILLRET-test, product path, 4 cards | — (baseline; must exist) |
| **R1 — ceiling** | the **full skill-tuned encoder** (`SKILLRET-Embedding-0.6B`, GPU) as the dense candidate source, fused with BM25F, same product path, **latency ignored** | if the ceiling does not beat R0 on `all_required@4` with HSR@4 non-worsening on **both** corpora, **no served dense can** — stop, report the ceiling |
| **R2 — served candidates** *(only if R1 passes)*, each an offline signal + integer query time | | |
| R2a | model2vec-proper distillation of the R1 teacher (their weighting, PCA-256, int8) | keep any R2 variant only if it retains ≥ 50 % of the R1 gain on `all_required@4` |
| R2b | prebuilt **potion-retrieval** static model, quantised to our table format | " |
| R2c | **document expansion**: teacher generates pseudo-queries per skill offline; BM25F indexes them as a sixth field; query time unchanged | " (this rung has zero query-time cost; it is the one most likely to survive the budget) |
| R2d | **trained static student** on SKILLRET *train* (63 259 pairs; 4-source hard negatives; contrastive) | " — heaviest; run only if R2a–c all fail the 50 % test |
| R2e | **small contextual encoder** (~22M params, MiniLM-class, ONNX) in a compiled runtime — the only rung that needs a language change | " — **and** an ADR: it breaks stdlib-only and bit-determinism (float), so it is a product decision, taken only if R1 shows a ceiling that no static rung retains |
| **R3 — fusion** | replace RRF with score-level convex fusion; weight chosen **only on SKILLRET train**; report on both test corpora | adopt only if it survives both test corpora |
| **R4 — gates** | for every survivor: `all_required@4` ≥ R0, HSR@4 ≤ R0, warm p95 ≤ 300 ms on the **6 006-skill** index (fresh process), artifact ≤ 15 MB | a variant that fails any gate on either corpus is **not adopted**, whatever its average |

## 4. Rules that cannot be relaxed after seeing results

1. **Product path only.** `policy_filter → candidates → score → select(admissible=…)`, 4 cards. No arm bypasses the filter. A dense arm's contribution is measured first as **coverage** — gold skills it adds to the candidate pool that BM25F missed — and only then as re-ordering.
2. **Tune on SKILLRET train, never on either test set.** SkillRetBench has no train split: it is test-only for every decision.
3. **Two corpora, both must agree.** A win on one and a loss on the other is a "no".
4. **Per-query rankings written for every run** (JSONL, committed) — paired comparison, not averages.
5. **Latency is the whole hook, fresh process, on the 6 006-skill index**, warm p50/p95, machine stated. Batch time ÷ n is not latency.
6. **Overlap caveat.** `SKILLRET-Embedding-0.6B` was trained on SkillRet train; SKILLRET-test is a disjoint pool from the same distribution, SkillRetBench is a different dataset. Report both; the SkillRetBench number is the less flattered one.
7. **The report says "does not earn it" if that is the answer.** A ceiling that beats BM25 but cannot be served inside 300 ms is a real, publishable finding; it is not a licence to ship the ceiling.

## 5. What "best skill-retrieval model on the market" would have to mean

Not the highest nDCG on a leaderboard — SkillRet-8B already owns that at a cost we cannot serve.
It means: **the highest `all_required@4` at the lowest HSR@4 that a developer's machine can compute
in 300 ms with no model installed.** If R2c (expansion) or a static student reaches within a few
points of the R1 ceiling at zero query-time cost, that is a stronger product than any encoder that
needs a GPU. If nothing does, the honest product is BM25F + closure, and this document says why.

---

## 6. Results (appended as they land; §1–5 above are frozen)

*(none yet — R0 running on SkillRetBench)*
