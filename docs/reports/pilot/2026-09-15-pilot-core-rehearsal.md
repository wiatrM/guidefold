# Próba generalna Pilot Core na stosie lokalnym — 2026-09-15

Status: raport z przebiegu. **Wszystko poniżej jest dowodem R (release acceptance na ścieżce produktu) z lokalnej próby generalnej — nie jest dowodem P.** Żaden krok nie dotknął produkcji: bez `kubectl`, bez `guidefold.cloudfloo.io`. Data: 2026-09-15. Gałąź `pilot/act01-rehearsal-20260915` z `main` @ `2a302f5`.
Cel: przejść lokalnie dokładnie tę ścieżkę Pilot Core, którą właściciel ma wykonać na produkcji do 2026-09-17 ([PRODUCT-PIVOT](../../PRODUCT-PIVOT.md) §13, ACT-01 w [PIVOT-BACKLOG](../../PIVOT-BACKLOG.md)), znaleźć i naprawić to, co się psuje, i zapisać komendę, środowisko oraz identyfikator przebiegu przy każdej liczbie.
Wejścia: stos `tools/dev/stack.py up --name act01 --pg-port 54341 --api-port 8781 --generator deterministic --ui`; importowane drzewo = klon tego repozytorium; [raport stanu 2026-09-15](../product/2026-09-15-mvp-closure-status.md) §3–§5; reguły dowodów: [pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md), [eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md).
Zakres zastępowania: brak. Raport nie zmienia U1–U11, P01–P15 ani żadnego ADR. Aktualizuje obraz §i [PIVOT-IMPLEMENTATION](../../PIVOT-IMPLEMENTATION.md) o nowszy przebieg acceptance, nie zastępując go.

## 1. Werdykt

Pełna pętla Pilot Core **przechodzi lokalnie**, ale dopiero po czterech naprawach i trzech obejściach konfiguracyjnych. Na `main` @ `2a302f5` import tego repozytorium kończył się stanem `partial` i **żadna publikacja nie była możliwa**; `guidefold install --harness claude` kończył się traceback'iem; `guidefold load` przez hostowane API zwracał 403 dla każdego klonu, którego katalog nie nazywa się dokładnie jak repo id; a każdy nieudany `load` wypadał z ledgera. Cztery naprawy są w tej gałęzi z testami. Sześć dalszych defektów jest opisanych z reprodukcją i nie jest naprawionych, bo wymagają decyzji o kontrakcie albo zachowaniu produktu.

Najważniejsze dla właściciela: **deterministyczny generator nie wyprodukuje na tym repozytorium żadnej propozycji ekstrakcji** (dokumenty są prozą, nie procedurami), a plan ogranicza ekstrakcję do 20 dokumentów na scope. Krok „jedna ograniczona propozycja ekstrakcji i jeden wspólny element" z §13 PRD nie jest domknięty samym uruchomieniem `guidefold extract` na produkcji.

## 2. Środowisko i wersje

| Co | Wartość |
|---|---|
| Host | WSL2, `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`, sieć: tylko loopback |
| Go | `go1.27.1 linux/amd64` (`~/.cache/guidefold/toolchain/go/bin`) |
| PostgreSQL | `18.6` (`~/.cache/guidefold/toolchain/pg18/bin`), klaster `act01`, port 54341 |
| API | `http://127.0.0.1:8781`, `GUIDEFOLD_AUTH=dev`, generator `deterministic` |
| Python / git | `3.12.3` / `2.43.0` |
| Drzewo importu | klon `gf-pilot-core` w `~/.cache/guidefold/act01/tree`, gałąź `rehearsal/act01-20260915` → `roundtrip/act01` |
| Organizacja / repo | `cloudfloo` (`e12cf903-7e0f-4bfa-b83b-6f63d4c06a33`) / `guidefold` |
| Claude Code | `2.1.272`; `copilot` i `gemini` **nie są zainstalowane** (`which copilot`, `which gemini` → brak) |

