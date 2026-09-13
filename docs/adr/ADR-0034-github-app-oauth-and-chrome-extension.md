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

## Amendment 2026-09-13: an installation belongs to the organisation that proved it

Recorded after the App was registered on the lab deployment (App ID `4928521`) and the owner
asked for the Codecov shape: anyone installs it, from their organisation in Guidefold, on every
repository, and pull requests get a report without further setup.

6. **The link between a GitHub App installation and a Guidefold organisation is proven, never
   inferred.** Until this amendment the webhook attached an installation to whichever Guidefold
   organisation had a slug equal to the GitHub login. That made the product depend on two
   unrelated names happening to match, and it was also a hole: an `installation_id` arriving in
   a request is attacker-controlled, so organisation B linking organisation A's installation
   would let B's Live Agent read A's private repositories with A's installation token. The
   match is removed with no fallback, because a fallback is the same hole.
7. **The owner starts the installation from Guidefold.** A start route issues a single-use
   signed state bound to the signed-in owner and organisation, reusing `gfm.auth_states`, and
   sends the browser to `https://github.com/apps/<slug>/installations/new`. With "Request user
   authorization (OAuth) during installation" enabled, GitHub returns to the callback with a
   `code` and the `installation_id`. The server exchanges the code with the App's client id and
   client secret and links the installation only if `GET /user/installations` for that user
   contains it. The code exchange lives in `internal/ghapp`, the only package allowed to talk to
   GitHub, which means the API now needs egress to GitHub as well as the worker.
8. **Repositories come from the installation, not from a manual import.** After a link, and on
   every later installation event, a worker job reconciles the organisation's repositories from
   the installation's paginated repository list, because the webhook payload is not complete for
   large "All repositories" installations. A repository that leaves the installation is detached
   and never deleted: its catalogue, proposals and publications cascade from it, and uninstalling
   an App is not a request to destroy an organisation's reviewed knowledge.
9. **The webhook enqueues a report for every pull request.** `opened`, `synchronize` and
   `reopened` enqueue exactly one `pr.report` for a linked installation; installation events
   enqueue nothing but the reconciliation. Before this amendment `pull_request` was ignored and
   installation events enqueued an `ascend.run` that could not use their payload.

Not settled by this amendment: matching a repository inside a linked installation still compares
`gfm.repos.git_host_url` strings rather than a stored GitHub repository id, and the contract names
that as the remaining workaround. Points 3 and 4 above, the repository picker and the Chrome
extension, are unchanged.

## Consequences

Automatic import requires GitHub App registration, callback configuration, repository permission review and new API/worker contract tests. The extension can be loaded locally now, but live GitHub repository discovery is not proven without those external credentials and a deployed callback.

## References

- [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §§5, 10, 11
- [API-CONTRACT](../API-CONTRACT.md) §§2, 4.2, 5.2
- [GitHub App user authorization](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [Chrome identity API](https://developer.chrome.com/docs/extensions/reference/api/identity)
