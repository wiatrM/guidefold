# Guidefold — project instructions

Git-native skill CI for a monorepo. Skills (`SKILL.md` dirs) live next to the code they govern,
CI validates and publishes them to Google Cloud Agent Registry, and one bootstrap skill + a tiny
CLI let any harness (Claude Code, Copilot CLI, Codex, Gemini CLI) discover them by location.

Project entry point: [AGENTS.md](AGENTS.md). Local workflows: [product changes](.agents/skills/guidefold-product-changes/SKILL.md) and [UI workflow](.agents/skills/guidefold-ui-workflow/SKILL.md).
Thirty rule skills (product direction, KISS/YAGNI/DRY/SOLID, hexagonal architecture, Definition of Done, review, UI) are indexed in `AGENTS.md`, linked from `.claude/skills/`, and decided in [ADR-0032](docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md). Hooks in `.claude/settings.json` are described in [.claude/README.md](.claude/README.md).

Start with `docs/DOCUMENTATION-RULES.md` to select the authoritative document for the task.
For the authorized product pivot, read `docs/PRODUCT-PIVOT.md` (requirements),
`docs/PIVOT-ARCHITECTURE.md` (system boundaries), `docs/PIVOT-BACKLOG.md` (order),
and `docs/PIVOT-REVIEW.md` (rationale). Their Proposed status does not cancel a task the user
has already authorized; it also does not prove that planned behavior is implemented.
For existing CLI behavior, read its code/tests plus `docs/DESIGN.md` and `docs/CONVENTIONS.md`.
For hosted UI, use `docs/ui/IA.md`, `UX.md`, `UI.md` and the relevant entry in
`docs/ui/pipeline/README.md`; do not restore the former four-section local UI.
Decisions are recorded in `docs/adr/`. `docs/ASSESSMENT.md` records dated registry API evidence;
verify time-sensitive claims before relying on them.

## Mandatory Spectrum UI components

