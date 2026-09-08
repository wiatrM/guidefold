---
name: dry-without-wrong-abstraction
description: Apply DRY in Guidefold with the rule of three and a single source of truth for data, tokens and contracts; prefer duplication over a wrong abstraction. Use when you see repeated code or copied values, and when tempted to create a shared helper. Not for merging things that only look alike.
---

# DRY bez złej abstrakcji

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: jedno źródło prawdy dla każdego faktu, a wspólny kod dopiero wtedy, gdy powtórzenie jest tym samym pojęciem, nie tylko tym samym tekstem.
Źródło: [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md) ("Nie duplikuj tokenów, kontraktów lub wymagań"), [UI](../../../docs/ui/UI.md) §2 i §4, [08-components](../../../docs/ui/pipeline/08-components.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Rozróżnij fakt od kodu

Dane i decyzje mają dokładnie jedno miejsce; kod może się powtarzać, dopóki nie wyraża tego samego pojęcia.

| Rodzaj | Jedyne źródło | Naruszenie |
|---|---|---|
| Kolory, rozmiary, typografia UI | `ui/src/tokens/tokens.css` | wartość hex lub px w `*.module.css` albo w TSX |
| Kontrakt SEARCH/USE | [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md) i schematy w `tools/` | drugi opis pól w README lub w komentarzu |
| Wymagania i AC | [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) | przepisane AC w dokumencie etapu lub skillu |
| Dane makiet i testów UI | `examples/monorepo/` (Meridian) | ręcznie wpisane obiekty w testach |
| Reguły frontmatter skilli | [CONVENTIONS](../../../docs/CONVENTIONS.md) | walidacja powtórzona w drugim miejscu z innymi limitami |

## Stosuj regułę trzech

Pierwsze wystąpienie piszesz wprost. Drugie kopiujesz i zaznaczasz w PR. Dopiero trzecie, gdy wszystkie trzy zmieniają się z tego samego powodu, wyciągasz do wspólnej funkcji lub komponentu. Dwa fragmenty, które dziś wyglądają tak samo, ale zmienią się z różnych powodów (np. walidacja importu i walidacja publikacji), zostają osobno. Zła abstrakcja kosztuje więcej niż duplikat: parametry-przełączniki, `if` po typie wywołującego i "wspólna" funkcja z pięcioma opcjami to sygnał, żeby ją rozdzielić z powrotem.

## Nie twórz worków

Plik `utils`, `helpers`, `common` bez nazwy pojęcia jest zakazany; wspólny kod nazywa się od tego, co robi (`urn.py`, `digest.go`, `useSkillQuery.ts`). Biblioteka UI ma najwyżej 14 komponentów ([UI](../../../docs/ui/UI.md) §4); drugi wariant istniejącego komponentu wymaga pisemnego uzasadnienia w PR, a nie kopii z innym kolorem. Formularze i lifecycle nie są komponentami biblioteki.

## Przykład z repo

Adapter fixture i adapter API w `ui/src/data` implementują jeden kontrakt; wspólny jest typ i test kontraktowy, nie kod ładowania. Wspólna funkcja `loadAnything(source, mode)` z rozgałęzieniem po `mode` byłaby złą abstrakcją: dwa źródła zmieniają się z różnych powodów.

## Sprawdź przed zakończeniem

- `grep -rnE '#[0-9a-fA-F]{6}\b' ui/src --include='*.css' --include='*.tsx' | grep -v tokens.css` zwraca pusto.
- Czy każda nowa wspólna funkcja ma dziś co najmniej trzech użytkowników zmieniających się z jednego powodu?
- Czy żaden nowy plik nie nazywa się `utils`, `helpers`, `common`, `misc`?
- Czy zmieniona wartość (limit, próg, token, pole kontraktu) została zmieniona w jednym miejscu, a zależne opisy wskazują to miejsce?
- Czy nowy komponent UI mieści się w limicie 14 i nie powiela istniejącego z drobną różnicą?
