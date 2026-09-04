# ADR-0008: Hierarchy lives in the registry resource ID; the URN is system-assigned

**Status:** Accepted · 2026-09-04 (verified live on project guidefold-test-b6a18a; amends ADR-0002, which is deleted)

## Context
ADR-0002 assumed we could mint `urn:skill:meridian:<node>:<name>` as the `skillId`. Verified against
Agent Registry v1alpha on 2026-09-04 (project `guidefold-test-b6a18a`):

- The URN is **assigned by the server**: `urn:skill:projects-<NUMBER>:locations:<LOCATION>:private-<RESOURCE_ID>`.
  Custom publishers cannot be created (Publisher has only `get`/`list`); user skills are `private-`.
- The resource ID we choose is prefixed with `private-` by the server. Double hyphens are accepted.
- Keyword search supports a trailing-wildcard prefix on `skillId` in the **short form**
  `skillId:private-meridian--atlas*`; the full-URN form returned nothing. Quoted phrases such as
  `"[atlas/identity/turnstile]"` match the description tag. Semantic search mixes in Google's
  first-party skills (`urn:skill:cloud.google.com:*`), so results must be filtered by our prefix.
- A skill is created in `draft`; it becomes `active` only after a revision exists and is set as
  default. `skills create --payload` without `--initial-revision-name` created **no** revision.

## Decision
1. **Logical URN stays ours, registry URN is derived.** Guidefold keeps
   `urn:skill:<publisher>:<node>:<name>` as the logical identifier in `metadata`, `requires`, cards
   and the index. The registry resource ID is a deterministic, injective mapping:
   `<publisher>--<node with '.' → '-'>--<name>`; root uses `_root` → `root`. Example:
   `meridian--atlas-identity-turnstile--postgres-auth` → registry URN
   `urn:skill:projects-777479017000:locations:global:private-meridian--atlas-identity-turnstile--postgres-auth`.
   `--` is the segment separator, so hyphens inside node or skill names stay unambiguous
   (`shared.auth-sdk` → `meridian--shared-auth-sdk--auth-sdk-usage`).
2. **Subtree and exact-node queries use the short prefix form:**
   `skillId:private-<publisher>--<node-hyphenated>*` (subtree) and
   `skillId:private-<publisher>--<node-hyphenated>--*` (exact node). Client filters results by
   the `private-<publisher>--` prefix to drop first-party skills.
3. **Publish sequence:** `skills create <id> --target-state=draft --payload=<zip>` (or
   `revisions create` for an existing skill) → `skills update --default-revision=<rev>` →
   `skills update --target-state=active`. Never `--initial-revision-name` unless it is proven to
   carry the `private-` prefix (see verification log in `docs/ASSESSMENT.md`).
4. The `[node/path]` description prefix (ADR-0002) is kept: it is the only keyword-searchable
   place where the exact node appears without hyphen flattening.

## Consequences
- ADR-0002's "hierarchy in the URN namespace" becomes "hierarchy in the resource ID + description
  tag". Nothing changes for skill authors.
- `guidefold.yaml.publisher` is a naming prefix, not a registry Publisher.
- `find`/`hook` must post-filter by prefix and map registry URNs back to logical URNs (strip
  `private-<publisher>--`, split on `--`, restore dots).
