# Architecture Decision Records

Cross-cutting technical decisions for Meridian live here as numbered Markdown files, one decision per
file. The process is described by the root `adr-process` skill.

## Index

| ADR | Title | Status | Touches |
|-----|-------|--------|---------|
| 0001 | Single Bazel monorepo with per-node ownership | accepted | _root |
| 0002 | golang-migrate for forward-only Postgres migrations | accepted | _root, libs/db |
| 0003 | Closed classification label enum in libs/classification | accepted | security, libs |
| 0004 | Offline release bundle as the only supported install artefact | accepted | _root, relay |
| 0005 | H3 as the geospatial index for atlas | accepted | atlas.geo |
| 0006 | Hash-chained audit events with synchronous emit | accepted | security.audit |
| 0007 | Delegated short-lived tokens for service-to-service calls | proposed | shared.auth-sdk, atlas.identity |

Next free number: **0008**.

## Template

Copy this block into `docs/adr/NNNN-short-kebab-title.md`:

```
# NNNN: <Title>

Status: proposed | accepted | deprecated | superseded by NNNN
Date: YYYY-MM-DD
Owners: @meridian/<team>
Supersedes: NNNN (optional)

## Context
## Decision
## Alternatives considered
## Consequences
```

Rules in brief: numbers are never reused, accepted ADRs are not rewritten (supersede instead), file name
and H1 must match, and any ADR adding an external dependency states how it is mirrored for air-gapped bundles.
