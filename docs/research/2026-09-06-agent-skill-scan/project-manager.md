# Guidefold: domknięcie MVP — raport Project Managera

Data: 2026-09-06. Analizowany checkout: `dfe9e4d4d6eb1536d35ef89493aa2725215a25f1`.

## Rekomendacja

Domykamy istniejący produkt: T0/T1 z referencyjnym BM25F, cienki klient, Go SEARCH/USE, authoring CI i raport dla właściciela skilli. Pierwszą bramką jest rzeczywista sesja dewelopera w partnerskim repozytorium. Model, composer, worker GPU i portal nie są warunkiem rozpoczęcia testów użytkowników.

T1 jest technicznie wykonalny: istnieją wyniki zgodności z CLI oraz opóźnień z zapasem na loopback. Gotowość do zewnętrznego pilota pozostaje warunkowa: nie wykazano uwierzytelnionego przepływu harness–service przez docelową sieć ani instalacji przez innego operatora. Jeżeli T1 nie przejdzie bramek, testy wartości można rozpocząć na T0, oznaczając wykorzystany tier i jego ograniczenia.

To ocena artefaktów repozytorium, bez ponawiania testów, pomiarów modeli lub sesji użytkowników. Numery issues pochodzą z lokalnego `docs/BACKLOG.md`; bieżącego statusu GitHub Issues nie zweryfikowano w tym raporcie. Nie ogłaszamy zakończenia pilota ani akceptacji publikacji naukowej.

## 1. Aktualny zakres i rozjazdy planowania

Najświeższe zaakceptowane decyzje znajdują się w [ADR-0029](../../adr/ADR-0029-product-focus-hard-rules.md) i [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md). README, część `docs/MVP.md` oraz CONTRIBUTING opisują starszy stan; np. dokumentują testy jako planowane, mimo istniejącego katalogu testów i workflow CI. Nie należy estymować prac z README.

ADR-0029 zamraża nowe komponenty runtime i utrzymuje jedną rodzinę badań — Family E, do sześciu konfiguracji dev, test-once dla zamrożonego wariantu. Istniejący TEI/GPU shadow jest zaparkowany; oznaczenie „shadow” nie czyni dalszej budowy elementem MVP. Nowa prośba właściciela o analizę i spiki uzasadnia niezależne audyty istniejących wyników, ale nie wymaga uzależnienia pilota od nowego retrievera.

| Data z aktualnych dokumentów | Interpretacja do utrzymania w backlogu |
|---|---|
| 2026-09-20, M1 | Partner i pierwsze rzeczywiste sesje: Claude Code oraz jawne `find`/`load` w Copilot. Brak partnera uruchamia istniejące stop-building z PRODUCT-FOCUS. |
| 2026-10-04, cel PRODUCT-FOCUS | Minimum 20 rzeczywistych sesji i pierwsza decyzja właściciela z raportu. To nie oznacza czterech tygodni obserwacji przy starcie 09-20. |
| 2026-10-18, M2 | Cztery tygodnie obserwacji od startu 09-20, raportowanie i przyjęcie T1 po sieci, jeśli bramki przejdą. |
| 2026-11-15, M3 | Cel decyzji E6.7, zależny od trzech zespołów i banku zadań; nie gwarancja mocy statystycznej. |

## 2. Co jest dowodem, a co pozostaje otwarte

