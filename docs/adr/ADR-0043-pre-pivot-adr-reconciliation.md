# ADR-0043: Reconciliation of the pre-pivot ADRs with what the code does

**Status:** Accepted · 2026-09-12 · decision of the product owner in the audit brief of the same
day ("zrób audyt założeń i doców projektu i porównaj z implementacją … zaktualizuj ADR, które
czujesz, że muszą być aktywne"). This ADR records which earlier decisions the implemented pivot
has overtaken; it does not add scope. The owner can revert any row by a dated amendment.
Merged to `main` on 2026-09-15 from the audit branch, with the code evidence re-verified against
`main` @ `2a302f5`; the decision, its date and its owner are unchanged.
**Supersedes:** [ADR-0013](ADR-0013-knowledge-api-holds-proposals-git-holds-text.md) (separate
Knowledge API on Cloud Run + Cloud SQL), the GCS clause of
[ADR-0018](ADR-0018-skills-stay-in-monorepo-one-postgres-gcs.md), the "serve from a self-hosted
skill-tuned model from Phase 1" clause of [ADR-0015](ADR-0015-self-hosted-skill-tuned-models.md),
the G0–G7 state machine of [ADR-0016](ADR-0016-knowledge-lifecycle-gates-and-layers.md).
**Parks (not superseded, not extended):** [ADR-0009](ADR-0009-hybrid-retrieval-client-side.md)
v2 pipeline items never built (query rewrite, family caps, listwise rerank),
[ADR-0021](ADR-0021-index-sharding-and-a-global-word-table.md) (per-node shards),
[ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) GPU worker,
[ADR-0024](ADR-0024-target-architecture-tiers-flywheel-composer.md) tier T2, telemetry flywheel and
model composer, [ADR-0027](ADR-0027-gpu-retrieval-profile.md).
**Amends:** [ADR-0029](ADR-0029-product-focus-hard-rules.md) rule 1 (the frozen surface is now the
pivot surface of ADR-0031) and rule 4 (the order of work is `docs/PIVOT-BACKLOG.md` P01–P16 until
the owner transfers it to GitHub Issues); rules 2, 3, 5, 6 and 7 stand unchanged.
**Governs:** `docs/adr/README.md`, `docs/MVP.md` §8 (historical), every agent brief that cites a
pre-pivot ADR.

## Context

An audit on 2026-09-12 compared all 42 ADRs with `services/search`, the CLI, `ui/` and `deploy/`.
The code follows [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md) (Accepted the same
day) and [ADR-0033](ADR-0033-api-contract-first-and-mvp-storage.md): one Go modular monolith with
`gf` and `gfm` schemas in one Postgres, blobs and jobs in Postgres, WorkOS identity, a React
console, a worker, a GitHub App registry, BM25F as the only production retrieval. Several earlier
ADRs still carry `Accepted` or `Proposed` while describing a system that was never built or was
replaced. The evidence column below was re-checked against `main` @ `2a302f5` on 2026-09-15 and
still holds:

| ADR | What it decided | What the code does (evidence, re-verified 2026-09-15) |
|---|---|---|
| 0013 | Knowledge API as its own Cloud Run service over Cloud SQL | `internal/{review,knowledge}` inside the monolith; `gfm.proposals` in the same Postgres (`internal/schema/importer.go`) |
| 0015 | bake-off winner serves queries from a GPU; own fine-tune from Phase 1 | `weights["w_dense"] = 0` still ships in the router (`skills/guidefold/scripts/guidefold:593`); dense is a gated research track (ADR-0029 rule 2; PRODUCT-PIVOT §1 "Domyślnie") |
| 0016 | eight-state lifecycle with gates G0–G7 | six-state `publication_status` CHECK — `draft, approved_for_export, awaiting_git, published, needs_review, archived` (`internal/schema/importer.go`; ADR-0031 §7) |
| 0018 | GCS holds artifacts | only `PostgresBlobStore` behind the `BlobStore` port (`internal/importer/blobstore.go`) |
| 0009 / 0021 | model rewrite, family caps, listwise rerank; per-node shards | none of it exists in the CLI (`grep` 0 hits); ADR-0022 items 1–3 are what landed |
| 0023 / 0024 / 0027 | GPU worker, tier T2, flywheel, model composer, TEI profile | T0/T1 only (`deploy/t1`, `deploy/k8s`); no GPU deployment artifact exists in the repository |
| 0029 rule 1 | no new runtime components until the pilot reports | identity, importer, review, worker, UI, extension exist under ADR-0031 |
| 0029 rule 4 | backlog lives in GitHub Issues | on 2026-09-12: 47 open issues, 0 closed since 2026-09-08; the order of work is `docs/PIVOT-BACKLOG.md` |

Leaving these statuses untouched lets an agent brief cite an "Accepted" ADR for a component the
owner has since frozen or replaced.

## Decision

1. The ADRs in `Supersedes:` are inactive for the clauses named there. Their files keep their
   historical status line and receive a `Superseded by ADR-0043` annotation; nothing else in them
   is edited.
2. The ADRs in `Parks:` stay Proposed. Nothing in them is extended, put on the critical path or
   cited as permission for a new component (ADR-0029 rule 1 as amended here). Reviving one
   requires a new ADR with measurements from the pilot.
3. ADR-0029 rules 2, 3, 5, 6 and 7 remain hard rules: dense is research only, "done" means used by
   a person who did not build Guidefold, one research family at a time, the pilot decides, KISS
   review before merge.
4. ADR-0029 rule 4 is read as: `docs/PIVOT-BACKLOG.md` P01–P16 is the order of work; the GitHub
   Issues #71–#117 are the historical backlog until the owner transfers P01–P16 to Issues or
   closes them. Two lists are not both authoritative.
5. `docs/MVP.md` §8 is historical. `docs/adr/README.md` is the only ADR index; its footer no
   longer points at MVP §8 for pending decisions.
6. An ADR that has been implemented and enforced in code for more than one contract version is
   not left `Proposed` for lack of a ceremony: 0028, 0030, 0031 and 0033 are Accepted on
   2026-09-12 under the same owner instruction. Later the same day the owner answered the audit's
   questions: 0039 is Accepted as an opt-in policy only and 0042 is Accepted with backlog slot P16;
   0036 stays Proposed with an order to finish `ascend.run` now; 0040 stays Proposed (no edgewise
   run in the repository).

## Consequences

- Agent briefs cite ADR-0031/0033 for the service shape, ADR-0032 for engineering rules,
  ADR-0029 rules 2–7 for scope discipline. Citing 0013, 0015 (serving clause), 0016 (G-gates) or
  0018 (GCS) as current is a review defect.
- `docs/PRODUCT-FOCUS.md` kill criteria (partner by 2026-09-20, twenty real sessions and a second
  harness by 2026-10-04) are unchanged by this ADR and were unmet on its date. They were still
  unmet on 2026-09-15: see
  [`docs/reports/product/2026-09-15-mvp-closure-status.md`](../reports/product/2026-09-15-mvp-closure-status.md).
- The reciprocal annotations owed by ADR-0033 to 0018/0026, by ADR-0040 to 0035 and by ADR-0042
  to 0036/0038 are added in the same change as this file.
- The order of work this ADR fixes is the one in `docs/PIVOT-BACKLOG.md`; the sequencing **inside**
  Pilot Core was revised on 2026-09-15 by the closure report (ACT-01 evidence before P16). That
  revision changes priority, not any status recorded here.

## References

Audit: [`docs/reports/product/2026-09-12-assumptions-vs-implementation-audit.md`](../reports/product/2026-09-12-assumptions-vs-implementation-audit.md).
`services/search/internal/README.md`, `services/search/internal/schema/importer.go`,
`services/search/internal/importer/blobstore.go`, `docs/PIVOT-BACKLOG.md`, `docs/MVP.md` §8.
