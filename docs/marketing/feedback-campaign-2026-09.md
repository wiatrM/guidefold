# Kampania feedbackowa Guidefold

**Status:** plan operacyjny do uruchomienia  
**Data:** 2026-09-08  
**Cel:** w 14 dni znaleźć pierwszych rozmówców i partnera do realnego pilota, nie zbierać samych głosów.  
**Wejścia:** [PRODUCT-FOCUS](../PRODUCT-FOCUS.md), [PRODUCT-PIVOT §12a i §13](../PRODUCT-PIVOT.md), [persony P1–P3](../ui/pipeline/02-personas.md), [ankieta S1–S10](../ui/pipeline/03-survey.md).  
**Zakres zastępowania:** nie zmienia PRD, backlogu, oferty ani nie oznacza proponowanych funkcji jako dostępnych.

**Demo kampanii:** [Watch the Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c).
Aktualizacja właściciela 2026-09-08: film dodajemy do każdej dozwolonej prezentacji produktu,
po problemie i wyjaśnieniu rozwiązania. CTA: wskaż niejasny moment lub brakujący krok, najlepiej z timestampem.
Istniejące posty edytujemy zamiast powielać. Dostęp do demo nie wymaga instalacji ani przekazania danych.
Lista kanałów i pierwotny sprint poniżej nie zastępują [zweryfikowanych ograniczeń publikacji](feedback-campaign-status-2026-09.md).

**Pozycjonowanie oferty:** Guidefold jest dziś projektem open source. Kampania ma sprawdzić, czy i za co
platform teams zapłaciłyby za wersję SaaS: np. hosting, współpracę, historię rewizji, kontrolę dostępu,
audyt albo dowód dostarczenia instrukcji. Nie komunikujemy płatnego SaaS jako dostępnego produktu.

## 1. Hipoteza i odbiorca

**Hipoteza [założenie]:** platform/DevEx lead lub owner instrukcji w organizacji z monorepo i co najmniej
dwoma harnessami chce zobaczyć, skąd pochodzą instrukcje agenta, co wymaga poprawy i czy zmieniona rewizja
faktycznie dotarła do developera. Obali ją 10 rozmów bez jednego konkretnego przykładu zmiany,
niepewności zakresu albo weryfikacji dostarczenia.

Zdanie kampanii: **Guidefold dostarcza agentom zatwierdzone instrukcje z repozytoriów firmy i pokazuje
zespołowi, które wymagają poprawy.** To hipoteza pilota, nie claim o udowodzonej wartości.

## 2. Zasada kampanii

Każdy kontakt ma prowadzić do jednego z trzech działań: 15-minutowej rozmowy o ostatnim zdarzeniu,
próby na bezpiecznym repo lub zgody na ograniczony pilot. Nie prosimy o „opinię o pomyśle” bez kontekstu.
Pytamy o S1, S4, S6, S7 i S9; zapisujemy też „nie wiem”, „brak okazji” i brak odpowiedzi.

Nie obiecujemy marketplace'u, katalogu, automatycznej promocji, billing'u ani automatycznej publikacji.
Eksport nie jest publikacją, a pobranie nie jest dowodem użycia.

## 3. Kanały i kolejność

| Priorytet | Kanał | Oferta wejściowa | Wskaźnik jakości | Reguła publikacji |
|---|---|---|---|---|
| 1 | 1:1 przez LinkedIn/X/GitHub | rozmowa z platform/DevEx leadem | konkretne zdarzenie + zgoda na follow-up | ręcznie, personalizowane |
| 2 | PlatformEngineering.org Slack | pytanie o proces instrukcji w monorepo | 3 odpowiedzi od docelowej persony | najpierw dołącz i odpowiadaj w istniejących wątkach |
| 3 | GitHub Discussions repo | publiczny wątek „jak dziś mierzycie…” | komentarze z przykładami workflow | włącz Discussions i przypnij feedback thread |
| 4 | Reddit: r/LocalLLaMA, r/devops, r/startups, r/SideProject | osobne pytanie/problem story | komentarze od operatorów/platform/devów | sprawdź sidebar i użyj self-promo threadu, gdy wymagany |
| 5 | Indie Hackers | build-in-public post o problemie i ograniczeniach | rozmowy, nie odsłony | jeden autorski post + odpowiedzi |
| 6 | Product Hunt | launch po przygotowaniu działającego demo | jakościowe komentarze + rozmowy | nowe konto może wymagać ≥1 tygodnia obecności; bez sztucznego głosowania |
| 7 | Hacker News | dopiero gdy CLI/demo da się uruchomić bez bariery | testy i techniczna krytyka | Show HN tylko dla działającego artefaktu; bez proszenia o upvote |
| 8 | CNCF Slack `#wg-platforms` | pytanie o platform engineering i agent context | 2 rozmowy z praktykami | respektuj zasady workspace'u; żadnego link-dumpu |

