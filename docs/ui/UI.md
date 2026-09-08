# UI Guidefold

Status: frontend fixture w ui/, 2026-09-06; etapy 6 i 7 zamknięte. Ekstrakcja etapu 8 zamknięta po dwóch rundach, bez otwartych P1/P2/P3; wyniki i granice w [08-components](pipeline/08-components.md).
Cel: system wizualny i zakres ekstrakcji siedmiu widoków U4. Wejścia: [IA](IA.md), [UX](UX.md), [brief](pipeline/00-brief.md), [makiety](pipeline/04-wireframes.md), [symulacja](pipeline/05-simulation.md), [pivot](../PRODUCT-PIVOT.md).
Zastępuje dokument 2026-09-04 z commitu 88e404561a9f6994cd870743bf858b9b0a616126. Reguły użycia: [DOCUMENTATION-RULES](../DOCUMENTATION-RULES.md).

## 1. Decyzje wizualne

Jedyny wzorzec: [Industrial Surveyor](../../prototypes/industrial-surveyor/DESIGN.md), [plansza źródłowa](../../prototypes/industrial-surveyor/design-reference/source-industrial-surveyor.png) i [styles.css](../../prototypes/industrial-surveyor/src/styles.css), odczyt 2026-09-06.
Implementacja: [ui](../../ui/). Zamrożone odniesienie sprzed ekstrakcji: [pipeline-hifi](../../prototypes/pipeline-hifi/). Plansza jest odniesieniem marki; zakres i zachowanie określa aktualny pivot.

| Zachowujemy | Zmieniamy względem starego prototypu / UI | Dlaczego |
|---|---|---|
| Paletę graphite, teal i orange; czerwony dla błędów | Rejected oraz usunięta linia diffu nie są czerwonym błędem | Odrzucenie jest decyzją człowieka; diff opisuje zmianę. |
| Barlow Condensed i Inter, fonty lokalne | Mono dla URN, SHA, ścieżek i kodu | Czytelność dokładnych identyfikatorów i plików. |
| Siatkę 8 px, radius 2 px, border 1 px | Balanced 40 px jest stałe; brak przełącznika gęstości | Wymaganie zlecenia, bez dodatkowej konfiguracji. |
| Oryginalny raster znaku i survey-grid-pattern | Brak nowego SVG logo, mapy z divów lub topograficznego tła pod treścią | Zachowanie zatwierdzonego assetu i czytelności danych. |
| Kanciaste panele i status z etykietą | Siedem widoków, bez Route monitor/Component bay/Asset library w nawigacji | Zakres U4. Galeria pozostaje narzędziem developerskim. |
| Phosphor regular | Bez fill, emoji oraz dekoracyjnych ikon metryk | Jedna waga w całym interfejsie. |
| Wzorzec dowodu przy decyzji | Brak fikcyjnej promocji team → division → company, quorum i metryk | Fixture deklaruje inne dane; brak klasyfikacji to Unclassified. |
| Ciemny motyw graphite | Brak czterech starych sekcji Atlas/Review/Routing/Health | Login, org, import, biblioteka i obieg propozycji wynikają z pivotu. |

Końcowy audyt: 21 zrzutów gotowej treści bez overflow, naruszeń axe i błędów JS; dodatkowo 42 scenariusze stanów i brak wycieku restricted. Mobilny rail skrócono z 524 px do Navigate. Formalne przeglądy zamknięte; [dowody](pipeline/06-ux-ui.md).

## 2. Tokeny

Kanoniczne wartości aplikacji: [ui/src/tokens/tokens.css](../../ui/src/tokens/tokens.css). Nie kopiuj wartości do modułów CSS; dotyczy to także transparent. Hi-fi pozostaje niezależnym odniesieniem. Dwa tokeny techniczne etapu 8 uzasadnia [08-components](pipeline/08-components.md).

