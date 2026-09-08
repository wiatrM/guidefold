from pathlib import Path
p=Path('../../docs/ui/pipeline/07-frontend.md');s=p.read_text()
s=s.replace('jedna warstwa fetch z AbortController i generacją org','jedna warstwa fetch z AbortController, generacją dostępu oraz numerem żądania zasobu')
s=s.replace('cache RAM z kluczem user/org/repo/snapshot/policy','cache RAM: namespace user/org/repo/policy i pełny klucz operacji/zasobu/query')
s=s.replace('Hi-fi pozostaje niezależnym punktem odniesienia.','Czyste lineDiff/digest i typy nie importują fixture; adapter danych jest wstrzykiwany przy składaniu aplikacji. Produkcyjna granica API nie importuje danych Meridian.\nHi-fi pozostaje niezależnym punktem odniesienia.')
s=s.replace('cursor + snapshot_id; bez body. Każdy skill ma pełną ścieżkę źródła dostępną na żądanie.','cursor + snapshot_id; bez body. Opcje scope/owner/layer/status pochodzą z autoryzowanego kontraktu facets z tego snapshotu, niezależnie od strony wyników.')
s=s.replace('Obecne SEARCH/USE i events:batch zachowują','Facets obsługują wyszukiwanie/stronicowanie wartości; aktywna wartość z URL ma osobny lookup i pozostaje widoczna także poza bieżącą stroną. Nieznana/niedostępna wartość daje jawny błąd filtra, nie cichy powrót do All. Nie pobieramy katalogu lub body, aby zbudować select.\nObecne SEARCH/USE i events:batch zachowują')
s=s.replace('Każda mutacja wiąże idempotency_key','Klucz cache obejmuje operację, ID zasobu, content/package revision, snapshot i znormalizowane filtry/cursor; namespace dostępu nie wystarcza. Numer aktywnego żądania zasobu odrzuca starszą odpowiedź także przy zmianie filtrów/rewizji w tej samej org; anulowanie jest dodatkową optymalizacją.\nKażda mutacja wiąże idempotency_key')
s=s.replace('Wylogowanie, 401/403 lub zmiana user/org/policy','U3 AC4 wymaga odwołania dostępu do 60 s. Projekt: potwierdzenie dostępu ważne maks. 45 s od rozpoczęcia requestu, odnowienie co 25 s z timeoutem 5 s; niepotwierdzone odnowienie nie przedłuża ważności. Deadline zasłania prywatny widok. Ukrycie karty zasłania dane, a wznowienie wymaga sprawdzenia przed odsłonięciem; API egzekwuje niezależnie własne odwołanie. To kontrakt Guidefold, nie SLA WorkOS.\nWylogowanie, 401/403 lub zmiana user/org/policy')
s=s.replace('Vitest: kontrakty komponentów, dekodery, konflikty rewizji i odrzucanie spóźnionej odpowiedzi org A po przejściu do B.','Vitest: kontrakty komponentów, dekodery, konflikty rewizji, odpowiedź org A po przejściu do B oraz odwrócona kolejność filtrów/rewizji w jednej org.')
s=s.replace('Etap 8 sprawdza lokalny fixture i symulację Git.','U4 AC3/AC4: sprawdzamy dokładny host/plik/commit linku Git oraz cały login→import→lista→review wyłącznie klawiaturą, w tym focus po zmianie stanu. Osobny test odwołuje membership przy bezczynnej stronie/ciepłym cache i po wznowieniu karty; odsłonięcie danych nie przekracza 60 s.\nEtap 8 sprawdza lokalny fixture i symulację Git.')
start=s.index('| Krok / nakład FE |')
s=s[:start]+"""| Krok / nakład FE | Zależność | Gotowe |
|---|---|---|
| F1 0,5 d — freeze referencji | Zamknięte 06 | Niezależne obrazy i hash źródeł galerii przed ekstrakcją. |
| F2 1 d — czyste funkcje i adapter | F1 | lineDiff/typy bez importu fixture, jawne składanie adaptera. |
| F3 1 d — pierwsze 7 komponentów | F2 | Kontrakty/testy/stories oraz zgodny render. |
| F4 1 d — kolejne 7 | F3 | ≤14 eksportów, kontrakty a11y/state bez sprawl. |
| F5 1 d — shell i Import/Organization | F4 | URL, rola fixture, lokalny onboarding i member/owner. |
| F6 1 d — Library/Map/Skill | F5 | Filtry/powrót, trzy osie, immutable source i feedback. |
| F7 1 d — Proposals/Usage | F6 | Lokalny lifecycle, edycja, dokładny eksport i rozdzielone dowody. |
| F8 1 d — galeria i wizualne QA | F4–F7 | Wszystkie stories, stany i niezależny pixel diff. |
| F9 1 d — CI i odbiór fixture | F8 | Build/Vitest/axe zielone; pełna ścieżka klawiaturą i host/plik/commit Git (etap 8). |
| F10 1 d — klient i dekodery API | OpenAPI Go, tenant cache z bramki CTO | GET/error/cancel i testy A/B, filtrów/rewizji w odwróconej kolejności. |
| F11 1 d — callback UI i org entry | Go auth/CSRF i testowy WorkOS | Google/GitHub/logout; deadline 60 s przy otwartej i wznawianej karcie. |
| F12 1 d — manifest i postęp | API import/job/idempotency | accepted/omitted/failed i bezpieczny retry. |
| F13 1 d — katalog i opcje | API stron + facets/lookup | Filtry/cursor bez body; owner/scope spoza strony 1 i odtworzenie URL. |
| F14 1 d — trzy osie Map | API children/relations | Lazy fragment, limit i dostępność każdego obiektu. |
| F15 1 d — szczegół i feedback | API rewizji/feedback | Immutable body/mismatch, epizod i właściwy host/plik/commit linku Git. |
| F16 1 d — decyzja i konflikt | API proposals/409 | Powód/diff, brak zapisu na starym źródle. |
| F17 1 d — eksport i status | Pakiety1.2 oraz Git validation/sync | Eksport zgodny z digestem, published z dowodu API. |
| F18 1 d — usage/quality | Ledger/agregaty/watermark | Unknown i mianownik; kolejka z przyczyną. |
| F19 1 d — org/integrations | Membership, token API i adapter | Last owner, revoke i observed health bez fałszywego sukcesu. |
| F20 1 d — integracyjne R | F11–F19, testowe org A/B/repo | Realny owner flow klawiaturą, Git links i revoke≤60 s przy ciepłym cache. |
| F21 1 d — profil i pilot Q | R zielone, dane10k i uczestnicy | Raport pomiaru; AC2/AC5 zaliczone albo jawnie niezaliczone. |

## Przegląd
R1 — Owner P1=0/P2=1/P3=0; Principal 0/3/0; Architekt 0/1/0. Pięć P2: odbiór AC3/4, pełna tożsamość żądania, facets, kroki portu oraz czas odwołania dostępu.
R2 — w toku; etap 8 nie rozpoczyna się przed 0 otwartych P1/P2.
"""
p.write_text(s)
p=Path('../../docs/ui/UI.md');s=p.read_text()
s=s.replace('Zmiana org anuluje requesty i odrzuca spóźnione wyniki starej generacji.','Potwierdzenie ważne maks.45 s, odnowienie co25 s; brak odnowienia zasłania dane. Wznowienie karty wymaga sprawdzenia. Odwołanie≤60 s ma test przy bezczynnym widoku/ciepłym cache.')
s=s.replace('Produkcja pobiera summary/cursor, body dopiero w szczególe.','Produkcja pobiera summary/cursor i osobne facets/lookup; body dopiero w szczególe. Pełny klucz query/zasobu i numer żądania blokują starsze odpowiedzi.')
s=s.replace('Playwright owner flow i izolacja org, axe w CI','Playwright owner flow wyłącznie klawiaturą, poprawny Git host/plik/commit i izolacja org, axe w CI')
s=s.replace('F1–F15 w 07','F1–F21 w 07')
p.write_text(s)
