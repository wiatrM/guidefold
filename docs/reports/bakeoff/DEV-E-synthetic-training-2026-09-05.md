# Family E — synthetic in-distribution training over the tenant's own skills (dev)

Status: **in progress**. This report is being written incrementally as the brief executes; every
section below is either a measured result (marked with the run that produced it) or an explicit
`TODO` placeholder. Nothing in a `TODO` section has been run yet — this file is committed at this
stage specifically to satisfy the pre-registration requirement in the addendum below, which must
land *before* any E1–E5 training or measurement run, not after.

Registered in `docs/reports/bakeoff/DENSE-PROGRAM.md` v2.6, §4 ("E synthetic in-distribution
training") and its "Why E exists" paragraph (PR #56, merged into `main` at `cb74c5b`). This report
is the "full detail (data, configurations, measurement)" document that entry points to.

## 0. Retrieval-mode addendum (pre-registered here, before any E1–E5 run)

**This is an addition to how every configuration in this family is measured, not a new training
configuration** — it does not change what gets fine-tuned, only how the fine-tuned (and zero-shot)
encoders are evaluated through the product path. Per instruction, it is written down here, before
the E1–E5 runs it applies to.

**What changes.** Every model in this family — E0 (zero-shot reference) and each fine-tuned Ek — is
run through the same product path (`policy_filter → candidates → score → select(admissible=…)`,
`tools/eval/dev_dense.py cmd_run`, unchanged) in **two retrieval modes**:

1. **hybrid** — RRF k = 60 fusion of the sparse (BM25F/F0) and dense channels. This is the
   family's original mode: `dense_ref.build_dense_index_and_router(..., weights={"w_dense": 1})`,
   unmodified `Router.candidates()`/`score()`/`select()`. Candidate membership is
   `bm25_order[:top_n] ∪ dense_order[:top_n]`; RRF sums both ranks where present.
2. **dense-only** ("pure dense", `w_sparse=0`) — candidates and scores come from the dense channel
   **exclusively**. Implemented as `dev_dense.make_dense_only_router_class` /
   `build_dense_only_index_and_router` (`tools/eval/dev_dense.py`, new this addendum): the router
   overrides `candidates()` itself so the candidate pool is `dense_order[:top_n]` only, and every
   candidate's `bm25_rank` is structurally `None` — `score()`'s RRF then has nothing to add for the
   BM25 term even in principle. **Zeroing `field.*` weights would not have been sufficient**:
   `Router._bm25_scores` still returns a same-value-0 entry for every lexically-matching URN
   regardless of field weight, and the base `candidates()`'s
   `bm25_order[:top_n] ∪ dense_order[:top_n]` union would still admit those URNs into the pool —
   that is a hybrid-at-zero-weight measurement, not a dense-only one. `w_scope`/`w_ppr`/
   `abstain_threshold`/… all stay at `Index.DEFAULT_WEIGHTS` in both modes ("everything else
   unchanged"); only candidate sourcing differs. `policy_filter`/`score`/`select` are the base
   `Router`'s, untouched — no arm bypasses the filter (ADR-0022); this is an eval-only measurement
   mode, never a shipped configuration.

**Why.** A dense-hybrid measurement run outside this family (reported by the service session)
found the same encoder, on the same dev split, at 47.0% `all_required@4` pure dense vs 37.5%
equal-RRF hybrid — and that session's hybrid number matched our own E0 hybrid number (37.6%) to
0.1 pp, indicating the two pipelines agree. Since pure dense measurably outperforms hybrid for this
encoder on this split, it is the stronger baseline this family's fine-tuned recipes must beat, and
reporting only the hybrid number would understate what a candidate recipe needs to clear.

**Sanity check, run this addendum** (`tools/eval/dev_dense.py run --identity E0 --mode dense-only`
against the already-cached E0 encode artifacts, no new encoding needed): E0 dense-only measures
**46.6%** `all_required@4` overall on our own dev split — within 0.4 pp of the externally-cited
47.0%, and E0 hybrid reproduces at 37.6% exactly as previously recorded. The two pipelines agree;
proceeding on this implementation.

**Freeze rule (unchanged text, reapplied per model to the better of two modes).** §5's rule stands
exactly as registered in DENSE-PROGRAM.md v2.6: a frozen E recipe must clear `all_required@4` ≥
F0 + 2.0 pp **and** ≥ E0 + 2.0 pp, both CI excluding 0, with `hit@1` not worse than E0 by > 1.0 pp.
Under this addendum, **that comparison is evaluated per model against whichever of its two modes
scores higher `all_required@4` on dev**, and the F0/E0 baseline used in the comparison is the
**same mode** as the candidate's chosen mode (e.g. a candidate whose better mode is dense-only is
compared against E0's dense-only number, 46.6%, not E0's hybrid number). The dev table below reports
**both modes for every model** regardless of which one is chosen; the mode chosen for the freeze
decision is named explicitly in §4 below, per model, when that model's runs are in.

## 1. Data (dev "tenant catalogue")

Design (frozen, from the original brief): corpus = SKILLRET-train dev split, 10,123 skills
(`tools/eval/corpora.py::load_skillret_dev()`); 1,000 dev queries held out, never read by the
generator. Generator: local `Qwen/Qwen2.5-7B-Instruct` (Apache-2.0, pinned revision
`a09a35458c702b33eeacc393d103063234e8bc28`), temperature 0.8 / top-p 0.9, seed 20260905 (+ batch
offset). Per skill: 5 natural queries, ≥ 2 of 5 not naming the skill. Composite: 2–3-skill sets
sampled by taxonomy co-occurrence (`major.sub`), one natural task needing all of them, sized to
≈ 30 % of training rows. Hard negatives: 3 same-category siblings per positive, topped up from a
repo-wide pool when the leaf runs short (`sample_hard_negatives`, tested).

### Generated (measured, 2026-09-05/06)

| file | backend | records | usable | parse failures | queries | notes |
|---|---|---|---|---|---|---|
| `per-skill-dev.jsonl` | transformers bf16, batch 8, max 320 new tokens | 10,123 / 10,123 | 10,026 skills | 97 (0.96 %) | **50,160** | 9,664 generated 2026-09-05 (16,900 s), 459 resumed 2026-09-06 after the NUL-line repair (§2 note); a batch-24 attempt thrashed GPU memory (72 skills / 10 min) and was restarted at batch 8 |
| `composite-dev.jsonl` | vLLM 0.28 bf16 (`VLLM_WSL2_ENABLE_PIN_MEMORY=1`), continuous batching, max 160 new tokens | 8,703 sets | 8,694 sets | 9 (0.10 %) | 8,694 (→ 21,669 rows, one per gold skill) | 1,848 s wall; sets sized by `composite_sets_for_target_rows` for 21,692 target rows |
| `hard-negatives-dev.jsonl` | pure sampling, seed 20260905 | 18,720 records (10,026 per-skill + 8,694 composite) | all | — | — | 3 per positive; composite negatives keyed per gold skill, excluding the whole set |

The two backends are not bit-identical samplers at the same seed (recorded in each file's
`.manifest.json`); this is offline data generation, not a runtime determinism claim. vLLM measured
3.5 docs/s on a 96-doc probe vs 0.5–0.75 docs/s for the batched `transformers.generate()` loop,
which is why composite generation switched backend; per-skill stayed on one backend end-to-end.

### Leakage check (family-E rule 1, run before any training)

`synth_queries.py leakage-check --corpus dev,test-a,test-b`: every generated query, raw and
normalised (NFKC, lower-cased, punctuation-stripped, whitespace-collapsed), against **all** labelled
query sets — dev (1,000), SKILLRET-test (4,392) and SkillRetBench (1,250) = 6,642 strings.

| file | generated | labelled | violations |
|---|---|---|---|
| per-skill | 50,160 | 6,642 | **0** |
| composite | 8,694 | 6,642 | **0** |

### Training rows (`finetune.py rows`, measured 2026-09-06)

| configuration | per-skill rows | composite rows | total | composite share | dropped |
|---|---|---|---|---|---|
| E1 (per-skill only, 0 negatives) | 50,160 | 0 | **50,160** | 0 % | 97 skills with no parsable queries |
| E2 (+ composite, 0 negatives) | 50,160 | 21,669 | **71,829** | 30.2 % | 97 + 9 composite parse failures |
| E3 (+ 3 hard negatives) | 50,160 | 21,669 | **71,829** | 30.2 % | same; every row has exactly 3 negatives |

The composite share lands on the registered ≈ 30 % of training pairs (target 21,692 rows).

(The first run of this check crashed on the SkillRetBench loader — its query list sits one level
down in the benchmark JSON — fixed and re-run before anything was trained.)

### 100-sample audit (manual, all 500 queries read; `audit-100.json` / `audit-100.labels.json`)

Seeded sample (`audit --n 100`, seed 20260905) of per-skill query groups, labelled by one reader
(this session) without seeing any ranking result:

| label | definition | groups |
|---|---|---|
| **good** | five distinct, plausible user requests this skill answers | **74** |
| **repetitive** | five paraphrases of one scenario — valid positives, low diversity (e.g. `add-cuda-kernel`: all five "add a scaling kernel to FlashInfer"; `openai-whisper-api`: all five "transcribe this audio") | **25** |
| **drifted** | ≥ 1 query asks for something outside the skill's scope (`epistemic-cognitive-guardrails`: one query about bilingual scholarly documentation) | **1** |

Heuristic flags on the same 500 queries: 68 (13.6 %) contain the skill's own name — the "≥ 2 of 5
must not name it" instruction holds in every group; 20 have zero content-word overlap with
name+description (mostly fine: they describe the need, as instructed); 0 near-duplicate pairs by
the > 0.6 token-Jaccard heuristic — the 25 "repetitive" groups are semantic paraphrases the
heuristic does not catch. Non-English output occurs where the skill itself is non-English
(`pont-de-londres`, French) — consistent with the source, not drift. Read-out: the generator's
per-skill queries are usable as positives with no observed label leakage; diversity, not
correctness, is the weak point, and it is what the composite queries and hard negatives are
supposed to add.

## 2. Configurations (≤ 6, frozen)

| id | recipe | status |
|---|---|---|
| E0 | `SKILLRET-Embedding-0.6B` zero-shot reference, `w_dense=1`, run once on dev | **measured**, both modes (§3) |
| E1 | 0.6B fine-tuned on per-skill queries only | TODO |
| E2 | E1 + composite queries | TODO |
| E3 | E2 + hard negatives | TODO |
| E4 | E3 recipe on a small CPU-servable base — **chosen: `Snowflake/snowflake-arctic-embed-m-v1.5`**, pinned revision `e58a8f756156a1293d763f17e3aae643474e9b8a` (Apache-2.0, 109M params, 768-dim; cached and load-verified via `SentenceTransformer` on CPU). `BAAI/bge-base-en-v1.5` was the documented alternative, not fetched. | TODO — model cached, not yet trained |
| E5 | one hyperparameter variant, conditional on E3 clearing the dev gate | conditional, not yet reached |

E1/E2 note (implementation detail, not a design change): `build_training_rows` (`tools/train/finetune.py`) requires an
exact match between each row's hard-negative count and `--n-negatives`, so building E1 ("per-skill queries only") and
E2 ("+ composite") rows — neither of which includes mined hard negatives — uses a companion all-empty hard-negatives
file (`hard_negatives: []` per skill; pre-built at `/home/mike/.cache/guidefold/family-e-data/hard-negatives-zero.jsonl`,
10,123 records, one per dev-corpus skill id) with `--n-negatives 0`, giving pure in-batch-negative
(`MultipleNegativesRankingLoss`) training for those two configurations. E3 uses the real mined file with the default
`--n-negatives 3`. No code change was needed — `n_neg` was already a generic parameter.

### Training-time implementation note (written 2026-09-06, before any E1–E5 run)

Three things `tools/train/finetune.py` had to settle before the first fine-tune could physically
run; none changes what is trained on or how it is measured, and all apply identically to every
configuration in the family:

| what | choice | why (measured) |
|---|---|---|
| sequence cap at **training** time | 1,024 tokens on every training text (query, positive, negatives); E4's base has its own 512 limit, which binds there | dev skill texts under the 0.6B tokenizer: median 1,564 tokens, p75 2,739, p95 5,516, max 34,410 (34 % fit in 1,024; 62 % in 2,048). Full-body MNRL at any useful batch does not fit 24 GB. **Eval is unchanged**: `dev_dense.py` still embeds the full body exactly as for E0, so every Ek is scored on the same document representation as the reference; this is a train-time truncation only |
| loss implementation | `CachedMultipleNegativesRankingLoss` (GradCache), batch 64, mini-batch 4 | the same objective as the registered `MultipleNegativesRanking` with in-batch negatives — identical loss value and gradient, computed in chunks — so the in-batch-negative batch is set by the recipe, not by activation memory. `--loss mnrl` remains for smoke runs |
| precision | **pure bf16** — corrected 2026-09-06 15:05Z after E1: the base checkpoint is stored in bf16 and transformers 5 loads it in its stored dtype, so the trainer's `bf16=True` autocast ran over bf16 weights, not fp32 master weights as first written here. Verified on the saved E1 (1.19 GB, `bfloat16`). | fp16 autocast (the only mixed mode the previous `old_fit` path offered) can overflow a Qwen3 model. Pure-bf16 AdamW can round away part of a 2e-5 update; E1's loss nevertheless fell 0.226 → 0.044 over the epoch, so learning happened. **Kept identical for E2–E4** so the arms differ only in data; fp32 master weights is the natural candidate for the one registered hyper-parameter variant (E5), conditional on E3 clearing the gate. Needed `datasets`+`accelerate` in the GPU venv (installed 2026-09-06) |
| query prompt | the base model's own query instruction (`dev_dense.QUERY_PROMPTS[source]`, byte-identical to E0's) is prepended to every training query; recorded in the checkpoint's `train_meta.json`, and `dev_dense._default_query_prompt` now reads it back for a local checkpoint directory | without this, E0 would be evaluated *with* the prompt and an Ek trained *without* it and then evaluated with none — a convention change masquerading as a training effect |

