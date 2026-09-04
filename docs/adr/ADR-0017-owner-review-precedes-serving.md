# ADR-0017: Owner review precedes any serving; agents cannot approve

**Status:** Accepted · 2026-09-04 (safety invariant of the approved lifecycle)

## Decision
GitHub PR review by CODEOWNERS is the only approval mechanism for skill text. The Knowledge API refuses approve/reject/vouch calls whose origin is an agent session; the bot never merges; humans never push to `proposal/*`; everyone except CI holds `agentregistry.viewer`. Governance kinds (`policy`, `compliance`, `security`, `architecture`) refuse agent origin entirely.

## Consequences
- Prompt-injection or poisoned sessions can create proposals, never active skills.
- Audit: `audit_event` (hash-chained) and the GitHub Enterprise audit log stream to BigQuery for 7 years.
