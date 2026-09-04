---
name: helm-conventions
description: "[relay/k8s] Authoring and releasing Helm charts for Meridian services under infra/relay/k8s/charts: chart layout, values schema, digest-pinned images, and release versioning. Use when creating or changing a chart, its values.yaml or values.schema.json, or when publishing a chart version. Do not use for Terraform-managed cloud resources or for building offline bundles."
license: Apache-2.0
compatibility: "Needs helm >= 3.14, kubeconform, helm-unittest, and helm-docs; a kind cluster (`make kind-up`) is enough for local installs."
metadata:
  scope: relay.k8s
  owner: k8s-team
  requires: "urn:skill:meridian:_root:release-process"
  references: "infra/relay/k8s/charts/README.md"
  status: active
  since: "2026-09-04"
  digest: >-
    Each Meridian service ships one chart under infra/relay/k8s/charts with a values.schema.json, the
    meridian-common library chart for labels and probes, and images referenced through global.imageRegistry
    by digest. Chart versions follow the release process and are published only from tags.
---
# Helm chart conventions

## When to use / when NOT to use
Use when you:
- create a chart under `infra/relay/k8s/charts/<service>/`,
- change templates, `values.yaml`, or `values.schema.json`,
- bump `Chart.yaml` `version` or `appVersion` for a release,
- add or update the dependency on the `meridian-common` library chart.

Do NOT use when:
- the resource is cloud infrastructure (`relay:terraform-conventions`),
- you are packaging charts into the offline bundle (`relay.edge:air-gapped-deploy`),
- you need to change the release tagging flow itself (`_root:release-process`).

## Steps
1. Scaffold: `make chart-new NAME=<service>` copies `charts/_template/` with `Chart.yaml`, `values.yaml`,
   `values.schema.json`, `templates/`, `tests/`, and `README.md`.
2. Declare `meridian-common` as a dependency in `Chart.yaml` and use its helpers
   (`meridian.labels`, `meridian.probes`, `meridian.securityContext`) instead of copying boilerplate.
3. Define every value in `values.yaml` with a comment and mirror it in `values.schema.json` (`additionalProperties: false`).
4. Reference images as `{{ .Values.global.imageRegistry }}/{{ .Values.image.repository }}@{{ .Values.image.digest }}`.
5. Write helm-unittest suites in `tests/*_test.yaml` for every template that contains a conditional.
6. Render and validate: `make chart-lint NAME=<service>` (helm lint plus kubeconform against the pinned k8s version).
7. Install into kind: `make chart-install NAME=<service> ENV=dev`.
8. For a release, bump `version` (chart) and `appVersion` (image) per `_root:release-process`;
   CI packages and pushes the chart to the internal OCI registry on tag.

## Conventions specific to this scope
- Chart name, service name, and release name are identical; namespaces are `meridian-<component>`.
- `values.yaml` is the complete documented default; environment overlays in `infra/relay/k8s/values/<env>/<service>.yaml`
  may only override keys that already exist.
- `global.imageRegistry` is required and has no default; installs must pass it, which the offline bundle relies on.
- Images are by digest; `image.tag` is rejected by the schema.
- All workloads set resource requests and limits, `securityContext` from the common chart, and readiness and liveness probes.
- Secrets are never templated from values; charts reference existing `Secret` names through `existingSecret` keys.
- `helm template` with default values (and a registry set) must render cleanly; it is a CI job.
- Labels come only from `meridian.labels`; no ad-hoc `app:` labels.
- `Chart.yaml` `version` bumps: patch for template fixes, minor for new values, major for removed or renamed values.
- `README.md` matches `helm-docs` output; CI diffs it.

## Verify
```bash
helm dependency update infra/relay/k8s/charts/<service>
helm lint infra/relay/k8s/charts/<service> --strict
helm template infra/relay/k8s/charts/<service> --set global.imageRegistry=<registry> | kubeconform -strict -kubernetes-version 1.30.0
helm unittest infra/relay/k8s/charts/<service>
helm-docs --chart-search-root infra/relay/k8s/charts/<service> --dry-run | diff - infra/relay/k8s/charts/<service>/README.md
```

## See also
- urn:skill:meridian:_root:release-process
- urn:skill:meridian:relay.edge:air-gapped-deploy
- urn:skill:meridian:relay:terraform-conventions
