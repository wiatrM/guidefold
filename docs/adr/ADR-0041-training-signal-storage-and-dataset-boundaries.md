# ADR-0041: Training-signal storage and dataset boundaries

**Status:** Accepted · 2026-09-09 · owner directive: design and implement storage for future model training
**Amends:** [ADR-0033](ADR-0033-api-contract-first-and-mvp-storage.md) for the telemetry dataset projection only.
**Governs:** `gf.training_examples`, telemetry export and future PBSD dataset builders.

## Context

Guidefold already stores an append-only, tenant-scoped event ledger in `gf.events`.
PBSD needs more than delivery counts: each training candidate needs immutable
snapshot/revision/scope provenance, proof predicates, the `LOAD`/`ASK` decision,
execution outcome and reviewer labels. The PBSD protocol requires repository-level
DEV/calibration/TEST splits and forbids tuning on the sealed TEST split.

Raw prompts, skill bodies, repository code, bearer tokens and personal identifiers
must not become a default training export. A query hash is a correlation key, not
an anonymous training example. The MVP already chooses Postgres over a second
object store for the ledger; introducing a bucket as a second source of truth
would add an authorization and retention boundary before the pilot.

## Decision

1. `gf.events` remains the source ledger. `gf.training_examples` is an append-only,
   tenant-scoped, redacted projection written by Telemetry/Reporting only.
2. A record may contain identifiers, hashes, model/router/policy revisions,
   candidate proof features, decision, outcome, token/tool/time counters and
   reviewer labels; it must not contain raw prompt, body, source text, bearer
   token or email. `content_mode` is `metadata_only` by default.
3. Dataset split is immutable and closed to `{dev, calibration, test}`. Split
   assignment is by repository/source family, never by individual query. TEST
   rows are readable for evaluation but are not eligible for training exports.
4. Every record carries `schema_version`, `dataset_version`, `case_id` or run
   correlation, source/snapshot hashes, and a provenance digest. Duplicate
   transport is rejected by `(tenant_id, event_id)`; duplicate examples by
   `(tenant_id, example_id)`.
5. Export to a future bucket is a derived, redacted artifact with a manifest,
   split hash, retention date and approval audit. It is not part of this MVP
   migration and cannot bypass tenant authorization.

## Consequences

The database can retain high-value supervision without retaining private content.
The first implementation supplies durable storage and schema guardrails; adapters
must explicitly emit the approved redacted signal fields before examples exist.
No current event is silently reclassified as a training label. Missing labels,
outcomes or provenance remain `unknown`, not a negative example. This ADR does not
claim a fine-tuning dataset exists or that PBSD has passed its confirmatory gates.

## References

- [PBSD protocol](../../research/proof-budgeted-skill-delivery-2026-09-09/PROTOCOL.md)
- [Telemetry contract](../SEARCH-USE-TELEMETRY.md)
- [API contract §7](../API-CONTRACT.md)
