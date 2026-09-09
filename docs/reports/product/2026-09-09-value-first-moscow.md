# Guidefold: wejście zespołu i pierwsza wartość — 50 use case’ów

Status: **W realizacji — zakres wykonawczy: 40 pozycji (10 Must + 15 Should + 15 Could); 10 Won’t now pozostaje odroczone**, 2026-09-09.
Cel: ustalić dokładnie 10 Must Have i 50 pozycji MoSCoW, z odbiorem opartym na wartości i łatwości obsługi.
Wejścia: bieżące zlecenie właściciela, [PRD](../../PRODUCT-PIVOT.md), [backlog](../../PIVOT-BACKLOG.md), [stan implementacji](../../PIVOT-IMPLEMENTATION.md), badania i audyt opisane niżej.
Zakres zastępowania: propozycja zmiany kolejności dostarczania i AC; nie zastępuje jeszcze U1–U11, kontraktów ani Accepted ADR. ID M/S/C/W są lokalnymi pozycjami tej oceny, nie numerami issue.
Autorstwo: agent główny + niezależny subagent w roli product ownera. Ocena agentów nie jest badaniem klientów.

## 1. Decyzja produktowa

**Dostarczamy pełny przepływ: konto → zespół → wybrane repo → zatwierdzona instrukcja → podłączenie agenta → poprawne zadanie → poprawka wiedzy.**

Problemem obecnego wydania jest przerwane wejście użytkownika oraz brak wykazanej korzyści u klienta. Nie ma podstaw do twierdzenia, że produkt nigdy nikomu nie pomoże. Jest za to wystarczający powód, aby zatrzymać rozszerzenia, które nie odblokowują tego przepływu.

Pierwszy klient [hipoteza]: platform/DevEx lead z powtarzalnymi zadaniami wymagającymi wiedzy firmy, ownerem instrukcji i dwoma używanymi harnessami. Pierwszy workflow wybiera partner: np. migracja wewnętrznego SDK, dodanie endpointu zgodnego z firmowym auth albo konfiguracja nowej usługi. Obala hipotezę brak takich powtarzalnych zadań lub brak korzyści po uwzględnieniu utrzymania instrukcji.

Aktywacja ownera: poprawna instrukcja z realnego repo jest opublikowana. Aktywacja zespołu: inna osoba otrzymuje tę rewizję w swoim agencie i kończy realne zadanie z ocenionym wynikiem. Powrót: kolejne zadanie albo poprawka źródła i następna wykorzystana rewizja. Sam import, mapa, test połączenia i licznik loadów nie zaliczają wartości.

