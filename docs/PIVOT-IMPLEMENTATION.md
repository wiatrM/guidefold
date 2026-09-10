# Stan implementacji pivotu

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument spisuje,
co jest zaimplementowane i przetestowane w kodzie na dany dzień; nie zastępuje PRD, architektury
ani backlogu i sam w sobie nie jest dowodem pilota (R/Q, nie P — patrz
[eval-evidence-rules](../.agents/skills/eval-evidence-rules/SKILL.md)).

**Status: implementacja w toku, niecommitowana. Data: 2026-09-09 (czwarta aktualizacja: real-repo
test poza fixture Meridian znalazł i tej samej sesji naprawił realny defekt, ACC 41/41 bez fail).**
Cel: jeden przegląd stanu historii P01–P15 wobec kodu, testów i kontraktu, żeby decyzje przed
pilotem (§h) nie wymagały ponownego przeszukiwania repozytorium.
Wejścia: [PRODUCT-PIVOT](PRODUCT-PIVOT.md), [PIVOT-ARCHITECTURE](PIVOT-ARCHITECTURE.md),
[PIVOT-BACKLOG](PIVOT-BACKLOG.md), [API-CONTRACT](API-CONTRACT.md) (`contract_version` 1.1.1).
Zakres zastępowania: brak — dokument uzupełnia backlog o stan implementacji, nie zmienia wymagań
ani kolejności.

## a) Środowisko wykonawcze

Go 1.27.1 pod `~/.cache/guidefold/toolchain/go/bin`; PostgreSQL 18 (binaria `initdb`/`pg_ctl`/`postgres`)
pod `~/.cache/guidefold/toolchain/pg18/bin`. `tools/dev/pg.py` uruchamia instancję Postgresa bez
roota (`--auth=trust`, katalog danych per nazwa). `tools/dev/stack.py` buduje `guidefold-search` i
uruchamia `migrate`/`serve`/`worker` (opcjonalnie `pnpm dev` dla UI) nad tą instancją — bez Dockera
i bez sudo. Docker pozostaje potrzebny tylko do budowy obrazów kontenerów (`Dockerfile`,
`Dockerfile.worker`) i do profilu ParadeDB (`tools/search_service/dev.py`), nie do tej pętli
deweloperskiej. Profil domyślny to plain Postgres: migracje przechodzą bez `pg_search` i bez
`pgvector` (`CREATE EXTENSION` w bloku wyjątku), a domyślny silnik `router` czyta
`gf.router_terms` i nie wymaga żadnego z tych rozszerzeń (ADR-0033 pkt 4).

## b) P01–P15: co jest zaimplementowane

