---
name: audit-logging
description: "[security/audit] How Meridian services emit tamper-evident audit events: the structured logger in security/audit/src, mandatory fields (actor, action, resource, classification, outcome), what must and must not be recorded, sinks, retention and verification. Use when you add an operation that reads or changes labelled data, wire a new service into the audit pipeline, or change event fields. Do not use for application debug logging or metrics."
license: Apache-2.0
compatibility: "Needs the security/audit Go module, the audit sink endpoint (or the file sink for tests) and the classification library."
metadata:
  scope: security.audit
  owner: audit-team
  requires: "urn:skill:meridian:security:classification-labels"
  references: "security/audit/src/logger.go"
  status: active
  since: "2026-09-04"
  kind: governance
  layer: team
  triggers: "audit event schema, tamper-evident logging, actor action resource outcome, hash chaining, audit sink retention, security/audit logger"
  digest: >-
    Every access to or change of labelled data in Meridian produces one structured audit event through the
    shared logger in security/audit, with a fixed schema, hash chaining and an append-only sink. Services never
    write audit records with their application logger or skip them on error paths.
---

# Audit logging

## When to use / when NOT to use
Use when you:
- add an endpoint, job or pipeline step that reads, writes, exports or deletes labelled data;
- onboard a new service to the audit sink or change its sink configuration;
- add or rename a field in the audit event schema;
- investigate a gap reported by the audit completeness check.

Do not use for debug or application logs (use the platform logger), for metrics and traces, or for
security incident handling procedures.

## Steps
1. Construct one logger per process from `security/audit/src`:
   `al, err := audit.NewLogger(audit.Config{Service: "atlas-graph", Sink: sink})`. Never per request.
2. Emit exactly one event per logical operation, after the outcome is known:
   `al.Emit(ctx, audit.Event{Action: "dataset.export", Resource: urn, Classification: lbl, Outcome: audit.Denied})`.
   Actor and session come from the auth SDK principal in `ctx`; do not pass them by hand.
3. Cover the error path: a denied, failed or timed-out operation is still an event with `Outcome` set.
   A missing event on failure is a CI-blocking bug.
4. Put context in `Details` as a small flat map (query id, row count, export format). Never include record
   content, tokens or free-text user input.
5. Set `Classification` to the label of the data touched, computed with `classification.Propagate` when
   several inputs are involved; the sink indexes on it.
6. For batch jobs emit a `batch.start` and `batch.end` pair sharing one `CorrelationID`, with per-item events
   only for writes.
7. Run the completeness check in CI: it compares actions registered in the policy registry with actions seen
   in the test sink and fails on any missing one.

## Conventions specific to this scope
- The schema is versioned (`schema_version: 3`) and append-only; fields are never removed, only deprecated.
- Mandatory fields: `time` (RFC 3339, UTC), `service`, `actor`, `session_id`, `action`, `resource`,
  `classification`, `outcome`, `correlation_id`, `prev_hash`, `hash`.
- Actions are `<noun>.<verb>` and must exist in the policy registry; the logger rejects unknown actions.
- Events are hash-chained per service: `prev_hash` is the previous event's `hash`, so gaps are detectable.
- The sink is append-only. Retention is seven years for RESTRICTED and above, two years otherwise; rotation
  is by day or by 512 MiB, whichever comes first.
- The file sink is for tests and air-gapped buffering only; production uses the streaming sink with
  at-least-once delivery and a local spool during outages.
- Events are written synchronously before the response is returned; a sink failure blocks the operation
  unless the service is marked `audit.BestEffort` with a security-org approved exception.
- Audit logs are themselves CONFIDENTIAL; reading the sink is a labelled operation and is audited.

## Verify
```bash
go test ./security/audit/...                                       # schema, chaining, sink behaviour
go run ./security/audit/cmd/auditcheck --sink file://./audit.log   # chain verifies, no gaps
go run ./security/audit/cmd/auditcheck --coverage ./platforms/...  # every registered action emits in tests
jq -r '.action' audit.log | sort | uniq -c                         # action names follow noun.verb
```

## See also
- urn:skill:meridian:security:classification-labels
- urn:skill:meridian:shared.auth-sdk:auth-sdk-usage
- urn:skill:meridian:_root:security-baseline
