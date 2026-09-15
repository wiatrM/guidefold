# Stan implementacji pivotu

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument spisuje,
co jest zaimplementowane i przetestowane w kodzie na dany dzień; nie zastępuje PRD, architektury
ani backlogu i sam w sobie nie jest dowodem pilota (R/Q, nie P — patrz
[eval-evidence-rules](../.agents/skills/eval-evidence-rules/SKILL.md)).

**Status: implementacja w toku, zacommitowana na `main`. Data: 2026-09-15 — §b/§c/§d/§e/§f
przepisane wobec `main` @ `2a302f5` i kontraktu 1.13.0.** Od poprzedniej aktualizacji (2026-09-09,
kontrakt 1.1.1) doszły: moduły `live`, `agentrun`, `ghapp`, `model`, `secrets` w
`services/search/internal`, GitHub App (connect, instalacje, import bez CLI, raport PR), Live Agent
(ADR-0046), klucze modelu organizacji szyfrowane w spoczynku (ADR-0045), organizacja jako domyślny
zakres odczytu (ADR-0047), telemetria domyślnie włączona (ADR-0048), widok Overview `/home` i
konsola na shadcn (ADR-0044), warstwa efektów wizualnych (ADR-0049). §a/§g/§h/§i pozostają
historią sesji 2026-09-06–09 poza wskazanymi aktualizacjami. Rozjazdy dokumentów wobec kodu z
2026-09-12: [audyt](reports/product/2026-09-12-assumptions-vs-implementation-audit.md); bieżąca
krytyczna ścieżka do MVP: [raport 2026-09-15](reports/product/2026-09-15-mvp-closure-status.md).
Cel: jeden przegląd stanu historii P01–P16 wobec kodu, testów i kontraktu, żeby decyzje przed
pilotem (§h) nie wymagały ponownego przeszukiwania repozytorium.
Wejścia: [PRODUCT-PIVOT](PRODUCT-PIVOT.md), [PIVOT-ARCHITECTURE](PIVOT-ARCHITECTURE.md),
[PIVOT-BACKLOG](PIVOT-BACKLOG.md), [API-CONTRACT](API-CONTRACT.md) (`contract_version` 1.13.0).
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

