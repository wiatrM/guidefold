from pathlib import Path
p=Path("CLAUDE.md");s=p.read_text()
old="Read `docs/DESIGN.md` (v0.3) first, then `docs/CONVENTIONS.md`. Decisions are in `docs/adr/`;\nADR-0008..0010 are Proposed. `docs/ASSESSMENT.md` holds every verified fact about the registry API."
new="""Start with `docs/DOCUMENTATION-RULES.md` to select the authoritative document for the task.
For the authorized product pivot, read `docs/PRODUCT-PIVOT.md` (requirements),
`docs/PIVOT-ARCHITECTURE.md` (system boundaries), `docs/PIVOT-BACKLOG.md` (order),
and `docs/PIVOT-REVIEW.md` (rationale). Their Proposed status does not cancel a task the user
has already authorized; it also does not prove that planned behavior is implemented.
For existing CLI behavior, read its code/tests plus `docs/DESIGN.md` and `docs/CONVENTIONS.md`.
For hosted UI, use `docs/ui/IA.md`, `UX.md`, `UI.md` and the relevant entry in
`docs/ui/pipeline/README.md`; do not restore the former four-section local UI.
Decisions are recorded in `docs/adr/`. `docs/ASSESSMENT.md` records dated registry API evidence;
verify time-sensitive claims before relying on them."""
assert old in s;s=s.replace(old,new)
s=s.replace("| `docs/` | Design doc, conventions, ADRs, assessment. |", "| `docs/` | Product requirements, architecture, backlog, documentation rules, CLI conventions, ADRs and evidence. |")
s=s.replace("| `docs/ui/` | UI information architecture (`IA.md`), interaction principles and anti-slop gate (`UX.md`), visual system and React port plan (`UI.md`) — for the future `guidefold ui` (E5). |", "| `docs/ui/` | Hosted U4 information architecture, UX, visual system and reviewed pipeline 00–08. Read each file's current status; a prototype is not the API implementation. |")
s=s.replace("17 nodes / 26 skills / stub code", "17 declared nodes / 27 SKILL.md files including the hierarchy index at the pivot baseline / stub code")
s=s.replace("| `tests/` | pytest suite (to be built). |", "| `tests/` | Existing pytest suite; use the checks appropriate to the changed behavior. |")
s=s.replace("## Hard constraints (from the design)", "## Existing CLI constraints")
s=s.replace("  inside the skill ZIP to the registry, so no package layout, no third-party deps.", "  inside the skill ZIP, so no package layout or additional runtime dependencies. This constraint\n  applies to the distributable CLI, not the proposed Go API/worker or React UI.")
s=s.replace("- Tests: `pytest` from repo root (once `tests/` exists).", "- Tests: `pytest` from repo root.")
s=s.replace("- Keep `docs/DESIGN.md` and `docs/CONVENTIONS.md` in sync with the CLI's behaviour.", "- Keep `docs/DESIGN.md` and `docs/CONVENTIONS.md` in sync with the CLI's behavior.\n- Update the canonical document and its affected consumers in the same task; use the new-file\n  and evidence rules in `docs/DOCUMENTATION-RULES.md`. Preserve unrelated work and do not commit\n  when the user requested uncommitted review.")
p.write_text(s)
p=Path("CONTRIBUTING.md");s=p.read_text()
s=s.replace("## Running the CLI against the fixture", "Choose requirements and update rules through [DOCUMENTATION-RULES](docs/DOCUMENTATION-RULES.md).\nThe pivot PRD defines the authorized new product scope; existing CLI behavior is evidenced by code and tests.\n\n## Running the CLI against the fixture")
s=s.replace("`tests/` is not built yet (`docs/MVP.md` story E0.1). Once it exists, run `pytest` from the\nrepo root.", "Run `pytest` from the repo root.")
s=s.replace("and `pytest` once `tests/` exists.", "and the relevant `pytest` tests.")
s=s.replace("- Add or update tests for behaviour you change, once `tests/` exists.", "- Add or update meaningful tests for changed behavior; do not add tests that merely restate a low-impact documentation edit.")
s=s.replace("`docs/MVP.md` if scope changed, a new or amended ADR if a decision changed.", "the canonical product/UI document selected by `docs/DOCUMENTATION-RULES.md` when scope or interaction changes, and a new or amended ADR when a decision changes.")
s=s.replace("`git status` after running them should go back to clean before you commit\n(`git clean -fd examples/monorepo` removes anything they left behind); see", "review named output paths against `git status` and preserve unrelated changes; see")
p.write_text(s)
p=Path(".github/PULL_REQUEST_TEMPLATE.md");s=p.read_text().replace("Link the MVP story or issue if there is one.", "Link the canonical requirement/story or issue selected by docs/DOCUMENTATION-RULES.md.")
s=s.replace("`pytest` once `tests/` exists", "relevant `pytest` tests").replace(" (once `tests/` exists)", "")
s=s.replace("`docs/MVP.md` if scope changed, a new or amended ADR if a decision changed.", "the canonical product/UI document selected by [DOCUMENTATION-RULES](../docs/DOCUMENTATION-RULES.md)\n      if scope or interaction changed, a new or amended ADR if a decision changed.")
s=s.replace("- [ ] No generated files in the diff —", "- [ ] No unreviewed generated consumer output in the diff —")
p.write_text(s)
