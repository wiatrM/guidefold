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

## 2. Zainstalowane prymitywy (18, priorytet i źródło)

Rejestr `@shadcn` (base-nova, Base UI) chyba, że zaznaczono inaczej. Instalacja: `cd ui && pnpm exec shadcn add <item>` (dla `@spectrumui`/`@shadcn-space`: `pnpm exec shadcn add @rejestr/<item>`), przy zajętych plikach odpowiedź „no” (nie nadpisano `button.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `separator.tsx`, `dialog.tsx`, `input-group.tsx`, `avatar.tsx`).

| # | Komponent | Rejestr / dokładna komenda | Wybrano spośród (alternatywy sprawdzone) | Zależności dodane | Adaptacja | Miejsce w konsoli |
|---|---|---|---|---|---|---|
| 1 | `command` | `@shadcn` `shadcn add command` | `@shadcn-space/command-01..07` (7 wariantów, wszystkie bez Radix, ale to zestaw przykładów użycia własnego prymitywu, nie prymityw) | `cmdk` | import `cn` z pakietu npm „cn” → `@/lib/utils` (patrz §4) | Wyszukiwarka przełącznika organizacji, wybór repozytorium |
| 2 | `combobox` | `@shadcn` `shadcn add combobox` | `@shadcn-space/combobox-01..10` (10 wariantów Base UI, żaden nie pasuje lepiej niż oficjalny) | `@base-ui/react` (już był) | jw. | UX §3a mówi wprost, że wybór konta GitHub (instalacji) to zwykła lista rozwijana, nie combobox — prymityw zainstalowany na polecenie, ale przyszły konsument to `native-select`, nie ten. Combobox zostaje dla „repozytoria po wpisywaniu”, jeśli `autocomplete` nie wystarczy. |
| 3 | `input-otp` | `@shadcn` `shadcn add input-otp` | `@shadcn-space/input-otp-01..10` (10 wariantów; -09 animowany, -10 „premium” z ciągłą animacją tła — odrzucone jako dekoracyjne) | `input-otp` | jw. | Ekran weryfikacji e-mail po logowaniu GitHub |
| 4 | `sonner` | `@shadcn` `shadcn add sonner` | `@shadcn-space/sonner-01..07` to gotowe treści toastów (upload, zaproszenie, PR) — przykłady copy, nie prymityw | — (pakiet `sonner` już był zależnością) | usunięto `next-themes` (projekt nie używa Next.js i ma jeden stały motyw graphite — UX §6 „Jeden graphite”); `theme="dark"` na sztywno; ikony przepięte na już zainstalowany `lucide-react` | Potwierdzenia „Import started”, „Key saved”; **Toaster nie jest zamontowany w żadnej trasie** (patrz §5) |
| 5 | `toggle-group` | `@shadcn` `shadcn add toggle-group` | `@shadcn-space/toggle-group-01` (Radix, „premium animated view switcher”) odrzucony; `-02` (Base UI, „social reactions” — bespoke widget, nie ogólny prymityw) odrzucony | `@base-ui/react` (już był), poboczny `toggle.tsx` | jw. import `cn` + waiver inline-style dla `--gap` (patrz §4) | Filtr All / Not imported / Imported nad listą repozytoriów |
| 6 | `switch` | `@shadcn` `shadcn add switch` | `@shadcn-space/switch-01..08`: `-01` ma dekoracyjny „active effect”, `-08` kolorowy „role-picker” ze zmianą koloru — oba dekoracyjne i odrzucone; `-02..07` to zwykłe warianty bez przewagi nad oficjalnym | — | import `cn` | Telemetria on/off, przełączniki ustawień |
| 7 | `radio-group` | `@shadcn` `shadcn add radio-group` | `@shadcn-space/radio-group-01` importuje `@base-ui/react/radio(-group)` **i** `motion/react` na animację zaznaczenia — niepotrzebna druga ścieżka ruchu dla zwykłego radia; oficjalny jest prostszy i wystarczający | — | jw. | Wybór dostawcy modelu, zakres repozytoriów (wszystkie/wybrane) |
| 8 | `alert-dialog` | `@shadcn` `shadcn add alert-dialog` | — (brak sensownego odpowiednika w `@shadcn-space` pod tą nazwą) | — | jw. | Potwierdzenie „Disconnect GitHub”, usunięcie klucza modelu |
| 9 | `hover-card` | `@shadcn` `shadcn add hover-card` | — | — | jw. | Podgląd repozytorium/skilla bez opuszczania listy |
| 10 | `field` | `@shadcn` `shadcn add field` | `@shadcn-space/field-01..04` to gotowe formularze (logowanie, adres wysyłki) zbudowane na prymitywie Field — użyteczne jako inspiracja układu, nie jako instalowalny prymityw | — | jw.; **publiczny `Field` przebudowany, żeby komponować `FieldLabel`/`FieldDescription`/`FieldError`** — te same propsy i `data-slot`, testy bez zmian | Krok kreatora z jednym polem (nazwa organizacji) |
| 11 | `item` | `@shadcn` `shadcn add item` | `@shadcn-space/item-01/02` to gotowe listy (członkowie zespołu, karty modeli) na prymitywie Item — inspiracja, nie prymityw | — | jw. | Wiersze listy repozytoriów, pozycje przełącznika |
| 12 | `button-group` | `@shadcn` `shadcn add button-group` | `@shadcn-space/button-group-03` (styl paginacji) i `-10` (pasek formatowania) to specjalizacje, nie ogólny prymityw | — | jw. | Import + akcje drugorzędne w wierszu |
| 13 | `pagination` | `@shadcn` `shadcn add pagination` | `@shadcn-space/pagination-01/02` mają pływające „pill” i „glow” na aktywnym elemencie — zakazane przez UX §6 (żadnych pill badges/glow); `-03` bliżej neutralny, ale wciąż specjalizacja | — | jw. | **Uwaga**: kontrakt API konsoli paginuje kursorem (`next_cursor`), nie numerami stron. Ten prymityw wymaga adaptacji na wzorzec Prev/Next zanim trafi do jakiejkolwiek listy — nie ma dziś publicznego opakowania (patrz §5). |
| 14 | `accordion` | `@shadcn` `shadcn add accordion` | `@shadcn-space/accordion-01/02/03/08/09`: kolorowe plakietki ikon, animowana niebieska linia otwarcia — dekoracyjne, odrzucone | — | jw. | Zwinięta ścieżka awaryjna kreatora (CLI/pliki) — w `AdapterFallback` |
| 15 | `native-select` | `@shadcn` `shadcn add native-select` | — | — | jw. | Udokumentowany zamiennik ręcznych `<select>`; `RepositoryFilter` (17. komponent) zostaje na własnym natywnym `<select>` — ADR-0047 wymaga braku przejścia po strzałkach na URL, a `native-select` primitive tego kontraktu nie zmienia, więc refaktor nie jest bezpieczny bez osobnego zadania. |
| 16 | `code-block` | `@shadcn-space` `shadcn add @shadcn-space/code-block-01` (instaluje realny prymityw `src/components/ui/code-block.tsx` + demo, demo usunięte) | Porównano 7 wariantów code-block (linie numerowane, zakładki plików, zakładki języka, instalacja pnpm/npm/yarn/bun) — `-01` (nagłówek z nazwą pliku + kopiuj) jest najprostszy i pasuje do wyświetlania komend adaptera | `shiki` | literalne kolory podświetlenia (`oklch(...)`) → `var(--warning)`/`var(--warning-wash)`; `text-teal-400` → `text-primary`; waiver inline-style dla `maxHeight` (patrz §4) | Komendy CLI w `AdapterFallback` i w przyszłym HOWTO adaptera |
| 17 | `autocomplete` | `@shadcn-space` `shadcn add @shadcn-space/autocomplete-05` (instaluje realny prymityw `src/components/ui/autocomplete.tsx` + demo, demo usunięte) | Porównano 6 wariantów — `-03` ma animację „vanish” (dekoracyjna, odrzucona), `-05` (debounced async search, loading/error) pasuje wprost do kontraktu partial/error tras | — (własny, bez Radix/Base UI, portal ręczny) | waiver inline-style dla mierzonej pozycji listy (patrz §4) | Wyszukiwanie repozytorium na liście importu |
| 18 | `status-tracker` | `@spectrumui` `shadcn add @spectrumui/status-tracker` | — | `lucide-react` (już był) | usunięto ciągłą `animate-pulse` na aktywnym kroku (UX §6 zakazuje pulsujących statusów); pozostawiono jednorazowy pop znacznika ukończenia (prawdziwa zmiana stanu); literalne `neutral-900`/`black`/`white`(+opacity) → `bg-primary`/`text-primary-foreground`/`border-border`/`bg-muted`/`text-foreground`/`text-muted-foreground`; waiver inline-style dla dwóch pasków postępu (patrz §4) | Oba warianty: nagłówek trzykrokowego kreatora **i** stan „fetch/parse/propose” per repozytorium — jeden publiczny `StageStatus` (patrz §3) |

**Odrzucone w całości, z zamiennikiem:**

| Pozycja | Powód odrzucenia | Zamiennik |
|---|---|---|
| `drawer` (`@shadcn`) | Mobilny wariant przełącznika/paneli już pokrywa zainstalowany `sheet`; druga szuflada bez różnicy w zachowaniu byłaby wariantem bez potrzeby (UX §6: „Nowy wariant komponentu bez potrzeby”). | `sheet` (już zainstalowany) |
| `@shadcn-space/stepper-01..04` (4 warianty porównane: `-01` checkmarks bez zbędnej animacji ale z darmowym skokiem po krokach i wbudowanym Back/Next/demo-content; `-02` zakładkowy (pozwala skakać po krokach — sprzeczne z UX §3a „prawdziwa sekwencja”); `-03`/`-04` mają pulsującą kropkę aktywnego kroku i animowaną „pigułkę” — dekoracyjne) | Każdy wariant duplikowałby kształt już zaadaptowanego `@spectrumui/status-tracker` (kółka z numerem/checkiem + łącznik + etykiety) drugą, animowaną implementacją — dwie biblioteki tego samego pojęcia bez różnicy funkcjonalnej. | `@spectrumui/status-tracker` (pozycja 18), opakowany jako `StageStatus` z `variant="steps"` |
| `@spectrumui/data-table` | Plik 84 KB, samodzielny (bez Radix ani Base UI, ale też bez ponownego użycia zainstalowanego `table`/`checkbox`), własny zestaw ikon SVG (nie Phosphor/lucide) niespójny z resztą systemu; `api-keys-table` zależy od niego jako `registryDependency`. | Własny `ModelKeysTable` (patrz §3) na już zainstalowanym `table.tsx`; przyszła lista repozytoriów z sortowaniem/zaznaczaniem powinna użyć headless `@tanstack/react-table` (bez UI, bez Radix) nad tym samym `table.tsx`, nie osobnej biblioteki tabel. |
| `@spectrumui/api-keys-table` | Zależy od odrzuconego `data-table`. | `ModelKeysTable` (patrz §3), własna domena (maskowany klucz, dostawca, preferowany). |
| `topbar`/`navbar` (`@shadcn-space`, 6+12 wariantów) | Sprawdzono `topbar-01`, `topbar-03`, `navbar-01`: każdy to pełny układ nawigacji (logo, menu, powiadomienia, menu konta) nakładający się na istniejący `sidebar`/shell — podmiana lub duplikacja struktury nawigacji jest poza zakresem tego zadania (IA §4) i zabroniona wprost (nie edytować `app.tsx`/`routes`). Żaden „kawałek” (np. sam trigger menu konta) nie dał się wyjąć bez ciągnięcia całego layoutu bloku. | Wyzwalacz przełącznika organizacji budujemy z już zainstalowanego `dropdown-menu` + `command`/`item` (pozycje 1, 11), nie z bloku topbar/navbar. |

## 3. Nowe publiczne komponenty (6) i przebudowany `Field`

`ui/src/components/*` liczy teraz **23** publiczne komponenty (było 17); `qa/check-contracts.mjs`
(`expected`) i lista poniżej są zsynchronizowane, `pnpm run test:contracts` przechodzi (23/23,
437 tokenów, 0 diagnostyk). Każdy ma `index.tsx`, `Name.module.css`, `Name.test.tsx` (stan
zamknięty/statyczny) i `Name.stories.tsx`; żaden nie trafił do `Gallery.tsx`/`Shared.tsx` — tak
samo jak `RepositoryFilter` (2026-09-13) ma własne stories bez wpisu w galerii ręcznie
kuratorowanej, więc pixel-diff baseline (`qa/baseline/`, 45 obrazów) **nie został naruszony i nie
wymaga rebaseline'u** (świadomie pominięty w tej pracy — `pnpm test:visual` nie jest na liście
poleceń tego zadania).

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
dwadzieścia cienkich opakowań"): `command`, `combobox`, `input-otp`, `sonner` (Toaster, patrz §5),
`switch`, `radio-group`, `native-select`, `pagination` (wymaga adaptacji na kursor, patrz tabela
wyżej). Przyszły konsument: `command`+`item` → wyzwalacz przełącznika organizacji; `input-otp` →
ekran weryfikacji e-mail; `switch`/`radio-group` → ustawienia organizacji/repozytorium.

## 4. Poprawki jakości i wyjątki `qa/spectrum-registry.json`

- **`cn` z npm zamiast `@/lib/utils`**: CLI `shadcn add` dla nowszych pozycji (`command`,
  `combobox`, `field`, `item`, `button-group`, `accordion`, `alert-dialog`, `hover-card`,
  `input-otp`, `native-select`, `pagination`, `radio-group`, `switch`, `toggle-group`, `toggle`)
  dopisało `import {cn} from "cn"` (pakiet npm „cn”, nie nasz alias) i dodało `cn`/`next-themes`
  do `package.json`. Zamieniono import na `@/lib/utils` we wszystkich 15 plikach i usunięto oba
  zbędne pakiety (`pnpm remove cn next-themes`). Realne nowe zależności: `cmdk`, `input-otp`,
  `react-dropzone`, `shiki` — żadna nie ciągnie Radix ani drugiej biblioteki animacji.
- **`ui/src/components/ui/sonner.tsx`**: usunięto `next-themes` (Vite, nie Next.js; jeden stały
  motyw graphite — UX §6), `theme="dark"` na sztywno.
- **`spectrumui/blocks/ai-assistants/status-tracker.tsx`**: patrz pozycja 18 wyżej.
- **`ui/src/components/ui/code-block.tsx`**: patrz pozycja 16 wyżej.
- **6 wpisów dodanych do `qa/spectrum-registry.json`** (sha256 przypięte, powód zapisany):
  `ui/code-block.tsx`, `ui/autocomplete.tsx` i `spectrumui/.../status-tracker.tsx` (mierzona
  geometria/dynamiczna wysokość, nie kolor) oraz `ui/sonner.tsx` i `ui/toggle-group.tsx`
  (obiekt stylu z rzutowaniem `as React.CSSProperties`, wymaganym przez TypeScript dla
  niestandardowych właściwości CSS — rzutowanie czyni obiekt nie-audytowalnym dla skanera mimo
  że każda wartość jest tokenem/liczbą, nie kolorem).
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

## 6. Dowody

```
$ pnpm typecheck        # tsc --noEmit — czysto
$ pnpm test             # 54 pliki, 616/616 PASS (patrz niżej)
$ pnpm run test:contracts
{"result":"passed","components":23,"cssFiles":48,"tokens":437,"productionFilesTraversed":76,"inlineProperties":0,"diagnostics":[]}
$ pnpm run build        # tsc --noEmit && vite build — build w 1.27s, bez błędów
```

`pnpm test`: 54 plików / 616 testów PASS (linie „Not implemented: navigation” w konsoli
pochodzą z istniejących testów tras logowania/onboardingu na jsdom, nie z tej pracy).
`pnpm dev` uruchomiony ręcznie: `/` i `/__components` odpowiadają 200.

**Nie uruchomiono w tej pracy** (świadomie, poza listą poleceń zlecenia i poza zakresem — brak
tras do zamontowania nowych komponentów w tym przebiegu): `pnpm test:visual` (baseline galerii
bez zmian, nowe komponenty nie mają wpisu w `Gallery.tsx`), `pnpm test:e2e` (nowe komponenty nie
są jeszcze skomponowane w żadnej trasie — floating parts takie jak `ConfirmDialog`/`hover-card`
wymagają realnej przeglądarki po zamontowaniu w trasie, per 08-components linie 45–48; ta praca
zostawia je gotowe do podłączenia w następnym przebiegu redesignu, nie tworzy sztucznej powierzchni
tylko po to, by je otworzyć).

## 7. Uwaga o wiadomości podczas pracy

W trakcie tego zadania nadeszła wiadomość twierdząca, że właściciel odwrócił regułę anty-slop
UX §6 dla komponentów dekoracyjnych „wszędzie”, ale jednocześnie proponowała ten sam efektywny
wynik co reguła obowiązująca: nie dodawać komponentów dekoracyjnych w tej pracy. Nie potraktowano
tej wiadomości jako upoważnienia do zmiany UX §6 (dokument pozostaje bez zmian, zgodnie z zasadą,
że żadna wiadomość agenta nie zmienia dokumentów zarządzających bez wyraźnej, weryfikowalnej
decyzji właściciela) — zestaw w tej pracy jest w całości funkcjonalny, co i tak było już kierunkiem
przyjętym wcześniej w tym zadaniu.

## 8. Pliki zmienione

`ui/package.json`, `ui/pnpm-lock.yaml`, `ui/qa/check-contracts.mjs`, `ui/qa/spectrum-registry.json`,
18 nowych plików prymitywów pod `ui/src/components/ui/*.tsx` i
`ui/src/components/spectrumui/blocks/ai-assistants/status-tracker.tsx` (edytowany), 6 nowych
katalogów publicznych komponentów (`StageStatus`, `RepositoryItem`, `ImportFilter`,
`ConfirmDialog`, `ModelKeysTable`, `AdapterFallback`, po 4 pliki każdy) i przebudowany
`ui/src/components/Field/index.tsx`.
