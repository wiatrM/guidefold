# CEO — decyzja portfelowa o MVP i badaniach

Data: 2026-09-06. Rola: sceptyczny przegląd decyzji Product Managera, CTO i Project Managera. To decyzja o kierunku i warunkach przyjęcia, nie deklaracja gotowego wdrożenia, odbytych sesji ani zaakceptowanego paperu. Numery issues są lokalnymi referencjami; ich status live nie został sprawdzony.

## Głos CEO

**GO na domknięcie istniejącego T0/T1 sparse, authoring CI i raportowania oraz na nadzorowane testy po spełnieniu bramki wejścia. NO-GO na ogłoszenie MVP gotowym dzisiaj, szeroki rollout, T2 i nowe komponenty runtime.**

Wąskie gardło biznesowe to brak potwierdzonego użytkownika, dostawy w rzeczywistym harnessie i decyzji ownera. Wąskie gardło techniczne obejmuje również klienta: odpowiedź zdalna czeka na lokalny scoring; szybki Go service nie dowodzi cienkiego hooka ani 300 ms end-to-end.

Nowe, jawne wskazanie przez użytkownika Field-Aware Agent Skill Retrieval oraz prośba o zbadanie małego MLP uzasadniają jeden ograniczony eksperyment offline opisany w osobnej prerejestracji. Traktuję to jako aktualną autoryzację konkretnego badania ponad wcześniejsze zamrożenie, a nie zgodę na przyjęcie modelu do produktu, nową infrastrukturę lub przesuwanie pilota. Wynik eksperymentu nie jest jeszcze znany w chwili zapisu tego memo.

## Gdzie może powstać wartość

Klientem pozostaje Platform/DevEx utrzymujący instrukcje wielu zespołów i harnessów. Pierwszy test sprawdza, czy konkretny developer otrzymuje właściwą, aktualną instrukcję i wykonuje zadanie lepiej lub szybciej, a owner na podstawie śladów poprawia zbiór. Nie mamy jeszcze dowodu gotowości do zapłaty ani powtarzalnego zapotrzebowania.

Rozliczamy dwie powiązane hipotezy:

1. Dystrybucja instrukcji pomaga w zadaniu. Ranking, wyświetlenia i pobrania są sygnałami pośrednimi.
2. Raport autora i ownera poprawia utrzymywane instrukcje. Raport bez decyzji lub komentarz bez użytecznej zmiany nie potwierdzają tej wartości.

**Zastrzeżenie CEO:** wysoka wykonalność techniczna nie oznacza wysokiej wykonalności biznesowej. Nazwany owner, repo, operator i realny termin ważą dziś więcej niż kolejne punkty Recall@1. Cross-harness musi zostać wykazany w dwóch rzeczywistych przepływach, nie wywnioskowany z dwóch konfiguracji.

## Zakres, który przyjmujemy do zamknięcia

| Element | Decyzja i warunek |
|---|---|
| T1 Go SEARCH/USE + obecny BM25F | Utrzymać. Zmierzyć rzeczywisty klient, docelową sieć, auth, walidację rewizji i load. |
| T0 | Dopuszczalny do pierwszego małego pilota, jeśli T1 czeka na środowisko. Zapisać wielkość korpusu i zmierzony tier; nie zaliczać tego jako dowodu T1. |
| Claude Code i Copilot CLI | Pierwsza obserwowana sesja w Claude, potem jawne find/load w Copilot. Obietnica wspólnej warstwy dopiero po obu dowodach. |
| Karty i body | Kandydaci i jawna/wybrana dostawa zatwierdzonej rewizji. Zachować standardowe, obowiązkowe instrukcje repo i harnessu. |
| NO_SKILL | Nie deklarować skalibrowanej odmowy. Włączyć zadania bez pasującej instrukcji i mierzyć zbędne karty oraz odrzucenia. |
| Authoring CI | Informacyjny raport i reakcja autora. Pierwsza nadzorowana sesja może używać zatwierdzonego snapshotu; regularne zmiany katalogu wymagają bramki jakości. |
| Telemetria | Powiązać search, dostawę, load i oceniony outcome. Brak danych pozostaje unknown; load nie oznacza wykonania ani korzyści. |
| Dense/MLP, kompresja sekcji, nowy composer | Offline research. Nie są warunkiem sesji; nie przyjmujemy ich do runtime na podstawie DEV. |

