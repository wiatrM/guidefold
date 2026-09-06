# CEO — kolejność badań nad jakością metadanych i pseudozapytań

Data: 2026-09-06. Zakres: przegląd strategii i bramek; bez uruchamiania GPU, pobierania korpusu i zmian produkcyjnych. Raport powstaje podczas trwającego eksperymentu; nie zna jego wyników. Aktualna prośba użytkownika autoryzuje dalsze iteracje badawcze. Wcześniejsze zamrożenie nie jest powodem do ich zatrzymania.

## Decyzja

**Najpierw poprawić reprezentację istniejących skilli i zmierzyć wpływ na rzeczywisty sparse; potem sprawdzić, czy mały head korzysta z większej liczby istniejących etykiet; dopiero następnie rozbudować pulę dokumentów do testu skali i distractorów.** Nie ma obecnie potrzeby pobierać 30 tys. skilli, żeby ustalić, czy enrichment pomaga.

To kolejność wartości informacyjnej. Żaden etap nie daje gwarancji dodatniego wyniku i nie jest obowiązkiem kontynuowania nieskutecznego wariantu. Dodatni mały pilot uzasadnia kolejny zamrożony eksperyment, a nie rollout całego produktu.

## Dlaczego ta kolejność

| Priorytet | Pytanie i istniejący zasób | Kiedy przejść dalej |
|---|---|---|
| 1. Metadata + pseudoqueries | Czy grounded intenty i parafrazy zadania poprawiają obecny BM25F na pełnym banku 10 123 skilli bez modelu podczas SEARCH? | Po zamknięciu obecnego A/B/C, QA groundingu, kosztów i szkód w innych zapytaniach. |
| 2. Learning curve małego sparse headu | Czy większy nadzór poprawia stałą reprezentację? W źródle jest 63 259 TRAIN queries, nie 63 tys. niezależnych skilli. | Po przypięciu reprezentacji i holdoutu; train na zagnieżdżonych próbkach z legalnie dostępnej reszty. |
| 3. 30k candidate bank | Jak dodatkowe podobne dokumenty zmieniają recall, kolizje, selekcję i koszt? | Gdy mamy stabilny wariant wart stresowania lub konkretny wymóg partnera. |

Ostatni inventory znalazł 3 000 wcześniej odnotowanych query IDs i 60 259 pozostałych przed nowym enrichment runem. To pula „nieodnotowana w przeskanowanych artefaktach”, a nie gwarantowanie nieoglądane dane. Obecne 2 048 queries również trzeba dopisać do rejestru ekspozycji. Przybliżone 63k nie oznacza, że wszystko można teraz przeznaczyć na trening: rezerwujemy ewaluację, wykluczamy duplikaty i kontrolujemy przeciek grup zadań/skilli.

Learning curve ma utrzymać ten sam tokenizer, sygnały, kandydatów, loss, head, budżet i holdout. Np. trzy zagnieżdżone, rosnące próbki połączone z prerejestrowanymi seedami rozstrzygają zależność od danych; konkretne rozmiary wybiera się dopiero po audycie dostępnych grup, przed wynikiem. Kontrolami pozostają obecny BM25F i identyczna reprezentacja bez uczenia. Nie zmieniać jednocześnie metadanych, funkcji straty i rozmiaru treningu, a potem przypisywać zysku „większym danym”.

Nie rozpoczynałbym pełnego sweepu sześciu nowych receptur i learning curve równocześnie. To różne pytania. Najpierw zamrozić jedną uczoną recepturę z uzasadnioną kontrolą, potem skalować jej dane albo osobno badać loss.

## Co obecny eksperyment rzeczywiście rozstrzyga

Właściwym protokołem wykonania jest [frozen pilot](../../../research/spikes/2026-09-06-query-enrichment/PROTOCOL.md), nie starszy dokument z propozycją TF-IDF/MAX. Aktualne ramiona:

- A: oryginalny BM25F i oryginalne pola.
- B: A + do trzech grounded intent phrases w triggers.
- C: dokładnie B + do trzech grounded pseudoqueries.

Wybrano niezależnie od gold 512 dokumentów, ale każdy arm przeszukuje wszystkie 10 123. Generator dostaje wyłącznie dokument i jego ucięty fragment body; nie otrzymuje query/qrels ani wyników. Oryginalne bodies, status, scope, requires i negative triggers pozostają bez zmian. To właściwa kontrola dla aktualnego pytania.

