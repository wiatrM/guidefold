# Portable Kubernetes deployment

This chart deploys the Go SEARCH/USE service and optional TEI GPU **shadow**. It does
not install a cloud-specific gateway, database operator or tenant IAM. GCP can later
supply these through cluster configuration without changing the artifact lifecycle.
Kubernetes >=1.33, Helm 3, a NetworkPolicy-capable CNI and existing Secrets are required.
[ADR-0030](../../docs/adr/ADR-0030-immutable-service-releases-on-kubernetes.md) records
the release design. Tests and measured limits are in the [validation report](../../docs/reports/bakeoff/KUBERNETES-RELEASE-2026-09-06.md).

## Release identity and rebuilding

A release binds the exact tenant/repository, snapshot, policy/CLI SHA, BM25 index SHA,
Go image and artifact image. GPU shadow also binds the encoder manifest and model
image. Use immutable `@sha256:...` image references. `k8s_release.py manifest` hashes
that tuple into a release name; one Helm installation owns one release. Keep old and
new installations side by side. The stable Service is owned separately.

| Input change | Build before deployment |
|---|---|
| Skill text, graph, scope map, weights or lexical statistics | Export a new committed snapshot and complete BM25 index; regenerate document vectors for its exact skill revisions if GPU shadow is enabled. |
| Query tokenization, synonyms/dictionaries or routing policy | Update the shared CLI/Go policy, rebuild the snapshot/index and runtime image, pass parity. No mutable dictionary is hot-loaded into serving pods. |
| Model weights, tokenizer, query prompt, document format, normalization or pooling | Produce a new approved encoder manifest, re-encode the full corpus offline, build the model image, and publish the exact matching vector set. |
| Only replica/resource settings | Change operational Helm values for the same artifact identity; do not edit its pinned ConfigMap. |

The existing encoder manifest hashes weights and tokenizer/configuration files, and
records the pinned model revision, TEI base image and embedding settings. Model images
are checked during build and by a GPU initContainer before TEI starts. Models and
indexes are never rewritten or trained in the online pods. Use a separate indexing
worker/GPU allocation so bulk encoding cannot exhaust the serving queue.

The current encoder validator still accepts only the registered SKILLRET model/profile.
A retrained checkpoint needs its approved profile and quality evaluation; this deployment
does not automatically admit it. Re-publishing an identical snapshot/vector bundle is
idempotent; different vectors for an already populated `(snapshot, encoder)` fail rather
than overwrite it. Register a new encoding generation/profile or snapshot with explicit
provenance when rebuilding changes those outputs. Do not add a nonce to evade evaluation.

## Cluster prerequisites

Provision Postgres with the extensions required by the pinned service (`pg_search`
and `vector`), TLS with a verified hostname/CA, backup/PITR and tested restore/failover.
The Compose reference pins ParadeDB 0.25.6/PG17; ordinary managed PostgreSQL does not
necessarily permit its extensions. The Kubernetes chart intentionally uses an external
DB; the single-node database in the kind test is not a production database template.

Allocate a namespace and deployment cell per tenant/repository, preferably a separate
DB/credentials where tenant isolation is required. Namespace separation does not create
DB RLS. Tenant identity comes from trusted configuration, never a request header.
The current migrator creates `guidefold_api`; it does not provision arbitrary role names.

Create existing Secrets through the cluster's secret-management process:

- `guidefold-credentials`: `app-password`, `api-token` (mounted by API only).
- `guidefold-operator-credentials`: `admin-password`, `app-password` (publication/migration only).
- `guidefold-postgres-ca`: `ca.crt` for `PGSSLMODE=verify-full`.
- Optional registry pull and ingress TLS Secrets.

Do not put secret values in Helm values, release manifests, images or Git. API pods
receive no operator credential or Kubernetes API token. Database password/token rotation
requires coordinating the service restart and clients; the current process reads its
bearer credential at startup, not continuously from the mounted file.

Copy [cluster.example.yaml](cluster.example.yaml) outside the repo and replace its DB
host, allowed network peers, client selectors and resource budgets. The chart rejects
unpinned production images, disabled production DB TLS, missing DB network peers,
unknown values and replica settings exceeding the allocated connection budget.
`developmentMode` is only for an isolated local fixture. Verify CNI enforcement; creating
a NetworkPolicy on a CNI that ignores it provides no isolation ([Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)).

## Build and stage a candidate

Work from a reviewed service commit. Build/push the Go image using
`services/search/Dockerfile`, then record its registry digest as `API_IMAGE`. Export
the committed consumer repo with `tools/search_service/dev.py prepare --repo-root ...
--repo-id ... --revision <commit>`; it produces the canonical BM25 export too.

Create a build context containing **only** `snapshot.json` (and `embeddings.json` for
GPU); do not use the Compose secrets directory as the context. Build/push with
[Artifact.Dockerfile](Artifact.Dockerfile) or [ArtifactGPU.Dockerfile](ArtifactGPU.Dockerfile):

