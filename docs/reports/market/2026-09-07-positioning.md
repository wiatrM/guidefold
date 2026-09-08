# 2026-09-07 — Positioning refresh: re-verifying the competitive matrix

**Date:** 2026-09-07 · **Status:** verification pass, stands alongside `docs/PRODUCT-FOCUS.md` (2026-09-06);
does not edit or replace it. **Scope:** re-fetch every URL the 2026-09-06 matrix cites, report what the
2026-09-07 fetch says, and re-derive positioning from what survives.

**Method note, read before the tables.** The interval between the matrix's fetch date and this one is one
day. Read literally, "what changed since yesterday" returns "nothing" for most rows and wastes the pass. The
useful question is **correctness verification of the 2026-09-06 cells**, not a day-over-day diff — several
cells turn out to have been wrong (or already stale) on the day they were written, not newly wrong today.
Every verdict below is one of: **VERIFIED UNCHANGED** (re-fetched, cell still accurate), **CORRECTED**
(cell was/is wrong, correction given), or **COULD NOT VERIFY** (fetch failed, blocked, or no supporting
quote — treated as unverified, never as confirmation). Every competitor claim below carries a URL that was
actually fetched on 2026-09-07 and a verbatim quote; a claim without both is marked accordingly and excluded
from the synthesis. Every claim about Guidefold's own state points to a commit, a merged PR, a test file, or
`docs/PIVOT-IMPLEMENTATION.md` (itself dated 2026-09-07 and treated here as ground truth, per this task's
brief) — never to a plan or a PRD promise.

Five research passes fed this report: three parallel `general-purpose` agents — one for Codex/Gemini CLI,
one for Google Cloud Agent Registry/MCP registries, one for public marketplaces/Backstage — each required to
cite URL + fetch status + verbatim quote per claim; one `claude-code-guide` agent for Anthropic-specific
product questions (`/skill-doctor`, `claude plugin validate` CI contract, team-wide telemetry); and direct
`WebFetch`/`WebSearch` calls in this session for the four load-bearing rows (Anthropic (a), Copilot (b),
Cursor (c), the `agents.md` convention) plus the Windsurf/Devin and Guidefold-installer checks in §1.5 and
§4.1. Two fetches failed outright (`docs.port.io/guides/all/build-port-scorecards-with-mcp/` — 404 twice;
Google's Gemini-platform release-notes page — returned navigation only) and are reported as **COULD NOT
VERIFY**, not filled from search-summary text.

---

## 1. Verification log

### 1.1 Anthropic Agent Skills / Claude Code — the load-bearing row

The doc's own header flags "current Claude Code has nested skills, `/skill-doctor`, evals" as things its
prose is stale on. The matrix's columns (c) and (e) for this row *already* credit `/skill-doctor` and
`claude plugin validate` — so the header's stale-flag isn't about those cells. It's about column **(a)**,
and the flag was correct.

| Cell | 2026-09-06 claim | 2026-09-07 verdict |
|---|---|---|
| (a) scoped by location | "partial — fixed dirs (`.claude/skills/`), no path or glob scoping; triggering is model-decided from the description" | **CORRECTED — this is wrong.** |
| (b) cross-harness | "no — Anthropic surfaces only [Claude Code]" | VERIFIED UNCHANGED |
| (c) measures exposure/use | "yes — OTel `skill.name`; `/skill-doctor` reports per-skill cost, usage frequency and never-invoked skills" | CORRECTED — real, but narrower than "yes" implies |
| (d) author feedback before merge | "partial — `claude plugin validate` checks frontmatter; `skill-creator` runs blind A/B trigger evals" | VERIFIED UNCHANGED, and reinforced |
| (e) quality gate in CI | "yes — `claude plugin validate` hard-fails in CI" | VERIFIED UNCHANGED |

**(a), in detail.** Fetched `https://code.claude.com/docs/en/skills` 2026-09-07. Quotes:

> "Skills also load from nested `.claude/skills/` directories below your working directory. When Claude reads
> or edits a file in a subdirectory, skills from that subdirectory's `.claude/skills/` become available. This
> lets a monorepo package provide its own skills that apply when working on that package, even if the session
> started at the repo root."

> `paths` (frontmatter field) — "Glob patterns that limit when this skill is activated... When set, Claude
> loads the skill automatically only when working with files matching the patterns."

> "If a nested skill shares a name with another skill, both stay available... The nested one appears under a
> directory-qualified name, `apps/web:deploy`... Claude picks the variant that matches the files it is
> working on."

This is real, working, arbitrary-depth, path-scoped discovery, plus an explicit glob field — not "no path or
glob scoping." **This is the single most important correction in this report**: Guidefold's column-(a) claim
cannot be "we scope by location and nobody else does" for the single-harness case. It has to be "we scope by
location **and deliver the same answer to whichever harness the developer is in, from one governed source,
across many repos with an accountable owner** — Claude Code's version of this is real but is Claude-Code-only,
authored per-directory by hand, with no cross-repo scope hierarchy, no owner-of-record, and no org-wide
consolidation."

**(c), in detail.** The `claude-code-guide` agent confirmed `/skill-doctor` is real:

> "Run `/skill-doctor` to see what each of your skills costs and how often it gets used... It flags skills in
> the listing that have never been invoked."

But it also fetched `monitoring-usage.md` and found the matrix's implicit "yes" overreaches:

> "No built-in team-wide or repository-wide dashboard. Claude Code only *emits* the telemetry (metrics +
> events) via OTLP; building dashboards, aggregations, or reports is left entirely to whatever backend you
> send data to... No dedicated skill-usage counter metric... No repo-scoped reporting attribute."

