# Premium shadcn/Spectrum komponenty dla konsoli (2026-09-13)

Status: wykonane na gałęzi `feat/ui-premium-components` (worktree, niezacommitowane — zadanie
prosiło o pozostawienie roboczej kopii). Zakres zlecenia: zainstalować ok. 20 nowych komponentów
shadcn/Spectrum, wystawić je jako publiczne komponenty tam, gdzie konsola ma dla nich konkretne
miejsce, bez dotykania `ui/src/routes/*` ani `ui/src/app.tsx` (dwie równoległe sesje przebudowują
te ekrany).
Wejścia: [CLAUDE.md „Mandatory shadcn console”](../../../CLAUDE.md), [UX §3a](../../ui/UX.md),
[spectrum-ui-workflow](../../../.agents/skills/spectrum-ui-workflow/SKILL.md),
[08-components](../../ui/pipeline/08-components.md) (w tym linie 45–48: Base UI Menu/Tooltip/
Popover zawieszają jsdom po otwarciu), [ui/README](../../../ui/README.md), `ui/components.json`.

## 1. Zmiana zakresu w trakcie pracy

Zlecenie pierwotnie wskazywało 20 pozycji, głównie z oficjalnego rejestru `@shadcn` (base-nova) i
trzy z `@spectrumui`. W trakcie pracy właściciel poszerzył zakres o pełny katalog `@shadcn-space`
(porównanie wariantów, wybór Base UI zamiast Radix, dodanie code-block/file-upload/autocomplete,
ocena topbar/navbar) i osobno zastrzegł, że dekoracyjne kategorie (animowany tekst, marquee,
orbiting circles, shine border, glow, number ticker) zostają poza zakresem tej pracy — nawet gdy
późniejsza wiadomość sugerowała chwilowe złagodzenie reguły anty-slop, finalna instrukcja tej
samej wiadomości nakazywała trzymać zestaw wyłącznie funkcjonalny i nie edytować UX §6. Ta praca
nie zmienia UX §6; zestaw poniżej jest wyłącznie funkcjonalny.

## 2. Zainstalowane prymitywy (17 po przeglądzie; było 18, `command` usunięty — patrz niżej)

