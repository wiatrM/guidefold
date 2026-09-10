# guidefold.cloudfloo.io — deployment runbook

## Presentation and production authentication — 2026-09-10

Owner requested deployment of the latest main plus the approved presentation.
The presentation is served by the UI image at `/prezentacja/`, with local fonts,
PlantUML diagrams and infographics. Runtime assets have a SHA256 manifest.

WorkOS production credentials are stored only in Secret `guidefold-workos`;
production client ID is `client_01M1XXZE942EDFDYZBW55X6ME1`, with public URL
`https://guidefold.cloudfloo.io`. Never commit the API key. The callback URL is
`https://guidefold.cloudfloo.io/api/v1/auth/callback`.

Immutable ConfigMaps now use a content-derived name, shared by API, worker and
operator references. Deleting and recreating the same immutable name left the
node supplying stale environment values; changing the name also rolls consumers.
The API build context now includes the required contract 1.2 schema.

Production verification: ArgoCD `Synced` / `Healthy`; API 2/2, UI 2/2,
worker 1/1, portal 1/1. Root, presentation, docs and auth providers return HTTP
200; unauthenticated `/api/v1/me` returns 401. Both API healthchecks pass.
All 36 presentation files match the approved local assets by SHA256.

Registered the production callback with WorkOS (`201`). GoogleOAuth and
GitHubOAuth authorization still return WorkOS `404`; the hosted AuthKit screen
currently offers only SSO. Full sign-in is not verified and requires configuring
those production OAuth providers. Do not report full login as working yet.

Ingress access explicitly allows the `ingress` namespace's nginx controller.
API-only public TCP/443 egress permits the WorkOS code exchange; private and
metadata networks are excluded (standard Kubernetes policies cannot filter FQDNs).

Deployed immutable images:
- UI: `sha256:4359c65505d766caa75068cb91424162a2149846bc00f504876a4a0bb5ae035c`
- API: `sha256:c18c9b58d10f4b79c24e7e09b6d038c7aa35769768c15c99ef0769d0136cd2cc`
- Worker: `sha256:5f290555275cb5480ae96f1130ba166a8f9bb1701af025b034521a1dedbd12c4`
Chart revision: `7b0958cfe8511ddbe86eaae6d62200749ade774c`.

Checks: 321 UI tests, UI contracts and build; Go vet/tests; 28 chart release tests.
The deployment worktree keeps image digests, rendered manifests, migration result
and rollback inputs under `reports/` (not committed). A database dump was saved
outside the repository before the migration.

## ArgoCD adoption and the why/how/value landing — 2026-09-09 (current)

The release is now managed by ArgoCD. `Application/guidefold` in namespace
`argocd` under its own `AppProject`, automated sync with prune and selfHeal,
destination namespace `guidefold`. First sync reported **Synced**; health is
**Degraded**, which is the pre-existing API crash described below and not a
result of this change.

UI image `ghcr.io/wiatrm/guidefold-ui@sha256:6cb8100637e6150bde1893d49dd5ced9b70781f062b2fc25b6446757025db627`,
built by `publish-images.yml` from merge commit `b195845`. Rollback image:
`sha256:2b29c9484b9c102afa5d23c4762c1b61c76ea118db1333ab6b1ea86372f8989e`
(Helm revision 12, material 3D).

The landing page now answers why, how and what a team gets, in that order. The
3D pyramid is replaced by a flat scope ladder with readable organisation and
skill names. A ten-second camera flight generated with Seedance 2.0 sits behind
the page with its playhead tied to scroll. Poster-first: reduced motion,
Save-Data, a decoder error, a missing file or no `canplay` inside eight seconds
all leave the still in place with no layout shift.

The Application pins `targetRevision` to the tag `deploy-cloudfloo-chart-r12`,
not `main`. Rendering the chart on main fails with
`workos.clientID is required when auth=workos`, and the live ConfigMap is
`immutable: true`, so a render that adds `WORKOS_CLIENT_ID` and
`GUIDEFOLD_PUBLIC_URL` could not be applied in place either. Rendering the
tagged chart with the release's own values differs from the live manifest by a
single line, the UI image; that diff was checked before applying.

Three things are needed to move the Application back to `main`, and the first
two also fix the API:

1. A real `workos.clientID` and `publicURL` in the values.
2. The `guidefold-workos` secret created in the namespace; it does not exist.
3. The immutable `ConfigMap/guidefold` deleted so it can be recreated.

