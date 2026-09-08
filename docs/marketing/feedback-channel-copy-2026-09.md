# Copy kit — 20 kanałów

Wspólny disclosure: **Guidefold jest dziś open source; wersję SaaS dopiero sprawdzamy.** Każdy tekst należy
dopasować do aktywnego wątku i regulaminu kanału. CTA prowadzi do przykładu problemu, fixture albo rozmowy —
nie do głosowania.

## Demo-first — aktualizacja 2026-09-08

Główne demo: https://www.youtube.com/watch?v=e350wBr1W8c

W każdej dozwolonej prezentacji umieszczamy ten film po krótkim wyjaśnieniu problemu i Guidefold,
przed prośbą o instalację. Gdy platforma ma pole video, dodajemy film także tam. Nie wymagamy
kontaktu, maila ani instalacji, żeby obejrzeć demo. Film nie jest dowodem użycia w produkcji.
Tabela poniżej to pomysły redakcyjne, **nie zgoda na publikację**: wykluczenia i ograniczenia
z [aktualnego statusu](feedback-campaign-status-2026-09.md) mają pierwszeństwo. Nie publikować
tych tekstów na kanałach wymagających samodzielnego tekstu człowieka lub zakazujących promocji AI.

### Product Hunt — opis premiery

Your repo instructions changed. Did your coding agent get the right revision? Guidefold keeps instructions beside the code and selects them by directory, with Git as the source of truth. Watch the demo, then tell us which step you would need to verify in your own monorepo. Open source is available now; paid SaaS is planned, not available yet. Demo: https://www.youtube.com/watch?v=e350wBr1W8c

### Reddit / Indie Hackers — problem, rozwiązanie, pytanie

Your team changed its agent instructions. Checking what the next session received is still a separate job.

I'm building Guidefold to keep instructions beside the code and select them by repository location. Git stays the source of truth.

