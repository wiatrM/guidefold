# F5 offline enrichment: deriving triggers, negative_triggers and skill-graph edges from plain `SKILL.md`

Builds the extractor for method family **F5** (`docs/reports/bakeoff/DENSE-PROGRAM.md` §4, v2.1):
most real-world skills have no `triggers`/`negative_triggers`/`requires` metadata at all — they are
just a `name`, a `description`, and a body of prose. F5 derives those fields at index time from the
body text alone, so the sparse retrieval path (and, eventually, any dense arm) has structured signal
to work with even for unenriched skills. The runtime (`skills/guidefold/scripts/guidefold`) is
**unchanged** — this is purely an index-time preprocessing step; its output is a cards JSONL that
`Index.from_cards` already knows how to consume.

**This report is a sanity check, not the F5 quality gate.** The family's actual acceptance criterion
is `all_required@4` on the dev/test split (§5), run later by family evaluation once a dev split
exists. What follows measures something narrower and much cheaper: on SkillRetBench, if you pretend
the authored `trigger_phrases`/`anti_triggers`/`composable_skills` don't exist and derive purely from
`full_text`, how much of that authored signal does the extractor recover, and how often is it wrong?
Low recall is expected and fine — the extractor only sees prose, the authors had the whole skill in
their head. **Low precision on `negative_triggers` is not fine**, because the router hard-filters on
it (see below) — this report is written with that asymmetry as its organizing principle.

## 1. The three rules, in order

`tools/enrich/derive.py::derive(skills: list[dict]) -> dict[str, Enrichment]` is a pure function.
Input skills need only `id`, `name`, `description`, `body`; `requires`/`triggers`/`negative_triggers`
may already be present and are respected (rule 3). It reuses the shared tokenizer
(`tools/bakeoff/tokenizer.py::tokenize`) rather than reimplementing normalisation — the same
NFKD-fold + ASCII-lowercase + `[a-z0-9]+` split the runtime and the shared test fixtures use.

### Rule 1 — section mining (triggers / negative_triggers)

