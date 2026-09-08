# 8. Biblioteka komponentów
Status: etap zamknięty po dwóch rundach, 2026-09-06; testy komponentów/build, axe, 42 stany i 42 porównania obrazu zaliczone.
Cel: wydzielenie React do ui/ bez zmiany zatwierdzonego wyglądu. Wejścia: [UI §4](../UI.md), [06](06-ux-ui.md), [07](07-frontend.md), [reguły](../../DOCUMENTATION-RULES.md).
Zakres zastępowania: ui/ jest bieżącą implementacją fixture; pipeline-hifi pozostaje zamrożonym odniesieniem, nie drugim miejscem edycji.

## Układ i kontrakty
[ui/src/components](../../../ui/src/components/) zawiera dokładnie 14 eksportów. Każdy katalog ma index.tsx, nazwany CSS Module, .test.tsx oraz standardowy plik CSF .stories.tsx.
[Shared.tsx](../../../ui/src/Shared.tsx) tylko reeksportuje. [Galeria /__components](http://127.0.0.1:4331/__components) renderuje wszystkie 14 na tych samych props i Meridian fixture co zamrożona galeria hi-fi.
Stories opisują scenariusze komponentu; galeria porównawcza ma stały zestaw props i nie wymaga osobnego runtime Storybook. Nie jest ósmą stroną produktu.
Kontrolki dostają stan od trasy; komponent nie pobiera danych, nie autoryzuje ani nie udaje opublikowania rewizji. Nie tworzymy sześciu pustych wariantów każdego komponentu.

| Komponent → widoki | Props / stany | Kontrakt dostępności i zachowania |
|---|---|---|
| ActionButton → wszystkie | children, tone neutral/system/human, href albo button props, disabled | Natywny button lub link, domyślnie type=button. Disabled link bez href i poza Tab; nie prowadzi także przez menu kontekstowe. |
| BrandMark → shell | bez props/odmian | Oryginalny raster z alt, tekst nazwy; brak dodatkowej dekoracji SVG. |
| Panel → wszystkie | title, eyebrow?, icon?, action?, children, id?, className? | Section nazwana przez unikalne h2; dekoracyjna ikona aria-hidden. |
| StateBadge → wszystkie | children, tone neutral/system/human/warning/error | Tekst zawsze określa stan; kolor tylko wspiera. Unknown nie jest success. |
| RouteState → wszystkie | state, title, description, action? | aria-live polite; loading aria-busy i ukryty przed AT szkielet. Akcja zależy od dostępności konkretnej trasy. |
| Tabs → Map, Skill, Organization | label, current, items id/label/href | Nav z nazwą i aria-current=page; zwykłe linki obsługiwane Tab/Enter, bez fałszywego tablist. |
| ProvenanceTrail → Import, Skill, Proposals, Organization | entries label/value/detail?/href?/code? | Semantyczne dt/dd; pełny tekst źródła, link Git z bezpiecznym rel. |
| ScopeTree → Map | nodes, selected?, label | Natywne details/summary i linki; wybrany liść otwiera przodków, aria-current; Enter/Space oraz Tab. |
| DataTable → Import, Library, Map, Skill, Organization | caption, headings, children, className? | Caption, th scope=col; wierszowe th dostarcza trasa. Nazwany focusowalny region scroll, strzałki przewijają szeroką tabelę. |
| SkillDiff → Proposals | source, candidate | Bez zmian: jawny komunikat. Zmiany mają opis Added/Removed i znak, nie sam kolor. Źródło nie jest mutowane. |
| MetricRow → Import, Library, Map, Proposals, Usage | items label/value/detail | Dt/dd, nazwa i kontekst obok wartości; Unknown zachowane jako brak dowodu. |
| Urn → Skill, Proposals | value | Pełny identyfikator, nazwany button kopiowania; role=status po sukcesie i błędzie, brak fałszywego sukcesu clipboard. |
| SkillContent → Skill, Proposals | content | Semantyczny Markdown, bez raw HTML i zdalnych obrazów; focusowalne bloki kodu, linki z rel. Dokładny plik jest osobnym odczytem. |
| Field → Import, Library, Skill, Proposals, Usage, Organization | id, label, hint?, error?, pojedyncza kontrolka children | Łączy label/id, hint/error i istniejące aria-describedby; błąd ustawia aria-invalid i alert. |

Trzy tony ActionButton mają uzasadnienie: neutralna czynność, przejście systemowe, decyzja człowieka. Usunięto niewykorzystane warning/error z API przycisku; pozostają na StateBadge, bo stan ostrzeżenia i błąd są różnymi komunikatami.
RouteState obsługuje sześć kontraktów tras z 07; nie dodaje rozmiarów, motywów ani przełącznika gęstości. Piętnasty komponent albo kolejny wariant wymaga zadania U4 i pisemnego powodu.

## Kandydaci do osobnego pakietu
ActionButton, Panel, StateBadge, RouteState, Tabs, Field, DataTable i MetricRow mogą być kandydatami do wspólnego pakietu UI, gdy drugi rzeczywisty konsument potwierdzi zgodne kontrakty. Dziś pozostają w ui/; sam ponowny import nie uzasadnia publikacji pakietu.
BrandMark pozostaje przy marce. Urn, ProvenanceTrail, ScopeTree, SkillContent i SkillDiff opisują odczyt instrukcji/źródeł Guidefold; ewentualny pakiet domenowy wymaga drugiego konsumenta i jawnych zależności Router/Markdown/typy, a nie sztucznej uniwersalizacji.
Routes, fixture adapter, formularz decyzji, lifecycle, sesja i eksport nie są kandydatami do biblioteki prezentacyjnej: zależą od konkretnego workflow i przyszłego Go API.

## Granica tras i danych
[app.tsx](../../../ui/src/app.tsx) składa siedem tras i stany; formularze, feedback, lifecycle, eksport i symulacja Git są w routes/. RouteErrorBoundary jest lokalną obsługą błędu trasy, nie elementem biblioteki.
Błąd modułu pokazuje Reload view i zachowuje szkic publicznego fixture w bieżącej sesji. Publikacja/eksport nie zmieniają się optymistycznie.
[data.ts](../../../ui/src/data.ts) tworzy wstrzykiwany FixtureAdapter bez importu JSON. [data/meridian.ts](../../../ui/src/data/meridian.ts) składa publiczny fixture w main; komponenty i czyste domain/diff, domain/skill nie zależą od danych demonstracyjnych.
To adapter fixture, nie deklaracja zaimplementowanego OpenAPI ani adaptera sieciowego. F10–F21 z 07 pozostają zależne od Go/auth/worker, testowego Git i pilota.
Publiczna symulacja zapisuje szkic w sessionStorage pod guidefold-ui-meridian-v1. Produkcyjnych prywatnych danych nie wolno podłączyć do tego magazynu; obowiązują RAM/cache/revocation z 07.
Eksport jest dokładnym SKILL.md, nie pakietem closure 1.2. Simulate Git sync oznacza lokalny scenariusz; nie wywołuje GitHub ani rzeczywistego sync.

## Tokeny i niezależne porównanie
Jedyny plik wartości w ui/src: [tokens/tokens.css](../../../ui/src/tokens/tokens.css); moduły używają var(). Hi-fi ma własny niezmieniany arkusz sprzed ekstrakcji.
Dodany przed freeze --gallery-width=1040px ogranicza długość wiersza wyłącznie developerskiej galerii; nie zmienia siedmiu widoków. --transparent nazywa bezbarwny obrys nawigacji, bez zmiany renderu; łącznie 103 tokeny. Pozostałe tokeny i ich uzasadnienia: [06](06-ux-ui.md).
[Manifest bazowy](../../../prototypes/pipeline-hifi/qa/baseline/manifest.json) zapisano przed utworzeniem ui/: SHA źródeł, assetów i 42 obrazów (14 × 1280/820/390, wysokość viewportu 720). To osobny render hi-fi, bez importów ui/.
[compare-gallery.mjs](../../../ui/qa/compare-gallery.mjs) najpierw weryfikuje SHA referencji. Porównuje rozmiar i wszystkie piksele z includeAA=true, threshold=0.05, wymagając 0 zmienionych pikseli; raport [pixel-diff.json](../../../ui/qa/pixel-diff.json).
42/42 porównania przeszły 2026-09-06 w Chromium153, Ubuntu24.04/WSL, Node22.14.0. Baseline nie wolno nadpisać, aby zaakceptować regresję; generator odmawia ponownego freeze.
Porównanie galerii nie zastępuje zrzutów pełnych widoków, oceny copy ani pilota. Pełne widoki i wzorzec marki oceniono w 06; ekstrakcję sprawdzamy dodatkowo na działających trasach.

## Sprawdzenia
Komendy z ui/: pnpm install --frozen-lockfile; pnpm build; pnpm test; pnpm test:contracts; pnpm test:e2e. Dla pnpm test:flow i pnpm test:visual uruchom wcześniej pnpm dev na 127.0.0.1:4331.
| Kontrola / dowód | Wynik i granica |
|---|---|
| TypeScript + Vite build | PASS; główny chunk fixture około 640 kB / 173 kB gzip. Ostrzeżenie >500 kB jest jawne; brak dowodu budżetu produkcji i datasetu 10k. |
| Vitest / 15 plików | 45/45 PASS: klawiatura, disabled, linki, semantyka, clipboard, Markdown, diff i etykiety. Nie są to testy autoryzacji Go. |
| [Owner keyboard](../../../ui/e2e/owner-keyboard.spec.ts) | PASS: login→org→import→lista→review→dokładny eksport→lokalny Git→Usage wyłącznie Tab/Enter/Space. Dokładny host/plik/commit źródła. |
| [Owner flow](../../../ui/qa/owner-flow.json) | 9/9 PASS, 0 błędów JS; edycja i 5540 bajtów eksportu z SHA d3e3c917…; member/restricted i brak podmiany rewizji. |
| [Axe](../../../ui/e2e/accessibility.spec.ts) | PASS: 7 widoków i galeria w 3 szerokościach oraz ujawniona treść propozycji/menu; 0 naruszeń wskazanych reguł WCAG A/AA i overflow. |
| [Sześć stanów](../../../ui/e2e/states.spec.ts) | 42/42 PASS: axe i brak overflow, blokada zmian oraz brak treści restricted. |
| [Struktura i tokeny](../../../ui/qa/contracts.json) | PASS: 14 kompletów, 103 tokeny, 21 CSS, brak zależności komponentów/domain od fixture i nierozwiązanych var(). |
| Niezależny pixel diff | 42/42 PASS; nie regenerowano referencji z kodu ui. |

[Workflow CI](../../../.github/workflows/ui.yml) powtarza install/build/Vitest/Playwright/axe/owner-flow/pixel diff na Ubuntu24.04 i publikuje raporty. Lokalnie uruchomiono komendy; workflow nie był jeszcze wykonany na GitHubie.
[README ui](../../../ui/README.md) podaje uruchomienie i zakres; reguły dalszych zmian: [AGENTS](../../../AGENTS.md) i [skill UI](../../../.agents/skills/guidefold-ui-workflow/SKILL.md).
Audyt przed R1 poprawił komunikat kopiowania po zmianie URN i dwa bezbarwne obrysy przeniesione do tokenu; dodano regresję późnego clipboard. R1 poprawia nieznane filtry URL (wartość i błąd pozostają widoczne, brak fałszywego zera) oraz ponowne otwarcie gałęzi dla nowego wyboru; normalny render galerii jest niezmieniony.
Nowe copy sprawdzone w kontekście przez odczyt tekstu: „Unavailable: {value}”, „This filter value is unavailable in this fixture. Choose a value or clear filters.”, „Filter unavailable”, „Resolve unavailable filters before reading the result count.” i „Choose an available value or clear filters. The requested value remains in the URL.”; tekst wskazuje problem, nie obiecuje wyników.
F1–F9 mają odebraną implementację fixture; nie zaliczamy U4 AC2/AC5, prawdziwego logowania, synchronizacji Git, revocation≤60s ani wartości biznesowej.
Pozostawione narzędzia i historyczne pomocniki: [pipeline-tools](../../../prototypes/pipeline-tools/README.md). Kontrakt bieżącego UI stanowi ten dokument i kod, nie archiwalne notatki koordynacyjne.
## Przegląd
R1 — Owner 0/0/0; Code reviewer P1=0/P2=1/P3=1; Designer 0/0/0. Poprawiono nieznane filtry i otwieranie wybranej gałęzi.
R2 — Owner, Code reviewer i Designer: każdy P1=0/P2=0/P3=0; niezależne kontrole przeglądarkowe potwierdzają poprawki.
Wyjście: 0 otwartych P1/P2/P3. F1–F9 odebrane jako fixture; bez zaliczenia integracji produkcyjnej ani pilota.
