# Guidefold: od monorepo do sprawdzonej biblioteki skilli

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument określa wymagania i AC. Decyzje ekranów rozwija pipeline UI; nie zmienia on zakresu bez jawnej aktualizacji PRD.

**Status: propozycja nowego MVP po przeglądzie agentów, 2026-09-06.** Wymagania właściciela rozszerzają wcześniejszy freeze o hosted UI, logowanie, organizacje, import i konsolidację wiedzy. Dokument opisuje docelowe zachowanie, nie stan implementacji. Decyzja: [ADR-0031](adr/ADR-0031-monorepo-to-managed-skill-library.md). Historie: [backlog pivotu](PIVOT-BACKLOG.md). [Ocena pięciu ról](PIVOT-REVIEW.md) i [React/Go/NestJS oraz podział usług](PIVOT-ARCHITECTURE.md).

## 1. Pivot i obietnica produktu

**Guidefold zamienia rozproszoną wiedzę z repozytoriów firmy w wersjonowaną bibliotekę skilli, dostarcza właściwe instrukcje agentom i pokazuje właścicielom, co wymaga poprawy.**

Pierwszy klient to platform team albo tech lead zarządzający monorepo i kilkoma narzędziami agentowymi. Użytkownikami są autorzy instrukcji i developerzy. Pierwsze wdrożenie obejmuje jedno prawdziwe repo, odpowiedzialnego ownera i dwa wspierane harnessy. Model danych dopuszcza wiele repozytoriów w organizacji.

Obietnica demonstracyjna: **„Podłącz repo, zobacz jego wiedzę i braki, zatwierdź instrukcje, udostępnij je agentom i sprawdź, czy pomagają.”** Pierwszą wartością jest mapa wiedzy i jej źródeł. Powód powrotu ma wynikać z używania instrukcji, zmian autorów i decyzji ownerów.

Dense i sparse pozostają wymiennymi metodami wyszukiwania. Domyślnie wykorzystujemy istniejący BM25F. Jakość nadal ma znaczenie, lecz własny model i wygrany benchmark nie są warunkiem wydania. Enrichment wpływa na ranking dopiero po osobnym porównaniu jakości.

