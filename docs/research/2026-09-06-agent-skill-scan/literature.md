# Literatura: co zmienia decyzję Guidefold

Stan skanu: 2026-09-06; addendum: 2026-09-08. Źródła pierwotne, głównie preprinty; publikacja na arXiv nie jest potwierdzeniem recenzji. Przeczytano powiązaną rozmowę, ale jej twierdzenia porównano z kodem i źródłami. Nie zakładamy kompletności wyszukiwarki ani braku innych prac. Dokładne wersje poniżej wskazują zakres sprawdzenia.

| Praca / wersja sprawdzona | Nowy pomysł i ograniczenie dowodu | Guidefold: stan / decyzja |
|---|---|---|
| [Field-Aware Agent Skill Retrieval, v3, 1 IX](https://arxiv.org/html/2608.02880v3) | MLP łączy osobne sygnały pól. R@10:77,95 wobec73,61 na SkillRet;83,78 wobec76,52 na SRA. Rozdzielenie pól samo nie poprawia każdej metryki. | Mamy BM25F, nie tę wyuczoną fuzję. Wykonujemy osobny DEV-only spike z zamrożonym generic encoderem i trzema małymi heads. |
| [SkillRouter, v5](https://arxiv.org/html/2603.22455v5) | Body dostarcza informacji niewidocznych w metadanych. GPU encoder p95=20,8ms, pełny pipeline=871,4ms;80 timed queries, nie WAN/hook. | Full encoder i statyczny student to różne warianty. Wynik studenta nie zamyka dense. Reranker poza ścieżką300ms; istniejący remote Go zostaje. |
| [Skill2Query, v1, 17 VIII](https://arxiv.org/html/2608.16071v1) | Pseudozapytania oparte na capabilities/parametrach/examples; prawie30k skilli i700k query. Offline index augmentation, online expansion i trening to trzy różne zastosowania. | Nasz doc2query-T5 nie jest reprodukcją Skill2Query. Dobry następca badania po zamknięciu obecnego eksperymentu; nie uruchamiać generacji per hook. |
| [Skill Following, v1, 1 IX](https://arxiv.org/html/2609.00549v1) | RAE porównuje tę samą pracę ze skillem i bez, warunkowo na pobraniu. Ranking i pozorny aggregate lift mogą maskować szkodę. | Telemetria load nie wystarcza. E6.7 potrzebuje paired outcomes, helpful/harmful flips i zachowania bazowych instrukcji. Małe biblioteki autorów nie dowodzą skali30k. |
| [SkillZip: Contract-Preserving Graph Compression, v1](https://arxiv.org/html/2608.05604v1) | Sekcje i dependency closure/hydration. Mikrobenchmark pomija provider task-analysis; pomiar na serwerze Xeon/512GB. | Warto badać `/use`, ale nie wyciągać wniosku o lokalnym retrievalu na laptopie ani WAN<300ms. Samo skrócenie body bez sprawdzania wymagań jest inną metodą. |
| [SkillZip: Evaluation-Free Skill Compression, odrębna praca](https://arxiv.org/abs/2608.11079) | Konsolidacja powtarzanych reguł i procedur pod warunkiem zachowania kontraktu. | Nie mieszać z2608.05604 ani z destylacją embeddingu do tabeli słów. To osobny potencjalny eksperyment po MVP. |
| [SkillCenter, v1](https://arxiv.org/html/2607.07676v1) | Biblioteka ze źródłami; SQLiteFTS5 indeksuje title/domain. Full-body retrieval i systematyczny latency benchmark są na liście przyszłych prac. | Przydatne provenance i authoring gates. Brak powodu, żeby zastępować remote Go lokalnym SQLite na podstawie tej pracy. |
| [SkillReason](https://arxiv.org/abs/2608.08640) | Reasoning podczas treningu, zwykłe query embedding przy inferencji;61 228 skilli/3 729 zapytań. | Technicznie pasuje do remote warm encoder. Dostępność i jakość u nas niepotwierdzone; nie dokładamy drugiego treningu teraz. |
| [SkillDreamer / Imagine Before Retrieval](https://arxiv.org/abs/2609.01642) | Generuje potrzebne capabilities i pseudo-skille przed retrievalem. Autorzy zapowiadają kod po akceptacji. Historia arXiv:28 VIII mimo identyfikatora2609. | Hipoteza query-skill misalignment, potencjalny offline teacher. Brak dowodu spełnienia hook SLA. |
| [SkillPyramid](https://arxiv.org/abs/2606.03692) | Hierarchia i ponowne użycie procedur dla samodoskonalenia agenta. Eksperymenty ALFWorld/WebShop/ScienceWorld. | Repo hierarchy/ACL nie jest tą samą hierarchią. Nie uzasadnia nowej topologii ani learning loop w MVP. |
| [R3-Skill / Skill Is Not Document](https://arxiv.org/abs/2606.03565) | Compatibility zestawu zależy od zapytania, nie tylko od relevance pojedynczych elementów. | Gold list nie zawsze oznacza AND wszystkich skilli; paper musi rozdzielić wymagane elementy i alternatywy. Sam ranking nie waliduje zgodności instrukcji. |
| [More Skills, Worse Agents?](https://arxiv.org/abs/2605.24050) | Podobny skill może wypierać właściwy; ekspansja biblioteki może pogarszać wykonanie. | Zachować pomiar harmful-sibling exposure i downstream harm. HSR sam też nie wystarcza: nasz audyt pokazuje równocześnie regresję kompletności w stratum distractor. |

Wniosek z porównania: aktualna architektura remote Go jest zgodna z tymi kierunkami. Największą nową, małą zmianą badawczą jest wyuczona fuzja pól; największym obowiązkiem pomiarowym jest sprawdzenie faktycznego wpływu dostarczonych instrukcji. Nie ma podstaw, żeby ogłosić ogólną porażkę dense, kompresji lub kompozycji.

Ograniczenia reprodukcji Field-Aware: dostępny pełny tekst v3 nie opisuje szczegółowo architektury/loss/samplingu MLP i nie wskazuje kodu w przeczytanej treści. Nasze16hidden/BCE30epochs są jawną implementacją inspirowaną pracą. Paper używa6 660 skilli/4 997 test queries w SkillRet; przypięty korpus Guidefold ma inną rewizję:6 006/4 392. Wyników procentowych między tymi wersjami nie porównujemy bezpośrednio. Przeczytano v1 i aktualne v3; kluczowe wyniki i metoda pozostały zgodne.

## Addendum: skan 8 września 2026

| Praca | Granica dla naszej hipotezy |
|---|---|
| [SkillOps](https://arxiv.org/abs/2605.13716) | Ma już typed Skill Contract `(P,O,A,V,F)`, hierarchiczny graf i bibliotekową pętlę maintenance; GSCM nie może być przedstawiony jako pierwszy kontrakt ani graf. |
| [Formal Skill](https://arxiv.org/abs/2605.19604) | Przenosi procedurę do JSON/action schemas, executorów i runtime state; to konkurencja dla formatu/runtime, nie dla naszego library-time promotion gate. |
| [SkillGuard / Skill Drift Is Contract Violation](https://arxiv.org/abs/2605.10990) | Wykrywa role-bearing drift i ma osobny benchmark degradacji; URCT `C→C'` musi porównać się z tym typem monitoringu zamiast nazywać drift nowością. |
| [SkillZip](https://arxiv.org/abs/2608.05604) oraz [evaluation-free compression](https://arxiv.org/abs/2608.11079) | Contract-preserving compression i wyjątki są już deklarowanym celem; kandydat GSCM zawęża się do guarded meet przy promocji między gałęziami. |
| [Proof-Carrying Certificates](https://arxiv.org/abs/2605.16407) | Conflict-aware certificates i bilattice/NLI grounding ograniczają claim o „proof”; porównanie musi rozdzielić źródłową autoryzację od semantycznej ekstrakcji. |
| [SkillResolve-Bench](https://arxiv.org/abs/2606.10388) | Ma już 661 helpful/risky sibling pairs, harmful-sibling rate i query-conditioned representative selection; CGSR nie jest nowym rozwiązaniem same-capability ambiguity. Nasz test musi dodać source-grounded contract, provenance i drift, a wyniki porównać bezpośrednio z HSR. |

Wniosek: po tym skanie nie ma podstaw do claimu „nowy system skilli”. Jedyny
testowalny claim pozostaje wąski: czy guarded signed meet, jako etap między
źródłami a kartą nadrzędną, zmniejsza błędne promocje i zachowuje wyjątki na
source-disjoint, niewidzianych repozytoriach.

## Addendum: ekstrakcja lokalnym Qwenem, 8 września 2026

Literatura kontraktowa i proof-carrying nie usuwa ryzyka, że model źle zamieni
zdanie na atom. Dlatego zapisano osobny pilot ekstrakcyjny. Ścisły JSON na 16
parach źródeł miał 11 błędów parsowania i 0/16 `LOAD`; tabulatorowa ablacja
ujawniła kopiowanie literalnego `<TAB>`, a post hoc jego odzyskanie dało 8/16
`LOAD` bez fałszywego `LOAD`. Drugi odczyt modelu z kontrprzykładem pogorszył
warunek bezpieczeństwa: 2 lokalne wyjątki zostały przepuszczone jako `LOAD`.

Ten wynik wzmacnia granicę wskazaną przez [Proof-Carrying
Certificates](https://arxiv.org/abs/2605.16407), [WiCER](https://arxiv.org/abs/2605.07068)
i [PCN-Rec](https://arxiv.org/abs/2601.09771): weryfikator może wykrywać
sprzeczność, lecz nie powinien ufać swobodnej naprawie bez niezależnego
świadectwa źródłowego. GSCM pozostaje kandydatem na fail-closed promotion gate;
pilot nie uzasadnia claimu o jakości ekstrakcji, transferze ani przełomie.

## Addendum: scope-complete routing, 8 września 2026

SC-PPACR jest implementacyjną odpowiedzią na lukę ujawnioną w pipe-format
checku: sam podpis atomu nie mówi, czy pokrywa cały żądany zakres. Wariant
rozszerza cel dowodu do `(requirement, requested_scope)` i dopuszcza
kompozycję kart tylko wtedy, gdy suma świadectw pokrywa wszystkie takie pary.
Nie jest to claim nowego kontraktu ani nowego formatu skilla — typed contracts,
contract-preserving compression i proof-carrying certyfikaty mają już
odpowiedniki w literaturze. Kandydat na różnicę to połączenie anchor-safe
retrieval, source-line proof i fail-closed scope coverage na etapie promocji
abstrakcji.

Oracle replay na 12 przypadkach dał 7/12 kompletnych bundle przy 0
nieobsługiwanych elementów dowodu, wobec 6/12 w jedno-kartowym ECCR. To mały
wynik polityki z etykietami recenzentów; pakiet nie ma etykiet scope ani
wykonania. Wniosek publikacyjny pozostaje warunkowy do source-disjoint URCT,
niezależnej oceny scope i parowanego wykonania po zmianie `C→C'`.

Macierz kernela (3 600 dwu-kartowych kombinacji) potwierdziła tę konkretną
różnicę: SC-PPACR miał 0 false-load i 0 false-ask względem niezależnego oracle,
podczas gdy PPACR bez osi scope miał 862 false-load. Jest to gwarancja dla
skończonej reprezentacji etykiet, nie dowód, że model poprawnie odczytuje
zakres z tekstu.

## Addendum: real-source URCT inventory, 8 września 2026

Pierwszy inwentarz rzeczywistych `SKILL.md` obejmuje trzy rodziny i 12
snapshotów w układzie `A/B/C/C'`, z hashami, rewizjami, drift edit i audytem
5-gramów. Integralność techniczna przeszła niezależną kontrolę, ale bramka
niezależności nie przeszła: źródła `A` i `B` mają wspólnego właściciela GitHub
`cloudfloo`. To ogranicza siłę przyszłego claimu transferu; zero overlapu
leksykalnego nie zastępuje niezależności autorstwa. Inventory jest więc
przygotowaniem protokołu i nie wnosi nowej metryki retrieval ani wykonania.

Pakiet adnotacji ma sześć anonymized cases, po dwóch pustych formularzach i 15
pól na przypadek; jego verifier blokuje wywołania modelu do czasu niezależnej
oceny. To procedura kontroli jakości inspirowana wymaganiem source-grounding,
a nie nowa metoda ani wynik skuteczności.

Najnowszy skan dużych korpusów zmienia też wymaganie dotyczące danych. [GitSkills
(arXiv:2608.10906)](https://arxiv.org/abs/2608.10906) grupuje prawie 1,9 mln
unikalnych treści `SKILL.md` i zapisuje pochodzenie oraz historię wybranych
plików, a [What Keeps Agent Skills from Being Reusable?
(arXiv:2608.08453)](https://arxiv.org/abs/2608.08453) wiąże poprawne metadane
routingu z lepszą niezawodnością wyboru w dużym stres teście. To wzmacnia
potrzebę hashy, owner splitu i testu routing→use w Guidefold, ale nie daje
gotowego claimu transferu ani jakości instrukcji. URCT-2 jest małym,
źródłowo przypiętym pilotem, a nie próbą konkurowania z tymi korpusami skalą.

URCT-2 usuwa wspólnego właściciela w źródłach pilota: sześć zdalnych plików
pochodzi od sześciu różnych kont GitHub i jest przypiętych do commitów. To
poprawia wiarygodność splitu `A/B→C`, lecz nie zastępuje sprawdzenia licencji,
anty-copy ani niezależnej oceny semantycznej. W literaturze o skill mining i
reusability taki filtr pochodzenia powinien być raportowany jako kontrola
leakage, nie jako dowód transferu.

W warstwie metodycznej recursive-scope PCL nie powinien być opisywany jako
„nowa hierarchia” sama w sobie. Jego wąska różnica względem prac o provenance,
typed contracts i drift to nieeskalujący eksport scope z dziecka do rodzica,
z dokładnym proof path i quorum na każdym poziomie. Skończona macierz (22 500
wariantów, 0/0 błędów kernela wobec oracle) uzasadnia twierdzenie warunkowe;
URCT-2 musi dopiero sprawdzić, czy ta własność przetrwa ekstrakcję tekstu i
wykonanie zadania.

## Addendum: pozycjonowanie PFR wobec nowszej literatury, 8 września 2026

Nowsze prace poszerzają zakres porównania. [Skill Retrieval Augmentation for
Agentic AI (SRA)](https://arxiv.org/abs/2604.24594) rozdziela retrieval,
incorporation i end-task execution na SRA-Bench; sam poprawny kandydat nie
gwarantuje jeszcze poprawnego załadowania. [SkillTrace](https://arxiv.org/abs/2608.05204)
łączy ślady ekspresji, implementacji i operacji, a audyt wykonuje
deterministycznie po ekstrakcji w ingestion. [From Agent Traces to
Trust](https://arxiv.org/abs/2606.04990) wskazuje claim-level provenance i
execution-trace benchmarks jako otwarte problemy.

To zawęża, a zarazem wyostrza pozycję naszego wyniku: PFR nie jest nowym
retrieverem ani ogólną metodą provenance. Jego testowalna różnica to
nieeskalujący eksport scope z rekurencyjnego child proof połączony z twardym
rozstrzyganiem funkcjonalnych siblingów przed użyciem. Macierz 139 968
przypadków daje 0/0 błędów wobec niezależnego oracle, ale jest tylko gwarancją
jądra kontraktowego. Publikacyjny claim wymaga jeszcze URCT-2: niezależnej
adnotacji, source-disjoint transferu i sparowanego wykonania na `C/C'`.
