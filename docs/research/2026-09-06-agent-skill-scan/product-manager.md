# Product Manager — decyzja o MVP do testów użytkowników

Data: 2026-09-06. Status: rekomendacja do wspólnej decyzji CEO/CTO/PM/Project Manager. Podstawa: wskazana rozmowa, aktualny kod klienta, dokumentacja oraz publikacje podlinkowane niżej. Raport nie potwierdza działającego wdrożenia ani realnego użycia. Numery issues pochodzą z lokalnego mirroru docs/BACKLOG.md; stan live na GitHub niezweryfikowany.

## Decyzja

**Zamknąć MVP jako istniejący T1: zdalny Go SEARCH/USE z BM25F, klient Python, poprawna dostawa zatwierdzonych rewizji, raport autora w CI oraz mierzalna ekspozycja/użycie. Uruchomić ograniczony pilot. Dense, hybryda i kompresja sekcji nie są warunkiem startu.** Istniejący T0 i lokalny sparse fallback pozostają istniejącym zachowaniem; nie przepisywać klienta w ramach research.

Klientem jest Platform/DevEx utrzymujący instrukcje w monorepo; developer jest użytkownikiem. Wartość ma pojawić się w realnym zadaniu oraz decyzji ownera, a nie wyłącznie w Hit@1. To zgadza się z ADR-0029. Nowe zlecenie badań uzasadnia izolowane spiki, ale wynik publikacyjny nie powinien przesuwać pilota.

## Fakty i granice dowodu

| Obszar | Potwierdzony fakt | Czego nie udowodniono |
|---|---|---|
| Serwis | services/search/README.md: Go, Postgres, default router_bm25f_v1; eksport integer IDF, norm pól i postings | Nie sprawdzono running deployment |
| Klient | Kod klienta od linii 2248 i CONVENTIONS §1a: backend local/service, remote SEARCH ściga lokalny sparse fallback | Ostatnia wypowiedź czatu o braku lokalnego BM25 nie opisuje checkoutu |
| Dense | Default deployment ma dense wyłączony; GPU/background hybrid shadow jest opcjonalny | Brak dowodu, że shadow jest teraz uruchomiony |
| Parzystość | Raport BM25F: 0/1000 niezgodności HTTP/CLI; structured corpus: 0/243 | Parzystość nie jest skutecznością ani produktywnością |
| Latencja | README: whole-client p95 116/136 ms przy c1/c4, benchmark loopback | Brak SLA TLS–IAM–sieć i dowodu <300 ms przy 30k |
| Dense quality | PRODUCT-FOCUS przytacza +17,96 pp in-distribution oraz +0,67 pp [−1,50; +2,83] na niezależnym korpusie | Brak uniwersalnego wniosku BM25 zawsze lepszy lub dense lepszy dla każdego klienta |
| Produkt | PRODUCT-FOCUS: brak potwierdzonej prawdziwej sesji, pusty design partner | Dokumenty/testy nie dowodzą realnego użycia; potrzebna telemetryka z repo partnera |
| Pilot | E6.7 jest Proposed, niezafreezowany, z analizatorem i ośmioma placeholderami ownera | Brak rekrutacji, zamrożonego badania i wyników użytkowników |

Źródła: docs/adr/ADR-0029-product-focus-hard-rules.md, docs/PRODUCT-FOCUS.md, docs/BACKLOG.md, docs/CONVENTIONS.md, services/search/README.md, skills/guidefold/scripts/guidefold, docs/reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md, docs/reports/bakeoff/PARITY-STRUCTURED-CORPUS-2026-09-05.md, docs/pilot/E6.7-PROTOCOL.md. Starsze DESIGN/MVP zawierają historyczne plany; nowszy ADR-0029 i backlog zawężają aktualny zakres.

## Wpływ nowych publikacji

