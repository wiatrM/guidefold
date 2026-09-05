# Aktualizacja: osobisty tracker nauki

Bieżący plik sciezka-nauki.html to samodzielny tracker z zapisem lokalnym, zgodnie z prośbą użytkownika o śledzenie etapów. Poniższe wcześniejsze notatki dokumentują pochodzenie materiałów; opisy dawnego renderera i raportu tylko do odczytu mają charakter historyczny.

Podejście zaktualizowano do pracy z AI od pierwszego dnia. Proporcja 9 godzin projektu, 4 godzin kursów i 2 godzin samodzielnego sprawdzenia przy 15 godzinach tygodniowo jest propozycją organizacyjną, nie wynikiem badania. Poprzednie 660 godzin oznacza zakres materiałów. Dziesięć etapów i 30 sprawdzianów służą kontroli opanowania umiejętności; nie są zwalidowanym psychometrycznie testem.

Dodano źródło Anthropic dotyczące AI i uczenia się programowania. Wynik krótkiego eksperymentu z nową biblioteką nie uzasadnia twierdzenia, że AI zawsze szkodzi uczeniu. Plan uwzględnia samodzielną weryfikację rozumienia kodu i metodologii.

Zapis: localStorage, eksport/import JSON, walidacja importu, zabezpieczenie poprzedniego stanu oraz jawna obsługa konfliktów między kartami. Aplikacja nie wysyła danych. Aktualne wyniki 13 testów funkcjonalnych oraz 12 kombinacji widoku i szerokości znajdują się w qa-receipt.json. Zastępują wcześniejsze ograniczenie renderera.

---

# Ścieżka nauki — źródła i założenia

Weryfikacja ofert: 5 września 2026. Profil: podstawy Pythona, początek ML, minimum 15 h tygodniowo, budżet elastyczny.
Główny plik do czytania: sciezka-nauki.html. Canonical source: artifact.json.

## Konstrukcja planu

10 etapów, 44 tygodnie, 660 godzin; bufor 4–8 tygodni poza planem.
Szacunki etapów są autorskie. Czasy organizatorów dotyczą całego kursu lub wybranych modułów, zgodnie z opisem w raporcie.
Pełne matematyka, DLS, NLP i CS336 są rozszerzeniami; nie sumujemy ich do podstawowych 660 h.
Trening zakłada istniejące dane z etykietami. Zbudowanie dużej biblioteki treningowej od zera wymaga dodatkowego czasu.
Plan jest materiałem edukacyjnym, nie ponowną walidacją aktualnej konfiguracji Guidefolda.

## Forma raportu

Delivery: lokalny samodzielny HTML. Audience specification: technical-report.
Tytuł i zalecenie odpowiadają roli technical summary. Harmonogram i etapy dostarczają evidence path.
Zakres i słownik podają definicje. Protokół projektu to methodology.
Sekcje o dostępie, czasie, sprzęcie i reprodukcji dokumentują limitations.
Pierwszy tydzień i bramki etapów są next steps. Pytania do lektury prac realizują further questions.
Narracja jest polska, zgodnie z żądaniem użytkownika.

## Wykres i tabela

Pytanie: jak rozłożyć planowane godziny między kolejno realizowane etapy?
Wykres: pojedynczy horizontalBar, 10 etapów, osie etap / planowane godziny, porządek etapów, bez redundantnej legendy.
Interpretacja: najwięcej czasu wymaga pełny fundament ML; ćwiczenia są uwzględnione.
Dane nie są pomiarami osiągnięć. Kolor: jeden domyślny zatwierdzony akcent wspólnego renderera.
Czytelność nie zależy od koloru; nazwy, kolejność, osie i tabela niosą informację.
Wykres i tabela pełnej szerokości, mobile układa je pionowo.
Wykonano rzeczywisty SELECT w SQLite nad learning_plan. plan.sql odtwarza tabelę wejściową oraz ten SELECT.
Dataset zachowuje kolejność, nazwy, zakres tygodni, liczbę tygodni, godziny i rezultat etapu.
Tabele kosztów i pierwszego tygodnia są w markdown: służą dokładnemu odczytowi, nie porównaniu wielkości.
Nie rysowano wykresu cen: różne waluty, zakresy abonamentów i warunki podatkowe nie tworzą uczciwego jednego rankingu.
Nie tworzono sztucznych wykresów jakości nauki ani szans publikacji.