Fixed hyper-parameters for E1–E4 (E5 is the one registered variant): 1 epoch, lr 2e-5, 10 %
warm-up, batch 64, seed 20260905, `NO_DUPLICATES` batch sampler (no text repeated within a batch
across any column). Data-file repair on record: the per-skill file's last line was 1,008 NUL bytes
from the shutdown kill on 2026-09-06 (`per-skill-dev.jsonl.bak-nul-2026-09-06` keeps the original);
the line was removed and generation resumed from the 9,664 intact records with the same backend,
prompt, sampling and seed rule as the first run.

**Leak caught on E1, before any number was read (2026-09-06 14:27Z).** `SentenceTransformer.save()`
persists `max_seq_length` into the checkpoint's `tokenizer_config.json` (`model_max_length`), so
the 1,024-token *train* cap travelled with the E1 checkpoint and its first encode truncated every
document at 1,024 tokens — while E0 was encoded at the base's 8,192. That is a different document
representation, not a training effect, and would have flattered or hurt E1 for reasons unrelated
to the recipe. The E1 encode and the one dev run that had completed were **discarded unread**
(cache and `validation/dev-dense-E1*` deleted before their summaries were opened); the checkpoint's
persisted limit was restored to 8,192 (original file kept as `tokenizer_config.json.trained-cap-1024`);
`finetune.py` now restores the base limit before saving (`restore_eval_seq_length`, tested) so
E2–E5 cannot repeat it; and every Ek encode uses E0's exact regime (`--skill-batch-size 4`, full
body up to 8,192 tokens). The train-time cap itself is unchanged.

