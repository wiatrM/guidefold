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
pass unnoticed. This eight-record assignment replay used test file SHA-256
`218703a3eff0e395909fe2653f912cb83852554b9c729d44510acd324193fc85` (commit `084730a`).
Reproduction from the repository root:

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

## Follow-up: full source-by-mutation cross-product — 2026-09-19

The previous replay assigned one mutation to each source. This follow-up removes that coverage
gap: each of the eight pinned public records from both families is paired with all seven HTTP
mutation classes plus a safe positive control. The opt-in test creates 64 USE cases (8 sources ×
8 variants) and runs each under `proof_gated` and `legacy`, for **128 HTTP requests**. The active
snapshot contains 56 deliverable variants; deprecated inputs are excluded from it and checked by
subsequent `USE` requests. Incomplete closure is tested separately as eight isolated failed
imports so each source-specific case is verified without contaminating the active snapshot.

The manifest SHA-256 remains
`47a145923f1fb256a2d6c03f9a117fbbde9fe99a6ec1d0d419bc9b0c7fa1f3ec`; the cross-product test
file SHA-256 is
`b62a2e7e5719e3c2cf5bb8088d5987561069c380b72736ecaf9f2f3698895c7f`. All eight source hashes
matched before the service publication path ran. The initial cross-product test was repeated in
a separate process with the same active snapshot ID,
`repository:42220b91a97a08c0724c0beb8ad4bfadf3c74fbf5c73980501bfc2923a9156d6`; the final
fingerprinted version, which adds an explicit cardinality guard, passed again with that same ID.
These repeats check execution determinism; they do not increase the statistical sample size.

| Result | Count |
|---|---:|
| Safe controls: `LOAD` with body, both policies | 8/8 each |
| Proof-gated exact `ASK` for conflict, scope, body hash, source hash and missing source | 40/40; 0 body bytes |
| Legacy body exposures for those same five proof defects | 40/40 |
| Stale-revision denials | 8/8 per policy, 409 `revision_mismatch`, 0 body bytes |
| Deprecated inputs excluded from active snapshot | 8/8 per policy, subsequent `USE` 404 `skill_not_found`, 0 body bytes |
| Incomplete-closure imports | 8/8 rejected as `missing_dependency`; active head preserved in every case |
| Total HTTP requests / invariant violations | 128 / 0 |

The five proof defects are the only cases where this gate-versus-legacy HTTP comparison changes
delivery: proof-gated returns `ASK` with no body while legacy returns `LOAD`. Stale and deprecated
cases are stopped by shared lifecycle checks; closure is stopped before `USE` by the importer.
The separate flat-concatenation arm is still not exercised through HTTP.

The result is a finite source-backed mechanism/regression check, not a population estimate,
independent semantic judgement, task-success result, natural-hierarchy transfer claim or product
impact. Reproduction uses the command above with the cross-product test file at the hash recorded
here; its assertions pin the per-source denominators and every exact gate reason.

## Follow-up: exhaustive combinations of proof defects — 2026-09-19

The next replay held the eight source records and delivery policies fixed, but combined every
non-empty subset of five proof-level defects: conflict, uncovered scope, body-hash mismatch,
source-hash mismatch and missing source. This is all **31** states of the five-bit defect vector
per source (five single defects plus 26 multi-defect combinations), not a random sample. The test
also retained safe controls, isolated stale/deprecated lifecycle cases and separate incomplete-
closure imports.

Across the eight hash-verified records, the service exercised 248 proof-defect/source pairs under
each policy. All 248 proof-gated requests returned body-free `ASK`; all 248 corresponding legacy
requests returned `LOAD` with a non-empty body. Both policies loaded all eight safe positives.
Stale and deprecated controls were denied by the shared lifecycle checks, and each of eight
incomplete-closure publications failed as `missing_dependency` without moving the active head.
The full replay made 544 HTTP calls and recorded zero invariant violations. It was repeated in a
separate process with the same snapshot ID
`repository:52157e29704b53742d515584d27a45b09c4bea57da71a5c7df2282b825bc71c8` and identical
summary counts. Environment: Go 1.27.1, Linux/amd64 under WSL2 kernel 6.18.33.2, 16 reported
vCPUs; the Go suite used its isolated repository test-database harness. No model was called.

The test file SHA-256 is
`99b60332da6644a76270c055f241278b3d95b35c8e3230de593193ba7e17fd87`. Reproduction, after
fetching the frozen source records as above:

```bash
cd services/search
GUIDEFOLD_E2_SNAPSHOTS=/tmp/guidefold-e2-http/replay \
  go test -v -run '^TestE2SourceBackedHarmfulMutationsThroughHTTP$' -count=1 .
```

This exhausts combinations of the selected five protocol defects for this finite manifest; it
does not exhaust all possible malformed proofs or repository states. The mutations are
structural and protocol-invalid by construction. Consequently this is stronger mechanism
regression coverage, not independent evidence that the source content is semantically harmful,
not task success, not a production-rate estimate and not evidence of user benefit. The HTTP
comparison is proof-gated versus legacy; it still does not include flat concatenation.

## Limits

The original 2026-09-11 replay demonstrates that source-backed proof can survive publication and
HTTP delivery; the 2026-09-19 follow-ups add cross-source and combined-defect regression coverage.
Neither replay measures agent task success or establishes natural hierarchy transfer. Those still
require the hidden-verifier task bank and independent human annotation.
