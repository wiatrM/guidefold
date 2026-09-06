# Audyt semantyczny: scope-prompt-b4

Data: 2026-09-06. Stałe 8 dokumentów × 2 ramiona. Oceniający: agent Product Manager, jeden reviewer LLM.

Scoped daje ograniczony sygnał lepszego zachowania zakresu: 18 z 29 accepted items oceniono jako supported_specific, wobec 11 z 28 w original. To opis tej próbki; nie dowodzi wzrostu recall ani jakości rankingu. Scoped ma też jeden pusty dokument po błędzie JSON na limicie 448 tokenów.

Oceniono wyłącznie accepted intents i synthetic queries względem dokładnych fragmentów source-inputs.json. Nie czytano rzeczywistych queries, qrels ani wyników retrieval. Tożsamość ramion była znana z metadanych; audyt nie jest w pełni zaślepiony. Przerwanego batch8 nie oceniano ani nie łączono z tym wykonaniem.

Rubryka i osiem ID zostały ustalone przed odczytem accepted outputs. Supported_specific (S) oznacza zadanie wspierane przez źródło, którego tekst zachowuje charakterystyczną platformę lub konkretny workflow. Weak_generic (W) oznacza wspierane znaczenie po utracie charakterystycznego zakresu. Unsupported (U) oznacza dodany lub sprzeczny cel, capability lub constraint. Nazwa platformy nie jest wymagana, gdy wystarcza konkretny, wyróżniający workflow. Puste wyniki i błędy parsowania są liczone oddzielnie.

| Miara w stałej próbce | original_prompt | scoped_task_prompt |
|---|---:|---:|
| Przypisane dokumenty | 8 | 8 |
| Accepted intents / queries | 17 / 11 | 17 / 12 |
| Accepted razem | 28 | 29 |
| Supported_specific | 11 | 18 |
| Weak_generic | 17 | 11 |
| Unsupported | 0 | 0 |
| Supported_specific / accepted | 39,3% | 62,1% |
| Dokumenty z ≥1 supported_specific | 4/8 | 6/8 |
| Dokumenty z ≥1 accepted item | 8/8 | 7/8 |
| Puste dokumenty / błędy JSON / cap hit | 0 / 0 / 0 | 1 / 1 / 1 |

Odsetki accepted mają różne mianowniki. Jednostką sparowania pozostaje dokument. Nie wykonano testu istotności ani ekstrapolacji na cały korpus. Zero unsupported dotyczy tylko 57 ocenionych accepted items po filtrze mechanicznym.

| Dokument | Original S / W / U | Scoped S / W / U |
|---|---:|---:|
| Hermetic SpecKit | 0 / 1 / 0 | 0 / 4 / 0 |
| packer | 3 / 2 / 0 | 3 / 0 / 0 |
| architecture-paradigm-microkernel | 4 / 1 / 0 | 4 / 1 / 0 |
| sfh-gen | 2 / 2 / 0 | 5 / 1 / 0 |
| huggingface-tokenizers | 0 / 4 / 0 | 1 / 3 / 0 |
| open-prose | 0 / 4 / 0 | 3 / 2 / 0 |
| axiom-xcode-debugging | 0 / 3 / 0 | 0 / 0 / 0 |
| erpnext-syntax-customapp | 2 / 0 / 0 | 2 / 0 / 0 |

Materialne przykłady:

- Packer: „building machine images” (W) traci narzędzie, podczas gdy „build machine images with Packer” (S) zachowuje platformę wskazaną w źródle. Original ma już trzy konkretne wpisy o Packer; nie jest całkowicie ogólne.
- OpenProse: „Where are the examples located?” (W) nie identyfikuje projektu. Scoped „what to do if a .prose program fails” oraz „how to contribute to the open-prose project” (S) zachowują zakres opisanych sekcji. „orchestrate multiple AI agents” nadal jest W.
- HuggingFace: „how to train a custom BPE tokenizer” (W) nie rozróżnia bibliotek; „Can I train a custom BPE tokenizer using HuggingFace tokenizers?” (S) to rozróżnienie zachowuje. Trzy scoped intents pozostają ogólne.
- Hermetic: „generate spec.md for feature specification” (W) w obu ramionach pomija SpecKit, .specify i container-use. Scoped „clarify the requirements for a payment module refactor” jest wspierane przez etap Clarify i przykład payment refactor w całym fragmencie, ale zgłoszony cytat o environment_file_read sam tego nie uzasadnia. Tekst nadal traci charakterystyczny proces.
- Xcode: original ma trzy wspierane objawy build/test/stale-code, ale wszystkie gubią Xcode/iOS/macOS/Derived Data. Scoped kończy się niepoprawnym JSON przy cap_hit=true i output_tokens=448. Brak słabych wpisów nie oznacza poprawy: dokument traci całe pokrycie.
- sfh-gen: „Generate a Peano horn with detailed parameters” oraz „Map a Mandelbrot boundary to an expansion profile” (S) odpowiadają konkretnym procedurom źródła. Audyt nie weryfikuje naukowej poprawności deklaracji akustycznych tego skilla.

