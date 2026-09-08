# Brief
Data: 2026-09-06. Zakres: hosted UI U4; dziewięć etapów 0–8, bez zmiany backendu i bez commita.
## Cel
Owner przygotowuje instrukcję do eksportu, widząc źródło, zakres i skutki decyzji; developer sprawdza instrukcję dostarczaną agentowi.
Źródła decyzji: [pivot §1, §3, §7](../../PRODUCT-PIVOT.md), [review](../../PIVOT-REVIEW.md), [architektura](../../PIVOT-ARCHITECTURE.md), [ADR-0031](../../adr/ADR-0031-monorepo-to-managed-skill-library.md).
[założenie] Owner ma 15 minut na review (IA §2), developer przychodzi ze swoim zadaniem. Obali to pilot, jeśli odpowiedzialność lub moment wejścia okażą się inne.
## Widoki
| U4 / string UI | Główne działanie |
|---|---|
| Start / Import — Import | Skopiuj komendy CLI i sprawdź wynik importu do wskazanej organizacji. |
| Biblioteka — Library | Znajdź skill z filtrami repo, scope, owner, layer i status. |
| Mapa — Map | Znajdź relacje w osi Repository, Scopes albo Pyramid. |
| Skill — Skill | Sprawdź źródło i zakres konkretnej rewizji. |
| Propozycje — Proposals | Porównaj źródło i propozycję obok siebie; zaakceptuj do eksportu, popraw albo odrzuć z powodem. |
| Użycie i jakość — Usage & quality | Otwórz instrukcję wymagającą przeglądu na podstawie jawnego dowodu. |
| Integracje / Organizacja — Organization | Zainstaluj adapter albo zarządzaj dostępem organizacji w dwóch zakładkach. |
Login jest stanem wejścia Import/Organization, nie ósmym widokiem produktu. Galeria jest narzędziem developerskim poza nawigacją U4.
## Zmiana IA
| IA.md / UX.md przed pivotem | Po pivocie |
|---|---|
| Atlas, Review, Routing, Health; UI lokalne | Siedem widoków powyżej, hosted React; Routing/Eval poza tym zakresem. |
| GitHub-only, read-only review | Przygotowanie propozycji i eksport; Git pozostaje kanoniczny; eksport ≠ published. |
| CODEOWNER jako uprawnienie | Owner/member organizacji; CODEOWNERS to wskazówka własności, nie autoryzacja. |
| Brak onboardingu i importu | Login Google/GitHub, utworzenie org, podgląd CLI, postęp i błędy importu. |
| Jedna hierarchia, pełne G0–G7 | Oddzielne osie źródła/scope/wiedzy; uproszczony cykl publikacji. |
| Domyślny Atlas, role ML i Platform | Pierwszy Import; deep link do Proposals dla ownera; Platform jako zadania ownera, ML poza U4. |
| Mobile tylko odczyt, wybór gęstości | Wszystkie siedem widoków responsywne; stałe Balanced 40 px, cele dotykowe ≥44 px. |
| Cache lokalny mimo odmowy | Hosted API autoryzuje; po utracie uprawnień czyścimy cache, nie pokazujemy zapisanych danych org. |
## Kryterium
U4 Q: ≥4/5 rzeczywistych osób niebędących autorami UI przechodzi samodzielnie import, źródło/scope i propozycja → Git → published. Rejestrujemy czas i tarcia; 15 minut jest hipotezą. Agentowe symulacje nie zaliczają tego kryterium.
U4 R: klawiatura, sześć stanów na widok, tekstowa mapa; pierwsza strona 10 tys. skilli p95 ≤2 s w zadeklarowanej sieci pilota. Prototyp nie dowodzi SLA API.
Jedyny kierunek: [Industrial Surveyor](../../../prototypes/industrial-surveyor/DESIGN.md) i jego raster; grafit, 8 px, 2 px, 1 px, Barlow Condensed/Inter, Phosphor regular. Dane wyłącznie [Meridian fixture](../../../examples/monorepo/README.md), podpisane przy widoku.
## Przegląd
R1: Owner + Architekt; P1=0/P2=2/P3=0. Dopisano odrzucenie/poprawkę oraz pomiar czasu i tarć.
R2: Owner + Architekt; otwarte P1=0/P2=0/P3=0. Etap zamknięty, 2026-09-06.
