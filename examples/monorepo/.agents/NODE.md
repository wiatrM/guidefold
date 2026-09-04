# Meridian

Meridian is a fictional open-source, Palantir-style data-integration and analysis platform built for
defence and public-safety organisations. It ingests data from many sources into a governed ontology, runs
batch and streaming pipelines over it, and gives analysts a workspace with geospatial, graph and
identity-aware services, all deployable to connected clusters or fully air-gapped edge sites. The whole
product lives in this single monorepo, owned at the root by `platform-engineering`, who maintain the build
system, the org-wide skills (monorepo conventions, ADRs, Postgres, security baseline, release process) and
the generated scope cards.

The tree has five top-level areas: `platforms/forge` (data integration: ontology modelling, Spark batch
pipelines, Kafka streaming ingestion), `platforms/atlas` (analyst workspace: geospatial indexing and tiles,
link-analysis graph API, identity and the `turnstile` auth service), `infra/relay` (deployment: Terraform,
Helm charts, offline edge bundles), `security` (classification labels and audit logging) and `libs` (shared
Go and Python libraries: db, classification, auth-sdk). Everything builds with Bazel from one `WORKSPACE`,
and development is trunk-based: short-lived branches squash-merge into `main`, monthly release trains branch
from it, and hotfixes land on release branches only.
