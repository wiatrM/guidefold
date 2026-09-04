# (Authoring spec used to seed the playground on 2026-09-04; kept for adding nodes/skills consistently.)

# Meridian playground — content spec for skill authors

Fixture root: examples/monorepo   (call it examples/monorepo)
Conventions (authoritative): docs/CONVENTIONS.md — read §4 and §5 first.
Hierarchy map: examples/monorepo/guidefold.yaml (already written — read it).

## Theme
Meridian = fictional open-source, Palantir-style data-integration + analysis platform for defence /
public-safety organisations. ALL skill content is about SOFTWARE ENGINEERING CONVENTIONS of that platform
(data pipelines, ontology modelling, geospatial indexing, RBAC, audit logging, air-gapped deployment,
Postgres, Kubernetes, Terraform, release process). Do NOT write anything about weapons, targeting,
tracking or surveilling individuals, or operational military procedures. Keep it to how engineers build
and operate the software. No real hostnames, no secrets, no absolute local paths, no real company names.

## Skill file rules (CI-enforced by `guidefold validate`)
Location: `examples/monorepo/<node-path>/.agents/skills/<skill-name>/SKILL.md` ; root skills: `examples/monorepo/.agents/skills/<name>/SKILL.md`.
Frontmatter — EXACTLY this shape:

```yaml
---
name: <skill-name>                       # MUST equal the directory name; kebab-case
description: "[<node/path>] <What it covers>. Use when <trigger>. Do not use for <anti-trigger>."
license: Apache-2.0
compatibility: "<one line: what tooling/access it needs>"
metadata:
  scope: <node>                          # dotted node from guidefold.yaml; root skills use _root
  owner: <owner>                         # node owner (or listed subteam) from guidefold.yaml
  requires:                              # OPTIONAL — only the URNs given in your assignment
    - urn:skill:meridian:<node>:<skill-name>
  references:                            # OPTIONAL — paths relative to examples/monorepo, optional #token
    - <path>#<token>
  status: active                         # or deprecated (then also add replaced_by: <urn>)
  since: 2026-09-04
  digest: >-
    Two or three sentences summarising the guidance. This text is copied into generated scope
    cards, so it must be a summary, never a procedure.
---
```

`[<node/path>]` = node with dots replaced by slashes, e.g. node `atlas.identity.turnstile` → `[atlas/identity/turnstile]`;
node `shared.auth-sdk` → `[shared/auth-sdk]`; root skills use `[meridian]`.
description ≤ 1024 chars and must say WHEN to use the skill. digest ≤ 3 sentences.

Body (after frontmatter), 40–90 lines, this structure:

```
# <Title>
## When to use / when NOT to use
## Steps
## Conventions specific to this scope
## Verify
## See also
```
Make the content concrete and realistic (commands, file names, naming rules, checklists) — it will be
semantically searched, so specific vocabulary matters. "See also" lists the `requires` URNs and 1–2
related URNs from the assignment table. Reference files with relative paths from examples/monorepo.

## Referenced code stubs
Every path in `metadata.references` MUST exist. Create each as a small but plausible stub (5–40 lines)
in the right language. If a reference has `#token`, the token string MUST appear in the file.

## NODE.md (optional per node)
`examples/monorepo/<node-path>/.agents/NODE.md` — 1–2 free-form paragraphs about the node (what it is, who owns it,
main components). Root: `examples/monorepo/.agents/NODE.md`. Only where the assignment says so.

## Requires graph (global — do not add other edges)
- forge.pipelines.streaming:kafka-ingestion → forge.pipelines:spark-pipeline-conventions, forge:dataset-conventions
- forge.pipelines:pipeline-testing → forge.pipelines:spark-pipeline-conventions
- forge.ontology:object-type-migrations → forge.ontology:ontology-modeling, _root:postgres-production
- atlas.geo:geospatial-indexing → _root:postgres-production
- atlas.geo:map-tile-serving → atlas.geo:geospatial-indexing
- atlas.graph:link-analysis-api → atlas:atlas-api-conventions
- atlas.identity.turnstile:postgres-auth → atlas.identity:rbac-policies, _root:postgres-production
- atlas.identity.turnstile:turnstile-oncall-runbook → atlas.identity.turnstile:postgres-auth
- relay.edge:air-gapped-deploy → _root:release-process, relay.k8s:helm-conventions
- relay.k8s:helm-conventions → _root:release-process
- security.audit:audit-logging → security:classification-labels
- shared.auth-sdk:auth-sdk-usage → atlas.identity:rbac-policies
(URN form: urn:skill:meridian:<node>:<name>)

