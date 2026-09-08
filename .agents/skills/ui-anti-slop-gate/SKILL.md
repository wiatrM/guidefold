---
name: ui-anti-slop-gate
description: The Guidefold anti-slop gate for screens, copy and documents (UX §6): banned visual patterns, banned words, structural slop, the screenshot test and the read-aloud test. Use before submitting any UI, string, prototype or doc change. Not a substitute for user research.
---

# Bramka anti-slop

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: żaden ekran, string ani dokument nie wygląda jak „jakiś AI dashboard” i nie mówi rzeczy, których nie powiedziałbyś współpracownikowi.
Źródło: [UX §6–§7](../../../docs/ui/UX.md), [UI §1](../../../docs/ui/UI.md), [DESIGN.md prototypu](../../../prototypes/industrial-surveyor/DESIGN.md). Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Odrzuć wzorce wizualne z UX §6

| Niedopuszczalne | Wymagana postać |
|---|---|
| Gradienty jako powierzchnia, glassmorphism, glow, neon | Płaskie tło graphite i obrys 1 px |
| Duże zaokrąglenia, pill badges, emoji jako ikony | Promień 2 px i Phosphor regular |
| Hero, slogan, wyśrodkowany wielki nagłówek w produkcie | Nazwa widoku, identyfikacja obiektu i jego działanie |
| Karty albo metryki dodane dla symetrii | Tylko dane potrzebne do konkretnej decyzji |
| Wykres bez pytania, skali lub danych | Tekstowy dowód albo jawny brak obserwacji |
| Przykładowe firmy/ludzie/liczby udające produkcję | Dane rzeczywiste lub podpisany Meridian fixture |
| Przełączniki motywu lub gęstości | Jeden graphite, stałe Balanced 40 px |
| Automatyczne ruchy, confetti, pulsujące statusy | Ruch wyłącznie po zmianie stanu, z reduced motion |
| Nowy wariant komponentu bez potrzeby | Istniejące API; drugi wariant ma pisemne uzasadnienie |

## Odrzuć słowa i struktury

Zakazane w stringach, copy i dokumentach: „seamless”, „streamline”, „empower”, „unlock”, „effortless”, „supercharge”, ogólne „powerful”; po polsku ich kalki („bezproblemowo”, „usprawnij”, „odblokuj”). Unikaj odruchowej reguły trzech, anonimowego „badania pokazują”, ciągłych em dash i zdań „to nie X, to Y”.
Nagłówki są nazwami, nie zdaniami reklamowymi. Tooltip nie powtarza etykiety. Sekcja z dwoma faktami nie dostaje trzeciego dla symetrii. Krótka kolumna jest w porządku.
Hook `.claude/hooks/check-slop.sh` (PostToolUse w `.claude/settings.json`) grepuje tę listę w `ui/`, `docs/ui/` i `prototypes/pipeline-*`; ostrzeżenie hooka nie zastępuje czytania.

## Wykonaj dwa testy

- Test zrzutu: usuń logo, pokaż ekran inżynierowi spoza projektu i zapytaj, co produkt robi. Odpowiedź „jakiś AI dashboard” to P1. Wynik agenta jest syntetyczny; z człowiekiem liczy się bardziej.
- Test na głos: przeczytaj każdy nowy string tak, jak do współpracownika; przepisz zdania, których nie użyłbyś w rozmowie. Etap 6 przechowuje inwentarz stringów; nowe copy dopisz tam, gdzie leży kontekst ([06-ux-ui](../../../docs/ui/pipeline/06-ux-ui.md)).

## Sprawdź przed zakończeniem

1. `git diff -U0 -- ui docs/ui prototypes | grep -i -E 'seamless|streamline|empower|unlock|effortless|supercharge|powerful'` zwraca nic.
2. Zmiana ekranu wskazuje obiekt/dowód/akcję i obsługiwane stany (UX §7); nic nie jest zaznaczone jako zaliczone na podstawie planu.
3. Brak nowego wariantu komponentu bez pisemnego powodu w opisie zmiany.
4. Każdy przykładowy obiekt ma widoczny podpis Meridian fixture albo jest danymi rzeczywistymi.
5. Test zrzutu i test na głos wykonane i zapisane w opisie zmiany.
