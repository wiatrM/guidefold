# Meridian playground monorepo

A fictional open-source, Palantir-style data-integration and analysis platform for defence and
public-safety organisations. It exists only as a **Guidefold fixture**: many organisations and
teams, each owning skills at its own level of the tree.

| Org / platform | Path | What it is |
|----------------|------|------------|
| `forge` | `platforms/forge/` | data integration: ontology, batch + streaming pipelines |
| `atlas` | `platforms/atlas/` | analyst workspace: geospatial, graph/link analysis, identity (incl. the `turnstile` auth service) |
| `relay` | `infra/relay/` | deployment: air-gapped edge bundles, Kubernetes |
| `security` | `security/` | classification labels, audit logging |
| `shared` | `libs/` | shared libraries (db, classification, auth-sdk) |

Hierarchy map: `guidefold.yaml`. Skills: `**/.agents/skills/<name>/SKILL.md`. Generated scope
cards (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/instructions/*.instructions.md`) come
from `guidefold materialize` and are committed.

Regenerate cards from the guidefold repo root:

```bash
cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold materialize
```

All code under `platforms/`, `infra/`, `libs/`, `security/` is stub content referenced by skills
(`metadata.references`) so that `validate` and `drift` have something real to check.