CTO potwierdził w dyskusji: hook dostarcza karty/digests, a USE hydratuje body. Ranking i budżet nie gwarantują dostarczenia całego zbioru obowiązkowych polityk. Pilot nie może zastępować natywnych reguł opcjonalnym retrievalem. Stały snapshot z rollbackiem wystarczy dla pierwszej nadzorowanej sesji w uzgodnionym środowisku po kontroli dostępu, checksum i rewizji; nie stanowi dowodu gotowości szerokiego wdrożenia.

## Bramki i rozstrzygnięcia

| Moment | Dowód | Decyzja przy braku |
|---|---|---|
| Wejście do pierwszej sesji | Partner/repo/developer spoza twórców/owner/data policy; operator przechodzi runbook; realne search→delivery→load→event; kontrola rewizji, dostępu i rollback | Przygotowanie trwa; MVP nie jest przyjęte. |
| Do 2026-09-20 | Nazwany partner i start, referencja #78 | Zgodnie z PRODUCT-FOCUS zatrzymać budowę funkcji; własne repo jako jawny dogfood albo stop. |
| Przyjęcie T1 | Cały proces klienta przez rzeczywistą sieć i TLS/IAM; p50/p95/p99, c1/c4, timeout/fallback/error counts; bramki #96–#98 | T1 pozostaje nieprzyjęty. Mały T0 pilot może postępować w swoim zmierzonym zakresie. |
| Cztery tygodnie | Minimum 20 sesji niezależnego developera i co najmniej jedna udokumentowana decyzja ownera; wyniki zadań osobno | Nie rozbudowywać telemetryki jako produktu bez decyzji ownera. Eventy nie są dowodem wartości. |
| Dziesięć rzeczywistych PR | Użyteczne zmiany oraz uzasadnione odrzucenia | Zero zmian uruchamia zawężenie authoring do lintera według istniejącego kill criterion. |
| E6.7, 20–40 par | Zamrożony A/B, zaślepiona ocena, rescue/regress, czas/koszt, przedziały i unknowns | Niejednoznaczność blokuje T2 i szeroki claim; obiecujący wynik może uzasadnić policzone większe badanie. |

Baseline A oznacza **Guidefold wyłączony przy zachowaniu zwykłych instrukcji zespołu i harnessu**. Sformułowanie „bez skilli” nie może oznaczać usunięcia normalnego wsparcia. B to obecny sparse. Oracle diagnozuje lukę treści/retrievalu; brak dopuszczonego challengera C nie opóźnia A/B. Protokół i analizator trzeba zmienić spójnie przed freeze.

Przy 20–40 parach brak istotności nie dowodzi braku efektu. Dzisiejszy eksploracyjny audyt mocy wskazuje około 17,2% mocy dla n=40 przy 15% poprawionych i 5% pogorszonych par. Nawet 0 szkód na 40 daje jednostronną górną granicę 95% około 7,2%, przy niezależnych obserwacjach; klastrowanie po developerze/zespole może dodatkowo osłabić dowód. Mały pilot rozstrzyga używalność, wykonalność i wartość dalszego pomiaru.

Kalendarz: 09-20 partner/start; 10-04 wcześniejszy odczyt minimum sesji i decyzji; 10-18 pełne cztery tygodnie przy starcie 09-20; 11-15 warunkowy cel E6.7. Cel 10-04 nie oznacza czterotygodniowej obserwacji przy starcie 09-20. Późniejszy start jawnie przesuwa okno. Aktualny milestone issue wymaga weryfikacji przed aktualizacją zdalnego planu.

## Co zmienia literatura

Sprawdzono strony i abstrakty publikacji 2026-09-06. Szczegółowa kontrola metod należy do wspólnego raportu. Poniżej konsekwencje portfelowe, nie deklaracja replikacji.

