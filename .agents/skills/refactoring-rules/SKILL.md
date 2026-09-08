---
name: refactoring-rules
description: How to refactor in Guidefold: behaviour-preserving steps under green tests, separate from behaviour changes, no drive-by edits, moving code toward KISS, YAGNI, DRY and hexagonal boundaries. Use before restructuring any file and when a task tempts you to "clean up while here". Not for parked code.
---

# Zasady refaktoryzacji

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: zmieniać strukturę bez zmiany zachowania, małymi krokami, z dowodem i bez rozlewania się na niezwiązane pliki.
Źródło: [CLAUDE.md](../../../CLAUDE.md) ("Preserve unrelated work"), [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) ("podział wymaga stopniowej pracy, nie pełnego rewrite"), [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md) (komponenty parked). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Rozpoznaj, kiedy refaktorować, a kiedy nie

| Sygnał do refaktoru | Sygnał, żeby nie ruszać |
|---|---|
| Funkcja wymaga scrolla, żeby ją przeczytać (np. handlery w `services/search/main.go`, ok. 23 KB w `package main`) | Kod parked z ADR-0029 (TEI/GPU shadow worker, k8s lifecycle, vector layout, graph admission) |
| Logika domenowa siedzi w handlerze HTTP, komponencie trasy lub komendzie CLI | Plik spoza zadania, którego nie testujesz w tym PR |
| Ten sam fakt w dwóch miejscach zmienia się razem (zob. `dry-without-wrong-abstraction`) | Brak testów pokrywających zachowanie, które chcesz zachować; najpierw test |
| Nowa funkcja musiałaby skopiować `if backend == ...` po raz trzeci | Zamrożony wzorzec `prototypes/industrial-surveyor` i hi-fi `prototypes/pipeline-hifi` |

## Wykonaj refaktor jako osobny, sprawdzalny krok

1. Zielone testy przed startem: `pytest` (CLI), `cd services/search && go test ./...` (Go), `cd ui && pnpm test` (UI). Bez zielonych testów nie ma refaktoru; dopisz test charakteryzujący.
2. Jeden ruch na raz: wyodrębnij funkcję, przenieś do modułu, zawęź interfejs, zmień nazwę. Po każdym ruchu testy zielone. Kierunek: KISS, YAGNI, DRY, port/adapter (zob. `hexagonal-architecture`).
3. Refaktor i zmiana zachowania w osobnych commitach lub PR. Diff refaktoru ma zerową zmianę w oczekiwaniach testów; jeśli test musiał się zmienić, to nie był refaktor.
4. Boy-scout tylko w dotkniętej funkcji lub pliku. Formatowanie, zmiana nazw i porządki w innych plikach są zabronione w tym samym PR.
5. Zachowuj kontrakty zewnętrzne: format wyjścia CLI, pola odpowiedzi SEARCH/USE 1.1, nazwy tokenów i props komponentów. Zmiana kontraktu to zmiana zachowania z własnym ADR lub wersją.

## Opisz, co się nie zmieniło

PR refaktoru zawiera zdanie "Zachowanie bez zmian: …" z listą kontraktów i komendą, którą to sprawdzono (np. `diff` wyjść przed/po na fixture `examples/monorepo`, `pnpm test:visual` bez regeneracji baseline). Reviewer odrzuca refaktor bez tej sekcji.

## Sprawdź przed zakończeniem

- Czy testy były zielone przed pierwszym ruchem i po każdym kroku?
- Czy `git diff` nie zmienia żadnego oczekiwania w testach ani baseline?
- Czy `git diff --stat` obejmuje tylko pliki dotknięte zadaniem?
- Czy PR zawiera sekcję "Zachowanie bez zmian" z komendą weryfikacji?
- Czy kod przeniesiony do domeny nie przyniósł ze sobą importów I/O?
