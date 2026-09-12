# Wielorepozytoriowe organizacje, CI configurator, ustawienia LLM per organizacja — specyfikacja projektowa

Status: propozycja (Proposed); nic poniżej nie jest wdrożone — brak kodu, brak migracji, brak zmiany API-CONTRACT.md. Data: 2026-09-12.
Cel: najmniejszy model danych wspierający „N repozytoriów źródłowych → propozycje → jedno repozytorium skilli” oraz „ustawienia generatora per organizacja z zaszyfrowanymi kluczami, których używa zainstalowana aplikacja GitHub”, zgodnie z ADR-0036 (GitHub App, Proposed) i ADR-0038 (BYOK/marża, Accepted).
Wejścia: PRODUCT-PIVOT (U1, §12a), PIVOT-ARCHITECTURE („Granice modułów”), API-CONTRACT 1.3.0 §2–§8, ADR-0034, ADR-0035, ADR-0036, ADR-0038, `templates/ci.yml`, `templates/github-workflows-skills.yml`, `services/search/internal/review/generator/{generator.go,remote.go}`, `.agents/skills/{security-baseline,scope-change-protocol,product-direction-guard}/SKILL.md`.
Zakres zastępowania: żaden — nowy dokument projektowy. Nie zastępuje ani nie zmienia `docs/API-CONTRACT.md` (obowiązujący pozostaje 1.3.0); §5 poniżej jest materiałem do przyszłej wersji kontraktu, nie edycją. Towarzyszy mu [ADR-0042](../../adr/ADR-0042-multi-repo-organisation-and-ci-configurator.md) (Proposed).

## 0. Rozbieżności (scope-change-protocol)

**Rozbieżność 1:** polecenie właściciela „multi repository organization” vs PRODUCT-PIVOT §4 „U1 — skan i synchronizacja **monorepo**” i PRODUCT-FOCUS (klient to platform team jednego monorepo).
Decyzja w tej pracy: dokumentuję jako Proposed rozszerzenie U1, zgodnie z bieżącym poleceniem właściciela; nie zmieniam treści PRODUCT-PIVOT.
Dokument zastępowany lub do zmiany: PRODUCT-PIVOT §4 (U1), PIVOT-BACKLOG (nowa pozycja); status: do aktualizacji dopiero po akceptacji ADR-0042.
Konsekwencje: R/Q/P dla U1 nadal liczą się na Meridian (monorepo); multi-repo nie ma jeszcze dowodu R.
Do decyzji właściciela: tak — czy przyjąć ADR-0042 do PIVOT-BACKLOG i nadać mu zakres wdrożeniowy.

**Rozbieżność 2:** komentarz w `generator.Select` (`services/search/internal/review/generator/generator.go`): „GUIDEFOLD_GENERATOR jest konfiguracją operatora i nigdy polem żądania” vs polecenie właściciela „każda organizacja ustawia swój model”.
Decyzja w tej pracy: ustawienia generatora są własnością **organizacji** (ustawia je owner w UI, nie wywołujący per request), więc reguła „nigdy pole żądania” zostaje dosłownie zachowana — zmienia się tylko to, kto jest „operatorem płacącym”.
Dokument zastępowany lub do zmiany: komentarz w kodzie (poza zakresem — brak kodu tutaj); API-CONTRACT §8 akapit „Generator” (materiał §5).
Konsekwencje: `GUIDEFOLD_GENERATOR*` zostaje jako fallback wdrożenia, nie jest usuwany.
Do decyzji właściciela: nie — zgodne z bieżącym poleceniem.

## 1. Co dziś już działa, a czego brakuje

`gfm.repos` ma PK `(org_id, repo_id)` — organizacja **już dziś** może zarejestrować N repozytoriów (`POST {org_base}/repos` wielokrotnie), każde z własnymi importami pod swoim `{repo_base}/imports`. Brakuje wyłącznie: (1) oznaczenia, które repo jest docelowym repozytorium skilli; (2) trasy eksportu propozycji do repo innego niż repo importu; (3) ekranu CI configurator; (4) ustawień generatora per organizacja. Zmiana jest więc routingiem i UI nad istniejącym mechanizmem importu, nie nowym mechanizmem.

