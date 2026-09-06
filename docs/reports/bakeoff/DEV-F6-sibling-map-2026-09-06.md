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

## 4. Dev results

TODO — filled by `tools/eval/dev_sibling.py run` after this protocol is committed.

## 5. Freeze decision

TODO.

## 6. Test-once

TODO — only if §5 freezes a configuration.
