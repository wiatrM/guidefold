# Product focus

**Status:** Accepted · 2026-09-06 · product owner / product manager pass required by
[ADR-0027](adr/ADR-0027-product-focus-hard-rules.md) rule 4 · binds `docs/MVP.md` §5 and
[`docs/BACKLOG.md`](BACKLOG.md)

Every claim about our own state points to a merged PR or a report file. Every claim about a
competitor points to a URL, fetched 2026-09-06.

## The customer

The platform team of a large organisation that runs several agent harnesses over one monorepo with
many teams, and that has more internal rules, runbooks and conventions than any agent session can
load.

Not the individual developer on a single repository with a single harness — vendors will solve that
themselves, and three of them already have (see the matrix).

## The job to be done

An agent standing in `platforms/atlas/identity/turnstile/` must receive the handful of the
organisation's rules that apply *there*, in whatever harness the developer chose, without anyone
maintaining a list — and the people who write those rules must find out before merge whether what
they wrote can be found at all.

## The competitive matrix

| | (a) scoped by repo location | (b) cross-harness | (c) measures exposure/use | (d) author feedback before merge | (e) quality gate in CI |
|---|---|---|---|---|---|
| **Anthropic Agent Skills / Claude Code** [1] | partial — fixed dirs (`.claude/skills/`), no path or glob scoping; triggering is model-decided from the description | no — Anthropic surfaces only | **yes** — OTel `skill.name`; `/skill-doctor` reports per-skill cost, usage frequency and never-invoked skills | partial — `claude plugin validate` checks frontmatter; `skill-creator` runs blind A/B trigger evals | **yes** — `claude plugin validate` hard-fails in CI |
| **GitHub Copilot custom instructions** [2] | **yes, by glob** — `applyTo` frontmatter; `.github/copilot-instructions.md` always loaded. All matching layers merge into context; precedence is a hint, not a filter | no (Copilot coding agent separately reads `AGENTS.md`) | partial — per-response "References" names the file used, to that developer only; no aggregate view for a repo owner | no | no |
| **OpenAI Codex `AGENTS.md`** [3] | **yes** — nested per directory, nearest file wins | **yes** — the cross-vendor convention's origin | no | no | no |
| **Google Gemini CLI `GEMINI.md`** [4] | **yes** — hierarchical, but every applicable file is **concatenated** and sent each prompt | partial — `context.fileName` can point at `AGENTS.md` | partial — `/memory show` is local inspection only | no | no |
| **Cursor / Cline / Windsurf rules** [5] | **yes, by glob** or `alwaysApply` / `model_decision` | no (all bridge via `AGENTS.md`) | partial — Cursor team analytics covers usage and audit-logs rule *edits*, not which rule fired; Cline and Windsurf are client-side only | no | no |
| **`agents.md` convention** [6] | **yes** — nested, nearest wins, designed for monorepos | **yes** — ~22 listed adopters | no | no | no |
| **Google Cloud Agent Registry** [7] | no — scoped by GCP project/location and `publisher`/`skillId` | partial — A2A/MCP protocols, but a GCP service | no per-skill usage on the registry resources | no — push-based via `gcloud`/REST, not a PR workflow | weak — valid frontmatter only; no CI pipeline shipped |
| **MCP server registries** [8] | no — indexes servers, not repo-scoped guidance | **yes** | no | Docker's catalog: PR review plus automated test/scan before inclusion. Official registry: reactive denylisting | official registry: "unopinionated"; Docker: yes at submission |
| **Public skill marketplaces** [9] | no | **yes** — install adapters for claude-code, cursor, codex, copilot, gemini | partial — install counts and self-reported outcomes; exposure-biased, not repo-scoped | `tech-leads-club/agent-skills`: static analysis, Snyk, hash integrity, human review. `skills.sh`: no formal submission process | partial |
| **Backstage catalog + TechDocs** [10] | **yes** — `catalog-info.yaml`, `backstage.io/managed-by-location`, co-located TechDocs | portal, not an agent mechanism; MCP bridges exist | no first-party; needs an analytics plugin | no in core | community — RoadieHQ entity-validator lints `catalog-info.yaml` in CI |
| **Guidefold today** | **yes — by retrieval**, ≤ 4 ranked cards over the monorepo scope hierarchy, not concatenation [11] | partial — Claude Code hook and Copilot `find`/`load` templates exist; **neither demonstrated in a real session** (#81, #82) | on paper — ledger and per-skill report exist (PR #49, #58, #60); **never run on a real developer's data** (#91) | **yes** — per-PR collision report and trigger suggestions (PR #65); F5-in-`validate` pending (#86) | **yes** — `validate`; structured-corpus parity 0/243 (PR #67); E7.5 snapshot gate pending (#87) |

**Scale limits the matrix does not fit.** Windsurf silently drops rules past 12 000 characters total
across active rules [5]. Codex truncates `AGENTS.md` at 32 KiB by default, silently [3]. Gemini CLI
concatenates every applicable file on every prompt [4]. Claude Code's skill listing is capped at 1 %
of the context window [1]. Every location-scoped competitor loads or concatenates matching files and
then hits a wall. That wall is the market.

**No direct competitor found.** A scan for a product combining repo-scoped internal rules, git-native
CI validation, cross-harness delivery and usage telemetry returned nothing [9][12]. The closest
artefact is a community Backstage plugin (8 stars) that catalogues Copilot and Claude assets and
tracks per-asset install counts [10]. Absence of a competitor is not evidence of a market.

## The three value propositions the matrix supports

1. **Retrieval, not concatenation, at monorepo scale.** Every competitor that scopes by location
   loads what matches and truncates when it will not fit. Guidefold ranks thousands of skills and
   injects at most four cards. Measured: whole-hook p95 113 ms at 500 skills and 320 ms at 6 006
   (`docs/reports/bakeoff/R4b-lazy-terms-postings-2026-09-05.md`, PR #45); T1 sparse p95 54 ms at
   one client and 128 ms at four (`docs/reports/bakeoff/E1.1b-service-feasibility-2026-09-05.md`).
2. **The author finds out before merge.** The nearest thing anyone ships is frontmatter validation
   and a single skill's trigger A/B [1]. Nobody tells an author "this description takes N queries
   from skill X" across the whole corpus. PR #65 does; `docs/CONVENTIONS.md` §12 defines it.
3. **One measurement layer spanning harnesses.** Claude Code measures Claude Code [1]; Copilot shows
   one developer one reference list [2]; Cursor audits rule *edits* [5]. A monorepo owner running
   four harnesses has no single answer to "which of our rules is never seen". Ours exists
   (PR #49, #58, #60) and has been run on nobody.

Proposition 1 is measured. Propositions 2 and 3 are built and unproven — which is what
[`docs/BACKLOG.md`](BACKLOG.md) epics A, B and C exist to settle.

## What we do not do, and who does

| Not us | Who does it |
|---|---|
| A catalogue portal or developer-portal UI | Backstage + TechDocs, Port, Cortex [10] |
| A public skill marketplace or distribution channel | skills.sh, `tech-leads-club/agent-skills`, Docker MCP catalog [8][9] |
| Indexing MCP servers or tools | the official MCP registry [8] |
| Winning single-harness, single-repo discovery | Anthropic (`/skill-doctor`, `claude plugin validate`) [1]; Copilot `applyTo` [2] |
| A registry, control plane or hosting product | Google Cloud Agent Registry [7] — for us it is an optional downstream mirror (`docs/MVP.md` §2), parked in #117 |
| Our own retrieval model | our own number: dense gives +17.96 pp in distribution and **+0.67 pp [−1.50, +2.83]** out of it (DENSE-PROGRAM §7). It is one gated research track (#76), never a product dependency (ADR-0027 rule 2) |
| Automated promotion, probation, induction, lifecycle | nobody — and it is downstream of a value we have not yet demonstrated. Parked in #117 |

## The next four weeks, in one measurable sentence

By **2026-10-04**, at least one developer who did not build Guidefold has run at least 20 real
Claude Code or Copilot CLI sessions in a design-partner monorepo; the telemetry ledger for that
repository contains a search and a load for each of them; and a named skill owner has received a
weekly per-skill report and recorded at least one decision made from it.

Nothing else in this repository is more important than that sentence until it is true or false.

## Kill criteria

| If | Then |
|---|---|
| No design partner is agreed by **2026-09-20** (#78) | Stop building features. Either use Guidefold on this repository as its only user and label the evidence as such, or stop. |
| Ten commented skill PRs produce zero text changes (#88) | Value proposition 2 is false. Drop the authoring loop to a plain linter and re-scope. |
| Four weeks of real sessions produce no owner decision (#95) | Value proposition 3 is false. Stop building telemetry as a product surface. |
| TLS and IAM push whole-client p95 past 400 ms and it cannot be recovered (#97) | T1 is not a supported tier. The product is T0 only, and the runbook says so. |
| Pilot E6.7 shows no paired time or task-success benefit (#106) | No work beyond T1. ADR-0027 rule 6. |
| Family E misses its pre-registered gate (#111) | Dense is closed as a product path. This is the expected outcome, not a surprise. |
| A vendor ships cross-harness, location-scoped retrieval with pre-merge author feedback | The differentiator is gone. Re-scope to the authoring loop alone, or stop. |

## Design partner

To be filled by #78 before 2026-09-20: repository, developers, receiving skill owner, data policy,
start date. Until this section has names in it, every "done" in this repository is provisional under
ADR-0027 rule 3.

## Sources

1. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview ·
   https://code.claude.com/docs/en/skills · https://code.claude.com/docs/en/hooks ·
   https://code.claude.com/docs/en/monitoring-usage
2. https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions ·
   https://docs.github.com/en/copilot/concepts/agents/hooks ·
   https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
3. https://agents.md/ · https://github.com/openai/codex/issues/12115 ·
   https://github.com/openai/codex/issues/13386 · https://github.com/openai/codex/issues/7138
4. https://geminicli.com/docs/cli/gemini-md/ ·
   https://google-gemini.github.io/gemini-cli/docs/cli/commands.html
5. https://cursor.com/docs/context/rules · https://cursor.com/docs/account/teams/analytics ·
   https://docs.cline.bot/features/cline-rules · https://docs.devin.ai/desktop/cascade/memories
6. https://agents.md/
7. https://docs.cloud.google.com/agent-registry/overview ·
   https://docs.cloud.google.com/agent-registry/search-agents-and-tools
8. https://github.com/modelcontextprotocol/registry · https://registry.modelcontextprotocol.io/ ·
   https://github.com/docker/mcp-registry · https://smithery.ai/
9. https://github.com/tech-leads-club/agent-skills · https://arxiv.org/abs/2607.00911
10. https://backstage.io/docs/features/software-catalog/descriptor-format/ ·
    https://backstage.io/docs/ai/mcp-actions/ · https://github.com/RoadieHQ/backstage-entity-validator ·
    https://github.com/JulianPedro/backstage-dev-ai-hub · https://docs.cortex.io/standardize/scorecards ·
    https://docs.port.io/guides/all/build-port-scorecards-with-mcp/
11. `docs/DESIGN.md`, ADR-0006, ADR-0024 §1; behaviour in `skills/guidefold/scripts/guidefold`
12. Scanned for: "agent skill CI", "skill registry monorepo", "instruction retrieval for coding
    agents", "context engineering platform", "agent context management platform". No product found
    combining (a)–(e).