## 2. Model danych

### 2.1 Wybór spośród trzech wariantów z briefu

| Wariant | Ocena |
|---|---|
| `gfm.repos.role: source\|skills` | Odrzucony: drugie źródło prawdy — nic nie wymusza dokładnie jednego wiersza `role='skills'` na org (0 albo 2 pod współbieżnym zapisem), a `approve`/`export` muszą znać dokładnie jedno repo. |
| `skills_repo_id` na `gfm.orgs` | Odrzucony jako **miejsce**: Identity jest właścicielem zapisu `gfm.orgs` (PIVOT-ARCHITECTURE „Granice modułów”); Import musiałby pisać do cudzej tabeli. Sam pomysł (jedna nullowalna kolumna, FK do repo) zostaje. |
| `gfm.repo_links` (nowa tabela) | **Wybrany.** Jeden wiersz na organizację, własność modułu Import. Mieści też ustawienia CI configuratora — edytowane na tym samym ekranie, czytane razem przy każdym `generate`/`export`; rozbicie na dwie tabele dałoby tylko drugi odczyt bez izolacji (YAGNI). |

`gfm.repo_links`: `org_id uuid NN PK → gfm.orgs`, `skills_repo_id text NN → gfm.repos(org_id,repo_id)`, `source_repo_ids text[] NN d:'{}'`, `kinds text[] NN d:'{extraction}'` (podzbiór `extraction\|enrichment\|consolidation`), `schedule_cron text?`, `ci_mode text NN d:'customer_ci' CHECK(customer_ci\|github_app)`, `updated_by uuid`, `updated_at timestamptz NN d:now()`. Pisze: API/Import. Czyta: API (plan/generate/export), worker (schedule tick).

### 2.2 Propozycje i eksport przez granicę repo — addytywne

`gfm.proposals.repo_id` **zostaje** repo źródła importu, bez zmiany znaczenia. Nowa nullowalna kolumna `target_repo_id text? → gfm.repos`: `null` = to samo repo (dzisiejsze zachowanie, monorepo — bajt w bajt bez zmian), ustawione = `repo_links.skills_repo_id`. Analogicznie `gfm.exports.target_repo_id text?`. `approve` (`DecisionResult`) zapisuje `gfm.skills` pod `repo_id = target_repo_id ?? proposal.repo_id` — jeden katalog na organizację żyje pod repo skilli.

`kind:consolidation` działa wyłącznie na katalogu repo skilli (`repo_id = skills_repo_id`, `target_repo_id: null`) — porównuje rodzeństwo już zatwierdzonych/wyeksportowanych skilli, niezależnie od repo źródłowego pochodzenia. Ekstrakcja/enrichment działają per repo źródłowe, z opcjonalnym `target_repo_id`. Scope grupy (`ImportPlanGroup.scope`) rozwiązuje się zawsze wobec `gfm.scopes` repo **docelowego** (skilli) — patrz §9 Q1.

## 3. CI configurator (Organization › CI)

Ekran ownera: wybór repo skilli (`GET {org_base}/repos`), dodanie repozytoriów źródłowych (z listy instalacji GitHub App `GET {org_base}/github/installations[].repositories`, albo ręcznie `POST {org_base}/repos`), wybór `kinds`, harmonogram, budżety (§4). Zapis: `PUT {org_base}/ci/config` → `gfm.repo_links`.

