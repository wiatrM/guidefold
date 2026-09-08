---
name: accessibility-contract
description: Accessibility contract for the Guidefold hosted UI: keyboard-only owner flow, visible focus, roles and aria, 44 px touch targets, measured contrast on dark graphite, colour never alone, axe in CI. Use when building or reviewing any screen, component or interaction in ui/. Not a completed audit.
---

# Kontrakt dostępności

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy widok U4 da się wykonać wyłącznie klawiaturą i przeczytać technologią asystującą, a dowód pochodzi z testu, nie z planu.
Źródło: [UX §3–§4](../../../docs/ui/UX.md), [08-components](../../../docs/ui/pipeline/08-components.md), [07 §Testy](../../../docs/ui/pipeline/07-frontend.md), [design-qa prototypu](../../../prototypes/industrial-surveyor/design-qa.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Spełnij wymagania UX §4

| Obszar | Wymaganie |
|---|---|
| Klawiatura | Natywne linki, przyciski, radio, select i disclosure; Tab/Shift+Tab i standardowe aktywacje. Cała ścieżka login → import → lista → review → eksport działa bez myszy (U4 AC4). Bez niezamówionej palety i skrótów j/k. |
| Focus | Widoczny ring 2 px z offsetem 3 px; skip to content prowadzi do `main`; po zmianie etapu decyzji focus trafia do nowego wyniku. |
| Kontrast | Tekst ≥4,5:1, granice kontrolek i wskaźniki ≥3:1 na graphite; każda konkretna para barw wymaga pomiaru, nie deklaracji. |
| Kolor | Teal/orange/red zawsze z etykietą tekstową: stan, rodzaj relacji, Added/Removed w diffie. Red oznacza wyłącznie błąd; Rejected jest orange. |
| Formularze | `Field` łączy label/id, hint/error przez `aria-describedby`; błąd ustawia `aria-invalid` i alert. |
| Tabele | `caption`, `th scope=col`; nazwany, focusowalny region przewijania, strzałki przewijają szeroką tabelę. |
| Map | Tekstowe drzewo (`details`/`summary`) i lista relacji; nie deklarujemy sterowania grafem strzałkami, którego nie ma. |
| Ikony | Phosphor regular; dekoracyjne `aria-hidden`, samodzielna kontrolka ikony ma nazwę. |
| Dotyk | Cele ≥44 px na mobile (390 px), bez utraty danych za trybem „read-only mobile”. |
| Ruch | Ruch tylko po zmianie stanu; reduced motion wyłącza przejścia; loading bez pulsowania i shimmeru. |

## Używaj ról z kontraktów komponentów (08)

- `RouteState`: `aria-live="polite"`, loading z `aria-busy` i szkieletem ukrytym przed AT.
- `Tabs`: `nav` z nazwą i `aria-current="page"`, zwykłe linki; bez pozornego `tablist`.
- `Urn`: nazwany button kopiowania, `role="status"` po sukcesie i błędzie; brak fałszywego sukcesu clipboard.
- `Panel`: `section` nazwana unikalnym `h2`. Modal (jeśli kiedyś potrzebny): `aria-modal` i pułapka focusu jak w design-qa prototypu.
- `ActionButton`: natywny button (`type="button"`) lub link; disabled link bez `href` i poza Tab.

## Dostarcz dowód z testu

Axe w CI i Playwright dla 7 tras i galerii w szerokościach 1280/820/390 (`ui/e2e/accessibility.spec.ts`), macierz 42 stanów (`ui/e2e/states.spec.ts`), owner flow wyłącznie klawiaturą (`ui/e2e/owner-keyboard.spec.ts`). Axe uzupełnia, nie zastępuje ręcznego sprawdzenia focusu i klawiatury; retry testu nie zamienia flaky w zielone.

## Sprawdź przed zakończeniem

1. `cd ui && pnpm test:e2e` przechodzi, w tym accessibility i states, po `pnpm exec playwright install chromium`.
2. Nowa akcja jest osiągalna Tab/Enter/Space i ma widoczny focus; sprawdzone ręcznie w `pnpm dev`.
3. Nowy kolor stanu ma etykietę tekstową i zmierzony kontrast zapisany w opisie zmiany.
4. Nowa kontrolka na 390 px ma cel ≥44 px i nie powoduje poziomego przewijania.
5. Nic nie jest oznaczone jako zaliczone na podstawie planu (UX §7).
