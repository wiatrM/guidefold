# Research użytkowników
Data odczytu źródeł: 2026-09-06. Desk research; brak rozmów z klientami i brak reprezentatywnej próby.
Wejścia: [brief](00-brief.md), [pivot §1 i §12a](../../PRODUCT-PIVOT.md), [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md), [katalog badań](../../AGENT-SKILLS-RESEARCH.md).
## 1. Obserwacje
| ID | Obserwacja i dowód | Granica dowodu | Wpływ na UI |
|---|---|---|---|
| R1 | Maintainer kolekcji skilli opisuje utrzymywanie symlinków, aby udostępnić zagnieżdżone skille: [Claude #28266](https://github.com/anthropics/claude-code/issues/28266), 2026-02-24. | Historyczne, zamknięte zgłoszenie jednego układu katalogów; nie dowodzi dzisiejszego braku nested skills. [Aktualne docs](https://code.claude.com/docs/en/skills), odczyt 2026-09-06, opisują nested discovery. | Import pokazuje znalezione i pominięte ścieżki; Map rozdziela położenie pliku od relacji wiedzy. |
| R2 | Autor prośby o wspólne instrukcje Copilota opisuje kopiowanie i synchronizowanie plików między repo: [discussion #179641](https://github.com/orgs/community/discussions/179641), 2025-11-14. | Jest to potrzeba zgłaszającego w multi-repo, nie dowód monorepo, aktualnych limitów ani popytu na Guidefold. | Skill pokazuje ownera, źródło i rewizję; Proposals podaje zakres zmiany przed decyzją. |
| R3 | Użytkownik eksperymentujący z Copilot CLI pyta o wybór agentów, skilli i instrukcji dla konkretnego workflow: [discussion #183962](https://github.com/orgs/community/discussions/183962), 2026-01-11. | Pytanie jednej osoby; odpowiedzi społeczności nie są specyfikacją produktu. | Import nazywa typ źródła, a Skill tłumaczy zastosowanie instrukcji bez wymagania znajomości kategorii modeli. |
| R4 | Autor wątku Cursor opisuje pracę developerów od root albo podfolderu i obawę o koszt indeksowania dużej reszty repo: [wątek 160263](https://forum.cursor.com/t/finding-skills-rules-in-the-same-repo-above-the-project-root/160263), 2026-05-11/12. | Zgłoszona obawa, bez pomiaru spowolnienia; nie uogólniamy sposobu pracy na wszystkie zespoły. | Organization/Integrations pokazuje repo i scope połączenia; link do Skill zachowuje kontekst wejścia. |
| R5 | Użytkownik zgłasza identyczne skille z dwóch pluginów: [anthropics/skills #189](https://github.com/anthropics/skills/issues/189), 2025-12-30, Claude 2.0.76. | Nie odtwarzaliśmy błędu; deklarowanych strat tokenów nie traktujemy jako zmierzonej oszczędności. | Library używa tożsamości i rewizji, a Import pokazuje deduplikację jako wynik, nie mnoży rekordów według instalacji. |
| R6 | Autor prosi o odróżnienie uploadu, rewizji domyślnej i załadowanej przez agenta: [google/skills #183](https://github.com/google/skills/issues/183), 2026-07-10. | Prośba o dokumentację weryfikacji, nie potwierdzony incydent; [Manage skills](https://docs.cloud.google.com/agent-registry/manage-skills), aktualizacja 2026-08-26, potwierdza model rewizji, nie użycie. | Skill i Usage pokazują oddzielnie publikację oraz potwierdzone załadowanie; brak obserwacji to Unknown. |
| R7 | Wewnętrzny pivot wymaga decyzji ownera ze źródłem i review w Git: [§1, §3, §7, §12a](../../PRODUCT-PIVOT.md), 2026-09-06; katalog badań rozdziela retrieval od wyniku zadania. | To wymaganie i hipoteza produktu, nie zaobserwowane zachowanie klienta; stary PRODUCT-FOCUS ma jawnie historyczne tezy o konkurencji. | Proposals zestawia diff i źródło; Usage zaczyna od powodów przeglądu, bez utożsamiania pobrań z wartością. |
## 2. Hipotezy
| Hipoteza | Co ją obali |
|---|---|
| [założenie] Owner instrukcji chce wracać do kolejki zmian źródeł. | Mimo zauważonych, istotnych zmian źródeł lub negatywnego feedbacku nie korzysta z kolejki; sprawdzamy decyzje poza Guidefold. Brak zdarzeń oznacza brak rozstrzygnięcia (pivot §1/§13). |
| [założenie] Repo/scope/rewizja pomagają odróżnić podobne instrukcje. | Uczestnicy nadal mylą zastosowanie po odczytaniu tych pól albo nie używają ich przy zadaniu. |
| [założenie] Przygotowanie w UI skraca review, mimo eksportu do Git. | Pomiar całego obiegu UI → Git na równoważnych zadaniach, z kontrolą kolejności, wykaże powtarzalnie równy lub większy czas niż dotychczasowy Git. Więcej błędów jest osobnym warunkiem jakości. Niepewny pomiar oznacza brak rozstrzygnięcia; próg istotnej oszczędności ustalamy przed pilotem. |
## 3. Pytania do pilotów
| ID | Brakujący dowód |
|---|---|
| Q1 | Kto ostatnio poprawił wspólną instrukcję i kto zdecydował o jej przyjęciu? |
| Q2 | Czy root/podfolder, instalacje i konkretne wersje harnessów zmieniają dostępność instrukcji w ich repo? |
| Q3 | Jaki fragment manifestu może opuścić komputer i kto to zatwierdza? |
| Q4 | Czy owner potrzebuje mapy do decyzji, czy wystarcza lista ze źródłami? |
| Q5 | Czy rozumie różnicę między eksportem, publikacją a załadowaniem; gdzie kończy pracę? |
| Q6 | Która obserwacja użycia wywołuje zmianę treści, a jaka pozostaje ciekawostką? |
Nie wyprowadzamy stanowisk pracy, częstotliwości problemu ani gotowości do zapłaty z reakcji pod issue. Obserwacje uzasadniają pytania i hipotezy interfejsu.
## Przegląd
R1: Owner + Badacz UX; P1=0/P2=2/P3=0 (unikalne). Doprecyzowano okazje do decyzji, cały obieg review i niepewność.
R2: Owner + Badacz UX; otwarte P1=0/P2=0/P3=0. Etap zamknięty, 2026-09-06.
