---
name: adr-writing
description: How to write, number, status and index an Architecture Decision Record in docs/adr for Guidefold. Use when a change alters architecture, a hard rule, a product boundary or reverses an earlier ADR. Not for backlog items or routine implementation notes.
---

# Pisanie ADR

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: decyzja ma jeden plik, jeden status i wpis w indeksie zgodny z plikiem.
Źródło: [indeks ADR](../../../docs/adr/README.md), [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md), wzorce [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md) i [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, czy to jest ADR

| Zmiana | Miejsce |
|---|---|
| Nowa granica architektury, hard rule, zamrożenie zakresu, zmiana źródła prawdy | Nowy ADR |
| Odwrócenie lub zawężenie istniejącego ADR | Nowy ADR z linią `Amends:`/`Supersedes:`; stary plik zostaje, dostaje adnotację `Proposed amendment:`/`Superseded by:` |
| Kolejność pracy, zależności, zakres wydania | [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md), nie ADR |
| Wymaganie produktowe lub acceptance criteria | [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md), nie ADR |

## Napisz plik w istniejącym formacie

- Nazwa: `docs/adr/ADR-<NNNN>-<slug>.md`; numer to ostatni w `ls docs/adr` plus jeden. Sprawdź `ls`, nie pamięć: 0032 jest zajęty przez zasady inżynierskie, 0027/0028 zajęły wcześniej PR-y GPU i graph-validation.
- Nagłówek: `# ADR-NNNN: <tytuł>`, potem pogrubione linie `Status:` (`Proposed · data · kto proponuje` albo `Accepted · data · decision of the product owner` z cytatem decyzji), `Amends:`/`Proposes amendments to:`, `Governs:` (czym rządzi: dokument, backlog, dispatch).
- Sekcje: `## Context`, `## Decision` (albo `## Proposed decision` dla Proposed), `## Consequences`, `## References`/`## Sources`. Kontekst mówi, co jest prawdą dziś i z jakiego dowodu; decyzja jest listą reguł sprawdzalnych, nie intencji.
- Accepted wymaga rzeczywistej decyzji właściciela zapisanej w pliku; nie awansuj statusu na podstawie braku sprzeciwu ani daty (DOCUMENTATION-RULES, Pierwszeństwo).
- Proposed opisuje zamiar. Nie pisz w ADR, że coś jest wdrożone; dowodem wdrożenia są kod, testy i raport z identyfikatorem przebiegu.
- Nie nadpisuj historii: poprawki treści starego ADR ograniczają się do adnotacji o amendmencie i linku.

## Zaktualizuj indeks w tej samej pracy

Dodaj wiersz w tabeli `docs/adr/README.md` (`#`, Title, Status, Date, Supersedes / amended by); jego `Status` musi być literalnie zgodny z linią w pliku. Gdy ADR zmienia zachowanie opisane w `docs/DESIGN.md`, `docs/CONVENTIONS.md`, `CLAUDE.md` lub w skillu projektu, zmień te opisy teraz, nie w osobnym zadaniu.

## Sprawdź przed zakończeniem

1. Numer nie koliduje: `ls docs/adr | grep <NNNN>` zwraca tylko nowy plik.
2. Linia `Status:` w pliku i wiersz w `docs/adr/README.md` są identyczne co do statusu i daty.
3. Każdy amendowany ADR ma adnotację zwrotną z linkiem.
4. Sekcja Decision zawiera reguły, które recenzent może sprawdzić tak/nie.
5. Zależne dokumenty (DESIGN, CONVENTIONS, CLAUDE.md, skille) nie opisują już starego stanu.