```sh
docker build -f deploy/k8s/Artifact.Dockerfile \
  --build-arg GUIDEFOLD_IMAGE="$API_IMAGE" -t "$ARTIFACT_TAG" "$BUNDLE_DIR"
# Push to your artifact registry and set ARTIFACT_IMAGE to its immutable digest.
```

For GPU, use `gpu.py prepare` to produce the verified adapter, then build
[Model.Dockerfile](Model.Dockerfile) with that adapter as context and `ENCODER_ID` from
its canonical manifest. This hashes files without running inference. Pin the resulting
model image digest and run document encoding offline with the same approved encoder.
The GPU job stages cards first, then complete matching vectors. Both stages leave
`gf.heads` unchanged; a failed second stage cannot put incomplete data in serving.

```sh
python tools/search_service/k8s_release.py manifest \
  --snapshot "$BUNDLE_DIR/snapshot.json" --tenant "$TENANT" \
  --image "$API_IMAGE" --artifact-image "$ARTIFACT_IMAGE" \
  --output release.json
# For shadow also pass --encoder-id "$ENCODER_ID" --model-image "$MODEL_IMAGE".
RELEASE=$(python -c 'import json; print(json.load(open("release.json"))["release"])')

for MODE in migrate publish serve; do
  python tools/search_service/k8s_release.py values --manifest release.json \
    --base "$CLUSTER_VALUES" --workload "$MODE" --output "$MODE.yaml"
done
```

All following calls name the kubeconfig, context and namespace explicitly. Run migrations
once under deployment coordination; they use the existing database advisory lock. Run
migration before publication and publication before serving. Jobs have a deadline and
no automatic retries; inspect a failure and retry a new named Job only after diagnosis.

```sh
helm --kubeconfig "$KUBECONFIG" --kube-context "$CONTEXT" -n "$NS" \
  install "$RELEASE-migrate" deploy/k8s/chart -f migrate.yaml
kubectl --kubeconfig "$KUBECONFIG" --context "$CONTEXT" -n "$NS" \
  wait --for=condition=complete "job/$RELEASE-migrate" --timeout=30m

helm --kubeconfig "$KUBECONFIG" --kube-context "$CONTEXT" -n "$NS" \
  install "$RELEASE-publish" deploy/k8s/chart -f publish.yaml
kubectl --kubeconfig "$KUBECONFIG" --context "$CONTEXT" -n "$NS" \
  wait --for=condition=complete "job/$RELEASE-publish" --timeout=30m

helm --kubeconfig "$KUBECONFIG" --kube-context "$CONTEXT" -n "$NS" \
  install "$RELEASE" deploy/k8s/chart -f serve.yaml --wait --timeout=30m
```

The preview address is `http://$RELEASE.$NS.svc:8080`. Every API process is pinned to
its manifest's snapshot. A missing pin fails readiness; a later global head change
cannot redirect this deployment to another snapshot. Sparse readiness checks the DB
and policy/index; GPU shadow failure leaves sparse SEARCH available.

## Verify, promote and roll back

Run SEARCH→USE through the candidate, check graph/CLI parity and required quality gates,
then inspect the promotion plan. `--expect-current none` is used only for first creation;
otherwise supply the actual currently active release name.

```sh
python tools/search_service/k8s_release.py promote --manifest release.json \
  --kubeconfig "$KUBECONFIG" --context "$CONTEXT" --namespace "$NS" \
  --expect-current "$OLD_RELEASE"
# Same command with --apply performs the reviewed change.
```

Preflight checks the image, immutable configuration and every available API replica's
live snapshot, policy, BM25 index and encoder identity. GPU preflight verifies worker
metadata and the complete published vector set. Changing the stable `guidefold` Service
uses a compare-and-swap on resourceVersion and prior selector. A stale operator gets an
error instead of overwriting a newer promotion. Artifact identity and preflight are not
a substitute for retrieval-quality admission or a signed approval system.

After application, verify actual traffic through `guidefold.$NS.svc:8080`. EndpointSlice
and proxy propagation take time; existing connections may still reach old pods. Keep both
releases serving through this period. A selector write is atomic, but not an instantaneous
cluster-wide drain. Initial Service creation can briefly have no routed endpoints.

Rollback uses the retained old `release.json` and `--expect-current "$NEW_RELEASE"`, with
the same preflight and `--apply`. Do not rebuild or edit old artifacts during an incident.
Keep at least the previous release ready until the validation/rollback window expires.
Later scale it down or uninstall its Helm installation; never delete the stable Service
as part of candidate cleanup. The operator tool refuses to adopt an unrelated Service.

Exact workspace/skill revision checks remain. A client still using an older repo commit
may receive 409 after promotion; retain its versioned release endpoint or use the existing
local fallback. The API does not silently change the requested revision. Multi-revision
routing and external tenant IAM belong in the later gateway/control plane.