## b) P01–P16: co jest zaimplementowane

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
| P08 | `internal/review` (kind `consolidation` grupowany po scope nadrzędnym, `consolidation_sources_insufficient`, `profile: one_shot`), `internal/review/generator` (`layer.go`: wnioskowanie `knowledge_layer` — 5 reguł, `origin: inferred`, nadpisywalne przez ownera na `origin: human`; `refines` w obu kierunkach), `internal/graph` (acykliczność), `family12.go` (addytywne `family` w 1.2, dowiedziony bit-identyczny ranking), CLI `guidefold extract --all [--personal ...]` (jedna komenda „scan → import → plan one_shot → generate wszystkich rodzajów") | UT (`generator/consolidation_test.go` na zaplantowanym fixture — dwa runbooki ze wspólną procedurą + jeden językowo podobny, poprawnie odrzucony jako `contradictory_steps`; `review/oneshot_test.go`, `review/p08_test.go`, `family12_test.go`), ACC (`test_p08_pyramid.py`, przechodzi na żywym stosie: 30 grup w trybie one-shot vs 15 domyślnie, jeden wspólny element z `derived_from`/`refines` do obu źródeł), UI (Map → Pyramid: pasma Abstract/Task/Atomic zamiast płaskiej listy, rodzic przez `refines` pokazany inline, rozwijalne „N specjalizacji") | zaimplementowano + testy | UI nie czyta jeszcze addytywnego pola `family` z odpowiedzi 1.2 (to pole służy agentom/adapterom, nie przeglądarce — Map/Pyramid już renderuje ten sam graf przez `/map/layers` i `/map/relations`, więc funkcjonalnie równoważne); real-repo (`wshobson/agents`, 183 skille, poza fixture Meridian, 2026-09-08 §h) potwierdził propagację hierarchii i uruchomienie mechanizmu konsolidacji na żywo, ale det-1 abstynował na wszystkich grupach (`too_few_procedures`) — ten korpus jest dokumentacją referencyjną, nie runbookami, więc to trafny werdykt generatora, nie luka; `GET /health/ready` ogłasza `"1.2"` od 2026-09-08 (naprawione tej sesji)  Pomiar na prawdziwym drzewie tego repozytorium 2026-09-15: [CONSOLIDATION-REAL-REPO-2026-09-15](reports/bakeoff/CONSOLIDATION-REAL-REPO-2026-09-15.md) — `no_shared_procedure` było trafne dla reguły i wypowiadane o niewłaściwych 10 z 81 skilli; po naprawie (wybór sąsiadów po rodzinie nazw, dwa kształty nagłówka kroków, przebieg 2 kroków w ≥3 skillach, `derived_from` do każdego niosącego go skilla, recepta `det-2`, kontrakt 1.16.0) repozytorium wydaje jeden prawdziwy wspólny element z trzema źródłami. |
| P09 | `internal/review` (`publication.go`, snapshot), bramka 3: `publisher.go`, `publication_test.go`; opt-in source-proof delivery: `services/search/proof_gate.go`, USE 1.2 `delivery_policy`, CLI `load --delivery-policy proof_gated` | UT/API, UI (aktywacja z powodem w Proposals), CLI transport (`test_service_backend.py`), independent contract replay (`research/proof-gated-delivery-2026-09-09`) | zaimplementowano + kontrakt/schema replay + publisher binding placeholderów + fetch i weryfikacja blobów źródłowych | proof gate proves source binding, source-byte availability and safe `ASK` on synthetic mutations; it does not prove claim truth, execution or user value; targeted Go proof tests pass, while the full suite has one pre-existing stale BM25F fixture failure |
| P10 | CLI `install`/`uninstall`, trzy harnessy: `INSTALL_HARNESSES = ("claude", "copilot", "gemini")` (`skills/guidefold/scripts/guidefold`, sprawdzone 2026-09-15). Szablon `hooks/codex.hooks.json` istnieje, ale `codex` **nie** jest wyborem `install`; `hooks/gemini.hooks.json` nie istnieje | UT (`test_pivot_cli_install.py`) | zaimplementowano + testy | realne sesje harnessów na repo partnera (ACT-01 live) nadal nie odbyły się: 0 tokenów i 0 zdarzeń na produkcji 2026-09-15 |
| P11 | `internal/usage` (`export.go`, `health.go`, `queue.go`) oraz `ExecutionMetrics` (task success, harness errors, SEARCH/USE/ASK, tokeny, czas) | UT/API, UI (`UsageRoute.test.tsx`) | zaimplementowano + testy | brak |
| P12 | CLI `guidefold report`/`validate` (sprzed pivotu, współdzielone) | UT (`test_report.py`) | zaimplementowano + testy (mechanizm) | dowód „10 realnych PR-ów" to dowód pilota, niezmierzony |
| P13 | `importer/drift_test.go` (`source_changed`/`source_removed`), `usage` (`negative_feedback`/`zero_loads`), `gfm.owner_queue` | UT/API, ACC (`test_act01_end_to_end.py`, U1.5/U9 partial-scan-never-implies-removal, pass 2026-09-08) | zaimplementowano + testy | 2026-09-08: znaleziono i naprawiono realny false-positive w "brak false deletion przy partial" — nie w drifcie samym (poprawny), lecz w `candidatePath()` generatora (§b P08, §i) wypychającym ekstrahowany skill pod złą ścieżkę, którą importer poprawnie (dla siebie) czytał jako inną tożsamość i archiwizował starą |
| P14 | `internal/knowledge` (strona modułu) | UT/API | częściowo | scenariusz „5 zadań, potwierdzone ponowne użycie" to dowód pilota, poza zasięgiem tej sesji |
| P15 | `tools/pilot/pivot_report.py`, `tools/pilot/analyze.py`, `docs/pilot/PIVOT-RUBRIC.md` | UT (`test_pivot_report.py`, `test_pilot_analyze.py`) | zaimplementowano + testy (narzędzie) | poza zasięgiem tej sesji: rzeczywisty przebieg pilota z partnerem (patrz [PIVOT-REVIEW](PIVOT-REVIEW.md)); rubryka nadal bez nazwanego buyera |
| P16 | — | — | **brak kodu** | ADR-0042 Accepted 2026-09-12, ale na `main` @ `2a302f5` nie ma `gfm.repo_links` ani `target_repo_id` (`grep`, 2026-09-15). Multi-repo istnieje na `main` w innej postaci: GitHub App (`gfm.github_installations`, import per repozytorium, duplikaty między repozytoriami w kontrakcie 1.12.0) i organizacja jako domyślny zakres odczytu (ADR-0047). Kolejność zmieniona 2026-09-15: po ACT-01 |

