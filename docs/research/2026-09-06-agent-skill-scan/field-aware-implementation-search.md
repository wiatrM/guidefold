# Field-Aware — audyt oficjalnych implementacji i następne eksperymenty

Data odczytu: 2026-09-06. Zakres: primary papers, oficjalne repozytoria autorów, kod i karty danych. **Nie uruchomiono obcego kodu, modeli ani pipeline generowania.** Publiczne pliki .py zostały wyłącznie odczytane jako tekst. To audyt metody i rekomendacja offline research, bez zmian produkcyjnych.

## Werdykt

Nie znalazłem publicznego oficjalnego kodu Field-Aware Agent Skill Retrieval. Istnieją natomiast konkretne, oficjalne implementacje MFTR i mFAR, które pozwalają zaprojektować lepsze eksperymenty niż arbitralne powiększanie MLP. Naszego 6→16 BCE nie należy nazywać wierną reprodukcją artykułu bez poznania brakujących ustawień autorów.

Najpierw wykorzystać większą, poprawnie rozdzieloną część posiadanych 63 259 train queries, zweryfikować utratę body oraz objective/negative sampling. Pobranie 30k nieetykietowanych skillów poszerza pulę distractorów i test skali; samo nie dostarcza nadzoru do uczenia fuzji.

## 1. Field-Aware Agent Skill Retrieval — co da się odtworzyć

