# ADR-0001: Git is the source of truth; Agent Registry is a build artifact

**Status:** Accepted · 2026-09-04

## Context
Google Agent Registry now stores, versions (immutable `SkillRevision`), validates, searches (keyword + semantic over the full SKILL.md) and governs standalone skills. It also has a console UI and a built-in `gcp-skill-registry` skill that lets agents create skills directly. We could author skills in the registry, in Git, or both.

## Decision
Skills are authored only in the monorepo under `.agents/skills/`. CI publishes them to Agent Registry on merge. The registry is treated like an artifact repository: never edited by hand, always reproducible from a commit. The registry's own write tools (`gcp-skill-registry`, console "Add skill") are disabled for humans/agents via IAM (`agentregistry.viewer` for everyone except the CI service account, which gets `agentregistry.user`).

## Consequences
- Review, ownership (CODEOWNERS), history and rollback come from Git for free.
- Drift detection and commonality checks can run in the same PR as the code change.
- We do not build any storage, search or versioning. We lose nothing from the registry's features.
- If a team wants to "just add a skill quickly", the answer is a PR, not the console.
