# ADR-0040: Edgewise, source-grounded ascent for abstract skill maps

**Status:** Proposed · 2026-09-09 · research direction after the staged ascent pilots
**Amends:** [ADR-0035](ADR-0035-knowledge-ascent-in-ci.md): changes the proposed model-call
shape while preserving owner review and the PR boundary; [ADR-0039](ADR-0039-proof-gated-source-grounded-delivery.md): applies the provisional proof state to generated maps.
**Evidence:** [`edgewise Qwen7B pilot`](../../research/ascend-qwen7b-edgewise-2026-09-09/README.md)
and its [`post-gate replay`](../../research/ascend-qwen7b-edgewise-2026-09-09/postgate-replay.json).

## Context

The original ascent prompt asks one model call to choose an action and write a complete map or
convention card. On the real fixture, Qwen2.5-1.5B produced zero accepted cards in 16 calls and
Qwen2.5-7B produced zero in a forced-create ablation. A staged single-parent call accepted only
four of eight scopes. The remaining failure was prompt fan-out: broad parents contain too many
children and the model either truncates or declines to synthesize.

The edgewise pilot instead asks for one bounded relation per parent→child edge. A deterministic
renderer assembles a parent card only after all edges are present, source URNs belong to the child
subtree, and summaries stay within the cap. Sixteen of sixteen edges passed those checks and all
eight parent cards passed the original proof draft gate. A later deprecated-source safeguard
correctly held one card for review, leaving seven of eight safe under the strengthened policy.

## Decision

1. Treat edgewise atoms (`child scope`, bounded summary, source URNs) as the proposed generation
   interface for future automatic map ascent. The model never chooses filenames, proof status,
   source ranges or whether a scope is admitted.
2. Let deterministic policy require exact direct-child coverage, reject duplicates and unknown
   scopes, require every source to belong to the cited child subtree, and hold any claim citing a
   deprecated source for owner review.
3. Render the parent body, claims and provisional `source_proof` deterministically. Generated
   cards remain `verified: false`/`pending_review` until a trusted importer or owner binds exact
   ranges and the immutable snapshot.
4. Build parents recursively from bounded edges, with fan-out limits and an explicit incomplete
   outcome. Keep the current full-card path until this proposal is implemented and reviewed.
5. Evaluate semantic correctness and task utility separately. This ADR makes no claim about
   Recall@k, agent pass rate or user productivity.

## Consequences

- Prompts stay short as the tree grows, and a single bad edge cannot silently create a complete
  parent card.
- The number of model calls grows with edges, so latency and cost need measurement and caching.
- Exact source hashes and a visible pending proof make generated summaries auditable, while the
  deprecated-source rule prevents a known class of scope conflation.
- Four positive structural cards are not enough for publication. Two independent semantic raters
  and held-out execution on an unseen repository remain required.

## Rejected

- One large full-card prompt with a model-selected `no_change` action: it truncated or declined
  on the fixture.
- Forcing `create` in the same prompt: it restored truncation (3/8 parseable, 0/8 complete).
- Treating lexical overlap or a model judge as semantic proof: both are diagnostics only.