[Artykuł v3](https://arxiv.org/html/2608.02880v3), 2026-09-01: trzy pola name/description/body, osobne TF-IDF oraz Qwen3-Embedding-0.6B, sześć podobieństw po L2-normalizacji, uniform fusion albo mały MLP. Artykuł nie podaje architektury MLP, loss, optimizera, learning rate, liczby epok, negative samplingu, maksymalnej długości/tokenizacji ani wersji checkpointu. Nie opisuje też dodatkowego scaleru wyników poza podobieństwem kosinusowym.

SkillRet: 6 660 kandydatów, 4 997 test queries i oddzielny train. SRA-Bench: 26 262 skills, 5 400 queries, split 70/30 osobno w sześciu domenach, pięć seeds i macro-average. Skalowanie polega na zachowaniu gold i dodawaniu losowych distractorów. Wagi BM25F porównanego w publikacji są uniform. To nie jest automatycznie odpowiednik naszej kanonicznej konfiguracji BM25F.

Przeszukano dokładny tytuł, arxiv ID, GitHub repository search (2608.02880: 0 wyników), odnośniki paperu oraz 20 publicznych repozytoriów pierwszego autora [Pie115](https://github.com/Pie115?tab=repositories), zweryfikowanych API. Nie znaleziono przypisanego projektu. To wynik wyszukiwania, nie dowód, że kod nie istnieje prywatnie lub pod inną nazwą. Nie wysyłano wiadomości do autorów. Licencja tekstu paperu: CC BY 4.0; licencji nieznanego kodu nie ustalono.

**Brakujące pytania reprodukcyjne:** architecture/activation, objective, multi-positive handling, negatives i ich liczba, train/dev split IDs, feature preprocessing, tokenizer i embedding instruction, max_length/chunking, checkpoint revision, seeds, early stopping, scope IDF oraz pełna definicja denominatorów. Do chwili uzyskania ich nasze testy są niezależną implementacją idei.

## 2. MFTR — oficjalny kod autorów, bez ukrytego MLP

Oficjalność potwierdza przypis w [paperze](https://arxiv.org/html/2602.05366v1), wskazujący [LittleDinoC/MFTR](https://github.com/LittleDinoC/MFTR).

Pin: **c3f4d40a560a3017200141c3de0fff66e2dcbe8f**, commit 2026-02-01T13:18:24Z; default branch main. API GitHub license=null; w recursive tree brak LICENSE. Repo skill-grep tego autora ma Apache-2.0, ale nie przenosi to licencji na MFTR. Audyt jest odczytem; nie dodaje MFTR jako dependency ani nie redistribuuje jego danych/kodu.

| Element | Co rzeczywiście implementuje kod |
|---|---|
| Reprezentacja | Standardyzowane description, parameters, response, examples; osobna LLM query rewrite, mogąca tworzyć kilka tool needs |
| Head | Linear(4,1): description score, średnie dopasowanie parametrów, response score, example score; odejmuje soft missing-parameter penalty |
| Liczba parametrów | 4 wagi + bias + tau + w_required + w_optional = 8, wyliczone z klasy. Brak hidden layer |
| Parametry penalty | tau clamp[0,1], w_req/w_opt softplus, sigmoid(alpha*(tau−similarity)), alpha=15 |
| Uwarunkowanie | Wagi headu są globalnymi parametrami. Query zmienia scores i penalty; brak bramki q→field weights jak w mFAR |

Źródło: [przypięty model.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/src/weight/model.py). Nie kopiować semantyki „required parameters” na requires/dependencies Guidefold: podobieństwo parametru nie jest kontrolą dopuszczalności instrukcji.

**Objective i negatives.** RankNet: mean(log(1+exp(−(s_positive−s_negative)))). Konstrukcja samples to każdy gold z relevance==1 × każdy wybrany negative; assert sprawdza brak przecięcia. CLI używa 64 negatives, 5 epochs, Adam lr=0.1, batch=256, seed42. Domyślne parametry funkcji treningowej to inne wartości, ale CLI je nadpisuje: przy reprodukcji liczy się wywołanie, nie sam podpis funkcji. [main.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/src/weight/main.py).

BM25 retrievaluje top150; preprocessing zachowuje pierwsze100 niebędących labelami; trening bierze pierwsze64. Split: shuffle queries z seed42 i pięć folds 80/20; Mixed dzielony osobno. Nie jest to split po źródle, skill family czy repo. [prepare_data.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/src/prepare_data.py). Loader dodatkowo sprawdza rozłączność IDs i literalnych query strings train/test. [utils.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/src/weight/utils.py).

**Skale.** Sprawdzony pipeline nie wykonuje minmax/z-score przed headem. BM25 zwraca raw score; dense wykorzystuje FAISS Flat Inner Product. [base.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/src/field_retrieval/base.py). Embeddingi są L2-normalizowane poza modelami gtr-t5/contriever; tekst jest ograniczany do2048 słów i do min(model max positions,2048) tokenów. [encode.py](https://github.com/LittleDinoC/MFTR/blob/c3f4d40a560a3017200141c3de0fff66e2dcbe8f/toolret/encode.py). Wniosek: nie zakładać wspólnej skali między scorerami bez jawnej kontroli w naszym eksperymencie.

LLM rewrite jest częścią MFTR, więc wynik całego MFTR nie izoluje learned field fusion. Do naszego spika należy przenieść hipotezę loss/headu, pozostawiając tę samą reprezentację, query i candidate set. Pełny MFTR wymagałby osobnego budżetu/measurement rewrite.

## 3. mFAR — uwarunkowane zapytaniem wagi i contrastive training

[Oficjalne repo Microsoft](https://github.com/microsoft/multifield-adaptive-retrieval), linked z pracy ICLR2025. Pin: **a5fbab0b408d5290ccf33b31fc5af9674c285327**, 2025-03-19T00:20:58Z. [Kod na licencji MIT](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/LICENSE).

Model obsługuje wiele indeksów (pola × sparse/dense). LinearWeights liczy softmax(qW) i ważoną sumę scores. To prawdziwe query-conditioned weights, a nie MLP wyłącznie sześciu podobieństw pary query/document. Jest opcja wag statycznych. [weighting.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/modeling/weighting.py).

Loss: contrastive log-softmax NLL, in-batch negatives, opcjonalny all-gather między GPU i reverse document→query loss, defaults true. Dense scores dzielone przez temperature; sparse scores dokładane jako osobne kanały. Hybrid ma opcjonalny BatchNorm1d dla kanałów, z running stats, domyślnie wyłączony. **In-batch loss wskazuje diagonal positive bez widocznego qrels-aware maskowania innych gold**: przed adaptacją do multi-gold SKILLRET trzeba dodać maskę lub multi-positive loss. [losses.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/modeling/losses.py).

Jawny sampler usuwa wszystkie znane positives danego query, następnie losuje z dolnej części listy BM25. Defaults klasy: top50/bottom5/sample1, ale **CLI nadpisuje na (100,50,1)**. Nie są to „64 najtrudniejsze negatives”. [negative_sampler.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/data/negative_sampler.py), [train.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/commands/train.py).

CLI defaults: facebook/contriever-msmarco, embedding normalize=False, temperature0.05, query_cond=True, use_batchnorm=False, train/dev query max length512, max_epochs50, patience10, encoder_lr1e−4; weights_lr konfigurowalny osobno. README przykład używa encoder_lr1e−5/weights_lr1e−1. Są to ustawienia kodu/przykładu, nie ustalony przez nas „najlepszy” zestaw. Prepare_model pozwala zamrozić encoder i dodaje Normalize tylko przy fladze. [modeling/util.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/modeling/util.py).

Dane STaRK amazon/mag/prime; loader zachowuje oficjalne train/val/test/test-0.1. Modele są związane ze schematem pól; README zaznacza, że custom dataset wymaga zmian schema/format, nie jest plug-and-play. [download_queries.py](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/mfar/commands/stark/download_queries.py), [README](https://github.com/microsoft/multifield-adaptive-retrieval/blob/a5fbab0b408d5290ccf33b31fc5af9674c285327/README.md).

## 4. Dane: wersje i licencje

Metadane pobrane z publicznych API2026-09-06; **są to pins sprawdzone online, nie zmiana lokalnego corpora-manifest**.

| Zbiór | Zweryfikowany revision | Licencja i pułapka |
|---|---|---|
| [ThakiCloud/SKILLRET](https://huggingface.co/datasets/ThakiCloud/SKILLRET/blob/a050ad233a504a43135bafe8cdf45574052b5729/README.md) | a050ad233a504a43135bafe8cdf45574052b5729 | Apache2 metadata/queries/taxonomy, źródłowe skills MIT/Apache2. v1.1 eval6006/4392, v1.0 eval6660/4997; train identyczny. Wyniki wersji nieporównywalne wprost |
| [WeihangSu/SRA-Bench](https://huggingface.co/datasets/WeihangSu/SRA-Bench/blob/6143f2634eb284955ce312213bac24b582d039f3/README.md) | 6143f2634eb284955ce312213bac24b582d039f3 | Card MIT; przy redystrybucji zachować provenance źródłowych treści. Oficjalny opis:636gold+25626web skills |
| [snap-stanford/stark](https://huggingface.co/datasets/snap-stanford/stark/blob/88269e23e90587f99476c5dd74e235a0877e69be/README.md) | 88269e23e90587f99476c5dd74e235a0877e69be | Retrieval data CC-BY4.0, code MIT; potwierdza też NeurIPS supplement |
| [mangopy/ToolRet-Tools](https://huggingface.co/datasets/mangopy/ToolRet-Tools) | e06c38c75612b6536bd959e08cdd345894aba6a7 | API cardData.license=null; nie ustalono jednej licencji tych danych |
| [mangopy/ToolRet-Queries](https://huggingface.co/datasets/mangopy/ToolRet-Queries/blob/b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445/README.md) | b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445 | API cardData.license=null; licencja kodu benchmarku nie zastępuje licencji danych |

Field-Aware używa liczebności SKILLRET v1.0. Nasz frozen v1.1 rezultat nie może potwierdzić ani obalić tabeli paperu samą różnicą wartości. Osobno oznaczać comparability oraz independent implementation.

## 5. Kolejność następnych eksperymentów — rekomendacje, nie wyniki

Punkt wyjścia przekazany przez root: 6→16 BCE gorzej niż flat; sparse81param porównywalny z flatuniform; 64,6% body obcięte przy1024; 10123train docs,63259train queries, wykorzystane tylko pierwsze2000; 1000DEV już odsłonięte. Te liczby są stanem wcześniejszego spika, nie wynikiem obliczonym w tym audycie.

1. **Zamrozić R2 dane przed zmianami.** Nie wybierać dalej na odsłoniętych1000DEV i nie używać tests do iteracji. Z niewykorzystanego TRAIN utworzyć oddzielny validation oraz końcowy lockbox; wykluczyć przecieki identycznych/niemal identycznych zapytań i source families. Dla skill-disjoint split przypisać komponenty współdzielonych gold, aby multi-gold query nie przekraczał granicy; jeśli niemożliwe, jawnie raportować ograniczenie. Odsłonięty DEV służy tylko diagnostyce historycznej.
2. **Learning curve 2k→8k→32k→reszta dostępnego TRAIN**, losowanie stratyfikowane po gold-count i źródle, identyczny head/loss/negatives. Pierwsze2000 mogą być nietypowe; to test hipotezy pokrycia, nie z góry pewna poprawa. Przy zmianie N zachować stały validation i raportować coverage skill IDs/families.
3. **Objective ablation na identycznych sześciu cechach.** Porównać BCE z pairwise RankNet oraz listwise multi-positive softmax; zacząć od linear/simplex weights, potem dopiero ten sam mały MLP. Wszystkie gold usunąć z negatives. Query-balanced weighting chroni przed dominacją zapytań o wielu positives. Liczbę negatives, sampling i seeds przypiąć przed wynikami.
4. **Scale calibration jako osobny test.** Obejrzeć rozkłady sześciu cech train/validation i wpływ pojedynczego kanału. Porównać raw cosine z train-fit per-feature scalerem; per-query rank fusion jako mocny baseline. BatchNorm mFAR nie jest automatyczną receptą: rozkład sampled negatives może różnić się od całego katalogu, więc porównać scoring train/inference.
5. **Truncation audit przed nowym encoderem.** Warstwy krótkie/długie body; te same queries i wszystkie arms. Jeden wariant dłuższego wejścia lub deterministycznych sekcji/chunków, równy budżet tekstu między flat/per-field, aby nie mylić field gain z dodatkowym tekstem. Obejrzeć, czy sygnał gold rzeczywiście znajduje się poza1024. Osobno zmierzyć bytes/index cost oraz czas embeddingu.
6. **30k distractor test po zamrożeniu wariantu.** Stałe queries/gold, rosnące zagnieżdżone katalogi, ten sam seed i manifest dla wszystkich arms. Nieoznaczony nowy skill może być trafny: extra corpus nie powinien automatycznie stawać się etykietą negative w train. Dedup i provenance przed interpretacją wyników. SRA-Bench26262 jest gotowym dużym bankiem; brakujące~4k nie czyni automatycznie lepszego benchmarku.

mFAR query-conditioned softmax(qW) jest osobną późniejszą hipotezą, jeśli stałe learned weights nie radzą sobie z różnymi typami query. Pełne fine-tuning encodera nie jest wymagane do pierwszego testu bramki. Nie łączyć jednocześnie nowego headu, loss, danych, max_length i negsamplingu: dodatni wynik nie powiedziałby, co zadziałało.

Sukces badawczy ustalić przed kolejną rundą: wymagany przyrost względem mocnego flat/uniform i kanonicznego BM25F, przedział niepewności, multi-gold/all-required, false exposure/NO_SKILL oraz koszt. Powtarzanie na tych samych etykietach aż pojawi się dodatni wynik nie daje potwierdzenia. Wartość dalszych danych określi learning curve: najpierw większa część już dostępnego train, dopiero potem nowy nadzór z realnych zadań.
