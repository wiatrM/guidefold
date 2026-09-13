# UX Guidefold

Status: projekt hosted UI po pivocie, 2026-09-06; wymagania i makiety po dwóch przeglądach etapów 0–5. Hi-fi etapu 6 ma potwierdzony build i audyt przeglądarkowy; formalne przeglądy zamknięte z 0 otwartych P1/P2.
Cel: zasady interakcji, treści i oceny siedmiu widoków U4. Reguły utrzymania: [DOCUMENTATION-RULES](../DOCUMENTATION-RULES.md).
Zastępuje UX z 2026-09-04, commit 88e404561a9f6994cd870743bf858b9b0a616126. Rozbieżności: [brief](pipeline/00-brief.md). Wejścia: [pivot §7](../PRODUCT-PIVOT.md), [IA](IA.md), [research](pipeline/01-research.md), [symulacja](pipeline/05-simulation.md).

## 1. Odbiorcy

| Zadanie [założenie] | Potrzebny dowód | Co obali założenie |
|---|---|---|
| Owner przygotowuje decyzję o instrukcji. | Źródło, zakres, diff i konsekwencja następnego kroku. | Przy rzeczywistych zmianach lub feedbacku nikt nie podejmuje takiej decyzji; brak okazji jest nierozstrzygnięty. |
| Developer sprawdza instrukcję dla modułu. | Zastosowanie, repo/scope i konkretna rewizja. | Informacja w harnessie wystarcza, a UI nie zmienia decyzji przy zadaniu. |
| Operator dostarczania weryfikuje rewizję. | Osobno publikacja oraz dowód załadowania. | Istniejący proces daje wystarczający dowód, a UI nie zmienia diagnozy rozbieżności. |

Źródło i granice person: [etap 2](pipeline/02-personas.md), 2026-09-06. Operator jest zadaniem ownera, nie nową rolą ACL. CODEOWNERS opisuje źródłową odpowiedzialność; owner/member organizacji określa API.
Budżet 15 minut aktywnego review jest [założeniem], nie wynikiem badania. Obali go obserwacja równoważnych rzeczywistych zadań; oczekiwanie na Git mierzymy oddzielnie.

## 2. Zasady

| Zasada | Wymaganie |
|---|---|
| Dowód przed wnioskiem | Przy instrukcji dostępne są źródło, commit i SHA-256 treści. Liczba bez źródła lub mianownika nie staje się metryką jakości. |
| Decyzja z konsekwencją | Approve for export, Edit candidate i Reject mają porównywalną dostępność. Decyzja wymaga powodu; odrzucenie nie jest błędem systemu. |
| Git pozostaje kanoniczny | UI przygotowuje treść i decyzję. Eksport prowadzi do Awaiting Git; Published wymaga właściwego review/merge, walidacji i sync. |
| Zachowanie kontekstu | Powrót ze Skill odtwarza filtry Library lub oś Map. Link do obserwacji niesie skill, scope i revision. URL nie nadaje uprawnień. Od 2026-09-13 (ADR-0047) domyślnym zakresem jest cała organizacja; repozytorium to filtr w railu zapisany w `?repo=`, wspólny dla Overview, Library, Map, Skill, Proposals i Usage; zmiana filtra kasuje kursor strony, zachowuje resztę adresu. |
| Rozdzielenie znaczeń | Repository, Scopes i Pyramid odpowiadają na inne pytania. Source layer/status nie określa Knowledge layer ani stanu publikacji. |
| Jawne ograniczenie | Partial opisuje brakujące źródła; degraded dostępny odczyt i zablokowane operacje; restricted usuwa dane organizacji z widoku i cache. |

Pobranie, context_loaded i outcome to różne poziomy dowodu. No observations/Unknown oznacza brak danych, nie skuteczność 0%. To wymagania [pivotu](../PRODUCT-PIVOT.md), a nie dowód, że obecny prototyp realizuje backend. W Usage & quality wykresy mogą skracać odczyt agregatów, ale każdy słupek ma tekstowy licznik i mianownik, a context_unknown pozostaje osobnym wynikiem. Tabela per skill jest dokładnym odczytem; brak danych nie jest słupkiem o wartości zero.

## 3. Interakcje