| Publikacja | Znaczenie |
|---|---|
| [Field-Aware Agent Skill Retrieval, v3](https://arxiv.org/abs/2608.02880v3) | Oddzielne pola i mały MLP są konkretnym challengerem. Nasz BM25F rozróżnia pola, lecz nie replikuje ich modelu. Zysk na ich benchmarkach nie przyjmuje modelu do naszego kontraktu. |
| [Skill2Query](https://arxiv.org/abs/2608.16071v1) | Grounding pytań w strukturze skilla wspiera badanie treści i sygnałów retrievalu. Pseudo-query nie zastępują niezależnych zadań użytkowników; nie dokładamy dziś generatora do runtime. |
| [Skill Following](https://arxiv.org/abs/2609.00549v1) | Same-task matched outcomes i rescue/regress są ważniejsze dla decyzji niż aggregate lift. Analiza warunkowa po pobraniu jest uzupełnieniem; pełny A/B nadal uwzględnia wszystkie przydzielone zadania. |
| [SkillZip](https://arxiv.org/abs/2608.05604v1) | Kompresja sekcji z zachowaniem kontraktu to odrębna złożona hipoteza. Nie wynika z niej, że bezpiecznie można ciąć body po nagłówkach; najpierw mierzymy limity pilota. |

Wniosek CEO z tych źródeł: pilna aktualizacja dotyczy pomiaru i prerejestracji. Jawna prośba użytkownika dodaje ograniczony eksperyment MLP, nie zmienia topologii wdrożenia.

## Osobny paper

**GO na reprodukowalny raport i szkic paperu; NO-GO na claim SOTA, poprawy produktywności lub potwierdzonej nowości.** Kandydatem jest praca empiryczna o rozbieżności między rankingiem, pełnym dopuszczalnym zbiorem instrukcji, dostawą i użytecznością. Samo BM25F, RRF i Go/Postgres nie wystarcza na wkład naukowy.

Dzisiejszy audyt wzmacnia temat, ale ogranicza obecne narracje:

- Reanaliza historycznego test-B R1 na wszystkich 1250 przypadkach: Hit@1 +8,4 pp [5,76; 11,12], all_required@4 +1,12 pp [-1,12; 3,44]. Historyczne +0,67 pp dotyczy wspólnej populacji 1200 odpowiedzi. To różne mianowniki.
- 215/1250 gold sets ma więcej niż cztery elementy. Przy cap=4 kompletność jest tam konstrukcyjnie niemożliwa. Pokazać wszystkie przypadki i jawnie nazwany podzbiór mieszczący się w budżecie; nie usuwać trudnych zadań, żeby poprawić headline.
- Spadek HSR przy słabej zmianie kompletności i jej regresji w podgrupie distractor nie wspiera prostego „dense nie działa” ani „dense wygrywa”.
- CTO odtworzył 0/44 odmów na syntetycznych no_applicable. RRF tłumaczy problem interpretowania rank-score jako pewności, ale fixture nie estymuje produkcyjnego false-positive rate.
- Byte proxy hydration i lokalny scoring przed odbiorem remote ujawniają granice kontraktu oraz timingów. Są ważne dla reprodukowalności, lecz nie dowodzą nowej ogólnej metody.

Przed mocniejszą publikacją: jeden manifest kod/dane/model/seed/komenda dla każdego wyniku, pełny rejestr prób, brak mieszania obejrzanych testów z nowym holdoutem, matched-budget porównania, niezależna reprodukcja i jawna relacja do literatury. Pilot może dostarczyć osobnego rozdziału; paper nie wymaga wymyślenia pozytywnego wyniku ani opóźnienia partnera.

Autoryzowany MLP spike kończy się tabelą DEV dla prerejestrowanych baselines i małych heads, kosztem i decyzją continue/stop. Dodatni DEV nie dowodzi generalizacji; potrzebny jest osobny plan niezależnego testu z uwzględnieniem obejrzanych korpusów. Wynik negatywny lub niejednoznaczny zapisujemy, bez automatycznej eskalacji do kolejnych modeli.

## Odpowiedzialność i zakres

CEO/sponsor odpowiada za partnera i stop/narrow; Product za pytanie oraz wartość; CTO za przepływ, rewizje i budżet; Project Manager za jeden plan i dowody przyjęcia. Szacunki PM 1–2 tygodnie do pierwszych sesji oraz 2–4 do T1 zależą od dwóch inżynierów i dostępu. Nie są datą obiecanego wdrożenia.

Przegląd nie uruchamiał kontaktu z partnerem, wdrożenia, publikacji ani zmian zdalnych issues. Referencje do kolejnej pracy: #78, #80–#82, #91, #95–#98 i #102–#107. Prośba użytkownika autoryzuje audyt i izolowane spiki; runtime pozostaje zamrożony.

## Źródła lokalne

- [Product Manager](product-manager.md), [Project Manager](project-manager.md), [CTO](cto.md).
- [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md), [ADR-0029](../../adr/ADR-0029-product-focus-hard-rules.md).
- [Reanaliza artefaktów](../../../research/spikes/2026-09-06-evidence/audit-results.json), [audyt mocy](../../../research/spikes/2026-09-06-evidence/pilot-power.json).
- [Spike CTO](../../../research/spikes/2026-09-06-cto/README.md), [wyniki CTO](../../../research/spikes/2026-09-06-cto/results.json).
