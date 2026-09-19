# Source-backed E2 through Go HTTP — 2026-09-11

## Status

This is an opt-in integration replay. It uses the actual Guidefold publication worker and the
HTTP `USE 1.2` handler, while reading source bytes from the fresh source-disjoint snapshot
replay. It is a delivery-integrity check, not a task-success or human semantic evaluation.

## Frozen inputs

- Source replay: `/tmp/guidefold-urct-replay-next`
- Manifest SHA-256: `47a145923f1fb256a2d6c03f9a117fbbde9fe99a6ec1d0d419bc9b0c7fa1f3ec`
- Targets: engineering C/C′ and documentation C/C′ (four source files).
- Test: [`services/search/e2_source_backed_http_test.go`](../../services/search/e2_source_backed_http_test.go)

For each target, the test copies the exact source bytes into a published reference resource,
creates a proof-bearing skill card whose claim hash binds those bytes, publishes through the
real import/parse/build path, then calls `/v1/use` with `delivery_policy: proof_gated`. It
requires `delivery.action=LOAD`, `reason=source_proof_complete`, `status=hydrated`, and a
non-empty body. The source proof reference path is checked by the service itself.

## Result

**4/4 targets passed.** All four were published and loaded through the HTTP handler with
`source_proof_complete`. No synthetic card body was used as the cited source; the cited bytes
were the freshly fetched public C/C′ snapshots.

Command environment used for the replay:

```text
GUIDEFOLD_E2_SNAPSHOTS=/snapshots
GUIDEFOLD_PG_BIN=/pgtool/bin
LD_LIBRARY_PATH=/pgtool/lib
PYTHONPATH=/hostdist
go test -v -run TestE2SourceBackedSnapshotsThroughHTTP -count=1 .
```

The default test run skips this test when `GUIDEFOLD_E2_SNAPSHOTS` is unset because the public
snapshot corpus is intentionally external to the repository. A missing worker dependency is a
test failure when the opt-in variable is set; it is never converted into a pass.

## Follow-up: harmful mutations through HTTP — 2026-09-19

The original replay above covered only safe current proofs. This follow-up exercises the
source-backed mutation fixture through the actual Go publication worker and HTTP `USE 1.2`
handler. It uses the eight hash-pinned public records from the same two source families and
compares `proof_gated` with the service's `legacy` delivery policy. This is deterministic R/Q
evidence, not a human semantic evaluation or an estimate of production error rates.

The frozen manifest SHA-256 is
`47a145923f1fb256a2d6c03f9a117fbbde9fe99a6ec1d0d419bc9b0c7fa1f3ec`; the strengthened test
file SHA-256 is
`218703a3eff0e395909fe2653f912cb83852554b9c729d44510acd324193fc85`.
The replay fetched all eight records and matched every source hash before publishing. It then
made 30 `/v1/use` requests: eight safe cases and seven HTTP mutation cases, each run under both
policies. The eighth harmful mutation (incomplete dependency closure) was rejected separately
during import and did not reach the HTTP handler.

| Observation | `proof_gated` | `legacy` |
|---|---:|---:|
| Safe positive controls returned `LOAD` with a non-empty body | 8/8 | 8/8 |
| Five malformed/conflicting proof variants returned a body-free `ASK` / `LOAD` | 5/5 `ASK`, 0 bytes | 5/5 `LOAD`, non-empty |
| Stale revision | 409 `revision_mismatch`, 0 bytes | 409 `revision_mismatch`, 0 bytes |
| Deprecated input excluded from the active snapshot; subsequent USE by its ID | 404 `skill_not_found`, 0 bytes | 404 `skill_not_found`, 0 bytes |
| Incomplete closure | Import failed with `missing_dependency`; active head preserved | Same shared admission check |

The five gate-specific reasons were `proof_conflict`, `proof_scope_incomplete`,
`proof_body_hash_mismatch`, `proof_source_hash_mismatch` and `proof_source_unavailable`.
Across all eight assigned harmful mutations, the gated arm delivered **0 bodies**; the legacy
arm delivered bodies in **5 cases**. Stale revision was denied by a shared revision check; the
deprecated input was excluded from the active snapshot and its subsequent USE returned
`skill_not_found`. These are not incremental proof-gate benefits. This HTTP run did not execute
the separate flat concatenation control.

The test now asserts both arms' safe controls, the five exact gated reasons and legacy exposures,
the exact stale/deprecated HTTP errors, and the incomplete-closure rejection with an unchanged
active head. It also asserts the expected aggregate counts, so a missing or vacuous control cannot
pass unnoticed. Reproduction from the repository root:

```bash
python3 tools/pilot/fetch_source_disjoint_urct.py \
  --manifest docs/reports/bakeoff/SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json \
  --output /tmp/guidefold-e2-http/replay \
  --repo-cache /tmp/guidefold-e2-http/cache
cd services/search
GUIDEFOLD_E2_SNAPSHOTS=/tmp/guidefold-e2-http/replay \
  go test -v -run '^TestE2SourceBackedHarmfulMutationsThroughHTTP$' -count=1 .
```

This result does not provide independent human labels, agent task success, natural-hierarchy
transfer, or a user-benefit claim. The eight source-backed structural cases are a regression
matrix, not eight independent draws from production traffic.

## Limits

The original 2026-09-11 replay demonstrates that source-backed proof can survive publication and
HTTP delivery; the 2026-09-19 follow-up above adds structural harmful-mutation coverage. Neither
replay measures agent task success or establishes natural hierarchy transfer. Those still require
the hidden-verifier task bank and independent human annotation.
