---
name: legacy-session-auth
description: "[atlas/identity] DEPRECATED. Cookie-based session authorization evaluated inside each atlas service, superseded by turnstile's postgres-auth. Use only when reading old code paths guarded by legacyAuthMode while they are being removed. Do not use for new endpoints or for any change to authorization logic."
license: Apache-2.0
compatibility: "No tooling required; informational only."
metadata:
  scope: atlas.identity
  owner: identity-platform
  status: deprecated
  replaced_by: urn:skill:meridian:atlas.identity.turnstile:postgres-auth
  since: "2026-09-04"
  digest: >-
    Legacy session authorization kept an atlas-wide sessions table and evaluated roles separately in
    each service. It is superseded by turnstile's postgres-auth, which centralises token validation
    and RBAC evaluation; this skill remains only until the last legacyAuthMode deployment is retired.
---
# Legacy session auth (deprecated)

## When to use / when NOT to use
Read this only to understand code paths guarded by `legacyAuthMode` while they are being removed.
Do not follow it for any new or changed authorization logic; load
`urn:skill:meridian:atlas.identity.turnstile:postgres-auth` instead.

## Steps
There are no steps. The former procedure (per-service session lookup, role checks inside handlers)
is intentionally not reproduced here so that it cannot be applied by accident.

## Conventions specific to this scope
- Superseded because per-service role evaluation drifted between geo, graph and the API gateway and
  could not be audited from one place; turnstile now issues a single decision per request.
- The `atlas_sessions` table is read-only and will be dropped once `legacyAuthMode` is `false` in
  every turnstile deployment.

## Verify
- `grep -rn legacyAuthMode platforms/atlas/` lists only hits tracked in the turnstile removal issue.

## See also
- urn:skill:meridian:atlas.identity.turnstile:postgres-auth (replacement)
- urn:skill:meridian:atlas.identity:rbac-policies
