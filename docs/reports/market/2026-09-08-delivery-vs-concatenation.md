# Ranked delivery versus concatenation: the concatenator never hit its limit

This is the committed copy of the write-up. The raw artefacts (`PROTOCOL.md`, `run.py`, `build_repo.py`, `placements.json`, the three generated repositories and the 232 KB `results.json` with every answer) live under `research/delivery-vs-concatenation-2026-09-08/`, which is gitignored, so they are on the machine that ran the experiment and not in this repository.

Status: completed, 183 cells (61 questions x 3 repository sizes), one pass each, real
`claude-haiku-4-5-20251001` calls through `claude -p`. Retrieval in the `guidefold` arm is the
shipped CLI (`guidefold find --scope <leaf>`), not a model. Cost: 19.58 USD.
Date: 2026-09-08. Protocol: `PROTOCOL.md`, frozen before the first model call.

**Verdict: the pre-registered claim was not confirmed.** The concatenated arm did not degrade as
the repository grew from 70 to 1,000 skills, and it matched or beat the ranked arm at 250 and
1,000. The reason is not that ranking is worse. It is that the experiment, as built, never put
the concatenator into the condition where ranking is supposed to matter: the set of files
applicable at a leaf stayed under the 32,768-character Codex default in 178 of 183 cells, so the
answer reached the agent in every cell of both arms. What the run does establish is narrower and
still useful, and it is stated below without the headline it was meant to produce.

## Why this exists

`docs/PRODUCT-FOCUS.md` states the product's first value proposition: location-scoped tools
concatenate every applicable rule file until a hard limit and truncate, while Guidefold ranks and
injects at most four cards with the body loaded on demand. `PROTOCOL.md` asked one question:
does ranked delivery answer questions that concatenation cannot, and at what repository size does
the difference appear?

## Material

- **Skills.** The 70 skills frozen on 2026-09-07 in
  `research/progressive-disclosure-execution-2026-09-07/skills-70.json` (local, gitignored) (26 Meridian fixture skills,
  44 sampled from public skill repositories). Repositories of 250 and 1,000 skills add filler
  drawn from the SkillRet pool with a fixed seed. Filler is never an answer skill.
- **Questions.** The 61 generated tasks from the same frozen set. Each has a strict keyword check
  of one to three phrases copied from the answer skill's body.
- **Trees.** `build_repo.py` writes one real monorepo per size under `repo-<size>/`, each with a
  `guidefold.yaml`, a three-level scope tree (`platform.team.service`) and one `SKILL.md` per
  skill. `placements.json` records where every answer skill landed and under which name.

## Arms

All three arms see the same question and the same model. They differ only in context.

| Arm | Context |
|---|---|
| `oracle` | The body of the one skill the question is about, capped at 8,000 characters. Upper bound on the question, not on delivery. |
| `concatenated` | Every skill applicable at the leaf under the nearest-wins convention, full text in path order, cut at 32,768 characters. |
| `guidefold` | What the shipped CLI returns for that leaf: ranked cards. The agent may reply `LOAD: <name>` once and receive that skill's body. |

## Result, pre-registered metric

Percent of the 61 questions passing the strict keyword check. This is the metric `PROTOCOL.md`
committed to; the 1,000 row is contaminated, see the next table.

| Size | oracle | concatenated | guidefold |
|---:|---:|---:|---:|
| 70 | 57.4 | 73.8 | **77.0** |
| 250 | 60.7 | **78.7** | 72.1 |
| 1,000 | 42.6 | **73.8** | 59.0 |

Ten cells at size 1,000 (questions 52 to 61, the last ten in run order) returned no answer in any
arm because the `claude -p` calls failed while the account's usage limit was exhausted. They count
as wrong above. Excluding them:

| Size | n | oracle | concatenated | guidefold |
|---:|---:|---:|---:|---:|
| 1,000 | 51 | 51.0 | **88.2** | 70.6 |

Read either way, `concatenated` did not degrade with size and `guidefold` did not hold. The
direction is the opposite of the claim.

## Did the answer even reach the agent

This is the number the claim depends on, and it is 100 percent everywhere.

