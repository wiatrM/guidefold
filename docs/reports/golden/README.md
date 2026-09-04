# Golden-set reports

`python3 tools/eval/run_golden.py` runs Router 0.1 over the 220 labelled queries in
`tests/golden/` and writes `<git-sha>.md` here. `baseline.json` is the machine-readable snapshot
the CI gate (`--check`) compares against; it is updated deliberately with `--update-baseline`,
never by CI.

## The Router has two orderings, and they must be measured separately

This is the most important thing to understand before reading any number in these reports.

| | produced by | ordered by | answers |
|---|---|---|---|
| **Retrieval** | `Router.score` | score descending, tie-broken on URN | *Did ranking put the right skills on top?* |
| **Injection** | `Router.select` | **node depth**, root-most first | *Did the ≤ 4 cards the agent receives hold the whole answer, and no plausible-but-wrong one?* |

`select` deliberately re-orders general → specific because that is the order an agent should
*read* the cards in (E1.5) — org-wide guidance before team-specific guidance. It is a
presentation decision taken **after** ranking has already chosen membership.

So the two lists answer different questions, and each metric is read from the table that
actually answers its own:

- `hit@1`, `recall@8`, `nDCG@10` ← **retrieval**
- `completeness@4`, `distractor_rate@4` ← **injection**

### Why this is called out so loudly

The first version of the runner fed the *injection* order into every ranking metric. That asks
"is the root-most card the most relevant one?", which is false almost by construction — root
skills are the general ones. It understated `hit@1` by **64 points** (0.236 against a true
0.874) and `nDCG@10` by 42 points, and it made Router 0.1 look dramatically *worse* than the
scope-only baseline it replaced.

Nothing about the router was wrong; the ruler was. `tests/test_eval_ordering.py` now guards the
distinction — including a test that fails if the two orderings ever coincide on every probe,
because that would mean either `select` stopped honouring the read-order contract or `score`
started sorting by depth.

## Router 0.1 vs B0 — the M2 comparison

B0 is the literal original CLI at commit `984d08c`, extracted from git with `git show` and run as
a subprocess at each case's `cwd`. It is not a reimplementation, so the comparison cannot flatter
the new code by accident. Its ranking was scope-distance only (`sorted(hits, key=_rank)`), which
is the P0 bug Router 0.1 replaces.

| metric | B0 | Router 0.1 | Δ |
|---|---|---|---|
| hit@1 | 0.6839 | **0.8736** | **+18.97 pp** |
| nDCG@10 | 0.7959 | **0.8880** | **+9.21 pp** |
| completeness@4 | 0.9023 | **0.9713** | **+6.90 pp** |
| recall@8 | 0.9310 | 0.9339 | +0.29 pp |

### Recall@8 is saturated on this fixture, and MVP §5's M2 gate should not be read literally

`docs/MVP.md` sets M2 as "shadow router beats B0 on the golden set (≥ +10 pp Recall@8)". That
threshold is **not reachable on the Meridian fixture, for a reason that has nothing to do with
router quality**: the fixture has 26 skills, and after the policy filter a typical query has only
8–18 *visible* candidates. Asking for recall at rank 8 out of a pool of ~10 is close to asking
"is the answer in the list at all", and B0 already scores 0.931 there — leaving at most 6.9 points
of headroom, so +10 pp is arithmetically impossible.

The metrics that still discriminate at this corpus size are `hit@1` (+18.97 pp) and `nDCG@10`
(+9.21 pp), both of which show a large, real improvement. **Recommendation:** restate M2 against
`hit@1` and `nDCG@10` for the fixture, and keep Recall@8 as the gate once the pilot corpus
(~200 skills) makes the metric informative again. Recorded here rather than silently substituting
a friendlier metric.

## Known weaknesses, reported rather than hidden

**Abstention does not work.** `abstention_precision` is undefined across all 220 cases because
the router never abstains. RRF is rank-based, so any rank-1 hit receives a near-constant high
score regardless of how relevant it truly is, and a magnitude threshold cannot discriminate
against that. The `no_applicable` stratum (44 cases, 20 % of the set) therefore measures nothing
today. A working gate needs a different confidence signal — the pre-fusion top score, or the
rank-1/rank-2 margin. This is a follow-up story, not a tuning exercise.

**Distractor rate is high.** `distractor_rate@4` is 0.489 overall and 0.500 on `no_applicable` —
the latter is the abstention failure showing through, since a router that always answers will
always inject something into a query that deserved silence. `sibling_ambiguity` at 0.621 is the
one to attack first: those are the cases where a plausible sibling skill is reaching the agent.
