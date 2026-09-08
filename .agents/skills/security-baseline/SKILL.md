---
name: security-baseline
description: Apply Guidefold's mandatory security rules: per-request org/repo isolation, no secrets in the browser, cookie and CSRF rules, least-privilege tokens, no execution of imported code. Use when touching auth, storage, API handlers, worker jobs, adapters or UI data access.
---

# Baza bezpieczeństwa

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: izolacja organizacji i brak wycieku sekretów są warunkiem każdej zmiany, nie osobnym zadaniem.
Źródło: [PRODUCT-PIVOT U3 i §11](../../../docs/PRODUCT-PIVOT.md), [PIVOT-ARCHITECTURE, Najpierw trzy techniczne bramki](../../../docs/PIVOT-ARCHITECTURE.md), [PIVOT-BACKLOG, Zasady prowadzenia](../../../docs/PIVOT-BACKLOG.md), [07-frontend](../../../docs/ui/pipeline/07-frontend.md), [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Utrzymaj granicę org/repo per request

- Zweryfikowane org/repo przy każdym request, także w workerze i storage. Dzisiejszy globalny `Store.Tenant/Repo` i jeden cached `Catalog` w `services/search/store.go` nie mogą być mutowane dla kolejnych użytkowników; cache jest kluczowany org/repo/snapshot/policy i ograniczony (bramka 1).
- Membership sprawdzane per request, niezależnie od claimu organizacji w sesji. Podmiana ID org A na B nie ujawnia treści, metadanych ani liczników (U3 AC3). Test równoległy A/B z tym samym `repo_id`/URN, ciepłym cache, retry i rollbackiem jest obowiązkowy dla P02.
- Odwołanie członka/tokenu blokuje dostęp w maks. 60 s mimo aktywnej sesji dostawcy; UI zasłania prywatny widok po deadline i sprawdza dostęp przed odsłonięciem.
- `node` i `workspace` w SEARCH są scope routingu, nie dowodem tożsamości. CODEOWNERS i katalogi doprecyzowują scope; nie są systemem autoryzacji.
- Żadna ścieżka administracyjna nie omija izolacji.

## Nie trzymaj sekretów tam, gdzie ich nie ma

| Miejsce | Zasada |
|---|---|
| Przeglądarka/JS | Bez WorkOS API key, refresh tokena, klucza SEARCH/USE. Sesja w cookie HttpOnly/Secure/SameSite; CSRF dla każdej mutacji |
| Repo, URL, logi | Bez tokenów. `.gitignore` obejmuje `.env.*`, `*.pem`, `*.json.key`; `private/` nigdy nie jest publikowane |
| Token instalacji adaptera | Zakres org/repo oraz search/use/events; bez import/publish/membership. CI ma osobny token o minimalnych uprawnieniach (U5 AC3) |
| Poświadczenia CLI | Magazyn OS lub chroniony plik poza repo; device login bez sekretu klienta OAuth |
| Spool telemetrii | Bez bearer tokenów i surowego promptu; HMAC zapytania kluczem miesięcznym, który nie opuszcza hosta |

## Nie wykonuj cudzego kodu

Worker parsuje dokumenty; nie uruchamia skryptów z importowanego repo ani kodu klienta. Serwer SEARCH nigdy nie otwiera ścieżki podanej przez HTTP; builder czyta tylko zacommitowane `guidefold.yaml` i pliki skilli. `react-markdown` renderuje bez raw HTML i bez automatycznego pobierania obrazów ze źródeł. Limity: body 16 384 B, query 4 096 znaków, do 32 `target_paths`; nieznane pola odrzucane.

## Ustal priorytet

Zgłoszenia błędów auth, utraty danych, błędnej publikacji i niezgodności rewizji mają pierwszeństwo przed rozszerzeniami UI. Cel: zero nieautoryzowanych ujawnień i zero naruszeń closure/cap w raporcie guardrails.

## Sprawdź przed zakończeniem

- Nowy handler, job lub zapytanie filtruje po org z żądania, nie ze wspólnego stanu; test A/B dodany lub wskazany.
- `grep -rn 'token\|secret\|api_key' ui/src` nie pokazuje wartości ani przechowywania w localStorage/JS.
- Mutacja w UI wysyła token CSRF i używa cookie, nie nagłówka z sekretem.
- Nowy token/uprawnienie ma zakres z tabeli i nie rozszerza istniejących.
- Żadna nowa ścieżka nie wykonuje, nie importuje ani nie eval-uje treści z repo klienta.