| Size | Concatenated: answer skill inside the 32,768 cut | Cells truncated at all | Median applicable characters | Guidefold: answer skill among the cards | Guidefold: body loaded |
|---:|---:|---:|---:|---:|---:|
| 70 | 61 / 61 | 2 / 61 | 8,341 | 61 / 61 | 55 / 61 |
| 250 | 61 / 61 | 6 / 61 | 16,249 | 61 / 61 | 53 / 61 |
| 1,000 | 61 / 61 | 6 / 61 | 16,249 | 61 / 61 | 45 / 61 |

Two facts explain the table.

1. **The applicable set is a function of tree depth, not repository size.** Under nearest-wins a
   leaf sees its own skills plus its ancestors' skills. `build_repo.py` places filler across the
   whole tree, so a bigger repository is a wider tree, not a heavier path. The applicable set at
   every one of the 61 leaves is byte-identical between 250 and 1,000 skills, and the largest
   applicable set at any size is 43,217 characters. Concatenation was cut in 14 cells out of 183
   and the cut never removed the answer skill.
2. **Retrieval was never the bottleneck.** The shipped router returned the answer skill as the
   first card in 61 of 61 questions at every size. It returned one or two cards per query, not
   four. Everything that separates the arms happened after delivery, in how the model answered.

## What actually separated the arms

**The strict keyword check rewards quoting the source.** The check phrases are lifted from the
skill bodies ("adds them before", "versioned", "default 50", "request paths"). An answer that says
"30 seconds" to a question whose check is `statement_timeout` and `request paths` is scored wrong.
The `concatenated` arm, holding the full text of every applicable rule, quotes it; the `oracle`
arm was told to answer without caveats and is the tersest of the three; the `guidefold` arm sits
in between. Mean answer length was 73 to 91 characters for `oracle`, 155 to 160 for
`concatenated`, 186 to 197 for `guidefold`. That is why the upper-bound arm scores below both
delivery arms at every size, which is impossible if the check measured correctness.

A post hoc rescore, not pre-registered, counts an answer as correct if any one check phrase
appears after case and punctuation are stripped. Failed calls excluded.

| Size | n | oracle | concatenated | guidefold |
|---:|---:|---:|---:|---:|
| 70 | 61 | 95.1 | 96.7 | 91.8 |
| 250 | 61 | 96.7 | 95.1 | 90.2 |
| 1,000 | 51 | 92.2 | 100.0 | 90.2 |

Under the lenient rescore the `oracle` arm flips between correct and wrong on identical input in 6
of 61 questions across sizes; under the strict check it flips in 23 of 61. The strict check, not
the model, is the main source of variance in the first table. The lenient rescore is reported as a
diagnostic only. It was chosen after seeing the data and it inflates every arm.

**The guidefold arm's remaining gap is protocol and calibration, not retrieval.** Of its wrong
cells at each size (excluding failed calls): 9 to 10 loaded the right body and then failed the
strict check; 2 per size replied with a backticked `` `LOAD: <name>` `` that the harness did not
parse as a load request because it looked only for an unquoted prefix, so the literal string was
scored as the answer; 2 to 5 answered from the card or from general knowledge without loading
(`run-the-tests` was answered from pytest folklore at more than one size) and missed the check. The
progressive-disclosure run one day earlier saw the same calibration miss at a similar rate.

## What would have refuted the claim, restated

`PROTOCOL.md` said: if `concatenated` matches `guidefold` at 1,000 skills, ranked delivery buys
nothing on this corpus and the value proposition is wrong as stated. `concatenated` did not merely
match at 1,000; it led by 14.7 points on the pre-registered metric and by 17.6 points with failed
calls excluded. On this corpus, as built, the refutation condition was met.

It also said: if `guidefold` matches `oracle` at every size, the retrieval step is not doing work
and the questions are too easy. `guidefold` exceeded `oracle` at every size, which is a scoring
artefact rather than evidence that the questions were hard.

The honest reading is neither "ranking loses" nor "ranking wins". The experiment did not create the
truncation regime it set out to test, so it cannot speak to the value proposition. Where it did
score, concatenating 8 to 16 kilobytes of applicable rules was at least as good for a Haiku-class
model as receiving one card and asking for one body, and the one-round-trip design cost a few
points of calibration. That is a real cost of progressive disclosure that the product copy should
not hide.

