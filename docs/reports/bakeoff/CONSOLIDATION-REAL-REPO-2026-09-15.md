# Dlaczego konsolidacja abstynowała na tym repozytorium — 2026-09-15

Status: raport pomiarowy + opis naprawy. **Wszystko poniżej jest dowodem R (na ścieżce produktu, lokalnie).** Nie jest dowodem Q ani P: jedna organizacja, jedna maszyna, loopback, generator `deterministic`, bez modelu i bez produkcji. Data: 2026-09-15. Gałąź `fix/consolidation-real-repo` z `feat/llm-org-scope-map` (`348806b`).
Cel: odpowiedzieć liczbami na pytanie z [próby generalnej Pilot Core](../pilot/2026-09-15-pilot-core-rehearsal.md) §4 i §6 — „konsolidacja (jeden wspólny element) nie została zademonstrowana wcale, każde uruchomienie kończyło się `no_shared_procedure`" — a potem wprowadzić najmniejszą zmianę, po której prawdziwy wspólny element **istnieje** na prawdziwych danych.
Wejścia: drzewo tego repozytorium (`.agents/skills/**`, `skills/**`, `docs/**`), stos lokalny `tools/dev/stack.py up --name e3 --pg-port 54361 --api-port 8801 --generator deterministic`, harness `TestRealTreeConsolidation`, reguły dowodów: [eval-evidence-rules](../../../.agents/skills/eval-evidence-rules/SKILL.md), [pilot-evidence](../../../.agents/skills/pilot-evidence/SKILL.md), [definition-of-done](../../../.agents/skills/definition-of-done/SKILL.md).
Zakres zastępowania: brak. Nie zmienia U1–U11, P01–P15 ani żadnego ADR. Uzupełnia [PIVOT-IMPLEMENTATION](../../PIVOT-IMPLEMENTATION.md) P08 o nowszy pomiar i jest uzasadnieniem rewizji [API-CONTRACT](../../API-CONTRACT.md) 1.16.0.

## 1. Werdykt w trzech zdaniach

Abstynencja `no_shared_procedure` była **prawdziwa dla reguły, która ją wypowiadała, i jednocześnie wypowiadana o niewłaściwych dziesięciu skillach**: plan pokazywał generatorowi 10 z 81 skilli w porządku alfabetycznym `skill_id`, a jedyna dosłowna duplikacja w tym drzewie leży w dziewięciu skillach `higgsfield-*`, które nigdy do porównania nie trafiały. Nawet gdyby trafiły, reguła nadal by abstynowała: w całych 81 skillach **najdłuższy przebieg identycznych, uporządkowanych kroków między dowolną parą ma długość 2**, a próg wynosi 3 — i żadne rozluźnienie parsowania kroków tego nie zmienia. Naprawą nie jest obniżenie progu dla pary, tylko dodanie zdania, którego regule brakowało: **te same dwa kroki, dosłownie, w trzech skillach to nie zbieg okoliczności, tylko kopiuj-wklej** — po czym repozytorium wydaje dokładnie jeden, prawdziwy wspólny element.

## 2. Środowisko

| Co | Wartość |
|---|---|
| Host | WSL2, `Linux-6.18.33.2-microsoft-standard-WSL2`, tylko loopback |
| Go / PostgreSQL / Python | `go1.27.1`, `18.6` (klaster `e3`, port 54361), `3.12.3` |
| API | `http://127.0.0.1:8801`, `GUIDEFOLD_AUTH=dev`, generator `deterministic` |
| Drzewo importu | kopia tego checkoutu w `~/.cache/guidefold/e3/tree`, commit `23b08e3d` / `4b3ba171`-import, 578 plików, 366 blobów |
| Wyłączenie | `.guidefoldignore` = `examples/monorepo/` — **celowo**: 25 z 27 skilli fixture Meridian ma ponumerowaną procedurę, więc bez wyłączenia raport mierzyłby fixture, a nie repozytorium (eval-evidence-rules) |

## 3. Diagnoza: liczby na prawdziwym drzewie

Komenda dla §3.1–§3.4 (czysty Python, te same reguły co `internal/review/generator/markdown.go`) i dla §3.5 (`GUIDEFOLD_REAL_TREE=$PWD go test ./internal/review/generator -run RealTree -v`).