| Tryb | Co powstaje | Token/sekret |
|---|---|---|
| `customer_ci` (domyślny, działa na bazie ADR-0035) | Workflow **dla repo skilli**, oparty o `templates/github-workflows-skills.yml` rozszerzony o krok `proposals:generate` wobec każdego `source_repo_id`; dla każdego repo źródłowego osobny, minimalny workflow „tylko import” (nowy szablon `templates/ci-source-import.yml`, poza tą pracą — repo źródłowe zwykle nie ma `.agents/skills/**`). | Jeden token CI **na repo źródłowe** — `gfm.tokens.repo_id` jest pojedynczą kolumną tekstową, nie da się związać jednego tokenu z wieloma repo. Zakres `validate import generate`, nigdy `publish` (API-CONTRACT §2). |
| `github_app` (token instalacji: ADR-0034/0036; job ekstrakcji: nowy, proponowany — §9 Q5) | Brak pliku workflow u klienta. Worker odczytuje `repo_links.schedule_cron` (nowy tick) i uruchamia **`extract.run`** (nowy, proponowany `kind` joba) dla każdego `source_repo_id` w tle — nigdy `ascend.run`, nigdy `proposal.generate` (§9 Q5). | Token instalacji z ADR-0034/0036; brak nowego sekretu u klienta. |

`github_app` jest wybieralny w UI dopiero, gdy `installations` zwraca ≥1 wiersz dla organizacji; inaczej opcja jest wyszarzona („Connect GitHub first”).

Minting tokenu CI nie potrzebuje nowej trasy: istniejący `POST {org_base}/installations` (API-CONTRACT §4.1, `{name, repo_id?, scopes, harness?} → Installation z token (raz)`) już przyjmuje `repo_id` (wiąże token z jednym repo źródłowym) i dowolny `scopes` z dozwolonej domeny — ekran CI configurator wywołuje go raz na repo źródłowe z `scopes:["validate","import","generate"]`, a `POST` przycisk „Download workflow files” osadza zwrócony `token` (widoczny raz, jak dziś) w pobranym pliku workflow zamiast każdej trasy w §5 potrzebować własnego mechanizmu wydawania sekretu.

## 4. Ustawienia LLM per organizacja

Nowa tabela `gfm.org_generator_settings`: `org_id uuid NN PK → gfm.orgs`, `provider text NN d:'none' CHECK(none\|openai\|anthropic\|azure)`, `model text?`, `azure_endpoint text?`, `azure_deployment text?`, `azure_api_version text?` (tylko `provider=azure`, §9 Q4), `api_key_ciphertext bytea?`, `api_key_last4 text?`, `kek_version int?`, `use_managed_key boolean NN d:false`, `max_usd_per_run numeric?`, `max_usd_per_month numeric?`, `updated_by uuid`, `updated_at timestamptz NN d:now()`. Pisze: API/Identity. Czyta: worker (wybór generatora), API (plan przed startem).

Szyfrowanie: AES-GCM z KEK per wdrożenie, `GUIDEFOLD_GENERATOR_KEK_FILE` (wzorzec `*_FILE` jak pozostałe sekrety), `kek_version` do rotacji bez jednorazowego re-encrypt całej tabeli. Surowy klucz dostawcy istnieje **tylko** w ciele żądania POST/PUT; żadna odpowiedź — także tworząca — go nie zwraca. To surowiej niż dzisiejszy wzorzec tokenów („sekret pokazywany jednorazowo w odpowiedzi tworzącej”, API-CONTRACT §2), bo to sekret **strony trzeciej**: ujawnienie ma większy promień rażenia niż `gf_…` (security-baseline, „Nie trzymaj sekretów tam, gdzie ich nie ma”). „Pokazany raz” = widoczny w polu formularza przeglądarki przed wysłaniem, nigdy odesłany z powrotem. GET zwraca wyłącznie `provider`, `model`, `api_key_last4`, `updated_at`.

Priorytet wyboru generatora w workerze (rozszerzenie `generator.Select`, Rozbieżność 2): (1) `org_generator_settings` tej organizacji, gdy `provider≠none`; (2) `GUIDEFOLD_GENERATOR*` środowiska wdrożenia (dzisiejszy fallback). `Recipe{Generator,Version,Model}` **musi** nieść provider/model organizacji, gdy użyte — `CacheKey` już zależy od `recipe.Version`/`recipe.Model`, więc bez tego zmiana modelu organizacji cicho odtworzyłaby stare propozycje z poprzedniego klucza cache. `ImportPlan.generator` (U2.7 — koszt widoczny przed startem) pokazuje ustawienia **organizacji**, nie zmienną środowiskową, gdy `provider≠none`.

