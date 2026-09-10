# Kolejne testy jakości Guidefold — plan stop/go

**Status:** plan wykonawczy, 2026-09-10  
**Cel:** sprawdzić jakość produktu na poziomie decyzji agenta i wykonania zadania.  
**Zakres:** SEARCH → USE → ASK, proof-gated delivery, hierarchia i telemetry.

Dotychczasowe wyniki potwierdzają, że harness działa, a bramka potrafi zatrzymać
konflikt, nieaktualną rewizję, zmianę scope i uszkodzone body. Nie pokazują jeszcze,
że agent wybiera właściwy skill ani że kończy zadanie lepiej od baseline'u. Dlatego
następne testy wykonujemy w poniższej kolejności.

## P0 — jakość pomiaru i widoczność w UI

**Hipoteza.** Każdy wynik widoczny w Organization → Telemetry jest zgodny z ledgerem
zdarzeń i nie ukrywa brakujących danych.

**Test.** Replay 100 zapisanych trace'ów: sukces, failure, harness error, timeout,
SEARCH bez wyników, USE zakończony `ASK`, retry i duplikat eventu. Porównać surowy
ledger, API agregujące i Score Cards.

**Akceptacja.** 100% zgodności liczników po deduplikacji; `unknown` pozostaje
`unknown`; brak mieszania organizacji/repozytoriów; poprawne okna 1/7/30 dni;
kliknięcie karty otwiera trace z taskiem i przyczyną ASK. Test powinien również
sprawdzić, że zero obserwacji nie jest pokazywane jako zero zamiast „brak danych”.

**Metryki.** task success, harness errors, SEARCH, returned results, search errors,
USE, ASK, input/output tokens, tool calls, p50/p95 elapsed time, unknown count.

To jest warunek wiarygodnego dashboardu, ale nie dowód przewagi produktu.

## E2-R — realna bramka bezpieczeństwa dostawy

**Hipoteza.** Przy konflikcie rodzeństwa, stale pointerze, deprecated skillu,
przeniesieniu scope lub niepełnym proofie system nie dostarczy treści i zwróci ASK.

**Test.** Co najmniej dwa niezależne repozytoria w każdej z dwóch rodzin źródeł,
zamrożone commity oraz późniejsza rewizja C′. Przygotować **minimum 73
pre-registered harmful-trigger opportunities** (konflikt, stale, scope, tamper,
closure), plus bezpieczne przypadki LOAD. Arm proof-gated porównać z flat/
concatenation, który jest kontrolą ekspozycji.

**Akceptacja.** Zero stale/conflicting body deliveries; dwustronny 95% Wilson upper
bound dla harmful loads ≤5% (73 przypadki pozwalają przejść tę bramkę przy zerze
szkodliwych dostaw); false-ASK i użyteczne LOAD-y raportowane osobno. Każdy przypadek
ma identyfikator rewizji, scope, expected action i powód decyzji.

E2-R jest blokujący dla wdrożenia. Sukces syntetycznego E2 pozostaje tylko testem
regresji.

## E6.7 — sparowany test wykonania zadań

**Hipoteza.** Dostarczenie skilli poprawia wynik pracy agenta, nie tylko Recall@k.

**Task bank.** Minimum 20 zadań jako feasibility run, docelowo 40; trzy zespoły,
realne zadania zamykalne w ≤60 minut, zamrożony hidden verifier i pre-written
acceptance check. Żadne zadanie nie może zostać dodane, usunięte ani zmienione po
zamrożeniu.

**Cztery warunki, każdy w osobnej sesji agenta:**

| Kod | Warunek | Rola |
|---|---|---|
| A | `no_skills` | dolny baseline |
| B | `sparse` | obecny shipped comparator |
| C | `map+gate+evolution` | kandydat do promocji |
| D | `oracle` | ceiling/headroom, nie produkt |