## Weryfikacja i ograniczenia źródeł

Źródła pierwotne: organizatorzy kursów, oficjalna dokumentacja, artykuły i repozytoria autorów.
Sprawdzono zakres, wymagania, publiczne czasy i dostęp; nie ukończono płatnych laboratoriów.
DLAI: bezpłatne wideo vs płatne laboratoria/quizy/certyfikaty; publiczny miesięczny Pro 30 USD, roczny równowartość 25 USD/mies.
Coursera: Preview nie jest pełnym auditem; DLAI Help wyklucza DLAI z Coursera Plus.
Zmienna promocja Plus została pominięta. Ceny konta w Polsce i podatki w koszyku niezweryfikowane.
Claude Academy jest kanoniczną nową platformą; nie twierdzimy, że stare adresy Skilljar globalnie przekierowują.
Google DeepMind Research Foundations jest bezpłatny; Google Skills Pro nie jest wymagany do tej ścieżki.
Stanford CS224N: publiczne kompletne nagrania 2024; materiały 2026 mają inny zakres dostępu.
HF FAQ i menu nie są spójne w kwestii certyfikacji; raport nie składa obietnicy certyfikatu.
SkillNet oznacza infrastrukturę skilli; nie został utożsamiony z checkpointem SkillRet/SkillRouter.
Wersje przytoczonych prac przypięte w źródłach; kursy są zmienne i oznaczone datą sprawdzenia.

Przegląd treści przez drugiego agenta doprowadził do dopisania jawnego przygotowania danych treningowych
oraz ochrony false negatives wewnątrz batcha. Suma etapów i JSON przeszły sprawdzenie.
Walidator canonical artifact: ok (25 bloków, 49 źródeł, 1 dataset).
Pakowanie: oficjalny deliver_portable_artifact.mjs z pluginu Data Analytics.
Końcowy stan QA zapisany osobno w qa-receipt.json.

## Katalog źródeł