| Obszar | Reguła |
|---|---|
| Nawigacja | Import, Library, Map, Skill, Proposals, Usage & quality, Organization. Login i tworzenie org są stanami wejścia; Members/Integrations/Telemetry/Audit zakładkami Organization. |
| Główna akcja | Wynika z obiektu i aktualnego etapu [IA §5](IA.md). Po eksporcie skrót prowadzi do dowodu publikacji; nie obiecuje ponownej decyzji. |
| Import | Org/repo, zakres i manifest przed wysyłką. Wynik rozdziela przyjęte i pominięte pliki; niekompletny import nie udaje pełnego. |
| Propozycja | Źródło i kandydat obok siebie na desktopie, kolejno na mobile. Podgląd Markdownu, dokładny surowy plik, diff oraz skok do formularza decyzji. |
| Edycja kandydata | Zmienia body; frontmatter, owner, scope i relacje zostają stałe. Eksport SKILL.md nie obiecuje zamknięcia pełnego pakietu zasobów. |
| Odświeżenie | Nie zmieniamy treści pod kursorem podczas decyzji. Nowa rewizja wymaga jawnego ponownego odczytu przed zapisem. |
| Błąd zapisu | Formularz zachowuje treść/powód i wskazuje, co nie zostało zapisane. Nie pokazuje powodzenia bez potwierdzenia. |
| Członkostwo | Member może czytać i zgłaszać feedback. Import, decyzje i zmiany org wymagają ownera; ochrona ostatniego ownera ma komunikat przy operacji. |
| Klawiatura | Natywne linki, przyciski, radio, select i disclosure; Tab/Shift+Tab oraz standardowe aktywacje. Nie dodajemy niezamówionej palety ani skrótów j/k. |
| Mobile | Wszystkie siedem widoków zachowuje działanie. Układ się składa; ważne dane i decyzje nie znikają za trybem „read-only mobile”. |

Macierz empty/loading/partial/error/degraded/restricted dla każdego widoku: [etap 4 §5](pipeline/04-wireframes.md). Wygląd i testy hi-fi należą do etapu 6; kontrakty API i ważność cache do etapu 7.
U4 AC2 wymaga pierwszej strony przy 10 tys. skilli z p95 ≤2 s w zadeklarowanej sieci pilota. Nie renderujemy całego grafu. Przykładowe 27 plików z etapów 4–6 nie zalicza tego pomiaru.

## 3a. Wdrożenie organizacji i repozytoria z GitHuba

Reguła właściciela z 2026-09-13, wiążąca dla kreatora organizacji, ekranu Import i przełącznika organizacji. Wzorzec: Codecov, Coveralls, Vercel i GitHub, które przeprowadzają przez ten sam przepływ: logowanie, instalacja aplikacji GitHub, lista repozytoriów z akcją przy wierszu, status konfiguracji. Szczegóły tras i DTO należą do [API-CONTRACT §4.7](../API-CONTRACT.md); ten rozdział opisuje zachowanie ekranu.

| Obszar | Reguła |
|---|---|
| Kolejność kreatora | Trzy kroki, bo każdy zależy od poprzedniego: organizacja, GitHub, import. Numerowany postęp jest dopuszczalny tylko dlatego, że to prawdziwa sekwencja. Każdy krok ma Wstecz; krok GitHub ma zwiniętą ścieżkę awaryjną (CLI albo pliki). |
| Organizacja | Jedno pole „Name”, wstępnie wypełnione loginem konta GitHub, jeśli użytkownik logował się przez GitHub. Slug wyprowadzany na żywo, zmieniany pod „Change URL”. Zajęty slug jest błędem przy polu; wpisana nazwa zostaje. Kreator nie pyta o identyfikator repozytorium, adres Git, dostęp członków, recenzenta ani limity generowania — to ustawienia organizacji i repozytorium. |
| Connect GitHub | Każdy przycisk „Connect GitHub” związany z importem instaluje aplikację GitHub dla bieżącej organizacji i wraca tam, skąd użytkownik zaczął. Nigdy nie jest zwykłym logowaniem przez GitHub. Tylko owner; member widzi, dlaczego nie może. |
| Lista repozytoriów | Repozytoria z połączonych instalacji jako lista z akcją przy każdym wierszu: wyszukiwarka, filtr All / Not imported / Imported, „Import” w wierszu i „Import all” nad listą. Import repozytorium nie wymaga klucza modelu. |
| Brakujące repozytorium | Pod listą link „Missing a repository? Change GitHub App access” do ustawień instalacji na GitHubie. Brak repozytorium na liście oznacza zakres nadany aplikacji, nie błąd Guidefold, i ekran mówi to wprost. |
| Synchronizacja | Dopóki rejestracja repozytoriów nie przebiegła, ekran pokazuje „Syncing” z liczbą, nie pustą listę. Nieudana rejestracja jest porażką z powodem i działaniem, nigdy wiecznym „Syncing”. |
| Kilka kont GitHub | Wybór konta GitHub (instalacji) jako lista rozwijana nad listą repozytoriów, pokazywana tylko przy więcej niż jednej instalacji. |
| Stan repozytorium | Przy każdym wierszu dokładnie jeden stan: gotowe do importu; zaimportowane z datą ostatniego importu; brak `guidefold.yaml` z linkiem do instrukcji; rejestracja nie powiodła się z powodem. Brak `guidefold.yaml` nie jest błędem, tylko nazwanym powodem, dla którego repozytorium nie jest zarządzane. |
| Klucz modelu | Przy kreatorze i na ekranie Import jedna linia statusu. Bez klucza: pełny import z propozycjami (duplikaty, sprzeczności) wymaga klucza modelu, z linkiem do Organization › Model keys. Z kluczem: nazwa używanego dostawcy. Link tylko dla ownera; member widzi, kto może dodać klucz. |
| Przełącznik organizacji | W górnej części raila nazwa organizacji i rola; po otwarciu wszystkie organizacje użytkownika z rolami, zaznaczona bieżąca, na końcu „Create organization”. Zmiana zostawia bieżący widok, podmienia `org` w URL zwykłą nawigacją (Wstecz wraca) i usuwa `repo`. Dane poprzedniej organizacji nie mogą mignąć w następnym widoku. |
| Zapamiętany kontekst | Jak w GitHubie: bez `org` w URL konsola otwiera ostatnio wybraną organizację, jeśli użytkownik nadal do niej należy. URL zawsze wygrywa i staje się nową zapamiętaną wartością. Zapamiętanie jest wygodą tej przeglądarki, nie uprawnieniem; dostęp rozstrzyga `/me`. |

