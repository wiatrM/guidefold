# Ścieżka nauki z AI i śledzenie postępów

Otwórz sciezka-nauki.html w przeglądarce. Jest to samodzielny plik, który działa bez serwera, konta i połączenia z siecią. Linki do kursów wymagają internetu.

## Nauka i postęp

Plan zakłada pracę z AI od pierwszego dnia. Pierwsze dwa tygodnie łączą podstawy Pythona z własnym skryptem, kolejne dwa z porównaniem BM25 i gotowego encodera. Mały trening rozpoczyna się po sprawdzeniu danych, metryk i zrozumieniu aktualizacji wag. Kursy ML i matematyka towarzyszą projektowi; wcześniejsze 660 godzin oznacza orientacyjny zakres materiałów, a nie warunek rozpoczęcia treningu.

Dziesięć etapów zawiera łącznie 30 sprawdzianów umiejętności. Dla każdego można zaznaczyć zadania, ustawić status, zapisać liczbę godzin i notatki. Zaliczenie etapu wymaga wszystkich jego sprawdzianów i ręcznego ustawienia statusu. Cofnięcie sprawdzianu otwiera zaliczony etap ponownie. Liczba godzin sama nie zalicza umiejętności.

## Zapis i kopia zapasowa

Zmiany zapisują się automatycznie w localStorage przeglądarki pod kluczem guidefold.learning.progress.v1. Dane należą do danej przeglądarki i miejsca otwarcia pliku. Nie ma synchronizacji urządzeń. Zmiana lokalizacji HTML-a lub wyczyszczenie danych przeglądarki może wymagać przywrócenia eksportu.

Przycisk eksportu zapisuje JSON z postępem. Import sprawdza strukturę, pokazuje podgląd i wymaga potwierdzenia zastąpienia bieżącego postępu. Przed zastąpieniem tworzy lokalną kopię poprzedniego stanu; nieudany zapis tej kopii blokuje import. Import i sam HTML nie wysyłają danych do sieci. Udostępnienie pliku HTML nie przenosi prywatnych notatek.

Gdy przeglądarka blokuje zapis, pojawia się ostrzeżenie i można pracować w pamięci oraz eksportować JSON. Uszkodzony zapis jest zachowywany do pobrania. Konflikt między kartami wymaga wyboru wersji; nie jest rozwiązywany przez ciche nadpisanie.

## Pliki i odbudowa

- sciezka-nauki.html: gotowy plik dla użytkownika.
- tracker-data.json: stabilne identyfikatory etapów oraz sprawdziany umiejętności.
- tracker.template.html i tracker.js: wygląd oraz logika aplikacji.
- artifact.json: materiały, źródła i treść ścieżki.
- build_tracker.py: odbudowa samodzielnego HTML-a; wymaga Python 3 i pakietu markdown-it-py.
- sources-notes.md: kontekst źródeł i historia zmian podejścia.
- plan.sql: historyczne dane szacunkowego zakresu nauki; nie sterują trackerem.

Odbudowa z tego katalogu: python3 build_tracker.py. Użytkownik gotowego HTML-a nie potrzebuje Pythona ani żadnych bibliotek.

## Weryfikacja

Przeszło 13 testów funkcjonalnych w Chromium na pliku file://: zapis po odświeżeniu, zaliczanie i cofanie zadań, godziny, notatki, eksport/import, anulowanie importu, błędne dane, brak miejsca na kopię, niedostępny lub uszkodzony localStorage oraz konflikty między kartami.

Sprawdzono wszystkie trzy widoki przy szerokościach 320, 390, 768 i 1440 px, etykiety pól i obsługę klawiaturą. Brak poziomego przepełnienia, błędów JavaScript oraz żądań sieciowych. Zrzuty widoku desktopowego i mobilnego sprawdzono wizualnie.

Testy: test-tracker.cjs oraz test-tracker-layout.cjs. Wymagają Node.js, Playwright i Chromium; ścieżkę przeglądarki można podać przez CHROMIUM_EXECUTABLE_PATH. Wyniki i sumy kontrolne znajdują się w qa-receipt.json, tracker-functional-qa.json oraz tracker-layout-qa.json.

Wyniki tej wersji zastępują wcześniejszy problem z renderowaniem raportu tylko do odczytu. Obecny HTML używa samodzielnego interfejsu i został sprawdzony w rzeczywistej przeglądarce.