## Limitations

- **Single pass, temperature not pinned.** `claude -p` exposes no temperature control. The strict
  check flips 23 of 61 oracle cells on identical input across sizes; arm differences under 15
  points are inside that noise.
- **Strict keyword scoring.** Phrases copied from the source body measure quotation, not
  correctness, and they punish the terse arms. The pre-registered metric is reported first because
  it was pre-registered, not because it is the better measure.
- **Public filler corpus.** Filler skills come from SkillRet, a public pool with its own style. A
  real monorepo's filler is written by the same teams as the answer skills and would compete
  harder in ranking; here ranking was perfect, so this limit did not bite, but it would in a
  harder design.
- **Head truncation at the Codex default.** Cutting at 32,768 characters from the head is what
  Codex does by default. A tool that truncated per file, or that dropped ancestors first, would
  behave differently. Only 14 of 183 cells were cut at all.
- **Ten failed calls.** The last ten questions at 1,000 skills have no answer in any arm because
  the run outlasted the account's usage window. They were not rerun, to keep the run single pass
  and the protocol unchanged; the tables above show both treatments.
- **The `LOAD` parser.** Two cells per size lost to a backtick. This is a harness defect, recorded
  here rather than patched after the fact.
- **The model had tools.** `claude -p` ran with the repository as working directory, and in at
  least one cell the model tried to open a file instead of using the context it was given.

## What a second run needs before this question can be answered

1. Place filler on the ancestor path of every answer skill so the applicable set at each leaf is
   pre-computed to exceed the truncation limit at 250 and 1,000, and record per cell whether the
   answer skill fell past the cut. Without this the concatenated arm has nothing to lose.
2. Pre-register a scoring rule that does not reward quotation: the number-and-identifier tokens
   only, or a judge with a frozen rubric, and check it against the oracle arm before the run.
3. Three passes per cell, reported as mean and range.
4. Accept `LOAD: <name>` with or without code formatting, and run the answering model without
   tools.
5. Keep the shipped CLI as the retriever. Its 61 of 61 top-1 result at 1,000 skills on this
   corpus is the one number from this run that supports the product, and it should be reported
   as retrieval evidence on a development corpus, not as delivery evidence.

## Post hoc addendum: the same trees under tighter competitor limits

Computed after the run, from the trees on disk, with no model calls. `PROTOCOL.md` chose the
Codex default (32,768 characters), the most generous limit among the tools named in
`docs/PRODUCT-FOCUS.md`. Rebuilding the same applicable blobs and cutting them at other
defaults gives the number the claim actually turns on: would the answer skill have been inside
the cut at all.

| Size | Codex 32,768: answer cut away | Windsurf 12,000: answer cut away | ~8,000 (1 percent of a 200k window): answer cut away |
|---:|---:|---:|---:|
| 70 | 0 / 61 | 19 / 61 | 28 / 61 |
| 250 | 0 / 61 | 27 / 61 | 37 / 61 |
| 1,000 | 0 / 61 | 27 / 61 | 37 / 61 |

Under the Windsurf default the concatenating arm would have had no chance on 44 percent of
questions at 250 and 1,000 skills, whatever the model did. The 8,000 figure is an approximation
of Claude Code's 1 percent listing cap and is not the same mechanism (that cap applies to the
skill listing, not to bodies), so it is a bound, not a measurement of Claude Code.

This addendum is descriptive and chosen after seeing the data. It does not change the verdict
above. It says where a second, pre-registered run should look: the limit is a per-arm parameter
and every named default is reported side by side, including the one where concatenation wins.
See `PROTOCOL-v2.md` (draft, not frozen).

## Files

- `PROTOCOL.md`: frozen design and refutation clause.
- `build_repo.py`, `placements.json`, `repo-70/`, `repo-250/`, `repo-1000/`: the trees.
- `run.py`: the three arms, the strict check, the summary.
- `results.json`: 183 rows with every prompt's answer, the check phrases, truncation flags and
  card lists. Every number in this file can be recomputed from it.