Wszystkie pliki tymczasowe (mapa `guidefold.yaml`, `.guidefoldignore`, dwa runbooki) powstały **wyłącznie w klonie**, nigdy w `wiatrM/guidefold`.

## 3. Kroki 1–11: co przeszło

| # | Krok | Wynik | Dowód (komenda / id przebiegu) |
|---|---|---|---|
| 1 | Stos + logowanie + organizacja + token urządzenia | pass | `stack.py up --name act01 …`; `GET /health/ready` 200, `api_schema_versions ["legacy-unversioned","1.1","1.2"]`, request_id `86d66f7d-fe06-4376-9340-79d423e59807`; org `e12cf903-…`, user `404b4570-…` |
| 2 | Skan i import tego repozytorium | pass **po trzech obejściach** | `scan` bez mapy: 413 plików, 108 sugestii, commit `2a302f5`. Importy: `54b68a73` (failed), `eadebd0a` (partial), `a31bc8ba` (ready, publikacja failed), `2ad8b67e` (ready + publikacja `active`, 81 skilli). Szczegóły w §4 D1–D4 |
| 3 | Library: lista, źródła, trzy osie | pass, ale **dwie osie puste** | `GET {repo_base}/skills?limit=100` 200 (items=100, `next_cursor`), `…/map/repository` 200 (81 skilli pod `.agents`), `…/map/scopes` 200 → **1 scope**, `…/map/layers` 200 → **`[{"layer":"unclassified","count":106}]`**, `…/map/relations` 200 (24 krawędzie) |
| 4 | Jedna ograniczona ekstrakcja + jeden wspólny element | **fail dla wspólnego elementu, pass dla ekstrakcji dopiero po wymuszeniu** | `guidefold extract --all --wait` na `2ad8b67e`: `proposals: 0`, abstencje `no_procedure_found` (20 dokumentów) i `no_shared_procedure`. Po dodaniu dwóch runbooków i węzła `docs.runbooks`: nadal 0 ekstrakcji z CLI (`d824bbac`). Wymuszone `POST …/proposals:generate {"kinds":["extraction"]}` → 2 propozycje (`a4d2d352`, `6ee5c6b8`, scope `docs.runbooks`). Konsolidacja: `no_shared_procedure` w każdym przebiegu |
| 5 | Git roundtrip | pass | decyzja `approve` → rewizja `7b77dce0…`; eksport `d70165c1-40a7-4e65-8894-1ee28231520f` (`base_commit c09af031`); `proposals apply --write` → `docs/runbooks/.agents/skills/rotate-relay-signing-keys/SKILL.md`; commit `c06a84b`; import `be352f3b` → snapshot `active`, 82 skille. **Ścieżka kandydata jest poprawna** (`docs/runbooks/…`, nie `docs.runbooks/…`) — defekt `candidatePath` z 2026-09-08 pozostaje naprawiony także dla węzła, którego nazwa jest dosłowną ścieżką |
| 6 | Publikacja i odpowiedź SEARCH/USE | pass | snapshot `repository:cbd7a08c…` → później `repository:16686c1d…`; `POST /v1/use` 200, request_id `7c123e2c-8d0b-432c-b3ce-b61eb559e40e` |
| 7 | Adapter: install → login → hook → realna sesja | pass **po naprawach D5 i D7** | `install --harness claude` (package sha256 `76b6224a…`); `login` = kod `Q7FS-S5RB`, „logged in as rehearsal@cloudfloo.test"; `index` → `cards=108 terms=8240`; hook z podkatalogu `docs/` zwrócił 3 karty, pierwsza to wyekstrahowany runbook. **Realna sesja `claude -p`** (Claude Code 2.1.272) w drzewie: model odpowiedział wyłącznie z wstrzykniętej guidance, spool `card_injected=3, search_requested=1, search_results=1` |
| 8 | Feedback → kolejka → decyzja | pass | `POST …/revisions/7b77dce0…/feedback {"verdict":"helped"}` → `judgment_id 071ac043-12d3-44fc-b046-1d7114bcbc9b`; `GET …/usage?window=30d` pokazuje `feedback:{helped:1,n:1}` |
| 9 | Drift (U9/P13) | pass | edycja źródła → import `1a9fbfb3`; pozycja kolejki `73c60fd1-44ea-402c-9395-177da39ee49d` `source_changed`, skill w `needs_review`; `POST …/usage/queue/73c60fd1…/decision {"action":"reviewed"}` → z powrotem `published` |
| 10 | Drugi harness (Copilot CLI) | **nie do wykonania tutaj** | `which copilot` i `which gemini` — brak binariów. Nic nie zostało odegrane. Wymagania dla właściciela w [ACT-01-RUNBOOK §8](../../pilot/ACT-01-RUNBOOK.md) |
| 11 | Warstwa akceptacyjna | **33 pass / 1 fail / 7 `not_measured_here`** | `GUIDEFOLD_ACCEPTANCE=1 rtk proxy python3 -m pytest tests/acceptance -q`, przebieg `2026-09-15T11:02:13Z` na czubku gałęzi (`repo_commit a285d595`), raport `.guidefold/checks/acceptance-2026-09-15.json` |

