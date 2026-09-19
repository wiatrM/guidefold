# ACT-01 — runbook produkcyjny Pilot Core dla właściciela

Status: instrukcja wykonawcza. Data: 2026-09-15 (zaktualizowana po drugiej próbie). Napisana na podstawie dwóch lokalnych prób generalnych ([pierwsza](../reports/pilot/2026-09-15-pilot-core-rehearsal.md), [druga, na scalonym `main` @ `6d8e521`](../reports/pilot/2026-09-15-pilot-core-rehearsal-v2.md)) — wszystko, co ten runbook obiecuje, jest dowodem **R**; dowodem **P** stanie się dopiero przebieg na produkcji, wykonany ręką właściciela i zapisany według §10. Każda liczba poniżej, która zmieniła się między próbami, została zmierzona ponownie w drugiej.
Cel: jedna ścieżka od zalogowania do decyzji właściciela, którą da się wykonać na `guidefold.cloudfloo.io` w jednym posiedzeniu, z zapytaniem dowodowym po każdym kroku, tak aby licznik z [raportu stanu 2026-09-15](../reports/product/2026-09-15-mvp-closure-status.md) §3 (`imports 0, skills 0, publications 0, tokens 0, gf.events 0`) przestał być zerem.
Wejścia: [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §13 (definicja Pilot Core), [PIVOT-BACKLOG](../PIVOT-BACKLOG.md) („Dwa poziomy dostarczenia", ACT-01), [API-CONTRACT](../API-CONTRACT.md) §4, [HOWTO-adapter](../HOWTO-adapter.md), [pilot-evidence](../../.agents/skills/pilot-evidence/SKILL.md).
Zakres zastępowania: brak. Runbook nie zmienia U1–U11, P01–P15 ani ADR; nie nadaje zgody na żadną zmianę produkcji poza wymienionymi tu krokami produktowymi. Każdy dowód zebrany tą drogą jest etykietowany `self-use` zgodnie z decyzją właściciela z 2026-09-12 (PRODUCT-FOCUS), a `self-use` nie jest dowodem popytu ani płatności.

## 0. Lista przedlotowa — rozstrzygnąć **przed** rozpoczęciem

Żadnego z tych punktów nie da się rozwiązać agentem; wszystkie należą do właściciela.

| # | Do rozstrzygnięcia | Dlaczego blokuje | Jak sprawdzić, że zrobione |
|---|---|---|---|
| P1 | **GitHub App: uprawnienie „Email addresses: Read-only"** | logowanie GitHubem kończy się w WorkOS `oauth_failed` („Error fetching GitHub profile"); jeśli właściciel loguje się Google, można to pominąć na dziś, ale sesja zewnętrzna z §7 tego wymaga | zalogowanie GitHubem kończy się powrotem na `/` z ustawioną sesją; w logach API brak `oauth_failed` |
| P2 | **Sprawdzić wywnioskowane scope'y po imporcie; `guidefold.yaml` tylko po to, żeby je nadpisać** | zero-config jest scalony (ADR-0050, PR #176): drzewo bez mapy **importuje się** i `gfm.scopes.source` ma wartość `inferred`. Plik nie jest już warunkiem startu. Ale dla **tego** repozytorium mapa wywnioskowana to **jeden węzeł `_root`**, bo wszystkie karty leżą w jednym `.agents/skills/` w korzeniu: Map pokazuje 1 scope, Pyramid 1 warstwę `unclassified`, relacje 0 krawędzi. Jeżeli chcesz więcej niż jeden scope, wtedy — i tylko wtedy — napisz `guidefold.yaml` (wzór w §3); ma pierwszeństwo przed wszystkim | Map › Scopes po imporcie pokazuje listę scope'ów z etykietą `inferred` i `owner`. **W tym repozytorium nie ma CODEOWNERS**, więc każdy `owner` będzie `unknown`; to brak danych, nie błąd |
| P3 | **`.guidefoldignore` z `examples/monorepo/`, przed pierwszym importem** | zmierzone ponownie w drugiej próbie **bez** tego pliku: import `aefb5dd6` kończy się `ready`, ale publikacja `51795c71` pada `missing_dependency`, bo `requires` kart fixture'u Meridian wskazuje `urn:skill:meridian:*`, a import nadaje im `urn:skill:guidefold:*`. Publikacja częściowa z 1.17.0 **tego nie ratuje**: `missing_dependency` jest walidacją całej publikacji, nie porażką pojedynczego pliku. Dodanie wykluczenia **po** imporcie archiwizuje fixture i zasypuje kolejkę pozycjami `source_removed`. To wymaganie jest specyficzne dla tego repozytorium, bo trzyma własny fixture — repozytorium klienta go nie ma | `scan --json` nie wymienia żadnego pliku spod `examples/monorepo/`; w drugiej próbie: 417 plików bez wykluczenia, 379 z nim |
| P4 | **Organizacja `cloudfloo` i nazwany deweloper spoza zespołu** z terminem sesji | PRODUCT-FOCUS „Design partner" wymaga pól: repo, deweloperzy, owner skilli, polityka danych, data startu; bez nazwiska §7 nie ma wykonawcy | wiersz w PRODUCT-FOCUS bez „to be named" |
| P5 | **Generator propozycji** | z generatorem `deterministic` ekstrakcja na prozie tego repozytorium abstynuje — druga próba: **20 × `no_procedure_found`, 0 propozycji ekstrakcji**. Konsolidacja natomiast **działa** od PR #178 (jeden wspólny element z trzech bootstrapów `higgsfield-*`), więc podpunkt „wspólny element" z §13 domyka się bez modelu, a podpunkt „ekstrakcja" nie. Jeśli §6 ma dać propozycję ekstrakcji z prawdziwych dokumentów, potrzebny jest generator zdalny (`internal/review/generator/remote.go`) i jego konfiguracja | `GET {repo_base}/imports/{id}/plan?profile=one_shot` pokazuje `generator.name` inny niż `deterministic`, albo świadomie akceptujesz §6 wariant B |
| P6 | **Zapisz aktualne digesty obrazów** przed czymkolwiek | reguła „produkcja jest święta" pkt 4: rollback zaczyna się od zapisanej wartości | wpis w `deploy/k8s/environments/cloudfloo-io/README.md` |

> Ten runbook **nie zawiera** kroku zmiany wdrożenia. Wszystko, co on obiecuje, zakłada, że produkcja ma obrazy z `main` @ `6d8e521` lub nowsze — bez PR #176 i #177 krok §4 skończy się `import_tree_has_no_guidefold_yaml`, a §6a nie będzie miał czego rozstrzygać. Wydanie jest osobną pracą, z osobną zgodą właściciela, z Jobem migracji i uwierzytelnionym smoke testem (CLAUDE.md „Produkcja jest święta"); przygotowany, **niewykonany** plan: [2026-09-15-release-prep](../reports/deploy/2026-09-15-release-prep.md).

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

## 3. Krok 2 — przygotowanie repozytorium

**Obowiązkowy jest tylko `.guidefoldignore` (P3).** Dodaj go do `wiatrM/guidefold` jednym commitem:

`.guidefoldignore`
```
examples/monorepo/
```

`guidefold.yaml` **nie jest potrzebny do importu** (ADR-0050). Dopisz go tylko wtedy, gdy po §5 (Map › Scopes) zobaczysz jeden węzeł `_root` i chcesz innej hierarchii. Wzór, który druga próba potwierdziła jako działający:

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

**Dlaczego warto rozważyć trzy węzły, nie jeden.** Przy płaskim `_root` z 81 skillami Map pokazuje **jeden** scope, a Pyramid **jedną** warstwę (`unclassified`) — druga próba zmierzyła dokładnie to samo na mapie wywnioskowanej. Trzeci objaw z pierwszej próby, przerwanie `materialize` z „scope card for `_root` exceeds 80 lines", **jest naprawiony** (PR #180): karta jest skracana do 80 linii, a `install` uruchamia mapę, `materialize` i `index` w trzech osobnych blokach. Plan ekstrakcji ma budżet **20 dokumentów na scope**, więc przy jednym węźle dokumenty spoza pierwszej dwudziestki alfabetycznej są dla ekstrakcji nieosiągalne.

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
Oczekiwane (zmierzone w drugiej próbie na klonie tego repozytorium, commit `6d8e521`): `scan` wypisuje `complete: true`, `dirty: false`, `commit` równy HEAD, **417 plików i 108 sugestii bez `.guidefoldignore`, 379 plików z nim**; `import` kończy się `"state": "ready"`, `failed_files: []`.

`guidefold status <import_id>` wypisuje teraz kubełki po stanie pliku i **listuje tylko te, które nie są `accepted`** — po `accepted=406 failed=1 omitted=1` widać od razu, który plik się nie sparsował i z jakim błędem.

**Konsola.** Import przez GitHub App (`POST {repo_base}/github/import`) robi to samo bez klonu, ale nie pokazuje manifestu przed wysłaniem. **Użyj CLI za pierwszym razem**, konsoli przy kolejnych.

**Czego się spodziewać, jeśli coś pójdzie nie tak.**

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `state: failed`, `build_tree_failed: FileNotFoundError … guidefold.yaml` | **nie powinno już wystąpić** (ADR-0050). Jeśli wystąpi, produkcja nie ma obrazów z PR #176 | sprawdź digest `search`/`worker` w `Application/guidefold` wobec [release-prep](../reports/deploy/2026-09-15-release-prep.md) |
| `state: failed`, `guidefold_yaml_unreadable` | repozytorium **deklaruje** `guidefold.yaml`, którego ten przebieg nie potrafił przeczytać (dziś: plik ponad `ghapp.MaxFileBytes`) | popraw plik albo go usuń — wywnioskowanie mapy sprzecznej z zadeklarowaną byłoby gorsze niż odmowa |
| `state: ready`, ale Map › Scopes pokazuje jeden `_root` | to nie jest błąd: wszystkie karty leżą w jednym `.agents/skills/` w korzeniu (P2) | zostaw albo napisz `guidefold.yaml` |
| `state: partial`, `failed: N`, publikacja aktywna z adnotacją „Partial" | karta z niepoprawnym YAML-em we frontmatterze (najczęściej niecytowany dwukropek w `description:`) | od kontraktu 1.17.0 reszta importu **publikuje się**, a każdy nieudany plik dostaje pozycję kolejki `import_file_failed`; napraw karty i zaimportuj ponownie. `import_partial` zostaje wyłącznie, gdy po odjęciu nieudanych plików nie ma czego publikować. Dziesięć takich kart tego repozytorium jest naprawionych na `main` (PR #180) i pilnuje ich `tests/test_frontmatter.py`; druga próba zaimportowała to repozytorium z `failed_files: []` |
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
Wszystkie `200`. Zmierzone w drugiej próbie na mapie wywnioskowanej: `skills?limit=100` → 81 pozycji bez `next_cursor`; `map/scopes` → **1 scope `_root`, `source: "inferred"`, `owner: "unknown"`**; `map/layers` → `[{"layer":"unclassified","count":81}]`; `map/relations` → **0 krawędzi**.

Trzy rzeczy, których nie należy raportować jako zera:
- **Pyramid pokaże `unclassified` dla każdej karty**, dopóki karty nie mają `metadata.layer` — to brak danych, nie błąd.
- **0 krawędzi relacji** znaczy, że karty tego repozytorium nie deklarują `metadata.requires`. W pierwszej próbie były 24 krawędzie i wszystkie pochodziły z fixture'u Meridian, którego `.guidefoldignore` teraz nie wpuszcza.
- **`owner: unknown`** w każdym scope znaczy, że repozytorium nie ma CODEOWNERS.

**Dowód.**
```sql
SELECT scope, count(*) FROM gfm.skills WHERE publication_status='published' GROUP BY 1 ORDER BY 2 DESC;
```

## 6. Krok 5 — jedna ograniczona propozycja ekstrakcji i jeden wspólny element

Najtrudniejszy krok §13 PRD. Wspólny element **wychodzi** od drugiej próby; ekstrakcja z prozy tego repozytorium **nadal nie**.

```sh
python3 skills/guidefold/scripts/guidefold extract --all --wait --json
```

`--wait` czeka teraz także na zadania generowania, nie tylko na import (poprawka z 2026-09-15); bez niej komenda kończyła się w ułamku sekundy i raportowała stan sprzed generowania.

**Czego się spodziewać z generatorem `deterministic`** (dosłownie to, co wypisał przebieg na imporcie `33a84b61`, 7,4 s):

```json
{
  "planned_groups": 3,
  "kinds_requested": ["extraction", "enrichment", "consolidation"],
  "kinds_without_groups": [],
  "proposals": 7,
  "proposals_by_kind": {"consolidation": 1, "enrichment": 5, "scope_map": 1},
  "consolidations": [
    {"path": ".agents/skills/shared-if-higgsfield-is-not-on-path-install-it/SKILL.md",
     "target_scope": "_root",
     "sources": ["urn:skill:guidefold:_root:higgsfield-generate",
                 "urn:skill:guidefold:_root:higgsfield-product-photoshoot",
                 "urn:skill:guidefold:_root:higgsfield-soul-id"]}],
  "cost": {"calls": 0, "usd_certain": 0, "usd_uncertain": 0}
}
```
plus `abstentions` z 22 pozycjami: **20 × `no_procedure_found`** („the document has no ordered steps to extract") i 2 × `already_consolidated`.

**Wspólny element (`det-2`).** To jest ten jeden podpunkt §13, który w pierwszej próbie nie wyszedł wcale. Trzy karty `higgsfield-*` powtarzają dosłownie ten sam blok bootstrapu, a recepta `det-2` go wyciąga. Dwie rzeczy warto zobaczyć na własne oczy przed zatwierdzeniem: **nazwa karty jest zdaniem z pierwszego kroku**, nie tematem (`shared-if-higgsfield-is-not-on-path-install-it`), a `description` kończy się dwukropkiem. Jeśli ten tytuł Ci nie odpowiada, odrzuć propozycję — `edit` kandydata na tej ścieżce nie jest do tego przeznaczony.

**Ekstrakcja.** Grupa `extraction:_root` dostaje 20 dokumentów (`AGENTS.md`, `CLAUDE.md`, `README.md`, trzy `deploy/**/README.md`, czternaście `docs/adr/ADR-00xx-*`) i abstynuje na każdym. Deterministyczna receptura wyciąga **procedury** (ponumerowane kroki); dokumenty tego repozytorium są prozą. **Zapisz to jako abstencję, nie jako porażkę i nie jako zero.** Żeby domknąć ten podpunkt §13, masz dwie drogi:
- **Wariant A** — generator zdalny (P5). Sprawdź `GET {repo_base}/imports/{import_id}/plan?profile=one_shot`: `generator.name` musi być inny niż `deterministic`. Potem porównaj `proposals_by_kind` z listą grup z planu.
- **Wariant B** — świadomie przyjmij, że ekstrakcja abstynuje, i zapisz ten podpunkt jako otwarty.

## 6a. Krok 5a — decyzja o propozycji mapy scope (`scope_map`)

Nowe od ADR-0051 (PR #177). Każdy import uruchamia `scope_map.propose`; z generatorem `deterministic` zadanie proponuje **mapę wywnioskowaną**, tę samą, którą policzył ADR-0050, z `origin: "inferred"`. Z `none` kończy się `worker.Skipped("llm_not_configured")` i import zostaje użyteczny.

Zobacz, co zatwierdzasz — `ScopeMapDiff` jest liczony przy odczycie, więc pokazuje, co zrobiłaby decyzja **dzisiaj**:
```
GET {repo_base}/proposals            -> pozycja kind: "scope_map", state: "draft"
GET {repo_base}/proposals/{id}       -> scope_map.diff {added, reparented, owner_changed, paths_changed, unchanged}
```
W drugiej próbie diff był `unchanged: 1` — propozycja deterministyczna na tym repozytorium jest **no-opem**, bo mapa wywnioskowana i proponowana to ta sama mapa. To nie jest powód, żeby jej nie rozstrzygnąć: dopóki jest `draft`, źródłem scope pozostaje `inferred`.

**Decyzję podejmuje właściciel organizacji, na trasie organizacji.** Bliźniacza trasa repozytorium **odmawia**:
```
POST {repo_base}/proposals/{id}/decision  -> 403 forbidden
     "A scope map changes several repositories; decide it at the organization route."
POST {org_base}/proposals/{id}/decision
     {"idempotency_key":"…","decision":"approve","reason":"<jedno zdanie>"}
  -> 200 {"state":"applied","scopes_written":1}
```
Po zatwierdzeniu `gfm.scopes` ma `source = 'llm_approved'`, `reviewed_by` = Twój `user_id` i `proposal_id`. **Uwaga na etykietę:** `llm_approved` zapisuje się także wtedy, gdy propozycja powstała deterministycznie i żaden model jej nie dotknął. Wartość mówi „ktoś zatwierdził propozycję", nie „model ją wymyślił".

Właściciel, któremu mapa nie odpowiada, odrzuca ją i pisze `guidefold.yaml` — plik wygrywa z każdą propozycją. `edit` kandydata to `invalid_candidate_change`, `export` to `proposal_state_invalid`: mapa nie ma bajtów do wyeksportowania.

**Decyzja właściciela o propozycji ekstrakcji/konsolidacji z powodem** (Proposals → Approve, albo API):
```
POST {repo_base}/proposals/{proposal_id}/decision
{"idempotency_key":"…","decision":"approve","reason":"<jedno zdanie: dlaczego ta karta jest prawdziwa>"}
```

**Dowód.**
```sql
SELECT kind, state, count(*) FROM gfm.proposals GROUP BY 1,2;
SELECT count(*) FROM gfm.decisions;
SELECT scope, source, reviewed_by, proposal_id FROM gfm.scopes;
```
Oczekiwane: `proposals ≥ 1`, `decisions ≥ 1`, a po decyzji `scope_map` — stan `applied` i wiersz `gfm.scopes` z `source` innym niż `inferred`.

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

Sprawdź, że karta wróciła z właściwą tożsamością: ścieżka pliku musi odpowiadać **prawdziwemu katalogowi** węzła (dla węzła `docs.runbooks` → `docs/runbooks/.agents/skills/<nazwa>/SKILL.md`, nie `docs.runbooks/…`). Dla węzła `_root` jest to `.agents/skills/<nazwa>/SKILL.md` — potwierdzone w drugiej próbie.

**Nie przesuwaj HEAD między eksportem a `apply`.** Eksport niesie `base_commit` importu, z którego powstała propozycja; `apply` odmawia, gdy HEAD jest inny („rebase the export (or re-export) before applying"). Jeśli jednak musisz, `--no-base-check` wymusza zapis — i wtedy sam odpowiadasz za to, że łatka pasuje.

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

**Druga pułapka: `503`/`snapshot_policy_mismatch`.** `serve` i `worker` hashują `skills/guidefold/scripts/guidefold` przy starcie (`GUIDEFOLD_POLICY_SOURCE`), a builder hashuje ten sam plik przy budowie snapshotu. Rozbieżność znaczy, że CLI publikujący różni się od CLI zapieczonego w obrazie — **nie** jest to problem uwierzytelnienia. Druga próba zmierzyła dokładne lekarstwo i poprzednia wersja tego runbooka podawała je źle:

1. zrestartuj usługi (albo, na produkcji, wydaj obrazy z tego samego commitu, co CLI, którym publikujesz — patrz [release-prep](../reports/deploy/2026-09-15-release-prep.md) §6) i uruchom `guidefold install` ponownie w każdym klonie, żeby zainstalowana kopia CLI się zgadzała;
2. **zmień drzewo.** Sam ponowny import **nie wystarczy**: `gfm.imports` ma `UNIQUE(org_id,repo_id,manifest_digest)`, więc `import --wait` na niezmienionym drzewie zwraca ten sam `import_id`, a `POST {repo_base}/publish` z nowym `idempotency_key` i tym samym `import_id` zwraca istniejący wiersz `failed` z tym samym `job_id` i nie zleca nic nowego. Dopóki manifest jest ten sam, nie ma czego opublikować.

**Trzecia pułapka: publikacja częściowa.** Od kontraktu 1.17.0 import z jednym niesparsowanym plikiem kończy się `partial`, a publikacja jest **`active` z `partial: true`** i niesie wszystkie pozostałe karty. Sprawdzone: 408 plików, `accepted 406 / failed 1 / omitted 1`, snapshot `active` z 83 skillami i jedna pozycja kolejki `import_file_failed`. `import_partial` zostaje wyłącznie wtedy, gdy po odjęciu nieudanych plików nie ma czego publikować. `missing_dependency` to co innego — jest walidacją całej publikacji i **nie** ratuje jej publikacja częściowa (patrz P3).

**Dowód.** `SELECT state, count(*) FROM gfm.publications GROUP BY 1;` → `active ≥ 1`. Dla publikacji częściowej: `SELECT state, partial, n_skills FROM gfm.publications ORDER BY created_at DESC LIMIT 1;` oraz `SELECT reason, state FROM gfm.owner_queue WHERE reason='import_file_failed';`

## 9. Krok 8 — adapter i realna sesja (jeden harness)

To jest krok, który zero-config rozciął, i jedyne miejsce w tym runbooku, gdzie trzeba wykonać coś ręcznie. Druga próba przeszła go dopiero po dwóch obejściach; oba są poniżej i oba są sprawdzone.

W klonie repozytorium, na maszynie **dewelopera z P4**:
```sh
python3 .agents/skills/guidefold/scripts/guidefold install --harness claude
python3 .agents/skills/guidefold/scripts/guidefold login       # kod urządzenia; zatwierdź w konsoli
python3 .agents/skills/guidefold/scripts/guidefold materialize  # OBEJŚCIE 1 — patrz niżej
python3 .agents/skills/guidefold/scripts/guidefold index        # OBEJŚCIE 1
```

**Obejście 1 — `install` w repozytorium bez `guidefold.yaml` nie buduje artefaktu indeksu.** Kończy się linią `materialize/index: skipped (no guidefold.yaml yet)`, więc hook nie ma czego wstrzyknąć. Obie komendy uruchomione ręcznie **działają** na mapie wywnioskowanej (w drugiej próbie `index` zapisał 109 kart i 8305 termów). Uruchom je i sprawdź `guidefold doctor` — wiersz `index-freshness` ma powiedzieć „index artifact is at least as new as HEAD".

**Obejście 2 — bez `guidefold.yaml` nie ma bloku `service:`, więc `find`/`load`/hook chodzą po backendzie lokalnym** i nic nie trafia do ledgera. Ustaw w środowisku sesji:
```sh
export GUIDEFOLD_API=https://guidefold.cloudfloo.io
export GUIDEFOLD_SEARCH_BACKEND=service
export GUIDEFOLD_SEARCH_URL=https://guidefold.cloudfloo.io
export GUIDEFOLD_ORG=cloudfloo GUIDEFOLD_REPO_ID=<repo_id>
unset GUIDEFOLD_TOKEN     # żeby poświadczenia z `guidefold login` wysłały X-Guidefold-Org/Repo
```
`GUIDEFOLD_SEARCH_*` to jedyne źródło konfiguracji, którego hook wolno użyć, więc te same zmienne wystarczają hookowi i `find`.

**`--limit 4`, nie domyślne 8.** Kontrakt 1.1 wyraża `budget.max_cards` w zakresie 0..4, więc `find` z `k > 4` **w ogóle nie otwiera gniazda**: degraduje do backendu lokalnego z `fallback_reason: "config"` i drukuje URN-y, których serwis nie zna. Zmierzone w drugiej próbie: z `--limit 8` telemetria zapisała `backend: local_sparse`, z `--limit 4` — odpowiedź serwisu i URN-y `urn:skill:<repo_id>:…`. Hook używa `k = 3`, więc jego ścieżka jest serwisowa bez żadnego flagowania.
```sh
guidefold find "<zadanie własnymi słowami>" --limit 4
guidefold load <urn>@<card_revision>
```

Potem **prawdziwa sesja Claude Code** w tym katalogu, z zadaniem, które deweloper i tak by wykonał. Hook `SessionStart` wstrzykuje guidance. Na koniec:
```sh
python3 .agents/skills/guidefold/scripts/guidefold telemetry flush
```

**`rejected=1: unknown_event_type` przy `flush` jest oczekiwane, nie awarią.** CLI emituje `telemetry_health.parity_mismatch`, gdy odpowiedź lokalna i serwisowa się różnią, a zamrożony schemat telemetrii tego typu nie zna. Linia `sent=23 accepted=22 duplicate=0 rejected=1` jest poprawnym przebiegiem. Żadne zdarzenie SEARCH/USE nie ginie.

**Trzy defekty pierwszej próby są już na `main`** (PR #179, #180), więc nie powinny wystąpić; jeśli wystąpią, produkcja nie ma tych obrazów:
- `install` kończący się `TypeError: '<' not supported between instances of 'dict' and 'dict'`;
- `load` odpowiadający 403 dla klonu, którego katalog nie nazywa się jak repo id — dziś komunikat nazywa kod HTTP, słowa serwera, `request_id` i krok `next:`, zamiast jednego słowa „(auth)";
- nieudany `load` odrzucany przez ledger (`missing_required_field:cache_source`).

**Uwaga o tożsamości URN.** Lokalne `find`, `materialize` i wygenerowane `AGENTS.md` nadają `publisher` z poświadczeń `guidefold login` (albo, przed zalogowaniem, z remote'u gita), a worker nadaje `publisher = <repo_id>`. Na jednym drzewie potrafią więc wystąpić trzy różne prefiksy URN. **Bierz URN z `guidefold find` na backendzie serwisowym**, nigdy z lokalnej karty.

**Dowód.**
```sql
SELECT count(*) FROM gfm.tokens;
SELECT event_type, count(*) FROM gf.events GROUP BY 1 ORDER BY 1;
```
Oczekiwane po jednej sesji: `tokens ≥ 1` oraz **jednocześnie** `search_requested`/`search_results`, `card_injected` i `skill_load_completed` — PRODUCT-FOCUS wymaga SEARCH **i** LOAD w każdej sesji, nie jednego z nich. W drugiej próbie sesja `claude -p` zapisała `search_requested 1`, `search_results 1`, `card_injected 3`, ale **nie** wywołała `load` — sama wstrzyknięta guidance jej wystarczyła. Jeśli u Ciebie wyjdzie tak samo, zapisz to jako sesję bez LOAD, nie dopisuj LOAD-u z własnego wywołania.

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

**Nie było możliwe do sprawdzenia w żadnej z dwóch prób generalnych**: na maszynie, na której je wykonano, nie ma ani `copilot`, ani `gemini` (`which copilot`, `which gemini` → brak, sprawdzone ponownie 2026-09-15). Nic nie zostało odegrane i nic nie jest tu obiecane.

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
