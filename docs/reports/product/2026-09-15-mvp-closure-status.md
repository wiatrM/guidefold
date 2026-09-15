# Stan repo i co zostało do domknięcia MVP — 2026-09-15

Status: raport stanu, przygotowany na polecenie właściciela („sprawdź aktualny stan repo, co nam zostało, żeby domknąć MVP, skonsultuj z PO/PM"). Data: 2026-09-15. Gałąź `main` @ `2a302f5` (2026-09-13 22:03), drzewo czyste.
Cel: jedna lista tego, co dzieli dzisiejszy kod i produkcję od MVP w rozumieniu [PRODUCT-PIVOT §13](../../PRODUCT-PIVOT.md) (Pilot Core do 2026-09-20, 20 sesji do 2026-10-04), [PIVOT-BACKLOG](../../PIVOT-BACKLOG.md) „Pilot Core" i [PRODUCT-FOCUS](../../PRODUCT-FOCUS.md) „The next four weeks" + „Kill criteria", z dowodem przy każdym twierdzeniu.
Wejścia: `git`/`gh` na `main`, gałąź `audit/2026-09-12-integration`, [audyt 2026-09-12](2026-09-12-assumptions-vs-implementation-audit.md) (tylko na tej gałęzi), `kubectl` w trybie odczytu na klastrze `cloudfloo-context` (deploymenty, ArgoCD Application, `SELECT count(*)` na bazie produkcyjnej), rejestr wydań `deploy/k8s/environments/cloudfloo-io/README.md`. Druga opinia PO/PM: Codex `gpt-5.6-sol`, read-only, sekcja 6.
Zakres zastępowania: brak; raport nie zmienia U1–U11, P01–P15 ani ADR. Etykiety R/Q/P wg [eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md).

## 1. Werdykt w czterech zdaniach

Kod i produkcja są technicznie sprawne: `main` zielony, ArgoCD `Synced/Healthy` na `main`, cztery deploymenty gotowe, logowanie Google działa. **Produkcja nie ma ani jednego importu, skilla, publikacji, tokenu adaptera ani zdarzenia telemetrii** (baza: `imports 0`, `skills 0`, `publications 0`, `tokens 0`, `gf.events 0`; są 2 organizacje, 2 użytkowników i 43 repozytoria zsynchronizowane przez GitHub App, z których jedno jest już zablokowane powodem `guidefold_yaml_missing`). Wszystkie dowody typu P z backlogu są otwarte, a decyzje właściciela z audytu 12.09 (partner = self-use, jeden backlog, ADR-0043/0044) **nie dotarły na `main`**: żyją w 12 commitach gałęzi `audit/2026-09-12-integration` bez PR-a. Do bramki kill (partner do **2026-09-20**) zostało 5 dni, do celu „20 realnych sesji + drugi harness" (**2026-10-04**) 19 dni; od audytu (27 PR-ów, #146–#172) praca poszła w konsolę, GitHub App i efekty wizualne, a licznik dowodów pilota nie drgnął.

## 2. Stan `main` i gałęzi

| Co | Stan | Dowód |
|---|---|---|
| `main` | `2a302f5`, czyste drzewo, `feat/org-scope-reads` wmerge'owany (#155) | `git status`, `git log` |
| Zmergowane od audytu 09-12 | 27 PR-ów #146–#172: GitHub App connect/install/PR report (#147–#151, #167), org scope (#155, #157–#159), device login + telemetria domyślnie on (#156, #163), WorkOS email verification (#154), production-is-sacred (#152), wizard/shadcn/efekty/Overview (#164–#172) | `gh pr list --state merged` |
| Otwarte PR-y | #173 rejestr wydania 09-13 (zielony, mergeable); #164 Overview na Spectrum Charts (zielony); #162 rejestr wydania duplicates (zielony, zastąpiony przez #173); #137 landing refresh (09-12); #134 deploy presentation (09-11, bez checków) | `gh pr view` |
| Gałąź `audit/2026-09-12-integration` | 12 commitów poza `main`, **brak PR-a**: audyt + ADR-0043/0044 (`77b80e8`), uzgodnienie docs (`12f8fa3`), `ascend.run` dla GitHub App (`d3489a0`), hero/README pod tezę 30 000 skilli (`7bdddc9`), Overview na Spectrum (`e296059`), decyzja o partnerze w PRODUCT-FOCUS | `git log main..audit/2026-09-12-integration` |
| P16 multi-repo (ADR-0042, `f268732`) | tylko na `worktree-agent-a8a0a403216669606`; na `main` ADR-0042 nadal **Proposed**, brak `repo_links` w `sql.go`; multi-repo istnieje na `main` w innej postaci (GitHub App: `github_installation_links`, import per repozytorium, duplikaty między repo #159) | `git branch --contains`, `grep repo_links` |
| Dokumenty na `main` | PRODUCT-FOCUS „Design partner": *To be filled*; PIVOT-BACKLOG kończy się na P15; PIVOT-IMPLEMENTATION datowany 09-09, kontrakt „1.1.1" przy realnym 1.13.0 *[korekta 2026-09-15: `docs/API-CONTRACT.md` podaje `contract_version: 1.13.0` z 2026-09-13; 1.12.0 to wcześniejszy wiersz changelogu]*; E6.7-PROTOCOL: `[PLACEHOLDER]` sha256 i data sign-off | `grep` |

## 3. Stan produkcji (`guidefold.cloudfloo.io`, odczyt 2026-09-15)

| Co | Wynik |
|---|---|
| ArgoCD `Application/guidefold` | `targetRevision: main`, `Synced`, `Healthy` |
| Deploymenty | api 2/2, ui 2/2, worker 1/1, portal 1/1; pody 37 h, 0 restartów; search `10636c30…`, worker `6295278d…`, ui `75898e20…` (wydanie `2a302f5`; rejestr w otwartym PR #173, nie w `main`) |
| Baza (`SELECT count(*)`) | orgs 2 (`main` 09-11, `maina` 09-13), users 2, memberships 2, **repos 43, imports 0, skills 0, publications 0, proposals 0, decisions 0, tokens 0, device_codes 0, gf.events 0** |
| `gfm.repos.import_blocked_reason` | 42 bez powodu (import nigdy nie próbowany), **1 × `guidefold_yaml_missing`** |
| Znany defekt | logowanie GitHub kończy się w WorkOS `oauth_failed` („Error fetching GitHub profile"): GitHub App bez uprawnienia „Email addresses: Read-only"; czeka na sudo właściciela (rejestr wydań, wpis 09-13) |

Wniosek: **nikt nie zaimportował, nie opublikował ani nie użył niczego na produkcji.** Każde „działa" w tym repo jest dziś dowodem R (testy, acceptance na stosie lokalnym), nie P.

## 4. Co zostało do MVP

Definicja (PRD §13): do 09-20 Pilot Core = Google/GitHub login, org, skan/import wybranego repo, lista/źródła/trzy osie, jedna ograniczona propozycja ekstrakcji i wspólnego elementu, Git roundtrip, jeden działający adapter SEARCH/USE, load i feedback. Do 10-04: ≥20 realnych sesji osoby niebudującej Guidefolda, każda z SEARCH **i** LOAD w ledgerze, drugi wspierany harness, podstawowy drift, tygodniowy raport per skill u nazwanego ownera i pierwsza zapisana decyzja.

### 4a. Ścieżka krytyczna (bez tego MVP nie jest domknięte)

| # | Do zrobienia | U/P · persona | Dowód odbioru | Stan dziś |
|---|---|---|---|---|
| 1 | **Partner i kalendarz sesji do 09-20**: decyzja z 09-12 (self-use w org `cloudfloo`) zapisana na `main` z polami, których wymaga PRODUCT-FOCUS „Design partner": repo, **developerzy** (≥1 osoba, która nie budowała Guidefolda), owner skilli, polityka danych, data startu; plus problem, buyer, budżet i warunki rozmowy płatnej (PRD §13). Zamknąć #78 | §13 PRD · właściciel | wiersz bez „to be named"; dowody etykietowane `self-use` | decyzja tylko na gałęzi audytu; drugie repo „jeszcze nie wiem"; brak nazwanego developera |
| 2 | **Bezpieczeństwo przed danymi partnera** (PRD §13: izolacja dwóch org, odwołanie dostępu, walidacja publikacji, poprawność rewizji) — testy R są (`multitenant_test.go`, 403 cross-org, live e2e odwołania 0,02 s); brakuje jednego zapisu przebiegu na produkcji z dwoma org (`main`, `maina` już istnieją) | U3 · operator | wpis w rejestrze wydań: podmiana org A→B daje 403/404, odwołanie maskuje w ≤25 s | R zielone; P nieudokumentowane |
| 3 | **Pełny Pilot Core na produkcji własnymi rękami** (smoke ACT-01 wewnętrzny): login Google, org `cloudfloo`, import `wiatrM/guidefold` przez GitHub App, **Library z listą/źródłami/trzema osiami**, **jedna ograniczona propozycja ekstrakcji i jednego wspólnego elementu** (generator deterministyczny wystarczy), **Git roundtrip** (`proposals apply` → PR → sync), publikacja snapshotu | U1/U2/U4/U5 · owner | w bazie prod `imports ≥ 1`, `skills > 0`, `proposals ≥ 1`, `decisions ≥ 1`, `publications ≥ 1`; PR w repo; wpis w rejestrze z request_id | 0; blokery: uprawnienie e-mail GitHub App (jeśli owner loguje się GitHubem) i wymóg `guidefold.yaml` (sekcja 7) |
| 4 | **Zapis live login** (U3 AC1–2, M01/M02): świeże konto Google i GitHub, powrót do tej samej tożsamości, zaproszenie, odwołanie | U3/P01 · owner + zaproszony | raport z datą, kontami testowymi, request_id; U3-1 w acceptance przestaje być `not_measured_here` | Google działa (302, 2 użytkowników), GitHub zepsuty, przebieg nieudokumentowany |
| 5 | **Sesja zewnętrzna ACT-01 przed 09-20, jeden harness**: osoba spoza zespołu, Claude Code `guidefold install` + device login do produkcji, realne zadanie, SEARCH → USE → `context_loaded` → feedback → decyzja ownera w kolejce | U5/U6 · P10/P11 · developer + owner | wiersze w `gf.events` i `gfm.tokens`; U5-4, U6-6 w acceptance jako pass | 0 tokenów, 0 zdarzeń |
| 6 | **Drugi harness sprawdzony technicznie teraz** (PIVOT-BACKLOG: „możliwości drugiego sprawdzamy w pierwszym etapie"): Copilot CLI `find`/`load` w jednej realnej sesji z uczciwymi ograniczeniami (#82) | U5 · developer | wpis w matrycy adapterów z dowodu sesji (#83) | szablony są, sesji nie było |
| 7 | **20 sesji do 10-04**, każda z SEARCH i LOAD w ledgerze (PRODUCT-FOCUS: „a search and a load for each of them") | U5/U6 · developer | zapytanie do `gf.events` grupujące po sesji: ≥20 sesji z oboma zdarzeniami | 0 |
| 8 | **Tygodniowy raport per skill u ownera + 1 decyzja** (#91, #95; U6) | U6/P11 · owner | raport z datą i zapisana decyzja (sprawdzono / poprawiono w Git / bez zmiany z powodem) | narzędzia są (`/usage/export`, kolejka), nikt nie dostał raportu |
| 9 | **Podstawowy drift P13** (PRD §13: „U9 jest częścią podstawowej pętli powrotu"): zmiana źródła w repo → `needs_review` w kolejce → decyzja | U9/P13 · owner | jeden przypadek na produkcji z datą | R zielone (ACC 09-08), P brak |
| 10 | **Minimalna rubryka P15 od pierwszego tygodnia**: `docs/pilot/PIVOT-RUBRIC.md` z nazwanym buyerem, progami go/no-go i miejscem zapisu wyniku; nie E6.7 | U11/P15 · product | rubryka z datą i nazwiskiem; pierwszy ręczny raport `pivot_report.py` po tygodniu | rubryka istnieje bez buyera i bez przebiegu |

### 4b. Poza ścieżką krytyczną (zrobić, ale nie kosztem 4a)

| # | Co | Powód odłożenia |
|---|---|---|
| 11 | PR z gałęzi audytu na `main` (ADR-0043/0044, raport, PIVOT-IMPLEMENTATION, jeden backlog) — **oprócz** sekcji „Design partner", która wchodzi w pkt 1 | prawda dokumentów, nie dowód użycia; PO/PM: „minimalny zapis decyzji pilota, nie szeroki merge" |
| 12 | E6.7: wypełnić placeholdery **albo** zapisać w `docs/pilot/README.md`, że E6.7 (3 zespoły, 20–40 par zadań) jest po MVP | PRD §13 opisuje E6.7 jako osobny eksperyment; nie blokuje zdania z PRODUCT-FOCUS |
| 13 | P16 multi-repo (ADR-0042) i drugie repo `cloudfloo` | kanon mówi o jednym monorepo partnera; multi-repo w postaci GitHub App już jest na `main`; decyzja po ACT-01 |
| 14 | `ascend.run` na produkcji (ADR-0036, `d3489a0`) | pyramid w CI klienta, nie ACT-01 |
| 15 | Higiena PR: zmergować #173 i #164, zamknąć #162, odświeżyć albo zamknąć #137 i #134; **żadnej nowej rundy UI** (audyt PRIO 4) | porządek, nie dowód |

## 5. Kolejność (5 dni do bramki, 19 do celu)

1. **Dziś, 09-15**: pkt 1 — nazwać developera spoza zespołu i termin jego sesji; wpisać partnera na `main` (mały PR z samą sekcją PRODUCT-FOCUS). Równolegle decyzja z sekcji 7 (`guidefold.yaml`) i uprawnienie e-mail w GitHub App, bo blokują pkt 3.
2. **09-16 → 09-17**: pkt 3 i 2 na produkcji własnymi rękami (pełny Pilot Core + zapis izolacji/odwołania), pkt 4 (zapis logowania). Dziennie jeden wpis w rejestrze wydań.
3. **09-18 → 09-20**: pkt 5 (sesja zewnętrzna Claude Code) i pkt 6 (Copilot CLI technicznie). Jeden wiersz w ledgerze wart jest więcej niż kolejny ekran.
4. **09-21 → 10-04**: pkt 7 w rytmie dziennym, pkt 8 co tydzień, pkt 9 i 10 w pierwszym tygodniu; 4b w wolnych oknach.

## 6. Druga opinia PO/PM (Codex `sol`, read-only, 2026-09-15) i jak ją przyjęto

| Ustalenie Codex | Przyjęte? | Skutek w raporcie |
|---|---|---|
| Lista niepełna: brak jawnego sprawdzenia listy/źródeł/trzech osi, ograniczonej ekstrakcji, wspólnego elementu i Git roundtripu (PRD §13:354, PIVOT-BACKLOG:31); brak P13 drift i wczesnej rubryki/buyera P15 (PIVOT-BACKLOG:33); „ledger z 20 sesjami" za słaby — każda sesja SEARCH i LOAD (PRODUCT-FOCUS:99); rekord partnera musi mieć developerów i politykę danych (PRODUCT-FOCUS:120) oraz problem/buyera/budżet (PRD §13:366) | tak | pkt 3 rozpisany na kroki Pilot Core; nowe pkt 9 i 10; pkt 7 z warunkiem SEARCH+LOAD; pkt 1 z polami partnera |
| Wyciąć z krytycznej ścieżki: szeroki merge 12 commitów/ADR/P16, placeholdery E6.7, P16/multi-repo, porządki PR; nie wycinać P13 ani minimalnej rubryki P15 | tak | przeniesione do 4b |
| Kolejność zła: dziś partner i kalendarz sesji, nie PR dokumentacyjny; potem bezpieczeństwo przed danymi partnera (PRD §13:360), wewnętrzny smoke ACT-01, sesja zewnętrzna przed 09-20; drugi harness technicznie teraz, nie po 09-21 | tak | sekcja 5 przepisana |
| **Najwyższe ryzyko**: self-use na `wiatrM/guidefold` uznany za design partnera; kanon opisuje self-use tylko jako oznaczony fallback po niespełnionej bramce (PRODUCT-FOCUS:110); można zebrać 20 zdarzeń i nie dowieść celu rynkowego | tak, z zastrzeżeniem | decyzja o self-use należy do właściciela i zapadła 09-12; raport wymaga etykiety `self-use` na każdym dowodzie i nazwanego developera spoza zespołu; to nie jest dowód popytu ani płatności (PRD §13: „zainteresowanie, bezpłatne używanie i płatne zobowiązanie są odrębnymi dowodami") |

## 7. Pytanie właściciela z 2026-09-15: czy `guidefold.yaml` musi istnieć?

Właściciel: „nie podoba mi się mus tworzenia guidefold.yaml". Stan faktów:

| Kto czyta `guidefold.yaml` | Po co | Czy da się bez |
|---|---|---|
| CLI `repo_root()`/`load_map()` (`scripts/guidefold:73–95`) | root repo, `publisher`, `nodes` (scope → `paths`, `owner`), `search.url/backend/deadline_ms`, `registry.*`, `router.weights`, `eval.queries` | root = git toplevel już jest fallbackiem; `nodes` można wywieść; `search.*` i `registry.*` należą do logowania/serwera, nie do repo |
| Hook (`cmd_hook`) | **nie czyta** — `nodes.json` z artefaktu indeksu (E1.5) | bez zmian |
| Worker `tools/worker/build_tree.py:150` | twardy błąd `import_tree_has_no_guidefold_yaml`; importer blokuje repo `guidefold_yaml_missing` | to jest **ostrzejsze niż PRD**: U1 mówi „guidefold.yaml ma pierwszeństwo; katalogi i CODEOWNERS dostarczają propozycji, jeśli mapy brak" (PRODUCT-PIVOT:69) |
| GitHub App `ghapp/content.go:118` | pobiera go razem ze `**/.agents/skills/**/SKILL.md` | opcjonalny |
| URN `urn:skill:<publisher>:<node>:<name>` | `publisher` i nazwa węzła | `publisher` = slug organizacji z konta; węzeł z inferencji (ryzyko: zmiana nazwy katalogu zmienia URN — dziś też, chyba że alias) |
| `gfm.scopes.source` | dziś zawsze `'guidefold_yaml'` | kolumna już przewiduje inne źródła |

Odpowiedź: **nie musi**. Nic w hot path go nie potrzebuje, a PRD już przewiduje tryb bez mapy; wymóg wprowadził kod builder-a i importera. Na produkcji jedno z 43 repozytoriów jest już zablokowane tym powodem, więc wymóg leży na ścieżce krytycznej pkt 3.

Propozycja (do decyzji właściciela, potem ADR, bo zmienia „Naming" w CLAUDE.md i U1):

1. **Zero-config domyślnie, ta sama konwencja co AGENTS.md („nested, nearest wins")**: węzeł = każdy katalog, w którym leży `.agents/skills/` (albo `.claude/skills/`, `.github/instructions/`), nazwa = ścieżka z `/` → `.`, `paths = ["<katalog>/**"]`, `_root` niejawny; owner z CODEOWNERS (najdłuższe dopasowanie; parser już jest w CLI). Zapis w `gfm.scopes.source = 'inferred'`, widoczny w Map → Scopes z etykietą „wywnioskowany", jak dziś `knowledge_layer: inferred` w P08.
2. **Mapa scope'ów po stronie serwera dla ścieżki GitHub App**: owner poprawia węzły i ownerów w konsoli (source `'console'`), a CLI i worker dostają `nodes` ze snapshotu, który już je niesie. Repo klienta zostaje czyste; spójne z ADR-0047 (organizacja jako domyślny zakres) i z ADR-0042 (repo „tylko skille" dla innych repozytoriów).
3. **`guidefold.yaml` zostaje wyłącznie jako opcjonalne nadpisanie** (aliasy przy rename, inny owner, niestandardowe ścieżki); `doctor` mówi „wywnioskowano N scope'ów; dodaj guidefold.yaml tylko, jeśli mapa jest błędna". `search.*`/`registry.*` wychodzą z pliku do `guidefold login` i ustawień organizacji.
4. Sygnały pomocnicze (nie wymagane pliki): `pnpm-workspace.yaml`, `go.work`, `Cargo.toml [workspace]`, Nx/Turbo `project.json`, Bazel `BUILD` — tylko jako kandydaci węzłów, gdy katalog skilli nie rozstrzyga.

Koszt pierwszego kroku (1 + 3): fallback w `build_tree.py` i `load_map()` (synteza `cfg` z drzewa + CODEOWNERS), zdjęcie `guidefold_yaml_missing` w importerze, komunikat `doctor`, testy na fixture bez pliku; kontrakt bez zmian poza wartością `source`. Ryzyko: stabilność URN przy zmianie katalogu — dziś to samo ryzyko istnieje bez wpisu `aliases`, więc reguła „rename trafia do review" (U1 AC5) pozostaje jedynym zabezpieczeniem.
