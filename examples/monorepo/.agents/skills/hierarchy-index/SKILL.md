---
name: hierarchy-index
description: "[meridian] Generated map of all hierarchy nodes, owners and skills. Load once per session when unsure where you are."
metadata:
  scope: _index
  owner: platform-engineering
  generated: "true"
  status: active
---
# meridian skill hierarchy

## _root  (owner: platform-engineering)  paths: **
- `urn:skill:meridian:_root:adr-process` — [meridian] How Meridian records architecture decisions as ADRs under docs/adr: numbering, template sections, status life
- `urn:skill:meridian:_root:monorepo-conventions` — [meridian] Layout, ownership and build conventions for the Meridian monorepo: directory structure per platform, Bazel ta
- `urn:skill:meridian:_root:postgres-production` — [meridian] Production Postgres conventions shared by every Meridian service: schema migrations with golang-migrate, conn
- `urn:skill:meridian:_root:release-process` — [meridian] How Meridian versions, tags, builds and publishes releases: monthly release trains tagged vYYYY.MM.N, hotfix 
- `urn:skill:meridian:_root:security-baseline` — [meridian] The org-wide security baseline every Meridian component must satisfy: allowedRegistries for container images,

## forge  (owner: forge-platform)  paths: platforms/forge/**
- `urn:skill:meridian:forge:dataset-conventions` — [forge] Naming, schema registration, and lineage tagging rules for datasets produced or consumed on the Forge data-integ

## forge.ontology  (owner: ontology-team)  paths: platforms/forge/ontology/**
- `urn:skill:meridian:forge.ontology:object-type-migrations` — [forge/ontology] Migrating released ontology object types: adding, renaming, widening, or dropping properties and links 
- `urn:skill:meridian:forge.ontology:ontology-modeling` — [forge/ontology] How to define object types, properties, and link types in the Forge ontology backed by Postgres. Use wh

## forge.pipelines  (owner: pipelines-team)  paths: platforms/forge/pipelines/**
- `urn:skill:meridian:forge.pipelines:pipeline-testing` — [forge/pipelines] Unit and golden-file testing of PySpark batch pipelines with pytest, a local SparkSession, and shared 
- `urn:skill:meridian:forge.pipelines:spark-pipeline-conventions` — [forge/pipelines] Structure, naming, and lifecycle hooks for PySpark batch pipelines in the meridian_pipelines package. 

## forge.pipelines.streaming  (owner: streaming-team)  paths: platforms/forge/pipelines/streaming/**
- `urn:skill:meridian:forge.pipelines.streaming:kafka-ingestion` — [forge/pipelines/streaming] Building Kafka ingestion jobs with Spark Structured Streaming: topic declaration, consumer g

## atlas  (owner: atlas-platform)  paths: platforms/atlas/**
- `urn:skill:meridian:atlas:atlas-api-conventions` — [atlas] HTTP API design rules for every atlas service: URL layout, the shared error envelope, cursor pagination, version

## atlas.geo  (owner: geo-team)  paths: platforms/atlas/geo/**
- `urn:skill:meridian:atlas.geo:geospatial-indexing` — [atlas/geo] Indexing conventions for geospatial layers in atlas: PostGIS geometry columns, companion H3 cell columns, Gi
- `urn:skill:meridian:atlas.geo:map-tile-serving` — [atlas/geo] Serving atlas geo layers as Mapbox vector tiles: per-layer zoom ranges, simplification, generalisation by H3

## atlas.graph  (owner: graph-team)  paths: platforms/atlas/graph/**
- `urn:skill:meridian:atlas.graph:link-analysis-api` — [atlas/graph] Design and implementation rules for the atlas graph endpoints (/v1/graph/neighbors, /v1/graph/paths): requ

## atlas.identity  (owner: identity-platform)  paths: platforms/atlas/identity/**
- `urn:skill:meridian:atlas.identity:legacy-session-auth` — [atlas/identity] DEPRECATED. Cookie-based session authorization evaluated inside each atlas service, superseded by turns
- `urn:skill:meridian:atlas.identity:rbac-policies` — [atlas/identity] Authoring and testing the atlas RBAC policy bundle in OPA Rego: the analyst/supervisor/admin role model

## atlas.identity.turnstile  (owner: turnstile-team)  paths: platforms/atlas/identity/turnstile/**
- `urn:skill:meridian:atlas.identity.turnstile:postgres-auth` — [atlas/identity/turnstile] Add or change authorization checks in the turnstile service: bearer-token validation, princip
- `urn:skill:meridian:atlas.identity.turnstile:turnstile-oncall-runbook` — [atlas/identity/turnstile] On-call runbook for the turnstile authorization service: what each TurnstileAuth* alert means

## relay  (owner: relay-infra)  paths: infra/relay/**
- `urn:skill:meridian:relay:terraform-conventions` — [relay] Terraform layout, module usage, remote state, and review rules for Meridian infrastructure under infra/relay. Us

## relay.edge  (owner: edge-team)  paths: infra/relay/edge/**
- `urn:skill:meridian:relay.edge:air-gapped-deploy` — [relay/edge] Assembling and installing the Meridian offline bundle for air-gapped edge sites: image mirroring by digest,

## relay.k8s  (owner: k8s-team)  paths: infra/relay/k8s/**
- `urn:skill:meridian:relay.k8s:helm-conventions` — [relay/k8s] Authoring and releasing Helm charts for Meridian services under infra/relay/k8s/charts: chart layout, values

## security  (owner: security-org)  paths: security/**
- `urn:skill:meridian:security:classification-labels` — [security] Data-classification labels in Meridian: the Label enum in libs/classification (UNCLASSIFIED, OFFICIAL, RESTRI

## security.audit  (owner: audit-team)  paths: security/audit/**
- `urn:skill:meridian:security.audit:audit-logging` — [security/audit] How Meridian services emit tamper-evident audit events: the structured logger in security/audit/src, ma

## shared  (owner: shared-libs)  paths: libs/**
- `urn:skill:meridian:shared:shared-lib-versioning` — [shared] Semantic versioning, tagging and compatibility rules for the shared libraries under libs (db, classification, a

## shared.auth-sdk  (owner: identity-platform)  paths: libs/auth-sdk/**
- `urn:skill:meridian:shared.auth-sdk:auth-sdk-usage` — [shared/auth-sdk] How services consume the Meridian auth SDK (Go and Python) to authenticate callers and enforce RBAC de
