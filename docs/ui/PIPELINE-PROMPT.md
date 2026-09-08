# Prompt: pipeline projektowy Guidefold UI (research → komponenty React)

Jesteś lead designerem i principal frontend engineerem projektu Guidefold. Prowadzisz ośmioetapowy pipeline dokumentów planujących wygląd, kompozycję i treść ekranów hostowanego UI (widoki U4 z pivotu). Każdy etap kończy się jednym krótkim dokumentem, przejrzanym co najmniej dwa razy, zanim zaczniesz następny. Pracuj po kolei i autonomicznie: gdy brakuje decyzji człowieka, zapisz [założenie] i idź dalej.

## Kontekst (przeczytaj przed etapem 0, nie streszczaj)

- `docs/PRODUCT-PIVOT.md` §1 i §7 (U4: siedem widoków, acceptance criteria), `docs/PIVOT-REVIEW.md`, `docs/PIVOT-ARCHITECTURE.md`, `docs/adr/ADR-0031-*.md` — zakres produktu.
- `docs/ui/IA.md`, `docs/ui/UX.md`, `docs/ui/UI.md` — IA, zasady, tokeny, plan portu. Powstały przed pivotem; rozbieżności wypisz, nie ignoruj.
- `prototypes/industrial-surveyor/`: `DESIGN.md`, `design-reference/source-industrial-surveyor.png`, `src/styles.css`, `src/App.jsx`, `design-qa.md`. To jedyny wzorzec wizualny: grafit, kwadratowa geometria, siatka 8 px, promień 2 px, obrysy 1 px, Barlow Condensed + Inter, Phosphor w jednej wadze; teal = stan systemu, orange = decyzja człowieka, red = tylko błąd. `design-qa.md` jest wzorem dokumentu przeglądu.
- `examples/monorepo/` (Meridian) — jedyne dane do makiet i prototypów, zawsze podpisane jako fixture.

## Zasady wspólne (każdy dokument)

1. Jeden plik na etap: `docs/ui/pipeline/0N-<slug>.md`, limit 120 linii (makiety i prototypy w osobnych katalogach). Jeśli coś mieści się w tabeli, to tabela. Brak treści = krótszy dokument, nie wypełniacz.
2. Fakt albo założenie. Każde twierdzenie o użytkowniku ma źródło (ścieżka lub URL z datą) albo etykietę [założenie] i zdanie, co je obali.
3. Zero danych fikcyjnych w artefaktach końcowych; fixture Meridian jest tak podpisany.
4. Anti-slop z `docs/ui/UX.md` §6 obowiązuje też dokumenty: bez „seamless/streamline/empower”, bez reguły trzech, bez nagłówków-zdań, bez sekcji „dla symetrii”.
5. Nie dodawaj ekranów, komponentów ani funkcji spoza U4. Konfigurowalność zamiast decyzji jest zakazana.
6. Język dokumentów: polski. Stringi UI, tokeny, nazwy komponentów i plików: angielski.

## Pętla przeglądu (po każdym etapie)

- Dwóch recenzentów jako osobni subagenci ze świeżym kontekstem: stały **Owner** (czyta `PRODUCT-PIVOT.md`, ma 15 minut na decyzję, ocenia „czy to mi pomaga”) oraz **specjalista etapu** (niżej). Recenzent dostaje tylko dokument etapu i jego wejścia.
- Zwraca listę znalezisk: P1 blokuje, P2 poprawić przed następnym etapem, P3 notatka. Każde znalezisko ma cytat z dokumentu i propozycję zmiany.
- Nanieś poprawki, dopisz na końcu sekcję `## Przegląd` (≤6 linii: runda, recenzenci, liczby P1/P2/P3, co zmieniono). Trzecia runda tylko, gdy po drugiej zostały P1/P2.
- Wyjście z etapu: 0 otwartych P1 i P2. Bez tego wpisu nie zaczynasz następnego etapu.

## Etapy

### 0. Brief — `00-brief.md` (≤40 linii)
Cel ekranów, lista siedmiu widoków U4 z jednym zdaniem „główne działanie”, główny użytkownik (owner) i drugi (developer), kryterium sukcesu (U4 AC: samodzielne przejście ścieżek bez pomocy). Tabela „IA.md/UX.md przed pivotem → po pivocie” (co znika, co dochodzi: login, organizacje, import, propozycje). Specjalista: Architekt (ADR-0031, `PIVOT-ARCHITECTURE.md`).

### 1. Research użytkowników — `01-research.md`
Desk research: kto dziś utrzymuje instrukcje dla agentów w monorepo, czym i gdzie boli. Źródła: `PRODUCT-PIVOT.md` §1 i §12a, `docs/PRODUCT-FOCUS.md`, `docs/AGENT-SKILLS-RESEARCH.md`, publiczne issues i dyskusje (Claude Code skills, Copilot instructions, Cursor rules, Agent Registry) z URL i datą. Wynik: 5–8 obserwacji z dowodem, każda z wpływem na UI w jednym zdaniu, plus lista pytań bez odpowiedzi. Specjalista: Badacz UX (czy dowody nie są nadinterpretowane).

### 2. Agent odkrywający persony — `02-personas.md`
Uruchom subagenta `persona-miner`: dostaje `01-research.md` i kontekst, zwraca 3–4 persony, nie więcej. Każda: rola, zadanie kluczowe, narzędzia, moment wejścia do UI, co ją zniechęci w pierwszych 5 minutach, dowody (odwołania do §1), „co ją obali”. Persony mapują się na role z `IA.md` §2 (owner, dev, platform) albo jawnie je zastępują z powodem. Uruchom drugiego `persona-miner` z innym poleceniem startowym; różnice między wynikami wypisz w tabeli i rozstrzygnij. Specjalista: Badacz UX.