Budżety (ADR-0038 — metering/capy, **nie** samoobsługowy billing z PRD §14 „Poza MVP”): `max_usd_per_run` zawęża `Limits.MaxUSD` joba, nigdy w górę ponad ceiling wdrożenia. `max_usd_per_month` sprawdzany **przed** enqueue (rezerwacja, ADR-0038 pkt 5) sumą `JobCost.usd_certain` organizacji w bieżącym miesiącu; `usd_uncertain` nie jest ani rozliczane, ani liczone jako zero — wymusza ręczne uzgodnienie, nigdy automatyczny dopłat. Gdy `use_managed_key=true`: opłata = `koszt_dostawcy / (1 − 0.10)` (ADR-0038 pkt 3 — **nie** `×1.10`, to dałoby tylko 9,09% marży). Bez skonfigurowanego dostawcy job kończy się jak dziś `skipped`/`llm_not_configured` (U2.7).

## 5. Dodatki do API-CONTRACT — projekt, NIE stosowany do `docs/API-CONTRACT.md`

| Metoda | Ścieżka | Rola / zakres | Wejście | Wyjście | Błędy | Idem. | P / AC |
|---|---|---|---|---|---|---|---|
| GET | `{org_base}/ci/config` | member | — | `CiConfig` | `not_found` | nie | U1 / AC7 |
| PUT | `{org_base}/ci/config` | owner+CSRF | `{idempotency_key, skills_repo_id, source_repo_ids[], kinds[], schedule_cron?, ci_mode}` | `CiConfig` | `invalid_request`, `repo_not_found` | tak | U1 / AC1, AC2 |
| GET | `{org_base}/ci/config/workflow` | owner | `repo_id` | `text/yaml` wygenerowany plik | `ci_not_configured` | nie | U1 / AC6 |
| GET | `{org_base}/generator` | owner | — | `GeneratorSettings` | `not_found` | nie | U1 / AC4, AC7 |
| PUT | `{org_base}/generator` | owner+CSRF | `{idempotency_key, provider, model?, api_key?, use_managed_key?, max_usd_per_run?, max_usd_per_month?}` | `GeneratorSettings` | `invalid_request`, `unsupported_provider` | tak | U1 / AC3, AC4 |
| POST | `{org_base}/generator/rotate-key` | owner+CSRF | `{idempotency_key, api_key}` | `GeneratorSettings` | `invalid_request` | tak | U1 / AC4 |
| GET | `{repo_base}/imports/{import_id}/plan` *(istniejąca trasa, API-CONTRACT §4.2 — nota semantyki, nie nowa trasa)* | owner (bez zmian) | — (bez zmian) | `ImportPlan` (bez zmian struktury); `ImportPlanGroup.scope` rozstrzygane wobec `gfm.scopes` repo **docelowego** (skilli), gdy istnieje `repo_links` (§2.2) | bez zmian | bez zmian | P06 / U2.7 |

DTO: `CiConfig` (`skills_repo_id:str!, source_repo_ids:[]str!, kinds:[]str!, schedule_cron:str?, ci_mode:{customer_ci|github_app}!, updated_at:ts?`); `GeneratorSettings` (`provider:{none|openai|anthropic|azure}!, model:str?, api_key_last4:str?, use_managed_key:bool!, max_usd_per_run:num?, max_usd_per_month:num?, updated_at:ts?`) — nigdy pole z surowym kluczem.

Nowe kody błędów: `repo_not_found` (404, repo spoza `gfm.repos` tej org — wzorzec istniejących kodów `*_not_found` dla nieznanego ID we własnej org, np. `import_not_found`/`proposal_not_found`, API-CONTRACT §3), `unsupported_provider` (400, `azure` bez wymaganych pól albo provider spoza domeny), `ci_not_configured` (404, brak wiersza `repo_links`). Zmiana `gfm.jobs.payload` dla `proposal.generate`: dodane opcjonalne `target_repo_id:str?` (addytywne, brak pola = dziś).

Nowe `kind`y joba (oba tylko `ci_mode=github_app`, oba proponowane, żaden dziś w API-CONTRACT §8 — §9 Q5):

