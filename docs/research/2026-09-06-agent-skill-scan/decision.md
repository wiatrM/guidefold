# Decyzja o zamknięciu MVP i kierunku badań

Stan:6 września2026. Zlecenie: porównać istniejący Guidefold z rozmową „Agent Skill Research Scan” i świeżą literaturą, podjąć decyzję w rolach Product Manager/CTO/Project Manager/CEO oraz wykonać spiki naukowe. Późniejsza prośba użytkownika dodała bezpośrednie badanie Field-Aware MLP. To zapis decyzji i dowodów; nie deklaracja wdrożonego MVP lub odbytego pilota.

## Decyzja zespołu agentów

**Domykamy MVP jako T1 remote Go SEARCH/USE z obecnym sparse BM25F, authoring CI i telemetrią. Pierwszy pilot jest nadzorowany, na rzeczywistym repo i w rzeczywistym harnessie. Badanie małego field-aware modelu trwa osobno i nie jest zależnością pilota.**

GO na tę ścieżkę domknięcia; NO-GO na ogłoszenie gotowości dziś, szeroki rollout lub T2. T0 pozostaje istniejącym trybem i może posłużyć do jawnie oznaczonego dogfoodu, lecz nie zastępuje przyjęcia T1. Nie przepisujemy topologii na laptop+model ani nie instalujemy developerom nowych encoderów.

| Rola agenta | Decyzja | Zastrzeżenie, które zmieniło plan |
|---|---|---|
| [Product Manager](product-manager.md) | Wartość to dostawa właściwych instrukcji i feedback autora/ownera. | Brak realnych sesji. Pilot A/B bez czekania na nieistniejącego admitted challengera. |
| [CTO](cto.md) | Istniejący Go/Postgres wykonalny; naprawić/zmierzyć klienta. | Klient nadal liczy lokalny ranking przed odczytem remote. Network deadline nie mierzy całego hooka; NO_SKILL nie jest skalibrowany. |
| [Project Manager](project-manager.md) | Krytyczna ścieżka partner→onboarding→harness→raport→pilot. | Clean-VM, telemetry Bearer, WAN/TLS/IAM i ownerzy nadal otwarte. Jedno źródło statusu issues, nie kolejne równoległe roadmapy. |
| [CEO](ceo.md) | Wartość przed rozbudową; kolejne ograniczone eksperymenty offline na wyraźną prośbę usera, z zachowaniem osobnych protokołów. | Wykonalność techniczna nie dowodzi rynku. Niepewny mały pilot nie dowodzi braku efektu, ale nie uzasadnia rozszerzania. |

## Co naprawdę jest zbudowane

Sprawdzono kod i raporty, nie środowisko produkcyjne. W repo działa single-file Python client, Go SEARCH/USE, Postgres, integer BM25F, mechanika scope i wybranych rewizji, authoring feedback, telemetry ledger. Są dense/hybrid shadow implementacje za flagami; nie potwierdzono, że aktualnie działają w zdalnym wdrożeniu. Dense domyślnie wyłączony. Flat sparse eksperyment również **nie został przyjęty**, ponieważ pogarszał harmful exposure.

Istnieją zapisane dowody parity0/1000, admission97/97, graph446checks i2100consistent responses oraz Go fresh-client loopback p95 około116/136ms przy concurrency1/4. To historyczne raporty inżynierskie, nie pomiar dzisiejszego deploymentu, produkcyjnego hooka ani wartości dla developera. [CTO evidence](cto.md).

Rozmowa błędnie usuwała lokalny BM25 ze stanu kodu: `search_with_backend` wykonuje `_local_selected` na wątku wywołującym przed sprawdzeniem gotowej odpowiedzi serwera. Indeks jest ładowany przed zegarem tej części. Cel pozostaje remote T1, ale „cienki klient bez lokalnej pracy” jest brakującym warunkiem implementacji, nie stanem obecnym. Podobnie limit300ms musi dotyczyć całego procesu, a nie jednego segmentu.

