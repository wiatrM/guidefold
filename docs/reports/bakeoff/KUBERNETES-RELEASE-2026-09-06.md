# Portable Kubernetes release validation — 2026-09-06

The Go service and Helm chart support immutable, independently deployed releases.
Local kind validation passed staging, promotion under traffic, rollback, replica
changes and rejection of an unpublished snapshot. A real CPU HPA brought four API
replicas online under load. This is deployment/controller validation, not a production
capacity, GPU-quality or HA admission.

## Evidence

[Raw evidence](validation/kubernetes-release-e2e.json.gz) records the source base,
runtime hashes, image identity and the following independent checks:

| Check | Local result |
|---|---|
| Real kind release E2E | 15 passed |
| Traffic during compatible release promotion | 150 SEARCH requests and subsequent USE/checksum checks passed |
| CPU HPA with Metrics Server 0.8.1 | Four available replicas observed, ScalingActive true |
| GPU and custom-HPA API-server dry run | 11 resources accepted; no GPU scheduled |
| Actual approved model files | Weights plus 7 tokenizer/config files verified |
| Corrupted model copies | Extra inference file and modified tokenizer both rejected |
| Release/CAS/Helm unit contracts | 16 pytest cases passed |
| Go runtime | `go test -race ./...` and `go vet ./...` passed |

The release fixture stages two synthetic repository revisions with the same Meridian
cards. It leaves `gf.heads` empty, serves both pinned previews, promotes the first,
changes the mutable head to the second, and verifies the first stays pinned. It then
promotes under HTTP traffic, rejects a stale compare-and-swap, rolls back, scales to
three replicas and performs a rolling restart. A third unpublished candidate cannot
promote. Two additional checks wait for that candidate's container to run and verify
Go itself returns `snapshot_not_published`, excluding a merely unfinished rollout.
Those checks were also exercised against the retained final local candidate.

The final fixture uses separate API/operator Secrets and real Postgres on a persistent
kind PVC. It does not simulate an external DB failover. The model check uses the existing
approved adapter read-only; tamper tests use separate copies/hardlinks without changing
the original. No GPU compute was used. A README and historical Guidefold preparation
notes are permitted alongside the hashed runtime files; extra inference files are not.

The HPA test uses six HTTP clients and a deliberately low **2% CPU target** to exercise
controller behavior. Its configured maximum is four pods; production defaults remain
70% CPU with 2–6 replicas. HTTP status counts and observed replica progression are in
the raw artifact. This threshold is not a calibrated production scaling policy, and
this is not a p95/throughput benchmark.

Kubernetes EndpointSlice/proxy propagation is asynchronous. The test waits for initial
Service creation and final routing convergence, while retaining all observations from
the promotion traffic window. It does not claim globally instantaneous cutover or a
zero-error deployment for clients requesting incompatible old repository revisions.

## Reproduction and CI

See the [runbook](../../../deploy/k8s/README.md) and [ADR-0030](../../adr/ADR-0030-immutable-service-releases-on-kubernetes.md).
`kubernetes-service` runs unit/Helm contracts, the real kind release test, GPU manifest
server dry run and the CPU HPA test, then uploads JSON evidence. Existing default
HTTP/CLI, graph and ledger CI gates remain unchanged.

```sh
python -m pytest tests/test_k8s_release.py
python tools/search_service/k8s_e2e.py
python tools/search_service/k8s_schema.py
python tools/search_service/k8s_hpa_e2e.py
```

The local tests use Kubernetes 1.36.1 in the isolated `guidefold-release-e2e` kind cluster,
Helm 3.20 and the existing Go toolchain. The chart declares Kubernetes >=1.33 because it
uses the native sleep lifecycle hook. Only the HPA test relaxes certificate verification
for the local kind kubelet; production database TLS is `verify-full`.

## Still separate from this result

- Physical GPU scheduling/inference and GPU/custom-metric HPA behavior.
- CNI NetworkPolicy enforcement, external TLS/gateway IAM and tenant RLS.
- Multi-node/zone failures, backup restoration and Postgres failover.
- Workload-calibrated scaling, retained artifact GC and a model-training scheduler.
- New model quality admission or dictionary/query-policy changes.

`production_ready` remains false. Default SEARCH is still canonical BM25F; neural
processing is shadow. No quality corpus, client CLI or 300/400 ms gate changed.