- Zachować pełny skill jako źródło prawdy. SkillRouter v5 (2026-07-20) opisuje utratę sygnału po ukryciu body; streszczenia nie odzyskują całej jakości. Dla MVP uzasadnia to dokładny USE i pełny tekst w artefakcie, nie obowiązkowy model. [SkillRouter](https://arxiv.org/abs/2603.22455v5).
- Field-Aware Agent Skill Retrieval v3 (2026-09-01) pokazuje korzyść osobnego scoringu pól i uczonej fuzji. Guidefold już ma BM25F: właściwe pytanie to przyrost sygnału dense względem tej konkretnej bazy. Naszego BM25F nie należy utożsamiać z dowolnym BM25 z tabeli artykułu. [Field-Aware Agent Skill Retrieval](https://arxiv.org/abs/2608.02880v3).
- SkillZip bada sekcje, kontrakty procedur, domknięcie zależności i odwracalną kompresję. To kandydat na późniejsze USE, jeśli pilot pokaże koszt zbędnego kontekstu lub niekompletne zestawy. Nie uzasadnia nowego graph engine na drodze do pilota. [SkillZip](https://arxiv.org/abs/2608.05604).

Publikacje dostarczają przesłanek technicznych. Nie zastępują dowodu, że użytkownik potrzebuje naszego przepływu pracy.

## Zakres MVP

| Użytkownik | Gotowy przebieg | Dowód odbioru |
|---|---|---|
| Operator | Instaluje obecne T1, konfiguruje auth, doctor, SEARCH→USE | Inna osoba niż autor potrafi wykonać runbook; pomiar docelowej sieci i przypięte wersje |
| Claude Code developer | Pyta w realnym repo; dostaje scoped karty; ładuje konkretną rewizję | Realna sesja, do 4 kart, budżet zachowany, ślad dostawy oraz load |
| Copilot CLI developer | Jawne find/load w tym samym repo | Realna demonstracja; brak obietnicy niepotwierdzonej auto-injekcji |
| Autor | PR instrukcji z raportem kolizji/triggerów | Przydatna zmiana treści albo odrzucenie sugestii z powodem |
| Owner | Czyta raport ekspozycji, pobrań, użycia i feedbacku | Decyzja: poprawić, wycofać, scalić lub pozostawić skill; unknown pozostaje unknown |
| Platform | Wycofuje błędną rewizję/snapshot i obserwuje outage | Próba rollbacku, granic dostępu i exact revision; realny backend/fallback w eventach |

Poza MVP: nowy lokalny model, portal, marketplace, T2/HA/k8s, automatyczna indukcja/promocja, nowy composer, reranker w hooku, nowe magazyny, obowiązkowy dense. U pierwszego partnera wystarczy 50–200 rzeczywistych użytecznych instrukcji z 3 zespołów; 30k to osobny eksperyment skalowania, nie warunek pierwszej obserwacji.

## Hipotezy i badanie

H1 — developer: właściwa instrukcja poprawia zadanie lub ogranicza czas bez wzrostu regresji. Porównanie: Guidefold włączony/wyłączony przy zachowanych zwykłych regułach repo i harnessu.

H2 — autor: raport przed merge prowadzi do przydatnej korekty tekstu. Otwarcie komentarza i zgoda z sugestią nie są wystarczającym wynikiem.

H3 — owner: raport prowadzi do działania. Eventy i pobrania dowodzą sprawności instrumentacji, nie wartości.

| Scenariusz | Co rozstrzyga |
|---|---|
| Moduł podobny do sąsiedniego zespołu | Poprawny scope, brak wrong-sibling detour, zadanie spełnia kryterium |
| Objaw problemu bez firmowych słów kluczowych | Czy sparse zawodzi mimo istnienia skilla; oracle wskazuje brak retrievalu |
| Korzystanie z platformy innego zespołu | Provider skill dochodzi mimo innego owner scope |
| Zadanie wymagające kilku instrukcji | Pełny dopuszczalny zestaw albo jawne cannot_fit |
| Brak pasującego skilla | Brak niepotrzebnej karty i dodatkowego detour |
| Wycofana rewizja/brak dostępu | Brak niedozwolonego body, jawny powód |
| PR z kolidującym opisem | Owner koryguje tekst, ponowny raport pokazuje zmianę |
| Timeout/outage/ponowienie | Sesja kontynuuje; backend znany; brak podwójnych liczników |

Usability: rekomenduję 6–9 developerów (2–3 z każdego z 3 zespołów), po jednej obserwowanej sesji około 45 minut, plus 2–3 ownerów i operator spoza twórców. To plan jakościowy, nie istniejąca rekrutacja ani próba do dowodu statystycznego. Zapisywać failure/unknown osobno dla instalacji, discovery, load, wykonania, dependencies, feedbacku i raportu.

## Go/no-go

| Moment | Próg | Decyzja |
|---|---|---|
| Start sesji | Nazwany partner/repo/owner/data policy, realny SEARCH→USE, rollback, zero naruszeń dostępu/revision/budżetu w próbach | GO na ograniczony pilot; bez tego nie nazywać MVP gotowym |
| Latencja | Whole process hook, TLS/IAM i sieć, p50/p95/p99 przy c1/c4 oraz fallback rate | Deadline requestu 300 ms odróżnić od istniejącego progu whole-client 400 ms; loopback nie jest produkcyjną obietnicą |
| 4 tygodnie | ≥20 realnych sesji przez developera spoza twórców, mierzalny SEARCH/LOAD | Dowód używalności/instrumentacji; nie wynik task success |
| Authoring | 10 rzeczywistych PR z komentarzem; policzyć przydatne zmiany i odrzucenia | 0 zmian → zredukować tę propozycję do lintera |
| Owner report | ≥1 udokumentowana decyzja ownera w 4 tygodnie | Brak decyzji → nie rozbudowywać telemetryki jako produktu |
| E6.7 | 20–40 par, success gain/regression, przedziały, czas/tokeny, unknown | Feasibility, nie szeroka adopcja. Niejednoznaczny wynik blokuje T2; obiecujący pozwala obliczyć follow-up n |
| Challenger | Osobna pre-rejestracja, te same warunki, etykiety i gate vs shipped sparse | Dense może pozostać research mimo sukcesu pilota sparse |

Mianowniki: sesje z obserwowalnością, logical requests, pokazane karty, załadowane rewizje, ocenione outcomes. Observed use, self-report i feedback są różnymi sygnałami. Brak negatywnego feedbacku przy braku odpowiedzi nie jest sukcesem. „Brak korzyści” przy n=20 nie jest dowodem, że efekt nie istnieje.

## Korekty przed zamrożeniem pilota

**Nie blokować testu wartości sparse dostępnością challengera.** E6.7 ma A/B i B/C jako dwa primary contrasts oraz placeholder C. Proponuję przed pierwszym pomiarem zatwierdzić wersję A/B, z oracle D jako diagnozą; C uruchomić w osobnej nazwanej pre-rejestracji po dopuszczeniu challengera. Analizator sprawdzić względem zatwierdzonej wersji. Ten raport nie zmienia samodzielnie protokołu ani historii.

W baseline A wyłączyć Guidefold, zachowując natywne instrukcje zespołu. Ich usunięcie sztucznie powiększyłoby przewagę. Zadania oceniać w ciemno, przypiąć model/harness/commit, nie pozwalać tej samej osobie wykonywać tego samego zadania drugi raz w innym warunku.

**Ujednolicić terminy.** PRODUCT-FOCUS oczekuje wyniku do 2026-10-04, BACKLOG: M1 2026-09-20, 4 tygodnie do 2026-10-18, E6.7 do 2026-11-15. Rekomenduję okna backlogu przy partnerze do 20 września; aktualne issue milestone ma pierwszeństwo. Czterech tygodni nie raportować po dwóch tygodniach.

Lokalne referencje do koniecznej pracy, status live niezweryfikowany: #78 partner, #80 onboarding, #81 Claude, #82 Copilot, #91 realny raport, #95 decyzja ownera, #96 instalacja T1, #97 TLS/IAM, #98 realna sieć. #102–#107 obejmują freeze, rekrutację, dry-run i badanie. Te referencje nie oznaczają nowo utworzonych issues.

## Wykonalność i paper

Wykonalność ograniczonego MVP: **wysoka, warunkowa**. Rdzeń i kontrakt istnieją; ryzyka to instalacja, auth/sieć, prawdziwy harness oraz jakość treści. Bez partnera/operatora nie przypisuję daty gotowego wdrożenia. Wykonalność szerokiej adopcji pozostaje nieustalona.

Paper nie jest bramką release. Potencjalny wkład: różnica między trafnością pojedynczego skilla a użytecznością całego dopuszczalnego zestawu w wielozespołowym repo, wraz z kosztem i granicami transferu dense. Samo BM25+RRF nie daje obronionej nowości. Najcenniejsze braki to niezależnie ocenione zadania i realne zachowanie developerów. Spiki powinny wskazać hipotezę wartą pomiaru, nie symulować wynik użytkowników.

**Głos Product Managera: GO dla przygotowania i startu ograniczonego MVP T1 sparse; NO-GO dla rozbudowy runtime przed pilotem; research kończy się raportem, także negatywnym, bez przesuwania testów.**