The API deployment has been in CrashLoopBackOff for 34 hours, failing on
`workos_requires_api_key_and_client_id`. It predates this deploy and is
unrelated to the UI.

Verified after sync: UI rollout 2/2, both pods on the new digest, public root
200 serving entry `/assets/index-D_C6sqQn.js`, `hero-flight.mp4` and
`hero-poster.webp` 200. Gates before merge: typecheck, build, contracts,
321 unit tests across 34 files, 7 landing browser tests, axe with zero
violations and zero horizontal overflow at 390 and 1440. Playhead against
scroll measured in Chromium at 1440 and WebKit at 390. Repository CI on the
pull request was bypassed at the owner's explicit instruction.


Target: the existing ArgoCD-managed cluster at `192.168.8.128` (kubeconfig supplied
by the owner out of band), temporary domain `guidefold.cloudfloo.io`. Per
[ADR-0034](../../../docs/adr/ADR-0034-github-app-oauth-and-chrome-extension.md),
now Accepted.

Nothing in this directory has been applied to the cluster. Everything below is a
manual sequence for whoever runs it — none of it was executed by the assistant
session that authored these files, beyond read-only reconnaissance (`kubectl get`).
The cluster already runs other live apps (`quackback`, `umami`, `indep-ai`,
`cloudfloo-v2`, `unslopify-alpha`) that this sequence must not touch: everything
here is scoped to a new `guidefold` namespace and its own ArgoCD AppProject.

## What's already true on the cluster (verified read-only)

- CloudNativePG operator installed (`cnpg-system`) — `postgres-cluster.yaml` uses it.
- In-cluster registry exists but isn't the build path: the self-hosted GitHub Actions
  runner (`github-runners` namespace) has **zero runners registered to
  `wiatrM/guidefold`** — it's scoped to the owner's other private repos. Images are
  built by `.github/workflows/publish-images.yml` on GitHub-hosted runners and pushed
  to `ghcr.io` instead.
- `ingress-nginx` has a real external IP, `192.168.8.128`, matching where the owner's
  forthcoming DNS record for `guidefold.cloudfloo.io` will point.
- No cert-manager installed — this deployment is HTTP-only until the owner adds TLS
  themselves (their explicit plan; `ingress.tlsSecret` stays empty until then).