| `kind` | Wejście | Wyjście | Checkpoint | Limity |
|---|---|---|---|---|
| `ci.schedule.tick` | `org_id`, `repo_links` | po jednym `extract.run` na `source_repo_id` | ostatni obsłużony `source_repo_id` | jak `extract.run` |
| `extract.run` (nowy `kind` — **nie** `ascend.run`, §9 Q5) | `org_id`, `source_repo_id`, `target_repo_id` (= `skills_repo_id`), referencja do `org_generator_settings` (§4) | klon repo źródłowego tokenem instalacji (ta sama ścieżka co ADR-0036 pkt 2), ekstrakcja piramidy ustawieniami generatora organizacji; PR do repo skilli albo wpis w kolejce review `gfm.proposals`, zależnie od `ci_mode` | ostatni ukończony poziom/scope (wzorem `ascend.run`) | `max_levels`, `max_calls`, `max_usd`, `max_tokens` (wzorem `ascend.run`, API-CONTRACT §8) |

Nowe tabele `gfm`: `repo_links` i `org_generator_settings` (§2.1, §4). Zmienione (addytywnie, nullable): `gfm.proposals.target_repo_id`, `gfm.exports.target_repo_id`.

## 6. Bezpieczeństwo

- Klucz dostawcy: nigdy w przeglądarce po zapisie, nigdy w logu/audycie/`details` błędu, szyfrowany KEK-iem per wdrożenie z pliku, nigdy w treści repozytorium eksportu.
- Token CI jest per repo źródłowe, zakres `validate import generate`, nigdy `publish`/`membership` — zgodnie z istniejącą regułą tokenu CI (API-CONTRACT §2).
- `gfm.audit` dostaje wpisy `ci_config.updated`, `generator_settings.updated`, `generator_key.rotated` — `actor` jak dziś (pseudonim principala), `entity` = `org_id`, **nigdy** wartość klucza w `revision`/`entity`.
- Member widzi `CiConfig` (bez sekretów) do odczytu; `GeneratorSettings` jest **owner-only** także do odczytu — to informacja finansowa organizacji (który dostawca płaci, `use_managed_key`), nie operacyjna.
- Cross-repo `target_repo_id` nie omija izolacji org/repo per request (security-baseline): oba repo muszą należeć do tej samej `org_id`; `target_repo_id` spoza `gfm.repos` tej organizacji to `404 repo_not_found`, nigdy ciche przypisanie.

## 7. UI — IA i makieta

Rozszerzenie istniejącego widoku Organization (`docs/ui/IA.md` §3): trzecia zakładka **CI** obok Members i Integrations — wybór repo skilli, repozytoria źródłowe, kinds, harmonogram, budżety, ustawienia LLM. Stringi UI po angielsku (projektowa konwencja).

```
Organization > CI                                            [Save]
+-------------------------------------------------------------+
| Skills repository        [ meridian/skills-hub          v ] |
|                                                               |
| Source repositories                                          |
|  [x] meridian/atlas-service       extraction, enrichment     |
|  [x] meridian/graph-api           extraction                 |
|  + Add repository...                                         |
|                                                               |
| Schedule   [ nightly 02:00 UTC v ]   Mode (o) Customer CI     |
|                                        ( ) GitHub App*        |
| Budgets    max/run [ $2.00 ]   max/month [ $120.00 ]          |
|                                                                |
| LLM settings                                                  |
|  Provider [ Anthropic         v ]  Model [ claude-sonnet-4-5] |
|  API key  [ **********1234  Rotate ]  (o) BYOK  ( ) Managed   |
|                                                                |
| [ Download workflow files ]     *GitHub App: connect first    |
+-------------------------------------------------------------+
```

Stany (IA.md §6, macierz pełna w etapie4): **empty** — brak `repo_links`, CTA „Add your first source repository”; **loading**; **partial** — któryś source repo bez ukończonego importu, oznaczony etykietą, nieukryty; **error** — zapis nieudany, poprzednia konfiguracja zachowana; **degraded** — instalacja GitHub App utracona, `ci_mode` automatycznie cofnięty do `customer_ci` z banerem; **member, bez operacji ownera** (IA.md §6 — to nie jest `restricted`: `restricted` w IA.md oznacza brak dostępu do danych org w ogóle, a member w uprawnionej organizacji to odrębny, zdefiniowany tam przypadek, który czyta) — read-only `CiConfig` bez przycisku Save, brak zakładki ustawień LLM w ogóle (nie „widoczna ale zablokowana” — nieobecna).

