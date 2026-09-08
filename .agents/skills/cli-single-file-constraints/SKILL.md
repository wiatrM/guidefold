---
name: cli-single-file-constraints
description: Hard constraints for editing the distributable Guidefold CLI in skills/guidefold/scripts/guidefold (single Python file, stdlib + PyYAML, Registry class boundary, generated files). Use before any change to that script or its tests. Not for the Go service or the React UI.
---

# Ograniczenia jednoplikowego CLI

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: zmiana CLI nie może zepsuć tego, że skrypt podróżuje w ZIP-ie skilla do rejestru i do repo klienta.
Źródło: [CLAUDE.md](../../../CLAUDE.md) (Existing CLI constraints), [CONVENTIONS §8–§9](../../../docs/CONVENTIONS.md), [ADR-0003](../../../docs/adr/ADR-0003-bootstrap-skill-cli-not-mcp.md), [ADR-0012](../../../docs/adr/ADR-0012-nothing-generated-is-committed.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, czy zmiana dotyczy tego pliku

Skill obowiązuje wyłącznie dla `skills/guidefold/scripts/guidefold`, jego hooków w `skills/guidefold/hooks/` i testów w `tests/`. Go API, worker i `ui/` mają własne reguły ([PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md)); plan pivotu nie dodaje komend `ui`, `import`, `login` ani `install` do tego CLI bez jawnego zadania.

## Zachowaj granice pliku

| Reguła | Jak sprawdzić |
|---|---|
| Jeden plik Python 3, bez package layout i bez `references/` z kodem | `ls skills/guidefold/scripts/` pokazuje tylko `guidefold` |
| Importy: stdlib oraz `yaml` (PyYAML); nic z pip | `grep -n '^import\|^from' skills/guidefold/scripts/guidefold` |
| Cały dostęp do rejestru przez klasę `Registry` (ADR-0003), bez `gcloud` poza nią | `grep -n 'gcloud' skills/guidefold/scripts/guidefold` wskazuje tylko `Registry` |
| Generowane pliki (`AGENTS.md`, `CLAUDE.md`/`GEMINI.md`, `.github/instructions/*`, `hierarchy-index`) powstają tylko w `materialize`/`index` | Żadna inna komenda nie pisze tych ścieżek |
| Karta zakresu ≤80 linii; przekroczenie skracasz przez `metadata.digest`, nie przez podniesienie limitu | CONVENTIONS §9 |
| Rejestr jest artefaktem builda; żadna komenda nie edytuje go ręcznie poza publish z CI | ADR-0001 |

Hook `.claude/hooks/check-cli-single-file.sh` (PostToolUse) powtarza kontrolę składni i importów po każdej edycji tego pliku (`.claude/settings.json`).

## Testuj tak, jak działa produkt

- Uruchamiaj z fixture: `cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold <cmd>`; root to najbliższy przodek z `guidefold.yaml` albo `$GUIDEFOLD_ROOT`.
- W `tests/` rejestr i `subprocess` są mockowane; żaden test nie wywołuje GCP ani sieci.
- Zmiana zachowania komendy wymaga aktualizacji `docs/DESIGN.md` i `docs/CONVENTIONS.md` w tej samej pracy.
- Reguły zapisu telemetrii i hooków: CONVENTIONS §10–§11; nie zmieniaj formatu plików `.guidefold/telemetry/*.jsonl` bez zmiany [SEARCH-USE-TELEMETRY](../../../docs/SEARCH-USE-TELEMETRY.md).

## Sprawdź przed zakończeniem

1. `python3 -m py_compile skills/guidefold/scripts/guidefold` przechodzi.
2. Lista importów zawiera tylko stdlib i `yaml`.
3. `pytest` z root przechodzi bez pominiętych testów rejestru, które wcześniej przechodziły.
4. Żadna nowa ścieżka zapisu poza `materialize`/`index` nie tworzy plików generowanych.
5. `docs/DESIGN.md` i `docs/CONVENTIONS.md` opisują nowe zachowanie; ZIP skilla nadal zawiera jeden skrypt plus hooki.