B−A mierzy dodany pakiet tekstu. C−B mierzy dodatkowe pseudoqueries. To nie czysta izolacja „jakości metadanych”: C ma też więcej tekstu i szans na dopasowanie. Mechaniczna zgodność evidence quote ze źródłem nie sprawdza, czy wniosek zachowuje warunki użycia, negację i parametry. Potrzebny jest ślepy audyt semantyczny przed wynikami; dokument niespełniający filtra zostaje w przypisanej grupie z pustym dodatkiem, bez wymiany na wygodniejszy.

## Dlaczego pozytywny partial coverage nie oznacza efektu pełnego enrichment

512/10 123 to około 5,1% banku. Nawet jeśli taki pilot poprawi wynik całkowity, nie wolno przemnożyć zysku przez około 20 ani przyjąć, że pełne pokrycie będzie monotonicznie lepsze.

1. **Konkurencja.** Przy częściowym pokryciu tylko niektóre dokumenty dostają nowe sygnały. Przy pełnym pokryciu wzmacniamy także konkurentów i podobne siblingi. Nowe trafienie może przestać wygrywać.
2. **Statystyki indeksu.** IDF, długość pól i normalizacja zmieniają się z pokryciem całej biblioteki. Efekt nie jest sumą niezależnych interwencji na dokumentach.
3. **Mała ekspozycja.** Większość queries nie ma zmodyfikowanego gold. Przy niezależnym przybliżeniu szansa dotknięcia co najmniej jednego gold dla k=1/2/3 to około 5%/10%/14%, a dotknięcia wszystkich spada z k. Faktyczne liczebności podaje eksperyment. Mały overall może być rozcieńczony; sam dodatni podzbiór nie dowodzi poprawy systemu.
4. **Collateral effects.** Queries bez zmodyfikowanego gold mogą tracić, bo wzmacniamy ich niepoprawnych kandydatów. Pokazujemy ich wynik niezależnie.
5. **Domena i etykiety.** Nowy wewnętrzny query sample nie jest nową organizacją; qrels nie pokrywają wszystkich alternatyw ani NO_SKILL. Nieoznaczony dokument nie staje się automatycznie zweryfikowanym szkodliwym distractorem.

Dodatni gate daje GO na nową prerejestrację pełnego pokrycia 10 123, z tym samym zamrożonym generatorem, kosztem, kolejną oceną i osobnym manifestem. Można wykonać ją od razu w ramach żądanej iteracji, po przygotowaniu testu; nie wymaga ponownego pytania użytkownika. Nie jest jeszcze GO na 30k ani zmianę produkcyjnego indeksu.

## Stop/advance: konkretny mechanizm

**Obecnej bramki nie zmieniamy po wyniku.** Protokół wymaga dla C−A overall Recall@10 delta > 0 z dolną granicą opisowego 95% CI > 0, nieujemnego point delta all-gold-selected@4 i no-gold-selected Recall@10 delta co najmniej −0,5 pp. B−A i C−B są diagnostyką; lepszy B nie zastępuje niespełnionej głównej bramki C.

| Wynik | Następny krok |
|---|---|
| Bramka spełniona, grounding i koszt zaakceptowane w QA | Nowy protokół pełnego pokrycia obecnego banku. Nie zmieniać generatora po wyniku; nowy sample ewaluacyjny, pełne per-query wyniki, koszty i guardrails. |
| Dodatni tylko any/all-gold stratum lub dolna granica overall ≤ 0 | Nierozstrzygnięty/ujemny screening. Zakończyć run z takim werdyktem. Nowy, nazwany eksperyment może zwiększyć ekspozycję albo sprawdzić konkretny mechanizm; nie deklarować, że gate przeszedł. |
| Zyskuje B, a C szkodzi | Pseudoqueries nie są domyślnym dalszym krokiem. B może nominować osobną kontrolowaną próbę; wymiana zwycięzcy nie zmienia wyniku bieżącego testu. |
| Szkoda no-gold stratum lub spadek kompletności poza gate | Zatrzymać automatyczne skalowanie wariantu. Obejrzeć znane już błędy jako DEV; nowy prompt/filtr potrzebuje nowego protokołu i ocenianych queries. |
| Częste nieuzasadnione capabilities, pominięte negacje, istotny truncation | Nie zwiększać generowania na ślepo. Najpierw audyt źródeł i sposobu podawania body, potem osobno oceniany poprawiony generator. |
| Dobre retrieval, duży koszt indeksu/SEARCH lub brak korzyści użytkownika | Nie przyjmować do MVP. Rozważyć krótszą reprezentację jako nowe badanie albo zakończyć linię. |
| Brak poprawy i brak przekonującego mechanizmu do poprawienia | Zapisać negatywny wynik i przejść do innego pytania. Nie zwiększać samej skali z nadzieją na pozytywną tabelę. |

