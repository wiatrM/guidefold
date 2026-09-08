---
name: eval-evidence-rules
description: What counts as evidence in Guidefold: labelled corpora for routing quality, the Meridian fixture as regression only, R/Q/P acceptance labels, run identifiers, synthetic versus human data. Use before quoting any metric, closing an acceptance criterion or claiming a result. Not for UI copy review.
---

# Reguły dowodów i ewaluacji

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: żadna liczba w dokumencie, PR ani raporcie nie pojawia się bez ścieżki do jej odtworzenia.
Źródło: [CLAUDE.md](../../../CLAUDE.md) (Evaluation corpora), [PRODUCT-PIVOT §1, §12a](../../../docs/PRODUCT-PIVOT.md), [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md) (Zasady prowadzenia), [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md). Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal rodzaj twierdzenia

| Twierdzenie | Dopuszczalny dowód |
|---|---|
| Jakość routingu (model, konfiguracja, ranking) | Wyłącznie realne, etykietowane korpusy z manifestu `docs/reports/bakeoff/validation/corpora-manifest.json` (rewizja HF + SHA-256 per plik), przepuszczone przez ścieżkę produktu `policy_filter → candidates → score → select(admissible=…)`. |
| Regresja CI | Fixture Meridian (`examples/monorepo`, 220 zapytań golden). To dev/regresja; zysk na fixture odwrócił się na held-out (PR #19), więc nie jest dowodem wyboru. |
| Skala, rozmiar, latencja | Lokalne nieetykietowane korpusy w `experiment/` (gitignored). |
| Acceptance criteria PRD | R (Release) przechodzi w wydaniu; Q (Quality Gate) na próbce z opisaną metodą; P (Pilot Evidence) tylko z użycia przez ludzi. Nieoznaczone AC to R. |
| Zachowanie użytkownika, użyteczność (np. U4 AC5: 4 z 5 osób) | Prawdziwi ludzie niebędący autorami. Symulacje agentów są podpisane jako syntetyczne i nie zamykają pytania. |

## Zapisz dowód tak, aby dało się go odtworzyć

- Raport podaje komendę, środowisko (sprzęt, przeglądarka, sieć, wersje), fixture albo dane rzeczywiste, identyfikator przebiegu, wynik i ograniczenia. Zrzut lub pozytywna recenzja nie zastępują przebiegu.
- Pobranie korpusów: `python3 tools/eval/corpora.py fetch` w venv z `huggingface_hub` (np. `~/.cache/guidefold/gpu-venv`); dane pod `~/.cache/guidefold/corpora/`, nigdy w repo.
- `tests/test_corpora.py` pomija sprawdzenia bez cache. Skip oznacza „nie zmierzono tutaj”, nie pass; nie raportuj zielonego CI jako pomiaru jakości.
- p95 i błędy per grupa cold/warm, nie średnia; pomiar 10k skilli (U4 AC2) wymaga produkcyjnego builda i zamrożonego datasetu ([07 §Budżety](../../../docs/ui/pipeline/07-frontend.md)).
- Wzbogacone pola z P06–P08 nie wchodzą do produkcyjnego rankingu; wpływ na retrieval wymaga osobnej, z góry opisanej ewaluacji.

## Nie powtarzaj błędów z przeglądu E1.3

Peer review z 2026-09-05 (`docs/reports/bakeoff/E1.3-peer-review-2026-09-05.md`) znalazł sześć błędów spec-level: BM25 bez saturacji, cosinus bez pierwiastka, bramka wobec nasyconej metryki, kompletność bez wymaganych zależności, wybiórcza tabela, nadinterpretacja regresji. Wnioski:
- formuła w specyfikacji dostaje test referencyjny wobec wersji float zanim zacytujesz jej liczby;
- bramka jest sprawdzana pod kątem osiągalności względem baseline;
- cytując tabelę, cytuj też wiersze niekorzystne;
- gdy poprawka pogarsza wynik, przelicz baseline i napisz to; nie stroj, aby odzyskać wynik błędu.

## Sprawdź przed zakończeniem

1. Każda liczba ma komendę, run id i środowisko w tym samym dokumencie albo link do raportu, który je ma.
2. Twierdzenie o jakości routingu wskazuje korpus z manifestu, nie fixture.
3. Etykieta R/Q/P przy każdym zamykanym AC jest zgodna z rodzajem dowodu.
4. Dane syntetyczne są podpisane `[syntetyczne, n=…]` i nie zamykają pytań do ludzi.
5. Nowa formuła ma test referencyjny w `tests/` przed publikacją wyniku.
