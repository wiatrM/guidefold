# Wzbogacanie skilli: wynik i następna decyzja

**Warto dalej badać jakość metadanych. Ten pilot dał bardzo mały dodatni efekt; nie uzasadnia jeszcze masowego enrichment 30k skilli ani deklaracji przełomu naukowego.** Wykonano generowanie, ewaluację rzeczywistego rankera i niezależny audyt wyników. Następnie wykonano osobną iterację promptu na nowych dokumentach.

## Wynik kontrolowanego porównania

Pełny katalog 10 123 skilli w każdym ramieniu; 512 dokumentów wybranych niezależnie od zapytań do wzbogacenia; 2048 zapytań wybranych po wykluczeniu 3000 znanych wcześniejszych ID i identycznych tekstów. To wewnętrzna próba na publicznym TRAIN SKILLRET, nie niezależna domena. Użyto rzeczywistego BM25F, domyślnych wag, policy/candidates/score/select i czterech wybranych kart.

| Wariant | Hit@1 | Recall@10 | nDCG@10 | Komplet wymaganych skilli w 4 kartach |
|---|---:|---:|---:|---:|
| Oryginalny BM25F | 70.85% | 57.42% | 57.50% | 29.05% |
| + frazy w metadanych | 70.90% | 57.44% | 57.53% | 29.05% |
| + frazy i pseudozapytania | 71.09% | 57.58% | 57.66% | 29.20% |

C−A: **Recall@10 +0,163 pp**, bootstrap po zapytaniach 95% CI **[+0,024; +0,358] pp**. Uprzednio zaplanowana analiza po komponentach współdzielących gold skill daje CI **[+0,032; +0,343] pp**. Kompletność rośnie **+0,146 pp**, ale oba przedziały obejmują zero. Z góry ustalona bramka dalszego pilota została spełniona; nie jest to bramka wdrożenia ani dowód nowości.

Efekt Recall dotyczy **5 lepszych zapytań, 0 gorszych i 2043 bez zmiany**. Dodatkowa analiza dokładna po zobaczeniu tej rzadkości daje dwustronne sign-flip p=0,0625, również po pięciu różnych komponentach. Dla kompletności są 3 poprawy, 0 regresji, p=0,25. Te testy są analizą wrażliwości z założeniem wymienności etykiet ramion; nie podmieniają zamrożonego kryterium. Pokazują, dlaczego nie nazywamy wyniku rozstrzygającym.

**Wszystkie trzy poprawy kompletności dotyczą zapytań wymagających jednego skilla. Nie uzyskano ani jednego dodatkowego kompletnego zestawu dla zadań wymagających 2 lub 3 skilli.** To zasadniczy brak wobec celu produktu. nDCG wzrasta dla 25 zapytań i spada dla 14; brak regresji Recall nie oznacza braku wszystkich regresji rankingu.

W diagnostycznej grupie 206 zapytań mających choć jeden gold w przypisanej grupie enrichment Recall wzrasta o 1,133 pp, a kompletność o 1,456 pp. W grupie 1842 bez wzbogacanych gold Recall rośnie o 0,054 pp, kompletność bez zmiany. Nie używamy tych mniejszych grup zamiast wyniku całej próby i nie mnożymy efektu 5% pokrycia przez 20.

## Co dowiedzieliśmy się o jakości

Lokalny Qwen2.5-7B wygenerował sidecar; filtr przyjął **869 fraz i 734 pseudozapytania**. 454/512 dokumentów ma co najmniej jeden przyjęty dopisek; 58 pozostaje pustych i nadal należy do przypisanej kohorty. Zachowano 20 niepoprawnych odpowiedzi JSON, w tym 8 osiągających limit generacji. Odrzucenie cytatu przez filtr jest naruszeniem kryterium mechanicznego, nie automatycznie dowodem halucynacji.

Niezależny agent ocenił 16 wcześniej wybranych dokumentów, bez oglądania rankingów: 26/44 przyjętych pozycji wspartych i dostatecznie konkretnych, 18 zbyt ogólnych lub gubiących zakres, 0 niepopartych; jeden pusty dokument. To mały audyt jednego agenta, nie walidacja przez ekspertów ludzkich ani test wykonania skilli. W szczególności ginęły nazwy Dafthunk, BTDP, Tailwind oraz lokalne reguły Express.

Diagnostyka leksykalna po wyniku: 24,0% par dokument–unikalny dopisany token było nowych wobec oryginalnego dokumentu. Wśród najczęstszych nowych tokenów są how, i, what, do, can. To sugeruje sprawdzenie, ile dodatków wnosi konkretne nowe słownictwo, a ile tylko formę pytania; sam licznik nowości nie dowodzi użyteczności ani przyczyny małego efektu.

## Druga wykonana iteracja

Na **32 innych dokumentach** porównano dotychczasowy prompt z wersją wymagającą zachowania konkretnej technologii/workflow i formułowania bezpośrednich zadań. Model, fragment źródła, decoder i filtr są takie same w obu ramionach ukończonego przebiegu batch4.

| Kontrola mechaniczna | Dotychczasowy prompt | Prompt zachowujący zakres |
|---|---:|---:|
| Przyjęte frazy | 57 | 62 |
| Przyjęte pseudozapytania | 38 | 57 |
| Puste dokumenty | 4/32 | 1/32 |
| Niepoprawny JSON | 1/32 | 1/32 |

