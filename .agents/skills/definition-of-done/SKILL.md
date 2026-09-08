---
name: definition-of-done
description: Definition of Done for Guidefold changes by type (CLI, Go, UI, docs, feature) with the exact checks to run and the evidence a PR must state. Use before claiming a task complete, opening a PR or reporting to the user. Not satisfied by "tests pass on the fixture" for user-facing features.
---

# Definition of Done

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: "gotowe" oznacza sprawdzone komendą, opisane w źródle i udowodnione na właściwym poziomie (R/Q/P), nie "działa u mnie".
Źródło: [CLAUDE.md](../../../CLAUDE.md) ("Working here"), [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md), [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) §1 (R/Q/P), [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md) (reguła 3: "Done means used"), [UI README](../../../ui/README.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Wykonaj sprawdzenia dla rodzaju zmiany

| Rodzaj | Komendy | Warunki |
|---|---|---|
| CLI (`skills/guidefold/scripts/guidefold`) | `python3 -m py_compile skills/guidefold/scripts/guidefold`; `pytest` | tylko stdlib + PyYAML; registry zamockowane; [DESIGN](../../../docs/DESIGN.md) i [CONVENTIONS](../../../docs/CONVENTIONS.md) zaktualizowane w tej samej pracy; pliki generowane tylko przez `materialize`/`index` |
| Go (`services/`) | `cd services/search && go vet ./... && go test ./...` | zapis w module-właścicielu; kontrakt 1.1 bez nowych gwarancji; brak nowej zależności runtime bez ADR; bramki z `module-boundaries-go` |
| UI (`ui/`) | `cd ui && pnpm build && pnpm test && pnpm test:contracts && pnpm test:e2e`; przy `pnpm dev`: `pnpm test:flow`, `pnpm test:visual` | wartości tylko z `tokens.css`; ≤14 komponentów; sześć stanów tras (restricted ma pierwszeństwo); axe bez błędów; brak słów z [UX](../../../docs/ui/UX.md) §6.2; baseline nie regenerowany |
| Docs | ręczna kontrola nagłówka i indeksu | status, data, cel, wejścia, zakres zastępowania; wpis w indeksie (AGENTS.md, ADR README, pipeline README); zależne opisy zmienione w tej samej pracy; Proposed nie opisany jako wdrożone |
| Feature | jak wyżej dla dotkniętych warstw | R: AC z PRD spełnione na fixture; Q: próbka lub pomiar wskazany w AC; P: dowód z pilota, jeśli AC go wymaga. Fixture Meridian dowodzi R, nie P |

## Zapisz dowód, nie deklarację

Opis PR podaje: identyfikator wymagania (U/P) lub cytat zlecenia; każdą komendę z tabeli, która została uruchomiona, z wynikiem (liczba testów, czas, identyfikator przebiegu); co pominięto i dlaczego. "Testy przechodzą" bez komendy i wyniku nie jest dowodem. Raport z pomiarem podaje środowisko, fixture lub dane rzeczywiste i ograniczenia ([DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md), "Nowe pliki").

## Zachowaj granice pracy

Nie commituj, gdy użytkownik zlecił przegląd bez commitu. Nie dotykaj niezwiązanych plików. Nie regeneruj baseline wizualnego, żeby zaakceptować zmianę. Nie podnoś statusu ADR do Accepted bez decyzji właściciela. Unknown nie jest zerem, eksport nie jest publikacją, pobranie nie jest użyciem.

## Przykład

Zmiana kolejności wyników `find` w CLI: `py_compile` i `pytest` z liczbą testów w opisie PR, wpis w [CONVENTIONS](../../../docs/CONVENTIONS.md) o nowej kolejności, poziom R. Twierdzenie o poprawie jakości routingu wymaga dodatkowo pomiaru na oznaczonym korpusie ([CLAUDE.md](../../../CLAUDE.md), "Evaluation corpora"); fixture Meridian tego nie dowodzi.

## Sprawdź przed zakończeniem

- Czy każda komenda z wiersza tabeli dla dotkniętych warstw została uruchomiona i jej wynik jest w opisie PR?
- Czy dokument kanoniczny i zależne opisy są zmienione w tym samym diffie?
- Czy opis PR nazywa poziom dowodu (R/Q/P) i to, czego fixture nie dowodzi?
- Czy `git status` pokazuje tylko pliki zadania, a commit istnieje tylko wtedy, gdy go zlecono?
- Czy w PR nie ma słowa "gotowe" dla rzeczy, których nie sprawdzono komendą?
