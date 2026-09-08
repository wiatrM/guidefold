---
name: git-workflow
description: Branching, staging, committing and PR rules for the Guidefold repository: worktree per task, never commit on main, named-path staging, PR template, no force push or hook bypass. Use before any git write operation; not for consumer monorepo CI design.
---

# Praca z Gitem w tym repozytorium

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy commit pochodzi z własnej gałęzi, zawiera tylko nazwane pliki zlecenia i ma zweryfikowany opis.
Źródło: [CONTRIBUTING, Sending a pull request i Never stage from the shared checkout](../../../CONTRIBUTING.md), [PULL_REQUEST_TEMPLATE](../../../.github/PULL_REQUEST_TEMPLATE.md), [CLAUDE.md, Working here](../../../CLAUDE.md), [ADR-0012](../../../docs/adr/ADR-0012-nothing-generated-is-committed.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Zacznij od gałęzi

- Nigdy nie commituj na `main`. Każde zadanie ma własny worktree: `git worktree add ../gf-<topic> -b feat/<topic> origin/main` (`fix/`, `docs/` dla innych rodzajów). Skill `superpowers:using-git-worktrees` opisuje mechanikę.
- Współdzielony checkout `/home/mike/projects/guidefold` może mieć kilku agentów naraz. `git add -A`, `.` i `-u` są zakazane; stage'uj wyłącznie nazwane ścieżki. PR #40 wciągnął ~65 800 linii cudzej pracy przez `-A`.
- Przed commitem przeczytaj `git status --short` i potwierdź, że każda ścieżka jest twoja. Pliki `*:Zone.Identifier` z Windows pomijaj i nie commituj.

## Commituj tylko na zlecenie

- Commit i push wykonuj, gdy użytkownik o to prosi. Gdy zlecił review lub "zostaw do przeglądu", nie commituj; wypisz zmienione pliki.
- Komunikat: pierwsza linia mówi co i po co, ciało wymienia, co zweryfikowano (komenda i wynik). Ostatnia linia: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Zakazane: wymuszony push (`--force`) na współdzielone gałęzie, pomijanie hooków commitowych flagą no-verify, `git reset --hard` na cudzych zmianach, rebase gałęzi z otwartym PR bez uzgodnienia. Hook `PreToolUse` z `.claude/settings.json` blokuje część z tego; blokada nie jest zaproszeniem do obejścia.
- `private/` nigdy nie trafia do publicznego repo; `.guidefold/telemetry/`, `~/.cache/guidefold/corpora/` i wyjścia `materialize`/`index` (`AGENTS.md` klienta, one-linery, `.github/instructions/*`, `hierarchy-index`) pozostają poza diffem.

## Przygotuj PR wg szablonu

| Sekcja | Wymaganie |
|---|---|
| What and why | Jedno lub dwa zdania i link do U-story, P-zadania lub issue wybranego przez DOCUMENTATION-RULES |
| CI | `guidefold validate` na fixture, `python3 -m py_compile skills/guidefold/scripts/guidefold`, właściwe `pytest`; dla `ui/` workflow `ui.yml` |
| Testy | Dodane lub zmienione dla zmienionego zachowania; bez testów restatujących edycję docs |
| Docs | `DESIGN.md`/`CONVENTIONS.md` przy zmianie CLI, kanoniczny dokument PRD/UI przy zmianie zakresu, ADR przy zmianie decyzji, w tym samym PR |
| Generowane | Brak w diffie |

Stopka PR: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Checklist odhaczaj tylko po zobaczeniu dowodu.

## Sprawdź przed zakończeniem

- `git branch --show-current` nie zwraca `main`.
- `git status --short` pokazuje wyłącznie pliki tego zlecenia; żadnych `Zone.Identifier`, `private/`, plików generowanych.
- Użytkownik zlecił commit; jeśli zlecił review, commit nie istnieje.
- Komunikat commita wymienia komendę weryfikacji i ma stopkę Co-Authored-By.
- Żadna komenda w historii sesji nie użyła wymuszonego pusha, pominięcia hooków ani `add -A`.