Sam portal, drzewo i licznik pobrań nie stanowią wystarczającej przewagi. Aktualne Claude Code obsługuje zagnieżdżone skille i narzędzia ich oceny. Hipotezą wyróżnika jest połączenie pochodzenia wiedzy, przeglądu zmian i spójnego dostarczania oraz pomiaru przez różne harnessy. To hipoteza do sprawdzenia z klientem. [Claude Code Skills](https://code.claude.com/docs/en/skills)

### Odbiorca, aktywacja i kryteria

Championem pilota jest platform/DevEx lead; potencjalnym płatnikiem właściciel budżetu narzędzi developerskich. To role do potwierdzenia w rozmowie. Partner musi mieć powracający problem z instrukcjami, dwa używane harnessy, ownera z czasem na review i dopuszczony zakres danych do przetwarzania w chmurze. Wymaganie SSO lub podziału dostępu wewnątrz org wyklucza ten wariant pilota albo wymaga wydzielonego, zatwierdzonego zakresu.

Aktywacja ownera: import realnego repo, publikacja poprawnego skilla i zrozumiałe źródło/scope. Aktywacja zespołu: niezależny developer wykonuje rzeczywiste zadanie z potwierdzonym załadowaniem instrukcji i oceną rezultatu. Mapa jest pierwszym widocznym efektem, ale dopiero druga aktywacja sprawdza dostarczanie wiedzy.

Powód powrotu: zmiana źródła lub negatywny feedback → zadanie ownera → poprawka w Git → nowa rewizja dla agentów. Mierzymy również czas utrzymania biblioteki, zamiast liczyć wyłącznie nowe skille.

W całym dokumencie **R (Release AC)** oznacza test techniczny przed wydaniem danego zakresu; **Q (Quality Gate)** ocenę jakości na wskazanej próbce; **P (Pilot Evidence)** dowód wartości zbierany podczas używania. Nieoznaczone AC są R. Dowody P nie są warunkiem rozpoczęcia pilota. Progi są propozycją do zamrożenia przed pomiarem.

## 2. Import i trzy osie piramidy

Skan obejmuje istniejące SKILL.md oraz instrukcje, dokumentację i runbooki, z których można zaproponować nowe skille. Przegląd całego drzewa nie oznacza wysłania całego kodu. CLI lokalnie wybiera źródła i buduje manifest; serwer po uploadzie parsuje, ekstrahuje, wzbogaca i proponuje konsolidację.

| Oś | Przykład | Pytanie |
|---|---|---|
| Źródło | repo → payments → runbooks/refunds.md | Skąd pochodzi instrukcja? |
| Zakres i owner | organizacja → produkt → komponent | Gdzie obowiązuje i kto ją ocenia? |
| Wiedza | wzorzec abstrakcyjny → procedura → operacja atomowa | Co specjalizuje lub wykorzystuje inny skill? |

Warstwa atomic/task/abstract nie wynika z głębokości katalogu. Podobieństwo nie tworzy zależności requires. CODEOWNERS nie jest systemem autoryzacji. Jeden skill może pasować do kilku modułów; rozszerzenie zakresu wymaga jawnej decyzji.

**Co wnosi SkillPyramid:** metoda zaczyna od istniejących skilli, grupuje je, wydziela wspólne operacje i tworzy nadrzędne schematy z zależnościami. Autorzy nie trenowali parametrów modeli. Badanie dotyczy ALFWorld, WebShop, ScienceWorld i małego GAIA-Lite, nie monorepo. Nagłówkowe +38% reward i −27,7% kroków porównuje z ReAct bez skilli. Wobec płaskiej biblioteki ReAct+Skills reward wynosi 73,7 zamiast 65,8, a liczba kroków 14,6 zamiast 17,7. Pojedynczy deterministyczny przebieg ogranicza uogólnienie. [Publikacja v1](https://arxiv.org/html/2606.03692v1)

Nasza adaptacja obejmuje propozycje wspólnych operacji, specjalizacji i nadrzędnych procedur. Nie obiecujemy samoczynnego poprawiania wiedzy. Brak popartej źródłami wspólnej procedury może prawidłowo zakończyć się brakiem propozycji.

## 3. Źródło prawdy i publikacja

Git pozostaje źródłem zatwierdzonych instrukcji. Guidefold przechowuje kopie wejść, metadane, graf, propozycje, snapshoty i telemetrię. Enrichment nie nadpisuje oryginalnego SKILL.md.

| Treść | Po imporcie | Wejście do produkcyjnego SEARCH/USE |
|---|---|---|
| Istniejący skill z commitu | Importowana rewizja i lista problemów | Owner potwierdza publikację; walidacja i atomowa aktywacja |
| Skill wydobyty z dokumentacji | Kandydat ze wskazaniem źródeł | Przygotowanie w UI → eksport plików/patcha → review i merge Git → sync według polityki publikacji |
| Wspólny lub abstrakcyjny skill | Propozycja z rewizjami źródeł i diffem | Ta sama ścieżka; bez automatycznego usuwania procedur źródłowych |
| Wygenerowane metadane | Osobna nakładka, oznaczenie pochodzenia | Akceptacja i walidacja; ranking wymaga osobnej bramki jakości |

UI rozróżnia draft, approved_for_export, awaiting_git, published, needs_review i archived. To proponowany uproszczony cykl MVP zamiast pełnego G0–G7. Akceptacja treści nie dowodzi jej skuteczności. Nieudany import nie zmienia aktywnego snapshotu.

UI służy do przygotowania propozycji; review w Git zatwierdza tekst. Powiązanie obejmuje proposal_id, bazę, digest treści, zasobów, scope i zależności. Niezmieniony pakiet nie wymaga drugiego pełnego review UI. Sync zamyka propozycję po publikacji; zmieniony digest pokazuje różnice i wymaga świadomej decyzji ownera. Bez integracji GitHub App serwer nie weryfikuje ochrony gałęzi ani review hosta: zapisuje deklarację uprawnionego operatora z commitem, a UI określa poziom dowodu. Późniejsza integracja może dostarczyć zweryfikowany stan merge.

MVP eksportuje propozycje lokalnie, bez wymagania GitHub App. Projektowana komenda `guidefold proposals apply` pokazuje diff, sprawdza bazowy commit i na polecenie operatora zapisuje wskazane pliki. Nie robi commitu/pusha. Automatyczne otwarcie PR jest późniejszą integracją. Serwer nie wykonuje kodu importowanych pakietów.

## 4. U1 — skan i synchronizacja monorepo

**Aktor i efekt:** owner podłącza repo bez ręcznego tworzenia katalogu skilli.

Wymagania:

- Skan wskazanego commitu, zagnieżdżonych katalogów skilli, AGENTS.md, CLAUDE.md, .github/instructions, README, ADR i wybranych runbooków. MVP obsługuje Markdown/YAML/JSON; inne formaty wykazuje jako pominięte.
- guidefold.yaml ma pierwszeństwo w mapowaniu scope. Katalogi i CODEOWNERS dostarczają propozycji, jeśli mapy brak. Niepewna hierarchia/owner są widoczne i nie stają się samoczynnie polityką.
- .gitignore, .guidefoldignore, lista dozwolonych źródeł, limity paczki; pomijanie sekretów, .git, zależności i buildów. Symlinki nie wyprowadzają poza root; submodule jest osobnym jawnym źródłem.
- Manifest: org, repo, commit, pliki, hashe, rozmiary i wykluczenia. Domyślny profil publikacji obejmuje commit; lokalne zmiany mają osobny podgląd bez publikacji.
- Sync po hashach, wznowienie uploadu, idempotencja. Usunięcia wymagają kompletnego skanu; częściowy skan nie może ich wywnioskować.

Acceptance criteria:

1. `scan --dry-run` nie wykonuje połączeń sieciowych. Paczka odpowiada pokazanemu manifestowi.
2. Fixture z 5 zagnieżdżonymi scope'ami wykrywa wszystkie obsługiwane źródła i jawne relacje. Przypadki niejednoznaczne mają listę przyczyn.
3. .env, ignorowany katalog i symlink poza root nie ujawniają zawartości w paczce.
4. Ten sam commit daje ten sam manifest treści; drugi sync przesyła 0 nowych blobów.
5. Przerwanie i retry daje jeden import. Rename zachowuje tożsamość przez jawne mapowanie/alias albo trafia do review.
6. R dla pierwszego pilota: do 10 tys. ścieżek, 200 istniejących skilli i 20 MiB wybranych źródeł; skan w p95 do 10 s i maks. 512 MiB RSS na 2 vCPU/8 GiB RAM/SSD (Linux lub WSL), 20 prób, z zapisanym cache state. Progi dotyczą skanu, nie generowania LLM. Szerszy raport 100 tys. ścieżek/10 tys. skilli mierzy granice i nie jest automatycznym zaliczeniem. Limit paczki bety: 100 MiB; bez ukrytego obcięcia.
7. Formaty do ekstrakcji są oddzielone od zasobów pakietu skilla. Manifest zasobów obejmuje ścieżkę, hash, rozmiar, typ i required/optional, również scripts i references. Niedopuszczony wymagany zasób blokuje publikację; nie znika po cichu.

## 5. U2 — ekstrakcja, enrichment i konsolidacja

**Aktor i efekt:** autor otrzymuje proponowane instrukcje i relacje z dowodami.

Pipeline: uploaded → parsing → extracting → enriching → proposing → ready/partial/failed. Stan publikacji jest osobny. Istniejące skille widać po parsowaniu, bez czekania na LLM.

Wymagania:

- Parsowanie zachowuje oryginał. Kandydat zawiera cel, kiedy użyć/nie używać, warunki, kroki, zasoby, weryfikację, ownera i scope.
- Enrichment dodaje tematy, technologie, streszczenie, triggery, negatywne triggery i przykładowe zapytania. Każda wartość ma pochodzenie source/parsed/inferred/human i może zostać odrzucona. Wygenerowane zapytania nie są niezależnym testem.
- Relacje derived_from, requires, refines, similar i conflicts_with mają odrębną semantykę. Scope, layer i owner są oddzielnymi polami.
- Każdy wygenerowany krok ma konkretny fragment źródła i rewizję albo „wymaga potwierdzenia”. Zgodność znaczenia z cytowanym źródłem podlega ludzkiej ocenie próbki.
- Wspólny element wymaga co najmniej dwóch procedur. Podniesienie scope wymaga co najmniej dwóch źródłowych scope'ów i akceptacji ownera zakresu docelowego.
- Joby mają retry, lease, cache po hashu wejść/modelu/recepty i limit kosztu. Maksymalnie 5 propozycji na grupę oraz 5 wybranych propozycji na repo w jednej sesji review pilota. Nie uruchamiamy kolejnej paczki bez decyzji ownera. Plan joba ogranicza także pliki, bajty, tokeny, liczbę grup, sąsiadów, wywołań i łączny wydatek; nie wykonuje porównań wszystkich par katalogu. Przed startem widoczne są limity pracy i kosztu.
- Review pokazuje źródła, diff, akceptację do eksportu, poprawkę i odrzucenie z powodem. Odrzucona propozycja nie wraca przy niezmienionym wejściu/recepcie.

Acceptance criteria:

1. Błąd jednego pliku jest widoczny per plik; poprawne pozostają dostępne. Import partial nie aktywuje po cichu niepełnej publikacji.
2. Każdy kandydat ma pochodzenie źródła i generowania. Wadliwy JSON jest odrzucony lub poprawiany w ograniczonym retry; nie omija walidacji.
3. Restart nie dubluje kandydatów. Każda próba workera ma fencing token; spóźniona próba nie nadpisuje nowej. Deduplikacja obejmuje org, wejścia, model i receptę. Niepewny koszt/rezultat wywołania modelu jest jawny; powtórki nie są traktowane jako bezpłatne.
4. Q: 30 propozycji wybranych przed oceną, z różnych źródeł/scope'ów i trudności. Co najmniej 24 przyjmowalne bez zmiany znaczenia to próg wstępnej selekcji recepty, nie dowód 80% jakości w populacji. Każdy krytyczny błąd ogranicza receptę. Osobno oceniamy ekstrakcję, enrichment, konsolidację i poprawną odmowę generowania; zapisujemy czas review oraz poprawki znaczenia.
5. Pozytywny fixture ma uprzednio oznaczony wspólny element w dwóch runbookach. Przypadki podobne językowo, lecz o innych warunkach/wersjach, sprzeczne i bez dowodów wymagają poprawnego powstrzymania się od konsolidacji. Mierzymy osobno trafność, wykrycie wspólnych elementów i odmowę; nie samą liczbę propozycji.
6. Draft nie pojawia się w SEARCH/USE. Cykle requires/refines i brakujące wymagane zależności blokują publikację; poprzedni snapshot działa. Similar/conflicts_with mogą być symetryczne i nie podlegają tej samej regule cykli. Test obejmuje diament, współdzielony atom, specjalizację i błędne poszerzenie scope; wielość źródłowych scope nie dowodzi generalizacji.
7. Limit kosztu zatrzymuje nowe wywołania i zachowuje postęp. Brak skonfigurowanego LLM nie blokuje importu istniejących skilli.

**Decyzja właściciela, 2026-09-07 (P08 „konsolidacja i piramida" jako killer use case).** Zapisane zgodnie z `scope-change-protocol`; dotychczasowy tekst i AC 1–7 pozostają bez zmian, poniższe je uzupełnia.

- **Konsolidacja szuka między rodzeństwem, nie w jednym scope.** Wspólna procedura prawie nigdy nie leży dwa razy w tym samym scope; leży raz w `atlas.geo` i raz w `atlas.graph`. Grupa konsolidacji to odtąd scope nadrzędny wraz z jego bezpośrednimi dziećmi, każdy skill w dokładnie jednej grupie, wielkość grupy ograniczona przez `max_neighbours`. To nadal nie jest przebieg all-pairs po katalogu. Wspólny element powstaje w najgłębszym wspólnym przodku źródeł, z `derived_from` do każdego źródła i proponowanym `refines` z każdego źródła w górę do niego. Reguła podniesienia scope nie zmienia się: ≥2 różne scope'y źródłowe i owner scope'u docelowego jako owner propozycji.
- **Oś Wiedzy jest wnioskowana, nie zgadywana.** Enrichment i konsolidacja wystawiają `knowledge_layer ∈ atomic|task|abstract` jako osobne pole z `origin: inferred`, wskazaniem linii źródła i jawną tablicą reguł recepty `det-1` (API-CONTRACT §5.3). Właściciel może je nadpisać przy zatwierdzeniu; pole przechodzi wtedy na `origin: human`. Warstwa nigdy nie wynika z głębokości katalogu ani z `source_layer`.
- **Powstrzymanie się nadal ma powód.** Każda odrzucona para ma nazwany powód w wyniku joba; milczące pominięcie pary jest błędem, tak samo jak zgadnięcie konsolidacji. AC5 mierzy to odtąd na zaplantowanym fixture (`examples/monorepo/docs/runbooks/README.md`, znacznik „Meridian fixture, planted for U2 AC5"): jedna para o identycznej procedurze w dwóch scope'ach rodzeństwa i jeden podobny językowo runbook o innych warunkach/wersjach, który musi zostać odrzucony z powodem. Fixture jest dowodem R (zachowanie reguły), nigdy dowodem recall na realnym repozytorium.
- **Jedno wywołanie może objąć cały import.** `profile: one_shot` na planie i na generowaniu podnosi wyłącznie `max_groups` do liczby znalezionych grup; `max_usd`, `max_calls` i pozostałe limity pozostają ceilingiem wdrożenia i nadal zatrzymują przebieg. Plan pokazuje pełny koszt i wszystkie limity przed startem (AC7 bez zmian), a job checkpointuje po każdej grupie, więc przerwany przebieg wznawia się bez duplikatów (AC3 bez zmian).

## 6. U3 — logowanie i organizacje

**Wybór: WorkOS AuthKit, Google/GitHub i hostowana domena.** AuthKit obecnie jest bezpłatny do 1 mln MAU. Własna domena auth kosztuje 99 USD/mies.; enterprise SSO od 125 USD/połączenie/mies. Te dodatki są poza MVP. Produkcja może wymagać karty. Darmowe auth nie oznacza darmowego hostingu lub LLM. [Cennik](https://workos.com/pricing)

WorkOS udostępnia [social login](https://workos.com/docs/authkit/social-login), [SDK Go](https://workos.com/docs/sdks/go) i [device flow CLI](https://workos.com/docs/authkit/cli-auth). Go obsługuje callback i sesję UI, bez dodatkowego serwera Node do auth. Wewnętrzne org_id, membership i reguły dostępu pozostają w Postgres Guidefolda.

| Alternatywa | Decyzja |
|---|---|
| [Better Auth](https://github.com/better-auth/better-auth) | Fallback przy wymogu self-host: MIT, ale dodatkowy runtime TS/Node i utrzymanie |
| [Clerk](https://clerk.com/pricing) | Gotowe UI; Hobby obecnie 50 tys. MRU, 100 MRO i do 20 członków/org według definicji dostawcy |
| [Supabase](https://supabase.com/pricing) | Warto wykorzystać istniejący płatny projekt; Free 50 tys. MAU, 2 aktywne projekty, usypianie po tygodniu; Pro od 25 USD/mies. |

MVP: owner/member. Owner importuje, publikuje, zaprasza i usuwa członków; member przegląda, używa i zgłasza feedback. Wszyscy członkowie mają dostęp do dopuszczonych repo swojej org. Dane wymagające podziału dostępu wewnątrz org czekają na granularne ACL. Role własne, SSO i SCIM są później; izolacja org jest obowiązkowa teraz.

Acceptance criteria:

1. Google i GitHub działają end-to-end. Pierwsze logowanie prowadzi do utworzenia org, kolejne do tego samego konta. Łączenie tożsamości wymaga potwierdzenia; sam równy e-mail nie wystarcza.
2. UI umożliwia tworzenie/przełączanie org i zaproszenie/usunięcie member. Ostatni owner jest chroniony przed przypadkowym usunięciem.
3. Backend autoryzuje import, job, blob, eksport, skill, graf, SEARCH/USE i raport. Podmiana ID org A na B nie ujawnia treści, metadanych ani liczników.
4. Usunięcie członka/unieważnienie tokenu blokuje zdalny dostęp w maks. 60 s, mimo aktywnej sesji dostawcy. Sprawdzamy także cache UI.
5. Cookies HttpOnly/Secure, ochrona CSRF, brak tokenów w repo/URL/logach. Org jest widoczna przed importem. Login GitHub nie wymaga dostępu OAuth do kodu repo.

## 7. U4 — UI biblioteki i piramidy

UI jest częścią definicji wydania. React/Vite obecnego prototypu jest punktem wyjścia, nie gotową aplikacją. Po rejestracji użytkownik widzi ścieżkę pierwszego importu.

| Widok | Główne działanie |
|---|---|
| Start / Import | Skopiuj komendy, zobacz postęp i błędy |
| Biblioteka | Szukaj po repo, scope, ownerze, warstwie i statusie |
| Mapa | Przełącz Repozytorium / Zakresy / Piramida i poznaj relacje |
| Skill | Przeczytaj treść, źródła, rewizję, wymagania i feedback |
| Propozycje | Porównaj źródła/diff, podejmij decyzję, eksportuj patch |
| Użycie i jakość | Przejrzyj obserwacje, brak danych i zadania ownera |
| Integracje / Organizacja | Zainstaluj adapter, sprawdź połączenie, zarządzaj członkami/tokenami |

Cała piramida jest osiągalna przez rozwijanie i filtry. Nie renderujemy 10 tys. węzłów jednocześnie: domyślnie drzewo/lista, graf jako sąsiedztwo wskazanego skilla. Źródła i zależności mają różne etykiety; kolor nie jest jedyną informacją. Draft i published zawsze są rozróżnione.

Acceptance criteria:

1. Każdy skill kompletnego importu jest osiągalny przez mapę/listę ze źródłem i zakresem. Powrót ze szczegółu zachowuje filtry.
2. Pierwsza strona katalogu 10 tys. skilli: p95 do 2 s w zadeklarowanym środowisku pilota i rzeczywistej sieci. Lazy loading nie pobiera całych body.
3. Review pokazuje propozycję i źródło obok siebie; link Git trafia do właściwego hosta, pliku i commitu.
4. Login, import, lista i review działają z klawiatury, mają focus, etykiety formularzy i czytelne błędy; graf ma alternatywę tekstową.
5. Q: co najmniej 4 z 5 osób niebędących autorami UI kończą import, znajdują źródło i przechodzą propozycja → Git → opublikowana rewizja bez pomocy. Rejestrujemy czas i tarcia, nie tylko ocenę ekranu.

## 8. U5 — instalacja w harnessie i API

**Aktor i efekt:** developer instaluje pakiet Guidefold; agent znajduje i pobiera firmowe instrukcje.

Projektowany UX CLI (nowe komendy nie są jeszcze implementacją):

```text
guidefold login
guidefold org use acme
guidefold scan . --dry-run
guidefold import .
guidefold sync .
guidefold install --harness claude
guidefold install --harness copilot
guidefold doctor
```

Przenośny pakiet to SKILL.md z instrukcją find → load → feedback oraz wersjonowany skrypt API. Native plugin opakowuje ten sam klient tam, gdzie to wspierane. **Bramka MVP: realne sesje Claude Code i Copilot CLI**, zgodnie z wcześniejszym backlogiem. Codex/Gemini są następnymi adapterami; nie zakładamy identycznych hooków ani obserwacji. Format i wersje potwierdzamy przy implementacji.

Pobranie pliku i weryfikacja checksum to download_verified. Załadowanie do kontekstu wymaga oddzielnego potwierdzenia adaptera (context_loaded); jeżeli harness go nie dostarcza, wynik pozostaje unknown. Ani pobranie, ani emisja tekstu nie dowodzi zastosowania instrukcji przez model.

SEARCH wybiera opublikowane karty dla zadania/repo/scope. USE pobiera dokładną rewizję i wymagane zasoby, bez wykonywania skryptów. Nowe gwarancje wymagają rozszerzenia kontraktu projektowanego jako 1.2: pełne requires w obrębie snapshotu, limity traversal, załadowane zależności i budżety kart/body/zasobów. Zależności mieszczą się w budżecie albo wynik to cannot_fit/unresolved. Domyślny limit pozostaje czterema kartami. Klient 1.1 nadal ma dotychczasową semantykę i nie otrzymuje obietnicy kompletności. Łańcuch głębszy niż dwa, ponad cztery karty, diamond i odmowa dostępu są obowiązkowymi testami. Zmiana snapshotu między SEARCH a USE może dać jawny 409 i powtórny SEARCH; nigdy mieszaninę rewizji.

Acceptance criteria:

1. Instalator jest idempotentny, pokazuje zmiany, zachowuje cudzą konfigurację i ma uninstall. Pakiet ma wersję/checksum; doctor sprawdza org/repo, auth, API i możliwości adaptera.
2. Device login działa lokalnie i w terminalu zdalnym; obsługuje odmowę/timeout bez sekretu klienta OAuth. Poświadczenia są poza repo w magazynie OS lub chronionym pliku.
3. Token instalacji ma org/repo i search/use/events; nie ma import/publish/membership. CI używa oddzielnego tokenu o minimalnych uprawnieniach.
4. Oba harnessy w rzeczywistych sesjach robią SEARCH → USE → potwierdzone przez klienta załadowanie rewizji; UI pokazuje te same identyfikatory zdarzeń.
5. USE ponownie sprawdza dostęp, także do zależności/zasobów. References/scripts zachowują względne ścieżki. Brak wymaganego zasobu jest błędem; archiwum nie zapisuje poza cache.
6. Awaria API daje błąd lub jawny lokalny profil o określonych uprawnieniach. Prywatna zawartość cache nie daje nieograniczonej autoryzacji offline. Cofnięcie dostępu nie wymazuje instrukcji już wczytanych do kontekstu agenta.
7. Cele dla adaptera z potwierdzoną obsługą hooka: świeży klient hooka kończy wybór wyniku/fallback w 400 ms p95; interaktywny SEARCH w 1 s p95. Pomiar: minimum 200 prób c1/c4, wskazany korpus, realna sieć, błędy i fallback w raporcie. Loopback nie staje się SLA.

**Decyzja właściciela, 2026-09-07 (P08).** Zapisane zgodnie z `scope-change-protocol`; AC 1–7 powyżej pozostają bez zmian.

- **Karta mówi, czy istnieje wersja dla mojego scope'u.** Kontrakt 1.2 dostaje addytywne `family` na każdej karcie SEARCH i w odpowiedzi USE: rodzic, którego karta uszczegóławia, dzieci, które uszczegóławiają ją, oraz warstwa wiedzy każdego z nich. Wyliczane z zatwierdzonych krawędzi `refines`, głębokość jeden skok, najwyżej ośmioro dzieci. `family` jest wskazówką nawigacyjną, nie deklaracją kompletności, i nie zastępuje `closure`.
- **To nie jest zmiana rankingu.** `family` powstaje po rankingu, po selekcji i po zmierzeniu `card_context`; kolejność `ranked`/`cards` i rozliczenie budżetu są identyczne z nim i bez niego, a żądanie 1.1 nie dostaje tego pola w ogóle. Wpływ metadanych piramidy na retrieval wymagałby osobnej, z góry opisanej ewaluacji (PIVOT-BACKLOG, „Zasady prowadzenia", P06–P08).
- **Token CI dostaje `import` i `generate`.** `guidefold extract --all` w CI musi zaimportować drzewo i zlecić propozycje, więc zakresy tokenu CI to podzbiór `validate import generate`. Zakresy tokenu instalacji z AC3 **nie zmieniają się**: adapter nadal dostaje wyłącznie `search`/`use`/`events`. Token CI nadal nie publikuje i nie zmienia membership.
- **Katalogi osobistych skilli są prywatną treścią.** `guidefold extract --personal` jest jedyną drogą, którą treść spoza drzewa git opuszcza maszynę; domyślnie wyłączona, `--dry-run` pokazuje dokładnie ścieżki, rozmiary i sha256 bez otwierania gniazda, CI nigdy tej flagi nie używa, a pliki trafiają do manifestu z `source: {kind: personal, harness}` i prefiksem `_personal/<harness>/`.

## 9. U6 — telemetria i użyteczność

Rozwijamy [kontrakt zdarzeń](SEARCH-USE-TELEMETRY.md). Pierwszym widokiem jest kolejka „Wymaga przeglądu” z przyczyną i akcją: sprawdzono, poprawiono w Git, brak zmiany z uzasadnieniem. Wykresy są podsumowaniem dalszej części ekranu. Owner ma rozpoznać skille niewidoczne, pobierane, oceniane jako pomocne, problematyczne i wymagające przeglądu. Nie budujemy rankingu pracowników.

| Miara | Definicja |
|---|---|
| Ekspozycje | Unikalne zdarzenia dostarczenia karty przez adapter; odpowiedź serwera nie wystarcza |
| Załadowania | Unikalne udane load_id z osobnym potwierdzeniem context_loaded; download_verified i brak potwierdzenia pokazane oddzielnie |
| Zastosowanie | Reported i observed osobno; wspólne epizody deduplikowane |
| Ocena pomocy | helped / (helped + hindered), zgodnie z istniejącym kontraktem; mixed/not_applicable/unknown/brak oceny osobno |
| Pokrycie feedbackiem | Ocenione epizody / kwalifikujące się epizody; brak identyfikatorów zadania oznacza niedostępną miarę |
| Zero załadowań | Zero loadów w oknie z pokazanym pokryciem obserwacji; nie dowodzi bezużyteczności |
| Zdrowie integracji | Lag, utracone zdarzenia, błędy, wersja i możliwości adaptera |

Acceptance criteria:

1. Kontrolny ledger daje oczekiwane liczniki po retry, duplikatach, opóźnionych zdarzeniach, cache i korekcie feedbacku.
2. USE HTTP200 nie zwiększa „zastosowano”/„pomogło”. Nieobsługiwany pomiar to unknown. Przy 0 ocen UI nie pokazuje 0% użyteczności.
3. Proporcje mają licznik/mianownik, okno, rewizję/agregat i źródło dowodu. Poniżej 20 ocen pokazujemy liczby i „mała próba” zamiast rankingu procentowego; 20 nie jest dowodem statystycznym.
4. Filtry: repo/scope/skill/rewizja/harness. Eksport CSV/JSON odtwarza dane, bez promptów i treści repo.
5. Spool jest ograniczony i poza krytyczną ścieżką hooka. Retry nie zmienia org po zmianie konta. Brak surowych promptów, kodu i ścieżek w telemetrii.
6. P: po 4 tygodniach owner zapisuje co najmniej jedną decyzję z danych. Bez decyzji wartość dashboardu pozostaje niepotwierdzona.

## 10. Top 5 dodatkowych use case'ów

Ranking jest oceną wartości i wykonalności, nie badaniem popytu. Wszystkie są opisane w docelowym MVP, ale nie blokują wspólnie pierwszego pilota; korzystają z powyższych funkcji, bez pięciu odrębnych platform. Publiczne źródła uzasadniają praktyki, nie chęć płacenia Guidefoldowi.

### U7. Kontrola jakości skilla przed merge

**Aktor/wyzwalacz:** autor zmienia skill, scope lub zależność w PR. CI porównuje rewizje, sprawdza graf i wpływ na przykłady wyszukiwania.

**Wymagania:** przypięty snapshot/config; pozytywne/negatywne przypadki ocenione przez ownera; diff trafień, severity, źródła, artefakt CI. Struktura blokuje; przypuszczalna kolizja jest ostrzeżeniem. Test retrievalu nie dowodzi wykonania procedury.

**AC:** fixture z cyklem, brakującym zasobem i utratą wymaganej karty daje właściwe błędy/przykłady; identyczne wejście daje identyczny deterministyczny wynik. Retry nie dubluje komentarza, jeśli integracja została skonfigurowana. W 10 realnych PR-ach rejestrujemy zmiany spowodowane raportem; zero zmian oznacza brak potwierdzenia wartości.

**MVP:** istniejący validate i raport CI z widokiem w UI; komentarz opcjonalny. Później izolowane testy wykonania. [Agent Skills: ewaluacja](https://agentskills.io/skill-creation/evaluating-skills)

### U8. Pierwsze zadanie w nieznanym module

**Aktor/wyzwalacz:** developer zaczyna pracę w nowym pakiecie. Podaje zadanie/katalog, poznaje ownera i procedury setup/test/review, a agent pobiera instrukcje.

**Wymagania:** strona modułu, źródła/rewizje, owner lub „nieustalony”, uzasadnienie scope, wyjątki od dziedziczenia, scenariusze dobrane przez ownera.

**AC:** 20 scenariuszy prawidłowo pokazuje mapowanie scope/owner; skill sąsiedniego modułu nie jest oznaczony jako obowiązujący bez reguły. USE zwraca właściwą rewizję. Co najmniej 5 realnych zadań: czas do poprawnego uruchomienia/testu, pytania do zespołu i poprawki w review. Próba kierunkowa, bez deklarowania istotnej przewagi.

**MVP:** strona modułu plus SEARCH/USE. Później ścieżki onboardingowe. [Backstage Catalog](https://backstage.io/docs/features/software-catalog/)

### U9. Zmiana źródła i review ownera

**Aktor/wyzwalacz:** zmiana runbooka, usunięcie pliku lub negatywny feedback. Sync pokazuje zależne instrukcje i powód przeglądu.

**Wymagania:** hashe, rewizje, derived_from, owner, last_reviewed_at i audyt decyzji. „Źródło zmienione” jest obserwacją; „skill błędny” wymaga oceny. Usunięcie źródła nie kasuje automatycznie zależnych instrukcji.

**AC:** 100% oznaczonych zmian/usunięć fixture tworzy właściwe zadania. Niezmienione źródło/retry nie alarmuje. Niekompletny skan nie usuwa źródeł. Zamknięcie review zapisuje osobę, rewizję i decyzję; pilot zawiera przynajmniej jeden potwierdzony przypadek.

**MVP:** drift po hashach/linkach i ręczny review. Semantyczna naprawa później. [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)

### U10. Wspólna procedura dla kilku zespołów

**Aktor/wyzwalacz:** drugi zespół potrzebuje sposobu migracji, wdrożenia lub obsługi incydentu. Znajduje procedurę z zakresem i warunkami; owner proponuje wspólny element zamiast kopii.

**Wymagania:** stabilne ID/rewizje, applicability, parametry, zasoby, zależności, diff i źródła. Popularność nie zastępuje dopasowania. Wykonanie produkcyjnych akcji pozostaje pod kontrolą człowieka/harnessa.

**AC:** dwa moduły używają jednego ID skilla z osobnymi epizodami telemetrii. Konsolidacja ma diff i zgodę ownera docelowego scope. Zależności są kompletne albo jawny błąd/budżet. Owner potwierdza uniknięcie utrzymywania dwóch kopii; odbiorca ocenia przydatność.

**MVP:** jeden przykład oparty na U2/U4/U5. Później kampanie zmian w wielu repo. [Agent Skills specification](https://agentskills.io/specification), [Google SRE: incident response](https://sre.google/workbook/incident-response/)

### U11. Sprawdzenie zmiany harnessa/modelu

**Aktor/wyzwalacz:** platform team planuje aktualizację adaptera, harnessa albo modelu. Porównuje te same zadania/snapshot na obecnej i kandydackiej konfiguracji.

**Wymagania:** wersje, przypięty zestaw zadań, wspólna rubryka, wyniki i dowody, eksport. Zgodność dostarczenia i rezultat zadania są oddzielne. Nie wymagamy identycznego tekstu odpowiedzi LLM.

**AC:** raport zawiera wszystkie scenariusze i oba kierunki sukces/porażka; odtwarza się z zapisanych wyników. Brak obserwacji nie jest porażką. Progi decyzji ustalone przed runem; loady nie nadają etykiety „lepszy”. Test adapterów porównuje URN/revision przy identycznym deterministycznym kontrakcie.

**MVP:** ręczny run obecnego eval/pilota, import/eksport wyniku do UI. Później automatyczna macierz, jeżeli będzie używana. [Agent Skills: ewaluacja](https://agentskills.io/skill-creation/evaluating-skills)

## 11. Minimalna architektura

| Element | Decyzja |
|---|---|
| Klient | Obecny Python CLI + scan/import/login/install; lokalny fallback w jawnym profilu |
| UI | React/Vite z prototypu, rzeczywiste API i sesja przez Go |
| Auth | WorkOS; membership/autoryzacja domenowa Guidefold |
| API | Rozszerzenie obecnego Go o katalog, import, org i review |
| Przetwarzanie | Jeden worker CPU z tej samej bazy kodu; kolejka/lease Postgres i limity LLM |
| Dane | Jeden Postgres: org, członkostwa, źródła, graf, rewizje, propozycje, snapshoty i ledger |
| Paczki/zasoby | GCS pod niezmiennymi hashami i autoryzowanym dostępem |
| Retrieval | Obecny Go BM25F i graf; brak obowiązkowego GPU |
| Hosting | Jeden region, obecny kształt T1 rozszerzony o hosted org |

**Frontend: React. Backend: rekomendowane Go.** Szczegółowe porównanie NestJS i podział usług: [architektura MVP](PIVOT-ARCHITECTURE.md).

Hosted multi-org wymaga przebudowy granicy zaufania: zweryfikowane org/repo per request, bez mutacji współdzielonego Store. Cache jest ograniczony i kluczowany org/repo/snapshot/policy. Testy równoległych A/B używają tych samych repo_id/URN i obejmują ciepły cache, retry, zmianę org i rollback. Prawa zapisu katalogu pozostają oddzielone od SEARCH/USE. Dzisiejszy globalny Store.Tenant/Repo i pojedynczy Catalog nie wystarczają. Nie dodajemy bazy grafowej, Kafka, nowego silnika wektorowego ani obowiązkowego Kubernetes. Worker przetwarza dokumenty, nie uruchamia kodu repo. Dostawca LLM jest konfigurowany dla pilota; koszt mierzymy per import, zaakceptowany skill i przydatne zadanie, osobno od minut review ownera. Worker używa istniejącego przypiętego Python buildera do eksportu kanonicznego router_index. Python/PyYAML są narzędziem w obrazie workera; obraz Go API pozostaje bez Pythona. Nie portujemy ponownie rankera tylko z powodu pivotu.

### Dane i API

Encje: organization, membership, repository, import_run, source_revision, skill, skill_revision, scope_node, skill_edge, proposal, installation, api_token, event, review_decision. Każdy rekord domenowy jest związany z org. Git commit i hash treści pozwalają odtworzyć pochodzenie.

URN nie migruje po cichu: katalog ma stabilne ID i jawne aliasy importowanych URN/rename. Tak samo nazwane skille z różnych repo nie są automatycznie scalane.

SEARCH/USE zachowują 1.1, gdzie semantyka jest zgodna. Schemat odrzuca nieznane pola; nowe pola/znaczenia wymagają wersjonowanego rozszerzenia i testów adapterów. Naprawa gwarancji zależności/budżetu musi mieć jawny kontrakt. Nowe operacje zarządcze mają osobne schematy: org/member, import/upload/status, katalog/graf, proposal/export, installation/token, usage/report. Duże paczki nie przechodzą przez limit 16 KiB SEARCH.

Worker i storage również sprawdzają org. Opublikowany pakiet obejmuje SKILL.md i manifest zasobów; jego rewizja wiąże oba. Aktywne paczki, wymagane źródła audytowe i zależności są przechowywane przez okres aktywności oraz co najmniej 30 dni okna rollbacku po dezaktywacji, chyba że polityka usunięcia danych wymaga inaczej. Wygaszenie surowego uploadu nie może zepsuć USE aktywnej rewizji. Domyślna retencja niepotrzebnych surowych wejść pilota: 30 dni; po wygaśnięciu UI sygnalizuje brak podglądu, zostają dozwolone hashe/pochodzenie. Surowa telemetria: dotychczasowe 90 dni. Usunięcie org obejmuje bloby i joby przez odrębną kontrolowaną operację.

## 12. Istniejąca baza i luki

| Obszar | Stan odczytany 2026-09-06 | Co dochodzi |
|---|---|---|
| CLI/mapy/validate | Istnieją | Ogólny import źródeł, login, instalator |
| Go SEARCH/USE/BM25F/snapshoty | Istnieją | Hosted auth, per-request org/repo, zasoby pakietów, zależności, realne adaptery |
| Ledger i events:batch | Istnieją w services/search/telemetry.go | UI, pokrycie obserwacji i dane pilota |
| Authoring reports | Tooling/testy istnieją | Jedna ścieżka CI → review UI |
| React/Vite | Prototyp industrial-surveyor | Aplikacja z backendem i testami użytkowymi |
| Hosted org/auth/import jobs | Brak dowodu gotowej ścieżki w sprawdzonym kodzie | P0 |
| Ekstrakcja/konsolidacja | Projekty/spiki | Ograniczona U2 z review i pomiarem jakości |

To mapa planistyczna, nie pełny audyt kodu. Implementer sprawdza bieżącą gałąź przed historią. Źródła lokalne: [service](../services/search/README.md), [kontrakt 1.1](HARNESS-SERVICE-CONTRACT.md), [telemetria](SEARCH-USE-TELEMETRY.md), [prototyp](../prototypes/industrial-surveyor/package.json).

## 12a. Plan badań, koszt i dowody

1. Przed generowaniem owner i researcher definiują rubryki: wierność źródłu, warunki, scope, wykonalność i wielkość poprawki. Ekstrakcja, enrichment i konsolidacja są oceniane osobno.
2. Manifest ewaluacji zapisuje autora etykiety, źródło zadania, rodzinę źródeł, dataset_version, recipe_version i snapshot_id. Konfiguracja i zestaw mają hash przed pomiarem. Dokładne duplikaty są sprawdzane automatycznie; pokrewne rodziny dzielimy świadomie.
3. Początkowe 30 propozycji to diagnostyka dwóch reviewerów z rozstrzygnięciem rozbieżności. Po naprawach jeden zamrożony run na 60 nowych pozycjach, po 20 na typ operacji, z przypadkami odmowy. Przed runem wybieramy próg rozszerzenia dla każdego typu: propozycja początkowa co najmniej 16/20 bez zmiany znaczenia i zero krytycznych błędów. Wyniki i niepewność raportujemy per typ; nie dowodzi to 80% jakości populacyjnej. Brak 60 niezależnych pozycji oznacza niewykonaną bramkę, nie dobieranie łatwych przykładów.
4. Holdout obejmuje inne rodziny źródeł i nowe zadania, niewidoczne przy dostrajaniu recepty. Po użyciu wyniku do poprawki test staje się developerski; kolejne potwierdzenie wymaga nowego holdoutu. Nie używamy wygenerowanych pseudozapytań jako niezależnego dowodu jakości.
5. Porównanie retrieval z enrichmentem korzysta z owner-reviewed zadań i tego samego snapshotu. Baseline jest rzeczywistym procesem klienta z jego istniejącymi instrukcjami, w tym dobrze skonfigurowaną natywną obsługą skilli.
6. Eksperyment agentów używa izolowanych checkoutów/sesji, przypiętych wersji i budżetów, losowej kolejności. Badanie ludzi używa równoważnych par zadań i kontrolowanej kolejności; ta sama osoba nie rozwiązuje tego samego zadania drugi raz jako rzekomo niezależnej próby.
7. Raport kosztu per import zawiera tokeny, wywołania, retry, opłaty pewne/niepewne, wall time, minuty review, liczbę zaakceptowanych i opublikowanych skilli. Koszt na zaakceptowany skill przy zerze akceptacji jest niedostępny, nie zerowy. Budżet pieniędzy i czasu review uzgadniamy przed rozszerzeniem.
8. Pakiet dowodowy ewaluacji jest oddzielny od surowego uploadu. Za zgodą org zachowujemy go do końca pilota i 30 dni na analizę. Manifest retencji wskazuje pliki i terminy; usunięcie org obejmuje również te dane. Jeżeli źródła muszą zniknąć wcześniej, raport jawnie traci odtwarzalność; hash nie zastępuje treści.

### Komunikacja i oferta do przetestowania

Proponowane zdanie: **„Guidefold dostarcza agentom zatwierdzone instrukcje z repozytoriów firmy i pokazuje zespołowi, które wymagają poprawy.”** Demo zaczyna się od pierwszego zadania w module (U8), potem zmiany źródła (U9) i raportu PR (U7). Piramida jest sposobem organizacji wiedzy, nie samodzielną obietnicą oszczędności.

W UI preferujemy zrozumiałe nazwy „Instrukcje”, „Źródła”, „Do sprawdzenia”, „Użycie”, z terminem skill tam, gdzie potrzebny. Landing pilota nie opisuje niegotowych funkcji jako już dostępnych. CTA: „Sprawdź na swoim repozytorium”; informacja obok: „Najpierw zobaczysz, które pliki trafią do Guidefolda”.

Hipoteza oferty: bezpłatny lokalny scan/podgląd, ograniczony pilot wdrożeniowy z jawnym limitem ekstrakcji, a następnie abonament organizacji z pakietem aktywnych użytkowników i budżetem kosztownych operacji. Kwot nie ustalamy bez rozmów i kosztów. Nie proponujemy podstawowej opłaty per skill lub każde SEARCH/USE, która zniechęcałaby do używania. Jednorazowy popyt może uzasadnić usługę jednorazową zamiast abonamentu.

## 13. Dostarczenie i bramki po przeglądzie CEO/CTO/PM

Pełne docelowe MVP pozostaje opisane w U1–U11. Dostarczamy je przez wcześniejszy **Pilot Core**: wąski pełny przebieg wszystkich głównych obietnic, na ograniczonym wolumenie. Nie czekamy na rozbudowany katalog i wszystkie wykresy, aby sprawdzić użycie.

| Etap | Zakres i dowód | Dalsza decyzja |
|---|---|---|
| Dni 1–3 | Potwierdzenie partnera/danych/buyera; techniczna próba granicy org, pakietów oraz realnych możliwości Claude/Copilot | Zamrożenie obsługiwanego zakresu i aktualizacja nakładu |
| Cel do 2026-09-20 | Pilot Core: Google/GitHub, org, skan/import wybranego repo, lista/źródła/trzy osie, jedna ograniczona propozycja ekstrakcji i wspólnego elementu, Git roundtrip, jeden działający adapter SEARCH/USE, load i feedback | Jeżeli pełny przepływ nie działa, odrębna decyzja o poprawie blokera; bez automatycznej rozbudowy |
| Cel do 2026-10-04 | Co najmniej 20 realnych sesji osoby niebudującej Guidefolda, drugi wspierany harness, podstawowy drift i pierwsza decyzja ownera | Ocena powrotów, kosztu review i rozmowy zakupowej |
| Warunkowo do 8 tygodni | Kompletna beta: wygoda UI, skalowanie importów, niezawodny worker, dwa instalatory, filtry i funkcjonalne demonstracje U7–U11 | Zakres zależy od dowodów; ponowna prognoza po pierwszych 2 tygodniach |

Terminy są celami, nie potwierdzoną estymacją. Zakładamy 2 inżynierów i około 0,5 etatu research/eval; 8 tygodni oznacza około 20 osobotygodni przed kosztem wsparcia. Dalszy etap wymaga jawnego limitu nakładu, nie automatycznej zgody na cały budżet. Brak partnera 2026-09-20 zatrzymuje rozbudowę według wcześniejszej decyzji.

Pilot Core ogranicza wolumen, a nie bezpieczeństwo: izolacja dwóch testowych org, odwołanie dostępu, źródła, walidacja publikacji i poprawność rewizji są wymagane przed danymi klienta. Drugi adapter jest wcześnie sprawdzany technicznie; pierwszy ma pierwszeństwo w pełnym użytkowym przepływie. R dla funkcji Core musi przejść przed dostępem partnera; Q i P mają osobne momenty oceny.

Obserwacja czterech tygodni zaczyna się po aktywacji Pilot Core. U9 (zmienione źródło → decyzja ownera) jest częścią podstawowej pętli powrotu. U7 początkowo używa istniejącego raportu CI, U8 jest zadaniem pilota, U10 pojedynczym przykładem wspólnej procedury, U11 odtwarzalnym raportem z ręcznego runu. Nie wymagają pięciu nowych modułów UI ani usług.

Pilot E6.7: docelowo 3 zespoły i 20–40 sparowanych zadań. Rubryka, progi i analiza są zamrożone przed wynikami. Porównujemy czas do poprawnego wyniku, poprawki, rezultat i obciążenie autorów. Kontrolujemy efekt uczenia człowieka przez kolejność/alternatywne równoważne zadania. Nierozstrzygająca mała próba nie dowodzi braku efektu.

Przed pilotem potwierdzamy osobę decyzyjną, problem, budżet zakupowy i warunki rozmowy o płatnym wdrożeniu. Pod koniec przedstawiamy konkretny zakres/cenę opartą na rozmowach i zmierzonym koszcie. Zainteresowanie, bezpłatne używanie i płatne zobowiązanie są odrębnymi dowodami.

Osobne decyzje po obserwacji:

- Brak przyjmowanych propozycji lub za drogi review: ograniczyć generowanie, zachować wartościową bibliotekę.
- Zero zmian autorów po 10 rzeczywistych raportach PR: ograniczyć authoring, nie rozbudowywać go na podstawie odsłon.
- Brak decyzji ownera: ograniczyć dashboard; sam traffic nie potwierdza wartości.
- Jednorazowy import bez powrotów: zbadać jednorazową usługę porządkowania; nie zakładać subskrypcji.
- Powtarzalne użycie bez postępu rozmowy zakupowej: ograniczony termin i konkretne pytanie do buyerów, bez kolejnej rundy funkcji.
- Powtarzalne korzyści i konkretny krok zakupowy: dalsze wdrożenie, z uzgodnioną obsługą i kosztami.
- Przedłużenie nierozstrzygającego pilota tylko z limitem czasu/nakładu i jednym pytaniem do rozstrzygnięcia.

### Scope change — GitHub App and Chrome extension (2026-09-07)

Rozbieżność: bieżące zlecenie właściciela żąda automatycznego importu repozytoriów z GitHuba przez OAuth/GitHub App i klienta Chrome vs PRODUCT-PIVOT §§5, 10, 14, gdzie import jest CLI-first, a GitHub App i nowe targety są poza MVP.
Decyzja w tej pracy: wdrażam jako Proposed slice zgodnie z bieżącym zleceniem: serwerowy OAuth, wybór repozytorium i cienkie rozszerzenie MV3; CLI pozostaje fallbackiem do czasu wdrożenia czytnika GitHub.
Dokument zastępowany lub do zmiany: PRODUCT-PIVOT §§5, 10, 14 oraz PIVOT-BACKLOG P01/P03; status: do aktualizacji po akceptacji ADR-0034.
Konsekwencje: automatyczny import wymaga nowego kontraktu API/worker, konfiguracji GitHub App, callbacku i testów izolacji; obecny prototyp nie jest dowodem działającego połączenia z GitHubem.
Do decyzji właściciela: tak; czy zaakceptować ADR-0034 jako część Pilot Core i nadać mu osobny zakres wdrożeniowy.

## 14. Poza MVP

Granularne ACL, SCIM/enterprise SSO, automatyczne wykonywanie runbooków, samoczynna publikacja wiedzy, mining pełnych sesji, marketplace, samoobsługowy billing, pełny edytor kodu, HA/multi-region i własny trenowany model. Badania nie blokują tej wersji produktu.

Nowe P01–P15 są lokalnymi ID propozycji, nie utworzonymi GitHub Issues. [Backlog pivotu](PIVOT-BACKLOG.md) mapuje je na obecne epiki #71–#77. Ten etap przygotowuje specyfikację; nie publikuje issue'ów, nie wdraża aplikacji i nie konfiguruje kont dostawców.