## c) Mapa modułów Go i właściciel tabel (wg API-CONTRACT §7)

| Moduł | Właściciel danych |
|---|---|
| `identity` | `gfm.users`, `identities`, `orgs`, `memberships`, `invitations`, `sessions`, `tokens`, `device_codes`, `auth_states`, `audit`, `github_installations`/`github_deliveries` (ADR-0036, `internal/identity/github.go`) |
| `mgmt` | brak własnych tabel — routing, envelope, CSRF, idempotencja (`gfm.idempotency`) |
| `jobs` | `gfm.jobs` (enqueue/lease/heartbeat/checkpoint, fencing po `generation`). Handler `ascend.run` w `worker_handlers.go` nadal zwraca `worker.Skipped("github_app_connector_not_configured")` — job jest trwały i widoczny, nic nie robi (ADR-0036; sprawdzone 2026-09-15) |
| `worker` | brak własnych tabel — uruchamia handlery innych modułów poza HTTP |
| `schema` | DDL dla `gf` i `gfm` (migracje), rola `guidefold_api` |
| `testdb` | brak — harness testowy (jedna baza Postgres per proces testowy) |
| `importer` | `gfm.repos`, `blobs`, `imports`, `import_files`, `gfm.scopes`; pisze też `gfm.relations` dla krawędzi z drzewa importu (`internal/importer/parse.go`) |
| `knowledge` | czyta `gfm.skills`, `skill_revisions`, `skill_resources`, `scopes`; zapisuje `judgment` do `gf.events` |
| `review` | `gfm.proposals`, `proposal_fields`, `decisions`, `exports`, `publications`; **też pisze** `gfm.relations` (krawędzie z propozycji, `store.go`/`approve.go`) — drugi pisarz obok `importer`, `graph` tylko czyta |
| `usage` | projekcja `gfm.owner_queue`, `adapter_health`; czyta `gf.events`. `gf.training_examples` ma tylko DDL i `GRANT INSERT` (`internal/schema/usage.go`, `sql.go`) — zero pisarzy i czytelników w Go (`grep`, 2026-09-15): ADR-0041 „Accepted-but-schema-only" |
| `live` | `gfm.live_runs`, `live_run_targets`, `live_run_events` i pięć tras `{org_base}/live/*` (ADR-0046); zleca `live.plan`, nie otwiera klucza modelu organizacji |
| `agentrun` | brak własnych tabel — workerowa połowa Live Agenta i raportu PR aplikacji GitHub: `live.plan`, `live.repo`, `pr.report` (ADR-0046, ADR-0036 pkt 1a/4a) |
| `ghapp` | brak własnych tabel — jedyny adapter do `api.github.com`: JWT aplikacji, token instalacji, odczyt drzewa i plików, wąski zapis (sticky comment, commit na własnej gałęzi, PR) |
| `model` | brak własnych tabel — klient strumieniowy do `openrouter`/`anthropic`/`openai` (ADR-0045); klucz organizacji żyje tylko w `Request.APIKey` |
| `secrets` | klucze modelu organizacji szyfrowane w spoczynku (`gfm.org_credentials`, ADR-0045) |
| `graph` | brak własnych tabel — reguły acykliczności nad `gfm.relations`/`gf.snapshots` |
| `pivottest` | brak — harness Postgres + router + fixture Meridian |

## d) CLI: nowe komendy

