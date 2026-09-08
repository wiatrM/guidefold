---
name: api-contract-versioning
description: Change SEARCH/USE and management API contracts safely: schema versions, strict validation, 1.1 vs designed 1.2 guarantees, OpenAPI-generated UI types and required conformance tests. Use when adding or changing request/response fields, status codes or delivery semantics.
---

# Wersjonowanie kontraktów API

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: nowa gwarancja istnieje tylko z nową wersją, schematem, testami i aktualizacją dokumentu kontraktu w tej samej pracy.
Źródło: [HARNESS-SERVICE-CONTRACT, Versioning and ownership / Requests and implemented effects / Response and delivery semantics](../../../docs/HARNESS-SERVICE-CONTRACT.md), [PIVOT-ARCHITECTURE, bramka 2](../../../docs/PIVOT-ARCHITECTURE.md), [PRODUCT-PIVOT, Dane i API](../../../docs/PRODUCT-PIVOT.md), [07-frontend](../../../docs/ui/pipeline/07-frontend.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, którą wersję zmieniasz

| Wersja | Stan | Gwarancje |
|---|---|---|
| bez `schema_version` (legacy) | Obsługiwana w obrębie backendu | Semantyka request/response jak dotąd; `"1.0"` nie jest wersją wire |
| `1.1` | Wdrożona: `GET /health/ready`, `POST /v1/search`, `POST /v1/use` | Do 4 kart, closure dwa poziomy, `cannot_fit`, kody 400/403/404/409/413/422/429/503/504 |
| `1.2` | Projektowana (bramka 2) | Wymagane zasoby, pełne `requires`, budżety, załadowane zależności, traversal, `cannot_fit`/`unresolved` |
| management API (org/member, import/upload/status, katalog/graf, proposal/export, installation/token, usage/report) | Projektowane | Osobne schematy; duże paczki nie przechodzą przez limit 16 KiB SEARCH |

Stary 1.1 nie otrzymuje nowych gwarancji przez zmianę etykiety. Niezgodne znaczenie pola wymaga nowej negocjowanej wersji; readiness ogłasza wspierane wersje. Nie opisuj 1.2 ani management API jako dostępnych.

## Zmieniaj addytywnie i ściśle

- Nieznane wersje, nieznane pola na każdym poziomie, duplikaty kluczy, złe typy i limity zwracają 400. Nigdy ciche ignorowanie. Klient toleruje dodatkowe pola odpowiedzi.
- Nowe pole request najpierw ląduje w `context.unused_fields` z `ranking_signal_not_admitted`, dopóki osobna ewaluacja nie dopuści go do rankingu. Przyjęcie metadanych nie jest dopuszczeniem zachowania.
- Retry transportu używa tego samego `request_id`; każda próba serwera ma własne `attempt_id`. `session_id`/`task_id` opcjonalne; brak to unknown.
- USE wymaga `skill_id` i dokładnej rewizji z SEARCH; nieaktualna rewizja lub zabroniony scope nigdy nie hydratują innej rewizji. Pełne body albo 413.
- Zmiana snapshotu lub repozytorium w trakcie to 409; klient nie przełącza się na "current" po cichu.

## Wersjonuj w jednej pracy

1. Schemat JSON i przykłady dla nowej wersji; walidacja runtime w Go.
2. Testy konformansu: głęboki łańcuch, diament, >4 karty, denied, zmiana snapshotu, 409, nieznane pole, limit bajtów, `cannot_fit`. Ścieżka `services/search/*_test.go` i `tests/` dla klienta.
3. Typy UI generowane z wersjonowanego OpenAPI Go; dekodowanie payloadu na granicy `ui/src/api` przed renderem. Fixture adapter implementuje ten sam interfejs i nie udaje sieci.
4. Aktualizacja `docs/HARNESS-SERVICE-CONTRACT.md` (tabela pól, kody, wersje) i `docs/SEARCH-USE-TELEMETRY.md`, gdy zmienia się grain zdarzeń, w tym samym PR. Adapter w `skills/guidefold/scripts/guidefold` i `hooks/` dostaje test konformansu, nie tylko nowy parametr.

## Sprawdź przed zakończeniem

- Zmiana ma numer wersji albo jest addytywnym polem odpowiedzi; żadna nie zmienia znaczenia istniejącego pola.
- Test odrzucenia nieznanego pola i złego typu istnieje dla każdego nowego obiektu.
- Lista kodów błędów w dokumencie kontraktu odpowiada handlerowi.
- Typy UI zregenerowane z OpenAPI, nie dopisane ręcznie.
- Dokument kontraktu zmieniony w tym samym diffie co kod.