Stan bazy po całej próbie (`select … from gfm.*`, klaster `act01`): `orgs 1`, `repos 1`, `imports ready 8 / partial 1 / failed 1`, `skills published 83 / archived 25`, `publications active 1 / superseded 6 / failed 2`, `proposals draft 6 / published 1`, `decisions 1`, `tokens 2`. `gf.events`: `card_injected 14`, `search_requested 3`, `search_results 3`, `skill_load_requested 6`, `skill_load_completed 1`, `skill_feedback 1`.

### 11a. Warstwa akceptacyjna — uwaga metodyczna

`tests/acceptance/conftest.py` **buduje własny klaster PostgreSQL i własne API na wolnych portach** (`start_stack(name="acceptance")`), więc nie da się jej uruchomić „przeciwko" stosowi `act01` — brief zakładał inaczej. Trzy przebiegi tego dnia; **liczbą obowiązującą jest przebieg 3, bo jako jedyny mierzy czubek gałęzi ze wszystkimi naprawami**:

| Przebieg | Start | `repo_commit` | pass / fail / `not_measured_here` |
|---|---|---|---|
| 1 | `2026-09-15T10:33:02Z` | `2a302f5` | 31 / 3 / 7 — **odrzucony**: w trakcie przebiegu zmieniłem `skills/guidefold/scripts/guidefold`, a taka zmiana czyni każdą publikację `snapshot_policy_mismatch` (mechanizm opisany wprost w `tests/acceptance/_support.py:130`). Znaczniki czasu nie dowodzą, że to ona wywołała akurat te trzy porażki — dwie z nich zapisały się przed edycją — ale przebieg nie jest już czysty, a późniejsze czyste przebiegi nie odtworzyły dwóch z trzech. Nie liczę go jako pomiaru |
| 2 | `2026-09-15T10:38:45Z` | `5373286` | 33 / 1 / 7 — czysty, ale tylko po pierwszym z trzech commitów napraw |
| 3 | `2026-09-15T11:02:13Z` | `a285d595` (czubek gałęzi) | **33 / 1 / 7** — po wszystkich naprawach, w tym D5 (`resolve_search_config`) i D6 (`cache_source`), które dotykają dokładnie tej ścieżki, którą chodzi ACT-01. Wynik nie drgnął w żadną stronę |

Jedyna pozostała porażka to `ACT-01` (`tests/acceptance/test_act01_end_to_end.py:219`): `assert "card_injected" in kinds` przy spoolu `{'skill_load_completed': 1}`, identycznie w przebiegu 2 i 3 — patrz D8. Siedem wierszy `not_measured_here` to niezmiennie realny WorkOS, sieć pilota, realne sesje ludzi i oceny Q — każdy z podanym powodem, nigdy jako pass.

## 4. Defekty

### Naprawione w tej gałęzi (każdy z testem, czerwonym przed zmianą)

