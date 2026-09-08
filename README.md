# Guidefold

Git-native skill CI for a monorepo.

Working on Guidefold: start with [project instructions](AGENTS.md) and [documentation rules](docs/DOCUMENTATION-RULES.md). The [product pivot](docs/PRODUCT-PIVOT.md) describes proposed hosted behavior; implementation and validation status are separate.

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

python3 $G validate                                    # validate the Meridian fixture
python3 $G where                                        # hierarchy node for the current directory
python3 $G find "add a kafka topic with 7 day retention" --scope forge.pipelines.streaming
echo '{"cwd":"'$PWD'/platforms/atlas/identity/turnstile","prompt":"add an authorization check"}' \
  | python3 $G hook
python3 $G load urn:skill:meridian:atlas.identity.turnstile:postgres-auth
```

`validate` is the CI gate; `where` and `find` are what an agent runs to orient itself and rank
candidate skills; `hook` is what a Claude Code or Codex hook runs on every prompt; `load`
prints the exact path to the resolved `SKILL.md`. Read that printed path; download caches use `GUIDEFOLD_CACHE` or `~/.cache/guidefold`. `skills/guidefold/SKILL.md` is the same
workflow written for an agent to follow.

Other implemented subcommands: `materialize [--check]`, `index`, `drift --base <ref>`,
`publish --changed`, `prewarm`. The hosted UI design is separate from CLI commands; see the reviewed [UI pipeline](docs/ui/pipeline/README.md).

### Onboarding a consumer repo

`init` and `doctor` bootstrap and diagnose a *consumer* monorepo in place — run them from that
repo's root, not from this one:

```bash
cd /path/to/your-monorepo
python3 /path/to/guidefold/skills/guidefold/scripts/guidefold init          # --dry-run to preview first
python3 /path/to/guidefold/skills/guidefold/scripts/guidefold doctor        # --json for machine-readable output
```

`init` writes a `guidefold.yaml` skeleton (never overwriting one that already exists), copies
`skills/guidefold/` in as `.agents/skills/guidefold/`, installs harness hooks (`--harness
claude|copilot|codex|all`, default `all`) by merging into any existing hook config, installs the
GitHub Action, and appends the `.gitignore` entries from
[ADR-0012](docs/adr/ADR-0012-nothing-generated-is-committed.md). It is idempotent — running it
again leaves already-present artifacts untouched. `doctor` then checks Python/CLI install,
`guidefold.yaml` validity, skill layout (`validate`), hook wiring, `.gitignore`, the GitHub
Action, the registry backend (gcloud/ADC/roles for `agent-registry`, a readability check for
`local` — gracefully degraded, never hangs, no network access beyond timeout-guarded gcloud
calls), and index freshness, printing a one-line fix for every non-`ok` check. Exit code is `0`
iff every check passed; `1` otherwise.

## Repository layout

```
guidefold/
├── AGENTS.md / CLAUDE.md         # instructions for agents working in this repo
├── .agents/skills/               # project workflows; not the distributable bootstrap
├── CONTRIBUTING.md               # how to run the CLI, run tests, propose an ADR, send a PR
├── docs/
│   ├── DOCUMENTATION-RULES.md    # choose the canonical document and maintain new files
│   ├── PRODUCT-PIVOT.md          # proposed U1–U11 scope, requirements and acceptance criteria
│   ├── PIVOT-ARCHITECTURE.md      # React + modular Go API + worker
│   ├── PIVOT-BACKLOG.md / PIVOT-REVIEW.md # local stories and decisions
│   ├── MVP.md                    # earlier roadmap and pivot entry point
│   ├── DESIGN.md                 # design doc v0.3: 2k+ skill model, index, router pipeline, caching, lift, demo UI
│   ├── KNOWLEDGE-DESIGN.md       # knowledge layer v0.1: lifecycle, gates, SkillPyramid induction, models
│   ├── AGENT-SKILLS-RESEARCH.md  # research registry: papers, models, datasets behind the router design
│   ├── CONVENTIONS.md            # guidefold.yaml, skill layout, URN naming, frontmatter, CI checks
│   ├── ASSESSMENT.md             # verified facts about the Agent Registry API (what was actually tested)
│   ├── archive/DESIGN-v0.2.md    # superseded design, kept for history
│   ├── ui/                       # UI information architecture (IA.md), interaction principles and
│   │                              # anti-slop rules (UX.md), visual system (UI.md), pipeline 00–08
│   └── adr/                      # architecture decisions; see docs/adr/README.md for the status index
├── skills/guidefold/             # THE DISTRIBUTABLE UNIT — copied into a consumer monorepo
│   ├── SKILL.md                  # bootstrap skill (find → load workflow for agents)
│   ├── scripts/guidefold         # single-file Python CLI (stdlib + PyYAML)
│   └── hooks/                    # hook templates: claude.settings.json, codex.hooks.json, copilot.hooks.json
├── templates/
│   ├── github-workflows-skills.yml   # consumer CI: validate / materialize --check / drift on PR, publish on main
│   └── guidefold.example.yaml        # example hierarchy map
├── examples/monorepo/            # "Meridian" fixture: 17 declared nodes, 26 authored skills plus hierarchy index
├── examples/PLAYGROUND_SPEC.md   # how the playground was authored; use it to add nodes/skills consistently
├── prototypes/, design-explorations/  # source references and local UI prototypes; not evidence of hosted API delivery
└── tests/                        # existing pytest suite; UI checks live with the UI artifacts
```

## Status and plan

The existing CLI and Go SEARCH/USE service have their own code, tests and dated verification records. See [service documentation](services/search/README.md) and [registry evidence](docs/ASSESSMENT.md); a proposed feature is not an implemented command.

The current product proposal is a versioned organizational skill library: import source instructions, review changes, hand them back to Git, deliver revisions through harnesses, and distinguish delivery from evidence of usefulness. The [pivot](docs/PRODUCT-PIVOT.md), [architecture](docs/PIVOT-ARCHITECTURE.md), [backlog](docs/PIVOT-BACKLOG.md) and [review](docs/PIVOT-REVIEW.md) define the proposed scope and dependencies.

The [UI pipeline](docs/ui/pipeline/README.md) records actual stage status and QA for seven U4 views. Its Meridian fixture is a local simulation, not working OAuth, multi-org backend, Git publication or adapter telemetry. Historical epics remain in [MVP.md](docs/MVP.md); current UI work must not restore the former four-view promotion demo.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to run the CLI against the fixture, run tests,
and the PR process.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