| Obszar | Istniejący dowód | Wniosek dla zamknięcia |
|---|---|---|
| Ranking T0/T1 | [BM25F parity](../../reports/bakeoff/validation/router-bm25f-parity.json): 1000/1000 HTTP OK, 0 rozbieżności rankingu, integer scores, wyboru i rewizji; [structured-corpus report](../../reports/bakeoff/PARITY-STRUCTURED-CORPUS-2026-09-05.md): 0/243 | Zachować bramki. To równoważność implementacji, nie dowód wartości dla użytkownika. |
| T1 opóźnienia | [BM25F report](../../reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md): fresh-client p95 115,811/135,636 ms przy c1/c4; 800/800 żądań | Sparse ma podstawy do integracji. WAN/TLS/IAM i pojemność docelowej VM pozostają niemierzone. |
| Telemetria | [Postgres evidence](../../reports/bakeoff/validation/t1-telemetry-postgres.json): 210 eventów, pierwszy flush 210 accepted, replay 210 duplicates, zgodne raporty SQLite/Postgres | To lokalny test 20 find/5 load, nie 20 sesji użytkowników. Artefakt ma `production_ready: false` i testowy adapter credentials. |
| Instalacja i transport | [Runbook T1](../../../deploy/t1/README.md) przyznaje brak clean-VM acceptance, docelowego ingressu oraz Bearer w CLI `telemetry flush` | #93 i #96–#98 nie mogą zostać zamknięte lokalnym smoke testem. |
| Authoring loop | Workflow CI, PR #65 w PRODUCT-FOCUS; istnieją collision report i trigger suggestions | Uruchomić w repo partnera i zmierzyć reakcję autora. Raport jest informacyjny; blocking snapshot quality gate #87 pozostaje oddzielnym zadaniem. |
| Pilot | [E6.7 protocol](../../pilot/E6.7-PROTOCOL.md), bank/arkusz template, `tools/pilot/analyze.py` i testy analizatora | Protokół ma placeholdery i brak SHA freeze. Istnienie analizatora nie jest wynikiem pilota. |

## 3. Minimalny zakres przyjęcia do user tests

