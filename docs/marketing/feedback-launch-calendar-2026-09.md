# Kalendarz promocji i feedbacku — Guidefold

**Okres:** 8–22 września 2026  
**Model:** open source dziś; płatny SaaS jest hipotezą do walidacji  
**Główny cel:** znaleźć powtarzalny problem i pierwszych kandydatów do pilota, nie maksymalizować zasięgu.

## Zasady wykonania

- Główne demo każdej dozwolonej prezentacji: [Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c).
  CTA: obejrzyj i wskaż niejasny moment lub brakujący krok. Istniejące publikacje edytujemy, bez duplikatów.
- Harmonogram poniżej jest pierwotnym planem, nie kolejką automatycznej publikacji. Wykluczenia,
  moderacja i wymagania osobistego autorstwa w [statusie](feedback-campaign-status-2026-09.md) mają pierwszeństwo.
- Maksymalnie dwie nowe publikacje dziennie; pozostały czas przeznaczamy na odpowiedzi.
- Ten sam problem pokazujemy różnymi formatami, ale nie kopiujemy identycznego posta.
- Linkujemy do repozytorium jako dostępnego OSS. Hosted SaaS opisujemy jako planowany i niedostępny do zakupu; nie sugerujemy działającego early access.
- Nie prosimy o upvoty, sztuczne komentarze ani polecenia produktu osobom bez związku z problemem.
- Każdą osobę z konkretnym przykładem wpisujemy do [trackera](feedback-tracker-2026-09.csv).

## Harmonogram

| Dzień | Kanały | Zadanie | CTA | Dowód postępu |
|---|---|---|---|---|
| 8 Sep | Product Hunt Forum, OpenAI Developer Community | pytanie o właściwą rewizję i provenance | opisz ostatni przypadek | 2 odpowiedzi z kontekstem |
| 9 Sep | Cursor Forum, LangChain Forum | porównanie rules/context w różnych harnessach | wskaż etap, który dziś jest ręczny | 2 przykłady workflow |
| 10 Sep | LangGraph Discussions, Hugging Face Forums | techniczny demo-flow na fixture | zgłoś edge case | 1 test lub issue |
| 11 Sep | CNCF Slack, CNCF TAG Developer Experience | dyskusja o instruction drift w platform teamie | 15-min rozmowa | 1 rozmowa z P1 |
| 12 Sep | CNCF Community Groups, Platform Engineering Community | zaproszenie do krótkiej clinic/demo | zgłoś zespół do testu | 3 leady P1 |
| 13 Sep | MLOps Community, AI Tinkerers | case: export ≠ delivery proof | opisz wymaganie audytowe | 2 wymagania SaaS |
| 14 Sep | DEV Community, Hashnode | artykuł z kodem i ograniczeniami OSS | zapisz się na early access | 5 odpowiedzi lub 2 zapisy |
| 15 Sep | Lobsters, daily.dev | krótki technical note bez marketingu | skrytykuj podejście | 3 techniczne uwagi |
| 16 Sep | Hacker News | Show HN tylko jeśli demo jest bezbarierowe | uruchom i zgłoś problem | 1 realne użycie |
| 17 Sep | r/ClaudeCode, r/LLMDevs | pytania o CLAUDE.md i instruction provenance | podaj ostatni incident | 3 przykłady |
| 18 Sep | r/AIAgentEngineering, follow-up 1:1 | production agents i delivery evidence | rozmowa o pilocie | 1 kandydat P1 |
| 19 Sep | wszystkie aktywne rozmowy | odpowiedzi, korekta FAQ, grupowanie paid_need | wybierz najdroższy problem | 5 rekordów z paid_need |
| 20 Sep | Product Hunt Forum, 1:1 | pokazanie wniosków, bez nowej obietnicy | skomentuj, co jest niepełne | 3 jakościowe odpowiedzi |
| 21 Sep | wszystkie kanały | przypomnienie o jutrzejszym launchu i gotowość supportu | test OSS lub rozmowa | lista kontaktów i FAQ |
| 22 Sep | Product Hunt launch | obecność przez dzień launchu, odpowiedzi i demo | opisz problem / zgłoś pilot | ≥3 rozmowy P1/P2 |

## Bramka SaaS przed 22 września

Do dalszego projektowania płatnej wersji przechodzimy tylko wtedy, gdy mamy co najmniej 10 rozmów z P1/P2,
3 konkretne zdarzenia z ostatnich tygodni i 1 zgodę na test na zatwierdzonym repozytorium. Przy każdym
potencjalnym pilocie sprawdzamy: właściciela problemu, liczbę repozytoriów, liczbę harnessów, politykę danych,
potrzebę SSO/RBAC/audytu i oczekiwany następny krok. Brak tych danych oznaczamy jako `unknown`, nie jako
brak popytu.

## Raport po każdym dniu

```text
date:
new_channels:
meaningful_replies:
conversations_booked:
concrete_problem_events:
paid_need_counts:
new_pilot_candidates:
what_changed_in_copy:
what_we_still_do_not_know:
```
