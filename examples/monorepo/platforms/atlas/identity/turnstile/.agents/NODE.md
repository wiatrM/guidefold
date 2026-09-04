# atlas.identity.turnstile

Turnstile is the Postgres-backed authorization service that fronts all atlas APIs. Every request
passes through its middleware chain: bearer-token validation (via the shared auth-sdk key set),
principal and role lookup in Postgres, and an RBAC decision evaluated in-process against the
atlas policy bundle owned by `atlas.identity`. Turnstile fails closed, caches decisions per bundle
version, and keeps all of its behaviour flags, including the transitional `legacyAuthMode`, in
`deploy/deployment.yaml`.

The service is owned by **turnstile-team**; the on-call rota is the **turnstile-oncall** sub-team,
which owns the runbook skill and is the only group allowed to apply the approved incident
mitigations (rollout undo, bundle re-pin, rolling restart) without a second reviewer.