| Komenda | Testy |
|---|---|
| `scan` | `tests/test_pivot_cli_scan.py` |
| `login`/`logout`, `org list`/`use` | `tests/test_pivot_cli_import.py` |
| `import`/`sync`/`status` | `tests/test_pivot_cli_import.py` |
| `install`/`uninstall` (`--harness claude\|copilot\|gemini`) | `tests/test_pivot_cli_install.py` |
| `proposals list`/`show`/`apply` (walidacja ścieżki eksportu przeciw path traversal) | `tests/test_pivot_cli_import.py` |
| `doctor` (rozszerzenie sieciowe) | `tests/test_doctor.py` |
| `report --base <ref>` (P12, deterministyczny diff skilli w CI; błędy struktury blokują, kolizje triggerów ostrzegają, przykłady retrievalu nigdy nie blokują) | `tests/test_report.py` (20) |
| `procedure <SKILL.md> [--run]` (S20, kontrakt wejść/wyjść/warunków/kroków/weryfikacji i jawny lokalny verifier) | `tests/test_procedure.py` |
| `extract [--all] [--personal claude,codex,copilot]` (P08 one-shot: scan → import → plan `profile=one_shot` → generate wszystkich rodzajów; `--personal` wymusza `publish:false`) | `tests/test_pivot_cli_extract.py` (21) |
| `ascend <node>` (ADR-0035: model pisze lub edytuje jeden abstrakcyjny skill map/convention per scope przodka, z bramkami uziemienia; nigdy nie commituje) | `tests/test_ascend.py` |
| `telemetry status`/`flush` (E6.4/E2.7; od ADR-0048 wysyłka jest domyślnie włączona, opt-out jawny) | `tests/test_telemetry.py` |
| `where`, `init`, `drift`, `publish`, `index`, `procedure`, `eval` (sprzed pivotu, opisane w [CONVENTIONS](CONVENTIONS.md)) | odpowiednie zestawy w `tests/` |

## e) UI: tryby, Overview i widoki konsoli

Tryb `fixture` (domyślny) i `api` (`VITE_GUIDEFOLD_API` lub `?mode=api`) przez abstrakcję
`DataSource` (`FixtureDataSource`/`ApiDataSource`); sześciostanowy model routingu obejmuje
`restricted`/`degraded`. Siedem widoków panelu (Import, Library, Map, Skill, Proposals,
Usage & quality, Organization) ma testy Vitest i jest pokryte przez `ui/e2e/api-mode.spec.ts`
(Playwright ze `page.route` — stub, nie prawdziwe API). Od 2026-09-12 pierwszym ekranem po
zalogowaniu jest **Overview `/home`** (`ui/src/routes/HomeRoute.tsx`, ADR-0044): osiem równoległych
odczytów, blok bez danych mówi to sam, brak organizacji lub repozytorium pokazuje jeden następny
krok zamiast pustych kart. Doszły też **Live Agent** (`LiveAgentRoute.tsx`, ADR-0046) oraz
`VerifyEmailRoute.tsx`. Od 2026-09-13 (ADR-0047, kontrakt 1.11.0) odczyty idą do `{org_base}`,
kiedy `?repo=` jest puste, a repozytorium jest filtrem.

