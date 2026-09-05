# ADR-0022: Separate admissibility, relevance, and bundle completeness

**Status:** Proposed · 2026-09-05 · [ADR-0024](ADR-0024-target-architecture-tiers-flywheel-composer.md) (Proposed) proposes an amendment: the composition stage may be a model
**Proposed by:** the E1.3 peer reviewer; written up and the first three repairs landed by the TL
**Amends:** [ADR-0020](ADR-0020-two-tier-dense-retrieval.md) (fixed-point contract, `w_dense` semantics),
[ADR-0021](ADR-0021-index-sharding-and-a-global-word-table.md) (word-table identity, §Consequences)
**Evidence:** [`E1.3-peer-review-2026-09-05.md`](../reports/bakeoff/E1.3-peer-review-2026-09-05.md),
[`E1-closure-plan.md`](../reports/bakeoff/E1-closure-plan.md),
[`E1.3-architecture-after-research.md`](../reports/bakeoff/E1.3-architecture-after-research.md)

## Context

The E1 router mixes three decisions into one pass: *may this skill be shown at all* (status,
scope, negative triggers), *how relevant is it* (BM25, dense, fusion), and *is the returned set
sufficient* (dependencies, budget). The peer review showed that the mixing is where the errors
hid. The following three code defects were repaired in merge `c08c58c` (2026-09-05).
The broader pipeline below remains Proposed; the repairs do not complete the composer or evaluator:

1. **BM25 had a fixed-point units error.** `k1` was scaled by 2²⁰; the weighted term frequency it
   was added to was not. Measured on equal-length documents with a term repeated 1 / 10 / 100
   times: integer scores **1 / 24 / 249** — near-linear, where BM25 saturates at 1 : 1.96 : 2.17 —
   and truncation to zero for low-TF matches. This affected the shipped CLI BM25F and its
   historical baselines. Bake-off B1 used a separate floating-point pseudo-document BM25, so
   its scores were not computed with this defective formula. Both definitions need explicit
   provenance; the corrected CLI is the reference for future product comparisons.
2. **`requires` expansion re-admitted rejected skills.** Dependency closure checked only
   `status == deprecated`; a dependency outside the caller's scope or hit by a negative trigger
   was pulled straight into the injected cards.
3. **`w_dense = 0` did not switch anything off.** The weight was never read. The dense channel ran,
   and cast its RRF vote, whenever a word table existed. It was "off" only because the table was
   empty. The repair makes the manifest gate effective in the shipped Router. Offline bake-off
   arms used their own dense implementation and must be identified separately.

The review also found the bake-off arms ran on the unfiltered corpus while the product sees
filtered candidates, that historical `completeness@4` ignored required companions, and that the
reranker's stale-stratum regression was largely explained by deprecated candidates. For historical
unfiltered B1, counting all required skills changes multi-skill completeness from 63/66 (95.45 %)
to 49/66 (74.24 %); this is not the corrected CLI baseline. Policy, retrieval, composition and
metric semantics must be consistent across stages.

## Decision