## 8. Migracja istniejących organizacji monorepo

Brak eager backfill. Organizacja bez wiersza `gfm.repo_links` zachowuje się jak dziś: jeśli ma dokładnie jedno zarejestrowane repo, ekran CI proponuje je jako skills+source w jednym polu i zapis pierwszego `PUT {org_base}/ci/config` materializuje `skills_repo_id = source_repo_ids = [to_repo]`. Do tego zapisu `target_repo_id` jest wszędzie `null` (bo kolumna jest nowa i nullowalna) — zachowanie identyczne co dziś, bajt w bajt, bez migracji danych. To mocniejsza odpowiedź niż backfill: nic w `gfm.proposals`/`gfm.exports` istniejących organizacji się nie zmienia.

## 9. Otwarte pytania dla właściciela

**Q1 — jak ścieżka repo źródłowego mapuje się na scope repo skilli?** (a) wyłącznie jawne mapowanie ownera w CI configuratorze; (b) podpowiedź z CODEOWNERS/katalogów repo źródłowego dopasowana nazwą do scope'u repo skilli, jak dziś `suggestions` (`ambiguous_node_match`); (c) połączenie — (b) jako propozycja, (a) jako zatwierdzenie. **Rekomendacja: (c)** — spójne z istniejącym mechanizmem `suggestions` (API-CONTRACT §5.6), ścieżka bez mapowania trafia do `excluded` z nowym powodem `unmapped_to_skills_repo_scope`, nigdy nie jest zgadywana.

**Q2 — czytanie „NOT IN CODE but ONLY in skill repository for other repositories also”.** (a) czysto techniczne: dziś ekstrakcja działa per-repo, ma zacząć działać dla wielu repo organizacji — pokrywa to cały §2–§3; (b) repo skilli ma **własne** dokumenty spoza kodu (np. centralne runbooki), które mają być źródłem ekstrakcji/konsolidacji stosowanym do wszystkich repo źródłowych, nie tylko do siebie. **Rekomendacja: obie** — (a) jest rdzeniem zmiany; (b) wymaga zero nowego mechanizmu, bo `source_repo_ids` już dziś może zawierać `skills_repo_id` (samoimport, `target_repo_id: null`) — repo skilli staje się wtedy zwykłym źródłem własnej organizacji.

**Q3 — domyślny `ci_mode` nowej organizacji.** Rekomendacja: `customer_ci` zawsze domyślny (działa bez zależności od ADR-0036); `github_app` wyłącznie po `Connect GitHub` i ≥1 instalacji — nigdy jako domyślny, bo ADR-0036 jest Proposed bez kodu.

**Q4 — `azure` jako provider: wdrażać teraz czy zostawić Proposed bez implementacji?** Rekomendacja: zostawić Proposed (pola `azure_*` zarezerwowane w §4, ale worker odrzuca `provider=azure` kodem `400 unsupported_provider` — jedyny status z §5/§3 zamkniętej listy API-CONTRACT, `501` tam nie istnieje — dopóki nie ma realnej potrzeby klienta) — YAGNI, brak dziś znanego klienta Azure OpenAI.

