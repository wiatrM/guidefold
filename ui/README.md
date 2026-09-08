# Guidefold UI
Status: fixture plus warstwa API, 2026-09-07. Siedem widoków U4 wydzielonych z zatwierdzonego hi-fi Industrial Surveyor; wszystkie siedem czyta hostowane API przez `DataSource`, a tryb fixture pozostaje bez zmian.
Wejścia: [AGENTS](../AGENTS.md), [reguły dokumentacji](../docs/DOCUMENTATION-RULES.md), [etap 7](../docs/ui/pipeline/07-frontend.md), [etap 8](../docs/ui/pipeline/08-components.md). Zastępuje hi-fi jako miejsce dalszej pracy; zamrożony wzorzec pozostaje w prototypes/pipeline-hifi.

## Uruchomienie
Node 22.14.0 i pnpm 10.30.3:
```sh
cd ui
pnpm install --frozen-lockfile
pnpm dev
```
Otwórz http://127.0.0.1:4331. Galeria komponentów: /__components, poza nawigacją produktu.

## Tryb fixture i tryb API
Bez zmiennej `VITE_GUIDEFOLD_API` aplikacja startuje w trybie fixture: dane pochodzą z `src/data/fixture.json`, a szkic scenariusza z sessionStorage. Nagłówek ma odznakę `Local simulation`.

Tryb API wybiera `main.tsx`, gdy ustawiono `VITE_GUIDEFOLD_API` albo gdy adres startowy zawiera `?mode=api`; `?mode=fixture` zawsze wymusza fixture. Tryb czytany jest przy starcie aplikacji, więc zmiana parametru wymaga przeładowania strony.
```sh
# to samo pochodzenie przez proxy dewelperskie (domyślne)
pnpm dev            # /api i /v1 → http://127.0.0.1:8765
# inne pochodzenie
VITE_GUIDEFOLD_API=https://api.example.test pnpm dev
```
W trybie API nagłówek pokazuje organizację z `/me` i repozytorium z adresu (`?org=`, `?repo=`), bez odznaki fixture. Organizacja spoza `/me.orgs` daje stan restricted bez żadnej informacji o jej treści.

