---
name: performance-budgets
description: Apply Guidefold's numeric latency, payload and render budgets and the measure-before-and-after rule for CLI hook, SEARCH service and hosted UI. Use when a change touches retrieval, catalog queries, list/map rendering or bundle size; not for microservice split decisions without measurements.
---

# Budżety wydajności

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: optymalizacja tylko przeciw zapisanemu pomiarowi, wobec liczb z dokumentów, na tym samym fixture przed i po.
Źródło: [PRODUCT-PIVOT U4 AC2, U5 AC7](../../../docs/PRODUCT-PIVOT.md), [UX §3](../../../docs/ui/UX.md), [07-frontend, Budżety](../../../docs/ui/pipeline/07-frontend.md), [SEARCH-USE-TELEMETRY §7](../../../docs/SEARCH-USE-TELEMETRY.md), [PIVOT-ARCHITECTURE, Kiedy wydzielić mikroserwis](../../../docs/PIVOT-ARCHITECTURE.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Znaj liczby

| Ścieżka | Budżet | Warunki pomiaru |
|---|---|---|
| Świeży klient hooka (wybór lub fallback) | p95 ≤400 ms | Loopback, osobno c1 i c4, świeży proces na request, gotowy serwer; ≥200 prób |
| Serwer SEARCH | p95 ≤300 ms | Od admission HTTP do serializacji JSON, oba obciążenia |
| Interaktywny SEARCH z klienta | p95 ≤1 s | Zadeklarowana sieć i współbieżność pilota; loopback nie jest SLA |
| Pierwsza strona katalogu 10 tys. skilli | p95 ≤2 s | Od wejścia/filtra do klikalnego pierwszego wyniku, realna sieć pilota; ≥100 prób cold i warm osobno |
| Odpowiedź katalogu API | p95 ≤500 ms [założenie] | 50 summary na stronę |
| Payload strony / początkowy JS | ≤100 kB / ≤250 kB gzip [założenie] | Produkcyjny build |
| Map | start ≤100 obiektów, twardy limit renderu 200 | Tylko żądane children i sąsiedztwo; reszta przez cursor |
| Watchdog hooka | 3 s | Awaryjne przerwanie, nie cel latencji |

Nie renderujemy całego grafu; graf to sąsiedztwo wskazanego skilla. Body i duży diff pobieramy dopiero na szczególe. Ranking pozostaje integer-only na mmap postings; nie dodawaj floatów ani ładowania całego indeksu do pamięci.

## Mierz przed i po

1. Zapisz komendę, fixture lub dataset, wersje sprzętu, przeglądarki i sieci przed uruchomieniem.
2. Uruchom pomiar na niezmienionym kodzie; zapisz p50/p95, błędy i timeouty, nie średnią. Cold i warm osobno.
3. Wprowadź zmianę, powtórz identyczny pomiar. Raport zawiera obie serie i różnicę.
4. Bez pomiaru nie ma optymalizacji: hipoteza "będzie szybciej" to P2 w przeglądzie. Lokalny seed 10k jest syntetyczny; zaliczenie U4 AC2 wymaga środowiska pilota.
5. Zegary klienta i serwera są osobne; nie odejmuj niesynchronizowanych timestampów.

## Nie wydzielaj usługi bez progu

Pierwsza reakcja to oddzielne pule i limity dla retrieval/management/events oraz profiling. Osobny serwis retrieval dopiero, gdy po izolacji pul SEARCH p95 >1 s utrzymuje się w 3 kolejnych oknach 15 min uzgodnionego obciążenia. Raporty: agregaty asynchroniczne; osobny proces po >30 % czasu DB w szczycie i zmierzonej szkodzie SLO.

## Sprawdź przed zakończeniem

- Raport zawiera komendę, dataset, środowisko, p95 przed i po oraz liczbę błędów.
- Zmiana nie ładuje do pierwszego renderu body, diffu ani więcej niż limit obiektów Map.
- Nowy endpoint listy ma stronicowanie i cursor; brak `SELECT` bez limitu.
- Żadna liczba w PR nie jest opisana jako spełnienie AC, jeśli pochodzi z loopbacku lub fixture 27 plików.
- Hook nadal nie wykonuje wywołań sieciowych poza ścieżką SEARCH z deadline.
