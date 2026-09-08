# Architektura pivotu: React + Go API + worker

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument określa granice systemu. Plan frontendowy rozwija pipeline UI, a prototyp nie potwierdza wdrożenia API ani izolacji organizacji.

**Status: rekomendacja MVP po recenzji CTO, 2026-09-06; nie wdrożona zmiana.** Zakres: [PRD](PRODUCT-PIVOT.md), decyzja: [ADR-0031](adr/ADR-0031-monorepo-to-managed-skill-library.md), historie: [backlog](PIVOT-BACKLOG.md).

## Decyzja

Frontend w **React/Vite**, backend w **Go jako modularna aplikacja**, z **osobnym procesem/kontenerem workera** do długich operacji. Jedna baza Postgres, GCS na pakiety i WorkOS do tożsamości. W MVP nie tworzymy mikroserwisu na każdy use case.

Oddzielamy ścieżkę szybkiego SEARCH/USE od pracy importu i modeli. To rzeczywista potrzeba odrębnych zasobów i restartów. U7–U11 współdzielą katalog, źródła, rewizje i review; rozdzielenie ich na usługi zamieniłoby lokalne transakcje w przepływy sieciowe bez dowiedzionej korzyści.

## Go czy NestJS

| Kryterium | Go | NestJS |
|---|---|---|
| Obecne repo | Istnieją SEARCH/USE, integer BM25F, snapshoty, graf, ledger i testy | Nowa warstwa albo migracja tej logiki |
| Nowe endpointy produktu | Potrzebny jawny podział modułów i middleware | Moduły, dependency injection i dekoratory mogą przyspieszyć pracę zespołu TS |
| React | Kontrakt HTTP/OpenAPI i generowane typy; różny język nie jest przeszkodą | Wspólny TypeScript ułatwia tooling, lecz nie zastępuje walidacji kontraktu |
| Joby | Postgres queue/lease i osobny worker; semantykę niezawodności implementujemy | BullMQ ma integrację, ale dodaje Redis; Postgres joby wymagają osobnego rozwiązania |
| Ryzyko zmiany | Rozbudowa znanego kodu, bez ponownego wdrożenia rankera | Koszt migracji/parytetu albo dwóch backendów |
| Kompetencje | Domyślny wybór przy istniejącym kodzie i zdolności zespołu do pracy w Go | Rozważyć, gdy rzeczywisty zespół zdecydowanie lepiej zna Nest/TS |

