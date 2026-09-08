# Narzędzia pipeline UI
Status: artefakty wykonanej pracy, 2026-09-06. Cel: odtworzenie wskazanych kontroli; indeks i wejścia: [pipeline](../../docs/ui/pipeline/README.md). Nie zastępują komend bieżącego [ui](../../ui/README.md).
Uruchomienia dotyczą wyłącznie Meridian fixture. Skrypty przeglądarkowe korzystają z zależności tego katalogu; pracuj z jego katalogu roboczego, chyba że skrypt wskazuje inaczej.
| Narzędzia | Zastosowanie |
|---|---|
| fixture.py | Ekstrakcja jawnych danych Meridian; generowany wynik i SHA należy sprawdzić przed aktualizacją artefaktów. |
| audit-wireframes.mjs, s04-owner-check.mjs | Stan low-fi oraz dokładny eksport etapu 4. |
| s05-*.mjs | Zapisane scenariusze symulacji/regresji etapu 5. Nie zastępują sesji z nowymi agentami ani prawdziwymi uczestnikami. |
| audit-hifi.mjs, s06-*.mjs | Viewporty, ścieżki, tabele i widoczność treści etapu 6. |
| inventory-hifi-copy.mjs, audit-tokens.py | Inwentarz copy oraz pochodzenie tokenów/kontrast. Raport historyczny należy odróżnić od wyniku ponownego uruchomienia. |
| freeze-hifi.mjs | Jednorazowe utrwalenie referencji sprzed ekstrakcji; istniejący manifest blokuje nadpisanie. Nie używaj do akceptowania zmian ui/. |
| check-final-docs.py | Z root repo: linki dokumentów i limity długości pipeline’u. |
| fix-*, update-*, close-*, setup-ui.py, add-gallery-route.py i pozostałe edytory | Historyczne, jednorazowe pomocniki tej pracy; nie są procedurą aktualizacji projektu. Nie uruchamiaj ich na bieżących źródłach. |

Pozostawione COMPONENT-CONTRACT.md w prototypie i ui/ są zapisem koordynacji ekstrakcji. Bieżące kontrakty znajdują się w [08-components](../../docs/ui/pipeline/08-components.md) i implementacji.
