---
name: yagni-scope-control
description: Refuse speculative code, flags and abstractions in Guidefold; build only what a backlog story (P01–P15), a PRD requirement (U1–U11) or an explicit user order names. Use before adding any "future-proof" element and when scoping a task. Not for cutting required acceptance criteria.
---

# YAGNI: buduj tylko to, co ma historię

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: żaden element kodu nie powstaje bez wymagania, które go dziś potrzebuje.
Źródło: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md) (reguła 1: surface freeze, komponenty parked), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md), [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md), [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Przypisz każdą zmianę do wymagania

Przed pierwszą linią kodu znajdź w [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md) zadanie P01–P15 albo w [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) wymaganie U1–U11 z acceptance criteria. Jeśli nie ma, potrzebne jest jawne zlecenie użytkownika w bieżącej rozmowie; zapisz je w opisie PR słowami użytkownika. Status Proposed dokumentu nie unieważnia zleconej pracy, ale też nie dodaje własnych zadań.

## Odrzuć elementy "na przyszłość"

| Element | Dlaczego zakazany | Co zrobić zamiast |
|---|---|---|
| Flaga funkcji bez drugiej ścieżki dziś używanej | nietestowana gałąź, zmiana zachowania bez dowodu | jedna ścieżka; flaga dopiero z zadaniem, które ją włącza |
| Interfejs z jedną implementacją poza granicą domena/adapter | abstrakcja bez drugiego użycia | konkretny typ; port tylko na granicy heksagonu (zob. `hexagonal-architecture`) |
| Parametr "na wypadek gdyby" | rozszerza kontrakt bez wymagania | stała; parametr, gdy pojawi się drugi wywołujący |
| Nowy runtime, baza, worker, język, target wdrożenia | reguła 1 ADR-0029 | pytanie do backlogu z progiem z tabeli "Kiedy wydzielić mikroserwis" w [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) |
| Rozszerzanie kodu parked (TEI/GPU shadow worker, k8s lifecycle, vector layout, graph admission) | kod trzymany za flagą, nie na ścieżce krytycznej | zostaw; zmiana wymaga decyzji właściciela i ADR |
| Komenda CLI z planu (`ui`, `import`, `login`, `install`) | [UI](../../../docs/ui/UI.md) §5: plan nie dodaje ich do CLI | kod w Go API/worker/ui zgodnie z modułem |

## Odmawiaj rozszerzeniu poprawnie

Gdy w trakcie pracy widzisz "przydałoby się X": nie koduj. Dopisz jedno zdanie do opisu PR w sekcji "Poza zakresem" z identyfikatorem najbliższego zadania P-nn albo propozycją nowego wpisu do [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md). Rozszerzenie zakresu zleca użytkownik, nie agent (zob. `guidefold-product-changes`).

## Przykład z repo

Pilot Core w [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md) obejmuje P01–P05, P09, jeden adapter z P10 i podstawowe P11. Drugi instalator, pełne retry i filtry eksportu należą do kompletnej bety; kod przygotowujący je "przy okazji" jest poza zakresem, nawet jeśli wygląda na tani.

## Sprawdź przed zakończeniem

- Czy opis PR zawiera identyfikator U/P albo cytat zlecenia użytkownika?
- Czy każdy nowy interfejs, flaga i parametr ma dziś co najmniej dwóch użytkowników albo leży na granicy port/adapter?
- Czy `git diff --stat` nie dotyka katalogów parked ani plików spoza zadania?
- Czy pomysły spoza zakresu są zapisane jako pytania, a nie jako kod?
- Czy nie dodano zależności runtime (`go.mod`, `ui/package.json`, importy w CLI) bez wskazanej reguły ADR?