**Proposed target.** The pipeline has five stages with one responsibility each, and a decision
made in a stage binds every later stage and every evaluation harness.

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
[5] SUFFICIENCY     abstain? · known requirements resolved?      → cards, or silence + reason
```

**1. Admissibility is decided once and applies everywhere.** `policy_filter` produces the set
`A`. Candidates come from `A`. Dependency expansion may only add members of `A`; a dependency
outside `A` is an *unresolved requirement*, surfaced as such, never silently injected. The
benchmark, the CLI, the shadow reranker and any future dense channel all consume the same `A`
for the same `(query, node, sha)`. *Implemented in `c08c58c`:* `route()` and `find` pass
`admissible` into `select()`, which skips excluded dependencies. The filter is currently recomputed
with the same inputs. Direct legacy calls with `admissible=None` retain only the deprecated check.
Returning an explicit unresolved-requirement result, rejecting incomplete bundles atomically and
requiring the policy contract in every evaluation adapter remain follow-up work.

**2. BM25F stays the fast-hook core, on one fixed-point scale.** `idf`, `k1`, the length
normaliser and the weighted TF all live on `S = 2²⁰`; the per-term quotient lands on `S`. A
reference test asserts the integer scores reproduce the float formula's shape (saturating, not
linear) and absolute value within 1 %. The benchmark harness must call the CLI's BM25, not its
own. Acceptance requires matching candidate sets, scores and rankings on all 220 regression
cases, plus artifact/in-memory parity; ranking agreement alone does not establish formula parity.

**3. A channel weight of zero disables the channel.** `w_dense = 0` means no vector arithmetic,
no dense rank, no RRF vote. *Implemented in `c08c58c`.* Dense re-enters only by first proving it
adds **admissible required skills that BM25 missed** (coverage), and only then by re-ordering.

**4. Composition is its own component.** It resolves several independent requirements, full
`requires` closure, shared prerequisites and cycles inside a card/token budget, and it says so
when the complete bundle **cannot fit** rather than returning a truncated set labelled complete.
Requirements form AND groups, with OR choices only among verified functional substitutes within
a group. A `similar` edge establishes similarity, not substitutability; `refines` also needs
explicit semantics before it drives composition. SkillRouter v5 Appendix A distinguishes
pipeline, substitute and mixed multi-skill tasks. Evaluation uses `all_required@k` against the
labelled requirements. Runtime can check declared dependencies and recognised task requirements;
it cannot observe the evaluator's oracle gold set. The current depth-2, greedy selection is not
yet this full composer.

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

**7. Sharding follows measurement.** ADR-0021's shard design must resolve cross-shard
`requires` and preserve comparable BM25F scores across shards before implementation. Use shared
corpus IDF and length statistics as the reference; per-shard statistics need an explicit, tested
score-comparability contract. Neither PPR, sharding nor vocabulary growth is adopted without a
named quality or resource limit it relieves.

## Consequences

**Immediately.** The BM25F repair changes score semantics and can change rankings. The golden
baseline was regenerated in the repair; old measurements retain their original revision and
metric names. Report the corrected baseline's `all_required@4` with its SHA and numerator/denominator.
Integer arithmetic is retained, but latency and reproducibility claims require their own checks;
pre-repair timings do not establish post-repair performance.

**For the next bake-off.** Every arm shares the shipped policy, sparse scorer and composer
contracts at the shipped budget; optional neural adapters live outside the stdlib CLI. Acceptance
per the closure plan: predeclared non-inferiority on `all_required@4`, non-worsening HSR@4, a
measured benefit that justifies added cost, and whole-hook warm p95 inside the hook budget, on a
frozen pilot set. Downstream utility includes success and cost, not retrieval metrics alone.

**What this costs.** One more parameter on `select()`, a repeated policy-filter scan in the
current `route()`, and reference tests that pin BM25F to its formula. Measure their end-to-end cost
on the target machine. Shared policy evaluation and explicit incomplete-bundle handling remain
implementation work.

## Order of work

| # | work | done when |
|---|---|---|
| 1 | fixed-point BM25, `w_dense` gate, skip inadmissible dependencies | **implemented in `c08c58c`**; reference tests and probes passed; baseline regenerated; full composer remains item 3 |
| 2 | one admissibility policy across benchmark and CLI; explicit denominators; per-query rankings recorded | candidate sets, scores and rankings match on 220/220 cases; every table names its n |
| 3 | composer: multi-requirement, closure, cycles, "cannot fit" | tests for each; `all_required@4` reported per stratum |
| 4 | frozen pilot test set; abstention as a calibrated component | split by task family; criteria written before the run |
| 5 | fair semantic experiment on the fixed ruler | sparse · +contextual dense (coverage first) · +reranker · students, same `A`, same budget |
| 6 | execution-level evaluation | no skills · selected bundle · oracle bundle · wrong sibling; success, cost, time |

The 220-case golden set remains the dev/regression fixture. Latency is measured for the whole
hook on the target machine, cold and warm separately; batch time divided by query count is not a
user's latency.