**Q5 — `ci_mode=github_app`: rozszerzyć `ascend.run` (ADR-0036) czy nowy `kind` joba?** `proposal.generate` (API-CONTRACT §8) odpada od razu — wymaga już sfinalizowanego wiersza `gfm.imports`, którego nic w trybie `github_app` nie tworzy (nie ma kroku `customer_ci`, który by go uploadował). Zostają dwie opcje dla joba, który ma faktycznie zrobić ekstrakcję: (a) rozszerzyć `ascend.run`; (b) nowy `kind` joba. **`ascend.run` (a) nie da się rozszerzyć bez zmiany jego znaczenia**: wyzwala się wyłącznie webhookiem PR, który zmienił istniejący `**/.agents/skills/**/SKILL.md` (ADR-0036 pkt 1) — harmonogram nie ma ani PR-a, ani zmienionego pliku do sprawdzenia; jego PR wraca do `base_ref` **tego samego** repo, które sklonował (ADR-0036 pkt 2) — nie istnieje ścieżka publikacji do *innego* repo, a configurator potrzebuje właśnie publikacji do repo skilli; i działa nad `git diff`/`validate` już istniejących skilli (ADR-0036 pkt 3), nie ekstrahuje z gołego kodu źródłowego — a repo źródłowe zwykle **nie ma** `.agents/skills/**` (§3). **Rekomendacja: (b) nowy `kind` joba `extract.run`** (proponowany, nie w API-CONTRACT §8) — wejście `org_id`, `source_repo_id`, `target_repo_id` (= `skills_repo_id`), referencja do ustawień generatora organizacji (§4); klonuje repo źródłowe tą samą ścieżką tokenu instalacji co ADR-0036 pkt 2 (jedyna część, którą dzieli z `ascend.run`), uruchamia ekstrakcję piramidy ustawieniami generatora organizacji (§4), i publikuje PR-em do repo skilli albo wpisem w kolejce review (`gfm.proposals`), zależnie od trybu — wyzwolony harmonogramem (`repo_links.schedule_cron` przez `ci.schedule.tick`), nie zdarzeniem `pull_request`. `proposal.generate` pozostaje zarezerwowany dla `ci_mode=customer_ci`, gdzie klient sam uploaduje i finalizuje import przed generowaniem propozycji. Job row §5 i ADR-0042 Decyzja pkt 3 są z tym spójne.

## 10. Kryteria akceptacji i testy

1. Org z dwoma repo źródłowymi i jednym repo skilli: ekstrakcja/enrichment per source repo, jedna konsolidacja nad połączonym katalogiem repo skilli; zatwierdzona propozycja ląduje w `gfm.skills` pod `repo_id = skills_repo_id` niezależnie od repo pochodzenia. Test: rozszerzenie `tests/acceptance/` na wzór acceptance testu ADR-0036 (2 repo źródłowe + 1 repo skilli, fake GitHub API, jeden `extract.run` na repo — §9 Q5).
2. Organizacja bez `repo_links` (dzisiejszy monorepo) ma `{repo_base}/proposals*` bajt w bajt identyczne — `target_repo_id` zawsze `null`. Test: istniejący fixture Meridian bez zmian, `pytest tests/` + `go test ./internal/review/...` bez regresji.
3. Zmiana modelu w ustawieniach organizacji zmienia `CacheKey` — ta sama grupa wejść nie zwraca odrzuconej wcześniej propozycji z innym modelem. Test: jednostkowy w `generator_test.go` (Go) dla `Recipe`/`CacheKey` z ustawieniami org zamiast env.
4. `GET {org_base}/generator` nigdy nie zwraca surowego klucza ani ciphertext. Test: kontraktowy (dekoder) + `grep -rn 'api_key_ciphertext\|api_key_raw' ui/src` puste.
5. Budżet miesięczny zatrzymuje nowe enqueue po przekroczeniu `usd_certain`; `usd_uncertain` nie jest liczone jako zero ani rozliczane automatycznie. Test: symulacja rezerwacji budżetu z częściowo niepewnym kosztem.
6. Token CI ma zakres `validate import generate`, nigdy `publish`, związany dokładnie z jednym `repo_id`. Test: rozszerzenie istniejącego testu zakresów tokenu (`identity` moduł).
7. Member widzi `CiConfig` read-only, nie widzi `GeneratorSettings` w ogóle (403/pominięta zakładka). Test: A/B ról jak w bramce 1 security-baseline.

Weryfikacja tego dokumentu: `python3 -m pytest tests/test_api_contract_doc.py -q` (kontrakt nietknięty — patrz raport), oraz ręczny przegląd renderowania tabel Markdown (brak złamanych wierszy).
