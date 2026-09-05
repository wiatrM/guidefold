# Dev-only diagnosis: why the shipped BM25F trails plain BM25 — 2026-09-05

**Corpus:** SKILLRET **train** split only (`tools/eval/corpora.py::load_skillret_dev()`) — 10,123
train skills, 1,000 train queries, frozen `skillret-dev-split.json`. **Test-A (SKILLRET-test) and
test-B (SkillRetBench) are not touched anywhere in this report or its code** — this is a
diagnostic run on dev, per `DENSE-PROGRAM.md`'s "the diagnosis moves to dev ... where a config
may be chosen; test-B is not touched again until a frozen variant exists" instruction (2026-09-05
entry, PR #30).

**Motivation:** `DENSE-PROGRAM.md` §7 reports the shipped sparse ranker (F0) losing to each
dataset's own reported BM25 baseline by a wide margin on both real corpora it has been run
against — test-B nDCG@10 0.436 vs 0.534 (−9.8 pp), test-A nDCG@10 0.400 vs 0.517 (−11.7 pp). This
report isolates *why*, using dev only, so no test corpus is spent on trial-and-error tuning.

Converter + runner: `tools/eval/dev_sparse.py` (`convert` / `run` subcommands). Tests:
`tests/test_dev_sparse.py` (15 cases, all passing; full repo suite, 387 tests, all passing — see
"Verification" below). Per-query output: `docs/reports/bakeoff/validation/dev-sparse-<arm>.jsonl.gz`
(9 files, one per arm, gzip). Aggregated metrics:
`docs/reports/bakeoff/validation/dev-sparse-metrics.json`. Every product ("P-*") arm went through
the real `Index.from_cards → Router.policy_filter → candidates → score → select(admissible=…)`
path — never a reimplementation. Reference ("R-*") arms are an independent textbook-BM25
implementation living only in `dev_sparse.py`, used purely as a same-corpus, same-queries
comparison point.

## Corpus and query facts

```
n_skills / n_cards            10,123     (0 dup ids, 0 slug collisions)
n_majors                      6
n_major.sub nodes             18
n_nodes_total (incl. _root)   25
n_queries / n_cases           1,000      (0 dropped, 0 qrel mismatches, 0 missing urn)
  k=1 (1 required skill)      328
  k=2 (2 required skills)     333
  k=3 (3 required skills)     339
admissible_size (policy_filter), every query   10,123 / 10,123   (0 skills ever dropped)
abstain_counts, every P-* arm, all 1,000 queries                  0
runtime                       1,276 s (~21 min) for all 9 arms end-to-end
```

