---
name: react-component-rules
description: Rules for the Guidefold hosted UI in ui/ (React 19, Vite, CSS Modules): tokens.css as the only value source, the 14-component library, route/data boundaries, fetch and decoding contracts, gallery and test commands. Use when adding or changing anything under ui/. Not for the frozen prototypes.
---

# Zasady komponentów React w ui/

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: ui/ rośnie bez sprawl komponentów, bez wartości poza tokenami i bez mieszania domeny z siecią i DOM.
Źródło: [UI §4–§5](../../../docs/ui/UI.md), [07-frontend](../../../docs/ui/pipeline/07-frontend.md), [08-components](../../../docs/ui/pipeline/08-components.md), [ui/README](../../../ui/README.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Trzymaj granice warstw

| Katalog | Może importować | Nie może |
|---|---|---|
| `ui/src/domain/` (diff, skill, typy) | nic z ui/ poza typami | `data/`, `routes/`, React, DOM, fixture |
| `ui/src/components/` (14 katalogów) | `tokens/`, `domain/` typy | fixture, adaptery, fetch; komponent nie pobiera danych, nie autoryzuje, nie udaje publikacji |
| `ui/src/data/`, `data.ts` | `domain/`, kontrakt adaptera | komponenty; fixture i API to osobne adaptery jednego kontraktu, wstrzykiwane w `main.tsx` |
| `ui/src/routes/` | wszystko powyżej | drugi wariant komponentu „na miejscu”; formularze, lifecycle, eksport, sesja zostają tu |

`Shared.tsx` tylko reeksportuje. Galeria `/__components` jest narzędziem developerskim poza nawigacją produktu; jej baseline nie importuje `ui/`.

## Utrzymuj bibliotekę 14 komponentów

ActionButton, BrandMark, Panel, StateBadge, RouteState, Tabs, ProvenanceTrail, ScopeTree, DataTable, SkillDiff, MetricRow, Urn, SkillContent, Field. Każdy katalog: `index.tsx`, nazwany `*.module.css`, `*.test.tsx`, `*.stories.tsx`, kontrakt a11y i obsługa stanów z tabeli w 08.
- Piętnasty komponent lub drugi wariant wymaga zadania U4 i pisemnego powodu w opisie zmiany; bez GateList, StageTrace, PromotionRoute, CommandPalette.
- `ui/src/tokens/tokens.css` jest jedynym miejscem wartości hex i rozmiarów (103 tokeny); moduły używają `var()`. Nowy token ma wpis „dlaczego” w [06-ux-ui](../../../docs/ui/pipeline/06-ux-ui.md). Bez biblioteki komponentów (MUI, shadcn, Chakra).
- `SkillContent` renderuje semantyczny Markdown przez react-markdown bez raw HTML i zdalnych obrazów; dokładny surowy plik jest osobnym odczytem.
- Kolor nigdy nie jest jedynym nośnikiem stanu; `RouteState` obsługuje empty/loading/partial/error/degraded/restricted, restricted ma pierwszeństwo.

## Pisz dane i nawigację według 07

- URL koduje stan nawigacji (filtry, oś Map, zakładka, wybór); nieznana wartość filtra daje jawny błąd, nie cichy powrót do All. URL nie nadaje uprawnień.
- Fetch w jednej warstwie: `AbortController`, numer aktywnego żądania odrzuca spóźnione odpowiedzi, klucz cache obejmuje operację, ID zasobu, rewizję, snapshot i znormalizowane filtry. GET maks. dwa ponowienia z backoff.
- Dekodowanie payloadu na granicy (typy z OpenAPI + dekoder runtime); błąd dekodowania obsługuje granica trasy, nie komponent.
- Mutacje: idempotency key + expected revision; 409 wymaga ponownego review; bez optymistycznego `published`.
- Prywatne body, feedback i propozycje nie trafiają do localStorage/sessionStorage/service workera; `guidefold-ui-meridian-v1` jest tylko dla publicznego fixture.

## Sprawdź przed zakończeniem

1. `cd ui && pnpm build && pnpm test && pnpm test:contracts` zielone; `pnpm test:e2e` (po `pnpm exec playwright install chromium`).
2. Przy zmianie wyglądu: `pnpm dev`, potem `pnpm test:flow` i `pnpm test:visual`; baseline nie jest regenerowany, aby zaakceptować zmianę.
3. `grep -rn '#[0-9a-fA-F]\{3,6\}' ui/src --include=*.css --include=*.tsx | grep -v tokens/tokens.css` zwraca nic.
4. `ls ui/src/components | wc -l` daje 14 albo zmiana ma pisemny powód i aktualizację UI §4 i 08.
5. `domain/` i `components/` nie importują `data/meridian` ani fixture JSON (`pnpm test:contracts` to sprawdza).
