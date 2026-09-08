---
title: Deploy
description: The hosted service, the worker and this portal, on Kubernetes with ArgoCD.
---

The adapter in your monorepo works with no server at all. The hosted service adds the review screen, the usage numbers, exact-revision delivery and the extraction jobs. It is one Go binary in two roles, API and worker, with Postgres.

## Parts

| Part | Image | Talks to |
|---|---|---|
| API | `services/search/Dockerfile` | Postgres, your browser, the adapter |
| Worker | `services/search/Dockerfile.worker` | Postgres only, plus a model endpoint if you enable a generator |
| Portal (this site) | `portal/Dockerfile` | nothing; static files behind nginx |

The API image has no Python. The worker has Python and the adapter file, because import parsing runs the repository's own trusted builder over a tree it materialised from blobs. It never runs a script from an imported repository.

## Helm chart

`deploy/k8s/chart` is the one chart. Values you will set:

```yaml
image: registry.example.com/guidefold-search@sha256:...
ingress:
  enabled: true
  host: guidefold.example.com
  tlsSecret: guidefold-tls
database:
  host: postgres.example.svc
  networkPeers: [...]
worker:
  enabled: true
  image: registry.example.com/guidefold-worker@sha256:...
  generator: none
portal:
  enabled: true
  image: registry.example.com/guidefold-portal@sha256:...
  host: docs.example.com
```

Images are pinned by digest. A production render fails without a network policy. The worker's egress is DNS and the database; add the model endpoint yourself if you enable a generator.

## ArgoCD

Point an Application at the chart path and your values file. Promotion between environments is a change to the image digest, checked by `tools/search_service/k8s_release.py`, which refuses a stale promotion. Rollback is the previous digest.

## The portal

The pages you are reading are plain Markdown in `portal/`. They are written in Mintlify's format, so `npx mint dev` previews them and Mintlify can host them. For self-hosting, the same files are built to static HTML with MkDocs Material and served by nginx:

```bash
docker build -f portal/Dockerfile -t guidefold-portal .
```

Mintlify's own static export and Helm chart are a private enterprise beta at the time of writing, which is why the self-hosted build uses an open source renderer over the same source files. Diagrams are Mermaid fences and render in both.

## Secrets

Every secret is a file, never an environment variable with the value in it: `PG_PASSWORD_FILE`, `WORKOS_API_KEY_FILE`, `OPENAI_API_KEY_FILE`, `ANTHROPIC_API_KEY_FILE`. The chart mounts them from one Kubernetes Secret at `/run/credentials`.