Status opisuje kod i testy, nie dowód pilota — żaden wiersz nie jest „done" w sensie
[definition-of-done](../.agents/skills/definition-of-done/SKILL.md) („done = used"); brak pilota
jest w kolumnie Uwaga.

| P | Moduł / pliki | Testy | Status | Uwaga (brak dowodu pilota) |
|---|---|---|---|---|
| P01 | `internal/identity` (sesje, tokeny, WorkOS+dev provider), CLI `login`/`org` | UT/API (`identity/api_test.go`, `TestWorkOSDeploymentExchangesTheCode`), CLI (`test_pivot_cli_import.py`) | zaimplementowano + testy | prawdziwe poświadczenia WorkOS niekonfigurowane |
| P02 | `internal/mgmt` (`Authorize`/`AuthorizeRepo`), bramka 1: `principal.go`, `catalog_cache.go` | UT/API (`mgmt` testy 403 cross-org, `multitenant_test.go`) | zaimplementowano + testy | brak |
| P03 | CLI `guidefold scan`, manifest v1 + sugestie | UT (`test_pivot_cli_scan.py`) | zaimplementowano + testy | tylko fixture Meridian, brak realnego repo partnera |
| P04 | `internal/importer` (`imports.go`, `blobs.go`, `parse.go`, job `import.parse`) | UT/API (`importer` testy, `drift_test.go`), CLI (`test_pivot_cli_import.py`) | zaimplementowano + testy | brak |
| P05 | `internal/knowledge` (`skills.go`, `maps.go`, `revisions.go`) | UT/API, UI (`LibraryRoute.test.tsx`, `MapRoute.test.tsx`) | zaimplementowano + testy | p95 przy 10k skilli w sieci pilota niezmierzony (U4 AC2, §h) |
| P06 | `internal/review` (`generate.go`, `plan.go`, `generator/{deterministic,remote,markdown}.go`) | UT/API, UI (`ImportRoute.test.tsx`) | zaimplementowano + testy | brak próby z realnym LLM i kosztem na próbce |
| P07 | `internal/review` (`approve.go`, `export.go`) | UT/API, UI (`ProposalsRoute.test.tsx`) | zaimplementowano + testy | brak |
| P08 | `internal/review` (kind `consolidation` grupowany po scope nadrzędnym, `consolidation_sources_insufficient`, `profile: one_shot`), `internal/review/generator` (`layer.go`: wnioskowanie `knowledge_layer` — 5 reguł, `origin: inferred`, nadpisywalne przez ownera na `origin: human`; `refines` w obu kierunkach), `internal/graph` (acykliczność), `family12.go` (addytywne `family` w 1.2, dowiedziony bit-identyczny ranking), CLI `guidefold extract --all [--personal ...]` (jedna komenda „scan → import → plan one_shot → generate wszystkich rodzajów") | UT (`generator/consolidation_test.go` na zaplantowanym fixture — dwa runbooki ze wspólną procedurą + jeden językowo podobny, poprawnie odrzucony jako `contradictory_steps`; `review/oneshot_test.go`, `review/p08_test.go`, `family12_test.go`), ACC (`test_p08_pyramid.py`, przechodzi na żywym stosie: 30 grup w trybie one-shot vs 15 domyślnie, jeden wspólny element z `derived_from`/`refines` do obu źródeł), UI (Map → Pyramid: pasma Abstract/Task/Atomic zamiast płaskiej listy, rodzic przez `refines` pokazany inline, rozwijalne „N specjalizacji") | zaimplementowano + testy | UI nie czyta jeszcze addytywnego pola `family` z odpowiedzi 1.2 (to pole służy agentom/adapterom, nie przeglądarce — Map/Pyramid już renderuje ten sam graf przez `/map/layers` i `/map/relations`, więc funkcjonalnie równoważne); real-repo (`wshobson/agents`, 183 skille, poza fixture Meridian, 2026-09-08 §h) potwierdził propagację hierarchii i uruchomienie mechanizmu konsolidacji na żywo, ale det-1 abstynował na wszystkich grupach (`too_few_procedures`) — ten korpus jest dokumentacją referencyjną, nie runbookami, więc to trafny werdykt generatora, nie luka; `GET /health/ready` ogłasza `"1.2"` od 2026-09-08 (naprawione tej sesji) |
| P09 | `internal/review` (`publication.go`, snapshot), bramka 3: `publisher.go`, `publication_test.go` | UT/API, UI (aktywacja z powodem w Proposals) | zaimplementowano + testy | brak |
| P10 | CLI `install`/`uninstall`, trzy harnessy (Claude Code, Copilot CLI, Gemini CLI) | UT (`test_pivot_cli_install.py`) | zaimplementowano + testy | poza zasięgiem tej sesji: realne sesje harnessów na repo partnera (ACT-01 live) |
| P11 | `internal/usage` (`export.go`, `health.go`, `queue.go`) oraz `ExecutionMetrics` (task success, harness errors, SEARCH/USE/ASK, tokeny, czas) | UT/API, UI (`UsageRoute.test.tsx`) | zaimplementowano + testy | brak |
| P12 | CLI `guidefold report`/`validate` (sprzed pivotu, współdzielone) | UT (`test_report.py`) | zaimplementowano + testy (mechanizm) | dowód „10 realnych PR-ów" to dowód pilota, niezmierzony |
| P13 | `importer/drift_test.go` (`source_changed`/`source_removed`), `usage` (`negative_feedback`/`zero_loads`), `gfm.owner_queue` | UT/API, ACC (`test_act01_end_to_end.py`, U1.5/U9 partial-scan-never-implies-removal, pass 2026-09-08) | zaimplementowano + testy | 2026-09-08: znaleziono i naprawiono realny false-positive w "brak false deletion przy partial" — nie w drifcie samym (poprawny), lecz w `candidatePath()` generatora (§b P08, §i) wypychającym ekstrahowany skill pod złą ścieżkę, którą importer poprawnie (dla siebie) czytał jako inną tożsamość i archiwizował starą |
| P14 | `internal/knowledge` (strona modułu) | UT/API | częściowo | scenariusz „5 zadań, potwierdzone ponowne użycie" to dowód pilota, poza zasięgiem tej sesji |
| P15 | `tools/pilot/pivot_report.py`, `tools/pilot/analyze.py`, `docs/pilot/PIVOT-RUBRIC.md` | UT (`test_pivot_report.py`, `test_pilot_analyze.py`) | zaimplementowano + testy (narzędzie) | poza zasięgiem tej sesji: rzeczywisty przebieg pilota z partnerem (patrz [PIVOT-REVIEW](PIVOT-REVIEW.md)) |

## c) Mapa modułów Go i właściciel tabel (wg API-CONTRACT §7)

| Moduł | Właściciel danych |
|---|---|
| `identity` | `gfm.users`, `identities`, `orgs`, `memberships`, `invitations`, `sessions`, `tokens`, `device_codes`, `auth_states`, `audit` |
| `mgmt` | brak własnych tabel — routing, envelope, CSRF, idempotencja (`gfm.idempotency`) |
| `jobs` | `gfm.jobs` (enqueue/lease/heartbeat/checkpoint, fencing po `generation`) |
| `worker` | brak własnych tabel — uruchamia handlery innych modułów poza HTTP |
| `schema` | DDL dla `gf` i `gfm` (migracje), rola `guidefold_api` |
| `testdb` | brak — harness testowy (jedna baza Postgres per proces testowy) |
| `importer` | `gfm.repos`, `blobs`, `imports`, `import_files` |
| `knowledge` | czyta `gfm.skills`, `skill_revisions`, `skill_resources`, `scopes`; zapisuje `judgment` do `gf.events` |
| `review` | `gfm.proposals`, `proposal_fields`, `decisions`, `exports`, `publications`, `relations` |
| `usage` | projekcja `gfm.owner_queue`, `adapter_health`; czyta `gf.events` |
| `graph` | brak własnych tabel — reguły acykliczności nad `gfm.relations`/`gf.snapshots` |
| `pivottest` | brak — harness Postgres + router + fixture Meridian |

## d) CLI: nowe komendy

| Komenda | Testy |
|---|---|
| `scan` | `tests/test_pivot_cli_scan.py` |
| `login`/`logout`, `org list`/`use` | `tests/test_pivot_cli_import.py` |
| `import`/`sync`/`status` | `tests/test_pivot_cli_import.py` |
| `install`/`uninstall` | `tests/test_pivot_cli_install.py` |
| `proposals list`/`show`/`apply` (walidacja ścieżki eksportu przeciw path traversal) | `tests/test_pivot_cli_import.py` |
| `doctor` (rozszerzenie sieciowe) | `tests/test_doctor.py` |
| `report --base <ref>` (P12, deterministyczny diff skilli w CI; błędy struktury blokują, kolizje triggerów ostrzegają, przykłady retrievalu nigdy nie blokują) | `tests/test_report.py` (20) |
| `procedure <SKILL.md> [--run]` (S20, kontrakt wejść/wyjść/warunków/kroków/weryfikacji i jawny lokalny verifier) | `tests/test_procedure.py` |
| `extract [--all] [--personal claude,codex,copilot]` (P08 one-shot: scan → import → plan `profile=one_shot` → generate wszystkich rodzajów; `--personal` wymusza `publish:false`) | `tests/test_pivot_cli_extract.py` (21) |

## e) UI: tryby i siedem widoków

Tryb `fixture` (domyślny) i `api` (`VITE_GUIDEFOLD_API` lub `?mode=api`) przez abstrakcję
`DataSource` (`FixtureDataSource`/`ApiDataSource`); sześciostanowy model routingu obejmuje
`restricted`/`degraded`. Wszystkie siedem widoków (Import, Library, Map, Skill, Proposals,
Usage & quality, Organization) ma testy Vitest i jest pokryte przez `ui/e2e/api-mode.spec.ts`
(Playwright ze `page.route` — stub, nie prawdziwe API). Klient trzyma `RamCache`
(`ui/src/api/cache.ts`, namespacing user/org/repo/policy, bez `localStorage`) i
`AccessController` (`ui/src/api/access.ts`, `/me` co najwyżej co 25 s, maskowanie po 45 s,
timeout 5 s), zgodnie z opisem w [ui/README](../ui/README.md).

Usage & quality zawiera także opt-inowy panel powiadomień właściciela: alerty są deduplikowane po
`owner_queue.item_id`, można je wyciszyć na 24 godziny lub odrzucić lokalnie, a każdy alert prowadzi
do istniejącej kolejki decyzji; nie ma automatycznej akceptacji ani publikacji.

Na początku widoku Usage & quality znajduje się panel **Decision scorecards**. Cztery karty pokazują
obserwowany sukces zadań, liczbę zatrzymań `ASK` i błędów harnessu, przepływ `SEARCH → USE` oraz
tokeny i średnie opóźnienie. Karty są kierunkowymi sygnałami dla organizacji; brak danych jest
wyświetlany jako `Unknown`, nigdy jako zero.

„Playwright live" (prawdziwa przeglądarka wobec działającego Go API + Postgres) **istnieje i
przechodzi**: `ui/playwright.live.config.ts` + `ui/e2e/live/*.spec.ts` (`pnpm test:e2e:live`,
25/25) uruchamiają przeglądarkę przez `pnpm dev` z proxy `/api`+`/v1` → `127.0.0.1:8765`
(same-origin — problem CORS obszedł się przez proxy, nie przez nagłówki po stronie API), logowanie
przez formularz dev-providera, cały przepływ import→library→skill→proposals(409 na nieaktualną
rewizję)→usage→organization→audyt klawiaturą i axe na siedmiu widokach. Zmierzono realnie: token
odwołania członkostwa działa natychmiast na API (0,02 s), UI maskuje dane po odświeżeniu `/me`
(25,4 s — cykl 25 s, nie SLA).

Po sesji audytu UX (2026-09-07, patrz niżej) trzy niezależne przebiegi naprawcze objęły
Import/Organization, Map/Usage & quality (w tym prawdziwe komponenty Spectrum Charts dla ekspozycji/ładowań i
rozkładu ocen, renderowane wyłącznie przy niezerowych danych) i Library/Skill/Proposals — 23
zweryfikowane znaleziska źródłowe (interaktywność, grupowanie, progresywne ujawnianie,
odkrywalność), wszystkie naprawione. Stan po naprawach: `pnpm test` 297/297, `pnpm test:contracts`
0 diagnostyk, `pnpm test:e2e` 33/33 (fixture), `pnpm test:e2e:live` 25/25 (API na żywo).

## f) Kontrakt

`contract_version` 1.1.1, data 2026-09-07 (od 1.0.0 do 1.1.1 w toku tej sesji: nagłówki
`X-Guidefold-Org`/`X-Guidefold-Repo` dla SEARCH/USE, `member_exists`, retencja blobów, jeden
rodzaj joba `proposal.generate`, DTO planu/importu, `family`/`profile: one_shot`, `card_revision`,
`activate` z wymaganym `reason`). Zasada „kontrakt przed kodem" (API-CONTRACT §1): handler,
tabela, migracja, DTO i komenda CLI zmieniają się wyłącznie razem ze zmianą kontraktu w tym samym
PR. Egzekwuje `tools/contract/check_api_contract.py` — stan na koniec sesji: **0 dryfu**, 17 not
informacyjnych (endpointy jeszcze nie w OpenAPI, kody błędów bez literału w Go).

## g) Komendy weryfikacyjne

```sh
# Go (wymaga Postgresa; GUIDEFOLD_REQUIRE_PG=1 zamienia brak binariów w błąd, nie cichy skip)
export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH
export GOPATH=$HOME/.cache/guidefold/gopath GOMODCACHE=$GOPATH/pkg/mod GOCACHE=$HOME/.cache/guidefold/gocache
export GUIDEFOLD_REQUIRE_PG=1
go vet -C services/search ./... && gofmt -l services/search && go test -C services/search -race -count=1 ./...

# CLI / kontrakt / dokumentacja
rtk proxy python3 -m pytest tests --ignore=tests/acceptance -q
python3 tools/contract/check_api_contract.py

# UI (fixture)
cd ui && pnpm build && pnpm test && pnpm test:contracts && pnpm test:e2e

# Warstwa akceptacyjna na realnym stosie (Go + Postgres + worker)
GUIDEFOLD_ACCEPTANCE=1 rtk proxy python3 -m pytest tests/acceptance -q

# UI wobec realnego API (przeglądarka, nie stub)
python3 tools/dev/stack.py up --name dev --generator deterministic
cd ui && pnpm test:e2e:live

# Stos lokalny do ręcznej próby (API-mode w przeglądarce)
python3 tools/dev/stack.py up --name dev --ui   # potem: seed --name dev --org acme --repo meridian
```

## h) Znane luki i decyzje właściciela przed pilotem

1. **WorkOS.** Kod i testy gotowe (`identity.ModeWorkOS`, fail-closed bez `GUIDEFOLD_AUTH`
   ustawionego jawnie); brak konta/kluczy dla realnego pilota — dev provider zastępuje go lokalnie.
2. **Repo partnera.** Brak zatwierdzonego repo i zakresu danych — P03/P06/P08 dotąd tylko na
   fixture Meridian, choć proces (scan→import→extract→consolidate→publish) przeszedł end-to-end
   na żywym stosie z prawdziwym Postgresem (patrz §i).
3. **Obraz workera niezbudowany.** `Dockerfile.worker` i szablon Helm
   (`deploy/k8s/chart/templates/worker.yaml`, bez Service) istnieją i przechodzą 39 testów
   statycznych; w tym środowisku nie ma Dockera, więc `docker build` nigdy nie uruchomiono
   naprawdę — zweryfikować przed pierwszym wdrożeniem.
4. **U4 AC2** (p95 ≤ 2 s przy 10k skilli w sieci pilota) — zmierzono lokalnie na syntetycznych
   10 026 skillach: p95 104,5 ms; to dowód lokalny/loopback, nie dowód sieci pilota.
5. **U4 AC5** (≥4/5 osób kończy import→znalezienie źródła→propozycję→Git→publikację) i pozostałe
   dowody P (P10 realne sesje harnessów, P12 10 realnych PR-ów, P14 5 zadań, P15 raport pilota,
   U2 AC4 recenzja 30 propozycji przez dwóch ludzi) wymagają prawdziwych ludzi i partnera;
   recenzja agenta i fixture ich nie zastępują.
6. **Znane defekty produktu naprawione w tej sesji** (nie tylko luki dowodowe): worker bez
   uprawnień zapisu do katalogu (brak `PGUSER=postgres` operatora), `guidefold telemetry flush`
   bez bearer tokenu, publikacja nadpisująca `needs_review` ustawione przez drift tego samego
   importu, dwie przestrzenie rewizji w `/usage` (naprawione jednym polem `card_revision`),
   `--personal` mogące opublikować prywatne skille organizacji, obcięcie sąsiadów w konsolidacji
   gubiące całe sąsiednie scope'y, path traversal w `guidefold proposals apply --write`.

## i) Dowody akceptacyjne

**Stan na 2026-09-08, po naprawie.** Raport: [`.guidefold/checks/acceptance-2026-09-08.json`/`.md`]
(../.guidefold/checks/) (niecommitowane, gitignored — lokalny artefakt przebiegu, napisany poprawnie
przez sesyjny `report` fixture przy tym przebiegu — wcześniejsza w tej samej sesji trójka przebiegów,
w trakcie których fixture nie zapisywał pliku, pozostaje nieustaloną, osobną usterką narzędzia raportowania,
nie odtworzoną przy tym czystym przebiegu). **Wynik: 41 wierszy — 34 pass, 0 fail, 7
`not_measured_here`** (WorkOS realny, sieć pilota, realne sesje harnessów, oceny Q z ludźmi — każdy
z podanym powodem, nigdy jako pass).

**Ścieżka do zera fail — realny defekt znaleziony i naprawiony w tej sesji, nie ukryty:**
`test_act01_end_to_end.py::test_act01_end_to_end` failował z `"a partial scan must never imply a
removal (U1.5, U9)"`, reprodukowalnie 100% (4/4 przebiegów przed naprawą). Root cause potwierdzony
instrumentacją (`fmt.Fprintf` tymczasowo w `parse.go`, zdjęte po śledztwie — `git diff` na ten plik
czysty) — **partial scan sam w sobie działał poprawnie** (`complete=false actions=[]` wprost z
logu); asercja fałszywie oskarżała go o coś, co spowodował krok dużo wcześniejszy
(`proposals apply --write` → drugi `import`, §b "authoring loop"):

`internal/review/generator/deterministic.go:670` `candidatePath(scope, slug)` zakładał, że katalog
węzła na dysku to dosłownie `scope` z kropkami zamienionymi na `/`. Dla scope `atlas.graph` dawało
to `atlas/graph/.agents/skills/<slug>/SKILL.md` — ale w fixture Meridian węzeł `atlas` jest
zadeklarowany jako `paths: ["platforms/atlas/**"]`, więc prawdziwy katalog to
`platforms/atlas/graph/...`. Serwer rejestrował propozycję z poprawnym scope `atlas.graph`, ale
`apply --write` zapisywał plik pod złą ścieżką; kolejny `import` skanował tę złą ścieżkę i
(poprawnie, biorąc pod uwagę wejście) rozwiązywał ją do scope `_root` — inny `skill_id` niż
oczekiwany, więc importer archiwizował starą tożsamość jako "superseded" (`parse.go:494`, reason
`source_removed`) natychmiast po apply, nie z powodu partial scanu.

**Naprawa (`IMPLEMENTUJ`, na wyraźną prośbę właściciela produktu, 2026-09-08):**
`generator.Request` dostaje pole `ScopeDirs map[string]string` (scope → prawdziwy katalog);
`candidatePath(scope, slug, dirs)` używa go zamiast zgadywać, z fallbackiem do starego zachowania
gdy scope'u brak w mapie. `GenerateWorker.scopeDirs()` (`internal/review/generate.go`) wypełnia tę
mapę jednym zapytaniem do `gfm.scopes` (tabela, którą `import.parse` już pisze przez
`writeScopes` — czytana tu przez jawną, jednoprzeznaczeniową projekcję, zgodnie z
`module-boundaries-go`, nie przez sięgnięcie do cudzej logiki) i `longestLiteralPrefix()`
(zduplikowana, nie zaimportowana z `internal/importer/domain.ScopeOf` — `dry-without-wrong-abstraction`,
trzy linie nie uzasadniają nowej zależności międzymodułowej). Test jednostkowy
(`generator/consolidation_test.go`) zaostrzony z tolerowania ZARÓWNO `platforms/` JAK I `atlas/`
(świadomy hedge sprzed naprawy) do wymagania wyłącznie poprawnego `platforms/atlas/...` — czerwony
przed naprawą, zielony po. Dotyczy każdego monorepo, gdzie węzeł grupuje katalog pod inną nazwą niż
dosłowna ścieżka (kształt Meridian) — nie edge case. Zweryfikowane bezpośrednio na scenariuszu, który
znalazł defekt: `test_act01_end_to_end` **pass** samodzielnie i w pełnym zestawie 41 wierszy, 0 fail.

Dodatkowo tej sesji: `GET /health/ready` teraz ogłasza `"1.2"` w `api_schema_versions`
(`main.go`) — zamyka ostatnią uwagę wiersza P08 poniżej; funkcjonalność 1.2 (`family12.go`,
`use12.go`, `harness-service-v1.2.schema.json`) była już zaimplementowana i przetestowana, brakowało
tylko ogłoszenia. Pełna regresja po wszystkich naprawach tej sesji: `go test ./... -count=1` (15
pakietów, `services/search`), `pytest tests/ -q` (pełny pakiet, nie tylko acceptance), checker
kontraktu (`tools/contract/check_api_contract.py`) 0 dryfu — wszystko zielone w jednym spójnym
stanie drzewa na koniec sesji.

## Radar badawczy (skan 2026-09-07)

| Praca | Co proponuje | Stan u nas | Decyzja |
|---|---|---|---|
| Persistent Skills (arXiv:2609.04869) | Niemutowalne wersje skilli i snapshoty indeksu; reindeks asynchroniczny; request zaczęty na N kończy na N | Zaimplementowane: `gf.snapshots` niemutowalne, atomowa podmiana `gf.heads` po walidacji, rollback, SEARCH zwraca `snapshot` + `revision`, USE 1.2 z `search_snapshot` → 409 `snapshot_changed` (PRD §8), cache LRU per snapshot | Bez zmian. Opcja później: USE czytające ze wskazanego, istniejącego snapshotu zamiast 409 (wymaga zmiany PRD §8). |
| CoSkill (arXiv:2609.04865) | Dwustopniowy retrieval: globalny → rodzina → dzieci | Dane są (scope, `refines`/`derived_from`/`requires`, warstwa piramidy), etap rankingu nie | Kandydat na następną rodzinę badawczą po zamknięciu bieżącej (ADR-0029, reguła P06–P08). Warunek: korpus z etykietami hierarchii; brak wyniku 30k/sub-300 ms w pracy. |
| SkillRevise (EMNLP 2026 Findings), FUSION | Walidacja skilla przez wykonanie, naprawa z trace | Provenance, zasoby pakietu, raport CI; bez wykonywania | Lifecycle, nie hot path; poza MVP. |

Źródło: zewnętrzny skan badawczy z 2026-09-07 (nie recenzowany w tym repozytorium); nie zmienia decyzji o BM25F jako domyślnym retrievalu.
