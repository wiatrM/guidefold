# Blind semantic audit of generated enrichment

Completed all **16 fixed documents before retrieval evaluation**. There are **44 accepted items: 26 supported, 18 weak or generic, 0 unsupported**. One of the 16 documents is empty after filtering. The item and document denominators are different.

The sample uses the previously frozen first16 SHA256(enrichment-audit-v1 + skill_id) ordering. Labels assess support against the full source actually supplied to the generator. A matching quotation alone does not establish support. Weak/generic means a supported action whose phrasing loses important applicability scope; it does not mean a demonstrated retrieval error.

Recurring omissions include Dafthunk, Loreal BTDP, frontend/Tailwind context, and repository-specific Express/globalAsyncHandler conventions. The offline/online evaluation document also shows why source grounding is weaker than verifying the quality of the underlying skill: its title and description are specific but much of its body is generic boilerplate. No generated capability was judged unsupported in this small sample. That is not a corpus-wide hallucination-rate estimate.

The audit did not inspect real evaluation query text or ranking outcomes. Separate structural QA used gold IDs for cohort validation and dependency components. Source/output record hashes and item-level reasons are in semantic-audit.json; the earlier partial audit is retained as semantic-audit-partial-v1.json.

| Sample | Skill | Supported | Weak/generic | Unsupported | Empty document |
|---|---|---:|---:|---:|---:|
| 1 | qa-resilience | 3 | 1 | 0 | 0 |
| 2 | php-laravel | 1 | 0 | 0 | 0 |
| 3 | xcstrings-localizer | 1 | 0 | 0 | 0 |
| 4 | ce:work | 3 | 1 | 0 | 0 |
| 5 | issue | 2 | 2 | 0 | 0 |
| 6 | Offline vs Online Evaluation | 2 | 0 | 0 | 0 |
| 7 | airflow-dag-patterns | 0 | 0 | 0 | 1 |
| 8 | implement architect workflow | 0 | 6 | 0 | 0 |
| 9 | code-review | 1 | 0 | 0 | 0 |
| 10 | rrna-prediction-patterns | 3 | 0 | 0 | 0 |
| 11 | go-error-wrapping | 4 | 2 | 0 | 0 |
| 12 | code-review | 4 | 0 | 0 | 0 |
| 13 | btdp-it-masterdata-retrieval | 1 | 2 | 0 | 0 |
| 14 | frontend-engineering | 1 | 1 | 0 | 0 |
| 15 | tailwindcss-accessibility | 0 | 1 | 0 | 0 |
| 16 | node-generator | 0 | 2 | 0 | 0 |

## 1. qa-resilience (b67937a6-255b-4a20-8fe9-79a977e3d8ad)

- **supported** — Configure retry strategies Explicit retry strategies and exponential backoff are part of the supplied resilience workflow.
- **supported** — How to handle external dependency failures in QA? The supplied source explicitly covers external dependency failures and QA fault injection.
- **weak_or_generic** — What are the steps for production hardening? Production hardening is a supported use case, but this wording omits the resilience and failure-mode scope and can describe other hardening work.
- **supported** — How do we validate system resilience under failure conditions? The full supplied workflow describes failure-mode validation, beyond the cited heading alone.

## 2. php-laravel (eab4c43a-cfcc-4e4a-b4f3-f415da7c8574)

- **supported** — Laravel 12+ development patterns The source explicitly names Laravel 12+ development patterns and related Eloquent/PHP guidance.

## 3. xcstrings-localizer (fbd54315-3f1a-4bf7-8a50-e634ae7fa7de)

- **supported** — translate Xcode String Catalog files Direct translation of Xcode String Catalog files is the stated purpose and preserves the Xcode scope.

## 4. ce:work (fb403d3b-0a9f-4043-922a-ee716171e258)

- **supported** — execute work plans efficiently Executing implementation work plans is the stated purpose.
- **supported** — create todo list from work plan The source explicitly instructs breaking a work plan into actionable tracked tasks.
- **supported** — choose execution strategy based on plan size The source explicitly chooses execution strategy using plan size and dependencies.
- **weak_or_generic** — what to do if the plan is unclear Clarifying an unclear plan is explicitly supported, but the standalone wording loses the coding work-plan context.

## 5. issue (4413090c-0805-411b-a68d-530bb6386348)

- **weak_or_generic** — manage issues The source manages local Issue specifications under specs/issues and distinguishes GitHub issues; this phrase omits that material scope.
- **weak_or_generic** — How do I create a new task? Creating a task is supported within the local Issue/Epic workflow, but the wording omits that scope and is broadly applicable.
- **supported** — What is the process for adding a bug fix task? Adding a bug-fix task is an explicit use case of the supplied Issue workflow, even though the cited quotation alone is less specific.
- **supported** — Can I create an issue without reading the Epic? The source explicitly requires reading the Epic first. This is a question about that boundary, not an assertion that it may be bypassed.

## 6. Offline vs Online Evaluation (bad47673-bbe7-40f1-ae46-d3a483b2d872)

The source has an evaluation-specific title/description but a largely generic implementation template. Source-grounded metadata does not prove that this underlying skill contains adequate specialist instructions.

