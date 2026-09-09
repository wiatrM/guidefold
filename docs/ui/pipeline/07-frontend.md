# 7. Plan frontendu
Status: plan po dwóch rundach, 2026-09-06; 0 otwartych P1/P2. 2026-09-08: właściciel usunął adapter fixture z ui/; wzmianki o fixture poniżej opisują plan i odbiór F1–F9, nie bieżący kod (jedyny adapter to `ApiDataSource`, [ui/README](../../../ui/README.md)).
Wejścia: [04](04-wireframes.md), [05](05-simulation.md), [06](06-ux-ui.md), [UI §5](../UI.md), [pivot U4](../../PRODUCT-PIVOT.md), [architektura](../../PIVOT-ARCHITECTURE.md), [ADR-0031](../../adr/ADR-0031-monorepo-to-managed-skill-library.md).
Cel: port siedmiu tras do ui/ oraz podłączenie zatwierdzonych kontraktów. Etap 8 dostarcza bibliotekę i działający fixture; poniższy plan integracji nie deklaruje gotowego backendu.

## Stack
| Obszar | Decyzja / powód |
|---|---|
| Runtime | React 19.2.8, TypeScript 7.0.2, Vite 8.2.2; wersje już budują hi-fi. Node 22.14.0, pnpm 10.30.3; piny i lockfile w każdym pakiecie. |
| Routing | React Router DOM 7.18.3, BrowserRouter; siedem tras, query z filtrami/osią/skill/revision. Statyczny host ma fallback do index.html; /api nigdy nie trafia do tego fallbacku. |
| Style | CSS Modules, lokalne fonty, Phosphor regular; Spectrum UI Charts registry dla telemetry charts. ui/src/tokens/tokens.css jest jedynym miejscem wartości kolorów i rozmiarów w ui/src. |
| Stan | URL dla nawigacji, formularz lokalny dla szkicu, jedna warstwa fetch z AbortController, generacją dostępu oraz numerem żądania zasobu; bez globalnego Redux i bez przechowywania sekretów w JS. |
| Kontrakt | Typy z wersjonowanego OpenAPI Go; dekodowanie payloadów w granicy API przed renderem. Fixture adapter spełnia ten sam interfejs, bez podszywania się pod sieć. |
| Markdown | react-markdown 10.1.0, bez raw HTML i automatycznego pobierania obrazów ze źródeł. Eksport porównuje dokładne bajty, nie HTML podglądu. |
| Testy | Vitest 5.0.0 + Testing Library/jsdom dla kontraktów; Playwright Chromium dla interakcji, axe i renderu. Vitest5 wspiera użyte Node/Vite według metadanych pnpm odczytanych 2026-09-06. |