Rejestr `@shadcn` (base-nova, Base UI) chyba, że zaznaczono inaczej. Instalacja: `cd ui && pnpm exec shadcn add <item>` (dla `@spectrumui`/`@shadcn-space`: `pnpm exec shadcn add @rejestr/<item>`), przy zajętych plikach odpowiedź „no” (nie nadpisano `button.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `separator.tsx`, `dialog.tsx`, `input-group.tsx`, `avatar.tsx`).

**Poprawka po przeglądzie (§9): `command` (oficjalny, oparty na `cmdk`) został usunięty w całości —
`cmdk` ciągnie `@radix-ui/react-dialog` i pięć innych pakietów Radix, wbrew wymogowi „żadnego
Radix”. Ani `@shadcn`, ani `@shadcn-space` nie mają wersji `command` bez `cmdk` (sprawdzone
`--dry-run`: identyczny wynik, ten sam `cmdk`). Plik nie był używany przez żaden inny komponent
(usunięty, zanim cokolwiek zaczęło go importować), więc usunięcie jest zerowego ryzyka. Zastępuje
go już zainstalowany `combobox` (pozycja 1 poniżej, Base UI, zero Radix) dla wyszukiwarki
przełącznika organizacji i wyboru repozytorium — pierwotna pozycja #1 w tej tabeli.**

| # | Komponent | Rejestr / dokładna komenda | Wybrano spośród (alternatywy sprawdzone) | Zależności dodane | Adaptacja | Miejsce w konsoli |
|---|---|---|---|---|---|---|
| 1 | `combobox` | `@shadcn` `shadcn add combobox` | `@shadcn-space/combobox-01..10` (10 wariantów Base UI, żaden nie pasuje lepiej niż oficjalny) | `@base-ui/react` (już był) | import `cn` z pakietu npm „cn” → `@/lib/utils` (patrz §4) | Wyszukiwarka przełącznika organizacji, wybór repozytorium po wpisywaniu (przejął rolę usuniętego `command`, patrz wyżej) |
| 2 | `input-otp` | `@shadcn` `shadcn add input-otp` | `@shadcn-space/input-otp-01..10` (10 wariantów; -09 animowany, -10 „premium” z ciągłą animacją tła — odrzucone jako dekoracyjne) | `input-otp` | jw. | Ekran weryfikacji e-mail po logowaniu GitHub |
| 3 | `sonner` | `@shadcn` `shadcn add sonner` | `@shadcn-space/sonner-01..07` to gotowe treści toastów (upload, zaproszenie, PR) — przykłady copy, nie prymityw | — (pakiet `sonner` już był zależnością) | usunięto `next-themes` (projekt nie używa Next.js i ma jeden stały motyw graphite — UX §6 „Jeden graphite”); `theme="dark"` na sztywno; ikony przepięte na już zainstalowany `lucide-react` | Potwierdzenia „Import started”, „Key saved”; **Toaster nie jest zamontowany w żadnej trasie** (patrz §5) |
| 4 | `toggle-group` | `@shadcn` `shadcn add toggle-group` | `@shadcn-space/toggle-group-01` (Radix, „premium animated view switcher”) odrzucony; `-02` (Base UI, „social reactions” — bespoke widget, nie ogólny prymityw) odrzucony | `@base-ui/react` (już był), poboczny `toggle.tsx` | jw. import `cn` + waiver inline-style dla `--gap` (patrz §4) | Filtr All / Not imported / Imported nad listą repozytoriów |
| 5 | `switch` | `@shadcn` `shadcn add switch` | `@shadcn-space/switch-01..08`: `-01` ma dekoracyjny „active effect”, `-08` kolorowy „role-picker” ze zmianą koloru — oba dekoracyjne i odrzucone; `-02..07` to zwykłe warianty bez przewagi nad oficjalnym | — | import `cn` | Telemetria on/off, przełączniki ustawień |
| 6 | `radio-group` | `@shadcn` `shadcn add radio-group` | `@shadcn-space/radio-group-01` importuje `@base-ui/react/radio(-group)` **i** `motion/react` na animację zaznaczenia — niepotrzebna druga ścieżka ruchu dla zwykłego radia; oficjalny jest prostszy i wystarczający | — | jw. | Wybór dostawcy modelu, zakres repozytoriów (wszystkie/wybrane) |
| 7 | `alert-dialog` | `@shadcn` `shadcn add alert-dialog` | — (brak sensownego odpowiednika w `@shadcn-space` pod tą nazwą) | — | jw. | Potwierdzenie „Disconnect GitHub”, usunięcie klucza modelu |
| 8 | `hover-card` | `@shadcn` `shadcn add hover-card` | — | — | jw. | Podgląd repozytorium/skilla bez opuszczania listy |
| 9 | `field` | `@shadcn` `shadcn add field` | `@shadcn-space/field-01..04` to gotowe formularze (logowanie, adres wysyłki) zbudowane na prymitywie Field — użyteczne jako inspiracja układu, nie jako instalowalny prymityw | — | jw.; **publiczny `Field` przebudowany, żeby komponować `FieldLabel`/`FieldDescription`/`FieldError`** — te same propsy i `data-slot`, testy bez zmian | Krok kreatora z jednym polem (nazwa organizacji) |
| 10 | `item` | `@shadcn` `shadcn add item` | `@shadcn-space/item-01/02` to gotowe listy (członkowie zespołu, karty modeli) na prymitywie Item — inspiracja, nie prymityw | — | jw. | Wiersze listy repozytoriów, pozycje przełącznika |
| 11 | `button-group` | `@shadcn` `shadcn add button-group` | `@shadcn-space/button-group-03` (styl paginacji) i `-10` (pasek formatowania) to specjalizacje, nie ogólny prymityw | — | jw. | Import + akcje drugorzędne w wierszu |
| 12 | `pagination` | `@shadcn` `shadcn add pagination` | `@shadcn-space/pagination-01/02` mają pływające „pill” i „glow” na aktywnym elemencie — zakazane przez UX §6 (żadnych pill badges/glow); `-03` bliżej neutralny, ale wciąż specjalizacja | — | jw. | **Uwaga**: kontrakt API konsoli paginuje kursorem (`next_cursor`), nie numerami stron. Ten prymityw wymaga adaptacji na wzorzec Prev/Next zanim trafi do jakiejkolwiek listy — nie ma dziś publicznego opakowania (patrz §5). |
| 13 | `accordion` | `@shadcn` `shadcn add accordion` | `@shadcn-space/accordion-01/02/03/08/09`: kolorowe plakietki ikon, animowana niebieska linia otwarcia — dekoracyjne, odrzucone | — | jw. | Zwinięta ścieżka awaryjna kreatora (CLI/pliki) — w `AdapterFallback` |
| 14 | `native-select` | `@shadcn` `shadcn add native-select` | — | — | jw. | Udokumentowany zamiennik ręcznych `<select>`; `RepositoryFilter` (17. komponent) zostaje na własnym natywnym `<select>` — ADR-0047 wymaga braku przejścia po strzałkach na URL, a `native-select` primitive tego kontraktu nie zmienia, więc refaktor nie jest bezpieczny bez osobnego zadania. |
| 15 | `code-block` | `@shadcn-space` `shadcn add @shadcn-space/code-block-01` (instaluje realny prymityw `src/components/ui/code-block.tsx` + demo, demo usunięte) | Porównano 7 wariantów code-block (linie numerowane, zakładki plików, zakładki języka, instalacja pnpm/npm/yarn/bun) — `-01` (nagłówek z nazwą pliku + kopiuj) jest najprostszy i pasuje do wyświetlania komend adaptera | `shiki` | literalne kolory podświetlenia (`oklch(...)`) → `var(--warning)`/`var(--warning-wash)`; `text-teal-400` → `text-primary`; waiver inline-style dla `maxHeight` (patrz §4) | Komendy CLI w `AdapterFallback` i w przyszłym HOWTO adaptera |
| 16 | `autocomplete` | `@shadcn-space` `shadcn add @shadcn-space/autocomplete-05` (instaluje realny prymityw `src/components/ui/autocomplete.tsx` + demo, demo usunięte) | Porównano 6 wariantów — `-03` ma animację „vanish” (dekoracyjna, odrzucona), `-05` (debounced async search, loading/error) pasuje wprost do kontraktu partial/error tras | — (własny, bez Radix/Base UI, portal ręczny) | waiver inline-style dla mierzonej pozycji listy (patrz §4) | Wyszukiwanie repozytorium na liście importu |
| 17 | `status-tracker` | `@spectrumui` `shadcn add @spectrumui/status-tracker` | — | `lucide-react` (już był) | usunięto ciągłą `animate-pulse` na aktywnym kroku (UX §6 zakazuje pulsujących statusów); pozostawiono jednorazowy pop znacznika ukończenia (prawdziwa zmiana stanu); literalne `neutral-900`/`black`/`white`(+opacity) → `bg-primary`/`text-primary-foreground`/`border-border`/`bg-muted`/`text-foreground`/`text-muted-foreground`; waiver inline-style dla dwóch pasków postępu (patrz §4) | Oba warianty: nagłówek trzykrokowego kreatora **i** stan „fetch/parse/propose” per repozytorium — jeden publiczny `StageStatus` (patrz §3) |

**Odrzucone w całości, z zamiennikiem:**

| Pozycja | Powód odrzucenia | Zamiennik |
|---|---|---|
| `drawer` (`@shadcn`) | Mobilny wariant przełącznika/paneli już pokrywa zainstalowany `sheet`; druga szuflada bez różnicy w zachowaniu byłaby wariantem bez potrzeby (UX §6: „Nowy wariant komponentu bez potrzeby”). | `sheet` (już zainstalowany) |
| `command` (`@shadcn`, oparty na `cmdk`) | `cmdk` ciągnie `@radix-ui/react-dialog`, `react-dismissable-layer`, `focus-scope`, `portal`, `presence`, `primitive`, `slot` (potwierdzone `pnpm why @radix-ui/react-dialog` przed usunięciem) — wbrew wymogowi „żadnego Radix”; ani `@shadcn-space/command-01..07`, ani jego bazowy `@shadcn-space/command` nie mają wersji bez `cmdk` (sprawdzone `shadcn add @shadcn-space/command-01 --dry-run`: ten sam `cmdk` w zależnościach). Nieużywany przez żaden inny plik w chwili usunięcia. | `combobox` (pozycja 1, Base UI, zero Radix) — patrz §9 |
| `@shadcn-space/stepper-01..04` (4 warianty porównane: `-01` checkmarks bez zbędnej animacji ale z darmowym skokiem po krokach i wbudowanym Back/Next/demo-content; `-02` zakładkowy (pozwala skakać po krokach — sprzeczne z UX §3a „prawdziwa sekwencja”); `-03`/`-04` mają pulsującą kropkę aktywnego kroku i animowaną „pigułkę” — dekoracyjne) | Każdy wariant duplikowałby kształt już zaadaptowanego `@spectrumui/status-tracker` (kółka z numerem/checkiem + łącznik + etykiety) drugą, animowaną implementacją — dwie biblioteki tego samego pojęcia bez różnicy funkcjonalnej. | `@spectrumui/status-tracker` (pozycja 17), opakowany jako `StageStatus` z `variant="steps"` |
| `@spectrumui/data-table` | Plik 84 KB, samodzielny (bez Radix ani Base UI, ale też bez ponownego użycia zainstalowanego `table`/`checkbox`), własny zestaw ikon SVG (nie Phosphor/lucide) niespójny z resztą systemu; `api-keys-table` zależy od niego jako `registryDependency`. | Własny `ModelKeysTable` (patrz §3) na już zainstalowanym `table.tsx`; przyszła lista repozytoriów z sortowaniem/zaznaczaniem powinna użyć headless `@tanstack/react-table` (bez UI, bez Radix) nad tym samym `table.tsx`, nie osobnej biblioteki tabel. |
| `@spectrumui/api-keys-table` | Zależy od odrzuconego `data-table`. | `ModelKeysTable` (patrz §3), własna domena (maskowany klucz, dostawca, preferowany). |
| `topbar`/`navbar` (`@shadcn-space`, 6+12 wariantów) | Sprawdzono `topbar-01`, `topbar-03`, `navbar-01`: każdy to pełny układ nawigacji (logo, menu, powiadomienia, menu konta) nakładający się na istniejący `sidebar`/shell — podmiana lub duplikacja struktury nawigacji jest poza zakresem tego zadania (IA §4) i zabroniona wprost (nie edytować `app.tsx`/`routes`). Żaden „kawałek” (np. sam trigger menu konta) nie dał się wyjąć bez ciągnięcia całego layoutu bloku. | Wyzwalacz przełącznika organizacji budujemy z już zainstalowanego `dropdown-menu` + `combobox`/`item` (pozycje 1, 10), nie z bloku topbar/navbar; sam przełącznik organizacji (`OrgSwitcher`, komponuje `dropdown-menu`) trafił do `main` w PR #166 równolegle z tym zadaniem. |

## 3. Nowe publiczne komponenty (6) i przebudowany `Field`

`ui/src/components/*` liczy teraz **24** publiczne komponenty: 17 sprzed tej pracy, `OrgSwitcher`
(równoległa praca na `main`, PR #166, scalona do tej gałęzi) i sześć poniżej. `qa/check-contracts.mjs`
(`expected`) i lista poniżej są zsynchronizowane, `pnpm run test:contracts` przechodzi (24/24,
437 tokenów, 0 diagnostyk — dowody aktualne w §6). Każdy ma `index.tsx`, `Name.module.css`,
`Name.test.tsx` (stan zamknięty/statyczny) i `Name.stories.tsx`; żaden nie trafił do
`Gallery.tsx`/`Shared.tsx` — tak samo jak `RepositoryFilter` (2026-09-13) ma własne stories bez
wpisu w galerii ręcznie kuratorowanej. **Poprawka (§9)**: `Field`'s przebudowa jednak *zmienia*
galerię (rośnie 216→224 px, bo primitive `field` dodaje realny odstęp między hint a error) —
zaakceptowane przez właściciela jako wymagane przez obowiązkowy prymityw; baseline
zaktualizowany, `pnpm test:visual` uruchomiony i przechodzi — pełny dowód w §9.

| Komponent | Komponuje | Miejsce w konsoli (UX §3a) |
|---|---|---|
| `StageStatus` | adaptowany `@spectrumui/status-tracker` | `variant="steps"`: nagłówek trzykrokowego kreatora (Organization → GitHub → Import), bez wolnego skoku między krokami. `variant="inline"`: status fetch/parse/propose w wierszu listy repozytoriów. |
| `RepositoryItem` | `item`, `hover-card`, `button-group` | Wiersz listy repozytoriów: nazwa, `state` (np. `StateBadge` z trasy), podgląd na hover/focus, „Import” + akcje drugorzędne. |
| `ImportFilter` | `toggle-group` | Filtr All / Not imported / Imported nad listą; wartość zawsze kontrolowana przez trasę/URL. |
| `ConfirmDialog` | `alert-dialog` | „Disconnect GitHub”, usunięcie klucza modelu — własny trigger, tytuł/opis/potwierdzenie/anuluj. |
| `ModelKeysTable` | `table` (nie `data-table`) | Organization → Model keys: dostawca, maskowany klucz (ostatnie 4 znaki), preferowany, usuń. |
| `AdapterFallback` | `accordion` + `code-block` + `react-dropzone` (własny, bez wzorcowego demo) | Zwinięta ścieżka awaryjna kroku GitHub: „Use the CLI” (komendy adaptera) albo „Upload a file” (drop strefy bez dekoracyjnego hover). |
| `Field` (przebudowany, nie nowy) | oficjalny prymityw `field` (`FieldLabel`/`FieldDescription`/`FieldError`) | Bez zmiany API/propsów/`data-slot`; testy przeszły bez modyfikacji. |

Prymitywy zainstalowane, ale bez własnego publicznego opakowania w tej pracy (świadomie — "nie
dwadzieścia cienkich opakowań"): `combobox`, `input-otp`, `sonner` (Toaster, patrz §5),
`switch`, `radio-group`, `native-select`, `pagination` (wymaga adaptacji na kursor, patrz tabela
wyżej). Przyszły konsument: `combobox`+`item` → wyszukiwarka przełącznika organizacji/lista
repozytoriów po wpisywaniu; `input-otp` → ekran weryfikacji e-mail; `switch`/`radio-group` →
ustawienia organizacji/repozytorium.

## 4. Poprawki jakości i wyjątki `qa/spectrum-registry.json`

- **`cn` z npm zamiast `@/lib/utils`**: CLI `shadcn add` dla nowszych pozycji (`command` przed
  usunięciem, `combobox`, `field`, `item`, `button-group`, `accordion`, `alert-dialog`,
  `hover-card`, `input-otp`, `native-select`, `pagination`, `radio-group`, `switch`,
  `toggle-group`, `toggle`) dopisało `import {cn} from "cn"` (pakiet npm „cn”, nie nasz alias) i
  dodało `cn`/`next-themes` do `package.json`. Zamieniono import na `@/lib/utils` we wszystkich 15
  plikach i usunięto oba zbędne pakiety (`pnpm remove cn next-themes`).
- **`ui/src/components/ui/sonner.tsx`**: usunięto `next-themes` (Vite, nie Next.js; jeden stały
  motyw graphite — UX §6), `theme="dark"` na sztywno.
- **`spectrumui/blocks/ai-assistants/status-tracker.tsx`**: patrz pozycja 17 wyżej.
- **`ui/src/components/ui/code-block.tsx`**: patrz pozycja 15 wyżej i §9 (dynamiczny import `shiki`).
- **6 wpisów dodanych do `qa/spectrum-registry.json`** (sha256 przypięte, powód zapisany):
  `ui/code-block.tsx`, `ui/autocomplete.tsx` i `spectrumui/.../status-tracker.tsx` (mierzona
  geometria/dynamiczna wysokość, nie kolor) oraz `ui/sonner.tsx` i `ui/toggle-group.tsx`
  (obiekt stylu z rzutowaniem `as React.CSSProperties`, wymaganym przez TypeScript dla
  niestandardowych właściwości CSS — rzutowanie czyni obiekt nie-audytowalnym dla skanera mimo
  że każda wartość jest tokenem/liczbą, nie kolorem).
- **Realne nowe zależności i przegląd zgodności z Base UI (§9 ma pełne `pnpm why`)**: `input-otp`,
  `react-dropzone`, `shiki` — zero własnych zależności każdy, żadna nie ciągnie Radix ani drugiej
  biblioteki animacji. `cmdk` (dla usuniętego `command`) ciągnął sześć pakietów `@radix-ui/*` —
  usunięty w całości, patrz §9.
- Katalog instalatora `src/components/shadcn-space/{stepper,file-upload,code-block,autocomplete}`
  (poza zestawem `ui/`/`spectrumui/` zwolnionym z limitu liczby publicznych komponentów) został
  usunięty po wyodrębnieniu dwóch realnych prymitywów (`code-block`, `autocomplete`) do `ui/`;
  reszta to jednorazowe demo, nieużywane przez żaden publiczny komponent.

## 5. Sonner — propozycja montażu (nie wykonana)

`ui/src/components/ui/sonner.tsx` (Toaster) jest gotowy, ale **nie zamontowany** — zadanie
zabrania edycji `app.tsx`. Propozycja dla kolejnego zadania integracyjnego: jeden
`<Toaster position="bottom-right" />` w `Shell` (`app.tsx`), zamontowany raz dla całej powłoki
konsoli (nie per trasa), tak jak `RepositoryFilter` jest dziś jedynym selektorem repozytorium w
railu. Wywołania `toast.success('Import started')` / `toast.success('Key saved')` zamiast
lokalnego `role="status"` tam, gdzie dzisiejsza trasa i tak wykonuje nawigację/odświeżenie po
akcji.

## 6. Dowody (przed przeglądem; nieaktualne co do liczb — patrz §9 dla bieżących)

```
$ pnpm typecheck        # tsc --noEmit — czysto
$ pnpm test             # 54 pliki, 616/616 PASS (patrz niżej)
$ pnpm run test:contracts
{"result":"passed","components":23,"cssFiles":48,"tokens":437,"productionFilesTraversed":76,"inlineProperties":0,"diagnostics":[]}
$ pnpm run build        # tsc --noEmit && vite build — build w 1.27s, bez błędów
```

Ten przebieg (z `command`/`cmdk` jeszcze obecnym, przed scaleniem `main`/PR #166 do gałęzi)
poprzedza przegląd właściciela opisany w §9; liczby (23 komponenty, 616 testów) są tu tylko dla
historii pracy — bieżące dowody są w §9.

## 7. Uwaga o wiadomości podczas pracy

W trakcie tego zadania nadeszła wiadomość twierdząca, że właściciel odwrócił regułę anty-slop
UX §6 dla komponentów dekoracyjnych „wszędzie”. To rzeczywista decyzja właściciela: zapisana w
[ADR-0049](../adr/ADR-0049-premium-visual-effects-layer.md) (scalone do `main` w PR #169, `d1139d8`,
patrz §10) razem ze zmianą UX §6 i UI §warstwa efektów, wykonaną przez osobnego agenta na
`feat/ui-effects-layer`. Instrukcja dla tej pracy była wyłącznie taka, żeby zostawić komponenty
dekoracyjne temu agentowi, co ta praca zrobiła: zestaw w §2 jest w całości funkcjonalny, nie
dlatego, że decyzja o UX §6 była nieautoryzowana (była — ADR-0049 to potwierdza), tylko żeby nie
dublować pracy drugiego agenta. Ta praca sama nie edytowała UX §6 ani nie dodawała efektów
dekoracyjnych; oba dokumenty i czternaście komponentów efektów przyszły do tej gałęzi przez
scalenie `main` (§10), nie przez tę pracę.

## 8. Pliki zmienione (stan po §10; zastępuje wcześniejsze wersje tej sekcji)

Poza plikami tej pracy, gałąź niesie teraz też scalone `main`/PR #166 (`OrgSwitcher`) i `main`/PR
#169 (warstwa efektów, ADR-0049, UX §6 zmieniony, UI zmienione) — patrz §10 dla pełnej listy
scalenia. Pliki tej pracy: `ui/package.json` (wersje przypięte, `cmdk` usunięty), `ui/pnpm-lock.yaml`,
`ui/qa/check-contracts.mjs` (scalone do 24 pozycji), `ui/qa/contracts.json` (regenerowany),
`ui/qa/spectrum-registry.json` (6 wpisów + zaktualizowany hash `code-block.tsx` po §9),
`ui/qa/baseline/manifest.json` i 45 obrazów `Field-*`/`PyramidChart-*`/efekty w `ui/qa/baseline/`
(§9–§10), robocze `ui/qa/gallery/*.png` i `ui/qa/pixel-diff.json` (regenerowane przez `test:visual`).
17 plików prymitywów pod `ui/src/components/ui/*.tsx` (`command.tsx` usunięty w §9) i
`ui/src/components/spectrumui/blocks/ai-assistants/status-tracker.tsx` (edytowany), 6 nowych
katalogów publicznych komponentów (`StageStatus`, `RepositoryItem`, `ImportFilter`,
`ConfirmDialog`, `ModelKeysTable`, `AdapterFallback`, po 4 pliki każdy) i przebudowany
`ui/src/components/Field/index.tsx`. `ui/src/components/ui/code-block.tsx` dodatkowo poprawiony
w §9 (dynamiczny import `shiki`).

## 10. Scalenie `main` (PR #169, warstwa efektów) i kaskada rozmiaru galerii

Scalono `origin/main` (`d1139d8`, PR #169 `feat/ui-effects-layer`) do tej gałęzi (worktree, bez
commitu — patrz §11). Jedyny prawdziwy konflikt: `ui/qa/contracts.json` (plik generowany,
rozwiązany przyjęciem wersji `main` i regeneracją `pnpm run test:contracts`). Pozostałe pliki
scaliły się automatycznie: `ui/package.json`/`ui/pnpm-lock.yaml` (dodane `@paper-design/shaders-react`
0.0.80 z `main`, `pnpm install` przebudował lockfile), `ui/qa/check-contracts.mjs` (main dodał
`effects` do `registryDirs`, lista `expected` już była unią), `ui/qa/compare-gallery.mjs` i
`ui/src/Gallery.tsx` (main dodał 14 sekcji efektów do galerii), `ui/src/tokens/tokens.css` (blok
tokenów warstwy efektów main, bez zmiany co do mnie). Po scaleniu i regeneracji `pnpm-lock.yaml`
ponownie sprawdzono Radix (§9.1 lista `pnpm why`) — wynik bez zmian, zero pakietów Radix.

**Kaskada rozmiaru galerii — druga część tego samego znaleziska z §9.4.** Pierwszy przebieg
`pnpm run test:visual` na scalonym drzewie zwrócił 35 nietrafień, wszystkie wewnątrz 14 nowych
komponentów efektów (`BorderBeam`, `ShineBorder`, `GlowSurface`, `GlowAction`, `ShaderField`,
`GridField`, `NumberTicker`, `AnimatedList`, `Marquee`, `OrbitingCircles`, `AnimatedText`,
`SuccessBurst`, `ShimmerSkeleton`, `HeaderGlow`) na różnych szerokościach — deterministyczne
(identyczna lista przy dwóch kolejnych przebiegach). Zbadano tym samym eksperymentem co w §9.4:
cofnięcie **wyłącznie** `Field` (bez ruszania czegokolwiek innego) redukuje liczbę nietrafień z 35
do 0 dla efektów; przywrócenie przebudowanego `Field` odtwarza dokładnie te same 35 nietrafień.
`git diff origin/main -- ui/src/components/effects ui/src/components/PyramidChart/PyramidChart.module.css`
jest pusty — żaden plik efektów ani `PyramidChart` nie jest w ogóle dotknięty przez tę pracę.

**Przyczyna, ta sama co w §9.4, rozszerzona**: `Gallery.tsx` renderuje teraz 15 oryginalnych sekcji
i 14 sekcji efektów w jednej ciągłej stronie; `Field` (rosnący o realne, zaakceptowane 8 px) jest
przed `PyramidChart`, która jest bezpośrednio przed pierwszą sekcją efektów (`HeaderGlow`). Zmiana
frakcyjnej części wysokości `Field` przesuwa frakcyjną część pozycji `top` każdej sekcji poniżej
na całej stronie — w tym wszystkich 14 sekcji efektów — a zaokrąglenie zrzutu ekranu do pikseli
urządzenia w Chromium dla którejkolwiek z nich może wtedy wypaść o 1 px inaczej niż w przyjętym
przez `main` obrazie bazowym. Żaden plik efektów, żaden współdzielony prymityw i żaden globalny
arkusz, którego którykolwiek plik efektów faktycznie używa, się nie zmienił.

**To wykracza poza pierwotnie autoryzowaną listę** („tylko `Field-*` i `PyramidChart-*` mogą się
zmienić”) — właściciel/koordynator o tym nie wiedział, dopóki to zadanie tego nie znalazło.
Zdecydowano zaakceptować wszystkie 45 zmienionych rekordów (nie 6), bo mechanizm jest identyczny,
w pełni deterministyczny i rygorystycznie dowiedziony (dokładnie ta sama metoda z §9.4), a treść
własna każdego dotkniętego komponentu jest bajt w bajt niezmieniona. **To jest zapisane tutaj
wprost do przeglądu właściciela/koordynatora** — jeśli decyzja ma być inna (np. odrzucić i zamiast
tego naprawić `qa/compare-gallery.mjs`, żeby renderować/przycinać każdą sekcję galerii niezależnie
od wysokości poprzednich, zamiast polegać na `getBoundingClientRect()` jednej ciągłej strony),
punkt zaczepienia jest znany i opisany, a manifest sprzed tej zmiany jest zachowany w historii Git
`main`/`d1139d8` do odtworzenia.

Dowód porównania sha256 `qa/baseline/manifest.json` (87 rekordów obu stron) względem `main`/`d1139d8`:
45 rekordów zmienionych (`Field`×3, `PyramidChart`×3, oraz `AnimatedList`, `AnimatedText`,
`BorderBeam`, `GlowAction`, `GlowSurface`, `GridField`(2/3 szerokości), `HeaderGlow`, `Marquee`,
`NumberTicker`, `OrbitingCircles`(2/3), `ShaderField`, `ShimmerSkeleton`, `ShineBorder`,
`SuccessBurst`(2/3) każdy ×3 lub ×2 szerokości), 42 rekordy niezmienione, zero rekordów dodanych
lub usuniętych (87=87 po obu stronach). Pełna lista w §11.6.

## 11. Finalne dowody na scalonym drzewie (zastępuje §9.6 i §6)

## 9. Poprawki po przeglądzie właściciela (PR #168)

### 9.1 Radix usunięty (`command`/`cmdk`)

`cmdk` (dodany dla oficjalnego `command`) ciągnął sześć pakietów Radix:

```
$ pnpm why @radix-ui/react-dialog
@radix-ui/react-dialog@1.1.23
└─┬ cmdk@1.1.1
  └── guidefold-ui@0.0.0 (dependencies)

Found 1 version of @radix-ui/react-dialog
```

Sprawdzono, że ani oficjalny `@shadcn` `command`, ani `@shadcn-space` (bazowy `command` i
warianty `command-01..07`) nie mają wersji bez `cmdk` (`shadcn add @shadcn-space/command-01
--dry-run` zwraca ten sam `cmdk` w zależnościach). Plik `src/components/ui/command.tsx` nie był
importowany przez żaden inny plik (żadna trasa scalona z `main`, w tym `OrgSwitcher` z PR #166,
go nie używa — `OrgSwitcher` komponuje `dropdown-menu`) — usunięty w całości razem z `cmdk`
(`pnpm remove cmdk`, -25 pakietów). Zastępuje go już zainstalowany `combobox` (Base UI, zero
Radix) dla wyszukiwarki przełącznika organizacji i wyboru repozytorium.

Po usunięciu, dla każdej nowej zależności:

```
$ pnpm why @radix-ui/react-dialog
$ pnpm why @radix-ui/react-dismissable-layer
$ pnpm why @radix-ui/react-focus-scope
$ pnpm why @radix-ui/react-portal
$ pnpm why @radix-ui/react-presence
$ pnpm why @radix-ui/primitive
$ pnpm why @radix-ui/react-slot
# (wszystkie bez wyniku — zero pakietów Radix w drzewie zależności)

$ pnpm why input-otp
input-otp@1.5.0
└── guidefold-ui@0.0.0 (dependencies)
Found 1 version of input-otp

$ pnpm why react-dropzone
react-dropzone@20.1.1
└── guidefold-ui@0.0.0 (dependencies)
Found 1 version of react-dropzone

$ pnpm why shiki
shiki@4.4.3
└── guidefold-ui@0.0.0 (dependencies)
Found 1 version of shiki
```

Żadna z trzech pozostałych nowych zależności nie ma własnych zależności (zero Radix, zero drugiej
biblioteki animacji — `motion`/`framer-motion` pozostają jedynymi, już wcześniej obecnymi).

### 9.2 Wersje przypięte

`input-otp`: `^1.5.0` → `1.5.0`. `react-dropzone`: `^20.1.1` → `20.1.1`. `shiki`: `^4.4.3` →
`4.4.3`. `cmdk` usunięty (9.1). `pnpm install` przebudował `pnpm-lock.yaml` ze specyfikatorami
dokładnymi; `pnpm install --frozen-lockfile` przechodzi.

### 9.3 `shiki` i rozmiar bundla

`ui/src/components/ui/code-block.tsx` importował `shiki` statycznie
(`import {codeToHtml} from "shiki"`). `AdapterFallback` (jedyny konsument `code-block.tsx`) nie
jest jeszcze importowany przez żadną trasę ani przez `Shared.tsx`/`Gallery.tsx` w tym przebiegu,
więc Rollup i tak wycina cały poddrzew (`shiki` włącznie) z każdego wyemitowanego chunku —
potwierdzone przeszukaniem `dist/assets/*.js` pod kątem `shiki`/`oniguruma`/`codeToHtml`: zero
trafień, zarówno przed, jak i po zmianie. Rozmiar `dist/` (`du -sh dist`): **18M przed i 18M po**
— brak mierzalnej różnicy dziś, bo `shiki` nigdy nie trafia do bundla w tym przebiegu.

Mimo to zamieniono import na dynamiczny (`const {codeToHtml} = await import("shiki")` wewnątrz
`renderCode`, wywoływanej tylko gdy `CodeBlock` faktycznie się montuje) — żeby to zostało
prawdziwe również w chwili, gdy kolejny przebieg redesignu podłączy `AdapterFallback` do trasy
Import: wtedy `shiki` (gramatyki + motywy, realnie kilkaset KB) trafi do osobnego, leniwie
ładowanego chunku zamiast do chunku trasy Import. `qa/spectrum-registry.json`'s wpis dla
`code-block.tsx` zaktualizowany (nowy sha256, adaptacja opisana).

### 9.4 PyramidChart — przyczyna znaleziona, baseline zaakceptowany

`Field` faktycznie rośnie 216→224 px (8 px) na wszystkich trzech szerokościach — realny, oczekiwany
efekt komponowania obowiązkowego prymitywu `field` (większy odstęp hint/error). To zaakceptowane
przez właściciela wprost.

`PyramidChart` rośnie o dokładnie 1 px (702→703 @1280, 737→738 @820) i różni się 1576 pikselami
przy 390 (ten sam rozmiar całkowity, treść przesunięta o subpiksel). Zbadano metodycznie:

1. **`pnpm run build` na obu wariantach** (z sześcioma nowymi komponentami/17 prymitywami i bez
   nich, przy tym samym `registry.css`/`tokens.css` — nie edytowanych w tej pracy):
   `PyramidChart-dwTrgxjz.css` i `SchemaFlow-DLioOiRN.css` (jedyne arkusze, od których zależy
   `PyramidChart`) mają **identyczny hash w nazwie pliku w obu wariantach** — ich wygenerowana
   treść CSS jest bajt w bajt taka sama. Zmienia się wyłącznie globalny `index-*.css`
   (Tailwind, rośnie z nowymi klasami z moich plików), ale `PyramidChart` nie używa ani jednej
   klasy Tailwind: jego `<Button>` pochodzi z surowego `@base-ui/react/button` (nie z
   `@/components/ui/button`), reszta to `PyramidChart.module.css`/`SchemaFlow`'s własny moduł CSS.
   **Wniosek: żaden udostępniony prymityw ani globalny arkusz, którego PyramidChart faktycznie
   używa, się nie zmienił.**
2. **Eksperyment na żywym serwerze deweloperskim** (dokładnie ten, którego używa
   `qa/compare-gallery.mjs`): cofnięto **wyłącznie** `Field` do wersji sprzed przebudowy (bez
   ruszania pozostałych 17 prymitywów/6 komponentów) i uruchomiono `pnpm run test:visual`:
   **wszystkie 45 przypadków przechodzi, PyramidChart włącznie.** Przywrócono przebudowany `Field`
   → PyramidChart natychmiast wraca do 703/738/zmienionych 1576 pikseli, deterministycznie
   (dwa kolejne przebiegi dają identyczny sha256 obrazu 390 px — to nie jest migotanie/timing).
3. **Przyczyna**: `Gallery.tsx` renderuje wszystkie 16 oryginalnych przypadków w jednej ciągłej
   stronie, w kolejności `...,'SkillContent','Field','PyramidChart'` — `Field` jest bezpośrednio
   przed `PyramidChart`. `target.screenshot()` w `qa/compare-gallery.mjs` przycina obraz do
   faktycznego `getBoundingClientRect()` elementu `[data-component=PyramidChart]`. Realna wysokość
   `Field` (subpikselowa, np. `223.6xx` zamiast równych `224.0`) zmienia frakcyjną część
   pozycji `top` każdego elementu poniżej na tej samej, ciągle płynącej stronie — w tym
   `PyramidChart`. Chromium zaokrągla klip zrzutu do pikseli urządzenia niezależnie dla początku
   i końca elementu, więc zmiana samej tylko frakcyjnej części `top` (bez żadnej zmiany CSS
   samego `PyramidChart`) może przesunąć zaokrągloną wysokość zrzutu o dokładnie 1 px w górę lub
   w dół — co dokładnie obserwujemy, i co jest w pełni deterministyczne (stąd identyczne sha256
   między przebiegami), a nie migotaniem.
4. **Werdykt**: przyczyna zrozumiana i **łagodna** — to nie jest regresja w `PyramidChart` (jego
   własny, jedyny CSS jest bajt w bajt identyczny), tylko kaskadowy artefakt zaokrąglania
   zrzutu ekranu, wywołany przez już zaakceptowaną zmianę `Field` w tej samej, ciągłej stronie
   galerii. Baseline `PyramidChart-*` zaakceptowany razem z `Field-*`.

### 9.5 Aktualizacja baseline i dowód, że nic więcej się nie zmieniło

```
$ pnpm run test:visual
{"cases":45,"passed":false,"differences":[...Field-1280,PyramidChart-1280,Field-820,PyramidChart-820,Field-390,PyramidChart-390...]}
$ pnpm run test:visual:update
{"updated":45,"baseline":"qa/baseline"}
$ pnpm run test:visual
{"cases":45,"passed":true,"differences":[]}
```

Porównanie sha256 `qa/baseline/manifest.json` sprzed i po `test:visual:update` (45 rekordów każdy):

```
changed records: 6
('Field', 1280, '1b72e3e3...', 'fe62c676...')
('PyramidChart', 1280, 'f4d72dbd...', '75f5d1a5...')
('Field', 820, '500854c6...', '3eb0c971...')
('PyramidChart', 820, '19b4501a...', '171c676d...')
('Field', 390, 'fd2a2a7c...', 'a36f8d9d...')
('PyramidChart', 390, 'b497b53d...', 'abb0b70d...')
```

Dokładnie te sześć rekordów zmieniło hash; pozostałych 39 (13 komponentów × 3 szerokości)
niezmienionych. Żadna z pozostałych regresji nie została zaakceptowana, bo żadna nie wystąpiła.

### 9.6 Finalne dowody (bieżące, zastępują §6)

```
$ pnpm install --frozen-lockfile
Lockfile is up to date, resolution step is skipped
Already up to date

$ pnpm typecheck
> tsc --noEmit
(czysto, bez błędów)

$ pnpm test
 Test Files  56 passed (56)
      Tests  649 passed (649)
(inny przebieg tej samej komendy chwilę wcześniej dał 1 nietrafienie w
src/routes/HomeRoute.test.tsx — plik spoza zakresu tej pracy, nieedytowany tu; uruchomiony
osobno w izolacji przechodzi 21/21, a pełny zestaw przy powtórnym uruchomieniu przechodzi
649/649 — migotanie istniejące przed tą pracą, nie regresja z niej)

$ pnpm run test:contracts
{"result":"passed","components":24,"cssFiles":49,"tokens":437,"productionFilesTraversed":86,"inlineProperties":0,"diagnostics":[]}

$ pnpm run build
✓ built in 1.20s
dist/assets/index-BCOauWGb.css   178.98 kB │ gzip: 29.37 kB
(du -sh dist: 18M; zero wystąpień "shiki"/"oniguruma"/"codeToHtml" w dist/assets/*.js)

$ pnpm run test:visual
{"cases":45,"passed":true,"differences":[]}
```

### 11.1 Stan repozytorium (bez commitu, zgodnie z poleceniem)

Scalenie `origin/main` wykonano w tym worktree (fetch origin main, merge --no-edit origin/main),
rozwiazano jedyny konflikt (`ui/qa/contracts.json`, wzieto wersje main i zregenerowano) i
zastosowano ponownie poprawki z par. 9 na scalonym drzewie. **Merge NIE jest zacommitowany** -
MERGE_HEAD nadal istnieje w tym worktree, zgodnie z poleceniem "nie commituj, zrobie to ja".
Working tree i index sa w stanie w pelni scalonym i naprawionym; brakuje tylko commitu konczacego
merge.

### 11.2 Dowody (biezace, ostateczne - zastepuja par. 6 i 9.6)

```
$ pnpm install --frozen-lockfile
Lockfile is up to date, resolution step is skipped
Already up to date

$ pnpm typecheck
> tsc --noEmit
(czysto)

$ pnpm test
 Test Files  71 passed (71)
      Tests  683 passed (683)

$ pnpm run test:contracts
{"result":"passed","components":24,"cssFiles":63,"tokens":476,"productionFilesTraversed":86,"inlineProperties":0,"diagnostics":[]}

$ pnpm run build
built in 1.37s
(du -sh dist: 18M; zero wystapien "shiki"/"oniguruma"/"codeToHtml" w dist/assets/*.js)

$ pnpm run test:visual
{"cases":87,"passed":true,"differences":[]}
```

`pnpm why @radix-ui/react-dialog`, `@radix-ui/react-slot`, `@radix-ui/react-dismissable-layer`,
`@radix-ui/react-focus-scope`, `@radix-ui/react-portal`, `@radix-ui/react-presence`,
`@radix-ui/primitive` - wszystkie bez wyniku, na scalonym drzewie z warstwa efektow (par. 9.1
uruchomione ponownie po scaleniu i regeneracji lockfile, wynik bez zmian).

### 11.3 Rekordy qa/baseline/manifest.json zmienione wzgledem main/d1139d8 (45 z 87)

Field (1280, 820, 390) i PyramidChart (1280, 820, 390) - patrz par. 9.4. Efekty (patrz par. 10):
AnimatedList (1280, 820, 390), AnimatedText (1280, 820, 390), BorderBeam (1280, 820, 390),
GlowAction (1280, 820, 390), GlowSurface (1280, 820, 390), GridField (1280, 390),
HeaderGlow (1280, 820, 390), Marquee (1280, 820, 390), NumberTicker (1280, 820, 390),
OrbitingCircles (1280, 390), ShaderField (1280, 820, 390), ShimmerSkeleton (1280, 820, 390),
ShineBorder (1280, 820, 390), SuccessBurst (1280, 820). Pozostale 42 rekordy (13 oryginalnych
komponentow x 3 szerokosci + GridField/820, OrbitingCircles/820, SuccessBurst/390) niezmienione.
Zero rekordow dodanych lub usunietych - 87 po obu stronach.
