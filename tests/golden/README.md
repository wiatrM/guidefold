# Golden evaluation set (E1.2)

A labelled query set for scoring Guidefold's skill router over the **Meridian** fixture
(`examples/monorepo/`, `registry.backend: local`, 17 hierarchy nodes, 26 real skills plus the
generated `hierarchy-index` skill which is never a valid answer). This directory is **data only**:
it does not run a router or compute metrics. Another component (the metrics runner) consumes this
schema and reports Hit@1, Recall@8, nDCG@10, Completeness@K and abstention precision against it.

## Files

| File | Cases | Tests |
|------|------:|-------|
| `multi_skill.yaml` | 66 | correct answer is 2-4 skills that must **all** appear — Recall@8 / Completeness@K |
| `sibling_ambiguity.yaml` | 66 | query plausibly matches two sibling nodes, only one is right given `cwd` — scope as a ranking *feature*, never the first sort key |
| `no_applicable.yaml` | 44 | real engineering task with no Meridian guidance, `relevant: []` — abstention precision |
| `stale_adversarial.yaml` | 22 | lexically attracts the deprecated `legacy-session-auth` skill, or shares vocabulary with an unrelated active skill — deprecated skill must never be a true positive |
| `simple.yaml` | 22 | one obvious skill or node — sanity baseline |
| **Total** | **220** | target split 30/30/20/10/10, tolerance ±3pp, overall count must stay in [150, 300] |

## Case schema

Each file is:

```yaml
version: 1
category: multi_skill   # one of: multi_skill | sibling_ambiguity | no_applicable | stale_adversarial | simple
cases:
  - id: multi-001
    query: "we're adding a new message broker for cross-platform events, what needs documenting"
    cwd: "."
    node: "_root"
    relevant:
      - {urn: "urn:skill:meridian:_root:adr-process", grade: 3}
      - {urn: "urn:skill:meridian:_root:monorepo-conventions", grade: 2}
    distractors:
      - {urn: "urn:skill:meridian:relay:terraform-conventions", why: "shares 'broker'/infra vocabulary but doesn't answer the documentation question"}
    notes: "optional free text"
```

Field rules:

- `id` — unique across the whole golden set, prefixed by category (`multi-`, `sib-`, `noapp-`,
  `stale-`, `simple-`).
- `query` — reads like real engineer input: lowercase, imperative or interrogative, 4-20 words,
  concrete Meridian nouns (services, tables, files, commands from the fixture's own `SKILL.md`
  bodies). No templated repetition, no near-duplicates elsewhere in the set.
- `cwd` — a real directory under `examples/monorepo`, relative to it (`"."` for the repo root).
- `node` — must equal `node_for(cwd)` per `examples/monorepo/guidefold.yaml` (longest-glob-wins
  resolution, same function the CLI uses).
- `relevant` — ordered most-useful-first. `grade` is graded relevance for nDCG@10:
  - `3` — must be rank 1 (the single best answer)
  - `2` — must appear in the top 8 (a required companion, e.g. a `requires` dependency)
  - `1` — acceptable if surfaced, not required
  - `no_applicable` cases always have `relevant: []`.
- `distractors` — URNs that a naive (e.g. pure-lexical) router might surface but that must **not**
  land in the top-4 injected cards. Each carries a `why` explaining the false attraction. Every
  `no_applicable` case has at least one distractor grounded in real fixture vocabulary; the
  deprecated skill (`legacy-session-auth`) is used as a distractor throughout `stale_adversarial`
  and must never appear as `relevant` anywhere in the set.
- `notes` — optional. Used for the three MVP smoke-test prompts ("write an ADR", "handle an
  outage", "add RBAC"), each tagged `notes: "MVP smoke-test prompt: ..."`; these three are required
  to route to three different top-3 skill sets (checked by the validator).
- Every `urn` (relevant or distractor) must be a real, non-generated skill in the fixture:
  `urn:skill:meridian:<node>:<skill-name>`, derived the same way the CLI derives URNs.

## Validating the set

```bash
python3 tests/golden/validate_golden.py       # standalone script, prints every check, exit 0/1
pytest tests/golden/test_golden_set.py         # same 9 checks as pytest assertions
```

`validate_golden.py` imports `node_for` / `ancestors` / `load_map` / `rel` / `urn` directly from
`skills/guidefold/scripts/guidefold` (via `importlib.machinery.SourceFileLoader`, since that file
has no `.py` extension) so node resolution in this validator can never drift from the CLI's own
behaviour. It checks:

1. total case count is in `[150, 300]`
2. every `id` is unique and matches its file's category prefix
3. category proportions are within ±3pp of 30/30/20/10/10
4. every `urn` (in `relevant` or `distractors`) exists among the fixture's real skills, parsed
   from `SKILL.md` frontmatter, ignoring the generated `hierarchy-index` skill
5. every `cwd` is an existing directory under `examples/monorepo`
6. every `node` equals `node_for(cwd)`
7. no skill with `metadata.status: deprecated` appears in any `relevant` list
8. no two queries anywhere in the set are identical or near-duplicate (token-set Jaccard ≥ 0.9)
9. every `no_applicable` case has `relevant: []`

plus a bonus check that the 3 MVP smoke-test prompts are present and produce 3 distinct top-3
`relevant` sets.

## How to add a case

1. Pick the category file that matches what you're testing (see the table above).
2. Pick or create a `cwd` under `examples/monorepo` and confirm its node with:
   ```bash
   cd examples/monorepo && python3 ../../skills/guidefold/scripts/guidefold hierarchy <path>
   ```
   (or read `guidefold.yaml`'s `paths` globs directly — longest match wins).
3. Ground `relevant`/`distractors` in what the fixture's `SKILL.md` files actually say — their
   `description`, `metadata.digest`, and any `metadata.requires` / cross-references. Don't invent
   skill behaviour that isn't in the fixture.
4. Write the query the way an engineer would type it into a task assistant: concrete nouns, no
   meta-references to Guidefold itself, 4-20 words.
5. Give the case a unique `id` with the right prefix (highest existing number in the file + 1).
6. Run `python3 tests/golden/validate_golden.py` and fix anything it flags before committing.