Policy filter drops nothing at `_root` on this corpus (same finding as test-B's F0 report), and
the abstain gate (`abstain_threshold=1200`, magnitude mode) never fires for any product arm —
`all_required@4` numbers below are pure ranking-precision effects, not abstention artifacts.

## Card scheme

Each of the 10,123 train skills becomes one card: `urn` from the skill id, `node` =
`<major_slug>.<sub_slug>` (2-level, matching the dataset's own category/subcategory), `name` =
skill name, `description`/`digest` = the skill's description (digest truncated to 200 chars),
`_body` = the skill's `body` text with its own YAML frontmatter block stripped (10,102/10,123
bodies matched the frontmatter pattern; the other 21 are left unchanged), `triggers` /
`negative_triggers` = `[]` (not present in the source data — see "Could not be reproduced"),
`requires` = `[]` (this dataset carries no skill-dependency graph). 25 nodes total (`_root` + 6
majors + 18 major.sub leaves); every query resolves to `_root` (full-corpus search, matching the
"fair" setting used on test-A/test-B, not the leaking `node_scoped` one).

## Arms

Nine arms, coordinate descent (one changed parameter per arm vs the shipped baseline), well
inside the ≤12-arm budget:

| Arm | What | Path |
|---|---|---|
| **R-BM25** | Textbook single-field Okapi BM25 (`k1=1.2, b=0.75`), independent implementation, over `name + description + body` concatenated per doc, shared tokenizer (`tools/bakeoff/tokenizer.py`). Ranks *every* doc, no filter, no cap. | reference |
| **R-BM25-simple-tok** | R-BM25 with a naive `[a-z0-9]+`/`.lower()` tokenizer instead of the shared one (no accent folding). | reference |
| **P-shipped** | Shipped config, unmodified: integer BM25F, RRF fusion, `w_scope`, PPR/closure, default field weights, `top_n=50`, `k1=1.2/b=0.75`. | product |
| **P-flat** | P-shipped with all `field.*` weights set to 1 (uniform), everything else unchanged. | product |
| **P-onefield** | P-shipped with every card's `name`/`description`/`digest`/`triggers` emptied and all text concatenated into `_body` alone — collapses BM25F to a single field, structurally matching R-BM25's normalization (one corpus-average length, not one per field). | product |
| **P-nopprocl** | P-shipped with `w_ppr=0`. | product |
| **P-noscope** | P-shipped with `w_scope=0`. | product |
| **P-top200** | P-shipped with `top_n=200` (same `Index`/`Router` object as P-shipped, only the candidate-pool cap changed). | product |
| **P-k1b** | P-shipped with `k1=0.9, b=0.4` (subclassed `Index`) instead of `1.2/0.75`. | product |

**P-idf was not run as a separate arm.** The shipped IDF formula,
`ln(1 + (N−df+0.5)/(df+0.5))`, is algebraically identical to the textbook form
`ln((N−n+0.5)/(n+0.5) + 1)` used by R-BM25 — confirmed by code inspection and by the existing
`tests/test_bm25_reference.py`. There is no IDF difference to ablate.

## Main results

```
arm                 break                n          hit1        ndcg10      recall10 all_required@4
--------------------------------------------------------------------------------------------------
R-BM25              overall           1000        0.7630        0.6475        0.6143        0.3170
R-BM25              k=1                328        0.7835        0.8453        0.9024        0.8750
R-BM25              k=2                333        0.7538        0.5993        0.5495        0.0841
R-BM25              k=3                339        0.7522        0.5035        0.3992        0.0059
R-BM25-simple-tok   overall           1000        0.7630        0.6479        0.6147        0.3170
P-shipped           overall           1000        0.7100        0.6101        0.5818        0.2990
P-shipped           k=1                328        0.7378        0.8082        0.8811        0.8415
P-shipped           k=2                333        0.7027        0.5630        0.5120        0.0691
P-shipped           k=3                339        0.6903        0.4647        0.3609        0.0000
P-flat              overall           1000        0.7610        0.6474        0.6175        0.3170
P-onefield          overall           1000        0.7060        0.6085        0.5797        0.2990
P-nopprocl          overall           1000        0.7100        0.6101        0.5818        0.2990
P-noscope           overall           1000        0.7100        0.6101        0.5818        0.2990
P-top200            overall           1000        0.7100        0.6101        0.5818        0.2990
P-k1b               overall           1000        0.5990        0.5415        0.5338        0.2680
```

Full per-`k` breakdown for every arm is in `dev-sparse-metrics.json`'s `summary` block.

### Paired bootstrap deltas (1,000 resamples, 95% percentile CI), nDCG@10, overall

| Arm vs baseline | Δ nDCG@10 (pp) | 95% CI (pp) | Δ recall@10 (pp) | 95% CI (pp) |
|---|---|---|---|---|
| P-shipped − R-BM25 | −3.74 | [−4.34, −3.07] | −3.25 | [−4.10, −2.42] |
| **P-flat − R-BM25** | **−0.01** | **[−0.27, +0.25]** | +0.32 | [+0.03, +0.65] |
| P-onefield − R-BM25 | −3.90 | [−4.55, −3.27] | −3.47 | [−4.37, −2.62] |
| P-nopprocl − R-BM25 | −3.74 | [−4.34, −3.07] | −3.25 | [−4.10, −2.42] |
| P-noscope − R-BM25 | −3.74 | [−4.34, −3.07] | −3.25 | [−4.10, −2.42] |
| P-top200 − R-BM25 | −3.74 | [−4.34, −3.07] | −3.25 | [−4.10, −2.42] |
| P-k1b − R-BM25 | −10.60 | [−11.70, −9.38] | −8.05 | [−9.27, −6.70] |
| R-BM25-simple-tok − R-BM25 | +0.04 | [+0.00, +0.09] | +0.03 | [+0.00, +0.13] |
| **P-flat − P-shipped** | **+3.72** | **[+3.16, +4.34]** | +3.57 | [+2.77, +4.43] |
| P-onefield − P-shipped | −0.17 | [−0.33, −0.01] | −0.22 | [−0.48, +0.00] |

By `k` (nDCG@10 Δ vs R-BM25, pp): P-flat is −0.48 [−1.14,+0.06] at k=1, −0.13 [−0.51,+0.23] at
k=2, **+0.55 [+0.23,+0.91]** at k=3 (CI entirely positive — P-flat *beats* R-BM25 at k=3); P-shipped
and P-onefield sit at roughly −3.6 to −4.1 pp at every k, uniformly.

## Attribution

**Field weights, not per-field normalisation, are the cause.** P-flat (uniform field weights,
still full BM25F with independent per-field length normalisation) is statistically
indistinguishable from R-BM25 on nDCG@10 overall (Δ = −0.01 pp, CI straddles zero) and even
slightly favours P-flat on recall@10 (+0.32 pp, CI excludes zero but the effect is ~0.3 pp — noise
floor, not a meaningful edge). Against P-shipped, P-flat is **+3.72 pp nDCG@10 [+3.16, +4.34]** —
this single change (`field.*` weights → 1) recovers essentially the entire gap to R-BM25
(3.72 of the 3.74 pp deficit, 99.5%).

P-onefield was the test of the competing hypothesis (per-field normalisation itself, independent
of weights, being the culprit — as it would be if collapsing to one field, matching R-BM25's
normalisation exactly, closed the gap). It does not: P-onefield trails R-BM25 by −3.90 pp,
statistically indistinguishable from P-shipped (Δ vs P-shipped = −0.17 pp, a barely-significant
and negligible-magnitude regression, not an improvement). **This rules out per-field
normalisation as the driver.** The BM25F mechanism itself (per-field independent length
normalisation, RRF fusion, scope term, PPR/closure) is not what costs the ranker accuracy on
this corpus — the shipped *default field weights* (which over- or under-weight `name` /
`description` / `body` relative to a flat combination) are.

k1/b tuning was checked and ruled out in the other direction: P-k1b (`k1=0.9, b=0.4`) is far
*worse* than shipped (−6.86 pp nDCG@10 vs P-shipped, −10.60 pp vs R-BM25) — the shipped
`k1=1.2/b=0.75` (textbook defaults) are already a better choice than this alternative, not a
source of the gap. Tokenizer (accent folding vs naive lowercasing) moves nDCG@10 by +0.04 pp
overall (CI technically excludes zero at n=1,000 but the magnitude is noise-level) — not a
meaningful factor. IDF was ruled out analytically (see "Arms" above), and the abstain mechanism
never fires (0 abstentions across every product arm), so it explains none of the gap either.

**Frozen-config proposal:** ship `field.*` weights = 1 (P-flat) instead of the current
differential weighting scheme; keep everything else (BM25F per-field normalisation, RRF fusion,
`w_scope`, PPR/closure, `k1=1.2/b=0.75`) as-is. This is a one-line change to `DEFAULT_WEIGHTS` in
`skills/guidefold/scripts/guidefold`, not a structural rewrite, and it is the only one of the
eight ablations that closed the gap to R-BM25 within noise.

**What is not explained / could not be reproduced:** the residual −3.7 pp shipped-vs-R-BM25 gap
this report explains is a dev-corpus effect; the actual test-A/test-B gaps this diagnosis was
launched to explain (−9.8 and −11.7 pp respectively, vs each dataset's own *reported* BM25
number, not this report's from-scratch reference) are larger than the field-weight effect found
here, and this report does not claim to close them — that requires re-running P-flat on test-A/
test-B, which is out of scope for this diagnosis (dev-only). Neither SKILLRET nor SkillRetBench
ships the exact BM25 code/tokenizer/stopword list its own reported baseline number came from, so
an exact apples-to-apples reference could never be built for either test corpus; R-BM25 here is
a faithful from-scratch textbook implementation over the same corpus/queries, not a
reproduction of either dataset's own baseline script. `triggers`/`negative_triggers` are not
present in the raw SKILLRET train data, so every card ships with `triggers=[]` — this is a card
scheme limitation for this dev run specifically (F5-style extraction, used elsewhere in the
programme, was out of scope here to keep the diagnosis to a single ablation axis: BM25F
construction).

## Confirmation: P-noscope / P-nopprocl / P-top200 are byte-identical to P-shipped on real dev data

Predicted from code inspection (`Router.score`/`Router.candidates` in
`skills/guidefold/scripts/guidefold`) and confirmed on the synthetic test fixture
(`tests/test_dev_sparse.py::test_noscope_nopprocl_top200_are_byte_identical_to_shipped_ranking`).
**Confirmed again on the full real run**: exact per-query comparison of the `ranked` (top-50 urn
list) and `injected` (the `select()` output) fields across all 1,000 dev queries between
P-shipped and each of P-noscope/P-nopprocl/P-top200 — 0 queries differ, 0 diffs in either field,
for all three arms. Structural cause for each, confirmed against the current source:

- **P-noscope** (`w_scope=0`): every dev query resolves to `_root`, and `_hops(skill_node,
  "_root")` is a constant across all "major.sub" nodes for a `_root` caller — `w_scope //
  (1 + hops)` in `Router.score` adds the *same* value to every candidate's score for a given
  query, a per-query constant that cannot change relative order.
- **P-nopprocl** (`w_ppr=0`): this corpus carries zero `requires` edges (dataset has no
  skill-dependency graph), so `_reverse_ppr`/`_decayed_closure` return 0 for every candidate;
  `w_ppr * ppr.get(u, 0)` is 0 regardless of `w_ppr`'s value.
- **P-top200** (`top_n=200` vs 50): `policy_filter` drops 0/10,123 skills for every query
  (confirmed above), so the admissible pool is always the full corpus; `candidates()` builds
  `cand_urns = bm25_order[:top_n] | dense_order[:top_n]` with `dense_order` empty (`w_dense=0`),
  so `cand_urns` is a prefix of the single deterministic `bm25_order` sort. Raising the prefix
  length from 50 to 200 only adds candidates *beyond* rank 50 — the top ranks that `hit@1`/
  `nDCG@10`/`recall@10` (top-10) and `select()` (top-4) ever look at are unaffected. Empirically,
  the cap never bound: it made no difference for any of the 1,000 queries.

None of the three differs from P-shipped on real data — this is confirmation of the structural
prediction, not a new finding; propagation/pool-cap reordering does not occur on this corpus
shape (zero graph edges, uniform depth-2 nodes, `w_dense=0`).

## `all_required@4` structural cause (confirms the original task's ask)

`Router.select()` builds its top-4 by taking the highest-scored candidates directly and only
fills gaps via `_requires_closure` over the `requires` graph — which is empty for every one of
the 10,123 dev cards (no dependency edges in this dataset). So for a k=3 case, `all_required@4`
reduces to "are all 3 gold skills literally within the top-4 scored candidates" — no closure
mechanism can rescue a gold skill ranked 5th or lower. This is a hard, near-impossible bar for
any of these rankers: R-BM25 achieves it in 2/339 k=3 cases (0.59%); P-shipped in 0/339 (0.00%).
Abstention (`abstain_threshold=1200`, magnitude mode) never fires for any product arm on any of
the 1,000 dev queries (`abstain_counts` all 0) — confirmed empirically, so the k=3 floor is a
pure ranking-precision / no-closure-graph effect, not an artifact of the abstain gate.

## Verification

- `python3 -m py_compile tools/eval/dev_sparse.py tests/test_dev_sparse.py` — clean.
- `tests/test_dev_sparse.py` — 15/15 passing, including a hand-verified 3-document BM25 check
  (`test_reference_bm25_hand_verified_on_three_documents`) and a real-corpus structural check
  against the frozen dev split (`test_real_dev_corpus_to_cards_and_cases_match_the_frozen_split`,
  not skipped — the corpus was present locally).
- Full repo suite (`pytest -q`): 387 tests, all passing, 0 failures/errors.
- Branch rebased cleanly onto `origin/main` (PRs #32, #33, #34, #35) before this report was
  written; `dev_sparse.py` re-verified against the post-rebase CLI/corpora/tokenizer modules
  (`convert` output unchanged).
- 9 arms run (≤12-arm budget); per-query rankings for all 9 committed as gzip JSONL under
  `docs/reports/bakeoff/validation/`; aggregate metrics + all pairwise comparisons in
  `docs/reports/bakeoff/validation/dev-sparse-metrics.json`.
