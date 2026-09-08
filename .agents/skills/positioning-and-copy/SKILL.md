---
name: positioning-and-copy
description: Keep every Guidefold text (README, PR descriptions, UI strings, skill descriptions, pilot landing) consistent with PRODUCT-FOCUS positioning and anti-slop copy rules. Use when writing or reviewing user-facing text; not for code comments.
---

# Pozycjonowanie i copy

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy tekst o Guidefoldzie mówi jedno prawdziwe zdanie o kliencie i obietnicy, ze źródłem dla każdej liczby.
Źródło: [PRODUCT-FOCUS](../../../docs/PRODUCT-FOCUS.md), [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) §12a „Komunikacja i oferta”, [UX](../../../docs/ui/UX.md) §5–§6. Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, o kim i o czym piszesz

Klient: platform team dużej organizacji z kilkoma harnessami nad jednym monorepo. Job to be done: agent w `platforms/atlas/identity/turnstile/` dostaje kilka reguł, które tam obowiązują, w dowolnym harnessie, bez utrzymywanej ręcznie listy; autor reguł dowiaduje się przed merge, czy da się je znaleźć.
Zdanie do testowania (PRD §12a): „Guidefold dostarcza agentom zatwierdzone instrukcje z repozytoriów firmy i pokazuje zespołowi, które wymagają poprawy.” Demo: U8 pierwsze zadanie w module → U9 zmiana źródła → U7 raport PR. Piramida jest sposobem organizacji wiedzy, nie obietnicą oszczędności.
Matryca PRODUCT-FOCUS porównuje Anthropic Agent Skills, Copilot custom instructions, Codex `AGENTS.md`, Gemini CLI, Cursor/Cline/Windsurf, konwencję agents.md, Google Cloud Agent Registry, rejestry MCP, marketplace'y i Backstage w pięciu kolumnach: scoped by repo location, cross-harness, measures exposure/use, author feedback before merge, quality gate in CI. Trzy value propositions: retrieval zamiast konkatenacji przy skali monorepo (zmierzone), autor dowiaduje się przed merge (zbudowane, nieudowodnione), jedna warstwa pomiaru między harnessami (zbudowane, nieudowodnione). Nagłówek PRODUCT-FOCUS ostrzega, że jego kategoryczne tezy o brakach vendorów są historyczne; nie cytuj ich jako aktualnych.

## Napisz jedno prawdziwe zdanie

| Gdzie pojawia się copy | Czytelnik | Zdanie, które ma być prawdziwe |
|---|---|---|
| `README.md` | Inżynier oceniający repo | Co robi dziś działający CLI/serwis; pivot opisany jako proposed, nie dostępny. |
| Opis PR | Reviewer | Które U/P i jaki dowód; test fixture nazwany R. |
| `description` w `skills/guidefold/SKILL.md` i skillach fixture | Model wybierający skill | Prefiks `[<node>]`, czynność i warunek użycia; bez przymiotników. |
| Stringi UI (`ui/`) | Owner z 15 minutami | Nazwa widoku, obiekt, jedna akcja; „Instrukcje”, „Źródła”, „Do sprawdzenia”, „Użycie” (PRD §12a). |
| Landing pilota | Platform team partnera | CTA „Sprawdź na swoim repozytorium”; obok „Najpierw zobaczysz, które pliki trafią do Guidefolda”. Niegotowe funkcje nie są opisane jako dostępne. |
| Raporty i ADR | Właściciel | Liczba ze źródłem i datą; twierdzenie o konkurencie z URL pobranym danego dnia. |

Każdy claim liczbowy wskazuje raport lub PR (np. p95 113 ms przy 500 skillach i 320 ms przy 6 006 z `docs/reports/bakeoff/R4b-lazy-terms-postings-2026-09-05.md`). Claim bez źródła usuwasz, nie łagodzisz.
Tabela „What we do not do, and who does” obowiązuje w copy: nie obiecuj portalu, marketplace, registry, własnego modelu ani automatycznej promocji.

## Odrzuć slop

Zakazane słowa (UX §6): seamless, streamline, empower, unlock, effortless, supercharge, ogólne powerful; po polsku ich odpowiedniki. Bez odruchowej reguły trzech, anonimowego „badania pokazują”, ciągłych em dash, zdań „to nie X, to Y”. Nagłówki są nazwami, nie zdaniami reklamowymi. W produkcie nie ma hero, sloganu ani wyśrodkowanego wielkiego nagłówka.
Test na głos: przeczytaj string jak do współpracownika i przepisz to, czego byś nie powiedział. Test zrzutu: bez logo czytelnik ma nazwać, co produkt robi; „jakiś AI dashboard” to P1.
Unknown jest wynikiem; eksport nie jest publikacją; pobranie nie jest użyciem (UX §5). Treść wygenerowana jest oznaczona w miejscu odczytu.

## Sprawdź przed zakończeniem

- `grep -niE 'seamless|streamline|empower|unlock|effortless|supercharge' <zmienione pliki>` zwraca pusto.
- Każda liczba w tekście ma odnośnik do raportu, PR lub URL z datą.
- Tekst nazywa klienta (platform team, wiele harnessów) albo konkretną personę, nie „użytkowników”.
- Żadna funkcja ze statusem Proposed nie jest opisana jako dostępna.
- Stringi UI przeszły test na głos; opis PR nazywa test fixture jako R.
