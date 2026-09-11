# Pilot docs — index

Status: aktywny indeks katalogu. Data: 2026-09-07.
Cel: jedno miejsce, które wskazuje protokół pilota, arkusze i narzędzie raportujące, zamiast
rozpraszać odnośniki po PRD. Wejścia: [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §13,
[PIVOT-BACKLOG](../PIVOT-BACKLOG.md) P15, [pilot-evidence](../../.agents/skills/pilot-evidence/SKILL.md).
Zakres zastępowania: brak; ten plik nie zmienia treści dokumentów, do których linkuje.

## Pliki

| Plik | Rola |
|---|---|
| [E6.7-PROTOCOL](E6.7-PROTOCOL.md) | Zamrożony pre-registered protokół pilota E6.7 (H1–H3, warunki A–D, stop rules). Zmienia się tylko przez datowany addendum po zamrożeniu (§11). |
| [task-bank.template.yaml](task-bank.template.yaml) | Schemat zadań pilota i `frozen.task_bank_sha256`. |
| [scoring-sheet.template.csv](scoring-sheet.template.csv) | Schemat arkusza ocen zadań (11 kolumn), z nagłówkiem `protocol_sha256`. |
| [QUALITY-GATE-EVALUATOR.md](QUALITY-GATE-EVALUATOR.md) | Mechaniczna bramka E2 + task success; `unknown` i brak dowodu kończą się `inconclusive`. |
| `tools/pilot/verify_annotation_packet.py` | Waliduje ślepy pakiet dwóch recenzentów przed i po etykietowaniu; sprawdza hashe, zakresy linii i zgodność, bez rozstrzygania sporów. |
| `tools/pilot/run_agent_tasks.py` | Uruchamia Pi w izolowanym workspace z ukrytym verifierem, zapisuje task success, SEARCH/USE/ASK, token usage i czas oraz rozdziela porażkę zadania od błędu harnessu. |
| `tools/pilot/bridge.py` | Referencyjny most Pi → Go SEARCH/USE: czyta zamrożony kontekst, obsługuje flat/top-down/bottom-up, redaguje trace i nie dostarcza ciała po `ASK`. |
| [PI-SMOKE-2026-09-10](PI-SMOKE-2026-09-10.md) | Reprodukowalny smoke prawdziwego Pi z ukrytym verifierem; potwierdza plumbing, nie jakość retrieval. |
| [HIERARCHY-SMOKE-2026-09-10](HIERARCHY-SMOKE-2026-09-10.md) | Replay scoped flat/top-down/bottom-up na 26-kartowym snapshotcie Meridian; neutralny wynik kierunku traversalu. |
| [PIVOT-RUBRIC](PIVOT-RUBRIC.md) | Rubryka U11 z etykietami R/Q/P, progi go/no-go i to, czego syntetyczny run nie dowodzi. |

## Narzędzia

`tools/pilot/analyze.py` liczy sparowaną analizę E6.7 dokładnie wg zamrożonego protokołu (4
stałe warunki, `protocol_sha256` wymagany w nagłówku arkusza, zakaz powtórki i post-hoc zmian —
§6 E6.7-PROTOCOL.md).

`tools/pilot/pivot_report.py` liczy szerszy raport U11 z [PIVOT-RUBRIC](PIVOT-RUBRIC.md): usage
export (`/usage/export`, CSV lub JSON), scoring sheet z generycznymi "ramionami" (np. `with_skills`
vs `without`, albo dwa harnessy) i opcjonalny koszt per import. Nie wymaga zamrożonego
`protocol_sha256` — służy porównaniom poza sztywnym schematem E6.7. `--synthetic` stemplu każdą
sekcję jako dane niebędące dowodem z pilota. Testy: `tests/test_pivot_report.py`.

`tools/pilot/run_verifiers.py` uruchamia evaluator-only hidden verifiers w izolowanych katalogach,
bez shella, z jawnym timeoutem i statusem `unknown` dla błędów harnessu. Jego JSONL jest wejściem
do `tools/pilot/quality_gate.py`.

`tools/pilot/bridge.py` jest jedynym mostem używanym przez runner Pi. Plik `nodes.json` musi
zawierać co najmniej `repo_id` oraz opcjonalnie `revision`, `cwd` i `scopes`; zapytanie pozostaje
niezmienione. Strategie hierarchiczne wykonują SEARCH per scope w ustalonej kolejności i łączą
unikalne karty po wyniku. `proof_gated` przełącza USE na kontrakt 1.2; odpowiedź `ASK` ma pusty
body. Trace zawiera wyłącznie endpoint, status, czas, identyfikatory i akcję, bez promptu, ciała
skilla ani tokenu.
