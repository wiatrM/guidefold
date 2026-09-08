---
name: guidefold-product-changes
description: Maintain Guidefold product requirements, architecture, backlog, API contracts and their documentation dependencies. Use for changes to the Guidefold product repository; consumer skill discovery uses the distributable bootstrap instead.
---

# Zmiany produktu Guidefold

Status: aktywny workflow repozytorium. Data: 2026-09-06.
Cel: prowadzić zmianę od wymagania do spójnych dokumentów i sprawdzalnego rezultatu.
Źródło i reguły utrzymania: [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill kieruje do kanonicznych dokumentów.

## Ustal źródło decyzji

Czytaj sekcje związane ze zleceniem:
- [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md): use case, obietnica, wymagania i acceptance criteria.
- [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md): granice modułów, dane i integracje.
- [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md): zadanie, zależności i zakres dostarczenia.
- [PIVOT-REVIEW](../../../docs/PIVOT-REVIEW.md): przyczyna rozstrzygnięcia i odrzucone warianty.
- [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md) oraz [indeks ADR](../../../docs/adr/README.md): status i historia decyzji, gdy zmiana dotyczy architektury.

Przypisz pracę do istniejącego wymagania/zadania albo jawnie opisz zmianę zakresu zleconą przez użytkownika. P01–P15 są identyfikatorami lokalnego backlogu. Plan Proposed opisuje zamiar; implementację potwierdzają kod i właściwe dowody.

## Wprowadź zmianę w jej źródle

Aktualizuj dokument odpowiedzialny za daną decyzję i tylko zależne opisy, których prawdziwość się zmienia. Nie twórz równoległej wersji PRD ani nie rozstrzygaj sprzeczności samą datą. Zmianę decyzji architektonicznej zapisz z jej statusem i konsekwencjami według istniejącego formatu ADR.

Dla aktualnego CLI i SEARCH/USE sprawdź zachowanie w kodzie i testach oraz właściwe części [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md), [SEARCH-USE-TELEMETRY](../../../docs/SEARCH-USE-TELEMETRY.md) i [CLAUDE.md](../../../CLAUDE.md). Nie opisuj planowanych komend jako dostępnych. Zmiany hosted UI kieruj do [IA](../../../docs/ui/IA.md), [UX](../../../docs/ui/UX.md), [UI](../../../docs/ui/UI.md) i skilla `guidefold-ui-workflow`.

## Domknij dokumentację i dowody

Stosuj sekcję „Nowe pliki” w DOCUMENTATION-RULES także dla kolejnych dokumentów: status, data, cel, wejścia, zakres zastępowania i właściwy indeks. Artefakt implementacji lub QA podłącz do jego dokumentu; opisuj środowisko, komendę, pochodzenie danych, wynik i ograniczenia.

Sprawdź zmienione linki i zgodność zakresu z acceptance criteria. Dla zmiany zachowania uruchom właściwe istniejące testy. Raportuj osobno dostarczony rezultat, wykonane sprawdzenia i pozostałe założenia. Recenzje agentów i fixture nie zastępują pomiarów na prawdziwych użytkownikach.