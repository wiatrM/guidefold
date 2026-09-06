# Family F6 — offline dense sibling map, dev protocol and results

Status: **pre-registered 2026-09-06 18:40Z, before any F6 configuration was run.** Registered in
`docs/reports/bakeoff/DENSE-PROGRAM.md` v2.2 §4 (PR #37); this note fixes the dev protocol the
v2.2 entry left open (which threshold, how many neighbours, which tie-break rule, and what dev —
which carries no distractor labels — can and cannot measure). Owner approved running F6 in writing
on 2026-09-06 ("2 TAK … potem od razu przejdz do F6").

## 0. Hypothesis (from v2.2, unchanged)

The full encoder's one clean, significant win on test-B was **harmful-sibling exposure −10.00 pp
[−15.67, −4.00]** while completeness did not move. Its value is *discrimination between
near-identical skills*, which is a property of the corpus, not of the query — so it can be
precomputed offline and shipped as a small typed graph, with **no model and no vectors at query
time**, inside T300.

## 1. Mechanism (deterministic, integer-only, evaluated in `tools/eval/dev_sibling.py`, never the CLI yet)

- **Sibling map (offline).** From the zero-shot encoder's skill vectors (E0, `SKILLRET-Embedding-0.6B`,
  the same int8 cache every dense arm uses), for each skill: the skills in the **same taxonomy leaf**
  (`major.sub`; on SkillRetBench its category) with cosine ≥ τ, keeping the top-N by cosine;
  symmetrised. Measured on dev before registration (corpus geometry only, no labels): same-leaf
  nearest-neighbour cosine p50 0.52 / p90 0.76 / p99 0.92; skills with ≥ 1 sibling at
  τ 0.80 / 0.85 / 0.90 = 6.7 % / 3.2 % / 1.3 % (544 / 204 / 66 pairs). Coverage on dev is therefore
  small by construction; dev is a **no-harm** check, test-B is where the effect is measured.
- **Discriminating terms (offline).** For a sibling pair (a, b): D_a = tokens(a) − tokens(b) and
  D_b = tokens(b) − tokens(a), where tokens() is the product tokenizer over the card's five BM25F
  fields (name, description, digest, triggers, body). Sets, computed once per pair.
- **Query-time rule (integer).** After the product's own `select()` produced its ≤ 4 cards: if two
  cards x, y in the injected set are siblings, compute m_x = |tokens(query) ∩ D_x| and
  m_y = |tokens(query) ∩ D_y|. The card with the *lower* count is the loser; it is removed from the
  candidate list and the product's `select()` is re-run on the remaining candidates (so closure,
  abstention and `cannot_fit` stay the product's), until no sibling pair remains in the injected set
  (at most 4 iterations). **Ties (m_x = m_y) never fire.** Two rule variants:
  - *margin* — fires whenever m_winner > m_loser;
  - *strict* — fires only when m_loser = 0 and m_winner ≥ 1 (the query names something only one
    of the two has).

## 2. Configurations (≤ 4, frozen)

| id | τ | N | rule |
|---|---|---|---|
| F6-1 | 0.85 | 3 | margin |
| F6-2 | 0.80 | 3 | margin |
| F6-3 | 0.80 | 3 | strict |
| F6-4 | 0.75 | 5 | strict |

Baseline: F0 = P-shipped (`dev-sparse-p-shipped.jsonl.gz`), re-run in the same process and
asserted identical (injected lists) to the recorded file before any F6 number is read.

## 3. What dev measures, and the selection rule

Dev (SKILLRET-train split) has **no distractor labels**, so HSR@4 cannot be measured there. Dev reports:

1. the standard four (`hit@1`, `nDCG@10`, `recall@10` from `ranked`; `all_required@4` from
   `injected`), paired-bootstrap deltas vs F0 (1,000 resamples, seed 0);
