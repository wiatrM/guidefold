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

## Aneks: fresh evidence po pullu, 8 września 2026

Wykonano git pull --ff-only na bieżącej gałęzi roboczej. Nie było
nowych commitów z origin; lokalne zmiany innych agentów zostały zachowane.
Poniższy aneks aktualizuje rekomendację badawczo-pilotażową na podstawie
późniejszych, zapisanych artefaktów. Nie usuwa ani nie przepisuje decyzji
operacyjnej z 6 września.

Nowe kontrole zawęziły hipotezy:

- dokładna optymalizacja wszystkich trójek po zablokowaniu pierwszego wyniku
  dała +1,98 pp Complete@4 na R3, lecz -0,25 pp na source-disjoint; dodatkowy
  wariant +0,70 pp nie przechodzi bramki +2 pp, więc greedy selector pozostaje
  prosty i lokalny;
- routing taksonomiczny z prawdziwym LLM był lepszy od centroidu przy 6 szerokich
  kategoriach, ale nadal 16 pp poniżej flat dense all-gold@20; przy 18 kategoriach
  przewaga zniknęła, dlatego routing jako generator kandydatów zamknięto;
- card-first progressive disclosure na 75 zadaniach i 70 skillach rozszerzało
  kontekst w 97,1% trudnych i 0% łatwych przypadków, a na zadaniach
  card-sufficient oszczędzało 86,3% tokenów treści. Wynik 9,3% blended zależy
  od sztucznego miksu i nie jest prognozą wdrożenia. Niezależne replaye wszystkich
  trzech kontroli mają status PASS.

**Zaktualizowana decyzja dla następnego pilota:** przygotować dense SKILLRET jako
główny generator kandydatów, trzymać cross-encoder w shadow/top-1, używać
source-disjoint fixed set selector tylko dla próśb wieloskillsowych oraz
włączyć card-first loading z telemetryką rozszerzeń, provenance i rewizji.
Sparse Go/BM25F pozostaje kompatybilnym fallbackiem i punktem odniesienia.

To jest rekomendacja konfiguracji badawczo-pilotażowej, nie automatyczna akceptacja
nowego runtime. Przełączenie produkcji i twierdzenie o poprawie pracy developera
nadal wymagają pomiaru całego hooka, niezależnego testu semantycznego, paired
skill/no-skill execution, safety/closure oraz realnego pilota. W szczególności
nie przyjmujemy taxonomy routing, late interaction, adaptive top-50 ani brute-force
global subset search do ścieżki domyślnej.

Źródła surowe i niezależne weryfikatory:
[set objective](../../../research/set-objective-transfer-2026-09-07/README.md),
[LLM pyramid](../../../research/pyramid-routing-llm-2026-09-07/README.md),
[progressive disclosure](../../../research/progressive-disclosure-execution-2026-09-07/README.md),
[fresh synthesis](../../../research/fresh-evidence-2026-09-08/README.md).

## Aktualizacja: proof before load, 8 września 2026

Niezależny replay świeżych przebiegów GPU jest PASS dla trzech artefaktów:
LNSR (3×1000, source-heldout), ALNR (3×1000) i positional multi-view (1000).
LNSR przeucza się na train (100% trafień), lecz na source-heldout spada do
Hit@1 4,8%, Recall@10 15,4% i Complete@4 7,9%; ALNR pozostaje praktycznie
remisem z dense (+0,3 pp Complete@4), a multi-view podnosi Hit@1 o 1,4 pp
kosztem Complete@4 (-0,9 pp) i all-gold@50 (-1,3 pp). Żaden z tych rankerów
nie wchodzi do produktu. Weryfikator i hashe są w
[fresh-gpu-verification-2026-09-08.json](../../../research/fresh-gpu-verification-2026-09-08.json).