Owner instruction, 2026-09-09: **Spectrum UI components are mandatory for new, redesigned or migrated Guidefold UI.** Read [.agents/skills/spectrum-ui-workflow/SKILL.md](.agents/skills/spectrum-ui-workflow/SKILL.md) before implementation. Browse/search the [Spectrum MCP registry](https://ui.spectrumhq.in/docs/mcp), inspect actual source/dependencies, install the matching item and verify behavior. Do not substitute a handmade lookalike when a suitable component exists. Record a concrete exception for missing or framework-incompatible items. This overrides the older shadcn/Tailwind prohibition for this integration, not security, accessibility or deployment authority. Whole-registry access is not blanket installation or compatibility certification.

## Mandatory Spectrum Charts migration

Owner instruction, 2026-09-09: **migrate ALL existing telemetry visualizations and charting to actual Spectrum UI Charts; use Spectrum for all new charts and metric cards.** Read [spectrum-charts-migration](.agents/skills/spectrum-charts-migration/SKILL.md) and follow the canonical acceptance requirements in [UI §7](docs/ui/UI.md#7-obowiązkowa-migracja-spectrum-charts). This includes pie/donut, trends, distributions and sparklines, with the chart type matched to the data. Preserve telemetry semantics, tenant isolation, unknown-versus-zero and accessibility. Do not rewrite backend collection/storage into a UI library. A written requirement or installed component is not a completed migration.

## Mandatory shadcn console (2026-09-12)

Owner instruction, 2026-09-12: **the management UI (every route after sign-in) is built on shadcn/ui primitives** (`ui/src/components/ui/*`, base-nova style on Base UI, installed with the pinned `pnpm exec shadcn`), composed through the public components in `ui/src/components/*` and Spectrum items where they fit. Every view leads with a large `IconTile`; the console follows the quickstart clarity of a documentation site, not a dense admin table. Values still come only from `ui/src/tokens/tokens.css` (shadcn semantic tokens are references into the Industrial Surveyor palette; `ui/src/registry.css` maps them into Tailwind). This lifts the earlier "no component library" rule for `ui/`; security, accessibility, honesty of states and the data boundary stay binding. Record: [docs/reports/ui/console-shadcn-20260912.md](docs/reports/ui/console-shadcn-20260912.md).

## Positioning: what we sell

Owner decision, 2026-09-09. Binding on every piece of marketing copy, the
landing page, the README intro and any deck. Full version:
[guidefold-positioning](.agents/skills/guidefold-positioning/SKILL.md).

We do not sell "team rules right where agents work". That is generic and says
nothing. We sell the problem a large organisation has:

- roughly **30,000 skills** across many repositories and a monorepo, in many
  folders, every team writing its own,
- **duplication** of the same rule in several places,
- no **management**: nobody can see the whole set,
- **extraction of knowledge into the organisation's pyramid**, from the specific
  up to the general.

Guidefold solves and automates that: the **search and USE** service, **harness
integration**, and **automatic CI**.

A reader has five seconds to learn the pain and what we solve. The rest of the
text is secondary. The landing page runs in one column, hero first; the
two-column layout was rejected by the owner.

## Repository layout

| Path | What |
|------|------|
| `skills/guidefold/` | **The distributable unit.** Bootstrap `SKILL.md`, `scripts/guidefold` (CLI), `hooks/*.json` (harness hook templates). This whole dir is what a consumer monorepo copies to `.agents/skills/guidefold/`. |
| `docs/` | Product requirements, architecture, backlog, documentation rules, CLI conventions, ADRs and evidence. |
| `docs/ui/` | Hosted U4 information architecture, UX, visual system and reviewed pipeline 00–08. Read each file's current status; a prototype is not the API implementation. |
| `templates/` | Files a consumer monorepo copies: CI workflow, example `guidefold.yaml`. |
| `examples/monorepo/` | "Meridian" playground: fictional Palantir-style data platform, 17 declared nodes / 27 SKILL.md files including the hierarchy index at the pivot baseline / stub code, `registry.backend: local`. Fixture for demos and tests. |
| `tests/` | Existing pytest suite; use the checks appropriate to the changed behavior. |
| `services/search/` | Product-pivot Go modular monolith: API + worker. `internal/{identity,mgmt,jobs,worker,schema,testdb,importer,knowledge,review,usage,graph,pivottest}` (ownership per module in `services/search/internal/README.md`); `openapi/management-v1.yaml` is the OpenAPI half of the contract. |
| `tools/dev/` | Local dev loop with no Docker/sudo: `pg.py` (non-root Postgres 18), `stack.py` (builds `guidefold-search`, runs migrate/serve/worker, optional `pnpm dev` UI). |
| `tools/worker/` | `build_tree.py`, used only by the worker container for `import.parse` (needs Python3 + PyYAML; the API image stays Python-free). |
| `tools/contract/` | `check_api_contract.py`: the contract-first drift checker (doc vs OpenAPI vs Go code). |
| `tests/acceptance/` | End-to-end acceptance scenarios for ACT-01 against a running stack; report lands at `.guidefold/checks/acceptance-<date>.json`. |
| `ui/` | React/Vite hosted UI: seven views, fixture and API `DataSource` modes; see `ui/README.md` for per-view coverage. |

Two repos are involved and must not be confused: **this repo** (the tool) and the **consumer
monorepo** (where `guidefold.yaml`, `.agents/skills/**`, generated `AGENTS.md` cards and the
CI workflow live). `templates/` and `skills/` are copied into the consumer; nothing else is.

## Existing CLI constraints

- `scripts/guidefold` stays a **single-file Python 3 script, stdlib + PyYAML only**. It ships
  inside the skill ZIP, so no package layout or additional runtime dependencies. This constraint
  applies to the distributable CLI, not the proposed Go API/worker or React UI.
- Git is the source of truth; the registry is a build artifact (ADR-0001). Never design a
  flow that edits the registry by hand.
- Generated consumer files (`AGENTS.md`, `CLAUDE.md`/`GEMINI.md` one-liners, `.github/instructions/*`,
  `_index-hierarchy` skill) are produced only by `guidefold materialize` / `index`.
- Scope cards are capped at 80 lines. Digests only, no procedures.
- All registry access goes through the `Registry` class in the CLI so it can be swapped for
  MCP or an ARD endpoint later (ADR-0003).
- Preview API: `gcloud alpha agent-registry skills ...` — pin the gcloud version in CI.
- For `services/search`, `ui/`, and the CLI's network commands: `docs/API-CONTRACT.md` is binding
  and comes before code — do not add a handler, DTO, table, or CLI network command without a
  contract entry in the same change; `tools/contract/check_api_contract.py` enforces this.

## Working here

- Run the CLI: `cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold <cmd>`.
  The monorepo root is the nearest ancestor with `guidefold.yaml` (or `$GUIDEFOLD_ROOT`).
- Real registry: GCP project `guidefold-test-b6a18a`, location `global`, needs
  `roles/agentregistry.admin`. Publish flow and ID mapping: `docs/adr/ADR-0008-*.md`.
- Tests: `pytest` from repo root. Registry calls must be mocked; never
  hit GCP in unit tests.
- Syntax check: `python3 -m py_compile skills/guidefold/scripts/guidefold`.
- New decision → new `docs/adr/ADR-000N-<slug>.md` (same format as existing ones).
- Keep `docs/DESIGN.md` and `docs/CONVENTIONS.md` in sync with the CLI's behavior.
- Update the canonical document and its affected consumers in the same task; use the new-file
  and evidence rules in `docs/DOCUMENTATION-RULES.md`. Preserve unrelated work and do not commit
  when the user requested uncommitted review.
- Go toolchain (product pivot): `export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH`, then
  `cd services/search && go vet ./... && go test ./...`. `go test -race ./...` and the database
  tests use a local Postgres via `internal/testdb`, not a shared server — no separate service to
  start by hand. `tools/dev/pg.py` and `tools/dev/stack.py` run the same stack for manual checks.
  Route pytest output for the pivot suites through `rtk proxy` when the default hook garbles it
  (e.g. `rtk proxy python3 -m pytest tests/ -q`).
- Pivot implementation status vs. P01–P15: `docs/PIVOT-IMPLEMENTATION.md`.

## Evaluation corpora (rule since 2026-09-05)

- **Routing-quality claims are measured only on real, labelled corpora**, run through the product
  path (`policy_filter → candidates → score → select(admissible=…)`). The 26-skill Meridian fixture
  and its 220-query golden set are the CI **dev/regression** suite, not evidence for model or
  configuration choices — gains on it reversed on a held-out half (PR #19).
- Corpora are pinned by HuggingFace revision and per-file SHA-256 in
  `docs/reports/bakeoff/validation/corpora-manifest.json`; fetch and verify with
  `python3 tools/eval/corpora.py fetch` (needs `huggingface_hub`, e.g. `~/.cache/guidefold/gpu-venv`).
  Data lives under `~/.cache/guidefold/corpora/` and is never committed.
- `tests/test_corpora.py` skips the corpus checks where the cache is absent (CI). A skip is
  "not measured here", not a pass.
- Local unlabelled corpora under `experiment/` (gitignored) are for scale/size/latency only.

## Naming

- Node: dotted path from `guidefold.yaml` (`atlas.identity.turnstile`); root is `_root`.
- URN: `urn:skill:<publisher>:<node>:<skill-name>` — derived, never hand-written.
- Skill `description` starts with `[<node/path>]`; root uses `[<publisher>]` (the `publisher`
  value from `guidefold.yaml`) — never a hard-coded organisation name.

## Earlier skill references

Use skills actually available in the current session. This table records earlier references, not a guarantee that those global skills are installed; project workflows are linked above.

| Skill | Repo | Use for |
|-------|------|---------|
| `skill-creator`, `skill-development` | anthropics/skills, anthropics/claude-code | authoring/reviewing `SKILL.md`, frontmatter rules `validate` must enforce |
| `agent-platform-skill-registry` | google/skills | Google's own skill for the Skill Registry API (search/upload/revisions/LROs) — cross-check with `gcloud alpha agent-registry` |
| `gcloud` | google/skills | safe `gcloud` invocation patterns, auth, `--format` flags |
| `hook-development` | anthropics/claude-code | `SessionStart`/`UserPromptSubmit` hook contract for the `hook` subcommand |
| `python-testing-patterns` | wshobson/agents | pytest fixtures, mocking `subprocess`, tmp repos |
| `github-actions-templates` | wshobson/agents | the consumer CI workflow in `templates/` |
| `create-agentsmd`, `copilot-instructions-blueprint-generator` | github/awesome-copilot | reference for `materialize` output (AGENTS.md, `*.instructions.md` with `applyTo`) |
| `architecture-decision-records` | wshobson/agents | new ADRs in `docs/adr/` |
| `mermaid-diagrams` | softaworks/agent-toolkit | diagrams in `docs/DESIGN.md` |
| `mcp-builder` | anthropics/skills | Phase 2+ MCP server, if the registry never exposes skill tools |

Other earlier references: `superpowers:*` (brainstorming, tdd, writing-plans), `tdd`, `codebase-design`, `writing-great-skills`, `setup-pre-commit`.