| Grupa | Pochodzenie / zastosowanie |
|---|---|
| graphite-950/900/850/800/700, stone-100/300, steel, survey-teal/dim, safety-orange, warning, signal-red, line/strong | Paleta i obrysy skopiowane ze styles.css wzorca. |
| system/human/warning/error-ink i -wash | Nazwane tokenami istniejące wartości statusów ze wzorca; tekst i płaskie tło stanu. |
| control-border | Alias steel; istotne granice formularza wymagają silniejszej widoczności niż dekoracyjne line. Zmierzony kontrast obrysu: co najmniej 3,96:1. |
| font-body/display/mono, font-size-*, weight-*, line-height-*, tracking-* | Stała skala dla formularzy, długiej treści, metadanych, nagłówków i dokładnego kodu. |
| space-1…7, border-width, radius, focus-width/offset | Odstępy 4/8/16/24/32/48/64 px; geometria 1/2 px. Offset focusu oddziela obrys od kontrolki. |
| row-height, control-height, touch-height, icon-size/large, brand-size | Wiersz i kontrolka 40 px; kontrolka mobilna 44 px; spójne ikony i oryginalny znak 40 px. |
| rail-*, shell-columns, page-padding, topbar-height | Przenoszą planszę marki na siedem dostępnych tras z widocznym kontekstem org/repo. |
| table-min-width, table-first-column, source-disclosure-width | Czytelne minimum tabeli/kolumn i Source details; poziomy scroll zamiast liter w pionie. |
| filter-columns, filter-form-columns/areas | Filtry i przyciski w zwartej kompozycji desktopu; pierwszy wynik widoczny w 720 px, na mobile kolejno. |
| two/aside/field/steps/metric-columns | Układy składane do jednej kolumny; kolejność czytania pozostaje w DOM. |
| form/reading/source-width, text-area/body-editor-height, raw-max-height, scroll-offset | Ograniczają długość wiersza i pełny surowy plik; decyzja pozostaje osiągalna po rozwinięciu treści. |
| zero, full, viewport, min-page-width, grid-tile | Wspólne rozmiary struktury i skali istniejącego rastra. |
| desktop/mobile-display, rail/context-padding, layer-skip, skip-hidden-offset | Kompaktowe menu na telefonie oraz link pomijania nawigacji; pełny powód każdego tokenu w [inwentarzu](../../prototypes/pipeline-hifi/qa/token-provenance.json). |
| duration, ease, disabled-opacity | Krótkie przejścia stanu i oznaczenie niedostępności; reduced motion ustawia duration na zero. |

Każdy dalszy token wymaga nazwy, zastosowania i powodu w dokumencie etapu. Sama możliwość stworzenia wariantu nie uzasadnia nowej wartości.

| Rola | Bieżące ustawienie |
|---|---|
| Tytuł | Barlow Condensed 700, 32 px; mobile 28 px |
| Sekcja / tekst metryki | Barlow Condensed 600, odpowiednio 20 / 28 px |
| Body | Inter 400, 14 px, line-height 1,55 |
| Metadane i tabela | Inter, 12 px; ważna treść nie jest ukryta przez mały kontrast |
| Kod / URN / SHA | Systemowy monospace, 12 px |
| Eyebrow | Barlow Condensed 600, 12 px, uppercase i tracking 0,12 em |

Teal opisuje system/wybór; orange decyzję człowieka i focus; warning częściowe lub ograniczone dane; red wyłącznie błąd. Neutralne Unknown nie jest zielonym potwierdzeniem.
Diff korzysta z +/−, opisu i istniejących wash: dodanie teal, usunięcie orange. Kolor nie określa poprawności zmiany.

## 3. Układ i stany

| Szerokość | Układ bieżącego hi-fi |
|---|---|
| Ponad 1080 px | Rail 216 px, treść minmax(0,1fr), porównanie źródło/kandydat w dwóch kolumnach. |
| 721–1080 px | Rail 184 px; porównanie w jednej kolumnie, pola i etapy najwyżej w dwóch. |
| Do 720 px | Kompaktowa nawigacja w natywnym disclosure Navigate, początkowo zamknięta; siedem pozycji po rozwinięciu. Org/repo pozostaje widoczne, pola i panele pojedynczo, padding 16 px. |