Zamiast kolejnej funkcji podobieństwa powstał badawczy prototyp **Evidence-
Carrying Capability Routing (ECCR)**. Zapytanie jest kontraktem wymagań, skill
ma ledger dowodów z dokładnymi liniami źródła, a `LOAD` jest dozwolone wyłącznie
przy pełnym pokryciu każdego obowiązkowego wymagania i zgodności zakresu
obiektu. W przeciwnym razie system zwraca `ASK`, brakujące wymagania i pytania
otwarte. Na zamrożonym, wcześniej ocenionym pakiecie 12 przypadków polityka
oracle’owa uzyskała 6 pełnych, źródłowo wspartych LOAD (100% precision wśród
LOAD) i 6 jawnych ASK, wobec 2/12 pełnych top-1 oraz 12 unsupported wymagań w
top-1 bez bramki. Automatyczny Qwen z adresami linii dał 3 LOAD i 9 ASK; po
deterministycznym claim-to-line guard wszystkie trzy LOAD zgadzały się z
dostępnym review oracle, a błędne przypadki `phi` i ogólny CAD zostały
zatrzymane. To jest przełom w kontrakcie bezpieczeństwa i obserwowalności
produktu, nie claim uniwersalnej poprawy retrieval ani wykonania. Artefakty,
protokół i kod są w
[evidence-carrying-capability-routing-2026-09-08](../../../research/evidence-carrying-capability-routing-2026-09-08/README.md).

Niezależny Haiku z tą samą bramką scope dał 2 LOAD i 10 ASK, a ścisły
dual-assessor consensus 1 LOAD i 11 ASK; ten jeden LOAD również był pełny w
dostępnym review. Zgodność modeli nie jest dowodem prawdy, ale pokazuje, że
bramka potrafi wymusić abstencję bez dostępu do etykiet gold.

Następny test powinien zamrozić większy source-disjoint pakiet, automatycznie
zbudować capability ledger w indeksie i wykonać paired skill/no-skill execution.
Do tego czasu ECCR pozostaje ścieżką badawczą; domyślne MVP i dense shadow nie
zmieniają się.

## Aktualizacja: anchor-preserved decomposition, 8 września 2026

Kolejna iteracja nie miesza już ślepo rankingów. Powstał operator **Anchor-
Preserved Decomposition (APD)**: globalny ranking zachowuje pierwszy element
(albo ustalony prefiks), a lista dekompozycji może dopiero potem rozszerzyć
ogon. Jest to jawna własność algorytmiczna, nie parametr wyuczony z etykiet:
`APD_a(B,A)[:a] = B[:a]`. W szczególności pomocniczy LLM nie może wprowadzić
nowego błędu rank-1. Dodatkowy selektor **Anchor-Constrained Greedy Coverage
(ACGC)** uzupełnia trzy wolne miejsca, maksymalizując stały, monotoniczny
submodularny cel złożony z użyteczności pozycji i pokrycia klauzul. Nie używa
gold podczas wyboru, a jego klasyczna gwarancja `(1−1/e)` dotyczy tego celu.

Na 1 000 zapytań source-heldout zapisany replay dał APD-1: Hit@1 71,00%
(dokładnie tyle co D0), Recall@10 65,37% wobec 58,18% D0 (+7,18 pp; bootstrap
95% CI [+5,62; +8,73]) oraz `all_required@4` 32,30% wobec 29,90% (+2,40 pp;
CI [+0,80; +4,00]). ACGC-1 zachował tę samą kotwicę i osiągnął 34,20%
`all_required@4` (+4,30 pp; CI [+2,60; +6,00]) oraz Recall@10 65,40%.
Niezależny verifier przeliczył metryki i sprawdził niezmienność prefiksu w
1 000/1 000 wierszy. Artefakty, protokół i hashe są w
[anchor-preserved-decomposition](../../../research/anchor-preserved-decomposition-2026-09-08/README.md).

