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
| precision | bf16 autocast over fp32 master weights (`SentenceTransformerTrainer`, `bf16=True`) | the 0.6B base is a Qwen3 model; fp16 autocast (the only mixed mode the previous `old_fit` path offered) can overflow it, and pure-bf16 weights round a 2e-5 update away. Needed `datasets`+`accelerate` in the GPU venv (installed 2026-09-06) |
| query prompt | the base model's own query instruction (`dev_dense.QUERY_PROMPTS[source]`, byte-identical to E0's) is prepended to every training query; recorded in the checkpoint's `train_meta.json`, and `dev_dense._default_query_prompt` now reads it back for a local checkpoint directory | without this, E0 would be evaluated *with* the prompt and an Ek trained *without* it and then evaluated with none — a convention change masquerading as a training effect |

Fixed hyper-parameters for E1–E4 (E5 is the one registered variant): 1 epoch, lr 2e-5, 10 %
warm-up, batch 64, seed 20260905, `NO_DUPLICATES` batch sampler (no text repeated within a batch
across any column). Data-file repair on record: the per-skill file's last line was 1,008 NUL bytes
from the shutdown kill on 2026-09-06 (`per-skill-dev.jsonl.bak-nul-2026-09-06` keeps the original);
the line was removed and generation resumed from the 9,664 intact records with the same backend,
prompt, sampling and seed rule as the first run.

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

## 4. Freeze decision

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
