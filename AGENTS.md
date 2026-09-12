# Guidefold — instrukcje pracy w repozytorium

Status: aktywne instrukcje projektu. Data: 2026-09-06.
Cel: wybór dokumentów i skilli przy zmianach produktu oraz hosted UI.
Źródło: polecenie właściciela i [reguły dokumentacji](docs/DOCUMENTATION-RULES.md).
Zakres: repozytorium narzędzia; uzupełnia [CLAUDE.md](CLAUDE.md), nie zastępuje wymagań ani ADR.

## Wybór kontekstu

Zacznij od [DOCUMENTATION-RULES](docs/DOCUMENTATION-RULES.md). Dokumenty mają różne role:
[PRODUCT-PIVOT](docs/PRODUCT-PIVOT.md) określa wymagania,
[PIVOT-ARCHITECTURE](docs/PIVOT-ARCHITECTURE.md) granice techniczne,
[PIVOT-BACKLOG](docs/PIVOT-BACKLOG.md) kolejność i zależności,
[PIVOT-REVIEW](docs/PIVOT-REVIEW.md) uzasadnienia.
Status Proposed nie jest dowodem implementacji; bieżące zlecenie użytkownika określa zakres pracy.
Stan wykonania wobec P01–P15: [PIVOT-IMPLEMENTATION](docs/PIVOT-IMPLEMENTATION.md); obowiązujący
kontrakt API/DB: [API-CONTRACT](docs/API-CONTRACT.md).

## Dostęp do wdrożenia produkcyjnego

Ścieżka wskazana przez właściciela 2026-09-09: `/home/mike/projects/hsk-monorepo/deployment/helm/webkd-prod/kubeconfig.yaml` (WSL). Używaj jej jawnie przez `kubectl --kubeconfig=...`; nie zakładaj, że domyślny kontekst jest produkcją Guidefold. Kontekst: `cloudfloo-context`, namespace: `guidefold`. Runbook: [cloudfloo-io](deploy/k8s/environments/cloudfloo-io/README.md).

Zapisana jest wyłącznie ścieżka, nie sekret. Nie wypisuj ani nie kopiuj zawartości kubeconfig do repozytorium lub rozmowy. Przed wdrożeniem zweryfikuj kontekst i stan zasobów; nie zmieniaj innych aplikacji w tym klastrze. Ten wpis nie stanowi samodzielnej zgody na przyszłe wdrożenia.

## Pozycjonowanie: co sprzedajemy

Decyzja właściciela, 2026-09-09. Obowiązuje w każdym tekście marketingowym, na
landing page, w README i w deckach. Pełna wersja:
[guidefold-positioning](.agents/skills/guidefold-positioning/SKILL.md).

Nie sprzedajemy "team rules right where agents work". To jest za generyczne i nic
nie znaczy. Sprzedajemy problem wielkiej organizacji:

- około **30 000 skilli** w wielu repozytoriach i w monorepo, w wielu folderach,
  każdy zespół pisze swoje,
- **duplikacja** tych samych reguł w kilku miejscach,
- brak **zarządzania**: nikt nie widzi całego zbioru,
- **ekstrakcja wiedzy w piramidzie organizacji**, od szczegółu do ogółu.

Guidefold to rozwiązuje i automatyzuje: serwis **search i USE**, **wpięcie do
harnessu** oraz **automatyczne CI**.

Czytelnik ma pięć sekund na poznanie bólu i tego, co rozwiązujemy. Reszta tekstu
jest drugorzędna. Landing prowadzi jedną kolumną, hero najpierw; układ
dwukolumnowy został odrzucony przez właściciela.

## Skille projektu

### Obowiązkowe komponenty Spectrum UI

