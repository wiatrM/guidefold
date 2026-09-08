# ADR-0033: Contract-first management API, a separate `gfm` schema, and blobs plus jobs in Postgres for the MVP

**Status:** Proposed · 2026-09-06 · propozycja po napisaniu wiążącego kontraktu API dla pivotu; nie deklaracja wdrożenia.
**Proposes amendments to:** [ADR-0018](ADR-0018-skills-stay-in-monorepo-one-postgres-gcs.md) (GCS jako miejsce artefaktów w MVP), [ADR-0026](ADR-0026-native-search-paradedb-compose.md) (profil bazy: ParadeDB przestaje być wymagane do uruchomienia migracji).
**Builds on:** [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md) (zakres pivotu), [ADR-0032](ADR-0032-engineering-principles-and-hexagonal-architecture.md) (porty i adaptery, reguły przeglądu).
**Governs:** [docs/API-CONTRACT.md](../API-CONTRACT.md), `services/search/openapi/management-v1.yaml`, `services/search/internal/**`, `ui/src/api/`, komendy sieciowe CLI, `tools/contract/check_api_contract.py`.

## Context

Pivot dokłada do istniejącej usługi SEARCH/USE cały control plane: tożsamość, organizacje, import, wiedzę, review, publikację i raporty. Prace nad backendem Go, UI i CLI idą równolegle, w trzech drzewach kodu, z roboczego briefu trzymanego poza repozytorium. Brief nie miał wersji, nie był indeksowany przez [DOCUMENTATION-RULES](../DOCUMENTATION-RULES.md) i nie dało się go sprawdzić maszynowo, więc każda rozbieżność między handlerem, migracją i dekoderem UI ujawniała się dopiero przy integracji.

Odczyt kodu z 2026-09-06 pokazuje, że rozbieżności już powstały: `internal/mgmt` używa `csrf_token_mismatch`, `insufficient_token_scope` i `organization_required`, a brief mówił o `csrf_token_invalid`, `insufficient_scope` i braku tego trzeciego; `ui/src/api/decoders.ts` nie zna stanu importu `uploading`, który opisuje maszyna stanów. Żadna z tych różnic nie jest błędem projektowym — są skutkiem braku jednego, wersjonowanego dokumentu.

Równocześnie środowisko pilota nie ma ani Dockera, ani rozszerzeń `pg_search`/`vector`, a przewidywany wolumen pierwszego wdrożenia to jedno repo, ~200 skilli i do 100 MiB wybranych źródeł na import.

## Proposed decision

1. **Kontrakt przed kodem.** [docs/API-CONTRACT.md](../API-CONTRACT.md) jest źródłem prawdy dla endpointów, DTO, kodów błędów, maszyn stanów, schematu bazy i kontraktu API–worker. Handler, tabela, migracja, job, DTO, dekoder UI i komenda sieciowa CLI zmieniają się wyłącznie razem ze zmianą tego dokumentu w tym samym PR. Kontrakt może wyprzedzać kod; kod nie może wyprzedzać kontraktu. Regułę egzekwuje skill [`api-contract`](../../.agents/skills/api-contract/SKILL.md) i `tools/contract/check_api_contract.py` (`DRIFT` dla kodu bez wpisu, `INFO` dla wpisu bez kodu).
2. **`contract_version` jest wersją tego kontraktu**, niezależną od `schema_version` ładunku. Zmiana addytywna podnosi MINOR/PATCH; zmiana znaczenia pola wymaga MAJOR i nowego `schema_version` (`mgmt-2`, `1.3`). 1.1 nie otrzymuje nowych gwarancji przez zmianę etykiety (bramka 2 z [PIVOT-ARCHITECTURE](../PIVOT-ARCHITECTURE.md)).
3. **Dwa schematy w jednej bazie.** Katalog serwowania zostaje w `gf` i jest dla roli API tylko do odczytu (poza appendem do `gf.events` i `gf.search_shadow`); pisze go wyłącznie job publikacji. Nowe dane zarządcze idą do `gfm`. Każdy wiersz organizacyjny w `gfm` ma `org_id`, a każdy klucz złożony zaczyna się od `org_id`, więc zapytanie bez predykatu tenanta nie może połączyć organizacji — izolacja z konstrukcji, nie z dyscypliny autora zapytania.
4. **Profil plain Postgres.** Migracja musi przechodzić bez `pg_search` i bez `pgvector`; `CREATE EXTENSION` biegnie w bloku wyjątku, kolumny i tabele wektorowe powstają tylko przy obecnym typie, a indeks BM25 tylko przy zainstalowanym rozszerzeniu. Domyślny silnik `router` czyta `gf.router_terms` i nie zależy od żadnego z nich. ParadeDB pozostaje profilem opcjonalnym, nie warunkiem startu.
5. **Bloby i kolejka jobów są w Postgres w MVP.** `gfm.blobs` przechowuje treść adresowaną hashem, per organizacja; `gfm.jobs` jest kolejką z lease, heartbeatem, checkpointem i fencingiem po `generation`. Powód: jedna transakcja dla enqueue razem z wierszami, które job uzasadniają, jeden model uprawnień i jedno miejsce retencji. GCS pozostaje portem wyjściowym (`BlobStore`: `Put`/`Get`/`Stat`/`Delete`), nie zależnością MVP; przejście to zmiana adaptera i przepisanie zawartości, bez zmiany kontraktu.
6. **Telemetria zostaje w `gf.events`.** UI, adapter i raport używają tej samej definicji zdarzenia; feedback z UI zapisuje `skill_feedback` do ledgera zamiast tworzyć drugą tabelę ocen. Agregaty muszą zgadzać się z `tools/telemetry/report.py` dla tego samego zbioru zdarzeń.
7. **Nazwy konkretne wygrywają z nazwami z briefu**, gdy nie są sprzeczne z architekturą. Kontrakt przyjmuje nazwy z `internal/mgmt` i `internal/identity` (`csrf_token_mismatch`, `insufficient_token_scope`, `organization_required`, `provider_unavailable`) i to one obowiązują dalej.

