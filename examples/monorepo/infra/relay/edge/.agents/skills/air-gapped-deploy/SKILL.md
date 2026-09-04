---
name: air-gapped-deploy
description: "[relay/edge] Assembling and installing the Meridian offline bundle for air-gapped edge sites: image mirroring by digest, chart vendoring, manifest signing, and the offline install and upgrade sequence. Use when building a release bundle, adding a component to bundle/manifest.yaml, or changing the edge install procedure. Do not use for connected environments or for authoring the Helm charts themselves."
license: Apache-2.0
compatibility: "Needs the release toolchain (skopeo, helm, cosign, oras) on a build host with access to the internal registry; the target site has no network and receives the bundle on removable media."
metadata:
  scope: relay.edge
  owner: edge-team
  requires: "urn:skill:meridian:_root:release-process, urn:skill:meridian:relay.k8s:helm-conventions"
  references: "infra/relay/edge/bundle/manifest.yaml#mirrorRegistry"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: team
  refines: "urn:skill:meridian:_root:release-process"
  triggers: "offline bundle, air-gapped install, image mirroring by digest, bundle manifest.yaml, edge site, mirrorRegistry"
  digest: >-
    Edge sites install Meridian from a signed, self-contained bundle described by bundle/manifest.yaml:
    every image is mirrored by digest into the bundle registry, every chart is vendored, and nothing is
    fetched at install time. Bundles are built only from release tags and verified with cosign on both ends.
---
# Air-gapped deployment

## When to use / when NOT to use
Use when you:
- build an offline bundle for a tagged release (`edge-bundle-v<x.y.z>.tar`),
- add or remove a component, image, or chart in `infra/relay/edge/bundle/manifest.yaml`,
- change the offline install or upgrade scripts under `infra/relay/edge/install/`,
- change the `mirrorRegistry` settings used by the on-site registry container.

Do NOT use when:
- the target has outbound network access; use the standard Helm release flow (`relay.k8s:helm-conventions`),
- you are changing chart templates or values schemas (that is `relay.k8s`),
- you are cutting the release itself (`_root:release-process` covers tagging and artifact promotion).

## Steps
1. Start from a release tag produced per `_root:release-process`; bundles are never built from branches.
2. Update `bundle/manifest.yaml`: `release`, `components[]` (each with `chart`, `chartVersion`, `images[]`),
   and `mirrorRegistry` (`host`, `port`, `tlsSecret`, `pullSecret`).
3. Resolve every image to a digest: `make bundle-resolve` rewrites tags to `@sha256:` and fails on any tag left.
4. Mirror: `make bundle-mirror` copies images with skopeo into `bundle/registry/` (OCI layout) and pulls charts
   into `bundle/charts/`.
5. Sign: `make bundle-sign` runs cosign over each image and the manifest; signatures sit beside the layout.
6. Pack: `make bundle-pack` produces `dist/edge-bundle-v<x.y.z>.tar` plus `.sha256` and `.sig`.
7. On site: `install/verify.sh <bundle>` (checksum and signatures), `install/load-registry.sh` (starts the mirror
   registry from the OCI layout), then `install/apply.sh --site <site>` (helm upgrade --install from vendored charts).
8. Record the installed version in `install/state/installed.yaml` on site and in the release log.

## Conventions specific to this scope
- The bundle is self-contained: no `helm repo add`, no `docker pull`, no `curl` during install. CI runs the
  installer inside a network-less container to prove it.
- `mirrorRegistry.host` is always the in-cluster service name; charts are pointed at it with
  `--set global.imageRegistry=<host>:<port>` by `install/apply.sh`, never by editing values files.
- Images are referenced by digest in the manifest; tags are informational only.
- Every component maps to exactly one chart release name; images not claimed by a component fail `bundle-resolve`.
- Upgrades are forward-only and skip at most one minor version; larger jumps go through an intermediate bundle.
- Bundle size limit is 20 GiB; exceeding it needs edge-team approval and a split-bundle plan.
- Site-specific values live in `install/sites/<site>.values.yaml` without secrets; secrets travel as a sealed
  file in the bundle and are decrypted only on site.
- Rollback means reinstalling the previous bundle from the site's retained copy; sites keep the last two bundles.
- Only registries in the security baseline `allowedRegistries` list may be sources for `bundle-mirror`.

## Verify
```bash
make bundle-resolve && grep -c "sha256:" infra/relay/edge/bundle/manifest.yaml
make bundle-verify                                        # cosign verify on every image and the manifest signature
docker run --network none -v ./dist:/bundle edge-installer:test install/verify.sh /bundle/edge-bundle-v3.4.0.tar
helm template bundle/charts/*.tgz --set global.imageRegistry=<host>:<port> | grep "image:" | grep -vc "@sha256:"   # expect 0
```

## See also
- urn:skill:meridian:_root:release-process
- urn:skill:meridian:relay.k8s:helm-conventions
- urn:skill:meridian:relay:terraform-conventions
