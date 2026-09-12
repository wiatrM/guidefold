# Kontrakt API i danych Guidefold

Status: obowiązujący kontrakt implementacyjny, `contract_version: 1.4.0`. Data: 2026-09-12.
Cel: jedno źródło prawdy dla endpointów, DTO, kodów błędów, schematu bazy, maszyn stanów i kontraktu API–worker pivotu, tak aby każde AC poziomu R z PRD dało się sprawdzić.
Wejścia: [PRODUCT-PIVOT](PRODUCT-PIVOT.md) (U1–U11), [PIVOT-ARCHITECTURE](PIVOT-ARCHITECTURE.md) (moduły, kontrakt API–worker, trzy bramki), [PIVOT-BACKLOG](PIVOT-BACKLOG.md) (P01–P15), [ADR-0031](adr/ADR-0031-monorepo-to-managed-skill-library.md), [ADR-0033](adr/ADR-0033-api-contract-first-and-mvp-storage.md), [07-frontend](ui/pipeline/07-frontend.md) (§Granice danych, §Offline i awarie), kod `services/search/internal/{mgmt,jobs,schema,worker}` i `ui/src/api/` odczytany 2026-09-06.
Zakres zastępowania: zastępuje roboczy brief implementacyjny (`CONTRACT-BRIEF.md`, kopia robocza poza repozytorium). **Nie zastępuje** [HARNESS-SERVICE-CONTRACT 1.1](HARNESS-SERVICE-CONTRACT.md) ani [SEARCH-USE-TELEMETRY](SEARCH-USE-TELEMETRY.md); dla `/v1/search`, `/v1/use`, `/v1/events:batch` te dokumenty pozostają normatywne, a niniejszy dodaje wyłącznie warstwę tożsamości org i addytywne `1.2`.

Aliasy ścieżek używane w §4 (rozwijane dosłownie przez checker):

- `{org_base}` = `/api/v1/orgs/{org}`
- `{repo_base}` = `/api/v1/orgs/{org}/repos/{repo}`

## 1. Zasada nadrzędna: kontrakt przed kodem

1. Ten dokument jest źródłem prawdy. Handler, tabela, migracja, job, DTO, dekoder UI i komenda sieciowa CLI zmieniają się **wyłącznie razem** ze zmianą tego dokumentu w tej samej zmianie (PR). Kod, który wprowadza endpoint, kolumnę lub kod błędu nieopisany tutaj, jest defektem, nie rozszerzeniem.
2. Kierunek asymetrii jest zamierzony: kontrakt może wyprzedzać kod (pozycja zaplanowana, jeszcze nieimplementowana), kod nie może wyprzedzać kontraktu.
3. Procedura zmiany: (a) edycja tego pliku, (b) `contract_version` według §10, (c) wpis w §11, (d) `services/search/openapi/management-v1.yaml`, (e) kod i testy, (f) `python3 tools/contract/check_api_contract.py`, (g) opis różnicy kontraktu w PR.
4. Zmiana, która przesuwa granicę modułu z [module-boundaries-go](../.agents/skills/module-boundaries-go/SKILL.md) albo dotyka jednej z trzech bramek technicznych (tożsamość per request, kontrakt pakietów 1.2, zaufana publikacja), wymaga dodatkowo ADR w `docs/adr/`.
5. Weryfikacja mechaniczna: `tools/contract/check_api_contract.py` porównuje tabele endpointów z `paths:` w OpenAPI i z rejestracjami tras w Go (`mgmt.Router.Handle`, `HandleFunc`), sekcję §7 z `CREATE TABLE`/`ALTER TABLE ... ADD COLUMN` w migracjach Go, oraz listę kodów błędów §3 z literałami w `fail(...)` i konstruktorach `mgmt.Fail/Invalid/NotFound/Conflict/Unprocessable`. Wzorce rejestracji tras są konfigurowalne w `ROUTE_PATTERNS` na górze skryptu; zmiana stylu routera wymaga dopisania wzorca tam i wzmianki tutaj.
6. Ten dokument opisuje zachowanie docelowe. Obecność pozycji tutaj **nie jest dowodem wdrożenia**; dowodem są kod, testy i raport z identyfikatorem przebiegu ([DOCUMENTATION-RULES](DOCUMENTATION-RULES.md)).

## 2. Tożsamość i autoryzacja

Każde żądanie `/api/v1/*` i `/v1/*` rozstrzyga `Principal` **przed** handlerem, z bazy, bez cache między żądaniami (bramka 1). Struktura odpowiada `services/search/internal/mgmt/principal.go`.

| Pole `Principal` | Typ | Znaczenie |
|---|---|---|
| `UserID` | uuid, puste dla tokenu maszynowego | Człowiek stojący za żądaniem |
| `OrgID` | uuid | Tenant żądania; jedyne źródło `tenant` dla schematu `gf` |
| `RepoID` | text, opcjonalne | Ustawione, gdy token jest związany z jednym repo |
| `Role` | `owner`\|`member`\|puste | Rola wynikająca z membership, nie z claimu klienta |
| `Scopes` | []text | Zakresy tokenu; sesja i token osobisty mają zakresy dostawy z definicji |
| `Source` | `session`\|`personal`\|`installation`\|`ci`\|`operator` | Skąd pochodzi tożsamość |
| `TokenID`, `SessionID`, `CSRF` | text | Identyfikatory do audytu, idempotencji i double-submit |

| Źródło | Nośnik | Nadaje | Zakresy |
|---|---|---|---|
| Sesja | cookie `gf_session`, HttpOnly, Secure (wyłączane tylko `GUIDEFOLD_INSECURE_COOKIES=true` lokalnie), SameSite=Lax, TTL 7 dni, rekord w `gfm.sessions` z `revoked_at` | Wszystkie operacje zgodne z rolą | wszystkie (domyślnie) |
| Token osobisty | `Authorization: Bearer gf_…` | Działa w imieniu użytkownika i jego membershipów | `user`, `search`, `use`, `events` |
| Token instalacji | `Authorization: Bearer gf_…` | Org (+ opcjonalnie repo) | podzbiór `search use events`; nigdy `import`, `publish`, `membership` |
| Token CI | `Authorization: Bearer gf_…` | Org (+ repo) | podzbiór `validate import generate`; nigdy `publish`, `membership` ani zakresy dostawy |
| Operator (legacy) | dotychczasowy bearer token z konfiguracji | Zachowuje obecne zachowanie testów `/v1/*` | wszystkie w obrębie skonfigurowanego tenant/repo |

Dla `/v1/search`, `/v1/use` i `/v1/events:batch` schemat JSON zostaje przy `1.1` bez zmian (schemat harnessu odrzuca nieznane pola najwyższego poziomu), więc wybór organizacji i repozytorium dla principali `session` i `personal` nie może wejść do ciała żądania — pochodzi z nagłówków `X-Guidefold-Org: <org_id|slug>` i `X-Guidefold-Repo: <repo_id>` (nagłówki opisane w §3). Kolejność rozstrzygania dla tych trzech endpointów: wiązanie tokenu (org, a opcjonalnie repo, gdy token instalacji lub CI jest do nich związany) > nagłówki `X-Guidefold-Org`/`X-Guidefold-Repo` > `workspace.repo_id` z ciała żądania (1.1) > jedyne membership principala albo jedyne repo organizacji, gdy wcześniejsze źródła milczą. Nagłówek sprzeczny z wiązaniem tokenu instalacji kończy się `403 organization_not_permitted` (org) albo `403 repository_not_permitted` (repo). Token operatora (legacy) nie czyta tych nagłówków — zachowuje dotychczasowe tenant/repo ze zmiennych środowiskowych.

Zakresy tokenu CI rozszerzono z samego `validate` do podzbioru `validate import generate`, bo `guidefold extract` w CI (§5.6, CONVENTIONS `extract`) musi zaimportować drzewo i zlecić generowanie propozycji. Zakresy tokenu instalacji **nie zmieniają się**: adapter nadal dostaje wyłącznie podzbiór `search use events`. Token CI nadal nie może publikować ani zmieniać membership — propozycje wymagają decyzji właściciela, a publikacja osobnego joba. Żądanie z zakresem spoza wydanego tokenu to `403 insufficient_token_scope` z nazwą brakującego zakresu w `details.required_scope`; nazwa zakresu nigdy nie niesie sekretu.

Reguły:

- Membership i ważność tokenu są sprawdzane **przy każdym żądaniu**. Odwołanie działa na API natychmiast; 60 s z U3.4 dotyczy wyłącznie cache UI (§9).
- Dostęp do organizacji, której principal nie jest członkiem, oraz do organizacji nieistniejącej daje **identyczny** `403 forbidden` bez `details`. Nigdy 404; 404 występuje wyłącznie wewnątrz własnej org.
- Member czyta, owner mutuje. Wyjątki: feedback do skilla (member), akceptacja zaproszenia (zapraszany).
- Tokeny są przechowywane jako SHA-256; sekret pokazywany jednorazowo w odpowiedzi tworzącej. Sekret nigdy nie trafia do URL, logu, telemetrii ani `details`.
- Tokeny (personalny, instalacji, CI) są w MVP wyłącznie odwoływalne: `gfm.tokens` nie ma kolumny `expires_at` (YAGNI); jedyną drogą unieważnienia jest `revoked_at`. Dotyczy to również tokenu osobistego wydanego przez device flow — nie różni się od innych tokenów osobistych. `POST /api/v1/auth/logout` odwołuje wyłącznie sesję (cookie `gf_session`); token osobisty CLI odwołuje się osobno, jawnym `guidefold logout`, więc wylogowanie z UI nigdy nie zrywa niepowiązanej sesji CLI.
- Mutacje z sesji wymagają nagłówka `X-CSRF-Token` równego `csrf_token` sesji (double submit). Tokeny bearer nie podlegają CSRF, bo przeglądarka ich nie dosyła automatycznie.
- Device flow: `POST /api/v1/auth/device` bez uwierzytelnienia zwraca `device_code`/`user_code`; zatwierdzenie wymaga sesji i CSRF; wymiana na token zwraca token osobisty o zakresie `user`. Brak sekretu klienta OAuth.
- Łączenie tożsamości jest jawne: `POST /api/v1/me/identities/link/start` wiąże `state` z bieżącą sesją. Sam zgodny e-mail nigdy nie łączy kont automatycznie; powstaje osobny użytkownik, a `GET /me` zwraca `link_suggestions`.
- Dostawca: `GUIDEFOLD_AUTH=dev|workos`. Provider `dev` jest wyłączony, dopóki nie zostanie ustawiony jawnie. Klucz WorkOS pochodzi z `WORKOS_API_KEY_FILE` i nigdy nie jest logowany. Nie żądamy zakresów OAuth do kodu repozytorium.

## 3. Koperta odpowiedzi, nagłówki, błędy, stronicowanie, idempotencja

Sukces zawiera `schema_version` (`mgmt-1` dla `/api/v1`, `1.1`/`1.2` dla `/v1`), `request_id`, a gdy dotyczy — `org_id`, `repo_id`, `snapshot_id`. Błąd ma zawsze kształt:

```json
{"error": "<snake_case_code>", "message": "…", "request_id": "…", "details": {…}}
```

`details` jest opcjonalne, maszynowe (np. `{"missing": ["sha…"]}`, `{"current_revision": "…"}`) i nigdy nie zawiera sekretów, e-maili ani treści repozytorium. Dla statusów ≥500 `details` jest usuwane, a przyczyna trafia wyłącznie do logu.

| Nagłówek | Kierunek | Reguła |
|---|---|---|
| `X-Request-Id` | request/response | Klient może podać `[A-Za-z0-9_-]{8,64}`; wszystko inne jest zastępowane wygenerowanym. Zawsze w odpowiedzi i w polu `request_id`. |
| `Idempotency-Key` | request | Wymagany dla mutacji oznaczonych w §4; alternatywnie pole `idempotency_key` w ciele. Maks. 200 znaków. |
| `X-CSRF-Token` | request | Wymagany dla mutacji z sesji; równy `csrf_token` z `GET /api/v1/me`. |
| `X-Guidefold-Org` | request | Tylko `/v1/search`, `/v1/use`, `/v1/events:batch`: `org_id` (uuid) albo slug organizacji dla principali `session`/`personal`. Kolejność źródeł i sprzeczność z wiązaniem tokenu → §2. |
| `X-Guidefold-Repo` | request | Jak `X-Guidefold-Org`, dla `repo_id`. Sprzeczność z repo, do którego jest związany token instalacji, daje `403 repository_not_permitted`. |
| `Idempotent-Replay` | response | `true`, gdy zwrócono zapamiętaną odpowiedź zamiast wykonania pracy; `false` na trasach o odpowiedzi „na żywo" (poniżej), gdzie powtórzenie uruchamia handler ponownie. |
| `Retry-After` | response | Sekundy przy 429 i 503. Klient GET ponawia najwyżej 2 razy z backoffem, honorując tę wartość. |
| `Cache-Control: no-store` | response | Na każdej odpowiedzi `/api/v1` i `/v1`. Prywatne dane nie trafiają do trwałego cache. |
| `X-Content-SHA256` | response | Przy pobraniu dokładnych bajtów rewizji lub zasobu. |

### Statusy HTTP

| Status | Znaczenie w tym API |
|---|---|
| 200 / 201 / 204 | Sukces; 201 dla utworzenia zasobu, 204 dla usunięcia |
| 400 | Nieprawidłowe żądanie: schemat, typ, nieznane pole, limit wartości, zły kursor |
| 401 | Brak lub nieważne poświadczenie |
| 403 | Brak uprawnień, w tym każdy dostęp poza własną org; także nieudany CSRF |
| 404 | Zasób nie istnieje **wewnątrz własnej org** |
| 409 | Konflikt stanu: nieaktualna rewizja, brakujące bloby, kolizja idempotencji, zmiana snapshotu |
| 413 | Ciało lub blob ponad limit |
| 422 | Żądanie poprawne składniowo, niewykonalne merytorycznie (graf, walidacja publikacji) |
| 429 | Przeciążenie lub limit; z `Retry-After` |
| 500 | Błąd wewnętrzny; `details` usunięte |
| 502 | Zewnętrzny dostawca tożsamości odpowiedział błędem lub nie odpowiedział |
| 503 | Zależność niedostępna (baza, snapshot, worker dense) |
| 504 | Przekroczony deadline z ciała żądania (tylko `/v1`) |

### Kody błędów

Lista jest zamknięta: handler nie zwraca kodu spoza tej tabeli. „1.1" oznacza kod istniejący w kontrakcie retrieval i pozostawiony bez zmian.

| Kod | HTTP | Kiedy | Moduł |
|---|---|---|---|
| `invalid_body` | 400 | Ciała nie da się odczytać lub jest puste tam, gdzie wymagane | mgmt |
| `invalid_json` | 400 | Ciało nie jest poprawnym JSON-em dla tego endpointu (nieznane pole włącznie) | mgmt |
| `invalid_request` | 400 | Wartość pola poza dziedziną, gdy nie ma kodu szczegółowego | mgmt |
| `invalid_form` | 400 | Formularz (dev login) nieczytelny | identity |
| `invalid_email` | 400 | E-mail nie przechodzi walidacji | identity |
| `invalid_profile` | 400 | Nazwa profilu jest pusta albo przekracza 120 znaków | identity |
| `invalid_name` | 400 | Nazwa org lub instalacji poza dopuszczalnym zakresem | identity |
| `invalid_slug` | 400 | Slug spoza `[a-z0-9-]{2,40}` | identity |
| `invalid_role` | 400 | Rola inna niż `owner`/`member` | identity |
| `invalid_kind` | 400 | Rodzaj tokenu lub zasobu spoza dziedziny | identity |
| `invalid_scopes` | 400 | Zakresy tokenu spoza dozwolonego zbioru | identity |
| `invalid_repo_id` | 400 | `repo_id` spoza `[A-Za-z0-9_.-]{1,64}` | identity |
| `invalid_user_id` | 400 | `user_id` nie jest UUID | identity |
| `invalid_access` | 400 | Repozytoryjny grant musi być `read` albo `write` | identity |
| `invalid_team` | 400 | Nazwa teamu pusta albo dłuższa niż 80 znaków | identity |
| `invalid_provider` | 400 | Dostawca modelu spoza dziedziny (`openrouter`) | secrets |
| `credential_invalid` | 400 | Dostawca odrzucił klucz podany przy zapisie (ADR-0043 §5) | secrets |
| `invalid_prompt` | 400 | Polecenie przebiegu puste albo dłuższe niż 4000 znaków | live |
| `invalid_model` | 400 | Model spoza listy dozwolonej dla tej organizacji | live |
| `team_exists` | 409 | W tej organizacji istnieje już team o tej nazwie | identity |
| `team_not_found` | 404 | Team nie należy do tej organizacji | identity |
| `team_member_not_found` | 404 | Osoba nie należy do tego teamu | identity |
| `invalid_identity` | 400 | Dane tożsamości od dostawcy niekompletne | identity |
| `invalid_state`, `expired_state` | 400 | `state` OAuth nieznany albo przeterminowany | identity |
| `invalid_callback` | 400 | Callback bez `code`/`state` lub z błędem dostawcy | identity |
| `unknown_provider` | 400 / 404 | Dostawca spoza `google`/`github` | identity |
| `invalid_webhook_signature` | 401 | Podpis `X-Hub-Signature-256` nie zgadza się z sekretem aplikacji GitHub (ADR-0036) | github |
| `github_app_not_configured` | 503 | Serwer nie ma klucza aplikacji GitHub albo sekretu webhooka; instalacja nie jest przyjmowana | github |
| `installation_not_found` | 404 | Organizacja nie ma tej instalacji aplikacji GitHub | github |
| `invalid_cursor` | 400 | Kursor nieczytelny lub niezwiązany z tym zapytaniem | mgmt |
| `invalid_filter_value` | 400 | Filtr o nieznanej wartości, gdy endpoint nie zwraca `filters` | mgmt |
| `org_required`, `organization_required` | 400 | Operacja wymaga kontekstu organizacji, którego nie podano (`org_required` w routerze, `organization_required` przy tokenie) | mgmt, identity |
| `repository_required` | 400 | Operacja wymaga `repo_id`, którego token ani ścieżka nie dostarczają | identity |
| `tenant_and_repository_required` | 400 | `/v1/*`: nie da się rozstrzygnąć tenanta i repozytorium żądania | retrieval |
| `idempotency_key_required` | 400 | Mutacja idempotentna bez klucza | mgmt |
| `idempotency_key_invalid` | 400 | Klucz idempotencji ponad 200 znaków | mgmt |
| `blob_digest_mismatch` | 400 | Wgrany blob ma inny sha256 niż ścieżka | import |
| `blob_not_in_manifest` | 400 | Wgrywany hash nie występuje w manifeście importu | import |
| `unsupported_manifest_format` | 400 | `format` manifestu inny niż `guidefold-import-manifest-v1` | import |
| `authorization_pending` | 400 | Device flow: użytkownik jeszcze nie zatwierdził | identity |
| `slow_down` | 400 | Device flow: odpytywanie częściej niż `interval` | identity |
| `expired_token` | 400 | Device flow: `device_code` wygasł | identity |
| `access_denied` | 400 | Device flow: użytkownik odmówił | identity |
| `unauthenticated` | 401 | Brak lub nieważna sesja/token | mgmt |
| `unauthorized` | 401 | 1.1: brak bearer tokenu operatora na `/v1` | retrieval |
| `forbidden` | 403 | Brak członkostwa lub org nie istnieje (identyczne ciało) | mgmt |
| `insufficient_token_scope` | 403 | Token nie ma zakresu wymaganego przez endpoint | identity |
| `organization_not_permitted` | 403 | Token jest związany z inną org niż żądana; również `X-Guidefold-Org` sprzeczny z wiązaniem tokenu instalacji na `/v1/search`, `/v1/use`, `/v1/events:batch` (§2) | identity |
| `repository_not_permitted` | 403 | Token jest związany z innym repo niż żądane; również `X-Guidefold-Repo` sprzeczny z wiązaniem tokenu instalacji na tych samych endpointach (§2) | identity |
| `csrf_token_mismatch` | 403 | Brak lub zły `X-CSRF-Token` przy mutacji z sesji | mgmt |
| `skill_outside_resolved_scope` | 403 | 1.1: USE poza rozwiązanym scope | retrieval |
| `not_found` | 404 | Zasób nie istnieje we własnej org lub nieznana ścieżka `/api/` | mgmt |
| `member_not_found` | 404 | Nieznany członek tej org | identity |
| `repo_access_not_found` | 404 | Członek nie ma jawnego grantu do tego repozytorium | identity |
| `reviewer_not_found` | 404 | Osoba nie jest przypisana jako reviewer tego repozytorium | identity |
| `invitation_not_found` | 404 | Nieznany token zaproszenia | identity |
| `installation_not_found` | 404 | Nieznana instalacja w tej org | identity |
| `device_code_not_found` | 404 | `user_code` nieznany, zużyty lub wygasły | identity |
| `credential_not_found` | 404 | Organizacja nie ma klucza dla tego dostawcy | secrets |
| `live_run_not_found` | 404 | Nieznany przebieg Live Agenta we własnej org | live |
| `import_not_found` | 404 | Nieznany `import_id` we własnej org | import |
| `revision_not_found` | 404 | Nieznana rewizja; nigdy podmiana na najnowszą | knowledge |
| `proposal_not_found` | 404 | Nieznana propozycja | review |
| `export_not_found` | 404 | Nieznany eksport | review |
| `skill_not_found` | 404 | 1.1 i mgmt: nieznany `skill_id` | retrieval/knowledge |
| `stale_revision` | 409 | `expected_revision` nie zgadza się z bieżącą; `details.current_revision` | review |
| `last_owner_protected` | 409 | Usunięcie/degradacja ostatniego ownera org | identity |
| `blobs_missing` | 409 | `finalize` przed wgraniem wszystkich blobów; `details.missing` | import |
| `idempotency_payload_mismatch` | 409 | Ten sam klucz z innym payloadem | mgmt |
| `idempotency_in_progress` | 409 | Żądanie z tym kluczem jeszcze trwa | mgmt |
| `import_already_finalized` | 409 | Upload lub `finalize` po finalizacji | import |
| `import_not_ready` | 409 | `publish` importu w stanie, z którego nie powstanie snapshot (`created`, `uploading`, `failed`, `cancelled`); `queued`/`parsing` są w locie i job je obsługuje | review |
| `slug_taken` | 409 | Slug organizacji zajęty | identity |
| `member_exists` | 409 | Zaproszenie e-maila, który jest już członkiem tej organizacji | identity |
| `invitation_used`, `invitation_expired` | 409 | Zaproszenie zużyte albo po `expires_at` | identity |
| `identity_already_linked` | 409 | Tożsamość dostawcy należy już do innego użytkownika | identity |
| `proposal_state_invalid` | 409 | Eksport lub decyzja w stanie, który tego nie dopuszcza | review |
| `snapshot_changed` | 409 | 1.2: snapshot zmienił się między SEARCH a USE | retrieval |
| `job_fenced` | 409 | Zapis workera ze starą generacją | jobs |
| `live_run_already_active` | 409 | Organizacja ma już trwający przebieg; `details.run_id` wskazuje który (ADR-0044 §6) | live |
| `live_run_not_cancellable` | 409 | Przebieg już się zakończył; anulowanie nic nie zmienia | live |
| `model_credential_missing` | 409 | Organizacja nie ma klucza modelu, więc przebiegu nie da się uruchomić | live |
| `revision_mismatch` | 409 | 1.1: żądana rewizja nie jest bieżąca | retrieval |
| `revision_unavailable` | 409 | 1.1: rewizji nie ma w aktywnym snapshocie; management: rewizja istnieje, ale jej surowe bajty wygasły (`.../raw`) — nigdy podmiana na inną rewizję | retrieval, knowledge |
| `skill_not_active` | 409 | 1.1: skill nieaktywny w snapshocie | retrieval |
| `repository_mismatch` | 409 | 1.1: `workspace.repo_id` inny niż załadowany | retrieval |
| `repository_revision_mismatch` | 409 | 1.1: `workspace.revision` inny niż snapshot | retrieval |
| `body_too_large` | 413 | Ciało ponad limit endpointu | mgmt |
| `blob_too_large` | 413 | Blob ponad `max_blob_bytes` | import |
| `batch_too_large` | 413 | 1.1: partia zdarzeń ponad limit | telemetry |
| `skill_body_exceeds_budget` | 413 | 1.1: body ponad `budget.max_bytes` | retrieval |
| `limit_exceeded` | 422 | Manifest ponad `max_files`/`max_total_bytes`; nigdy ciche obcięcie | import |
| `graph_cycle` | 422 | Cykl `requires`/`refines`; `details.path` | review |
| `missing_dependency` | 422 | Brak wymaganej zależności w snapshocie | review |
| `missing_required_resource` | 422 | Wymagany zasób pakietu nieobecny | review |
| `invalid_candidate_change` | 422 | `edit` zmienił frontmatter, scope, ownera lub relacje | review |
| `scope_widening_not_approved` | 422 | Podniesienie scope bez 2 źródłowych scope'ów lub bez ownera docelowego | review |
| `consolidation_sources_insufficient` | 422 | Wspólny element z mniej niż 2 źródłami `derived_from` | review |
| `ambiguous_workspace_path` | 422 | 1.1 | retrieval |
| `unmapped_workspace_path` | 422 | 1.1 | retrieval |
| `too_many_resolved_scopes` | 422 | 1.1 | retrieval |
| `overloaded` | 429 | Brak wolnych slotów SEARCH/USE; `Retry-After: 1` | retrieval |
| `telemetry_overloaded` | 429 | Brak wolnych slotów telemetrii | telemetry |
| `internal_error` | 500 | Nieoczekiwany błąd; przyczyna tylko w logu | mgmt |
| `provider_unavailable` | 502 | Dostawca tożsamości niedostępny lub odpowiedział błędem | identity |
| `backend_unavailable` | 503 | 1.1: backend retrieval niedostępny | retrieval |
| `database_unavailable` | 503 | Baza niedostępna dla management API | mgmt |
| `secret_encryption_unavailable` | 503 | Serwer nie ma klucza głównego sekretów; klucza organizacji nie da się zapisać ani otworzyć (ADR-0043 §6) | secrets |
| `empty_snapshot` | 503 | 1.1 | retrieval |
| `snapshot_not_published` | 503 | 1.1 | retrieval |
| `snapshot_policy_mismatch` | 503 | 1.1 | retrieval |
| `snapshot_encoder_mismatch` | 503 | 1.1 | retrieval |
| `snapshot_embeddings_unavailable` | 503 | 1.1 | retrieval |
| `router_index_not_published` | 503 | 1.1 | retrieval |
| `router_index_count_mismatch` | 503 | 1.1 | retrieval |
| `dense_worker_unavailable` | 503 | 1.1 | retrieval |
| `dense_worker_identity_mismatch` | 503 | 1.1 | retrieval |
| `invalid_dense_response` | 503 | 1.1 | retrieval |
| `deadline_exceeded` | 504 | 1.1: deadline z ciała żądania | retrieval |
| `invalid_payload` | 400 | 1.1 | retrieval |
| `invalid_query` | 400 | 1.1 | retrieval |
| `invalid_node` | 400 | 1.1 | retrieval |
| `invalid_integer` | 400 | 1.1 | retrieval |
| `invalid_context_value` | 400 | 1.1 | retrieval |
| `invalid_request_schema` | 400 | 1.1 | retrieval |
| `unsupported_schema_version` | 400 | 1.1 | retrieval |
| `missing_events_list` | 400 | 1.1 | telemetry |

