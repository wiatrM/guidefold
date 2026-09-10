# R22 novelty review and executable baseline readiness

Status: primary-source review, 10 September 2026; no new experiments.
Purpose: advance the owner's LLM-built skill-hierarchy and monorepo-agent goal while preserving the requested pause in experiments.
Inputs: [R22 mechanism audit](2026-09-10-r22-mechanism-audit.md), the [9 September literature review](../../../research/literature-update-2026-09-09/README.md), current paper versions and pinned official code.
Scope: supplements the earlier review with graph evolution and concrete baseline interfaces; does not change product requirements, ranking, presentation metrics or deployment. The full scientific goal remains unachieved.

## Decision

Keep hierarchical skill retrieval as the product direction. R22 provides a positive pooled retrieval result, including recovered candidates outside the initial pool. It has not established new science merely by combining generated descriptions, structural expansion and source checks. The next study must compare against existing navigable/evolving libraries and measure task execution in real repository scopes. Repeating tuning on the exposed SRA queries would not resolve that gap.

## Closest primary sources

| Work, verified version | Overlap with Guidefold | Consequence |
|---|---|---|
| [Corpus2Skill, v4, 26 August](https://arxiv.org/html/2604.14572v4) | Compiles summaries into a navigable skill hierarchy; agents browse branches and fetch original documents. Its eleven-dataset study has wins, ties and losses. | LLM hierarchy construction, navigation and structure-dependent gains are established comparisons. R22 is a fixed selector plus dense expansion, not a reproduction of this agentic method. |
| [SkillDAG, v2, 2 July](https://arxiv.org/html/2606.03056v2) | Exposes matches, typed neighbors and conflicts; agents propose graph edits, subject to structural checks and reversible logging. | Expansion beyond vector matches and guarded graph evolution cannot be our standalone novelty. Compare both static and evolved state. |
| [SE-GoS, v1, 8 September](https://arxiv.org/html/2609.08228v1) | Updates graph topology, edge weights and retrieval descriptions from execution traces. | Learning a better skill map from logs is now a direct baseline, not an unoccupied contribution. |
| [Graph-of-Skills, v3](https://arxiv.org/abs/2604.05333v3) | Combines semantic/lexical seeds, graph diffusion and bounded delivery. | Compare against structural retrieval as well as flat dense. |
| [Skill2Query, v1](https://arxiv.org/abs/2608.16071v1) | Generates skill-conditioned pseudo-queries for enrichment, expansion and training. | Generated task examples are an established retrieval signal; cluster-level economy must be measured rather than assumed. |
| [RAPTOR](https://arxiv.org/abs/2401.18059) | Recursively clusters and summarizes text for tree retrieval. | Abstract hierarchy alone is insufficient as a method claim. |

SE-GoS needs a careful reading: the full study reuses traced tasks; a separate 50/37 split reports +5.4 reward points, which the authors place inside their noise band. Its headline substrate uses lexical seeding and a token-overlap graph. Repeated evolution reaches 59.4, 59.8 and 54.0 reward. These are reported results, not our reproduction, and they motivate held-out evaluation and monitoring regressions rather than assuming every update helps. No attributable SE-GoS implementation was found in the reviewed paper links and targeted search; availability remains unverified.

## What the code inspection establishes

These are source-readiness checks, not successful baseline runs. Repository metadata reported MIT for each pinned project; third-party datasets retain their own terms.

| Official source and pinned commit | Inspected entry | Practical consequence |
|---|---|---|
| [Corpus2Skill](https://github.com/dukesun99/Corpus2Skill/tree/b0108ce22d434983cf97abc2ca455aebc6b625dd) | `corpus2skill/config.py`, `serve.py` | Native serving uses Anthropic skill upload and a document store. A Pi port is an adaptation and must be labelled as such. |
| [SkillDAG](https://github.com/Ericbai06/SkillDAG/tree/2bd7baffae58854018f75857e5626a4a28a705ae) | `src/skilldag/graph.py`, SkillsBench YAML | `search` retains vector matches separately from graph neighbors/conflicts; embedding cache invalidates on text/model change. Docker/Harbor configuration is present; execution is unverified here. |
| [Graph-of-Skills](https://github.com/davidliuk/graph-of-skills/tree/203f60a2c689da055ce1ac351eb3cb9912a3bca7) | README and repository tree | Official structural-retrieval baseline located and pinned; the implementation was not fully audited or run. |

Corpus2Skill's `_get_document` returns exact-ID content or a prefix match. SkillDAG's reviewed graph checks address cycles, contradictory edge polarity and reversibility. Those particular mechanisms do not establish Guidefold's requested repository-scope/revision authorization. This is a bounded comparison of inspected functions, not a claim that no other version or system implements that boundary.

## Candidate contribution and the test that could distinguish it

Working hypothesis, **not an established novelty claim**: an LLM-built search hierarchy can learn cross-team routes while the original repository scope and revision remain binding on delivery; useful retrieval gains survive both unseen tasks and later repository changes.

The map answers where to search. It must not grant authority to a rule merely because that rule was useful in a neighboring team. A successful task trace is evidence of utility in that task; it does not authorize changing a shared convention. This keeps the complete product goal—automatic hierarchy plus better harness execution—rather than substituting an isolated safety checker.

After the pause, the decisive design should have these properties before any model call:

1. **Repository and time separation.** Build from an initial immutable repository snapshot; learn only from development tasks. Freeze artifacts before unseen tasks in sibling scopes and a later revision. Reference answers, hidden evaluation tests and evaluators' expected-scope labels stay unavailable to the map builder and executing agent; ordinary repository tests and source rules remain available. Split by related task/source family, not random prompts sharing the same skill.
2. **Two distinct comparisons.** For scientific positioning, compare to pinned Corpus2Skill and SkillDAG with documented adapters and equal agent budgets. To isolate the map, compare Guidefold flat versus generated-map retrieval through the same delivery contract, model and tools. Hold source content and proof eligibility constant across that pair.
3. **Separate authorization effect.** Compare the same frozen map with and without revision/scope enforcement in a sandbox. Include useful deliverable skills, stale/conflicting skills and unanswerable requests. ASK alone cannot win; report false abstention and task failures as well as harmful/stale loads.
4. **Execution as the primary outcome.** Use existing task verifiers where they express correctness, blinded to method. Fix expected scope from repository source before trials. Ambiguous semantic cases still require independent adjudication; code tests do not prove a policy's meaning. Report paired task-level results, tokens, time and all failed harness attempts separately.
5. **Evolution with a protected evaluation set.** Record map versions and every proposed update. Select stopping/rollback rules on development data; never select the best round after seeing held-out reward. Measure repeated updates as well as the first positive round. Preserve original source identifiers, revisions and eligibility throughout.
6. **Resolve the SRA shortcut separately.** A prefix-blind reconstruction can diagnose the existing benchmark effect, but remains exploratory on this exposed corpus. It cannot replace the real-repository execution comparison or become a new confirmatory holdout by renaming the split.

This is a design constraint list, not a frozen protocol or permission to resume experiments. Task inventory, sample size/power, compute budget and implementation fidelity still have to be set before execution. No agents, benchmarks or paid model calls were launched for this review.

## Evidence and reproducibility

The arXiv API confirmed Corpus2Skill v4, SkillDAG v2 and SE-GoS v1 identifiers, titles and revision dates. The `arxiv-lookup` workflow was applied through the direct API with Python's standard library because its optional `arxiv` package was unavailable; its supplied CLI script was not run. GitHub API supplied default-branch commit identifiers, and pinned raw files were inspected as data without importing or executing them.

Snapshots, URLs, SHA-256 and retrieval time: [manifest](../../../.guidefold/checks/r22-prior-art-20260910/manifest.json). Fetch command: bundled Windows Python `.guidefold/checks/r22-prior-art-20260910/fetch_sources.py`. All 12 requested primary-source files returned HTTP 200. This verifies access and retained bytes, not correctness of published results or completeness of the literature search. No new claims were added to public marketing from this review.
