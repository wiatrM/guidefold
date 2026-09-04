# Guidefold — viability assessment

**Date:** 2026-09-04 · **Against:** DESIGN.md v0.2, ADR-0001…0007, CLI skeleton
**Method:** local `gcloud` SDK 579.0.0 help pages (alpha 2026.07.31), Google Cloud docs, harness vendor docs, GitHub issues. Every claim below carries a source.

> **Redaction note.** This file is a log of `gcloud` calls actually executed against the live
> Agent Registry. The publisher and hierarchy names in the recorded commands have been
> rewritten to this repository's fictional `meridian` / `atlas` vocabulary; the literal strings
> used at the time differed. Nothing else about the commands, responses or conclusions was
> altered — the record's technical content stands as verified.

## Verdict

**The project makes sense.** The problem is real (skill sprawl across four harnesses, no ownership or drift signal, context bloat), and the design is unusually disciplined: it builds nothing that a platform already provides and keeps the custom part to ~500 lines of glue. Every load-bearing platform feature exists today.

Three findings change the plan, in order of weight:

1. **Agent Registry skills are six weeks old and v1alpha.** The default allocation quota is 100 standalone skills per project and 100 revisions per skill; both are *quotas* ("you can typically request adjustments"), not system limits, so "hundreds of skills" means filing a quota increase early, not a redesign. The fixed system limits are 500 KB compressed ZIP, 10 MB uncompressed, 1 MB per file. Rate: 20 QPS global. (Numbers such as 10 MB ZIP / 500 MB / 10,000 files belong to the separate Vertex AI Skill Registry page.)
2. **The design conflates two Google registries.** ADK `list_skills` / `load_skill` and the built-in `gcp-skill-registry` skill belong to the *Vertex AI Skill Registry* (`aiplatform.googleapis.com`), not to *Agent Registry* (`agentregistry.googleapis.com`). ADR-0007's "Gemini/ADK agents consume the same registry natively, no adapter" is not true today.
3. **L0 scope cards need no registry at all.** `materialize`, `validate`, `drift`, `where`, and a hook that reads local skills deliver most of the value with zero GCP dependency. The registry should be a pluggable backend behind the existing `Registry` seam, with a local-filesystem backend first. That turns the alpha API from a foundation into an option.

Recommendation: keep the architecture, reorder the MVP so the local-only path ships first, and fix the concrete mismatches listed below.

## 1. Google Cloud Agent Registry — verified

