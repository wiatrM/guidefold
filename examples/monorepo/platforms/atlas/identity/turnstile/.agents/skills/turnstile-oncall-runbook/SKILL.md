---
name: turnstile-oncall-runbook
description: "[atlas/identity/turnstile] On-call runbook for the turnstile authorization service: what each TurnstileAuth* alert means, first-response checks, the three approved mitigations (rollout undo, bundle re-pin, rolling restart), reconciling deploy/deployment.yaml afterwards, and escalation. Use when paged for a turnstile alert, when atlas APIs return 403s at scale, or when rolling back a turnstile release. Do not use for planned auth changes or policy edits."
license: Apache-2.0
compatibility: "Needs kubectl access to the turnstile namespace, read access to the metrics dashboard and membership of the turnstile-oncall pager rota."
metadata:
  scope: atlas.identity.turnstile
  owner: turnstile-oncall
  requires: "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
  references: "platforms/atlas/identity/turnstile/deploy/deployment.yaml"
  status: active
  since: "2026-09-04"
  digest: >-
    Turnstile on-call handles authorization outages for all atlas APIs; the service fails closed, so
    incidents surface as 403 spikes rather than bypasses. The runbook maps each alert to a triage
    path, limits on-call to three approved mitigations, and defines when to escalate to
    turnstile-team or identity-platform.
---
# Turnstile on-call runbook

## When to use / when NOT to use
Use this skill when:
- you are paged by any `TurnstileAuth*` alert
- atlas services report an elevated 403 or 5xx rate that correlates with `turnstile_authz_errors_total`
- a turnstile release must be rolled back outside a planned window

Do NOT use it for:
- planned changes to auth logic, schema or flags; those follow `postgres-auth` with a normal PR
- editing Rego policies during an incident (re-pin the previous bundle instead, step 4)
- incidents in the token issuer; page identity-platform directly

## Steps
1. Acknowledge the page and post the alert name plus a sample `requestId` in the incident channel.
2. Triage by alert:
   - `TurnstileAuthErrorRateHigh`: Postgres or OPA backend errors, go to step 3.
   - `TurnstileAuthLatencyHigh`: usually pool exhaustion or a cold decision cache, go to step 5.
   - `TurnstileBundleStale`: bundle refresh failing for over 5 min, go to step 4.
   - `TurnstileLegacyFallbackNonZero`: `legacyAuthMode` is on where it should be off; compare the
     ConfigMap in `deploy/deployment.yaml` for that environment and go to step 6.
3. Backend errors: `kubectl -n turnstile logs deploy/turnstile --since=10m | grep auth_backend_unavailable`.
   If the reason is Postgres, follow the `_root` Postgres incident checks; if OPA, go to step 4.
4. Bundle problems: re-pin the last known-good version with
   `kubectl -n turnstile set env deploy/turnstile AUTH_BUNDLE_VERSION=<previous>` and confirm
   `turnstile_bundle_version` changes on the dashboard. Open an issue for identity-platform.
5. Latency: compare `turnstile_pg_pool_in_use` with `maxConns`. If saturated, restart pods one at a
   time (`kubectl -n turnstile rollout restart deploy/turnstile`); never raise `maxConns` mid-incident.
6. Rollback: `kubectl -n turnstile rollout undo deploy/turnstile`, then revert the change in
   `deploy/deployment.yaml` through a PR so the manifest matches the cluster again.
7. Escalate to turnstile-team after 30 min without mitigation, or immediately if a mitigation would
   change `legacyAuthMode` or any other `config.auth` value.
8. Write the incident note within 24 h using `docs/incidents/TEMPLATE.md`.

## Conventions specific to this scope
- Turnstile fails closed. An outage is a 403 storm, not a security bypass; do not "open" auth to
  restore traffic. There is no flag for that and none may be added.
- Only three mitigations are approved for on-call use without a second reviewer: rollout undo,
  bundle re-pin, rolling pod restart.
- `deploy/deployment.yaml` is the single source of truth for flags; a manual `kubectl set env` is a
  temporary mitigation and must be reconciled by a PR before the incident is closed.
- Never run ad-hoc SQL against the principal tables during an incident; read-only checks go through
  the `turnstile_ro` role.
- Alert thresholds live in `deploy/alerts.yaml` next to `deployment.yaml`; tuning one is a PR, not
  a dashboard edit.
- The rota is turnstile-oncall (a turnstile-team sub-team); handover notes go in the incident channel
  at the end of each shift.

## Verify
- After mitigation, the `turnstile_authz_errors_total` rate is back to baseline for 15 min and the
  atlas gateway 403 rate matches the previous day.
- `kubectl -n turnstile get configmap turnstile-config -o yaml` matches the ConfigMap in
  `deploy/deployment.yaml`, or a reconciling PR is open.
- The incident note links the alert, the mitigation used and the follow-up issue.

## See also
- urn:skill:meridian:atlas.identity.turnstile:postgres-auth (required)
- urn:skill:meridian:_root:postgres-production
- urn:skill:meridian:atlas.identity:rbac-policies
