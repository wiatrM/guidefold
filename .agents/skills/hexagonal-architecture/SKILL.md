---
name: hexagonal-architecture
description: Required ports-and-adapters structure for new Guidefold Go (API/worker) and React code, and the Registry port in the CLI. Use when creating a module, handler, repository, data loader or route, and when deciding where a piece of logic lives. Not a mandate to rewrite existing package-main code at once.
---

# Architektura heksagonalna (porty i adaptery)

Status: aktywna reguła repozytorium, wymagana dla nowego kodu. Data: 2026-09-06.
Cel: domena (reguły importu, wiedzy, review, retrieval) nie zna HTTP, SQL, GCS, WorkOS, LLM, `fetch` ani DOM; wszystko to są adaptery za portami zdefiniowanymi przez domenę.
Źródło: [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) ("Granice modułów", "Co wdrażamy"), [UI](../../../docs/ui/UI.md) §5, [07-frontend](../../../docs/ui/pipeline/07-frontend.md), [ADR-0003](../../../docs/adr/ADR-0003-bootstrap-skill-cli-not-mcp.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal kierunek zależności

Zależności wskazują do środka: adapter → aplikacja → domena. Domena nie importuje niczego z zewnętrznego I/O. Port to interfejs zadeklarowany po stronie domeny lub aplikacji, nazwany od potrzeby (`SkillRepository`, `JobQueue`, `IdentityProvider`, `SkillSource`), nie od technologii (`PostgresClient`).

| Warstwa | Go (proponowany układ, dziś kod jest w `package main` w `services/search`) | React (`ui/src`, układ z [07-frontend](../../../docs/ui/pipeline/07-frontend.md)) | CLI |
|---|---|---|---|
| Domena | `internal/<module>/domain`: typy, reguły, błędy domenowe; testy bez I/O | `domain/`: typy, parsery, decyzje (np. `diff.ts`, `skill.ts`) | funkcje czyste: URN, karty, ranking |
| Porty | `internal/<module>/ports`: interfejsy wejściowe (use case) i wyjściowe (repo, queue, provider) | kontrakt danych: typy z OpenAPI i dekodowanie runtime | klasa `Registry` jako port (ADR-0003: wymienna na MCP/ARD) |
| Aplikacja | `internal/<module>/app`: use case'y, transakcje, autoryzacja per request | hooki/loadery składające porty dla tras | komendy w `main()` |
| Adaptery | `internal/<module>/adapters/{http,postgres,gcs,workos,llm}` | `data/`: adapter fixture i adapter API do jednego kontraktu; `routes/`: adapter widoku | `LocalRegistry`, gcloud |

Układ Go jest propozycją; dopóki pakiet `main` nie zostanie podzielony, nowy kod wchodzi już w tej strukturze, a stary migruje stopniowo (pełny rewrite jest zakazany).

## Zakazy

- Logika biznesowa w handlerze HTTP, w komponencie React lub w komendzie CLI; handler tłumaczy request na wywołanie use case'u i wynik na odpowiedź.
- SQL, typy sterownika bazy, typy HTTP, struktury ORM i odpowiedzi WorkOS/LLM widoczne w domenie lub w sygnaturach portów.
- Adapter wywołujący inny adapter bezpośrednio (Postgres → GCS); składanie odbywa się w warstwie aplikacji.
- Domena importująca `fetch`, `window`, `document`, `net/http`, `database/sql`, `cloud.google.com/go/storage`.

## Testuj po obu stronach portu

Domenę testujesz bez I/O, na pamięciowych implementacjach portów. Adaptery testujesz kontraktowo: ten sam zestaw testów uruchamiasz na adapterze fixture i na adapterze prawdziwym (w UI: `pnpm test:contracts`; w Go: testy z tagiem integracyjnym na Postgres). Test bramki 1 z [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) (równoległe A/B z tym samym repo_id/URN) to test warstwy aplikacji, nie handlera.

## Sprawdź przed zakończeniem

- Czy nowy kod domenowy nie ma importów I/O? Go: `grep -rn '"net/http"\|"database/sql"' <domain dir>`; UI: `grep -rn 'fetch(\|window\.\|document\.' ui/src/domain`.
- Czy każdy port jest interfejsem po stronie domeny/aplikacji z nazwą od potrzeby, a nie od technologii?
- Czy handler HTTP i komponent trasy zawierają tylko tłumaczenie wejścia/wyjścia?
- Czy nowa integracja (baza, storage, dostawca) weszła jako adapter z testem kontraktowym wspólnym z fixture?
- Czy zmiana w istniejącym `package main` jest krokiem migracji, a nie nową logiką dopisaną do handlera?