### 3.1 Co w ogóle jest w drzewie

| Liczba | Wartość |
|---|---|
| `SKILL.md` w repozytorium | **109** (81 w `.agents/skills/`, 27 w `examples/monorepo/`, 1 w `skills/guidefold/`) |
| Skille zaimportowane (po wyłączeniu fixture) | **81**, wszystkie w jednym scope `_root` (mapa zero-config, [ADR-0050](../../adr/ADR-0050-zero-config-scope-map.md)) |
| Grupy konsolidacji w planie | **1** (`consolidation:_root`), `n_inputs: 10` |

### 3.2 Dwie przesłanki briefu są nieprawdziwe w tym checkoucie

- **`skills/higgsfield-*` nie istnieje.** `skills/` zawiera wyłącznie `guidefold/`; wszystkie dziewięć skilli `higgsfield-*` leży tylko w `.agents/skills/`. Nie ma więc pary „ten sam plik w dwóch miejscach".
- **Zero par bajtowo identycznych ciał.** Po odcięciu frontmattera sha256 ciał wszystkich 109 plików są różne: **0 grup duplikatów**. `security-baseline` istnieje i w `.agents/skills/`, i w `examples/monorepo/` — to duplikat **nazwy**, nie treści (i dokładnie ten, który wywrócił `install` jako D4 w próbie generalnej).
- Wniosek: wariant (i) z briefu (`duplicate_body`, ten sam sha256 w ≥2 scope'ach) nie ma na tym repozytorium **czego** znaleźć. Nie jest zaimplementowany.

### 3.3 Klasa (b): grupowanie nigdy nie pokazuje właściwej pary

`gfm.skills.skill_id` jest tekstem URN (`urn:skill:<publisher>:_root:<nazwa>`), a `skillsByScope` brało `ORDER BY s.scope,s.skill_id` i odcinało na `max_neighbours` (10). Przy jednym scope znaczy to: **dziesięć pierwszych skilli alfabetu**. Przebieg przed naprawą (`TestRealTreeConsolidation`, `main`-owe reguły):

```
skills under .agents/skills: 81
skills with >=3 parsed steps: 4
group presented to consolidation (10 of 81): accessibility-contract, adr-writing, animate,
  animation-vocabulary, api-contract, api-contract-versioning, apple-design,
  audit-release-quality, avoid-ai-writing, backlog-prioritisation
candidates: 0  abstentions: 1
  abstention no_shared_procedure [... te dziesięć ...]:
    no run of 3 identical ordered steps appears in two procedures
```

**71 z 81 skilli nie było oglądanych ani razu**, a wycięte zostało wszystko od `b` wzwyż — w tym cała rodzina `higgsfield-*`. Odpowiedź na pytanie briefu „czy generator w ogóle widzi te pary": **nie widział ich nigdy**.

### 3.4 Klasa (c): kroki nie mają kształtu, którego szuka parser, i (a) reguła i tak by abstynowała

`RoleOf` rozpoznaje sekcję kroków po tekście nagłówka. Na 81 skillach:

| Lista słów | Skille z nagłówkiem roli „kroki" | Skille z ≥3 krokami |
|---|---|---|
| przed zmianą (`steps`, `procedure`, `runbook`, …) | **4** | **4** |
| po dodaniu `step ` i `bootstrap` | **16** | **13** |

Prawdziwa procedura tego repozytorium nosi nagłówek `## Step 0 — Bootstrap` (`higgsfield-generate`, `-product-photoshoot`, `-soul-id`) albo `## Bootstrap` (sześć pozostałych `higgsfield-*`) — `"steps"` nie pasuje do `"step 0 — bootstrap"`.

To jednak **nie wystarcza**, i to jest najważniejsza liczba w raporcie. Porównanie wszystkich par wśród wszystkich 81 skilli, przy trzech coraz luźniejszych sposobach czytania kroków:

| Sposób czytania kroków | Procedury | Pary z przebiegiem ≥3 | Najdłuższy przebieg w drzewie |
|---|---|---|---|
| tylko sekcje o roli „kroki", lista bazowa | 4 | **0** | 0 |
| tylko sekcje o roli „kroki", lista rozszerzona | 13 | **0** | 2 |
| **każda** ponumerowana pozycja w pliku, bez względu na nagłówek | 38 | **0** | 2 |
| **każda** pozycja listy (`1.`, `-`, `*`) w pliku | 66 | **0** | 2 |

Czyli: `no_shared_procedure` przy progu `minSharedSteps = 3` jest **trafnym werdyktem** dla tego drzewa i pozostałby trafny po dowolnym rozluźnieniu parsowania. Wariant (iii) z briefu sam z siebie nie produkuje niczego; wariant (ii) sam z siebie też nie (porównanie all-pairs, powyżej, daje zero).

Jedyny przebieg dwóch kroków niesiony przez więcej niż dwa skille jest w całym drzewie **dokładnie jeden**:

```
3 skille: higgsfield-generate, higgsfield-product-photoshoot, higgsfield-soul-id
  "if higgsfield path install"
  "if higgsfield account status fails session expired authenticated ask user run higgsfield auth login"
```

Na poziomie surowych linii ta sama rodzina dzieli **8 identycznych, kolejnych linii** (`## Step 0 — Bootstrap` … `curl -fsSL …/install.sh | sh` … krok 2), a 23 pary skilli dzielą przebieg ≥3 identycznych linii.

### 3.5 Dlaczego nie „duplikat bloku"

Uogólnienie na „identyczny blok ≥N linii" łapałoby to samo, ale głośniej: w tych 23 parach są m.in. `animate` / `find-animation-opportunities` z czterema identycznymi liniami, które są **wierszami tabeli czasów trwania**, a nie procedurą. Dopasowanie na poziomie kroków łapie ten sam duplikat i nie proponuje właścicielowi wspólnego skilla zbudowanego z tabeli. Blok nie jest zaimplementowany.

## 4. Naprawa

Trzy zmiany, z których **żadna nie działa bez pozostałych dwóch** (§3.3, §3.4 pokazują, że każda z osobna daje zero). Ranking nietknięty; `family`/relacje nadal addytywne; ścieżka deterministyczna nadal bez modelu.

1. **Wybór sąsiadów po rodzinie nazw** (`internal/review/generator/neighbours.go`, `internal/review/plan.go`). `max_neighbours` bez zmian — scope nadal wnosi najwyżej 10 skilli, grupa najwyżej `max_neighbours²` — ale gdy scope ma ich więcej, pierwszeństwo ma największa rodzina nazw (pierwszy człon nazwy przed `-`), a nie alfabet. Kolejność jest totalna i zależy tylko od identyfikatorów, więc dwa plany nad tym samym katalogiem są identyczne. Dotyczy **wyłącznie** konsolidacji: enrichment ogląda każdy skill osobno, więc zostaje przy dotychczasowym porządku.
2. **Dwa kształty nagłówka więcej** (`markdown.go`): `step ` i `bootstrap`. Tylko te dwa, bo tylko te dwa zostały zmierzone. Promień rażenia na ekstrakcji zmierzony osobno: na 177 dokumentach `docs/**` liczba dokumentów, z których deterministyczna ekstrakcja **wyprodukowałaby** kandydata, rośnie z **1 do 2** — jedynym nowym jest `docs/CONVENTIONS.md` („Reconciling a partial or drifted bootstrap (`init`)", 6 kroków), czyli prawdziwa procedura. Szersza lista (`workflow`, `process`, `checklist`, …) nie jest dodana, bo nie jest zmierzona.
3. **Próg źródeł zamiast niższego progu kroków** (`deterministic.go`). `minSharedSteps = 3` zostaje nietknięte: para nadal potrzebuje trzech kroków. Dochodzi `minRepeatedSteps = 2` z `minRepeatedSources = 3` — ten sam przebieg dwóch kroków, dosłownie i w tej samej kolejności, w trzech lub więcej skillach grupy liczy się jako wspólny element. Procedura dwukrokowa wchodzi z tego powodu do porównania (wcześniej `< minSharedSteps` wypadała z grupy — to dlatego `higgsfield-product-photoshoot` był niewidoczny nawet po zmianie 1 i 2).
4. **Źródłem jest każdy skill niosący przebieg**, nie tylko para, która go ujawniła. Wspólny element wymieniający dwa z trzech egzemplarzy duplikatu zostawiałby trzeci na miejscu po zatwierdzeniu. Skill, który niesie przebieg, ale gdzieś się z nim nie zgadza (wersja, warunek, sprzeczność) **nie** jest źródłem — dostaje własny powód w `abstentions[]`.
5. **Kandydat niesie to, na co wskazuje jego `SourceRef`.** Krok jest przepisywany z linii, które zajmuje, a nie z jednolinijkowego tekstu z parsera: `Items()` trzyma blok kodu w zakresie linii kroku, ale nie w jego tekście, więc bez tego wspólny skill mówiłby „install it:" i nigdy nie powiedział jak.

Recepta idzie z `det-1` na **`det-2`** — klucz cache niesie wersję recepty, więc bez podbicia repozytorium, które już raz przeliczyło konsolidację nad niezmienionymi plikami, odpowiedziałoby z cache i nigdy nie zobaczyło nowego wspólnego elementu. To jedyny powód, dla którego ta zmiana ma wpis w kontrakcie ([API-CONTRACT](../../API-CONTRACT.md) 1.16.0): **żadnej trasy, DTO, kolumny, kodu błędu ani nowej wartości w zamkniętej liście powodów abstynencji nie dodano**; `python3 tools/contract/check_api_contract.py` → `OK: no contract drift`.

## 5. Przebieg po naprawie na prawdziwym drzewie

### 5.1 Harness (`GUIDEFOLD_REAL_TREE=$PWD go test ./internal/review/generator -run RealTree -v`)

```
skills under .agents/skills: 81
skills with >=3 parsed steps: 8
group presented to consolidation (10 of 81): cloudfloo-cinematic-landing, higgsfield-brandkit,
  higgsfield-cinematic-assets, higgsfield-generate, higgsfield-marketplace-cards,
  higgsfield-product-photoshoot, higgsfield-soul-id, higgsfield-video-explainer,
  higgsfield-websites, higgsfield-youtube-thumbnail
candidates: 1  abstentions: 2
  already_consolidated [higgsfield-generate higgsfield-soul-id]
  already_consolidated [higgsfield-product-photoshoot higgsfield-soul-id]
```

### 5.2 Ścieżka produktu (stos `e3`, org `e3org2`, import `2529eb96-e8d1-496b-8370-a00b3b1dc61b`, snapshot 578 plików / 366 blobów, `POST …/proposals:generate {"kinds":["consolidation"],"profile":"one_shot"}`)

`GET …/plan?kinds=consolidation&profile=one_shot` → 200, `generator.version: "det-2"`, jedna grupa `consolidation:_root`, `n_inputs: 10` (te same dziesięć co wyżej). Propozycja `797de4ab-03b4-43b9-8ad2-f1cec4ce499e`, `kind: consolidation`, `state: draft`, `scope: _root`, ścieżka `.agents/skills/shared-if-higgsfield-is-not-on-path-install-it/SKILL.md`, **trzy źródła z sha256**:

```
.agents/skills/higgsfield-generate/SKILL.md           7c3c48de04a4fac6…
.agents/skills/higgsfield-product-photoshoot/SKILL.md 139c38f3b8a33a4e…
.agents/skills/higgsfield-soul-id/SKILL.md            1ce57e956e412a4d…
```

sześć relacji: `derived_from` w dół do każdego z trzech, `refines` w górę z każdego z trzech. Ciało kandydata:

```markdown
---
name: shared-if-higgsfield-is-not-on-path-install-it
description: "[_root] Shared: If `higgsfield` is not on `$PATH`, install it:"
metadata:
  knowledge_layer: task
  layer: atomic
  owner: unknown
  scope: _root
---

# Shared: If `higgsfield` is not on `$PATH`, install it:

## Purpose

The 2 steps urn:skill:guidefold:_root:higgsfield-generate,
urn:skill:guidefold:_root:higgsfield-product-photoshoot,
urn:skill:guidefold:_root:higgsfield-soul-id perform identically.

## Steps

1. If `higgsfield` is not on `$PATH`, install it:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh
   ```
2. If `higgsfield account status` fails with `Session expired` / `Not authenticated`, ask the
   user to run `higgsfield auth login` (interactive) and wait for confirmation.

## Derived from

- urn:skill:guidefold:_root:higgsfield-generate
- urn:skill:guidefold:_root:higgsfield-product-photoshoot
- urn:skill:guidefold:_root:higgsfield-soul-id
```

## 6. Czego ten przebieg **nie** dowodzi

- **To jeden wspólny element, nie zdolność wykrywania duplikatów.** `n=1` na jednym repozytorium; nic tu nie mówi, ile duplikatów ma repozytorium klienta ani jaki odsetek z nich reguła znajduje. To dowód R, nie Q i nie P.
- **Nikt tej propozycji nie zatwierdził.** Jest `draft`. Czy „zbootstrapuj CLI" ma być osobnym skillem, a nie sekcją powtarzaną w dziewięciu, jest decyzją właściciela rodziny `higgsfield-*` — dokładnie dlatego kończy się propozycją, a nie zapisem.
- **`owner: unknown`**, bo zero-config nie zna właściciela `_root` tego drzewa. Podniesienia scope tu nie było (wszystkie źródła są w `_root`), więc `scope_widening_not_approved` nie było sprawdzane na prawdziwych danych tym przebiegiem.
- **`guidefold extract --all --wait` nadal wypisuje `groups: 0, proposals: 0`** na tym repozytorium (org `e3cli`, import `4b3ba171`), mimo że `GET …/plan` dla tego samego importu pokazuje trzy grupy (`extraction` 20, `enrichment` 10, `consolidation` 10), a `POST …/proposals:generate` natychmiast daje wspólny element. Mechanizm: `cmd_extract` woła `plan`/`proposals:generate` **zanim** import zostanie sparsowany (`_run_import(..., finish=False)`), więc `gfm.skills` jest jeszcze puste. To defekt D7 z próby generalnej, zmierzony tu dokładniej; **nie jest naprawiony w tej zmianie** i jest dziś jedyną rzeczą, która dzieli właściciela od zobaczenia tego wspólnego elementu komendą z runbooka ACT-01.
- Dziewięć skilli `higgsfield-*` niesie tę samą procedurę **w intencji**, ale tylko trzy niosą ją dosłownie; sześć pozostałych ma warianty (`## Bootstrap` z innymi krokami). Reguła deterministyczna ich nie łączy i nie powinna — to jest praca dla modelu, nie dla `det-2`.

## 7. Weryfikacja

| Co | Komenda | Wynik |
|---|---|---|
| Kontrakt | `python3 tools/contract/check_api_contract.py` | `OK: no contract drift` (20 INFO) |
| Go | `go vet -C services/search ./...` | czysto |
| Go | `go test -C services/search -race -count=1 ./...` | wszystkie pakiety `ok` |
| Python | `rtk proxy python3 -m pytest tests --ignore=tests/acceptance -q` | exit 0, 1424 wybrane, 3 pominięte |
| Drzewo prawdziwe | `GUIDEFOLD_REAL_TREE=$PWD go test ./internal/review/generator -run RealTree -v` | §5.1 |
| Ścieżka produktu | `tools/dev/stack.py up --name e3 --pg-port 54361 --api-port 8801 --generator deterministic`, potem `down --name e3 --stop-pg` | §5.2, stos zatrzymany |

Testy na zaplantowanym drzewie (`t.TempDir()`, nie fixture): `TestTwoStepsInTwoSkillsAreACoincidence` (dwa skille → `no_shared_procedure`), `TestTwoStepsInThreeSkillsAreASharedElement` (trzy skille → jeden element, trzy źródła, komenda w ciele), `TestAThirdSkillThatContradictsIsNotASource`, `TestRoleOfRecognisesTheHeadingsRealSkillsUse`, `TestNeighbourOrderPrefersTheLargestNameFamily`, `TestPickNeighboursKeepsTheLargestFamilyNotTheAlphabet`. `TestRealTreeConsolidation` jest pomiarem, nie regresją: bez `GUIDEFOLD_REAL_TREE` pomija się, żeby CI nie padało od czyjejś edycji `SKILL.md`.