`/skill-doctor` is a real, useful, **per-developer, per-session** report. It is not an owner-level, org-wide,
across-repo view — which is what Guidefold's telemetry claims to be (on paper; see §3).

**(d), in detail — the differentiator that survives intact.** The agent confirmed `claude plugin validate
--strict` and `skill-creator`'s blind A/B are both real (exit-code contract quoted, description-tuning quoted).
But asked directly whether Claude Code detects, before merge, that a new or edited skill description will
steal invocations from a sibling skill in the same project corpus, the answer is an explicit no:

> "There is **no documented mechanism** to detect description collisions before merge... The recommended
> workaround per the documentation: write should-trigger/should-not-trigger test prompts for both the new and
> existing skill, run them in a fresh session with both enabled, and manually verify no unwanted
> cross-invocation occurs. This is **not automated**."

This is exactly Guidefold's differentiator #2 (`docs/PRODUCT-FOCUS.md` §"the author finds out before merge") —
and it holds, confirmed against the vendor's own current docs, not against a year-old snapshot.

### 1.2 GitHub Copilot custom instructions

| Cell | 2026-09-06 claim | 2026-09-07 verdict |
|---|---|---|
| (a) | "yes, by glob — `applyTo` frontmatter; `.github/copilot-instructions.md` always loaded" | VERIFIED UNCHANGED, with a scope nuance |
| (b) | "no (Copilot coding agent reads `AGENTS.md`)" | **CORRECTED — understates it** |
| (c) | partial — per-response "References" | VERIFIED UNCHANGED |
| (d) / (e) | no / no | VERIFIED UNCHANGED |

Fetched `docs.github.com/.../add-repository-instructions` 2026-09-07: `applyTo` glob scoping confirmed;
`copilot-instructions.md` is loaded "for all requests made in the context of a repository" (not literally
unconditional, but repo-scoped, not file-scoped — a minor nuance, not a correction).

The real correction is (b). Fetched `github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/`
2026-09-07:

> "You can also create nested `AGENTS.md` files which apply to specific parts of your project... Alongside
> `AGENTS.md`, the agent continues to support GitHub's `.github/copilot-instructions.md` and
> `.github/instructions/**.instructions.md` formats, plus `CLAUDE.md` and `GEMINI.md` files."

Copilot's coding agent reads **AGENTS.md, CLAUDE.md, and GEMINI.md natively**, on top of its own format. This
dates to August 2025 — over a year before the original matrix's 2026-09-06 scan, which should have caught it
and didn't (a methodology flag, echoed in the Backstage finding below, not a change since yesterday). It is
real cross-format reading, but narrow: it's the **coding agent surface only** — not Copilot CLI, which
Microsoft's own docs confirm uses a wholly separate `.agent.md` format and is unaffected by any of this; not
Copilot Chat. There is no documented precedence order across four simultaneously-read formats, and no
retrieval or ranking — everything that matches gets concatenated into one agent's context. The corrected cell:
**partial — one Copilot surface (not the CLI most developers touch) reads three vendors' formats
unilaterally, with no merge contract and no ranking; this is convergence at the file-format layer, not a
shared retrieval layer.**

### 1.3 OpenAI Codex `AGENTS.md`

