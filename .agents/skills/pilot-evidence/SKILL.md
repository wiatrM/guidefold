---
name: pilot-evidence
description: Collect and report pilot evidence for Guidefold under the R/Q/P split, §13 of the PRD and the kill criteria. Use when claiming value, closing a story, writing a report or planning the design-partner pilot; not for unit-test or fixture results.
---

# Dowody z pilota

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: wartość produktu jest stwierdzana wyłącznie dowodem z realnego użycia, zapisanym w odtwarzalnym raporcie z progiem ustalonym przed pomiarem.
Źródło: [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) §1, §12a, §13, U11, [PRODUCT-FOCUS](../../../docs/PRODUCT-FOCUS.md), [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md) P15, [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md). Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Rozróżnij trzy rodzaje kryteriów

| Etykieta | Znaczenie (PRD §1) | Kto i kiedy zalicza |
|---|---|---|
| R (Release AC) | Test techniczny przed wydaniem zakresu; nieoznaczone AC są R | Kod, testy, fixture Meridian; przed dostępem partnera |
| Q (Quality Gate) | Ocena jakości na wskazanej próbce, np. 30 propozycji dwóch reviewerów, potem zamrożony run 60 pozycji (§12a) | Owner i researcher wg rubryki ustalonej przed generowaniem |
| P (Pilot Evidence) | Dowód wartości zbierany podczas używania; nie jest warunkiem startu pilota | Realne sesje, ledger, decyzja ownera w czasie obserwacji |

Progi Q i P są zamrażane przed pomiarem; wynik nie zmienia progu. Wskaźnik 24/30 jest diagnostyczny, nie obietnicą 80% jakości (PIVOT-REVIEW).

## Uznaj tylko dowód, który nim jest

Dowodem jest: sesja osoby niebudującej Guidefolda w realnym harnessie na realnym repo z wpisem search i load w ledgerze; decyzja ownera zapisana z osobą, rewizją i powodem; raport z identyfikatorem przebiegu, wersjami i zamrożoną rubryką (U11); koszt per import z tokenami, retry, minutami review i liczbą opublikowanych skilli (§12a pkt 7).
Dowodem nie jest: test fixture, screenshot, pozytywna recenzja agenta, dane syntetyczne, liczba loadów lub krawędzi, zainteresowanie bez zobowiązania (DOCUMENTATION-RULES „Pierwszeństwo”, PRODUCT-FOCUS „Design partner”). Brak obserwacji to Unknown, nie porażka i nie zero. Koszt na zaakceptowany skill przy zerze akceptacji jest niedostępny.
Rubryka i buyer są definiowane od pierwszego tygodnia (P15), nie na końcu. Hipoteza „one minute a day” i pilot E6.7 (3 zespoły, 20–40 sparowanych zadań) pozostają go/no-go dla wszystkiego poza T1 (ADR-0029 reguła 6); protokół: [E6.7-PROTOCOL](../../../docs/pilot/E6.7-PROTOCOL.md), arkusze `docs/pilot/scoring-sheet.template.csv` i `task-bank.template.yaml`.

## Zapisz wynik tak, by dało się go odtworzyć

Raport trafia do `docs/reports/` (istniejące podkatalogi `bakeoff/`, `golden/`, `tuning/`); protokół i arkusze pilota do `docs/pilot/`. Raport podaje komendę i środowisko, fixture lub rzeczywiste dane, rezultat, ograniczenia oraz oba kierunki sukces/porażka (U11 AC). Wpis w dokumencie kanonicznym linkuje raport; nie duplikuj liczb w PRD.
Terminy z §13: partner potwierdzony w dniach 1–3, Pilot Core do 2026-09-20, 20 realnych sesji i drugi harness do 2026-10-04, obserwacja czterech tygodni po aktywacji Core. Brak partnera 2026-09-20 zatrzymuje rozbudowę.

| Kill criterion (PRODUCT-FOCUS) | Skutek |
|---|---|
| Brak partnera do 2026-09-20 | Stop dla feature'ów; Guidefold używany tylko na tym repo z jawną etykietą, albo stop |
| 10 skomentowanych PR bez zmiany tekstu | Authoring loop redukowany do lintera |
| 4 tygodnie sesji bez decyzji ownera | Telemetria przestaje być powierzchnią produktu |
| E6.7 bez korzyści czasu lub sukcesu zadania | Nic poza T1 |

Osobne decyzje po obserwacji (PRD §13, lista): brak przyjętych propozycji, zero zmian po raportach PR, brak decyzji ownera, jednorazowy import, użycie bez rozmowy zakupowej. Każda ma przypisaną reakcję; nie proponuj kolejnej rundy funkcji zamiast niej.

## Sprawdź przed zakończeniem

- Każde twierdzenie o wartości ma etykietę R, Q lub P i wskazuje raport z identyfikatorem przebiegu.
- Próg był zapisany przed pomiarem; raport zawiera oba kierunki wyniku i ograniczenia próby.
- Dane z fixture, screenshoty i recenzje agentów są podpisane jako R lub jako nie-dowód.
- Unknown nie został zastąpiony zerem; brak zdarzeń jest opisany jako nierozstrzygnięty.
- Sprawdzono tabelę kill criteria; spełnione kryterium jest zgłoszone właścicielowi, nie obejście.
