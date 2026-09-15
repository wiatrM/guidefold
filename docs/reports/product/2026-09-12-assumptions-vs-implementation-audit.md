# Audyt założeń i dokumentów wobec implementacji — 2026-09-12

Status: wykonany audyt, decyzje ADR z tego samego dnia. Data: 2026-09-12. Gałąź `landing/why-how-value` @ `ebcb863` (origin/main wmerge'owany w `51c9c1a`).
Cel: sprawdzić, czy stare założenia (ADR-0001–0029, DESIGN/CONVENTIONS/MVP) i nowe (PRODUCT-PIVOT, PIVOT-ARCHITECTURE, API-CONTRACT 1.3.0, ADR-0031–0042, polecenia właściciela z CLAUDE.md) zgadzają się z kodem, i wypisać kompletną listę PRIO.
Wejścia: pięć niezależnych przeglądów (serwis Go, UI i landing, CLI i dystrybucja, korpus 42 ADR, spójność docs i dowody pilota), uruchomione testy (`go test ./...` 16/16 pakietów, pytest 1347 pass / 3 skip / 0 fail, `pnpm build`/`test` 453/453/`test:contracts` 0 diagnostyk, `check_api_contract.py` 0 dryfu / 17 INFO), sonda produkcji `https://guidefold.cloudfloo.io` (`/api/v1/auth/providers` 200 w trybie `workos`, `/api/v1/me` 401), `gh issue list`.
Zakres zastępowania: brak; raport uzupełnia [PIVOT-BACKLOG](../../PIVOT-BACKLOG.md) i [PIVOT-IMPLEMENTATION](../../PIVOT-IMPLEMENTATION.md), nie zmienia wymagań U1–U11. Decyzje zapisane w [ADR-0043](../../adr/ADR-0043-pre-pivot-adr-reconciliation.md) i [ADR-0044](../../adr/ADR-0044-console-on-shadcn-and-spectrum.md).

> **Wniesiony na `main` 2026-09-15** z gałęzi `audit/2026-09-12-integration` (commit `77b80e8`), bez zmian w treści poza oznaczonymi `[korekta 2026-09-15: …]`. Wszystkie liczby, statusy i wyniki testów poniżej opisują **2026-09-12**; od tamtej daty zmergowano 27 PR-ów (#146–#172). Co z tej listy PRIO jest nadal otwarte, a co zdezaktualizowane, mówi [raport zamknięcia MVP z 2026-09-15](2026-09-15-mvp-closure-status.md) — on, nie ten plik, jest bieżącym stanem.

## 1. Werdykt w pięciu zdaniach

Kod jest w dobrym stanie technicznym: wszystkie zestawy testów zielone, kontrakt bez dryfu, produkcja odpowiada na logowanie WorkOS (blocker M01 z raportu 09-09 zdjęty). Rozjazd jest **między tym, co dokumenty mówią, że jest priorytetem, a tym, na co poszła praca**: od 2026-09-09 ~60 commitów, niemal wszystkie w landing i konsolę, zero postępu w dowodach pilota. **Kryterium kill z PRODUCT-FOCUS (partner do 2026-09-20) jest niespełnione na 8 dni przed terminem**; sekcja „Design partner" pusta, issue #78 `blocked-on-owner`, 0 realnych sesji, U5-4 i U6-6 w raporcie akceptacyjnym jako `not_measured_here`. Warstwa ADR opisywała system, którego nie ma (Cloud SQL, GCS, G0–G7, GPU serving) obok Proposed ADR-ów, które od tygodnia są w kodzie — to uporządkowano dziś w ADR-0043. Cztery różne zdania pozycjonujące (README, landing, skill `guidefold-positioning`, PRD §12a) i trzy różne backlogi (PIVOT-BACKLOG P01–P15, GitHub Issues #71–#117, MoSCoW M01–M10 „w realizacji") wymagają jednej decyzji właściciela każde.

## 2. Stare założenia vs nowe: gdzie się rozbiegamy

| Założenie (skąd) | Stan dziś (dowód) | Ocena |
|---|---|---|
| Registry Google jako artefakt build, „no own storage/IAM" (ADR-0001, DESIGN.md:33) | Hosted katalog `gf`/`gfm` w Postgres, WorkOS, tokeny (`internal/{identity,schema}`) | DESIGN.md opisuje stary świat jako bieżący; ADR-0001 zostaje dla trybu `agent-registry`, DESIGN wymaga banera |
| Knowledge API na Cloud Run + Cloud SQL (ADR-0013) | Monolit Go, jeden Postgres (ADR-0033) | superseded — ADR-0043 |
| GCS na artefakty (ADR-0018) | tylko `PostgresBlobStore` za portem `BlobStore` | GCS clause superseded — ADR-0043 |
| Model self-hosted serwuje zapytania (ADR-0015, Accepted) | `w_dense=0`, dense = research track (ADR-0029 r2) | serving clause superseded — ADR-0043 |
| Lifecycle G0–G7 (ADR-0016, Accepted) | enum 6 stanów (`schema/importer.go:83`) | superseded — ADR-0043 |
| Surface freeze do pilota (ADR-0029 r1) | identity/importer/review/worker/UI/extension istnieją pod ADR-0031 | ADR-0031 Accepted 09-12; freeze przeniesiony na powierzchnię pivotu |
| Backlog w GitHub Issues (ADR-0029 r4, BACKLOG.md:5) | 47 otwartych, 0 zamkniętych od 09-08; praca idzie po PIVOT-BACKLOG i MoSCoW | ADR-0043 r4; decyzja właściciela 09-12: PIVOT-BACKLOG P01–P16 jest jedynym porządkiem |
| Klient = platform team nad **monorepo** (PRODUCT-FOCUS, PRD §4) | ADR-0042 (Proposed 09-12) wprowadza multi-repo org | rozbieżność zapisana w ADR-0042; decyzja właściciela 09-12: Accepted, P16 w Pilot Core, bez kodu |
| „Nowe komendy nie są jeszcze implementacją" (PRD §8:167) | 29 komend CLI, wszystkie z testami | PRD stale |
| Adaptery: „Claude Code i Copilot" (PRD), „Claude/Codex" (DESIGN:453), „Claude/Copilot/Gemini" (PIVOT-IMPLEMENTATION:46) | `install --harness {claude,copilot,gemini}`; szablon hooka `codex` istnieje, `gemini.hooks.json` nie | trzy dokumenty, trzy zestawy; kod niespójny sam ze sobą |
| ADR-0012 „nic generowanego nie jest commitowane" | `examples/monorepo/.agents/skills/hierarchy-index/SKILL.md` w git; `skills.yml:44` mówi o commitowaniu kart przez bota | częściowo; `guidefold card`/GCS nigdy nie zbudowane |
| Kontrakt 1.1.1 (PIVOT-IMPLEMENTATION §f) | 1.3.0, 11 rewizji dalej | stale (poprawione dziś w nagłówku) · *[korekta 2026-09-15: na `main` @ `2a302f5` kontrakt jest w wersji **1.13.0** (2026-09-13); §f przepisane na tę wersję przy wnoszeniu raportu]* |
| „Jeden bootstrap + CLI, `Registry` jedyną drogą do rejestru" (ADR-0003, CLAUDE.md) | `_gcloud_json` w `cmd_doctor` omija `Registry` | drobne naruszenie |
| Hex architektura (ADR-0032) | domena/porty w `usage`, `importer`; SQL w handlerach `identity` (41), `knowledge` (12), `review` (13); retrieval w `package main` (22 % kodu prod.) | częściowo; zapisane w adnotacji ADR-0032 |
| ADR-0036 webhook → `ascend.run` → PR (kontrakt 1.2.0 §8) | webhook, HMAC, tabela, enqueue ✓; handler workera zawsze `Skipped("github_app_connector_not_configured")`, brak `git` w obrazie | kontrakt opisuje zachowanie, którego worker nie wykonuje |
| ADR-0041 (Accepted) projekcja `gf.training_examples` | tabela + grant, zero `INSERT`, zero czytelników | Accepted-but-schema-only |
| Spectrum Charts obowiązkowe (CLAUDE.md 09-09, UI §7) | 5 wykresów na Spectrum; 4 na Overview (`HomeRoute.tsx`) na blokach shadcn-space/recharts, w 4 dokumentach opisane jako „Spectrum" | naruszenie SC-01 + fałszywy opis; ADR-0044 r3 |
| Liczba komponentów publicznych | 14 (07-frontend:33), 15 (UI.md:84), 16 (08-components, skill, README, check-contracts) | jedno miejsce prawdy — ADR-0044 r5 |
| Pozycjonowanie | README („Your coding agent can read the repo…"), landing hero („doesn't know your team's rules"), skill `guidefold-positioning` (30 000 skilli/duplikacja/zarządzanie/piramida), PRD §12a:335 (proof-gated, „odmawia dostawy") i :341 (zatwierdzone instrukcje) | cztery tezy; decyzja właściciela 09-12: teza 30 000 skilli; landing i README do przepisania (1.9) |
| Deploy: `deploy/t1` jedyny wspierany (ADR-0029, BACKLOG #113) | ArgoCD `cloudfloo-io`, chart `deploy/k8s`, `targetRevision` = tag `deploy-cloudfloo-chart-r12` (nie `main`) | ADR-0030 Accepted 09-12; brak wiersza w DOCUMENTATION-RULES; pin taga do zdjęcia |
| „Trzydzieści skilli reguł" (CLAUDE.md, DOCUMENTATION-RULES) | 81 w `.agents/skills`, 36 w AGENTS.md, 45 nieindeksowanych, `guidefold-positioning` bez symlinku (`tools/check_skills.py`: 89 znalezisk) | stale |
| PRODUCT-FOCUS trzyma kill criteria | plik jest sierotą: nie ma go w tabeli DOCUMENTATION-RULES ani w AGENTS.md | do indeksu |
| MoSCoW 09-09 | nagłówek „W realizacji", §9 „Proposed"; PIVOT-BACKLOG linkuje jako Proposed | wewnętrznie sprzeczny |

Pełne listy z przeglądów (per plik i linia) są w transkryptach agentów tej sesji; powyższa tabela zawiera każdą pozycję, która zmienia decyzję lub kolejność.

## 3. Co zmieniono dziś (ADR)

- **ADR-0043** (Accepted): rekoncyliacja — supersedes 0013, klauzula GCS 0018, klauzula serwowania 0015, G0–G7 z 0016; parkuje 0009/0021/0023-GPU/0024-T2/0027; amenduje 0029 r1 i r4; przyjmuje 0028, 0030, 0031, 0033.
- **ADR-0044** (Accepted): stack konsoli shadcn + Spectrum + Spectrum Charts jako ADR z trzech poleceń właściciela; nazywa naruszenie na Overview.
- Statusy: **0028, 0030, 0031, 0033 → Accepted 2026-09-12**; po decyzjach właściciela (§5) także **0039 (opt-in) i 0042 (P16)**. Zostają Proposed: 0012, 0014, 0036 (do dokończenia), 0040 (brak kodu w repo).
- Adnotacje zwrotne dopisane w 0009, 0013, 0015, 0016, 0018, 0020, 0021, 0022, 0023, 0024, 0026, 0027, 0029, 0032, 0035, 0036, 0038; indeks `docs/adr/README.md` zgodny z plikami (0028/0030 miały brak daty; 0016 miało zbłąkany `;`; stopka nie wskazuje już MVP §8).
- Linie statusu: PRODUCT-PIVOT, PIVOT-ARCHITECTURE, PIVOT-BACKLOG (ADR-0031 Accepted), PIVOT-IMPLEMENTATION (kontrakt 1.3.0, „zacommitowana").

Nie zmieniono: wymagań U1–U11 poza notą przy §4 (P16), kontraktu ani żadnego kodu poza usunięciem trasy `/demo` (§5).

## 4. PRIO do wdrożenia

Kolejność wynika z `backlog-prioritisation` (krytyczne → bramki → Pilot Core → dowód → beta), nie z wygody. R = kryterium techniczne, Q = jakość na próbce, P = dowód pilota. Każda pozycja ma U/P, personę i dowód odbioru; pozycje bez U/P są jawnymi pytaniami do właściciela.

### PRIO 0 — do 2026-09-20 (bramka kill; nic innego nie jest ważniejsze)

| # | Zadanie | U/P · persona | Dowód odbioru | Owner |
|---|---|---|---|---|
| 0.1 | **Partner projektowy** — zdecydowane 2026-09-12: self-use + drugie repo org `cloudfloo`; zostaje wpisać nazwę drugiego repo, ownera skilli, harness i datę w PRODUCT-FOCUS; zamknąć #78 | §13 PRD · owner produktu | wiersz „Repository 2" bez „to be named"; dowody etykietowane self-use | właściciel |
| 0.2 | **Live login na cloudfloo**: świeże konto Google i GitHub, powrót do tej samej tożsamości, zaproszenie i odwołanie (M01/M02, U3 AC1–2) — produkcja już odpowiada 200/401, brakuje zapisu przebiegu | U3/P01 · owner + zaproszony developer | raport z datą, kontami testowymi i request_id; U3-1 w acceptance przestaje być `not_measured_here` | backend/operator |
| 0.3 | **ACT-01 na żywo, jeden harness**: osoba spoza zespołu, realne repo, Claude Code `install` → SEARCH → USE → `context_loaded` → feedback → decyzja ownera w kolejce | U5/U6 · P10/P11 · developer + owner | wiersze w ledgerze org partnera; U5-4, U6-6 w acceptance jako pass; pierwsze z 20 sesji do 10-04 | zespół + partner |
| 0.4 | *[nadal otwarte 2026-09-15]* **Uzgodnić manifest ArgoCD z klastrem**: zacommitowany `deploy/k8s/environments/cloudfloo-io/argocd-application.yaml` pinuje tag `deploy-cloudfloo-chart-r12`, a właściciel opisał żywą aplikację jako śledzącą `main`; sprawdzić na klastrze, ustawić `workos.clientID` w values i zdjąć pin, żeby plik w repo mówił prawdę | ADR-0030 · operator | `kubectl -n argocd get application guidefold` zgodne z plikiem; API 2/2 Ready po sync | operator |
| 0.5 | **Zamrozić E6.7**: wypełnić `[PLACEHOLDER]` sha256 i sign-off w `docs/pilot/E6.7-PROTOCOL.md` przed pierwszą sesją pilota | P15 · research | hash w nagłówku arkusza ocen | research + właściciel |
| 0.6 | **Jedna lista pracy** — zdecydowane 2026-09-12: PIVOT-BACKLOG P01–P16; MoSCoW i BACKLOG.md oznaczone jako historyczne | ADR-0029 r4 / ADR-0043 r4 · właściciel | zrobione | właściciel |
| 0.7 | **P16 multi-repo (ADR-0042)**: `gfm.repo_links`, `target_repo_id`, ustawienia generatora per org, konfigurator CI; kontrakt przed kodem; test akceptacyjny z ADR-0042 §Consequences; drugie repo `cloudfloo` podpięte na hostowanej instancji | U1 nota / P16 · owner org | test akceptacyjny zielony + drugie repo widoczne w Library | backend + frontend |

### PRIO 1 — rozjazdy kod ↔ kontrakt ↔ reguła (przed kolejnym rozszerzeniem UI)

| # | Zadanie | Reguła | Dowód odbioru |
|---|---|---|---|
| 1.1 | `ascend.run` **wdrożyć** (decyzja 2026-09-12): git w `Dockerfile.worker`, egress do GitHub i modelu w NetworkPolicy, `test_worker_image.py`, handler zamiast stubu | ADR-0036, API-CONTRACT §1 | test akceptacyjny z ADR-0036 §Consequences przechodzi; ADR-0036 → Accepted |
| 1.2 | `gf.training_examples`: dopisać writer w Telemetry/Reporting (projekcja z zaakceptowanych zdarzeń, `content_mode` bez treści) albo obniżyć ADR-0041 do „schema reserved" | ADR-0041, ADR-0033 | test parity z `tools/telemetry/report.py` albo adnotacja w ADR |
| 1.3 | Overview na Spectrum Charts: KPI, lejek, donut, proposals-by-state z `shadcn-space` → adaptery `spectrumui/charts`, albo wpis SC-07 z powodem; poprawić 07-frontend:29, console-shadcn:105/107, IA.md:18, ui/README:131 (mówią „Spectrum") | ADR-0044 r3, UI §7 SC-01/SC-07 | `grep shadcn-space ui/src/routes/HomeRoute.tsx` = 0 albo wpis SC-07; dokumenty nie używają słowa Spectrum dla nie-Spectrum |
| 1.4 | Harnessy: `install --harness codex` (szablon `codex.hooks.json` istnieje) i `gemini.hooks.json` (mapa `HARNESS_HOOK_FILES` wskazuje nieistniejący plik); jedna tabela harness × {install, hook, telemetria} w HOWTO-adapter, do której linkują PRD §8, DESIGN, PIVOT-IMPLEMENTATION | U5 AC1, ADR-0031 §9 | `test_pivot_cli_install.py` dla czterech harnessów; trzy dokumenty cytują jedną tabelę |
| 1.5 | `templates/github-workflows-skills.yml`: przypiąć `version:` w `setup-gcloud`, usunąć komentarz o bocie commitującym karty (ADR-0012), ujednolicić ścieżkę CLI z `ci.yml` | CLAUDE.md „pin gcloud", ADR-0012 | test szablonu w `tests/` |
| 1.6 | Osiem literałów hex w kodzie registry (`ui/chart.tsx:65`, `spectrumui/tree-nav.tsx:217`, `bento-card.tsx:137`): zamienić na tokeny albo wpis waiver w UI §7 | ADR-0044 r4, react-component-rules | `guard-tokens.sh` czysty albo waiver z plikiem i linią |
| 1.7 | `cmd_doctor` `_gcloud_json` → przez `Registry` | ADR-0003, cli-single-file-constraints | `grep gcloud` w CLI wskazuje tylko `Registry` |
| 1.8 | ADR-0034 §5 wewnętrznie mówi „remains Proposed" przy Accepted w nagłówku; poprawić adnotacją | adr-writing | zrobione 2026-09-12 |
| 1.9 | **Hero landingu i intro README pod tezę 30 000 skilli** (decyzja 2026-09-12): trzy problemy nazwane w pierwszych pięciu sekundach, „What you get" na każdym bloku, proof band z etykietą statusu źródła | guidefold-positioning, positioning-and-copy | hero i README cytują tę samą tezę; landing e2e zielone |

### PRIO 2 — prawda dokumentów (jedna sesja, bez zmiany kodu)

| # | Zadanie | Dowód odbioru |
|---|---|---|
| 2.1 | PIVOT-IMPLEMENTATION: przepisać §b/§c/§f na 1.3.0 (github_installations, training_examples, ascend, Overview, shadcn), data 2026-09-12 | 0 odwołań do 1.1.1 poza changelogiem |
| 2.2 | PRODUCT-PIVOT: §7 dopisać Overview `/home` (`/demo` usunięte 2026-09-12), §8 skreślić „nowe komendy nie są jeszcze implementacją" (§4 nota do ADR-0042 dopisana) | linie 141–167 zgodne z kodem |
| 2.3 | PIVOT-ARCHITECTURE: tabela modułów dopisuje „Retrieval/Delivery — dziś `package main`", właściciel `gfm.relations` (importer pisze, review czyta), odwołania do ADR-0036/0037/0041/0042 | brak dwóch dokumentów spierających się o ownera tabeli |
| 2.4 | Pozycjonowanie: zdanie wybrane 2026-09-12 (30 000 skilli, zapis w PRD §12a); `docs/marketing` i pipeline UI cytują je; wykonanie w landingu i README to 1.9 | jedna teza w pięciu miejscach; brak liczby bez statusu |
| 2.5 | DOCUMENTATION-RULES: wiersze dla PRODUCT-FOCUS (kill criteria), deploymentu (`deploy/k8s/environments/cloudfloo-io/README.md`), ADR-0042/specs; „trzydzieści skilli" → liczba z `tools/check_skills.py`; AGENTS.md indeksuje 45 brakujących skilli albo usuwa je z `.agents/skills`; symlink `guidefold-positioning` | `tools/check_skills.py` 0 znalezisk |
| 2.6 | DESIGN.md i CONVENTIONS.md: baner „stan sprzed pivotu; hosted katalog opisuje PIVOT-ARCHITECTURE/API-CONTRACT", usunąć `sync-harness` (CONVENTIONS:138), `install` z `gemini`, komendy `where/init/telemetry/login/org/status/extract` | 0 komend opisanych, których nie ma; 0 istniejących bez opisu |
| 2.7 | MVP.md, BACKLOG.md, KNOWLEDGE-DESIGN.md, AGENT-SKILLS-RESEARCH.md, ASSESSMENT.md: baner historyczny z linkiem do dokumentu zastępującego; PRODUCT-FOCUS:7 przestaje „bind" BACKLOG.md | każdy top-level plik w docs/ ma status i jest osiągalny z indeksu |
| 2.8 | HARNESS-SERVICE-CONTRACT: tytuł „1.1" → „1.1 + addytywne 1.2"; `/health/ready` może ogłaszać `contract_version` mgmt | jedna linia + opcjonalne pole |
| 2.9 | MoSCoW 09-09: jeden status (nagłówek vs §9), decyzja z 0.6 | brak dwóch statusów w jednym pliku |
| 2.10 | `.claude/README.md`: matcher `MultiEdit`, data, obietnica check_skills | zgodne z `settings.json` |
| 2.11 | Nietrackowane kopie `skills/higgsfield-*` (identyczne z `.agents/skills/higgsfield-*`): usunąć z `skills/` — to katalog dystrybucyjny, nie miejsce na skille firm trzecich | `git status` czysty w `skills/` |

### PRIO 3 — dług architektoniczny (przyrostowo, z pomiarem; po ACT-01)

| # | Zadanie | Reguła |
|---|---|---|
| 3.1 | `package main` → `internal/retrieval` (routing, use12, proof_gate, store, bm25f, dense, family12, contract): najpierw testy parity bit w bit, potem przenosiny plik po pliku | ADR-0032, PIVOT-ARCHITECTURE „Retrieval/Delivery" |
| 3.2 | SQL z handlerów `identity`/`knowledge`/`review` do pakietów `domain` + porty, zaczynając od handlerów zmienianych w bieżącej pracy (nie masowy refaktor) | ADR-0032, refactoring-rules |
| 3.3 | `guidefold report` z powrotem do `validate --base` (odstępstwo YAGNI zapisane 09-07 w PIVOT-BACKLOG) | KISS/YAGNI |
| 3.4 | ADR-0012: albo zbudować `card` przy SessionStart i zdjąć hierarchy-index z fixture, albo przepisać ADR na to, co robi `hook`/`prewarm`, i zaakceptować | adr-writing |

### PRIO 4 — nie zaczynać przed dowodem ACT-01

- ADR-0039 proof-gated jako **domyślna** polityka i ADR-0040 edgewise ascent: bramki dowodowe niespełnione; opt-in (Accepted) zostaje.
- Kolejne redesigny landingu i konsoli: MoSCoW §7 („frontend wygląda na gotowy, API nie startuje") stracił aktualność w części API, ale reguła zostaje: bez dowodu użycia nie ma następnej rundy UI.

## 5. Decyzje właściciela (ta sama sesja, po pytaniach audytu)

| Pytanie | Decyzja | Zapisane w |
|---|---|---|
| Partner do 09-20 | **Guidefold self-use** w org `cloudfloo` + **drugie repo tej organizacji** jako test multi-repo (nazwa do podania) | PRODUCT-FOCUS „Design partner" |
| Jeden backlog | **PIVOT-BACKLOG P01–P16**; MoSCoW i BACKLOG.md historyczne | PIVOT-BACKLOG, nagłówki MoSCoW i BACKLOG.md |
| Zdanie pozycjonujące | **30 000 skilli / duplikacja / zarządzanie / piramida** (polecenie 09-09) jako jedyna teza hero; proof-gated i „zatwierdzone instrukcje" pomocnicze | PRD §12a; landing i README do przepisania (1.9) |
| ADR-0036 `ascend.run` | **dokończyć teraz** (git w obrazie workera, egress, test akceptacyjny) | ADR-0036; 1.1 |
| ADR-0039 proof-gated | **Accepted jako opt-in**; tryb domyślny dalej za bramką E2 | ADR-0039, indeks |
| `/demo` | **usunięte** (trasa, plik, test); `pnpm test` 452/452, tsc czysty | `ui/src/app.tsx`, `ui/src/routes/DemoRoute*` |
| Multi-repo (ADR-0042) | **od razu, w Pilot Core** jako P16, przed pierwszą sesją ACT-01 (wbrew rekomendacji audytu; zapisane jako decyzja) | ADR-0042 Accepted, PIVOT-BACKLOG P16, PRD §4 nota |

Otwarte: nazwa drugiego repozytorium, owner skilli, harness i data startu do wpisania w PRODUCT-FOCUS.

## 6. Czego ten audyt nie dowodzi

Nie uruchamiano `pnpm test:e2e` ani `tests/acceptance` na żywym stosie w tej sesji; wynik 41/41 z 2026-09-08 jest cytowany, nie odtworzony. Sonda produkcji sprawdza dostępność endpointów, nie przebieg logowania prawdziwym kontem. Żadna pozycja nie jest „done" w sensie ADR-0029 r3.
