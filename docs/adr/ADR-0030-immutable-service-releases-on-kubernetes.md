# ADR-0030: Immutable service releases on portable Kubernetes

Status: Proposed

## Context

A global `gf.heads` pointer is adequate for a single compatible API process. Updating
that head while rolling out a new policy image or encoder can give old pods an index
built for new code. A warmed model Service must also not mix different encoders behind
one name. Kubernetes restarts and scaling make these mismatches observable across pods.
The owner requested portable Kubernetes now, with GCP integration considered later.

## Decision

Package one immutable release as a content-derived identity binding tenant/repository,
snapshot digest, CLI/policy SHA, BM25 index SHA, Go image digest and artifact image
digest. GPU shadow additionally binds the encoder manifest ID and model image digest.
The encoder manifest already includes weights, tokenizer/config hashes, query/document
format, pooling, normalization, dimensions and TEI image. A new release uses a new Helm
installation and retains the previous one for rollback.

`GUIDEFOLD_SNAPSHOT_ID` pins every API pod to one tenant/repository-qualified immutable
snapshot. It still checks Postgres on requests; it is not offline fallback. Absence of
the variable retains existing Compose head-following behavior. Publisher jobs reject a
bundle inconsistent with their configured pin. Migration and catalog/vector publication
are separate, bounded Jobs with admin credentials. Publication sets
`GUIDEFOLD_PUBLISH_ACTIVATE=false`; it does not move the Compose head.

Build artifacts offline from reviewed Git/model inputs. Do not train, update dictionaries,
re-encode the corpus or download mutable model weights in serving pods. Publish cards and
BM25 postings, then complete vectors for the exact snapshot/encoder. The same approved
encoder must produce document and query vectors. Bake verified model files into a pinned
TEI image; check file hashes at build and in an initContainer. Its Deployment/Service is
release-specific. GPU remains shadow; model availability does not govern sparse readiness.

An operator preflight checks every available candidate API replica against the release
manifest, including database index and encoder compatibility. Promotion changes only a
separately owned stable Service selector, using tests of resourceVersion and prior selector.
A stale promotion fails. Rollback performs the same preflight and compare-and-swap against
a retained release. Helm uninstall/upgrade of a candidate cannot delete the stable Service.
Kubernetes data-plane propagation and existing connections are asynchronous: selector
mutation is atomic, global instantaneous cutover is not promised.

The chart uses external Postgres, existing Secrets, ClusterIP Services, non-root/read-only
pods, separate operator credentials, NetworkPolicies, probes, PDB and autoscaling/v2.
API scaling can use CPU and a per-pod admission gauge through a metrics adapter. GPU HPA
is opt-in and requires a measured queue metric, not CPU. The configuration checks that
DB connection allocation covers two overlapping releases plus surge and operator reserve.
No cloud-specific ingress, IAM, storage class or registry is required by the chart.

## Consequences

- Old and new artifacts coexist; promotion never overwrites a model/index in place.
  Failed publication or preflight leaves the prior serving release available.
- Artifact identity is integrity/versioning, not proof of retrieval quality or a cryptographic
  approval signature. Existing quality gates and review remain required. The current neural
  validator still accepts only the registered SKILLRET profile; a newly trained model needs
  its own approved profile and evaluation, not just a new image tag.
- A changed query tokenizer/synonym policy requires matching CLI and Go behavior, a rebuilt
  index, a new policy image and renewed parity. There is no independent mutable synonym
  dictionary endpoint in the current runtime. Compatible catalog updates can retain the model;
  changed encoder/tokenizer/prompt/format requires fresh document vectors.
- Each installation serves one trusted tenant/repository and release. Namespace separation
  is not DB RLS or a production tenant IAM layer. Prefer separate databases/credentials for
  tenant cells. The migration creates the existing `guidefold_api` role; it does not provision
  arbitrary roles or authenticate tenants from headers.
- Exact revision checks remain. A client still on an old repository revision may receive 409
  from the newly active release; keep a versioned endpoint or use the established local
  fallback. API 1.1 does not silently route arbitrary client revisions to retained releases.
- API HPA cannot fix exhausted Postgres, GPU queue capacity or missing cluster nodes. Two
  release generations need spare CPU/GPU/database capacity. PDB covers voluntary eviction,
  not database failover or involuntary node loss.
- Retain old snapshots/images/model artifacts until no deployment or in-flight job references
  them. Automatic artifact garbage collection and model training orchestration are not added.
- Local kind tests validate rollout mechanics. Production admission separately requires
  enforced CNI policies, certified Postgres TLS, backups/restore/failover, gateway TLS/IAM,
  multi-node failure drills and workload-calibrated SLOs.

Implementation and operations: [Kubernetes runbook](../../deploy/k8s/README.md).
