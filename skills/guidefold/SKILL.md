---
# This is the bootstrap skill template Guidefold ships to every consumer monorepo (see
# CLAUDE.md "Layout" and docs/adr/ADR-0019). Replace <publisher> below with the `publisher`
# value from your monorepo's guidefold.yaml before copying this into `.agents/skills/guidefold/`.
name: guidefold
description: "[<publisher>] Discover and load this organization's guidance (conventions, procedures, runbooks) from the Agent Registry, scoped to where you are in the monorepo. Use BEFORE implementing any task that touches this organization's platforms, products, deployment, auth, data stores or internal tooling, or whenever an instruction says 'follow team conventions'. Do not use for generic language/library questions."
license: Apache-2.0
compatibility: "Requires gcloud CLI with `gcloud auth application-default login` and the agentregistry.viewer role on the registry project. Works in Copilot CLI, Claude Code, Codex, Gemini CLI."
metadata:
  scope: _root
  owner: platform-engineering
  status: active
---

# Guidefold — organizational guidance, unfolded on demand

This organization keeps procedural knowledge as Agent Skills in a hierarchy that mirrors the
monorepo: `<publisher> (root) → product/platform → sub-platform → team`. Skills closer to your
current directory are more specific; ancestors hold shared conventions. This skill tells you how
to find and load the right ones progressively, so you never pre-load the whole organization.

## You may already have most of this

- The `AGENTS.md` / `CLAUDE.md` chain in your context is the **scope card** for where you are:
  node, owner, and one-line digests of every ancestor level (root → product → platform → team)
  with skill URNs. Read it first; it is authoritative about *which* skills exist.
- In Claude Code / Codex a hook may have already printed `[guidefold] Relevant organizational
  guidance…` with URNs for this prompt. If so, skip to step 3.

## Workflow (do these in order, stop as soon as you have enough)

1. **Locate yourself**
   ```bash
   scripts/guidefold where
   ```
   Prints the hierarchy node for the current directory (e.g. `atlas.identity.turnstile`),
   its owner, and the ancestor chain. If you are outside any node you get `_root`.

2. **Find candidate skills for the task** (one call; describe the task in plain language)
   ```bash
   scripts/guidefold find "add authorization check to Turnstile Spanner path" --scope <node>
   ```
   Returns up to 8 ranked cards: URN, display name, one-line description, scope, owner, and
   whether it is an ancestor-scope skill. Ranking: exact node > ancestors > semantic hits
   elsewhere. Cards are cheap; do not load everything.

3. **Load only what you need**
   ```bash
   scripts/guidefold load <urn>
   ```
   Downloads the default revision into `.guidefold/cache/<urn>/` and prints the path of
   `SKILL.md`. Read that file. If its frontmatter has `metadata.requires`, load those URNs
   too (they are shared conventions you must follow). Typical depth: 1–3 skills.

4. **Apply and cite**
   Follow the loaded instructions. In your final summary, list the URNs you applied so the
   reviewer can check them.

## Rules

- Prefer the most specific skill; ancestor skills add constraints, they do not override
  the specific one.
- If `find` returns nothing relevant, say so and proceed with general best practice — do
  not invent this organization's conventions.
- Never edit files under `.guidefold/cache/`. To improve a skill, open a PR in the
  monorepo at the path shown by `scripts/guidefold where --skill <urn>`.
- If a loaded skill looks stale (references a file/flag that no longer exists), mention it
  explicitly in your summary; CI will flag it as drift.

## Map of the organization (optional, once per session)

```bash
scripts/guidefold load urn:skill:<publisher>:_index:hierarchy-index
```
This is a generated overview of all nodes, owners and skill names. Use it when the task
spans several platforms or you are unsure where you are.

## Examples

- Task in `platforms/atlas/identity/turnstile/`: `where` → `atlas.identity.turnstile`;
  `find` → `spanner-auth` (turnstile), `atlas-auth` (atlas), `spanner-production`
  (root); load all three because `spanner-auth` requires the other two.
- Task in `products/booking/`: `where` → `booking`; `find "add a new fare rule"` → likely one
  booking-scope skill and one root skill on ADR/PR conventions.