## Full skill table (node → skill → owner → references)
_root (owner platform-engineering), paths under examples/monorepo/.agents/skills/:
  monorepo-conventions  refs: WORKSPACE, .github/CODEOWNERS
  adr-process           refs: docs/adr/README.md
  postgres-production   refs: libs/db/migrations/README.md, libs/db/pool.go#maxConns
  security-baseline     refs: security/policy/baseline.yaml#allowedRegistries
  release-process       refs: tools/release/build-bundle.sh
forge (forge-platform) platforms/forge/.agents/skills/:
  dataset-conventions   refs: platforms/forge/schemas/README.md
forge.ontology (ontology-team) platforms/forge/ontology/.agents/skills/:
  ontology-modeling     refs: platforms/forge/ontology/schema/object-types.yaml
  object-type-migrations refs: platforms/forge/ontology/migrations/README.md
forge.pipelines (pipelines-team) platforms/forge/pipelines/.agents/skills/:
  spark-pipeline-conventions refs: platforms/forge/pipelines/src/meridian_pipelines/base.py
  pipeline-testing      refs: platforms/forge/pipelines/tests/conftest.py
forge.pipelines.streaming (streaming-team) platforms/forge/pipelines/streaming/.agents/skills/:
  kafka-ingestion       refs: platforms/forge/pipelines/streaming/config/topics.yaml#retentionMs
atlas (atlas-platform) platforms/atlas/.agents/skills/:
  atlas-api-conventions refs: platforms/atlas/api/openapi.yaml
atlas.geo (geo-team) platforms/atlas/geo/.agents/skills/:
  geospatial-indexing   refs: platforms/atlas/geo/src/index/h3_index.go
  map-tile-serving      refs: platforms/atlas/geo/tiles/config.yaml#maxZoom
atlas.graph (graph-team) platforms/atlas/graph/.agents/skills/:
  link-analysis-api     refs: platforms/atlas/graph/src/query/traversal.go
atlas.identity (identity-platform) platforms/atlas/identity/.agents/skills/:
  rbac-policies         refs: platforms/atlas/identity/policies/rbac.rego
  legacy-session-auth   status: deprecated, replaced_by: urn:skill:meridian:atlas.identity.turnstile:postgres-auth ; no refs
atlas.identity.turnstile (turnstile-team; subteam turnstile-oncall) platforms/atlas/identity/turnstile/.agents/skills/:
  postgres-auth         refs: platforms/atlas/identity/turnstile/deploy/deployment.yaml#legacyAuthMode, platforms/atlas/identity/turnstile/src/auth/middleware.go
  turnstile-oncall-runbook  owner: turnstile-oncall ; refs: platforms/atlas/identity/turnstile/deploy/deployment.yaml
relay (relay-infra) infra/relay/.agents/skills/:
  terraform-conventions refs: infra/relay/terraform/main.tf
relay.edge (edge-team) infra/relay/edge/.agents/skills/:
  air-gapped-deploy     refs: infra/relay/edge/bundle/manifest.yaml#mirrorRegistry
relay.k8s (k8s-team) infra/relay/k8s/.agents/skills/:
  helm-conventions      refs: infra/relay/k8s/charts/README.md
security (security-org) security/.agents/skills/:
  classification-labels refs: libs/classification/labels.go#Label
security.audit (audit-team) security/audit/.agents/skills/:
  audit-logging         refs: security/audit/src/logger.go
shared (shared-libs) libs/.agents/skills/:
  shared-lib-versioning refs: libs/VERSIONING.md
shared.auth-sdk (identity-platform) libs/auth-sdk/.agents/skills/:
  auth-sdk-usage        refs: libs/auth-sdk/README.md