## Porównanie z badaniami i feasibility

Pełna tabela z wersjami i źródłami: [literature.md](literature.md). Pierwszy wykonany eksperyment dotyczył małej wyuczonej fuzji sygnałów pól. Po wyniku user zlecił dalszą pracę, w tym wzbogacanie metadanych i pseudozapytań; bieżący priorytet opisuje [strategia danych](data-and-enrichment-strategy.md). Nie wymaga wytrenowania własnego dużego encodera. Jeżeli używa dense, nadal wymaga query embedding i przechowywania kilku reprezentacji dokumentu; koszt małego MLP nie usuwa tego kosztu.

| Kierunek | Wykonalność | Decyzja teraz |
|---|---|---|
| Remote sparse Go + istniejący Postgres | Wysoka na podstawie kodu/testów; operational acceptance nieukończone. | MVP. |
| Field-aware sparse-only learned fusion | Mały head, bez nowego query-time encodera; wymaga feature export, labels, calibration i parity. | Jeden arm w wykonanym badaniu. Nie przyjęty. |
| Field-aware sparse+dense learned fusion | Mały head; encoder i feature construction dominują koszt. | Badanie offline na lokalnym GPU; w przyszłości wyłącznie po stronie remote. |
| Skill2Query/index-time enrichment | Wykonalne offline; koszty generacji i label leakage wymagają kontroli. | Uruchomiony osobny pilot 512 dokumentów / 2048 zapytań na wyraźną prośbę usera; poza przyjętym MVP. |
| Section hydration / graph compression | Wykonalne, ale poprawność wymaga zachowania preconditions, dependencies, verifiers. | Nie wdrażać na podstawie samego oszczędzania bajtów. |
| Query-time LLM decomposition / cross-encoder | Brak dowodu spełnienia300ms whole-hook; nowy koszt operacyjny. | Nie w krytycznej ścieżce. |
| Własny nowy encoder / dynamiczny knowledge graph | Technicznie możliwe, nieuzasadnione przed wartością i niezależnym testem. | Parkujemy. |

## Wykonane spiki i ich znaczenie

1. **Audyt abstencji i hydration** — [kod i wynik](../../../research/spikes/2026-09-06-cto/README.md). Na istniejących44 syntetycznych no_applicable przypadkach0odmów; każdy otrzymuje karty. To błąd semantyki confidence, nie oszacowanie częstości pomyłek na userach. Przy opcjonalnym4096 budget byte proxy mieści1/26 pełnych bodies. Nie znaczy to, że wszystkie normalne loady są zepsute.
2. **Reanaliza frozen wyników** — [odtwarzanie](../../../research/spikes/2026-09-06-evidence/README.md). Na1250 wspólnych root queries historyczny R1 daje Hit@1 +8,40pp, completeness +1,12pp zCI[-1,12;+3,44]. Wspólny answered subset n1200 odtwarza wcześniejsze+0,67pp. Nie są to sprzeczne liczby; opisują inne mianowniki.215 gold lists przekraczaK4. Na300 distractor cases HSR maleje10pp, ale completeness maleje11pp. Nie przyjmujemy prostego wniosku „dense wygrał/przegrał”.
3. **Moc planowanego pilota** — [dokładny rachunek](../../../research/spikes/2026-09-06-evidence/pilot-power.json).40 niezależnych par przy net+10pp (15%improvement/5%regression) daje17,2%mocy.0harm/40 nadal dopuszcza7,2%harm przy jednostronnej granicy95%.20–40par nadaje się do feasibility; nie gwarantuje rozstrzygającego paperu o efficacy.
4. **Field-aware MLP** — [zamrożony protokół](../../../research/spikes/2026-09-06-field-aware/PROTOCOL.md), [skrypt](../../../research/spikes/2026-09-06-field-aware/run.py).10 123 train skills,2000train queries i1000DEV; generic Qwen3-0.6B, trzy małe heads i porównania. Końcowa tabela i rozstrzygnięcie są w [field-aware-results.md](field-aware-results.md). Nie uruchamiano nowych konfiguracji na frozen test-A/test-B.