| # | Design claim | Status | Evidence |
|---|-------------|--------|----------|
| R1 | Product exists with `Skill`, `SkillRevision`, `Publisher`; keyword + semantic search | **TRUE** | v1alpha overview; `gcloud alpha agent-registry skills {create,delete,describe,list,search,update}` and `skills revisions {create,delete,describe,download,list}` present locally in SDK 579 |
| R2 | Skills feature is Preview | **TRUE** — Preview since 2026-07-23, **v1alpha only**; Agent Registry itself GA 2026-06-18 but v1 covers agents/MCP servers/endpoints only | release notes |
| R3 | `skills search --query --search-type=semantic` | **TRUE**; `--search-type=keyword\|semantic`, plus generic `--filter` | local help |
| R4 | `skillId` is a prefix-searchable URN `urn:skill:<publisher>:<ns>:<name>` | **FALSE for our skills** — the URN is server-assigned: `urn:skill:projects-<NUMBER>:locations:<LOC>:private-<RESOURCE_ID>`. Prefix search works in the short form `skillId:private-meridian--atlas*` (keyword); the full-URN form returned nothing. See ADR-0008 | concepts page; live test |
| R5 | Create revision with base64 ZIP | **TRUE for REST** (`initialRevision.archiveUploadSource.archiveContent`), **FALSE for gcloud** — `--payload=<LOCAL ZIP PATH>`. Live: `skills create --payload` creates the skill but **no revision**; with `--initial-revision-name` it fails ("source is required"). Use `revisions create REV --skill=… --payload=…` | live test |
| R6 | Download revision payload | **TRUE** — `skills revisions download REV --skill=ID --location=L --destination=file.zip [--allow-overwrite]` writes a raw ZIP; REST `GET …/revisions/{rev}?alt=media` | local help |
| R7 | `skills create` flags | `--publisher`, `--display-name` (≤128), `--description`, `--type=simple`, `--target-state=draft\|active\|deprecated\|decommissioned\|disabled`, `--initial-revision-name`, `--payload`; `skills update --default-revision` | local help |
| R8 | Publisher can be created | **NO** — v1alpha Publisher has only `get`/`list`; user skills are implicitly `private-` under the project. `publisher:` in `guidefold.yaml` is a naming prefix only (ADR-0008) | REST reference; live test |
| R9 | MCP server at `agentregistry.googleapis.com/mcp` exposes skill tools | **FALSE** — 20 tools, all agent/MCP-server/endpoint/service/binding/operation. No skill search/get/download. ADR-0003 (CLI, not MCP) is therefore *required*, not merely preferred | MCP tools list |
| R10 | IAM roles | **TRUE** — `roles/agentregistry.{viewer,user,editor,admin}`, permissions `agentregistry.skills.*`, `agentregistry.skillRevisions.*`; `roles/mcp.toolUser` | IAM reference |
| R11 | `global` location | **TRUE** — standalone skills supported in `global`, `us`, `eu`. Known issue: `global` search may leak `us`/`eu` results | locations page |
| R12 | Gemini/ADK consume Agent Registry skills natively | **FALSE as written** — `list_skills`/`load_skill`/`gcp-skill-registry` are Vertex AI Skill Registry (regional: `us-central1`, `europe-west4`, `us-east5`; 10 MB zip). Agent Registry policy bindings can "authorize reasoning engine agents to load standalone skills", but the ADK tools named in the design point at the other registry | govern-agent-skills, skill-registry, adk.dev |

### Limits (Agent Registry skills, Preview)

| Limit | Value | Kind | Impact on design |
|-------|-------|------|------------------|
| Standalone skills per project | **100** | quota (adjustable) | File the increase request on day 1; no redesign needed |
| Revisions per skill | **100** | quota (adjustable) | Publish-on-every-merge exhausts this in months for active skills. CI deletes old non-default revisions (CLI keeps 20) |
| ZIP size | 500 KB compressed / 10 MB uncompressed / 1 MB per file / 8 dir levels | system limit (fixed) | Fine for text skills; CLI enforces before upload |
| API rate | 20 QPS regional/global, 200 aggregate | quota | L1 hook = 1 prefix search per top-level segment of the chain (cached) + 1 semantic per prompt |

## 2. Harnesses — verified

