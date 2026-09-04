# ADR-0014: Drift stays in-repo (code diff ∩ references), comment-only; symbol anchors are an optional upgrade

**Status:** Proposed · 2026-09-04 (revised after the storage review)

## Context
Skills stay in the code monorepo (ADR-0018), so the v0.3 drift check (code diff ∩ `metadata.references`, with `#token` grep) keeps working inside one repository and one CI.

## Decision
Keep the in-repo drift check as the path-filtered PR comment that names the skill and its owner. Record every drift hit as `evidence` in the Knowledge API so unacknowledged drift can trigger retirement proposals (G7). Optional upgrade: `references` may use `<path>#<symbol>` anchors with region hashes (fiberplane/drift format) when path-only references prove too noisy. Advisory in the code PR; blocking only for `policy` skills after 7 days unacknowledged.

## Consequences
- Drift works across repositories without cross-repo checkouts.
- Owners, not code authors, receive the alert; acknowledgement is recorded as evidence.