## Warunki wejścia do user tests

Pierwsze sesje: zatwierdzony snapshot małego realnego korpusu, kandydaci w kartach i świadomy load właściwej rewizji; obowiązkowe natywne instrukcje zespołu pozostają aktywne. Nie przedstawiamy top4 jako gwarancji kompletu polityk. Rejestrujemy także brak dobrego skilla, odrzucenia kart, brak pobrania i przerwane zadania.

| Priorytet | Wynik do przyjęcia | Odpowiedzialna rola / referencja |
|---|---|---|
| P0 partner | Nazwany developer spoza autorów, repo, owner, zgoda na telemetrykę, termin sesji. | CEO/Product, #78/#80 |
| P0 rzeczywisty transport | Operator z czystej maszyny przechodzi search→selected delivery→USE→ledger; auth/revision/rollback potwierdzone. | CTO, #96–#98 |
| P0 budżet klienta | Pomiar od startu procesu do delivery przez docelową sieć; p50/p95/p99 przyc1/c4, error/timeout/fallback counts.300ms jest targetem, nie wynikiem obecnego audytu. | CTO, #81/#96 |
| P0 semantyka | UI/harness traktuje karty jako kandydatów, NO_SKILL nie jest fałszywie deklarowany; budżet body ma zgodne jednostki i jawny powód odmowy. | CTO/Product, obecny SEARCH/USE scope |
| P0 pomiar | Zdarzenia mają wspólny request/session/revision; brak danych=unknown; load≠successful use. Bearer dla flush przestaje opierać się na adapterze testowym. | CTO/PM, #91/#95 |
| P1 cross-harness | Jedna obserwowana sesja Claude i jedna Copilot find/load; oba ślady zapisane. | Product, #81/#82 |
| P1 authoring | Autor otrzymuje collision/trigger feedback i zapisuje użyteczną poprawkę; owner podejmuje decyzję na raporcie. | Product, #86/#87/#91 |

Numery issues pochodzą z lokalnej dokumentacji; aktualny status GitHub nie był sprawdzany ani modyfikowany. Ten raport nie tworzy drugiego backlogu i nie przypisuje rzeczywistym osobom nowych zobowiązań.

Proponowane E6.7: A=ten sam harness/model i zwykłe instrukcje repo bez Guidefold; B=Guidefold sparse; oracle jako diagnostyczny upper reference. Challenger C dopiero po osobnym przyjęciu. Randomizować kolejność, używać sparowanych niezależnych wykonań taska/warunków, weryfikować rezultat; nie traktować powtórki tego samego zadania przez człowieka jako niezależnej próby. Raportować czas poprawnego wykonania, pass/fail, helpful/harmful flips, utrzymanie adopcji i działanie autora/ownera.20–40par to feasibility,6–9osób/3zespoły to proponowany usability sample. Liczebność badania skuteczności należy wyliczyć z obserwowanej wariancji/discordance i klastrów.

Szacunek PM przy2inżynierach i dostępie:1–2tygodnie do pierwszych sesji,2–4do operacyjnie przyjętego T1. To nie obietnice. Rozbieżność dat można rozwiązać tak:20IX partner;4X wczesny odczyt;18X cztery tygodnie od startu20IX; później formalne E6.7. Nie zmieniono automatycznie historycznych planów. Brak partnera uruchamia istniejącą decyzję stop/narrow, a nie kolejną rozbudowę.

## Paper i walidacja