To poprawa liczby dopisków spełniających filtr, nie wynik Recall. Odrębny agent zakończył ocenę stałych 8 par: wpisy supported/specific **11/28 → 18/29**, weak/generic **17 → 11**, unsupported **0 w obu** wśród zaakceptowanych wpisów. Dokumenty z co najmniej jednym konkretnym wpisem: **4/8 → 6/8**. Jednocześnie pokrycie tego małego audytu spadło **8/8 → 7/8**: wariant scoped dla Xcode osiągnął limit 448 tokenów i dał niepoprawny JSON. To wskazuje poprawę konkretności w próbie oraz stratę na niezawodności jednego przykładu; globalne liczby pustych dokumentów w tabeli mają inny mianownik. Jeden agent znał nazwy ramion, więc audyt nie był w pełni zaślepiony. [Szczegóły i wszystkie etykiety](../../../research/spikes/2026-09-06-scope-prompt-b4/semantic-review.md). Pierwszy batch8 przerwano po 48/64 odpowiedziach przy presji pamięci GPU; oba ramiona powtórzono z batch4. Częściowe wyniki są zachowane i nie są łączone z ukończonym porównaniem.

## Koszt i feasibility

Pierwsza generacja: 751 685 tokenów wejściowych, 123 600 wyjściowych, 1155,9 s batchy (~19,3 min), bez wywołań płatnego API. 258/512 body wymagało wyciągu pierwszych 1200 i ostatnich 400 tokenów. Liniowo daje to orientacyjnie 6,35 h dla 10 123 dokumentów i 18,81 h dla 30k na tym GPU, przed QA i przy podobnych długościach. To projekcja kosztu, nie pomiar pełnej generacji.

Ukończony restart drugiej próby trwał 260,4 s generacji; wcześniejszy przerwany przebieg to dodatkowy koszt. C dodaje 59 586 bajtów tekstu triggers, a rozmiar JSON kart rośnie o 63 941 bajtów. To rozmiary tekstu/serializacji kart, nie rozmiar całego indeksu. Obserwowane lokalne czasy wyszukiwania nie są kontrolowanym benchmarkiem szybkości: część przebiegu nakładała się na generację. Nie dowodzą remote/WAN/whole-hook SLA.

## Decyzja wykonawcza

1. **Kontynuować poprawę konkretności i weryfikację metadanych.** Wykonany prompt zachowujący zakres jest kandydatem do kolejnego osobno zamrożonego testu retrieval. Dodać tani punkt odniesienia z fragmentami oryginalnego źródła, aby oddzielić nową treść od zwykłego zwiększenia wagi już istniejących słów. Przy budowaniu wejścia generatora preferować sekcje zakresu, warunków użycia i przykładów. Obecnych 2048 zapytań nie nazywać ponownie świeżym holdoutem.
2. **Nie uruchamiać teraz hurtowej generacji 30k.** Bramka pilota pozwala planować pełne pokrycie, ale mały efekt, brak poprawy kompletnych zestawów multi-skill i koszt kilku godzin uzasadniają najpierw lepszy generator i kontrolę na nowych danych. Większy katalog później posłuży do badania skali i trudnych konkurentów.
3. **Wykorzystać istniejące etykiety.** Mamy 63 259 syntetycznych TRAIN queries; poprzedni MLP użył 2000. Learning curve i porównanie strat rankingowych wykonać po ustaleniu reprezentacji. Samo pobranie dokumentów nie zastępuje query–skill labels.
4. **MVP zamknąć na istniejącym sparse T1 z authoring i telemetryką.** Challenger pozostaje badawczy; warunki operacyjne i realne sesje opisuje [wspólna decyzja agentów](decision.md).
5. **Paper: raport empiryczny i hipoteza, jeszcze bez mocnego claimu.** Sama ekspansja zapytań ma wcześniejsze prace. Potencjalny wkład wymaga niezależnej domeny, pełnego pokrycia, kontroli źródeł/duplikatów, oceny zakresu i kompletnych zestawów oraz wykonania zadań, jeśli twierdzenie dotyczy użyteczności.

## Dowody i odtwarzanie

- [Protokół i kod głównego eksperymentu](../../../research/spikes/2026-09-06-query-enrichment/README.md).
- [Niezależne QA](../../../research/spikes/2026-09-06-query-enrichment/independent-qa.json): 6144/6144 wierszy, 84 komórki porównań, 7 grup, hashe oraz bramka zgodne.
- [Analiza dokładna rzadkich zmian](../../../research/spikes/2026-09-06-query-enrichment/posthoc-fragility.json).
- [Dane enrichment](../../../research/spikes/2026-09-06-query-enrichment/enrichment.jsonl), [wyniki maszynowe](../../../research/spikes/2026-09-06-query-enrichment/results.json).
- [Strategia danych i źródła](data-and-enrichment-strategy.md), [przegląd literatury](query-enrichment-sources.md).

Naukowa podstawa: [docTTTTTquery](https://github.com/castorini/docTTTTTquery), [Doc2Query--](https://arxiv.org/abs/2301.03266), [Skill2Query](https://arxiv.org/html/2608.16071v1). Badania uzasadniają sprawdzenie wzbogacania i jego filtracji; nie gwarantują poprawy na Guidefold.
