---
name: backlog-prioritisation
description: Choose the next Guidefold task from PIVOT-BACKLOG P01–P15 by dependencies, Pilot Core scope, technical gates and pilot deadlines. Use when deciding what to work on or ordering work in a plan; not for tasks already assigned by the user.
---

# Kolejność backlogu pivotu

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: wybór następnego zadania wynika z zależności, bramek technicznych i terminów pilota, nie z wygody implementacji.
Źródło: [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md), [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) §13, [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md). Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Rozpoznaj strukturę backlogu

P01–P15 to lokalne ID historii, nie numery GitHub Issues; kolumna „Powiązanie istniejące” podaje numery issue, które są historycznym backlogiem do aktualizacji po przyjęciu decyzji. Pełne AC są w sekcji PRD podanej w kolumnie „Dowód odbioru”; skrót w tabeli ich nie zastępuje.
Zależności krytyczne: P02 (izolacja org) przed danymi więcej niż jednej organizacji; P04 przed P05/P06; P09 (snapshot i pakiety) przed P10; P05 i P10 przed P11; P10–P11 i partner od tygodnia 1 przed P15. P09 dla istniejących zatwierdzonych skilli nie czeka na P07.

| Poziom | Zakres | Cel i termin z §13 PRD |
|---|---|---|
| Pilot Core | Ograniczone P01–P05, P09, jeden adapter z P10, podstawowe P11, mały przykład P06–P08 | Pełny wąski przepływ do 2026-09-20; partner potwierdzony w dniach 1–3 |
| ACT-01 | Scenariusz odbioru P05/P09/P10/P11: źródło → publikacja → load w prawdziwym zadaniu → feedback → decyzja ownera | 20 realnych sesji osoby spoza zespołu i drugi harness do 2026-10-04 |
| Kompletna beta | Błędy/retry, wygodne review i mapa, skala katalogu, drugi instalator, filtry, eksport, P12–P15 | Warunkowo do 8 tygodni; zakres zależy od dowodów |

## Wybierz następne zadanie

1. Zbierz otwarte zgłoszenia krytyczne: auth, utrata danych, błędna publikacja, niezgodność rewizji. Mają pierwszeństwo przed każdym rozszerzeniem UI (backlog „Zasady prowadzenia”).
2. Sprawdź bramki techniczne: P02, P09 i zaufany builder w workerze (PIVOT-ARCHITECTURE „Najpierw trzy techniczne bramki”). Niezamknięta bramka blokuje historie, które od niej zależą.
3. Z pozostałych wybierz historię Pilot Core, której wszystkie zależności z kolumny „Zależności” są zamknięte dowodem, nie planem. Preferuj zadanie na ścieżce ACT-01.
4. Przed implementacją zapisz obsługiwane środowiska, próbkę odbioru i miejsce zapisu wyniku (backlog „Zasady prowadzenia”, ostatni punkt); bez tego historia nie jest gotowa do startu.
5. Jeśli żadna historia Core nie jest odblokowana, wybierz najmniejszą pracę, która odblokowuje bramkę z kroku 2, albo zadanie dowodowe z `pilot-evidence`. Nie sięgaj po Kompletną betę, dopóki ACT-01 nie ma dowodu.

## Odrzuć skróty

- Nowa funkcja nie dostaje statusu done przez test fixture; wymaga dowodu użytkowego z kolumny „Dowód odbioru” (ADR-0029 reguła 3).
- P03–P05 dają wartość niezależnie od jakości modelu; awaria generowania nie blokuje importu istniejących skilli.
- P06–P08 nie zmieniają produkcyjnego rankingu bez osobnej, ograniczonej i z góry opisanej ewaluacji.
- P14 i P15 używają wspólnych komponentów; nie dodawaj portalu onboardingowego ani platformy benchmarkowej.
- Praca na 10–20 istniejących skillach jednego modułu może dać pierwszy użytkowy przebieg przed masowym przetwarzaniem. Wybieraj ją przed skalowaniem.

## Sprawdź przed zakończeniem

- Wybrane zadanie ma `P<nn>`, sekcję PRD z AC i wszystkie zależności zamknięte dowodem; wynik kroków 1–5 jest zapisany w planie.
- Żadne otwarte zgłoszenie krytyczne (auth, dane, publikacja, rewizje) nie czeka za tym zadaniem.
- Zadanie należy do Pilot Core lub odblokowuje bramkę P02/P09/builder; jeśli należy do Kompletnej bety, plan wskazuje dowód ACT-01, który to uzasadnia.
- Plan podaje środowiska, próbkę odbioru i miejsce zapisu wyniku.
- Numery GitHub Issues i P-id nie są używane zamiennie.
