# Wyniki Field-Aware MLP — wykonany spike

6 września 2026. **Nie przyjmujemy field-aware sparse+dense do produktu: ten zamrożony wariant nie przeszedł bramki. Mały model wyłącznie nad sparse pozostaje obiecującą hipotezą do osobnego badania.** To DEV-only feasibility, nie reprodukcja paperu, admission ani wynik user study.

Badanie wynika z jawnej prośby użytkownika o [Field-Aware Agent Skill Retrieval, v3](https://arxiv.org/html/2608.02880v3). Użyliśmy lokalnego generic Qwen3-Embedding-0.6B, bez fine-tuningu encodera. Procentów z artykułu nie porównujemy bezpośrednio z naszym innym splitem i protokołem.

## Wyniki na tych samych 1 000 zapytań DEV

| Wariant | Hit@1 | Recall@10 | nDCG@10 binary | Cały gold w top-4 |
|---|---:|---:|---:|---:|
| Obecny sparse (historyczny replay) | 71.00% | 58.18% | 58.04% | 29.90% |
| Flat sparse+dense, średnia | 81.30% | 67.83% | 67.23% | 36.90% |
| Pola sparse+dense, średnia | 68.70% | 64.43% | 60.21% | 32.80% |
| Flat sparse+dense + MLP (65 parametrów) | 81.30% | 67.72% | 68.03% | 38.50% |
| Pola sparse+dense + MLP (129 parametrów) | 79.10% | 64.10% | 64.79% | 36.10% |
| Pola tylko sparse + MLP (81 parametrów) | 80.10% | 67.85% | 67.38% | 38.90% |

Replay obecnego sparse jest punktem odniesienia. Nowe warianty zmieniają też źródło kandydatów/scoring i wyłączają abstencję, więc różnica wobec produktu nie izoluje skutku samego uczenia. Nie wybrano nowego produkcyjnego rankera z tej tabeli.

## Najważniejsze porównania sparowane

| Porównanie | Zmiana Recall@10, pp [95% CI] | Zmiana kompletności@4, pp [95% CI] |
|---|---:|---:|
| Field MLP minus flat MLP | -3.62 [-4.75, -2.53] | -2.40 [-3.80, -1.10] |
| Field MLP minus field average | -0.33 [-1.90, +1.17] | +3.30 [+1.50, +5.30] |
| Field dense+sparse MLP minus sparse-only MLP | -3.75 [-4.73, -2.77] | -2.80 [-4.00, -1.70] |

Field MLP poprawił Hit@1 o **10,4 pp** względem prostego uśrednienia tych samych sześciu sygnałów, ale nie poprawił Recall@10. Uczenie może więc zmienić użytecznie porządek wyników; nie gwarantuje lepszego pokrycia. Dodanie dense do sparse-only MLP w tej konfiguracji obniżyło Recall@10 i kompletność.

Sparse-only MLP ma opisowo +9,1 pp Hit@1, +9,67 pp Recall@10 i +9,0 pp kompletności względem historycznego shipped sparse. **Nie przypisujemy tej różnicy wyłącznie treningowi:** brak w tym runie identycznego trzykanałowego sparse-uniform baseline, a generator kandydatów i scoring różnią się od produktu. To nominacja do kolejnego badania, nie potwierdzony lifting produktu.

## Co dokładnie uruchomiono

- 10 123 skille z train; 2 000 queries do treningu; istniejące 1 000 DEV do oceny. Wszystkie nowe metryki liczone na tym samym root scope i gold. Bez czytania test-A/test-B przez ten eksperyment.
- 1 832 DEV gold skills wykluczone z dodatnich i ujemnych par treningowych. Wykluczono również dokładne znormalizowane duplikaty oraz identyczne teksty zapytań. Semantyczne near-duplicates i pretraining contamination nie zostały wykluczone.
- 186 673 pary uczące, w tym 3 774 pozytywne; 36 953 potencjalne pary usunięte po sprawdzeniu wykluczeń. Te same pary dla wszystkich heads; standardyzacja tylko na train.
- Adam, lr0.003, balanced BCE, 30 epok, jeden ustalony seed. Brak hyperparameter search, early stopping na DEV lub wybierania lepszego seeda.
- Pięć nowych armów używa wspólnego product policy_filter i select(admissible=...), ale score powstaje dla całej biblioteki, następnie wybierane jest top200. To nie benchmark produkcyjnego ograniczonego candidate source. Brak dependencies/negative triggers w tym korpusie nie stresuje tych bramek.
- Niezależny review CTO wykrył przed treningiem, że DEV dokumenty mogły wejść jako negatywy. Przerwano pierwszy proces podczas kodowania body, przed feature construction/treningiem/wynikami; poprawiono wykluczenie i zachowano oryginalny manifest. Parametry i sześć armów pozostały stałe.

## Koszt i ograniczenia

Ukończony proces trwał **8.61 min** z cache name/description z przerwanego runu. Każdy head trenował około **2 s** na RTX4090. Body i flat wymagały po około **3,5 min** kodowania całego banku; 3 000 query embeddings około **24,5 s** w batchu. To nie online p95 pojedynczego query.

Sam forward headu dla 10 123 par miał GPU p95 0,55 ms dla field MLP i 0,54 ms dla sparse-only. Pomiar pomija przygotowanie cech, query embedding, transfer wejścia, sieć, startup i hook. **Nie dowodzi SLA300ms.** MLP nie jest dominującym kosztem; do przyjęcia należy zmierzyć koszt wszystkich sygnałów.

Encoder był ograniczony do 1 024 tokenów: **6 543/10 123 body (64,6%)** i **6 686/10 123 flat (66,0%)** przekraczało limit. To poważne ograniczenie, szczególnie dla tezy o dostępie do body. Dodatkowo per-field ma większy łączny budżet tekstu i inną liczbę parametrów niż flat. Nie jest to czysta ablacją struktury ani pełnotekstowa reprodukcja. QA potwierdziło brak obciętych queries także po dodaniu promptu (max291train/219DEV tokens).

Query-bootstrap ignoruje zależności wewnątrz rodzin skilli, wariancję treningowego seeda i wiele porównań. DEV był używany w historii projektu; nie stanowi świeżego confirmatory holdoutu. Brak etykiet NO_SKILL lub downstream wykonania.

## Decyzja i następny mierzalny krok

1. **Zamknąć tę konfigurację field+sparse+dense wynikiem negatywnym** względem prerejestrowanej bramki (+2 pp R@10 z CI>0 i brak >1 pp utraty kompletności). Nie promować jej do runtime ani nie tunować do zwycięstwa na tych 1 000 queries.
2. Dopuścić jako następną hipotezę **mały sparse-only head**: porównać w nowej prerejestracji identyczne trzy sygnały ze stałą średnią, modelem liniowym i MLP, przy identycznych kandydatach oraz select. Odnieść je także do rzeczywistego BM25F. Świeży holdout, kilka seedów, harmful-sibling/NO_SKILL i whole-hook timing są warunkami przyjęcia.
3. Odpowiedź na paper field-aware wymaga osobnej kontroli matched-budget i capacity: np. flat2->16->1 oraz field6->8->1 mają po65parametrów; ta sama łączna liczba dostępnych tokenów, następnie oddzielnie wariant full-body/chunked. Nie uruchomiono tych dodatkowych armów w tym zadaniu.
4. MVP pozostaje sparse remote Go + authoring + telemetry. Wynik badania nie opóźnia pierwszego nadzorowanego pilota.

## Artefakty i QA

- [Protokół](../../../research/spikes/2026-09-06-field-aware/PROTOCOL.md), [implementacja](../../../research/spikes/2026-09-06-field-aware/run.py), [różnice i uwagi](../../../research/spikes/2026-09-06-field-aware/IMPLEMENTATION-NOTES.md).
- [Wyniki JSON](../../../research/spikes/2026-09-06-field-aware/results.json), [rankingi per-query](../../../research/spikes/2026-09-06-field-aware/dev-rankings.jsonl.gz), [manifest](../../../research/spikes/2026-09-06-field-aware/manifest.json), [provenance](../../../research/spikes/2026-09-06-field-aware/provenance.json).
- [Niezależny review CTO](field-aware-review.md), [QA wyników](../../../research/spikes/2026-09-06-field-aware/qa-results.json). Wszystkie pięć zestawów metryk odtworzono z 5 000 zapisanych rekordów; hashe i rozłączne etykiety zweryfikowane. Nie wykonano nowego runu modelu po obejrzeniu wyniku.

Odtwarzanie z katalogu repo: `/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-field-aware/run.py`, następnie ten sam Python z `qa.py`. Wagi encoderów i dane muszą być obecne lokalnie; kod wymusza offline. Cache pozostaje ignorowany przez Git.