Decyzja właściciela, 2026-09-09: przy tworzeniu, redesignie i migracji UI **obowiązkowo korzystaj z komponentów Spectrum UI** i [Spectrum MCP](https://ui.spectrumhq.in/docs/mcp). Przed implementacją przeczytaj [spectrum-ui-workflow](.agents/skills/spectrum-ui-workflow/SKILL.md): wyszukaj rzeczywisty item, sprawdź jego kod i zależności, zainstaluj odpowiednik i zweryfikuj działanie. Ręczny zamiennik wymaga udokumentowanego braku odpowiednika lub problemu zgodności. Dostęp do całego rejestru nie oznacza instalacji wszystkich komponentów. Ta decyzja zastępuje wcześniejszy zakaz shadcn/Tailwind dla integracji Spectrum; nie zmienia kontraktów API, bezpieczeństwa ani zgód na deploy.

### Obowiązkowa migracja telemetrii i wykresów

Decyzja właściciela, 2026-09-09: **wszystkie istniejące i nowe wizualizacje telemetrii oraz wykresy mają korzystać ze Spectrum Charts**, nie tylko nowo edytowane komponenty. Przeczytaj [spectrum-charts-migration](.agents/skills/spectrum-charts-migration/SKILL.md); kanoniczne wymagania i kryteria odbioru: [UI §7](docs/ui/UI.md#7-obowiązkowa-migracja-spectrum-charts). Obowiązek obejmuje pie/donut, trendy, rozkłady, miniwykresy i karty metryk, z doborem typu do danych. Nie oznacza przepisywania backendu telemetrii. Zapis wymagań nie jest dowodem zakończenia migracji.

Workflowy:
- [guidefold-product-changes](.agents/skills/guidefold-product-changes/SKILL.md): zmiany wymagań, architektury, backlogu, kontraktów i dokumentacji pivotu.
- [guidefold-ui-workflow](.agents/skills/guidefold-ui-workflow/SKILL.md): projektowanie, implementacja i QA siedmiu widoków U4 oraz utrzymanie pipeline’u UI.

Reguły (decyzja: [ADR-0032](docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md); dla Claude Code linki w [`.claude/skills/`](.claude/README.md), sprawdzenie: `python3 tools/check_skills.py`). Czytaj przed pracą: `product-direction-guard`, `definition-of-done`, `hexagonal-architecture`.

| Grupa | Skill | Kiedy |
|---|---|---|
| Kierunek produktu | [product-direction-guard](.agents/skills/product-direction-guard/SKILL.md) | Każde zadanie: mapowanie na U-historię i P-id, odrzucanie dryfu. |
| Kierunek produktu | [backlog-prioritisation](.agents/skills/backlog-prioritisation/SKILL.md) | Wybór następnego zadania z P01–P15, Pilot Core vs beta. |
| Kierunek produktu | [pilot-evidence](.agents/skills/pilot-evidence/SKILL.md) | Co jest dowodem wartości (R/Q/P), raport pilota, kill criteria. |
| Kierunek produktu | [positioning-and-copy](.agents/skills/positioning-and-copy/SKILL.md) | Copy w README, UI, PR, opisach skilli zgodne z PRODUCT-FOCUS. |
| Kierunek produktu | [scope-change-protocol](.agents/skills/scope-change-protocol/SKILL.md) | Odstępstwo od PRD/backlogu/ADR: jak zapisać i kto decyduje. |
| Kierunek produktu | [user-research-alignment](.agents/skills/user-research-alignment/SKILL.md) | Persony, hipotezy, ankieta i pytania do ludzi przed funkcją UI. |
| Zasady inżynierskie | [kiss-simplicity](.agents/skills/kiss-simplicity/SKILL.md) | Najprostsze rozwiązanie, budżet złożoności. |
| Zasady inżynierskie | [yagni-scope-control](.agents/skills/yagni-scope-control/SKILL.md) | Nic bez historii backlogu lub zlecenia; brak abstrakcji na zapas. |
| Zasady inżynierskie | [dry-without-wrong-abstraction](.agents/skills/dry-without-wrong-abstraction/SKILL.md) | Reguła trzech, jedno źródło prawdy, bez worków utils. |
| Zasady inżynierskie | [solid-principles](.agents/skills/solid-principles/SKILL.md) | SOLID na przykładach z tego repo i wykrywanie naruszeń. |
| Zasady inżynierskie | [hexagonal-architecture](.agents/skills/hexagonal-architecture/SKILL.md) | Wymagane porty i adaptery w Go, React i CLI; kierunek zależności. |
| Zasady inżynierskie | [module-boundaries-go](.agents/skills/module-boundaries-go/SKILL.md) | Sześć modułów API/worker, własność zapisu, kontrakt jobów. |
| Zasady inżynierskie | [refactoring-rules](.agents/skills/refactoring-rules/SKILL.md) | Kiedy i jak refaktorować, czego nie ruszać. |
| Zasady inżynierskie | [definition-of-done](.agents/skills/definition-of-done/SKILL.md) | DoD per rodzaj zmiany: CLI, Go, UI, docs, feature. |
| Jakość i proces | [code-review-checklist](.agents/skills/code-review-checklist/SKILL.md) | Przegląd PR: zakres, dowody, testy, granice, P1/P2/P3. |
| Jakość i proces | [testing-strategy](.agents/skills/testing-strategy/SKILL.md) | Która warstwa testów dowodzi czego; TDD; fixture vs korpusy. |
| Jakość i proces | [error-handling-and-states](.agents/skills/error-handling-and-states/SKILL.md) | Sześć stanów UI, błędy w Go, unknown ≠ zero. |
| Jakość i proces | [security-baseline](.agents/skills/security-baseline/SKILL.md) | Izolacja org, sesje, sekrety, worker bez wykonywania kodu klienta. |
| Jakość i proces | [performance-budgets](.agents/skills/performance-budgets/SKILL.md) | Budżety p95, 10 tys. skilli, pomiar przed i po. |
| Jakość i proces | [observability-telemetry](.agents/skills/observability-telemetry/SKILL.md) | Ledger, dedupe, unknown, raport z identyfikatorem przebiegu. |
| Jakość i proces | [git-workflow](.agents/skills/git-workflow/SKILL.md) | Branch/worktree, PR, brak commitów na main, stopka. |
| Jakość i proces | [api-contract](.agents/skills/api-contract/SKILL.md) | Kontrakt przed kodem: endpoint, DTO, kod błędu, tabela `gfm`, job. |
| Jakość i proces | [api-contract-versioning](.agents/skills/api-contract-versioning/SKILL.md) | Kontrakt 1.1/1.2, OpenAPI, zmiana = wersja + testy + dokument. |
| Konwencje repo | [cli-single-file-constraints](.agents/skills/cli-single-file-constraints/SKILL.md) | Jednoplikowy CLI, stdlib + PyYAML, klasa Registry. |
| Konwencje repo | [skill-authoring-conventions](.agents/skills/skill-authoring-conventions/SKILL.md) | Frontmatter, `[node]` w description, URN, validate. |
| Konwencje repo | [adr-writing](.agents/skills/adr-writing/SKILL.md) | Format ADR, statusy, amendment, indeks. |
| Konwencje repo | [domain-glossary](.agents/skills/domain-glossary/SKILL.md) | Pojęcia: skill, scope, URN, rewizja, propozycja, snapshot, osie piramidy. |
| Konwencje repo | [eval-evidence-rules](.agents/skills/eval-evidence-rules/SKILL.md) | Korpusy vs fixture, R/Q/P, skip ≠ pass, formuły referencyjne. |
| UI | [ui-anti-slop-gate](.agents/skills/ui-anti-slop-gate/SKILL.md) | UX §6: zakazane wzorce i słowa, test zrzutu, test na głos. |
| UI | [react-component-rules](.agents/skills/react-component-rules/SKILL.md) | tokens.css, CSS Modules, 14 komponentów, stany, galeria. |
| UI | [accessibility-contract](.agents/skills/accessibility-contract/SKILL.md) | axe, klawiatura, focus, role, 44 px, kontrast. |

To instrukcje dla autorów Guidefold. Dystrybuowany bootstrap znajduje się w `skills/guidefold/`; jego instrukcje służą agentom w repozytorium klienta. Ten root `AGENTS.md` jest pisanym ręcznie wejściem projektu, odrębnym od generowanych kart zakresu w repozytorium klienta.

## Zmiana i weryfikacja

- Nowy plik dokumentacji rejestruj i opisuj według sekcji „Nowe pliki” w DOCUMENTATION-RULES; artefakty i dowody łącz z dokumentem, który je wyjaśnia.
- Dla istniejącego CLI sprawdź kod, testy i [CLAUDE.md](CLAUDE.md). Dla SEARCH/USE czytaj [kontrakt](docs/HARNESS-SERVICE-CONTRACT.md) i [telemetrię](docs/SEARCH-USE-TELEMETRY.md).
- Dobieraj sprawdzenia do zmiany: linki/statusy dla dokumentacji; właściwe testy zachowania dla kodu; build, dostępność i porównanie wizualne dla UI zgodnie z etapem. W raporcie odróżnij wynik sprawdzenia od nieprzetestowanej obietnicy.
- Zachowuj niezwiązane zmiany. Reguły projektu nie wymagają ponownego zatwierdzania już zleconych edycji; nie nadają uprawnień do dodatkowych działań zewnętrznych.