### Stronicowanie, limity, idempotencja

- Listy zwracają `{items: [...], next_cursor: str|null}`. Kursor jest nieprzezroczysty, zawiera org, zasób, znormalizowane filtry i pozycję; kursor z innego zapytania to `400 invalid_cursor`. `limit` domyślnie 50, maksymalnie 100 (relacje: 200, mapa: start ≤100, twardy limit renderu 200 po stronie UI).
- Porządek list jest deterministyczny i zawiera klucz rozstrzygający: katalog `name asc, skill_id asc`; importy, propozycje i audyt `created_at desc, id desc`.
- Nieznana wartość filtru w katalogu **nie** cofa się do „All": odpowiedź to 200 z pustym `items` i `filters: {"scope": {"value": "…", "available": false}}`.
- Limity ciał: management JSON 1 MiB (`mgmt.DefaultBodyLimit`); blob `max_blob_bytes` 8 MiB; import `max_total_bytes` 100 MiB i `max_files` 100 000; `/v1/search`, `/v1/use` 16 KiB (1.1, bez zmian).
- Idempotencja: klucz jest zajmowany **przed** wykonaniem handlera w `gfm.idempotency` (PK `(org_id, principal_id, key)`), razem z `payload_sha256` = sha256(`METODA ŚCIEŻKA\n` + ciało). Ten sam klucz i ten sam payload → zapamiętana odpowiedź bajt w bajt z `Idempotent-Replay: true`. Ten sam klucz i inny payload → `409 idempotency_payload_mismatch`. Klucz zajęty przez trwające żądanie → `409 idempotency_in_progress`. Nieudana mutacja zwalnia klucz, więc porażka nigdy nie jest odtwarzana jako sukces.
- **Odpowiedź „na żywo".** Trasy `POST {org_base}/repos`, `POST {repo_base}/imports`, `.../finalize` i `.../cancel` zajmują klucz tak samo (równoległy duplikat dostaje `409 idempotency_in_progress`, inny payload `409 idempotency_payload_mismatch`), ale powtórzenie z tym samym payloadem **wykonuje handler ponownie** i odpowiada `Idempotent-Replay: false`. Ich ciało jest widokiem bieżącego stanu: odtworzenie pierwszej odpowiedzi `POST …/imports` kazałoby wznowionej synchronizacji wysłać bloby, które serwer już ma — czyli dokładnie ten przypadek, dla którego klucz istnieje (U1.4). Gwarancja „bez podwójnej pracy" pochodzi tam z samego zasobu: jeden import na `manifest_digest`, jeden job na `idempotency_key`. Trasy, których odpowiedź jest zapisem faktu (`.../feedback` → `judgment_id`), odtwarzają ciało jak dotąd.
- Idempotencja nie zamraża autoryzacji: uprawnienia są sprawdzane ponownie przy każdym odtworzeniu.

## 4. Endpointy

Kolumna „Idem." oznacza wymagany `Idempotency-Key`. Kolumna „P / AC" wskazuje historię backlogu i acceptance criteria PRD, które endpoint realizuje.

### 4.1 Identity (P01, P02 — U3)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/openapi.yaml` | publiczny | — | YAML kontraktu | — | nie | P02 |
| GET | `/api/v1/auth/providers` | publiczny | — | `AuthProviders` | — | nie | P01 / U3.1 |
| GET | `/api/v1/auth/login/{provider}` | publiczny | `return_to` (ścieżka względna) | 302 do dostawcy | `invalid_request` | nie | P01 / U3.1 |
| GET | `/api/v1/auth/dev` | publiczny, tylko `GUIDEFOLD_AUTH=dev` | — | formularz HTML | `not_found` | nie | P01 |
| POST | `/api/v1/auth/dev` | publiczny, tylko `dev` | form `provider,subject,email,name,return_to` | 302 + cookie sesji | `invalid_request` | nie | P01 |
| GET | `/api/v1/auth/callback` | publiczny | `code`, `state` | 302 + cookie sesji | `invalid_request`, `unauthenticated` | nie | P01 / U3.1 |
| POST | `/api/v1/auth/logout` | sesja | — | 204 | `csrf_token_mismatch` | nie | P01 / U3.5 |
| POST | `/api/v1/auth/device` | publiczny | `{harness?}` | `DeviceCode` | — | nie | P10 / U5.2 |
| POST | `/api/v1/auth/device/token` | publiczny | `{device_code}` | `{token, token_id, user, orgs}` | `authorization_pending`, `slow_down`, `expired_token`, `access_denied` | nie | P10 / U5.2 |
| POST | `/api/v1/auth/device/approve` | sesja + CSRF | `{user_code}` | `DeviceApproval` | `not_found`, `expired_token` | nie | P10 / U5.2 |
| POST | `/api/v1/auth/device/deny` | sesja + CSRF | `{user_code}` | `DeviceApproval` | `not_found` | nie | P10 / U5.2 |
| GET | `/api/v1/me` | sesja lub token osobisty | — | `Me` | `unauthenticated` | nie | P01 / U3.1, U3.4 |
| PATCH | `/api/v1/me/profile` | sesja + CSRF | `{name}` | `{user}` | `invalid_profile` | tak | C27 |
| POST | `/api/v1/me/identities/link/start` | sesja + CSRF | `{provider}` | `{login_url}` | `invalid_request` | nie | P01 / U3.1 |
| POST | `/api/v1/orgs` | sesja + CSRF | `{name, slug}` | `Org` (201) | `slug_taken`, `invalid_request` | tak | P01 / U3.2 |
| GET | `/api/v1/orgs` | sesja lub token osobisty | — | `{items: [Org]}` (bez `next_cursor`: lista organizacji jednego użytkownika, bez stronicowania) | — | nie | P01 / U3.2 |
| GET | `{org_base}` | member | — | `Org` z `counts` | `forbidden` | nie | P01 |
| GET | `{org_base}/members` | member | `cursor` | `{items: [Member], next_cursor}` | `forbidden` | nie | P01 / U3.2 |
| PATCH | `{org_base}/members/{user_id}` | owner + CSRF | `{role}` | `Member` | `last_owner_protected`, `not_found` | tak | P01 / U3.2 |
| DELETE | `{org_base}/members/{user_id}` | owner + CSRF | — | 204 | `last_owner_protected`, `not_found` | tak | P01 / U3.2, U3.4 |
| GET | `{org_base}/teams` | member | — | `{items: [Team]}`; team membership is grouping only and grants no access | `forbidden` | nie | C28 |
| POST | `{org_base}/teams` | owner + CSRF | `{name}` | `Team` (201) | `team_exists`, `invalid_team` | tak | C28 |
| PUT | `{org_base}/teams/{team_id}/members/{user_id}` | owner + CSRF | — | 204, idempotent | `team_not_found`, `member_not_found` | tak | C28 |
| DELETE | `{org_base}/teams/{team_id}/members/{user_id}` | owner + CSRF | — | 204 | `team_member_not_found`, `not_found` | tak | C28 |
| POST | `{org_base}/invitations` | owner + CSRF | `{email, role}` | `Invitation` | `member_exists`, `invalid_request` | tak | P01 / U3.2 |
| GET | `{org_base}/invitations` | owner | — | `{items: [InvitationLifecycle]}` bez tokenów | `forbidden` | nie | S12 |
| DELETE | `{org_base}/invitations/{invitation_id}` | owner + CSRF | — | 204 | `invitation_used`, `not_found` | tak | S12 |
| GET | `/api/v1/invitations/{token}/accept` | public | — | `302` to hosted acceptance screen | `invitation_not_found` | tak | M02 browser landing |
| POST | `/api/v1/invitations/{token}/accept` | sesja + CSRF | — | `OrgMembership` | `not_found`, `expired_token` | tak | P01 / U3.2 |
| GET | `{org_base}/installations` | owner | — | `{items: [Installation]}` bez sekretów | `forbidden` | nie | P10 / U5.3 |
| POST | `{org_base}/installations` | owner + CSRF | `{name, repo_id?, scopes, harness?}` | `Installation` z `token` (raz) | `invalid_request` | tak | P10 / U5.3 |
| DELETE | `{org_base}/installations/{installation_id}` | owner + CSRF | — | 204 | `not_found` | tak | P10 / U3.4 |
| GET | `{org_base}/audit` | member | `cursor` | `{items: [AuditEntry], next_cursor}` | `forbidden` | nie | P02 / U9 |

Od 1.3.0 `{org_base}/audit` jest dostępny każdemu członkowi, nie tylko ownerowi: owner czyta każdy wiersz organizacji, a member wyłącznie wiersze, których `actor` to ten sam pseudonim principala, jakim serwer identyfikuje jego samego (§5.1 `AuditEntry.actor` pozostaje pseudonimem, nie e-mailem — porównanie jest po tej samej wartości, którą serwer już zapisał przy audycie żądania membera). Kształt strony i kursor bez zmian.

### 4.2 Import (P03, P04 — U1)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `{org_base}/repos` | member | `cursor` | `{items: [Repo], next_cursor}` | `forbidden` | nie | P03 |
| POST | `{org_base}/repos` | owner + CSRF | `{repo_id, name?, git_host_url?}` | `Repo` (201 zarejestrowane / 200 już istniało, pole `created:bool!` rozróżnia) | `invalid_request`, `invalid_repo_id` | tak | P03 / U1.1 |
| GET | `{repo_base}/access` | owner | — | `{repo_id, items: [{user_id,email,name,access,created_at}]}` | `forbidden`, `not_found` | nie | S15 |
| PUT | `{repo_base}/access/{user_id}` | owner + CSRF | `{access: read\|write}` | `{repo_id,user_id,access}` | `invalid_access`, `member_not_found` | tak | S15 |
| DELETE | `{repo_base}/access/{user_id}` | owner + CSRF | — | 204 | `repo_access_not_found` | tak | S15 |
| GET | `{repo_base}/reviewers` | owner | — | `{repo_id, items: [{user_id,email,name,created_at}]}` | `forbidden`, `not_found` | nie | S14 |
| PUT | `{repo_base}/reviewers/{user_id}` | owner + CSRF | — | 204 | `member_not_found` | tak | S14 |
| DELETE | `{repo_base}/reviewers/{user_id}` | owner + CSRF | — | 204 | `reviewer_not_found` | tak | S14 |
| POST | `{repo_base}/imports` | owner + CSRF | `{idempotency_key, manifest}` | `ImportCreated` (201) | `unsupported_manifest_format`, `limit_exceeded` | tak | P04 / U1.4, U1.5 |
| GET | `{repo_base}/imports` | member | `cursor` | `{items: [ImportStatus], next_cursor}` | `forbidden` | nie | P04 |
| GET | `{repo_base}/imports/{import_id}` | member | — | `ImportStatus` | `import_not_found` | nie | P04 / U2.1 |
| PUT | `{repo_base}/imports/{import_id}/blobs/{sha256}` | owner | `application/octet-stream` | 201 utworzony / 200 już był | `blob_digest_mismatch`, `blob_not_in_manifest`, `blob_too_large`, `import_already_finalized` | nie (idempotentne z natury) | P04 / U1.4 |
| POST | `{repo_base}/imports/{import_id}/finalize` | owner + CSRF | `{idempotency_key}` | `ImportStatus` (`state: queued`) | `blobs_missing`, `import_already_finalized` | tak | P04 / U1.5 |
| POST | `{repo_base}/imports/{import_id}/cancel` | owner + CSRF | `{idempotency_key}` | `ImportStatus` | `import_not_found` | tak | P04 |
| GET | `{repo_base}/imports/{import_id}/plan` | owner | `kinds`, `profile` | `{groups, limits, estimated_usd_max, generator, profile}` | `import_not_found`, `invalid_request` | nie | P06 / U2.7 |
| POST | `{repo_base}/imports/{import_id}/proposals:generate` | owner + CSRF | `{idempotency_key, kinds, limits, profile}` | `{job_ids, plan, profile}` | `limit_exceeded`, `import_not_found`, `invalid_request` | tak | P06 / U2.7, P08 |

`kinds` na `GET …/plan` jest listą wartości `{extraction|enrichment|consolidation}` zakodowaną jako pojedynczy parametr zapytania rozdzielony przecinkami (np. `?kinds=extraction,enrichment`), zgodnie z ogólną regułą jednowartościowych parametrów zapytania (§3); nieobecny lub pusty `kinds` znaczy „wszystkie trzy rodzaje". `POST …/proposals:generate` przyjmuje `kinds` jako tablicę JSON w ciele (ciało nie ma tego ograniczenia) i zakłada po jednym jobie `proposal.generate` na każdy żądany rodzaj (§8), więc `job_ids` w odpowiedzi może nieść kilka pozycji. `plan` w odpowiedzi generowania ma ten sam kształt `ImportPlan` co `GET …/plan` (§5.2) i odzwierciedla limity faktycznie zastosowane do tego wywołania, nie tylko oszacowanie sprzed startu.

`profile` (parametr zapytania na `GET …/plan`, pole ciała na `POST …/proposals:generate`) należy do zamkniętego zbioru `{default|one_shot}`; nieznana wartość to `400 invalid_request`, a brak pola znaczy `default`. `one_shot` podnosi **wyłącznie** `max_groups` do liczby grup, które plan rzeczywiście znalazł (twardy sufit 1000 grup na rodzaj), tak aby jedno wywołanie objęło cały import i `groups_skipped` było zerowe. Żaden inny limit się nie zmienia: `max_usd`, `max_calls`, `max_tokens`, `max_neighbours`, `max_files` i `max_bytes` pozostają ceilingiem wdrożenia, a wywołujący nadal może je obniżyć w `limits` — zawężenie działa po zastosowaniu profilu, więc `one_shot` nigdy nie przywraca limitu, który wywołujący celowo obniżył. Odpowiedź obu tras niesie `profile` z nazwą profilu, który faktycznie wykonano, a `limits.max_groups` po planowaniu jest liczbą grup do uruchomienia, nie sufitem — właściciel widzi koszt przed startem także wtedy, gdy startuje wszystko naraz (U2.7).

### 4.3 Knowledge (P05, P08 — U4, U8)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `{repo_base}/skills` | member | `q,scope,owner,layer,status,cursor,limit,snapshot_id` | `SkillPage` | `invalid_cursor` | nie | P05 / U4.1, U4.2 |
| GET | `{repo_base}/skills/facets` | member | `field,q,cursor` | `Facets` | `invalid_request` | nie | P05 / U4.1 |
| GET | `{repo_base}/skills/facets/lookup` | member | `field,value` | `FacetLookup` | `invalid_request` | nie | P05 / U4.1 |
| GET | `{repo_base}/skills/{skill_id}` | member | — | `SkillDetail` | `skill_not_found` | nie | P05 / U4.1 |
| GET | `{repo_base}/skills/{skill_id}/revisions/{revision_id}` | member | — | `Revision` | `revision_not_found` | nie | P05 / U4.1, U4.3 |
| GET | `{repo_base}/skills/{skill_id}/revisions/{revision_id}/raw` | member | — | dokładne bajty, `X-Content-SHA256` | `revision_not_found` | nie | P05 / U1.7 |
| POST | `{repo_base}/skills/{skill_id}/revisions/{revision_id}/feedback` | member + CSRF | `{idempotency_key, verdict, reason, task_id?}` | `{judgment_id}` | `invalid_request` | tak | P11 / U6.1 |
| GET | `{repo_base}/map/repository` | member | `path,cursor` | `MapRepository` | `invalid_cursor` | nie | P05 / U4.1 |
| GET | `{repo_base}/map/scopes` | member | `scope` | `MapScopes` | `not_found` | nie | P05 / U4.1 |
| GET | `{repo_base}/map/layers` | member | — | `MapLayers` | `forbidden` | nie | P08 / U4.1 |
| GET | `{repo_base}/map/relations` | member | `skill_id,type,cursor,limit` | `Relations` | `invalid_request` | nie | P08 / U4.1 |
| GET | `{repo_base}/modules/{scope}` | member | — | `ModulePage` | `not_found` | nie | P14 / U8 |

### 4.4 Review i publikacja (P06–P09 — U2, U5)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `{repo_base}/proposals` | member | `state,kind,scope,cursor` | `ProposalList` | `invalid_cursor` | nie | P07 / U2.8 |
| GET | `{repo_base}/proposals/{proposal_id}` | member | — | `ProposalDetail` | `proposal_not_found` | nie | P07 / U2.2, U4.3 |
| POST | `{repo_base}/proposals/{proposal_id}/decision` | owner + CSRF | `{idempotency_key, decision, reason, candidate_body?, expected_revision}` | `DecisionResult` | `stale_revision`, `invalid_candidate_change`, `graph_cycle`, `scope_widening_not_approved`, `proposal_state_invalid` | tak | P07 / U2.8, U2.6 |
| POST | `{repo_base}/proposals/{proposal_id}/export` | owner + CSRF | `{idempotency_key}` | `Export` | `proposal_state_invalid` | tak | P07 / U2.8 |
| GET | `{repo_base}/proposals/{proposal_id}/publication` | member | — | `Publication` | `proposal_not_found` | nie | P07 / U3 §3 |
| GET | `{repo_base}/exports/{export_id}` | member | — | `Export` | `export_not_found` | nie | P07 |
| GET | `{repo_base}/exports/{export_id}/patch` | member | — | `text/x-diff` | `export_not_found` | nie | P07 / U4.3 |
| POST | `{repo_base}/publish` | owner + CSRF | `{idempotency_key, import_id}` | `{job_id}` | `import_not_found`, `import_not_ready`, `missing_required_resource` | tak | P09 / U5 |
| GET | `{repo_base}/snapshots` | member | `cursor` | `{items: [Snapshot], next_cursor}` | `forbidden` | nie | P09 / U5 |
| POST | `{repo_base}/snapshots/{snapshot_id}/activate` | owner + CSRF | `{idempotency_key, reason}` | `{snapshot: Snapshot}` | `not_found`, `graph_cycle`, `missing_dependency` | tak | P09 / U5, U2.6 |
| GET | `{repo_base}/publications/{job_id}` | member | — | `Job` + `Publication` | `not_found` | nie | P09 |

### 4.5 Retrieval / Delivery (1.1 bez zmian, 1.2 addytywnie)

Semantyka pól, budżetów, kolejności i statusów pozostaje w [HARNESS-SERVICE-CONTRACT 1.1](HARNESS-SERVICE-CONTRACT.md). Ten kontrakt dodaje wyłącznie: rozstrzyganie org z `Principal` zamiast globalnego `Store.Tenant/Repo` (dla principali `session`/`personal` z nagłówków `X-Guidefold-Org`/`X-Guidefold-Repo`, kolejność źródeł w §2) oraz addytywne pola `1.2`. Ciało żądania 1.1 pozostaje niezmienione — te nagłówki, nie nowe pole, przenoszą wybór org/repo.

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `/health/live` | publiczny | — | `{live: true}` | — | nie | — |
| GET | `/health/ready` | publiczny | — | gotowość, `api_schema_versions` | `snapshot_not_published` | nie | P09 |
| GET | `/metrics` | wewnętrzny | — | Prometheus | — | nie | — |
| POST | `/v1/search` | `search` | żądanie 1.1/1.2 | karty 1.1/1.2 | 1.1 + `snapshot_changed` | nie | P09, P10 / U5.4 |
| POST | `/v1/use` | `use` | żądanie 1.1/1.2 | rewizja, `closure` (1.2), opcjonalny `delivery` (tryb `proof_gated`) | 1.1 + `snapshot_changed`, `missing_required_resource` | nie | P09 / U5.5 |
| GET | `/v1/skills/{skill_id}/revisions/{revision}/resources/{path}` | `use` | — | dokładne bajty zasobu, `X-Content-SHA256` | `revision_not_found`, `missing_required_resource`, `skill_outside_resolved_scope` | nie | P09 / U1.7, U5.5 |

