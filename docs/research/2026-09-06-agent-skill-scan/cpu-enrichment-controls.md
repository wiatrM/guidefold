# Sześć wariantów CPU: dopiski, filtry, ekstrakcja i wiarygodność etykiet

**Nie potwierdziliśmy przełomu ani przewagi filtra. Najważniejszy nowy trop dotyczy trafności dodatkowych etykiet w SKILLRET TRAIN.** Sześć wariantów ukończono bez GPU i bez nowej generacji. Wszystkie wyniki zachowano, a metryki i przedziały przeliczono drugim skryptem.

## Wynik na nowej wewnętrznej próbie

| Wariant | Recall@10 | Recall@50 | Kompletność@4 |
|---|---:|---:|---:|
| A: obecny router | 58.0485% | 65.9342% | 28.7109% |
| B: wszystkie dopiski LLM, 512 przypisanych skilli | 58.1217% | 65.9831% | 28.7109% |
| C: dopiski po filtrze top-10 źródła | 58.0566% | 65.9261% | 28.6621% |
| D: losowe usunięcie, liczby pozycji jak C | 58.0811% | 65.9505% | 28.6621% |
| E: ekstrakcja źródłowa, długość jak B | 58.0322% | 65.9342% | 28.7109% |
| F: 20 słów ze źródła dla całego katalogu (eksploracyjny) | 58.1217% | 66.0238% | 28.7109% |

A–E stanowią pierwotne, zamrożone porównanie. F dodano jako osobną kontrolę eksploracyjną w trakcie wykonywania A–E, przed odczytaniem wyników kohorty. Ma pełne pokrycie i stałe 20 słów; nie jest kontrolą dopasowaną do B pod względem pokrycia i liczby słów. Równe agregaty B i F nie dowodzą równoważności metod.

Wszystkie dopiski B zwiększają Recall@10 o **0,0732 pp** względem A: sześć zapytań poprawia się, trzy pogarszają, 2 039 pozostaje bez zmiany. Kompletność nie zmienia się netto: jedna poprawa w k=2 i jedna regresja w k=1. Filtr C nie przechodzi zaplanowanego progu dalszych prac; względem B zmniejsza Recall o 0,0651 pp i kompletność o 0,0488 pp. To nie dowód, że każdy filtr szkodzi, tylko brak uzasadnienia dla tej konfiguracji.

| Zaplanowane porównanie | Zmiana Recall@10 [pp] | 95% CI po komponentach gold | Poprawione / pogorszone zapytania | p dokładne | p Holm |
|---|---:|---|---:|---:|---:|
| C_roundtrip minus B_generated | -0.0651 | [-0.1607, +0.0161] | 1 / 4 | 0.2500 | 0.7500 |
| C_roundtrip minus D_matched_random | -0.0244 | [-0.0758, +0.0000] | 0 / 1 | 1.0000 | 1.0000 |
| B_generated minus E_extractive | +0.0895 | [-0.0158, +0.2065] | 6 / 2 | 0.1484 | 0.5938 |
| B_generated minus A_original | +0.0732 | [-0.0327, +0.1943] | 6 / 3 | 0.2578 | 0.7500 |

Żadne z czterech zaplanowanych porównań nie uzyskuje p Holm < 0,05. Raportujemy test zmiany znaków na komponentach zapytań połączonych wspólnymi gold skillami, a nie traktujemy ich bezwarunkowo jako niezależnych obserwacji. Są 1 329 takie komponenty. To nadal nie obejmuje wszystkich zależności semantycznych i pochodzenia dokumentów. Pełne przedziały query-bootstrap i component-bootstrap, po 5 000 losowań: [results.json](../../../research/spikes/2026-09-06-cpu-enrichment-controls/results.json).

F ma również +0,0732 pp Recall@10, ale tylko cztery poprawione zapytania, zero regresji Recall i brak zmiany kompletności netto. Dodatni przedział percentylowy nie stanowi mocnego potwierdzenia przy tak rzadkich zmianach: dodatkowy, jawnie post-hoc test dokładny daje p=0,125. Nie dodajemy F do rodziny testów głównych ani nie ogłaszamy istotności. [Wynik F](../../../research/spikes/2026-09-06-cpu-enrichment-controls/full-coverage-results.json), [kontrola kruchości](../../../research/spikes/2026-09-06-cpu-enrichment-controls/full-coverage-fragility.json).

## Dane i kontrola eksperymentu

Pełny katalog pozostaje ten sam: 10 123 skille. Wybrano hashem 2 048 zapytań po wykluczeniu 5 048 wcześniej użytych ID oraz identycznych znormalizowanych tekstów. To nowa próba tylko względem zapisanego rejestru ekspozycji, z tego samego syntetycznego TRAIN. Nie jest niezależnym zewnętrznym benchmarkiem.

Podgrupy kohorty: k=3: 724, no_assigned_gold: 1860, k=1: 678, any_assigned_gold: 188, k=2: 646, all_assigned_gold: 31.

Ponownie użyto 1 603 istniejących dopisków dla 512 wcześniej przypisanych dokumentów. Filtr sprawdza, czy przy dopisku użytym jako zapytanie oryginalny, nierozszerzony indeks zwraca źródłowy skill w top-10. Zachowano 1 111 pozycji: 654 intencje i 457 pseudozapytania. D zachowuje tyle samo pozycji per dokument i rodzaj jak C. Ich długości są bliskie: 6 466/6 461 słów i 6 639/6 631 tokenów routera. B i E mają dokładnie po 9 547 słów, ale odpowiednio 9 768/10 320 tokenów routera. Są to jawne ograniczenia dopasowania kontroli.

