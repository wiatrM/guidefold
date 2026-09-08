# ADR-0034: Server-side GitHub App import with a thin Chrome extension

**Status:** Accepted · 2026-09-07, owner approval 2026-09-08. Deployment target: existing ArgoCD
cluster, temporary domain `https://guidefold.cloudfloo.io` (DNS/HTTPS to follow); GitHub App
registration, callback wiring and worker adapter are in progress against that target.
**Amends:** [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md).
**Governs:** GitHub repository discovery, automatic import entry point and the optional Chrome client.

## Context

The current U4 import screen asks for a local repository id and a CLI manifest. The owner requested automatic GitHub import through OAuth/GitHub App and a Chrome extension. This adds an external auth provider, a new runtime target and a new source adapter beyond the current pivot documents.

## Proposed decision

1. GitHub authorization is initiated by Guidefold and completed server-side. Client code never receives a GitHub client secret, access token or installation token.
2. The server exposes a sanitized list of repositories available to the signed-in user and starts an import from a selected repository/ref. The worker reads repository content through a least-privilege GitHub adapter and never executes imported code.
3. The UI replaces manual registration as the primary path with `Connect GitHub → choose repository → preview → import`. The existing CLI remains an explicit fallback until the server-side reader is accepted.
4. `extension/` is a Manifest V3 thin client. It opens the hosted flow and stores only a configurable Guidefold origin. OAuth state, cookies and provider credentials remain server-owned.
5. This ADR remains Proposed until the owner accepts the new target and a registered GitHub App supplies a real callback, permissions and deployment URL.

## Consequences

Automatic import requires GitHub App registration, callback configuration, repository permission review and new API/worker contract tests. The extension can be loaded locally now, but live GitHub repository discovery is not proven without those external credentials and a deployed callback.

## References

- [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §§5, 10, 11
- [API-CONTRACT](../API-CONTRACT.md) §§2, 4.2, 5.2
- [GitHub App user authorization](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [Chrome identity API](https://developer.chrome.com/docs/extensions/reference/api/identity)
