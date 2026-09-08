---
name: guidefold-ui-workflow
description: Design, implement and verify Guidefold hosted U4 screens using the reviewed UI pipeline, source prototype and Meridian fixture. Use for Guidefold IA, UX, visual system, React components and UI QA; not for unrelated frontend work.
---

# Workflow hosted UI Guidefold

Status: aktywny workflow repozytorium. Data: 2026-09-06.
Cel: utrzymywać spójność projektu ekranów, implementacji i dowodów QA.
Źródło: [polecenie pipeline’u](../../../docs/ui/PIPELINE-PROMPT.md) oraz [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; szczegóły pozostają w dokumentach etapów.

## Wybierz etap i jego wejścia

Sprawdź aktualny status w [pipeline/README](../../../docs/ui/pipeline/README.md) i sekcji Przegląd właściwego dokumentu. Jeśli indeks jest jeszcze tworzony, odczytaj istniejące pliki w `docs/ui/pipeline/`; nie zakładaj ukończenia na podstawie samej obecności pliku.

Czytaj U4 w [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md), [IA](../../../docs/ui/IA.md), [UX](../../../docs/ui/UX.md), [UI](../../../docs/ui/UI.md) oraz wejścia wskazane dla etapu w PIPELINE-PROMPT. Dla kontraktów i portu sprawdź [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) i [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).

Przy prowadzeniu pipeline’u wykonuj etapy 0–8 w kolejności. Stosuj szczegółowy rezultat i rolę specjalisty z PIPELINE-PROMPT: brief → research → persony → ankieta → makiety → symulacje → hi-fi → plan frontendu → komponenty. Każdy etap wymaga dwóch rund Owner + specjalista; przejście dalej wymaga 0 otwartych P1/P2. Ponownie użyj recenzentów w drugiej rundzie etapu, a następny etap przekaż świeżym recenzentom. Dodatkowi recenzenci oraz symulacje z etapów 2, 3, 5, 7 i 8 mają własne wymagania w poleceniu.

Przy lokalnej zmianie gotowego ekranu ustal dotknięte decyzje i zależności; przeglądaj zmieniony zakres zgodnie z DOCUMENTATION-RULES. Nie uruchamiaj całego pipeline’u ponownie bez wpływu na jego pozostałe wyniki.

## Zachowaj ustalone granice

Jedynym wzorcem wizualnym jest [industrial-surveyor](../../../prototypes/industrial-surveyor/DESIGN.md), jego obraz źródłowy i tokeny. Dane makiet i prototypów pochodzą z `examples/monorepo/` i mają widoczne oznaczenie Meridian fixture. Nie przenoś przykładowych twierdzeń ani starych ekranów wzorca do zakresu produktu.

Siedem widoków U4, ich nawigacja, znaczenie stanów i granice danych wynikają z aktualnych IA/UX/UI i etapów. Nie dodawaj ustawień lub ekranów w celu uniknięcia decyzji projektowej. Dokumenty pisz po polsku, a stringi UI oraz nazwy plików, tokenów i komponentów po angielsku.

## Zapisz sprawdzalny rezultat

- Dokument etapu ma najwyżej 120 linii, brief 40, końcowy indeks 30; sekcja Przegląd najwyżej 6 linii. Liczby znalezisk i zamknięcie P1/P2 muszą wynikać z wykonanych recenzji.
- Dla makiet/symulacji stosuj zadania, stany i dostęp do renderowanego HTML określone w etapach 4–5. Nie przedstawiaj symulacji jako pilota U4 z prawdziwymi ludźmi.
- Dla hi-fi i komponentów sprawdź wymagane viewporty, stany, klawiaturę, kontrast i axe. Porównuj z rzeczywistym źródłem; pixel diff w etapie 8 wymaga niezależnego obrazu hi-fi sprzed ekstrakcji.
- Dla implementacji wybierz build i testy z planu etapu 7 oraz aktualnych skryptów pakietu. Sprawdź kontrakty komponentów etapu 8; udane testy fixture nie dowodzą budżetu 10 tys. skilli.
- Nowe artefakty i raporty połącz z właściwym dokumentem etapu, a nowe dokumenty z indeksem zgodnie z DOCUMENTATION-RULES. Zachowaj pytania do ludzi i jawnie opisane ograniczenia pomiarów.

Bieżącą implementację fixture edytuj w `ui/`, a nie w zamrożonym `prototypes/pipeline-hifi/`. Komendy i kontrakty: [ui/README](../../../ui/README.md) oraz [08-components](../../../docs/ui/pipeline/08-components.md). Sprawdzaj build, test, test:contracts, test:e2e i dotknięty zakres flow/visual z package.json; nie regeneruj baseline, aby ukryć różnicę. Prywatne API, logowanie i rzeczywisty Git nadal wymagają integracji z planu 07.

Instrukcje tego skilla służą autorom UI. Nie eksportuj ich do dystrybuowanego `skills/guidefold/` ani do skilli fixture.