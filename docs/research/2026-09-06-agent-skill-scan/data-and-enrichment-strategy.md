# Strategia danych i wzbogacania skilli — 2026-09-06

## Decyzja

Najpierw zbadać jakość reprezentacji istniejących skilli, potem większą liczbę istniejących przykładów treningowych, a następnie skalę katalogu. To hipoteza priorytetu poparta kosztami i znanymi brakami, nie dowód, że wzbogacanie wygra. User wyraźnie autoryzował dalsze eksperymenty offline po pierwszym wyniku MLP; wcześniejsze ograniczenie do jednego spike'a nie zamyka obecnego badania. Produkcyjny MVP pozostaje przy obecnym sparse T1 i authoring/telemetry, dopóki challenger nie przejdzie osobnego przyjęcia.

1. **Jakość i pochodzenie.** Zachować source URL, rewizję, licencję, hash, pola i treść. Wykryć exact/near duplicates i rodziny źródeł. Nie usuwać wspólnych nazw automatycznie: różne skille mogą mieć tę samą nazwę. Sprawdzić, czy metadane mówią kiedy skill stosować, co przyjmuje/zwraca i jakie ma ograniczenia. Brakującej funkcji nie da się stworzyć przez dopisanie opisu.
2. **Wzbogacanie offline.** Dodać osobny wersjonowany rekord z krótkimi intent phrases i przykładowymi zapytaniami, każde z fragmentem źródłowym. Oryginalne instrukcje pozostają źródłem prawdy. Początkowo pola generowane służą wyszukiwaniu; nie stają się hard policy, requires, scope ani negatywnymi wyzwalaczami.
3. **Porównanie na tych samych danych.** A = oryginalny BM25F, B = A + frazy, C = B + pseudozapytania. Stałe wagi, cały ten sam katalog i zapytania; Recall@10 plus faktyczna kompletność wybranych czterech kart i regresje. Koszt generowania występuje przy indeksowaniu; brak LLM w ścieżce zapytania.
4. **Dane do rankera.** Mamy63,259 TRAIN zapytań; pierwszy MLP zużył2,000. Po ustaleniu reprezentacji wykonać learning curve oraz matched comparison pointwise BCE vs query-balanced/pairwise loss. Rejestrować każdy wykorzystany split. Pseudozapytania indeksowe nie stają się automatycznie niezależną etykietowaną ewaluacją.
5. **Większy katalog.** Dopiero potem pinned30k kandydatów jako test odporności na konkurencję i koszt indeksu. Potrzebne dedup oraz relevance judgments; przypadkowo dodany dokument nie musi być prawdziwym negatywem. Więcej dokumentów bez zapytań i etykiet nie odpowie, czy model potrzebował więcej treningu.

## Wykonany audyt wejścia

[corpus-quality.json](../../../research/spikes/2026-09-06-query-enrichment/corpus-quality.json):10,123 rekordów. Brak pustych nazw/opisów/body.94opisy mają mniej niż30znaków.552powtarzające się nazwy obejmują955dodatkowych wystąpień;17grup identycznych znormalizowanych opisów,22dodatkowe wystąpienia. Brak identycznych po normalizacji całych body. Korpus ma już13 wartości primary_action,15 primary_object i13 domain; są to ogólne tagi LLM, nie szczegółowe przykłady zapytań. To pomiar struktury, nie semantycznych duplikatów, poprawności instrukcji ani skuteczności na zadaniach. Mediana body6,519znaków;95.percentyl22,133znaki — potwierdza potrzebę jawnego budżetu ekstrakcji zamiast milczącego ucinania tekstu.

## Weryfikacja propozycji30k