All five cells **VERIFIED UNCHANGED**, fetched 2026-09-07 (`agents.md`; Codex's own docs at
`learn.chatgpt.com/docs/agent-configuration/agents-md`; GitHub issues #12115, #7138, #13386).

- (a) nested, nearest-file-wins, confirmed on current docs. Issue #12115 (open) asks for *dynamic* reload as
  work moves into a subtree mid-session — a live gap, not a contradiction of the documented behaviour.
- (b) origin of the cross-vendor convention, confirmed; governance detail below (§1.6).
- (c)/(d)/(e): no, no, no — confirmed by documentation silence plus targeted search; no page or changelog
  entry surfaced a contradicting feature.
- **Scale limit, reinforced rather than merely unchanged.** The 32 KiB silent-truncation limit is not just
  still true — it is now a *settled* decision. Issue #7138 (asking for a truncation warning) was **closed as
  not planned**, quoting Codex's own source comment: "Larger files are silently truncated to this size so we
  do not take up too much of the context window." Issue #13386, opened months later reporting the same
  behaviour with no fix, remains open. Codex has decided, twice, not to change this.

### 1.4 Google Gemini CLI `GEMINI.md`

All five cells **VERIFIED UNCHANGED**, fetched 2026-09-07 (`geminicli.com/docs/cli/gemini-md/`,
`google-gemini.github.io/gemini-cli/docs/cli/commands.html`).

- (a) "It loads various context files from several locations, concatenates the contents of all found files" —
  confirmed, no ranking/retrieval described.
- (b) `context.fileName` can be set to include `AGENTS.md` — confirmed.
- (c) `/memory show` is local-only inspection — confirmed; a separate, pre-existing OTel session-telemetry
  feature (tokens/latency/tool-calls) exists but does not measure GEMINI.md-specific exposure, so it does not
  upgrade the "partial" rating.
- (d)/(e): no, no — confirmed.
- One unconfirmed rumour surfaced (a "Gemini CLI → Antigravity CLI" migration story) and is explicitly
  **excluded**: no fetchable primary source, reported by the verifying agent as low-confidence and not used.

### 1.5 Cursor / Cline / Windsurf rules

Cursor's per-rule-firing question was the fourth load-bearing check (advisor priority). Fetched
`cursor.com/docs/context/rules` and `cursor.com/docs/account/teams/analytics` directly, 2026-09-07:

> Team analytics tracks "AI code share in commits, Agent/Tab edits, messages sent, active users, daily usage,
> a usage leaderboard, repository insights, conversation insights... cloud agent usage, and client versions."
> No mention of rule files, rule edits, or which specific rule fired per session/query.

> On the rules docs: "No mention of any system that validates a new or edited rule's description against the
> descriptions of other existing rules to check for overlap, collision, or 'stolen' activation." Conflicts
> addressed are "across rule *precedence*" (Always/Auto-Attached/Agent-Requested ordering), never rules'
> descriptions competing for the same "Apply Intelligently" trigger.

**VERIFIED UNCHANGED, precisely.** Cursor still audits rule *edits* and general usage, never which rule fired
for a given query, and has no corpus-wide collision check either — the same gap Anthropic has, confirmed
independently on a second vendor's current docs.

**Windsurf — a naming correction, not a behavioural one.** `WebSearch` first surfaced a claim that Cognition
(which had already acquired Windsurf) rebranded it to Devin Desktop; per this report's own strict-evidence
rule, that alone isn't a finding. Fetched `https://windsurf.com` directly 2026-09-07 to check: it returns a
**308 Permanent Redirect to `https://devin.ai/desktop`** (server-supplied `Location` header). That much is
now primary-source-confirmed, not search-summary. The specific date (2026-06-02) and the detail that legacy
`.windsurfrules`/`.windsurf/rules/` still work under a preferred new `.devin/rules/` path come only from the
search summary and were **not** independently fetched — reported here as **COULD NOT VERIFY (redirect
confirmed; date and compat-path detail unconfirmed)**, not asserted as fact. A further claimed detail — a new
6,000-character cap on a `global_rules.md` file — rests on the same unconfirmed search summary and is **cut
from this report** rather than reported unverified. What's actually established: "Windsurf" as an independent
product name no longer resolves at its own domain, which redirects to a Cognition/Devin property; the
12,000-character scale-limit claim in `docs/PRODUCT-FOCUS.md` was not re-verified against a primary source
this pass and should be re-checked, not re-cited as-is, before this matrix is next revised. Cline was not
independently re-fetched this pass (budget); no information surfaced that contradicts the original citation.

### 1.6 The `agents.md` convention — governance enrichment, no cell change

Not a distinct row in the 2026-09-06 matrix (it's folded into the Codex citation), but named explicitly in
this task's brief. Fetched `https://agents.md/` directly 2026-09-07: 26 tools listed as compatible (Codex,
Jules, Factory, Aider, goose, opencode, Zed, Warp, VS Code, Devin, Junie, Amp, Cursor, RooCode, Gemini CLI,
Kilo Code, Copilot coding agent, Windsurf/Devin, Augment Code and others), with a "growing ecosystem" link
suggesting more. Fetched `linuxfoundation.org/press/...agentic-ai-foundation` 2026-09-07:

> AGENTS.md, "released by OpenAI in August 2025," "has been adopted by more than 60,000 open source projects
> and agent frameworks." It is one of three founding project contributions to the Agentic AI Foundation
> (AAIF), alongside Anthropic's MCP and Block's goose. Platinum members: AWS, Anthropic, Block, Bloomberg,
> Cloudflare, Google, Microsoft, OpenAI.

This is a real governance shift (announced 2025-12-09, so also predates the 2026-09-06 scan) worth carrying
into positioning: AGENTS.md is now a neutral, vendor-agnostic, heavily-adopted **file-format** standard,
co-governed by the same vendors this matrix treats as competitors. It still does none of (c)/(d)/(e) — it's a
convention, not a product, and has no retrieval, no telemetry, and no CI gate of its own. Guidefold's CLI
already treats `AGENTS.md` as a generated *output* (`materialize`/`index`, per `CLAUDE.md`), not a rival
format — worth stating plainly in positioning rather than leaving implicit.

### 1.7 Google Cloud Agent Registry

All five cells **VERIFIED UNCHANGED**, fetched 2026-09-07 (`docs.cloud.google.com/agent-registry/{overview,concepts,search-agents-and-tools,register-skills}`).

- (a) resource identity is `urn:skill:PUBLISHER_ID:NAMESPACE:SKILL_ID` — project/publisher-scoped, not
  repo-location-scoped. Confirmed.
- (b) A2A/MCP search across agents/skills/MCP servers, still a GCP service. Confirmed.
- (c) no per-skill usage metric on the cited pages; a *different* doc tree
  (`gemini-enterprise-agent-platform/optimize/observability/overview`) has per-**agent** session/invocation
  dashboards, which is adjacent but not what the matrix cell claims or denies. Doesn't change the verdict.
- (d) push-based via `gcloud`/REST; no "pull request," "review," or "approval" language anywhere on the
  registration page. Confirmed.
- (e) only structural/frontmatter validation (size caps, nesting depth); no CI/quality pipeline. Confirmed.
- **Stage:** could not confirm or deny GA for the product overall (release-notes page returned navigation
  only, twice — **COULD NOT VERIFY**), but the specific "search for standalone skills" feature the matrix
  cites is explicitly labelled **"Preview"** with pre-GA terms language, confirmed on the cited page itself.

### 1.8 MCP server registries

Four of five cells **VERIFIED UNCHANGED**; one **CORRECTED**, narrowly.

- (a) "indexes servers, not repo-scoped guidance" — confirmed on `github.com/modelcontextprotocol/registry`
  ("an app store for MCP servers") and `smithery.ai` (18,231+ listed MCP servers, not instruction files).
- (b) cross-harness — confirmed, thinly ("provides MCP clients with a list of MCP servers").
- (c) **CORRECTED for Smithery only.** Fetched `smithery.ai` 2026-09-07: individual server cards show public
  use-counts ("22.49k uses," "43.39k uses"), and a publisher-facing feature: "Observability. See how your
  tools are used," with an example "10.2k calls." The official registry and Docker's catalog show no such
  metric on any fetched page. This is per-**MCP-server** popularity, not per-instruction-file exposure — it
  doesn't touch what Guidefold measures, but the blanket row-level "no" needs a Smithery footnote.
- (d) Docker: "Every pull request requires a review from the Docker team before merging" + passing CI,
  confirmed. Official registry: "we have limited active moderation capabilities... consumers should assume
  minimal-to-no moderation," confirmed (weaker than "reactive denylisting," if anything).
- (e) official registry "deliberately unopinionated," confirmed; still labelled "currently in preview."
  Docker: same PR+CI gate as (d).

### 1.9 Public skill marketplaces

Four cells **VERIFIED UNCHANGED**; one source-citation error found and corrected.

- (a) no repo-location scoping — confirmed; install scope on `tech-leads-club/agent-skills` is a destination
  choice (global vs. local install), not routing by repo path.
- (b) cross-harness — confirmed and *stronger* than cited: `skills.sh` lists 20 named agent targets including
  Claude Code, Cursor, Codex, Copilot, Gemini, each with a dedicated install page.
- (c) **the arXiv citation (2607.00911) does not support the install-count/exposure-bias claim** — the paper
  is about reuse/modification patterns ("53% [of skills] are never modified after adoption"), not install
  counts. The install-count half of the claim is real but should cite `skills.sh` itself, which has a public
  "Skills Leaderboard" ranked by installs (top entry: 3.3M). "Self-reported outcomes" remains
  **unsupported by any fetched source** — drop it or re-source it if this matrix is revised.
- (d) `tech-leads-club/agent-skills` — static analysis, Snyk scan, hash integrity, human review, all
  re-confirmed with quotes; now at 5.1k stars / 469 forks / 1,172 commits, clearly active. `skills.sh` shows
  no formal submission process (absence of evidence on the page, reported as such).
- (e) partial — confirmed, consistent with (d) (varies by marketplace).

### 1.10 Backstage catalog + TechDocs

**Not named explicitly in this task's brief's competitor list, but present as row 10 of the existing matrix
and worth the same rigor.** Four cells verified; the "closest artefact" framing is corrected with a
methodology flag.

- (a) `catalog-info.yaml` + `backstage.io/managed-by-location`, confirmed; TechDocs co-location confirmed via
  a different (current, official) page than originally cited (`backstage.io/docs/features/techdocs/`).
- (b) portal, not an agent mechanism — confirmed, with an addendum: `backstage.io/docs/ai/skills/` shows
  Backstage's own site hand-publishing skills for external agents via a manual PR process into
  `docs/.well-known/skills/index.json` — dogfooding, not a capability any Backstage instance's catalog gets
  for free. An open, uncommented feature request (`backstage/backstage#34318`, opened 2026-05-20) asks for
  exactly the bridge that would close this gap.
- (c) **CORRECTED, nuance not reversal.** `backstage.io/docs/ai/mcp-actions/` documents first-party
  OpenTelemetry tracing (`mcp.server.operation.duration`, `mcp.server.session.duration`) — but for MCP
  tool-call actions, not for the static `AiResource` catalog entities a skill/rule would be. "No first-party
  telemetry of any kind" is no longer accurate; "no first-party **per-skill** usage telemetry" still is.
- (d) no in core — confirmed; the new `AiResource` entity kind (below) goes through the same generic
  catalog PR flow as any other entity, no AI-content-specific review.
- (e) RoadieHQ's entity-validator — unchanged at 81 stars, generic YAML/annotation linting only, no
  AI-content rules.
- **The real finding:** Backstage core shipped an opt-in `AiResource` catalog entity kind (subtypes `skill`,
  `rule`) in **v1.51.0, dated 2026-05-27** — over three months before the original 2026-09-06 scan, which
  missed it. This is a **methodology flag for the original matrix, not a change since yesterday**: it stores
  metadata and a `backstage.io/source-location` reference to skill content, not the content itself, and
  delivers nothing cross-harness, measures nothing per-skill, and gates nothing pre-merge — confirmed via two
  open, unbuilt feature requests (`#34318`, and `#33575` proposing a rename to `AIContext`, opened
  2026-03-25). `JulianPedro/backstage-dev-ai-hub` (the "8-star plugin" the matrix calls the closest artefact)
  is unchanged at **8 stars** and remains the only thing that combines cataloguing + install-tracking +
  cross-harness delivery in one package — but Backstage's own roadmap is now visibly moving toward closing
  that gap, which "no direct competitor found" should describe as a narrowing trend, not a static fact.

### 1.11 `davila7/claude-code-templates` — a real miss, surfaced by the user 2026-09-08, not this pass's own search

Not checked in the original 2026-09-06 matrix or in this report's first pass. The user pasted a search-AI
summary citing an "Agent MD Refactor" skill and a related dev.to article; both were independently re-fetched
2026-09-08 rather than taken from the pasted summary.

**What it is.** `davila7/claude-code-templates` — **27,000–30,192 GitHub stars** (two sources, both fetched
2026-09-08: `getclaudeskills.com/skills/agent-md-refactor-davila7` gives 30,192; a WebSearch summary citing "the
Agent Skills Marketplace site" gives 27,000+ — not reconciled to one number, both far larger than anything
else checked in this report, including `tech-leads-club/agent-skills` at 5.1k). A free, MIT-licensed CLI +
web dashboard (`aitmpl.com`) to "browse and install 1000+ pre-built components for Claude Code" — agents,
slash commands, MCP integrations, hooks, settings — plus a real-time session-monitoring dashboard ("live
state detection and performance metrics," mobile-accessible via Cloudflare Tunnel).

**"Agent MD Refactor," specifically** (fetched `getclaudeskills.com/skills/agent-md-refactor-davila7`,
2026-09-08): a Claude Skill, run on demand inside a session, that reorganizes one bloated `AGENTS.md`/
`CLAUDE.md`/`COPILOT.md` using progressive disclosure: analyze for contradictions → extract only universal
rules into a root file → categorize the rest into topic files (`typescript.md`, `testing.md`, ...) → structure
a root file targeting under 50 lines with links → prune redundant/vague instructions. A companion article
(`dev.to/superorange0707/refactoring-agent-skills...`, fetched 2026-09-08) frames the root cause the same way:
"multiple skills loading simultaneously and consuming the shared context window" — regrouping skills by
workflow stage, not just trimming one file.

**Where it lands on the five axes:** (a) no repo-location scoping beyond what Claude Code's own nested
`.claude/skills/` already provides (§1.1) — it edits content, it doesn't add a routing mechanism; (b) Claude
Code only, no cross-harness delivery; (c) the monitoring dashboard is real-time and richer-looking than
`/skill-doctor`, but still per-developer/per-session, not an owner-level cross-repo aggregate; (d)/(e) no
pre-merge collision detection between two different skills' descriptions, no CI quality gate — it is a manual,
on-demand authoring aid, invoked by the individual author on their own files. It belongs in the same category
as row 9 (public marketplaces: `tech-leads-club/agent-skills`, `skills.sh`) — install/browse plus, here,
content hygiene — just an order of magnitude more popular than either.

A fourth item the pasted summary named, "Extract: AI Code Refactoring Skill" (`mcpmarket.com/tools/skills/
refactor-extract`), could not be independently fetched (HTTP 429, 2026-09-08) — excluded from this report per
its own no-unverified-claim rule. Its own listed description ("decomposes large **source files** into modular,
single-responsibility **components**") is about application source code, not `SKILL.md`/agent-instruction
files, and is very likely a keyword-match false positive from the search summary that surfaced it, not a
fourth competitor in this space — noted here only so the omission isn't silent.

**Net effect on the report's conclusions: reinforces them, doesn't change them.** This is the fourth
individual-developer-facing tool found in this space (after Cursor/Cline/Windsurf rules, the marketplaces in
§1.9, and Claude Code's own native features) — `docs/PRODUCT-FOCUS.md`'s framing that "the individual developer
on a single repository with a single harness... vendors will solve that themselves" is, if anything, better
evidenced now: at 27k+ stars, a vendor-adjacent community tool already has, and popularly, solved single-file
instruction hygiene for individual Claude Code users. It does not touch cross-harness delivery, repo-location
governance across many authors, pre-merge collision detection across a corpus, or organizational consolidation
with provenance — Guidefold's actual claimed ground (§4). The one genuinely complementary angle, worth stating
in a demo rather than treating as a threat: Guidefold's own skill-directory convention (`references/`,
`scripts/`, `assets/` under a skill, `docs/CONVENTIONS.md`) already rewards exactly the progressive-disclosure
structure this tool retrofits by hand — an author who keeps individual files lean makes Guidefold's own
retrieval budget (`budget.max_cards`, §API-CONTRACT) work better, not worse. The two are additive: one keeps a
single author's one file lean; the other finds, ranks and governs the right ≤4 files across many authors, many
repos and several harnesses. Neither replaces the other.

---

## 2. Rows that changed (the honest summary)

1. **Anthropic (a)** — the single most important correction. Claude Code has real nested, path-scoped skill
   discovery (`.claude/skills/` at arbitrary depth, a `paths` glob field, directory-qualified collision
   naming). "No path or glob scoping" was wrong. This is a **positioning-blocking finding**: it forces the
   whole "we scope by location and nobody else does" framing to be rewritten as a cross-harness/multi-repo
   governance claim, not a location-scoping-invented-here claim.
2. **Copilot (b)** — understated. The Copilot coding agent (not the CLI) natively reads AGENTS.md, CLAUDE.md
   *and* GEMINI.md alongside its own formats, since August 2025 — a real but single-surface, no-precedence,
   no-ranking convergence at the file-format layer.
3. **Backstage's "closest artefact" framing** — Backstage core shipped a first-party `AiResource` entity kind
   in May 2026 that the original scan missed; it doesn't close any of the three gaps (delivery, measurement,
   pre-merge review) but shows the direction of travel.
4. **MCP registries (c)** — Smithery specifically shows public per-server usage counts and a publisher
   "Observability" feature; the official registry and Docker's catalog still show none. Row-level "no" needs
   a one-vendor carve-out.
5. **Windsurf, as a name** — acquired and rebranded to Devin Desktop (2026-06-02); the 12,000-character
   scale-limit claim is mechanically still true but now describes legacy-compat behaviour inside a different
   product.
6. **Guidefold's own row, (d) and (e)** — not a competitor row, but the most consequential change found in
   this pass. See §3.

Two items marked **COULD NOT VERIFY** and excluded from any claim: Google Cloud's platform-wide GA status
(nav-only fetch, twice), and Port.io's scorecard-MCP page (404, twice).

## 3. Guidefold's own row moved since 2026-09-06 — and the tracking issues haven't caught up

`docs/PRODUCT-FOCUS.md`'s Guidefold row says, for 2026-09-06: "per-PR collision report and trigger
suggestions (PR #65); **F5-in-`validate` pending (#86)**" and "`validate`; structured-corpus parity 0/243
(PR #67); **E7.5 snapshot gate pending (#87)**."

Both are no longer pending. Commit `68dbf2c` (PR #120, "Authoring loop, part 2: `validate --suggest` +
`guidefold eval` quality gate (E7.5)") shipped:

- `guidefold validate --suggest --json` — deterministic, local trigger/negative-trigger suggestions, verified
  byte-identical against the pre-change CLI on the default (no-flag) path (`docs/CONVENTIONS.md` §13).
- `guidefold eval --queries <dir|yaml|jsonl> [--gate] [--write-baseline]` — runs every query through the real
  product path (`policy_filter → candidates → score → select(admissible=…)`), reporting retrieval metrics
  (hit@1, recall@k, nDCG@10) and injection metrics (completeness@k, all_required@k, distractor_rate@k,
  abstention precision/recall/coverage) from the *same* injected set the agent would actually receive.

Wired as a real, hard-blocking CI gate: this repo's own `.github/workflows/ci.yml` runs a `golden-eval` job
(`guidefold eval --gate` against `docs/reports/golden/eval-baseline.json`); `templates/ci.yml` — the file a
consumer monorepo copies — has the matching `quality-gate` job (`--gate` on a PR, `--write-baseline` committed
back on a push to the default branch). Confirmed present with `grep` in both files.

**But the GitHub issues these two AC items map to are still open.** `gh issue view 86` →
`{"state":"OPEN", "title":"B2 — F5 trigger and negative-trigger suggestions inside guidefold validate"}`;
`gh issue view 87` → `{"state":"OPEN", "title":"B3 — E7.5: the frozen dev set runs on every index build..."}`
— checked 2026-09-07. `#120`'s own PR body cross-references both by number and closes their stated acceptance
criteria, but neither issue is marked closed on GitHub. Net effect for this report: the *code* is more mature
than the 2026-09-06 matrix says, but the *tracked backlog* (which ADR-0029 rule 4 makes the source of truth
for "what is next") hasn't been updated to reflect it — a bookkeeping gap the team should close, separate
from this report.

## 4. What's genuinely and defensibly ours

The intersection of (a) implemented and tested per `docs/PIVOT-IMPLEMENTATION.md` §b today and (b) not
matched by any competitor verified above:

1. **Cross-harness delivery of one retrieval-ranked answer from one governed source.** Claude Code's nested
   skills and Copilot's `applyTo` globs are both real location scoping — but each is single-harness, authored
   by hand per directory in that harness's own format. Nobody verified here delivers the *same* ≤4-card,
   scope-ranked answer to whichever of several harnesses a developer happens to be running, from one git
   source of truth. Guidefold's SEARCH/USE service and two harness installers (P09/P10) implement this and
   are unit/API-tested; **P10's real-session proof is explicitly out of scope of every session that produced
   PIVOT-IMPLEMENTATION.md** — no design partner, no real Claude Code/Copilot CLI session on a partner repo.
   One nuance the installer's own code already states plainly (checked directly in
   `skills/guidefold/scripts/guidefold`, not asserted from the PRD): the two installers are not symmetric.
   The `claude` harness writes a session hook, so retrieval is automatic. The `copilot` harness writes an
   explicit-workflow block into `.github/copilot-instructions.md` whose own body says, verbatim, "Copilot CLI
   does not inject them automatically here, so load them explicitly before acting on an unfamiliar area,"
   followed by the literal `guidefold find`/`guidefold load` commands to run — matching a second in-code
   comment, "Copilot CLI has no such hook, so it stays explicit find/load." This is an honest, deliberate
   design choice, not a bug — §1.2 confirms Copilot CLI is on a wholly separate `.agent.md` format from
   `.github/copilot-instructions.md` and doesn't auto-load either — but it means the cross-harness claim
   today is "automatic in Claude Code, explicit-workflow in Copilot CLI," not "automatic in both." Say that
   precisely in a demo rather than letting "cross-harness" imply uniform automation it doesn't yet have.
2. **Corpus-wide pre-merge collision/trigger feedback, now on two independent legs.** Confirmed, on Anthropic's
   own current docs (§1.1) and independently on Cursor's own current docs (§1.5), that neither vendor
   automates "this new/edited description takes queries from skill X" — both recommend manual testing.
   Guidefold's `skill-authoring-report` CI job (PR #65) plus `validate --suggest` and `eval --gate` (PR #120,
   §3) do this automatically, dogfooded in this repo's own CI. The gap: `docs/PIVOT-BACKLOG.md` issue #88
   ("measure whether skill authors actually act on the collision comment") is open — the mechanism is real,
   its behavioural effect on authors is unmeasured.
3. **Cross-sibling-scope consolidation with named abstention, not just dedup.** P08
   (`internal/review/generator/{consolidation,layer}.go`, tests: `consolidation_test.go`, `p08_test.go`,
   `family12_test.go`, plus a live-stack acceptance run `test_p08_pyramid.py`) groups a parent scope with its
   direct children, proposes a shared procedure at the deepest common ancestor with `derived_from`/`refines`
   provenance in both directions, infers a `knowledge_layer ∈ {atomic, task, abstract}` axis
   (`origin: inferred`, owner-overridable to `origin: human`), and **names a reason for every rejected
   candidate pair** (e.g. `contradictory_steps`, `consolidation_sources_insufficient`) rather than silently
   skipping it. Nothing verified in this pass does any part of this: marketplaces dedupe by near-verbatim
   reuse (53% of reused skills are never modified, per the arXiv paper checked in §1.9 — that's copy
   detection, not consolidation with provenance); Backstage's new `AiResource` entity references content, it
   doesn't infer a layer or propose a merge; nobody else has an abstention taxonomy at all. **Caveat
   required, per `docs/PIVOT-BACKLOG.md`'s own rule**: the fixture this is tested on
   (`examples/monorepo/docs/runbooks/README.md`) is *planted* — it is R-evidence that the rule behaves
   correctly, never recall-evidence that P08 finds real duplicate knowledge in a messy real repository. That
   evidence does not exist yet.
4. **An owner-level, cross-harness telemetry ledger design** (`internal/usage`: exposures, loads with
   `context_loaded` confirmation, helped/hindered feedback, a "zero-loads" owner queue) that is structurally
   different from every competitor checked here — `/skill-doctor` is per-developer/per-session (§1.1),
   Cursor's dashboards don't reach the rule level (§1.5), MCP registries measure servers not instructions
   (§1.8). It is implemented and unit/API-tested. It has **never processed a single real developer's data**
   (`docs/PRODUCT-FOCUS.md`'s own words, unchanged) — the mechanism is ours to claim; the value is not yet
   ours to claim.

## 5. Honest gap list

- **No design partner.** Issue #78 ("A1 — Agree the design partner") is open, checked 2026-09-07 via
  `gh issue view 78`. `docs/PRODUCT-PIVOT.md`'s own "Design partner" section is an empty template. Every
  customer-outcome, ROI, or retention claim anywhere is unevidenced — there is no pilot to have produced one.
- **No real WorkOS credentials.** `identity.ModeWorkOS` and its tests exist; a dev provider substitutes
  locally (`PIVOT-IMPLEMENTATION.md` §h.1).
- **P10 has no real harness session.** Claude Code/Copilot CLI installers are unit-tested against the
  Meridian fixture only; no real developer, real repo, real harness session exists (§h.2, §h.5).
- **The worker container has never actually been built.** `Dockerfile.worker` and its Helm template pass 39
  static tests; `docker build` has never run for real in this environment (§h.3).
- **U4 AC2 (10k-skill catalog, p95 ≤ 2s "in the pilot network") is measured on loopback only** — 104.5 ms
  locally, which is not evidence about a pilot network (§h.4).
- **P08's own recall is unmeasured.** As stated in §4.3: the consolidation rule is proven correct on a planted
  fixture, never tested for recall/precision against real, messy, duplicated knowledge.
- **Local acceptance-run artifact is currently inconsistent with what `PIVOT-IMPLEMENTATION.md` cites.** That
  document quotes `.guidefold/checks/acceptance-2026-09-07.md` as "40 rows — 30 pass, 3 fail... 7
  `not_measured_here`"; the copy of that file on disk when this report was written instead reads "1 pass · 0
  fail · 0 `not_measured_here`". The file is gitignored and locally regenerable, so this is most likely a
  re-run since that document was written, not a contradiction of it — but it means the acceptance evidence
  should be re-confirmed, not re-cited, before anyone leans on it. Not resolved in this report; flagged for
  the team.
- **Tracking-issue lag.** §3: two acceptance-criteria items shipped in code and CI are still open issues on
  GitHub — the backlog that ADR-0029 rule 4 names as the source of truth is behind the code.
- **The Copilot installer isn't automatic yet.** §4.1: `guidefold install --harness copilot` writes an
  explicit find/load workflow into `.github/copilot-instructions.md`, not a hook — Copilot CLI has no
  automatic-injection point Guidefold can target today. The `claude` harness is automatic; the `copilot`
  harness requires the developer or agent to run `guidefold find`/`guidefold load` by hand. "Cross-harness"
  is real; "automatic in every supported harness" is not, yet.

## 6. Kill-criterion check

`docs/PRODUCT-FOCUS.md`'s own kill criteria table: "A vendor ships cross-harness, location-scoped retrieval
with pre-merge author feedback → the differentiator is gone. Re-scope to the authoring loop alone, or stop."

**Verdict: not fired.** No single vendor checked in this pass combines all three:

- Anthropic: strong location-scoping (§1.1, corrected), zero cross-harness, and pre-merge feedback that is
  real for frontmatter/schema (`claude plugin validate --strict`) but explicitly manual, not automated, for
  description collisions.
- Copilot: narrow cross-format *reading* (one surface, no ranking, no precedence contract, concatenation not
  retrieval), no pre-merge feedback.
- Codex / the `agents.md` convention: real cross-harness reach, concatenation/truncation instead of retrieval,
  no pre-merge feedback of any kind.
- Marketplaces: real cross-harness install adapters, no location-scoping, generic security scanning (Snyk,
  hash integrity) rather than corpus-wide description-collision feedback.

The criterion is close on one axis (Anthropic's location-scoping) and far on the other two for every vendor
checked. It has not fired, but it is no longer a comfortable margin on that first axis — see the positioning
change this forces, below.

## 7. Positioning recommendation

**Do not lead with "we scope skills by repo location."** That claim, alone, is now matched by Claude Code
itself for the single-harness case, confirmed against its current docs. Leading with it invites the buyer's
first question — "doesn't Claude Code already do this?" — and to a platform team running multiple harnesses
over one monorepo, the honest answer is now "yes, for Claude Code."

**Lead with the thing no vendor checked here does at all, twice-confirmed: nobody tells a skill/rule author,
automatically, corpus-wide, before merge, that their new text steals another skill's queries.** Anthropic
recommends manual testing; Cursor's own docs say the same; Codex and Gemini CLI don't scope triggering at all
(they concatenate); no marketplace reviews for this. Guidefold's CI job does it today, dogfooded on this
repo's own PRs (PR #65, then #120's `--suggest`/`--gate`) — that is a real, shipped, tested claim, not a
promise.

**Second, lead with cross-harness delivery of one governed answer, reframed as a governance claim, not a
discovery-mechanics claim:** the platform team's actual job to be done (`docs/PRODUCT-PIVOT.md`) is that an
agent standing in `platforms/atlas/identity/turnstile/` gets the org's rules *for that location*, in
*whichever harness the developer opened*, without anyone hand-maintaining a per-harness copy. Claude Code
solves this within Claude Code. Copilot's coding agent partially solves it by unilaterally reading three
other vendors' file formats on one surface. Nobody solves it *as a managed, owner-accountable layer over many
repos and several harnesses at once* — which is the platform team's actual problem, not any single
developer's.

**Third, offer P08 (cross-sibling consolidation with named abstention) as the concrete "why now" hook**,
exactly as the owner already scoped it as the killer use case — but state its evidence honestly: implemented,
tested, correct on a planted fixture; recall on real duplicated knowledge is unmeasured, and say so in the
same sentence, not in a footnote.

**Do not claim, or imply, any customer outcome, adoption number, or time saved.** There is no design partner
and no pilot (§5). Every number in this report that looks like traction (60,000 AGENTS.md adopters, 3.3M
skill installs, 5.1k GitHub stars on a marketplace) describes the *market*, not Guidefold's place in it — say
that distinction out loud when this report's numbers get reused in a deck.

**Open question for the human, not folded into this recommendation** (per `scope-change-protocol`, this task's
own instruction not to relitigate the customer): nothing surfaced in this pass suggests the individual-developer
segment is more attractive than the platform-team segment — if anything, Anthropic's and Cursor's own
single-repo/single-harness features (§1.1, §1.5) look more mature exactly where three vendors were already
expected to "solve that themselves" (`docs/PRODUCT-FOCUS.md`). No scope-change flag is being raised here.

## Sources

Anthropic: https://code.claude.com/docs/en/skills (fetched 2026-09-07) ·
https://code.claude.com/docs/en/monitoring-usage (2026-09-07) ·
https://code.claude.com/docs/en/hooks (2026-09-07) ·
https://code.claude.com/docs/en/plugins-reference (2026-09-07, via claude-code-guide agent) ·
https://code.claude.com/docs/en/skills.md — skill-doctor / skill-creator A/B sections (2026-09-07, via agent).
GitHub Copilot: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions (2026-09-07) ·
https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli (2026-09-07) ·
https://docs.github.com/en/copilot/concepts/agents/hooks (2026-09-07) ·
https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/ (2026-09-07).
OpenAI Codex: https://agents.md/ (2026-09-07) ·
https://learn.chatgpt.com/docs/agent-configuration/agents-md (2026-09-07) ·
https://github.com/openai/codex/issues/12115, /13386, /7138 (2026-09-07).
Google Gemini CLI: https://geminicli.com/docs/cli/gemini-md/ (2026-09-07) ·
https://google-gemini.github.io/gemini-cli/docs/cli/commands.html (2026-09-07).
Cursor/Windsurf: https://cursor.com/docs/account/teams/analytics (2026-09-07) ·
https://cursor.com/docs/context/rules (2026-09-07) · WebSearch, Windsurf→Devin Desktop rebrand (2026-09-07).
`agents.md` governance: https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation (2026-09-07).
Google Cloud Agent Registry: https://docs.cloud.google.com/agent-registry/overview, /concepts,
/search-agents-and-tools, /register-skills (all 2026-09-07) ·
https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes — fetch failed, nav only (2026-09-07).
MCP registries: https://github.com/modelcontextprotocol/registry (2026-09-07) ·
https://registry.modelcontextprotocol.io/ (2026-09-07) ·
https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/{about,moderation-policy}.mdx (2026-09-07) ·
https://github.com/docker/mcp-registry/blob/main/CONTRIBUTING.md (2026-09-07) · https://smithery.ai/ (2026-09-07).
Marketplaces: https://github.com/tech-leads-club/agent-skills (2026-09-07) · https://skills.sh (2026-09-07) ·
https://arxiv.org/abs/2607.00911 (2026-09-07, re-checked — does not support the exposure-bias claim it was
cited for).
Backstage: https://backstage.io/docs/features/software-catalog/descriptor-format/ (2026-09-07) ·
https://backstage.io/docs/features/techdocs/ (2026-09-07) · https://backstage.io/docs/ai/skills/ (2026-09-07) ·
https://backstage.io/docs/ai/mcp-actions/ (2026-09-07) ·
https://github.com/backstage/backstage/issues/34318, /33575 (2026-09-07) ·
https://roadie.io/backstage-weekly/135-v1-51-0-airesource-kind-scaffolder-4/ (2026-09-07) ·
https://github.com/RoadieHQ/backstage-entity-validator (2026-09-07) ·
https://github.com/JulianPedro/backstage-dev-ai-hub (2026-09-07) ·
https://docs.cortex.io/standardize/scorecards (2026-09-07) ·
https://docs.port.io/guides/all/build-port-scorecards-with-mcp/ — fetch failed, 404 twice (2026-09-07).
Guidefold internal: `docs/PIVOT-IMPLEMENTATION.md` (2026-09-07) · `docs/CONVENTIONS.md` §13 (F5/E7.5) ·
commit `68dbf2c` / PR #120 · `.github/workflows/ci.yml` (`golden-eval` job) · `templates/ci.yml`
(`quality-gate` job) · `services/search/internal/review/generator/{consolidation,layer}.go` and their tests ·
`gh issue view 78/86/87/88/106/111` (2026-09-07, `wiatrM/guidefold`).