W SEARCH reguła polityki jest stosowana przed każdym kanałem retrieval (BM25F,
dense i fusion): po odrzuceniu kart niedozwolonych, deprecated i z negatywnym
triggerem, dla tej samej kanonicznej nazwy pozostaje kopia z najgłębszego
widocznego scope'u. Kopie na tej samej głębokości nie shadowują się wzajemnie.
Odrzucone kopie zwiększają `policy_drops`; nie są tylko karane wagą rankingu.
Przy wielu resolved scopes zwycięzca jest liczony z ich unii, więc szerszy scope
nie może ponownie wprowadzić shadowowanego parenta. `policy_revision` identyfikuje
rewizję tej polityki.

`/metrics` jest wewnętrzny na stałe (ADR-0030): nigdy nie trafia do `services/search/openapi/management-v1.yaml` ani na publiczny ingress; jego nieobecność w OpenAPI nie jest luką do naprawienia.

Rozszerzenie 1.2 (`schema_version: "1.2"`): żądanie przyjmuje dodatkowe pole najwyższego poziomu `search_snapshot:str?` (walidowane osobnym dokumentem `tools/serve_spike/contracts/harness-service-v1.2.schema.json`, nadzbiorem 1.1; w żądaniu 1.1 to pole jest nieznane i daje `400`). USE zwraca `closure: {status: complete|unresolved|cannot_fit, requires: [{skill_id, revision, status, depth}], depth_limit: 8, loaded: [...]}` respektując `budget.max_cards` (domyślnie 4, maksimum 4 jak w 1.1) i `loaded_skills`; `status` zależności to `loaded|available|denied|missing`, a `depth` liczy skoki od żądanego skilla. USE zwraca też `resources: [{path, sha256, size, required, url}]` — manifest plików pakietu tej rewizji, z `path` **względnym wobec katalogu pakietu** i `url` wskazującym `GET /v1/skills/{skill_id}/revisions/{revision}/resources/{path}`; wymagany zasób bez bajtów daje `409 missing_required_resource`, a `resources: []` oznacza, że snapshot nie ma manifestu dla tej rewizji, nie że pakiet jest pusty. Podanie `search_snapshot` różnego od aktywnego daje `409 snapshot_changed` i ponowny SEARCH; nigdy mieszanki rewizji. Klient 1.1 nie otrzymuje żadnej z tych gwarancji przez samą zmianę etykiety.

Tryb `proof_gated` jest addytywnym, jawnym opt-in w żądaniu USE 1.2 (`delivery_policy:"proof_gated"`). W tym trybie serwer zwraca `delivery:{action:LOAD|ASK,reason,missing[],provenance}`. `LOAD` zostaje wydany tylko wtedy, gdy opublikowana karta niesie ważny, źródłowo związany dowód: identyfikator skilla, rewizja, snapshot, hash body, wszystkie rozwiązane scope'y, kompletna closure oraz każdy obowiązkowy claim ma status `supported` i niepusty zakres linii źródłowych. Przed wydaniem `LOAD` Go sprawdza, że każda ścieżka claimu należy do manifestu aktywnej rewizji albo wskazuje opublikowany skill/document z tego samego repozytorium i snapshotu, a następnie pobiera wskazany content-addressed blob z `gfm.blobs` (dla `SKILL.md` używa dokładnie dostarczanego body), sprawdza jego SHA-256 i obecność deklarowanego zakresu linii. Przy braku dowodu, konflikcie, niezgodności rewizji/snapshotu/scope'u, niepełnej closure, niedostępnym lub zmienionym źródle albo nieprawidłowym zakresie linii odpowiedź ma `action:"ASK"`, `status:"ask"`, `body:""` i opisuje brakujące warunki; pusty body nie jest instrukcją do wstrzyknięcia. `provenance` pokazuje wyłącznie identyfikatory, hashe i zakresy linii, nigdy treść źródła. Domyślny tryb (`legacy` lub brak pola) zachowuje dotychczasową odpowiedź 1.2. To jest bramka źródłowego pochodzenia i spójności dostawy, nie dowód poprawności wykonania ani autoryzacji człowieka.

W snapshotach rekord wejściowy nosi nazwę `source_proof` i znajduje się na
poziomie frontmatteru `SKILL.md`, poza skalarnym `metadata`; builder przenosi go
do pola karty `proof`. Wymagany kształt wersji `source-proof-v1` odpowiada
projekcji `delivery.provenance`: `schema`, `verified`, `snapshot`, `skill_id`,
`revision`, `body_sha256`, `scopes`, `claims[]` oraz opcjonalne `conflicts[]`.
Claim może dodatkowo nieść `claim_refs[]`: content-addressed pointers
(`skill_id`, `revision`, `claim_id`, `claim_digest`, `commitment`) do wspierających
claimów niższej karty w tym samym snapshotcie. Przy takim dowodzie serwis
przechodzi rekurencyjnie po całej ścieżce; brak karty, zmiana commitmentu/digestu,
konflikt lub cykl daje `ASK`.
`verified:true` jest oświadczeniem zaufanego importera/reviewera po sprawdzeniu
źródła i zakresów linii, a nie wartością, którą klient może nadać w żądaniu.
Brak tego rekordu jest celowo bezpieczny: tryb proof-gated zwraca `ASK`.
Publisher wiąże jawne placeholdery `pending`/puste dla `snapshot`, `revision` i
`body_sha256` z aktywnym snapshotem, rewizją karty i dostarczanymi bajtami. Nie
podnosi `verified` i nie nadpisuje wartości podanej przez reviewera; błędna wartość
pozostaje błędem, który kończy się `ASK`.
Rewizja karty obejmuje body i metadane retrieval, ale wyłącza wyłącznie kopertę
`proof`, aby jej publisher-bound pola nie tworzyły cyklicznego hasha.

1.2 dodaje też `family` — po jednym obiekcie na każdą kartę `cards[]` i `ranked[]` w SEARCH oraz jeden na odpowiedź USE: `family: {parent: {skill_id, revision, layer} | null, children: [{skill_id, revision, scope, layer}], layer}`. Wyliczane jest z zatwierdzonych krawędzi `refines` (dziecko → rodzic) i z `gfm.skills.knowledge_layer`; `layer` należy do `{atomic|task|abstract}` albo jest `null`, gdy nikt jeszcze nie sklasyfikował skilla. Głębokość to **jeden skok**, `children` ma najwyżej 8 pozycji w kolejności `skill_id`, a krawędź wskazująca poza snapshot nie jest więzią rodzinną i nie pojawia się w ogóle. `family` jest wskazówką nawigacyjną, nigdy deklaracją kompletności: nie mówi, że lista dzieci jest pełna, i nie zastępuje `closure`, które odpowiada na inne pytanie („czego jeszcze potrzebuję, żeby to uruchomić"). **`family` nie ma znaczenia rankingowego.** Jest doklejane po rankingu, po selekcji i po zmierzeniu `card_context`, więc kolejność `ranked`/`cards` oraz każdy bajt rozliczenia budżetu są identyczne z nim i bez niego; żądanie 1.1 nie dostaje tego pola w ogóle. Jeżeli metadane piramidy miałyby kiedykolwiek wpływać na retrieval, wymaga to osobnej, ograniczonej i z góry opisanej ewaluacji (PIVOT-BACKLOG, „Zasady prowadzenia", P06–P08).

### 4.6 Telemetry / Reporting (P11 — U6)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| POST | `/v1/events:batch` | `events` | partia zdarzeń (schemat telemetrii) | per-event `accepted`/`duplicate`/`rejected` | `batch_too_large`, `missing_events_list`, `telemetry_overloaded` | nie (dedupe po `event_id`) | P11 / U6.1, U6.5 |
| GET | `{repo_base}/usage` | member | `window,scope,skill_id,revision,harness` | `Usage` | `invalid_request` | nie | P11 / U6.2–U6.4 |
| GET | `{repo_base}/usage/export` | member | `format,window` | CSV lub JSON | `invalid_request` | nie | P11 / U6.4 |
| POST | `{repo_base}/usage/queue/{item_id}/decision` | owner + CSRF | `{idempotency_key, action, reason}` | `QueueItem` | `not_found`, `invalid_request` | tak | P13 / U9 |

`window` przyjmuje `7d|30d|90d` (domyślnie `30d`) i jest liczone względem **watermarku** = największego `received_at` w `gf.events` danej organizacji, a nie względem zegara czytającego: dwóch czytających o różnych porach widzi te same liczby, a zdarzenie spóźnione wpada do okna, w którym wystąpiło. Ledger jest w skali organizacji (`gf.events.tenant_id = org_id`), a te trasy w skali repozytorium: wiersz trafia do tego repozytorium, gdy katalog mówi, że jego skill tu należy; skill nieznany katalogowi jest liczony (ledger go widział) bez `scope` i `owner`. `coverage` opisuje całe okno i nie zawęża się filtrami; `totals` są sumą pokazanych wierszy. `harness` to pole `producer` zdarzenia. `{item_id}` w decyzji to `uuid` pozycji zapisanej przez workera **albo** wyprowadzony identyfikator pozycji policzonej (§5.5). Decyzja na pozycji `source_changed` przenosi skill z `needs_review` do `published` w tej samej transakcji; decyzja na pozycji `source_removed` zostawia go `archived`; pozostałe przyczyny nie ruszają statusu publikacji (§5.5, §6).

### 4.7 GitHub App (ADR-0036 — ascent bez edycji CI klienta)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/github/webhook` | publiczny; podpis HMAC `X-Hub-Signature-256` | ładunek zdarzenia GitHub (`installation`, `installation_repositories`, `pull_request`) | `202` `{accepted:bool!, job_id:uuid?, reason:str?}` | `invalid_webhook_signature`, `github_app_not_configured`, `invalid_body` | tak (klucz = `X-GitHub-Delivery`) | ADR-0036 / U2, U5, U10 |
| GET | `{org_base}/github/installations` | member | — | `{items: [GitHubInstallation]}` | — | nie | ADR-0036 / S11 |
| DELETE | `{org_base}/github/installations/{installation_id}` | owner + CSRF | — | `204` | `installation_not_found` | tak | ADR-0036 |

Webhook nie czyta ciała skilli i nie wywołuje modelu: weryfikuje podpis, dopasowuje `installation.id` i `repository.full_name` do `gfm.github_installations` oraz `gfm.repos`, i dla `pull_request` (`opened`, `synchronize`, `reopened`) ze zmienionym `**/.agents/skills/**/SKILL.md` kolejkuje **jeden** job `ascend.run` (klucz idempotencji `ascend:<installation_id>:<pr_number>:<head_sha>`). Zdarzenie bez dopasowanej instalacji lub repozytorium odpowiada `202 {accepted:false, reason:"unknown_installation"}` — GitHub nie ma dostać `4xx` za instalację, której ta organizacja jeszcze nie zarejestrowała. Rejestracja instalacji odbywa się przez zdarzenie `installation` (`created`) po tym, jak owner organizacji przeszedł przez `Connect GitHub` z ADR-0034; `installation` `deleted` usuwa wiersz. Token instalacji (JWT z `GITHUB_APP_PRIVATE_KEY_FILE` → `POST /app/installations/{id}/access_tokens`) jest pobierany przez **workera** per job, ważny godzinę, nigdy zapisywany w bazie ani logach.

### 4.8 Klucze modelu organizacji (ADR-0043 — BYOK)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `{org_base}/credentials` | member | — | `{items: [OrgCredential]}` | — | nie | ADR-0043 |
| PUT | `{org_base}/credentials/{provider}` | owner + CSRF | `{api_key:str!, name:str?}` | `OrgCredential` | `invalid_provider`, `invalid_body`, `credential_invalid`, `secret_encryption_unavailable` | nie (nadpisanie jest z natury idempotentne) | ADR-0043 |
| DELETE | `{org_base}/credentials/{provider}` | owner + CSRF | — | `204` | `credential_not_found` | nie | ADR-0043 |

Klucz nigdy nie wraca z API. `GET` i odpowiedź `PUT` niosą wyłącznie `provider`, `name`, `last4`, `created_at` i `created_by`. `PUT` przed zapisem sprawdza klucz u dostawcy jednym tanim wywołaniem i odrzuca taki, którego dostawca nie akceptuje — przyjęcie klucza, który nie działa, przeniosłoby awarię do joba w tle, którego właściciel nie ogląda. Zapis, nadpisanie, usunięcie i **użycie** klucza zapisują wiersz `gfm.audit` (`credential.set`, `credential.delete`, `credential.used`), zawsze z `last4`, nigdy z czymś więcej.

### 4.9 Live Agent (ADR-0044 — przebieg na żądanie po podpiętych repozytoriach)

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| POST | `{org_base}/live/runs` | owner + CSRF | `{prompt:str!, model:str?, repos:[]str?}` | `202` `LiveRun` | `invalid_prompt`, `invalid_model`, `model_credential_missing`, `live_run_already_active`, `secret_encryption_unavailable` | tak | ADR-0044 / U4 |
| GET | `{org_base}/live/runs` | member | `limit`, `cursor` | `{items: [LiveRun], next_cursor}` | `invalid_cursor` | nie | ADR-0044 / U4 |
| GET | `{org_base}/live/runs/{run_id}` | member | — | `{run: LiveRun, targets: [LiveRunTarget]}` | `live_run_not_found` | nie | ADR-0044 / U4 |
| GET | `{org_base}/live/runs/{run_id}/events` | member | `after:int?`, `limit` | `{items: [LiveRunEvent], next_after:int!, done:bool!}` | `live_run_not_found`, `invalid_integer` | nie | ADR-0044 / U4 |
| POST | `{org_base}/live/runs/{run_id}/cancel` | owner + CSRF | — | `LiveRun` | `live_run_not_found`, `live_run_not_cancellable` | nie | ADR-0044 / U4 |

`…/events` jest jedynym kanałem żywego wyjścia i **nie** jest transportem strumieniowym: zwykła koperta z §3, kursor pozycyjny `after` zamiast nieprzezroczystego `next_cursor`, bo dziennik jest monotoniczny w `seq` i klient dopytuje o „co po tym, co już mam". `next_after` to `seq` ostatniego zwróconego zdarzenia (albo `after`, gdy nic nie doszło), a `done` jest prawdziwe dopiero wtedy, gdy przebieg się zakończył **i** zwrócono już ostatnie zdarzenie — klient przestaje odpytywać wyłącznie na `done`, nigdy na pustej stronie. Dziennik jest też zapisem przebiegu: druga osoba i odświeżona karta widzą dokładnie to, co pierwszy oglądający widział na żywo.

`repos` pominięte oznacza wszystkie repozytoria organizacji, które mają instalację aplikacji GitHub. Repozytorium bez instalacji dostaje własny wiersz `LiveRunTarget` w stanie `skipped` z `github_app_not_configured` — przebieg „po wszystkich repozytoriach", który po cichu pominął część, byłby gorszy od takiego, który się nie udał.

## 5. Schematy DTO

Notacja pól: `nazwa:typ!` wymagane i nie-null, `nazwa:typ?` może być `null` lub nieobecne, `{a|b|c}` dziedzina zamknięta. Typy: `str`, `int`, `num`, `bool`, `ts` (RFC 3339, UTC), `uuid`, `sha` (64 hex), `urn` (`urn:skill:<publisher>:<node>:<name>`), `obj`, `[]T`. Dekoder klienta ignoruje pola nadmiarowe i odrzuca brakujące zadeklarowane (`ui/src/api/decoders.ts`). Serwer odrzuca nieznane pola **żądania** (`400 invalid_json`).

### 5.1 Tożsamość i organizacja

| DTO | Pola | Semantyka |
|---|---|---|
| `Me` | `user:obj!` (`id:uuid!`, `email:str!`, `name:str?`), `identities:[]obj!` (`provider:str!`, `created_at:ts?`), `orgs:[]OrgMembership!`, `csrf_token:str?`, `access:obj!` (`checked_at:ts?`, `valid_for_s:int!` = 45), `link_suggestions:[]obj!` (`provider:str!`) | Zawsze czyta membership z bazy. `access.valid_for_s` jest kontraktem maskowania UI (§9), nie SLA dostawcy. |
| `OrgMembership` | `org_id:uuid!`, `slug:str!`, `name:str!`, `role:{owner|member}!` | Rola wynika z `gfm.memberships`. |
| `Org` | `org_id:uuid!`, `slug:str!`, `name:str!`, `my_role:{owner|member}?`, `created_at:ts?`, `counts:obj?` (`members:int!`, `repos:int!`) | `slug` pasuje do `[a-z0-9-]{2,40}`, unikalny globalnie. `{org}` w ścieżce to `org_id` (kanoniczny) albo `slug` — każda odpowiedź niosącą organizację zawsze zwraca `org_id`, więc klient nie musi zgadywać, który wariant rozstrzygnął żądanie. UI buduje adresy slugiem dla czytelności i rozwiązuje bieżący slug przez `GET /api/v1/me`. Zmiana slugu jest wyłącznie działaniem ownera; po zmianie stare adresy z poprzednim slugiem przestają działać — nieznany slug jest nieznaną organizacją, więc dostaje ten sam `403 forbidden` co w §2, nigdy przekierowanie na nowy slug. |
| `Member` | `user_id:uuid!`, `email:str!`, `name:str?`, `role:{owner|member}!`, `joined_at:ts?` | E-mail widoczny tylko dla członków tej org. |
| `Invitation` | `invitation_id:uuid!`, `accept_url:str!`, `expires_at:ts?`, `email:str?`, `role:{owner|member}?` | MVP zwraca `accept_url` zapraszającemu; serwer nie wysyła e-maila. |
| `Installation` | `installation_id:uuid!`, `name:str!`, `repo_id:str?`, `scopes:[]str!`, `harness:str?`, `last_seen_at:ts?`, `adapter_version:str?`, `capabilities:[]str?`, `created_at:ts?`, `token:str?` | `token` niepuste **wyłącznie** w odpowiedzi tworzącej. Listy nigdy nie zawierają sekretu. |
| `DeviceCode` | `device_code:str!`, `user_code:str!`, `verification_uri:str!`, `expires_in:int!` = 600, `interval:int!` = 5 | `verification_uri` jest ścieżką względną UI z `?device=<user_code>`. |
| `DeviceApproval` | `user_code:str!`, `state:{pending|approved|denied|expired}!`, `expires_at:ts?` | — |
| `AuthProviders` | `providers:[]obj!` (`id:{google|github}!`, `label:str!`, `login_url:str!`), `mode:{dev|workos}!` | — |
| `GitHubInstallation` | `installation_id:int!`, `account:str!`, `repositories:[]obj!` (`full_name:str!`, `repo_id:str?`), `suspended:bool!`, `created_at:ts?`, `updated_at:ts?` | `repo_id` jest `null`, dopóki owner nie połączył repozytorium GitHub z `gfm.repos` (ADR-0034); job `ascend.run` jest kolejkowany tylko dla połączonych. |
| `AuditEntry` | `at:ts!`, `actor:str?`, `action:str!`, `entity:str?`, `revision:str?`, `request_id:str?` | `actor` jest pseudonimem principala, nie e-mailem. |

### 5.2 Import i joby

