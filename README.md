# Guidefold

Git-native skill CI for a monorepo.

## What problem this solves

An agent working in a large monorepo does not know which of an organisation's rules,
conventions and runbooks apply to the directory it is standing in. A company can accumulate
thousands of these as the codebase grows, and no agent session can load all of them on every
prompt. Guidefold keeps that guidance as Agent Skills (`SKILL.md` directories) next to the code
they govern, then gives any coding agent a way to find and load only the handful that apply to
where it is and what it is doing.

## How it works

- Skills live next to the code they govern, under `.agents/skills/` at any level of the
  monorepo.
- CI validates every skill on pull request and publishes merged skills to Google Cloud Agent
  Registry as immutable revisions.
- An index artifact — cards, search postings, the hierarchy graph — is built from the merged
  skill set on every commit to `main`.
- A `SessionStart`/`UserPromptSubmit` hook reads the current directory and the prompt, then
  injects at most four skill cards, ordered general to specific.
- Git is the source of truth for skill text; the registry is a build artifact, never edited by
  hand ([ADR-0001](docs/adr/ADR-0001-git-source-of-truth-registry-artifact.md)).

## Quickstart

The commands below run against the "Meridian" fixture in `examples/monorepo/`
(`registry.backend: local`), so no GCP account is needed. Each one was run against this repo
before being written down here.

```bash
cd examples/monorepo
G=../../skills/guidefold/scripts/guidefold

python3 $G validate                                    # 26 skills, 0 errors
python3 $G where                                        # hierarchy node for the current directory
python3 $G find "add a kafka topic with 7 day retention" --scope forge.pipelines.streaming
echo '{"cwd":"'$PWD'/platforms/atlas/identity/turnstile","prompt":"add an authorization check"}' \
  | python3 $G hook
python3 $G load urn:skill:meridian:atlas.identity.turnstile:postgres-auth
```

`validate` is the CI gate; `where` and `find` are what an agent runs to orient itself and rank
candidate skills; `hook` is what a Claude Code or Codex hook runs on every prompt; `load`
downloads one skill's body into `.guidefold/cache/`. `skills/guidefold/SKILL.md` is the same
workflow written for an agent to follow.

Other implemented subcommands: `materialize [--check]`, `index`, `drift --base <ref>`,
`publish --changed`, `prewarm`. `init`, `doctor`, `card` and `ui` are designed but not built
yet — see Roadmap.

## Repository layout

```
guidefold/
├── CLAUDE.md                     # instructions for an agent working in this repo
├── CONTRIBUTING.md               # how to run the CLI, run tests, propose an ADR, send a PR
├── docs/
│   ├── MVP.md                    # 8-week MVP: storage decision, epics, user stories, plan  ← start here
│   ├── DESIGN.md                 # design doc v0.3: 2k+ skill model, index, router pipeline, caching, lift, demo UI
│   ├── KNOWLEDGE-DESIGN.md       # knowledge layer v0.1: lifecycle, gates, SkillPyramid induction, models
│   ├── AGENT-SKILLS-RESEARCH.md  # research registry: papers, models, datasets behind the router design
│   ├── CONVENTIONS.md            # guidefold.yaml, skill layout, URN naming, frontmatter, CI checks
│   ├── ASSESSMENT.md             # verified facts about the Agent Registry API (what was actually tested)
│   ├── archive/DESIGN-v0.2.md    # superseded design, kept for history
│   ├── ui/                       # UI information architecture (IA.md), interaction principles and
│   │                              # anti-slop gate (UX.md), visual system (UI.md) — for the future `guidefold ui`
│   └── adr/                      # architecture decisions; see docs/adr/README.md for the status index
├── skills/guidefold/             # THE DISTRIBUTABLE UNIT — copied into a consumer monorepo
│   ├── SKILL.md                  # bootstrap skill (find → load workflow for agents)
│   ├── scripts/guidefold         # single-file Python CLI (stdlib + PyYAML)
│   └── hooks/                    # hook templates: claude.settings.json, codex.hooks.json, copilot.hooks.json
├── templates/
│   ├── github-workflows-skills.yml   # consumer CI: validate / materialize --check / drift on PR, publish on main
│   └── guidefold.example.yaml        # example hierarchy map
├── examples/monorepo/            # "Meridian" playground: 17 nodes, 26 skills — fixture for demos and tests
├── examples/PLAYGROUND_SPEC.md   # how the playground was authored; use it to add nodes/skills consistently
├── prototypes/, design-explorations/  # frozen visual-design references behind docs/ui/UI.md, not shipped code
└── tests/                        # pytest suite (planned, see docs/MVP.md E0.1)
```

## Status

Design v0.3. The CLI works end to end against the local backend and against a GCP test
registry (project `guidefold-test-b6a18a`) — see `docs/ASSESSMENT.md` for the verification log.
MVP epics E0 and E1 are in progress. Full plan, scope and kill criteria:
[`docs/MVP.md`](docs/MVP.md).

## Roadmap

The MVP (`docs/MVP.md`) is eight weeks across six epics:

- **E0 — Foundation and hygiene** (week 1): CI baseline, `Router`/`Registry` split in the CLI,
  this publication cleanup, `guidefold init`/`doctor`, ADR hygiene.
- **E1 — Router 0.1** (weeks 1-3): task-aware ranking instead of directory-only, a golden query
  set, an embedder bake-off, the immutable index artifact, the prompt-time hook pipeline.
- **E2 — Serving without generated files** (weeks 2-4): no generated file committed, scope
  cards rendered at session start, CI publishing a merged skill to the registry within 10
  minutes.
- **E3 — Promotion vertical** (weeks 3-6): `scan → propose → eval → promotion PR →
  probationary serving`, with the decision log in one Postgres.
- **E4 — Lifecycle and governance** (weeks 6-8): gates G1-G4 enforced in CI, probation scoring,
  SkillPyramid induction, an append-only audit log.
- **E5 — Demo UI** (weeks 7-8): the scope graph, a routing probe, a promotion feed — see
  [`docs/ui/IA.md`](docs/ui/IA.md) (structure), [`docs/ui/UX.md`](docs/ui/UX.md) (interaction
  principles and the anti-slop gate) and [`docs/ui/UI.md`](docs/ui/UI.md) (visual system).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to run the CLI against the fixture, run tests,
and the PR process.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
