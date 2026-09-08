---
name: api-contract
description: Kontrakt przed kodem - docs/API-CONTRACT.md jest źródłem prawdy dla endpointów, DTO, kodów błędów, schematu gfm i kontraktu jobów. Use when changing anything under services/search, ui/src/api, ui/src/data, CLI network commands, migrations or jobs. Not for retrieval quality or UI visual work.
---

# Kontrakt API przed kodem

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: żaden endpoint, kolumna, kod błędu, DTO ani job nie istnieje w kodzie, zanim nie opisze go kontrakt w tej samej zmianie.
Źródło: [API-CONTRACT](../../../docs/API-CONTRACT.md) (§1 Zasada nadrzędna, §10 Wersjonowanie), [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md), [SEARCH-USE-TELEMETRY](../../../docs/SEARCH-USE-TELEMETRY.md), [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md). Decyzja: [ADR-0033](../../../docs/adr/ADR-0033-api-contract-first-and-mvp-storage.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD. Zasady wersji 1.1/1.2 rozwija [api-contract-versioning](../api-contract-versioning/SKILL.md).

## Reguła niezmienna

**Kontrakt przed kodem.** [docs/API-CONTRACT.md](../../../docs/API-CONTRACT.md) jest źródłem prawdy. Handler, tabela, migracja, job, DTO, dekoder UI i komenda sieciowa CLI zmieniają się wyłącznie razem ze zmianą tego dokumentu w tym samym PR. Kontrakt może wyprzedzać kod; kod nie może wyprzedzać kontraktu.

## Kiedy to obowiązuje

| Zmiana | Obowiązuje |
|---|---|
| Cokolwiek w `services/search/` (trasa, DTO, migracja `internal/schema`, kod błędu, job) | tak |
| `ui/src/api/` (klient, dekodery) i `ui/src/data/apiSource` | tak |
| Komenda CLI wykonująca żądanie sieciowe (`login`, `import`, `sync`, `status`, `proposals`, `doctor`) | tak |
| Nowy `kind` joba, nowe pole `payload`/`limits`/`checkpoint` | tak |
| Ranking, korpusy, tokeny UI, treść skilla fixture | nie |

## Procedura

1. Zmień [docs/API-CONTRACT.md](../../../docs/API-CONTRACT.md): właściwa tabela endpointów (§4), DTO (§5), maszyna stanów (§6), tabela `gfm` (§7), kontrakt joba (§8), inwariant (§9). Nowy kod błędu dopisz do zamkniętej listy w §3.
2. Podnieś `contract_version` według §10 (addytywnie → MINOR/PATCH; zmiana znaczenia → MAJOR i nowe `schema_version`) i dopisz wiersz w changelogu §11.
3. Zaktualizuj `services/search/openapi/management-v1.yaml` tak, aby `paths:` zgadzały się z §4.
4. Dopiero teraz kod i testy: handler, migracja, dekoder, test z §9 nazwany bramką lub AC, które dowodzi.
5. Uruchom `python3 tools/contract/check_api_contract.py` (dopóki nie ma YAML-a: `--allow-missing-openapi`) oraz `python3 -m pytest tests/test_api_contract_doc.py`.
6. W opisie PR podaj diff kontraktu: co doszło, jaka wersja, które AC/bramka i który test to pokrywa.

Zmiana przesuwająca granicę modułu ([module-boundaries-go](../module-boundaries-go/SKILL.md)) albo dotykająca trzech bramek technicznych wymaga dodatkowo ADR ([adr-writing](../adr-writing/SKILL.md)).

## Co recenzent odrzuca

- Endpoint, kolumna, kod błędu lub `kind` joba w kodzie bez wiersza w kontrakcie; `check_api_contract.py` zgłasza to jako `DRIFT`.
- Zmiana znaczenia istniejącego pola bez nowej wersji; nowa gwarancja dostawy dopisana do 1.1 przez zmianę etykiety.
- Odpowiedź bez `request_id`, `schema_version` lub `Cache-Control: no-store`; mutacja bez idempotencji tam, gdzie §4 jej wymaga.
- 404 zamiast `403 forbidden` dla cudzej lub nieistniejącej organizacji; sekret w URL, logu, `details` albo w liście instalacji.
- Tabela `gfm` bez `org_id` w kluczu złożonym; zapis do `gf.*` z API zamiast z joba publikacji.
- PR bez sekcji z diffem kontraktu albo z zieloną bramką uzyskaną przez `--allow-missing-openapi` po powstaniu YAML-a.

## Pliki kanoniczne

[docs/API-CONTRACT.md](../../../docs/API-CONTRACT.md) · `services/search/openapi/management-v1.yaml` · [tools/contract/check_api_contract.py](../../../tools/contract/check_api_contract.py) · [tests/test_api_contract_doc.py](../../../tests/test_api_contract_doc.py) · `services/search/internal/schema/sql.go` · `services/search/internal/mgmt/` · `ui/src/api/decoders.ts`