## Deployment

Worker działa jako osobny obraz i osobny Deployment, nie jako proces w API. `services/search/Dockerfile` jest bez Pythona (obraz API, sam binarny `guidefold-search`); `services/search/Dockerfile.worker` dokłada do tego samego binarnego Pythona 3 i PyYAML, potrzebne wyłącznie `tools/worker/build_tree.py` przy jobie `import.parse`. Szablon Helm (`deploy/k8s/chart/templates/worker.yaml`) tworzy Deployment bez Service — worker nie przyjmuje ruchu przychodzącego, tylko odpytuje `gfm.jobs` — z domyślną polityką sieciową deny-all; `worker.enabled`, `worker.image` i `worker.generator` (`none|deterministic|openai|anthropic`) są polami w `values.yaml`. Reguły ingressu i model immutable-release z [ADR-0030](ADR-0030-immutable-service-releases-on-kubernetes.md) nie zmieniają się: worker dołącza do tej samej instalacji, dzieli `credentialsSecret` (tylko `app-password`) i jest wiązany do release'u tym samym `k8s_release.py` co API.

## Consequences

- Powstaje dokument, który recenzent może sprawdzić maszynowo, i test, który zawodzi, gdy kod wyprzedzi kontrakt. Koszt: każdy PR dotykający API ma dodatkowy plik do zmiany i wiersz changelogu.
- Zamknięta lista kodów błędów oznacza, że dopisanie kodu w handlerze bez wpisu w §3 zatrzymuje bramkę. To jest cel; to także oznacza, że agent implementujący nowy moduł najpierw pisze wiersze kontraktu.
- Pierwsze uruchomienie nie wymaga Dockera, ParadeDB ani GCS. W zamian Postgres przyjmuje ruch blobów i kolejki; przy większym wolumenie decyzja 5 zostanie ponowiona z pomiarem, nie z przeczuciem.
- `gf` nie jest przepisywane. Kolumny można dopisywać, semantyki `tenant`/`repo`/`snapshot_id` nie zmieniamy, a `tenant` równa się `org_id`; to wiąże istniejący retrieval z nowym modelem organizacji bez migracji danych.
- Status Proposed: dokument opisuje zachowanie docelowe. Dowodem wdrożenia pozostają kod, testy i raport z identyfikatorem przebiegu.

## References

[API-CONTRACT](../API-CONTRACT.md) · [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) · [PIVOT-ARCHITECTURE](../PIVOT-ARCHITECTURE.md) · [PIVOT-BACKLOG](../PIVOT-BACKLOG.md) · [HARNESS-SERVICE-CONTRACT](../HARNESS-SERVICE-CONTRACT.md) · [SEARCH-USE-TELEMETRY](../SEARCH-USE-TELEMETRY.md) · [07-frontend](../ui/pipeline/07-frontend.md)