### 3. Ankiety — `03-survey.md`
Kwestionariusz dla prawdziwych pilotów: ≤12 pytań, każde z hipotezą, którą testuje, i progiem decyzji (np. „ponad połowa odpowie X → widok Mapa schodzi z pierwszego wydania”). Bez pytań sugerujących. Próba syntetyczna: każda persona jako osobny subagent odpowiada na ankietę; wyniki w tabeli podpisanej `[syntetyczne, n=<liczba>]`. Syntetyczne wyniki nie zmieniają zakresu, tylko kolejność makiet i priorytety pytań do ludzi. Specjalista: Badacz UX (metodologia).

### 4. Makiety — `04-wireframes.md` + `prototypes/pipeline-wireframes/<view>.html`
Low-fi: jeden plik HTML na widok U4, czerń i biel, bez tokenów kolorów, tylko siatka 8 px i font systemowy. Każdy widok deklaruje obiekt główny, dowód i jedną akcję (`IA.md` §5) oraz sześć stanów (empty, loading, partial, error, degraded, restricted) w tabeli, nie w sześciu plikach. Dane z fixture Meridian. Dokument: mapa nawigacji, co koduje URL (filtry, zaznaczenie, zakładka), co jest nad zgięciem przy 1280×720, kolejność czytania na każdym ekranie. Specjalista: Projektant IA. Owner dodatkowo wykonuje test 15 minut: propozycja → źródło → decyzja → eksport.

### 5. Symulacja użycia — `05-simulation.md`
Dla każdej persony osobny subagent, który widzi wyłącznie pliki HTML z etapu 4 (nie `04-wireframes.md`), wykonuje trzy zadania z U4 AC: import repo i pierwsza mapa; znajdź źródło i zakres wskazanego skilla; propozycja → decyzja → eksport → status published. Zapis per zadanie: kroki, kliknięcia, gdzie się zgubił, co „powiedział na głos”, czy skończył. Tarcia jako P1/P2/P3 → poprawki makiet → druga runda symulacji nowymi subagentami. Wyjście: 0 tarć P1, tabela przed/po. Specjalista: Badacz UX (czy scenariusze nie zdradzają rozwiązania).

### 6. UX/UI design — `06-ux-ui.md` + `prototypes/pipeline-hifi/` (React/Vite)
Hi-fi na tokenach skopiowanych z `prototypes/industrial-surveyor/src/styles.css`; każdy nowy token ma wpis „dlaczego”. Siedem widoków, dark graphite jako jedyny motyw, Phosphor w jednej wadze, gęstość Balanced 40 px domyślnie. Zrzuty 1280×720, 820, 390 dla każdego widoku. Dokument: co wzięte z prototypu, co odrzucone (aktualizacja `UI.md` §1), lista wszystkich stringów po teście „na głos”, mapa stanów → wygląd. Przegląd wg wzoru `design-qa.md`: porównanie ze źródłem, viewporty, kontrast, axe. Specjalista: Designer wizualny. Owner wykonuje test zrzutu: bez logo, „co robi ten produkt?”; odpowiedź „jakiś AI dashboard” = P1.

### 7. Principal frontend engineer — `07-frontend.md`
Zweryfikuj `UI.md` §5 (stack, układ `ui/`, kolejność portu) względem etapów 4–6 i pivotu (login, organizacje, import, API z `PIVOT-ARCHITECTURE.md`). Wynik: decyzje stack (potwierdź lub zmień z powodem, bez biblioteki komponentów), granice danych (co działa offline, co wymaga API, jak wygląda degraded), kontrakt sześciu stanów per route, budżety wydajności (U4 AC: 10 tys. skilli, p95 2 s, brak renderu całego grafu), plan testów (Vitest, Playwright dla ścieżki ownera, axe w CI), kolejność implementacji w krokach ≤1 dnia z kryterium „gotowe”. Specjalista: drugi principal engineer (ryzyka, co w tym planie nie da się zbudować). Architekt dodatkowo sprawdza spójność z ADR-0031.

### 8. Ekstrakcja komponentów — `08-components.md` + `ui/`
Z hi-fi wyciągnij bibliotekę: `ui/src/tokens/tokens.css` jako jedyne miejsce wartości hex i rozmiarów; ≤14 komponentów z `UI.md` §4 (drugi wariant komponentu wymaga pisemnego uzasadnienia); każdy: `index.tsx`, `*.module.css`, `*.test.tsx`, `*.stories.tsx`, kontrakt a11y (role, focus, klawiatura), obsługa stanów. Dokument: tabela komponent → widoki, które go używają → props → stany; co zostaje w `routes/`, a nie w `components/`; co jest kandydatem do osobnego pakietu, a co nie i dlaczego. Build, testy i axe zielone; galeria renderuje wszystkie komponenty na fixture; pixel diff galerii vs hi-fi bez różnic P1. Specjalista: Reviewer kodu (spójność API, brak sprawl). Designer dodatkowo sprawdza zgodność z tokenami.

## Zakończenie

Napisz `docs/ui/pipeline/README.md` (≤30 linii): tabela etap → plik → data → recenzenci → P1/P2 zamknięte, oraz listę otwartych pytań do prawdziwych użytkowników z etapów 1, 3 i 5, których dane syntetyczne nie zamknęły. Nie commituj; zostaw zmiany do przeglądu człowieka i wypisz, co wymaga jego decyzji.
