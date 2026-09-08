---
name: module-boundaries-go
description: Enforce the six Go module boundaries of the Guidefold pivot (Identity, Import, Knowledge, Review/Publication, Retrieval/Delivery, Telemetry/Reporting), the API–worker job contract and the three technical gates. Use when touching services/ Go code, schemas, jobs or publication. Not a plan to split services.
---

# Granice modułów Go i kontrakt API–worker

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy zapis ma jednego właściciela, każdy job jest idempotentny i ogrodzony generacją, publikacja jest transakcją na zwalidowanym snapshocie.
Źródło: [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) (sekcje "Granice modułów", "Co wdrażamy", "Kontrakt API–worker", "Najpierw trzy techniczne bramki", "Kiedy wydzielić mikroserwis"), [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Przypisz zmianę do modułu-właściciela

| Moduł | Własne dane | Kto pisze |
|---|---|---|
| Identity | sesje, membership, org, instalacje/tokeny, kontekst org/repo | API |
| Import | repo, manifest, source_revision, import_run, upload, plan joba | API (enqueue), worker (postęp) |
| Knowledge | skille, rewizje, scope, relacje, propozycje, provenance | worker (ekstrakcja), API (edycja propozycji) |
| Review/Publication | decyzje, digests, eksport, walidacja pakietu/grafu, aktywacja snapshotu | API (decyzja), worker (build, aktywacja) |
| Retrieval/Delivery | SEARCH/USE, policy, budżet, odczyt opublikowanej rewizji | API, tylko odczyt danych Knowledge |
| Telemetry/Reporting | ledger, dedupe, agregaty, health, raporty | API (events); nigdy nie modyfikuje skilli ani membership |

Odczyt między modułami idzie przez jawny interfejs lub projekcję (zob. `hexagonal-architecture`), nie przez wspólne zapytanie do cudzej tabeli. Worker i API mogą uruchamiać ten sam kod modułu, ale mają różne role bazodanowe i uprawnienia operacyjne; obraz API nie zawiera Pythona, worker ma przypięty builder `router_index`. Nie wykonujemy zaimportowanych skryptów i nie piszemy drugiego portu rankera.

## Trzymaj kontrakt jobów

Job niesie: `schema_version`, `org_id`, `repo_id`, `import_id`, etap, `input_manifest_digest`, `recipe_version`/`model_revision`, `idempotency_key`, limit pracy/wydatku, `generation`/fencing token. Enqueue i zmiana stanu w jednej transakcji. Worker przed pracą sprawdza aktualne uprawnienie i tożsamość org, odnawia lease, zapisuje checkpointy; wynik starej generacji nie nadpisuje nowszego. Cache generowania i dedupe kluczują org i wersje wejść; zmiana źródła unieważnia propozycję z niej wyprowadzoną. `Ready` importu nie oznacza `published`; publikacja aktywuje tylko zwalidowany snapshot przypisany do zatwierdzonego digestu. Niepewne opłaty LLM po timeout są rejestrowane pod `import_id`.

## Przejdź trzy bramki przed rozbudową

1. Tożsamość per request: `Store` w `services/search/store.go` ma Tenant/Repo i jeden cache Catalog; nie mutuj ich między użytkownikami. Wymagany test równoległych A/B z tym samym `repo_id`/URN, ciepłym cache, retry i rollbackiem.
2. Kontrakt pakietów: 1.1 nie dostaje nowych gwarancji przez etykietę; 1.2 dostaje testy: głęboki łańcuch, diament, >4 karty, denied, zmiana snapshotu, 409.
3. Zaufana publikacja: builder i walidator zachowują zgodność indeksu; rewizja obejmuje manifest zasobów; retencja uploadu nie usuwa aktywnego pakietu ani zależności do rollbacku.

Wydzielenie osobnej usługi wymaga progu z tabeli "Kiedy wydzielić mikroserwis" (np. SEARCH p95 >1 s w trzech kolejnych oknach 15 min po izolacji pul), ownera, kontraktu, SLO i planu migracji danych. Progi są propozycją, nie pomiarem.

## Sprawdź przed zakończeniem

- Czy każda nowa tabela lub kolumna ma jeden moduł-właściciel i rolę bazodanową, która ją pisze?
- Czy nowy job ma wszystkie pola kontraktu, a enqueue i stan zmieniają się w jednej transakcji?
- Czy handler retrieval czyta Knowledge przez projekcję, a nie przez zapis lub cudzą tabelę?
- Czy zmiana dotykająca cache/Store ma test równoległych org (bramka 1)?
- `cd services/search && go test ./...` przechodzi; nowe testy nazywają bramkę, którą dowodzą.