Warunki są counterbalanced, model, harness, prompt, snapshot i policy są
hash-addressed. Wynik zadania to wyłącznie `success`, `failure` albo `unknown`;
unknown nie wolno zamieniać na pass.

**Akceptacja kandydata C.**

* success nie więcej niż 5 pp poniżej najlepszego non-gated baseline'u;
* useful delivery ≥90% baseline'u;
* brak nieznanych wyników w komórkach wymaganych przez bramkę (w feasibility
  unknown jest raportowany i oznacza `inconclusive`);
* E2-R przechodzi niezależnie od task success.

Raportujemy paired gain rate, regression rate, exact i Wilson CI, czas, tokeny,
liczbę loads, wrong-skill detours, loads-never-used, time-to-first-relevant-skill
oraz wszystkie SEARCH/USE/ASK i harness errors. `ASK` jest poprawny tylko wtedy,
gdy verifier lub etykieta E2 potwierdza, że dostawa była nieuprawniona.

## HIER-C/C′ — naturalna hierarchia i drift

**Hipoteza.** Mapa hierarchiczna pomaga na scope'ach niewidzianych przy budowie mapy
i pozostaje bezpieczna po zmianie rewizji.

**Test.** Mapę budować na rodzinach A/B, a oceniać na niezależnym C oraz C′. Uruchomić
ten sam bank i budżet kandydatów w sześciu armach: `flat`, `navigate`, `graph`,
`map`, `map+gate`, `map+gate+evolution`. Nie używać gold do selekcji.

**Pierwszorzędne wyniki.** task success, harmful loads, stale/conflict deliveries,
false ASK, unknown coverage. Recall@k, Complete@4, latency i tokeny są wtórne.
Wynik tylko na C, bez C′, nie jest dowodem odporności na drift.

## ABL-R — ablacją i odporność

Po E2-R i pierwszym E6.7 uruchomić kontrolowane testy: brak wyników, 10× distractors,
malformed URN, timeout SEARCH, timeout USE, brak proofu, duplikat rewizji i duży
payload. Dla każdego scenariusza zapisać expected action, actual action, body bytes,
latency i harness error.

**Warunek:** brak silent fallbacku do body przy błędzie; każdy wyjątek ma jawny
`ASK`/error reason; p95 SEARCH i USE pozostaje w budżecie produktu. Nie stroić modelu
na tych przypadkach ani nie mieszać ich z głównym wynikiem task success.

## Kolejność i decyzje

1. P0 telemetry replay — odblokowuje zaufanie do UI i raportów.
2. E2-R — jeśli nie przejdzie, zatrzymać dostawę body i naprawić gate.
3. E6.7 feasibility (20 zadań), potem rozszerzenie do 40, jeśli harness i unknown
   rate są akceptowalne.
4. HIER-C/C′ oraz ABL-R — dopiero po zamrożeniu task banku i konfiguracji.

Decyzja po tych testach:

* **GO pilot:** E2-R przechodzi, C spełnia bramkę task success/useful coverage,
  a wyniki obejmują dwie rodziny repozytoriów.
* **GO jako reliability/governance:** E2-R przechodzi, lecz C nie poprawia task
  success; sprzedajemy bezpieczną, źródłowo dowodowaną dostawę, bez claimu o
  wyższości retrievalu.
* **SHADOW:** retrieval zyskuje tylko na Recall@k albo przegrywa na jednym typie
  zadań; mapę zostawiamy jako shadow i nie zmieniamy defaultu.
* **STOP/narrow:** harmful delivery, brak realnego useful coverage albo porażka na
  obu rodzinach repozytoriów; zawężamy produkt do governance/feedback przed merge.

Nie uruchamiać teraz kolejnych sweepów MLP, encoderów ani macierzy retrieval-only.
Bez task-level outcome nie rozstrzygają jakości produktu, a zwiększają ryzyko
wyboru konfiguracji po obejrzeniu wyniku.
