from pathlib import Path
p=Path('../../docs/DOCUMENTATION-RULES.md');s=p.read_text().replace('Data: 2026-09-06.','Status: aktywne reguły projektu. Data: 2026-09-06.',1)
s+='\n## Instrukcje projektu\n[AGENTS.md](../AGENTS.md) jest wejściem dla agentów pracujących w tym repozytorium. [guidefold-product-changes](../.agents/skills/guidefold-product-changes/SKILL.md) kieruje zmiany wymagań i kontraktów, a [guidefold-ui-workflow](../.agents/skills/guidefold-ui-workflow/SKILL.md) pracę nad U4 i pipeline’em.\nSkille projektu rozwijają reguły odczytu i wykonania, nie są drugim PRD. Dystrybuowany [bootstrap](../skills/guidefold/SKILL.md) służy repozytoriom klientów; nie dopisuj do niego wewnętrznych planów Guidefold ani nie zmieniaj skilli fixture w celu aktualizacji instrukcji projektu.\n'
p.write_text(s)
p=Path('../../CLAUDE.md');s=p.read_text().replace('Start with `docs/DOCUMENTATION-RULES.md`','Project entry point: [AGENTS.md](AGENTS.md). Local workflows: [product changes](.agents/skills/guidefold-product-changes/SKILL.md) and [UI workflow](.agents/skills/guidefold-ui-workflow/SKILL.md).\n\nStart with `docs/DOCUMENTATION-RULES.md`')
s=s.replace('- Generated files (`AGENTS.md`,','- Generated consumer files (`AGENTS.md`,')
s=s.replace('## Relevant installed skills (global, `~/.agents/skills`)','## Earlier skill references')
s=s.replace('Invoke via the Skill tool when the task matches. Reinstall with `npx skills add <repo> --skill <name> -g -y`.','Use skills actually available in the current session. This table records earlier references, not a guarantee that those global skills are installed; project workflows are linked above.')
s=s.replace('Already installed from before and also relevant:','Other earlier references:')
p.write_text(s)
p=Path('../../README.md');s=p.read_text().replace('Git-native skill CI for a monorepo.','Git-native skill CI for a monorepo.\n\nWorking on Guidefold: start with [project instructions](AGENTS.md) and [documentation rules](docs/DOCUMENTATION-RULES.md). The [product pivot](docs/PRODUCT-PIVOT.md) describes proposed hosted behavior; implementation and validation status are separate.',1)
s=s.replace('python3 $G validate                                    # 26 skills, 0 errors','python3 $G validate                                    # validate the Meridian fixture')
s=s.replace('downloads one skill\'s body into `.guidefold/cache/`.','prints the exact path to the resolved `SKILL.md`. Read that printed path; download caches use `GUIDEFOLD_CACHE` or `~/.cache/guidefold`.')
s=s.replace('`card` and `ui` are designed but not built yet — see Roadmap.','The hosted UI design is separate from CLI commands; see the reviewed [UI pipeline](docs/ui/pipeline/README.md).')
s=s.replace('├── CLAUDE.md                     # instructions for an agent working in this repo','├── AGENTS.md / CLAUDE.md         # instructions for agents working in this repo\n├── .agents/skills/               # project workflows; not the distributable bootstrap')
s=s.replace('│   ├── MVP.md                    # 8-week MVP: storage decision, epics, user stories, plan  ← start here','│   ├── DOCUMENTATION-RULES.md    # choose the canonical document and maintain new files\n│   ├── PRODUCT-PIVOT.md          # proposed U1–U11 scope, requirements and acceptance criteria\n│   ├── PIVOT-ARCHITECTURE.md      # React + modular Go API + worker\n│   ├── PIVOT-BACKLOG.md / PIVOT-REVIEW.md # local stories and decisions\n│   ├── MVP.md                    # earlier roadmap and pivot entry point')
s=s.replace('# anti-slop gate (UX.md), visual system (UI.md) — for the future `guidefold ui`','# anti-slop rules (UX.md), visual system (UI.md), pipeline 00–08')
s=s.replace('# "Meridian" playground: 17 nodes, 26 skills — fixture for demos and tests','# "Meridian" fixture: 17 declared nodes, 26 authored skills plus hierarchy index')
s=s.replace('# frozen visual-design references behind docs/ui/UI.md, not shipped code','# source references and local UI prototypes; not evidence of hosted API delivery')
s=s.replace('# pytest suite (planned, see docs/MVP.md E0.1)','# existing pytest suite; UI checks live with the UI artifacts')
start=s.index('## Status');end=s.index('## Contributing',start)
s=s[:start]+"""## Status and plan

The existing CLI and Go SEARCH/USE service have their own code, tests and dated verification records. See [service documentation](services/search/README.md) and [registry evidence](docs/ASSESSMENT.md); a proposed feature is not an implemented command.

The current product proposal is a versioned organizational skill library: import source instructions, review changes, hand them back to Git, deliver revisions through harnesses, and distinguish delivery from evidence of usefulness. The [pivot](docs/PRODUCT-PIVOT.md), [architecture](docs/PIVOT-ARCHITECTURE.md), [backlog](docs/PIVOT-BACKLOG.md) and [review](docs/PIVOT-REVIEW.md) define the proposed scope and dependencies.

The [UI pipeline](docs/ui/pipeline/README.md) records actual stage status and QA for seven U4 views. Its Meridian fixture is a local simulation, not working OAuth, multi-org backend, Git publication or adapter telemetry. Historical epics remain in [MVP.md](docs/MVP.md); current UI work must not restore the former four-view promotion demo.

"""+s[end:]
p.write_text(s)
