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

**Produkcja to skarb** (reguła właściciela z 2026-09-13, po tym jak agent zepsuł logowanie na produkcji). Wiąże każdego agenta i każdą sesję:

1. **Żadnej zmiany na produkcji bez wyraźnej zgody właściciela w bieżącej rozmowie.** Dotyczy skrótów obrazów, wartości aplikacji ArgoCD, sekretów, jobów, polityk sieciowych i ustawień aplikacji GitHub. Zgoda na jedną zmianę nie przechodzi na następną.
2. **ArgoCD nie uruchamia migracji.** Synchronizuje tylko Deploymenty; job migracji z charta (`workload: migrate`) uruchamia się wyłącznie ręcznie. Wydanie, które zmienia `services/search/internal/schema/sql.go`, idzie w tej kolejności: wyrenderuj job z charta z bieżących wartości aplikacji, z nowym obrazem `search` i `--set workload=migrate`, uruchom go, poczekaj na zakończenie, potwierdź nowe kolumny i tabele, i dopiero wtedy podmień skróty obrazów. Nowy kod na niezmigrowanej bazie to awaria.
3. **Wdrożenie przechodzi tylko po teście z logowaniem.** `/health/ready` z kodem 200 nie mówi nic o schemacie: 2026-09-13 odpowiadał 200 przez 25 minut, a każde logowanie kończyło się błędem `column "org_id" of relation "auth_states" does not exist`. Po każdym wdrożeniu `GET /api/v1/auth/login/google` musi odpowiedzieć 302 do WorkOS, każda zmieniona trasa musi odpowiadać zgodnie z założeniem, a logi API nie mogą zawierać linii `ERROR` w pierwszych minutach.
4. **Przed podmianą zapisz poprzednie skróty i cofnij wdrożenie przy pierwszej regresji**, zamiast diagnozować na produkcji.
5. **Testuj na lokalnym stosie** (`tools/dev/stack.py`), nigdy na produkcji, wszystko, co da się tam przetestować.

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

### Inne skille w `.agents/skills`

Poniższe 45 skilli (`python3 tools/check_skills.py`, stan 2026-09-15) to przyjęte skille
design/motion/generacji treści, nie decyzje inżynierskie projektu z ADR-0032; są indeksowane tu,
żeby checker nie wykazywał znalezisk „not listed", nie jako drugi PRD. Część z nich narusza limit
linii skilla (35–70); te 43 znaleziska są zapisane, nie obejściem przez dopisywanie treści —
patrz [audyt 2026-09-12](docs/reports/product/2026-09-12-assumptions-vs-implementation-audit.md)
PRIO 2.5.

