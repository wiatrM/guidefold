---
name: solid-principles
description: Check Guidefold code against SOLID using the repository's own boundaries (Go modules, the CLI Registry port, UI adapters, contract versions). Use when adding a class, module, interface or contract field and when reviewing structure. Not an academic checklist; each rule maps to a concrete detection.
---

# SOLID w Guidefold

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: rozpoznać naruszenie zasady po konkretnym sygnale w tym repo i naprawić je w kierunku granic z architektury pivotu.
Źródło: [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) ("Granice modułów", "Najpierw trzy techniczne bramki"), [ADR-0003](../../../docs/adr/ADR-0003-bootstrap-skill-cli-not-mcp.md), [UI](../../../docs/ui/UI.md) §5, [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Rozpoznaj zasadę po sygnale z repo

| Zasada | Jak wygląda tu | Jak wykryć naruszenie |
|---|---|---|
| SRP | Moduł Go ma właściciela zapisu do swoich tabel (Identity, Import, Knowledge, Review/Publication, Retrieval/Delivery, Telemetry/Reporting). Telemetria nie modyfikuje skilli ani membership. | Jedna funkcja pisze do tabel dwóch modułów; handler HTTP parsuje, liczy i zapisuje; plik zmienia się z dwóch niezależnych powodów w kolejnych PR. |
| OCP | Nowy backend registry lub nowe źródło danych UI dodaje adapter, nie zmienia domeny. `Registry`/`LocalRegistry` w `skills/guidefold/scripts/guidefold` są wymienne (ADR-0003: MCP lub ARD później). | `if backend == "local"` rozsiane po komendach; `switch` po typie źródła w kodzie widoku. |
| LSP | Kontrakt 1.1 nie dostaje nowych gwarancji przez zmianę etykiety; 1.2 jest osobnym kontraktem z własnymi testami (bramka 2). Fixture adapter i API adapter spełniają ten sam kontrakt w `ui/src/data`. | Klient 1.1 zaczyna zależeć od pola, którego 1.1 nie obiecuje; fixture zwraca stan, którego API nigdy nie zwróci, albo odwrotnie. |
| ISP | Odczyty między modułami przez jawne, wąskie interfejsy/projekcje; worker i API mają różne uprawnienia mimo wspólnego kodu. | Interfejs "Store" z dwudziestoma metodami przekazywany wszędzie; widok importuje cały klient API, używa jednej metody. |
| DIP | Domena definiuje port, adapter go implementuje (zob. `hexagonal-architecture`). Routing w `services/search/routing.go` nie zna HTTP ani SQL. | Import `net/http`, `database/sql`, `fetch`, DOM w kodzie reguł biznesowych; test domeny wymaga bazy. |

## Napraw w kierunku granic pivotu

Naruszenie SRP naprawiasz przez przeniesienie zapisu do modułu-właściciela, nie przez nowy moduł. Naruszenie OCP/DIP naprawiasz portem po stronie domeny i adapterem po stronie I/O. Naruszenie LSP naprawiasz nową wersją kontraktu z testami (głęboki łańcuch, diament, >4 karty, denied, zmiana snapshotu, 409), nie łataniem starej. Naruszenie ISP naprawiasz zawężeniem interfejsu do metod używanych przez wywołującego. Zmiany robisz stopniowo; dziś `services/search` jest w `package main` i pełny rewrite jest zakazany ([PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md)).

## Przykład z repo

Dodanie backendu ARD do CLI: nowa klasa obok `LocalRegistry` z tymi samymi metodami co `Registry`, wybór w jednym miejscu (konstruktor z `guidefold.yaml`), komendy `find`/`publish` bez zmian. Jeśli komenda musi wiedzieć, który backend działa, port jest za wąski albo za szeroki; popraw port, nie komendę.

## Sprawdź przed zakończeniem

- Czy każda nowa tabela lub zapis ma jednego właściciela wśród sześciu modułów?
- Czy nowa implementacja (registry, źródło danych, dostawca LLM) weszła jako adapter bez edycji kodu domeny?
- Czy zmiana kontraktu ma nowy numer wersji i testy, a stary klient nadal przechodzi swoje?
- Czy interfejsy przekazywane między modułami mają tylko metody używane przez odbiorcę?
- `grep -n '"net/http"\|"database/sql"' services/search/routing.go` zwraca pusto; analogicznie brak `fetch(` w `ui/src/domain`.