Go API pozostaje modularne, worker osobnym procesem; jeden Postgres i GCS. UI nie uruchamia LLM/buildera i nie wprowadza BFF w NestJS ani mikroserwisu dla widoku.
AuthKit: redirect Google/GitHub przez Go, callback i odświeżanie sesji w Go; cookie HttpOnly/Secure/SameSite oraz ochrona CSRF dla zmian. Guidefold sprawdza aktualne membership przy każdym request, niezależnie od claimu organizacji. [WorkOS sessions](https://workos.com/docs/authkit/sessions), odczyt 2026-09-06.
Użycie sesji nie daje OAuth dostępu do kodu repo. W aplikacji nie ma WorkOS API key, refresh tokena ani administracyjnego klucza SEARCH/USE.

## Spectrum Charts inventory

| Route/file | Previous renderer | Spectrum registry item | Data contract | Evidence |
|---|---|---|---|---|
| Usage → delivery/context, `src/components/MetricRow/SpectrumTelemetryChart.tsx` | Local dependency-free SVG bars | [`@spectrumui/bar-chart`](https://ui.spectrumhq.in/charts/bar) | `{month, desktop, mobile}` rows; text list keeps exact counts | Registry source adapted to CSS Modules/tokens; Vitest adapter test |
| Usage → feedback, same adapter | Local stacked SVG | [`@spectrumui/pie-chart`](https://ui.spectrumhq.in/charts/pie) via `DonutPieChart` | `{name, value}` non-zero verdict slices; full verdict list remains textual | Registry source adapted to CSS Modules/tokens; Vitest adapter test |

All telemetry visualizations route through the registry adapters above. Empty and unknown states are rendered as explicit text and unknown is never coerced into a failure.

## Układ ui/
| Katalog | Odpowiedzialność |
|---|---|
| src/tokens, components | Tokeny i najwyżej 14 eksportów z UI §4; każdy index, CSS Module, test i story. |
| src/routes, app | Formularze, lifecycle, nawigacja, per-route error/loading boundary oraz orkiestracja; bez drugiej biblioteki layoutów. |
| src/domain, data | Obiekty i czyste funkcje; port `DataSource` z jednym adapterem API (od 2026-09-08; wcześniej dodatkowo oznaczony adapter Meridian). Produkcyjny build nie importuje danych przykładowych ani wszystkich body. |
| src/api | Jeden klient, dekodery i cache RAM: namespace user/org/repo/policy i pełny klucz operacji/zasobu/query; bez kopiowania fetch do komponentów. |
| src/test, e2e, qa | Setup testów, scenariusze, raporty i galeria developerska. Galeria nie jest ósmym widokiem produktu ani pozycją menu. |

Czyste lineDiff i typy nie importują danych; adapter danych jest wstrzykiwany przy składaniu aplikacji. Produkcyjna granica API nie importuje danych Meridian.
Hi-fi pozostaje niezależnym punktem odniesienia sprzed ekstrakcji; ui nie importuje komponentów z prototypes/. Od 2026-09-08 galeria ui renderuje wartości przykładowe z `ui/src/sample.ts`, a pixel diff porównuje ją z własnym zaakceptowanym baseline `ui/qa/baseline/` (08 §Tokeny).

## Granice danych
Wiersze poniżej są projektowanymi kontraktami management API; ścieżki i DTO utrwalamy w OpenAPI przed integracją, nie udajemy istniejących endpointów.
| Trasa | Potrzebne operacje / dowód |
|---|---|
| Import | Sesja i org; manifest/plan uploadu, create import, odczyt import_id/jobów; accepted/omitted/failed i digest wejścia. UI polluje ograniczony status, nie parsuje całego monorepo. |
| Library | Stronicowane summary po org/repo/scope/owner/layer/status/q, cursor + snapshot_id; bez body. Opcje scope/owner/layer/status pochodzą z autoryzowanego kontraktu facets z tego snapshotu, niezależnie od strony wyników. |
| Map | Osobne children źródeł/scope, lista warstw oraz sąsiedztwo relacji z kursorem i typem; brak automatycznej klasyfikacji source layer. |
| Skill | Summary + wybrana immutable revision; body, references, requires/refines i feedback z epizodem/źródłem. Brak rewizji nie zastępuje jej nowszą treścią. |
| Proposals | Source/candidate digests, recipe/source refs, diff, decyzja z powodem i expected revision; eksport; odczyt publikacji po Git review/merge/validation/sync. |
| Usage & quality | Agregaty i kolejka z przyczyną, oknem, źródłem, mianownikiem, coverage i watermarkiem; download, context_loaded, outcome osobno. |
| Organization | Membership owner/member, ochrona ostatniego ownera, instalacje, ograniczone tokeny i status połączenia; sekrety ujawniane jednorazowo według API. |

Facets obsługują wyszukiwanie/stronicowanie wartości; aktywna wartość z URL ma osobny lookup i pozostaje widoczna także poza bieżącą stroną. Nieznana/niedostępna wartość daje jawny błąd filtra, nie cichy powrót do All. Nie pobieramy katalogu lub body, aby zbudować select.
Obecne SEARCH/USE i events:batch zachowują [kontrakt](../../HARNESS-SERVICE-CONTRACT.md) i [telemetrię](../../SEARCH-USE-TELEMETRY.md). Rozszerzenie pakietów/closure 1.2 z ADR-0031 wymaga własnej walidacji; UI nie dopisuje gwarancji do 1.1.
Odpowiedź ma request_id, schema_version, org/repo, snapshot/policy oraz kompletność; treść skilla i manifest pakietu mają osobne nazwane digests. Nie mutujemy globalnego tenant/repo w serwisie.
Klucz cache obejmuje operację, ID zasobu, content/package revision, snapshot i znormalizowane filtry/cursor; namespace dostępu nie wystarcza. Numer aktywnego żądania zasobu odrzuca starszą odpowiedź także przy zmianie filtrów/rewizji w tej samej org; anulowanie jest dodatkową optymalizacją.
Każda mutacja wiąże idempotency_key z tym samym payloadem i oczekiwaną rewizją. 409 pokazuje nieaktualne źródło oraz wymaga ponownego review; zachowuje lokalny tekst, ale blokuje wcześniejszą decyzję/eksport.
GET może mieć najwyżej dwa ponowienia z backoff/Retry-After; mutacja po timeout najpierw odczytuje wynik po kluczu operacji. Brak potwierdzenia nie zmienia stanu na sukces.

## Offline i awarie
Prywatne body, feedback i propozycje nie trafiają do localStorage, sessionStorage, service workera ani trwałego cache HTTP (Cache-Control: no-store); od 2026-09-08 nie ma też publicznego trybu lokalnego.
Produkcyjne degraded pozwala czytać snapshot RAM wyłącznie po świeżym potwierdzeniu membership/policy przez API, gdy niedostępna jest usługa danych. Bez łączności pozwalającej zweryfikować dostęp prywatny widok jest zasłonięty; nie obiecujemy offline pracy na danych klienta.
U3 AC4 wymaga odwołania dostępu do 60 s. Projekt: potwierdzenie dostępu ważne maks. 45 s od rozpoczęcia requestu, odnowienie co 25 s z timeoutem 5 s; niepotwierdzone odnowienie nie przedłuża ważności. Deadline zasłania prywatny widok. Ukrycie karty zasłania dane, a wznowienie wymaga sprawdzenia przed odsłonięciem; API egzekwuje niezależnie własne odwołanie. To kontrakt Guidefold, nie SLA WorkOS.
Wylogowanie, 401/403 lub zmiana user/org/policy czyści cache i prywatne szkice, anuluje requesty oraz odrzuca spóźnione odpowiedzi poprzedniej generacji. Brak sieci bez odmowy nie oznacza automatycznego wylogowania; UI zachowuje sesję, ale nie odsłania danych bez sprawdzenia.
Obsługa błędu modułu JS, timeoutu i błędu dekodowania jest na granicy trasy. Retry nie usuwa dostępnego szkicu z powodu zwykłego błędu walidacji; decyzji ani publikacji nie aktualizujemy optymistycznie.

## Sześć stanów per route
Ready nie zastępuje kontroli uprawnień. Restricted ma pierwszeństwo przed pozostałymi stanami; member w dozwolonej org nie jest restricted.
| Route | Empty | Loading | Partial | Error | Degraded | Restricted |
|---|---|---|---|---|---|---|
| Import | Brak repo→start | Status joba | accepted/omitted, bez finalizacji | Etap i retry z tym samym import_id | Ostatni status, bez uploadu | Bez manifestu/liczników |
| Library | Brak wyników→filtry/import | Szkielet strony | Zakres i cursor, braki jawne | Retry strony | Autoryzowany snapshot RAM, odczyt | Bez nazw/summary |
| Map | Brak obiektów→import | Ładowany fragment | Limit/pominięte relacje | Retry gałęzi | Autoryzowany fragment, odczyt | Bez węzłów/liczników |
| Skill | Brak wyboru→lista | Konkretna rewizja | Brak body/referencji nazwany | Niedostępna rewizja, bez podmiany | Odczyt sprawdzonego snapshotu | Bez body i feedbacku |
| Proposals | Brak kandydatów→źródła | Źródło i kandydat | Blokada decyzji/eksportu | Niezapisana decyzja/409 | Odczyt, brak mutacji | Bez źródeł/diffu |
| Usage | No observations | Okno raportu | Coverage/mianownik niepełny | Błąd raportu, bez zera | Ostatni watermark i ograniczenie | Bez agregatów org |
| Organization | Wybór/tworzenie org | Membership/installations | Brakujące dane i brak zmian | Błąd konkretnej operacji | Odczyt potwierdzonej roli | Sesja/dostęp do ponowienia |

## Budżety
U4 AC2: p95 pierwszej strony przy 10 tys. skilli ≤2 s w rzeczywistej sieci pilota; dotyczy czasu od wejścia/filtra do klikalnego pierwszego wyniku, nie samego response HTTP.
Budżety robocze [założenie]: 50 summary na stronę, ≤100 kB gzip payloadu, ≤250 kB gzip początkowego JS; odpowiedź katalogu p95≤500 ms. Obali je profil z rzeczywistymi nazwami/ścieżkami lub pomiar pilota; zmiana limitu wymaga zachowania AC2.
Map ładuje tylko żądane children i sąsiedztwo (start≤100 obiektów, twardy limit renderu 200); cursor daje dostęp do reszty. Body/duży diff pobieramy dopiero na szczególe, a parsing diffu odkładamy poza pierwszy render.
Pomiar: produkcyjny build, zamrożony dataset 10k, wersje sprzętu/przeglądarki i sieć zapisane przed runem, co najmniej 100 prób osobno cold/warm; p95 każdej grupy i błędy, nie średnia. Lokalny seed oznaczamy jako syntetyczny; zaliczenie U4 wymaga także realnego środowiska pilota.
Hi-fi ma 27 plików i główny chunk ~639 kB/172 kB gzip; to punkt kontroli ekstrakcji, nie wynik testu 10k. W produkcji body nie wchodzą do bundle, a koszt query mierzymy na Go/DB i końcu UI.

## Testy i kroki
Vitest: kontrakty komponentów, dekodery, konflikty rewizji, odpowiedź org A po przejściu do B oraz odwrócona kolejność filtrów/rewizji w jednej org. Playwright: właściciel import→źródło→edit/approve→dokładny eksport→Git→published, odmowa/member oraz utrata sieci.
U4 AC3/AC4: sprawdzamy dokładny host/plik/commit linku Git oraz cały login→import→lista→review wyłącznie klawiaturą, w tym focus po zmianie stanu. Osobny test odwołuje membership przy bezczynnej stronie/ciepłym cache i po wznowieniu karty; odsłonięcie danych nie przekracza 60 s.
Etap 8 sprawdził lokalny fixture i symulację Git (zapis historyczny; usunięte 2026-09-08). Osobny test integracyjny hostowanego MVP używa prawdziwego callbacku, testowego repo Git i potwierdzonego sync (`ui/e2e/live/`); testy na stubie API (`ui/e2e/stub.ts`) dowodzą okablowania, nie publikacji.
CI: frozen lockfile→typecheck/build→Vitest→Playwright+axe dla 7 tras/galerii i ujawnionych formularzy→pixel diff niezależnej galerii; retry testu nie zamienia flaky w zielone. [Vitest](https://vitest.dev/guide/), [Playwright axe](https://playwright.dev/docs/accessibility-testing), odczyt 2026-09-06.
Kroki to ≤1 dzień pracy frontendu każdy [założenie], po gotowych zależnościach; brak API lub przekroczenie kroku rozbija go przed kontynuacją. Nie jest to estymacja pracy backendu, auth ani workera.
| Krok / nakład FE | Zależność | Gotowe |
|---|---|---|
| F1 0,5 d — freeze referencji | Zamknięte 06 | Niezależne obrazy i hash źródeł galerii przed ekstrakcją. |
| F2 1 d — czyste funkcje i adapter | F1 | lineDiff/typy bez importu fixture, jawne składanie adaptera. |
| F3 1 d — pierwsze 7 komponentów | F2 | Kontrakty/testy/stories oraz zgodny render. |
| F4 1 d — kolejne 7 | F3 | ≤14 eksportów, kontrakty a11y/state bez sprawl. |
| F5 1 d — shell i Import/Organization | F4 | URL, rola fixture, lokalny onboarding i member/owner. |
| F6 1 d — Library/Map/Skill | F5 | Filtry/powrót, trzy osie, immutable source i feedback. |
| F7 1 d — Proposals/Usage | F6 | Lokalny lifecycle, edycja, dokładny eksport i rozdzielone dowody. |
| F8 1 d — galeria i wizualne QA | F4–F7 | Wszystkie stories, stany i niezależny pixel diff. |
| F9 1 d — CI i odbiór fixture | F8 | Build/Vitest/axe zielone; pełna ścieżka klawiaturą i host/plik/commit Git (etap 8). |
| F10 1 d — klient i dekodery API | OpenAPI Go, tenant cache z bramki CTO | GET/error/cancel i testy A/B, filtrów/rewizji w odwróconej kolejności. |
| F11 1 d — callback UI i org entry | Go auth/CSRF i testowy WorkOS | Google/GitHub/logout; deadline 60 s przy otwartej i wznawianej karcie. |
| F12 1 d — manifest i postęp | API import/job/idempotency | accepted/omitted/failed i bezpieczny retry. |
| F13 1 d — katalog i opcje | API stron + facets/lookup | Filtry/cursor bez body; owner/scope spoza strony 1 i odtworzenie URL. |
| F14 1 d — trzy osie Map | API children/relations | Lazy fragment, limit i dostępność każdego obiektu. |
| F15 1 d — szczegół i feedback | API rewizji/feedback | Immutable body/mismatch, epizod i właściwy host/plik/commit linku Git. |
| F16 1 d — decyzja i konflikt | API proposals/409 | Powód/diff, brak zapisu na starym źródle. |
| F17 1 d — eksport i status | Pakiety1.2 oraz Git validation/sync | Eksport zgodny z digestem, published z dowodu API. |
| F18 1 d — usage/quality | Ledger/agregaty/watermark | Unknown i mianownik; kolejka z przyczyną. |
| F19 1 d — org/integrations | Membership, token API i adapter | Last owner, revoke i observed health bez fałszywego sukcesu. |
| F20 1 d — integracyjne R | F11–F19, testowe org A/B/repo | Realny owner flow klawiaturą, Git links i revoke≤60 s przy ciepłym cache. |
| F21 1 d — profil i pilot Q | R zielone, dane10k i uczestnicy | Raport pomiaru; AC2/AC5 zaliczone albo jawnie niezaliczone. |

## Przegląd
R1 — Owner P1=0/P2=1/P3=0; Principal 0/3/0; Architekt 0/1/0. Pięć P2: odbiór AC3/4, pełna tożsamość żądania, facets, kroki portu oraz czas odwołania dostępu.
R2 — Owner, Principal i Architekt: każdy 0/0/0; pięć P2 zamkniętych.
Wyjście: 0 otwartych P1/P2/P3; kompletność planu nie jest dowodem implementacji ani estymacji.
