---
name: user-research-alignment
description: Tie any user-facing change to the researched personas, dated observations, survey thresholds and open questions from docs/ui/pipeline. Use before adding or changing UI behavior or claiming what users need; not for backend-only work.
---

# Zgodność z badaniem użytkowników

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każde twierdzenie o użytkowniku i każda zmiana zachowania UI wskazuje personę, zadanie i dowód z pipeline albo jest oznaczona jako założenie z kryterium obalenia.
Źródło: [01-research](../../../docs/ui/pipeline/01-research.md), [02-personas](../../../docs/ui/pipeline/02-personas.md), [03-survey](../../../docs/ui/pipeline/03-survey.md), [pipeline/README](../../../docs/ui/pipeline/README.md), [PRODUCT-FOCUS](../../../docs/PRODUCT-FOCUS.md) „Design partner”. Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Wskaż personę, zadanie i dowód

| Persona (02, [założenie]) | Zadanie kluczowe | Wejście do UI | Dowody z 01 |
|---|---|---|---|
| P1 Owner instrukcji, użytkownik podstawowy | Porównać źródło, treść, zakres i dowód problemu; przyjąć do eksportu, poprawić lub odrzucić | Proposals z linku lub po zmianie źródła; Usage → Skill/Proposals po feedbacku | R1, R2, R5; R7 to wymaganie, nie dowód |
| P2 Developer przy zadaniu | Znaleźć instrukcję i sprawdzić zastosowanie w bieżącym module | Skill z zachowanym repo/scope; Library, gdy zna cel, nie nazwę | R3, R4 |
| P3 Operator dostarczania (zadanie ownera) | Sprawdzić, która rewizja jest published, a która ma dowód load | Organization → Integrations; Skill/Usage | R6, R4, R7 |

Persona to hipoteza zadania, nie rola uprawnień; owner/member rozstrzyga API (02 §4). Owner ma 15 minut aktywnego review na decyzję (03 S6); kolejność dowodów na ekranie służy temu budżetowi.
Obserwacje R1–R7 mają URL i datę odczytu; granica dowodu w kolumnie „Granica dowodu” obowiązuje przy cytowaniu. Z reakcji pod issue nie wyprowadzamy stanowisk, częstości problemu ani gotowości do zapłaty.

## Zanim zmienisz UI

Zapisz trzy odpowiedzi: która persona, które zadanie z tabeli, który dowód (R-id, S-id z progiem, lub [założenie] z kryterium obalenia z 01 §2 albo 02 §3). Bez nich zmiana jest domysłem i zostaje propozycją w raporcie.
Progi z 03 są ustalone przed badaniem i liczone przy ≥5 ważnych odpowiedziach właściwej grupy; wynik syntetyczny [syntetyczne, n=3] nie zalicza żadnego progu i zmienia tylko kolejność makiet oraz priorytet pytań (S6, S4/S9, S7). Nie zmieniaj liczby siedmiu widoków U4 na podstawie danych syntetycznych.
Otwarte pytania do ludzi z pipeline/README (kto przygotowuje i zatwierdza; root/podfolder i harness; zakres źródeł opuszczających komputer; mapa czy lista; eksport/published/loaded; koszt obiegu UI→Git→sync) pozostają otwarte do rozmowy z uczestnikami. Nowa funkcja nie może udawać odpowiedzi na nie.
U4 AC5 wymaga ≥4/5 prawdziwych osób niebędących autorami UI; symulacje agentów z etapu 5 są dowodem R dla makiet, nie P.

## Zapisz to, czego nie wiesz

Twierdzenie o użytkowniku ma źródło z datą albo etykietę [założenie] i zdanie, co je obali (DOCUMENTATION-RULES „Nowe pliki”). Brak zdarzeń jest nierozstrzygnięty, nie jest brakiem potrzeby.
Design partner (PRODUCT-FOCUS): repozytorium, developerzy, odbierający owner, polityka danych, data startu. Dopóki sekcja nie ma nazw, każde „done” UI jest prowizoryczne (ADR-0029 reguła 3). Nowe pytanie do uczestników dopisz do listy w pipeline/README z odwołaniem do dokumentu etapu; nie prowadź drugiej listy.
Ankieta 03 dotyczy prawdziwych zdarzeń, nie opinii o obietnicy; moderator nie pokazuje makiet przed opisem zdarzenia i nie zbiera kodu ani danych osobowych.

## Sprawdź przed zakończeniem

- Zmiana UI ma zapisaną personę P1–P3, zadanie i dowód (R-id, S-id lub [założenie] z kryterium obalenia).
- Żadne twierdzenie o użytkownikach w dokumentach lub PR nie występuje bez źródła z datą albo etykiety [założenie].
- Dane syntetyczne i symulacje agentów są podpisane i nie zaliczają progów ani AC5.
- Liczba widoków U4 i progi z 03 pozostają bez zmian, chyba że zmienił je wpis wg `scope-change-protocol`.
- Nowe pytanie do ludzi jest w liście pipeline/README, nie w osobnym pliku.