To jest pierwszy kandydat na własną metodę, ponieważ wnosi kontrakt
bezpieczeństwa rankingu i optymalizację pokrycia, zamiast kolejnej funkcji
podobieństwa. Wynik pochodzi jednak z zapisanych wyjść DEV, bez nowej inferencji
LLM i bez pomiaru wykonania zadania. APD/ACGC nie wchodzą automatycznie do MVP;
następny krok to zamrożony zewnętrzny test, niezależna adjudykacja relewancji i
paired skill/no-skill execution.

## Synteza metody: proof-preserving anchor-cover routing, 8 września 2026

APD i ECCR tworzą jeden, testowalny kontrakt nazwany **Proof-Preserving
Anchor-Cover Routing (PPACR)**. Dekompozycja może eksplorować i rozszerzać
zbiór kandydatów, ale jej wynik przechodzi najpierw przez niezmienną kotwicę
globalnego rankingu. Następnie wybór kart pokrywa obowiązki zapytania, a granicę
`LOAD` przekracza wyłącznie komplet świadectw: zakres, etykieta `supported` i
ważne linie źródłowe dla każdego obowiązku. W innym przypadku system zwraca
`ASK` z brakami i obserwacjami.

To jest kandydat na przełom metodologiczny: preferencja rankingu, kompletność
pakietu i autoryzacja wykonania są osobnymi obiektami, a nie jednym score'em.
Twierdzenia są niezależne od konkretnego LLM: APD zachowuje prefiks przez
konstrukcję, bramka dowodowa jest fail-closed względem ledgeru, a funkcja
pokrycia ma własność monotonicznej submodularności z klasycznym ograniczeniem
greedy `(1−1/e)`. Prototyp referencyjny i szkice dowodów są w
[PPACR](../../../research/proof-preserving-anchor-cover-routing-2026-09-08/README.md)
i [THEORY.md](../../../research/proof-preserving-anchor-cover-routing-2026-09-08/THEORY.md).

Literatura pokazuje, że GoSkills już buduje anchor-centered grupy i jawne role,
a SRA-Bench rozdziela retrieval, incorporation i end-task execution. PPACR
stawia dodatkowo warunek, że nic nie może być załadowane bez źródłowego dowodu;
to odróżnienie trzeba zweryfikować pełnym przeglądem related work, zanim zostanie
opisane jako nowość. Następny eksperyment nie powinien stroić kolejnego rankera,
lecz zamrozić ludzkie ledger-y, zmierzyć proof-valid bundle completion,
unsupported-load rate, jakość `ASK` i wykonanie zadań.

## Aktualizacja: pyramid claim lattice, 8 września 2026

Dodano wersję PPACR specyficzną dla automatycznego tworzenia abstraktów:
**Pyramid Claim Lattice (PCL)**. Rodzic nie jest już zwykłym streszczeniem
LLM. Każde jego twierdzenie jest złączem (`join`) dokładnych zakresów linii z
kart dzieci, ma hash pełnych rewizji źródeł i wymaga wsparcia z co najmniej
dwóch niezależnych gałęzi pod danym rodzicem, a byte-identical witness nie
liczy się jako druga corroboracja. Wsparcie liczy się po pierwszej gałęzi
poniżej scope'u, więc wiele kart jednego zespołu nie udaje niezależnej zgody
całego monorepo. Parser propozycji LLM wymaga line-level evidence i sprawdza
cytat, hash spanu oraz rewizję przed utworzeniem karty. Loader ponownie
sprawdza świadectwa i commitment przed `LOAD`; zmiana lub usunięcie źródła
przechodzi w `ASK/STALE`.

Świeży replay na bieżącym `examples/monorepo` przyjął 3/3 wielogałęziowych
twierdzeń, odrzucił kontrolę jednego źródła i wymusił `ASK/STALE` po mutacji
rewizji w pamięci. Testy obejmują także manipulację zakresem linii i częściowo
zbudowaną kartę. Kod, protokół, szkic dowodu i hashe są w
[pyramid-claim-lattice](../../../research/pyramid-claim-lattice-2026-09-08/README.md).

