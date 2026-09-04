## What and why

<!-- One or two sentences: what changes, and why. Link the MVP story or issue if there is one. -->

## Checklist

- [ ] CI is green (`guidefold validate` on the fixture, `py_compile` on
      `skills/guidefold/scripts/guidefold`, `pytest` once `tests/` exists).
- [ ] Tests added or updated for behaviour this PR changes (once `tests/` exists).
- [ ] Docs updated in this PR: `docs/DESIGN.md`/`docs/CONVENTIONS.md` if CLI behaviour changed,
      `docs/MVP.md` if scope changed, a new or amended ADR if a decision changed.
- [ ] No generated files in the diff — `AGENTS.md`, `CLAUDE.md`/`GEMINI.md` one-liners,
      `.github/instructions/*`, `.agents/skills/hierarchy-index/`
      ([ADR-0012](../docs/adr/ADR-0012-nothing-generated-is-committed.md)).

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full process.
