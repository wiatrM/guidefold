---
name: domain-glossary
description: Canonical Guidefold vocabulary (skill, node, URN, revision, proposal, snapshot, package, lifecycle states, pyramid axes, SEARCH/USE, ledger, unknown) with the document that defines each term. Use when naming things in code, UI strings, docs or tests, or when two documents seem to disagree.
---

# Słownik domeny Guidefold

Status: aktywna reguła repozytorium. Data: 2026-09-06.
Cel: jedno słowo, jedno znaczenie, jeden dokument źródłowy; nazwy w kodzie i UI nie dryfują.
Źródło: [PRODUCT-PIVOT §2–§3, §8](../../../docs/PRODUCT-PIVOT.md), [CONVENTIONS §1–§4](../../../docs/CONVENTIONS.md), [SEARCH-USE-TELEMETRY §1, §3](../../../docs/SEARCH-USE-TELEMETRY.md), [HARNESS-SERVICE-CONTRACT](../../../docs/HARNESS-SERVICE-CONTRACT.md). Decyzja: [ADR-0031](../../../docs/adr/ADR-0031-monorepo-to-managed-skill-library.md).
Indeks: [AGENTS.md](../../../AGENTS.md). Zakres zastępowania: brak; skill jest instrukcją odczytu i wykonania, nie drugim PRD.

## Używaj tych pojęć

| Pojęcie | Definicja | Dokument |
|---|---|---|
| Skill | Katalog z `SKILL.md` (frontmatter + body) leżący obok kodu, którym rządzi. | CONVENTIONS §2 |
| Node / scope | Węzeł z `guidefold.yaml`, kropkowana ścieżka (`atlas.identity.turnstile`), root to `_root`; określa, gdzie skill obowiązuje i kto go ocenia. | CONVENTIONS §1, §3 |
| Publisher | Wartość `publisher` z `guidefold.yaml`; prefiks URN i opisu root. | CONVENTIONS §3 |
| URN | `urn:skill:<publisher>:<node>:<skill-name>`, wyprowadzany, nigdy ręczny. | CONVENTIONS §3 |
| Karta zakresu | Generowany `AGENTS.md` węzła, ≤80 linii, digesty bez procedur. | CONVENTIONS §9 |
| Rewizja | Niezmienna treść skilla z digestem; UI pokazuje konkretną rewizję, nie „najnowszą”. | PRODUCT-PIVOT §3, §7 |
| Źródło / source_revision | Plik i commit, z którego pochodzi instrukcja; oś Źródło piramidy. | PRODUCT-PIVOT §2, §4 |
| Propozycja | Kandydat wydobyty lub skonsolidowany, ze źródłami i diffem; decyzję podejmuje owner, tekst zatwierdza review w Git. | PRODUCT-PIVOT §3, §5 |
| Snapshot | Zwalidowany, atomowo aktywowany zestaw opublikowanych rewizji; nieudany import go nie zmienia. | PRODUCT-PIVOT §3, §8 |
| Pakiet | SKILL.md plus wymagane zasoby o nazwanym digeście; USE pobiera pakiet, nie wykonuje skryptów. | PRODUCT-PIVOT §8 |
| Stany propozycji | draft → approved_for_export → awaiting_git → published; oraz needs_review i archived. | PRODUCT-PIVOT §3 |
| Trzy osie piramidy | Źródło (skąd), Zakres i owner (gdzie, kto ocenia), Wiedza (abstract / task / atomic). | PRODUCT-PIVOT §2 |
| SEARCH | Zwraca karty opublikowanych skilli po filtrze uprawnień dla zadania/repo/scope; domyślnie 4 karty. | SEARCH-USE-TELEMETRY §1 |
| USE | Pobiera dokładną rewizję i wymagane zasoby po weryfikacji; 409 przy zmianie snapshotu między SEARCH a USE. | PRODUCT-PIVOT §8 |
| Ledger | Zapis zdarzeń SEARCH/USE z jawnymi powiązaniami, nie najbliższym timestampem. | SEARCH-USE-TELEMETRY §3–§4 |
| Unknown | Brak obserwacji; pełnoprawny wynik, nie zero i nie porażka. | SEARCH-USE-TELEMETRY §3 |

## Trzymaj się rozróżnień

- Eksport ≠ publikacja ≠ pobranie ≠ użycie. Kolejno: `approved_for_export` → `published` po merge/validate/sync → `download_verified` → `context_loaded` → outcome. Żaden krok nie dowodzi następnego (PRODUCT-PIVOT §8, DOCUMENTATION-RULES).
- Podobieństwo treści nie tworzy `requires`; zależność jest jawną decyzją (PRODUCT-PIVOT §2).
- Warstwa abstract/task/atomic nie wynika z głębokości katalogu ani z osi Źródło; source layer/status nie określa Knowledge layer ani stanu publikacji ([UX §2](../../../docs/ui/UX.md)).
- CODEOWNERS opisuje odpowiedzialność za źródło; uprawnienia w hosted API nadaje owner/member organizacji, nie plik w repo.
- Rejestr Google Agent Registry jest artefaktem builda, Git jest źródłem prawdy ([ADR-0001](../../../docs/adr/ADR-0001-git-source-of-truth-registry-artifact.md)).

## Sprawdź przed zakończeniem

1. Nowa nazwa w kodzie/UI/teście odpowiada wierszowi tabeli albo dopisujesz wiersz z dokumentem źródłowym.
2. String UI nie miesza stanów: `Published` tylko z dowodu API, `Exported` dla eksportu.
3. Metryka bez mianownika i źródła pozostaje `Unknown`, nie `0`.
4. Nie wprowadzasz synonimu istniejącego pojęcia (np. „katalog” zamiast „snapshot”).
