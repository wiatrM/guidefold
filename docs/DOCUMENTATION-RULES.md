# Reguły dokumentacji Guidefold
Status: aktywne reguły projektu. Data: 2026-09-06. Reguły użycia i utrzymania dokumentów produktu oraz hosted UI; polecenie właściciela z bieżącej pracy.
## Pierwszeństwo
Bieżące polecenie użytkownika wyznacza zakres pracy. Dokument Proposed opisuje proponowane zachowanie; nie staje się dowodem wdrożenia ani pozwoleniem na publikację, migrację danych lub zmianę zadań zewnętrznych.
W obrębie autoryzowanego pivotu PRD określa wymagania, architektura ograniczenia techniczne, backlog kolejność, review uzasadnienia. Nie rozstrzygaj sprzeczności samą datą pliku.
Przy rozbieżności zapisz ją, wybierz decyzję zgodną z bieżącym zakresem i wskaż dokument zastępowany. Zachowaj historię ADR; status Accepted wymaga rzeczywistej decyzji właściciela, nie samego ukończenia prototypu.
Kod, testy i raporty z identyfikatorem przebiegu dowodzą implementacji. Plan, screenshot i pozytywna recenzja agenta nie zastępują pomiaru ani prawdziwego pilota.
## Wybór dokumentu
| Praca | Czytaj | Rola dokumentu |
|---|---|---|
| Zakres, wymagania, acceptance criteria | [PRODUCT-PIVOT](PRODUCT-PIVOT.md) | U1–U11; R/Q/P i obietnice produktu. |
| Backend, frontend, granice modułów, API | [PIVOT-ARCHITECTURE](PIVOT-ARCHITECTURE.md) | React + Go + worker; multi-org, publikacja i kontrakty. |
| Kontrakt API, DTO, schemat DB, joby | [API-CONTRACT](API-CONTRACT.md) | Obowiązujący kontrakt: endpointy, DTO, kody błędów, `gf`/`gfm`, kontrakt API–worker. Kod zmienia się razem z nim; nie zastępuje HARNESS-SERVICE-CONTRACT ani SEARCH-USE-TELEMETRY. |
| Dobór zadania i zależności | [PIVOT-BACKLOG](PIVOT-BACKLOG.md) | P01–P15 są lokalnymi historiami; nie numerami nowych issue. |
| Powód zmiany lub odrzucony wariant | [PIVOT-REVIEW](PIVOT-REVIEW.md) | Oceny ról agentowych i rozstrzygnięcia, nie głosy klientów. |
| Zmiana wcześniejszej decyzji | [ADR-0031](adr/ADR-0031-monorepo-to-managed-skill-library.md) oraz właściwy wcześniejszy ADR | Proponowane poprawki i konsekwencje; bez cichego nadpisywania historii. |
| Hosted UI | [pipeline/README](ui/pipeline/README.md), potem dokument właściwego etapu | Rejestr stanu przeglądów i źródło szczegółowych decyzji ekranów. |
| Architektura informacji, UX i system wizualny | [IA](ui/IA.md), [UX](ui/UX.md), [UI](ui/UI.md) | Dokumenty aktualizowane pod pivot; status na początku wskazuje zakres przeglądu. Historyczne różnice zapisuje brief; nie odtwarzaj starych czterech sekcji. |
| Istniejący CLI lub kontrakt SEARCH/USE | Właściwy kod, testy, HARNESS-SERVICE-CONTRACT i SEARCH-USE-TELEMETRY | Sprawdź bieżące zachowanie; nie opisuj komend projektowanych jako dostępnych. |
| Instalacja i uwierzytelnienie adaptera (harness ↔ hosted API) | [HOWTO-adapter](HOWTO-adapter.md) | Pięć komend cytowanych dosłownie z `skills/guidefold/scripts/guidefold`, tabela rozwiązywania problemów; ten sam przewodnik w zakładce Organization › Integrations. Publikacja importu to osobny krok. |
| Rubryka pilota, dowody U11, raport porównania harnessów | [pilot/README](pilot/README.md), [pilot/PIVOT-RUBRIC](pilot/PIVOT-RUBRIC.md), [pilot/E6.7-PROTOCOL](pilot/E6.7-PROTOCOL.md) | Etykiety R/Q/P, progi go/no-go i `tools/pilot/pivot_report.py`; syntetyczny run nie jest dowodem z pilota. |
| Stan implementacji pivotu | [PIVOT-IMPLEMENTATION](PIVOT-IMPLEMENTATION.md) | Które P01–P15 mają kod i testy, mapa modułów Go, luki przed pilotem; nie dowód pilota ani zamiennik backlogu. |
## Pipeline UI
| Etap | Dokument | Zastosowanie |
|---|---|---|
| 0 | [00-brief](ui/pipeline/00-brief.md) | Cel, siedem widoków, różnice względem starego IA. |
| 1 | [01-research](ui/pipeline/01-research.md) | Obserwacje ze źródłami, ograniczenia i pytania do ludzi. |
| 2 | [02-personas](ui/pipeline/02-personas.md) | Hipotezy zadań i odbiorców; nie role autoryzacji. |
| 3 | [03-survey](ui/pipeline/03-survey.md) | Kwestionariusz, progi decyzji i jawne odpowiedzi syntetyczne. |
| 4 | [04-wireframes](ui/pipeline/04-wireframes.md) | Kompozycja, nawigacja, URL, stany i makiety HTML. |
| 5 | [05-simulation](ui/pipeline/05-simulation.md) | Tarcia i poprawki; nie zaliczenie U4 Q z prawdziwymi ludźmi. |
| 6 | [06-ux-ui](ui/pipeline/06-ux-ui.md) | Tokeny, stringi, responsywność i dowody wizualne. |
| 7 | [07-frontend](ui/pipeline/07-frontend.md) | Stack, dane/API, budżety i plan implementacji. |
| 8 | [08-components](ui/pipeline/08-components.md) | API komponentów, stany, a11y, testy i galeria. |
Etapy są zależne: następny zaczyna się po dwóch rundach Owner + specjalista i 0 otwartych P1/P2, zapisanych w sekcji Przegląd. Gdy runda 2 pozostawia P1/P2, wykonaj rundę 3 po poprawkach.
Zmiana gotowego etapu wymaga oceny wpływu na zależne dokumenty/artefakty i ponownego przeglądu zmienionego zakresu; nie uruchamiaj całego pipeline’u dla lokalnej poprawki, jeśli zależności pozostają prawdziwe.
Dokumenty etapów: polski, maks. 120 linii (brief 40); README 30. Stringi UI, tokeny, komponenty i pliki: angielski. Jedyny wzorzec wizualny: prototypes/industrial-surveyor; fixture: examples/monorepo, zawsze podpisany.
## Nowe pliki
Każdy nowy dokument planistyczny podaje status, datę, cel, wejścia i zakres zastępowania. Dodaj go do właściwego indeksu oraz tej tabeli, jeśli wprowadza nowy rodzaj decyzji; nie dopisuj tu każdego testu i screenshotu.
Pliki źródłowe, makiety i dowody QA mają odnośnik z dokumentu etapu, do którego należą. Raport wskazuje komendę/środowisko, fixture lub rzeczywiste dane, rezultat i ograniczenia.
Nie duplikuj tokenów, kontraktów lub wymagań: wskaż kanoniczny plik. Przy zmianie zachowania aktualizuj jego źródło i zależne opisy w tej samej pracy.
Twierdzenia o użytkownikach mają źródło z datą albo [założenie] i kryterium obalenia. Dane syntetyczne nie zamykają pytań do ludzi. Unknown nie jest zerem, eksport nie jest publikacją, pobranie nie jest użyciem.
Reguły są instrukcją odczytu i utrzymania. Nie nadają dodatkowych uprawnień, nie wymagają powtórnego zatwierdzania pracy już zleconej i nie przenoszą prototypu do produkcji.

## Instrukcje projektu
[AGENTS.md](../AGENTS.md) jest wejściem dla agentów pracujących w tym repozytorium. [guidefold-product-changes](../.agents/skills/guidefold-product-changes/SKILL.md) kieruje zmiany wymagań i kontraktów, a [guidefold-ui-workflow](../.agents/skills/guidefold-ui-workflow/SKILL.md) pracę nad U4 i pipeline’em.
Trzydzieści skilli reguł (kierunek produktu, zasady inżynierskie, jakość, konwencje, UI) jest zindeksowanych w AGENTS.md i wynika z [ADR-0032](adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md); Claude Code czyta je przez linki w `.claude/skills/`, a `.claude/settings.json` uruchamia hooki opisane w [.claude/README.md](../.claude/README.md). Skille projektu rozwijają reguły odczytu i wykonania, nie są drugim PRD. Dystrybuowany [bootstrap](../skills/guidefold/SKILL.md) służy repozytoriom klientów; nie dopisuj do niego wewnętrznych planów Guidefold ani nie zmieniaj skilli fixture w celu aktualizacji instrukcji projektu.
