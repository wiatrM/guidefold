# Status kampanii feedbackowej — 2026-09-09

## Dwunaste miejsce — r/coolgithubprojects

2026-09-09 opublikowano [prezentację repozytorium](https://www.reddit.com/r/coolgithubprojects/comments/1wbhjzq/guidefold_find_codingagent_instructions_by/).
Chrome potwierdził wpis w feedzie społeczności, autora mwiatruZ, link do repozytorium, demo YouTube
i GitHub #127. Prośba dotyczy pierwszego niejasnego kroku README i wyboru instrukcji dla katalogu.
Wpis ujawnia autorstwo i pomoc AI; rozróżnia dostępny OSS oraz planowany płatny hosting.
Licencję Apache-2.0 sprawdzono w LICENSE. Nie proszono o gwiazdki ani prywatne repozytoria.

Przed publikacją odczytano stronę społeczności i formularz wymagający linku/obrazu/AMA;
wyszukiwanie Guidefolda nie zwróciło wcześniejszego wpisu. Pierwszy odczyt: 0 komentarzy,
1 głos z zaznaczonym własnym upvote. To publikacja, nie dowód zainteresowania.
Stan: 14 publikacji w 12 różnych kanałach. Nowy permalink obejmuje tracker używany przez monitoring.

10 minut po publikacji użytkownik Specific_Cream2815 zapytał: „how does it match instructions to a task,
nearest directory up the tree or keyword matching”. To pierwszy konkretny sygnał produktowy z tego miejsca:
nie jest jeszcze deklaracją testu, użycia ani potrzeby płatnego SaaS, ale wskazuje, że opis mechanizmu
wyboru instrukcji wymaga doprecyzowania. Zapisano permalink komentarza w wierszu 34. Nie odpowiadano automatycznie.

2026-09-09 odpowiedziano ręcznie pod komentarzem: [p8q1x3l](https://www.reddit.com/r/coolgithubprojects/comments/1wbhjzq/comment/p8q1x3l/).
Wyjaśniono kolejność: zakres node + ancestors, następnie nearest/deepest wins dla tej samej nazwy,
a dopiero potem BM25F wewnątrz dozwolonego zakresu. Podano diagnostykę 24/24 i 23/24 oraz linki do
RESEARCH i ADR-0037; wyraźnie oznaczono ograniczenia i brak tej reguły w hosted Go service.

Sprawdzono też [bieżący wątek r/ChatGPTCoding](https://www.reddit.com/r/ChatGPTCoding/comments/1w9lsay/weekly_self_promotion_thread/).
Promocja należy do tego wątku, ale rozwinięta reguła 7 zakazuje surowego tekstu AI i pozwala AI
na gramatykę/klarowność. Nie publikowano wygenerowanej treści; potrzebny własny tekst autora.

## Kontrola zainteresowania — 2026-09-09

### Rasa Agent Engineering — zweryfikowany kanał, dostęp nieuzyskany

2026-09-09 odczytano w Chrome [stronę społeczności](https://info.rasa.com/community)
i pełne [zasady](https://info.rasa.com/community-guidelines), oznaczone aktualizacją November 2025.
Prośby o feedback, badania użytkowników i prezentacje produktu należą do `#shameless-promotion`;
limit to 2 posty tygodniowo na kanał. Zakazane są duplikaty między kanałami i niezamówiona promocja w DM.
`#showcase` dotyczy projektów voice AI; nie należy tam kierować Guidefolda tylko ze względu na nazwę kanału.
Treść musi dotyczyć AI lub powiązanych tematów i ujawniać afiliację autora. Proponowane dopasowanie:
instrukcje dla coding-agentów utrzymujących repozytorium aplikacji agentowej, nie deklaracja integracji z Rasa.

Dostęp do Discorda prowadzi przez formularz: wymagane work email, country i akceptacja Community Guidelines.
Formularz informuje także o aktualizacjach i wiadomościach firmy. Nie przesłano danych, nie zaakceptowano
warunków i niczego nie opublikowano. Potrzebne dołączenie przez właściciela, potem kontrola rzeczywistego
kanału i jego historii przed pojedynczą publikacją. Wiersz 33 nie zwiększa licznika 11 miejsc.

Odczyt w zalogowanym Chrome: [r/git](https://www.reddit.com/r/git/comments/1wbd58o/i_built_guidefold_to_track_which_agent/p8p1vfd/)
pokazuje 943 wyświetlenia i odpowiedź waterkip: „This isnt a git problem. Kthnxbye”. To sygnał
niedopasowania kanału, nie ocena działania Guidefolda ani deklaracja testu. Wpis istniał przed kontrolą;
nie publikowano go w tym przebiegu. Dodano brakujący kanał do trackera. Nie ponawiać promocji na r/git.

Pozostałe odczyty dotyczą permalinków w trackerze:
- r/SideProject: 172 wyświetlenia; licznik 2 komentarzy, ale treść niewidoczna. Ich znaczenie pozostaje unknown.
- r/AIAgentEngineering: 71 wyświetleń; r/alphaandbetausers: 45; oba pokazują brak odpowiedzi.
- Product Hunt, wiersze 1 i 26: odpowiednio 4 i 3 wyświetlenia, oba bez odpowiedzi.
- GitHub #127: 0 komentarzy, jedynym uczestnikiem jest autor.
- Pod komentarzami Guidefolda w r/ClaudeCode, r/devops, r/github i r/betatests nie znaleziono odpowiedzi.
- CNCF: główny wpis bez widocznych reakcji/odpowiedzi; wątek Nicolasa nadal pokazuje 2 odpowiedzi.

[Strona launchu Product Hunt](https://www.producthunt.com/products/guidefold?launch=guidefold-2)
pokazuje termin 2026-09-22 00:01 PDT, wyłączone głosowanie i 1 obserwującego. Nie ustalono,
czy obserwujący jest osobą spoza zespołu. W sprawdzonych odpowiedziach brak deklaracji testu lub zakupu;
nie jest to pomiar zapisów do waitlisty ani użycia OSS. Nie wysyłano odpowiedzi ani nowych postów.

Tracker po uzupełnieniu obejmuje 13 istniejących publikacji w 11 różnych kanałach, w tym r/git
z negatywnym sygnałem dopasowania. Cel 20 miejsc pozostaje niewykonany; rejestracja, kandydat
i strona produktu bez dyskusji nie są publikacją feedbackową.

## LinuxCommunity — ograniczenie sposobu publikacji

Lobsters również zweryfikowano 2026-09-08: [About / Guidelines](https://lobste.rs/about) ogranicza
autopromocję do mniejszości aktywności i wyklucza treści promujące usługę komercyjną lub pozbawione
znaczącego autorstwa człowieka. Nowe konta wymagają zaproszenia i mają ograniczenia. Pozycja 15
nie jest już niezweryfikowanym discovered: wymaga osobistego udziału autora, nie automatycznej kampanii.
Nie proszono obcych osób o zaproszenia ani nie opublikowano wpisu.

2026-09-08: main agent zweryfikował [Showcase guidelines](https://linuxcommunity.io/t/showcase-category-guidelines-what-to-include-when-sharing-your-project/7628)
oraz [FAQ, reguły 5 i 9](https://linuxcommunity.io/faq). Showcase wymaga opisu, demonstracji, sposobu
wypróbowania i licencji. AI może pomagać w redakcji własnych myśli; tekst będący głównie wynikiem AI
może zostać ukryty lub usunięty. Reklama nakierowana na przychód wymaga zgody staff.
Wniosek: osobisty techniczny pokaz autora po spełnieniu reguł, nie automatyczny wpis z copy kitu.
Nie publikowano ani nie rejestrowano konta. Ten kandydat nie zwiększa licznika promocji.
Chrome ponownie odpowiada; zachowana karta DeepLearning.AI nadal jest ekranem Sign In.

## Kolejne społeczności poza Redditem — kontrola 2026-09-08

DeepLearning.AI: main agent odczytał oficjalne [zasady promocji](https://community.deeplearning.ai/t/self-promotion-and-solicitation-policies/894879)
i [zasady AI slop](https://community.deeplearning.ai/t/prohibited-ai-slop/888269).
Istotna merytorycznie prezentacja biznesu jest dozwolona raz w miesiącu w AI Discussions;
aktualizacje mają pozostać w jednym wątku. Nieedytowane generowane teksty i ogólne szablony są wykluczone.
Chrome otworzył AI Discussions, potem ekran Sign in (Google/LinkedIn/Apple lub email/hasło).
Brak zalogowanej sesji; nic nie wysłano. Następny krok: właściciel loguje się na swoje konto.
Temat do rozwinięcia: testowanie poprawności wyboru instrukcji po zadaniu i katalogu na jawnej fixture.

Research pomocniczy wskazał pięć dalszych kandydatów, jeszcze bez weryfikacji dostępu przez main agenta:

- [LinuxCommunity Showcase](https://linuxcommunity.io/c/showcase/21): techniczny pokaz OSS; reklama hostingu wymaga dodatkowego sprawdzenia.
- [Claude Code Community Australia](https://claudecommunity.com.au/community): trzeba ustalić dostęp dla osoby spoza Australii.
- [Rasa Agent Engineering](https://info.rasa.com/community): rejestracja i zasady konkretnego kanału #shameless-promotion do sprawdzenia.
- [DevOpsChat](https://www.devopschat.co/community/register): automatyczne publikowanie zabronione; wymaga osobistego udziału autora, nie automatycznego copy kitu.
- [Agentics NZ showcase](https://github.com/agenticsnz/showcase): kuratorowany PR, nie natychmiastowa rozmowa; uprawnienie uczestnictwa spoza NZ nieustalone.

Nie są publikacjami i nie zwiększają licznika. Indie Hackers nadal pokazuje Posts 0; kliknięcie na stronie
produktu otworzyło pusty szkic. Nie wpisano treści; zaakceptowano usunięcie wyłącznie tego własnego pustego szkicu,
ale błąd połączenia Chrome uniemożliwił potwierdzenie końcowego stanu. Nie stwierdzono odblokowania publicznych postów.

## Kontrola CNCF i uzupełnienie brakującego wpisu

2026-09-08, kolejny odczyt Chrome: wątek Nicolasa nadal ma dwie odpowiedzi, z których ostatnia jest
naszym komentarzem o 20:26. Wcześniejsza odpowiedź Oliviera nie jest feedbackiem na Guidefold.
Zidentyfikowano także [istniejący główny wpis Guidefold z 20:39](https://cloud-native.slack.com/archives/C093U0DN49H/p1788892751088229),
z demo i opisem CLI/Go/SEARCH/USE. W tym przebiegu go nie publikowano ani nie edytowano.
Dodano brakujący permalink do monitora; to ten sam kanał CNCF, nie nowe miejsce.

W historii kanału odczytano komunikat z 22 stycznia o przenoszeniu rozmów AI do
[#cncf-artificial-intelligence-technical-community-group](https://cloud-native.slack.com/archives/C08Q78J65A7).
Podgląd docelowego kanału jest dostępny, opis wskazuje oficjalny CNCF TOC AI Initiatives;
historia obejmuje prezentację K8sGPT/Codex MCP. Nie dołączono ani nie opublikowano cross-postu.
Sam historyczny komunikat o planowanym read-only nie dowodzi, że stary kanał jest dziś zablokowany.
Przed następną prezentacją należy ustalić właściwe miejsce i zasady udziału, nie mnożyć kopii.

## Dziesiąte miejsce: r/betatests

2026-09-08: opublikowano [odpowiedź na publiczne zaproszenie developera do testowania](https://www.reddit.com/r/betatests/comments/1vc3ed8/comment/p8m7q9o/).
Autor wątku deklaruje testowanie projektów w przeglądarce i prosi o opis oraz konkretne pytania.
Odczytano reguły: brak spamu/low-effort oraz wymagania wieku konta i karmy. Nie obchodzono ograniczeń.
Prośba Guidefold obejmuje obejrzenie demo i przeczytanie quickstartu bez uruchamiania komend;
wynik to pierwszy niezrozumiały krok lub timestamp. Nie obiecuje natywnej aplikacji macOS/iOS.
Zawiera demo, repo, GitHub #127, ujawnienie autorstwa i pomocy AI oraz rozróżnienie OSS/planowany hosted.
Chrome potwierdził autora mwiatruZ, pełną treść i permalink. Brak odpowiedzi w pierwszym odczycie;
wcześniejsza ogólna oferta testowania nie jest jeszcze zgodą na test Guidefold ani sygnałem popytu.

Tracker ma 10 odrębnych miejsc published (w tym własny GitHub). Cel 20 miejsc pozostaje otwarty.
Odczyt konfiguracji potwierdził aktywny monitor feedback-kampanii-guidefold co 6 godzin, czytający tracker.
Daily blog X pozostaje PAUSED do wskazania docelowego profilu; nie utworzono duplikatu automatyzacji.

## Dziewiąte miejsce: megawątek r/github

2026-09-08: opublikowano [komentarz Guidefold w przypiętym Self-Promotion Megathread](https://www.reddit.com/r/github/comments/1jy8rea/comment/p8m7f86/).
Reguła 4 odczytana w Chrome dopuszcza promocję wyłącznie w tym dedykowanym wątku; treść główna prosi
o opis projektu i link do repo. Wyszukiwanie komentarzy dla Guidefold przed publikacją nie zwróciło wyników.
Po publikacji potwierdzono autora mwiatruZ, pełną treść, permalink, demo oraz GitHub Discussions #127.
Pytanie dotyczy quickstartu i ustalania instrukcji właściwych dla katalogu. OSS dostępny, hosted planowany;
pomoc AI ujawniona, fictional fixture opisany wprost. Brak odpowiedzi w pierwszym odczycie.

To dziewiąte odrębne miejsce z publikacją, wliczając własne GitHub Discussions; nie zamyka celu 20 miejsc.
Domyślny własny głos nie jest zainteresowaniem odbiorcy. Nowy rekord published trafia do trackera dla monitora.

## Kolejna dyskusja i bramka wdrożenia landing page

2026-09-08, wieczorna kontrola w Chrome:

- Opublikowano [nowy wątek Product Hunt o agencie CI, BYOK i kontroli kosztów](https://www.producthunt.com/p/guidefold/would-your-team-run-an-instruction-editing-agent-in-its-own-ci).
  Potwierdzono autora Michał Wiatr, pełną treść, osadzone demo i link do głównej dyskusji GitHub #127.
  Hosted i agent CI są jawnie planowane. Przy odczycie brak odpowiedzi; to kolejny wątek w istniejącym kanale, nie dziewiąte miejsce.
- Zaktualizowano istniejący [post r/SideProject](https://www.reddit.com/r/SideProject/comments/1waugep/i_built_guidefold_to_track_which_agent/):
  dodano link do GitHub #127 i ujawnienie pomocy AI, zachowując demo i dotychczasowe pytania.
  Zapisany link zweryfikowano w publicznej treści. 141 wyświetleń i 0 komentarzy w tym odczycie; brak dowodu popytu.
- GitHub #127 nadal pokazywał 0 komentarzy. Nie dodano własnych komentarzy podbijających widoczność.
- Właściciel zlecił deploy landing page. Diagnostyka: publiczny host HTTPS zwraca 200 ze starym UI,
  API zwraca 503. Brak dostępu do opisanego produkcyjnego klastra: standardowy WSL kubeconfig zawiera
  wyłącznie niedostępny docker-desktop. Potrzebny produkcyjny kubeconfig. Nie wykonano deployu,
  migracji, odczytu sekretów ani prawdziwej wysyłki Resend. Nie promować formularza jako działającego.

Tekst pytania ograniczono zgodnie z positioning-and-copy do rzeczywistego stanu produktu.
Kampania kieruje obecnie do sprawdzonego wątku feedbackowego; masowe duplikaty i obchodzenie ograniczeń są wykluczone.

## GitHub Discussions — własne miejsce na feedback

2026-09-08: włączono Discussions w repozytorium właściciela i opublikowano
[Start here: watch the Guidefold demo and tell us where the workflow breaks](https://github.com/wiatrM/guidefold/discussions/127).
To pierwsza dyskusja, kategoria Announcements; UI potwierdził przypięcie (kontrolka Unpin discussion),
autora wiatrM, pełną treść, demo YouTube i 0 komentarzy. GitHub jest własnym kanałem projektu,
nie zewnętrzną społecznością ani dowodem pozyskania nowych odbiorców.

Treść stosuje positioning-and-copy: OSS dostępny, płatny hosted planowany, eksport nie dowodzi użycia.
Prosi o timestamp lub odtwarzalny problem na fictional fixture, bez prywatnego kodu. Pomoc AI ujawniona.
Nie zmieniono plików repozytorium na GitHubie, widoczności, uprawnień ani ustawień bezpieczeństwa.
Tracker obejmuje teraz **8 miejsc z publikacją**, w tym ten własny punkt zbierania feedbacku.
Nie oznacza to wykonania promocji w 20 zewnętrznych społecznościach. Monitor obejmuje nowy rekord published.

## CNCF — dostęp odblokowany i odpowiedź opublikowana

2026-09-08: Chrome potwierdził zalogowane konto Michał Wiatr w workspace CNCF. Zastępuje to
wcześniejszą blokadę dołączenia. Dołączono do `#ai-native-platform-engineering` (C093U0DN49H).
Sprawdzono opis kanału (pusty) i [Slack Guidelines](https://github.com/cncf/foundation/blob/main/policies-guidance/slack-guidelines.md):
wiadomości mają pasować do tematu; bez spamu i niezamówionych ofert w DM.

Opublikowano [odpowiedź Guidefold](https://cloud-native.slack.com/archives/C093U0DN49H/p1788891987610779?thread_ts=1788593442.439139&cid=C093U0DN49H)
w istniejącym [wątku o wersjach skilli, MCP i pluginów](https://cloud-native.slack.com/archives/C093U0DN49H/p1788593442439139).
Zweryfikowano autora, pełną treść, demo YouTube i permalink. Bez cross-postu do kanału i bez DM.
Skill positioning-and-copy ograniczył obietnicę do instrukcji repo: jawnie zaznaczono, że Guidefold nie
jest pełnym inwentarzem wszystkich pluginów na maszynach. OSS dostępny, hosted planowany, autorstwo i pomoc AI ujawnione.

Pytanie rozmówcy sprzed publikacji jest kontekstem discovery, nie odpowiedzią na Guidefold ani dowodem
popytu na SaaS. W momencie zapisu brak nowej odpowiedzi na nasz komentarz. Monitor czyta tracker ze statusem published.
Aktualnie **7 miejsc z publikacją**; pozostałe pozycje CNCF nie są osobnymi wykonanymi publikacjami.

## Aktualizacja demo — 2026-09-08

Główny film wskazany przez właściciela: [Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c).
Przepisano istniejące treści, bez nowych postów i bez duplikatów. Hook prowadzi do problemu,
krótkiego wyjaśnienia Guidefold, filmu i pytania o konkretny krok lub timestamp.

Zweryfikowano zapis w Chrome:

- Product Hunt: opis premiery zawiera URL; natywne pole Video/Loom zachowało URL po ponownym otwarciu edytora.
  Termin bez zmian: 22 września 2026, 09:01 CEST.
- [Forum Product Hunt](https://www.producthunt.com/p/guidefold/how-do-you-check-which-instructions-your-coding-agent-received): nowa treść z demo.
- [r/SideProject](https://www.reddit.com/r/SideProject/comments/1waugep/i_built_guidefold_to_track_which_agent/): demo i pytanie o niejasny krok; URL sprawdzony po ponownym otwarciu.
- [r/alphaandbetausers](https://www.reddit.com/r/alphaandbetausers/comments/1wavp2c/open_source_developer_tool_guidefold_looking_for/): obejrzenie filmu przed instalacją; URL sprawdzony po ponownym otwarciu.
- [r/AIAgentEngineering](https://www.reddit.com/r/AIAgentEngineering/comments/1wavu87/what_belongs_in_a_receipt_for_instructions/): demo jako kontekst techniczny, z zachowaną granicą export/delivery/use. Pierwsza próba edycji nie utrwaliła się; ponowny zapis zweryfikowany w treści publicznej.
- [r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1w9pn3e/comment/p8l3ysq/): edycja istniejącego komentarza showcase, URL widoczny w zapisanej treści.
- [r/devops](https://www.reddit.com/r/devops/comments/1w9k9gw/comment/p8kxako/): edycja istniejącego komentarza, URL widoczny w zapisanej treści.

Lokalnie: demo dodano do playbooka, copy kitu, kalendarza, indeksu marketingu oraz
`portal/content/index.md`. To zmiana źródła strony dokumentacji, **nie potwierdzenie wdrożenia na serwer**.
Copy kit zawiera także warianty IH i X; nie są opublikowane. Sprawdzenie `git diff --check` ograniczone
do `portal/content/index.md` i `docs/marketing` zakończyło się kodem 0; bez pełnego buildu portalu.

Wyjątki:

- Indie Hackers: edytor nie ma pola demo; pełny zapis profilu wymaga niepodanych danych założycieli,
  daty startu, finansowania i zaangażowania. Nie zastąpiono linku do repo filmem ani nie dopisano fikcyjnych danych.
  Ograniczenie publikowania nowych postów pozostaje ostatnim potwierdzonym stanem.
- X: nadal brak wskazanego docelowego profilu; automatyzacja nie została aktywowana.
- **OpenAI Community: nowy stan zastępuje wcześniejsze „pending”.** Kolejka jest pusta, lista tematów konta
  pokazuje brak tematów. [Komunikat systemowy](https://community.openai.com/t/account-temporarily-on-hold/1395878)
  potwierdza tymczasowe wstrzymanie konta do przeglądu ostatnich wpisów przez staff; nie można tworzyć tematów ani odpowiadać.
  Nie potwierdzono publicznej publikacji i nie dodano demo. Nie wysyłać ponownie ani nie obchodzić ograniczenia.

## Zweryfikowane

- Product Hunt: Guidefold ma logo, zaktualizowany opis i launch zaplanowany na **22 września 2026,
  09:01 CEST**.
- Product Hunt odbudowany na zlecenie właściciela: [produkt](https://www.producthunt.com/products/guidefold),
  [forum p/guidefold](https://www.producthunt.com/p/guidefold),
  [panel zaplanowanego launchu](https://www.producthunt.com/products/guidefold/guidefold-2/prelaunch).
  Stary adres produktu `products/github-500` zwracał 404 po usunięciu. Nie używać go do promocji.
- Product Hunt Forum: [nowy wątek opublikowany](https://www.producthunt.com/p/guidefold/how-do-you-check-which-instructions-your-coding-agent-received).
  Treść rozróżnia dostępny OSS i planowany SaaS; pyta o ostatnią zmianę instrukcji. Przy weryfikacji publikacji brak odpowiedzi.
- Cursor Forum: otwarto logowanie; brak zalogowanej sesji. [Regulamin](https://forum.cursor.com/guidelines/)
  dopuszcza odpowiednią autopromocję w Showcase, ale całkowicie wygenerowane wpisy mogą być usuwane,
  a boty wyciszane. Kanał wymaga osobistego udziału autora i własnych obserwacji; przygotowany copy kit nie jest gotowy do automatycznej publikacji tutaj.
- Reddit: opublikowany komentarz w cotygodniowym wątku r/devops oraz post w r/SideProject.
- Reddit r/ClaudeCode: [komentarz Guidefold](https://www.reddit.com/r/ClaudeCode/comments/1w9pn3e/comment/p8l3ysq/)
  opublikowany w przypiętym Weekly Showcase 2026-09-08; ten wątek wprost dopuszcza krótkie prezentacje projektów.
  Zweryfikowano autora `mwiatruZ` i treść po publikacji. Brak odpowiedzi przy pierwszym odczycie;
  własny domyślny głos nie jest sygnałem zainteresowania.
- [OpenAI Community](https://community.openai.com/guidelines): 2026-09-08 wysłano temat
  „Guidefold: checking which repo instructions reach a Codex session” w Community z tagiem `projects`.
  Chrome potwierdził „Post Needs Approval” i dokładnie jeden wpis w
  [kolejce konta mwiatr.dev](https://community.openai.com/u/mwiatr.dev/activity/pending).
  Zweryfikowano pełną treść w kolejce: OSS dostępny, płatny hosted planowany, pytanie o ostatnią zmianę
  instrukcji w zespole używającym Codex, bez żądania prywatnych danych. **Oczekuje na moderację, nie jest
  jeszcze publiczny; permalink nie został przydzielony w widocznym UI.** Nie wysyłać ponownie.
- [Hashnode](https://hashnode.com/code-of-conduct): zakaz automatycznego lub masowego publikowania
  oraz używania platformy głównie do autopromocji bez wkładu w społeczność. Nie publikować automatycznie copy kitu.
- Odczyt Reddit 2026-09-08: [r/SideProject](https://www.reddit.com/r/SideProject/comments/1waugep/i_built_guidefold_to_track_which_agent/)
  pokazuje 60 wyświetleń i 0 odpowiedzi (wpis miał około 16 minut); pod [komentarzem Guidefold w r/devops](https://www.reddit.com/r/devops/comments/1w9k9gw/comment/p8kxako/)
  brak widocznych odpowiedzi. To stan początkowy, bez wniosków o popycie.
- LangChain Forum: logowanie przez istniejące GitHub doprowadziło do formularza rejestracji;
  nie wysłano formularza ani wpisu. [Community Code, Rule 4](https://www.langchain.com/community-code)
  zabrania vendor lead generation. Kanał wyłączony z tej kampanii sprzedażowo-feedbackowej,
  nie ukrywamy celu komercyjnego pod techniczną dyskusją.
- Hugging Face, kontrola 2026-09-08: przycisk Log In na forum przeniósł do „Verify Your Email”.
  Konto istnieje, ale wymaga kliknięcia linku w mailu weryfikacyjnym przez właściciela. Zachowano
  kartę Chrome; nie wysłano kolejnego maila ani treści na forum. Nie zapisywać tokenizowanego adresu SSO w trackerze.
- DEV, kontrola 2026-09-08: [zasady AI](https://dev.to/guidelines-for-ai-assisted-articles-on-dev)
  zabraniają promowania biznesu w artykułach generowanych lub wspomaganych AI oraz generowania
  komentarzy przez AI. [Warunki treści](https://dev.to/terms) wymagają merytorycznej treści i wykluczają
  wpisy głównie promocyjne. Kanał wyłączony z automatycznej kampanii; nie publikować copy kitu po samym zalogowaniu.
- Ponowny odczyt r/SideProject 2026-09-08: 92 odsłony, 0 komentarzy, widoczny komunikat
  „Nobody's responded to this post yet”, wiek wpisu około 46 minut. Brak sygnału popytu;
  nie dodano własnego komentarza w celu podbijania wpisu.
- r/alphaandbetausers: [opublikowano prośbę o test pierwszego uruchomienia OSS](https://www.reddit.com/r/alphaandbetausers/comments/1wavp2c/open_source_developer_tool_guidefold_looking_for/),
  2026-09-08, autor `mwiatruZ`. Wpis widoczny w feedzie społeczności z pełną treścią i 0 komentarzy
  przy pierwszym odczycie. Pytanie dotyczy setupu i zrozumiałości wyboru instrukcji na fikcyjnym
  `examples/monorepo`, bez prywatnego kodu. SaaS nazwany planowanym; brak zachęt za pozytywne opinie.
  Opis społeczności wprost zaprasza do rekrutowania testerów; formularz nie pokazał dodatkowych reguł.
- [Platform Engineering](https://platformengineering.org/): link Join Slack prowadzi do działającego
  zaproszenia. Kontynuacja wymaga e-maila lub Google/Apple oraz akceptacji warunków Slacka.
  Nie dołączono do workspace; formularz zostawiono w Chrome.
- [MLOps Community](https://mlops.community/): oficjalny link Join prowadzi do
  [formularza rejestracji](https://gatewaze.mlops.community/). Nie przesłano danych; formularz zostawiono w Chrome.
- [AI Tinkerers](https://aitinkerers.org/): kanał wymaga działającego technicznego demo i udziału w wydarzeniu;
  nie jest miejscem na sprzedażowy post SaaS. Nie zgłoszono wystąpienia bez wyboru wydarzenia i dostępności autora.
- [CNCF](https://contribute.cncf.io/projects/best-practices/community/vendor-neutrality/): zasady promocji
  zależą od konkretnego projektu/kanału; zakazane jest spamowanie kanałów i sprzedażowe wiadomości prywatne.
  Trzech ogólnych pozycji CNCF nie traktować jako trzech zweryfikowanych miejsc publikacji.
- LangGraph i LangChain nie są dwoma niezależnymi forami: [oficjalna migracja dyskusji](https://github.com/langchain-ai/langchain/discussions/31978).
- [Hacker News](https://news.ycombinator.com/newsguidelines.html): nie publikować tekstu wygenerowanego
  lub redagowanego przez AI; potrzebny własny tekst autora.
- [r/LLMDevs](https://www.reddit.com/mod/LLMDevs/rules/): odrzucono dla kampanii pozyskiwania klientów
  przyszłego SaaS z powodu reguł przeciw komercyjnej promocji i marketingowi ukrytemu jako prośba o feedback.
- Monitor feedbacku `feedback-kampanii-guidefold`: utworzony, aktywny, co 6 godzin w tym zadaniu.
  Powiadamia o merytorycznych zmianach; nie publikuje automatycznych odpowiedzi. Ma zakończyć monitoring po 23 września.
- Indie Hackers: utworzono [stronę produktu Guidefold](https://www.indiehackers.com/product/guidefold)
  na koncie `Mwiatr`, 2026-09-08. Zweryfikowano logo, tagline „Git-native instructions for coding agents
  in monorepos”, link do GitHub i przypisanie właściciela. **To wizytówka, nie rozmowa: Posts 0.**
  Główny formularz nowych postów nadal pokazuje „You can't create posts yet”; nie próbowano obejść
  ograniczenia. Pełny profil wymaga niepodanych faktów: daty rozpoczęcia, liczby założycieli/pracowników,
  finansowania i początkowego zaangażowania. Nie wpisano domysłów ani danych o przychodach.
- Repozytorium: istnieją playbook, kalendarz 14-dniowy i tracker 20 kanałów.

## Nie przedstawiamy jako wykonane

- Tracker obejmuje 24 pozycje: pierwotne 20, wizytówkę Indie Hackers oraz nowy kanał testerów i dwie wcześniej opublikowane
  rozmowy Reddit. Sześć miejsc ma zapisane publikacje, jedno czeka na moderację; pozostałe obejmują
  blokady, wykluczenia i duplikaty. Nie dowodzi to wykonania kampanii w 20 miejscach.
  Pozostałe pozycje wymagają weryfikacji dostępu, zasad i dopasowania przed publikacją.
- Nie ma jeszcze dowodu popytu na płatny SaaS; zbieramy dopiero przykłady problemów, wymagania i kandydatów
  do pilota.
- Publikacja Product Hunt została wykonana na podstawie wcześniejszego zlecenia użytkownika.

## Następne działania

Kontrola dostępu 2026-09-08: CNCF Slack potwierdził, że konto Google używane w kampanii nie należy
do workspace. Zwykły signup ogranicza domenę do Linux Foundation. Oficjalny [slack.cncf.io](https://slack.cncf.io/)
przekierowuje do `cncf-slack.netlify.app`, gdzie należy zaakceptować Code of Conduct i Slack Guidelines
przed przejściem do zaproszenia. Nie zaznaczono zgód; karta Chrome zachowana dla właściciela.
[Slack Guidelines](https://github.com/cncf/foundation/blob/main/policies-guidance/slack-guidelines.md)
zabraniają spamu między kanałami i niezamówionych ofert w DM. TAG DevEx nadal wymaga dostępu i odczytu
zasad konkretnego kanału; nie zaliczamy go oddzielnie jako wykonanego.

daily.dev: brak zalogowanej sesji, a [aktualne zasady treści](https://docs.daily.dev/content-guidelines/)
wykluczają treści generowane przez AI i treści głównie autopromocyjne. Samo logowanie nie odblokowuje
automatycznej kampanii: potrzebny oryginalny tekst właściciela zgodny z regułami wybranego Squad.
Nie utworzono konta, Squad ani posta.

Publikacja 2026-09-08: [r/AIAgentEngineering — delivery receipt](https://www.reddit.com/r/AIAgentEngineering/comments/1wavu87/what_belongs_in_a_receipt_for_instructions/).
W Chrome zweryfikowano wpis w feedzie, autora `mwiatruZ`, pełną treść i 0 komentarzy przy pierwszym
odczycie. Opis społeczności wyklucza strategię marketingową i niskiej jakości treści LLM; wpis omawia
konkretny problem implementacji: różnicę między eksportem i potwierdzeniem odbioru, błędy hooka,
stare rewizje i duplikaty. Format receipt jawnie nazwano propozycją do dyskusji, nie wdrożonym
kontraktem. Autorstwo Guidefold, planowany SaaS i pomoc AI ujawnione; brak CTA sprzedażowego.
Skill positioning-and-copy ograniczył claims do tej granicy dowodowej. Nie zmieniono kontraktu produktu.

1. Zebrać odpowiedzi pod opublikowanym wątkiem Product Hunt.
2. Zweryfikować kolejne kanały; Cursor wymaga zalogowania i osobistego wkładu autora zgodnie z regulaminem.
3. Odblokowanie publikacji na Indie Hackers albo wykorzystanie istniejących dyskusji bez obchodzenia zasad.
4. Po pierwszych 10 rozmowach aktualizacja hipotez `paid_need`.