| # | Claim | Status | Notes |
|---|-------|--------|-------|
| H1 | Copilot CLI: AGENTS.md cwd→root chain + on-touch nested + `applyTo` instructions | **TRUE**, but issue #3051 (open) reports nested off-path AGENTS.md are *not* discovered from root at all | `applyTo` instructions are the real fallback; design already has them |
| H2 | Copilot `userPromptSubmitted` output dropped | **TRUE** for config-file hooks | — |
| H3 | Copilot cannot inject context via hooks | **FALSE** — `sessionStart` *can* return `additionalContext` | Copilot gets a session-level L1 (scope card + chain skills). Bugs #991 (fires per prompt) and #2201 (not at startup) affect timing |
| H4 | Copilot skill dirs | `.github/skills`, `.claude/skills`, **`.agents/skills`**, `~/.copilot/skills`, `~/.agents/skills` | `.agents/skills` symlink in `.github/skills` is unnecessary for Copilot |
| H5 | Claude Code hook stdout → context for `SessionStart`/`UserPromptSubmit` | **TRUE** | — |
| H6 | Claude Code nested `CLAUDE.md` lazy; `@AGENTS.md` import | **TRUE** (documented recommendation) | — |
| H7 | Claude Code Vertex env vars; managed settings push hooks | **TRUE** (`allowManagedHooksOnly`, managed `claudeMd`); skills are pushed via plugin marketplaces, not a skills key | ADR-0007 holds |
| H8 | Claude Code reads `.agents/skills/` | **FALSE** — only `~/.claude/skills/` and `.claude/skills/` | Bootstrap skill must be symlinked into `.claude/skills/` (design does this). Nested node skills are invisible to Claude Code except via `load` |
| H9 | Codex AGENTS.md root→cwd merge; nested `.agents/skills` | **TRUE**; chain capped at **32 KiB** (`project_doc_max_bytes`) | 4 levels × 80-line cards ≈ 20 KB. Add a byte cap next to the line cap |
| H10 | Codex hooks inject context | **TRUE** — plain stdout or `hookSpecificOutput.additionalContext`, subject to `additionalContextLimit` truncation; `~/.codex/hooks.json` or `<project>/.codex/hooks.json` | Bug #17532: repo-local hooks not firing. Keep hook output short |
| H11 | Gemini CLI `GEMINI.md`, `@import`, `.agents/skills` alias | **TRUE** | — |
| H12 | Gemini CLI hooks inject context | **TRUE**, but output **must be JSON** (`hookSpecificOutput.additionalContext`); plain stdout is rejected | `guidefold hook` needs a `--format gemini` mode |
| H13 | `skillscheck` exists | **TRUE** — 0.9.7 (2026-08-20), MIT, Python ≥3.11, `uvx skillscheck` | — |
| H14 | Agent Skills spec fields | **TRUE** — `name`, `description` required; `license`, `compatibility`, `metadata`, experimental `allowed-tools` | — |
| H15 | ARD 0.9: `/.well-known/ai-catalog.json` + `POST /search` | **STALE** — current spec is **v0.91 (2026-08-26)**; manifest renamed to `/.well-known/ard.json`, `ai-catalog.json` optional legacy | Update ADR-0004 |
| H16 | Agent Finder private registry via managed settings | **UNVERIFIABLE** — changelog says so; no documented settings key found; connector skill hard-defaults to GitHub's endpoint | Phase 2 risk |

## 2b. Live verification log (project `guidefold-test-b6a18a`, 2026-09-04)

Owner role alone → `PERMISSION_DENIED` on `agentregistry.skills.list`; `roles/agentregistry.admin` fixes it. Location `global` works. The project comes pre-populated with Google first-party skills (`urn:skill:discoveryengine.googleapis.com:…`, `urn:skill:cloud.google.com:…`), which semantic search returns alongside ours.

| Step | Command | Result |
|------|---------|--------|
| create | `skills create meridian--atlas-identity-turnstile--postgres-auth --type=simple --target-state=draft --payload=x.zip` | created as `private-meridian--…`, URN `urn:skill:projects-777479017000:locations:global:private-meridian--atlas-identity-turnstile--postgres-auth`, **no revision** |
| create with `--target-state=active` | same | rejected: "target_state is required and must be TARGET_STATE_DRAFT or TARGET_STATE_DISABLED" |
| create with `--initial-revision-name` | same + name | rejected: "initial revision name must start with the skill name" / "source is required" |
| REST create with `archiveContent` | `POST …/skills?skillId=…` | creates skill + revision `rev-<uuid>` (ACTIVE) but `defaultRevision` unset, skill DRAFT |
| add revision | `skills revisions create rev-2 --skill=private-… --payload=x.zip` | revision ACTIVE (~90 s LRO) |
| default | `skills update private-… --default-revision=projects/…/revisions/rev-2` | ok |
| promote | `skills update private-… --target-state=active` | STATE_ACTIVE |
| keyword prefix | `search --search-type=keyword --query='skillId:private-meridian--atlas*'` | hit |
| keyword prefix, full URN | `--query='skillId:urn:skill:projects-…:private-meridian--atlas*'` | **no hit** |
| keyword phrase | `--query='"[atlas/identity/turnstile]"'` | hit |
| semantic | `--query='add an authorization check to the turnstile postgres endpoint'` | our skill ranked 1st, then 4 Google first-party skills |
| list filter | `skills list --filter='name:skills/private-meridian--'` | hit (client-side) |
| download | `skills revisions download rev-2 --skill=… --destination=<dir>` | **extracts into the directory** (not a zip file); REST `?alt=media` returns the zip |
| publish fixture (26 skills) | `revisions create … --payload` | **rejected: "SKILL.md validation failed: metadata key-value pairs must be scalar strings"** — YAML lists/dates in `metadata` are invalid. Fixed by ADR-0010 (comma-separated strings); the string-only `hierarchy-index` skill had published fine |
| publish fixture, retry | `guidefold --backend agent-registry publish` (6 parallel workers) | **27/27 OK** in ~4 min: 25 ACTIVE, 1 DEPRECATED (`legacy-session-auth`, via active → deprecated), 1 index. ~27–45 s per skill |
| live find / hook / load / prewarm | from `platforms/atlas/identity/turnstile` | `find` 7 s, turnstile skills ranked first; hook injects top-3; `load` downloads; `prewarm` caches the 10-skill chain |
| download layout | `revisions download --destination=<dir>` | payload is extracted under `<dir>/<revision-id>/SKILL.md`; CLI flattens it |
| republish | `publish --only …:postgres-auth` | new revision, default moved, description/display-name re-synced from SKILL.md |
| delete | `skills delete` | fails with `cannot_delete_skill_with_revisions`; REST `DELETE …?force=true` works (LRO). Rejected uploads stay as `FAILED` revisions; CLI deletes them on the next publish |

