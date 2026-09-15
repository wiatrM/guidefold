# Druga próba generalna Pilot Core na stosie lokalnym — 2026-09-15

Status: raport z przebiegu. **Wszystko poniżej jest dowodem R (release acceptance na ścieżce produktu) z lokalnej próby generalnej — nie jest dowodem P.** Żaden krok nie dotknął produkcji: bez `kubectl`, bez `guidefold.cloudfloo.io`. Data: 2026-09-15. Gałąź `pilot/act01-rehearsal-v2-20260915` z `main` @ `6d8e521` (merge PR #179).
Cel: powtórzyć kroki 1–11 [pierwszej próby](2026-09-15-pilot-core-rehearsal.md) na scalonym `main`, **bez pisania `guidefold.yaml`** (ADR-0050), sprawdzić, co naprawiło siedem scalonych PR-ów (#174, #176–#180), i zmierzyć to, co nadal nie działa.
Wejścia: stos `tools/dev/stack.py up --name v2 --pg-port 54371 --api-port 8811 --generator deterministic --ui`; importowane drzewo = klon tego repozytorium; [pierwszy raport](2026-09-15-pilot-core-rehearsal.md); [ADR-0050](../../adr/ADR-0050-zero-config-scope-map.md), [ADR-0051](../../adr/ADR-0051-llm-proposed-organisation-map.md); reguły dowodów: [pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md), [eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md), [definition-of-done](../../../.agents/skills/definition-of-done/SKILL.md).
Zakres zastępowania: brak. Raport nie zmienia U1–U11, P01–P15 ani żadnego ADR. Nie zastępuje pierwszego raportu — uzupełnia go o przebieg na scalonym `main` i aktualizuje obraz acceptance w [PIVOT-IMPLEMENTATION](../../PIVOT-IMPLEMENTATION.md).

## 1. Werdykt

Pętla Pilot Core **przechodzi lokalnie bez `guidefold.yaml`**. Import tego repozytorium kończy się `ready`, publikacja jest `active`, konsolidacja po raz pierwszy naprawdę produkuje wspólny element na prawdziwych danych, a propozycja `scope_map` z ADR-0051 daje się rozstrzygnąć na trasie organizacji i zapisuje `gfm.scopes`. Z dwunastu defektów pierwszej próby dziewięć jest zamkniętych.

Dwie rzeczy nie wyszły i to one są treścią tego raportu.

**Po pierwsze: zero-config domyka połowę importową ACT-01 i rozcina połowę dostarczającą.** Bez `guidefold.yaml` `guidefold install` nie uruchamia `materialize` ani `index` („no guidefold.yaml yet"), nie zapisuje bloku `service:`, a więc `find` i `load` chodzą po backendzie lokalnym, żadne `search_requested` nie trafia do ledgera i hook nie ma artefaktu, dopóki właściciel nie uruchomi `guidefold index` ręcznie. ADR-0050 §4 zapowiada dokładnie tę lukę („designed, not implemented here"); tutaj jest ona zmierzona na ścieżce, którą ma przejść właściciel. Obejście istnieje i działa (`GUIDEFOLD_SEARCH_BACKEND=service` + `GUIDEFOLD_SEARCH_URL`), ale nikt go nie zapisał w runbooku — teraz jest w [ACT-01-RUNBOOK §9](../../pilot/ACT-01-RUNBOOK.md).

**Po drugie: `guidefold find` z domyślnym `--limit 8` nigdy nie otwiera gniazda do serwisu.** Kontrakt 1.1 wyraża `budget.max_cards` w zakresie 0..4, więc `search_with_backend` przy `k>4` w ogóle nie próbuje sieci, degraduje do lokalnego z `fallback_reason: "config"` i drukuje URN-y, których serwis nie zna. To nie jest błąd — to zapisana decyzja w kodzie — ale bez `--limit 4` krok 8 ACT-01 nie da się domknąć, bo w `gf.events` nie pojawi się SEARCH.

Oraz jedna rzecz, na którą brief liczył, a której nie ma: **ekstrakcja z prawdziwych dokumentów tego repozytorium nadal daje zero propozycji** (20 × `no_procedure_found`), identycznie jak w pierwszej próbie. Wspólny element `det-2` powstał; ekstrakcja nie.

## 2. Środowisko i wersje

| Co | Wartość |
|---|---|
| Host | WSL2, `Linux-6.18.33.2-microsoft-standard-WSL2`, sieć: tylko loopback |
| Go | `~/.cache/guidefold/toolchain/go/bin` |
| PostgreSQL | `18` (`~/.cache/guidefold/toolchain/pg18/bin`), klaster `v2`, port 54371 |
| API / UI | `http://127.0.0.1:8811`, `GUIDEFOLD_AUTH=dev`, generator `deterministic`; UI `http://127.0.0.1:4331` |
| Claude Code | `2.1.272` (realna sesja `claude -p`); `copilot` i `gemini` **nadal nie są zainstalowane** |
| Drzewo importu | klon tego repozytorium w `~/.cache/guidefold/v2/tree`, `6d8e521` → `5fe68a1` |
| Organizacja / repo | `cloudfloo` (`718f784c-d949-47a9-afdb-6e7d9ecb2bdc`) / `guidefold`, user `65222973-6eca-42ea-bebc-ce675f96a36d` |
| CODEOWNERS | **nie istnieje w tym repozytorium** (`.github/CODEOWNERS`, `CODEOWNERS`, `docs/CODEOWNERS` — brak), więc każdy wywnioskowany `owner` to `unknown` |

**Jedno zastrzeżenie do identyfikatorów.** Pomiar „bez `.guidefoldignore`" (import `aefb5dd6`, publikacja `51795c71`, org `d22aad36-180e-45b8-91d4-8b45c28a99d5`) został wykonany na pierwszej instancji bazy. Żeby nie ciągnąć za sobą 25 zarchiwizowanych skilli fixture'u i kolejki `source_removed` — dokładnie tego, na co pierwsza próba się nadziała — klaster został zresetowany (`stack.py up --reset`) i cała reszta przebiegu poszła od zera, z `.guidefoldignore` obecnym **przed** pierwszym importem, w organizacji `718f784c-…`. Identyfikatory z pierwszej instancji są w tym raporcie oznaczone tym akapitem i nie da się ich już odpytać.

W `wiatrM/guidefold` **nie powstał żaden `guidefold.yaml`**. Jedyne pliki tymczasowe (`.guidefoldignore`, jedna celowo zepsuta karta, dwa znaczniki dryfu) powstały wyłącznie w klonie.

## 3. Mapa scope tego repozytorium, wywnioskowana

`guidefold doctor` przed importem: `no guidefold.yaml — inferred 21 scopes from 17 skill directories`. Po imporcie `gfm.scopes` ma **21 węzłów, wszystkie `source: inferred`, wszystkie `owner: unknown`** — ale dwadzieścia z nich to fixture Meridian (`examples.monorepo`, `examples.monorepo.platforms.atlas.identity.turnstile`, …), a **wszystkie 81 własnych skilli tego repozytorium siedzi w jednym `_root`**, bo leżą w jednym katalogu `.agents/skills/` w korzeniu. Po dodaniu `.guidefoldignore` zostaje **jeden węzeł `_root`**.

Innymi słowy: zero-config usuwa wymóg pliku, ale **nie** rozwiązuje problemu płaskiej mapy, który pierwsza próba opisała w §5 pkt 3. Trzy objawy tamtej płaskiej mapy sprawdzone ponownie:

| Objaw z pierwszej próby | Teraz |
|---|---|
| Map pokazuje jeden scope | nadal jeden (`GET {repo_base}/map/scopes` → 1 scope `_root`, 81 skilli) |
| Pyramid jedną warstwę | nadal jedna (`GET …/map/layers` → `[{"layer":"unclassified","count":81}]`) |
| `materialize` przerywa z „scope card for `_root` exceeds 80 lines" | **naprawione** (PR #180): karta jest skracana, `materialize` i `index` kończą się sukcesem |
| relacje | `GET …/map/relations` → **0 krawędzi** (w pierwszej próbie 24 — pochodziły z `requires` fixture'u Meridian, którego teraz nie ma) |

Właściciel, który chce więcej niż jeden scope na tym repozytorium, **nadal pisze `guidefold.yaml`** — tyle że teraz jest to wybór, a nie warunek startu.

## 4. Kroki 1–11: co przeszło, wobec pierwszej próby

| # | Krok | v1 | v2 | Dowód (komenda / id przebiegu) |
|---|---|---|---|---|
| 1 | Stos, logowanie, organizacja, token urządzenia | pass | pass | `stack.py up --name v2 …`; `GET /health/ready` 200 (`request_id d76385a7-a4a3-46dc-a187-dedb5052b7a4`), org `718f784c-…`; `guidefold login` → kod `B3VL-H8XC`, „logged in as rehearsal-v2@cloudfloo.test" |
| 2 | Skan i import **bez mapy** | pass po trzech obejściach | **pass, jedno obejście** | `scan`: 417 plików, 215 wykluczonych, 108 sugestii, commit `6d8e521`. Import `aefb5dd6` → `ready`, `failed_files: []` — dziesięć kart z niecytowanym dwukropkiem (D1) jest naprawionych na `main`. Po `.guidefoldignore`: import `ec08674b` → `ready`, 379 plików, publikacja `42d6fd12` `active`, 81 skilli |
| 3 | Library / Map / Pyramid | pass, dwie osie puste | pass, **te same dwie osie puste** | `GET {org_base}/skills?limit=100` 200 (81, brak `next_cursor`), `…/map/repository` 200, `…/map/scopes` 200 (1 scope, `source: inferred`), `…/map/layers` 200 (1 warstwa), `…/map/relations` 200 (0 krawędzi) |
| 4 | Ekstrakcja | fail dla wspólnego elementu; ekstrakcja tylko wymuszona | **wspólny element: pass; ekstrakcja: nadal 0** | `extract --all --wait --json` na imporcie `33a84b61`, 7,4 s: `planned_groups 3`, `proposals 7` (`enrichment 5`, `consolidation 1`, `scope_map 1`), `kinds_without_groups []`, `abstentions 22` (20 × `no_procedure_found`, 2 × `already_consolidated`), `cost.calls 0`. Konsolidacja `6363e679` = `det-2` |
| 4a | Propozycja `scope_map` (ADR-0051) | nie istniała | pass | `scope_map.propose` `77d14db9` → propozycja `555341db`, `origin: inferred`, diff `unchanged: 1`. Trasa repo `POST {repo_base}/proposals/555341db/decision` → **403 `forbidden`** (`request_id a58a870897c9803a3fde710114a8ce6d`), trasa organizacji → 200, `state: applied`, `scopes_written: 1` |
| 5 | Git roundtrip | pass | pass | eksport `6b7d362f-a0cc-4dc2-93cd-cd21332d8a02` (`base_commit 8064e89`) → `proposals apply --write` → `.agents/skills/shared-if-higgsfield-is-not-on-path-install-it/SKILL.md` (ścieżka realnego katalogu, nie `_root/…`) → commit `5ec84f8` → import `8d0016d6` → publikacja `9de3a1e6` `active`, **82 skille** |
| 6 | Publikacja i odpowiedź SEARCH/USE | pass | pass | `POST /v1/use` z `card_revision` → 200 (`request_id fe886fa0-b673-4092-b14c-eb3f05cfddfb`); z `revision_id` → **409 `revision_mismatch` z `hint: "send card_revision from the catalog"`** (`48fc1d7a-70a6-407b-9567-5f8c45590d67`) — D10 zamknięty |
| 6a | Publikacja częściowa (kontrakt 1.17.0) | fail (`import_partial`, nic nie publikowało) | **pass** | jedna celowo zepsuta karta → import `7d978c54` `partial` (`counts: accepted 406, failed 1, omitted 1`), publikacja `9045b9cf` **`active`, `partial: true`, 83 skille**, jedna pozycja kolejki `import_file_failed` |
| 7 | Adapter: install → login → hook → realna sesja | pass po naprawach | **pass dopiero po dwóch obejściach** | `install --harness claude` bez traceback'u (D4 zamknięty), pakiet sha256 `00226333…`, ale `materialize/index: skipped (no guidefold.yaml yet)`. Po ręcznym `materialize` + `index` (109 kart, 8305 termów) hook z `docs/` zwrócił 3 karty z URN-ami serwisu. **Realna sesja `claude -p`** (2.1.272) odpowiedziała wyłącznie z wstrzykniętej guidance; ledger: `search_requested 1`, `search_results 1`, `card_injected 3` |
| 8 | Feedback → kolejka → decyzja | pass | pass | `POST …/revisions/c7ec077d…/feedback {"verdict":"helped"}` → `judgment_id 52f34003-be44-4fd9-9a4f-4b1165ae30b5`; `GET …/usage?window=30d` → `feedback {helped: 1, n: 1}`, `exposures 34`, `search_requests 6` |
| 9 | Drift (U9/P13) | pass | pass | edycja `.agents/skills/adr-writing/SKILL.md` → import `aab435dc` → pozycja `d287c763-6e12-4c73-91c9-6281058c4e29` `source_changed`, skill w `needs_review`; decyzja `reviewed` → z powrotem `published` |
| 10 | Drugi harness (Copilot CLI) | nie do wykonania | **nadal nie do wykonania** | `which copilot`, `which gemini` — brak binariów. Nic nie zostało odegrane; wymagania dla właściciela w [ACT-01-RUNBOOK §11](../../pilot/ACT-01-RUNBOOK.md) |
| 11 | Warstwa akceptacyjna | 33 / 1 / 7 | patrz §7 | `GUIDEFOLD_ACCEPTANCE=1 python3 -m pytest tests/acceptance -q` |

Stan bazy po całej próbie (klaster `v2`): `orgs 1`, `repos 1`, `imports 6` (`ready 5`, `partial 1`), `skills 83` (wszystkie `published`), `proposals 7` (`enrichment draft 5`, `consolidation published 1`, `scope_map applied 1`), `decisions 2`, `publications 6` (`active 1`, `superseded 3`, `failed 2`), `tokens 2`, `gf.events 59` (`card_injected 34`, `search_requested 6`, `search_results 6`, `skill_load_requested 6`, `skill_load_completed 6`, `skill_feedback 1`). Kolejka właściciela: `source_changed` (resolved) 1, `import_file_failed` (open) 1.

## 5. Wspólny element `det-2` — co dokładnie powstał

Jedyna propozycja konsolidacji, `6363e679-d550-4c29-90e9-80be0c2b2550`, scope `_root`, generator `deterministic` wersja `det-2`, źródła:

```
urn:skill:guidefold:_root:higgsfield-generate
urn:skill:guidefold:_root:higgsfield-product-photoshoot
urn:skill:guidefold:_root:higgsfield-soul-id
```

Kandydat: `.agents/skills/shared-if-higgsfield-is-not-on-path-install-it/SKILL.md`, dwa kroki (instalacja CLI z `$PATH` i ponowne logowanie po `Session expired`), sekcja „Derived from" z trzema URN-ami. Po zatwierdzeniu, eksporcie, `proposals apply --write` i ponownym imporcie karta jest opublikowana i **wygrywa `find "higgsfield install"`** (rank 1) na backendzie serwisowym.

To jest **realne dane, n=1** — pierwszy raz, gdy konsolidacja znalazła cokolwiek poza syntetycznymi runbookami z pierwszej próby. Dwa uczciwe zastrzeżenia:

1. **Nazwa i opis karty są zdaniem z pierwszego kroku**, nie tematem: `name: shared-if-higgsfield-is-not-on-path-install-it`, `description: "[_root] Shared: If \`higgsfield\` is not on \`$PATH\`, install it:"`. Recepta `det-2` nie nazywa procedury, tylko cytuje jej początek. Do katalogu, który ma być przeszukiwalny, to jest słaby tytuł.
2. **n=1 na 83 kartach.** Trzy bootstrapy `higgsfield-*` dzielą dosłownie ten sam blok. Nic w tym przebiegu nie mówi, ile takich powtórzeń jest w repozytorium klienta.

## 6. Ekstrakcja: oczekiwanie briefu, którego nie udało się spełnić

Brief zakładał, że po scaleniu #178/#180 `extract --all --wait` „musi teraz wyprodukować ekstrakcję **i** element `det-2`". Element powstał; ekstrakcja nie.

Plan importu `33a84b61` (`GET {repo_base}/imports/{id}/plan?profile=one_shot`) ma grupę `extraction:_root` z **20 dokumentami** (`AGENTS.md`, `CLAUDE.md`, `README.md`, `deploy/k8s/README.md`, `deploy/k8s/environments/cloudfloo-io/README.md`, `deploy/t1/README.md` i czternaście `docs/adr/ADR-00xx-*.md` w kolejności alfabetycznej). Zadanie `proposal.generate` zwróciło **20 abstencji `no_procedure_found`** z jednakowym `detail: "the document has no ordered steps to extract"` i zero propozycji.

Dwie rzeczy, które to znaczą:

- **Deterministyczna recepta wyciąga procedury, a dokumenty tego repozytorium są prozą.** To samo stwierdzenie co w pierwszej próbie, teraz na scalonym `main` i bez podrzuconych runbooków. Nie jest to porażka generatora — jest to abstencja, i tak należy ją zapisać (nie jako zero).
- **Budżet 20 dokumentów na scope przy jednym scope oznacza, że reszta repozytorium jest dla ekstrakcji niewidoczna.** `deploy/k8s/environments/cloudfloo-io/README.md`, który naprawdę zawiera ponumerowaną procedurę wydania, **jest** w tych dwudziestu i mimo to abstynował.

Krok „jedna ograniczona propozycja ekstrakcji" z §13 PRD nadal wymaga albo generatora zdalnego (P5 w runbooku), albo świadomej zgody właściciela na wariant B.

## 7. Warstwa akceptacyjna

**34 pass / 0 fail / 7 `not_measured_here`** (41 wierszy), wobec **33 / 1 / 7** w pierwszej próbie.

```
GUIDEFOLD_ACCEPTANCE=1 python3 -m pytest tests/acceptance -q
```

| Co | Wartość |
|---|---|
| Przebieg | `2026-09-15T15:18:37Z` → `15:22:50Z` (4 min 12 s) |
| `repo_commit` | `d4fdf785c765c3bec322e553bdeb297bc9513453` — czubek gałęzi, po obu naprawach |
| Raport | `.guidefold/checks/acceptance-2026-09-15.json` (`format: guidefold-acceptance-report-v1`), 41 wierszy |
| Środowisko | własny klaster PostgreSQL 18.6 na porcie 47348 i własne API na 43506 (`start_stack(name="acceptance")`), generator `deterministic`, sieć wyłącznie loopback |

Uwaga metodyczna z §11a pierwszego raportu obowiązuje bez zmian: `tests/acceptance/conftest.py` **buduje własny stos**, więc tej warstwy nie da się uruchomić „przeciwko" stosowi `v2`; numery portów powyżej nie są portami `v2`.

**Jedyna porażka pierwszej próby zniknęła.** `ACT-01` (`tests/acceptance/test_act01_end_to_end.py`) przechodzi: asercja sprawdza teraz spool ∪ ledger, a `flush` przestał kasować zdarzenia dopisane w trakcie wysyłki (D8, PR #180). Żaden wiersz nie zmienił się w drugą stronę.

Siedem `not_measured_here` to niezmiennie te same siedem i **żadnego z nich nie da się zamknąć lokalnie** — każdy niesie powód w raporcie:

| `acc_id` | Czego brakuje |
|---|---|
| `U11 (pilot)` | trzy zespoły, 20–40 sparowanych zadań, zamrożona rubryka (E6.7) — poziom P |
| `U2-4` | dwóch ludzkich reviewerów i rubryka zamrożona przed generowaniem — poziom Q |
| `U3-1 (WorkOS)` | prawdziwy tenant WorkOS; ten przebieg ma `GUIDEFOLD_AUTH=dev` |
| `U4-2 (pilot network)` | sieć partnera i produkcyjny build; liczba z loopbacku nie jest twierdzeniem o latencji |
| `U4-5` | pięć osób spoza zespołu przechodzących ścieżkę bez pomocy — poziom Q |
| `U5-4` | dwie realne sesje w dwóch harnessach; podproces CLI sterowany testem nie jest sesją |
| `U6-6` | decyzja właściciela po czterech tygodniach obserwacji — poziom P |

`not_measured_here` to „nie zmierzono tutaj", nie pass i nie zero.

## 8. Defekty

### Naprawione w tej gałęzi (każdy z testem, czerwonym przed zmianą)

**D13 — `extract --all --wait` nie czekał na zadania, które sam zlecił.** `proposals:generate` kolejkuje zadania, gdy import jest **już** w stanie terminalnym, więc `_wait_for_import` wracał natychmiast i całe podsumowanie było czytane, zanim cokolwiek się wygenerowało. Pierwszy przebieg: `guidefold extract --all --wait --json` skończył się w **0,4 s** i wypisał `proposals: 1 (scope_map=1)`, `abstentions: []`, `cost.calls: 0` dla przebiegu, który dwadzieścia sekund później miał pięć enrichmentów, jedną konsolidację i dwadzieścia abstencji. Właściciel przeczytałby to jako „ekstrakcja nic nie znalazła i niczego nie odmówiła" — to jest ta sama klasa błędu co D7, przeniesiona o jeden krok dalej. Naprawa: `_wait_for_jobs` odpytuje `ImportDetail.jobs[]` (serwis zapisuje te wiersze w tej samej transakcji, w której odpowiada na `proposals:generate`), aż każde zlecone zadanie jest `done`/`failed`/`skipped`/`cancelled`. Test: `tests/test_pivot_cli_extract.py::test_extract_wait_waits_for_the_generation_jobs_not_only_for_the_import`. Commit `189cebb`. Po naprawie ten sam przebieg trwa 7,4 s i raportuje 7 propozycji oraz 22 abstencje.

**D20 — `guidefold status` nie nazywa pliku, przez który import jest `partial`.** Drukarka kubełkowała pliki po `state`; kontraktowe DTO `ImportFile` ma pole `status` (API-CONTRACT §5.2). Każdy plik trafiał więc do `unknown`, a `unknown` jest kubełkiem, który drukarka **wypisuje** — więc `partial` import 408 plików wypisał 408 nierozróżnialnych linii i ani razu nie nazwał `.agents/skills/rehearsal-v2-broken-card/SKILL.md` ani jego `ScannerError`. To jest dokładnie ten plik, o który właściciel ma pozycję w kolejce. Fałszywe pole miał też serwer atrapa w testach, dlatego nikt tego nie złapał. Test: `tests/test_pivot_cli_import.py::test_status_names_the_file_a_partial_import_could_not_parse`. Commit `d4fdf78`.

W obu commitach `services/search/testdata/{bm25f,policy}.json` niosą nowy `source_cli_sha256` i wywiedzione z niego cyfry pakietu; żaden posting, norm, idf ani przypadek policy się nie zmienił, więc ranking nie drgnął.

### Opisane, nienaprawione

**D14 — `gfm.scopes.source = 'llm_approved'` dla przebiegu, w którym żaden model nie brał udziału.** Propozycja `555341db` powstała z deterministycznego wariantu `scope_map.propose` (ADR-0051 decyzja 7), niesie `origin: inferred` i diff `unchanged: 1` — jest dosłownie mapą, którą `infer_map()` już policzył. Zatwierdzenie zapisało jednak `source = 'llm_approved'`, `reviewed_by`, `proposal_id`. Wiersz twierdzi więc, że mapę zaakceptowano po modelu, którego nie było. ADR-0051 decyzja 1 podaje tę wartość wprost, więc rozróżnienie (`proposal_approved` obok `llm_approved`, albo zapisanie `origin` osobno) jest zmianą kontraktu, nie łatką.

**D15 — nieudanej publikacji nie da się powtórzyć.** Po tym, jak edycja CLI unieważniła snapshot (§9), `POST {repo_base}/publish` z **nowym** `idempotency_key` i tym samym `import_id` zwrócił istniejący wiersz `failed` z tym samym `job_id` (`10e0472e-…`) i nie zlecił nic nowego; `guidefold import --wait` na niezmienionym drzewie zwrócił ten sam `import_id` (`b7425cf1-…`), bo `gfm.imports` ma `UNIQUE(org_id,repo_id,manifest_digest)`. Właściciel nie ma żadnej komendy, którą wróciłby do stanu publikowalnego — musi zmienić drzewo. Dopiero commit zmieniający `README.md` dał import `8d0016d6` i publikację `9de3a1e6`. Obecne zdanie runbooka („Lekarstwo to ponowny import i publikacja") jest nieprawdziwe i zostało poprawione w [§8 runbooka](../../pilot/ACT-01-RUNBOOK.md).

**D16 — `install` nie buduje artefaktu indeksu w repozytorium zero-config.** `guidefold install --harness claude` kończy się `materialize/index: skipped (no guidefold.yaml yet)`, mimo że uruchomione ręcznie **obie** komendy działają na mapie wywnioskowanej (`materialize` zapisał komplet plików, `index` — 109 kart, 8305 termów). Hook zostaje bezczynny do ręcznego `guidefold index`. To jest ADR-0050 §4 („`search.*`/`registry.*` … the move is not in this change") widziane od strony właściciela: plik, którego ADR-0050 nie wymaga, `install` nadal chce.

**D17 — `infer_map` nie honoruje `.guidefoldignore`.** Po dodaniu `.guidefoldignore` z `examples/monorepo/` serwis ma **jeden** scope i 82 skille, a lokalne `doctor`/`materialize`/`index` dalej widzą **21 scope'ów i 109 skilli**; `materialize` zapisał `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` i `.github/instructions/*` w dwudziestu katalogach `examples/monorepo/**`, których import nigdy nie widział (67 zmienionych ścieżek w drzewie roboczym). `scan` honoruje wykluczenie, mapa nie.

**D18 — jedno drzewo, trzy różne `publisher`, i to wbrew treści ADR-0050.** ADR-0050 §3 zapewnia, że „URN stability … the hook is unaffected". Zmierzone w jednym przebiegu, dla jednego drzewa:

| Źródło | Wartość | Kiedy |
|---|---|---|
| git remote (owner segment ścieżki klona) | `projects` | przed `guidefold login` — i to ta wartość trafiła do nagłówka wygenerowanego `AGENTS.md`: „Scope: projects (root)" |
| plik credentials (`guidefold login`) | `cloudfloo` | po zalogowaniu; `find` drukował `urn:skill:cloudfloo:_root:*` |
| `build_tree.py --publisher <repo_id>` (worker) | `guidefold` | zawsze na serwerze; `gf.skills` niesie `urn:skill:guidefold:_root:*` |

Skutek: URN wypisany przez lokalny `find` nie jest URN-em, który zna serwis, a wygenerowana karta scope zmienia tytuł w zależności od tego, czy właściciel zdążył się zalogować przed `materialize`. Naprawa wymaga decyzji, które z trzech źródeł jest kanoniczne — to jest zmiana ADR-0050, nie łatka.

**D19 — `telemetry_health.parity_mismatch` jest odrzucane przez ingest.** CLI emituje to zdarzenie z `search_with_backend`, gdy odpowiedź lokalna i serwisowa się różnią (a różnią się prawie zawsze: inne skale wyników). Zamrożone `services/search/telemetry-schema.json` zna sześć typów (`search_requested`, `search_results`, `card_injected`, `skill_load_requested`, `skill_load_completed`, `skill_feedback`) i nie zna tego. Każdy `telemetry flush` po serwisowym `find` kończy się więc linią `rejected <event_id>: unknown_event_type` (zaobserwowane dwukrotnie: `b4014b8a-9297-40d4-9b5c-73fcaa43c68d`, `b405c264-5194-4a5f-9da9-20a036e33f1e`). To jest ta sama klasa co D6, tyle że tu odrzucane zdarzenie nie jest błędem — jest sygnałem parity. Dopisanie typu do zamrożonego schematu to zmiana kontraktu.

### Defekty pierwszej próby: stan na `main` @ `6d8e521`

| Defekt | v1 | v2 |
|---|---|---|
| D1 dziesięć niecytowanych dwukropków | blokował publikację | **zamknięty** — import `aefb5dd6` `ready`, `failed 0` |
| D2 `validate` wywracał się na złym YAML | fail | **zamknięty** |
| D3 `import_tree_has_no_guidefold_yaml` był martwym kodem | fail | **bezprzedmiotowy** — ADR-0050 usuwa tę przyczynę; drzewo bez mapy się importuje |
| D4 `install` kończył się `TypeError` | fail | **zamknięty** |
| D5 `load` dawał 403 dla klonu o innej nazwie | fail | **zamknięty** — klon nazywa się `tree`, repo id `guidefold`, `load` działa |
| D6 nieudany `load` wypadał z ledgera | fail | **zamknięty** — `skill_load_completed` 6 w `gf.events` |
| D7 `extract` nie uruchamiał ekstrakcji i milczał | open | **zamknięty**, ale odsłonił D13 |
| D8 ACT-01 nie zapisywał `card_injected` | open | patrz §7 |
| D9 publikacja odmawiała całego snapshotu przy `partial` | open | **zamknięty** — publikacja `9045b9cf` `active`, `partial: true` |
| D10 `/v1/use` przyjmuje `card_revision`, katalog zwraca `revision_id` | open | **zamknięty** — 409 z `hint` |
| D11 `telemetry flush` przegrywał wyścig | open | **zamknięty** — pusty spool to jedna linia i kod 0 |
| D12 każdy błąd `/v1/use` jako „(auth)" | open | **zamknięty** — kod HTTP, słowa serwera, `request_id` i krok `next:` w każdym z trzech sprawdzonych przypadków |

## 9. Dwa problemy środowiskowe, które czytają się jak defekty produktu

Oba trafiły się w tym przebiegu i oba są opisane w runbooku, bo trafią się też właścicielowi.

1. **`snapshot_policy_mismatch` po edycji CLI.** `serve` i `worker` hashują `skills/guidefold/scripts/guidefold` przy starcie (`GUIDEFOLD_POLICY_SOURCE`), a `build_tree.py` hashuje ten sam plik przy budowie snapshotu. Commit D13 unieważnił więc każdą publikację działającego stosu (dwa wiersze `failed`: `191733fb`, `ccaa2373`). Lekarstwo to **restart usług**, nie debugowanie uwierzytelnienia — i (przez D15) także zmiana drzewa.
2. **`rejected=1 unknown_event_type` przy poprawnym `flush`.** Patrz D19. `sent=23 accepted=22 rejected=1` jest poprawnym przebiegiem, nie awarią telemetrii.

## 10. Uczciwe ograniczenia

- Wszystko powyżej to **R**. Jedna organizacja, jedna maszyna, loopback, provider `dev` zamiast WorkOS, generator `deterministic` zamiast modelu. Nic tu nie jest dowodem wartości ani dowodem P ([pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md)).
- **Drugi harness nadal nie sprawdzony.** `copilot` i `gemini` nie istnieją na tej maszynie; żaden wiersz macierzy adapterów nie może zostać wypełniony tym raportem (#82, #83).
- **Realna sesja `claude -p` została wykonana**, ale jej operatorem był agent budujący Guidefolda. Sesja dowodzi plumbingu (hook → SEARCH przez serwis → `card_injected` → ledger), nie użyteczności. Sesja ta wykonała SEARCH, ale **nie** wykonała `load` — LOAD w ledgerze pochodzi z moich jawnych wywołań, nie z sesji. PRODUCT-FOCUS wymaga jednej sesji mającej **i** SEARCH, **i** LOAD; ten przebieg jej nie dostarcza.
- **Wspólny element to n=1 na prawdziwych danych.** Ekstrakcja to n=0. Żadna z tych liczb nie mówi nic o repozytorium klienta.
- **Propozycja `scope_map` była no-opem** (diff `unchanged: 1`). Ścieżka review → decyzja → zapis `gfm.scopes` jest udowodniona; wartość mapy proponowanej przez model — nie, i bez modelu nie może być.
- Zapytania dowodowe na `gf.events` mogą używać wyłącznie kolumn `event_id, event_type, occurred_at, received_at, schema_version, tenant_id, search_id, load_id` — `payload` jest `bytea`.

## 11. Co dalej

Kolejność produkcyjna i pełna lista przedlotowa: [ACT-01-RUNBOOK](../../pilot/ACT-01-RUNBOOK.md), zaktualizowany w tej samej pracy. Przygotowane (niewykonane) wydanie: [2026-09-15-release-prep](../deploy/2026-09-15-release-prep.md).

Z tego raportu wynikają cztery rzeczy, których nie da się rozwiązać agentem:
1. uprawnienie „Email addresses: Read-only" w GitHub App (niezmienione z pierwszej próby);
2. nazwany deweloper spoza zespołu z terminem sesji, która wykona **i** SEARCH, **i** LOAD;
3. decyzja o generatorze zdalnym albo świadoma zgoda na wariant B kroku §13 (ekstrakcja);
4. decyzja o `publisher` (D18) i o `source = 'llm_approved'` (D14) — obie zmieniają kontrakt lub ADR.