**D1 — dziesięć kart tego repozytorium jest nie do zaimportowania.** `description:` w dziesięciu `.agents/skills/*/SKILL.md` zawiera niecytowany dwukropek, co nie jest poprawnym YAML-em (`ScannerError: mapping values are not allowed here`). Loader Claude Code jest pobłażliwy i to ukrywał. Skutek: import `eadebd0a` = `accepted 403, failed 10`, stan `partial`, a `publish.build` odmówił całego snapshotu (`import_partial`) — **z `wiatrM/guidefold` nie dało się opublikować niczego**. Naprawa: zacytowane opisy (tekst po sparsowaniu identyczny co do bajtu). Test: `tests/test_frontmatter.py::test_every_skill_md_in_this_repository_has_parseable_frontmatter`. Commit `5373286`.

**D2 — `guidefold validate` nie nazywał zepsutej karty, tylko się wywracał.** Bramka, która miała złapać D1, przepuszczała `yaml.ScannerError` jako surowy traceback, więc plik nie był nazwany, a pozostałe karty nie były w ogóle sprawdzone. Naprawa: `_validate_errors` używa istniejącego już w `all_skills` callbacku `on_error`. Test: `tests/test_validate.py::test_unparseable_frontmatter_is_named_not_a_traceback`. Commit `5373286`.

**D3 — nazwana przyczyna `import_tree_has_no_guidefold_yaml` była martwym kodem.** `build()` ją miał, ale `main()` dochodzi wcześniej do `cli.load_map(tree)` dla inwentarza, więc drzewo bez mapy kończyło się `build_tree_failed: FileNotFoundError: …/guidefold.yaml` (import `54b68a73`). Właściciel czyta tę wartość z `gfm.repos.import_blocked_reason`; traceback Pythona nie jest przyczyną. Naprawa: strażnik podniesiony do punktu wejścia. Test w `tests/test_build_tree.py` uruchamia prawdziwy punkt wejścia, nie `build()`. Commit `5373286`.

**D4 — `guidefold install --harness claude` kończył się traceback'iem.** `build_card` sortował skille węzła gołym `sorted()` po parach `(name, frontmatter)`; dwa skille jednego węzła mogą mieć tę samą nazwę (to repozytorium ma `security-baseline` i w `.agents/skills/`, i w fixture Meridian), więc Python porównywał dwa słowniki: `TypeError: '<' not supported between instances of 'dict' and 'dict'`. Repozytorium zostawało w połowie zainstalowane. Naprawa: sortowanie po samej nazwie. Test: `tests/test_pivot_cli_install.py::test_install_survives_two_skills_of_one_node_sharing_a_name`. Commit `e937834`.

**D5 — `guidefold load` przez hostowane API dawał 403 dla normalnego klonu.** Z tokenem osobistym z `guidefold login` CLI wysyła `X-Guidefold-Org`/`X-Guidefold-Repo`, ale `resolve_search_config` brało repo **wyłącznie z nazwy katalogu klonu**, ignorując `GUIDEFOLD_REPO_ID` i `service.repo` z `guidefold.yaml` — czyli pierwszeństwo, które `resolve_service_config` opisuje trzy linie wyżej. Katalog `gf-pilot-core` przy repo id `guidefold` → nagłówek `X-Guidefold-Repo: gf-pilot-core` → 403 (request_id `e6776291-6e2c-4fdc-8399-c33e25a1135f`), podczas gdy identyczne żądanie ręcznie tym samym tokenem dawało 200 (`7c123e2c-8d0b-432c-b3ce-b61eb559e40e`). CLI meldował to jako „service USE failed (auth)". Test: `tests/test_pivot_cli_install.py::test_search_config_takes_the_repo_id_from_config_not_from_the_checkout_name`. Commit `1792de3`.

**D6 — nieudany `load` nigdy nie trafiał do ledgera.** Obie ścieżki błędu wysyłały `skill_load_completed` z `cache_source: null`, a to pole jest `required` i niepuste w zamrożonym `services/search/telemetry-schema.json`; ingest odrzucał zdarzenie z `missing_required_field:cache_source` (zaobserwowane trzykrotnie w `telemetry flush`). Właśnie te wiersze mówią właścicielowi, że ładowania się nie udają. Naprawa: `"service"` na ścieżce serwisowej, `"none"` na rejestrowej; test w `tests/test_telemetry_cli.py` sprawdza teraz zdarzenie wobec `required`/`nullable` z samego zamrożonego schematu. Commit `1792de3`.

