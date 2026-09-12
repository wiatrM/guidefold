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

## Limits

This replay demonstrates that source-backed proof can survive publication and HTTP delivery.
It does not exercise all harmful mutations through the HTTP stack, measure agent task success,
or establish natural hierarchy transfer. Those remain covered by the separate deterministic
E2 matrix, hidden-verifier task bank and pending human annotation.
