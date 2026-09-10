# E2 proof-gated delivery matrix — 2026-09-10

**Status:** regression evidence only; synthetic fixture, not pilot or user evidence.

This matrix is the next quality gate for the product direction. It exercises the same
`proofGate` used by the 1.2 USE delivery path and checks that unsafe inputs end in `ASK`
before skill bytes are exposed. It does not measure ranking, task completion, or developer
value. Those require the frozen paired-task protocol in `docs/pilot/E6.7-PROTOCOL.md` and
real repository snapshots.

## Reproduction

```text
cd services/search
go test -run TestE2ProofGatedDeliveryMatrix -v .
```

The run uses Go 1.26 in the repository's `golang:1.26` container. The fixture is built in
`services/search/e2_proof_gate_test.go`; it contains active `auth-v1`/`auth-v2` siblings,
a deprecated sibling, a narrower child scope, and an unrelated database scope. No model,
network, or gold label is used.

## Result

| Scenario | Expected action | Reason |
|---|---|---|
| current version | `LOAD` | `source_proof_complete` |
| conflicting v1 sibling | `ASK` | `proof_conflict` |
| deprecated sibling | `ASK` | `skill_not_active` |
| narrow child in its scope | `LOAD` | `source_proof_complete` |
| narrow child outside its scope | `ASK` | `skill_outside_resolved_scope` |
| published revision drift | `ASK` | `revision_mismatch` |
| body tampering | `ASK` | `proof_body_hash_mismatch` |
| incomplete dependency closure | `ASK` | `closure_incomplete` |

The targeted test passed with **2 safe loads, 6 abstentions, and 0 proof-gated harmful
loads**. The six abstention cases are the negative safety controls; they are not a claim
that a production workload will have a zero harmful-load rate. A flat concatenation arm
would expose the selected candidate bytes by construction, which is why it is retained as
the harmful-load control for the real E2 run.

## What this unlocks

The service boundary is now protected by a repeatable regression test for conflict, scope,
revision, integrity, and closure failure. The next experiment must run the same arms on
real monorepo snapshots and frozen tasks, with two independent human judgements where a
deterministic verifier is impossible. The report must include task success, harness errors,
SEARCH/USE/ASK counts, tokens, latency, and unknown coverage; synthetic passes do not close
that gate.
