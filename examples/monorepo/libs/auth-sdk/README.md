# auth-sdk

The Meridian authentication and authorization SDK for services, shipped as a Go module
(`meridian.example/libs/auth-sdk`, package `authsdk`) and a Python package (`meridian-auth-sdk`).
It verifies caller tokens against the platform issuer, builds an immutable `Principal`, asks the RBAC
policy service for decisions and emits an audit event for every decision.

## Go

```go
srv.Use(authsdk.Middleware(authsdk.Config{Audience: "atlas-geo", Issuer: cfg.Issuer}))

func handler(w http.ResponseWriter, r *http.Request) {
    p := authsdk.PrincipalFrom(r.Context())
    if err := authsdk.Authorize(r.Context(), p, authsdk.Action("dataset.read"), authsdk.Resource(urn)); err != nil {
        authsdk.WriteDenied(w, err) // 403, already audited
        return
    }
    client := authsdk.Outbound(r.Context()) // forwards a short-lived delegated token
}
```

## Python

```python
app.add_middleware(AuthMiddleware, audience="forge-pipelines")

@router.get("/datasets/{urn}")
async def read(request: Request, urn: str):
    principal = request.state.principal
    await authorize(request, principal, action="dataset.read", resource=urn)
    async with outbound_session(request) as session: ...
```

## Rules of the road

- Wire the middleware once; read the principal from context, never from headers.
- Authorize through policy actions (`noun.verb`), never by comparing role strings.
- Health and readiness routes are registered with `authsdk.Public()`; everything else is authenticated.
- Tests use `authsdk/fake` (`fake.Allow`, `fake.Principal`); the middleware is never disabled.
- See `CHANGELOG.md` and `conformance/` before upgrading across a major version.
