# guidefold.cloudfloo.io — deployment runbook

## Material 3D and proof-carrying positioning — 2026-09-09 (current)

Helm revision **12**, namespace `guidefold`, context `cloudfloo-context`.
UI image `ghcr.io/wiatrm/guidefold-ui@sha256:2b29c9484b9c102afa5d23c4762c1b61c76ea118db1333ab6b1ea86372f8989e`.
Tag `redesign-20260909-material3d-12`, built from `gf-waitlist-20260908`.
Owner selected material 3D after rejecting the card animation; this release adds
folding layers, camera motion, orange paths and an explicitly illustrative
proof-gated LOAD/ASK control, plus the new product thesis and four research links.
The scope-authority lattice is labelled research-only. No backend proof feature
or task-success claim is introduced by this UI deployment.

Read-only Helm comparison against the root chart confirmed only the UI image
changed. Upgrade with reused values completed; rollout **2 updated, 2 ready,
2 available / 2**. Public entry `/assets/index-CDUI313h.js`: HTTP 200;
root and both evidence JSON files: 200. Browser verified WebGL, formed layers,
ASK without a body, LOAD with a body, explicit review/publication and four
research links; zero overflow and page errors. `/api/v1/me` remains **503**.

QA: 29 landing browser tests + 8 unit tests PASS; final rebuild followed by
7/7 pyramid tests, contracts and Docker build PASS. Three.js is lazy (~146kB
gzip); its >500kB raw chunk warning is retained. No new Lighthouse, field CWV,
full application-suite or real-agent task-success result. No Git commit/push.
Rollback point: revision **11**, previous image recorded below.
Evidence: combined worktree `reports/build-notes.md`, `ui/qa/spectrum-deployment.json`.

## Pyramid deployment state — 2026-09-09 (previous)

Helm revision **11**, namespace `guidefold`, context `cloudfloo-context`.
UI image `ghcr.io/wiatrm/guidefold-ui@sha256:539ae7ef7b666e054cf3424ee0eb3fdbc3c1e5c8bd8ad638096058df777f1aae`.
Cluster check: **2/2 ready**. Revision 10 was cancelled and marked failed;
revision 11 completed through the Windows Helm client. Only the UI image changed.
The owner rejected the explanation design. The subsequent local motion rewrite
was also rejected; its pushed image `redesign-20260909-motion-12`
(`sha256:50f764c748e0986f7e4cc699e9d7630d6f1d04fa56ab337d5c713024d1214b14`)
is **NOT deployed and must not be treated as design-approved**.
Do not infer a deployment from that rejected image tag. The owner subsequently
selected the material 3D direction deployed above with a different image.
Combined-worktree evidence: `reports/build-notes.md`.

## Waitlist controls deployment — 2026-09-09 (previous)

Helm revision **9**, namespace `guidefold`; UI image
`ghcr.io/wiatrm/guidefold-ui@sha256:b3c757d068e563144156aaccc8db82727f9a10be916905eadfe1c25dc95e5268`.
Tag `redesign-20260909-controls-09`, built from `gf-waitlist-20260908`; no commit/push.
Scope: prevent waitlist CTA compression, align email/button at 52px, use shadcn
buttonVariants for header/hero/hosted links, wire Spectrum MorphButton loading.

Read-only preflight against the root checkout chart confirmed only the UI image changed.
Upgrade with reused values succeeded; rollout completed, **2/2 ready and available**.
Production browser verified entry `/assets/index-BRRisNfw.js`, three shadcn CTA links,
185px-wide submit, 52px height, 25px content inset on both sides and zero overflow.
No browser page errors. Root, entry bundle and `/licenses/shadcn-ui.txt`: HTTP 200.
API `/api/v1/me` remains **503**; real subscription delivery is not established.

Fresh scoped QA: **22 browser + 8 unit tests PASS**, build and contracts PASS.
Four layout sizes: 1440/1024/768/390px. Includes axe, equal control heights, state
transitions and error/retry with a stub API. Lighthouse was not rerun for this patch.
Rollback: revision **8**, previous image `sha256:75160f39b8dea2b33d8e67a7a0371e85d39b30b88a3c777f741ff08485f8ab2e`.
Source, license and screenshots: combined worktree `docs/ui/spectrum-migration.md`.

## Material landing deployment — 2026-09-09 (previous)

Helm release `guidefold`, namespace `guidefold`, revision **8**. UI image:
`ghcr.io/wiatrm/guidefold-ui@sha256:75160f39b8dea2b33d8e67a7a0371e85d39b30b88a3c777f741ff08485f8ab2e`.
Built from `gf-waitlist-20260908`, tag `redesign-20260909-material-08`; no Git commit/push.
Scope: film-inspired orange/ivory material landing, two generated assets, pausable
WebGL hero, interactive instruction reader with Spectrum CodeBlock, aligned mini-demos
and custom footer. Logo and application navigation backgrounds are preserved.

Read-only release preflight against `/home/mike/projects/guidefold/deploy/k8s/chart`
confirmed only the UI container image changes. Upgrade used `--reuse-values --wait=false`.
Rollout succeeded: **2/2 ready, 2 available**. No backend, database or secret changed.
Public `/`, `/import`, `/assets/index-V-sgaQN3.js`, Spectrum license and both
new WebP assets return HTTP 200. Both deployed asset SHA256 hashes match local files.
The root document references the new entry bundle. API `/api/v1/me` remains **503**;
production login/import/waitlist delivery has not been established.