Dzisiejszy query-bootstrap ma zależności współdzielonych skilli i wiele porównań; dodatnia dolna granica jest screeningiem, nie pełnym confirmatory dowodem. Pełny follow-up powinien z góry określić główny kontrast, tolerowaną szkodę, rozmiar próby i sposób obsługi zależnych grup. Dotychczasowe wyniki pozostają częścią historii niezależnie od kolejnych iteracji.

## Kiedy odwrócić kolejność

- **Najpierw diagnostyka etykiet/treści:** jeżeli source nie opisuje potrzebnej capability, qrels są niejednoznaczne lub truncation usuwa ograniczenia. LLM nie naprawi braku wiedzy przez dopisanie pewnie brzmiących słów.
- **Najpierw candidate recall:** jeśli poprawny skill nie trafia do kandydatów, nowy head sam go nie odzyska. Enrichment jest wtedy rozsądnym mechanizmem do sprawdzenia; nie rozwiąże hard policy lub selection-cap niemożliwości.
- **Najpierw learning curve:** jeśli reprezentacja i candidate coverage są wystarczające, ale wspólne sygnały źle porządkują trafienia, a enrichment nie pokazuje korzyści. To test scoringu, nie pretekst do większego korpusu.
- **30k wcześniej:** tylko gdy partner rzeczywiście ma taką skalę albo teza paperu jawnie dotyczy konkurencji i skalowania. Wtedy stałe queries/gold i przypięte przyrosty banku, dedup, pochodzenie/licencje oraz audyt potencjalnych alternatyw. Dodatkowe nieetykietowane dokumenty służą stress testowi, nie dowodowi transferu czy zweryfikowanym negatywom.
- **Najpierw użytkownik:** gdy kolejna poprawa offline nie rozstrzyga, czy developer chce i używa dostarczanej instrukcji. Realna sesja nadal jest krytycznym źródłem informacji dla MVP.

## MVP i paper

MVP nadal domykamy jako istniejący sparse + authoring + telemetria; enrichment może być później zatwierdzonym artefaktem indeksu bez LLM podczas SEARCH. To mniejszy koszt operacyjny niż nowy model online, ale nadal trzeba sprawdzić rozmiar indeksu, build/refresh, całe opóźnienie klienta, rewizje i odbiór ownera. Offline sidecar nie przepisuje polityk ani oryginalnych procedur.

Paper może badać wpływ grounded enrichment na silny BM25F, interference przy częściowym i pełnym pokryciu oraz kompletność zestawu. Samo „LLM generuje zapytania do BM25” nie jest nowością: mamy [doc2query](https://arxiv.org/abs/1904.08375), [Doc2Query--](https://arxiv.org/abs/2301.03266) i [Skill2Query](https://arxiv.org/abs/2608.16071). Szczegółowe źródła oraz ograniczenia ich reprodukcji są w [przeglądzie enrichment](query-enrichment-sources.md).

Zaakceptowany partial pilot może uzasadnić tezę o konkretnym wariancie w tej populacji; nie poprawie developer productivity, skutecznej odmowie NO_SKILL, bezpieczeństwie polityk ani przewadze na 30k. Mocniejszy paper potrzebuje niezależnego porównania, kontroli zwiększonego budżetu tekstu i kosztów oraz jawnego treatment coverage. Nie trzeba czekać z partnerem do publikacji i nie trzeba obiecywać przełomu, żeby obecne spiki miały wartość.

## Źródła lokalne

[Protokół wykonania](../../../research/spikes/2026-09-06-query-enrichment/PROTOCOL.md), [manifest](../../../research/spikes/2026-09-06-query-enrichment/manifest.json), [wyniki field-aware](field-aware-results.md), [diagnostyka i inventory](diagnostics-v2.md), [propozycja badania funkcji celu](protocol-v2-proposal.md), [wcześniejsza decyzja CEO](ceo.md).
