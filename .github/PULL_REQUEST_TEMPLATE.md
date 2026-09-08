## What and why

<!-- One or two sentences: what changes, and why. Link the canonical requirement/story or issue selected by docs/DOCUMENTATION-RULES.md. -->

## Checklist

- [ ] CI is green (`guidefold validate` on the fixture, `py_compile` on
      `skills/guidefold/scripts/guidefold`, relevant `pytest` tests).
- [ ] Tests added or updated for behaviour this PR changes.
- [ ] Docs updated in this PR: `docs/DESIGN.md`/`docs/CONVENTIONS.md` if CLI behaviour changed,
      the canonical product/UI document selected by [DOCUMENTATION-RULES](../docs/DOCUMENTATION-RULES.md)
      if scope or interaction changed, a new or amended ADR if a decision changed.
- [ ] No unreviewed generated consumer output in the diff — `AGENTS.md`, `CLAUDE.md`/`GEMINI.md` one-liners,
      `.github/instructions/*`, `.agents/skills/hierarchy-index/`
      ([ADR-0012](../docs/adr/ADR-0012-nothing-generated-is-committed.md)).

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full process.