**Konsola na shadcn/ui (owner, 2026-09-12; ADR-0044).** Powłoka (`app.tsx` `Shell`) i Overview są
złożone z prymitywów `ui/src/components/ui/*` i bloków `ui/src/components/ui/shadcn-space/blocks`
(boczny pasek, karty KPI `statistics-01`, wykresy `chart-01`/`chart-02` na `ui/chart.tsx` +
Recharts, tabela `table-01`, pusty stan `empty-state-01`). Cztery wizualizacje Overview idą więc
przez Recharts, **nie** przez Spectrum Charts — to nazwane naruszenie SC-01 z ADR-0044 r3, nadal
otwarte na `main` @ `2a302f5` (migracja czeka w PR #164). Szczegóły i zrzuty:
[console-shadcn-20260912](reports/ui/console-shadcn-20260912.md). Klient trzyma `RamCache`
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

Stan tej sekcji: **2026-09-15, `contract_version` 1.13.0 (dokument datowany 2026-09-13).** Pełny
changelog 1.0.0–1.13.0 jest w [API-CONTRACT §11](API-CONTRACT.md#11-changelog) i nie jest tu
duplikowany; poniżej tylko to, co ma dziś odpowiednik w kodzie i zmienia czytanie tego dokumentu:

- **1.2.0 (ADR-0036):** webhook GitHub z HMAC, `gfm.github_installations`, enqueue `ascend.run` —
  zaimplementowane i zapisujące (`internal/identity/github.go`). Sam handler `ascend.run` pozostaje
  stubem (§c), więc wiersz §8 kontraktu opisuje zachowanie, którego worker nie wykonuje.
- **1.2.3 (`gf.training_examples`):** tabela i `GRANT INSERT` istnieją — **schema-only**, zero
  pisarzy i czytelników (ADR-0041).
- **1.2.1/1.2.4 (proof-gated delivery, `claim_refs`):** `services/search/proof_gate.go`, opt-in
  przez `delivery_policy: "proof_gated"` (§b P09; ADR-0039 Accepted jako opt-in 2026-09-12).
- **1.3.0 (Overview `/home`):** `Usage.previous`, `ProposalSummary.decision`,
  `QueueItem.decision.actor`, `FeedbackEntry.actor`, `GET {org_base}/audit` dla roli `member`.
- **1.4.0–1.6.0 (ADR-0045/0046, ADR-0036 jako bot pokrycia):** klucze modelu organizacji, Live
  Agent (`gfm.live_runs` i pięć tras `{org_base}/live/*`), raport PR.
- **1.7.0–1.10.0:** naprawy zweryfikowane przy podłączaniu zarejestrowanej aplikacji GitHub i przy
  logowaniu GitHub na produkcji (weryfikacja e-maila w WorkOS).
- **1.11.0/1.11.1 (ADR-0047):** bliźniaki `{org_base}` każdego odczytu, repozytorium jako filtr,
  integralność katalogu między repozytoriami jednej organizacji.
- **1.12.0:** `GET {org_base}/skills/duplicates` — ta sama nazwa skilla w kilku repozytoriach.
- **1.13.0:** naprawa ścieżki „connect GitHub w kreatorze organizacji → import repozytoriów".

Zasada „kontrakt przed kodem" (API-CONTRACT §1): handler, tabela, migracja, DTO i komenda CLI
zmieniają się wyłącznie razem ze zmianą kontraktu w tym samym PR. Egzekwuje
`tools/contract/check_api_contract.py` — stan 2026-09-15 na `main` @ `2a302f5`: **0 dryfu**, 20 not
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
6. **Stan produkcji 2026-09-15 (dowody P, nie R).** `guidefold.cloudfloo.io` działa i jest
   `Synced/Healthy`, ale baza produkcyjna ma **0 importów, 0 skilli, 0 publikacji, 0 tokenów i 0
   zdarzeń `gf.events`**; z 43 zsynchronizowanych repozytoriów jedno jest zablokowane powodem
   `guidefold_yaml_missing`, a logowanie GitHub kończy się błędem WorkOS, bo aplikacja GitHub nie
   ma uprawnienia „Email addresses: Read-only". Każde „działa" w tym dokumencie jest dowodem R lub
   Q; żadne nie jest P. Pełna lista z dowodami i kolejnością:
   [raport 2026-09-15](reports/product/2026-09-15-mvp-closure-status.md) §3 i §4.
7. **`ascend.run` nadal stub, P16 nadal bez kodu** (§c, §b) — obie pozycje były decyzjami
   właściciela z 2026-09-12; kod do nich nie wszedł na `main`.
8. **Znane defekty produktu naprawione w sesji 2026-09-08/09** (nie tylko luki dowodowe): worker bez
   uprawnień zapisu do katalogu (brak `PGUSER=postgres` operatora), `guidefold telemetry flush`
   bez bearer tokenu, publikacja nadpisująca `needs_review` ustawione przez drift tego samego
   importu, dwie przestrzenie rewizji w `/usage` (naprawione jednym polem `card_revision`),
   `--personal` mogące opublikować prywatne skille organizacji, obcięcie sąsiadów w konsolidacji
   gubiące całe sąsiednie scope'y, path traversal w `guidefold proposals apply --write`.

## i) Dowody akceptacyjne

**Nowszy przebieg, 2026-09-15.** Ta sama komenda na czubku gałęzi `pilot/act01-rehearsal-20260915`
(`repo_commit a285d595`) dała **33 pass, 1 fail, 7 `not_measured_here`**: `ACT-01` przestał przechodzić,
bo spool CLI nie zawiera `card_injected`
(`tests/acceptance/test_act01_end_to_end.py:219`). Reprodukcja, otoczenie i pozostałe znaleziska:
[próba generalna Pilot Core 2026-09-15](reports/pilot/2026-09-15-pilot-core-rehearsal.md).
Opis poniżej zostaje jako zapis stanu z 2026-09-08; nie jest już najświeższym pomiarem.

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
