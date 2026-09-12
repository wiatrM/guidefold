# 6. UX/UI
Status: ponownie otwarty i zaktualizowany 2026-09-08 na zlecenie właściciela; QA przeglądarkowe w toku.
Wejścia: [04](04-wireframes.md), [05](05-simulation.md), [pivot U4](../../PRODUCT-PIVOT.md), [Industrial Surveyor](../../../prototypes/industrial-surveyor/DESIGN.md).
Artefakt: [React/Vite hi-fi](../../../prototypes/pipeline-hifi/); [UI §1–4](../UI.md), [UX](../UX.md) zastępują dokumenty sprzed pivotu.

## Zakres
Siedem widoków U4: Import, Library, Map, Skill, Proposals, Usage & quality, Organization. Login i org to kroki Import; Members/Integrations to zakładki Organization.
Dane: wyłącznie podpisany Meridian fixture z examples/monorepo, commit 88e404561a9f6994cd870743bf858b9b0a616126; 27 plików SKILL.md, 17 zadeklarowanych nodes, 125466 B.
To lokalna symulacja: brak OAuth, API, zapisów repo, Git sync i telemetrii adaptera. Eksportuje się dokładny SKILL.md, bez dołączania zasobów referencyjnych. (Zapis etapu hi-fi; ui/ od 2026-09-08 nie ma symulacji i czyta wyłącznie hostowane API, [08](08-components.md).)
Scenariusze ról w URL służą QA; uprawnienia produkcji musi egzekwować API. Dane importu nie są dowodem użyteczności.

## Wzorzec
| Przejęte | Decyzja |
|---|---|
| Graphite, płaskie obrysy, square geometry | Jedyny motyw; radius 2 px, border 1 px, siatka 8 px z połówką 4 px przy etykiecie. |
| Barlow Condensed + Inter | Fonty lokalne; kod/URN/SHA w systemowym monospace; brak dodatkowego fontu marki. |
| Teal / orange / red | System i zaznaczenie / decyzja człowieka / wyłącznie błąd. Rejected jest orange, nie red. |
| Oryginalny znak | Raster znaku zostaje; survey-grid-pattern i każde obrazkowe tło raila usunięto. |
| Balanced 40 px i Phosphor regular | Jedna gęstość; mobilne cele dotykowe 44 px, bez selektora wariantów. |

Odrzucone: historyczny Route monitor, fikcyjne metryki, promocja team→company i Component bay w menu produktu. Plansza źródłowa określa markę, nie dane ani dzisiejszy zakres.

## Zmiana zlecona 2026-09-08
Rozbieżność: ten etap utrwalał Industrial Surveyor jako jedyny wzorzec oraz raster tła raila, a właściciel zlecił pełny redesign i migrację na shadcnspace bez tego tła.
Źródło decyzji: bieżące zlecenie właściciela obejmujące wszystkie strony, składane menu, profil, logout, edycje/revisions, animacje, cienie i Shine Border.
Decyzja: zachować siedem tras, dane, paletę i kontrakty; zmienić shell i receptury wszystkich 15 komponentów na kompozycje shadcnspace/Base UI/Motion opisane w [design brief](../../../ui/qa/navigation-redesign/design-brief.json).
Dokumenty zastępowane lokalnie: ta sekcja wzorca/kompozycji, [IA §4](../IA.md), [UI §1–5](../UI.md), [08](08-components.md); zamrożone prototypy pozostają dowodem historycznym.
Do decyzji właściciela: nie; zakres został podany wprost, a oddzielnej trasy Editions nie dodano, bo historia rewizji już istnieje w Skill/Proposals.
[Inwentarz tokenów](../../../prototypes/pipeline-hifi/qa/token-provenance.json) przypisuje każdemu z 101 tokenów pochodzenie i powód, także 129 deklaracjom z nadpisaniami responsywnymi.
Nowe nazwy grupują wartości typografii, rozmiarów i układu; control-border używa istniejącego steel dla widocznej granicy formularza. Wpisane są również powody mobile/desktop, skip-link, focusu oraz nowych minimalnych szerokości tabeli/kolumn i zwartego układu filtrów.

## Kompozycja
| View | Pierwszy obiekt / następny krok |
|---|---|
| Import | Kroki sign-in→organization→manifest→result; Google/GitHub jawnie jako fixture. |
| Library | Filtry i tabela instrukcji; odczyt konkretnego źródła z zachowaniem filtrów. |
| Map | Repository/Scopes/Pyramid; tekstowe drzewo i typowane requires/refines, Unclassified bez domysłu. |
| Skill | Tożsamość, scope, rewizja, body/source/references/feedback; obca rewizja nie odsłania body jako pasującego. |
| Proposals | Nazwa, Draft i brak obserwacji loaded; skrót do równorzędnych approve/edit/reject oraz źródła. |
| Usage & quality | Unknown i Review queue bez zdarzeń; filtry zachowują skill/scope/revision. |
| Organization | Members albo Integrations; lokalne ćwiczenia nie udają prawdziwego zaproszenia ani tokenu. |

