---
name: skill-authoring-conventions
description: Rules for writing and validating SKILL.md files in Guidefold contexts (consumer skills under guidefold.yaml nodes, the distributable bootstrap, and this repo's own project skills). Use when creating, editing or reviewing any SKILL.md. Not for hosted UI copy.
---

# Konwencje autorskie SKILL.md

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy SKILL.md przechodzi `guidefold validate` i trafia do właściwego z trzech miejsc.
Źródło: [CONVENTIONS §2–§5, §7–§8, §12–§13](../../../docs/CONVENTIONS.md), [ADR-0010](../../../docs/adr/ADR-0010-flat-string-metadata.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, który rodzaj skilla edytujesz

| Rodzaj | Miejsce | Zasada |
|---|---|---|
| Skill fixture | `examples/monorepo/**/.agents/skills/` | Dane testowe Meridian. Nie zmieniaj ich, aby zapisać instrukcje tego projektu; zmiana wymaga zadania na fixture i przegląd goldenów w `tests/golden/`. |
| Bootstrap dystrybuowany | `skills/guidefold/SKILL.md` | Trafia do repo klienta i rejestru. Bez planów wewnętrznych, bez odwołań do `docs/` tego repo, bez ścieżek lokalnych. |
| Skill projektu | `.agents/skills/<name>/SKILL.md` | Instrukcja dla agentów w tym repo. Format: frontmatter `name`/`description`, nagłówek Status/Cel/Źródło/Indeks/Zakres zastępowania, ≤70 linii, linki `../../../`. |

## Pisz frontmatter zgodnie z §3–§4

- `name` w kebab-case, 3–40 znaków, równy nazwie katalogu. Skill konsumencki leży w `<node-path>/.agents/skills/<name>/`; nigdy bezpośrednio pod `.claude/`, `.github/` czy `.gemini/` (§2).
- `description` konsumencka zaczyna się od `[<node/path>]`, root od `[<publisher>]` z `guidefold.yaml`; nigdy od nazwy organizacji wpisanej ręcznie. Maks. 1024 znaki i musi mówić, kiedy użyć.
- URN `urn:skill:<publisher>:<node>:<name>` jest pochodny; nie wpisuj go do frontmattera ręcznie. `metadata.scope` równa się węzłowi z katalogu, `metadata.owner` ownerowi węzła.
- Wszystkie wartości `metadata` są skalarnymi stringami (ADR-0010): listy jako string po przecinku, daty w cudzysłowie, booleany `"true"`/`"false"`.
- `requires` tylko URN-y istniejące w drzewie, bez cykli; `references` ≤10 wpisów; `refines` nigdy do głębszego węzła (§8).
- Body ≤500 linii / ≤5k słów; dłuższy materiał do `references/*.md`. Bez sekretów i ścieżek absolutnych.

## Utrzymuj body i cykl życia

Zalecany szkielet (§5): `When to use / when NOT to use`, `Steps`, `Conventions specific to this scope`, `Verify`, `See also (URNs)`. Para nagłówków when/do-not jest tym, co `validate --suggest` (§13) czyta, proponując `metadata.triggers`; sugestia jest do wklejenia, nie stosuje się sama.
Akapit prawdziwy dla węzła nadrzędnego należy do skilla nadrzędnego i jest linkowany przez `requires`, nie kopiowany (§6). Wycofanie: `metadata.status: deprecated` plus `metadata.replaced_by: <urn>` (§7).
Raport `skill-authoring-report` w PR (§12) informuje o kolizjach z sąsiadami; nigdy nie blokuje builda i nie zastępuje decyzji ownera.

## Sprawdź przed zakończeniem

1. `cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold validate` przechodzi (dla skilli konsumenckich i fixture).
2. `name` == katalog; `description` zaczyna się od właściwego prefiksu.
3. Każda wartość `metadata` jest stringiem; `requires`/`references` istnieją.
4. Skill projektu: nagłówek Status/Cel/Źródło/Indeks/Zakres, ≤70 linii, wpis w [AGENTS.md](../../../AGENTS.md).
5. Bootstrap: brak odwołań do `docs/` i planów wewnętrznych.
