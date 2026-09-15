# ACT-01 — runbook produkcyjny Pilot Core dla właściciela

Status: instrukcja wykonawcza. Data: 2026-09-15. Napisana na podstawie **lokalnej próby generalnej** ([raport](../reports/pilot/2026-09-15-pilot-core-rehearsal.md)) — wszystko, co ten runbook obiecuje, jest dowodem **R**; dowodem **P** stanie się dopiero przebieg na produkcji, wykonany ręką właściciela i zapisany według §10.
Cel: jedna ścieżka od zalogowania do decyzji właściciela, którą da się wykonać na `guidefold.cloudfloo.io` w jednym posiedzeniu, z zapytaniem dowodowym po każdym kroku, tak aby licznik z [raportu stanu 2026-09-15](../reports/product/2026-09-15-mvp-closure-status.md) §3 (`imports 0, skills 0, publications 0, tokens 0, gf.events 0`) przestał być zerem.
Wejścia: [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §13 (definicja Pilot Core), [PIVOT-BACKLOG](../PIVOT-BACKLOG.md) („Dwa poziomy dostarczenia", ACT-01), [API-CONTRACT](../API-CONTRACT.md) §4, [HOWTO-adapter](../HOWTO-adapter.md), [pilot-evidence](../../.agents/skills/pilot-evidence/SKILL.md).
Zakres zastępowania: brak. Runbook nie zmienia U1–U11, P01–P15 ani ADR; nie nadaje zgody na żadną zmianę produkcji poza wymienionymi tu krokami produktowymi. Każdy dowód zebrany tą drogą jest etykietowany `self-use` zgodnie z decyzją właściciela z 2026-09-12 (PRODUCT-FOCUS), a `self-use` nie jest dowodem popytu ani płatności.

## 0. Lista przedlotowa — rozstrzygnąć **przed** rozpoczęciem

Żadnego z tych punktów nie da się rozwiązać agentem; wszystkie należą do właściciela.

| # | Do rozstrzygnięcia | Dlaczego blokuje | Jak sprawdzić, że zrobione |
|---|---|---|---|
| P1 | **GitHub App: uprawnienie „Email addresses: Read-only"** | logowanie GitHubem kończy się w WorkOS `oauth_failed` („Error fetching GitHub profile"); jeśli właściciel loguje się Google, można to pominąć na dziś, ale sesja zewnętrzna z §7 tego wymaga | zalogowanie GitHubem kończy się powrotem na `/` z ustawioną sesją; w logach API brak `oauth_failed` |
| P2 | **`guidefold.yaml` albo zero-config** | worker odmawia importu drzewa bez mapy. Dwie drogi: (a) wpisać plik do `wiatrM/guidefold` (patrz §2, wzór gotowy), (b) zmergować zmianę zero-config z `feat/zero-config-scope-map`. **Nie zaczynaj §3 bez jednej z nich** | `GET {repo_base}/imports/{id}` kończy się `state: ready`, nie `failed` z `import_tree_has_no_guidefold_yaml` |
| P3 | **`.guidefoldignore` z `examples/monorepo/`** — w tym samym commicie co P2a | skille fixture Meridian wchodzą jako `urn:skill:cloudfloo:_root:*`, a ich `requires` wskazuje `urn:skill:meridian:*`; publikacja pada na `missing_dependency`. Dodanie wykluczenia **po** pierwszym imporcie archiwizuje je i zasypuje kolejkę pozycjami `source_removed` | `scan --json` nie wymienia żadnego pliku spod `examples/monorepo/` |
| P4 | **Organizacja `cloudfloo` i nazwany deweloper spoza zespołu** z terminem sesji | PRODUCT-FOCUS „Design partner" wymaga pól: repo, deweloperzy, owner skilli, polityka danych, data startu; bez nazwiska §7 nie ma wykonawcy | wiersz w PRODUCT-FOCUS bez „to be named" |
| P5 | **Generator propozycji** | z generatorem `deterministic` ekstrakcja na prozie abstynuje (`no_procedure_found`), a konsolidacja zawsze `no_shared_procedure`. Jeśli §5 ma dać propozycję z prawdziwych dokumentów, potrzebny jest generator zdalny (`internal/review/generator/remote.go`) i jego konfiguracja | `GET {repo_base}/imports/{id}/plan` pokazuje `generator.name` inny niż `deterministic`, albo świadomie akceptujesz §5 wariant B |
| P6 | **Zapisz aktualne digesty obrazów** przed czymkolwiek | reguła „produkcja jest święta" pkt 4: rollback zaczyna się od zapisanej wartości | wpis w `deploy/k8s/environments/cloudfloo-io/README.md` |

> Ten runbook **nie zawiera** kroku zmiany wdrożenia. Jeśli którakolwiek z napraw z gałęzi `pilot/act01-rehearsal-20260915` ma trafić na produkcję, to jest osobne wydanie, z osobną zgodą właściciela, z Jobem migracji i uwierzytelnionym smoke testem (CLAUDE.md „Produkcja jest święta").

## 1. Konwencje zapisu dowodu

Po każdym kroku zapisz **jedną linię** w rejestrze wydań: datę UTC, krok, `request_id` z odpowiedzi API (każda odpowiedź go niesie) **albo** wynik zapytania dowodowego, oraz etykietę `self-use`. Zapytania dowodowe poniżej są **wyłącznie odczytem**.

Skróty: `{org_base}` = `/api/v1/orgs/cloudfloo`, `{repo_base}` = `{org_base}/repos/{repo_id}`.

Uwaga do SQL: `gf.events.payload` jest typu `bytea`, więc **nie** używaj `payload->>'…'`. Dostępne kolumny: `event_id, event_type, occurred_at, received_at, schema_version, tenant_id, search_id, load_id`.

## 2. Krok 1 — logowanie i organizacja

**Konsola.** Otwórz `https://guidefold.cloudfloo.io`, zaloguj się Google (albo GitHubem, jeśli P1 zrobione). Oczekiwany ekran: lista organizacji z `cloudfloo`.

**Dowód.**
```sql
SELECT count(*) FROM gfm.orgs;
SELECT count(*) FROM gfm.memberships;
```
oraz `GET /api/v1/me` → `200`, `user.email` = konto właściciela, `orgs[]` zawiera `cloudfloo`.

## 3. Krok 2 — przygotowanie repozytorium (P2a)

Jeżeli wybrałeś wariant „plik w repo", dodaj do `wiatrM/guidefold` jednym commitem:

`guidefold.yaml`
```yaml
publisher: cloudfloo
nodes:
  _root:
    paths: ["**"]
    owner: platform-engineering
  docs:
    paths: ["docs/**"]
    owner: platform-engineering
  docs.runbooks:
    paths: ["docs/runbooks/**"]
    owner: platform-engineering
```

`.guidefoldignore`
```
examples/monorepo/
```

**Dlaczego trzy węzły, nie jeden.** Przy płaskim `_root` z 81 skillami: Map pokazuje **jeden** scope, Pyramid **jedną** warstwę (`unclassified`), a `guidefold materialize` przerywa z „scope card for `_root` exceeds 80 lines", przez co `install` nie zbuduje artefaktu indeksu i hook pozostanie bezczynny. Trzy węzły usuwają wszystkie trzy objawy. Plan ekstrakcji ma też budżet **20 dokumentów na scope**, więc dokumenty spoza pierwszej dwudziestki alfabetycznej są dla ekstrakcji nieosiągalne, dopóki nie dostaną własnego węzła.

## 4. Krok 3 — skan i import

**CLI (zalecane dla pierwszego przebiegu — widać każdy stan).** W klonie `wiatrM/guidefold`:
```sh
export GUIDEFOLD_API=https://guidefold.cloudfloo.io
export GUIDEFOLD_ORG=cloudfloo GUIDEFOLD_REPO_ID=<repo_id z konsoli>
python3 skills/guidefold/scripts/guidefold login        # §6, urządzenie
python3 skills/guidefold/scripts/guidefold scan --json | head -40
python3 skills/guidefold/scripts/guidefold import --wait --json
python3 skills/guidefold/scripts/guidefold status <import_id> --json
```
Oczekiwane: `scan` wypisuje `complete: true`, `dirty: false` i `commit` równy HEAD; `import` kończy się `"state": "ready"`.

**Konsola.** Import przez GitHub App (`POST {repo_base}/github/import`) robi to samo bez klonu, ale nie pokazuje manifestu przed wysłaniem. **Użyj CLI za pierwszym razem**, konsoli przy kolejnych.

**Czego się spodziewać, jeśli coś pójdzie nie tak.**

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `state: failed`, `build_tree_failed: FileNotFoundError … guidefold.yaml` | P2 nie zrobione | dodaj mapę albo weź zero-config |
| `state: partial`, `failed: N`, publikacja aktywna z adnotacją „Partial" | karta z niepoprawnym YAML-em we frontmatterze (najczęściej niecytowany dwukropek w `description:`) | od kontraktu 1.17.0 reszta importu **publikuje się**, a każdy nieudany plik dostaje pozycję kolejki `import_file_failed`; napraw karty i zaimportuj ponownie. `import_partial` zostaje wyłącznie, gdy po odjęciu nieudanych plików nie ma czego publikować. Gałąź `pilot/act01-rehearsal-20260915` naprawia dziesięć takich kart w tym repozytorium i dodaje test, który je łapie |
| publikacja `missing_dependency` | P3 nie zrobione — fixture Meridian wszedł do importu | dodaj `.guidefoldignore` i zaimportuj ponownie |

**Dowód.**
```sql
SELECT id, state, commit, created_at FROM gfm.imports ORDER BY created_at DESC LIMIT 3;
SELECT publication_status, count(*) FROM gfm.skills GROUP BY 1;
```
Oczekiwane po udanym imporcie: `imports ≥ 1` ze stanem `ready`, `skills > 0`.

## 5. Krok 4 — Library: lista, źródła, trzy osie

**Konsola.** Library → lista skilli; wejdź w jeden skill → zakładka źródła (ścieżka, `content_sha256`, rewizja, surowe bajty). Potem Map (repozytorium, scope'y) i Pyramid (warstwy).

**API, jeśli chcesz `request_id` do rejestru.**
```
GET {org_base}/skills?limit=100
GET {repo_base}/skills/{skill_id}
GET {repo_base}/skills/{skill_id}/revisions/{revision_id}/raw
GET {repo_base}/map/repository
GET {repo_base}/map/scopes
GET {repo_base}/map/layers
GET {repo_base}/map/relations
```
Wszystkie `200`. **Pyramid pokaże `unclassified` dla każdej karty**, dopóki karty nie mają `metadata.layer` — to nie jest błąd, to brak danych; nie raportuj tego jako zera.

**Dowód.**
```sql
SELECT scope, count(*) FROM gfm.skills WHERE publication_status='published' GROUP BY 1 ORDER BY 2 DESC;
```

## 6. Krok 5 — jedna ograniczona propozycja ekstrakcji i jeden wspólny element

Najtrudniejszy krok §13 PRD i jedyny, który w próbie generalnej **nie wyszedł sam z siebie**.

```sh
python3 skills/guidefold/scripts/guidefold extract --all --wait --json
```

**Wariant A (generator zdalny, P5 zrobione).** Sprawdź `GET {repo_base}/imports/{import_id}/plan?profile=one_shot` — wypisze grupy `extraction:*`, `enrichment:*`, `consolidation:*`. Po `extract` porównaj `proposals_by_kind` z listą grup z planu.

**Wariant B (generator `deterministic`).** Spodziewaj się `proposals: 0` i abstencji `no_procedure_found` — deterministyczna receptura wyciąga **procedury** (ponumerowane kroki), a dokumenty tego repozytorium są prozą. Aby mimo to domknąć krok §13:
1. wskaż katalog, w którym naprawdę leżą procedury (runbooki, instrukcje wdrożeniowe), i nadaj mu własny węzeł w `guidefold.yaml` — inaczej budżet 20 dokumentów na scope go nie obejmie;
2. jeżeli `extract --all` nadal zgłasza `planned_groups` mniejsze niż liczba grup w planie i zero ekstrakcji, wymuś jeden rodzaj:
   `POST {repo_base}/imports/{import_id}/proposals:generate` z ciałem `{"idempotency_key":"…","profile":"one_shot","kinds":["extraction"]}`.

**Konsolidacja („wspólny element")** w próbie generalnej abstynowała za każdym razem (`no_shared_procedure`: „no run of 3 identical ordered steps appears in two procedures"). Jeśli i u Ciebie tak wyjdzie, **zapisz to jako abstencję, nie jako porażkę i nie jako zero** — i zanotuj, że ten podpunkt §13 pozostaje otwarty.

**Decyzja właściciela z powodem** (Proposals → Approve, albo API):
```
POST {repo_base}/proposals/{proposal_id}/decision
{"idempotency_key":"…","decision":"approve","reason":"<jedno zdanie: dlaczego ta karta jest prawdziwa>"}
```

**Dowód.**
```sql
SELECT kind, state, count(*) FROM gfm.proposals GROUP BY 1,2;
SELECT count(*) FROM gfm.decisions;
```
Oczekiwane: `proposals ≥ 1`, `decisions ≥ 1`.

## 7. Krok 6 — Git roundtrip

```sh
# eksport łatki dla zatwierdzonej propozycji
curl -X POST … {repo_base}/proposals/{proposal_id}/export    # -> export_id, base_commit
git switch -c pilot/act01-extraction
python3 skills/guidefold/scripts/guidefold proposals apply <export_id>            # sam diff
python3 skills/guidefold/scripts/guidefold proposals apply <export_id> --write
git add -A && git commit && git push -u origin pilot/act01-extraction
```
Guidefold **nigdy nie commituje ani nie pushuje** — to robi właściciel. Otwórz PR, zmerguj, a potem zaimportuj ponownie (`import --wait`) i opublikuj.

Sprawdź, że karta wróciła z właściwą tożsamością: ścieżka pliku musi odpowiadać **prawdziwemu katalogowi** węzła (dla węzła `docs.runbooks` → `docs/runbooks/.agents/skills/<nazwa>/SKILL.md`, nie `docs.runbooks/…`).

**Dowód.**
```sql
SELECT skill_id, scope, path, publication_status FROM gfm.skills WHERE path LIKE '%runbooks%';
SELECT state, n_skills, commit FROM gfm.publications ORDER BY created_at DESC LIMIT 3;
```
Oczekiwane: nowy skill `published`, najnowsza publikacja `active`, `commit` = commit po merge'u.

## 8. Krok 7 — publikacja i odpowiedź SEARCH/USE

```
POST {repo_base}/publish   {"idempotency_key":"…","import_id":"…"}
GET  {repo_base}/snapshots        -> items[0].state == "active", validation.ok == true
GET  /health/ready                -> 200
POST /v1/search                   -> 200, karty z tej organizacji
POST /v1/use                      -> 200
```

**Pułapka rewizji.** `POST /v1/use` przyjmuje **`card_revision`**, a `GET {repo_base}/skills/{skill_id}` zwraca i `revision_id`, i `card_revision`. Użycie `revision_id` daje `409 revision_mismatch` z `hint: "send card_revision from the catalog"` (kontrakt 1.17.0). `guidefold find` drukuje właściwą wartość — bierz ją stamtąd.

**Druga pułapka.** `503 snapshot_policy_mismatch` znaczy, że `skills/guidefold/scripts/guidefold` zmienił się po zbudowaniu snapshotu. Lekarstwo to ponowny import i publikacja, nie debugowanie uwierzytelnienia.

**Dowód.** `SELECT state, count(*) FROM gfm.publications GROUP BY 1;` → `active ≥ 1`.

## 9. Krok 8 — adapter i realna sesja (jeden harness)

W klonie repozytorium, na maszynie **dewelopera z P4**:
```sh
python3 .agents/skills/guidefold/scripts/guidefold install --harness claude
python3 .agents/skills/guidefold/scripts/guidefold login       # kod urządzenia; zatwierdź w konsoli
python3 .agents/skills/guidefold/scripts/guidefold index       # jeśli install ostrzegł o karcie scope
```
Potem **prawdziwa sesja Claude Code** w tym katalogu, z zadaniem, które deweloper i tak by wykonał. Hook `SessionStart` wstrzykuje guidance; użycie karty kończy się `guidefold load <urn>@<card_revision>`. Na koniec:
```sh
python3 .agents/skills/guidefold/scripts/guidefold telemetry flush
```

**Trzy rzeczy, które w próbie generalnej zawiodły i zostały naprawione na gałęzi `pilot/act01-rehearsal-20260915`** — jeśli produkcja nie ma tych napraw, spodziewaj się ich:
- `install` kończy się `TypeError: '<' not supported between instances of 'dict' and 'dict'` i zostawia repozytorium w połowie zainstalowane;
- `load` zawodzi dla każdego klonu, którego katalog nie nazywa się dokładnie jak repo id (API odpowiada 403 na nagłówek `X-Guidefold-Repo`). Od naprawy D12 komunikat nazywa kod i podaje krok („forbidden", HTTP 403, `guidefold doctor`); starsza wersja CLI pokazywała tu „service USE failed (auth)" i wyglądało to na problem z logowaniem;
- nieudany `load` jest odrzucany przez ledger (`missing_required_field:cache_source`), więc porażki nie są widoczne w `gf.events`.

**Dowód.**
```sql
SELECT count(*) FROM gfm.tokens;
SELECT event_type, count(*) FROM gf.events GROUP BY 1 ORDER BY 1;
```
Oczekiwane po jednej sesji: `tokens ≥ 1` oraz **jednocześnie** `search_requested`/`search_results`, `card_injected` i `skill_load_completed` — PRODUCT-FOCUS wymaga SEARCH **i** LOAD w każdej sesji, nie jednego z nich.

## 10. Krok 9 — feedback, kolejka, drift i decyzja

```
POST {repo_base}/skills/{skill_id}/revisions/{revision_id}/feedback
     {"idempotency_key":"…","verdict":"helped|hindered|mixed|not_applicable|unknown","reason":"…"}
GET  {repo_base}/usage?window=30d          -> totals.feedback, queue[]
POST {repo_base}/usage/queue/{item_id}/decision
     {"idempotency_key":"…","action":"reviewed","reason":"…"}
```

**Drift (U9/P13).** Zmień treść pliku źródłowego opublikowanego skilla, zmerguj, zaimportuj ponownie. Pozycja `source_changed` pojawia się w `queue[]`, a skill przechodzi w `needs_review`; decyzja `reviewed` wraca go do `published` w tej samej transakcji.

**Dowód.**
```sql
SELECT publication_status, count(*) FROM gfm.skills GROUP BY 1;   -- needs_review pojawia się i znika
SELECT event_type, count(*) FROM gf.events WHERE event_type='skill_feedback' GROUP BY 1;
```

## 11. Krok 10 — drugi harness (Copilot CLI)

**Nie było możliwe do sprawdzenia w próbie generalnej**: na maszynie, na której ją wykonano, nie ma ani `copilot`, ani `gemini` (`which copilot`, `which gemini` → brak). Nic nie zostało odegrane i nic nie jest tu obiecane.

Co właściciel musi zrobić, żeby zamknąć ten punkt (#82, #83):
1. zainstalować GitHub Copilot CLI i zalogować je do konta z dostępem do repozytorium;
2. w repozytorium: `guidefold install --harness copilot` — pisze `.agents/skills/guidefold/hooks/copilot.hooks.json` oraz pliki `.github/instructions/*` z `applyTo`;
3. w jednej realnej sesji wykonać kroki `find` i `load` opisane w [bootstrapie](../../skills/guidefold/SKILL.md), tak jak robi to deweloper;
4. `guidefold telemetry flush` i sprawdzić `gf.events`.

**Uczciwe ograniczenie, które trzeba zapisać w macierzy adapterów.** Copilot CLI nie daje adapterowi hooka odpowiadającego `SessionStart` Claude Code, więc:
- wstrzyknięcie kontekstu jest **deklaratywne** (pliki instrukcji czytane przez harness), a nie wywołane przez Guidefold;
- adapter **nie obserwuje**, czy karta rzeczywiście trafiła do promptu — `card_injected` z tej ścieżki jest wnioskowany, nie zaobserwowany;
- `USE` jest widoczny tylko wtedy, gdy deweloper sam wywoła `guidefold load`.
Zapisz to jako `unknown`, nie jako zero.

## 12. Krok 11 — zamknięcie

Na koniec sesji zapisz w rejestrze wydań jedną tabelę: krok, `request_id` albo wynik zapytania, wynik (`pass` / `abstained` / `open`), etykieta `self-use`. Skopiuj do niej końcowe liczniki:

```sql
SELECT (SELECT count(*) FROM gfm.imports)      AS imports,
       (SELECT count(*) FROM gfm.skills)       AS skills,
       (SELECT count(*) FROM gfm.proposals)    AS proposals,
       (SELECT count(*) FROM gfm.decisions)    AS decisions,
       (SELECT count(*) FROM gfm.publications) AS publications,
       (SELECT count(*) FROM gfm.tokens)       AS tokens,
       (SELECT count(*) FROM gf.events)        AS events;
```

Punkt 3 ścieżki krytycznej z [raportu stanu](../reports/product/2026-09-15-mvp-closure-status.md) §4a jest domknięty, gdy `imports ≥ 1`, `skills > 0`, `proposals ≥ 1`, `decisions ≥ 1`, `publications ≥ 1`. Punkt 5 — gdy `tokens ≥ 1` i w `gf.events` istnieje sesja mająca **i** SEARCH, **i** LOAD. Brak obserwacji zapisz jako `unknown`; nie zastępuj go zerem.
