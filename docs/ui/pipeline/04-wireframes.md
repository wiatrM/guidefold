# Makiety
Data: 2026-09-06. Wejścia: [brief](00-brief.md), [research](01-research.md), [persony](02-personas.md), [ankieta](03-survey.md), [pivot §3/7](../../PRODUCT-PIVOT.md), [IA §5 po przepisaniu](../IA.md); porównanie historycznej IA w briefie.
Artefakty: [siedem HTML](../../../prototypes/pipeline-wireframes/), czarno-białe, font systemowy, siatka 8 px; dane z examples/monorepo, podpis Meridian fixture.
## 1. Nawigacja
Import → Map → Skill; Library → Skill → źródło; Usage → Skill/Proposals; Proposals → źródło → decyzja → eksport → oczekiwanie Git → publikacja po sync.
Organization zawiera Members/Integrations; login i utworzenie org są stanami wejścia, nie dodatkowymi widokami. Link Skill nie zastępuje pozycji zaznaczonej w Library/Map.
[założenie] Stałe repo/scope i powrót z zachowanymi filtrami ograniczą utratę kontekstu (research R4). Obali to obserwowane błądzenie mimo tych informacji; do sprawdzenia z ludźmi.
## 2. Obiekt i działanie
| HTML / widok | Obiekt główny | Dowód | Jedna akcja główna |
|---|---|---|---|
| import.html / Import | Przebieg importu repo | Manifest, commit, pliki i błędy | Uruchom import po podglądzie do wskazanej org. |
| library.html / Library | Lista rewizji skilli | Źródło, scope, owner, status | Otwórz właściwy skill. |
| map.html / Map | Wybrany skill lub scope | Jawne relacje i źródła | Wybierz obiekt do sprawdzenia. |
| skill.html / Skill | Niezmienna rewizja | Treść, źródło, scope, zależności | Otwórz źródło. |
| proposals.html / Proposals | Kandydat do eksportu | Źródło obok kandydata, diff, scope | Zapisz decyzję; po akceptacji następny krok to eksport. |
| usage.html / Usage & quality | Obserwacja wymagająca decyzji | Rodzaj zdarzenia, rewizja i brak danych | Otwórz skill wskazany przez obserwację. |
| organization.html / Organization | Organizacja / instalacja | Membership albo wynik diagnostyki | Zakładka Members: zarządzaj dostępem; Integrations: sprawdź połączenie. |
## 3. URL
| Pole | Znaczenie |
|---|---|
| Ścieżka HTML | Jeden z siedmiu widoków; docelowe trasy hosted określi etap 7. |
| org, repo | Autoryzowany kontekst; URL nie nadaje uprawnień. Fixture: meridian/monorepo. |
| q, scope, owner, layer, status | Filtry Library; wracają ze szczegółu i zachowują się po reload. |
| revision | SHA-256 rewizji przy przejściu Published → Usage; przenoszony razem ze skill i scope (poprawka etapu 5). |
| skill | Zaznaczony skill jako URN; kandydat fixture jest związany z postgres-auth. |
| tab, from, return_tab | Zakładka lub oś Map oraz źródło wejścia i zakładka powrotu. |
| step | Stan wejścia Import: login, organization, preview, result. |
| role | Wyłącznie QA: owner lub member; scenariusz member ma odczyt i feedback, bez operacji ownera. Nie jest to kontrola API. |
| state | Wyłącznie wejście QA do sześciu stanów; brak przełącznika stanu w UI produktu. |
Po zmianie org/repo filtry i zaznaczenie spoza kontekstu są czyszczone. Sekrety i treść instrukcji nie trafiają do URL. Stan przygotowania/eksportu fixture jest lokalnym symulatorem, nie dowodem API.
## 4. Kompozycja
| Widok | Nad zgięciem 1280×720 | Kolejność czytania |
|---|---|---|
| Import | Org/repo, etap, instrukcja CLI i manifest | Kontekst → zakres wysyłki → akcja → wynik i pominięcia. |
| Library | Filtry, nagłówki i pierwsze wiersze | Kontekst → zapytanie → scope/status → obiekt. |
| Map | Oś, korzeń/lista i zaznaczenie | Kontekst → rodzaj relacji → obiekt → źródło. |
| Skill | Nazwa, scope, owner, rewizja i źródło | Tożsamość → zastosowanie → treść → wymagania. |
| Proposals | Scope, źródło i kandydat obok siebie, skok do decyzji | Powód → źródło/diff → skutki zakresu → decyzja → Git. |
| Usage | Rodzaj dowodu i brak obserwacji | Co wiadomo → czego nie wiadomo → obiekt do przeglądu. |
| Organization | Org, zakładka i konkretne działanie | Kontekst → członkostwo lub instalacja → wynik. |
Na 390 px panele źródło/kandydat przechodzą jeden pod drugim z nazwanymi nagłówkami; nie ukrywamy decyzji, treści ani widoków.
## 5. Sześć stanów
| Widok | Empty | Loading | Partial | Error | Degraded | Restricted |
|---|---|---|---|---|---|---|
| Import | Komendy i manifest do rozpoczęcia | Etap bez fałszywego procentu | Udane pliki i jawne pominięcia; bez publikacji | Przyczyna i retry | Wynik w pamięci; nowe zadania zablokowane | Bez manifestu; brak dostępu do org |
| Library | Brak importu albo brak dopasowania | Wiersze o docelowej geometrii | Zakres niekompletny i źródło ograniczenia | Błąd odczytu i retry | Odczyt ostatniej odpowiedzi z oznaczeniem | Bez nazw, treści i liczników org |
| Map | Brak obiektów | Miejsce listy, bez pustego grafu udającego wynik | Niepełny import lub nieklasyfikowane relacje opisane osobno | Nie udało się odczytać mapy | Tylko dostępna lista/sąsiedztwo | Bez węzłów org |
| Skill | Obiekt niedostępny w wybranej rewizji | Stały szkielet szczegółu | Źródło lub wymagany zasób niedostępne, bez ukrywania braku | Nie udało się odczytać rewizji | Treść z pamięci; feedback/zapis wyłączone | Bez body i metadanych |
| Proposals | Brak kandydatów | Bez aktywnych decyzji | Brak źródła lub digestu blokuje eksport | Decyzja nie została zapisana; bez pozornego sukcesu | Odczyt źródła; decyzje i eksport zablokowane | Bez propozycji; member ma oddzielny odczyt bez zapisu |
| Usage | No observations; nie 0% sukcesu | Bez wyników do chwili odpowiedzi | Pokrycie ograniczone; jawny mianownik | Brak raportu, nie wynik 0 | Ostatni dostępny raport z oznaczeniem | Bez zdarzeń i agregatów |
| Organization | Utworzenie org / brak instalacji | Bez aktywnych zmian membership | Część diagnostyki nieznana | Błąd logowania lub operacji | Diagnostyka/zmiany zablokowane | Brak dostępu; ponowne logowanie |
Restricted oznacza odmowę do org i czyści dane; member w uprawnionej org ma czytanie, ale brak operacji ownera. Awaria sieci nie potwierdza prawa do bezterminowego odczytu cache; docelowy kontrakt opisze etap 7.
## 6. Dane i publikacja
Generator fixture zachowuje 27 źródłowych skilli, 17 scope i commit 88e404561a9f6994cd870743bf858b9b0a616126. SHA każdej treści jest obliczona; Source status active nie znaczy Published w Guidefold.
Source layer team/platform/org pozostaje nazwą z fixture; Knowledge layer to Unclassified. Nie wymyślamy atomic/task/abstract ani zdarzeń użycia. Skill hierarchy-index ma scope _index poza mapą 17 scope; pokazujemy go jako Unmapped scope.
Edycja fixture obejmuje wyłącznie body; frontmatter, scope, owner i deklarowane relacje zostają stałe. Zmiany body pokazuje diff linii z kontekstem, pełne pliki są rozwijane.
Kandydat review wykorzystuje dokładną treść postgres-auth; No text changes jest prawdziwym wynikiem porównania. Export SKILL.md pobiera dokładny plik źródłowy, bez obietnicy pełnego pakietu zasobów; stan Published (fixture) wymaga jawnej symulacji Git sync, bez zapisu do repo.
Partial jest scenariuszem QA z tym samym subsetem 8/27 w Import, Library i Map oraz jawnymi dostarczonymi/pominiętymi ścieżkami. Scope instalacji: Unknown, ponieważ fixture nie zawiera konfiguracji adaptera.
Komendy nowego CLI są oznaczone Proposed CLI. Fixture nie ma rzeczywistych użytkowników ani członkostw; operator sesji jest rolą symulatora, nie wymyślonym pracownikiem.
## 7. Weryfikacja
Chromium: node prototypes/pipeline-wireframes/check.cjs — trzy ścieżki, 42 stany i sześć regresji po review; 0 błędów JS. pnpm z katalogu pipeline-tools: node audit-wireframes.mjs — 21 zrzutów (1280/820/390), 0 overflow i 0 naruszeń axe WCAG A/AA.
Dowody: [raport viewportów](../../../prototypes/pipeline-wireframes/qa/report.json), [przebieg Ownera](../../../prototypes/pipeline-wireframes/qa/owner-check.json). Export postgres-auth.SKILL.md: 5540 B, zgodne bajty i SHA.
Test agenta jest syntetyczny: nie mierzy 15 minut człowieka i nie zalicza U4 AC5 (co najmniej 4 z 5 prawdziwych osób). Test ACL fixture sprawdza kontrolki, nie bezpieczeństwo serwera.
## Przegląd
2026-09-08: Owner usunął tryb fixture z ui/ (wyłącznie hostowane API). Opisy fixture w §3–§7 pozostają zapisem makiet i symulatora z 2026-09-06; scenariusz Partial 8/27, edycja fixture, Published (fixture) i `?state=` nie istnieją już w ui/, gdzie sześć stanów pochodzi z odpowiedzi API (macierz w `ui/e2e/states.spec.ts` na stubie API).
R1: Owner + Projektant IA; P1=0/P2=5/P3=1 (unikalne). Poprawiono diff, edycję body, powrót do osi, partial, membera i scope instalacji; QA usunęło overflow/focus.
R2: Owner + Projektant IA; otwarte P1=0/P2=0/P3=0. Eksport zmienionego kandydata i mobilny diff sprawdzone w Chromium; etap zamknięty, 2026-09-06.
2026-09-07: Owner zgłosił nieczytelność Map i Usage & quality na żywym fixture; punktowa poprawka bez pełnego przebiegu pipeline'u — zwijanie łańcuchów katalogów w Repository, pasma Abstract/Task/Atomic/Unclassified w Pyramid, wcięcie/zwijanie Scopes, jeden panel powodu i rozdzielone Filters/Evidence na Usage, mocniejsze zaznaczenie w ScopeTree, dwa wykresy SVG w ApiUsageRoute tylko przy realnych danych; bez zmiany IA (te same siedem widoków, ten sam kontrakt URL).
2026-09-07 (druga poprawka): Owner zlecił przegląd wyświetlania telemetrii i ranking skilli. ApiUsageRoute po Needs review pokazuje lejek pięciu miar U6 (Exposed → Loaded → Context confirmed → Applied → Helped) z licznikiem, mianownikiem i definicją każdej miary; nowy panel Top skills (ranking wyłącznie po helped/(helped+hindered) przy ≥20 ocenach, AC3; poniżej progu liczby bez rangi; brak podziału per osoba) i By team (jeden wiersz na scope: owner, sumy, „needs attention” = exposed-never-loaded lub hindered). Poprawki błędów: opis „Cards returned by SEARCH” zastąpiony definicją ekspozycji adaptera; „Exposed but never loaded” tylko przy ekspozycjach > 0; feedback z UI bez zdarzeń adaptera liczy się jako obserwacja; okno jako lista 7d/30d/90d zamiast pola tekstowego; pokrycie feedbackiem nazwane tylko przy obecnych task_id; scope i owner w tabeli Per skill. Kontrakt API bez zmian (ranking i grupowanie liczone w UI z `Usage.skills`); `tools/telemetry/report.py` liczy `verified` jak Go. Wyniki shadow (E1.6, `gf.search_shadow`, `shadow-export`) pozostają narzędziem badawczym poza UI (ADR-0029).
