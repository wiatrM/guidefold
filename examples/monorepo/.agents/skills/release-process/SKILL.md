---
name: release-process
description: "[meridian] How Meridian versions, tags, builds and publishes releases: monthly release trains tagged vYYYY.MM.N, hotfix branches, the offline release bundle produced by tools/release/build-bundle.sh, changelog rules and rollback. Use when you cut a release, hotfix a shipped version, change what goes into the bundle or edit the release workflow. Do not use for shared-library version bumps or for applying a bundle on an edge site; those have their own skills."
license: Apache-2.0
compatibility: "Needs Bazel, helm, syft, cosign, signed-tag rights on main and the release workflow in .github/workflows."
metadata:
  scope: _root
  owner: platform-engineering
  references: "tools/release/build-bundle.sh"
  status: active
  since: "2026-09-04"
  digest: >-
    Meridian ships a monthly release train tagged vYYYY.MM.N from main, plus hotfix tags on release branches.
    Every release is an offline bundle built by tools/release/build-bundle.sh that contains images, Helm charts,
    migrations, SBOMs and checksums, so air-gapped sites can install without network access.
---

# Release process

## When to use / when NOT to use
Use when you:
- cut the monthly release train or a hotfix from a `release/vYYYY.MM` branch;
- change what `tools/release/build-bundle.sh` packs, or how it signs and checksums;
- edit `.github/workflows/release.yaml` or the release PR template;
- write or review `CHANGELOG.md` entries.

Do not use for bumping a shared library (`shared:shared-lib-versioning`), for installing a bundle on an
edge site (`relay.edge:air-gapped-deploy`) or for Helm chart layout (`relay.k8s:helm-conventions`).

## Steps
1. Freeze: on the first working day of the month branch `release/vYYYY.MM` from `main` and announce it.
   Only fixes labelled `release-blocker` merge into the branch afterwards.
2. Confirm every component's `CHANGELOG.md` has an `## Unreleased` section with user-facing entries. Move
   them under `## vYYYY.MM.0` in the release PR.
3. Run the migration dry-run and the upgrade test from the previous release:
   `bazel test //tools/release:upgrade_from_previous`.
4. Build the bundle: `tools/release/build-bundle.sh vYYYY.MM.0`. It writes `dist/meridian-vYYYY.MM.0.tar.gz`
   containing `SHA256SUMS` and a signed `manifest.yaml`.
5. Verify offline: `tools/release/build-bundle.sh --verify dist/meridian-vYYYY.MM.0.tar.gz` must pass on a
   machine with no registry access.
6. Tag: `git tag -s vYYYY.MM.0 -m "Meridian vYYYY.MM.0"` on the release branch and push the tag; the release
   workflow publishes images, charts and the bundle to the release store.
7. Hotfix: cherry-pick onto `release/vYYYY.MM`, bump the patch number (`vYYYY.MM.1`) and repeat steps 4 to 6.
   Never hotfix from `main` directly.
8. Rollback: the previous bundle stays installable for two trains; release notes list which migrations are
   irreversible and therefore used the two-phase migration pattern.

## Conventions specific to this scope
- Tag format is `vYYYY.MM.N` for the platform; shared libs use plain semver and are released independently.
- The bundle layout is fixed: `images/` (OCI layout), `charts/`, `migrations/<service>/`, `sbom/`,
  `manifest.yaml`, `SHA256SUMS`. Adding a top-level directory needs an ADR.
- Every image in the bundle is referenced by digest and signed; `build-bundle.sh` fails if an image comes
  from a registry outside the security baseline's `allowedRegistries`.
- Release notes have three sections: Breaking changes, Operator actions, Fixes. Breaking changes link the
  ADR that introduced them.
- The release captain rotates through platform-engineering; the checklist is the release PR template.
- No releases on the last working day of the week; hotfixes are the exception and need two approvals.
- Reproducibility: `build-bundle.sh` run twice on the same tag must produce identical `SHA256SUMS`.

## Verify
```bash
tools/release/build-bundle.sh --dry-run vYYYY.MM.0     # lists contents without writing
sha256sum -c dist/SHA256SUMS                            # every artefact matches
cosign verify-blob --key security/policy/cosign.pub --signature dist/manifest.yaml.sig dist/manifest.yaml
git describe --tags --exact-match                       # HEAD is on the release tag
```

## See also
- urn:skill:meridian:relay.edge:air-gapped-deploy
- urn:skill:meridian:relay.k8s:helm-conventions