[Watch the demo](https://www.youtube.com/watch?v=e350wBr1W8c). Which step would you need to check in your own repo? If something is unclear, share a timestamp and the question it raised.

[Source and setup](https://github.com/wiatrM/guidefold). The open-source version is available now. A paid hosted version is planned, not shipped. I'm the author; please keep examples free of private code or credentials.

Wariant Indie Hackers pozostaje szkicem do odblokowania publikacji. Na Reddicie używaj właściwego
wątku showcase; nie zastępuj technicznej dyskusji identycznym tekstem sprzedażowym.

### Kanały techniczne — dopisek do istniejącej dyskusji

For project context, [here is the Guidefold demo](https://www.youtube.com/watch?v=e350wBr1W8c). It isn't evidence that an agent followed an instruction. Which additional check would you need between export and an acknowledged delivery?

### Testerzy — wejście bez instalacji

You can start with [the demo](https://www.youtube.com/watch?v=e350wBr1W8c), without installing anything. Where does the workflow first become unclear? A timestamp is enough. If you want to try the OSS version, use the fictional example repository first, not private or production code.

### X — szkic na wskazany profil, nie opublikowano

Your repo instructions changed. Did your coding agent get the right revision?

I'm building Guidefold: Git-native instructions for monorepos. OSS is available; paid SaaS is planned.

Demo: https://www.youtube.com/watch?v=e350wBr1W8c

Which step needs a clearer explanation?

Nie aktywować automatyzacji bez wskazanego konta. Kolejne wpisy mają wnosić nową obserwację;
sam film nie uzasadnia codziennego powtarzania identycznej reklamy.

| # | Kanał | Otwarcie | Pytanie feedbackowe | CTA |
|---:|---|---|---|---|
| 1 | Product Hunt Forum | „Guidefold is open source today; we’re exploring a paid SaaS for teams managing agent instructions.” | „Which would matter first: shared history, approvals, audit, or delivery proof?” | „Share a recent example.” |
| 2 | OpenAI Developer Community | „How do you keep repository instructions traceable across Codex/API workflows?” | „Where do you lose confidence: scope, revision, or delivery?” | „Compare your workflow with the OSS CLI.” |
| 3 | Cursor Forum | „For teams using Cursor rules in a monorepo, what is your source of truth after a rule changes?” | „How do you know the current directory received the intended rules?” | „Describe the last manual check.” |
| 4 | LangChain Forum | „Agent context can be versioned in Git, but export alone does not prove delivery.” | „What evidence do you keep that the intended context was loaded?” | „Point to the step you would automate.” |
| 5 | LangGraph Discussions | „We are testing a small OSS flow for scoped instructions and revision evidence.” | „Which event would belong in an agent audit trail?” | „Suggest one edge case.” |
| 6 | Hugging Face Forums | „Show and Tell: Guidefold maps repository instructions to a directory without replacing Git.” | „What would make this useful in your model/app workflow?” | „Try it on a safe fixture.” |
| 7 | CNCF Slack | „Platform teams now own more agent context; how are you reviewing changes to it?” | „Who owns scope and delivery checks in your organisation?” | „Reply in the existing relevant channel.” |
| 8 | CNCF TAG DevEx | „Instruction drift looks like a developer-experience problem when every harness resolves context differently.” | „What would you measure to detect it?” | „Join a short practitioner conversation.” |
| 9 | CNCF Community Groups | „I’m collecting real examples of agent instructions changing inside platform repositories.” | „What did the team need to verify after the change?” | „Volunteer a 15-minute clinic example.” |
| 10 | Platform Engineering Community | „What happens between approving a platform instruction and an agent using it?” | „Which SaaS capability would remove the most manual work?” | „Rank one capability and explain why.” |
| 11 | MLOps Community | „Exported config is not the same as evidence that production received it.” | „Where does provenance stop in your current agent pipeline?” | „Share the control you already use.” |
| 12 | AI Tinkerers | „I’m building a small OSS tool to inspect which instructions match a repo directory.” | „What should a 10-minute demo prove to you?” | „Bring one workflow question.” |
| 13 | DEV Community | „The awkward part of agent instructions is not writing them; it is knowing which ones apply.” | „How do you review scope in a large repository?” | „Read the technical walkthrough and comment with a counterexample.” |
| 14 | Hashnode | „Why export is not proof of delivery: a Git-native look at agent instruction provenance.” | „Would hosted history or access control solve a real team problem?” | „Add your architecture constraint.” |
| 15 | Lobsters | „A small open-source CLI for discovering scoped instructions in a monorepo.” | „What is the smallest useful evidence record for an agent run?” | „Critique the design or implementation.” |
| 16 | Hacker News | „Show HN: Guidefold — Git-native instruction discovery for monorepo teams.” | „Does this solve a problem you have, or is the abstraction wrong?” | „Run the demo and report one failure.” |
| 17 | daily.dev | „Which repository rules did your coding agent actually read today?” | „How could a team check that without relying on guesswork?” | „Reply with tool and repo shape.” |
| 18 | r/ClaudeCode | „Where do CLAUDE.md changes get hard to reason about when a repo has nested directories?” | „What do you check before trusting a changed instruction?” | „Describe the last confusing case.” |
| 19 | r/LLMDevs | „Instruction provenance is becoming an engineering concern, not just a prompt concern.” | „What should be logged when an agent loads repository context?” | „Challenge the model with a production example.” |
| 20 | r/AIAgentEngineering | „For production agents, what counts as proof that the intended instruction revision was delivered?” | „Which control would your team pay to remove from the manual process?” | „Share a concrete incident or constraint.” |

## Follow-up sequence

**Po odpowiedzi ogólnej:** „Dzięki — czy możesz opisać ostatni konkretny przypadek, bez wrażliwego kodu?”

**Po przykładzie:** „To brzmi jak problem na granicy [scope/review/delivery]. Jak rozwiązujecie go dziś i kto
jest właścicielem tego procesu?”

**Po zainteresowaniu SaaS:** „Open source pokrywa dziś lokalny przepływ. Który element hostowany musiałby
działać pierwszy, żebyście użyli go w zespole, i jakie ograniczenia danych musiałby spełnić?”

**Po zgodzie na test:** „Zacznijmy od fixture albo zatwierdzonego, nie wrażliwego repo. Ustalimy jeden
scenariusz, oczekiwany dowód i kryterium zakończenia.”