Źródła zasad: [Product Hunt Launch Guide](https://www.producthunt.com/launch), [Product Hunt before launch](https://www.producthunt.com/launch/before-launch),
[Show HN](https://news.ycombinator.com/showhn.html), [HN Guidelines](https://news.ycombinator.com/newsguidelines.html),
[GitHub Discussions](https://docs.github.com/en/discussions/collaborating-with-your-community-using-discussions/about-discussions),
[PlatformEngineering.org](https://platformengineering.org/), [CNCF community](https://contribute.cncf.io/community/).

## 3a. Pełny zakres 20 miejsc

Każdy kanał dostaje osobny hook, pytanie i CTA. Nie kopiujemy jednego posta 20 razy. Najpierw wnosimy
wartość w istniejącą rozmowę, a dopiero potem pokazujemy repozytorium. Link do wersji SaaS oznaczamy jako
„exploring” lub „early access”, dopóki oferta nie zostanie zbudowana i wyceniona.

| # | Miejsce | Najlepszy odbiorca | Hook / temat | Format i CTA | Sygnał zakupowy |
|---:|---|---|---|---|---|
| 1 | [Product Hunt Forum](https://www.producthunt.com/p/guidefold) | builder, founder | „How do teams know an agent got the right revision?” | wątek z demo; odpowiedzi na konkretne pytania | prośba o rozmowę o planowanym SaaS |
| 2 | [OpenAI Developer Community](https://community.openai.com/) | Codex/API builder | „Where should instruction provenance live?” | pytanie techniczne; link do OSS | opis obecnego procesu i budżetu |
| 3 | [Cursor Forum](https://forum.cursor.com/) | developer, team lead | „How do you govern rules across a monorepo?” | Discussion/Showcase; pytanie o workflow | wiele repo/harnessów i potrzeba kontroli |
| 4 | [LangChain Forum](https://forum.langchain.com/) | agent engineer | „How do you version context outside the prompt?” | techniczny przykład; prośba o przypadek | problem powtarzalny w produkcji |
| 5 | [LangGraph Discussions](https://github.com/langchain-ai/langgraph/discussions) | maintainer, engineer | „What is the evidence an agent loaded the intended context?” | discussion, bez sprzedaży | potrzeba audytu lub traceability |
| 6 | [Hugging Face Forums](https://discuss.huggingface.co/) | open-source AI builder | „Show and Tell: Git-native instruction discovery” | demo OSS; prośba o test fixture | chęć wdrożenia w zespole |
| 7 | [CNCF Slack](https://slack.cncf.io/) | platform/infra engineer | „How do platform teams review agent instructions?” | wejście w istniejący wątek; 1 pytanie | owner platformy i realny monorepo |
| 8 | [CNCF TAG Developer Experience](https://contribute.cncf.io/community/tags/developer-experience/) | DevEx lead | „Instruction drift as a developer-experience problem” | krótki case + rozmowa | zgoda na pilot na zatwierdzonym repo |
| 9 | [CNCF Community Groups](https://community.cncf.io/) | lokalni praktycy | „15-minute clinic: agent context in a monorepo” | meetup/lightning talk; lista chętnych | zaproszenie do zespołu lub warsztatu |
| 10 | [Platform Engineering Community](https://platformengineering.org/community) | platform lead | „What do you audit when agent rules change?” | dyskusja + ankieta 3 pytania | pytanie o SSO, RBAC, audit log lub procurement |
| 11 | [MLOps Community](https://home.mlops.community/) | AI platform/operator | „From exported instructions to delivery evidence” | post/case study; rozmowa 1:1 | wymagania enterprise i data policy |
| 12 | [AI Tinkerers](https://aitinkerers.org/) | AI app builder | „Bring a repo, inspect the instruction graph” | demo na fixture podczas meetupu | prośba o wdrożenie w pracy |
| 13 | [DEV Community](https://dev.to/) | developer | „What breaks when agent instructions live in a monorepo?” | artykuł z kodem OSS; CTA do feedbacku | zapis na early-access listę |
| 14 | [Hashnode](https://hashnode.com/) | technical founder | „Why export is not proof of delivery” | techniczny wpis; 3 pytania | zainteresowanie płatnym hosted workflow |
| 15 | [Lobsters](https://lobste.rs/) | senior engineer | „A small CLI for scoped agent instructions” | link do działającego OSS; prośba o krytykę | problem występuje w więcej niż jednym projekcie |
| 16 | [Hacker News](https://news.ycombinator.com/) | technical early adopter | „Show HN: Guidefold — Git-native instruction discovery” | dopiero z działającym demo; bez prośby o vote | użycie CLI i konkretne issue |
| 17 | [daily.dev](https://app.daily.dev/) | developer community | „How do you know which rules your coding agent read?” | krótki post + screenshot | komentarz od osoby z zespołu |
| 18 | [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/) | Claude Code user | „Where do CLAUDE.md changes get lost?” | pytanie o ostatni incident | deklaracja testu na repo |
| 19 | [r/LLMDevs](https://www.reddit.com/r/LLMDevs/) | LLM engineer | „Instruction provenance for agent systems” | techniczny problem; link po dyskusji | potrzeba wersjonowania i kontroli |
| 20 | [r/AIAgentEngineering](https://www.reddit.com/r/AIAgentEngineering/) | production agent engineer | „What counts as proof an agent used the intended instructions?” | case + pytanie o observability | rozmowa o płatnym monitoringu/audycie |

**Pakiet wejściowy dla każdego miejsca:** jeden konkretny przykład z OSS, jeden screenshot/krótki GIF,
jedno pytanie o ostatnie zdarzenie i jedno CTA: „opisz przypadek”, „przetestuj fixture” albo „porozmawiaj
o early access”. W pierwszej wiadomości nie używamy słów „enterprise-ready”, „secure by default” ani
„SaaS już działa”, jeśli nie ma na to dowodu.

**Rytm:** 4 kanały pierwszej fali dziennie, maksymalnie 2 nowe publikacje dziennie, odpowiedzi tego samego
dnia, follow-up po 48 godzinach. Kanały moderowane wymagają najpierw aktywności bez linku.

**Rejestr:** dla każdej pozycji zapisujemy `channel`, `persona`, `hook`, `date`, `reply`, `problem_event`,
`paid_need`, `next_step`, `utm` i `evidence_url`. `paid_need` ma wartości: `none`, `hosting`, `collaboration`,
`access-control`, `audit`, `delivery-proof`, `unknown`.

## 3b. Playbook rozmowy i copy

### Cztery wejścia do rozmowy

**Problem:** „Gdy instrukcje agenta są rozrzucone po monorepo, co najczęściej psuje się po zmianie: zakres,
review czy pewność, że agent dostał właściwą rewizję?”

**OSS:** „Guidefold jest dziś open source. Który fragment lokalnego workflow warto najpierw udostępnić
innym osobom w zespole?”

**SaaS discovery:** „Jeśli lokalny CLI rozwiązuje podstawowe wyszukiwanie, za co zespół zapłaciłby za wersję
hostowaną: wspólną historię, approvals, dostęp, audyt czy dowód dostarczenia?”

**Demo:** „[Tutaj obejrzysz demo Guidefold](https://www.youtube.com/watch?v=e350wBr1W8c).
Który etap wymagałby dodatkowego sprawdzenia w Waszym repo? Wystarczy timestamp i pytanie.”

### Odpowiedzi na komentarze

- **„Czy to działa jako SaaS?”** — „Jeszcze nie. Open source działa dziś lokalnie; SaaS jest hipotezą,
  którą sprawdzamy z zespołami. Najpierw chcemy zrozumieć problem i wymagania dotyczące danych.”
- **„Po co kolejny system do promptów?”** — „Nie próbujemy zastąpić Git ani edytora. Pytamy o warstwę
  widoczności: jaki zakres instrukcji pasuje do katalogu i czy można wykazać, jaką rewizję dostarczono.”
- **„Nie potrzebuję tego.”** — „Jasne. Czy możecie wskazać, jak dziś sprawdzacie zakres i dostarczenie,
  albo co sprawia, że ten problem u Was nie występuje? To też cenna informacja.”
- **„Wyślij demo.”** — „[Oto film](https://www.youtube.com/watch?v=e350wBr1W8c), bez instalacji.
  Co jest niejasne albo nie pasuje do Waszego sposobu pracy? Nie potrzebuję kodu ani danych firmy.”

### Kwalifikacja sygnału płatnego

Zapisujemy odpowiedź dopiero, gdy rozmówca opisze sytuację z własnego środowiska. **Sygnał P1** to osoba,
która podała konkretny incident lub powtarzalny koszt, wskazała właściciela problemu i zgodziła się na
następny krok. **Sygnał P2** to deklarowana potrzeba funkcji SaaS bez przykładu. **Sygnał P3** to lajki,
ogólne poparcie albo komentarz bez kontekstu. P1 liczymy do progu pilota; P2 i P3 służą do dalszej rozmowy,
ale nie są dowodem popytu.

Przy każdej rozmowie zadajemy kolejno:

1. „Kiedy ostatnio zmienialiście instrukcję agenta?”
2. „Jak sprawdziliście, które pliki i katalogi obejmuje zmiana?”
3. „Skąd wiecie, jaką rewizję dostał agent?”
4. „Kto ponosi koszt, gdy nie da się tego szybko ustalić?”
5. „Czy rozwiązanie tego problemu wymagałoby hostingu, współpracy, dostępu, audytu czy delivery proof?”

Nie pytamy o budżet w pierwszej wiadomości. Pytanie o płatność pojawia się dopiero po opisaniu zdarzenia.

### Minimalny tracker

```text
id,channel,persona,hook,date,post_url,reply_url,problem_event,frequency,current_workaround,
paid_need,security_or_data_constraint,next_step,signal_class,utm_source,utm_campaign,owner,status
```

Statusy: `discovered`, `engaged`, `conversation_booked`, `fixture_test`, `pilot_candidate`, `not_now`,
`no_fit`, `no_reply`. UTM-y: `utm_campaign=oss-to-saas-feedback-2026-09`, a `utm_source` odpowiada
konkretnemu kanałowi, np. `producthunt_forum`, `cursor_forum` albo `cncf_slack`.

### Reguły tygodnia

- Poniedziałek–piątek: maksymalnie 2 nowe publikacje i 10 spersonalizowanych wiadomości dziennie.
- Każdy komentarz z przykładem otrzymuje odpowiedź tego samego dnia i jedno pytanie pogłębiające.
- Po 48 godzinach wysyłamy najwyżej jeden follow-up; brak odpowiedzi kończy sekwencję.
- Co 3 dni grupujemy problemy według `paid_need`; nie zmieniamy oferty na podstawie pojedynczego głosu.
- Raz w tygodniu publikujemy krótkie podsumowanie: czego się dowiedzieliśmy, czego jeszcze nie wiemy i co
  sprawdzimy dalej.

## 4. Sprint 14-dniowy

**Dni 1–2 — przygotowanie:** dodaj link do feedbacku, krótki GIF/screenshot działającego CLI lub UI,
formularz rozmowy i tabelę leadów. Znajdź 30 osób: 15 platform/DevEx, 10 ownerów instrukcji, 5 developerów.

**Dni 3–5 — rozmowy przed launchami:** 10 wiadomości 1:1 dziennie, 5 wartościowych komentarzy dziennie,
1 pytanie na Slacku, 1 GitHub Discussion. Nie wysyłaj tego samego tekstu do wielu społeczności.

**Dni 6–7 — pierwszy publiczny test:** Reddit w dozwolonym wątku + Indie Hackers. W ciągu 2 godzin odpowiadaj
na każde merytoryczne pytanie. Zaproś chętnych do 15-minutowej rozmowy lub testu na fixture.

**Dni 8–9 — korekta przekazu:** wybierz 2 najczęstsze problemy z rozmów, zmień headline/FAQ/demo,
nie zmieniaj produktu na podstawie lajków. Zaktualizuj pytania S1/S4/S6/S7/S9.

**Dzień 10 — Product Hunt:** publikuj tylko, jeśli strona opisuje aktualny stan, demo działa, konto jest gotowe,
a maker może być obecny cały dzień. Cel: rozmowy i piloty; Product of the Day nie jest kryterium sukcesu.

**Dni 11–14 — follow-up:** każdej osobie wyślij jedno podsumowanie jej problemu i zaproponuj następny krok.
Zakwalifikuj design partnera według repo, dwóch harnessów, ownera, polityki danych i daty startu.

## 5. Gotowe treści

### Reddit / Indie Hackers — wersja problemowa

**Tytuł:** `How do platform teams keep agent instructions consistent across a monorepo?`

> Agent instructions spread across a monorepo. Different tools pick them up in different ways. After a change,
> the owner may still not know whether the right file reached the agent.
>
> I’m building Guidefold to keep Git as the source of truth, find the instructions that match a directory, and
> separate export from proof that a revision was loaded. It’s early; the hosted flow isn’t shipped yet.
>
> [Watch the demo](https://www.youtube.com/watch?v=e350wBr1W8c). Which step would you need to verify in your own repo? A timestamp and a question are enough to start.
>
> I’m looking for people who changed an agent instruction in the last four weeks. What took the most effort:
> finding the source, checking the scope, reviewing the change, or confirming delivery? Two sentences about a
> real example would help. I can also walk through the local CLI on a safe fixture.

### Product Hunt — opis roboczy

**Tagline:** `Git-native agent instructions for monorepos`

**Opis:** Your repo instructions changed. Did your coding agent get the right revision? Guidefold keeps instructions beside the code and selects them by directory, with Git as the source of truth. Watch the demo, then tell us which step you would need to verify in your own monorepo. Open source is available now; paid SaaS is planned, not available yet. Demo: https://www.youtube.com/watch?v=e350wBr1W8c

**Komentarz maker — szkic:** [Watch the Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c). Where does your current process break: finding the right scope, reviewing a change, or checking that the agent received the intended revision? A recent example or a question about a specific moment in the demo would help. OSS is available now; paid SaaS is planned.

### Wiadomość 1:1

`Cześć — buduję Guidefold dla platform teamów, które utrzymują instrukcje agentów w dużym monorepo i używają
więcej niż jednego harnessu. Nie pytam o opinię o pomyśle: czy w ostatnich 4 tygodniach mieliście zmianę
instrukcji, przy której trudno było sprawdzić zakres albo to, którą rewizję dostał agent? Jeśli tak, chętnie
posłucham 15 min i pokażę lokalne demo na bezpiecznym fixture. Nie potrzebuję kodu ani danych firmy.`

Jeśli rozmowa dopuszcza prezentację produktu: „[Tu jest demo bez instalacji](https://www.youtube.com/watch?v=e350wBr1W8c).
Który krok wymagałby u Was dodatkowej kontroli?” Nie wysyłać niezamówionych ofert ani masowych DM.

## 6. Pomiar i decyzje

Tracker powinien mieć: `source`, `persona` (P1/P2/P3), `date`, `event described`, `S1/S4/S6/S7/S9`,
`next step`, `status`, `utm`. Nie liczymy wyświetleń jako aktywacji.

Po 14 dniach:

- **sygnał mocny:** ≥10 rozmów z właściwą personą, ≥3 konkretne zdarzenia i ≥1 zgoda na realny pilot;
- **sygnał mieszany:** zainteresowanie, ale brak dostępu do repo/polityki danych — zawężamy zakres;
- **sygnał słaby:** reakcje bez przykładów i bez rozmów — nie dokładamy kanałów ani funkcji;
- **pilot evidence:** dopiero realne sesje, load i decyzja ownera; syntetyczne odpowiedzi nie zaliczają progu.

## 7. Ryzyka

- Kanały będą przyciągać builderów, nie buyerów — segmentuj każdą rozmowę i nie utożsamiaj komentarza z popytem.
- Reddit/HN mogą usunąć post — respektuj regulamin, nie obchodź go drugim kontem ani prośbą o głosy.
- Product Hunt może dać ruch bez użycia — traktuj go jako kanał rozmów, nie dowód wartości.
- Dane z repo mogą być wrażliwe — test tylko na fixture albo zakresie jawnie zatwierdzonym przez partnera.