Dodałem też właściwy skok wielopoziomowy: karta Atlasu jest zbudowana z dwóch
liści, a karta root odwołuje się do niej przez commitment i digest twierdzenia.
Mutacja jednej linii w liściu grafowym propaguje `STALE` przez kartę Atlasu do
root; niezależne twierdzenie root pozostaje dostępne w trybie selektywnego
ładowania. Lokalny Qwen2.5-7B-Instruct wygenerował propozycję root z trzema
istniejącymi kartami potomnymi. Parser sam uzupełnił kanoniczne commitmenty,
przyjął twierdzenie, a niezależny replay potwierdził świeży `LOAD` i
dryfowe `ASK/STALE`. Pierwszy, luźniejszy prompt zakończył się błędnym JSON-em
i pozostał zapisany jako odrzucony przebieg.

Dodatkowy lexical-anchor gate wymaga wspólnego znormalizowanego terminu na
każdej krawędzi dowodu. Druga propozycja Qwen była poprawna strukturalnie i
miała dwa różne scope'y, ale przypisała zdanie o limitach serwerowych spanowi
Postgresa opisującemu wyłącznie CODEOWNERS. Gate odrzucił kartę
`anchor_0<1`. To jest istotny postęp metody: quorum i provenance nie udają już
entailmentu, a oczywistą błędną alokację można zatrzymać deterministycznie.
Pełne rozstrzygnięcie semantyki nadal wymaga osobnego asesora lub ludzkiej
adjudykacji.

To jest istotne węższe twierdzenie niż „LLM dobrze buduje piramidę”: PCL daje
algorytmiczną gwarancję, że zaakceptowany abstrakt ma aktualne, wielogałęziowe
świadectwa i nie może pozostać ważny po dryfie źródeł. Nie zmienia produkcyjnego
rankingu ani domyślnego P08; jest kandydatem metody do testu na niezależnym
ledgerze. Następny gate to ludzka adjudykacja spanów na source-disjoint corpus,
porównanie zwykłego `ascend` z PCL i paired skill/no-skill execution. Dopiero
ten test może rozstrzygnąć, czy formalny kontrakt przekłada się na mniej
unsupported loads i lepsze działanie agenta.

Po rozszerzeniu teza metody brzmi: **abstrakt jest ładowalny tylko wtedy, gdy
cała ścieżka dowodu dochodzi do świeżych spanów liści i spełnia quorum na każdym
poziomie**. To jest kandydat na nową metodę dla automatycznej piramidy; nie jest
jeszcze dowodem prawdziwości semantycznej tekstu generowanego przez model.

## Aktualizacja: CEGAR-PCL, 8 września 2026

Najmocniejszy nowy kierunek to **counterexample-guided abstraction
refinement for the Pyramid Claim Lattice (CEGAR-PCL)**. Po odrzuceniu claimu
weryfikator nie uruchamia ponownie całej piramidy: zwraca strukturalny
kontrprzykład (`STALE`, brak gałęzi, brak różnorodności spanów albo anchor
mismatch), a refiner dostaje skończone menu kanonicznych, aktualnych zakresów
linii i referencji do kart dzieci. Dodaje jedną krawędź dowodu i powtarza
weryfikację. Nie może obniżyć quorum, wygenerować hashy ani załadować częściowo
naprawionej karty; po wyczerpaniu menu wynik jest `ASK/ABSTAIN`.

Własność, którą da się udowodnić bez założeń o jakości LLM, jest skończoność i
fail-closed: przy skończonym menu `W` każda udana iteracja dodaje nową
krawędź, więc pętla kończy się w najwyżej `|W|+1` decyzjach na claim; `LOAD`
przechodzi wyłącznie przez rekurencyjny PCL verifier. Jest to nowy kandydat na
wkład algorytmiczny: model proponuje, verifier lokalizuje kontrprzykład, a
abstrakt może zostać naprawiony lokalnie albo odmówić załadowania. Nie jest to
jeszcze twierdzenie entailmentu dla wolnego tekstu — span nadal wymaga
niezależnej oceny semantycznej.

