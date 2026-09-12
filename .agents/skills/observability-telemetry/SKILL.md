---
name: observability-telemetry
description: Record and report Guidefold evidence correctly: event ledger, dedupe, unknown-not-zero, run identifiers, local spool files and LLM cost per import. Use when emitting events, writing reports or adding metrics; not for changing what SEARCH/USE return.
---

# Obserwowalność i telemetria

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każde zdarzenie i raport da się przypisać do przebiegu, rewizji i org, a brak danych pozostaje brakiem.
Źródło: [SEARCH-USE-TELEMETRY §4, §5, §7](../../../docs/SEARCH-USE-TELEMETRY.md), [CONVENTIONS §11](../../../docs/CONVENTIONS.md), [DOCUMENTATION-RULES, Nowe pliki](../../../docs/DOCUMENTATION-RULES.md), [PRODUCT-PIVOT §11 i U11 AC7](../../../docs/PRODUCT-PIVOT.md), [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Emituj zdarzenia z pełną tożsamością

- Każde zdarzenie niesie `schema_version`, `event_id`, `event_type`, `occurred_at`, `producer`, wersję adaptera, środowisko (`pilot`/`eval`/`dev`) oraz `session_id`, `task_id`, `correlation_id`, gdy są. Brak ID to jawne unknown, wykluczone z proporcji per zadanie.
- Zdarzenie o skillu niesie URN i dokładną niezmienną rewizję; nierozwiązane żądania zachowują selektor i nie wchodzą do wyników per rewizja. Nigdy nie łącz rewizji w jedną ocenę bez filtra wersji.
- Zapisz `index_snapshot`, `model_profile`, `router_version`, `policy_version`, tryb cache. Klucz cache zawiera granicę autoryzacji.
- Telemetria nie modyfikuje skilli, membership ani odpowiedzi SEARCH/USE; zapis do bazy nie warunkuje zwrotu odpowiedzi.

## Rozróżniaj obserwacje

| Zdarzenie | Znaczy | Nie znaczy |
|---|---|---|
| `search_results` | Serwer wybrał karty | Że adapter je wstrzyknął |
| `card_injected` | Adapter dodał `card_context` | Że model użył treści |
| `skill_load_completed` (`load_id`) | Body pobrane i sprawdzone sumą | Wykonanie zadania |
| rezultat zadania / judgment | Ocena z `judgment_id`; korekta wskazuje poprzednią | Drugi głos tego samego oceniającego |

Ledger jest append-only z unikalnym `(tenant_id, event_id)`; duplikat transportu to nie drugie użycie. Rollupy liczą unikalne epizody `(tenant, task, skill, revision)`; liczbę wywołań trzymaj osobno jako diagnostykę. Brak zdarzeń to Unknown, nie 0 %.

## Znaj pliki lokalne

Wszystko pod `.guidefold/telemetry/` (gitignored): `spool/<tenant|local>/<env>/events-<date>.jsonl` (append-only, 10 MB / 7 dni, bez promptu i tokenów), `.health.json` (liczniki za `guidefold telemetry status`), `hmac-key-<YYYY-MM>.bin` (nie opuszcza hosta), `ledger.sqlite3` (serwer referencyjny, poza ZIP-em skilla), `shadow-<date>.jsonl` (E1.6, tylko `find --experimental`). `telemetry flush` drenuje tylko po `accepted`/`duplicate`, nigdy z hooka. Spool jest partycjonowany po pierwotnym tenant/pseudonimie; zmiana logowania kwarantannuje starą partycję zamiast ją przepisać.

## Raportuj z identyfikatorem przebiegu

Warstwę wizualizacji telemetrii obowiązkowo migruj według [spectrum-charts-migration](../spectrum-charts-migration/SKILL.md) i [UI §7](../../../docs/ui/UI.md#7-obowiązkowa-migracja-spectrum-charts); nie zmienia to powyższego kontraktu zdarzeń.

Raport podaje komendę, środowisko, fixture lub dane rzeczywiste, identyfikator przebiegu (`search_id`, `import_id`, run id), rezultat i ograniczenia. Guardrails: p50/p95 klienta i całego hooka, timeouty/fallback, ukończenie load, kolejka, koszt na 1 000 żądań; obok nieautoryzowane ujawnienia (cel zero) i pokrycie dostarczania zdarzeń. Slice offline/denied/error publikowane, nie usuwane z mianownika. Koszt LLM łączony przez `import_id`: tokeny, wywołania, retry, opłaty pewne i niepewne (timeout), wall time, minuty review; koszt na zaakceptowany skill przy zerze akceptacji jest niedostępny.

## Sprawdź przed zakończeniem

- Nowe zdarzenie ma `schema_version`, typ w słowniku §3 i test deduplikacji po `(tenant_id, event_id)`.
- Zapytanie użytkownika, body skilla i bearer token nie trafiają do spoola ani logów.
- Agregat zwraca Unknown przy braku zdarzeń; test to sprawdza.
- Raport w PR zawiera komendę, środowisko i identyfikator przebiegu.
- Żadna metryka nie miesza rewizji bez filtra wersji.