- **supported** — Implement offline and online evaluation strategies The supplied description and second Overview explicitly cover offline/online evaluation for AI/ML. The chosen evidence sentence alone is generic; this label does not validate the mostly templated body as usable implementation guidance.
- **supported** — How to implement offline and online evaluation strategies? Offline/online evaluation is the stated source purpose. Support comes from the full supplied text, not the generic implementation quotation alone.

## 7. airflow-dag-patterns (46b0f4a3-86d2-466c-a89c-e4fa666a0ed5)

Zero accepted items after frozen mechanical filtering. Counted as one empty document, not an unsupported item. No claim about the source quality or generator raw text follows.


## 8. implement architect workflow (d36a0433-334d-49e4-a885-fb9974f57278)

- **weak_or_generic** — Implement error handling strategy The action exists, but this is a repository-specific Express/globalAsyncHandler error strategy; the phrase omits that important implementation context.
- **weak_or_generic** — Register API routes The source uses a particular Express router/globalAsyncHandler/registerRoute workflow; generic API-route registration drops those applicability conditions.
- **weak_or_generic** — Use layered architecture The source specifies a Controller-Service-Repository API pattern; broad layered architecture loses both that pattern and API implementation scope.
- **weak_or_generic** — How to handle errors in API controllers? The question concerns a supported action, but the source prohibition on local try/catch depends on this repository already installing globalAsyncHandler. The generic controller question omits that condition.
- **weak_or_generic** — What is the correct way to define API routes? The phrase presents a generic correct API-route workflow while the source prescribes specific Express and registerRoute conventions in one repository.
- **weak_or_generic** — How should I structure my API code for better organization? API organization is supported through one Controller-Service-Repository implementation; this broad request does not preserve the source-specific conventions.

## 9. code-review (69507794-bc4e-48aa-bb9e-1fef089ced56)

- **supported** — Perform comprehensive code reviews Comprehensive code review is the stated purpose and the supplied workflow covers commit, staged, range, and file review.

## 10. rrna-prediction-patterns (4ed5d253-fa68-4571-98ba-631c017b0c3e)

- **supported** — Use HMM for rRNA detection The source explicitly describes HMM profiles for rRNA detection.
- **supported** — How do I detect rRNA using HMM? The source explicitly describes the requested HMM-based rRNA detection workflow.
- **supported** — Can I use BLAST to find rRNA sequences? The full supplied source has a BLAST-based rRNA section; this is supported beyond the database-only evidence quotation.

## 11. go-error-wrapping (30bddd35-f4ba-4589-b49d-43ac63f07ca0)

- **supported** — wrap errors with context Wrapping errors with contextual information is the narrow action explicitly described in the source.
- **supported** — preserve error chain Preserving the original error chain is an explicit source rule and a specific error-handling concept.
- **weak_or_generic** — add meaningful context The source means context in wrapped errors; the phrase drops errors and can refer to almost any kind of context.
- **supported** — how to add context to errors in Go The query preserves the Go language and specific error-context purpose.
- **weak_or_generic** — what is the correct way to handle errors in Go The source covers error wrapping, while this asks about general Go error handling and omits that narrower scope.
- **supported** — why should I preserve the error chain when wrapping errors The source explains preservation of the original error for type checking and illustrates the wrapped chain, supporting a question about why to retain it.

## 12. code-review (4d2095dc-0ae4-4ac9-9867-a4ce30a3995b)

- **supported** — perform code review Systematic code review is the stated purpose.
- **supported** — How to review code for security issues? The supplied checklist explicitly covers secrets, input validation, SQL injection and XSS.
- **supported** — What should I look for in a code review? The source contains a security, quality and tests checklist answering this question.
- **supported** — How do I format the output of a code review? The source explicitly defines severity levels and a review output example.

## 13. btdp-it-masterdata-retrieval (a79274ae-05bd-42bf-8ff5-50a2cd377985)

- **weak_or_generic** — retrieve IT masterdata IT masterdata retrieval is supported specifically for Loreal BTDP; the phrase omits the organization/platform boundary.
- **weak_or_generic** — data lineage queries Lineage queries are supported specifically through BTDP data sources and infrastructure; the phrase is platform-generic.
- **supported** — What is the lineage for tables_v2 This exact question is a documented workflow example for tables_v2 in the supplied source.

## 14. frontend-engineering (2f1f7b22-dd85-42b7-add8-efd4d68e96bc)

- **weak_or_generic** — state management The skill is restricted to frontend engineering; state management alone drops that domain qualifier.
- **supported** — How can I improve state management in my React app? The query preserves frontend/React scope and the source explicitly supports React and state management.

## 15. tailwindcss-accessibility (91823ed1-b996-4557-a92c-f5901dda723b)

- **weak_or_generic** — focus management The source covers focus management through Tailwind CSS accessibility utilities; the phrase drops the Tailwind/web accessibility scope.

## 16. node-generator (e69f9870-69bc-4151-af50-b04a9d5faa10)

- **weak_or_generic** — generate workflow nodes Workflow-node generation is supported specifically for Dafthunk. Omitting Dafthunk removes a material platform discriminator.
- **weak_or_generic** — How do I generate a new workflow node? The requested action is present, but the source is a Dafthunk implementation/test/registry workflow, while this wording is platform-generic.

No prompts, filters, generated outputs, or retrieval settings were changed. This descriptive audit adds no retrospective numeric gate. It checks source grounding and scope retention, not external scientific accuracy, safety, retrieval utility, or user outcomes.
