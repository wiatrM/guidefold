# ADR-0039: Proof-gated, source-grounded skill delivery

**Status:** Proposed · 2026-09-09 · direction from the product owner ("proof-gated delivery,
provenance, ASK")
**Amends:** [ADR-0022](ADR-0022-admissibility-relevance-and-bundle-completeness.md): adds a
post-retrieval source-proof boundary to delivery; [ADR-0025](ADR-0025-harness-service-context-contract.md):
adds an opt-in delivery policy to the versioned USE contract.
**Governs:** USE 1.2 `delivery_policy: "proof_gated"`, the top-level `source_proof` snapshot
record and its `proof` card projection, and the CLI `load --delivery-policy proof_gated` adapter.
**Evidence:** [`proof-gated-delivery-2026-09-09`](../../research/proof-gated-delivery-2026-09-09/README.md)
is a deterministic contract replay. The separately frozen
[`E2-Qwen replay`](../../research/e2-qwen-proof-gated-2026-09-09/README.md) is an exploratory
single-model mechanism signal, not evidence of semantic correctness, execution success or user
utility. A second separately frozen query-only replay with Qwen2.5-1.5B is
reported in [`E2-Qwen1.5 query-window replay`](../../research/e2-qwen15-query-window-2026-09-09/README.md):
it reproduces the direction (+25.00 pp) without using answer values for line
selection, but remains synthetic and single-corpus. Adoption as an accepted
product decision still requires the planned E2 and URCT-2 with two independent
assessments.

## Context

Retrieval quality and delivery authorization answer different questions. A high-ranked card can
be stale, have the wrong identity, omit a required scope, conflict with a sibling rule, or lack a
complete dependency closure. Injecting such a card gives an agent no safe way to distinguish
"relevant" from "authorized for this snapshot". The existing 1.1 path intentionally has no such
guarantee and must keep its legacy behavior.

The service already has immutable snapshots, revisions and closure metadata. The missing boundary
is a small, explicit decision after candidate selection: either return a card whose source-bound
proof is complete, or abstain with a bounded explanation that an adapter can show as `ASK`.

## Decision

1. Add an additive USE 1.2 request option, `delivery_policy: "proof_gated"`. The default and all
   1.1 requests remain unchanged. The option is rejected by local CLI delivery because the local
   path cannot establish the service snapshot and source binding.
2. A proof-gated `LOAD` is allowed only when all of the following match the active snapshot and
   selected card: proof schema `source-proof-v1`, `verified: true`, exact `skill_id`, revision,
   snapshot and body SHA-256, every requested scope is covered, every mandatory claim is
   `supported` with valid relative source references and line ranges, conflicts are absent, and
   dependency closure is complete. `verified` records a trusted importer or reviewer assertion;
   this ADR does not turn it into cryptographic authorship, semantic or runtime-execution proof.
   During publication, explicit `pending`/empty `snapshot`, `revision` and `body_sha256`
   placeholders are deterministically bound to the immutable snapshot, card revision and
   delivered bytes. The publisher never changes `verified` or overwrites a non-placeholder value.
   Before returning `LOAD`, the service requires each cited path and SHA to match either the
   selected package's active resource manifest or a skill/document published in the same
   repository snapshot, then fetches each cited content-addressed source blob (or uses the exact
   delivered `SKILL.md` body), verifies its SHA-256 and checks that the claimed line range exists.
   A missing snapshot binding/blob, digest mismatch or out-of-range reference is an `ASK`
   condition. This same-snapshot source lookup lets an automatically ascended parent cite the
   child skill files that support it without copying those files into the parent package.
3. Any missing, malformed, stale, conflicting or incomplete condition returns `ASK`. The response
   has `status: "ask"`, an empty body, one bounded reason from the contract enum, bounded missing
   requirement names, and redacted provenance containing identifiers, hashes, scopes, claims and
   line ranges only. It never returns source text or diagnostic candidate bodies.
4. The CLI adapter must not write an `ASK` body to its cache and records the load as denied with
   zero delivered bytes. A valid `LOAD` follows the existing checksum and cache path. Provenance is
   explanatory metadata, not a ranking feature and must not change candidate ordering.
5. The builder carries a top-level `source_proof` object from SKILL.md frontmatter into the card's
   `proof` field without putting it in scalar metadata or the retrieval index. This preserves the
   evidence alongside the immutable snapshot while keeping the gate after retrieval.
6. The deterministic replay is a release-contract check only: one valid proof must load and twelve
   targeted mutations must ask, with no source text in output. It is a regression guard for the
   boundary, not a claim that the policy improves Recall@k, task success, or the quality of a
   model's answer.

## Consequences

- A harness can safely surface uncertainty instead of silently injecting an unsupported skill. The
  user-facing choice becomes "load this source-grounded card" or "ask the owner / refresh the
  snapshot".
- Recent adjacent systems already provide source-grounded skill libraries and typed or
  hierarchical execution graphs (SkillCenter, GraSP, HiSkill, AIP and SkillAlchemy). This ADR
  therefore makes no novelty claim for citations, graphs or pyramids alone; its testable boundary
  is the pre-delivery check of monorepo identity, revision, scope and dependency closure.
- Provenance and revision drift become observable delivery states. Existing legacy integrations
  continue to receive their current response shape and behavior.
- The gate can abstain more often than it loads until import and review produce complete proofs;
  that is an intentional fail-closed trade-off and must be measured in E2/URCT-2.
- Binding publication placeholders removes the self-reference trap between a proof and the
  snapshot/card hashes. Card revisions exclude only the delivery proof envelope; body and all
  retrieval metadata remain part of the revision identity.
- The implementation validates proof structure, bindings and availability of the cited bytes but
  does not re-run the skill, assess semantic truth or verify reviewer identity. Those remain
  separate product and research work; no scientific breakthrough is claimed by this ADR.
- Acceptance is blocked on the pre-registered conflict experiment E2 and two-independent-rater
  URCT-2. If they do not show a useful reduction in wrong-rule delivery without unacceptable ASK
  rates, this remains a contract hardening experiment rather than the product's headline claim.

## Rejected

- Using a reranker score, Recall@10, or a confidence threshold as authorization. Scores express
  relevance and can be high for stale or conflicting content.
- Returning the best available body together with a warning. This preserves the unsafe ambiguity
  the gate is intended to remove and makes cache behavior non-deterministic.
- Requiring proof on the 1.1 path by silently changing its semantics. Existing adapters need a
  versioned opt-in and a reviewable migration boundary.

## References

- [Harness-service contract](../HARNESS-SERVICE-CONTRACT.md)
- [API contract](../API-CONTRACT.md)
- [E2/URCT-2 decision gate](../../research/scientific-status-2026-09-08/DECISION.md)
- [Proof-gated delivery replay](../../research/proof-gated-delivery-2026-09-09/README.md)
- [Exploratory E2-Qwen proof-gated replay](../../research/e2-qwen-proof-gated-2026-09-09/README.md)
- [Exploratory E2-Qwen1.5 query-window replay](../../research/e2-qwen15-query-window-2026-09-09/README.md)
