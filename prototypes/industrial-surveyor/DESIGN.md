# Guidefold — Industrial Surveyor

## Status i źródło prawdy

Ten prototyp rozwija wariant **Industrial Surveyor**, wybrany jako opcja 6 z serii eksploracji złożonej mapy. Wizualnym źródłem prawdy jest `design-reference/source-industrial-surveyor.png`. Implementacja nie kopiuje całej planszy jako bitmapy: osobne assety odpowiadają za charakter marki, a tekst, dane, komponenty i interakcje pozostają natywnym HTML-em.

## Idea systemu

Guidefold nie jest kolejnym katalogiem dokumentów. To centrum operacyjne, które prowadzi sprawdzoną wiedzę przez trzy warstwy organizacji:

1. **Team** — źródło praktyki i właściciel propozycji.
2. **Division** — walidacja, ujednolicenie i kontrola wpływu.
3. **Company standard** — aktywacja zaufanego standardu dla całej firmy.

Metafora mapy ma dwa zadania. Pokazuje, że wiedza ma pochodzenie i historię, a zarazem komunikuje bezpieczną trasę promocji. Interfejs powinien kojarzyć się z systemem kontroli infrastruktury, nie z futurystycznym kokpitem.

## Logo

Znak to litera **G** zbudowana z jednej złożonej mapy technicznej. Jasne płaszczyzny papieru kontrastują z ciemnym interfejsem, a pomarańczowa trasa wskazuje ruch od źródła do standardu.

Zasady użycia:

- zachować czysty, czytelny kontur oraz duże światło wewnątrz litery;
- pomarańczowej trasy używać tylko w głównym znaku, nie jako dekoracji w każdym komponencie;
- minimalna zalecana wielkość: 32 px w interfejsie, 20 px wyłącznie dla prostego faviconu;
- nie rozciągać, nie obracać i nie dodawać poświaty;
- na ciemnym tle używać wersji jasnej, na jasnym — wariantu monochromatycznego.

Plik: `public/assets/industrial-surveyor/guidefold-mark.png` — PNG 1024×1024 z przezroczystością.

## Kolor

| Token | Wartość | Rola |
|---|---:|---|
| `--graphite-950` | `#081014` | tło aplikacji |
| `--graphite-900` | `#0F1418` | główna powierzchnia paneli |
| `--graphite-800` | `#162126` | powierzchnia interaktywna |
| `--stone-100` | `#E6E8EA` | tekst i ikony o wysokim kontraście |
| `--stone-300` | `#AEB8BE` | tekst wspierający |
| `--steel` | `#677681` | opisy, metadane, stan neutralny |
| `--survey-teal` | `#2BA6A0` | zdrowy system, walidacja, aktywna nawigacja |
| `--safety-orange` | `#FF6A28` | decyzja, review, akcja główna |
| `--warning` | `#EFAD3F` | ostrzeżenie i etap probationary |
| `--signal-red` | `#E24A4A` | błąd blokujący lub odrzucenie |

Teal i orange nie są równorzędnymi akcentami. Teal opisuje system, orange wymaga decyzji człowieka. Czerwony nie może pełnić funkcji dekoracyjnej.

## Typografia

- **Barlow Condensed 500–700** — nagłówki operacyjne, etykiety sekcji i dane o charakterze telemetrycznym.
- **Inter 400–600** — tekst interfejsu, formularze, tabele i opisy.
- Treść podstawowa: 14–16 px w produkcie; drobniejsze rozmiary są zarezerwowane dla metadanych o wysokim kontraście.
- Nagłówki są zwarte i zapisywane kapitalikami, ale treść oraz etykiety akcji pozostają w naturalnej pisowni.
- Maksymalnie dwie rodziny fontów na ekranie.

Fonty są bundlowane lokalnie przez pakiety `@fontsource`, więc prototyp nie zależy od zewnętrznego CDN.

## Siatka i gęstość

