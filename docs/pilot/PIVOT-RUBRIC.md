# Rubryka pilota U11 (P15)

Status: aktywna rubryka, zamrożona przed pomiarem. Data: 2026-09-07.
Cel: dać `tools/pilot/pivot_report.py` i pilotowi E6.7 jeden wspólny, zamrożony zestaw mierników
i progów decyzji dla U11 ("Sprawdzenie zmiany harnessa/modelu"), zamiast ustalać je po zebraniu
wyników. Rubryka i buyer są definiowane od pierwszego tygodnia, nie na końcu (PIVOT-BACKLOG P15).
Wejścia: [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §10 U11, §12a, §13; [PRODUCT-FOCUS](../PRODUCT-FOCUS.md)
"Kill criteria", "Design partner"; [pilot-evidence](../../.agents/skills/pilot-evidence/SKILL.md);
[E6.7-PROTOCOL](E6.7-PROTOCOL.md).
Zakres zastępowania: brak nowego kontraktu; ta rubryka nie zastępuje E6.7-PROTOCOL.md (hipotezy
H1–H3, warunki A–D, stop rules), tylko dodaje etykiety R/Q/P i progi go/no-go, które
`pivot_report.py` liczy z tych samych trzech wejść co ono opisuje.

## Buyer / osoba decyzyjna (tydzień 1)

Zanim pilot wystartuje, są nazwane: repozytorium, developerzy, **przyjmujący skill owner**,
polityka danych, data startu (PRODUCT-FOCUS "Design partner") oraz osoba decyzyjna, problem,
budżet zakupowy i warunki rozmowy o płatnym wdrożeniu (PRODUCT-PIVOT §13). Dopóki te pola są puste,
każde "done" w tym repozytorium jest tymczasowe (ADR-0029 reguła 3). Brak partnera do
**2026-09-20** zatrzymuje rozbudowę.

## Rubryka U11: miernik, etykieta, populacja, próg

| # | Miernik | Etykieta | Populacja / mianownik | Próg / decyzja |
|---|---|---|---|---|
| 1 | Task success per arm | P | judged outcomes (`success`/`failure`) tej ręki; `unknown` wyłączone | Wilson 95% CI; `small_sample=true` przy `n_judged < 20` (API-CONTRACT `HelpedRatio`) |
| 2 | Regresja w obu kierunkach: with_skills vs without | P | discordant pairs (task obecny w obu ramionach, oba judged) | `gain_rate − regression_rate`; oba kierunki raportowane zawsze, nie tylko dodatni |
| 3 | Regresja w obu kierunkach: harness A vs B | P | jw., ramiona = harness/adapter zamiast with/without | jw.; brak par evaluable = `not_measured_here` |
| 4 | Time, paired delta | P | pary z `time_seconds` znanym w obu ramionach | bootstrap 95% CI (percentile); `n=0` → `not_measured_here`, nie 0 s |
| 5 | Cost per accepted skill | P | `accepted` zsumowane z cost JSON per import | `unavailable` przy `accepted=0`, nigdy 0 (pilot-evidence) |
| 6 | Cost per published skill | P | `published` zsumowane z cost JSON | jw., dla `published=0` |
| 7 | Review minutes per accepted skill | P | jw. (mianownik `accepted`) | jw.; nigdy sumowane z `usd_certain`/`usd_uncertain` |
| 8 | Owner decisions recorded | P | pozycje kolejki z zapisaną decyzją (`action`, `reason`, `at`) | `unavailable` przy zero pozycji; 4 tygodnie bez decyzji = kill |
| 9 | Adapter capability coverage (parity) | R | (skill_id, harness) z `/usage/export` | brak wspólnego `loads_verified>0` = `coverage_gap`; brak kolumny `harness` = `not_measured_here` |

Etykiety: **R** = test techniczny przed dostępem partnera, **Q** = ocena jakości na zamrożonej
próbce, **P** = dowód z realnego użycia (pilot-evidence SKILL.md). Wiersze 1–8 wymagają realnej
sesji i ledgera; są P, nie Q, mimo że liczy je ten sam skrypt co dane syntetyczne.

## Tabela go/no-go (PRODUCT-PIVOT §13, "Osobne decyzje po obserwacji")

| Obserwacja | Decyzja |
|---|---|
| Brak przyjmowanych propozycji / za drogi review | Ograniczyć generowanie, zachować bibliotekę |
| Zero zmian autorów po 10 realnych PR | Ograniczyć authoring do lintera |
| Brak decyzji ownera | Ograniczyć dashboard; traffic nie potwierdza wartości |
| Jednorazowy import bez powrotów | Zbadać usługę jednorazową, nie zakładać subskrypcji |
| Powtarzalne użycie bez rozmowy zakupowej | Ograniczony termin i jedno pytanie do buyera, bez nowej rundy funkcji |
| Powtarzalne korzyści + krok zakupowy | Dalsze wdrożenie z uzgodnionym kosztem |
| Przedłużenie nierozstrzygającego pilota | Tylko z limitem czasu/nakładu i jednym pytaniem |

Kill criteria (pełna tabela: [PRODUCT-FOCUS](../PRODUCT-FOCUS.md) "Kill criteria" — nie duplikujemy
liczb tutaj): brak partnera do 2026-09-20; 10 skomentowanych PR bez zmiany tekstu; 4 tygodnie sesji
bez decyzji ownera; **E6.7 bez sparowanej korzyści czasu lub sukcesu zadania → nic poza T1**
(ADR-0029 reguła 6). Spełnione kryterium jest zgłoszone ownerowi, nie obchodzone kolejną funkcją.

## `not_measured_here` w syntetycznym runie

`--synthetic` w `pivot_report.py` liczy te same wzory na fabrykowanych plikach, żeby przetestować
kod raportu. Nawet gdy wszystkie sekcje się wypełnią, syntetyczny run **nigdy** nie ustala: że
buyer/decision-maker istnieje; że review minutes odczuwa prawdziwy owner pod presją czasu; że
task success trzyma się poza jednym zbudowanym przez autora zadaniem; że adapter faktycznie
działa w produkcyjnym harnessie, nie w fixture; że rozmowa zakupowa posunęła się choćby o krok;
że decyzja ownera ma realną konsekwencję. To są pytania do ludzi, których dane syntetyczne nie
zamykają (DOCUMENTATION-RULES "Nowe pliki"). Osobno, tool-level `not_measured_here` (bez flagi)
oznacza tylko brak opcjonalnej sekcji wejścia (np. `--cost-json` pominięty, brak `queue` w
usage export) — to inne znaczenie niż powyższe i nie wolno ich mylić w raporcie dla ownera.

## Narzędzie

`tools/pilot/pivot_report.py` liczy wiersze 1–9 z usage export + scoring sheet + opcjonalnego
cost JSON i emituje `run_id`, sha256 wejść i znacznik czasu do odtworzenia raportu
(`tests/test_pivot_report.py`). Nie zastępuje `tools/pilot/analyze.py` (E6.7's własny,
zamrożony pre-registered protokół z 4 warunkami A–D) — służy szerszym porównaniom "z/bez skilli"
i "harness A/B" poza sztywnym schematem E6.7.