Headings are matched against curated regexes (`USAGE_HEADING_RE` for "When to Use", "Use this skill
when", "Trigger Phrases", ...; `EXCLUSION_HEADING_RE` for "Do not use this skill when", "When NOT to
use", ...). Under a matching heading, bullets are extracted if present, else the section is sentence-
split. Outside any matching heading, individual sentences are still checked against
`USAGE_SENTENCE_RE` (`\buse\s+(when|for|if)\b`-ish) and `EXCLUSION_SENTENCE_RE` (`do not use`, `not
for`, `avoid when/if`, `out of scope`) so a "Do not use this for X" sentence buried in an `## Overview`
paragraph still gets caught.

Every candidate phrase goes through `_finalize_phrase`, which:
- strips parentheticals and boilerplate lead-in ("use when", "do not use", ...) via `_cue_remainder`;
- truncates at the first `" or "`/`;` (keeps each derived item to one condition, not a run-on list);
- requires 3–8 tokens (`MIN_PHRASE_TOKENS=3`, `MAX_PHRASE_TOKENS=8`; below 3 the phrase is dropped as
  too vague — "you want" or "the user" are not a signal on their own);
- requires a minimum number of **non-stopword** tokens — 1 for `triggers`, **2 for
  `negative_triggers`** (see §2, this is the single highest-leverage precision fix in this PR);
- dedupes by tokenized form (so "Use when adding a container image" and "when you add a Container
  Image" collapse to one entry);
- is capped at 12 `triggers` / 8 `negative_triggers` per skill (`TRIGGERS_CAP`,
  `NEGATIVE_TRIGGERS_CAP`).

`EXCLUSION_HEADING_RE` deliberately does **not** match bare "Anti-Patterns", "Triggers", or "Activate"
headings — measured on the 2,037-skill reference corpus, those bare headings are dominated by
off-topic domain content (e.g. an "Anti-Patterns" section about *code* anti-patterns the skill
teaches you to avoid writing, not about when not to invoke the skill itself); matching them
indiscriminately produced negative_triggers that were actively wrong, not just noisy.

### Rule 2 — edge mining (requires / similar)

`_build_candidates` indexes every other skill's tokenized `name` (≥2 tokens, `MIN_NAME_TOKENS`) and
raw `id` (≥7 chars, `MIN_ID_CHARS`) as whole-phrase mention targets. Each skill's body is scanned for
these; a match under a dependency-shaped heading/cue (`## Prerequisites`, "requires", "depends on",
`EDGE_DEPENDENCY_HEADING_RE`/`DEPENDENCY_CUE_RE`) becomes a `requires` edge, a match under a
related/reference heading or cue ("See also", "Related Skills", "related to", `EDGE_RELATED_HEADING_RE`/
`RELATED_CUE_RE`) or a bare mention with no cue becomes `similar` (lower confidence, tagged
accordingly in provenance). Self-edges are never produced. `requires` edges are added in a
deterministic `sorted(by_id)` order with a DFS reachability check (`_reachable`) before each edge is
added; an edge that would close a cycle is demoted to `similar` instead of being dropped — the
information ("these two skills are connected") is kept, just not as a directed dependency the router
could get stuck walking.

### Rule 3 — existing fields win

If a skill already has `triggers`/`negative_triggers`/`requires`, those values are kept **verbatim**
and marked `derived: false` in `provenance`; derived items for the same field are appended after them
(subject to the same caps and dedup as above) and marked `derived: true`. Nothing authored is ever
edited, reordered, or dropped by this tool.

An LLM-based fourth rule is explicitly out of scope for this PR; `derive.py` leaves a single marked,
currently-unused extension seam (`LLM_EXTENSION_POINT`) rather than a half-built hook, so a future PR
adding one doesn't have to restructure the three rules above.

## 2. Precision engineering for `negative_triggers`

Reading the runtime (`skills/guidefold/scripts/guidefold`, `Router.policy_filter`, ~line 1131)
confirms the fact this whole design is built around:

```python
for t in c.get("negative_triggers", []):
    ttoks = tokenize(t)
    if ttoks and set(ttoks) <= qtoks:
        hit_neg = t; break
```

`negative_triggers` is a **hard filter**, matched by unordered **token-set** containment, with no
length floor of its own. A short, mostly-stopword derived phrase is therefore dangerous: any query
whose tokens happen to be a superset of the phrase's tokens hard-drops the skill, regardless of word
order or position. Two defenses were added after finding this, both validated against the real
corpus:

1. **Per-phrase content-token floor.** `_finalize_phrase(..., min_content_tokens=2)` for
   `negative_triggers` (vs. 1 for `triggers`) — a phrase needs 2 tokens that are not stopwords, not
   just "not stopword-only". This alone rejects phrases like "for the domain" that the original
   "not entirely stopwords" check let through.
2. **Corpus-wide boilerplate guard.** Even a content-bearing phrase can be boilerplate if it recurs
   verbatim across many otherwise-unrelated skills (a shared authoring template, not skill-specific
   signal). After deriving, `derive()` counts, per tokenized form, how many distinct skills carry a
   *derived* (never authored) `negative_triggers` phrase with that form, and drops any form present
   in more than `max(15, 1% of corpus size)` skills. Measured on the 2,037-skill reference corpus
   before this guard existed: **"You need a different domain" recurred in 221 skills**; two more
   forms ("a simpler more specific tool can handle the", "the user needs general purpose assistance
   without domain") recurred in **49 skills each**; the next most common derived form recurred in
   only **11** — a clean natural gap the `max(15, 1%)` threshold sits inside. All three outliers are
   fully removed by the guard; the legitimate long tail (≤11 skills) is untouched. Authored
   `negative_triggers` are exempt no matter how common — repeating your own phrase is the author's
   choice (rule 3).

Both mechanisms are covered by dedicated unit tests
(`test_negative_trigger_needs_2_content_tokens_triggers_needs_only_1`,
`test_derived_negative_trigger_repeated_across_many_skills_is_dropped_as_boilerplate`,
`test_derived_negative_trigger_shared_by_only_a_few_skills_is_kept`,
`test_existing_negative_trigger_survives_the_boilerplate_guard_no_matter_how_common`).

## 3. SkillRetBench agreement (sanity check, not the gate)

Run via `tools/enrich/apply.py skillretbench`: `derive()` is given only `full_text` (+ `name`/`id`) for
each of the 501 skills, then its output is compared against the authored `composable_skills` (1,241
gold edges), `trigger_phrases`, and `anti_triggers` — fields it never saw.

| Comparison | Metric | Value |
|---|---|---:|
| `requires ∪ similar` vs. `composable_skills` (1,241 gold edges) | precision | **0.6008** |
| | recall | **0.9533** |
| | tp / fp / fn | 1183 / 786 / 58 |
| `triggers` vs. `trigger_phrases` | mean token-set Jaccard | 0.3019 (n=438) |
| | mean recall of authored tokens | 0.4299 (n=428) |
| | mean token precision vs. authored | 0.5902 (n=432) |
| `negative_triggers` vs. `anti_triggers` | mean token-set Jaccard | 0.5557 (n=501) |
| | mean recall of authored tokens | **0.8103** (n=501) |
| | mean token precision vs. authored | **0.6897** (n=435) |

Reading these honestly:
- **Edge recall is very high (0.95)** — derive's mention-based edge mining finds nearly every
  authored `composable_skills` relationship. **Edge precision is mediocre (0.60)** — see §5, worst
  false positive #1 (generic-word skill ids). This is the one number in this table I would not want
  someone to skim past: it is the direct, measured cost of the known limitation below, and it is why
  `requires`/`similar` edges should not be wired into ranking weights without addressing it first.
- **`negative_triggers` token recall (0.81) is good and its precision (0.69) is the best of the three
  token-comparisons** — consistent with deliberately trading trigger recall for negative_trigger
  precision throughout this design. The comparison here is still token-level, not semantic: a derived
  phrase that expresses the *same* real exclusion in different words scores as "imprecise" even when
  it is a correct negative trigger. §5 below reviews actual phrases, not just token overlap, which is
  the check that matters more than this number.
- **`triggers` recall (0.43) and precision (0.59) are the weakest pair**, expected: authors write
  `trigger_phrases` as terse, keyword-like tags (SkillRetBench's own convention), while this rule
  extracts fuller natural-language conditions ("you want to add structured product search to") from
  prose sentences — the two rarely match token-for-token even when they describe the same trigger.
  This is a recall/precision trade against a different *phrasing convention*, not evidence of wrong
  triggers; §5's "good derivations" example shows why.

## 4. Local corpus stats (2,037 skills, `experiment/skills`, gitignored)

Run via `tools/enrich/apply.py local experiment/skills`:

| | n | % |
|---|---:|---:|
| Skills with ≥1 `triggers` | 1,987 | 97.5% |
| Skills with ≥1 `negative_triggers` | 499 | 24.5% |
| Skills with ≥1 `requires` | 91 | 4.5% |
| Skills with ≥1 `similar` | 1,855 | 91.1% |
| Total edges (`requires` + `similar`) | 9,484 | — |

Rule attribution (item counts, not skills):

| rule | count |
|---|---:|
| `similar/edge_mining` | 9,360 |
| `triggers/section_mining` | 6,734 |
| `negative_triggers/section_mining` | 897 |
| `triggers/sentence_mining` | 469 |
| `requires/edge_mining` | 124 |
| `negative_triggers/sentence_mining` | 4 |

Confidence attribution: `similar/low` 7,797, `similar/high` 1,506, `requires/medium` 92,
`similar/medium` 57, `requires/high` 32 — the great majority of `similar` edges are low-confidence
bare mentions (§5 explains why that number should not be read as "9,360 good edges").

Top headings actually matched (frequency ≥15): `'When to Use'` 2,921, `'When to Use This Skill'`
1,865, `'Use this skill when'` 1,196, `'Do not use this skill when'` 513, `'When to Use This
Workflow'` 138, `'Trigger Phrases'` 90, `'When NOT to use'` 61, `'When to activate this skill'` 56,
`'When NOT to use this'` 52, `'When NOT to Use'` / `'How to use this skill'` 50 each, `'When to Use
What'` 28, `'When to Use This Skill'` (as a negative-trigger heading, i.e. mislabeled combined
sections) 27, `'When to Use Each'` 19, `'When to use this skill'` 17, `'Use This Skill When'` 15 — the
authoring conventions in this corpus converge heavily on a handful of heading phrasings, which is why
the curated regex list generalises as well as it does without an LLM pass.

## 5. Examples

### Good derivation — `buywhere-product-catalog`

Body has an explicit `## When to Use This Skill` bulleted section and a `## Related Skills` section
using `@skill-name` formatting. Derived:

```
triggers: [
  "you want to add structured product search to",
  "the user asks for buywhere mcp setup in",
  "you need a concrete onboarding path for buywhere",
]
similar: [api-design-principles, mcp-builder, onboarding, api-onboarding,
          api-integration, documentation, screenshots, setup-help]
```

The three `triggers` are exactly the three authored bullets (cue-stripped), correctly extracted and
capped. `similar` contains the two intended matches (`api-design-principles`, `mcp-builder`, from the
explicit `@`-prefixed "Related Skills" list) — but also 6 false positives, which is worst-false-
-positive #1 below.

### Worst false positive #1 — generic-English-word skill ids contaminate edges (found, documented, **not fixed** in this PR)

Same skill, same `similar` list: `onboarding`, `api-onboarding`, `api-integration`, `documentation`,
`screenshots`, `setup-help` are **not** related skills — they are ordinary English words/compounds
("...API key **onboarding** flow...", "...**documentation** surfaces can change...") that happen to
be the literal `id` of some other real skill in the corpus. `MIN_ID_CHARS=7` (raw character count) is
used as a proxy for "this token is specific enough to be a deliberate cross-reference", which fails
for common vocabulary at or above 7 characters (`architecture`, `database`, `patterns`, `templates`,
`onboarding`, `documentation`). This is not confined to `similar`: it was also confirmed to produce
bad `requires` edges elsewhere in the corpus (e.g. `rex → requires → architecture`,
`agent-orchestration-improve-agent → requires → evaluation`). It is the direct cause of the 0.60 edge
precision in §3.

**Why not fixed here:** a real fix needs raw-text formatting cues (backticks, `@`-prefixes, markdown
links) plumbed through to the mention classifier — bare mentions without such a cue should require a
much higher specificity bar than "≥7 characters", or should be dropped from `requires` entirely and
only ever contribute to `similar`. That is a bigger, structural change than fits in this PR, and:
`similar` is not consumed by the shipped index today (`Index._build_graph` only initializes empty
adjacency for it — CONVENTIONS.md: "generated, never authored", not yet wired into ranking); this
PR's own brief frames its SkillRetBench numbers as a sanity check, with family evaluation (which must
address this before any `requires`/`similar` weight is turned on) still pending. Documented here as
the most significant known limitation rather than silently shipped.

### Worst false positive #2 — boilerplate `negative_triggers` duplicated across 49–221 skills (found and **fixed**)

See §2. Before the corpus-wide boilerplate guard existed, "You need a different domain" was derived
as a `negative_triggers` phrase on 221 distinct skills in the reference corpus — meaning any query
containing those 4 content-ish tokens (in any order, anywhere in the query) would have hard-dropped
all 221 of them, regardless of actual relevance. Fixed by the guard described in §2; covered by
`test_derived_negative_trigger_repeated_across_many_skills_is_dropped_as_boilerplate`.

### Worst false positive #3 — "do not use for X" sentences misread as a trigger *for X* (found and **fixed**)

The most serious bug found this PR — an exact semantic reversal, not just noise. `examples/monorepo`'s
`security-baseline` skill has the description sentence *"Do not use for classification-label
semantics or audit-event formats, which the security org owns in its own skills."* This sentence
matches `EXCLUSION_SENTENCE_RE` (correctly, via "do not use") **and** `USAGE_SENTENCE_RE` (because it
also contains the literal substring "use for", which that regex has no negation-awareness against).
Before the fix, checking both regexes independently on every sentence produced both a correct
`negative_triggers` candidate ("for classification-label semantics") **and** an incorrect,
exactly-backwards `triggers` candidate ("classification-label semantics") for the very thing the skill
says it is *not* for. Fixed by making exclusion-classification take precedence and be mutually
exclusive with usage-classification for the same sentence/bullet (in both the unheaded-prose sentence
loop and the heading-gated bullet-extraction loop — a heading like "When to use / when NOT to use" is
classified `is_usage` only, so its individual "do not use..." bullets needed their own reroute).
Caught by `test_derived_fields_never_contradict_authored_fields_on_the_real_fixture` in
`tests/test_enrich_apply.py`, which asserts no derived field's tokenized form matches an authored
field of the opposite polarity for the same skill — a check the synthetic unit tests, which never
happened to construct a sentence matching both cue regexes at once, would not have caught. Impact was
not confined to this one fixture skill: fixing it moved the SkillRetBench `triggers`-vs-authored token
precision (§3) from 0.358 pre-fix to 0.590 post-fix.

## 6. Tests

`tests/test_enrich_derive.py` (23 tests): section extraction (usage/exclusion headings and bare
"Anti-Patterns"/"Triggers" headings correctly *not* treated as exclusion), cue-boilerplate stripping,
sentence-level cues in unheaded prose, both caps, dedup-by-tokenized-form, short/stopword-only phrase
rejection, the negative_trigger 2-content-token floor, dependency vs. related edge classification
(heading and in-prose cue), bare-mention low-confidence classification, `MIN_ID_CHARS` boundary,
self-edge exclusion, `requires`-cycle detection and demotion to `similar`, existing-fields-win for
both triggers/negative_triggers/requires, and both directions of the boilerplate guard (dropped when
common, kept when rare, never dropped when authored).

`tests/test_enrich_apply.py` (3 tests): the real-`examples/monorepo`-fixture contradiction test that
caught worst-false-positive #3 above, plus a round-trip test building cards with `apply.build_cards`,
loading them with `Index.from_cards`, and confirming the `requires` graph edge appears and
`Router.policy_filter` runs cleanly over the enriched cards.

Full suite: `pytest -q` — 315 tests, all green (26 net-new this PR).

## 7. Summary for family evaluation

F5's extractor is built and self-consistent (never contradicts authored fields, respects existing
data, never cycles). Its `negative_triggers` output is deliberately conservative and defended in depth
against the router's hard-filter semantics — this is the property that matters most and it is in good
shape (0.81 token recall / 0.69 token precision vs. authored `anti_triggers`; the two precision bugs
found this session are fixed). Its edge output (`requires`/`similar`) has high recall but only
moderate precision (0.60), traced to one specific, well-understood, and clearly documented root cause
(`MIN_ID_CHARS` as a proxy for reference-specificity) rather than a diffuse quality problem — family
evaluation should treat that as the concrete next fix before enabling any edge-derived ranking weight,
and should run the actual `all_required@4` gate this report does not attempt.