1. Jedno nazwane repo partnera, deweloper spoza autorów Guidefold i właściciel skilli, który przeczyta raport. Data startu, warunki dostępu, zakres danych i sposób zgłaszania problemów (#78).
2. Inny operator przechodzi `init` i `doctor` na tym repo w mniej niż 30 minut (#79–#80). `find` pokazuje ranking istotności, `load` pobiera wskazaną niezmienną rewizję (#84).
3. Pełna rzeczywista sesja Claude Code z poprawnymi kartami; następnie Copilot z explicit `find`/`load`. Capability matrix opisuje zaobserwowane ograniczenia (#81–#83). Hook template nie wystarcza jako dowód integracji.
4. SEARCH → delivery → load daje się powiązać z sesją i rewizją. Brak observed use pozostaje brakiem obserwacji; load nie oznacza „skill pomógł”. Spool jest ograniczony, flush poza hookiem, retry nie duplikuje danych (#91–#94).
5. W repo partnera działa informacyjny authoring report. Właściciel dostaje raport skilli i odnotowuje decyzję albo powód braku działania (#85, #88, #90, #95).
6. Dla T1: czysta VM, uwierzytelniony harness przez realną sieć, p95 klienta ≤400 ms i serwera ≤300 ms w zamrożonym obciążeniu c1/c4, jawne timeout/fallback/error counts, snapshot rollback i odtworzenie backupu (#93, #96–#100). Przekroczenie nie oznacza automatycznego podniesienia budżetu.

Do pierwszych sesji nie są konieczne: nowa baza, worker, UI, registry GCP, automatyczna promocja/lifecycle, trening, adaptery Codex/Gemini, k8s ani T2. Snapshot quality gate #87 należy domknąć przed regularnymi aktualizacjami wspólnego katalogu podczas pilota; pierwsza sesja może działać na ręcznie zatwierdzonym, przypiętym snapshotcie.

## 4. Kolejność, role i szacunki

Założenie z MVP: dwóch inżynierów i 0,5 etatu ML, dostęp operatora i partnera. Roboczodni poniżej są szacunkami pracy zespołu; nie obejmują oczekiwania na dostęp i rekrutacji.

| Priorytet / issues | Praca i zależność | Rola | Szacunek | Reviewable exit |
|---|---|---|---|---|
| P0 / #78, #102, #104 | Nazwać partnera, operatora, ownera raportu i osoby od pilota; od razu | CEO/sponsor + Product | 0,5–1 dnia przygotowania; czas odpowiedzi zewnętrzny | Karta partnera, dostęp, terminy i właściciele. |
| P0 / #79–#84, #89, #101 | Usunąć tarcie onboardingowe, potwierdzić ranking, uruchomić harnessy; próby zależą od #78 | Inżynier klienta | 4–7 dni | Timed onboarding, dwa typy realnych sesji, capability matrix. |
| P0 / #91–#94 | Sesja→raport, bounded spool, autoryzowany flush, dane i retention | Inżynier serwisu + klient | 3–5 dni; transport zależy od #97–#98 | Realne eventy, raport, lag/loss, replay i deletion checks. |
| P1 / #85–#90 | Authoring report w CI partnera, dokument dla autora, quality gate | Klient + 0,5 ML | 3–5 dni | PR i reakcja autora; regresja dev blokuje snapshot swap. |
| P1 / #96–#100 | Czysta VM→TLS/IAM→harness, rollback/restore, parity | Serwis + operator | 5–9 dni po dostępie | Dowody z docelowej maszyny/sieci i limity wspieranego T1. |
| P1 / #95 | Cotygodniowy raport i rejestr decyzji | Skill owner + Product | Założenie 0,5–1 h/tydzień/owner | Decyzja z datą, rewizją, uzasadnieniem i dalszym działaniem. |
| P2 / #102–#107 | Zamrozić protokół, dry-run pięciu zadań, pilot | Product + ML + PM | 3–5 dni przygotowania/analizy + czas uczestników | SHA protokołu/banku, wyniki kontrastów, CI, failures, unknowns. |

Przy dwóch inżynierach przygotowanie techniczne pierwszego partnera szacuję na 1–2 tygodnie, a T1 do zewnętrznych testów na 2–4 tygodnie przy sprawnym dostępie. Research nie jest składnikiem tych estymacji. Pierwsza próbka może działać na T0, gdy T1 pozostaje w pracy.

Project Manager prowadzi jeden rejestr blokad i dowodów zamknięcia issues. CTO odpowiada za wydanie i bramki operacyjne. Product Manager odpowiada za task bank i decyzję o wartości. CEO/sponsor zapewnia partnera i podejmuje stop/narrow po kill criteria; nie zastępuje wyników własnym przekonaniem.

## 5. Pilot wymaga dopasowania do MVP

E6.7 ma dwa kontrasty główne, w tym contender C, lecz [composer freeze](../../reports/bakeoff/validation/dev-composer-freeze.json) ma `deterministic: null` i `model: null`; nowy dense default także nie jest przyjęty. Nie należy opóźniać pilota, aby stworzyć C.

Przed pierwszym freeze rekomenduję zrewidować protokół: główny kontrast A = bez skilli i B = obecny sparse; oracle D służy diagnostyce treści i niewykorzystanego potencjału. C powstaje dopiero dla nazwanego, dopuszczonego kandydata w oddzielnie zamrożonym badaniu. Analizator i template muszą odpowiadać tej decyzji; ten raport sam ich nie zmienia.

20–40 zadań to pilot wykonalności, nie automatycznie mocne potwierdzenie produktywności. Cztery pełne warunki oznaczają 80–160 wykonań; A/B daje 40–80 wykonań plus ustalona próbka oracle. To liczba wykonań, nie roboczogodzin; zadania mają tylko limit ≤60 minut. Przed freeze trzeba policzyć dostępność uczestników. Raportujemy sukces, czas, koszt i unknowns; mała próbka bez istotności nie dowodzi braku efektu.

Kill criteria z PRODUCT-FOCUS: brak partnera do 09-20; zero zmian po dziesięciu skomentowanych PR-ach; brak decyzji ownera po czterech tygodniach; T1 poza budżetem sieciowym; brak przekonującego efektu w pilocie. Każde uruchamia określone zawężenie, nie kolejny komponent.

## 6. Gotowość do osobnego paperu

Istnieje materiał na pracę empiryczną i pakiet reprodukowalności; nie ma kompletnego paperu z potwierdzoną nowością ani dowodu wartości użytkowej. Wiarygodny kierunek to audyt rozbieżności między benchmarkiem, produkcyjną ścieżką routingu i kryteriami wdrożenia. Go/Postgres, fixed-point BM25F lub transfer gap nie stanowią automatycznie nowego wkładu naukowego.

Warto zachować:

- [DENSE-PROGRAM](../../reports/bakeoff/DENSE-PROGRAM.md), jawne negatywy i brak przyjęcia konfiguracji, zamiast tabeli samych zwycięzców.
- Dwa zbiory z revision/SHA, [corpora manifest](../../reports/bakeoff/validation/corpora-manifest.json), zamrożony dev, gzip JSONL per query i summary JSON.
- R1 `all_required@4` +17,96 pp [16,80; 19,08] na test-A i +0,67 pp [−1,50; 2,83] na test-B. Osobno poprawę hit@1 i spadek HSR na test-B; „dense nie działa” byłoby niezgodne z materiałem.
- Rozdzielenie rankingu i wyboru kart, audyty metryk, eligibility oraz dokładną zgodność T0/T1.
- Family D: completeness zyskuje kosztem hit@1 i kosztu. C-model-2 +4 pp [0; 8] na n=150 pozostaje nierozstrzygnięta, nie dowodzi negatywnego efektu.

| Brak przed submission | Dlaczego blokuje mocniejszy wniosek | Minimalne domknięcie |
|---|---|---|
| Teza i kontrola literatury | Raporty inżynierskie nie są jeszcze nowym wynikiem | Claim–evidence–related work; rozdzielić replikację, obserwację i wkład. |
| Jednolity manifest wykonania | Raporty dotyczą różnych commitów, populacji i timingów | Każdy wiersz tabeli wiąże się z kodem, config, modelem, danymi, seed, hardware, raw result i komendą. |
| Interpretacja transferu | Zbiory różnią się etykietami/zakresem/dystrybucją, train overlap modelu nie jest wykluczony | Transfer gap jako obserwacja; nie przypisywać wyłącznie domain shift bez kontrolowanego badania. |
| Przyczynowość completeness | Zero przy k=3 nie dowodzi, że jedynie composer pomaga; candidate recall też ogranicza wynik | Audyt candidate ceiling i matched-budget ranking/selection. Mechanizmy niepotwierdzone pozostają hipotezami. |
| Statystyki i rejestr prób | Oglądane testy, wiele rodzin/podzbiorów zwiększają swobodę interpretacji | Pełny rejestr prób, mianowniki, multiplicity i CI; reanaliza nie udaje nowego holdoutu. |
| Niezależna reprodukcja | Własne środowisko, często współdzielone WSL | Drugi operator odtwarza zamrożone tabele; braki caches/model CLI są oznaczone. |
| Utility w realnym repo | Retrieval i loopback nie odpowiadają, czy pomaga deweloperowi | E6.7 jako osobny rozdział lub przyszłe badanie; brak user study zawęża tezę. |

Tanie spiki poza krytyczną ścieżką: (1) pokrycie i hashe artefaktów; (2) ponowne wyliczenie tabel/CI z istniejących per-query records bez strojenia; (3) candidate ceiling i wpływ budżetu/wyboru jako analiza eksploracyjna; (4) analizator pilota na jawnie syntetycznych danych pod kątem mocy i accounting. Wyniki syntetyczne potwierdzają zachowanie narzędzia, nie przydatność Guidefold.

Audyty to szacunkowo 2–4 roboczodni ML/research. Dopuszczalnym wynikiem jest „materiał na technical report/workshop; potrzeba niezależnego zbioru do mocniejszej tezy”. Family E pozostaje jedynym torem zmiany modelu. Jej powodzenie nie jest potrzebne do wartościowej publikacji negatywów i nie może blokować partnera.

## Decyzja PM

Przyjąć T0/T1 sparse + authoring + telemetry. Otworzyć rzeczywiste użycie po pierwszej demonstracji całego przepływu; T1 przyjąć warunkowo po bramce sieciowej. Po czterech tygodniach rozliczyć decyzje ownerów. Paper prowadzić jako osobny pakiet dowodowy z ograniczonym budżetem i tezą dobraną do wyników. Największe ryzyko obecnie to partner i integracja, a nie brak nowego retrievera.
