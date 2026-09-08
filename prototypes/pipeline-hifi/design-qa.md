# Przegląd wizualny — pipeline hi-fi
Status: audyt i przeglądy ukończone, 2026-09-06; brak otwartych znalezisk.
Zakres: siedem widoków U4, wyłącznie Meridian fixture. Wzorzec: [plansza](../industrial-surveyor/design-reference/source-industrial-surveyor.png) i [styles.css](../industrial-surveyor/src/styles.css).
Plansza marki zawiera historyczny ekran; bieżące dane i zadania wynikają z U4. Planszę i render Proposals 1280 porównano w jednym wejściu obrazu; osobno obejrzano 21 gotowych zrzutów i pełne strony.
## Porównanie
| Obszar | Wynik |
|---|---|
| Typografia | Barlow Condensed dla tytułów, Inter dla tekstu; lokalne fonty. Dokładne identyfikatory mają mono. |
| Odstępy | Siatka 8 px z połówką 4 px, radius 2 px, obrys 1 px; wiersz minimum 40 px, bez przełącznika gęstości. |
| Kolory | Paleta źródłowa; orange to decyzja człowieka, teal system, red błąd. Kontrast tekstu i istotnych kontrolek spełnia progi pomiaru. |
| Assety | Oryginalne guidefold-mark.png i survey-grid-pattern.png; Designer porównał SHA ze źródłem. Ikony Phosphor regular. |
| Treść | [Inwentarz stringów](qa/copy-review.json) obejmuje wszystkie autorskie wystąpienia i szablony; ocena syntetyczna, bez nagrania lub udziału człowieka. |
Różnice zamierzone: siedem widoków i nowy lifecycle zamiast Route monitor; brak fikcyjnych metryk, mapy promocji i konfigurowalnych motywów.
## Iteracje
1. Odczyt mobilny wykrył rail zajmujący 524 px. Natywne Navigate zmniejsza nawigację; siedem tras pozostaje dostępnych klawiaturą, wybór zamyka menu.
2. Odrzucenie otrzymało kolor decyzji. Niezgodna rewizja z Usage ma jawny komunikat i blokadę body; źródło nie udaje innej rewizji.
3. Podział kodu na lazy routes wymagał poprawienia gotowości screenshotu. Końcowy audyt czeka na wnętrze trasy; wcześniejsze Loading view nie zaliczały ready.
4. R1 Designer: P2 ściskania tabel. Minimum 640 px tabeli, 240 px pierwszej kolumny i 112 px disclosure zachowuje czytelność; 9 przypadków przewijania/overflow przeszło.
5. R1 Designer: P3 mobilnego commitu i wyników Library poniżej folda. Krótki commit jest widoczny; pierwszy wiersz przy 1280×720 mieści się na y661–718, przycisk Import na y661–701.
6. Copy: poprawiono opis członka, eksportowanego pliku, źródła oraz ćwiczenia tokena. Nowy Source commit przeszedł odczyt redakcyjny po zmianie.
## Dowody
- [Raport](qa/report.json): 21 zrzutów 1280×720, 820×720, 390×720, bez overflow, błędów JS i naruszeń axe WCAG A/AA; dodatkowa macierz 42 stanów bez wycieku restricted.
- [Przepływy](qa/s06-flow.json): 9/9 grup PASS; zmieniony eksport 5540 B, SHA d3e3c91750bfd0bbc13e30bbf2d6a1d5398b8710b69a5c37796a9d4825bb3168; zachowany frontmatter, focus i powrót przez zależności.
- [Responsive](qa/s06-responsive.json), [tabele](qa/s06-tables.json), [fold](qa/s06-fold.json): klawiatura, menu, kontekst i czytelność.
- [Tokeny i kontrast](qa/token-provenance.json): body15,08:1, secondary9,17:1, przycisk orange6,71:1, istotny border≥3,96:1, focus6,48:1.
- Build TypeScript/Vite PASS. Ostrzeżenie o głównym chunku ~639 kB pozostaje; lokalny fixture nie dowodzi p95 ani wydajności 10 tys. skilli.
- Owner bez logo rozpoznał przegląd rewizji, źródło, decyzję i przekazanie do Git. To test syntetyczny, bez zaliczenia U4 AC5.
## Przegląd
R1 Owner: P1=0/P2=0/P3=0. R1 Designer: P1=0/P2=1/P3=2; wszystkie poprawki wykonane.
R2 Owner i Designer: wspólne P2 — test wybierał nazwany Panel zamiast kontenera DataTable.
R3: poprawiony selector i raport potwierdzają 7 realnych przewinięć ArrowRight, 2 przypadki bez potrzeby scrolla; obaj recenzenci P1=0/P2=0/P3=0.
Final result: passed
