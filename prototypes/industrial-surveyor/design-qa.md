# Design QA — Industrial Surveyor

## Final result: passed

Data przeglądu: 2026-09-04  
Źródło wizualne: `design-reference/source-industrial-surveyor.png` (1488×1056)  
Implementacja: `src/App.jsx` + `src/styles.css`  
Stan porównania: initial review / Customer Onboarding Checklist  
Przeglądarka: Codex In-app Browser

## Porównanie źródło ↔ implementacja

Plansza referencyjna i działający prototyp zostały umieszczone w jednym widoku porównawczym. Obie powierzchnie były renderowane jako ramy 1488×1056 i skalowane identycznie, dzięki czemu można było ocenić proporcje brand railu, hierarchię route monitora, panel governance, detale i gęstość danych bez mieszania viewportów.

Zachowane cechy kierunku:

- ciemny, techniczny charakter mapy geodezyjnej;
- znak G złożony z mapy i pomarańczowej trasy;
- lewy brand rail jako żywa dokumentacja systemu;
- jasna hierarchia team → division → company standard;
- osobny panel CI / Governance gates i wyraźna akcja approval;
- Barlow Condensed dla warstwy operacyjnej oraz Inter dla danych;
- kwadratowe panele, cienkie obrysy, brak miękkich kart i ozdobnych gradientów.

Celowo rozszerzono planszę o działające stany produktu: kolejkę promocji, wyszukiwanie, widok komponentów, bibliotekę assetów, modal oraz sukces po akceptacji. Te różnice są funkcjonalnym rozwinięciem kierunku, nie zmianą języka wizualnego.

## Obowiązkowe obszary QA

### Typografia

Bundlowane lokalnie fonty Barlow Condensed 500/600/700 i Inter 400/500/600 ładują się bez zależności od CDN. Hierarchia nagłówków odpowiada industrialnemu charakterowi referencji; interfejs i dane zachowują neutralny krój oraz czytelne odstępy. Nie wykryto uciętych nagłówków ani tekstu nachodzącego na inne elementy.

### Layout i spacing

Desktop zachowuje relację stałego brand railu do obszaru roboczego i zestawia monitor trasy z węższym panelem governance. Siatka 8 px, kwadratowe narożniki, 1 px obrysy oraz zwarte wiersze danych są spójne z referencją. Sekcje poniżej pierwszego viewportu rozwijają produkt, ale nie zaburzają hierarchii ekranu głównego.

### Viewport resilience

Sprawdzono:

- desktop 1280×720 oraz porównanie w ramie 1488×1056;
- tablet 820 px;
- mobile 390 px.

Na pierwszym przebiegu wykryto problem P2: na 390 px zakładki topbara próbowały zmieścić się w tym samym rzędzie co wordmark i akcje, co powodowało poziomy scroll. Poprawiono `src/styles.css`: nawigacja ma osobny rząd `flex: 0 0 100%`, a trzy zakładki dzielą dostępną szerokość. Ponowny zrzut potwierdził brak kolizji i zachowanie celu dotykowego 44 px.

### Kolory i tokeny

Tokeny graphite, stone, survey teal, safety orange, steel i signal red mapują role z referencji. Teal opisuje system i walidację; orange jest zarezerwowany dla review oraz decyzji użytkownika; red wyłącznie dla błędów i odrzucenia. Tekst stanów zawsze towarzyszy kolorowi.

### Assety i jakość obrazu

- `guidefold-mark.png`: 1024×1024, 32-bit ARGB, przezroczystość;
- `topographic-route-bg.png`: 2048×1024, 24-bit RGB;
- `survey-grid-pattern.png`: 1254×1254, 24-bit RGB.

Każdy plik został obejrzany w pełnej rozdzielczości. Brak fałszywego tekstu, halo, przypadkowych symboli, poszarpanych krawędzi i artefaktów na łączeniach. Tekst UI pozostaje natywnym HTML-em, a ikony pochodzą z jednego zestawu Phosphor. Nie ma inline SVG, CSS-owego substytutu logo ani rastrowych zrzutów udających interfejs.

### Copy i treść

Dane są realistyczne dla przepływu promocji wiedzy: właściciel, dywizja, wersja, checki, polityki, wpływ i provenance. Główna akcja wyjaśnia rezultat w modalu przed zmianą stanu.

### Interakcje i stany

Zweryfikowano w przeglądarce:

- przełączanie Route monitor / Component bay / Asset library;
- trzy linki pobierania assetów;
- filtrowanie kolejki do jednego wyniku dla zapytania „Vendor”;
- kopiowanie tokenów i stan „Copied”;
- modal approval, stan ładowania oraz końcowy stan „Approved”;
- komunikat sukcesu z zaplanowaną datą aktywacji.

### Dostępność

Interaktywne ikony mają etykiety, formularze używają labeli, modal ma `role="dialog"` oraz `aria-modal`, komunikat sukcesu używa `role="status"`, a focus ring jest widoczny na tle graphite. Główne akcje zachowują praktyczne cele dotykowe w widoku mobilnym.

## Kontrole techniczne

- Vite production build: passed;
- Sites packaging preparation: passed;
- tests: 4/4 passed;
- błędy i ostrzeżenia konsoli aplikacji: 0;
- nierozwiązane P1/P2: 0.

## Historia iteracji

1. Pierwsze porównanie źródła i desktopowej implementacji: układ, fonty, paleta i assety zgodne; brak krytycznych różnic.
2. Test tablet/mobile: wykryty P2 w mobilnym topbarze.
3. Poprawka mobilnej nawigacji i ponowny capture: passed.
4. Pełny test interakcji, build i testy workerów: passed.
