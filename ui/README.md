# Guidefold UI
Status: publiczny landing z waitlistą oraz panel przez hostowane API, 2026-09-08. Siedem widoków U4 wydzielonych z zatwierdzonego hi-fi Industrial Surveyor; wszystkie siedem czyta hostowane API przez `DataSource`. Publiczne `/` nie uruchamia sesji panelu. Kierunek, konsultacje i dowody: [landing DESIGN](../docs/reports/landing/DESIGN.md), [QA](../docs/reports/landing/build-notes.md).
Wejścia: [AGENTS](../AGENTS.md), [reguły dokumentacji](../docs/DOCUMENTATION-RULES.md), [etap 7](../docs/ui/pipeline/07-frontend.md), [etap 8](../docs/ui/pipeline/08-components.md). Zastępuje hi-fi jako miejsce dalszej pracy; zamrożony wzorzec pozostaje w prototypes/pipeline-hifi.

## Uruchomienie
Node 22.14.0 i pnpm 10.30.3:
```sh
cd ui
pnpm install --frozen-lockfile
pnpm dev
```
Otwórz http://127.0.0.1:4331. Galeria komponentów: /__components, poza nawigacją produktu.

## Źródło danych: hostowane API
Panel ma jedno źródło danych: hostowane API zarządzania przez `ApiDataSource` (`src/data/apiSource.ts`). `main.tsx` składa je wyłącznie dla tras panelu; nie ma trybu lokalnego, parametru `?mode=` ani danych przykładowych w bundlu poza galerią komponentów. Landing korzysta z osobnego publicznego adaptera `src/data/waitlist.ts` i kontraktu [API §4.0](../docs/API-CONTRACT.md#40-publiczna-lista-oczekujących-adr-0039). Wymaga działającego backendu, migracji i workera; sukces nie jest symulowany w przeglądarce. Konfiguracja Resend: [moduł waitlist](../services/search/internal/waitlist/README.md).
```sh
# to samo pochodzenie przez proxy dewelperskie (domyślne)
pnpm dev            # /api i /v1 → http://127.0.0.1:8765
# inne pochodzenie
VITE_GUIDEFOLD_API=https://api.example.test pnpm dev
```
Nagłówek pokazuje organizację z `/me` i repozytorium z adresu (`?org=`, `?repo=`). Organizacja spoza `/me.orgs` daje stan restricted bez żadnej informacji o jej treści. Bez działającego API każdy widok pozostaje w stanie loading/error/restricted; to oczekiwane, nie regresja.

### Brama sesji i trasa `/login`

Status: 2026-09-12, polecenie właściciela. Każda trasa panelu jest prywatna. Gdy `/me` zostaje
odrzucone — brak sesji, `access.denial === 'unauthenticated'` — powłoka `ApiApp` nie pokazuje
stanu restricted w środku panelu, tylko przekierowuje żądanie na `/login?return=<oryginalny adres>`
(`src/app.tsx`). **Odmowa 403 na zasobie przy żywej sesji (`denial === 'forbidden'`) nigdy nie
przekierowuje**: sesja jest ważna, więc logowanie odesłałoby operatora pod ten sam zakazany adres
i odmówiłoby ponownie. Taki przypadek maskuje wszystkie widoki panelem „Not available to your
account” z powrotem do własnej organizacji i drugorzędnym „Sign in again”; tożsamość zostaje,
dane i szkice tej organizacji są kasowane (`src/api/access.ts`, `DenialKind`).
`/login` renderuje się poza powłoką: pełna szerokość, graphite, znak Guidefold, formularz w
mierze `--form-width`, cele 44 px (`src/routes/LoginRoute.tsx`). Publiczne pozostają `/`
z `?confirm=`/`?unsubscribe=` (osobne wejście w `main.tsx`, nie dociera do `App`), statyczne
`/docs/` oraz galeria `/__components`.

Kontrakt bez zmian: strona czyta `GET /auth/providers` i startuje `GET /auth/login/{provider}?return_to=`
([API §4.1](../docs/API-CONTRACT.md)). Logowanie kończy się u dostawcy tożsamości, a API robi 302 na
`return_to` — nie ma w aplikacji przejścia „zalogowano”. Cel `return` jest walidowany
(`src/routes/loginTarget.ts`): przyjmowana jest wyłącznie ścieżka tego samego pochodzenia,
inaczej `/import`; adres nie nadaje uprawnień.

Kreator importu nie ma już kroku `login`: zostały trzy kroki (Organization, Repository,
Import status). Zakładka `/import?step=login` bez sesji pokazuje stronę logowania, a z sesją —
pierwszy realny krok tego konta.

### Pokrycie operacji kontraktu
| Widok | Operacje kontraktu | Uwagi |
|---|---|---|
| Overview (`/home`, od 2026-09-12 domyślny cel po zalogowaniu i nieznanych adresów) | `usage`, `skills` (limit 100, maksimum kontraktu), `skills/facets` (scope), `map/layers`, `proposals`, `imports`, `installations`, `audit` (owner) | Osiem odczytów równolegle; każdy blok, którego odczyt się nie powiódł, mówi to sam, reszta strony jest kompletna. Domena `src/domain/overview.ts` (czyste agregacje, testy null/zero/partial). Brak delty i wyniku zdrowia: kontrakt nie zwraca poprzedniego okna. |
| Login (`/login`, poza siedmioma widokami) | `auth/providers`, `auth/login/{provider}` | Brama sesji: brak sesji (`denial === 'unauthenticated'`) na dowolnej trasie panelu przekierowuje tu z `?return=`; 403 przy żywej sesji (`'forbidden'`) maskuje widok w powłoce i nie przekierowuje. Strona pokazuje formularz dopiero wtedy, gdy brak sesji jest znany — przy `checking` i przy trzymanej tożsamości jest neutralny stan ładowania. Pusta lista dostawców to jawny stan „No identity provider is configured”, nie błąd. |
| Import | `orgs`, `repos`, `imports`, `imports/{id}`, `imports/{id}/plan`, `imports/{id}/proposals:generate` | Polling statusu co 2 s do stanu terminalnego. Generowanie propozycji: plan (grupy, wejścia, szacunek kosztu, limity, generator) czytany przed startem, tylko dla ownera; `proposals:generate` otwiera jedno zadanie `proposal.generate` na rodzaj z własnym `Idempotency-Key`; osobny polling zadań generacji po `job_ids` (niezależny od pollingu statusu importu, który zatrzymuje się po pierwszym stanie terminalnym importu); `skipped`/`llm_not_configured` pokazywany jako uczciwy stan, nie błąd. |
| Library | `skills`, `skills/facets`, `skills/facets/lookup` | Filtry `q, scope, owner, layer, status` i `cursor` w URL; bez pobierania body. Aktywna wartość ma własny lookup; `filters[*].available:false` renderuje jawny brak, nigdy cichego „All”. |
| Map | `map/repository`, `map/scopes`, `map/layers`, `map/relations`, `modules/{scope}` | Leniwe rozwijanie gałęzi (≤100 obiektów na żądanie, twardy limit renderu 200), tekstowa lista relacji z etykietą typu, jawne `truncated`, nazwany unmapped scope. |
| Skill | `skills/{id}`, `revisions/{rev}`, `revisions/{rev}/raw`, `revisions/{rev}/feedback` | Brak rewizji to `revision_not_found`, nigdy podmiana na nowszą. Link źródła buduje się z `source.url`; bez `git_host_url` pokazujemy ścieżkę i „Source host not configured”. |
| Proposals | `proposals`, `proposals/{id}`, `decision`, `export`, `publication`, `snapshots`, `snapshots/{id}/activate`, `publish` | `expected_revision` + stabilny `Idempotency-Key` na szkic; 409 `stale_revision` zachowuje tekst i wymaga ponownego odczytu. Eksport pokazuje `files[]`, patch i komendę `guidefold proposals apply <export_id> --write`; publikacja pollowana co 2 s do stanu terminalnego. |
| Usage & quality | `usage`, `usage/export`, `usage/queue/{id}/decision` | Kolejka „Needs review” pierwsza; `helped_ratio: null` to Unknown, `small_sample` pokazuje liczby zamiast procentu, brak zdarzeń to „No observations”. |
| Organization | `members`, `invitations`, `installations`, `auth/device/*`, `audit`, `me/identities/link/start` | Sekrety pokazywane raz, nigdy nie zapisywane. Audit to trzecia zakładka, tylko dla ownera (`GET .../audit?cursor`), paginacja kursorem, pusty stan „No audit entries”. Sugestie łączenia tożsamości (`/me`'s `link_suggestions`) pokazywane w zakładce Members dla każdego użytkownika — nigdy automatycznie łączone; akcja startuje flow i przekierowuje na `login_url` zwrócone przez API. Zakładka Integrations otwiera się panelem „Set up an adapter” (pięć komend CLI, treść z [HOWTO-adapter](../docs/HOWTO-adapter.md)) nad listą Installations; członkowie widzą te same kroki, tylko owner ma link do Create an installation. |

Sześć stanów per trasa działa jak w [etapie 7](../docs/ui/pipeline/07-frontend.md): degraded to ostatni potwierdzony odczyt tylko do odczytu (odświeżenie nie powiodło się albo `useAccess()` zwraca `offline`), a restricted (odmowa lub brak potwierdzenia dostępu >45 s) ma pierwszeństwo i jest egzekwowany w powłoce `ApiApp`.

## Sprawdzenia
```sh
pnpm typecheck
pnpm build
pnpm test
pnpm test:contracts
pnpm exec playwright install chromium
pnpm test:e2e
# Wymaga działającego pnpm dev:
pnpm test:visual
```
`pnpm test:e2e` (`e2e/*.spec.ts`) uruchamia siedem widoków na stubie API `page.route('**/api/v1/**')` z `e2e/stub.ts`: małe dane przykładowe w kształtach z [API-CONTRACT](../docs/API-CONTRACT.md) plus scenariusze empty/loading/partial/error/degraded/restricted, logowanie → organizacja → repozytorium → import → biblioteka → skill → decyzja → eksport → usage wyłącznie klawiaturą, nieznane filtry URL, axe w 1280/820/390. Stub dowodzi okablowania UI, nie zachowania serwera Go; zachowanie na realnej usłudze sprawdza zestaw live poniżej.
`pnpm test:visual` porównuje 16 komponentów galerii `/__components` w trzech szerokościach z zaakceptowanym baseline `qa/baseline/` (45 obrazów, manifest z SHA-256). Baseline pochodzi z tej galerii (od 2026-09-08, po zamianie danych galerii na wartości przykładowe z `src/sample.ts`; zamrożony hi-fi w `prototypes/pipeline-hifi/qa/baseline` pozostaje zapisem sprzed ekstrakcji i nie jest już celem porównania). `pnpm test:visual:update` regeneruje baseline wyłącznie po zaakceptowanej przez właściciela zmianie wyglądu, nigdy po to, żeby ukryć różnicę. Dawny `pnpm test:flow` (przebieg właściciela na fixture) został usunięty; tę ścieżkę pokrywają `e2e/owner-keyboard.spec.ts` na stubie i `e2e/live/keyboard.spec.ts` na realnym API.

## Zestaw live: siedem widoków na realnym API

Status: opt-in, 2026-09-07. Cel: dowód, że aplikacja działa przeciw uruchomionej usłudze Go z
Postgresem, a nie tylko przeciw stubowi `page.route` z `e2e/stub.ts`. Wejścia: działający
stos z `tools/dev/stack.py`, zasiew z `stack.py seed`, zmienne `GUIDEFOLD_E2E_*`.

Specyfikacje leżą w `e2e/live/` i mają własną konfigurację `playwright.live.config.ts` (projekt
`live`, jeden worker, bo dzielą wiersze jednej organizacji). Zwykłe `pnpm test:e2e` ich nie zbiera
(`testIgnore: '**/live/**'`), a zestaw live nie zbiera specyfikacji na stubie.

```sh
# z katalogu głównego repozytorium
export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH
python3 tools/dev/stack.py up --generator deterministic      # bez --ui: pnpm dev startuje Playwright
python3 tools/dev/stack.py seed > seed.json                  # dev login, org, repo, token, import
# publikacja importu (POST {repo_base}/publish) jest osobnym krokiem; bez niej SEARCH nie odpowiada

cd ui
export GUIDEFOLD_E2E_ORG=$(jq -r .org_slug ../seed.json) GUIDEFOLD_E2E_REPO=$(jq -r .repo_id ../seed.json)
export GUIDEFOLD_E2E_IMPORT_ID=$(jq -r .import_id ../seed.json) GUIDEFOLD_E2E_EMAIL=$(jq -r .email ../seed.json)
export GUIDEFOLD_E2E_TREE=$(jq -r .tree ../seed.json) GUIDEFOLD_E2E_CLI_HOME=$(jq -r .cli_home ../seed.json)
export GUIDEFOLD_E2E_TOKEN_FILE=$(jq -r .token_file ../seed.json)
pnpm test:e2e:live
```

Pozostałe zmienne (`GUIDEFOLD_E2E_SUBJECT`, `_API`, `_PROPOSAL_ID`, `_SKILL_ID`, `_COMMIT`,
`_GIT_HOST_URL`) mają domyślne wartości zasiewu; czego nie podano, spec odkrywa przez `/api/v1/**`
w sesji strony. `_TREE`, `_CLI_HOME` i `_TOKEN_FILE` są potrzebne tylko specyfikacji
`proposals.spec.ts`, która przesuwa źródło propozycji commitem i `guidefold sync`, żeby wymusić
prawdziwe `409 stale_revision`; bez nich ten jeden test jawnie się pomija.

Co zestaw sprawdza: logowanie przez dostawcę deweloperskiego i nagłówek z `/me`, status zasianego
importu, filtry i niedostępną fasetę w Bibliotece, dokładne pobranie rewizji (SHA-256 pobranych
bajtów równa deklarowanemu) i link do źródła, decyzję z odmową 409 i eksport, decyzję właściciela
w kolejce Usage, trzy zakładki Organizacji, ścieżkę klawiaturową, axe na siedmiu widokach oraz
zasłonięcie danych w otwartej sesji usuniętego członka (mierzone zegarem ściennym, wynik w
załączniku `revocation-latency` raportu).

Czego nie dowodzi: zachowania pilota ani jakości routingu. To dowód okablowania UI z realną usługą
na jednej maszynie i pętli zwrotnej; wymaga działającego API i zostawia po sobie wiersze
w bazie zasiewu (decyzje, członków, importy), więc nie jest testem jednostkowym.


## Dalsza implementacja
Komponenty edytuj w src/components, a wartości wyłącznie w src/tokens/tokens.css; bez dodatkowych literałów kolorów i wymiarów.
Każdy z 16 komponentów ma CSS Module, testy kontraktu i stories CSF. Od 2026-09-12 komponenty publiczne i trasy są złożone z prymitywów shadcn/ui w `src/components/ui` (base-nova, Base UI; instalacja `pnpm exec shadcn add https://ui.shadcn.com/r/styles/base-nova/<item>.json`), z klasami Tailwind mapowanymi w `src/registry.css` na tokeny; `components/ui` i `components/spectrumui` są kodem registry, nie publicznym API. Galeria i stories podają stałe props z `src/sample.ts` (wycinki plików examples/monorepo trzymane inline; żaden komponent ani funkcja domenowa ich nie importuje, co sprawdza `pnpm test:contracts`).
Trasy odpowiadają za formularze, decyzje i nawigację. Dane wchodzą wyłącznie przez port `DataSource` (`src/data/source.ts`); jedyną implementacją produkcyjną jest `ApiDataSource` z `src/api/`, a testy podstawiają `fakeSource` z `src/test/fakes.ts`.
`src/api/` zawiera jeden klient fetch (generacja dostępu, numer żądania per zasób, retry GET ≤2 z Retry-After, `Idempotency-Key` i potwierdzenie mutacji po timeoucie), dekodery DTO, cache w RAM z namespace user/org/repo/policy oraz potwierdzanie dostępu (`/me` co najwyżej co 25 s, maskowanie danych starszych niż 45 s, 401/403 czyści cache i szkice). Prywatne dane nie trafiają do localStorage, sessionStorage ani cache HTTP.
`src/routes/apiState.tsx` trzyma wspólny cykl życia tras (`useAsync`, `ApiFailure`, notatki degraded/partial, klucz idempotencji szkicu, pobranie dokładnych bajtów). Nie jest to komponent biblioteki.
Kontrakt DTO i dziedziny zamknięte są w `src/api/decoders.ts` i muszą zgadzać się z [API-CONTRACT](../docs/API-CONTRACT.md) §5–§6; nieznana wartość dziedziny to błąd dekodowania na granicy trasy, nie ciche podstawienie.
`e2e/api-mode.spec.ts` dokłada na tym samym stubie plan → generowanie propozycji → uczciwy stan skipped, zakładkę Audit z paginacją kursorem i sugestię łączenia tożsamości z rzeczywistym przekierowaniem przeglądarki na `login_url`.
`export` zwraca pliki i patch, a `Published` wymaga potwierdzenia z `publication`; nic w UI nie symuluje synchronizacji Git ani dostarczenia do adaptera.

Powłoka konsoli (`app.tsx` `Shell`) i Overview (`routes/HomeRoute.tsx`) od 2026-09-12 są złożone z bloków shadcnspace (`src/components/ui/shadcn-space/blocks`, rejestr `@shadcn-space` w `components.json`, wzór https://dashboard.shadcnspace.com/, ciemny neutralny motyw): boczny pasek na prymitywach `ui/sidebar.tsx` (grupy Workspace/Knowledge/Review/Manage, ikonowy tryb zwinięty, arkusz mobilny z przyciskiem „Menu”), karty KPI (`statistics-01`) z ikoną w kolorowym kwadracie i plakietką trendu, wykresy na `ui/chart.tsx` + Recharts (`chart-01` słupkowy dla lejka dostarczania, `chart-02` pierścieniowy z liczbą pośrodku dla werdyktów opinii i warstw wiedzy), tabela `table-01` dla najlepszych skilli i pusty stan `empty-state-01` dla braku telemetrii/repozytorium. Motyw `.console` w `src/tokens/tokens.css` podmienia tokeny shadcn (`--background`, `--primary`, `--sidebar*` itd.) na wartości ciemne neutralne tylko wewnątrz powłoki zarządzania; strona `/` (landing) nigdy nie dostaje klasy `.console` i zachowuje pomarańczową markę. Szczegóły instalacji, dostosowań i zrzuty ekranu: [docs/reports/ui/console-shadcn-20260912.md](../docs/reports/ui/console-shadcn-20260912.md) §9.
