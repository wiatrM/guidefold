# Source-disjoint URCT preparation — 2026-09-10

**Status:** prepared, not annotated, no model calls. This is an input-quality artifact for the
proof-gated hierarchy experiment; it is not task or retrieval evidence.

The old URCT packet used A/B sources owned by the same organization. This replacement uses two
families with three pairwise distinct GitHub owners per family:

| Family | A | B | C (held-out target) | C′ |
|---|---|---|---|---|
| engineering | obra/superpowers | wshobson/agents | JeffAllan/claude-skills | controlled C drift copy |
| documentation | anthropics/skills | K-Dense-AI/claude-scientific-skills | wshobson/agents | controlled C drift copy |

The manifest records immutable repository commits, source paths, SHA-256 digests, line counts and
lineage. Local bodies are kept under `.guidefold/checks/source-disjoint-urct-2026-09-10/` and are
ignored by Git. An independent verification run found **2 families, 8 records, 4 cases, and
three distinct source owners in each family; all snapshot hashes matched**.

C′ is a deterministic controlled semantic derivative used to exercise revision drift. It is not an upstream
historical commit, so the publication experiment must either retain this limitation explicitly or
replace C′ with a real later commit before making a historical-drift claim.

Before any model call, two reviewers must independently label applicability, scope, revision,
closure, semantic usefulness, and whether the correct action is `ASK`. Disagreements require a
separate adjudication record. The current state is `PREPARED_NOT_ANNOTATED`; no task-success,
retrieval-quality or user-value claim follows from this artifact.

Manifest: `SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json`.

The local check artifact now also contains a four-packet, two-reviewer blinded annotation packet
under `.guidefold/checks/source-disjoint-urct-2026-09-10/annotation_packet/`. Its manifest hash is
`2e3887610dba163ec2118eb51bcd3b59c94640a1081a62c607c6ec264acb288e`; the packet verifier found
all labels blank and `model_calls_allowed=false`. The independent public-commit replay using `fetch_source_disjoint_urct.py` also rebuilt all 8 records with matching hashes. The packet must be copied or regenerated after
any corpus change, and it cannot be used as a quality result until two reviewers and an adjudicator
complete it.
