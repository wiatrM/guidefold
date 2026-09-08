from pathlib import Path
p=Path('../../docs/ui/UI.md');s=p.read_text()
start=s.index('## 5.');end=s.index('## 6.',start)
s=s[:start]+"""## 5. Plan frontendu
Kanoniczny plan portu: [07-frontend](pipeline/07-frontend.md), 2026-09-06; formalne przeglądy w toku. Ta sekcja podaje granice, nie drugą listę zadań.

| Obszar | Decyzja |
|---|---|
| Stack | React 19.2.8, TypeScript 7.0.2, Vite 8.2.2, Router DOM 7.18.3; CSS Modules bez biblioteki komponentów. Node22.14/pnpm10.30, wersjonowane lockfile. |
| ui/ | src/tokens, components≤14, routes/app, domain/data, przyszła warstwa api, test/e2e/qa. Formularze i lifecycle nie są komponentami biblioteki. |
| Dane | Fixture i API mają oddzielne adaptery do jednego kontraktu; typy OpenAPI i dekodowanie runtime. Produkcja pobiera summary/cursor, body dopiero w szczególe. |
| Backend | Modularne Go API i osobny worker, Postgres/GCS, WorkOS przez Go. Brak mikroserwisów na widok i dodatkowego Nest BFF. |
| Sesja | Cookie HttpOnly/Secure, CSRF i membership per request; bez sekretów w JS. Zmiana org anuluje requesty i odrzuca spóźnione wyniki starej generacji. |
| Offline/degraded | Publiczny fixture lokalnie. Prywatny snapshot tylko w RAM i po świeżym potwierdzeniu dostępu; brak łączności do auth zasłania dane. 401/403/logout/zmiana org czyści cache i szkice. |
| Mutacje | Idempotency key + expected revision; 409 wymaga ponownego review. Bez optymistycznego published i bez automatycznej duplikacji zapisu po timeout. |
| Stany | Macierz siedem tras × empty/loading/partial/error/degraded/restricted w 07; restricted ma pierwszeństwo. |
| Budżet | U4 AC2: 10k, p95≤2s w realnej sieci; docelowo strona50 summary, lazy map/body i limity renderu. Dodatkowe budżety są jawnymi założeniami. |
| Kontrole | Vitest5/Testing Library, Playwright owner flow i izolacja org, axe w CI, niezależny pixel diff. Pilot AC5 wymaga prawdziwych ludzi. |

Etap 8 dostarcza wydzielony frontend na fixture; integracja Go/auth/worker i produkcyjny test Git mają własne zależności. F1–F15 w 07 to małe kroki frontendu, nie estymacja całego backendu.
Hi-fi pozostaje niezależnym renderem sprzed ekstrakcji. Galeria jest narzędziem developerskim poza nawigacją U4; jej baseline nie może importować komponentów ui.
ui/ jest oddzielne od skills/guidefold; frontend nie trafia do paczki konsumenckiego skilla. Plan nie dodaje komend guidefold ui/import/login/install do istniejącego CLI.

"""+s[end:]
s=s.replace('§5 jest szkicem do weryfikacji w etapie 7.','§5 odsyła do planu etapu 7, obecnie w przeglądzie.')
p.write_text(s)
