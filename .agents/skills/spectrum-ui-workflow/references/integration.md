# Integracja Spectrum w Guidefold

Status: instrukcja techniczna, 2026-09-09. Właściciel reguły: [SKILL.md](../SKILL.md).
Czytaj przy konfiguracji MCP, instalacji/aktualizacji itemów i diagnozie zgodności.

## Lokalizacja i narzędzia

- Repo jest monorepo; frontend ma własne package.json i components.json w ui/.
- Sprawdź cwd serwera Vite i aktywny worktree. Nie instaluj do innego checkoutu niż edytowany UI.
- Konfiguracja projektu Claude Code to .mcp.json; konfiguracja w ui/.mcp.json działa dla sesji uruchomionej w ui/.
- Wybieraj lokalne, przypięte pnpm exec shadcn i pnpm exec spectrumui-mcp. Wersje są zapisane w ui/package.json.
- Oficjalny bootstrap: npx shadcn@latest mcp init --client claude. Przed uruchomieniem sprawdź i zachowaj istniejącą konfigurację.
- Po zapisie potrzebny jest restart/reconnect klienta. Zapis pliku nie oznacza, że narzędzie pojawiło się w bieżącej sesji.
- Nie zmieniaj globalnego Codex/Claude Desktop ani innych klientów tylko dlatego, że dokumentacja pokazuje ich przykłady.

## Odkrywanie i instalacja

Spectrum: https://ui.spectrumhq.in/docs/mcp
Rejestr: https://ui.spectrumhq.in/r/{name}.json
CLI shadcn: https://ui.shadcn.com/docs/cli
Vite: https://ui.shadcn.com/docs/installation/vite

Uruchamiaj z ui/:
```sh
pnpm exec shadcn search @spectrumui -q beam
pnpm exec shadcn view @spectrumui/beam-search
pnpm exec shadcn add @spectrumui/beam-search --dry-run
pnpm exec shadcn add @spectrumui/beam-search
```

MCP: list_components i list_categories ustalają katalog, search_components szuka, get_component zwraca metadata.
install_component przyjmuje project_dir: podaj absolutną ścieżkę aktywnego ui/, nie root monorepo.
Przed instalacją sprawdź jego aktualną implementację: wersja 0.1.1 używa bunx/npx, nawet w projekcie pnpm.
Gdy brak tych launcherów, zainstaluj item przez przypięty pnpm exec shadcn; nie ogłaszaj sukcesu install_component.
Cały katalog jest dostępny przez namespace; nie twórz ręcznie utrzymywanej kopii setek nazw.

## Pułapki rzeczywistego rejestru

- beam-search to pole wyszukiwania, beam-card to karta; oba używają border-beam i use-surface-theme.
- Niektóre itemy mają jawne target components/spectrumui/... i nie respektują niestandardowego aliasu components.
- Utrzymuj alias @/* → src/* w TypeScript i Vite. Docelowe importy zweryfikuj po dry-run.
- Zachowaj rozdział: src/components/spectrumui i src/components/ui to źródła registry; 15 istniejących katalogów to publiczne API produktu.
- Tailwind utilities i theme są w osobnym wejściu bez Preflight. Nie zamieniaj global.css na standardowy reset z tutoriala.
- Tokeny shadcn mapuj na istniejące tokeny produktu; nie kopiuj całego nowego systemu barw.
- use-surface-theme wykrywa klasę dark/light i OS. Guidefold ma stały ciemny motyw: jawne theme=dark i kontener dark, bez nowego przełącznika.
- RSC, next/image, next/link, next/navigation oraz server actions wymagają osobnej oceny; nie gwarantuj zgodności wszystkich itemów z Vite.
- Klasy utility nie gwarantują czytelności: sprawdź kaskadę z globalnymi input/button/h3 i portalami.
- BeamSearch upstream wymaga audytu etykiety pola, celu Clear i reduced-motion; popraw rzeczywistą dostępność przed użyciem.
- Efekty wizualne bez realnej akcji umieszczaj tylko w podpisanym podglądzie developerskim.

## Kontrakt weryfikacji

1. Dry-run wskazuje dokładne pliki i pakiety; nie ma niezamierzonego overwrite.
2. TypeScript/Vite rozwiązuje importy, a CSS generator widzi źródła nowych itemów.
3. Test wpisywania/clear/submit lub innej istotnej akcji; klawiatura, focus i axe.
4. Reduced-motion i pause respektowane przez bibliotekę, nie tylko przez wrapper.
5. Zrzut desktop/mobile oraz kontrola braku wpływu na istniejące widoki.
6. Notice upstream i datowana ewidencja źródła, wersji, adaptacji i testów.