- [Harvard — CS50P](https://cs50.harvard.edu/python/)
- [DeepLearning.AI — AI Python for Beginners](https://www.deeplearning.ai/courses/ai-python-for-beginners)
- [Google — Machine Learning Crash Course](https://developers.google.com/machine-learning/crash-course)
- [Google MLCC — wymagania i prework](https://developers.google.com/machine-learning/crash-course/prereqs-and-prework)
- [Stanford / DeepLearning.AI — Machine Learning Specialization](https://www.coursera.org/specializations/machine-learning-introduction)
- [DeepLearning.AI — Machine Learning Specialization](https://www.deeplearning.ai/specializations/machine-learning)
- [DeepLearning.AI — Mathematics for Machine Learning and Data Science](https://www.coursera.org/specializations/mathematics-for-machine-learning-and-data-science)
- [DeepLearning.AI — Deep Learning Specialization](https://www.coursera.org/specializations/deep-learning)
- [PyTorch — Learn the Basics](https://docs.pytorch.org/tutorials/beginner/basics/intro.html)
- [Stanford — Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/)
- [DeepLearning.AI — Retrieval Augmented Generation](https://www.coursera.org/learn/retrieval-augmented-generation-rag)
- [DeepLearning.AI — Embedding Models: from Architecture to Implementation](https://www.deeplearning.ai/courses/embedding-models-from-architecture-to-implementation)
- [Hugging Face — LLM Course](https://huggingface.co/learn/llm-course/chapter1/1)
- [Google Skills — Attention Mechanism](https://www.skills.google/course_templates/537)
- [Google Skills — Transformer Models and BERT Model](https://www.skills.google/course_templates/538)
- [Google DeepMind — AI Research Foundations](https://www.skills.google/paths/3135)
- [Google DeepMind — 05 Fine-Tune Your Model](https://www.skills.google/course_templates/1556)
- [Google — bezpłatność AI Research Foundations](https://blog.google/company-news/inside-google/around-the-globe/google-africa/ai-research-foundations/)
- [SentenceTransformers — Training Overview](https://sbert.net/docs/sentence_transformer/training_overview.html)
- [SentenceTransformers — Loss Overview](https://sbert.net/docs/sentence_transformer/loss_overview.html)
- [SentenceTransformers — hard negatives](https://sbert.net/docs/package_reference/util/hard_negatives.html)
- [SentenceTransformers — MS MARCO training example](https://sbert.net/examples/sentence_transformer/training/ms_marco/README.html)
- [SentenceTransformers — training rerankers](https://sbert.net/examples/cross_encoder/training/rerankers/README.html)
- [SentenceTransformers — CrossEncoder losses](https://sbert.net/docs/package_reference/cross_encoder/losses.html)
- [SentenceTransformers — evaluation](https://sbert.net/docs/package_reference/sentence_transformer/evaluation.html)
- [Claude Academy — Building with the Claude API](https://academy.claude.com/courses/building-with-the-claude-api)
- [Claude Academy — Introduction to agent skills](https://academy.claude.com/courses/introduction-to-agent-skills)
- [Claude Academy — FAQ / migracja ze Skilljar](https://academy.claude.com/help/faq)
- [SciPy — bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
- [NeurIPS — Paper Checklist](https://neurips.cc/public/guides/PaperChecklist)
- [SkillNet: Create, Evaluate, and Connect AI Skills, v3](https://arxiv.org/abs/2603.04448v3)
- [SkillNet — oficjalne repozytorium](https://github.com/zjunlp/SkillNet)
- [SkillRouter, v5](https://arxiv.org/html/2603.22455v5)
- [SkillRet, v3](https://arxiv.org/html/2605.05726v3)
- [BEIR, v4](https://arxiv.org/html/2104.08663v4)
- [DeepLearning.AI — Free / Pro](https://info.deeplearning.ai/knowledge-base/what-do-i-get-with-the-deeplearning.ai-pro-membership-that-i-dont-get-for-free)
- [DeepLearning.AI — platforma a Coursera](https://info.deeplearning.ai/knowledge-base/whats-the-difference-between-taking-deeplearning.ai-courses-on-learn.deeplearning.ai-vs-coursera)
- [Coursera — nowy bezpłatny Preview](https://blog.coursera.org/introducing-courseras-new-course-preview-experience/)
- [Coursera Plus — cennik](https://www.coursera.org/courseraplus)
- [Google Skills — cennik](https://www.skills.google/subscriptions)
- [DeepLearning.AI — Natural Language Processing Specialization](https://www.coursera.org/specializations/natural-language-processing)
- [DeepLearning.AI / AWS — Generative AI with Large Language Models](https://www.coursera.org/learn/generative-ai-with-llms)
- [Stanford — CS224N](https://web.stanford.edu/class/cs224n/)
- [Stanford — CS336](https://cs336.stanford.edu/)
- [DeepLearning.AI — trial i certyfikaty](https://info.deeplearning.ai/knowledge-base/are-professional-certificates-included-in-the-deeplearning.ai-pro-membership-0)
- [DeepLearning.AI — podatki](https://info.deeplearning.ai/knowledge-base/are-taxes-included-in-my-pro-membership-payment)
- [University of London / SOAS — Understanding Research Methods](https://www.coursera.org/learn/research-methods)
- [Stanford — Writing in the Sciences](https://www.coursera.org/learn/sciwrite)

## Wynik pakowania

Oficjalny deliver nie ukończył kontroli interaktywnej: reader_timeout/state=fallback w Chromium Windows i Linux, także przy 20 s budżetu. Chrome zgłosił browser_environment_mismatch.
Zapisano samodzielny HTML tym samym oficjalnym buildPortableArtifact. verifyPortableArtifactStructure potwierdził zgodność całego payloadu i strukturę.
Pełny semantic fallback, wszystkie linki źródeł i etapy obecne. Nie deklarujemy przejścia browser QA ani ekstrakcji statycznego SVG wykresu.

Aby odtworzyć podstawowy HTML, użyj dołączonego do Data Analytics build_portable_artifact.mjs --input artifact.json --output sciezka-nauki.html.
Pełny test: deliver_portable_artifact.mjs z tymi samymi argumentami; qa-receipt.json dokumentuje wynik tego środowiska.
