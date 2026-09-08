# Pipeline UI Guidefold
Status: etapy 0–8 zamknięte, 0 otwartych P1/P2/P3, 2026-09-06. Indeks decyzji, implementacji i otwartych pytań.
Wejście: [reguły dokumentacji](../../DOCUMENTATION-RULES.md), [polecenie](../PIPELINE-PROMPT.md), [IA](../IA.md), [UX](../UX.md), [UI](../UI.md). Bieżący frontend: [ui](../../../ui/README.md).
Zastępuje rozproszoną nawigację po etapach; nie zmienia PRD ani statusu ADR. Daty i liczby dotyczą przeglądów agentów, nie badań klientów.
| Etap | Dokument | Data | Recenzenci / rundy | Zamknięte P1/P2 (unikalne) |
|---|---|---|---|---|
| 0 Brief | [00-brief](00-brief.md) | 2026-09-06 | Owner + Architekt, 2 | 0/2 |
| 1 Research | [01-research](01-research.md) | 2026-09-06 | Owner + Badacz UX, 2 | 0/2 |
| 2 Persony | [02-personas](02-personas.md) | 2026-09-06 | Owner + Badacz UX, 2; dwóch minerów | 0/1 |
| 3 Ankieta | [03-survey](03-survey.md) | 2026-09-06 | Owner + Badacz UX, 2; trzy persony | 0/2 |
| 4 Makiety | [04-wireframes](04-wireframes.md) | 2026-09-06 | Owner + Projektant IA, 2 | 0/5 |
| 5 Symulacja | [05-simulation](05-simulation.md) | 2026-09-06 | Owner + Badacz UX, 2; dwie próby po 3 agentów | 0/0 formalnie; 0/1 tarcie |
| 6 Hi-fi | [06-ux-ui](06-ux-ui.md) | 2026-09-06 | Owner + Designer, 3 | 0/2 |
| 7 Plan FE | [07-frontend](07-frontend.md) | 2026-09-06 | Owner + Principal + Architekt, 2 | 0/5 |
| 8 Komponenty | [08-components](08-components.md) | 2026-09-06 | Owner + Code reviewer + Designer, 2 | 0/1 |
P3 surowego Markdown z etapu 5 zamknięto w 6. Szczegółowe znaleziska, źródła, progi i dowody pozostają w dokumentach etapów.
## Otwarte pytania do ludzi
- Kto faktycznie przygotowuje i zatwierdza instrukcje, kiedy wraca do kolejki oraz jaki dowód powoduje zmianę? 01 Q1/Q6, 03 S1/S2/S10; brak okazji nie dowodzi braku potrzeby.
- Jak root/podfolder i konkretny harness wpływają na znalezienie instrukcji; czy repo/scope pozwalają samodzielnie wybrać właściwy skill? 01 Q2, 03 S3/S8, 05 §4.
- Jaki zakres źródeł może opuścić komputer i kto go dopuszcza? 01 Q3, 03 S7; kwalifikacja pilota wymaga rzeczywistej polityki zespołu.
- Czy mapa pomaga w realnej decyzji, czy wystarcza wyszukiwanie i lista? 01 Q4, 03 S5/S8; odpowiedź zmienia priorytet, nie automatycznie siedem widoków.
- Czy owner rozumie wpływ decyzji oraz różnicę eksport/published/loaded; czy to pomaga podczas incydentu? 01 Q5, 03 S4/S9, 05 §4.
- Ile kosztuje cały obieg UI→Git→sync względem obecnej pracy, a ile aktywne review? 01 hipoteza, 03 S6, 05 §4; próg oszczędności ustalamy przed pilotem.
Decyzja człowieka: dopuścić zakres i uczestników pilota oraz potwierdzić proponowane decyzje ADR-0031. U4 AC5 wymaga ≥4/5 prawdziwych osób niebędących autorami UI; AC2 wymaga pomiaru 10k/p95 w realnej sieci.
Zmiany pozostają do przeglądu, bez commita. F1–F9 dotyczą fixture; backend, realne logowanie/Git i pomiary należą do F10–F21.
