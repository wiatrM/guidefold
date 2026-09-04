# ADR-0010: `SKILL.md` metadata is a flat map of scalar strings

**Status:** Accepted · 2026-09-04 (forced by Agent Registry validation, verified live)

## Context
Publishing the Meridian fixture to Agent Registry (project `guidefold-test-b6a18a`) failed for every
hand-written skill with:

```
SKILL.md validation failed: metadata key-value pairs must be scalar strings.
```

CONVENTIONS.md v0.1 put YAML lists in `metadata.requires` / `metadata.references` and a bare date
in `metadata.since`. The Agent Skills spec calls `metadata` "arbitrary key-value pairs"; the
registry enforces the strict reading (string → string). The generated `hierarchy-index` skill,
whose metadata was all strings, published fine.

## Options
1. **Comma-separated strings in `metadata`** — `requires: "urn:a, urn:b"`, `since: "2026-09-04"`.
2. Move Guidefold-specific structure to a sidecar (`guidefold.yaml` next to `SKILL.md`).
3. Rewrite the frontmatter at publish time (registry copy differs from git).

## Decision
Option 1. Every `metadata` value is a scalar string; lists are comma-separated (whitespace after
commas allowed); dates are quoted; booleans are `"true"`/`"false"`. `guidefold validate` fails on
any non-string value, so the mistake surfaces in the skill PR, not at publish. The CLI reads lists
through one helper (`md_list`) that also tolerates YAML lists so old skills get a clear error.

## Consequences
- One file per skill stays the rule; every harness and the registry read the same bytes.
- The 26 fixture skills and CONVENTIONS.md §4 were rewritten accordingly.
- `requires` URNs remain inside `SKILL.md`, so semantic search still sees them.
- Sidecar files (option 2) remain available later for data that should not ship to the registry.