- bazowa jednostka odstępu: **8 px**;
- typowe wartości: 8, 16, 24, 32, 48, 64 px;
- panele mają kwadratowe narożniki i obrys 1 px;
- cień jest używany tylko dla modala; hierarchię budują przede wszystkim odstęp, typografia i linie;
- docelowa gęstość pulpitu: **Balanced / 40 px** dla wiersza danych;
- minimalny interaktywny cel dotykowy w widoku mobilnym: 44 px.

## Architektura ekranu

### Brand rail

Stały lewy panel pokazuje znak, paletę, typografię i gęstość. W produkcyjnym panelu administratora może zostać uproszczony do nawigacji; tutaj pełni również rolę żywej dokumentacji design systemu.

### Operational route monitor

Główny ekran koncentruje się na jednym zadaniu: ocenie i zatwierdzeniu promocji. Trasa team → division → company znajduje się nad szczegółami, bo najpierw odpowiada na pytanie „gdzie jest ta wiedza?”, a dopiero potem „co zawiera?”.

### CI / Governance gates

Panel po prawej łączy kontrolę automatyczną i decyzje ludzi. Kolejność jest stała: schema, jakość, policy, security, executive approval. Status jest komunikowany kolorem i tekstem; kolor nigdy nie jest jedynym nośnikiem informacji.

### Component bay

Oddzielny widok zawiera produkcyjne stany przycisków, formularzy, badge’y, alertów, toggle’a i tabeli. Komponenty zachowują ten sam zestaw tokenów co ekran główny.

### Asset library

Oddzielny widok prezentuje i pozwala pobrać trzy assety rastrowe. Asset nie może zawierać interaktywnego tekstu ani metryk, ponieważ utrudniałoby to responsywność i lokalizację.

## Assety

| Plik | Rozdzielczość projektowa | Zastosowanie |
|---|---:|---|
| `guidefold-mark.png` | 1024×1024 | logo, znak nawigacji, app icon |
| `topographic-route-bg.png` | 2048×1024 | tło monitora trasy |
| `survey-grid-pattern.png` | 1254×1254 | subtelny pattern tła i powierzchni |

Assety zostały wygenerowane jako osobne pliki HQ i sprawdzone w pełnej rozdzielczości. Nie zawierają losowego tekstu ani elementów interfejsu. Cała semantyka produktu jest renderowana w HTML, a ikony pochodzą z biblioteki Phosphor.

## Interakcje prototypu

- przełączanie między **Route monitor**, **Component bay** i **Asset library**;
- filtrowanie kolejki promocji po nazwie, zespole i dywizji;
- interaktywny wybór gęstości w brand railu;
- toggle w katalogu komponentów;
- kopiowanie podstawowych tokenów kolorystycznych;
- modal potwierdzający promocję;
- przejście do stanu „Approved” z komunikatem aktywacji i zmianą lifecycle;
- pobieranie osobnych assetów z Asset library.

## Dostępność

- ikony interaktywne mają etykiety `aria-label`;
- focus ring używa safety orange i jest widoczny na ciemnym tle;
- statusy mają tekst, nie tylko kolor;
- formularze mają jawne etykiety;
- elementy natywne zachowują obsługę klawiatury;
- responsywny układ przechodzi z trzech kolumn do jednej, bez ukrywania akcji głównej.

## Reguła jakości

Nie używać pełnej planszy koncepcyjnej jako tła aplikacji. Nie odtwarzać logo ani mapy z przypadkowych `div`-ów. Nie nakładać tekstu na raster, jeżeli ma być interaktywny lub lokalizowany. Każdy nowy asset musi zostać sprawdzony w 100% powiększenia pod kątem poszarpanych krawędzi, halo, fałszywego tekstu i niespójnych linii.

## Mapa implementacji

- `src/App.jsx` — widoki, komponenty i interakcje;
- `src/styles.css` — tokeny, layout, stany i responsywność;
- `public/assets/industrial-surveyor/` — assety wizualne;
- `design-reference/` — źródłowa plansza i wycinki użyte do generacji assetów;
- `design-qa.md` — wynik końcowego porównania wizualnego.