Załącznik sugerował, że agentowe zbiory20–30k nie istnieją i trzeba użyć Alexa. To wniosek nieaktualny. [SkillRouter Eval Core](https://huggingface.co/datasets/pipizhao/SkillRouter-Eval-Core/blob/main/README.md) deklaruje78,361kandydatów Easy i79,141Hard;87tasks,75ocenianych po wyłączeniu generic_only. To benchmark ewaluacyjny mimo technicznej etykiety split=train w HF, a nie78k par treningowych. Alexa może być osobnym testem transferu domeny, lecz nie zastępuje proceduralnych SKILL.md z instrukcjami i ograniczeniami. Nie pobrano nowego katalogu, bo bieżące pytanie o enrichment można sprawdzić na już zweryfikowanym korpusie.

## Podstawa naukowa

[docTTTTTquery](https://github.com/castorini/docTTTTTquery) dostarcza kodu i precedensu generowania zapytań przed indeksowaniem BM25. [Doc2Query--](https://arxiv.org/abs/2301.03266) pokazuje potrzebę filtrowania nietrafionych zapytań; automatycznie dodany tekst może zwiększyć szum. [Skill2Query](https://arxiv.org/html/2608.16071v1) jest bliższe domenie skilli, lecz efekt nie jest uniwersalny, a jego [repozytorium](https://github.com/MatZaharia/Skill2Query) ujawnia brak execution verifier i placeholdery w ablation runnerze. Nasz protokół jest własnym kontrolowanym testem inspirowanym tymi pracami, nie ich wierną reprodukcją. Szczegóły źródeł i ograniczeń: [query-enrichment-sources.md](query-enrichment-sources.md).

## Bieżący eksperyment

[Protokół](../../../research/spikes/2026-09-06-query-enrichment/PROTOCOL.md) został zamrożony przed generacją i rankingiem.512dokumentów wybrano przez hash niezależnie od zapytań. GeneratorQwen2.5-7B otrzymuje tylko dokument; metadata i pseudoqueries zapisuje do osobnego pliku.2,048zapytań z TRAIN wybrano po wykluczeniu3,000znanych wcześniejszych identyfikatorów i ich identycznych tekstów. To wewnętrzna próba na tym samym publicznym katalogu, nie nowa domena ani gwarantowanie nieznany modelowi benchmark.

206zapytań ma przynajmniej jeden gold skill w przypisanej grupie512;1,842nie ma żadnego; tylko40ma wszystkie gold w tej grupie. Wynik główny obejmuje wszystkie2,048. Podgrupy przypisane przed wynikami służą diagnozie efektu oraz regresji; nie zastępują wyniku całej próby. Nie ekstrapolować efektu5%pokrycia przez mnożenie przez20.

Filtr wymaga poprawnej struktury, limitów długości, cytatu obecnego w źródle i deduplikacji. Cytat sam nie dowodzi, że wygenerowane twierdzenie z niego wynika — potrzebny niezależny przegląd semantyczny. Błędy generatora zostają jako puste rozszerzenie, bez wymiany skilla. Nie oceniamy jeszcze wykonania instrukcji ani jakości samego skilla.

## Próg dalszych prac i paper

Z góry ustalony warunek dalszego pełnego enrichment: C−A Recall@10>0 z dolną granicąCI>0, punktowa kompletność@4 nie maleje, Recall@10 w grupie bez wzbogaconych gold nie spada więcej niż0.5pp. To filtr kolejnego kosztu, nie kryterium wdrożenia czy nowości. Nie wybieramy po fakcie innego ramienia jako zamiennika tej hipotezy. Ujemny wynik prowadzi do zapisanej diagnozy i nowej hipotezy na nowych danych; dodatni do pełnego pokrycia i niezależnej walidacji.

Samo uruchomienie doc2query na skillach nie wystarcza na nowy paper. Wartościowe pytanie brzmi: kiedy udokumentowane rozszerzenia pomagają odzyskać komplet instrukcji przy ograniczeniu czterech kart, a kiedy zwiększają błędne dopasowania? Do twierdzenia naukowego potrzebne pełne pokrycie, grupowanie źródeł/duplikatów, niezależna domena, ocena semantyczna oraz porównania z istniejącymi metodami. Wyniku retrieval nie nazywać poprawą produktywności developera bez badania wykonania zadań.

Dodatkowe ograniczenie: [karta SKILLRET](https://huggingface.co/datasets/ThakiCloud/SKILLRET) identyfikuje TRAIN queries jako syntetyczne, wygenerowane Qwen3.5-122B-A10B. Nasz generator Qwen2.5-7B nie dostał tych zapytań, ale wspólna rodzina modeli może dzielić styl; wynik nie zastępuje testu na rzeczywistych prośbach developerów.

## Generacja zakończona

512 dokumentów przeszło przez lokalny generator. Filtr przyjął869 intent phrases oraz734 pseudoqueries;409 dokumentów ma co najmniej jedną frazę,365 ma co najmniej jedno pseudozapytanie. Zapisano20niepoprawnych odpowiedzi JSON;8generacji osiągnęło limit448tokenów (te liczniki mogą się nakładać).1071pozycji odpadło z powodu cytatu nieobecnego w dokładnym fragmencie źródłowym,268z powodu długości i5z powodu struktury. To kryteria mechaniczne, nie licznik udowodnionych halucynacji.

Generowanie zużyło751,685tokenów wejściowych i123,600wyjściowych. Suma czasów batchy1155.9s (~19.3min); końcowa faza z zapisem/hashowaniem1200.4s, poza początkowym ładowaniem modelu.258z512body wymagało wyciągu pierwszych1200 i ostatnich400tokenów. Przy podobnym rozkładzie długości30k dokumentów oznacza orientacyjnie18.8godziny samej generacji na tym GPU — liniowa ekstrapolacja orientacyjna, nie benchmark pełnego korpusu. Nowego modelu nie pobierano i nie wykonywano płatnych wywołańAPI. [Surowy zapis i hashe](../../../research/spikes/2026-09-06-query-enrichment/generation-freeze.json).

## Iteracja jakości po audycie

Niezależny przegląd16 uprzednio wybranych dokumentów ocenił44 przyjęte pozycje:26 supported,18 weak/generic,0unsupported; jeden dokument miał puste rozszerzenie. Ocena dotyczy dostarczonego fragmentu źródłowego i nie potwierdza poprawności samego źródła.18ogólnych pozycji nie oznacza18halucynacji; najczęściej ginęła nazwa technologii albo lokalnego workflow. To mała ocena jednego recenzenta, bez tezy o częstości w całym katalogu. [Audyt](../../../research/spikes/2026-09-06-query-enrichment/semantic-audit.md).

Dlatego wykonano oddzielną próbę dwóch promptów na32 nowych dokumentach: oryginalny oraz wymagający zachowania konkretnej platformy/workflow i bezpośredniego zadania użytkownika. Stałe8dokumentów przeznaczono do oceny obu odpowiedzi. Pierwszy przebieg batch8 przerwano przy48/64odpowiedziach po dojściu do24,027MiB pamięciGPU i silnym spowolnieniu. Zachowano częściowe pliki, a oba ramiona powtórzono z batch4, tymi samymi dokumentami i pozostałymi ustawieniami. [Protokół restartu](../../../research/spikes/2026-09-06-scope-prompt-b4/PROTOCOL.md). Nie połączono przerwanego runu z nowym porównaniem. Ta próba mierzy jakość tekstu i działania filtra, nie Recall.

Próby źródłowe i rankingowe dotyczą anglojęzycznego benchmarku. Dla produkcyjnego zastosowania trzeba osobno sprawdzić realne zapytania zespołu, w tym polskie, jeśli są używane. Zwiększenie katalogu może wprowadzać nowe poprawne alternatywy nieobecne w qrels; nie wolno automatycznie traktować wszystkich nowych skilli jako negatywów.

## Wynik końcowy głównego testu

Zakończono i niezależnie przeliczono6144 wiersze: Recall@10 57,4219%→57,5846%, kompletność4 29,0527%→29,1992%. Poprawa Recall to5 zapytań bez regresji tego konkretnego wskaźnika, lecz nDCG spada w14 przypadkach. Próg bootstrap przechodzi, a dodatkowy test dokładny daje p=0,0625. Wszystkie3poprawy kompletności dotyczą jednego skilla. Decyzja i pełne granice wnioskowania: [query-enrichment-results.md](query-enrichment-results.md).

## Aktualizacja po eksperymentach CPU, 6 września 2026

Ukończono sześć wariantów bez GPU. Pełne dopiski zwiększają Recall@10 o 0,0732 pp, bez poprawy kompletności netto; filtr top-10 źródła nie przechodzi zamrożonego progu. Nie ma podstaw do zmiany MVP ani masowej generacji na tej podstawie. Priorytetem badawczym staje się weryfikacja podejrzanych dodatkowych etykiet SKILLRET TRAIN: surowe qrels są strukturalnie spójne, ale znaleziono konkretne semantyczne rozbieżności. Przygotowano 120 zapytań do niezależnej oceny; ocen jeszcze nie wykonano. [Wyniki CPU](cpu-enrichment-controls.md), [audyt danych](skillret-train-label-audit.md).
