# Przegląd wizualny — ekstrakcja UI
Status: kontrola renderu i zachowania zakończona, formalne R2 zamknięte; 2026-09-06.
Cel: niezależne porównanie komponentów po przeniesieniu. Wejścia: [08-components](../docs/ui/pipeline/08-components.md), [przegląd hi-fi](../prototypes/pipeline-hifi/design-qa.md), [manifest](../prototypes/pipeline-hifi/qa/baseline/manifest.json).
Nie zastępuje źródła Industrial Surveyor ani pomiaru z prawdziwymi użytkownikami.
## Porównanie
| Obszar | Ocena i dowód |
|---|---|
| Typografia | Barlow Condensed / Inter, lokalne fonty; identyczne łamanie tekstu w 42 parach komponentów. |
| Odstępy | Zachowana siatka i geometria; w trzech szerokościach jednakowe rozmiary obszarów komponentów. |
| Kolory | Paleta źródła bez zmian; --transparent jedynie nazywa istniejący bezbarwny obrys. Teal system, orange decyzja, red błąd. |
| Assety | Oryginalne rastrowe mark/grid; weryfikowane SHA źródeł i assetów hi-fi; Phosphor regular. |
| Treść | Galeria ma identyczne props i Meridian fixture. Nieznany filtr ma jawny błąd; skopiowany URN nie udaje sukcesu po zmianie wyboru. |
Obejrzano wspólnie referencję i UI: [tabela 390](qa/comparison-table.jpg); Designer sprawdza wszystkie 14 par przy390. Porównanie obejmuje typography/spacing/colors/assets/copy, nie tylko automatyczne piksele.
## Iteracje
1. Ekstrakcja zachowała 42 obrazy; wycofano niewykorzystane tony ActionButton, a disabled link nie ma href.
2. Kontrakty wskazały dwa literalne transparent i stale notice URN; użyto wspólnego tokenu i powiązano wynik clipboard z konkretną wartością/operacją.
3. R1 kodu wykrył cichy fallback nieznanego filtra do All i niewidoczny wybrany liść po zwinięciu drzewa. Poprawiono jawny błąd oraz otwarcie przodków po nowym wyborze; dodano regresje.
## Dowody
- [pixel-diff](qa/pixel-diff.json): 42/42 pary, 0 zmienionych pikseli przy threshold0.05/includeAA, 1280×720/820×720/390×720, źródła i obrazy SHA zweryfikowane.
- [contracts](qa/contracts.json): 14 kompletów index/module/test/story, 103 tokeny, 21 CSS, brak zależności runtime komponentów/domain od fixture.
- [Playwright](qa/playwright-report.json): 12 testów; 7 tras + galeria w3szerokościach, ujawnione treści/menu, 42 stany, nieznane filtry i pełny przebieg klawiaturą; 0 błędów axe reguł WCAG A/AA.
- [owner-flow](qa/owner-flow.json): 9 grup, dokładny plik/SHA, właściwy Git host/plik/commit, rewizje i odczyt ograniczonych stanów.
- Vitest45/45 i build PASS. Fixture bundle ~640kB/173kB gzip pozostawia ostrzeżenie; brak produkcyjnego testu 10k.
## Przegląd
R1: Owner 0/0/0, Code reviewer 0/1/1, Designer 0/0/0; poprawki wykonane.
R2: wszystkie trzy role 0/0/0. Designer powtórzył porównanie źródeł/obrazów i sprawdził nowe stany w przeglądarce.
Final result: passed
