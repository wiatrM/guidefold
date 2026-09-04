---
name: rbac-policies
description: "[atlas/identity] Authoring and testing the atlas RBAC policy bundle in OPA Rego: the analyst/supervisor/admin role model, the fixed OPA input document, allow-rule structure, policy tests and bundle versioning. Use when adding a role, action or resource type to policies/rbac.rego, changing how a service builds the policy input, or reviewing a request for broader access. Do not use for turnstile service internals (see atlas/identity/turnstile postgres-auth) or for authentication."
license: Apache-2.0
compatibility: "Needs the opa CLI (0.60+) and read access to the identity policies directory; no cluster access required."
metadata:
  scope: atlas.identity
  owner: identity-platform
  references: "platforms/atlas/identity/policies/rbac.rego"
  status: active
  since: "2026-09-04"
  digest: >-
    Atlas authorization decisions come from one OPA Rego bundle with three linearly inherited roles
    (analyst, supervisor, admin) and a fixed input document built by the auth-sdk. Policies deny by
    default, every allow has a matching deny test, and bundle versions are pinned by the services.
---
# RBAC policies for atlas

## When to use / when NOT to use
Use this skill when you:
- add a role, action or resource type to `platforms/atlas/identity/policies/rbac.rego`
- change how an atlas service maps an HTTP request to the OPA `input` document
- write or update policy unit tests (`*_test.rego`)
- review a request to grant a role broader access

Do NOT use it for:
- turnstile internals (token validation, Postgres lookups, deployment flags); see
  `atlas.identity.turnstile:postgres-auth`
- authentication, i.e. establishing who the caller is; this scope only decides what a principal may do
- classification labels on data rows; that is the security org's `classification-labels`

## Steps
1. Describe the change as a row in `policies/MATRIX.md` (role × action × resource) before touching Rego.
2. Edit `rbac.rego`. Keep the structure: `default allow := false`, one `allow` rule per (role, action
   family), helper sets in `roles.rego`, no role names inlined outside `role_rank`.
3. Add a test in `rbac_test.rego` for the new allow AND for the closest deny (same action, next lower
   role). A PR that adds an allow without a matching deny test is rejected.
4. Run `opa fmt --write policies/` and `opa test -v policies/`.
5. Bump `bundle.version` in `policies/.manifest`; services pin a bundle version and refresh every 60 s.
6. If the change alters decisions for existing inputs, say so in the PR so turnstile-team can bump
   `decisionCacheVersion`.

## Conventions specific to this scope
- Roles are exactly `analyst`, `supervisor`, `admin`; a new role needs identity-platform approval and
  a MATRIX.md update. Inheritance is linear: admin ⊇ supervisor ⊇ analyst (`role_rank`).
- Actions are `<resource>:<verb>` strings with verbs from `read|write|export|admin`
  (`layer:read`, `graph:export`).
- The `input` document shape is fixed:
  `{ principal: {id, roles[], orgUnit, clearance[]}, action, resource: {type, id, orgUnit, label}, context: {requestId} }`.
  Services build it through `libs/auth-sdk`, never by hand.
- Deny by default; there is no `deny` rule. Anything not explicitly allowed is refused.
- Policies read no external data at decision time except the bundled `data.roles` document; no
  `http.send` in Rego.
- `export` actions additionally require `resource.label` to be within the principal's clearance set,
  evaluated by the shared `label_ok` helper.
- Every decision is logged by the calling service with the bundle version and the `requestId`.

## Verify
- `opa test -v platforms/atlas/identity/policies/` passes with coverage ≥ 90 % (`opa test --coverage`).
- `opa eval -d policies/ -i testdata/analyst_read.json 'data.atlas.rbac.allow'` prints `true`.
- `opa eval -d policies/ -i testdata/analyst_export.json 'data.atlas.rbac.allow'` prints `false`.
- `opa fmt --diff policies/` is empty.
- `make -C platforms/atlas/identity matrix-check` confirms `MATRIX.md` has a row for every allow rule.

## See also
- urn:skill:meridian:atlas.identity.turnstile:postgres-auth
- urn:skill:meridian:shared.auth-sdk:auth-sdk-usage