Fresh scoped QA: **17 browser tests, 8 unit tests PASS**; build and UI contracts PASS.
Desktop Lighthouse: performance **99**, accessibility **100**, LCP **944 ms**,
CLS **0.014**, TBT **0 ms**. Slow-phone experiments did not establish passing
mobile Core Web Vitals; field INP was not measured.
Evidence: combined worktree `docs/ui/spectrum-migration.md`,
`ui/qa/spectrum-deployment.json` and `ui/qa/landing-generated-assets.json`.
Rollback point: revision **7**, image ending
`a81293cf1aeed9c2abf4731dbf6b7d20bb37e9636d127b72ebe6e462b34b402d`.

## Spectrum UI deployment — 2026-09-09 (previous)

Helm release `guidefold`, namespace `guidefold`, revision **7**. UI image:
`ghcr.io/wiatrm/guidefold-ui@sha256:a81293cf1aeed9c2abf4731dbf6b7d20bb37e9636d127b72ebe6e462b34b402d`.
Built from `gf-waitlist-20260908`, tag `redesign-20260909-spectrum-07`; no Git commit/push.
Implemented scope: Spectrum metric cards, bar/pie charts, Tree Nav, Morph Button,
BeamCard/BeamSearch mini-demos; existing Guidefold brand and video modal preserved.
This is not a claim that every product renderer has been rewritten.

Preflight against the combined worktree's chart blocked an unrelated ConfigMap change.
The chart at `/home/mike/projects/guidefold/deploy/k8s/chart` was separately compared
with the live Helm manifest using live values: only `Deployment/guidefold-ui` image changed.
Upgrade used that verified chart, `--reuse-values --wait=false`; rollout succeeded,
**2/2 UI replicas ready**. No API/worker/database/secret/configuration change was applied.

Verified public `/`, `/import`, `/assets/index-Dab4VwiB.js` and
`/licenses/spectrum-ui.txt`: HTTP 200. The production API `/api/v1/me` remains **503**.
Local QA uses the stub API; it does not establish production login/import/waitlist delivery.
Rollback point: revision **6**, UI image ending `497166b2c0afcba4cfea2d298391fc312e40e31ad0ceb8606d4f489eb9029abe`.
Migration evidence is in the combined worktree's `docs/ui/spectrum-migration.md`.

## Previous deployment — 2026-09-09

The fold-film landing, video Dialog, source Sheet and animated feature examples are deployed as Helm release
`guidefold`, revision **6**, namespace `guidefold`. UI image:
`ghcr.io/wiatrm/guidefold-ui@sha256:497166b2c0afcba4cfea2d298391fc312e40e31ad0ceb8606d4f489eb9029abe`.
The Docker build used the combined `gf-waitlist-20260908` working tree, tag
`redesign-20260909-fold-film-06`; no Git commit or push was made. The kubeconfig
location supplied by the owner is recorded in [AGENTS.md](../../../../AGENTS.md).

Before upgrade, rendering this checkout's chart with the live release values
matched the live Helm manifest exactly. Adding the new `ui.image` changed only
the UI container image. Upgrade used `--reuse-values --wait=false` because the
API was already unavailable; UI readiness was checked separately using
`kubectl -n guidefold rollout status deployment/guidefold-ui --timeout=50s`.
Result: **2/2 UI replicas ready**, public `/`, `/import`, CSS/JS assets and
`/licenses/shadcn-space.txt` return HTTP 200. The served entry bundle is
`/assets/index-C1H_1Gpz.js`. No API, worker, database, ingress or secret changed.

The API still returns **503** and logs `workos_requires_api_key_and_client_id`.
This release does not fix authentication or activate hosted waitlist delivery.
Do not report login/import/signup as production-tested. The previous UI image
is `ghcr.io/wiatrm/guidefold-ui@sha256:4dee933b3d842c114dea531459a319b2f0386be103ad791d7232faf4874bab76`;
revision 5 is the rollback point for this UI-only change. ArgoCD Application is
still not installed. The sequence below is historical, not current readiness.

## Initial deployment history

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
     and set `WORKOS_API_KEY_FILE=/run/workos/api-key` (mounted from that secret) —
     `values.yaml` in this directory does not yet wire this mount in; it's the one
     piece still to add once the secret exists, since the chart's `api.yaml`
     currently has no WorkOS volume mount at all (only `credentialsSecret` and
     `operatorCredentialsSecret` are mounted today).

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

   Result: `guidefold-portal` and `guidefold-worker` pods Running; `guidefold`
   (api) pods correctly CrashLoopBackOff with `workos_requires_api_key_and_client_id`
   — expected, not a bug: `auth: workos` with no WorkOS secret wired yet (see
   step 3's still-open WorkOS mount). Harmless to leave crash-looping until
   WorkOS is wired — **except** that step 10 below routes `/api` and `/v1` to
   it, so once the UI is live, every API call it makes will 503 until this is
   fixed. That's expected too, not a new failure — see step 10.

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
    - **Still true after this step**: the API is still `auth: workos` with no
      WorkOS secret (step 3), so the UI's app shell loads but every
      `/api/v1/...` call — including the one on load that checks whether
      you're signed in — gets a 503 from an all-unready backend. Real
      login/import through the UI needs step 3's WorkOS piece finished first.

## What this does not cover

- TLS / DNS: explicitly the owner's own next step, not blocked on anything here.
- **The GitHub App backend itself** (OAuth callback, repository adapter, import
  trigger) — confirmed absent from the code in this pass, not merely unverified.
  ADR-0034 is an accepted design, not a built feature; this deploy stands up the
  infrastructure it will eventually run on, not the feature.
- The WorkOS secret mount (`WORKOS_API_KEY_FILE`) — the chart doesn't wire this
  volume in yet (see step 3); add it alongside building the GitHub App backend.
- Raising `instances`/replica counts for real production load — this sizing is
  deliberately pilot-scale.