### Opisane, nienaprawione (wymagają decyzji o kontrakcie albo zachowaniu)

**D7 — `guidefold extract --all` nigdy nie uruchomił grupy ekstrakcji i nie powiedział o tym.** Plan dla importu `d824bbac` z `profile=one_shot` wymienia pięć grup, w tym `extraction:docs.runbooks` z dwoma dokumentami, które naprawdę zawierają ponumerowane kroki. CLI zgłosiło `planned_groups: 2`, `groups_skipped: {}`, `proposals_by_kind: {"enrichment": 5}` i zero ekstrakcji; uruchomiły się dwa zadania `proposal.generate`. Wymuszone `POST …/proposals:generate {"kinds":["extraction"]}` na tym samym imporcie natychmiast dało dwie propozycje. Skutek: właściciel może uruchomić `extract` na produkcji, zobaczyć „5 propozycji" i nie dowiedzieć się, że ekstrakcja w ogóle nie została podjęta. Reprodukcja: powyższe dwa wywołania na repozytorium z więcej niż `max_groups` grupami w planie.

**D8 — w scenariuszu ACT-01 `find` nie zapisuje `card_injected`.** Jedyna porażka czystego przebiegu acceptance: spool zawiera `{'skill_load_completed': 1}` bez `card_injected`. W mojej próbie na backendzie lokalnym `find` **zapisuje** `card_injected` (8 zdarzeń), a realna sesja `claude -p` zapisała 3 — więc luka jest specyficzna dla ścieżki, którą chodzi acceptance (`backend: service`). Bez tego „sesja z SEARCH i LOAD w ledgerze" z PRODUCT-FOCUS nie jest policzalna. Reprodukcja: `GUIDEFOLD_ACCEPTANCE=1 python3 -m pytest tests/acceptance/test_act01_end_to_end.py -q`.

**D9 — publikacja odmawia całego snapshotu, gdy import jest `partial`.** `publish.build` → `import_partial` przy `accepted 403 / failed 10`. PRODUCT-PIVOT U2.1 mówi, że jeden zepsuty plik ma upaść sam, a reszta importu ma zostać przyjęta; pliki rzeczywiście upadają pojedynczo, ale publikacja i tak nie powstaje. To decyzja produktowa (albo publikować częściowo z jawną adnotacją, albo utrzymać obecne zachowanie i wyraźnie to komunikować), nie łatka.

**D10 — `/v1/use` przyjmuje `card_revision`, a katalog zwraca `revision_id`.** `GET {repo_base}/skills/{skill_id}` podaje oba pola; użycie `revision_id` w `POST /v1/use` daje 409 `revision_mismatch` (request_id `7c1f40c3-dd07-4da9-9a76-926cfdbdc284`), a `card_revision` — 200. `guidefold find` drukuje właściwe, ale każde narzędzie czytające katalog trafi na złe. Warto to nazwać w [API-CONTRACT](../../API-CONTRACT.md) §4.3.

**D11 — `telemetry flush` przegrywa wyścig z automatycznym flushem.** Po `load` z włączonym auto-uploadem ręczny `telemetry flush` kończy się `FileNotFoundError: …/spool/local/dev/events-2026-09-15.jsonl` (surowy traceback) — automatyczny flush zdążył usunąć plik. Zdarzenia nie giną, ale komenda kończy się błędem.

**D12 — CLI mapuje każdą nieudaną odpowiedź `/v1/use` na „(auth)".** 403, 409 `revision_mismatch` i 503 `snapshot_policy_mismatch` są pokazane użytkownikowi tym samym słowem. To właśnie sprawiło, że D5 wyglądał na problem z logowaniem. Naprawa jest mała, ale dotyka komunikatów w pięciu miejscach `cmd_load`; zostawiam ją do osobnej zmiany, żeby nie mieszać jej z naprawą przyczyny.