| DTO | Pola | Semantyka |
|---|---|---|
| `ImportCreated` | `import_id:uuid!`, `state:{created\|uploading\|queued\|parsing\|ready\|partial\|failed\|cancelled}!`, `missing_blobs:[]sha!`, `limits:ImportLimits?`, `reused_import_id:uuid?` | Manifest o digeście równym wcześniejszemu, nieudanemu importowi zwraca `reused_import_id` i 0 nowych blobów (U1.4). |
| `ImportLimits` | `max_blob_bytes:int!` = 8 388 608, `max_total_bytes:int!` = 104 857 600, `max_files:int!` = 100 000 | Przekroczenie to `422 limit_exceeded`, nigdy ciche obcięcie. |
| `ImportFile` | `path:str!`, `sha256:sha?`, `size:int?`, `kind:{skill\|document\|config\|resource}?`, `status:{pending\|accepted\|omitted\|failed}!`, `reason:str?`, `skill_id:urn?` | Błąd jednego pliku nie unieważnia pozostałych (U2.1). |
| `ImportCounts` | `files,accepted,omitted,failed,new_blobs,reused_blobs,skills,documents:int!` | `new_blobs = 0` przy powtórnym imporcie tego samego drzewa. |
| `ImportStatus` | `import_id:uuid!`, `state`, `manifest_digest:sha?`, `commit:str?`, `complete:bool!`, `publish:bool?`, `counts:ImportCounts?`, `files:[]ImportFile!`, `files_truncated:bool?`, `jobs:[]Job!`, `publication:ImportPublication?`, `error:str?`, `reused_import_id:uuid?`, `created_at:ts?`, `updated_at:ts?`, `finalized_at:ts?` | `state: ready` **nie** oznacza `published`; publikacja ma osobne pole. `files` jest przycinane do 20 000 pozycji; `files_truncated:true` mówi o tym wprost — nigdy ciche obcięcie listy plików. |
| `ImportPublication` | `snapshot_id:str?`, `state:{none\|building\|published\|failed}!`, `error:str?` | Nieudana publikacja nie zmienia aktywnego snapshotu. To zgrubszy widok silnika `gfm.publications.state` (§7: `building\|validated\|active\|failed\|superseded`) z perspektywy tego importu: brak wiersza → `none`; `building`/`validated` → `building`; `active` **i** `superseded` → `published` (`published` ⇔ `active`; ten import faktycznie osiągnął `active` choćby później zastąpiony — który snapshot jest aktywny teraz, mówi `GET {repo_base}/snapshots`, nie ten DTO); `failed` → `failed`. |
| `Job` | `job_id:uuid!`, `kind:str!`, `state:{queued\|leased\|done\|failed\|skipped\|cancelled}!`, `attempts:int!`, `generation:int!`, `error:str?`, `cost:JobCost?`, `started_at:ts?`, `finished_at:ts?`, `abstentions:[]obj!` (`reason:str!`, `skills:[]str!`, `detail:str?`) | `skipped` z `llm_not_configured` nie jest porażką importu. `abstentions` to nazwane odmowy z wyniku joba, do 20 pozycji, puste dla jobów innych niż `proposal.generate`: przebieg, który odmówił konsolidacji dwóch runbooków, wykonał swoje zadanie, a klient widzący samo „3 propozycje" nie odróżniłby tego od przebiegu, który po cichu nic nie zrobił. Pełna lista pozostaje w wierszu joba. |
| `JobCost` | `calls,tokens_in,tokens_out:int!`, `usd_certain,usd_uncertain:num!` | Opłata po timeoucie modelu trafia do `usd_uncertain`; nie sumujemy jej z pewną. |
| `ImportPlan` | `groups:[]ImportPlanGroup!`, `limits:ProposalLimits!`, `profile:{default\|one_shot}!`, `estimated_usd_max:num!`, `estimated_calls:int!`, `groups_skipped:obj!` (per rodzaj: ile scope'ów odciął `max_groups`), `generator:obj!` (`name:{none\|deterministic\|openai\|anthropic}!`, `configured:bool!`, `generator:str!`, `version:str!`, `model:str?`) | Wynik `GET …/plan` i pole `plan` w odpowiedzi `…/proposals:generate` (§4.2) — ten sam kształt w obu miejscach; w odpowiedzi generowania odzwierciedla limity faktycznie zastosowane, nie tylko oszacowanie. `generator.configured:false` ⇔ `name:"none"`: job `proposal.generate` skończy jako `skipped` z `llm_not_configured` (§6, §8), więc UI pokazuje to przed startem, nie dopiero po. `estimated_usd_max` jest górnym oszacowaniem, nie rachunkiem: `JobCost` po fakcie jest rozstrzygający. `profile` mówi, pod jakim profilem plan powstał (§4.2); przy `one_shot` `groups_skipped` jest zerowe, a `limits.max_groups` równa się liczbie grup największego rodzaju. |
| `ImportPlanGroup` | `group_id:str!`, `kind:{extraction\|enrichment\|consolidation}!`, `scope:str!`, `owner:str?`, `inputs:[]str!`, `n_inputs:int!`, `estimated_tokens:int?`, `estimated_calls:int!` | Jedna grupa = jedno wejście dla `proposal.generate` (§8, „grupa wejść"). `inputs` to ścieżki lub `skill_id` uczestniczące w tej grupie; kolejność bez znaczenia. `estimated_tokens` nieobecne, gdy generator nie potrafi oszacować przed uruchomieniem. Dla `kind:extraction` i `kind:enrichment` `scope` jest scope'em wejść. Dla `kind:consolidation` `scope` jest scope'em **nadrzędnym**, a wejścia pochodzą z niego i z jego bezpośrednich dzieci (§8): wspólna procedura prawie nigdy nie leży dwa razy w jednym scope, tylko raz w `atlas.geo` i raz w `atlas.graph`. `owner` grupy jest ownerem scope'u docelowego i to on staje się ownerem propozycji przy podniesieniu scope. |
| `ProposalLimits` | `max_files:int!`, `max_bytes:int!`, `max_groups:int!` = 5, `max_proposals_per_group:int!` = 5, `max_neighbours:int!` = 10, `max_tokens:int!`, `max_calls:int!`, `max_usd:num!` | Podzbiór pól joba `proposal.generate` istotny dla tego rodzaju joba (§8); operator może zawęzić `max_tokens`/`max_calls`/`max_usd` w żądaniu `…/proposals:generate` w dół od wartości z `GET …/plan`, nigdy w górę — poszerzenie ponad wartość z planu to `422 limit_exceeded`. |

### 5.3 Knowledge

| DTO | Pola | Semantyka |
|---|---|---|
| `SkillSummary` | `skill_id:urn!`, `name:str!`, `description:str!`, `scope:str!`, `owner:str?`, `source_layer:str?`, `knowledge_layer:{atomic\|task\|abstract\|unclassified}?`, `source_status:str?`, `publication_status:{draft\|approved_for_export\|awaiting_git\|published\|needs_review\|archived}!`, `path:str!`, `content_sha256:sha?`, `revision_id:sha?`, `card_revision:sha?`, `package_digest:sha?`, `commit:str?`, `updated_at:ts?` | Bez body. `card_revision` to rewizja **karty** (`gf.skills.skill_revision`), którą job publikacji zapisał na bieżącej rewizji katalogu; `null`, dopóki rewizja nie weszła do snapshotu. To jedyny identyfikator, którym posługuje się ścieżka dostawy (SEARCH/USE i telemetria adaptera), więc raport użycia łączy po nim i po `revision_id` (§5.5). `source_layer` (oś Źródło) i `knowledge_layer` (oś Wiedza) są rozłączne i nie wynikają z głębokości katalogu. `knowledge_layer` powstaje wyłącznie przez wnioskowanie generatora (`origin:inferred`, pole `knowledge_layer` w `gfm.proposal_fields`) albo przez decyzję właściciela przy zatwierdzeniu (`origin:human`); nigdy nie jest kopiowane z `source_layer`. Tablica reguł recepty `det-1`, w kolejności — pierwsza pasująca wygrywa: (1) zbudowane z ≥2 różnych scope'ów → `abstract`; (2) ≥2 kroki uporządkowane → `task`; (3) dokładnie jeden krok → `atomic`; (4) brak kroków, ≥2 reguły lub ograniczenia → `abstract`; (5) w pozostałych przypadkach → `atomic`. Reguła 1 wyprzedza regułę 2 celowo: wspólny element wyniesiony z dwóch scope'ów nadal ma kroki, a nazwanie go zadaniem stawiałoby go na tym samym szczeblu co procedury, z których powstał. |
| `SkillPage` | `items:[]SkillSummary!`, `next_cursor:str?`, `snapshot_id:str?`, `schema_version:str?`, `filters:map<str,FilterEcho>!` | `filters` niesie każdą wartość filtru, także niedostępną. |
| `FilterEcho` | `value:str!`, `available:bool!` | `available:false` = filtr rozpoznany, brak trafień; nie cichy powrót do „All". |
| `Facets` / `FacetLookup` | `field:str!`, `values:[]obj!` (`value:str!`, `count:int!`), `next_cursor:str?` / `field,value:str!`, `count:int!`, `available:bool!` | Aktywna wartość z URL ma osobny lookup i pozostaje widoczna poza bieżącą stroną. |
| `RevisionRef` | `revision_id:sha!`, `content_sha256:sha?`, `card_revision:sha?`, `commit:str?`, `import_id:uuid?`, `created_at:ts?`, `source:{import\|proposal}?` | `card_revision` jest `null`, dopóki rewizja nie weszła do snapshotu. |
| `SkillDetail` | `SkillSummary` + `revisions:[]RevisionRef!` | — |
| `Revision` | `revision_id:sha!`, `content_sha256:sha?`, `card_revision:sha?`, `body:str?`, `frontmatter:obj?`, `source:obj?` (`path,commit,url`), `references:[]SkillReference!`, `requires:[]urn!`, `refines:[]urn!`, `relations:[]RelationEdge!`, `feedback:[]FeedbackEntry!`, `provenance:obj?` (`origin:{source\|parsed\|inferred\|human}!`, `import_id`, `proposal_id`), `publication_status` | Rewizja jest niezmienna. Brak rewizji to `404 revision_not_found`, nigdy podmiana na nowszą. `source.url` buduje się z `git_host_url` + `/blob/<commit>/<path>`. `feedback` obejmuje oceny zapisane pod **obiema** rewizjami tej samej rewizji katalogu — `revision_id` (UI) i `card_revision` (adapter) — bo to jedna obserwacja liczona raz (§7). |
| `SkillReference` | `path:str!`, `sha256:sha?`, `size:int?`, `type:str?`, `required:bool!`, `available:bool!` | Manifest zasobów pakietu (U1.7). `required:true` i `available:false` blokuje publikację. |
| `RelationEdge` | `from:urn?`, `to:urn!`, `type:{derived_from\|requires\|refines\|similar\|conflicts_with}!`, `provenance:str?`, `revision:sha?` | Podobieństwo nie tworzy `requires`. |
| `FeedbackEntry` | `judgment_id:str!`, `verdict:{helped\|hindered\|mixed\|not_applicable\|unknown}!`, `reason:str?`, `source:str?`, `task_id:str?`, `occurred_at:ts?`, `actor:str?` | Korekta odwołuje się do poprzedniego `judgment_id`, nie tworzy drugiego głosu. `actor` (1.3.0) jest identyfikatorem principala, który ocenił przez UI (`source: "ui"`); `null` dla oceny pochodzącej z adaptera. |
| `MapRepository` / `MapScopes` / `MapLayers` / `Relations` / `ModulePage` | zob. `ui/src/api/decoders.ts` (`mapRepository`, `mapScopes`, `mapLayers`, `relations`, `modulePage`) | Osobne osie: drzewo źródeł, scope'y, warstwy, sąsiedztwo relacji. `Relations.truncated` mówi wprost o obcięciu. |

### 5.4 Review i publikacja

| DTO | Pola | Semantyka |
|---|---|---|
| `ProposalSummary` | `proposal_id:uuid!`, `kind:{extraction\|enrichment\|consolidation}!`, `state:{draft\|approved_for_export\|awaiting_git\|published\|rejected\|superseded}!`, `scope:str?`, `owner:str?`, `target_skill_id:urn?`, `path:str?`, `created_at:ts?`, `decision:obj?` (`decision:{approve\|edit\|reject}!`, `actor:str?`, `at:ts?`) | `decision` (1.3.0) jest najnowszym wierszem `gfm.decisions` dla tej propozycji; `null`, dopóki nierozstrzygnięta. `actor` to ten sam identyfikator principala, który `ProposalDetail.decision.actor` zwraca dla tej samej decyzji. |
| `ProposalDetail` | `ProposalSummary` + `target_revision_id:sha?`, `sources:[]obj!` (`path,sha256,commit,lines`), `recipe:obj?` (`version,generator,model`), `candidate:obj!` (`path,body,sha256,frontmatter`), `source_body:str?`, `provenance:[]obj!` (`field,origin,source_ref,needs_confirmation`), `relations:[]obj!` (`type,to,from`), `decision:obj?` (`decision_id,decision,reason,actor_user_id,expected_revision,result_revision_id,at`), `expected_revision:sha?`, `created_at:ts?`, `cost:JobCost?` | Każde pole ma pochodzenie. `ProposalDetail.decision` jest własnym, pełniejszym obiektem tej trasy (pole `actor_user_id`), nie tym samym kształtem co zwięzłe `ProposalSummary.decision` (1.3.0, pole `actor`) — oba niosą ten sam identyfikator principala, ale pod inną nazwą pola, więc dekoder nie może zakładać jednego kształtu dla obu. Krok bez konkretnego fragmentu źródła ma `needs_confirmation:true`. W `relations[]` dokładnie jedno z `to`/`from` jest niepuste: `to` to daleki koniec krawędzi **wychodzącej** z kandydata (np. `derived_from` do każdego źródła konsolidacji), `from` to daleki koniec krawędzi **przychodzącej** (np. `refines` z każdego skilla źródłowego w górę do wspólnego elementu). Rozróżnienie jest wymagane: „ten wspólny element powstał z twojego runbooka" i „twój runbook uszczegóławia ten wspólny element" to dwa różne twierdzenia o tej samej parze. |
| `DecisionResult` | `proposal_id:uuid!`, `state`, `revision_id:sha?`, `expected_revision:sha?` | `approve` zapisuje rewizję ludzką (`origin:human`, gdy edytowana). `metadata.knowledge_layer` z zatwierdzonego ciała trafia do `gfm.skills.knowledge_layer`; jeżeli właściciel zmienił je wobec wartości wywnioskowanej, wiersz `knowledge_layer` w `gfm.proposal_fields` dostaje `origin:human`. Warstwa jest jedynym polem metadanych, które `edit` może zmienić bez naruszenia tożsamości kandydata (`invalid_candidate_change`, §4.4): to, na którym szczeblu piramidy stoi instrukcja, jest oceną właściciela scope'u. Zatwierdzenie ustawia też `gfm.skills.current_revision_id` na zapisaną rewizję (§7, kolumna „Pisze": API przy decyzji) — bez tego zatwierdzony wspólny element nie byłby widoczny dla planu generowania, mapy scope ani walidatora grafu, bo wszystkie łączą po tej kolumnie. To **nie** jest publikacja: `publication_status` zostaje `draft`, a job publikacji przenosi wyłącznie skille, których plik jest w zaimportowanym drzewie (U2.6). |
| `Export` | `export_id:uuid!`, `proposal_id:uuid!`, `state:{awaiting_git}!`, `base_commit:str?`, `files:[]obj!` (`path,sha256,content`), `patch:str?` | Eksport ≠ publikacja. Patch to unified diff wobec rewizji źródłowej albo patch nowego pliku. |
| `Snapshot` | `publication_id:uuid!`, `snapshot_id:str?`, `state:{building\|validated\|active\|failed\|superseded}!`, `active:bool!`, `import_id:uuid?`, `job_id:uuid?`, `commit:str?`, `n_skills:int!`, `builder_sha256:str?`, `validation:obj?`, `error:str?`, `activated_at:ts?`, `created_at:ts!` | Jeden wiersz `gfm.publications` (§7). `state` to słownik silnika; `active` to jedyny fakt, którego potrzebuje rollback — publikacja bez `snapshot_id` nigdy nie jest aktywna. `validation` niesie `{ok, findings[]}` nieudanej walidacji, więc powód porażki jest czytelny bez zaglądania do logu. |
| `Publication` | `state:{awaiting_git\|published\|superseded}!`, `published_revision_id:sha?`, `import_id:uuid?`, `snapshot_id:str?` | `published` dopiero, gdy **kompletny** import ma plik o `candidate.path` z tym samym sha256 i job publikacji aktywował snapshot. |

### 5.5 Usage i jakość

| DTO | Pola | Semantyka |
|---|---|---|
| `Usage` | `window:obj!` (`from,to,watermark`), `coverage:obj?` (`events_received,dropped_reported:int!`, `oldest_lag_s:int?`, `task_ids_present:bool!`), `totals:obj!` (`exposures,loads_verified,context_loaded,context_unknown,use_reported,use_observed,use_episodes,exposures_expanded,loads_unlinked:int!`, `feedback:FeedbackTotals?`, `metrics:ExecutionMetrics!`), `previous:obj?` (`window:obj!` (`from:ts!,to:ts!`), `totals:UsageTotals!`), `skills:[]UsageSkill!`, `queue:[]QueueItem!`, `health:obj?` (`adapters:[]AdapterHealth!`), `filters:obj?` (`scope,skill_id,revision,harness,window:str?`) | Agregaty liczone z `gf.events` po `tenant_id = org_id`; muszą zgadzać się z `tools/telemetry/report.py` dla tego samego zbioru zdarzeń. `metrics` to obserwowane sygnały do scorecardów: sukces/zakończenie zadań, błędy harnessu, SEARCH/USE/ASK, tokeny, wywołania narzędzi i próbki opóźnienia; brak obserwacji pozostaje `Unknown`, nie jest zerem ani dowodem jakości. `filters` jest echem tego, co zastosowano, kluczami **identycznymi z parametrami zapytania** (`scope`, `skill_id`, `revision`, `harness`, `window`); parametr niepodany nie ma klucza, a `window` niesie zastosowane okno, także domyślne. `previous` (1.3.0) jest oknem tej samej długości, kończącym się w `window.from` (zakotwiczonym na tym samym watermarku); liczone tak samo jak `totals`, tymi samymi filtrami. `null` wyłącznie, gdy raport nie ma `totals`. Zero jest prawdziwym zerem w tym oknie, nie Unknown — UI decyduje, czy delta ma sens (oba okna muszą mieć `exposures > 0`). |
| `ExecutionMetrics` | `tasks_started,tasks_finished,tasks_succeeded,tasks_failed,tasks_unknown,harness_errors,search_requests,search_results,search_errors,use_requests,ask_count,input_tokens,output_tokens,tool_calls,latency_ms,latency_samples:int!`, `tasks_observed,cost_observed:bool!`, `ask_reasons:map<string,int>!` | Sygnały są sumowane z zaakceptowanych zdarzeń w wybranym oknie. `tasks_succeeded / tasks_finished` pokazuje tylko jawnie oznaczone wyniki; `tasks_unknown` nie jest porażką. `latency_ms` łączy jawne czasy zadań i SEARCH, dlatego UI pokazuje średnią z liczbą próbek, bez udawania jednego p95 end-to-end. `ask_reasons` grupuje decyzje fail-closed po kodzie powodu; brak powodu trafia do `unknown`, a UI pokazuje najwyżej trzy najczęstsze przyczyny. |
| `UsageSkill` | `skill_id:urn!`, `revision:sha?`, `card_revision:sha?`, `content_sha256:sha?`, `scope:str?`, `owner:str?`, `harness:str?`, `exposures,loads_verified,context_loaded,context_unknown,use_reported,use_observed,use_episodes,exposures_expanded,loads_unlinked:int!`, `feedback:FeedbackTotals?`, `helped_ratio:HelpedRatio?`, `zero_loads:bool!` | HTTP 200 na USE nigdy nie zwiększa „użyto"/„pomogło". `exposures_expanded` i `loads_unlinked` (1.1.4) mówią, czy karta wystarczyła: pierwsza liczy ekspozycje, po których to samo `search_id` doprowadziło do zweryfikowanego załadowania body tego skilla, druga — załadowania, których nie da się powiązać z żadną ekspozycją, bo adapter nie podał `search_id`. `exposures − exposures_expanded` to ekspozycje, po których body nie pobrano; przy `loads_unlinked > 0` ta różnica jest **górną** granicą „karta wystarczyła", nie faktem, bo część pobrań mogła pochodzić z tych ekspozycji. Ekspozycja bez pobrania nie dowodzi, że karta wystarczyła — mogła być nietrafna; rozstrzyga dopiero ocena (`feedback`). `scope`/`owner` z bieżącej rewizji skilla w katalogu (decyzja 14); `harness` = `producer`, gdy dokładnie jeden adapter złożył się na wiersz, inaczej `null`. **Jedna przestrzeń nazw rewizji.** Zdarzenie ze ścieżki dostawy niesie rewizję karty (`gf.skills.skill_revision`), a ocena z UI — `gfm.skill_revisions.revision_id`. Agregat sprowadza obie do rewizji katalogu przez `gfm.skill_revisions(revision_id, card_revision)`, więc ten sam skill oceniony w UI i dostarczony do harnessu daje **jeden** wiersz; `revision` to rewizja katalogu, a `card_revision` i `content_sha256` pokazują pozostałe dwa identyfikatory tej samej rewizji (oba `null`, gdy rewizja nie jest znana katalogowi). Filtr `revision=` przyjmuje **rewizję katalogu albo rewizję karty** — dwa identyfikatory, które faktycznie występują w zdarzeniach — i jest echem **dosłownie tak, jak go podano**. `content_sha256` jest pokazywany, ale nie jest kluczem wyszukiwania: dwa skille o bajtowo identycznym SKILL.md dzielą go, więc nie nazywa jednej rewizji. |
| `FeedbackTotals` | `helped,hindered,mixed,not_applicable,unknown,n:int!` | Brak oceny jest osobną kategorią, nie zerem. |
| `HelpedRatio` | `numerator,denominator:int!`, `small_sample:bool!` | `small_sample:true` przy `denominator < 20`; poniżej progu UI pokazuje liczby, nie procent. |
| `QueueItem` | `item_id:str!`, `skill_id:urn!`, `revision:sha?`, `reason:{negative_feedback\|source_changed\|source_removed\|zero_loads\|missing_dependency}!`, `since:ts?`, `evidence:obj?`, `decision:obj?` (`action:{reviewed\|fixed_in_git\|no_change}!`, `reason`, `at`, `actor:str?`), `source:{worker\|computed}?` | Powtórny import z tym samym manifestem nie tworzy drugiej pozycji o tej samej przyczynie. `decision.actor` (1.3.0) jest identyfikatorem użytkownika zapisanym na decyzji ownera w `gfm.owner_queue`; `null` dla decyzji zapisanej przez workera. |
| `AdapterHealth` | `harness:str!`, `adapter_version:str?`, `capabilities:[]str?`, `last_seen_at:ts?`, `lag_s:int?`, `dropped:int?` | Brak wiersza to `unknown`, nie zdrowie. |

`GET {repo_base}/usage/export`: kolumny CSV są przypięte w tej kolejności — `skill_id,revision,scope,owner,harness,window_from,window_to,exposures,loads_verified,context_loaded,context_unknown,use_reported,use_observed,helped,hindered,mixed,not_applicable,unknown,feedback_n,helped_numerator,helped_denominator,small_sample,zero_loads,card_revision,content_sha256,exposures_expanded,loads_unlinked`. Zmiana kolejności lub usunięcie kolumny jest zmianą znaczącą (MAJOR wg §10); dopisanie kolumny na końcu jest addytywne — `card_revision` i `content_sha256` doszły na końcu w 1.1.1, `exposures_expanded` i `loads_unlinked` w 1.1.4, i nie ruszyły żadnej wcześniejszej kolumny. `format=json` zwraca te same wiersze jako obiekty o tych samych nazwach pól, plus `coverage` i `window` (jak w `Usage`).

Kształt `format=json` jest przypięty (decyzja 12): `{"schema_version":"mgmt-1","window":{…},"coverage":{…},"rows":[{…}]}`; klucz listy to `rows`. Pusta komórka CSV odpowiada `null` w JSON — brak oceny nie jest zerem, więc `helped…feedback_n`, `helped_numerator`, `helped_denominator` i `small_sample` są puste, gdy dla wiersza nie ma żadnej oceny.

**Definicje miar (U6).** Liczone wyłącznie ze zdarzeń klienta; odpowiedź HTTP nie jest dowodem.

| Miara | Definicja |
|---|---|
| `exposures` | Unikalne `exposure_id` zdarzeń `card_injected` w oknie |
| `loads_verified` | Unikalne `load_id` zdarzeń `skill_load_completed` o `status ∈ {ok, verified}`; `denied`/`error` nigdy nie są załadowaniem |
| `context_loaded` | Te z nich, których `skill_load_completed` niesie `context_confirmation: "context_loaded"` (pole opcjonalne, addytywne) |
| `context_unknown` | `loads_verified − context_loaded`: `download_verified`, `unsupported` i brak pola to *unknown*, nie porażka |
| `exposures_expanded` | Ekspozycje (`card_injected`), których `search_id` występuje też na zweryfikowanym `skill_load_completed` **tego samego `skill_id`** w oknie. `skill_load_completed` niesie `search_id` jako pole **opcjonalne, addytywne** (jak `context_confirmation`; nie ma go na liście `required_fields` walidatora, adapter 1.1 działa dalej). Powiązanie jest po `skill_id`, nie po rewizji: karta i body tego samego skilla mogą nieść różne identyfikatory rewizji (rewizja karty vs katalogu), a pytanie brzmi „czy po tej karcie pobrano body", nie „którą rewizję" |
| `loads_unlinked` | Zweryfikowane załadowania bez `search_id` — adapter nie wiedział, po jakiej ekspozycji je wykonał. To *unknown*, nie „bez karty": dopóki `loads_unlinked > 0`, `exposures − exposures_expanded` jest górną granicą liczby kart, które wystarczyły |
| `use_reported` / `use_observed` | Osobno, deduplikowane po `use_id` (brak `use_id` → po `event_id`); nigdy nie sumowane |
| `use_episodes` | Unikalne `(tenant, task_id, skill_id, revision)` w obu rodzajach łącznie; zdarzenie bez `task_id` nie tworzy epizodu |
| `feedback` | Jedna opinia na epizod: korekta niesie `corrects_judgment_id` wskazujący wcześniejsze `judgment_id` i **zastępuje** je (kolejność po `occurred_at`, potem `event_id`), a nie dodaje drugiego głosu |
| `skill_feedback` z UI | `POST …/revisions/{revision_id}/feedback` zapisuje `revision` = rewizja katalogu (adresowana w ścieżce) plus **opcjonalne** `content_sha256` i — gdy rewizja weszła do snapshotu — `card_revision`. Oba pola są opcjonalne i nie występują na liście `required_fields` walidatora (`telemetry-schema.json` bez zmian), więc adapter 1.1 i klient 1.1.0 działają dalej. `revision` celowo zostaje przy rewizji katalogu: to jedyny z trzech identyfikatorów, który kontrolna implementacja `tools/telemetry/report.py` potrafi policzyć bez dostępu do katalogu |
| `helped_ratio` | `{numerator: helped, denominator: helped+hindered, small_sample: denominator<20}`; `null`, gdy mianownik jest zerem |
| `zero_loads` | Brak zweryfikowanego załadowania w oknie; nie dowodzi bezużyteczności |
| `coverage.oldest_lag_s` | Największy `oldest_lag_s` z `gfm.adapter_health` organizacji; brak wiersza to `null` (nieznane), nie zero |

Kolejka (`Usage.queue`) łączy otwarte wiersze `gfm.owner_queue` (przyczyny driftu pisane przez workera importu) z dwiema przyczynami **policzonymi** z telemetrii: `negative_feedback` (≥1 `hindered` w oknie na bieżącej lub opublikowanej rewizji) i `zero_loads` (skill opublikowany, ≥1 ekspozycja **albo** ≥7 dni od publikacji, zero załadowań). Pozycja policzona ma stabilny identyfikator `<reason>:<skill_id>:<revision>` i również podlega decyzji: decyzja zapisuje wiersz `gfm.owner_queue` w stanie `resolved`, którego `item_id` jest deterministycznie wyprowadzone z tego identyfikatora, więc ta sama obserwacja nie wraca i nie dubluje się. Istniejący wiersz o tym samym `(skill_id, reason, revision_id)` — otwarty albo już rozstrzygnięty — wygasza pozycję policzoną.

Decyzja ownera na pozycji **`source_changed`** zamyka też pytanie, które drift postawił skillowi: `POST {repo_base}/usage/queue/{item_id}/decision` z akcją `reviewed`, `fixed_in_git` albo `no_change` przenosi skill z `needs_review` z powrotem do `published` w tej samej transakcji, w której zapisuje decyzję (§6). Decyzja na pozycji **`source_removed`** niczego nie cofa: skill zostaje `archived`, bo pliku nadal nie ma w repozytorium, a przywraca go dopiero import, który go z powrotem przynosi. Żadna inna przyczyna nie rusza statusu publikacji.

### 5.5a Klucze organizacji i Live Agent (ADR-0043, ADR-0044)

| DTO | Pola | Semantyka |
|---|---|---|
| `OrgCredential` | `provider:{openrouter}!`, `name:str!`, `last4:str!`, `created_at:ts?`, `created_by:uuid?` | Metadane, nigdy sekret. `last4` to cztery ostatnie znaki klucza i jedyne, co z niego kiedykolwiek opuszcza serwer — także w wierszu audytu. Brak wiersza dla dostawcy oznacza, że organizacja nie ma klucza; nie ma stanu „klucz jest, ale nieznany". |
| `LiveRun` | `run_id:uuid!`, `state:{queued\|running\|succeeded\|partial\|failed\|cancelled}!`, `prompt:str!`, `model:str!`, `created_by:uuid?`, `created_at:ts!`, `started_at:ts?`, `finished_at:ts?`, `counts:obj!` (`targets:int!`, `done:int!`, `failed:int!`, `skipped:int!`), `cost:obj!` (`tokens_in:int!`, `tokens_out:int!`, `usd:num!`, `usd_estimated:bool!`), `error:str?` | `partial` znaczy, że część repozytoriów nie doszła do końca, i jest stanem końcowym, nie sukcesem — `counts.failed` i `counts.skipped` mówią ile. `cost.usd_estimated` jest prawdziwe, gdy choć jedna odpowiedź dostawcy nie niosła zużycia i trzeba je było oszacować; koszt oszacowany nigdy nie jest pokazywany jako zmierzony. `error` niesie powód zakończenia przebiegu (`live_run_budget_exhausted`, `model_provider_unavailable`, `cancelled_by_owner`), nie błąd HTTP. |
| `LiveRunTarget` | `repo_id:str!`, `state:{queued\|running\|done\|failed\|skipped}!`, `job_id:uuid?`, `findings:int!`, `error:str?`, `started_at:ts?`, `finished_at:ts?` | Jeden wiersz na repozytorium objęte przebiegiem. `skipped` z `github_app_not_configured` to repozytorium bez instalacji — jawnie pominięte, nie milcząco. |
| `LiveRunEvent` | `seq:int!`, `at:ts!`, `repo_id:str?`, `type:{run.started\|repo.started\|model.delta\|finding\|repo.finished\|run.finished\|error}!`, `payload:obj!` | `seq` rośnie monotonicznie w obrębie przebiegu i jest kursorem `after`. `model.delta` niesie `{text:str!}` zbatchowany przez workera (~500 ms albo ~2 KB), żeby gadatliwy model nie zrobił z jednego przebiegu stu tysięcy wierszy. `finding` niesie `{scope:str?, path:str?, summary:str!, severity:{info\|warn}!}` i jest jedynym typem, który UI pokazuje poza transkryptem. |

### 5.6 Manifesty i artefakty

`guidefold-import-manifest-v1` (produkowany lokalnie przez CLI, wysyłany w `POST {repo_base}/imports`):

| Pole | Typ | Semantyka |
|---|---|---|
| `format` | `"guidefold-import-manifest-v1"!` | Inna wartość → `400 unsupported_manifest_format` |
| `org`, `repo` | `str!` | Slug org i `repo_id` (`[A-Za-z0-9_.-]{1,64}`) |
| `commit` | `str?` | 40 hex albo `null` dla skanu bez gita |
| `complete` | `bool!` | `false` (skan częściowy) **nigdy** nie prowadzi do usunięć |
| `dirty` | `bool!` | Lokalne zmiany; domyślny profil publikacji obejmuje commit |
| `cli_version`, `scan_profile`, `root` | `str!` | Diagnostyka i zakres skanu |
| `files` | `[]obj!` | `path`, `sha256`, `size`, `kind:{skill\|document\|config\|resource}`, `mode`, `source:obj?` |
| `files[].source` | `obj?` | Nieobecne dla plików repozytorium (domyślne, wstecznie zgodne). Obecne wyłącznie dla treści spoza drzewa git, dołączonej jawnym `guidefold extract --personal`: `{kind:"personal", harness:{claude\|codex\|copilot}}`. Ścieżka takiego pliku ma prefiks `_personal/<harness>/…` i nigdy nie koliduje ze ścieżką repozytorium. Bez `--personal` żaden wiersz z `source.kind:"personal"` nie istnieje; CI nigdy nie używa tej flagi. Manifest zawierający choć jeden taki wiersz ma `publish:false` — kompletny import z `publish:true` zleca `publish.build`, więc prywatne skille dewelopera zaczęłyby odpowiadać na SEARCH całej organizacji z jednej flagi |
| `excluded` | `[]obj!` | `path`, `reason:{secret_pattern\|ignored_directory\|symlink_outside_root\|submodule\|unsupported_format\|limit_exceeded\|non_canonical_skill_path}` |
| `aliases` | `[]obj!` | `from`, `to` — zachowanie tożsamości przy rename (U1.5) |
| `limits` | `obj!` | `max_files`, `max_bytes` deklarowane przez klienta; serwer i tak stosuje własne |
| `publish` | `bool?` | Domyślnie `true`. `false` finalizuje import bez joba `publish.build`: drzewo jest sparsowane, katalog uzupełniony, ale nic nie startuje do publikacji (§6) |
| `suggestions` | `[]obj!` | Doradcze dopasowania scope/owner dla plików `kind:skill`, których `guidefold.yaml` samodzielnie nie pokrywa (U1 AC2): `path`, `suggested_scope:str?`, `suggested_owner:str?`, `reasons:[]str`, `candidates:[]str?` (przy `ambiguous_node_match`). Nigdy nie wpływa na `files`/`excluded` ani na scope faktycznie użyty przez CLI — czysto informacyjne, obecne (może być puste) w każdym manifeście |

Manifest jest deterministyczny: to samo drzewo daje identyczne bajty (porządek po bajtach ścieżki). `manifest_digest` = sha256 kanonicznego JSON-a manifestu.

`guidefold-service-snapshot-v1` — istniejący artefakt buildera snapshotu (wiąże `repo_id`, commit, mapę scope, karty, wagi i sha CLI). Kontrakt bez zmian; opis w [HARNESS-SERVICE-CONTRACT §Scope resolution](HARNESS-SERVICE-CONTRACT.md).
`router_index` — istniejący kanoniczny indeks leksykalny budowany przez zaufany Python builder; postać i digest bez zmian (`gf.router_indexes`, `gf.router_terms`). Ten kontrakt go **nie** redefiniuje.

## 6. Maszyny stanów

Każde przejście ma aktora, warunek i efekt uboczny. Efekt „audyt" oznacza wiersz w `gfm.audit` z `request_id`.

| Maszyna | Przejście | Kto | Warunek | Efekt uboczny |
|---|---|---|---|---|
| import | `created → uploading` | API | pierwszy `PUT …/blobs/{sha}` | licznik `new_blobs` |
| import | `created\|uploading → queued` | API | `finalize`, komplet blobów | enqueue `import.parse` (+ `publish.build`, gdy `manifest.publish ≠ false`) w tej samej transakcji |
| import | `queued → parsing` | worker | lease joba `import.parse` | `started_at`, heartbeat |
| import | `parsing → ready` | worker | wszystkie pliki `accepted` | rewizje, dokumenty, zasoby, drift; audyt |
| import | `parsing → partial` | worker | ≥1 plik `failed`, reszta `accepted` | jak wyżej; publikacja **nie** startuje samoczynnie |
| import | `parsing → failed` | worker | manifest lub bloby nieczytelne | brak zmian w katalogu; aktywny snapshot bez zmian |
| import | `* → cancelled` | owner (API) | `cancel` | joby `queued → cancelled`, job `leased` kończy na najbliższym checkpoincie |
| publikacja | `none → building` | API/worker | `publish.build` zaleasowany | `gfm.publications` |
| publikacja | `building → validated` | worker | graf i pakiety poprawne | `validation.ok = true` |
| publikacja | `validated → active` | worker | transakcja zapisu `gf.snapshots/skills/heads` | zmiana `gf.heads`; audyt |
| publikacja | `building\|validated → failed` | worker | walidacja lub transakcja nieudana | poprzedni head bez zmian; `error` |
| publikacja | `active → superseded` | worker/owner | aktywacja innego snapshotu (rollback lub roll-forward) | audyt; retencja ≥30 dni |
| job | `queued → leased` | worker | `lease_until < now()` lub `state='queued'` | `generation += 1`, `worker_id`, `attempts += 1` |
| job | `leased → leased` | worker | heartbeat ≤10 s, generacja zgodna | `lease_until` przedłużony, `checkpoint` |
| job | `leased → done` | worker | handler zwrócił `nil` | `result`, `finished_at` |
| job | `leased → failed` | worker | błąd trwały lub `attempts ≥ max_attempts` | `error`; backoff 5 s, 10 s, 20 s… ≤5 min |
| job | `leased → queued` | worker | błąd przejściowy, `attempts < max_attempts` | `lease_until` = teraz + backoff |
| job | `leased → skipped` | worker | brak pracy (np. `llm_not_configured`) | `error` = powód; import pozostaje użyteczny |
| job | `* → cancelled` | owner (API) | anulowanie importu | zapis starej generacji odrzucony (`job_fenced`) |
| proposal | `draft → approved_for_export` | owner | `decision: approve\|edit`, `expected_revision` zgodne, graf poprawny | rewizja `origin:human`; `gfm.decisions`; audyt |
| proposal | `draft → rejected` | owner | `decision: reject` z powodem | `cache_key` zablokowany: to samo wejście/recepta nie generuje ponownie |
| proposal | `approved_for_export → awaiting_git` | owner | `export` | `gfm.exports`; UI pokazuje „Exported", nie „Published" |
| proposal | `awaiting_git → published` | sync (worker) | kompletny import ma plik `candidate.path` o tym samym sha256 **i** snapshot aktywowany | skill `publication_status = published`; audyt |
| proposal | `* → superseded` | worker | zmiana źródła unieważnia wejście propozycji | pozycja kolejki ownera `source_changed` |
| skill | `draft → approved_for_export → awaiting_git → published` | jak wyżej | — | draft nigdy nie trafia do SEARCH/USE |
| skill | `published → needs_review` | worker (drift) | inny sha źródła albo negatywny feedback | pozycja `owner_queue`; poprzedni snapshot działa dalej |
| skill | `* → archived` | worker (drift) | brak w **kompletnym** manifeście (`source_removed`) | nigdy nie usuwamy wiersza; decyzja należy do ownera |
| skill | `draft\|approved_for_export\|awaiting_git\|published → published` | worker (`publish.build`) | rewizja skilla weszła do aktywowanego snapshotu | `published_revision_id`, `published_snapshot_id`, `card_revision` na rewizji |
| skill | `needs_review → needs_review`, `archived → archived` | worker (`publish.build`) | ten sam warunek, ale flaga jest zadaniem ownera, nie bramką serwowania | snapshot dalej serwuje bieżącą rewizję; publikacja **nie** kasuje pytania postawionego przez drift |
| skill | `needs_review → published` | owner (API) | decyzja `reviewed\|fixed_in_git\|no_change` na pozycji `source_changed` | `gfm.owner_queue.state = resolved`; audyt |
| skill | `archived → archived` | owner (API) | decyzja na pozycji `source_removed` | tylko zamknięcie pozycji; pliku nadal nie ma, więc status się nie zmienia |
| device code | `pending → approved\|denied` | owner sesji + CSRF | `approve`/`deny` przed `expires_at` | — |
| device code | `pending → expired` | API | `now() > expires_at` | `expired_token` przy wymianie |
| device code | `approved → (skonsumowany)` | API | pierwsza udana wymiana | token osobisty; kod jednorazowy |
| membership | `(brak) → member\|owner` | owner (zaproszenie) / API (twórca org) | akceptacja zaproszenia w terminie | audyt |
| membership | `owner → member`, `* → (brak)` | owner | nie jest to ostatni owner | audyt; dostęp odcięty przy następnym żądaniu |
| invitation | `pending → accepted\|revoked\|expired` | zapraszany / owner / czas | token jednorazowy | audyt |

Ten sam cykl publikacji widziany przez import ma tylko cztery wartości: `ImportPublication.state` (§5.2) zwija `building`/`validated` do `building` i `active`/`superseded` do `published`, bo z perspektywy importu liczy się, czy publikacja **kiedykolwiek** osiągnęła `active`, nie czy nadal jest bieżącym snapshotem.

## 7. Schemat bazy

Dwa schematy, jedna baza (ADR-0018, ADR-0033). `gf` to istniejący katalog serwowania: **niezmienny poza dopisaniem kolumn**, zgodnie z profilem plain Postgres (`pg_search` i `pgvector` są opcjonalne; migracja musi przejść bez nich, a silnik `router` nigdy ich nie czyta). `gfm` to schemat zarządczy: każdy wiersz danych organizacyjnych ma `org_id`, a każdy klucz złożony zaczyna się od `org_id`, więc zapytanie bez predykatu tenanta nie może połączyć organizacji.

Rola `guidefold_api` ma `default_transaction_read_only=on`; każdy zapis otwiera jawną transakcję read-write. `gf.*` pozostaje dla API tylko do odczytu z wyjątkiem append do `gf.events` i `gf.search_shadow`; wiersze katalogu pisze wyłącznie job publikacji.

Legenda kolumn: `NN` = NOT NULL, `d:` = default, `[]` = tablica, `→` = klucz obcy.

### Katalog serwowania (`gf`) — bez zmian

| Tabela | Kolumny | Klucze i indeksy | Pisze | Czyta | Retencja |
|---|---|---|---|---|---|
| `gf.schema_version` | version integer NN | PK(version) | migracja | migracja | trwałe |
| `gf.snapshots` | tenant text NN, repo text NN, snapshot_id text NN, revision text NN, cli_sha text NN, nodes jsonb NN, weights jsonb NN, published_at timestamptz NN d:now() | PK(tenant,repo,snapshot_id) | worker (publish) | API, worker | aktywny + ≥30 dni okna rollbacku |
| `gf.skills` | id bigint NN identity, tenant text NN, repo text NN, snapshot_id text NN, urn text NN, skill_revision text NN, node text NN, status text NN, metadata json NN, body bytea NN, search_text text NN, embedding vector(1024) | PK(id), UNIQUE(tenant,repo,snapshot_id,urn), FK→gf.snapshots | worker (publish) | API | jak snapshot |
| `gf.heads` | tenant text NN, repo text NN, snapshot_id text NN | PK(tenant,repo), FK→gf.snapshots | worker (publish) | API | trwałe |
| `gf.router_indexes` | tenant text NN, repo text NN, snapshot_id text NN, index_sha text NN, n_docs integer NN, n_terms integer NN | PK(tenant,repo,snapshot_id), FK→gf.snapshots | worker | API | jak snapshot |
| `gf.router_terms` | tenant text NN, repo text NN, snapshot_id text NN, term text NN, postings bytea NN | PK(tenant,repo,snapshot_id,term), FK→gf.router_indexes | worker | API | jak snapshot |
| `gf.events` | tenant_id text NN, event_id bytea NN, event_type text NN, schema_version text NN, occurred_at text NN, received_at text NN, search_id text, load_id text, payload bytea NN | PK(tenant_id,event_id), IDX(tenant_id,event_type), (occurred_at), (tenant_id,search_id), (tenant_id,load_id) | API (append) | API | 90 dni (SEARCH-USE-TELEMETRY §5) |
| `gf.training_examples` | tenant_id text NN, example_id text NN, event_id bytea NN, schema_version text NN, dataset_version text NN, dataset_split {dev\|calibration\|test} NN, content_mode {metadata_only\|redacted_text} NN, case_id text?, task_id text?, search_id text?, use_id text?, snapshot_id text?, source_family text?, repository_hash text?, leaf_scope text?, candidate_rank integer?, candidate_skill_id text?, candidate_revision text?, decision text?, decision_reason text?, outcome text?, feedback_label text?, model_profile text?, router_revision text?, policy_revision text?, input_tokens bigint?, output_tokens bigint?, tool_calls integer?, latency_ms bigint?, context_bytes bigint?, provenance_sha256 text NN, features jsonb NN, created_at timestamptz NN d:now() | PK(tenant_id,example_id), UNIQUE(tenant_id,event_id), IDX(tenant_id,dataset_version,dataset_split,created_at) | Telemetry/Reporting (append) | owner-scoped telemetry/export | 90 dni MVP; dataset artifact retains its own declared retention |
| `gf.search_shadow` | tenant_id text NN, search_id text NN, repo text NN, snapshot_id text NN, encoder_id text NN, status text NN, sparse_ranked bytea NN, hybrid_ranked bytea NN, selected bytea NN, hybrid_selected bytea NN, timings jsonb NN, error text, created_at timestamptz NN d:now() | PK(tenant_id,search_id), IDX(created_at) | API (append) | eval | 90 dni |
| `gf.training_examples` | tenant_id text NN, example_id text NN, event_id bytea NN, schema_version text NN, dataset_version text NN, dataset_split text NN CHECK(dev\|calibration\|test), content_mode text NN CHECK(metadata_only\|redacted_text), case_id text?, task_id text?, search_id text?, use_id text?, snapshot_id text?, source_family text?, repository_hash text?, leaf_scope text?, candidate_rank int?, candidate_skill_id text?, candidate_revision text?, decision text?, decision_reason text?, outcome text?, feedback_label text?, model_profile text?, router_revision text?, policy_revision text?, input_tokens bigint?, output_tokens bigint?, tool_calls int?, latency_ms bigint?, context_bytes bigint?, provenance_sha256 text NN, features jsonb NN d:'{}', created_at timestamptz NN d:now() | PK(tenant_id,example_id), UNIQUE(tenant_id,event_id), IDX(tenant_id,dataset_version,dataset_split,created_at) | API (append) | eval | 90 dni |
| `gf.embedding_sets` | tenant text NN, repo text NN, snapshot_id text NN, encoder_id text NN, manifest jsonb NN, bundle_sha text NN, n_vectors integer NN | PK(tenant,repo,snapshot_id,encoder_id), FK→gf.snapshots | worker | API | jak snapshot; profil pgvector |
| `gf.embeddings` | tenant text NN, repo text NN, snapshot_id text NN, encoder_id text NN, urn text NN, skill_revision text NN, embedding vector(1024) NN | PK(tenant,repo,snapshot_id,encoder_id,urn), FK→gf.embedding_sets, gf.skills | worker | API | jak snapshot; profil pgvector |

`tenant` w `gf.*` **równa się** `org_id` z `gfm.orgs` (uuid jako tekst). Innego mapowania nie ma.

`gf.events` ma dodatkowo dwa indeksy dla modułu Telemetry/Reporting: `IDX(tenant_id,event_type,occurred_at)` (okno raportu czyta zamknięty zbiór typów jednej organizacji) oraz wyrażeniowy `IDX(tenant_id, gf.event_field(payload,'skill_id'))` (filtr per skill). `payload` jest `bytea`, bo ledger zachowuje dokładne bajty UTF-8 referencji, łącznie z NUL, którego `jsonb` nie przyjmuje — dlatego indeks nie może użyć `payload->>'skill_id'`. `gf.event_field(bytea, text) → text` jest funkcją IMMUTABLE, która dekoduje ostrożnie i zwraca `NULL` dla ładunku, którego nie potrafi sparsować: indeks nigdy nie odrzuci wiersza, który ledger przyjął. Obie zmiany są addytywne — żadna kolumna `gf.*` się nie zmienia.

### Schemat zarządczy (`gfm`)

| Tabela | Kolumny | Klucze i indeksy | Pisze | Czyta | Retencja |
|---|---|---|---|---|---|
| `gfm.users` | user_id uuid NN, email text NN, name text NN d:'', created_at timestamptz NN d:now() | PK(user_id), IDX(lower(email)) | API/Identity | API | do usunięcia konta |
| `gfm.identities` | provider text NN, subject text NN, user_id uuid NN → gfm.users, created_at timestamptz NN d:now() | PK(provider,subject), IDX(user_id) | API/Identity | API | jak user |
| `gfm.orgs` | org_id uuid NN, slug text NN, name text NN, created_at timestamptz NN d:now() | PK(org_id), UNIQUE(slug) | API/Identity | API, worker | do usunięcia org |
| `gfm.memberships` | org_id uuid NN → gfm.orgs, user_id uuid NN → gfm.users, role text NN CHECK(owner\|member), joined_at timestamptz NN d:now() | PK(org_id,user_id), IDX(user_id) | API/Identity | API (każde żądanie) | jak org |
| `gfm.teams` | org_id uuid NN → gfm.orgs, team_id uuid NN, name text NN, created_at timestamptz NN d:now() | PK(org_id,team_id), UNIQUE(team_id), UNIQUE(org_id,name), IDX(org_id) | API/Identity | API | jak org |
| `gfm.team_members` | org_id uuid NN → gfm.orgs, team_id uuid NN → gfm.teams, user_id uuid NN → gfm.users | PK(org_id,team_id,user_id), IDX(org_id,user_id), FK(org_id,team_id) | API/Identity | API | jak org |
| `gfm.invitations` | org_id uuid NN, invitation_id uuid NN, token_sha256 text NN, email text NN, role text NN CHECK, created_by uuid, created_at timestamptz NN d:now(), expires_at timestamptz NN, accepted_by uuid, accepted_at timestamptz, revoked_at timestamptz | PK(org_id,invitation_id), UNIQUE(token_sha256) | API/Identity | API | 30 dni po wygaśnięciu |
| `gfm.sessions` | id_sha256 text NN, user_id uuid NN → gfm.users, csrf_token text NN, created_at timestamptz NN d:now(), expires_at timestamptz NN, revoked_at timestamptz, last_seen_at timestamptz | PK(id_sha256), IDX(user_id) | API/Identity | API (każde żądanie) | 7 dni + czyszczenie |
| `gfm.tokens` | token_id uuid NN, token_sha256 text NN, kind text NN CHECK(personal\|installation\|ci), user_id uuid, org_id uuid, repo_id text, scopes text[] NN d:'{}', name text NN d:'', harness text, adapter_version text, capabilities jsonb, created_at timestamptz NN d:now(), last_seen_at timestamptz, revoked_at timestamptz | PK(token_id), UNIQUE(token_sha256), IDX(org_id) | API/Identity | API (każde żądanie) | do odwołania |
| `gfm.github_installations` | org_id uuid NN, installation_id bigint NN, account text NN, repositories jsonb NN d:'[]', suspended_at timestamptz, created_at timestamptz NN d:now(), updated_at timestamptz NN d:now() | PK(org_id,installation_id), UNIQUE(installation_id) | API/github (webhook) | API, worker | jak org |
| `gfm.github_deliveries` | delivery_id text NN, payload_sha256 text NN, received_at timestamptz NN d:now() | PK(delivery_id), IDX(received_at) | API/github (webhook) | API | 30 dni |
| `gfm.org_credentials` | org_id uuid NN → gfm.orgs, provider text NN CHECK(openrouter), credential_id uuid NN, key_id text NN, nonce bytea NN, ciphertext bytea NN, last4 text NN, name text NN d:'', created_by uuid, created_at timestamptz NN d:now() | PK(org_id,provider), UNIQUE(credential_id) | API/secrets | worker (otwiera w pamięci na czas joba) | jak org |
| `gfm.live_runs` | org_id uuid NN → gfm.orgs, run_id uuid NN, state text NN d:'queued' CHECK(queued\|running\|succeeded\|partial\|failed\|cancelled), prompt text NN, model text NN, limits jsonb NN d:'{}', cost jsonb NN d:'{}', error text, created_by uuid, created_at timestamptz NN d:now(), started_at timestamptz, finished_at timestamptz | PK(org_id,run_id), UNIQUE(org_id) WHERE state IN ('queued','running'), IDX(org_id,created_at DESC) | API/live (start, anulowanie), worker (postęp) | oba | 90 dni po `finished_at` |
| `gfm.live_run_targets` | org_id uuid NN, run_id uuid NN, repo_id text NN, state text NN d:'queued' CHECK(queued\|running\|done\|failed\|skipped), job_id uuid, findings integer NN d:0, error text, started_at timestamptz, finished_at timestamptz | PK(org_id,run_id,repo_id), FK(org_id,run_id)→gfm.live_runs, IDX(org_id,run_id,state) | API (fan-out), worker | oba | jak przebieg |
| `gfm.live_run_events` | org_id uuid NN, run_id uuid NN, seq bigint NN, at timestamptz NN d:now(), repo_id text, type text NN CHECK(run.started\|repo.started\|model.delta\|finding\|repo.finished\|run.finished\|error), payload jsonb NN d:'{}' | PK(org_id,run_id,seq), FK(org_id,run_id)→gfm.live_runs | worker (dopisuje), API (`run.started`) | API | jak przebieg |
| `gfm.device_codes` | device_code_sha256 text NN, user_code text NN, state text NN CHECK(pending\|approved\|denied\|expired), user_id uuid, created_at timestamptz NN d:now(), expires_at timestamptz NN, last_poll_at timestamptz | PK(device_code_sha256), UNIQUE(user_code) | API/Identity | API | 24 h |
| `gfm.auth_states` | state_sha256 text NN, kind text NN CHECK(login\|link), provider text NN, user_id uuid, return_to text NN d:'/', created_at timestamptz NN d:now(), expires_at timestamptz NN | PK(state_sha256) | API/Identity | API | 10 min |
| `gfm.audit` | org_id uuid NN, audit_id bigint NN identity, at timestamptz NN d:now(), actor text NN, action text NN, entity text NN, revision text, request_id text NN d:'' | PK(org_id,audit_id), IDX(org_id,at DESC,audit_id DESC) | wszystkie moduły API | owner | 12 miesięcy |
| `gfm.idempotency` | org_id uuid NN, principal_id text NN, key text NN, payload_sha256 text NN, status integer NN d:0, body bytea NN d:'', created_at timestamptz NN d:now() | PK(org_id,principal_id,key) | API/mgmt | API/mgmt | 7 dni |
| `gfm.jobs` | org_id uuid NN, job_id uuid NN, repo_id text, import_id uuid, kind text NN, state text NN d:'queued' CHECK, payload jsonb NN d:'{}', input_digest text, recipe_version text, idempotency_key text, attempts integer NN d:0, max_attempts integer NN d:3, lease_until timestamptz, worker_id text, generation integer NN d:0, checkpoint jsonb, limits jsonb, cost jsonb, result jsonb, error text, created_at timestamptz NN d:now(), started_at timestamptz, finished_at timestamptz | PK(org_id,job_id), UNIQUE(job_id), UNIQUE(org_id,idempotency_key) WHERE NOT NULL, IDX(kind,state,created_at) | API (enqueue), worker (postęp) | oba | 90 dni po `finished_at` |
| `gfm.repos` | org_id uuid NN → gfm.orgs, repo_id text NN, name text NN d:'', git_host_url text NN d:'', created_at timestamptz NN d:now() | PK(org_id,repo_id) | API/Import | wszystkie | jak org |
| `gfm.repo_acl_policies` | org_id uuid NN, repo_id text NN, enabled bool NN d:true, created_by uuid, created_at timestamptz NN d:now() | PK(org_id,repo_id), FK(org_id,repo_id)→gfm.repos | API/Identity | wszystkie | jak repo |
| `gfm.repo_members` | org_id uuid NN, repo_id text NN, user_id uuid NN, access text NN CHECK(read\|write), created_by uuid, created_at timestamptz NN d:now() | PK(org_id,repo_id,user_id), FK(org_id,repo_id)→gfm.repos, IDX(user_id) | API/Identity | wszystkie | jak repo |
| `gfm.repo_reviewers` | org_id uuid NN, repo_id text NN, user_id uuid NN, assigned_by uuid, created_at timestamptz NN d:now() | PK(org_id,repo_id,user_id), FK(org_id,repo_id)→gfm.repos, IDX(user_id) | API/Identity | review | jak repo |
| `gfm.blobs` | org_id uuid NN, sha256 text NN, size_bytes bigint NN, content bytea NN, created_at timestamptz NN d:now(), last_referenced_at timestamptz NN d:now() | PK(org_id,sha256), IDX(org_id,last_referenced_at) | API/Import | worker | 30 dni dla wejść nieużywanych; blob wskazywany przez aktywną rewizję nie wygasa |
| `gfm.imports` | org_id uuid NN, import_id uuid NN, repo_id text NN, state text NN d:'created' CHECK, manifest_digest text NN, commit text, complete boolean NN d:false, dirty boolean NN d:false, cli_version text NN d:'', scan_profile text NN d:'default', manifest jsonb NN, publish boolean NN d:true, reused_import_id uuid, created_by uuid, error text, created_at timestamptz NN d:now(), updated_at timestamptz NN d:now(), finalized_at timestamptz | PK(org_id,import_id), FK(org_id,repo_id)→gfm.repos, UNIQUE(org_id,repo_id,manifest_digest) WHERE state<>'failed', IDX(org_id,repo_id,created_at DESC) | API (utworzenie), worker (postęp) | oba | 90 dni; manifest zostaje po wygaśnięciu blobów |
| `gfm.import_files` | org_id uuid NN, import_id uuid NN, path text NN, sha256 text NN, size_bytes bigint NN, kind text NN CHECK(skill\|document\|config\|resource), status text NN d:'pending' CHECK, reason text, skill_id text, mode text NN d:'100644' | PK(org_id,import_id,path), FK→gfm.imports, IDX(org_id,import_id,status) | worker/Import | API | jak import |
| `gfm.skills` | org_id uuid NN, skill_id text NN, repo_id text NN, name text NN, description text NN d:'', scope text NN, owner text, path text NN, source_layer text, knowledge_layer text NN d:'unclassified', source_status text NN d:'active', publication_status text NN d:'draft' CHECK, current_revision_id text, published_revision_id text, published_snapshot_id text, first_import_id uuid, last_import_id uuid, created_at timestamptz NN d:now(), updated_at timestamptz NN d:now() | PK(org_id,skill_id), UNIQUE(org_id,repo_id,path) WHERE source_status<>'removed', IDX(org_id,repo_id,scope), (org_id,repo_id,publication_status), (org_id,repo_id,lower(name)) | worker (import), API (decyzja) | API, worker | jak org; nigdy nie usuwamy przy `source_removed` |
| `gfm.skill_revisions` | org_id uuid NN, revision_id text NN, skill_id text NN, content_sha256 text NN, blob_sha256 text NN, frontmatter jsonb NN, commit text, import_id uuid, proposal_id uuid, origin text NN d:'source' CHECK(source\|parsed\|inferred\|human), source_path text NN, card_revision text, created_at timestamptz NN d:now() | PK(org_id,revision_id), FK(org_id,skill_id)→gfm.skills, FK(org_id,blob_sha256)→gfm.blobs, IDX(org_id,skill_id,created_at DESC) | worker, API | API, worker | jak org |
| `gfm.skill_resources` | org_id uuid NN, revision_id text NN, path text NN, sha256 text NN, size_bytes bigint NN, type text NN, required boolean NN d:false, available boolean NN d:false | PK(org_id,revision_id,path), FK→gfm.skill_revisions | worker | API, worker | jak rewizja |
| `gfm.scopes` | org_id uuid NN, repo_id text NN, scope text NN, owner text, parent text, paths text[] NN d:'{}', source text NN d:'guidefold_yaml' CHECK(guidefold_yaml\|directory\|codeowners\|unknown), import_id uuid, updated_at timestamptz NN d:now() | PK(org_id,repo_id,scope), IDX(org_id,repo_id,parent) | worker/Knowledge | API | jak org |
| `gfm.relations` | org_id uuid NN, relation_id uuid NN, from_skill_id text NN, to_skill_id text NN, type text NN CHECK(derived_from\|requires\|refines\|similar\|conflicts_with), provenance text NN d:'source', revision_id text, proposal_id uuid, created_at timestamptz NN d:now() | PK(org_id,relation_id), UNIQUE(org_id,from_skill_id,to_skill_id,type,revision_id), IDX(org_id,to_skill_id,type) | worker, API | API, worker | jak rewizja |
| `gfm.documents` | org_id uuid NN, document_id uuid NN, repo_id text NN, path text NN, sha256 text NN, kind text NN, scope text, size_bytes bigint NN, import_id uuid NN, commit text, created_at timestamptz NN d:now() | PK(org_id,document_id), UNIQUE(org_id,repo_id,path,sha256), IDX(org_id,repo_id,scope) | worker/Import | API, worker | jak import |
| `gfm.proposals` | org_id uuid NN, proposal_id uuid NN, repo_id text NN, import_id uuid, job_id uuid, kind text NN CHECK, state text NN d:'draft' CHECK, scope text, owner text, target_skill_id text, target_revision_id text, expected_revision text, candidate_path text NN, candidate_sha256 text NN, candidate_blob_sha256 text NN, candidate_frontmatter jsonb NN, sources jsonb NN d:'[]', recipe_version text NN, generator text NN, model text, cache_key text NN, cost jsonb, created_at timestamptz NN d:now(), updated_at timestamptz NN d:now() | PK(org_id,proposal_id), UNIQUE(org_id,cache_key), IDX(org_id,state,created_at DESC) | worker (generowanie), API (decyzja) | API | jak org |
| `gfm.proposal_fields` | org_id uuid NN, proposal_id uuid NN, field text NN, origin text NN CHECK(source\|parsed\|inferred\|human), source_path text, source_sha256 text, line_from integer, line_to integer, needs_confirmation boolean NN d:false, value_sha256 text | PK(org_id,proposal_id,field), FK→gfm.proposals | worker | API | jak propozycja |
| `gfm.decisions` | org_id uuid NN, decision_id uuid NN, proposal_id uuid NN, decision text NN CHECK(approve\|edit\|reject), reason text NN, actor_user_id uuid NN, expected_revision text, result_revision_id text, request_id text NN d:'', at timestamptz NN d:now() | PK(org_id,decision_id), FK→gfm.proposals, IDX(org_id,proposal_id,at DESC) | API/Review | API | 12 miesięcy |
| `gfm.exports` | org_id uuid NN, export_id uuid NN, proposal_id uuid NN, base_commit text, files jsonb NN, patch text NN, files_digest text NN, created_by uuid, created_at timestamptz NN d:now() | PK(org_id,export_id), FK→gfm.proposals, UNIQUE(org_id,proposal_id,files_digest) | API/Review | API, worker (sync) | jak propozycja |
| `gfm.publications` | org_id uuid NN, publication_id uuid NN, repo_id text NN, import_id uuid, job_id uuid, snapshot_id text, state text NN d:'building' CHECK(building\|validated\|active\|failed\|superseded), commit text, n_skills integer NN d:0, builder_sha256 text, validation jsonb, error text, activated_at timestamptz, created_at timestamptz NN d:now(), updated_at timestamptz NN d:now() | PK(org_id,publication_id), UNIQUE(org_id,repo_id,snapshot_id), IDX(org_id,repo_id,created_at DESC) | worker/Review | API | jak snapshot |
| `gfm.owner_queue` | org_id uuid NN, item_id uuid NN, repo_id text NN, skill_id text NN, revision_id text, reason text NN CHECK(negative_feedback\|source_changed\|source_removed\|zero_loads\|missing_dependency), evidence jsonb NN d:'{}', since timestamptz NN d:now(), state text NN d:'open' CHECK(open\|resolved), decision text CHECK(reviewed\|fixed_in_git\|no_change), decision_reason text, decided_by uuid, decided_at timestamptz | PK(org_id,item_id), UNIQUE(org_id,skill_id,reason,revision_id) NULLS NOT DISTINCT WHERE state='open', IDX(org_id,state,since DESC) | worker (drift), API (decyzja) | API | 12 miesięcy po `resolved` |
| `gfm.adapter_health` | org_id uuid NN, harness text NN, installation_id uuid, adapter_version text, capabilities jsonb, last_seen_at timestamptz, produced bigint NN d:0, acknowledged bigint NN d:0, dropped bigint NN d:0, oldest_lag_s integer, updated_at timestamptz NN d:now() | PK(org_id,harness) | API/Telemetry | API | 90 dni |

`gfm.adapter_health` jest **projekcją**, nie źródłem prawdy: API zapisuje ją przy przyjęciu partii na `/v1/events:batch`, wyłącznie ze zdarzeń, które ta partia faktycznie zaakceptowała (powtórka daje `duplicate` i nic nie zmienia), i wyłącznie dla organizacji zweryfikowanego principala — zdarzenia nie niosą tenanta i nie mogą go przenieść. `harness` to `producer` zdarzenia; `installation_id` pochodzi z tokenu instalacji, gdy partię wysłał token instalacji. Liczniki `produced`/`acknowledged`/`dropped` sumują to, co adapter zaraportował w `telemetry_health`; `oldest_lag_s` **zastępuje** poprzednią wartość, bo to stan bieżący, a adapter, który nadrobił zaległości, nie może dalej wyglądać na spóźniony. Utrata tej tabeli to utrata diagnostyki, nigdy obserwacji — zdarzenia zostają w `gf.events`.

Feedback z UI **nie** ma własnej tabeli: `POST …/feedback` zapisuje zdarzenie `skill_feedback` do `gf.events` z `tenant_id = org_id` i zwraca `judgment_id`, żeby jedna definicja oceny obsługiwała adapter i UI.

**Retencja blobów** jest ręcznie wywoływaną komendą operatora, `guidefold-search blobs-retain [days] [now]` (na wzór istniejącego `telemetry-retain`), **nie** rodzajem (`kind`) joba z §8 — nic w kolejce `gfm.jobs` jej nie leasuje. „Referencowany" sha256 to taki, który występuje w `gfm.skill_revisions`, `gfm.skill_resources` lub `gfm.documents` nie-zarchiwizowanego skilla, albo należy do importu młodszego niż `days` (domyślnie 30, jak w kolumnie Retencja `gfm.blobs`). Nie-referencowany blob starszy niż `days` jest usuwany; wiersze, które go opisywały (import, skill, rewizja), nie są ruszane.

**Dlaczego bloby i telemetria są w Postgres w MVP.** Jedna baza oznacza jedną transakcję dla enqueue joba razem z wierszami, które go uzasadniają, jeden model uprawnień i jedno miejsce retencji; wolumen pilota (100 MiB na import, 200 skilli) mieści się bez obiektowego magazynu, a GCS dodałby drugą granicę autoryzacji i drugi tor awarii przed pierwszym klientem (ADR-0033). Port wyjściowy jest już zdefiniowany: `BlobStore` z operacjami `Put(org, sha, bytes)`, `Get(org, sha)`, `Stat`, `Delete` — adapter Postgres dziś, adapter GCS (obiekty pod `<bucket>/<org_id>/<sha256>`, dostęp krótkożyjącymi referencjami) później, bez zmiany domeny. Migracja polega na przepisaniu zawartości i przełączeniu adaptera; ten kontrakt się wtedy nie zmienia, bo `gfm.blobs.content` jest jedyną kolumną, którą traci.

## 8. Kontrakt API–worker

Job jest jedynym kanałem między API a workerem. Enqueue odbywa się w transakcji wywołującego (`jobs.Queue.Enqueue(ctx, tx, job)`), więc job nigdy nie istnieje bez wierszy, które go uzasadniają.

| Pole joba | Źródło | Reguła |
|---|---|---|
| `schema_version` | API | W `payload`; worker odrzuca nieznaną wersję zamiast zgadywać |
| `org_id`, `repo_id`, `import_id` | API | Worker sprawdza tożsamość org i aktualne uprawnienie **przed** pracą |
| `kind` | API | Z zamkniętej listy poniżej |
| `input_digest` | API | `manifest_digest` albo sha256 posortowanych sha wejść; podstawa dedupe |
| `recipe_version` / `model_revision` | API | Część klucza cache generowania |
| `idempotency_key` | API | UNIQUE `(org_id, idempotency_key)`; ponowne enqueue zwraca istniejący job |
| `limits` | API | `max_files, max_bytes, max_tokens, max_groups (5), max_proposals_per_group (5), max_neighbours (10), max_calls, max_usd` |
| `generation` | queue | Rośnie przy każdym lease; każdy zapis workera niesie swoją generację |
| `checkpoint` | worker | Pozwala wznowić bez duplikowania kandydatów (dedupe po `input_digest`) |
| `cost` | worker | `JobCost`; `usd_uncertain` dla opłat po timeoucie |

Lease: `UPDATE gfm.jobs SET state='leased', generation=generation+1, … WHERE state='queued' OR (state='leased' AND lease_until < now())`. Lease trwa 30 s, heartbeat co najwyżej 10 s. Zapis z nieaktualną generacją nie zmienia nic i zwraca `job_fenced` (`jobs.ErrFenced`); heartbeat, który zobaczy fencing, anuluje kontekst handlera, więc spóźniony worker przestaje pisać. Backoff 5 s, 10 s, 20 s… do 5 minut, `max_attempts` domyślnie 3.

| `kind` | Wejście | Wyjście | Checkpoint | Limity |
|---|---|---|---|---|
| `import.parse` | `import_id`, manifest, bloby | `gfm.skills`, `skill_revisions`, `skill_resources`, `documents`, `scopes`, `import_files.status`, drift → `owner_queue` | ostatnia przetworzona ścieżka | `max_files`, `max_bytes`; bez wywołań modelu |
| `proposal.generate` | grupa wejść (`input_digest`, każde wejście z własnym `scope`/`owner`), `payload.kind:{extraction\|enrichment\|consolidation}!`, `payload.profile:{default\|one_shot}?`, `limits` | `gfm.proposals`, `proposal_fields`, `relations` (kandydackie) | ostatnia grupa i wykorzystany budżet | `max_groups`, `max_proposals_per_group`, `max_neighbours`, `max_calls`, `max_usd`, `max_tokens` |
| `publish.build` | `import_id`, zatwierdzony digest | `gfm.publications`, `gf.snapshots/skills/heads`, `router_indexes/terms` | etap budowy | rozmiar drzewa; bez wywołań modelu |
| `ascend.run` | `org_id`, `repo_id`, `installation_id`, `pr_number`, `head_sha`, `base_ref`, `changed_paths[]` | gałąź `guidefold/ascend-pr-<n>` i PR do `base_ref` przez token instalacji; `result: {pr_url, written[], levels[], calls}` | ostatni ukończony poziom (scope) | `max_levels (6)`, `max_calls`, `max_usd`, `max_tokens` |

| `live.plan` | `run_id`, `repos[]` (puste = wszystkie z instalacją) | wiersze `gfm.live_run_targets`, po jednym jobie `live.repo` na cel, zdarzenie `run.started` | lista celów już zakolejkowanych | `max_repos (50)` |
| `live.repo` | `run_id`, `repo_id`, `installation_id` | zdarzenia `repo.started`, `model.delta`, `finding`, `repo.finished` w `gfm.live_run_events`; stan i `findings` w `live_run_targets` | ostatni ukończony plik źródłowy | `max_tokens`, `max_usd`, `max_files` |

`live.plan` i `live.repo` (ADR-0044) **czytają** repozytorium przez API treści GitHuba tokenem instalacji — wyłącznie `AGENTS.md` i `**/.agents/skills/**/SKILL.md`. Nie klonują, nie uruchamiają niczego z repozytorium, nie zakładają gałęzi ani PR-a; to, co agent proponuje zmienić, idzie do istniejącego przepływu propozycji. Klucz modelu należy do organizacji (ADR-0043), jest otwierany w pamięci na czas jednego joba i nigdy nie trafia do `payload`, `checkpoint`, `result`, logu ani komunikatu błędu. Wyczerpanie `max_usd` albo `max_tokens` kończy przebieg jako `partial` z `live_run_budget_exhausted`, po zapisaniu wszystkich dotychczasowych zdarzeń. Anulowanie zatrzymuje `live.repo` na najbliższym checkpoincie, a nie na końcu repozytorium. Polityka sieciowa workera musi mieć wyjście do endpointu OpenRoutera obok GitHuba; do czasu tej zmiany job kończy się `skipped` z `github_app_not_configured`.

`ascend.run` (ADR-0036) wykonuje w workerze dokładnie to, co `guidefold ascend` w CI klienta (ADR-0035): klonuje `head_sha` tokenem instalacji do `/work`, uruchamia zaufany plik CLI z obrazu workera (`skills/guidefold/scripts/guidefold ascend --since <base_ref>`), a zapisane pliki wypycha na gałąź i otwiera PR, którego recenzentami są CODEOWNERS katalogów rodzica. Nigdy nie wykonuje skryptów z klonowanego repozytorium. Klucz modelu z `GUIDEFOLD_ASCEND_API_KEY_FILE`, klucz aplikacji z `GITHUB_APP_PRIVATE_KEY_FILE`, sekret webhooka z `GITHUB_WEBHOOK_SECRET_FILE` — wzorzec `*_FILE` jak u generatora. Obraz workera musi mieć `git`, a polityka sieciowa workera wyjście do `api.github.com`, `github.com` i endpointu modelu — dziś ma tylko DNS i bazę (deploy/k8s/chart/templates/worker.yaml), więc do czasu tej zmiany job kończy się `skipped` z `github_app_not_configured`.

Jest jeden rodzaj joba dla wszystkich propozycji, `proposal.generate`; rozróżnia je wyłącznie `payload.kind`. `POST {repo_base}/imports/{import_id}/proposals:generate` przyjmuje tablicę `kinds` i zakłada po jednym jobie na każdy żądany rodzaj, więc odpowiedź `{job_ids, plan}` może nieść kilka `job_id`. Nie ma osobnego `kind` joba `consolidate`.

Dla `payload.kind = consolidation` wejściem jest zbiór skilli **scope'u nadrzędnego i jego bezpośrednich dzieci**, a nie jednego scope'u: skille scope'u trafiają do grupy scope'u, który je zawiera, a skille scope'u najwyższego poziomu do grupy `_root`. Każdy skill należy do dokładnie jednej grupy — wspólny element zaproponowany pod dwoma różnymi przodkami byłby dwiema propozycjami z dwoma kluczami cache dla jednej wiedzy. Wewnątrz grupy porównywane są wszystkie pary, bo wspólny element widoczny dopiero w trzecim i piątym runbooku jest właśnie tym, którego człowiek ręcznie nie znajdzie; `max_neighbours` ogranicza zarówno wkład jednego scope'u, jak i liczbę scope'ów wnoszących do grupy, więc grupa ma najwyżej `max_neighbours²` skilli (100 przy domyślnych) i liczba porównań jest kwadratowa w małej stałej, **nigdy** w rozmiarze repozytorium. Limit nie jest nakładany na sklejoną listę: obcięcie sklejenia pozwoliłoby pierwszemu scope'owi w kolejności nazw wydać cały budżet i zostawić rodzeństwo bez porównania — czyli zgubić dokładnie te pary, dla których konsolidacja istnieje, i pary, które wcześniejsze grupowanie po pojedynczym scope już porównywało. To nadal nie jest przebieg all-pairs po katalogu.

Wspólny element trafia do scope'u będącego najgłębszym wspólnym przodkiem swoich źródeł (`_root`, gdy nie mają innego), niesie `derived_from` do każdego źródła i proponuje `refines` z każdego źródła w górę do siebie (§5.4). Podniesienie scope wymaga ≥2 różnych scope'ów źródłowych i ownera scope'u docelowego jako ownera propozycji; inaczej zatwierdzenie kończy się `422 scope_widening_not_approved`. Każda odrzucona para ma jawny powód w `result.abstentions[]` (`no_shared_procedure`, `too_few_procedures`, `version_mismatch`, `condition_mismatch`, `contradictory_steps`, `already_consolidated`, `max_proposals_reached`); milczące pominięcie pary jest błędem.

`payload.profile` jest tym, co wybrał wywołujący na `…/proposals:generate` (§4.2). Wpływa wyłącznie na `limits.max_groups` zapisane w wierszu joba; worker czyta limity z wiersza, nie z profilu. Checkpoint jest **na grupę**: `{groups_done, cost, abstentions}` po każdej ukończonej grupie, więc przerwany przebieg one-shot wznawia się od następnej grupy, a grupy już zrobione nie tworzą nic nowego, bo klucz cache je odrzuca.

`publish.build` materializuje drzewo importu z blobów do prywatnego katalogu pod `.guidefold/worker/`, uruchamia **zaufany** builder `tools/worker/build_tree.py` (używa `load_map`/`Index.build`/`with_router_index` z CLI; sha CLI jest sha polityki), waliduje graf i dopiero wtedy zapisuje katalog w jednej transakcji. Do snapshotu wchodzą wyłącznie skille o statusie kwalifikującym do publikacji; nieudana walidacja zostawia poprzedni head. Obraz API **nie zawiera Pythona**; builder jest narzędziem obrazu workera. Worker nigdy nie wykonuje skryptów z importowanych pakietów.

Generator: `GUIDEFOLD_GENERATOR=none|deterministic|openai|anthropic`. `none` kończy job jako `skipped` z `llm_not_configured` — import istniejących skilli pozostaje użyteczny (U2.7). `deterministic` (recepta `det-1`) obsługuje testy i demo offline. Dostawcy HTTP używają `*_API_KEY_FILE`, timeoutów i ≤2 retry dla niepoprawnego JSON-a. Klucz cache = sha256(org, posortowane sha wejść, `recipe_version`, `model_revision`); propozycja odrzucona z tym samym kluczem nie jest generowana ponownie.

## 9. Inwarianty i testy obowiązkowe

| Inwariant | Bramka / AC | Test |
|---|---|---|
| Org A i B z tym samym `repo_id` i URN, ciepły cache, retry, rollback — brak przecieku treści, metadanych i liczników | bramka 1; U3.3, P02 | Go: równoległy test warstwy aplikacji; UI: odpowiedź org A po przejściu do B |
| `Store` nie trzyma jednego globalnego Catalogu; cache kluczowany `(org_id, repo_id, snapshot_id, policy)` z ograniczeniem rozmiaru | bramka 1 | Go: test wypełnienia cache dwiema org |
| Draft nigdy nie pojawia się w SEARCH ani USE | U2.6 | Go: publikacja z draftem w katalogu → snapshot bez niego |
| Snapshot aktywowany wyłącznie po walidacji; cykl lub brak zależności zostawia poprzedni head | bramka 3; U2.6 | Go: `graph_cycle`, `missing_dependency`, `missing_required_resource` |
| USE 1.2: łańcuch głębszy niż dwa, diament, >4 karty, `denied`, zmiana snapshotu → `409 snapshot_changed` | bramka 2; U5.4, U5.5 | Go: pięć nazwanych testów kontraktu 1.2 |
| 1.1 nie zyskuje gwarancji przez etykietę | bramka 2 | Go: klient 1.1 dostaje dotychczasową semantykę i `composition.status: not_evaluated` |
| Odwołanie członkostwa lub tokenu blokuje API natychmiast; UI odsłania dane najwyżej 60 s | U3.4 | Go: żądanie po `DELETE` członka; UI: bezczynna karta i wznowienie z ciepłym cache |
| Brak sekretów w URL, logu, `details` i telemetrii | U3.5 | Go: test allowlisty logu; przegląd `details` w handlerach |
| HTTP 200 na USE nie zwiększa „użyto"/„pomogło"; `unknown` ≠ 0 | U6.2 | Parytet z `tools/telemetry/report.py` na wspólnym fixture zdarzeń |
| Ledger: retry, duplikat, zdarzenie spóźnione i korekta feedbacku dają oczekiwane liczniki | U6.1 | Replay tej samej partii: 0 nowych `accepted`, liczniki bez zmian |
| Częściowy skan (`complete:false`) nie powoduje usunięć ani `source_removed` | U1.5, U9 | Worker: manifest częściowy po pełnym |
| Powtórny import tego samego manifestu nie tworzy nowych pozycji kolejki ownera | U9 | Worker: dwa przebiegi, `owner_queue` bez przyrostu |
| Ten sam manifest → 0 nowych blobów, `reused_import_id` ustawione | U1.4 | API: dwa `POST …/imports` z tym samym digestem |
| Ten sam commit → identyczne bajty manifestu | U1.1, U1.4 | CLI: dwa `scan --json` |
| Idempotencja: ten sam klucz i payload → ta sama odpowiedź; inny payload → `409` | §3 | Go: trzy żądania (nowe, powtórka, kolizja) |
| Zapis workera ze starą generacją nie nadpisuje nowszego | kontrakt jobów | Go: `jobs` test fencingu po wygaśnięciu lease |
| Rewizja niedostępna to `404`, nigdy podmiana na najnowszą | U4.1, U5.5 | Go i UI: żądanie usuniętej rewizji |
| Wymagany zasób pakietu nieobecny blokuje publikację | U1.7, U5.5 | Worker: `missing_required_resource` |
| Retencja surowego uploadu nie psuje USE aktywnej rewizji ani rollbacku | bramka 3 | Worker: wygaszenie blobów spoza aktywnego snapshotu |

## 10. Wersjonowanie

`contract_version` opisuje ten dokument i management API; `schema_version` w odpowiedzi opisuje ładunek: `mgmt-1` dla `/api/v1`, `1.1` i `1.2` dla `/v1`.

| Rodzaj zmiany | Wersja | Wymagania |
|---|---|---|
| Nowe pole odpowiedzi, nowy endpoint, nowy kod błędu, nowa kolumna nullable | `contract_version` PATCH/MINOR, `schema_version` bez zmian | Wpis w §11, aktualizacja OpenAPI, test odrzucenia nieznanego pola żądania |
| Zmiana znaczenia pola, usunięcie pola, zawężenie dziedziny, nowy wymagany parametr | `contract_version` MAJOR i nowe `schema_version` (`mgmt-2`, `1.3`) | Negocjowana wersja, równoległe wsparcie starej, ADR |
| Nowa gwarancja dostawy (closure, budżety, zasoby) | `1.2` i wyżej | Pełny zestaw testów z §9; 1.1 nie zmienia zachowania |

Serwer odrzuca nieznane pola żądania i nieznane wersje (`400`); klient toleruje addytywne pola odpowiedzi. `GET /health/ready` ogłasza wspierane wersje w `api_schema_versions`.

Wsparcie klienta CLI: jedna wersja `contract_version` MAJOR wstecz przez co najmniej 90 dni od wydania następnej. `guidefold doctor` zgłasza niezgodność wersji jako ostrzeżenie z konkretną komendą aktualizacji, a nie cichy fallback. Adapter, który nie potrafi obsłużyć zadeklarowanej wersji, **nie** ponawia żądania przez ciche usunięcie kontekstu workspace.

## 11. Changelog

| Wersja | Data | Zmiana |
|---|---|---|
| 1.0.0 | 2026-09-06 | Pierwsza wersja obowiązująca. Zastępuje roboczy brief implementacyjny: ustala tożsamość i autoryzację, kopertę błędów z zamkniętą listą kodów, sześć tabel endpointów, DTO, maszyny stanów, schematy `gf`/`gfm`, kontrakt API–worker oraz inwarianty testowe. `/v1/search`, `/v1/use` i `/v1/events:batch` pozostają pod kontraktem 1.1 i dokumentem telemetrii. |
| 1.0.1 | 2026-09-06 | Addytywne doprecyzowania z decyzji tech leada (1–10):<br>1. Publikacja: dwa słowniki (`gfm.publications.state` silnika i `ImportPublication.state` importu) z jawnym mapowaniem `published ⇔ active` (§5.2, §6).<br>2. Zaproszenie już istniejącego członka → `409 member_exists`, dopisany do zamkniętej listy kodów (§3).<br>3. Tokeny są w MVP wyłącznie odwoływalne, bez `expires_at` (YAGNI); dotyczy też tokenu osobistego z device flow; `guidefold logout` odwołuje tylko token CLI, nie sesję UI (§2).<br>4. Usunięto `rate_limited` z zamkniętej listy (nieużywany, brak limitera); retrieval nadal ma `overloaded`/`telemetry_overloaded` (§3, §4.1).<br>5. Retencja blobów to operatorska komenda `guidefold-search blobs-retain [days] [now]`, nie rodzaj joba; zdefiniowano „referencowany" sha256 (§7).<br>6. `{org}` przyjmuje uuid lub slug; odpowiedzi zawsze niosą `org_id`; zmiana slugu jest wyłącznie działaniem ownera i unieważnia stare adresy (§5.1).<br>7. Przypięto kolejność kolumn CSV `usage/export` oraz kształt eksportu JSON (§5.5).<br>8. `/metrics` jest trwale wewnętrzny (ADR-0030): poza OpenAPI i poza publicznym ingressem (§4.5).<br>9. Jeden rodzaj joba `proposal.generate` z `payload.kind ∈ extraction\|enrichment\|consolidation`; usunięto osobny `consolidate` (§8).<br>10. Potwierdzono bez zmiany treści: `ImportState` już zawierał `uploading`, `ImportPublication.state` już był `none\|building\|published\|failed` w kontrakcie i w `ui/src/api/decoders.ts` — luka była tylko w analizie, nie w dokumencie ani w kodzie. |
| 1.0.2 | 2026-09-07 | Addytywne doprecyzowanie z decyzji tech leada (11): `/v1/search`, `/v1/use`, `/v1/events:batch` zostają przy niezmienionym schemacie JSON 1.1 (nieznane pola najwyższego poziomu odrzuca schemat harnessu), więc wybór org/repo dla principali `session`/`personal` pochodzi z nowych nagłówków `X-Guidefold-Org`/`X-Guidefold-Repo`, udokumentowanych w §2 (tożsamość, kolejność źródeł) i §3 (tabela nagłówków). Kolejność rozstrzygania: wiązanie tokenu > nagłówki > `workspace.repo_id` z ciała (1.1) > jedyne membership principala / jedyne repo organizacji. Sprzeczny nagłówek wobec tokenu instalacji nadal daje `403 organization_not_permitted`/`repository_not_permitted` — opisy tych kodów w §3 rozszerzone o ten przypadek; token operatora (legacy) nie zmienia zachowania. Potwierdzono bez zmiany treści: `idempotency_key_required` (400, mutacja bez klucza) i `idempotency_in_progress` (409, powtórka podczas trwającego żądania) już były w zamkniętej liście kodów §3 i w opisie idempotencji — luka była tylko w analizie decyzji, nie w dokumencie. |
| 1.0.3 | 2026-09-07 | Addytywne: pole manifestu `guidefold-import-manifest-v1` `suggestions` (§5.6) — doradcze dopasowania scope/owner dla plików `kind:skill`, których `guidefold.yaml` samodzielnie nie pokrywa (U1 AC2). Wypełniane przez `guidefold scan` z katalogów i CODEOWNERS, gdy mapa jest niepełna lub nieobecna; przy dwóch węzłach związanych tą samą specyficznością pozycja trafia do `suggestions` z `reasons` zawierającym `ambiguous_node_match` i listą `candidates`, a plik pozostaje w `files` (nie w `excluded`). Nie zmienia `files`/`excluded` ani scope faktycznie użytego przez CLI; pole obecne (może być puste) w każdym manifeście, więc zgodne wstecz. |
| 1.0.4 | 2026-09-07 | Addytywne, z wdrożenia modułów Import i Knowledge (`services/search/internal/{importer,knowledge}`):<br>1. `POST {org_base}/repos` zwraca 201 przy rejestracji i 200, gdy repozytorium już istniało; pole `created:bool!` rozróżnia te dwa przypadki, bo CLI wywołuje tę trasę przed każdym importem i ponowna rejestracja nie jest błędem (§4.2).<br>2. Manifest `guidefold-import-manifest-v1` dostaje jawny wiersz `publish:bool?` (domyślnie `true`) — pole było już używane przez §6 i kolumnę `gfm.imports.publish`, brakowało go wyłącznie w tabeli §5.6.<br>3. `ImportStatus` dostaje `files_truncated:bool?` oraz jawne `publish`, `error`, `reused_import_id`, `finalized_at`; lista `files` jest przycinana do 20 000 pozycji i mówi o tym wprost, zamiast cicho gubić pliki przy imporcie bliskim `max_files` (§5.2).<br>4. Indeks `gfm.skills UNIQUE(org_id,repo_id,path)` staje się częściowy: `WHERE source_status<>'removed'`. Zmiana mapy scope w `guidefold.yaml` zmienia URN skilla przy niezmienionej ścieżce, więc archiwalna tożsamość i nowa muszą móc współistnieć pod tą samą ścieżką; jedna **żywa** pozostaje wymuszona (§7).<br>5. Indeks otwartych pozycji `gfm.owner_queue` jest `NULLS NOT DISTINCT`, żeby powtórny import nie dopisywał drugiej pozycji o przyczynie bez rewizji (§7, inwariant U9).<br>6. `revision_unavailable` (409) obejmuje też management: rewizja istnieje, ale jej surowe bajty wygasły; `Revision.body` jest wtedy `null`. Kod i status bez zmiany znaczenia — dochodzi endpoint, nie nowa semantyka (§3).<br>7. Idempotencja na czterech trasach importu ma odpowiedź „na żywo" (§3): klucz jest zajmowany tak samo, ale powtórzenie wykonuje handler ponownie i zwraca `Idempotent-Replay: false`, bo `missing_blobs` i `ImportStatus` są widokiem bieżącego stanu, a nie zapisem faktu.<br>Nie zmienia: żadnego istniejącego pola, statusu ani domeny wartości; klient 1.0.3 działa bez zmian. |
| 1.0.5 | 2026-09-07 | Addytywne, z wdrożenia modułu Telemetry/Reporting (`services/search/internal/usage`):<br>1. §4.6 dostaje jawne znaczenie `window` (`7d\|30d\|90d`, domyślnie `30d`, liczone od watermarku = `max(received_at)`), regułę przypisania wiersza do repozytorium przy ledgerze w skali organizacji, oraz zdanie, że `coverage` opisuje całe okno i nie zawęża się filtrami.<br>2. §5.5 `UsageSkill` dostaje `scope`, `owner` (decyzja 14 — z bieżącej rewizji skilla), `harness`, `context_unknown` i `use_episodes`; wszystkie były już w przypiętych kolumnach CSV albo w `Usage.totals`, brakowało ich wyłącznie w wierszu DTO.<br>3. §5.5 dostaje tabelę definicji miar (co jest ekspozycją, zweryfikowanym załadowaniem, potwierdzeniem kontekstu, zastosowaniem, epizodem, oceną i korektą) oraz opis kolejki: dwie przyczyny są **policzone** z telemetrii (`negative_feedback`, `zero_loads`), mają stabilny identyfikator `<reason>:<skill_id>:<revision>` i również podlegają decyzji.<br>4. `QueueItem.item_id` przechodzi z `uuid!` na `str!` (rozszerzenie dziedziny, nie zawężenie — dekoder UI już czytał `str`): pozycja workera nadal ma `uuid`, pozycja policzona ma identyfikator wyprowadzony. Dochodzi opcjonalne `source:{worker\|computed}`.<br>5. Opcjonalne pole zdarzenia `skill_load_completed.context_confirmation` (`context_loaded\|download_verified\|unsupported`) i `skill_feedback.corrects_judgment_id`; oba są opcjonalne, więc walidator telemetrii (`telemetry-schema.json`, generowany z referencji) się nie zmienia i klient 1.0.4 działa bez zmian.<br>6. §7: `gfm.adapter_health` opisana jako projekcja pisana przy ingest z **zaakceptowanych** zdarzeń; `gf.events` dostaje `IDX(tenant_id,event_type,occurred_at)` i wyrażeniowy `IDX(tenant_id, gf.event_field(payload,'skill_id'))` wraz z funkcją `gf.event_field(bytea,text)` — `payload` jest `bytea` z powodu NUL, którego `jsonb` nie przyjmuje, więc `payload->>'skill_id'` nie istnieje.<br>Nie zmienia: żadnego istniejącego pola poza rozszerzeniem dziedziny `item_id`, żadnego statusu ani kodu błędu.
| 1.0.6 | 2026-09-07 | Addytywne, luka dokumentacyjna zamknięta przed implementacją UI (kontrakt przed kodem, §1): `GET {repo_base}/imports/{import_id}/plan` i `POST {repo_base}/imports/{import_id}/proposals:generate` (§4.2, obecne od 1.0.0) miały wyjście opisane tylko na poziomie endpointu, bez wierszy DTO w §5.2. Dochodzi `ImportPlan` (`groups`, `limits`, `estimated_usd_max`, `generator.name/configured`), `ImportPlanGroup` (`group_id`, `kind`, `inputs`, `estimated_tokens`) i `ProposalLimits` (podzbiór pól joba `proposal.generate` z §8: `max_groups`, `max_proposals_per_group`, `max_neighbours`, `max_tokens`, `max_calls`, `max_usd`) oraz doprecyzowanie kodowania `kinds` na GET (lista rozdzielona przecinkami w parametrze zapytania, §4.2). Nie zmienia: żadnego istniejącego pola, endpointu, statusu ani kodu błędu — obie trasy i ich wyjścia były już poprawne w kodzie i w `ui/src/api/decoders.ts`; luka była wyłącznie w tym dokumencie. |
| 1.0.7 | 2026-09-07 | Addytywne, z wdrożenia modułu Review/Publication (`services/search/internal/{review,graph}`, `publish.build`, kontrakt 1.2 na `/v1/use`):<br>1. `POST {repo_base}/snapshots/{snapshot_id}/activate` przyjmuje wymagane `reason` (3..500) i zwraca `{snapshot: Snapshot}`; powód trafia do `gfm.audit` (decyzja TL 13 — rollback jest decyzją ownera z powodem jak każda inna).<br>2. §5.4 dostaje wiersz DTO `Snapshot` (widok `gfm.publications` z polem `active`) oraz `Export.proposal_id`/`Export.state`.<br>3. `gfm.skills` dostaje nullowalną kolumnę `published_snapshot_id` (§7): USE 1.2 odpowiada manifestem zasobów wyłącznie dla rewizji, którą **aktywny** snapshot faktycznie serwuje.<br>4. §5.2: `ImportPlan` dostaje `estimated_calls` i `groups_skipped` (ile scope'ów odciął `max_groups` — nazwane, nie ukryte); `generator` dostaje `generator`/`version`/`model` obok `name`/`configured` (składniki klucza cache z §8); `ImportPlanGroup` dostaje `scope`, `owner`, `n_inputs`, `estimated_calls`; `ProposalLimits` dostaje `max_files` i `max_bytes`, a `max_tokens`/`max_calls`/`max_usd` są zawsze obecne, bo plan musi pokazać każdy limit przed wydaniem pieniędzy (U2.7).<br>5. §4.5: 1.2 przyjmuje pole żądania `search_snapshot` (osobny dokument schematu `harness-service-v1.2.schema.json`, nadzbiór 1.1), a odpowiedź niesie `closure.requires[].depth`, `closure.requires[].status ∈ loaded|available|denied|missing` oraz `resources[]` ze ścieżkami względnymi wobec katalogu pakietu.<br>6. Doprecyzowanie bez zmiany pól: `publish.build` odmawia aktywacji z importu w stanie `partial` — publikacja kończy się `failed` z `error: import_partial` i listą plików w `validation`, a poprzedni head dalej serwuje (U2.1). Import `partial` pozostaje sukcesem po stronie katalogu.<br>Nie zmienia: żadnego istniejącego pola ani kodu błędu poza dodaniem wymaganego `reason` na `activate`, opisanym już jako decyzja TL 13. |
| 1.0.8 | 2026-09-07 | Korekta z niezależnego przeglądu (bez zmiany znaczenia istniejącego pola):<br>1. §5.4 miała **dwa** sprzeczne wiersze `Snapshot`; drugi (`snapshot_id:str!`, `published_at`, `validation.errors[]`) opisywał kształt, którego serwis nigdy nie zwracał, i był źródłem rozjazdu dekodera UI. Usunięty. Obowiązuje wiersz `gfm.publications`: `publication_id:uuid!`, `snapshot_id:str?`, `validation` z `{ok, findings[]}`.<br>2. §3 i §4.4 dostają kod `import_not_ready` (409): `POST {repo_base}/publish` odmawia importu w stanie `created`/`uploading`/`failed`/`cancelled`, zamiast przyjmować 200 i wypalać `max_attempts` joba, którego nie da się zbudować. `queued`/`parsing` nadal przechodzą — są w locie.<br>Nie zmienia: żadnego pola żądania ani odpowiedzi; klient 1.0.7, który nie publikował niegotowego importu i nie czytał usuniętego wiersza, działa bez zmian. |
| 1.1.0 | 2026-09-07 | Addytywne, z decyzji właściciela P08 „konsolidacja i piramida" (PRODUCT-PIVOT §5 U2 / §8 U5, PIVOT-BACKLOG P08):<br>1. §4.2: `GET …/plan` przyjmuje `profile` w zapytaniu, `POST …/proposals:generate` w ciele; zamknięty zbiór `{default\|one_shot}`, nieznana wartość to `400 invalid_request`. `one_shot` podnosi **wyłącznie** `max_groups` do liczby znalezionych grup (sufit 1000/rodzaj), aby jedno wywołanie objęło cały import; `max_usd`/`max_calls`/`max_tokens`/`max_neighbours` bez zmian, zawężenie przez wywołującego nadal działa i ma pierwszeństwo. Obie trasy zwracają `profile`.<br>2. §5.2: `ImportPlan` dostaje `profile`; `ImportPlanGroup` doprecyzowuje, że dla `kind:consolidation` `scope` jest scope'em nadrzędnym, a `owner` — ownerem scope'u docelowego.<br>3. §8: `proposal.generate` grupuje konsolidację po scope **nadrzędnym** (scope i jego bezpośrednie dzieci, każdy skill w dokładnie jednej grupie) zamiast po pojedynczym scope, bo wspólna procedura leży raz w `atlas.geo` i raz w `atlas.graph`. Wewnątrz grupy porównywane są wszystkie pary, ale grupa jest ograniczona przez `max_neighbours` — nadal nie all-pairs po katalogu. Każde wejście grupy niesie własny `scope`/`owner`. Checkpoint jest na grupę, więc one-shot wznawia się bez duplikatów. Zamknięta lista powodów abstynencji.<br>4. §5.3: `knowledge_layer` dostaje jawną tablicę reguł recepty `det-1` (pierwsza pasująca wygrywa) i regułę pochodzenia: tylko `inferred` z generatora albo `human` z zatwierdzenia, nigdy kopia `source_layer`.<br>5. §5.4: doprecyzowanie bez zmiany pola — `approve` ustawia `gfm.skills.current_revision_id` na zapisaną rewizję (§7 już przypisywał ten zapis API przy decyzji), więc zatwierdzony wspólny element może być wejściem kolejnego przebiegu; `publication_status` nadal zostaje `draft`. `ProposalDetail.relations[]` dostaje `from` — dokładnie jedno z `to`/`from` jest niepuste, bo konsolidacja proponuje krawędzie w obu kierunkach (`derived_from` w dół, `refines` z każdego źródła w górę). `DecisionResult` opisuje zapis `metadata.knowledge_layer` do `gfm.skills` i przejście pola na `origin:human` przy nadpisaniu przez właściciela; warstwa jest jedynym polem metadanych, które `edit` może zmienić.<br>6. §4.5: 1.2 dostaje `family` na każdej karcie SEARCH i w odpowiedzi USE (`parent`/`children`/`layer`, głębokość 1, do 8 dzieci, krawędź poza snapshot pomijana). Doklejane po rankingu i po zmierzeniu `card_context`: kolejność `ranked`/`cards` i rozliczenie budżetu są identyczne z nim i bez niego, a 1.1 nie dostaje go w ogóle. Schemat `harness-service-v1.2.schema.json` rozszerzony; `schema_version` odpowiedzi w tym dokumencie dopuszcza `1.1` i `1.2`.<br>7. §2: zakresy tokenu **CI** rozszerzone z `validate` do podzbioru `validate import generate` (dla `guidefold extract` w CI). Zakresy tokenu **instalacji** bez zmian.<br>8. §5.6: `files[]` dostaje opcjonalne `source:{kind:"personal", harness}` z prefiksem ścieżki `_personal/<harness>/…`, wyłącznie dla jawnego `guidefold extract --personal`; nieobecne dla plików repozytorium i nigdy w CI.<br>Nie zmienia: żadnego istniejącego pola, kodu błędu ani `schema_version` ładunku. Klient 1.0.8, który nie wysyła `profile` i nie deklaruje 1.2, dostaje bajt w bajt to samo. |
| 1.1.1 | 2026-09-07 | Addytywne, z naprawy trzech defektów przebiegu akceptacyjnego 2026-09-07 (ACT-01, U9, U6-3):<br>1. **Publikacja nie kasuje pytania driftu** (§6): `publish.build` ustawia `published` wyłącznie dla skilli w stanie `draft|approved_for_export|awaiting_git|published`. Skill w `needs_review` albo `archived` zachowuje status, choć nowy snapshot dalej serwuje jego bieżącą rewizję — Git jest kanoniczny, a flaga jest zadaniem ownera, nie bramką serwowania. Wcześniej `markPublished` nadpisywał `needs_review` przy tym samym imporcie, który drift oznaczył (`finalize` kolejkuje `import.parse` i `publish.build` razem), więc ACT-01 nigdy nie widział `needs_review`. Połowa `archived` nie była zepsuta (warunek `source_status='active'` już ją chronił).<br>2. **Decyzja ownera zamyka pytanie** (§4.6, §5.5, §6): decyzja `reviewed|fixed_in_git|no_change` na pozycji `source_changed` przenosi skill `needs_review → published` w transakcji decyzji; na pozycji `source_removed` zostawia `archived`.<br>3. **Jedna przestrzeń nazw rewizji w raporcie użycia** (§5.3, §5.5, §7): `gfm.skill_revisions` dostaje nullowalną kolumnę `card_revision` (rewizja karty `gf.skills.skill_revision`), zapisywaną przez `publish.build` dla rewizji, które weszły do snapshotu. Kolumna jest wystawiona jako `card_revision` w `SkillSummary`, `RevisionRef` i `Revision`. Agregat `/usage` sprowadza rewizję zdarzenia — kartową ze ścieżki dostawy albo katalogową z UI — do rewizji katalogu, więc ocena z UI i `skill_feedback` adaptera dają **jeden** wiersz; wiersz pokazuje `revision` (katalogową), `card_revision` i `content_sha256`. Filtr `revision=` przyjmuje rewizję katalogu albo rewizję karty (dwa identyfikatory występujące w zdarzeniach) i jest echem dosłownym; `content_sha256` jest pokazywany, ale nie jest kluczem. `Revision.feedback` czyta oceny zapisane pod obiema rewizjami. Zdarzenie `skill_feedback` z UI niesie dodatkowo `card_revision` i `content_sha256`; jego pole `revision` zostaje bez zmiany (rewizja katalogu), żeby kontrolna implementacja `tools/telemetry/report.py` — która nie ma dostępu do katalogu — dalej liczyła te same wiersze (§5.5, U6-1).<br>4. **Echo filtrów `/usage`** (§5.5): klucze `filters` są dosłownie parametrami zapytania (`scope`, `skill_id`, `revision`, `harness`) i dochodzi `window` z zastosowanym oknem. Parametr niepodany nadal nie ma klucza.<br>5. Kolumny CSV `usage/export`: `card_revision` i `content_sha256` dopisane **na końcu** przypiętej listy; żadna wcześniejsza kolumna nie zmieniła pozycji ani znaczenia.<br>Nie zmienia: żadnego istniejącego pola, statusu ani kodu błędu; klient 1.1.0 działa bez zmian. |
| 1.1.2 | 2026-09-07 | Korekta znaleziona przy pierwszym prawdziwym logowaniu WorkOS (rzeczywiste konto, nie fixture): `GET /api/v1/orgs` od zawsze zwracał `{items: [Org]}` (`identity/orgs.go` `handleListOrgs`), a ten dokument opisywał `{orgs: [Org]}` — nazwa pola z odpowiedzi `/me` (gdzie `orgs` jest właściwym kluczem, bez zmian) omyłkowo skopiowana do osobnego, niezależnego endpointu. `ui/src/api/decoders.ts`'s `orgList` szukał pola `orgs` i zawsze rzucał błąd dekodowania dla tego endpointu, także dla pustej listy — widoczne jako „Could not read this view" na ekranie Organization/Import w trybie API dla każdego konta bez organizacji. Naprawiono dekoder na `items`; zero paginacji dla tego endpointu (lista jednego użytkownika). Nie zmienia: kodu serwera, innych pól ani `/me`. |
| 1.1.3 | 2026-09-07 | Korekta znaleziona przy imporcie prawdziwego zewnętrznego monorepo (183 realne `SKILL.md`, `wshobson/agents`, poza fixture Meridian): `scan`/`import` (P03/P04) akceptowały `SKILL.md` w dowolnej lokalizacji dopasowanej do glob'a węzła, podczas gdy jedyna ścieżka odkrywania kart — `all_skills()`, używana przez `find`/`load`/`validate`/`materialize`/`doctor`/`report` i workerowy `build_tree.py` — rozpoznaje wyłącznie `<cokolwiek>/.agents/skills/<name>/SKILL.md`. Skill spoza tego kształtu importował się bez ostrzeżenia i nigdy nie mógł się opublikować (`publish.build` kończył `invalid_snapshot_dimensions`, `n_skills:0`, bez wskazania przyczyny) — myląca awaria trzy kroki później zamiast jasnego komunikatu przy skanie. §5.2: `excluded[].reason` dostaje `non_canonical_skill_path` (zamknięty zbiór, addytywnie); `scan`/`import` wyklucza taki plik z `kind:"skill"` i nigdy nie rejestruje go jako skilla zamiast po cichu przyjmować dane, które nigdy się nie opublikują. Nie zmienia: żadnego istniejącego pola, kodu błędu ani zachowania dla drzewa, które już używa `.agents/skills/` (fixture Meridian, wszystkie istniejące testy) — bajt w bajt to samo. To zamknięcie rozjazdu z istniejącą konwencją (CLAUDE.md §Naming, `all_skills()` niezmienione), nie nowa decyzja architektoniczna; brak nowego ADR. |
| 1.1.4 | 2026-09-08 | Addytywne, z dowodu z `docs/reports/market/2026-09-07-progressive-disclosure-evidence.md` (agent widzący samą kartę w 97% przypadków trafnie rozpoznaje, kiedy potrzebuje body; nieznana pozostaje **rzeczywista** proporcja zapytań, w których karta wystarcza):<br>1. §5.5: `UsageSkill` i `Usage.totals` dostają `exposures_expanded` (ekspozycje, po których to samo `search_id` doprowadziło do zweryfikowanego załadowania body tego skilla) i `loads_unlinked` (załadowania bez `search_id`, czyli *unknown*, nie „bez karty”). Powiązanie jest po `skill_id` i `search_id`, nie po rewizji.<br>2. §5.5: `skill_load_completed` niesie `search_id` jako pole opcjonalne i addytywne, tą samą drogą co `context_confirmation` w 1.0.5 — poza `required_fields` walidatora, `telemetry-schema.json` bez zmian. Adapter CLI zapamiętuje lokalnie ostatnie ekspozycje (`.guidefold/telemetry/recent-exposures.json`, ograniczone do 64 wpisów i 60 minut, bez treści zapytania) i dokleja `search_id` do `skill_load_requested` (pole istniało, było zawsze `null`) oraz do `skill_load_completed`, gdy `load` następuje po ekspozycji tego skilla; sesja znana po obu stronach i różna blokuje powiązanie.<br>3. Kolumny CSV `usage/export`: `exposures_expanded` i `loads_unlinked` dopisane **na końcu** przypiętej listy.<br>4. `tools/telemetry/report.py` liczy oba pola tak samo (parzystość z agregatem Go, `usage_ledger_test.go`).<br>Nie zmienia: żadnego istniejącego pola, statusu ani kodu błędu; adapter, który nie wysyła `search_id`, daje `exposures_expanded: 0` i `loads_unlinked = loads_verified`, co UI ma czytać jako *nie wiadomo*, nie jako „karty zawsze wystarczały”. Klient 1.1.3 działa bez zmian. |
| 1.2.0 | 2026-09-08 | Addytywne, z decyzji ownera 2026-09-08 (ascent ma działać u klienta, który zainstalował aplikację GitHub, bez edycji jego CI) — **kontrakt wyprzedza kod** (§1 pkt 2) w chwili napisania, ADR-0036: GitHub webhook jest wpięty jako weryfikowany HMAC (`X-Hub-Signature-256`) rejestr instalacji, obsługujący utworzenie/aktualizację/usunięcie instalacji i listę repozytoriów.<br>1. §4.7: `POST /api/v1/github/webhook` (publiczny, podpis HMAC, idempotentny po `X-GitHub-Delivery`), `GET {org_base}/github/installations`, `DELETE {org_base}/github/installations/{installation_id}`.<br>2. §3: `invalid_webhook_signature` (401), `github_app_not_configured` (503), `installation_not_found` (404).<br>3. §5: `GitHubInstallation`.<br>4. §7: `gfm.github_installations`.<br>5. §8: job `ascend.run` — worker klonuje `head_sha` tokenem instalacji, uruchamia zaufany plik CLI `ascend`, otwiera PR do `base_ref`; sekrety przez `*_FILE`; wymaga `git` w obrazie workera i wyjścia sieciowego do GitHub i modelu.<br>Nie zmienia: żadnego istniejącego pola, statusu, kodu błędu ani zachowania; do czasu implementacji `check_api_contract.py` raportuje te wiersze jako INFO (kontrakt bez kodu), nigdy jako drift. Klient 1.1.4 działa bez zmian. |
| 1.2.1 | 2026-09-09 | Addytywny opt-in źródłowo dowodowanej dostawy dla P09/U5.5, wynikający z kierunku ownera „proof-gated delivery, provenance, ASK”. Żądanie USE 1.2 przyjmuje `delivery_policy:"proof_gated"`; odpowiedź niesie `delivery` z akcją `LOAD` albo `ASK`, powodami, brakami i zredukowanym provenance. `LOAD` wymaga zgodności snapshotu/rewizji/hash body/scope'u, kompletnej closure i ważnych claimów z liniami źródłowymi; serwis wiąże każdą ścieżkę claimu z manifestem aktywnej rewizji, pobiera jej content-addressed bajty i sprawdza SHA oraz zakres linii. Niespełnienie warunku zwraca `ASK` bez body. Brak pola zachowuje dotychczasowy tryb. Dodano schemat, publisher binding placeholderów oraz deterministyczny gate w `services/search/proof_gate.go` wraz z testami brzegowymi. Nie zmienia zachowania klienta 1.1 ani domyślnego 1.2; nie jest dowodem wykonania ani wyników użytkownika. |
| 1.2.2 | 2026-09-09 | Korekta luki między zaakceptowaną decyzją ADR-0037 a hosted Go service: SEARCH stosuje `nearest-wins` jako twardy filtr po polityce widoczności/deprecation/negative-trigger i przed BM25F, dense oraz fusion. Dla tej samej nazwy wygrywa najgłębszy widoczny scope; równorzędne scope'y pozostają niezależne. `policy_drops` obejmuje shadowowane kopie, a `policy_revision` nadal identyfikuje konfigurację polityki. USE zachowuje semantykę jawnego, dokładnego `skill_id` i rewizji. Dodano test regresyjny reguły oraz filtrowanie przygotowanych kandydatów dense. Nie zmienia schematu JSON ani zachowania klienta 1.1 poza zgodnym z decyzją usunięciem shadowowanych kart z wyników SEARCH. Wyniki 23/24 pozostają wynikiem benchmarku prototypu, nie gwarancją jakości live. |
| 1.2.3 | 2026-09-09 | Dodano append-only projekcję `gf.training_examples` dla redagowanych sygnałów PBSD i przyszłych ewaluacji/model training: immutable dataset split, wersja datasetu, provenance digest, proof/decision/outcome metadata, model/router/policy revisions, token/tool/time counters oraz ograniczony `content_mode`. Domyślnie bez surowych promptów, body, kodu, sekretów i danych osobowych; TEST nie jest źródłem treningu. Migracja i uprawnienie append-only są po stronie Telemetry/Reporting. Nie zmienia istniejącego ledgeru ani odpowiedzi SEARCH/USE. |
| 1.2.4 | 2026-09-09 | Addytywne rozszerzenie proof-gated delivery dla hierarchicznych kart: `source_proof.claims[]` może nieść `claim_refs[]` wskazujące niższą kartę przez `skill_id`, `revision`, `claim_id`, `claim_digest` i `commitment`. Go sprawdza te krawędzie rekurencyjnie w tym samym snapshotcie, z relacją scope/refines i ochroną przed cyklem, a potem weryfikuje źródłowe bajty każdego poziomu. Nie zmienia legacy/1.1 ani proofów bez `claim_refs`; niespójna ścieżka kończy się `proof_recursive_invalid` i `ASK`. |
| 1.2.5 | 2026-09-10 | Addytywne: `Usage.totals.metrics` udostępnia obserwowane sygnały wykonania (`ExecutionMetrics`) dla organizacyjnych scorecardów UI: sukcesy i nieznane wyniki zadań, błędy harnessu, liczniki SEARCH/USE/ASK, tokeny, wywołania narzędzi i próbki opóźnienia. Brak obserwacji pozostaje jawny jako `Unknown`; nie zmienia istniejących agregatów dostawy ani kontraktu zdarzeń. |
| 1.2.6 | 2026-09-11 | Addytywne: `ExecutionMetrics.ask_reasons` grupuje obserwowane decyzje `ASK` po kodzie powodu (brak powodu → `unknown`). Organizacyjny scorecard pokazuje ten rozkład obok licznika `ASK`, żeby właściciel widział, czy blokadą jest konflikt, brak dowodu, dryf rewizji czy niepełne zamknięcie. Nie zmienia zdarzeń ani istniejących agregatów. |
| 1.3.0 | 2026-09-12 | Addytywne na bazie kontraktu 1.2.0 (obejmuje, bez usuwania, całą linię 1.2.x powyżej), z Overview (`/home`): widok potrzebuje totali z poprzedniego okna, aktorów decyzji i audytu dostępnego członkom, nie tylko ownerowi.<br>1. §5.5 `Usage` dostaje `previous:obj?` (`window:{from,to}`, `totals:UsageTotals`) — okno tej samej długości co żądane, kończące się w `window.from` (zakotwiczone na tym samym watermarku), liczone tymi samymi filtrami co `totals`; `null` wyłącznie, gdy raport nie ma `totals`. Zero jest prawdziwym zerem w tym oknie, nie Unknown; UI ocenia sens delty tylko wtedy, gdy oba okna mają `exposures > 0`.<br>2. §5.4 `ProposalSummary` dostaje `decision:obj?` (`decision:{approve\|edit\|reject}!`, `actor:str?`, `at:ts?`) — najnowszy wiersz `gfm.decisions` dla propozycji; `null`, dopóki nierozstrzygnięta. `actor` jest tym samym identyfikatorem principala, który `ProposalDetail.decision.actor` zwraca dla tej samej decyzji.<br>3. §5.5 `QueueItem.decision` dostaje `actor:str?` — identyfikator użytkownika zapisany na decyzji ownera w `gfm.owner_queue`; `null` dla decyzji zapisanej przez workera.<br>4. §5.3 `FeedbackEntry` dostaje `actor:str?` — identyfikator principala, który ocenił przez UI (`source: "ui"`); `null` dla oceny pochodzącej z adaptera.<br>5. §4.1 `GET {org_base}/audit`: rola z `owner` na `member` — owner czyta każdy wiersz organizacji jak dotychczas, member wyłącznie wiersze, których `actor` odpowiada jego własnemu principalowi; ten sam kształt strony i kursor.<br>Nie zmienia: żadnego istniejącego pola, statusu ani kodu błędu wprowadzonego w żadnej rewizji 1.2.x; klient 1.2.x działa bez zmian. |
| 1.4.0 | 2026-09-12 | Addytywne, z decyzji właściciela o Live Agencie i kluczu modelu należącym do organizacji ([ADR-0043](adr/ADR-0043-org-provider-credentials-encrypted-at-rest.md), [ADR-0044](adr/ADR-0044-live-agent-on-demand-across-connected-repositories.md)):<br>1. §4.8: trzy trasy `{org_base}/credentials[/{provider}]` — lista metadanych dla membera, zapis i usunięcie dla ownera z CSRF. Klucz nigdy nie wraca z API; wychodzi z niego wyłącznie `last4`. `PUT` weryfikuje klucz u dostawcy przed zapisem.<br>2. §4.9: pięć tras `{org_base}/live/*` — start przebiegu (owner, idempotentny), lista, szczegóły z celami, dziennik zdarzeń i anulowanie. `…/events` nie jest transportem strumieniowym: zwykła koperta z §3 i kursor pozycyjny `after`, a `done` gasi odpytywanie dopiero po zwróceniu ostatniego zdarzenia zakończonego przebiegu.<br>3. §3: dziewięć nowych kodów (`invalid_provider`, `credential_invalid`, `invalid_prompt`, `invalid_model`, `credential_not_found`, `live_run_not_found`, `live_run_already_active`, `live_run_not_cancellable`, `model_credential_missing`, `secret_encryption_unavailable`) w modułach `secrets` i `live`.<br>4. §5.5a: `OrgCredential`, `LiveRun`, `LiveRunTarget`, `LiveRunEvent`. `LiveRun.state` ma `partial` jako stan **końcowy**, a `cost.usd_estimated` odróżnia koszt zmierzony z zużycia zwróconego przez dostawcę od oszacowanego.<br>5. §7: `gfm.org_credentials` (szyfrogram, nigdy jawny klucz; PK po `(org_id,provider)`), `gfm.live_runs` (częściowy UNIQUE po `org_id` dla stanów `queued`/`running` — jeden przebieg naraz), `gfm.live_run_targets`, `gfm.live_run_events`.<br>6. §8: rodzaje jobów `live.plan` i `live.repo`. Czytają repozytorium przez API treści GitHuba tokenem instalacji, nie klonują i nie uruchamiają niczego z repozytorium, nie zakładają gałęzi ani PR-a.<br>Nie zmienia: żadnego istniejącego pola, statusu ani kodu błędu; klient 1.3.0 działa bez zmian. |
