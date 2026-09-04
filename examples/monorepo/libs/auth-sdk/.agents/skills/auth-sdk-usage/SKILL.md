---
name: auth-sdk-usage
description: "[shared/auth-sdk] How services consume the Meridian auth SDK (Go and Python) to authenticate callers and enforce RBAC decisions: middleware wiring, token verification, principal propagation, policy client usage and test doubles. Use when you add an authenticated endpoint, call another service with the caller's identity, or upgrade the auth-sdk dependency. Do not use for writing the RBAC policies themselves or for changing the identity service internals."
license: Apache-2.0
compatibility: "Needs the auth-sdk Go module or Python package, a policy endpoint or the bundled fake, and the platform CA bundle for token verification."
metadata:
  scope: shared.auth-sdk
  owner: identity-platform
  requires: "urn:skill:meridian:atlas.identity:rbac-policies"
  references: "libs/auth-sdk/README.md"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: team
  triggers: "auth-sdk middleware, PrincipalFrom context, authsdk.Authorize, token verification, authenticated endpoint, outbound delegated token"
  digest: >-
    auth-sdk is the only supported way for Meridian services to verify caller tokens, build a Principal and
    ask the RBAC policy service for a decision. Services wire the middleware once, pass the Principal through
    context, and never parse tokens or hard-code role checks themselves.
---

# Using the auth SDK

## When to use / when NOT to use
Use when you:
- add an HTTP or gRPC endpoint that must know who is calling;
- make an outbound call to another Meridian service on behalf of the current caller;
- write tests for authenticated code paths;
- upgrade `libs/auth-sdk` in a platform and hit API changes.

Do not use for authoring or editing Rego policies (`atlas.identity:rbac-policies`), for identity service or
turnstile internals, or for end-user login flows in the web UI.

## Steps
1. Add the dependency: Go `meridian.example/libs/auth-sdk`, Python `meridian-auth-sdk`, at the version pinned
   in your platform's lockfile.
2. Wire the middleware once at server construction. Go:
   `srv.Use(authsdk.Middleware(authsdk.Config{Audience: "atlas-geo", Issuer: cfg.Issuer}))`;
   Python: `app.add_middleware(AuthMiddleware, audience="forge-pipelines")`.
3. Read the caller from context, never from headers: `p := authsdk.PrincipalFrom(ctx)` or
   `principal = request.state.principal`. A missing principal is a 401 handled by the middleware.
4. Authorize with a policy check, never with role string comparisons:
   `authsdk.Authorize(ctx, p, authsdk.Action("dataset.read"), authsdk.Resource(datasetURN))`.
   Actions are dot-separated and listed in the policy registry.
5. Propagate identity on outbound calls with `authsdk.Outbound(ctx)` (Go) or `outbound_session(request)`
   (Python); it forwards a short-lived delegated token, not the original.
6. In tests use `authsdk/fake`: `fake.Allow("dataset.read")` and `fake.Principal("analyst-1", groups...)`.
   Never disable the middleware with a build tag or env var.
7. On upgrade read `libs/auth-sdk/CHANGELOG.md` and run the contract tests in `libs/auth-sdk/conformance`.

## Conventions specific to this scope
- Audience equals the service name derived from the node path (`atlas-geo`, `forge-pipelines`).
- The Principal is immutable and carries `Subject`, `Groups`, `Clearance` and `SessionID`; add fields in
  the SDK, not in service code.
- Decision caching lives inside the SDK (30s, keyed by principal, action, resource); do not add another.
- Deny is the default: a policy error, timeout or unknown action is a 403 with an audit event, never a pass.
- Every authorization decision emits an audit event through the SDK hook; services must not log decisions
  separately.
- Health and readiness endpoints are the only unauthenticated routes; register them via `authsdk.Public()`.
- Do not log tokens; use `authsdk.Redact(header)` when tracing requests.
- Go and Python APIs are kept in lockstep; a feature missing in one language is a bug, not a difference.

## Verify
```bash
go test ./libs/auth-sdk/... ./platforms/<platform>/...             # middleware and handlers
go run ./libs/auth-sdk/cmd/authlint ./platforms/<platform>/...     # flags header parsing and role string checks
pytest platforms/<platform>/tests -k auth                          # Python services
! grep -rn "X-Meridian-Subject" platforms/                         # no direct header use
```

## See also
- urn:skill:meridian:atlas.identity:rbac-policies
- urn:skill:meridian:shared:shared-lib-versioning
- urn:skill:meridian:security.audit:audit-logging
