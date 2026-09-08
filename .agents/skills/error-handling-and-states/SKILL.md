---
name: error-handling-and-states
description: Model failures honestly across Guidefold UI (six view states), Go service (wrapped errors, timeouts, contract status codes) and semantics (unknown is not zero, export is not publish). Use when adding a data path, endpoint, view or job step; not for product scope.
---

# Obsługa błędów i stany

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy brak danych, odmowa i awaria ma nazwany stan, a żaden z nich nie udaje sukcesu.
Źródło: [IA §6–7](../../../docs/ui/IA.md), [UX §3](../../../docs/ui/UX.md), [04-wireframes](../../../docs/ui/pipeline/04-wireframes.md), [HARNESS-SERVICE-CONTRACT, Response and delivery semantics](../../../docs/HARNESS-SERVICE-CONTRACT.md), [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md), [DOCUMENTATION-RULES, Nowe pliki](../../../docs/DOCUMENTATION-RULES.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Nazwij stan w UI

Każdy z siedmiu widoków obsługuje sześć stanów; macierz per widok jest w etapie 4 §5.

| Stan | Znaczenie | Komunikat |
|---|---|---|
| empty | Brak obiektów w zakresie | Co można zrobić, żeby się pojawiły |
| loading | Oczekiwanie | Bez podmiany treści pod kursorem podczas decyzji |
| partial | Znany brak części danych | Które pola/pliki brakują i dlaczego (np. pominięte w imporcie) |
| error | Niepowodzenie operacji | Co się nie zapisało; formularz zachowuje treść i powód |
| degraded | Ograniczone możliwości (brak API, wygasły surowy upload) | Czego brakuje; dostępne hashe i pochodzenie zostają |
| restricted | Brak dostępu do danych org | Bez body, nazw, liczników i poprzedniego cache |

Brak zdarzeń to "No observations"/Unknown, nie 0 %. Koszt na zaakceptowany skill przy zerze akceptacji jest niedostępny, nie zerowy. Decyzja o zakresie i brak dowodu mają komunikat tekstowy, nie sam kolor. Obsługa błędu modułu JS, timeoutu i dekodowania siedzi na granicy trasy; decyzji i publikacji nie aktualizujemy optymistycznie.

## Zwracaj błędy z kontekstem w Go

- Opakuj błąd z operacją i identyfikatorami: `fmt.Errorf("publish snapshot %s for org %s: %w", digest, orgID, err)`. Bez `panic` w ścieżce request; odzyskanie na granicy handlera zwraca 500 i loguje `attempt_id`.
- Zewnętrzne zależności (WorkOS, dostawca LLM, Postgres) mają timeouty i obsługę awarii jako oddzielne zależności; niepewne opłaty LLM po timeoutcie są rejestrowane, nie zgadywane.
- Kody kontraktu: 400 schemat, 403 USE poza scope, 404 nieznany skill, 409 zła rewizja/repozytorium lub zmiana snapshotu, 413 przekroczony budżet body, 422 nierozwiązany/niejednoznaczny scope, 429 przeciążenie, 503 niegotowy, 504 deadline. Nieznane pole żądania to 400, nigdy ciche zignorowanie.
- Gdy pakiet nie mieści się w budżecie: zero kart i `delivery_status: cannot_fit`; nigdy przycięty pakiet udający pełne closure. USE zwraca pełne body albo 413, nigdy fragment.
- Nieaktualna rewizja, brakujący zasób i zabroniony scope nigdy nie hydratują innej rewizji po cichu.

## Rozdzielaj obserwacje

Eksport nie jest publikacją, pobranie nie jest użyciem, `status: hydrated` nie jest wykonaniem (`execution_observed: false`). Ready importu nie oznacza published. Niekompletny import nazywa przyjęte i pominięte pliki. Te rozróżnienia mają odrębne pola i zdarzenia, nie jeden boolean.

## Sprawdź przed zakończeniem

- Nowy widok lub dana ma wpis w macierzy stanów i test dla stanów, które może przyjąć (`ui/e2e/states.spec.ts` lub Vitest).
- Nowy endpoint ma listę kodów błędów zgodną z kontraktem i test dla każdego kodu, który może zwrócić.
- Żaden komunikat nie mówi "sukces" bez potwierdzenia z serwera.
- Brak danych renderuje Unknown/No observations, nie zero, w kodzie i w agregacie.
- Timeout zewnętrznej zależności ma określoną wartość i test ścieżki po timeoutcie.
