# Architektura informacji Guidefold
Status: hosted UI po pivocie; nawigacja i system komponentów zaktualizowane 2026-09-08. Reguły: [DOCUMENTATION-RULES](../DOCUMENTATION-RULES.md).
Zastępuje wersję 2026-09-04 z commitu 88e404561a9f6994cd870743bf858b9b0a616126. Różnice zapisano w [briefie](pipeline/00-brief.md); stare Routing/Eval nie wracają przez ten dokument.
## 1. Cel
Hosted UI pomaga znaleźć instrukcję ze źródłem i zakresem, przygotować propozycję do Git oraz rozpoznać potrzebę poprawki. Zakres: [PRODUCT-PIVOT §7](../PRODUCT-PIVOT.md).
Git jest kanonicznym źródłem zatwierdzonej treści. Guidefold zapisuje przygotowanie propozycji i eksport; publikacja wymaga właściwego obiegu Git, walidacji i sync. Eksport nie potwierdza publikacji ani załadowania.
## 2. Odbiorcy
| Zadanie | Wejście | Oczekiwany rezultat |
|---|---|---|
| Owner instrukcji | Proposals albo Usage po zmianie źródła/feedbacku; Import na początku | Decyzja oparta na źródle, treści i zakresie. |
| Developer | Library lub link Skill z repo/scope | Odczyt właściwej instrukcji i jej pochodzenia. |
| Platform jako zadanie ownera | Organization/Integrations; Skill/Usage | Rozróżnienie publikacji od potwierdzonego załadowania rewizji. |
To [założenia] z [person](pipeline/02-personas.md), z warunkami obalenia tamże; budżet15min nie jest wynikiem badania.
Persona nie nadaje uprawnień. Owner/member pochodzą z polityki organizacji; CODEOWNERS wskazuje odpowiedzialność za źródło, nie dostęp do Guidefold.
## 3. Widoki U4
| Widok | Zawartość |
|---|---|
| Overview (od 2026-09-12, `/home`, pierwszy ekran po zalogowaniu) | Cztery liczby z API (opublikowane skille, ekspozycje w oknie, udział helped, otwarte pozycje kolejki), „Your next actions” według roli, lejek dostawy (Spectrum `BarChart`), feedback i warstwy wiedzy (Spectrum `DonutPieChart`), karty liczb (Spectrum `StatCards`; od 2026-09-13, [raport](../reports/ui/overview-spectrum-20260913.md)), top skille z czterema bramkami i rekomendacją, biblioteka wg stanu/warstwy/scope, pipeline (ostatni import, propozycje wg stanu, adaptery), audyt dla ownera. Okno `?window=` wspólne z Usage. Od 1.3.0 plakietki trendu względem `usage.previous`. Od 2026-09-13 (ADR-0047) widok obejmuje całą organizację: bez `?repo=` liczby, lejek, top skille, propozycje i importy pochodzą z tras `{org_base}` (repozytoria dostępne dla czytającego), „Largest scopes” staje się „Largest repositories”, a selektor repozytorium w railu zawęża wszystkie widoki. Od 1.12.0 karta biblioteki w zakresie organizacji mówi, ile nazw skilli występuje w więcej niż jednym repozytorium, z linkiem do `library?duplicates=1`. |
| Import | Wejście przez login/org, komendy CLI, zakres wysyłki, manifest, postęp i błędy. |
| Library | Lista metadanych skilli całej organizacji (od 2026-09-13, ADR-0047); filtr repozytorium w railu (`?repo=`), filtry scope, owner, layer, status i zapytanie; wiersz niesie `repo_id`. Od 1.12.0 panel „Duplicated across repositories” nad listą: ta sama nazwa w kilku dostępnych repozytoriach, `Identical` albo `Differs`, linki do każdej kopii; `?duplicates=1` pokazuje pełną listę grup zamiast listy skilli. |
| Map | Repository, Scopes, Pyramid; domyślnie drzewo/lista, ograniczone sąsiedztwo. Bez wybranego repozytorium korzeń drzewa to lista repozytoriów (`kind: repository`), a wybór scope'u zawęża adres do jego repozytorium, bo identyfikator scope'u jest unikalny tylko w repozytorium (kontrakt §4.10). |
| Skill | Tożsamość rewizji, zastosowanie, treść, źródła, wymagania i feedback. |
| Proposals | Kolejka całej organizacji (od 2026-09-13) i kandydat ze źródłem/diffem; przygotowanie decyzji, eksport i stan Git zawsze w repozytorium propozycji (`repo_id` z wiersza). |
| Usage & quality | Powody przeglądu, obserwacje, pokrycie i brak danych w skali organizacji (od 2026-09-13); `?repo=` zawęża raport do jednego repozytorium, decyzja na pozycji kolejki idzie do jej `repo_id`. |
| Organization | Members, Integrations, Telemetry oraz Model keys: instalacja adaptera, diagnostyka, członkowie, tokeny, szybki obraz jakości wykonania i klucze dostawców modelu (ADR-0045) — jeden wiersz na dostawcę (openrouter, anthropic, openai), `last4` i data zapisu albo jawne „No key stored"; zapis/zamiana/usunięcie tylko dla ownera, member czyta bez edycji. |
| Live Agent (`/live`) | Composer (prompt, provider, model, zakres repozytoriów) i, po starcie, transkrypt obok listy stanu per repozytorium; sondowanie `GET …/live/runs/{id}/events` kursorem `after` mniej więcej raz na sekundę, zatrzymane wyłącznie przez `done` w odpowiedzi. Stany przebiegu (`queued/running/succeeded/partial/failed/cancelled`) czytane wprost; `partial` podaje liczbę repozytoriów, które zawiodły albo zostały pominięte. Start tylko dla ownera i tylko gdy organizacja ma zapisany klucz wybranego dostawcy — inaczej link do Model keys zamiast przycisku, który i tak by zawiódł; anulowanie również tylko dla ownera. |
Login jest stanem wejścia i od 2026-09-12 ma własną trasę `/login` poza dziewięcioma widokami (siedem U4, Overview i Live Agent): każda trasa panelu jest prywatna, więc żądanie bez sesji trafia tam z celem powrotu w `?return=` i wraca pod pierwotny adres po zalogowaniu (odmowa 403 przy żywej sesji nie przekierowuje, tylko maskuje widok). Szczegół propozycji pozostaje częścią Proposals. Galeria komponentów jest narzędziem developerskim poza nawigacją produktu.
## 4. Nawigacja i kontekst
Kontekst org/repo jest widoczny przed importem i decyzją. Odmowa autoryzacji usuwa dane poprzedniego kontekstu.
Stały rail grupuje cele, a nie typy danych: Workspace (Overview, Import, Live Agent), Knowledge (Library, Map), Review (Proposals, Usage & quality) oraz Manage (Organization). Skill jest kontekstowym szczegółem otwieranym z Library, Map, Usage lub linku bezpośredniego, więc nie konkuruje z celami pierwszego poziomu.
Rail składa się do paska ikon; etykiety znikają krótką animacją bez przesuwania treści strony. Na małym ekranie ten sam porządek otwiera modalny sheet. Profil i rola są w stopce raila; menu konta prowadzi do członkostwa organizacji i wywołuje istniejący logout. Historia edycji pozostaje historią rewizji w Skill/Proposals, bez ósmej trasy. Ulubione są działaniem na wierszu i w menu kontekstowym, nie nowym silosem nawigacji. Lista jest trwała w tej przeglądarce i izolowana kluczem użytkownik/organizacja/repozytorium; nie udaje preferencji zsynchronizowanej przez API.
URL koduje widok, filtry, zaznaczony obiekt i zakładkę; zamknięcie szczegółu lub powrót odtwarza listę/mapę. Kontrakty bieżących makiet: [etap4](pipeline/04-wireframes.md); docelowych tras: etap7.
Repo tree odpowiada na położenie źródła, scope na zastosowanie i odpowiedzialność, Pyramid na relacje wiedzy. Głębokość folderu nie nadaje warstwy atomic/task/abstract.
Każdy obiekt kompletnego importu jest osiągalny. Nieprzypisany scope i brak klasyfikacji są nazwanymi brakami, nie powodem ukrycia skilla.
Nie renderujemy całych10tys.węzłów. Graf przedstawia sąsiedztwo; tekstowa lista relacji umożliwia pełne wykonanie zadania klawiaturą.
## 5. Model ekranu
| Widok | Obiekt | Dowód | Główna akcja |
|---|---|---|---|
| Import | Przebieg importu | Manifest i wynik per źródło | Uruchom import po podglądzie. |
| Library | Lista rewizji | Źródło/scope/status | Otwórz skill. |
| Map | Wybrany obiekt | Jawne relacje | Sprawdź powiązany obiekt. |
| Skill | Rewizja | Treść i źródło | Otwórz źródło. |
| Proposals | Kandydat | Źródło obok diffu i zakres skutków | Zapisz decyzję; potem eksportuj. |
| Usage & quality | Obserwacja | Zdarzenie, rewizja, pokrycie | Otwórz instrukcję do przeglądu. |
| Organization | Org, instalacja lub klucz dostawcy | Membership, diagnostyka lub `last4`/data zapisu klucza | Wykonaj konkretną operację wybranej zakładki. |
| Live Agent | Przebieg (`LiveRun`) | Transkrypt i stan per repozytorium | Uruchom przebieg po sprawdzeniu klucza; obserwuj do zakończenia. |
## 6. Stany
Każdy widok ma empty, loading, partial, error, degraded i restricted; szczegółowa macierz to [etap4 §5](pipeline/04-wireframes.md).
Partial oznacza znany brak danych; loading oczekiwanie; error niepowodzenie; degraded ograniczone możliwości. Żaden z nich nie udaje sukcesu.
Restricted oznacza brak dostępu do danych org: bez body, nazw, liczników i poprzedniego cache. Member w uprawnionej org jest innym przypadkiem: może czytać, bez operacji ownera.
## 7. Dane i dowody
Rewizja treści, digest paczki, snapshot i commit są odrębnymi polami. Źródło ma link do właściwego hosta/pliku/commitu; nierozpoznany anchor jest nazwany, nie zamieniony w zmyślony numer linii.
Source status i Source layer pochodzą ze źródła. Stan publikacji Guidefold i klasyfikacja wiedzy nie wynikają z tych etykiet.
Pobranie, załadowanie i rezultat zadania są odrębnymi obserwacjami. Brak zdarzeń oznacza No observations/Unknown, nie skuteczność0%.
Treść wygenerowana jest oznaczona w miejscu odczytu. Decyzja o zakresie i brak dowodu wymagają jasnego komunikatu; nie samego koloru.
## 8. Utrzymanie
Kolejność makiet wynika z [ankiety](pipeline/03-survey.md); kolejność wdrażania z etapu7 i backlogu pivotu.
Dla zmiany ekranów czytaj kolejno ten dokument, [UX](UX.md), [UI](UI.md) i właściwy etap pipeline’u. Aktualizuj tylko zależne zakresy i dołącz dowód przeglądu.
Prawdziwy test U4 Q wymaga ≥4/5 osób niebędących autorami UI; syntetyczne persony i przeglądy agentów go nie zaliczają.
