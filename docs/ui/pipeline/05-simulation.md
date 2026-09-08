# Symulacja użycia
Status: dwie rundy symulacji i dwa formalne przeglądy zakończone; 0 otwartych P1/P2. Data: 2026-09-06. Wejścia: [persony](02-personas.md), [makiety po R2](04-wireframes.md), [U4 AC](../../PRODUCT-PIVOT.md).
## 1. Metoda
[syntetyczne, n=3 na rundę] Każdą personę odgrywa osobny agent ze świeżym kontekstem. Runda 2 używa nowych agentów. Wyniki nie są obserwacją ludzi ani zaliczeniem U4 AC5 (co najmniej 4 z 5 prawdziwych osób).
Agent dostaje zadanie persony oraz adres HTML, bez dokumentu makiet, kodu renderera, fixture JSON, nazw przycisków i instrukcji przejścia. Odkrywa UI z renderowanego DOM i dostępnych screenshotów w nowej sesji Chromium.
Persony: P1 owner instrukcji, P2 developer przy zadaniu, P3 operator dostarczania. Dla zadań wymagających zapisu wszyscy mają rolę fixture owner; persona nie nadaje uprawnień, a member sprawdzono osobno w etapie 4.
| Zadanie | Polecenie wyniku, bez rozwiązania | Kryterium ukończenia |
|---|---|---|
| A | Przeprowadź dostępny scenariusz wprowadzenia repo Meridian i pokaż pierwszą mapę. | Uczestnik przechodzi wejście/import do mapy i rozpoznaje źródło danych jako fixture. |
| B | Znajdź dokładne źródło i zakres skilla postgres-auth. | Wskazuje ścieżkę, commit oraz scope z widocznego UI. |
| C | Oceń dostępną propozycję, podejmij decyzję pozwalającą przekazać ją do Git, pobierz artefakt i doprowadź scenariusz do Published. | Eksport jest faktycznie pobrany; końcowy status jest opisany jako symulacja, bez utożsamienia z użyciem. |
K oznacza aktywacje linków, przycisków, radia i disclosure; D to liczba disclosure zawarta w K, S — wybory select, W — wpisania w pole. Przewijanie i nieudane próby zapisujemy osobno. Czas narzędzi nie jest czasem człowieka.
P1: zadania nie można ukończyć lub wynik jest mylący. P2: istotna utrata kontekstu/dowodu albo konieczne obejście. P3: lokalne tarcie bez utraty poprawnego wyniku.
## 2. Runda 1
[syntetyczne, n=3] Wykonano 9/9 lokalnych zadań. Wszystkie trzy sesje rozróżniły eksport od Published (fixture); żadna nie potwierdza realnego importu, Git lub loaded.
| Persona / zadanie | Faktyczna droga | K; D/S/W | Zagubienie / wynik | Parafrazy syntetycznego myślenia na głos |
|---|---|---|---|---|
| P1 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | Sprawdzam commit i listę źródeł przed importem. |
| P1 B | Wybrany skill → source → pełny plik | 2; 1/0/0 | Brak; ukończone | Mam ścieżkę, commit i hash. |
| P1 C | Proposals → kandydat → approve + powód → export → sync | 6; 1/0/1 | Krótka niepewność statusu źródła; ukończone | Pobranie daje Awaiting Git, a nie publikację. |
| P2 A | Dostawca → org → import → Map | 5; 0/0/0 | Brak; ukończone | To lokalny scenariusz właściciela. |
| P2 B | Source → Content → Map → Library z filtrami → Skill → powrót | 8; 0/1/1 | Filtry zachowane; ukończone | Nie muszę filtrować od nowa. |
| P2 C | Proposals → approve → export → sync → Usage → Proposals | 7; 0/0/1 | Utrata rewizji; ukończone z tarciem | Pole Revision jest puste. |
| P3 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | Parsed nie znaczy Published. |
| P3 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | Active to stan źródła. |
| P3 C | Pełne źródła → approve → export → sync → Usage → ręczne filtry → Integrations | 13; 3/1/2 | Ręczne odtworzenie scope/SHA; lokalne C ukończone | Unknown pozostaje Unknown. |
Pełne kroki i cytaty: [P1 R1](../../../prototypes/pipeline-wireframes/qa/s05-owner-r1.json), [P2 R1](../../../prototypes/pipeline-wireframes/qa/s05-dev-r1.json), [P3 R1](../../../prototypes/pipeline-wireframes/qa/s05-operator-r1.json).
P3 C obejmuje późniejsze sprawdzenie dowodów i powrót do Library. Liczniki nie porównują efektywności person. P1: 1440×1100; P2/P3: 1440×1000. Test B korzystał z domyślnie wybranego postgres-auth; P2 dodatkowo sprawdził wyszukanie z filtrami.