### Pokrycie trybu API
| Widok | Operacje kontraktu | Uwagi |
|---|---|---|
| Import | `auth/providers`, `orgs`, `repos`, `imports`, `imports/{id}`, `imports/{id}/plan`, `imports/{id}/proposals:generate` | Polling statusu co 2 s do stanu terminalnego. Generowanie propozycji: plan (grupy, wejścia, szacunek kosztu, limity, generator) czytany przed startem, tylko dla ownera; `proposals:generate` otwiera jedno zadanie `proposal.generate` na rodzaj z własnym `Idempotency-Key`; osobny polling zadań generacji po `job_ids` (niezależny od pollingu statusu importu, który zatrzymuje się po pierwszym stanie terminalnym importu); `skipped`/`llm_not_configured` pokazywany jako uczciwy stan, nie błąd. |
| Library | `skills`, `skills/facets`, `skills/facets/lookup` | Filtry `q, scope, owner, layer, status` i `cursor` w URL; bez pobierania body. Aktywna wartość ma własny lookup; `filters[*].available:false` renderuje jawny brak, nigdy cichego „All”. |
| Map | `map/repository`, `map/scopes`, `map/layers`, `map/relations`, `modules/{scope}` | Leniwe rozwijanie gałęzi (≤100 obiektów na żądanie, twardy limit renderu 200), tekstowa lista relacji z etykietą typu, jawne `truncated`, nazwany unmapped scope. |
| Skill | `skills/{id}`, `revisions/{rev}`, `revisions/{rev}/raw`, `revisions/{rev}/feedback` | Brak rewizji to `revision_not_found`, nigdy podmiana na nowszą. Link źródła buduje się z `source.url`; bez `git_host_url` pokazujemy ścieżkę i „Source host not configured”. |
| Proposals | `proposals`, `proposals/{id}`, `decision`, `export`, `publication`, `snapshots`, `snapshots/{id}/activate`, `publish` | `expected_revision` + stabilny `Idempotency-Key` na szkic; 409 `stale_revision` zachowuje tekst i wymaga ponownego odczytu. Eksport pokazuje `files[]`, patch i komendę `guidefold proposals apply <export_id> --write`; publikacja pollowana co 2 s do stanu terminalnego. |
| Usage & quality | `usage`, `usage/export`, `usage/queue/{id}/decision` | Kolejka „Needs review” pierwsza; `helped_ratio: null` to Unknown, `small_sample` pokazuje liczby zamiast procentu, brak zdarzeń to „No observations”. |
| Organization | `members`, `invitations`, `installations`, `auth/device/*`, `audit`, `me/identities/link/start` | Sekrety pokazywane raz, nigdy nie zapisywane. Audit to trzecia zakładka, tylko dla ownera (`GET .../audit?cursor`), paginacja kursorem, pusty stan „No audit entries”. Sugestie łączenia tożsamości (`/me`'s `link_suggestions`) pokazywane w zakładce Members dla każdego użytkownika — nigdy automatycznie łączone; akcja startuje flow i przekierowuje na `login_url` zwrócone przez API. |

Sześć stanów per trasa działa jak w [etapie 7](../docs/ui/pipeline/07-frontend.md): degraded to ostatni potwierdzony odczyt tylko do odczytu (odświeżenie nie powiodło się albo `useAccess()` zwraca `offline`), a restricted (odmowa lub brak potwierdzenia dostępu >45 s) ma pierwszeństwo i jest egzekwowany w powłoce `ApiApp`.

## Sprawdzenia
```sh
pnpm build
pnpm test
pnpm test:contracts
pnpm exec playwright install chromium
pnpm test:e2e
# Te dwie komendy wymagają działającego pnpm dev:
pnpm test:flow
pnpm test:visual
```
Porównanie wizualne czyta niezależny baseline sprzed ekstrakcji i sprawdza SHA źródeł/obrazów. Nie regeneruj baseline, aby zaakceptować zmianę UI. Testy Playwright i wizualne używają publicznego Meridian fixture; nie dowodzą zachowania trybu API.

## Zestaw live: siedem widoków na realnym API

Status: opt-in, 2026-09-07. Cel: dowód, że tryb API działa przeciw uruchomionej usłudze Go z
Postgresem, a nie tylko przeciw stubom `page.route` z `e2e/api-mode.spec.ts`. Wejścia: działający
stos z `tools/dev/stack.py`, zasiew z `stack.py seed`, zmienne `GUIDEFOLD_E2E_*`.

Specyfikacje leżą w `e2e/live/` i mają własną konfigurację `playwright.live.config.ts` (projekt
`live`, jeden worker, bo dzielą wiersze jednej organizacji). Zwykłe `pnpm test:e2e` ich nie zbiera
(`testIgnore: '**/live/**'`), a zestaw live nie zbiera specyfikacji fixture.

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
Każdy z 14 komponentów ma CSS Module, testy kontraktu i stories CSF. Galeria podaje stałe, zgodne ze wzorcem props.
Trasy odpowiadają za formularze, decyzje i nawigację. Dane wchodzą wyłącznie przez `DataSource` (`src/data/source.ts`): `FixtureDataSource` opakowuje adapter Meridian i symulację sessionStorage, `ApiDataSource` korzysta z `src/api/`.
`src/api/` zawiera jeden klient fetch (generacja dostępu, numer żądania per zasób, retry GET ≤2 z Retry-After, `Idempotency-Key` i potwierdzenie mutacji po timeoucie), dekodery DTO, cache w RAM z namespace user/org/repo/policy oraz potwierdzanie dostępu (`/me` co najwyżej co 25 s, maskowanie danych starszych niż 45 s, 401/403 czyści cache i szkice). Prywatne dane nie trafiają do localStorage, sessionStorage ani cache HTTP.
`src/routes/apiState.tsx` trzyma wspólny cykl życia tras API (`useAsync`, `ApiFailure`, notatki degraded/partial, klucz idempotencji szkicu, pobranie dokładnych bajtów). Nie jest to piętnasty komponent: biblioteka publiczna nadal ma 14 katalogów w `src/components`.
Kontrakt DTO i dziedziny zamknięte są w `src/api/decoders.ts` i muszą zgadzać się z [API-CONTRACT](../docs/API-CONTRACT.md) §5–§6; nieznana wartość dziedziny to błąd dekodowania na granicy trasy, nie ciche podstawienie.
`e2e/api-mode.spec.ts` uruchamia siedem widoków w trybie API na stubie `page.route('**/api/v1/**')` z danych fixture (logowanie → filtry → skill → decyzja → eksport → kolejka usage, ścieżka klawiaturowa i axe), plus plan → generowanie propozycji → uczciwy stan skipped, zakładkę Audit z paginacją kursorem i sugestię łączenia tożsamości z rzeczywistym przekierowaniem przeglądarki na `login_url`. Stub dowodzi okablowania UI, nie zachowania serwera Go.
Eksport w trybie fixture to pobranie SKILL.md; w trybie API `export` zwraca pliki i patch, a `Published` wymaga potwierdzenia z `publication`. Simulate Git sync nie dowodzi rzeczywistej publikacji ani dostarczenia do adaptera.
