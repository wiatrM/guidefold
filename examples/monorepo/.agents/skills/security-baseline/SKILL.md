---
name: security-baseline
description: "[meridian] The org-wide security baseline every Meridian component must satisfy: allowedRegistries for container images, image signing and SBOMs, dependency pinning, secret handling, TLS defaults and container hardening. Use when you add a container image, a new external dependency, a network listener or a CI workflow, or when a security review asks for the baseline. Do not use for classification-label semantics or audit-event formats, which the security org owns in its own skills."
license: Apache-2.0
compatibility: "Needs cosign, syft and read access to security/policy/baseline.yaml; CI runs the checks automatically."
metadata:
  scope: _root
  owner: platform-engineering
  references: "security/policy/baseline.yaml#allowedRegistries"
  status: active
  since: "2026-09-04"
  digest: >-
    security/policy/baseline.yaml is the machine-readable minimum for every Meridian service: images only
    from allowedRegistries, signed and with an SBOM, pinned dependencies, no plaintext secrets, TLS by default.
    Platform teams may tighten it but never relax it without a security-org approved exception.
---

# Security baseline

## When to use / when NOT to use
Use when you:
- add or update a container image reference in a Dockerfile, Helm chart or bundle manifest;
- add a new external dependency (Go module, PyPI package, npm package, Bazel `http_archive`);
- open a new network listener or change TLS settings;
- add a GitHub Actions workflow or grant a workflow new permissions;
- answer a security review checklist.

Do not use for how classification labels propagate (`security:classification-labels`) or for the audit
event schema (`security.audit:audit-logging`); those extend this baseline but are owned elsewhere.

## Steps
1. Read `security/policy/baseline.yaml`. It is the source of truth; this skill explains it.
2. Images: pull only from a registry listed under `allowedRegistries`. Reference by digest
   (`@sha256:...`) in anything that ships; tags are tolerated only in local compose files.
3. Sign every image you publish in the release workflow: `cosign sign --key env://COSIGN_KEY <image>@<digest>`,
   then attach an SBOM: `syft <image> -o spdx-json > sbom.json && cosign attest --predicate sbom.json`.
4. Dependencies: pin exact versions with a lockfile (`go.sum`, `requirements.lock`, `pnpm-lock.yaml`) and a
   checksum in `WORKSPACE`. The bump bot opens PRs; humans merge them.
5. Secrets: read from the mounted secret store path or an injected env var. Never commit them, log them or
   put them in Helm values. List the key names in the service's `secrets.md` so operators know them.
6. Network: listeners use TLS 1.2+ with the platform CA; plaintext is allowed only on `localhost` sidecars.
   Every HTTP service exposes `/healthz` and `/readyz` without auth and everything else behind auth-sdk.
7. CI: workflows declare `permissions:` explicitly, pin actions by commit SHA and never combine
   `pull_request_target` with a checkout of the PR head.
8. If you genuinely cannot meet a rule, file an exception under `security/policy/exceptions/` with an expiry
   date and get `@meridian/security-org` approval before merging.

## Conventions specific to this scope
- `baseline.yaml` keys are a stable API: `allowedRegistries`, `imageSigning`, `sbom`, `dependencies`,
  `secrets`, `tls`, `containers`. Tools parse them; renaming a key needs an ADR.
- Base images: distroless or the platform-maintained minimal image only; no `latest`, no package-manager
  installs in production stages.
- Containers run as non-root with a read-only root filesystem and no added Linux capabilities.
- Log lines never include tokens, session cookies or full request bodies; use the redaction helpers in
  `libs/auth-sdk`.
- Vulnerability gate: critical CVEs block a release; high CVEs need an exception with an owner.
- Air-gapped installs must remain possible: every allowed registry has a mirror path in the release bundle.

## Verify
```bash
python3 -c "import yaml; print(yaml.safe_load(open('security/policy/baseline.yaml'))['allowedRegistries'])"
cosign verify --key security/policy/cosign.pub <image>@<digest>
syft <image> -o table | head                                    # SBOM generates cleanly
grep -rn "image:" infra/ platforms/ | grep -v "@sha256"          # any hit is a tag-based reference to fix
```

## See also
- urn:skill:meridian:security:classification-labels
- urn:skill:meridian:relay.edge:air-gapped-deploy