1280×720: rail 216 px i dwie kolumny porównania. 820×720: rail 184 px, główna treść w jednej kolumnie. 390×720: kompaktowe natywne Navigate, zamknięte na wejściu; wszystkie trasy po rozwinięciu.
Library mieści pierwszy pełny wiersz na y661–718 przy 1280×720; przycisk kontynuacji Import na y661–701. Mobilny kontekst zachowuje krótki source commit. [Pomiar](../../../prototypes/pipeline-hifi/qa/s06-fold.json).
Długi Markdown ma semantyczne nagłówki i kod, surowy pełny plik jest osobnym disclosure. Skok klawiaturą dochodzi do decyzji; P3 z etapu 5 zamknięty w regresji s06-flow.
[Inwentarz wszystkich autorskich stringów i czytanie na głos](../../../prototypes/pipeline-hifi/qa/copy-review.json): 683 wystąpienia/szablony, 115 kontekstów dynamicznych, 0 nieprzejrzanych i 0 otwartych uwag; próba redakcyjna syntetyczna, bez głosu i udziału człowieka; treść źródłowych procedur fixture nie podlega przepisywaniu.
Poprawki copy: Add local member, candidate revision zamiast package, Source: Meridian fixture zamiast domniemanego autora; żadna etykieta nie obiecuje wysłanego zaproszenia.

## Stany
| Stan | Wygląd / dostępna praca |
|---|---|
| Empty | Nazwany brak danych + następny krok; No observations nie oznacza 0% skuteczności. |
| Loading | Statyczny szkielet graphite, aria-busy; brak decyzji. |
| Partial | Warning, 8/27 dostępnych źródeł i jawne braki; brak decyzji/eksportu. |
| Error | Red, konkretne niepowodzenie i retry; bez potwierdzenia operacji. |
| Degraded | Warning, opis lokalnego snapshotu i odczyt; mutacje zablokowane. |
| Restricted | Ogólny komunikat; bez nazw, body i liczników org, wyczyszczenie sesji. |

## QA
[Raport wizualny](../../../prototypes/pipeline-hifi/design-qa.md), [21 zrzutów i macierz 42 stanów](../../../prototypes/pipeline-hifi/qa/report.json), [regresja przepływów](../../../prototypes/pipeline-hifi/qa/s06-flow.json).
Końcowy audyt czeka na gotowe wnętrze trasy po lazy load: 21 gotowych widoków, 0 overflow, 0 naruszeń axe WCAG A/AA, 0 błędów JS. Macierz 42 stanów sprawdza odczyt i brak wycieku restricted; nie jest 42 dodatkowymi audytami axe.
9/9 grup regresji, 0 błędów JS: edycja/eksport, Markdown/focus, zależności/powrót, przypięta rewizja, member i partial/degraded. Wynik wyłącznie lokalny.
Eksport zmiany cache 30→60: 5540 B, SHA d3e3c91750bfd0bbc13e30bbf2d6a1d5398b8710b69a5c37796a9d4825bb3168; pełny frontmatter zachowany.
Kontrast obliczony z tokenów: body 15,08:1; secondary 9,17:1; tekst przycisku orange 6,71:1; border kontrolki co najmniej 3,96:1; focus 6,48:1. Axe osobno sprawdza rzeczywisty render.
Build TypeScript/Vite przechodzi. Trasy ładowane osobno, fonty Latin; główny chunk około 639 kB / 172 kB gzip nadal wywołuje ostrzeżenie >500 kB. Fixture w bundle nie dowodzi budżetu 10 tys. skilli.
Podział modułów oparty na [React Router declarative](https://reactrouter.com/start/declarative/installation), [Vite](https://vite.dev/guide/); bezpieczny podgląd na [react-markdown](https://github.com/remarkjs/react-markdown), odczyt 2026-09-06.
Test zrzutu bez logo: świeży Owner rozpoznał „przeglądanie rewizji skilli przed decyzją i przekazaniem do Git”, obiekt postgres-auth i approve/edit/reject; wynik syntetyczny, bez P1 ogólnego dashboardu.
U4 AC5 nadal wymaga co najmniej 4/5 prawdziwych osób niebędących autorami UI. Wyniki syntetyczne nie zamykają pytań z 01/03/05.

## Przegląd
R1 — Owner: 0/0/0; Designer: P1=0/P2=1/P3=2. Naprawiono tabele, mobilny commit i pierwszy wynik poniżej folda.
R2 — Owner i Designer: P1=0/P2=1/P3=0 każdy; jedno wspólne znalezisko: test mierzył Panel zamiast kontenera przewijania.
R3 — obaj: 0/0/0; poprawiony selektor potwierdza 7/7 potrzebnych przewinięć klawiaturą, 2 przypadki bez potrzeby scrolla.
Wyjście: 0 otwartych P1/P2/P3; trzy rundy z powodu P2 w R2. Przeglądy syntetyczne, bez zaliczenia U4 AC5.