- Plain PostgreSQL is sufficient — no ParadeDB/`pg_search`/`vector` extensions needed.
  The chart defaults to `GUIDEFOLD_LEXICAL_ENGINE=router` and `gpu.enabled=false`,
  both of which run on stock Postgres (`services/search/main.go`, the "Plain
  PostgreSQL profile" check); the migration's `CREATE EXTENSION` calls for
  `pg_search`/`vector` already tolerate being unavailable
  (`internal/schema/sql.go`).

## Sequence

1. **Build and push images.** Merge this branch to `main` (touches
   `services/search/**`, which triggers `.github/workflows/publish-images.yml`
   automatically) or run it manually via `workflow_dispatch`. Copy the two digests
   from the run's step summary.

2. **Create the namespace and Postgres app-role secret**, then the Postgres cluster
   (done — 2026-09-08, this exact sequence, against the real cluster):
   ```
   kubectl create namespace guidefold
   kubectl create secret generic guidefold-postgres-app -n guidefold \
     --from-literal=username=guidefold_bootstrap \
     --from-literal=password="$(openssl rand -base64 24)"
   kubectl apply -f postgres-cluster.yaml
   kubectl wait --for=condition=Ready cluster/guidefold-postgres -n guidefold --timeout=5m
   ```
   This also auto-creates `guidefold-postgres-ca` (cluster CA, has the `ca.crt` key
   the chart mounts for `sslMode: verify-full`) — nothing more to do for TLS.

   Note on what actually happened: CNPG uses `bootstrap.initdb.owner` (`guidefold_api`)
   as the real role name regardless of the secret's own `username` field — `\du` on
   the live cluster shows `guidefold_api` exists, not `guidefold_bootstrap`. The
   secret's username field is vestigial here; only its password mattered. Left as-is
   rather than renamed, to not re-churn an already-created role.

   `enableSuperuserAccess: true` is also on by default in this file now — the
   chart's migrate Job connects as `database.adminUser` (`postgres` by default) to
   run DDL, and CNPG does not expose a superuser secret unless this is set.

3. **Create the app-facing secrets** the chart requires
   (`deploy/k8s/README.md` § "Create the existing Secrets") — done 2026-09-08:
   ```
   kubectl create secret generic guidefold-credentials -n guidefold \
     --from-literal=app-password="$(openssl rand -base64 32)" \
     --from-literal=api-token="$(openssl rand -base64 32)"
   kubectl create secret generic guidefold-operator-credentials -n guidefold \
     --from-literal=admin-password="$(kubectl get secret guidefold-postgres-superuser -n guidefold -o jsonpath='{.data.password}' | base64 -d)" \
     --from-literal=app-password="$(openssl rand -base64 32)"
   ```
   (the operator's `admin-password` is the CNPG-managed `postgres` superuser secret,
   not the app-owner secret from step 2 — different roles, different privileges)
   **WorkOS** (`auth: workos`) needs its own secret with the real API key — this is
   the one value the assistant session will not handle as pasted chat text. Either:
   - hand a local file path containing the key to the session so it can be read
     straight into a `kubectl create secret` command without ever being echoed, or
   - run this yourself:
     ```
     kubectl create secret generic guidefold-workos -n guidefold \
       --from-literal=api-key="<the real WorkOS API key>"
     ```
     The chart mounts this secret at `/run/workos/api-key` and sets
     `WORKOS_API_KEY_FILE` automatically. Set `workos.clientID` in this values
     file (or in the ArgoCD Application) before syncing; keep the API key only
     in the Kubernetes Secret.

4. **Pinned image digests** (done — 2026-09-08, `publish-images.yml` on
   `fix/ghcr-lowercase-owner`, dispatched directly rather than waiting for a
   merge): both `values.yaml` and `argocd-application.yaml`'s inlined
   `helm.values` now carry the real digests. Two real bugs hit and fixed along
   the way, both in `publish-images.yml`/`.dockerignore`, not the chart:
   `github.repository_owner` is `wiatrM` (registry names must be lowercase —
   hardcoded `ghcr.io/wiatrm/...`), and `.dockerignore`'s allowlist never
   included `portal/` (same `**`-then-allowlist pattern as the api/worker
   paths, just missing an entry).

5. **Migrated the schema** (done): `helm install guidefold-migrate ... -f
   values.migrate.yaml`, waited for `job/guidefold-migrate` to complete,
   `helm uninstall`. `gfm`/`gf` schemas and tables exist and were verified
   directly (`\dt gfm.*`) — real tables, not just "job succeeded."

   **Gotcha hit and fixed**: `guidefold-credentials`' `app-password` and
   `guidefold-operator-credentials`' `app-password` were generated as two
   independent random values (steps 2/3 above). They must be the **same**
   value — migrate sets `guidefold_api`'s real Postgres password from the
   *operator* secret's `app-password`; the running API/worker pods then
   authenticate using the *app* secret's `app-password`. Mismatched values
   here produce a clean, correctly-labelled crash
   (`password authentication failed for user "guidefold_api"`), not a hang —
   but nothing catches the mismatch at deploy time, so get the value from
   `guidefold-operator-credentials` and reuse it in `guidefold-credentials`,
   don't generate a second random one:
   ```
   kubectl create secret generic guidefold-credentials -n guidefold \
     --from-literal=app-password="$(kubectl get secret guidefold-operator-credentials -n guidefold -o jsonpath='{.data.app-password}' | base64 -d)" \
     --from-literal=api-token="$(openssl rand -base64 32)"
   ```

6. **Deployed directly with `helm install`, not yet via ArgoCD** (done): to
   get live faster than a full PR-merge-then-sync cycle, `helm install
   guidefold ../../chart -n guidefold -f values.yaml` was run directly
   against the cluster. `portal.yaml` has no `workload` guard (unlike
   api.yaml/worker.yaml), so it renders on *every* release including
   `migrate` — pass `--set portal.enabled=false` for one-off Job releases or
   you'll get a stray duplicate portal Deployment.

   Result: `guidefold-portal` and `guidefold-worker` pods should be Running. The
   API becomes Ready only after `workos.clientID` and the `guidefold-workos`
   Secret from step 3 are present; otherwise Helm fails validation before an
   unusable serving release is applied.

7. **Apply the ArgoCD Application** (not yet done — the live release above was
   installed directly with `helm install`, bypassing GitOps for speed):
   ```
   kubectl apply -f argocd-application.yaml -n argocd
   kubectl get application guidefold -n argocd -w
   ```
   ArgoCD adopts the existing resources on first sync (same chart, same
   values, same rendered manifests) rather than recreating them — but this
   hasn't been tried against this specific Helm-installed release yet;
   verify `kubectl get application guidefold -n argocd` shows `Synced`, not
   `OutOfSync`, before trusting it for ongoing management.

8. **Verified** (done, via the cluster's ingress IP + Host header — DNS for
   `guidefold.cloudfloo.io` isn't pointed at `192.168.8.128` yet). At the time
   this step ran, the portal was still mounted at `/` (before step 10's
   routing redesign moved it to `/docs` for the UI):
   ```
   curl -H "Host: guidefold.cloudfloo.io" http://192.168.8.128/
   ```
   Real 200, real MkDocs-rendered content, CSS/JS assets load, a second page
   resolved. Re-verify against the current paths (`/docs`, `/`) after step 10.

9. **GitHub App registration is blocked on real backend work that doesn't exist
   yet — checked this pass, not assumed.** `internal/identity` has a `"github"`
   entry in its SSO provider list (`identity.go:64`), but that's the WorkOS
   "sign in with GitHub" login option from P01, not the ADR-0034 flow. There is no
   GitHub-App-specific OAuth callback route, no least-privilege repository-read
   adapter, and no `Connect GitHub → choose repository → preview → import` handler
   anywhere in `internal/importer` or `internal/identity` — ADR-0034 point 2/3
   describe a design, not shipped code. Registering a GitHub App against this
   domain today would get you a callback URL with nothing real behind it.
   Deploying (steps 1–8) makes the existing CLI-driven import/review/publish API
   live on a real domain; it does not implement the GitHub App surface itself.
   That's the next real chunk of engineering work, separate from this deploy.

10. **Hosted UI added and the domain re-routed (2026-09-08).** The gap flagged
    after step 8/9 — no React app was ever built or deployed, so "login" had
    literally nowhere to run — is closed:
    - `ui/Dockerfile` builds the real React app (`pnpm build`) behind an
      unprivileged nginx with SPA fallback (`ui/nginx-spa.conf`:
      `try_files $uri /index.html`). Same-origin by design
      (`ui/src/api/client.ts`), so it does not proxy `/api`/`/v1` itself.
    - Routing changed from "portal owns `/`" to three path rules on the one
      shared host: `/` → UI (`ui.yaml`), `/docs` → portal (`portal.yaml`,
      **rebuilt to serve from `/usr/share/nginx/html/docs/`, not its root** —
      the portal's own directory-redirect only comes out correct if nginx's
      own view of the path already includes `/docs`; stripping the prefix at
      the ingress instead would need the ingress to rewrite the backend's
      *response* Location header too, which plain nginx-ingress
      rewrite-target does not do), `/api` + `/v1` → api (`ingress.yaml`).
      nginx-ingress merges same-host rules from separate Ingress objects by
      path specificity, so the three files' declaration order doesn't matter.
    - `ingress.enabled` is now `true` (was `false`): the UI's own `/api`/`/v1`
      calls are same-origin, so without this every request the app makes
      404s against the UI's own static-file catch-all instead of reaching
      the api Service.
    - Build/deploy is the same `helm install`-then-`upgrade` pattern as
      before, with a new `ui` job in `publish-images.yml`; `ui.image` follows
      the same "TODO: pin from the run's Summary" placeholder pattern.
    - The UI's app shell renders the sign-in route even while the API is
      temporarily unavailable, but real login/import requires the serving API
      to pass WorkOS validation and reach Ready.

## What this does not cover

- TLS / DNS: explicitly the owner's own next step, not blocked on anything here.
- **The GitHub App backend itself** (OAuth callback, repository adapter, import
  trigger) — confirmed absent from the code in this pass, not merely unverified.
  ADR-0034 is an accepted design, not a built feature; this deploy stands up the
  infrastructure it will eventually run on, not the feature.
- The WorkOS provider project setup and secret creation remain operator steps;
  the chart wiring and validation are now included here.
- Raising `instances`/replica counts for real production load — this sizing is
  deliberately pilot-scale.
