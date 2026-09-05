# Contributing to Guidefold

Guidefold is git-native skill CI for a monorepo. This file covers how to run it locally, how to
test a change, the one hard constraint on the CLI, and what a pull request needs.

## Running the CLI against the fixture

There is nothing to install beyond Python 3 and PyYAML. The playground lives in
`examples/monorepo/` ("Meridian," a fictional data-integration platform) with
`registry.backend: local`, so it runs without a GCP account:

```bash
cd examples/monorepo
G=../../skills/guidefold/scripts/guidefold

python3 $G validate
python3 $G where
python3 $G find "add a kafka topic with 7 day retention" --scope forge.pipelines.streaming
python3 $G load urn:skill:meridian:atlas.identity.turnstile:postgres-auth
```

If PyYAML is not on your system Python, install it in a virtualenv first
(`python3 -m venv venv && venv/bin/pip install pyyaml`) and use that interpreter instead.

`materialize` and `index` write generated files into the tree (`AGENTS.md`, `CLAUDE.md`,
`.github/instructions/*`, `.agents/skills/hierarchy-index/`). Do not commit their output —
`git status` after running them should go back to clean before you commit
(`git clean -fd examples/monorepo` removes anything they left behind); see
[ADR-0012](docs/adr/ADR-0012-nothing-generated-is-committed.md) and the "no generated files
committed" line in the PR checklist.

## Running tests

`tests/` is not built yet (`docs/MVP.md` story E0.1). Once it exists, run `pytest` from the
repo root. Tests that talk to the registry must mock `Registry`/`subprocess` — no test may hit
GCP.

## The single-file CLI constraint

`skills/guidefold/scripts/guidefold` is a single Python 3 file, standard library plus PyYAML
only. No package layout, no other third-party dependency. This is not a style preference: the
script ships inside the skill ZIP that CI uploads to Agent Registry, and the registry has no
mechanism to install a dependency alongside a skill. If your change needs a library the
standard library does not provide, it does not belong in this file — raise it as an ADR instead
of adding the import.

## Proposing a decision (ADR)

A change to the design that another contributor would reasonably ask "why did we do it this
way" about gets an ADR in `docs/adr/`, not just a paragraph in a PR description. Copy the format
of an existing ADR (Status line, Context, Decision, Consequences), number it the next free
`ADR-000N`, and set `Status: Proposed` until the decision owner accepts it. See
[`docs/adr/README.md`](docs/adr/README.md) for the full index and process note, and
[`docs/adr/ADR-0019-open-source-apache-2.md`](docs/adr/ADR-0019-open-source-apache-2.md) for a
recent example.

## Sending a pull request

- Branch from `main`, name it `feat/<short-description>` (or `fix/…`, `docs/…` for
  non-feature changes).
- CI must be green: `guidefold validate` on the fixture, `python3 -m py_compile
  skills/guidefold/scripts/guidefold`, and `pytest` once `tests/` exists.
- Add or update tests for behaviour you change, once `tests/` exists.
- Update the docs in the same PR: `docs/DESIGN.md`/`docs/CONVENTIONS.md` if CLI behaviour
  changed, `docs/MVP.md` if scope changed, a new or amended ADR if a decision changed.
- Fill in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) — it is the
  actual review checklist, not boilerplate to delete.
- No generated files in the diff (`AGENTS.md`, `CLAUDE.md`/`GEMINI.md` one-liners,
  `.github/instructions/*`, `.agents/skills/hierarchy-index/` — see ADR-0012).

## Scope note

Two repos are involved in the design and must not be confused in a PR: **this repo** (the tool:
the bootstrap skill, the CLI, the templates) and a **consumer monorepo** (where a real
`guidefold.yaml`, real `.agents/skills/**` and a real CI workflow would live after copying
`skills/guidefold/` and `templates/` in). `examples/monorepo/` plays the part of the consumer
monorepo for development and tests; nothing under it is a real organisation's data.

## Real evaluation corpora

Quality numbers come from real labelled skill corpora (SkillRetBench, SkillRet), pinned by revision
and SHA-256 in `docs/reports/bakeoff/validation/corpora-manifest.json`:

```
~/.cache/guidefold/gpu-venv/bin/python tools/eval/corpora.py fetch    # ~130 MB, once
python3 tools/eval/corpora.py verify                                  # stdlib; must print OK
```

The 26-skill fixture and its golden set are the dev/regression suite only. See `CLAUDE.md`.

## Never stage from the shared checkout

`/home/mike/projects/guidefold` (or whatever your main checkout is) may have **more than one agent
or session writing into it at once**. `git add -A` there will commit whatever anyone else happens
to have in flight — this happened in PR #40, which swept ~65 800 lines of an unrelated service
spike into a documentation commit.

- Do every change in its own worktree: `git worktree add ../gf-<topic> -b <branch> origin/main`.
- If you must commit from the shared checkout, stage **named paths only** (`git add docs/x.md`),
  never `-A`, `.` or `-u`.
- Before committing anywhere, read `git status --short` and confirm every listed path is yours.
