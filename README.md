# Guidefold

**Git-native skill CI for a monorepo.** Agent Skills (`SKILL.md` directories) live next to the
code they govern. CI validates them, detects drift against code changes, and publishes each one
as an immutable revision in Google Cloud Agent Registry. One bootstrap skill and a tiny CLI let
any local harness — Claude Code, GitHub Copilot CLI, Codex, Gemini CLI — discover the right
guidance for *where it is* in the monorepo, general → specific, in at most two tool calls.

Status: **design v0.2, CLI working end to end (2026-09-04).** All 27 playground skills are published
to the test registry (GCP project `guidefold-test-b6a18a`, location `global`) and `find` / `hook` /
`load` / `prewarm` work against it and against the local backend. See `docs/ASSESSMENT.md` for the
verification log and `docs/adr/ADR-0008..0010` for the decisions it forced (proposed, not yet accepted).

## Repository layout

```
guidefold/
├── CLAUDE.md                     # instructions for Claude Code working in this repo
├── docs/
│   ├── MVP.md                    # 8-week MVP: storage decision, epics, user stories, plan, kill criteria  ← start here
│   ├── KNOWLEDGE-DESIGN.md       # knowledge layer v0.1: lifecycle, gates, SkillPyramid induction, models (storage revised in MVP.md)
│   ├── AGENT-SKILLS-RESEARCH.md  # research registry: papers, models, datasets, Router 0.1 plan
│   ├── DESIGN.md                 # design doc v0.3: 2k+ skill model, index, router pipeline, caching, lift, demo UI
│   ├── archive/DESIGN-v0.2.md    # previous design (the design partner-era assumptions)
│   ├── CONVENTIONS.md            # guidefold.yaml, skill layout, URN naming, frontmatter, CI checks
│   ├── ASSESSMENT.md             # viability check of the design against verified facts
│   ├── AGENT-SKILLS-RESEARCH.md  # living registry: papers, models, datasets, code and Guidefold decisions
│   ├── Guidefold-Agent-Skills-Research-2026-09-04.pptx  # technical/product research deck
│   ├── Guidefold-Agent-Skills-Research-Prosto-PL-2026-09-04.pptx  # 60-slide beginner-friendly Polish deck
│   └── adr/ADR-0001..0010.md     # 0001–0007 accepted; 0008 identity, 0009 retrieval, 0010 flat metadata: proposed
├── skills/guidefold/             # THE DISTRIBUTABLE UNIT — copied into a consumer monorepo
│   ├── SKILL.md                  # bootstrap skill (find → load workflow for agents)
│   ├── scripts/guidefold         # single-file Python CLI (stdlib + PyYAML)
│   └── hooks/                    # hook templates: claude.settings.json, codex.hooks.json, copilot.hooks.json
├── templates/
│   ├── github-workflows-skills.yml   # consumer CI: validate/materialize --check/drift on PR, publish on main
│   └── guidefold.example.yaml        # example hierarchy map
├── examples/monorepo/            # "Meridian" playground: 17 nodes, 26 skills + index, generated cards — fixture for demos and tests
├── examples/PLAYGROUND_SPEC.md   # how the playground was authored; use it to add nodes/skills consistently
└── tests/                        # (planned) pytest suite with mocked registry
```

## How it fits together

| Layer | Mechanism | Decided by |
|-------|-----------|-----------|
| L0 scope cards | generated `AGENTS.md` per hierarchy node (+ `CLAUDE.md`/`GEMINI.md` one-liners, `.github/instructions/*.instructions.md` with `applyTo`) | the harness, by path — no model decision |
| L1 prompt-time find | `UserPromptSubmit`/`SessionStart` hook runs `guidefold hook`, injects top-3 skill cards | deterministic, per prompt |
| L2 load on demand | agent runs `guidefold load <urn>` | the model, from already-listed URNs |

Hierarchy is encoded in the skill URN: `urn:skill:<publisher>:<dotted.node.path>:<skill-name>`.
Discovery walks up the tree: `turnstile → identity → mosaic → _root`, plus semantic hits ranked lower.

## CLI subcommands

`where` · `find` · `load` · `hook` · `prewarm` · `materialize [--check]` · `validate` · `drift --base <ref>` · `publish --changed` · `index`

## Consumer setup (target state)

1. Copy `skills/guidefold/` to `<monorepo>/.agents/skills/guidefold/`; symlink from `.claude/skills/` and `.github/skills/`.
2. Write `guidefold.yaml` at the monorepo root (see `templates/guidefold.example.yaml`).
3. Copy `templates/github-workflows-skills.yml` to `.github/workflows/skills.yml`; set up Workload Identity Federation for the CI service account.
4. Install hooks from `skills/guidefold/hooks/` into `.claude/settings.json`, `.github/hooks/guidefold.json`, `~/.codex/hooks.json`.
5. `guidefold materialize` and commit the generated cards.

Developers need only `gcloud auth application-default login` and `roles/agentregistry.viewer`.

## Try it on the playground

```bash
cd examples/monorepo
G=../../skills/guidefold/scripts/guidefold
python3 $G validate                                   # 26 skills, 0 errors
python3 $G materialize && python3 $G index            # regenerate AGENTS.md cards + hierarchy-index skill
python3 $G find "add a kafka topic with 7 day retention" --scope forge.pipelines.streaming
echo '{"cwd":"'$PWD'/platforms/atlas/identity/turnstile","prompt":"add an authorization check"}' | python3 $G hook
python3 $G load urn:skill:meridian:atlas.identity.turnstile:postgres-auth
```

`registry.backend: local` in `guidefold.yaml` makes all of this run without GCP. Switch to
`agent-registry` (and set `registry.project`) to `publish` and `find` against the real registry.

## Day-1 checklist (remaining)

1. ~~Preview access, payload flags, download shape~~ — verified, see `docs/ASSESSMENT.md` §2b.
2. ~~MCP skill tools~~ — none exist; ADR-0003 stands.
3. Quota increase request for standalone skills per project (default 100).
4. Copilot CLI from repo root AND node dir: `/instructions` must list the node card in both.
5. Claude Code: `[guidefold]` lines appear after a prompt (hook L1). Codex / Gemini CLI: verify injection (Gemini needs JSON output).
6. Legal: OSS license + IP sign-off.

## License

TBD — see risk Q6 in `docs/DESIGN.md`.