## 5. Obejścia konfiguracyjne, które okazały się konieczne (to nie są defekty, tylko wymagania)

1. **`guidefold.yaml` musi istnieć w drzewie importu.** `scan` działa bez niego (`GUIDEFOLD_ROOT` wystarcza, 413 plików, 108 sugestii), blokuje dopiero worker. Na produkcji trzeba albo wpisać ten plik do `wiatrM/guidefold`, albo wziąć zmianę zero-config (PR z `feat/zero-config-scope-map`) — ta próba **nie zależy** od tamtej gałęzi.
2. **`.guidefoldignore` z `examples/monorepo/` przed pierwszym importem.** Bez tego skille fixture Meridian trafiają do organizacji jako `urn:skill:cloudfloo:_root:*`, ale ich `metadata.requires` nadal wskazuje `urn:skill:meridian:*`, więc publikacja pada na 12 znaleziskach `missing_dependency`. Dodanie wykluczenia **po** imporcie archiwizuje 25 skilli i wypełnia kolejkę właściciela 26 pozycjami `source_removed` — dokładnie to zdarzyło się w tej próbie.
3. **Płaska mapa `_root` psuje trzy osie i kartę scope.** Przy 81 skillach w jednym węźle Map ma jeden scope, Pyramid jedną warstwę (`unclassified`, 106 pozycji), a `materialize` przerywa z „scope card for `_root` exceeds 80 lines", przez co `install` nie zbudował artefaktu indeksu i hook był bezczynny do ręcznego `guidefold index`. Trzy węzły (`_root`, `docs`, `docs.runbooks`) usunęły wszystkie trzy objawy.

## 6. Uczciwe ograniczenia

- Wszystko powyżej to **R**. Jedna organizacja, jedna maszyna, loopback, provider `dev` zamiast WorkOS, generator `deterministic` zamiast modelu. Nic tu nie jest dowodem wartości ani dowodem P ([pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md)).
- **Drugi harness nie został sprawdzony.** `copilot` i `gemini` nie istnieją na tej maszynie. Szablony hooków są w `skills/guidefold/hooks/`, ale żadna sesja Copilota nie została odegrana i żaden wiersz macierzy adapterów nie może zostać wypełniony tym raportem (#82, #83).
- **Realna sesja `claude -p` została wykonana**, ale jej operatorem był agent budujący Guidefolda, a nie deweloper spoza zespołu. Dowodzi plumbingu (hook → SEARCH → `card_injected` → ledger), nie użyteczności. Sesja PRODUCT-FOCUS wymaga nazwanej osoby, która nie budowała tego produktu.
- **Propozycje ekstrakcji powstały z dwóch runbooków napisanych na potrzeby tej próby** (ten sam szablon, którego używa `tests/acceptance/_support.py::add_runbooks`). To dane syntetyczne, `n=2`; nie dowodzą, że deterministyczny generator znajdzie cokolwiek w prawdziwych dokumentach tego repozytorium — przeciwnie, na 20 prawdziwych dokumentach abstynował za każdym razem.
- **Konsolidacja („jeden wspólny element") nie została zademonstrowana wcale.** Każde uruchomienie kończyło się `no_shared_procedure`.
- Zapytania dowodowe na `gf.events` mogą używać wyłącznie kolumn `event_id, event_type, occurred_at, received_at, schema_version, tenant_id, search_id, load_id` — `payload` jest `bytea`, więc `payload->>'…'` nie zadziała.

## 7. Co dalej

Kolejność produkcyjna i pełna lista przedlotowa są w [ACT-01-RUNBOOK](../../pilot/ACT-01-RUNBOOK.md). Z tego raportu wynikają trzy rzeczy, których nie da się rozwiązać bez właściciela: uprawnienie „Email addresses: Read-only" w GitHub App, decyzja `guidefold.yaml`-albo-zero-config, oraz nazwany deweloper spoza zespołu wraz z terminem jego sesji.