**MoSCoW: 10 Must + 15 Should + 15 Could + 10 Won’t now = 50.** Na wyraźne polecenie właściciela implementujemy teraz 40 pozycji Must/Should/Could; Won’t pozostają poza zakresem wykonawczym. Telemetria zespołów używa registry components `@spectrumui/bar-chart` i `@spectrumui/pie-chart` z [Spectrum UI Charts](https://ui.spectrumhq.in/charts/), zaadaptowanych do CSS Modules i tokenów Guidefold, z tekstową alternatywą i stanami empty/partial/error.

## 2. Co sprawdzono i co rzeczywiście jest zepsute

Audyt kodu dotyczy współdzielonego checkoutu `/home/mike/projects/guidefold` z istniejącymi niezacommitowanymi zmianami, bazowy HEAD `3c5ec15`. Dokument powstał w oddzielnym worktree `gf-product-value-20260909`; nie przeniesiono do niego cudzych zmian. Kod w tym worktree może różnić się od badanego checkoutu. Stany poniżej odnoszą się do odczytu 2026-09-09, nie do przyszłego wdrożenia.

Odczyt produkcji był tylko do odczytu: jawny kubeconfig wskazany w AGENTS.md, kontekst `cloudfloo-context`, namespace `guidefold`. Nie odczytywano zawartości sekretów ani nie zmieniano klastra.

| Dowód | Wynik | Znaczenie |
|---|---|---|
| `kubectl … config current-context` | `cloudfloo-context` | Sprawdzono właściwy kontekst. |
| `kubectl … -n guidefold get deployments` | API `guidefold` 0/2; UI 2/2; portal 1/1; worker 1/1 | Dostępny frontend nie oznacza działającej aplikacji. |
| HTTPS GET `/api/v1/auth/providers` | **503** | Użytkownik nie może pobrać metod logowania. |
| HTTPS GET `/api/v1/me` | **503** | Nie działa sprawdzenie sesji; to nie jest prawidłowe 401 anonimowej osoby. |
| `kubectl … logs deployment/guidefold --tail=10` | `service_failed`, `workos_requires_api_key_and_client_id` | Proces nie startuje z powodu brakującego wymaganego zestawu konfiguracji WorkOS. Nie ustalano, który sekret/pole konkretnie jest nieobecny. |
| Przeglądarka `/import`, potem kliknięcie Sign in | `Access not reconfirmed`; kliknięcie zmienia URL na `?step=login`, ale formularz się nie pojawia | Błąd API i logika ekranu blokują bramkę. Tekst o wcześniejszym potwierdzeniu członkostwa jest mylący w tej nowej sesji. |

Przyczynę należy usuwać w konfiguracji produkcyjnego auth oraz stanach UI. W ramach tej pracy przygotowałem w worktree wiring chartu: `publicURL`, `workos.clientID` oraz montowanie `guidefold-workos` jako `WORKOS_API_KEY_FILE`; wartości sekretu i client ID pozostają do ustawienia przez operatora poza repo. Przełączenie publicznej instalacji na dev-provider nie jest naprawą.

| Obszar | Co jest w badanym kodzie | Luka do działającego produktu |
|---|---|---|
| Tożsamość | `services/search/internal/identity/{routes,auth,workos}.go`: Google/GitHub, callback, sesja, logout, `/me`; `ui/src/api/access.ts`: potwierdzanie dostępu | Awaria konfiguracji na produkcji; brak udowodnionego signup/login na rzeczywistych providerach. |
| Bramka | `ui/src/app.tsx`: import dostępny po `denied`, ale `offline/stale` maskują cały widok | Publiczna ścieżka logowania nie może zależeć od wcześniejszego sukcesu prywatnego `/me`; 503 musi mieć osobny komunikat. Nie stwierdzono wycieku danych. |
| Profil | `AccountMenu` w `ui/src/app.tsx` pokazuje nazwę/e-mail/rolę i logout | „Profile and organization” prowadzi do członków org, nie pełnego profilu. Nie znaleziono edycji profilu w sprawdzonych trasach API/UI. |
| Organizacje i role | `identity/orgs.go`, OrganizationRoute: tworzenie, owner/member, zmiana roli, usunięcie, guard ostatniego ownera | Istnieją mechanizmy; działanie przez prawdziwe konta na produkcji niezaliczone. Nie są to repo-level ACL ani SCIM. |
| Zaproszenia | Backend zwraca `accept_url` `/api/v1/invitations/{token}/accept`; GET przekierowuje do hosted acceptance screen, POST nadal wymaga sesji/CSRF | Landing page, adapter `acceptInvitation` oraz lifecycle list/revoke są dodane i pokryte testami Go/UI; live test nowej/istniejącej osoby nadal wymaga działającego WorkOS. |
| Wizard | `OnboardingRoutes.tsx`: login → organization → preview → result | To pasek importu, nie prowadzenie do publikacji, instalacji i pierwszego zadania. Stan w URL nie jest dowodem ukończenia kroku. |
| GitHub import | Przycisk `Connect GitHub` wywołuje `signIn('github')`, czyli `startLogin` i powrót do kroku organization | Logowanie tożsamości nie podłącza repo. `workos.go` wprost nie żąda repo scopes. W sprawdzonym Go/UI nie znaleziono obsługi GitHub App discovery/import. |
| Import/publikacja | CLI scan/import, joby, biblioteka, review, snapshoty, rollback opisane i pokryte testami w rejestrze implementacji | Nie uruchamiano tu ponownie pełnych zestawów testów. Awaria API uniemożliwia live odbiór dalszego przepływu. |
| Agenci/użycie | Adaptery Claude/Copilot, ledger, raport pilota, feedback/drift | Test adaptera i raport techniczny nie potwierdzają użycia przez team ani poprawy zadania. |

W [ADR-0034](../../adr/ADR-0034-github-app-oauth-and-chrome-extension.md) nagłówek ma Accepted z akceptacją 09-08, choć pkt 5 nadal mówi Proposed. Przyjmujemy udokumentowaną akceptację browser-first importu; stary punkt należy uporządkować przy zmianie dokumentu kanonicznego. Rozszerzenie Chrome nie jest potrzebne do działania importu w przeglądarce.

## 3. Jak badania zmieniają priorytety

Zakres przeglądu: cały katalog rodzin tematów w [AGENT-SKILLS-RESEARCH](../../AGENT-SKILLS-RESEARCH.md), nowsza [synteza pomiarów](../../RESEARCH.md), raporty produktowe, stan badań 08–09 września i cztery pełne publikacje z poprzedniej analizy. Nie wykonano ponownie wszystkich eksperymentów ani niezależnej replikacji każdej publikacji. Starszy rejestr ma historyczne opisy implementacji i rekomendacje, które nie są aktualnym kontraktem produktu. Przy poniższych dalszych pracach korzystano z lokalnych syntez; nie deklarujemy nowej weryfikacji wszystkich wersji arXiv.

| Rodzina i źródła | Wniosek dla produktu | Decyzja |
|---|---|---|
| SkillCenter | Wiedza pomaga, gdy zadanie ma rzeczywistą lukę, biblioteka ją pokrywa i retrieval ją odnajduje; wielkość zbioru nie wystarcza. | M05/M08/M10: wybierz konkretny problem firmy, mierz wynik. |
| SkillRouter, SkillRet, Field-Aware Retrieval, BM25/BEIR/DPR/RRF/monoBERT | Ranking, dostęp do body i komplet wymaganych skilli to różne rzeczy; wynik benchmarku nie równa się poprawie pracy. | M08: pełny potrzebny materiał i właściwy zakres; utrzymaj baseline, zmiany rankingu osobno. |
| GoS, R3-Skill, SkillResolve, badanie lokalne graph-semantics | Komplementarne instrukcje, zamienniki, kolejność i zwykłe odwołania wymagają różnych relacji. | Nie wybierać jednego elementu rodziny, jeśli potrzebne są dwa; nie zamieniać similar w requires. |
| GraSP, HiSkill, AIP, HASP | Testowalne kroki i mały podgraf są obiecujące; badania nie dowodzą poprawy Guidefold. AIP nie izoluje w pełni struktury od lepszych skryptów. | S20: jedna sprawdzalna procedura przed nowym silnikiem wykonawczym. |
| SkillPyramid, SkillRAE, Corpus2Skill, SkillCorpus, SkillAlchemy, lokalny ascent | Hierarchia i pochodzenie mają zastosowania, lecz graf sam nie dowodzi transferu. Najnowszy edgewise run potwierdza strukturę, nie semantyczną prawdę ani wynik zadania. | S21: jedno sprawdzone ponowne użycie przez drugi team; bogata mapa C31. |
| SkillsBench, SWE-Skills-Bench, Regression Tax, Harmful Skills, ContinualSkillBench | Korzyść zależy od zadania; trzeba raportować pogorszenia i kontrolować historię sesji. | M10: obecny proces klienta jako baseline, niezależne sesje, także zadania bez potrzeby skilla. |
| SkillRevise, SkillHEX, MSCE, SkillLearnBench, CoEvoSkills | Poprawka wymaga wyniku/verifiera i ponownego sprawdzenia; self-feedback może dryfować. | M09: owner zatwierdza zmianę; automatyczne merge/publish W44. |
| WikiSkill, Trace2Skill, MASkills, MemSkill, Memento-Skills | Uczenie z doświadczenia wymaga wiarygodnego materiału z wykonań i selekcji. | Zbieraj minimalny feedback M09, nie pełne ślady sesji W45. |
| MERA, SkillRL, SkillFlow, SkillOrchestra, PILOT, Generative Skill Composition | Więcej modeli, trening i supervisor zwiększają zakres oraz wymagają własnych wyników. | W42/W43/W50: odłóż do wykazanej potrzeby. |
| SkillJack, Semantic Supply-Chain, Skills in the Wild, ClawsBench, badania reusability | Importowane instrukcje i skrypty nie są zaufane tylko dlatego, że mają strukturę. | M04/M06/M08: zakres, źródło, zatwierdzenie, integralność, brak wykonywania kodu przez importer. |
| SkillZip, SKIM, lokalne progressive-disclosure i activation-bench | Kompresja może gubić obowiązkowe informacje; oszczędność jest zależna od rodzaju zadania. | Nie limitować każdej procedury do identycznej długości; mierzyć koszt przy poprawnym wyniku. |
| Lokalne delivery-vs-concatenation i SRA/SkillRet transfer | Brak potwierdzonej uniwersalnej przewagi. Zewnętrzne kontrole wykazały także regresje. | Nie sprzedawać większego recall/piramidy jako gotowej wartości. |
| Lokalne E2/proof-gate | Dodatni sygnał na syntetycznych konfliktach, poprawne odrzucanie mutacji; brak niezależnego dowodu wartości u klienta. | Nie wymuszać proof-gated na istniejących skillach bez proof; pokaż ograniczenia i sprawdzaj realny wynik. |
| Research UI i ankieta | Desk research; brak rozmów, ankieta niewysłana, odpowiedzi syntetyczne. | Cele użyteczności niżej są hipotezami do testu z ludźmi. |

Źródła czterech prac: [SkillCenter](https://arxiv.org/html/2607.07676v1), [GraSP](https://arxiv.org/html/2604.17870v1), [HiSkill](https://arxiv.org/html/2607.25853v1), [AIP v2](https://arxiv.org/html/2606.04781v2). Ich wyniki nie są dodawane ani przedstawiane jako spodziewany procent poprawy Guidefold.

Trwałe raporty lokalne: [progressive disclosure](../market/2026-09-07-progressive-disclosure-evidence.md), [delivery vs concatenation](../market/2026-09-08-delivery-vs-concatenation.md), [applicable set](../market/2026-09-08-applicable-set-real-monorepos.md), [propozycja testu transferu](../market/2026-09-08-ascent-benchmark-and-positioning.md), [research UI](../../ui/pipeline/01-research.md), [ankieta](../../ui/pipeline/03-survey.md).

Dodatkowe lokalne, gitignored wejścia w badanym checkoutcie: `research/scientific-status-2026-09-08/DECISION.md`, `research/scientific-status-2026-09-09/README.md`, `research/activation-bench-2026-09-07/README.md`, `research/graph-semantics-2026-09-07/README.md`, `research/skillbench-execution-a11y-2026-09-07/README.md`, `research/product-paper-assessment-2026-09-07/README.md`. Nie są przenośnym pakietem replikacji. Materiał dla zewnętrznego klienta powinien opierać twierdzenia na trwałych, dostępnych raportach.

## 4. Wspólna definicja odbioru

**R — wydawalne technicznie:** właściwe testy zachowania i kontraktów, backendowa autoryzacja, stany loading/empty/partial/error/restricted, retry bez duplikatów, keyboard-only i axe dla zmienionej ścieżki. Realne sekrety/provider konfigurowane poza repo. Rewizja i środowisko w raporcie. Nie zaliczamy publicznego auth testem dev-provider.

**Q — użyteczne:** test zadaniowy z co najmniej 5 osobami niebudującymi produktu, wynik co najmniej 4/5 bez pomocy moderatora dla wskazanego zadania. Pomoc, porzucenie i błąd są zapisywane; wyników nie uśredniamy tak, aby ukryć barierę jednego kroku. To próg iteracji przy małej próbie, nie estymacja rynku.

**P — wartość potwierdzona:** rzeczywisty team, repo, harness i zadanie, ocena rezultatu oraz czas utrzymania. Negatywny lub nierozstrzygnięty wynik oznacza zakończony eksperyment, ale nie „wartość udowodniona”. Testy i mały pilot nie uzasadniają gwarancji braku błędów.

Wszystkie liczby czasowe poniżej są **proponowanymi celami**, do zamrożenia przed testem. Czas aktywny, czekanie na API/import, oczekiwanie na administratora GitHuba i merge są raportowane osobno. Pierwszy pilot obejmuje repo i konto z wcześniej dopuszczonym zakresem dostępu; nie ukrywamy czasu uzyskania tych zgód.

Wspólna DoD każdego Must: dowód R + odpowiednie Q/P wskazane niżej, brak otwartych P1/P2 w danym przepływie, dokumentacja/kontrakt zaktualizowane, test na docelowej konfiguracji, zapis wyniku i ograniczeń. R wystarcza do kontrolowanego startu pilota; nie wystarcza do deklaracji kompletnej wartości produktu. Pełne DoD produktu wymaga P.

Komendy według dotkniętej warstwy: CLI `python3 -m py_compile skills/guidefold/scripts/guidefold` i właściwe pytest; Go `go vet ./...`, `go test ./...` z wymaganym Postgres dla integracji; UI `pnpm build`, `pnpm test`, `pnpm test:contracts`, `pnpm test:e2e`, test flow/wizualny przy zmianie UI. W tej pracy przygotowano plan i audyt, wykonano wiring WorkOS w Helm, publiczną bramkę przy przejściowym 503, browser landing i lifecycle zaproszeń dla M02 oraz registry components Spectrum UI Charts dla telemetry delivery/context/feedback, zaadaptowane do CSS Modules i tokenów. Live OAuth, live invite i realne źródła GitHub nadal wymagają ustawienia client ID/sekretu przez operatora oraz wdrożenia.

## 5. Dziesięć MUST HAVE

### M01 — Rejestruję konto, loguję się i widzę swój profil

Persona: nowy i powracający użytkownik. Wartość: samodzielne wejście do produktu. Mapa: U3/P01. Priorytet: **P0, pierwszy blocker**. Stan: mechanizmy kodowe istnieją; produkcja jest zablokowana przez brak skonfigurowanego client ID/sekretu WorkOS.

AC:
- Anonimowa osoba trafia do czytelnej publicznej bramki. Nowe konto Google i GitHub przechodzi prawdziwy redirect/callback; kolejny login wraca do tej samej tożsamości. Nie dokładamy lokalnych haseł.
- Signup prowadzi do utworzenia/dołączenia org, login zachowuje bezpieczny wewnętrzny deep link. Powiązanie metod logowania wymaga potwierdzenia; samo zgodne e-mail nie przejmuje konta.
- Profil minimum pokazuje nazwę, e-mail, metodę logowania, aktywną organizację/rolę oraz logout. Wyjaśnia, gdzie zmienia się dane u providera; nie udaje gotowej edycji profilu.
- `/me` bez sesji daje 401, provider discovery działa publicznie. 503 pokazuje awarię usługi i retry, nie „członkostwo wygasło”; formularz/komunikat publiczny nie jest zasłonięty przez prywatną bramkę.
- Wylogowanie, timeout, anulowany OAuth, zły state i nieprawidłowy callback nie ujawniają prywatnych danych; powrót Back nie przywraca cache.
- Na publicznej konfiguracji brak dev-provider; API osiąga gotowość, a dostępne w UI metody faktycznie działają.

DoD: R: świeże i powracające konta obu providerów na docelowej domenie, testy błędów sesji/OAuth. Q: 4/5 osób wchodzi bez operatora, cel ≤2 min aktywnej pracy. P: konta realnego ownera i developera używane dalej w M02–M10. Owner dostarczenia: backend + deployment, frontend.

### M02 — Tworzę zespół, zapraszam ludzi i kontroluję dostęp

Persona: owner i zaproszony developer. Wartość: współpraca i poprawna granica danych. Mapa: U3/P01–P02. Zależność: M01. Stan: org/member API istnieją; browser landing i POST akceptacji są domknięte repozytoryjnie, live odbiór zależy od M01.

AC:
- Owner podaje nazwę org; slug ma automatyczną propozycję i bezpieczną obsługę kolizji. Przełączanie org czyści repo, stare dane i niedozwolone cache.
- Zaproszenie otwiera stronę, która po loginie pozwala jawnie zaakceptować właściwą org i rolę. Działa dla nowego i istniejącego konta. Jednorazowy token, zła osoba, wygaśnięcie i ponowienie są obsłużone.
- Minimum uprawnień: owner zarządza członkami/importem/review/publikacją; member korzysta z opublikowanej wiedzy i wysyła feedback. Rola ma prosty opis. Ograniczenia są egzekwowane przez API, nie sam disabled button.
- Owner nie może usunąć ani zdegradować ostatniego ownera. Usunięcie membera blokuje jego następne żądanie API; UI maskuje dane w obowiązującym limicie 45 s lub przy najbliższym potwierdzeniu, także po powrocie do ukrytej karty.
- Podmiana org/repo/resource ID, sesji i installation tokena nie daje dostępu do drugiej org. Cofnięcie dostępu osoby i cofnięcie integracji organizacyjnej mają osobne, jawne znaczenie.
- Po domknięciu S15 repo-level ACL jest dostępne jako opt-in: owner może ograniczyć repo do jawnie wskazanych członków; wymagający partner nadal musi przejść negatywne testy storage/worker/tokenów przed wdrożeniem.

DoD: R: dwie org, owner/member, negatywne przypadki dostępu do API/storage/jobów/eksportu, lifecycle zaproszenia i ostatni owner. Q: 4/5 zaproszonych dołącza ≤3 min aktywnie bez pomocy. P: minimum dwie osoby w jednym realnym teamie, jedna z nich nie konfigurowała Guidefold. Owner: identity/backend + frontend.

### M03 — Wizard prowadzi mnie do pierwszego użycia i pozwala wrócić

Persona: owner konfigurujący team. Wartość: nie musi odgadywać kolejności. Mapa: U1/U3/U4/U5, P01/P03–05/P09–10; nowe przekrojowe AC. Zależności: implementowany razem z M01–M08. Stan: czterostopniowy import, brak pełnej aktywacji.

AC:
- Jedna ścieżka: konto i team → repo/zakres → wybór instrukcji → publikacja → narzędzie → pierwsze zadanie. Zawsze jedno główne następne działanie, widoczny powód blokady i możliwość powrotu.
- Postęp wynika z backendowych faktów. Parametr `step=done`, odświeżenie i nowa sesja nie oznaczają ukończenia ani nie tworzą duplikatu importu/org.
- Po wyjściu użytkownik wraca do ostatniego niedokończonego etapu; niesekretne wybory są zachowane. Tokenów/invite linków nie zapisujemy jako draftów.
- Po pierwszym wejściu UI nie wymaga rozumienia URN, snapshot, job, manifest digest lub grafu. Szczegóły techniczne są dostępne na żądanie.
- „Gotowe do pracy” wymaga potwierdzonego load; „Pierwsze zadanie ukończone” wymaga zapisanego rezultatu. Checklisty nie utożsamiają tych stanów.
- Cel całej konfiguracji dla istniejącej zatwierdzonej instrukcji: 4/5 osób osiąga publikację i load w ≤15 min aktywnej pracy; czas zadania mierzony osobno.

DoD: R: test przejścia, powrotu, braku uprawnień, błędu importu i utraty sesji. Q: obserwacja 5 nowych osób z zapisanymi punktami tarcia i czasem czekania. P: partner przechodzi bez rozmowy instalacyjnej z autorem. Owner: frontend/UX + product owner.

### M04 — Podłączam GitHub i importuję wybrany zakres bez ręcznej konfiguracji

Persona: owner repo. Wartość: używa istniejących materiałów bez przygotowania YAML i kopiowania tokenów. Mapa: U1/P03–04 + Accepted ADR-0034. Zależności: M01/M02. Stan: CLI istnieje; browser-first połączenie nie jest domknięte.

AC:
- Oddzielne „Zaloguj przez GitHub” i „Podłącz repozytorium”. GitHub App rzeczywiście autoryzuje wybrane repo; UI pokazuje repo/ref/podfolder i brak potrzebnych uprawnień, nie zapętla loginu.
- Widoczne są wyłącznie repo dostępne przez przecięcie uprawnień użytkownika i instalacji. Odwołanie dostępu zatrzymuje kolejne odczyty; callback jest związany z właściwą sesją/org.
- Przed czytaniem zawartości pokazujemy dozwolony zakres dostępu; przed importem/LLM listę wybranych plików, wykluczeń i informację, co już odczytano. Podgląd nie udaje, że serwer niczego jeszcze nie przeczytał.
- SKILL.md wraz z potrzebnymi references/scripts jest importowany jako istniejący pakiet. AGENTS.md, CLAUDE.md i runbooki są źródłami; nie udają gotowych opublikowanych skilli. Brak klucza LLM nie blokuje importu i użycia istniejących pakietów.
- Importer nie wykonuje kodu repo, nie podąża za symlinkiem poza zakres; blokuje jawne sekrety i respektuje wykluczenia. Nie obiecujemy wykrycia wszystkich sekretów.
- Retry zachowuje tożsamość joba; powtórzenie nie dubluje skilli. Przyrost, zerowa zmiana, plik nieobsługiwany, partial i utrata uprawnień mają wynik i działanie naprawcze. Partial nie wywołuje usunięć.
- Owner uruchamia kolejną synchronizację podłączonego repo przyciskiem w UI, widzi przypięty commit, postęp, wynik i retry; przy nadal ważnej autoryzacji nie loguje się ponownie ani nie podaje tokenów. Test: zmiana Git → synchronizacja w UI → review/publikacja → następny load. Automatyczny webhook pozostaje S11.
- CLI pozostaje działającym fallbackiem z instrukcją dopasowaną do org/repo. Dodatkowe repo i importerzy nie blokują pierwszego wspieranego zakresu.

DoD: R: prywatne zatwierdzone repo testowe przez prawdziwy GitHub App, wybrany ref/podfolder, revoke i retry, test izolacji. Q: 4/5 ownerów uruchamia poprawny import bez edycji YAML, cel ≤5 min aktywnie po dostępnej autoryzacji. P: repo partnera, świadomy wybór danych. Owner: importer/backend + integracja GitHub + frontend.

### M05 — Po imporcie wiem, czego mogę użyć i co wymaga poprawy

Persona: owner i developer. Wartość: wynik ma konkretne zastosowanie, nie pustą mapę. Mapa: U4/U8/P05/P14. Zależność: M04. Stan: lista/źródła istnieją; guided first result niepotwierdzony.

AC:
- Wynik pokazuje istniejące poprawne instrukcje, źródło, zakres i właściciela; przy każdym problemie nazwę pliku i następne działanie.
- Dla wskazanego modułu/zadania pokazuje do 3 sensownych kandydatów. Zero lub jeden kandydat jest prawidłowe; system nie generuje treści, żeby zapełnić ekran.
- „Brak instrukcji” odróżnia brak źródła, błąd importu i brak dopasowania. Nie nazywa automatycznie każdego modułu bez skilla luką biznesową.
- Owner może otworzyć źródło i przejść do publikacji istniejącego pakietu bez mapy, enrichmentu albo masowej generacji.
- Na zamrożonej próbce 10 scenariuszy partnera reviewer ocenia trafność propozycji: cel ≥8/10 z właściwym kandydatem lub poprawnym brakiem; zero kandydatów z niedozwolonej org/statusu.

DoD: R: repo 0/1/wiele skilli, błędy i niepełny import. Q: 4/5 osób wskazuje właściwą instrukcję i kolejny krok ≤2 min. P: wybrana instrukcja jest użyta w M08. Owner: frontend/knowledge + product owner.

### M06 — Zatwierdzam instrukcję i udostępniam dokładnie tę wersję

Persona: owner wiedzy. Wartość: kontrola bez zbędnych rund pracy. Mapa: U2/U5/P07/P09. Zależność: M04/M05. Stan: review/publication mechanizmy istnieją, live odbiór zablokowany.

AC:
- Istniejący zatwierdzony pakiet z Git nie wymaga wygenerowania go od nowa. Owner widzi źródło/commit, zakres i komplet zasobów, zatwierdza publikację.
- Dla nowej treści: diff ze źródłem → decyzja → Git → synchronizacja. UI mówi dokładnie, co zostało przygotowane i co trzeba zrobić dalej; eksport nie jest publikacją. Automatyczny PR to S13, nie warunek tego Must.
- Niezmieniony zatwierdzony digest nie wymaga drugiego pełnego review; zmiana treści/zasobów unieważnia poprzednią decyzję.
- Draft/odrzucona rewizja nie trafia do agenta. Snapshot aktywuje się atomowo; błąd pozostawia poprzednią wersję.
- Owner może cofnąć aktywną rewizję; przyszłe pobrania stosują cofnięcie. Nie obiecujemy usunięcia wiedzy już załadowanej do trwającej sesji agenta.
- UI pokazuje prosty stan „Dostępne agentom” plus szczegóły rewizji. Niedopasowana wersja, brak obowiązkowego zasobu i brak uprawnień blokują publikację z konkretną naprawą.

DoD: R: istniejąca i nowa instrukcja, zmieniony digest, awaria publikacji, rollback, porównanie delivered bytes z zatwierdzonym pakietem. Q: 4/5 ownerów rozumie i kończy ścieżkę; istniejący pakiet ≤3 min aktywnie, nowa treść ≤15 min aktywnego review. P: prawdziwy owner publikuje i developer odbiera tę samą rewizję. Owner: review/publication + frontend.

### M07 — Podłączam używanego agenta i wiem, że połączenie działa

Persona: developer. Wartość: nie musi ręcznie konfigurować endpointów i tokenów. Mapa: U5/P10. Zależność: M01/M02/M06. Stan: adaptery/testy istnieją, realne sesje teamu nieudowodnione.

AC:
- Wybór Claude Code albo Copilot CLI daje instrukcję dopasowaną do środowiska i repo. Jedno prowadzone logowanie urządzenia/instalacja bez pokazywania sekretu w URL.
- Member może podłączyć narzędzie w granicach przyznanych praw; nie musi być ownerem, aby wykonać zwykłe zadanie. Tworzenie integracji organizacyjnej pozostaje kontrolowane.
- Test kończy się rzeczywistym SEARCH i LOAD znanej opublikowanej rewizji z danego repo. Ping/200 nie daje zielonego statusu użycia.
- Zły endpoint, brak scope, cofnięty token i brak opublikowanej instrukcji prowadzą do odrębnych działań naprawczych.
- Instalator nie nadpisuje cudzej konfiguracji; ponowienie jest bezpieczne, uninstall odwraca własne zmiany. Potwierdzone repo/scope są widoczne.
- Oba harnessy przechodzą ten sam scenariusz. Pierwszy odblokowuje kontrolowany pilot, drugi jest warunkiem deklaracji gotowego wsparcia wielonarzędziowego.

DoD: R: testy kontraktów/instalatora/uninstall oraz prawdziwa sesja każdego wspieranego harnessa. Q: 4/5 developerów łączy narzędzie ≤5 min aktywnie. P: niezależny developer kończy zadanie w każdym z dwóch harnessów, z wynikami i rewizjami. Owner: CLI/integrations + frontend.

### M08 — Agent wykonuje firmowe zadanie z właściwą instrukcją

Persona: developer. Wartość: mniej zgadywania i poprawek seniora. Mapa: U5/U8/U10/P09/P10/P14. Zależności: M06/M07. Stan: delivery jest, dowód zadania pozostaje luką.

AC:
- Partner wybiera powtarzalne zadanie wymagające wiedzy wewnętrznej oraz kryterium poprawności przed wykonaniem. Zadanie ogólne, które model już rozwiązuje, jest kontrolą, nie jedynym demo.
- Instrukcja odpowiada repo, zakresowi i wersji; wymagane zasoby/prerequisites są dostępne. Fakty źródłowe i kryterium wykonania są rozdzielone.
- Jawny konflikt, nieaktualna instrukcja, brak wymaganej zależności lub budżetu nie kończy się cichą obietnicą kompletności. Agent dostaje powód i potrzebne pytanie/odmowę, bez obchodzenia ograniczeń.
- Body jest doczytywane, gdy karta nie wystarcza. Nie utożsamiamy czterech kart z kompletem wiedzy i nie kompresujemy obowiązkowych kroków tylko dla limitu.
- Wykonanie pozostaje w środowisku klienta i jego harnessie; hosted importer nie uruchamia skryptów klienta. Wynik potwierdza test/uzgodniony reviewer, nie deklaracja modelu.
- Pierwszy scenariusz kończy się zaakceptowaną zmianą. Sam LOAD nie zalicza AC; późniejsze porównanie czasu/korzyści prowadzi M10.

DoD: R: testy scope/status/version/resources/konflikt/ASK i pozytywny przypadek dostarczenia. Q: 5 rzeczywistych zadań, z jawnie ocenionym wynikiem i brakami. P: co najmniej jedno poprawne zadanie niezależnego developera; korzyść względem baseline dopiero po M10. Owner: retrieval/integrations + owner procedury.

### M09 — Zgłaszam problem, a poprawiona wiedza trafia do następnego zadania

Persona: developer zgłaszający i owner poprawiający. Wartość: problem nie powtarza się bez reakcji. Mapa: U6/U9/P11/P13. Zależności: M06–M08. Stan: feedback/drift/kolejka istnieją; użycie pętli niepotwierdzone.

AC:
- Developer w ≤30 s aktywnie zgłasza „pomogło / przeszkodziło / nie użyto / nie wiem”, opcjonalnie powód. Feedback wiąże rewizję, zadanie i harness bez domyślnego uploadu całej rozmowy.
- Zmiana/usunięcie źródła podczas pełnego sync lub negatywny feedback tworzy konkretne zadanie ownera z przyczyną. Retry nie mnoży wpisów; partial nie oznacza deletion.
- Owner widzi źródło, dotkniętą rewizję i zakres oraz może poprawić, odrzucić albo odłożyć z powodem. Automatyczna obserwacja nie publikuje zmian.
- Poprawka przechodzi Git/publication; kolejne zadanie otrzymuje nową rewizję. Kolejka rozróżnia „decyzja podjęta”, „opublikowane” i „sprawdzone w użyciu”.
- Cofnięta integracja i brak telemetrii pokazują „brak danych”, nie „skill nie pomaga”.

DoD: R: źródło zmienione/usunięte/partial, feedback retry, powiązanie rewizji. Q: 4/5 ownerów rozumie zadanie naprawcze i wykonuje decyzję bez wsparcia. P: przynajmniej jedna prawdziwa decyzja ownera i następne użycie po poprawce; do oceny powrotów 4 tygodnie obserwacji. Owner: usage/importer + frontend + owner wiedzy.

### M10 — Team widzi, czy Guidefold jest wart dalszego używania

Persona: platform lead i buyer. Wartość: decyzja na podstawie poprawnej pracy i kosztu utrzymania. Mapa: U11/P15, U6/P11. Planowanie od dnia 1; pomiar po M07/M08. Stan: narzędzia raportu istnieją, brak dowodu pilota.

AC:
- Przed pilotem zapisujemy problem, ownera, buyera, obecny sposób pracy, rubrykę i warunek kontynuacji. Kontrolą jest dobrze skonfigurowany obecny proces z natywnymi instrukcjami.
- Raport lejka rozróżnia wejście, login, org, import, publikację, instalację, LOAD, wynik zadania i powrót. Ma mianowniki, daty i brak danych; nie przechowuje sekretów.
- Pierwsze 20 realnych sesji służy diagnozie aktywacji. Proponowany test korzyści: 20–40 par zadań łącznie w 3 teamach, czyli 40–80 wykonań (jedno z Guidefold i jedno kontrolne na parę), przypięte wersje/budżety, kontrola kolejności i brak podwójnego liczenia uczenia tej samej osoby. Dla ludzi używamy równoważnych zadań, dla agentów izolowanych sesji; przydział i jednostka analizy są zamrożone przed pomiarem. To doprecyzowanie proponowanego nakładu P15, nie już wykonany pilot.
- Mierzymy czas aktywny do poprawnego wyniku, review/poprawki, sukces i pogorszenia, koszt modelu, przygotowania i utrzymania instrukcji. Wyniki nieskończonych zadań nie znikają z raportu czasu.
- Proponowany próg decyzji pilota: ≥20% niższy łączny nakład aktywnej pracy na porównywalne zadania przy braku zaobserwowanego wzrostu istotnych błędów; raport pokazuje niepewność i mianownik. Mała próba nie ustanawia statystycznej gwarancji non-inferiority. Inny próg trzeba zamrozić przed wynikami.
- Zapisujemy konkretny krok zakupowy osobno od zainteresowania. Niepowodzenie/niepewność prowadzi do cięcia zakresu lub ograniczonego eksperymentu, nie automatycznej kolejnej rundy funkcji.

DoD: R: odtwarzalny raport z manifestem wersji i kontrolą liczników, bez podszywania danych syntetycznych pod klientów. Q: buyer potrafi odczytać co wiadomo i czego nie wiadomo. P: raport rzeczywistego pilota, decyzja ownera/buyera; wartość zaliczona tylko przy uprzednio ustalonym progu. Owner: product owner/research + partner.

## 6. Pozostałe 40 pozycji MoSCoW

Stan: **K** = znaleziony mechanizm/testy lub wskazany w rejestrze, nie live DoD; **Cz** = fragment/propozycja, brak pełnej ścieżki; **ND** = brak dowodu w audycie, nie twierdzenie o nieistnieniu każdego fragmentu; **B** = badawcze. Żaden taki status nie oznacza wartości u klienta. Każda przyszła implementacja wymaga R/Q/P odpowiednich do zakresu; „odbiór” poniżej podaje dodatkowy warunek. Rozszerzenia spoza U/P są jawnymi propozycjami zakresu, nie autoryzacją runtime/ACL/wykonania.

### SHOULD — następne 15 po działającym przepływie Must

| ID | Use case | Stan / mapa | AC i DoD dodatkowe | Dlaczego później |
|---|---|---|---|---|
| S11 | Owner automatycznie synchronizuje źródła po zmianie gałęzi | **Cz — webhook, rejestr instalacji i idempotentny `ascend.run` job zaimplementowane; connector GitHub REST pozostaje konfiguracją wdrożenia** | Zweryfikowany webhook, retry bez duplikatów, zmiana właściwej rewizji; test realnego commitu; nowa treść nie publikuje się bez wymaganej decyzji | M09 najpierw obsługuje jawny sync, potem automatyzuje powrót. |
| S12 | Owner ponawia, odwołuje i śledzi oczekujące zaproszenia | **K — zaimplementowane + testy**, U3/P01 | Lista statusów nie zwraca tokenów, revoke jest idempotentny, zaakceptowanego zaproszenia nie można cofnąć; scenariusz dwóch przeglądarek pozostaje testem live | Podstawowe poprawne zaproszenie M02 pierwsze. |
| S13 | Owner wysyła zatwierdzoną propozycję bezpośrednio jako PR | **K — template CI uruchamia `ascend` po zmianie i otwiera osobny PR przez `peter-evans/create-pull-request`, z dedykowaną gałęzią i tokenem opcjonalnym** | Jeden draft PR z właściwym diffem; retry nie dubluje; publikacja dopiero po sync/merge; realny Git roundtrip w repo klienta | M06 może korzystać z istniejącego eksportu. |
| S14 | Owner deleguje review bez przekazania zarządzania organizacją | **K — reviewer ACL, egzekwowanie na decision/export i test scoped** | Macierz roli reviewer, testy wszystkich zabronionych mutacji; dwóch rzeczywistych autorów | Owner/member wystarcza pierwszemu dopuszczonemu teamowi. |
| S15 | Owner ogranicza członkowi dostęp do wybranych repo | **K — opt-in repo ACL, read/write grant/revoke, reviewer assignments i negatywny test cross-repo** | Repo ACL obejmuje API/worker/storage/eksport/cache/tokeny; cross-repo negatywne testy; partner z tym wymogiem | Jeżeli wymagane u partnera, staje się bramką przed jego danymi. |
| S16 | Owner przypisuje opiekunów instrukcji z podpowiedzi CODEOWNERS | **K — scan/manifest wylicza sugestie CODEOWNERS z jawną niepewnością** | Sugestia wymaga potwierdzenia; brak dopasowania jest jawny; CODEOWNERS nie zmienia uprawnień; realny owner przyjmuje odpowiedzialność | Po imporcie rzeczywiście brakuje jasnego opiekuna. |
| S17 | Owner usuwa zbędną pracę przez wykrywanie identycznych duplikatów | **K — digest manifestu i `ON CONFLICT` reuse blokują identyczny import** | Dokładny digest i pochodzenie pokazane razem; nie scala zakresów ani podobnych semantycznie treści; test dwóch repo i decyzja ownera | Po stwierdzonym powtarzaniu review tych samych plików. |
| S18 | Owner zamienia jeden runbook w propozycję skilla | **K — `guidefold extract` one-shot przechodzi scan → import → plan → propozycje** | Źródło/scope/warunki i poprawna odmowa; Q według PRD §12a: diagnoza 30, potem nowe 60 po 20/typ; koszt/review; realne wykonanie | Nie blokuje wartości istniejących skilli. |
| S19 | Autor sprawdza odnajdywalność instrukcji przed merge | **K — `guidefold report --base` i `validate` mają deterministyczne kontrole CI** | Raport kontrolnego PR wskazuje regresję i poprawkę; 10 realnych PR oraz decyzje autorów; merge blokują normatywne błędy struktury/kontraktu, przykłady rankingu są diagnostyczne | Nie rozbudowywać raportu bez reakcji autorów. |
| S20 | Owner tworzy jedną procedurę z testowalnymi krokami | **Cz — `guidefold procedure` sprawdza Inputs/Outputs/Preconditions/Steps/Verification i opcjonalnie uruchamia lokalny `metadata.verifier`** | Struktura i jawny lokalny verifier są testowane; hosted worker nie wykonuje kodu repo; nadal potrzebny held-out wynik niezależnego zadania i porównanie z/bez grafu | AIP/GraSP są inspiracją, nie dowodem gotowego produktu. |
| S21 | Drugi team wykorzystuje zatwierdzoną wspólną procedurę | B/K, U10/P08/P14 | Zakres zatwierdzony, wyjątki zachowane; held-out sibling wykonuje zadanie; brak kopiowania i oceniony wynik | Transfer ważniejszy od masowej piramidy. |
| S22 | Owner przegląda kilka podobnych propozycji naraz | **K/Cz — UI pozwala zaznaczyć wiele propozycji i porównać scope, pliki, body oraz decyzje bez auto-apply; test UI** | Grupowanie nie ukrywa różnic scope/digest; każda decyzja audytowana; mniejszy czas review na próbce | Najpierw jedna łatwa decyzja. |
| S23 | Team wykrywa regresję po zmianie modelu lub harnessa | **K — `guidefold eval --baseline` porównuje zamrożone przypadki i może zablokować regresję** | Zamrożone zadania, porównanie obu wersji, jawne pogorszenia; decyzja o rollout | Po zebraniu sensownego banku zadań M10. |
| S24 | Owner kontroluje koszt generacji i czas review | **K — plan/generate respektuje limity files/groups/tokens/calls/USD i pokazuje koszt w jobie** | Limit przed wywołaniem, koszt/retry per import, koszt na akceptację niedostępny przy zerze; realny rachunek | Limity wymagane zawsze przy płatnym generowaniu; rozbudowany widok po M10. |
| S25 | Owner dostaje powiadomienie o istotnym problemie instrukcji | **Cz — opt-inowe powiadomienia in-app, dedupe po queue item_id, wyciszenie na 24 h, dismiss i link do Needs review; email/chat pozostają niezintegrowane** | Test UI weryfikuje opt-in, listę problemów, mute i dismiss; brak auto-approve/publish | Najpierw dowód powrotu w kolejce M09, potem kanały zewnętrzne. |

### COULD — 15 opcji wymagających sygnału popytu

| ID | Use case | Stan / mapa | AC/DoD przed udostępnieniem | Warunek wejścia |
|---|---|---|---|---|
| C26 | Nowy użytkownik próbuje produktu na przykładowym repo | **K — demo izolowane + test**, rozszerzenie U4 | Wyraźne demo bez danych klienta i bez pozorowania jego wyniku; przejście do własnego repo | Uczestnicy potrzebują przykładu przed autoryzacją. |
| C27 | Użytkownik edytuje profil i zarządza powiązanymi metodami logowania | **K — profil zaimplementowany + testy**, U3/P01 + rozszerzenie | Zmiana nazwy utrzymana po powrocie; link pozostaje jawnie potwierdzanym flow providera, unlink i ochrona ostatniej metody są poza zakresem obecnego API | Minimum tożsamości i bezpieczny login M01 już działają. |
| C28 | Owner organizuje członków w grupy teamowe | **K — API, migracja, UI i test**, rozszerzenie U3 | Członkostwo/grupy rozróżnione od ACL; poprawne aktualizacje; test rzeczywistego teamu | Ręczne zarządzanie osobami jest mierzalnie uciążliwe. |
| C29 | Organizacja korzysta z enterprise SSO | ND, poza obecnym MVP | Zaufany IdP, logowanie/revoke/break-glass w uzgodnionej polityce; test klienta | Konkretny kupujący i finansowany zakres. |
| C30 | Organizacja automatycznie provisionuje konta przez SCIM | ND, poza MVP | Create/update/deactivate idempotentne, spójna revocation; audyt u klienta | Umowa wymagająca SCIM. |
| C31 | Owner eksploruje rozbudowaną mapę wiedzy | **K — mapa scopes/layers/relations i Pyramid UI są dostępne z klawiaturą** | Zadanie decyzyjne rozwiązane szybciej niż listą; keyboard/a11y/skalowanie | Badanie pokazuje, że mapa wspiera decyzję. |
| C32 | Developer używa trzeciego harnessa | **K — adapter instaluje Claude, Copilot i Gemini; Gemini ma jawny brak hooka i bezpieczny uninstall, testy instalatora** | Ten sam LOAD/revision/revoke/uninstall i zadanie jak M07/M08 | Partner rzeczywiście go używa. |
| C33 | Developer otwiera kontekst Guidefold rozszerzeniem Chrome | **K/Cz — MV3 popup otwiera bieżące repo GitHub w hosted flow, bez cookies/storage/tokenów; test statyczny** | Otwiera właściwe repo/scope; nie przechowuje tokenów; działający hosted flow | Mierzalnie skraca istniejący krok wejścia. |
| C34 | Team importuje repo z GitLaba | ND, rozszerzenie U1 | Ten sam manifest/scope/revoke i R/Q jak M04; działające repo partnera | Partner z potwierdzonym problemem nie używa GitHuba. |
| C35 | Developer korzysta z lokalnego/offline zestawu | **K — `scan --dry-run`, local manifest i CLI status działają bez publikacji** | Jawna wersja i ograniczenia świeżości/revocation offline; test bez sieci | Wymóg środowiska, nie optymalizacja na zapas. |
| C36 | Owner zaczyna od szablonu firmowej procedury | **K — `guidefold init` dostarcza szablon repo, hooków i CI bez publikacji** | Szablon wymaga własnych źródeł i walidacji; brak automatycznej publikacji | Powtarza się kilka wdrożeń tego samego workflow. |
| C37 | Owner importuje lokalną paczkę przez przeglądarkę | **K — browser manifest, limity, digest, raw blob upload, finalize, rejestracja repo, duplicate/secret path guard i testy** | Preview, limity, zip-slip/symlink/sekrety i retry; 4/5 kończy bez CLI | GitHub App ani CLI nie są dostępną ścieżką teamu. |
| C38 | Owner dołącza wiedzę z Confluence/Notion | ND, nowe źródło U1 | Scope/revoke/provenance i zasady retencji źródła; realny import bez wycieków | Wartościowa procedura istnieje wyłącznie poza Git. |
| C39 | Owner uruchamia cykliczny test jakości procedur | **K — template CI ma tygodniowy `scheduled-quality`, budżet lokalnego eval i artefakt z jawnym `unknown`** | Harmonogram, budżet, brak duplikatów i raport wersji; kontrola jednego przebiegu | Ręczne porównanie M10/S23 jest używane. |
| C40 | Owner przekazuje zadanie naprawcze do systemu ticketów | ND, rozszerzenie U9 | Jawny wybór celu, dedupe i backlink, odwołanie integracji; test roundtrip | Kolejka Guidefold działa, team pracuje w ticketach. |

### WON’T NOW — 10 świadomie odłożonych use case’ów

| ID | Use case odłożony | Stan / powód | Warunek ponownego rozważenia i przyszły odbiór |
|---|---|---|---|
| W41 | Użytkownik kupuje/sprzedaje skille na marketplace | ND; inny model produktu, problem podaży/popytu | Osobna decyzja o rynku i modelu; nie jest zależnością żadnego Must. |
| W42 | Team korzysta z własnego trenowanego modelu Guidefold | B; brak dowodu, że to obecny bottleneck | Dodatni wynik na niezależnych zadaniach klienta, koszt i utrzymanie lepsze od baseline. |
| W43 | Agent wykonuje dowolny workflow przez nowy silnik GraSP | B; nowy runtime i inna odpowiedzialność | Jedna procedura S20 dowodzi potrzeby, osobny ADR i verifier/sandbox/operacje. |
| W44 | System sam generuje, zatwierdza i publikuje instrukcje | B; odbiera kontrolę nad wiedzą | Osobna decyzja i niezależne dowody jakości; obecnie zawsze decyzja ownera. |
| W45 | System czyta wszystkie sesje pracowników i automatycznie uczy się skilli | B; brak potrzeby pełnych trace’ów, zakres danych | Potwierdzona potrzeba, polityka danych, minimalizacja i niezależny wynik; M09 zbiera minimum. |
| W46 | Buyer otrzymuje gwarancję bezbłędnego wykonania dzięki proof/grafowi | Nieuprawniona obietnica; hash nie dowodzi prawdy | Nie wraca w takiej formie; można zdefiniować wąski, sprawdzalny kontrakt gwarancji. |
| W47 | Developer zastępuje IDE pełnym edytorem w Guidefold | ND; duży koszt poza przepływem | Osobny udowodniony problem, którego Git/harness nie rozwiązuje. |
| W48 | Buyer sam zarządza rozbudowanym billingiem i marketplace payments | ND; samoobsługowy billing poza MVP | Po płatnych wdrożeniach i zmierzonym koszcie obsługi; obecna oferta 99 USD/org + BYOK zachowana jako plan. |
| W49 | Team wybiera regiony i korzysta z HA multi-region | ND; wyprzedza wymagania partnera | Płatny wymóg SLA/regionu, architektura i zmierzony failover. |
| W50 | Team dostaje ciągłe nowe warianty rankingu/piramidy przed działającym onboardingiem | B; zastępuje dowód wartości pracą badawczą | Najpierw M01–M10; potem ograniczony eksperyment rozstrzygający konkretny błąd klienta. |

## 7. Gdzie zmieniamy kierunek

| Obecna tendencja | Koszt dla klienta | Korekta |
|---|---|---|
| Frontend wygląda na gotowy, API nie startuje | Nikt nie przechodzi początku lejka | M01 przed dalszym redesignem. |
| Logowanie i podłączenie GitHuba mają wspólną akcję | Użytkownik wraca do loginu, repo nie jest podłączone | Oddzielne procesy identity i repo authorization M04. |
| Wizard kończy się statusem importu | Team nie wie, jak uruchomić instrukcję | M03 kończy się load i zadaniem. |
| Profil oznacza przejście do listy członków | Niejasne konto, rola i organizacja | Minimum profilu M01 i czytelny wybór org M02. |
| UI pokazuje job/digest/URN przed działaniem | Nowy owner musi nauczyć się implementacji | Prosty następny krok, szczegóły rozwijane. |
| Masowa ekstrakcja/piramida przed pierwszym użyciem | Koszt i review bez gwarantowanej potrzeby | Istniejące 10–20 skilli, jedna procedura; S18/S21 po aktywacji. |
| Więcej recall/loadów jako definicja sukcesu | Nie wiadomo, czy zadanie wymaga mniej poprawek | M10 mierzy wynik i pełny nakład. |
| Source-proof traktowane jak prawda lub obowiązkowy etap każdego importu | Fałszywa pewność albo ciągłe ASK na starszych pakietach | Rozdziel integralność, review i wykonanie; opt-in pozostaje jawny. |
| Rozbudowa raportów CI przed reakcją autorów | Powstaje powierzchnia do utrzymywania | S19 z bramką 10 realnych PR; bez reakcji redukcja. |
| Testy fixture i recenzje agentów zamykają gotowość UX | Brak dowodu samodzielnego wejścia | R/Q/P oraz 4/5 ludzi w konkretnych zadaniach. |

P08 był przesunięty na początek na polecenie właściciela 09-07. Nowa rekomendacja świadomie zmienia tę kolejność na podstawie obecnego zlecenia; nie przedstawia wcześniejszego wykonania jako samowoli. Zachowujemy przydatny kod. Nie proponujemy masowego refaktoru.

## 8. Kolejność wykonania i bramki

1. **Natychmiast:** M01 — naprawa konfiguracji WorkOS i stanu bramki; M02 — rzeczywisty invite/role/profile minimum. Backend developer/operator odpowiada za działającą domenę, frontend za ścieżkę. Kryterium: świeże konto i zaproszony member wchodzą do właściwej org.
2. **Potem:** M04 + M03/M05 — prawdziwe podłączenie GitHuba i wznowialny prosty import. Kryterium: owner bez CLI/YAML wybiera poprawny istniejący skill. Dostęp do GitHub App jest zależnością operacyjną, nie ekranem do zamockowania jako gotowy.
3. **Pierwsza wartość:** M06/M07/M08 — publikacja, pierwszy harness, realne zadanie. Drugi harness domyka M07 przed deklaracją cross-harness. M10 zbiera baseline od początku.
4. **Powrót i decyzja:** M09/M10 — zmiana źródła/feedback, poprawka i kolejne użycie; raport korzyści i rozmowa zakupowa.

WIP: jedno domykane pasmo użytkowe, bez rozpoczynania Could. Dziesięć Must nie oznacza dziesięciu mikroserwisów ani ekranów. Nie zmieniamy React/Go/Postgres, nie dokładamy silnika wykonawczego.

Obecne cele PRD pozostają widoczne: partner do **20.09**, 20 realnych sesji i drugi harness do **04.10**. To cele, nie nowa obietnica terminu dla 50 pozycji. Po diagnozie konfiguracji i GitHub App należy oszacować pozostały nakład. Brak partnera 20.09 uruchamia istniejącą decyzję o zatrzymaniu rozbudowy. Nie maskujemy tego kolejną funkcją.

Po 4 tygodniach od aktywacji: brak decyzji ownera → ograniczyć dashboard; jednorazowy import → sprawdzić jednorazową usługę; brak przewagi w zadaniu → zmienić workflow albo zamknąć hipotezę; brak postępu zakupowego → ograniczony czas rozmów z buyerem, nie automatyczne rozszerzenie backlogu.

## 9. Proponowane zmiany źródeł kanonicznych

Po wyborze tego zakresu aktualizujemy: PRD §1/§12a/§13 (aktywacja i wartość), U3 (profil/bramka/zaproszenia), U1/U4/U5 (browser-first wizard do zadania), backlog (kolejność M→P), PIVOT-IMPLEMENTATION (osobny status code/live/Q/P), pipeline UI (wpływ wyłącznie na zmienione etapy), API-CONTRACT/OpenAPI (brakujące operacje zgodnie z kontrakt-first). Rozszerzenia ról/repo ACL pozostają Should i nie wchodzą po cichu do bieżącej implementacji.

Rozbieżność: wcześniejszy nacisk P08/rozbudowa UI kontra obecne zlecenie wartości i wejścia teamów. Decyzja w tej pracy: kompletna propozycja 10 Must/50 MoSCoW z audytem. Dokumenty do przyszłej zmiany wskazano wyżej. Konsekwencja: prace badawcze i wizualizacje ustępują domknięciu aktywacji. Status: Proposed; nie dokonano wdrożenia, zakupu, konfiguracji providerów ani zmiany kontraktów.

## 10. Odbiór tego dokumentu

- Sprawdzono kod wskazanych ścieżek, aktualne raporty i produkcję read-only; odróżniono brak mechanizmu od niedziałającej konfiguracji oraz od braku dowodu.
- Przedstawiono dokładnie 10 Must z AC/DoD, 15 Should, 15 Could, 10 Won’t, razem 50; każdy wpis ma status i warunek odbioru lub ponownego rozważenia.
- Opisano ograniczenia badań i nieznane wyniki użytkowe. Progi są proponowane, nie przedstawione jako osiągnięte.
- Naprawiono repozytoryjny wiring logowania i publiczny stan UI; produkcyjny OAuth pozostaje niezaliczony do czasu konfiguracji WorkOS i wdrożenia.
- Walidacja dokumentu: 50 unikalnych ID, rozkład 10/15/15/10, 10 sekcji AC i 10 sekcji DoD, wszystkie względne odnośniki lokalne istnieją; `git diff --check` bez błędów. Końcowy przegląd product ownera: brak P1; wskazany P2 dotyczący browser-first ponownego sync poprawiony w M04.
