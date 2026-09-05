# ADR-0022: Separate admissibility, relevance, and bundle completeness

**Status:** Proposed · 2026-09-05
**Proposed by:** the E1.3 peer reviewer; written up and the first three repairs landed by the TL
**Amends:** [ADR-0020](ADR-0020-two-tier-dense-retrieval.md) (fixed-point contract, `w_dense` semantics),
[ADR-0021](ADR-0021-index-sharding-and-a-global-word-table.md) (word-table identity, §Consequences)
**Evidence:** [`E1.3-peer-review-2026-09-05.md`](../reports/bakeoff/E1.3-peer-review-2026-09-05.md),
[`E1-closure-plan.md`](../reports/bakeoff/E1-closure-plan.md)

## Context

The E1 router mixes three decisions into one pass: *may this skill be shown at all* (status,
scope, negative triggers), *how relevant is it* (BM25, dense, fusion), and *is the returned set
sufficient* (dependencies, budget). The peer review showed that the mixing is where the errors
hid. Three of them were latent in code and are repaired in the same change as this ADR:

1. **BM25 had a fixed-point units error.** `k1` was scaled by 2²⁰; the weighted term frequency it
   was added to was not. Measured on equal-length documents with a term repeated 1 / 10 / 100
   times: integer scores **1 / 24 / 249** — near-linear, where BM25 saturates at 1 : 1.96 : 2.17 —
   and truncation to zero for low-TF matches. Every BM25 number reported before this ADR was
   computed with that formula. Rankings still looked sane because the rarest matching term
   dominates either way; they were not BM25.
2. **`requires` expansion re-admitted rejected skills.** Dependency closure checked only
   `status == deprecated`; a dependency outside the caller's scope or hit by a negative trigger
   was pulled straight into the injected cards.
3. **`w_dense = 0` did not switch anything off.** The weight was never read. The dense channel ran,
   and cast its RRF vote, whenever a word table existed. It was "off" only because the table was
   empty — and the bake-off arms that *did* have a table were therefore not measuring the
   configuration the manifest described.

The review also found the bake-off arms ran on the unfiltered corpus while the product sees
filtered candidates, that `completeness@4` ignored required companions (65 % of multi-skill
bundles are incomplete on the shipped path once they are counted), and that the reranker's
regression was mostly a deprecated skill leaking into its candidates. All of these are the same
failure: **a decision made in one stage was not honoured in another.**

## Decision

The pipeline has five stages with one responsibility each, and a decision made in a stage binds
every later stage and every evaluation harness.

```
query + node + index sha
  │
  ▼
[1] ADMISSIBILITY   status · scope · negative triggers            → the admissible set A
  │                 decided once; A governs everything below
  ▼
[2] CANDIDATES      BM25F over A   ∪   dense over A (only if w_dense > 0)
  ▼
[3] RELEVANCE       RRF · scope feature · graph propagation      → ranked list, integer scores
  ▼
[4] COMPOSITION     requires closure ⊆ A · budget k · cycle-safe  → a bundle, or "cannot fit"
  ▼
[5] SUFFICIENCY     abstain? · all required present?             → cards, or silence + reason
```

**1. Admissibility is decided once and applies everywhere.** `policy_filter` produces the set
`A`. Candidates come from `A`. Dependency expansion may only add members of `A`; a dependency
outside `A` is an *unresolved requirement*, surfaced as such, never silently injected. The
benchmark, the CLI, the shadow reranker and any future dense channel all consume the same `A`
for the same `(query, node, sha)`. *Repaired in this change:* `select()` takes `admissible`, and
`route()` passes the filter's output.

**2. BM25F stays the fast-hook core, on one fixed-point scale.** `idf`, `k1`, the length
normaliser and the weighted TF all live on `S = 2²⁰`; the per-term quotient lands on `S`. A
reference test asserts the integer scores reproduce the float formula's shape (saturating, not
linear) and absolute value within 1 %. The benchmark harness must call the CLI's BM25, not its
own; "identical rankings 220/220" is the acceptance test.

**3. A channel weight of zero disables the channel.** `w_dense = 0` means no vector arithmetic,
no dense rank, no RRF vote. *Repaired in this change.* Dense re-enters only by first proving it
adds **admissible required skills that BM25 missed** (coverage), and only then by re-ordering.

**4. Composition is its own component.** It resolves several independent requirements, full
`requires` closure, shared prerequisites and cycles inside a card/token budget, and it says so
when the complete bundle **cannot fit** rather than returning a truncated set labelled complete.
`similar` is an alternative; `refines` needs an explicit semantics before it drives composition.
Its metric is `all_required@k`, not `hit@1`.

**5. Sufficiency, including abstention, is evaluated on its own axis.** Wrong injection on an
unanswerable query, wrong silence on an answerable one, harmful-sibling exposure (HSR@k) and
coverage are reported together. Any threshold is calibrated on a dev split, never chosen on the
test set. RRF scores may be a feature; they are not a confidence.

**6. Model and cache identity is complete.** A cache key for any encoded text covers the document
content, model revision, tokenizer, input instruction, truncation, pooling and normalisation; the
distilled student additionally covers vocabulary, weighting, projection and quantisation. A
teacher's commit sha alone is not an identity — which amends ADR-0021: the word table is keyed by
the *distillation identity*, not by the teacher alone, and a corpus-derived vocabulary makes it
corpus-dependent after all. Its "language artifact" status holds only for a vocabulary fixed
independently of the corpus.

**7. Sharding follows measurement.** ADR-0021's shard design must state how cross-shard
`requires` resolve and whether IDF is per-shard or global before it is implemented. Neither PPR,
sharding nor vocabulary growth is adopted without a named quality or resource limit it relieves.

## Consequences

**Immediately.** BM25 scores change for every query: the golden baseline is regenerated
*deliberately* in the same change, and the diff is reported, not hidden. `all_required@4` on the
shipped path is the new headline completeness number (0.65 on multi-skill). Nothing about latency
or determinism changes — the fix is integer arithmetic on integer arithmetic.

**For the next bake-off.** Every arm runs `[1]→[4]` from the shipped `Router` at the shipped
budget. Acceptance per the closure plan: non-inferior `all_required@4`, non-worsening HSR@4,
warm p95 inside the hook budget, on a frozen pilot set.

**What this costs.** One more parameter on `select()`; one extra `policy_filter` pass in `route()`
(a dictionary scan — microseconds); a reference test that pins BM25 to its formula, which will fail
loudly if anyone changes `IDF_SCALE` without updating every term. That is the point.

## Order of work

| # | work | done when |
|---|---|---|
| 1 | fixed-point BM25, `w_dense` gate, admissible closure | **this change**; reference tests green; baseline regenerated with the diff in the PR |
| 2 | one admissibility policy across benchmark and CLI; explicit denominators; per-query rankings recorded | benchmark B1 = CLI ranking 220/220; every table names its n |
| 3 | composer: multi-requirement, closure, cycles, "cannot fit" | tests for each; `all_required@4` reported per stratum |
| 4 | frozen pilot test set; abstention as a calibrated component | split by task family; criteria written before the run |
| 5 | fair semantic experiment on the fixed ruler | sparse · +contextual dense (coverage first) · +reranker · students, same `A`, same budget |
| 6 | execution-level evaluation | no skills · selected bundle · oracle bundle · wrong sibling; success, cost, time |

The 220-case golden set remains the dev/regression fixture. Latency is measured for the whole
hook on the target machine, cold and warm separately; batch time divided by query count is not a
user's latency.
