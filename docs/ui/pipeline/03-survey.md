# Ankieta pilotów
Data: 2026-09-06. Wejścia: [research](01-research.md), [persony](02-personas.md), [U4 i plan badań](../../PRODUCT-PIVOT.md).
Kwestionariusz dotyczy prawdziwych zdarzeń, nie opinii o obietnicy Guidefold. Nie wysłano ankiety; nie skontaktowano uczestników.
## 1. Metoda
[założenie] Pierwsza seria to 5 ownerów i 5 developerów z ≥3 niezależnych zespołów, nie autorzy UI. Obali użyteczność takiego doboru brak dostępu do ostatnich rzeczywistych zadań lub dominacja jednego procesu organizacji.
Próba celowa i mała; progi są regułami iteracji, nie estymacją rynku. Owner wykonujący zadania platformowe oznacza oba zadania, ale liczy się raz w mianowniku.
Każde pytanie dopuszcza „nie wiem”, „nie dotyczy” i brak zdarzenia. Progi porównań liczymy przy ≥5 ważnych odpowiedziach właściwej grupy, inaczej Nierozstrzygnięte; pokazujemy licznik/mianownik. S7 kwalifikuje pojedynczy zakres i nie czeka na 5 osób.
Kodowanie: niepamiętanie/brak respondenta zawsze oznacza brak danych. S1 potwierdzony brak zdarzenia to ważne Nie; S4 brak sposobu weryfikacji to ważne Nie; nieznana rewizja przy znanym sposobie jej sprawdzenia nie oznacza braku sposobu. S6 obejmuje ownerów z oszacowaniem czasu aktywnego sprawdzania. S2/S3/S5/S6/S8/S9: „nie wiem” i „nie dotyczy” poza mianownikiem; błędna interpretacja S9 jest ważna. S10: mianownik to ownerzy z konkretną okazją; brak okazji raportujemy osobno, nie jako brak potrzeby. S7 jest regułą kwalifikacji bez głosowania. Rekrutujemy dalsze osoby, jeśli po wyłączeniach n<5.
Moderator nie pokazuje makiet ani proponowanych odpowiedzi przed opisem zdarzenia; dopytuje o artefakt za zgodą, nie zbiera kodu ani danych osobowych.
## 2. Pytania
| ID | Pytanie | Hipoteza [założenie] | Próg decyzji przed badaniem |
|---|---|---|---|
| S1 | Jaką instrukcję dla agenta ostatnio zmieniono w Twoim zespole i z jakiego powodu? Jeśli nie pamiętasz, zaznacz to. | Zmiany treści są powracającym zadaniem P1. | Jeśli ≥3/5 ownerów potwierdzi brak zmian z ostatnich 4 tygodni, wydłużamy obserwację przed wnioskiem o powrotach; nie ogłaszamy braku potrzeby. |
| S2 | Kto przygotował, sprawdził i udostępnił tę zmianę? Opisz role, bez nazwisk. | Przygotowanie i zatwierdzenie mogą dotyczyć różnych osób. | Jeśli >1/2 ownerów wskaże różne osoby, makieta pokazuje osobno autora i uprawnionego decydenta; nie dodajemy ról ACL. |
| S3 | Skąd uruchamiasz narzędzie przy ostatnim zadaniu: root repo, podfolder, workspace z kilkoma rootami czy inny kontekst? | Kontekst katalogu bywa węższy niż repo. | Jeśli >1/2 devów pracuje poza root, podgląd repo/scope i zachowanie deep linku testujemy przed rozbudową mapy. |
| S4 | Jak sprawdziłeś, którą wersję instrukcji agent otrzymał przy tym zadaniu? | Dostarczenie rewizji bywa nieznane. | Jeśli >1/2 uczestników nie ma sposobu sprawdzenia, testujemy rozumienie Unknown przed dodawaniem statystyk agregowanych. |
| S5 | Co otwierasz najpierw, gdy masz zdecydować o zmianie instrukcji? Pokaż kolejność na ostatnim przykładzie. | Źródło i zakres wspierają decyzję ownera. | Jeśli >1/2 ownerów zaczyna od źródła lub zakresu, zachowujemy je nad zgięciem; inne odpowiedzi uruchamiają test kolejności w obrębie U4. |
| S6 | Ile zajęły osobno przygotowanie, sprawdzanie treści i oczekiwanie przy ostatniej zmianie do jej udostępnienia? Podaj szacunki lub „nie wiem”. | Budżet 15 minut dotyczy aktywnego review, nie czasu merge. | Jeśli mediana aktywnego review >15 min, upraszczamy kolejność dowodów i mierzymy ją zadaniowo; samo oszacowanie nie zalicza celu czasu. |
| S7 | Jakie zasady obowiązują u Was przy wysyłaniu dokumentacji repo do usługi zewnętrznej i kto je zatwierdza? | Dopuszczony zakres importu można pokazać w manifeście. | Każdy wymóg zakazujący wspólnego dostępu org lub wysyłki wyklucza dany zakres pilota; wybieramy dopuszczony zakres, bez obchodzenia polityki. |
| S8 | Jak znalazłeś ostatnio instrukcję dla nieznanego modułu? Opisz kroki, także gdy jej nie znalazłeś. | Lista/wyszukiwanie mogą być pierwszą drogą, mapa narzędziem kontekstu. | Jeśli >1/2 devów zaczyna od wyszukiwania, Library otrzymuje pierwszeństwo po imporcie; Map pozostaje jednym z siedmiu widoków U4. |
| S9 | Po przygotowaniu plików zmienionej instrukcji do repo: jakie zdarzenia muszą nastąpić, zanim uznasz ją za dostępną agentom? | Eksport, publikacja i załadowanie są odróżnialne. | Jeśli ≥2/5 ownerów utożsami przygotowanie plików z dostępnością dla agentów, poprawiamy stringi i ponawiamy test; nie skracamy procesu Git. |
| S10 | Czy w ostatnich 4 tygodniach pojawił się wynik pracy agenta, po którym rozważano sprawdzenie instrukcji? Jeśli tak, co zrobiono i na podstawie czego; jeśli nie, zaznacz brak okazji. | Obserwacja jakości może wywołać decyzję P1. | Jeśli >1/2 ownerów nie wskaże dowodu mimo realnych okazji, priorytetem jest pytanie o decyzję poza UI; brak okazji pozostaje Nierozstrzygnięty. |
## 3. Próba syntetyczna
Każda z trzech person odpowiada jako osobny agent ze świeżym kontekstem. Odpowiedzi są hipotetycznymi wariantami na fixture Meridian, nigdy historią prawdziwego uczestnika ani prognozą częstości.
[syntetyczne, n=3] Oddzielni agenci P1, P2 i P3 odpowiedzieli na S1–S10. Wszystkie odpowiedzi o fakty brzmią Nieznane (brak respondenta). Tabela zawiera wyłącznie zaproponowane warianty do sprawdzenia, nie wyniki zachowań.
| Pytanie | P1 Owner [syntetyczne] | P2 Dev [syntetyczne] | P3 Operator [syntetyczne] |
|---|---|---|---|
| S1 | Wariant: poprawka po feedbacku | Brak historii zmian | Brak historii zmian |
| S2 | Wariant: autor i owner mogą być jedną osobą | Brak danych | Wariant: owner sprawdza dostarczenie |
| S3 | Brak danych | Wariant: start z podfolderu | Wariant: weryfikacja repo/scope |
| S4 | Wariant: dowód load albo Unknown | Wariant: źródło bez dowodu load | Wariant: porównanie published i loaded |
| S5 | Wariant: problem → źródło/scope → diff | Wariant: treść i zastosowanie | Wariant: repo/scope → rewizja → dowód |
| S6 | Czas nieznany | Czas nieznany | Czas nieznany |
| S7 | Polityka nieznana | Polityka nieznana | Polityka nieznana |
| S8 | Wariant: Library → Skill | Wariant: wyszukanie celu, odczyt scope | Nie odpowiada na szukanie; weryfikuje Skill/Usage |
| S9 | Wariant: eksport ≠ publikacja; load osobno | Wariant: bez dowodu dostępność nieznana | Wariant: publikacja ≠ load |
| S10 | Wariant: konkretny feedback z kontekstem | Brak zdarzenia | Brak zdarzenia |
Wszyscy wskazali niezgodność S6 z progiem aktywnego review; poprawiono pytanie na osobne etapy. P3 wskazał wieloznaczność S4/S9: po swobodnej odpowiedzi moderator pyta „Co dokładnie znaczy tu otrzymał/dostępna i na czym to opierasz?”, bez podawania modelu odpowiedzi.
Kolejność makiet: Proposals → Skill → Library → Import → Map → Usage → Organization; priorytet pytań do ludzi: S6, S4/S9, S7. Siedem widoków i progi pozostają bez zmian; syntetyczne odpowiedzi nie zaliczają żadnego progu.
## Przegląd
R1: Owner + Badacz UX; P1=0/P2=2/P3=0 (unikalne). Doprecyzowano kodowanie/mianowniki i okazje do decyzji S10.
R2: Owner + Badacz UX; otwarte P1=0/P2=0/P3=0. Etap zamknięty, 2026-09-06.
