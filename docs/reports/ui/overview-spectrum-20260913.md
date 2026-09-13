# Overview: migracja na Spectrum UI Charts (SC-07)

Status: wdrożone w worktree `feat/overview-spectrum-charts`, 2026-09-13; niezacommitowane, bez przeglądu w przeglądarce.
Źródło wymagań: [UI §7](../../ui/UI.md#7-obowiązkowa-migracja-spectrum-charts), [spectrum-charts-migration](../../../.agents/skills/spectrum-charts-migration/SKILL.md), audyt PRIO 1.3 ([2026-09-12](../product/2026-09-12-assumptions-vs-implementation-audit.md)).
Zakres: `ui/src/routes/HomeRoute.tsx` i nowy `ui/src/routes/overviewCharts.tsx`. Pliki itemów w `ui/src/components/spectrumui/charts` pozostały bajt w bajt (hashe w `ui/qa/spectrum-registry.json` bez zmian).

## Inwentarz 2026-09-13

| Trasa/plik | Stary renderer | Item Spectrum | Kontrakt danych | Status | Dowód (Vitest, `HomeRoute.test.tsx`) |
|---|---|---|---|---|---|
| Overview → „Key numbers”, 4 karty | shadcn-space `statistics-01` (`StatisticsMain`/`StatisticsSecondary`) | `StatCards` (po jednej karcie na element listy) | `displayValue` = sformatowana liczba z API albo `Unknown`; `caption` bez zmian; bez `series`/`previous`, więc item nie liczy własnej delty. Plakietka trendu (`delta`/`helpedShareDelta`, „No previous window”) obok karty, poza jej `<dl>` | verified (jsdom) | „shows the four key numbers…”, „1.3.0: trend badges…”, „no previous window is…”, „…reads "new"”, „…reads "no change"”, „no telemetry is one compact state…” |
| Overview → „Delivery funnel” | shadcn-space `chart-01` (Recharts przez `ui/chart.tsx`) | `BarChart`, `layout="horizontal"` | `funnelSteps(usage)`: `{category, first: value, second: null}`; lista „Delivery funnel counts” z dokładną liczbą i notą (lower bound, unknown) | verified (jsdom) | „Spectrum funnel: a bar chart plus every step as its exact count in text” |
| Overview → „Feedback” | shadcn-space `chart-02` | `DonutPieChart` | `usage.totals.feedback`; wykres tylko gdy `n > 0` i suma werdyktów = `n`; plasterki > 0, lista wszystkich pięciu werdyktów (znane zero widoczne) | verified (jsdom) | „Spectrum feedback donut: n=0 is the no-assessment state…”, „…verdict counts are the API counts, a known zero included” |
| Overview → Library → „Knowledge layers” | shadcn-space `chart-02` | `DonutPieChart` | `map/layers`, wiersze `count > 0`; lista „Skills per knowledge layer” i suma | verified (jsdom) | „Spectrum layers donut: values match the map/layers counts”, „a layer read with no positive count draws no donut” |
| Overview → Library → „Largest scopes/repositories” | inline `<svg><rect>` | `BarChart`, horizontal | `skills/facets` (`scope` z repo, `repo` bez), `topFacetValues`; wykres rysuje słupki, obok dostępna lista linków z liczbami | verified (jsdom) | „Spectrum bars for the largest repositories and for proposals by state…”, „ADR-0047: no repository is the whole organisation…” |
| Overview → Pipeline → „Proposals by state” | shadcn `Progress` | `BarChart`, horizontal | `proposalsByState`; wykres tylko gdy suma > 0; lista linków ze stanem i liczbą | verified (jsdom) | „Spectrum bars for the largest repositories and for proposals by state…”, „no proposal at all draws no proposals chart…” |

Poza HomeRoute nie było innych importów `shadcn-space/blocks/chart-*` ani `statistics-*`. Bloki `chart-01`, `chart-02`, `statistics-01` usunięte razem z wpisami w `ui/qa/spectrum-registry.json`; `table-01` i `empty-state-01` to nie wykresy i zostają.

## Adaptacje bez forka

- `BarChart` wymaga dwóch serii. Druga ma wartość `null`: Recharts nie rysuje dla niej prostokąta, a domyślne `filterNull` tooltipa ją pomija. `0` dałoby fałszywą obserwację w tooltipie.
- `DonutPieChart` nie ma etykiety środka; łączna liczba przeszła do opisu karty i `aria-label` figury.
- Wykresy ładują się leniwie (`overviewCharts.tsx`), więc Recharts nie wchodzi do pierwszego chunku Overview.
- Wykres Recharts siedzi we wspólnym, leniwym chunku `PieChart-*.js` (build 2026-09-13: 363,00 kB / 102,83 kB gzip). Nie ma go w `index.html`; statycznie importują go tylko `ReviewRoutes` (Usage, tak samo na `main` 141ae36) i leniwy `overviewCharts`. Rozmiaru sprzed zmiany nie zmierzono.

## Wyjątki SC-02

- **SC-02-OV-1, plakietka trendu KPI:** tekst trendu renderuje shadcn `Badge` obok karty `StatCards`, nie sam item. `StatCardData` nie ma pola na gotową etykietę, a jego własna delta `((headline-base)/base)*100` wymyśliłaby procent tam, gdzie kontrakt ma „+7 pp”, „new”, „no change” albo „No previous window”. Liczba w karcie to item Spectrum. Dalsza decyzja: pole etykiety trendu w upstream albo przegląd adaptacji w rejestrze.

## Recent activity

Wpis audytu, którego `actor` = `user:<me.user.id>` (format `Principal.ID` w `services/search/internal/mgmt/principal.go`), pokazuje „You” z pseudonimem w `title`; inni aktorzy, `worker` i `system` bez zmian. Test: „Recent activity says "You" for the reader's own pseudonym…”.

## Czego nie sprawdzono

`ui/qa/contracts.json` różni się tylko polem `capturedAt`: checker zapisuje je przy każdym uruchomieniu.

Brak renderu w przeglądarce (390 px/desktop), axe i reduced-motion w Playwright; jsdom nie mierzy układu, więc status „verified” dotyczy liczb, stanów i struktury, nie wyglądu.