Decyzje graniczne: „STL meshes and fractal analysis data” to W w obu ramionach, ponieważ pomija acoustic horn; uznanie zestawu wyników za wystarczająco specyficzny dodałoby po jednym S do obu ramion. BPE training bez HuggingFace jest W względem zakresu biblioteki. Plugin contract i extension loader są S jako konkretne mechanizmy źródłowej architektury. „Acoustic optimized horn topology” jest S, bo zachowuje obiekt i cel, mimo braku nazwy fractal. Nie dostrajano ocen do wyników retrieval.

Rekomendacja: nominować scoped prompt jako hipotezę do osobno zamrożonego eksperymentu, z osobnym rozliczeniem limitu długości i pustych dokumentów. Nie zastępuje to pierwotnego gate C–A, nie wykazuje recall lift i nie uzasadnia zmiany produkcyjnych metadanych. Warto uzyskać niezależną adjudykację: osiem dokumentów, jeden reviewer LLM i ocenny próg specyficzności ograniczają ten wynik.

Integralność: sprawdzono 64 wiersze, 64 unikalne pary arm/skill, po 32 dokumenty na ramię i wszystkie 16 oczekiwanych par audytu. Źródła mają ten sam hash pliku co przerwany batch8. Decoder: greedy, max_new_tokens=448, batch_size=4, seed=20260906. Model Qwen2.5-7B-Instruct, lokalna rewizja a09a35458c702b33eeacc393d103063234e8bc28. Nie modyfikowano protokołu, ustawień, generacji ani źródeł.

| Plik wejściowy | SHA-256 |
|---|---|
| PROTOCOL.md | 0767966474ab8ff28c1e9f822e51dac7f5c7d8f9ff53c29a47d036e926907518 |
| manifest.json | f4188ed843eb4d8608a397c8a6e5caa966babaee339f3a8cdda52a80f1d0a0ff |
| source-inputs.json | 4a055291d54b4456c508471f680235930e7de3f896eda774deb2f714cd40a821 |
| paired-generation.jsonl | bc2a18bd9cb1a0432199a25dc993d535c4a0dac33bb518fe85366594caf56104 |
| generation-summary.json | 941361b769bfca5e6bb33c87b17e6a32a6afeffd412a21fc86ae95778fae4b44 |

Hashe poniżej dotyczą dokładnego tekstu source po zdekodowaniu JSON i zakodowaniu w UTF-8; nie całego rekordu JSON.

| Dokument / skill_id | SHA-256 tekstu source |
|---|---|
| Hermetic SpecKit; b1ede29c-68f0-4bfc-a804-d5f85fb3df02 | 55d49067898bc9e458c8bfa3410fb5604edd1d0caf4dcb46b4920815b217ab98 |
| packer; 331851d6-9590-4c47-9a08-d836b93cdc84 | 650a67d216922532836b8dc035cf9df8198f231f348a74006d6c3f0e90ae642e |
| architecture-paradigm-microkernel; a7532140-ae18-4cce-a9e3-1c843da728f2 | e1655a0520ea0208f77877ab2ee91ab02f68b9a3e6169dba10dbb1515ea6d0de |
| sfh-gen; ebf47fd2-4fbc-41fd-8f35-81413fbbda74 | 545fd1b72ea9e227f4a873d9e2c9224fb78c866de931673f69caebcd40840636 |
| huggingface-tokenizers; 80f7aae4-fdd4-4000-ac0f-51d71a6187a3 | bab4f6975f8702a96c18066857daa66a3617c7a0e184a847cd2ab9327dfd1afe |
| open-prose; 8c7de50e-8d10-41ed-930f-fc83a45a197e | 5da40c0085c091034b7fb4ae535d0c366aa52edac9a4387c066af7a1b20fced6 |
| axiom-xcode-debugging; eafe7b49-7315-4821-a3e4-24894314f1af | e08a9f311c3b38390bec377b74c50c42c2f3cf40d5e89539f7505aca5cd19bf5 |
| erpnext-syntax-customapp; a5fd56b1-56c7-4557-99da-21b1da6e8ba7 | c75e193a915d0f89eca60e6ca20fede0d0ced2912282454ee84f3428b5196414 |

Pełne etykiety 57 wpisów, uzasadnienia, zgłoszone evidence, kotwice źródłowe z numerami linii, metadane błędów oraz agregaty znajdują się w semantic-review.json. Fragmenty oznaczone jako pominięte nie były dowodem. Audyt nie ocenia odrzuconych propozycji ani pozostałych 24 dokumentów.

