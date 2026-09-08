# Backlog propozycji pivotu Guidefold

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument porządkuje zadania i zależności. Szczegółowe kryteria pozostają w PRD; ukończenie makiety nie oznacza ukończenia historii backendowej.

**Status: propozycja po recenzji pięciu ról, 2026-09-06.** Szczegóły wymagań i AC: [PRODUCT-PIVOT](PRODUCT-PIVOT.md). P01–P15 to lokalne ID, nie numery GitHub Issues. Obecne issue'y pozostają historycznym/operacyjnym backlogiem do aktualizacji po przyjęciu nowej decyzji. Ten dokument nie deklaruje wykonania nowych funkcji.

Każda historia ma wartość dla użytkownika, właściciela roli, zależności i dowód odbioru. Pełne AC są normatywne w podanej sekcji PRD; skróty w tabeli ich nie zastępują. Implementacja otrzymuje rzeczywisty numer issue po przełożeniu zatwierdzonej propozycji na GitHub.

| ID | Historia i wartość | Owner roli | Zależności | Dowód odbioru | Powiązanie istniejące |
|---|---|---|---|---|---|
| P01 | Google/GitHub login, org i owner/member: użytkownik może zacząć | Backend + frontend | Dostawca auth i konfiguracja OAuth | U3; oba logowania, zaproszenie, odwołanie dostępu | #71, #78, rozszerzenie #117 |
| P02 | Autoryzacja org/repo we wszystkich operacjach: dane organizacji pozostają izolowane | Backend | P01 | U3.3–5; A/B obejmuje API, worker, storage, eksport i metryki | #74, #97–98, rozszerzenie #117 |
| P03 | Scan, manifest i przyrost: owner wie, co podłącza i wysyła | CLI | Przykładowe repo partnera | U1; fixture, offline dry-run, rename, ignored files, zerowy przyrost | #71, #79–80 |
| P04 | Upload i joby z retry: duży import ma widoczny postęp i nie ginie | Backend | P02, P03 | U1/U2; restart, idempotencja, partial, limit kosztu | nowy zakres #117 |
| P05 | Biblioteka, źródła i mapa repo/scope: użytkownik odnajduje instrukcje | Frontend | P01, P04 | U4; realny import, filtry, 10k skilli, klawiatura | nowy zakres #117 |
| P06 | Ekstrakcja i enrichment: autor dostaje propozycje poparte źródłami | Backend + research | P04, źródła partnera | U2; provenance, błędy modelu, próbka 30, koszt | #72, #86; nowy zakres #117 |
| P07 | Review i eksport do Git: owner kontroluje treść przed publikacją | Frontend + CLI | P05, P06 | U2/U3; diff, reject, apply z kontrolą commitu, sync | #72, #85, rozszerzenie #117 |
| P08 | Konsolidacja i widok piramidy: wspólna wiedza ma źródła i zakres | Research + frontend | P06, P07 | U2/U4; pary powiązane/niepowiązane, brak cykli, decyzja ownera | #117; oddzielne od treningu #76 |
| P09 | Snapshot i pakiety: agent pobiera dokładnie zatwierdzoną treść | Backend | P02, P04; P07 tylko dla nowej wygenerowanej treści | U5; atomowa publikacja, rollback, references/scripts, budget/closure | #74, #99–100 |
| P10 | Instalator dwóch adapterów: developer korzysta w swoim narzędziu | CLI + integracje | P01, P09 | U5; Claude i Copilot na realnym repo, uninstall, token scopes | #71, #81–84 |
| P11 | UI użycia i zdrowie integracji: owner podejmuje decyzję na danych | Backend + frontend | P05, P10 | U6; ledger, unknown, retry, rewizje, export | #73, #91–95 |
| P12 | Raport zmian w CI: autor widzi regresje przed merge | CLI + CI | P03, P05, P09 | U7; deterministyczny diff, kontrolny PR, 10 realnych PR-ów | #72, #85, #87–90 |
| P13 | Drift i kolejka ownera: zmienione źródło nie pozostaje niezauważone | Backend + frontend | P04, P07, P11 | U9; zmiana/usunięcie, brak false deletion przy partial, audyt | #72–73 |
| P14 | Strona modułu i przykład wspólnej procedury: wiedza pomaga w prawdziwym zadaniu | Product + frontend | P05/P10 dla U8; P08/P09 dla U10 | U8/U10; scenariusze scope, 5 zadań, potwierdzenie ponownego użycia | #71, #75 |
| P15 | Eksport porównania i pilot: właściciel wie, czy dalej inwestować | Product + research | P10–11; partner od tygodnia 1 | U11 i §13 PRD; rubryka, oba kierunki regresji, decyzja | #75, #102–107 |

## Dwa poziomy dostarczenia

**Pilot Core:** ograniczone P01–P05, P09, jeden adapter z P10 i podstawowe P11, a także mały przykład P06–P08 spełniający obietnicę ekstrakcji/piramidy. Praca na 10–20 wybranych istniejących skillach w jednym module może dać pierwszy użytkowy przebieg przed masowym przetwarzaniem. P09 dla istniejących zatwierdzonych skilli nie czeka na P07. Wspólny scenariusz odbioru P05/P09/P10/P11 ma ID ACT-01: źródło → publikacja → load w prawdziwym zadaniu → feedback → decyzja ownera.

