---
name: spectrum-charts-migration
description: Mandatory migration of all Guidefold telemetry visualizations, metric cards and charts to actual Spectrum UI Charts components. Use for telemetry UI, dashboards, chart creation, replacement or migration audits; preserve data contracts and do not rewrite event ingestion or backend storage.
---

# Spectrum Charts — migracja telemetrii i wykresów

Status: aktywna instrukcja, 2026-09-09; migracja jest wymaganiem, nie potwierdzonym wdrożeniem.
Cel: przeprowadzić kompletną, mierzalną migrację warstwy wizualizacji, bez zmiany znaczenia danych.
Źródło: [UI §7](../../../docs/ui/UI.md#7-obowiązkowa-migracja-spectrum-charts), [Spectrum Charts](https://ui.spectrumhq.in/charts), [Pie](https://ui.spectrumhq.in/charts/pie).
Indeks: [AGENTS.md](../../../AGENTS.md), [CLAUDE.md](../../../CLAUDE.md).
Zakres zastępowania: dotychczasowy dowolny wybór rendererów wykresów; nie kontrakty telemetrii, API, bezpieczeństwo ani historyczne baseline.

## Uruchomienie i zakres

Przeczytaj [spectrum-ui-workflow](../spectrum-ui-workflow/SKILL.md), [observability-telemetry](../observability-telemetry/SKILL.md) oraz [UI §7](../../../docs/ui/UI.md#7-obowiązkowa-migracja-spectrum-charts).
Przy implementacji odczytaj również [accessibility-contract](../accessibility-contract/SKILL.md) i [performance-budgets](../performance-budgets/SKILL.md).
Ustal aktywny worktree i źródło danych. Nie traktuj podglądu developerskiego jako produkcji.
Obowiązek obejmuje także istniejące wykresy, miniwykresy i karty telemetrii; brak edycji danego widoku nie wyłącza go z inwentarza migracji.
Nie przepisuj ledgerów, collectorów, transportu, schematów ani raportów CLI do biblioteki React.

## Inwentarz i prawdziwe komponenty

1. Przeszukaj trasy, wspólne komponenty, SVG/canvas/CSS, zależności wykresowe i użycia metryk; sprawdź widoki w przeglądarce.
2. Dla każdej powierzchni zapisz: trasa/plik → obecny renderer → źródło i jednostka → item Spectrum → status → dowód/test.
3. Uwzględnij Usage, metryki szczegółu skilla, importu i organizacji, jeżeli istnieją; nie twórz nowych dashboardów bez zadania.
4. Wyszukaj item przez MCP lub oficjalny registry CLI; odczytaj źródło, wymagane pliki chart-kit, API, licencję i zależności.
5. Dla pie/donut punktem wyjścia jest @spectrumui/pie-chart. Nazwy pozostałych itemów potwierdź w aktualnym rejestrze.
6. Nie zakładaj jednego silnika: strona katalogu opisuje SVG, a dokumentacja Pie wskazuje Recharts i framer-motion.
7. Wykonaj dry-run i instaluj tylko potrzebne itemy. Zachowaj upstream i opis adaptacji; sam import ani własny podobny SVG nie spełnia wymagania.
8. Stary renderer usuń dopiero po sprawdzeniu wszystkich jego konsumentów. Brak odpowiednika lub niezgodność wymagają jawnego wyjątku, nie cichego pominięcia.

## Dobór wykresu i kontrakt danych

- Pie/donut: rozłączne części jednej całości z jawnym dodatnim mianownikiem. Nie sumuj nakładających się etapów search/load/use.
- Trend: line/area; porównanie kategorii: bar; rozkład opóźnień: histogram; gęste metryki: odpowiedni stat card/sparkline.
- Nie przenoś giełdowego copy, cen ani przykładowych danych z katalogu do telemetrii Guidefold.
- Adapter danych zachowuje filtr org/repo/rewizji, okres, strefę czasową, jednostkę, mianownik, deduplikację i pokrycie.
- Nie licz percentyli przez uśrednianie percentyli; nie mieszaj wywołań z unikalnymi epizodami ani load z użyciem.
- Unknown/null pozostaje brakiem danych. Zero pokazuj tylko przy potwierdzonej obserwacji zera; pusta seria nie jest serią zer.
- Dane częściowe, niedostępne i przestarzałe mają etykietę; nie ukrywaj braków przez normalizację znanych segmentów do 100%.
- Dla pie odrzuć NaN, nieskończoność i wartości ujemne; przy sumie zero pokaż stan pusty bez pozornego pełnego pierścienia.

## Interakcje i dostępność

Stosuj tokeny Guidefold, czytelne osie, jednostki i stabilne kolory serii; nie polegaj tylko na kolorze.
Zapewnij tekstowe podsumowanie i dostęp do dokładnych wartości w tabeli/liście; tooltip hover nie jest jedynym dostępem.
Filtry i legendy są obsługiwane klawiaturą z widocznym focusem; tooltip nie może zasłaniać aktywnej kontrolki.
Obsłuż sześć stanów tras, pierwszeństwo restricted, czyszczenie danych po zmianie org/logout i późne odpowiedzi.
Animacje pomagają śledzić zmianę wartości; respektuj reduced-motion, zatrzymuj pętle poza ekranem i w tle.
Nie animuj fikcyjnego live feedu ani rosnących liczników; duże serie agreguj według kontraktu i ładuj kod wykresów per trasa.

## Weryfikacja i raport

Testuj adaptery na dokładnych liczbach: null, zero, partial, pusty okres, pojedynczy punkt, zmiana filtra i dane z innej org.
Dla pie sprawdź mianownik, sumę, zaokrąglenia etykiet i poprawność legendy; dla trendów kolejność czasu i luki.
Uruchom build, testy zachowania, kontrakty, axe i kontrolę klawiatury; sprawdź 390px/desktop, resize i reduced-motion.
Porównaj wartości starego i nowego widoku na tym samym oznaczonym zestawie; sprawdź payload i budżet renderu.
Statusy: planned / in-progress / verified / exception. Verified wymaga rzeczywistego renderu i powiązanych wyników testów.
Raport obejmuje wszystkie pozycje inwentarza, usunięte renderery, źródła komponentów, dowody i pozostałe wyjątki.
Nie ogłaszaj pełnej migracji na podstawie instalacji pakietu, konfiguracji MCP lub zapisania tego skilla.
