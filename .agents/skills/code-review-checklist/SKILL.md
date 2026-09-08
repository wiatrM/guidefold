---
name: code-review-checklist
description: Review a Guidefold pull request or diff against scope, evidence, tests, module boundaries, anti-slop and dependent docs; report P1/P2/P3 findings with quotes. Use when reviewing or self-reviewing a change before merge; not for product scope decisions.
---

# Przegląd zmiany w repozytorium Guidefold

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: jeden przegląd, który sprawdza zakres, dowody, testy, granice i dokumenty zamiast ogólnego "wygląda dobrze".
Źródło: [PULL_REQUEST_TEMPLATE](../../../.github/PULL_REQUEST_TEMPLATE.md), [CONTRIBUTING](../../../CONTRIBUTING.md), [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md), [UX §6](../../../docs/ui/UX.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, co zmiana miała zrobić

Przeczytaj sekcję "What and why" PR albo zlecenie użytkownika. Przypisz zmianę do U1–U11, P01–P15 lub jawnie opisanej zmiany zakresu ([DOCUMENTATION-RULES, Wybór dokumentu](../../../docs/DOCUMENTATION-RULES.md)). Pliki spoza tego zakresu w diffie to P2, chyba że PR nazywa je i uzasadnia.
Sprawdź `git status --short` i listę plików PR: cudza praca w toku w diffie to P1 ([CONTRIBUTING, Never stage from the shared checkout](../../../CONTRIBUTING.md)).

## Sprawdź dowody, testy i granice

| Pytanie | Zaliczone gdy | Inaczej |
|---|---|---|
| Czy zmienione zachowanie ma test? | Nowy lub zmieniony test w `tests/`, `services/search/*_test.go` lub `ui/src`/`ui/e2e` nazywa to zachowanie | P1 |
| Czy dowód to komenda i wynik? | PR cytuje komendę, środowisko i rezultat; screenshot i "review agenta OK" nie wystarczają | P2 |
| Czy CI z szablonu przeszło? | `guidefold validate` na fixture, `py_compile` CLI, właściwe `pytest` | P1 |
| Czy zależności idą do środka? | Domena nie importuje adapterów, HTTP ani fixture (ADR-0032; `ui/src/domain`, `services/search`) | P2 |
| Czy nowy komponent lub wariant ma uzasadnienie? | Pisemny powód w PR; limit 14 eksportów z [UI](../../../docs/ui/UI.md) | P2 |
| Czy jest fikcja? | Brak wymyślonych firm, liczb i "planowanych" komend opisanych jako dostępne; fixture podpisany Meridian | P1 |
| Czy słowa z listy UX §6 pojawiają się w UI lub docs? | `grep -inE 'seamless|streamline|empower|unlock|effortless|supercharge' <pliki>` pusty | P2 |
| Czy dokumenty zależne są w tym samym PR? | `docs/DESIGN.md`/`CONVENTIONS.md` przy zmianie CLI; kanoniczny dokument PRD/UI przy zmianie zakresu; ADR przy zmianie decyzji | P1 |
| Czy diff zawiera pliki generowane? | Brak `AGENTS.md` klienta, one-linerów, `.github/instructions/*`, `hierarchy-index` ([ADR-0012](../../../docs/adr/ADR-0012-nothing-generated-is-committed.md)) | P1 |

## Zapisz znaleziska w jednym formacie

Każde znalezisko: priorytet, plik i linia, cytat z diffu lub dokumentu, jedno zdanie problemu, propozycja zmiany. P1 blokuje merge, P2 do poprawy przed merge, P3 notatka. Bez znaleziska bez cytatu. Podsumowanie kończy się liczbami P1/P2/P3 i zdaniem, czego nie sprawdziłeś (np. brak dostępu do korpusów, nieuruchomione e2e).

## Sprawdź przed zakończeniem

- Każdy plik diffu ma przypisanie do zakresu albo znalezisko.
- Każde P1/P2 ma cytat i propozycję; żadne nie opiera się na "chyba".
- Wymienione komendy naprawdę uruchomiłeś albo napisałeś, że nie.
- Lista słów zakazanych sprawdzona grepem na zmienionych plikach `ui/`, `docs/`, `prototypes/`.
- Checklist z szablonu PR odhaczony tylko tam, gdzie widziałeś dowód.
