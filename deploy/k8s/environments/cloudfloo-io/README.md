# guidefold.cloudfloo.io — deployment runbook

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

4. **Fill in the two pinned image digests** from step 1 into `values.yaml`
   (`image` and `worker.image`) and into `argocd-application.yaml`'s inlined
   `helm.values` block — both files must match; `values.yaml` is the one to
   `helm template`-test against before touching the inlined copy.

5. **Migrate the schema** (one-off Job, separate Helm install per the immutable-
   release design):
   ```
   helm install guidefold-migrate ../../chart -n guidefold \
     -f values.yaml -f values.migrate.yaml
   kubectl wait --for=condition=complete job/guidefold-migrate -n guidefold --timeout=5m
   helm uninstall guidefold-migrate -n guidefold
   ```

6. **Verify locally before ArgoCD ever sees it:**
   ```
   helm template guidefold ../../chart -f values.yaml | kubectl apply --dry-run=server -f -
   ```

7. **Apply the ArgoCD Application** (only after 1–6):
   ```
   kubectl apply -f argocd-application.yaml -n argocd
   kubectl get application guidefold -n argocd -w
   ```

8. **Verify:**
   ```
   kubectl get pods -n guidefold
   curl -s http://guidefold.cloudfloo.io/health/ready   # once DNS points at 192.168.8.128
   ```
   Expect `{"ready": true, "retrieval": "not_configured", ...}` — that's correct,
   not a failure: nothing has been imported/published yet. The management API
   (`/api/v1/...`) is live at this point.

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
