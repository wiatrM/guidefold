from pathlib import Path
p=Path("docs/ui/pipeline/05-simulation.md");s=p.read_text().replace("Status: w toku.","Status: wyniki po dwóch rundach symulacji; formalny przegląd w toku.")
s=s.replace("Regresja Chromium PASS; nowe symulacje w toku", "Regresja PASS; P3 R2 odczytuje właściwy scope i SHA bez ręcznego wpisywania")
s=s.replace("pięć warunków PASS", "sześć warunków PASS")
s=s.replace("Runda 2: nowe agenty ze świeżym kontekstem i nowymi sesjami, te same cele i brak instrukcji nawigacji; wyniki w toku.", """[syntetyczne, n=3] Runda 2 użyła nowych agentów i nowych sesji, bez instrukcji nawigacji; 9/9 lokalnych zadań ukończone. P3 dodatkowo określił brak dowodu loaded zgodnie z zadaniem persony.
| Persona / zadanie | Faktyczna droga | K; D/S/W | Zagubienie / wynik | Syntetyczne „na głos” |
|---|---|---|---|---|
| P1 A | Domyślny dostawca → org → manifest → import → Map | 5; 1/0/0 | Brak; ukończone | „Nie uruchamiam proponowanych poleceń.” |
| P1 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | „Mam dokładną ścieżkę źródła, commit i SHA-256.” |
| P1 C | Proposals → pełny kandydat otwórz/zamknij → approve → export → sync | 7; 2/0/1 | Długi blok treści; ukończone | „Długi blok treści oddala formularz decyzji.” |
| P2 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | „To podgląd 27 plików, nie skan repo.” |
| P2 B | Source → Content → powrót do Map | 3; 0/0/0 | Kontekst zachowany; ukończone | „Zależy mi, by nadal było widać turnstile.” |
| P2 C | Kandydat otwórz/zamknij → approve → export → sync | 7; 2/0/1 | Brak; ukończone | „Widzę Context loaded: Unknown.” |
| P3 A | Dostawca → org → manifest → import → Map | 6; 1/0/0 | Brak; ukończone | „To jest jawna symulacja.” |
| P3 B | Wybrany skill → source i scope | 1; 0/0/0 | Brak; ukończone | „Mapa od razu pokazuje wybrany postgres-auth.” |
| P3 C | Proposals → approve → export → sync → Usage z odziedziczonym kontekstem | 6; 0/0/1 | Zawahanie przy pustej kolejce; ukończone | „Loaded będzie wymagać dowodu klienta.” |
Pełne kroki: [P1 R2](../../../prototypes/pipeline-wireframes/qa/s05-owner-r2.json), [P2 R2](../../../prototypes/pipeline-wireframes/qa/s05-dev-r2.json), [P3 R2](../../../prototypes/pipeline-wireframes/qa/s05-operator-r2.json).
Znormalizowano P3 R2: raport rozdziela 12 zwykłych kliknięć i 1 disclosure, tutaj K=13. Różnice ścieżek, rozwinięć i viewportów nie pozwalają wyliczyć poprawy czasu lub liczby kliknięć.
Po R2: P1=0/P2=0, dwa nowe P3. Nagłówek „Requires review” przy „No observations” zmieniono na Review queue i potwierdzono regresją; nie wymagał ponownej symulacji pełnej ścieżki.
Pozostały P3: „Full candidate SKILL.md” jako surowy Markdown utrudnia skanowanie. W etapie 6 wprowadzić semantyczny podgląd body i skrót do decyzji, zachowując dokładny surowy plik. To uwaga do przeniesienia, nie zamknięty finding.
""")
s=s.replace("Niezależna kontrola bajtów eksportu pochodzi z etapu 4 i P3 R1", "Niezależna kontrola bajtów eksportu pochodzi z etapu 4 i P3 R1/R2")
s=s.replace("z renderowanego DOM i screenshotów", "z renderowanego DOM i dostępnych screenshotów")
p.write_text(s)