Wymagane zrzuty: siedem widoków przy 1280×720, 820×720 i 390×720. Nie ukrywamy funkcji na mobile. Duże tabele mają własny obszar przewijania; body, URN i ścieżki zawijają się.
Kontekst meridian/monorepo, Meridian fixture, rola symulatora i commit są widoczne, dopóki scenariusz dopuszcza odczyt. Restricted nie pokazuje danych organizacji.
Map ma Repository/Scopes/Pyramid z tekstowym drzewem i relacjami. Source layer oraz Knowledge layer są oddzielne; nie rysujemy pełnej sieci 10 tys. skilli.

| Stan | Wygląd i zachowanie |
|---|---|
| Empty | Nazwany brak obiektu/obserwacji i dostępny następny krok, bez liczb udających wyniki. |
| Loading | Stałe szare wiersze bez shimmeru; aria-busy, brak aktywnej decyzji. |
| Partial | Etykieta i komunikat warning; jawny dostępny zakres oraz braki. |
| Error | Tekst błędu i red; informacja o niepotwierdzonej operacji oraz dostępne retry. |
| Degraded | Warning i opis dostępnego snapshotu; odczyt, bez nowych zmian. |
| Restricted | Ogólny komunikat dostępu; brak body, nazw, liczników i poprzedniego cache org. |

Stany dotyczą tras; nie wymagamy sześciu sztucznych wariantów każdej ikony. Member w dostępnej org jest innym przypadkiem niż restricted. Macierz per widok i wymagania: [04 §5](pipeline/04-wireframes.md), [UX](UX.md).

## 4. Komponenty

Aktualne 14 eksportów [ui/src/Shared.tsx](../../ui/src/Shared.tsx), inwentarz z 2026-09-06. Każdy wydzielony komponent ma testy i stories; szczegółowe props, stany i dowody: [08-components](pipeline/08-components.md).

| Komponent | Użycie | Granica odpowiedzialności / stan |
|---|---|---|
| ActionButton | Nawigacja i formularze siedmiu tras | Button albo link; neutral/system/human, disabled. Nie autoryzuje operacji. |
| BrandMark | Rail | Oryginalny raster oraz wordmark; bez wariantów znaku. |
| Panel | Dowody, formularze i listy | Tytuł, eyebrow, ikona i opcjonalna akcja; section z nazwą. |
| StateBadge | Stan źródła, procesu i dowodu | Etykieta z tone; kolor nie zastępuje tekstu. |
| RouteState | Sześć stanów tras | Tytuł, opis i dostępna akcja; loading ma szkielet i aria-busy. |
| Tabs | Osie Map, zakładki Skill/Organization | Linki w nav z aria-current; bez pozornego ARIA tablist. |
| ProvenanceTrail | Metadane źródła i rewizji | Lista label/value/detail/link; nie wnioskuje pochodzenia. |
| ScopeTree | Repository i Scopes | Natywne disclosure oraz linki; zaznaczenie i opis. |
| DataTable | Library, manifest, relacje i membership | Caption, nagłówki oraz wiersze; sortowanie/filtry są logiką trasy. |
| SkillDiff | Proposals | Rzeczywisty source/candidate; No text changes albo oznaczone linie. |
| MetricRow | Liczniki fixture i dowody użycia | Label/value/detail; Unknown jest dopuszczalne, metryka wymaga źródła. |
| Urn | Tożsamość skilla | Pełna wartość, kopiowanie i komunikat sukcesu/błędu. |
| SkillContent | Skill i porównanie propozycji | Semantyczny Markdown bez raw HTML; surowy plik jest osobnym odczytem. |
| Field | Filtry, feedback i decyzje | Jawna etykieta, hint/error oraz aria-describedby; poprawność kontrolki sprawdza kontrakt a11y. |

Formularz decyzji, lifecycle, eksport, filtry, auth i wybór źródła zostają w routes/data. Nie tworzymy GateList, StageTrace, PromotionRoute ani CommandPalette bez zadania U4.
Każdy komponent ma index.tsx, CSS Module, test i story. Drugi wariant wymaga pisemnego powodu; piętnasty komponent wymaga ograniczenia zakresu lub jawnej zmiany decyzji.

