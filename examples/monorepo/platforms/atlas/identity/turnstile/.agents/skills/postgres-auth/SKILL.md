---
name: postgres-auth
description: "[atlas/identity/turnstile] Add or change authorization checks in the turnstile service: bearer-token validation, principal and role lookup in Postgres, RBAC evaluation through the OPA middleware, and the legacyAuthMode flag in deploy/deployment.yaml. Use when touching turnstile's auth middleware, its principal or role tables, or any auth-related field in deployment.yaml. Do not use for writing Rego policies (see atlas/identity rbac-policies) or for on-call incident response (see turnstile-oncall-runbook)."
license: Apache-2.0
compatibility: "Needs Go 1.22+, a local Postgres 16 with the turnstile schema, the opa CLI and kubectl read access to the turnstile namespace."
metadata:
  scope: atlas.identity.turnstile
  owner: turnstile-team
  requires: "urn:skill:meridian:atlas.identity:rbac-policies, urn:skill:meridian:_root:postgres-production"
  references: "platforms/atlas/identity/turnstile/deploy/deployment.yaml#legacyAuthMode, platforms/atlas/identity/turnstile/src/auth/middleware.go"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: team
  refines: "urn:skill:meridian:_root:postgres-production"
  replaces: "urn:skill:meridian:atlas.identity:legacy-session-auth"
  triggers: "turnstile auth middleware, bearer token validation, principal role lookup, legacyAuthMode flag, decision cache, principals table"
  digest: >-
    Turnstile authorizes every atlas API request by validating the bearer token, loading the principal
    and its roles from Postgres, and evaluating the atlas RBAC bundle in-process. All auth behaviour
    flags, including the transitional legacyAuthMode, live in deploy/deployment.yaml and nowhere else.
---
# Postgres-backed authorization in turnstile

## When to use / when NOT to use
Use this skill when you:
- change `platforms/atlas/identity/turnstile/src/auth/middleware.go` or anything it calls
- add or alter the `principals`, `principal_roles` or `decision_cache` tables
- flip or remove `legacyAuthMode` (or any `config.auth` key) in `deploy/deployment.yaml`
- put a new atlas service behind turnstile

Do NOT use it for:
- writing or testing Rego; that is `rbac-policies`, loaded with this skill
- pooling, migrations and failover mechanics; follow `_root:postgres-production`
- responding to an auth outage; use `turnstile-oncall-runbook`

## Steps
1. Read the chain in `middleware.go`: `Authenticate` (token → principal id) → `LoadPrincipal`
   (one Postgres query, cached 30 s) → `Authorize` (OPA eval with the pinned bundle) → handler. New
   checks are added as a step in this chain, never inside a handler.
2. Schema changes go through a migration in `turnstile/migrations/` with the `_root` naming scheme.
   `principals` and `principal_roles` are append-only with `valid_from`/`valid_to`; never `DELETE` a role row.
3. If the change needs a new policy input field, extend `auth.PolicyInput` in `middleware.go` and the
   `input` schema in `rbac-policies` in the same PR (both CODEOWNERS must approve).
4. Add any behaviour flag under `config.auth` in the ConfigMap in `deploy/deployment.yaml`, with a
   default equal to current production behaviour, and read it once at start-up via `auth.Config`.
5. To retire `legacyAuthMode`: set it to `false` per environment in the order dev → staging → prod,
   one release apart, and confirm `turnstile_auth_legacy_fallback_total` stays at zero before each step.
6. Add middleware tests with a fake `Verifier` and a Postgres test container covering allow, deny,
   expired token, unknown principal and a role outside its validity window.

## Conventions specific to this scope
- Tokens are verified with the key set from `libs/auth-sdk`; turnstile never parses JWTs itself.
- Principal lookup is exactly one query joining `principals` and `principal_roles` on the validity
  window. Any additional query on the request path needs a benchmark in the PR.
- The decision cache key is `sha256(principalId | action | resourceType | resourceId | bundleVersion |
  decisionCacheVersion)`; it is invalidated by version bumps, never by TTL alone.
- Failure mode is closed: a Postgres or OPA error yields `FORBIDDEN` with
  `details[0].reason = "auth_backend_unavailable"`, never a pass-through.
- `legacyAuthMode: true` makes `Authenticate` fall back to the `atlas_sessions` table when the bearer
  token is absent; every fallback increments `turnstile_auth_legacy_fallback_total`. The flag is read
  only through `auth.Config`.
- The auth query path uses `maxConns` from the `_root` Postgres defaults; do not raise it per deployment.
- Decisions are logged with `requestId`, `principalId`, `action`, `decision`, `bundleVersion` and
  `latencyMs`; never log the token or the resource payload.

## Verify
- `go test ./platforms/atlas/identity/turnstile/src/auth/...` passes with the Postgres test container.
- `go test -bench Authorize ./platforms/atlas/identity/turnstile/src/auth/` reports p50 under 2 ms
  with a warm cache and under 15 ms cold.
- `kubectl -n turnstile get configmap turnstile-config -o yaml | grep legacyAuthMode` matches the
  value in `deploy/deployment.yaml` for that environment.
- `curl -s -H 'Authorization: Bearer invalid' localhost:8081/v1/authz/check` returns 403 with the
  atlas error envelope.

## See also
- urn:skill:meridian:atlas.identity:rbac-policies (required)
- urn:skill:meridian:_root:postgres-production (required)
- urn:skill:meridian:atlas.identity.turnstile:turnstile-oncall-runbook
- urn:skill:meridian:shared.auth-sdk:auth-sdk-usage