Conclusion: the publish sequence is create(draft) → revisions create → update default → update active; the CLI now does exactly this and maps IDs per ADR-0008.

## 2c. Retrieval quality (papers you sent)

Graph-of-Skills (arXiv 2604.05333) and SkillRouter (arXiv 2603.22455) both show that flat description-embedding retrieval is not sufficient at scale: vector top-k scored below "load everything" on a 1,000-skill library, and hiding the skill body costs 37–44 pp of routing accuracy on ~80K skills. Agent Registry's semantic search indexes the body, which addresses the second finding, but offers no fusion, scores, reranking, or relations. The design response is in **ADR-0009**: scope-first filtering, client-side reciprocal-rank fusion of keyword + semantic legs, one-hop `requires` expansion, negative-trigger filtering, card/hydration budgets, a local BM25 leg, CI description lint plus near-duplicate detection, and a golden-query regression set. Model calls (listwise reranker) stay out of the hot path.

## 3. Concrete corrections

### To the CLI (`skills/guidefold/scripts/guidefold`)

1. ~~`Registry.publish`~~ **Done 2026-09-04:** create(draft) → `revisions create --payload` → `update --default-revision` → `update --target-state=active`; old revisions trimmed to 20.
2. ~~`Registry.download_payload`~~ **Done:** `revisions download <rev> --skill=<id> --destination=<dir>` (extracts in place); `<rev>` from `describe` → `defaultRevision`.
3. ~~Skill-id mapping~~ **Done (ADR-0008):** `<publisher>--<node dots→hyphens>--<name>`, server adds `private-`; reverse mapping via `guidefold.yaml`; validate rejects nodes that collide after flattening.
4. **Partly done:** one prefix search per top-level chain segment, filtered client-side; per-prompt semantic search. Session cache for the chain (`prewarm`) is still to do.
5. `hook`: add `--format text|gemini` (Gemini wants JSON). Codex accepts plain text.
6. `materialize`: add a byte cap (≤ 6 KB per card) alongside `CARD_CAP = 80` lines, for Codex's 32 KiB chain limit.
7. `publish`: after creating a revision, list revisions and delete the oldest non-default beyond N=20.
8. `validate`: enforce ZIP limits (500 KB compressed, 1 MB/file, 8 levels) before publish.
9. ~~`LocalRegistry` backend~~ **Done:** `registry.backend: local|agent-registry`; local `find` = node filter + keyword overlap (BM25 per ADR-0009 to follow).

### To the docs