**Materiał nadaje się na roboczy raport empiryczny. Nie jest jeszcze gotowym paperem dowodzącym nowości algorytmu albo wzrostu produktywności.** Przygotowano [paper-draft.md](paper-draft.md) z istniejącymi licznikami, źródłami i brakami. Najmocniejszy kandydat to audyt rozbieżności ranking→admissibility→kompletność→delivery→outcome, uzupełniony field-aware fusion i badaniem kontraktów/budżetu. Field-aware MLP jest cudzym pomysłem; naszą możliwą wartością publikacyjną jest kontrolowane porównanie i nowy wiarygodny wynik na granicy produktu.

Przed publikacją: niezależna reprodukcja, review AND/OR gold i functional duplicates, matched aggregate token budgets, kilka seedów, świeży holdout, pełny rejestr konfiguracji, whole-hook latency i paired execution jeśli claim dotyczy działania usera. Zamrożonych obejrzanych testów nie nazywać nowymi ślepymi danymi. Ujemne i niepewne wyniki są dopuszczalne; nie zastępujemy ich kolejnym tuningiem do pozytywnego wyniku.

Ocena `validate-data`: **Share with caveats** dla decyzji i wewnętrznego raportu; **Needs revision** dla zgłoszenia naukowego. CTO niezależnie sprawdził reanalizę i wychwycił przed treningiem przeciek DEV dokumentów do negative labels; run został zatrzymany przed wynikami i poprawiony zgodnie z pierwotną intencją protokołu. Nie ma dowodów realnego pilota, WAN SLA ani przyjęcia nowego modelu. Te braki są jawne, nie liczone jako udane testy.

## Dalsza iteracja autoryzowana przez usera

Po negatywnym wyniku field-aware user poprosił o dalsze iteracje i konkretnie o poprawę metadata LLM-em przed pobraniem 30k skilli. Wykonujemy [kontrolowany pilot enrichment](../../../research/spikes/2026-09-06-query-enrichment/PROTOCOL.md), a zakres pierwotnego pojedynczego spike’a nie blokuje tej nowej prośby. [Źródła i metody](query-enrichment-sources.md), [kod autorów i alternatywy MLP](field-aware-implementation-search.md), [diagnoza pierwszego MLP](diagnostics-v2.md) oraz [stanowisko CEO](enrichment-strategy-ceo.md) utrwalają decyzję. Produkcyjny kod i jego kryteria przyjęcia pozostają oddzielną decyzją.

## Końcowy odczyt enrichment

[Wynik i decyzja](query-enrichment-results.md): Recall@10 +0,163 pp na2048 zapytaniach, tylko5 popraw; kompletność +0,146 pp,3 poprawy wyłącznie dla pojedynczego skilla. Próg bootstrap pilota przechodzi, ale dodatkowy dokładny test daje p=0,0625 dlaRecall. Nie przyjmujemy produkcyjnie nowego rankera ani pełnego enrichment. Wykonana druga próba32 dokumentów poprawia mechaniczne przyjmowanie pseudozapytań38→57 oraz puste dokumenty4→1; ocena jakości nie zastępuje osobnego testu retrieval. Kontynuować source-scope quality i kontrolowane badanie, potem learning curve z istniejących etykiet;30k wykorzystać jako późniejszy test skali.

## Aktualizacja po eksperymentach CPU, 6 września 2026

Ukończono sześć wariantów bez GPU. Pełne dopiski zwiększają Recall@10 o 0,0732 pp, bez poprawy kompletności netto; filtr top-10 źródła nie przechodzi zamrożonego progu. Nie ma podstaw do zmiany MVP ani masowej generacji na tej podstawie. Priorytetem badawczym staje się weryfikacja podejrzanych dodatkowych etykiet SKILLRET TRAIN: surowe qrels są strukturalnie spójne, ale znaleziono konkretne semantyczne rozbieżności. Przygotowano 120 zapytań do niezależnej oceny; ocen jeszcze nie wykonano. [Wyniki CPU](cpu-enrichment-controls.md), [audyt danych](skillret-train-label-audit.md).
