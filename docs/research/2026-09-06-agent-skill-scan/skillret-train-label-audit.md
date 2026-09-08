# SKILLRET TRAIN: podejrzane etykiety dodatkowych skilli

**Wniosek: zachowujemy oryginalne wyniki, ale wstrzymujemy ich interpretację jako dowodu poprawy kompletności rzeczywistych zadań.** W kontrolowanej serii CPU ujawniono przykłady etykiet, których nie uzasadnia treść prośby użytkownika. To istotny problem do sprawdzenia przed kolejnym treningiem i przed publikacją. Nie jest to oszacowanie odsetka błędów w całym benchmarku.

## Co sprawdzono

Audyt obejmuje przypięty lokalnie SKILLRET **TRAIN**: 10 123 skille, 63 259 zapytań, 127 190 par query–skill. Brak powtórzonych ID zapytań, powtórzonych par qrels, osieroconych relacji, niezgodności nazw z ID oraz niezgodności k z liczbą etykiet. Wszystkie zapisane qrels mają relevance=1. Znaleziono 427 grup identycznych znormalizowanych tekstów zapytań; w żadnej nie różnią się zestawy gold. Nowa próba 2 048 zapytań nie zawiera takich duplikatów.

Te kontrole potwierdzają spójność strukturalną, **nie trafność semantyczną**. Przykłady poniżej występują jednocześnie w surowym skill_ids i qrels. Nasz adapter nie dopisał ich jako pozytywów. [Kod i wynik audytu](../../../research/spikes/2026-09-06-cpu-enrichment-controls/label-structure-audit.json), [notebook](../../../research/spikes/2026-09-06-cpu-enrichment-controls/label-quality-audit.ipynb).

## Konkretne przypadki

| Query ID | Rzeczywista prośba, parafraza | Podejrzany pozytywny skill | Dlaczego wymaga korekty lub wyjaśnienia |
|---|---|---|---|
| q-train-023137 | Przenieś wybrane konfiguracje serwerów MCP z Claude Code do VS Code na Linuksie. | attacking-wireless-networks | Źródło dotyczy testów penetracyjnych Wi-Fi; prośba nie dotyczy sieci bezprzewodowych ani testów bezpieczeństwa. |
| q-train-014157 | Scharakteryzuj testami pytest moduł płatności i bezpiecznie zrefaktoryzuj go do wzorca strategy. | exercise-builder | Źródło tworzy ćwiczenia dla uczniów uczących się prompt engineering; nie jest instrukcją testowania modułu płatności. |
| q-train-021740 | Popraw Lighthouse, dostępność i build lokalny strony Hugo przed wdrożeniem GitHub Pages. | jira | Źródło obsługuje zadania i workflow Jira; zapytanie nie prosi o pracę z Jira ani zarządzanie ticketami. |

Przeczytano pełne body tych trzech podejrzanych skilli. To ocena jednego asystenta, po obejrzeniu wyników i po dobraniu próby z błędów k=3; nie jest niezależną adjudykacją przez ludzi. Zachowano całą hash-wybraną próbę sześciu niekompletnych przypadków: [candidate-error-sample.json](../../../research/spikes/2026-09-06-cpu-enrichment-controls/candidate-error-sample.json). Nie podajemy na jej podstawie częstości błędów populacji ani nie uznajemy wszystkich dodatkowych etykiet za niewłaściwe.

## Co wynika ze źródła benchmarku

[Karta danych SKILLRET](https://huggingface.co/datasets/ThakiCloud/SKILLRET/blob/main/README.md) definiuje skill_ids jako istotne skille i qrels jako binarne etykiety trafności. Wersja 1.1 dodaje semantyczne filtrowanie części **TEST**, podczas gdy TRAIN pozostaje bajtowo identyczny z 1.0. Nasze obserwacje dotyczą TRAIN; nie przenosimy ich na oczyszczony TEST. Dokumentacja wskazuje też syntetyczne generowanie TRAIN przez Qwen3.5-122B-A10B. Nie ustalono, na którym etapie powstały podejrzane powiązania.

Możliwa hipoteza: generator nie włączył do końcowej prośby wszystkich wcześniej wybranych skilli. To hipoteza, nie wykazana przyczyna. Problem nie wygląda na niezgodność ID lub interpretację negatywów przez nasz kod.

## Wpływ na decyzje

Ryzyko jest wysokie dla uczenia i porównywania metod: model może być nagradzany za dopasowanie nieuzasadnionego skilla, a poprawne pominięcie takiego skilla może obniżać Recall i kompletność. Nie wykazano rozmiaru tego wpływu ani tego, że zmienia kolejność dotychczasowych metod. Wyniki pozostają poprawnymi obliczeniami względem zapisanych etykiet.

W szczególności słaba kompletność k=3 nie dowodzi sama, że należy poszerzyć dostarczany zestaw instrukcji. Najpierw trzeba rozdzielić: wymagany skill, opcjonalnie przydatny, alternatywa oraz nieistotny. Ta uwaga dotyczy naszych eksperymentów na SKILLRET TRAIN; historyczny audyt SkillRetBench jest osobnym źródłem danych.

## Konkretna kontynuacja

Przygotowano [pakiet 120 zapytań / 240 ocen](../../../research/spikes/2026-09-06-cpu-enrichment-controls/label-review-packet.json): po 40 zapytań dla k=1,2,3, wybranych hashem z obecnej kohorty niezależnie od wyniku rankingu. Kolejność przypisanych skilli jest przemieszana, wyniki routerów są pominięte, pełne źródła są dołączone. Pola dwóch recenzentów i rozstrzygnięcia pozostają puste: **pakiet przygotowano, ocen jeszcze nie wykonano**. Notebook jest nieuruchomionym towarzyszem; źródłowy skrypt audytu został wykonany.

Następny krok wymaga dwóch niezależnych ocen trafności z cytatem z prośby i źródła, rozstrzygnięcia sporów oraz osobnego oszacowania częstości problemu. Próba jest zbalansowana po k, więc odsetek dla całej kohorty wymaga wag. Następnie zamrozić korekty i zbadać, czy zmieniają kolejność sparse, dense i learned fusion. Nie usuwać pozytywów tylko dlatego, że BM25 ich nie znajduje; byłoby to ocenianie modelu według jego własnych preferencji. Do tezy o generalizacji potrzebna dodatkowo inna domena lub źródło zapytań.

W pracy naukowej można uczciwie przedstawić te przypadki jako motywację audytu etykiet. Nie mamy jeszcze podstaw do tezy, że benchmark jest ogólnie nieważny, że znamy skalę problemu albo że jest to nowe odkrycie w literaturze.
