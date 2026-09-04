---
name: atlas-api-conventions
description: "[atlas] HTTP API design rules for every atlas service: URL layout, the shared error envelope, cursor pagination, versioning and the contract-first OpenAPI workflow. Use when adding or changing an endpoint, response schema, status code or error code in any service under platforms/atlas. Do not use for internal gRPC between atlas services or for deciding who may call an endpoint (see atlas/identity rbac-policies)."
license: Apache-2.0
compatibility: "Needs Go 1.22+ and the oapi-codegen and spectral CLIs from the repo toolchain; no cluster access required."
metadata:
  scope: atlas
  owner: atlas-platform
  references: "platforms/atlas/api/openapi.yaml"
  status: active
  since: "2026-09-04"
  digest: >-
    Every atlas HTTP API is contract-first: the OpenAPI document under platforms/atlas/api is the
    source of truth and handlers are generated from it. All endpoints share one error envelope,
    cursor-based pagination and a /v{n} path prefix so analyst clients treat geo, graph and identity
    services uniformly.
---
# Atlas API conventions

## When to use / when NOT to use
Use this skill when you:
- add, rename or remove a public HTTP endpoint in any service under `platforms/atlas/`
- change a request or response schema, status code or error code
- bump the API version prefix or deprecate an endpoint
- review a PR that touches `platforms/atlas/api/openapi.yaml` or a sub-service `openapi.yaml`

Do NOT use it for:
- internal gRPC or message-bus contracts between atlas services
- deciding *who* may call an endpoint; that is `rbac-policies` in `atlas.identity`
- database schema changes (follow `_root:postgres-production`)

## Steps
1. Edit the contract first. Shared components (`ErrorEnvelope`, `PageSize`, `PageToken`, the
   `Error` response) live in `platforms/atlas/api/openapi.yaml`; sub-services (geo, graph, turnstile)
   keep their own `openapi.yaml` next to `src/` and `$ref` the shared file. Never copy a component.
2. Run `make api-lint` (spectral with the atlas ruleset). Zero errors before writing any Go.
3. Regenerate server stubs with `make api-gen` (oapi-codegen, strict-server mode) and commit the
   generated `api/gen/*.go`; CI diffs them against a fresh generation.
4. Implement the handler in `src/http/` and register it only through the generated router so it
   passes the shared middleware chain (request-id → auth → RBAC → handler).
5. Add a contract test in `src/http/*_contract_test.go` that replays the example bodies from the spec.
6. For a breaking change add a `/v{n+1}` path, keep the old one for two minor releases, mark the old
   operation `deprecated: true` and set `x-sunset` to a release tag.

## Conventions specific to this scope
- Path layout: `/v1/{resource}` with plural kebab-case nouns, at most three levels
  (`/v1/layers/{layerId}/features`). Verbs belong in the HTTP method, never in the path.
- IDs are opaque strings prefixed by resource type (`lyr_`, `ent_`, `lnk_`, `usr_`). Never expose a
  Postgres serial id.
- Every non-2xx response is an `ErrorEnvelope`: `{ "error": { "code", "message", "requestId",
  "details"[] } }`. `code` is one of the shared enum values (`NOT_FOUND`, `FORBIDDEN`,
  `INVALID_ARGUMENT`, `RATE_LIMITED`, `INTERNAL`); free text goes only in `message`.
- List endpoints take `pageSize` (default 50, max 500) and `pageToken` and return `nextPageToken`
  (empty string when exhausted). Offset pagination is forbidden on tables above 10k rows.
- Timestamps are RFC 3339 UTC strings; geometries in JSON bodies are GeoJSON objects, never WKT.
- Idempotent writes accept an `Idempotency-Key` header scoped to the caller principal.
- Every response carries `X-Request-Id`; handlers propagate it into logs and downstream calls.
- Per-operation rate limits are declared with the `x-rate-limit` extension so the gateway can enforce them.

## Verify
- `make api-lint` passes with zero warnings on the atlas ruleset.
- `make api-gen && git diff --exit-code platforms/atlas/api/gen` shows generated code is committed.
- `go test ./platforms/atlas/... -run Contract` runs the replayed spec examples.
- `curl -s -o /dev/null -w '%{http_code}' localhost:8080/v1/does-not-exist` returns 404 with an
  `ErrorEnvelope` body and an `X-Request-Id` header.
- The PR description links the spec diff and states whether the change is additive or breaking.

## See also
- urn:skill:meridian:atlas.graph:link-analysis-api (builds on these conventions)
- urn:skill:meridian:atlas.identity:rbac-policies (authorization of the endpoints)