Sprawdziłem najnowsze prace i zawęziłem claim: sam wzorzec CEGAR nie jest nowy.
WiCER ([arXiv:2605.07068](https://arxiv.org/abs/2605.07068)) używa
compile–evaluate–refine do ochrony faktów w kompilowanej wiedzy, a PCN-Rec
([arXiv:2601.09771](https://arxiv.org/abs/2601.09771)) naprawia certyfikaty po
nieudanej weryfikacji. Do obrony pozostaje tylko kombinacja rekurencyjnych
proof objects dla skilli, quorum niezależnych gałęzi i load-time invalidation
po zmianie źródła.

Świeży replay naprawił niedomknięty claim Forge+Atlas w jednej iteracji,
odmówił naprawy zapisanej fałszywej propozycji Qwen po braku
rozróżniającego świadka gałęzi identity i pozostawił poprawny root Qwen jako
zero-round no-op. Artefakty są w
[CEGAR-PCL](../../../research/pyramid-claim-lattice-2026-09-08/CEGAR.md), a
surowy wynik w
[cegar-results.json](../../../research/pyramid-claim-lattice-2026-09-08/cegar-results.json).

## Aktualizacja: K-PCL i funkcjonalne sibling hard negatives, 8 września 2026

Domknąłem kolejną granicę protokołu: **kernelized Pyramid Claim Lattice
(K-PCL)**. Karta abstrakcyjna ma dwie powierzchnie. `presentation` jest tekstem
dla człowieka i ma osobny hash diagnostyczny; kernel zawiera wyłącznie
zweryfikowane identyfikatory claimów, wskaźniki exact-line evidence,
commitmenty i referencje do niższych kart. `/use` może zwrócić kernel tylko po
rekurencyjnej weryfikacji; przy błędzie zwraca pusty `ASK`. Zmiana prezentacji
nie może dodać capability, a zmiana claimu dziecka propaguje `ASK` do
przodków. Konstruktor przecięcia odrzuca atom nieobecny w którejkolwiek
gałęzi. To jest formalna granica autoryzacji i provenance, nie dowód
semantycznego wynikania zdania z tekstu.

Replay i niezależny proces są w
[KERNEL.md](../../../research/pyramid-claim-lattice-2026-09-08/KERNEL.md),
[kernel.py](../../../research/pyramid-claim-lattice-2026-09-08/kernel.py),
[kernel-results.json](../../../research/pyramid-claim-lattice-2026-09-08/kernel-results.json)
i [kernel-verification.json](../../../research/pyramid-claim-lattice-2026-09-08/kernel-verification.json).

Świeży skan dostarczył też ważny warunek ewaluacji. **ExecRetrieval**
([arXiv:2609.01865](https://arxiv.org/abs/2609.01865)) pokazuje, że dense może
mieć exec@10 = 1.00 i jednocześnie exec@1 = 0.331, bo wybiera bliskiego,
funkcjonalnie błędnego near-clone. Nie przenoszę tych liczb na Guidefold;
traktuję je jako wskazówkę do osobnego korpusu `same-family hard negatives`:
różny API/version, precondition, repo scope, verifier albo jeden krytyczny
fragment body. To powinno być następne badanie retrievalu. K-PCL może
przechowywać wskaźnik do weryfikatora i provenance, ale nie zastępuje
execution oracle.

TROVE ([arXiv:2609.05019](https://arxiv.org/abs/2609.05019)), Trace2Tower
([arXiv:2609.05261](https://arxiv.org/abs/2609.05261)) i Repo-To-Skill
([arXiv:2609.02749](https://arxiv.org/abs/2609.02749)) wzmacniają architekturę
second-stage typed DAG oraz outcome-aware `/use`; nie uzasadniają zmiany
produkcyjnego BM25F. MVP pozostaje remote Go/BM25F z dense/hybrid w shadow,
wersjami, scope/family resolution, `NO_SKILL` oraz CI generującym reviewable
proposals.

## Aktualizacja: Contract-Gated Sibling Resolution, 8 września 2026

Na podstawie ExecRetrieval dodałem osobny, deterministyczny spike
**Contract-Gated Sibling Resolution (CGSR)**. Ranker nadal tworzy listę
kandydatów, ale drugi etap sprawdza family, repo/language scope, wersję API,
preconditions, stan kernelu K-PCL i wynik execution verifiera. Kandydat z
wyższym score'em, lecz z błędnym verifierem lub scope'em, jest odrzucany. Gdy
pozostają dwa bliskie, zweryfikowane siblingi z różnymi operacjami, wynik to
`ASK`, nie zgadywanie.

Na kontrolowanej zabawce gate odrzucił błędny v2 near-clone mimo wyższego score'u,
wybrał poprawny sibling v2, odrzucił wariant z innego repo i zatrzymał zarówno
niejednoznaczne siblingi, jak i kartę z kernel `ASK`. To jest warunkowa
gwarancja kontraktowa przy założeniu poprawnego ledgeru i verifiera, nie wynik
retrievalu ani dowód poprawy pracy użytkownika. Artefakty:
[CGSR README](../../../research/functional-sibling-resolution-2026-09-08/README.md),
[sibling_gate.py](../../../research/functional-sibling-resolution-2026-09-08/sibling_gate.py),
[results.json](../../../research/functional-sibling-resolution-2026-09-08/results.json),
[verification.json](../../../research/functional-sibling-resolution-2026-09-08/verification.json).

Najbliższy test naukowy powinien zbudować source-disjoint korpus takich klastrów
na realnych skillach i zmierzyć functional sibling top-1, proof-valid `/use`,
harmful-sibling exposure, useful abstention, Recall@k, opóźnienie oraz paired
skill/no-skill execution. Do czasu tych etykiet CGSR i K-PCL pozostają shadow/
CI, a produkcyjny hot path nadal jest remote Go/BM25F.

## Aktualizacja: ocena skanu z 8 września i design delt, 8 września 2026

Trzy wiadomości skanu (CoSkill, Persistent Skills, SkillRevise, FUSION; ExecRetrieval,
TROVE, Trace2Tower, Repo-To-Skill; „werdykt MVP") oceniłem w
[design-2026-09-08-scan-deltas.md](design-2026-09-08-scan-deltas.md). Kierunek architektury zgadza się z tą decyzją; analiza
zawiera cztery błędy o naszym systemie (BM25F już jest field-aware, klient ma lokalny
sparse fallback, `revision`/`snapshot_id` już pełnią rolę `skill_version`/`index_version`,
300 ms jest targetem, nie wynikiem) i dwie rekomendacje zmierzone u nas z wynikiem zerowym
(pseudoqueries +0,163 pp, learned fusion). Zaprojektowane delty: D1 korpus same-family hard
negatives, D2 jawna abstencja `decision: no_skill`, D3 deterministyczna rezolucja po
rankingu, D4 reguły promocji w P08, D5 one-hop w USE, D6 feedback jako istniejące zdarzenia.
Żadna nie zmienia produkcyjnego rankingu; D2 i D3 zmieniają selekcję i czekają na decyzję
właściciela.

Tego samego dnia eksperyment
[delivery-vs-concatenation](../../reports/market/2026-09-08-delivery-vs-concatenation.md)
nie potwierdził pierwszej propozycji wartości: konkatenacja nie traci przy 1000 skillach, bo
applicable set pod nearest-wins zmieścił się w limicie 32 KiB w 178/183 komórkach; retrieval
CLI był 61/61 top-1 na każdym rozmiarze. Drugi przebieg wymaga filleru na ścieżce przodków i
scoringu bez nagrody za cytowanie.
