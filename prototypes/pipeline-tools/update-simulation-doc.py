from pathlib import Path
p=Path("docs/ui/pipeline/05-simulation.md");s=p.read_text()
s=s.replace("Kliknięcie oznacza aktywację linku, przycisku lub opcji; wpisywanie ma osobny licznik.", "K oznacza aktywacje linków, przycisków, radia i disclosure; D to liczba disclosure zawarta w K, S — wybory select, W — wpisania w pole.")
s=s.replace("Oczekuje na trzy niezależne przebiegi przeglądarkowe.", """[syntetyczne, n=3] Wykonano 9/9 lokalnych zadań. Wszystkie trzy sesje rozróżniły eksport od Published (fixture); żadna nie potwierdza realnego importu, Git lub loaded.
| Persona / zadanie | Faktyczna droga | K; D/S/W | Zagubienie / wynik | Syntetyczne „na głos” |
|---|---|---|---|---|
| P1 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | „Sprawdzam commit i listę źródeł przed importem.” |
| P1 B | Wybrany skill → source → pełny plik | 2; 1/0/0 | Brak; ukończone | „Mam ścieżkę, commit i hash.” |
| P1 C | Proposals → kandydat → approve + powód → export → sync | 6; 1/0/1 | Krótka niepewność statusu źródła; ukończone | „Pobranie daje Awaiting Git, a nie publikację.” |
| P2 A | Dostawca → org → import → Map | 5; 0/0/0 | Brak; ukończone | „To lokalny scenariusz właściciela.” |
| P2 B | Source → Content → Map → Library z filtrami → Skill → powrót | 8; 0/1/1 | Filtry zachowane; ukończone | „Nie muszę filtrować od nowa.” |
| P2 C | Proposals → approve → export → sync → Usage → Proposals | 7; 0/0/1 | Utrata rewizji; ukończone z tarciem | „Pole Revision jest puste.” |
| P3 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | „Parsed nie znaczy Published.” |
| P3 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | „Active to stan źródła.” |
| P3 C | Pełne źródła → approve → export → sync → Usage → ręczne filtry → Integrations | 13; 3/1/2 | Ręczne odtworzenie scope/SHA; lokalne C ukończone | „Unknown pozostaje Unknown.” |
Pełne kroki i cytaty: [P1 R1](../../../prototypes/pipeline-wireframes/qa/s05-owner-r1.json), [P2 R1](../../../prototypes/pipeline-wireframes/qa/s05-dev-r1.json), [P3 R1](../../../prototypes/pipeline-wireframes/qa/s05-operator-r1.json).
P3 C obejmuje późniejsze sprawdzenie dowodów i powrót do Library. Liczniki nie porównują efektywności person. P1: 1440×1100; P2/P3: 1440×1000. Test B korzystał z domyślnie wybranego postgres-auth; P2 dodatkowo sprawdził wyszukanie z filtrami.
""")
s=s.replace("Oczekuje na wyniki R1; nie rozpoczynamy hi-fi przed zamknięciem przeglądu.", """| Tarcie / cytat R1 | Przed | Poprawka | Po |
|---|---|---|---|
| F1 P2: „Check usage evidence” → „Revision / Optional SHA-256”, Scope All | Skill przenoszony; scope zależał od wejścia, rewizja ginęła | Jawnie przenoszone skill, scope i SHA kandydata; formularz odczytuje URL | Regresja Chromium PASS; nowe symulacje w toku |
| F2 P3: „Review decision: approve, edit or reject” w Published | Skrót obiecywał niedostępne akcje | Etykieta zależna od etapu, końcowo Review publication evidence | Regresja PASS |
| F3 P3: „publication not established” obok Published | Brak perspektywy czasowej | publication at import: not established | Regresja PASS |
| F4 P3: „Evidence level / Context loaded” dopiero pod długim porównaniem | Trudno ocenić poziom dowodu na początku | Zwięzłe Local simulation only / Context loaded Unknown obok statusu | Regresja PASS; y395–433 przy 1280×720 |
Przed: unikalne P1=0/P2=1/P3=3. Poprawiono renderer i zregenerowano siedem HTML. Aktualizacja zależna: 04 §3 opisuje revision w URL; zakres U4 pozostał ten sam.
[Regresje](../../../prototypes/pipeline-wireframes/qa/s05-regressions.json): pięć warunków PASS, 0 błędów JS; komenda node s05-regressions.mjs z prototypes/pipeline-tools.
Runda 2: nowe agenty ze świeżym kontekstem i nowymi sesjami, te same cele i brak instrukcji nawigacji; wyniki w toku.
""")
s=s.replace("Czy samo UI pozwala", "Syntetyczne przejście nie bada odrzucenia/konfliktu, kosztu rzeczywistego Git ani wyszukiwania dowolnego skilla. Niezależna kontrola bajtów eksportu pochodzi z etapu 4 i P3 R1; pozostałe sesje potwierdzają zdarzenie download.\nCzy samo UI pozwala")
p.write_text(s)