2. **sibling-exposure proxy**: a query counts as exposed if any *non-gold* injected card is a
   mapped sibling of a *gold* skill of that query (the "found the family, showed the wrong
   representative" shape), computed for **every arm including F0 with one fixed reference map
   (τ 0.75, N 5 — the broadest configuration)** so the proxy is the same instrument for all arms;
3. firing statistics: queries where the rule fired, replacements made, `cannot_fit`/abstention
   changes.

**Selection (dev):** among configurations whose `all_required@4` and `hit@1` are not worse than
F0 by more than 1.0 pp (point estimate; the §5 tolerance), pick the one with the largest proxy
exposure reduction; ties → the smaller map (higher τ, smaller N). If no configuration reduces the
proxy at all, nothing freezes and F6 terminates on dev with numbers.

**Test-once (both corpora, once):** the frozen configuration on SKILLRET-test (no-harm on the four
metrics) and on SkillRetBench (HSR@4 — the gate of record, §5: not worse than F0 by > 1.0 pp is
the *floor*; the hypothesis predicts a reduction, and F6 is reported as a win only if HSR@4 drops
with a CI excluding zero while `all_required@4`/`hit@1` stay within tolerance on both corpora).
The test-once sibling maps are built from each test corpus's own skill vectors (E0, no labels),
exactly as a deployment would build them at index time.

## 4. Dev results (measured 2026-09-06 19:10Z; `validation/dev-sibling-summary.json`, `dev-sibling-f6-*.jsonl.gz`)

**A harness bug first.** The first dev run reported 0 firings for every configuration. The
exposure diagnostic (F0 has 67/1,000 queries with a mapped non-gold sibling in its top-4, and in
54 of them the gold is *also* in the top-4, i.e. the rule had somewhere to act) showed that was
impossible, and the cause was that the product's callers invoke `select()` without the query text
— the rule saw an empty query and always tied. Fixed (the query is captured in `score()`, which
every caller passes it to), the test now mirrors the real call path, the first run's artefacts were
discarded (kept outside the repo as `f6-dev-summary.attempt1-no-query-bug.json`), and the run was
repeated. F0 re-run in-process is identical to the recorded `dev-sparse-p-shipped.jsonl.gz`.

**Before the numbers, the diagnostic that frames them.** On the 54 rule-able F0 pairs, the
discriminating-term rule (margin, reference map) picks the gold 33 times, the *sibling* 30 times,
and ties 3 — near a coin flip on dev. Several "siblings" are functional duplicates of the gold
(`mcp-integration` vs `mcp-integration`, `shadcn` vs `shadcn-ui`, `k8s-…` vs `kubernetes-…`),
where the dev label chose one arbitrarily; dev cannot say whether removing the other is harm.
That is what SkillRetBench's distractor labels exist for.

| config | map pairs | queries fired / removals | `all_required@4` (injected) | exposure proxy | Δ all_required@4, k = 1 |
|---|---|---|---|---|---|
| F0 | — | — | 0.299 | 0.067 | — |
| F6-1 | 204 | 28 / 29 | 0.294 (-0.5 pp [-1.0, -0.1]) | 0.062 (-0.5 pp [-1.0, -0.1]) | -1.2 pp [-2.4, -0.3] |
| F6-2 | 517 | 58 / 71 | 0.290 (-0.9 pp [-1.6, -0.3]) | 0.052 (-1.5 pp [-2.3, -0.8]) | -2.1 pp [-4.0, -0.3] |
| F6-3 | 517 | 13 / 16 | 0.297 (-0.2 pp [-0.5, +0.0]) | 0.065 (-0.2 pp [-0.5, +0.0]) | -0.6 pp [-1.8, +0.0] |
| F6-4 | 1123 | 17 / 20 | 0.297 (-0.2 pp [-0.5, +0.0]) | 0.063 (-0.4 pp [-0.9, -0.1]) | -0.6 pp [-1.8, +0.0] |

`hit@1`, `nDCG@10`, `recall@10` are unchanged in every configuration (the rule touches only the
injected set, never `ranked`). Abstentions: 0 in every arm. F6-2 fires on 58 queries and removes
71 cards: exposure −1.5 pp, completeness −0.9 pp — for every three exposures removed, roughly two
gold cards are lost, exactly the coin-flip the diagnostic predicted.

## 5. Freeze decision (per §3, mechanical)

All four configurations are within the ±1.0 pp point-estimate tolerance on `all_required@4` and
`hit@1`; F6-2 has the largest proxy reduction → **F6-2 (τ 0.80, N 3, margin) freezes**. Recorded
with its caveat in full: on dev the rule trades completeness for exposure at nearly 2:3, and its
`all_required@4` CI [−1.6, −0.3] excludes zero — dev says the discriminating-term heuristic has weak
power *on dev's labels*. The test-once run is what the protocol requires next and it is also the
only measurement that can tell duplicates from distractors: the hypothesis survives dev only in
the weak sense that dev could not refute it.

## 6. Test-once

TODO — only if §5 freezes a configuration.