- DESIGN.md §2 G2: `skillId:urn:skill:meridian:atlas.*` → trailing-`*` syntax; note user-minted URN ids are unverified.
- DESIGN.md §5.1, §7.2, ADR-0007: separate *Agent Registry* (distribution, this design) from *Vertex AI Skill Registry* (ADK consumption). State that ADK consumption needs either dual-publish from CI or Google's promised convergence.
- DESIGN.md §7.1 Copilot: L1 is partially available via `sessionStart` `additionalContext`.
- DESIGN.md §9: add quota risks (100 skills/project, 100 revisions/skill, 20 QPS) with mitigations above.
- ADR-0003: MCP path is confirmed absent for skills; reword "if/when".
- ADR-0004: ARD v0.91, `/.well-known/ard.json`.
- CONVENTIONS.md §2: Copilot reads `.agents/skills` natively; Claude Code does not.
- README/DESIGN doc links: `docs.cloud.google.com/agent-registry/<page>` (the `/docs/` form 404s).

## 4. Recommended MVP shape

Three ways to sequence the work:

**A. Local-first, registry as a backend (recommended).** Phase 0 = `where`, `validate`, `drift`, `materialize`, `index`, `hook` against a `LocalRegistry` that reads the repo. Every harness demo (L0 + L1 + L2) runs with no GCP. Phase 1 adds the `AgentRegistry` backend and `publish`, behind the same interface. Pros: demo this week, alpha API isolated, quota problem becomes a Phase 1 decision with data. Cons: `find` semantic ranking is weaker locally (keyword only) until Phase 1.

**B. Registry-first, as designed.** Do Day-1 verification, patch the CLI, publish 6–8 skills, then build cards and hooks. Pros: proves the hardest integration first. Cons: blocked on Preview access, allowlist, publisher creation, and quota answers before anything is demoable; every test needs GCP or heavy mocks.

**C. Split repos now.** `guidefold` (tool) + `guidefold-example-monorepo` (fixture). Pros: mirrors real usage. Cons: premature; an `examples/monorepo/` fixture inside this repo gives the same test surface with less overhead.

Go with **A**, keeping `examples/monorepo/` as the fixture and pytest target.

## 5. Day-1 checklist (revised)

1. Skill-id rules: try `skills create` with an id containing `urn:` and with a hyphen slug; record what the API accepts. Try `skills search --query='skillId:<prefix>*' --search-type=keyword` on the result.
2. Publisher: does `skills create --publisher=meridian` need a pre-existing Publisher? How is a PRIVATE publisher provisioned?
3. Quota: file the increase request for skills/project early; confirm revision deletion works on non-default revisions.
4. Gemini CLI hook: confirm the JSON envelope for `SessionStart`/`BeforeAgent`.
5. Codex repo-local hooks: test `<project>/.codex/hooks.json` against issue #17532; fall back to `~/.codex/hooks.json` template.
6. Copilot `sessionStart` `additionalContext`: confirm it lands in context from repo root and node dir.
7. Legal: license + IP sign-off (unchanged).

## Sources

- Agent Registry: overview, register-skills, manage-skill-revisions, search-agents-and-tools, use-agentregistry-mcp, locations, quotas, release-notes at `docs.cloud.google.com/agent-registry/…`; gcloud alpha reference for `agent-registry skills` and `skills revisions download`
- IAM: `docs.cloud.google.com/iam/docs/roles-permissions/agentregistry`, `…/mcp`
- Vertex AI Skill Registry: `docs.cloud.google.com/gemini-enterprise-agent-platform/build/skill-registry`; `…/govern/policies/govern-agent-skills`; `adk.dev/integrations/skills-registry/`
- Copilot: `docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions`, `…/reference/hooks-reference`, `…/concepts/agents/about-agent-skills`; issues github/copilot-cli #3051, #991, #2201
- Claude Code: `code.claude.com/docs/en/hooks-guide`, `…/memory`, `…/google-vertex-ai`, `…/managed-settings`, `…/skills`
- Codex: `learn.chatgpt.com/docs/agent-configuration/agents-md`, `…/docs/hooks`; issues #17532, #16933
- Gemini CLI: `geminicli.com/docs/cli/gemini-md/`, `…/cli/skills/`, `…/hooks/reference/`
- `pypi.org/project/skillscheck/` (0.9.7); `agentskills.io/specification`; `agenticresourcediscovery.org/spec/` (v0.91); GitHub changelog 2026-06-17 (Agent Finder GA)
