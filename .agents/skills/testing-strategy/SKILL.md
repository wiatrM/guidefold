---
name: testing-strategy
description: Choose and run the right Guidefold test layer (pytest, Go, Vitest, Playwright, corpora) and know what each proves; includes the short TDD loop. Use when adding, changing or verifying behavior in CLI, service or UI; not for product acceptance with real users.
---

# Strategia testów: co dowodzi czego

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy test ma znaną warstwę, komendę i granicę tego, co potwierdza.
Źródło: [CONTRIBUTING, Running tests](../../../CONTRIBUTING.md), [CLAUDE.md, Evaluation corpora](../../../CLAUDE.md), [ui/README](../../../ui/README.md), [07-frontend, Testy i kroki](../../../docs/ui/pipeline/07-frontend.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Wybierz warstwę

| Warstwa | Narzędzie | Komenda (z root repo) | Dowodzi | Nie dowodzi |
|---|---|---|---|---|
| CLI `skills/guidefold/scripts/guidefold` | pytest, `tests/` | `pytest`; `python3 -m py_compile skills/guidefold/scripts/guidefold` | Zachowania komend na fixture Meridian; `Registry`/`subprocess` zamockowane | Działania na realnym GCP; nigdy go nie wołaj |
| Formuły rankingu | test referencyjny | `pytest tests/test_bm25_reference.py` | Zgodność implementacji z niezależnie policzonym wzorem | Jakości retrieval |
| Go SEARCH/USE | `go test` | `cd services/search && go test ./...` | Kontrakt 1.1, admission, parity, metryki z `*_test.go` | Multi-org, którego jeszcze nie ma w kodzie |
| Komponenty i dekodery UI | Vitest + Testing Library | `cd ui && pnpm test`, `pnpm test:contracts` | Kontrakty propsów, sześć stanów, dekodowanie payloadu na granicy | Użyteczności ani wydajności 10k |
| Trasy, klawiatura, axe | Playwright | `cd ui && pnpm test:e2e`; przy działającym `pnpm dev`: `pnpm test:flow`, `pnpm test:visual` | Ścieżka ownera, focus po zmianie stanu, brak naruszeń axe, pixel diff galerii | Realnego logowania, Git i sieci pilota |
| Jakość routingu | korpusy pinowane | `python3 tools/eval/corpora.py verify`, ścieżka `policy_filter → candidates → score → select` | Twierdzenia o jakości modelu/konfiguracji | Nic, gdy cache korpusów jest nieobecny: skip to "nie zmierzone", nie pass |

Fixture `examples/monorepo/` jest suitą regresji. Zysk na fixture nie jest dowodem jakości (odwrócił się na held-out, PR #19). Nie regeneruj baseline wizualnego, aby zaakceptować zmianę UI; baseline jest niezależny od zmiany.

## Pracuj w pętli TDD

1. Napisz najmniejszy test, który pada z powodu brakującego zachowania; uruchom go i zobacz czerwony wynik. Test, który nigdy nie padł, nic nie sprawdza.
2. Napisz minimalny kod do zielonego. Bez refaktoru w tym kroku.
3. Refaktoruj przy zielonych testach, małymi krokami, z ponownym uruchomieniem po każdym.
4. Formułę (BM25, cosine, ważenie) najpierw policz ręcznie lub niezależnym skryptem, potem porównaj testem referencyjnym; peer review znalazł sześć błędów spec-level w cytowanych wzorach.

Test nazywa zachowanie, nie implementację: `test_find_orders_scope_before_root`, nie `test_helper_returns_list`. Mock tylko na granicy portu (registry, subprocess, sieć, LLM); domenę testuj bez mocków.

## Sprawdź przed zakończeniem

- Zmienione zachowanie ma test w warstwie z tabeli i test ten był czerwony przed zmianą.
- Komenda uruchomiona, wynik wklejony do raportu razem z liczbą testów i skipów.
- Żaden test nie dotyka GCP, sieci ani `~/.cache` poza jawnie skipowanymi testami korpusów.
- Twierdzenie o jakości retrieval ma za sobą korpus, nie fixture.
- Testy flaky nie zostały "naprawione" retry ani regeneracją baseline.
