# Guidefold Agent Skills Research Registry

**Kanoniczny, stale aktualizowany katalog prac naukowych, modeli, datasetów i implementacji związanych z agent skills.**

- Prezentacja rekomendowana, prostym językiem (60 slajdów): [Instrukcje dla agentów — od podstaw do produktu](Guidefold-Agent-Skills-Research-Prosto-PL-2026-09-04.pptx)
- Prezentacja skrócona, techniczna: [Guidefold Agent Skills — research, modele i plan wdrożenia](Guidefold-Agent-Skills-Research-2026-09-04.pptx)
- Ostatnia aktualizacja: **4 września 2026**
- Zakres: retrieval, routing, composition, orchestration, procedural memory, evolution, consolidation, compression, evaluation, bezpieczeństwo i produkcyjne serving
- Źródła priorytetowe: arXiv, repozytoria autorów, Hugging Face, oficjalne materiały konferencyjne
- Statusy: `reuse now`, `reproduce`, `watch`, `blocked by license/artifacts`
- Reguła utrzymania: dopisywać datę publikacji i rewizji, link do źródła pierwotnego, kod/model/dataset, licencję, najważniejszy wynik, ograniczenia i decyzję dla Guidefold

Research został wykonany równolegle przez agentów analizujących publikacje, publiczne artefakty ML oraz obecny kod Guidefold. Plik ma być pojedynczym źródłem prawdy dla kolejnych przeglądów literatury. Nie tworzyć osobnych raportów datowanych, jeśli nowy materiał mieści się w tym zakresie.

## Decyzja w skrócie

Nie budować od zera dużego „modelu Guidefold”. Najszybsza droga to **Guidefold Router 0.1**: wymienne retrievery i rerankery 0.6B, field-aware hybrid retrieval, twarde polityki, graph-constrained composition oraz rygorystyczny paired evaluation. Publiczne modele są akceleratorem. Przewagę tworzą dane Guidefold:

- query + scope + stan repozytorium;
- pełna lista kandydatów, score'y i wybrany uporządkowany bundle;
- zależności, konflikty i wymagane uprawnienia;
- wynik wykonania względem kontroli `no-skill`;
- model/harness/version, tokeny, latency i kroki;
- decyzje ownerów, przyczyny odrzucenia, rollbacki i historia wersji;
- pochodzenie skilla i możliwość kaskadowego unieważnienia.

Największe uzupełnienia wobec obecnego projektu to:

1. **Field-aware retrieval** zamiast konkatenowania całego `SKILL.md` do jednego dokumentu.
2. **Kompatybilność bundle'a** i możliwość `SKIP/CONFLICT`, nie tylko relevance pojedynczego skilla.
3. Pośrednia warstwa **persistent knowledge** między surowym trace'em a wykonywalnym skillem.
4. Ewolucja evidence-gated z replayem, kontrolą regresji, probation i rollbackiem.
5. Bezpieczeństwo semantycznego supply chain: provenance, sandbox, skanowanie i kill switch.

## Co rzeczywiście istnieje dziś w Guidefold

Guidefold jest działającym prototypem Git-native discovery i dystrybucji, ale nie systemem ML.