Throughput knobs (no effect on the objective, recorded for reproducibility): E1 attempt 1 ran the
collator's tokenisation in the training process (GPU 19–47 % busy at 120 % CPU) and was stopped at
step ~75; the run that produced E1 used 6 dataloader workers and mini-batch 8 (6.5 s/step, 1.42
GPU-h, 23.8 GB peak VRAM). Its logged losses at steps 25/50 match attempt 1's to three decimals
(0.226 / 0.112), as expected for a memory/throughput-only change. E2–E4 use mini-batch 6 with
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` for VRAM headroom on the 5-text E3 rows.

## 3. Dev table — E0 (measured, both modes)

Product path, dev split, 1,000 cases (k=1: 328, k=2: 333, k=3: 339). `all_required4`/hit1/ndcg10/
recall10 computed as `dev_dense.py` documents (`all_required@4` from `injected`; hit@1/nDCG@10/
recall@10 from raw `ranked`). Paired bootstrap CI, 1,000 resamples, seed 0, vs F0
(`dev-sparse-p-shipped.jsonl.gz`).

### hybrid (RRF k=60 with F0)

| scope | n | all_required4 | hit1 | ndcg10 | recall10 | Δ all_required4 vs F0 (CI) | Δ hit1 vs F0 (CI) |
|---|---|---|---|---|---|---|---|
| overall | 1000 | 0.376 | 0.839 | 0.727 | 0.708 | +7.7pp [6.2, 9.5] | +12.9pp [10.8, 15.0] |
| k=1 | 328 | 0.930 | 0.832 | 0.898 | 0.963 | +8.8pp [5.8, 12.2] | +9.5pp [6.1, 13.1] |
| k=2 | 333 | 0.195 | 0.838 | 0.692 | 0.665 | +12.6pp [9.3, 16.5] | +13.5pp [9.6, 17.7] |
| k=3 | 339 | 0.018 | 0.847 | 0.596 | 0.501 | +1.8pp [0.6, 3.2] | +15.6pp [10.9, 20.4] |

### dense-only ("pure dense", w_sparse=0)

| scope | n | all_required4 | hit1 | ndcg10 | recall10 | Δ all_required4 vs F0 (CI) | Δ hit1 vs F0 (CI) |
|---|---|---|---|---|---|---|---|
| overall | 1000 | 0.466 | 0.878 | 0.785 | 0.774 | +16.7pp [14.3, 19.0] | +16.8pp [14.0, 19.5] |
| k=1 | 328 | 0.973 | 0.875 | 0.936 | 0.991 | +13.1pp [9.1, 17.1] | +13.7pp [9.5, 18.0] |
| k=2 | 333 | 0.363 | 0.877 | 0.753 | 0.733 | +29.4pp [24.3, 34.8] | +17.4pp [12.3, 22.2] |
| k=3 | 339 | 0.077 | 0.882 | 0.668 | 0.606 | +7.7pp [5.0, 10.6] | +19.2pp [13.3, 25.1] |

Both baseline numbers — E0 hybrid 37.6% and E0 dense-only 46.6% overall — are the two references
every fine-tuned Ek's "≥ E0 + 2.0pp" gate is measured against, selected per §0's rule (same mode as
the candidate's own better mode).

### Candidate ceiling (gold within top-N, from `ranked`, no closure assist — dev has `requires=[]`)

| mode | ceiling4 | ceiling10 | ceiling15 | ceiling50 |
|---|---|---|---|---|
| hybrid | 0.376 | 0.459 | 0.510 | 0.597 |
| dense-only | 0.466 | 0.541 | 0.563 | 0.602 |

### Encode latency

TODO — batch-1 GPU/CPU latency for E0 not yet captured under this report (`dev_dense.py latency`);
will be filled in alongside E1–E5's numbers so all arms are comparable in one table.


## 3a. Dev table — E1 (measured 2026-09-06 15:18Z, run under E0's exact encode regime after the §2 leak repair)

E1 = `SKILLRET-Embedding-0.6B` fine-tuned on the 50,160 per-skill synthetic queries only (no
composite, no mined negatives; in-batch negatives, batch 64), 783 steps, 1 epoch, lr 2e-5, pure
bf16, train cap 1,024 tokens, base query prompt; 1.42 GPU-h. Final train loss
0.044 (from 0.226 at step 25). Same 1,000 dev cases, same paired bootstrap (1,000
resamples, seed 0) as the E0 table.

### E1 — hybrid

| scope | n | all_required4 | hit1 | ndcg10 | recall10 | Δ all_required4 vs F0 (CI) | Δ all_required4 vs E0 (CI) | Δ hit1 vs E0 (CI) |
|---|---|---|---|---|---|---|---|---|
| overall | 1000 | 0.351 | 0.794 | 0.696 | 0.673 | +5.2pp [3.8, 6.7] | -2.5pp [-3.6, -1.4] | -4.5pp [-6.3, -2.9] |
| k=1 | 328 | 0.909 | 0.823 | 0.889 | 0.951 | +6.7pp [4.3, 9.5] | -2.1pp [-3.7, -0.6] | -0.9pp [-2.7, 0.9] |
| k=2 | 333 | 0.150 | 0.790 | 0.650 | 0.623 | +8.1pp [5.1, 11.4] | -4.5pp [-7.2, -1.8] | -4.8pp [-7.5, -2.1] |
| k=3 | 339 | 0.009 | 0.770 | 0.556 | 0.454 | +0.9pp [0.0, 2.1] | -0.9pp [-2.4, 0.3] | -7.7pp [-11.5, -3.8] |

Candidate ceiling (hybrid): ceiling4 0.351 · ceiling10 0.415 · ceiling15 0.436 · ceiling50 0.517 (E0 hybrid: 0.376 / 0.459 / 0.510 / 0.597).

### E1 — dense-only

| scope | n | all_required4 | hit1 | ndcg10 | recall10 | Δ all_required4 vs F0 (CI) | Δ all_required4 vs E0 (CI) | Δ hit1 vs E0 (CI) |
|---|---|---|---|---|---|---|---|---|
| overall | 1000 | 0.371 | 0.832 | 0.721 | 0.686 | +7.2pp [5.4, 9.2] | -9.5pp [-11.6, -7.6] | -4.6pp [-6.7, -2.3] |
| k=1 | 328 | 0.951 | 0.857 | 0.922 | 0.985 | +11.0pp [7.3, 14.6] | -2.1pp [-4.3, 0.0] | -1.8pp [-5.2, 1.5] |
| k=2 | 333 | 0.171 | 0.811 | 0.673 | 0.626 | +10.2pp [6.0, 13.8] | -19.2pp [-24.0, -14.7] | -6.6pp [-10.5, -2.4] |
| k=3 | 339 | 0.006 | 0.829 | 0.575 | 0.457 | +0.6pp [0.0, 1.5] | -7.1pp [-9.7, -4.4] | -5.3pp [-9.7, -1.2] |

Candidate ceiling (dense-only): ceiling4 0.371 · ceiling10 0.420 · ceiling15 0.439 · ceiling50 0.524 (E0 dense-only: 0.466 / 0.541 / 0.563 / 0.602).

**Read-out.** E1 is *better than sparse* (F0) on every metric in both modes, and *worse than the
zero-shot encoder* (E0) on every metric in both modes — decisively so in the mode that matters:
dense-only `all_required@4` **−9.5 pp [−11.6, −7.6]** vs E0, with the loss concentrated on
multi-skill cases (k = 2: −19.2 pp; k = 3: −7.1 pp; k = 1: −2.1 pp), and `hit@1` −4.6 pp. The
candidate ceiling also drops (ceiling@50 0.602 → lower), i.e. the fine-tuned encoder *surfaces
fewer* of the required skills into the pool, not just ranks them worse. **E1 fails the freeze gate
on both conditions** (needs ≥ E0 + 2.0 pp; `hit@1` not worse than E0 by > 1.0 pp).

What this does and does not say. E0 was fine-tuned by SkillRet on queries a 122B model wrote over
this same skill distribution; our per-skill queries come from a 7B model with a different style
(§1 audit: 25 % of groups are single-scenario paraphrases). Training on them moved the encoder
*toward our generator's distribution and away from the dev queries'* — on dev, that is a
regression by construction, exactly the in-distribution ceiling the v2.7 amendment (§4b) was
written for before this number existed. It does **not** show that per-tenant adaptation fails
out-of-distribution (SkillRetBench), which is the family's premise and is measured only by §4b.
A second, uglier reading — that pure-bf16 AdamW at lr 2e-5 damaged the model rather than
re-targeted it — cannot be separated from the first with dev alone; the post-hoc diagnostic that
would separate them (E0 vs E1 on a *held-out* synthetic query set from a fresh generator seed:
if E1 wins there, it learned our distribution; if it loses there too, training hurt) is recorded
here as a planned diagnostic, not a selection step, and runs when the GPU is free.

Per the registered plan the family continues: E2 (+ composite) and E3 (+ hard negatives) measure
whether the *other two* data kinds move multi-skill completeness relative to E1, which is the
question they were registered to answer; nothing about E1's result changes their protocol.

## 4. Freeze decision

Interim (2026-09-06 15:18Z): **E1 does not freeze** — fails both the ≥ E0 + 2.0 pp condition (−9.5 pp dense-only, −2.5 pp hybrid) and the `hit@1` guard (−4.6 pp). E2–E4 pending.

TODO — not reached. Recorded here once E1–E5 are measured: which recipe (if any) clears
`all_required4 ≥ F0+2.0pp` and `≥ E0+2.0pp` (both CI excl. 0) with `hit1` not worse than E0 by
`>1.0pp`, **which of the two modes was used for that decision**, and why.

## 5. Test-once results

TODO — not run. Two routes, both fixed in advance:

- **Normal freeze (§4 passes):** the frozen recipe, in its frozen mode, once on SKILLRET-test
  (6,006 skills / 4,392 queries) and once on SkillRetBench (501 skills / 1,250 queries, HSR@4 gate).
- **No freeze (§4 fails for every arm):** DENSE-PROGRAM.md v2.7 §4b — the best-on-dev recipe gets
  one premise-check run on SkillRetBench only (generate from its 501 skills, same recipe, same
  hyper-parameters, paired vs F0 and vs E0 in the same mode); test-A untouched. Registered
  2026-09-06T11:24Z, before any E1–E5 dev result existed.

## 6. GPU-hours

TODO — running total, updated as generation/training jobs complete.