Nie przenosimy wzorca tokenu repozytorium do wklejenia w CI (Codecov, Coveralls): adapter loguje się kodem urządzenia, a import idzie przez aplikację GitHub.

## 4. Dostępność

Wymagania, nie deklaracja ukończonego audytu:

- Tekst zwykły ma kontrast ≥4,5:1; istotne granice kontrolek i wskaźniki ≥3:1. Każda konkretna para barw wymaga pomiaru.
- Kolor ma etykietę tekstową: stan, rodzaj relacji, dodanie/usunięcie. Red oznacza wyłącznie błąd.
- Focus jest widoczny; ring 2 px i offset 3 px. Skip to content prowadzi do main. Po zmianie etapu decyzji focus trafia do nowego wyniku.
- Pola mają widoczne etykiety, powiązane podpowiedzi/błędy oraz stan niepoprawności. Komunikaty nie wymagają rozróżnienia samej barwy.
- Tablice mają caption i th scope; obszar przewijania jest osiągalny klawiaturą. Długie ścieżki, URN i diff nie rozszerzają strony.
- Map zapewnia tekstowe drzewo i listę relacji. Natywne disclosure i linki pozwalają wykonać zadanie bez myszy; nie deklarujemy niezaimplementowanego sterowania grafem strzałkami.
- Dekoracyjne ikony są ukryte dla technologii asystujących; samodzielna kontrolka ikony ma nazwę. Dotykowe kontrolki mają docelowo ≥44 px na mobile.
- Reduced motion wyłącza przejścia; loading nie używa pulsowania ani shimmeru. Axe uzupełnia ręczne sprawdzenie focusu i klawiatury.

## 5. Treść

| Obszar | Reguła |
|---|---|
| Nazwy | Stringi UI po angielsku; krótkie etykiety przedmiotu lub czynności. Dokumentacja po polsku. |
| Stan | Opisuj, co wiadomo i co można zrobić. Unknown jest pełnoprawnym wynikiem. |
| Pochodzenie | Rewizja treści, commit, snapshot i digest paczki to odrębne pola. Nie wymyślaj numeru linii, jeżeli referencja nie ma zweryfikowanego mapowania. |
| Treść wygenerowana | Oznacz ją w miejscu odczytu; pokaż dostępne źródła i metadane procesu. Nie wypełniaj nieznanego modelu lub recepty przykładową nazwą. |
| Dane przykładowe | Wyłącznie w makietach, hi-fi i galerii komponentów, zawsze podpisane. Od 2026-09-08 produkt nie ma trybu fixture ani symulacji: każdy widok czyta hostowane API, a nieznane pozostaje Unknown. |
| Błąd | Nazwij nieudany krok, skutek i dostępne działanie. Bez wymyślonego retry, jeśli system nie potrafi go wykonać. |

Etap 6 zapisuje inwentarz stringów i wynik czytania na głos. Dane przykładowe etapów 4–6 nie zawierały prawdziwych członków, zdarzeń użycia ani potwierdzonej instalacji adaptera.

