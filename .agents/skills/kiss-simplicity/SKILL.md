---
name: kiss-simplicity
description: Keep every Guidefold change as simple as the requirement allows. Use when designing a function, module, config key or service boundary, and when reviewing a PR that adds machinery. Not a licence to skip required states, tests or contracts.
---

# KISS: najprostsze działające rozwiązanie

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: każdy fragment kodu i konfiguracji ma być zrozumiały bez wyjaśnień i nie większy niż wymaganie, które realizuje.
Źródło: [PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md) (sekcja "Kiedy wydzielić mikroserwis"), [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md) (reguła 7, "KISS review before merge"), [UX](../../../docs/ui/UX.md) §6.3. Decyzja: [ADR-0032](../../../docs/adr/ADR-0032-engineering-principles-and-hexagonal-architecture.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Wybierz najprostszy wariant, który spełnia wymaganie

Zanim napiszesz kod, nazwij wymaganie jednym zdaniem z identyfikatorem (U1–U11, P01–P15 lub zlecenie użytkownika). Rozwiązanie ma spełniać to zdanie i nic więcej.

| Sytuacja | Prosty wariant | Wariant, który odrzucasz bez uzasadnienia |
|---|---|---|
| Nowa komenda CLI | funkcja w `skills/guidefold/scripts/guidefold`, stdlib + PyYAML | pakiet, plugin system, zależność |
| Nowy use case backendu | funkcja w istniejącym module Go | osobna usługa, kolejka, Redis ([PIVOT-ARCHITECTURE](../../../docs/PIVOT-ARCHITECTURE.md): "Use case nie jest automatycznie granicą usługi") |
| Różnica preferencji użytkowników | jedna decyzja projektowa | toggle w UI ([UX](../../../docs/ui/UX.md) §6.3: konfigurowalność zamiast decyzji) |
| Powtarzalna transformacja danych | jawna funkcja z typami | metaprogramowanie, refleksja, generyk bez drugiego użycia |
| Konfiguracja | stała w kodzie z komentarzem skąd | nowy klucz w `guidefold.yaml` lub env |

## Zastosuj test pięciu minut

Nowy inżynier czytający zmianę bez autora ma zrozumieć w pięć minut: co robi, gdzie jest wejście, gdzie wyjście i co się dzieje przy błędzie. Jeśli potrzebny jest komentarz "to działa, bo…", uprość kod zamiast dopisywać komentarz. Funkcja, której nie da się nazwać jednym czasownikiem z dopełnieniem, robi za dużo.

## Licz budżet złożoności w PR

PR, który dodaje komponent, zależność, klucz konfiguracji, warstwę pośrednią lub proces, wskazuje regułę z [ADR-0029](../../../docs/adr/ADR-0029-product-focus-hard-rules.md), która na to pozwala; reviewer odrzuca domyślnie. Zamiast "może się przydać" zapisz pytanie w backlogu (zob. `yagni-scope-control`). Warstwa pośrednia ma sens tylko wtedy, gdy oddziela domenę od adaptera (zob. `hexagonal-architecture`); warstwa dla samej symetrii jest złożonością bez pracy.

## Przykład z repo

`Registry` i `LocalRegistry` w CLI to dwie klasy z tym samym zestawem metod wybierane raz przy starcie. Prosty wariant. Rejestr pluginów ładowany przez `importlib` z katalogu byłby wariantem złożonym bez wymagania; ADR-0003 przewiduje wymianę na MCP/ARD, i to wystarczy jako druga implementacja tej samej klasy.

## Sprawdź przed zakończeniem

- Czy wymaganie realizowane przez zmianę jest zapisane jednym zdaniem z identyfikatorem w opisie PR?
- Czy da się usunąć jedną klasę, plik, parametr lub klucz konfiguracji bez utraty zachowania? Jeśli tak, usuń.
- Czy nowa zależność, proces lub klucz ma wskazaną regułę ADR-0029, która na niego pozwala?
- Czy żadna funkcja nie wymaga komentarza tłumaczącego mechanizm zamiast intencji?
- Czy `python3 -m py_compile skills/guidefold/scripts/guidefold` (dla CLI) albo `go vet ./...` w `services/search` (dla Go) przechodzi bez ostrzeżeń o nieużywanym kodzie?
