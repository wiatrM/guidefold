# Hierarchy SEARCH smoke — 2026-09-10

**Status:** fixture diagnostic; not pilot evidence and not a task-success result.

This replay checks that the same bridge can issue scoped SEARCH requests over a real Git snapshot
with nested owners, and that its merge order is observable. It uses the 26 published cards from
the committed examples/monorepo snapshot at revision
23709b6563464b6223fa60c435a692629dea0baf. The local feasibility server exposed contract 1.1, so
this replay used legacy USE; proof-gated delivery remains covered by the Go service tests and was
not silently approximated here.

## Frozen query and scopes

Query: “Use the current RBAC auth policy for the turnstile endpoint and avoid deprecated session
auth.”

The nodes file listed platforms/atlas/identity, platforms/atlas and infra/relay. The bridge sent
the query unchanged and merged duplicate cards using the scores from each response's diagnostic
ranked list.

## Result

| Strategy | SEARCH calls | Selected cards (in order) |
|---|---:|---|
| flat | 1 | auth-sdk-usage, postgres-auth, rbac-policies, postgres-production |
| top_down | 3 | postgres-auth, security-baseline, atlas-api-conventions, adr-process |
| bottom_up | 3 | postgres-auth, security-baseline, atlas-api-conventions, adr-process |

The first flat card was then loaded through legacy USE: HTTP 200, action LOAD, body length
4,566 characters. The redacted bridge trace contained eight rows for the three searches and one
USE; no prompt, body or token appeared in the trace.

## Interpretation and limit

Scoped hierarchy changes the candidate set relative to root search, which validates the plumbing
needed for the ablation. Top-down and bottom-up tied on this query, so this run provides no
evidence that traversal direction improves retrieval. It does not measure task execution,
harmful sibling delivery or proof safety. The next run must use a proof-bearing 1.2 snapshot and
paired tasks where the expected answer depends on the active versus deprecated sibling.