## 3. Poprawki i runda 2
| Tarcie / cytat R1 | Przed | Poprawka | Po |
|---|---|---|---|
| F1 P2: „Check usage evidence” → „Revision / Optional SHA-256”, Scope All | Skill przenoszony; scope zależał od wejścia, rewizja ginęła | Jawnie przenoszone skill, scope i SHA kandydata; formularz odczytuje URL | Regresja PASS; P3 R2 odczytuje właściwy scope i SHA bez ręcznego wpisywania |
| F2 P3: „Review decision: approve, edit or reject” w Published | Skrót obiecywał niedostępne akcje | Etykieta zależna od etapu, końcowo Review publication evidence | Regresja PASS |
| F3 P3: „publication not established” obok Published | Brak perspektywy czasowej | publication at import: not established | Regresja PASS |
| F4 P3: „Evidence level / Context loaded” dopiero pod długim porównaniem | Trudno ocenić poziom dowodu na początku | Zwięzłe Local simulation only / Context loaded Unknown obok statusu | Regresja PASS; y395–433 przy 1280×720 |
Przed: unikalne P1=0/P2=1/P3=3. Poprawiono renderer i zregenerowano siedem HTML. Aktualizacja zależna: 04 §3 opisuje revision w URL; zakres U4 pozostał ten sam.
[Regresje](../../../prototypes/pipeline-wireframes/qa/s05-regressions.json): sześć warunków PASS, 0 błędów JS; komenda node s05-regressions.mjs z prototypes/pipeline-tools.
[syntetyczne, n=3] Runda 2 użyła nowych agentów i nowych sesji, bez instrukcji nawigacji; 9/9 lokalnych zadań ukończone. P3 dodatkowo określił brak dowodu loaded zgodnie z zadaniem persony.
| Persona / zadanie | Faktyczna droga | K; D/S/W | Zagubienie / wynik | Parafrazy syntetycznego myślenia na głos |
|---|---|---|---|---|
| P1 A | Domyślny dostawca → org → manifest → import → Map | 5; 1/0/0 | Brak; ukończone | Nie uruchamiam proponowanych poleceń. |
| P1 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | Mam dokładną ścieżkę źródła, commit i SHA-256. |
| P1 C | Proposals → pełny kandydat otwórz/zamknij → approve → export → sync | 7; 2/0/1 | Długi blok treści; ukończone | Długi blok treści oddala formularz decyzji. |
| P2 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | To podgląd 27 plików, nie skan repo. |
| P2 B | Source → Content → powrót do Map | 3; 0/0/0 | Kontekst zachowany; ukończone | Zależy mi, by nadal było widać turnstile. |
| P2 C | Kandydat otwórz/zamknij → approve → export → sync | 7; 2/0/1 | Brak; ukończone | Widzę Context loaded: Unknown. |
| P3 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | To jest jawna symulacja. |
| P3 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | Mapa od razu pokazuje wybrany postgres-auth. |
| P3 C | Proposals → approve → export → sync → Usage z odziedziczonym kontekstem | 6; 0/0/1 | Zawahanie przy pustej kolejce; ukończone | Loaded będzie wymagać dowodu klienta. |
Pełne kroki: [P1 R2](../../../prototypes/pipeline-wireframes/qa/s05-owner-r2.json), [P2 R2](../../../prototypes/pipeline-wireframes/qa/s05-dev-r2.json), [P3 R2](../../../prototypes/pipeline-wireframes/qa/s05-operator-r2.json).
Znormalizowano P3 R2: raport rozdziela 12 zwykłych kliknięć i 1 disclosure, tutaj K=13. Różnice ścieżek, rozwinięć i viewportów nie pozwalają wyliczyć poprawy czasu lub liczby kliknięć.
Po R2: P1=0/P2=0, dwa nowe P3. Nagłówek „Requires review” przy „No observations” zmieniono na Review queue i potwierdzono regresją; nie wymagał ponownej symulacji pełnej ścieżki.
Pozostały P3: „Full candidate SKILL.md” jako surowy Markdown utrudnia skanowanie. W etapie 6 wprowadzić semantyczny podgląd body i skrót do decyzji, zachowując dokładny surowy plik. To uwaga do przeniesienia, nie zamknięty finding.


## 4. Pytania do ludzi
Syntetyczne przejście nie bada odrzucenia/konfliktu, kosztu rzeczywistego Git ani wyszukiwania dowolnego skilla. Niezależna kontrola bajtów eksportu pochodzi z etapu 4 i P3 R1/R2; pozostałe sesje potwierdzają zdarzenie download.
Czy samo UI pozwala rozpoznać właściwy zakres i źródło, a nie tylko wskazany skill? Czy właściciel rozumie wpływ decyzji przed eksportem?
Czy powrót do Git i czas oczekiwania na sync tworzą większy koszt niż sam przegląd instrukcji? Czy rozróżnienie published/loaded zmienia diagnozę w rzeczywistym incydencie?
[założenie] Przyjęte trzy zadania są reprezentatywne dla U4. Obali to pilot, jeśli realne cele lub punkty wejścia wymagają innego dowodu; wyniki agentów tego nie rozstrzygają.
## Przegląd
R1 formalny: Owner + Badacz UX; P1=0/P2=0/nowe P3=2. Uściślono AC5 (4 z 5 osób) i oznaczono parafrazy myślenia na głos.
R2 formalny: Owner + Badacz UX; otwarte P1=0/P2=0, nowe P3=0; znany P3=1 przeniesiony do etapu 6. Etap zamknięty, 2026-09-06.
