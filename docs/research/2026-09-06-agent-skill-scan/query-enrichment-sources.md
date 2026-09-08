# Rozszerzanie metadanych i pseudozapytań dla sparse retrieval

Weryfikacja źródeł pierwotnych: 2026-09-06. Ten przegląd nie uruchamia modeli, GPU, treningu ani ewaluacji jakości. Opisy wyników literatury nie są wynikami Guidefold.

## Decyzja

Najmniejszy sensowny kierunek to enrichment offline: z istniejącego SKILL.md powstają metadane z odwołaniem do źródła oraz kilka sprawdzonych pseudozapytań. Indeksujemy je w tej samej ścieżce sparse, bez LLM podczas SEARCH. Początkowy eksperyment powinien porównać pełny obecny BM25F, metadane oraz metadane z pseudozapytaniami. Nie potrzeba najpierw zbierać 30 tys. dokumentów.

To propozycja badania, nie twierdzenie o jego skuteczności. Dodatkowy tekst potrafi zwiększyć recall i jednocześnie pogorszyć wybór właściwego siblinga; jakość i opóźnienie mierzymy po zbudowaniu większego indeksu.

## Źródła i ich rzeczywisty zakres

### 1. Doc2query — pierwotny mechanizm

Nogueira, Yang, Lin, Cho, 2019: model generuje zapytania na podstawie dokumentu, następnie zapytania dołącza się do dokumentu przed indeksowaniem. Wniosek praktyczny: sygnał neural można przenieść do zwykłego indeksu leksykalnego, bez neural inference dla każdej prośby użytkownika. Model trenowano na parach query–document; nie jest to dowód, że dowolny LLM bez adaptacji poprawi skille organizacji. Artykuł porównuje także warianty z rerankingiem — nie należy przypisywać całego zysku samemu rozszerzeniu. [Artykuł, arXiv:1904.08375](https://arxiv.org/abs/1904.08375).

Oficjalne [repozytorium nyu-dl/dl4ir-doc2query](https://github.com/nyu-dl/dl4ir-doc2query) oraz [instrukcja reprodukcji Anserini](https://github.com/castorini/anserini/blob/master/docs/experiments-doc2query.md) udostępniają drogę od danych i przewidzianych zapytań do indeksu BM25. To starszy, odtwarzalny punkt odniesienia; nie wymaga kopiowania ich silnika do Guidefold.

### 2. DocTTTTTquery — praktyczny baseline generatora

Nogueira i Lin, 2019, zastępują pierwotny model przez T5. To krótki raport autorów, nie nowy dowód dla agent-skills. [Raport v2](https://cs.uwaterloo.ca/~jimmylin/publications/Nogueira_Lin_2019_docTTTTTquery-v2.pdf).

Oficjalne [castorini/docTTTTTquery](https://github.com/castorini/docTTTTTquery) zawiera model T5-base, identyfikator `castorini/doc2query-t5-base-msmarco`, kod PyTorch, gotowe zapytania oraz dane z checksumami. README pokazuje też ścieżkę CPU; to dostępność wykonania, nie gwarancja sensownego czasu dla korpusu. Generator jest dopasowany do MS MARCO passages. Długie dokumenty wymagają polityki podziału; przypadkowy truncation SKILL.md może usunąć ograniczenia i parametry. Guidefold ma już historyczny eksperyment F3/doc2query, więc jego wynik trzeba zachować jako baseline, a nową metodę zarejestrować oddzielnie.

### 3. Doc2Query-- — najważniejszy precedens filtrowania

Gospodinov, MacAvaney, Macdonald, ECIR 2023: filtrowanie wygenerowanych zapytań względem dokumentu przez model relevance. Wersja v3 podaje do 16% względnej poprawy retrieval oraz spadek średniego query time o 23% i rozmiaru indeksu o 33%. To ich pomiary MS MARCO, nie prognoza dla Guidefold. Badali ELECTRA, MonoT5 i TCT; filtrowanie po prawdopodobieństwach samego generatora nie okazało się skuteczne. Progi dobrano na dev, a część różnic na małych TREC DL nie była istotna. [Artykuł v3, 2023-02-27](https://arxiv.org/html/2301.03266v3).

Oficjalne [terrierteam/pyterrier_doc2query](https://github.com/terrierteam/pyterrier_doc2query) pokazuje działający interfejs `QueryScorer` → `QueryFilter`, przykładowy pipeline oraz udostępnione scores. Przykład zachowuje zapytania powyżej progu odpowiadającego 70. percentylowi na MS MARCO, czyli około 30%, nie 70%. Wartość `3.21484375` nie jest uniwersalnym progiem jakości. Dla pierwszego małego eksperymentu Guidefold można użyć jawnego ręcznego audytu i reguł zamiast nowego modelu filtrującego; wtedy to adaptacja idei, nie reprodukcja Doc2Query--.

### 4. Skill2Query — świeża i bezpośrednio związana hipoteza

Ding i współautorzy, arXiv v1 z 2026-08-17, wykorzystują wewnętrzną strukturę skilla: capability, parameter i example. Generowanie obejmuje styl, szablon i wypełnienie parametrów. Papier obejmuje offline augmentation, online expansion i trening; te warunki trzeba rozdzielać. Średnie +6,70 pp z abstraktu nie opisuje oczekiwanego zysku naszego pełnego BM25F. W tabeli 3 BM25(full) offline daje R@1:

| Zbiór | Baseline | Offline | Delta, pp |
|---|---:|---:|---:|
| TheoremQA | 60,37 | 60,37 | 0,00 |
| LogicBench | 15,39 | 21,97 | +6,58 |
| ToolQA | 46,15 | 48,32 | +2,17 |
| CHAMP | 13,90 | 10,76 | −3,14 |

To argument za małym testem kontrolowanym, nie za domyślnym enrichment całego katalogu. Badanie downstream dotyczy 747 zadań TheoremQA, top-1 skill i one-step answering; nie zastępuje sesji programisty w monorepo. [Skill2Query v1](https://arxiv.org/html/2608.16071v1).

**Stan oficjalnego kodu:** papier wskazuje [MatZaharia/Skill2Query](https://github.com/MatZaharia/Skill2Query). README w odczytanej wersji otwarcie podaje, że execution verifier nie jest zaimplementowany; `Exec-Pass` używa statycznego sprawdzenia niepustych defaults dla required slots. `AblationStudy.run()` zwraca placeholder metrics i wymaga podłączenia do pipeline. Dlatego nie opisujemy publicznego repo jako kompletnej, zwalidowanej reprodukcji eksperymentów. Dostęp do konkretnego pliku ablation przez przeglądarkę nie powiódł się; powyższy wniosek pochodzi bezpośrednio z jawnych zastrzeżeń README. Nie uruchamiano repo ani testów. Najmniejsza inspiracja do Guidefold to evidence-backed lista capabilities i parametrów w JSON; graph database nie jest konieczna.

### 5. InPars-v2 — filtr oddzielony od generatora

InPars-v2 używa LLM do tworzenia par query–document i istniejącego rerankera do ich selekcji. Wynik BM25 + wytrenowany monoT5 dotyczy treningu rerankera, a nie czystego BM25 po augmentation. [Artykuł](https://arxiv.org/abs/2301.01820).

Oficjalny [InPars toolkit](https://github.com/zetaalphavector/InPars) udostępnia generowanie, filtrowanie po model scores lub rerankerze, dane i procedury reprodukcji. Przydatna zasada to oddzielenie generatora od oceny jego wyników. Nie kopiujemy treningu ani nie uznajemy confidence generatora za dowód groundingu.

### 6. Negatywne wyniki i nowsze warianty

Weller i współautorzy, Findings EACL 2024, porównują 11 technik expansion, 12 datasetów i 24 retrievery. Widzą zależność między siłą baseline a zyskiem: mocniejsze systemy częściej tracą. Dodatkowe false positives autorzy przedstawiają jako hipotezę wynikającą z analizy błędów, nie uniwersalne prawo. [Publikacja ACL](https://aclanthology.org/2024.findings-eacl.134/). Oficjalne [orionw/LM-expansions](https://github.com/orionw/LM-expansions) zawiera kod, konfiguracje i odnośniki do gotowych generacji; można badać część pipeline bez ponownego generowania.

Doc2Query++ z 2025-10-10 proponuje topic coverage, wybór słów i generowanie różnych zapytań. Zamiast powtarzać ten sam intent, generator ma pokrywać tematy dokumentu. Pełna metoda obejmuje BERTopic i wariant dense dual-index, więc nie jest najprostszym MVP. [Preprint v1](https://arxiv.org/html/2510.09557v1) odsyła do [anonimowego repo](https://anonymous.4open.science/r/doc2queryPlusPlus-41BB/), którego nie udało się otworzyć. Nie potwierdzono kompletności kodu ani reprodukcji; adnotacja konferencyjna z placeholder DOI w v1 nie jest tu traktowana jako dowód przyjęcia. Do małego spiku wystarczy własna jawna lista capabilities, bez nowej infrastruktury topic modeling.

## Proponowany eksperyment: dokładnie trzy ramiona

Poniżej własna propozycja projektowa. Nie jest opublikowanym wynikiem żadnej z powyższych prac.

| Arm | Zawartość indeksu | Co izoluje |
|---|---|---|
| A — sparse | Obecny pełny tekst i metadane; obecny BM25F, policy, selection | Mocny punkt odniesienia. Nie osłabiać go do name-only. |
| B — metadata | A + ograniczona lista capabilities, aliasów/triggerów i parametrów, każda pozycja z evidence span w oryginale | B−A: przyrost z pakietu metadanych. |
| C — metadata + queries | Dokładnie B + do 3–5 zaakceptowanych pseudozapytań na skill, budżet zamrożony przed oceną | C−B: przyrost z zapytań ponad metadane. C−A: cały enrichment. |

B i C muszą używać tych samych raz utworzonych metadanych. Generator nie dostaje ocenianych zapytań, qrels ani wcześniejszych błędów testu. Ramiona mają identyczne skill IDs, teksty, scope, policy, tokenizer, scorer, fixed-point weights, candidate limits, selection i k. Dodatki trafiają do stałej, jawnej reprezentacji indeksowej; jeżeli używamy istniejących pól zamiast nowego pola expansion, mapowanie jest identyczne i zapisane przed oceną. Tekst skilla dostarczany przez USE pozostaje oryginalny.

Ten układ **nie izoluje efektu samego filtrowania** ani przewagi LLM nad parserem. Do pierwszego pytania pasowałby inny plan A/base, B/raw queries, C/te same queries po filtrze. Nie należy mieszać tych dwóch pytań i przypisywać całego zysku filtrowaniu.

Pierwszy zbiór może mieć kilkadziesiąt–kilkaset rzeczywistych skilli z istniejącego dev lub repo partnera. Ważniejsze od rozmiaru są podobne siblingi, skille wielofunkcyjne i no-applicable cases. Zmniejszony candidate pool utrzymujemy identyczny między ramionami i jawnie raportujemy: wynik nie jest wtedy dowodem działania na pełnym katalogu. Fixture syntetyczny służy smoke testowi; etykietowane rzeczywiste dane służą wnioskowaniu o jakości.

## Grounding, filtry i higiena danych

1. **Pochodzenie.** Każda pozycja przechowuje skill ID, body/revision hash, evidence span, rodzaj informacji, generator ID/model revision, prompt hash, timestamp, accepted/rejected i powód. Surowe wyjście oraz odrzucone propozycje są zachowane; nie dopisujemy znacznika „LLM”, jeśli dane przygotowano ręcznie lub parserem.
2. **Zgodność semantyczna.** Query musi opisywać capability wspieraną przez źródło. Nowe synonimy mogą rozwiązać lexical mismatch, więc brak identycznego słowa w body sam w sobie nie jest odrzuceniem. Wymagana jest weryfikowalna zgodność działania i ograniczeń, nie sam overlap.
3. **Parametry.** Brak wymyślonych argumentów, uprawnień, systemów, enumów i obietnic działania. Wartości bierzemy wyłącznie ze źródła albo stosujemy jawny neutralny placeholder dopuszczony przez schema. Nie mylić istnienia slotu z wykonalnością zadania.
4. **Negacje i policy.** „Nie używaj do X” nie staje się pozytywnym triggerem X. W pierwszym porównaniu modelowe ograniczenia nie modyfikują automatycznie hard policy, scope, `requires`, `replaces` ani statusu. Taka zmiana byłaby osobnym interwencyjnym czynnikiem; owner approval i oddzielna ocena są potrzebne do aktywacji polityki.
5. **Dedup i limity.** Normalizacja whitespace/Unicode, exact i bliskie duplikaty, stały limit zapytań/znaków, maksymalnie jeden prawie identyczny wariant. Duplikaty zwiększające term frequency nie udają różnorodności. Prawidłowy wynik może mieć zero zaakceptowanych zapytań; nie dopisujemy wypełniaczy do osiągnięcia kwoty.
6. **Siblings.** Audyt kolizji jest diagnostyką. Nie odrzucać automatycznie każdej frazy wspólnej dla dwóch skilli: oba mogą być poprawnymi alternatywami. Odróżnić verified substitute, complementary dependency i harmful sibling według etykiet/ownerów.
7. **Rozdzielenie generowania i oceny.** Split na poziomie task/capability lub grup podobnych query, nie przypadkowych parafraz tego samego zadania. Generator nie widzi held-out queries. Source skill text podczas offline indeksowania jest dozwolonym inputem, nie query-label leakage; identyczność/near-duplicates należy osobno zbadać.
8. **Samopotwierdzenie.** Wynik „pseudoquery znajduje własny skill” jest sanity check, nie skuteczność na użytkownikach. Filtr wymagający top-1 w starym BM25 może usunąć właśnie użyteczne nowe synonimy; nie stosować go bezwarunkowo jako gold validator.

## Pomiary, decyzja i granice

Przed generowaniem zamrozić trzy ramiona, budżet, subset i reguły metryk. Zachować per-query ranked i selected IDs/scores, delta względem A/B, poprawne alternatywy, brak wyników i braki etykiet. Mierzyć hit@1, candidate recall@10/50, `all_required@4`, HSR@4 tam, gdzie istnieją etykiety, abstention oraz per-k i sibling strata. Dodatkowo bytes/tokens indeksu, build cost, accepted-query rate i świeży whole-client p95. Zwiększony indeks nie ma gwarantowanego zerowego kosztu online.

Dla małego spiku 95% paired intervals raportujemy jako niepewność; brak istotności może oznaczać zbyt małą próbkę. Dopuszczenie do ścieżki produktu stosuje istniejące zamrożone gates Guidefold, a nie post-hoc łagodniejszy próg dobrany do wyniku. Dotychczas oglądane test-A/test-B pozostają historycznym budżetem; nowy holdout i zakres nowych prób muszą być nazwane przed ich użyciem. Wynik „brak zysku albo szkoda dla siblingów” kończy ten wariant; nie uzasadnia automatycznej rozbudowy pipeline.

Najlepsza pierwsza implementacja to mały, audytowalny adapter eksportujący enrichment artifact i porównanie tych samych trzech indeksów. Źródła dają podstawę do hipotezy; wdrożenie rozstrzygają nasze etykiety i testy użytkowników.
