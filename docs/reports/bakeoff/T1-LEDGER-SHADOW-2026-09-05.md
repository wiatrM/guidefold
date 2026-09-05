# T1 ledger and sparse-preserving GPU shadow — 2026-09-05

The Go service now accepts the existing telemetry contract into Postgres and computes
hybrid comparisons after delivering the sparse response. No default ranker is changed;
API 1.1 and the client file remain fixed. This is service integration evidence, not
new model-quality or production admission evidence.

## Verified behavior

- **Same tests, two stores:** all 32 parametrized ledger/report cases pass on SQLite
  and real HTTP/Postgres. Go also passes 245 validation cases exported from the SQLite
  vocabulary/validator. Existing report formulas are reused unchanged.
- **Real client cycle:** 20 find + 5 load commands generate 210 events: 20 requested
  searches, 20 results, 160 injected cards, 5 requested loads and 5 completed loads.
  First flush accepts 210; replay of the identical spool accepts zero and returns
  210 duplicates. Postgres and SQLite reports match after excluding generated_at.
- **Durability:** an injected database error after the first insert rolls back the
  whole batch and returns 503 without accepted IDs. Replaying the same IDs after
  repair succeeds. Reports survive DB/API restart. Retention removes expired shadow
  rows as well as events; tenant isolation, partial rejects and concurrent replay pass.
- **GPU shadow:** 12 requests at c4 retain the entire stable sparse response. The only
  excluded fields across independent executions are request_id, search_id and stages_ms.
  A separate Go test verifies byte-exact delivery of one fixed response before enqueue,
  including disabled/full/cancelled queues. This does **not** claim identical bytes
  across independently generated HTTP UUIDs/timings.
- **Correlation:** shadow rows retain the observed snapshot, top-20 sparse/hybrid ranks,
  delivered selection and timings. The unchanged CLI emitter supplies search_results,
  skill_load_requested and skill_load_completed; all three join on tenant/search_id.
  USE body checksum matches. GPU outage leaves sparse response/readiness available;
  the failed shadow is recorded and the restarted worker produces comparisons again.
- **Default parity:** 1000/1000 HTTP 200 and zero mismatches at c4 on 10123
  documents: top-10 URNs/integer scores, selected order and immutable revisions match
  the unchanged CLI. This equivalence check uses no new neural treatment or quality gate.
- **Regression/operations:** 693 Python tests pass; Go race tests and vet pass; 39
  Compose smoke checks include 40 concurrent requests, atomic publication and restart.
  Base and GPU Compose configurations parse successfully. Systemd syntax passes using
  an explicit docker.service verification stub on this Docker Desktop/WSL host.

The first shadow run failed on its inherited inline 250 ms encoder timeout (recorded
compute time 265.325 ms). No sparse error occurred. Shadow now has a separate one-second
encode limit within a two-second compute deadline; the repeated integration passes.
The inline experiment remains at 250 ms. Historical GPU measurements and 300/400 ms
release budgets are not rewritten by this background-processing change.

## Remaining integration boundaries

The CLI flush command currently lacks a Bearer-token option. Its spool/ACK regression
therefore uses a **test-only** loopback credential-injection transport to the authenticated
Go endpoint. This proves transport semantics and report parity, not completion of E2.6.
The correlation test calls the real emitter as an adapter would; the find command itself
has not been changed to call the service. Client work remains with its owning session.

Shadow has four workers and a 32-job in-memory queue. Overflow, shutdown or a persistence
failure can lose a comparison. Logs identify queue/persistence losses; compare persisted
statuses and missing rows with event counts. It is not a durable queue or a new source of
usage events. It shares the T1 database pool, so the 12-request fixture test does not
establish sustained production capacity or performance isolation.

[The VM/systemd runbook](../../../deploy/t1/README.md) includes publication/rollback,
image selection, event export, daily retention and upgrade/backout instructions. A clean
VM install by a different operator in <30 minutes remains **unmeasured** because SSH
access to the nominated host was rejected. No VM 114 operation was attempted. The
systemd stub check is syntax-only; no unit was installed or started here. Backup archive
commands are documented; restoring a separate database and rebooting a VM are still
acceptance work, not inferred from Compose restart success.

Branch-protection check name: **compose-service** (real 1000-query HTTP/CLI parity).
Also retain native-service (formula/policy/validator tests); the new telemetry-service
job runs the actual Postgres ledger cycle. The repository owner controls required checks.

## Evidence and quality boundary

- [Ledger/replay/retention/restart](validation/t1-telemetry-postgres.json)
- [GPU shadow, stable response and event joins](validation/t1-shadow.json)
- [Final 1000-query default parity](validation/t1-router-parity.json)
- [Compose smoke](validation/t1-compose-smoke.json)
- [Systemd syntax scope](validation/t1-systemd.json)
- [Earlier frozen GPU latency and DEV results](GPU-SERVICE-2026-09-05.md)

The two neural DEV treatments are now entered in DENSE-PROGRAM section 7 for shared
cross-session accounting. All 1000 query IDs came from SKILLRET train, which trained
the encoder; exact overlap cannot be excluded. Dense hit@1 88.7% / completeness 47.0%
are in-distribution reproduction. Test-B remains +0.67 pp completeness with a CI crossing
zero; no new test-A/test-B evaluation or fusion-weight tuning was run. The new TEI
latency result is engineering evidence independent of that admission failure.

`production_ready: false`. Required remaining gates include authenticated client
integration, clean-VM/restore evidence and target-network/TLS/IAM/pilot evaluation.