| Grupa | Skill | Kiedy |
|---|---|---|
| Animacja i ruch | [animate](.agents/skills/animate/SKILL.md) | Budowa animacji od zera: cel, narzędzie, krzywa, przerywanie, wyjście. |
| Animacja i ruch | [animation-vocabulary](.agents/skills/animation-vocabulary/SKILL.md) | Nazwanie efektu ruchu opisanego słownie (np. „ten odbijający popover"). |
| Animacja i ruch | [apple-design](.agents/skills/apple-design/SKILL.md) | Gesty, sprężyny, materiały i typografia w stylu Apple przeniesione na web. |
| Animacja i ruch | [emil-design-eng](.agents/skills/emil-design-eng/SKILL.md) | Filozofia Emila Kowalskiego: polish UI, decyzje animacyjne, niewidoczne detale. |
| Animacja i ruch | [find-animation-opportunities](.agents/skills/find-animation-opportunities/SKILL.md) | Wyszukanie miejsc, które powinny się animować, bez wdrażania (read-only). |
| Animacja i ruch | [improve-animations](.agents/skills/improve-animations/SKILL.md) | Audyt istniejącej animacji z priorytetową listą planów naprawy (read-only). |
| Animacja i ruch | [review-animations](.agents/skills/review-animations/SKILL.md) | Recenzja kodu animacji wobec wysokiej poprzeczki jakości; domyślnie odrzuca. |
| Design i front-end | [design-assessment-product](.agents/skills/design-assessment-product/SKILL.md) | Quiz/scorecard jako warstwa wartości produktu na landing page. |
| Design i front-end | [design-taste-frontend](.agents/skills/design-taste-frontend/SKILL.md) | Anti-slop dla landing page i redesignów; audyt przed budową. |
| Design i front-end | [hooked-ux](.agents/skills/hooked-ux/SKILL.md) | Pętle nawyku (Hook Model) z obowiązkową oceną etyczną. |
| Design i front-end | [impeccable](.agents/skills/impeccable/SKILL.md) | Projektowanie, redesign i krytyka interfejsu front-end ogólnie. |
| Design i front-end | [pick-ui-library](.agents/skills/pick-ui-library/SKILL.md) | Dobór biblioteki UI do zadania z kuratorowanej listy; tylko na żądanie. |
| Design i front-end | [prototype](.agents/skills/prototype/SKILL.md) | Kilka wariantów UI za wizualnym picker-em do porównania; tylko na żądanie. |
| Design i front-end | [refactoring-ui](.agents/skills/refactoring-ui/SKILL.md) | Hierarchia wizualna, odstępy, kolor, tokeny, dark mode. |
| Design i front-end | [top-design](.agents/skills/top-design/SKILL.md) | Strony klasy Awwwards: typografia, scroll, ruch premium. |
| Design i front-end | [ui-ux-pro-max](.agents/skills/ui-ux-pro-max/SKILL.md) | Zapytanie do bazy UI/UX i system projektowy poparty dowodami. |
| Redesign i Unslopify | [audit-release-quality](.agents/skills/audit-release-quality/SKILL.md) | QA blokujące release po build/repair: a11y, wydajność, ruch, sekrety. |
| Redesign i Unslopify | [avoid-ai-writing](.agents/skills/avoid-ai-writing/SKILL.md) | Druga przepustka po humanizerze: wzorce pisania AI w copy strony. |
| Redesign i Unslopify | [build-motion-landing](.agents/skills/build-motion-landing/SKILL.md) | Budowa landing page Vite/TS/Tailwind/Motion z DESIGN.md i kontraktem zachowania. |
| Redesign i Unslopify | [direct-motion-site-prompts](.agents/skills/direct-motion-site-prompts/SKILL.md) | Zamiana referencji motion-site na prompty do budowy, choreografię, briefy assetów. |
| Redesign i Unslopify | [humanizer](.agents/skills/humanizer/SKILL.md) | Usunięcie wzorców pisania AI z copy bez zmiany treści chronionych. |
| Redesign i Unslopify | [refine-harness-offline](.agents/skills/refine-harness-offline/SKILL.md) | Ewaluacja poprawek HarnessCandidate bez samo-modyfikacji produkcji. |
| Redesign i Unslopify | [research-redesign-source](.agents/skills/research-redesign-source/SKILL.md) | Audyt i sanityzacja publicznej strony przed redesignem. |
| Redesign i Unslopify | [route-agent-models](.agents/skills/route-agent-models/SKILL.md) | Dobór modeli agentów (advisor/tech lead/executor/reviewer) dla joba Unslopify. |
| Redesign i Unslopify | [run-unslopify-job](.agents/skills/run-unslopify-job/SKILL.md) | Orkiestracja pełnego joba Unslopify: capture → research → build → QA → repair → paczka. |
| Redesign i Unslopify | [select-media-generation-route](.agents/skills/select-media-generation-route/SKILL.md) | Najtańsza trasa produkcji mediów spełniająca wymagania asset planu. |
| Redesign i Unslopify | [shape-premium-direction](.agents/skills/shape-premium-direction/SKILL.md) | Jeden kierunek redesignu z ResearchPacket i briefu klienta. |
| Cloudfloo premium motion | [cloudfloo-cinematic-landing](.agents/skills/cloudfloo-cinematic-landing/SKILL.md) | Kinowe landing page: rzadkie hero, rytm rozdziałów, odwracalne reveal. |
| Cloudfloo premium motion | [cloudfloo-premium-scroll-motion](.agents/skills/cloudfloo-premium-scroll-motion/SKILL.md) | Ruch sprzężony ze scrollem: deterministyczny progres, budżety wydajności. |
| Cloudfloo premium motion | [cloudfloo-quality-gate](.agents/skills/cloudfloo-quality-gate/SKILL.md) | QA blokujące release dla stron premium motion. |
| Cloudfloo premium motion | [cloudfloo-visual-system](.agents/skills/cloudfloo-visual-system/SKILL.md) | Spójny system wizualny premium: typografia, kolor, materiały, tokeny ruchu. |
| Marka i generacja mediów | [brand-forge](.agents/skills/brand-forge/SKILL.md) | Routing brakującego brand assetu do skilli logo/social/graphic/template. |
| Marka i generacja mediów | [generate-doc-template](.agents/skills/generate-doc-template/SKILL.md) | Branded SVG letterhead/slajdy/one-pager z zatwierdzonego profilu Brand Forge. |
| Marka i generacja mediów | [generate-graphic](.agents/skills/generate-graphic/SKILL.md) | Rastrowy hero/reklama/tło z zatwierdzonego profilu Brand Forge, tylko za zgodą. |
| Marka i generacja mediów | [generate-logo](.agents/skills/generate-logo/SKILL.md) | SVG wordmark/monogram/favicon z zatwierdzonego profilu Brand Forge. |
| Marka i generacja mediów | [generate-social](.agents/skills/generate-social/SKILL.md) | Szablony social (IG, OG card, YouTube thumbnail) z profilu Brand Forge. |
| Marka i generacja mediów | [higgsfield-brandkit](.agents/skills/higgsfield-brandkit/SKILL.md) | Pełny system marki przez Higgsfield CLI: paleta, logo, brandbook. |
| Marka i generacja mediów | [higgsfield-cinematic-assets](.agents/skills/higgsfield-cinematic-assets/SKILL.md) | Hero obrazy/wideo Higgsfield z referencjami i zatwierdzeniem płatnego wywołania. |
| Marka i generacja mediów | [higgsfield-generate](.agents/skills/higgsfield-generate/SKILL.md) | Generacja obrazów/wideo/3D/audio przez Higgsfield AI (domyślne modele). |
| Marka i generacja mediów | [higgsfield-marketplace-cards](.agents/skills/higgsfield-marketplace-cards/SKILL.md) | Karty produktowe marketplace przez Higgsfield. |
| Marka i generacja mediów | [higgsfield-product-photoshoot](.agents/skills/higgsfield-product-photoshoot/SKILL.md) | Sesja zdjęciowa produktu przez Higgsfield. |
| Marka i generacja mediów | [higgsfield-soul-id](.agents/skills/higgsfield-soul-id/SKILL.md) | Spójna tożsamość postaci/twarzy w generacjach Higgsfield. |
| Marka i generacja mediów | [higgsfield-video-explainer](.agents/skills/higgsfield-video-explainer/SKILL.md) | Wideo wyjaśniające produkt przez Higgsfield. |
| Marka i generacja mediów | [higgsfield-websites](.agents/skills/higgsfield-websites/SKILL.md) | Assety strony internetowej przez Higgsfield. |
| Marka i generacja mediów | [higgsfield-youtube-thumbnail](.agents/skills/higgsfield-youtube-thumbnail/SKILL.md) | Miniatury YouTube przez Higgsfield. |

To instrukcje dla autorów Guidefold. Dystrybuowany bootstrap znajduje się w `skills/guidefold/`; jego instrukcje służą agentom w repozytorium klienta. Ten root `AGENTS.md` jest pisanym ręcznie wejściem projektu, odrębnym od generowanych kart zakresu w repozytorium klienta.

## Zmiana i weryfikacja

- Nowy plik dokumentacji rejestruj i opisuj według sekcji „Nowe pliki” w DOCUMENTATION-RULES; artefakty i dowody łącz z dokumentem, który je wyjaśnia.
- Dla istniejącego CLI sprawdź kod, testy i [CLAUDE.md](CLAUDE.md). Dla SEARCH/USE czytaj [kontrakt](docs/HARNESS-SERVICE-CONTRACT.md) i [telemetrię](docs/SEARCH-USE-TELEMETRY.md).
- Dobieraj sprawdzenia do zmiany: linki/statusy dla dokumentacji; właściwe testy zachowania dla kodu; build, dostępność i porównanie wizualne dla UI zgodnie z etapem. W raporcie odróżnij wynik sprawdzenia od nieprzetestowanej obietnicy.
- Zachowuj niezwiązane zmiany. Reguły projektu nie wymagają ponownego zatwierdzania już zleconych edycji; nie nadają uprawnień do dodatkowych działań zewnętrznych.