## Scaling and observation

Default API HPA is 2–6 replicas, CPU target 70%, at most two new pods/minute and a
five-minute downscale window. Each pod has eight shared SEARCH/USE slots, two telemetry
slots and **eight total DB connections** (background work shares that pool). Configuration
checks reserve `(2 * (maxReplicas + 1) * 8) + operatorReserve` DB connections for overlapping
releases and rolling surge: defaults require 128. This is an allocated DB budget, not a
query-throughput benchmark. Include all tenant cells sharing the DB in the operator's sum.

CPU alone can miss I/O or pool saturation. `/metrics` exposes bounded-cardinality request,
429, latency-histogram and admitted-request metrics; no queries, user IDs or skill IDs.
Optional ServiceMonitor requires Prometheus Operator. Permit the collector's namespace/pod
selector in NetworkPolicy; do not expose `/metrics` through the external gateway.
A Prometheus Adapter rule can expose the search pool as a per-pod HPA metric:

```yaml
seriesQuery: 'guidefold_http_inflight{namespace!="",pod!="",pool="search_use"}'
resources:
  overrides:
    namespace: {resource: namespace}
    pod: {resource: pod}
name: {matches: guidefold_http_inflight, as: guidefold_admitted_requests}
metricsQuery: 'sum(<<.Series>>{<<.LabelMatchers>>,pool="search_use"}) by (<<.GroupBy>>)'
```

After verifying this rule in your adapter, set `autoscaling.inflightMetric` to
`guidefold_admitted_requests`; the default target is four per pod. CPU HPA requires
Metrics Server; custom metrics require the adapter ([Kubernetes HPA documentation](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)). Alert on 429 rate, p95, DB pool waits,
shadow coverage and GPU queue time. HPA cannot provision nodes or solve DB exhaustion.

Developer count alone does not size the service. For illustration, 5,000 developers at
one SEARCH/minute average 83 requests/s; at 100 ms **mean** service time that is about
8.3 requests in flight before bursts, retries, USE and telemetry. These are assumptions,
not measured capacity. Calibrate min/max replicas and DB allocation with the actual
catalog, harness cadence and concurrent-load SLO tests.

GPU Deployment/HPA is separate. GPU HPA is off until a measured per-pod queue metric is
exposed by the adapter; set its name/target explicitly. Default batch size remains the
registered repeatability profile. Provision NVIDIA device support and enough spare GPUs
for a new release plus surge; HPA does not create GPUs. No scale-to-zero is configured. With only one GPU, continuous GPU blue/green service is
not possible: disable the old GPU autoscaler and scale its TEI deployment to zero before
warming the candidate. Primary sparse traffic can continue, but record the shadow gap.
Rollback must warm the retained old encoder again before its preflight can pass.

## Failure handling and operations

- Catalog/policy/model mismatch: candidate fails publication or preflight; leave old traffic.
- DB outage: API fails readiness/requests explicitly; no stale in-memory serving fallback.
- GPU outage: primary sparse remains available; shadow records failures/coverage gaps.
- Rollout: startup/liveness are separate from readiness, with a five-second preStop delay
  and 30-second pod grace period around Go's graceful HTTP shutdown.
- Bad concurrent promotion: re-read active release; do not bypass the compare-and-swap.
- Incompatible DB migration: use the reviewed maintenance/restore plan; application rollback
  cannot reverse arbitrary DDL. Back up and test restoration before such an upgrade.

NetworkPolicy, PDB and replica count do not establish HA. Verify distribution over real
nodes/zones, voluntary and involuntary failure behavior, certified DB TLS, backup/PITR,
restore, retention and gateway authentication. [traffic.example.yaml](traffic.example.yaml)
is an optional generic Ingress for `/v1` only; choose an installed controller and TLS Secret.
Provider-specific GCP ingress/IAM/storage configuration can be added later.

Retain the ledger/shadow in Postgres across API releases and preserve tenant+event_id
idempotency. Run the existing administrative telemetry retention under the DB owner.
Automatic snapshot/model GC is not implemented: before deleting artifacts, inventory all
retained deployments, rollback references and in-flight indexing jobs. Never use cascading
DB deletion or `down -v` as a release rollback.

## Validation

```sh
python -m pytest tests/test_k8s_release.py
(cd services/search && go test -race ./... && go vet ./...)
python tools/search_service/k8s_e2e.py
python tools/search_service/k8s_hpa_e2e.py
```

These tools create/use only the named `guidefold-release-e2e` kind cluster and owned
namespace. The HPA test installs pinned Metrics Server there and relaxes only that kind
kubelet's self-signed certificate check. It uses an intentionally low 2% CPU target to
test controller mechanics, not the production target. GPU scheduling/inference, custom
metrics and CNI enforcement need separate target-cluster validation. The kind test records
those boundaries explicitly. Existing quality corpora and 300/400 ms gates are unchanged.