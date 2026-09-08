---
name: scope-change-protocol
description: Record and route a deviation from PRODUCT-PIVOT, PIVOT-BACKLOG or an ADR: log the discrepancy, pick the decision consistent with the current order, update the owning document. Use when a task conflicts with a canonical doc; not for routine details.
---

# Protokół zmiany zakresu

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: odstępstwo od PRD, backlogu lub ADR jest zapisane w dokumencie, który za tę decyzję odpowiada, z widoczną historią i statusem.
Źródło: [DOCUMENTATION-RULES](../../../docs/DOCUMENTATION-RULES.md) „Pierwszeństwo” i „Wybór dokumentu”, [guidefold-product-changes](../guidefold-product-changes/SKILL.md), [indeks ADR](../../../docs/adr/README.md). Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, co z czym się kłóci

Bieżące polecenie użytkownika wyznacza zakres pracy. W obrębie autoryzowanego pivotu: PRD określa wymagania, PIVOT-ARCHITECTURE ograniczenia techniczne, PIVOT-BACKLOG kolejność, PIVOT-REVIEW uzasadnienia. Wcześniejsze dokumenty (`docs/MVP.md`, `docs/BACKLOG.md`, `docs/PRODUCT-FOCUS.md`) pozostają zapisem poprzedniej decyzji.
Nie rozstrzygaj sprzeczności datą pliku ani statusem. Proposed opisuje zamiar: nie dowodzi implementacji, nie pozwala na publikację, migrację danych ani zmianę zadań zewnętrznych, ale też nie cofa pracy już zleconej przez użytkownika. Accepted wymaga rzeczywistej decyzji właściciela, nie ukończonego prototypu.
Zanim napiszesz kod, zapisz rozbieżność w raporcie lub PR według szablonu:

```
Rozbieżność: <zlecenie / kod> vs <dokument §sekcja, cytat ≤ 1 zdanie>
Decyzja w tej pracy: <co robisz> zgodnie z <bieżące zlecenie | dokument nadrzędny>
Dokument zastępowany lub do zmiany: <ścieżka §sekcja>; status: <bez zmian | do aktualizacji | ADR amendment>
Konsekwencje: <co przestaje być prawdziwe w zależnych opisach>
Do decyzji właściciela: <tak/nie; jedno pytanie>
```

## Skieruj zmianę do właściwego dokumentu

| Rodzaj odstępstwa | Gdzie zapisać | W tej samej pracy zaktualizuj |
|---|---|---|
| Wymaganie, AC, obietnica (U1–U11) | PRODUCT-PIVOT, właściwa sekcja U | PIVOT-BACKLOG (zależności, dowód odbioru), PIVOT-REVIEW (powód), zależne opisy w `docs/ui/` |
| Kolejność, zależność, zakres Core/beta | PIVOT-BACKLOG | §13 PRD, jeśli zmienia termin lub etap; brief `docs/ui/pipeline/00-brief.md`, jeśli dotyka U4 |
| Granica modułu, proces, kontrakt API–worker, nowy serwis | Nowy ADR lub amendment istniejącego (format i indeks `docs/adr/README.md`) | PIVOT-ARCHITECTURE, HARNESS-SERVICE-CONTRACT przy zmianie kontraktu |
| Powierzchnia zamrożona przez ADR-0029 (komponent, język, baza, worker, target) | Amendment ADR-0031 lub nowy ADR wskazujący regułę ADR-0029 | Wpis w PR „która reguła pozwala” (reguła 7) |
| Ekran, string, komponent U4 | Dokument etapu pipeline z nową rundą przeglądu | `docs/ui/pipeline/README.md`; `guidefold-ui-workflow` |
| Reguła odczytu dokumentów | DOCUMENTATION-RULES | AGENTS.md i skille projektu, które ją cytują |

Zmianę wcześniejszej decyzji ADR zapisz jako amendment z widocznym odsyłaczem w obu plikach; nie nadpisuj historii, nie usuwaj statusu (PIVOT-REVIEW „Poprawki w dokumentach”). Zgodność indeksu `docs/adr/README.md` z linią `Status:` w pliku jest obowiązkowa.
Nie twórz równoległej wersji PRD, drugiego backlogu ani „tymczasowego” dokumentu decyzji. Skill projektu jest instrukcją odczytu, nie miejscem na nowe wymagania.

## Zostaw decyzję właścicielowi

Odstępstwo, które zmienia klienta, obietnicę, termin z §13 PRD, izolację org (P02) lub kanoniczność Git (ADR-0031 pkt 5), realizujesz tylko na jawne polecenie użytkownika; inaczej zostawiasz wpis „Do decyzji właściciela: tak” i wykonujesz część niezależną od odpowiedzi.
Status Accepted, zmiana etykiety R/Q/P i zamknięcie kill criterion nie są decyzjami agenta.

## Sprawdź przed zakończeniem

- Każda rozbieżność ma pięciolinijkowy wpis w raporcie lub PR.
- Zmieniony dokument kanoniczny i jego zależne opisy zaktualizowano w tej samej pracy; brak drugiej wersji PRD.
- Nowy lub zmieniony ADR ma wpis w `docs/adr/README.md` zgodny z linią `Status:`.
- Żaden status nie został podniesiony do Accepted bez decyzji właściciela.
- Praca zależna od pytania do właściciela jest odłożona; reszta wykonana.