## 5. Plan frontendu
Kanoniczny plan portu: [07-frontend](pipeline/07-frontend.md), 2026-09-06; dwie rundy Owner/Principal/Architekt zakończone, 0 otwartych P1/P2. Ta sekcja podaje granice, nie drugą listę zadań.

| Obszar | Decyzja |
|---|---|
| Stack | React 19.2.8, TypeScript 7.0.2, Vite 8.2.2, Router DOM 7.18.3; CSS Modules bez biblioteki komponentów. Node22.14/pnpm10.30, wersjonowane lockfile. |
| ui/ | src/tokens, components≤14, routes/app, domain/data, przyszła warstwa api, test/e2e/qa. Formularze i lifecycle nie są komponentami biblioteki. |
| Dane | Fixture i API mają oddzielne adaptery do jednego kontraktu; typy OpenAPI i dekodowanie runtime. Produkcja pobiera summary/cursor i osobne facets/lookup; body dopiero w szczególe. Pełny klucz query/zasobu i numer żądania blokują starsze odpowiedzi. |
| Backend | Modularne Go API i osobny worker, Postgres/GCS, WorkOS przez Go. Brak mikroserwisów na widok i dodatkowego Nest BFF. |
| Sesja | Cookie HttpOnly/Secure, CSRF i membership per request; bez sekretów w JS. Potwierdzenie ważne maks.45 s, odnowienie co25 s; brak odnowienia zasłania dane. Wznowienie karty wymaga sprawdzenia. Odwołanie≤60 s ma test przy bezczynnym widoku/ciepłym cache. |
| Offline/degraded | Publiczny fixture lokalnie. Prywatny snapshot tylko w RAM i po świeżym potwierdzeniu dostępu; brak łączności do auth zasłania dane. 401/403/logout/zmiana org czyści cache i szkice. |
| Mutacje | Idempotency key + expected revision; 409 wymaga ponownego review. Bez optymistycznego published i bez automatycznej duplikacji zapisu po timeout. |
| Stany | Macierz siedem tras × empty/loading/partial/error/degraded/restricted w 07; restricted ma pierwszeństwo. |
| Budżet | U4 AC2: 10k, p95≤2s w realnej sieci; docelowo strona50 summary, lazy map/body i limity renderu. Dodatkowe budżety są jawnymi założeniami. |
| Kontrole | Vitest5/Testing Library, Playwright owner flow wyłącznie klawiaturą, poprawny Git host/plik/commit i izolacja org, axe w CI, niezależny pixel diff. Pilot AC5 wymaga prawdziwych ludzi. |

Etap 8 dostarcza F1–F9 jako wydzielony frontend na fixture; integracja Go/auth/worker i produkcyjny test Git mają własne zależności. F1–F21 w 07 to małe kroki frontendu, nie estymacja całego backendu.
Hi-fi pozostaje niezależnym renderem sprzed ekstrakcji. Galeria jest narzędziem developerskim poza nawigacją U4; jej baseline nie może importować komponentów ui.
ui/ jest oddzielne od skills/guidefold; frontend nie trafia do paczki konsumenckiego skilla. Plan nie dodaje komend guidefold ui/import/login/install do istniejącego CLI.

## 6. Weryfikacja

Build sprawdza TypeScript i pakowanie aplikacji. Nie potwierdza a11y, czytelności, SLA, autoryzacji ani wartości produktu.
Etap 6 zamknął P3 z symulacji: semantyczny Markdown, dokładny surowy plik i skok klawiaturą ustawiający focus na decyzji; dowód s06-flow.json.
Decyzje do prawdziwego pilota dotyczą potrzeb i pracy, nie wyboru motywu: rozumienie źródła/scope, granica eksport/published/loaded, sens mapy oraz koszt powrotu do Git. Progi i pytania: [03](pipeline/03-survey.md), [05](pipeline/05-simulation.md).
