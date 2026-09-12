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
| Import | Wejście przez login/org, komendy CLI, zakres wysyłki, manifest, postęp i błędy. |
| Library | Lista metadanych skilli; filtry repo, scope, owner, layer, status i zapytanie. |
| Map | Repository, Scopes, Pyramid; domyślnie drzewo/lista, ograniczone sąsiedztwo. |
| Skill | Tożsamość rewizji, zastosowanie, treść, źródła, wymagania i feedback. |
| Proposals | Kolejka i kandydat ze źródłem/diffem; przygotowanie decyzji, eksport i stan Git. |
| Usage & quality | Powody przeglądu, obserwacje, pokrycie i brak danych. |
| Organization | Members oraz Integrations: instalacja adaptera, diagnostyka, członkowie i tokeny. |
Login jest stanem wejścia i od 2026-09-12 ma własną trasę `/login` poza siedmioma widokami: każda trasa panelu jest prywatna, więc żądanie bez sesji trafia tam z celem powrotu w `?return=` i wraca pod pierwotny adres po zalogowaniu (odmowa 403 przy żywej sesji nie przekierowuje, tylko maskuje widok). Szczegół propozycji pozostaje częścią Proposals. Galeria komponentów jest narzędziem developerskim poza nawigacją produktu.
## 4. Nawigacja i kontekst
Kontekst org/repo jest widoczny przed importem i decyzją. Odmowa autoryzacji usuwa dane poprzedniego kontekstu.
Stały rail grupuje cele, a nie typy danych: Workspace (Import), Knowledge (Library, Map), Review (Proposals, Usage & quality) oraz Manage (Organization). Skill jest kontekstowym szczegółem otwieranym z Library, Map, Usage lub linku bezpośredniego, więc nie konkuruje z celami pierwszego poziomu.
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
| Organization | Org lub instalacja | Membership lub diagnostyka | Wykonaj konkretną operację wybranej zakładki. |
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