## 6. Anti-slop

Te reguły dotyczą ekranów i dokumentów. Utrzymujemy język oraz geometrię [Industrial Surveyor](../../prototypes/industrial-surveyor/DESIGN.md); wymaganie zlecenia zawęża jego historyczne warianty.

| Niedopuszczalne | Wymagana postać |
|---|---|
| Duże zaokrąglenia, pill badges, emoji jako ikony | Promień 2 px i Phosphor regular. |
| Hero, slogan marketingowy, wyśrodkowany wielki nagłówek w produkcie | Nazwa widoku, identyfikacja obiektu i jego działanie. |
| Karty albo metryki dodane dla symetrii | Tylko dostępne dane potrzebne do konkretnej decyzji. |
| Wykres bez pytania, skali lub danych | Tekstowy dowód albo jawny brak obserwacji. |
| Przykładowe firmy/ludzie/liczby udające produkcję | Dane rzeczywiste; wartości przykładowe tylko w makietach i galerii, wyraźnie podpisane. |
| Przełączniki motywu lub gęstości | Jeden graphite, stałe Balanced 40 px; mobile powiększa cele dotykowe. |
| Stan przekazany wyłącznie animacją (pulsowanie, poświata, kolor ruchu) bez etykiety | Etykieta i ton `StateBadge`; animacja może być dodatkiem do opisanego stanu, nigdy jego jedynym nośnikiem. |
| Nowy wariant komponentu bez potrzeby | Użycie istniejącego API; drugi wariant ma pisemne uzasadnienie. |

**Decyzja właściciela 2026-09-13 ([ADR-0049](../adr/ADR-0049-premium-visual-effects-layer.md)):**
gradienty jako powierzchnia, glow, neon, animowane obramowania (border beam, shine border),
shadery i kategorie dekoracyjne (animowane listy, animowany tekst, liczniki, marquee, orbiting
circles) są dopuszczone wszędzie w konsoli, z zestawu `ui/src/components/effects/*` — bez
ograniczenia miejsca. To samo dotyczy ciągłego ruchu dekoracyjnego (obracający się border,
dryfująca siatka), nie tylko ruchu po zmianie stanu. Dotyczy to także glassmorphismu (`backdrop-filter`)
i pulsowania: właściciel zniósł zakaz wizualny w całości. Wiążące pozostaje to, co jest dostępnością, a
nie estetyką: `prefers-reduced-motion` wyłącza ruch albo zatrzymuje go na jednej klatce; kontrast
tekstu na dowolnym efekcie spełnia WCAG AA; żaden efekt nie niesie informacji sam z siebie (stan
zawsze czyta się z etykiety i tonu `StateBadge`); focus pozostaje widoczny (glow jest dodatkiem do
istniejącego obrysu focusu, nie jego zastąpieniem); żaden efekt nie miga szybciej niż trzy razy na
sekundę.

Nie używaj „seamless”, „streamline”, „empower”, „unlock”, „effortless”, „supercharge” ani ogólnego „powerful”. Unikaj odruchowej reguły trzech, anonimowego „badania pokazują”, ciągłych em dash i zdań „to nie X, to Y”.
Nagłówki są nazwami, nie zdaniami reklamowymi. Tooltip nie powtarza etykiety. Krótka sekcja z dwoma faktami nie wymaga trzeciego dla symetrii.
Test zrzutu: usuń logo i zapytaj, co produkt robi. Odpowiedź „jakiś AI dashboard” to P1; wynik agenta jest syntetyczny.
Test na głos: przeczytaj każdy string tak, jak do współpracownika; przepisz zdania, których nie użyłbyś w rozmowie. Test nie zastępuje badania z ludźmi.

## 7. Przegląd zmiany

Zmiana ekranu wskazuje obiekt/dowód/akcję, obsługiwane stany i powrót z kontekstem. Dołącza dowód kontrastu, klawiatury, axe i responsywności dla zmienionego zakresu.
Nie zaznaczaj kontroli jako zaliczonej na podstawie planu. Budowanie Reacta nie dowodzi bezpieczeństwa API, wydajności 10 tys. skilli ani użyteczności.
[Etap 5](pipeline/05-simulation.md) potwierdził 18 lokalnych zadań syntetycznych; P3 czytelności Markdownu zamknięto semantycznym podglądem i testem focusu w hi-fi (s06-flow.json).
U4 AC5 wymaga co najmniej 4 z 5 rzeczywistych osób niebędących autorami UI. Pytania do pilota pozostają w [research](pipeline/01-research.md), [ankiecie](pipeline/03-survey.md) i [symulacji](pipeline/05-simulation.md).
