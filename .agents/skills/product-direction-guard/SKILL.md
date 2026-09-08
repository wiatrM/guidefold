---
name: product-direction-guard
description: Check that a Guidefold task serves the authorized product direction (U1–U11, P01–P15, the platform-team customer) before building. Use when picking up, scoping or reviewing any task; not for consumer-monorepo skill discovery.
---

# Strażnik kierunku produktu

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każde zadanie w tym repo ma wskazaną historię U, pozycję backlogu i klienta, albo jest jawnie zapisaną zmianą zakresu.
Źródło: [PRODUCT-PIVOT](../../../docs/PRODUCT-PIVOT.md) §1, §13, §14, [PRODUCT-FOCUS](../../../docs/PRODUCT-FOCUS.md), [PIVOT-BACKLOG](../../../docs/PIVOT-BACKLOG.md). Decyzja: [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Ustal, komu i której obietnicy służy zadanie

Klient to platform team dużej organizacji z kilkoma harnessami nad jednym monorepo (PRODUCT-FOCUS „The customer”, ADR-0029 kontekst). Nie jest nim pojedynczy developer z jednym repo i jednym harnessem; ten segment obsługują vendorzy.
Obietnica z PRODUCT-PIVOT §1: agent dostaje zatwierdzone instrukcje z repozytoriów firmy, a zespół widzi, które wymagają poprawy. Aktywacja ownera to realny import, publikacja i zrozumiałe źródło/scope; aktywacja zespołu to realne zadanie z potwierdzonym loadem. Mapa jest pierwszym efektem, nie dowodem wartości.
Wartość nie leży w modelu: dense retrieval to jeden gated tor badawczy, nigdy zależność produktu (ADR-0029 reguła 2; PRODUCT-FOCUS „Our own retrieval model”).
Przed pierwszą zmianą zapisz w briefie: `U<n>` z PRODUCT-PIVOT, `P<nn>` z PIVOT-BACKLOG, persona (owner, dev, operator), dowód odbioru z kolumny „Dowód odbioru”. Brak którejś pozycji oznacza zmianę zakresu: użyj `scope-change-protocol`, nie koduj.

## Odrzuć to, czego nie robimy

Tabela „What we do not do, and who does” w PRODUCT-FOCUS oraz §14 PRD wykluczają: portal katalogowy, marketplace, indeks serwerów MCP, wygraną w single-harness/single-repo, registry jako produkt, własny model, automatyczną promocję i lifecycle, granularne ACL/SCIM, automatyczne wykonywanie runbooków, samoczynną publikację, billing, HA/multi-region.
ADR-0029 reguła 1 zamraża powierzchnię: nowy komponent runtime, język, baza, worker lub target wdrożenia wymaga wskazania reguły, która na to pozwala, albo poprawki ADR-0031. PIVOT-BACKLOG „Podział techniczny”: use case nie wyznacza mikroserwisu.

| Sygnał dryfu | Co zrobić |
|---|---|
| Zadanie nie ma U/P ani persony | Zapisz jako pytanie do właściciela w raporcie; nie implementuj. |
| „Przyda się później”, konfigurowalność, drugi wariant | Usuń; YAGNI, ADR-0029 reguła 7 (KISS review). |
| Feature z listy „not us” lub §14 PRD | Odrzuć z odnośnikiem do wiersza tabeli; zaproponuj, kto to robi. |
| Nowy serwis, baza, język, worker | Zatrzymaj; wymaga ADR amendment (`scope-change-protocol`). |
| Metryka sukcesu: liczba loadów, krawędzi, skilli | Zamień na aktywację ownera/zespołu lub decyzję ownera (PIVOT-REVIEW „Rozstrzygnięcia”). |
| Ranking zmieniany przez pola z enrichmentu | Zatrzymaj; P06–P08 nie zmieniają produkcyjnego rankingu (backlog „Zasady prowadzenia”). |
| Marketing w produkcie, hero, obietnica niegotowej funkcji | Usuń; `positioning-and-copy`. |
| Kill criterion spełniony (PRODUCT-FOCUS) | Nie buduj dalej w tym obszarze; zgłoś decyzję do właściciela. |

## Zachowaj priorytet dowodu nad kodem

„Done” znaczy „użyte” przez osobę niebudującą Guidefolda w realnym harnessie z zapisem w ledgerze (ADR-0029 reguła 3). Test na fixture Meridian zamyka R, nie P. Terminy z §13 PRD (partner do 2026-09-20, 20 realnych sesji i drugi harness do 2026-10-04) są nadrzędne wobec wygody UI.
Przy konflikcie między rozbudową a dowodem wybierz dowód: uruchomienie na realnym repo, sesja partnera, decyzja ownera zapisana w raporcie. Rozstrzygnięcia ról z [PIVOT-REVIEW](../../../docs/PIVOT-REVIEW.md) obowiązują do zmiany przez właściciela.

## Sprawdź przed zakończeniem

- Brief lub PR wskazuje `U<n>`, `P<nn>`, personę i dowód odbioru; albo zawiera wpis rozbieżności wg `scope-change-protocol`.
- Żaden element zmiany nie trafia w wiersz „What we do not do” ani w §14 PRD.
- Nowy komponent, zależność lub klucz konfiguracji ma wskazaną regułę ADR-0029, która go dopuszcza.
- Raport nie nazywa pracy „done” bez dowodu użycia; test fixture jest opisany jako R.
- Klient w opisie zmiany to platform team z wieloma harnessami, nie „użytkownik” bez kontekstu.