- Lokalny „semantic search” to suma wystąpień słów w opisie, digescie i body, bez BM25, embeddingów i IDF: [`guidefold`](../skills/guidefold/scripts/guidefold#L240).
- `rank_cards` wkłada exact scope i ancestors przed semantic hits przez `setdefault`; semantyka nie może ich przestawić: [`guidefold`](../skills/guidefold/scripts/guidefold#L306).
- `index` generuje wyłącznie hierarchiczny Markdown, nie cards/BM25/vectors/graph: [`guidefold`](../skills/guidefold/scripts/guidefold#L433).
- Cache body jest kluczowany URN-em, a nie `(URN, revision)`: [`guidefold`](../skills/guidefold/scripts/guidefold#L178).
- `validate` nie obsługuje jeszcze `kind`, `layer`, `topics`, triggers, probation ani limitów jakości body: [`guidefold`](../skills/guidefold/scripts/guidefold#L332).
- Nie istnieje katalog testów; README nadal opisuje go jako planowany: [`README.md`](../README.md#L32).
- Docelowy Knowledge Plane, SkillRouter i SkillPyramid są projektem `Draft v0.1`, nie implementacją: [`KNOWLEDGE-DESIGN.md`](KNOWLEDGE-DESIGN.md#L1).

To ważne dla eksperymentów: obecny scope-first ranking powinien być **B0**, a nie docelowym baseline'em produkcyjnym.

## Najnowsze i najbardziej użyteczne prace

Gotowość: **5/5** = uruchomić pilota teraz; **3/5** = odtworzyć metodę; **1/5** = obserwować.

| Data | Praca | Najważniejsza idea lub wynik | Znaczenie dla Guidefold | Gotowość |
|---|---|---|---|---:|
| 2026-09-02 | [MASkills](https://arxiv.org/abs/2609.02094) | Skill-conditioned credit assignment, hierarchiczna agregacja, momentum-smoothed refinement/induction/consolidation/pruning; HotpotQA, LoCoMo, GAIA; [kod](https://github.com/DaRL-GenAI/MASkills). | Najnowszy wzorzec okresowego consolidation job i credit assignment. | 3/5 |
| 2026-09-01, v3 | [Field-Aware Agent Skill Retrieval](https://arxiv.org/abs/2608.02880) | Oddzielne sparse+dense scores dla pól skilla, łączone wagami lub małym MLP; 77.95 Recall@10 na SkillRet i 83.78 na SRA-Bench. | **Najtańsza istotna innowacja do natychmiastowego odtworzenia.** | 5/5 |
| 2026-09-01, v3 | [SkillRet](https://arxiv.org/abs/2605.05726) | 16,129 publicznych skills, 63,259 train samples, 4,392 eval queries; fine-tuning +12.9 NDCG@10 nad najmocniejszym wcześniejszym retrieverem. | Publiczny benchmark, dane i checkpointy do pierwszej macierzy testów. | 5/5 |
| 2026-08-28 | [SkillDreamer](https://arxiv.org/abs/2609.01642) | Najpierw przewiduje potrzebne capabilities i generuje pseudo-skills, aby zniwelować mismatch query–skill, dopiero potem wyszukuje. | Prototyp prompt-side dla niejasnych zadań; kod zapowiedziany „upon acceptance”. | 2/5 |
| 2026-08-27 | [WikiSkill](https://arxiv.org/abs/2608.27454) | Rozdziela surowe wykonania, trwałą wiki wiedzy i wykonywalne skills; raportuje transfer między rodzinami modeli. | Brakująca warstwa `knowledge_unit` pomiędzy trace'em a skill PR. | 4/5 |
| 2026-08-27 | [PILOT](https://arxiv.org/abs/2608.26530) | Supervisor steruje wykonaniem na żywo i aktualizuje pamięć/skills; Terminal-Bench +9.8 pp oraz duże redukcje tokenów dla części modeli. | Późniejszy runtime supervisor; nie blokuje MVP control plane. | 3/5 |
| 2026-08-12 | [Agent Skills Can Be Harmful](https://arxiv.org/abs/2608.11888) | Differential testing przypisał 307 porażek konkretnym skills: 125 funkcjonalnych i 182 kosztowe. | Obowiązkowy gate `no-skill / selected / wrong sibling / oracle`. | 5/5 |
| 2026-08-11 | [MERA](https://arxiv.org/abs/2608.10333) | Wspólna ewolucja SkillBook, LoRA małego modelu i cost routera; Qwen2.5-Coder-1.5B 28.7%→49.7%; [kod](https://github.com/zeyuyuyu/router-skills-evolve). | Późniejszy tani local model z eskalacją do dużego modelu. | 4/5 |
| 2026-08-09 | [What Keeps Agent Skills from Being Reusable?](https://arxiv.org/abs/2608.08453) | 138,133 skills; 91.8% ma co najmniej jeden wykryty defekt w routingu, body lub resource organization. | Bezpośrednia specyfikacja nowych lintów `guidefold validate`. | 5/5 |
| 2026-08-06 | [SkillHEX](https://arxiv.org/abs/2608.05628) | Evidence-guided tree search nad konkurencyjnymi hipotezami przyczyn błędu. | Kandydaci lift/repair powinni mieć falsyfikowalną hipotezę i test. | 3/5 |
| 2026-08-04 | [ContinualSkillBench](https://arxiv.org/abs/2608.03874) | 5 domen × 100 powiązanych zadań; długie ICL bywa równie dobre jak jawna biblioteka; [kod](https://github.com/gtynnn060110-hash/continual-skill-bench-final). | Mierzyć transfer po wyczyszczeniu kontekstu, nie efekt historii rozmowy. | 4/5 |
| 2026-08-04, v5 | [R3-Skill](https://arxiv.org/abs/2606.03565) | 10,246 skills, zaakceptowane i odrzucone kombinacje; 75.39% Hit@1, 81.97% NDCG@10, 33.27% Set-Compat; [kod](https://github.com/Tencent/R3-Skill). | **Najważniejsze uzupełnienie SkillRoutera:** relevance + compatibility + `SKIP`. | 5/5 |
| 2026-07-24 | [The Regression Tax](https://arxiv.org/abs/2607.22520) | Prawie 6,000 uruchomień; dobre skills wygrywają często dlatego, że mniej regresują. | Raportować gain rate i regression rate osobno. | 5/5 |
| 2026-07-20, v5 | [SkillRouter](https://arxiv.org/abs/2603.22455) | Full-body retrieve+rereank na puli ~80K; 74% Hit@1; usunięcie body kosztuje 37–44 pp; encoder i reranker po 0.6B. | Najszybszy released baseline, nie przewaga sama w sobie. | 5/5 |
| 2026-07-18 | [From Memory to Skills / MSCE](https://arxiv.org/abs/2607.16621) | Promuje ślady do skills wyłącznie przy dodatnim evidence-backed gain. | `lifted_from`, applicability boundary, verifier result, reliability. | 4/5 |
| 2026-07-07 | [Task Decomposition-Guided Reranking](https://arxiv.org/abs/2607.06283) | Rozkłada query i skills do stanów/krawędzi DAG przed rerankingiem. | Dekompozycja wielointentowych promptów przed wyborem bundle'a. | 3/5 |
| 2026-06-30 | [Generative Skill Composition](https://arxiv.org/abs/2606.32025) | Wspólnie przewiduje subset, liczbę i kolejność skills; +23.1 pp GPT-5.2-Codex i +18.2 pp Gemini-3-Pro vs no-skill. | Model sekwencyjny dopiero po zebraniu własnych successful bundles. | 3/5 |
| 2026-06-04 | [SkillComposer](https://arxiv.org/abs/2606.06079) | Wyuczone operacje `create`, `improve`, `merge`; SkillComposer-4B daje +4.5 pkt executorowi 27B na agent tasks. | API offline consolidatora; brak publicznych wag/kodu. | 3/5 |
| 2026-06-02 | [SkillPyramid](https://arxiv.org/abs/2606.03692) | Atomic extraction, abstract induction, jawne zależności i task-driven evolution; +38% średniej nagrody, −27.7% kroków. | Odtworzyć hierarchiczną konsolidację, ale nie uzależniać produktu od brakujących artefaktów. | 3/5 |
| 2026-05-31 | [SkillRevise](https://arxiv.org/abs/2606.01139) | Trace-conditioned repair + ponowne wykonanie + verifier; 36.05%→61.63% na SkillsBench. | Automatycznie otwierać PR po failure, nigdy bez replayu. | 4/5 |
| 2026-05-18 | [HASP](https://arxiv.org/abs/2605.17734) | Kompiluje tekstowe skills do Program Functions aktywowanych w ryzykownych stanach. | Deterministyczne guardraile i corrective hooks dla `program` skills. | 3/5 |
| 2026-04-22 | [SkillLearnBench](https://arxiv.org/abs/2604.20087) | Self-feedback prowadzi do recursive drift; zewnętrzny feedback i wiele iteracji pomagają; [kod](https://github.com/cxcscmu/SkillLearnBench). | Zakaz automatycznego auto-merge bez niezależnego verifiera/człowieka. | 5/5 |
| 2026-04-07 | [Graph-of-Skills](https://arxiv.org/abs/2604.05333) | Hybrid seeding, reverse PPR i budgeted hydration; do +25.55% reward i −56.72% tokenów; [kod](https://github.com/davidliuk/graph-of-skills). | Najbliższa gotowa implementacja warstwy grafowej Guidefold. | 5/5 |
| 2026-04-02 | [CoEvoSkills](https://arxiv.org/abs/2604.01687) | Generator i surrogate verifier współewoluują bez test-answer leakage; [kod](https://github.com/Zhang-Henry/CoEvoSkills). | Wzorzec kandydatów promotion PR i ochrony benchmarku. | 4/5 |
| 2026-03-26 | [Trace2Skill](https://arxiv.org/abs/2603.25158) | Równoległa destylacja trajectories do wspólnego SOP; duże zyski na WikiTableQuestions. | Offline mining powtarzalnych workarounds/failures. | 3/5 |
| 2026-03-19 | [Memento-Skills](https://arxiv.org/abs/2603.18743) | Trainable router + rozdzielone read/write evolution Markdown skills; [kod](https://github.com/Memento-Teams/Memento-Skills). | Dobra referencja dla read-path vs write-path. | 4/5 |
| 2026-02-13 | [SkillsBench](https://arxiv.org/abs/2602.12670) | 87 zadań; curated skills średnio 33.9%→50.5%, ale niektóre pogarszają wynik; małe focused bundles są lepsze; [kod](https://github.com/benchflow-ai/skillsbench). | Publiczny paired benchmark i argument za bundle ≤4. | 5/5 |
| 2026-02-09 | [SkillRL](https://arxiv.org/abs/2602.08234) | Hierarchiczny SkillBank współewoluuje podczas RL; >15.3% nad baseline'ami; [kod](https://github.com/aiming-lab/SkillRL). | Pełny otwarty research stack, ale za ciężki na pierwszy krok. | 4/5 |
| 2026-02-02 | [MemSkill](https://arxiv.org/abs/2602.02474) | Controller wybiera extraction/consolidation/pruning, designer rozwija zestaw; [kod](https://github.com/ViktorAxelsen/MemSkill). | Selekcja trace'ów zasługujących na knowledge lift. | 4/5 |

### Dalsze ważne pozycje

- [Recuris](https://arxiv.org/abs/2608.24876) i [kod](https://github.com/Gen-Verse/Recuris): osobna pamięć robocza śledzi stan zadania i dobiera skills z pamięci doświadczeń; validation-gated, lokalne aktualizacje Skill Memory. Bardzo trafne dla długich harnessów i lokalizacji źródła błędu.
- [HyperSkill](https://arxiv.org/abs/2608.16114): hypergraph łączy subtasks i skills występujące w tych samych trajektoriach; dual-path retrieval wykorzystuje podobieństwo i współwystępowanie. Trafna referencja dla hiperkrawędzi reprezentujących całe udane bundle'e.
- [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401): dla większości z 49 specjalistycznych skills efekt był zerowy; wybrane skills dawały duże zyski, a wersyjnie niedopasowane powodowały regresje. Wniosek: time/version-aware eval i kontrola bez skilla.
- [Skills in the Wild / SkillUsage](https://arxiv.org/abs/2604.04323): przy realistycznej puli ok. 34K korzyści są kruche; query-specific refinement pomaga. Wniosek: wynik z małej, czystej puli nie wystarcza.
- [GoSkills](https://arxiv.org/abs/2605.06978): group-structured retrieval i role `Start/Support/Check/Avoid`. Wniosek: role i grupy są dobrym etapem przejściowym przed generatywnym composerem.
- [SkillResolve-Bench](https://arxiv.org/abs/2606.10388): wybór bezpiecznego reprezentanta w rodzinie pomocnych/ryzykownych skills. Wniosek: hard sibling negatives i harmful-sibling rate.
- [AgentSkillOS](https://arxiv.org/abs/2603.02176): hierarchiczna organizacja i DAG orchestration przy skali do 200K skills. Wniosek: systemowa referencja dla graph planner.
- [Skill Self-Play](https://arxiv.org/abs/2607.22529) i [kod](https://github.com/Qwen-Applications/skill-self-play): współewolucja proposer/solver/controller. Dobre laboratorium, zbyt kosztowne na MVP.
- [Skill-α](https://arxiv.org/abs/2608.01678) i [kod](https://github.com/ejhshen/skill-alpha): jawne `CREATE/UPDATE/MERGE/PRUNE/NOOP` i rollback-aware reward. Użyć jako kontraktu operacji write-path.
- [SkillProx](https://arxiv.org/abs/2608.07449): closed-loop diagnosis, leave-one-out utility i rollback. Użyć do późniejszego pruning job.
- [SkillEvo](https://arxiv.org/abs/2608.13120): multi-turn feedback i governance repair faktów/bloat. Użyć do PR review loop.
- [SkillZip](https://arxiv.org/abs/2608.11079): evaluation-free compression z twardym zachowaniem coverage. Użyć jako `Zip-on-Write`, ale zawsze z golden replay.
- [VCE-Skill](https://arxiv.org/abs/2608.16544): wykorzystuje doświadczenia ze zmian wersji. Guidefold może mieć tu naturalną przewagę dzięki Git history.
- [ERSkill](https://arxiv.org/abs/2608.12720): osobna capability frontier i deploy frontier. Odpowiada rozdzieleniu eksperymentów od `probation/blessed`.
- [SkillMaster](https://arxiv.org/abs/2605.08693): counterfactual utility probes i DualAdv-GRPO. Późniejszy mechanizm utility learning.
- [SkillOpt](https://arxiv.org/abs/2605.23904): bounded text-space edits z held-out validation i zerowym kosztem inference po optymalizacji. Praktyczny offline optimizer.
- [EvoDS](https://arxiv.org/abs/2606.03841) i [kod](https://github.com/usail-hkust/EvoDS): specjalistyczny przykład ewolucji skillów dla data science.
- [SkillForge](https://arxiv.org/abs/2604.08618): Domain-Contextualized Skill Creator oraz Failure Analyzer, Diagnostician i Optimizer na danych wsparcia chmurowego. Przykład tego, dlaczego firmowe tickety i knowledge base są cenniejsze niż ogólny corpus.
- [SkillFoundry](https://arxiv.org/abs/2604.03964): kompiluje heterogeniczne repozytoria, API, notebooki, dokumentację i publikacje do testowalnych skill packages z provenance. Dobra referencja dla mining/compilation pipeline.
- [SkillFlow](https://arxiv.org/abs/2605.14089): trainable supervisor, Tempered Trajectory Balance i backward policy do credit assignment oraz ewolucji. Późniejszy kierunek, gdy Guidefold będzie miał reward i pełne trajectories.
- [SkillOrchestra](https://arxiv.org/abs/2602.19672) i [kod](https://github.com/jiayuww/SkillOrchestra): modeluje kompetencję i koszt różnych agentów per skill, zamiast wybierać model wyłącznie z query. Przydatne dla warstwy skill-to-model routing.
- [Agent Skill Evaluation and Evolution Survey](https://arxiv.org/abs/2606.11435) i [żywy katalog](https://github.com/Cassie07/AgentSkill_Survey): taksonomia creation, retrieval, management, execution-feedback evolution, trajectory distillation, compression i RL. Używać jako źródło nowych pozycji do kolejnych aktualizacji tego rejestru.

## Bezpieczeństwo i jakość są częścią modelu produktu

- [Agent Skills in the Wild](https://arxiv.org/abs/2601.10338) analizuje 31,132 skills i raportuje podatności oraz artefakty jawnie złośliwe. Skille ze skryptami są szczególnie ryzykowne.
- [SkillJack](https://arxiv.org/abs/2608.03509) pokazuje, że zatrute doświadczenie może zostać skonsolidowane w trwały skill, a atak przetrwać usunięcie pierwotnego źródła.
- [Under the Hood: Semantic Supply-Chain Attacks](https://arxiv.org/abs/2605.11418) pokazuje ataki na discovery, selection i governance. Full-body routing nie może traktować body jako zaufanych instrukcji.
- [ClawsBench](https://arxiv.org/abs/2604.05172) mierzy oddzielnie skuteczność i niebezpieczne zachowania. Guidefold również musi utrzymywać osobne quality i safety gates.

Minimalne mechanizmy: podpisane pochodzenie, `source_revision`, immutable audit, kaskadowe revoke, policy filter przed modelem, skan sekretów i injection, sandbox replay, canaries oraz możliwość unieważnienia wszystkich potomków `lifted_from`.

## Publiczne modele i zbiory na Hugging Face

### Reuse now

| Artefakt | Licencja / rozmiar | Rola | Decyzja |
|---|---|---|---|
| [SkillRouter-Embedding-0.6B](https://huggingface.co/pipizhao/SkillRouter-Embedding-0.6B) | Apache-2.0, 0.6B BF16, ok. 1.19 GB wag | Full-body first-stage retrieval | P0 baseline, pin commit SHA. |
| [SkillRouter-Reranker-0.6B](https://huggingface.co/pipizhao/SkillRouter-Reranker-0.6B) | Apache-2.0, 0.6B BF16, ok. 1.19 GB | Cross-encoder top-K reranking | P0 baseline; brak hosted inference providera. |
| [R3-embedding-0.6b](https://huggingface.co/tencent/R3-embedding-0.6b) + [R3-rerank-0.6b](https://huggingface.co/tencent/R3-rerank-0.6b) | Publiczne checkpointy powiązane z R3-Skill | Recall + query-conditioned compatibility | P0, test obok SkillRouter. |
| [SKILLRET-Embedding-0.6B](https://huggingface.co/ThakiCloud/SKILLRET-Embedding-0.6B) | Apache-2.0, 0.6B BF16 | Retriever dostrojony na SkillRet | P0 trzeci kandydat. |
| [SKILLRET-Embedding-8B](https://huggingface.co/ThakiCloud/SKILLRET-Embedding-8B) | Apache-2.0, ok. 8B BF16 | Accuracy ceiling | Offline benchmark, nie MVP serving. |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) + [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | MIT / Apache-2.0; multilingual | Polski + dense/sparse/ColBERT baseline | Obowiązkowy multilingual baseline. |
| [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) + [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) | Apache-2.0 | Niezmieniony base model | Kontrola: ile daje skill-specific tuning. |

### Dane i benchmarki

| Artefakt | Co wnosi | Ryzyko |
|---|---|---|
| [SKILLRET](https://huggingface.co/datasets/ThakiCloud/SKILLRET) | 63,259 train queries, 4,392 eval queries; metadata, bodies, taxonomy i qrels. | English/SWE-heavy; pinować wersję; respektować licencje upstream bodies. |
| [SkillRouter-Eval-Core](https://huggingface.co/datasets/pipizhao/SkillRouter-Eval-Core) | Pula ok. 80K i 87 zadań do regresji. | Nie zakładać automatycznie prawa do treningu całej zawartości. |
| [SkillRL-SFT-Data](https://huggingface.co/datasets/Jianwen/SkillRL-SFT-Data) | 11,253 przykłady do eksperymentów z failure-driven updates. | Benchmark-specific; nie stanowi danych Guidefold. |
| [GitSkills](https://huggingface.co/datasets/mvaccargiu/gitskills) | 11.34M rekordów, 1.88M różnych treści, 282K repo; dedup/taxonomy/hard negatives. | 13.4 GB; treści zachowują licencje repozytoriów; około połowa to duplikaty. |
| [SkillLifeBench](https://huggingface.co/datasets/SkillLifeBench2026/SkillLifeBench) | 194 przypadki lifecycle, prompt injection, runtime i composition. | Nowy/prowizoryczny benchmark; raportować oddzielnie. |

### Nie adoptować bez dodatkowej walidacji

- Brak publicznego checkpointu lub oficjalnego kodu SkillPyramid.
- SkillDreamer zapowiada kod po akceptacji, więc nie czynić z niego zależności roadmapy.
- [Arch-Router-1.5B](https://huggingface.co/katanemo/Arch-Router-1.5B) ma Katanemo Research License; nie przyjmować jako komercyjnego baseline'u bez legal review.
- Nie znaleziono oficjalnych kwantyzowanych checkpointów SkillRouter. Kwantyzować dopiero po A/B na polskich, długich i multi-skill queries.

### Biblioteki i implementacje referencyjne

| Projekt | Licencja / funkcja | Jak wykorzystać |
|---|---|---|
| [SkillRouter](https://github.com/zhengyanzhao1997/SkillRouter) | MIT; trening i ewaluacja retrieve+rereank | Reprodukowany baseline i format benchmarku. |
| [R3-Skill](https://github.com/Tencent/R3-Skill) | Kod i dane query-conditioned compatibility | `USE/SKIP/CONFLICT`, Set-Compat i graded listwise reranking. |
| [Graph-of-Skills](https://github.com/davidliuk/graph-of-skills) | Graph retrieval i hydration | Reverse PPR i budgeted hydration. |
| [agent-tool-router](https://github.com/dalek-ai/agent-tool-router) | MIT; mały CPU router z TF-IDF, embeddings i transition prior | Tani latency baseline oraz prior z historii wywołań. |
| [MetaClaw](https://github.com/aiming-lab/MetaClaw) | MIT; memory, skill evolution, LoRA/RL | Referencja read/write evolution; nie wdrażać wholesale. |
| [SimpleMem](https://github.com/aiming-lab/SimpleMem) | MIT; hybrid retrieval i Evaluate/Diagnose/Propose/Guard | Wzorzec pamięci i bezpiecznej optymalizacji retrievalu. |
| [LLMRouter](https://github.com/ulab-uiuc/LLMRouter) | MIT; biblioteka routerów modeli | Osobna warstwa wyboru modelu po wyborze skilla. |
| [Router-R1](https://github.com/ulab-uiuc/Router-R1) | Apache-2.0; wielorundowy model routing | Późniejszy model router; nie jest potrzebny w hot path MVP. |
| [Agent Skills specification](https://github.com/agentskills/agentskills) | Apache-2.0; format skilla | Kanoniczny format wymiany. |
| [Hugging Face Skills](https://github.com/huggingface/skills) | Apache-2.0; realne skills | Corpus fixtures i testy integracyjne o prostszym provenance. |

## Słownik pojęć

| Pojęcie | Znaczenie praktyczne |
|---|---|
| Embedding | Wektor liczb reprezentujący znaczenie tekstu. Podobne query i skill powinny leżeć blisko siebie w przestrzeni wektorowej. |
| Bi-encoder | Ten sam lub współdzielony model koduje query i dokument osobno. Szybki, bo embeddingi skills można policzyć wcześniej. |
| Cross-encoder / reranker | Model czyta query i jednego kandydata razem. Wolniejszy, ale widzi dokładne interakcje słów i zależności. |
| Sparse retrieval / BM25 | Wyszukiwanie oparte na dopasowaniu tokenów, ich rzadkości i długości dokumentu. Bardzo dobre dla nazw API, błędów i symboli. |
| Dense retrieval | Wyszukiwanie po embeddingach. Lepiej radzi sobie z parafrazami i znaczeniem, gorzej z precyzyjnymi identyfikatorami. |
| Hybrid retrieval | Łączy sparse i dense, zwykle przez RRF lub uczoną funkcję fuzji. |
| Contrastive learning | Zbliża embedding query do poprawnego skilla, a oddala od negatywnych kandydatów. |
| Hard negative | Kandydat bardzo podobny, lecz błędny, na przykład sibling o tej samej nazwie capability, ale innej wersji lub platformie. |
| False negative | Kandydat oznaczony jako błędny, chociaż faktycznie też rozwiązuje zadanie. Psuje trening, jeśli go nie odfiltrujemy. |
| Pointwise / pairwise / listwise | Uczenie pojedynczego score'u, porównania pary albo właściwego porządku całej listy. Routing top-K zwykle korzysta na listwise loss. |
| NDCG@K | Jakość kolejności top-K z uwzględnieniem graded relevance. |
| Recall@K | Jaki odsetek potrzebnych skills znalazł się w pierwszych K wynikach. |
| Hit@1 / MRR | Czy właściwy skill jest pierwszy i jak wysoko znajduje się pierwszy poprawny wynik. |
| Set-Compat | Czy wybrany zestaw skills tworzy wykonalny, wzajemnie zgodny bundle. |
| PPR | Personalized PageRank. Rozszerza początkowych kandydatów po grafie zależności i powiązań. |
| Abstention | Router świadomie zwraca brak skilla, jeśli margines lub zgodność są zbyt niskie. |
| Credit assignment | Określenie, który skill lub krok rzeczywiście przyczynił się do sukcesu albo błędu. |
| LoRA / PEFT | Tanie dostrajanie małej liczby dodatkowych parametrów bez zmiany całego modelu bazowego. |
| SFT | Supervised fine-tuning na przykładach wejście–oczekiwane wyjście. |
| RL / GRPO | Uczenie polityki z rewardu. Wymaga stabilnego verifiera i jest znacznie bardziej ryzykowne niż SFT. |
| Canary / probation | Ograniczony rollout nowego modelu lub skilla z automatycznym porównaniem i rollbackiem. |

## Materiały edukacyjne

- [Google Machine Learning Crash Course](https://developers.google.com/machine-learning/crash-course/) oraz [film o embeddingach](https://www.youtube.com/watch?v=my5wFNQpFO0): intuicja ML, wektory i podobieństwo.
- [Hugging Face: Sentence Transformers](https://huggingface.co/docs/hub/en/sentence-transformers): generowanie embeddingów i semantic search.
- [Sentence Transformers documentation](https://www.sbert.net/): bi-encoders, cross-encoders, losses, training i evaluation.
- [DeepLearning.AI: Vector Databases, from Embeddings to Applications](https://www.deeplearning.ai/courses/vector-databases-embeddings-applications): krótki kurs o ANN, hybrid search i vector databases.
- [FAISS](https://github.com/facebookresearch/faiss): praktyczne wyszukiwanie nearest neighbors.
- [Hugging Face PEFT](https://huggingface.co/docs/peft/): LoRA i inne techniki taniego dostrajania.
- [vLLM LoRA serving](https://docs.vllm.ai/en/stable/features/lora/): adaptery per request; dynamiczne ładowanie wymaga zaufanego środowiska.

## Docelowa architektura Guidefold Router

```text
query + cwd/scope + repo state + previous skill IDs
                         │
        normalize / aliases / intent decomposition
                         │
       hard policy filter: tenant, permission, platform,
       version, freshness, dependencies, retired/deprecated
                         │
  field-aware candidates: name/triggers | description | body |
  scope/topics | negative triggers; BM25 + dense per field
                         │
           tiny learned MLP + RRF + transition prior
                         │
             dense top-40/50 → rerank top-20
                         │
      USE / SKIP / CONFLICT + same-family representative
                         │
 graph-constrained composer: Start / Support / Check / Avoid,
 requires closure, general→specific, max 4 cards, abstention
                         │
        signed hydration → sandboxed execution → telemetry
```

### Komponenty

1. **Router** jest osobnym interfejsem od `Registry`; storage nie powinien definiować rankingu.
2. **Policy filter** jest deterministyczny i działa przed ML. Model nie może obejść uprawnień, izolacji tenantów, platformy ani wersji.
3. **Field-aware retriever** zachowuje semantykę osobnych pól. Dla każdego pola liczy sparse i dense score; mały MLP uczy wyłącznie ich fuzji. To najłatwiejszy pierwszy „własny model”.
4. **Reranker** dostaje body, scope chain, negative triggers i zależności; zwraca `USE/SKIP/CONFLICT` oraz score.
5. **Composer 0.1** jest deterministyczny: DAG `requires/refines`, role i mały budget. Generatywny ordered-ID decoder dopiero po danych.
6. **Knowledge compiler** zamienia trace'y w trwałe knowledge units; dopiero udowodniona wiedza może stać się kandydatem zmiany skilla.
7. **Evolver** wykonuje ograniczone operacje `CREATE/UPDATE/MERGE/PRUNE/NOOP`, otwiera PR i nigdy nie promuje bez replayu oraz CODEOWNER review.

## Brakująca warstwa danych

Obecny projekt ma `skill_revision`, `candidate`, `assignment`, `proposal`, `evidence`, `rejection_memory`, telemetry i `training_pair`. Należy dodać:

```text
knowledge_unit
  id, tenant, scope, statement, applicability_boundary,
  evidence_refs[], counter_evidence_refs[], confidence,
  source_model, source_harness, source_revision,
  contradiction_group, freshness_at, status
```

Przepływ:

```text
raw trace
→ redaction + verifier
→ knowledge_unit (persistent, non-executable)
→ multi-trace support / contradiction resolution
→ bounded skill diff
→ sandbox replay + no-skill comparison
→ owner PR
→ probation
→ active albo rollback
```

To ogranicza ryzyko, że pojedyncza halucynacja lub zatruty trace stanie się trwałym wykonywalnym skillem.

## Stack implementacyjny

### Cienki klient Guidefold

Pozostawić dystrybuowany CLI jako stdlib + PyYAML. Powinien:

- pobierać podpisane i checksumowane immutable shardy z GCS;
- lokalnie wykonywać policy filter, BM25, int8 cosine, PPR i selection;
- wywoływać `/embed` i `/rerank` przez zwykły HTTP;
- mieć deadline 1.5 s dla dense leg i 3 s dla hooka;
- w awarii działać na BM25 + graph fallback.

Nie dodawać PyTorch/Transformers do skill ZIP.

### ML i Knowledge Plane

- Python 3.12, PyTorch, Transformers, Sentence Transformers, Datasets, Accelerate, PEFT, Optimum/ONNX Runtime.
- FastAPI/Uvicorn lub mały gRPC service z `POST /embed` i `POST /rerank`.
- BM25 przez Tantivy/Pyserini; FAISS lub prosty mmap/brute-force dla wektorów.
- Cloud Run GPU/Vertex na pojedynczym L4 24 GB dla pilota; minimum jedna ciepła instancja.
- Cloud Run CPU + PostgreSQL/pgvector dla Knowledge API i lifecycle.
- GCS/CDN dla immutable indeksów; `latest.json` wskazuje SHA.
- BigQuery + OpenTelemetry/Cloud Monitoring dla outcome events i audytu.
- Cloud Run Jobs dla induction, consolidation, drift i probation.
- MLflow lub W&B tylko jako registry eksperymentów; produkcyjne modele kopiować do kontrolowanego bucketu/Artifact Registry, przypięte do HF commit SHA.

Przy 2K–10K skills hot-path vector DB jest zbędny: `10k × 1024 int8` to około 10 MB surowych wektorów. pgvector jest użyteczny dla lifecycle/novelty/offline candidates, nie dla każdego promptu.

### GPU

- Dwa modele 0.6B to około 2.4 GB samych wag BF16; z runtime, batchingiem i aktywacjami bezpiecznie planować 6–12 GB. Jeden L4 24 GB wystarcza do pilota, ale trzeba zmierzyć długość body i batch.
- Dwa modele 8B BF16 to około 32 GB samych wag, więc nie mieszczą się rozsądnie na jednym L4. 8B zostawić jako offline accuracy ceiling.
- Oficjalne przepisy treningowe SkillRet używają wielokrotnych B200 przez kilka godzin; obecny szacunek `< $5` na fine-tuning jest zbyt optymistyczny bez bardzo małego PEFT/prototypu.
- RL/GRPO, vLLM, VERL i multi-GPU zostawić do etapu, w którym istnieje stabilny reward, replay holdout, kill switch i wystarczająca ilość danych.

## Plan 12 tygodni

### Tydzień 0–2: evidence baseline

- Utworzyć pierwszy stabilny commit/SHA; repo obecnie nie ma wiarygodnego historycznego baseline'u.
- Naprawić scope-first ranking i cache `(URN, revision)`.
- Dodać testy CLI oraz mocked Registry.
- Zbudować 150–300 golden queries: 30% multi-skill, 30% sibling ambiguity, 20% no-applicable-skill, 10% stale/adversarial, 10% proste.
- Ramiona B0–B4: current lexical, BM25, generic Qwen/BGE, SkillRouter 0.6B, SkillRet 0.6B, R3 0.6B.
- Pinować dataset/model revisions i licencje.

### Tydzień 3–4: shadow router

- Cards/BM25/graph/field vectors jako immutable artifact.
- Field-aware sparse+dense + mały MLP/RRF.
- Rerank top-20; `USE/SKIP/CONFLICT` i same-family resolver.
- `find --experimental`; bez wpływu na hook.
- Shadow telemetry i CPU fallback.

### Tydzień 5–6: composition i paired eval

- Deterministyczny composer z roles, `requires/refines`, closure i max 4 cards.
- Testy `no-skill / selected / oracle / hard-negative sibling` w co najmniej dwóch harnessach/modelach.
- Time split, team/scope holdout oraz skill-held-out split.
- Gate: brak istotnego wzrostu regression/safety rate, nie tylko wyższe NDCG.

### Tydzień 7–8: knowledge i governance

- Knowledge API, `knowledge_unit`, provenance, contradiction handling i cascade revoke.
- `report --helped|--wrong` oraz redagowany opt-in query corpus; sam hash promptu nie wystarcza do treningu.
- Owner PR, golden delta, canary/probation i rollback.
- SkillPyramid w trybie comment-only na dwóch pilot nodes.

### Tydzień 9–10: pierwsze własne uczenie

- Najpierw uczyć field-fusion MLP na setkach wiarygodnych ocen.
- Retriever contrastive/LoRA dopiero przy 5K–20K jakościowych parach i hard negatives.
- Reranker listwise przy minimum ok. 5K oznaczonych candidate lists.
- Walidacja oddzielona po czasie, zespole i skillu; nie uczyć na wynikach obecnego błędnego rankingu bez verifiera.

### Tydzień 11–12: rollout

- Shadow → 5% probation → 25% → 100% z automatycznym rollbackiem.
- Jeden L4, warm min-instance; rozdzielić embed/rerank dopiero gdy p95 lub concurrency tego wymagają.
- Generatywny composer dopiero po około 5K poprawnych ordered bundles.
- Model evolvera dopiero po co najmniej około 1K zaakceptowanych/odrzuconych diffów z wynikami replayu.

## Macierz eksperymentów

| Ramię | Retrieval | Graph/policy | Rerank/composition | Cel |
|---|---|---|---|---|
| B0 | Obecny lexical + scope-first | obecne | brak | Zachować rzeczywisty punkt startu. |
| B1 | BM25 | policy | brak | Tani lexical baseline. |
| B2 | BGE-M3/Qwen3 generic | policy | brak | Koszt skill-specific tuningu. |
| B3 | SkillRouter / SkillRet / R3 embedder | policy | brak | Porównanie publicznych retrieverów. |
| B4 | Field-aware BM25+dense + RRF/MLP | policy | brak | Własna, tania przewaga w recall. |
| B5 | B4 | + reverse PPR | brak | Wkład grafu. |
| B6 | B5 | + hard filters | SkillRouter vs R3 reranker | `SKIP/CONFLICT`, sibling risk. |
| B7 | B6 | closure | deterministic ordered composer | Wkład bundle/order. |
| B8 | B7 | lifecycle | + induced parent skills | Wkład knowledge lift bez regresji. |

### Metryki

Offline routing:

- Recall@10, nDCG@10, Hit@1/MRR;
- Completeness/FullCoverage@K dla multi-skill;
- Set-Compat i harmful-sibling false-positive rate;
- prerequisite closure recall;
- abstention precision/recall;
- policy/compliance false-negative rate.

Paired end-to-end:

- pass-rate delta vs `no-skill`;
- **gain rate, regression rate i residual failure rate osobno**;
- tokeny, koszt, latency i liczba kroków;
- unsafe-action rate;
- wynik per model/harness/version.

Lifecycle:

- owner acceptance/rejection reasons;
- probation pass i rollback rate;
- wrong-load i zero-load rate;
- duplicate rate i time-to-promote;
- reviewer time, PR latency i cascade-revoke completeness.

SLO z istniejącego projektu może pozostać punktem startowym: warm p50 ≤300 ms, p95 ≤2 s, watchdog 3 s. Trzeba go potwierdzić na rzeczywistych długościach body i cold starts.

## Konkretne poprawki do istniejącego projektu

1. Naprawić `rank_cards`: scope jest feature'em i filtrem, nie bezwarunkowym pierwszym sort key.
2. Rozdzielić `Registry` od `Router`; registry odpowiada za storage, router za ranking.
3. Zmienić cache na `(URN, revision)` i immutable body/index artifacts.
4. Rozszerzyć schema/validate o `kind`, `layer`, `topics`, triggers, negative triggers, provenance, permission, status `draft/canary/blessed/retired` i resource hygiene.
5. Skorygować opis rerankera: inference punktuje kandydatów pojedynczo, lecz trening SkillRoutera jest listwise; określenie go po prostu jako „pointwise” jest mylące.
6. Dodać `knowledge_unit` i redagowany opt-in corpus treningowy; z hashy promptów nie da się fine-tunować.
7. Zwiększyć gate probation ponad trzy loady; użyć minimum ocen lub dolnej granicy posterioru, nie samej średniej.
8. Najpierw napisać ADR-y supersedujące konflikt między „zero committed generated files” a zaakceptowanym ADR-0006/materialize.
9. Nie używać Google Agent Registry jako hot-path dependency; obecny v1alpha/limit i wywołania przez `gcloud` są nieodpowiednie dla hook SLA.
10. Zweryfikować na przypiętych kartach modeli licencję i dimensionality; dokumenty projektu zawierają dziś sprzeczne wartości.

## Co budować, a czego nie budować

### Budować teraz

- Guidefold Router 0.1 jako moduł i eval harness.
- Field-aware score tensor + mały MLP.
- SkillRouter, R3-Skill, SkillRet i multilingual BGE-M3 jako wymienne backendy.
- Twarde policy filters, graph planner, abstention i same-family resolver.
- Telemetry/evidence schema, `knowledge_unit`, provenance i paired regression gates.

### Odtworzyć po MVP

- GoSkills roles i grouped presentation.
- Graph-of-Skills PPR/hydration.
- SkillPyramid lift z LCA, parent composition i child patch.
- SkillZip-on-Write, leave-one-out pruning i version-change priors.

### Obserwować

- MASkills do consolidation/credit assignment.
- SkillDreamer do pseudo-skill query expansion.
- Generative Skill Composition do learned ordering.
- SkillComposer/SkillEvo/SkillProx do write-path.
- MERA/SkillRL/Skill Self-Play do kosztownej koewolucji modeli dopiero po zbudowaniu danych i rewardu.

## Ostateczna teza produktowa

**Publiczne wagi rozwiązują cold start; nie tworzą przewagi.** Guidefold powinien być systemem, który wie nie tylko „jaki skill pasuje do tekstu”, ale:

- jaki skill działa w tym repo, scope, modelu i wersji;
- z jakimi innymi skills jest kompatybilny;
- kiedy należy odmówić jego użycia;
- czy wynik jest lepszy od `no-skill`;
- z jakich dowodów powstał i jak go bezpiecznie wycofać;
- które lokalne doświadczenie jest prawdziwą wiedzą, a które tylko jednorazowym śladem.

Ta pętla danych i governance jest trudniejsza do skopiowania niż dowolny pojedynczy checkpoint z Hugging Face.