Pierwszy adapter prowadzi ACT-01; możliwości drugiego sprawdzamy technicznie w pierwszym etapie. Do 04.10 celem są 20 realnych sesji i działanie drugiego harnessa. Podstawowe P13 zamyka pętlę zmiany źródła. P15 definiuje rubrykę/buyera już od pierwszego tygodnia, nie dopiero na końcu.

**Kompletna beta:** pełne zachowanie błędów/retry, wygodne review i mapa, skala katalogu, drugi kompletny instalator, filtry i eksport. P12 używa istniejącego validate; P14 demonstruje U8/U10; P15 daje ręczny odtwarzalny raport U11. Nie dodajemy pięciu osobnych usług lub systemów.

**Zmiana zakresu P08, zapisana 2026-09-07 na polecenie właściciela (`scope-change-protocol`).** Właściciel wskazał P08 „konsolidacja i piramida" jako killer use case i zlecił wykonanie go end-to-end przed resztą kolejki. Zakres P08 obejmuje odtąd wprost: (a) grupowanie konsolidacji po scope **nadrzędnym** wraz z bezpośrednimi dziećmi, z ograniczeniem `max_neighbours` i jawnym powodem dla każdej odrzuconej pary; (b) wnioskowaną oś Wiedzy `knowledge_layer ∈ atomic|task|abstract` z `origin: inferred` i nadpisaniem przez właściciela (`human`); (c) addytywne `family` w kontrakcie 1.2 na kartach SEARCH i w USE; (d) `profile: one_shot` na planie i generowaniu; (e) komendę CLI `guidefold extract` wraz z jednym jobem CI. Zależność od P07 pozostaje: propozycja nadal wymaga decyzji właściciela, a `extract` niczego nie publikuje.

Warunek z „Zasad prowadzenia" obowiązuje bez wyjątku: **P08 nie zmienia produkcyjnego rankingu.** `family` jest doklejane po rankingu, po selekcji i po zmierzeniu `card_context`, żądanie 1.1 nie dostaje go w ogóle, a testy parity Go/CLI oraz `tests/test_run_golden.py`/`tests/test_bm25_reference.py` pozostają zielone bit w bit. Gdyby metadane piramidy miały kiedykolwiek wpływać na retrieval, wymaga to osobnej, ograniczonej i z góry opisanej ewaluacji na realnym korpusie — nie na fixture Meridian. Zaplantowany fixture (`examples/monorepo/docs/runbooks/README.md`) jest dowodem R dla reguły konsolidacji, nigdy dowodem recall.

**Odstępstwo od zakresu, zapisane 2026-09-07 (`scope-change-protocol`).** `guidefold report` powstał jako osobna komenda (~830 linii) zamiast rozszerzenia `validate --base <ref>`, i wyprzedził swoją pozycję w kolejce — P12 należy do *Kompletnej bety*, nie do Pilot Core. Powtarza kontrole cykli, brakujących zależności i brakujących zasobów, które mają już właścicieli w `check_cycles`/`check_urn_refs`/`validate`, i dokłada sekcję przykładów retrievalu, której nie wymaga żadne kryterium akceptacji P12. Zapis jest tu, bo niezależny przegląd (2026-09-07, ustalenie L8) słusznie wskazał to jako naruszenie YAGNI; złożenie tych kontroli z powrotem w `validate` to osobna praca refaktoryzacyjna, nie poprawka przeglądowa, i nie jest wykonywana w tej zmianie.

R = kryterium techniczne wydania danego zakresu, Q = bramka jakości, P = dowód z pilota. Liczba realnych PR-ów, cztery tygodnie używania i deklaracja płatności nie blokują startu testu użytkowego, bo są jego wynikiem. Terminy i definicje z §13 PRD są nadrzędne dla tej propozycji.

## Zasady prowadzenia

- Nowe feature'y nie otrzymują statusu done przez sam test fixture. Wymagany jest dowód użytkowy wskazany w historii.
- P02 jest warunkiem przyjęcia danych więcej niż jednej organizacji; żadna ścieżka administracyjna nie omija izolacji.
- P03–P05 dają pierwszą wartość niezależnie od jakości modelu. Przy awarii generowania import istniejących skilli pozostaje dostępny.
- P06–P08 nie zmieniają produkcyjnego rankingu. Jeżeli wzbogacone pola mają wpływać na retrieval, potrzebna jest osobna, ograniczona i z góry opisana ewaluacja.
- P14 i P15 wykorzystują wspólne komponenty, zamiast dodawać oddzielny portal onboardingowy lub platformę benchmarkową.
- Zgłoszenia krytycznych problemów auth, utraty danych, błędnej publikacji i niezgodności rewizji mają pierwszeństwo przed rozszerzeniami UI.
- Każda historia przed implementacją określa obsługiwane środowiska, próbkę odbioru oraz miejsce zapisu wyniku. Szacunki aktualizujemy po pierwszym etapie.


## Podział techniczny

React/Vite + Go API + osobny worker. Przypisanie historii do modułów i kontrakty procesu opisuje [PIVOT-ARCHITECTURE](PIVOT-ARCHITECTURE.md). Use case nie wyznacza mikroserwisu. P02, P09 i zaufany builder są wczesnymi bramkami technicznymi. Uwagi agentów i rozstrzygnięcia: [PIVOT-REVIEW](PIVOT-REVIEW.md).