Reguła ekstrakcji E bierze pierwsze N słów oryginalnego name + description + body bez frontmatter; N jest liczbą słów dopisków B dla tego samego skilla. Nie używa cytatów wybranych przez LLM. F stosuje pierwsze 20 słów tego samego źródła dla wszystkich skilli.

Zachowano produkcyjne wagi i ścieżkę policy → candidates(50) → score → select(4). Pamięć podręczna przechowuje wyłącznie deterministyczne wyniki oryginalnego scorera dla pojedynczych tokenów. Łącznie 448 porównań query–wariant potwierdziło identyczność całej ścieżki z niezmienionym scorerem; te porównania obejmują powtarzaną między wariantami próbę 64 zapytań oraz 64 dopiski użyte do kontroli filtra. Nie jest to benchmark szybkości produktu.

Sześć wariantów daje **12 288 unikatowych wierszy query–wariant**. Drugi skrypt sprawdził źródła, przypisania, kontrole, qrels, metryki, bootstrapy i testy dokładne. [QA A–E](../../../research/spikes/2026-09-06-cpu-enrichment-controls/independent-qa.json), [QA F](../../../research/spikes/2026-09-06-cpu-enrichment-controls/full-coverage-qa.json). Użyto pojedynczych procesów oceny CPU przy nice 10; CUDA_VISIBLE_DEVICES pozostawało puste. Nie uruchamiano modelu ani nie modyfikowano kodu produkcyjnego.

## Gdzie ginie kompletność — warunkowo względem qrels

W A komplet wszystkich zapisanych gold mieści się w top-50 dla 833/2 048 zapytań (40,67%). Zatem nawet idealny reranker tej zamrożonej puli nie osiągnie większej kompletności, jeśli traktujemy te etykiety jako wymagany zestaw. To granica oraklowa, nie wynik nowego algorytmu.

Dla k=3 komplet istnieje w top-50 tylko w 20/724 przypadkach (2,76%), a wybrano go w top-4 w 3/724 (0,41%). Dla k=2 jest to 199/646 w top-50 i 56/646 w wybranym top-4. Pierwszy wymieniony gold ma Recall@10 75,83%, a pozostałe łącznie 25,41%; kolejność etykiet nie jest potwierdzoną rolą skilla. [Pełna diagnoza](../../../research/spikes/2026-09-06-cpu-enrichment-controls/candidate-diagnostics.json).

**Nie wolno na tej podstawie automatycznie uczyć routera zwracania większej liczby dodatkowych skilli.** W małej próbie błędów znaleziono etykiety takie jak atakowanie Wi-Fi przy synchronizacji MCP, tworzenie ćwiczeń szkolnych przy refaktoryzacji płatności i Jira przy optymalizacji Hugo. Ich obecność sprawdzono w surowych qrels i porównano z pełnymi źródłami. To wskazuje potrzebę audytu etykiet, nie pozwala oszacować jego skali. [Oddzielny audyt danych i pakiet do oceny](skillret-train-label-audit.md).

Sprawdzono także potencjalny błąd normalizacji: średnia długość pola w routerze pomija pola puste, więc brak enrichment w 95% dokumentów nie rozcieńcza tej średniej dwudziestokrotnie. Częściowe pokrycie nadal ogranicza interwencję i zmienia statystyki terminów. [Sprawdzenie kodu](../../../research/spikes/2026-09-06-cpu-enrichment-controls/normalization-diagnostic.json).

## Decyzja badawcza i praca naukowa

1. Nie przyjmujemy filtra top-10 ani masowej generacji metadanych na podstawie tej próby. Wynik nie daje powodu, by zwiększać katalog do 30k jako sposób naprawienia trafności etykiet.
2. Najpierw niezależnie zweryfikować przygotowany pakiet 120 zapytań i 240 relacji, rozdzielając skille wymagane, opcjonalne, alternatywne i nieistotne. Ocen jeszcze nie wykonano; nie wolno przedstawiać pustego pakietu jako gotowego oczyszczonego benchmarku.
3. Po zamrożeniu ocen sprawdzić wrażliwość kolejności sparse/dense/MLP na jakość etykiet. Jeśli pozostaje problem odnajdywania dodatkowych wymaganych skilli, następną hipotezą CPU jest dekompozycja prośby i dobór kandydatów dla poszczególnych potrzeb, z takim samym budżetem końcowym i nową próbą.
4. Do szkicu pracy dokładamy kontrolowane negatywne wyniki i konkretne zastrzeżenie do etykiet. Nie mamy jeszcze wykazanej nowości, skali problemu ani przełomu. Potencjalny kierunek paperu to wpływ wiarygodności etykiet na ocenę wieloskillowej kompletności — wymaga systematycznej walidacji, osobnego źródła i porównania z literaturą.

Rozszerzanie dokumentów i filtrowanie wygenerowanych zapytań mają precedensy w [Promptagator](https://openreview.net/pdf?id=gmL46YMpu2J), [Doc2Query--](https://arxiv.org/abs/2301.03266) i [RaDeR](https://aclanthology.org/2025.emnlp-main.1011.pdf). To motywacje testu, nie nasze nowe metody. [Źródła i granice porównania](../../../research/spikes/2026-09-06-cpu-enrichment-controls/related-work.md).

Wszystkie zamrożenia, skrypty i wyniki: [katalog eksperymentu](../../../research/spikes/2026-09-06-cpu-enrichment-controls/README.md). Produkcyjne MVP zachowuje dotychczasową decyzję sparse-first; ten eksperyment nie sprawdza wykonania zadań przez użytkowników ani SLA.