**Wybrać Go.** To decyzja o koszcie dostarczenia tego produktu, nie twierdzenie, że Go zawsze jest szybsze lub lepsze. NestJS obsługuje zarówno modułowy monolit, jak i mikroserwisy; jego wybór nie wymusza podziału usług. [Nest modules](https://docs.nestjs.com/modules), [Nest microservices](https://docs.nestjs.com/microservices/basics), [Nest queues](https://docs.nestjs.com/techniques/queues), [Go net/http](https://pkg.go.dev/net/http)

Pełny rewrite do NestJS wymagałby ponownego odtworzenia kontraktów i walidacji. Wariant Nest control plane + Go retrieval jest uzasadniony dopiero przy silnej przewadze kompetencji lub osobnym zespole TS. Przy obecnym założeniu dwóch inżynierów dodaje runtime, granicę auth, wersjonowanie i koordynację publikacji. Nie wybieramy go na start.

## Granice modułów

To docelowe granice odpowiedzialności w jednej bazie kodu Go. Dzisiaj duża część serwisu jest w package main; podział wymaga stopniowej pracy, nie pełnego rewrite.

| Moduł | Własne dane i operacje | Użytkowe zastosowania |
|---|---|---|
| Identity | Sesje, membership, org, instalacje/tokeny, autoryzowany kontekst org/repo | Login, organizacje, integracje |
| Import | Repo, manifest, source_revision, import_run, upload, plan joba | Skan, sync, zmiany źródeł |
| Knowledge | Skille, rewizje, scope, relacje, propozycje, provenance | Katalog, piramida, konsolidacja, strona modułu |
| Review/Publication | Decyzje, digests, eksport, walidacja pakietu/grafu, aktywacja snapshotu | Review UI, CI, drift, rollback |
| Retrieval/Delivery | SEARCH/USE, policy, budżet, odczyt opublikowanej rewizji i zasobów | Agent, onboarding, ponowne użycie |
| Telemetry/Reporting | Ledger, dedupe, agregaty, health i raporty | Feedback, usage, ocena migracji |

Moduł ma właściciela zapisu do swoich tabel. Odczyty między modułami używają jawnych interfejsów/projekcji. Worker i API mogą wykonywać kod tego samego modułu, lecz mają różne uprawnienia operacyjne. Moduł telemetryczny nie modyfikuje skilli lub membership.

## Co wdrażamy

| Proces/usługa | Co robi | Izolacja |
|---|---|---|
| React web | UI katalogu, propozycji, użycia i org | Statyczny build; tokenów administracyjnych nie ma w przeglądarce |
| Go API | Sesje, org, operacje interaktywne, SEARCH/USE, batch zdarzeń | Oddzielne pule/limity dla retrieval, management i events |
| Go worker | Parsowanie, LLM, enrichment, konsolidacja, build i publikacja | Osobny CPU/RAM/concurrency i restart; brak wykonywania kodu klienta |
| Postgres | Dane domenowe, joby, ledger, snapshoty i indeks BM25F | Role API/worker ograniczone; jedna transakcja na enqueue+zmianę stanu |
| GCS | Surowe wejścia, niezmienne paczki i dowody | Org/repo/policy i autoryzowane odwołania |
| WorkOS + dostawca LLM | Tożsamość oraz generowanie | Oddzielne zależności z timeoutami i obsługą awarii |

API i worker początkowo mają zgodną wersję kodu oraz migracji, nawet jeśli są osobnymi obrazami. Worker zawiera przypięty zaufany Python/PyYAML builder eksportujący kanoniczny router_index; obraz API pozostaje bez Pythona. Nie wykonujemy zaimportowanych skryptów ani nie piszemy drugiego portu rankera.

## Kontrakt API–worker

### Proposed external source adapter

ADR-0034 adds a server-side GitHub App adapter as a source for the Import module. The adapter owns OAuth code exchange, installation/user token handling and repository reads; domain code receives only a normalized repository/ref and manifest bytes. The Chrome extension is a client adapter, not a trust boundary or token store. This remains Proposed until the management API and worker contract are versioned together.

Job: schema_version, org_id, repo_id, import_id, etap, input_manifest_digest, recipe_version/model_revision, idempotency_key, limit pracy/wydatku i generation/fencing token. Enqueue i zmiana stanu odbywają się w jednej transakcji.

Worker sprawdza aktualne uprawnienie operacji i tożsamość org, odnawia lease, zapisuje checkpointy. Wynik starej generacji nie może nadpisać nowszego. Cache generowania i deduplikacja obejmują org i wersje wejść. Zmiana źródła unieważnia propozycję opartą na starej treści.

Publikacja jest transakcją aktywującą tylko zwalidowany snapshot przypisany do zatwierdzonego digestu. Ready importu nie oznacza published. Niepewne opłaty za timeout LLM są rejestrowane; koszt całego przebiegu łączy import_id.

## Najpierw trzy techniczne bramki

1. **Tożsamość per request.** Obecny Store ma Tenant/Repo oraz jeden cached Catalog; nie wolno mutować ich dla kolejnych użytkowników. Wprowadzić ograniczony cache org/repo/snapshot/policy i test równoległych A/B z takim samym repo_id/URN, ciepłym cache, retry i rollbackiem. Dane administracyjne i worker podlegają tej samej granicy.
2. **Kontrakt pakietów i zależności.** Obecny USE zwraca body, a closure jest ograniczone do dwóch poziomów. Nowy kontrakt projektowany jako 1.2 opisuje wymagane zasoby, pełne requires, budżety, już załadowane zależności, traversal i cannot_fit/unresolved. Stary 1.1 nie otrzymuje nowych gwarancji przez zmianę etykiety. Testy: głęboki łańcuch, diament, >4 karty, denied, zmiana snapshotu i 409.
3. **Zaufana publikacja.** Builder i walidator muszą zachować aktualną zgodność indeksu. Rewizja obejmuje manifest zasobów, nie tylko body. Retencja surowego uploadu nie usuwa aktywnego pakietu ani zależności potrzebnych do rollbacku.

Źródła lokalne: [Store](../services/search/store.go), [routing](../services/search/routing.go), [API](../services/search/main.go), [kontrakt](HARNESS-SERVICE-CONTRACT.md). Są to ustalenia z odczytu kodu, nie z ponownego uruchomienia testów.

## Kiedy wydzielić mikroserwis

Progi poniżej są propozycją decyzji, a nie wynikami obecnych pomiarów.

| Obszar | Pierwsza reakcja | Warunek rozważenia osobnej usługi |
|---|---|---|
| Retrieval | Oddzielne pule i limity, profiling | Po izolacji pul współdzielenie procesu nadal powoduje SEARCH p95 >1 s w 3 kolejnych 15-min oknach uzgodnionego obciążenia |
| Processing | Więcej workerów i kolejki z limitami etapów | Różne zasoby, np. GPU, albo stałe blokowanie innych etapów mimo limitów; oddzielamy rodzaj workera |
| Raporty | Asynchroniczne agregaty/projekcje | Agregacje >30% czasu DB w szczycie i zmierzona szkoda dla SLO; osobny proces/usługa dopiero po ocenie obciążenia DB |
| Zespół | Moduły i jawne interfejsy | Dwa zespoły wymagają niezależnych wydań, a wspólny release blokuje ≥2 wdrożenia/mies. przez 2 miesiące |

Każde wydzielenie potrzebuje ownera, kontraktu, SLO, planu migracji danych i dowodu, że poprawia ograniczenie. Samo dodanie sieciowego hopa nie rozwiązuje współdzielonego przeciążenia bazy. Use case nie jest automatycznie granicą usługi.
